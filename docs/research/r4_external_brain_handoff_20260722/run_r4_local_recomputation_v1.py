#!/usr/bin/env python3
"""Run one locally rederived R4 quantitative checker in an offline sandbox."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from types import ModuleType
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RESEARCH_DIR.parents[2]
SELECTOR_PATH = RESEARCH_DIR / "select_r4_ready_receipt_v1.py"
STRICT_INSTANCE = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
STRICT_INSTANCE_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
FIXED_PYTHON = Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
BWRAP = Path("/usr/bin/bwrap")
TIMEOUT_SECONDS = 60
MAX_STDIO_BYTES = 1_000_000
IDENTITY_KEYS = {"relative_path", "size_bytes", "sha256"}
FILE_RECORD_KEYS = {"path", "size_bytes", "sha256"}
ALLOWED_IMPORTS = {
    "argparse",
    "collections",
    "dataclasses",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "json",
    "math",
    "operator",
    "pathlib",
    "statistics",
    "sys",
    "typing",
}
BANNED_CALL_NAMES = {
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "setattr",
    "vars",
    "__import__",
}
BANNED_ATTRIBUTES = {
    "fork",
    "forkpty",
    "kill",
    "meta_path",
    "modules",
    "popen",
    "system",
}


class RecomputationError(RuntimeError):
    """Fail-closed local recomputation error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise RecomputationError(f"symlink is not a provenance file: {path}")
    resolved = path.resolve(strict=True)
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise RecomputationError(f"not a regular provenance file: {resolved}")
    return {"path": str(resolved), "size_bytes": resolved.stat().st_size, "sha256": _sha256(resolved)}


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise RecomputationError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise RecomputationError(f"non-finite JSON value in {path}: {value}")

    try:
        value = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputationError(f"cannot parse local control JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecomputationError(f"local control JSON is not an object: {path}")
    return value


def _identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != IDENTITY_KEYS:
        raise RecomputationError(f"{label} is not an exact selected receipt identity")
    relative, size, digest = value.get("relative_path"), value.get("size_bytes"), value.get("sha256")
    if type(relative) is not str or not relative:
        raise RecomputationError(f"{label}.relative_path is malformed")
    path = Path(relative)
    if path.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in path.parts):
        raise RecomputationError(f"{label}.relative_path is not normalized")
    if type(size) is not int or size < 0:
        raise RecomputationError(f"{label}.size_bytes is malformed")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise RecomputationError(f"{label}.sha256 is malformed")
    return {"relative_path": relative, "size_bytes": size, "sha256": digest}


def _file_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != FILE_RECORD_KEYS:
        raise RecomputationError(f"{label} is not an exact file record")
    path_value, size, digest = value.get("path"), value.get("size_bytes"), value.get("sha256")
    if type(path_value) is not str or not Path(path_value).is_absolute():
        raise RecomputationError(f"{label}.path must be absolute")
    expected = {"path": path_value, "size_bytes": size, "sha256": digest}
    if _record(Path(path_value)) != expected:
        raise RecomputationError(f"{label} bytes are stale")
    return expected


def _selector() -> ModuleType:
    if not SELECTOR_PATH.is_file() or SELECTOR_PATH.is_symlink():
        raise RecomputationError(f"local READY selector is unavailable: {SELECTOR_PATH}")
    name = "_r4_ready_selector_for_local_recomputation"
    spec = importlib.util.spec_from_file_location(name, SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RecomputationError("cannot load local READY selector")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _check_selected(authority_run: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    checker = getattr(_selector(), "check_selected_receipt", None)
    if not callable(checker):
        raise RecomputationError("local READY selector lacks check_selected_receipt")
    try:
        result = checker(authority_run, expected_identity=dict(identity))
    except Exception as exc:
        raise RecomputationError(f"selected receipt failed semantic/byte replay: {exc}") from exc
    if not isinstance(result, Mapping):
        raise RecomputationError("selected receipt checker returned a malformed result")
    return dict(result)


def _validate_ingest(response_run: Path, authority_run: Path) -> dict[str, Any]:
    intent = _strict_json(response_run / "canonical-intent.json")
    ingest = _strict_json(response_run / "response-ingest.json")
    if ingest.get("schema") != "r4_response_ingest_v1" or ingest.get("status") != "ARCHIVED_PENDING_RECOMPUTATION":
        raise RecomputationError("response ingest is not terminally archived")
    if intent.get("schema") != "r4_canonical_intent_v1":
        raise RecomputationError("canonical intent schema is invalid")
    identity = _identity(ingest.get("selected_receipt_identity"), "response_ingest.selected_receipt_identity")
    if _identity(intent.get("selected_receipt_identity"), "canonical_intent.selected_receipt_identity") != identity:
        raise RecomputationError("canonical intent selected receipt identity differs")
    selection = _check_selected(authority_run, identity)
    raw = _file_record(ingest.get("raw_response"), "response_ingest.raw_response")
    canonical = _file_record(ingest.get("canonical_document"), "response_ingest.canonical_document")
    if _file_record(intent.get("raw_response"), "canonical_intent.raw_response") != raw:
        raise RecomputationError("canonical intent raw response binding differs")
    if intent.get("canonical_target") != canonical["path"]:
        raise RecomputationError("canonical intent target differs from ingested canonical document")
    if (raw["size_bytes"], raw["sha256"]) != (canonical["size_bytes"], canonical["sha256"]):
        raise RecomputationError("raw and canonical response bytes differ")
    if ingest.get("raw_canonical_byte_equal") is not True:
        raise RecomputationError("response ingest did not close raw/canonical equality")
    package_id = ingest.get("package_id")
    if type(package_id) is not str or package_id != intent.get("package_id"):
        raise RecomputationError("response package identity is absent or inconsistent")
    if selection.get("package_id") not in {None, package_id}:
        raise RecomputationError("selected receipt package identity differs from response ingest")
    return {
        "selected_receipt_identity": identity,
        "package_id": package_id,
        "raw_response": raw,
        "canonical_document": canonical,
    }


def _validate_ledger(path: Path, provenance: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = _strict_json(path)
    if ledger.get("schema") != "r4_quantitative_claim_ledger_v1":
        raise RecomputationError("claim ledger schema is invalid")
    if ledger.get("status") != "COMPLETE" or ledger.get("quantitative_claims_complete") is not True:
        raise RecomputationError("claim ledger does not attest complete quantitative enumeration")
    identity = _identity(ledger.get("selected_receipt_identity"), "claim_ledger.selected_receipt_identity")
    if identity != provenance["selected_receipt_identity"]:
        raise RecomputationError("claim ledger selected receipt identity differs")
    if ledger.get("package_id") != provenance["package_id"]:
        raise RecomputationError("claim ledger package identity differs")
    if _file_record(ledger.get("raw_response"), "claim_ledger.raw_response") != provenance["raw_response"]:
        raise RecomputationError("claim ledger raw response binding differs")
    if (
        _file_record(ledger.get("canonical_document"), "claim_ledger.canonical_document")
        != provenance["canonical_document"]
    ):
        raise RecomputationError("claim ledger canonical document binding differs")
    if ledger.get("raw_canonical_byte_equal") is not True:
        raise RecomputationError("claim ledger did not bind raw/canonical equality")
    claims = ledger.get("claims")
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        raise RecomputationError("claim ledger claims must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    raw_size = provenance["raw_response"]["size_bytes"]
    for index, item in enumerate(claims):
        if not isinstance(item, Mapping):
            raise RecomputationError(f"claim {index} is not an object")
        claim_id = item.get("claim_id")
        if type(claim_id) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", claim_id) is None:
            raise RecomputationError(f"claim {index} has an invalid claim_id")
        if claim_id in by_id:
            raise RecomputationError(f"duplicate claim_id: {claim_id}")
        span = item.get("source_byte_span")
        if not isinstance(span, Mapping) or set(span) != {"start", "end"}:
            raise RecomputationError(f"claim {claim_id} has an invalid source byte span")
        start, end = span.get("start"), span.get("end")
        if type(start) is not int or type(end) is not int or not (0 <= start < end <= raw_size):
            raise RecomputationError(f"claim {claim_id} source byte span is out of range")
        if "expected_result" not in item:
            raise RecomputationError(f"claim {claim_id} lacks expected_result")
        by_id[claim_id] = dict(item)
    return ledger, by_id


def validate_claim_ledger(
    path: Path, provenance: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Public read-only ledger validator reused by the final admission gate."""
    return _validate_ledger(path, provenance)


def validate_local_script(path: Path) -> dict[str, Any]:
    """Apply the fail-closed static policy to a locally authored checker."""
    if path.is_symlink() or not path.is_file():
        raise RecomputationError(f"local checker is not a regular file: {path}")
    raw = path.read_bytes()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecomputationError("local checker is not UTF-8 Python source") from exc
    lines = len(raw.splitlines())
    if lines == 0 or lines >= 200:
        raise RecomputationError(f"local checker must contain 1..199 physical lines; got {lines}")
    try:
        tree = ast.parse(source, filename=str(path), mode="exec")
    except SyntaxError as exc:
        raise RecomputationError(f"local checker syntax error: {exc}") from exc
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                raise RecomputationError("relative imports are forbidden in a local checker")
            names = [node.module]
        else:
            names = []
        for name in names:
            root = name.split(".", 1)[0]
            if root not in ALLOWED_IMPORTS:
                raise RecomputationError(f"local checker import is not allowlisted: {name}")
            imports.add(name)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALL_NAMES:
                raise RecomputationError(f"local checker call is forbidden: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and (
                node.func.attr in BANNED_ATTRIBUTES
                or node.func.attr.startswith(("exec", "spawn"))
                or node.func.attr.startswith("__")
            ):
                raise RecomputationError(f"local checker attribute call is forbidden: {node.func.attr}")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in BANNED_ATTRIBUTES):
            raise RecomputationError(f"local checker attribute is forbidden: {node.attr}")
    return {
        "physical_line_count": lines,
        "less_than_200_lines": True,
        "ast_policy": "PASS",
        "allowed_imports_used": sorted(imports),
        "locally_rederived_from_claim_only": True,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _publish_bytes(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise RecomputationError(f"no-overwrite target exists: {path}")
    pending = path.with_name(f".{path.name}.pending-{os.getpid():010d}")
    with pending.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(pending, path, follow_symlinks=False)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    try:
        pending.unlink()
    except OSError:
        pass


def _publish_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    _publish_bytes(path, raw)


def _bwrap_argv(script: Path, instance: Path) -> list[str]:
    python_root = FIXED_PYTHON.resolve(strict=True).parents[1]
    return [
        str(BWRAP),
        "--unshare-net",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib",
        "/lib64",
        "--ro-bind",
        str(python_root),
        "/python",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/scratch",
        "--dir",
        "/work",
        "--ro-bind",
        str(script),
        "/work/recompute.py",
        "--ro-bind",
        str(instance),
        "/work/problem_instance.json",
        "--chdir",
        "/work",
        "--setenv",
        "HOME",
        "/scratch",
        "--setenv",
        "TMPDIR",
        "/scratch",
        "--setenv",
        "PYTHONDONTWRITEBYTECODE",
        "1",
        "--setenv",
        "PYTHONNOUSERSITE",
        "1",
        "/python/bin/python3.13",
        "-I",
        "-S",
        "/work/recompute.py",
        "/work/problem_instance.json",
    ]


def build_sandbox_argv(script: Path, instance: Path) -> list[str]:
    """Return the one allowed offline checker argv for admission replay."""
    return _bwrap_argv(script, instance)


def run_recomputation(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    claim_id: str,
    script_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    authority_run = authority_run.resolve(strict=True)
    response_run = response_run.resolve(strict=True)
    provenance = _validate_ingest(response_run, authority_run)
    ledger, claims = _validate_ledger(ledger_path.resolve(strict=True), provenance)
    if claim_id not in claims:
        raise RecomputationError(f"claim_id is not present in the complete ledger: {claim_id}")
    policy = validate_local_script(script_path.resolve(strict=True))
    strict_record = _record(STRICT_INSTANCE)
    if strict_record["sha256"] != STRICT_INSTANCE_SHA256:
        raise RecomputationError("strict instance bytes are stale")
    if not BWRAP.is_file() or BWRAP.is_symlink():
        raise RecomputationError("bwrap is unavailable; offline execution is NO_GO")
    if not FIXED_PYTHON.exists() or not FIXED_PYTHON.resolve(strict=True).is_file():
        raise RecomputationError("fixed Python interpreter is unavailable")
    output_dir = output_dir.absolute()
    output_dir.mkdir(parents=True, exist_ok=False)
    script_snapshot = output_dir / "local-recomputation.py"
    instance_snapshot = output_dir / "problem_instance.json"
    _publish_bytes(script_snapshot, script_path.read_bytes())
    _publish_bytes(instance_snapshot, STRICT_INSTANCE.read_bytes())
    if validate_local_script(script_snapshot) != policy:
        raise RecomputationError("local checker bytes changed while being snapshotted")
    if _record(instance_snapshot)["sha256"] != STRICT_INSTANCE_SHA256:
        raise RecomputationError("strict instance snapshot differs")
    argv = _bwrap_argv(script_snapshot, instance_snapshot)
    try:
        completed = subprocess.run(
            argv, stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=TIMEOUT_SECONDS
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        completed = None
        timed_out = True
    else:
        stdout, stderr = completed.stdout, completed.stderr
    if len(stdout) > MAX_STDIO_BYTES or len(stderr) > MAX_STDIO_BYTES:
        raise RecomputationError("local checker output exceeds the fixed 1 MB cap")
    _publish_bytes(output_dir / "stdout.bin", stdout)
    _publish_bytes(output_dir / "stderr.bin", stderr)
    actual: Any = None
    parse_error: str | None = None
    if not timed_out and completed is not None and completed.returncode == 0:
        try:
            actual = json.loads(
                stdout.decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            parse_error = str(exc)
    expected = claims[claim_id]["expected_result"]
    status_value = (
        "EXECUTION_TIMEOUT"
        if timed_out
        else "EXECUTION_FAILED"
        if completed is None or completed.returncode != 0
        else "OUTPUT_INVALID"
        if parse_error is not None
        else "PASS_EXACT_MATCH"
        if actual == expected and type(actual) is type(expected)
        else "VALUE_MISMATCH"
    )
    ledger_record = _record(ledger_path.resolve(strict=True))
    report = {
        "schema": "r4_local_recomputation_report_v1",
        "created_at_utc": _utc_now(),
        "status": status_value,
        "claim_id": claim_id,
        "source_byte_span": claims[claim_id]["source_byte_span"],
        "package_id": provenance["package_id"],
        "selected_receipt_identity": provenance["selected_receipt_identity"],
        "receipt_semantic_replay_pass": True,
        "receipt_detached_byte_match": True,
        "raw_response": provenance["raw_response"],
        "canonical_document": provenance["canonical_document"],
        "raw_canonical_byte_equal": True,
        "claim_ledger": ledger_record,
        "claim_ledger_status": ledger.get("status"),
        "runner_tool": _record(Path(__file__).resolve()),
        "local_script": {**_record(script_snapshot), **policy},
        "strict_instance": _record(instance_snapshot),
        "sandbox": {
            "offline": True,
            "bwrap_unshare_net": True,
            "host_response_not_bound": True,
            "argv": argv,
            "timeout_seconds": TIMEOUT_SECONDS,
            "returncode": None if completed is None else completed.returncode,
            "timed_out": timed_out,
        },
        "stdout": _record(output_dir / "stdout.bin"),
        "stderr": _record(output_dir / "stderr.bin"),
        "expected_result": expected,
        "actual_result": actual,
        "output_parse_error": parse_error,
        "encoder_return_authorized": False,
    }
    _check_selected(authority_run, provenance["selected_receipt_identity"])
    _publish_json(output_dir / "recomputation-report.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-run", type=Path, required=True)
    parser.add_argument("--response-run", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--script", type=Path, required=True, help="locally authored checker; never response code")
    parser.add_argument("--output-dir", type=Path, required=True, help="new no-overwrite report directory")
    parser.add_argument("--attest-locally-rederived-from-claim-only", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_recomputation(
            args.authority_run,
            args.response_run,
            args.claim_ledger,
            args.claim_id,
            args.script,
            args.output_dir,
        )
    except (RecomputationError, FileExistsError, OSError) as exc:
        print(f"R4_LOCAL_RECOMPUTATION_FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "PASS_EXACT_MATCH" else 3


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run locally rederived R4 checkers against fixed local evidence only."""

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
ARCHIVER_PATH = RESEARCH_DIR / "archive_r4_response_bundle_v2.py"
LEDGER_BUILDER_PATH = RESEARCH_DIR / "build_r4_claim_ledger_v2.py"
STRICT_INSTANCE = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
STRICT_INSTANCE_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
W2D_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/witness-ea407fa-20260720")
W2D_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
FIXED_PYTHON = Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
BWRAP = Path("/usr/bin/bwrap")
TIMEOUT_SECONDS = 60
MAX_STDIO_BYTES = 1_000_000
ALLOWED_IMPORTS = {
    "__future__",
    "argparse",
    "collections",
    "functools",
    "hashlib",
    "itertools",
    "json",
    "math",
    "operator",
    "pathlib",
    "re",
    "sys",
    "typing",
}
BANNED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "setattr",
    "vars",
}
BANNED_ATTRIBUTES = {"fork", "forkpty", "kill", "popen", "system"}
PROFILES = {"strict_instance", "w2d_authority"}
EXPECTED_AUTHORITY_RUN = (
    PROJECT_ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722" / "run-20260722T084343Z-R4hP1A"
)
EXPECTED_RESPONSE_RUN = (
    PROJECT_ROOT
    / ".artifacts/track_b_r4_external_brain_handoff_20260722"
    / "responses/run-20260723T023657Z-R4resp-357f260d"
)
EXPECTED_PACKAGE_ID = "1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f"
EXPECTED_MANIFEST_SHA256 = "8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b"
EXPECTED_SELECTED_RECEIPT = {
    "relative_path": "verifications/independent-a002-20260722T0845Z/receipt.json",
    "sha256": "cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4",
    "size_bytes": 13840,
}
EXPECTED_READY_SELECTION = {
    "path": str((EXPECTED_AUTHORITY_RUN / "ready/selected-receipt.json").absolute()),
    "sha256": "ae121f1b16be01bc2a3b22ddb5bcf9365624cac8726b84364ddae52794bccee0",
    "size_bytes": 771,
}
EXPECTED_SELECTOR_TOOL = {
    "path": str(
        (PROJECT_ROOT / "docs/research/r4_external_brain_handoff_20260722/select_r4_ready_receipt_v1.py").absolute()
    ),
    "sha256": "f2a7c94edb73c661c35f0df25ef12faf2f411bc7898c8ef3ebb15577620d90e4",
    "size_bytes": 11474,
}
EXPECTED_RESPONSE_INGEST = {
    "path": str((EXPECTED_RESPONSE_RUN / "response-ingest.json").absolute()),
    "sha256": "f0cfeafc074460d92588d30b3a02c2636a781c56e3b9586c2a47597631b4e618",
    "size_bytes": 5709,
}
EXPECTED_SOURCE_IDENTITIES = {
    "response_text": {
        "path": "/home/zhuran24/下载/回复.txt",
        "sha256": "357f260d8da002cca947822aece83e0183161fb1efd4348f1fccecab0afe374a",
        "size_bytes": 6885,
    },
    "certificate_markdown": {
        "path": "/home/zhuran24/下载/r4_next_certificate.md",
        "sha256": "88196c4ae9de07a05f5d50467baa36d934857842f4c37239ef7d735c69cf8700",
        "size_bytes": 5268,
    },
    "certificate_python": {
        "path": "/home/zhuran24/下载/r4_next_certificate.py",
        "sha256": "d3169ba46fc55516cf047804d56ea568c867e4684a0ab0f912024d4f3c8644f6",
        "size_bytes": 7184,
    },
}
REGISTERED_CHECKERS = {
    "upper_counts": {
        "path": RESEARCH_DIR / "independent_r4_upper_counts_v1.py",
        "profile": "strict_instance",
        "sha256": "f3ab9fed7f6af39d9861f6c524065f3f7c76f476933f729c4d9d8b0aba41bc85",
        "size_bytes": 10901,
    },
    "marked_geometry": {
        "path": RESEARCH_DIR / "independent_r4_marked_geometry_v1.py",
        "profile": "strict_instance",
        "sha256": "7c4d930af4bba4b007131dd798d7f7720e67b6c12ba7bbf33d078a3a94a86eec",
        "size_bytes": 10960,
    },
    "w2d_audit": {
        "path": RESEARCH_DIR / "independent_r4_w2d_audit_v1.py",
        "profile": "w2d_authority",
        "sha256": "f9d568b691d7056595f703e1d3047051bec6cad7e634e70802f8a16238f48d73",
        "size_bytes": 8580,
    },
}


class RecomputationError(RuntimeError):
    """Fail-closed local recomputation error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path) -> dict[str, Any]:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise RecomputationError(f"cannot resolve provenance file {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or resolved != absolute or not stat.S_ISREG(mode):
        raise RecomputationError(f"not a canonical regular provenance file: {path}")
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise RecomputationError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise RecomputationError(f"non-finite JSON value in {label}: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputationError(f"cannot parse JSON {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecomputationError(f"JSON is not an object: {label}")
    return value


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        return _strict_json_bytes(path.read_bytes(), str(path))
    except OSError as exc:
        raise RecomputationError(f"cannot read JSON {path}: {exc}") from exc


def _load_archiver() -> ModuleType:
    if not ARCHIVER_PATH.is_file() or ARCHIVER_PATH.is_symlink():
        raise RecomputationError(f"bundle archiver is unavailable: {ARCHIVER_PATH}")
    name = "_r4_response_bundle_archiver_for_recomputation"
    spec = importlib.util.spec_from_file_location(name, ARCHIVER_PATH)
    if spec is None or spec.loader is None:
        raise RecomputationError("cannot load bundle archiver")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_ledger_builder() -> ModuleType:
    if not LEDGER_BUILDER_PATH.is_file() or LEDGER_BUILDER_PATH.is_symlink():
        raise RecomputationError(f"claim ledger builder is unavailable: {LEDGER_BUILDER_PATH}")
    name = "_r4_claim_ledger_builder_for_recomputation"
    spec = importlib.util.spec_from_file_location(name, LEDGER_BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RecomputationError("cannot load claim ledger builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _expected_authority_binding() -> dict[str, Any]:
    return {
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "package_id": EXPECTED_PACKAGE_ID,
        "ready_selection": EXPECTED_READY_SELECTION,
        "receipt_detached_byte_match": True,
        "receipt_semantic_replay_pass": True,
        "run_dir": str(EXPECTED_AUTHORITY_RUN.absolute()),
        "selected_receipt_identity": EXPECTED_SELECTED_RECEIPT,
        "selector_tool": EXPECTED_SELECTOR_TOOL,
    }


def _expected_input_bindings() -> list[dict[str, Any]]:
    names = {
        "response_text": (
            "inputs/response_text.verbatim.bin",
            "12_r4_response_gpt_pro_verbatim.md",
        ),
        "certificate_markdown": (
            "inputs/certificate_markdown.verbatim.bin",
            "13_r4_next_certificate_gpt_pro_verbatim.md",
        ),
        "certificate_python": (
            "inputs/certificate_python.verbatim.bin",
            "14_r4_next_certificate_python_gpt_pro_verbatim.md",
        ),
    }
    cleanroom = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718"
    result: list[dict[str, Any]] = []
    for input_id in ("response_text", "certificate_markdown", "certificate_python"):
        raw_relative, canonical_name = names[input_id]
        source = EXPECTED_SOURCE_IDENTITIES[input_id]
        identity = {"sha256": source["sha256"], "size_bytes": source["size_bytes"]}
        result.append(
            {
                "canonical_document": {
                    "path": str((cleanroom / canonical_name).absolute()),
                    **identity,
                },
                "expected_identity": identity,
                "input_id": input_id,
                "raw_canonical_byte_equal": True,
                "raw_document": {
                    "path": str((EXPECTED_RESPONSE_RUN / raw_relative).absolute()),
                    **identity,
                },
                "source_identity_at_archive": source,
            }
        )
    return result


def validate_archive(response_run: Path, authority_run: Path) -> dict[str, Any]:
    if authority_run.is_symlink() or authority_run.absolute() != authority_run.resolve(strict=True):
        raise RecomputationError("authority run is a symlink or alias")
    if response_run.is_symlink() or response_run.absolute() != response_run.resolve(strict=True):
        raise RecomputationError("response run is a symlink or alias")
    if authority_run.absolute() != EXPECTED_AUTHORITY_RUN.absolute():
        raise RecomputationError("authority run differs from the fixed R4 authority")
    if response_run.absolute() != EXPECTED_RESPONSE_RUN.absolute():
        raise RecomputationError("response run differs from the fixed R4 response run")
    if _record(response_run / "response-ingest.json") != EXPECTED_RESPONSE_INGEST:
        raise RecomputationError("response ingest differs from the fixed detached identity")
    if _record(authority_run / "ready/selected-receipt.json") != EXPECTED_READY_SELECTION:
        raise RecomputationError("READY selection differs from the fixed detached identity")
    if _record(Path(EXPECTED_SELECTOR_TOOL["path"])) != EXPECTED_SELECTOR_TOOL:
        raise RecomputationError("READY selector differs from the fixed detached identity")
    for input_id, expected in EXPECTED_SOURCE_IDENTITIES.items():
        if _record(Path(expected["path"])) != expected:
            raise RecomputationError(f"{input_id} source bytes differ from the at-archive identity")
    checker = getattr(_load_archiver(), "check_bundle", None)
    if not callable(checker):
        raise RecomputationError("bundle archiver lacks check_bundle")
    try:
        value = checker(response_run.resolve(strict=True), authority_run.resolve(strict=True))
    except Exception as exc:
        raise RecomputationError(f"response bundle replay failed: {exc}") from exc
    if not isinstance(value, Mapping):
        raise RecomputationError("bundle replay returned a malformed value")
    provenance = dict(value)
    if provenance.get("authority") != _expected_authority_binding():
        raise RecomputationError("response authority differs from the fixed R4 authority identity")
    if provenance.get("response_ingest") != EXPECTED_RESPONSE_INGEST:
        raise RecomputationError("normalized response ingest differs from the fixed detached identity")
    if provenance.get("inputs") != _expected_input_bindings():
        raise RecomputationError("response input bindings differ from the fixed three-input corpus")
    return provenance


def _file_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"path", "size_bytes", "sha256"}:
        raise RecomputationError(f"{label} is not an exact file record")
    path_value = value.get("path")
    if type(path_value) is not str or not Path(path_value).is_absolute():
        raise RecomputationError(f"{label}.path must be absolute")
    expected = {
        "path": path_value,
        "size_bytes": value.get("size_bytes"),
        "sha256": value.get("sha256"),
    }
    if _record(Path(path_value)) != expected:
        raise RecomputationError(f"{label} bytes are stale")
    return expected


def validate_claim_ledger(
    ledger_path: Path,
    provenance: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    builder = _load_ledger_builder()
    replay = getattr(builder, "replay_claim_ledger", None)
    if not callable(replay):
        raise RecomputationError("claim ledger builder lacks canonical replay")
    try:
        value = replay(EXPECTED_AUTHORITY_RUN, EXPECTED_RESPONSE_RUN, ledger_path)
    except Exception as exc:
        raise RecomputationError(f"canonical claim ledger replay failed: {exc}") from exc
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], Mapping)
        or not isinstance(value[1], Mapping)
    ):
        raise RecomputationError("canonical claim ledger replay returned a malformed value")
    ledger = dict(value[0])
    by_id = {str(key): dict(item) for key, item in value[1].items() if isinstance(item, Mapping)}
    if len(by_id) != len(value[1]):
        raise RecomputationError("canonical claim ledger replay returned malformed claims")
    if ledger.get("authority") != provenance.get("authority"):
        raise RecomputationError("canonical claim ledger authority differs")
    if ledger.get("input_bindings") != provenance.get("inputs"):
        raise RecomputationError("canonical claim ledger input multiset differs")
    if ledger.get("response_ingest") != provenance.get("response_ingest"):
        raise RecomputationError("canonical claim ledger ingest binding differs")
    if ledger.get("claim_count") != 17 or len(by_id) != 17:
        raise RecomputationError("canonical claim ledger is not the fixed 17-claim corpus")
    return ledger, by_id


def _prepare_output_dir(
    response_run: Path,
    output_dir: Path,
    *,
    checker_id: str,
) -> Path:
    """Create one fresh checker attempt directly under the fixed response run."""
    response = response_run.absolute()
    try:
        response_mode = response.lstat().st_mode
        response_resolved = response.resolve(strict=True)
    except OSError as exc:
        raise RecomputationError(f"cannot resolve response run for output: {exc}") from exc
    if stat.S_ISLNK(response_mode) or not stat.S_ISDIR(response_mode) or response_resolved != response:
        raise RecomputationError("response run output root is a symlink or alias")
    category = response / "recomputations"
    try:
        category_mode = category.lstat().st_mode
        category_resolved = category.resolve(strict=True)
    except OSError as exc:
        raise RecomputationError(f"cannot resolve recomputation output root: {exc}") from exc
    if stat.S_ISLNK(category_mode) or not stat.S_ISDIR(category_mode) or category_resolved != category:
        raise RecomputationError("recomputation output root is a symlink or alias")
    if any(part in {".", ".."} for part in output_dir.parts):
        raise RecomputationError("recomputation output contains a non-canonical path component")
    output = output_dir.absolute()
    slug = checker_id.replace("_", "-")
    if output.parent != category or re.fullmatch(rf"{re.escape(slug)}-a[0-9]{{3}}", output.name) is None:
        raise RecomputationError(f"recomputation output must be a fresh direct {slug}-aNNN child of {category}")
    if output.exists() or output.is_symlink():
        raise RecomputationError(f"no-overwrite output exists: {output}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    parent_fd = os.open(category, flags)
    try:
        before = os.fstat(parent_fd)
        current = os.stat(category, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise RecomputationError("recomputation output parent descriptor is not a directory")
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise RecomputationError("recomputation output parent changed during validation")
        try:
            os.mkdir(output.name, mode=0o755, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise RecomputationError(f"no-overwrite output exists: {output}") from exc
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    try:
        output_mode = output.lstat().st_mode
        output_resolved = output.resolve(strict=True)
    except OSError as exc:
        raise RecomputationError(f"cannot verify new recomputation output: {exc}") from exc
    if stat.S_ISLNK(output_mode) or not stat.S_ISDIR(output_mode) or output_resolved != output:
        raise RecomputationError("new recomputation output is a symlink or alias")
    return output


def _script_policy(script_path: Path, provenance: Mapping[str, Any]) -> dict[str, Any]:
    if script_path.is_symlink() or script_path.absolute() != script_path.resolve(strict=True):
        raise RecomputationError("local checker path is a symlink or alias")
    script_path = script_path.absolute()
    record = _record(script_path)
    input_hashes = {
        record_value["sha256"]
        for item in provenance["inputs"]
        for record_value in (item["raw_document"], item["canonical_document"])
    }
    if record["sha256"] in input_hashes:
        raise RecomputationError("local checker bytes equal untrusted response bytes")
    raw = script_path.read_bytes()
    line_count = len(raw.splitlines())
    if not 0 < line_count < 200:
        raise RecomputationError("local checker must contain 1..199 physical lines")
    try:
        tree = ast.parse(raw.decode("utf-8"), filename=str(script_path))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RecomputationError(f"local checker cannot be parsed: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".", 1)[0] for alias in node.names}
            if not roots <= ALLOWED_IMPORTS:
                raise RecomputationError(f"local checker imports forbidden modules: {sorted(roots)}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if node.level or root not in ALLOWED_IMPORTS:
                raise RecomputationError(f"local checker imports forbidden module: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
                raise RecomputationError(f"local checker calls forbidden function: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_ATTRIBUTES:
                raise RecomputationError(f"local checker calls forbidden attribute: {node.func.attr}")
        if isinstance(node, ast.Attribute) and (
            node.attr == "__dict__"
            or node.attr.startswith("__")
            or (node.attr == "modules" and isinstance(node.value, ast.Name) and node.value.id == "sys")
        ):
            raise RecomputationError(f"local checker uses forbidden dynamic attribute: {node.attr}")
    return {
        **record,
        "physical_line_count": line_count,
        "less_than_200_lines": True,
        "ast_policy": "PASS",
        "locally_rederived_from_claim_only": True,
    }


def validate_local_script(
    script_path: Path,
    provenance: Mapping[str, Any],
    checker_id: str,
    profile: str,
) -> dict[str, Any]:
    registration = REGISTERED_CHECKERS.get(checker_id)
    if not isinstance(registration, Mapping):
        raise RecomputationError(f"unregistered local checker: {checker_id}")
    if registration.get("profile") != profile:
        raise RecomputationError(f"checker/profile mismatch: {checker_id}/{profile}")
    registered_path = Path(str(registration["path"])).absolute()
    if script_path.is_symlink() or script_path.absolute() != registered_path:
        raise RecomputationError(f"local checker path is not the registered {checker_id} path")
    policy = _script_policy(script_path, provenance)
    expected = {
        "path": str(registered_path),
        "sha256": registration.get("sha256"),
        "size_bytes": registration.get("size_bytes"),
    }
    if {key: policy[key] for key in expected} != expected:
        raise RecomputationError(f"registered local checker bytes differ: {checker_id}")
    return policy


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


def build_sandbox_argv(script: Path, profile: str) -> list[str]:
    if profile not in PROFILES:
        raise RecomputationError(f"unknown checker profile: {profile}")
    python_root = FIXED_PYTHON.resolve(strict=True).parents[1]
    source = STRICT_INSTANCE if profile == "strict_instance" else W2D_ROOT
    target = "/input/problem_instance.json" if profile == "strict_instance" else "/input/w2d"
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
        "--dir",
        "/input",
        "--ro-bind",
        str(script),
        "/work/recompute.py",
        "--ro-bind",
        str(source),
        target,
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
        target,
    ]


def _profile_identity(profile: str) -> dict[str, Any]:
    if profile == "strict_instance":
        record = _record(STRICT_INSTANCE)
        if record["sha256"] != STRICT_INSTANCE_SHA256:
            raise RecomputationError("strict instance bytes are stale")
        return {"profile": profile, "strict_instance": record}
    if W2D_ROOT.is_symlink() or W2D_ROOT.absolute() != W2D_ROOT.resolve(strict=True):
        raise RecomputationError("W2d detached authority root is a symlink or alias")
    head_path = W2D_ROOT / ".git/HEAD"
    if not head_path.is_file() or head_path.is_symlink():
        raise RecomputationError("W2d detached authority root is unavailable")
    try:
        head = head_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise RecomputationError(f"cannot read W2d detached HEAD: {exc}") from exc
    if head != W2D_HEAD:
        raise RecomputationError("W2d detached HEAD differs")
    return {"profile": profile, "root": str(W2D_ROOT), "expected_head": W2D_HEAD}


def validate_recomputation_report(
    report_path: Path,
    ledger_path: Path,
    provenance: Mapping[str, Any],
    claims: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Read-only replay of every fact needed to trust one PASS report."""
    if report_path.is_symlink() or report_path.absolute() != report_path.resolve(strict=True):
        raise RecomputationError("recomputation report path is a symlink or alias")
    report_path = report_path.absolute()
    report = _strict_json(report_path)
    ledger_path_builder_record = _record(LEDGER_BUILDER_PATH)
    checker_id = report.get("checker_id")
    profile = report.get("profile")
    registration = REGISTERED_CHECKERS.get(checker_id)
    if not isinstance(registration, Mapping) or registration.get("profile") != profile:
        raise RecomputationError(f"report checker/profile is not registered: {checker_id}/{profile}")
    if (
        report.get("schema") != "r4_local_recomputation_bundle_report_v2"
        or report.get("status") != "PASS_EXACT_MATCH"
        or report.get("authority") != provenance.get("authority")
        or report.get("input_bindings") != provenance.get("inputs")
        or report.get("response_ingest") != provenance.get("response_ingest")
        or report.get("claim_ledger_status") != "COMPLETE"
        or report.get("claim_ledger_builder_tool") != ledger_path_builder_record
        or report.get("external_response_code_executed") is not False
        or report.get("formal_run_authorized") is not False
        or report.get("solver_run_authorized") is not False
        or report.get("output_parse_error") is not None
    ):
        raise RecomputationError(f"report state or provenance differs: {report_path}")
    if ledger_path.is_symlink() or ledger_path.absolute() != ledger_path.resolve(strict=True):
        raise RecomputationError("report ledger path is a symlink or alias")
    ledger_path = ledger_path.absolute()
    if report.get("claim_ledger") != _record(ledger_path):
        raise RecomputationError(f"report claim ledger differs: {report_path}")
    if report.get("runner_tool") != _record(Path(__file__)):
        raise RecomputationError(f"report runner bytes differ: {report_path}")
    local_script = report.get("local_script")
    if not isinstance(local_script, Mapping):
        raise RecomputationError(f"report local checker binding is malformed: {report_path}")
    snapshot_path = Path(str(local_script.get("path")))
    if snapshot_path.parent != report_path.parent or snapshot_path.name != "local-recomputation.py":
        raise RecomputationError(f"report local checker snapshot path differs: {report_path}")
    snapshot_policy = _script_policy(snapshot_path, provenance)
    if dict(local_script) != snapshot_policy:
        raise RecomputationError(f"report local checker policy replay differs: {report_path}")
    if snapshot_policy["sha256"] != registration.get("sha256") or snapshot_policy["size_bytes"] != registration.get(
        "size_bytes"
    ):
        raise RecomputationError(f"report local checker is not the registered checker: {report_path}")
    if report.get("evidence") != _profile_identity(str(profile)):
        raise RecomputationError(f"report evidence identity differs: {report_path}")
    stdout = _file_record(report.get("stdout"), "report.stdout")
    stderr = _file_record(report.get("stderr"), "report.stderr")
    if (
        Path(stdout["path"]).parent != report_path.parent
        or Path(stdout["path"]).name != "stdout.bin"
        or Path(stderr["path"]).parent != report_path.parent
        or Path(stderr["path"]).name != "stderr.bin"
    ):
        raise RecomputationError(f"report stdio paths differ: {report_path}")
    output = _strict_json_bytes(Path(stdout["path"]).read_bytes(), f"{checker_id} replay stdout")
    results = output.get("results")
    if (
        output.get("schema") != "r4_independent_checker_output_v1"
        or output.get("checker_id") != checker_id
        or not isinstance(results, Mapping)
    ):
        raise RecomputationError(f"report stdout schema differs: {report_path}")
    selected = sorted(
        (claim for claim in claims.values() if claim.get("checker_id") == checker_id),
        key=lambda item: str(item["claim_id"]),
    )
    if not selected:
        raise RecomputationError(f"report checker has no claims: {checker_id}")
    expected_claim_results: list[dict[str, Any]] = []
    for claim in selected:
        key = claim["result_key"]
        if key not in results:
            raise RecomputationError(f"report stdout lacks result {key}: {report_path}")
        actual = results[key]
        if type(actual) is not type(claim["expected_result"]) or actual != claim["expected_result"]:
            raise RecomputationError(f"report stdout result differs for {claim['claim_id']}")
        expected_claim_results.append(
            {
                "actual_result": actual,
                "claim_id": claim["claim_id"],
                "exact_match": True,
                "expected_result": claim["expected_result"],
                "result_key": key,
            }
        )
    if report.get("claim_results") != expected_claim_results:
        raise RecomputationError(f"report claim-result replay differs: {report_path}")
    expected_sandbox = {
        "argv": build_sandbox_argv(snapshot_path, str(profile)),
        "bwrap_unshare_net": True,
        "host_response_not_bound": True,
        "offline": True,
        "returncode": 0,
        "timed_out": False,
        "timeout_seconds": TIMEOUT_SECONDS,
    }
    if report.get("sandbox") != expected_sandbox:
        raise RecomputationError(f"report sandbox replay differs: {report_path}")
    return report


def run_recomputation(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    checker_id: str,
    profile: str,
    script_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    provenance = validate_archive(response_run, authority_run)
    authority_run = authority_run.absolute()
    response_run = response_run.absolute()
    ledger, claims = validate_claim_ledger(ledger_path, provenance)
    selected = [claim for claim in claims.values() if claim["checker_id"] == checker_id]
    if not selected:
        raise RecomputationError(f"checker_id is absent from complete ledger: {checker_id}")
    policy = validate_local_script(script_path, provenance, checker_id, profile)
    evidence = _profile_identity(profile)
    if not BWRAP.is_file() or BWRAP.is_symlink():
        raise RecomputationError("bwrap is unavailable; offline execution is NO_GO")
    if not FIXED_PYTHON.exists() or not FIXED_PYTHON.resolve(strict=True).is_file():
        raise RecomputationError("fixed Python interpreter is unavailable")
    output_dir = _prepare_output_dir(response_run, output_dir, checker_id=checker_id)
    script_snapshot = output_dir / "local-recomputation.py"
    _publish_bytes(script_snapshot, script_path.read_bytes())
    snapshot_policy = _script_policy(script_snapshot, provenance)
    if {k: v for k, v in snapshot_policy.items() if k != "path"} != {k: v for k, v in policy.items() if k != "path"}:
        raise RecomputationError("local checker bytes changed while being snapshotted")
    argv = build_sandbox_argv(script_snapshot, profile)
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
        timed_out = False
        returncode = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
    if len(stdout) > MAX_STDIO_BYTES or len(stderr) > MAX_STDIO_BYTES:
        raise RecomputationError("local checker output exceeds the fixed 1 MB cap")
    stdout_path = output_dir / "stdout.bin"
    stderr_path = output_dir / "stderr.bin"
    _publish_bytes(stdout_path, stdout)
    _publish_bytes(stderr_path, stderr)
    output_parse_error: str | None = None
    output: dict[str, Any] | None = None
    try:
        output = _strict_json_bytes(stdout, f"{checker_id} stdout")
    except RecomputationError as exc:
        output_parse_error = str(exc)
    results = output.get("results") if isinstance(output, Mapping) else None
    claim_results: list[dict[str, Any]] = []
    for claim in sorted(selected, key=lambda item: item["claim_id"]):
        actual = results.get(claim["result_key"]) if isinstance(results, Mapping) else None
        exact = (
            isinstance(results, Mapping)
            and claim["result_key"] in results
            and type(actual) is type(claim["expected_result"])
            and actual == claim["expected_result"]
        )
        claim_results.append(
            {
                "claim_id": claim["claim_id"],
                "result_key": claim["result_key"],
                "expected_result": claim["expected_result"],
                "actual_result": actual,
                "exact_match": exact,
            }
        )
    passed = (
        not timed_out
        and returncode == 0
        and output_parse_error is None
        and isinstance(output, Mapping)
        and output.get("schema") == "r4_independent_checker_output_v1"
        and output.get("checker_id") == checker_id
        and all(item["exact_match"] for item in claim_results)
    )
    report = {
        "schema": "r4_local_recomputation_bundle_report_v2",
        "created_at_utc": _utc_now(),
        "status": "PASS_EXACT_MATCH" if passed else "FAIL_CLOSED",
        "checker_id": checker_id,
        "profile": profile,
        "authority": provenance["authority"],
        "input_bindings": provenance["inputs"],
        "response_ingest": provenance["response_ingest"],
        "claim_ledger": _record(ledger_path),
        "claim_ledger_status": ledger["status"],
        "claim_ledger_builder_tool": ledger["claim_ledger_builder_tool"],
        "local_script": snapshot_policy,
        "runner_tool": _record(Path(__file__)),
        "evidence": evidence,
        "claim_results": claim_results,
        "sandbox": {
            "argv": argv,
            "offline": True,
            "bwrap_unshare_net": True,
            "host_response_not_bound": all(
                record["path"] not in argv
                for item in provenance["inputs"]
                for record in (item["raw_document"], item["canonical_document"])
            ),
            "timeout_seconds": TIMEOUT_SECONDS,
            "timed_out": timed_out,
            "returncode": returncode,
        },
        "stdout": _record(stdout_path),
        "stderr": _record(stderr_path),
        "output_parse_error": output_parse_error,
        "external_response_code_executed": False,
        "formal_run_authorized": False,
        "solver_run_authorized": False,
    }
    report_path = output_dir / "report.json"
    _publish_json(report_path, report)
    if passed:
        return validate_recomputation_report(report_path, ledger_path, provenance, claims)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-run", type=Path, required=True)
    parser.add_argument("--response-run", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--checker-id", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_recomputation(
            args.authority_run,
            args.response_run,
            args.claim_ledger,
            args.checker_id,
            args.profile,
            args.script,
            args.output_dir,
        )
    except (OSError, RecomputationError, ValueError) as exc:
        print(f"R4_RECOMPUTATION_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS_EXACT_MATCH" else 3


if __name__ == "__main__":
    raise SystemExit(main())

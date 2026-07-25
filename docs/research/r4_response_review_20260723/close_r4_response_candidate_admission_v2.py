#!/usr/bin/env python3
"""Close and read-only replay candidate-aware R4 admission without execution."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any, Iterator


RESEARCH_DIR = Path(__file__).resolve().parent
VERDICT_BUILDER_PATH = RESEARCH_DIR / "build_r4_adversarial_verdict_v2.py"
UPPER_CANDIDATE = "upper_bound_1188_22"
WITNESS_CANDIDATE = "witness_x67_c5_min_repair"
_VERDICT_REPLAY_KEYS = {
    "verdict",
    "provenance",
    "ledger",
    "claims",
    "reports",
    "report_bindings",
    "verdict_record",
}
_ADMISSION_REPLAY_KEYS = {"admission", "verdict_replay", "admission_record"}
ATTEMPT_RE = re.compile(r"a[0-9]{3}")


class AdmissionError(RuntimeError):
    """Fail-closed R4 candidate admission publication or replay error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any, label: str) -> datetime:
    if (
        type(value) is not str
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z",
            value,
        )
        is None
    ):
        raise AdmissionError(f"{label} is not a canonical UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AdmissionError(f"{label} is not a valid UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise AdmissionError(f"{label} is not UTC")
    return parsed


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
        raise AdmissionError(f"cannot resolve provenance file {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or resolved != absolute or not stat.S_ISREG(mode):
        raise AdmissionError(f"not a canonical regular provenance file: {path}")
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _canonical_existing_dir(path: Path, label: str) -> Path:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise AdmissionError(f"cannot resolve {label}: {exc}") from exc
    if stat.S_ISLNK(mode) or resolved != absolute or not stat.S_ISDIR(mode):
        raise AdmissionError(f"{label} is not a canonical non-symlink directory")
    return resolved


def _artifact_file(response_run: Path, category: str, path: Path, filename: str) -> Path:
    response = _canonical_existing_dir(response_run, "response run")
    parent = _canonical_existing_dir(response / category, f"response {category} directory")
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise AdmissionError(f"cannot resolve {category} artifact: {exc}") from exc
    artifact_dir = _canonical_existing_dir(resolved.parent, f"{category} artifact directory")
    if (
        stat.S_ISLNK(mode)
        or not stat.S_ISREG(mode)
        or resolved != absolute
        or resolved.name != filename
        or artifact_dir.parent != parent
        or ATTEMPT_RE.fullmatch(artifact_dir.name) is None
    ):
        raise AdmissionError(f"{category} artifact is outside its response-run direct child")
    return resolved


def _create_output_dir(response_run: Path, category: str, output_dir: Path) -> Path:
    if category != "admission":
        raise AdmissionError(f"unsupported response-run output category: {category}")
    response = _canonical_existing_dir(response_run, "response run")
    parent = _canonical_existing_dir(response / category, f"response {category} directory")
    if any(part in {".", ".."} for part in output_dir.parts):
        raise AdmissionError("output directory contains a non-canonical path component")
    target = output_dir.absolute()
    if target.parent != parent or ATTEMPT_RE.fullmatch(target.name) is None:
        raise AdmissionError(f"output directory must be a direct aNNN child of {parent}")
    if target.exists() or target.is_symlink():
        raise AdmissionError(f"no-overwrite target exists: {target}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    parent_fd = os.open(parent, flags)
    try:
        before = os.fstat(parent_fd)
        current = os.stat(parent, follow_symlinks=False)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise AdmissionError(f"response {category} directory changed during validation")
        try:
            os.mkdir(target.name, mode=0o750, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise AdmissionError(f"no-overwrite target exists: {target}") from exc
        created = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(created.st_mode):
            raise AdmissionError(f"created output is not a directory: {target}")
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    if target.is_symlink() or target.resolve(strict=True) != target:
        raise AdmissionError(f"created output is not canonical: {target}")
    return target


def _strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise AdmissionError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise AdmissionError(f"non-finite JSON value in {label}: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot parse JSON {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdmissionError(f"JSON is not an object: {label}")
    return value


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _strict_canonical_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AdmissionError(f"cannot read JSON {path}: {exc}") from exc
    value = _strict_json_bytes(raw, str(path))
    if raw != _canonical_json_bytes(value):
        raise AdmissionError(f"JSON bytes are not in the canonical serialization: {path}")
    return value, raw


@contextmanager
def _no_bytecode_writes() -> Iterator[None]:
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous


def _load_verdict_builder() -> ModuleType:
    if not VERDICT_BUILDER_PATH.is_file() or VERDICT_BUILDER_PATH.is_symlink():
        raise AdmissionError(f"adversarial verdict builder is unavailable: {VERDICT_BUILDER_PATH}")
    name = "_r4_adversarial_verdict_builder_for_candidate_admission"
    spec = importlib.util.spec_from_file_location(name, VERDICT_BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise AdmissionError("cannot load adversarial verdict builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _replay_verdict(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
    verdict_path: Path,
) -> dict[str, Any]:
    with _no_bytecode_writes():
        builder = _load_verdict_builder()
        replay = getattr(builder, "replay_verdict", None)
        if not callable(replay):
            raise AdmissionError("adversarial verdict builder lacks read-only replay_verdict")
        try:
            value = replay(
                authority_run,
                response_run,
                ledger_path,
                report_paths,
                verdict_path,
            )
        except Exception as exc:
            raise AdmissionError(f"complete adversarial verdict replay failed: {exc}") from exc
    if not isinstance(value, Mapping) or set(value) != _VERDICT_REPLAY_KEYS:
        raise AdmissionError("adversarial verdict replay returned a malformed context")
    context = dict(value)
    if (
        type(context["verdict"]) is not dict
        or type(context["provenance"]) is not dict
        or type(context["ledger"]) is not dict
        or type(context["claims"]) is not dict
        or type(context["reports"]) is not list
        or type(context["report_bindings"]) is not list
        or type(context["verdict_record"]) is not dict
        or len(context["claims"]) != 17
        or len(context["reports"]) != 3
        or len(context["report_bindings"]) != 3
    ):
        raise AdmissionError("adversarial verdict replay context types or cardinalities differ")
    return context


def _canonical_admission_payload(created_at_utc: str, replay: Mapping[str, Any]) -> dict[str, Any]:
    verdict = replay["verdict"]
    provenance = replay["provenance"]
    reports = replay["reports"]
    upper_verdict = verdict["candidates"][UPPER_CANDIDATE]
    witness_verdict = verdict["candidates"][WITNESS_CANDIDATE]
    all_reports_pass = all(report.get("status") == "PASS_EXACT_MATCH" for report in reports)
    upper_admitted = (
        all_reports_pass
        and verdict["quantitative_recomputation_status"] == "PASS"
        and verdict["adversarial_review_started_after_recomputation"] is True
        and upper_verdict["status"] == "PASS"
        and upper_verdict["geometric_necessity_complete"] is True
    )
    witness_admitted = (
        all_reports_pass
        and witness_verdict["classification"] == "EXECUTABLE_CANDIDATE"
        and witness_verdict["physical_partition_semantics_complete"] is True
        and witness_verdict["guarded_cut_soundness_complete"] is True
        and witness_verdict["escapes_common_c3_gate"] is True
    )
    incomplete = (
        not all_reports_pass
        or verdict["quantitative_recomputation_status"] != "PASS"
        or upper_verdict["status"] == "INCOMPLETE"
    )
    if incomplete:
        overall = "INCOMPLETE"
    elif upper_admitted and witness_admitted:
        overall = "GRANTED"
    elif upper_admitted or witness_admitted:
        overall = "PARTIAL"
    else:
        overall = "DENIED"
    return {
        "schema": "r4_response_candidate_admission_v2",
        "created_at_utc": created_at_utc,
        "cutoff_date": "2026-07-23",
        "status": overall,
        "admission_tool": _record(Path(__file__)),
        "verdict_replay_tool": dict(verdict["verdict_builder_tool"]),
        "claim_ledger_builder_tool": dict(verdict["claim_ledger_builder_tool"]),
        "recomputation_runner_tool": dict(verdict["recomputation_runner_tool"]),
        "authority": provenance["authority"],
        "input_bindings": provenance["inputs"],
        "response_ingest": provenance["response_ingest"],
        "claim_ledger": verdict["claim_ledger"],
        "recomputation_reports": replay["report_bindings"],
        "adversarial_verdict": replay["verdict_record"],
        "candidates": {
            UPPER_CANDIDATE: {
                "verdict": upper_verdict["status"],
                "research_followup_admitted": upper_admitted,
                "b1_followup_input_admitted": upper_admitted,
                "proposed_upper_ledger": [1188, 22],
            },
            WITNESS_CANDIDATE: {
                "classification": witness_verdict["classification"],
                "research_followup_admitted": witness_admitted,
                "track_w_followup_input_admitted": witness_admitted,
                "prerequisites": witness_verdict["prerequisites"],
            },
        },
        "current_project_ledger": {"U": [1190, 34], "L": "absent"},
        "upper_bound_changed": False,
        "formal_run_authorized": False,
        "encoder_execution_authorized": False,
        "solver_run_authorized": False,
        "search_run_authorized": False,
        "assembly_run_authorized": False,
        "router_run_authorized": False,
        "track_w_execution_authorized": False,
        "external_response_code_executed": False,
        "witness_established": False,
        "attainability_established": False,
        "optimality_established": False,
        "global_infeasibility_established": False,
        "production_certified": False,
        "claim_boundary": (
            "research follow-up admission only; project ledgers and execution authorizations are unchanged"
        ),
    }


def replay_admission(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
    verdict_path: Path,
    admission_path: Path,
) -> dict[str, Any]:
    """Read-only, byte-exact replay of the full admission chain and semantics."""
    verdict_replay = _replay_verdict(
        authority_run,
        response_run,
        ledger_path,
        report_paths,
        verdict_path,
    )
    admission_path = _artifact_file(response_run, "admission", admission_path, "admission.json")
    admission, raw = _strict_canonical_json(admission_path)
    admission_time = _parse_utc(admission.get("created_at_utc"), "candidate admission timestamp")
    verdict_time = _parse_utc(
        verdict_replay["verdict"].get("created_at_utc"),
        "adversarial verdict timestamp",
    )
    if admission_time <= verdict_time:
        raise AdmissionError("candidate admission timestamp is not after the adversarial verdict")
    expected = _canonical_admission_payload(admission["created_at_utc"], verdict_replay)
    if admission != expected or raw != _canonical_json_bytes(expected):
        raise AdmissionError("candidate admission differs from the complete canonical semantics")
    result = {
        "admission": admission,
        "verdict_replay": verdict_replay,
        "admission_record": _record(admission_path),
    }
    if set(result) != _ADMISSION_REPLAY_KEYS:
        raise AdmissionError("internal admission replay context differs")
    return result


def _publish_bytes(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise AdmissionError(f"no-overwrite target exists: {path}")
    pending = path.with_name(f".{path.name}.pending-{os.getpid():010d}")
    try:
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
    finally:
        pending.unlink(missing_ok=True)


def close_admission(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
    verdict_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    verdict_replay = _replay_verdict(
        authority_run,
        response_run,
        ledger_path,
        report_paths,
        verdict_path,
    )
    created_at = _utc_now()
    verdict_time = _parse_utc(
        verdict_replay["verdict"].get("created_at_utc"),
        "adversarial verdict timestamp",
    )
    if _parse_utc(created_at, "candidate admission timestamp") <= verdict_time:
        raise AdmissionError("candidate admission timestamp is not after the adversarial verdict")
    admission = _canonical_admission_payload(created_at, verdict_replay)
    output = _create_output_dir(response_run, "admission", output_dir)
    admission_path = output / "admission.json"
    _publish_bytes(admission_path, _canonical_json_bytes(admission))
    replayed = replay_admission(
        authority_run,
        response_run,
        ledger_path,
        report_paths,
        verdict_path,
        admission_path,
    )
    return replayed["admission"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-run", type=Path, required=True)
    parser.add_argument("--response-run", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--recomputation-report", type=Path, action="append", default=[])
    parser.add_argument("--adversarial-verdict", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        value = close_admission(
            args.authority_run,
            args.response_run,
            args.claim_ledger,
            args.recomputation_report,
            args.adversarial_verdict,
            args.output_dir,
        )
    except (AdmissionError, OSError, ValueError) as exc:
        print(f"R4_ADMISSION_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

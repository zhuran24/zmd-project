#!/usr/bin/env python3
"""Publish and read-only replay the R4 candidate-wise adversarial verdict."""

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
RUNNER_PATH = RESEARCH_DIR / "run_r4_local_recomputation_bundle_v2.py"
UPPER = "upper_bound_1188_22"
WITNESS = "witness_x67_c5_min_repair"
WITNESS_PREREQUISITES = [
    "Byte-pinned partition-mutation domain, protected invariants, Hamming objective, and deterministic tie-break.",
    "Per-cut provenance and complete pin, geometry, front, connectivity, and power dependencies for all 7,168 c3 cuts.",
    "Independent guard-implies-cut proof and replay for every conditional cut; missing or UNKNOWN dependencies disable the cut.",
    "A new hash-pinned exact 17-component manifest with independent count-closure replay that avoids c3 (12,4,3).",
    "Accepted results for every local row required by the new manifest; the current x67-c5 UNKNOWN is not feasibility.",
    "Proof that partition mutation preserves coordinate, body, front, connectivity, power, and assembly interfaces.",
    "Owner authorization explicitly superseding W2d STOP and establishing a new search resource contract.",
]
_REPLAY_KEYS = {
    "verdict",
    "provenance",
    "ledger",
    "claims",
    "reports",
    "report_bindings",
    "verdict_record",
}
ATTEMPT_RE = re.compile(r"a[0-9]{3}")


class VerdictError(RuntimeError):
    """Fail-closed adversarial-verdict publication or replay error."""


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
        raise VerdictError(f"{label} is not a canonical UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise VerdictError(f"{label} is not a valid UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise VerdictError(f"{label} is not UTC")
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
        raise VerdictError(f"cannot resolve provenance file {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or resolved != absolute or not stat.S_ISREG(mode):
        raise VerdictError(f"not a canonical regular provenance file: {path}")
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
        raise VerdictError(f"cannot resolve {label}: {exc}") from exc
    if stat.S_ISLNK(mode) or resolved != absolute or not stat.S_ISDIR(mode):
        raise VerdictError(f"{label} is not a canonical non-symlink directory")
    return resolved


def _artifact_file(
    response_run: Path,
    category: str,
    path: Path,
    filename: str,
    *,
    directory_pattern: re.Pattern[str] = ATTEMPT_RE,
) -> Path:
    response = _canonical_existing_dir(response_run, "response run")
    parent = _canonical_existing_dir(response / category, f"response {category} directory")
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise VerdictError(f"cannot resolve {category} artifact: {exc}") from exc
    artifact_dir = _canonical_existing_dir(resolved.parent, f"{category} artifact directory")
    if (
        stat.S_ISLNK(mode)
        or not stat.S_ISREG(mode)
        or resolved != absolute
        or resolved.name != filename
        or artifact_dir.parent != parent
        or directory_pattern.fullmatch(artifact_dir.name) is None
    ):
        raise VerdictError(f"{category} artifact is outside its response-run direct child")
    return resolved


def _create_output_dir(response_run: Path, category: str, output_dir: Path) -> Path:
    if category != "adversarial":
        raise VerdictError(f"unsupported response-run output category: {category}")
    response = _canonical_existing_dir(response_run, "response run")
    parent = _canonical_existing_dir(response / category, f"response {category} directory")
    if any(part in {".", ".."} for part in output_dir.parts):
        raise VerdictError("output directory contains a non-canonical path component")
    target = output_dir.absolute()
    if target.parent != parent or ATTEMPT_RE.fullmatch(target.name) is None:
        raise VerdictError(f"output directory must be a direct aNNN child of {parent}")
    if target.exists() or target.is_symlink():
        raise VerdictError(f"no-overwrite target exists: {target}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    parent_fd = os.open(parent, flags)
    try:
        before = os.fstat(parent_fd)
        current = os.stat(parent, follow_symlinks=False)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise VerdictError(f"response {category} directory changed during validation")
        try:
            os.mkdir(target.name, mode=0o750, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise VerdictError(f"no-overwrite target exists: {target}") from exc
        created = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(created.st_mode):
            raise VerdictError(f"created output is not a directory: {target}")
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    if target.is_symlink() or target.resolve(strict=True) != target:
        raise VerdictError(f"created output is not canonical: {target}")
    return target


def _strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise VerdictError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise VerdictError(f"non-finite JSON value in {label}: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerdictError(f"cannot parse JSON {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerdictError(f"JSON is not an object: {label}")
    return value


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _strict_canonical_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerdictError(f"cannot read JSON {path}: {exc}") from exc
    value = _strict_json_bytes(raw, str(path))
    if raw != _canonical_json_bytes(value):
        raise VerdictError(f"JSON bytes are not in the canonical serialization: {path}")
    return value, raw


@contextmanager
def _no_bytecode_writes() -> Iterator[None]:
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous


def _load_runner() -> ModuleType:
    if not RUNNER_PATH.is_file() or RUNNER_PATH.is_symlink():
        raise VerdictError(f"local recomputation runner is unavailable: {RUNNER_PATH}")
    name = "_r4_bundle_runner_for_adversarial_verdict"
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise VerdictError("cannot load local recomputation runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _replay_upstream(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
) -> dict[str, Any]:
    with _no_bytecode_writes():
        runner = _load_runner()
        try:
            provenance = runner.validate_archive(response_run, authority_run)
            ledger, claims = runner.validate_claim_ledger(ledger_path, provenance)
        except Exception as exc:
            raise VerdictError(f"archive or strict claim-ledger replay failed: {exc}") from exc
        if type(ledger) is not dict or type(claims) is not dict or len(claims) != 17:
            raise VerdictError("strict claim-ledger replay did not return the fixed 17-claim corpus")
        if set(claims) != {item.get("claim_id") for item in ledger.get("claims", [])}:
            raise VerdictError("strict claim-ledger replay returned inconsistent claim identities")
        builder_tool = ledger.get("claim_ledger_builder_tool")
        if not isinstance(builder_tool, Mapping) or set(builder_tool) != {"path", "size_bytes", "sha256"}:
            raise VerdictError("strict claim ledger lacks its exact builder identity")
        expected_ids = list(runner.REGISTERED_CHECKERS)
        if len(expected_ids) != 3 or len(report_paths) != len(expected_ids):
            raise VerdictError("exactly three registered recomputation reports are required")
        reports: list[dict[str, Any]] = []
        bindings: list[dict[str, Any]] = []
        covered: set[str] = set()
        for expected_id, report_path in zip(expected_ids, report_paths, strict=True):
            report_pattern = re.compile(rf"{re.escape(expected_id.replace('_', '-'))}-a[0-9]{{3}}")
            report_path = _artifact_file(
                response_run,
                "recomputations",
                report_path,
                "report.json",
                directory_pattern=report_pattern,
            )
            try:
                report = runner.validate_recomputation_report(
                    report_path,
                    ledger_path,
                    provenance,
                    claims,
                )
            except Exception as exc:
                raise VerdictError(f"report replay failed for {expected_id}: {exc}") from exc
            if type(report) is not dict or report.get("checker_id") != expected_id:
                raise VerdictError(f"registered report order differs at {expected_id}")
            for item in report.get("claim_results", []):
                claim_id = item.get("claim_id")
                if type(claim_id) is not str or claim_id in covered:
                    raise VerdictError(f"duplicate or malformed report claim coverage: {claim_id}")
                covered.add(claim_id)
            reports.append(report)
            bindings.append(_record(report_path))
    if covered != set(claims):
        raise VerdictError("recomputation reports do not cover the complete claim ledger")
    report_times = [_parse_utc(report.get("created_at_utc"), "recomputation report timestamp") for report in reports]
    return {
        "provenance": provenance,
        "ledger": ledger,
        "claims": claims,
        "reports": reports,
        "report_bindings": bindings,
        "latest_report_time": max(report_times),
    }


def _canonical_verdict_payload(
    created_at_utc: str,
    provenance: Mapping[str, Any],
    ledger: Mapping[str, Any],
    ledger_path: Path,
    report_bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "r4_adversarial_verdict_v2",
        "created_at_utc": created_at_utc,
        "cutoff_date": "2026-07-23",
        "status": "COMPLETE",
        "authority": provenance["authority"],
        "input_bindings": provenance["inputs"],
        "response_ingest": provenance["response_ingest"],
        "claim_ledger": _record(ledger_path),
        "claim_ledger_builder_tool": dict(ledger["claim_ledger_builder_tool"]),
        "recomputation_reports": list(report_bindings),
        "recomputation_runner_tool": _record(RUNNER_PATH),
        "verdict_builder_tool": _record(Path(__file__)),
        "quantitative_recomputation_status": "PASS",
        "adversarial_review_started_after_recomputation": True,
        "candidates": {
            UPPER: {
                "status": "PASS",
                "research_disposition": "ADMITTED_FOR_B1_ENCODER_DESIGN",
                "proposed_upper_ledger": [1188, 22],
                "geometric_necessity_complete": True,
                "marked_terminal_accounting_complete": True,
                "local_access_cell_complete": True,
                "marked_membrane_complete": True,
                "boundary_packing_complete": True,
                "full_span_exclusion_complete": True,
                "dimension_scan_complete": True,
                "lex_better_survivors": [],
                "first_unclosed_obligation": (
                    "proof-bearing B1 encoder, translation admission, and formal lex-better-band UNSAT"
                ),
            },
            WITNESS: {
                "classification": "NEEDS_PREREQUISITES",
                "research_disposition": "NOT_ADMITTED_FOR_TRACK_W_EXECUTION",
                "physical_partition_semantics_complete": False,
                "guarded_cut_soundness_complete": False,
                "escapes_common_c3_gate": False,
                "first_unclosed_obligation": (
                    "a hash-pinned exact 17-component count-closure manifest that does not require c3 (12,4,3)"
                ),
                "prerequisites": WITNESS_PREREQUISITES,
            },
        },
        "current_project_ledger": {"U": [1190, 34], "L": "absent"},
        "upper_bound_changed": False,
        "external_response_code_executed": False,
        "formal_run_authorized": False,
        "solver_run_authorized": False,
        "search_run_authorized": False,
        "track_w_execution_authorized": False,
        "witness_established": False,
        "attainability_established": False,
        "optimality_established": False,
        "global_infeasibility_established": False,
        "production_certified": False,
        "claim_boundary": (
            "mathematical research admission only; project ledgers and all execution authorizations remain unchanged"
        ),
    }


def replay_verdict(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
    verdict_path: Path,
) -> dict[str, Any]:
    """Read-only, byte-exact replay of the complete adversarial-verdict semantics."""
    upstream = _replay_upstream(authority_run, response_run, ledger_path, report_paths)
    verdict_path = _artifact_file(response_run, "adversarial", verdict_path, "verdict.json")
    verdict, raw = _strict_canonical_json(verdict_path)
    verdict_time = _parse_utc(verdict.get("created_at_utc"), "adversarial verdict timestamp")
    if verdict_time <= upstream["latest_report_time"]:
        raise VerdictError("adversarial verdict timestamp is not after all recomputation reports")
    expected = _canonical_verdict_payload(
        verdict["created_at_utc"],
        upstream["provenance"],
        upstream["ledger"],
        ledger_path,
        upstream["report_bindings"],
    )
    if verdict != expected or raw != _canonical_json_bytes(expected):
        raise VerdictError("adversarial verdict differs from the complete canonical semantics")
    result = {
        "verdict": verdict,
        "provenance": upstream["provenance"],
        "ledger": upstream["ledger"],
        "claims": upstream["claims"],
        "reports": upstream["reports"],
        "report_bindings": upstream["report_bindings"],
        "verdict_record": _record(verdict_path),
    }
    if set(result) != _REPLAY_KEYS:
        raise VerdictError("internal verdict replay context differs")
    return result


def _publish_bytes(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise VerdictError(f"no-overwrite target exists: {path}")
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


def build_verdict(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
    report_paths: Sequence[Path],
    output_dir: Path,
) -> dict[str, Any]:
    upstream = _replay_upstream(authority_run, response_run, ledger_path, report_paths)
    created_at = _utc_now()
    if _parse_utc(created_at, "adversarial verdict timestamp") <= upstream["latest_report_time"]:
        raise VerdictError("adversarial verdict timestamp is not after all recomputation reports")
    verdict = _canonical_verdict_payload(
        created_at,
        upstream["provenance"],
        upstream["ledger"],
        ledger_path,
        upstream["report_bindings"],
    )
    output = _create_output_dir(response_run, "adversarial", output_dir)
    verdict_path = output / "verdict.json"
    _publish_bytes(verdict_path, _canonical_json_bytes(verdict))
    replayed = replay_verdict(authority_run, response_run, ledger_path, report_paths, verdict_path)
    return replayed["verdict"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-run", type=Path, required=True)
    parser.add_argument("--response-run", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--recomputation-report", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        verdict = build_verdict(
            args.authority_run,
            args.response_run,
            args.claim_ledger,
            args.recomputation_report,
            args.output_dir,
        )
    except (OSError, VerdictError, ValueError) as exc:
        print(f"R4_VERDICT_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

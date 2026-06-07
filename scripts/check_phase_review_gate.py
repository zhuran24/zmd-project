#!/usr/bin/env python3
"""Check machine-readable phase review gates.

The gate can be honestly blocked. This script is not a phase-transition button;
it validates that blocked/closed state, review counters, evidence paths, and
front-door documentation agree.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_DIR = PROJECT_ROOT / "data" / "review_gates"

OPEN_STATUSES = {"blocked_pending_clean_reviews", "open", "blocked"}
CLOSED_STATUS = "closed"
CLEAN_FULL_REVIEW_TYPE = "independent_full_external"


class GateError(RuntimeError):
    pass


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GateError(f"{label} must be a list")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise GateError(f"{label} must be a boolean")
    return value


def require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GateError(f"{label} must be an integer")
    return value


def require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{label} must be a non-empty string")
    return value


def load_gate(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot read {rel(path)}: {exc}") from exc
    return require_mapping(payload, rel(path))



def _is_not_implemented_raise(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Raise) or stmt.exc is None:
        return False
    exc = stmt.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"


def _function_body_is_fail_closed_not_implemented(source_path: Path, symbol: str) -> bool:
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - gate should report parse/read failures.
        raise GateError(f"cannot inspect source boundary {rel(source_path)}: {exc}") from exc

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != symbol:
            continue
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        if body and isinstance(body[0], ast.Delete):
            body = body[1:]
        return len(body) == 1 and _is_not_implemented_raise(body[0])
    raise GateError(f"source boundary symbol not found: {rel(source_path)}::{symbol}")



def _review_history_clean_counter(
    records: list[dict[str, Any]],
    *,
    latest_reset_index: int,
) -> int:
    """Derive the consecutive clean full-review counter from review_history.

    The JSON counter is intentionally redundant: it is a human-readable summary,
    not authority.  A gate is ready only when the review history after the latest
    reset contains the required consecutive independent full external reviews.
    """
    count = 0
    for record in records[latest_reset_index + 1:]:
        if record["review_type"] != CLEAN_FULL_REVIEW_TYPE:
            continue
        if record["clean"] and record["major"] == 0 and not record["resets_counter"]:
            count += 1
        else:
            count = 0
    return count

def _check_source_boundaries(boundaries: list[Any], *, status: str) -> list[str]:
    errors: list[str] = []
    for index, raw_boundary in enumerate(boundaries):
        boundary = require_mapping(raw_boundary, f"source_boundaries[{index}]")
        rel_path = require_str(boundary.get("path"), f"source_boundaries[{index}].path")
        symbol = require_str(boundary.get("symbol"), f"source_boundaries[{index}].symbol")
        required_state = require_str(
            boundary.get("required_state_until_closed"),
            f"source_boundaries[{index}].required_state_until_closed",
        )
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"source boundary target missing: {rel_path}")
            continue
        if status != CLOSED_STATUS and required_state == "fail_closed_not_implemented":
            if not _function_body_is_fail_closed_not_implemented(full_path, symbol):
                errors.append(
                    f"source boundary no longer fail-closed before gate close: {rel_path}::{symbol}"
                )
        elif required_state != "fail_closed_not_implemented":
            errors.append(f"unsupported source boundary required_state_until_closed: {required_state}")
    return errors


def _check_evidence_paths(paths: list[Any], label: str) -> list[str]:
    errors: list[str] = []
    for raw_path in paths:
        rel_path = require_str(raw_path, f"{label} evidence path")
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"missing evidence path: {rel_path}")
    return errors


def _check_doc_markers(markers: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, raw_marker in enumerate(markers):
        marker = require_mapping(raw_marker, f"required_doc_markers[{index}]")
        rel_path = require_str(marker.get("path"), f"required_doc_markers[{index}].path")
        needle = require_str(marker.get("contains"), f"required_doc_markers[{index}].contains")
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"required doc marker target missing: {rel_path}")
            continue
        text = full_path.read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"required marker not found in {rel_path}: {needle!r}")
    return errors


def check_gate(path: Path) -> tuple[str, list[str]]:
    gate = load_gate(path)
    errors: list[str] = []

    if gate.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    gate_id = require_str(gate.get("gate_id"), "gate_id")
    status = require_str(gate.get("status"), "status")
    if status not in OPEN_STATUSES | {CLOSED_STATUS}:
        errors.append(f"unsupported status: {status}")

    close_policy = require_mapping(gate.get("close_policy"), "close_policy")
    counters = require_mapping(gate.get("counters"), "counters")
    next_phase_entry = require_mapping(gate.get("next_phase_entry"), "next_phase_entry")
    last_reset = require_mapping(gate.get("last_reset"), "last_reset")
    history = require_list(gate.get("review_history"), "review_history")

    required = require_int(
        close_policy.get("required_consecutive_clean_full_reviews"),
        "close_policy.required_consecutive_clean_full_reviews",
    )
    counted_required = require_int(
        counters.get("required_consecutive_clean_full_reviews"),
        "counters.required_consecutive_clean_full_reviews",
    )
    clean_count = require_int(
        counters.get("consecutive_clean_full_reviews_after_reset"),
        "counters.consecutive_clean_full_reviews_after_reset",
    )
    remaining = require_int(
        counters.get("remaining_clean_full_reviews"),
        "counters.remaining_clean_full_reviews",
    )
    if required <= 0:
        errors.append("required clean-review count must be positive")
    if counted_required != required:
        errors.append("counter required count disagrees with close_policy")
    if clean_count < 0:
        errors.append("clean review count cannot be negative")
    expected_remaining = max(required - clean_count, 0)
    if remaining != expected_remaining:
        errors.append(f"remaining_clean_full_reviews {remaining} != expected {expected_remaining}")

    next_allowed = require_bool(next_phase_entry.get("allowed"), "next_phase_entry.allowed")
    if status == CLOSED_STATUS:
        if clean_count < required:
            errors.append("closed gate must have enough consecutive clean full reviews")
        if not next_allowed:
            errors.append("closed gate should allow next phase entry")
    else:
        if clean_count >= required:
            errors.append("open/blocked gate has enough clean reviews; status should be closed")
        if next_allowed:
            errors.append("open/blocked gate must not allow next phase entry")

    reset_package = require_str(last_reset.get("review_package"), "last_reset.review_package")
    if not require_bool(last_reset.get("resets_counter"), "last_reset.resets_counter"):
        errors.append("last_reset.resets_counter must be true")
    errors.extend(_check_evidence_paths(require_list(last_reset.get("evidence_paths"), "last_reset.evidence_paths"), "last_reset"))

    reset_entries = []
    all_reset_entries: list[tuple[int, str]] = []
    history_records: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(history):
        entry = require_mapping(raw_entry, f"review_history[{index}]")
        package = require_str(entry.get("package"), f"review_history[{index}].package")
        review_type = require_str(entry.get("review_type"), f"review_history[{index}].review_type")
        clean = require_bool(entry.get("clean"), f"review_history[{index}].clean")
        major = require_int(
            entry.get("major_or_soundness_findings"),
            f"review_history[{index}].major_or_soundness_findings",
        )
        resets_counter = require_bool(
            entry.get("resets_counter", False),
            f"review_history[{index}].resets_counter",
        )
        history_records.append(
            {
                "index": index,
                "package": package,
                "review_type": review_type,
                "clean": clean,
                "major": major,
                "resets_counter": resets_counter,
            }
        )
        if clean and major != 0:
            errors.append(f"review_history[{index}] is clean but has {major} major/soundness findings")
        if clean and resets_counter:
            errors.append(f"review_history[{index}] is clean but resets the clean-review counter")
        if not clean and major == 0 and resets_counter:
            errors.append(f"review_history[{index}] resets counter but has zero major/soundness findings")
        if not clean and major > 0 and not resets_counter:
            errors.append(f"review_history[{index}] has major/soundness findings but does not reset counter")
        if resets_counter:
            all_reset_entries.append((index, package))
            if package == reset_package:
                reset_entries.append(index)
        errors.extend(_check_evidence_paths(require_list(entry.get("evidence_paths", []), f"review_history[{index}].evidence_paths"), f"review_history[{index}]"))
    latest_reset_index: int | None = None
    if not reset_entries:
        errors.append(f"review_history lacks reset entry for {reset_package}")
    if all_reset_entries:
        latest_reset_index, latest_package = all_reset_entries[-1]
        if latest_package != reset_package:
            errors.append(
                "last_reset.review_package must match the latest resetting "
                f"review_history entry: review_history[{latest_reset_index}]={latest_package!r}, "
                f"last_reset={reset_package!r}"
            )
        else:
            derived_clean_count = _review_history_clean_counter(
                history_records,
                latest_reset_index=latest_reset_index,
            )
            if clean_count != derived_clean_count:
                errors.append(
                    "counters.consecutive_clean_full_reviews_after_reset "
                    f"{clean_count} != review_history-derived {derived_clean_count} "
                    f"since latest reset {reset_package!r}"
                )

    errors.extend(_check_doc_markers(require_list(gate.get("required_doc_markers"), "required_doc_markers")))
    errors.extend(_check_source_boundaries(require_list(gate.get("source_boundaries", []), "source_boundaries"), status=status))
    summary = f"{gate_id}: status={status}, clean={clean_count}/{required}, next_allowed={next_allowed}"
    return summary, errors


def iter_gate_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise GateError(f"gate path not found: {path}")
    return sorted(path.glob("*.json"))


def _gate_by_id(paths: list[Path]) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    for path in paths:
        gate = load_gate(path)
        gate_id = require_str(gate.get("gate_id"), f"{rel(path)}.gate_id")
        gates[gate_id] = gate
    return gates


def _check_required_ready(paths: list[Path], required_gate_ids: list[str]) -> list[str]:
    if not required_gate_ids:
        return []
    errors: list[str] = []
    gates = _gate_by_id(paths)
    for gate_id in required_gate_ids:
        gate = gates.get(gate_id)
        if gate is None:
            errors.append(f"required ready gate not found: {gate_id}")
            continue
        counters = require_mapping(gate.get("counters"), f"{gate_id}.counters")
        required = require_int(
            counters.get("required_consecutive_clean_full_reviews"),
            f"{gate_id}.counters.required_consecutive_clean_full_reviews",
        )
        clean_count = require_int(
            counters.get("consecutive_clean_full_reviews_after_reset"),
            f"{gate_id}.counters.consecutive_clean_full_reviews_after_reset",
        )
        next_phase_entry = require_mapping(gate.get("next_phase_entry"), f"{gate_id}.next_phase_entry")
        next_allowed = require_bool(next_phase_entry.get("allowed"), f"{gate_id}.next_phase_entry.allowed")
        status = require_str(gate.get("status"), f"{gate_id}.status")
        if status != CLOSED_STATUS or clean_count < required or not next_allowed:
            errors.append(
                f"{gate_id} is not ready: status={status}, "
                f"clean={clean_count}/{required}, next_allowed={next_allowed}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check phase review gate manifests.")
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE_DIR, help="Gate JSON file or directory")
    parser.add_argument(
        "--require-ready",
        action="append",
        default=[],
        metavar="GATE_ID",
        help="Fail unless the named gate is closed, has enough clean reviews, and allows next-phase entry.",
    )
    args = parser.parse_args()

    try:
        paths = iter_gate_paths(args.gate)
    except GateError as exc:
        print(f"phase review gate check failed: {exc}", file=sys.stderr)
        return 2
    if not paths:
        print(f"phase review gate check failed: no gate manifests in {rel(args.gate)}", file=sys.stderr)
        return 2

    summaries: list[str] = []
    all_errors: list[str] = []
    for path in paths:
        try:
            summary, errors = check_gate(path)
        except GateError as exc:
            summary = rel(path)
            errors = [str(exc)]
        summaries.append(summary)
        for error in errors:
            all_errors.append(f"{rel(path)}: {error}")

    try:
        all_errors.extend(_check_required_ready(paths, args.require_ready))
    except GateError as exc:
        all_errors.append(str(exc))

    if all_errors:
        print(f"phase review gate check failed: {len(all_errors)} issue(s)")
        for error in all_errors[:40]:
            print(f"  - {error}")
        if len(all_errors) > 40:
            print(f"  ... {len(all_errors) - 40} more")
        return 1

    print("phase review gate check passed: " + "; ".join(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

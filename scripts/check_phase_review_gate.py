#!/usr/bin/env python3
"""Check the manual Phase 1.2 review gate.

The Phase 1.2 "three clean reviews" rule is an owner-governance standard, not a
repo-derived proof protocol.  Earlier V37-V50 hardening tried to infer clean
credit from review reports, receipts, package metadata, and Git authority; that
created a large parser/state-machine attack surface.  This checker is therefore
intentionally small: it validates that the repository remains fail-closed unless
an explicit owner manual decision opens P1.3B.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_DIR = PROJECT_ROOT / "data" / "review_gates"
LIFECYCLE_PATH = PROJECT_ROOT / "src" / "cuts" / "lifecycle.py"

BLOCKED_STATUSES = {"blocked_manual_review_count", "blocked", "open"}
CLOSED_STATUS = "closed_manual_owner_decision"
COUNTING_AUTHORITY = "owner_manual_count_outside_repo"
RECEIPT_ROLE = "informational_record_only"


class GateError(RuntimeError):
    pass


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise GateError(f"invalid JSON constant {value!r}; phase-gate JSON must be strict JSON")


def load_gate(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except GateError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot read {rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{rel(path)} must contain a JSON object")
    return value


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


def _check_allowed_top_level_keys(gate: dict[str, Any]) -> list[str]:
    allowed = {
        "schema_version",
        "gate_id",
        "phase",
        "status",
        "updated_at",
        "summary",
        "current_review_anchor",
        "manual_review_standard",
        "owner_manual_state",
        "owner_manual_decision",
        "next_phase_entry",
        "informational_history",
        "required_doc_markers",
        "source_boundaries",
        "receipt_policy",
    }
    old_auto_authority_keys = {
        "counters",
        "last_reset",
        "review_history",
        "current_review_package",
        "clean_review_receipt_protocol",
        "counter_domains",
    }
    errors: list[str] = []
    for key in sorted(set(gate) - allowed):
        errors.append(f"unsupported top-level key for manual phase gate: {key}")
    for key in sorted(old_auto_authority_keys & set(gate)):
        errors.append(
            f"manual phase gate must not contain repo-derived clean-count authority key: {key}"
        )
    return errors


def _check_manual_review_standard(standard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = require_int(
        standard.get("required_consecutive_clean_full_reviews"),
        "manual_review_standard.required_consecutive_clean_full_reviews",
    )
    if required != 3:
        errors.append("manual_review_standard.required_consecutive_clean_full_reviews must be 3")
    authority = require_str(standard.get("counting_authority"), "manual_review_standard.counting_authority")
    if authority != COUNTING_AUTHORITY:
        errors.append(
            "manual_review_standard.counting_authority must be "
            f"{COUNTING_AUTHORITY!r}, not {authority!r}"
        )
    derives = require_bool(
        standard.get("repo_derives_clean_count_from_receipts"),
        "manual_review_standard.repo_derives_clean_count_from_receipts",
    )
    if derives:
        errors.append("repo must not derive clean-review count from receipts")
    receipt_role = require_str(standard.get("receipt_role"), "manual_review_standard.receipt_role")
    if receipt_role != RECEIPT_ROLE:
        errors.append(f"manual_review_standard.receipt_role must be {RECEIPT_ROLE!r}")
    for index, raw_class in enumerate(
        require_list(
            standard.get("finding_classes_that_break_manual_clean_review"),
            "manual_review_standard.finding_classes_that_break_manual_clean_review",
        )
    ):
        require_str(raw_class, f"manual_review_standard.finding_classes_that_break_manual_clean_review[{index}]")
    return errors


def _check_owner_manual_state(state: dict[str, Any], *, current_anchor: str) -> list[str]:
    errors: list[str] = []
    if require_str(state.get("counting_authority"), "owner_manual_state.counting_authority") != COUNTING_AUTHORITY:
        errors.append("owner_manual_state.counting_authority must match manual review standard")
    if require_str(state.get("current_review_anchor"), "owner_manual_state.current_review_anchor") != current_anchor:
        errors.append("owner_manual_state.current_review_anchor must match current_review_anchor")
    if require_bool(
        state.get("repo_derives_clean_count_from_receipts"),
        "owner_manual_state.repo_derives_clean_count_from_receipts",
    ):
        errors.append("owner_manual_state must keep repo_derives_clean_count_from_receipts=false")
    if require_bool(state.get("p1_3b_entry_allowed"), "owner_manual_state.p1_3b_entry_allowed"):
        # The state may be allowed only when the explicit decision object below is present.
        pass
    owner_count_status = require_str(state.get("owner_clean_count_status"), "owner_manual_state.owner_clean_count_status")
    if owner_count_status != "maintained_outside_repo":
        errors.append("owner_manual_state.owner_clean_count_status must be maintained_outside_repo")
    return errors


def _check_owner_manual_decision(raw_decision: Any, *, next_allowed: bool) -> list[str]:
    errors: list[str] = []
    if not next_allowed:
        if raw_decision is None:
            return errors
        decision = require_mapping(raw_decision, "owner_manual_decision")
        if decision.get("p1_3b_entry_allowed") is True:
            errors.append("owner_manual_decision cannot allow P1.3B while next_phase_entry.allowed=false")
        return errors

    decision = require_mapping(raw_decision, "owner_manual_decision")
    if not require_bool(decision.get("p1_3b_entry_allowed"), "owner_manual_decision.p1_3b_entry_allowed"):
        errors.append("owner_manual_decision.p1_3b_entry_allowed must be true when next phase is allowed")
    if require_str(decision.get("counting_authority"), "owner_manual_decision.counting_authority") != COUNTING_AUTHORITY:
        errors.append("owner_manual_decision.counting_authority must be owner_manual_count_outside_repo")
    for key in ("decision_id", "decided_by", "decided_at", "decision_note"):
        require_str(decision.get(key), f"owner_manual_decision.{key}")
    if require_bool(
        decision.get("acknowledges_repo_does_not_prove_clean_count"),
        "owner_manual_decision.acknowledges_repo_does_not_prove_clean_count",
    ) is not True:
        errors.append("owner_manual_decision must acknowledge repo does not prove clean count")
    if require_bool(
        decision.get("acknowledges_owner_verified_three_clean_reviews"),
        "owner_manual_decision.acknowledges_owner_verified_three_clean_reviews",
    ) is not True:
        errors.append("owner_manual_decision must acknowledge owner-verified three clean reviews")
    return errors


def _step_8_apply_to_master_is_fail_closed() -> bool:
    try:
        tree = ast.parse(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot parse {rel(LIFECYCLE_PATH)}: {exc}") from exc
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "step_8_apply_to_master":
            for child in ast.walk(node):
                if isinstance(child, ast.Raise):
                    raised = child.exc
                    if (
                        isinstance(raised, ast.Call)
                        and isinstance(raised.func, ast.Name)
                        and raised.func.id == "NotImplementedError"
                    ):
                        return True
                    if isinstance(raised, ast.Name) and raised.id == "NotImplementedError":
                        return True
            return False
    raise GateError("function not found in src/cuts/lifecycle.py: step_8_apply_to_master")


def _check_step_8_boundary(*, next_allowed: bool) -> list[str]:
    if next_allowed:
        return []
    if _step_8_apply_to_master_is_fail_closed():
        return []
    return ["P1.3B is not manually allowed, so step_8_apply_to_master must remain fail-closed"]


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


def _check_informational_history(history: list[Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw_entry in enumerate(history):
        entry = require_mapping(raw_entry, f"informational_history[{index}]")
        package = require_str(entry.get("package"), f"informational_history[{index}].package")
        if package in seen:
            errors.append(f"duplicate informational history package: {package}")
        seen.add(package)
        require_str(entry.get("classification"), f"informational_history[{index}].classification")
        for path_index, raw_path in enumerate(
            require_list(entry.get("evidence_paths", []), f"informational_history[{index}].evidence_paths")
        ):
            rel_path = require_str(raw_path, f"informational_history[{index}].evidence_paths[{path_index}]")
            if not (PROJECT_ROOT / rel_path).exists():
                errors.append(f"informational history evidence path missing: {rel_path}")
    return errors


def check_gate(path: Path) -> tuple[str, list[str]]:
    gate = load_gate(path)
    errors: list[str] = []
    errors.extend(_check_allowed_top_level_keys(gate))

    try:
        schema_version = require_int(gate.get("schema_version"), "schema_version")
    except GateError as exc:
        errors.append(str(exc))
        schema_version = -1
    if schema_version != 2:
        errors.append("manual phase gate schema_version must be 2")

    gate_id = require_str(gate.get("gate_id"), "gate_id")
    status = require_str(gate.get("status"), "status")
    if status not in BLOCKED_STATUSES | {CLOSED_STATUS}:
        errors.append(f"unsupported manual phase gate status: {status}")
    current_anchor = require_str(gate.get("current_review_anchor"), "current_review_anchor")

    standard = require_mapping(gate.get("manual_review_standard"), "manual_review_standard")
    errors.extend(_check_manual_review_standard(standard))

    owner_state = require_mapping(gate.get("owner_manual_state"), "owner_manual_state")
    errors.extend(_check_owner_manual_state(owner_state, current_anchor=current_anchor))
    owner_state_allowed = require_bool(owner_state.get("p1_3b_entry_allowed"), "owner_manual_state.p1_3b_entry_allowed")

    next_phase_entry = require_mapping(gate.get("next_phase_entry"), "next_phase_entry")
    next_allowed = require_bool(next_phase_entry.get("allowed"), "next_phase_entry.allowed")
    if owner_state_allowed != next_allowed:
        errors.append("owner_manual_state.p1_3b_entry_allowed must match next_phase_entry.allowed")
    if status in BLOCKED_STATUSES and next_allowed:
        errors.append("blocked/open manual gate must not allow P1.3B")
    if status == CLOSED_STATUS and not next_allowed:
        errors.append("closed manual gate should allow P1.3B")
    if require_str(next_phase_entry.get("authority"), "next_phase_entry.authority") != "owner_manual_decision_only":
        errors.append("next_phase_entry.authority must be owner_manual_decision_only")

    try:
        errors.extend(_check_owner_manual_decision(gate.get("owner_manual_decision"), next_allowed=next_allowed))
    except GateError as exc:
        errors.append(str(exc))
    errors.extend(_check_step_8_boundary(next_allowed=next_allowed))
    try:
        errors.extend(_check_informational_history(require_list(gate.get("informational_history", []), "informational_history")))
        errors.extend(_check_doc_markers(require_list(gate.get("required_doc_markers", []), "required_doc_markers")))
    except GateError as exc:
        errors.append(str(exc))

    try:
        receipt_policy = require_mapping(gate.get("receipt_policy"), "receipt_policy")
        if require_str(receipt_policy.get("role"), "receipt_policy.role") != RECEIPT_ROLE:
            errors.append("receipt_policy.role must be informational_record_only")
        if require_bool(receipt_policy.get("can_open_p1_3b"), "receipt_policy.can_open_p1_3b"):
            errors.append("receipt_policy.can_open_p1_3b must be false")
    except GateError as exc:
        errors.append(str(exc))

    summary = (
        f"{gate_id}: status={status}, anchor={current_anchor}, "
        f"next_allowed={next_allowed}, counting_authority={COUNTING_AUTHORITY}"
    )
    return summary, errors


def _gate_paths() -> list[Path]:
    return sorted(DEFAULT_GATE_DIR.glob("phase_*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-ready",
        nargs="*",
        metavar="GATE_ID",
        help="Fail unless the named gate(s) are manually opened by owner decision.",
    )
    args = parser.parse_args()

    required_ready = set(args.require_ready or [])
    any_errors = False
    ready_by_gate: dict[str, bool] = {}

    for path in _gate_paths():
        try:
            summary, errors = check_gate(path)
            gate_id = require_str(load_gate(path).get("gate_id"), "gate_id")
            next_allowed = require_bool(
                require_mapping(load_gate(path).get("next_phase_entry"), "next_phase_entry").get("allowed"),
                "next_phase_entry.allowed",
            )
            ready_by_gate[gate_id] = next_allowed
        except GateError as exc:
            print(f"phase review gate check failed for {rel(path)}: {exc}", file=sys.stderr)
            any_errors = True
            continue
        print(summary)
        if errors:
            any_errors = True
            print(f"phase review gate check failed for {rel(path)}: {len(errors)} issue(s)")
            for error in errors[:80]:
                print(f"  - {error}")
            if len(errors) > 80:
                print(f"  ... {len(errors) - 80} more")

    for gate_id in sorted(required_ready):
        if gate_id not in ready_by_gate:
            print(f"{gate_id} is not ready: gate not found")
            any_errors = True
        elif not ready_by_gate[gate_id]:
            print(f"{gate_id} is not ready: owner manual decision has not opened next phase")
            any_errors = True

    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

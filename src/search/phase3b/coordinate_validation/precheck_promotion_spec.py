from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

COORDINATE_VALIDATION_PRECHECK_PROMOTION_SPEC_SOURCE = (
    "phase3b_coordinate_validation_precheck_promotion_spec_v1"
)
SUPPORTED_COORDINATE_VALIDATION_PRECHECK_CANDIDATE_SOURCES = {
    "phase3b_coordinate_validation_precheck_candidate_v1",
    "phase3b_coordinate_validation_precheck_candidate_v2",
}
DEFAULT_PRECHECK_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_precheck_candidate/precheck_candidate.json"
)
DEFAULT_MIN_REJECTED_ANCHOR_COUNT = 8
DEFAULT_MIN_MATRIX_INFEASIBLE_COUNT = 3


def build_phase3b_coordinate_validation_precheck_promotion_spec(
    project_root: Path,
    *,
    precheck_candidate_path: Optional[Path] = None,
    min_rejected_anchor_count: int = DEFAULT_MIN_REJECTED_ANCHOR_COUNT,
    min_matrix_infeasible_count: int = DEFAULT_MIN_MATRIX_INFEASIBLE_COUNT,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    input_path = _resolve_path(
        project_root,
        precheck_candidate_path
        if precheck_candidate_path is not None
        else DEFAULT_PRECHECK_CANDIDATE_PATH,
    )
    candidate_summary, load_error = _load_json_mapping(input_path)
    metadata = _mapping(candidate_summary.get("metadata")) if candidate_summary else {}
    candidate = _mapping(candidate_summary.get("candidate")) if candidate_summary else {}
    gate = _mapping(candidate_summary.get("gate")) if candidate_summary else {}
    validation = (
        _mapping(candidate_summary.get("coordinate_validation"))
        if candidate_summary
        else {}
    )
    joined_xy_proof_candidate = (
        _mapping(candidate_summary.get("joined_xy_proof_preserving_candidate"))
        if candidate_summary
        else {}
    )
    matrix = (
        _mapping(candidate_summary.get("forced_anchor_solver_matrix"))
        if candidate_summary
        else {}
    )
    rejected_samples = [
        dict(entry)
        for entry in list(validation.get("rejected_samples", []))
        if isinstance(entry, Mapping)
    ]
    matrix_entries = [
        dict(entry)
        for entry in list(matrix.get("entries", []))
        if isinstance(entry, Mapping)
    ]
    source_supported = metadata.get("source") in (
        SUPPORTED_COORDINATE_VALIDATION_PRECHECK_CANDIDATE_SOURCES
    )
    design_gate_passed = bool(gate.get("design_gate_passed", False))
    input_runtime_ready = bool(gate.get("runtime_promotion_ready", False))
    failed_input_checks = [
        str(check.get("check_id"))
        for check in list(candidate_summary.get("checks", []) if candidate_summary else [])
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    runtime_guard_present = (
        not input_runtime_ready and "runtime_promotion_guard" in failed_input_checks
    )
    rejected_count = int(validation.get("rejected_count", 0))
    matrix_infeasible_count = int(matrix.get("infeasible_count", 0))
    matrix_all_infeasible = bool(matrix.get("matrix_all_infeasible", False))
    rejected_anchor_coverage_present = bool(
        rejected_count >= int(min_rejected_anchor_count)
        and len(rejected_samples) >= int(min_rejected_anchor_count)
    )
    matrix_evidence_present = bool(
        matrix_all_infeasible
        and matrix_infeasible_count >= int(min_matrix_infeasible_count)
        and len(matrix_entries) >= int(min_matrix_infeasible_count)
    )
    promotion_blocked_by = _promotion_blockers(
        candidate_summary_present=candidate_summary is not None and load_error is None,
        source_supported=source_supported,
        design_gate_passed=design_gate_passed,
        runtime_guard_present=runtime_guard_present,
        rejected_anchor_coverage_present=rejected_anchor_coverage_present,
        matrix_evidence_present=matrix_evidence_present,
        input_runtime_ready=input_runtime_ready,
    )
    spec_ready_for_runtime_slice = bool(
        candidate_summary is not None
        and load_error is None
        and source_supported
        and design_gate_passed
        and runtime_guard_present
        and rejected_anchor_coverage_present
        and matrix_evidence_present
    )
    checks = [
        _check(
            "precheck_candidate_present",
            "pass" if candidate_summary is not None and load_error is None else "fail",
            "precheck candidate summary loaded"
            if candidate_summary is not None and load_error is None
            else load_error or f"missing:{_display_path(project_root, input_path)}",
        ),
        _check(
            "precheck_candidate_schema",
            "pass" if source_supported else "fail",
            "supported coordinate-validation precheck candidate schema"
            if source_supported
            else f"unsupported source:{metadata.get('source')}",
        ),
        _check(
            "design_gate_passed",
            "pass" if design_gate_passed else "fail",
            "diagnostic design gate is passed"
            if design_gate_passed
            else "diagnostic design gate is not passed",
        ),
        _check(
            "runtime_promotion_guard_present",
            "pass" if runtime_guard_present else "fail",
            "runtime promotion remains explicitly guarded"
            if runtime_guard_present
            else "expected runtime_promotion_guard failed check is missing",
        ),
        _check(
            "rejected_anchor_coverage_present",
            "pass" if rejected_anchor_coverage_present else "fail",
            (
                f"rejected_count={rejected_count}; sample_count={len(rejected_samples)}; "
                f"required>={int(min_rejected_anchor_count)}"
            ),
        ),
        _check(
            "forced_anchor_matrix_infeasible",
            "pass" if matrix_evidence_present else "fail",
            (
                f"matrix_all_infeasible={matrix_all_infeasible}; "
                f"infeasible_count={matrix_infeasible_count}; entries={len(matrix_entries)}; "
                f"required>={int(min_matrix_infeasible_count)}"
            ),
        ),
        _check(
            "proof_semantics_unchanged",
            "pass",
            "promotion spec is report-only and does not alter proof sources",
        ),
        _check(
            "runtime_slice_guarded_default",
            "pass",
            "runtime precheck implementation is opt-in and disabled by default",
        ),
    ]
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_PRECHECK_PROMOTION_SPEC_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "precheck_candidate": _display_path(project_root, input_path),
        },
        "candidate": dict(candidate),
        "promotion_status": {
            "spec_ready_for_runtime_slice": bool(spec_ready_for_runtime_slice),
            "design_gate_passed": bool(design_gate_passed),
            "runtime_slice_implemented": True,
            "runtime_promotion_ready": False,
            "runtime_promotion_guarded": bool(runtime_guard_present),
            "input_runtime_promotion_ready": bool(input_runtime_ready),
            "promotion_blocked_by": promotion_blocked_by,
            "recommendation": _recommendation(
                spec_ready_for_runtime_slice=spec_ready_for_runtime_slice,
                promotion_blocked_by=promotion_blocked_by,
                joined_xy_proof_candidate=joined_xy_proof_candidate,
            ),
        },
        "evidence_summary": {
            "min_rejected_anchor_count": int(min_rejected_anchor_count),
            "min_matrix_infeasible_count": int(min_matrix_infeasible_count),
            "rejected_count": rejected_count,
            "rejected_samples": rejected_samples,
            "matrix_infeasible_count": matrix_infeasible_count,
            "matrix_all_infeasible": matrix_all_infeasible,
            "matrix_entries": matrix_entries,
            "joined_xy_proof_candidate_design_ready": bool(
                joined_xy_proof_candidate.get("design_ready", False)
            ),
            "joined_xy_proof_candidate_ready": bool(
                joined_xy_proof_candidate.get("proof_preserving_precheck_ready", False)
            ),
            "joined_xy_proof_candidate_core_label_count": int(
                joined_xy_proof_candidate.get("core_label_count", 0) or 0
            ),
            "joined_xy_row_domain_runtime_patch_ready": bool(
                joined_xy_proof_candidate.get("row_domain_runtime_patch_ready", False)
            ),
            "joined_xy_runtime_patch_authored_in_code": bool(
                joined_xy_proof_candidate.get("runtime_patch_authored_in_code", False)
            ),
            "joined_xy_authored_but_not_enableable": bool(
                joined_xy_proof_candidate.get("authored_but_not_enableable", False)
            ),
            "joined_xy_runtime_enablement_allowed": bool(
                joined_xy_proof_candidate.get("runtime_enablement_allowed", False)
            ),
        },
        "proposed_precheck_contract": _proposed_precheck_contract(),
        "required_runtime_tests": _required_runtime_tests(),
        "required_safety_gates": _required_safety_gates(),
        "checks": checks,
    }


def render_phase3b_coordinate_validation_precheck_promotion_spec_markdown(
    spec: Mapping[str, Any],
) -> str:
    candidate = _mapping(spec.get("candidate"))
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    contract = _mapping(spec.get("proposed_precheck_contract"))
    runtime_env = _mapping(contract.get("runtime_env"))
    lines = [
        "# Phase 3B Coordinate-Validation Precheck Promotion Spec",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Spec ready for runtime slice: {bool(status.get('spec_ready_for_runtime_slice', False))}",
        f"- Runtime slice implemented: {bool(status.get('runtime_slice_implemented', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Runtime promotion guarded: {bool(status.get('runtime_promotion_guarded', False))}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Evidence",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key in [
        "min_rejected_anchor_count",
        "rejected_count",
        "min_matrix_infeasible_count",
        "matrix_infeasible_count",
        "matrix_all_infeasible",
    ]:
        lines.append(f"| {_markdown_cell(key)} | {_markdown_cell(evidence.get(key))} |")
    blocked_by = [str(item) for item in list(status.get("promotion_blocked_by", []))]
    if blocked_by:
        lines.extend(["", "## Promotion Blockers", ""])
        lines.extend(f"- {item}" for item in blocked_by)
    samples = [
        entry
        for entry in list(evidence.get("rejected_samples", []))
        if isinstance(entry, Mapping)
    ]
    if samples:
        lines.extend(
            [
                "",
                "## Coordinate Rejection Samples",
                "",
                "| Anchor | Reason | Status | Forced slots |",
                "| --- | --- | --- | --- |",
            ]
        )
        for entry in samples:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("failure_reason") or entry.get("reason")),
                        _markdown_cell(entry.get("status")),
                        _markdown_cell(entry.get("forced_slot_field_count")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Proposed Runtime Contract",
            "",
            f"- Precheck reason: {contract.get('precheck_reason')}",
            f"- Candidate status: {contract.get('candidate_status')}",
            f"- Master solve skipped: {bool(contract.get('master_solve_skipped', False))}",
            f"- Attempt budget consumed: {bool(contract.get('attempt_budget_consumed', False))}",
            f"- Evidence scope: {contract.get('evidence_scope')}",
            f"- Guard env max anchors: {runtime_env.get('max_anchors_env')} (default {runtime_env.get('default_max_anchors')})",
            f"- Guard env seconds: {runtime_env.get('seconds_env')} (default {runtime_env.get('default_seconds')})",
            "",
            "## Required Proof Summary Fields",
            "",
        ]
    )
    lines.extend(
        f"- {field}"
        for field in list(contract.get("required_proof_summary_fields", []))
    )
    lines.extend(["", "## Required Runtime Tests", ""])
    for test in list(spec.get("required_runtime_tests", [])):
        if isinstance(test, Mapping):
            lines.append(f"- {test.get('test_id')}: {test.get('assertion')}")
    lines.extend(["", "## Required Safety Gates", ""])
    for gate in list(spec.get("required_safety_gates", [])):
        if isinstance(gate, Mapping):
            lines.append(f"- {gate.get('gate_id')}: {gate.get('assertion')}")
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(spec.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_precheck_promotion_spec_text(
    spec: Mapping[str, Any],
) -> str:
    candidate = _mapping(spec.get("candidate"))
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    contract = _mapping(spec.get("proposed_precheck_contract"))
    runtime_env = _mapping(contract.get("runtime_env"))
    lines = [
        "Phase 3B coordinate-validation precheck promotion spec",
        f"candidate={candidate.get('key')}",
        f"spec_ready_for_runtime_slice={bool(status.get('spec_ready_for_runtime_slice', False))}",
        f"runtime_slice_implemented={bool(status.get('runtime_slice_implemented', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"runtime_promotion_guarded={bool(status.get('runtime_promotion_guarded', False))}",
        f"promotion_blocked_by={','.join(str(item) for item in list(status.get('promotion_blocked_by', [])))}",
        f"recommendation={status.get('recommendation')}",
        f"rejected_count={evidence.get('rejected_count')}",
        f"matrix_infeasible_count={evidence.get('matrix_infeasible_count')}",
        f"matrix_all_infeasible={bool(evidence.get('matrix_all_infeasible', False))}",
        f"precheck_reason={contract.get('precheck_reason')}",
        f"candidate_status={contract.get('candidate_status')}",
        f"attempt_budget_consumed={bool(contract.get('attempt_budget_consumed', False))}",
        f"runtime_env_max_anchors={runtime_env.get('max_anchors_env')}",
        f"runtime_env_seconds={runtime_env.get('seconds_env')}",
    ]
    for test in list(spec.get("required_runtime_tests", [])):
        if isinstance(test, Mapping):
            lines.append(f"required_test id={test.get('test_id')} assertion={test.get('assertion')}")
    for gate in list(spec.get("required_safety_gates", [])):
        if isinstance(gate, Mapping):
            lines.append(f"safety_gate id={gate.get('gate_id')} assertion={gate.get('assertion')}")
    for check in list(spec.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _proposed_precheck_contract() -> Dict[str, Any]:
    return {
        "precheck_reason": "coordinate_validation_infeasible",
        "candidate_status": "INFEASIBLE",
        "master_status": "INFEASIBLE",
        "diagnostic_flow_status": "NOT_RUN",
        "master_solve_skipped": True,
        "attempt_budget_consumed": False,
        "campaign_candidate_attempts_incremented": False,
        "evidence_scope": "guarded_runtime_diagnostic_until_fresh_b5a_rerun",
        "terminal_proof_source": "unchanged",
        "parallel_path_behavior": "unchanged; serial pre-master precheck is opt-in",
        "runtime_env": {
            "max_anchors_env": "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS",
            "seconds_env": "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS",
            "default_max_anchors": 0,
            "default_seconds": 2.0,
        },
        "required_proof_summary_fields": [
            "master_candidate_precheck.triggered",
            "master_candidate_precheck.precheck_reason",
            "master_candidate_precheck.master_solve_skipped",
            "coordinate_validation_precheck.triggered",
            "coordinate_validation_precheck.considered_anchor_count",
            "coordinate_validation_precheck.evaluated_anchor_count",
            "coordinate_validation_precheck.infeasible_anchor_count",
            "coordinate_validation_precheck.short_circuited_after_non_triggering_anchor",
            "coordinate_validation_precheck.rejected_anchors[]",
            "coordinate_validation_precheck.forced_anchor_matrix.status_counts",
            "coordinate_validation_precheck.forced_anchor_matrix.entries[]",
            "precheck_lookahead.enabled",
            "precheck_lookahead.slot_index",
            "precheck_lookahead.limit",
            "precheck_lookahead.is_selected_head",
        ],
    }


def _required_runtime_tests() -> list[Dict[str, str]]:
    return [
        {
            "test_id": "coordinate_rejected_candidate_marked_infeasible_without_solve",
            "assertion": (
                "A triggered coordinate-validation precheck records INFEASIBLE, skips master solve, "
                "and preserves candidate attempts at zero."
            ),
        },
        {
            "test_id": "coordinate_non_trigger_writes_no_evidence",
            "assertion": (
                "Non-triggered coordinate-validation scans do not create campaign evidence."
            ),
        },
        {
            "test_id": "coordinate_validation_attempt_limit_is_reported",
            "assertion": (
                "Validation attempt limits are reported and do not silently select a bad hint."
            ),
        },
        {
            "test_id": "forced_anchor_matrix_evidence_is_diagnostic_only",
            "assertion": (
                "Forced-anchor matrix evidence is referenced as diagnostic context, not terminal proof."
            ),
        },
        {
            "test_id": "parallel_path_remains_unchanged",
            "assertion": (
                "Parallel coordinator precheck behavior remains unchanged until an explicit opt-in slice."
            ),
        },
        {
            "test_id": "telemetry_reason_counts_include_coordinate_validation",
            "assertion": (
                "Telemetry preserves existing precheck counters and adds coordinate_validation_infeasible counts."
            ),
        },
    ]


def _required_safety_gates() -> list[Dict[str, str]]:
    return [
        {
            "gate_id": "coordinate_validation_coverage",
            "assertion": "Rejected anchor coverage meets the configured minimum and records validation limit status.",
        },
        {
            "gate_id": "forced_anchor_matrix_all_infeasible",
            "assertion": "Forced-anchor matrix has no feasible, unknown, or skipped branchings for sampled anchors.",
        },
        {
            "gate_id": "exact_hash_truth_unchanged",
            "assertion": "The four exact hash truth sources still match the B0 startline manifest.",
        },
        {
            "gate_id": "b5a_rerun_after_runtime_change",
            "assertion": "A fresh B5A workspace sprint must run after runtime precheck implementation.",
        },
        {
            "gate_id": "b6_b7_status_unchanged",
            "assertion": "Release/viewer/frontdoor/surface-health status remains exact-open.",
        },
    ]


def _promotion_blockers(
    *,
    candidate_summary_present: bool,
    source_supported: bool,
    design_gate_passed: bool,
    runtime_guard_present: bool,
    rejected_anchor_coverage_present: bool,
    matrix_evidence_present: bool,
    input_runtime_ready: bool,
) -> list[str]:
    blockers: list[str] = []
    if not candidate_summary_present:
        blockers.append("precheck_candidate_missing")
    if candidate_summary_present and not source_supported:
        blockers.append("unsupported_precheck_candidate_schema")
    if source_supported and not design_gate_passed:
        blockers.append("design_gate_not_passed")
    if not runtime_guard_present and not input_runtime_ready:
        blockers.append("runtime_promotion_guard_missing")
    elif runtime_guard_present:
        blockers.append("runtime_promotion_guard")
    if not rejected_anchor_coverage_present:
        blockers.append("rejected_anchor_coverage_gate")
    if not matrix_evidence_present:
        blockers.append("forced_anchor_matrix_gate")
    if input_runtime_ready:
        blockers.append("input_unexpectedly_runtime_ready")
    return blockers


def _recommendation(
    *,
    spec_ready_for_runtime_slice: bool,
    promotion_blocked_by: list[str],
    joined_xy_proof_candidate: Mapping[str, Any],
) -> str:
    if spec_ready_for_runtime_slice:
        proof_ready = bool(
            joined_xy_proof_candidate.get("proof_preserving_precheck_ready", False)
        )
        authored_but_not_enableable = bool(
            joined_xy_proof_candidate.get("authored_but_not_enableable", False)
        )
        if proof_ready and authored_but_not_enableable:
            return (
                "Anchor119 row-domain runtime patch is authored and the joined-XY "
                "proof-preserving extraction is no longer the next blocker, but runtime "
                "enablement is still blocked. Keep it disabled and require "
                "reviewed_runtime_patch_exists / reviewed enablement before any B5A "
                "workspace rerun or production acceptance."
            )
        if bool(joined_xy_proof_candidate.get("design_ready", False)) and not bool(
            joined_xy_proof_candidate.get("proof_preserving_precheck_ready", False)
        ):
            return (
                "Guarded coordinate-validation runtime precheck exists, but the preferred "
                "next move is to finish the joined-XY proof-preserving extraction around "
                "protocol_planter_buckwheat_3_x_labels before any B5A workspace rerun."
            )
        return (
            "Guarded coordinate-validation runtime precheck is available for an explicit "
            "B5A workspace rerun; production promotion still requires fresh B5A evidence."
        )
    return "Spec is not ready; blocked by " + ", ".join(
        promotion_blocked_by or ["unknown"]
    )


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": str(status),
        "detail": str(detail),
    }


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}

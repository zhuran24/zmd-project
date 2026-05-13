from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

COORDINATE_VALIDATION_PRECHECK_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_precheck_candidate_v2"
)
START_COMPATIBILITY_SOURCE = "phase3b_start_compatibility_diagnostics_v1"
FORCED_ANCHOR_SOLVER_MATRIX_SOURCE = "phase3b_forced_anchor_solver_matrix_v1"
COORDINATE_VALIDATION_PROFILE_PROBE_SOURCE = (
    "phase3b_coordinate_validation_profile_probe_v1"
)
JOINED_XY_COORDINATE_VALIDATION_DELTA_SYNTHESIS_SOURCE = (
    "phase3b_joined_xy_coordinate_validation_delta_synthesis_v1"
)
B5_ANCHOR_SPRINT_SUMMARY_SOURCE = "phase3b_b5_anchor_sprint_summary_v1"
DEFAULT_START_COMPATIBILITY_PATH = Path(
    ".artifacts/phase3b_start_compatibility_current/start_compatibility_67x13.json"
)
DEFAULT_FORCED_ANCHOR_SOLVER_MATRIX_PATH = Path(
    ".artifacts/phase3b_forced_anchor_solver_matrix_current/forced_anchor_solver_matrix_67x13_anchor118.json"
)
DEFAULT_JOINED_XY_PROFILE_PROBE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_profile_probe_joined_xy_anchor119_20260423/"
    "coordinate_validation_profile_probe.json"
)
DEFAULT_JOINED_XY_DELTA_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_joined_xy_coordinate_validation_delta_synthesis_20260423/"
    "joined_xy_coordinate_validation_delta_synthesis.json"
)
DEFAULT_B5A_SUMMARY_PATH = Path(
    ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json"
)
ANCHOR119_PAIR_X_CORE_SYNTHESIS_SOURCE = "phase3b_anchor119_pair_x_core_synthesis_v1"
ANCHOR119_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_SOURCE = (
    "phase3b_anchor119_pair_x_no_ghost_space_synthesis_v1"
)
ORDER_IMPLIED_CAPACITY_EXPLANATION_SOURCE = (
    "phase3b_coordinate_validation_order_implied_capacity_explanation_v1"
)
ANCHOR119_ROW_DOMAIN_RUNTIME_PATCH_STATUS_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
)
ANCHOR119_ROW_DOMAIN_REVIEW_STATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1"
)
DEFAULT_ANCHOR119_PAIR_X_CORE_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_core_synthesis_20260423/"
    "anchor119_pair_x_core_synthesis.json"
)
DEFAULT_ANCHOR119_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_no_ghost_space_synthesis_20260423/"
    "anchor119_pair_x_no_ghost_space_synthesis.json"
)
DEFAULT_ORDER_IMPLIED_CAPACITY_EXPLANATION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_order_implied_capacity_explanation_20260423/"
    "order_implied_capacity_explanation.json"
)
DEFAULT_ANCHOR119_ROW_DOMAIN_RUNTIME_PATCH_STATUS_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_20260424/"
    "anchor119_row_domain_runtime_patch_status.json"
)
DEFAULT_ANCHOR119_ROW_DOMAIN_REVIEW_STATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_review_state_20260425/"
    "anchor119_row_domain_review_state.json"
)


def build_phase3b_coordinate_validation_precheck_candidate_summary(
    project_root: Path,
    *,
    start_compatibility_path: Optional[Path] = None,
    forced_anchor_solver_matrix_path: Optional[Path] = None,
    joined_xy_profile_probe_path: Optional[Path] = None,
    joined_xy_delta_synthesis_path: Optional[Path] = None,
    b5a_summary_path: Optional[Path] = None,
    anchor119_pair_x_core_synthesis_path: Optional[Path] = None,
    anchor119_pair_x_no_ghost_space_synthesis_path: Optional[Path] = None,
    order_implied_capacity_explanation_path: Optional[Path] = None,
    anchor119_row_domain_runtime_patch_status_path: Optional[Path] = None,
    anchor119_row_domain_review_state_path: Optional[Path] = None,
    min_rejected_anchor_count: int = 1,
    min_matrix_infeasible_count: int = 1,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    start_path = _resolve_path(
        project_root,
        start_compatibility_path
        if start_compatibility_path is not None
        else DEFAULT_START_COMPATIBILITY_PATH,
    )
    matrix_path = _resolve_path(
        project_root,
        forced_anchor_solver_matrix_path
        if forced_anchor_solver_matrix_path is not None
        else DEFAULT_FORCED_ANCHOR_SOLVER_MATRIX_PATH,
    )
    joined_xy_profile_probe_resolved = _resolve_path(
        project_root,
        joined_xy_profile_probe_path
        if joined_xy_profile_probe_path is not None
        else DEFAULT_JOINED_XY_PROFILE_PROBE_PATH,
    )
    joined_xy_delta_synthesis_resolved = _resolve_path(
        project_root,
        joined_xy_delta_synthesis_path
        if joined_xy_delta_synthesis_path is not None
        else DEFAULT_JOINED_XY_DELTA_SYNTHESIS_PATH,
    )
    b5a_summary_resolved = _resolve_path(
        project_root,
        b5a_summary_path if b5a_summary_path is not None else DEFAULT_B5A_SUMMARY_PATH,
    )
    anchor119_pair_x_core_synthesis_resolved = _resolve_path(
        project_root,
        anchor119_pair_x_core_synthesis_path
        if anchor119_pair_x_core_synthesis_path is not None
        else DEFAULT_ANCHOR119_PAIR_X_CORE_SYNTHESIS_PATH,
    )
    anchor119_pair_x_no_ghost_space_synthesis_resolved = _resolve_path(
        project_root,
        anchor119_pair_x_no_ghost_space_synthesis_path
        if anchor119_pair_x_no_ghost_space_synthesis_path is not None
        else DEFAULT_ANCHOR119_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH,
    )
    order_implied_capacity_explanation_resolved = _resolve_path(
        project_root,
        order_implied_capacity_explanation_path
        if order_implied_capacity_explanation_path is not None
        else DEFAULT_ORDER_IMPLIED_CAPACITY_EXPLANATION_PATH,
    )
    anchor119_row_domain_runtime_patch_status_resolved = _resolve_path(
        project_root,
        anchor119_row_domain_runtime_patch_status_path
        if anchor119_row_domain_runtime_patch_status_path is not None
        else DEFAULT_ANCHOR119_ROW_DOMAIN_RUNTIME_PATCH_STATUS_PATH,
    )
    anchor119_row_domain_review_state_resolved = _resolve_path(
        project_root,
        anchor119_row_domain_review_state_path
        if anchor119_row_domain_review_state_path is not None
        else DEFAULT_ANCHOR119_ROW_DOMAIN_REVIEW_STATE_PATH,
    )
    start_report, start_error = _load_json_mapping(start_path)
    matrix_report, matrix_error = _load_json_mapping(matrix_path)
    joined_xy_profile_probe, joined_xy_profile_probe_error = _load_json_mapping(
        joined_xy_profile_probe_resolved
    )
    joined_xy_delta_synthesis, joined_xy_delta_synthesis_error = _load_json_mapping(
        joined_xy_delta_synthesis_resolved
    )
    b5a_summary, b5a_summary_error = _load_json_mapping(b5a_summary_resolved)
    anchor119_pair_x_core_synthesis, anchor119_pair_x_core_synthesis_error = (
        _load_json_mapping(anchor119_pair_x_core_synthesis_resolved)
    )
    anchor119_pair_x_no_ghost_space_synthesis, anchor119_pair_x_no_ghost_space_synthesis_error = (
        _load_json_mapping(anchor119_pair_x_no_ghost_space_synthesis_resolved)
    )
    order_implied_capacity_explanation, order_implied_capacity_explanation_error = (
        _load_json_mapping(order_implied_capacity_explanation_resolved)
    )
    anchor119_row_domain_runtime_patch_status, anchor119_row_domain_runtime_patch_status_error = (
        _load_json_mapping(anchor119_row_domain_runtime_patch_status_resolved)
    )
    if anchor119_row_domain_review_state_path is not None:
        anchor119_row_domain_review_state, anchor119_row_domain_review_state_error = (
            _load_json_mapping(anchor119_row_domain_review_state_resolved)
        )
    else:
        anchor119_row_domain_review_state, anchor119_row_domain_review_state_error = (
            None,
            "not_provided",
        )

    start_meta = _mapping(start_report.get("metadata")) if start_report else {}
    matrix_meta = _mapping(matrix_report.get("metadata")) if matrix_report else {}
    joined_xy_profile_meta = (
        _mapping(joined_xy_profile_probe.get("metadata"))
        if joined_xy_profile_probe
        else {}
    )
    joined_xy_delta_meta = (
        _mapping(joined_xy_delta_synthesis.get("metadata"))
        if joined_xy_delta_synthesis
        else {}
    )
    b5a_meta = _mapping(b5a_summary.get("metadata")) if b5a_summary else {}
    anchor119_pair_x_core_meta = (
        _mapping(anchor119_pair_x_core_synthesis.get("metadata"))
        if anchor119_pair_x_core_synthesis
        else {}
    )
    anchor119_pair_x_no_ghost_space_meta = (
        _mapping(anchor119_pair_x_no_ghost_space_synthesis.get("metadata"))
        if anchor119_pair_x_no_ghost_space_synthesis
        else {}
    )
    order_implied_capacity_meta = (
        _mapping(order_implied_capacity_explanation.get("metadata"))
        if order_implied_capacity_explanation
        else {}
    )
    anchor119_row_domain_runtime_patch_status_meta = (
        _mapping(anchor119_row_domain_runtime_patch_status.get("metadata"))
        if anchor119_row_domain_runtime_patch_status
        else {}
    )
    anchor119_row_domain_review_state_meta = (
        _mapping(anchor119_row_domain_review_state.get("metadata"))
        if anchor119_row_domain_review_state
        else {}
    )
    anchor119_row_domain_review_state_status = (
        _mapping(anchor119_row_domain_review_state.get("status"))
        if anchor119_row_domain_review_state
        else {}
    )
    candidate = _mapping(start_report.get("candidate")) if start_report else {}
    start_status = _mapping(start_report.get("status")) if start_report else {}
    start_diag = _mapping(start_report.get("diagnostics")) if start_report else {}
    warm_start = _mapping(start_diag.get("warm_start"))
    failure_summary = _mapping(start_diag.get("start_failure_summary"))
    matrix_status = _mapping(matrix_report.get("status")) if matrix_report else {}
    matrix_candidate = _mapping(matrix_report.get("candidate")) if matrix_report else {}

    rejected_count = int(
        warm_start.get(
            "ghost_aware_coordinate_validation_rejected_count",
            _coordinate_failure_count(failure_summary),
        )
    )
    validation_limit_reached = bool(
        warm_start.get("ghost_aware_coordinate_validation_limit_reached", False)
    ) or "coordinate_validation_attempt_limit_reached" in _mapping(
        failure_summary.get("failure_reason_counts")
    )
    rejected_samples = _coordinate_failure_samples(failure_summary, warm_start)
    matrix_payload = _mapping(matrix_report.get("matrix")) if matrix_report else {}
    matrix_entries = [
        dict(entry)
        for entry in list(
            matrix_report.get(
                "matrix_entries",
                matrix_report.get("entries", matrix_payload.get("entries", [])),
            )
        )
        if isinstance(entry, Mapping)
    ] if matrix_report else []
    if not matrix_entries and matrix_report:
        matrix_entries = [
            dict(entry)
            for entry in list(matrix_report.get("forced_anchors", []))
            if isinstance(entry, Mapping)
        ]
    matrix_status_counts = _mapping(matrix_payload.get("status_counts"))
    if not matrix_status_counts and matrix_report:
        matrix_status_counts = _mapping(matrix_status.get("status_counts"))
    if matrix_entries:
        derived_matrix_status_counts: Dict[str, int] = {}
        for entry in matrix_entries:
            key = str(entry.get("status") or "UNKNOWN")
            derived_matrix_status_counts[key] = derived_matrix_status_counts.get(key, 0) + 1
        matrix_status_counts = derived_matrix_status_counts
    matrix_infeasible_count = int(matrix_status_counts.get("INFEASIBLE", 0))
    matrix_all_infeasible = bool(matrix_entries) and matrix_infeasible_count == len(
        matrix_entries
    )
    computed_matrix_outcome = str(matrix_status.get("outcome") or "")
    if matrix_entries:
        if matrix_all_infeasible:
            computed_matrix_outcome = "matrix_all_infeasible"
        elif matrix_infeasible_count > 0:
            computed_matrix_outcome = "matrix_mixed_or_incomplete"
        else:
            computed_matrix_outcome = "matrix_without_infeasible_terminal"
    candidate_key = str(candidate.get("key") or matrix_candidate.get("key") or "")
    matrix_candidate_matches = not matrix_candidate or str(
        matrix_candidate.get("key", candidate_key)
    ) == candidate_key
    joined_xy_profile_probe_supported = (
        joined_xy_profile_meta.get("source") == COORDINATE_VALIDATION_PROFILE_PROBE_SOURCE
    )
    joined_xy_delta_supported = (
        joined_xy_delta_meta.get("source")
        == JOINED_XY_COORDINATE_VALIDATION_DELTA_SYNTHESIS_SOURCE
    )
    b5a_summary_supported = (
        b5a_meta.get("source") == B5_ANCHOR_SPRINT_SUMMARY_SOURCE
    )
    joined_xy_current_blocker = _build_joined_xy_current_blocker(
        candidate_key=candidate_key,
        b5a_summary=b5a_summary,
        b5a_summary_error=b5a_summary_error,
        b5a_summary_supported=b5a_summary_supported,
        joined_xy_profile_probe=joined_xy_profile_probe,
        joined_xy_profile_probe_error=joined_xy_profile_probe_error,
        joined_xy_profile_probe_supported=joined_xy_profile_probe_supported,
        joined_xy_delta_synthesis=joined_xy_delta_synthesis,
        joined_xy_delta_synthesis_error=joined_xy_delta_synthesis_error,
        joined_xy_delta_supported=joined_xy_delta_supported,
    )
    joined_xy_proof_preserving_candidate = _build_joined_xy_proof_preserving_candidate(
        anchor119_pair_x_core_synthesis=anchor119_pair_x_core_synthesis,
        anchor119_pair_x_core_synthesis_error=anchor119_pair_x_core_synthesis_error,
        anchor119_pair_x_core_supported=(
            anchor119_pair_x_core_meta.get("source")
            == ANCHOR119_PAIR_X_CORE_SYNTHESIS_SOURCE
        ),
        anchor119_pair_x_no_ghost_space_synthesis=anchor119_pair_x_no_ghost_space_synthesis,
        anchor119_pair_x_no_ghost_space_synthesis_error=(
            anchor119_pair_x_no_ghost_space_synthesis_error
        ),
        anchor119_pair_x_no_ghost_space_supported=(
            anchor119_pair_x_no_ghost_space_meta.get("source")
            == ANCHOR119_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_SOURCE
        ),
        order_implied_capacity_explanation=order_implied_capacity_explanation,
        order_implied_capacity_explanation_error=(
            order_implied_capacity_explanation_error
        ),
        order_implied_capacity_supported=(
            order_implied_capacity_meta.get("source")
            == ORDER_IMPLIED_CAPACITY_EXPLANATION_SOURCE
        ),
        anchor119_row_domain_runtime_patch_status=anchor119_row_domain_runtime_patch_status,
        anchor119_row_domain_runtime_patch_status_error=(
            anchor119_row_domain_runtime_patch_status_error
        ),
        anchor119_row_domain_runtime_patch_status_supported=(
            anchor119_row_domain_runtime_patch_status_meta.get("source")
            == ANCHOR119_ROW_DOMAIN_RUNTIME_PATCH_STATUS_SOURCE
        ),
        joined_xy_current_blocker=joined_xy_current_blocker,
    )
    row_domain_review_state_present = bool(
        isinstance(anchor119_row_domain_review_state, Mapping)
        and anchor119_row_domain_review_state_error is None
        and anchor119_row_domain_review_state_meta.get("source")
        == ANCHOR119_ROW_DOMAIN_REVIEW_STATE_SOURCE
    )
    row_domain_review_state_ready = bool(
        row_domain_review_state_present
        and anchor119_row_domain_review_state_status.get("review_state_ready", False)
        and anchor119_row_domain_review_state_status.get(
            "repo_side_review_state_updated", False
        )
        and anchor119_row_domain_review_state_status.get(
            "reviewed_runtime_patch_exists", False
        )
        and not anchor119_row_domain_review_state_status.get(
            "runtime_enablement_allowed", False
        )
        and not anchor119_row_domain_review_state_status.get(
            "production_acceptance_refresh_completed", False
        )
    )
    joined_xy_proof_preserving_candidate.update(
        {
            "row_domain_review_state_present": bool(row_domain_review_state_present),
            "row_domain_review_state_ready": bool(row_domain_review_state_ready),
            "reviewed_runtime_patch_exists": bool(row_domain_review_state_ready),
            "row_domain_review_state_detail": (
                "anchor119 row-domain review state marker loaded"
                if row_domain_review_state_ready
                else anchor119_row_domain_review_state_error
                or (
                    "unsupported source:"
                    + str(anchor119_row_domain_review_state_meta.get("source"))
                )
            ),
        }
    )
    if (
        joined_xy_proof_preserving_candidate.get("row_domain_runtime_patch_ready")
        and row_domain_review_state_ready
    ):
        joined_xy_proof_preserving_candidate["recommendation"] = (
            "Reviewed runtime patch state is now marked in a repo-side artifact. "
            "The next gate is production_acceptance_refresh_completed via the locked "
            "prod_4x4_normal production acceptance refresh; runtime_enablement_allowed "
            "remains false and this is not final 168h authorization."
        )
    joined_xy_workspace_check_status = (
        "pass"
        if joined_xy_current_blocker["workspace_present"]
        else "skipped"
        if joined_xy_current_blocker["workspace_missing"]
        else "fail"
    )
    joined_xy_workspace_start_incompatible_status = (
        "pass"
        if joined_xy_current_blocker["workspace_start_incompatible"]
        else "skipped"
        if joined_xy_current_blocker["workspace_missing"]
        else "fail"
    )
    joined_xy_profile_probe_check_status = (
        "pass"
        if joined_xy_current_blocker["profile_probe_terminal_infeasible"]
        else "skipped"
        if joined_xy_current_blocker["profile_probe_missing"]
        else "fail"
    )
    joined_xy_delta_check_status = (
        "pass"
        if joined_xy_current_blocker["delta_shrink_present"]
        else "skipped"
        if joined_xy_current_blocker["delta_missing"]
        else "fail"
    )
    design_gate_passed = bool(
        start_report is not None
        and start_error is None
        and start_meta.get("source") == START_COMPATIBILITY_SOURCE
        and matrix_report is not None
        and matrix_error is None
        and matrix_meta.get("source") == FORCED_ANCHOR_SOLVER_MATRIX_SOURCE
        and matrix_candidate_matches
        and rejected_count >= int(min_rejected_anchor_count)
        and matrix_infeasible_count >= int(min_matrix_infeasible_count)
        and matrix_all_infeasible
    )
    gate_recommendation = (
        joined_xy_proof_preserving_candidate["recommendation"]
        if bool(
            joined_xy_proof_preserving_candidate.get(
                "proof_preserving_precheck_ready", False
            )
        )
        else _recommendation(
            design_gate_passed=design_gate_passed,
            rejected_count=rejected_count,
            matrix_infeasible_count=matrix_infeasible_count,
            matrix_all_infeasible=matrix_all_infeasible,
            joined_xy_current_blocker=joined_xy_current_blocker,
        )
    )
    checks = [
        _check(
            "start_compatibility_present",
            "pass" if start_report is not None and start_error is None else "fail",
            "start-compatibility report loaded"
            if start_report is not None and start_error is None
            else start_error or f"missing:{_display_path(project_root, start_path)}",
        ),
        _check(
            "start_compatibility_schema",
            "pass" if start_meta.get("source") == START_COMPATIBILITY_SOURCE else "fail",
            "supported start-compatibility schema"
            if start_meta.get("source") == START_COMPATIBILITY_SOURCE
            else f"unsupported source:{start_meta.get('source')}",
        ),
        _check(
            "coordinate_validation_rejections_present",
            "pass" if rejected_count >= int(min_rejected_anchor_count) else "fail",
            f"rejected_count={rejected_count}; required>={int(min_rejected_anchor_count)}",
        ),
        _check(
            "forced_anchor_solver_matrix_present",
            "pass" if matrix_report is not None and matrix_error is None else "fail",
            "forced-anchor solver matrix loaded"
            if matrix_report is not None and matrix_error is None
            else matrix_error or f"missing:{_display_path(project_root, matrix_path)}",
        ),
        _check(
            "forced_anchor_solver_matrix_schema",
            "pass"
            if matrix_meta.get("source") == FORCED_ANCHOR_SOLVER_MATRIX_SOURCE
            else "fail",
            "supported solver-matrix schema"
            if matrix_meta.get("source") == FORCED_ANCHOR_SOLVER_MATRIX_SOURCE
            else f"unsupported source:{matrix_meta.get('source')}",
        ),
        _check(
            "candidate_keys_match",
            "pass" if matrix_candidate_matches else "fail",
            f"start={candidate_key}; matrix={matrix_candidate.get('key')}",
        ),
        _check(
            "matrix_infeasible_count",
            "pass"
            if matrix_infeasible_count >= int(min_matrix_infeasible_count)
            else "fail",
            f"infeasible_count={matrix_infeasible_count}; required>={int(min_matrix_infeasible_count)}",
        ),
        _check(
            "matrix_all_infeasible",
            "pass" if matrix_all_infeasible else "fail",
            f"outcome={computed_matrix_outcome}; entries={len(matrix_entries)}",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "coordinate-validation evidence is diagnostic; add deterministic "
                "runtime precheck tests and rerun B5A before promotion"
            ),
        ),
        _check(
            "joined_xy_workspace_summary_present",
            joined_xy_workspace_check_status,
            joined_xy_current_blocker["workspace_detail"],
        ),
        _check(
            "joined_xy_workspace_start_incompatible",
            joined_xy_workspace_start_incompatible_status,
            joined_xy_current_blocker["workspace_start_incompatible_detail"],
        ),
        _check(
            "joined_xy_profile_probe_terminal_infeasible",
            joined_xy_profile_probe_check_status,
            joined_xy_current_blocker["profile_probe_detail"],
        ),
        _check(
            "joined_xy_delta_shrink_present",
            joined_xy_delta_check_status,
            joined_xy_current_blocker["delta_detail"],
        ),
        _check(
            "joined_xy_pair_x_core_present",
            "pass"
            if joined_xy_proof_preserving_candidate["core_present"]
            else "skipped"
            if joined_xy_proof_preserving_candidate["core_missing"]
            else "fail",
            joined_xy_proof_preserving_candidate["core_detail"],
        ),
        _check(
            "joined_xy_pair_x_core_minimality",
            "pass"
            if joined_xy_proof_preserving_candidate["minimality_ready"]
            else "skipped"
            if joined_xy_proof_preserving_candidate["core_missing"]
            else "fail",
            joined_xy_proof_preserving_candidate["minimality_detail"],
        ),
        _check(
            "joined_xy_pair_x_anchor_sweep_all_infeasible",
            "pass"
            if joined_xy_proof_preserving_candidate["anchor_sweep_all_infeasible"]
            else "skipped"
            if joined_xy_proof_preserving_candidate["no_ghost_space_missing"]
            else "fail",
            joined_xy_proof_preserving_candidate["anchor_sweep_detail"],
        ),
        _check(
            "joined_xy_pair_x_standalone_pair_optimal",
            "pass"
            if joined_xy_proof_preserving_candidate["standalone_pair_optimal"]
            else "skipped"
            if joined_xy_proof_preserving_candidate["no_ghost_space_missing"]
            else "fail",
            joined_xy_proof_preserving_candidate["standalone_pair_detail"],
        ),
        _check(
            "joined_xy_order_capacity_explanation_present",
            "pass"
            if joined_xy_proof_preserving_candidate["order_capacity_present"]
            else "skipped"
            if joined_xy_proof_preserving_candidate["order_capacity_missing"]
            else "fail",
            joined_xy_proof_preserving_candidate["order_capacity_detail"],
        ),
        _check(
            "anchor119_row_domain_review_state_marker",
            "pass"
            if row_domain_review_state_ready
            else "skipped"
            if anchor119_row_domain_review_state_error == "not_provided"
            else "fail",
            joined_xy_proof_preserving_candidate["row_domain_review_state_detail"],
        ),
    ]
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_PRECHECK_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "start_compatibility": _display_path(project_root, start_path),
            "forced_anchor_solver_matrix": _display_path(project_root, matrix_path),
            "joined_xy_profile_probe": _display_path(
                project_root, joined_xy_profile_probe_resolved
            ),
            "joined_xy_delta_synthesis": _display_path(
                project_root, joined_xy_delta_synthesis_resolved
            ),
            "b5a_summary": _display_path(project_root, b5a_summary_resolved),
            "anchor119_pair_x_core_synthesis": _display_path(
                project_root, anchor119_pair_x_core_synthesis_resolved
            ),
            "anchor119_pair_x_no_ghost_space_synthesis": _display_path(
                project_root, anchor119_pair_x_no_ghost_space_synthesis_resolved
            ),
            "order_implied_capacity_explanation": _display_path(
                project_root, order_implied_capacity_explanation_resolved
            ),
            "anchor119_row_domain_runtime_patch_status": _display_path(
                project_root, anchor119_row_domain_runtime_patch_status_resolved
            ),
            "anchor119_row_domain_review_state": _display_path(
                project_root, anchor119_row_domain_review_state_resolved
            ),
        },
        "candidate": dict(candidate or matrix_candidate),
        "input_status": {
            "start_compatibility": dict(start_status),
            "forced_anchor_solver_matrix": dict(matrix_status),
        },
        "gate": {
            "design_gate_passed": bool(design_gate_passed),
            "runtime_promotion_ready": False,
            "min_rejected_anchor_count": int(min_rejected_anchor_count),
            "min_matrix_infeasible_count": int(min_matrix_infeasible_count),
            "validation_limit_reached": bool(validation_limit_reached),
            "recommendation": gate_recommendation,
            "promotion_requirements": [
                "Broaden validation coverage beyond the current rejected anchor sample.",
                "Add deterministic runtime pre-master tests before any eliminator promotion.",
                "Keep terminal proof source unchanged; this report is diagnostic evidence only.",
                "Rerun B5A in a fresh workspace after any runtime precheck change.",
                (
                    "Translate the joined-XY shrunk current blocker into a proof-preserving "
                    "precheck candidate before another joined-XY workspace rerun."
                ),
            ],
        },
        "coordinate_validation": {
            "rejected_count": int(rejected_count),
            "validation_limit_reached": bool(validation_limit_reached),
            "rejected_samples": rejected_samples,
            "failure_reason_counts": dict(
                _mapping(failure_summary.get("failure_reason_counts"))
            ),
        },
        "forced_anchor_solver_matrix": {
            "outcome": computed_matrix_outcome,
            "status_counts": dict(matrix_status_counts),
            "infeasible_count": int(matrix_infeasible_count),
            "matrix_all_infeasible": bool(matrix_all_infeasible),
            "entries": matrix_entries,
        },
        "joined_xy_current_blocker": joined_xy_current_blocker,
        "joined_xy_proof_preserving_candidate": joined_xy_proof_preserving_candidate,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_precheck_candidate_markdown(
    summary: Mapping[str, Any],
) -> str:
    candidate = _mapping(summary.get("candidate"))
    gate = _mapping(summary.get("gate"))
    validation = _mapping(summary.get("coordinate_validation"))
    matrix = _mapping(summary.get("forced_anchor_solver_matrix"))
    lines = [
        "# Phase 3B Coordinate-Validation Precheck Candidate Gate",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Design gate passed: {bool(gate.get('design_gate_passed', False))}",
        f"- Runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}",
        f"- Coordinate rejected anchors: {validation.get('rejected_count', 0)}",
        f"- Matrix outcome: {matrix.get('outcome')}",
        f"- Recommendation: {gate.get('recommendation')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(summary.get("checks", [])):
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
    samples = [
        entry
        for entry in list(validation.get("rejected_samples", []))
        if isinstance(entry, Mapping)
    ]
    if samples:
        lines.extend(
            [
                "",
                "## Coordinate Rejection Samples",
                "",
                "| Anchor | Reason | Status | Forced Slots |",
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
    entries = [
        entry
        for entry in list(matrix.get("entries", []))
        if isinstance(entry, Mapping)
    ]
    if entries:
        lines.extend(
            [
                "",
                "## Solver Matrix",
                "",
                "| Anchor | Branching | Status | Wall | Branches | Conflicts |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in entries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("search_branching") or entry.get("branching")),
                        _markdown_cell(entry.get("status")),
                        _markdown_cell(entry.get("wall_time")),
                        _markdown_cell(entry.get("branches")),
                        _markdown_cell(entry.get("conflicts")),
                    ]
                )
                + " |"
            )
    requirements = [str(item) for item in list(gate.get("promotion_requirements", []))]
    if requirements:
        lines.extend(["", "## Promotion Requirements", ""])
        lines.extend(f"- {item}" for item in requirements)
    joined_xy_current_blocker = _mapping(summary.get("joined_xy_current_blocker"))
    joined_xy_proof_preserving_candidate = _mapping(
        summary.get("joined_xy_proof_preserving_candidate")
    )
    if joined_xy_current_blocker:
        lines.extend(
            [
                "",
                "## Joined-XY Current Blocker",
                "",
                f"- Active: {bool(joined_xy_current_blocker.get('active', False))}",
                f"- Blocker subtype: {joined_xy_current_blocker.get('blocker_subtype')}",
                f"- Workspace outcome: {joined_xy_current_blocker.get('workspace_outcome')}",
                f"- Workspace branches/conflicts: "
                f"{joined_xy_current_blocker.get('workspace_master_branches')}/"
                f"{joined_xy_current_blocker.get('workspace_master_conflicts')}",
                f"- Workspace deterministic time: "
                f"{joined_xy_current_blocker.get('workspace_master_deterministic_time')}",
                f"- Coordinate validation infeasible count: "
                f"{joined_xy_current_blocker.get('coordinate_validation_infeasible_count')}",
                f"- Profile probe outcome: {joined_xy_current_blocker.get('profile_probe_outcome')}",
                f"- Best terminal profile: {joined_xy_current_blocker.get('best_terminal_profile')}",
                f"- Delta outcome: {joined_xy_current_blocker.get('delta_outcome')}",
                f"- Shrunk core outcome: {joined_xy_current_blocker.get('shrunk_core_outcome')}",
                f"- Shrunk core label count: {joined_xy_current_blocker.get('shrunk_core_label_count')}",
                f"- Recommendation: {joined_xy_current_blocker.get('recommendation')}",
            ]
        )
    if joined_xy_proof_preserving_candidate:
        lines.extend(
            [
                "",
                "## Joined-XY Proof-Preserving Candidate",
                "",
                f"- Present: {bool(joined_xy_proof_preserving_candidate.get('present', False))}",
                f"- Design ready: {bool(joined_xy_proof_preserving_candidate.get('design_ready', False))}",
                f"- Proof-preserving precheck ready: {bool(joined_xy_proof_preserving_candidate.get('proof_preserving_precheck_ready', False))}",
                f"- Core outcome: {joined_xy_proof_preserving_candidate.get('core_outcome')}",
                f"- Core label count: {joined_xy_proof_preserving_candidate.get('core_label_count')}",
                f"- Minimality ready: {bool(joined_xy_proof_preserving_candidate.get('minimality_ready', False))}",
                f"- Anchor sweep all infeasible: {bool(joined_xy_proof_preserving_candidate.get('anchor_sweep_all_infeasible', False))}",
                f"- Standalone pair optimal: {bool(joined_xy_proof_preserving_candidate.get('standalone_pair_optimal', False))}",
                f"- Order-capacity explanation present: {bool(joined_xy_proof_preserving_candidate.get('order_capacity_present', False))}",
                f"- Row-domain review state ready: {bool(joined_xy_proof_preserving_candidate.get('row_domain_review_state_ready', False))}",
                f"- Reviewed runtime patch exists: {bool(joined_xy_proof_preserving_candidate.get('reviewed_runtime_patch_exists', False))}",
                f"- Recommendation: {joined_xy_proof_preserving_candidate.get('recommendation')}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_precheck_candidate_text(
    summary: Mapping[str, Any],
) -> str:
    candidate = _mapping(summary.get("candidate"))
    gate = _mapping(summary.get("gate"))
    validation = _mapping(summary.get("coordinate_validation"))
    matrix = _mapping(summary.get("forced_anchor_solver_matrix"))
    joined_xy_current_blocker = _mapping(summary.get("joined_xy_current_blocker"))
    joined_xy_proof_preserving_candidate = _mapping(
        summary.get("joined_xy_proof_preserving_candidate")
    )
    lines = [
        "Phase 3B coordinate-validation precheck candidate gate",
        f"candidate={candidate.get('key')}",
        f"design_gate_passed={bool(gate.get('design_gate_passed', False))}",
        f"runtime_promotion_ready={bool(gate.get('runtime_promotion_ready', False))}",
        f"coordinate_rejected_count={validation.get('rejected_count', 0)}",
        f"validation_limit_reached={bool(gate.get('validation_limit_reached', False))}",
        f"matrix_outcome={matrix.get('outcome')}",
        f"matrix_infeasible_count={matrix.get('infeasible_count', 0)}",
        f"recommendation={gate.get('recommendation')}",
    ]
    if joined_xy_current_blocker:
        lines.extend(
            [
                f"joined_xy_current_blocker_active={bool(joined_xy_current_blocker.get('active', False))}",
                f"joined_xy_blocker_subtype={joined_xy_current_blocker.get('blocker_subtype')}",
                f"joined_xy_workspace_outcome={joined_xy_current_blocker.get('workspace_outcome')}",
                f"joined_xy_workspace_master_branches={joined_xy_current_blocker.get('workspace_master_branches')}",
                f"joined_xy_workspace_master_conflicts={joined_xy_current_blocker.get('workspace_master_conflicts')}",
                f"joined_xy_workspace_master_deterministic_time={joined_xy_current_blocker.get('workspace_master_deterministic_time')}",
                f"joined_xy_coordinate_validation_infeasible_count={joined_xy_current_blocker.get('coordinate_validation_infeasible_count')}",
                f"joined_xy_profile_probe_outcome={joined_xy_current_blocker.get('profile_probe_outcome')}",
                f"joined_xy_best_terminal_profile={joined_xy_current_blocker.get('best_terminal_profile')}",
                f"joined_xy_delta_outcome={joined_xy_current_blocker.get('delta_outcome')}",
                f"joined_xy_shrunk_core_outcome={joined_xy_current_blocker.get('shrunk_core_outcome')}",
                f"joined_xy_shrunk_core_label_count={joined_xy_current_blocker.get('shrunk_core_label_count')}",
            ]
        )
    if joined_xy_proof_preserving_candidate:
        lines.extend(
            [
                f"joined_xy_proof_candidate_present={bool(joined_xy_proof_preserving_candidate.get('present', False))}",
                f"joined_xy_proof_candidate_design_ready={bool(joined_xy_proof_preserving_candidate.get('design_ready', False))}",
                f"joined_xy_proof_candidate_ready={bool(joined_xy_proof_preserving_candidate.get('proof_preserving_precheck_ready', False))}",
                f"joined_xy_proof_candidate_core_outcome={joined_xy_proof_preserving_candidate.get('core_outcome')}",
                f"joined_xy_proof_candidate_core_label_count={joined_xy_proof_preserving_candidate.get('core_label_count')}",
                f"joined_xy_proof_candidate_anchor_sweep_all_infeasible={bool(joined_xy_proof_preserving_candidate.get('anchor_sweep_all_infeasible', False))}",
                f"joined_xy_proof_candidate_standalone_pair_optimal={bool(joined_xy_proof_preserving_candidate.get('standalone_pair_optimal', False))}",
                f"joined_xy_proof_candidate_review_state_ready={bool(joined_xy_proof_preserving_candidate.get('row_domain_review_state_ready', False))}",
                f"reviewed_runtime_patch_exists={bool(joined_xy_proof_preserving_candidate.get('reviewed_runtime_patch_exists', False))}",
            ]
        )
    for entry in list(validation.get("rejected_samples", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "coordinate_rejection_sample="
            f"anchor={entry.get('anchor_idx')} "
            f"reason={entry.get('failure_reason') or entry.get('reason')} "
            f"status={entry.get('status')} "
            f"forced_slots={entry.get('forced_slot_field_count')}"
        )
    for entry in list(matrix.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "solver_matrix_entry="
            f"anchor={entry.get('anchor_idx')} "
            f"branching={entry.get('search_branching') or entry.get('branching')} "
            f"status={entry.get('status')} "
            f"wall={entry.get('wall_time')} "
            f"branches={entry.get('branches')} "
            f"conflicts={entry.get('conflicts')}"
        )
    for check in list(summary.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _coordinate_failure_count(failure_summary: Mapping[str, Any]) -> int:
    reason_counts = _mapping(failure_summary.get("failure_reason_counts"))
    return int(reason_counts.get("coordinate_validation_infeasible", 0))


def _coordinate_failure_samples(
    failure_summary: Mapping[str, Any],
    warm_start: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    samples = [
        dict(entry)
        for entry in list(warm_start.get("ghost_aware_coordinate_validation_rejection_samples", []))
        if isinstance(entry, Mapping)
    ]
    if samples:
        return samples
    return [
        dict(entry)
        for entry in list(failure_summary.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
        and str(entry.get("failure_reason", "")).startswith("coordinate_validation_")
    ]


def _recommendation(
    *,
    design_gate_passed: bool,
    rejected_count: int,
    matrix_infeasible_count: int,
    matrix_all_infeasible: bool,
    joined_xy_current_blocker: Mapping[str, Any],
) -> str:
    if bool(joined_xy_current_blocker.get("active", False)):
        return str(
            joined_xy_current_blocker.get(
                "recommendation",
                (
                    "Joined-XY now points at the current coordinate-validation / "
                    "ghost-aware start blocker; shrink that core before another B5A rerun."
                ),
            )
        )
    if design_gate_passed:
        return (
            "Coordinate-validation evidence is a strong B2 design candidate, "
            "but runtime promotion remains blocked until deterministic precheck tests and B5A rerun."
        )
    blockers: list[str] = []
    if rejected_count <= 0:
        blockers.append("coordinate validation rejection samples missing")
    if matrix_infeasible_count <= 0:
        blockers.append("forced-anchor infeasible matrix evidence missing")
    if not matrix_all_infeasible:
        blockers.append("forced-anchor matrix is mixed or incomplete")
    return "Design gate blocked: " + ", ".join(blockers or ["input evidence incomplete"])


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": str(status),
        "detail": str(detail),
    }


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not path.exists():
            return None, f"missing:{path}"
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return None, "json root is not an object"
        return payload, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


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


def _build_joined_xy_current_blocker(
    *,
    candidate_key: str,
    b5a_summary: Optional[Mapping[str, Any]],
    b5a_summary_error: Optional[str],
    b5a_summary_supported: bool,
    joined_xy_profile_probe: Optional[Mapping[str, Any]],
    joined_xy_profile_probe_error: Optional[str],
    joined_xy_profile_probe_supported: bool,
    joined_xy_delta_synthesis: Optional[Mapping[str, Any]],
    joined_xy_delta_synthesis_error: Optional[str],
    joined_xy_delta_supported: bool,
) -> Dict[str, Any]:
    top_blocker = _b5a_top_blocker_for_candidate(b5a_summary, candidate_key)
    proof_summary = _mapping(top_blocker.get("proof_summary"))
    master_last_solve = _mapping(proof_summary.get("master_last_solve"))
    start_failure = _mapping(proof_summary.get("master_start_failure_attribution"))
    blocker_subtype = str(top_blocker.get("blocker_subtype") or "")
    workspace_present = (
        isinstance(b5a_summary, Mapping)
        and b5a_summary_error is None
        and b5a_summary_supported
    )
    workspace_missing = b5a_summary is None and isinstance(b5a_summary_error, str) and b5a_summary_error.startswith("missing:")
    workspace_start_incompatible = (
        blocker_subtype == "master_start_incompatible_unknown"
    )

    profile_probe_status = _mapping(joined_xy_profile_probe.get("status")) if joined_xy_profile_probe else {}
    profile_probe_probe = _mapping(joined_xy_profile_probe.get("probe")) if joined_xy_profile_probe else {}
    best_terminal_entry = _mapping(profile_probe_probe.get("best_terminal_entry"))
    profile_probe_terminal_infeasible = (
        isinstance(joined_xy_profile_probe, Mapping)
        and joined_xy_profile_probe_error is None
        and joined_xy_profile_probe_supported
        and str(profile_probe_status.get("outcome")) == "coordinate_validation_infeasible"
        and str(best_terminal_entry.get("status")) == "INFEASIBLE"
    )
    profile_probe_missing = (
        joined_xy_profile_probe is None
        and isinstance(joined_xy_profile_probe_error, str)
        and joined_xy_profile_probe_error.startswith("missing:")
    )

    delta_status = _mapping(joined_xy_delta_synthesis.get("status")) if joined_xy_delta_synthesis else {}
    delta_evidence = _mapping(joined_xy_delta_synthesis.get("evidence")) if joined_xy_delta_synthesis else {}
    shrunk_core = _mapping(delta_evidence.get("anchor119_pair_x_core_synthesis"))
    no_ghost_space = _mapping(
        delta_evidence.get("anchor119_pair_x_no_ghost_space_synthesis")
    )
    delta_shrink_present = (
        isinstance(joined_xy_delta_synthesis, Mapping)
        and joined_xy_delta_synthesis_error is None
        and joined_xy_delta_supported
        and bool(delta_status.get("completed", False))
        and bool(shrunk_core)
    )
    delta_missing = (
        joined_xy_delta_synthesis is None
        and isinstance(joined_xy_delta_synthesis_error, str)
        and joined_xy_delta_synthesis_error.startswith("missing:")
    )
    coordinate_validation_infeasible_count = int(
        _mapping(start_failure.get("failure_reason_counts")).get(
            "coordinate_validation_infeasible", 0
        )
    )
    active = bool(
        workspace_start_incompatible
        and profile_probe_terminal_infeasible
        and delta_shrink_present
    )
    workspace_detail = (
        "joined-XY workspace summary loaded"
        if workspace_present
        else b5a_summary_error
        or (
            "unsupported source:"
            + str(_mapping(b5a_summary.get("metadata") if b5a_summary else {}).get("source"))
        )
    )
    workspace_start_incompatible_detail = (
        "workspace blocker is master_start_incompatible_unknown"
        if workspace_start_incompatible
        else f"blocker_subtype={blocker_subtype or 'none'}"
    )
    profile_probe_detail = (
        "joined-XY profile probe has terminal INFEASIBLE evidence"
        if profile_probe_terminal_infeasible
        else joined_xy_profile_probe_error
        or (
            "outcome="
            + str(profile_probe_status.get("outcome"))
            + "; best_terminal_status="
            + str(best_terminal_entry.get("status"))
        )
    )
    delta_detail = (
        "joined-XY delta synthesis shrank the blocker core"
        if delta_shrink_present
        else joined_xy_delta_synthesis_error
        or ("outcome=" + str(delta_status.get("outcome")))
    )
    recommendation = (
        "Current blocker is the joined-XY coordinate-validation / ghost-aware start gate: "
        "workspace B5A is conflictful UNKNOWN with master_start_incompatible attribution, "
        "anchor119 profile probe reaches terminal INFEASIBLE under deterministic profiles, "
        "and delta synthesis shrinks the core to protocol_planter_buckwheat_3_x_labels. "
        "Next turn that shrunk core into a proof-preserving precheck candidate; do not rerun "
        "B5A or final 168h yet."
    )
    return {
        "present": bool(workspace_present or profile_probe_terminal_infeasible or delta_shrink_present),
        "active": active,
        "workspace_present": workspace_present,
        "workspace_missing": workspace_missing,
        "workspace_detail": workspace_detail,
        "workspace_start_incompatible": workspace_start_incompatible,
        "workspace_start_incompatible_detail": workspace_start_incompatible_detail,
        "workspace_outcome": _mapping(b5a_summary.get("status") if b5a_summary else {}).get(
            "outcome"
        ),
        "blocker_subtype": blocker_subtype or None,
        "workspace_master_branches": int(master_last_solve.get("branches", 0) or 0),
        "workspace_master_conflicts": int(master_last_solve.get("conflicts", 0) or 0),
        "workspace_master_deterministic_time": master_last_solve.get(
            "deterministic_time"
        ),
        "coordinate_validation_infeasible_count": coordinate_validation_infeasible_count,
        "profile_probe_present": (
            isinstance(joined_xy_profile_probe, Mapping)
            and joined_xy_profile_probe_error is None
            and joined_xy_profile_probe_supported
        ),
        "profile_probe_missing": profile_probe_missing,
        "profile_probe_terminal_infeasible": profile_probe_terminal_infeasible,
        "profile_probe_detail": profile_probe_detail,
        "profile_probe_outcome": profile_probe_status.get("outcome"),
        "profile_probe_status_counts": dict(
            _mapping(profile_probe_status.get("status_counts"))
        ),
        "best_terminal_profile": best_terminal_entry.get("profile_id"),
        "delta_shrink_present": delta_shrink_present,
        "delta_missing": delta_missing,
        "delta_detail": delta_detail,
        "delta_outcome": delta_status.get("outcome"),
        "shrunk_core_outcome": shrunk_core.get("outcome"),
        "shrunk_core_label_count": int(shrunk_core.get("remaining_label_count", 0) or 0),
        "no_ghost_space_outcome": no_ghost_space.get("outcome"),
        "recommendation": recommendation if active else (
            "Joined-XY current blocker evidence is incomplete."
        ),
    }


def _b5a_top_blocker_for_candidate(
    b5a_summary: Optional[Mapping[str, Any]], candidate_key: str
) -> Mapping[str, Any]:
    if not isinstance(b5a_summary, Mapping):
        return {}
    triage = _mapping(b5a_summary.get("triage"))
    for entry in list(triage.get("top_blockers", [])):
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("candidate_key")) == str(candidate_key):
            return entry
    return {}


def _build_joined_xy_proof_preserving_candidate(
    *,
    anchor119_pair_x_core_synthesis: Optional[Mapping[str, Any]],
    anchor119_pair_x_core_synthesis_error: Optional[str],
    anchor119_pair_x_core_supported: bool,
    anchor119_pair_x_no_ghost_space_synthesis: Optional[Mapping[str, Any]],
    anchor119_pair_x_no_ghost_space_synthesis_error: Optional[str],
    anchor119_pair_x_no_ghost_space_supported: bool,
    order_implied_capacity_explanation: Optional[Mapping[str, Any]],
    order_implied_capacity_explanation_error: Optional[str],
    order_implied_capacity_supported: bool,
    anchor119_row_domain_runtime_patch_status: Optional[Mapping[str, Any]],
    anchor119_row_domain_runtime_patch_status_error: Optional[str],
    anchor119_row_domain_runtime_patch_status_supported: bool,
    joined_xy_current_blocker: Mapping[str, Any],
) -> Dict[str, Any]:
    core_present = (
        isinstance(anchor119_pair_x_core_synthesis, Mapping)
        and anchor119_pair_x_core_synthesis_error is None
        and anchor119_pair_x_core_supported
    )
    no_ghost_space_present = (
        isinstance(anchor119_pair_x_no_ghost_space_synthesis, Mapping)
        and anchor119_pair_x_no_ghost_space_synthesis_error is None
        and anchor119_pair_x_no_ghost_space_supported
    )
    order_capacity_present = (
        isinstance(order_implied_capacity_explanation, Mapping)
        and order_implied_capacity_explanation_error is None
        and order_implied_capacity_supported
    )
    runtime_patch_status_present = (
        isinstance(anchor119_row_domain_runtime_patch_status, Mapping)
        and anchor119_row_domain_runtime_patch_status_error is None
        and anchor119_row_domain_runtime_patch_status_supported
    )
    core_missing = (
        anchor119_pair_x_core_synthesis is None
        and isinstance(anchor119_pair_x_core_synthesis_error, str)
        and anchor119_pair_x_core_synthesis_error.startswith("missing:")
    )
    no_ghost_space_missing = (
        anchor119_pair_x_no_ghost_space_synthesis is None
        and isinstance(anchor119_pair_x_no_ghost_space_synthesis_error, str)
        and anchor119_pair_x_no_ghost_space_synthesis_error.startswith("missing:")
    )
    order_capacity_missing = (
        order_implied_capacity_explanation is None
        and isinstance(order_implied_capacity_explanation_error, str)
        and order_implied_capacity_explanation_error.startswith("missing:")
    )
    runtime_patch_status_missing = (
        anchor119_row_domain_runtime_patch_status is None
        and isinstance(anchor119_row_domain_runtime_patch_status_error, str)
        and anchor119_row_domain_runtime_patch_status_error.startswith("missing:")
    )

    core_status = (
        _mapping(anchor119_pair_x_core_synthesis.get("status"))
        if anchor119_pair_x_core_synthesis
        else {}
    )
    core_evidence = (
        _mapping(anchor119_pair_x_core_synthesis.get("evidence"))
        if anchor119_pair_x_core_synthesis
        else {}
    )
    no_ghost_space_status = (
        _mapping(anchor119_pair_x_no_ghost_space_synthesis.get("status"))
        if anchor119_pair_x_no_ghost_space_synthesis
        else {}
    )
    no_ghost_space_evidence = (
        _mapping(anchor119_pair_x_no_ghost_space_synthesis.get("evidence"))
        if anchor119_pair_x_no_ghost_space_synthesis
        else {}
    )
    anchor_sweep_all = _mapping(no_ghost_space_evidence.get("anchor_sweep_all"))
    standalone_pair_ladder = _mapping(
        no_ghost_space_evidence.get("standalone_pair_ladder")
    )
    order_capacity_geometry = (
        _mapping(order_implied_capacity_explanation.get("geometry"))
        if order_implied_capacity_explanation
        else {}
    )
    runtime_patch_status = (
        _mapping(anchor119_row_domain_runtime_patch_status.get("status"))
        if anchor119_row_domain_runtime_patch_status
        else {}
    )
    core_minimality = _mapping(core_evidence.get("minimality_10s"))
    _mapping(no_ghost_space_evidence.get("minimality_10s"))
    anchor_sweep_status_counts = _mapping(
        anchor_sweep_all.get("status_counts")
        or no_ghost_space_evidence.get("anchor_sweep_status_counts")
    )

    core_label_count = len(list(core_evidence.get("remaining_labels", [])))
    minimality_ready = bool(
        core_present
        and bool(core_minimality.get("all3_infeasible", False))
        and int(core_minimality.get("proper_subsets_terminal_infeasible", -1)) == 0
    )
    anchor_sweep_all_infeasible = bool(
        no_ghost_space_present
        and int(anchor_sweep_status_counts.get("INFEASIBLE", 0)) > 0
        and len(anchor_sweep_status_counts) == 1
    )
    standalone_pair_status = str(
        standalone_pair_ladder.get("full_pair_all_constraints_status")
        or no_ghost_space_evidence.get("standalone_pair_status")
    )
    standalone_pair_optimal = standalone_pair_status == "OPTIMAL"
    design_ready = bool(
        joined_xy_current_blocker.get("active", False)
        and core_present
        and no_ghost_space_present
        and order_capacity_present
        and minimality_ready
        and anchor_sweep_all_infeasible
        and standalone_pair_optimal
        and core_label_count == 3
    )
    row_domain_runtime_patch_ready = bool(
        design_ready
        and runtime_patch_status_present
        and bool(runtime_patch_status.get("patch_status_ready", False))
        and bool(runtime_patch_status.get("runtime_patch_authored_in_code", False))
        and bool(runtime_patch_status.get("authored_but_not_enableable", False))
        and not bool(runtime_patch_status.get("runtime_enablement_allowed", True))
    )
    extraction_recommendation = (
        "The joined-XY shrunk core is now specific enough for proof-preserving extraction: "
        "protocol_core + planter_buckwheat 3 x-labels are jointly terminal in the anchored full model, "
        "proper subsets are not terminal, the 3-label core kills the full ghost-domain sweep, "
        "but the standalone pair remains OPTIMAL. Next derive a no-solve certificate or row-domain "
        "extraction that proves these labels imply coordinate_validation_infeasible without using "
        "the solver outcome itself."
    )
    review_gate_recommendation = (
        "Joined-XY proof-preserving extraction has advanced to an authored anchor119 "
        "row-domain runtime patch, but the patch is still disabled and not enableable. "
        "The next gate is reviewed_runtime_patch_exists=false / reviewed enablement, "
        "not another B5A workspace rerun or production acceptance."
    )
    return {
        "present": bool(core_present or no_ghost_space_present or order_capacity_present),
        "design_ready": design_ready,
        "proof_preserving_precheck_ready": row_domain_runtime_patch_ready,
        "core_present": core_present,
        "core_missing": core_missing,
        "core_detail": (
            "anchor119 pair-x core synthesis loaded"
            if core_present
            else anchor119_pair_x_core_synthesis_error
            or ("unsupported source:" + str(_mapping(anchor119_pair_x_core_synthesis.get("metadata") if anchor119_pair_x_core_synthesis else {}).get("source")))
        ),
        "core_outcome": core_status.get("outcome"),
        "core_label_count": int(core_label_count),
        "minimality_ready": minimality_ready,
        "minimality_detail": (
            "all3_infeasible=true and proper subsets stay non-terminal"
            if minimality_ready
            else (
                "all3_infeasible="
                + str(core_minimality.get("all3_infeasible"))
                + "; proper_subsets_terminal_infeasible="
                + str(core_minimality.get("proper_subsets_terminal_infeasible"))
            )
        ),
        "no_ghost_space_present": no_ghost_space_present,
        "no_ghost_space_missing": no_ghost_space_missing,
        "anchor_sweep_all_infeasible": anchor_sweep_all_infeasible,
        "anchor_sweep_detail": (
            "three-label core eliminates the entire 67x13 ghost-domain sweep"
            if anchor_sweep_all_infeasible
            else f"anchor_sweep_status_counts={dict(anchor_sweep_status_counts)}"
        ),
        "standalone_pair_optimal": standalone_pair_optimal,
        "standalone_pair_detail": (
            "standalone pair remains OPTIMAL"
            if standalone_pair_optimal
            else f"standalone_pair_status={standalone_pair_status or None}"
        ),
        "latest_followup_outcome": no_ghost_space_status.get("latest_followup_outcome"),
        "order_capacity_present": order_capacity_present,
        "order_capacity_missing": order_capacity_missing,
        "order_capacity_detail": (
            "order-implied capacity explanation loaded"
            if order_capacity_present
            else order_implied_capacity_explanation_error
            or ("unsupported source:" + str(_mapping(order_implied_capacity_explanation.get("metadata") if order_implied_capacity_explanation else {}).get("source")))
        ),
        "free_ghost_infeasible_threshold_slots": order_capacity_geometry.get(
            "free_ghost_infeasible_threshold_slots"
        ),
        "fixed_anchor_infeasible_threshold_slots": order_capacity_geometry.get(
            "anchor119_fixed_infeasible_threshold_slots"
        ),
        "row_domain_runtime_patch_status_present": runtime_patch_status_present,
        "row_domain_runtime_patch_status_missing": runtime_patch_status_missing,
        "row_domain_runtime_patch_status_detail": (
            "anchor119 row-domain runtime patch status loaded"
            if runtime_patch_status_present
            else anchor119_row_domain_runtime_patch_status_error
            or (
                "unsupported source:"
                + str(
                    _mapping(
                        anchor119_row_domain_runtime_patch_status.get("metadata")
                        if anchor119_row_domain_runtime_patch_status
                        else {}
                    ).get("source")
                )
            )
        ),
        "row_domain_runtime_patch_ready": row_domain_runtime_patch_ready,
        "runtime_patch_authored_in_code": bool(
            runtime_patch_status.get("runtime_patch_authored_in_code", False)
        ),
        "authored_but_not_enableable": bool(
            runtime_patch_status.get("authored_but_not_enableable", False)
        ),
        "runtime_enablement_allowed": bool(
            runtime_patch_status.get("runtime_enablement_allowed", False)
        ),
        "recommendation": (
            review_gate_recommendation
            if row_domain_runtime_patch_ready
            else extraction_recommendation
            if design_ready
            else "Joined-XY proof-preserving candidate evidence is incomplete."
        ),
    }

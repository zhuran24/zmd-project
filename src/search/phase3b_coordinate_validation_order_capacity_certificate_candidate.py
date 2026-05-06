from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

ORDER_CAPACITY_CERTIFICATE_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_order_capacity_certificate_candidate_v1"
)
PAIR_X_CORE_SYNTHESIS_SOURCE = "phase3b_anchor119_pair_x_core_synthesis_v1"
PAIR_X_NO_GHOST_SPACE_SYNTHESIS_SOURCE = (
    "phase3b_anchor119_pair_x_no_ghost_space_synthesis_v1"
)
ORDER_CAPACITY_EXPLANATION_SOURCE = (
    "phase3b_coordinate_validation_order_implied_capacity_explanation_v1"
)

DEFAULT_PAIR_X_CORE_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_core_synthesis_20260423/"
    "anchor119_pair_x_core_synthesis.json"
)
DEFAULT_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_no_ghost_space_synthesis_20260423/"
    "anchor119_pair_x_no_ghost_space_synthesis.json"
)
DEFAULT_ORDER_CAPACITY_EXPLANATION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_order_implied_capacity_explanation_20260423/"
    "order_implied_capacity_explanation.json"
)


def build_phase3b_coordinate_validation_order_capacity_certificate_candidate(
    project_root: Path,
    *,
    pair_x_core_synthesis_path: Optional[Path] = None,
    pair_x_no_ghost_space_synthesis_path: Optional[Path] = None,
    order_capacity_explanation_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    core_path = _resolve_path(
        project_root,
        pair_x_core_synthesis_path
        if pair_x_core_synthesis_path is not None
        else DEFAULT_PAIR_X_CORE_SYNTHESIS_PATH,
    )
    no_ghost_path = _resolve_path(
        project_root,
        pair_x_no_ghost_space_synthesis_path
        if pair_x_no_ghost_space_synthesis_path is not None
        else DEFAULT_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH,
    )
    explanation_path = _resolve_path(
        project_root,
        order_capacity_explanation_path
        if order_capacity_explanation_path is not None
        else DEFAULT_ORDER_CAPACITY_EXPLANATION_PATH,
    )

    core_report, core_error = _load_json_mapping(core_path)
    no_ghost_report, no_ghost_error = _load_json_mapping(no_ghost_path)
    explanation_report, explanation_error = _load_json_mapping(explanation_path)

    core_meta = _mapping(core_report.get("metadata")) if core_report else {}
    no_ghost_meta = _mapping(no_ghost_report.get("metadata")) if no_ghost_report else {}
    explanation_meta = _mapping(explanation_report.get("metadata")) if explanation_report else {}

    core_status = _mapping(core_report.get("status")) if core_report else {}
    core_evidence = _mapping(core_report.get("evidence")) if core_report else {}
    no_ghost_status = _mapping(no_ghost_report.get("status")) if no_ghost_report else {}
    no_ghost_evidence = _mapping(no_ghost_report.get("evidence")) if no_ghost_report else {}
    explanation_geometry = _mapping(explanation_report.get("geometry")) if explanation_report else {}
    explanation_interpretation = _mapping(
        explanation_report.get("interpretation")
    ) if explanation_report else {}

    remaining_labels = [
        dict(entry)
        for entry in list(core_evidence.get("remaining_labels", []))
        if isinstance(entry, Mapping)
    ]
    minimality = _mapping(core_evidence.get("minimality_10s"))
    anchor_sweep_all = _mapping(no_ghost_evidence.get("anchor_sweep_all"))
    anchor_sweep_status_counts = _mapping(anchor_sweep_all.get("status_counts"))
    standalone_pair_ladder = _mapping(no_ghost_evidence.get("standalone_pair_ladder"))

    capacity_entries = [
        dict(entry)
        for entry in list(explanation_report.get("entries", []) if explanation_report else [])
        if isinstance(entry, Mapping)
    ]
    exceeded_entries = [
        entry for entry in capacity_entries if bool(entry.get("free_ghost_capacity_exceeded", False))
    ]
    exceeded_infeasible_entries = [
        entry for entry in exceeded_entries if str(entry.get("observed_status")) == "INFEASIBLE"
    ]
    non_exceeded_entries = [
        entry for entry in capacity_entries if not bool(entry.get("free_ghost_capacity_exceeded", False))
    ]
    non_exceeded_unknown_entries = [
        entry for entry in non_exceeded_entries if str(entry.get("observed_status")) == "UNKNOWN"
    ]
    exceeded_slot_indices = [
        int(entry.get("slot_index"))
        for entry in exceeded_infeasible_entries
        if entry.get("slot_index") is not None
    ]
    non_exceeded_slot_indices = [
        int(entry.get("slot_index"))
        for entry in non_exceeded_unknown_entries
        if entry.get("slot_index") is not None
    ]

    core_present = bool(
        core_report is not None
        and core_error is None
        and core_meta.get("source") == PAIR_X_CORE_SYNTHESIS_SOURCE
    )
    no_ghost_present = bool(
        no_ghost_report is not None
        and no_ghost_error is None
        and no_ghost_meta.get("source") == PAIR_X_NO_GHOST_SPACE_SYNTHESIS_SOURCE
    )
    explanation_present = bool(
        explanation_report is not None
        and explanation_error is None
        and explanation_meta.get("source") == ORDER_CAPACITY_EXPLANATION_SOURCE
    )
    core_shape_ready = (
        str(core_status.get("outcome"))
        == "anchor119_fixed_conflict_shrunk_to_protocol_planter_buckwheat_3_x_labels"
        and len(remaining_labels) == 3
    )
    minimality_ready = bool(
        minimality.get("all3_infeasible", False)
        and int(minimality.get("proper_subsets_terminal_infeasible", -1)) == 0
    )
    anchor_sweep_all_infeasible = bool(
        anchor_sweep_status_counts
        and int(anchor_sweep_status_counts.get("INFEASIBLE", 0)) > 0
        and len(anchor_sweep_status_counts) == 1
    )
    standalone_pair_optimal = (
        str(standalone_pair_ladder.get("full_pair_all_constraints_status")) == "OPTIMAL"
    )
    threshold_ready = bool(
        int(explanation_geometry.get("free_ghost_infeasible_threshold_slots", 0) or 0) == 15
        and int(explanation_geometry.get("anchor119_fixed_infeasible_threshold_slots", 0) or 0)
        == 14
    )
    witnessed_transition_ready = bool(
        exceeded_slot_indices == [14, 15, 16] and non_exceeded_slot_indices[-1:] == [13]
    )
    design_gate_passed = bool(
        core_present
        and no_ghost_present
        and explanation_present
        and core_shape_ready
        and minimality_ready
        and anchor_sweep_all_infeasible
        and standalone_pair_optimal
        and threshold_ready
        and witnessed_transition_ready
    )

    candidate = _mapping(core_report.get("candidate")) if core_report else {}

    checks = [
        _check(
            "pair_x_core_synthesis_present",
            "pass" if core_present else "fail",
            "pair-x core synthesis loaded"
            if core_present
            else core_error or f"missing:{_display_path(project_root, core_path)}",
        ),
        _check(
            "pair_x_no_ghost_space_synthesis_present",
            "pass" if no_ghost_present else "fail",
            "pair-x no-ghost-space synthesis loaded"
            if no_ghost_present
            else no_ghost_error or f"missing:{_display_path(project_root, no_ghost_path)}",
        ),
        _check(
            "order_capacity_explanation_present",
            "pass" if explanation_present else "fail",
            "order-implied capacity explanation loaded"
            if explanation_present
            else explanation_error
            or f"missing:{_display_path(project_root, explanation_path)}",
        ),
        _check(
            "three_label_core_shape",
            "pass" if core_shape_ready else "fail",
            f"outcome={core_status.get('outcome')}; label_count={len(remaining_labels)}",
        ),
        _check(
            "three_label_core_minimality",
            "pass" if minimality_ready else "fail",
            (
                f"all3_infeasible={minimality.get('all3_infeasible')}; "
                f"proper_subsets_terminal_infeasible={minimality.get('proper_subsets_terminal_infeasible')}"
            ),
        ),
        _check(
            "full_ghost_domain_eliminated",
            "pass" if anchor_sweep_all_infeasible else "fail",
            f"anchor_sweep_status_counts={dict(anchor_sweep_status_counts)}",
        ),
        _check(
            "standalone_pair_not_self_contradictory",
            "pass" if standalone_pair_optimal else "fail",
            "standalone pair remains OPTIMAL"
            if standalone_pair_optimal
            else f"full_pair_all_constraints_status={standalone_pair_ladder.get('full_pair_all_constraints_status')}",
        ),
        _check(
            "order_capacity_threshold_shape",
            "pass" if threshold_ready else "fail",
            (
                f"free_ghost_threshold={explanation_geometry.get('free_ghost_infeasible_threshold_slots')}; "
                f"fixed_anchor_threshold={explanation_geometry.get('anchor119_fixed_infeasible_threshold_slots')}"
            ),
        ),
        _check(
            "order_capacity_transition_witnessed",
            "pass" if witnessed_transition_ready else "fail",
            f"non_exceeded_unknown_slots={non_exceeded_slot_indices}; exceeded_infeasible_slots={exceeded_slot_indices}",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "certificate candidate is still diagnostic-only; derive a proof-preserving "
                "no-solve predicate or row-domain extraction before runtime promotion"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ORDER_CAPACITY_CERTIFICATE_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_order_capacity_certificate_candidate_not_proof_source"
            ),
            "proof_source": False,
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "pair_x_core_synthesis": _display_path(project_root, core_path),
            "pair_x_no_ghost_space_synthesis": _display_path(project_root, no_ghost_path),
            "order_capacity_explanation": _display_path(project_root, explanation_path),
        },
        "candidate": dict(candidate),
        "gate": {
            "design_gate_passed": bool(design_gate_passed),
            "proof_preserving_precheck_ready": False,
            "certificate_shape": "order_implied_x_overlap_upper_strip",
            "recommendation": _recommendation(design_gate_passed),
            "next_paths": [
                "no_solve_certificate",
                "row_domain_extraction",
            ],
        },
        "evidence": {
            "three_label_core": remaining_labels,
            "core_outcome": core_status.get("outcome"),
            "minimality": dict(minimality),
            "anchor_sweep_status_counts": dict(anchor_sweep_status_counts),
            "standalone_pair_full_status": standalone_pair_ladder.get(
                "full_pair_all_constraints_status"
            ),
            "free_ghost_infeasible_threshold_slots": int(
                explanation_geometry.get("free_ghost_infeasible_threshold_slots", 0) or 0
            ),
            "fixed_anchor_infeasible_threshold_slots": int(
                explanation_geometry.get("anchor119_fixed_infeasible_threshold_slots", 0) or 0
            ),
            "exceeded_infeasible_slot_indices": exceeded_slot_indices,
            "highest_non_exceeded_unknown_slot_index": (
                max(non_exceeded_slot_indices) if non_exceeded_slot_indices else None
            ),
            "why_x_overlap_is_unavoidable": explanation_geometry.get(
                "why_x_overlap_is_unavoidable"
            ),
            "free_ghost_explanation": explanation_interpretation.get(
                "free_ghost_x0_slots_14_16"
            ),
            "fixed_anchor_distinction": explanation_interpretation.get(
                "fixed_anchor119_distinction"
            ),
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_order_capacity_certificate_candidate_markdown(
    report: Mapping[str, Any]
) -> str:
    candidate = _mapping(report.get("candidate"))
    gate = _mapping(report.get("gate"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "# Phase 3B Coordinate-Validation Order-Capacity Certificate Candidate",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        f"- Formulation profile: {candidate.get('formulation_profile')}",
        f"- Design gate passed: {bool(gate.get('design_gate_passed', False))}",
        f"- Proof-preserving precheck ready: {bool(gate.get('proof_preserving_precheck_ready', False))}",
        f"- Certificate shape: {gate.get('certificate_shape')}",
        f"- Recommendation: {gate.get('recommendation')}",
        "",
        "## Evidence",
        "",
        f"- Core outcome: {evidence.get('core_outcome')}",
        f"- Core label count: {len(list(evidence.get('three_label_core', [])))}",
        f"- Anchor sweep status counts: {evidence.get('anchor_sweep_status_counts')}",
        f"- Standalone pair full status: {evidence.get('standalone_pair_full_status')}",
        f"- Free-ghost infeasible threshold slots: {evidence.get('free_ghost_infeasible_threshold_slots')}",
        f"- Fixed-anchor infeasible threshold slots: {evidence.get('fixed_anchor_infeasible_threshold_slots')}",
        f"- Exceeded infeasible slot indices: {evidence.get('exceeded_infeasible_slot_indices')}",
        f"- Highest non-exceeded unknown slot index: {evidence.get('highest_non_exceeded_unknown_slot_index')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
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


def render_phase3b_coordinate_validation_order_capacity_certificate_candidate_text(
    report: Mapping[str, Any]
) -> str:
    gate = _mapping(report.get("gate"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "Phase 3B coordinate-validation order-capacity certificate candidate",
        f"design_gate_passed={bool(gate.get('design_gate_passed', False))}",
        f"proof_preserving_precheck_ready={bool(gate.get('proof_preserving_precheck_ready', False))}",
        f"certificate_shape={gate.get('certificate_shape')}",
        f"core_outcome={evidence.get('core_outcome')}",
        f"core_label_count={len(list(evidence.get('three_label_core', [])))}",
        f"anchor_sweep_status_counts={evidence.get('anchor_sweep_status_counts')}",
        f"standalone_pair_full_status={evidence.get('standalone_pair_full_status')}",
        f"exceeded_infeasible_slot_indices={evidence.get('exceeded_infeasible_slot_indices')}",
        f"highest_non_exceeded_unknown_slot_index={evidence.get('highest_non_exceeded_unknown_slot_index')}",
        f"recommendation={gate.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"check id={check.get('check_id')} status={check.get('status')} detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _recommendation(design_gate_passed: bool) -> str:
    if design_gate_passed:
        return (
            "No-solve order-capacity certificate candidate is ready as a proof-preserving "
            "extraction target: encode the order-implied x-overlap / upper-strip threshold "
            "without relying on solver-terminal evidence, then validate it as guarded/default-off."
        )
    return (
        "Certificate candidate is incomplete; repair the three-label core / anchor-sweep / "
        "order-threshold evidence before extraction work."
    )


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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

ROW_DOMAIN_EXTRACTION_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_row_domain_extraction_candidate_v1"
)
PROOF_PRESERVING_EXTRACTION_SPEC_SOURCE = (
    "phase3b_coordinate_validation_proof_preserving_extraction_spec_v1"
)
ORDER_CAPACITY_CERTIFICATE_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_order_capacity_certificate_candidate_v1"
)
PAIR_X_CORE_DOMAIN_INSPECTION_SOURCE = (
    "phase3b_anchor119_pair_x_core_domain_inspection_v1"
)

DEFAULT_EXTRACTION_SPEC_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_proof_preserving_extraction_spec_20260423/"
    "proof_preserving_extraction_spec.json"
)
DEFAULT_ORDER_CAPACITY_CERTIFICATE_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_order_capacity_certificate_candidate_20260423/"
    "order_capacity_certificate_candidate.json"
)
DEFAULT_PAIR_X_CORE_DOMAIN_INSPECTION_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_core_domain_inspection_20260423/"
    "anchor119_pair_x_core_domain_inspection.json"
)


def build_phase3b_coordinate_validation_row_domain_extraction_candidate(
    project_root: Path,
    *,
    extraction_spec_path: Optional[Path] = None,
    order_capacity_certificate_candidate_path: Optional[Path] = None,
    pair_x_core_domain_inspection_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    extraction_spec_resolved = _resolve_path(
        project_root,
        extraction_spec_path
        if extraction_spec_path is not None
        else DEFAULT_EXTRACTION_SPEC_PATH,
    )
    certificate_resolved = _resolve_path(
        project_root,
        order_capacity_certificate_candidate_path
        if order_capacity_certificate_candidate_path is not None
        else DEFAULT_ORDER_CAPACITY_CERTIFICATE_CANDIDATE_PATH,
    )
    domain_inspection_resolved = _resolve_path(
        project_root,
        pair_x_core_domain_inspection_path
        if pair_x_core_domain_inspection_path is not None
        else DEFAULT_PAIR_X_CORE_DOMAIN_INSPECTION_PATH,
    )

    extraction_spec, extraction_error = _load_json_mapping(extraction_spec_resolved)
    certificate, certificate_error = _load_json_mapping(certificate_resolved)
    domain_inspection, domain_error = _load_json_mapping(domain_inspection_resolved)

    extraction_meta = _mapping(extraction_spec.get("metadata")) if extraction_spec else {}
    certificate_meta = _mapping(certificate.get("metadata")) if certificate else {}
    domain_meta = _mapping(domain_inspection.get("metadata")) if domain_inspection else {}

    extraction_status = _mapping(extraction_spec.get("status")) if extraction_spec else {}
    bridge_gap = _mapping(extraction_spec.get("bridge_gap")) if extraction_spec else {}
    certificate_evidence = _mapping(certificate.get("evidence")) if certificate else {}
    candidate = _mapping(certificate.get("candidate")) if certificate else {}

    slot_details = [
        dict(entry)
        for entry in list(domain_inspection.get("slot_details", []) if domain_inspection else [])
        if isinstance(entry, Mapping)
    ]
    planter_order_implications = [
        dict(entry)
        for entry in list(
            domain_inspection.get("planter_order_implications", [])
            if domain_inspection
            else []
        )
        if isinstance(entry, Mapping)
    ]
    notes = _mapping(domain_inspection.get("notes")) if domain_inspection else {}

    extraction_spec_present = bool(
        extraction_spec is not None
        and extraction_error is None
        and extraction_meta.get("source") == PROOF_PRESERVING_EXTRACTION_SPEC_SOURCE
    )
    certificate_present = bool(
        certificate is not None
        and certificate_error is None
        and certificate_meta.get("source")
        == ORDER_CAPACITY_CERTIFICATE_CANDIDATE_SOURCE
    )
    domain_inspection_present = bool(
        domain_inspection is not None
        and domain_error is None
        and domain_meta.get("source") == PAIR_X_CORE_DOMAIN_INSPECTION_SOURCE
    )

    extraction_path_is_row_domain = (
        extraction_status.get("recommended_next_path") == "row_domain_extraction"
    )
    bridge_gap_present = bool(bridge_gap.get("anchored_case_bridge_missing", False))
    all_core_slots_overlap_ghost = bool(
        slot_details and all(bool(slot.get("x_overlaps_ghost", False)) for slot in slot_details)
    )
    ghost_avoiding_counts = [
        len(list(slot.get("ghost_avoiding_y_values", [])))
        for slot in slot_details
    ]
    all_core_slots_have_ghost_avoiding_rows = bool(
        ghost_avoiding_counts and all(count > 0 for count in ghost_avoiding_counts)
    )
    planter_order_implication_count = int(len(planter_order_implications))
    all_planter_order_overlap_ghost = bool(
        planter_order_implications
        and all(
            bool(entry.get("all_allowed_x_overlap_ghost", False))
            for entry in planter_order_implications
        )
    )
    implied_fixed_slots = [
        int(entry.get("slot_index"))
        for entry in planter_order_implications
        if entry.get("implied_x_fixed") is not None
    ]
    design_gate_passed = bool(
        extraction_spec_present
        and certificate_present
        and domain_inspection_present
        and extraction_path_is_row_domain
        and bridge_gap_present
        and all_core_slots_overlap_ghost
        and all_core_slots_have_ghost_avoiding_rows
        and planter_order_implication_count >= 1
        and all_planter_order_overlap_ghost
    )

    checks = [
        _check(
            "extraction_spec_present",
            "pass" if extraction_spec_present else "fail",
            "proof-preserving extraction spec loaded"
            if extraction_spec_present
            else extraction_error
            or f"missing:{_display_path(project_root, extraction_spec_resolved)}",
        ),
        _check(
            "recommended_next_path_is_row_domain_extraction",
            "pass" if extraction_path_is_row_domain else "fail",
            f"recommended_next_path={extraction_status.get('recommended_next_path')}",
        ),
        _check(
            "anchored_case_bridge_missing",
            "pass" if bridge_gap_present else "fail",
            str(bridge_gap.get("reason") or "bridge gap not present"),
        ),
        _check(
            "order_capacity_certificate_present",
            "pass" if certificate_present else "fail",
            "order-capacity certificate candidate loaded"
            if certificate_present
            else certificate_error
            or f"missing:{_display_path(project_root, certificate_resolved)}",
        ),
        _check(
            "pair_x_core_domain_inspection_present",
            "pass" if domain_inspection_present else "fail",
            "pair-x core domain inspection loaded"
            if domain_inspection_present
            else domain_error
            or f"missing:{_display_path(project_root, domain_inspection_resolved)}",
        ),
        _check(
            "all_core_slots_overlap_ghost",
            "pass" if all_core_slots_overlap_ghost else "fail",
            f"slot_count={len(slot_details)}",
        ),
        _check(
            "all_core_slots_have_ghost_avoiding_rows",
            "pass" if all_core_slots_have_ghost_avoiding_rows else "fail",
            f"ghost_avoiding_counts={ghost_avoiding_counts}",
        ),
        _check(
            "planter_order_implications_overlap_ghost",
            "pass" if all_planter_order_overlap_ghost else "fail",
            f"planter_order_implication_count={planter_order_implication_count}",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "row-domain extraction candidate is still diagnostic-only; derive the actual "
                "deterministic row-domain/count witness before runtime promotion"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ROW_DOMAIN_EXTRACTION_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_row_domain_extraction_candidate_not_proof_source"
            ),
            "solver_invoked": False,
            "proof_source": False,
        },
        "paths": {
            "project_root": str(project_root),
            "extraction_spec": _display_path(project_root, extraction_spec_resolved),
            "order_capacity_certificate_candidate": _display_path(
                project_root, certificate_resolved
            ),
            "pair_x_core_domain_inspection": _display_path(
                project_root, domain_inspection_resolved
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "design_gate_passed": bool(design_gate_passed),
            "runtime_promotion_ready": False,
            "recommended_next_step": "implement_row_domain_extraction_witness",
            "recommendation": _recommendation(design_gate_passed),
        },
        "evidence": {
            "core_slot_count": len(slot_details),
            "all_core_slots_overlap_ghost": all_core_slots_overlap_ghost,
            "ghost_avoiding_y_counts": ghost_avoiding_counts,
            "planter_order_implication_count": planter_order_implication_count,
            "all_planter_order_overlap_ghost": all_planter_order_overlap_ghost,
            "implied_fixed_slots": implied_fixed_slots,
            "free_ghost_threshold": certificate_evidence.get(
                "free_ghost_infeasible_threshold_slots"
            ),
            "fixed_anchor_threshold": certificate_evidence.get(
                "fixed_anchor_infeasible_threshold_slots"
            ),
            "highest_non_exceeded_unknown_slot_index": certificate_evidence.get(
                "highest_non_exceeded_unknown_slot_index"
            ),
            "exceeded_infeasible_slot_indices": certificate_evidence.get(
                "exceeded_infeasible_slot_indices"
            ),
            "order_key_scale_x": notes.get("order_key_scale_x"),
            "order_key_scale_y": notes.get("order_key_scale_y"),
            "domain_notes": notes.get("interpretation"),
        },
        "required_outputs": list(bridge_gap.get("required_outputs", [])),
        "checks": checks,
    }


def render_phase3b_coordinate_validation_row_domain_extraction_candidate_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "# Phase 3B Coordinate-Validation Row-Domain Extraction Candidate",
        "",
        f"- Design gate passed: {bool(status.get('design_gate_passed', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Recommended next step: {status.get('recommended_next_step')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Evidence",
        "",
        f"- Core slot count: {evidence.get('core_slot_count')}",
        f"- All core slots overlap ghost: {evidence.get('all_core_slots_overlap_ghost')}",
        f"- Ghost-avoiding y counts: {evidence.get('ghost_avoiding_y_counts')}",
        f"- Planter order implication count: {evidence.get('planter_order_implication_count')}",
        f"- All planter order implications overlap ghost: {evidence.get('all_planter_order_overlap_ghost')}",
        f"- Implied fixed slots: {evidence.get('implied_fixed_slots')}",
        f"- Free-ghost threshold: {evidence.get('free_ghost_threshold')}",
        f"- Fixed-anchor threshold: {evidence.get('fixed_anchor_threshold')}",
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


def render_phase3b_coordinate_validation_row_domain_extraction_candidate_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "Phase 3B coordinate-validation row-domain extraction candidate",
        f"design_gate_passed={bool(status.get('design_gate_passed', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"recommended_next_step={status.get('recommended_next_step')}",
        f"core_slot_count={evidence.get('core_slot_count')}",
        f"ghost_avoiding_y_counts={evidence.get('ghost_avoiding_y_counts')}",
        f"planter_order_implication_count={evidence.get('planter_order_implication_count')}",
        f"implied_fixed_slots={evidence.get('implied_fixed_slots')}",
        f"recommendation={status.get('recommendation')}",
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
            "Row-domain extraction candidate is ready: extract the deterministic row/count "
            "witness for the three-label core and map it back to the anchored B5A case before "
            "any workspace rerun."
        )
    return "Row-domain extraction candidate is incomplete; repair prerequisite evidence first."


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

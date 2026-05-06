from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

PROOF_PRESERVING_EXTRACTION_SPEC_SOURCE = (
    "phase3b_coordinate_validation_proof_preserving_extraction_spec_v1"
)
PRECHECK_CANDIDATE_SOURCE = "phase3b_coordinate_validation_precheck_candidate_v2"
ORDER_CAPACITY_CERTIFICATE_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_order_capacity_certificate_candidate_v1"
)
DEFAULT_PRECHECK_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_precheck_candidate/precheck_candidate.json"
)
DEFAULT_ORDER_CAPACITY_CERTIFICATE_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_order_capacity_certificate_candidate_20260423/"
    "order_capacity_certificate_candidate.json"
)


def build_phase3b_coordinate_validation_proof_preserving_extraction_spec(
    project_root: Path,
    *,
    precheck_candidate_path: Optional[Path] = None,
    order_capacity_certificate_candidate_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    precheck_path = _resolve_path(
        project_root,
        precheck_candidate_path
        if precheck_candidate_path is not None
        else DEFAULT_PRECHECK_CANDIDATE_PATH,
    )
    certificate_path = _resolve_path(
        project_root,
        order_capacity_certificate_candidate_path
        if order_capacity_certificate_candidate_path is not None
        else DEFAULT_ORDER_CAPACITY_CERTIFICATE_CANDIDATE_PATH,
    )

    precheck_report, precheck_error = _load_json_mapping(precheck_path)
    certificate_report, certificate_error = _load_json_mapping(certificate_path)
    precheck_meta = _mapping(precheck_report.get("metadata")) if precheck_report else {}
    certificate_meta = _mapping(certificate_report.get("metadata")) if certificate_report else {}
    precheck_gate = _mapping(precheck_report.get("gate")) if precheck_report else {}
    current_blocker = (
        _mapping(precheck_report.get("joined_xy_current_blocker"))
        if precheck_report
        else {}
    )
    proof_candidate = (
        _mapping(precheck_report.get("joined_xy_proof_preserving_candidate"))
        if precheck_report
        else {}
    )
    certificate_gate = _mapping(certificate_report.get("gate")) if certificate_report else {}
    certificate_evidence = (
        _mapping(certificate_report.get("evidence")) if certificate_report else {}
    )
    candidate = _mapping(precheck_report.get("candidate")) if precheck_report else {}

    precheck_present = bool(
        precheck_report is not None
        and precheck_error is None
        and precheck_meta.get("source") == PRECHECK_CANDIDATE_SOURCE
    )
    certificate_present = bool(
        certificate_report is not None
        and certificate_error is None
        and certificate_meta.get("source") == ORDER_CAPACITY_CERTIFICATE_CANDIDATE_SOURCE
    )
    current_blocker_active = bool(current_blocker.get("active", False))
    proof_candidate_design_ready = bool(proof_candidate.get("design_ready", False))
    certificate_design_gate_passed = bool(certificate_gate.get("design_gate_passed", False))
    certificate_is_free_ghost_local = (
        certificate_gate.get("certificate_shape") == "order_implied_x_overlap_upper_strip"
    )
    standalone_pair_optimal = bool(
        str(certificate_evidence.get("standalone_pair_full_status")) == "OPTIMAL"
    )
    fixed_anchor_threshold = int(
        certificate_evidence.get("fixed_anchor_infeasible_threshold_slots", 0) or 0
    )
    free_ghost_threshold = int(
        certificate_evidence.get("free_ghost_infeasible_threshold_slots", 0) or 0
    )
    anchored_case_bridge_missing = bool(
        current_blocker_active
        and certificate_design_gate_passed
        and certificate_is_free_ghost_local
        and standalone_pair_optimal
    )
    recommended_next_path = (
        "row_domain_extraction"
        if anchored_case_bridge_missing
        else "no_solve_certificate"
        if certificate_design_gate_passed
        else "evidence_repair"
    )
    spec_ready_for_patch = bool(
        precheck_present
        and certificate_present
        and current_blocker_active
        and proof_candidate_design_ready
        and certificate_design_gate_passed
    )
    checks = [
        _check(
            "precheck_candidate_present",
            "pass" if precheck_present else "fail",
            "precheck candidate loaded"
            if precheck_present
            else precheck_error or f"missing:{_display_path(project_root, precheck_path)}",
        ),
        _check(
            "current_joined_xy_blocker_active",
            "pass" if current_blocker_active else "fail",
            "joined-XY current blocker is active"
            if current_blocker_active
            else str(current_blocker.get("recommendation") or "current blocker inactive"),
        ),
        _check(
            "proof_candidate_design_ready",
            "pass" if proof_candidate_design_ready else "fail",
            str(proof_candidate.get("recommendation") or "proof candidate not ready"),
        ),
        _check(
            "order_capacity_certificate_present",
            "pass" if certificate_present else "fail",
            "order-capacity certificate candidate loaded"
            if certificate_present
            else certificate_error
            or f"missing:{_display_path(project_root, certificate_path)}",
        ),
        _check(
            "order_capacity_certificate_design_gate_passed",
            "pass" if certificate_design_gate_passed else "fail",
            str(
                certificate_gate.get("recommendation")
                or "certificate design gate not passed"
            ),
        ),
        _check(
            "anchored_case_bridge_missing",
            "pass" if anchored_case_bridge_missing else "fail",
            (
                "free-ghost certificate exists but standalone pair remains OPTIMAL, "
                "so anchored runtime promotion still needs a bridge"
            )
            if anchored_case_bridge_missing
            else "anchored case bridge already resolved or prerequisite evidence missing",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "proof-preserving extraction spec is not a runtime patch; finish row-domain "
                "or no-solve guard extraction first"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": PROOF_PRESERVING_EXTRACTION_SPEC_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_proof_preserving_extraction_spec_not_proof_source"
            ),
        },
        "paths": {
            "project_root": str(project_root),
            "precheck_candidate": _display_path(project_root, precheck_path),
            "order_capacity_certificate_candidate": _display_path(
                project_root, certificate_path
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "spec_ready_for_patch": bool(spec_ready_for_patch),
            "runtime_promotion_ready": False,
            "recommended_next_path": recommended_next_path,
            "recommendation": _recommendation(
                spec_ready_for_patch=spec_ready_for_patch,
                recommended_next_path=recommended_next_path,
            ),
        },
        "current_blocker": {
            "active": current_blocker_active,
            "blocker_subtype": current_blocker.get("blocker_subtype"),
            "workspace_master_branches": current_blocker.get("workspace_master_branches"),
            "workspace_master_conflicts": current_blocker.get("workspace_master_conflicts"),
            "coordinate_validation_infeasible_count": current_blocker.get(
                "coordinate_validation_infeasible_count"
            ),
        },
        "proof_candidate": {
            "design_ready": proof_candidate_design_ready,
            "core_label_count": proof_candidate.get("core_label_count"),
            "anchor_sweep_all_infeasible": proof_candidate.get(
                "anchor_sweep_all_infeasible"
            ),
            "standalone_pair_optimal": proof_candidate.get("standalone_pair_optimal"),
            "recommendation": proof_candidate.get("recommendation"),
        },
        "certificate_candidate": {
            "design_gate_passed": certificate_design_gate_passed,
            "certificate_shape": certificate_gate.get("certificate_shape"),
            "free_ghost_threshold": free_ghost_threshold,
            "fixed_anchor_threshold": fixed_anchor_threshold,
            "standalone_pair_full_status": certificate_evidence.get(
                "standalone_pair_full_status"
            ),
            "highest_non_exceeded_unknown_slot_index": certificate_evidence.get(
                "highest_non_exceeded_unknown_slot_index"
            ),
            "exceeded_infeasible_slot_indices": certificate_evidence.get(
                "exceeded_infeasible_slot_indices"
            ),
            "recommendation": certificate_gate.get("recommendation"),
        },
        "bridge_gap": {
            "anchored_case_bridge_missing": anchored_case_bridge_missing,
            "reason": (
                "The current certificate candidate explains the free-ghost threshold transition, "
                "but standalone pair remains OPTIMAL, so anchored B5A runtime rejection still "
                "needs a row-domain or equivalent bridge."
            ),
            "required_outputs": [
                "Extract a deterministic row-domain/count witness for the three-label core.",
                "Show how the anchored case maps to the same order-implied x-overlap strip logic.",
                "Define non-trigger controls for anchors that do not satisfy the same strip threshold.",
                "Keep runtime slice default-off and prove no false positives before any B5A rerun.",
            ],
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_proof_preserving_extraction_spec_markdown(
    report: Mapping[str, Any]
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    bridge_gap = _mapping(report.get("bridge_gap"))
    certificate = _mapping(report.get("certificate_candidate"))
    lines = [
        "# Phase 3B Coordinate-Validation Proof-Preserving Extraction Spec",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Recommended next path: {status.get('recommended_next_path')}",
        f"- Spec ready for patch: {bool(status.get('spec_ready_for_patch', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Bridge Gap",
        "",
        f"- Anchored case bridge missing: {bool(bridge_gap.get('anchored_case_bridge_missing', False))}",
        f"- Reason: {bridge_gap.get('reason')}",
        f"- Free-ghost threshold: {certificate.get('free_ghost_threshold')}",
        f"- Fixed-anchor threshold: {certificate.get('fixed_anchor_threshold')}",
        f"- Standalone pair full status: {certificate.get('standalone_pair_full_status')}",
        "",
        "## Required Outputs",
        "",
    ]
    lines.extend(f"- {item}" for item in list(bridge_gap.get("required_outputs", [])))
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
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


def render_phase3b_coordinate_validation_proof_preserving_extraction_spec_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bridge_gap = _mapping(report.get("bridge_gap"))
    certificate = _mapping(report.get("certificate_candidate"))
    lines = [
        "Phase 3B coordinate-validation proof-preserving extraction spec",
        f"recommended_next_path={status.get('recommended_next_path')}",
        f"spec_ready_for_patch={bool(status.get('spec_ready_for_patch', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"anchored_case_bridge_missing={bool(bridge_gap.get('anchored_case_bridge_missing', False))}",
        f"free_ghost_threshold={certificate.get('free_ghost_threshold')}",
        f"fixed_anchor_threshold={certificate.get('fixed_anchor_threshold')}",
        f"standalone_pair_full_status={certificate.get('standalone_pair_full_status')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"check id={check.get('check_id')} status={check.get('status')} detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _recommendation(*, spec_ready_for_patch: bool, recommended_next_path: str) -> str:
    if spec_ready_for_patch and recommended_next_path == "row_domain_extraction":
        return (
            "The no-solve certificate candidate is mature enough to guide a narrow row-domain "
            "extraction task. Use row-domain extraction first, because the free-ghost certificate "
            "alone does not yet bridge to anchored B5A runtime rejection."
        )
    if spec_ready_for_patch and recommended_next_path == "no_solve_certificate":
        return (
            "The no-solve certificate path is ready to be encoded directly as a guarded/default-off "
            "predicate."
        )
    return "Repair prerequisite evidence before patch planning."


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

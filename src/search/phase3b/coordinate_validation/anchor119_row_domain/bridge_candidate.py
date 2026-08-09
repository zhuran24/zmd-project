from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

ANCHOR119_ROW_DOMAIN_BRIDGE_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_v1"
)
ROW_DOMAIN_COUNT_WITNESS_PAYLOAD_SOURCE = (
    "phase3b_coordinate_validation_row_domain_count_witness_payload_v1"
)
ANCHOR119_GUARDED_PRECHECK_SPEC_SOURCE = "phase3b_anchor119_guarded_precheck_spec_v1"
ANCHOR119_GUARDED_PRECHECK_RUNTIME_SOURCE = (
    "phase3b_anchor119_guarded_precheck_runtime_v1"
)

DEFAULT_ROW_DOMAIN_COUNT_WITNESS_PAYLOAD_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_row_domain_count_witness_payload_20260424/"
    "row_domain_count_witness_payload.json"
)
DEFAULT_GUARDED_PRECHECK_SPEC_PATH = Path(
    ".artifacts/phase3b_anchor119_guarded_precheck_spec_20260423/"
    "guarded_precheck_spec.json"
)
DEFAULT_GUARDED_PRECHECK_ADVISORY_ENABLED_PATH = Path(
    ".artifacts/phase3b_anchor119_guarded_precheck_advisory_20260423/"
    "guarded_precheck_advisory_enabled.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate(
    project_root: Path,
    *,
    row_domain_count_witness_payload_path: Optional[Path] = None,
    guarded_precheck_spec_path: Optional[Path] = None,
    guarded_precheck_advisory_enabled_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    payload_resolved = _resolve_path(
        project_root,
        row_domain_count_witness_payload_path
        if row_domain_count_witness_payload_path is not None
        else DEFAULT_ROW_DOMAIN_COUNT_WITNESS_PAYLOAD_PATH,
    )
    spec_resolved = _resolve_path(
        project_root,
        guarded_precheck_spec_path
        if guarded_precheck_spec_path is not None
        else DEFAULT_GUARDED_PRECHECK_SPEC_PATH,
    )
    advisory_resolved = _resolve_path(
        project_root,
        guarded_precheck_advisory_enabled_path
        if guarded_precheck_advisory_enabled_path is not None
        else DEFAULT_GUARDED_PRECHECK_ADVISORY_ENABLED_PATH,
    )

    payload_report, payload_error = _load_json_mapping(payload_resolved)
    spec_report, spec_error = _load_json_mapping(spec_resolved)
    advisory_report, advisory_error = _load_json_mapping(advisory_resolved)

    payload_meta = _mapping(payload_report.get("metadata")) if payload_report else {}
    spec_meta = _mapping(spec_report.get("metadata")) if spec_report else {}
    advisory_meta = _mapping(advisory_report.get("metadata")) if advisory_report else {}

    payload_status = _mapping(payload_report.get("status")) if payload_report else {}
    payload_body = _mapping(payload_report.get("deterministic_payload")) if payload_report else {}
    payload_boundaries = _mapping(payload_report.get("count_boundaries")) if payload_report else {}
    candidate = _mapping(payload_report.get("candidate")) if payload_report else {}

    spec_status = _mapping(spec_report.get("status")) if spec_report else {}
    proposed_guard = _mapping(spec_report.get("proposed_guard")) if spec_report else {}
    spec_candidate = _mapping(spec_report.get("candidate")) if spec_report else {}

    advisory_proof = _mapping(advisory_report.get("proof_summary")) if advisory_report else {}
    advisory_master = _mapping(advisory_proof.get("master_candidate_precheck"))
    advisory_guard = _mapping(advisory_proof.get("anchor119_mixed_lane_guarded_precheck"))

    payload_present = bool(
        payload_report is not None
        and payload_error is None
        and payload_meta.get("source") == ROW_DOMAIN_COUNT_WITNESS_PAYLOAD_SOURCE
    )
    spec_present = bool(
        spec_report is not None
        and spec_error is None
        and spec_meta.get("source") == ANCHOR119_GUARDED_PRECHECK_SPEC_SOURCE
    )
    advisory_present = bool(
        advisory_report is not None
        and advisory_error is None
        and advisory_meta.get("source") == ANCHOR119_GUARDED_PRECHECK_RUNTIME_SOURCE
    )

    payload_ready = bool(payload_status.get("payload_ready", False))
    spec_ready = spec_status.get("outcome") == "guarded_precheck_spec_ready_for_review"
    advisory_would_trigger = bool(advisory_report.get("would_trigger", False))
    advisory_triggered = bool(advisory_report.get("triggered", False))
    advisory_reason_matches = (
        str(advisory_report.get("reason")) == "advisory_guard_would_reject_anchor119"
    )
    advisory_anchor_matches = (
        _optional_int(advisory_master.get("first_infeasible_anchor_idx"))
        == _optional_int(candidate.get("anchor_idx"))
        == _optional_int(spec_candidate.get("anchor_idx"))
    )
    guard_id_matches = (
        str(advisory_guard.get("guard_id") or "") == str(proposed_guard.get("guard_id") or "")
        and bool(str(proposed_guard.get("guard_id") or ""))
    )
    candidate_key_matches = (
        str(candidate.get("key") or "") == str(spec_candidate.get("key") or "") == "67x13"
    )
    non_trigger_boundary_present = _optional_int(
        payload_boundaries.get("non_trigger_max_slot_count")
    ) == 13
    anchored_trigger_boundary_present = _optional_int(
        payload_boundaries.get("anchored_trigger_min_slot_count")
    ) == 14
    free_ghost_trigger_boundary_present = _optional_int(
        payload_boundaries.get("free_ghost_trigger_min_slot_count")
    ) == 15
    default_off_retained = (
        bool(proposed_guard.get("default_state") == "disabled")
        and bool(advisory_master.get("triggered", False)) is False
        and bool(advisory_guard.get("runtime_precheck_enabled", False)) is False
    )

    bridge_ready_for_review = bool(
        payload_present
        and spec_present
        and advisory_present
        and payload_ready
        and spec_ready
        and advisory_would_trigger
        and not advisory_triggered
        and advisory_reason_matches
        and advisory_anchor_matches
        and guard_id_matches
        and candidate_key_matches
    )
    non_trigger_controls_ready = bool(
        bridge_ready_for_review
        and non_trigger_boundary_present
        and anchored_trigger_boundary_present
        and free_ghost_trigger_boundary_present
        and default_off_retained
    )

    checks = [
        _check(
            "row_domain_count_witness_payload_present",
            "pass" if payload_present else "fail",
            "row-domain/count witness payload loaded"
            if payload_present
            else payload_error or f"missing:{_display_path(project_root, payload_resolved)}",
        ),
        _check(
            "row_domain_count_payload_ready",
            "pass" if payload_ready else "fail",
            str(payload_status.get("recommendation") or "payload not ready"),
        ),
        _check(
            "guarded_precheck_spec_present",
            "pass" if spec_present else "fail",
            "guarded precheck spec loaded"
            if spec_present
            else spec_error or f"missing:{_display_path(project_root, spec_resolved)}",
        ),
        _check(
            "guarded_precheck_spec_ready",
            "pass" if spec_ready else "fail",
            str(spec_status.get("outcome")),
        ),
        _check(
            "guarded_precheck_advisory_present",
            "pass" if advisory_present else "fail",
            "guarded precheck advisory loaded"
            if advisory_present
            else advisory_error or f"missing:{_display_path(project_root, advisory_resolved)}",
        ),
        _check(
            "advisory_would_trigger_anchor119",
            "pass" if advisory_would_trigger and advisory_reason_matches else "fail",
            f"would_trigger={advisory_report.get('would_trigger')} reason={advisory_report.get('reason')}",
        ),
        _check(
            "advisory_never_short_circuits_runtime",
            "pass" if not advisory_triggered else "fail",
            f"triggered={advisory_report.get('triggered')}",
        ),
        _check(
            "anchor_and_candidate_match",
            "pass" if advisory_anchor_matches and candidate_key_matches else "fail",
            (
                f"candidate_key={candidate.get('key')} spec_candidate_key={spec_candidate.get('key')} "
                f"anchor={advisory_master.get('first_infeasible_anchor_idx')}"
            ),
        ),
        _check(
            "guard_id_matches",
            "pass" if guard_id_matches else "fail",
            f"payload/spec guard_id={proposed_guard.get('guard_id')} advisory guard_id={advisory_guard.get('guard_id')}",
        ),
        _check(
            "nontrigger_boundaries_present",
            "pass"
            if non_trigger_boundary_present
            and anchored_trigger_boundary_present
            and free_ghost_trigger_boundary_present
            else "fail",
            (
                f"non_trigger_max={payload_boundaries.get('non_trigger_max_slot_count')} "
                f"anchored_trigger_min={payload_boundaries.get('anchored_trigger_min_slot_count')} "
                f"free_ghost_trigger_min={payload_boundaries.get('free_ghost_trigger_min_slot_count')}"
            ),
        ),
        _check(
            "default_off_retained",
            "pass" if default_off_retained else "fail",
            (
                f"default_state={proposed_guard.get('default_state')} "
                f"advisory_triggered={advisory_report.get('triggered')} "
                f"runtime_precheck_enabled={advisory_guard.get('runtime_precheck_enabled')}"
            ),
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "anchor119 row-domain bridge candidate is still review/default-off only; "
                "do not enable runtime behavior until the anchored bridge and non-trigger "
                "controls are turned into a separately reviewed patch"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ANCHOR119_ROW_DOMAIN_BRIDGE_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_anchor119_row_domain_bridge_candidate_not_proof_source"
            ),
            "solver_invoked": False,
            "proof_source": False,
            "default_off": True,
        },
        "paths": {
            "project_root": str(project_root),
            "row_domain_count_witness_payload": _display_path(project_root, payload_resolved),
            "guarded_precheck_spec": _display_path(project_root, spec_resolved),
            "guarded_precheck_advisory_enabled": _display_path(project_root, advisory_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "bridge_ready_for_review": bool(bridge_ready_for_review),
            "non_trigger_controls_ready": bool(non_trigger_controls_ready),
            "runtime_promotion_ready": False,
            "recommended_next_step": "draft_default_off_anchor119_row_domain_guard_spec",
            "recommendation": _recommendation(
                bridge_ready_for_review=bridge_ready_for_review,
                non_trigger_controls_ready=non_trigger_controls_ready,
            ),
        },
        "bridge": {
            "payload_id": payload_body.get("payload_id"),
            "guard_id": proposed_guard.get("guard_id"),
            "advisory_reason": advisory_report.get("reason"),
            "advisory_would_trigger": advisory_would_trigger,
            "advisory_triggered": advisory_triggered,
            "first_infeasible_anchor_idx": advisory_master.get("first_infeasible_anchor_idx"),
            "supported": advisory_master.get("supported"),
            "shared_safe_strip_lower_bound": payload_body.get("shared_safe_strip_lower_bound"),
            "total_row_count": payload_body.get("total_row_count"),
            "rows": list(payload_body.get("rows", [])),
        },
        "non_trigger_controls": {
            "default_state": proposed_guard.get("default_state"),
            "advisory_only": advisory_guard.get("advisory_only"),
            "candidate_key_required": candidate.get("key"),
            "anchor_idx_required": candidate.get("anchor_idx"),
            "non_trigger_max_slot_count": payload_boundaries.get("non_trigger_max_slot_count"),
            "anchored_trigger_min_slot_count": payload_boundaries.get("anchored_trigger_min_slot_count"),
            "free_ghost_trigger_min_slot_count": payload_boundaries.get("free_ghost_trigger_min_slot_count"),
            "same_three_label_payload_required": True,
            "runtime_short_circuit_disabled": not advisory_triggered,
        },
        "required_outputs": [
            "Turn the bridge candidate into a reviewed default-off anchor119 row-domain guard spec.",
            "Encode the 13 -> non-trigger and 14 -> anchored trigger boundary in the same guard family.",
            "Preserve advisory-only behavior unless and until a separate reviewed runtime patch exists.",
        ],
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bridge = _mapping(report.get("bridge"))
    controls = _mapping(report.get("non_trigger_controls"))
    lines = [
        "# Phase 3B Coordinate-Validation Anchor119 Row-Domain Bridge Candidate",
        "",
        f"- Bridge ready for review: {bool(status.get('bridge_ready_for_review', False))}",
        f"- Non-trigger controls ready: {bool(status.get('non_trigger_controls_ready', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Recommended next step: {status.get('recommended_next_step')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Bridge",
        "",
        f"- Payload id: {bridge.get('payload_id')}",
        f"- Guard id: {bridge.get('guard_id')}",
        f"- Advisory reason: {bridge.get('advisory_reason')}",
        f"- Advisory would trigger: {bridge.get('advisory_would_trigger')}",
        f"- Advisory triggered: {bridge.get('advisory_triggered')}",
        f"- First infeasible anchor idx: {bridge.get('first_infeasible_anchor_idx')}",
        f"- Shared safe-strip lower bound: {bridge.get('shared_safe_strip_lower_bound')}",
        f"- Total row count: {bridge.get('total_row_count')}",
        "",
        "## Non-Trigger Controls",
        "",
        f"- Default state: {controls.get('default_state')}",
        f"- Candidate key required: {controls.get('candidate_key_required')}",
        f"- Anchor idx required: {controls.get('anchor_idx_required')}",
        f"- Non-trigger max slot count: {controls.get('non_trigger_max_slot_count')}",
        f"- Anchored trigger min slot count: {controls.get('anchored_trigger_min_slot_count')}",
        f"- Free-ghost trigger min slot count: {controls.get('free_ghost_trigger_min_slot_count')}",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bridge = _mapping(report.get("bridge"))
    controls = _mapping(report.get("non_trigger_controls"))
    lines = [
        "Phase 3B coordinate-validation anchor119 row-domain bridge candidate",
        f"bridge_ready_for_review={bool(status.get('bridge_ready_for_review', False))}",
        f"non_trigger_controls_ready={bool(status.get('non_trigger_controls_ready', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"recommended_next_step={status.get('recommended_next_step')}",
        f"payload_id={bridge.get('payload_id')}",
        f"guard_id={bridge.get('guard_id')}",
        f"advisory_would_trigger={bridge.get('advisory_would_trigger')}",
        f"advisory_triggered={bridge.get('advisory_triggered')}",
        f"non_trigger_max_slot_count={controls.get('non_trigger_max_slot_count')}",
        f"anchored_trigger_min_slot_count={controls.get('anchored_trigger_min_slot_count')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"check id={check.get('check_id')} status={check.get('status')} detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _recommendation(*, bridge_ready_for_review: bool, non_trigger_controls_ready: bool) -> str:
    if bridge_ready_for_review and non_trigger_controls_ready:
        return (
            "Anchor119 row-domain bridge candidate is ready for review: the next bounded move is "
            "to draft a default-off guard spec or patch that preserves advisory-only behavior and "
            "encodes the non-trigger boundaries explicitly."
        )
    if bridge_ready_for_review:
        return "Anchor119 row-domain bridge is visible, but non-trigger controls still need cleanup."
    return "Anchor119 row-domain bridge candidate is incomplete; repair prerequisite evidence first."


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


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


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

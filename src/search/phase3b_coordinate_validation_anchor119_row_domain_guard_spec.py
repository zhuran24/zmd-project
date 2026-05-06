from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_anchor119_guard_controls import (
    PHASE3B_ANCHOR119_ANCHORED_TRIGGER_MIN_SLOT_COUNT,
    PHASE3B_ANCHOR119_ANCHOR_IDX,
    PHASE3B_ANCHOR119_CANDIDATE_KEY,
    PHASE3B_ANCHOR119_DEFAULT_STATE,
    PHASE3B_ANCHOR119_FREE_GHOST_TRIGGER_MIN_SLOT_COUNT,
    PHASE3B_ANCHOR119_GUARD_ID,
    PHASE3B_ANCHOR119_NON_TRIGGER_MAX_SLOT_COUNT,
    phase3b_anchor119_guard_candidate_scope,
)

ANCHOR119_ROW_DOMAIN_GUARD_SPEC_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_spec_v1"
)
ANCHOR119_ROW_DOMAIN_BRIDGE_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_v1"
)

DEFAULT_BRIDGE_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_20260424/"
    "anchor119_row_domain_bridge_candidate.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_guard_spec(
    project_root: Path,
    *,
    bridge_candidate_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    bridge_resolved = _resolve_path(
        project_root,
        bridge_candidate_path if bridge_candidate_path is not None else DEFAULT_BRIDGE_CANDIDATE_PATH,
    )

    bridge_report, bridge_error = _load_json_mapping(bridge_resolved)
    bridge_meta = _mapping(bridge_report.get("metadata")) if bridge_report else {}
    bridge_status = _mapping(bridge_report.get("status")) if bridge_report else {}
    bridge = _mapping(bridge_report.get("bridge")) if bridge_report else {}
    controls = _mapping(bridge_report.get("non_trigger_controls")) if bridge_report else {}
    candidate = _mapping(bridge_report.get("candidate")) if bridge_report else {}

    bridge_present = bool(
        bridge_report is not None
        and bridge_error is None
        and bridge_meta.get("source") == ANCHOR119_ROW_DOMAIN_BRIDGE_CANDIDATE_SOURCE
    )
    bridge_ready = bool(bridge_status.get("bridge_ready_for_review", False))
    non_trigger_controls_ready = bool(bridge_status.get("non_trigger_controls_ready", False))
    default_off = str(controls.get("default_state")) == str(PHASE3B_ANCHOR119_DEFAULT_STATE)
    advisory_only = bool(controls.get("advisory_only", False))
    runtime_short_circuit_disabled = bool(controls.get("runtime_short_circuit_disabled", False))
    candidate_key_ok = str(controls.get("candidate_key_required")) == PHASE3B_ANCHOR119_CANDIDATE_KEY
    anchor_idx_ok = _optional_int(controls.get("anchor_idx_required")) == PHASE3B_ANCHOR119_ANCHOR_IDX
    boundary_13_ok = (
        _optional_int(controls.get("non_trigger_max_slot_count"))
        == PHASE3B_ANCHOR119_NON_TRIGGER_MAX_SLOT_COUNT
    )
    boundary_14_ok = (
        _optional_int(controls.get("anchored_trigger_min_slot_count"))
        == PHASE3B_ANCHOR119_ANCHORED_TRIGGER_MIN_SLOT_COUNT
    )
    boundary_15_ok = (
        _optional_int(controls.get("free_ghost_trigger_min_slot_count"))
        == PHASE3B_ANCHOR119_FREE_GHOST_TRIGGER_MIN_SLOT_COUNT
    )

    review_ready = bool(
        bridge_present
        and bridge_ready
        and non_trigger_controls_ready
        and default_off
        and advisory_only
        and runtime_short_circuit_disabled
        and candidate_key_ok
        and anchor_idx_ok
        and boundary_13_ok
        and boundary_14_ok
        and boundary_15_ok
    )

    proposed_guard = {
        "guard_id": str(bridge.get("guard_id") or PHASE3B_ANCHOR119_GUARD_ID),
        "scope": phase3b_anchor119_guard_candidate_scope(
            suffix="joined_xy_block64_all_templates, anchor119 fixed-anchor row-domain/count bridge"
        ),
        "default_state": PHASE3B_ANCHOR119_DEFAULT_STATE,
        "advisory_only": True,
        "runtime_hook": "none_in_this_patch",
        "payload_id": bridge.get("payload_id"),
        "matching_requirements": {
            "candidate_key": PHASE3B_ANCHOR119_CANDIDATE_KEY,
            "anchor_idx": PHASE3B_ANCHOR119_ANCHOR_IDX,
            "payload_id": bridge.get("payload_id"),
        },
        "trigger_requirements": {
            "same_three_label_payload_required": bool(controls.get("same_three_label_payload_required", False)),
            "shared_safe_strip_lower_bound": bridge.get("shared_safe_strip_lower_bound"),
            "advisory_would_trigger": bool(bridge.get("advisory_would_trigger", False)),
            "advisory_triggered": bool(bridge.get("advisory_triggered", False)),
            "first_infeasible_anchor_idx": _optional_int(bridge.get("first_infeasible_anchor_idx")),
        },
        "non_trigger_controls": {
            "non_trigger_max_slot_count": _optional_int(controls.get("non_trigger_max_slot_count")),
            "anchored_trigger_min_slot_count": _optional_int(controls.get("anchored_trigger_min_slot_count")),
            "free_ghost_trigger_min_slot_count": _optional_int(controls.get("free_ghost_trigger_min_slot_count")),
            "runtime_short_circuit_disabled": runtime_short_circuit_disabled,
            "candidate_key_required": controls.get("candidate_key_required"),
            "anchor_idx_required": _optional_int(controls.get("anchor_idx_required")),
        },
        "patch_review_targets": [
            "src/search/phase3b_anchor119_guarded_precheck_spec.py",
            "src/search/phase3b_anchor119_guarded_precheck_runtime.py",
            "src/tests/test_phase3b_anchor119_guarded_precheck_spec.py",
            "src/tests/test_phase3b_anchor119_guarded_precheck_runtime.py",
        ],
        "non_goals": [
            "No runtime semantics change in this spec.",
            "No candidate elimination claim.",
            "No release/viewer/frontdoor status change.",
            "No workspace checkpoint import.",
            "No final 168h long run.",
        ],
    }

    checks = [
        _check(
            "bridge_candidate_present",
            "pass" if bridge_present else "fail",
            "anchor119 row-domain bridge candidate loaded"
            if bridge_present
            else bridge_error or f"missing:{_display_path(project_root, bridge_resolved)}",
        ),
        _check(
            "bridge_ready_for_review",
            "pass" if bridge_ready else "fail",
            str(bridge_status.get("recommendation") or "bridge not ready"),
        ),
        _check(
            "non_trigger_controls_ready",
            "pass" if non_trigger_controls_ready else "fail",
            str(bridge_status.get("recommendation") or "non-trigger controls not ready"),
        ),
        _check(
            "default_off_state_retained",
            "pass" if default_off else "fail",
            f"default_state={controls.get('default_state')}",
        ),
        _check(
            "advisory_only_retained",
            "pass" if advisory_only else "fail",
            f"advisory_only={controls.get('advisory_only')}",
        ),
        _check(
            "runtime_short_circuit_disabled",
            "pass" if runtime_short_circuit_disabled else "fail",
            f"runtime_short_circuit_disabled={controls.get('runtime_short_circuit_disabled')}",
        ),
        _check(
            "candidate_key_and_anchor_match",
            "pass" if candidate_key_ok and anchor_idx_ok else "fail",
            f"candidate_key={controls.get('candidate_key_required')} anchor_idx={controls.get('anchor_idx_required')}",
        ),
        _check(
            "count_boundaries_locked",
            "pass" if boundary_13_ok and boundary_14_ok and boundary_15_ok else "fail",
            (
                f"non_trigger_max={controls.get('non_trigger_max_slot_count')} "
                f"anchored_trigger_min={controls.get('anchored_trigger_min_slot_count')} "
                f"free_ghost_trigger_min={controls.get('free_ghost_trigger_min_slot_count')}"
            ),
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "anchor119 row-domain guard spec is review-only; keep runtime behavior unchanged "
                "until a separate reviewed patch explicitly adopts this default-off guard"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ANCHOR119_ROW_DOMAIN_GUARD_SPEC_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_row_domain_guard_spec_only_not_runtime_semantics",
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "bridge_candidate": _display_path(project_root, bridge_resolved),
        },
        "candidate": dict(candidate),
        "proposed_guard": proposed_guard,
        "status": {
            "completed": True,
            "outcome": (
                "anchor119_row_domain_guard_spec_ready_for_review"
                if review_ready
                else "anchor119_row_domain_guard_spec_blocked"
            ),
            "all_gates_pass": bool(review_ready),
            "runtime_precheck_enabled": False,
            "runtime_promotion_ready": False,
            "recommended_next_step": "prepare_anchor119_row_domain_guard_patch_review",
            "recommendation": (
                "Spec gates pass for a default-off anchor119 row-domain guard review; do not enable runtime behavior without a separate reviewed patch."
                if review_ready
                else "Spec gates did not all pass; repair bridge candidate inputs before patch review."
            ),
        },
        "evidence": {
            "payload_id": bridge.get("payload_id"),
            "guard_id": bridge.get("guard_id"),
            "advisory_reason": bridge.get("advisory_reason"),
            "advisory_would_trigger": bridge.get("advisory_would_trigger"),
            "advisory_triggered": bridge.get("advisory_triggered"),
            "shared_safe_strip_lower_bound": bridge.get("shared_safe_strip_lower_bound"),
            "total_row_count": bridge.get("total_row_count"),
            "non_trigger_max_slot_count": controls.get("non_trigger_max_slot_count"),
            "anchored_trigger_min_slot_count": controls.get("anchored_trigger_min_slot_count"),
            "free_ghost_trigger_min_slot_count": controls.get("free_ghost_trigger_min_slot_count"),
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_guard_spec_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    proposed_guard = _mapping(report.get("proposed_guard"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Guard Spec",
        "",
        f"- Outcome: `{status.get('outcome')}`",
        "- Spec only: true",
        "- Default-off: true",
        "- Runtime precheck enabled: false",
        "- Runtime semantics changed: false",
        "- Proof source: false",
        f"- Candidate: `{candidate.get('key')}` / anchor `{candidate.get('anchor_idx')}`",
        f"- Guard id: `{proposed_guard.get('guard_id')}`",
        f"- All gates pass: `{status.get('all_gates_pass')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Evidence",
        "",
        f"- Payload id: `{evidence.get('payload_id')}`",
        f"- Advisory would trigger: `{evidence.get('advisory_would_trigger')}`",
        f"- Advisory triggered: `{evidence.get('advisory_triggered')}`",
        f"- Shared safe-strip lower bound: `{evidence.get('shared_safe_strip_lower_bound')}`",
        f"- Total row count: `{evidence.get('total_row_count')}`",
        f"- Non-trigger max slot count: `{evidence.get('non_trigger_max_slot_count')}`",
        f"- Anchored trigger min slot count: `{evidence.get('anchored_trigger_min_slot_count')}`",
        f"- Free-ghost trigger min slot count: `{evidence.get('free_ghost_trigger_min_slot_count')}`",
        "",
        "## Proposed Guard",
        "",
        f"- Scope: `{proposed_guard.get('scope')}`",
        f"- Default state: `{proposed_guard.get('default_state')}`",
        f"- Advisory only: `{proposed_guard.get('advisory_only')}`",
        f"- Runtime hook: `{proposed_guard.get('runtime_hook')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_guard_spec_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    evidence = _mapping(report.get("evidence"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain guard spec",
            f"outcome={status.get('outcome')}",
            f"all_gates_pass={status.get('all_gates_pass')}",
            "spec_only=true",
            "default_off=true",
            "runtime_precheck_enabled=false",
            "runtime_semantics_changed=false",
            "proof_source=false",
            f"payload_id={evidence.get('payload_id')}",
            f"advisory_would_trigger={evidence.get('advisory_would_trigger')}",
            f"advisory_triggered={evidence.get('advisory_triggered')}",
            f"non_trigger_max_slot_count={evidence.get('non_trigger_max_slot_count')}",
            f"anchored_trigger_min_slot_count={evidence.get('anchored_trigger_min_slot_count')}",
        ]
    ) + "\n"


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

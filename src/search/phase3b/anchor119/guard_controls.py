from __future__ import annotations

import os
from typing import Any, Dict, Optional

PHASE3B_ANCHOR119_GUARD_ID = "anchor119_mixed_lane_no_witness_guard_v0"
PHASE3B_ANCHOR119_PAYLOAD_ID = "anchor119_three_label_overlap_above_strip_count_guard_v0"
PHASE3B_ANCHOR119_ADVISORY_ENV = "EXACT_PRE_MASTER_ANCHOR119_MIXED_LANE_GUARD_ADVISORY"
PHASE3B_ANCHOR119_DEFAULT_STATE = "disabled"
PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED = "advisory_enabled"
PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED = "runtime_enabled_reserved"
PHASE3B_ANCHOR119_RUNTIME_DECISION_ID = "anchor119_row_domain_runtime_decision_v0"
PHASE3B_ANCHOR119_CANDIDATE_KEY = "67x13"
PHASE3B_ANCHOR119_GHOST_W = 67
PHASE3B_ANCHOR119_GHOST_H = 13
PHASE3B_ANCHOR119_ANCHOR_IDX = 119
PHASE3B_ANCHOR119_NON_TRIGGER_MAX_SLOT_COUNT = 13
PHASE3B_ANCHOR119_ANCHORED_TRIGGER_MIN_SLOT_COUNT = 14
PHASE3B_ANCHOR119_FREE_GHOST_TRIGGER_MIN_SLOT_COUNT = 15
PHASE3B_ANCHOR119_ADVISORY_TRUTHY_VALUES = ("1", "true", "yes", "on")
PHASE3B_ANCHOR119_RUNTIME_REQUEST_VALUES = (
    "runtime",
    "apply",
    "reserved",
    "runtime_enabled_reserved",
)


def build_phase3b_anchor119_guard_locked_boundaries() -> Dict[str, int]:
    return {
        "non_trigger_max_slot_count": int(PHASE3B_ANCHOR119_NON_TRIGGER_MAX_SLOT_COUNT),
        "anchored_trigger_min_slot_count": int(
            PHASE3B_ANCHOR119_ANCHORED_TRIGGER_MIN_SLOT_COUNT
        ),
        "free_ghost_trigger_min_slot_count": int(
            PHASE3B_ANCHOR119_FREE_GHOST_TRIGGER_MIN_SLOT_COUNT
        ),
    }


def phase3b_anchor119_guard_candidate_matches(
    *,
    ghost_w: int,
    ghost_h: int,
    anchor_idx: Optional[int],
) -> bool:
    actual_anchor_idx = PHASE3B_ANCHOR119_ANCHOR_IDX if anchor_idx is None else int(anchor_idx)
    return (
        int(ghost_w) == int(PHASE3B_ANCHOR119_GHOST_W)
        and int(ghost_h) == int(PHASE3B_ANCHOR119_GHOST_H)
        and int(actual_anchor_idx) == int(PHASE3B_ANCHOR119_ANCHOR_IDX)
    )


def phase3b_anchor119_guard_candidate_scope(*, suffix: str = "") -> str:
    base = (
        f"candidate={PHASE3B_ANCHOR119_CANDIDATE_KEY}, "
        f"anchor_idx={PHASE3B_ANCHOR119_ANCHOR_IDX}"
    )
    suffix = str(suffix).strip()
    if not suffix:
        return base
    return f"{base}, {suffix}"


def phase3b_anchor119_guard_advisory_enabled(raw: Optional[str] = None) -> bool:
    if raw is None:
        raw = os.environ.get(PHASE3B_ANCHOR119_ADVISORY_ENV, "")
    return str(raw).strip().lower() in set(PHASE3B_ANCHOR119_ADVISORY_TRUTHY_VALUES)


def _phase3b_anchor119_guard_requested_state(raw: Optional[str]) -> str:
    if raw is None:
        raw = os.environ.get(PHASE3B_ANCHOR119_ADVISORY_ENV, "")
    token = str(raw).strip().lower()
    if token in set(PHASE3B_ANCHOR119_RUNTIME_REQUEST_VALUES):
        return PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED
    if token in set(PHASE3B_ANCHOR119_ADVISORY_TRUTHY_VALUES):
        return PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    return PHASE3B_ANCHOR119_DEFAULT_STATE


def build_phase3b_anchor119_guard_runtime_state(
    *,
    advisory_env_raw: Optional[str] = None,
) -> Dict[str, Any]:
    requested_state = _phase3b_anchor119_guard_requested_state(advisory_env_raw)
    runtime_requested = (
        requested_state == PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED
    )
    advisory_enabled = requested_state in {
        PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
        PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED,
    }
    runtime_activation_allowed = False
    effective_state = (
        PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED
        if runtime_requested and runtime_activation_allowed
        else (
            PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
            if advisory_enabled
            else PHASE3B_ANCHOR119_DEFAULT_STATE
        )
    )
    runtime_precheck_enabled = bool(runtime_requested and runtime_activation_allowed)
    return {
        "env_name": PHASE3B_ANCHOR119_ADVISORY_ENV,
        "truthy_values": list(PHASE3B_ANCHOR119_ADVISORY_TRUTHY_VALUES),
        "runtime_request_values": list(PHASE3B_ANCHOR119_RUNTIME_REQUEST_VALUES),
        "requested_state": requested_state,
        "effective_state": effective_state,
        "default_state": PHASE3B_ANCHOR119_DEFAULT_STATE,
        "advisory_enabled": bool(advisory_enabled),
        "runtime_requested": bool(runtime_requested),
        "advisory_only": not bool(runtime_precheck_enabled),
        "default_off": True,
        "runtime_precheck_enabled": bool(runtime_precheck_enabled),
        "runtime_activation_allowed": bool(runtime_activation_allowed),
        "runtime_enablement_blockers": [
            "reviewed_runtime_patch_missing",
            "production_acceptance_refresh_required",
            "proof_source_promotion_forbidden",
        ],
    }


def build_phase3b_anchor119_guard_runtime_decision(
    *,
    requested_state: Optional[str],
    effective_state: Optional[str],
    runtime_activation_allowed: bool,
    would_trigger: bool,
    triggered: bool,
    reason: Optional[str],
    runtime_enablement_blockers: Optional[list[str]] = None,
) -> Dict[str, Any]:
    blockers = [str(token) for token in list(runtime_enablement_blockers or [])]
    apply_runtime_elimination = bool(runtime_activation_allowed and triggered)
    if apply_runtime_elimination:
        blocked_reason = None
    elif bool(would_trigger) and not bool(runtime_activation_allowed):
        blocked_reason = "runtime_activation_not_allowed"
    elif bool(would_trigger):
        blocked_reason = "advisory_only_no_runtime_apply"
    else:
        blocked_reason = "guard_not_triggered"
    return {
        "decision_id": PHASE3B_ANCHOR119_RUNTIME_DECISION_ID,
        "requested_state": requested_state,
        "effective_state": effective_state,
        "would_trigger": bool(would_trigger),
        "triggered": bool(triggered),
        "runtime_activation_allowed": bool(runtime_activation_allowed),
        "apply_runtime_elimination": bool(apply_runtime_elimination),
        "blocked_reason": blocked_reason,
        "runtime_enablement_blockers": blockers,
        "reason": reason,
    }

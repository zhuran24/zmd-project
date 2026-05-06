from __future__ import annotations

from src.search.phase3b_anchor119_guard_controls import (
    PHASE3B_ANCHOR119_ADVISORY_ENV,
    PHASE3B_ANCHOR119_RUNTIME_DECISION_ID,
    PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
    PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED,
    PHASE3B_ANCHOR119_ANCHOR_IDX,
    PHASE3B_ANCHOR119_CANDIDATE_KEY,
    PHASE3B_ANCHOR119_DEFAULT_STATE,
    PHASE3B_ANCHOR119_GHOST_H,
    PHASE3B_ANCHOR119_GHOST_W,
    PHASE3B_ANCHOR119_GUARD_ID,
    PHASE3B_ANCHOR119_PAYLOAD_ID,
    build_phase3b_anchor119_guard_runtime_decision,
    build_phase3b_anchor119_guard_runtime_state,
    build_phase3b_anchor119_guard_locked_boundaries,
    phase3b_anchor119_guard_candidate_matches,
    phase3b_anchor119_guard_candidate_scope,
)


def test_anchor119_guard_controls_match_current_reviewed_boundaries() -> None:
    boundaries = build_phase3b_anchor119_guard_locked_boundaries()

    assert PHASE3B_ANCHOR119_GUARD_ID == "anchor119_mixed_lane_no_witness_guard_v0"
    assert PHASE3B_ANCHOR119_PAYLOAD_ID == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert PHASE3B_ANCHOR119_ADVISORY_ENV == "EXACT_PRE_MASTER_ANCHOR119_MIXED_LANE_GUARD_ADVISORY"
    assert PHASE3B_ANCHOR119_DEFAULT_STATE == "disabled"
    assert PHASE3B_ANCHOR119_CANDIDATE_KEY == "67x13"
    assert PHASE3B_ANCHOR119_GHOST_W == 67
    assert PHASE3B_ANCHOR119_GHOST_H == 13
    assert PHASE3B_ANCHOR119_ANCHOR_IDX == 119
    assert boundaries == {
        "non_trigger_max_slot_count": 13,
        "anchored_trigger_min_slot_count": 14,
        "free_ghost_trigger_min_slot_count": 15,
    }


def test_anchor119_guard_controls_helpers_build_scope_and_match_candidate() -> None:
    assert (
        phase3b_anchor119_guard_candidate_scope()
        == "candidate=67x13, anchor_idx=119"
    )
    assert phase3b_anchor119_guard_candidate_scope(suffix="joined_xy_block64_all_templates") == (
        "candidate=67x13, anchor_idx=119, joined_xy_block64_all_templates"
    )
    assert phase3b_anchor119_guard_candidate_matches(
        ghost_w=67,
        ghost_h=13,
        anchor_idx=119,
    )
    assert phase3b_anchor119_guard_candidate_matches(
        ghost_w=67,
        ghost_h=13,
        anchor_idx=None,
    )
    assert not phase3b_anchor119_guard_candidate_matches(
        ghost_w=66,
        ghost_h=13,
        anchor_idx=119,
    )


def test_anchor119_guard_runtime_state_stays_default_off_even_when_advisory_enabled() -> None:
    disabled = build_phase3b_anchor119_guard_runtime_state(advisory_env_raw="")
    advisory = build_phase3b_anchor119_guard_runtime_state(advisory_env_raw="true")
    runtime_requested = build_phase3b_anchor119_guard_runtime_state(
        advisory_env_raw="runtime"
    )

    assert disabled["requested_state"] == PHASE3B_ANCHOR119_DEFAULT_STATE
    assert disabled["effective_state"] == PHASE3B_ANCHOR119_DEFAULT_STATE
    assert disabled["advisory_enabled"] is False
    assert disabled["runtime_precheck_enabled"] is False
    assert disabled["runtime_activation_allowed"] is False

    assert advisory["requested_state"] == PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    assert advisory["effective_state"] == PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    assert advisory["advisory_enabled"] is True
    assert advisory["advisory_only"] is True
    assert advisory["runtime_precheck_enabled"] is False
    assert advisory["runtime_activation_allowed"] is False
    assert "reviewed_runtime_patch_missing" in advisory["runtime_enablement_blockers"]
    assert runtime_requested["requested_state"] == PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED
    assert runtime_requested["effective_state"] == PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    assert runtime_requested["runtime_requested"] is True
    assert runtime_requested["advisory_enabled"] is True
    assert runtime_requested["runtime_precheck_enabled"] is False
    assert runtime_requested["runtime_activation_allowed"] is False
    assert PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED == "runtime_enabled_reserved"


def test_anchor119_guard_runtime_state_reads_env_when_raw_value_is_omitted(monkeypatch) -> None:
    monkeypatch.delenv(PHASE3B_ANCHOR119_ADVISORY_ENV, raising=False)
    disabled = build_phase3b_anchor119_guard_runtime_state()

    assert disabled["requested_state"] == PHASE3B_ANCHOR119_DEFAULT_STATE
    assert disabled["effective_state"] == PHASE3B_ANCHOR119_DEFAULT_STATE
    assert disabled["advisory_enabled"] is False
    assert disabled["runtime_precheck_enabled"] is False

    monkeypatch.setenv(PHASE3B_ANCHOR119_ADVISORY_ENV, "true")
    advisory = build_phase3b_anchor119_guard_runtime_state()

    assert advisory["requested_state"] == PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    assert advisory["effective_state"] == PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    assert advisory["advisory_enabled"] is True
    assert advisory["runtime_precheck_enabled"] is False
    assert advisory["runtime_activation_allowed"] is False

    monkeypatch.setenv(PHASE3B_ANCHOR119_ADVISORY_ENV, "runtime")
    runtime_requested = build_phase3b_anchor119_guard_runtime_state()

    assert runtime_requested["requested_state"] == PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED
    assert runtime_requested["effective_state"] == PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED
    assert runtime_requested["runtime_requested"] is True
    assert runtime_requested["advisory_enabled"] is True
    assert runtime_requested["runtime_precheck_enabled"] is False
    assert runtime_requested["runtime_activation_allowed"] is False

def test_anchor119_guard_runtime_decision_stays_blocked_in_default_off_mode() -> None:
    decision = build_phase3b_anchor119_guard_runtime_decision(
        requested_state=PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
        effective_state=PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
        runtime_activation_allowed=False,
        would_trigger=True,
        triggered=False,
        reason="advisory_guard_would_reject_anchor119",
        runtime_enablement_blockers=[
            "reviewed_runtime_patch_missing",
            "production_acceptance_refresh_required",
        ],
    )

    assert decision["decision_id"] == PHASE3B_ANCHOR119_RUNTIME_DECISION_ID
    assert decision["would_trigger"] is True
    assert decision["apply_runtime_elimination"] is False
    assert decision["blocked_reason"] == "runtime_activation_not_allowed"
    assert decision["reason"] == "advisory_guard_would_reject_anchor119"

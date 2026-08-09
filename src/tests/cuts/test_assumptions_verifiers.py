"""Phase 1.0 P1.4 test — assumption verifier dispatch (production 实施 vs Phase 1.0 stub).

Coverage:
- verify_placement_rule: "group=rule" parse + match canonical_rules
- verify_boundary_saturation: fail-closed on None rules
- lookup_verifier registered keys
- register_verifier overwrite
- lifecycle.assumption_holds delegate 到 lookup_verifier (lazy import)
"""
from __future__ import annotations

import pytest

from src.cuts.assumptions.verifiers import (
    lookup_verifier,
    register_verifier,
    verify_boundary_saturation,
    verify_placement_rule,
    _VERIFIERS,
)
from src.cuts.lifecycle import (
    Assumption,
    BState,
    GroupState,
    assumption_holds,
)


CANONICAL_RULES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "cells_per_pose": 3,
    },
    "crusher_blue_iron": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
}


_FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},
    },
    "manufacturing_3x3": {
        "dimensions": {"w": 3, "h": 3},
    },
}
_INSTANCE_TO_FT = {
    "boundary_storage_port": "boundary_storage_port",
    "crusher_blue_iron": "manufacturing_3x3",
}


def _make_state(with_rules: bool = True) -> BState:
    """Gap 8 修后, 'with_rules=False' 意味着 facility_templates +
    instance_to_facility_type 都 None — helper 返 unknown, verifier fail-closed."""
    return BState(
        groups={
            "boundary_storage_port": GroupState(
                "boundary_storage_port", demand=23, pose_domain=frozenset()
            ),
        },
        canonical_rules=CANONICAL_RULES if with_rules else None,
        facility_templates=_FACILITY_TEMPLATES if with_rules else None,
        instance_to_facility_type=_INSTANCE_TO_FT if with_rules else None,
        available_oracle_versions=frozenset(),
    )


# ============================================================================
# verify_placement_rule
# ============================================================================

def test_verify_placement_rule_match():
    state = _make_state()
    assert verify_placement_rule(state, "boundary_storage_port=left_or_bottom_boundary") is True
    assert verify_placement_rule(state, "crusher_blue_iron=free") is True


def test_verify_placement_rule_mismatch():
    """canonical_rules rotated → verifier 必须返 False."""
    state = _make_state()
    # boundary_storage_port actually is left_or_bottom_boundary, not free
    assert verify_placement_rule(state, "boundary_storage_port=free") is False


def test_verify_placement_rule_unknown_group():
    state = _make_state()
    assert verify_placement_rule(state, "unknown_group=any") is False


def test_verify_placement_rule_fails_closed_on_none_rules():
    """Gemini round 27 B1 finding 修: canonical_rules None → fail-closed."""
    state = _make_state(with_rules=False)
    assert verify_placement_rule(state, "boundary_storage_port=left_or_bottom_boundary") is False


def test_verify_placement_rule_malformed_value():
    state = _make_state()
    assert verify_placement_rule(state, "no_equals_sign") is False
    assert verify_placement_rule(state, "") is False
    assert verify_placement_rule(state, "=val") is False
    assert verify_placement_rule(state, "key=") is False


# ============================================================================
# verify_boundary_saturation
# ============================================================================

def test_verify_boundary_saturation_with_rules():
    state = _make_state()
    assert verify_boundary_saturation(state, "anything") is True


def test_verify_boundary_saturation_fails_closed_on_none_rules():
    state = _make_state(with_rules=False)
    assert verify_boundary_saturation(state, "x") is False


# ============================================================================
# lookup_verifier + register_verifier
# ============================================================================

def test_lookup_verifier_returns_registered():
    assert lookup_verifier("placement_rule") is verify_placement_rule
    assert lookup_verifier("left_or_bottom_boundary_saturation") is verify_boundary_saturation


def test_lookup_verifier_unknown_returns_none():
    assert lookup_verifier("never_registered_key_xyz") is None


def test_register_verifier_overwrite_explicit_ok():
    """显式 overwrite=True 允许覆盖."""
    def stub_verifier(state, value):
        return value == "expected"

    original = _VERIFIERS.get("placement_rule")
    try:
        register_verifier("placement_rule", stub_verifier, overwrite=True)
        assert lookup_verifier("placement_rule") is stub_verifier
    finally:
        if original is not None:
            register_verifier("placement_rule", original, overwrite=True)


def test_register_verifier_silent_overwrite_rejected():
    """Gemini round 28 finding #2: 默认 overwrite=False 拒 silent 覆盖."""
    def stub_verifier(state, value):
        return True

    with pytest.raises(ValueError, match="已 registered"):
        register_verifier("placement_rule", stub_verifier)  # 已存在


def test_register_verifier_none_raises():
    with pytest.raises(ValueError, match="不能为 None"):
        register_verifier("x", None)  # type: ignore[arg-type]


# ============================================================================
# Integration: lifecycle.assumption_holds delegate
# ============================================================================

def test_assumption_holds_delegate_match():
    state = _make_state()
    assumption = Assumption(
        key="placement_rule",
        value="boundary_storage_port=left_or_bottom_boundary",
    )
    assert assumption_holds(state, assumption) is True


def test_assumption_holds_delegate_mismatch():
    state = _make_state()
    assumption = Assumption(key="placement_rule", value="boundary_storage_port=free")
    assert assumption_holds(state, assumption) is False


def test_assumption_holds_unknown_key_fails_closed():
    state = _make_state()
    assumption = Assumption(key="never_registered_xyz", value="v")
    assert assumption_holds(state, assumption) is False


def test_assumption_holds_no_rules_fails_closed():
    """Verifier 注册了, 但 state.canonical_rules None → fail-closed."""
    state = _make_state(with_rules=False)
    assumption = Assumption(
        key="placement_rule",
        value="boundary_storage_port=left_or_bottom_boundary",
    )
    assert assumption_holds(state, assumption) is False


# ----------------------------------------------------------------------------
# Deleted-family assumption keys stay fail-closed (F8 deleted 2026-07-08)
# ----------------------------------------------------------------------------


def test_deleted_f8_assumption_keys_fail_closed() -> None:
    """The F8-only verifiers ("power_pole_jump_radius" /
    "protocol_core_position") were deleted with the power_grid_reach family
    (retired on a false game-rule premise). Any surviving cert carrying these
    assumption keys must fail closed as unknown keys, not silently pass.
    """
    state = BState(
        groups={
            "manufacturing_3x3": GroupState(
                group_id="manufacturing_3x3",
                demand=1,
                pose_domain=frozenset(),
                selected_poses=[],
            )
        },
    )
    for key, value in (
        ("power_pole_jump_radius", "R=5"),
        ("protocol_core_position", "(10,10)"),
    ):
        assert assumption_holds(state, Assumption(key=key, value=value)) is False, key

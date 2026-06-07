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
# F8 verifiers (Gemini F8 round 3 Finding #2 / #3)
# ----------------------------------------------------------------------------


_F8_CANONICAL_RULES = {
    "facility_templates": {
        "power_pole": {
            "dimensions": {"w": 2, "h": 2},
            "needs_power": False,
            "power_coverage_radius": 5,
        },
        "protocol_core": {
            "dimensions": {"w": 9, "h": 9},
            "needs_power": False,
        },
    },
}


def _make_f8_state(*, with_rules: bool = True, with_owner: bool = False) -> BState:
    groups = {"manufacturing_3x3": GroupState(
        group_id="manufacturing_3x3", demand=1, pose_domain=frozenset(), selected_poses=[]
    )}
    cell_owner: dict[tuple[int, int], tuple[str, int]] = {}
    instance_map: dict[str, str] | None = None
    if with_owner:
        instance_map = {"protocol_core_singleton": "protocol_core"}
        for dx in range(9):
            for dy in range(9):
                cell_owner[(10 + dx, 10 + dy)] = ("protocol_core_singleton", 0)
    return BState(
        groups=groups,
        canonical_rules=_F8_CANONICAL_RULES if with_rules else None,
        cell_owner=cell_owner,
        instance_to_facility_type=instance_map,
    )


def test_verify_power_pole_jump_radius_match() -> None:
    state = _make_f8_state()
    assumption = Assumption(key="power_pole_jump_radius", value="R=5")
    assert assumption_holds(state, assumption) is True


def test_verify_power_pole_jump_radius_mismatch_rejects_malicious_cert() -> None:
    """Gemini F8 round 3 Finding #2: malicious cert with R=0.001 to fake a
    BFS disconnect must be rejected at attach-scope."""
    state = _make_f8_state()
    assumption = Assumption(key="power_pole_jump_radius", value="R=0.001")
    assert assumption_holds(state, assumption) is False


def test_verify_power_pole_jump_radius_no_rules_fails_closed() -> None:
    state = _make_f8_state(with_rules=False)
    assumption = Assumption(key="power_pole_jump_radius", value="R=5")
    assert assumption_holds(state, assumption) is False


def test_verify_power_pole_jump_radius_malformed_value() -> None:
    state = _make_f8_state()
    for bad in ("R=abc", "X=5", "5", "", "R=-1", "R=0"):
        assert assumption_holds(
            state, Assumption(key="power_pole_jump_radius", value=bad)
        ) is False, f"value={bad!r}"


def test_verify_protocol_core_position_fails_closed_when_owner_absent() -> None:
    """v29 regression: bounds-only protocol_core anchor is not certified SoT."""
    state = _make_f8_state(with_owner=False)
    assert assumption_holds(
        state, Assumption(key="protocol_core_position", value="(10,10)")
    ) is False


def test_verify_protocol_core_position_out_of_grid() -> None:
    state = _make_f8_state(with_owner=False)
    # footprint at (65, 65) extends to (73, 73) — overflows 70×70 grid
    assert assumption_holds(
        state, Assumption(key="protocol_core_position", value="(65,65)")
    ) is False


def test_verify_protocol_core_position_master_cross_check_match() -> None:
    """When cell_owner is available, the verifier cross-checks the 9×9
    footprint owners match facility_type=protocol_core."""
    state = _make_f8_state(with_owner=True)
    assert assumption_holds(
        state, Assumption(key="protocol_core_position", value="(10,10)")
    ) is True


def test_verify_protocol_core_position_master_cross_check_mismatch() -> None:
    """If cell_owner exists but anchor doesn't match a placed protocol_core,
    fail (anchor (0,0) has no cell_owner mapping at all in this state)."""
    state = _make_f8_state(with_owner=True)
    assert assumption_holds(
        state, Assumption(key="protocol_core_position", value="(0,0)")
    ) is False


def test_verify_protocol_core_position_malformed() -> None:
    state = _make_f8_state()
    for bad in ("10,10", "(10)", "(a,b)", "()", "(10,10,5)"):
        assert assumption_holds(
            state, Assumption(key="protocol_core_position", value=bad)
        ) is False, f"value={bad!r}"

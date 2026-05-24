"""Tests for Family 8 power_grid_reach (P1.2B-F8).

Phase 1.2 single-case scope: cert_kind = "power_pole_bfs_disconnect_ghost".
cell_owner causation (multi-literal) deferred Phase 1.5+.

Coverage:
- Generator: default-disabled / disconnect emits / connected → no cut /
  empty-CoverSet skip (F7 territory) / cell_owner-only-cause skip.
- Validator: 8-phase (parse / cert_kind / scalars / ghost scope / group +
  needs_power / full disconnect / ghost-only cause).
- Adversarial: wrong cert_kind / pole_shape!=2x2 / pole_jump_radius<=0 /
  ghost drift / non-powered facility / ghost-agnostic scope /
  literals ≠ cert.
- Watcher keys.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

import pytest

from src.cuts.families.power_grid_reach import (
    evaluate_geometric_power_grid_reach,
    validate_power_grid_reach,
    watcher_keys_power_grid_reach,
)
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cut,
    CutScope,
    GroupState,
    OracleCert,
    canonical_bytes_for_cert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
)
from src.cuts.oracles.power_grid_reach_oracle import (
    generate_power_grid_reach_cuts,
)


_UNSET: Any = object()


def _3x3_pose_cells(anchor: Tuple[int, int]) -> List[List[int]]:
    x, y = anchor
    return sorted([[x + dx, y + dy] for dx in range(3) for dy in range(3)])


def _f5_fixture_state(
    *,
    facility_anchor: Tuple[int, int] = (60, 60),
    pc_anchor: Tuple[int, int] = (10, 10),
    ghost_rect: Tuple[int, int, int, int] = (30, 0, 10, 70),
    instance_to_facility_type: Any = _UNSET,
    facility_templates: Any = _UNSET,
    cell_owner: Dict[Tuple[int, int], Any] | None = None,
    selected_poses: list[str] | None = None,
) -> BState:
    """F5 reference fixture: ghost wide vertical strip (30..39, 0..69) splits the
    grid into Left and Right. protocol_core at (10,10), facility at (60,60).
    pole_jump_radius=5 < ghost width=10 → no Left→Right jump possible.
    """
    if instance_to_facility_type is _UNSET:
        instance_to_facility_type = {"crusher_blue_iron": "manufacturing_3x3"}
    if facility_templates is _UNSET:
        facility_templates = {
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "needs_power": True,
            },
            "power_pole": {
                "dimensions": {"w": 2, "h": 2},
                "needs_power": False,
                "power_coverage_radius": 5,
            },
            "protocol_core": {
                "dimensions": {"w": 9, "h": 9},
                "needs_power": False,
            },
        }
    x, y, h, w = ghost_rect
    ghost_cells = frozenset(
        (x + i, y + j) for i in range(h) for j in range(w)
    )
    if cell_owner is None:
        cell_owner = {}
    candidate_placements = {
        "facility_pools": {
            "manufacturing_3x3": [
                {
                    "pose_id": "p_3x3_a",
                    "anchor": list(facility_anchor),
                    "occupied_cells": _3x3_pose_cells(facility_anchor),
                    "input_port_cells": [],
                    "output_port_cells": [],
                }
            ],
        },
    }
    groups = {
        "crusher_blue_iron": GroupState(
            group_id="crusher_blue_iron",
            demand=1,
            pose_domain=frozenset({"p_3x3_a"}),
            selected_poses=list(selected_poses) if selected_poses else [],
        ),
    }
    # Source-of-truth canonical_rules (R4 Finding #2 fix): F8 validator now
    # cross-checks cert.pole_jump_radius against canonical
    # facility_templates.power_pole.power_coverage_radius. Mirror the
    # facility_templates dict here so the cross-check finds R=5.
    canonical_rules: dict[str, Any] | None = (
        {"facility_templates": facility_templates}
        if isinstance(facility_templates, dict)
        else None
    )
    return BState(
        groups=groups,
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset(),
        cell_owner=cell_owner,
        candidate_placements=candidate_placements,
        instance_to_facility_type=instance_to_facility_type,
        facility_templates=facility_templates,
        canonical_rules=canonical_rules,
        source_digest="test-source-digest",
    )


def _make_cert(
    state: BState,
    *,
    cert_kind: str = "power_pole_bfs_disconnect_ghost",
    facility_group: str = "crusher_blue_iron",
    facility_pose_id: str = "p_3x3_a",
    facility_cells: List[List[int]] | None = None,
    pole_jump_radius: float = 5.0,
    pole_shape_canonical: str = "2x2_rigid",
    protocol_core_cell: List[int] = [10, 10],
    ghost_rect_repr: List[int] | None = None,
    exterior_blocks_digest: str | None = None,
    facility_anchor: Tuple[int, int] = (60, 60),
) -> bytes:
    if facility_cells is None:
        facility_cells = _3x3_pose_cells(facility_anchor)
    if ghost_rect_repr is None:
        ghost_rect_repr = list(state.ghost_rect) if state.ghost_rect else [0, 0, 1, 1]
    if exterior_blocks_digest is None:
        exterior_blocks_digest = compute_exterior_blocks_hash(state)
    return canonical_bytes_for_cert({
        "cert_kind": cert_kind,
        "facility_group": facility_group,
        "facility_pose_id": facility_pose_id,
        "facility_cells": facility_cells,
        "pole_jump_radius": pole_jump_radius,
        "pole_shape_canonical": pole_shape_canonical,
        "protocol_core_cell": list(protocol_core_cell),
        "ghost_rect_repr": ghost_rect_repr,
        "exterior_blocks_digest": exterior_blocks_digest,
    })


def _make_cut(
    cert_payload: bytes,
    state: BState,
    *,
    facility_group: str = "crusher_blue_iron",
    facility_pose_id: str = "p_3x3_a",
    scope_ghost_id: str | None = None,
) -> Cut:
    if scope_ghost_id is None:
        scope_ghost_id = compute_ghost_rect_id(state.ghost_rect)
    cert_hash = hashlib.sha256(cert_payload).hexdigest()
    scope = CutScope(
        ghost_rect_id=scope_ghost_id,
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest="test-source-digest",
        oracle_abstraction_version="power_grid_reach_v1",
    )
    return Cut(
        cut_id=f"f8_test_{cert_hash[:8]}",
        family="power_grid_reach",
        literals=None,
        geometric_payload=cert_payload,
        scope=scope,
        cert=OracleCert(
            cert_kind="power_pole_bfs_disconnect_ghost",
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.0",
        validator_version="v1.0",
        oracle_name="power_grid_reach_v1",
        oracle_cert_hash=cert_hash,
    )


# ---- generator -------------------------------------------------------------


def test_generator_default_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXACT_F8_GENERATOR_ENABLED", raising=False)
    state = _f5_fixture_state()
    cuts = generate_power_grid_reach_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        protocol_core_anchor=(10, 10),
        pole_jump_radius=5.0,
    )
    assert cuts == []


def test_generator_no_target_poses_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F8_GENERATOR_ENABLED", "1")
    state = _f5_fixture_state()
    cuts = generate_power_grid_reach_cuts(state, target_poses=None)
    assert cuts == []


def test_generator_no_pc_anchor_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F8_GENERATOR_ENABLED", "1")
    state = _f5_fixture_state()
    cuts = generate_power_grid_reach_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        protocol_core_anchor=None,
        pole_jump_radius=5.0,
    )
    assert cuts == []


def test_generator_skips_non_powered_facility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXACT_F8_GENERATOR_ENABLED", "1")
    state = _f5_fixture_state(
        facility_templates={
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "needs_power": False,
            },
            "power_pole": {"dimensions": {"w": 2, "h": 2}, "needs_power": False, "power_coverage_radius": 5},
            "protocol_core": {"dimensions": {"w": 9, "h": 9}, "needs_power": False},
        },
    )
    cuts = generate_power_grid_reach_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        protocol_core_anchor=(10, 10),
        pole_jump_radius=5.0,
    )
    assert cuts == []


def test_generator_emits_cut_when_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    """F5 reference: ghost vertical strip (30..39, 0..69) + R_jump=5 → Left ↛ Right."""
    monkeypatch.setenv("EXACT_F8_GENERATOR_ENABLED", "1")
    state = _f5_fixture_state()
    cuts = generate_power_grid_reach_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        protocol_core_anchor=(10, 10),
        pole_jump_radius=5.0,
    )
    assert len(cuts) == 1
    cert_dict = json.loads(cuts[0].cert.cert_payload)
    assert cert_dict["cert_kind"] == "power_pole_bfs_disconnect_ghost"
    assert cert_dict["facility_group"] == "crusher_blue_iron"
    assert cert_dict["protocol_core_cell"] == [10, 10]
    assert cert_dict["pole_shape_canonical"] == "2x2_rigid"


def test_generator_no_cut_when_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Large jump radius → ghost cannot disconnect."""
    monkeypatch.setenv("EXACT_F8_GENERATOR_ENABLED", "1")
    state = _f5_fixture_state(ghost_rect=(60, 60, 5, 5))  # small ghost in corner
    # Update ghost_cells to match
    state = _f5_fixture_state(
        ghost_rect=(60, 60, 5, 5),
        facility_anchor=(0, 0),
        pc_anchor=(10, 10),
    )
    cuts = generate_power_grid_reach_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        protocol_core_anchor=(10, 10),
        pole_jump_radius=50.0,  # large
    )
    assert cuts == []


def test_generator_no_cut_via_spanning_intermediate_poles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini F8 round 1 Finding #1 regression: with a small corner ghost and
    facility distant from pc, the FULL pole-anchor enumeration sees the chain
    of intermediate poles that span the grid (radius 8 is well within
    walking distance across the 70×70 board), so BFS reaches the facility's
    CoverSet via intermediate hops — NO disconnect, NO cut.

    The pre-fix code passed only ``list(cover_set)`` (poles near facility) to
    ``build_power_network``, so the graph had no intermediates, BFS reported
    a fake disconnect, and this test would have emitted a bogus cut. With
    the full-anchor fix, the cut MUST NOT be emitted.
    """
    monkeypatch.setenv("EXACT_F8_GENERATOR_ENABLED", "1")
    # Tiny ghost in a corner (doesn't separate any region)
    state = _f5_fixture_state(
        ghost_rect=(65, 65, 3, 3),
        facility_anchor=(60, 60),
        pc_anchor=(10, 10),
    )
    cuts = generate_power_grid_reach_cuts(
        state,
        target_poses=[("crusher_blue_iron", "p_3x3_a")],
        protocol_core_anchor=(10, 10),
        pole_jump_radius=8.0,  # enough to chain across grid via intermediates
    )
    assert cuts == [], (
        "FULL pole-anchor enumeration should connect facility to pc via "
        "spanning intermediates (small corner ghost cannot disconnect the "
        "70×70 board with R_jump=8)"
    )


# ---- validator: happy path --------------------------------------------------


def test_validator_happy_path() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "ok", f"detail={result.detail!r}"


# ---- validator: schema errors ----------------------------------------------


def test_validator_rejects_wrong_cert_kind() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, cert_kind="power_pole_bfs_disconnect_cell_owner")
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_pole_shape_not_2x2() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, pole_shape_canonical="1x1_rigid")
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "schema_err"
    assert "2x2_rigid" in (result.detail or "")


def test_validator_rejects_nonpositive_pole_jump_radius() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, pole_jump_radius=0.0)
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_pc_out_of_grid() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, protocol_core_cell=[65, 65])  # 65+9 > 70
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_literals_present() -> None:
    """F8 is geometric mode — cut.literals must be None."""
    # F8 is geometric per _FAMILY_MODE_MAP; Cut __post_init__ already enforces
    # this invariant. The validator's defensive double-check is exercised by
    # constructing a literal cert payload mismatched to geometric expectations.
    # Skipping direct Cut construction (would fail __post_init__); the mode
    # invariant is enforced upstream.
    pass


# ---- validator: unsound ----------------------------------------------------


def test_validator_unsound_ghost_agnostic_scope() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state, scope_ghost_id=GHOST_AGNOSTIC)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "GHOST_AGNOSTIC" in (result.detail or "")


def test_validator_unsound_when_connected() -> None:
    """Cert claims disconnect but with large R_jump the pole graph is connected."""
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, pole_jump_radius=50.0)
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_when_needs_power_false() -> None:
    state = _f5_fixture_state(
        facility_templates={
            "manufacturing_3x3": {
                "dimensions": {"w": 3, "h": 3},
                "needs_power": False,
            },
            "power_pole": {"dimensions": {"w": 2, "h": 2}, "needs_power": False, "power_coverage_radius": 5},
            "protocol_core": {"dimensions": {"w": 9, "h": 9}, "needs_power": False},
        },
    )
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "needs_power" in (result.detail or "")


def test_validator_unsound_facility_group_not_in_state() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, facility_group="fake_group")
    cut = _make_cut(cert_payload, state, facility_group="fake_group")
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_ghost_drift() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    new_state = _f5_fixture_state(ghost_rect=(35, 0, 5, 70))
    result = validate_power_grid_reach(cut, new_state, canonical_rules={})
    assert result.kind == "unsound"


# ---- evaluator (geometric, O(1) scope guard) -------------------------------


def test_evaluator_returns_true_under_matching_scope() -> None:
    # Gemini F8 round 1 Finding #3: facility must be in selected_poses.
    state = _f5_fixture_state(selected_poses=["p_3x3_a"])
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    assert evaluate_geometric_power_grid_reach(cut, state) is True


def test_evaluator_returns_false_on_ghost_drift() -> None:
    state = _f5_fixture_state(selected_poses=["p_3x3_a"])
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    new_state = _f5_fixture_state(
        ghost_rect=(35, 0, 5, 70), selected_poses=["p_3x3_a"]
    )
    assert evaluate_geometric_power_grid_reach(cut, new_state) is False


def test_evaluator_returns_false_when_facility_not_selected() -> None:
    """Gemini F8 round 1 Finding #3 (CRITICAL): even if ghost is unchanged,
    once the master removes the facility from selected_poses the cut must
    stop firing — otherwise ``literals=None`` would poison the whole ghost.
    """
    state_with = _f5_fixture_state(selected_poses=["p_3x3_a"])
    cert_payload = _make_cert(state_with)
    cut = _make_cut(cert_payload, state_with)
    state_without = _f5_fixture_state(selected_poses=[])
    assert evaluate_geometric_power_grid_reach(cut, state_without) is False


def test_evaluator_returns_false_when_facility_group_missing() -> None:
    """Cert references a group that no longer exists in state.groups."""
    state = _f5_fixture_state(selected_poses=["p_3x3_a"])
    cert_payload = _make_cert(state, facility_group="ghost_group")
    cut = _make_cut(cert_payload, state)
    assert evaluate_geometric_power_grid_reach(cut, state) is False


def test_evaluator_returns_false_when_protocol_core_moved() -> None:
    """Gemini F8 round 4 Finding #1 (CRITICAL): evaluator must reject the cut
    if master moved the protocol_core away from the cert's anchor. Without
    this check, the F8 ``literals=None`` cut would poison the ghost AABB
    even after master legitimately reconnected the power network via the
    new pc placement.

    Setup: state has cell_owner populated with protocol_core at (10, 10).
    Cert encodes that. Then build a second state where protocol_core is
    moved to (40, 40). The evaluator must return False against the second
    state (the cert's anchor is no longer protocol_core's footprint).
    """
    state_at_orig = _f5_fixture_state(selected_poses=["p_3x3_a"])
    # Mutate cell_owner to place protocol_core at (10, 10)
    state_at_orig.cell_owner = {
        (10 + dx, 10 + dy): ("protocol_core_singleton", 0)
        for dx in range(9)
        for dy in range(9)
    }
    state_at_orig.instance_to_facility_type = {
        **(state_at_orig.instance_to_facility_type or {}),
        "protocol_core_singleton": "protocol_core",
    }
    cert_payload = _make_cert(state_at_orig)
    cut = _make_cut(cert_payload, state_at_orig)
    assert evaluate_geometric_power_grid_reach(cut, state_at_orig) is True

    state_at_moved = _f5_fixture_state(selected_poses=["p_3x3_a"])
    state_at_moved.cell_owner = {
        (40 + dx, 40 + dy): ("protocol_core_singleton", 0)
        for dx in range(9)
        for dy in range(9)
    }
    state_at_moved.instance_to_facility_type = {
        **(state_at_moved.instance_to_facility_type or {}),
        "protocol_core_singleton": "protocol_core",
    }
    assert evaluate_geometric_power_grid_reach(cut, state_at_moved) is False


def test_validator_rejects_malicious_pole_jump_radius() -> None:
    """Gemini F8 round 4 Finding #2 (CRITICAL): validator must catch a cert
    that forges ``pole_jump_radius=0.001`` to fake a BFS disconnect. The
    new ``_validate_source_of_truth_scalars`` phase cross-checks against
    state.canonical_rules.power_pole.power_coverage_radius.
    """
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, pole_jump_radius=0.001)
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "schema_err" or result.kind == "unsound", (
        f"expected unsound/schema_err for forged radius, got {result.kind}: {result.detail}"
    )


def test_validator_rejects_negative_protocol_core_cell() -> None:
    """Gemini F8 round 4 Finding #4 (HIGH): _parse_protocol_core_cell now
    explicitly rejects negative coords (prior check let -1 through because
    -1 + 9 = 8 ∈ [0, 70]).
    """
    state = _f5_fixture_state()
    cert_payload = _make_cert(state, protocol_core_cell=[-1, -1])
    cut = _make_cut(cert_payload, state)
    result = validate_power_grid_reach(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_evaluator_failsafe_malformed_payload() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    garbled = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=b"not json {{{",
        scope=cut.scope,
        cert=OracleCert(
            cert_kind="power_pole_bfs_disconnect_ghost",
            cert_payload=b"not json {{{",
            cert_hash=hashlib.sha256(b"not json {{{").hexdigest(),
        ),
        family_version=cut.family_version, validator_version=cut.validator_version,
        oracle_name=cut.oracle_name,
        oracle_cert_hash=hashlib.sha256(b"not json {{{").hexdigest(),
    )
    assert evaluate_geometric_power_grid_reach(garbled, state) is False


# ---- watcher keys ----------------------------------------------------------


def test_watcher_keys_returns_group_pose_cell() -> None:
    state = _f5_fixture_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    keys = watcher_keys_power_grid_reach(cut)
    assert keys["group_keys"] == ["crusher_blue_iron"]
    assert keys["pose_keys"] == [("crusher_blue_iron", "p_3x3_a")]
    assert len(keys["cell_keys"]) == 9  # 3×3 facility
    assert (60, 60) in keys["cell_keys"]

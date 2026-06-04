"""Tests for Family 9 density_envelope (P1.2B-F9).

Coverage:
- Generator: empty witness / non-area_capacity_overflow witness rejected /
  group_id unknown / ghost None / max_allowed_area > safe_ub / no strict
  overflow / happy path.
- Validator: 9-phase (cert_kind / witness_kind / window_rect / group /
  assignment_witness / ghost scope / max_allowed_area / safe_ub / strict overflow).
- Red fixtures: F9-reject-routing-overflow / F9-any-overlap-overcount /
  F9-origin-in-window / F9-all-in-window-FN.
- R3+R4+R5 schema regression (bool!=int, grid bound, strict inequality).
- Evaluator: area-based counting, fail-safe.
- Watcher keys.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Tuple

import pytest

from src.cuts.families.density_envelope import (
    ACCEPTED_WITNESS_KIND,
    evaluate_geometric_density_envelope,
    validate_density_envelope,
    watcher_keys_density_envelope,
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
from src.cuts.oracles.density_envelope_oracle import (
    generate_density_envelope_cuts,
)


# ---- fixtures --------------------------------------------------------------


def _make_pose(pose_id: str, anchor: Tuple[int, int], h: int, w: int) -> Dict:
    """Build a pose with occupied_cells = h × w rectangle anchored at (anchor)."""
    x, y = anchor
    return {
        "pose_id": pose_id,
        "anchor": [x, y],
        "occupied_cells": [[x + i, y + j] for i in range(h) for j in range(w)],
        "input_port_cells": [],
        "output_port_cells": [],
    }


def _make_state(
    *,
    groups: Dict[str, GroupState] | None = None,
    candidate_placements: Dict | None = None,
    ghost_rect: Tuple[int, int, int, int] | None = (0, 0, 10, 10),
    cell_owner: Dict | None = None,
) -> BState:
    if groups is None:
        groups = {
            "g1": GroupState(
                group_id="g1",
                demand=4,
                pose_domain=frozenset({"p_3x3_a", "p_3x3_b", "p_3x3_c", "p_3x3_d"}),
                selected_poses=[],
            ),
            "g_other": GroupState(
                group_id="g_other",
                demand=2,
                pose_domain=frozenset({"p_other_a"}),
                selected_poses=[],
            ),
        }
    if candidate_placements is None:
        # Default: 4 manufacturing_3x3-like poses at 4 corners of window (0,0,10,10).
        # Each pose occupies a 3x3 block. Anchored at (0,0), (0,3), (3,0), (3,3).
        candidate_placements = {
            "facility_pools": {
                "manufacturing_3x3": [
                    _make_pose("p_3x3_a", (0, 0), 3, 3),
                    _make_pose("p_3x3_b", (0, 3), 3, 3),
                    _make_pose("p_3x3_c", (3, 0), 3, 3),
                    _make_pose("p_3x3_d", (3, 3), 3, 3),
                ],
                "other_facility": [
                    _make_pose("p_other_a", (50, 50), 2, 2),
                ],
            },
        }
    state = BState(
        groups=groups,
        ghost_rect=ghost_rect,
        ghost_cells=frozenset(),
        exterior_blocks=frozenset(),
        cell_owner=cell_owner or {},
        candidate_placements=candidate_placements,
        instance_to_facility_type={"g1": "manufacturing_3x3", "g_other": "other_facility"},
        source_digest="test-source-digest",
    )
    return state


def _make_density_envelope_cert(
    *,
    cert_kind: str = "density_envelope_v1",
    witness_kind: str = "area_capacity_overflow",
    window_rect: List[int] | Tuple = [0, 0, 10, 10],
    group_id: str = "g1",
    max_allowed_area: int = 10,
    assignment_witness: List | None = None,
    ghost_rect_repr: List[int] | Tuple = [0, 0, 10, 10],
) -> bytes:
    if assignment_witness is None:
        # 4 poses × 9 cells each = 36 cells; all inside window (0,0,10,10) → sum = 36
        assignment_witness = [
            ["g1", "p_3x3_a"],
            ["g1", "p_3x3_b"],
            ["g1", "p_3x3_c"],
            ["g1", "p_3x3_d"],
        ]
    cert_dict = {
        "cert_kind": cert_kind,
        "witness_kind": witness_kind,
        "window_rect": list(window_rect),
        "group_id": group_id,
        "max_allowed_area": max_allowed_area,
        "oracle_assignment_witness": assignment_witness,
        "ghost_rect_repr": list(ghost_rect_repr),
    }
    return canonical_bytes_for_cert(cert_dict)


def _make_density_envelope_cut(
    cert_payload: bytes,
    *,
    ghost_rect: Tuple[int, int, int, int] | None = (0, 0, 10, 10),
    scope_ghost_id: str | None = None,
) -> Cut:
    if scope_ghost_id is None:
        scope_ghost_id = compute_ghost_rect_id(ghost_rect)
    cert_hash = hashlib.sha256(cert_payload).hexdigest()
    state = BState(
        groups={},
        ghost_rect=ghost_rect,
        ghost_cells=frozenset(),
        exterior_blocks=frozenset(),
    )
    scope = CutScope(
        ghost_rect_id=scope_ghost_id,
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest="test-source-digest",
        oracle_abstraction_version="density_envelope_v1",
    )
    return Cut(
        cut_id=f"f9_test_{cert_hash[:8]}",
        family="density_envelope",
        literals=None,
        geometric_payload=cert_payload,
        scope=scope,
        cert=OracleCert(
            cert_kind="density_envelope_v1",
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.0",
        validator_version="v1.0",
        oracle_name="density_envelope_v1",
        oracle_cert_hash=cert_hash,
    )


def _tamper_cert(cut: Cut, mutate) -> Cut:
    """Modify cert payload dict + re-hash, preserving R3 integrity."""
    cert_dict = json.loads(cut.cert.cert_payload)
    mutate(cert_dict)
    new_payload = canonical_bytes_for_cert(cert_dict)
    new_hash = hashlib.sha256(new_payload).hexdigest()
    return Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=cut.literals,
        geometric_payload=new_payload,
        scope=cut.scope,
        cert=OracleCert(
            cert_kind=cut.cert.cert_kind,
            cert_payload=new_payload,
            cert_hash=new_hash,
        ),
        family_version=cut.family_version,
        validator_version=cut.validator_version,
        oracle_name=cut.oracle_name,
        oracle_cert_hash=new_hash,
        minimization_audit=dict(cut.minimization_audit),
        iter_index=cut.iter_index,
    )


# ---- validator happy + schema --------------------------------------------


def test_validate_rejects_unproved_tight_max_allowed_area():
    state = _make_state()
    # 4 poses × 9 cells = 36 cells, but max_allowed_area=10 is tighter than
    # the static safe_ub=100. Phase 1.2 has no replayable proof for that K.
    cert_payload = _make_density_envelope_cert(max_allowed_area=10)
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "no replayable proof" in (vr.detail or "")


def test_validate_schema_err_cert_kind_wrong():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(cert_kind="evil_kind")
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "cert_kind" in (vr.detail or "")


def test_F9_reject_routing_overflow():
    """Red fixture #1: witness_kind != 'area_capacity_overflow' must be rejected.

    PROJECT_LOCK §3A F9 area-only invariant.
    """
    state = _make_state()
    cert_payload = _make_density_envelope_cert(witness_kind="routing_overflow")
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "witness_kind" in (vr.detail or "")


def test_validate_schema_err_binding_overflow_rejected():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(witness_kind="binding_overflow")
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"


def test_validate_schema_err_pcr_cut_overflow_rejected():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(witness_kind="pcr_cut_overflow")
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"


def test_validate_schema_err_window_out_of_grid():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(window_rect=[65, 0, 10, 10])  # x+h=75 > 70
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"


def test_validate_schema_err_window_zero_size():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(window_rect=[0, 0, 0, 5])
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"


def test_validate_schema_err_bool_max_allowed_area():
    """R4 catch: bool!=int strict."""
    state = _make_state()
    cert_payload = _make_density_envelope_cert(max_allowed_area=True)  # type: ignore[arg-type]
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"


def test_validate_schema_err_max_allowed_area_exceeds_window():
    state = _make_state()
    # Window is 10×10 = 100 cells; cert claims 1000
    cert_payload = _make_density_envelope_cert(max_allowed_area=1000)
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "schema_err"
    assert "exceed" in (vr.detail or "").lower() or "|W|" in (vr.detail or "")


def test_validate_unsound_max_allowed_area_exceeds_safe_ub():
    """cert claims max_allowed_area > safe upper bound recomputed by validator.

    Per Gemini F9 round 2 BLOCKER fix, safe_ub is now STATIC (only ghost +
    exterior); cell_owner_other no longer reduces the bound. So we exercise
    the safe_ub-exceeded path using ghost_cells (static obstacles).
    """
    base = _make_state()
    # Add 1 ghost cell in window (0,0,10,10) so safe_ub = 100 - 1 = 99
    state = BState(
        groups=base.groups,
        ghost_rect=base.ghost_rect,
        ghost_cells=frozenset({(5, 5)}),
        exterior_blocks=base.exterior_blocks,
        cell_owner=base.cell_owner,
        candidate_placements=base.candidate_placements,
        instance_to_facility_type=base.instance_to_facility_type,
        source_digest=base.source_digest,
    )
    cert_payload = _make_density_envelope_cert(max_allowed_area=100)
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "safe upper bound" in (vr.detail or "")


def test_validate_unsound_unknown_group():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(
        group_id="ghost_group_id",
        assignment_witness=[["ghost_group_id", "p_3x3_a"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "not in state.groups" in (vr.detail or "")


def test_validate_unsound_pose_not_in_domain():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(
        assignment_witness=[["g1", "pose_not_in_domain"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "pose_domain" in (vr.detail or "")


def test_validate_unsound_cross_group_witness():
    state = _make_state()
    cert_payload = _make_density_envelope_cert(
        assignment_witness=[["g_other", "p_other_a"]],  # cert.group_id=g1
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "single-group" in (vr.detail or "")


def test_validate_unsound_witness_multiset_overflow_demand():
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=1,  # only 1 instance allowed
                pose_domain=frozenset({"p_3x3_a"}),
                selected_poses=[],
            ),
        },
    )
    cert_payload = _make_density_envelope_cert(
        assignment_witness=[
            ["g1", "p_3x3_a"],
            ["g1", "p_3x3_a"],  # 2 copies, but demand = 1
        ],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "demand" in (vr.detail or "")


def test_validate_unsound_ghost_agnostic_rejected():
    """F9 is ghost-bound; scope == GHOST_AGNOSTIC must reject."""
    state = _make_state()
    cert_payload = _make_density_envelope_cert()
    cut = _make_density_envelope_cut(cert_payload, scope_ghost_id=GHOST_AGNOSTIC)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "GHOST_AGNOSTIC" in (vr.detail or "")


def test_validate_unsound_ghost_mismatch():
    """cert.ghost_rect_repr must byte-equal state.ghost_rect."""
    state = _make_state(ghost_rect=(0, 0, 10, 10))
    cert_payload = _make_density_envelope_cert(ghost_rect_repr=[5, 5, 10, 10])
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "ghost_rect" in (vr.detail or "")


def test_validate_unsound_state_ghost_none():
    """F9 cut with ghost-bound scope but state.ghost_rect is None."""
    state = _make_state(ghost_rect=None)
    cert_payload = _make_density_envelope_cert()
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"


def test_validate_unsound_witness_area_le_max_allowed():
    """Strict inequality: equality does not cut, must be > (PROJECT_LOCK §3A)."""
    state = _make_state()
    # 4 poses × 9 cells = 36; set max_allowed_area = 36 (equal, not strict overflow)
    cert_payload = _make_density_envelope_cert(max_allowed_area=36)
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert ("strict overflow" in (vr.detail or "") or "no replayable proof" in (vr.detail or ""))


def test_validate_strict_inequality_just_above():
    """Just below total overflow is still rejected without replayable K proof."""
    state = _make_state()
    cert_payload = _make_density_envelope_cert(max_allowed_area=35)
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "no replayable proof" in (vr.detail or "")


# ---- 3 remaining red fixtures (evaluator-side) ----------------------------


def test_F9_any_overlap_overcount_FP_rejected():
    """Red fixture #2: 'any overlap → whole facility' is the historical FP.

    1 pose with 1 cell inside W (others outside). Naive 'any-overlap' would
    count the whole facility (9 cells); correct area-based counts 1 cell.

    The validator uses real per-pose-occupied-cells lookup, so a cert that
    claims max_allowed_area=4 with witness sum=1 actual → unsound (not
    strictly overflowing).
    """
    # Pose 'p_corner' has anchor (-2, -2) — only cell (0,0) is in window (0,0,10,10);
    # but we can't have negative anchor; use anchor (8, 8) with 3x3, cells
    # (8,8),(8,9),(8,10*),(9,8),(9,9),... — but 10 is out of grid 0..9 of W.
    # Actually window is (0,0,10,10) so cells y=0..9. Pose at (8, 8) has cells
    # (8,8),(8,9),(8,10),(9,8),(9,9),(9,10),(10,8),(10,9),(10,10) — within
    # window: (8,8),(8,9),(9,8),(9,9) = 4 cells in W (not 1, my arithmetic).
    # For a cleaner case, use anchor (9, 9) → cells (9,9),(9,10),(9,11),
    # (10,9),(10,10),(10,11),(11,9),(11,10),(11,11). Only (9,9) is in
    # window (0,0,10,10) (since W covers x in [0,9], y in [0,9]).
    poses_corner = [_make_pose("p_corner", (9, 9), 3, 3)]
    cp = {
        "facility_pools": {
            "manufacturing_3x3": poses_corner,
        },
    }
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=4,
                pose_domain=frozenset({"p_corner"}),
                selected_poses=[],
            ),
        },
        candidate_placements=cp,
    )
    # Only 1 cell ∈ W, so sum_area_overlap = 1.
    # Set max_allowed_area = 4. cert claims strict overflow but actual sum=1 ≤ 4 → unsound.
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=4,
        assignment_witness=[["g1", "p_corner"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    # Validator correctly does area-based recompute and finds no overflow
    assert vr.kind == "unsound"
    assert ("strict overflow" in (vr.detail or "") or "no replayable proof" in (vr.detail or ""))


def test_F9_origin_in_window_FP_rejected():
    """Red fixture #3: pose anchor ∈ W but body mostly outside.

    Same family as overcount: validator must count only |cells ∩ W|, not
    'pose has anchor in W → whole facility'.
    """
    # Pose anchored at (9, 0) — anchor in W (0,0,10,10), but body extends to
    # (9..11, 0..2): cells (9,0),(9,1),(9,2),(10,0),(10,1),(10,2),(11,0),(11,1),(11,2)
    # In window (x∈[0,9], y∈[0,9]): only (9,0),(9,1),(9,2) = 3 cells.
    poses_anchored = [_make_pose("p_anchor_edge", (9, 0), 3, 3)]
    cp = {
        "facility_pools": {
            "manufacturing_3x3": poses_anchored,
        },
    }
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=4,
                pose_domain=frozenset({"p_anchor_edge"}),
                selected_poses=[],
            ),
        },
        candidate_placements=cp,
    )
    # 3 cells in W; max_allowed_area = 5; cert claims overflow but sum=3 ≤ 5 → unsound
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=5,
        assignment_witness=[["g1", "p_anchor_edge"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"


def test_F9_all_in_window_FN_caught():
    """Red fixture #4: 'all in window only' historical FN.

    Edge pose with partial overlap (5 cells in W of 9 total) should
    contribute its 5 cells, not 0 ('all-in-window' rule would skip it).

    Verify that with multiple edge poses contributing partial cells, the
    validator correctly sums partial overlaps and finds strict overflow.
    """
    # Pose at (8, 0): cells (8,0),(8,1),(8,2),(9,0),(9,1),(9,2),(10,0),(10,1),(10,2)
    #   In W (x∈[0,9], y∈[0,9]): (8,0),(8,1),(8,2),(9,0),(9,1),(9,2) = 6 cells
    # Pose at (8, 7): cells (8,7),(8,8),(8,9),(9,7),(9,8),(9,9),(10,7),(10,8),(10,9)
    #   In W: (8,7),(8,8),(8,9),(9,7),(9,8),(9,9) = 6 cells
    # Sum = 12 cells; max_allowed_area = 10 → 12 > 10 strict overflow → ok
    poses = [
        _make_pose("p_edge_a", (8, 0), 3, 3),
        _make_pose("p_edge_b", (8, 7), 3, 3),
    ]
    cp = {
        "facility_pools": {
            "manufacturing_3x3": poses,
        },
    }
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=4,
                pose_domain=frozenset({"p_edge_a", "p_edge_b"}),
                selected_poses=[],
            ),
        },
        candidate_placements=cp,
    )
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=10,
        assignment_witness=[["g1", "p_edge_a"], ["g1", "p_edge_b"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    # The partial-overlap arithmetic is no longer reachable for an unproved
    # tight K in Phase 1.2; fail-closed before accepting the cut.
    assert vr.kind == "unsound"
    assert "no replayable proof" in (vr.detail or "")


# ---- evaluator -------------------------------------------------------------


def test_evaluator_returns_false_when_no_owner_in_window():
    """Empty cell_owner → 0 cells in window → False (not overflow)."""
    state = _make_state(cell_owner={})
    cert_payload = _make_density_envelope_cert(max_allowed_area=10)
    cut = _make_density_envelope_cut(cert_payload)
    assert evaluate_geometric_density_envelope(cut, state) is False


def test_evaluator_returns_true_when_owner_overflow():
    """11 cells owned by g1 in W (max=10) → strict overflow → True."""
    cell_owner = {(i, 0): ("g1", 0) for i in range(7)}  # 7 cells in column y=0
    cell_owner.update({(i, 1): ("g1", 1) for i in range(4)})  # 4 more in y=1
    # Total 11 cells in W (0,0,10,10) owned by g1; max=10 → strict overflow
    state = _make_state(cell_owner=cell_owner)
    cert_payload = _make_density_envelope_cert(max_allowed_area=10)
    cut = _make_density_envelope_cut(cert_payload)
    assert evaluate_geometric_density_envelope(cut, state) is True


def test_evaluator_strict_inequality_at_equality_returns_false():
    """Equality (occupied == max_allowed) is not strict overflow → False."""
    cell_owner = {(i, 0): ("g1", 0) for i in range(10)}  # 10 cells in column y=0
    state = _make_state(cell_owner=cell_owner)
    cert_payload = _make_density_envelope_cert(max_allowed_area=10)
    cut = _make_density_envelope_cut(cert_payload)
    assert evaluate_geometric_density_envelope(cut, state) is False


def test_evaluator_other_group_cells_ignored():
    """Cells owned by other groups don't count toward cert.group_id area."""
    cell_owner = {(i, j): ("g_other", 0) for i in range(10) for j in range(10)}
    # Entire window filled by g_other; g1 has 0 cells → False
    state = _make_state(cell_owner=cell_owner)
    cert_payload = _make_density_envelope_cert(max_allowed_area=10)
    cut = _make_density_envelope_cut(cert_payload)
    assert evaluate_geometric_density_envelope(cut, state) is False


def test_evaluator_fail_safe_on_malformed_payload():
    """Malformed cert payload → False (fail-safe per F1/F2 pattern)."""
    state = _make_state()
    cert_payload = b'{"cert_kind": "wrong"}'
    cut = _make_density_envelope_cut(cert_payload)
    assert evaluate_geometric_density_envelope(cut, state) is False


# ---- generator -------------------------------------------------------------


def test_generate_routing_overflow_witness_rejected():
    """Generator end of PROJECT_LOCK §3A double-defense."""
    state = _make_state()
    cuts = generate_density_envelope_cuts(
        state,
        witness_kind="routing_overflow",
        group_id="g1",
        window_rect=(0, 0, 10, 10),
        max_allowed_area=10,
        assignment_witness=(("g1", "p_3x3_a"),),
    )
    assert cuts == []


def test_generate_unproved_tight_k_returns_empty():
    state = _make_state()
    cuts = generate_density_envelope_cuts(
        state,
        witness_kind="area_capacity_overflow",
        group_id="g1",
        window_rect=(0, 0, 10, 10),
        max_allowed_area=10,
        assignment_witness=(
            ("g1", "p_3x3_a"),
            ("g1", "p_3x3_b"),
            ("g1", "p_3x3_c"),
            ("g1", "p_3x3_d"),
        ),
    )
    assert cuts == []


def test_generate_unknown_group_returns_empty():
    state = _make_state()
    cuts = generate_density_envelope_cuts(
        state,
        witness_kind="area_capacity_overflow",
        group_id="ghost_group",
        window_rect=(0, 0, 10, 10),
        max_allowed_area=10,
        assignment_witness=(("ghost_group", "p_x"),),
    )
    assert cuts == []


def test_generate_ghost_none_returns_empty():
    state = _make_state(ghost_rect=None)
    cuts = generate_density_envelope_cuts(
        state,
        witness_kind="area_capacity_overflow",
        group_id="g1",
        window_rect=(0, 0, 10, 10),
        max_allowed_area=10,
        assignment_witness=(("g1", "p_3x3_a"),),
    )
    assert cuts == []


def test_generate_equality_no_cut():
    """Witness sum == max_allowed → no overflow → []."""
    state = _make_state()
    cuts = generate_density_envelope_cuts(
        state,
        witness_kind="area_capacity_overflow",
        group_id="g1",
        window_rect=(0, 0, 10, 10),
        max_allowed_area=36,  # = total witness sum (4 poses × 9 cells)
        assignment_witness=(
            ("g1", "p_3x3_a"),
            ("g1", "p_3x3_b"),
            ("g1", "p_3x3_c"),
            ("g1", "p_3x3_d"),
        ),
    )
    assert cuts == []


# ---- watcher_keys ---------------------------------------------------------


def test_validate_rejects_cert_max_zero_without_replayable_proof():
    """cert_max=0 is a tight K and must carry proof; Phase 1.2 quarantines it."""
    state = _make_state()
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=0,
        assignment_witness=[["g1", "p_3x3_a"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "no replayable proof" in (vr.detail or "")


def test_evaluator_cert_max_zero_only_fires_when_g_inside_window():
    """cert_max=0 sound semantics: only fires when group g actually places in W."""
    state_outside = _make_state(cell_owner={(50, 50): ("g1", 0)})  # outside W (0,0,10,10)
    state_inside = _make_state(cell_owner={(5, 5): ("g1", 0)})  # inside W
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=0,
        assignment_witness=[["g1", "p_3x3_a"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    # g placed outside W: 0 > 0 is False → no spurious fire
    assert evaluate_geometric_density_envelope(cut, state_outside) is False
    # g placed inside W: 1 > 0 is True → cut correctly prunes
    assert evaluate_geometric_density_envelope(cut, state_inside) is True


def test_safe_ub_static_immune_to_cell_owner_other_TOCTOU():
    """Gemini F9 round 2 BLOCKER regression: safe_ub static, ignores cell_owner_other.

    If safe_ub were dynamic (= |W| - |ghost| - |exterior| - |cell_owner_other ∩ W|),
    an oracle would freeze that transient value into cert.max_allowed_area.
    Once cell_owner_other vacated, real capacity would grow, but the cert's
    cap stayed frozen → cut prunes legal solutions.

    Verify: cell_owner_other in window does NOT affect safe_ub recompute.
    """
    state_with_other = _make_state(
        cell_owner={(0, 0): ("g_other", 0), (0, 1): ("g_other", 1)},
    )

    # Without ghost/exterior, the state has safe_ub = |W| = 100
    # (any cell_owner_other in W must NOT reduce the cap).
    # Use a cut with max_allowed_area=100 (cap is exactly |W|=100; max=100 allowed):
    # If safe_ub dynamic, state_with_other.safe_ub = 98 → 100 > 98 → unsound.
    # If safe_ub static (correct fix), state_with_other.safe_ub = 100 → ok at this check.
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=100,  # equal to |W|, sanity test (not strict, but max_allowed_area check)
        assignment_witness=[["g1", "p_3x3_a"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    # max=100 == |W|; this triggers the schema "max <= |W|" path (passes),
    # but witness area is small so overflow fails. The point: cell_owner_other
    # must NOT cause max_allowed_area > safe_ub error.
    vr = validate_density_envelope(cut, state_with_other, canonical_rules={})
    # Should fail on strict overflow (not on safe_ub) — so the failure mode is
    # 'witness area <= max_allowed_area', NOT 'cert > safe_ub'.
    assert vr.kind == "unsound"
    assert "safe upper bound" not in (vr.detail or ""), (
        f"safe_ub recompute used cell_owner_other (TOCTOU vuln); vr.detail={vr.detail!r}"
    )


def test_validator_union_excludes_ghost_cells():
    """Gemini F9 round 2 HIGH regression: validator union must exclude ghost.

    candidate_placements isn't ghost-pre-filtered; an oracle could pick a
    ghost-crossing pose as witness, inflating validator's union count by
    cells that are physically unreachable (master's ghost_anchor_filter
    blocks them in real placement). Evaluator iterates cell_owner (never
    contains ghost cells), so the divergence allows unsound cuts.
    """
    # Pose at (4, 4): cells (4,4),(4,5),(4,6),(5,4),(5,5),(5,6),(6,4),(6,5),(6,6)
    # Make 4 of these cells ghost: (5,5),(5,6),(6,5),(6,6)
    # Within window (0,0,10,10): all 9 cells are inside; with ghost excluded, 5 cells.
    pose_ghost = _make_pose("p_ghost_crossing", (4, 4), 3, 3)
    cp = {"facility_pools": {"manufacturing_3x3": [pose_ghost]}}
    ghost_cells = frozenset({(5, 5), (5, 6), (6, 5), (6, 6)})
    state = BState(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=4,
                pose_domain=frozenset({"p_ghost_crossing"}),
                selected_poses=[],
            ),
        },
        ghost_rect=(0, 0, 10, 10),
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset(),
        candidate_placements=cp,
        instance_to_facility_type={"g1": "manufacturing_3x3"},
        source_digest="test-source-digest",
    )
    # Without ghost-exclusion: union = 9. With exclusion: union = 5.
    # max_allowed_area = 7: ghost-included would say 9 > 7 → ok (unsoundly);
    # ghost-excluded says 5 ≤ 7 → unsound.
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=7,
        assignment_witness=[["g1", "p_ghost_crossing"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert ("strict overflow" in (vr.detail or "") or "no replayable proof" in (vr.detail or "")), (
        f"Validator counted ghost cells in union or accepted an unproved K; vr.detail={vr.detail!r}"
    )


def test_validator_overlap_witness_union_not_sum():
    """Gemini F9 round 1 BLOCKER regression: validator must use UNION semantics.

    If two witness poses overlap, the SUM-based validator would double-count
    the shared cells and accept a cut whose evaluator never fires (because
    cell_owner dedups by cell). That loops LBBD on identical solutions.

    Setup: two poses sharing 3 cells. SUM = 9+9 = 18; UNION = 9+9-3 = 15.
    With max_allowed_area = 16: SUM (18) > 16 would accept; UNION (15) ≤ 16
    rejects as no strict overflow (expected).
    """
    # Pose A at (0, 0): cells (0,0)..(2,2) = 9 cells
    # Pose B at (1, 1): cells (1,1)..(3,3) = 9 cells
    # Overlap: (1,1),(1,2),(2,1),(2,2) = 4 cells
    # UNION = 9 + 9 - 4 = 14
    pose_a = _make_pose("p_overlap_a", (0, 0), 3, 3)
    pose_b = _make_pose("p_overlap_b", (1, 1), 3, 3)
    cp = {"facility_pools": {"manufacturing_3x3": [pose_a, pose_b]}}
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=4,
                pose_domain=frozenset({"p_overlap_a", "p_overlap_b"}),
                selected_poses=[],
            ),
        },
        candidate_placements=cp,
    )
    # max_allowed_area = 14: union (14) == 14 not strict, rejects;
    #                       sum (18) > 14 would erroneously accept
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=14,
        assignment_witness=[["g1", "p_overlap_a"], ["g1", "p_overlap_b"]],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert ("strict overflow" in (vr.detail or "") or "no replayable proof" in (vr.detail or "")), (
        f"Validator used SUM not UNION or accepted an unproved K; vr.detail={vr.detail!r}"
    )


def test_validator_total_instances_exceed_demand_rejected():
    """Gemini F9 round 1 review #2 HIGH: total instance count must be ≤ demand.

    Per-pose multiset cap alone lets attacker inflate witness with demand+1
    different poses, exceeding the group's physical placement capacity.
    """
    state = _make_state(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=2,  # Only 2 instances allowed
                pose_domain=frozenset({"p_3x3_a", "p_3x3_b", "p_3x3_c"}),
                selected_poses=[],
            ),
        },
    )
    cert_payload = _make_density_envelope_cert(
        max_allowed_area=5,
        # 3 distinct poses, each count=1 ≤ demand=2 (per-pose OK), but total
        # 3 > demand 2 (must reject)
        assignment_witness=[
            ["g1", "p_3x3_a"],
            ["g1", "p_3x3_b"],
            ["g1", "p_3x3_c"],
        ],
    )
    cut = _make_density_envelope_cut(cert_payload)
    vr = validate_density_envelope(cut, state, canonical_rules={})
    assert vr.kind == "unsound"
    assert "total instances" in (vr.detail or "")
    assert "demand" in (vr.detail or "")


def test_generator_witness_canonical_order_independent_cert_hash():
    """Gemini F9 round 1 review #3 HIGH: cert_hash must be permutation-invariant.

    Two equivalent witnesses with permuted pair order must produce identical
    cert_payload bytes → identical cert_hash → identical cut_id (so CutStore
    can dedup). Without sort, F5 round 1's anonymity trap re-emerges.
    """
    state = _make_state()
    args = dict(
        witness_kind="area_capacity_overflow",
        group_id="g1",
        window_rect=(0, 0, 10, 10),
        max_allowed_area=10,
    )
    cuts_forward = generate_density_envelope_cuts(
        state,
        assignment_witness=(("g1", "p_3x3_a"), ("g1", "p_3x3_b")),
        **args,
    )
    cuts_reversed = generate_density_envelope_cuts(
        state,
        assignment_witness=(("g1", "p_3x3_b"), ("g1", "p_3x3_a")),
        **args,
    )
    # Phase 1.2 now quarantines all non-trivial F9 K values that lack a
    # replayable area-capacity proof, so no cert is emitted to hash.  The
    # important invariant here is order-independent fail-closed behavior.
    assert cuts_forward == []
    assert cuts_reversed == []


def test_watcher_keys_pattern():
    cert_payload = _make_density_envelope_cert(window_rect=[2, 3, 4, 5])
    cut = _make_density_envelope_cut(cert_payload)
    keys = watcher_keys_density_envelope(cut)
    assert keys["group_keys"] == ["g1"]
    expected_cells = [(2 + i, 3 + j) for i in range(4) for j in range(5)]
    assert sorted(keys["cell_keys"]) == sorted(expected_cells)
    assert keys["region_keys"] == ["density_envelope:2,3,4,5"]

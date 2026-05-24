"""Tests for Family 6 shape_packing_hall (P1.2B-F6).

Coverage:
- Generator: happy F2 fixture / feasible / ghost None / no boundary group /
  pose_length<2 rejected / Phase 1.5+ region_demand override.
- Validator: 11-phase (parse / cert_kind / closed-enum / scalars / partition
  internal consistency / Hall witness strict / group source-of-truth /
  facility template match / ghost scope binding / partition recompute /
  recomputed max+Hall).
- Adversarial cert attacks (forged partition_lens / forged total_packable /
  ghost drift / exterior drift / fake group / pose_length=1 degenerate /
  pose_length×dimensions mismatch).
- Evaluator: strict inequality + fail-safe.
- Watcher keys.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

import pytest

from src.cuts.families.shape_packing_hall import (
    evaluate_geometric_shape_packing_hall,
    validate_shape_packing_hall,
    watcher_keys_shape_packing_hall,
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
from src.cuts.oracles.shape_packing_hall_oracle import (
    generate_shape_packing_hall_cuts,
)


# ---- fixtures --------------------------------------------------------------


_UNSET: Any = object()


def _make_state(
    *,
    groups: Dict[str, GroupState] | None = None,
    ghost_rect: Tuple[int, int, int, int] | None = (0, 4, 1, 1),
    ghost_cells: frozenset[Tuple[int, int]] | None = None,
    exterior_blocks: frozenset[Tuple[int, int]] | None = None,
    instance_to_facility_type: Any = _UNSET,
    facility_templates: Any = _UNSET,
) -> BState:
    if groups is None:
        groups = {
            "boundary_storage_port": GroupState(
                group_id="boundary_storage_port",
                demand=46,
                pose_domain=frozenset({"p0"}),
                selected_poses=[],
            ),
        }
    if ghost_cells is None:
        # ghost (0, 4, 1, 1) covers cell (0, 4) — but F6 looks at baseline
        # cells via region_kind. left_baseline = [(x, 0) for x in range(70)].
        # To bite into the baseline we want ghost cells overlapping (x, 0).
        # Use (0, 4, 1, 1) anchored at (x=0, y=4) → ghost covers cells
        # (0, 4) only (1×1 ghost). That doesn't touch (x, 0) cells.
        # For F2 fixture (left baseline split into [4, 5]), we need ghost
        # to cover (4, 0). Use ghost_cells = {(4, 0)} directly, ignore
        # ghost_rect→ghost_cells lookup (Phase 1.2 fixture).
        ghost_cells = frozenset({(4, 0)})
    if exterior_blocks is None:
        # Exterior covers cells 10..69 on left_baseline so partition is
        # restricted to first 10 cells (= F2 fixture: length 10 total).
        exterior_blocks = frozenset({(x, 0) for x in range(10, 70)})
    if instance_to_facility_type is _UNSET:
        instance_to_facility_type = {"boundary_storage_port": "boundary_storage_port"}
    if facility_templates is _UNSET:
        facility_templates = {
            "boundary_storage_port": {
                "dimensions": {"w": 1, "h": 3},
                "rotatable": True,
                "placement_rule": "left_or_bottom_boundary",
            },
        }
    return BState(
        groups=groups,
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=exterior_blocks,
        cell_owner={},
        candidate_placements={},
        instance_to_facility_type=instance_to_facility_type,
        facility_templates=facility_templates,
        source_digest="test-source-digest",
    )


def _make_cert(
    state: BState,
    *,
    cert_kind: str = "hall_interval_witness",
    region_kind: str = "left_baseline",
    region_total_length: int = 70,
    partition_lens: List[int] | None = None,
    partition_offsets: List[int] | None = None,
    pose_length: int = 3,
    pose_shape_canonical: str = "1x3_rigid",
    max_packable: List[int] | None = None,
    total_packable: int | None = None,
    contributing_group: str = "boundary_storage_port",
    region_demand: int = 3,
    group_demand: int = 46,
    ghost_rect_repr: List[int] | None = None,
    exterior_blocks_digest: str | None = None,
) -> bytes:
    if partition_lens is None:
        partition_lens = [4, 5]
    if partition_offsets is None:
        partition_offsets = [0, 5]
    if max_packable is None:
        max_packable = [L // pose_length for L in partition_lens]
    if total_packable is None:
        total_packable = sum(max_packable)
    if ghost_rect_repr is None:
        ghost_rect_repr = list(state.ghost_rect) if state.ghost_rect else [0, 0, 1, 1]
    if exterior_blocks_digest is None:
        exterior_blocks_digest = compute_exterior_blocks_hash(state)
    cert_dict = {
        "cert_kind": cert_kind,
        "region_kind": region_kind,
        "region_total_length": region_total_length,
        "partition_lens": list(partition_lens),
        "partition_offsets": list(partition_offsets),
        "pose_length": pose_length,
        "pose_shape_canonical": pose_shape_canonical,
        "max_packable": list(max_packable),
        "total_packable": total_packable,
        "contributing_group": contributing_group,
        "region_demand": region_demand,
        "group_demand": group_demand,
        "ghost_rect_repr": list(ghost_rect_repr),
        "exterior_blocks_digest": exterior_blocks_digest,
    }
    return canonical_bytes_for_cert(cert_dict)


def _make_cut(
    cert_payload: bytes,
    state: BState,
    *,
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
        oracle_abstraction_version="shape_packing_hall_v1",
    )
    return Cut(
        cut_id=f"f6_test_{cert_hash[:8]}",
        family="shape_packing_hall",
        literals=None,
        geometric_payload=cert_payload,
        scope=scope,
        cert=OracleCert(
            cert_kind="hall_interval_witness",
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.0",
        validator_version="v1.0",
        oracle_name="shape_packing_hall_v1",
        oracle_cert_hash=cert_hash,
    )


def _tamper_cert(cut: Cut, mutate) -> Cut:
    """Mutate cert dict + re-hash to satisfy Cut integrity guard."""
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
    )


# ---- generator -------------------------------------------------------------


def test_generator_f2_fixture_emits_cut() -> None:
    """F2 reference fixture: baseline length 10 split into [4, 5] by ghost+exterior,
    pose_length=3, region_demand=3 → ⌊4/3⌋+⌊5/3⌋=2 < 3 → INFEASIBLE."""
    state = _make_state()
    cuts = generate_shape_packing_hall_cuts(
        state,
        boundary_groups=["boundary_storage_port"],
        region_kinds=("left_baseline",),
        region_demand_overrides={("boundary_storage_port", "left_baseline"): 3},
    )
    assert len(cuts) == 1
    cert_dict = json.loads(cuts[0].cert.cert_payload)
    assert cert_dict["partition_lens"] == [4, 5]
    assert cert_dict["partition_offsets"] == [0, 5]
    assert cert_dict["max_packable"] == [1, 1]
    assert cert_dict["total_packable"] == 2
    assert cert_dict["region_demand"] == 3


def test_generator_feasible_returns_empty() -> None:
    """No ghost split → partition = [10], total_packable=⌊10/3⌋=3 ≥ region_demand 3
    (equality not violating per strict < invariant) → no cut."""
    state = _make_state(ghost_cells=frozenset())
    cuts = generate_shape_packing_hall_cuts(
        state,
        boundary_groups=["boundary_storage_port"],
        region_kinds=("left_baseline",),
        region_demand_overrides={("boundary_storage_port", "left_baseline"): 3},
    )
    assert cuts == []


def test_generator_phase_1_2_default_disabled() -> None:
    """Gemini F6 round 2 HIGH #2: Phase 1.2 default disabled — no overrides → no cuts.

    Single-region defaults are unsound for left_or_bottom_boundary groups:
    the demand can legally be met entirely on the other baseline.
    """
    # Fully block left baseline — even this trivial case must not emit
    # without explicit Phase 1.5+ override.
    state = _make_state(
        ghost_cells=frozenset(),
        exterior_blocks=frozenset({(x, 0) for x in range(70)}),
    )
    cuts = generate_shape_packing_hall_cuts(
        state,
        boundary_groups=["boundary_storage_port"],
        region_kinds=("left_baseline",),
    )
    assert cuts == []


def test_generator_skips_region_with_missing_override_key() -> None:
    """Gemini F6 round 2 HIGH #3: missing key = master plans 0 poses in region."""
    state = _make_state()
    # Override for left only — bottom is missing → bottom should be skipped.
    cuts = generate_shape_packing_hall_cuts(
        state,
        boundary_groups=["boundary_storage_port"],
        region_kinds=("left_baseline", "bottom_baseline"),
        region_demand_overrides={("boundary_storage_port", "left_baseline"): 3},
    )
    # left emits (partition [4,5] total=2 < 3). bottom skipped (no override).
    assert len(cuts) == 1
    cert = json.loads(cuts[0].cert.cert_payload)
    assert cert["region_kind"] == "left_baseline"


def test_generator_rejects_override_exceeding_capacity() -> None:
    """region_demand override beyond min(group_demand, region_cap) is skipped
    (would emit a cert validator phase 7 rejects)."""
    state = _make_state()
    cuts = generate_shape_packing_hall_cuts(
        state,
        boundary_groups=["boundary_storage_port"],
        region_kinds=("left_baseline",),
        # region_cap = 70//3 = 23. group_demand = 46. min = 23. 24 exceeds.
        region_demand_overrides={("boundary_storage_port", "left_baseline"): 24},
    )
    assert cuts == []


def test_generator_ghost_none_returns_empty() -> None:
    state = _make_state(ghost_rect=None)
    cuts = generate_shape_packing_hall_cuts(state)
    assert cuts == []


def test_generator_skips_pose_length_lt_2() -> None:
    """1×1 facility template → pose_length=1 (degenerates to F1) → skip."""
    state = _make_state(
        facility_templates={
            "boundary_storage_port": {
                "dimensions": {"w": 1, "h": 1},
                "placement_rule": "left_or_bottom_boundary",
            },
        },
    )
    cuts = generate_shape_packing_hall_cuts(state)
    assert cuts == []


def test_generator_auto_detect_boundary_groups() -> None:
    """Auto-detect via placement_rule == 'left_or_bottom_boundary'."""
    state = _make_state()
    cuts = generate_shape_packing_hall_cuts(
        state,
        region_kinds=("left_baseline",),
        region_demand_overrides={("boundary_storage_port", "left_baseline"): 3},
    )
    assert len(cuts) == 1


# ---- validator: happy path --------------------------------------------------


def test_validator_happy_path() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "ok", f"detail={result.detail!r}"


# ---- validator: schema errors ----------------------------------------------


def test_validator_rejects_wrong_cert_kind() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, cert_kind="density_envelope_v1")
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"
    assert "cert_kind" in (result.detail or "")


def test_validator_rejects_unknown_region_kind() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, region_kind="interior_rect")
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_pose_length_one_degenerate() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, pose_length=1, pose_shape_canonical="1x1_rigid",
                              max_packable=[4, 5], total_packable=9, region_demand=10)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"
    assert "pose_length" in (result.detail or "")


def test_validator_rejects_pose_shape_canonical_mismatch() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, pose_length=3, pose_shape_canonical="1x5_rigid")
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_partition_length_mismatch() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, partition_lens=[4, 5], partition_offsets=[0, 5, 10],
                              max_packable=[1, 1, 1])
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_partition_overlap() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, partition_lens=[5, 5], partition_offsets=[0, 3],
                              max_packable=[1, 1], total_packable=2)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_bool_in_partition_lens() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    tampered = _tamper_cert(cut, lambda d: d.__setitem__("partition_lens", [4, True]))
    result = validate_shape_packing_hall(tampered, state, canonical_rules={})
    assert result.kind == "schema_err"


def test_validator_rejects_max_packable_inconsistent() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, max_packable=[2, 2], total_packable=4, region_demand=5)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "schema_err"


# ---- validator: unsound (semantic violation) -------------------------------


def test_validator_unsound_when_hall_witness_equality() -> None:
    """total_packable == region_demand → not violating (strict < required)."""
    state = _make_state()
    # 3 segments of length 3 each → max_packable=[1,1,1] total=3, region_demand=3
    cert_payload = _make_cert(
        state,
        partition_lens=[3, 3, 3],
        partition_offsets=[0, 4, 7],
        max_packable=[1, 1, 1],
        total_packable=3,
        region_demand=3,
    )
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "strict" in (result.detail or "").lower() or ">=" in (result.detail or "")


def test_validator_unsound_when_group_demand_drift() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, group_demand=100)  # state has 46
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "source-of-truth" in (result.detail or "") or "group_demand" in (result.detail or "")


def test_validator_unsound_when_contributing_group_not_in_state() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, contributing_group="fake_group_xyz")
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_ghost_drift() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    # State ghost changes
    new_state = _make_state(ghost_rect=(5, 5, 1, 1), ghost_cells=frozenset({(5, 5)}))
    result = validate_shape_packing_hall(cut, new_state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_ghost_agnostic_scope() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state, scope_ghost_id=GHOST_AGNOSTIC)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "GHOST_AGNOSTIC" in (result.detail or "")


def test_validator_unsound_exterior_drift() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    # New state with different exterior (cells 12..69 instead of 10..69)
    new_state = _make_state(
        exterior_blocks=frozenset({(x, 0) for x in range(12, 70)}),
    )
    result = validate_shape_packing_hall(cut, new_state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_partition_drift_recompute() -> None:
    """Adversary plants partition_lens=[2,2,2] (max=0+0+0=0<3) but actual is [4,5]."""
    state = _make_state()
    cert_payload = _make_cert(
        state,
        partition_lens=[2, 2, 2],
        partition_offsets=[0, 3, 6],
        max_packable=[0, 0, 0],
        total_packable=0,
        region_demand=3,
    )
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "partition_lens drift" in (result.detail or "")


def test_validator_unsound_when_facility_templates_missing() -> None:
    """Gemini F6 round 1 BLOCKER #1: fail-closed when source-of-truth missing.

    Adversary plants fake cert (pose_length=35) without state.facility_templates
    — validator must return unsound, not silently pass.
    """
    state = _make_state(facility_templates=None)
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "source-of-truth" in (result.detail or "") or "facility_templates" in (result.detail or "")


def test_validator_unsound_when_instance_to_facility_type_missing() -> None:
    """Fail-closed: state.instance_to_facility_type=None → unsound."""
    state = _make_state(instance_to_facility_type=None)
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"
    assert "instance_to_facility_type" in (result.detail or "")


def test_validator_unsound_when_facility_type_not_in_templates() -> None:
    """Adversary names a gid whose facility_type isn't in facility_templates."""
    state = _make_state(
        instance_to_facility_type={"boundary_storage_port": "missing_type"},
    )
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"


def test_validator_unsound_facility_template_dimensions_mismatch() -> None:
    state = _make_state(
        facility_templates={
            "boundary_storage_port": {
                "dimensions": {"w": 1, "h": 5},  # actual 1×5
                "placement_rule": "left_or_bottom_boundary",
            },
        },
    )
    # Adversary plants pose_length=3 but canonical_rules says 5
    cert_payload = _make_cert(state, pose_length=3, pose_shape_canonical="1x3_rigid")
    cut = _make_cut(cert_payload, state)
    result = validate_shape_packing_hall(cut, state, canonical_rules={})
    assert result.kind == "unsound"


# ---- evaluator -------------------------------------------------------------


def test_evaluator_returns_true_when_hall_holds() -> None:
    state = _make_state()
    cert_payload = _make_cert(state, region_demand=3)
    cut = _make_cut(cert_payload, state)
    assert evaluate_geometric_shape_packing_hall(cut, state) is True


def test_evaluator_returns_false_at_equality() -> None:
    """Strict < required — equality returns False (does not cut)."""
    # Setup state where recomputed total_packable == region_demand.
    # partition [10] (no ghost split), pose_length=3 → max_packable=3.
    # region_demand=3 → equality, not violating.
    state = _make_state(ghost_cells=frozenset())  # no ghost split
    cert_payload = _make_cert(
        state,
        partition_lens=[10],
        partition_offsets=[0],
        max_packable=[3],
        total_packable=3,
        region_demand=3,
    )
    cut = _make_cut(cert_payload, state)
    assert evaluate_geometric_shape_packing_hall(cut, state) is False


def test_evaluator_returns_false_on_ghost_drift() -> None:
    """Gemini F6 round 2 CRITICAL #1: evaluator must scope-check before trusting payload.

    Cut was generated for ghost (0, 4, 1, 1). After ghost moves, evaluator
    is called with new state — payload would still say "violating" but the
    scope is invalid, so evaluator must return False.
    """
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    new_state = _make_state(ghost_rect=(5, 5, 1, 1), ghost_cells=frozenset({(5, 5)}))
    assert evaluate_geometric_shape_packing_hall(cut, new_state) is False


def test_evaluator_returns_false_on_exterior_drift() -> None:
    """Exterior change invalidates cut even though ghost matches."""
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    new_state = _make_state(
        exterior_blocks=frozenset({(x, 0) for x in range(12, 70)}),
    )
    assert evaluate_geometric_shape_packing_hall(cut, new_state) is False


def test_evaluator_failsafe_malformed_payload() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    # Replace geometric_payload with garbage
    garbled = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=b"not json {{{",
        scope=cut.scope,
        cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
        oracle_name=cut.oracle_name, oracle_cert_hash=cut.oracle_cert_hash,
    )
    assert evaluate_geometric_shape_packing_hall(garbled, state) is False


# ---- watcher keys ----------------------------------------------------------


def test_watcher_keys_returns_group_and_region() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    keys = watcher_keys_shape_packing_hall(cut)
    assert keys["group_keys"] == ["boundary_storage_port"]
    # Region-first prefix per spec §8 (Gemini F6 round 1 MEDIUM #3 fix).
    assert keys["region_keys"] == ["left_baseline:shape_hall"]
    # No cell_keys — F6 is cell_owner-independent per v1.1
    assert "cell_keys" not in keys


def test_watcher_keys_failsafe_on_malformed() -> None:
    state = _make_state()
    cert_payload = _make_cert(state)
    cut = _make_cut(cert_payload, state)
    garbled = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=b"not json {{{",
        scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
        oracle_name=cut.oracle_name, oracle_cert_hash=cut.oracle_cert_hash,
    )
    keys = watcher_keys_shape_packing_hall(garbled)
    assert keys == {"group_keys": [], "region_keys": []}

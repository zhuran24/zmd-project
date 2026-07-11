"""B2 vertical-slice and differential contracts for F1 region capacity.

These tests keep the Stage-B typed path production-disconnected: a real raw
``Cut`` is adapted and compiled, while tests explicitly interpret or lower the
resulting plan through the pre-B5 master seam.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, cast

import pytest
from ortools.sat.python import cp_model

from src.cuts import state_snapshot as snapshot_layer
from src.cuts.families.region_capacity import (
    RegionKind,
    _decode_region_bitset,
    compute_demand,
    compute_static_capacity,
    validate_region_capacity,
)
from src.cuts.families.region_capacity_typed import (
    RegionCapacityBody,
    RegionCapacityProof,
)
from src.cuts.frozen_artifacts import (
    FrozenArtifactBundle,
    build_frozen_artifact_bundle,
)
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    Assumption,
    BState,
    Cut,
    GroupState,
    ScopeIdentityPreimageV1,
    assumption_holds,
    compute_ghost_rect_id,
    compute_source_digest,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
from src.cuts.state_snapshot import (
    ValidatedStateSnapshot,
    build_validated_state_snapshot,
    master_domain_facility_pool_projection_v1,
    master_domain_projection_v1,
)
from src.cuts.typed_platform import (
    CapabilityStage,
    CompiledCut,
    ConstraintPlan,
    CutRejection,
    ModelScope,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.models.master_model import MasterPlacementModel


_ARTIFACT_HASHES = {
    "candidate_placements": "1" * 64,
    "canonical_rules": "2" * 64,
    "certified_exact_source_tree": "3" * 64,
    "commodity_demands": "4" * 64,
    "generic_io_requirements": "5" * 64,
    "mandatory_exact_instances": "6" * 64,
    "orbit_homogeneity_digest": "7" * 64,
    "preprocess_plan": "8" * 64,
}
_GROUP_ID = "group::miner::mining::0"
_SECOND_GROUP_ID = "group::miner::mining::1"
_FACILITY_TYPE = "miner"
_OPERATION_TYPE = "mining"
_POSES = (
    {
        "pose_id": "pose_left",
        "anchor": {"x": 0, "y": 0},
        "occupied_cells": [[0, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": "pose_mid",
        "anchor": {"x": 2, "y": 0},
        "occupied_cells": [[2, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": "pose_right",
        "anchor": {"x": 4, "y": 0},
        "occupied_cells": [[4, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
)
_OUTSIDE_POOL_POSE = {
    "pose_id": "pose_outside_region",
    "anchor": {"x": 10, "y": 10},
    "occupied_cells": [[10, 10]],
    "input_port_cells": [],
    "output_port_cells": [],
    "power_coverage_cells": None,
}
_UNION_CELLS = frozenset({(x, 0) for x in range(70)} | {(0, y) for y in range(70)})


def _build_state_and_bundle(
    *,
    capacity: int = 1,
    ghost_mode: str = "none",
    second_contributor: bool = False,
    unscoped_pool_pose: bool = False,
    template_dimensions: tuple[int, int] = (1, 1),
) -> tuple[BState, FrozenArtifactBundle]:
    """Build an F1 world whose union demand is two one-cell poses."""

    if ghost_mode == "none":
        ghost_rect = None
        ghost_cells: frozenset[tuple[int, int]] = frozenset()
    elif ghost_mode == "intersecting":
        ghost_rect = (0, 0, 1, 1)
        ghost_cells = frozenset({(0, 0)})
    elif ghost_mode == "disjoint":
        ghost_rect = (10, 10, 1, 1)
        ghost_cells = frozenset({(10, 10)})
    else:  # pragma: no cover - test helper guard
        raise AssertionError(f"unknown ghost_mode={ghost_mode!r}")

    blocked_in_union = len(_UNION_CELLS) - capacity
    exterior_count = blocked_in_union - len(ghost_cells & _UNION_CELLS)
    assert 0 <= exterior_count <= len(_UNION_CELLS - ghost_cells)
    exterior_blocks = frozenset(sorted(_UNION_CELLS - ghost_cells)[:exterior_count])
    facility_templates = {
        _FACILITY_TYPE: {
            "placement_rule": "left_or_bottom_boundary",
            "dimensions": {
                "w": template_dimensions[0],
                "h": template_dimensions[1],
            },
            "needs_power": False,
        }
    }
    canonical_rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": facility_templates,
    }
    pool_poses = [dict(pose) for pose in _POSES]
    if unscoped_pool_pose:
        pool_poses.append(dict(_OUTSIDE_POOL_POSE))
    candidate_placements = {"facility_pools": {_FACILITY_TYPE: pool_poses}}
    pose_domain = frozenset(str(pose["pose_id"]) for pose in _POSES)
    groups = {
        _GROUP_ID: GroupState(
            group_id=_GROUP_ID,
            demand=1 if second_contributor else 2,
            pose_domain=pose_domain,
        )
    }
    instance_to_facility_type = {_GROUP_ID: _FACILITY_TYPE}
    if second_contributor:
        groups[_SECOND_GROUP_ID] = GroupState(
            group_id=_SECOND_GROUP_ID,
            demand=1,
            pose_domain=pose_domain,
        )
        instance_to_facility_type[_SECOND_GROUP_ID] = _FACILITY_TYPE
    state = BState(
        groups=groups,
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=exterior_blocks,
        artifact_hashes=dict(_ARTIFACT_HASHES),
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
    )
    state.source_digest = compute_source_digest(state)
    bundle = build_frozen_artifact_bundle(
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
        artifact_hashes=_ARTIFACT_HASHES,
    )
    return state, bundle


def _assert_sha256(value: str) -> None:
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def _oracle_cut(state: BState) -> Cut:
    cuts = generate_region_capacity_cuts(state, state.canonical_rules or {})
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.scope is not None
    assert cut.scope.identity_preimage is not None
    return cut


def _compile_production_cut(
    *,
    ghost_mode: str = "none",
) -> tuple[BState, Cut, ValidatedStateSnapshot, CompiledCut]:
    state, bundle = _build_state_and_bundle(ghost_mode=ghost_mode)
    raw_cut = _oracle_cut(state)
    # Preserve the intended boundary order: raw v1 admission precedes the typed
    # snapshot/registry execution and does not receive a test-only scope bypass.
    envelope = cut_to_envelope_v1(raw_cut)
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )
    assert isinstance(result, CompiledCut)
    return state, raw_cut, snapshot, result


def _plan_parameters(plan: ConstraintPlan) -> tuple[dict[str, int], int]:
    raw_weights = plan.parameters["group_cell_weights"]
    raw_capacity = plan.parameters["capacity"]
    assert isinstance(raw_weights, Mapping)
    assert type(raw_capacity) is int
    weights: dict[str, int] = {}
    for group_id, raw_weight in raw_weights.items():
        assert type(group_id) is str
        assert type(raw_weight) is int
        weights[group_id] = raw_weight
    return weights, raw_capacity


def _interpret_region_plan(
    plan: ConstraintPlan,
    *,
    group_presence_counts: Mapping[str, int],
    condition_active: bool,
) -> bool:
    """Independent second implementation of ``region_capacity_le``."""

    assert plan.operation == "region_capacity_le"
    if plan.model_scope.ghost_policy == "bound" and not condition_active:
        return True
    weights, capacity = _plan_parameters(plan)
    activity = sum(weight * group_presence_counts.get(group_id, 0) for group_id, weight in weights.items())
    return activity <= capacity


def _plan_with_capacity(plan: ConstraintPlan, capacity: int) -> ConstraintPlan:
    weights, _old_capacity = _plan_parameters(plan)
    return ConstraintPlan(
        family=plan.family,
        schema_version=plan.schema_version,
        semantic_fingerprint="9" * 64,
        model_scope=plan.model_scope,
        operation=plan.operation,
        parameters={
            "capacity": capacity,
            "group_cell_weights": weights,
        },
    )


def _build_tiny_master(
    *,
    template_dimensions: tuple[int, int] = (1, 1),
    poses: Sequence[Mapping[str, object]] = _POSES,
    grid_width: int = 5,
) -> MasterPlacementModel:
    """Two mandatory miners sharing three disjoint one-cell poses."""

    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": _FACILITY_TYPE,
            "operation_type": _OPERATION_TYPE,
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_002",
            "facility_type": _FACILITY_TYPE,
            "operation_type": _OPERATION_TYPE,
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {_FACILITY_TYPE: [dict(pose) for pose in poses]}
    rules = {
        "globals": {"grid": {"width": grid_width, "height": 1}},
        "facility_templates": {
            _FACILITY_TYPE: {
                "dimensions": {
                    "w": template_dimensions[0],
                    "h": template_dimensions[1],
                },
                "needs_power": False,
            }
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def _lower_plan_for_test(
    plan: ConstraintPlan,
    master: MasterPlacementModel,
    *,
    condition_lits: Sequence[Any] = (),
) -> bool:
    weights, capacity = _plan_parameters(plan)
    return master.add_region_capacity_cut(
        group_cell_weights=weights,
        capacity=capacity,
        condition_lits=condition_lits,
    )


# ---------------------------------------------------------------------------
# Layer 1: real v1 admission, identity, assumptions, and result algebra
# ---------------------------------------------------------------------------


def test_production_raw_f1_cut_compiles_and_matches_legacy_validator() -> None:
    state, raw_cut, snapshot, compiled = _compile_production_cut()

    legacy = validate_region_capacity(raw_cut, state, state.canonical_rules or {})
    capability = build_production_registry().capabilities["region_capacity"]

    assert legacy.kind == "ok", legacy.detail
    assert capability.stage is CapabilityStage.COMPILABLE
    assert compiled.cut_id == raw_cut.cut_id
    assert compiled.snapshot_digest == snapshot.digest
    assert compiled.plan.family == "region_capacity"
    assert compiled.plan.operation == "region_capacity_le"
    assert _plan_parameters(compiled.plan) == ({_GROUP_ID: 1}, 1)


def test_f1_empty_literal_tuple_is_an_audited_typed_only_rejection() -> None:
    """The v1 adapter preserves strict geometric framing that legacy F1 lacks."""

    state, _bundle = _build_state_and_bundle()
    with_empty_literals = replace(_oracle_cut(state), literals=())

    legacy = validate_region_capacity(
        with_empty_literals,
        state,
        state.canonical_rules or {},
    )

    assert legacy.kind == "ok", legacy.detail
    with pytest.raises(ValueError, match="geometric cuts require literals to be None"):
        cut_to_envelope_v1(with_empty_literals)


def test_f1_plan_binds_full_snapshot_master_domain_and_semantic_identities() -> None:
    _state, _raw_cut, snapshot, compiled = _compile_production_cut()

    domain_fingerprint = compiled.plan.model_scope.domain_fingerprint
    semantic_fingerprint = compiled.plan.semantic_fingerprint

    assert domain_fingerprint == snapshot.master_domain_projection
    _assert_sha256(snapshot.master_domain_projection)
    _assert_sha256(domain_fingerprint)
    _assert_sha256(semantic_fingerprint)


def test_old_f1_cut_without_identity_preimage_fails_closed_at_adapter() -> None:
    state, _bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    old_scope = replace(raw_cut.scope, identity_preimage=None)

    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(replace(raw_cut, scope=old_scope))


@pytest.mark.parametrize(
    "legacy_hash_field",
    ["blocked_cells_hash", "exterior_blocks_hash"],
)
def test_f1_adapter_rejects_raw_preimage_legacy_hash_mismatch(
    legacy_hash_field: str,
) -> None:
    state, _bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    preimage = raw_cut.scope.identity_preimage
    assert isinstance(preimage, ScopeIdentityPreimageV1)
    assert len(raw_cut.scope.blocked_cells_hash) == 16
    assert len(raw_cut.scope.exterior_blocks_hash) == 16
    original_hash = cast(str, getattr(raw_cut.scope, legacy_hash_field))
    forged_hash = ("0" if original_hash[0] != "0" else "1") + original_hash[1:]
    forged_scope = replace(raw_cut.scope, **{legacy_hash_field: forged_hash})

    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(replace(raw_cut, scope=forged_scope))


def test_f1_adapter_rejects_ghost_id_that_differs_from_raw_preimage() -> None:
    state, _bundle = _build_state_and_bundle(ghost_mode="intersecting")
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    assert raw_cut.scope.ghost_rect_id != GHOST_AGNOSTIC
    original_id = raw_cut.scope.ghost_rect_id
    forged_id = ("0" if original_id[0] != "0" else "1") + original_id[1:]
    forged_scope = replace(raw_cut.scope, ghost_rect_id=forged_id)

    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(replace(raw_cut, scope=forged_scope))


def test_f1_oracle_assumptions_are_snapshot_verified() -> None:
    state, raw_cut, _snapshot, _compiled = _compile_production_cut()
    assert raw_cut.scope is not None
    assumptions = raw_cut.scope.active_assumptions

    assert {assumption.key for assumption in assumptions} == {
        "left_or_bottom_boundary_saturation",
        "placement_rule",
    }
    assert all(assumption_holds(state, assumption) for assumption in assumptions)


def test_f1_boundary_assumption_preserves_legacy_source_exists_semantics() -> None:
    state, bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    arbitrary_boundary = Assumption(
        key="left_or_bottom_boundary_saturation",
        value="arbitrary-non-empty-value-is-opaque-in-v1",
    )
    assumptions = tuple(
        arbitrary_boundary if assumption.key == arbitrary_boundary.key else assumption
        for assumption in raw_cut.scope.active_assumptions
    )
    assert assumption_holds(state, arbitrary_boundary)
    scope = replace(raw_cut.scope, active_assumptions=assumptions)
    envelope = cut_to_envelope_v1(replace(raw_cut, scope=scope))
    snapshot = build_validated_state_snapshot(state, bundle)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert isinstance(result, CompiledCut)


def test_f1_boundary_assumption_rejects_missing_canonical_source_like_legacy() -> None:
    state, bundle = _build_state_and_bundle()
    state.canonical_rules = None
    state.source_digest = compute_source_digest(state)
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    boundary = next(
        assumption
        for assumption in raw_cut.scope.active_assumptions
        if assumption.key == "left_or_bottom_boundary_saturation"
    )
    placement = next(
        assumption for assumption in raw_cut.scope.active_assumptions if assumption.key == "placement_rule"
    )
    assert not assumption_holds(state, boundary)
    assert assumption_holds(state, placement)

    envelope = cut_to_envelope_v1(raw_cut)
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert envelope.scope.source_digest == snapshot.source_digest
    assert not snapshot.canonical_rules_source_present
    assert isinstance(result, CutRejection)
    assert result.stage == "scope"


def test_f1_multiple_contributors_keep_repeated_placement_assumption_keys() -> None:
    state, bundle = _build_state_and_bundle(second_contributor=True)
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    placement_assumptions = tuple(
        assumption for assumption in raw_cut.scope.active_assumptions if assumption.key == "placement_rule"
    )

    # Repeated keys are required here: the values identify distinct contributor
    # groups and ScopeManifest must not collapse them into a key-only set.
    assert len(placement_assumptions) == 2
    assert {assumption.value.split("=", 1)[0] for assumption in placement_assumptions} == {
        _GROUP_ID,
        _SECOND_GROUP_ID,
    }
    assert all(assumption_holds(state, assumption) for assumption in placement_assumptions)

    envelope = cut_to_envelope_v1(raw_cut)
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert isinstance(result, CompiledCut)
    assert _plan_parameters(result.plan) == (
        {_GROUP_ID: 1, _SECOND_GROUP_ID: 1},
        1,
    )


@pytest.mark.parametrize(
    "bad_assumption",
    [
        Assumption(key="placement_rule", value=f"{_GROUP_ID}=free"),
        Assumption(key="unregistered_f1_assumption", value="true"),
    ],
    ids=("placement-rule-drift", "unknown-key"),
)
def test_f1_false_scope_assumption_returns_rejection(
    bad_assumption: Assumption,
) -> None:
    state, bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    retained = tuple(
        assumption for assumption in raw_cut.scope.active_assumptions if assumption.key != bad_assumption.key
    )
    tampered_scope = replace(
        raw_cut.scope,
        active_assumptions=(*retained, bad_assumption),
    )
    envelope = cut_to_envelope_v1(replace(raw_cut, scope=tampered_scope))
    snapshot = build_validated_state_snapshot(state, bundle)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert not assumption_holds(state, bad_assumption)
    assert isinstance(result, CutRejection)
    assert result.stage == "scope"


@pytest.mark.parametrize(
    "required_key",
    ["left_or_bottom_boundary_saturation", "placement_rule"],
    ids=("boundary-saturation", "placement-rule"),
)
def test_f1_missing_required_scope_assumption_returns_rejection(
    required_key: str,
) -> None:
    state, bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    incomplete_assumptions = tuple(
        assumption for assumption in raw_cut.scope.active_assumptions if assumption.key != required_key
    )
    assert len(incomplete_assumptions) < len(raw_cut.scope.active_assumptions)
    incomplete_scope = replace(
        raw_cut.scope,
        active_assumptions=incomplete_assumptions,
    )
    envelope = cut_to_envelope_v1(replace(raw_cut, scope=incomplete_scope))
    snapshot = build_validated_state_snapshot(state, bundle)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert isinstance(result, CutRejection)
    assert result.stage == "scope"


def test_redundant_bound_f1_scope_is_expected_typed_only_rejection() -> None:
    state, bundle = _build_state_and_bundle(ghost_mode="disjoint")
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    assert raw_cut.scope.ghost_rect_id == GHOST_AGNOSTIC
    assert state.ghost_rect is not None
    redundant_bound_scope = replace(
        raw_cut.scope,
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
    )
    redundant_bound = replace(raw_cut, scope=redundant_bound_scope)
    legacy = validate_region_capacity(
        redundant_bound,
        state,
        state.canonical_rules or {},
    )
    envelope = cut_to_envelope_v1(redundant_bound)
    snapshot = build_validated_state_snapshot(state, bundle)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert legacy.kind == "ok", legacy.detail
    assert isinstance(result, CutRejection)
    assert result.stage == "plan"


def test_f1_pose_domain_strict_subset_of_pool_is_typed_fail_closed() -> None:
    state, bundle = _build_state_and_bundle(unscoped_pool_pose=True)
    raw_cut = _oracle_cut(state)
    legacy = validate_region_capacity(raw_cut, state, state.canonical_rules or {})
    envelope = cut_to_envelope_v1(raw_cut)
    snapshot = build_validated_state_snapshot(state, bundle)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    # Expected tightening — ratified in spec §5.1 "B2 双审补拍板" (2026-07-11):
    # legacy validates only group.pose_domain, while the exact master lowering
    # enumerates the complete facility pool. Rejecting a strict subset prevents
    # unvalidated pool poses from being introduced into the lowered inequality.
    assert legacy.kind == "ok", legacy.detail
    assert isinstance(result, CutRejection)
    assert result.stage == "proof"


def test_f1_pose_cardinality_mismatch_is_typed_fail_closed_before_overcut() -> None:
    state, bundle = _build_state_and_bundle(
        capacity=3,
        template_dimensions=(2, 1),
    )
    raw_cut = _oracle_cut(state)
    legacy = validate_region_capacity(raw_cut, state, state.canonical_rules or {})
    envelope = cut_to_envelope_v1(raw_cut)
    snapshot = build_validated_state_snapshot(state, bundle)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    # The legacy chain trusts template width*height (=2) even though every pose
    # has one occupied cell.  Its lowering would therefore attach 2*presence<=3
    # and falsely exclude the two mandatory one-cell placements.
    assert legacy.kind == "ok", legacy.detail
    assert isinstance(result, CutRejection)
    assert result.stage == "proof"

    baseline_master = _build_tiny_master(template_dimensions=(2, 1))
    assert baseline_master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )

    attacked_master = _build_tiny_master(template_dimensions=(2, 1))
    assert attacked_master.add_region_capacity_cut(
        group_cell_weights={_GROUP_ID: 2},
        capacity=3,
    )
    assert attacked_master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_snapshot_pose_mode_ids_match_real_master_decimal_token_order() -> None:
    poses: tuple[Mapping[str, object], ...] = (
        {
            "pose_id": "relative_two",
            "anchor": {"x": 0, "y": 0},
            "occupied_cells": [[2, 0]],
            "pose_params": {"orientation": "", "port_mode": ""},
        },
        {
            "pose_id": "relative_ten",
            "anchor": {"x": 0, "y": 0},
            "occupied_cells": [[10, 0]],
            "pose_params": {"orientation": "", "port_mode": ""},
        },
    )
    candidate_placements = {
        "facility_pools": {
            _FACILITY_TYPE: [dict(pose) for pose in poses],
        }
    }
    facility_templates = {
        _FACILITY_TYPE: {
            "placement_rule": "left_or_bottom_boundary",
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
        }
    }
    bundle = build_frozen_artifact_bundle(
        canonical_rules={
            "globals": {"grid": {"width": 12, "height": 1}},
            "facility_templates": facility_templates,
        },
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type={_GROUP_ID: _FACILITY_TYPE},
        artifact_hashes=_ARTIFACT_HASHES,
    )
    pose_cells = snapshot_layer._freeze_pose_occupied_cells(  # noqa: SLF001
        bundle.candidate_placements
    )
    frozen_pools = cast(
        Mapping[str, Any],
        bundle.candidate_placements["facility_pools"],
    )
    registrations, _pose_tuple_by_key = snapshot_layer._master_domain_pose_registrations(  # noqa: SLF001
        frozen_pools,
        pose_cells,
    )

    master = _build_tiny_master(
        poses=poses,
        grid_width=12,
    )
    delegate = master._coordinate_delegate
    assert delegate is not None
    real_pose_tuples = delegate._template_pose_tuple_by_idx[_FACILITY_TYPE]
    raw_registration = cast(dict[str, object], registrations[0])
    projected_poses = cast(list[dict[str, object]], raw_registration["poses"])
    projected_pose_tuples = {
        cast(int, pose["pose_index"]): (
            cast(list[int], pose["anchor"])[0],
            cast(list[int], pose["anchor"])[1],
            cast(int, pose["mode_id"]),
        )
        for pose in projected_poses
    }

    # The master sorts decimal footprint-key strings ("10" before "2"), not
    # numeric relative-cell tuples.  The snapshot projection must be byte-for-
    # byte equivalent to that actual index construction.
    assert projected_pose_tuples == real_pose_tuples


def test_snapshot_and_live_master_rows_share_one_domain_projection_schema() -> None:
    state, bundle = _build_state_and_bundle()
    snapshot = build_validated_state_snapshot(state, bundle)
    master = _build_tiny_master()
    delegate = master._coordinate_delegate
    assert delegate is not None

    live_registration_rows: list[object] = []
    live_pools = {_FACILITY_TYPE: master.facility_pools[_FACILITY_TYPE]}
    pose_tuples = delegate._template_pose_tuple_by_idx[_FACILITY_TYPE]
    live_registration_rows.append(
        {
            "facility_type": _FACILITY_TYPE,
            "poses": [
                {
                    "anchor": [pose_tuple[0], pose_tuple[1]],
                    "mode_id": pose_tuple[2],
                    "pose_id": str(master.facility_pools[_FACILITY_TYPE][pose_index]["pose_id"]),
                    "pose_index": pose_index,
                }
                for pose_index, pose_tuple in sorted(pose_tuples.items())
            ],
        }
    )
    live_slot_rows: list[object] = []
    for group_id, slots in sorted(delegate.mandatory_slots.items()):
        if group_id != _GROUP_ID:
            continue
        for slot in slots:
            live_slot_rows.append(
                {
                    "allowed_pose_tuples": [list(pose_tuple) for pose_tuple in sorted(slot.allowed_tuples)],
                    "candidate_pose_count": slot.candidate_pose_count,
                    "facility_type": slot.template,
                    "group_id": group_id,
                    "slot_index": slot.slot_index,
                    # B2 dual-review codex#2: live rows carry the master's real
                    # slot.key — equality with the snapshot-derived key proves
                    # the projection detects master-side key drift.
                    "slot_key": str(slot.key),
                    "slot_kind": "mandatory",
                    "template_dimensions": [slot.dims[0], slot.dims[1]],
                }
            )

    live_projection = master_domain_projection_v1(
        family_subset="region_capacity",
        facility_pool_projection=master_domain_facility_pool_projection_v1(live_pools),
        mandatory_slot_rows=live_slot_rows,
        template_pose_registration_rows=live_registration_rows,
    )

    assert live_projection == snapshot.master_domain_projection


# ---------------------------------------------------------------------------
# Layer 2: frozen proof/helper facts -> typed plan projection
# ---------------------------------------------------------------------------


def test_f1_proof_helper_and_compiler_project_the_same_plan_parameters() -> None:
    state, raw_cut, snapshot, compiled = _compile_production_cut()
    assert raw_cut.cert is not None
    cert = json.loads(raw_cut.cert.cert_payload)
    assert type(cert) is dict
    region_kind = cast(RegionKind, cert["region_kind"])
    region_cells = _decode_region_bitset(cast(str, cert["region_cells_bitset_b64"]))
    contributors = [
        (cast(str, item[0]), cast(int, item[1])) for item in cast(list[list[object]], cert["contributing_groups"])
    ]
    cells_per_pose = cast(dict[str, int], cert["cells_per_pose"])
    registry = build_production_registry()
    plugin = registry.plugins["region_capacity"]
    envelope = cut_to_envelope_v1(raw_cut)

    proof = plugin.parse_and_validate_proof(envelope.proof_payload, snapshot)
    body = plugin.derive_body(proof)
    direct_plan = plugin.compile(body, proof, snapshot)
    plugin.validate_plan(direct_plan, proof, snapshot)

    assert isinstance(proof, RegionCapacityProof)
    assert isinstance(body, RegionCapacityBody)
    assert compute_static_capacity(region_cells, state) == cert["cap_R"] == 1
    assert (
        compute_demand(
            region_kind,
            contributors,
            cells_per_pose,
            state,
        )
        == cert["demand_R"]
        == 2
    )
    assert _plan_parameters(direct_plan) == ({_GROUP_ID: 1}, 1)
    assert direct_plan == compiled.plan


def test_f1_oracle_does_not_emit_when_demand_equals_capacity() -> None:
    state, _bundle = _build_state_and_bundle(capacity=2)

    assert generate_region_capacity_cuts(state, state.canonical_rules or {}) == []


# ---------------------------------------------------------------------------
# Layer 3: independent plan interpreter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("capacity", "presence_count", "expected"),
    [(1, 1, True), (1, 2, False), (2, 2, True)],
)
def test_independent_f1_plan_interpreter_capacity_boundary(
    capacity: int,
    presence_count: int,
    expected: bool,
) -> None:
    _state, _raw_cut, _snapshot, compiled = _compile_production_cut()
    plan = _plan_with_capacity(compiled.plan, capacity)

    assert (
        _interpret_region_plan(
            plan,
            group_presence_counts={_GROUP_ID: presence_count},
            condition_active=True,
        )
        is expected
    )


def test_independent_f1_plan_interpreter_makes_bound_plan_dormant() -> None:
    _state, _raw_cut, _snapshot, compiled = _compile_production_cut(ghost_mode="intersecting")

    assert compiled.plan.model_scope.ghost_policy == "bound"
    assert _interpret_region_plan(
        compiled.plan,
        group_presence_counts={_GROUP_ID: 2},
        condition_active=False,
    )
    assert not _interpret_region_plan(
        compiled.plan,
        group_presence_counts={_GROUP_ID: 2},
        condition_active=True,
    )


# ---------------------------------------------------------------------------
# Layer 4: real tiny CP-SAT master through the pre-B5 lowering seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("capacity", "expected_feasible"),
    [(1, False), (2, True)],
)
def test_f1_agnostic_plan_matches_interpreter_on_real_tiny_master(
    capacity: int,
    expected_feasible: bool,
) -> None:
    _state, _raw_cut, _snapshot, compiled = _compile_production_cut()
    plan = _plan_with_capacity(compiled.plan, capacity)
    master = _build_tiny_master()

    assert plan.model_scope.ghost_policy == "agnostic"
    assert _lower_plan_for_test(plan, master)
    status = master.solve(time_limit_seconds=5.0)

    interpreted = _interpret_region_plan(
        plan,
        group_presence_counts={_GROUP_ID: 2},
        condition_active=True,
    )
    assert interpreted is expected_feasible
    assert (status in (cp_model.OPTIMAL, cp_model.FEASIBLE)) is expected_feasible


def test_f1_bound_plan_is_dormant_or_active_on_real_tiny_master() -> None:
    _state, _raw_cut, _snapshot, compiled = _compile_production_cut(ghost_mode="intersecting")
    plan = compiled.plan
    assert plan.model_scope == ModelScope(
        ghost_policy="bound",
        ghost_rect_digest=plan.model_scope.ghost_rect_digest,
        domain_fingerprint=plan.model_scope.domain_fingerprint,
    )

    dormant_master = _build_tiny_master()
    dormant_lit = dormant_master.u_vars[0]
    assert _lower_plan_for_test(
        plan,
        dormant_master,
        condition_lits=(dormant_lit,),
    )
    dormant_status = dormant_master.solve(time_limit_seconds=5.0)

    active_master = _build_tiny_master()
    active_lit = active_master.u_vars[0]
    assert _lower_plan_for_test(
        plan,
        active_master,
        condition_lits=(active_lit,),
    )
    delegate = active_master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(active_lit == 1)
    active_status = active_master.solve(time_limit_seconds=5.0)

    assert _interpret_region_plan(
        plan,
        group_presence_counts={_GROUP_ID: 2},
        condition_active=False,
    )
    assert not _interpret_region_plan(
        plan,
        group_presence_counts={_GROUP_ID: 2},
        condition_active=True,
    )
    assert dormant_status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert active_status == cp_model.INFEASIBLE


# ---------------------------------------------------------------------------
# B2 dual-review fixes (2026-07-11): joint-rejection tamper matrix, assumption
# bypass negatives, projection drift, and legacy-check ordering.
# ---------------------------------------------------------------------------


def _tampered_cert_cut(raw_cut: Cut, mutate: Any) -> Cut:
    """Rebuild a representation-consistent cut whose cert semantics are tampered.

    The payload is re-encoded and the cert hash recomputed so the tamper is
    invisible to frame/self-consistency checks and must be caught by the
    semantic validators (legacy AND typed alike).
    """
    import hashlib as _hashlib

    from src.cuts.lifecycle import canonical_bytes_for_cert

    assert raw_cut.geometric_payload is not None
    cert = json.loads(raw_cut.geometric_payload.decode("utf-8"))
    mutate(cert)
    payload = canonical_bytes_for_cert(cert)
    new_hash = _hashlib.sha256(payload).hexdigest()
    fields: dict[str, object] = {
        "geometric_payload": payload,
        "oracle_cert_hash": new_hash,
    }
    if raw_cut.cert is not None:
        fields["cert"] = replace(raw_cut.cert, cert_payload=payload, cert_hash=new_hash)
    return replace(raw_cut, **fields)


def _typed_result_for_cut(state: BState, bundle: Any, cut: Cut) -> object:
    envelope = cut_to_envelope_v1(cut)
    snapshot = build_validated_state_snapshot(state, bundle)
    return validate_and_compile_cut(envelope, snapshot, build_production_registry())


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("capacity_inflated", lambda cert: cert.__setitem__("cap_R", cert["cap_R"] + 5)),
        ("demand_understated", lambda cert: cert.__setitem__("demand_R", 0)),
        ("gap_nonpositive", lambda cert: cert.__setitem__("gap", 0)),
        (
            "contributor_demand_tampered",
            lambda cert: cert.__setitem__(
                "contributing_groups",
                [[gid, demand + 3] for gid, demand in cert["contributing_groups"]],
            ),
        ),
        (
            "cells_per_pose_tampered",
            lambda cert: cert.__setitem__(
                "cells_per_pose",
                {gid: value + 1 for gid, value in cert["cells_per_pose"].items()},
            ),
        ),
        (
            "region_bitset_corrupted",
            lambda cert: cert.__setitem__("region_cells_bitset_b64", "AAAA"),
        ),
    ],
)
def test_f1_semantic_tamper_is_jointly_rejected_by_legacy_and_typed(
    label: str,
    mutate: Any,
) -> None:
    """B2 dual-review codex#5: every legacy validation obligation must reject on
    BOTH paths — the expected-difference table covers ratified tightenings only."""
    state, bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    tampered = _tampered_cert_cut(raw_cut, mutate)

    legacy = validate_region_capacity(tampered, state, state.canonical_rules or {})
    typed_result = _typed_result_for_cut(state, bundle, tampered)

    assert legacy.kind != "ok", f"{label}: legacy accepted tampered cert"
    assert isinstance(typed_result, CutRejection), f"{label}: typed accepted tampered cert"


def test_f1_non_production_validator_version_is_rejected_even_with_empty_assumptions() -> None:
    """B2 dual-review codex#1: the validator_version seam must not bypass the
    assumption obligations — a probe-version capability is rejected outright,
    empty-assumption envelopes included."""
    from dataclasses import replace as dc_replace

    state, bundle = _build_state_and_bundle()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    stripped_scope = dc_replace(raw_cut.scope, active_assumptions=())
    stripped_cut = dc_replace(raw_cut, scope=stripped_scope)

    registry = build_production_registry()
    production = registry.capabilities["region_capacity"]
    probe_capability = dc_replace(production, validator_version="probe-0")
    probe_registry = type(registry)(
        capabilities={**registry.capabilities, "region_capacity": probe_capability},
        plugins=dict(registry.plugins),
    )

    envelope = cut_to_envelope_v1(stripped_cut)
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(envelope, snapshot, probe_registry)

    assert isinstance(result, CutRejection)
    assert not isinstance(result, CompiledCut)


def test_f1_master_domain_projection_changes_when_slot_key_semantics_change() -> None:
    """B2 dual-review codex#2: the projection must carry slot identity so a
    slot-key alias on the master side cannot escape resolve-time comparison."""
    state, _bundle = _build_state_and_bundle()

    # The canonical row payload must include the slot identity fields.
    groups = state.groups or {}
    assert groups, "fixture must provide at least one group"
    sample_group = sorted(groups)[0]
    fake_rows = [
        {
            "allowed_pose_tuples": [],
            "candidate_pose_count": 0,
            "facility_type": "t",
            "group_id": sample_group,
            "slot_index": 0,
            "slot_key": f"{sample_group}::slot::0",
            "slot_kind": "mandatory",
            "template_dimensions": [1, 1],
        }
    ]
    aliased_rows = [dict(fake_rows[0], slot_key=f"{sample_group}::slot::1")]
    fingerprint_a = master_domain_projection_v1(
        family_subset="region_capacity",
        facility_pool_projection=master_domain_facility_pool_projection_v1({}),
        mandatory_slot_rows=fake_rows,
        template_pose_registration_rows=[],
    )
    fingerprint_b = master_domain_projection_v1(
        family_subset="region_capacity",
        facility_pool_projection=master_domain_facility_pool_projection_v1({}),
        mandatory_slot_rows=aliased_rows,
        template_pose_registration_rows=[],
    )
    assert fingerprint_a != fingerprint_b, "slot_key drift must change the projection"


def test_f1_adapter_checks_all_legacy_identities_before_any_stage_b_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B2 dual-review codex#6: no Stage-B 64-hex digest may be computed until
    every applicable legacy 16-hex identity check has passed."""
    from src.cuts import typed_platform as tp

    state, _bundle = _build_state_and_bundle(ghost_mode="intersecting")
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    assert raw_cut.scope.ghost_rect_id != GHOST_AGNOSTIC
    forged_id = ("0" if raw_cut.scope.ghost_rect_id[0] != "0" else "1") + raw_cut.scope.ghost_rect_id[1:]
    forged_cut = replace(raw_cut, scope=replace(raw_cut.scope, ghost_rect_id=forged_id))

    calls: list[object] = []
    original = tp._v1_scope_cells_digest  # noqa: SLF001

    def _tripwire(cells: object, *, prefix: bytes) -> str:
        calls.append(prefix)
        return original(cells, prefix=prefix)  # type: ignore[arg-type]

    monkeypatch.setattr(tp, "_v1_scope_cells_digest", _tripwire)
    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(forged_cut)
    assert calls == [], "Stage-B digest computed before legacy identity checks completed"


def test_f1_compiled_plan_nested_parameters_are_deeply_frozen() -> None:
    """Nested-mapping deep-freeze on the real F1 chain (moved here from the
    B0 platform fixture when it switched to the neutral F6 scalar schema)."""
    _state, _raw_cut, _snapshot, compiled = _compile_production_cut()
    plan_digest_before = compiled.plan.digest

    with pytest.raises((TypeError, AttributeError)):
        compiled.plan.parameters["capacity"] = 999  # type: ignore[index]
    with pytest.raises((TypeError, AttributeError)):
        compiled.plan.parameters["group_cell_weights"]["boundary_io"] = 999  # type: ignore[index]
    with pytest.raises((TypeError, AttributeError)):
        compiled.plan.parameters["group_cell_weights"].update({"boundary_io": 999})  # type: ignore[union-attr]
    assert compiled.plan.digest == plan_digest_before

"""Adversarial obligations for pre-promotion hardening batch alpha."""

from __future__ import annotations

from collections import UserDict
from collections.abc import Callable, Iterable, Set
from typing import Any, cast

import pytest

from src.cuts import state_snapshot
from src.cuts.frozen_artifacts import (
    ArtifactValidationError,
    FrozenArtifactBundle,
    build_frozen_artifact_bundle,
)
from src.cuts.lifecycle import (
    BState,
    _live_master_domain_projection,
    _locate_master_ghost_rect,
    _resolve_model_scope_binding,
    step_8_apply_to_master,
)
from src.cuts.state_snapshot import SnapshotValidationError, build_validated_state_snapshot
from src.tests.cuts.test_stage_b_snapshot_layer import (
    _artifact_sources,
    _bundle_from_sources,
    _state_from_sources,
)
from src.tests.cuts.test_step_8_apply_to_master import _f1_world


class _ObservedHostile:
    calls: int


class _ExplodingTuple(tuple[Any, ...], _ObservedHostile):
    def __new__(cls, values: tuple[Any, ...]) -> _ExplodingTuple:
        instance = super().__new__(cls, values)
        instance.calls = 0
        return instance

    def __len__(self) -> int:
        self.calls += 1
        raise AssertionError("hostile tuple length was observed")

    def __iter__(self) -> Any:
        self.calls += 1
        raise AssertionError("hostile tuple iteration was observed")

    def __getitem__(self, index: object) -> Any:
        self.calls += 1
        raise AssertionError(f"hostile tuple index was observed: {index!r}")


class _ExplodingFrozenset(frozenset[Any], _ObservedHostile):
    def __new__(cls, values: Iterable[Any] = ()) -> _ExplodingFrozenset:
        instance = super().__new__(cls, values)
        instance.calls = 0
        return instance

    def __iter__(self) -> Any:
        self.calls += 1
        raise AssertionError("hostile frozenset iteration was observed")


class _ExplodingList(list[Any], _ObservedHostile):
    def __init__(self, values: list[Any]) -> None:
        super().__init__(values)
        self.calls = 0

    def __iter__(self) -> Any:
        self.calls += 1
        raise AssertionError("hostile list iteration was observed")


class _ExplodingDict(dict[Any, Any], _ObservedHostile):
    def __init__(self, values: dict[Any, Any]) -> None:
        super().__init__(values)
        self.calls = 0

    def items(self) -> Any:
        self.calls += 1
        raise AssertionError("hostile dict items were observed")


class _LyingPoseTupleCache(dict[int, tuple[int, int, int]], _ObservedHostile):
    def __init__(self, values: dict[int, tuple[int, int, int]]) -> None:
        super().__init__(values)
        self.calls = 0

    def __ne__(self, other: object) -> bool:
        self.calls += 1
        return False

    def get(self, key: int, default: Any = None) -> Any:
        self.calls += 1
        return (69, 69, 69)


class _LyingPoseIndex(int, _ObservedHostile):
    alias: int

    def __new__(cls, value: int, *, alias: int) -> _LyingPoseIndex:
        instance = super().__new__(cls, value)
        instance.alias = alias
        instance.calls = 0
        return instance

    def __eq__(self, other: object) -> bool:
        self.calls += 1
        return True

    def __hash__(self) -> int:
        self.calls += 1
        return hash(self.alias)


class _LyingFacilityType(str, _ObservedHostile):
    def __new__(cls, value: str) -> _LyingFacilityType:
        instance = super().__new__(cls, value)
        instance.calls = 0
        return instance

    def __eq__(self, other: object) -> bool:
        self.calls += 1
        return True

    def __hash__(self) -> int:
        self.calls += 1
        return super().__hash__()


class _ExplodingUserDict(UserDict[Any, Any], _ObservedHostile):
    def __init__(self, values: dict[Any, Any]) -> None:
        self.calls = 0
        super().__init__(values)

    def items(self) -> Any:
        self.calls += 1
        raise AssertionError("hostile UserDict items were observed")


class _ExplodingSet(Set[Any], _ObservedHostile):
    def __init__(self) -> None:
        self.calls = 0

    def __contains__(self, value: object) -> bool:
        self.calls += 1
        raise AssertionError(f"hostile set membership was observed: {value!r}")

    def __iter__(self) -> Any:
        self.calls += 1
        raise AssertionError("hostile set iteration was observed")

    def __len__(self) -> int:
        self.calls += 1
        raise AssertionError("hostile set length was observed")


Attack = tuple[Callable[[], object], _ObservedHostile]
AttackFactory = Callable[[BState, FrozenArtifactBundle], Attack]


def _attack_cell(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingTuple((11, 17))
    state.ghost_cells = frozenset({hostile})  # type: ignore[arg-type]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_cell_set(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingSet()
    state.ghost_cells = hostile  # type: ignore[assignment]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_cell_sequence(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    del state, bundle
    hostile = _ExplodingTuple(((0, 0),))
    return (
        lambda: state_snapshot._freeze_cell_sequence(hostile, path="bundle.attack.occupied_cells"),
        hostile,
    )


def _attack_ghost(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingTuple((11, 17, 2, 3))
    state.ghost_rect = hostile  # type: ignore[assignment]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_groups(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingUserDict(state.groups)
    state.groups = hostile  # type: ignore[assignment]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_pose_domain(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    group = state.groups["boundary_io"]
    hostile = _ExplodingFrozenset(group.pose_domain)
    group.pose_domain = hostile  # type: ignore[assignment]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_selected_poses(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    group = state.groups["boundary_io"]
    hostile = _ExplodingList(group.selected_poses)
    group.selected_poses = hostile
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_cell_owner(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingDict(state.cell_owner)
    state.cell_owner = hostile
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_cell_owner_value(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingTuple(("boundary_io", 0))
    state.cell_owner[(4, 4)] = hostile  # type: ignore[assignment]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_artifact_hashes(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingDict(state.artifact_hashes)
    state.artifact_hashes = hostile
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def _attack_oracle_capabilities(state: BState, bundle: FrozenArtifactBundle) -> Attack:
    hostile = _ExplodingSet()
    state.available_oracle_versions = hostile  # type: ignore[assignment]
    return (lambda: build_validated_state_snapshot(state, bundle), hostile)


def test_alpha_1_honest_state_and_bundle_are_content_bound() -> None:
    sources = _artifact_sources()
    state = _state_from_sources(sources)
    bundle = _bundle_from_sources(sources)

    snapshot = build_validated_state_snapshot(state, bundle)

    f1_inputs = snapshot.family_inputs["region_capacity"]
    assert isinstance(f1_inputs, state_snapshot.F1RegionInputs)
    assert f1_inputs.instance_to_facility_type == bundle.instance_to_facility_type


def test_alpha_1_honest_runtime_cache_keys_share_one_normalized_world() -> None:
    sources = _artifact_sources()
    sources["candidate_placements"]["__pose_id_cache__"] = {
        "boundary_storage_port::shared_pose": {"pose_id": "shared_pose"}
    }
    sources["candidate_placements"]["__pose_id_cache_digest__"] = "runtime-only"
    state = _state_from_sources(sources)
    bundle = _bundle_from_sources(sources)

    snapshot = build_validated_state_snapshot(state, bundle)

    assert snapshot.family_inputs["region_capacity"]


@pytest.mark.parametrize(
    "field_name",
    [
        "candidate_placements",
        "facility_templates",
        "instance_to_facility_type",
        "canonical_rules",
    ],
)
def test_alpha_1_rejects_mixed_static_world_after_bundle_freeze(field_name: str) -> None:
    sources = _artifact_sources()
    state = _state_from_sources(sources)
    bundle = _bundle_from_sources(sources)
    state_source = getattr(state, field_name)
    assert type(state_source) is dict
    state_source["alpha_state_world_only"] = "drift"

    with pytest.raises(SnapshotValidationError, match=field_name):
        build_validated_state_snapshot(state, bundle)


def test_alpha_2_accepts_exact_production_container_shapes() -> None:
    sources = _artifact_sources()
    snapshot = build_validated_state_snapshot(
        _state_from_sources(sources),
        _bundle_from_sources(sources),
    )

    assert snapshot.digest == "1ffd473bbc0c521a57c0cb8072a014543917b83f5b50c4106011c949b8b60ebb"


@pytest.mark.parametrize(
    "attack_factory",
    [
        _attack_cell,
        _attack_cell_set,
        _attack_cell_sequence,
        _attack_ghost,
        _attack_groups,
        _attack_pose_domain,
        _attack_selected_poses,
        _attack_cell_owner,
        _attack_cell_owner_value,
        _attack_artifact_hashes,
        _attack_oracle_capabilities,
    ],
    ids=lambda factory: factory.__name__.removeprefix("_attack_"),
)
def test_alpha_2_rejects_behavioral_containers_before_observation(
    attack_factory: AttackFactory,
) -> None:
    sources = _artifact_sources()
    state = _state_from_sources(sources)
    operation, hostile = attack_factory(state, _bundle_from_sources(sources))

    with pytest.raises(SnapshotValidationError):
        operation()

    assert hostile.calls == 0


def test_alpha_3_honest_projection_validation_keeps_f7_pose_cache_lazy() -> None:
    from src.tests.cuts.test_stage_b_power_hitting_set import _build_master, _build_world

    state, bundle = _build_world()
    snapshot = build_validated_state_snapshot(state, bundle)
    master = _build_master()
    delegate = master._coordinate_delegate
    assert delegate is not None

    live_projection = _live_master_domain_projection(master, "power_hitting_set")

    assert live_projection == snapshot.power_hitting_set_master_domain_projection
    assert delegate._pose_idx_by_pose_id_cache == {}


def test_alpha_3_rejects_mandatory_group_template_drift() -> None:
    master, _snapshot, _compiled = _f1_world()
    master._mandatory_groups[0]["facility_type"] = "alpha_foreign_template"

    with pytest.raises(ValueError, match="mandatory group cache drifted"):
        _live_master_domain_projection(master, "region_capacity")


def test_alpha_3_rejects_template_pose_tuple_cache_drift() -> None:
    master, _snapshot, _compiled = _f1_world()
    delegate = master._coordinate_delegate
    assert delegate is not None
    cache = delegate._template_pose_tuple_by_idx["boundary_storage_port"]
    pose_index = min(cache)
    cache[pose_index] = (69, 69, 69)

    with pytest.raises(ValueError, match="template pose tuple cache drifted"):
        _live_master_domain_projection(master, "region_capacity")


def test_alpha_3_rejects_behavioral_template_pose_cache_before_observation() -> None:
    master, _snapshot, _compiled = _f1_world()
    delegate = master._coordinate_delegate
    assert delegate is not None
    original = delegate._template_pose_tuple_by_idx["boundary_storage_port"]
    hostile = _LyingPoseTupleCache(original)
    delegate._template_pose_tuple_by_idx["boundary_storage_port"] = hostile

    with pytest.raises(ValueError, match="non-exact template map"):
        _live_master_domain_projection(master, "region_capacity")

    assert hostile.calls == 0


def test_alpha_3_rejects_behavioral_template_cache_key_before_observation() -> None:
    master, _snapshot, _compiled = _f1_world()
    delegate = master._coordinate_delegate
    assert delegate is not None
    cache = delegate._template_pose_tuple_by_idx
    original = cache.pop("boundary_storage_port")
    hostile = _LyingFacilityType("boundary_storage_port")
    cache[hostile] = original
    hostile.calls = 0

    with pytest.raises(ValueError, match="invalid facility key"):
        _live_master_domain_projection(master, "region_capacity")

    assert hostile.calls == 0


def test_alpha_3_rejects_materialized_f7_pose_id_cache_drift() -> None:
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _FACILITY_TYPE,
        _TARGET_POSE_ID,
        _build_master,
    )

    master = _build_master()
    delegate = master._coordinate_delegate
    assert delegate is not None
    assert delegate._resolve_pose_idx_by_pose_id(_FACILITY_TYPE, _TARGET_POSE_ID) is not None
    materialized = delegate._pose_idx_by_pose_id_cache[_FACILITY_TYPE]
    assert materialized is not None
    materialized[_TARGET_POSE_ID] = 10_000

    with pytest.raises(ValueError, match="materialized pose-id cache drifted"):
        _live_master_domain_projection(master, "power_hitting_set")


def test_alpha_3_rejects_behavioral_f7_pose_index_before_observation() -> None:
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _FACILITY_TYPE,
        _TARGET_POSE_ID,
        _build_master,
    )

    master = _build_master()
    delegate = master._coordinate_delegate
    assert delegate is not None
    assert delegate._resolve_pose_idx_by_pose_id(_FACILITY_TYPE, _TARGET_POSE_ID) is not None
    materialized = delegate._pose_idx_by_pose_id_cache[_FACILITY_TYPE]
    assert materialized is not None
    original_index = materialized[_TARGET_POSE_ID]
    hostile = _LyingPoseIndex(original_index, alias=original_index + 1)
    materialized[_TARGET_POSE_ID] = hostile

    with pytest.raises(ValueError, match="materialized pose-id cache has an invalid entry"):
        _live_master_domain_projection(master, "power_hitting_set")

    assert hostile.calls == 0


def test_alpha_binding_honest_chain_preserves_master_and_ghost_identity() -> None:
    master, snapshot, compiled = _f1_world()
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)

    assert binding.master_ref() is master
    live_master: Any = master
    assert binding.master_domain_family == "region_capacity"
    assert binding.rect_idx is not None
    assert binding.condition_lits[0] is live_master.u_vars[binding.rect_idx]

    step_8_apply_to_master(compiled, live_master, scope_binding=binding)
    assert live_master.build_stats["coordinate_framework_cut_count"] == 1


def test_alpha_4_rejects_pool_drift_after_binding() -> None:
    master, snapshot, compiled = _f1_world()
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    master.facility_pools["boundary_storage_port"][0]["alpha_post_binding_drift"] = True

    with pytest.raises(ValueError, match="domain changed after scope binding"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)

    assert master.build_stats.get("coordinate_framework_cut_count", 0) == 0


def test_alpha_4_rejects_ghost_rect_relocated_after_binding() -> None:
    """α-4 FORGE-rect gate (spec §4 item 4 deferred negative test).

    The master keeps every candidate ghost anchor as its own domain/u_var, so
    this is genuinely a multi-ghost-rect world.  After an honest resolve we swap
    the bound domain's cells with another candidate anchor: the bound digest now
    relocates to a *different* live index while ``u_vars`` stay put — so the
    α-6 identity check still passes and only the fresh rect re-location (α-4)
    can catch the drift.  This pins that the gate compares the exact index, not
    mere presence, which the single-rect fixture cannot exercise.
    """
    master, snapshot, compiled = _f1_world()
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    assert binding.rect_idx == 0
    assert _locate_master_ghost_rect(master, binding.ghost_rect_digest) == 0

    domain_0 = master._ghost_domains[0]
    domain_1 = master._ghost_domains[1]
    domain_0["cells"], domain_1["cells"] = domain_1["cells"], domain_0["cells"]

    # The bound digest now points at index 1, but u_vars[0] (α-6 identity) is
    # untouched — so only the exact-index rect re-location gate can reject.
    assert _locate_master_ghost_rect(master, binding.ghost_rect_digest) == 1
    assert master.u_vars[0] is binding.condition_lits[0]

    with pytest.raises(ValueError, match="resolved rect index no longer matches"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)

    assert master.build_stats.get("coordinate_framework_cut_count", 0) == 0


def test_alpha_6_rejects_replaced_u_var_identity() -> None:
    master, snapshot, compiled = _f1_world()
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    assert binding.rect_idx is not None
    bound_u_var = master.u_vars[binding.rect_idx]
    replacement = next(u_var for u_var in master.u_vars.values() if u_var is not bound_u_var)
    master.u_vars[binding.rect_idx] = replacement

    with pytest.raises(ValueError, match="ghost literal identity drifted"):
        step_8_apply_to_master(compiled, master, scope_binding=binding)

    assert master.build_stats.get("coordinate_framework_cut_count", 0) == 0


def test_alpha_7_rejects_binding_moved_to_equivalent_master() -> None:
    master_a, snapshot_a, compiled_a = _f1_world()
    master_b, _snapshot_b, _compiled_b = _f1_world()
    binding_a = _resolve_model_scope_binding(compiled_a.plan.model_scope, snapshot_a, master_a)

    with pytest.raises(ValueError, match="belongs to a different master"):
        step_8_apply_to_master(compiled_a, master_b, scope_binding=binding_a)

    assert master_b.build_stats.get("coordinate_framework_cut_count", 0) == 0


def test_alpha_5_shared_nodes_are_frozen_once_across_bundle_roots() -> None:
    shared_templates = {"widget": {"dimensions": {"w": 1, "h": 1}}}
    shared_pool = [{"pose_id": "p0", "occupied_cells": [[0, 0]]}]
    shared_instance_mapping = {"widget_group": "widget"}
    canonical_rules = {
        "facility_templates": shared_templates,
        "instance_to_facility_type": shared_instance_mapping,
        "shared_pool": shared_pool,
    }
    candidate_placements = {"facility_pools": {"widget": shared_pool}}

    bundle = build_frozen_artifact_bundle(
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=shared_templates,
        instance_to_facility_type=shared_instance_mapping,
    )

    frozen_rules = cast(Any, bundle.canonical_rules)
    frozen_candidates = cast(Any, bundle.candidate_placements)
    assert frozen_rules["facility_templates"] is bundle.facility_templates
    assert frozen_rules["shared_pool"] is frozen_candidates["facility_pools"]["widget"]
    assert frozen_rules["instance_to_facility_type"] is bundle.instance_to_facility_type


def _dict_self_cycle() -> dict[str, object]:
    root: dict[str, object] = {}
    root["self"] = root
    return root


def _list_self_cycle() -> dict[str, object]:
    cycle: list[object] = []
    cycle.append(cycle)
    return {"cycle": cycle}


def _cross_cycle() -> dict[str, object]:
    root: dict[str, object] = {}
    child: list[object] = [root]
    root["child"] = child
    return root


@pytest.mark.parametrize("cycle_factory", [_dict_self_cycle, _list_self_cycle, _cross_cycle])
def test_alpha_5_cycles_raise_explicit_artifact_error(
    cycle_factory: Callable[[], dict[str, object]],
) -> None:
    with pytest.raises(ArtifactValidationError, match="cyclic"):
        build_frozen_artifact_bundle(
            canonical_rules=cycle_factory(),
            candidate_placements={},
            facility_templates={},
            instance_to_facility_type={},
        )


def _nested_artifact(container_count: int) -> dict[str, object]:
    root: dict[str, object] = {}
    cursor = root
    for index in range(container_count - 1):
        child: dict[str, object] = {}
        cursor[f"level_{index}"] = child
        cursor = child
    cursor["leaf"] = "ok"
    return root


def test_alpha_5_freeze_depth_limit_is_controlled() -> None:
    accepted = build_frozen_artifact_bundle(
        canonical_rules=_nested_artifact(128),
        candidate_placements={},
        facility_templates={},
        instance_to_facility_type={},
    )
    assert accepted.canonical_rules

    with pytest.raises(ArtifactValidationError, match="nesting limit of 128"):
        build_frozen_artifact_bundle(
            canonical_rules=_nested_artifact(129),
            candidate_placements={},
            facility_templates={},
            instance_to_facility_type={},
        )

"""Unit contracts for the RFC-001 Stage-B frozen snapshot layer."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from src.cuts.frozen_artifacts import (
    FrozenArtifactBundle,
    build_frozen_artifact_bundle,
)
from src.cuts.lifecycle import BState, GroupState, compute_source_digest
from src.cuts.state_snapshot import (
    F1RegionInputs,
    F5PatternNogoodInputs,
    F6HallInputs,
    F7PowerInputs,
    GhostRect,
    SnapshotValidationError,
    ValidatedStateSnapshot,
    build_validated_state_snapshot,
    master_domain_facility_pool_projection_v1,
    master_domain_projection_v1,
    snapshot_digest_v1,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
TESTS_ROOT = SRC_ROOT / "tests"
STATE_SNAPSHOT_PATH = REPO_ROOT / "src" / "cuts" / "state_snapshot.py"


class _MutableInt(int):
    """Adversarial scalar whose behavior can drift after a digest is fixed."""

    bias = 0

    def __add__(self, other: object) -> int:
        return int(self) + int(other) + self.bias  # type: ignore[arg-type]


class _MutableStr(str):
    accept_all = False

    def __eq__(self, other: object) -> bool:
        return self.accept_all or super().__eq__(other)

    __hash__ = str.__hash__


class _MutableFloat(float):
    """Float subclass forbidden by the exact JSON-native boundary."""


class _CustomList(list[Any]):
    """List subclass forbidden by the exact JSON-native boundary."""


class _RuntimeErrorMapping(dict[Any, Any]):
    def items(self) -> Any:
        raise RuntimeError("hostile mapping iteration")


class _RuntimeErrorSet(set[Any]):
    def __iter__(self) -> Any:
        raise RuntimeError("hostile set iteration")


class _FlipGroupOnSecondItems(dict[str, GroupState]):
    """Expose the old builder's two-pass hybrid-snapshot vulnerability."""

    items_calls = 0

    def items(self) -> Any:
        self.items_calls += 1
        if self.items_calls == 2:
            self["boundary_io"].demand = 7
        return super().items()


def _assert_sha256_hex(value: str) -> None:
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def _reverse_mappings(value: Any) -> Any:
    if isinstance(value, dict):
        items = reversed(list(value.items()))
        return {key: _reverse_mappings(item) for key, item in items}
    if isinstance(value, list):
        return [_reverse_mappings(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_reverse_mappings(item) for item in value)
    if isinstance(value, set):
        return set(value)
    if isinstance(value, frozenset):
        return frozenset(value)
    return value


def _artifact_sources(*, reverse: bool = False) -> dict[str, Any]:
    facility_templates = {
        "boundary_storage_port": {
            "placement_rule": "left_or_bottom_boundary",
            "dimensions": {"w": 1, "h": 3},
            "needs_power": False,
        },
        "manufacturing_3x3": {
            "placement_rule": "free",
            "dimensions": {"w": 3, "h": 3},
            "needs_power": True,
        },
        "power_pole": {
            "placement_rule": "free",
            "dimensions": {"w": 2, "h": 2},
            "needs_power": False,
            "power_coverage_radius": 5,
        },
    }
    canonical_rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": deepcopy(facility_templates),
        "snapshot_test_metadata": {
            "label": "阶段-B",
            "unordered_flags": ["alpha", "beta"],
        },
    }
    candidate_placements = {
        "facility_pools": {
            "boundary_storage_port": [
                {
                    "pose_id": "shared_pose",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 1], [0, 2], [0, 3]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
                {
                    "pose_id": "boundary_alt",
                    "anchor": {"x": 1, "y": 0},
                    "occupied_cells": [[1, 0], [2, 0], [3, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
            ],
            # Reusing a pose_id in another facility pool is valid.  The B1
            # projection must key poses by (facility_type, pose_id).
            "manufacturing_3x3": [
                {
                    "pose_id": "shared_pose",
                    "anchor": {"x": 30, "y": 30},
                    "occupied_cells": [
                        [30, 30],
                        [30, 31],
                        [30, 32],
                        [31, 30],
                        [31, 31],
                        [31, 32],
                        [32, 30],
                        [32, 31],
                        [32, 32],
                    ],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
            "power_pole": [],
        }
    }
    sources = {
        "artifact_hashes": {
            "canonical_rules.json": "1" * 64,
            "candidate_placements.json": "2" * 64,
            "mandatory_exact_instances.json": "3" * 64,
        },
        "candidate_placements": candidate_placements,
        "canonical_rules": canonical_rules,
        "facility_templates": facility_templates,
        "instance_to_facility_type": {
            "boundary_io": "boundary_storage_port",
            "crusher_blue_iron": "manufacturing_3x3",
        },
    }
    return _reverse_mappings(sources) if reverse else sources


def _state_from_sources(sources: Mapping[str, Any], *, reverse: bool = False) -> BState:
    groups = {
        "boundary_io": GroupState(
            group_id="boundary_io",
            demand=2,
            pose_domain=frozenset({"shared_pose", "boundary_alt"}),
            selected_poses=["shared_pose"],
        ),
        "crusher_blue_iron": GroupState(
            group_id="crusher_blue_iron",
            demand=1,
            pose_domain=frozenset({"shared_pose"}),
            selected_poses=[],
        ),
    }
    cell_owner = {
        (4, 4): ("boundary_io", 0),
        (30, 30): ("crusher_blue_iron", 0),
    }
    if reverse:
        groups = dict(reversed(list(groups.items())))
        cell_owner = dict(reversed(list(cell_owner.items())))
    ghost_rect = (11, 17, 2, 3)
    ghost_cells = frozenset(
        (x, y)
        for x in range(ghost_rect[0], ghost_rect[0] + ghost_rect[2])
        for y in range(ghost_rect[1], ghost_rect[1] + ghost_rect[3])
    )
    return BState(
        groups=groups,
        cell_owner=cell_owner,
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset({(7, 0), (8, 0)}),
        artifact_hashes=dict(sources["artifact_hashes"]),
        available_oracle_versions=frozenset(
            {
                "power_cover_v1",
                "region_capacity_v1",
                "shape_packing_hall_v1",
            }
        ),
        canonical_rules=sources["canonical_rules"],
        candidate_placements=sources["candidate_placements"],
        facility_templates=sources["facility_templates"],
        instance_to_facility_type=sources["instance_to_facility_type"],
        source_digest="4" * 64,
    )


def _bundle_from_sources(sources: Mapping[str, Any]) -> FrozenArtifactBundle:
    return build_frozen_artifact_bundle(
        canonical_rules=sources["canonical_rules"],
        candidate_placements=sources["candidate_placements"],
        facility_templates=sources["facility_templates"],
        instance_to_facility_type=sources["instance_to_facility_type"],
        artifact_hashes=sources["artifact_hashes"],
    )


def _build_world(*, reverse: bool = False) -> tuple[BState, FrozenArtifactBundle, ValidatedStateSnapshot]:
    sources = _artifact_sources(reverse=reverse)
    state = _state_from_sources(sources, reverse=reverse)
    bundle = _bundle_from_sources(sources)
    snapshot = build_validated_state_snapshot(state, bundle)
    return state, bundle, snapshot


def test_bundle_factory_accepts_only_explicit_artifacts() -> None:
    sources = _artifact_sources()

    explicit = _bundle_from_sources(sources)

    assert explicit.artifact_hashes == sources["artifact_hashes"]
    _assert_sha256_hex(explicit.digest)
    with pytest.raises((TypeError, ValueError)):
        build_frozen_artifact_bundle(_state_from_sources(sources))  # type: ignore[call-arg]


def test_bundle_recursively_freezes_every_supported_container() -> None:
    sources = _artifact_sources()
    bundle = _bundle_from_sources(sources)
    digest_before = bundle.digest

    assert isinstance(bundle.canonical_rules, MappingProxyType)
    assert isinstance(bundle.canonical_rules["globals"], MappingProxyType)
    assert bundle.canonical_rules["snapshot_test_metadata"]["unordered_flags"] == ("alpha", "beta")
    assert bundle.candidate_placements["facility_pools"]["boundary_storage_port"][0]["occupied_cells"] == (
        (0, 1),
        (0, 2),
        (0, 3),
    )
    with pytest.raises(TypeError):
        bundle.canonical_rules["globals"]["grid"]["width"] = 99
    with pytest.raises(AttributeError):
        bundle.candidate_placements["facility_pools"]["boundary_storage_port"].append({})
    with pytest.raises(AttributeError):
        bundle.canonical_rules["snapshot_test_metadata"]["unordered_flags"].append("attacker")
    assert bundle.digest == digest_before


def test_bundle_digest_is_canonical_and_sensitive_to_nested_content() -> None:
    forward = _artifact_sources()
    reverse = _artifact_sources(reverse=True)

    forward_bundle = _bundle_from_sources(forward)
    reverse_bundle = _bundle_from_sources(reverse)
    _assert_sha256_hex(forward_bundle.digest)
    assert forward_bundle.digest == reverse_bundle.digest

    reverse["candidate_placements"]["facility_pools"]["boundary_storage_port"][0]["occupied_cells"].append([69, 69])
    assert _bundle_from_sources(reverse).digest != forward_bundle.digest


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_bundle_digest_rejects_non_finite_numbers(bad_value: float) -> None:
    sources = _artifact_sources()
    sources["canonical_rules"]["snapshot_test_metadata"]["non_finite"] = bad_value

    with pytest.raises(ValueError, match="non-finite"):
        _bundle_from_sources(sources)


@pytest.mark.parametrize(
    "field_name",
    [
        "canonical_rules",
        "candidate_placements",
        "facility_templates",
        "instance_to_facility_type",
        "artifact_hashes",
    ],
)
@pytest.mark.parametrize(
    "bad_mapping",
    [
        MappingProxyType({"payload": "value"}),
        _RuntimeErrorMapping({"payload": "value"}),
    ],
    ids=("mapping-proxy", "custom-mapping"),
)
def test_bundle_rejects_non_exact_top_level_mappings_before_normalization(
    field_name: str,
    bad_mapping: Mapping[Any, Any],
) -> None:
    sources = _artifact_sources()
    sources[field_name] = bad_mapping

    with pytest.raises(TypeError, match=f"{field_name} must be an exact dict"):
        _bundle_from_sources(sources)


@pytest.mark.parametrize(
    "bad_value",
    [
        MappingProxyType({"payload": "value"}),
        _RuntimeErrorMapping({"payload": "value"}),
        ("tuple",),
        {"set"},
        frozenset({"frozenset"}),
        _CustomList(["list-subclass"]),
    ],
    ids=("mapping-proxy", "custom-mapping", "tuple", "set", "frozenset", "list-subclass"),
)
def test_bundle_rejects_non_json_native_nested_containers_before_normalization(bad_value: object) -> None:
    sources = _artifact_sources()
    sources["canonical_rules"]["snapshot_test_metadata"]["attack"] = bad_value

    with pytest.raises(TypeError, match="outside the exact JSON-native domain"):
        _bundle_from_sources(sources)


def test_bundle_rejects_missing_non_mapping_and_non_string_key_artifacts() -> None:
    sources = _artifact_sources()
    with pytest.raises((TypeError, ValueError)):
        build_frozen_artifact_bundle(
            candidate_placements=sources["candidate_placements"],
            facility_templates=sources["facility_templates"],
            instance_to_facility_type=sources["instance_to_facility_type"],
            artifact_hashes=sources["artifact_hashes"],
        )

    sources["canonical_rules"] = []
    with pytest.raises((TypeError, ValueError)):
        _bundle_from_sources(sources)

    sources = _artifact_sources()
    sources["canonical_rules"][7] = "non-string-key"
    with pytest.raises((TypeError, ValueError)):
        _bundle_from_sources(sources)


@pytest.mark.parametrize(
    "hostile_scalar",
    [_MutableInt(70), _MutableStr("hostile"), _MutableFloat(1.25)],
    ids=("int-subclass", "str-subclass", "float-subclass"),
)
def test_bundle_rejects_behavioral_scalar_subclasses(hostile_scalar: object) -> None:
    sources = _artifact_sources()
    sources["canonical_rules"]["snapshot_test_metadata"]["hostile_scalar"] = hostile_scalar

    with pytest.raises(TypeError, match="outside the exact JSON-native domain"):
        _bundle_from_sources(sources)


def test_bundle_rejects_behavioral_string_subclass_as_mapping_key() -> None:
    sources = _artifact_sources()
    sources["canonical_rules"][_MutableStr("hostile_key")] = "value"

    with pytest.raises(TypeError, match="mapping key that is not an exact str"):
        _bundle_from_sources(sources)


def test_bundle_rejects_behavioral_artifact_hash_subclasses() -> None:
    sources = _artifact_sources()
    hostile_hash = _MutableStr("1" * 64)
    sources["artifact_hashes"]["canonical_rules.json"] = hostile_hash

    with pytest.raises(TypeError, match="exact str keys to exact str values"):
        _bundle_from_sources(sources)


def test_snapshot_projects_all_groups_and_public_dynamic_cells_once() -> None:
    _state, _bundle, snapshot = _build_world()

    assert snapshot.ghost == GhostRect(x=11, y=17, width=2, height=3)
    assert set(snapshot.groups) == {"boundary_io", "crusher_blue_iron"}
    assert snapshot.groups["boundary_io"].selected_poses == ("shared_pose",)
    assert snapshot.groups["crusher_blue_iron"].pose_domain == frozenset({"shared_pose"})
    assert snapshot.ghost_cells == frozenset({(11, 17), (11, 18), (11, 19), (12, 17), (12, 18), (12, 19)})
    assert snapshot.exterior_blocks == frozenset({(7, 0), (8, 0)})
    assert snapshot.cell_owner == {
        (4, 4): ("boundary_io", 0),
        (30, 30): ("crusher_blue_iron", 0),
    }
    _assert_sha256_hex(snapshot.blocked_cells_digest)
    _assert_sha256_hex(snapshot.exterior_blocks_digest)
    _assert_sha256_hex(snapshot.digest)


def test_snapshot_digest_is_order_independent() -> None:
    _state, _bundle, forward = _build_world()
    _reverse_state, _reverse_bundle, reverse = _build_world(reverse=True)

    assert reverse.digest == forward.digest


def test_master_domain_projection_is_order_stable_and_tracks_pose_registration() -> None:
    _state, _bundle, forward = _build_world()
    _reverse_state, _reverse_bundle, reverse = _build_world(reverse=True)

    assert forward.master_domain_projection == reverse.master_domain_projection
    _assert_sha256_hex(forward.master_domain_projection)

    changed_sources = _artifact_sources()
    changed_sources["candidate_placements"]["facility_pools"]["boundary_storage_port"][0]["anchor"]["x"] = 9
    changed_state = _state_from_sources(changed_sources)
    changed_bundle = _bundle_from_sources(changed_sources)
    changed = build_validated_state_snapshot(changed_state, changed_bundle)

    assert changed.master_domain_projection != forward.master_domain_projection


def test_f6_master_domain_projection_is_separate_order_stable_and_tracks_occupied_cells() -> None:
    _state, _bundle, forward = _build_world()
    _reverse_state, _reverse_bundle, reverse = _build_world(reverse=True)

    assert forward.shape_packing_hall_master_domain_projection == reverse.shape_packing_hall_master_domain_projection
    _assert_sha256_hex(forward.shape_packing_hall_master_domain_projection)
    assert forward.shape_packing_hall_master_domain_projection != forward.master_domain_projection

    changed_sources = _artifact_sources()
    related_pose = changed_sources["candidate_placements"]["facility_pools"]["boundary_storage_port"][0]
    related_pose["occupied_cells"] = [[0, 2], [0, 3], [0, 4]]
    changed_state = _state_from_sources(changed_sources)
    changed_bundle = _bundle_from_sources(changed_sources)
    changed = build_validated_state_snapshot(changed_state, changed_bundle)

    assert changed.shape_packing_hall_master_domain_projection != forward.shape_packing_hall_master_domain_projection
    assert changed.master_domain_projection != forward.master_domain_projection


def test_f6_projection_does_not_change_the_reviewed_f1_or_snapshot_identities() -> None:
    _state, _bundle, snapshot = _build_world()

    assert snapshot.master_domain_projection == "80ae61bca0c96a81773250971dce150a63575698aabf33a66fc2413d847f6a38"
    assert snapshot.digest == "1ffd473bbc0c521a57c0cb8072a014543917b83f5b50c4106011c949b8b60ebb"


def test_f6_master_domain_projection_ignores_non_f6_facility_pool_noise() -> None:
    _state, _bundle, baseline = _build_world()
    changed_sources = _artifact_sources()
    unrelated_pose = changed_sources["candidate_placements"]["facility_pools"]["manufacturing_3x3"][0]
    unrelated_pose["occupied_cells"][0] = [29, 30]
    changed_state = _state_from_sources(changed_sources)
    changed_bundle = _bundle_from_sources(changed_sources)
    changed = build_validated_state_snapshot(changed_state, changed_bundle)

    assert changed.digest != baseline.digest
    assert changed.shape_packing_hall_master_domain_projection == baseline.shape_packing_hall_master_domain_projection


@pytest.mark.parametrize(
    ("demand", "dimensions", "placement_rule"),
    [
        (0, (1, 3), "left_or_bottom_boundary"),
        (1, (1, 1), "left_or_bottom_boundary"),
        (1, (2, 2), "left_or_bottom_boundary"),
        (1, (1, 71), "left_or_bottom_boundary"),
        (1, (1, 3), "free"),
    ],
    ids=("zero-demand", "pose-length-one", "not-one-by-l", "longer-than-grid", "free-placement"),
)
def test_f6_projection_ignores_statically_ineligible_groups(
    demand: int,
    dimensions: tuple[int, int],
    placement_rule: str,
) -> None:
    _state, _bundle, baseline = _build_world()
    sources = _artifact_sources()
    extra_template = {
        "placement_rule": placement_rule,
        "dimensions": {"w": dimensions[0], "h": dimensions[1]},
        "needs_power": False,
    }
    sources["facility_templates"]["f6_ineligible"] = extra_template
    sources["canonical_rules"]["facility_templates"]["f6_ineligible"] = deepcopy(extra_template)
    sources["candidate_placements"]["facility_pools"]["f6_ineligible"] = [
        {
            "pose_id": "ineligible_pose",
            "anchor": {"x": 50, "y": 50},
            "occupied_cells": [[50, 50]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
    ]
    sources["instance_to_facility_type"]["ineligible_group"] = "f6_ineligible"
    changed_state = _state_from_sources(sources)
    changed_state.groups["ineligible_group"] = GroupState(
        group_id="ineligible_group",
        demand=demand,
        pose_domain=frozenset({"ineligible_pose"}),
    )
    changed = build_validated_state_snapshot(changed_state, _bundle_from_sources(sources))

    assert changed.shape_packing_hall_master_domain_projection == baseline.shape_packing_hall_master_domain_projection


def test_f1_master_domain_projection_ignores_unrelated_family_pool_noise() -> None:
    _state, _bundle, baseline = _build_world()
    changed_sources = _artifact_sources()
    unrelated_pose = changed_sources["candidate_placements"]["facility_pools"]["manufacturing_3x3"][0]
    unrelated_pose["anchor"]["x"] = 31
    changed_state = _state_from_sources(changed_sources)
    changed_bundle = _bundle_from_sources(changed_sources)
    changed = build_validated_state_snapshot(changed_state, changed_bundle)

    assert changed.digest != baseline.digest
    assert changed.master_domain_projection == baseline.master_domain_projection


def test_master_domain_projection_primitive_rejects_ambiguous_keys() -> None:
    with pytest.raises(SnapshotValidationError):
        master_domain_projection_v1(
            family_subset="region_capacity",
            facility_pool_projection={1: "numeric key"},
            mandatory_slot_rows=[],
            template_pose_registration_rows=[],
        )


def test_master_domain_pool_projection_matches_frozen_and_live_container_shapes() -> None:
    sources = _artifact_sources()
    bundle = _bundle_from_sources(sources)
    raw_pools = sources["candidate_placements"]["facility_pools"]
    frozen_pools = bundle.candidate_placements["facility_pools"]

    assert master_domain_facility_pool_projection_v1(raw_pools) == (
        master_domain_facility_pool_projection_v1(frozen_pools)
    )


def _change_selected_poses(state: BState) -> None:
    state.groups["boundary_io"].selected_poses.append("boundary_alt")


def _change_ghost_rect(state: BState) -> None:
    state.ghost_rect = (10, 17, 2, 3)


def _change_ghost_cells(state: BState) -> None:
    state.ghost_cells = frozenset({*state.ghost_cells, (69, 69)})


def _change_exterior_blocks(state: BState) -> None:
    state.exterior_blocks = frozenset({*state.exterior_blocks, (9, 0)})


def _change_artifact_hashes(state: BState) -> None:
    state.artifact_hashes["derived.snapshot-inputs.json"] = "5" * 64


def _change_group_demand(state: BState) -> None:
    state.groups["boundary_io"].demand = 3


def _change_group_pose_domain(state: BState) -> None:
    state.groups["boundary_io"].pose_domain = frozenset({"shared_pose"})


def _change_cell_owner(state: BState) -> None:
    state.cell_owner[(5, 5)] = ("boundary_io", 1)


def _change_oracle_capabilities(state: BState) -> None:
    state.available_oracle_versions = frozenset({*state.available_oracle_versions, "new_oracle_v1"})


@pytest.mark.parametrize(
    "change",
    [
        _change_selected_poses,
        _change_ghost_rect,
        _change_ghost_cells,
        _change_exterior_blocks,
        _change_artifact_hashes,
        _change_group_demand,
        _change_group_pose_domain,
        _change_cell_owner,
        _change_oracle_capabilities,
    ],
    ids=lambda change: change.__name__.removeprefix("_change_"),
)
def test_snapshot_digest_covers_every_dynamic_layer(change: Callable[[BState], None]) -> None:
    state, bundle, baseline = _build_world()
    change(state)

    changed = build_validated_state_snapshot(state, bundle)

    assert changed.digest != baseline.digest


def test_bundle_and_snapshot_digests_are_stable_across_processes() -> None:
    _state, bundle, snapshot = _build_world()
    script = "\n".join(
        (
            "import sys",
            "sys.path.insert(0, sys.argv[1])",
            "from src.tests.cuts.test_stage_b_snapshot_layer import _build_world",
            "_state, bundle, snapshot = _build_world(reverse=True)",
            "print(bundle.digest)",
            "print(snapshot.digest)",
        )
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(REPO_ROOT)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stderr == ""
    assert completed.stdout.splitlines() == [bundle.digest, snapshot.digest]


def test_snapshot_digest_v1_matches_domain_separated_compact_utf8_known_vector() -> None:
    projection = {"乱序-z": [3, 2, 1], "a": {"中文": "阶段-B"}}
    canonical_bytes = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    expected = hashlib.sha256(b"zmd.snapshot.v1:" + canonical_bytes).hexdigest()

    assert snapshot_digest_v1(projection) == expected


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_snapshot_digest_v1_rejects_non_finite_numbers(bad_value: float) -> None:
    with pytest.raises(SnapshotValidationError):
        snapshot_digest_v1({"x": bad_value})


@pytest.mark.parametrize(
    ("ambiguous_projection", "exact_projection"),
    [
        ({1: "v"}, {"1": "v"}),
        ({True: "v"}, {"true": "v"}),
        ({"x": ("v",)}, {"x": ["v"]}),
    ],
    ids=["int-key-vs-str-key", "bool-key-vs-str-key", "tuple-vs-list"],
)
def test_snapshot_digest_v1_rejects_primitive_type_collisions(
    ambiguous_projection: object,
    exact_projection: dict[str, object],
) -> None:
    _assert_sha256_hex(snapshot_digest_v1(exact_projection))

    with pytest.raises(SnapshotValidationError):
        snapshot_digest_v1(ambiguous_projection)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "ambiguous_projection",
    [
        MappingProxyType({"x": "v"}),
        {"x": _MutableInt(7)},
        {_MutableStr("x"): "v"},
    ],
    ids=["custom-mapping", "int-subclass", "str-key-subclass"],
)
def test_snapshot_digest_v1_rejects_non_exact_primitive_types(ambiguous_projection: object) -> None:
    with pytest.raises(SnapshotValidationError):
        snapshot_digest_v1(ambiguous_projection)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_snapshot_rejects_non_finite_dynamic_numbers(bad_value: float) -> None:
    state, bundle, _snapshot = _build_world()
    state.groups["boundary_io"].demand = bad_value  # type: ignore[assignment]

    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


def test_snapshot_rejects_source_key_collision_hidden_by_legacy_coercion() -> None:
    valid_state, bundle, _snapshot = _build_world()
    invalid_state = _state_from_sources(_artifact_sources())
    valid_state.canonical_rules["snapshot_test_metadata"]["collision"] = {"1": "v"}
    invalid_state.canonical_rules["snapshot_test_metadata"]["collision"] = {1: "v"}

    assert compute_source_digest(valid_state) == compute_source_digest(invalid_state)
    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(invalid_state, bundle)


@pytest.mark.parametrize(
    "collision_items",
    [
        [(1, "integer"), ("1", "string")],
        [("1", "string"), (1, "integer")],
    ],
    ids=["integer-first", "string-first"],
)
def test_snapshot_rejects_conflicting_source_keys_in_any_insertion_order(
    collision_items: list[tuple[object, str]],
) -> None:
    state, bundle, _snapshot = _build_world()
    state.canonical_rules["snapshot_test_metadata"]["collision"] = dict(collision_items)

    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_snapshot_rejects_non_finite_source_payload_numbers(bad_value: float) -> None:
    state, bundle, _snapshot = _build_world()
    state.commodity_demands = {"iron_plate": bad_value}  # type: ignore[dict-item]

    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


@pytest.mark.parametrize(
    "bad_demands",
    [
        {1: 7},
        {"iron_plate": True},
        {"iron_plate": _MutableInt(7)},
    ],
    ids=["non-string-key", "bool-value", "int-subclass-value"],
)
def test_snapshot_strictly_validates_commodity_demands_source_payload(bad_demands: object) -> None:
    state, bundle, _snapshot = _build_world()
    state.commodity_demands = bad_demands  # type: ignore[assignment]

    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


def test_snapshot_recomputes_source_digest_instead_of_trusting_optional_note() -> None:
    state, bundle, _snapshot = _build_world()
    state.source_digest = None
    expected_source_digest = compute_source_digest(state)

    without_note = build_validated_state_snapshot(state, bundle)

    state.source_digest = "9" * 64
    assert compute_source_digest(state) == expected_source_digest
    with_stale_note = build_validated_state_snapshot(state, bundle)

    assert without_note.source_digest == expected_source_digest
    assert with_stale_note.source_digest == expected_source_digest
    assert without_note.digest == with_stale_note.digest


def test_snapshot_side_effect_iteration_either_fails_closed_or_stays_self_consistent() -> None:
    state, bundle, _snapshot = _build_world()
    hostile_groups = _FlipGroupOnSecondItems(state.groups)
    state.groups = hostile_groups

    try:
        snapshot = build_validated_state_snapshot(state, bundle)
    except SnapshotValidationError:
        assert hostile_groups.items_calls >= 1
        return

    assert hostile_groups.items_calls >= 1
    state.groups = {
        group_id: GroupState(
            group_id=group.group_id,
            demand=group.demand,
            pose_domain=group.pose_domain,
            selected_poses=list(group.selected_poses),
        )
        for group_id, group in snapshot.groups.items()
    }
    assert snapshot.source_digest == compute_source_digest(state)
    f1 = snapshot.family_inputs["region_capacity"]
    f6 = snapshot.family_inputs["shape_packing_hall"]
    assert isinstance(f1, F1RegionInputs)
    assert isinstance(f6, F6HallInputs)
    assert f1.group_demands == {group_id: group.demand for group_id, group in snapshot.groups.items()}
    assert f6.group_demands == f1.group_demands


def test_snapshot_allows_derived_artifact_hashes_but_rejects_overlap_mismatch() -> None:
    state, bundle, baseline = _build_world()
    derived_name = "derived.snapshot-inputs.json"
    state.artifact_hashes[derived_name] = "5" * 64

    with_derived_hash = build_validated_state_snapshot(state, bundle)

    assert with_derived_hash.artifact_hashes[derived_name] == "5" * 64
    assert with_derived_hash.digest != baseline.digest

    state.artifact_hashes["canonical_rules.json"] = "9" * 64
    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


def test_snapshot_preserves_missing_optional_artifact_identity() -> None:
    sources = _artifact_sources()
    missing_identity = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"
    sources["artifact_hashes"]["commodity_demands"] = missing_identity
    state = _state_from_sources(sources)
    bundle = _bundle_from_sources(sources)

    snapshot = build_validated_state_snapshot(state, bundle)

    assert snapshot.artifact_hashes["commodity_demands"] == missing_identity
    _assert_sha256_hex(bundle.digest)
    _assert_sha256_hex(snapshot.digest)


@pytest.mark.parametrize("attack", ["mapping", "set"])
def test_snapshot_wraps_hostile_container_runtime_errors(attack: str) -> None:
    state, bundle, _snapshot = _build_world()
    if attack == "mapping":
        state.cell_owner = _RuntimeErrorMapping(state.cell_owner)
    else:
        state.ghost_cells = _RuntimeErrorSet(state.ghost_cells)  # type: ignore[assignment]

    with pytest.raises(SnapshotValidationError) as exc_info:
        build_validated_state_snapshot(state, bundle)

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def _corrupt_artifact_binding(state: BState) -> None:
    state.artifact_hashes["canonical_rules.json"] = "9" * 64


def _corrupt_ghost_tuple(state: BState) -> None:
    state.ghost_rect = (11, 17, 2)  # type: ignore[assignment]


def _corrupt_ghost_span(state: BState) -> None:
    state.ghost_rect = (11, 17, 0, 3)


def _corrupt_group_identity(state: BState) -> None:
    state.groups["boundary_alias"] = state.groups.pop("boundary_io")


def _corrupt_group_demand(state: BState) -> None:
    state.groups["boundary_io"].demand = -1


def _corrupt_selected_pose(state: BState) -> None:
    state.groups["boundary_io"].selected_poses.append("not_in_domain")


def _corrupt_cell_coordinate(state: BState) -> None:
    state.cell_owner[(4, "bad")] = ("boundary_io", 0)  # type: ignore[index]


def _corrupt_cell_owner_group(state: BState) -> None:
    state.cell_owner[(5, 5)] = ("missing_group", 0)


def _corrupt_cell_owner_slot(state: BState) -> None:
    state.cell_owner[(5, 5)] = ("boundary_io", 2)


def _corrupt_oracle_capabilities(state: BState) -> None:
    state.available_oracle_versions = frozenset({"", "region_capacity_v1"})


@pytest.mark.parametrize(
    "corrupt",
    [
        _corrupt_artifact_binding,
        _corrupt_ghost_tuple,
        _corrupt_ghost_span,
        _corrupt_group_identity,
        _corrupt_group_demand,
        _corrupt_selected_pose,
        _corrupt_cell_coordinate,
        _corrupt_cell_owner_group,
        _corrupt_cell_owner_slot,
        _corrupt_oracle_capabilities,
    ],
    ids=lambda corrupt: corrupt.__name__.removeprefix("_corrupt_"),
)
def test_snapshot_builder_fails_closed_on_invalid_dynamic_state(corrupt: Callable[[BState], None]) -> None:
    state, bundle, _snapshot = _build_world()
    corrupt(state)

    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


@pytest.mark.parametrize("case", ["missing_group_mapping", "missing_pose", "duplicate_pose", "malformed_pose_cell"])
def test_snapshot_builder_fails_closed_on_incomplete_static_projection(case: str) -> None:
    sources = _artifact_sources()
    if case == "missing_group_mapping":
        del sources["instance_to_facility_type"]["boundary_io"]
    elif case == "missing_pose":
        sources["candidate_placements"]["facility_pools"]["boundary_storage_port"] = []
    elif case == "duplicate_pose":
        pose = deepcopy(sources["candidate_placements"]["facility_pools"]["boundary_storage_port"][0])
        sources["candidate_placements"]["facility_pools"]["boundary_storage_port"].append(pose)
    else:
        sources["candidate_placements"]["facility_pools"]["boundary_storage_port"][0]["occupied_cells"] = [[0, 1, 2]]
    state = _state_from_sources(sources)
    bundle = _bundle_from_sources(sources)

    with pytest.raises(SnapshotValidationError):
        build_validated_state_snapshot(state, bundle)


def test_validated_snapshot_constructor_is_private_and_has_one_production_callsite() -> None:
    _state, _bundle, snapshot = _build_world()
    public_fields = {
        field.name: getattr(snapshot, field.name)
        for field in fields(snapshot)
        if field.init and not field.name.startswith("_")
    }
    public_fields["digest"] = "0" * 64

    with pytest.raises((TypeError, ValueError)):
        ValidatedStateSnapshot(**public_fields)
    with pytest.raises((TypeError, ValueError)):
        replace(snapshot, digest="0" * 64)

    callsites: list[tuple[Path, str | None, int]] = []
    production_files = [
        path for path in sorted(SRC_ROOT.rglob("*.py")) if path != TESTS_ROOT and TESTS_ROOT not in path.parents
    ]
    for path in production_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == "ValidatedStateSnapshot")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "ValidatedStateSnapshot")
                )
            ):
                continue
            ancestor: ast.AST | None = node
            while ancestor is not None and not isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ancestor = parents.get(ancestor)
            function_name = ancestor.name if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
            callsites.append((path, function_name, node.lineno))

    assert len(callsites) == 1, callsites
    path, function_name, _line_number = callsites[0]
    assert path == STATE_SNAPSHOT_PATH
    assert function_name == "build_validated_state_snapshot"


def _require_mapping(value: object) -> Mapping[str, Any]:
    assert isinstance(value, Mapping)
    return value


def _rebuild_family_inputs(
    snapshot: ValidatedStateSnapshot,
    bundle: FrozenArtifactBundle,
) -> Mapping[str, F1RegionInputs | F5PatternNogoodInputs | F6HallInputs | F7PowerInputs]:
    group_demands = MappingProxyType({group_id: group.demand for group_id, group in snapshot.groups.items()})
    group_pose_domains = MappingProxyType({group_id: group.pose_domain for group_id, group in snapshot.groups.items()})
    group_to_facility_type = MappingProxyType(
        {group_id: facility_type for group_id, facility_type in bundle.instance_to_facility_type.items()}
    )

    placement_rules: dict[str, str] = {}
    dimensions: dict[str, tuple[int, int]] = {}
    needs_power: dict[str, bool] = {}
    for facility_type, raw_template in bundle.facility_templates.items():
        template = _require_mapping(raw_template)
        placement_rule = template.get("placement_rule", "free")
        raw_dimensions = _require_mapping(template["dimensions"])
        assert type(placement_rule) is str
        assert type(raw_dimensions["w"]) is int
        assert type(raw_dimensions["h"]) is int
        assert type(template.get("needs_power", False)) is bool
        placement_rules[facility_type] = placement_rule
        dimensions[facility_type] = (raw_dimensions["w"], raw_dimensions["h"])
        needs_power[facility_type] = template.get("needs_power", False)

    pose_occupied_cells: dict[tuple[str, str], frozenset[tuple[int, int]]] = {}
    pools = _require_mapping(bundle.candidate_placements["facility_pools"])
    for facility_type, raw_pool in pools.items():
        assert isinstance(raw_pool, tuple)
        for raw_pose in raw_pool:
            pose = _require_mapping(raw_pose)
            pose_id = pose["pose_id"]
            raw_cells = pose["occupied_cells"]
            assert type(pose_id) is str
            assert isinstance(raw_cells, tuple)
            pose_occupied_cells[(facility_type, pose_id)] = frozenset(
                (raw_cell[0], raw_cell[1]) for raw_cell in raw_cells
            )

    canonical_templates = _require_mapping(bundle.canonical_rules["facility_templates"])
    pole = _require_mapping(canonical_templates["power_pole"])
    raw_pole_dimensions = _require_mapping(pole["dimensions"])
    raw_radius = pole["power_coverage_radius"]
    assert type(raw_radius) in (int, float)
    assert type(raw_pole_dimensions["w"]) is int
    assert type(raw_pole_dimensions["h"]) is int

    frozen_rules = MappingProxyType(placement_rules)
    frozen_dimensions = MappingProxyType(dimensions)
    frozen_needs_power = MappingProxyType(needs_power)
    frozen_pose_cells = MappingProxyType(pose_occupied_cells)
    f1 = F1RegionInputs(
        group_demands=group_demands,
        group_pose_domains=group_pose_domains,
        pose_occupied_cells=frozen_pose_cells,
        instance_to_facility_type=group_to_facility_type,
        template_placement_rules=frozen_rules,
        template_dimensions=frozen_dimensions,
    )
    f5 = F5PatternNogoodInputs(
        facility_pools=pools,
        canonical_rules=bundle.canonical_rules,
        instance_to_facility_type=group_to_facility_type,
        facility_templates=bundle.facility_templates,
        group_demands=group_demands,
        group_pose_domains=group_pose_domains,
        artifact_hashes=snapshot.artifact_hashes,
    )
    f6 = F6HallInputs(
        group_demands=group_demands,
        group_to_facility_type=group_to_facility_type,
        template_placement_rules=frozen_rules,
        template_dimensions=frozen_dimensions,
        ghost=snapshot.ghost,
    )
    f7 = F7PowerInputs(
        ghost=snapshot.ghost,
        group_pose_domains=group_pose_domains,
        group_to_facility_type=group_to_facility_type,
        template_needs_power=frozen_needs_power,
        pose_occupied_cells=frozen_pose_cells,
        cell_owner=snapshot.cell_owner,
        pole_radius=float(raw_radius),
        pole_dimensions=(raw_pole_dimensions["w"], raw_pole_dimensions["h"]),
    )
    return MappingProxyType(
        {
            "pattern_nogood": f5,
            "power_hitting_set": f7,
            "region_capacity": f1,
            "shape_packing_hall": f6,
        }
    )


def test_family_inputs_equal_independent_derivation_from_snapshot_and_bundle() -> None:
    _state, bundle, snapshot = _build_world()

    rebuilt = _rebuild_family_inputs(snapshot, bundle)

    assert rebuilt == snapshot.family_inputs
    for family, inputs in rebuilt.items():
        assert inputs == snapshot.family_inputs[family]


def test_family_input_values_are_typed_and_deeply_frozen() -> None:
    _state, _bundle, snapshot = _build_world()

    assert set(snapshot.family_inputs) == {
        "pattern_nogood",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    }
    assert isinstance(snapshot.family_inputs["region_capacity"], F1RegionInputs)
    assert isinstance(snapshot.family_inputs["pattern_nogood"], F5PatternNogoodInputs)
    assert isinstance(snapshot.family_inputs["shape_packing_hall"], F6HallInputs)
    assert isinstance(snapshot.family_inputs["power_hitting_set"], F7PowerInputs)
    assert isinstance(snapshot.family_inputs, MappingProxyType)

    f1 = snapshot.family_inputs["region_capacity"]
    f5 = snapshot.family_inputs["pattern_nogood"]
    f6 = snapshot.family_inputs["shape_packing_hall"]
    f7 = snapshot.family_inputs["power_hitting_set"]
    assert {field.name for field in fields(F1RegionInputs)} == {
        "group_demands",
        "group_pose_domains",
        "instance_to_facility_type",
        "pose_occupied_cells",
        "template_dimensions",
        "template_placement_rules",
    }
    assert {field.name for field in fields(F5PatternNogoodInputs)} == {
        "artifact_hashes",
        "canonical_rules",
        "facility_pools",
        "facility_templates",
        "group_demands",
        "group_pose_domains",
        "instance_to_facility_type",
    }
    assert {field.name for field in fields(F6HallInputs)} == {
        "ghost",
        "group_demands",
        "group_to_facility_type",
        "template_dimensions",
        "template_placement_rules",
    }
    assert {field.name for field in fields(F7PowerInputs)} == {
        "cell_owner",
        "ghost",
        "group_pose_domains",
        "group_to_facility_type",
        "pole_dimensions",
        "pole_radius",
        "pose_occupied_cells",
        "template_needs_power",
    }

    assert f1.group_demands == {"boundary_io": 2, "crusher_blue_iron": 1}
    assert f1.group_pose_domains["boundary_io"] == frozenset({"shared_pose", "boundary_alt"})
    assert f1.instance_to_facility_type == {
        "boundary_io": "boundary_storage_port",
        "crusher_blue_iron": "manufacturing_3x3",
    }
    assert set(f1.pose_occupied_cells) == {
        ("boundary_storage_port", "boundary_alt"),
        ("boundary_storage_port", "shared_pose"),
        ("manufacturing_3x3", "shared_pose"),
    }
    assert f1.pose_occupied_cells[("boundary_storage_port", "shared_pose")] == frozenset({(0, 1), (0, 2), (0, 3)})
    assert f1.template_placement_rules["boundary_storage_port"] == "left_or_bottom_boundary"
    assert f1.template_dimensions["boundary_storage_port"] == (1, 3)

    assert f5.group_demands is f1.group_demands
    assert f5.group_pose_domains is f1.group_pose_domains
    assert f5.instance_to_facility_type is f1.instance_to_facility_type
    assert f5.artifact_hashes is snapshot.artifact_hashes
    assert f5.facility_pools == _require_mapping(_bundle.candidate_placements["facility_pools"])
    assert f5.canonical_rules is _bundle.canonical_rules
    assert f5.facility_templates is _bundle.facility_templates

    assert f6.group_demands == f1.group_demands
    assert f6.group_to_facility_type == f1.instance_to_facility_type
    assert f6.template_placement_rules == f1.template_placement_rules
    assert f6.template_dimensions == f1.template_dimensions
    assert f6.ghost is snapshot.ghost

    assert f7.ghost is snapshot.ghost
    assert f7.group_pose_domains == f1.group_pose_domains
    assert f7.group_to_facility_type == f1.instance_to_facility_type
    assert f7.template_needs_power == {
        "boundary_storage_port": False,
        "manufacturing_3x3": True,
        "power_pole": False,
    }
    assert f7.pose_occupied_cells == f1.pose_occupied_cells
    assert f7.cell_owner is snapshot.cell_owner
    assert f7.pole_radius == 5
    assert f7.pole_dimensions == (2, 2)

    digest_before = snapshot.digest
    with pytest.raises(TypeError):
        snapshot.family_inputs["attacker"] = snapshot.family_inputs["region_capacity"]
    with pytest.raises(TypeError):
        f1.group_demands["boundary_io"] = 999
    with pytest.raises(TypeError):
        f5.facility_pools["attacker"] = ()
    with pytest.raises(TypeError):
        f5.canonical_rules["globals"]["grid"]["width"] = 999
    with pytest.raises(AttributeError):
        f1.pose_occupied_cells[("boundary_storage_port", "shared_pose")].add((69, 69))
    with pytest.raises(TypeError):
        f7.cell_owner[(69, 69)] = ("attacker", 0)
    with pytest.raises(AttributeError):
        f7.pole_radius = 999
    assert snapshot.digest == digest_before

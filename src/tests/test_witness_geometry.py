from __future__ import annotations

import importlib
import itertools
import json
from pathlib import Path

import pytest


geometry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.geometry"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRICT_INSTANCE = (
    PROJECT_ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
)
CANDIDATE_POOL = PROJECT_ROOT / "data/preprocessed/candidate_placements.json"


def _strict_instance() -> dict:
    return json.loads(STRICT_INSTANCE.read_text(encoding="utf-8"))


def test_boundary_enumeration_is_exact_47_patterns() -> None:
    patterns = geometry.enumerate_boundary_patterns()

    assert len(patterns) == 47
    assert len(set(patterns)) == 47
    assert patterns[0] == geometry.BoundaryPattern(0, 0)
    assert {pattern.left_gap for pattern in patterns} == set(range(0, 70, 3))
    assert {pattern.bottom_gap for pattern in patterns} == set(range(0, 70, 3))
    assert all(pattern.left_gap == 0 or pattern.bottom_gap == 0 for pattern in patterns)
    with pytest.raises(geometry.GeometryContractError):
        geometry.BoundaryPattern(3, 6)


def test_boundary_anchor_phase_shift_and_preferred_order() -> None:
    assert geometry.boundary_anchors(0) == tuple(range(1, 68, 3))
    assert geometry.boundary_anchors(69) == tuple(range(0, 69, 3))
    assert set(range(70)) - {
        cell
        for anchor in geometry.boundary_anchors(30)
        for cell in range(anchor, anchor + 3)
    } == {30}

    patterns = geometry.enumerate_boundary_patterns(preferred=(69, 0))
    assert patterns[0] == geometry.BoundaryPattern(69, 0)
    assert len(patterns) == len(set(patterns)) == 47


def test_boundary_ids_are_assigned_deterministically_and_bodies_do_not_overlap() -> None:
    ids = [f"boundary_port_{index:03d}" for index in range(46, 0, -1)]
    placements = geometry.place_boundary_instances(ids, geometry.BoundaryPattern(69, 0))

    assert [placement.instance_id for placement in placements] == sorted(ids)
    assert [placement.side for placement in placements[:23]] == ["left"] * 23
    assert [placement.side for placement in placements[23:]] == ["bottom"] * 23
    assert [placement.anchor[1] for placement in placements[:23]] == list(range(0, 69, 3))
    assert [placement.anchor[0] for placement in placements[23:]] == list(range(1, 68, 3))
    bodies = [cell for placement in placements for cell in placement.body_cells]
    assert len(bodies) == len(set(bodies)) == 138
    assert all(geometry.cells_in_grid(placement.front_cells) for placement in placements)
    assert placements[0].front_cells == frozenset({(1, 1)})


@pytest.mark.parametrize(
    ("name", "protected_size"),
    [
        ("vertical_comb", (6, 7)),
        ("horizontal_comb", (7, 6)),
        ("dual_spine_shelf", (6, 7)),
    ],
)
def test_corridor_templates_are_connected_and_reserve_core_and_empty_rect(
    name: str, protected_size: tuple[int, int]
) -> None:
    template = geometry.generate_corridor_template(name)

    assert geometry.four_connected(template.corridor_cells)
    assert template.core_ring_cells <= template.corridor_cells
    assert not (template.core_body_cells & template.corridor_cells)
    assert not (template.core_body_cells & template.protected_body_rect.cells)
    assert (template.protected_body_rect.width, template.protected_body_rect.height) == protected_size
    assert template.protected_body_rect.width * template.protected_body_rect.height == 42
    assert template.protected_body_rect.cells <= template.body_reservation_cells
    assert template.corridor_cells <= template.body_reservation_cells
    assert 0 < len(template.corridor_cells) < 1348
    assert template.cross_bays
    for x, y in template.cross_bays:
        assert {(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)} <= template.corridor_cells


def test_candidate_front_coordinate_is_identity_not_direction_plus_one() -> None:
    pools = json.loads(CANDIDATE_POOL.read_text(encoding="utf-8"))["facility_pools"]
    candidate = pools["manufacturing_3x3"][0]
    candidate_geometry = geometry.candidate_pose_geometry(candidate)
    strict_mode = next(
        mode
        for mode in _strict_instance()["facility_templates"]["manufacturing_3x3"]["modes"]
        if mode["id"] == "north_to_south"
    )
    strict_geometry = geometry.strict_mode_geometry(strict_mode, (0, 1))

    # The stored N ports are y=4 already.  A historical double offset made y=5.
    assert candidate_geometry.input_front_cells == ((0, 4), (1, 4), (2, 4))
    assert candidate_geometry == strict_geometry


def test_collision_report_blocks_body_on_body_front_corridor_and_protected_cells() -> None:
    pose = geometry.PoseGeometry(
        body_cells=frozenset({(4, 4), (4, 5)}),
        input_front_cells=((3, 4),),
        output_front_cells=((5, 5),),
    )
    report = geometry.collision_report(
        pose,
        occupied_body_cells={(4, 4), (3, 4)},
        reserved_active_front_cells={(4, 5)},
        forbidden_body_cells={(4, 4)},
    )

    assert report.body_overlap == frozenset({(4, 4)})
    assert report.body_on_reserved_front == frozenset({(4, 5)})
    assert report.body_on_forbidden == frozenset({(4, 4)})
    assert report.front_blocked_by_body == frozenset({(3, 4)})
    assert not report.ok


def test_g0_requires_all_fronts_but_g1_selects_only_required_fronts() -> None:
    pose = geometry.PoseGeometry(
        body_cells=frozenset({(5, 5)}),
        input_front_cells=((4, 5), (5, 4)),
        output_front_cells=((6, 5), (5, 6)),
    )
    partial_corridor = {(4, 5), (6, 5)}

    assert not geometry.g0_eligible(pose, partial_corridor)
    selected = geometry.select_g1_fronts(
        pose,
        partial_corridor,
        required_inputs=1,
        required_outputs=1,
    )
    assert selected == geometry.G1Selection(((4, 5),), ((6, 5),))
    assert geometry.g1_eligible(
        pose,
        partial_corridor,
        required_inputs=1,
        required_outputs=1,
    )
    assert not geometry.g1_eligible(
        pose,
        partial_corridor,
        required_inputs=2,
        required_outputs=1,
    )


def test_power_lattice_is_nonoverlapping_and_canonical_stencils_cover_grid() -> None:
    anchors = geometry.pole_bay_lattice()
    footprints = [geometry.pole_footprint(anchor) for anchor in anchors]

    assert len(anchors) == 144
    assert not any(left & right for left, right in itertools.combinations(footprints, 2))
    assert set().union(*(geometry.pole_coverage_cells(anchor) for anchor in anchors)) == {
        (x, y) for x in range(70) for y in range(70)
    }
    assert len(geometry.pole_coverage_cells((10, 10))) == 12 * 12
    assert geometry.pole_coverage_cells((0, 0)) == {
        (x, y) for x in range(7) for y in range(7)
    }


def test_minimum_pole_set_cover_is_exact_and_fail_closed_when_uncoverable() -> None:
    powered = {
        "a": {(5, 5)},
        "b": {(10, 5)},
        "c": {(30, 30)},
    }
    candidates = [(0, 0), (6, 0), (24, 24)]
    occupied = set().union(*powered.values())

    result = geometry.minimum_pole_set_cover(
        powered,
        candidates,
        blocked_body_cells=occupied,
    )
    assert result.feasible and result.optimal
    assert result.selected_anchors == ((6, 0), (24, 24))
    assert not result.uncovered_instance_ids
    assert all(
        any(body & geometry.pole_coverage_cells(anchor) for anchor in result.selected_anchors)
        for body in powered.values()
    )
    assert not any(
        all(body & geometry.pole_coverage_cells(anchor) for body in powered.values())
        for anchor in candidates
    )

    infeasible = geometry.minimum_pole_set_cover(
        powered,
        candidates[:2],
        blocked_body_cells=occupied,
    )
    assert not infeasible.feasible
    assert infeasible.optimal
    assert infeasible.uncovered_instance_ids == ("c",)
    assert infeasible.selected_anchors == ()


def test_storage_box_schedule_is_zero_then_one_then_two() -> None:
    assert geometry.storage_box_schedule() == (0, 1, 2)
    assert geometry.storage_box_schedule(0) == (0,)
    with pytest.raises(geometry.GeometryContractError):
        geometry.storage_box_schedule(3)


def test_real_strict_instances_collapse_to_17_manufacturing_groups() -> None:
    groups = geometry.build_operation_groups(_strict_instance()["required_instances"])

    assert len(groups) == 17
    assert sum(group.multiplicity for group in groups) == 219
    assert [group.operation for group in groups] == sorted(group.operation for group in groups)
    assert all(group.template.startswith("manufacturing_") for group in groups)


def test_group_pose_assignment_is_row_major_and_geometry_fingerprint_ignores_ids() -> None:
    group = geometry.OperationGroup("demo", "manufacturing_3x3", ("demo_001", "demo_002"))
    poses = [
        {"anchor": {"x": 8, "y": 9}, "mode": "south_to_north", "pose_idx": 4},
        {"anchor": {"x": 20, "y": 2}, "mode": "north_to_south", "pose_idx": 7},
    ]
    assigned = geometry.deterministic_assign_group_poses(group, poses)

    assert [(record["id"], record["anchor"]) for record in assigned] == [
        ("demo_001", {"x": 20, "y": 2}),
        ("demo_002", {"x": 8, "y": 9}),
    ]
    renamed = [dict(record, id=f"other_{index}") for index, record in enumerate(assigned)]
    assert geometry.geometry_fingerprint(assigned) == geometry.geometry_fingerprint(renamed)
    assert geometry.geometry_fingerprint(assigned, include_instance_ids=True) != geometry.geometry_fingerprint(
        renamed, include_instance_ids=True
    )

    tabu = geometry.GeometryTabu()
    fingerprint, is_new = tabu.remember(assigned)
    assert is_new
    assert len(fingerprint) == 64
    assert tabu.contains(renamed)
    assert tabu.remember(renamed) == (fingerprint, False)

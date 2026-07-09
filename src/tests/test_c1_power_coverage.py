"""Batch 1B tests for C1 native power coverage."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import pytest
from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel
from src.search.exact_campaign import _is_authorized_exact_pose_optional_solution_entry


def _coverage_cells(
    x_val: int,
    y_val: int,
    *,
    width: int,
    height: int,
    radius: int = 1,
) -> List[List[int]]:
    return [
        [x, y]
        for x in range(
            max(0, int(x_val) - int(radius)),
            min(int(width) - 1, int(x_val) + 2 + int(radius) - 1) + 1,
        )
        for y in range(
            max(0, int(y_val) - int(radius)),
            min(int(height) - 1, int(y_val) + 2 + int(radius) - 1) + 1,
        )
    ]


def _power_pole_pool(
    width: int,
    height: int,
    *,
    radius: int = 1,
    pole_width: int = 1,
    pole_height: int = 1,
) -> List[Dict[str, Any]]:
    return [
        {
            "pose_id": f"pole_{x}_{y}",
            "anchor": {"x": x, "y": y},
            "pose_params": {"orientation": "north", "port_mode": "none"},
            "occupied_cells": [
                [x + dx, y + dy]
                for dx in range(int(pole_width))
                for dy in range(int(pole_height))
            ],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": _coverage_cells(
                x,
                y,
                width=width,
                height=height,
                radius=radius,
            ),
        }
        for y in range(int(height) - int(pole_height) + 1)
        for x in range(int(width) - int(pole_width) + 1)
    ]


def _machine_pose(x_val: int, y_val: int) -> Dict[str, Any]:
    return {
        "pose_id": f"machine_{x_val}_{y_val}",
        "anchor": {"x": int(x_val), "y": int(y_val)},
        "pose_params": {"orientation": "north", "port_mode": "none"},
        "occupied_cells": [[int(x_val), int(y_val)]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


def _mandatory_machine_instances(count: int = 1) -> List[Dict[str, Any]]:
    return [
        {
            "instance_id": f"machine_{idx}",
            "facility_type": "machine",
            "operation_type": "crafting",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for idx in range(int(count))
    ]


def _rules(
    *,
    width: int,
    height: int,
    radius: int = 1,
    include_protocol_box: bool = False,
    machine_needs_power: bool = True,
    pole_width: int = 1,
    pole_height: int = 1,
) -> Dict[str, Any]:
    templates: Dict[str, Any] = {
        "machine": {
            "dimensions": {"w": 1, "h": 1},
            "needs_power": bool(machine_needs_power),
        },
        "power_pole": {
            "dimensions": {"w": int(pole_width), "h": int(pole_height)},
            "needs_power": False,
            "power_coverage_radius": int(radius),
        },
    }
    if include_protocol_box:
        templates["protocol_storage_box"] = {
            "dimensions": {"w": 1, "h": 1},
            "needs_power": True,
        }
    return {
        "globals": {"grid": {"width": int(width), "height": int(height)}},
        "facility_templates": templates,
    }


def _solve_coordinate(
    *,
    c1: bool,
    instances: Sequence[Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    ghost_rect: Optional[Tuple[int, int]] = None,
    ghost_anchor_filter: Optional[Sequence[Tuple[int, int]]] = None,
    required_counts: Optional[Mapping[str, int]] = None,
    mutate: Optional[Callable[[MasterPlacementModel], None]] = None,
) -> Tuple[int, MasterPlacementModel]:
    model = MasterPlacementModel(
        instances=instances,
        facility_pools={
            str(tpl): [dict(pose) for pose in pool] for tpl, pool in pools.items()
        },
        rules=rules,
        ghost_rect=ghost_rect,
        ghost_anchor_filter=(
            None
            if ghost_anchor_filter is None
            else {(int(x), int(y)) for x, y in ghost_anchor_filter}
        ),
        solve_mode="certified_exact",
        skip_power_coverage=False,
        c1_power_pole_representation=bool(c1),
        exact_required_pose_optional_counts=required_counts,
    )
    model.build()
    if mutate is not None:
        mutate(model)
    return model.solve(time_limit_seconds=5.0), model


def _selected_power_poles(model: MasterPlacementModel) -> Dict[str, Mapping[str, Any]]:
    return {
        str(key): dict(entry)
        for key, entry in model.extract_solution().items()
        if str(key).startswith("pose_optional::power_pole::")
    }


def _c1_pole_var_for_anchor(model: MasterPlacementModel, anchor: Tuple[int, int]):
    delegate = model._coordinate_delegate
    assert delegate is not None
    for pose_idx, var, _coverage in delegate._c1_pole_bools:
        pose = model.facility_pools["power_pole"][int(pose_idx)]
        pose_anchor = dict(pose["anchor"])
        if (int(pose_anchor["x"]), int(pose_anchor["y"])) == anchor:
            return var
    raise AssertionError(f"missing C1 pole bool for anchor {anchor!r}")


def _force_power_pole_anchor(
    model: MasterPlacementModel,
    anchor: Tuple[int, int],
) -> None:
    delegate = model._coordinate_delegate
    assert delegate is not None
    if delegate.c1_power_pole_representation:
        model.model.Add(_c1_pole_var_for_anchor(model, anchor) == 1)
        return
    pole_slots = list(delegate.required_optional_slots.get("power_pole", []))
    pole_slots.extend(delegate.residual_optional_slots.get("power_pole", []))
    assert len(pole_slots) == 1
    pole_slot = pole_slots[0]
    if pole_slot.active is not None:
        model.model.Add(pole_slot.active == 1)
    model.model.Add(pole_slot.x == int(anchor[0]))
    model.model.Add(pole_slot.y == int(anchor[1]))


def _ghost_lex_pair(model: MasterPlacementModel) -> Tuple[int, int]:
    ghost_pick = model.extract_solution().get("ghost_pick")
    assert ghost_pick is not None
    selected_domain = model._ghost_domains[int(ghost_pick["pose_idx"])]
    cells = [(int(cell[0]), int(cell[1])) for cell in selected_domain["cells"]]
    assert cells
    width = max(x for x, _y in cells) - min(x for x, _y in cells) + 1
    height = max(y for _x, y in cells) - min(y for _x, y in cells) + 1
    assert len(cells) == int(width * height)
    return int(width * height), int(min(width, height))


def test_c1_matches_old_witness_for_mandatory_powered_fixture() -> None:
    pools = {
        "machine": [_machine_pose(0, 0)],
        "power_pole": _power_pole_pool(2, 1),
    }
    rules = _rules(width=2, height=1)
    instances = _mandatory_machine_instances()

    old_status, old_model = _solve_coordinate(
        c1=False,
        instances=instances,
        pools=pools,
        rules=rules,
    )
    c1_status, c1_model = _solve_coordinate(
        c1=True,
        instances=instances,
        pools=pools,
        rules=rules,
    )

    assert c1_status == old_status
    assert c1_status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert {
        (entry["anchor"]["x"], entry["anchor"]["y"])
        for entry in _selected_power_poles(c1_model).values()
    } == {
        (entry["anchor"]["x"], entry["anchor"]["y"])
        for entry in _selected_power_poles(old_model).values()
    }


def test_c1_matches_old_witness_when_ghost_blocks_only_covering_pole() -> None:
    pools = {
        "machine": [_machine_pose(0, 0)],
        "power_pole": _power_pole_pool(2, 1),
    }
    rules = _rules(width=2, height=1)
    instances = _mandatory_machine_instances()

    old_status, _old_model = _solve_coordinate(
        c1=False,
        instances=instances,
        pools=pools,
        rules=rules,
        ghost_rect=(1, 1),
        ghost_anchor_filter=[(1, 0)],
    )
    c1_status, _c1_model = _solve_coordinate(
        c1=True,
        instances=instances,
        pools=pools,
        rules=rules,
        ghost_rect=(1, 1),
        ghost_anchor_filter=[(1, 0)],
    )

    assert old_status == cp_model.INFEASIBLE
    assert c1_status == old_status


def test_c1_matches_old_witness_with_ghost_and_lex_pair() -> None:
    pools = {
        "machine": [_machine_pose(0, 0)],
        "power_pole": _power_pole_pool(5, 3),
    }
    rules = _rules(width=5, height=3)
    instances = _mandatory_machine_instances()
    candidate_sizes = ((1, 1), (4, 1), (2, 2))
    lex_pairs_by_representation: Dict[bool, List[Tuple[int, int]]] = {}

    for c1 in (False, True):
        for ghost_anchor in ((3, 0), (3, 1)):
            anchor_status, _anchor_model = _solve_coordinate(
                c1=c1,
                instances=instances,
                pools=pools,
                rules=rules,
                ghost_rect=(2, 2),
                ghost_anchor_filter=[ghost_anchor],
            )
            assert anchor_status == cp_model.OPTIMAL

        lex_pairs: List[Tuple[int, int]] = []
        for ghost_rect in candidate_sizes:
            status, model = _solve_coordinate(
                c1=c1,
                instances=instances,
                pools=pools,
                rules=rules,
                ghost_rect=ghost_rect,
            )
            assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
            assert model.build_stats["ghost_rect"]["placements"] > 1
            lex_pairs.append(_ghost_lex_pair(model))
        lex_pairs_by_representation[c1] = lex_pairs

    assert len(set(lex_pairs_by_representation[False])) > 1
    assert max(lex_pairs_by_representation[True]) == max(
        lex_pairs_by_representation[False]
    ) == (4, 2)


def test_c1_two_dimensional_cov_channel_uses_row_major_flat_index() -> None:
    pools = {
        "machine": [_machine_pose(3, 1)],
        "power_pole": _power_pole_pool(4, 3, radius=0),
    }
    rules = _rules(width=4, height=3, radius=0)
    statuses = []

    for c1 in (False, True):
        status, _model = _solve_coordinate(
            c1=c1,
            instances=_mandatory_machine_instances(),
            pools=pools,
            rules=rules,
            mutate=lambda model: _force_power_pole_anchor(model, (2, 0)),
        )
        statuses.append(status)

    assert statuses == [cp_model.OPTIMAL, cp_model.OPTIMAL]


def test_c1_empty_pool_matches_old_optional_active_guard() -> None:
    pools = {
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "north", "port_mode": "none"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": [],
    }
    rules = _rules(width=2, height=1, include_protocol_box=True)

    def force_box_active(model: MasterPlacementModel) -> None:
        delegate = model._coordinate_delegate
        assert delegate is not None
        slot = delegate.residual_optional_slots["protocol_storage_box"][0]
        assert slot.active is not None
        model.model.Add(slot.active == 1)

    old_status, _old_model = _solve_coordinate(
        c1=False,
        instances=[],
        pools=pools,
        rules=rules,
        mutate=force_box_active,
    )
    c1_status, c1_model = _solve_coordinate(
        c1=True,
        instances=[],
        pools=pools,
        rules=rules,
        mutate=force_box_active,
    )

    assert old_status == cp_model.INFEASIBLE
    assert c1_status == old_status
    assert c1_model.build_stats["power_coverage"]["pole_pose_bools"] == 0


def test_c1_empty_pool_leaves_optional_powered_slot_inactive_and_feasible() -> None:
    pools = {
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "north", "port_mode": "none"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": [],
    }
    rules = _rules(width=2, height=1, include_protocol_box=True)

    for c1 in (False, True):
        status, model = _solve_coordinate(
            c1=c1,
            instances=[],
            pools=pools,
            rules=rules,
        )
        assert status == cp_model.OPTIMAL
        delegate = model._coordinate_delegate
        assert delegate is not None
        slot = delegate.residual_optional_slots["protocol_storage_box"][0]
        assert slot.active is not None
        assert model._solver.Value(slot.active) == 0


def test_c1_empty_pool_mandatory_powered_is_infeasible() -> None:
    status, model = _solve_coordinate(
        c1=True,
        instances=_mandatory_machine_instances(),
        pools={"machine": [_machine_pose(0, 0)], "power_pole": []},
        rules=_rules(width=2, height=1),
    )

    assert status == cp_model.INFEASIBLE
    assert model.build_stats["power_coverage"]["pole_pose_bools"] == 0


def test_c1_capacity_family_counts_feed_power_capacity_bounds() -> None:
    old_status, _old_model = _solve_coordinate(
        c1=False,
        instances=_mandatory_machine_instances(),
        pools={
            "machine": [_machine_pose(0, 0)],
            "power_pole": _power_pole_pool(2, 1),
        },
        rules=_rules(width=2, height=1),
    )
    status, model = _solve_coordinate(
        c1=True,
        instances=_mandatory_machine_instances(),
        pools={
            "machine": [_machine_pose(0, 0)],
            "power_pole": _power_pole_pool(2, 1),
        },
        rules=_rules(width=2, height=1),
    )

    assert status == old_status
    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    capacity = model.build_stats["global_valid_inequalities"][
        "power_capacity_families"
    ]
    assert capacity["applied"] is True
    assert capacity["family_count"] == len(model._coordinate_delegate.power_pole_family_count_vars)


def test_c1_required_power_pole_extracts_authorized_entry() -> None:
    pools = {
        "machine": [_machine_pose(0, 0)],
        "power_pole": _power_pole_pool(2, 1),
    }
    old_status, _old_model = _solve_coordinate(
        c1=False,
        instances=_mandatory_machine_instances(),
        pools=pools,
        rules=_rules(width=2, height=1),
        required_counts={"power_pole": 1},
    )
    status, model = _solve_coordinate(
        c1=True,
        instances=_mandatory_machine_instances(),
        pools=pools,
        rules=_rules(width=2, height=1),
        required_counts={"power_pole": 1},
    )

    assert status == old_status
    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    selected = _selected_power_poles(model)
    assert list(selected) == ["pose_optional::power_pole::pole_1_0"]
    entry = selected["pose_optional::power_pole::pole_1_0"]
    assert _is_authorized_exact_pose_optional_solution_entry(
        instance_id=str(entry["instance_id"]),
        entry=entry,
        pose=pools["power_pole"][int(entry["pose_idx"])],
        facility_type="power_pole",
    )


def test_c1_required_power_pole_without_powered_demand_matches_old() -> None:
    pools = {
        "machine": [_machine_pose(0, 0)],
        "power_pole": _power_pole_pool(2, 1),
    }
    rules = _rules(width=2, height=1, machine_needs_power=False)

    old_status, old_model = _solve_coordinate(
        c1=False,
        instances=_mandatory_machine_instances(),
        pools=pools,
        rules=rules,
        required_counts={"power_pole": 1},
    )
    c1_status, c1_model = _solve_coordinate(
        c1=True,
        instances=_mandatory_machine_instances(),
        pools=pools,
        rules=rules,
        required_counts={"power_pole": 1},
    )

    assert old_status == cp_model.OPTIMAL
    assert c1_status == old_status
    assert len(_selected_power_poles(old_model)) == 1
    assert len(_selected_power_poles(c1_model)) == 1
    assert c1_model.build_stats["power_coverage"]["dominance_bound_terms"] == 0


def test_c1_required_power_pole_exact_count_matches_old_infeasible() -> None:
    pools = {
        "machine": [_machine_pose(0, 0), _machine_pose(7, 7)],
        "power_pole": _power_pole_pool(8, 8),
    }
    rules = _rules(width=8, height=8)
    instances = _mandatory_machine_instances(2)

    old_status, _old_model = _solve_coordinate(
        c1=False,
        instances=instances,
        pools=pools,
        rules=rules,
        required_counts={"power_pole": 1},
    )
    c1_status, _c1_model = _solve_coordinate(
        c1=True,
        instances=instances,
        pools=pools,
        rules=rules,
        required_counts={"power_pole": 1},
    )

    assert old_status == cp_model.INFEASIBLE
    assert c1_status == old_status


def test_c1_two_by_two_pole_lattice_intervals_and_clipped_coverage() -> None:
    pools = {
        "machine": [_machine_pose(5, 3)],
        "power_pole": _power_pole_pool(
            6,
            4,
            radius=1,
            pole_width=2,
            pole_height=2,
        ),
    }
    rules = _rules(
        width=6,
        height=4,
        radius=1,
        pole_width=2,
        pole_height=2,
    )
    expected_anchors = {
        (x, y)
        for y in range(0, 4 - 2 + 1)
        for x in range(0, 6 - 2 + 1)
    }
    assert {
        (int(pose["anchor"]["x"]), int(pose["anchor"]["y"]))
        for pose in pools["power_pole"]
    } == expected_anchors

    for c1 in (False, True):
        clear_status, _clear_model = _solve_coordinate(
            c1=c1,
            instances=_mandatory_machine_instances(),
            pools=pools,
            rules=rules,
            mutate=lambda model: _force_power_pole_anchor(model, (3, 1)),
        )
        blocked_status, _blocked_model = _solve_coordinate(
            c1=c1,
            instances=_mandatory_machine_instances(),
            pools=pools,
            rules=rules,
            ghost_rect=(1, 1),
            ghost_anchor_filter=[(3, 1)],
            mutate=lambda model: _force_power_pole_anchor(model, (3, 1)),
        )
        assert clear_status == cp_model.OPTIMAL
        assert blocked_status == cp_model.INFEASIBLE


@pytest.mark.parametrize("c1", [False, True])
def test_power_pole_whole_layout_benders_cut_is_applied(c1: bool) -> None:
    status, model = _solve_coordinate(
        c1=c1,
        instances=_mandatory_machine_instances(),
        pools={
            "machine": [_machine_pose(0, 0)],
            "power_pole": _power_pole_pool(2, 1),
        },
        rules=_rules(width=2, height=1),
    )
    assert status == cp_model.OPTIMAL
    first_solution = model.extract_solution()
    first_conflict = {
        str(solution_id): int(entry["pose_idx"])
        for solution_id, entry in first_solution.items()
    }
    assert any(
        solution_id.startswith("pose_optional::power_pole::")
        for solution_id in first_conflict
    )

    assert model.add_benders_cut(first_conflict) is True
    assert model.extract_solution() == {}
    assert model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_c1_clone_with_ghost_preserves_coverage_constraints() -> None:
    instances = _mandatory_machine_instances()
    pools = {
        "machine": [_machine_pose(0, 0)],
        "power_pole": _power_pole_pool(5, 1),
    }
    rules = _rules(width=5, height=1)
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=False,
        c1_power_pole_representation=True,
    )
    overlay = MasterPlacementModel.from_exact_core(
        core,
        ghost_rect=(1, 1),
        ghost_anchor_filter=[(3, 0)],
    )
    overlay.model.Add(_c1_pole_var_for_anchor(overlay, (4, 0)) == 1)

    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_c1_build_stats_preserve_old_fields_and_add_new_fields() -> None:
    status, model = _solve_coordinate(
        c1=True,
        instances=_mandatory_machine_instances(),
        pools={
            "machine": [_machine_pose(0, 0)],
            "power_pole": _power_pole_pool(2, 1),
        },
        rules=_rules(width=2, height=1),
    )

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    power_coverage = model.build_stats["power_coverage"]
    for field in (
        "powered_slots",
        "pole_slots",
        "cover_literals",
        "witness_indices",
        "element_constraints",
        "radius",
    ):
        assert field in power_coverage
    assert power_coverage["encoding"] == "c1_pose_bool_cov_channel_v1"
    assert power_coverage["pole_pose_bools"] == 2
    assert power_coverage["cov_channel_literals"] == 2
    assert power_coverage["constant_pole_intervals"] == 4
    assert power_coverage["dominance_bound_terms"] == 1
    assert model.build_stats["master_pose_bool_literals"] == 2


def test_c1_rejects_uniformly_shrunken_power_pole_pool() -> None:
    shrunken_pool = [
        pose
        for pose in _power_pole_pool(3, 3)
        if pose["anchor"]["x"] <= 1 and pose["anchor"]["y"] <= 1
    ]

    with pytest.raises(RuntimeError, match="complete coordinate lattice"):
        _solve_coordinate(
            c1=True,
            instances=[],
            pools={"power_pole": shrunken_pool},
            rules=_rules(width=3, height=3),
        )


def test_c1_rejects_multi_mode_power_poles() -> None:
    pool = _power_pole_pool(2, 1)
    pool.append(
        {
            **pool[0],
            "pose_id": "pole_0_0_alt",
            "pose_params": {"orientation": "south", "port_mode": "none"},
        }
    )

    with pytest.raises(RuntimeError, match="one pose mode"):
        _solve_coordinate(
            c1=True,
            instances=[],
            pools={"power_pole": pool},
            rules=_rules(width=2, height=1),
        )


def test_c1_nonrectangular_powered_footprint_fails_closed() -> None:
    instances = [
        {
            "instance_id": "assembler_0",
            "facility_type": "assembler",
            "operation_type": "crafting",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "assembler": [
            {
                "pose_id": "assembler_l",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "north", "port_mode": "none"},
                "occupied_cells": [[0, 0], [1, 0], [0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": _power_pole_pool(3, 3),
    }
    rules = _rules(width=3, height=3)
    rules["facility_templates"]["assembler"] = {
        "dimensions": {"w": 2, "h": 2},
        "needs_power": True,
    }
    del rules["facility_templates"]["machine"]

    with pytest.raises(NotImplementedError, match="C1 非矩形回退不在批 1B 范围"):
        _solve_coordinate(
            c1=True,
            instances=instances,
            pools=pools,
            rules=rules,
        )

"""Regression tests for coordinate-exact protocol storage lower bounds."""

from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def _protocol_box_pose(*, pose_id: str, x: int, input_slots: int) -> dict[str, object]:
    directions = ["N", "E", "S", "W"]
    return {
        "pose_id": pose_id,
        "anchor": {"x": x, "y": 0},
        "occupied_cells": [[x, 0]],
        "input_port_cells": [
            {"x": x, "y": 0, "dir": directions[index]}
            for index in range(input_slots)
        ],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


def test_protocol_lower_bound_uses_supplied_utility_snapshot_end_to_end() -> None:
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "protocol_storage_box": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
            },
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "protocol_storage_box": [
                _protocol_box_pose(pose_id="box_0", x=0, input_slots=2),
                _protocol_box_pose(pose_id="box_1", x=1, input_slots=2),
            ]
        },
        rules=rules,
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {
                "future_a": 1,
                "future_b": 1,
                "future_c": 1,
            },
        },
        generic_input_slots_by_operation={"future_box_sink": 2},
        utility_operation_by_template={
            "protocol_storage_box": "future_box_sink",
        },
    )

    status = model.solve(time_limit_seconds=2.0)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.utility_operation_by_template == {
        "protocol_storage_box": "future_box_sink",
    }
    assert model._certified_optional_lower_bounds == {
        "protocol_storage_box": 2,
    }
    protocol_stats = model.build_stats["global_valid_inequalities"][
        "optional_cardinality_bounds"
    ]["protocol_storage_box"]
    assert protocol_stats["slots_per_pose"] == 2
    assert protocol_stats["lower"] == 2


def test_protocol_lower_bound_allows_empty_map_for_dormant_toy_project() -> None:
    model = MasterPlacementModel(
        instances=[],
        facility_pools={"protocol_storage_box": []},
        rules={
            "globals": {"grid": {"width": 1, "height": 1}},
            "facility_templates": {
                "protocol_storage_box": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                },
            },
        },
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
        generic_input_slots_by_operation={},
        utility_operation_by_template={},
    )

    model.build()

    assert model._certified_optional_lower_bounds == {}
    protocol_stats = model.build_stats["global_valid_inequalities"][
        "optional_cardinality_bounds"
    ]["protocol_storage_box"]
    assert protocol_stats["slots_per_pose"] == 0
    assert protocol_stats["lower"] == 0


def test_protocol_lower_bound_rejects_missing_map_for_residual_demand() -> None:
    with pytest.raises(
        ValueError,
        match="residual generic-input demand requires a plan-derived utility operation",
    ):
        MasterPlacementModel(
            instances=[],
            facility_pools={
                "protocol_storage_box": [
                    _protocol_box_pose(pose_id="box_0", x=0, input_slots=1),
                ]
            },
            rules={
                "globals": {"grid": {"width": 1, "height": 1}},
                "facility_templates": {
                    "protocol_storage_box": {
                        "dimensions": {"w": 1, "h": 1},
                        "needs_power": False,
                    },
                },
            },
            solve_mode="certified_exact",
            generic_io_requirements={
                "required_generic_outputs": {},
                "required_generic_inputs": {"future_a": 1},
            },
            generic_input_slots_by_operation={"future_box_sink": 1},
            utility_operation_by_template={},
        )


def test_protocol_lower_bound_counts_fixed_required_storage_boxes() -> None:
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [
                    {"x": 0, "y": 0, "dir": "N"},
                    {"x": 0, "y": 0, "dir": "E"},
                    {"x": 0, "y": 0, "dir": "S"},
                ],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 3}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"final_a": 1, "final_b": 1},
        },
        generic_input_slots_by_operation={"box_sink": 3},
        exact_required_pose_optional_counts={"protocol_storage_box": 1},
    )

    status = model.solve(time_limit_seconds=2.0)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    protocol_stats = model.build_stats["global_valid_inequalities"][
        "optional_cardinality_bounds"
    ]["protocol_storage_box"]
    assert protocol_stats["lower"] == 1
    assert protocol_stats["slot_pool_upper_bound"] == 0


def test_protocol_lower_bound_shortfall_keeps_residual_storage_pool() -> None:
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [
                    {"x": 0, "y": 0, "dir": "N"},
                    {"x": 0, "y": 0, "dir": "E"},
                    {"x": 0, "y": 0, "dir": "S"},
                ],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_1",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [
                    {"x": 1, "y": 0, "dir": "N"},
                    {"x": 1, "y": 0, "dir": "E"},
                    {"x": 1, "y": 0, "dir": "S"},
                ],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 3}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {
                "final_a": 1,
                "final_b": 1,
                "final_c": 1,
                "final_d": 1,
            },
        },
        generic_input_slots_by_operation={"box_sink": 3},
        exact_required_pose_optional_counts={"protocol_storage_box": 1},
    )

    status = model.solve(time_limit_seconds=2.0)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    protocol_stats = model.build_stats["global_valid_inequalities"][
        "optional_cardinality_bounds"
    ]["protocol_storage_box"]
    assert protocol_stats["lower"] == 2
    assert protocol_stats["slot_pool_upper_bound"] == 1
    assert model._residual_optional_powered_slot_upper_bounds()["protocol_storage_box"] == 1


def test_fixed_required_power_pole_slots_cover_powered_facilities() -> None:
    instances = [
        {
            "instance_id": "machine_1",
            "facility_type": "machine",
            "operation_type": "crafting",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "machine": [
            {
                "pose_id": "machine_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": [
            {
                "pose_id": f"pole_{x}",
                "anchor": {"x": x, "y": 0},
                "occupied_cells": [[x, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0]],
            }
            for x in range(2)
        ],
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 1,
            },
        },
    }
    model = MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
        exact_required_pose_optional_counts={"power_pole": 1},
    )

    status = model.solve(time_limit_seconds=2.0)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    delegate = model._coordinate_delegate
    assert delegate is not None
    assert "power_pole" not in delegate.required_optional_slots
    assert "power_pole" not in delegate.residual_optional_slots
    assert len(delegate._c1_pole_bools) == 2
    assert sum(model._solver.Value(var) for _, var, _ in delegate._c1_pole_bools) == 1
    assert model.build_stats["power_coverage"]["pole_slots"] == 2


def test_fixed_required_power_pole_without_powered_demand_keeps_geometry_semantics() -> None:
    pools = {
        "power_pole": [
            {
                "pose_id": f"pole_{x}",
                "anchor": {"x": x, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "none"},
                "occupied_cells": [[x, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0]],
            }
            for x in range(2)
        ],
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 1,
            },
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        exact_required_pose_optional_counts={"power_pole": 1},
    )

    status = model.solve(time_limit_seconds=2.0)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    delegate = model._coordinate_delegate
    assert delegate is not None
    assert "power_pole" not in delegate.required_optional_slots
    assert len(delegate._all_power_pole_slots()) == 0
    assert len(delegate._c1_pole_bools) == 2
    assert sum(model._solver.Value(var) for _, var, _ in delegate._c1_pole_bools) == 1

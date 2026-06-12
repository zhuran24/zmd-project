"""Regression tests for coordinate-exact protocol storage lower bounds."""

from __future__ import annotations

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def test_protocol_lower_bound_counts_fixed_required_storage_boxes() -> None:
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "omni"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
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
        wireless_sink_generic_input_slots=3,
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
                "pose_params": {"orientation": 0, "port_mode": "omni"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_1",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "omni"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
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
        wireless_sink_generic_input_slots=3,
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
                "pose_id": "pole_0",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0]],
            }
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
    assert len(model._coordinate_delegate.required_optional_slots["power_pole"]) == 1
    assert len(model._coordinate_delegate.residual_optional_slots.get("power_pole", [])) == 0
    assert model.build_stats["power_coverage"]["pole_slots"] == 1


def test_fixed_required_power_pole_without_powered_demand_keeps_geometry_semantics() -> None:
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "none"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0]],
            }
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
    assert len(model._coordinate_delegate.required_optional_slots["power_pole"]) == 1
    assert len(model._coordinate_delegate._all_power_pole_slots()) == 1

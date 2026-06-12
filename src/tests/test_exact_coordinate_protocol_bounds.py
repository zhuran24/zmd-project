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

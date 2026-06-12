"""Regression tests for solver/solution invalidation after master-side cuts."""

from __future__ import annotations

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def _two_pose_fixture():
    instances = [
        {
            "instance_id": "solid_1",
            "facility_type": "solid",
            "operation_type": "noop",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "solid": [
            {
                "pose_id": "solid_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "solid_1",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    return instances, pools, rules


def _make_model(*, solve_mode: str) -> MasterPlacementModel:
    instances, pools, rules = _two_pose_fixture()
    return MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode=solve_mode,
        skip_power_coverage=True,
    )


def test_exact_coordinate_benders_cut_invalidates_solver_before_extract() -> None:
    model = _make_model(solve_mode="certified_exact")
    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    solution = model.extract_solution()
    first_pose = int(solution["solid_1"]["pose_idx"])

    assert model.add_benders_cut({"solid_1": first_pose}) is True

    assert model.extract_solution() == {}
    assert model.extract_bound_state()["ub"] is None
    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    second_solution = model.extract_solution()
    assert int(second_solution["solid_1"]["pose_idx"]) != first_pose


def test_legacy_benders_cut_invalidates_solver_before_extract() -> None:
    model = _make_model(solve_mode="exploratory")
    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    solution = model.extract_solution()
    first_pose = int(solution["solid_1"]["pose_idx"])

    assert model.add_benders_cut({"solid_1": first_pose}) is True

    assert model.extract_solution() == {}
    assert model.extract_bound_state()["ub"] is None
    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    second_solution = model.extract_solution()
    assert int(second_solution["solid_1"]["pose_idx"]) != first_pose

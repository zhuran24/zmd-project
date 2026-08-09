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


def _make_pose_bool_model() -> MasterPlacementModel:
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
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    return MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        ghost_anchor_filter={(2, 0)},
        skip_power_coverage=True,
    )


def test_pose_bool_benders_cut_invalidates_solver_before_extract(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    model = _make_pose_bool_model()
    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert type(model._coordinate_delegate).__name__ == "PoseBoolExactMasterDelegate"
    solution = model.extract_solution()
    first_pose = int(solution["solid_1"]["pose_idx"])

    assert model.add_benders_cut({"solid_1": first_pose}) is True

    assert model._solver is None
    assert model._status is None
    assert model.extract_solution() == {}
    assert model.extract_bound_state()["ub"] is None
    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    second_solution = model.extract_solution()
    assert int(second_solution["solid_1"]["pose_idx"]) != first_pose


def test_pose_bool_exact_required_power_pole_is_enforced_against_ghost(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [],
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 1, "height": 1}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        ghost_anchor_filter={(0, 0)},
        skip_power_coverage=True,
        exact_required_pose_optional_counts={"power_pole": 1},
    )

    assert model.solve(time_limit_seconds=2.0) == cp_model.INFEASIBLE


def test_pose_bool_unfiltered_ghost_rect_blocks_required_pole_body(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [],
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 1, "height": 1}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
        exact_required_pose_optional_counts={"power_pole": 1},
    )

    assert model.solve(time_limit_seconds=2.0) == cp_model.INFEASIBLE


def test_pose_bool_unfiltered_ghost_rect_extracts_selected_ghost(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {},
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools={},
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )

    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    solution = model.extract_solution()
    ghost_pick = solution["ghost_pick"]
    assert ghost_pick["facility_type"] == "ghost_rect"
    assert (ghost_pick["anchor"]["x"], ghost_pick["anchor"]["y"]) in {(0, 0), (1, 0)}
    assert model.build_stats["ghost_rect"]["placements"] == 2


def test_pose_bool_protocol_storage_lower_bound_requires_candidate(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    rules = {
        "globals": {"grid": {"width": 1, "height": 1}},
        "facility_templates": {
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools={"protocol_storage_box": []},
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
        generic_io_requirements={"required_generic_inputs": {"item": 1}},
        generic_input_slots_by_operation={"box_sink": 1},
    )

    assert model.solve(time_limit_seconds=2.0) == cp_model.INFEASIBLE


def test_pose_bool_protocol_storage_lower_bound_selects_pose(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    pools = {
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [{"x": 0, "y": 0, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        ghost_anchor_filter={(1, 0)},
        skip_power_coverage=True,
        generic_io_requirements={"required_generic_inputs": {"item": 1}},
        generic_input_slots_by_operation={"box_sink": 1},
    )

    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    solution = model.extract_solution()
    assert "pose_optional::protocol_storage_box::box_0" in solution


def test_pose_bool_protocol_storage_lower_bound_counts_beyond_fixed_required(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    pools = {
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [{"x": 0, "y": 0, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_1",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [{"x": 1, "y": 0, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        ghost_anchor_filter={(2, 0)},
        skip_power_coverage=True,
        generic_io_requirements={"required_generic_inputs": {"item": 2}},
        generic_input_slots_by_operation={"box_sink": 1},
        exact_required_pose_optional_counts={"protocol_storage_box": 1},
    )

    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    selected_boxes = [
        key for key in model.extract_solution()
        if key.startswith("pose_optional::protocol_storage_box::")
    ]
    assert len(selected_boxes) == 2


def test_pose_bool_direct_no_ghost_build_still_enforces_body_packing(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    instances = [
        {
            "instance_id": "a_1",
            "facility_type": "a",
            "operation_type": "noop",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "b_1",
            "facility_type": "b",
            "operation_type": "noop",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "a": [
            {
                "pose_id": "a_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "b": [
            {
                "pose_id": "b_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 1, "height": 1}},
        "facility_templates": {
            "a": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "b": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    model = MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )

    assert model.solve(time_limit_seconds=2.0) == cp_model.INFEASIBLE


def test_pose_bool_exact_core_packaging_no_ghost_remains_intentional_noop(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    instances, pools, rules = _two_pose_fixture()

    core = MasterPlacementModel.build_exact_core(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        skip_power_coverage=True,
    )

    assert core.master_representation == "pose_bool_exact_v1"
    assert core.build_stats["pose_bool_master"]["no_op_reason"] == "ghost_rect_none_at_build_exact_core_stage"


def test_pose_bool_exact_core_overlay_rebuilds_instead_of_reusing_empty_proto(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    pools = {
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 1, "height": 1}},
        "facility_templates": {
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }

    core = MasterPlacementModel.build_exact_core(
        instances=[],
        facility_pools=pools,
        rules=rules,
        skip_power_coverage=True,
        exact_required_pose_optional_counts={"protocol_storage_box": 1},
    )
    assert core.master_representation == "pose_bool_exact_v1"
    assert len(core.proto.variables) == 0
    assert len(core.proto.constraints) == 0

    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    assert overlay.build_stats["exact_core_reuse"]["proto_reused"] is False
    assert overlay.build_stats["exact_core_reuse"]["reason"] == (
        "pose_bool_exact_core_proto_is_packaging_noop_direct_rebuild"
    )
    assert overlay.solve(time_limit_seconds=2.0) == cp_model.INFEASIBLE


def test_pose_bool_respects_skip_power_coverage_for_powered_mandatory(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    instances = [
        {
            "instance_id": "machine_1",
            "facility_type": "machine",
            "operation_type": "noop",
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
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    model = MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        ghost_anchor_filter={(1, 0)},
        skip_power_coverage=True,
    )

    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.extract_solution()["machine_1"]["pose_idx"] == 0


def test_coordinate_exact_skip_power_keeps_powered_candidate_without_coverer(monkeypatch) -> None:
    monkeypatch.delenv("EXACT_USE_POSE_BOOL_MASTER", raising=False)
    instances = [
        {
            "instance_id": "machine_1",
            "facility_type": "machine",
            "operation_type": "noop",
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
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    model = MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        ghost_anchor_filter={(1, 0)},
        skip_power_coverage=True,
    )

    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.extract_solution()["machine_1"]["pose_idx"] == 0

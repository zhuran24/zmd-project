"""Unit tests for the deterministic power-pole placement subproblem."""
from __future__ import annotations

import os
from unittest import mock

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel
from src.models.power_placement_subproblem import (
    PowerPlacementSubproblem,
    inject_power_poles_into_solution,
)


def _make_pools_with_one_pole_one_machine():
    return {
        "power_pole": [
            {
                "pose_id": "pole_only",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0]],
            }
        ],
        "manufacturing_3x3": [
            {
                "pose_id": "machine_A",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }


def test_power_subproblem_feasible_when_single_pole_covers_single_machine() -> None:
    pools = _make_pools_with_one_pole_one_machine()
    master_solution = {
        "machine_001": {
            "instance_id": "machine_001",
            "facility_type": "manufacturing_3x3",
            "operation_type": "anything",
            "pose_idx": 0,
        }
    }
    coverers = {"manufacturing_3x3": {0: [0]}}
    sub = PowerPlacementSubproblem(
        master_solution=master_solution,
        facility_pools=pools,
        powered_templates=["manufacturing_3x3"],
        power_coverers_by_template_pose=coverers,
    )
    sub.build()
    result = sub.solve(time_limit_seconds=5.0)
    assert result.status == "FEASIBLE"
    assert result.selected_pose_indices == (0,)
    assert result.stats["candidate_pole_count"] == 1


def test_power_subproblem_infeasible_when_pole_blocked_by_fixed_cells() -> None:
    pools = _make_pools_with_one_pole_one_machine()
    # The machine itself sits on the same cell the pole wants to occupy
    # (after we re-anchor): a contrived but valid blocker test. Use ghost
    # cells as the obstacle, that's clearer.
    master_solution = {
        "machine_001": {
            "instance_id": "machine_001",
            "facility_type": "manufacturing_3x3",
            "operation_type": "anything",
            "pose_idx": 0,
        }
    }
    coverers = {"manufacturing_3x3": {0: [0]}}
    sub = PowerPlacementSubproblem(
        master_solution=master_solution,
        facility_pools=pools,
        powered_templates=["manufacturing_3x3"],
        power_coverers_by_template_pose=coverers,
        ghost_cells=[(4, 0)],  # blocks pole_only's only cell
    )
    sub.build()
    result = sub.solve(time_limit_seconds=5.0)
    assert result.status == "INFEASIBLE"
    assert "machine_001" in result.uncovered_instance_ids
    assert result.stats["candidate_pole_count"] == 0


def test_power_subproblem_two_poles_cannot_overlap_same_cell() -> None:
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_at_4_0",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0]],
            },
            {
                "pose_id": "pole_at_4_0_dup",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0]],
            },
        ],
        "manufacturing_3x3": [
            {
                "pose_id": "machine_A",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_B",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "power_coverage_cells": None,
            },
        ],
    }
    master_solution = {
        "machine_001": {
            "instance_id": "machine_001",
            "facility_type": "manufacturing_3x3",
            "pose_idx": 0,
        },
        "machine_002": {
            "instance_id": "machine_002",
            "facility_type": "manufacturing_3x3",
            "pose_idx": 1,
        },
    }
    coverers = {"manufacturing_3x3": {0: [0], 1: [1]}}
    sub = PowerPlacementSubproblem(
        master_solution=master_solution,
        facility_pools=pools,
        powered_templates=["manufacturing_3x3"],
        power_coverers_by_template_pose=coverers,
    )
    sub.build()
    result = sub.solve(time_limit_seconds=5.0)
    # Both poles want the same cell (4,0). Cell non-overlap forces at most
    # one to be selected. But each machine has a unique covering pole. So
    # the model is INFEASIBLE.
    assert result.status == "INFEASIBLE"


def _build_one_powered_machine_one_pole_fixture():
    """Minimal fixture: 1 powered machine + 1 pole pose on a 3x1 grid."""
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_widget",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "powered_widget": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [
            {
                "pose_id": "pole_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0]],  # covers the widget cell
            },
        ],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "powered_widget": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return instances, pools, rules


def test_flag_off_baseline_master_still_carries_power_pole_slots() -> None:
    """With flag off (default), master must still build power_pole slots."""
    instances, pools, rules = _build_one_powered_machine_one_pole_fixture()
    with mock.patch.dict(os.environ, {"EXACT_POWER_PLACEMENT_SUBPROBLEM": ""}):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
    slot_counts = core.build_stats.get("master_slot_counts", {})
    assert slot_counts.get("residual_optionals", {}).get("power_pole", 0) >= 1
    assert core.build_stats.get("power_placement") is None


def test_flag_on_master_drops_power_pole_residual_slots() -> None:
    """With flag on, master should not carry power_pole residual slots."""
    instances, pools, rules = _build_one_powered_machine_one_pole_fixture()
    with mock.patch.dict(
        os.environ,
        {
            "EXACT_POWER_PLACEMENT_SUBPROBLEM": "1",
            "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST": "1",
        },
    ):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
    slot_counts = core.build_stats.get("master_slot_counts", {})
    assert "power_pole" not in slot_counts.get("residual_optionals", {})
    power_placement = core.build_stats.get("power_placement") or {}
    assert power_placement.get("representation") == "delegated_power_subproblem_v1"


def test_flag_on_end_to_end_master_solve_plus_power_subproblem_feasible() -> None:
    """Flag on: master solves powered_widget placement, subproblem picks pole."""
    instances, pools, rules = _build_one_powered_machine_one_pole_fixture()
    with mock.patch.dict(
        os.environ,
        {
            "EXACT_POWER_PLACEMENT_SUBPROBLEM": "1",
            "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST": "1",
        },
    ):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
        overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        status = overlay.solve(time_limit_seconds=5.0)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        solution = overlay.extract_solution()
        assert "powered_001" in solution
        n_pole = sum(
            1 for v in solution.values() if v.get("facility_type") == "power_pole"
        )
        assert n_pole == 0, f"master should not place power_pole, got {n_pole}"

        sub = PowerPlacementSubproblem(
            master_solution=solution,
            facility_pools=overlay.facility_pools,
            powered_templates=overlay._powered_templates,
            power_coverers_by_template_pose=overlay._power_coverers_by_template_pose,
        )
        sub.build()
        result = sub.solve(time_limit_seconds=5.0)
        assert result.status == "FEASIBLE"
        assert result.selected_pose_indices == (0,)

        injected = inject_power_poles_into_solution(
            solution,
            selected_pose_indices=result.selected_pose_indices,
            facility_pools=overlay.facility_pools,
        )
        n_pole_after = sum(
            1 for v in injected.values() if v.get("facility_type") == "power_pole"
        )
        assert n_pole_after == 1


def test_inject_power_poles_extends_solution_with_synthetic_entries() -> None:
    pools = _make_pools_with_one_pole_one_machine()
    base_solution = {
        "machine_001": {"facility_type": "manufacturing_3x3", "pose_idx": 0},
    }
    out = inject_power_poles_into_solution(
        base_solution, selected_pose_indices=[0], facility_pools=pools,
    )
    assert "machine_001" in out
    pole_keys = [k for k in out if k.startswith("pose_optional::power_pole::")]
    assert len(pole_keys) == 1
    entry = out[pole_keys[0]]
    assert entry["facility_type"] == "power_pole"
    assert entry["pose_idx"] == 0
    assert entry["bound_type"] == "exact_pose_optional"
    assert entry["is_mandatory"] is False

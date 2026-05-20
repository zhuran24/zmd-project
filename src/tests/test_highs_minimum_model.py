"""HiGHS minimum model PoC 测试 (Phase 1 重写).

验证 build_highs_minimum_model + solve 在简化 problem 上工作:
- mandatory facility group exactly-one pose
- ghost rect anchor exactly-one position
- cell occupancy ≤ 1 set-packing
"""

from __future__ import annotations

import pytest

from src.models.highs_master_model import (
    HighsMinimumModel,
    build_highs_minimum_model,
)


def _minimal_5x5_rules() -> dict:
    return {
        "globals": {"grid": {"width": 5, "height": 5}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }


def _miner_instance(instance_id: str) -> dict:
    return {
        "instance_id": instance_id,
        "facility_type": "miner",
        "operation_type": "mining",
        "is_mandatory": True,
        "bound_type": "exact",
    }


def _pose(x: int, y: int, pose_id: str | None = None) -> dict:
    return {
        "pose_id": pose_id or f"pose_{x}_{y}",
        "anchor": {"x": x, "y": y},
        "occupied_cells": [[x, y]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


def test_build_2_facility_1x1_ghost_2x2_feasible() -> None:
    instances = [_miner_instance("m1"), _miner_instance("m2")]
    pools = {
        "miner": [
            _pose(0, 0),
            _pose(4, 4),
            _pose(2, 2),
        ]
    }
    model = build_highs_minimum_model(
        instances,
        pools,
        _minimal_5x5_rules(),
        ghost_rect=(2, 2),
    )
    assert model.build_stats["mandatory_group_count"] == 2
    assert model.build_stats["z_var_count"] == 6  # 2 instances × 3 poses
    # 5x5 grid - 2x2 ghost = 4x4 anchors = 16
    assert model.build_stats["u_var_count"] == 16

    status, solution = model.solve(time_limit_seconds=10.0)
    assert status == "OPTIMAL"
    assert solution is not None
    assert len(solution["selected_poses"]) == 2
    ghost_xy = solution["ghost_anchor"]
    assert ghost_xy is not None
    gx, gy = ghost_xy
    ghost_cells = {(gx + dx, gy + dy) for dx in range(2) for dy in range(2)}
    facility_cells = set()
    for sp in solution["selected_poses"]:
        pose = pools["miner"][sp["pose_idx"]]
        facility_cells.update(tuple(c) for c in pose["occupied_cells"])
    assert ghost_cells.isdisjoint(facility_cells), \
        f"ghost {ghost_cells} overlaps facility {facility_cells}"


def test_no_ghost_rect_no_u_vars() -> None:
    instances = [_miner_instance("m1")]
    pools = {"miner": [_pose(0, 0), _pose(4, 4)]}
    model = build_highs_minimum_model(
        instances, pools, _minimal_5x5_rules(), ghost_rect=None
    )
    assert model.build_stats["u_var_count"] == 0
    status, solution = model.solve(time_limit_seconds=5.0)
    assert status == "OPTIMAL"
    assert solution["ghost_anchor"] is None


def test_ghost_too_large_for_grid_infeasible() -> None:
    instances = [_miner_instance("m1")]
    pools = {"miner": [_pose(0, 0)]}
    model = build_highs_minimum_model(
        instances, pools, _minimal_5x5_rules(), ghost_rect=(10, 10)
    )
    status, _ = model.solve(time_limit_seconds=5.0)
    assert status == "INFEASIBLE"


def test_conflicting_mandatory_packing_infeasible() -> None:
    # 5x5 grid, 2 mandatory miners, both can only sit at (2,2) — conflict
    instances = [_miner_instance("m1"), _miner_instance("m2")]
    pools = {"miner": [_pose(2, 2)]}
    model = build_highs_minimum_model(
        instances, pools, _minimal_5x5_rules(), ghost_rect=None
    )
    status, _ = model.solve(time_limit_seconds=5.0)
    assert status == "INFEASIBLE"

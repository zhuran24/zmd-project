"""SCIP minimum model tests — 镜像 test_highs_minimum_model."""

from __future__ import annotations

import importlib.util
from typing import Any

import pytest

_HAS_SCIP = importlib.util.find_spec("pyscipopt") is not None
pytestmark = pytest.mark.skipif(not _HAS_SCIP, reason="optional SCIP solver dependency")

if _HAS_SCIP:
    from src.models.scip_master_model import build_scip_minimum_model
else:
    def build_scip_minimum_model(*args: Any, **kwargs: Any) -> object:  # pragma: no cover
        raise RuntimeError("pyscipopt is not installed")


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
        "is_mandatory": True,
    }


def _pose(x: int, y: int) -> dict:
    return {
        "pose_id": f"p_{x}_{y}",
        "anchor": {"x": x, "y": y},
        "occupied_cells": [[x, y]],
    }


def test_scip_2_facility_2x2_ghost_feasible() -> None:
    instances = [_miner_instance("m1"), _miner_instance("m2")]
    pools = {"miner": [_pose(0, 0), _pose(4, 4), _pose(2, 2)]}
    model = build_scip_minimum_model(
        instances, pools, _minimal_5x5_rules(), ghost_rect=(2, 2)
    )
    assert model.build_stats["z_var_count"] == 6
    assert model.build_stats["u_var_count"] == 16
    status, sol = model.solve(time_limit_seconds=10.0)
    assert status == "OPTIMAL"
    assert sol is not None
    assert len(sol["selected_poses"]) == 2
    assert sol["ghost_anchor"] is not None


def test_scip_ghost_too_large_infeasible() -> None:
    instances = [_miner_instance("m1")]
    pools = {"miner": [_pose(0, 0)]}
    model = build_scip_minimum_model(
        instances, pools, _minimal_5x5_rules(), ghost_rect=(10, 10)
    )
    status, _ = model.solve(time_limit_seconds=5.0)
    assert status == "INFEASIBLE"


def test_scip_no_ghost_feasible() -> None:
    instances = [_miner_instance("m1")]
    pools = {"miner": [_pose(0, 0), _pose(4, 4)]}
    model = build_scip_minimum_model(
        instances, pools, _minimal_5x5_rules(), ghost_rect=None
    )
    assert model.build_stats["u_var_count"] == 0
    status, sol = model.solve(time_limit_seconds=5.0)
    assert status == "OPTIMAL"
    assert sol["ghost_anchor"] is None

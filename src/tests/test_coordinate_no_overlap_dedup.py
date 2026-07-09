"""Coordinate master no_overlap_2d dedup (M6 诊断修复 C).

历史形态：build()/克隆路径先放 core-only AddNoOverlap2D，ghost overlay 再放
core+ghost 组合版——组合版严格蕴含 core-only 版，后者是最重 propagator 的纯冗余
双份（M6 诊断 01_ablation_map 出土）。修复：overlay 加完组合版后清空被蕴含的
core-only 前身（_dedup_subsumed_core_no_overlap，找不到恰一个候选则保留冗余）。

本文件钉死四个面：
1. 带 ghost 的模型 proto 里只剩一个活 no_overlap_2d，telemetry 记 deduped=True。
2. core-vs-core 语义保住：两个 mandatory 抢同一格 → INFEASIBLE。
3. ghost-vs-core 语义保住：ghost 唯一锚与唯一 pose 同格 → INFEASIBLE。
4. 无 ghost 路径不受影响：core-only 约束仍在（恰一个）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def _live_no_overlap_count(master: MasterPlacementModel) -> int:
    delegate = getattr(master, "_coordinate_delegate", None)
    model = delegate.model if delegate is not None else master.model
    proto = model.Proto()
    return sum(
        1 for constraint in proto.constraints if constraint.has_no_overlap_2d()
    )


def _build_master(
    *,
    pose_xs: Sequence[int],
    n_miners: int = 2,
    ghost_rect: Optional[Tuple[int, int]] = (1, 1),
    ghost_anchor_filter: Optional[List[Tuple[int, int]]] = None,
) -> MasterPlacementModel:
    """n 个 mandatory miner / 指定 x 坐标的 1×1 pose 池 / 5×1 盘（仿 step_8 fixture）。"""
    instances = [
        {
            "instance_id": f"miner_{idx:03d}",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for idx in range(1, n_miners + 1)
    ]
    pools: Dict[str, Any] = {
        "miner": [
            {
                "pose_id": f"pose_x{x}_{i}",
                "anchor": {"x": x, "y": 0},
                "occupied_cells": [[x, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for i, x in enumerate(pose_xs)
        ]
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True
    )
    return MasterPlacementModel.from_exact_core(
        core, ghost_rect=ghost_rect, ghost_anchor_filter=ghost_anchor_filter
    )


def test_ghost_overlay_dedups_core_no_overlap() -> None:
    master = _build_master(pose_xs=[0, 2, 4])
    assert _live_no_overlap_count(master) == 1
    ghost_stats = master.build_stats["ghost_rect"]
    assert ghost_stats["core_no_overlap_deduped"] is True


def test_core_vs_core_semantics_survive_dedup() -> None:
    # 两种 mandatory 设施、唯一 pose 几何重叠于 (0,0) → 组合约束必须判死。
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "hub_001",
            "facility_type": "hub",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": "miner_p0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "hub": [
            {
                "pose_id": "hub_p0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "hub": {"dimensions": {"w": 2, "h": 1}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True
    )
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    assert _live_no_overlap_count(master) == 1
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_ghost_vs_core_semantics_survive_dedup() -> None:
    # 唯一 pose 在 (0,0)、ghost 唯一锚也在 (0,0) → 组合约束必须判死。
    master = _build_master(
        pose_xs=[0],
        n_miners=1,
        ghost_anchor_filter=[(0, 0)],
    )
    assert _live_no_overlap_count(master) == 1
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE
    # 对照：锚放 (4,0) 与 pose 无冲突 → 可解（证明判死来自重叠而非其他）。
    master_ok = _build_master(
        pose_xs=[0],
        n_miners=1,
        ghost_anchor_filter=[(4, 0)],
    )
    assert master_ok.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_no_ghost_path_keeps_core_no_overlap() -> None:
    master = _build_master(pose_xs=[0, 2, 4], ghost_rect=None)
    assert _live_no_overlap_count(master) == 1
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )

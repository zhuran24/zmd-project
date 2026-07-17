"""front-clear lift master 编码哨兵（doc 04 v2 §3/§5 阶梯1，任务 7）。

钉死的面（对应四席审查的击穿点与 R11-R14/R17）：
1. 双 NoOverlap 拓扑：lift ON 时恰两条活约束、成员集精确 = B∪F 与 B∪G、
   free 与 ghost 永不同处一条约束、dedup 拒清（R11/R12——三席同洞的
   ghost-overlay 泄漏 = 系统性超杀，本文件是它的结构哨兵）；
2. R11 行为哨兵：ghost 内的 front 必须仍可 free=1（可行）；被真体格堵死的
   front 必须判死（约束咬合），lift OFF 对照臂可行（判死来自 lift）；
3. env 严格值域（R17：垃圾值 fail-closed 抛错，不静默当 OFF）；
4. clone 携带 feature identity、不重读 env（R14）；
5. free flat id 单射 build 哨兵（审查 encoding F4）。

fixture 用真实 op（crusher_source，demand (1,1)）+ 未登记 op 的 blocker
（出范围，无 lift 约束）——12×12 小盘，秒级。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import pytest
from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel

_LIFT_ENV = "EXACT_MASTER_FRONT_CLEAR_LIFT"


@pytest.fixture(autouse=True)
def _pin_solver_env(monkeypatch: Any) -> None:
    for name in list(os.environ):
        if name.startswith("EXACT_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "1")


def _crusher_pose(anchor_x: int, anchor_y: int, tag: str) -> Dict[str, Any]:
    """3×3 crusher_source pose：输入 port 左缘朝 W、输出 port 右缘朝 E。"""
    cells = [
        [anchor_x + dx, anchor_y + dy] for dx in range(3) for dy in range(3)
    ]
    return {
        "pose_id": f"crusher_{tag}",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "occupied_cells": cells,
        # identity 语义（front 错位事故修复 2026-07-18）：stored 口坐标即
        # front/带子格=体外第 1 格（镜像冻结池真形态），不再是体缘格。
        "input_port_cells": [{"x": anchor_x - 1, "y": anchor_y + 1, "dir": "W"}],
        "output_port_cells": [
            {"x": anchor_x + 3, "y": anchor_y + 1, "dir": "E"}
        ],
        "power_coverage_cells": None,
    }


def _box_pose(anchor_x: int, anchor_y: int, tag: str) -> Dict[str, Any]:
    cells = [
        [anchor_x + dx, anchor_y + dy] for dx in range(3) for dy in range(3)
    ]
    return {
        "pose_id": f"box_{tag}",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "occupied_cells": cells,
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


_RULES = {
    "globals": {"grid": {"width": 12, "height": 12}},
    "facility_templates": {
        "crusher": {"dimensions": {"w": 3, "h": 3}, "needs_power": False},
        "box": {"dimensions": {"w": 3, "h": 3}, "needs_power": False},
    },
}


def _build_master(
    *,
    with_blocker_box: bool = False,
    ghost_rect: Optional[Tuple[int, int]] = None,
    ghost_anchor_filter: Optional[List[Tuple[int, int]]] = None,
) -> MasterPlacementModel:
    instances: List[Dict[str, Any]] = [
        {
            "instance_id": "crusher_001",
            "facility_type": "crusher",
            "operation_type": "crusher_source",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools: Dict[str, Any] = {"crusher": [_crusher_pose(3, 3, "a")]}
    if with_blocker_box:
        instances.append(
            {
                "instance_id": "box_001",
                "facility_type": "box",
                # 未登记 profile 的 op = lift 出范围（无约束、纯 blocker）
                "operation_type": "fixture_storage",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        )
        # box 体格 (0..2, 3..5) 覆盖 crusher 唯一输入 front (2,4)
        pools["box"] = [_box_pose(0, 3, "blk")]
    core = MasterPlacementModel.build_exact_core(
        instances, pools, _RULES, skip_power_coverage=True
    )
    return MasterPlacementModel.from_exact_core(
        core, ghost_rect=ghost_rect, ghost_anchor_filter=ghost_anchor_filter
    )


def _active_no_overlaps(master: MasterPlacementModel) -> List[Tuple[int, set]]:
    delegate = master._coordinate_delegate
    proto = delegate.model.Proto()
    result = []
    for idx, constraint in enumerate(proto.constraints):
        if constraint.has_no_overlap_2d():
            xs = set(int(v) for v in constraint.no_overlap_2d.x_intervals)
            if xs:
                result.append((idx, xs))
    return result


def _interval_sets(master: MasterPlacementModel) -> Tuple[set, set, set]:
    delegate = master._coordinate_delegate
    body = {int(iv.Index()) for iv in delegate._core_x_intervals}
    free = {a for a, _ in delegate._front_clear_interval_proto_indexes}
    ghost = {int(iv.Index()) for iv in delegate._ghost_x_intervals}
    return body, free, ghost


def test_lift_off_topology_unchanged() -> None:
    master = _build_master(ghost_rect=(1, 1))
    assert master.build_stats["ghost_rect"]["core_no_overlap_deduped"] is True
    assert len(_active_no_overlaps(master)) == 1
    assert "front_clear_lift" not in master.build_stats
    assert master._coordinate_delegate.front_clear_lift_enabled is False


def test_lift_on_dual_no_overlap_exact_membership(monkeypatch: Any) -> None:
    monkeypatch.setenv(_LIFT_ENV, "1")
    master = _build_master(ghost_rect=(1, 1))
    body, free, ghost = _interval_sets(master)
    assert len(free) == 144  # 12×12
    active = _active_no_overlaps(master)
    assert len(active) == 2
    memberships = {frozenset(xs) for _, xs in active}
    assert frozenset(body | free) in memberships
    assert frozenset(body | ghost) in memberships
    # free 与 ghost 永不同处一条约束（三席同洞的超杀路径）
    for _, xs in active:
        assert not (xs & free and xs & ghost)
    assert master.build_stats["ghost_rect"]["core_no_overlap_deduped"] is False
    core_idx = master._coordinate_delegate._core_no_overlap_constraint_index
    assert core_idx in {idx for idx, _ in active}
    stats = master.build_stats["front_clear_lift"]
    assert stats["enabled"] is True
    assert stats["slots_constrained"] == 1
    assert stats["demands_by_operation"] == {"crusher_source": [1, 1]}
    # interval 计数口径含 free（doc 04 v2 §7）
    assert master.build_stats["master_interval_count"] >= 2 * 144


def test_lift_on_ghost_interior_front_stays_free(monkeypatch: Any) -> None:
    """R11 击杀哨兵：ghost 压在唯一输入 front (2,4) 上，front 在 routing 语义
    下仍是真自由格——lift 编码必须允许 free=1，模型必须可行。若 free 泄进
    ghost overlay（错误拓扑）本测试变 INFEASIBLE。"""
    monkeypatch.setenv(_LIFT_ENV, "1")
    master = _build_master(ghost_rect=(1, 1), ghost_anchor_filter=[(2, 4)])
    assert master.solve(time_limit_seconds=10.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_lift_on_blocked_front_infeasible_and_off_control(
    monkeypatch: Any,
) -> None:
    """约束咬合哨兵：box 体格堵死唯一输入 front → lift ON 判死；
    lift OFF 对照可行（判死确实来自 lift 而非几何/其它约束）。"""
    monkeypatch.setenv(_LIFT_ENV, "1")
    master_on = _build_master(with_blocker_box=True)
    assert master_on.solve(time_limit_seconds=10.0) == cp_model.INFEASIBLE

    monkeypatch.delenv(_LIFT_ENV, raising=False)
    master_off = _build_master(with_blocker_box=True)
    assert master_off.solve(time_limit_seconds=10.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


@pytest.mark.parametrize("raw", ["0", "false", "off", ""])
def test_lift_env_off_spellings(monkeypatch: Any, raw: str) -> None:
    monkeypatch.setenv(_LIFT_ENV, raw)
    master = _build_master()
    assert master._coordinate_delegate.front_clear_lift_enabled is False


@pytest.mark.parametrize("raw", ["true", "on", "1"])
def test_lift_env_on_spellings(monkeypatch: Any, raw: str) -> None:
    monkeypatch.setenv(_LIFT_ENV, raw)
    master = _build_master()
    assert master._coordinate_delegate.front_clear_lift_enabled is True


@pytest.mark.parametrize("raw", ["2", "yes", "enabled", "garbage"])
def test_lift_env_garbage_fails_closed(monkeypatch: Any, raw: str) -> None:
    """R17：非法值抛错，绝不静默当 OFF（假 A/B 面）。"""
    monkeypatch.setenv(_LIFT_ENV, raw)
    with pytest.raises(RuntimeError, match="EXACT_MASTER_FRONT_CLEAR_LIFT"):
        _build_master()


def test_clone_carries_lift_identity_not_env(monkeypatch: Any) -> None:
    """R14：clone 的 lift identity 来自 core binding，不重读 ambient env。"""
    monkeypatch.setenv(_LIFT_ENV, "1")
    core_on = MasterPlacementModel.build_exact_core(
        [
            {
                "instance_id": "crusher_001",
                "facility_type": "crusher",
                "operation_type": "crusher_source",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        {"crusher": [_crusher_pose(3, 3, "a")]},
        _RULES,
        skip_power_coverage=True,
    )
    monkeypatch.delenv(_LIFT_ENV, raising=False)
    clone_on = MasterPlacementModel.from_exact_core(core_on, ghost_rect=(1, 1))
    delegate = clone_on._coordinate_delegate
    assert delegate.front_clear_lift_enabled is True
    assert len(delegate._front_clear_free_bools) == 144
    assert "front_clear_lift" in clone_on.build_stats
    active = _active_no_overlaps(clone_on)
    assert len(active) == 2
    assert clone_on.build_stats["ghost_rect"]["core_no_overlap_deduped"] is False

    core_off = MasterPlacementModel.build_exact_core(
        [
            {
                "instance_id": "crusher_001",
                "facility_type": "crusher",
                "operation_type": "crusher_source",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        {"crusher": [_crusher_pose(3, 3, "a")]},
        _RULES,
        skip_power_coverage=True,
    )
    monkeypatch.setenv(_LIFT_ENV, "1")
    clone_off = MasterPlacementModel.from_exact_core(core_off, ghost_rect=(1, 1))
    assert clone_off._coordinate_delegate.front_clear_lift_enabled is False
    assert len(_active_no_overlaps(clone_off)) == 1


def test_free_flat_ids_injective(monkeypatch: Any) -> None:
    monkeypatch.setenv(_LIFT_ENV, "1")
    master = _build_master()
    delegate = master._coordinate_delegate
    cells = list(delegate._front_clear_free_bools)
    assert len(cells) == len(set(cells)) == 144
    pairs = delegate._front_clear_interval_proto_indexes
    assert len({a for a, _ in pairs}) == 144
    assert len({b for _, b in pairs}) == 144

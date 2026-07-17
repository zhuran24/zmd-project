"""front 错位事故修复批 1 —— identity 语义 6 类回归矩阵。

权威：docs/research/front_offset_incident_20260718/00_incident_survey_and_fix_plan.md
owner 游戏实测定谳（2026-07-18）：贴脸死 / 隔 1 格通 / 1 格带合法 / 两相对
口共享中间格；stored 端口坐标即 front/带子格（体外第 1 格）；堵 = 任何设施
本体（含电线杆），带子不堵（belt-belt 由 routing cross 约束裁决）。

6 类：
  T1 单格带 + 相对口共享中格（旧机械必杀、新语义必通——假 INFEASIBLE 反例）
  T2 stored 格被体占 = front_blocked + 精确归因（假放行反例）
  T3 墙距 1 / 最外圈 stored 格合法（批 3 补域 2,064 pose 的机械可用性哨兵）
  T4 跨模块统一：binding 侧 port_front_status 与 routing 侧同判
  T5 第 2 格占不再是口堵理由（判定理由回归：front_blocked → 连通性归因）
  T6 相对口不折叠 duplicate key；同键双口 fail-closed
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from src.models.routing_binding_context import (
    build_routing_binding_context,
    port_front_status,
)
from src.models.routing_subproblem import (
    GRID_H,
    GRID_W,
    RoutingGrid,
    RoutingSubproblem,
    run_exact_routing_precheck,
)


@pytest.fixture(autouse=True)
def _pin_solver_env(monkeypatch: Any) -> None:
    for key in list(os.environ):
        if key.startswith("EXACT_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "1")
    monkeypatch.setenv("EXACT_ROUTING_CP_SAT_WORKERS", "1")


def _occupy_all_except(free_cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for x in range(GRID_W)
        for y in range(GRID_H)
        if (x, y) not in free_cells
    }


def _micro(
    free_cells: set[tuple[int, int]],
    port_specs: list[dict[str, Any]],
    owner_map: dict[tuple[int, int], str] | None = None,
) -> dict[str, Any]:
    grid = RoutingGrid(
        _occupy_all_except(free_cells),
        port_specs,
        occupied_owner_by_cell=owner_map or {},
    )
    sub = RoutingSubproblem(grid, ["c"])
    sub.build(time_limit=10.0)
    return {
        "domain": sub.build_stats.get("domain_analysis", {}).get("status"),
        "solve": sub.solve(time_limit=10.0),
        "stats": sub.build_stats,
    }


def test_t1_one_cell_belt_opposite_ports_share_middle_cell() -> None:
    """1 格带合法、两相对口共享中间格（owner 游戏实测）。

    旧机械（front=stored+delta）会把双方 front 推进对方体格judged
    front_blocked——本用例是错位语义的假 INFEASIBLE 直接反例。
    """
    src = {"instance_id": "SRC", "x": 5, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    snk = {"instance_id": "SNK", "x": 5, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
    result = _micro({(5, 5)}, [src, snk])
    assert result["domain"] == "feasible"
    assert result["solve"] in ("OPTIMAL", "FEASIBLE")


def test_t2_stored_cell_occupied_by_body_blocks_with_attribution() -> None:
    """stored/front 格被任何设施本体占 = 口堵 + 精确归因（假放行反例）。

    电线杆同类：pole 体格进 occupied（OQ2 owner 定谳「电线杆也算本体」），
    此处 BLOCKER 即代表任意 body（含 pole）。
    """
    src = {"instance_id": "SRC", "x": 5, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    snk = {"instance_id": "SNK", "x": 8, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
    result = _micro(
        {(6, 5), (7, 5), (8, 5)},
        [src, snk],
        owner_map={(5, 5): "BLOCKER"},
    )
    assert result["domain"] == "front_blocked"
    assert result["solve"] == "INFEASIBLE"
    precheck = run_exact_routing_precheck(
        RoutingGrid(
            _occupy_all_except({(6, 5), (7, 5), (8, 5)}),
            [src, snk],
            occupied_owner_by_cell={(5, 5): "BLOCKER"},
        ),
    )
    blocked = precheck["blocked_ports"]
    assert len(blocked) == 1
    entry = blocked[0]
    assert entry["front_cell"] == [5, 5]
    assert entry["port_cell"] == [5, 5]  # identity：双字段同值
    assert "BLOCKER" in entry["blocking_instance_ids"]


def test_t3_outermost_ring_stored_cell_is_legal() -> None:
    """最外圈格可承载带子（OQ8 owner 定谳）——批 3 补域 pose 的机械哨兵。

    口朝墙的 pose 在旧机械下 front=图外第 2 格 → 永久判死并在生成期被
    剪枝（缺角 2,064）；identity 语义下 stored 格在图内即合法。
    """
    src = {"instance_id": "SRC", "x": 0, "y": 5, "dir": "W", "type": "out", "commodity": "c"}
    snk = {"instance_id": "SNK", "x": 0, "y": 8, "dir": "E", "type": "in", "commodity": "c"}
    corridor = {(0, 5), (0, 6), (0, 7), (0, 8)}
    result = _micro(corridor, [src, snk])
    assert result["domain"] == "feasible"
    assert result["solve"] in ("OPTIMAL", "FEASIBLE")


def test_t4_binding_side_port_front_status_matches_routing() -> None:
    """跨模块统一：binding 侧 port_front_status 与 routing 判定同源同判。"""
    def _box_pose(ax: int, ay: int) -> dict[str, Any]:
        return {
            "pose_id": f"box_{ax}_{ay}",
            "anchor": {"x": ax, "y": ay},
            "pose_params": {"orientation": 0, "port_mode": "omni"},
            "occupied_cells": [[ax + dx, ay + dy] for dx in range(3) for dy in range(3)],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }

    pose = _box_pose(10, 10)
    context = build_routing_binding_context(
        {
            "pose_optional::protocol_storage_box::a": {
                "facility_type": "protocol_storage_box",
                "pose_idx": 0,
            }
        },
        {"protocol_storage_box": [pose]},
        grid_w=70,
        grid_h=70,
    )
    # stored 格落体格 → blocked + 归因（与 T2 routing 判定同向）
    status = port_front_status({"x": 10, "y": 10, "dir": "N", "commodity": "c"}, context)
    assert status.in_grid and not status.is_free
    assert status.blocker_instance_id == "pose_optional::protocol_storage_box::a"
    # stored 格在体旁空格 → free（identity：不再 +delta 推格）
    status_free = port_front_status({"x": 10, "y": 9, "dir": "N", "commodity": "c"}, context)
    assert status_free.in_grid and status_free.is_free
    # 墙距 1：最外圈 stored 格 in-grid（T3 的 binding 侧）
    status_wall = port_front_status({"x": 0, "y": 5, "dir": "W", "commodity": "c"}, context)
    assert status_wall.in_grid and status_wall.is_free
    # 图外 stored 格 fail-closed
    status_oob = port_front_status({"x": -1, "y": 5, "dir": "W", "commodity": "c"}, context)
    assert not status_oob.in_grid and not status_oob.is_free


def test_t5_second_cell_occupancy_is_not_a_front_block() -> None:
    """stored+delta（体外第 2 格）被占不再构成口堵——判定理由回归哨兵。

    源 stored (5,5) 空、(6,5)（旧机械的 front）被占：错位语义判
    front_blocked；identity 语义下两口 front 均可用，正确归因是源分量
    缺 counterpart 的连通性拒绝（relaxed_disconnected），绝不是口堵。
    """
    src = {"instance_id": "SRC", "x": 5, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    snk = {"instance_id": "SNK", "x": 8, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
    free = {(5, 5), (7, 5), (8, 5)}  # (6,5) 被占：走廊断开
    result = _micro(free, [src, snk], owner_map={(6, 5): "WALL"})
    assert result["domain"] == "relaxed_disconnected"
    assert result["domain"] != "front_blocked"
    assert result["solve"] == "INFEASIBLE"


def test_t6_opposite_ports_do_not_fold_duplicate_terminal_keys() -> None:
    """相对口共享中格键不折叠；同键双口 fail-closed（F-RT-R4-02 identity 版）。"""
    # 相对口：terminal_dir/type 均不同 → 不折叠，正常可行（T1 已证可行，
    # 此处断言 precheck 不把它归为 duplicate/blocked）
    src = {"instance_id": "SRC", "x": 5, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    snk = {"instance_id": "SNK", "x": 5, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
    ok = run_exact_routing_precheck(RoutingGrid(_occupy_all_except({(5, 5)}), [src, snk]))
    assert ok["status"] == "feasible"
    # 同 front、同 terminal_dir、同 commodity、同 type 的双口 = 真折叠，必须 fail-closed
    dup_a = {"instance_id": "A", "x": 5, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    dup_b = {"instance_id": "B", "x": 5, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    snk2 = {"instance_id": "SNK", "x": 8, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
    dup = run_exact_routing_precheck(
        RoutingGrid(
            _occupy_all_except({(5, 5), (6, 5), (7, 5), (8, 5)}),
            [dup_a, dup_b, snk2],
        ),
    )
    assert dup["status"] == "front_blocked"
    assert any(
        b.get("reason") == "duplicate_terminal_front_key" for b in dup["blocked_ports"]
    )

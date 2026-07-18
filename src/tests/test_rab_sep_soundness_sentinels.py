"""RAB-SEP soundness 哨兵 + 结构守卫回归（2026-07-16 ①′ 第二段）。

来源=docs/research/rab_sep_promotion_20260716/01_front_free_necessity_soundness_review.md
（v2，11 席对抗验证后）§7 工程义务清单。两组：

哨兵（钉现行 sound 行为，防未来重构静默破坏）：
  - front_blocked 的 live 守卫是 RoutingSubproblem.build() 的短路
    （analysis_status != feasible ⟹ model.Add(0==1) ⟹ return），
    _add_port_adherence 对该情形不可达（build_stats["port_adherence"] is None）。
    若有人"清理"掉 build 短路、指望 adherence 兜底，此哨兵先红。
  - relaxed_disconnected 的正确语义：同 commodity 多分量本身不非法——
    每分量各有 source+sink 即 FEASIBLE；缺 counterpart 的分量才触发拒绝。
  - 归因完备不变量：build_routing_binding_context 的 occupied 与
    occupied_owner_by_cell 同源填充，键集恒等；被他人占据的 front 必有归因。

结构守卫（2026-07-16 批新增的 fail-closed 面）：
  - ghost_pick 等非设施 marker 被 context 构建显式排除（不再依赖空池巧合）。
  - filter-empty 空域：归因不完备 ⟹ 不发 cert 且 thin fallback 被禁；
    blocker literal 解析失败 ⟹ 整证不发（CUT-R8-H1 constant-support）。
  - generic output/input 角色重叠 commodity 在 PortBindingModel 边界 fail-closed。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import src.models.binding_subproblem as binding_subproblem_module
from src.models.binding_subproblem import PortBindingModel, _strict_literal_pose_idx
from src.models.port_binding import routing_free_sink_commodities_from_generic_inputs
from src.models.routing_binding_context import (
    RoutingBindingContext,
    build_routing_binding_context,
    port_front_status,
)
from src.models.routing_subproblem import GRID_H, GRID_W, RoutingGrid, RoutingSubproblem
from src.search.benders_loop import _rab_empty_domain_thin_fallback_forbidden

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_GENERIC_INPUTS = {"valley_battery": 1, "qiaoyu_capsule": 1}


@pytest.fixture(autouse=True)
def _pin_solver_env(monkeypatch: Any) -> None:
    # 微型 routing 哨兵不得继承会话里飘着的 solver env（worker 数/参数注入），
    # 否则慢 lane/并发重载下有 TIMEOUT flake 风险（对抗复核 medium 项）
    for key in list(os.environ):
        if key.startswith("EXACT_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "1")
    monkeypatch.setenv("EXACT_ROUTING_CP_SAT_WORKERS", "1")


# ---------------------------------------------------------------------------
# 哨兵 1：front_blocked ⟹ build 短路（adherence 不可达）+ INFEASIBLE
# ---------------------------------------------------------------------------

def _occupy_all_except(free_cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for x in range(GRID_W)
        for y in range(GRID_H)
        if (x, y) not in free_cells
    }


def _run_micro_routing(
    free_cells: set[tuple[int, int]],
    port_specs: list[dict[str, Any]],
    owner_map: dict[tuple[int, int], str],
) -> dict[str, Any]:
    grid = RoutingGrid(
        _occupy_all_except(free_cells),
        port_specs,
        occupied_owner_by_cell=owner_map,
    )
    sub = RoutingSubproblem(grid, ["c"])
    sub.build(time_limit=10.0)
    return {
        "domain_status": sub.build_stats.get("domain_analysis", {}).get("status"),
        "port_adherence": sub.build_stats.get("port_adherence"),
        "solve": sub.solve(time_limit=10.0),
    }


# identity 语义（front 错位事故修复 2026-07-18）：port spec 的 stored 坐标
# 即 front/带子格自身——微型 fixture 的口直接写在走廊端点格上。
_SRC = {"instance_id": "SRC", "x": 6, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
_SNK = {"instance_id": "SNK", "x": 9, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
_CORRIDOR = {(6, 5), (7, 5), (8, 5), (9, 5)}


def test_front_blocked_short_circuits_build_before_port_adherence() -> None:
    control = _run_micro_routing(_CORRIDOR, [_SRC, _SNK], {})
    assert control["solve"] in ("OPTIMAL", "FEASIBLE")
    # feasible 路径 adherence 真跑了（哨兵的对照臂）
    assert control["port_adherence"] is not None

    blocked = _run_micro_routing(
        _CORRIDOR - {(9, 5)}, [_SRC, _SNK], {(9, 5): "BLOCKER"}
    )
    assert blocked["domain_status"] == "front_blocked"
    # live 守卫=build 短路：_add_port_adherence 不可达
    assert blocked["port_adherence"] is None
    assert blocked["solve"] == "INFEASIBLE"

    # identity 语义下 stored=(-1,5) 即 front 出界（旧 fixture 的 (0,5,W)+delta）
    oob_snk = {"instance_id": "SNK", "x": -1, "y": 5, "dir": "W", "type": "in", "commodity": "c"}
    oob_src = {"instance_id": "SRC", "x": 3, "y": 5, "dir": "E", "type": "out", "commodity": "c"}
    oob = _run_micro_routing({(0, 5), (1, 5), (2, 5), (3, 5)}, [oob_src, oob_snk], {})
    assert oob["domain_status"] == "front_blocked"
    assert oob["port_adherence"] is None
    assert oob["solve"] == "INFEASIBLE"


# ---------------------------------------------------------------------------
# 哨兵 2：relaxed_disconnected 语义 = 分量缺 counterpart，多分量本身合法
# ---------------------------------------------------------------------------

def test_multi_component_with_local_source_sink_pairs_is_feasible() -> None:
    corridor_a = {(6, 5), (7, 5), (8, 5), (9, 5)}
    corridor_b = {(6, 20), (7, 20), (8, 20), (9, 20)}
    src_b = {"instance_id": "SRC2", "x": 6, "y": 20, "dir": "E", "type": "out", "commodity": "c"}
    snk_b = {"instance_id": "SNK2", "x": 9, "y": 20, "dir": "W", "type": "in", "commodity": "c"}

    both_paired = _run_micro_routing(
        corridor_a | corridor_b, [_SRC, _SNK, src_b, snk_b], {}
    )
    # 同 commodity 落两个分量、每分量各有 source+sink ⟹ 合法可行
    #（备忘录 v2 推论 B 的正确语义；v1 的全称"多分量⟹无解"是被证伪的写法）
    assert both_paired["domain_status"] == "feasible"
    assert both_paired["solve"] in ("OPTIMAL", "FEASIBLE")

    split = _run_micro_routing(corridor_a | corridor_b, [_SRC, snk_b], {})
    # source 与 sink 分居两分量、各缺 counterpart ⟹ relaxed_disconnected 拒绝
    assert split["domain_status"] == "relaxed_disconnected"
    assert split["port_adherence"] is None
    assert split["solve"] == "INFEASIBLE"

    mixed = _run_micro_routing(corridor_a | corridor_b, [_SRC, _SNK, src_b], {})
    # 混合臂：A 分量 source+sink 齐、B 分量只有 source ⟹ 只要存在一个缺
    # counterpart 的分量即拒绝（防未来错改成"全部分量都缺才拒"）
    assert mixed["domain_status"] == "relaxed_disconnected"
    assert mixed["solve"] == "INFEASIBLE"


# ---------------------------------------------------------------------------
# 哨兵 3 + 守卫：归因完备不变量与 ghost_pick 排除
# ---------------------------------------------------------------------------

def _box_pose(anchor_x: int, anchor_y: int) -> dict[str, Any]:
    return {
        "pose_id": f"box_x{anchor_x:02d}_y{anchor_y:02d}",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "pose_params": {"orientation": 0, "port_mode": "TB"},
        "occupied_cells": [
            [anchor_x + dx, anchor_y + dy] for dx in range(3) for dy in range(3)
        ],
        "input_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y + 3, "dir": "N"}
            for dx in range(3)
        ],
        "output_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y - 1, "dir": "S"}
            for dx in range(3)
        ],
        "power_coverage_cells": None,
    }


def _box_solution_entry(pose: dict[str, Any], pose_idx: int) -> dict[str, Any]:
    return {
        "facility_type": "protocol_storage_box",
        "pose_idx": pose_idx,
        "pose_id": pose["pose_id"],
        "anchor": dict(pose["anchor"]),
        "orientation": 0,
        "port_mode": "TB",
        "bound_type": "exact_pose_optional",
        "solve_mode": "certified_exact",
    }


def test_context_attribution_completeness_and_blocker_identity() -> None:
    pose_a = _box_pose(10, 10)
    pose_b = _box_pose(20, 20)
    context = build_routing_binding_context(
        {
            "pose_optional::protocol_storage_box::a": _box_solution_entry(pose_a, 0),
            "pose_optional::protocol_storage_box::b": _box_solution_entry(pose_b, 1),
        },
        {"protocol_storage_box": [pose_a, pose_b]},
        grid_w=70,
        grid_h=70,
    )
    # 承重不变量：occupied 与 owner 归因同源，键集恒等 + 逐格归属精确
    expected_owner_by_cell = {
        (10 + dx, 10 + dy): "pose_optional::protocol_storage_box::a"
        for dx in range(3)
        for dy in range(3)
    }
    expected_owner_by_cell.update(
        {
            (20 + dx, 20 + dy): "pose_optional::protocol_storage_box::b"
            for dx in range(3)
            for dy in range(3)
        }
    )
    assert dict(context.occupied_owner_by_cell) == expected_owner_by_cell
    assert set(context.occupied_cells) == set(expected_owner_by_cell)
    # 被他人体格占据的 front 必有 blocker 归因（identity 语义：stored 格
    # 直接落在 A 的体格 (10,10) 上）
    status = port_front_status(
        {"x": 10, "y": 10, "dir": "N", "commodity": "c"},
        context,
        owner_instance_id="someone_else",
    )
    assert status.in_grid and not status.is_free
    assert status.blocker_instance_id == "pose_optional::protocol_storage_box::a"


def test_ghost_pick_marker_excluded_from_context_even_with_pool() -> None:
    ghost_pose = {
        "pose_id": "ghost_6x6",
        "anchor": {"x": 30, "y": 30},
        "occupied_cells": [[30 + dx, 30 + dy] for dx in range(6) for dy in range(6)],
    }
    pose_a = _box_pose(10, 10)
    context = build_routing_binding_context(
        {
            "pose_optional::protocol_storage_box::a": _box_solution_entry(pose_a, 0),
            "ghost_pick": {
                "facility_type": "ghost_rect",
                "pose_idx": 0,
                "pose_id": "ghost_6x6",
            },
        },
        {
            "protocol_storage_box": [pose_a],
            # 故意给 ghost_rect 一个非空池：排除必须靠 marker 判定这一结构保证，
            # 不再依赖"facility_pools 无 ghost_rect key ⟹ 空池 continue"的巧合
            "ghost_rect": [ghost_pose],
        },
        grid_w=70,
        grid_h=70,
    )
    ghost_cells = {(30 + dx, 30 + dy) for dx in range(6) for dy in range(6)}
    # 全部 ghost cell 必须被排除（不只抽查一格）
    assert not (ghost_cells & set(context.occupied_cells))
    assert not (ghost_cells & set(context.occupied_owner_by_cell))
    assert all(
        owner != "ghost_pick" for owner in context.occupied_owner_by_cell.values()
    )
    # 正向对照：合法 box 的九格仍完整在场（防"跳过所有 placement"式空 context 逃逸）
    box_cells = {(10 + dx, 10 + dy) for dx in range(3) for dy in range(3)}
    assert box_cells <= set(context.occupied_cells)
    assert all(
        context.occupied_owner_by_cell[cell] == "pose_optional::protocol_storage_box::a"
        for cell in box_cells
    )


# ---------------------------------------------------------------------------
# 守卫：filter-empty 空域的 cert / thin-fallback fail-closed 面
# ---------------------------------------------------------------------------

def _filling_capsule_pose(anchor_x: int = 10, anchor_y: int = 10) -> dict[str, Any]:
    return {
        "pose_id": f"filling_capsule_probe_x{anchor_x:02d}_y{anchor_y:02d}",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "pose_params": {"orientation": 0, "port_mode": "probe"},
        "occupied_cells": [
            [anchor_x + dx, anchor_y + dy] for dx in range(6) for dy in range(4)
        ],
        "input_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y + 4, "dir": "N"} for dx in range(6)
        ],
        "output_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y - 1, "dir": "S"} for dx in range(6)
        ],
        "power_coverage_cells": None,
    }


_OWNER_ID = "filling_capsule_001"
_BLOCKER_LEFT = "pose_optional::protocol_storage_box::blocks_input_fronts_left"
_BLOCKER_RIGHT = "pose_optional::protocol_storage_box::blocks_input_fronts_right"


def _empty_domain_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """owner=filling_capsule@(10,10)，输入 front 行 y=14 被两只 3x3 箱完全占据。

    filling_capsule 的输出 commodity（qiaoyu_capsule）也是 routed 商品；但堵死
    全部六个输入 front 已足以令每个 pattern 至少一个 routing-visible 端口被占，
    因而 filter 后域空、blockers={左箱,右箱}。
    """
    producer_pose = _filling_capsule_pose(10, 10)
    left_pose = _box_pose(10, 14)
    right_pose = _box_pose(13, 14)
    placement_solution = {
        _OWNER_ID: {
            "facility_type": "manufacturing_6x4",
            "pose_idx": 0,
            "pose_id": producer_pose["pose_id"],
            "anchor": dict(producer_pose["anchor"]),
            "orientation": 0,
            "port_mode": "probe",
            "bound_type": "exact_mandatory",
            "solve_mode": "certified_exact",
        },
        _BLOCKER_LEFT: _box_solution_entry(left_pose, 0),
        _BLOCKER_RIGHT: _box_solution_entry(right_pose, 1),
    }
    facility_pools = {
        "manufacturing_6x4": [producer_pose],
        "protocol_storage_box": [left_pose, right_pose],
    }
    return placement_solution, facility_pools


def _build_owner_model(
    placement_solution: dict[str, Any],
    facility_pools: dict[str, Any],
    routing_context: Any,
    *,
    required_generic_inputs: dict[str, int] | None = None,
) -> PortBindingModel:
    model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=[
            {
                "instance_id": _OWNER_ID,
                "facility_type": "manufacturing_6x4",
                "operation_type": "filling_capsule",
                "is_mandatory": True,
            }
        ],
        required_generic_outputs={},
        required_generic_inputs=(
            CANONICAL_GENERIC_INPUTS
            if required_generic_inputs is None
            else required_generic_inputs
        ),
        project_root=PROJECT_ROOT,
        routing_context=routing_context,
    )
    model.build()
    return model


def test_raw_empty_lift_scope_bucketing_helper() -> None:
    """front-clear lift 验收遥测（doc 04 v2 §4.3）：raw 空域按 liftable scope
    分桶——raw 事件口径与 accepted-cut counter 是两回事（审查 F-05 假绿面）。
    分桶是 benders 侧纯诊断 helper，**绝不进 conflict summary / proof 记录**
    （golden semantic digest 钉死 proof 面，slow lane 抓过一次污染）。
    filling_capsule 在 lift 范围内（demand 4/1）⟹ 空域进 scope 桶。"""
    from src.search.benders_loop import _front_clear_lift_scope_raw_empty_instances

    placement_solution, facility_pools = _empty_domain_fixture()
    context = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    model = _build_owner_model(placement_solution, facility_pools, context)

    empties = model.extract_empty_binding_domain_instances()
    assert len(empties) == 1
    rfsc = routing_free_sink_commodities_from_generic_inputs(
        model.required_generic_inputs
    )
    assert rfsc == frozenset()
    scoped = _front_clear_lift_scope_raw_empty_instances(
        empties, rfsc
    )
    assert scoped == [_OWNER_ID]
    # 出范围条目（未 profile op）不入桶
    assert (
        _front_clear_lift_scope_raw_empty_instances(
            [{"instance_id": "x", "operation_type": "fixture_storage"}],
            rfsc,
        )
        == []
    )
    # proof 面清洁哨兵：summary 不携带分桶诊断键
    summary = model.extract_conflict_summary()
    assert not any("lift_scope" in str(key) for key in summary)


def test_filter_empty_with_blockers_yields_full_cert_and_forbids_thin_fallback() -> None:
    placement_solution, facility_pools = _empty_domain_fixture()
    context = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    model = _build_owner_model(placement_solution, facility_pools, context)

    empties = model.extract_empty_binding_domain_instances()
    assert [entry["instance_id"] for entry in empties] == [_OWNER_ID]
    assert model.routing_aware_filter_stats["unattributed_rejection_owners"] == []
    assert model.routing_aware_blockers_by_owner[_OWNER_ID] == {
        _BLOCKER_LEFT,
        _BLOCKER_RIGHT,
    }

    certs = model.extract_routing_aware_certificates()
    assert len(certs) == 1
    cert = certs[0]
    assert cert["owner_instance_id"] == _OWNER_ID
    # conflict_set 逐 literal 精确断言（不只键集/计数——pose 值写错 = cut 绑到
    # 错误布局 = 超杀，对抗复核 high 项）：owner pose 0、左箱 pool idx 0、右箱 1
    assert cert["conflict_set"] == {_OWNER_ID: 0, _BLOCKER_LEFT: 0, _BLOCKER_RIGHT: 1}
    assert cert["owner_pose_idx"] == 0
    assert cert["blocker_instance_ids"] == sorted([_BLOCKER_LEFT, _BLOCKER_RIGHT])
    assert cert["core_size"] == 3

    # cert 在手时守卫与否无关；此断言钉的是「有 blocker ⟹ thin fallback 被禁」
    assert _rab_empty_domain_thin_fallback_forbidden(model, _OWNER_ID) is True


def test_unattributed_rejection_fail_closes_cert_and_thin_fallback() -> None:
    placement_solution, facility_pools = _empty_domain_fixture()
    healthy = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    # 人为破坏归因完备不变量：occupied 保留、owner 归因整体丢失
    #（builder 正常产的 context 不可能出现——codex 反例场景 ①）
    broken = RoutingBindingContext(
        grid_width=healthy.grid_width,
        grid_height=healthy.grid_height,
        occupied_cells=healthy.occupied_cells,
        component_by_cell=healthy.component_by_cell,
        cells_by_component=healthy.cells_by_component,
        occupied_owner_by_cell={},
    )
    model = _build_owner_model(placement_solution, facility_pools, broken)

    assert [e["instance_id"] for e in model.extract_empty_binding_domain_instances()] == [
        _OWNER_ID
    ]
    assert _OWNER_ID in model.routing_aware_unattributed_owners
    # 可审计 stats 字段也必须被正向填充（对抗复核 medium 项：只断"健康时为空"
    # 抓不到 append 被删）
    assert model.routing_aware_filter_stats["unattributed_rejection_owners"] == [_OWNER_ID]
    # blockers 恰为空——v1 的「blockers>=1 才禁」guard 在此不触发，
    # 必须由归因不完备记名独立触发 fail-closed
    assert model.routing_aware_blockers_by_owner.get(_OWNER_ID) is None
    assert model.extract_routing_aware_certificates() == []
    assert _rab_empty_domain_thin_fallback_forbidden(model, _OWNER_ID) is True


def test_mixed_attribution_fail_closes_cert_and_thin_fallback() -> None:
    placement_solution, facility_pools = _empty_domain_fixture()
    healthy = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    # 混合场景（对抗复核 high 项）：左箱归因保留、右箱归因丢失——
    # blockers 与 unattributed 同时非空，两个 fail-closed 条件必须各自独立触发
    partial_owner_by_cell = {
        cell: owner
        for cell, owner in healthy.occupied_owner_by_cell.items()
        if owner != _BLOCKER_RIGHT
    }
    broken = RoutingBindingContext(
        grid_width=healthy.grid_width,
        grid_height=healthy.grid_height,
        occupied_cells=healthy.occupied_cells,
        component_by_cell=healthy.component_by_cell,
        cells_by_component=healthy.cells_by_component,
        occupied_owner_by_cell=partial_owner_by_cell,
    )
    model = _build_owner_model(placement_solution, facility_pools, broken)

    assert [e["instance_id"] for e in model.extract_empty_binding_domain_instances()] == [
        _OWNER_ID
    ]
    assert model.routing_aware_blockers_by_owner[_OWNER_ID] == {_BLOCKER_LEFT}
    assert _OWNER_ID in model.routing_aware_unattributed_owners
    # 归因不完备 ⟹ 即便有部分 blocker 归因也整证不发
    assert model.extract_routing_aware_certificates() == []
    assert _rab_empty_domain_thin_fallback_forbidden(model, _OWNER_ID) is True


def test_partial_blocker_drop_fail_closes_whole_cert() -> None:
    placement_solution, facility_pools = _empty_domain_fixture()
    context = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    # codex 反例场景 ②（partial-drop）：blocker 在 context 里有占据、
    # 但在传给 binding 的 placement_solution 里丢了条目 ⟹ literal 解析失败
    reduced_solution = {
        key: value
        for key, value in placement_solution.items()
        if key != _BLOCKER_RIGHT
    }
    model = _build_owner_model(reduced_solution, facility_pools, context)

    assert [e["instance_id"] for e in model.extract_empty_binding_domain_instances()] == [
        _OWNER_ID
    ]
    assert _BLOCKER_RIGHT in model.routing_aware_blockers_by_owner[_OWNER_ID]
    # 旧行为=静默丢该 literal 仍发 core_size=2 的不完整 cert（超杀方向）；
    # 新行为=整证不发
    assert model.extract_routing_aware_certificates() == []
    assert _rab_empty_domain_thin_fallback_forbidden(model, _OWNER_ID) is True


@pytest.mark.parametrize(
    "raw_pose_idx",
    [None, "1", "bad", 1.0, 0.5, True, False, -1, -7],
)
def test_non_literal_pose_idx_fail_closes_whole_cert(raw_pose_idx: Any) -> None:
    # F-BL-R11-01「blocker literal 无法解析即整证不发」的字面口径
    #（对抗复核 soundness 席 medium 项：int() 宽松转换会把 '1'/True/0.5
    # 静默铸成 literal 或直接抛异常）；strict 解析对非字面 int 一律 -1
    assert _strict_literal_pose_idx(raw_pose_idx) == -1

    placement_solution, facility_pools = _empty_domain_fixture()
    context = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    corrupted_solution = {
        key: (dict(value, pose_idx=raw_pose_idx) if key == _BLOCKER_RIGHT else value)
        for key, value in placement_solution.items()
    }
    # 本反例只钉 cert literal 解析；清空 generic-input 需求，避免故意损坏的
    # box pose_idx 先在实体 sink 槽构造阶段被更早的严格位姿校验拒绝。
    model = _build_owner_model(
        corrupted_solution,
        facility_pools,
        context,
        required_generic_inputs={},
    )
    assert model.extract_routing_aware_certificates() == []
    assert _rab_empty_domain_thin_fallback_forbidden(model, _OWNER_ID) is True


def test_strict_literal_pose_idx_accepts_plain_non_negative_int() -> None:
    assert _strict_literal_pose_idx(0) == 0
    assert _strict_literal_pose_idx(7) == 7


class _NoBlockersSurface:
    routing_aware_unattributed_owners: set[str] = set()


class _NoUnattributedSurface:
    routing_aware_blockers_by_owner: dict[str, set[str]] = {}


class _NoneSurfaces:
    routing_aware_blockers_by_owner = None
    routing_aware_unattributed_owners = None


class _LegacyModel:
    pass


@pytest.mark.parametrize(
    "model_cls",
    [_LegacyModel, _NoBlockersSurface, _NoUnattributedSurface, _NoneSurfaces],
)
def test_thin_fallback_guard_fails_closed_on_missing_tracking_surface(
    model_cls: type,
) -> None:
    # 任一追踪面缺失/为 None ⟹ 判禁（对抗复核 high 项：不只测两面全缺，
    # 防 or 逻辑被弱化成"两者均缺才禁"）
    assert _rab_empty_domain_thin_fallback_forbidden(model_cls(), "x") is True


def test_pose_intrinsic_all_oob_empty_domain_keeps_thin_fallback_allowed() -> None:
    # 真·pose 内在空域（§4 row 3）：owner 贴上边界，全部输入 front 出界，
    # 零 blocker、零 unattributed ⟹ thin fallback 对该 owner 本人被允许
    #（对抗复核指出旧版只查了个无关 id，未构造真实全出界 owner）
    # identity 语义：input stored/front 行 = anchor_y+4；anchor 66 ⟹ 体格
    # y 66-69、stored y=70=OOB（旧 fixture anchor 65 的 stored 行 69 在图内）
    producer_pose = _filling_capsule_pose(10, 66)
    placement_solution = {
        _OWNER_ID: {
            "facility_type": "manufacturing_6x4",
            "pose_idx": 0,
            "pose_id": producer_pose["pose_id"],
            "anchor": dict(producer_pose["anchor"]),
            "orientation": 0,
            "port_mode": "probe",
            "bound_type": "exact_mandatory",
            "solve_mode": "certified_exact",
        },
    }
    facility_pools = {"manufacturing_6x4": [producer_pose]}
    context = build_routing_binding_context(
        placement_solution, facility_pools, grid_w=70, grid_h=70
    )
    model = _build_owner_model(placement_solution, facility_pools, context)

    assert [e["instance_id"] for e in model.extract_empty_binding_domain_instances()] == [
        _OWNER_ID
    ]
    assert model.routing_aware_blockers_by_owner.get(_OWNER_ID) is None
    assert _OWNER_ID not in model.routing_aware_unattributed_owners
    # 全出界 ⟹ cert 只有 owner 自身（core=1，controller 不走 cert 分支）
    certs = model.extract_routing_aware_certificates()
    assert len(certs) == 1 and certs[0]["core_size"] == 1
    assert certs[0]["conflict_set"] == {_OWNER_ID: 0}
    # pose 内在空域 ⟹ thin fallback 允许（对 owner 本人）
    assert _rab_empty_domain_thin_fallback_forbidden(model, _OWNER_ID) is False


# ---------------------------------------------------------------------------
# 守卫：generic output/input disjoint 不变量
# ---------------------------------------------------------------------------

def test_generic_output_input_overlap_fails_closed(monkeypatch: Any) -> None:
    # canonical role validator 在上游会先拒绝该形态；此处 no-op 掉它，
    # 单独钉 PortBindingModel 自身的消费者边界结构保证
    monkeypatch.setattr(
        binding_subproblem_module,
        "_validate_generic_io_requirement_roles",
        lambda *args, **kwargs: None,
    )
    pose = _box_pose(10, 10)

    def _construct(outputs: dict[str, int], inputs: dict[str, int]) -> PortBindingModel:
        return PortBindingModel(
            placement_solution={
                "pose_optional::protocol_storage_box::a": _box_solution_entry(pose, 0)
            },
            facility_pools={"protocol_storage_box": [pose]},
            instances=[],
            required_generic_outputs=outputs,
            required_generic_inputs=inputs,
            project_root=PROJECT_ROOT,
        )

    with pytest.raises(ValueError, match="角色重叠.*valley_battery"):
        _construct({"valley_battery": 1}, {"valley_battery": 1})

    # acceptance 对照（防断言口径过宽误杀）：不同 commodity 允许；
    # 同 key 但一侧计数为 0 允许（零需求键不参与判定）
    _construct({"valley_battery": 1}, {"qiaoyu_capsule": 1})
    _construct({"valley_battery": 0}, {"valley_battery": 1})

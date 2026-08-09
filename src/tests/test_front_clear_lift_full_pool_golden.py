"""front-clear lift 全池黄金对照（doc 04 v2 §5 阶梯2，任务 7；slow）。

真实冻结 candidate 池按 eligible mandatory operation group 全量逐 pose 双向核对：

1. master 派生的 offsets_by_mode 应用到 pose 原始锚点 == 测试侧直接把
   pose 原始端口绝对坐标解释为 front 集——**双向 equality**（审查 F4b：
   只验"被占不能为1"抓不到超杀方向）。测试侧仅接受字面 N/S/E/W，
   不调用任何生产 front helper 或方向偏移表；
2. padded 索引三断言：row、column 各自在界 + 标量 f 与独立重算相等
   （审查 F1-padding：不许只断言标量 f）；
3. demand 与 build_stats.demands_by_operation 一致。

session+master 真实构建 ~50s ⟹ slow lane（conftest 登记）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterator

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


@pytest.fixture(scope="module")
def _lift_master() -> Iterator[Any]:
    saved = {
        name: os.environ.pop(name)
        for name in list(os.environ)
        if name.startswith("EXACT_")
    }
    os.environ["EXACT_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_FRONT_CLEAR_LIFT"] = "1"
    try:
        from src.models.master_model import MasterPlacementModel
        from src.search.benders_loop import ExactSearchSession

        session = ExactSearchSession.create(
            PROJECT_ROOT, solve_mode="certified_exact"
        )
        master = MasterPlacementModel.from_exact_core(
            session.core, ghost_rect=(6, 6)
        )
        yield master
    finally:
        for name in list(os.environ):
            if name.startswith("EXACT_"):
                del os.environ[name]
        os.environ.update(saved)


def test_full_pool_offsets_bidirectional_golden(_lift_master: Any) -> None:
    from src.models.port_binding import (
        routing_visible_port_demands,
        supports_exact_pose_level_binding,
    )
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

    master = _lift_master
    delegate = master._coordinate_delegate
    stats = master.build_stats["front_clear_lift"]
    assert stats["enabled"] is True

    grid_w, grid_h = int(delegate.grid_w), int(delegate.grid_h)
    padded_w, padded_h = grid_w + 2, grid_h + 2
    rfsc = delegate._front_clear_routing_free_sink_commodities()
    assert rfsc == frozenset()

    poses_checked = 0
    expected_poses_checked = 0
    groups_checked = 0
    for group in delegate.owner._mandatory_groups:
        operation_type = str(group.get("operation_type", ""))
        if (
            not operation_type
            or operation_type not in OPERATION_PORT_PROFILES
            or not supports_exact_pose_level_binding(operation_type)
        ):
            continue
        req_in, vis_out = routing_visible_port_demands(operation_type, rfsc)
        if req_in <= 0 and vis_out <= 0:
            continue
        # demand 与 build stats 一致
        assert stats["demands_by_operation"][operation_type] == [
            int(req_in),
            int(vis_out),
        ]
        tpl = str(group["facility_type"])
        offsets_by_mode = delegate._front_clear_offsets_by_mode(group, tpl)
        pool = list(delegate.owner.facility_pools.get(tpl, []))
        tuple_by_idx = delegate._template_pose_tuple_by_idx[tpl]
        pose_indices = delegate._coordinate_master_pose_indices_for_group(group)
        assert set(pose_indices) == set(range(len(pool))), (
            f"{tpl} candidate domain was truncated: "
            f"actual={len(pose_indices)} expected={len(pool)}"
        )
        expected_poses_checked += len(pool)
        groups_checked += 1
        for pose_idx in pose_indices:
            pose = pool[int(pose_idx)]
            anchor = pose["anchor"]
            anchor_x, anchor_y = int(anchor["x"]), int(anchor["y"])
            # master 内部锚点映射必须与 pose 原始锚点一致
            pose_tuple = tuple_by_idx[int(pose_idx)]
            assert (int(pose_tuple[0]), int(pose_tuple[1])) == (
                anchor_x,
                anchor_y,
            ), f"{tpl}#{pose_idx} anchor mismatch"
            mode_id = int(pose_tuple[2])
            derived = offsets_by_mode[mode_id]
            for side_idx, field_name in (
                (0, "input_port_cells"),
                (1, "output_port_cells"),
            ):
                # 独立重算（identity 语义，front 错位事故修正 2026-07-18）：
                # stored 端口坐标即 front 绝对格，不再方向步进
                raw_fronts = set()
                for port in pose.get(field_name, []) or []:
                    assert str(port["dir"]) in {"N", "S", "E", "W"}
                    raw_fronts.add((int(port["x"]), int(port["y"])))
                derived_fronts = {
                    (anchor_x + odx, anchor_y + ody)
                    for odx, ody in derived[side_idx]
                }
                # 双向 equality（R5）
                assert derived_fronts == raw_fronts, (
                    f"{tpl}#{pose_idx} {field_name}: "
                    f"derived={sorted(derived_fronts)} raw={sorted(raw_fronts)}"
                )
                # padded 索引三断言（row / column / 标量 f）
                for odx, ody in derived[side_idx]:
                    px = anchor_x + 1 + odx
                    py = anchor_y + 1 + ody
                    assert 0 <= px <= padded_w - 1, f"{tpl}#{pose_idx} col 越界"
                    assert 0 <= py <= padded_h - 1, f"{tpl}#{pose_idx} row 越界"
                    f_formula = (
                        anchor_y * padded_w
                        + anchor_x
                        + ((1 + ody) * padded_w + (1 + odx))
                    )
                    fx, fy = anchor_x + odx, anchor_y + ody
                    f_raw = (fy + 1) * padded_w + (fx + 1)
                    assert f_formula == f_raw == py * padded_w + px
                    assert 0 <= f_formula <= padded_w * padded_h - 1
            poses_checked += 1

    assert groups_checked == stats["groups_covered"] == 17
    # 每个 eligible group 必须精确覆盖其完整模板池，防 silent truncation。
    assert poses_checked == expected_poses_checked
    assert poses_checked > 0
    print(f"[golden] groups={groups_checked} poses={poses_checked}")

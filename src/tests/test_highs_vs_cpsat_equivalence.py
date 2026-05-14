"""HiGHS vs OR-Tools cp_model 等价性测试 — Phase 3 重写 correctness verification.

同一 input (instances, pools, rules, ghost_rect) 给两个 build_*_minimum_model,
都 OPTIMAL 或都 INFEASIBLE → HiGHS 翻译没漏约束 / 没引语义偏差.

Solution-level 不要求字节级一致 (CP 跟 MIP 求解搜索顺序不同, witness 可能不同),
只要求**双方都给一组合法 layout** (set-packing + exactly-one 都满足).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.cpsat_minimum_model import build_cpsat_minimum_model
from src.models.highs_master_model import build_highs_minimum_model


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


def _verify_legal_layout(
    instances: Sequence[Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    ghost_rect: tuple[int, int] | None,
    solution: dict,
) -> None:
    """Solution 检查: exactly-one + set-packing 全满足."""
    selected = solution["selected_poses"]
    mandatory_groups = {
        str(i["instance_id"])
        for i in instances
        if bool(i.get("is_mandatory"))
    }
    selected_groups = {s["group_id"] for s in selected}
    assert mandatory_groups == selected_groups, \
        f"mandatory {mandatory_groups} != selected {selected_groups}"

    occupied: set[tuple[int, int]] = set()
    for sp in selected:
        pool = pools[next(
            i["facility_type"] for i in instances if i["instance_id"] == sp["group_id"]
        )]
        pose = pool[sp["pose_idx"]]
        cells = [tuple(c) for c in pose["occupied_cells"]]
        for cell in cells:
            assert cell not in occupied, f"cell {cell} 重叠"
            occupied.add(cell)

    if ghost_rect is not None and solution.get("ghost_anchor") is not None:
        gx, gy = solution["ghost_anchor"]
        gw, gh = ghost_rect
        ghost_cells = {(gx + dx, gy + dy) for dx in range(gw) for dy in range(gh)}
        overlap = ghost_cells & occupied
        assert not overlap, f"ghost {ghost_cells} 跟 facility 重叠 {overlap}"


def test_equivalence_2_facility_2x2_ghost() -> None:
    instances = [_miner_instance("m1"), _miner_instance("m2")]
    pools = {"miner": [_pose(0, 0), _pose(4, 4), _pose(2, 2)]}
    rules = _minimal_5x5_rules()
    ghost = (2, 2)

    h = build_highs_minimum_model(instances, pools, rules, ghost_rect=ghost)
    c = build_cpsat_minimum_model(instances, pools, rules, ghost_rect=ghost)
    assert h.build_stats["z_var_count"] == c.build_stats["z_var_count"]
    assert h.build_stats["u_var_count"] == c.build_stats["u_var_count"]

    h_status, h_sol = h.solve(time_limit_seconds=10.0)
    c_status, c_sol = c.solve(time_limit_seconds=10.0)
    assert h_status == c_status == "OPTIMAL"
    _verify_legal_layout(instances, pools, ghost, h_sol)
    _verify_legal_layout(instances, pools, ghost, c_sol)


def test_equivalence_infeasible_ghost_too_large() -> None:
    instances = [_miner_instance("m1")]
    pools = {"miner": [_pose(0, 0)]}
    rules = _minimal_5x5_rules()
    ghost = (10, 10)

    h = build_highs_minimum_model(instances, pools, rules, ghost_rect=ghost)
    c = build_cpsat_minimum_model(instances, pools, rules, ghost_rect=ghost)
    h_status, _ = h.solve(time_limit_seconds=5.0)
    c_status, _ = c.solve(time_limit_seconds=5.0)
    assert h_status == c_status == "INFEASIBLE"


def test_equivalence_infeasible_conflicting_mandatory() -> None:
    instances = [_miner_instance("m1"), _miner_instance("m2")]
    pools = {"miner": [_pose(2, 2)]}
    rules = _minimal_5x5_rules()

    h = build_highs_minimum_model(instances, pools, rules, ghost_rect=None)
    c = build_cpsat_minimum_model(instances, pools, rules, ghost_rect=None)
    h_status, _ = h.solve(time_limit_seconds=5.0)
    c_status, _ = c.solve(time_limit_seconds=5.0)
    assert h_status == c_status == "INFEASIBLE"


def test_equivalence_no_ghost_feasible() -> None:
    instances = [_miner_instance("m1"), _miner_instance("m2")]
    pools = {"miner": [_pose(0, 0), _pose(4, 4)]}
    rules = _minimal_5x5_rules()

    h = build_highs_minimum_model(instances, pools, rules, ghost_rect=None)
    c = build_cpsat_minimum_model(instances, pools, rules, ghost_rect=None)
    h_status, h_sol = h.solve(time_limit_seconds=5.0)
    c_status, c_sol = c.solve(time_limit_seconds=5.0)
    assert h_status == c_status == "OPTIMAL"
    _verify_legal_layout(instances, pools, None, h_sol)
    _verify_legal_layout(instances, pools, None, c_sol)

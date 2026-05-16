"""SCIP-backed master placement model — HiGHS 替代品 (Phase 4 重写 attempt).

[STATUS 2026-05-16: 实验 PoC, 未完成 + 验证为死路, 留作 reference]
- HiGHS Phase 3 撞 42 GB 之后, 尝试 SCIP 6.2 separator callback 懒加 power_coverage
- PoC 验证 separator fire 3 次 OK, 但完整 production 集成未做完
- 同时 [[project_rewrite_path_exhausted]] verdict: 任何 LP-MIP solver 在 dense
  power_coverage 上都给不出决定性收益, 不只是 HiGHS, SCIP 同样困境
- 生产路径仍 CP-SAT, SCIP 不再 active 开发
- 不删: SCIP separator callback 设计可能未来 problem 重 encode 时复用
- 当前 dead code, 没 env gate enable

历史背景:


为啥换 SCIP:
- HiGHS 1.14 lazy constraint API 只是占位符, C++ 没真 fire (实测确认)
- SCIP 6.2 完整支持 separator callback + Benders default cuts (PoC 验过 3 次 fire)
- SCIP 学术 / non-commercial 免费 (用户是个人 dev, 符合)

设计思路:
- 跟 highs_master_model 同结构 minimum: mandatory + ghost + cell_occupancy
- power_coverage 用 separator callback 懒加 (不 upfront build 4M rows)
- 期望: build RAM 小 (SCIP minimum model 跟 HiGHS 类似 ~5 GB), solve 阶段
  separator 按需加 violated power_coverage row, RAM 不爆

注意:
- SCIP 商业 license 需付费. 这个 module 是非商业 PoC, 个人项目用免费 OK.
- 集成 production 前需 user confirm license scope.

API:
  build_scip_minimum_model(instances, facility_pools, rules, ghost_rect=None)
    → ScipMinimumModel
  ScipMinimumModel.solve(time_limit_seconds=None) → status, solution
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pyscipopt as scip

from src.models.highs_power_coverage import build_pole_cell_index
from src.models.scip_power_separator import PowerCoverageSeparator


@dataclass
class ScipMinimumModel:
    """SCIP minimum model state + index 映射."""

    model: scip.Model
    z_var_by_group_pose: Dict[Tuple[str, int], Any] = field(default_factory=dict)
    u_var_by_anchor_idx: Dict[int, Any] = field(default_factory=dict)
    anchor_xy_by_idx: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    ghost_rect: Optional[Tuple[int, int]] = None
    grid_w: int = 0
    grid_h: int = 0
    build_stats: Dict[str, Any] = field(default_factory=dict)

    def solve(
        self,
        *,
        time_limit_seconds: Optional[float] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        if time_limit_seconds is not None:
            self.model.setParam("limits/time", float(time_limit_seconds))
        self.model.hideOutput()
        self.model.optimize()

        scip_status = self.model.getStatus()
        status_map = {
            "optimal": "OPTIMAL",
            "infeasible": "INFEASIBLE",
            "unbounded": "UNBOUNDED",
            "inforunbd": "INFEASIBLE",
            "timelimit": "UNKNOWN",
            "nodelimit": "UNKNOWN",
            "memorylimit": "UNKNOWN",
            "gaplimit": "UNKNOWN",
            "sollimit": "UNKNOWN",
            "userinterrupt": "UNKNOWN",
        }
        status = status_map.get(scip_status, f"UNKNOWN({scip_status})")
        if status != "OPTIMAL":
            return status, None

        selected_poses: List[Dict[str, Any]] = []
        for (group_id, pose_idx), var in self.z_var_by_group_pose.items():
            if self.model.getVal(var) > 0.5:
                selected_poses.append(
                    {"group_id": group_id, "pose_idx": int(pose_idx)}
                )
        ghost_xy: Optional[Tuple[int, int]] = None
        for anchor_idx, var in self.u_var_by_anchor_idx.items():
            if self.model.getVal(var) > 0.5:
                ghost_xy = self.anchor_xy_by_idx[anchor_idx]
                break
        return status, {
            "selected_poses": selected_poses,
            "ghost_anchor": ghost_xy,
            "objective": float(self.model.getObjVal()),
        }


def _pose_occupied_cells(pose: Mapping[str, Any]) -> List[Tuple[int, int]]:
    return [(int(cell[0]), int(cell[1])) for cell in pose.get("occupied_cells", [])]


def build_scip_minimum_model(
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    ghost_rect: Optional[Tuple[int, int]] = None,
    with_power_coverage_separator: bool = False,
) -> ScipMinimumModel:
    """Build SCIP minimum model — 镜像 build_highs_minimum_model.

    with_power_coverage_separator=True 时:
      - 加 power_pole z_var 进 model + 进 cell occupancy
      - register PowerCoverageSeparator (lazy cut, 不 upfront 加 4M rows)
      - 关 heuristics (separator-only solve path)
    """
    grid = dict(rules["globals"]["grid"])
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])

    model = scip.Model()
    model.hideOutput()
    if with_power_coverage_separator:
        # disable heuristics to force LP-based search; separator runs on each LP node
        model.setHeuristics(scip.SCIP_PARAMSETTING.OFF)

    z_var_by_group_pose: Dict[Tuple[str, int], Any] = {}
    u_var_by_anchor_idx: Dict[int, Any] = {}
    pole_var_by_pose_idx: Dict[int, Any] = {}
    anchor_xy_by_idx: Dict[int, Tuple[int, int]] = {}
    cell_occupancy: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    group_z_vars: Dict[str, List[Any]] = defaultdict(list)

    mandatory_groups: Dict[str, str] = {}
    for inst in instances:
        if not bool(inst.get("is_mandatory")):
            continue
        instance_id = str(inst["instance_id"])
        tpl = str(inst["facility_type"])
        mandatory_groups[instance_id] = tpl

    infeasible_marker_added = False

    for group_id, tpl in mandatory_groups.items():
        pool = list(facility_pools.get(tpl, []))
        if not pool:
            v = model.addVar(vtype="B", name=f"infeasible_marker_{group_id}")
            model.addCons(v == 1)
            model.addCons(v == 0)
            infeasible_marker_added = True
            continue
        for pose_idx, pose in enumerate(pool):
            v = model.addVar(vtype="B", name=f"z_{group_id}_{pose_idx}")
            z_var_by_group_pose[(group_id, pose_idx)] = v
            group_z_vars[group_id].append(v)
            for cell in _pose_occupied_cells(pose):
                cx, cy = cell
                if 0 <= cx < grid_w and 0 <= cy < grid_h:
                    cell_occupancy[(cx, cy)].append(v)

    if with_power_coverage_separator:
        pole_pool = list(facility_pools.get("power_pole", []))
        for pole_idx, pole_pose in enumerate(pole_pool):
            v = model.addVar(vtype="B", name=f"pole_{pole_idx}")
            pole_var_by_pose_idx[pole_idx] = v
            for cell in _pose_occupied_cells(pole_pose):
                cx, cy = cell
                if 0 <= cx < grid_w and 0 <= cy < grid_h:
                    cell_occupancy[(cx, cy)].append(v)

    anchor_u_vars: List[Any] = []
    if ghost_rect is not None:
        ghost_w, ghost_h = (int(ghost_rect[0]), int(ghost_rect[1]))
        if ghost_w > grid_w or ghost_h > grid_h:
            v = model.addVar(vtype="B", name="ghost_too_large")
            model.addCons(v == 1)
            model.addCons(v == 0)
            infeasible_marker_added = True
        else:
            anchor_idx = 0
            for ax in range(grid_w - ghost_w + 1):
                for ay in range(grid_h - ghost_h + 1):
                    v = model.addVar(vtype="B", name=f"u_{ax}_{ay}")
                    u_var_by_anchor_idx[anchor_idx] = v
                    anchor_xy_by_idx[anchor_idx] = (ax, ay)
                    anchor_u_vars.append(v)
                    for dx in range(ghost_w):
                        for dy in range(ghost_h):
                            cell_occupancy[(ax + dx, ay + dy)].append(v)
                    anchor_idx += 1

    for group_id, vars_ in group_z_vars.items():
        model.addCons(scip.quicksum(vars_) == 1)

    if anchor_u_vars:
        model.addCons(scip.quicksum(anchor_u_vars) == 1)

    cell_occupancy_constraint_count = 0
    for cell, vars_ in cell_occupancy.items():
        if len(vars_) < 2:
            continue
        model.addCons(scip.quicksum(vars_) <= 1)
        cell_occupancy_constraint_count += 1

    model.setObjective(0, "minimize")

    separator_attached = False
    if with_power_coverage_separator and pole_var_by_pose_idx:
        pole_pool = list(facility_pools.get("power_pole", []))
        pole_cell_index = build_pole_cell_index(pole_pool)
        sepa = PowerCoverageSeparator(
            z_var_by_group_pose=z_var_by_group_pose,
            pole_var_by_pose_idx=pole_var_by_pose_idx,
            facility_pools=facility_pools,
            mandatory_groups=mandatory_groups,
            pole_cell_index=pole_cell_index,
        )
        model.includeSepa(
            sepa,
            "power_coverage",
            "lazy power_coverage cut",
            priority=10**6,
            freq=1,
            maxbounddist=1.0,
            usessubscip=False,
            delay=False,
        )
        separator_attached = True

    return ScipMinimumModel(
        model=model,
        z_var_by_group_pose=z_var_by_group_pose,
        u_var_by_anchor_idx=u_var_by_anchor_idx,
        anchor_xy_by_idx=anchor_xy_by_idx,
        ghost_rect=ghost_rect,
        grid_w=grid_w,
        grid_h=grid_h,
        build_stats={
            "mandatory_group_count": len(mandatory_groups),
            "z_var_count": len(z_var_by_group_pose),
            "u_var_count": len(u_var_by_anchor_idx),
            "pole_var_count": len(pole_var_by_pose_idx),
            "cell_occupancy_constraint_count": cell_occupancy_constraint_count,
            "with_power_coverage_separator": with_power_coverage_separator,
            "separator_attached": separator_attached,
            "ghost_rect": ghost_rect,
            "grid": {"width": grid_w, "height": grid_h},
            "infeasible_marker_added": infeasible_marker_added,
        },
    )

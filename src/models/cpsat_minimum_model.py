"""OR-Tools cp_model 镜像版 minimum model — 跟 highs_master_model.py 同结构.

目的: Phase 3 重写 correctness verification. 同一 input (instances/pools/rules
/ghost_rect) 给 OR-Tools + HiGHS, 都 OPTIMAL 或都 INFEASIBLE, 都给 legal layout
→ HiGHS translation 没漏约束 / 没引语义偏差.

跟 src/models/master_model.py MasterPlacementModel **不同**:
- master_model 是 production 全套 (signature buckets, coordinate delegate,
  power_coverage, symmetry breaking, signature instrumentation 等), 11600 行
- 这个文件是 **minimum mirror**, 只跟 highs_master_model.py 一样:
  mandatory group exactly-one + ghost anchor exactly-one + cell occupancy set-packing
- 用于 1:1 翻译验证, 不是 production 替代品

API:
  build_cpsat_minimum_model(instances, facility_pools, rules, ghost_rect=None)
    → CpSatMinimumModel
  CpSatMinimumModel.solve(time_limit_seconds=None) → status, solution
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ortools.sat.python import cp_model


CpVar = Any  # cp_model.IntVar


@dataclass
class CpSatMinimumModel:
    model: cp_model.CpModel
    z_var_by_group_pose: Dict[Tuple[str, int], CpVar] = field(default_factory=dict)
    u_var_by_anchor_idx: Dict[int, CpVar] = field(default_factory=dict)
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
        solver = cp_model.CpSolver()
        if time_limit_seconds is not None:
            solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        status = solver.Solve(self.model)
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "OPTIMAL",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.UNKNOWN: "UNKNOWN",
            cp_model.MODEL_INVALID: "INFEASIBLE",
        }
        status_str = status_map.get(status, f"UNKNOWN({status})")
        if status_str != "OPTIMAL":
            return status_str, None

        selected_poses: List[Dict[str, Any]] = []
        for (group_id, pose_idx), var in self.z_var_by_group_pose.items():
            if solver.Value(var) > 0:
                selected_poses.append(
                    {"group_id": group_id, "pose_idx": int(pose_idx)}
                )
        ghost_xy: Optional[Tuple[int, int]] = None
        for anchor_idx, var in self.u_var_by_anchor_idx.items():
            if solver.Value(var) > 0:
                ghost_xy = self.anchor_xy_by_idx[anchor_idx]
                break
        return status_str, {
            "selected_poses": selected_poses,
            "ghost_anchor": ghost_xy,
        }


def _pose_occupied_cells(pose: Mapping[str, Any]) -> List[Tuple[int, int]]:
    return [(int(cell[0]), int(cell[1])) for cell in pose.get("occupied_cells", [])]


def build_cpsat_minimum_model(
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    ghost_rect: Optional[Tuple[int, int]] = None,
) -> CpSatMinimumModel:
    """Build cp_model.CpModel from project rules — 镜像 highs_master_model.py."""
    grid = dict(rules["globals"]["grid"])
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])

    model = cp_model.CpModel()
    z_var_by_group_pose: Dict[Tuple[str, int], CpVar] = {}
    u_var_by_anchor_idx: Dict[int, CpVar] = {}
    anchor_xy_by_idx: Dict[int, Tuple[int, int]] = {}
    cell_occupancy: Dict[Tuple[int, int], List[CpVar]] = defaultdict(list)

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
            model.Add(0 == 1)
            infeasible_marker_added = True
            continue
        group_z_vars: List[CpVar] = []
        for pose_idx, pose in enumerate(pool):
            v = model.NewBoolVar(f"z_{group_id}_{pose_idx}")
            z_var_by_group_pose[(group_id, pose_idx)] = v
            group_z_vars.append(v)
            for cell in _pose_occupied_cells(pose):
                cx, cy = cell
                if 0 <= cx < grid_w and 0 <= cy < grid_h:
                    cell_occupancy[(cx, cy)].append(v)
        if group_z_vars:
            model.AddExactlyOne(group_z_vars)

    if ghost_rect is not None:
        ghost_w, ghost_h = (int(ghost_rect[0]), int(ghost_rect[1]))
        if ghost_w > grid_w or ghost_h > grid_h:
            model.Add(0 == 1)
            infeasible_marker_added = True
        else:
            anchor_u_vars: List[CpVar] = []
            anchor_idx = 0
            for ax in range(grid_w - ghost_w + 1):
                for ay in range(grid_h - ghost_h + 1):
                    v = model.NewBoolVar(f"u_{ax}_{ay}")
                    u_var_by_anchor_idx[anchor_idx] = v
                    anchor_xy_by_idx[anchor_idx] = (ax, ay)
                    anchor_u_vars.append(v)
                    for dx in range(ghost_w):
                        for dy in range(ghost_h):
                            cell_occupancy[(ax + dx, ay + dy)].append(v)
                    anchor_idx += 1
            if anchor_u_vars:
                model.AddExactlyOne(anchor_u_vars)

    for cell, vars_ in cell_occupancy.items():
        if len(vars_) >= 2:
            model.Add(sum(vars_) <= 1)

    return CpSatMinimumModel(
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
            "cell_occupancy_constraint_count": sum(
                1 for vars_ in cell_occupancy.values() if len(vars_) >= 2
            ),
            "ghost_rect": ghost_rect,
            "grid": {"width": grid_w, "height": grid_h},
            "infeasible_marker_added": infeasible_marker_added,
        },
    )

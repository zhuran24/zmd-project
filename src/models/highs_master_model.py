"""HiGHS-backed minimal master placement model (Phase 1 重写 PoC).

目的: 验证 HiGHS MIP solver 在 Endfield 70x70 packing 问题上的 RAM/wall-time vs
OR-Tools CP-SAT. 不集成现有 ExactSearchSession / Benders / outer_search, 独立 PoC.

Phase 1 不带的:
  - power coverage (mandatory facility 必须被 pole 覆盖)
  - port clearance / signature buckets / coordinate delegate
  - 优化 hint / decision strategy
  - cuts replay / hint persistence

Phase 1 带的:
  - mandatory facility group placement (AddExactlyOne over poses)
  - ghost rectangle anchor (AddExactlyOne over anchors)
  - cell occupancy set-packing (每个 cell ≤ 1 物体占据)

API:
  build_highs_minimum_model(instances, facility_pools, rules, ghost_rect=None)
    → HighsMinimumModel (持有 Highs 对象 + 变量 index 映射)
  HighsMinimumModel.solve(time_limit_seconds=None) → status, solution
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import highspy


HighsVar = Any  # highspy.highs.highs_var (high-level wrapper, supports arithmetic)


@dataclass
class HighsMinimumModel:
    """HiGHS minimum-build model state + index 映射, 用于 PoC 量 RAM."""

    highs: highspy.Highs
    z_var_by_group_pose: Dict[Tuple[str, int], HighsVar] = field(default_factory=dict)
    u_var_by_anchor_idx: Dict[int, HighsVar] = field(default_factory=dict)
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
        """Solve the built MIP. Returns (status_str, solution_or_None)."""
        if time_limit_seconds is not None:
            self.highs.setOptionValue("time_limit", float(time_limit_seconds))
        # silence presolve / solver log
        self.highs.setOptionValue("output_flag", False)
        self.highs.run()
        model_status = self.highs.getModelStatus()
        sol = self.highs.getSolution()

        status_map = {
            highspy.HighsModelStatus.kOptimal: "OPTIMAL",
            highspy.HighsModelStatus.kInfeasible: "INFEASIBLE",
            highspy.HighsModelStatus.kUnbounded: "UNBOUNDED",
            highspy.HighsModelStatus.kTimeLimit: "UNKNOWN",
            highspy.HighsModelStatus.kIterationLimit: "UNKNOWN",
            highspy.HighsModelStatus.kSolutionLimit: "UNKNOWN",
            highspy.HighsModelStatus.kInterrupt: "UNKNOWN",
        }
        status = status_map.get(model_status, f"UNKNOWN({model_status})")

        if status != "OPTIMAL":
            return status, None

        selected_poses: List[Dict[str, Any]] = []
        for (group_id, pose_idx), var in self.z_var_by_group_pose.items():
            if sol.col_value[var.index] > 0.5:
                selected_poses.append(
                    {"group_id": group_id, "pose_idx": int(pose_idx)}
                )
        ghost_xy: Optional[Tuple[int, int]] = None
        for anchor_idx, var in self.u_var_by_anchor_idx.items():
            if sol.col_value[var.index] > 0.5:
                ghost_xy = self.anchor_xy_by_idx[anchor_idx]
                break
        return status, {
            "selected_poses": selected_poses,
            "ghost_anchor": ghost_xy,
            "objective": float(self.highs.getObjectiveValue()),
        }


def _pose_occupied_cells(pose: Mapping[str, Any]) -> List[Tuple[int, int]]:
    return [(int(cell[0]), int(cell[1])) for cell in pose.get("occupied_cells", [])]


def build_highs_minimum_model(
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    ghost_rect: Optional[Tuple[int, int]] = None,
) -> HighsMinimumModel:
    """Build HiGHS MIP from project rules + mandatory instances + ghost rect.

    变量:
      z[(group_id, pose_idx)] ∈ {0, 1}: 1 = facility group 选这个 pose
      u[anchor_idx] ∈ {0, 1}: 1 = ghost anchor 在这个 (x, y)

    约束:
      ∀ group g:  Σ_p z[(g, p)] = 1
      Σ_a u[a] = 1 (如果 ghost_rect 给定)
      ∀ cell c:  Σ_{(g,p) cover c} z[(g, p)] + Σ_{a cover c} u[a] ≤ 1

    目标: minimize 0 (feasibility-only, PoC stage).
    """
    grid = dict(rules["globals"]["grid"])
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])

    h = highspy.Highs()
    h.silent()

    z_var_by_group_pose: Dict[Tuple[str, int], HighsVar] = {}
    u_var_by_anchor_idx: Dict[int, HighsVar] = {}
    anchor_xy_by_idx: Dict[int, Tuple[int, int]] = {}
    cell_occupancy: Dict[Tuple[int, int], List[HighsVar]] = defaultdict(list)

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
            # mandatory group 没 pose → 立即 infeasible
            v = h.addBinary()
            h.addConstr(v == 1)
            h.addConstr(v == 0)
            infeasible_marker_added = True
            continue
        group_z_vars: List[HighsVar] = []
        for pose_idx, pose in enumerate(pool):
            v = h.addBinary()
            z_var_by_group_pose[(group_id, pose_idx)] = v
            group_z_vars.append(v)
            for cell in _pose_occupied_cells(pose):
                cx, cy = cell
                if 0 <= cx < grid_w and 0 <= cy < grid_h:
                    cell_occupancy[(cx, cy)].append(v)
        if group_z_vars:
            h.addConstr(sum(group_z_vars) == 1)

    if ghost_rect is not None:
        ghost_w, ghost_h = (int(ghost_rect[0]), int(ghost_rect[1]))
        if ghost_w > grid_w or ghost_h > grid_h:
            # ghost 比 grid 大 → 立即 infeasible
            v = h.addBinary()
            h.addConstr(v == 1)
            h.addConstr(v == 0)
            infeasible_marker_added = True
        else:
            anchor_u_vars: List[HighsVar] = []
            anchor_idx = 0
            for ax in range(grid_w - ghost_w + 1):
                for ay in range(grid_h - ghost_h + 1):
                    v = h.addBinary()
                    u_var_by_anchor_idx[anchor_idx] = v
                    anchor_xy_by_idx[anchor_idx] = (ax, ay)
                    anchor_u_vars.append(v)
                    for dx in range(ghost_w):
                        for dy in range(ghost_h):
                            cell_occupancy[(ax + dx, ay + dy)].append(v)
                    anchor_idx += 1
            if anchor_u_vars:
                h.addConstr(sum(anchor_u_vars) == 1)

    for cell, vars_ in cell_occupancy.items():
        if len(vars_) >= 2:
            h.addConstr(sum(vars_) <= 1)

    h.changeObjectiveSense(highspy.ObjSense.kMinimize)

    model = HighsMinimumModel(
        highs=h,
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
                1 for cols in cell_occupancy.values() if len(cols) >= 2
            ),
            "ghost_rect": ghost_rect,
            "grid": {"width": grid_w, "height": grid_h},
            "infeasible_marker_added": infeasible_marker_added,
        },
    )
    return model

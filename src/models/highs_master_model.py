"""HiGHS-backed master placement model (Phase 1 PoC → Phase 3 production-grade).

[STATUS 2026-05-16: 实验 PoC, 验证为死路, 留作 reference]
- Phase 1 (minimum, 无 power): RSS 39 → 8 GB, -79%, 看似赢
- Phase 3 (加 power_coverage): 42 GB > OR-Tools CP-SAT 30 GB, 真败
- 结论: LP-MIP solver 对 dense power_coverage linear constraint 不适合
- 生产路径仍走 CP-SAT (src/models/master_model.py + exact_coordinate_master.py)
- 详见 docs/lever_verdicts.md L2, memory [[project_highs_rewrite_blocker]]
- 不删: PROJECT_LOCK 没禁, 这段代码记录了 LP-MIP 真实失败原因; 未来如果换 solver
  或 problem encoding 变 (比如 dense → sparse 重写), 可能 re-enable
- 当前 dead code, env `EXACT_USE_HIGHS_MASTER` 默认 0

目的 (历史): 验证 HiGHS MIP solver 在 Endfield 70x70 packing 问题上的 RAM/wall-time vs
OR-Tools CP-SAT. 独立 PoC + 渐进加 production-grade 约束.

Phase 1 minimum 带的:
  - mandatory facility group placement (AddExactlyOne over poses)
  - ghost rectangle anchor (AddExactlyOne over anchors)
  - cell occupancy set-packing (每个 cell ≤ 1 物体占据)

Phase 3 production add (include_power_coverage=True):
  - power_pole optional z_var 加入 cell occupancy
  - mandatory facility pose 必须被 pole cover (sum(pole_z) - z[g,p] >= 0)
  - 无 coverer 的 facility pose 强制 z == 0

Phase 3 还没带的 (后续):
  - port clearance / signature buckets / coordinate delegate
  - 优化 hint / decision strategy
  - cuts replay / hint persistence

性能: 用 `passModel(HighsLp)` 批量 CSR row-wise, 跳过 Python expression 构造
overhead (实测 70x70 + 266 mandatory build 9.9 秒, RSS 4.8 GB).

API:
  build_highs_minimum_model(instances, facility_pools, rules, ghost_rect=None,
                            include_power_coverage=False)
    → HighsMinimumModel
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import highspy

from src.models.highs_power_coverage import (
    build_pole_cell_index,
    emit_power_coverage_rows,
)


HighsCol = int  # column index in HighsLp


@dataclass
class HighsMinimumModel:
    """HiGHS minimum-build model state + index 映射, 用于 PoC 量 RAM."""

    highs: highspy.Highs
    z_col_by_group_pose: Dict[Tuple[str, int], HighsCol] = field(default_factory=dict)
    u_col_by_anchor_idx: Dict[int, HighsCol] = field(default_factory=dict)
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
            self.highs.setOptionValue("time_limit", float(time_limit_seconds))
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

        col_value = sol.col_value
        selected_poses: List[Dict[str, Any]] = []
        for (group_id, pose_idx), col in self.z_col_by_group_pose.items():
            if col_value[col] > 0.5:
                selected_poses.append(
                    {"group_id": group_id, "pose_idx": int(pose_idx)}
                )
        ghost_xy: Optional[Tuple[int, int]] = None
        for anchor_idx, col in self.u_col_by_anchor_idx.items():
            if col_value[col] > 0.5:
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
    include_power_coverage: bool = False,
) -> HighsMinimumModel:
    """Build HiGHS MIP, 用 passModel 批量 CSR 跳过 Python sum() overhead.

    变量: z[(group_id, pose_idx)] / u[anchor_idx] / (optional) pole_z[idx] all binary.
    约束:
      ∀ group g:  Σ_p z[(g, p)] = 1
      Σ_a u[a] = 1 (if ghost_rect)
      ∀ cell c with ≥2 covers:  Σ_{occupy c} ≤ 1 (set-packing)
      (if include_power_coverage):
        ∀ (g, p):  Σ_{pole cover (g,p)} pole_z - z[g,p] >= 0
        无 coverer 的 z[g,p] == 0
    目标: minimize 0 (feasibility-only PoC).
    """
    grid = dict(rules["globals"]["grid"])
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])

    z_col_by_group_pose: Dict[Tuple[str, int], HighsCol] = {}
    u_col_by_anchor_idx: Dict[int, HighsCol] = {}
    anchor_xy_by_idx: Dict[int, Tuple[int, int]] = {}
    pole_col_by_pose_idx: Dict[int, HighsCol] = {}
    # cell -> list of col indices that occupy this cell
    cell_occupancy: Dict[Tuple[int, int], List[HighsCol]] = defaultdict(list)
    # group -> list of z cols (for exactly-one constraint)
    group_z_cols: Dict[str, List[HighsCol]] = defaultdict(list)
    # ghost anchor u cols
    anchor_u_cols: List[HighsCol] = []

    mandatory_groups: Dict[str, str] = {}
    for inst in instances:
        if not bool(inst.get("is_mandatory")):
            continue
        instance_id = str(inst["instance_id"])
        tpl = str(inst["facility_type"])
        mandatory_groups[instance_id] = tpl

    next_col = 0
    missing_pool_groups: List[str] = []

    for group_id, tpl in mandatory_groups.items():
        pool = list(facility_pools.get(tpl, []))
        if not pool:
            missing_pool_groups.append(group_id)
            continue
        for pose_idx, pose in enumerate(pool):
            col = next_col
            next_col += 1
            z_col_by_group_pose[(group_id, pose_idx)] = col
            group_z_cols[group_id].append(col)
            for cell in _pose_occupied_cells(pose):
                cx, cy = cell
                if 0 <= cx < grid_w and 0 <= cy < grid_h:
                    cell_occupancy[(cx, cy)].append(col)

    # Phase 3: add optional power_pole cols (z_var per pole pose) so they
    # participate in cell occupancy + serve as coverers below.
    if include_power_coverage:
        pole_pool = list(facility_pools.get("power_pole", []))
        for pole_idx, pole_pose in enumerate(pole_pool):
            col = next_col
            next_col += 1
            pole_col_by_pose_idx[pole_idx] = col
            for cell in _pose_occupied_cells(pole_pose):
                cx, cy = cell
                if 0 <= cx < grid_w and 0 <= cy < grid_h:
                    cell_occupancy[(cx, cy)].append(col)

    ghost_too_large = False
    if ghost_rect is not None:
        ghost_w, ghost_h = (int(ghost_rect[0]), int(ghost_rect[1]))
        if ghost_w > grid_w or ghost_h > grid_h:
            ghost_too_large = True
        else:
            anchor_idx = 0
            for ax in range(grid_w - ghost_w + 1):
                for ay in range(grid_h - ghost_h + 1):
                    col = next_col
                    next_col += 1
                    u_col_by_anchor_idx[anchor_idx] = col
                    anchor_xy_by_idx[anchor_idx] = (ax, ay)
                    anchor_u_cols.append(col)
                    for dx in range(ghost_w):
                        for dy in range(ghost_h):
                            cell_occupancy[(ax + dx, ay + dy)].append(col)
                    anchor_idx += 1

    num_col = next_col

    # CSR row-wise: list rows in order
    row_starts: List[int] = [0]
    col_indices: List[int] = []
    values: List[float] = []
    row_lower: List[float] = []
    row_upper: List[float] = []

    INF = highspy.kHighsInf
    infeasible_marker_added = False

    if ghost_too_large or missing_pool_groups:
        # 加一个 0=1 row 强制 infeasible (无变量, 但 row_lower=1 row_upper=1)
        row_starts.append(len(col_indices))
        row_lower.append(1.0)
        row_upper.append(1.0)
        infeasible_marker_added = True

    for group_id, cols in group_z_cols.items():
        for c in cols:
            col_indices.append(c)
            values.append(1.0)
        row_starts.append(len(col_indices))
        row_lower.append(1.0)
        row_upper.append(1.0)

    if anchor_u_cols:
        for c in anchor_u_cols:
            col_indices.append(c)
            values.append(1.0)
        row_starts.append(len(col_indices))
        row_lower.append(1.0)
        row_upper.append(1.0)

    cell_occupancy_constraint_count = 0
    for cell, cols in cell_occupancy.items():
        if len(cols) < 2:
            continue
        for c in cols:
            col_indices.append(c)
            values.append(1.0)
        row_starts.append(len(col_indices))
        row_lower.append(-INF)
        row_upper.append(1.0)
        cell_occupancy_constraint_count += 1

    # Phase 3: power coverage constraints
    power_coverage_row_count = 0
    power_coverage_nonzero = 0
    if include_power_coverage:
        pole_pool = list(facility_pools.get("power_pole", []))
        pole_cell_index = build_pole_cell_index(pole_pool)
        added_rows, added_nz = emit_power_coverage_rows(
            facility_pools=facility_pools,
            z_col_by_group_pose=z_col_by_group_pose,
            pole_col_by_pose_idx=pole_col_by_pose_idx,
            mandatory_groups=mandatory_groups,
            pole_cell_index=pole_cell_index,
            row_starts=row_starts,
            col_indices=col_indices,
            values=values,
            row_lower=row_lower,
            row_upper=row_upper,
            INF=INF,
        )
        power_coverage_row_count = added_rows
        power_coverage_nonzero = added_nz

    num_row = len(row_lower)

    lp = highspy.HighsLp()
    lp.num_col_ = num_col
    lp.num_row_ = num_row
    lp.col_cost_ = [0.0] * num_col
    lp.col_lower_ = [0.0] * num_col
    lp.col_upper_ = [1.0] * num_col
    lp.integrality_ = [highspy.HighsVarType.kInteger] * num_col
    lp.row_lower_ = row_lower
    lp.row_upper_ = row_upper
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = row_starts
    lp.a_matrix_.index_ = col_indices
    lp.a_matrix_.value_ = values
    lp.sense_ = highspy.ObjSense.kMinimize

    h = highspy.Highs()
    h.silent()
    h.passModel(lp)

    return HighsMinimumModel(
        highs=h,
        z_col_by_group_pose=z_col_by_group_pose,
        u_col_by_anchor_idx=u_col_by_anchor_idx,
        anchor_xy_by_idx=anchor_xy_by_idx,
        ghost_rect=ghost_rect,
        grid_w=grid_w,
        grid_h=grid_h,
        build_stats={
            "mandatory_group_count": len(mandatory_groups),
            "z_var_count": len(z_col_by_group_pose),
            "u_var_count": len(u_col_by_anchor_idx),
            "pole_var_count": len(pole_col_by_pose_idx),
            "cell_occupancy_constraint_count": cell_occupancy_constraint_count,
            "power_coverage_row_count": power_coverage_row_count,
            "power_coverage_nonzero": power_coverage_nonzero,
            "include_power_coverage": include_power_coverage,
            "ghost_rect": ghost_rect,
            "grid": {"width": grid_w, "height": grid_h},
            "infeasible_marker_added": infeasible_marker_added,
            "num_col": num_col,
            "num_row": num_row,
            "num_nonzero": len(values),
        },
    )

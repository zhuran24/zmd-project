"""HiGHS power coverage 约束 builder — Phase 3 production-grade 重写.

跟 OR-Tools master_model.py:_add_power_coverage_constraints (line 4571) 等价语义.

每个 mandatory facility pose 必须被至少一个 power_pole pose 覆盖:
    sum(pole_z[i] for i in coverers_of(g, p)) >= z[g, p]

coverers_of(g, p) = 哪些 pole pose 的 power_coverage_cells 跟 facility pose
(g, p) 的 occupied_cells 至少有一个 cell 重叠.

注意:
- 这个 module 是 standalone 数据结构 + CSR row 生成器, 不直接 build HighsLp.
- 跟 highs_master_model.build_highs_minimum_model 配合, 同 PoC session 把
  power_coverage rows append 到 row_starts / col_indices / values 数组里.
- Phase 3 集成进 build_highs_minimum_model 用一个 include_power_coverage=True
  flag, 调这里的 helper.

API:
  build_pole_cell_index(pole_pool) → Dict[cell, List[pole_pose_idx]]
  compute_facility_pose_coverers(facility_pose, pole_cell_index) → Set[int]
  emit_power_coverage_rows(...) → 返回 (new_row_count, total_nonzero_added)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Mapping, Sequence, Set, Tuple


def build_pole_cell_index(
    pole_pool: Sequence[Mapping],
) -> Dict[Tuple[int, int], List[int]]:
    """对每个 cell, 收集哪些 power_pole pose 的 PCC 包含它.

    输入: power_pool[i] 有 power_coverage_cells: List[[x, y]]
    输出: dict[(cx, cy)] = sorted list of pole pose indices
    """
    cell_to_poles: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for pole_idx, pose in enumerate(pole_pool):
        pcc = pose.get("power_coverage_cells") or []
        for cell in pcc:
            cell_to_poles[(int(cell[0]), int(cell[1]))].append(int(pole_idx))
    # sort for determinism
    return {cell: sorted(poles) for cell, poles in cell_to_poles.items()}


def compute_facility_pose_coverers(
    facility_pose: Mapping,
    pole_cell_index: Mapping[Tuple[int, int], Sequence[int]],
) -> Set[int]:
    """给定 facility pose 跟 cell-to-poles index, 返回 cover 这 pose 的 pole pose 集合.

    semantic 跟 OR-Tools 一致: 一个 pole cover 这 facility, 当且仅当该 pole 的
    PCC 跟 facility 的 occupied_cells 至少有一个 cell 重叠.
    """
    coverers: Set[int] = set()
    for cell in facility_pose.get("occupied_cells", []):
        key = (int(cell[0]), int(cell[1]))
        if key in pole_cell_index:
            coverers.update(pole_cell_index[key])
    return coverers


def emit_power_coverage_rows(
    *,
    facility_pools: Mapping[str, Sequence[Mapping]],
    z_col_by_group_pose: Mapping[Tuple[str, int], int],
    pole_col_by_pose_idx: Mapping[int, int],
    mandatory_groups: Mapping[str, str],
    pole_cell_index: Mapping[Tuple[int, int], Sequence[int]],
    row_starts: List[int],
    col_indices: List[int],
    values: List[float],
    row_lower: List[float],
    row_upper: List[float],
    INF: float,
) -> Tuple[int, int]:
    """加 power_coverage 约束 rows 到 CSR 数组 (in-place).

    跟 OR-Tools 一致: 每个 mandatory pose 加 row "sum(pole_z) - z[g,p] >= 0".
    转 LP form: sum(pole_z) - z[g,p] >= 0 (row_lower=0, row_upper=INF).

    如果 facility pose 没 coverer → 加 z[g,p] == 0 (固定不选).

    返回 (added_row_count, total_nonzero_added).
    """
    added_rows = 0
    added_nonzero = 0
    no_coverer_zfixed: List[int] = []

    for group_id, tpl in mandatory_groups.items():
        if tpl == "power_pole":
            continue  # pole 自身不要求被 cover
        pool = facility_pools.get(tpl)
        if not pool:
            continue
        for pose_idx, pose in enumerate(pool):
            z_col = z_col_by_group_pose.get((group_id, pose_idx))
            if z_col is None:
                continue
            coverers = compute_facility_pose_coverers(pose, pole_cell_index)
            if not coverers:
                no_coverer_zfixed.append(z_col)
                continue
            # row: sum(pole_z[c] for c in coverers) - z[g,p] >= 0
            for cov_pose_idx in sorted(coverers):
                pole_col = pole_col_by_pose_idx.get(int(cov_pose_idx))
                if pole_col is None:
                    continue
                col_indices.append(pole_col)
                values.append(1.0)
            col_indices.append(z_col)
            values.append(-1.0)
            row_starts.append(len(col_indices))
            row_lower.append(0.0)
            row_upper.append(INF)
            added_rows += 1
            added_nonzero += len(coverers) + 1

    # fix no-coverer z = 0 batch: 单 row per z (sum(z) == 0)
    for z_col in no_coverer_zfixed:
        col_indices.append(z_col)
        values.append(1.0)
        row_starts.append(len(col_indices))
        row_lower.append(0.0)
        row_upper.append(0.0)
        added_rows += 1
        added_nonzero += 1

    return added_rows, added_nonzero

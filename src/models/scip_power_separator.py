"""SCIP power_coverage lazy separator — Phase 4 重写关键组件.

设计:
- 不在 build 阶段加 4M power_coverage rows (HiGHS 那条路撞 42 GB)
- 在 SCIP separator callback 内, fire on LP fractional solution
- 检测当前 LP 解中哪些 z[g,p] > 0.5 但没被任何 pole_z 覆盖 (违反 power)
- 加 violated cut (只加违反的, 不全加)
- SCIP 重 solve LP, 直到所有 z[g,p] 都满足 power_coverage

期望: build RAM 小 (跟 minimum 5 GB 类似), solve 阶段累 cut < 100K (估计),
RAM 不爆.

Separator 内 add_cut 用 model.addCons (实测 PoC 验过 work).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

import pyscipopt as scip


class PowerCoverageSeparator(scip.Sepa):
    """Lazy power_coverage cut: 给定 LP 解, 找违反 cover 的 facility pose."""

    def __init__(
        self,
        *,
        z_var_by_group_pose: Mapping[Tuple[str, int], Any],
        pole_var_by_pose_idx: Mapping[int, Any],
        facility_pools: Mapping[str, Sequence[Mapping]],
        mandatory_groups: Mapping[str, str],
        pole_cell_index: Mapping[Tuple[int, int], Sequence[int]],
    ):
        super().__init__()
        self.z_var_by_group_pose = z_var_by_group_pose
        self.pole_var_by_pose_idx = pole_var_by_pose_idx
        self.facility_pools = facility_pools
        self.mandatory_groups = mandatory_groups
        self.pole_cell_index = pole_cell_index
        # cache coverer set per (group_id, pose_idx) to avoid recompute each fire
        self._coverer_cache: Dict[Tuple[str, int], List[int]] = {}
        self.fired = 0
        self.cuts_added = 0

    def _coverers_for(self, group_id: str, pose_idx: int) -> List[int]:
        key = (group_id, pose_idx)
        if key in self._coverer_cache:
            return self._coverer_cache[key]
        tpl = self.mandatory_groups[group_id]
        pose = self.facility_pools[tpl][pose_idx]
        coverers: set[int] = set()
        for cell in pose.get("occupied_cells", []):
            ck = (int(cell[0]), int(cell[1]))
            if ck in self.pole_cell_index:
                coverers.update(self.pole_cell_index[ck])
        result = sorted(coverers)
        self._coverer_cache[key] = result
        return result

    def sepaexeclp(self):
        self.fired += 1
        added_this_round = 0
        for (group_id, pose_idx), z_var in self.z_var_by_group_pose.items():
            z_val = self.model.getVal(z_var)
            if z_val < 0.5:
                continue
            coverers = self._coverers_for(group_id, pose_idx)
            if not coverers:
                # pose has no coverer at all — force z = 0
                self.model.addCons(z_var == 0, name=f"force_zero_{group_id}_{pose_idx}_round{self.fired}")
                added_this_round += 1
                continue
            pole_sum = sum(
                self.model.getVal(self.pole_var_by_pose_idx[c])
                for c in coverers
                if c in self.pole_var_by_pose_idx
            )
            if pole_sum >= z_val - 1e-6:
                continue
            pole_vars = [
                self.pole_var_by_pose_idx[c]
                for c in coverers
                if c in self.pole_var_by_pose_idx
            ]
            self.model.addCons(
                scip.quicksum(pole_vars) - z_var >= 0,
                name=f"power_{group_id}_{pose_idx}_round{self.fired}",
            )
            added_this_round += 1

        self.cuts_added += added_this_round
        if added_this_round > 0:
            return {"result": scip.SCIP_RESULT.CONSADDED}
        return {"result": scip.SCIP_RESULT.DIDNOTFIND}

"""A 批 0：C6 供电编码原型（pairwise cover 布尔 + 半具体化几何）。

测量专用 monkeypatch——绝非 certified 旋钮；结果 JSON 透明记录编码名。
语义：与 witness 逐点等价的 ∃-证人析取展开（同一四条矩形相交不等式，
出处 exact_coordinate_master._add_power_coverage_selected_geometry:5388-5403，
含 '+2+radius-1' 不对称常量——2×2 杆使 anchor 盒每轴负向 r+1 正向 r）。
红线（对抗审查）：cover_lit ≤ pole.active 是 soundness 必需项（inactive 杆
坐标钉在域角落，漏掉 = 角落附近可拿假覆盖）。
"""
from __future__ import annotations

from typing import Any

import src.models.exact_coordinate_master as ecm

_ORIG = ecm.CoordinateExactMasterDelegate._add_geometric_power_coverage_constraints


def _add_geometric_power_coverage_constraints_c6(self: Any) -> None:
    powered_slots = self._all_powered_slots()
    pole_slots = self._all_power_pole_slots()
    radius = int(self._power_coverage_radius())
    if not self._supports_rectangular_power_coverage() or not pole_slots:
        # 非矩形世界/无杆世界回退原实现（table 路径/fail-closed 语义保持）
        _ORIG(self)
        return

    cover_literals = 0
    for powered_slot in powered_slots:
        fx = self._slot_footprint_x_start(powered_slot)
        fy = self._slot_footprint_y_start(powered_slot)
        fw = self._slot_footprint_width(powered_slot)
        fh = self._slot_footprint_height(powered_slot)
        witnesses = []
        for pole_slot in pole_slots:
            lit = self.model.NewBoolVar(
                f"c6cov__{pole_slot.key}__{powered_slot.key}"
            )
            if pole_slot.active is not None:
                self.model.Add(lit <= pole_slot.active)
            constraints = [
                self.model.Add(fx <= pole_slot.x + 2 + radius - 1),
                self.model.Add(pole_slot.x - radius <= fx + fw - 1),
                self.model.Add(fy <= pole_slot.y + 2 + radius - 1),
                self.model.Add(pole_slot.y - radius <= fy + fh - 1),
            ]
            for constraint in constraints:
                constraint.OnlyEnforceIf(lit)
            witnesses.append(lit)
            cover_literals += 1
        if powered_slot.active is not None:
            self.model.Add(sum(witnesses) >= powered_slot.active)
        else:
            self.model.Add(sum(witnesses) >= 1)

    self.owner.build_stats["power_coverage"] = {
        "representation": "coordinate_geometric",
        "encoding": "c6_pairwise_cover_v0_prototype",
        "powered_slots": len(powered_slots),
        "pole_slots": len(pole_slots),
        "cover_literals": int(cover_literals),
        "witness_indices": 0,
        "element_constraints": 0,
        "radius": radius,
    }


def apply_c6_patch() -> None:
    ecm.CoordinateExactMasterDelegate._add_geometric_power_coverage_constraints = (
        _add_geometric_power_coverage_constraints_c6
    )


def revert_c6_patch() -> None:
    ecm.CoordinateExactMasterDelegate._add_geometric_power_coverage_constraints = _ORIG

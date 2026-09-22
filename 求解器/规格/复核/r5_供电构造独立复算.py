# -*- coding: utf-8 -*-
"""r5 可导出性复核：供电格集合两读法的下界构造（独立于 r4 脚本重写）。
只用规则 L76（供电桩 2x2，以中心为原点 12x12 范围内若有需电单位的一部分）、
L44（小制造单位 3x3）、L8（基地 70x70），核对 约束·供电下限「一个供电桩至多为 24 台制造单位供电」。
构造即可证伪上界，不需要最大独立集。"""

BASE = 70
A = B = 30                      # 桩占格左下角，取基地内部
PILE = {(A + dx, B + dy) for dx in (0, 1) for dy in (0, 1)}
CX = CY = A + 1                 # 中心落在格交点

def covered_cols(rule):
    # 中心区域 R=[CX-6,CX+6]；positive_area 取与格方块有正面积交的格，closed_touch 再加边界接触格
    if rule == "positive_area":
        return set(range(CX - 6, CX + 6))          # 12 列
    return set(range(CX - 7, CX + 7))              # 14 列（含两侧接触列）

def powered(rule, x0, y0):
    cols, rows = covered_cols(rule), covered_cols(rule)
    return any(x in cols for x in range(x0, x0 + 3)) and any(y in rows for y in range(y0, y0 + 3))

def build(rule):
    cols = sorted(covered_cols(rule))
    lo, hi = cols[0] - 2, cols[-1]                 # 3x3 起点使其至少一格落入覆盖列
    starts = list(range(lo, hi + 1, 3))            # 间隔 3 保证互不重叠
    placed = []
    for x0 in starts:
        for y0 in starts:
            cells = {(x0 + i, y0 + j) for i in range(3) for j in range(3)}
            if cells & PILE:                       # 不能压住供电桩
                continue
            assert all(0 <= c < BASE for cell in cells for c in cell), "越界"
            assert powered(rule, x0, y0), "未被覆盖"
            placed.append((x0, y0))
    # 互不重叠自检
    occ = set()
    for x0, y0 in placed:
        cells = {(x0 + i, y0 + j) for i in range(3) for j in range(3)}
        assert not (cells & occ), "构造内部重叠"
        occ |= cells
    return placed

for rule in ("positive_area", "closed_touch"):
    p = build(rule)
    print(f"{rule}: 一个供电桩可同时为 {len(p)} 台 3x3 制造单位供电（构造下界）；"
          f"约束·供电下限 的上界 24 → {'相容' if len(p) <= 24 else '矛盾'}")

#!/usr/bin/env python3
# 复核 r4 · 可导出性视角的独立复算
# 目的：穷举核验「一个 2x2 供电桩最多能为多少台 3x3 制造单位供电」，
#       用来对照 求解约束.txt 的 供电下限「至多 24 / 14 / 8 台」。
# 只用三份正式文件的条文：规则 L44（小制造单位 3x3）、L76（供电桩 2x2、
# 中心为原点的 12x12 范围内有一部分即供电）、L8（基地 70x70）。
# 两种待审读法取自 求解器/规格/选择点清单.md 的 T15 `power.cell_rule`。

BASE = 70


def covered_axis(a: int, rule: str) -> set:
    """桩 2x2 占格在该轴上为 a、a+1，几何中心 c=a+1；返回被覆盖的格下标集合。"""
    c = a + 1
    if rule == "positive_area":
        # 格方块 [i,i+1] 与中心方块 [c-6,c+6] 有正面积交 <=> c-6 <= i <= c+5
        return set(range(c - 6, c + 6))          # 12 个
    if rule == "closed_touch":
        # 闭区间相交（含边界接触）<=> c-7 <= i <= c+6
        return set(range(c - 7, c + 7))          # 14 个
    raise ValueError(rule)


def max_units(a: int, b: int, rule: str, size: int = 3, base: int = BASE) -> int:
    """桩占格左下角 (a,b) 时，最多能有多少台互不重叠的 size×size 制造单位获得供电。"""
    cx, cy = covered_axis(a, rule), covered_axis(b, rule)
    cands = []
    for x0 in range(0, base - size + 1):
        xs = set(range(x0, x0 + size))
        if not xs & cx:
            continue
        for y0 in range(0, base - size + 1):
            ys = set(range(y0, y0 + size))
            if not ys & cy:
                continue
            if (xs & {a, a + 1}) and (ys & {b, b + 1}):
                continue                          # 与桩占格重叠，不能同时存在
            cands.append((x0, y0))
    # size×size 同构方块的最大不重叠集合由 size×size 个相位网格之一达到
    best = 0
    for ox in range(size):
        for oy in range(size):
            n = sum(1 for (x0, y0) in cands
                    if (x0 - ox) % size == 0 and (y0 - oy) % size == 0)
            best = max(best, n)
    return best


if __name__ == "__main__":
    rows = [
        ("桩在内部", 30, 30, 24),
        ("桩占格含第 1 列（贴一边）", 0, 30, 14),
        ("桩占格含第 1 列与第 1 行（贴两边）", 0, 0, 8),
    ]
    print("读法          位置                                 计数  约束·供电下限上界  相容？")
    for rule in ("positive_area", "closed_touch"):
        for name, a, b, bound in rows:
            n = max_units(a, b, rule)
            print(f"{rule:14s}{name:34s}{n:5d}{bound:14d}      {'是' if n <= bound else '否（矛盾）'}")

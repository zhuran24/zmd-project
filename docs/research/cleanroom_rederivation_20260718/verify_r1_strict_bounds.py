#!/usr/bin/env python3
"""R1 严格版回复的两项量化断言的独立复算（2026-07-20）。

断言 1（47 边界模式塌缩）：46 台边界仓每边恰 23 台（⌊70/3⌋=23 上限强制均分）、
每边 23 个 3 格区间盖 69 格留 1 个 gap（gap ≡ 0 mod 3，24 个位置）、
角格 (0,0) 互斥 ⇒ g_L=0 ∨ g_B=0 ⇒ 24+24−1=47。

断言 2（certified 起始上界 (1326, 34)）：
- 自由格 ≤ 4900 − 3544 − 4·2 = 1348（P≥2：219 受电本体两两不交，
  单塔覆盖 ≤144 格 ⇒ ⌈219/144⌉=2）；
- 52 个 generic 出口 slot（46 边界 + 6 core）恰等于 52 路原料需求 ⇒ 全部激活
  ⇒ 46 个边界接驳格（identity 语义=池内 stored 口格，几何实取自 f05b1291 池：
  左仓 anchor y=a → (1, a+1)，底仓对称）是强制非本体格；
- 列 0/行 0 各只剩 1 个自由格 ⇒ 短边 ≥6 的矩形不能含列 0/行 0；
- 对 47 模式 × 全部尺寸对枚举 |R∩Q_δ| 的最大值 M，筛
  w·h + |Q_δ| − M ≤ 1348。

本脚本用集合语义精确计数（含 (1,1) 双重身份格），复算结果与 GPT Pro 断言
逐字一致：无序尺寸对 1,182、最大可行面积 1326、lex 最优对 34×39。
运行：.venv-uvbolt-backup/bin/python3.13 docs/research/cleanroom_rederivation_20260718/verify_r1_strict_bounds.py
"""

from __future__ import annotations

import bisect

CAP = 4900 - 3544 - 4 * 2  # 1348


def anchors(gap: int) -> list[int]:
    """一条边上 gap 处留空后 23 个 1×3 区间的 anchor 序列。"""
    out = list(range(0, gap, 3)) + [gap + 1 + 3 * k for k in range(23 - gap // 3)]
    assert len(out) == 23 and all(0 <= a <= 67 for a in out), gap
    return out


def main() -> int:
    gaps = list(range(0, 70, 3))
    patterns = [(0, g) for g in gaps] + [(g, 0) for g in gaps if g != 0]
    assert len(patterns) == 47, len(patterns)

    pairs = [(w, h) for w in range(6, 70) for h in range(6, 70) if w * h <= CAP]
    unordered = sum(1 for w, h in pairs if w <= h)
    assert unordered == 1182, unordered

    feasible: set[tuple[int, int]] = set()
    for g_left, g_bottom in patterns:
        left_ys = sorted(a + 1 for a in anchors(g_left))
        bottom_xs = sorted(a + 1 for a in anchors(g_bottom))
        q_cells = {(1, y) for y in left_ys} | {(x, 1) for x in bottom_xs}
        n_q = len(q_cells)

        def count(vals: list[int], lo: int, size: int) -> int:
            return bisect.bisect_left(vals, lo + size) - bisect.bisect_left(vals, lo)

        def max_window(vals: list[int], size: int, lo_min: int) -> int:
            return max(
                (count(vals, lo, size) for lo in range(lo_min, 71 - size)), default=0
            )

        for w, h in pairs:
            if (w, h) in feasible:
                continue
            corner = {(1, y) for y in left_ys if 1 <= y < 1 + h} | {
                (x, 1) for x in bottom_xs if 1 <= x < 1 + w
            }
            m = max(len(corner & q_cells), max_window(left_ys, h, 2), max_window(bottom_xs, w, 2))
            if w * h + n_q - m <= CAP:
                feasible.add((w, h))

    top_area = max(w * h for w, h in feasible)
    best = max((p for p in feasible if p[0] * p[1] == top_area), key=min)
    print(f"patterns=47 unordered_pairs={unordered}")
    print(f"max_feasible_area={top_area} best_pair={best} min_side={min(best)}")
    assert top_area == 1326 and min(best) == 34, (top_area, best)
    print("VERIFIED: certified 起始上界 (1326, 34) 复算一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

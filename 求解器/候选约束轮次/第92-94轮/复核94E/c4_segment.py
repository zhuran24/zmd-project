#!/usr/bin/env python3
"""复核94E：候选「制造取货连续同种段步数界」的段长公式与台数算术。

编码一（最短路）：c 条通道，机器每步至多送一件，同一通道两次送货至少隔 8 步。
  状态 = 各通道剩余冷却步数的多重集（排序元组）。首件之前全部通道就绪（这是最宽的起态）。
  求送完 q 件的最少步数 t_q−t_1，再加 1（下一段首件最早在下一步）。与公式 8⌊(q−1)/c⌋+((q−1) mod c)+1 比较。
编码二（闭式贪心下界的逐项验证）：直接构造「轮流用 c 条通道、每轮 c 件连发、轮间等冷却」的时序并检查合法，
  给出可达的上界；与编码一的下界相等即说明公式恰为最短。
另外核算：采种 16 批/tick、研磨 31.5 批/tick 的来源（两套记法），以及 N−a/9≥16、N≥18、a≤4、W≤4/tick。
"""
import json
from fractions import Fraction
from collections import deque


def min_span_bfs(c, q):
    start = (0,) * c
    # BFS：每步一层；状态 (已送件数, 冷却多重集)；首件在第 0 步送出
    best = None
    frontier = {}
    # 第 0 步送第一件
    cd = tuple(sorted((8,) + (0,) * (c - 1)))
    frontier = {(1, cd)}
    t = 0
    if q == 1:
        return 1
    while True:
        t += 1
        nxt = set()
        for (k, cd) in frontier:
            cd2 = tuple(max(0, x - 1) for x in cd)
            nxt.add((k, cd2))  # 本步不送
            if 0 in cd2:
                i = cd2.index(0)
                cd3 = tuple(sorted(cd2[:i] + (8,) + cd2[i + 1:]))
                if k + 1 == q:
                    return t + 1  # t_q − t_1 = t，再加 1
                nxt.add((k + 1, cd3))
        frontier = nxt


def construct(c, q):
    times, chans = [], []
    t = 0
    for i in range(q):
        r, j = divmod(i, c)
        times.append(8 * r + j)
        chans.append(j)
    # 合法性：每步至多一件，同通道相隔 ≥8
    assert len(set(times)) == len(times)
    last = {}
    for tt, ch in zip(times, chans):
        if ch in last:
            assert tt - last[ch] >= 8
        last[ch] = tt
    return times[-1] - times[0] + 1


def formula(c, q):
    return 8 * ((q - 1) // c) + ((q - 1) % c) + 1


def main():
    rows = []
    allok = True
    for c in range(1, 7):
        for q in range(1, 41):
            a = min_span_bfs(c, q)
            b = construct(c, q)
            f = formula(c, q)
            ok = (a == b == f)
            allok &= ok
            rows.append((c, q, a, b, f, ok))
    # 采种机每批 2 件、单路：16m−7 ≥ 9m
    seg = [(m, formula(1, 2 * m), 9 * m, formula(1, 2 * m) >= 9 * m) for m in range(1, 51)]
    # 需求两套记法
    # 记法一：分数率
    battery, capsule = Fraction(3, 5), Fraction(11, 20)
    dense_src = battery * 15
    parts, bottles = battery * 10, capsule * 10
    steel = parts * 1 + bottles * 2
    dense_iron = steel
    fine_qh = capsule * 10
    grind1 = dense_src + dense_iron + fine_qh
    sand_powder = grind1  # 每批 1 砂叶粉末
    sand_crush = sand_powder / 3
    qh_crush = fine_qh * 2 / 2  # 每批 2 荞花粉末 → 1 荞花 2 粉末
    # 植物回路：采种 x 批产 2x 种子 → 2x 植株 = x（采种）+ 粉碎量
    sand_harvest = sand_crush
    qh_harvest = qh_crush
    harvest1 = sand_harvest + qh_harvest
    # 记法二：20 tick 整数件数（12 电池、11 胶囊）
    B20, C20 = 12, 11
    g2 = B20 * 15 + (B20 * 10 + C20 * 10 * 2) + C20 * 10
    sp2 = g2
    assert sp2 % 3 == 0
    h2 = sp2 // 3 + (C20 * 10 * 2) // 2
    grind2, harvest2 = Fraction(g2, 20), Fraction(h2, 20)
    # 台数
    def min_N_all_restricted(need):
        N = 1
        while Fraction(8, 9) * N < need:
            N += 1
        return N
    seeds = dict(N_all_restricted_frac=min_N_all_restricted(harvest1),
                 N_all_restricted_int=min(N for N in range(1, 100) if 8 * N >= 9 * 16),
                 a_max_at_N16=max(a for a in range(0, 17) if Fraction(16) - Fraction(a, 9) >= harvest1),
                 a_max_at_N16_int=max(a for a in range(0, 17) if 9 * 16 - a >= 9 * 16))
    grind = dict(a_max_at_N32_frac=max(a for a in range(0, 33) if 32 - Fraction(a, 9) >= grind1),
                 a_max_at_N32_int=max(a for a in range(0, 33) if 2 * (9 * 32 - a) >= 9 * 63),
                 W_per_tick_max_N32=str(8 * (32 - grind1)),  # W ≤ NK − 8B，K=8P，B ≥ 31.5P → W/P ≤ 8(N−31.5)
                 W_per_tick_max_N32_int=str(Fraction(8 * 32 * 2 - 8 * 63, 2)))
    out = dict(segment_formula_all_ok=allok, segment_rows=rows, seed_segment_16m_minus_7_ge_9m=all(s[3] for s in seg),
               grind_need=[str(grind1), str(grind2)], harvest_need=[str(harvest1), str(harvest2)],
               seeds=seeds, grind=grind)
    json.dump(out, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)
    print({k: v for k, v in out.items() if k != 'segment_rows'})


if __name__ == '__main__':
    main()

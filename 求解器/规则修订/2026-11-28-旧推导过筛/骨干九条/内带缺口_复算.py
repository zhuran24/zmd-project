"""内带缺口独立复算。仅用 Python 标准库，全部流量以半件为整数单位。"""
from collections import Counter
from itertools import product
from math import ceil
from fractions import Fraction


SIZE = 70
INNER = {(1, i) for i in range(1, SIZE)} | {(i, 1) for i in range(1, SIZE)}
OUTER = {(0, i) for i in range(SIZE)} | {(i, 0) for i in range(SIZE)}


def strips(start=0, skipped=False, mouths=()):
    """从角落开始按顺序铺三格口，只许空过一格。"""
    if start == SIZE:
        if skipped:
            yield mouths
        return
    if start + 3 <= SIZE:
        yield from strips(start + 3, skipped, mouths + (start + 1,))
    if not skipped:
        yield from strips(start + 1, True, mouths)


def inward_point(side, depth, along):
    return (depth, along) if side == 0 else (along, depth)


def blocks_on_inner(size, ores):
    """每个触内带的方块都以第1行或第1列为底边之一。"""
    union = set()
    max_cells = 0
    for side in range(2):
        for start in range(1, SIZE - size + 1):
            block = {inward_point(side, n, k) for n in range(1, size + 1)
                     for k in range(start, start + size)}
            if not block.isdisjoint(ores):
                continue
            hit = block & INNER
            max_cells = max(max_cells, len(hit))
            union.update(hit)
    return union, max_cells


def geometry():
    distribution = Counter()
    by_distance = {}
    configs = 0
    max_body = max_pole = max_tangent = 0
    g_min = 46
    for left, bottom in product(strips(), repeat=2):
        use = [{inward_point(side, 0, i + d) for i in centers for d in (-1, 0, 1)}
               for side, centers in enumerate((left, bottom))]
        if not use[0].isdisjoint(use[1]):
            continue
        configs += 1
        q, = OUTER - use[0] - use[1]
        ore = {inward_point(side, 1, i) for side, centers in enumerate((left, bottom))
               for i in centers}
        assert len(ore) == 46 and ore <= INNER
        body_cells, _ = blocks_on_inner(3, ore)
        _, pole_max = blocks_on_inner(2, ore)
        tangent_possible = 0
        g = 0
        previous_faces = set()
        for side, centers in enumerate((left, bottom)):
            for i in centers:
                def pt(depth, along):
                    return inward_point(side, depth, along)

                tangent_possible += sum(pt(1, i + e) in body_cells for e in (-1, 1))
                if not (i - 3 in centers and i + 3 in centers):
                    continue
                g += 1
                o, z = pt(1, i), pt(2, i)
                # 不同矿源的可选新增面必须完全不交。在同一矿源处只取一个分支。
                choices = {(o, z), (z, o)}
                for e in (-1, 1):
                    u, v = pt(1, i + e), pt(1, i + 2*e)
                    assert u not in ore | body_cells and v not in ore | body_cells
                    assert u != q and u in INNER and v in INNER
                    choices.update(((u, o), (u, v)))
                assert previous_faces.isdisjoint(choices)
                previous_faces.update(choices)
        # 角区另补三面。q 非角时，让跳过角格的那一带取作横带。
        if q == (0, 0):
            c = (1, 1)
            assert {(1, 2), (2, 1)} <= ore and c not in ore | body_cells
            assert not any(start == c for start, _ in previous_faces)
            corner_bonus = 4 - 1  # 非源内带外向已付一面
        else:
            side = 1 if q[0] == 0 else 0
            along = bottom if side == 1 else left
            p, z = inward_point(side, 1, 2), (2, 2)
            u, v = inward_point(side, 1, 3), inward_point(side, 1, 4)
            o = (1, 1)
            assert {o, p, inward_point(side, 1, 5)} <= ore
            assert 2 in along and {u, v}.isdisjoint(ore | body_cells)
            extra_faces = {(o, p), (p, z), (z, p), (u, p), (u, v)}
            assert extra_faces.isdisjoint(previous_faces)
            # (o,p) 总可取。p 的矿路决定再取哪一对。
            corner_bonus = 1 + 2
        g_min = min(g_min, g)
        max_body = max(max_body, len(body_cells))
        max_pole = max(max_pole, pole_max)
        max_tangent = max(max_tangent, tangent_possible)
        # 只记一定能付的切向、内带外向，以及每个普通矿源的两面。
        band_total = 2*len(ore) - tangent_possible + len(INNER - ore - body_cells) + 2*g + corner_bonus
        distance = sum(q)
        assert by_distance.setdefault(distance, band_total) == band_total
        distribution[g, tangent_possible, len(body_cells), band_total] += 1
    print("联合排布数、内带长度、机身可占内带格最大数、单桩交集最大数、可能贴机身切向数最大值、普通矿源最少数：",
          configs, len(INNER), max_body, max_pole, max_tangent, g_min)
    print("（普通矿源、可能贴机身切向、机身可占内带格、连角区补数的合计）及排布数：", sorted(distribution.items()))
    return by_distance, g_min


def fleet_weight(length, machine_cap, count, demand_twice):
    """固定支持后存在半件格极点，证明见文稿。算出单机各总量下的精确最小权，再拼全类。"""
    single = {}
    for flow in product(range(3), repeat=length):
        load = sum(flow)
        if load > 2*machine_cap:
            continue
        opened = [i for i, f in enumerate(flow) if f]
        cost = sum(flow[i] + flow[j] for i, j in zip(opened, opened[1:]) if j-i <= 3)
        single[load] = min(single.get(load, cost), cost)
    costs = {0: 0}
    for _ in range(count):
        next_costs = {}
        for prior, c1 in costs.items():
            for load, c2 in single.items():
                total = prior + load
                if total <= demand_twice:
                    next_costs[total] = min(next_costs.get(total, c1+c2), c1+c2)
        costs = next_costs
    return Fraction(costs[demand_twice], 2)


def main():
    by_distance, g_min = geometry()
    band_min = min(by_distance.values())
    weights = [fleet_weight(*args) for args in
               ((6, 3, 32, 189), (3, 2, 6, 22), (6, 5, 3, 30), (6, 4, 3, 22))]
    # 各表最后一项为零。再多的机器只需用记权非负。
    tables = (
        (6, 3, 189, 32, [Fraction(379-8*n, 2) for n in range(32, 48)] + [0]),
        (3, 2, 22, 6, [10, 8, 6, 4, 2, 0]),
        (6, 5, 30, 3, [24, 18, 10, 6, 2, 0]),
        (6, 4, 22, 3, [14, 6, 2, 0]),
    )
    for length, cap, demand, first, expected in tables:
        actual = [fleet_weight(length, cap, n, demand)
                  for n in range(first, first + len(expected))]
        assert actual == expected, (first, actual)
    print("四张台数权重表已逐项核对（至首个零下界）。")
    inputs = (68, 51, 95, 11, 6, 32, 16, 15, 11)
    outputs = (95, 51, 32, 6, 6, 32, 32, 3, 3)
    active = sum(inputs) + 2 + sum(outputs) + 52
    core = 2 * 2 * (3 - 1)
    border_gap = 4
    print("接口、核心切向、边界余格：", active, core, border_gap)
    print("研、塑、封、灌各自权重：", *weights, "总权重", sum(weights))
    simple_base = active + core + border_gap + 90 + 88
    bonuses = {d: band - band_min for d, band in sorted(by_distance.items())}
    print("按非零边界坐标（角格取0）的额外方向：", bonuses)
    print("去掉四机型权重的通用常数：", active + core + border_gap + band_min)
    with_ring = active + core + border_gap + ceil(sum(weights)) + band_min
    print("不含普通矿源及权重的底数、四机型无箱带周边下界、沿用旧X的下界、不含周边的偶数下界：",
          simple_base, with_ring, with_ring-2, 2*((with_ring+1)//2))
    assert simple_base + 2*g_min + 3 + ceil(sum(weights)) == with_ring
    assert all(b == (9 if d in (0, 69) else 2 if d in (3, 66) else 0) for d, b in bonuses.items())


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""独立编码 B：端口线段相交；枚举通道排列再求单位次序见证；整数层数方程。

不读取 A 的输入或结果，也不导入任何其他复核/推导脚本。只写 stdout。
"""
import itertools
import collections
import json


def layout(name):
    # (名称, 类型, x, y, 宽, 高, 存货边, 取货边)，与 A 分别手工输入。
    tri = [("A", "粉碎机", 20, 20, 3, 3, "W", "E"),
           ("B", "分流器", 23, 20, 1, 1, "W", "ENS"),
           ("C", "汇流器", 23, 21, 1, 1, "WNS", "E")]
    square = [("A", "分流器", 30, 30, 1, 1, "N", "ESW"),
              ("B", "分流器", 31, 30, 1, 1, "W", "ENS"),
              ("C", "分流器", 30, 31, 1, 1, "E", "NSW"),
              ("D", "分流器", 31, 31, 1, 1, "S", "ENW")]
    star = [("A", "分流器", 10, 10, 1, 1, "W", "ENS"),
            ("B", "传送带", 11, 10, 1, 1, "W", "E"),
            ("C", "传送带", 10, 11, 1, 1, "S", "N"),
            ("D", "传送带", 10, 9, 1, 1, "N", "S")]
    extra = [("PA", "传送带", 30, 29, 1, 1, "N", "S"),
             ("PB", "传送带", 32, 30, 1, 1, "W", "E"),
             ("PC", "传送带", 29, 31, 1, 1, "E", "W"),
             ("PD", "传送带", 31, 32, 1, 1, "S", "N"),
             ("MA", "粉碎机", 29, 26, 3, 3, "N", "S"),
             ("MB", "粉碎机", 33, 29, 3, 3, "W", "E"),
             ("MC", "粉碎机", 26, 30, 3, 3, "E", "W"),
             ("MD", "粉碎机", 30, 33, 3, 3, "S", "N")]
    fed_star = star + [("W", "仓库取货口", 0, 9, 1, 3, "", "E")]
    for x in range(1, 10):
        fed_star.append(("F" + str(x), "传送带", x, 10, 1, 1, "W", "E"))
    return {"triangle": tri, "square": square, "star": star,
            "fed_star": fed_star, "exits": square + extra}[name]


def channels(rows):
    def face(r, d):
        _, _, x, y, w, h, _, _ = r
        if r[1] == "仓库取货口":
            assert d == "E" and w == 1 and h == 3
            return ("vertical", x + w, y + 1, y + 2)
        return {"E": ("vertical", x + w, y, y + h),
                "W": ("vertical", x, y, y + h),
                "N": ("horizontal", y + h, x, x + w),
                "S": ("horizontal", y, x, x + w)}[d]

    for r in rows:
        assert min(r[2:4]) >= 0 and r[2] + r[4] <= 70 and r[3] + r[5] <= 70
    for a, b in itertools.combinations(rows, 2):
        overlap_x = min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2])
        overlap_y = min(a[3] + a[5], b[3] + b[5]) - max(a[3], b[3])
        assert overlap_x <= 0 or overlap_y <= 0
    opposite = dict(E="W", W="E", N="S", S="N")
    arcs = []
    for a, b in itertools.permutations(rows, 2):
        if a[1] in ("粉碎机", "仓库取货口") and b[1] in ("粉碎机", "仓库取货口"):
            continue
        for d in a[7]:
            if opposite[d] not in b[6]:
                continue
            f, g = face(a, d), face(b, opposite[d])
            if f[:2] == g[:2]:
                length = min(f[3], g[3]) - max(f[2], g[2])
                arcs.extend([[a[0], b[0]]] * max(0, length))
    return sorted(arcs)


def orders(nodes, edges):
    edges = sorted("".join(sorted(e)) for e in edges)
    units = list(itertools.permutations(nodes))
    times = []
    hist = collections.Counter()
    tied = 0
    for p in units:
        rank = {x: p.index(x) + 1 for x in nodes}
        t = {e: max(rank[e[0]], rank[e[1]]) for e in edges}
        multiplicities = collections.Counter(t.values())
        hist[",".join(str(multiplicities[k]) for k in sorted(multiplicities))] += 1
        tied += any(v > 1 for v in multiplicities.values())
        times.append(t)
    good, bad = [], []
    pair_count = 0
    compatible_per_unit = [[] for _ in units]
    witnesses = {}
    # 与 A 相反：先枚举待核通道排列，再检查有没有单位次序能产生它。
    for p in itertools.permutations(edges):
        supporting = []
        for k, t in enumerate(times):
            if all(t[p[i]] <= t[p[i + 1]] for i in range(len(p) - 1)):
                supporting.append(k)
                compatible_per_unit[k].append(list(p))
        if supporting:
            good.append(list(p))
            witnesses["/".join(p)] = list(units[supporting[0]])
        else:
            bad.append(list(p))
        pair_count += len(supporting)
    return {"vertices": list(nodes), "edges": edges, "unit_order_count": len(units),
            "unit_orders_with_ties": tied, "batch_size_histogram": dict(sorted(hist.items())),
            "order_refinement_pairs": pair_count, "refinement_count": len(good),
            "missing_count": len(bad), "refinements": good, "missing": bad,
            "witnesses": witnesses,
            "schedules": [{"unit_order": list(p), "times": t, "refinements": seq}
                          for p, t, seq in zip(units, times, compatible_per_unit)]}


def integer_layers():
    # 四个分流器 A→B→D→C→A；每台另可按直达粉碎机的一段带数层。
    # 带的层数为 1；每个分流器在 2…5 中，逐条核 h=1+h(所选下游)。
    nodes = ["A", "B", "C", "D", "PA", "PB", "PC", "PD"]
    next_node = {"A": "B", "B": "D", "C": "A", "D": "C"}
    good = []
    for values in itertools.product(range(2, 6), repeat=4):
        h = dict(zip("ABCD", values))
        if all(h[u] == 2 or h[u] == h[next_node[u]] + 1 for u in "ABCD"):
            good.append(list(values) + [1, 1, 1, 1])
    # 无出口时四个等式相加会得到 sum(h)=sum(h)+4，不存在有限解。
    pure_ring_bounded_solutions = []
    for v in itertools.product(range(1, 5), repeat=4):
        h = dict(zip("ABCD", v))
        if all(h[u] == h[next_node[u]] + 1 for u in "ABCD"):
            pure_ring_bounded_solutions.append(list(v))
    return {"vertices": nodes, "vectors": sorted(good), "acyclic_choice_count": len(good),
            "pure_ring_bounded_solutions": pure_ring_bounded_solutions,
            "pure_ring_sum_gap": len(next_node)}


def main():
    out = {"method": "B: rectangle faces; edge permutations and max endpoint times; integer equations",
           "cases": {}}
    for name in ("triangle", "square", "star"):
        rows = layout(name)
        arcs = channels(rows)
        case = orders(sorted(r[0] for r in rows), arcs)
        case["directed_channels"] = arcs
        out["cases"][name] = case
    out["layer_channels"] = channels(layout("exits"))
    out["fed_star_channels"] = channels(layout("fed_star"))
    out["layers"] = integer_layers()
    # 轮询第一次从第二条开始；枚举给各通道分配的名次，而不是模拟搬货。
    rr = []
    for ranks in itertools.permutations(range(1, 4)):
        rank = dict(zip(("AB", "AC", "AD"), ranks))
        order = sorted(rank, key=rank.get)
        winner = next(e for e in rank if rank[e] == 2)
        rr.append({"tie_order": order, "first_success": winner})
    out["first_send"] = sorted(rr, key=lambda r: r["tie_order"])
    out["first_send_histogram"] = dict(sorted(collections.Counter(r["first_success"] for r in rr).items()))
    family = []
    for n in range(1, 5):
        nodes = "ABCD"[:n]
        pairs = list(itertools.combinations(nodes, 2))
        for mask in range(2 ** len(pairs)):
            subset = [pairs[i] for i in range(len(pairs)) if (mask // (2 ** i)) % 2]
            r = orders(nodes, subset)
            family.append({"n": n, "edges": r["edges"], "refinements": r["refinements"],
                           "unit_orders_with_ties": r["unit_orders_with_ties"],
                           "order_refinement_pairs": r["order_refinement_pairs"]})
    out["graph_family"] = family
    out["graph_family_count"] = len(family)
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

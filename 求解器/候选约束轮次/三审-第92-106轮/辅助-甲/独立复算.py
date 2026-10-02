#!/usr/bin/env python3
"""甲席独立复算；仅用标准库，不读取、导入或运行其他席的程序。

数值由明列的规则模型计算。有限枚举是证明的核对，不代替一般性证明。
输出固定在本脚本目录。运行：python3 -B 独立复算.py
"""
from fractions import Fraction as F
from itertools import permutations, product, combinations
from pathlib import Path
from collections import Counter
from functools import lru_cache
import json
import random

OUT = Path(__file__).resolve().parent
results = {}


def construction_orders(n, edges):
    orders = set()
    untied = 0
    for build in permutations(range(n)):
        rank = {v: i for i, v in enumerate(build)}
        batches = {}
        for i, (u, v) in enumerate(edges):
            batches.setdefault(max(rank[u], rank[v]), []).append(i)
        groups = [batches[t] for t in sorted(batches)]
        untied += all(len(g) == 1 for g in groups)
        for chunks in product(*(permutations(g) for g in groups)):
            orders.add(tuple(e for chunk in chunks for e in chunk))
    # Independent reverse check: the last vertex contributes a suffix batch.
    def realizable(seq):
        @lru_cache(None)
        def strip(vertices, remaining):
            if not remaining:
                return True
            for v in vertices:
                incident = {i for i in remaining if v in edges[i]}
                k = len(incident)
                if not k or set(remaining[-k:]) == incident:
                    prefix = remaining[:-k] if k else remaining
                    if strip(tuple(x for x in vertices if x != v), prefix):
                        return True
            return False
        return strip(tuple(range(n)), seq)
    inverse = {s for s in permutations(range(len(edges))) if realizable(s)}
    assert inverse == orders
    return {"unit_orders": len(list(permutations(range(n)))),
            "untied_unit_orders": untied, "edge_orders": len(orders),
            "edge_order_set": [list(s) for s in sorted(orders)]}


graphs = {
    "三角形": (3, [(0, 1), (1, 2), (2, 0)]),
    "四单位环": (4, [(0, 1), (1, 2), (2, 3), (3, 0)]),
    "三支汇回图": (5, [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4)]),
    "双桥同轴含两条反向通道": (4, [(0, 1), (1, 2), (2, 1), (2, 3)]),
    "三叶树": (4, [(0, 1), (0, 2), (0, 3)]),
}
results["接通枚举"] = {k: construction_orders(*v) for k, v in graphs.items()}
assert [results["接通枚举"][k]["edge_orders"] for k in graphs] == [6, 16, 168, 20, 6]


def forest(n, edges):
    parent = list(range(n))
    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for u, v in edges:
        u, v = root(u), root(v)
        if u == v:
            return False
        parent[u] = v
    return True


forest_tests = 0
for n in range(1, 6):
    possible = list(combinations(range(n), 2))
    for bits in product((0, 1), repeat=len(possible)):
        edges = [e for e, b in zip(possible, bits) if b]
        # An acyclic build is a removal order with at most one live neighbor.
        @lru_cache(None)
        def peel(vertices):
            if not vertices:
                return True
            return any(sum(u in vertices and w in vertices and v in (u, w)
                           for u, w in edges) <= 1
                       and peel(tuple(x for x in vertices if x != v)) for v in vertices)
        assert peel(tuple(range(n))) == forest(n, edges)
        forest_tests += 1
results["无同刻与森林"] = {"全部简单图数_1至5点": forest_tests, "all_equal": True,
                          "含重边路径无无同刻次序": not forest(*graphs["双桥同轴含两条反向通道"])}


def level_vectors(options):
    keys = tuple(options)
    vectors = set()
    for selected in product(*(options[k] or [None] for k in keys)):
        nxt = dict(zip(keys, selected))
        values = {}
        def value(x, stack):
            if x in stack:
                raise ValueError("cycle")
            if x not in values:
                values[x] = 1 if nxt[x] is None else 1 + value(nxt[x], stack | {x})
            return values[x]
        try:
            vectors.add(tuple(value(k, set()) for k in keys))
        except ValueError:
            pass
    # Check all bounded integer solutions separately, without reading selected edges.
    direct = {v for v in product(range(1, len(keys) + 1), repeat=len(keys))
              if all((v[i] == 1 if not options[k] else
                      any(v[i] == v[keys.index(j)] + 1 for j in options[k]))
                     for i, k in enumerate(keys))}
    assert vectors == direct
    return [list(v) for v in sorted(vectors)]


results["整套层数"] = {
    "两点互指且各通末端": level_vectors({"A": ["B", "T"], "B": ["A", "T"], "T": []}),
    "方环有出口": level_vectors({"A": ["B"], "B": ["C"], "C": ["D"], "D": ["A", "T"], "T": []}),
    "纯环": level_vectors({"A": ["B"], "B": ["C"], "C": ["D"], "D": ["A"]}),
}
assert results["整套层数"]["两点互指且各通末端"] == [[2, 2, 1], [2, 3, 1], [3, 2, 1]]
assert results["整套层数"]["方环有出口"] == [[5, 4, 3, 2, 1]]

grades = []
for nh, nl in product(range(1, 4), repeat=2):
    counts = Counter()
    for p in permutations(range(1 + nh + nl)):
        b = {v: i for i, v in enumerate(p)}
        hi = min(max(b[0], b[i]) for i in range(1, nh + 1))
        lo = min(max(b[0], b[i]) for i in range(nh + 1, nh + nl + 1))
        counts["高先" if hi < lo else "低先" if lo < hi else "同刻"] += 1
        # Form edges by scanning built vertices, independently of the max formula.
        built = set()
        events = {}
        for t, v in enumerate(p):
            built.add(v)
            for i in range(1, 1 + nh + nl):
                if 0 in built and i in built and i not in events:
                    events[i] = t
        assert hi == min(events[i] for i in range(1, nh + 1))
        assert lo == min(events[i] for i in range(nh + 1, nh + nl + 1))
    assert counts["高先"] and counts["低先"]
    grades.append({"高级条数": nh, "低级条数": nl, **counts})
results["等层级序可反转"] = grades


def cooldown_counter(steps, initial, resets, inactive):
    rem = initial
    attempts = []
    # rem is the remaining duration at this step's own box judgement.
    for s in range(steps):
        if s in resets:
            rem = 0
        if s not in inactive:
            if rem == 0:
                attempts.append(s)
                rem = 40
            rem -= 1
    return attempts


def cooldown_active_clock(steps, initial, resets, inactive):
    active_time = 0
    due = initial
    attempts = []
    for s in range(steps):
        if s in resets:
            due = active_time
        if s not in inactive:
            if active_time >= due:
                attempts.append(s)
                due = active_time + 40
            active_time += 1
    return attempts


rng = random.Random(920106)
for _ in range(1000):
    initial = rng.randrange(41)
    resets = {s for s in range(240) if rng.randrange(40) == 0}
    inactive = {s for s in range(240) if rng.randrange(6) == 0}
    assert cooldown_counter(240, initial, resets, inactive) == cooldown_active_clock(240, initial, resets, inactive)
results["传输相位"] = {
    "5tick步数": int(F(5) / F(1, 8)),
    "17步前离线保留": cooldown_counter(101, 0, set(), set()),
    "17步前离线清空": cooldown_counter(101, 0, {17}, set()),
    "两箱初相差23_57步前一起清空": [cooldown_counter(150, q, {57}, set()) for q in (0, 23)],
    "独立时钟对照例数": 1000,
}
assert results["传输相位"]["17步前离线保留"] == [0, 40, 80]
assert results["传输相位"]["17步前离线清空"] == [0, 17, 57, 97]


def polling_after_offline(order, last, clear=False):
    start = 1 % len(order) if clear or last is None else (order.index(last) + 1) % len(order)
    return order[start:] + order[:start]


results["轮询记录"] = {
    "分流上次乙_保留": polling_after_offline(["甲", "乙", "丙"], "乙"),
    "分流上次乙_清空": polling_after_offline(["甲", "乙", "丙"], "乙", True),
    "同起点不同循环方向": [polling_after_offline(o, None) for o in (["甲", "乙", "丙"], ["丙", "乙", "甲"])],
}
assert results["轮询记录"]["同起点不同循环方向"] == [["乙", "丙", "甲"], ["乙", "甲", "丙"]]


# Exact 18-recipe stoichiometry, transcribed from rules 82--115.
recipes = [
    ("粉碎源矿", "粉碎机", {"源矿": 1}, {"源石粉末": 1}, 1),
    ("粉碎蓝铁块", "粉碎机", {"蓝铁块": 1}, {"蓝铁粉末": 1}, 1),
    ("粉碎荞花", "粉碎机", {"荞花": 1}, {"荞花粉末": 2}, 1),
    ("粉碎砂叶", "粉碎机", {"砂叶": 1}, {"砂叶粉末": 3}, 1),
    ("精炼蓝铁矿", "精炼炉", {"蓝铁矿": 1}, {"蓝铁块": 1}, 1),
    ("精炼致密蓝铁粉末", "精炼炉", {"致密蓝铁粉末": 1}, {"钢块": 1}, 1),
    ("蓝铁回炼", "精炼炉", {"蓝铁粉末": 1}, {"蓝铁块": 1}, 1),
    ("研磨蓝铁", "研磨机", {"蓝铁粉末": 2, "砂叶粉末": 1}, {"致密蓝铁粉末": 1}, 1),
    ("研磨源石", "研磨机", {"源石粉末": 2, "砂叶粉末": 1}, {"致密源石粉末": 1}, 1),
    ("研磨荞花", "研磨机", {"荞花粉末": 2, "砂叶粉末": 1}, {"细磨荞花粉末": 1}, 1),
    ("塑形", "塑形机", {"钢块": 2}, {"钢质瓶": 1}, 1),
    ("配件", "配件机", {"钢块": 1}, {"钢制零件": 1}, 1),
    ("种植荞花", "种植机", {"荞花种子": 1}, {"荞花": 1}, 1),
    ("种植砂叶", "种植机", {"砂叶种子": 1}, {"砂叶": 1}, 1),
    ("采种荞花", "采种机", {"荞花": 1}, {"荞花种子": 2}, 1),
    ("采种砂叶", "采种机", {"砂叶": 1}, {"砂叶种子": 2}, 1),
    ("封装", "封装机", {"钢制零件": 10, "致密源石粉末": 15}, {"高容谷地电池": 1}, 5),
    ("灌装", "灌装机", {"钢质瓶": 10, "细磨荞花粉末": 10}, {"精选荞愈胶囊": 1}, 5),
]
items = sorted(set().union(*(set(a) | set(b) for _, _, a, b, _ in recipes)))
targets = {"高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20)}

# Mineral content is derived without presupposing zero non-product warehousing.
weights = {"源矿": (F(1), F(0)), "蓝铁矿": (F(0), F(1))}
weights.update({x: (F(0), F(0)) for x in ("荞花", "砂叶", "荞花种子", "砂叶种子")})
while len(weights) < len(items):
    previous_size = len(weights)
    for _, _, ins, outs, _ in recipes:
        if all(x in weights for x in ins):
            assert len(outs) == 1
            product_item, quantity = next(iter(outs.items()))
            content = tuple(sum(count*weights[x][axis] for x,count in ins.items())/quantity for axis in range(2))
            if product_item in weights:
                assert weights[product_item] == content
            else:
                weights[product_item] = content
    assert len(weights) > previous_size
for _, _, ins, outs, _ in recipes:
    for axis in range(2):
        assert sum(c*weights[x][axis] for x,c in ins.items()) == sum(c*weights[x][axis] for x,c in outs.items())
results["独立矿物权重"] = {
    "权重顺序": ["源矿", "蓝铁矿"], "全部物品": {x: [str(v) for v in w] for x,w in weights.items()},
    "配方守恒等式数": 36,
    "成品目标矿耗": [str(sum(rate*weights[x][axis] for x,rate in targets.items())) for axis in range(2)]}
assert results["独立矿物权重"]["成品目标矿耗"] == ["18", "34"]


def solve_rates(recycle):
    mat = []
    for x in items:
        if x not in ("源矿", "蓝铁矿"):
            mat.append([F(out.get(x, 0) - ins.get(x, 0)) for _, _, ins, out, _ in recipes] + [targets.get(x, F(0))])
    mat.append([F(int(i == 6)) for i in range(18)] + [F(recycle)])
    pivot_row = 0
    pivots = []
    for col in range(18):
        choices = [i for i in range(pivot_row, len(mat)) if mat[i][col]]
        if not choices:
            continue
        i = choices[0]
        mat[i], mat[pivot_row] = mat[pivot_row], mat[i]
        div = mat[pivot_row][col]
        mat[pivot_row] = [x / div for x in mat[pivot_row]]
        for j in range(len(mat)):
            if j != pivot_row and mat[j][col]:
                factor = mat[j][col]
                mat[j] = [a - factor * b for a, b in zip(mat[j], mat[pivot_row])]
        pivots.append(col)
        pivot_row += 1
    assert pivots == list(range(18))
    rates = [mat[i][-1] for i in range(18)]
    assert all(not any(row[:-1]) and row[-1] == 0 for row in mat[18:])
    return rates


rates0 = solve_rates(0)
rates1 = solve_rates(1)
machine_order = ["粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"]
machine_rates = {m: sum(q for q, (_, typ, _, _, _) in zip(rates0, recipes) if typ == m) for m in machine_order}
durations = {typ: d for _, typ, _, _, d in recipes}
ceil = lambda q: -(-q.numerator // q.denominator)
machine_counts = {m: ceil(q * durations[m]) for m, q in machine_rates.items()}
assert list(machine_counts.values()) == [68, 51, 32, 6, 6, 32, 16, 3, 3]
mineral_need = {x: sum(q * ins.get(x, 0) for q, (_, _, ins, _, _) in zip(rates0, recipes)) for x in ("源矿", "蓝铁矿")}
assert mineral_need == {"源矿": F(18), "蓝铁矿": F(34)}
areas = {m: 25 if m in ("种植机", "采种机") else 24 if m in ("研磨机", "封装机", "灌装机") else 9 for m in machine_order}
results["配方与台数"] = {
    "配方数": len(recipes), "物品数": len(items),
    "逐配方批率_r0": {row[0]: str(q) for row, q in zip(recipes, rates0)},
    "逐配方批率对r的系数": {row[0]: str(b-a) for row, a, b in zip(recipes, rates0, rates1)},
    "机型批率": {m: str(q) for m, q in machine_rates.items()},
    "20tick所需批数": {m: int(20*q) for m, q in machine_rates.items()},
    "20tick单机容量": {m: 20//durations[m] for m in machine_order},
    "下限台数": machine_counts, "总台数": sum(machine_counts.values()),
    "总占格": sum(machine_counts[m] * areas[m] for m in machine_order),
    "原矿需求": {x: str(q) for x, q in mineral_need.items()},
    "出库口上限": 2*(70//3)+6,
}
assert results["配方与台数"]["总台数"] == 217
assert results["配方与台数"]["总占格"] == 3291
slots = {m: 2 if m in ("研磨机", "封装机", "灌装机") else 1 for m in machine_order}
assert all(len(ins) == slots[m] for _, m, ins, _, _ in recipes)
results["误料与输出拒收"] = {
    "一格误料后每配方种类需求都大于剩余格数": True,
    "研磨三主料的两两组合": list(combinations(["蓝铁粉末", "源石粉末", "荞花粉末"], 2)),
    "三件整批空格开始可装": 3*(50//3), "其后缓存受阻批量": 3,
    "一机缓存批数上限": 1,
}

# Set-boundary conservation, enumerated closed paths of a tiny capacity-2 store.
balance_paths = 0
def walks(stock, start, depth, incoming_q, incoming_b, outgoing):
    global balance_paths
    if depth == 0:
        if stock == start:
            assert incoming_q + incoming_b == outgoing
            balance_paths += 1
        return
    walks(stock, start, depth-1, incoming_q, incoming_b, outgoing)
    if stock < 2:
        walks(stock+1, start, depth-1, incoming_q+1, incoming_b, outgoing)
        walks(stock+1, start, depth-1, incoming_q, incoming_b+1, outgoing)
    if stock:
        walks(stock-1, start, depth-1, incoming_q, incoming_b, outgoing+1)
for start in range(3):
    walks(start, start, 7, 0, 0, 0)
results["来源守恒"] = {"7事件封闭库存路径数": balance_paths,
    "缓存例": {"入株": 1, "出种": 2, "制造净增": 1},
    "上界不足例": {"Qmax": 1, "bmax": "1/5", "Q": 0, "b": 0, "q": 0, "要求r": "1/2"},
    "有下界的充分式例": {"Q0": "4/5", "b0": "1/5", "推出q至少": str(F(4, 5)-F(1, 5))}}

checked = 0
for x in range(301):
    for v in range(301):
        assert (min(x, v) == 0) == (x == 0 or v == 0)
        checked += 1
results["传输实际动作截面"] = {
    "x_v_0至300等价核对数": checked,
    "先送货后传输": {"箱判定开始x": 1, "v": 1, "物理送货": 1, "传输前x": 0, "传输入库": 0},
    "先传输后送货": {"箱判定开始x": 1, "v": 1, "传输前x": 1, "传输入库": 1},
    "说明": "枚举只核算等价式；任意非负整数的一般证明用min的零点性质。",
}

results["all_checks_passed"] = True
(OUT / "独立复算结果.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"all_checks_passed": True, "输出": str(OUT / "独立复算结果.json"),
                  "接通计数": {k:v["edge_orders"] for k,v in results["接通枚举"].items()},
                  "台数": machine_counts, "森林核对图数": forest_tests}, ensure_ascii=False))

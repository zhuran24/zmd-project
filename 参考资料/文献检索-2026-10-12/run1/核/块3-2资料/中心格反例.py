#!/usr/bin/env python3
"""规则73--82的一格运输单位枚举；静态可布线反例，不是运行内核。"""
import itertools
import json

# 坐标闭区间；x向右，y向上。端点机器只有朝十字孔的中间端口可用。
rectangles = {
    "西源_精炼炉_钢块_出东": (25, 27, 29, 31),
    "南源_粉碎机_蓝铁粉末_出北": (29, 31, 25, 27),
    "北汇_塑形机_钢块_入南": (29, 31, 33, 35),
    "东汇_精炼炉_蓝铁粉末_入西": (33, 35, 29, 31),
    "桩_西南": (28, 29, 28, 29),
    "桩_东南": (31, 32, 28, 29),
    "桩_西北": (28, 29, 31, 32),
    "桩_东北": (31, 32, 31, 32),
}
occupied = {}
for name, (x0, x1, y0, y1) in rectangles.items():
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            assert (x, y) not in occupied, (name, occupied[(x, y)])
            assert 0 <= x < 70 and 0 <= y < 70
            occupied[x, y] = name
free = [(x, y) for x in range(28, 33) for y in range(28, 33)
        if (x, y) not in occupied]
assert set(free) == ({(x, 30) for x in range(28, 33)}
                     | {(30, y) for y in range(28, 33)})

sides = "WNES"
opposite = {"W": "E", "E": "W", "N": "S", "S": "N"}
# (入边, 出边)，对每种一格元件取最乐观的端口可达关系。
# 分/汇的内部选择也放宽成所有合法出边/入边，仍不能满足两条指定进路。
states = []
for a, b in itertools.permutations(sides, 2):
    states.append((f"带_{a}{b}", {(a, b)}))
for a in sides:
    states.append((f"准入口_{a}", {(a, opposite[a])}))
    states.append((f"分流_{a}", {(a, b) for b in sides if b != a}))
    states.append((f"汇流_{a}", {(b, a) for b in sides if b != a}))
states.append(("桥", {(a, opposite[a]) for a in sides}))
required = {("W", "N"), ("S", "E")}
witnesses = [name for name, pairs in states if required <= pairs]
assert len(states) == 25
assert witnesses == []

# 五节点粗图：W--C--N 和 S--C--E，每段边界容量1，需求也都是1。
loads = {"W-C": 1, "C-N": 1, "S-C": 1, "C-E": 1}
assert all(load <= 1 for load in loads.values())
print(json.dumps({
    "units_nonoverlapping_and_inside_70x70": True,
    "free_cross_cells": sorted(free),
    "coarse_boundary_loads": loads,
    "coarse_capacity_each": 1,
    "coarse_feasible": True,
    "single_cell_transport_states_checked": len(states),
    "fine_center_witnesses": witnesses,
    "evidence_type": "static_rule_enumeration_not_runtime_simulation",
}, ensure_ascii=False, indent=2))

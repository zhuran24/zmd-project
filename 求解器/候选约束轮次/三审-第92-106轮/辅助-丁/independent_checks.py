#!/usr/bin/env python3
"""三审辅助丁独立核算。仅用标准库，不导入推导/复核/内核程序。

局部状态图和发送日历用于检查引理，不声称给出全厂布局。
输出只写入本脚本目录。运行: python -B independent_checks.py
"""
from collections import Counter, defaultdict
from fractions import Fraction as F
from itertools import combinations, permutations, product
from pathlib import Path
import hashlib
import json
import math
import re
import time

OUT = Path(__file__).resolve().parent
ROUNDS = OUT.parent.parent
SNAP = ROUNDS / "第107-109轮/前提快照"


def linear_solve(rows, n):
    a = [[F(x) for x in row] for row in rows]
    pivots = []
    for col in range(n):
        k = next((k for k in range(len(pivots), len(a)) if a[k][col]), None)
        if k is None:
            continue
        i = len(pivots)
        a[i], a[k] = a[k], a[i]
        d = a[i][col]
        a[i] = [v / d for v in a[i]]
        for j in range(len(a)):
            if j != i and a[j][col]:
                d = a[j][col]
                a[j] = [v - d * w for v, w in zip(a[j], a[i])]
        pivots.append(col)
    assert all(any(row[:-1]) or not row[-1] for row in a)
    assert len(pivots) == n, (len(pivots), n)
    ans = [F(0)] * n
    for i, col in enumerate(pivots):
        ans[col] = a[i][-1]
    return ans


def parse_recipes():
    recipes = []
    machine = None
    machine_names = {"粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"}
    for line_no, raw in enumerate((SNAP / "《明日方舟：终末地》游戏规则.txt").read_text().splitlines(), 1):
        line = raw.strip()
        if line in machine_names:
            machine = line
        if " → " not in line:
            continue
        lhs, rhs = line.split(" → ")
        rhs, ticks = re.split(r"[,，]\s*", rhs)
        def side(s):
            return {name: int(q) for q, name in (part.split(" ", 1) for part in s.split(" ＋ "))}
        recipes.append(dict(line=line_no, machine=machine, inputs=side(lhs), outputs=side(rhs), ticks=int(ticks.split()[0])))
    assert len(recipes) == 18
    return recipes


def material_counts(recipes):
    species = sorted(set().union(*(set(r[side]) for r in recipes for side in ("inputs", "outputs"))))
    n = len(recipes)
    reverse = next(i for i, r in enumerate(recipes) if r["line"] == 90)
    cases = []
    for recycling in [F(0), F(1, 7), F(2)]:
        rows = []
        for s in species:
            if s in ("源矿", "蓝铁矿"):
                continue
            demand = {"高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20)}.get(s, F(0))
            rows.append([r["outputs"].get(s, 0) - r["inputs"].get(s, 0) for r in recipes] + [demand])
        rows.append([int(i == reverse) for i in range(n)] + [recycling])
        rates = linear_solve(rows, n)
        by_machine = defaultdict(F)
        for r, x in zip(recipes, rates):
            assert x >= 0
            by_machine[r["machine"]] += x
        ore = {s: sum(x * r["inputs"].get(s, 0) for r, x in zip(recipes, rates)) for s in ("蓝铁矿", "源矿")}
        assert by_machine["研磨机"] == F(63, 2)
        assert by_machine["采种机"] == 16
        assert ore == {"蓝铁矿": 34, "源矿": 18}
        cases.append(dict(recycling=recycling, batch_rates=dict(by_machine), ore=ore, rates_by_rule_line={r["line"]: x for r, x in zip(recipes, rates)}))
    # 独立整数倒推，未调用上面的线性消元结果。
    battery, capsule = 12, 11
    parts, bottles = 10 * battery, 10 * capsule
    steel = parts + 2 * bottles
    dense_source, fine_buck = 15 * battery, 10 * capsule
    grinders = steel + dense_source + fine_buck
    leaf_crush = grinders // 3
    buck_crush = (2 * fine_buck) // 2
    seed_batches = leaf_crush + buck_crush
    assert (steel, dense_source, fine_buck, grinders, seed_batches) == (340, 180, 110, 630, 320)
    ports = 2 * (70 // 3) + 6
    assert ports == 52
    return dict(matrix_cases=cases, per_20_ticks=dict(parts=parts, bottles=bottles, steel=steel, dense_source=dense_source, fine_buck=fine_buck, grinders=grinders, leaf_crush=leaf_crush, buck_crush=buck_crush, seed_batches=seed_batches), warehouse_port_capacity=ports)


def belt_cycle(n, boundary_period, blocked_phase, full, splitter_first=True):
    # 年龄为完整步末已滞留步数，截到8；内部移动可在外送判定前后发生。
    belt = [8] * n if full else [None] * n
    split = 8 if full else None
    seen = {}
    q = occupancy = t = 0
    while True:
        key = (tuple(belt), split, t % boundary_period)
        if key in seen:
            old_t, old_q, old_h = seen[key]
            p, sent, h = t - old_t, q - old_q, occupancy - old_h
            if splitter_first:
                assert 8 * n * sent <= h <= n * p - sent
            return dict(n=n, boundary_period=boundary_period, blocked_phase=blocked_phase, full=full, splitter_first=splitter_first, transient=old_t, period=p, sent=sent, occupancy=h, rate=F(8 * sent, p))
        seen[key] = (t, q, occupancy)
        assert t < 200000
        belt = [None if a is None else min(a + 1, 8) for a in belt]
        split = None if split is None else min(split + 1, 8)
        def internal():
            for j in range(n - 2, -1, -1):
                if belt[j] == 8 and belt[j + 1] is None:
                    belt[j], belt[j + 1] = None, 0
        def give():
            nonlocal split
            if split == 8 and belt[0] is None:
                split, belt[0] = None, 0
        def send():
            nonlocal q
            if belt[-1] == 8 and t % boundary_period != blocked_phase:
                belt[-1] = None
                q += 1
            internal()
        internal()
        if splitter_first:
            give()
            send()
        else:
            send()
            give()
        if split is None:
            split = 0
        occupancy += sum(a is not None for a in belt)
        t += 1


def capacity_and_layers():
    cycles = []
    for n, boundary, full in product([1, 2, 3, 4, 6, 8, 16, 32, 64], [(1, -1), (9, 0), (17, 0)], [False, True]):
        p, blocked = boundary
        row = belt_cycle(n, p, blocked, full)
        cycles.append(row)
        if p == 1:
            assert row["rate"] == F(8 * n, 8 * n + 1)
    reverse = [belt_cycle(n, 1, -1, False, False) for n in [1, 2, 3, 8, 32]]
    assert all(r["rate"] == 1 for r in reverse)
    def levels(length, dead):
        successor = {i: i + 1 for i in range(length - 1)}
        if not dead:
            successor[length - 1] = "machine"
        def level(i):
            j = successor.get(i)
            return 1 + level(j) if isinstance(j, int) and j in successor else 1
        return [level(i) for i in range(length)]
    layer_cases = []
    for k, m in product(range(1, 33), repeat=2):
        dead, alive = levels(k, True), levels(m, False)
        assert alive[0] == m
        assert dead[0] == max(1, k - 1)
        x_via_dead = 1 + dead[0] if k >= 2 else None
        assert x_via_dead is None or x_via_dead == k
        layer_cases.append([k, m, x_via_dead, alive[0]])
    # k=m=2 的单位建造证书。每条边形成时刻=max(两端建成时刻)。
    witnesses = []
    for dead_is_belt in (False, True):
        kinds = {"X": "special", "D": "belt" if dead_is_belt else "special", "E": "special", "B": "belt", "G": "special", "M": "machine"}
        edges = [("X", "D"), ("D", "E"), ("X", "B"), ("B", "G"), ("G", "M")]
        orders = []
        for order in permutations(kinds):
            build = {u: i for i, u in enumerate(order)}
            if max(build[u] for u in kinds if kinds[u] != "belt") > min(build[u] for u in kinds if kinds[u] == "belt"):
                continue
            edge_times = {a + "->" + b: max(build[a], build[b]) for a, b in edges}
            x_first = min(edge_times["X->D"], edge_times["X->B"])
            if x_first < edge_times["B->G"]:
                orders.append((order, edge_times))
        assert orders
        witnesses.append(dict(dead_head_belt=dead_is_belt, valid_strict_orders=len(orders), witness=orders[0]))
    return dict(capacity_cases=cycles, opposite_order_controls=reverse, layer_case_count=len(layer_cases), layer_cases=layer_cases, equal_layer_build_witnesses=witnesses)


def full_rate_and_segments():
    phase_cases = []
    for p in (8, 16, 24, 32):
        n = p // 8
        schedules = []
        checked = 0
        for times in combinations(range(p), n):
            checked += 1
            gaps = [b - a for a, b in zip(times, times[1:] + (times[0] + p,))]
            if min(gaps) >= 8:
                assert set(gaps) == {8}
                assert len({t % 8 for t in times}) == 1
                schedules.append(times)
        assert len(schedules) == 8
        phase_cases.append(dict(period=p, checked=checked, full_rate_schedules=schedules))
    assignments = sum(1 for _ in permutations(range(8), 6))
    assert assignments == math.factorial(8) // math.factorial(2) == 20160
    # 前7步发送历史的动态规划；不使用待检公式作转移。
    segment_results = []
    for c in range(1, 7):
        dp = {0: 0}
        first_hit = {}
        for steps in range(1, 8 * 80 + 1):
            nxt = {}
            for mask, sent in dp.items():
                shifted = (mask << 1) & 127
                nxt[shifted] = max(nxt.get(shifted, -1), sent)
                if mask.bit_count() < c:
                    nxt[shifted | 1] = max(nxt.get(shifted | 1, -1), sent + 1)
            dp = nxt
            maximum = max(dp.values())
            for q in range(1, min(maximum, 80) + 1):
                first_hit.setdefault(q, steps)
            if len(first_hit) == 80:
                break
        for q in range(1, 81):
            formula = 8 * ((q - 1) // c) + ((q - 1) % c) + 1
            assert first_hit[q] == formula, (c, q, first_hit[q], formula)
            segment_results.append([c, q, first_hit[q]])
    assert all(16 * m - 7 >= 9 * m for m in range(1, 1001))
    min_seeders = next(n for n in range(100) if F(8 * n, 9) >= 16)
    assert min_seeders == 18
    return dict(phase_cases=phase_cases, six_named_channel_assignments=assignments, segment_case_count=len(segment_results), segment_results=segment_results, min_seeders_if_all_species_single_route=min_seeders, seed_rate_bound=F(8, 9), single_species_single_route_bound=F(1, 2))


def seed_balance_and_grinding():
    comparisons = 0
    for batches in range(1, 9):
        for word in product(("荞", "砂"), repeat=batches):
            expanded = [kind for kind in word for _ in range(2)]
            for r0, r1 in permutations(range(8), 2):
                events = sorted((8 * k + r, channel) for k in range(batches) for channel, r in enumerate((r0, r1)))
                channels = [channel for _, channel in events]
                assert all(channels[i] != channels[(i + 1) % len(channels)] for i in range(len(channels)))
                for shift in (0, 1):
                    kinds = expanded[shift:] + expanded[:shift]
                    counts = Counter(zip(kinds, channels))
                    for kind in set(word):
                        assert counts[kind, 0] == counts[kind, 1] == word.count(kind)
                    comparisons += 1
    earliest = {}
    arrival_witnesses = {}
    for n_channels in (1, 2):
        candidates = []
        for t1, t2, c1, c2 in product(range(1, 18), range(1, 18), range(n_channels), range(n_channels)):
            if t2 < t1 or (c1 == c2 and t2 - t1 < 8):
                continue
            candidates.append((max(8, t2), t1, t2, c1, c2))
        earliest[n_channels] = min(x[0] for x in candidates)
        arrival_witnesses[n_channels] = min(candidates)
    assert earliest == {1: 9, 2: 8}
    limits = {}
    for n in (32, 33):
        a_max = max(a for a in range(n + 1) if F(n) - F(a, 9) >= F(63, 2))
        limits[n] = dict(every_batch_switching_machine_limit=a_max, counted_switches_per_tick=8 * (F(n) - F(63, 2)))
    assert limits[32] == dict(every_batch_switching_machine_limit=4, counted_switches_per_tick=4)
    assert limits[33]["every_batch_switching_machine_limit"] == 13
    workload, available = 8 * 630, 32 * 160
    assert available - workload == 80
    return dict(seed_species_phase_comparisons=comparisons, earliest_new_batch=earliest, arrival_witnesses=arrival_witnesses, grinding_limits=limits, per_20_ticks=dict(required_machine_steps=workload, available_machine_steps=available, counted_switch_budget=available-workload))


def box_potential():
    # 全部单格合法放宽转移：年龄截8；成熟未送时可把h放宽为1。
    states = [None] + list(range(9))
    def potential(a):
        return 0 if a is None else -min(a, 7)
    certificate = []
    for a in states:
        aged = None if a is None else min(a + 1, 8)
        outcomes = []
        if aged is None:
            outcomes += [(None, 0, 0), (0, 0, 0)]
        elif aged < 8:
            outcomes += [(aged, 0, 0)]
        else:
            outcomes += [(8, 0, 0), (8, 0, 1), (None, 1, 0), (0, 1, 0)]
        for b, sent, refused in outcomes:
            slack = 1 + potential(b) - potential(a) - 8 * sent - refused
            assert slack >= 0, (a, b, sent, refused, slack)
            certificate.append(dict(before=a, after=b, sent=sent, mature_refusal=refused, slack=slack))
    # 箱每8步在运输之后送1件：第一步拒收，随后以错开一步的相位满速。
    box = 50
    entered_at = -8
    events = []
    for t in range(160):
        sent = failed = 0
        if t - entered_at >= 8:
            if box < 50:
                box += 1
                sent = 1
                entered_at = t  # 源在本步后半补入，需再滞留8步。
            else:
                failed = 1
        if t % 8 == 0:
            assert box > 0
            box -= 1
        events.append(dict(step=t, sent=sent, failed=failed, box=box))
    assert events[0]["failed"] == 1
    assert all(e["failed"] == 0 for e in events[1:])
    assert all(e["sent"] == int(e["step"] % 8 == 1) for e in events[1:])
    return dict(potential="V(empty)=0; V(age)=-min(age,7)", edge_count=len(certificate), certificate=certificate, phase_shift_example=events[:18], steady_period_steps=8, steady_sent=1, steady_mature_refusals=0)


def main():
    start = time.monotonic()
    recipes = parse_recipes()
    results = dict(material=material_counts(recipes), capacity_layers=capacity_and_layers(), phases_segments=full_rate_and_segments(), seed_grinding=seed_balance_and_grinding(), box=box_potential())
    results["elapsed_seconds"] = time.monotonic() - start
    results["status"] = "PASS"
    (OUT / "independent_checks.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps(dict(status="PASS", elapsed_seconds=results["elapsed_seconds"], belt_cases=len(results["capacity_layers"]["capacity_cases"]), layer_cases=results["capacity_layers"]["layer_case_count"], segment_cases=results["phases_segments"]["segment_case_count"], seed_phase_cases=results["seed_grinding"]["seed_species_phase_comparisons"], potential_edges=results["box"]["edge_count"]), ensure_ascii=False))


if __name__ == "__main__":
    main()

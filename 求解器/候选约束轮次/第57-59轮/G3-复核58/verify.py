#!/usr/bin/env python3
"""第 58 轮 G3 独立复算。标准库；仅向本脚本目录写 verification.json。

五项均为局部必要条件检查，有限枚举不是整厂运行或任意规模的证明。
解析证明和规则行号见相邻的 G3-复核58.md。
"""
from collections import defaultdict
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPECTED = {
    "《明日方舟：终末地》游戏规则.txt": "4f04de50b2f743aec1da903f00f0f89f92f1aeba60eb4513320b71d0ee0a57fd",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6",
    "候选约束.txt": "a0ac3f9c82f371132b7de29fe47e4c6c587904680bc2786523de0c825fd5efd9",
    "思路.txt": "95d2af723613bfd61c325ab2fafd89bcd060f099d2a2172a1d79b206c3995cee",
    "求解器/候选约束轮次/第57-59轮/G3-推导.md": "10e1a1c1e0e2a56153d590912b622f8169ce79e348dda05337a01b164b167e79",
}


def inventory_checks():
    regions = []
    transitions = 0
    for name, a, b in [("研磨", 2, 1), ("封装", 10, 15), ("灌装", 10, 10)]:
        values = []
        for x, y in product(range(51), repeat=2):
            old = (x, y)
            z = b*x-a*y
            values.append(z)
            assert -50*a <= z <= 50*b
            events = []
            if x < 50:
                events.append(((x+1, y), (1, 0), 0))
            if y < 50:
                events.append(((x, y+1), (0, 1), 0))
            if x >= a and y >= b:
                events.append(((x-a, y-b), (0, 0), 1))
            for new, received, started in events:
                transitions += 1
                assert new == (old[0]+received[0]-a*started,
                               old[1]+received[1]-b*started)
                assert b*new[0]-a*new[1] == z+b*received[0]-a*received[1]
        assert (min(values), max(values)) == (-50*a, 50*b)
        assert max(values)-min(values) == 50*(a+b)
        regions.append(dict(recipe=name, states=len(values), raw_bounds=[min(values), max(values)],
                            raw_width=max(values)-min(values),
                            safe_open=[b*(a-1)-50*a, 50*b-a*(b-1)]))

    # 三种主粉可轮换，但两个存货格不能同时存放三种物品。
    mixed_states = [(0, 0, 0, 0)]
    for size in (1, 2):
        for places in combinations(range(4), size):
            for amounts in product(range(1, 51), repeat=size):
                s = [0]*4
                for i, n in zip(places, amounts):
                    s[i] = n
                mixed_states.append(tuple(s))
    mixed_events = 0
    recipes = [(2, 0, 0, 1), (0, 2, 0, 1), (0, 0, 2, 1)]
    for s in mixed_states:
        for use in recipes:
            if all(x >= n for x, n in zip(s, use)):
                new = tuple(x-n for x, n in zip(s, use))
                assert all(0 <= x <= 50 for x in new)
                assert sum(x > 0 for x in new) <= 2
                assert tuple(new[i]+use[i] for i in range(4)) == s
                mixed_events += 1

    # 三条存货通道，前两条各 ABAB，第三条恒 A。
    s = [20, 20]
    total = [0, 0]
    per_line = [0, 0]
    trace = []
    for tick in range(400):
        s[0] -= 2
        s[1] -= 1
        for material in (0 if tick % 2 == 0 else 1,)*2+(0,):
            s[material] += 1
            total[material] += 1
            assert all(0 <= x <= 50 for x in s)
        per_line[tick % 2] += 1
        if tick < 2:
            trace.append(s.copy())
    assert s == [20, 20] and total == [800, 400]
    assert per_line[0]-2*per_line[1] == -200

    def drain_word(word, initial, repeats):
        x, y = initial
        accepted = starts = 0
        for token in word*repeats:
            while x >= 2 and y >= 1:
                x -= 2
                y -= 1
                starts += 1
            if (token == "A" and x == 50) or (token == "B" and y == 50):
                return dict(blocked=True, inventory=[x, y], accepted=accepted, starts=starts)
            x += token == "A"
            y += token == "B"
            accepted += 1
        return dict(blocked=False, inventory=[x, y], accepted=accepted, starts=starts)

    burst = drain_word("A"*102+"B"*51, (50, 50), 2)
    assert burst == dict(blocked=True, inventory=[50, 0], accepted=100, starts=50)
    assert not drain_word("BAA", (50, 0), 200)["blocked"]
    return dict(fixed_recipe_states=7803, fixed_recipe_events=transitions, regions=regions,
                mixed_recipe_states=len(mixed_states), mixed_recipe_starts=mixed_events,
                three_channel_trace=trace, after_400_ticks=dict(inventory=s, receipts=total,
                single_mixed_line_deviation=-200, total_deviation=0), balanced_burst=burst)


@lru_cache(None)
def out_step(old, same, k, c):
    """同刻可先出旧货、整批入格、再出货；每口本刻仅有一个名额。

    放宽下游为每刻全部可收。old 为完成事件前的旧取货格件数。
    不允许半批入格或异种共格，返回同刻所有判定后可剩下的件数。
    """
    result = set()
    for before in range(min(old, c)+1):
        remaining = old-before
        if remaining and not same:
            continue
        placed = remaining+k
        if placed > 50:
            continue
        for after in range(min(placed, c-before)+1):
            result.add(placed-after)
    return tuple(sorted(result))


def cyclic_nodes(graph):
    """Kahn 删除无入边点；剩余非空当且仅当有限图存在有向回路。"""
    indegree = {u: 0 for u in graph}
    for neighbors in graph.values():
        for v in neighbors:
            indegree[v] += 1
    todo = [u for u, deg in indegree.items() if deg == 0]
    for u in todo:
        for v in graph[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                todo.append(v)
    return len(todo) < len(graph)


def window_checks():
    local_cases = 0
    for k, c, m in product(range(1, 4), range(1, 4), range(1, 101)):
        states = {0}
        for _ in range(m):
            states = {n for old in states for n in out_step(old, True, k, c)}
        can_clear = any(old <= c for old in states)
        assert can_clear == (k*m <= c*(m+1))
        local_cases += 1
    word_cases = possible_cases = 0
    for period in range(2, 9):
        for word in product((1, 3), repeat=period):
            if len(set(word)) == 1:
                continue
            for c in range(1, 4):
                graph = {}
                for phase, old in product(range(period), range(51)):
                    graph[(phase, old)] = [((phase+1) % period, n) for n in
                        out_step(old, word[phase-1] == word[phase], word[phase], c)]
                possible = cyclic_nodes(graph)
                word_cases += 1
                if not possible:
                    continue
                possible_cases += 1
                assert sum(word) <= c*period
                for start in range(period):
                    if word[start-1] == word[start]:
                        continue
                    m = 1
                    while word[(start+m) % period] == word[start]:
                        m += 1
                    assert word[start]*m <= c*(m+1)
    # 达到 m=2 的局部出货周期；同刻清旧货再入新货不可漏计。
    word, trace, old = (3, 3, 1, 1), [], 0
    for phase, k in enumerate(word):
        before = min(old, 2)
        assert old-before == 0 or word[phase-1] == k
        placed = old-before+k
        after = min(placed, 2-before)
        old = placed-after
        trace.append(dict(phase=phase, completed=k, sent=before+after, remaining=old))
    assert old == 0 and [x["remaining"] for x in trace] == [1, 2, 1, 0]
    return dict(local_cases=local_cases, periodic_words_and_ports=word_cases,
                periodic_cases_with_cycle=possible_cases,
                three_sandleaf=dict(demand=9, capacity=8, feasible=False),
                two_sandleaf_periodic_relaxation=trace)


def partition_checks():
    units = ["A1", "A2", "Z1", "Z2", "F1", "F2", "bridge", "seed_split",
             "plant_split1", "plant_split2", "box"]
    # 同一 bridge 单位的 s、p 在独立格，分区时整个单位一并划入。
    edges = [
        ("A1", "bridge", "s", 4), ("bridge", "Z1", "s", 4),
        ("A2", "seed_split", "s", 4), ("seed_split", "Z2", "s", 3),
        ("seed_split", "box", "s", 1),
        ("Z1", "plant_split1", "p", 4), ("plant_split1", "A1", "p", 2),
        ("plant_split1", "F1", "p", 1), ("plant_split1", "box", "p", 1),
        ("Z2", "bridge", "p", 3), ("bridge", "plant_split2", "p", 3),
        ("plant_split2", "A2", "p", 2), ("plant_split2", "F2", "p", 1)]
    batches = {"A1": (2, 0, 0), "A2": (2, 0, 0), "Z1": (0, 4, 0),
               "Z2": (0, 3, 0), "F1": (0, 0, 1), "F2": (0, 0, 1)}
    checked = 0
    for mask in range(1 << len(units)):
        group = {name for i, name in enumerate(units) if mask >> i & 1}
        a, z, f = (sum(batches.get(u, (0, 0, 0))[i] for u in group) for i in range(3))
        incoming, outgoing = defaultdict(int), defaultdict(int)
        for source, target, kind, n in edges:
            if source not in group and target in group:
                incoming[kind] += n
            if source in group and target not in group:
                outgoing[kind] += n
        ws = wp = int("box" in group)
        assert 2*a+incoming["s"] == z+outgoing["s"]+ws
        assert z+incoming["p"] == a+f+outgoing["p"]+wp
        assert a+sum(incoming.values()) == f+sum(outgoing.values())+ws+wp
        checked += 1
    return dict(units=len(units), all_subsets=checked,
                whole_network=dict(A=4, Z=7, F=2, W_s=1, W_p=1),
                seed_only_group=dict(A=2, Z=0, F=0, I_p=2, E_s=4))


@lru_cache(None)
def two_rows(rows, cols):
    assert sum(rows) == sum(cols)
    result = []
    for first in product(*(range(c+1) for c in cols)):
        if sum(first) == rows[0]:
            result.append((first, tuple(c-x for c, x in zip(cols, first))))
    return tuple(result)


def reachable(graph, start):
    seen = {start}
    todo = [start]
    for node in todo:
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def has_regeneration(graph, crusher):
    # 每条正采种转化边 Ap -> As，检查 As 能返回 Ap 且能到粉碎终点。
    for i in range(2):
        raw, seed = f"A{i}p", f"A{i}s"
        if seed in graph.get(raw, ()):
            downstream = reachable(graph, seed)
            if raw in downstream and crusher in downstream:
                # 返回路必须改变 s/p，图中另一种变种边仅为种植。
                return True
    return False


def regeneration_checks():
    cases = crusher_checks = 0
    for a in product(range(3), repeat=2):
        total = sum(a)
        if not total:
            continue
        for z0 in range(2*total+1):
            z = (z0, 2*total-z0)
            for f0 in range(total+1):
                f = (f0, total-f0)
                for seeds in two_rows(tuple(2*x for x in a), z):
                    for plants in two_rows(z, a+f):
                        graph = defaultdict(set)
                        for i in range(2):
                            if a[i]:
                                graph[f"A{i}p"].add(f"A{i}s")
                            if z[i]:
                                graph[f"Z{i}s"].add(f"Z{i}p")
                            for j in range(2):
                                if seeds[i][j]:
                                    graph[f"A{i}s"].add(f"Z{j}s")
                            for j in range(4):
                                if plants[i][j]:
                                    target = f"A{j}p" if j < 2 else f"F{j-2}p"
                                    graph[f"Z{i}p"].add(target)
                        # 另加一个无关的纯植株搬运循环，对粉碎来路没有帮助。
                        graph["R0p"].add("R1p")
                        graph["R1p"].add("R0p")
                        for i in range(2):
                            if f[i]:
                                assert has_regeneration(graph, f"F{i}p")
                                crusher_checks += 1
                        cases += 1
    fake = {"stockp": {"F0p"}, "A0p": {"A0s"}, "A0s": {"Z0s"},
            "Z0s": {"Z0p"}, "Z0p": {"A0p"}}
    assert not has_regeneration(fake, "F0p")
    return dict(balanced_integer_flow_graphs=cases, positive_crushers_checked=crusher_checks,
                range="2 采种、2 种植、2 粉碎；每台采种每周期 0..2 批；逐一枚举所有整数分配",
                unrelated_cycle_negative_control="PASS；库存支线净支出，不能成为循环态")


def tilings(remaining):
    if remaining == 0:
        yield ()
        return
    for tail in tilings(remaining-1):
        yield (("empty", 1),)+tail
    for length in range(2, remaining+1):
        for kind in ("s", "p"):
            for tail in tilings(remaining-length):
                yield ((kind, length),)+tail


def occupancy_checks():
    cases = wraps = 0
    for period in range(2, 9):
        for blocks in tilings(period):
            for shift in range(period):
                occupied = [None]*period
                counts = defaultdict(int)
                position = shift
                for kind, length in blocks:
                    if kind != "empty":
                        counts[kind] += 1
                        if position % period+length > period:
                            wraps += 1
                        for offset in range(length):
                            i = (position+offset) % period
                            assert occupied[i] is None
                            occupied[i] = kind
                    position += length
                for kind in ("s", "p"):
                    # 每个半 tick 的占用积分为 1/2，入格件数须不超过它。
                    integral_twice = occupied.count(kind)
                    assert integral_twice >= 2*counts[kind]
                cases += 1
    # 在制缓存用同一组时长 >=1 tick 的不交叠区间；位置与运输格独立。
    # 全部项目直接以“占用积分/P”相加，不在周期截点丢掉跨界的货。
    recovery = []
    for name, z in [("荞花", 11), ("砂叶", 21)]:
        a = f = z/2
        qs = qp = z
        assert z+qs == a+f+qp == 2*z
        recovery.append(dict(plant=name, z=z, a=a, f=f, Q_s=qs, Q_p=qp,
                             seed_bound=z+qs, plant_bound=a+f+qp))
    return dict(half_tick_periodic_cell_schedules=cases, wrapped_occupancies=wraps,
                periods_in_half_ticks=[2, 8],
                manufacture_interval_check="同一枚举检查每批至少 1 tick 的在制投入占用",
                extra_transport_cell_at_rate_1_over_2="平均下界增加 1/2 件",
                recovery_at_32_planters=recovery)


def main():
    sources = {}
    for relative, expected in EXPECTED.items():
        actual = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
        assert actual == expected, (relative, "输入已改变，应重新核对报告", actual)
        sources[relative] = actual
    result = dict(scope="独立局部复算；一般结论由报告解析证明；非整厂可行性证书", sources=sources)
    for key, function in [("inventory", inventory_checks), ("output_window", window_checks),
                          ("partitions", partition_checks), ("regeneration", regeneration_checks),
                          ("occupancy", occupancy_checks)]:
        result[key] = function()
        print(key+": PASS", flush=True)
    result["status"] = "PASS"
    target = HERE/"verification.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

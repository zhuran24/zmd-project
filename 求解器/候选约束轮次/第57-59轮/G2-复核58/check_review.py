#!/usr/bin/env python3
"""第58轮G2独立局部复算；标准库，无文件写入。

运行：python -B 求解器/候选约束轮次/第57-59轮/G2-复核58/check_review.py
状态图只覆盖其明示的时间格；一般结论的证明见同级复核报告。
"""
from collections import deque
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from itertools import permutations, product
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[4]
SOURCES = (
    "《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt",
    "候选约束.txt", "思路.txt", "求解器/候选约束轮次/第57-59轮/G2-推导.md",
)


def check_balance():
    # 两种原矿分别计数，植物物品不含矿。
    weights = {
        "蓝铁矿": (1, 0), "源矿": (0, 1), "蓝铁块": (1, 0),
        "蓝铁粉末": (1, 0), "源石粉末": (0, 1),
        "致密蓝铁粉末": (2, 0), "致密源石粉末": (0, 2),
        "钢块": (2, 0), "钢制零件": (2, 0), "钢质瓶": (4, 0),
        "高容谷地电池": (20, 30), "精选荞愈胶囊": (40, 0),
    }
    text = (ROOT / SOURCES[0]).read_text()
    recipes = [line.strip() for line in text.splitlines() if " → " in line]

    def mass(side):
        result = [0, 0]
        for term in side.split(" ＋ "):
            number, name = term.split(" ", 1)
            for axis, value in enumerate(weights.get(name, (0, 0))):
                result[axis] += int(number) * value
        return tuple(result)

    for recipe in recipes:
        inputs, rest = recipe.split(" → ")
        outputs = rest.split("，")[0]
        assert mass(inputs) == mass(outputs), recipe
    target = (Fraction(3, 5), Fraction(11, 20))
    ore = (target[0] * 20 + target[1] * 40, target[0] * 30)
    assert ore == (34, 18) and sum(ore) == 52
    # 成品倒推每20tick粉碎的株数，再由零入库的回路守恒得采种、种植。
    buckwheat_crush = target[1] * 10 * 2 / 2
    steel = target[0] * 10 + target[1] * 10 * 2
    sandleaf_crush = (steel + target[0] * 15 + target[1] * 10) / 3
    period20 = {
        "capsules": target[1] * 20, "batteries": target[0] * 20,
        "buckwheat_seed_batches": buckwheat_crush * 20,
        "buckwheat_plant_batches": buckwheat_crush * 40,
        "sandleaf_seed_batches": sandleaf_crush * 20,
        "sandleaf_plant_batches": sandleaf_crush * 40,
    }
    assert list(period20.values()) == [11, 12, 110, 220, 210, 420]
    assert all(value.denominator == 1 for value in period20.values())
    # 种子、植株两条独立守恒式，枚举有限批次数，核对消元。
    solutions = 0
    for a, f, z in product(range(41), range(41), range(81)):
        if 2 * a == z and z == a + f:
            assert a == f and z == 2 * a
            solutions += 1
    # 调试腾空后允许有限入库，但每一件成功入库都改变仓库存量。
    stock = 79998
    deltas = []
    for _ in range(4):
        before = stock
        stock += min(1, 80000 - stock)
        deltas.append(stock - before)
    assert deltas == [1, 1, 0, 0]
    return {"recipes": len(recipes), "ore_per_tick": list(ore),
            "plant_balance_solutions": solutions, "finite_warehouse_fill": deltas,
            "period_20_at_required_product_flow": period20}


def check_transfer():
    cases = 0
    for slots in product((0, 1, 49, 50), repeat=6):
        for free in (0, 1, 49, 50, 51, 299, 300, 79999, 80000):
            remaining = free
            sent = 0
            for n in slots:
                part = min(n, remaining)
                sent += part
                remaining -= part
            assert sent == min(sum(slots), free)
            assert (sent == 0) == (sum(slots) == 0 or free == 0)
            cases += 1
    # 所有整数判定排列及1/4 tick格上的全部传输相位。
    # 输入、输出各1件/tick；箱内先有1件，避免初次先取后存缺货。
    phase_cases = 0
    for order in permutations("IOT"):
        rank = {event: i for i, event in enumerate(order)}
        for phase4 in range(20):
            events = [(Fraction(t), e) for t in range(20) for e in "IO"]
            events += [(Fraction(phase4, 4) + 5 * t, "T") for t in range(4)]
            events.sort(key=lambda pair: (pair[0], rank[pair[1]]))
            stock, box, wireless, physical = 80000, 1, 0, 0
            for _, e in events:
                if e == "I":
                    assert box < 50
                    box += 1
                elif e == "O":
                    assert box > 0
                    box -= 1
                    physical += 1
                else:
                    sent = min(box, 80000 - stock)
                    stock += sent
                    box -= sent
                    wireless += sent
            assert (stock, box, wireless, physical) == (80000, 1, 0, 20)
            phase_cases += 1
    return {"split_slot_cases": cases, "full_warehouse_order_phase_cases": phase_cases,
            "physical_output_per_case": 20, "wireless_output_per_case": 0}


def gate_graph(k, q):
    # 状态为当前判定前的(窗口剩余时间格, 已收件数, 再收件需等待时间格)。
    start = (0, 0, 0)
    states, index, edges = [start], {start: 0}, []
    queue = deque([start])
    while queue:
        state = queue.popleft()
        source = index[state]
        timer0, used0, wait0 = state
        for take in (0, 1):
            if take and (wait0 > 0 or (timer0 > 0 and used0 >= k)):
                continue
            timer, used, wait = state
            if take:
                if timer == 0:
                    timer, used = 5 * q, 0
                used += 1
                wait = q
            expired_count = used if timer == 1 else None
            timer = max(0, timer - 1)
            wait = max(0, wait - 1)
            if timer == 0:
                used = 0
            target = (timer, used, wait)
            if target not in index:
                index[target] = len(states)
                states.append(target)
                queue.append(target)
            # 一步长1/q，cost=q*(k*时间-5*件数)。
            edges.append((source, index[target], k - 5 * q * take,
                          take, expired_count))
    # 非负环代价 <=> 没有平均速率大于k/5的循环。
    distances = [0] * len(states)
    for _ in range(len(states)):
        changed = False
        for u, v, cost, _, _ in edges:
            if distances[v] > distances[u] + cost:
                distances[v] = distances[u] + cost
                changed = True
        if not changed:
            break
    assert not changed, ("rate_exceeds_bound", k, q)
    zero_edges = [edge for edge in edges if distances[edge[1]] == distances[edge[0]] + edge[2]]
    adjacent = [[] for _ in states]
    for u, v, *_ in zero_edges:
        adjacent[u].append(v)

    @lru_cache(None)
    def reachable(u):
        seen, todo = {u}, [u]
        while todo:
            for v in adjacent[todo.pop()]:
                if v not in seen:
                    seen.add(v)
                    todo.append(v)
        return frozenset(seen)

    cycle_edges = 0
    for u, v, _, take, expired_count in zero_edges:
        if u not in reachable(v):
            continue
        cycle_edges += 1
        # 在取等环内，任何到期窗口都满额，窗口已过期时立即收下一件。
        assert expired_count is None or expired_count == k, (k, q, states[u])
        assert states[u][0] > 0 or take == 1, (k, q, states[u])
    assert cycle_edges > 0
    return {"k": k, "time_grid": f"1/{q}", "states": len(states),
            "edges": len(edges), "saturated_cycle_edges": cycle_edges,
            "counterexamples": 0}


def check_gate():
    graphs = [gate_graph(k, q) for q in (1, 2, 3, 4) for k in range(1, 6)]
    arrivals = (0, 4, 5, 6)
    windows = []
    for t in arrivals:
        if not windows or t >= windows[-1][0] + 5:
            windows.append([t, 0])
        windows[-1][1] += 1
    assert windows == [[0, 2], [5, 2]]
    assert sum(4 <= t < 9 for t in arrivals) == 3
    # 在周期20中少收一件、延后一整tick的两个严格亏损例子。
    for k in range(1, 6):
        assert Fraction(4 * k - 1, 20) < Fraction(k, 5)
        assert Fraction(4 * k, 21) < Fraction(k, 5)
    return {"graphs": graphs, "sliding_window_count": 3,
            "self_started_window_counts": [2, 2]}


EMPTY = ("", 0)


def put(box, item):
    for i, (name, count) in enumerate(box):
        if count == 0 or (name == item and count < 50):
            answer = list(box)
            answer[i] = (item, count + 1)
            return tuple(answer), i
    return box, None


def take(box, accepted):
    for i, (name, count) in enumerate(box):
        if count:
            if name not in accepted:
                return box, None
            answer = list(box)
            answer[i] = (name, count - 1) if count > 1 else EMPTY
            return tuple(answer), i
    return box, None


def check_blocked_tail():
    alphabet = (EMPTY, ("A", 1), ("A", 50), ("B", 1), ("B", 50))
    states = transitions = 0
    for box in product(alphabet, repeat=6):
        blocked = [j for j, (name, _) in enumerate(box) if name == "A"]
        for j in blocked:
            states += 1
            for item in ("A", "B", "C"):
                after, _ = put(box, item)
                assert after[j][0] == "A" and after[j][1] >= box[j][1]
                assert all(after[i][1] >= box[i][1] for i in range(j, 6))
                transitions += 1
            for accepted in ({"B"}, {"C"}, {"B", "C"}):
                after, taken = take(box, accepted)
                assert after[j:] == box[j:]
                assert taken is None or taken < j
                transitions += 1
    # 周期例子：第2格A不动，前格B持续通过；改变成第1格A则B出不去。
    initial = (("B", 1), ("A", 1), EMPTY, EMPTY, EMPTY, EMPTY)
    box = initial
    for _ in range(100):
        box, taken = take(box, {"B"})
        assert taken == 0
        box, stored = put(box, "B")
        assert stored == 0 and box == initial
    head_block = (("A", 1), ("B", 50), EMPTY, EMPTY, EMPTY, EMPTY)
    assert take(head_block, {"B"}) == (head_block, None)
    return {"box_blocker_pairs": states, "checked_transitions": transitions,
            "prefix_period_repetitions": 100, "capacities_by_j": [50 * j for j in range(6)]}


def check_full_speed_head():
    cases = 0
    maxima = {}
    # 每口在长1tick半开区间至多成功一次；三存货口各至多进一件。
    # 任意相位、同刻排列都落在这些事件排列中。允许的排列比固定轮询更宽。
    for c in range(1, 4):
        for cx in range(c):
            maximum = 0
            for n in sorted({cx + 1, 50}):
                initial = (("X", n), ("Y", 50), ("Z", 50), EMPTY, EMPTY, EMPTY)
                actions = tuple(("I", i) for i in range(3)) + tuple(("O", i) for i in range(c))
                for incoming in product("XYZ", repeat=3):
                    for order in permutations(actions):
                        box, output = initial, 0
                        for kind, index in order:
                            if kind == "I":
                                box, _ = put(box, incoming[index])
                            else:
                                accepts = {"X", "Y", "Z"} if index < cx else {"Y", "Z"}
                                box, slot = take(box, accepts)
                                if slot is not None:
                                    assert index < cx
                                    output += 1
                        assert box[0][0] == "X" and box[0][1] > 0
                        assert output <= cx < c
                        maximum = max(maximum, output)
                        cases += 1
            maxima[f"c={c},cx={cx}"] = maximum
    # 无进货时遍历每一个合法超界存量，而不只检查阈值与50。
    quantity_cases = 0
    for c in range(1, 4):
        for cx in range(c):
            for n in range(cx + 1, 51):
                for order in permutations(range(c)):
                    box = (("X", n), ("Y", 50), EMPTY, EMPTY, EMPTY, EMPTY)
                    for index in order:
                        accepts = {"X", "Y"} if index < cx else {"Y"}
                        box, slot = take(box, accepts)
                        assert slot is None or index < cx
                    assert box[0][0] == "X" and box[0][1] > 0
                    quantity_cases += 1
    return {"arrival_departure_interleavings": cases,
            "all_excess_quantities_without_arrivals": quantity_cases,
            "maximum_outputs": maxima, "counterexamples": 0}


def main():
    result = {
        "status": "PASS",
        "source_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        "balance": check_balance(),
        "transfer": check_transfer(),
        "gate": check_gate(),
        "blocked_tail": check_blocked_tail(),
        "full_speed_head": check_full_speed_head(),
    }
    # Fraction只出现在已经核对为整数的矿耗中。
    print(json.dumps(result, ensure_ascii=False, indent=2, default=lambda x: int(x)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""第57轮 G2 局部规则复算。只读正式文件，只向标准输出写结果。

枚举的是准入口的整数时刻周期序列和箱体局部事件；不模拟全厂，
不证明调试可达性，也不把局部例子当作达标布局。
"""
from collections import Counter
from hashlib import sha256
from itertools import permutations, product
from pathlib import Path
import json


def gate_step(state, receive, k):
    """state 在整数时刻判定前；remaining=0 表示下一件重新起窗。"""
    remaining, used = state
    started = False
    if receive:
        if remaining == 0:
            remaining, used, started = 5, 1, True
        elif used < k:
            used += 1
        else:
            return None
    remaining = max(0, remaining - 1)
    if remaining == 0:
        used = 0
    return (remaining, used), started


def check_gate_cycles(period=10):
    result = []
    for k in range(1, 6):
        valid = saturated = 0
        states = [(0, 0)] + [(r, u) for r in range(1, 5) for u in range(1, k + 1)]
        for bits in product((0, 1), repeat=period):
            for initial in states:
                state, starts = initial, []
                for t, receive in enumerate(bits):
                    step = gate_step(state, receive, k)
                    if step is None:
                        break
                    state, started = step
                    if started:
                        starts.append(t)
                else:
                    if state != initial:
                        continue
                    valid += 1
                    n = sum(bits)
                    assert 5 * n <= k * period
                    if 5 * n == k * period:
                        saturated += 1
                        assert starts
                        gaps = [(starts[(j + 1) % len(starts)] - s) % period
                                or period for j, s in enumerate(starts)]
                        assert all(gap == 5 for gap in gaps)
                        assert all(sum(bits[(s + d) % period] for d in range(5)) == k
                                   for s in starts)
        result.append({"k": k, "period": period,
                       "legal_periodic_state_sequences": valid,
                       "saturated_sequences": saturated})
    return result


def put(box, item):
    for i, slot in enumerate(box):
        if slot is None or (slot[0] == item and slot[1] < 50):
            box[i] = (item, 1 if slot is None else slot[1] + 1)
            return True
    return False


def take(box, allowed=None):
    for i, slot in enumerate(box):
        if slot is not None:
            item, amount = slot
            if allowed is not None and item not in allowed:
                return None  # 不能跳过不合身份的小号格。
            box[i] = None if amount == 1 else (item, amount - 1)
            return item
    return None


def transfer(box, warehouse):
    moved = Counter()
    for i, slot in enumerate(box):
        if slot is None:
            continue
        item, amount = slot
        send = min(amount, 80000 - warehouse.get(item, 0))
        warehouse[item] = warehouse.get(item, 0) + send
        moved[item] += send
        box[i] = None if send == amount else (item, amount - send)
    return sum(moved.values())


def check_boxes():
    # 六种来料、仅六件库存，也能因同种重复占格而拒收。
    fragmented = [None] * 6
    assert put(fragmented, "A") and put(fragmented, "B")
    assert take(fragmented) == "A"
    for item in "BCDEF":
        assert put(fragmented, item)
    assert not put(fragmented, "A")
    assert sum(s[1] for s in fragmented) == 6

    # 不可取走的第2格封住尾部，但第1格仍能周转。
    pinned = [("B", 1), ("A", 1), ("C", 50), None, None, None]
    initial = list(pinned)
    for _ in range(100):
        assert take(pinned, {"B"}) == "B"
        assert put(pinned, "B")
        assert pinned == initial
    pinned_first = [("A", 1), ("B", 50), None, None, None, None]
    assert take(pinned_first, {"B"}) is None

    # c=3，只有两口接受A；1号格有3个A时，任意出货次序最多出2件。
    head_counts = []
    allowed = ({"A"}, {"A"}, {"B"})
    for order in permutations(range(3)):
        box = [("A", 3), ("B", 1), None, None, None, None]
        n = sum(take(box, allowed[i]) is not None for i in order)
        assert n == 2
        head_counts.append(n)

    # 仓库钢块已满且无钢块出库；保持固定的三事件次序，传输均为零。
    full_warehouse_cases = []
    for order in permutations(("in", "out", "transfer")):
        box = [("steel", 2), None, None, None, None, None]
        warehouse = {"steel": 80000}
        sent = taken = 0
        for tick in range(20):
            for event in order:
                if event == "in":
                    assert put(box, "steel")
                elif event == "out":
                    assert take(box) == "steel"
                    taken += 1
                elif tick % 5 == 0:
                    sent += transfer(box, warehouse)
            assert box[0] == ("steel", 2)
        assert sent == 0 and taken == 20 and warehouse["steel"] == 80000
        full_warehouse_cases.append({"fixed_order": order, "wireless": sent,
                                     "physical_out": taken})
    return {"fragmented_slots": fragmented,
            "pinned_slot_prefix_cycles": 100,
            "head_order_cases": len(head_counts),
            "head_max_departures": max(head_counts),
            "full_warehouse_fixed_orders": full_warehouse_cases}


def sliding_window_example():
    arrivals, k, state = {0, 4, 5, 6}, 2, (0, 0)
    for t in range(10):
        step = gate_step(state, t in arrivals, k)
        assert step is not None
        state = step[0]
    in_window = [t for t in sorted(arrivals) if 4 <= t < 9]
    assert len(in_window) == 3 > k
    return {"k": k, "arrivals": sorted(arrivals),
            "window": "[4,9)", "arrivals_in_window": in_window}


def main():
    root = Path(__file__).resolve().parents[4]
    files = ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt",
             "候选约束.txt", "思路.txt"]
    hashes = {name: sha256((root / name).read_bytes()).hexdigest() for name in files}
    print(json.dumps({"scope": "local_mechanisms_only", "source_sha256": hashes,
                      "gate_cycles": check_gate_cycles(),
                      "self_started_not_sliding": sliding_window_example(),
                      "boxes": check_boxes(), "status": "PASS"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""B 席独立复算；只输出结果，不写文件，不调用原推导脚本。"""
from collections import Counter
from itertools import product
from math import gcd


def check_stock_bounds():
    checked = 0
    for a, b in ((2, 1), (10, 15), (10, 10)):
        low = b * (a - 1) - 50 * a
        high = 50 * b - a * (b - 1)
        for x, y in product(range(51), repeat=2):
            z = b * x - a * y
            if x == 50 and y < b:
                assert z >= high
            if y == 50 and x < a:
                assert z <= low
            if low < z < high:
                assert not (x == 50 and y < b)
                assert not (y == 50 and x < a)
            checked += 1
        print(f"配方 ({a},{b})：严格区间 ({low},{high})")
    print(f"库存边界复算：{checked} 个状态")
    for word in ("AAB", "ABA", "BAA"):
        z = -50
        seen = [z]
        for letter in word * 100:
            z += 1 if letter == "A" else -2
            seen.append(z)
        assert min(seen) > -99 and max(seen) < 50
        assert z == -50
        print(f"{word}：Z 范围 [{min(seen)},{max(seen)}]")


def check_coprime():
    checked = 0
    for length in range(1, 9):
        for k in range(1, 7):
            if gcd(length, k) != 1:
                continue
            for word in product("AB", repeat=length):
                for start in range(k):
                    received = [Counter() for _ in range(k)]
                    for i in range(length * k):
                        received[(start + i) % k][word[i % length]] += 1
                    assert all(row == Counter(word) for row in received)
                    checked += 1
    print(f"互质分料算术复算：{checked} 个清单/口数/起点组合")


def dense_node(external=True, end=40):
    # M 为汇流器，T 为其下一格，B 为分流器另一出口首格。
    # 元组为 (货源标签, 收件时刻)，每格最多一件，至少滞留 1 tick。
    m = t = branch = None
    pointer = "B"
    bottles, powder = 50, 0
    choices = []
    snapshots = {}
    main_in = extra_in = batches = 0
    trace = []
    for now in range(end + 1):
        phase = now % 20
        events = []
        if branch is not None and now - branch[1] >= 1:
            branch = None
        powder += {11: 3, 12: 3, 13: 3, 14: 1}.get(phase, 0)
        if phase == 14:
            assert bottles >= 10 and powder >= 10
            bottles -= 10
            powder -= 10
            batches += 1
            events.append("灌装开工，瓶格减10")
        if t is not None and now - t[1] >= 1 and bottles < 50:
            bottles += 1
            main_in += 1
            events.append(f"T送走{t[0]}")
            t = None
        if m is not None and now - m[1] >= 1 and t is None:
            events.append(f"M向T送{m[0]}")
            t, m = (m[0], now), None
        if external and phase == 1:
            assert m is None
            m = ("外来", now)
            events.append("外来进入M")
        if phase in (0, 4, 8, 12, 16):
            assert m is None or m[0] != "外来"
            order = (pointer, "M" if pointer == "B" else "B")
            for target in order:
                if (target == "M" and m is None) or (target == "B" and branch is None):
                    if target == "M":
                        m = ("分流器", now)
                    else:
                        branch = ("分流器", now)
                    pointer = "B" if target == "M" else "M"
                    choices.append((now, target))
                    events.append(f"分流器走{target}")
                    break
            else:
                raise AssertionError("分流器意外无出口")
        if now > 0 and (phase == 0 or 14 <= phase <= 19):
            assert bottles < 50
            bottles += 1
            extra_in += 1
        assert 0 <= bottles <= 50 and 0 <= powder <= 50
        def relative(cell):
            return None if cell is None else (cell[0], now - cell[1])
        snapshots[now] = (relative(m), relative(t), relative(branch), pointer, bottles, powder)
        if events:
            trace.append((now, events))
    if external:
        assert snapshots[0] == snapshots[20] == snapshots[40]
        assert [target for now, target in choices if now < 20] == ["B", "M", "B", "B", "M"]
        assert main_in == 6 and extra_in == 14 and batches == 2
    return choices, trace


if __name__ == "__main__":
    check_stock_bounds()
    check_coprime()
    choices, trace = dense_node()
    baseline, _ = dense_node(external=False, end=12)
    assert dict(choices)[12] == "B" and dict(baseline)[12] == "M"
    print("密集结点反例：20 tick 状态复原；有外来时第12 tick走B，无外来时走M")
    for now, events in trace:
        if now < 20:
            print(now, "；".join(events))
    arrivals = tuple(range(5))
    assert all(y - x >= 1 for x, y in zip(arrivals, arrivals[1:]))
    assert sum(0 <= x < 5 for x in arrivals) == 5
    print("准入口：0、1、2、3、4 收五件，第4 tick额度已用尽")

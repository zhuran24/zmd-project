#!/usr/bin/env python3
"""A 席报告的算术与局部事件账复算；不是整厂模拟器。只读文件，只向终端输出。"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {
    "《明日方舟：终末地》游戏规则.txt": "52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f",
    "求解器/候选约束轮次/第57-59轮/充分条件汇总.md": "7f46b7855aabb7d60334e9a9c69f3861d0e227fd5c9e0ae37b75919bd01ddf97",
}


def splitter_run(external):
    """固定顺序：B/C 出货，M 到 C，D 出货，外来货进 M。

    C 是每窗口限 1 件的准入口，采用窗口结束可再收货的运行。
    这是报告明确列出的一个允许实例，不能用于证明所有阻断都会恢复。
    D 的边界待出时刻为 10n+1、10n+3、10n+4；对应提前 1 tick 入 D。
    """
    m = ("E", -1) if external else None
    b = c = None
    window = None
    pointer = 0  # 0=M，1=B
    events = []
    snapshots = {}
    for t in range(41):
        if b is not None and t - b[1] >= 1:
            b = None
        if c is not None and t - c[1] >= 1:
            c = None
        if window is not None and t >= window + 5:
            window = None
        if m is not None and t - m[1] >= 1 and c is None and window is None:
            c = (m[0], t)
            m = None
            window = t
            events.append([t, "M→C", c[0]])
        if t % 10 in (1, 3, 4):
            for offset in (0, 1):
                j = (pointer + offset) % 2
                if (m if j == 0 else b) is None:
                    if j == 0:
                        m = ("D", t)
                    else:
                        b = ("D", t)
                    pointer = (j + 1) % 2
                    events.append([t, "D→" + ("M" if j == 0 else "B"), "D"])
                    break
            else:
                raise AssertionError("D 的边界待出事件被堵，须另建队列")
        if external and t % 10 == 9:
            assert m is None
            m = ("E", t)
            events.append([t, "E→M", "E"])
        if t in (0, 20, 40):
            def state(item):
                return None if item is None else (item[0], min(t - item[1], 1))
            snapshots[t] = (state(m), state(b), state(c), pointer,
                            None if window is None else window + 5 - t)
    assert snapshots[0] == snapshots[20] == snapshots[40]
    one_period = [e for e in events if 0 <= e[0] < 20]
    count = {name: sum(e[1] == name for e in one_period)
             for name in ("D→M", "D→B", "E→M", "M→C")}
    return {"20_tick_counts": count, "events": one_period,
            "periodic_local_state": True}


def arithmetic():
    intervals = []
    for name, a, b in (("研磨", 2, 1), ("封装", 10, 15), ("灌装", 10, 10)):
        low = b * (a - 1) - 50 * a
        high = 50 * b - a * (b - 1)
        inside_deadlocks = 0
        for x in range(51):
            for y in range(51):
                z = b * x - a * y
                deadlock = (x == 50 and y < b) or (y == 50 and x < a)
                inside_deadlocks += bool(deadlock and low < z < high)
        assert inside_deadlocks == 0
        intervals.append([name, a, b, low, high, 51 * 51, inside_deadlocks])
    rotations = {}
    for word in ("AAB", "ABA", "BAA"):
        z = 0
        values = [z]
        for letter in word:
            z += 1 if letter == "A" else -2
            values.append(z)
        assert z == 0
        rotations[word] = values
    x = y = 50
    batches = accepted_a = 0
    word = "A" * 102 + "B" * 51
    for letter in word:
        while x >= 2 and y >= 1:
            x -= 2
            y -= 1
            batches += 1
        if (x if letter == "A" else y) == 50:
            break
        if letter == "A":
            x += 1
            accepted_a += 1
        else:
            y += 1
    assert (x, y, batches, accepted_a) == (50, 0, 50, 100)
    return {"intervals": intervals, "AAB_prefix_deviations": rotations,
            "A102B51": {"stock": [x, y], "batches": batches,
                         "accepted_A": accepted_a, "next_A_index": accepted_a + 1}}


def main():
    hashes = {}
    for name, expected in EXPECTED.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected, (name, "依据版本改变", actual)
        hashes[name] = actual
    constraint_lines = (ROOT / "求解约束.txt").read_text().splitlines()
    numbered = [(i, line.split("：", 1)[0])
                for i, line in enumerate(constraint_lines, 1)
                if i >= 3 and line and not line[0].isspace()
                and "：" in line and line.split("：", 1)[1].strip()]
    assert len(numbered) == 72, len(numbered)
    ext = splitter_run(True)
    absent = splitter_run(False)
    assert ext["20_tick_counts"]["D→M"] == 2
    assert ext["20_tick_counts"]["D→B"] == 4
    assert absent["20_tick_counts"]["D→M"] == 3
    assert absent["20_tick_counts"]["D→B"] == 3
    report = Path(__file__).with_name("充分复核-A.md").read_text()
    headings = re.findall(r"^### (G[1-4]-\d+)", report, re.M)
    expected_headings = [f"G{group}-{item}" for group, size in ((1, 4), (2, 5), (3, 4), (4, 4))
                         for item in range(1, size + 1)]
    assert headings == expected_headings, headings
    verdicts = re.findall(r"^\*\*判定：(未否证|修正|否证)。\*\*", report, re.M)
    assert len(verdicts) == 17 and verdicts.count("未否证") == 15 and verdicts.count("修正") == 2
    print(json.dumps({"sha256": hashes, "constraints": len(numbered),
                      "report_verdicts": {"未否证": 15, "修正": 2, "否证": 0},
                      "arithmetic": arithmetic(),
                      "with_external": ext, "without_external": absent,
                      "G2_1_window": {"half_open": "[0,5)", "accept_times": [0, 1, 2, 3, 4],
                                      "quota_exhausted_at": 4}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

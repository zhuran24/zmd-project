#!/usr/bin/env python3
"""复算报告中的局部几何、算术和箱体接口模型；不是全厂游戏模拟器。"""
from pathlib import Path
from fractions import Fraction
from itertools import permutations
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPECTED = {
    "《明日方舟：终末地》游戏规则.txt": "52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f",
    "候选简化.txt": "e1653f6c818c925454b8576c488bcb3aa8a2d7d2ebcd32769840446e3b0872ca",
}
DIR = {"E": (1, 0), "W": (-1, 0), "N": (0, 1), "S": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}
units = []


def unit(name, kind, x, y, w, h, ports):
    units.append(dict(name=name, kind=kind, x=x, y=y, w=w, h=h, ports=ports))


def belt(name, x, y, incoming, outgoing, kind="运输"):
    unit(name, kind, x, y, 1, 1,
         [(x, y, incoming, "in"), (x, y, outgoing, "out")])


unit("源矿取货口", "仓库取货口", 0, 3, 1, 3, [(0, 4, "E", "out")])
unit("蓝铁矿取货口", "仓库取货口", 0, 9, 1, 3, [(0, 10, "E", "out")])
for name, y in [("源矿粉碎机", 1), ("蓝铁矿精炼炉", 5)]:
    unit(name, "制造", 6, y, 3, 3,
         [(6, k, "W", "in") for k in range(y, y + 3)]
         + [(8, k, "E", "out") for k in range(y, y + 3)])
unit("供电桩", "供电", 10, 4, 2, 2, [])
belt("源矿首带", 1, 4, "W", "E")
unit("源矿分流器", "运输", 2, 4, 1, 1,
     [(2, 4, "W", "in")] + [(2, 4, d, "out") for d in ["E", "S", "N"]])
for name, x, y, di, do in [
    ("误料前带", 3, 4, "W", "E"),
    ("误料转北", 5, 4, "W", "N"),
    ("误料入炉", 5, 5, "S", "E"),
    ("源矿向南", 2, 3, "N", "S"),
    ("源矿转东", 2, 2, "N", "E"),
    ("源矿中带一", 3, 2, "W", "E"),
    ("源矿中带二", 4, 2, "W", "E"),
    ("源矿入粉碎机", 5, 2, "W", "E"),
    ("源石粉末交接口", 9, 2, "W", "E"),
    ("蓝铁块交接口", 9, 6, "W", "E"),
]:
    belt(name, x, y, di, do)
belt("一次性源矿准入口", 4, 4, "W", "E")
for x in range(1, 6):
    belt(f"蓝铁矿横带{x}", x, 10, "W", "E" if x < 5 else "S")
belt("蓝铁矿竖带9", 5, 9, "N", "S")
belt("蓝铁矿竖带8", 5, 8, "N", "S")
belt("蓝铁矿入炉", 5, 7, "N", "E")

occupied = {}
for u in units:
    for x in range(u["x"], u["x"] + u["w"]):
        for y in range(u["y"], u["y"] + u["h"]):
            assert 0 <= x < 70 and 0 <= y < 70
            assert (x, y) not in occupied, ((x, y), occupied.get((x, y)), u["name"])
            occupied[x, y] = u["name"]

ports = {(x, y, d): (u, role) for u in units for x, y, d, role in u["ports"]}
edges = set()
for u in units:
    for x, y, d, role in u["ports"]:
        if role != "out":
            continue
        dx, dy = DIR[d]
        target = ports.get((x + dx, y + dy, OPP[d]))
        if target is not None and target[1] == "in":
            v = target[0]
            if "运输" in [u["kind"], v["kind"]]:
                edges.add((u["name"], v["name"]))

paths = [
    ["源矿取货口", "源矿首带", "源矿分流器", "误料前带", "一次性源矿准入口", "误料转北", "误料入炉", "蓝铁矿精炼炉"],
    ["源矿分流器", "源矿向南", "源矿转东", "源矿中带一", "源矿中带二", "源矿入粉碎机", "源矿粉碎机", "源石粉末交接口"],
    ["蓝铁矿取货口"] + [f"蓝铁矿横带{x}" for x in range(1, 6)]
    + ["蓝铁矿竖带9", "蓝铁矿竖带8", "蓝铁矿入炉", "蓝铁矿精炼炉", "蓝铁块交接口"],
]
expected_edges = {e for p in paths for e in zip(p, p[1:])}
assert edges == expected_edges, (edges - expected_edges, expected_edges - edges)
for name in ["源矿粉碎机", "蓝铁矿精炼炉"]:
    u = next(u for u in units if u["name"] == name)
    # 供电桩中心 (11,5)，覆盖 [5,17]×[-1,11]，只需和机器有交集。
    assert u["x"] < 17 and u["x"] + u["w"] > 5
    assert u["y"] < 11 and u["y"] + u["h"] > -1
for name in ["源矿取货口", "蓝铁矿取货口"]:
    u = next(u for u in units if u["name"] == name)
    assert u["y"] % 3 == 0  # 可属于左边唯一空格在 y=69 的 23 口排法。

# 2A+B 机器。此处只检验给定成功入货次序与库存的相容性。
# while 允许立即尽量消费，是库存松弛模型，不是制造时间模拟。
# 不能据此认定真实布局会生成该次序。
def accept_word(a, b, word):
    batches = 0
    for pos, item in enumerate(word, 1):
        while a >= 2 and b >= 1:
            a -= 2
            b -= 1
            batches += 1
        if (a if item == "A" else b) == 50:
            return dict(blocked_at=pos, a=a, b=b, batches=batches)
        a += item == "A"
        b += item == "B"
    while a >= 2 and b >= 1:
        a -= 2
        b -= 1
        batches += 1
    return dict(blocked_at=None, a=a, b=b, batches=batches)

word = "A" * 102 + "B" * 51
mixed_full = accept_word(50, 50, word)
mixed_low = accept_word(0, 50, word)
assert mixed_full == dict(blocked_at=101, a=50, b=0, batches=50)
assert mixed_low == dict(blocked_at=None, a=0, b=50, batches=51)

# 箱体接口模型：X 入、X 出各恰每 tick 一件，P 每 5 tick 一件，
# 传输每 5 tick 一次且仅仓库 P 有余量。枚举固定判定次序及两个相位。
# 原游戏到这组接口假设的供货证明不在这个枚举程序内。
def box_run(full, order, phase_p, phase_send):
    slots = [["X", 50] for _ in range(6)] if full else [["X", 25]] + [[None, 0] for _ in range(5)]
    seen = {}
    delivered = accepted = 0
    for tick in range(100):
        key = (tick % 5, tuple(tuple(s) for s in slots))
        if key in seen:
            t0, d0, a0 = seen[key]
            return dict(period=tick-t0, delivered=delivered-d0, accepted=accepted-a0,
                        slots=slots, steady_rate=str(Fraction(delivered-d0, tick-t0)))
        seen[key] = (tick, delivered, accepted)
        pending_x = False
        for event in order:
            if event == "X入":
                pending_x = True
            elif event == "X出":
                s = next((s for s in slots if s[1]), None)
                if s is not None and s[0] == "X":
                    s[1] -= 1
                    if not s[1]:
                        s[0] = None
            elif event == "P入" and tick % 5 == phase_p:
                for s in slots:
                    if s[1] == 0 or (s[0] == "P" and s[1] < 50):
                        s[0], s[1] = "P", s[1] + 1
                        accepted += 1
                        break
            elif event == "传输" and tick % 5 == phase_send:
                for s in slots:
                    if s[0] == "P":
                        delivered += s[1]
                        s[0], s[1] = None, 0
            # 已到箱口的 X 在出现空位后继续尝试，不能丢弃被挡住的物品。
            if pending_x:
                for s in slots:
                    if s[1] == 0 or (s[0] == "X" and s[1] < 50):
                        s[0], s[1] = "X", s[1] + 1
                        pending_x = False
                        break
        assert not pending_x
        if not full:
            assert 24 <= slots[0][1] <= 26 and slots[0][0] == "X"
            assert not any(s[0] == "X" for s in slots[1:])
    raise AssertionError("未找到重复状态")

box_cases = []
for order in permutations(["X入", "X出", "P入", "传输"]):
    for pp in range(5):
        for ps in range(5):
            bad = box_run(True, order, pp, ps)
            good = box_run(False, order, pp, ps)
            assert bad["steady_rate"] == "0"
            assert good["steady_rate"] == "1/5"
            box_cases.append(dict(order=order, phase_p=pp, phase_send=ps, bad=bad, good=good))

actual = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in EXPECTED}
assert actual == EXPECTED, actual
# 小标题也带冒号，正式条目按下一行为“据：”计数。
lines = (ROOT / "求解约束.txt").read_text().splitlines()
formal_count = sum(line.lstrip().startswith("据：") for line in lines)
assert formal_count == 72
result = {
    "范围": "局部几何、精确算术、明示接口下的箱体离散模型；不是全厂状态覆盖证书",
    "原文件sha256": actual,
    "约束条数": formal_count,
    "局部占格数": len(occupied),
    "局部单位数": len(units),
    "运输单位数": sum(u["kind"] == "运输" for u in units),
    "自动通道数": len(edges),
    "无多余自动通道": True,
    "单位": units,
    "自动通道": sorted(edges),
    "混料全满": mixed_full,
    "混料低库存": mixed_low,
    "混料周期平均批次每入货事件": str(Fraction(51, 153)),
    "蓝铁矿少一口且电池达标时胶囊上界": str((Fraction(33) - 20 * Fraction(3, 5)) / 40),
    "上述胶囊每30tick上界": str(30 * (Fraction(33) - 20 * Fraction(3, 5)) / 40),
    "箱体模型枚举数": len(box_cases),
    "箱体模型枚举": box_cases,
}
(HERE / "复算结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k not in ["单位", "自动通道", "箱体模型枚举"]}, ensure_ascii=False, indent=2))

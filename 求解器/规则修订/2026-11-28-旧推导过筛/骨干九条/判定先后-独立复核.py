from fractions import Fraction
from math import comb
from pathlib import Path

root = Path(__file__).resolve().parents[4]
rules = (root / "《明日方舟：终末地》游戏规则.txt").read_text().splitlines()
task = (root / "求解任务.txt").read_text().splitlines()
deps = "判定顺序、输入判定、移动判定、轮询、元件轮询、非运输单位轮询、可移动物品、蓝图、接通、次序、组、级别、存货/取货物品格、缓存格、制造、端口、通道、协议储存箱、需电功能、传输、建造方式、调试期、离线、零干预运行、循环态、目标".split("、")
assert all(any(line.strip().partition("：")[0] == name for line in rules + task) for name in deps)
phases = [line.strip() for line in rules[51:57]]
assert all(s.startswith(f"{i}.") for i, s in enumerate(phases, 1))
events = [(step, phase, description) for step in (0, 1) for phase, description in enumerate(phases, 1)]
finished = next(i for i, (_, _, s) in enumerate(events) if "同时进行结束制造判定" in s)
print("结束制造后首次本机对外移动", next(e[:2] for e in events[finished+1:] if "非运输单位按建成" in e[2]))
# 单独选出直连汇流器的端口，其余端口选任一子集接非汇流器。
counts = [0] * 4
for m in range(4):
    choices = comb(3, m)
    counts[m] += choices
    if m < 3:
        counts[m+1] += choices * (2**(3-m) - 1)
print("接法类数", counts, "总数", sum(counts))
print("无线入库", [min(2 + 1 - m, 80000) for m in range(4)])
print("每 tick 达标件数", Fraction(18, 30), Fraction(33, 2*30))

from collections import Counter
from fractions import Fraction
from itertools import product
from pathlib import Path
import re

root = Path(__file__).resolve().parents[4]
rules = (root / "《明日方舟：终末地》游戏规则.txt").read_text()
task = (root / "求解任务.txt").read_text()
stages = re.findall(r"^\s+(\d+)\. (.+)$", rules.split("判定顺序：")[1].split("输入判定：")[0], re.M)
print("阶段", [int(n) for n, _ in stages])
events = [(step, n, name) for step in range(2) for n, name in stages]
end = next(i for i, (_, _, s) in enumerate(events) if "同时进行结束制造" in s)
print("首次后续出货", next((t, n) for t, n, s in events[end+1:] if s.startswith("非运输单位")))
width = int(re.search(r"协议储存箱：大小 (\d+)×", rules)[1])
counts, groups = Counter(), Counter()
for ports in product(("空", "汇", "其余"), repeat=width):
    c = width - ports.count("空")
    g = ports.count("汇") + ("其余" in ports)
    counts[c] += 1
    groups[g] += 1
    assert 1 <= g+1 <= c+1 <= 4
print("按通道数", sorted(counts.items()), "按组数", sorted(groups.items()))
print("三出口全可收，每个触发位置的无线入库量", [2+1-k for k in range(width+1)])
period, a, b = re.search(r"平均每 (\d+) tick 至少向仓库交付前者 (\d+) 个、后者 ([\d.]+) 个",task).groups()
print("交付率", Fraction(a)/int(period), Fraction(b)/int(period))

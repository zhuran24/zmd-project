#!/usr/bin/env python3
"""R3 方法论移植轮两证书独立复算（2026-07-20）。

证书 A（供电光环，P>=9）：14 轨道权重 stencil 总权重 396；840 个与
coverage 相交且不压杆体的制造机 placement 全部满足 sum(lambda) >= area；
不相交 body 记账 => 3325 <= 396p => p >= 9。倍权整数算术（25/2 -> 25）。

证书 B（端口膜，(1190,34)）：类表 excess 63 + 端点 24 => K <= w+h+43，
核心+最终品 +5 => U = w+h+48；外部接驳容量 4/格 =>
wh + ceil((580-w-h)/4) <= 1320；双实现全维扫描 lex-max = (1190,34)。

全部断言失败即非零退出。数据源 = strict external instance（本仓真实池语义）。
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INST = json.loads((HERE / "strict/external/problem_instance.json").read_text())
TPLS = INST["facility_templates"]

# ---------- 前提 ----------
opp = {"E": "W", "W": "E", "N": "S", "S": "N"}
for tid, t in TPLS.items():
    if not tid.startswith("manufacturing"):
        continue
    for m in t["modes"]:
        ins = {p["direction"] for p in m["ports"] if p["kind"] == "input"}
        outs = {p["direction"] for p in m["ports"] if p["kind"] == "output"}
        assert len(ins) == 1 and len(outs) == 1 and opp[next(iter(ins))] == next(iter(outs)), (
            f"对侧单向口前提破: {tid} {m['id']}")

area_by_tpl = {tid: t["modes"][0]["body"]["width"] * t["modes"][0]["body"]["height"]
               for tid, t in TPLS.items()}
powered = [ri for ri in INST["required_instances"] if TPLS[ri["template"]].get("requires_power")]
assert len(powered) == 219
POW_AREA = sum(area_by_tpl[ri["template"]] for ri in powered)
assert POW_AREA == 3325, POW_AREA

# ---------- 证书 A ----------
W2 = {(3, 3): 2, (5, 1): 8, (5, 5): 16, (7, 7): 8, (9, 3): 2, (9, 9): 2,
      (11, 1): 2, (11, 3): 12, (11, 5): 22, (11, 7): 2, (11, 9): 2,
      (13, 11): 25, (15, 3): 2, (17, 3): 8}

def w2(dx: int, dy: int) -> int:
    a_, b_ = abs(2 * dx - 1), abs(2 * dy - 1)
    return W2.get((max(a_, b_), min(a_, b_)), 0)

total2 = sum(w2(dx, dy) for dx in range(-12, 14) for dy in range(-12, 14))
assert total2 == 792, total2  # 2*396

pole_body = {(0, 0), (1, 0), (0, 1), (1, 1)}
checked = 0
for W, H in ((3, 3), (5, 5), (6, 4), (4, 6)):
    for ax in range(-5 - W + 1, 7):
        for ay in range(-5 - H + 1, 7):
            body = [(ax + i, ay + j) for i in range(W) for j in range(H)]
            if not any(-5 <= x <= 6 and -5 <= y <= 6 for x, y in body):
                continue
            if any(c in pole_body for c in body):
                continue
            checked += 1
            assert sum(w2(x, y) for x, y in body) >= 2 * W * H, (W, H, ax, ay)
assert checked == 840, checked
P_MIN = math.ceil(POW_AREA / 396)
assert P_MIN == 9

# ---------- 证书 B ----------
groups = INST["operation_groups"]
ops = {g["id"]: g for g in groups} if isinstance(groups, list) else groups
cls: Counter = Counter()
for ri in powered:
    m0 = TPLS[ri["template"]]["modes"][0]
    w, h = m0["body"]["width"], m0["body"]["height"]
    d = next(p["direction"] for p in m0["ports"] if p["kind"] == "output")
    s = w if d in ("N", "S") else h
    pn = ops[ri["operation"]].get("port_needs", {})
    I = sum(pn.get("inputs", {}).values()) if isinstance(pn.get("inputs"), dict) else pn.get("inputs", 0)
    O = sum(pn.get("outputs", {}).values()) if isinstance(pn.get("outputs"), dict) else pn.get("outputs", 0)
    cls[(s, max(I, O))] += 1
cls[(3, 1)] += 46  # 边界仓
assert cls == Counter({(3, 1): 155, (3, 2): 12, (3, 3): 11, (5, 1): 32,
                       (5, 2): 17, (6, 3): 32, (6, 4): 3, (6, 5): 3}), dict(cls)  # 155 = 109 制造 + 46 边界仓
excess = sum(n * max(0, 2 * a - s) for (s, a), n in cls.items())
assert excess == 63, excess

def ceil_div(a: int, b: int) -> int:
    return -(-a // b)

def scan(orient_free: bool):
    best = (-1, -1)
    rng = range(6, 71)
    for w in rng:
        for h in (rng if orient_free else range(w, 71)):
            if w * h + ceil_div(580 - w - h, 4) <= 1320:
                best = max(best, (w * h, min(w, h)))
    return best

b1, b2 = scan(True), scan(False)
assert b1 == b2 == (1190, 34), (b1, b2)

print(f"OK: 前提3项 | 证书A stencil=396 placements=840 全过 => P>={P_MIN} | "
      f"证书B excess=63 双扫描 lex-max=(1190,34)")
sys.exit(0)

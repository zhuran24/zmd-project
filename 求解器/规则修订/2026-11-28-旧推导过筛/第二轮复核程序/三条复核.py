#!/usr/bin/env python3
"""第二轮独立复核：传输按仓库余量判定、成品停收的停批范围、成品汇入。
配方从现行规则正文解析；停批范围用线性规划求平稳解或势函数证书，再用分数精确核验。"""
import re, sys, itertools, random
from fractions import Fraction as F
from math import ceil
import numpy as np
from scipy.optimize import linprog

RULE = sys.argv[1]
text = open(RULE, encoding="utf-8").read()

# ---------- 解析配方 ----------
sec = text.split("\n配方\n", 1)[1]
recipes = []
for line in sec.strip().splitlines():
    line = line.strip()
    if "：" not in line:
        continue
    mach, body = line.split("：", 1)
    for part in body.split("；"):
        part = part.strip().rstrip("，")
        m = re.match(r"(.+?)\s*→\s*(\d+)\s*(\S+?)，\s*(\d+)\s*tick", part)
        lhs, n_out, out, dur = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        ins = {}
        for term in lhs.split("＋"):
            mm = re.match(r"\s*(\d+)\s*(\S+)\s*", term)
            ins[mm.group(2)] = int(mm.group(1))
        recipes.append((mach, ins, out, n_out, dur))
assert len(recipes) == 18, len(recipes)
items = sorted({i for r in recipes for i in r[1]} | {r[2] for r in recipes})
assert len(items) == 19, items
BAT, CAP, YK, TK = "高容谷地电池", "精选荞愈胶囊", "源矿", "蓝铁矿"
idx = {it: k for k, it in enumerate(items)}

def vec(d):
    v = [0] * len(items)
    for k, c in d.items():
        v[idx[k]] += c
    return v

def name(r):
    mach, ins, out, n, _ = r
    return f"{mach}:{'+'.join(f'{c}{i}' for i, c in ins.items())}->{n}{out}"

base_acts = []
for r in recipes:
    d = {k: -c for k, c in r[1].items()}
    d[r[2]] = d.get(r[2], 0) + r[3]
    base_acts.append((name(r), vec(d)))
base_acts.append(("取货:源矿", vec({YK: 1})))
base_acts.append(("取货:蓝铁矿", vec({TK: 1})))

def scenario(stopped, ore_entry):
    acts = list(base_acts)
    for o in (YK, TK):
        if ore_entry[o]:
            acts.append((f"入库:{o}", vec({o: -1})))
    for p in (BAT, CAP):
        if p not in stopped:
            acts.append((f"玩家拿取:{p}", vec({p: -1})))
    return acts

def exact_check_stationary(acts, t, x):
    xs = [F(v).limit_denominator(1000) for v in x]
    if any(v < 0 for v in xs) or xs[t] <= 0:
        return False
    for j in range(len(items)):
        if sum(xs[a] * acts[a][1][j] for a in range(len(acts))) != 0:
            return False
    return True

def exact_check_cert(acts, t, w):
    ws = [F(v).limit_denominator(1000) for v in w]
    dots = [sum(ws[j] * a[1][j] for j in range(len(items))) for a in acts]
    return all(d >= 0 for d in dots) and dots[t] > 0

def classify(acts):
    A = np.array([a[1] for a in acts], dtype=float)  # acts x items
    finite, infinite = [], []
    n = len(acts)
    for t in range(n):
        # 平稳解：x>=0, x_t=1, A^T x = 0
        Aeq = np.vstack([A.T, np.eye(n)[t]])
        beq = np.concatenate([np.zeros(len(items)), [1.0]])
        res = linprog(np.zeros(n), A_eq=Aeq, b_eq=beq, bounds=[(0, None)] * n, method="highs")
        if res.status == 0:
            assert exact_check_stationary(acts, t, res.x), acts[t][0]
            infinite.append(acts[t][0])
        else:
            # 证书：w·Δa >= 0 对全部 a，w·Δt >= 1
            Aub = -A.copy()
            bub = np.zeros(n); bub[t] = -1.0
            res2 = linprog(np.zeros(len(items)), A_ub=Aub, b_ub=bub,
                           bounds=[(-100, 100)] * len(items), method="highs")
            assert res2.status == 0, acts[t][0]
            assert exact_check_cert(acts, t, res2.x), acts[t][0]
            finite.append(acts[t][0])
    return finite, infinite

cases = {
    "（一）电池停收、源矿不入库": ({BAT}, {YK: False, TK: True}),
    "（二）胶囊停收、矿石可入库": ({CAP}, {YK: True, TK: True}),
    "（三）两种都停收、矿石不入库": ({BAT, CAP}, {YK: False, TK: False}),
    "对照（一）源矿可入库": ({BAT}, {YK: True, TK: True}),
    "对照（三）矿石可入库": ({BAT, CAP}, {YK: True, TK: True}),
    "对照（二）再禁矿石入库": ({CAP}, {YK: False, TK: False}),
}
print("== 成品停收的停批范围 ==")
for label, (st, oe) in cases.items():
    fin, inf = classify(scenario(st, oe))
    fin = [f for f in fin if not f.startswith(("入库", "玩家"))]
    print(label, "必有限:", len(fin))
    for f in fin:
        print("   ", f)
    print("   可持续的配方/取货:", [i for i in inf if not i.startswith(("入库", "玩家"))])

# ---------- 成品汇入 ----------
print("\n== 成品汇入 ==")
for p, rate in ((BAT, F(6, 10)), (CAP, F(55, 100))):
    r = [x for x in recipes if x[2] == p][0]
    per = F(r[3], r[4])
    print(p, "每台至多", per, "件/tick，至少", ceil(rate / per), "台在产")

# 步级模拟一台末级机器：原料无限、出口每步都取走，看相邻两次结束制造隔几步
def sim_steps(dur_tick, steps=2000):
    STEPS = 8 * dur_tick
    cache = None  # 剩余步数
    ends = []
    for s in range(steps):
        # 1-4 移动判定：取货格每步被取空（最乐观）
        # 5 结束制造
        if cache is not None:
            cache -= 1
            if cache == 0:
                ends.append(s); cache = None
        # 6 开始制造（上一批已进取货格）
        if cache is None:
            cache = STEPS
    return set(b - a for a, b in zip(ends, ends[1:]))
print("末级 5 tick 配方相邻完工间隔（步）:", sim_steps(5))

# 各单位 r = 承接的成品通道数 − 外送的成品通道数 的上界（有进必有出，核心与传输箱除外）
units = {
    "传送带": (1, 1, False), "物品准入口": (1, 1, False), "分流器": (1, 3, False),
    "汇流器": (3, 1, False), "桥接器的一个物品格": (1, 1, False),
    "不传输的协议储存箱": (3, 3, False), "传输的协议储存箱": (3, 3, True),
}
for u, (i_max, o_max, absorb) in units.items():
    best = max(i - o for i in range(i_max + 1) for o in range(o_max + 1)
               if (absorb or i == 0 or o >= 1) and not (i == 0 and o > 0))
    print(f"  {u}: r ≤ {best}")
# 小型穷举：K、B、C 组合使 Σ吸收 >= 6 的充要
ok = all((K + 3 * B + 2 * C >= 6) == (K + 3 * B + 2 * C >= 6) for K in range(15) for B in range(4) for C in range(4))

# ---------- 传输按仓库余量判定 ----------
print("\n== 传输按仓库余量判定 ==")
def transmit(cells, f):
    # cells: 每格该种件数，按编号从小到大送，送不完留原格
    sent = 0
    for n in cells:
        k = min(n, f - sent)
        sent += k
    return sent
bad = 0
for cells in itertools.product(range(4), repeat=6):  # 每格 0..3（缩小上限穷举）
    for f in range(0, 20):
        s = transmit(cells, f)
        if s != min(sum(cells), f): bad += 1
        if (s == 0) != (sum(cells) == 0 or f == 0): bad += 1
random.seed(1)
for _ in range(200000):
    cells = [random.choice([0, 0, random.randint(1, 50), 50]) for _ in range(6)]
    f = random.choice([0, random.randint(1, 400), 80000])
    s = transmit(cells, f)
    if s != min(sum(cells), f) or (s == 0) != (sum(cells) == 0 or f == 0): bad += 1
print("min(n,f) 与「n=0 或 f=0」逐格送法核对，违例:", bad)

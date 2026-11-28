"""主会话三审用的独立复算：只算随规则变化而要重核的几处数字。
用法：python3 三审复算.py <游戏规则.txt>。不读席位的程序。"""
import sys, re, itertools
from fractions import Fraction as F
from math import ceil
from collections import deque

rules = open(sys.argv[1], encoding='utf-8').read()

# ---- 1. 配方和各物料流量、机型下限、端口收支 ----
sec = rules.split('\n配方\n', 1)[1]
recipes = []   # (机型, {原料: 件}, 产物, 件, tick)
for line in sec.strip().splitlines():
    m, body = line.strip().split('：', 1)
    for ent in body.split('；'):
        lhs, rhs = ent.split('→')
        ins = {}
        for part in lhs.split('＋'):
            n, name = part.strip().split(' ', 1); ins[name.strip()] = int(n)
        out, t = rhs.split('，')
        n, name = out.strip().split(' ', 1)
        recipes.append((m, ins, name.strip(), int(n), int(t.strip().split(' ')[0])))
assert len(recipes) == 18, len(recipes)
prod = {}
for r in recipes: prod.setdefault(r[2], []).append(r)
# 每种物品取唯一的「正向」做法：蓝铁块由蓝铁矿炼（回炼率 r 取 0），其余物品只有一个配方
def maker(x):
    rs = prod.get(x, [])
    if x == '蓝铁块': rs = [r for r in rs if '蓝铁矿' in r[1]]
    assert len(rs) <= 1, (x, rs)
    return rs[0] if rs else None
need = {}      # 每 tick 消耗量（不含种子自循环）
batch = {}     # 每个配方的批率
def demand(x, q):
    need[x] = need.get(x, 0) + q
    r = maker(x)
    if r is None or x in ('荞花', '砂叶'): return
    b = q / r[3]; batch[(r[0], x)] = batch.get((r[0], x), 0) + b
    for y, n in r[1].items(): demand(y, b * n)
demand('高容谷地电池', F(18, 30)); demand('精选荞愈胶囊', F(165, 300))
assert need['蓝铁矿'] == 34 and need['源矿'] == 18, (need['蓝铁矿'], need['源矿'])
# 植物：粉碎 f 株/tick，采种 h，种植 p：p = f + h，p = 2h  => h = f，p = 2f
plant = {}
for sp in ('荞花', '砂叶'):
    f = need[sp]; plant[sp] = (f, f, 2 * f)       # 粉碎、采种、种植
    batch[('采种机', sp + '种子')] = f; batch[('种植机', sp)] = 2 * f
rate = {}
for (m, x), b in batch.items():
    r = maker(x) if m not in ('采种机', '种植机') else [q for q in recipes if q[0] == m and q[2] == x][0]
    rate[m] = rate.get(m, 0) + b * r[4]            # 所需加工台数 = 批率 × 时长
want = {'粉碎机': 68, '精炼炉': 51, '研磨机': 32, '塑形机': 6, '配件机': 6, '种植机': 32, '采种机': 16, '封装机': 3, '灌装机': 3}
got = {m: ceil(v) for m, v in rate.items()}
assert got == want, (got, want)
small = sum(want[m] for m in ('粉碎机', '精炼炉', '配件机', '塑形机')); mid = want['采种机'] + want['种植机']; big = want['研磨机'] + want['封装机'] + want['灌装机']
area = small * 9 + mid * 25 + big * 24
assert (small, mid, big, sum(want.values()), area) == (131, 48, 38, 217, 3291)
# 每台机器的进、出件数/tick（端口每 tick 至多 1 件），各机型进出通道数下界
outflow = {}; inflow = {}
for (m, x), b in batch.items():
    r = maker(x) if m not in ('采种机', '种植机') else [q for q in recipes if q[0] == m and q[2] == x][0]
    outflow[m] = outflow.get(m, 0) + b * r[3]
    inflow[m] = inflow.get(m, 0) + b * sum(r[1].values())
S = sum(ceil(outflow[m]) for m in want if m not in ('封装机', '灌装机')) + 3 + 3 + 52
R = sum(ceil(inflow[m]) for m in want) + 2
total = sum(inflow.values()) + F(18, 30) + F(165, 300)
print('机型下限', got, '占地', area, '| S>=', S, 'R>=', R, 'S+R>=', S + R, '| 每 tick 进运输格的件数', float(sum(outflow.values()) + 52))
assert (S, R) == (312, 307)
assert sum(outflow.values()) + 52 == F(30565, 100)
assert 3291 + 81 + 46 * 3 + 10 * 4 == 3550 and 3550 + 208 == 3758 and 3550 + 306 == 3856

# ---- 2. 传输箱：相邻两次传输之间每口至多进几件；六格符号枚举 ----
def per_port(stages, gap=8):
    best = 0
    for first in range(stages):
        best = max(best, len(range(first, stages, gap)))
    return best
assert per_port(40) == 5 and per_port(41) == 6
def min_fills(kinds, slots=6):
    """从空箱起，至少填几次空格才能到「六格全占且缺某种来货」。来货放进第一个同种格或第一个空格；
    任何时候可以免费擦掉第一个非空格（取货取编号最小的非空格，取空才变）。"""
    start = (None,) * slots
    dist = {start: 0}; dq = deque([start])
    while dq:
        s = dq.popleft(); d = dist[s]
        if all(c is not None for c in s) and len(set(s)) < kinds: return d
        nxt = []
        i = next((j for j, c in enumerate(s) if c is not None), None)
        if i is not None: nxt.append((s[:i] + (None,) + s[i + 1:], 0))
        for k in range(kinds):
            for j, c in enumerate(s):
                if c == k: break                     # 遇到同种格，进这一格，符号不变
                if c is None: nxt.append((s[:j] + (k,) + s[j + 1:], 1)); break
        for t, w in nxt:
            if t not in dist or dist[t] > d + w:
                dist[t] = d + w
                (dq.appendleft if w == 0 else dq.append)(t)
    return None
fills = {k: min_fills(k) for k in range(1, 8)}
print('每口 40 个进箱轮次至多', per_port(40), '件；填空次数下界', fills)
assert fills[3] == 20 and fills[4] == 11 and fills[1] is None
assert 15 < fills[3] and 10 < fills[4] and 10 >= fills[5]

# ---- 3. 物品准入口每 5 tick 上限 k：长期平均至多 k/5 ----
def gate_max(k, steps=4000, built=0):
    """每步都有货等着（不管滞留），贪心收：收得下就收。段：建成后第 1~3 步为第 1 段，此后每 4 步一段。"""
    seg = lambda s: 1 + s // 4          # s 为建成后的步号，从 1 起
    got = []
    for s in range(1, steps + 1):
        cur = seg(s); cnt = sum(1 for g in got if seg(g) > cur - 10)
        if cnt < k: got.append(s)
    return len(got)
for k in range(6):
    n = gate_max(k)
    assert n <= k * (4000 + 3) // 40 + k, (k, n)
    assert abs(F(n, 4000) * 8 - F(k, 5)) < F(1, 50), (k, n)   # 不管滞留时贪心正好达到 k/5（k=5 时每步都收，受滞留再限到 1）
print('准入口每 5 tick 上限 k 的长期收货率（件/tick，不计滞留）', [float(F(gate_max(k), 4000) * 8) for k in range(6)])
print('三审复算通过')

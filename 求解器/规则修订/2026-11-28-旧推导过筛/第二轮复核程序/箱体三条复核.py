"""第二轮独立复核：箱体接口、箱体预算、箱体过站 三条里的数字。
只读仓库；输出到标准输出。
1 配方逐物品收支（有理数），r 为蓝铁粉末回炼批次率；
2 机器端口边沿边缺口 f(k,n)（自写放置模型）与 164 的动态规划；
3 η 与 S+R 下界的小范围穷举；
4 箱体预算的占地/空矩形取整，含 0/1/2 台增机（55 种）与 ≥3 台；
5 无箱时 46 源口到 3x3 消费机身的额外访问下界（自写 CP-SAT，预算 7 应不可行）。
"""
import re, sys, itertools, json, time
from fractions import Fraction as Fr
from math import ceil, floor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
rules = (ROOT / '《明日方舟：终末地》游戏规则.txt').read_text()

# ---------- 1 配方 ----------
sec = rules.split('\n配方\n')[1]
recipes = []
for line in sec.strip().splitlines():
    m, body = line.strip().split('：', 1)
    for ent in body.split('；'):
        lhs, rhs = ent.split('→')
        rhs, dur = rhs.rsplit('，', 1)
        def parse(s):
            d = {}
            for n, name in re.findall(r'(\d+)\s*([^\s＋，]+)', s):
                d[name.strip()] = int(n)
            return d
        recipes.append((m, parse(lhs), parse(rhs), int(re.findall(r'\d+', dur)[0])))
assert len(recipes) == 18, len(recipes)
items = sorted({x for _, a, b, _ in recipes for x in list(a) + list(b)})

def solve(r):
    # 未知：18 个配方批次率 x_j。物品收支：产出-消耗 = 外部净提取
    ext = {x: Fr(0) for x in items}
    ext['蓝铁矿'] = Fr(-34); ext['源矿'] = Fr(-18)  # 仓库供给（取出为负的"外部提取"）
    ext['高容谷地电池'] = Fr(3, 5); ext['精选荞愈胶囊'] = Fr(11, 20)
    rows = []
    for x in items:
        rows.append([Fr(b.get(x, 0) - a.get(x, 0)) for _, a, b, _ in recipes] + [ext[x]])
    rows.append([Fr(1 if (m == '精炼炉' and '蓝铁粉末' in a) else 0) for m, a, b, _ in recipes] + [Fr(r)])
    n = len(recipes)
    piv_cols = []
    rr = 0
    for c in range(n):
        p = next((i for i in range(rr, len(rows)) if rows[i][c] != 0), None)
        if p is None:
            continue
        rows[rr], rows[p] = rows[p], rows[rr]
        pv = rows[rr][c]
        rows[rr] = [v / pv for v in rows[rr]]
        for i in range(len(rows)):
            if i != rr and rows[i][c] != 0:
                f = rows[i][c]
                rows[i] = [v - f * w for v, w in zip(rows[i], rows[rr])]
        piv_cols.append(c); rr += 1
    assert rr == n, ('秩不足', rr)
    assert all(all(v == 0 for v in row) for row in rows[n:])
    x = [rows[i][-1] for i in range(n)]
    assert all(v >= 0 for v in x), x
    out = sum(xj * sum(b.values()) for xj, (_, a, b, _) in zip(x, recipes))
    return x, out + 52  # 制造单位全部产出 + 52 件原矿出库

x0, V0 = solve(0)
x1, V1 = solve(1)
print('[1] 18 配方；制造产出+矿口 r=0:', V0, float(V0), ' 斜率', V1 - V0)
bymachine = {}
for xj, (m, a, b, d) in zip(x0, recipes):
    bymachine[m] = bymachine.get(m, 0) + xj
print('    各机型批次率 r=0:', {k: float(v) for k, v in bymachine.items()})
print('    ceil(V0+52)=', ceil(V0 + 52), ' ceil(V0+8)=', ceil(V0 + 8))

# ---------- 2 沿边缺口 ----------
def f_edge(k, n):
    """长 n 的端口边前一行放 k 个对接格；对接格沿行的邻格若放不下"端口面向它的非运输单位"
    则计 1。内部空段长 g：g>=3 时可放（3x3 两对边皆端口；g=4 用 6x4 的两条长边；g=5 用 5x5；
    更长可放多台），否则两侧各计 1；相邻对接格互计各 1；行两端外侧不受限。"""
    best = None
    for pos in itertools.combinations(range(n), k):
        inc = 0
        for a, b in zip(pos, pos[1:]):
            g = b - a - 1
            if g == 0 or g < 3:
                inc += 2
        best = inc if best is None else min(best, inc)
    return best if k > 0 else 0

f3 = [f_edge(k, 3) for k in range(4)]
f5 = [f_edge(k, 5) for k in range(6)]
f6 = [f_edge(k, 6) for k in range(7)]
print('[2] f3', f3, ' f5', f5, ' f6', f6)

def dp(nmach, need, cap, f):
    """nmach 台，每台 k 条（有效 min(k,cap)），Σ有效 ≥ need，最小 Σf(k)。"""
    INF = 10**9
    best = [INF] * (need + 1)
    best[0] = 0
    for _ in range(nmach):
        nb = [INF] * (need + 1)
        for s in range(need + 1):
            if best[s] >= INF:
                continue
            for k in range(len(f)):
                t = min(need, s + min(k, cap))
                nb[t] = min(nb[t], best[s] + f[k])
        best = nb
    return best[need]

def inc_total(n粉, n研, n塑, n灌, n封):
    return (dp(n粉, 95, 3, f3) + dp(n研, 95, 3, f6) + dp(n塑, 11, 2, f3)
            + dp(n灌, 11, 4, f6) + dp(n封, 15, 5, f6))

parts = (dp(68, 95, 3, f3), dp(32, 95, 3, f6), dp(6, 11, 2, f3), dp(3, 11, 4, f6), dp(3, 15, 5, f6))
print('    五项', parts, '合计', sum(parts))
core_cap = 2 * (3 + 2 + 3)  # 每条取货边：三格各 1 个朝外 + 核心面 1，侧向只在偏移 0、8 外侧
ore_nonport = 4 * 46 - 93
core_nonport = 4 * 6 - core_cap
print('    矿格缺口', ore_nonport, ' 核心缺口', core_nonport, ' 99+164/2=', ore_nonport + core_nonport + sum(parts) / 2)

# ---------- 3 η ----------
bad = 0
for B0 in range(4):
    for B1 in range(6):
        H = max(2, B1)
        for M in range(6):
            for D in range(6):
                s = 312 + B0; v = 305 + B0 + H
                mn = min(S + R for S in range(s, s + 30) for R in range(v, v + 30)
                         if -2 * M <= R - S <= 2 * D)
                eta = 2 * B0 + max(H - 2, 5 - 2 * M, 2 * H - 9 - 2 * D)
                if mn != 619 + eta:
                    bad += 1
print('[3] S+R 最小值与 619+η 不符的组合数', bad)
# 2T+M 取整
for B0 in range(4):
    for M in range(8):
        eta_lb = 2 * B0 + 5 - 2 * M
        T1 = ceil((718 + max(eta_lb, 2 * B0)) / 4)
        T2 = ceil((800 + max(eta_lb, 2 * B0)) / 4)
        assert 2 * T1 + M >= 362 + B0 and 2 * T2 + M >= 403 + B0
print('    2T+M≥362+B0、403+B0 在 B0<4、M<8 的取整检查通过')

# ---------- 4 箱体预算 ----------
small = ['粉碎机', '精炼炉', '配件机', '塑形机']
mid = ['采种机', '种植机']
big = ['研磨机', '封装机', '灌装机']
base = dict(粉碎机=68, 精炼炉=51, 研磨机=32, 塑形机=6, 配件机=6, 种植机=32, 采种机=16, 封装机=3, 灌装机=3)
area = lambda n: sum(n[t] * (9 if t in small else 25 if t in mid else 24) for t in n)
A0 = area(base)
fixed = A0 + 81 + 46 * 3 + 10 * 4
print('[4] 机器占地', A0, ' 加核心/取货口/10 桩', fixed)
types = list(base)
worst = None
for add in range(3):
    for combo in itertools.combinations_with_replacement(types, add):
        n = dict(base)
        for t in combo:
            n[t] += 1
        inc = inc_total(n['粉碎机'], n['研磨机'], n['塑形机'], n['灌装机'], n['封装机'])
        for eta in range(12):
            for q in (0, 3):  # q=3：边带余格放运输单位
                T = ceil((619 + eta + 99 + q + Fr(inc, 2)) / 4)
                occ = area(n) + 81 + 138 + 40 + T
                need = 3750 + ceil(Fr(eta, 4)) + (0 if q == 0 else 0)
                slack = occ - need
                if q == 3:
                    # 空矩形：A ≤ 4900-occ（余格被占）；余格空时 A ≤ 4900-occ-1
                    pass
                worst = slack if worst is None else min(worst, slack)
                assert slack >= 0, (combo, eta, q, occ, need)
print('    0/1/2 台增机 55 种 × η 0..11 × 余格两支：占地 ≥3750+⌈η/4⌉，最小余量', worst)
# ≥3 台：T ≥ ceil((718+η)/4)，增地 ≥27
for eta in range(12):
    assert fixed + 27 + ceil(Fr(718 + eta, 4)) >= 3750 + ceil(Fr(eta, 4))
# 空矩形：两支取较弱
for eta in range(40):
    a1 = 4900 - (fixed + ceil(Fr(800 + eta, 4))) - 1      # 余格空着，不在矩形内
    a2 = 4900 - (fixed + ceil(Fr(803 + eta, 4)))          # 余格放运输单位
    assert max(a1, a2) == 1149 - (eta + 2) // 4, eta
# 增机时空矩形两支也要不超过 1149-⌊(η+2)/4⌋
for add in range(3):
    for combo in itertools.combinations_with_replacement(types, add):
        n = dict(base)
        for t in combo:
            n[t] += 1
        inc = inc_total(n['粉碎机'], n['研磨机'], n['塑形机'], n['灌装机'], n['封装机'])
        fx = area(n) + 81 + 138 + 40
        for eta in range(40):
            a1 = 4900 - (fx + ceil((718 + eta + Fr(inc, 2)) / 4)) - 1
            a2 = 4900 - (fx + ceil((721 + eta + Fr(inc, 2)) / 4))
            assert max(a1, a2) <= 1149 - (eta + 2) // 4, (combo, eta)
for eta in range(40):
    a1 = 4900 - (fixed + 27 + ceil(Fr(718 + eta, 4))) - 1
    a2 = 4900 - (fixed + 27 + ceil(Fr(721 + eta, 4)))
    assert max(a1, a2) <= 1149 - (eta + 2) // 4
print('    空矩形 max 两支 = 1149-⌊(η+2)/4⌋（指定配置），增机均不超过；B0≥1:',
      fixed + 200 + 9 + ceil(Fr(2, 4)), 1149 - 9 - (2 + 2) // 4)
print('    217 台 / 每桩 23 台 =', ceil(217 / 23), '桩')

# ---------- 5 无箱 46 源口额外访问 ----------
def ports(e):
    out, p = [], 0
    while p < 70:
        if p == e:
            p += 1; continue
        out.append(p + 1); p += 3
    assert len(out) == 23
    return out

def infeasible(eL, eB, budget=7):
    from ortools.sat.python import cp_model
    src = [(1, y) for y in ports(eL)] + [(x, 1) for x in ports(eB)]
    srcset = set(src)
    def d(s, x, y):
        dx = max(x - s[0], 0, s[0] - (x + 2)); dy = max(y - s[1], 0, s[1] - (y + 2))
        return dx + dy - 1
    bodies = []
    for x in range(1, 68):
        for y in range(1, 68):
            cells = [(x + i, y + j) for i in range(3) for j in range(3)]
            if srcset.intersection(cells):
                continue
            cs = [d(s, x, y) for s in src]
            if min(cs) <= budget:
                bodies.append((cells, cs))
    m = cp_model.CpModel()
    use = [m.NewBoolVar('') for _ in bodies]
    pair = {}
    for j, (cells, cs) in enumerate(bodies):
        for i, c in enumerate(cs):
            if c <= budget:
                pair[i, j] = m.NewBoolVar('')
    for i in range(len(src)):
        m.Add(sum(v for (a, j), v in pair.items() if a == i) == 1)
    for j in range(len(bodies)):
        lst = [v for (a, b), v in pair.items() if b == j]
        if lst:
            m.Add(sum(lst) <= use[j])
    cover = {}
    for j, (cells, cs) in enumerate(bodies):
        for c in cells:
            cover.setdefault(c, []).append(use[j])
    for c, l in cover.items():
        if len(l) > 1:
            m.Add(sum(l) <= 1)
    m.Add(sum(bodies[j][1][i] * v for (i, j), v in pair.items()) <= budget)
    sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = 300; sv.parameters.num_workers = 8
    return sv.StatusName(sv.Solve(m))

if '--ore' in sys.argv:
    es = list(range(0, 70, 3))
    arr = [(a, b) for a in es for b in es if a == 0 or b == 0]
    print('[5] 边带排布数', len(arr))
    budget = 7 if '--b8' not in sys.argv else 8
    res = {}
    for a, b in arr:
        res[(a, b)] = infeasible(a, b, budget)
    from collections import Counter
    print('    预算', budget, Counter(res.values()))

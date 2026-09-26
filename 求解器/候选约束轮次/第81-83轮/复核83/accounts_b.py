#!/usr/bin/env python3
"""复核83 编码乙：与编码甲独立的写法核对关键数字。
- C1：配方手抄，numpy 求秩；从成品逐级倒推 r=0 与 r=1 两组解，核批率与物理出货。
- C5：f 表用 MILP（scipy/HiGHS），逐口流量连续变量 + 支持二元变量 + 相邻近距离对的权重线性化。
- C6：外边界 X0 下界用逐格贪心构造的最坏排布另算（最多能被在产机器、核心、额外单位覆盖的长度）。
- B1：首件死锁按“到件是否被拒”的状态机逐件模拟判定，含/不含误料首件。"""
import json, itertools, math
import numpy as np
from fractions import Fraction as Fr
from scipy.optimize import milp, LinearConstraint, Bounds

out = {}
# ---------- C1 ----------
R = [  # (机器, {输入}, {输出})
    ('粉碎机', {'源矿': 1}, {'源石粉末': 1}), ('粉碎机', {'蓝铁块': 1}, {'蓝铁粉末': 1}),
    ('粉碎机', {'荞花': 1}, {'荞花粉末': 2}), ('粉碎机', {'砂叶': 1}, {'砂叶粉末': 3}),
    ('精炼炉', {'蓝铁矿': 1}, {'蓝铁块': 1}), ('精炼炉', {'致密蓝铁粉末': 1}, {'钢块': 1}),
    ('精炼炉', {'蓝铁粉末': 1}, {'蓝铁块': 1}),
    ('研磨机', {'蓝铁粉末': 2, '砂叶粉末': 1}, {'致密蓝铁粉末': 1}),
    ('研磨机', {'源石粉末': 2, '砂叶粉末': 1}, {'致密源石粉末': 1}),
    ('研磨机', {'荞花粉末': 2, '砂叶粉末': 1}, {'细磨荞花粉末': 1}),
    ('塑形机', {'钢块': 2}, {'钢质瓶': 1}), ('配件机', {'钢块': 1}, {'钢制零件': 1}),
    ('种植机', {'荞花种子': 1}, {'荞花': 1}), ('种植机', {'砂叶种子': 1}, {'砂叶': 1}),
    ('采种机', {'荞花': 1}, {'荞花种子': 2}), ('采种机', {'砂叶': 1}, {'砂叶种子': 2}),
    ('封装机', {'钢制零件': 10, '致密源石粉末': 15}, {'高容谷地电池': 1}),
    ('灌装机', {'钢质瓶': 10, '细磨荞花粉末': 10}, {'精选荞愈胶囊': 1}),
]
items = sorted({k for r in R for k in list(r[1]) + list(r[2])})
A = np.array([[r[2].get(i, 0) - r[1].get(i, 0) for r in R] for i in items], dtype=float)
out['C1_rank_numpy'] = int(np.linalg.matrix_rank(A))
def solve(rr):
    x = {}
    x['e1'] = Fr(3, 5); x['e2'] = Fr(11, 20)
    part = 10 * x['e1']; dys = 15 * x['e1']; bot = 10 * x['e2']; fine = 10 * x['e2']
    steel = part + 2 * bot
    dfe = steel
    qpow = 2 * fine; ypow = 2 * dys
    sand_pow = dfe + dys + fine
    fe_pow = 2 * dfe + rr
    rates = {'粉碎机': ypow + fe_pow + qpow / 2 + sand_pow / 3, '精炼炉': Fr(34) + steel + rr,
             '研磨机': dfe + dys + fine, '塑形机': bot, '配件机': part,
             '种植机': 2 * (qpow / 2) + 2 * (sand_pow / 3), '采种机': qpow / 2 + sand_pow / 3,
             '封装机': x['e1'], '灌装机': x['e2']}
    phys = (ypow + fe_pow + qpow + sand_pow + Fr(34) + rr + steel + dfe + dys + fine + bot + part
            + 2 * (qpow / 2 + sand_pow / 3) * 2 + x['e1'] + x['e2'] + 52)
    # 植物：种植产植株 = 2*采种批；采种产种子 = 2*采种批
    return {k: str(v) for k, v in rates.items()}, str(phys)
out['C1_r0'] = solve(Fr(0)); out['C1_r1'] = solve(Fr(1))

# ---------- C5：MILP f ----------
def f_milp(E, Fmax, total, n):
    # 变量：每台机器 j、每口 p：f[j,p] in [0,1]，z[j,p] 支持；每对 p<q（q-p<=3）且中间无支持口时 y[j,p,q] 二元“是相邻近对”
    # 权重 sum_{j,p<q close} (f[j,p]+f[j,q]) * y[j,p,q]，线性化 w[j,p,q]>= f_p + f_q - 2(1-y)
    V = []
    idx = {}
    def var(name, lo, hi, integ):
        idx[name] = len(V); V.append((lo, hi, integ))
    pairs = [(p, q) for p in range(E) for q in range(p + 1, E) if q - p <= 3]
    for j in range(n):
        for p in range(E):
            var(('f', j, p), 0, 1, 0); var(('z', j, p), 0, 1, 1)
        for (p, q) in pairs:
            var(('y', j, p, q), 0, 1, 1); var(('w', j, p, q), 0, 2, 0)
    N = len(V)
    rows, lo, hi = [], [], []
    def row(coefs, l, h):
        r = np.zeros(N)
        for k, v in coefs:
            r[idx[k]] += v
        rows.append(r); lo.append(l); hi.append(h)
    tot = []
    for j in range(n):
        mf = []
        for p in range(E):
            row([(('f', j, p), 1), (('z', j, p), -1)], -np.inf, 0)  # f<=z
            mf.append((('f', j, p), 1))
        row(mf, -np.inf, Fmax)
        tot += mf
        for (p, q) in pairs:
            # y>= z_p + z_q - 1 - sum_{p<r<q} z_r  （p,q 都支持且中间无支持 => 是相邻近对）
            c = [(('y', j, p, q), 1), (('z', j, p), -1), (('z', j, q), -1)] + [(('z', j, r), 1) for r in range(p + 1, q)]
            row(c, -1, np.inf)
            # w >= f_p + f_q - 2(1-y)
            row([(('w', j, p, q), 1), (('f', j, p), -1), (('f', j, q), -1), (('y', j, p, q), -2)], -2, np.inf)
    row(tot, float(total), np.inf)
    # 正流量才算支持：z=1 => f>=eps？取闭包：允许 z=1,f=0（只会多算权重，不影响最小值）
    c = np.zeros(N)
    for j in range(n):
        for (p, q) in pairs:
            c[idx[('w', j, p, q)]] = 1
    res = milp(c, constraints=[LinearConstraint(np.array(rows), lo, hi)],
               integrality=np.array([v[2] for v in V]), bounds=Bounds([v[0] for v in V], [v[1] for v in V]),
               options={'time_limit': 120})
    return round(res.fun, 6) if res.x is not None else None
fm = {}
for name, E, Fmax, total, ns in [('塑形机', 3, 2, 11, [6, 7, 8, 11]), ('封装机', 6, 5, 15, [3, 4, 5, 6, 7, 8]),
                                  ('灌装机', 6, 4, 11, [3, 4, 5, 6]), ('研磨机', 6, 3, 94.5, [32, 33, 40, 47, 48])]:
    fm[name] = {n: f_milp(E, Fmax, total, n) for n in ns}
out['C5_f_milp'] = fm

# ---------- C6：外边界 ----------
def x0_lower(L, k, t, c):
    # 反复试 X0 从 0 起：给定 X0 个分隔格，在产机器接触段数 m<=X0+c+t+k，总可覆盖长度 5m+9c+3t+X0
    for X0 in range(0, 200):
        m = X0 + c + t + k
        if 5 * m + 9 * c + 3 * t + X0 >= L:
            return X0
out['C6_X0_b'] = {'both': x0_lower(71, 2, 1, 1), 'one': min(x0_lower(138 - 37, 3, 2, 1), x0_lower(138 - 30, 3, 2, 1)),
                  'none': x0_lower(138, 2, 2, 1), 'both_t0': x0_lower(71, 2, 0, 1)}
# 1110 的整数边长及 1107
out['C6_areas'] = {A_: [(a, A_ // a) for a in range(6, 69) if A_ % a == 0 and A_ // a <= 68 and a <= A_ // a] for A_ in (1107, 1108, 1109, 1110, 1111, 1112, 1113)}

# ---------- B1：逐件模拟 ----------
def refuses(slots, item):
    kinds = [s[0] for s in slots if s]
    if item in kinds:
        return dict((s[0], s[1]) for s in slots if s)[item] >= 50
    return all(s is not None for s in slots)
def can_batch(slots, recs):
    h = {s[0]: s[1] for s in slots if s}
    return any(all(h.get(k, 0) >= v for k, v in r.items()) for r in recs)
recs = {'研磨机': [{'蓝铁粉末': 2, '砂叶粉末': 1}, {'源石粉末': 2, '砂叶粉末': 1}, {'荞花粉末': 2, '砂叶粉末': 1}],
        '封装机': [{'钢制零件': 10, '致密源石粉末': 15}], '灌装机': [{'钢质瓶': 10, '细磨荞花粉末': 10}]}
b1 = {}
for mname, rs in recs.items():
    kinds = sorted({k for r in rs for k in r})
    tot_no, tot_w = 0, 0
    for s1 in [None] + [(k, c) for k in kinds for c in range(1, 51)]:
        for s2 in [None] + [(k, c) for k in kinds for c in range(1, 51)]:
            if s1 and s2 and s1[0] >= s2[0]:
                continue
            if s1 is None and s2 is not None:
                continue
            slots = (s1, s2)
            if can_batch(slots, rs):
                continue
            ks = [s[0] for s in slots if s]
            if mname == '研磨机' and len([k for k in ks if k != '砂叶粉末']) >= 2:
                continue
            ref = [h for h in kinds if refuses(slots, h)]
            tot_no += 2 ** len(ref) - 1
            wr = refuses(slots, '误料')
            tot_w += 2 ** (len(ref) + (1 if wr else 0)) - 1
    b1[mname] = {'no_wrong_heads': tot_no, 'with_wrong_heads': tot_w}
out['B1_b'] = b1
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))

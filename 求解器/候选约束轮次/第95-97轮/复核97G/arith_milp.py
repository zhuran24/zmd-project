#!/usr/bin/env python3
"""复核97G 算术乙：与 arith_halfgrid.py 不共享代码。

1. 20 tick 整数件数倒推台数、通道、接口 619；
2. 存货边权重：按“支持集类别台数（整数）+ 连续流量”聚合成 0-1/整数混合规划（scipy HiGHS），
   不假定半件极点；
3. 方向账常数、整数取整、面积式、A=1110 的桩数与外边段长表、合法尺寸。
"""
import json, os, math, itertools
from fractions import Fraction as Fr
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

out = {}
# ---------- 1. 20 tick 整数倒推 ----------
T20 = 20
BAT, CAP = 12, 11                      # 20 tick 内电池 12、胶囊 11
parts, dsrc = 10 * BAT, 15 * BAT       # 封装每批
bottles, fine = 10 * CAP, 10 * CAP     # 灌装每批
steel = parts + 2 * bottles
dfe = steel
grind = dfe + dsrc + fine
fe_pow, src_pow, qh_pow, sy_pow = 2 * dfe, 2 * dsrc, 2 * fine, grind
crush_batches = fe_pow + src_pow + qh_pow // 2 + sy_pow // 3
assert qh_pow % 2 == 0 and sy_pow % 3 == 0
refine_batches = fe_pow + dfe          # 蓝铁块 = 蓝铁粉末（r=0），钢块 = 致密蓝铁粉末
plant = 2 * (qh_pow // 2 + sy_pow // 3)
seed = qh_pow // 2 + sy_pow // 3
batches20 = {'粉碎机': crush_batches, '精炼炉': refine_batches, '研磨机': grind, '塑形机': bottles,
             '配件机': parts, '种植机': plant, '采种机': seed, '封装机': BAT, '灌装机': CAP}
ticks_per_batch = {'封装机': 5, '灌装机': 5}
machines = {k: -(-v * ticks_per_batch.get(k, 1) // T20) for k, v in batches20.items()}
in20 = {'粉碎机': crush_batches, '精炼炉': refine_batches, '研磨机': 3 * grind, '塑形机': 2 * bottles,
        '配件机': parts, '种植机': plant, '采种机': seed, '封装机': 25 * BAT, '灌装机': 20 * CAP}
outitems20 = {'粉碎机': fe_pow + src_pow + qh_pow + sy_pow, '精炼炉': refine_batches, '研磨机': grind,
              '塑形机': bottles, '配件机': parts, '种植机': plant, '采种机': 2 * seed, '封装机': BAT, '灌装机': CAP}
inch = {k: max(machines[k], -(-in20[k] // T20)) for k in machines}
outch_old = {k: max(machines[k] if k not in ('封装机', '灌装机') else 1, -(-outitems20[k] // T20)) for k in machines}
outch_new = dict(outch_old); outch_new['封装机'] = machines['封装机']; outch_new['灌装机'] = machines['灌装机']
ore20 = (refine_batches - dfe) + src_pow   # 蓝铁矿 + 源矿
footprint = {'粉碎机': 9, '精炼炉': 9, '配件机': 9, '塑形机': 9, '种植机': 25, '采种机': 25, '研磨机': 24, '封装机': 24, '灌装机': 24}
C = sum(inch.values()) + sum(outch_new.values()) + 46 + 6 + 2
out['twenty_tick'] = dict(machines=machines, total=sum(machines.values()),
                          area=sum(machines[k] * footprint[k] for k in machines),
                          ore_per_tick=ore20 / T20, in_channels=sum(inch.values()),
                          out_old=sum(outch_old.values()), out_new=sum(outch_new.values()), C=C)

# ---------- 2. 权重：支持集类别 MILP ----------
def supports(L):
    res = []
    for mask in range(1, 1 << L):
        pos = [i for i in range(L) if mask >> i & 1]
        alpha = []
        for k, i in enumerate(pos):
            a = (k > 0 and i - pos[k - 1] <= 3) + (k + 1 < len(pos) and pos[k + 1] - i <= 3)
            alpha.append(int(a))
        res.append((pos, alpha))
    return res

def weight_min(L, n, dmax, D):
    S = supports(L)
    # 变量：每个支持集 s 的台数 c_s（整数），以及该类各口聚合流量 F_{s,i}
    nv_c = len(S)
    fidx = []
    for s, (pos, al) in enumerate(S):
        for j in range(len(pos)):
            fidx.append((s, j))
    nv = nv_c + len(fidx)
    cost = np.zeros(nv)
    for k, (s, j) in enumerate(fidx):
        cost[nv_c + k] = S[s][1][j]
    A, lb, ub = [], [], []
    # sum c_s <= n
    r = np.zeros(nv); r[:nv_c] = 1; A.append(r); lb.append(0); ub.append(n)
    # 总流量 = D
    r = np.zeros(nv); r[nv_c:] = 1; A.append(r); lb.append(float(D)); ub.append(float(D))
    for s in range(nv_c):
        # 单类 intake <= dmax*c_s
        r = np.zeros(nv)
        for k, (ss, j) in enumerate(fidx):
            if ss == s: r[nv_c + k] = 1
        r[s] = -dmax; A.append(r); lb.append(-np.inf); ub.append(0)
        # 每口 F <= c_s
        for k, (ss, j) in enumerate(fidx):
            if ss == s:
                r = np.zeros(nv); r[nv_c + k] = 1; r[s] = -1
                A.append(r); lb.append(-np.inf); ub.append(0)
    integrality = np.concatenate([np.ones(nv_c), np.zeros(len(fidx))])
    res = milp(cost, constraints=LinearConstraint(np.array(A), lb, ub), integrality=integrality,
               bounds=Bounds(0, np.inf), options={'disp': False, 'mip_rel_gap': 0})
    assert res.status == 0, res.message
    return Fr(res.fun).limit_denominator(8), res

spec = {'研磨机': (6, 3, Fr(189, 2), 32), '塑形机': (3, 2, Fr(11), 6), '封装机': (6, 5, Fr(15), 3), '灌装机': (6, 4, Fr(11), 3)}
W = {}
tables = {}
for k, (L, dmax, D, n0) in spec.items():
    W[k] = weight_min(L, n0, dmax, D)[0]
    rows = []
    for n in range(n0, n0 + 18):
        v = weight_min(L, n, dmax, D)[0]
        rows.append([n, str(v)])
        if v == 0:
            break
    tables[k] = rows
formal = {
    '研磨机': lambda n: Fr(379 - 8 * n, 2) if n <= 47 else Fr(0),
    '塑形机': lambda n: Fr(max(0, 22 - 2 * n)),
    '封装机': lambda n: Fr({3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(n, 0)),
    '灌装机': lambda n: Fr({3: 14, 4: 6, 5: 2}.get(n, 0)),
}
for k, rows in tables.items():
    for n, v in rows:
        assert Fr(v) == formal[k](n), (k, n, v)
Wtot = sum(W.values())
area = {'研磨机': 24, '塑形机': 9, '封装机': 24, '灌装机': 24}
incr = {}
for k in tables:
    vals = [Fr(v) for _, v in tables[k]] + [Fr(0)] * 3
    incr[k] = min(4 * area[k] - (vals[i] - vals[i + 1]) for i in range(len(vals) - 1))
incr.update({'粉碎机/精炼炉/配件机': 36, '协议储存箱': 36, '种植机/采种机': 100})
out['weights'] = {k: str(v) for k, v in W.items()}
out['W_total'] = str(Wtot)
out['tables_match_formal'] = True
out['min_increment_4E_plus_Omega'] = {k: str(v) for k, v in incr.items()}

# ---------- 3. 方向账与取整 ----------
const = Fr(C) + 184 + 8 + Wtot + 88 + 4 - 91
out['direction_constant'] = str(const)
# 4(T+F)+2J 是偶数；对任意整数 s=X0+Y，最小偶数 >= const+s
def min_even_at_least(x):
    m = math.ceil(x)
    return m if m % 2 == 0 else m + 1
chk = []
for s in range(0, 200):
    for chi in (0, 1):
        X = s  # 这里 s 视作 X+Y，X0+Y = s-2chi
        lhs_min = min_even_at_least(const + s - 2 * chi)
        cand = 921 + s - chi
        orig = 921 + s
        chk.append((s, chi, lhs_min, lhs_min >= cand, lhs_min >= orig))
assert all(c[3] for c in chk)
out['rounding'] = {
    'candidate_holds_all': all(c[3] for c in chk),
    'original_fails_only_when': sorted(set((c[0] % 2, c[1]) for c in chk if not c[4])),
    'chi0_stronger_bound': '4(T+F)+2J >= 922+X+Y' if all(c[2] >= 922 + c[0] for c in chk if c[1] == 0) else None,
}
# 面积式：4(T+F) = 5560-4A-16P-4E；代入 lhs >= 922+X+Y-2chi
out['area'] = {'1390': 4900 - 3291 - 81 - 138, 'rhs_const': 4 * 1390 - 922,
               'chi1_with_E9': 4 * 1390 - 922 + 2 - 36}

# ---------- A=1110、桩数、尺寸 ----------
def legal(Aa):
    return [(w, Aa // w) for w in range(6, 69) if Aa % w == 0 and 6 <= Aa // w <= 68]
sizes = {a: legal(a) for a in range(1100, 1120)}
out['legal_sizes'] = {str(a): v for a, v in sizes.items() if v}
pj = []
for P in range(10, 20):
    for J in range(0, P + 1):
        if 23 * P - 10 * J < 217 or 54 * P - 25 * J < 520:
            continue
        budget = 4751 - 4 * 1110 - 16 * P + 2 * J        # >= 4E+Omega
        xy = 4639 - 4 * 1110 - 16 * P + 2 * J             # >= X+Y（无增配）
        pj.append((P, J, budget, xy))
out['P_J_1110'] = pj
out['max_P_feasible_noextra'] = max(P for P, J, b, xy in pj if xy >= 0 and b >= Wtot)
out['P13_J_min'] = min(J for P, J, b, xy in pj if P == 13 and xy >= 0)
out['P12_J0_xy'] = [xy for P, J, b, xy in pj if P == 12 and J == 0]
out['extra_allowed'] = [(P, J, b) for P, J, b, xy in pj if b >= Wtot + 34]
out['A_max_with_extra'] = str(Fr(4751 - 160) - (Wtot + 34)) + '/4'
# 外边段长：L <= 6X0+14c+8t+5k
edge = {}
for name, L, k, tmax in [('both', 71, 2, 1), ('one', 101, 3, 2), ('none', 138, 2, 2)]:
    def minX(t):
        for X0 in range(0, 200):
            if L <= 6 * X0 + 14 * 1 + 8 * t + 5 * k:
                return X0
    edge[name] = {'no_extra': minX(0), 'one_extra': minX(tmax)}
out['edge_X0_lower'] = edge
# 30x37 的 L 与 k 直接数（角格两次）
def edge_slots(W_, H_, a, b):
    slots = [(69, y) for y in range(1, 70)] + [(x, 69) for x in range(1, 70)]
    cov = [s for s in slots if a <= s[0] < a + W_ and b <= s[1] < b + H_]
    return len(slots) - len(cov)
Ls = {'both': set(), 'one': set(), 'none': set()}
for (W_, H_) in [(30, 37), (37, 30)]:
    for a in range(4, 70 - W_ + 1):
        for b in range(4, 70 - H_ + 1):
            tr = a + W_ - 1 == 69; tt = b + H_ - 1 == 69
            key = 'both' if tr and tt else ('one' if tr or tt else 'none')
            Ls[key].add(edge_slots(W_, H_, a, b))
out['edge_L_min'] = {k: min(v) for k, v in Ls.items()}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'arith_milp.json'), 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: out[k] for k in ('twenty_tick', 'weights', 'W_total', 'min_increment_4E_plus_Omega', 'direction_constant', 'rounding', 'area', 'legal_sizes', 'max_P_feasible_noextra', 'P13_J_min', 'P12_J0_xy', 'extra_allowed', 'A_max_with_extra', 'edge_X0_lower', 'edge_L_min')}, ensure_ascii=False, default=str))

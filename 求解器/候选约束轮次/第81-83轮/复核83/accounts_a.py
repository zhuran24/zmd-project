#!/usr/bin/env python3
"""复核83 编码甲：配方收支（C1）、在产下限与加权（C2）、多通道机器下限（C3）、
存货边方向权重函数 f（C5）、A>=1110 标量分支（C6）、A4 区间、B1 首件死锁枚举。
全部用 Fraction 精确算；配方从快照规则解析。"""
import re, json, itertools, math
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULE = (HERE.parent / '前提快照' / '《明日方舟：终末地》游戏规则.txt').read_text()
out = {}

# ---------- 配方解析 ----------
lines = RULE.splitlines()
i0 = lines.index('配方')
recipes = []  # (machine, inputs{item:n}, outputs{item:n}, dur)
mach = None
for s in lines[i0 + 1:]:
    s = s.strip()
    if not s:
        continue
    if '→' not in s:
        mach = s
        continue
    lhs, rhs = s.split('→')
    rhs, dur = rhs.rsplit('，', 1)
    def parse(side):
        d = {}
        for part in side.split('＋'):
            n, it = part.strip().split(' ', 1)
            d[it.strip()] = int(n)
        return d
    recipes.append((mach, parse(lhs), parse(rhs), int(dur.replace('tick', '').strip())))
items = sorted({k for r in recipes for k in list(r[1]) + list(r[2])})
out['recipes'] = len(recipes)
out['items'] = len(items)

# ---------- C1：周期收支 ----------
# 未知量：18 个配方批率。方程：每种物品 产出-消耗 = 外送（成品）- 取入（矿）
BAT, CAP = '高容谷地电池', '精选荞愈胶囊'
ext = {it: Fr(0) for it in items}
ext[BAT] = Fr(3, 5)
ext[CAP] = Fr(11, 20)
ext['蓝铁矿'] = Fr(-34)
ext['源矿'] = Fr(-18)
A = [[Fr(r[2].get(it, 0) - r[1].get(it, 0)) for r in recipes] for it in items]
b = [ext[it] for it in items]
# 高斯消元求秩与通解
M = [row[:] + [bb] for row, bb in zip(A, b)]
nr, nc = len(M), len(recipes)
piv = []
r0 = 0
for c in range(nc):
    p = next((i for i in range(r0, nr) if M[i][c] != 0), None)
    if p is None:
        continue
    M[r0], M[p] = M[p], M[r0]
    pv = M[r0][c]
    M[r0] = [v / pv for v in M[r0]]
    for i in range(nr):
        if i != r0 and M[i][c] != 0:
            f = M[i][c]
            M[i] = [a - f * bb for a, bb in zip(M[i], M[r0])]
    piv.append(c)
    r0 += 1
rank = r0
consistent = all(any(v != 0 for v in M[i][:nc]) or M[i][nc] == 0 for i in range(nr))
free = [c for c in range(nc) if c not in piv]
out['C1_rank'] = rank
out['C1_consistent'] = consistent
out['C1_free'] = [f'{recipes[c][0]}:{list(recipes[c][1])}' for c in free]
# 以自由量 r 表示每个配方率：x_piv = rhs - coef*r
sol = {}
for i, c in enumerate(piv):
    const = M[i][nc]
    coef = {f: -M[i][f] for f in free}
    sol[c] = (const, coef)
for f in free:
    sol[f] = (Fr(0), {f: Fr(1)})
per_machine = {}
for c, (const, coef) in sol.items():
    m = recipes[c][0]
    k0, k1 = per_machine.get(m, (Fr(0), Fr(0)))
    per_machine[m] = (k0 + const, k1 + sum(coef.values()))
out['C1_machine_rates(const,r_coef)'] = {m: [str(v[0]), str(v[1])] for m, v in per_machine.items()}
# 物理出货：配方产出件数 + 52 矿
outflow_const = sum(sol[c][0] * sum(recipes[c][2].values()) for c in sol) + 52
outflow_r = sum(sum(sol[c][1].values()) * sum(recipes[c][2].values()) for c in sol)
out['C1_physical_outflow'] = [str(outflow_const), str(outflow_r)]
# 物品流量（产出侧）
item_rate = {}
for it in items:
    k0 = sum(sol[c][0] * recipes[c][2].get(it, 0) for c in sol)
    k1 = sum(sum(sol[c][1].values()) * recipes[c][2].get(it, 0) for c in sol)
    item_rate[it] = [str(k0), str(k1)]
out['C1_item_production'] = item_rate

# ---------- C2：在产下限 ----------
maxrate = {m: Fr(1, d) for (m, _, _, d) in recipes}  # 每台每 tick 至多批数
inprod = {m: math.ceil(per_machine[m][0] / maxrate[m]) for m in per_machine}
out['C2_inprod_min'] = inprod
size = {'粉碎机': 'S', '精炼炉': 'S', '配件机': 'S', '塑形机': 'S', '种植机': 'M', '采种机': 'M',
        '研磨机': 'L', '封装机': 'L', '灌装机': 'L'}
wt = {'S': 2, 'M': 3, 'L': 3}
out['C2_counts_by_size'] = {z: sum(inprod[m] for m in inprod if size[m] == z) for z in 'SML'}
out['C2_min_weight'] = sum(wt[size[m]] * inprod[m] for m in inprod)
out['C2_P10_J'] = [J for J in range(0, 11) if 54 * 10 - 25 * J >= out['C2_min_weight']]

# ---------- C3 ----------
def c3(n_yan, n_su, n_feng, n_guan, n_cai):
    return [max(0, math.ceil(Fr(189, 2) - 2 * n_yan)), max(0, 11 - n_su), max(0, 15 - 4 * n_feng),
            max(0, 11 - 3 * n_guan), max(0, 32 - n_cai)]
out['C3_min'] = c3(32, 6, 3, 3, 16)
out['C3_plus1'] = c3(33, 7, 4, 4, 17)

# ---------- C5：方向权重 f ----------
def machine_w(E, Fmax, F):
    """一台机器存货边长 E、总流量 F（<=Fmax）时的最小方向权重：穷举端口支持，闭包 LP 贪心。"""
    best = None
    for s in range(1, E + 1):
        for sup in itertools.combinations(range(E), s):
            if s > F * 1 + 1e-12 and False:
                pass
            if F > s:  # 每口至多 1
                continue
            c = []
            for idx, p in enumerate(sup):
                k = 0
                if idx > 0 and p - sup[idx - 1] <= 3:
                    k += 1
                if idx < s - 1 and sup[idx + 1] - p <= 3:
                    k += 1
                c.append(k)
            # 最小化 sum c_p f_p，sum f_p = F，0<=f_p<=1：便宜的先填满
            rem = F
            val = Fr(0)
            for k in sorted(c):
                t = min(Fr(1), rem)
                val += k * t
                rem -= t
            if rem > 0:
                continue
            if best is None or val < best:
                best = val
    return best

def f_table(E, Fmax, total, nmin, nmax, step):
    grid = [Fr(i, step) for i in range(0, Fmax * step + 1)]
    w = {F: machine_w(E, Fmax, F) for F in grid}
    res = {}
    # DP: dp[n][flow] = min weight; flow 以 1/step 为单位，最多 total
    T = int(total * step)
    INF = None
    dp = {0: Fr(0)}
    for n in range(1, nmax + 1):
        nd = {}
        for fl, v in dp.items():
            for F in grid:
                g = min(T, fl + int(F * step))
                nv = v + w[F]
                if g not in nd or nv < nd[g]:
                    nd[g] = nv
        dp = nd
        if n >= nmin:
            res[n] = dp.get(T)
    return res, {str(F): str(w[F]) for F in grid}

tabs = {}
for name, E, Fmax, total, nmin, nmax in [('研磨机', 6, 3, Fr(189, 2), 32, 49), ('塑形机', 3, 2, Fr(11), 6, 12),
                                          ('封装机', 6, 5, Fr(15), 3, 9), ('灌装机', 6, 4, Fr(11), 3, 7)]:
    r2, w2 = f_table(E, Fmax, total, nmin, nmax, 2)
    r4, _ = f_table(E, Fmax, total, nmin, nmax, 4) if name != '研磨机' else f_table(E, Fmax, total, nmin, min(nmax, 36), 4)
    tabs[name] = {'half': {n: str(v) for n, v in r2.items()}, 'quarter': {n: str(v) for n, v in r4.items()}, 'w_half': w2}
out['C5_f'] = tabs
def claimed_f(name, n):
    if name == '研磨机':
        return Fr(379 - 8 * n, 2) if n <= 47 else Fr(0)
    if name == '塑形机':
        return Fr(max(0, 22 - 2 * n))
    if name == '封装机':
        return Fr({3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(n, 0))
    if name == '灌装机':
        return Fr({3: 14, 4: 6, 5: 2}.get(n, 0))
out['C5_match_claim'] = {name: all(Fr(v) == claimed_f(name, n) for n, v in tabs[name]['half'].items()) for name in tabs}
out['C5_quarter_equals_half'] = {name: all(tabs[name]['quarter'][n] == tabs[name]['half'][n] for n in tabs[name]['quarter']) for name in tabs}
Omega0 = sum(claimed_f(nm, n) for nm, n in [('研磨机', 32), ('塑形机', 6), ('封装机', 3), ('灌装机', 3)])
out['C5_Omega_min'] = str(Omega0)
area = {'粉碎机': 9, '精炼炉': 9, '配件机': 9, '塑形机': 9, '种植机': 25, '采种机': 25, '研磨机': 24, '封装机': 24, '灌装机': 24, '协议储存箱': 9}
base = {'研磨机': 32, '塑形机': 6, '封装机': 3, '灌装机': 3}
first = {}
for m in area:
    dO = (claimed_f(m, base[m] + 1) - claimed_f(m, base[m])) if m in base else 0
    first[m] = str(4 * area[m] + dO)
out['C5_first_extra_cost'] = first

# ---------- C6 ----------
br = []
for P in range(10, 19):
    for J in range(0, P + 1):
        if 25 * J > 54 * P - 520 or 9 * J > 23 * P - 217:
            continue
        lim = 4751 - 4 * 1110 - 16 * P + 2 * J   # 4E+Omega 上限（X0=Y0=0）
        br.append((P, J, lim))
out['C6_max_4E+Omega'] = max(l for _, _, l in br)
out['C6_max_4E+Omega_P>=11'] = max(l for P, _, l in br if P >= 11)
# X0 下界：L <= 6X0 + 14c + 8t + 5k
def x0min(L, k, t, c=1):
    return max(0, math.ceil(Fr(L - 14 * c - 8 * t - 5 * k, 6)))
W, H = 30, 37
out['C6_X0'] = {'both': x0min(138 - W - H, 2, 1), 'one_W': x0min(138 - W, 3, 2), 'one_H': x0min(138 - H, 3, 2),
                'none': x0min(138, 2, 2), 'both_t0(P12J0)': x0min(138 - W - H, 2, 0)}
# 最小配置无箱：4A+16P-2J+X+Y<=4639
rem = []
for P in range(10, 19):
    for J in range(0, P + 1):
        if 25 * J > 54 * P - 520 or 9 * J > 23 * P - 217:
            continue
        xy = 4639 - 4 * 1110 - 16 * P + 2 * J
        if xy >= 0:
            rem.append((P, J, xy))
out['C6_minconfig_branches_1110'] = rem
def sides(Aa):
    return [(a, Aa // a) for a in range(6, 69) if Aa % a == 0 and a <= Aa // a <= 68]
out['C6_sides'] = {A_: sides(A_) for A_ in range(1105, 1114)}

# ---------- A4 ----------
a4 = {}
for name, a, bb in [('研磨机', 2, 1), ('封装机', 10, 15), ('灌装机', 10, 10)]:
    g = math.gcd(a, bb)
    Z0 = 50 * (bb - a)
    Lo = bb * (a - 1) - 50 * a
    Up = 50 * bb - a * (bb - 1)
    C = min(Z0 - Lo, Up - Z0)
    per = a * bb // g
    a4[name] = {'Z0': Z0, 'L': Lo, 'U': Up, 'C': C, 'ab/g': per,
                'max_m_full': max(m for m in range(0, 40) if m * per < C),
                'max_m_mid': max(m for m in range(0, 40) if 2 * m * per < C)}
out['A4'] = a4

# ---------- B1：首件死锁（含误料首件的检查） ----------
def head_deadlocks(inputs_sets, nslots, include_wrong_heads):
    kinds = sorted({k for r in inputs_sets for k in r})
    heads_univ = kinds + (['误料'] if include_wrong_heads else [])
    states = set()
    opts = [None] + [(k, c) for k in kinds for c in range(1, 51)]
    for combo in itertools.product(opts, repeat=nslots):
        ks = [x[0] for x in combo if x]
        if len(ks) != len(set(ks)):
            continue
        states.add(tuple(sorted(combo, key=lambda x: ('~',) if x is None else x)))
    res = []
    for st in states:
        have = {x[0]: x[1] for x in st if x}
        if any(all(have.get(k, 0) >= n for k, n in r.items()) for r in inputs_sets):
            continue
        # 两种主料同格（研磨机）另算
        mains = [k for k in have if k != '砂叶粉末']
        if len(inputs_sets) == 3 and len(mains) >= 2:
            continue
        full = all(x is not None for x in st)
        refused = []
        for h in heads_univ:
            if h in have:
                if have[h] >= 50:
                    refused.append(h)
            else:
                if full:
                    refused.append(h)
        for s in range(1, len(refused) + 1):
            for H_ in itertools.combinations(refused, s):
                res.append((st, H_))
    return res
rec_by = {}
for m, ins, _, _ in recipes:
    rec_by.setdefault(m, []).append(ins)
b1 = {}
for m in ['研磨机', '封装机', '灌装机']:
    no_w = head_deadlocks(rec_by[m], 2, False)
    with_w = head_deadlocks(rec_by[m], 2, True)
    extra = [x for x in with_w if '误料' in x[1]]
    b1[m] = {'no_wrong_heads': len(no_w), 'with_wrong_heads': len(with_w), 'combos_with_wrong_head': len(extra),
             'example_wrong_head': [list(map(list, [y for y in extra[0][0] if y])), list(extra[0][1])] if extra else None}
for m in ['塑形机', '粉碎机', '精炼炉', '配件机', '种植机', '采种机']:
    b1[m] = {'no_wrong_heads': len(head_deadlocks(rec_by[m], 1, False)),
             'with_wrong_heads': len(head_deadlocks(rec_by[m], 1, True))}
out['B1'] = b1

print(json.dumps(out, ensure_ascii=False, indent=1, default=str))

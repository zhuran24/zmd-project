#!/usr/bin/env python3
"""复核109S2B 算术（自写，两套编码互核）：台数、占地、供电权、Ω、面积上界、流量守恒、备料当量。"""
import json
from fractions import Fraction as Fr
from itertools import product

from engine_x import wiring, RECIPES, AREA

out = {}
# ---------- 编码一：由 engine_x.wiring 的接法图计数 ----------
M, P = wiring()
kind_to_type = {'OS': '精炼炉', 'R': '精炼炉', 'IC': '粉碎机', 'SC': '粉碎机', 'Ks': '粉碎机', 'Kq': '粉碎机',
                'B': '研磨机', 'O': '研磨机', 'Q': '研磨机', 'P': '配件机', 'H': '塑形机',
                'As': '种植机', 'Aq': '种植机', 'Cs': '采种机', 'Cq': '采种机', 'E': '封装机', 'F': '灌装机'}
cnt = {}
for m, k in M.items():
    cnt[kind_to_type[k]] = cnt.get(kind_to_type[k], 0) + 1
area1 = sum(AREA[k] for k in M.values())
size = {'粉碎机': 's', '精炼炉': 's', '配件机': 's', '塑形机': 's', '种植机': 'm', '采种机': 'm',
        '研磨机': 'l', '封装机': 'l', '灌装机': 'l'}
ns = sum(v for t, v in cnt.items() if size[t] == 's')
nm = sum(v for t, v in cnt.items() if size[t] == 'm')
nl = sum(v for t, v in cnt.items() if size[t] == 'l')
out['enc1'] = {'counts': cnt, 'total': len(M), 'area': area1, 'paths': len(P), 'small_mid_large': [ns, nm, nl]}

# ---------- 编码二：按条文直接写数 ----------
c2 = {'粉碎机': 34 + 18 + 13 + 6, '精炼炉': 34 + 17, '研磨机': 17 + 9 + 6, '塑形机': 6, '配件机': 6,
      '种植机': 2 * 19, '采种机': 19, '封装机': 3, '灌装机': 4}
a2 = {'s': 9, 'm': 25, 'l': 24}
area2 = sum(v * a2[size[t]] for t, v in c2.items())
paths2 = (52 + 34 + 34 + 18 + 17 + 17 + 6 + 9 + 6 + 6 + 7 + 4 * 19
          + sum(len(g) for g in [[1]*3, [1]*2, [1]*3, [1]*2, [1]*3, [1]*2, [1]*3, [1]*3, [1]*3, [1]*3, [1]*3, [1], [1]])
          + 5 * 2 + 1)
out['enc2'] = {'counts': c2, 'total': sum(c2.values()), 'area': area2, 'paths': paths2}
assert c2 == cnt and area1 == area2 and len(P) == paths2

# ---------- 正式下限与 E、Ω ----------
mins = {'粉碎机': 68, '精炼炉': 51, '研磨机': 32, '塑形机': 6, '配件机': 6, '种植机': 32, '采种机': 16, '封装机': 3, '灌装机': 3}
minarea = sum(v * a2[size[t]] for t, v in mins.items())
E = area1 - minarea
def omega(nyan, nsu, nfeng, nguan):
    fy = Fr(379 - 8 * nyan, 2) if nyan <= 47 else Fr(0)
    fs = max(0, 22 - 2 * nsu)
    ff = {3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(nfeng, 0)
    fg = {3: 14, 4: 6, 5: 2}.get(nguan, 0)
    return fy + fs + ff + fg
Om = omega(cnt['研磨机'], cnt['塑形机'], cnt['封装机'], cnt['灌装机'])
w = 2 * ns + 3 * (nm + nl)
out['formal'] = {'minarea': minarea, 'E': E, 'Omega': str(Om), 'power_weight': w}

# ---------- 供电 P、J 可行集与面积上界（两种写法） ----------
def pj_feasible():
    res = []
    for Pn in range(10, 20):
        for J in range(0, Pn + 1):
            if 23 * Pn - 10 * J >= len(M) and 54 * Pn - 25 * J >= w and 10 * J <= 23 * Pn - 217:
                res.append((Pn, J))
    return res
feas = pj_feasible()
def best_A(extra_SR):
    # 编码一：4A+16P-2J+4E+Ω ≤ 4751 - extra_SR
    best = None
    for Pn, J in feas:
        A = (Fr(4751 - extra_SR) - 16 * Pn + 2 * J - 4 * E - Om) / 4
        if best is None or A > best[0]:
            best = (A, Pn, J)
    return best
def best_A2(SR):
    # 编码二：占地恒等式 A+F+T+4P = 4900-机身-81-138，4(T+F)+2J ≥ SR+90+8+Ω+88+4，T+F 取整
    import math
    best = None
    rest = 4900 - area1 - 81 - 138
    for Pn, J in feas:
        need = Fr(SR + 90 + 8 + 88 + 4) + Om - 2 * J
        TF = math.ceil(need / 4)
        A = rest - 4 * Pn - TF
        if best is None or A > best[0]:
            best = (A, Pn, J, TF)
    return best
def max_rect(Amax):
    best = None
    for a in range(6, 69):
        for b in range(a, 69):
            if a * b <= Amax and (best is None or a * b > best[0] or (a * b == best[0] and a > best[1])):
                best = (a * b, a, b)
    return best
b619 = best_A(0); b650 = best_A(650 - 619)
c619 = best_A2(619); c650 = best_A2(650)
out['area'] = {
    'feasible_PJ_first': feas[:6],
    'enc1_619': [str(b619[0]), b619[1], b619[2], max_rect(int(b619[0]))],
    'enc1_650': [str(b650[0]), b650[1], b650[2], max_rect(int(b650[0]))],
    'enc2_619_intA': [c619[0], c619[1], c619[2], 'T+F>=%d' % c619[3], max_rect(c619[0])],
    'enc2_650_intA': [c650[0], c650[1], c650[2], 'T+F>=%d' % c650[3], max_rect(c650[0])],
    'T_lower_650': None,
    'transport_axis_cells_max': 2 * (4900 - area1 - 81 - 138),
}
import math
out['area']['T_lower_650'] = math.ceil((Fr(650 + 90 + 8) + Om) / 4)
out['area']['pure_belt_A_plus_F_max_P11'] = 4900 - area1 - 81 - 138 - 44 - 333

# ---------- 流量守恒 ----------
b, c = Fr(3, 5), Fr(11, 20)
x = 30 * b
y = 20 * b + 40 * c
# 逐机批次率：由成品倒推（每台的需求）
sand = 17 * 1 + 9 * 1 + 5 * 1 + Fr(1, 2)  # B1-B17 满速、O 满速、Q1-Q5 满速、Q6 半速
qh_pow = 5 * 2 + 1
out['flow'] = {'src_ore': str(x), 'iron_ore': str(y), 'sand_powder': str(sand), 'qh_powder': str(qh_pow),
               'capsule_sum': str(Fr(1, 5) + Fr(1, 5) + Fr(1, 10) + Fr(1, 20)), 'battery_sum': str(3 * Fr(1, 5))}
assert x == 18 and y == 34 and Fr(1, 5) * 2 + Fr(1, 10) + Fr(1, 20) == c

# ---------- 备料当量（编码一：逐机；编码二：按机群公式） ----------
EQ = {
    '砂叶': (1, 0, 0, 0), '砂叶种子': (1, 0, 0, 0), '砂叶粉末': (Fr(1, 3), 0, 0, 0),
    '荞花': (0, 1, 0, 0), '荞花种子': (0, 1, 0, 0), '荞花粉末': (0, Fr(1, 2), 0, 0),
    '蓝铁矿': (0, 0, 1, 0), '蓝铁块': (0, 0, 1, 0), '蓝铁粉末': (0, 0, 1, 0),
    '源矿': (0, 0, 0, 1), '源石粉末': (0, 0, 0, 1),
}
def eqv(item):
    if item in EQ:
        return tuple(Fr(v) for v in EQ[item])
    for k, (ins, (o, q), d) in RECIPES.items():
        if o == item:
            tot = [Fr(0)] * 4
            for i, n in ins.items():
                e = eqv(i)
                tot = [t + n * v for t, v in zip(tot, e)]
            return tuple(t / q for t, v in zip(tot, tot))
    raise KeyError(item)
cap = [Fr(0)] * 4
for m, k in M.items():
    ins, (o, q), d = RECIPES[k]
    fin = o in ('高容谷地电池', '精选荞愈胶囊')
    for i in ins:
        cap = [a + 50 * v for a, v in zip(cap, eqv(i))]
    if not fin:
        cap = [a + 50 * v for a, v in zip(cap, eqv(o))]
        bin_ = [sum(n * eqv(i)[j] for i, n in ins.items()) for j in range(4)]
        bout = [q * eqv(o)[j] for j in range(4)]
        cap = [a + max(x1, x2) for a, x1, x2 in zip(cap, bin_, bout)]
cellmax = [max(eqv(i)[j] for i in list(EQ) + ['致密蓝铁粉末', '钢块', '钢制零件', '钢质瓶', '致密源石粉末', '细磨荞花粉末']) for j in range(4)]
tot = [a + 4900 * mx for a, mx in zip(cap, cellmax)]
items = list(EQ) + ['致密蓝铁粉末', '钢块', '钢制零件', '钢质瓶', '致密源石粉末', '细磨荞花粉末']
budget = {}
for it in items:
    e = eqv(it)
    budget[it] = int(min(tot[j] / e[j] for j in range(4) if e[j] > 0))
out['startup'] = {'machine_cap': [str(v) for v in cap], 'cell_max': [str(v) for v in cellmax],
                  'total_cap_4900': [str(v) for v in tot], 'budget': budget}
# 编码二：机群公式（手写每类机器的三项当量）
def grp():
    s = Fr(0); q = Fr(0); fe = Fr(0); sr = Fr(0)
    th = Fr(1, 3)
    s += 17 * (50 * th + 50 * th + th) + 9 * (50 * th + 50 * th + th) + 6 * (50 * th + 50 * th + th)  # B,O,Q
    s += 17 * (50 * th * 2 + th) + 6 * (50 * th * 2 + th) + 6 * (50 * th + 100 * th + 2 * th)          # R,P,H
    s += 3 * (100 * th) + 4 * (100 * th + 50 * th) + 13 * 102 + 26 * 101 + 13 * (50 + 50 * th + 1)   # E,F,Cs,As,Ks
    q += 6 * (25 + 50 + 1) + 4 * 50 + 6 * 102 + 12 * 101 + 6 * (50 + 25 + 1)
    fe += 34 * 101 * 2 + 17 * (50 + 100 + 2) + 17 * (100 + 100 + 2) + 6 * 202 + 6 * (100 + 200 + 4) + 3 * 100 + 4 * 200
    sr += 18 * 101 + 9 * (50 + 100 + 2) + 3 * 100
    return [s, q, fe, sr]
g = grp()
out['startup']['machine_cap_enc2'] = [str(v) for v in g]
assert g == cap, (g, cap)
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open('arith_x.json', 'w'), ensure_ascii=False, indent=1)

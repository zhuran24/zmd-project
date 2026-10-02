#!/usr/bin/env python3
"""复核100S2：报告第4.4、9节及速率上界的数字，两套独立编码互核。

甲：按机型手写公式（Fraction）。
乙：从 net.build() 的物料图自动展开：物品当量按配方递归，机器容量逐台加总；速率按路容量逐台求上界。
"""
import json
from fractions import Fraction as Fr
from math import floor
from net import build, SIZE

M, S, P = build()

# ---------------- 乙：自动展开 ----------------
# 四种原料当量：砂叶系(植株与种子各1)、荞花系、蓝铁矿、源矿。由配方逆推（植物配方不计入当量守恒，按定义赋值）。
BASE = {'砂叶': (1, 0, 0, 0), '砂叶种子': (1, 0, 0, 0), '荞花': (0, 1, 0, 0), '荞花种子': (0, 1, 0, 0),
        '蓝铁矿': (0, 0, 1, 0), '源矿': (0, 0, 0, 1)}
recipes = {}
for m in M.values():
    if m['role'] in ('C', 'A', 'B'):
        continue
    recipes.setdefault(m['product'], (m['inputs'], m['qty']))


def eq(item, memo={}):
    if item in BASE:
        return tuple(Fr(x) for x in BASE[item])
    if item in memo:
        return memo[item]
    ins, q = recipes[item]
    tot = [Fr(0)] * 4
    for k, a in ins.items():
        e = eq(k)
        for i in range(4):
            tot[i] += a * e[i]
    memo[item] = tuple(x / q for x in tot)
    return memo[item]


def machine_bound_b(m):
    tot = [Fr(0)] * 4
    if m['role'] == 'final':
        for k in m['inputs']:
            e = eq(k)
            for i in range(4):
                tot[i] += 50 * e[i]
        return tot
    for k in m['inputs']:
        e = eq(k)
        for i in range(4):
            tot[i] += 50 * e[i]
    ep = eq(m['product'])
    for i in range(4):
        tot[i] += 50 * ep[i]
    cin = [sum(a * eq(k)[i] for k, a in m['inputs'].items()) for i in range(4)]
    cout = [m['qty'] * ep[i] for i in range(4)]
    for i in range(4):
        tot[i] += max(cin[i], cout[i])
    return tot


inv_b = [sum(machine_bound_b(m)[i] for m in M.values()) for i in range(4)]
items = sorted(set(k for m in M.values() for k in m['inputs']) | set(m['product'] for m in M.values() if m['role'] != 'final'))
cell_max_b = [max(eq(k)[i] for k in items) for i in range(4)]
total_b = [inv_b[i] + 4900 * cell_max_b[i] for i in range(4)]
spare_b = {}
for k in items:
    e = eq(k)
    spare_b[k] = min(floor(total_b[i] / e[i]) for i in range(4) if e[i] > 0)

# ---------------- 甲：按机型手写 ----------------
t3 = Fr(1, 3)
inv_a = [
    # 砂叶系：13个砂叶单元（C 50+50+2，A、B 各101，K 50+50/3+1），研磨机、精炼炉、配件机、塑形机、成品机
    13 * (102 + 101 + 101 + 50 + Fr(50, 3) + 1) + 17 * Fr(101, 3) + 9 * Fr(101, 3) + 6 * Fr(101, 3)
    + 17 * Fr(101, 3) + 6 * Fr(101, 3) + 6 * Fr(152, 3) + 3 * Fr(100, 3) + 4 * Fr(150, 3),
    # 荞花系：6个荞花单元（K 50+25+1），Q 25+50+1，F 50
    6 * (102 + 101 + 101 + 76) + 6 * 76 + 4 * 50,
    # 蓝铁矿：矿石精炼炉、铁粉碎、B、R、P、H、E、F
    34 * 101 + 34 * 101 + 17 * 152 + 17 * 202 + 6 * 202 + 6 * 304 + 3 * 100 + 4 * 200,
    # 源矿：源矿粉碎、O、E
    18 * 101 + 9 * 152 + 3 * 100,
]
cell_max_a = [1, 1, 4, 2]
total_a = [inv_a[i] + 4900 * cell_max_a[i] for i in range(4)]
report_table = {'源矿': 13286, '源石粉末': 13286, '砂叶': 12187, '砂叶种子': 12187, '砂叶粉末': 36562,
                '细磨荞花粉末': 7836, '致密源石粉末': 6643, '致密蓝铁粉末': 18311, '荞花': 7836,
                '荞花种子': 7836, '荞花粉末': 15672, '蓝铁块': 36622, '蓝铁矿': 36622, '蓝铁粉末': 36622,
                '钢制零件': 18311, '钢块': 18311, '钢质瓶': 9155}

# 全部备用件由配方制出时的原料（同种中间物合并计算后取整）
need_sl_powder = sum(report_table[k] * (eq(k)[0] * 3 if k != '砂叶粉末' else 1)
                     for k in report_table if k not in ('砂叶', '砂叶种子', '源矿', '蓝铁矿', '荞花', '荞花种子'))
raw = dict(砂叶=report_table['砂叶'] + -(-need_sl_powder // 3),
           荞花=report_table['荞花'] + sum(report_table[k] * eq(k)[1] for k in ('荞花粉末', '细磨荞花粉末')),
           蓝铁矿=sum(report_table[k] * eq(k)[2] for k in report_table),
           源矿=sum(report_table[k] * eq(k)[3] for k in report_table))

# ---------------- 速率上界：每条纯带 ≤1 件/tick ----------------
paths_in = {}
for p in P:
    paths_in.setdefault(p['dst'], []).append(p)
nout = {}
for p in P:
    nout[p['src']] = nout.get(p['src'], 0) + 1
rate = {}


def mrate(name):
    """该机器每 tick 批次上界。"""
    if name in rate:
        return rate[name]
    m = M[name]
    r = Fr(8, m['dur'])
    if m['role'] in ('C', 'A', 'B', 'K'):
        rate[name] = Fr(1)  # 采种单元满库存每 tick 一批（上界）
        return rate[name]
    for k, a in m['inputs'].items():
        sup = Fr(0)
        for p in paths_in.get(name, []):
            if p['kind'] != k:
                continue
            if p['src'] in S:
                sup += 1
            else:
                src = M[p['src']]
                sup += min(Fr(1), mrate(p['src']) * src['qty'] / nout[p['src']])
        r = min(r, sup / a)
    rate[name] = r
    return r


bat = sum(mrate(n) for n, m in M.items() if m['product'] == '高容谷地电池')
cap = sum(mrate(n) for n, m in M.items() if m['product'] == '精选荞愈胶囊')

# 守恒：x=30b，y=20b+40c
x, y = 30 * bat, 20 * bat + 40 * cap

# ---------------- 面积 ----------------
body = {'small': 9, 'medium': 25, 'large': 24}
bodies = sum(body[SIZE[m['type']]] for m in M.values())
cnt = {}
for m in M.values():
    cnt[m['type']] = cnt.get(m['type'], 0) + 1
minimum = {'粉碎机': 68, '精炼炉': 51, '研磨机': 32, '塑形机': 6, '配件机': 6, '种植机': 32, '采种机': 16, '封装机': 3, '灌装机': 3}
E_excess = sum((cnt[t] - minimum[t]) * body[SIZE[t]] for t in cnt)
small = sum(1 for m in M.values() if SIZE[m['type']] == 'small')
med = sum(1 for m in M.values() if SIZE[m['type']] == 'medium')
large = sum(1 for m in M.values() if SIZE[m['type']] == 'large')
wpow = 2 * small + 3 * (med + large)
nm = len(M)
f_yan = Fr(379 - 8 * cnt['研磨机'], 2)
f_su = max(0, 22 - 2 * cnt['塑形机'])
f_feng = {3: 24, 4: 18, 5: 10, 6: 6, 7: 2}[cnt['封装机']]
f_guan = {3: 14, 4: 6, 5: 2}[cnt['灌装机']]
Omega = f_yan + f_su + f_feng + f_guan
best = None
for Pp in range(10, 301):
    for J in range(0, Pp + 1):
        if 23 * Pp - 10 * J >= nm and 54 * Pp - 25 * J >= wpow:
            A = (Fr(4751) - 16 * Pp + 2 * J - 4 * E_excess - Omega) / 4
            if best is None or A > best[0]:
                best = (A, Pp, J)
Amax = best[0]
best_rect = max(a * b for a in range(6, 69) for b in range(6, 69) if a * b <= Amax)
Pmin = min(Pp for Pp in range(10, 301) if any(23 * Pp - 10 * J >= nm and 54 * Pp - 25 * J >= wpow for J in range(Pp + 1)))
T = len(P) + 8
A_pure = 4900 - bodies - 81 - 46 * 3 - 4 * Pmin - T
rects = sorted({(a, b) for a in range(6, 69) for b in range(a, 69) if a * b == A_pure})

out = dict(
    inventory_bound_a=[str(v) for v in inv_a], inventory_bound_b=[str(v) for v in inv_b],
    report_inventory=['21862/3', '2936', '17022', '3486'],
    cell_max_a=cell_max_a, cell_max_b=[str(v) for v in cell_max_b],
    total_a=[str(v) for v in total_a], total_b=[str(v) for v in total_b],
    spare_b=spare_b, spare_match_report=all(spare_b[k] == report_table[k] for k in report_table),
    raw_from_recipes={k: str(v) for k, v in raw.items()},
    report_raw=dict(砂叶=53615, 荞花=23508, 蓝铁矿=256352, 源矿=39858),
    rate_upper_battery=str(bat), rate_upper_capsule=str(cap), ore_x=str(x), ore_y=str(y),
    machines=nm, paths=len(P), bodies=bodies, E_excess=E_excess, power_weight=wpow,
    Omega=str(Omega), direction_budget_best=dict(A=str(Amax), P=best[1], J=best[2]),
    best_rect_under_direction_budget=best_rect, Pmin=Pmin, T_min=T, A_pure_belt=A_pure, rects=rects,
)
out['agree_inventory'] = [str(a) for a in inv_a] == [str(b) for b in inv_b]
out['agree_total'] = [str(a) for a in total_a] == [str(b) for b in total_b]
json.dump(out, open('arith_check.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))

#!/usr/bin/env python3
"""复核97G 算术甲：配方倒推、通道与接口计数；存货边权重按每口 {0,1/2,1} 流量向量 + 机群半件背包 DP。

全部用 Fraction，不用浮点。与 arith_milp.py 不共享代码。
"""
from fractions import Fraction as Fr
from itertools import product
import json, os, math

# ---------- 配方与机型下限 ----------
# 目标每 tick：高容谷地电池 0.6，精选荞愈胶囊 0.55
bat, cap = Fr(3, 5), Fr(11, 20)
# 封装：10 钢制零件 + 15 致密源石粉末 -> 1 电池，5 tick
# 灌装：10 钢质瓶 + 10 细磨荞花粉末 -> 1 胶囊，5 tick
part = 10 * bat; dsrc = 15 * bat
bottle = 10 * cap; fine = 10 * cap
steel = part + 2 * bottle          # 配件 1:1，塑形 2:1
dense_fe = steel                   # 精炼：1 致密蓝铁粉末 -> 1 钢块
# 研磨：2 主料 + 1 砂叶粉末 -> 1
grind_batches = dense_fe + dsrc + fine
fe_powder = 2 * dense_fe           # r=0
src_powder = 2 * dsrc
qh_powder = 2 * fine
sy_powder = grind_batches
fe_block = fe_powder               # 粉碎：1 蓝铁块 -> 1 蓝铁粉末
fe_ore = fe_block                  # 精炼：1 蓝铁矿 -> 1 蓝铁块
src_ore = src_powder
qh_crush = qh_powder / 2           # 1 荞花 -> 2 荞花粉末
sy_crush = sy_powder / 3
# 种子回路：采种 1 株 -> 2 种子；种植 1 种子 -> 1 株；稳态 种植 = 2*采种，株净产 = 采种 批数
qh_seedbatches = qh_crush          # 株净 = 种植 - 采种 = 2a - a = a
sy_seedbatches = sy_crush
rates = {
    '粉碎机': fe_block + src_ore + qh_crush + sy_crush,
    '精炼炉': fe_ore + dense_fe,
    '研磨机': grind_batches,
    '塑形机': bottle,
    '配件机': part,
    '种植机': 2 * (qh_seedbatches + sy_seedbatches),
    '采种机': qh_seedbatches + sy_seedbatches,
    '封装机': bat,
    '灌装机': cap,
}
dur = {k: 1 for k in rates}; dur['封装机'] = 5; dur['灌装机'] = 5
need = {k: math.ceil(rates[k] * dur[k]) for k in rates}
area = {'粉碎机': 9, '精炼炉': 9, '配件机': 9, '塑形机': 9, '种植机': 25, '采种机': 25, '研磨机': 24, '封装机': 24, '灌装机': 24}
ore = fe_ore + src_ore
# 存货通道：每台在产机至少 1 条，且机群收料总量/1
inputs_per_batch = {'粉碎机': 1, '精炼炉': 1, '研磨机': 3, '塑形机': 2, '配件机': 1, '种植机': 1, '采种机': 1, '封装机': 25, '灌装机': 20}
outputs_per_batch_total = {
    '粉碎机': fe_block * 1 + src_ore * 1 + qh_crush * 2 + sy_crush * 3,
    '精炼炉': fe_ore + dense_fe, '研磨机': grind_batches, '塑形机': bottle, '配件机': part,
    '种植机': 2 * (qh_seedbatches + sy_seedbatches), '采种机': 2 * (qh_seedbatches + sy_seedbatches),
    '封装机': bat, '灌装机': cap}
in_ch = {k: max(need[k], math.ceil(rates[k] * inputs_per_batch[k])) for k in rates}
out_ch = {k: max(need[k], math.ceil(outputs_per_batch_total[k])) for k in rates}
out_ch_orig = dict(out_ch); out_ch_orig['封装机'] = 1; out_ch_orig['灌装机'] = 1
C = sum(in_ch.values()) + sum(out_ch.values()) + 52 + 2

# ---------- 存货边权重 ----------
def edge_table(L):
    """每个 intake d（半件）在长度 L 的存货边上的最小权重，枚举每口 {0,1/2,1}。"""
    best = {}
    for f in product((Fr(0), Fr(1, 2), Fr(1)), repeat=L):
        pos = [i for i in range(L) if f[i] > 0]
        w = Fr(0)
        for k, i in enumerate(pos):
            a = 0
            if k > 0 and i - pos[k - 1] <= 3: a += 1
            if k + 1 < len(pos) and pos[k + 1] - i <= 3: a += 1
            w += a * f[i]
        d = sum(f)
        if d not in best or w < best[d]:
            best[d] = w
    return best

def group_min(table, n, dmax, D):
    """n 台、每台 intake 0..dmax（半件），总 intake 恰 D 的最小总权。半件单位整数背包。"""
    units = int(D * 2)
    opts = [(int(d * 2), w) for d, w in table.items() if d <= dmax]
    INF = None
    cur = {0: Fr(0)}
    for _ in range(n):
        nxt = {}
        for s, v in cur.items():
            for du, w in opts:
                t = s + du
                if t > units: continue
                nv = v + w
                if t not in nxt or nv < nxt[t]:
                    nxt[t] = nv
        cur = nxt
    return cur.get(units)

t6, t3 = edge_table(6), edge_table(3)
spec = {'研磨机': (t6, 3, Fr(189, 2), 32), '塑形机': (t3, 2, Fr(11), 6), '封装机': (t6, 5, Fr(15), 3), '灌装机': (t6, 4, Fr(11), 3)}
W = {k: group_min(t, n, dm, D) for k, (t, dm, D, n) in spec.items()}
Wtot = sum(W.values())
# 逐台表（直到降为 0）
tables = {}
for k, (t, dm, D, n0) in spec.items():
    rows = []
    n = n0
    while True:
        v = group_min(t, n, dm, D)
        rows.append([n, str(v)])
        if v == 0 or n > n0 + 20: break
        n += 1
    tables[k] = rows

# ---------- 方向账与取整 ----------
I_band = 137; O = 46; U = I_band - O
dir_sum = C + (4 * O) + 8 + Wtot + (U - 3) + 4 - 91   # 不含 2J、X、Y
res = {
    'rates': {k: str(v) for k, v in rates.items()}, 'need': need, 'machines': sum(need.values()),
    'area': sum(need[k] * area[k] for k in need), 'ore_per_tick': str(ore),
    'in_channels': in_ch, 'in_total': sum(in_ch.values()), 'out_channels_orig_total': sum(out_ch_orig.values()),
    'out_total': sum(out_ch.values()), 'C': C,
    'W_by_type': {k: str(v) for k, v in W.items()}, 'W_total': str(Wtot),
    'weight_tables': tables,
    'U_cells': U, 'direction_constant': str(dir_sum),
    'four_T_lower': str(C + 4 * O - 91 + 8 + Wtot), 'T_lower': math.ceil(C + 4 * O - 91 + 8 + Wtot) // 4 + (1 if (C + 4 * O - 91 + 8 + Wtot) % 4 else 0),
}
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'arith_halfgrid.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ('need', 'machines', 'area', 'ore_per_tick', 'in_total', 'out_channels_orig_total', 'out_total', 'C', 'W_by_type', 'W_total', 'direction_constant', 'four_T_lower')}, ensure_ascii=False))
for k, v in tables.items(): print(k, v)

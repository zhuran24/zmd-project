#!/usr/bin/env python3
"""第 89 轮复核：从前提快照重算配方收支、机型下限、Φ 常数、骨架台数与接口，并核清单里同文条目。
只读 ../前提快照/ 与 ../修正版清单.json；不导入任何其他席位的脚本。输出 JSON 到 stdout。"""
import json, re, hashlib, math, sys
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
SNAP = ROUND / '前提快照'
out = {}

# ---------- 快照哈希 ----------
out['sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SNAP.glob('*.txt'))}
out['sha256']['修正版清单.json'] = hashlib.sha256((ROUND / '修正版清单.json').read_bytes()).hexdigest()

# ---------- 解析配方 ----------
rules = (SNAP / '《明日方舟：终末地》游戏规则.txt').read_text(encoding='utf-8')
sec = rules.split('配方', 3)[-1]
recipes = []
cur = None
for line in rules.splitlines():
    s = line.strip()
    if s in ('粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机') and '→' not in s:
        cur = s
        continue
    m = re.match(r'^(.*)→\s*(\d+)\s*(\S+?)，\s*(\d+)\s*tick$', s)
    if m and cur:
        lhs = m.group(1)
        ins = {}
        for part in re.split(r'＋|\+', lhs):
            part = part.strip()
            mm = re.match(r'^(\d+)\s*(\S+)$', part)
            ins[mm.group(2)] = int(mm.group(1))
        recipes.append({'machine': cur, 'in': ins, 'out': (m.group(3), int(m.group(2))), 'd': int(m.group(4))})
out['recipes_parsed'] = len(recipes)
assert len(recipes) == 18, len(recipes)

items = sorted({k for r in recipes for k in r['in']} | {r['out'][0] for r in recipes})
out['items'] = len(items)
ores = {'源矿', '蓝铁矿'}
demand = {'高容谷地电池': F(3, 5), '精选荞愈胶囊': F(11, 20)}

# 未知量：18 个配方批次率。方程：每种非矿物品 净产 = 需求（仓库外不积累、非成品零入库、矿系不入库）。
# 自由度来自 蓝铁块 两条来路（蓝铁矿 / 蓝铁粉末回炼），把回炼批次率 r 作参数。
def solve(rval):
    idx = {i: n for n, i in enumerate(range(len(recipes)))}
    rec_r = [n for n, r in enumerate(recipes) if r['machine'] == '精炼炉' and '蓝铁粉末' in r['in']][0]
    eqs = []
    for it in items:
        if it in ores:
            continue
        row = [F(0)] * len(recipes)
        for n, r in enumerate(recipes):
            if r['out'][0] == it:
                row[n] += r['out'][1]
            if it in r['in']:
                row[n] -= r['in'][it]
        eqs.append((row, demand.get(it, F(0))))
    row = [F(0)] * len(recipes); row[rec_r] = F(1)
    eqs.append((row, F(rval)))
    # 高斯消元
    A = [r[:] + [b] for r, b in eqs]
    ncol = len(recipes)
    piv = []
    rrow = 0
    for c in range(ncol):
        p = next((i for i in range(rrow, len(A)) if A[i][c] != 0), None)
        if p is None:
            continue
        A[rrow], A[p] = A[p], A[rrow]
        pv = A[rrow][c]
        A[rrow] = [x / pv for x in A[rrow]]
        for i in range(len(A)):
            if i != rrow and A[i][c] != 0:
                f = A[i][c]
                A[i] = [x - f * y for x, y in zip(A[i], A[rrow])]
        piv.append(c); rrow += 1
    assert len(piv) == ncol, ('rank', len(piv))
    for i in range(rrow, len(A)):
        assert A[i][-1] == 0, 'inconsistent'
    x = [F(0)] * ncol
    for i, c in enumerate(piv):
        x[c] = A[i][-1]
    return x

x0 = solve(0)
assert all(v >= 0 for v in x0)
work = {}
for n, r in enumerate(recipes):
    work[r['machine']] = work.get(r['machine'], F(0)) + x0[n] * r['d']
order = ['粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机']
out['workload_r0'] = {m: str(work[m]) for m in order}
out['lower_bounds'] = {m: math.ceil(work[m]) for m in order}
assert [math.ceil(work[m]) for m in order] == [68, 51, 32, 6, 6, 32, 16, 3, 3]
x1 = solve(1)
work1 = {}
for n, r in enumerate(recipes):
    work1[r['machine']] = work1.get(r['machine'], F(0)) + x1[n] * r['d']
out['workload_r1_minus_r0'] = {m: str(work1[m] - work[m]) for m in order}

# ---------- Φ 受阻界常数 ----------
cap = 50
stuck = F(cap) + 1 + cap + cap + 1 + F(cap - 1, 2)   # A存、A缓存、A取、C存、C缓存、C取≥49 的一半（再加 L1+L2）
out['stuck_bound_minus_L'] = str(stuck)
out['stuck_bound_minus_half'] = str(stuck - F(1, 2))
assert stuck - F(1, 2) == 176

# ---------- 清单同文 ----------
lst = json.loads((ROUND / '修正版清单.json').read_text(encoding='utf-8'))
out['n_items'] = len(lst)
groups = {}
for n, it in enumerate(lst):
    groups.setdefault(it['text'], []).append(n)
out['identical_text_groups'] = [g for g in groups.values() if len(g) > 1]

# ---------- 全厂骨架：逐台建图 ----------
M = []   # (name, type, recipe-key)
E = []   # (src, dst, item)
def add(name, typ):
    M.append((name, typ)); return name
ore_lines = []
for j in range(34):
    rf = add(f'R{j}', '精炼炉'); cr = add(f'KB{j}', '粉碎机')
    ore_lines.append(('W', rf, '蓝铁矿')); E.append((rf, cr, '蓝铁块'))
for j in range(18):
    cr = add(f'KY{j}', '粉碎机'); ore_lines.append(('W', cr, '源矿'))
units = []
for u in range(17):
    kind = '砂叶' if u < 11 else '荞花'
    C = add(f'C{u}', '采种机'); A = add(f'A{u}', '种植机'); B = add(f'B{u}', '种植机'); K = add(f'K{u}', '粉碎机')
    E += [(C, A, kind + '种子'), (C, B, kind + '种子'), (A, C, kind), (B, K, kind)]
    units.append((kind, K))
GB = [add(f'GB{j}', '研磨机') for j in range(17)]
GY = [add(f'GY{j}', '研磨机') for j in range(9)]
GQ = [add(f'GQ{j}', '研磨机') for j in range(6)]
for j in range(17):
    E += [(f'KB{2*j}', GB[j], '蓝铁粉末'), (f'KB{2*j+1}', GB[j], '蓝铁粉末')]
for j in range(9):
    E += [(f'KY{2*j}', GY[j], '源石粉末'), (f'KY{2*j+1}', GY[j], '源石粉末')]
sandK = [K for kind, K in units if kind == '砂叶']
qiaoK = [K for kind, K in units if kind == '荞花']
grinders = GB + GY + GQ
for n, g in enumerate(grinders):              # 32 条砂叶粉末出口，每台 K 至多 3 条
    E.append((sandK[n // 3], g, '砂叶粉末'))
for j in range(6):
    E += [(qiaoK[j], GQ[j], '荞花粉末'), (qiaoK[j], GQ[j], '荞花粉末')]
RS = [add(f'RS{j}', '精炼炉') for j in range(17)]
for j in range(17):
    E.append((GB[j], RS[j], '致密蓝铁粉末'))
PJ = [add(f'PJ{j}', '配件机') for j in range(6)]
SX = [add(f'SX{j}', '塑形机') for j in range(6)]
for j in range(6):
    E.append((RS[j], PJ[j], '钢块'))
for j in range(5):
    E += [(RS[6 + 2*j], SX[j], '钢块'), (RS[7 + 2*j], SX[j], '钢块')]
E.append((RS[16], SX[5], '钢块'))
FZ = [add(f'FZ{j}', '封装机') for j in range(3)]
GZ = [add(f'GZ{j}', '灌装机') for j in range(3)]
for j in range(3):
    E += [(PJ[2*j], FZ[j], '钢制零件'), (PJ[2*j+1], FZ[j], '钢制零件')]
    E += [(GY[3*j + i], FZ[j], '致密源石粉末') for i in range(3)]
E += [(SX[0], GZ[0], '钢质瓶'), (SX[1], GZ[0], '钢质瓶'), (GQ[0], GZ[0], '细磨荞花粉末'), (GQ[1], GZ[0], '细磨荞花粉末')]
E += [(SX[2], GZ[1], '钢质瓶'), (SX[3], GZ[1], '钢质瓶'), (GQ[2], GZ[1], '细磨荞花粉末'), (GQ[3], GZ[1], '细磨荞花粉末')]
E += [(SX[4], GZ[2], '钢质瓶'), (SX[5], GZ[2], '钢质瓶'), (GQ[4], GZ[2], '细磨荞花粉末'), (GQ[5], GZ[2], '细磨荞花粉末')]
prod_lines = [(m, 'CORE', '成品') for m in FZ + GZ]
cnt = {}
for _, t in M:
    cnt[t] = cnt.get(t, 0) + 1
out['skeleton_counts'] = {m: cnt[m] for m in order}
assert [cnt[m] for m in order] == [69, 51, 32, 6, 6, 34, 17, 3, 3]
body = {'粉碎机': 9, '精炼炉': 9, '配件机': 9, '塑形机': 9, '研磨机': 24, '封装机': 24, '灌装机': 24, '种植机': 25, '采种机': 25}
out['skeleton_machines'] = len(M)
out['skeleton_body_cells'] = sum(body[t] for _, t in M)
out['skeleton_logical_paths'] = len(E) + len(ore_lines) + len(prod_lines)
indeg = {}; outdeg = {}
for s, d, _ in E + ore_lines + prod_lines:
    outdeg[s] = outdeg.get(s, 0) + 1; indeg[d] = indeg.get(d, 0) + 1
out['sand_K_exits'] = [outdeg[k] for k in sandK]
out['qiao_K_exits'] = [outdeg[k] for k in qiaoK]
# 传递前提逐台核：d*c_i >= a_i；源头出口数 <= 每批件数
rec_of = {'精炼炉': None}
need = {
    'R': ('蓝铁矿', {'蓝铁矿': 1}, 1), 'KB': ('蓝铁块', {'蓝铁块': 1}, 1), 'KY': ('源矿', {'源矿': 1}, 1),
    'GB': (None, {'蓝铁粉末': 2, '砂叶粉末': 1}, 1), 'GY': (None, {'源石粉末': 2, '砂叶粉末': 1}, 1),
    'GQ': (None, {'荞花粉末': 2, '砂叶粉末': 1}, 1), 'RS': (None, {'致密蓝铁粉末': 1}, 1),
    'PJ': (None, {'钢块': 1}, 1), 'SX': (None, {'钢块': 2}, 1), 'FZ': (None, {'钢制零件': 10, '致密源石粉末': 15}, 5),
    'GZ': (None, {'钢质瓶': 10, '细磨荞花粉末': 10}, 5)}
batch_out = {'R': 1, 'KB': 1, 'KY': 1, 'GB': 1, 'GY': 1, 'GQ': 1, 'RS': 1, 'PJ': 1, 'SX': 1, 'C': 2, 'A': 1, 'B': 1}
relay_fail = []
for name, typ in M:
    pre = re.match(r'[A-Z]+', name).group(0)
    if pre not in need:
        continue
    _, ins, d = need[pre]
    for it, a in ins.items():
        c = sum(1 for s, dd, i2 in E + ore_lines if dd == name and (i2 == it or (it in ('蓝铁矿', '源矿') and i2 == it)))
        if d * c < a:
            relay_fail.append((name, it, d, c, a))
out['relay_dc_ge_a_failures'] = relay_fail   # 期望只有 SX5（单路塑形）
src_fail = []
for name, typ in M:
    pre = re.match(r'[A-Z]+', name).group(0)
    k = batch_out.get(pre)
    if pre == 'K':
        k = 3 if name in sandK else 2
    if k is not None and outdeg.get(name, 0) > k:
        src_fail.append((name, outdeg[name], k))
out['source_exits_gt_batch'] = src_fail
# 产率（按复核文中的推导，把每台 1tick 机的上限 1 批/tick 代入）
batt = 3 * F(1, 5)
bottles_third = F(1) + F(1, 2)
caps = 2 * F(1, 5) + bottles_third / 10
out['rates'] = {'battery': str(batt), 'capsule': str(caps)}
assert batt == F(3, 5) and caps == F(11, 20)
sand_need = 17 + 9 + 4 + 2 * F(3, 4)
out['sand_powder_need'] = str(sand_need)
out['iron_ore_lines'] = sum(1 for l in ore_lines if l[2] == '蓝铁矿')
out['source_ore_lines'] = sum(1 for l in ore_lines if l[2] == '源矿')
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print()

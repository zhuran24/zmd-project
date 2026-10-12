#!/usr/bin/env python3
"""块7-1 最便宜试法的第一步：第四张全厂候选（独立）固定机位下，接法按物料匿名重配时
运输格数下界和固定机位阻断数各能降到多少。只读仓库文件，不改动。
口径与 check_static.py 的「固定机位的运输格数必要条件」「fixed_geometry_obstructed」相同，
只是把逐路固定的 (source,target) 换成同物料内任意配对（每台机器的出入进路条数不变）。"""
import json, sys, importlib.util
from collections import defaultdict, deque, Counter
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

REPO = Path('/home/zhuran24/zmd-research-fresh/求解器/构造/第四张全厂候选/独立')
spec = importlib.util.spec_from_file_location('cs', REPO / '代码' / 'check_static.py')
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)
D = cs.D
d = json.loads((REPO / '布局.json').read_text()); l = d['layout']
em, ef = cs.expected()
units = {}
typ = {}
for g in ['machines', 'warehouse_outlets', 'power_poles', 'storage_boxes', 'transport']:
    for u in l[g]: units[u['id']] = u; typ[u['id']] = g
units['CORE'] = l['core']; typ['CORE'] = 'core'
trans = {u['id'] for u in l['transport']}
occ = {}
for n, u in units.items():
    for c in cs.cells(u): occ[c] = n
body = {c for c, n in occ.items() if n not in trans}
cfg = {(p['side'], p['offset']): p['item'] for p in l['core']['output_items']}
ports = {}
def port(u, side, off, mode):
    if side == 0: x, y = u['x1'], u['y0'] + off
    elif side == 2: x, y = u['x0'], u['y0'] + off
    elif side == 1: x, y = u['x0'] + off, u['y1']
    else: x, y = u['x0'] + off, u['y0']
    ports[(u['id'], side, off)] = (x, y, mode)
for n, u in units.items():
    g = typ[n]
    if g == 'machines':
        for side, mode in [(u['Din'], 1), ((u['Din'] + 2) % 4, 2)]:
            for off in range(u['y1'] - u['y0'] + 1 if side % 2 == 0 else u['x1'] - u['x0'] + 1): port(u, side, off, mode)
    elif g == 'warehouse_outlets': port(u, u['Dout'], 1, 2)
    elif g == 'core':
        for side in [u['Din'], (u['Din'] + 2) % 4]:
            for off in range(1, 8): port(u, side, off, 1)
        for (side, off), it in cfg.items(): port(u, side, off, 2)
comp = {}; ci = 0
for x in range(70):
    for y in range(70):
        if (x, y) in body or (x, y) in comp: continue
        ci += 1; comp[x, y] = ci; q = deque([(x, y)])
        while q:
            a, b = q.popleft()
            for dx, dy in D:
                z = (a + dx, b + dy)
                if 0 <= z[0] < 70 and 0 <= z[1] < 70 and z not in body and z not in comp: comp[z] = ci; q.append(z)
pts = defaultdict(list); comps = defaultdict(set)
# 与 check_static.py 同口径：端口外侧格不论是否被机身占着都计入距离（只会更低估）；连通分量只看空格
for p, (x, y, mode) in ports.items():
    dx, dy = D[p[1]]; c = (x + dx, y + dy)
    pts[p[0], mode].append(c)
    if c in comp: comps[p[0], mode].add(comp[c])
def dist(s, t):
    aa, bb = pts[s, 2], pts[t, 1]
    if not aa or not bb: return None
    return min(abs(x - z) + abs(y - w) + 1 for x, y in aa for z, w in bb)
BIG = 10 ** 6
fixed_sum = 0; fixed_none = 0
for s, t, it, q in ef:
    v = dist(s, t)
    if v is None: fixed_none += 1
    else: fixed_sum += v
fixed_obs = sum(1 for s, t, it, q in ef if not comps[s, 2] & comps[t, 1])
PLANT = {'砂叶种子', '荞花种子', '砂叶', '荞花'}
def anon(keep_fixed):
    groups = defaultdict(list); total = 0; obs = 0; per = {}
    for s, t, it, q in ef:
        if it in keep_fixed:
            v = dist(s, t); total += v if v is not None else 0
            obs += 0 if comps[s, 2] & comps[t, 1] else 1
        else: groups[it].append((s, t))
    for it, fs in groups.items():
        S = [s for s, t in fs]; T = [t for s, t in fs]
        n = len(fs); C = np.full((n, n), BIG, dtype=np.int64); R = np.ones((n, n), dtype=np.int64)
        cache = {}
        for i, s in enumerate(S):
            for j, t in enumerate(T):
                if s == t: continue
                k = (s, t)
                if k not in cache: cache[k] = dist(s, t)
                if cache[k] is not None: C[i, j] = cache[k]
                if comps[s, 2] & comps[t, 1]: R[i, j] = 0
        r, c = linear_sum_assignment(C); v = int(C[r, c].sum())
        r2, c2 = linear_sum_assignment(R); o = int(R[r2, c2].sum())
        per[it] = (n, v, o); total += v; obs += o
    return total, obs, per
slot_upper = 2 * (4900 - len(body) - 36)
print('body', len(body), 'slot_upper', slot_upper)
print('fixed pairing: length lower bound', fixed_sum, 'missing ports', fixed_none, 'obstructed', fixed_obs)
for name, keep in [('all items anonymous', set()), ('plant routes kept fixed', PLANT)]:
    tot, obs, per = anon(keep)
    print(name, ': length lower bound', tot, 'obstructed lower bound', obs)
    for it, (n, v, o) in sorted(per.items(), key=lambda z: -z[1][1]): print('   ', it, 'routes', n, 'min sum', v, 'unmatched-in-component', o)

# 端口边整条被非运输单位（机身、核心、取货口、供电桩）堵死的单位，以及因此必断的进路
walled = set()
for (n, mode), cl in list(pts.items()):
    if not comps[n, mode]: walled.add((n, mode))
dead = [(s, t, it) for s, t, it, q in ef if (s, 2) in walled or (t, 1) in walled]
print('walled unit-sides', len(walled), sorted(walled)[:40])
print('routes with a walled endpoint', len(dead), Counter(it for s, t, it in dead))

# 保守口径：植物回路、荞花粉末（同一粉碎机两路进同一研磨机）、灌装机两种原料、砂叶粉末分组都按原接法不动，只换其余
CONS = PLANT | {'荞花粉末', '钢质瓶', '细磨荞花粉末', '砂叶粉末'}
tot, obs, per = anon(CONS)
print('conservative (only ore/iron/steel/source chains and products anonymous): length lower bound', tot, 'obstructed lower bound', obs)

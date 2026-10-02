#!/usr/bin/env python3
"""运输物品格数的必要条件：机位不动时，325 条进路各至少需要（起终外侧格曼哈顿距离+1）格，
不同进路不共用物品格，总和不能超过 2×(4900−非运输占格−36)。矿路来源按任意指派取最小（比固定指派更宽）。
用法：python3 cellcount.py 布局.json 输出.json"""
import json, sys, collections
D = json.load(open(sys.argv[1])); L = D['layout']
def edge(b, s):
    x0, y0, x1, y1 = b
    if s == 0: return [(x1 + 1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0 - 1, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1 + 1) for x in range(x0, x1 + 1)]
    return [(x, y0 - 1) for x in range(x0, x1 + 1)]
mach = {m['id']: m for m in L['machines']}
def mb(m): return (m['x0'], m['y0'], m['x1'], m['y1'])
outc = {k: edge(mb(m), (m['Din'] + 2) % 4) for k, m in mach.items()}
inc = {k: edge(mb(m), m['Din']) for k, m in mach.items()}
c = L['core']; cb = (c['x0'], c['y0'], c['x1'], c['y1'])
inc['CORE'] = [e for s in (c['Din'], (c['Din'] + 2) % 4) for i, e in enumerate(edge(cb, s)) if 1 <= i <= 7]
src = {'蓝铁矿': [], '源矿': [], 'CORE': []}
for o in L['warehouse_outlets']:
    src[o['item']].append((1, o['y0'] + 1) if o['Dout'] == 0 else (o['x0'] + 1, 1))
for e in c['output_items']: src['CORE'].append(edge(cb, e['side'])[e['offset']])
def inb(p): return 0 <= p[0] < 70 and 0 <= p[1] < 70
req = []
for i in range(1, 35): req += [('蓝铁矿', f'T{i}'), (f'T{i}', f'KB{i}')]
for i in range(1, 18): req += [(f'KB{2*i-1}', f'B{i}'), (f'KB{2*i}', f'B{i}'), (f'B{i}', f'R{i}')]
for j in range(1, 19): req.append(('CORE' if j <= 6 else '源矿', f'U{j}'))
for i in range(1, 10): req += [(f'U{2*i-1}', f'O{i}'), (f'U{2*i}', f'O{i}')]
for i in range(1, 7): req.append((f'R{i}', f'P{i}'))
for h in range(1, 6): req += [(f'R{2*h+5}', f'H{h}'), (f'R{2*h+6}', f'H{h}')]
req.append(('R17', 'H6'))
for e in range(1, 4):
    req += [(f'P{2*e-1}', f'E{e}'), (f'P{2*e}', f'E{e}')] + [(f'O{o}', f'E{e}') for o in range(3*e-2, 3*e+1)]
req += [('H1','F1'),('H2','F1'),('Q1','F1'),('Q2','F1'),('H3','F2'),('H4','F2'),('Q3','F2'),('Q4','F2'),('H5','F3'),('Q5','F3'),('H6','F4'),('Q6','F4')]
req += [(x, 'CORE') for x in ['E1','E2','E3','F1','F2','F3','F4']]
for p, k, n in (('S', 'S', 13), ('Q', 'KQ', 6)):
    for i in range(1, n + 1): req += [(f'{p}C{i}', f'{p}A{i}'), (f'{p}C{i}', f'{p}B{i}'), (f'{p}A{i}', f'{p}C{i}'), (f'{p}B{i}', f'{k}{i}')]
sand = {1: ['B1','B2','O1'], 2: ['O2','O3'], 3: ['B3','B4','O4'], 4: ['O5','O6'], 5: ['B5','B6','O7'], 6: ['O8','O9'], 7: ['B7','B8','B9'],
        8: ['B10','Q1','Q2'], 9: ['B11','B12','B13'], 10: ['B14','Q3','Q4'], 11: ['B15','B16','Q5'], 12: ['B17'], 13: ['Q6']}
for s_, ts in sand.items(): req += [(f'S{s_}', t) for t in ts]
for q in range(1, 6): req += [(f'KQ{q}', f'Q{q}')] * 2
req.append(('KQ6', 'Q6'))
assert len(req) == 325
tot = 0
for s, t in req:
    S = src.get(s) or outc[s]
    T = inc[t]
    S = [a for a in S if inb(a)] or S; T = [b for b in T if inb(b)] or T
    tot += min(abs(a[0] - b[0]) + abs(a[1] - b[1]) + 1 for a in S for b in T)
nont = 0
own = set()
for g in (L['machines'], L['warehouse_outlets'], L['power_poles'], [L['core']]):
    for u in g:
        own |= {(x, y) for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)}
cap = 2 * (4900 - len(own) - 36)
res = dict(进路下界总和=tot, 非运输占格=len(own), 物品格容量上界=cap, 超出=tot > cap)
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1); print(res)

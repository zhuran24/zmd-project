#!/usr/bin/env python3
"""矿石进路的来源可任意指派时，撤去全部运输单位后最多能接几条：二分图最大匹配。
用法：python3 ore_matching.py 布局.json 输出.json"""
import json, sys
D = json.load(open(sys.argv[1])); L = D['layout']; N = 70
occ = set()
def rect(u): return [(x, y) for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)]
for g in (L['machines'], L['warehouse_outlets'], L['power_poles'], [L['core']]):
    for u in g: occ |= set(rect(u))
def free(c): return 0 <= c[0] < N and 0 <= c[1] < N and c not in occ
comp = {}; k = 0
for x in range(N):
    for y in range(N):
        if free((x, y)) and (x, y) not in comp:
            k += 1; st = [(x, y)]; comp[(x, y)] = k
            while st:
                cx, cy = st.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (cx + dx, cy + dy)
                    if free(n) and n not in comp: comp[n] = k; st.append(n)
def edge(b, s):
    x0, y0, x1, y1 = b
    if s == 0: return [(x1 + 1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0 - 1, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1 + 1) for x in range(x0, x1 + 1)]
    return [(x, y0 - 1) for x in range(x0, x1 + 1)]
mach = {m['id']: m for m in L['machines']}
def incomps(uid):
    m = mach[uid]
    return {comp[c] for c in edge((m['x0'], m['y0'], m['x1'], m['y1']), m['Din']) if free(c)}
srcs = {}
for o in L['warehouse_outlets']:
    c = (1, o['y0'] + 1) if o['Dout'] == 0 else (o['x0'] + 1, 1)
    srcs[o['id']] = (o['item'], {comp[c]} if free(c) else set())
c = L['core']; b = (c['x0'], c['y0'], c['x1'], c['y1'])
for e in c['output_items']:
    cell = edge(b, e['side'])[e['offset']]
    srcs[f'CORE:{e["side"]},{e["offset"]}'] = ('核心', {comp[cell]} if free(cell) else set())
def match(S, T):
    adj = {s: [t for t in T if srcs[s][1] & incomps(t)] for s in S}
    mt = {}
    def aug(s, seen):
        for t in adj[s]:
            if t in seen: continue
            seen.add(t)
            if t not in mt or aug(mt[t], seen):
                mt[t] = s; return True
        return False
    return sum(aug(s, set()) for s in S), [s for s in S if not srcs[s][1]]
res = {}
for name, S, T in (('蓝铁矿口->T1..T34', [s for s, v in srcs.items() if v[0] == '蓝铁矿'], [f'T{i}' for i in range(1, 35)]),
                   ('源矿口->U7..U18', [s for s, v in srcs.items() if v[0] == '源矿'], [f'U{i}' for i in range(7, 19)]),
                   ('核心口->U1..U6', [s for s, v in srcs.items() if v[0] == '核心'], [f'U{i}' for i in range(1, 7)])):
    m, blocked = match(S, T)
    res[name] = dict(要求=len(T), 最大匹配=m, 端口外侧被非运输单位占的来源=blocked)
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
for k_, v in res.items(): print(k_, v)

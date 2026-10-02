#!/usr/bin/env python3
"""缺路能否靠只改运输单位补出：撤去全部运输单位，非运输单位不动。
一条缺路要能补，必须有起点取货端口与终点存货端口，它们外侧格在界内、不被非运输单位占，且在空格四连通图中连通。
三条有一条不满足即补不出。用法：python3 obstruct.py 布局.json 编码一结果.json 输出.json"""
import json, sys, collections
D = json.load(open(sys.argv[1])); R = json.load(open(sys.argv[2]))
L = D['layout']
N = 70
occ = {}
def rect(u): return [(x, y) for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)]
for m in L['machines']:
    for c in rect(m): occ[c] = m['id']
for o in L['warehouse_outlets']:
    for c in rect(o): occ[c] = o['id']
for c in rect(L['core']): occ[c] = 'CORE'
for p in L['power_poles']:
    for c in rect(p): occ[c] = p['id']
ST = [(1, 0), (0, 1), (-1, 0), (0, -1)]
def edge(b, s):
    x0, y0, x1, y1 = b
    if s == 0: return [(x1 + 1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0 - 1, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1 + 1) for x in range(x0, x1 + 1)]
    return [(x, y0 - 1) for x in range(x0, x1 + 1)]
def free(c): return 0 <= c[0] < N and 0 <= c[1] < N and c not in occ
# 连通分量
comp = {}
k = 0
for x in range(N):
    for y in range(N):
        if free((x, y)) and (x, y) not in comp:
            k += 1; st = [(x, y)]; comp[(x, y)] = k
            while st:
                cx, cy = st.pop()
                for dx, dy in ST:
                    n = (cx + dx, cy + dy)
                    if free(n) and n not in comp: comp[n] = k; st.append(n)
mach = {m['id']: m for m in L['machines']}
def outcells(uid):
    m = mach[uid]; b = (m['x0'], m['y0'], m['x1'], m['y1'])
    return edge(b, (m['Din'] + 2) % 4)
def incells(uid):
    if uid == 'CORE':
        c = L['core']; b = (c['x0'], c['y0'], c['x1'], c['y1'])
        return [e for s in (c['Din'], (c['Din'] + 2) % 4) for i, e in enumerate(edge(b, s)) if 1 <= i <= 7]
    m = mach[uid]; b = (m['x0'], m['y0'], m['x1'], m['y1'])
    return edge(b, m['Din'])
def srccells(s):
    if s.startswith('OUTLET:'):
        it = s.split(':')[1]
        return [((1, o['y0'] + 1) if o['Dout'] == 0 else (o['x0'] + 1, 1)) for o in L['warehouse_outlets'] if o['item'] == it]
    if s == 'COREPORT':
        c = L['core']; b = (c['x0'], c['y0'], c['x1'], c['y1'])
        return [e for s2 in ((c['Din'] + 1) % 4, (c['Din'] + 3) % 4) for i, e in enumerate(edge(b, s2)) if i in (1, 4, 7)]
    return outcells(s)
out = []
cnt = collections.Counter()
for key, n in R['缺路'].items():
    s, t = key.split('->')
    sc = [c for c in srccells(s) if free(c)]
    tc = [c for c in incells(t) if free(c)]
    if not sc: why = f'起点 {s} 的取货端口外侧全被非运输单位或边界挡住'
    elif not tc: why = f'终点 {t} 的存货端口外侧全被非运输单位或边界挡住'
    elif not ({comp[c] for c in sc} & {comp[c] for c in tc}): why = '起终两侧可用格不在同一连通块'
    else: why = None
    cnt['补不出' if why else '未排除'] += n
    out.append(dict(缺路=key, 条数=n, 补不出原因=why))
# 全部取货边被挡的机器
blocked_out = [uid for uid in mach if not any(free(c) for c in outcells(uid))]
blocked_in = [uid for uid in mach if not any(free(c) for c in incells(uid))]
res = dict(统计=dict(cnt), 取货边全被挡的机器=blocked_out, 存货边全被挡的机器=blocked_in,
           空格连通块数=k, 逐条=out)
json.dump(res, open(sys.argv[3], 'w'), ensure_ascii=False, indent=1)
print(res['统计']); print('取货边全被挡', blocked_out); print('存货边全被挡', blocked_in); print('连通块', k)
reasons = collections.Counter((x['补不出原因'] or '未排除').split(' ')[0] for x in out)
print(reasons)
for x in out:
    if x['补不出原因'] and not x['补不出原因'].startswith('起点') and not x['补不出原因'].startswith('终点'):
        print(x)

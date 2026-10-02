#!/usr/bin/env python3
"""缺路能否在不动非运输单位的前提下补出：放宽判法，两套编码互核。

放宽：撤去全部运输单位，非运输单位（制造单位、协议核心、仓库取货口、供电桩）占格不可走，其余格都可走、可任意转弯、
容量无限、可随意交叉（桥接器只能让进路在运输格上交叉，不能穿过非运输单位），也不保留空矩形。
一条进路至少一格运输物品格，首格是起点某个取货端口正对的格，末格是终点某个存货端口正对的格。
两格都得不被非运输单位占，且在可走格的四连通图里连通；否则这条进路在这组固定摆放下怎样都布不出来。
编码一：集合+BFS；编码二：扁平数组+并查集。
另给与编号无关的判法：一台机器的整条存货边（或取货边）外侧，所在连通块里没有任何其他非运输单位的取货端口（或存货端口）外侧格，
则不论怎样给同型机器换身份、改配方设定，这台机器都接不进任何进路。
"""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, '..', '构造A', '未通过候选.json')))
MAIN = json.load(open(os.path.join(HERE, '结果-主.json')))
L = C['layout']; N = 70
D = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
blocked = set(); units = {}
for m in L['machines']:
    units[m['id']] = ('M', m)
for o in L['warehouse_outlets']: units[o['id']] = ('O', o)
units['CORE'] = ('C', L['core'])
for p in L['power_poles']: units[p['id']] = ('P', p)
for k, (c, u) in units.items():
    for x in range(u['x0'], u['x1'] + 1):
        for y in range(u['y0'], u['y1'] + 1): blocked.add((x, y))

def edge_front(u, s, offsets=None):
    x0, y0, x1, y1 = u['x0'], u['y0'], u['x1'], u['y1']
    if s == 0: cs = [(x1, y) for y in range(y0, y1 + 1)]
    elif s == 1: cs = [(x, y1) for x in range(x0, x1 + 1)]
    elif s == 2: cs = [(x0, y) for y in range(y0, y1 + 1)]
    else: cs = [(x, y0) for x in range(x0, x1 + 1)]
    if offsets is not None: cs = [cs[k] for k in offsets]
    dx, dy = D[s]
    return [(x + dx, y + dy) for x, y in cs if 0 <= x + dx < N and 0 <= y + dy < N and (x + dx, y + dy) not in blocked]

def out_fronts(uid):
    c, u = units[uid]
    if c == 'M': return edge_front(u, (u['Din'] + 2) % 4)
    if c == 'O': return edge_front(u, u['Dout'], [1])
    if c == 'C':
        r = []
        for s in ((u['Din'] + 1) % 4, (u['Din'] + 3) % 4): r += edge_front(u, s, [1, 4, 7])
        return r
    return []
def in_fronts(uid):
    c, u = units[uid]
    if c == 'M': return edge_front(u, u['Din'])
    if c == 'C':
        r = []
        for s in (u['Din'], (u['Din'] + 2) % 4): r += edge_front(u, s, range(1, 8))
        return r
    return []

# ---- 编码一：BFS ----
comp1 = {}
k = 0
for x in range(N):
    for y in range(N):
        if (x, y) in blocked or (x, y) in comp1: continue
        q = collections.deque([(x, y)]); comp1[(x, y)] = k
        while q:
            a, b = q.popleft()
            for dx, dy in D.values():
                n = (a + dx, b + dy)
                if 0 <= n[0] < N and 0 <= n[1] < N and n not in blocked and n not in comp1:
                    comp1[n] = k; q.append(n)
        k += 1
ncomp1 = k

# ---- 编码二：并查集 ----
par = list(range(N * N))
def find(i):
    while par[i] != i:
        par[i] = par[par[i]]; i = par[i]
    return i
free = [[(x, y) not in blocked for y in range(N)] for x in range(N)]
for x in range(N):
    for y in range(N):
        if not free[x][y]: continue
        if x + 1 < N and free[x + 1][y]: par[find(x * N + y)] = find((x + 1) * N + y)
        if y + 1 < N and free[x][y + 1]: par[find(x * N + y)] = find(x * N + y + 1)
roots = {find(x * N + y) for x in range(N) for y in range(N) if free[x][y]}
def comp2(c): return find(c[0] * N + c[1])

outlets = [o['id'] for o in L['warehouse_outlets']]
def sources_for(route_src):
    # route_src 是编码一的标签：矿口:物品 / 核心:源矿 / 单位 id
    if route_src.startswith('矿口:'):
        return None
    if route_src.startswith('核心:'): return ['CORE']
    return [route_src]

def feasible(src_units, dst, comp):
    s = {comp(c) for u in src_units for c in out_fronts(u)}
    d = {comp(c) for c in in_fronts(dst)}
    return bool(s & d)

res = {'可走格': sum(1 for x in range(N) for y in range(N) if free[x][y]), '连通块(编码一)': ncomp1, '连通块(编码二)': len(roots)}
# 全部 325 条 S2 进路：缺的 175 条 + 已布的 150 条
missing = [(s, d) for s, d, n in MAIN['routes_missing'] for _ in range(n)]
built = [(r['src'], r['dst']) for r in MAIN['routes']]
item_of = {o['id']: o['item'] for o in L['warehouse_outlets']}
def judge(lst, mode):
    bad1 = []; bad2 = []
    for s, d in lst:
        if s.startswith('矿口:'):
            it = s.split(':')[1]
            if mode == '同号':      # 按候选编号：WFEi→RFi，WOi→KOi
                num = d.lstrip('RFKO'); pre = 'WFE' if d.startswith('RF') else 'WO'
                su = [pre + num]
            elif mode == '同物品':
                su = [o for o in outlets if item_of[o] == it]
            else:
                su = outlets
        elif s in units and units[s][0] == 'O':
            su = [s] if mode == '同号' else ([o for o in outlets if item_of[o] == item_of[s]] if mode == '同物品' else outlets)
        else:
            su = sources_for(s)
        if not feasible(su, d, lambda c: comp1[c]): bad1.append([s, d])
        if not feasible(su, d, comp2): bad2.append([s, d])
    return bad1, bad2
for mode in ('同号', '同物品', '任一取货口'):
    b1, b2 = judge(missing, mode)
    c1, c2 = judge(built, mode)
    res['缺路中布不出(%s)' % mode] = {'编码一': len(b1), '编码二': len(b2), '一致': b1 == b2}
    res['已布路中判为布不出(%s，应为0)' % mode] = [len(c1), len(c2)]
    if mode == '同号': res['布不出清单(同号)'] = b1
    if mode == '任一取货口': res['布不出清单(任一取货口)'] = b1

# 与编号无关的判法
dead_in = []; dead_out = []
all_out_comps = collections.defaultdict(set); all_in_comps = collections.defaultdict(set)
for uid, (c, u) in units.items():
    for f in out_fronts(uid): all_out_comps[comp1[f]].add(uid)
    for f in in_fronts(uid): all_in_comps[comp1[f]].add(uid)
for uid, (c, u) in units.items():
    if c != 'M': continue
    ic = {comp1[f] for f in in_fronts(uid)}
    oc = {comp1[f] for f in out_fronts(uid)}
    if not any(all_out_comps[k] - {uid} for k in ic): dead_in.append(uid)
    if not any(all_in_comps[k] - {uid} for k in oc): dead_out.append(uid)
# 编码二（并查集）重算一遍
o2 = collections.defaultdict(set); i2 = collections.defaultdict(set)
for uid in units:
    for f in out_fronts(uid): o2[comp2(f)].add(uid)
    for f in in_fronts(uid): i2[comp2(f)].add(uid)
dead_in2 = [u for u, (c, _) in units.items() if c == 'M' and not any(o2[comp2(f)] - {u} for f in in_fronts(u))]
dead_out2 = [u for u, (c, _) in units.items() if c == 'M' and not any(i2[comp2(f)] - {u} for f in out_fronts(u))]
res['与编号无关判法两套一致'] = (dead_in == dead_in2 and dead_out == dead_out2)
res['存货边接不到任何取货端口的机器'] = dead_in
res['取货边接不到任何存货端口的机器'] = dead_out
res['存货边外侧全被非运输单位挡住的机器'] = [u for u, (c, _) in units.items() if c == 'M' and not in_fronts(u)]
res['取货边外侧全被挡住的机器'] = [u for u, (c, _) in units.items() if c == 'M' and not out_fronts(u)]
json.dump(res, open(os.path.join(HERE, '结果-可达.json'), 'w'), ensure_ascii=False, indent=1)
for k2, v in res.items():
    if '清单' in k2: print(k2, len(v))
    else: print(k2, v)

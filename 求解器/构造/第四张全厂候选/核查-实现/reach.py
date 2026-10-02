#!/usr/bin/env python3
"""放宽可达判定：撤去全部运输单位，只把制造单位、协议核心、仓库取货口、供电桩当障碍，
其余格都可走、可任意转弯和交叉（桥接器能交叉进路，但不能穿过非运输单位），也不保留空矩形。
一条进路的首格和末格必须是源取货端口、汇存货端口外侧的空格，且在同一个四连通块里。
两种实现：集合 + BFS，扁平数组 + 并查集，结果须一致。
另做逐单位端口容量：端口外侧可用格数少于接法要求的进路数，就一定接不全。
用法：python3 reach.py <布局.json> <结果-主.json> <输出.json>
"""
import json, sys
from collections import Counter, defaultdict, deque

doc = json.load(open(sys.argv[1]))
main = json.load(open(sys.argv[2]))
L = doc['layout']
N = 70
DX = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
blk = {}
U = {}
for m in L['machines']:
    U[m['id']] = dict(t='M', **m)
for o in L['warehouse_outlets']:
    U[o['id']] = dict(t='O', **o)
U['CORE'] = dict(t='C', **L['core'])
for p in L['power_poles']:
    U[p['id']] = dict(t='P', **p)
for uid, u in U.items():
    for x in range(u['x0'], u['x1'] + 1):
        for y in range(u['y0'], u['y1'] + 1):
            blk[(x, y)] = uid


def free(c):
    return 0 <= c[0] < N and 0 <= c[1] < N and c not in blk


def side_cells(u, s):
    if s == 0:
        return [(u['x1'], y) for y in range(u['y0'], u['y1'] + 1)]
    if s == 2:
        return [(u['x0'], y) for y in range(u['y0'], u['y1'] + 1)]
    if s == 1:
        return [(x, u['y1']) for x in range(u['x0'], u['x1'] + 1)]
    return [(x, u['y0']) for x in range(u['x0'], u['x1'] + 1)]


def out_cells(uid):
    """取货端口外侧格（含不可用的）"""
    u = U[uid]
    res = []
    if u['t'] == 'M':
        s = (u['Din'] + 2) % 4
        res = [((x + DX[s][0], y + DX[s][1]), (s, i)) for i, (x, y) in enumerate(side_cells(u, s))]
    elif u['t'] == 'O':
        if u['Dout'] == 0:
            res = [((1, u['y0'] + 1), (0, 1))]
        else:
            res = [((u['x0'] + 1, 1), (1, 1))]
    elif u['t'] == 'C':
        for it in u['output_items']:
            s, off = it['side'], it['offset']
            x, y = side_cells(u, s)[off]
            res.append(((x + DX[s][0], y + DX[s][1]), (s, off)))
    return res


def in_cells(uid):
    u = U[uid]
    res = []
    if u['t'] == 'M':
        s = u['Din']
        res = [((x + DX[s][0], y + DX[s][1]), (s, i)) for i, (x, y) in enumerate(side_cells(u, s))]
    elif u['t'] == 'C':
        for s in (u['Din'], (u['Din'] + 2) % 4):
            cs = side_cells(u, s)
            for off in range(1, 8):
                x, y = cs[off]
                res.append(((x + DX[s][0], y + DX[s][1]), (s, off)))
    return res


# ---- 实现一：集合 + BFS ----
comp1 = {}
cid = 0
for x in range(N):
    for y in range(N):
        if free((x, y)) and (x, y) not in comp1:
            q = deque([(x, y)])
            comp1[(x, y)] = cid
            while q:
                a = q.popleft()
                for d in range(4):
                    b = (a[0] + DX[d][0], a[1] + DX[d][1])
                    if free(b) and b not in comp1:
                        comp1[b] = cid
                        q.append(b)
            cid += 1
ncomp1 = cid

# ---- 实现二：扁平数组 + 并查集 ----
par = list(range(N * N))


def find(i):
    while par[i] != i:
        par[i] = par[par[i]]
        i = par[i]
    return i


fr = [free((i // N, i % N)) for i in range(N * N)]
for i in range(N * N):
    if not fr[i]:
        continue
    x, y = divmod(i, N)
    if x + 1 < N and fr[i + N]:
        par[find(i)] = find(i + N)
    if y + 1 < N and fr[i + 1]:
        par[find(i)] = find(i + 1)


def comp2(c):
    return find(c[0] * N + c[1])


ncomp2 = len({find(i) for i in range(N * N) if fr[i]})

# ---- 期望接法（按源统计），复用结果-主.json 的缺路清单 ----
missing = []
for m in main['接法']['缺路清单']:
    missing += [(m['源'], m['汇'])] * m['缺条数']

outlets = [uid for uid, u in U.items() if u['t'] == 'O']
used_src_ports = set()
for r in main['已通进路']:
    used_src_ports.add((r['源'], tuple(r['源端口'])))


def src_cands(s, mode):
    """mode: 'same' 同物品未用取货口/端口；'anyitem' 任一未用取货口；'all' 任一取货口或端口"""
    if s.startswith('仓库取货口:'):
        item = s.split(':')[1]
        res = []
        for o in outlets:
            for c, p in out_cells(o):
                if mode == 'same' and (U[o]['item'] != item or (o, p) in used_src_ports):
                    continue
                if mode == 'anyitem' and (o, p) in used_src_ports:
                    continue
                res.append(c)
        return res
    if s == 'CORE':
        return [c for c, p in out_cells('CORE') if mode == 'all' or ('CORE', p) not in used_src_ports]
    return [c for c, p in out_cells(s)]


def classify(s, t, mode, compf):
    sc = [c for c in src_cands(s, mode) if free(c)]
    tc = [c for c, p in in_cells(t) if free(c)]
    if not sc:
        return '源取货端口没有可用邻格'
    if not tc:
        return '汇存货端口没有可用邻格'
    if {compf(c) for c in sc} & {compf(c) for c in tc}:
        return '单路可达'
    return '两端位于不同空格连通块'


res = {}
for mode in ('same', 'anyitem', 'all'):
    a = [classify(s, t, mode, lambda c: comp1[c]) for s, t in missing]
    b = [classify(s, t, mode, comp2) for s, t in missing]
    res[mode] = dict(一致=a == b, 分类=dict(Counter(a)),
                     逐条=[dict(源=s, 汇=t, 判定=k) for (s, t), k in zip(missing, a)])

# ---- 逐单位端口容量 ----
need_out = Counter()
need_in = Counter()
exp_src = Counter()
for r in main['已通进路']:
    pass
# 期望接法：由 已通 + 缺 合成（与 check_main 的 325 条相同）
allr = [(r['源'] if not r['源'].startswith('W') else '仓库取货口:' + U[r['源']]['item'], r['汇'])
        for r in main['已通进路']] + missing
assert len(allr) == 325
for s, t in allr:
    need_out[s] += 1
    need_in[t] += 1
cap = []
for uid, u in U.items():
    if u['t'] not in ('M', 'C'):
        continue
    fo = [c for c, p in out_cells(uid) if free(c)]
    fi = [c for c, p in in_cells(uid) if free(c)]
    no, ni = need_out.get(uid, 0), need_in.get(uid, 0)
    if len(fo) < no or len(fi) < ni:
        cap.append(dict(单位=uid, 占格=[u['x0'], u['y0'], u['x1'], u['y1']], Din=u['Din'],
                        取货可用邻格=len(fo), 需出路=no, 存货可用邻格=len(fi), 需来路=ni,
                        取货边外侧=[[c[0], c[1], blk.get(c, '界外' if not (0 <= c[0] < N and 0 <= c[1] < N) else None)]
                                for c, p in out_cells(uid)],
                        存货边外侧=[[c[0], c[1], blk.get(c, '界外' if not (0 <= c[0] < N and 0 <= c[1] < N) else None)]
                                for c, p in in_cells(uid)] if u['t'] == 'M' else '略'))
# 取货口：端口外侧格被非运输单位占
outlet_blocked = []
for o in outlets:
    for c, p in out_cells(o):
        if not free(c):
            outlet_blocked.append(dict(取货口=o, 物品=U[o]['item'], 正对格=list(c), 被占=blk[c]))
# 取货口总容量
usable_outlets = {it: sum(1 for o in outlets if U[o]['item'] == it and all(free(c) for c, p in out_cells(o)))
                  for it in ('蓝铁矿', '源矿')}

out = dict(空格=sum(fr), 连通块_BFS=ncomp1, 连通块_并查集=ncomp2, 缺路判定=res,
           端口容量不足单位=cap, 取货口被挡=outlet_blocked, 可用取货口=usable_outlets)
json.dump(out, open(sys.argv[3], 'w'), ensure_ascii=False, indent=1)
print('空格', sum(fr), '连通块', ncomp1, ncomp2)
for mode, v in res.items():
    print(mode, v['一致'], v['分类'])
print('端口容量不足单位', len(cap))
for c in cap:
    print(' ', c['单位'], c['占格'], 'Din', c['Din'], '取货', c['取货可用邻格'], '/', c['需出路'], '存货', c['存货可用邻格'], '/', c['需来路'])
print('取货口被挡', outlet_blocked)
print('可用取货口', usable_outlets)

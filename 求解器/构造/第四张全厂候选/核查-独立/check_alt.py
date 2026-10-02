#!/usr/bin/env python3
"""核查「独立」第四张全厂候选：编码二（网格涂色、逐对相邻格判通道、从终点倒追）。

与 check_main.py 不共用任何函数。接法按终点单位逐台写来路。
用法：python3 check_alt.py 布局.json 输出.json
"""
import json, sys, collections

D = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
L = D['layout']
N = 70
owner = [[None] * N for _ in range(N)]   # owner[y][x]
info = {}
clash = []
def paint(uid, xs, ys, kind, **kw):
    info[uid] = dict(kind=kind, xs=xs, ys=ys, **kw)
    for y in ys:
        for x in xs:
            if not (0 <= x < N and 0 <= y < N):
                clash.append(('出界', uid, x, y)); continue
            if owner[y][x] is not None:
                clash.append(('重叠', uid, owner[y][x], x, y))
            owner[y][x] = uid

for m in L['machines']:
    paint(m['id'], range(m['x0'], m['x1'] + 1), range(m['y0'], m['y1'] + 1), 'M',
          Din=m['Din'], model=m['model'], recipe=m['recipe_ids'][0])
for o in L['warehouse_outlets']:
    paint(o['id'], range(o['x0'], o['x1'] + 1), range(o['y0'], o['y1'] + 1), 'O', item=o['item'], Dout=o['Dout'])
c = L['core']
paint('CORE', range(c['x0'], c['x1'] + 1), range(c['y0'], c['y1'] + 1), 'C', Din=c['Din'],
      oi={(e['side'], e['offset']): e['item'] for e in c['output_items']})
for p in L['power_poles']:
    paint(p['id'], range(p['x0'], p['x1'] + 1), range(p['y0'], p['y1'] + 1), 'P')
for t in L['transport']:
    if t['type'] == 'belt':
        paint(t['id'], [t['x']], [t['y']], 'B', i=t['in_side'], o=t['out_side'])
    else:
        paint(t['id'], [t['x']], [t['y']], 'G' if t['type'] == 'bridge' else 'X')

STEP = [(1, 0), (0, 1), (-1, 0), (0, -1)]

def port(uid, x, y, d):
    """单位 uid 在格 (x,y) 朝方向 d 的边上的端口：'in'/'out'/'io'/None，及该边的 offset。"""
    u = info[uid]
    xs, ys = u['xs'], u['ys']
    nx, ny = x + STEP[d][0], y + STEP[d][1]
    if nx in xs and ny in ys:
        return None, None   # 不在外边上
    off = (y - ys[0]) if d in (0, 2) else (x - xs[0])
    k = u['kind']
    if k == 'B':
        return ('in' if d == u['i'] else 'out' if d == u['o'] else None), 0
    if k == 'G':
        return 'io', 0
    if k == 'M':
        return ('in' if d == u['Din'] else 'out' if d == (u['Din'] + 2) % 4 else None), off
    if k == 'O':
        # 向内长边中间一格
        if u['Dout'] == 0 and d == 0 and off == 1 and xs[0] == 0: return 'out', off
        if u['Dout'] == 1 and d == 1 and off == 1 and ys[0] == 0: return 'out', off
        return None, off
    if k == 'C':
        if d in (u['Din'], (u['Din'] + 2) % 4):
            return ('in' if 1 <= off <= 7 else None), off
        return ('out' if off in (1, 4, 7) else None), off
    return None, None

TR = {'B', 'G'}
# 枚举相邻格对
chans = []   # (uidA, xA, yA, d) -> (uidB, xB, yB) 方向从 A 到 B
for y in range(N):
    for x in range(N):
        a = owner[y][x]
        if a is None: continue
        for d in range(4):
            nx, ny = x + STEP[d][0], y + STEP[d][1]
            if not (0 <= nx < N and 0 <= ny < N): continue
            b = owner[ny][nx]
            if b is None or b == a: continue
            if info[a]['kind'] not in TR and info[b]['kind'] not in TR: continue
            pa, oa = port(a, x, y, d)
            pb, ob = port(b, nx, ny, (d + 2) % 4)
            if pa in ('out', 'io') and pb in ('in', 'io'):
                chans.append(((a, x, y, d, oa), (b, nx, ny, (d + 2) % 4, ob)))

def nd(e):
    uid, x, y, d, off = e
    k = info[uid]['kind']
    if k == 'B': return (uid, '-')
    if k == 'G': return (uid, 'H' if d in (0, 2) else 'V')
    return (uid, d, off)

incoming = collections.defaultdict(list)
for a, b in chans:
    incoming[(b[0], b[3])].append((a, b))   # 按（单位, 进入边）索引

# 从非运输单位的存货端口倒追
routes = []
for a, b in chans:
    if info[b[0]]['kind'] in TR: continue
    if info[a[0]]['kind'] not in TR: continue
    seq = [(a, b)]
    cells = []
    cur = a
    status = 'ok'
    phys = set()
    while info[cur[0]]['kind'] in TR:
        uid = cur[0]
        if uid in phys:
            status = '重复物理单位'; break
        phys.add(uid)
        cells.append(nd(cur))
        k = info[uid]['kind']
        need_in = info[uid]['i'] if k == 'B' else (cur[3] + 2) % 4
        if k == 'B' and cur[3] != info[uid]['o']:
            status = '不是从传送带取货边出'; break
        cand = incoming.get((uid, need_in), [])
        if len(cand) != 1:
            status = f'倒追断于 {uid}'; break
        seq.append(cand[0]); cur = cand[0][0]
    routes.append(dict(src=(cur[0], cur[3], cur[4]), dst=(b[0], b[3], b[4]), cells=cells, status=status,
                       chans=seq))
ok = [r for r in routes if r['status'] == 'ok']

# 进路占用、前向集合
use = collections.Counter()
fw = set()
for r in ok:
    for n in r['cells']: use[n] += 1
    for a, b in r['chans']: fw.add((a, b))
shared = [n for n, v in use.items() if v > 1]
# 逆向与多余
rev, extra = [], []
for a, b in chans:
    if (a, b) in fw: continue
    if info[a[0]]['kind'] == 'G' and info[b[0]]['kind'] == 'G' and (b, a) in fw:
        rev.append((a, b)); continue
    extra.append((a, b))
# 运输物品格清单
tnodes = []
for uid, u in info.items():
    if u['kind'] == 'B': tnodes.append((uid, '-'))
    if u['kind'] == 'G': tnodes += [(uid, 'H'), (uid, 'V')]
unused = [n for n in tnodes if n not in use]
unused_belts = [n for n in unused if n[1] == '-']
# 未用桥轴是否有通道
touch = collections.Counter()
for a, b in chans:
    touch[nd(a)] += 1; touch[nd(b)] += 1
unused_axis_with_chan = [n for n in unused if n[1] in 'HV' and touch[n] > 0]
bridges_unused_both = [uid for uid, u in info.items() if u['kind'] == 'G' and (uid, 'H') in unused and (uid, 'V') in unused]
# 同一进路过两轴
both_axis_same = []
rid = {}
for i, r in enumerate(ok):
    for n in r['cells']: rid[n] = i
for uid, u in info.items():
    if u['kind'] == 'G' and rid.get((uid, 'H')) is not None and rid.get((uid, 'H')) == rid.get((uid, 'V')):
        both_axis_same.append(uid)

# 接法：按终点逐台写来路
want = collections.defaultdict(collections.Counter)   # 终点 -> 来源身份 -> 条数
for i in range(1, 35): want[f'T{i}']['蓝铁矿口'] += 1; want[f'KB{i}'][f'T{i}'] += 1
for i in range(1, 18):
    want[f'B{i}'][f'KB{2*i-1}'] += 1; want[f'B{i}'][f'KB{2*i}'] += 1
    want[f'R{i}'][f'B{i}'] += 1
for j in range(1, 19): want[f'U{j}']['核心口' if j <= 6 else '源矿口'] += 1
for i in range(1, 10): want[f'O{i}'][f'U{2*i-1}'] += 1; want[f'O{i}'][f'U{2*i}'] += 1
for i in range(1, 7): want[f'P{i}'][f'R{i}'] += 1
for h in range(1, 6): want[f'H{h}'][f'R{2*h+5}'] += 1; want[f'H{h}'][f'R{2*h+6}'] += 1
want['H6']['R17'] += 1
for e in range(1, 4):
    want[f'E{e}'][f'P{2*e-1}'] += 1; want[f'E{e}'][f'P{2*e}'] += 1
    for o in range(3 * e - 2, 3 * e + 1): want[f'E{e}'][f'O{o}'] += 1
want['F1'].update({'H1': 1, 'H2': 1, 'Q1': 1, 'Q2': 1})
want['F2'].update({'H3': 1, 'H4': 1, 'Q3': 1, 'Q4': 1})
want['F3'].update({'H5': 1, 'Q5': 1})
want['F4'].update({'H6': 1, 'Q6': 1})
want['CORE'].update({x: 1 for x in ['E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4']})
for p, k, n in (('S', 'S', 13), ('Q', 'KQ', 6)):
    for i in range(1, n + 1):
        want[f'{p}A{i}'][f'{p}C{i}'] += 1
        want[f'{p}B{i}'][f'{p}C{i}'] += 1
        want[f'{p}C{i}'][f'{p}A{i}'] += 1
        want[f'{k}{i}'][f'{p}B{i}'] += 1
sandsrc = {'B1': 1, 'B2': 1, 'O1': 1, 'O2': 2, 'O3': 2, 'B3': 3, 'B4': 3, 'O4': 3, 'O5': 4, 'O6': 4, 'B5': 5, 'B6': 5,
           'O7': 5, 'O8': 6, 'O9': 6, 'B7': 7, 'B8': 7, 'B9': 7, 'B10': 8, 'Q1': 8, 'Q2': 8, 'B11': 9, 'B12': 9,
           'B13': 9, 'B14': 10, 'Q3': 10, 'Q4': 10, 'B15': 11, 'B16': 11, 'Q5': 11, 'B17': 12, 'Q6': 13}
for t, s in sandsrc.items(): want[t][f'S{s}'] += 1
for q in range(1, 6): want[f'Q{q}'][f'KQ{q}'] += 2
want['Q6']['KQ6'] += 1
total_want = sum(sum(v.values()) for v in want.values())

def ident(src):
    uid = src[0]
    k = info[uid]['kind']
    if k == 'O': return '蓝铁矿口' if info[uid]['item'] == '蓝铁矿' else '源矿口'
    if k == 'C': return '核心口'
    return uid
have = collections.defaultdict(collections.Counter)
for r in ok:
    have[r['dst'][0]][ident(r['src'])] += 1
missing = []
excess = []
for t in sorted(set(want) | set(have)):
    for s in set(want[t]) | set(have[t]):
        dlt = want[t][s] - have[t][s]
        if dlt > 0: missing.append((s, t, dlt))
        if dlt < 0: excess.append((s, t, -dlt))

def rl(s, t):
    return sorted(len(r['cells']) for r in ok if r['src'][0] == s and r['dst'][0] == t)

# 供电（连续坐标区间相交）
unpowered = []
for m in L['machines']:
    hit = False
    for p in L['power_poles']:
        cx, cy = p['x0'] + 1.0, p['y0'] + 1.0
        if (m['x0'] < cx + 6 and m['x1'] + 1 > cx - 6 and m['y0'] < cy + 6 and m['y1'] + 1 > cy - 6):
            hit = True; break
    if not hit: unpowered.append(m['id'])

# 尺寸
size_bad = []
for m in L['machines']:
    w, h = m['x1'] - m['x0'] + 1, m['y1'] - m['y0'] + 1
    k = m['kind']
    ok_ = (k == '小' and (w, h) == (3, 3)) or (k == '中' and (w, h) == (5, 5)) or \
          (k == '大' and ((w, h) == (6, 4) and m['Din'] % 2 == 1 or (w, h) == (4, 6) and m['Din'] % 2 == 0))
    if not ok_: size_bad.append(m['id'])

# 空矩形：二维前缀和穷举
occ = [[1 if owner[y][x] is not None else 0 for x in range(N)] for y in range(N)]
P = [[0] * (N + 1) for _ in range(N + 1)]
for y in range(N):
    for x in range(N):
        P[y + 1][x + 1] = occ[y][x] + P[y][x + 1] + P[y + 1][x] - P[y][x]
def s(x0, y0, x1, y1):
    return P[y1 + 1][x1 + 1] - P[y0][x1 + 1] - P[y1 + 1][x0] + P[y0][x0]
best = (0, 0); where = []; cnt = 0
for x0 in range(N):
    for x1 in range(x0 + 5, N):
        w = x1 - x0 + 1
        for y0 in range(N):
            # 最大的 y1 使得空
            if s(x0, y0, x1, min(y0 + 5, N - 1)) or y0 + 5 >= N:
                continue
            lo, hi = y0 + 5, N - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if s(x0, y0, x1, mid) == 0: lo = mid
                else: hi = mid - 1
            for y1 in range(y0 + 5, lo + 1):
                cnt += 1
                h = y1 - y0 + 1
                key = (w * h, min(w, h))
                if key > best: best = key; where = [(x0, y0, x1, y1)]
                elif key == best: where.append((x0, y0, x1, y1))

# 仓库取货口边带
left = sorted(o['y0'] for o in L['warehouse_outlets'] if o['x0'] == 0 and o['x1'] == 0)
down = sorted(o['x0'] for o in L['warehouse_outlets'] if o['y0'] == 0 and o['y1'] == 0)
def gaps(starts):
    covered = set()
    for a in starts: covered |= {a, a + 1, a + 2}
    return sorted(set(range(70)) - covered)
# 每个取货口端口外侧格是什么
outlet_face = collections.Counter()
for o in L['warehouse_outlets']:
    if o['Dout'] == 0: fx, fy = 1, o['y0'] + 1
    else: fx, fy = o['x0'] + 1, 1
    u = owner[fy][fx]
    outlet_face[info[u]['kind'] if u else '空'] += 1

res = dict(
    禁用运输类型=sorted(uid for uid, u in info.items() if u['kind'] == 'X'),
    协议储存箱=len(L.get('storage_boxes', [])),
    占格冲突=clash,
    重建通道数=len(chans),
    倒追得到的完整进路=len(ok),
    倒追失败=[(r['dst'], r['status']) for r in routes if r['status'] != 'ok'],
    共用物品格=shared,
    相邻桥逆向通道=len(rev),
    多余通道=[(a[:4], b[:4]) for a, b in extra],
    不在进路上的传送带=unused_belts,
    未用桥轴有通道=unused_axis_with_chan,
    两轴都未用的桥=bridges_unused_both,
    同一进路过两轴的桥=both_axis_same,
    桥轴使用数=sum(1 for n in tnodes if n[1] in 'HV' and n in use),
    运输物品格总数_在用=sum(1 for n in tnodes if n in use),
    要求进路=total_want,
    接法外或超额=excess,
    缺路条数=sum(x[2] for x in missing),
    缺路=missing,
    H6_F4=rl('H6', 'F4'), Q6_F4=rl('Q6', 'F4'),
    无供电=unpowered,
    尺寸错=size_bad,
    最大空矩形=dict(面积=best[0], 短边=best[1], 位置=where, 枚举的短边至少6空矩形数=cnt),
    左边界取货口起点=left, 左边界空格=gaps(left), 下边界取货口起点=down, 下边界空格=gaps(down),
    取货口端口外侧格=dict(outlet_face),
    进路明细=sorted([(r['src'], r['dst'], len(r['cells'])) for r in ok]),
)
json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1, default=str)
for k, v in res.items():
    if k in ('进路明细', '缺路'): continue
    print(k, ':', v)
print('缺路条目数', len(missing))

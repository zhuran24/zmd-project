#!/usr/bin/env python3
"""核查A 编码二：与 check_main.py 不共用任何函数的第二套重建。

- 占格：numpy 整数网格涂色，重叠用计数>1 判；
- 端口：对每个单位的每一格，问「这一格往方向 s 的邻格是否在本单位外」得到外边，再按单位定义判存/取；
  制造单位的存货边由 Din 得到，机身尺寸由「长边与存取边平行」反推；
- 通道：枚举全部相邻格对（水平、竖直），两侧各查一次端口表；
- 进路：从非运输单位的存货端口倒着追到取货端口；
- 空矩形：逐行直方图+单调栈列举全部极大矩形；另用二维前缀和对最优值做穷举反证（没有更大的）；
- 供电：涂覆盖网格；
- S2 期望：按终点单位逐台写来路，与编码一的「按出发单位」写法不同。
结果写 结果-副.json。
"""
import json, os, hashlib, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.environ.get('CAND_PATH') or os.path.join(HERE, '..', '构造A', '未通过候选.json')
OUTFILE = os.environ.get('OUT_PATH') or os.path.join(HERE, '结果-副.json')
raw = open(CAND, 'rb').read()
C = json.loads(raw)
Lay = C['layout']
N = 70
VEC = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # E N W S
issues = []

grid = np.full((N, N), -1, dtype=np.int64)   # unit index
count = np.zeros((N, N), dtype=np.int64)
U = []  # list of dict
def add_unit(uid, cls, xs, ys, **kw):
    idx = len(U)
    U.append(dict(id=uid, cls=cls, x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys), **kw))
    for x in range(min(xs), max(xs) + 1):
        for y in range(min(ys), max(ys) + 1):
            if 0 <= x < N and 0 <= y < N:
                count[x, y] += 1; grid[x, y] = idx
            else:
                issues.append(('出界', uid))
    return idx

MODEL_DIM = {'粉碎机': 3, '精炼炉': 3, '配件机': 3, '塑形机': 3, '采种机': 5, '种植机': 5}
LARGE = {'研磨机', '封装机', '灌装机'}
OUTPUT = {'粉碎-源矿': '源石粉末', '粉碎-蓝铁块': '蓝铁粉末', '粉碎-荞花': '荞花粉末', '粉碎-砂叶': '砂叶粉末',
          '精炼-蓝铁矿': '蓝铁块', '精炼-致密蓝铁': '钢块', '研磨-致密蓝铁': '致密蓝铁粉末', '研磨-致密源石': '致密源石粉末',
          '研磨-细磨荞花': '细磨荞花粉末', '塑形-钢质瓶': '钢质瓶', '配件-钢制零件': '钢制零件', '种植-荞花': '荞花',
          '种植-砂叶': '砂叶', '采种-荞花': '荞花种子', '采种-砂叶': '砂叶种子', '封装-电池': '高容谷地电池', '灌装-胶囊': '精选荞愈胶囊'}
INPUTS = {'粉碎-源矿': {'源矿'}, '粉碎-蓝铁块': {'蓝铁块'}, '粉碎-荞花': {'荞花'}, '粉碎-砂叶': {'砂叶'},
          '精炼-蓝铁矿': {'蓝铁矿'}, '精炼-致密蓝铁': {'致密蓝铁粉末'}, '研磨-致密蓝铁': {'蓝铁粉末', '砂叶粉末'},
          '研磨-致密源石': {'源石粉末', '砂叶粉末'}, '研磨-细磨荞花': {'荞花粉末', '砂叶粉末'}, '塑形-钢质瓶': {'钢块'},
          '配件-钢制零件': {'钢块'}, '种植-荞花': {'荞花种子'}, '种植-砂叶': {'砂叶种子'}, '采种-荞花': {'荞花'},
          '采种-砂叶': {'砂叶'}, '封装-电池': {'钢制零件', '致密源石粉末'}, '灌装-胶囊': {'钢质瓶', '细磨荞花粉末'}}

for m in Lay['machines']:
    w = m['x1'] - m['x0'] + 1; h = m['y1'] - m['y0'] + 1
    if m['model'] in LARGE:
        # 存取边是长边：Din 为上下(1,3)时长边水平 → 宽 6
        horiz_long = m['Din'] % 2 == 1
        want = (6, 4) if horiz_long else (4, 6)
    else:
        d = MODEL_DIM[m['model']]; want = (d, d)
    if (w, h) != want: issues.append(('尺寸', m['id']))
    add_unit(m['id'], 'M', [m['x0'], m['x1']], [m['y0'], m['y1']], din=m['Din'], recipe=m['recipe_ids'][0], model=m['model'])
co = Lay['core']
core_idx = add_unit('CORE', 'C', [co['x0'], co['x1']], [co['y0'], co['y1']], din=co['Din'],
                    outs={(o['side'], o['offset']): o['item'] for o in co['output_items']})
if (co['x1'] - co['x0'], co['y1'] - co['y0']) != (8, 8): issues.append(('核心尺寸', 'CORE'))
for o in Lay['warehouse_outlets']:
    xs = [o['x0'], o['x1']]; ys = [o['y0'], o['y1']]
    # 贴左：x 全为 0 且竖长 3；贴下：y 全为 0 且横长 3
    left = (o['x0'] == 0 == o['x1']) and (o['y1'] - o['y0'] == 2)
    bottom = (o['y0'] == 0 == o['y1']) and (o['x1'] - o['x0'] == 2)
    if not (left or bottom): issues.append(('取货口位置', o['id']))
    if left and o['Dout'] != 0 or bottom and o['Dout'] != 1: issues.append(('取货口朝向', o['id']))
    add_unit(o['id'], 'O', xs, ys, item=o['item'], edge='L' if left else 'B')
for p in Lay['power_poles']:
    if (p['x1'] - p['x0'], p['y1'] - p['y0']) != (1, 1): issues.append(('桩尺寸', p['id']))
    add_unit(p['id'], 'P', [p['x0'], p['x1']], [p['y0'], p['y1']])
for t in Lay['transport']:
    add_unit(t['id'], 'T', [t['x']], [t['y']], ttype=t['type'], rec=t)
overlap = int((count > 1).sum())
if overlap: issues.append(('重叠格数', overlap))

def is_outer(i, x, y, s):
    u = U[i]; nx, ny = x + VEC[s][0], y + VEC[s][1]
    return not (u['x0'] <= nx <= u['x1'] and u['y0'] <= ny <= u['y1'])

def offset_along(u, x, y, s):
    return (y - u['y0']) if s in (0, 2) else (x - u['x0'])

# 端口表：P_in[x,y,s]、P_out[x,y,s]
P_in = np.zeros((N, N, 4), dtype=bool); P_out = np.zeros((N, N, 4), dtype=bool)
for i, u in enumerate(U):
    for x in range(u['x0'], u['x1'] + 1):
        for y in range(u['y0'], u['y1'] + 1):
            for s in range(4):
                if not is_outer(i, x, y, s): continue
                k = offset_along(u, x, y, s)
                if u['cls'] == 'M':
                    if s == u['din']: P_in[x, y, s] = True
                    elif s == (u['din'] ^ 2): P_out[x, y, s] = True   # 对边：E<->W(0^2=2)，N<->S(1^2=3)
                elif u['cls'] == 'C':
                    if s % 2 == u['din'] % 2:
                        if 1 <= k <= 7: P_in[x, y, s] = True
                    else:
                        if k in (1, 4, 7): P_out[x, y, s] = True
                elif u['cls'] == 'O':
                    # 向内的长边中间一格
                    inward = 0 if u['edge'] == 'L' else 1
                    if s == inward and k == 1: P_out[x, y, s] = True
                elif u['cls'] == 'T':
                    r = u['rec']
                    if r['type'] == 'belt':
                        if s == r['in_side']: P_in[x, y, s] = True
                        if s == r['out_side']: P_out[x, y, s] = True
                    elif r['type'] == 'bridge':
                        P_in[x, y, s] = True; P_out[x, y, s] = True

# 通道：相邻格对
CH = set()
for x in range(N):
    for y in range(N):
        a = grid[x, y]
        if a < 0: continue
        for s, (dx, dy) in ((0, (1, 0)), (1, (0, 1))):
            nx, ny = x + dx, y + dy
            if nx >= N or ny >= N: continue
            b = grid[nx, ny]
            if b < 0 or b == a: continue
            if U[a]['cls'] != 'T' and U[b]['cls'] != 'T': continue
            t = s + 2
            if P_out[x, y, s] and P_in[nx, ny, t]: CH.add(((x, y), s, (nx, ny)))
            if P_out[nx, ny, t] and P_in[x, y, s]: CH.add(((nx, ny), t, (x, y)))
res = {'channels': len(CH)}

# 与声明比对（换成格+边表示）
def cell_of(pref):
    hit = [i for i, v in enumerate(U) if v['id'] == pref['unit']]
    if not hit: return ('未知单位', pref['unit'])
    u = U[hit[0]]
    s, k = pref['side'], pref['offset']
    if s == 0: return (u['x1'], u['y0'] + k)
    if s == 1: return (u['x0'] + k, u['y1'])
    if s == 2: return (u['x0'], u['y0'] + k)
    return (u['x0'] + k, u['y0'])
DECL = set()
for pc in C['design']['physical_channels']:
    a = cell_of(pc['from']); b = cell_of(pc['to'])
    DECL.add((a, pc['from']['side'], b))
res['decl_equal'] = (DECL == CH)
res['undeclared'] = len(CH - DECL); res['declared_fake'] = len(DECL - CH)

# 运输节点 = (格, 轴)；轴：带为 'b'，桥按进出边分 'h'/'v'
def tnode(cell, s):
    i = grid[cell]
    if U[i]['cls'] != 'T': return None
    if U[i]['rec']['type'] == 'bridge': return (cell, 'h' if s % 2 == 0 else 'v')
    return (cell, 'b')
into = collections.defaultdict(list); outof = collections.defaultdict(list)
for (a, s, b) in CH:
    na = tnode(a, s); nb = tnode(b, s ^ 2)
    if na: outof[na].append((a, s, b))
    if nb: into[nb].append((a, s, b))

# 倒追：从每条终点为非运输单位的通道出发
routes = []
used = collections.Counter()
for ch in CH:
    a, s, b = ch
    if U[grid[b]]['cls'] == 'T': continue
    dst = U[grid[b]]['id']; length = 0; cur = ch; ok = True; cells = []
    while True:
        a, s, b = cur
        nd = tnode(a, s)
        if nd is None: src = U[grid[a]]['id']; src_cell = a; src_side = s; break
        length += 1; used[nd] += 1; cells.append(a)
        cand_in = into[nd]
        if nd[1] in ('h', 'v'): cand_in = [c for c in cand_in if c[1] == s]  # 桥直穿：从对边进来的那条，其方向与出方向同
        if len(cand_in) != 1: ok = False; src = None; break
        cur = cand_in[0]
    if not ok: issues.append(('倒追断开', dst, b)); continue
    su = U[grid[src_cell]]
    if su['cls'] == 'O': item = su['item']; slabel = 'outlet:' + item
    elif su['cls'] == 'C':
        # 由格和边求 offset
        k = (src_cell[1] - su['y0']) if src_side in (0, 2) else (src_cell[0] - su['x0'])
        item = su['outs'][(src_side, k)]; slabel = 'core:' + item
    else: item = OUTPUT[su['recipe']]; slabel = src
    du = U[grid[b]]
    if du['cls'] == 'M' and item not in INPUTS[du['recipe']]: issues.append(('误料', src, dst, item))
    if du['cls'] == 'C' and item not in ('高容谷地电池', '精选荞愈胶囊'): issues.append(('核心收非成品', src))
    routes.append(dict(src=src, slabel=slabel, dst=dst, length=length, item=item, cells=cells[::-1]))
res['routes'] = len(routes)
res['shared_nodes'] = [n for n, k in used.items() if k > 1]
# 所有运输节点都在进路上？
all_nodes = set()
for i, u in enumerate(U):
    if u['cls'] == 'T':
        c = (u['x0'], u['y0'])
        if u['rec']['type'] == 'bridge':
            for ax in 'hv':
                if into[(c, ax)] or outof[(c, ax)]: all_nodes.add((c, ax))
        else: all_nodes.add((c, 'b'))
res['nodes_total'] = len(all_nodes)
res['nodes_not_on_route'] = sorted([list(n[0]) + [n[1]] for n in all_nodes - set(used)])
res['transport_cells_on_routes'] = len(used)
bridges = [u for u in U if u['cls'] == 'T' and u['rec']['type'] == 'bridge']
res['bridges'] = len(bridges)
res['bridge_both_axes_used'] = sum(1 for u in bridges if ((u['x0'], u['y0']), 'h') in used and ((u['x0'], u['y0']), 'v') in used)
# 每座桥两轴不同进路
node_route = {}
for k, r in enumerate(routes):
    for c in r['cells']:
        pass
# 用 cells+轴重算：给每条路记录节点
def route_nodes(r):
    return r['cells']
same_route_bridge = []
for u in bridges:
    c = (u['x0'], u['y0'])
    owners = [k for k, r in enumerate(routes) if c in r['cells']]
    if len(owners) != 2 or owners[0] == owners[1]: same_route_bridge.append(u['id'])
res['bridges_not_two_distinct_routes'] = same_route_bridge
# 相邻桥
bset = {(u['x0'], u['y0']) for u in bridges}
res['adjacent_bridges'] = sorted([[list(c), list((c[0] + dx, c[1] + dy))] for c in bset for dx, dy in ((1, 0), (0, 1)) if (c[0] + dx, c[1] + dy) in bset])

# ---------- S2 期望：按终点逐台写来路 ----------
def into_spec():
    D = collections.defaultdict(list)
    for i in range(1, 35): D['RF%d' % i] = ['outlet:蓝铁矿']; D['KF%d' % i] = ['RF%d' % i]
    for i in range(1, 19): D['KO%d' % i] = ['core:源矿' if i <= 6 else 'outlet:源矿']
    sand_to = {}
    groups = {'S1': 'B1 B2 O1', 'S2': 'O2 O3', 'S3': 'B3 B4 O4', 'S4': 'O5 O6', 'S5': 'B5 B6 O7', 'S6': 'O8 O9', 'S7': 'B7 B8 B9',
              'S8': 'B10 Q1 Q2', 'S9': 'B11 B12 B13', 'S10': 'B14 Q3 Q4', 'S11': 'B15 B16 Q5', 'S12': 'B17', 'S13': 'Q6'}
    for s, ds in groups.items():
        for d in ds.split(): sand_to[d] = s
    for i in range(1, 18): D['B%d' % i] = ['KF%d' % (2 * i - 1), 'KF%d' % (2 * i), sand_to['B%d' % i]]
    for i in range(1, 10): D['O%d' % i] = ['KO%d' % (2 * i - 1), 'KO%d' % (2 * i), sand_to['O%d' % i]]
    for i in range(1, 7): D['Q%d' % i] = (['QK%d' % i] * (2 if i <= 5 else 1)) + [sand_to['Q%d' % i]]
    for i in range(1, 18): D['R%d' % i] = ['B%d' % i]
    for i in range(1, 7): D['P%d' % i] = ['R%d' % i]
    hmap = {1: [7, 8], 2: [9, 10], 3: [11, 12], 4: [13, 14], 5: [15, 16], 6: [17]}
    for h, rs in hmap.items(): D['H%d' % h] = ['R%d' % r for r in rs]
    for e in (1, 2, 3): D['E%d' % e] = ['P%d' % (2 * e - 1), 'P%d' % (2 * e)] + ['O%d' % j for j in range(3 * e - 2, 3 * e + 1)]
    D['F1'] = ['H1', 'H2', 'Q1', 'Q2']; D['F2'] = ['H3', 'H4', 'Q3', 'Q4']; D['F3'] = ['H5', 'Q5']; D['F4'] = ['H6', 'Q6']
    D['CORE'] = ['E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4']
    for pre, n, k in (('S', 13, 'S'), ('Q', 6, 'QK')):
        for j in range(1, n + 1):
            D['%sA%d' % (pre, j)] = ['%sC%d' % (pre, j)]
            D['%sB%d' % (pre, j)] = ['%sC%d' % (pre, j)]
            D['%sC%d' % (pre, j)] = ['%sA%d' % (pre, j)]
            D['%s%d' % (k, j)] = ['%sB%d' % (pre, j)]
    return D
SPEC = into_spec()
res['spec_total'] = sum(len(v) for v in SPEC.values())
have = collections.defaultdict(list)
for r in routes: have[r['dst']].append(r['slabel'])
miss = []; extra = []
for dst in sorted(set(SPEC) | set(have)):
    e = collections.Counter(SPEC.get(dst, [])); g = collections.Counter(have.get(dst, []))
    for k, v in (e - g).items(): miss += [[k, dst]] * v
    for k, v in (g - e).items(): extra += [[k, dst]] * v
res['missing'] = len(miss); res['extra'] = extra
res['missing_list'] = sorted(miss)
# 每台机器进出路数 vs S2
# H6/Q6 等长
res['H6_F4'] = [r['length'] for r in routes if r['src'] == 'H6' and r['dst'] == 'F4']
res['Q6_F4'] = [r['length'] for r in routes if r['src'] == 'Q6' and r['dst'] == 'F4']

# ---------- 供电（涂覆盖网格） ----------
cov = np.zeros((N, N), dtype=bool)
for u in U:
    if u['cls'] == 'P':
        cx, cy = u['x0'] + 1, u['y0'] + 1   # 中心格点
        cov[max(0, cx - 6):min(N, cx + 6), max(0, cy - 6):min(N, cy + 6)] = True
unp = []
for i, u in enumerate(U):
    if u['cls'] == 'M' and not cov[u['x0']:u['x1'] + 1, u['y0']:u['y1'] + 1].any(): unp.append(u['id'])
res['unpowered'] = unp

# ---------- 空矩形：直方图+单调栈（全部极大矩形），再前缀和穷举 ----------
free = (grid < 0)
res['occupied'] = int((~free).sum())
best = (0, 0, None)
hgt = np.zeros(N, dtype=int)
for y in range(N):              # 以行 y 为上沿，向下数连续空格
    for x in range(N): hgt[x] = hgt[x] + 1 if free[x, y] else 0
    st = []
    for x in range(N + 1):
        cur = hgt[x] if x < N else 0
        start = x
        while st and st[-1][1] >= cur:
            sx, sh = st.pop()
            w = x - sx
            if sh >= 6 and w >= 6:
                key = (w * sh, min(w, sh))
                if key > best[:2]: best = (key[0], key[1], (sx, y - sh + 1, x - 1, y))
            start = sx
        st.append((start, cur))
res['rect_hist'] = {'area': int(best[0]), 'short': int(best[1]), 'bounds': [int(v) for v in best[2]] if best[2] else None}
# 前缀和穷举：是否存在面积更大，或面积相等短边更长的空矩形
S = np.zeros((N + 1, N + 1), dtype=np.int64)
S[1:, 1:] = np.cumsum(np.cumsum((~free).astype(np.int64), 0), 1)
better = 0; equal = []
for w in range(6, N + 1):
    for h in range(6, N + 1):
        a = w * h
        if a < best[0]: continue
        # 所有位置
        blk = S[w:, h:] - S[:-w or None, h:][:N + 1 - w, :] - S[w:, :N + 1 - h] + S[:N + 1 - w, :N + 1 - h]
        blk = S[w:N + 1, h:N + 1] - S[0:N + 1 - w, h:N + 1] - S[w:N + 1, 0:N + 1 - h] + S[0:N + 1 - w, 0:N + 1 - h]
        z = np.argwhere(blk == 0)
        if len(z) == 0: continue
        if (a, min(w, h)) > (best[0], best[1]): better += len(z)
        elif (a, min(w, h)) == (best[0], best[1]):
            equal += [[int(x0), int(y0), int(x0) + w - 1, int(y0) + h - 1] for x0, y0 in z]
res['rect_prefix_better_count'] = better
res['rect_prefix_ties'] = equal

res['issues'] = [list(map(str, i)) for i in issues]
res['candidate_sha256'] = hashlib.sha256(raw).hexdigest()
res['routes_list'] = sorted([[r['src'], r['dst'], r['length'], r['item']] for r in routes])
json.dump(res, open(OUTFILE, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('missing_list', 'routes_list')}, ensure_ascii=False))

#!/usr/bin/env python3
"""核查A 编码一：从布局文件重建占格、端口、通道、进路，逐条核规则与 S2 第 2 节接法。

不导入构造席或核查B的任何程序。只读布局文件，结果写到本目录的 结果-主.json。
做法：按单位定义逐单位列出端口（边、偏移），从每个取货端口往外看一格找对面的存货端口；
进路从非运输单位的取货端口出发往前追；空矩形对每个列区间做行扫描。
"""
import json, sys, os, hashlib, collections, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.environ.get('CAND_PATH') or os.path.join(HERE, '..', '构造A', '未通过候选.json')
OUTFILE = os.environ.get('OUT_PATH') or os.path.join(HERE, '结果-主.json')
SNAP = os.path.join(HERE, '..', '..', '..', '候选约束轮次', '第107-109轮')

N = 70
DXY = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
def opp(s): return (s + 2) % 4

problems = []  # (类别, 说明)
def bad(cat, msg): problems.append((cat, msg))

def no_dup(pairs):
    d = {}
    for k, v in pairs:
        if k in d: raise ValueError('重复键 %s' % k)
        d[k] = v
    return d

raw = open(CAND, 'rb').read()
cand = json.loads(raw.decode('utf-8'), object_pairs_hook=no_dup)
out = {'candidate_sha256': hashlib.sha256(raw).hexdigest()}

# ---------- 指纹 ----------
fp = {}
for key, name in [('rules', '《明日方舟：终末地》游戏规则.txt'), ('task', '求解任务.txt'), ('constraints', '求解约束.txt')]:
    fp[key] = hashlib.sha256(open(os.path.join(SNAP, '前提快照', name), 'rb').read()).hexdigest()
out['fingerprints_match'] = (fp == cand['source_fingerprints'])
if not out['fingerprints_match']: bad('指纹', '候选记录的规则/任务/约束指纹与第107-109轮快照不同')

L = cand['layout']
if L['W'] != 70 or L['H'] != 70: bad('基地', 'W/H 不是 70')
if L['vin'] or L['vout']: bad('格式', 'vin/vout 非空')

# ---------- 单位与占格 ----------
SIZE_KIND = {'粉碎机': '小', '精炼炉': '小', '配件机': '小', '塑形机': '小',
             '采种机': '中', '种植机': '中', '研磨机': '大', '封装机': '大', '灌装机': '大'}
RECIPE = {  # recipe id -> (model, inputs, outputs)
    '粉碎-源矿': ('粉碎机', {'源矿': 1}, {'源石粉末': 1}),
    '粉碎-蓝铁块': ('粉碎机', {'蓝铁块': 1}, {'蓝铁粉末': 1}),
    '粉碎-荞花': ('粉碎机', {'荞花': 1}, {'荞花粉末': 2}),
    '粉碎-砂叶': ('粉碎机', {'砂叶': 1}, {'砂叶粉末': 3}),
    '精炼-蓝铁矿': ('精炼炉', {'蓝铁矿': 1}, {'蓝铁块': 1}),
    '精炼-致密蓝铁': ('精炼炉', {'致密蓝铁粉末': 1}, {'钢块': 1}),
    '精炼-蓝铁粉末': ('精炼炉', {'蓝铁粉末': 1}, {'蓝铁块': 1}),
    '研磨-致密蓝铁': ('研磨机', {'蓝铁粉末': 2, '砂叶粉末': 1}, {'致密蓝铁粉末': 1}),
    '研磨-致密源石': ('研磨机', {'源石粉末': 2, '砂叶粉末': 1}, {'致密源石粉末': 1}),
    '研磨-细磨荞花': ('研磨机', {'荞花粉末': 2, '砂叶粉末': 1}, {'细磨荞花粉末': 1}),
    '塑形-钢质瓶': ('塑形机', {'钢块': 2}, {'钢质瓶': 1}),
    '配件-钢制零件': ('配件机', {'钢块': 1}, {'钢制零件': 1}),
    '种植-荞花': ('种植机', {'荞花种子': 1}, {'荞花': 1}),
    '种植-砂叶': ('种植机', {'砂叶种子': 1}, {'砂叶': 1}),
    '采种-荞花': ('采种机', {'荞花': 1}, {'荞花种子': 2}),
    '采种-砂叶': ('采种机', {'砂叶': 1}, {'砂叶种子': 2}),
    '封装-电池': ('封装机', {'钢制零件': 10, '致密源石粉末': 15}, {'高容谷地电池': 1}),
    '灌装-胶囊': ('灌装机', {'钢质瓶': 10, '细磨荞花粉末': 10}, {'精选荞愈胶囊': 1}),
}

units = {}   # id -> dict
owner = {}   # (x,y) -> id
placed_ids = set()
def place(uid, cells, cls):
    if uid in placed_ids: bad('身份', '单位 id 重复：%s' % uid)
    placed_ids.add(uid)
    for c in cells:
        x, y = c
        if not (0 <= x < N and 0 <= y < N): bad('出界', '%s 占格 %s 出界' % (uid, c)); continue
        if c in owner: bad('重叠', '%s 与 %s 在格 %s 重叠' % (uid, owner[c], c))
        owner[c] = uid

def rect_cells(x0, y0, x1, y1):
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

def edge_cells(b, s):
    x0, y0, x1, y1 = b
    if s == 0: return [((x1, y), y - y0) for y in range(y0, y1 + 1)]
    if s == 1: return [((x, y1), x - x0) for x in range(x0, x1 + 1)]
    if s == 2: return [((x0, y), y - y0) for y in range(y0, y1 + 1)]
    return [((x, y0), x - x0) for x in range(x0, x1 + 1)]

# ports[(uid)] = list of (cell, side, offset, io) io in {'in','out'}
ports = collections.defaultdict(list)

model_count = collections.Counter()
for m in L['machines']:
    b = (m['x0'], m['y0'], m['x1'], m['y1'])
    w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
    k = SIZE_KIND.get(m['model'])
    if k is None or m['kind'] != k: bad('机型', '%s 机型/尺寸类别不符' % m['id'])
    if k == '小': ok = (w, h) == (3, 3)
    elif k == '中': ok = (w, h) == (5, 5)
    else: ok = (w, h) == ((6, 4) if m['Din'] in (1, 3) else (4, 6))
    if not ok: bad('尺寸', '%s(%s) 占 %dx%d，Din=%d 不合规' % (m['id'], m['model'], w, h, m['Din']))
    if len(m['recipe_ids']) != 1: bad('配方', '%s 配方数不为 1' % m['id'])
    for r in m['recipe_ids']:
        if RECIPE[r][0] != m['model']: bad('配方', '%s 配方 %s 不属于 %s' % (m['id'], r, m['model']))
    if m['settings'] != {'manufacture_on': True}: bad('开关', '%s 制造开关不是开' % m['id'])
    units[m['id']] = dict(cls='machine', model=m['model'], b=b, Din=m['Din'], recipe=m['recipe_ids'][0])
    place(m['id'], rect_cells(*b), 'machine')
    model_count[m['model']] += 1
    for c, o in edge_cells(b, m['Din']): ports[m['id']].append((c, m['Din'], o, 'in'))
    for c, o in edge_cells(b, opp(m['Din'])): ports[m['id']].append((c, opp(m['Din']), o, 'out'))

core = L['core']
cb = (core['x0'], core['y0'], core['x1'], core['y1'])
if (cb[2] - cb[0] + 1, cb[3] - cb[1] + 1) != (9, 9): bad('协议核心', '核心不是 9x9')
units['CORE'] = dict(cls='core', b=cb, Din=core['Din'])
place('CORE', rect_cells(*cb), 'core')
core_out_item = {}
for s in (core['Din'], opp(core['Din'])):
    for c, o in edge_cells(cb, s):
        if 1 <= o <= 7: ports['CORE'].append((c, s, o, 'in'))
for s in ((core['Din'] + 1) % 4, (core['Din'] + 3) % 4):
    for c, o in edge_cells(cb, s):
        if o in (1, 4, 7): ports['CORE'].append((c, s, o, 'out'))
for it in core['output_items']:
    core_out_item[(it['side'], it['offset'])] = it['item']
if sorted(core_out_item) != sorted((s, o) for s in ((core['Din'] + 1) % 4, (core['Din'] + 3) % 4) for o in (1, 4, 7)):
    bad('协议核心', '核心六口物品设定不全或错位')
if set(core_out_item.values()) != {'源矿'}: bad('协议核心', '核心六口不全是源矿（S2 要求全设源矿）')

outlet_side = {}
for o in L['warehouse_outlets']:
    b = (o['x0'], o['y0'], o['x1'], o['y1'])
    if o['Dout'] == 0:
        ok = b[0] == 0 and b[2] == 0 and b[3] == b[1] + 2
        side = '左'
    elif o['Dout'] == 1:
        ok = b[1] == 0 and b[3] == 0 and b[2] == b[0] + 2
        side = '下'
    else:
        ok = False; side = '?'
    if not ok: bad('取货口位置', '%s 不是贴左/下边界的 3x1（规则第74行、任务第15行）' % o['id'])
    if o['item'] not in ('源矿', '蓝铁矿'): bad('取货口', '%s 物品设定不是矿' % o['id'])
    outlet_side[o['id']] = side
    units[o['id']] = dict(cls='outlet', b=b, item=o['item'], side=side)
    place(o['id'], rect_cells(*b), 'outlet')
    # 向内长边中间
    ports[o['id']].append((edge_cells(b, o['Dout'])[1][0], o['Dout'], 1, 'out'))

for p in L['power_poles']:
    b = (p['x0'], p['y0'], p['x1'], p['y1'])
    if (b[2] - b[0] + 1, b[3] - b[1] + 1) != (2, 2): bad('供电桩', '%s 不是 2x2' % p['id'])
    units[p['id']] = dict(cls='pole', b=b)
    place(p['id'], rect_cells(*b), 'pole')

if L['storage_boxes']: bad('S2', '有协议储存箱')

for t in L['transport']:
    c = (t['x'], t['y'])
    units[t['id']] = dict(cls='transport', type=t['type'], cell=c, rec=t)
    place(t['id'], [c], 'transport')
    if t['type'] == 'belt':
        if t['in_side'] == t['out_side']: bad('传送带', '%s 存取同边' % t['id'])
        ports[t['id']].append((c, t['in_side'], 0, 'in'))
        ports[t['id']].append((c, t['out_side'], 0, 'out'))
    elif t['type'] == 'bridge':
        for s in range(4):
            ports[t['id']].append((c, s, 0, 'in'))
            ports[t['id']].append((c, s, 0, 'out'))
    else:
        bad('S2', '%s 类型 %s 不是传送带或桥接器' % (t['id'], t['type']))

out['counts'] = {
    'machines': len(L['machines']), 'models': dict(model_count),
    'outlets': len(L['warehouse_outlets']), 'poles': len(L['power_poles']),
    'transport': len(L['transport']),
    'belts': sum(1 for t in L['transport'] if t['type'] == 'belt'),
    'bridges': sum(1 for t in L['transport'] if t['type'] == 'bridge'),
    'occupied_cells': len(owner),
    'machine_cells': sum(1 for c, u in owner.items() if units[u]['cls'] == 'machine'),
    'non_transport_cells': sum(1 for c, u in owner.items() if units[u]['cls'] != 'transport'),
}
EXPECT_MODELS = {'粉碎机': 71, '精炼炉': 51, '研磨机': 32, '塑形机': 6, '配件机': 6, '种植机': 38, '采种机': 19, '封装机': 3, '灌装机': 4}
if dict(model_count) != EXPECT_MODELS: bad('台数', '机型台数与 S2 不同：%s' % dict(model_count))

# ---------- 取货口：左/下各数、边带排布（约束第128行） ----------
oc = collections.Counter(outlet_side.values())
out['outlets_by_side'] = dict(oc)
if oc.get('左', 0) != 23 or oc.get('下', 0) != 23: bad('取货口配置', '左、下取货口数不是各 23：%s' % dict(oc))
out['outlet_items'] = dict(collections.Counter(u['item'] for u in units.values() if u['cls'] == 'outlet'))
gaps = {}
for side in ('左', '下'):
    used = set()
    for uid, u in units.items():
        if u['cls'] == 'outlet' and u['side'] == side:
            x0, y0, x1, y1 = u['b']
            used |= set(range(y0, y1 + 1)) if side == '左' else set(range(x0, x1 + 1))
    gaps[side] = sorted(set(range(N)) - used)
out['edge_gaps'] = gaps
for side, g in gaps.items():
    if len(g) != 1 or g[0] % 3 != 0: bad('边带排布', '%s边的空格 %s 不是恰一个且位于第3k+1格' % (side, g))
if not (gaps.get('左') == [0] or gaps.get('下') == [0]): bad('边带排布', '两边空格都不在角格')

# ---------- 供电 ----------
unpowered = []
for uid, u in units.items():
    if u['cls'] != 'machine': continue
    x0, y0, x1, y1 = u['b']
    ok = False
    for pid, p in units.items():
        if p['cls'] != 'pole': continue
        px0, py0 = p['b'][0], p['b'][1]
        cx0, cx1, cy0, cy1 = px0 - 5, px0 + 6, py0 - 5, py0 + 6
        if x0 <= cx1 and cx0 <= x1 and y0 <= cy1 and cy0 <= y1: ok = True; break
    if not ok: unpowered.append(uid)
out['unpowered_machines'] = unpowered
if unpowered: bad('供电', '无供电制造单位：%s' % unpowered)

# ---------- 通道重建 ----------
port_index = collections.defaultdict(list)  # (cell, side, io) -> [(uid, offset)]
for uid, pl in ports.items():
    for c, s, o, io in pl:
        port_index[(c, s, io)].append((uid, o))
channels = set()
for uid, pl in ports.items():
    for c, s, o, io in pl:
        if io != 'out': continue
        dx, dy = DXY[s]
        n = (c[0] + dx, c[1] + dy)
        if n not in owner: continue
        v = owner[n]
        if v == uid: continue
        for (v2, o2) in port_index.get((n, opp(s), 'in'), []):
            if v2 != v: continue
            if units[uid]['cls'] == 'transport' or units[v]['cls'] == 'transport':
                channels.add((uid, s, o, v, opp(s), o2))
out['channels_rebuilt'] = len(channels)

def pref(p): return (p['unit'], p['side'], p['offset'])
decl = set()
decl_by_id = {}
for pc in cand['design']['physical_channels']:
    key = pref(pc['from']) + pref(pc['to'])
    if key in decl: bad('通道声明', '声明通道重复 %s' % pc['id'])
    decl.add(key); decl_by_id[pc['id']] = key
out['channels_declared'] = len(decl)
out['channels_undeclared'] = sorted(map(list, channels - decl))
out['channels_declared_not_real'] = sorted(map(list, decl - channels))
if channels != decl: bad('通道声明', '声明与重建不一致：多 %d 少 %d' % (len(decl - channels), len(channels - decl)))

# 桥接器方向声明
def axis(s): return 'H' if s in (0, 2) else 'V'
bridge_info = {}
for uid, u in units.items():
    if u['cls'] != 'transport' or u['type'] != 'bridge': continue
    ins = [ch for ch in channels if ch[3] == uid]
    outs = [ch for ch in channels if ch[0] == uid]
    info = {}
    for ax in ('H', 'V'):
        ai = sorted(ch[4] for ch in ins if axis(ch[4]) == ax)
        ao = sorted(ch[1] for ch in outs if axis(ch[1]) == ax)
        info[ax] = {'in_sides': ai, 'out_sides': ao}
    bridge_info[uid] = info
    rec = u['rec']
    for ax, key in (('H', 'H_in'), ('V', 'V_in')):
        ai = info[ax]['in_sides']
        derived = ai[0] if len(ai) == 1 else None
        if rec[key] != derived: bad('桥接器', '%s %s轴声明入边 %s 与重建 %s 不符' % (uid, ax, rec[key], ai))
# 相邻桥
adj_bridges = []
for uid, u in units.items():
    if u['cls'] == 'transport' and u['type'] == 'bridge':
        x, y = u['cell']
        for s in (0, 1):
            n = (x + DXY[s][0], y + DXY[s][1])
            if n in owner and units[owner[n]]['cls'] == 'transport' and units[owner[n]]['type'] == 'bridge':
                adj_bridges.append((uid, owner[n]))
out['adjacent_bridge_pairs'] = adj_bridges

# ---------- 进路追踪（顺流） ----------
def node_of(uid, side):
    u = units[uid]
    if u['cls'] != 'transport': return None
    if u['type'] == 'bridge': return (uid, axis(side))
    return (uid, '-')
in_ch = collections.defaultdict(list); out_ch = collections.defaultdict(list)
for ch in channels:
    a = node_of(ch[0], ch[1]); b2 = node_of(ch[3], ch[4])
    if a: out_ch[a].append(ch)
    if b2: in_ch[b2].append(ch)
# 每个运输节点的度
tnodes = set()
for uid, u in units.items():
    if u['cls'] == 'transport':
        if u['type'] == 'bridge': tnodes |= {(uid, 'H'), (uid, 'V')}
        else: tnodes.add((uid, '-'))
deg_anom = []
for nd in sorted(tnodes):
    i, o = len(in_ch[nd]), len(out_ch[nd])
    if units[nd[0]]['type'] == 'bridge' and i == 0 and o == 0: continue
    if i != 1 or o != 1: deg_anom.append({'node': list(nd), 'cell': list(units[nd[0]]['cell']), 'in': i, 'out': o})
    elif units[nd[0]]['type'] == 'bridge':
        if in_ch[nd][0][4] != opp(out_ch[nd][0][1]): deg_anom.append({'node': list(nd), 'cell': list(units[nd[0]]['cell']), 'not_straight': True})
out['transport_degree_anomalies'] = deg_anom
for a in deg_anom: bad('进路断头/分叉', '运输节点 %s 格 %s 入 %s 出 %s' % (a['node'], a['cell'], a.get('in'), a.get('out')))

routes = []
visited = collections.Counter()
for ch in sorted(channels):
    if units[ch[0]]['cls'] == 'transport': continue
    src = ch[0]; cells = []; path_ch = [ch]; cur = ch; seen_units = set(); ok = True
    while True:
        nd = node_of(cur[3], cur[4])
        if nd is None:
            dst = cur[3]; break
        cells.append(nd); visited[nd] += 1
        if nd[0] in seen_units: bad('进路', '进路重复经过物理单位 %s' % nd[0])
        seen_units.add(nd[0])
        nxt = [c for c in out_ch[nd]]
        if units[nd[0]]['type'] == 'bridge':
            nxt = [c for c in nxt if c[1] == opp(cur[4])]
        if len(nxt) != 1: ok = False; dst = None; break
        cur = nxt[0]; path_ch.append(cur)
        if len(cells) > 5000: ok = False; dst = None; break
    routes.append(dict(src=src, src_port=[ch[1], ch[2]], dst=dst, dst_port=[cur[4], cur[5]] if ok else None,
                       nodes=[list(n) for n in cells], cells=[list(units[n[0]]['cell']) for n in cells], complete=ok,
                       channels=[list(c) for c in path_ch]))
complete = [r for r in routes if r['complete']]
incomplete = [r for r in routes if not r['complete']]
for r in incomplete:
    bad('进路未达终点', '自 %s 端口 %s 出发的进路在 %s 断开' % (r['src'], r['src_port'], r['cells'][-1] if r['cells'] else '首格'))
shared = [list(n) for n, k in visited.items() if k > 1]
if shared: bad('进路共用格', '运输节点被多条进路使用：%s' % shared)
orphan = [list(n) for n in tnodes if visited[n] == 0 and not (units[n[0]]['type'] == 'bridge' and not in_ch[n] and not out_ch[n])]
out['orphan_transport_nodes'] = orphan
if orphan: bad('多余运输单位', '不在任何从机器出发的进路上：%s' % orphan)
# 每座桥两轴是否属不同进路
route_of_node = {}
for i, r in enumerate(complete):
    for n in r['nodes']: route_of_node[tuple(n)] = i
bridges_table = []
for uid, info in sorted(bridge_info.items()):
    rh = route_of_node.get((uid, 'H')); rv = route_of_node.get((uid, 'V'))
    def lab(i): return None if i is None else '%s→%s' % (complete[i]['src'], complete[i]['dst'])
    bridges_table.append({'bridge': uid, 'cell': list(units[uid]['cell']), 'H': lab(rh), 'V': lab(rv),
                          'H_in': info['H']['in_sides'], 'V_in': info['V']['in_sides']})
    if rh is not None and rh == rv: bad('桥接器', '%s 两轴属于同一条进路' % uid)
    for ax, ri in (('H', rh), ('V', rv)):
        if ri is None and (info[ax]['in_sides'] or info[ax]['out_sides']): bad('桥接器', '%s %s轴有通道但不在完整进路上' % (uid, ax))
out['bridges'] = bridges_table

# ---------- 物品 ----------
def out_items(uid, port):
    u = units[uid]
    if u['cls'] == 'outlet': return {u['item']}
    if u['cls'] == 'core': return {core_out_item[(port[0], port[1])]}
    return set(RECIPE[u['recipe']][2])
def in_ok(uid, item):
    u = units[uid]
    if u['cls'] == 'core': return item in ('高容谷地电池', '精选荞愈胶囊')
    return item in RECIPE[u['recipe']][1]
for r in complete:
    its = out_items(r['src'], r['src_port'])
    r['item'] = sorted(its)[0]
    if len(its) != 1 or not in_ok(r['dst'], r['item']):
        bad('物品', '进路 %s→%s 运 %s，终点不收' % (r['src'], r['dst'], its))

# ---------- S2 第 2 节期望接法（按出发单位写） ----------
def S2_expected():
    E = []  # (src_label, dst)
    for i in range(1, 35):
        E.append(('矿口:蓝铁矿', 'RF%d' % i)); E.append(('RF%d' % i, 'KF%d' % i))
    for i in range(1, 18):
        E.append(('KF%d' % (2 * i - 1), 'B%d' % i)); E.append(('KF%d' % (2 * i), 'B%d' % i))
    for i in range(1, 19):
        E.append(('核心:源矿' if i <= 6 else '矿口:源矿', 'KO%d' % i))
    for i in range(1, 10):
        E.append(('KO%d' % (2 * i - 1), 'O%d' % i)); E.append(('KO%d' % (2 * i), 'O%d' % i))
    for i in range(1, 18): E.append(('B%d' % i, 'R%d' % i))
    for i in range(1, 7): E.append(('R%d' % i, 'P%d' % i))
    for r, h in [(7, 1), (8, 1), (9, 2), (10, 2), (11, 3), (12, 3), (13, 4), (14, 4), (15, 5), (16, 5), (17, 6)]:
        E.append(('R%d' % r, 'H%d' % h))
    for i in range(1, 4):
        E.append(('P%d' % (2 * i - 1), 'E%d' % i)); E.append(('P%d' % (2 * i), 'E%d' % i))
        for j in (3 * i - 2, 3 * i - 1, 3 * i): E.append(('O%d' % j, 'E%d' % i))
    for f, srcs in [(1, ['H1', 'H2', 'Q1', 'Q2']), (2, ['H3', 'H4', 'Q3', 'Q4']), (3, ['H5', 'Q5']), (4, ['H6', 'Q6'])]:
        for s in srcs: E.append((s, 'F%d' % f))
    for s in ['E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4']: E.append((s, 'CORE'))
    for p, n in (('S', 13), ('Q', 6)):
        for j in range(1, n + 1):
            K = 'S%d' % j if p == 'S' else 'QK%d' % j
            E += [(p + 'C%d' % j, p + 'A%d' % j), (p + 'C%d' % j, p + 'B%d' % j), (p + 'A%d' % j, p + 'C%d' % j), (p + 'B%d' % j, K)]
    sand = {1: ['B1', 'B2', 'O1'], 2: ['O2', 'O3'], 3: ['B3', 'B4', 'O4'], 4: ['O5', 'O6'], 5: ['B5', 'B6', 'O7'], 6: ['O8', 'O9'],
            7: ['B7', 'B8', 'B9'], 8: ['B10', 'Q1', 'Q2'], 9: ['B11', 'B12', 'B13'], 10: ['B14', 'Q3', 'Q4'], 11: ['B15', 'B16', 'Q5'],
            12: ['B17'], 13: ['Q6']}
    for j, ds in sand.items():
        for d in ds: E.append(('S%d' % j, d))
    for j in range(1, 6):
        E.append(('QK%d' % j, 'Q%d' % j)); E.append(('QK%d' % j, 'Q%d' % j))
    E.append(('QK6', 'Q6'))
    return E
EXP = S2_expected()
out['S2_expected_routes'] = len(EXP)
def label(r):
    u = units[r['src']]
    if u['cls'] == 'outlet': return ('矿口:' + u['item'], r['dst'])
    if u['cls'] == 'core': return ('核心:' + core_out_item[tuple(r['src_port'])], r['dst'])
    return (r['src'], r['dst'])
got = collections.Counter(label(r) for r in complete)
exp = collections.Counter(EXP)
missing = exp - got
extra = got - exp
out['routes_complete'] = len(complete)
out['routes_incomplete'] = len(incomplete)
out['routes_matched'] = sum((exp & got).values())
out['routes_missing'] = sorted([list(k) + [v] for k, v in missing.items()])
out['routes_missing_count'] = sum(missing.values())
out['routes_extra'] = sorted([list(k) + [v] for k, v in extra.items()])
if extra: bad('S2接法', '接法外进路：%s' % dict(extra))
if missing: bad('S2接法', '缺 %d 条 S2 进路' % sum(missing.values()))
# 同一单位不同进路用不同端口（由通道唯一性自动成立）；矿口、核心口每口至多一路
src_port_use = collections.Counter((r['src'], tuple(r['src_port'])) for r in complete)
dst_port_use = collections.Counter((r['dst'], tuple(r['dst_port'])) for r in complete)
if any(v > 1 for v in src_port_use.values()) or any(v > 1 for v in dst_port_use.values()): bad('端口', '同一端口多条进路')
# 标签一致：矿口编号 WFEi→RFi、WOi→KOi（只作记录）
out['outlet_label_pairs_mismatch'] = [(r['src'], r['dst']) for r in complete
    if units[r['src']]['cls'] == 'outlet' and r['src'].lstrip('WFEO') != r['dst'].lstrip('RFKO')]

# 机器出口接法：每台机器的进路出口数与 S2 一致（缺路时记录）
# ---------- H6→F4 与 Q6→F4 ----------
def rlen(s, d):
    return [len(r['nodes']) for r in complete if r['src'] == s and r['dst'] == d]
out['H6_F4_len'] = rlen('H6', 'F4'); out['Q6_F4_len'] = rlen('Q6', 'F4')
if out['H6_F4_len'] != out['Q6_F4_len'] or len(out['H6_F4_len']) != 1:
    bad('等长', 'H6→F4 运输物品格数 %s，Q6→F4 运输物品格数 %s，不相等' % (out['H6_F4_len'], out['Q6_F4_len']))

# 与声明的 logical_feeds 比对（只核对，不作为事实来源）
lf_keys = collections.Counter()
for lf in cand['design'].get('logical_feeds', []):
    lf_keys[(lf['from']['unit'], lf['to']['unit'], len(lf['path']))] += 1
mine = collections.Counter((r['src'], r['dst'], len(r['nodes']) + 1) for r in complete)
out['logical_feeds_declared'] = sum(lf_keys.values())
out['logical_feeds_equal_rebuilt'] = (lf_keys == mine)

# ---------- 空矩形（对每个列区间做行扫描） ----------
occ = [[False] * N for _ in range(N)]
for (x, y) in owner: occ[x][y] = True
best = None
for x0 in range(N):
    rowfree = [True] * N
    for x1 in range(x0, N):
        for y in range(N):
            if occ[x1][y]: rowfree[y] = False
        w = x1 - x0 + 1
        if w < 6: continue
        if not any(rowfree): break
        y = 0
        while y < N:
            if rowfree[y]:
                y2 = y
                while y2 + 1 < N and rowfree[y2 + 1]: y2 += 1
                h = y2 - y + 1
                if h >= 6:
                    key = (w * h, min(w, h))
                    if best is None or key > best[0]: best = (key, (x0, y, x1, y2))
                y = y2 + 1
            else: y += 1
out['max_empty_rect'] = None if best is None else {'area': best[0][0], 'short': best[0][1], 'bounds': list(best[1])}
# 所有达到最优的位置
ties = []
if best:
    A, S = best[0]
    for x0 in range(N):
        for x1 in range(x0 + 5, N):
            w = x1 - x0 + 1
            if A % w: continue
            h = A // w
            if h < 6 or min(w, h) != S: continue
            for y0 in range(0, N - h + 1):
                if all(not occ[x][y] for x in range(x0, x1 + 1) for y in range(y0, y0 + h)): ties.append([x0, y0, x1, y0 + h - 1])
out['max_empty_rect_all'] = ties
er = cand['empty_rectangle']
out['declared_rect'] = er
out['declared_rect_empty'] = all(not occ[x][y] for x in range(er['x0'], er['x1'] + 1) for y in range(er['y0'], er['y1'] + 1))

out['routes'] = [{k: r[k] for k in ('src', 'src_port', 'dst', 'dst_port', 'item', 'cells')} for r in complete]
out['problems'] = [list(p) for p in problems]
json.dump(out, open(OUTFILE, 'w'), ensure_ascii=False, indent=1)
summ = {k: v for k, v in out.items() if k not in ('routes', 'routes_missing', 'channels_undeclared', 'channels_declared_not_real', 'problems', 'max_empty_rect_all')}
print(json.dumps(summ, ensure_ascii=False, indent=1))
print('problems:', len(problems))
for p in collections.Counter(c for c, _ in problems).items(): print(p)
for p in problems:
    if p[0] not in ('S2接法',): print(p)

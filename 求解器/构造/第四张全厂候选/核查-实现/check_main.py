#!/usr/bin/env python3
"""核查-实现 编码一：从布局文件的单位占格、朝向和设定独立重建端口、通道、进路，
并与第107轮 S2B 第2节接法逐条比对。不读实现席的任何程序或中间文件，
physical_channels / logical_feeds / H_in / V_in / empty_rectangle 只拿来和重建结果比对。

用法：python3 check_main.py <布局.json> <输出.json>
"""
import json, sys, collections, hashlib

LAYOUT = sys.argv[1]
OUT = sys.argv[2]
raw = open(LAYOUT, 'rb').read()
SHA = hashlib.sha256(raw).hexdigest()


def no_dup(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise SystemExit('重复键 %s' % k)
        d[k] = v
    return d


doc = json.loads(raw, object_pairs_hook=no_dup)
L = doc['layout']
W = H = 70
DX = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
opp = lambda s: (s + 2) % 4
problems = []   # (类别, 说明)


def prob(cat, msg):
    problems.append({'类别': cat, '说明': msg})


# ---------------- 机型与配方（规则原文） ----------------
KIND = {'粉碎机': '小', '精炼炉': '小', '配件机': '小', '塑形机': '小',
        '采种机': '中', '种植机': '中', '研磨机': '大', '封装机': '大', '灌装机': '大'}
RECIPE = {  # 配方 -> (机型, {原料:量}, {产物:量})
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

# ---------------- S2B 第2节：逐台身份 -> 机型、配方 ----------------
ident = {}
for i in range(1, 35):
    ident['RF%d' % i] = ('精炼炉', '精炼-蓝铁矿')
    ident['KF%d' % i] = ('粉碎机', '粉碎-蓝铁块')
for i in range(1, 19):
    ident['KO%d' % i] = ('粉碎机', '粉碎-源矿')
for i in range(1, 18):
    ident['B%d' % i] = ('研磨机', '研磨-致密蓝铁')
    ident['R%d' % i] = ('精炼炉', '精炼-致密蓝铁')
for i in range(1, 10):
    ident['O%d' % i] = ('研磨机', '研磨-致密源石')
for i in range(1, 7):
    ident['Q%d' % i] = ('研磨机', '研磨-细磨荞花')
    ident['P%d' % i] = ('配件机', '配件-钢制零件')
    ident['H%d' % i] = ('塑形机', '塑形-钢质瓶')
for i in range(1, 4):
    ident['E%d' % i] = ('封装机', '封装-电池')
for i in range(1, 5):
    ident['F%d' % i] = ('灌装机', '灌装-胶囊')
for i in range(1, 14):
    ident['SC%d' % i] = ('采种机', '采种-砂叶')
    ident['SA%d' % i] = ('种植机', '种植-砂叶')
    ident['SB%d' % i] = ('种植机', '种植-砂叶')
    ident['S%d' % i] = ('粉碎机', '粉碎-砂叶')
for i in range(1, 7):
    ident['QC%d' % i] = ('采种机', '采种-荞花')
    ident['QA%d' % i] = ('种植机', '种植-荞花')
    ident['QB%d' % i] = ('种植机', '种植-荞花')
    ident['QK%d' % i] = ('粉碎机', '粉碎-荞花')
assert len(ident) == 230

# ---------------- S2B 第2节：325 条进路（源, 汇） ----------------
expected = []
for i in range(1, 35):
    expected.append(('仓库取货口:蓝铁矿', 'RF%d' % i))
    expected.append(('RF%d' % i, 'KF%d' % i))
for i in range(1, 18):
    expected.append(('KF%d' % (2 * i - 1), 'B%d' % i))
    expected.append(('KF%d' % (2 * i), 'B%d' % i))
for i in range(1, 19):
    expected.append(('CORE' if i <= 6 else '仓库取货口:源矿', 'KO%d' % i))
for i in range(1, 10):
    expected.append(('KO%d' % (2 * i - 1), 'O%d' % i))
    expected.append(('KO%d' % (2 * i), 'O%d' % i))
for i in range(1, 18):
    expected.append(('B%d' % i, 'R%d' % i))
for i in range(1, 7):
    expected.append(('R%d' % i, 'P%d' % i))
for h, rs in {1: (7, 8), 2: (9, 10), 3: (11, 12), 4: (13, 14), 5: (15, 16), 6: (17,)}.items():
    for r in rs:
        expected.append(('R%d' % r, 'H%d' % h))
for i in range(1, 4):
    expected += [('P%d' % (2 * i - 1), 'E%d' % i), ('P%d' % (2 * i), 'E%d' % i)]
    expected += [('O%d' % (3 * i - 2), 'E%d' % i), ('O%d' % (3 * i - 1), 'E%d' % i), ('O%d' % (3 * i), 'E%d' % i)]
for f, hs, qs in [(1, (1, 2), (1, 2)), (2, (3, 4), (3, 4)), (3, (5,), (5,)), (4, (6,), (6,))]:
    for h in hs:
        expected.append(('H%d' % h, 'F%d' % f))
    for q in qs:
        expected.append(('Q%d' % q, 'F%d' % f))
for m in ['E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4']:
    expected.append((m, 'CORE'))
for p, n in (('S', 13), ('Q', 6)):
    for i in range(1, n + 1):
        C, A, B = p + 'C%d' % i, p + 'A%d' % i, p + 'B%d' % i
        K = ('S%d' % i) if p == 'S' else ('QK%d' % i)
        expected += [(C, A), (C, B), (A, C), (B, K)]
for i in range(1, 6):
    expected += [('QK%d' % i, 'Q%d' % i)] * 2
expected.append(('QK6', 'Q6'))
SAND = {1: 'B1 B2 O1', 2: 'O2 O3', 3: 'B3 B4 O4', 4: 'O5 O6', 5: 'B5 B6 O7', 6: 'O8 O9',
        7: 'B7 B8 B9', 8: 'B10 Q1 Q2', 9: 'B11 B12 B13', 10: 'B14 Q3 Q4', 11: 'B15 B16 Q5',
        12: 'B17', 13: 'Q6'}
for i, s in SAND.items():
    for t in s.split():
        expected.append(('S%d' % i, t))
assert len(expected) == 325, len(expected)
# 每台研磨机恰一条砂叶粉末来路
_sinks = collections.Counter(t for s, t in expected if s.startswith('S') and s[1:].isdigit())
for i in range(1, 18):
    assert _sinks['B%d' % i] == 1
for i in range(1, 10):
    assert _sinks['O%d' % i] == 1
for i in range(1, 7):
    assert _sinks['Q%d' % i] == 1

# ---------------- 单位、占格 ----------------
units = {}   # id -> dict(cat, cells(set), bounds, ...)
occ = {}     # (x,y) -> id


def add_unit(uid, cat, x0, y0, x1, y1, **kw):
    if uid in units:
        prob('单位', '单位 id 重复：%s' % uid)
    if not (0 <= x0 <= x1 < W and 0 <= y0 <= y1 < H):
        prob('单位', '%s 出界 (%d,%d)-(%d,%d)' % (uid, x0, y0, x1, y1))
    cells = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    for c in cells:
        if c in occ:
            prob('单位', '%s 与 %s 在 %s 重叠' % (uid, occ[c], c))
        occ[c] = uid
    u = dict(id=uid, cat=cat, x0=x0, y0=y0, x1=x1, y1=y1, cells=cells)
    u.update(kw)
    units[uid] = u
    return u


MSET = set()
for m in L['machines']:
    keys = set(m.keys())
    if keys != {'id', 'model', 'kind', 'x0', 'y0', 'x1', 'y1', 'Din', 'recipe_ids', 'settings'}:
        prob('单位', '%s 字段集合不符 %s' % (m['id'], sorted(keys)))
    uid = m['id']
    MSET.add(uid)
    w, h = m['x1'] - m['x0'] + 1, m['y1'] - m['y0'] + 1
    k = m['kind']
    if KIND.get(m['model']) != k:
        prob('单位', '%s 机型 %s 与尺寸类别 %s 不符' % (uid, m['model'], k))
    if k == '小':
        ok = (w, h) == (3, 3)
    elif k == '中':
        ok = (w, h) == (5, 5)
    else:
        ok = (w, h) == ((6, 4) if m['Din'] in (1, 3) else (4, 6))
    if not ok:
        prob('单位', '%s %s 尺寸 %dx%d 与 Din=%d 不符' % (uid, m['model'], w, h, m['Din']))
    if m['Din'] not in (0, 1, 2, 3):
        prob('单位', '%s Din 非法' % uid)
    if uid not in ident:
        prob('接法', '%s 不是 S2B 第2节的机器身份' % uid)
    else:
        mod, rec = ident[uid]
        if m['model'] != mod or m['recipe_ids'] != [rec]:
            prob('接法', '%s 应为 %s/%s，实为 %s/%s' % (uid, mod, rec, m['model'], m['recipe_ids']))
    for r in m['recipe_ids']:
        if r not in RECIPE or RECIPE[r][0] != m['model']:
            prob('单位', '%s 配方 %s 不属于机型 %s' % (uid, r, m['model']))
    if m['settings'] != {'manufacture_on': True}:
        prob('单位', '%s 制造开关不是开' % uid)
    add_unit(uid, 'machine', m['x0'], m['y0'], m['x1'], m['y1'], Din=m['Din'], model=m['model'],
             recipe=m['recipe_ids'][0], kind=k)
missing_ident = set(ident) - MSET
if missing_ident:
    prob('接法', '缺少机器身份：%s' % sorted(missing_ident))

for o in L['warehouse_outlets']:
    uid = o['id']
    if set(o.keys()) != {'id', 'x0', 'y0', 'x1', 'y1', 'Dout', 'item'}:
        prob('单位', '%s 字段集合不符' % uid)
    x0, y0, x1, y1 = o['x0'], o['y0'], o['x1'], o['y1']
    if x0 == x1 == 0 and y1 == y0 + 2:
        side, pos = 'L', 0
        if o['Dout'] != 0:
            prob('取货口', '%s 贴左边界但 Dout=%d' % (uid, o['Dout']))
        port = ((0, y0 + 1), 0)
    elif y0 == y1 == 0 and x1 == x0 + 2:
        side = 'B'
        if o['Dout'] != 1:
            prob('取货口', '%s 贴下边界但 Dout=%d' % (uid, o['Dout']))
        port = ((x0 + 1, 0), 1)
    else:
        prob('取货口', '%s 不是长边贴左或下边界的 3×1：(%d,%d)-(%d,%d)' % (uid, x0, y0, x1, y1))
        side, port = '?', None
    if o['item'] not in ('源矿', '蓝铁矿'):
        prob('取货口', '%s 物品 %s 不是矿' % (uid, o['item']))
    add_unit(uid, 'outlet', x0, y0, x1, y1, band=side, port=port, item=o['item'])

c = L['core']
if c['x1'] - c['x0'] != 8 or c['y1'] - c['y0'] != 8:
    prob('协议核心', '协议核心不是 9×9')
core_out = {}
for it in c['output_items']:
    core_out[(it['side'], it['offset'])] = it['item']
need_sides = {(c['Din'] + 1) % 4, (c['Din'] + 3) % 4}
if set(core_out) != {(s, o) for s in need_sides for o in (1, 4, 7)}:
    prob('协议核心', '取货端口设定不是两条取货边各 1、4、7：%s' % sorted(core_out))
for k_, v in core_out.items():
    if v != '源矿':
        prob('协议核心', '取货端口 %s 设为 %s，S2B 要求全设源矿' % (k_, v))
add_unit('CORE', 'core', c['x0'], c['y0'], c['x1'], c['y1'], Din=c['Din'], out=core_out)

for p in L['power_poles']:
    if p['x1'] - p['x0'] != 1 or p['y1'] - p['y0'] != 1 or p.get('orientation') != 0:
        prob('供电桩', '%s 不是 2×2' % p['id'])
    add_unit(p['id'], 'pole', p['x0'], p['y0'], p['x1'], p['y1'])

if L['storage_boxes']:
    prob('禁用单位', '有协议储存箱 %d 个' % len(L['storage_boxes']))
if L['vin'] or L['vout']:
    prob('禁用单位', 'vin/vout 非空')

tcount = collections.Counter()
for t in L['transport']:
    tcount[t['type']] += 1
    uid = t['id']
    if t['type'] == 'belt':
        if set(t) != {'id', 'x', 'y', 'type', 'in_side', 'out_side'} or t['in_side'] == t['out_side']:
            prob('运输', '%s 传送带字段或方向非法' % uid)
        add_unit(uid, 'belt', t['x'], t['y'], t['x'], t['y'], ins=t['in_side'], outs=t['out_side'])
    elif t['type'] == 'bridge':
        if set(t) != {'id', 'x', 'y', 'type', 'H_in', 'V_in'}:
            prob('运输', '%s 桥接器字段非法' % uid)
        add_unit(uid, 'bridge', t['x'], t['y'], t['x'], t['y'], H_in=t['H_in'], V_in=t['V_in'])
    else:
        prob('禁用单位', '%s 类型 %s（只许传送带、桥接器）' % (uid, t['type']))
        add_unit(uid, t['type'], t['x'], t['y'], t['x'], t['y'])

TRANSPORT = {'belt', 'bridge'}


# ---------------- 端口 ----------------
def port_kind(uid, cell, side):
    """返回该单位在 cell 的 side 边上的端口类别：'in' / 'out' / 'both' / None"""
    u = units[uid]
    x, y = cell
    nx, ny = x + DX[side][0], y + DX[side][1]
    if (nx, ny) in u['cells']:
        return None  # 内部边
    cat = u['cat']
    if cat == 'belt':
        return 'in' if side == u['ins'] else ('out' if side == u['outs'] else None)
    if cat == 'bridge':
        return 'both'
    if cat == 'machine':
        if side == u['Din']:
            return 'in'
        if side == opp(u['Din']):
            return 'out'
        return None
    if cat == 'outlet':
        return 'out' if u['port'] == (cell, side) else None
    if cat == 'core':
        if side in (u['Din'], opp(u['Din'])):
            off = (x - u['x0']) if side in (1, 3) else (y - u['y0'])
            return 'in' if 1 <= off <= 7 else None
        off = (x - u['x0']) if side in (1, 3) else (y - u['y0'])
        return 'out' if (side, off) in u['out'] else None
    return None  # pole


def offset_of(uid, cell, side):
    u = units[uid]
    return (cell[0] - u['x0']) if side in (1, 3) else (cell[1] - u['y0'])


def axis(side):
    return 'H' if side in (0, 2) else 'V'


def node(uid, side):
    """物品格节点：运输单位为 (uid, 'c') 或 (uid,'H'/'V')；非运输单位为 None"""
    cat = units[uid]['cat']
    if cat == 'belt':
        return (uid, 'c')
    if cat == 'bridge':
        return (uid, axis(side))
    return None


# ---------------- 通道：逐相邻格对重建 ----------------
channels = []  # dict(fu, fc, fs, tu, tc, ts)
for (x, y), uid in sorted(occ.items()):
    for s in range(4):
        nb = (x + DX[s][0], y + DX[s][1])
        if nb not in occ:
            continue
        vid = occ[nb]
        if vid == uid:
            continue
        a = port_kind(uid, (x, y), s)
        b = port_kind(vid, nb, opp(s))
        if a in ('out', 'both') and b in ('in', 'both'):
            if units[uid]['cat'] in TRANSPORT or units[vid]['cat'] in TRANSPORT:
                channels.append(dict(fu=uid, fc=(x, y), fs=s, tu=vid, tc=nb, ts=opp(s)))
ch_out = collections.defaultdict(list)  # (uid, side, cell) -> channel
ch_in = collections.defaultdict(list)
for i, ch in enumerate(channels):
    ch['i'] = i
    ch_out[(ch['fu'], ch['fc'], ch['fs'])].append(ch)
    ch_in[(ch['tu'], ch['tc'], ch['ts'])].append(ch)

# 与声明比对
decl = set()
for pc in doc['design']['physical_channels']:
    f, t = pc['from'], pc['to']
    decl.add(((f['unit'], f['side'], f['offset']), (t['unit'], t['side'], t['offset'])))
rebuilt = set()
for ch in channels:
    rebuilt.add(((ch['fu'], ch['fs'], offset_of(ch['fu'], ch['fc'], ch['fs'])),
                 (ch['tu'], ch['ts'], offset_of(ch['tu'], ch['tc'], ch['ts']))))
if decl != rebuilt:
    prob('通道', '声明通道与重建不一致：多声明 %d，漏声明 %d' % (len(decl - rebuilt), len(rebuilt - decl)))


# ---------------- 物品 ----------------
def src_item(uid, cell, side):
    u = units[uid]
    if u['cat'] == 'machine':
        return list(RECIPE[u['recipe']][2])[0]
    if u['cat'] == 'outlet':
        return u['item']
    if u['cat'] == 'core':
        return u['out'][(side, offset_of(uid, cell, side))]
    return None


# ---------------- 进路：从非运输单位取货端口顺流追 ----------------
routes = []
dead = []
for ch in channels:
    if units[ch['fu']]['cat'] in TRANSPORT:
        continue
    item = src_item(ch['fu'], ch['fc'], ch['fs'])
    path_nodes, path_units, path_ch = [], [], [ch]
    cur = ch
    status = None
    while True:
        tu = cur['tu']
        if units[tu]['cat'] not in TRANSPORT:
            status = 'ok'
            break
        if tu in path_units:
            status = 'repeat-unit'
            break
        nd = node(tu, cur['ts'])
        path_nodes.append(nd)
        path_units.append(tu)
        if units[tu]['cat'] == 'belt':
            es = units[tu]['outs']
        else:
            es = opp(cur['ts'])
        nxt = ch_out.get((tu, cur['tc'], es), [])
        if len(nxt) != 1:
            status = 'dead-end' if not nxt else 'branch'
            break
        cur = nxt[0]
        path_ch.append(cur)
        if len(path_nodes) > 5000:
            status = 'loop'
            break
    rec = dict(src=ch['fu'], src_port=(ch['fs'], offset_of(ch['fu'], ch['fc'], ch['fs'])),
               item=item, nodes=path_nodes, units=path_units, chans=[c_['i'] for c_ in path_ch],
               status=status, first=ch['tc'])
    if status == 'ok':
        rec['dst'] = cur['tu']
        rec['dst_port'] = (cur['ts'], offset_of(cur['tu'], cur['tc'], cur['ts']))
        routes.append(rec)
    else:
        rec['last'] = cur['tc']
        dead.append(rec)
for r in dead:
    prob('进路', '从 %s 端口 %s 出发的运输链 %s 结束于 %s（%d 格）' % (
        r['src'], r['src_port'], r['status'], r['last'], len(r['nodes'])))

# 物品与汇的配方
for r in routes:
    u = units[r['dst']]
    if u['cat'] == 'machine':
        ins = RECIPE[u['recipe']][1]
        if r['item'] not in ins:
            prob('接法', '%s→%s 送 %s，不是 %s 的原料' % (r['src'], r['dst'], r['item'], u['recipe']))
    elif u['cat'] == 'core':
        if r['item'] not in ('高容谷地电池', '精选荞愈胶囊'):
            prob('接法', '%s→协议核心 送入非成品 %s' % (r['src'], r['item']))
    else:
        prob('接法', '进路汇 %s 不是制造单位或协议核心' % r['dst'])

# 物品格共用、通道归属
node_use = collections.defaultdict(list)
chan_use = collections.defaultdict(list)
for k_, r in enumerate(routes):
    for nd in r['nodes']:
        node_use[nd].append(k_)
    for ci in r['chans']:
        chan_use[ci].append(k_)
for nd, ks in node_use.items():
    if len(ks) > 1:
        prob('进路', '运输物品格 %s 被 %d 条进路共用' % (nd, len(ks)))

# 逆向通道：两端都是桥接器同轴，且该通道的反方向通道是某条进路的前向通道
reverse = []
extra = []
for ch in channels:
    if ch['i'] in chan_use:
        continue
    fu, tu = ch['fu'], ch['tu']
    if units[fu]['cat'] == 'bridge' and units[tu]['cat'] == 'bridge':
        rev = [c2 for c2 in ch_out.get((tu, ch['tc'], ch['ts']), []) if c2['tu'] == fu]
        if rev and rev[0]['i'] in chan_use:
            reverse.append(ch)
            continue
    extra.append(ch)
for ch in extra:
    prob('通道', '多余通道 %s%s 边%d → %s%s 边%d（不属于任何进路，也不是相邻桥逆向通道）' % (
        ch['fu'], ch['fc'], ch['fs'], ch['tu'], ch['tc'], ch['ts']))
decl_rev = set(doc['design'].get('bridge_reverse_channels', []))
pcmap = {pc['id']: pc for pc in doc['design']['physical_channels']}
decl_rev_set = set()
for i in decl_rev:
    pc = pcmap[i]
    decl_rev_set.add(((pc['from']['unit'], pc['from']['side']), (pc['to']['unit'], pc['to']['side'])))
my_rev_set = {((ch['fu'], ch['fs']), (ch['tu'], ch['ts'])) for ch in reverse}
if decl_rev_set != my_rev_set:
    prob('通道', '声明的逆向通道与重建不一致')

# 运输单位使用情况、桥接器两轴
bridge_rows = []
belt_unused = []
for uid, u in units.items():
    if u['cat'] == 'belt':
        if (uid, 'c') not in node_use:
            belt_unused.append(uid)
    elif u['cat'] == 'bridge':
        row = {'桥': uid, '格': [u['x0'], u['y0']]}
        for ax, sides in (('H', (0, 2)), ('V', (1, 3))):
            used = node_use.get((uid, ax), [])
            chs = [c_ for s in sides for c_ in ch_out.get((uid, (u['x0'], u['y0']), s), []) +
                   ch_in.get((uid, (u['x0'], u['y0']), s), [])]
            if used:
                r = routes[used[0]]
                idx = r['nodes'].index((uid, ax))
                # 入边：本路进入此轴的通道的 to-side
                inside = channels[r['chans'][idx]]['ts']
                row[ax] = '%s→%s（%s）' % (r['src'], r['dst'], r['item'])
                decl_in = u['H_in'] if ax == 'H' else u['V_in']
                if decl_in != inside:
                    prob('桥接器', '%s %s 轴声明入边 %s，重建为 %s' % (uid, ax, decl_in, inside))
            else:
                row[ax] = None
                if chs:
                    prob('桥接器', '%s %s 轴未用但有 %d 条通道' % (uid, ax, len(chs)))
                decl_in = u['H_in'] if ax == 'H' else u['V_in']
                if decl_in is not None:
                    prob('桥接器', '%s %s 轴未用但声明入边 %s' % (uid, ax, decl_in))
        if row['H'] and row['V']:
            rH = node_use[(uid, 'H')][0]
            rV = node_use[(uid, 'V')][0]
            if rH == rV:
                prob('桥接器', '%s 两轴属同一进路' % uid)
        if not row['H'] and not row['V']:
            prob('桥接器', '%s 两轴都未用' % uid)
        bridge_rows.append(row)

# 相邻桥对
adj_bridge = []
for uid, u in units.items():
    if u['cat'] != 'bridge':
        continue
    for s in (0, 1):
        nb = (u['x0'] + DX[s][0], u['y0'] + DX[s][1])
        if nb in occ and units[occ[nb]]['cat'] == 'bridge':
            adj_bridge.append((uid, occ[nb], axis(s)))

# 每条进路不重复物理单位已在追踪时检查；这里再查同路是否两次用同一桥
for r in routes:
    if len(set(r['units'])) != len(r['units']):
        prob('进路', '%s→%s 重复经过同一物理单位' % (r['src'], r['dst']))

# ---------------- 与 S2B 接法比对 ----------------
def norm_src(r):
    u = units[r['src']]
    if u['cat'] == 'outlet':
        return '仓库取货口:' + u['item']
    return r['src']


real = collections.Counter((norm_src(r), r['dst']) for r in routes)
exp = collections.Counter(expected)
missing = exp - real
extra_routes = real - exp
for (s, t), n in sorted(extra_routes.items()):
    prob('接法', '接法外的进路 %s→%s ×%d' % (s, t, n))
# 每个取货口、核心取货端口至多一路
src_port_use = collections.Counter((r['src'], r['src_port']) for r in routes)
for k_, n in src_port_use.items():
    if n > 1:
        prob('进路', '同一取货端口 %s 出 %d 路' % (k_, n))
dst_port_use = collections.Counter((r['dst'], r['dst_port']) for r in routes)
for k_, n in dst_port_use.items():
    if n > 1:
        prob('进路', '同一存货端口 %s 收 %d 路' % (k_, n))

# H6→F4 与 Q6→F4
def lens(s, t):
    return sorted(len(r['nodes']) for r in routes if r['src'] == s and r['dst'] == t)


eq = {'H6→F4': lens('H6', 'F4'), 'Q6→F4': lens('Q6', 'F4')}
if len(eq['H6→F4']) != 1 or len(eq['Q6→F4']) != 1 or eq['H6→F4'] != eq['Q6→F4']:
    prob('等长', 'H6→F4 %s，Q6→F4 %s' % (eq['H6→F4'], eq['Q6→F4']))

# ---------------- 与 logical_feeds 比对 ----------------
lf_set = set()
for f in doc['design']['logical_feeds']:
    lf_set.add((f['from']['unit'], f['from']['side'], f['from']['offset'], f['to']['unit'], f['to']['side'],
                f['to']['offset'], f['item'], len(f['path']) - 1))
my_set = set((r['src'], r['src_port'][0], r['src_port'][1], r['dst'], r['dst_port'][0], r['dst_port'][1],
              r['item'], len(r['nodes'])) for r in routes)
lf_cmp = {'声明条数': len(doc['design']['logical_feeds']), '重建条数': len(routes),
          '只在声明中': len(lf_set - my_set), '只在重建中': len(my_set - lf_set)}
if lf_set != my_set:
    prob('进路', 'logical_feeds 与重建不一致 %s' % lf_cmp)

# ---------------- 供电 ----------------
cover = set()
for p in L['power_poles']:
    for x in range(p['x0'] - 5, p['x0'] + 7):
        for y in range(p['y0'] - 5, p['y0'] + 7):
            if 0 <= x < W and 0 <= y < H:
                cover.add((x, y))
unpowered = [uid for uid, u in units.items() if u['cat'] == 'machine' and not (u['cells'] & cover)]
for uid in unpowered:
    prob('供电', '%s 无供电状态' % uid)
pole_load = {}
for p in L['power_poles']:
    cv = {(x, y) for x in range(p['x0'] - 5, p['x0'] + 7) for y in range(p['y0'] - 5, p['y0'] + 7)}
    pole_load[p['id']] = sum(1 for u in units.values() if u['cat'] == 'machine' and u['cells'] & cv)

# ---------------- 取货口：位置与边带排布 ----------------
outs = [u for u in units.values() if u['cat'] == 'outlet']
band = collections.Counter(u['band'] for u in outs)
items_cnt = collections.Counter(u['item'] for u in outs)
if len(outs) != 46 or items_cnt != collections.Counter({'蓝铁矿': 34, '源矿': 12}):
    prob('取货口', '取货口 %d 个，物品 %s；S2B 要 46 个（34 蓝铁矿、12 源矿）' % (len(outs), dict(items_cnt)))
band_info = {}
for b, coord in (('L', lambda u: u['y0']), ('B', lambda u: u['x0'])):
    used = set()
    for u in outs:
        if u['band'] == b:
            s0 = coord(u)
            used |= {s0, s0 + 1, s0 + 2}
    free = sorted(set(range(70)) - used)
    band_info[b] = free
# 边带排布（求解约束）：各 23 个，恰 1 空格且在 3k 位置，至少一边空格在角格
bb = []
if band['L'] != 23 or band['B'] != 23:
    bb.append('左、下取货口数 %d、%d，不是各 23' % (band['L'], band['B']))
for b in ('L', 'B'):
    if len(band_info[b]) != 1 or band_info[b][0] % 3 != 0:
        bb.append('%s 边未占格 %s' % (b, band_info[b]))
if not (band_info['L'] == [0] or band_info['B'] == [0]):
    bb.append('两边空格都不在角格')
facing_not_transport = []
for u in outs:
    if u['port'] is None:
        continue
    (cx, cy), s = u['port']
    nb = (cx + DX[s][0], cy + DX[s][1])
    if nb not in occ or units[occ[nb]]['cat'] not in TRANSPORT:
        facing_not_transport.append((u['id'], nb, occ.get(nb)))
if facing_not_transport:
    bb.append('%d 个取货口的取货端口正对格不是运输单位' % len(facing_not_transport))
for m in bb:
    prob('边带排布', m)

# ---------------- 空矩形 ----------------
grid = [[False] * H for _ in range(W)]
for (x, y) in occ:
    grid[x][y] = True
best = None
bests = []
for y0 in range(H):
    free = [True] * W
    for y1 in range(y0, H):
        for x in range(W):
            if grid[x][y1]:
                free[x] = False
        h = y1 - y0 + 1
        x = 0
        while x < W:
            if free[x]:
                x0 = x
                while x < W and free[x]:
                    x += 1
                w = x - x0
                if w >= 6 and h >= 6:
                    key = (w * h, min(w, h))
                    if best is None or key > best:
                        best, bests = key, [(x0, y0, x0 + w - 1, y1)]
                    elif key == best:
                        bests.append((x0, y0, x0 + w - 1, y1))
            else:
                x += 1
er = doc['empty_rectangle']
er_t = (er['x0'], er['y0'], er['x1'], er['y1'])
er_empty = all(not grid[x][y] for x in range(er['x0'], er['x1'] + 1) for y in range(er['y0'], er['y1'] + 1))
if best is None:
    prob('空矩形', '没有短边至少 6 的空矩形')
elif er_t not in bests:
    prob('空矩形', '声明 %s 不是最大空矩形之一；重算 %s' % (er_t, bests))

# ---------------- 统计 ----------------
mach_cells = sum(len(u['cells']) for u in units.values() if u['cat'] == 'machine')
nontr_cells = sum(len(u['cells']) for u in units.values() if u['cat'] not in TRANSPORT)
tr_cells = sum(len(u['cells']) for u in units.values() if u['cat'] in TRANSPORT)
model_cnt = collections.Counter(u['model'] for u in units.values() if u['cat'] == 'machine')


def fmt_missing():
    out = []
    for (s, t), n in sorted(missing.items()):
        out.append({'源': s, '汇': t, '缺条数': n})
    return out


result = {
    '布局SHA256': SHA,
    '单位': {'制造单位': len(MSET), '机型': dict(model_cnt), '取货口': len(outs), '左': band['L'], '下': band['B'],
           '取货口物品': dict(items_cnt), '供电桩': len(L['power_poles']), '运输单位': dict(tcount),
           '制造单位占格': mach_cells, '非运输占格': nontr_cells, '运输占格': tr_cells,
           '总占格': len(occ), '空格': W * H - len(occ)},
    '协议核心': {'占格': [c['x0'], c['y0'], c['x1'], c['y1']], 'Din': c['Din'],
             '取货端口': {'%d,%d' % k_: v for k_, v in sorted(core_out.items())}},
    '通道': {'重建': len(channels), '声明': len(decl), '一致': decl == rebuilt,
           '前向（在进路上）': len(chan_use), '相邻桥逆向': len(reverse), '多余': len(extra)},
    '进路': {'重建条数': len(routes), '断头链': len(dead), '运输物品格': len(node_use),
           '被共用物品格': sum(1 for v in node_use.values() if len(v) > 1),
           '未在进路上的传送带': belt_unused, 'logical_feeds比对': lf_cmp},
    '接法': {'期望': 325, '已通（按接法计）': sum((exp & real).values()), '缺': sum(missing.values()),
           '接法外': sum(extra_routes.values()), '缺路清单': fmt_missing()},
    '桥接器': {'座数': tcount['bridge'], '相邻对': [list(a) for a in adj_bridge], '逐座': bridge_rows},
    '等长': eq,
    '供电': {'无电制造单位': unpowered, '逐桩覆盖台数': pole_load},
    '边带排布': {'左边未占': band_info['L'], '下边未占': band_info['B'],
             '正对格不是运输单位': [[a, list(b), c_] for a, b, c_ in facing_not_transport]},
    '空矩形': {'重算最优': [list(b) for b in bests], '面积': best[0] if best else None,
            '短边': best[1] if best else None, '声明': list(er_t), '声明格为空': er_empty},
    '已通进路': [{'源': r['src'], '源端口': list(r['src_port']), '汇': r['dst'], '汇端口': list(r['dst_port']),
              '物品': r['item'], '格数': len(r['nodes']),
              '运输格': [[units[n[0]]['x0'], units[n[0]]['y0'], n[1]] for n in r['nodes']]} for r in routes],
    '问题': problems,
}
json.dump(result, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('SHA', SHA)
for k_ in ('单位', '通道', '接法', '等长', '空矩形'):
    v = result[k_]
    if k_ == '接法':
        v = {a: b for a, b in v.items() if a != '缺路清单'}
    print(k_, json.dumps(v, ensure_ascii=False))
print('进路', json.dumps({a: b for a, b in result['进路'].items() if a != '未在进路上的传送带'}, ensure_ascii=False),
      '未用传送带', len(belt_unused))
print('桥接器 座数', tcount['bridge'], '相邻对', adj_bridge)
print('无电', unpowered)
print('边带排布', json.dumps(result['边带排布'], ensure_ascii=False))
print('问题类别', collections.Counter(p['类别'] for p in problems))
for p in problems:
    if p['类别'] not in ('边带排布',):
        print(' ', p['类别'], p['说明'])

#!/usr/bin/env python3
"""核查「独立」第四张全厂候选：编码一（端口列表法）。

从布局文件的单位占格、朝向、设定重建端口与通道，正向追进路，
与第107轮 S2B 第2节接法逐条比对。不使用构造席的程序和逻辑接法 json。
用法：python3 check_main.py 布局.json 输出.json
"""
import json, sys, hashlib, collections

DIRS = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
def opp(s): return (s + 2) % 4

PATH = sys.argv[1]
OUT = sys.argv[2]
raw = open(PATH, 'rb').read()
D = json.loads(raw)
L = D['layout']
problems = []
def prob(cat, msg):
    problems.append({'类别': cat, '说明': msg})

res = {'布局SHA256': hashlib.sha256(raw).hexdigest()}

# ---------- 单位与占格 ----------
SIZE = {'小': (3, 3), '中': (5, 5)}
MODEL_KIND = {'粉碎机': '小', '精炼炉': '小', '配件机': '小', '塑形机': '小',
              '采种机': '中', '种植机': '中', '研磨机': '大', '封装机': '大', '灌装机': '大'}
RECIPES = {  # 配方: (机型, {输入:量}, {输出:量})
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

occ = {}           # (x,y) -> unit id
units = {}         # id -> dict(type=..., ...)
def place(uid, cells, typ):
    if uid in units:
        prob('单位', f'单位编号重复 {uid}')
    for c in cells:
        x, y = c
        if not (0 <= x < 70 and 0 <= y < 70):
            prob('占格', f'{uid} 出界于 {c}')
            continue
        if c in occ:
            prob('占格', f'{uid} 与 {occ[c]} 重叠于 {c}')
        occ[c] = uid

def rect(u):
    return [(x, y) for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)]

def side_cells(b, s):
    """返回某边从 offset 0 起的内侧格列表（E/W 自下而上，N/S 自左而右）。"""
    x0, y0, x1, y1 = b
    if s == 0: return [(x1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1) for x in range(x0, x1 + 1)]
    return [(x, y0) for x in range(x0, x1 + 1)]

ports = []  # dict(unit, side, offset, cell, io in {'in','out','both'}, axis)
def addport(uid, side, off, cell, io, axis=None):
    ports.append(dict(unit=uid, side=side, offset=off, cell=cell, io=io, axis=axis))

# 制造单位
model_count = collections.Counter()
machine_cells = 0
for m in L['machines']:
    uid = m['id']
    b = (m['x0'], m['y0'], m['x1'], m['y1'])
    w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
    kind = MODEL_KIND.get(m['model'])
    if kind is None or kind != m['kind']:
        prob('单位', f'{uid} 机型 {m["model"]} 与类别 {m["kind"]} 不符')
    Din = m['Din']
    if kind in SIZE:
        if (w, h) != SIZE[kind]:
            prob('单位', f'{uid} {m["model"]} 尺寸 {w}x{h} 错')
    else:
        want = (6, 4) if Din in (1, 3) else (4, 6)
        if (w, h) != want:
            prob('单位', f'{uid} 大制造单位 Din={Din} 尺寸 {w}x{h}，应为 {want[0]}x{want[1]}（存取边须为长边）')
    if len(m['recipe_ids']) != 1:
        prob('配方', f'{uid} 配方数 {len(m["recipe_ids"])}')
    for r in m['recipe_ids']:
        if r not in RECIPES or RECIPES[r][0] != m['model']:
            prob('配方', f'{uid} 配方 {r} 不属于 {m["model"]}')
    if m['settings'].get('manufacture_on') is not True:
        prob('开关', f'{uid} 制造开关未开')
    cells = rect(m)
    machine_cells += len(cells)
    place(uid, cells, 'machine')
    units[uid] = dict(type='machine', model=m['model'], recipe=m['recipe_ids'][0], b=b, Din=Din)
    model_count[m['model']] += 1
    for off, c in enumerate(side_cells(b, Din)):
        addport(uid, Din, off, c, 'in')
    for off, c in enumerate(side_cells(b, opp(Din))):
        addport(uid, opp(Din), off, c, 'out')
res['机型台数'] = dict(model_count)
res['制造单位台数'] = len(L['machines'])
res['制造单位占格'] = machine_cells

# 仓库取货口
outlet_side = collections.Counter(); outlet_item = collections.Counter()
for o in L['warehouse_outlets']:
    uid = o['id']
    b = (o['x0'], o['y0'], o['x1'], o['y1'])
    w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
    if o['x0'] == 0 and o['x1'] == 0 and h == 3 and o['Dout'] == 0:
        outlet_side['左'] += 1
        cell = (0, o['y0'] + 1); side = 0
    elif o['y0'] == 0 and o['y1'] == 0 and w == 3 and o['Dout'] == 1:
        outlet_side['下'] += 1
        cell = (o['x0'] + 1, 0); side = 1
    else:
        prob('仓库取货口', f'{uid} 不在左边界或下边界、尺寸或朝向不对：{b} Dout={o["Dout"]}')
        continue
    if o['item'] not in ('源矿', '蓝铁矿'):
        prob('仓库取货口', f'{uid} 物品 {o["item"]}')
    outlet_item[o['item']] += 1
    place(uid, rect(o), 'outlet')
    units[uid] = dict(type='outlet', item=o['item'], b=b)
    addport(uid, side, 1, cell, 'out')
res['仓库取货口'] = {'按边': dict(outlet_side), '按物品': dict(outlet_item), '总数': len(L['warehouse_outlets'])}

# 协议核心
c = L['core']
b = (c['x0'], c['y0'], c['x1'], c['y1'])
if (b[2] - b[0] + 1, b[3] - b[1] + 1) != (9, 9):
    prob('协议核心', '尺寸不是 9x9')
place('CORE', rect(c), 'core')
cin = c['Din']
core_out_items = {}
for s in (cin, opp(cin)):
    for off, cc in enumerate(side_cells(b, s)):
        if 1 <= off <= 7:
            addport('CORE', s, off, cc, 'in')
oi = {(e['side'], e['offset']): e['item'] for e in c['output_items']}
need = {(s, o) for s in ((cin + 1) % 4, (cin + 3) % 4) for o in (1, 4, 7)}
if set(oi) != need or len(c['output_items']) != 6:
    prob('协议核心', f'取货端口设定位置不对：{sorted(oi)}')
for s in ((cin + 1) % 4, (cin + 3) % 4):
    for off, cc in enumerate(side_cells(b, s)):
        if off in (1, 4, 7):
            addport('CORE', s, off, cc, 'out')
            core_out_items[(s, off)] = oi.get((s, off))
units['CORE'] = dict(type='core', b=b, Din=cin, out_items=core_out_items)
res['协议核心'] = {'占格': b, 'Din': cin, '取货端口物品': {f'{s},{o}': v for (s, o), v in sorted(core_out_items.items())}}
if any(v != '源矿' for v in core_out_items.values()):
    prob('协议核心', '六个取货端口不全是源矿')

# 供电桩
poles = []
for p in L['power_poles']:
    b = (p['x0'], p['y0'], p['x1'], p['y1'])
    if (b[2] - b[0] + 1, b[3] - b[1] + 1) != (2, 2):
        prob('供电桩', f'{p["id"]} 尺寸错')
    place(p['id'], rect(p), 'pole')
    units[p['id']] = dict(type='pole', b=b)
    poles.append(b)
unpowered = []
for m in L['machines']:
    ok = False
    for (px0, py0, _, _) in poles:
        # 覆盖格列 px0-5..px0+6，行 py0-5..py0+6
        if m['x0'] <= px0 + 6 and m['x1'] >= px0 - 5 and m['y0'] <= py0 + 6 and m['y1'] >= py0 - 5:
            ok = True; break
    if not ok:
        unpowered.append(m['id'])
if unpowered:
    prob('供电', f'无供电的制造单位：{unpowered}')
res['供电桩数'] = len(poles)
res['无供电制造单位'] = unpowered

if L.get('storage_boxes'):
    prob('禁用单位', f'有协议储存箱 {len(L["storage_boxes"])} 个')
if L.get('vin') or L.get('vout'):
    prob('禁用单位', 'vin/vout 非空')

# 运输单位
tcount = collections.Counter()
bridge_decl = {}
for t in L['transport']:
    uid = t['id']; cell = (t['x'], t['y'])
    tcount[t['type']] += 1
    place(uid, [cell], 'transport')
    if t['type'] == 'belt':
        if t['in_side'] == t['out_side']:
            prob('运输', f'{uid} 存取同边')
        units[uid] = dict(type='belt', cell=cell, ins=t['in_side'], outs=t['out_side'])
        addport(uid, t['in_side'], 0, cell, 'in')
        addport(uid, t['out_side'], 0, cell, 'out')
    elif t['type'] == 'bridge':
        units[uid] = dict(type='bridge', cell=cell)
        bridge_decl[uid] = (t.get('H_in'), t.get('V_in'))
        for s in range(4):
            addport(uid, s, 0, cell, 'both', axis=('H' if s in (0, 2) else 'V'))
    else:
        prob('禁用单位', f'{uid} 类型 {t["type"]}（不许用分流器、汇流器、物品准入口）')
        units[uid] = dict(type=t['type'], cell=cell)
res['运输单位'] = dict(tcount)
TRANS = {'belt', 'bridge'}
res['占格总数'] = len(occ)
res['非运输占格'] = sum(1 for v in occ.values() if units.get(v, {}).get('type') not in TRANS)

# ---------- 通道重建 ----------
port_at = {}  # (cell, side) -> port
for p in ports:
    key = (p['cell'], p['side'])
    if key in port_at:
        prob('端口', f'同一格同一边两个端口 {key}')
    port_at[key] = p

def node_of(p):
    """端口所属物品格节点。"""
    u = units[p['unit']]
    if u['type'] == 'bridge':
        return (p['unit'], p['axis'])
    if u['type'] == 'belt':
        return (p['unit'], '')
    return (p['unit'], 'port', p['side'], p['offset'])

channels = []  # (from_port, to_port)
for p in ports:
    if p['io'] not in ('out', 'both'):
        continue
    dx, dy = DIRS[p['side']]
    nc = (p['cell'][0] + dx, p['cell'][1] + dy)
    q = port_at.get((nc, opp(p['side'])))
    if q is None or q['unit'] == p['unit']:
        continue
    if q['io'] not in ('in', 'both'):
        continue
    tu, tq = units[p['unit']]['type'], units[q['unit']]['type']
    if tu not in TRANS and tq not in TRANS:
        continue  # 非运输单位之间贴靠不形成通道
    channels.append((p, q))

def pkey(p):
    return (p['unit'], p['side'], p['offset'])
chan_keys = {(pkey(a), pkey(b)) for a, b in channels}
res['重建通道数'] = len(channels)

# 与声明比对
decl = {}
for ch in D['design']['physical_channels']:
    k = ((ch['from']['unit'], ch['from']['side'], ch['from']['offset']),
         (ch['to']['unit'], ch['to']['side'], ch['to']['offset']))
    decl[k] = ch['id']
missing_decl = chan_keys - set(decl)
extra_decl = set(decl) - chan_keys
res['声明通道数'] = len(decl)
res['声明比对'] = {'重建有声明无': len(missing_decl), '声明有重建无': len(extra_decl)}
if missing_decl or extra_decl:
    prob('通道声明', f'声明与重建不一致：缺 {sorted(missing_decl)[:10]}，多 {sorted(extra_decl)[:10]}')

# ---------- 进路追踪 ----------
out_of = collections.defaultdict(list)  # node -> [(side_of_exit, chan)]
in_of = collections.defaultdict(list)
for a, b in channels:
    out_of[node_of(a)].append((a, b))
    in_of[node_of(b)].append((a, b))

def product_of(uid, p):
    u = units[uid]
    if u['type'] == 'outlet': return u['item']
    if u['type'] == 'core': return u['out_items'][(p['side'], p['offset'])]
    if u['type'] == 'machine':
        outs = RECIPES[u['recipe']][2]
        return next(iter(outs))
    return None

routes = []
forward = set()
visited_nodes = collections.Counter()
for a, b in channels:
    if units[a['unit']]['type'] in TRANS:
        continue
    # 从非运输单位取货端口出发
    src = a; path = [(a, b)]; cells = []; phys = []
    cur_in = b
    status = None
    seen_phys = set()
    while True:
        u = units[cur_in['unit']]
        if u['type'] not in TRANS:
            status = 'ok'; dst = cur_in; break
        nd = node_of(cur_in)
        cells.append(nd)
        if cur_in['unit'] in seen_phys:
            status = f'重复经过物理单位 {cur_in["unit"]}'; break
        seen_phys.add(cur_in['unit']); phys.append(cur_in['unit'])
        if u['type'] == 'belt':
            if cur_in['side'] != u['ins']:
                status = f'从非存货边进入传送带 {cur_in["unit"]}'; break
            exit_side = u['outs']
        else:
            exit_side = opp(cur_in['side'])
        nxt = [(x, y) for (x, y) in out_of[nd] if x['side'] == exit_side]
        if not nxt:
            status = f'断头于 {cur_in["unit"]} 出边 {exit_side}'; dst = None; break
        if len(nxt) > 1:
            status = '出口多条'; break
        path.append(nxt[0]); cur_in = nxt[0][1]
    for x in cells: visited_nodes[x] += 1
    r = dict(src=pkey(src), dst=(pkey(dst) if status == 'ok' else None), status=status,
             cells=cells, phys=phys, nchan=len(path), chans=[(pkey(x), pkey(y)) for x, y in path],
             item=product_of(src['unit'], src))
    routes.append(r)
    for x, y in path: forward.add((pkey(x), pkey(y)))

ok_routes = [r for r in routes if r['status'] == 'ok']
bad_routes = [r for r in routes if r['status'] != 'ok']
res['从非运输单位出发的进路'] = len(routes)
res['到达非运输单位存货端口的进路'] = len(ok_routes)
res['不完整进路'] = [{'起点': r['src'], '状态': r['status'], '格数': len(r['cells'])} for r in bad_routes]
for r in bad_routes:
    prob('进路', f'进路 {r["src"]} {r["status"]}')

shared = [n for n, k in visited_nodes.items() if k > 1]
if shared:
    prob('进路', f'运输物品格被多条进路共用：{shared[:10]}')
res['被多路共用的物品格'] = [list(map(str, s)) for s in shared]

# 所有运输物品格是否都在进路上
all_nodes = []
for uid, u in units.items():
    if u['type'] == 'belt': all_nodes.append((uid, ''))
    if u['type'] == 'bridge': all_nodes += [(uid, 'H'), (uid, 'V')]
belt_orphans = [n for n in all_nodes if n[1] == '' and n not in visited_nodes]
if belt_orphans:
    prob('进路', f'不在任何进路上的传送带：{belt_orphans[:20]}')
res['不在进路上的传送带'] = [n[0] for n in belt_orphans]

# 桥接器轴用法
bridge_use = {}
node_route = {}
for i, r in enumerate(routes):
    for n in r['cells']: node_route[n] = i
bad_bridge = []
reverse_ok = set()
for uid, u in units.items():
    if u['type'] != 'bridge': continue
    used = {ax: node_route.get((uid, ax)) for ax in 'HV'}
    bridge_use[uid] = used
    if used['H'] is None and used['V'] is None:
        bad_bridge.append((uid, '两轴都不在进路上'))
    if used['H'] is not None and used['H'] == used['V']:
        bad_bridge.append((uid, '同一进路经过两轴'))
    for ax in 'HV':
        if used[ax] is None:
            if out_of[(uid, ax)] or in_of[(uid, ax)]:
                bad_bridge.append((uid, f'未用的 {ax} 轴有通道'))
for b in bad_bridge:
    prob('桥接器', f'{b[0]} {b[1]}')
res['桥接器两轴用法问题'] = bad_bridge
res['桥接器两轴都用'] = sum(1 for v in bridge_use.values() if v['H'] is not None and v['V'] is not None)
res['桥接器只用一轴'] = sum(1 for v in bridge_use.values() if (v['H'] is None) != (v['V'] is None))

# 桥方向声明与推导比对（只作记录）
decl_mismatch = []
for uid, (hin, vin) in bridge_decl.items():
    for ax, dv in (('H', hin), ('V', vin)):
        n = (uid, ax)
        derived = None
        if node_route.get(n) is not None:
            # 找本轴前向进入的那条通道的边
            for x, y in in_of[n]:
                if (pkey(x), pkey(y)) in forward:
                    derived = y['side']
        if derived != dv:
            decl_mismatch.append((uid, ax, dv, derived))
res['桥方向声明与推导不符'] = decl_mismatch

# 多余通道：不在前向集合中，且不是同一进路同轴相邻桥的逆向通道
extra = []
rev = []
for a, b in channels:
    k = (pkey(a), pkey(b))
    if k in forward: continue
    ua, ub = units[a['unit']], units[b['unit']]
    if ua['type'] == 'bridge' and ub['type'] == 'bridge' and a['axis'] == b['axis'] \
            and (pkey(b), pkey(a)) in forward:
        rev.append(k); continue
    extra.append(k)
res['前向通道数'] = len(forward)
res['相邻桥逆向通道数'] = len(rev)
res['多余通道'] = [list(map(list, e)) for e in extra]
for e in extra:
    prob('多余通道', f'{e[0]} -> {e[1]}')
decl_rev = set()
idmap = {v: k for k, v in decl.items()}
for cid in D['design'].get('bridge_reverse_channels', []):
    decl_rev.add(idmap.get(cid))
if decl_rev != set(rev):
    prob('通道声明', f'逆向通道声明 {len(decl_rev)} 与重建 {len(rev)} 不一致')

# 相邻桥最长同轴直串
def chain_len(uid, ax):
    x, y = units[uid]['cell']
    dx, dy = (1, 0) if ax == 'H' else (0, 1)
    n = 1
    xx, yy = x + dx, y + dy
    while occ.get((xx, yy)) and units[occ[(xx, yy)]]['type'] == 'bridge':
        n += 1; xx += dx; yy += dy
    return n
mx = 0
for uid, u in units.items():
    if u['type'] == 'bridge':
        for ax in 'HV':
            mx = max(mx, chain_len(uid, ax))
res['最长相邻桥直串'] = mx

# ---------- 逻辑接法（S2B 第2节）----------
req = collections.Counter()   # (src, dst) -> 条数；src 'OUTLET:蓝铁矿' / 'OUTLET:源矿' / 'COREPORT'
def add(s, t, n=1): req[(s, t)] += n
for i in range(1, 35):
    add('OUTLET:蓝铁矿', f'T{i}'); add(f'T{i}', f'KB{i}')
for i in range(1, 18):
    add(f'KB{2*i-1}', f'B{i}'); add(f'KB{2*i}', f'B{i}')
for j in range(1, 19):
    add('COREPORT' if j <= 6 else 'OUTLET:源矿', f'U{j}')
for i in range(1, 10):
    add(f'U{2*i-1}', f'O{i}'); add(f'U{2*i}', f'O{i}')
for i in range(1, 18): add(f'B{i}', f'R{i}')
for i in range(1, 7): add(f'R{i}', f'P{i}')
for k, h in zip(range(7, 17, 2), range(1, 6)):
    add(f'R{k}', f'H{h}'); add(f'R{k+1}', f'H{h}')
add('R17', 'H6')
for i in range(1, 4):
    add(f'P{2*i-1}', f'E{i}'); add(f'P{2*i}', f'E{i}')
    for o in (3*i-2, 3*i-1, 3*i): add(f'O{o}', f'E{i}')
for f, hs, qs in ((1, (1, 2), (1, 2)), (2, (3, 4), (3, 4)), (3, (5,), (5,)), (4, (6,), (6,))):
    for h in hs: add(f'H{h}', f'F{f}')
    for q in qs: add(f'Q{q}', f'F{f}')
for e in ('E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4'): add(e, 'CORE')
for i in range(1, 14):
    add(f'SC{i}', f'SA{i}'); add(f'SC{i}', f'SB{i}'); add(f'SA{i}', f'SC{i}'); add(f'SB{i}', f'S{i}')
for i in range(1, 7):
    add(f'QC{i}', f'QA{i}'); add(f'QC{i}', f'QB{i}'); add(f'QA{i}', f'QC{i}'); add(f'QB{i}', f'KQ{i}')
sand = {1: ['B1', 'B2', 'O1'], 2: ['O2', 'O3'], 3: ['B3', 'B4', 'O4'], 4: ['O5', 'O6'], 5: ['B5', 'B6', 'O7'],
        6: ['O8', 'O9'], 7: ['B7', 'B8', 'B9'], 8: ['B10', 'Q1', 'Q2'], 9: ['B11', 'B12', 'B13'],
        10: ['B14', 'Q3', 'Q4'], 11: ['B15', 'B16', 'Q5'], 12: ['B17'], 13: ['Q6']}
for s, ts in sand.items():
    for t in ts: add(f'S{s}', t)
for i in range(1, 6): add(f'KQ{i}', f'Q{i}', 2)
add('KQ6', 'Q6')
res['S2B要求进路总数'] = sum(req.values())
assert sum(req.values()) == 325

# 身份与配方
ROLE = {}
for i in range(1, 35): ROLE[f'T{i}'] = '精炼-蓝铁矿'; ROLE[f'KB{i}'] = '粉碎-蓝铁块'
for i in range(1, 19): ROLE[f'U{i}'] = '粉碎-源矿'
for i in range(1, 18): ROLE[f'B{i}'] = '研磨-致密蓝铁'; ROLE[f'R{i}'] = '精炼-致密蓝铁'
for i in range(1, 10): ROLE[f'O{i}'] = '研磨-致密源石'
for i in range(1, 7): ROLE[f'Q{i}'] = '研磨-细磨荞花'; ROLE[f'P{i}'] = '配件-钢制零件'; ROLE[f'H{i}'] = '塑形-钢质瓶'
for i in range(1, 4): ROLE[f'E{i}'] = '封装-电池'
for i in range(1, 5): ROLE[f'F{i}'] = '灌装-胶囊'
for i in range(1, 14):
    ROLE[f'SC{i}'] = '采种-砂叶'; ROLE[f'SA{i}'] = '种植-砂叶'; ROLE[f'SB{i}'] = '种植-砂叶'; ROLE[f'S{i}'] = '粉碎-砂叶'
for i in range(1, 7):
    ROLE[f'QC{i}'] = '采种-荞花'; ROLE[f'QA{i}'] = '种植-荞花'; ROLE[f'QB{i}'] = '种植-荞花'; ROLE[f'KQ{i}'] = '粉碎-荞花'
mids = {m['id'] for m in L['machines']}
if mids != set(ROLE):
    prob('接法', f'机器编号集合与 S2B 身份不一致：多 {sorted(mids - set(ROLE))}，少 {sorted(set(ROLE) - mids)}')
for uid in mids & set(ROLE):
    if units[uid]['recipe'] != ROLE[uid]:
        prob('接法', f'{uid} 配方 {units[uid]["recipe"]}，S2B 身份应为 {ROLE[uid]}')

def src_label(pk):
    uid = pk[0]
    u = units[uid]
    if u['type'] == 'outlet': return f'OUTLET:{u["item"]}'
    if u['type'] == 'core': return 'COREPORT'
    return uid

got = collections.Counter()
route_list = []
for r in ok_routes:
    s = src_label(r['src']); t = r['dst'][0]
    got[(s, t)] += 1
    # 物品合法性
    tu = units[t]
    if tu['type'] == 'machine':
        if r['item'] not in RECIPES[tu['recipe']][1]:
            prob('物品', f'进路 {r["src"]}->{r["dst"]} 送 {r["item"]}，终点配方不收')
    elif tu['type'] == 'core':
        if r['item'] not in ('高容谷地电池', '精选荞愈胶囊'):
            prob('物品', f'进路 {r["src"]}->CORE 送 {r["item"]}')
    route_list.append(dict(起点=list(r['src']), 终点=list(r['dst']), 起点身份=s, 终点身份=t, 物品=r['item'],
                           运输物品格数=len(r['cells']), 格=[f'{a}{":"+b if b else ""}' for a, b, *_ in r['cells']]))
over = {k: (got[k], req.get(k, 0)) for k in got if got[k] > req.get(k, 0)}
miss = {k: (got.get(k, 0), req[k]) for k in req if got.get(k, 0) < req[k]}
res['已接进路数'] = sum(got.values())
res['接法外或超额进路'] = {f'{a}->{b}': v for (a, b), v in over.items()}
res['缺路'] = {f'{a}->{b}': req[(a, b)] - got.get((a, b), 0) for (a, b) in miss}
res['缺路条数'] = sum(req[k] - got.get(k, 0) for k in miss)
for (a, b), v in over.items():
    prob('接法', f'接法外或超额进路 {a}->{b}：实有 {v[0]}，应有 {v[1]}')
if miss:
    prob('接法', f'缺 {res["缺路条数"]} 条进路（325 条只接通 {sum(got.values())} 条）')

# 缺路分类
cat = collections.Counter()
def catname(s, t):
    if s.startswith('OUTLET') or s == 'COREPORT': return '矿石进路'
    if t == 'CORE': return '成品入库'
    if s[0] in 'S' and s[:2] in ('SC', 'SA', 'SB') or s[:2] in ('QC', 'QA', 'QB'): return '采种单元内部'
    if s.startswith('S') or s.startswith('KQ'): return '植物粉末'
    return '其他中间物'
for (a, b) in miss:
    cat[catname(a, b)] += req[(a, b)] - got.get((a, b), 0)
res['缺路分类'] = dict(cat)
ore_req = sum(v for (a, b), v in req.items() if a.startswith('OUTLET') or a == 'COREPORT')
ore_got = sum(v for (a, b), v in got.items() if a.startswith('OUTLET') or a == 'COREPORT')
prod_got = sum(v for (a, b), v in got.items() if b == 'CORE')
res['矿石进路接通'] = f'{ore_got}/{ore_req}'
res['成品入库接通'] = f'{prod_got}/7'
res['核心取货端口接通'] = sum(v for (a, b), v in got.items() if a == 'COREPORT')

# 来源端口不重复（每个仓库取货口、核心端口至多一路）
srcports = collections.Counter(r['src'] for r in ok_routes)
dup = [k for k, v in srcports.items() if v > 1]
if dup: prob('接法', f'同一取货端口出多路 {dup}')
dstports = collections.Counter(r['dst'] for r in ok_routes)
dupd = [k for k, v in dstports.items() if v > 1]
if dupd: prob('接法', f'同一存货端口进多路 {dupd}')

# H6->F4 与 Q6->F4
def rlen(s, t):
    return [len(r['cells']) for r in ok_routes if r['src'][0] == s and r['dst'][0] == t]
res['H6->F4格数'] = rlen('H6', 'F4')
res['Q6->F4格数'] = rlen('Q6', 'F4')
if res['H6->F4格数'] != res['Q6->F4格数'] or not res['H6->F4格数']:
    prob('等长', f'H6->F4 {res["H6->F4格数"]}，Q6->F4 {res["Q6->F4格数"]}，不等长或缺路')

# logical_feeds 比对
lf = D['design'].get('logical_feeds', [])
lf_set = collections.Counter()
for f in lf:
    lf_set[((f['from']['unit'], f['from']['side'], f['from']['offset']),
            (f['to']['unit'], f['to']['side'], f['to']['offset']), len(f['path']))] += 1
my_set = collections.Counter((r['src'], r['dst'], r['nchan']) for r in ok_routes)
res['logical_feeds条数'] = len(lf)
res['logical_feeds与重建一致'] = (lf_set == my_set)
if lf_set != my_set:
    prob('进路声明', f'logical_feeds 与重建进路不一致：只在声明 {list((lf_set - my_set).items())[:5]}，只在重建 {list((my_set - lf_set).items())[:5]}')
# 声明路径逐通道核对
cid2k = {v: k for k, v in decl.items()}
pathbad = 0
myroute_by = {(r['src'], r['dst']): r for r in ok_routes}
for f in lf:
    k = ((f['from']['unit'], f['from']['side'], f['from']['offset']), (f['to']['unit'], f['to']['side'], f['to']['offset']))
    r = myroute_by.get(k)
    if r is None or [cid2k.get(c) for c in f['path']] != r['chans']:
        pathbad += 1
res['logical_feeds路径逐通道不符'] = pathbad
if pathbad: prob('进路声明', f'{pathbad} 条 logical_feeds 的通道序列与重建不符')

# ---------- 空矩形 ----------
grid = [[False] * 70 for _ in range(70)]  # grid[x][y] occupied
for (x, y) in occ: grid[x][y] = True
best = None; allbest = []
for x0 in range(70):
    colfree = [True] * 70
    for x1 in range(x0, 70):
        for y in range(70):
            if grid[x1][y]: colfree[y] = False
        w = x1 - x0 + 1
        y = 0
        while y < 70:
            if colfree[y]:
                y0 = y
                while y < 70 and colfree[y]: y += 1
                h = y - y0
                s = min(w, h)
                if s >= 6:
                    # 在这一列区间内，最大高度 h 的竖直段（取全段）
                    key = (w * h, s)
                    if best is None or key > best[0]:
                        best = (key, (x0, y0, x1, y - 1)); allbest = [(x0, y0, x1, y - 1)]
                    elif key == best[0]:
                        allbest.append((x0, y0, x1, y - 1))
            else:
                y += 1
# 只保留水平方向也极大的
def maximal(r):
    x0, y0, x1, y1 = r
    left = x0 > 0 and all(not grid[x0 - 1][y] for y in range(y0, y1 + 1))
    right = x1 < 69 and all(not grid[x1 + 1][y] for y in range(y0, y1 + 1))
    return not left and not right
allbest = sorted(set(r for r in allbest if maximal(r)))
res['最大空矩形'] = {'面积': best[0][0], '短边': best[0][1], '位置(x0,y0,x1,y1)': allbest} if best else None
er = D['empty_rectangle']
decl_r = (er['x0'], er['y0'], er['x1'], er['y1'])
res['声明空矩形'] = decl_r
inside_occ = [(x, y) for x in range(er['x0'], er['x1'] + 1) for y in range(er['y0'], er['y1'] + 1) if grid[x][y]]
if inside_occ: prob('空矩形', f'声明矩形内有占格 {inside_occ[:5]}')
if best and decl_r not in allbest:
    prob('空矩形', f'声明 {decl_r} 不是最优之一 {allbest}')

# 最大空矩形（不限短边）作参考
res['问题'] = problems
res['问题条数'] = len(problems)
json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1, default=str)
json.dump(route_list, open(OUT.replace('.json', '-进路.json'), 'w'), ensure_ascii=False, indent=0)
for k, v in res.items():
    if k in ('问题', '多余通道', '不完整进路', '缺路', '桥方向声明与推导不符'):
        continue
    print(k, ':', v)
print('多余通道', len(extra), extra[:10])
print('不完整进路', len(bad_routes))
print('缺路条目', len(miss))
print('桥方向声明与推导不符', len(decl_mismatch), decl_mismatch[:10])
print('问题', len(problems))
for p in problems: print(' -', p['类别'], p['说明'][:300])

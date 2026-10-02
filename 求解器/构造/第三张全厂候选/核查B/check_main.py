#!/usr/bin/env python3
"""核查B 主检查程序（编码一）。

只读构造 B 的候选布局文件，从单位占格与朝向重建端口、通道、进路，
不调用构造席的任何代码。规则依据：第107-109轮前提快照 + 临时规则。

输出：核查B/结果-主.json
"""
import json, hashlib, sys, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
LAYOUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '构造B', '候选布局.json')
OUTNAME = sys.argv[2] if len(sys.argv) > 2 else '结果-主.json'
SNAP = os.path.join(ROOT, '求解器', '候选约束轮次', '第107-109轮', '前提快照')
TMPRULE = os.path.join(ROOT, '求解器', '候选约束轮次', '第107-109轮', '临时规则.md')

W = H = 70
DELTA = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
def opp(s): return (s + 2) % 4

problems = []   # (类别, 文字)
def prob(cat, msg):
    problems.append({'类别': cat, '说明': msg})

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

raw = open(LAYOUT, 'rb').read()
cand_sha = hashlib.sha256(raw).hexdigest()
d = json.loads(raw)
Lay = d['layout']; Des = d['design']

# ---------- 指纹 ----------
fp = {
    'rules': sha(os.path.join(SNAP, '《明日方舟：终末地》游戏规则.txt')),
    'task': sha(os.path.join(SNAP, '求解任务.txt')),
    'constraints': sha(os.path.join(SNAP, '求解约束.txt')),
}
fp_ok = {k: d['source_fingerprints'].get(k) == v for k, v in fp.items()}
tmp_ok = any(p['sha256'] == sha(TMPRULE) for p in d.get('provenance', []))

# ---------- 配方目录（据规则配方段） ----------
RECIPES = {
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
SIZE = {'粉碎机': '小', '精炼炉': '小', '配件机': '小', '塑形机': '小',
        '采种机': '中', '种植机': '中', '研磨机': '大', '封装机': '大', '灌装机': '大'}

# ---------- 单位与占格 ----------
occ = {}           # (x,y) -> unit id
units = {}         # id -> dict(kind=..., cells=[...])
ports = collections.defaultdict(list)  # (x,y,side) -> list of (uid, io, axis)
# io: 'in' 存货端口, 'out' 取货端口, 'both' 桥接器

def place(uid, cells, kind):
    if uid in units:
        prob('规则-单位', f'单位 id 重复：{uid}')
    units[uid] = {'kind': kind, 'cells': cells}
    for c in cells:
        x, y = c
        if not (0 <= x < W and 0 <= y < H):
            prob('规则-占格', f'{uid} 占格 {c} 出界')
            continue
        if c in occ:
            prob('规则-占格', f'{uid} 与 {occ[c]} 重叠于 {c}')
        occ[c] = uid

def rect_cells(x0, y0, x1, y1):
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

def side_cells(x0, y0, x1, y1, s):
    """该边的端口内侧格，offset 0 起：E/W 自下向上，N/S 自左向右。"""
    if s == 0: return [(x1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1) for x in range(x0, x1 + 1)]
    if s == 3: return [(x, y0) for x in range(x0, x1 + 1)]

machine = {}
for m in Lay['machines']:
    uid = m['id']; machine[uid] = m
    x0, y0, x1, y1, Din = m['x0'], m['y0'], m['x1'], m['y1'], m['Din']
    w, h = x1 - x0 + 1, y1 - y0 + 1
    model = m['model']
    if SIZE.get(model) != m['kind']:
        prob('规则-单位', f'{uid} 机型 {model} 与尺寸类别 {m["kind"]} 不符')
    if m['kind'] == '小' and (w, h) != (3, 3): prob('规则-单位', f'{uid} 小制造单位尺寸 {w}x{h}')
    if m['kind'] == '中' and (w, h) != (5, 5): prob('规则-单位', f'{uid} 中制造单位尺寸 {w}x{h}')
    if m['kind'] == '大':
        exp = (6, 4) if Din in (1, 3) else (4, 6)
        if (w, h) != exp: prob('规则-单位', f'{uid} 大制造单位 Din={Din} 尺寸 {w}x{h}，应为 {exp}（存取边须为长边）')
    for r in m['recipe_ids']:
        if r not in RECIPES or RECIPES[r][0] != model:
            prob('规则-配方', f'{uid} 配方 {r} 不属于 {model}')
    if not m['settings'].get('manufacture_on', False):
        prob('S2-开关', f'{uid} 制造开关关闭')
    place(uid, rect_cells(x0, y0, x1, y1), 'machine')
    for c in side_cells(x0, y0, x1, y1, Din):
        ports[(c[0], c[1], Din)].append((uid, 'in', None))
    for c in side_cells(x0, y0, x1, y1, opp(Din)):
        ports[(c[0], c[1], opp(Din))].append((uid, 'out', None))

outlet = {}
for o in Lay['warehouse_outlets']:
    uid = o['id']; outlet[uid] = o
    x0, y0, x1, y1, Dout = o['x0'], o['y0'], o['x1'], o['y1'], o['Dout']
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if Dout == 0:
        if not (x0 == 0 and x1 == 0 and h == 3):
            prob('规则-仓库取货口', f'{uid} 声明贴左边界但占格 x{x0}-{x1} 高 {h}')
        pc = (0, y0 + 1)
    elif Dout == 1:
        if not (y0 == 0 and y1 == 0 and w == 3):
            prob('规则-仓库取货口', f'{uid} 声明贴下边界但占格 y{y0}-{y1} 宽 {w}')
        pc = (x0 + 1, 0)
    else:
        prob('规则-仓库取货口', f'{uid} Dout={Dout}，取货口只能在左边界或下边界（求解任务第15行）')
        pc = None
    if o['item'] not in ('源矿', '蓝铁矿'):
        prob('约束-取货口配置', f'{uid} 物品 {o["item"]}')
    place(uid, rect_cells(x0, y0, x1, y1), 'outlet')
    if pc:
        ports[(pc[0], pc[1], Dout)].append((uid, 'out', None))

core = Lay['core']
cx0, cy0, cx1, cy1, cDin = core['x0'], core['y0'], core['x1'], core['y1'], core['Din']
if (cx1 - cx0 + 1, cy1 - cy0 + 1) != (9, 9):
    prob('规则-协议核心', f'协议核心尺寸 {cx1-cx0+1}x{cy1-cy0+1}')
place('CORE', rect_cells(cx0, cy0, cx1, cy1), 'core')
core_out = {}
for s in (cDin, opp(cDin)):
    cells = side_cells(cx0, cy0, cx1, cy1, s)
    for off in range(1, 8):
        ports[(cells[off][0], cells[off][1], s)].append(('CORE', 'in', None))
oitems = {(oi['side'], oi['offset']): oi['item'] for oi in core['output_items']}
for s in ((cDin + 1) % 4, (cDin + 3) % 4):
    cells = side_cells(cx0, cy0, cx1, cy1, s)
    for off in (1, 4, 7):
        if (s, off) not in oitems:
            prob('规则-协议核心', f'核心取货端口 side{s} offset{off} 未设物品')
        core_out[(cells[off][0], cells[off][1], s)] = oitems.get((s, off))
        ports[(cells[off][0], cells[off][1], s)].append(('CORE', 'out', None))
if len(core['output_items']) != 6 or set(oitems) != set(((cDin + 1) % 4, o) for o in (1, 4, 7)) | set(((cDin + 3) % 4, o) for o in (1, 4, 7)):
    prob('规则-协议核心', f'核心 output_items 与取货边不符：{core["output_items"]}')

poles = []
for p in Lay['power_poles']:
    if (p['x1'] - p['x0'] + 1, p['y1'] - p['y0'] + 1) != (2, 2):
        prob('规则-供电桩', f'{p["id"]} 尺寸不是 2x2')
    place(p['id'], rect_cells(p['x0'], p['y0'], p['x1'], p['y1']), 'pole')
    poles.append(p)

if Lay.get('storage_boxes'):
    prob('S2-运输限制', '出现协议储存箱')

transport = {}
for t in Lay['transport']:
    uid = t['id']; transport[uid] = t
    x, y = t['x'], t['y']
    place(uid, [(x, y)], t['type'])
    if t['type'] == 'belt':
        if t['in_side'] == t['out_side']:
            prob('规则-传送带', f'{uid} 存取同边')
        ports[(x, y, t['in_side'])].append((uid, 'in', None))
        ports[(x, y, t['out_side'])].append((uid, 'out', None))
    elif t['type'] == 'bridge':
        for s in range(4):
            ports[(x, y, s)].append((uid, 'both', 'H' if s in (0, 2) else 'V'))
    else:
        prob('S2-运输限制', f'{uid} 类型 {t["type"]}（S2B 只允许传送带与桥接器）')

TRANSPORT_KINDS = ('belt', 'bridge')
def is_tr(uid): return units[uid]['kind'] in TRANSPORT_KINDS

# ---------- 占格统计 ----------
n_occ = len(occ)
machine_cells = sum(len(units[u]['cells']) for u in machine)

# ---------- 通道重建 ----------
# 节点：运输物品格 = (uid, axis)；带子 axis='B'；非运输端口 = (uid, x, y, side)
def node_of(uid, x, y, side):
    k = units[uid]['kind']
    if k == 'belt': return (uid, 'B')
    if k == 'bridge': return (uid, 'H' if side in (0, 2) else 'V')
    return (uid, x, y, side)

channels = set()   # (from_node, from_side_at_from, to_node, to_side) 用端口坐标表示
chan_list = []
for (x, y, s), plist in list(ports.items()):
    for (uid, io, ax) in plist:
        if not is_tr(uid):
            continue
        dx, dy = DELTA[s]
        nx, ny = x + dx, y + dy
        for (vid, vio, vax) in ports.get((nx, ny, opp(s)), []):
            if vid == uid:
                continue
            # 至少一端是运输单位（uid 已是）
            # uid 出 -> vid 入
            if io in ('out', 'both') and vio in ('in', 'both'):
                channels.add(((uid, x, y, s), (vid, nx, ny, opp(s))))
            if io in ('in', 'both') and vio in ('out', 'both'):
                channels.add(((vid, nx, ny, opp(s)), (uid, x, y, s)))
channels = sorted(channels)

# ---------- 与声明的通道比对 ----------
def portref_cell(pr):
    uid, s, off = pr['unit'], pr['side'], pr['offset']
    u = units.get(uid)
    if u is None:
        return None
    k = u['kind']
    if k in TRANSPORT_KINDS:
        t = transport[uid]
        return (uid, t['x'], t['y'], s)
    if k == 'machine':
        m = machine[uid]; cells = side_cells(m['x0'], m['y0'], m['x1'], m['y1'], s)
    elif k == 'outlet':
        o = outlet[uid]; cells = side_cells(o['x0'], o['y0'], o['x1'], o['y1'], s)
    elif k == 'core':
        cells = side_cells(cx0, cy0, cx1, cy1, s)
    else:
        return None
    if off >= len(cells): return None
    return (uid, cells[off][0], cells[off][1], s)

declared = {}
for pc in Des['physical_channels']:
    a = portref_cell(pc['from']); b = portref_cell(pc['to'])
    declared[(a, b)] = pc['id']
chanset = set(channels)
decl_set = set(declared)
missing_decl = sorted(chanset - decl_set)
extra_decl = sorted(decl_set - chanset)
if missing_decl: prob('声明-通道', f'{len(missing_decl)} 条实际形成的通道未在 physical_channels 中声明：{missing_decl[:10]}')
if extra_decl: prob('声明-通道', f'{len(extra_decl)} 条声明通道不能由占格重建：{extra_decl[:10]}')

# ---------- 物品格图与进路追踪 ----------
# out_edges[node_key] = list of (channel, to_node_key, entry_side_at_to)
out_from = collections.defaultdict(list)
in_to = collections.defaultdict(list)
for ch in channels:
    (fu, fx, fy, fs), (tu, tx, ty, ts) = ch
    out_from[node_of(fu, fx, fy, fs)].append(ch)
    in_to[node_of(tu, tx, ty, ts)].append(ch)

def tr_exit_channels(uid, entry_side):
    """物品从 entry_side 进入运输单位 uid 后，前向可走的出通道。"""
    t = transport[uid]
    if t['type'] == 'belt':
        s_out = t['out_side']
    else:
        s_out = opp(entry_side)
    res = []
    for ch in channels:
        pass
    key = (uid, 'B') if t['type'] == 'belt' else (uid, 'H' if s_out in (0, 2) else 'V')
    return [ch for ch in out_from[key] if ch[0][3] == s_out]

routes = []
used_forward = set()
for ch in channels:
    (fu, fx, fy, fs), (tu, tx, ty, ts) = ch
    if is_tr(fu) or not is_tr(tu):
        continue
    # 起点：非运输单位取货端口 -> 运输单位
    path = [ch]; cells = []; phys = []
    cur, entry = tu, ts
    status = None
    while True:
        t = transport[cur]
        ax = 'B' if t['type'] == 'belt' else ('H' if entry in (0, 2) else 'V')
        cells.append((cur, ax)); phys.append(cur)
        nxt = tr_exit_channels(cur, entry)
        if len(nxt) == 0:
            status = '断头'; break
        if len(nxt) > 1:
            status = '分叉'; break
        c2 = nxt[0]; path.append(c2)
        (_, _, _, _), (nu, nx_, ny_, ns) = c2
        if not is_tr(nu):
            status = '到达'; break
        if (nu, 'B' if transport[nu]['type'] == 'belt' else ('H' if ns in (0, 2) else 'V')) in cells:
            status = '成环'; break
        cur, entry = nu, ns
    for c in path: used_forward.add(c)
    end = path[-1][1]
    routes.append({'from': ch[0], 'to': end if status == '到达' else None, 'status': status,
                   'path': path, 'cells': cells, 'phys': phys})

# 运输段内是否有不从非运输单位开始的链（孤立运输段）
tr_nodes_in_routes = collections.Counter(c for r in routes for c in r['cells'])
all_tr_nodes = set()
for uid, t in transport.items():
    if t['type'] == 'belt': all_tr_nodes.add((uid, 'B'))
    else:
        for ax in 'HV':
            # 只把有通道的轴算作在用物品格
            if out_from.get((uid, ax)) or in_to.get((uid, ax)):
                all_tr_nodes.add((uid, ax))
orphan_nodes = sorted(all_tr_nodes - set(tr_nodes_in_routes))
shared_nodes = sorted(k for k, v in tr_nodes_in_routes.items() if v > 1)
if orphan_nodes: prob('S2-进路', f'{len(orphan_nodes)} 个运输物品格不在任何从非运输单位出发的进路上：{orphan_nodes[:10]}')
if shared_nodes: prob('S2-进路', f'{len(shared_nodes)} 个运输物品格被多条进路共用：{shared_nodes[:10]}')

# 每条进路不重复经过物理单位
for r in routes:
    c = collections.Counter(r['phys'])
    dup = [u for u, n in c.items() if n > 1]
    if dup:
        prob('S2-进路', f'进路 {r["from"]} 重复经过物理单位 {dup}')
    if r['status'] != '到达':
        prob('S2-进路', f'从 {r["from"][0]} 端口 {r["from"][1:]} 出发的运输链 {r["status"]}，末格 {r["cells"][-1]}')

# 非前向通道
non_forward = [ch for ch in channels if ch not in used_forward]
reverse_ok = []
other_extra = []
fwd_set = set(used_forward)
for ch in non_forward:
    a, b = ch
    if units[a[0]]['kind'] == 'bridge' and units[b[0]]['kind'] == 'bridge' and (b, a) in fwd_set:
        reverse_ok.append(ch)
    else:
        other_extra.append(ch)
if other_extra:
    prob('S2-多余通道', f'{len(other_extra)} 条通道既不在进路上也不是相邻桥逆向通道：{other_extra}')
decl_rev = set()
for cid in Des.get('bridge_reverse_channels', []):
    for k, v in declared.items():
        if v == cid: decl_rev.add(k)
if decl_rev != set(reverse_ok):
    prob('声明-通道', f'bridge_reverse_channels 声明 {sorted(decl_rev)} 与重建的相邻桥逆向通道 {sorted(reverse_ok)} 不一致')

# ---------- 物品与供电 ----------
def product_of(uid, port):
    k = units[uid]['kind']
    if k == 'machine':
        prods = set()
        for r in machine[uid]['recipe_ids']: prods |= set(RECIPES[r][2])
        return prods
    if k == 'outlet': return {outlet[uid]['item']}
    if k == 'core': return {core_out.get((port[1], port[2], port[3]))}
    return set()

def consumes(uid):
    k = units[uid]['kind']
    if k == 'machine':
        s = set()
        for r in machine[uid]['recipe_ids']: s |= set(RECIPES[r][1])
        return s
    if k == 'core': return {'高容谷地电池', '精选荞愈胶囊'}
    return set()

done_routes = [r for r in routes if r['status'] == '到达']
for r in done_routes:
    src, dst = r['from'][0], r['to'][0]
    items = product_of(src, r['from'])
    r['item'] = sorted(items)[0] if len(items) == 1 else None
    if not (items & consumes(dst)):
        prob('S2-物品', f'进路 {src}→{dst} 物品 {items} 不是终点配方原料')

# 供电
def covered(m, p):
    px0, py0 = p['x0'] - 5, p['y0'] - 5
    px1, py1 = p['x0'] + 6, p['y0'] + 6
    return not (m['x1'] < px0 or m['x0'] > px1 or m['y1'] < py0 or m['y0'] > py1)
unpowered = [u for u, m in machine.items() if not any(covered(m, p) for p in poles)]
if unpowered: prob('规则-供电', f'{len(unpowered)} 台制造单位没有供电：{unpowered}')

# ---------- 桥接器 ----------
bridge_info = []
route_of_node = {}
for i, r in enumerate(done_routes):
    for c in r['cells']: route_of_node[c] = i
for uid, t in transport.items():
    if t['type'] != 'bridge': continue
    info = {'id': uid, 'xy': (t['x'], t['y'])}
    for ax, sides in (('H', (0, 2)), ('V', (1, 3))):
        chs_in = in_to.get((uid, ax), []); chs_out = out_from.get((uid, ax), [])
        fwd_in = [c for c in chs_in if c in fwd_set]
        info[ax] = {'in通道': len(chs_in), 'out通道': len(chs_out), '前向入': [c[1][3] for c in fwd_in],
                    '进路': None}
        rn = route_of_node.get((uid, ax))
        if rn is not None:
            r = done_routes[rn]
            info[ax]['进路'] = f'{r["from"][0]}→{r["to"][0]}'
        if not chs_in and not chs_out:
            info[ax]['用法'] = '未用'
        # 声明方向
        decl = t['H_in'] if ax == 'H' else t['V_in']
        derived = fwd_in[0][1][3] if len(fwd_in) == 1 else None
        info[ax]['声明入边'] = decl; info[ax]['重建入边'] = derived
        if decl != derived:
            prob('声明-桥接器', f'桥 {uid}{(t["x"], t["y"])} {ax} 轴声明入边 {decl}，重建 {derived}')
    if info['H']['进路'] and info['V']['进路']:
        rh = route_of_node[(uid, 'H')]; rv = route_of_node[(uid, 'V')]
        if rh == rv:
            prob('S2-桥接器', f'桥 {uid} 两轴属于同一进路')
    for ax in 'HV':
        if (info[ax]['in通道'] or info[ax]['out通道']) and info[ax]['进路'] is None:
            prob('S2-桥接器', f'桥 {uid} {ax} 轴有通道但不在完成进路上')
    bridge_info.append(info)

# ---------- S2 第 2 节的期望接法（按 S2 原文逐条写出） ----------
expected = collections.Counter()   # (src_role, dst_role, item) -> count
# 1. 蓝铁矿：34 条矿路各进一台 T；T_j -> KB_j；KB(2i-1),KB(2i) -> Bi
for j in range(1, 35):
    expected[('仓库取货口:蓝铁矿', f'T{j}', '蓝铁矿')] += 1
    expected[(f'T{j}', f'KB{j}', '蓝铁块')] += 1
for i in range(1, 18):
    expected[(f'KB{2*i-1}', f'B{i}', '蓝铁粉末')] += 1
    expected[(f'KB{2*i}', f'B{i}', '蓝铁粉末')] += 1
# 2. 源矿：U1..U6 由协议核心，U7..U18 由仓库取货口；U(2i-1),U(2i) -> Oi
for j in range(1, 19):
    src = '协议核心:源矿' if j <= 6 else '仓库取货口:源矿'
    expected[(src, f'U{j}', '源矿')] += 1
for i in range(1, 10):
    expected[(f'U{2*i-1}', f'O{i}', '源石粉末')] += 1
    expected[(f'U{2*i}', f'O{i}', '源石粉末')] += 1
# 3. Bi->Ri；R1..R6->P1..P6；R7,R8->H1 ... R15,R16->H5；R17->H6
for i in range(1, 18):
    expected[(f'B{i}', f'R{i}', '致密蓝铁粉末')] += 1
for i in range(1, 7):
    expected[(f'R{i}', f'P{i}', '钢块')] += 1
for k in range(5):
    expected[(f'R{7+2*k}', f'H{k+1}', '钢块')] += 1
    expected[(f'R{8+2*k}', f'H{k+1}', '钢块')] += 1
expected[('R17', 'H6', '钢块')] += 1
# 4. Ei 收 P(2i-1),P(2i) 及 O(3i-2..3i)
for i in range(1, 4):
    expected[(f'P{2*i-1}', f'E{i}', '钢制零件')] += 1
    expected[(f'P{2*i}', f'E{i}', '钢制零件')] += 1
    for k in (3*i-2, 3*i-1, 3*i):
        expected[(f'O{k}', f'E{i}', '致密源石粉末')] += 1
# 5. F1: H1,H2,Q1,Q2; F2: H3,H4,Q3,Q4; F3: H5,Q5; F4: H6,Q6
for f, hs, qs in (('F1', (1, 2), (1, 2)), ('F2', (3, 4), (3, 4)), ('F3', (5,), (5,)), ('F4', (6,), (6,))):
    for h_ in hs: expected[(f'H{h_}', f, '钢质瓶')] += 1
    for q in qs: expected[(f'Q{q}', f, '细磨荞花粉末')] += 1
# 6. 成品入库
for e in ('E1', 'E2', 'E3'): expected[(e, 'CORE', '高容谷地电池')] += 1
for f in ('F1', 'F2', 'F3', 'F4'): expected[(f, 'CORE', '精选荞愈胶囊')] += 1
# 植物单元
for j in range(1, 14):
    expected[(f'SC{j}', f'SA{j}', '砂叶种子')] += 1
    expected[(f'SC{j}', f'SB{j}', '砂叶种子')] += 1
    expected[(f'SA{j}', f'SC{j}', '砂叶')] += 1
    expected[(f'SB{j}', f'S{j}', '砂叶')] += 1
for j in range(1, 7):
    expected[(f'QC{j}', f'QA{j}', '荞花种子')] += 1
    expected[(f'QC{j}', f'QB{j}', '荞花种子')] += 1
    expected[(f'QA{j}', f'QC{j}', '荞花')] += 1
    expected[(f'QB{j}', f'KQ{j}', '荞花')] += 1
for j in range(1, 6):
    expected[(f'KQ{j}', f'Q{j}', '荞花粉末')] += 2
expected[('KQ6', 'Q6', '荞花粉末')] += 1
SAND = {1: ['B1', 'B2', 'O1'], 2: ['O2', 'O3'], 3: ['B3', 'B4', 'O4'], 4: ['O5', 'O6'],
        5: ['B5', 'B6', 'O7'], 6: ['O8', 'O9'], 7: ['B7', 'B8', 'B9'], 8: ['B10', 'Q1', 'Q2'],
        9: ['B11', 'B12', 'B13'], 10: ['B14', 'Q3', 'Q4'], 11: ['B15', 'B16', 'Q5'], 12: ['B17'], 13: ['Q6']}
for j, dsts in SAND.items():
    for t in dsts: expected[(f'S{j}', t, '砂叶粉末')] += 1
n_expected = sum(expected.values())

def role_src(r):
    u = r['from'][0]
    k = units[u]['kind']
    if k == 'outlet': return f'仓库取货口:{outlet[u]["item"]}'
    if k == 'core': return f'协议核心:{core_out.get((r["from"][1], r["from"][2], r["from"][3]))}'
    return u
actual = collections.Counter()
for r in done_routes:
    actual[(role_src(r), r['to'][0], r.get('item'))] += 1

# 仓库/核心来源不按名字固定：检查 T、U 各收到几条矿路
missing = []
extra = []
for k in set(expected) | set(actual):
    e, a = expected.get(k, 0), actual.get(k, 0)
    if a < e: missing.append((k, e - a))
    if a > e: extra.append((k, a - e))
missing.sort(); extra.sort()
n_missing = sum(n for _, n in missing)
n_extra = sum(n for _, n in extra)
if extra: prob('S2-接法', f'{n_extra} 条进路不在 S2 第2节接法中：{extra}')
if n_missing: prob('S2-接法', f'缺 {n_missing} 条 S2 第2节进路（完成 {len(done_routes)}/{n_expected}）')

# 同一单位不同进路是否用不同端口（端口唯一由通道唯一保证；这里检查同一机器端口被多条进路占用）
port_use = collections.Counter()
for r in done_routes:
    port_use[r['from']] += 1; port_use[r['to']] += 1
dup_ports = [p for p, n in port_use.items() if n > 1]
if dup_ports: prob('S2-进路', f'端口被多条进路共用：{dup_ports}')

# ---------- H6->F4 与 Q6->F4 ----------
def route_len(src, dst):
    return [len(r['cells']) for r in done_routes if r['from'][0] == src and r['to'][0] == dst]
h6 = route_len('H6', 'F4'); q6 = route_len('Q6', 'F4')
if not h6 or not q6:
    prob('S2-等长', f'H6→F4 物品格数 {h6 or "缺路"}，Q6→F4 物品格数 {q6 or "缺路"}，等长条件无从满足')
elif h6 != q6:
    prob('S2-等长', f'H6→F4 {h6} 格，Q6→F4 {q6} 格，不等长')

# ---------- 核心与取货口 ----------
core_ports_status = []
for (x, y, s), item in sorted(core_out.items()):
    dx, dy = DELTA[s]; n = (x + dx, y + dy)
    occu = occ.get(n)
    used = any(r['from'][0] == 'CORE' and (r['from'][1], r['from'][2], r['from'][3]) == (x, y, s) for r in done_routes)
    dst = [r['to'][0] for r in done_routes if r['from'][0] == 'CORE' and (r['from'][1], r['from'][2], r['from'][3]) == (x, y, s)]
    core_ports_status.append({'端口格': (x, y), '边': s, '物品': item, '对面格': n, '对面单位': occu,
                              '对面单位类型': units[occu]['kind'] if occu else None, '进路终点': dst})
    if occu is None or not is_tr(occu):
        prob('约束-核心邻格', f'协议核心取货端口 {(x, y)} 边{s} 对面格 {n} 是 {occu or "空格"}（{units[occu]["kind"] if occu else "-"}），不是运输单位，该口不能出货')
core_in_used = [r for r in done_routes if r['to'][0] == 'CORE']

# 边带排布
left = sorted(o['y0'] for o in outlet.values() if o['Dout'] == 0)
bottom = sorted(o['x0'] for o in outlet.values() if o['Dout'] == 1)
def band_gap(starts):
    covered_ = set()
    for s in starts: covered_ |= {s, s + 1, s + 2}
    return sorted(set(range(70)) - covered_)
band = {'左边界取货口数': len(left), '下边界取货口数': len(bottom),
        '左边界空格行': band_gap(left), '下边界空格列': band_gap(bottom)}
if len(left) != 23 or len(bottom) != 23:
    prob('约束-边带排布', f'左 {len(left)}、下 {len(bottom)} 个取货口，不是各 23 个')
for name, gaps in (('左', band['左边界空格行']), ('下', band['下边界空格列'])):
    if len(gaps) != 1 or gaps[0] % 3 != 0:
        prob('约束-边带排布', f'{name}边界空格 {gaps}（应恰 1 格且在从角起第 3k+1 格）')
if not (band['左边界空格行'][:1] == [0] or band['下边界空格列'][:1] == [0]):
    prob('约束-边带排布', '两边的空格都不在角格')
outlet_port_status = []
for uid, o in sorted(outlet.items()):
    if o['Dout'] == 0: n = (1, o['y0'] + 1)
    else: n = (o['x0'] + 1, 1)
    occu = occ.get(n)
    rs = [r for r in done_routes if r['from'][0] == uid]
    outlet_port_status.append({'id': uid, '物品': o['item'], '对面格': n, '对面单位': occu,
                               '进路终点': [r['to'][0] for r in rs]})
    if occu is None or not is_tr(occu):
        prob('约束-边带排布', f'仓库取货口 {uid} 端口对面格 {n} 是 {occu or "空格"}，不是运输单位')
    elif not rs:
        prob('S2-接法', f'仓库取货口 {uid} 端口对面有运输单位但没有完成进路')
ore_routes = [r for r in done_routes if units[r['from'][0]]['kind'] in ('outlet', 'core')]

# ---------- 空矩形（编码一：逐行直方图） ----------
grid = [[False] * H for _ in range(W)]
for (x, y) in occ: grid[x][y] = True
best = None; best_list = []
hgt = [0] * W   # 以行 y 为上沿，向下连续空格数
for y in range(H):
    for x in range(W):
        hgt[x] = 0 if grid[x][y] else hgt[x] + 1
    for x0 in range(W):
        mn = 10 ** 9
        for x1 in range(x0, W):
            mn = min(mn, hgt[x1])
            if mn == 0: break
            w = x1 - x0 + 1; h = mn
            if w < 6 or h < 6: continue
            key = (w * h, min(w, h))
            rect = (x0, y - h + 1, x1, y)
            if best is None or key > best:
                best = key; best_list = [rect]
            elif key == best:
                best_list.append(rect)
best_list = sorted(set(best_list))
er = d['empty_rectangle']
er_rect = (er['x0'], er['y0'], er['x1'], er['y1'])
er_empty = all(not grid[x][y] for x in range(er['x0'], er['x1'] + 1) for y in range(er['y0'], er['y1'] + 1))
er_w, er_h = er['x1'] - er['x0'] + 1, er['y1'] - er['y0'] + 1
if not er_empty: prob('空矩形', f'声明空矩形 {er_rect} 含单位')
if best is None:
    prob('空矩形', '没有短边≥6 的空矩形')
elif (er_w * er_h, min(er_w, er_h)) != best:
    prob('空矩形', f'声明空矩形 {er_rect} 的 (面积,短边)=({er_w*er_h},{min(er_w,er_h)}) 与重算最大 {best} 不符')

# ---------- logical_feeds 与重建进路比对 ----------
id2ch = {v: k for k, v in declared.items()}
traced_by_start = {r['from']: r for r in done_routes}
lf_bad = []
lf_seen = set()
for lf in Des.get('logical_feeds', []):
    a = portref_cell(lf['from']); b = portref_cell(lf['to'])
    r = traced_by_start.get(a)
    pth = [id2ch.get(cid) for cid in lf['path']]
    if r is None or r['to'] != b or pth != r['path']:
        lf_bad.append(lf['id'])
    elif lf['item'] != r.get('item'):
        lf_bad.append(lf['id'] + ':物品')
    lf_seen.add(a)
lf_unlisted = [r['from'] for r in done_routes if r['from'] not in lf_seen]
if lf_bad: prob('声明-进路', f'logical_feeds 与重建进路不符：{lf_bad}')
if lf_unlisted: prob('声明-进路', f'重建出的进路未列入 logical_feeds：{lf_unlisted}')

# ---------- 每桩覆盖台数（供电下限的几何上限，作为占格自洽检查） ----------
pole_cover = {}
for p in poles:
    n = sum(1 for m in machine.values() if covered(m, p))
    edge_ = any(v in (1, 69) for v in (p['x0'], p['x1'])) or any(v in (1, 69) for v in (p['y0'], p['y1']))
    pole_cover[p['id']] = (n, edge_)
    if n > 24 or (edge_ and n > 14):
        prob('约束-供电下限', f'{p["id"]} 覆盖 {n} 台制造单位（贴第1/69行列={edge_}）')

# ---------- 汇总 ----------
out = {
    '候选SHA256': cand_sha,
    '快照指纹一致': fp_ok, '临时规则指纹在provenance中': tmp_ok,
    '制造单位数': len(machine),
    '按机型': dict(collections.Counter(m['model'] for m in machine.values())),
    '机身占格': machine_cells,
    '协议核心占格': len(units['CORE']['cells']),
    '仓库取货口数': len(outlet), '仓库取货口占格': sum(len(units[u]['cells']) for u in outlet),
    '供电桩数': len(poles), '已供电制造单位': len(machine) - len(unpowered),
    '传送带数': sum(1 for t in transport.values() if t['type'] == 'belt'),
    '桥接器数': sum(1 for t in transport.values() if t['type'] == 'bridge'),
    '总占格': n_occ, '空格': W * H - n_occ,
    '重建通道数': len(channels), '声明通道数': len(Des['physical_channels']),
    '前向通道数': len(used_forward), '相邻桥逆向通道': [list(map(list, c)) for c in reverse_ok],
    '其他非前向通道': [list(map(list, c)) for c in other_extra],
    '运输链总数': len(routes), '完成进路数': len(done_routes),
    '未完成运输链': [{'起点': r['from'], '状态': r['status'], '格数': len(r['cells'])} for r in routes if r['status'] != '到达'],
    '完成进路物品格总数': sum(len(r['cells']) for r in done_routes),
    'S2期望进路数': n_expected, '缺进路数': n_missing, '多余进路数': n_extra,
    '缺进路明细': [[list(k), n] for k, n in missing],
    '多余进路明细': [[list(k), n] for k, n in extra],
    '矿路完成数': len(ore_routes),
    '成品入库进路数': len(core_in_used),
    '桥接器': bridge_info,
    'H6到F4物品格': h6, 'Q6到F4物品格': q6,
    '协议核心取货端口': core_ports_status,
    '边带': band, '仓库取货口端口': outlet_port_status,
    '最大空矩形(面积,短边)': best, '最大空矩形全部位置': best_list,
    '声明空矩形': er_rect, '声明空矩形为空': er_empty,
    '未供电': unpowered,
    'logical_feeds不符': lf_bad, '未列入logical_feeds的进路': lf_unlisted,
    '每桩覆盖': pole_cover,
    '问题': problems,
}
json.dump(out, open(os.path.join(HERE, OUTNAME) if not os.path.isabs(OUTNAME) else OUTNAME, 'w'), ensure_ascii=False, indent=1, default=str)
print('SHA', cand_sha)
print('fingerprints', fp_ok, 'tmp', tmp_ok)
for k in ('制造单位数', '机身占格', '协议核心占格', '仓库取货口数', '仓库取货口占格', '供电桩数', '已供电制造单位', '传送带数', '桥接器数',
          '总占格', '空格', '重建通道数', '声明通道数', '前向通道数', '运输链总数', '完成进路数', '完成进路物品格总数',
          'S2期望进路数', '缺进路数', '多余进路数', '矿路完成数', '成品入库进路数', 'H6到F4物品格', 'Q6到F4物品格',
          '最大空矩形(面积,短边)', '最大空矩形全部位置', '声明空矩形', '声明空矩形为空'):
    print(k, out[k])
print('按机型', out['按机型'])
print('问题数', len(problems))
cnt = collections.Counter(p['类别'] for p in problems)
print(cnt)

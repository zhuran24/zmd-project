#!/usr/bin/env python3
"""核查B 第二套编码：与 check_main.py 不共用任何函数。

占格用 70×70 涂色计数；通道按每对相邻格逐边判断两侧端口；
进路从终点（非运输单位存货端口）倒着追；空矩形用二维前缀和穷举；
供电用连续坐标区间相交；S2 接法按「每台终点的来路」另写一份。
输出：核查B/结果-副.json
"""
import json, os, collections, hashlib, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '构造B', '候选布局.json')
OUTNAME = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '结果-副.json')
raw = open(P, 'rb').read()
D = json.loads(raw)
LY = D['layout']
N = 70

owner = [[None] * N for _ in range(N)]
paint = [[0] * N for _ in range(N)]
info = {}

def paint_rect(uid, x0, y0, x1, y1, typ):
    info[uid] = (typ, x0, y0, x1, y1)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            paint[y][x] += 1
            owner[y][x] = uid

for m in LY['machines']:
    paint_rect(m['id'], m['x0'], m['y0'], m['x1'], m['y1'], 'M')
for o in LY['warehouse_outlets']:
    paint_rect(o['id'], o['x0'], o['y0'], o['x1'], o['y1'], 'O')
c = LY['core']; paint_rect('CORE', c['x0'], c['y0'], c['x1'], c['y1'], 'C')
for p in LY['power_poles']:
    paint_rect(p['id'], p['x0'], p['y0'], p['x1'], p['y1'], 'P')
for t in LY['transport']:
    paint_rect(t['id'], t['x'], t['y'], t['x'], t['y'], {'belt': 'Tb', 'bridge': 'Tr'}.get(t['type'], 'T?' + t['type']))

overlaps = sum(1 for y in range(N) for x in range(N) if paint[y][x] > 1)
occupied = sum(1 for y in range(N) for x in range(N) if paint[y][x] > 0)
painted_total = sum(paint[y][x] for y in range(N) for x in range(N))

MBY = {m['id']: m for m in LY['machines']}
OBY = {o['id']: o for o in LY['warehouse_outlets']}
TBY = {t['id']: t for t in LY['transport']}

# 方向：E=0 N=1 W=2 S=3。格 (x,y) 在单位 uid 的 side 边上的端口性质
def port_io(uid, x, y, side):
    typ = info[uid][0]
    if typ == 'P':
        return None
    if typ == 'Tb':  # belt
        t = TBY[uid]
        if side == t['in_side']: return 'I'
        if side == t['out_side']: return 'O'
        return None
    if typ == 'Tr':  # bridge
        return 'IO'
    if typ.startswith('T'):
        raise SystemExit('未知运输类型 ' + typ)
    _, x0, y0, x1, y1 = info[uid]
    on_edge = {0: x == x1, 2: x == x0, 1: y == y1, 3: y == y0}[side]
    if not on_edge:
        return None
    if typ == 'M':
        din = MBY[uid]['Din']
        if side == din: return 'I'
        if side == (din + 2) % 4: return 'O'
        return None
    if typ == 'O':
        o = OBY[uid]
        if o['Dout'] == 0 and side == 0 and y == y0 + 1: return 'O'
        if o['Dout'] == 1 and side == 1 and x == x0 + 1: return 'O'
        return None
    if typ == 'C':
        din = c['Din']
        off = (y - y0) if side in (0, 2) else (x - x0)
        if side in (din, (din + 2) % 4):
            return 'I' if 1 <= off <= 7 else None
        return 'O' if off in (1, 4, 7) else None

def is_t(uid): return info[uid][0].startswith('T')

# 逐对相邻格
chans = []  # (from_uid, fx, fy, fside, to_uid, tx, ty, tside)
for y in range(N):
    for x in range(N):
        for (dx, dy, s) in ((1, 0, 0), (0, 1, 1)):
            x2, y2 = x + dx, y + dy
            if x2 >= N or y2 >= N: continue
            a, b = owner[y][x], owner[y2][x2]
            if a is None or b is None or a == b: continue
            if not (is_t(a) or is_t(b)): continue
            pa = port_io(a, x, y, s); pb = port_io(b, x2, y2, (s + 2) % 4)
            if pa is None or pb is None: continue
            if 'O' in pa and 'I' in pb: chans.append((a, x, y, s, b, x2, y2, (s + 2) % 4))
            if 'I' in pa and 'O' in pb: chans.append((b, x2, y2, (s + 2) % 4, a, x, y, s))

# 物品格：带子一格，桥按轴
def cell_key(uid, side):
    if info[uid][0] == 'Tb': return (uid, '-')
    return (uid, 'H' if side in (0, 2) else 'V')

into = collections.defaultdict(list)    # 运输物品格 -> 进入它的通道
for ch in chans:
    if is_t(ch[4]): into[cell_key(ch[4], ch[7])].append(ch)

# 倒追：从每条「运输单位 -> 非运输单位」通道出发
def back_entry(uid, exit_side):
    """物品从 exit_side 离开 uid 时，它是从哪条边进来的；返回可能的进入通道。"""
    if info[uid][0] == 'Tb':
        ent = TBY[uid]['in_side']
    else:
        ent = (exit_side + 2) % 4
    return [ch for ch in into[cell_key(uid, ent)] if ch[7] == ent]

back_routes = []
for ch in chans:
    if not is_t(ch[0]) or is_t(ch[4]): continue
    seq = [ch]; cells = []
    cur, exs = ch[0], ch[3]
    status = None
    seen = set()
    while True:
        k = cell_key(cur, exs if info[cur][0] != 'Tb' else 0)
        if k in seen: status = 'loop'; break
        seen.add(k); cells.append(k)
        prev = back_entry(cur, exs)
        if len(prev) != 1:
            status = 'dead' if not prev else 'merge'; break
        p = prev[0]; seq.append(p)
        if not is_t(p[0]): status = 'ok'; break
        cur, exs = p[0], p[3]
    back_routes.append({'src': seq[-1][0], 'src_port': seq[-1][1:4], 'dst': ch[4], 'dst_port': ch[5:8],
                        'status': status, 'ncell': len(cells), 'cells': cells, 'nchan': len(seq)})

ok_routes = [r for r in back_routes if r['status'] == 'ok']
fwd = set()
cell_use = collections.Counter()
for r in ok_routes:
    for k in r['cells']: cell_use[k] += 1
fwd_count = sum(r['nchan'] for r in ok_routes)
# 统计不在任何倒追进路上的通道
route_chan = set()
for r in back_routes:
    pass
# 重新倒追一次收集通道
def collect(ch):
    out = [ch]; cur, exs = ch[0], ch[3]
    while True:
        prev = back_entry(cur, exs)
        if len(prev) != 1: return out
        out.append(prev[0])
        if not is_t(prev[0][0]): return out
        cur, exs = prev[0][0], prev[0][3]
for ch in chans:
    if is_t(ch[0]) and not is_t(ch[4]):
        for x in collect(ch): route_chan.add(x)
leftover = [ch for ch in chans if ch not in route_chan]

# 供电：连续坐标
def powered(m):
    for p in LY['power_poles']:
        cx, cy = p['x0'] + 1, p['y0'] + 1
        if m['x0'] < cx + 6 and m['x1'] + 1 > cx - 6 and m['y0'] < cy + 6 and m['y1'] + 1 > cy - 6:
            return True
    return False
n_pow = sum(1 for m in LY['machines'] if powered(m))

# 空矩形：二维前缀和穷举
S = [[0] * (N + 1) for _ in range(N + 1)]
for y in range(N):
    row = 0
    for x in range(N):
        row += 1 if paint[y][x] else 0
        S[y + 1][x + 1] = S[y][x + 1] + row
def cnt(x0, y0, x1, y1):
    return S[y1 + 1][x1 + 1] - S[y0][x1 + 1] - S[y1 + 1][x0] + S[y0][x0]
best = (0, 0); where = []
for x0 in range(N):
    for x1 in range(x0 + 5, N):
        w = x1 - x0 + 1
        for y0 in range(N):
            # 最长向上延伸
            if cnt(x0, y0, x1, min(N - 1, y0 + 5)) != 0 or y0 + 5 >= N:
                continue
            y1 = y0 + 5
            while y1 + 1 < N and cnt(x0, y1 + 1, x1, y1 + 1) == 0:
                y1 += 1
            for yy in range(y0 + 5, y1 + 1):
                h = yy - y0 + 1
                key = (w * h, min(w, h))
                if key > best: best = key; where = [(x0, y0, x1, yy)]
                elif key == best: where.append((x0, y0, x1, yy))

# S2：按终点写的来路表（与主程序独立写）
want = collections.Counter()
def add(dst, srcs, item):
    for s in srcs: want[(s, dst, item)] += 1
for i in range(1, 35): add('T%d' % i, ['ORE-蓝铁矿'], '蓝铁矿'); add('KB%d' % i, ['T%d' % i], '蓝铁块')
for i in range(1, 19): add('U%d' % i, ['CORE-源矿' if i <= 6 else 'ORE-源矿'], '源矿')
for i in range(1, 18): add('B%d' % i, ['KB%d' % (2 * i - 1), 'KB%d' % (2 * i)], '蓝铁粉末'); add('R%d' % i, ['B%d' % i], '致密蓝铁粉末')
for i in range(1, 10): add('O%d' % i, ['U%d' % (2 * i - 1), 'U%d' % (2 * i)], '源石粉末')
for i in range(1, 7): add('P%d' % i, ['R%d' % i], '钢块')
add('H1', ['R7', 'R8'], '钢块'); add('H2', ['R9', 'R10'], '钢块'); add('H3', ['R11', 'R12'], '钢块')
add('H4', ['R13', 'R14'], '钢块'); add('H5', ['R15', 'R16'], '钢块'); add('H6', ['R17'], '钢块')
add('E1', ['P1', 'P2'], '钢制零件'); add('E1', ['O1', 'O2', 'O3'], '致密源石粉末')
add('E2', ['P3', 'P4'], '钢制零件'); add('E2', ['O4', 'O5', 'O6'], '致密源石粉末')
add('E3', ['P5', 'P6'], '钢制零件'); add('E3', ['O7', 'O8', 'O9'], '致密源石粉末')
add('F1', ['H1', 'H2'], '钢质瓶'); add('F1', ['Q1', 'Q2'], '细磨荞花粉末')
add('F2', ['H3', 'H4'], '钢质瓶'); add('F2', ['Q3', 'Q4'], '细磨荞花粉末')
add('F3', ['H5'], '钢质瓶'); add('F3', ['Q5'], '细磨荞花粉末')
add('F4', ['H6'], '钢质瓶'); add('F4', ['Q6'], '细磨荞花粉末')
add('CORE', ['E1', 'E2', 'E3'], '高容谷地电池'); add('CORE', ['F1', 'F2', 'F3', 'F4'], '精选荞愈胶囊')
for j in range(1, 14):
    add('SA%d' % j, ['SC%d' % j], '砂叶种子'); add('SB%d' % j, ['SC%d' % j], '砂叶种子')
    add('SC%d' % j, ['SA%d' % j], '砂叶'); add('S%d' % j, ['SB%d' % j], '砂叶')
for j in range(1, 7):
    add('QA%d' % j, ['QC%d' % j], '荞花种子'); add('QB%d' % j, ['QC%d' % j], '荞花种子')
    add('QC%d' % j, ['QA%d' % j], '荞花'); add('KQ%d' % j, ['QB%d' % j], '荞花')
for j in range(1, 6): add('Q%d' % j, ['KQ%d' % j, 'KQ%d' % j], '荞花粉末')
add('Q6', ['KQ6'], '荞花粉末')
sand_by_dst = {'B1': 1, 'B2': 1, 'O1': 1, 'O2': 2, 'O3': 2, 'B3': 3, 'B4': 3, 'O4': 3, 'O5': 4, 'O6': 4,
               'B5': 5, 'B6': 5, 'O7': 5, 'O8': 6, 'O9': 6, 'B7': 7, 'B8': 7, 'B9': 7, 'B10': 8, 'Q1': 8, 'Q2': 8,
               'B11': 9, 'B12': 9, 'B13': 9, 'B14': 10, 'Q3': 10, 'Q4': 10, 'B15': 11, 'B16': 11, 'Q5': 11,
               'B17': 12, 'Q6': 13}
for dst, s in sand_by_dst.items(): add(dst, ['S%d' % s], '砂叶粉末')

PROD = {'粉碎-源矿': '源石粉末', '粉碎-蓝铁块': '蓝铁粉末', '粉碎-荞花': '荞花粉末', '粉碎-砂叶': '砂叶粉末',
        '精炼-蓝铁矿': '蓝铁块', '精炼-致密蓝铁': '钢块', '研磨-致密蓝铁': '致密蓝铁粉末', '研磨-致密源石': '致密源石粉末',
        '研磨-细磨荞花': '细磨荞花粉末', '塑形-钢质瓶': '钢质瓶', '配件-钢制零件': '钢制零件', '种植-荞花': '荞花',
        '种植-砂叶': '砂叶', '采种-荞花': '荞花种子', '采种-砂叶': '砂叶种子', '封装-电池': '高容谷地电池', '灌装-胶囊': '精选荞愈胶囊'}
def src_label(r):
    u = r['src']; t = info[u][0]
    if t == 'O': return 'ORE-' + OBY[u]['item']
    if t == 'C':
        x, y, s = r['src_port']
        off = (x - c['x0']) if s in (1, 3) else (y - c['y0'])
        for oi in c['output_items']:
            if oi['side'] == s and oi['offset'] == off: return 'CORE-' + oi['item']
    return u
def item_of(r):
    u = r['src']; t = info[u][0]
    if t == 'O': return OBY[u]['item']
    if t == 'C': return src_label(r).split('-')[1]
    return PROD[MBY[u]['recipe_ids'][0]]
have = collections.Counter((src_label(r), r['dst'], item_of(r)) for r in ok_routes)
lack = {k: want[k] - have.get(k, 0) for k in want if want[k] > have.get(k, 0)}
surplus = {k: have[k] - want.get(k, 0) for k in have if have[k] > want.get(k, 0)}

len_h6 = [r['ncell'] for r in ok_routes if r['src'] == 'H6' and r['dst'] == 'F4']
len_q6 = [r['ncell'] for r in ok_routes if r['src'] == 'Q6' and r['dst'] == 'F4']

res = {
    'sha256': hashlib.sha256(raw).hexdigest(),
    '重叠格': overlaps, '占格': occupied, '涂色总次数': painted_total, '空格': N * N - occupied,
    '机身占格': sum((m['x1'] - m['x0'] + 1) * (m['y1'] - m['y0'] + 1) for m in LY['machines']),
    '通道数': len(chans), '通道去重数': len(set(chans)),
    '倒追运输链': len(back_routes), '倒追状态': dict(collections.Counter(r['status'] for r in back_routes)),
    '完成进路': len(ok_routes), '进路通道合计': fwd_count, '进路物品格合计': sum(r['ncell'] for r in ok_routes),
    '被多条进路共用的物品格': [k for k, v in cell_use.items() if v > 1],
    '不在进路上的通道': leftover,
    '供电制造单位': n_pow,
    'S2期望总数': sum(want.values()), '缺': sum(lack.values()), '多': sum(surplus.values()),
    '多余明细': [[list(k), v] for k, v in surplus.items()],
    '矿路完成': sum(1 for r in ok_routes if info[r['src']][0] in ('O', 'C')),
    '成品入库': sum(1 for r in ok_routes if r['dst'] == 'CORE'),
    'H6F4': len_h6, 'Q6F4': len_q6,
    '最大空矩形': best, '位置': sorted(set(where)),
}
json.dump(res, open(OUTNAME, 'w'), ensure_ascii=False, indent=1, default=str)
for k, v in res.items():
    print(k, v)

#!/usr/bin/env python3
"""核查-实现 编码二：与 check_main.py 不共享代码。
- 用 70×70 整数网格涂单位编号；端口按「该格往该方向的邻格不属于本单位」判外边，再按单位定义判存取。
- 通道：枚举全部水平、竖直相邻格对，两向各判一次。
- 进路：从非运输单位的存货端口倒着追到取货端口。
- 期望接法：按汇（终点单位）逐台写来路清单。
- 空矩形：二维前缀和穷举全部宽高 ≥6 的矩形。
用法：python3 check_alt.py <布局.json> <输出.json>
"""
import json, sys
from collections import Counter, defaultdict

doc = json.load(open(sys.argv[1]))
L = doc['layout']
N = 70
STEP = [(1, 0), (0, 1), (-1, 0), (0, -1)]

U = []          # 单位表
G = [[-1] * N for _ in range(N)]
issues = []


def put(d):
    k = len(U)
    U.append(d)
    for x in range(d['x0'], d['x1'] + 1):
        for y in range(d['y0'], d['y1'] + 1):
            if not (0 <= x < N and 0 <= y < N):
                issues.append('出界 %s' % d['id'])
                continue
            if G[x][y] != -1:
                issues.append('重叠 %s %s (%d,%d)' % (U[G[x][y]]['id'], d['id'], x, y))
            G[x][y] = k
    return k


SIZE = {'粉碎机': 3, '精炼炉': 3, '配件机': 3, '塑形机': 3, '采种机': 5, '种植机': 5}
for m in L['machines']:
    w = m['x1'] - m['x0'] + 1
    h = m['y1'] - m['y0'] + 1
    if m['model'] in SIZE:
        if (w, h) != (SIZE[m['model']],) * 2:
            issues.append('尺寸 %s' % m['id'])
    else:
        # 大型：存取两边是长 6 的边
        if m['Din'] % 2 == 1 and (w, h) != (6, 4):
            issues.append('尺寸 %s' % m['id'])
        if m['Din'] % 2 == 0 and (w, h) != (4, 6):
            issues.append('尺寸 %s' % m['id'])
    put(dict(id=m['id'], t='M', x0=m['x0'], y0=m['y0'], x1=m['x1'], y1=m['y1'], din=m['Din'],
             rec=m['recipe_ids'], on=m['settings']['manufacture_on'], model=m['model']))
for o in L['warehouse_outlets']:
    put(dict(id=o['id'], t='O', x0=o['x0'], y0=o['y0'], x1=o['x1'], y1=o['y1'], item=o['item']))
c = L['core']
CORE = put(dict(id='CORE', t='C', x0=c['x0'], y0=c['y0'], x1=c['x1'], y1=c['y1'], din=c['Din'],
                outs={(i['side'], i['offset']): i['item'] for i in c['output_items']}))
for p in L['power_poles']:
    put(dict(id=p['id'], t='P', x0=p['x0'], y0=p['y0'], x1=p['x1'], y1=p['y1']))
for t in L['transport']:
    if t['type'] == 'belt':
        put(dict(id=t['id'], t='b', x0=t['x'], y0=t['y'], x1=t['x'], y1=t['y'], i=t['in_side'], o=t['out_side']))
    elif t['type'] == 'bridge':
        put(dict(id=t['id'], t='g', x0=t['x'], y0=t['y'], x1=t['x'], y1=t['y'], hin=t['H_in'], vin=t['V_in']))
    else:
        issues.append('禁用运输单位 %s' % t['id'])


def outer(k, x, y, d):
    nx, ny = x + STEP[d][0], y + STEP[d][1]
    return not (0 <= nx < N and 0 <= ny < N) or G[nx][ny] != k


def can_give(k, x, y, d):
    u = U[k]
    if not outer(k, x, y, d):
        return False
    t = u['t']
    if t == 'b':
        return d == u['o']
    if t == 'g':
        return True
    if t == 'M':
        return d == (u['din'] + 2) % 4
    if t == 'O':
        # 外边：贴左边界的口向右，贴下边界的口向上，只有中间一格
        if u['x0'] == u['x1'] == 0:
            return d == 0 and y == u['y0'] + 1
        if u['y0'] == u['y1'] == 0:
            return d == 1 and x == u['x0'] + 1
        return False
    if t == 'C':
        if d % 2 == u['din'] % 2:
            return False
        off = x - u['x0'] if d % 2 == 1 else y - u['y0']
        return (d, off) in u['outs']
    return False


def can_take(k, x, y, d):
    u = U[k]
    if not outer(k, x, y, d):
        return False
    t = u['t']
    if t == 'b':
        return d == u['i']
    if t == 'g':
        return True
    if t == 'M':
        return d == u['din']
    if t == 'C':
        if d % 2 != u['din'] % 2:
            return False
        off = x - u['x0'] if d % 2 == 1 else y - u['y0']
        return 1 <= off <= 7
    return False


TR = ('b', 'g')
# 通道：(from_k, from_cell, from_d) -> (to_k, to_cell, to_d)
give = {}
take = defaultdict(list)
chans = []
for x in range(N):
    for y in range(N):
        for d in (0, 1):
            nx, ny = x + STEP[d][0], y + STEP[d][1]
            if nx >= N or ny >= N:
                continue
            a, b = G[x][y], G[nx][ny]
            if a < 0 or b < 0 or a == b:
                continue
            if U[a]['t'] not in TR and U[b]['t'] not in TR:
                continue
            if can_give(a, x, y, d) and can_take(b, nx, ny, d + 2):
                chans.append(((a, (x, y), d), (b, (nx, ny), d + 2)))
            if can_give(b, nx, ny, d + 2) and can_take(a, x, y, d):
                chans.append(((b, (nx, ny), d + 2), (a, (x, y), d)))
for f, t in chans:
    give[f] = t
    take[t].append(f)


def cell_of(k):
    return (U[k]['x0'], U[k]['y0'])


# 倒追：从每个非运输单位的存货端口
ROUTES = []
bad = []
for t_end, froms in list(take.items()):
    k, cell, d = t_end
    if U[k]['t'] in TR:
        continue
    for f in froms:
        seq = []           # (k, 轴)
        seen = set()
        cur = f
        ok = True
        while U[cur[0]]['t'] in TR:
            kk, cc, dd = cur          # dd：物品离开 kk 的边
            if kk in seen:
                ok = False
                bad.append(('重复单位', U[kk]['id']))
                break
            seen.add(kk)
            if U[kk]['t'] == 'b':
                ax = 'c'
                indir = U[kk]['i']
            else:
                ax = 'H' if dd % 2 == 0 else 'V'
                indir = (dd + 2) % 4
            seq.append((kk, ax, indir))
            ins = take.get((kk, cc, indir), [])
            if len(ins) != 1:
                ok = False
                bad.append(('入口数%d' % len(ins), U[kk]['id'], ax))
                break
            cur = ins[0]
        if ok:
            ROUTES.append(dict(src=cur[0], sport=(cur[2], cur[1]), dst=k, seq=list(reversed(seq))))

# 物品
PROD = {'粉碎-源矿': '源石粉末', '粉碎-蓝铁块': '蓝铁粉末', '粉碎-荞花': '荞花粉末', '粉碎-砂叶': '砂叶粉末',
        '精炼-蓝铁矿': '蓝铁块', '精炼-致密蓝铁': '钢块', '研磨-致密蓝铁': '致密蓝铁粉末', '研磨-致密源石': '致密源石粉末',
        '研磨-细磨荞花': '细磨荞花粉末', '塑形-钢质瓶': '钢质瓶', '配件-钢制零件': '钢制零件', '种植-荞花': '荞花',
        '种植-砂叶': '砂叶', '采种-荞花': '荞花种子', '采种-砂叶': '砂叶种子', '封装-电池': '高容谷地电池',
        '灌装-胶囊': '精选荞愈胶囊'}
NEED = {'粉碎-源矿': {'源矿'}, '粉碎-蓝铁块': {'蓝铁块'}, '粉碎-荞花': {'荞花'}, '粉碎-砂叶': {'砂叶'},
        '精炼-蓝铁矿': {'蓝铁矿'}, '精炼-致密蓝铁': {'致密蓝铁粉末'}, '研磨-致密蓝铁': {'蓝铁粉末', '砂叶粉末'},
        '研磨-致密源石': {'源石粉末', '砂叶粉末'}, '研磨-细磨荞花': {'荞花粉末', '砂叶粉末'}, '塑形-钢质瓶': {'钢块'},
        '配件-钢制零件': {'钢块'}, '种植-荞花': {'荞花种子'}, '种植-砂叶': {'砂叶种子'}, '采种-荞花': {'荞花'},
        '采种-砂叶': {'砂叶'}, '封装-电池': {'钢制零件', '致密源石粉末'}, '灌装-胶囊': {'钢质瓶', '细磨荞花粉末'}}


def item_of(r):
    u = U[r['src']]
    if u['t'] == 'M':
        return PROD[u['rec'][0]]
    if u['t'] == 'O':
        return u['item']
    if u['t'] == 'C':
        d, (x, y) = r['sport']
        off = x - u['x0'] if d % 2 == 1 else y - u['y0']
        return u['outs'][(d, off)]


for r in ROUTES:
    r['item'] = item_of(r)
    du = U[r['dst']]
    if du['t'] == 'M' and r['item'] not in NEED[du['rec'][0]]:
        issues.append('误料 %s→%s %s' % (U[r['src']]['id'], du['id'], r['item']))
    if du['t'] == 'C' and r['item'] not in ('高容谷地电池', '精选荞愈胶囊'):
        issues.append('非成品入核心 %s' % U[r['src']]['id'])

# 共用物品格；全部通道是否被进路覆盖或为相邻桥逆向
cellroute = Counter()
used_ch = set()
for r in ROUTES:
    for kk, ax, _ in r['seq']:
        cellroute[(kk, ax)] += 1
shared = [(U[k]['id'], a) for (k, a), n in cellroute.items() if n > 1]
# 前向通道集合：路上相邻元素
fwd = set()
for r in ROUTES:
    seq = r['seq']
    # 源 -> 第一格
    k0, ax0, in0 = seq[0]
    fwd.add((r['src'], k0, in0))
    for (ka, axa, ina), (kb, axb, inb) in zip(seq, seq[1:]):
        fwd.add((ka, kb, inb))
    kl, axl, inl = seq[-1]
    fwd.add((kl, r['dst'], None))
others = []
rev = []
for (fk, fc, fd), (tk, tc, td) in chans:
    if U[tk]['t'] in TR:
        key = (fk, tk, td)
    else:
        key = (fk, tk, None)
    if key in fwd:
        continue
    if U[fk]['t'] == 'g' and U[tk]['t'] == 'g' and (tk, fk, fd) in fwd:
        rev.append((U[fk]['id'], U[tk]['id']))
        continue
    others.append((U[fk]['id'], fc, fd, U[tk]['id'], tc, td))
unused_cells = []
for k, u in enumerate(U):
    if u['t'] == 'b' and (k, 'c') not in cellroute:
        unused_cells.append(u['id'])
    if u['t'] == 'g':
        for ax in 'HV':
            if (k, ax) not in cellroute:
                unused_cells.append(u['id'] + ':' + ax)
# 桥声明比对
bridge_decl_bad = []
for r in ROUTES:
    for kk, ax, ind in r['seq']:
        if U[kk]['t'] == 'g':
            dec = U[kk]['hin'] if ax == 'H' else U[kk]['vin']
            if dec != ind:
                bridge_decl_bad.append(U[kk]['id'])
# 桥两轴同路
two_axes_same = []
for r in ROUTES:
    ks = [kk for kk, _, _ in r['seq']]
    if len(ks) != len(set(ks)):
        two_axes_same.append(U[r['src']]['id'])

# ---------- 期望接法：按汇逐台写来路 ----------
INC = defaultdict(list)
for i in range(1, 35):
    INC['RF%d' % i] = ['矿:蓝铁矿']
    INC['KF%d' % i] = ['RF%d' % i]
for i in range(1, 19):
    INC['KO%d' % i] = ['核心:源矿' if i <= 6 else '矿:源矿']
sandsrc = {}
for s, ts in {1: ['B1', 'B2', 'O1'], 2: ['O2', 'O3'], 3: ['B3', 'B4', 'O4'], 4: ['O5', 'O6'], 5: ['B5', 'B6', 'O7'],
              6: ['O8', 'O9'], 7: ['B7', 'B8', 'B9'], 8: ['B10', 'Q1', 'Q2'], 9: ['B11', 'B12', 'B13'],
              10: ['B14', 'Q3', 'Q4'], 11: ['B15', 'B16', 'Q5'], 12: ['B17'], 13: ['Q6']}.items():
    for t in ts:
        sandsrc[t] = 'S%d' % s
for i in range(1, 18):
    INC['B%d' % i] = ['KF%d' % (2 * i - 1), 'KF%d' % (2 * i), sandsrc['B%d' % i]]
    INC['R%d' % i] = ['B%d' % i]
for i in range(1, 10):
    INC['O%d' % i] = ['KO%d' % (2 * i - 1), 'KO%d' % (2 * i), sandsrc['O%d' % i]]
for i in range(1, 6):
    INC['Q%d' % i] = ['QK%d' % i, 'QK%d' % i, sandsrc['Q%d' % i]]
INC['Q6'] = ['QK6', sandsrc['Q6']]
for i in range(1, 7):
    INC['P%d' % i] = ['R%d' % i]
INC['H1'] = ['R7', 'R8']; INC['H2'] = ['R9', 'R10']; INC['H3'] = ['R11', 'R12']
INC['H4'] = ['R13', 'R14']; INC['H5'] = ['R15', 'R16']; INC['H6'] = ['R17']
INC['E1'] = ['P1', 'P2', 'O1', 'O2', 'O3']
INC['E2'] = ['P3', 'P4', 'O4', 'O5', 'O6']
INC['E3'] = ['P5', 'P6', 'O7', 'O8', 'O9']
INC['F1'] = ['H1', 'H2', 'Q1', 'Q2']; INC['F2'] = ['H3', 'H4', 'Q3', 'Q4']
INC['F3'] = ['H5', 'Q5']; INC['F4'] = ['H6', 'Q6']
INC['CORE'] = ['E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4']
for p, n, k in (('S', 13, 'S'), ('Q', 6, 'QK')):
    for i in range(1, n + 1):
        INC['%sA%d' % (p, i)] = ['%sC%d' % (p, i)]
        INC['%sB%d' % (p, i)] = ['%sC%d' % (p, i)]
        INC['%sC%d' % (p, i)] = ['%sA%d' % (p, i)]
        INC['%s%d' % (k, i)] = ['%sB%d' % (p, i)]
assert sum(len(v) for v in INC.values()) == 325


def sname(r):
    u = U[r['src']]
    if u['t'] == 'O':
        return '矿:' + u['item']
    if u['t'] == 'C':
        return '核心:' + r['item']
    return u['id']


got = defaultdict(Counter)
for r in ROUTES:
    got[U[r['dst']]['id']][sname(r)] += 1
miss = []
extra = []
for t, srcs in INC.items():
    e = Counter(srcs)
    g = got.get(t, Counter())
    for s, n in (e - g).items():
        miss += [(s, t)] * n
    for s, n in (g - e).items():
        extra += [(s, t)] * n
for t in got:
    if t not in INC:
        for s, n in got[t].items():
            extra += [(s, t)] * n

# 等长
lenH = [len(r['seq']) for r in ROUTES if U[r['src']]['id'] == 'H6' and U[r['dst']]['id'] == 'F4']
lenQ = [len(r['seq']) for r in ROUTES if U[r['src']]['id'] == 'Q6' and U[r['dst']]['id'] == 'F4']

# 供电：覆盖网格
pw = [[0] * N for _ in range(N)]
for p in L['power_poles']:
    for x in range(max(0, p['x0'] - 5), min(N, p['x0'] + 7)):
        for y in range(max(0, p['y0'] - 5), min(N, p['y0'] + 7)):
            pw[x][y] = 1
nopower = []
for u in U:
    if u['t'] == 'M':
        if not any(pw[x][y] for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)):
            nopower.append(u['id'])
        if not u['on']:
            issues.append('开关关 %s' % u['id'])

# 空矩形：二维前缀和穷举
S = [[0] * (N + 1) for _ in range(N + 1)]
for x in range(N):
    for y in range(N):
        S[x + 1][y + 1] = S[x][y + 1] + S[x + 1][y] - S[x][y] + (1 if G[x][y] >= 0 else 0)
best = (0, 0)
arg = []
for x0 in range(N):
    for x1 in range(x0 + 5, N):
        w = x1 - x0 + 1
        for y0 in range(N):
            Sx1 = S[x1 + 1]
            Sx0 = S[x0]
            for y1 in range(y0 + 5, N):
                if Sx1[y1 + 1] - Sx0[y1 + 1] - Sx1[y0] + Sx0[y0]:
                    break
                h = y1 - y0 + 1
                key = (w * h, min(w, h))
                if key > best:
                    best, arg = key, [(x0, y0, x1, y1)]
                elif key == best:
                    arg.append((x0, y0, x1, y1))

er = doc['empty_rectangle']
declared_ok = (er['x0'], er['y0'], er['x1'], er['y1']) in arg
if not declared_ok:
    issues.append('声明空矩形 %s 不是重算最优 %s' % (er, arg))
out = dict(
    issues=issues,
    channels=len(chans), reverse=sorted(rev), other_channels=others,
    routes=len(ROUTES), bad_traces=bad, shared_cells=shared, unused_transport_cells=unused_cells,
    bridge_decl_mismatch=bridge_decl_bad, same_route_twice=two_axes_same,
    item_cells=len(cellroute),
    matched=325 - len(miss), missing=sorted(miss), extra=sorted(extra),
    H6F4=lenH, Q6F4=lenQ, unpowered=nopower,
    empty_rect=dict(area=best[0], short=best[1], where=arg),
    route_list=sorted((U[r['src']]['id'], U[r['dst']]['id'], r['item'], len(r['seq'])) for r in ROUTES),
)
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
print('通道', len(chans), '逆向', len(rev), '其他', len(others))
print('进路', len(ROUTES), '断/错追', len(bad), '共用格', len(shared), '未用运输物品格', len(unused_cells), '物品格', len(cellroute))
print('接法 已通', 325 - len(miss), '缺', len(miss), '接法外', len(extra))
print('等长', lenH, lenQ, '无电', nopower, '桥声明不符', bridge_decl_bad)
print('空矩形', best, arg)
print('其他问题', issues)

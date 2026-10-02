#!/usr/bin/env python3
"""核查B：缺路能否在不动非运输单位的前提下补出（放宽：撤去全部运输单位）。

依据：通道只在运输单位与端口相遇时形成（规则第16行），运输单位不能叠在非运输单位上；
桥接器可让进路互相交叉，但不能穿过机器、协议核心、仓库取货口、供电桩。
所以一条缺路可补的必要条件是：起点有一个取货端口，其对面格在界内且不被非运输单位占；
终点同理；两格在「不被非运输单位占的格」构成的四连通图中连通。
另做逐台计数：某单位按 S2 要的取货／存货进路数多于它对面格可放运输单位的端口数，则无论怎么布运输都不够。
读入 结果-主.json 的缺路明细（由 check_main.py 产生）。
输出：核查B/结果-卡点.json
"""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, '..', '构造B', '候选布局.json')))
R = json.load(open(os.path.join(HERE, '结果-主.json')))
LY = D['layout']
N = 70
DEL = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}

block = {}   # 非运输单位占格
def mark(uid, x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            block[(x, y)] = uid
for m in LY['machines']: mark(m['id'], m['x0'], m['y0'], m['x1'], m['y1'])
for o in LY['warehouse_outlets']: mark(o['id'], o['x0'], o['y0'], o['x1'], o['y1'])
c = LY['core']; mark('CORE', c['x0'], c['y0'], c['x1'], c['y1'])
for p in LY['power_poles']: mark(p['id'], p['x0'], p['y0'], p['x1'], p['y1'])

def edge(x0, y0, x1, y1, s):
    if s == 0: return [(x1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1) for x in range(x0, x1 + 1)]
    return [(x, y0) for x in range(x0, x1 + 1)]

# 端口：uid -> {'out': [(cell, side, item)], 'in': [...]}
ports = collections.defaultdict(lambda: {'out': [], 'in': []})
for m in LY['machines']:
    b = (m['x0'], m['y0'], m['x1'], m['y1'])
    for cc in edge(*b, m['Din']): ports[m['id']]['in'].append((cc, m['Din'], None))
    for cc in edge(*b, (m['Din'] + 2) % 4): ports[m['id']]['out'].append((cc, (m['Din'] + 2) % 4, None))
for o in LY['warehouse_outlets']:
    if o['Dout'] == 0: ports[o['id']]['out'].append(((0, o['y0'] + 1), 0, o['item']))
    else: ports[o['id']]['out'].append(((o['x0'] + 1, 0), 1, o['item']))
cb = (c['x0'], c['y0'], c['x1'], c['y1'])
for s in (c['Din'], (c['Din'] + 2) % 4):
    e = edge(*cb, s)
    for off in range(1, 8): ports['CORE']['in'].append((e[off], s, None))
for oi in c['output_items']:
    e = edge(*cb, oi['side'])
    ports['CORE']['out'].append((e[oi['offset']], oi['side'], oi['item']))

def facing(cell, s):
    return (cell[0] + DEL[s][0], cell[1] + DEL[s][1])
def free(cell, reserve):
    x, y = cell
    if not (0 <= x < N and 0 <= y < N): return False
    if cell in block: return False
    if reserve and reserve[0] <= x <= reserve[2] and reserve[1] <= y <= reserve[3]: return False
    return True

er = D['empty_rectangle']; RES = (er['x0'], er['y0'], er['x1'], er['y1'])

def components(reserve):
    comp = {}; k = 0
    for x in range(N):
        for y in range(N):
            if (x, y) in comp or not free((x, y), reserve): continue
            k += 1; st = [(x, y)]; comp[(x, y)] = k
            while st:
                a = st.pop()
                for dx, dy in DEL.values():
                    b = (a[0] + dx, a[1] + dy)
                    if b not in comp and free(b, reserve):
                        comp[b] = k; st.append(b)
    return comp

# S2 期望（从主结果取缺路；期望的整体度数从缺路+已完成重算）
missing = []
for (k, n) in R['缺进路明细']:
    for _ in range(n): missing.append(tuple(k))
# 已完成进路端口：从主结果没有直接给端口，这里用通道声明的 logical feeds 不可取——改为本程序独立判：
# 计数时不扣除已完成进路（放宽全部运输），只看端口对面格是否可放运输单位。

def src_units(role):
    if role.startswith('仓库取货口:'):
        it = role.split(':')[1]
        return [o['id'] for o in LY['warehouse_outlets'] if o['item'] == it]
    if role.startswith('协议核心:'):
        return ['CORE']
    return [role]

def avail_out(uid, item=None, reserve=None):
    res = []
    for (cell, s, it) in ports[uid]['out']:
        if item is not None and it is not None and it != item: continue
        f = facing(cell, s)
        if free(f, reserve): res.append(f)
    return res
def avail_in(uid, reserve=None):
    return [facing(cell, s) for (cell, s, _) in ports[uid]['in'] if free(facing(cell, s), reserve)]

out = {}
for tag, reserve in (('不保留空矩形', None), ('保留声明空矩形', RES)):
    comp = components(reserve)
    cls = collections.Counter(); detail = []
    for (src, dst, item) in missing:
        sus = src_units(src)
        so = []
        for u in sus: so += avail_out(u, item if u == 'CORE' else None, reserve)
        si = avail_in(dst, reserve)
        if not so: kind = '起点无可放运输单位的取货口对面格'
        elif not si: kind = '终点无可放运输单位的存货口对面格'
        else:
            cs = {comp[f] for f in so}; cd = {comp[f] for f in si}
            kind = '起终点不连通' if not (cs & cd) else '放宽后单路连通'
        cls[kind] += 1
        detail.append({'起点': src, '终点': dst, '物品': item, '类别': kind,
                       '起点可用对面格': so[:8], '终点可用对面格': si[:8]})
    out[tag] = {'分类': dict(cls), '明细': detail}

# 逐台计数：按 S2 全部进路（已完成+缺）需要的取货、存货进路数
need_out = collections.Counter(); need_in = collections.Counter()
done = collections.Counter()
for (k, n) in R['缺进路明细']:
    pass
# 期望度数：缺 + 已完成。已完成数从 结果-主 的 S2 统计反推不到端点，这里直接重建期望表
import importlib.util
exp = collections.Counter()
spec = R.get('S2期望进路数')
# 用主程序同样的 S2 期望（独立再写一遍度数即可）
deg_out = collections.Counter(); deg_in = collections.Counter()
def add(src, dst, n=1):
    deg_out[src] += n; deg_in[dst] += n
for j in range(1, 35): add('仓库取货口:蓝铁矿', f'T{j}'); add(f'T{j}', f'KB{j}')
for i in range(1, 18): add(f'KB{2*i-1}', f'B{i}'); add(f'KB{2*i}', f'B{i}'); add(f'B{i}', f'R{i}')
for j in range(1, 19): add('协议核心:源矿' if j <= 6 else '仓库取货口:源矿', f'U{j}')
for i in range(1, 10): add(f'U{2*i-1}', f'O{i}'); add(f'U{2*i}', f'O{i}')
for i in range(1, 7): add(f'R{i}', f'P{i}')
for k in range(5): add(f'R{7+2*k}', f'H{k+1}'); add(f'R{8+2*k}', f'H{k+1}')
add('R17', 'H6')
for i in range(1, 4):
    add(f'P{2*i-1}', f'E{i}'); add(f'P{2*i}', f'E{i}')
    for k in (3*i-2, 3*i-1, 3*i): add(f'O{k}', f'E{i}')
for f, hs in (('F1', (1, 2)), ('F2', (3, 4)), ('F3', (5,)), ('F4', (6,))):
    for h in hs: add(f'H{h}', f); add(f'Q{h}', f)
for e in ('E1', 'E2', 'E3', 'F1', 'F2', 'F3', 'F4'): add(e, 'CORE')
for j in range(1, 14): add(f'SC{j}', f'SA{j}'); add(f'SC{j}', f'SB{j}'); add(f'SA{j}', f'SC{j}'); add(f'SB{j}', f'S{j}')
for j in range(1, 7): add(f'QC{j}', f'QA{j}'); add(f'QC{j}', f'QB{j}'); add(f'QA{j}', f'QC{j}'); add(f'QB{j}', f'KQ{j}')
for j in range(1, 6): add(f'KQ{j}', f'Q{j}', 2)
add('KQ6', 'Q6')
SAND = {1: 3, 2: 2, 3: 3, 4: 2, 5: 3, 6: 2, 7: 3, 8: 3, 9: 3, 10: 3, 11: 3, 12: 1, 13: 1}
for j, n in SAND.items(): deg_out[f'S{j}'] += n
for g in [f'B{i}' for i in range(1, 18)] + [f'O{i}' for i in range(1, 10)] + [f'Q{i}' for i in range(1, 7)]:
    deg_in[g] += 1
assert sum(deg_out.values()) == 325 and sum(deg_in.values()) == 325, (sum(deg_out.values()), sum(deg_in.values()))

def shortage(reserve):
    res = []
    for uid in sorted(set(list(deg_out) + list(deg_in))):
        if ':' in uid: continue
        ao = len(set(avail_out(uid, None, reserve))); ai = len(set(avail_in(uid, reserve)))
        if deg_out[uid] > ao or deg_in[uid] > ai:
            res.append({'单位': uid, '需取货进路': deg_out[uid], '可用取货端口对面格': ao,
                        '需存货进路': deg_in[uid], '可用存货端口对面格': ai})
    return res
short = shortage(None)
short_res = shortage(RES)
out['端口不足的单位-保留空矩形'] = short_res
print('保留空矩形时端口不足', len(short_res), '其中制造单位', sum(1 for x in short_res if x['单位'] != 'CORE'))
print('不保留时端口不足', len(short), '其中制造单位', sum(1 for x in short if x['单位'] != 'CORE'))
core_out_av = len(set(avail_out('CORE', '源矿')))
outlets_dead = [o['id'] for o in LY['warehouse_outlets'] if not avail_out(o['id'])]
out['端口不足的单位'] = short
out['端口不足台数'] = len(short)
out['协议核心可用取货端口'] = core_out_av
out['取货端口对面被非运输单位占的仓库取货口'] = outlets_dead
json.dump(out, open(os.path.join(HERE, '结果-卡点.json'), 'w'), ensure_ascii=False, indent=1)
for tag in ('不保留空矩形', '保留声明空矩形'):
    print(tag, out[tag]['分类'])
print('端口不足台数', len(short))
for s in short: print(' ', s)
print('协议核心可用取货端口', core_out_av)
print('取货端口被堵的仓库取货口', outlets_dead)

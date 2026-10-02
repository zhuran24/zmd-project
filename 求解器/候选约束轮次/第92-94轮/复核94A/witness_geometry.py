#!/usr/bin/env python3
"""复核94A：「密集结点」见证的摆放核对（本席自写，坐标取自推导92A 第4节表格）。
坐标：基地左上格 (0,0)，x 向右、y 向下。每个单位列出占格与端口（格、朝向、存/取）。
核对：占格不重叠、都在 70×70 内、取货口贴左边界；按「一方取货端口与另一方存货端口相遇、
且至少一方是运输单位」列出全部通道，与预期通道表逐条相等（没有多出、没有缺少）。
"""
import json
D = {'R': (1, 0), 'L': (-1, 0), 'U': (0, -1), 'D': (0, 1)}
OPP = {'R': 'L', 'L': 'R', 'U': 'D', 'D': 'U'}
units = {}   # name -> dict(cells=set, transport=bool, ports=[(cell, dir, 'in'/'out')])

def add(name, cells, transport, ports):
    units[name] = dict(cells=set(cells), transport=transport, ports=ports)

# 取货口（仓库取货口，非运输）
add('取货口甲', [(0, y) for y in (9, 10, 11)], False, [((0, 10), 'R', 'out')])
add('取货口乙', [(0, y) for y in (1, 2, 3)], False, [((0, 2), 'R', 'out')])
# 传送带：每格一个单位，入口边与出口边
def belt(prefix, path, first_in, last_out):
    names = []
    for i, c in enumerate(path):
        if i == 0:
            din = first_in
        else:
            px, py = path[i - 1]; din = [k for k, v in D.items() if (c[0] + v[0], c[1] + v[1]) == (px, py)][0]
        if i == len(path) - 1:
            dout = last_out
        else:
            nx, ny = path[i + 1]; dout = [k for k, v in D.items() if (c[0] + v[0], c[1] + v[1]) == (nx, ny)][0]
        n = f'{prefix}{i}'
        add(n, [c], True, [(c, din, 'in'), (c, dout, 'out')])
        names.append(n)
    return names
pathA = [(x, 10) for x in range(1, 5)] + [(4, y) for y in range(11, 15)] + [(x, 14) for x in range(5, 9)] + [(8, y) for y in range(13, 9, -1)]
pathB = [(x, 2) for x in range(1, 12)] + [(11, y) for y in range(3, 8)]
A = belt('带甲', pathA, 'L', 'R')
B = belt('带乙', pathB, 'L', 'D')
add('准入口甲', [(9, 10)], True, [((9, 10), 'L', 'in'), ((9, 10), 'R', 'out')])
add('准入口乙', [(11, 8)], True, [((11, 8), 'U', 'in'), ((11, 8), 'D', 'out')])
add('分流器', [(10, 10)], True, [((10, 10), 'L', 'in')] + [((10, 10), d, 'out') for d in ('R', 'D', 'U')])
add('未设条件准入口', [(11, 9)], True, [((11, 9), 'U', 'in'), ((11, 9), 'D', 'out')])
add('汇流器甲', [(11, 10)], True, [((11, 10), d, 'in') for d in ('U', 'L', 'D')] + [((11, 10), 'R', 'out')])
add('汇流器乙', [(10, 11)], True, [((10, 11), d, 'in') for d in ('U', 'L', 'D')] + [((10, 11), 'R', 'out')])
R1 = belt('回库甲', [(12, 10)], 'L', 'R')
R2 = belt('回库乙', [(11, 11), (12, 11)], 'L', 'R')
core = [(x, y) for x in range(13, 22) for y in range(9, 18)]
cports = []
for i, y in enumerate(range(9, 18), start=1):
    if 2 <= i <= 8:
        cports += [((13, y), 'L', 'in'), ((21, y), 'R', 'in')]
for i, x in enumerate(range(13, 22), start=1):
    if i in (2, 5, 8):
        cports += [((x, 9), 'U', 'out'), ((x, 17), 'D', 'out')]
add('协议核心', core, False, cports)

# 占格
occ = {}
problems = []
for n, u in units.items():
    for c in u['cells']:
        if not (0 <= c[0] < 70 and 0 <= c[1] < 70):
            problems.append(('出界', n, c))
        if c in occ:
            problems.append(('重叠', n, occ[c], c))
        occ[c] = n
# 通道
chan = set()
for n, u in units.items():
    for (c, d, io) in u['ports']:
        if io != 'out':
            continue
        nb = (c[0] + D[d][0], c[1] + D[d][1])
        m = occ.get(nb)
        if m is None:
            continue
        v = units[m]
        if (nb, OPP[d], 'in') in v['ports'] and (u['transport'] or v['transport']):
            chan.add((n, m))
# 预期通道（把带的逐格通道合成一段）
def chain(names):
    return {(names[i], names[i + 1]) for i in range(len(names) - 1)}
expected = set()
expected |= chain(A) | chain(B) | chain(R2)
expected |= {('取货口甲', A[0]), (A[-1], '准入口甲'), ('准入口甲', '分流器'),
             ('分流器', '汇流器甲'), ('分流器', '汇流器乙'),
             ('取货口乙', B[0]), (B[-1], '准入口乙'), ('准入口乙', '未设条件准入口'),
             ('未设条件准入口', '汇流器甲'), ('汇流器甲', R1[0]), (R1[0], '协议核心'),
             ('汇流器乙', R2[0]), (R2[-1], '协议核心')}
res = dict(problems=problems, belt_lengths=dict(甲=len(A), 乙=len(B)),
           extra_channels=sorted(chan - expected), missing_channels=sorted(expected - chan),
           channel_count=len(chan))
json.dump(res, open('witness_geometry.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))

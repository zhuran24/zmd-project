#!/usr/bin/env python3
"""核查B：拒绝性检验。对候选做小改动，确认两套编码都能报出。输出 核查B/变异/ 与 核查B/变异结果.json"""
import json, os, subprocess, copy

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '构造B', '候选布局.json')
OUT = os.path.join(HERE, '变异'); os.makedirs(OUT, exist_ok=True)
base = json.load(open(SRC))

def run(name, d):
    p = os.path.join(OUT, name + '.json')
    json.dump(d, open(p, 'w'), ensure_ascii=False)
    ra = os.path.join(OUT, name + '-主.json'); rb = os.path.join(OUT, name + '-副.json')
    subprocess.run(['python3', '-B', os.path.join(HERE, 'check_main.py'), p, ra], check=True, capture_output=True)
    subprocess.run(['python3', '-B', os.path.join(HERE, 'check_alt.py'), p, rb], check=True, capture_output=True)
    return json.load(open(ra)), json.load(open(rb))

res = {}
# 1. 把 (24,50) 的桥换成向右的带：H 轴进路仍通，但 KQ4→Q4 一路断
d = copy.deepcopy(base)
for t in d['layout']['transport']:
    if t['id'] == 'X_24_50':
        t.clear(); t.update({'id': 'X_24_50', 'x': 24, 'y': 50, 'type': 'belt', 'in_side': 2, 'out_side': 0})
a, b = run('桥换带', d)
res['桥换带'] = {'主-完成进路': a['完成进路数'], '副-完成进路': b['完成进路'], '主-问题类别': sorted({p['类别'] for p in a['问题']}),
               '副-倒追状态': b['倒追状态']}
# 2. 去掉一个供电桩
d = copy.deepcopy(base); d['layout']['power_poles'] = [p for p in d['layout']['power_poles'] if p['id'] != 'POWER928']
a, b = run('去桩', d)
res['去桩'] = {'主-已供电': a['已供电制造单位'], '副-已供电': b['供电制造单位']}
# 3. 在空矩形内放一格带子
d = copy.deepcopy(base); d['layout']['transport'].append({'id': 'Z1', 'x': 20, 'y': 20, 'type': 'belt', 'in_side': 2, 'out_side': 0})
a, b = run('矩形内放带', d)
res['矩形内放带'] = {'主-最大空矩形': a['最大空矩形(面积,短边)'], '副-最大空矩形': b['最大空矩形'],
                  '主-问题类别': sorted({p['类别'] for p in a['问题']})}
# 4. 在 B12 的一个空的取货口对面放一格带子（多出一条通道和断头）
d = copy.deepcopy(base)
occ = set()
L = d['layout']
for m in L['machines']:
    for x in range(m['x0'], m['x1'] + 1):
        for y in range(m['y0'], m['y1'] + 1): occ.add((x, y))
for o in L['warehouse_outlets'] + L['power_poles'] + [L['core']]:
    for x in range(o['x0'], o['x1'] + 1):
        for y in range(o['y0'], o['y1'] + 1): occ.add((x, y))
for t in L['transport']: occ.add((t['x'], t['y']))
m = [m for m in L['machines'] if m['id'] == 'B12'][0]
so = (m['Din'] + 2) % 4
DEL = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
cand = []
if so in (1, 3):
    y = m['y1'] if so == 1 else m['y0']
    cand = [(x + DEL[so][0], y + DEL[so][1]) for x in range(m['x0'], m['x1'] + 1)]
else:
    x = m['x1'] if so == 0 else m['x0']
    cand = [(x + DEL[so][0], y + DEL[so][1]) for y in range(m['y0'], m['y1'] + 1)]
cell = [c for c in cand if c not in occ and 0 <= c[0] < 70 and 0 <= c[1] < 70][0]
L['transport'].append({'id': 'Z2', 'x': cell[0], 'y': cell[1], 'type': 'belt', 'in_side': (so + 2) % 4, 'out_side': so})
a, b = run('多一格断头带', d)
res['多一格断头带'] = {'位置': cell, '主-重建通道': a['重建通道数'], '副-通道': b['通道数'], '主-问题类别': sorted({p['类别'] for p in a['问题']}),
                   '副-倒追状态': b['倒追状态']}
# 5. 把 KQ4→Q4 的一路改为进 Q3（交换终点名）：改 Q3、Q4 的 id，接法比对应报多余与缺
d = copy.deepcopy(base)
for mm in d['layout']['machines']:
    if mm['id'] == 'Q3': mm['id'] = 'Q4tmp'
for mm in d['layout']['machines']:
    if mm['id'] == 'Q4': mm['id'] = 'Q3'
for mm in d['layout']['machines']:
    if mm['id'] == 'Q4tmp': mm['id'] = 'Q4'
def ren(pr):
    if pr['unit'] == 'Q3': pr['unit'] = 'Q4'
    elif pr['unit'] == 'Q4': pr['unit'] = 'Q3'
for pc in d['design']['physical_channels']: ren(pc['from']); ren(pc['to'])
for lf in d['design']['logical_feeds']: ren(lf['from']); ren(lf['to'])
a, b = run('交换Q3Q4', d)
res['交换Q3Q4'] = {'主-多余': a['多余进路数'], '副-多': b['多'], '主-缺': a['缺进路数'], '副-缺': b['缺']}
json.dump(res, open(os.path.join(HERE, '变异结果.json'), 'w'), ensure_ascii=False, indent=1, default=str)
for k, v in res.items(): print(k, v)

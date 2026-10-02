#!/usr/bin/env python3
"""列出端口外侧被挡的来源与机器：挡住它的是哪个单位或基地边界。用法：python3 blockers.py 布局.json 输出.json"""
import json, sys
D = json.load(open(sys.argv[1])); L = D['layout']; N = 70
own = {}
def rect(u): return [(x, y) for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)]
for g in (L['machines'], L['warehouse_outlets'], L['power_poles'], [L['core']]):
    for u in g:
        for c in rect(u): own[c] = u['id']
def who(c):
    if not (0 <= c[0] < N and 0 <= c[1] < N): return '基地边界'
    return own.get(c)
def edge(b, s):
    x0, y0, x1, y1 = b
    if s == 0: return [(x1 + 1, y) for y in range(y0, y1 + 1)]
    if s == 2: return [(x0 - 1, y) for y in range(y0, y1 + 1)]
    if s == 1: return [(x, y1 + 1) for x in range(x0, x1 + 1)]
    return [(x, y0 - 1) for x in range(x0, x1 + 1)]
SN = {0: '右', 1: '上', 2: '左', 3: '下'}
res = {'来源端口被挡': [], '取货边全被挡': [], '存货边全被挡': []}
for o in L['warehouse_outlets']:
    c = (1, o['y0'] + 1) if o['Dout'] == 0 else (o['x0'] + 1, 1)
    if who(c): res['来源端口被挡'].append(f'{o["id"]}（{o["item"]}，占 x{o["x0"]}-{o["x1"]} y{o["y0"]}-{o["y1"]}）端口正对格 {c} 被 {who(c)} 占')
c = L['core']; b = (c['x0'], c['y0'], c['x1'], c['y1'])
for e in c['output_items']:
    cell = edge(b, e['side'])[e['offset']]
    if who(cell): res['来源端口被挡'].append(f'协议核心{SN[e["side"]]}边第{e["offset"]+1}格取货端口正对格 {cell} 被 {who(cell)} 占')
for m in L['machines']:
    b = (m['x0'], m['y0'], m['x1'], m['y1'])
    for key, s in (('取货边全被挡', (m['Din'] + 2) % 4), ('存货边全被挡', m['Din'])):
        cells = edge(b, s)
        ws = [who(x) for x in cells]
        if all(ws):
            res[key].append(f'{m["id"]}（{m["model"]}，x{m["x0"]}-{m["x1"]} y{m["y0"]}-{m["y1"]}，{SN[s]}边）外侧：' + '、'.join(sorted(set(ws))))
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
for k, v in res.items():
    print(k, len(v))
    for x in v: print('  ', x)

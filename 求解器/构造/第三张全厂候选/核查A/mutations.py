#!/usr/bin/env python3
"""拒绝性检验：对候选做几种已知错误的改动，看两套编码是否都能报出；另试一处 H6/Q6 等长的局部改法。
改动后的文件写在 变异/ 下，不改原候选。"""
import json, os, copy, subprocess, collections
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '构造A', '未通过候选.json')
base = json.load(open(SRC))
os.makedirs(os.path.join(HERE, '变异'), exist_ok=True)
occ = set()
L = base['layout']
for m in L['machines'] + L['warehouse_outlets'] + [L['core']] + L['power_poles']:
    for x in range(m['x0'], m['x1'] + 1):
        for y in range(m['y0'], m['y1'] + 1): occ.add((x, y))
for t in L['transport']: occ.add((t['x'], t['y']))

def run(name, cand):
    p = os.path.join(HERE, '变异', name + '.json'); json.dump(cand, open(p, 'w'), ensure_ascii=False)
    oa = os.path.join(HERE, '变异', name + '.主.json'); ob = os.path.join(HERE, '变异', name + '.副.json')
    env = dict(os.environ, CAND_PATH=p, OUT_PATH=oa)
    subprocess.run(['python3', '-B', os.path.join(HERE, 'check_main.py')], env=env, capture_output=True, check=True)
    env = dict(os.environ, CAND_PATH=p, OUT_PATH=ob)
    subprocess.run(['python3', '-B', os.path.join(HERE, 'check_alt.py')], env=env, capture_output=True, check=True)
    A = json.load(open(oa)); B = json.load(open(ob))
    return A, B

def summary(A, B):
    return {
        '主-问题类别': dict(collections.Counter(p[0] for p in A['problems'])),
        '主-完成进路': A['routes_complete'], '副-完成进路': B['routes'],
        '主-缺路': A['routes_missing_count'], '副-缺路': B['missing'],
        '主-接法外': len(A['routes_extra']), '副-接法外': len(B['extra']),
        '主-不在进路上节点': len(A['orphan_transport_nodes']), '副-不在进路上节点': len(B['nodes_not_on_route']),
        '主-断头分叉': len(A['transport_degree_anomalies']), '副-倒追断开等': len(B['issues']),
        '主-通道': A['channels_rebuilt'], '副-通道': B['channels'], '副-声明一致': B['decl_equal'],
        '主-无电': A['unpowered_machines'], '副-无电': B['unpowered'],
        '主-空矩形': A['max_empty_rect'], '副-空矩形': B['rect_hist'],
        '主-H6F4/Q6F4': [A['H6_F4_len'], A['Q6_F4_len']], '副-H6F4/Q6F4': [B['H6_F4'], B['Q6_F4']],
    }

results = {}
A0, B0 = run('原样', base)
results['原样'] = summary(A0, B0)

# M1 去掉一个供电桩
c = copy.deepcopy(base); gone = c['layout']['power_poles'].pop(0)
results['M1去掉供电桩%s' % gone['id']] = summary(*run('M1', c))

# M2 把一条进路中段的一格传送带存取边对调
c = copy.deepcopy(base)
BT = {(t['x'], t['y']): t for t in c['layout']['transport']}
r = next(r for r in A0['routes'] if len(r['cells']) >= 5 and BT[tuple(r['cells'][2])]['type'] == 'belt')
x, y = r['cells'][2]
t = BT[(x, y)]
t['in_side'], t['out_side'] = t['out_side'], t['in_side']
results['M2对调(%d,%d)传送带方向(%s→%s)' % (x, y, r['src'], r['dst'])] = summary(*run('M2', c))

# M3 把一座桥接器换成只走水平轴的传送带（同一格、同一 id）
c = copy.deepcopy(base)
b0 = A0['bridges'][0]
t = next(t for t in c['layout']['transport'] if (t['x'], t['y']) == tuple(b0['cell']))
tid = t['id']; t.clear()
t.update({'id': tid, 'x': b0['cell'][0], 'y': b0['cell'][1], 'type': 'belt', 'in_side': b0['H_in'][0], 'out_side': (b0['H_in'][0] + 2) % 4})
results['M3桥(%d,%d)换成水平传送带' % (t['x'], t['y'])] = summary(*run('M3', c))

# M4 在最大空矩形里放一格传送带（不接任何东西也照样占格）
c = copy.deepcopy(base)
c['layout']['transport'].append({'id': 'T66_66', 'x': 66, 'y': 66, 'type': 'belt', 'in_side': 2, 'out_side': 0})
results['M4空矩形内(66,66)加一格带'] = summary(*run('M4', c))

# M5 在某台机器取货端口外的空格加一格接出去的断头带
c = copy.deepcopy(base)
done = None
D = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
for m in L['machines']:
    s = (m['Din'] + 2) % 4
    xs = range(m['x0'], m['x1'] + 1); ys = range(m['y0'], m['y1'] + 1)
    edge = [(m['x1'], y) for y in ys] if s == 0 else [(x, m['y1']) for x in xs] if s == 1 else [(m['x0'], y) for y in ys] if s == 2 else [(x, m['y0']) for x in xs]
    for (ex, ey) in edge:
        n = (ex + D[s][0], ey + D[s][1])
        if 0 <= n[0] < 70 and 0 <= n[1] < 70 and n not in occ:
            done = (m['id'], n, s); break
    if done: break
mid, n, s = done
c['layout']['transport'].append({'id': 'TX', 'x': n[0], 'y': n[1], 'type': 'belt', 'in_side': (s + 2) % 4, 'out_side': s})
c['design']['physical_channels'].append({'id': 'PCX', 'from': {'unit': mid, 'side': s, 'offset': (n[1] - next(mm for mm in L['machines'] if mm['id'] == mid)['y0']) if s in (0, 2) else (n[0] - next(mm for mm in L['machines'] if mm['id'] == mid)['x0'])}, 'to': {'unit': 'TX', 'side': (s + 2) % 4, 'offset': 0}, 'allowed_items': ['钢块']})
results['M5在%s取货端口外(%d,%d)加断头带' % (mid, n[0], n[1])] = summary(*run('M5', c))

# M6 交换 B1 与 B2 的身份（位置不动）
c = copy.deepcopy(base)
for m in c['layout']['machines']:
    if m['id'] == 'B1': m['id'] = 'B2tmp'
for m in c['layout']['machines']:
    if m['id'] == 'B2': m['id'] = 'B1'
for m in c['layout']['machines']:
    if m['id'] == 'B2tmp': m['id'] = 'B2'
results['M6交换B1、B2身份'] = summary(*run('M6', c))

# F1 H6/Q6 等长的局部改法：(30,15) 改桥接器，两路在此交叉，各 2 格
c = copy.deepcopy(base)
T = {(t['x'], t['y']): t for t in c['layout']['transport']}
before = {k: dict(T[k]) for k in [(31, 15), (31, 16), (30, 16), (30, 15)]}
T[(31, 15)].update({'in_side': 0, 'out_side': 2})
t15 = T[(30, 15)]; tid = t15['id']; t15.clear(); t15.update({'id': tid, 'x': 30, 'y': 15, 'type': 'bridge', 'H_in': 0, 'V_in': 3})
T[(30, 16)].update({'in_side': 3, 'out_side': 2})
c['layout']['transport'] = [t for t in c['layout']['transport'] if (t['x'], t['y']) != (31, 16)]
A1, B1 = run('F1', c)
sm = summary(A1, B1)
sm['改前四格'] = {str(k): v for k, v in before.items()}
sm['主-除通道声明与缺路外的问题'] = [p for p in A1['problems'] if p[0] not in ('通道声明', 'S2接法')]
results['F1 H6/Q6局部改法（(30,15)改桥）'] = sm
json.dump(results, open(os.path.join(HERE, '变异结果.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in results.items():
    print(k)
    print('   ', json.dumps(v, ensure_ascii=False))

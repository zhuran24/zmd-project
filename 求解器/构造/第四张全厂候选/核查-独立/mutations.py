#!/usr/bin/env python3
"""拒绝性检验：对布局做 8 种改动，两套编码都应报出问题。用法：python3 mutations.py 布局.json 变异目录 输出.json"""
import json, sys, copy, subprocess, os
SRC, DIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
base = json.load(open(SRC))
here = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
def run(path):
    a = path.replace('.json', '-一.json'); b = path.replace('.json', '-二.json')
    subprocess.run(['python3', f'{here}/check_main.py', path, a], check=True, capture_output=True, env=env)
    subprocess.run(['python3', f'{here}/check_alt.py', path, b], check=True, capture_output=True, env=env)
    return json.load(open(a)), json.load(open(b))
def sig1(r):
    return dict(问题=sorted(p['类别'] + '：' + p['说明'][:80] for p in r['问题']))
def sig2(r):
    keys = ['占格冲突', '倒追得到的完整进路', '共用物品格', '多余通道', '不在进路上的传送带', '未用桥轴有通道',
            '同一进路过两轴的桥', '接法外或超额', '缺路条数', '无供电', '尺寸错', '最大空矩形', '重建通道数']
    return {k: r[k] for k in keys}
b1, b2 = run(SRC) if False else (json.load(open(f'{here}/编码一结果.json')), json.load(open(f'{here}/编码二结果.json')))
S1, S2 = sig1(b1), sig2(b2)
muts = {}
def mk(name, f):
    d = copy.deepcopy(base); f(d); muts[name] = d
L = 'layout'
mk('去掉一个供电桩', lambda d: d[L]['power_poles'].pop(0))
def flip(d):
    for t in d[L]['transport']:
        if t['type'] == 'belt' and t['id'] == 'X59_1':
            t['in_side'], t['out_side'] = t['out_side'], t['in_side']
mk('对调一格传送带方向', flip)
def br2belt(d):
    for t in d[L]['transport']:
        if t['id'] == 'X1_44':
            t.clear(); t.update({'id': 'X1_44', 'x': 1, 'y': 44, 'type': 'belt', 'in_side': 2, 'out_side': 0})
mk('桥接器换成传送带', br2belt)
mk('空矩形里放一格传送带', lambda d: d[L]['transport'].append({'id': 'Z66_66', 'x': 66, 'y': 66, 'type': 'belt', 'in_side': 2, 'out_side': 0}))
mk('T1取货端口外加一格断头带', lambda d: d[L]['transport'].append({'id': 'Z58_5', 'x': 58, 'y': 5, 'type': 'belt', 'in_side': 3, 'out_side': 1}))
def swap(d):
    for m in d[L]['machines']:
        if m['id'] == 'B1': m['id'] = 'TMPB'
    for m in d[L]['machines']:
        if m['id'] == 'B2': m['id'] = 'B1'
    for m in d[L]['machines']:
        if m['id'] == 'TMPB': m['id'] = 'B2'
mk('交换B1与B2身份', swap)
def splitter(d):
    for t in d[L]['transport']:
        if t['id'] == 'X59_1':
            t.pop('out_side'); t['type'] = 'splitter'
mk('一格传送带换成分流器', splitter)
def grow(d):
    for m in d[L]['machines']:
        if m['id'] == 'E1':
            if m['Din'] in (1, 3): m['x1'] = m['x0'] + 3; m['y1'] = m['y0'] + 5
            else: m['x1'] = m['x0'] + 5; m['y1'] = m['y0'] + 3
mk('封装机E1旋转而不改存取边', grow)
res = {}
for name, d in muts.items():
    p = os.path.join(DIR, name + '.json')
    json.dump(d, open(p, 'w'), ensure_ascii=False)
    try:
        r1, r2 = run(p)
        c1 = sig1(r1) != S1; c2 = sig2(r2) != S2
        new1 = sorted(set(sig1(r1)['问题']) - set(S1['问题']))[:4]
        diff2 = [k for k in S2 if sig2(r2)[k] != S2[k]]
        res[name] = dict(编码一报出=c1, 编码二报出=c2, 编码一新问题=new1, 编码二变化项=diff2)
    except subprocess.CalledProcessError as e:
        res[name] = dict(编码一报出='程序异常', 编码二报出='程序异常', 错误=e.stderr.decode()[-300:])
json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1)
for k, v in res.items(): print(k, v)

#!/usr/bin/env python3
"""拒绝性检验：对布局做若干处改动，两套编码都应报出比原布局多的问题。
用法：python3 mutations.py <布局.json> <输出.json>
变异文件写在本目录的 变异/ 下。"""
import json, sys, os, copy, subprocess

SRC = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, '变异')
os.makedirs(MD, exist_ok=True)
base = json.load(open(SRC))


def run(path, tag):
    o1 = os.path.join(MD, tag + '.主.json')
    o2 = os.path.join(MD, tag + '.副.json')
    subprocess.run([sys.executable, '-B', os.path.join(HERE, 'check_main.py'), path, o1], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, '-B', os.path.join(HERE, 'check_alt.py'), path, o2], check=True,
                   stdout=subprocess.DEVNULL)
    a = json.load(open(o1))
    b = json.load(open(o2))
    sa = dict(问题=len(a['问题']), 已通=a['接法']['已通（按接法计）'], 接法外=a['接法']['接法外'])
    sb = dict(问题=len(b['issues']) + len(b['other_channels']) + len(b['bad_traces']) + len(b['shared_cells'])
              + len(b['unpowered']) + len(b['bridge_decl_mismatch']) + len(b['extra'])
              + (0 if b['H6F4'] == b['Q6F4'] and len(b['H6F4']) == 1 else 1)
              + len(b['unused_transport_cells']),
              已通=b['matched'])
    return sa, sb, a, b


sa0, sb0, a0, b0 = run(SRC, '原布局')
L0 = base['layout']


def find_t(x, y):
    for t in L0['transport']:
        if (t['x'], t['y']) == (x, y):
            return t


muts = []


def m_pole(d):
    d['layout']['power_poles'] = [p for p in d['layout']['power_poles'] if p['id'] != 'POWER17']
    return '去掉覆盖台数最多的供电桩 POWER17'


def m_flip(d):
    r = a0['已通进路'][0]
    x, y, _ = r['运输格'][0]
    for t in d['layout']['transport']:
        if (t['x'], t['y']) == (x, y):
            t['in_side'], t['out_side'] = t['out_side'], t['in_side']
    return '对调 %s→%s 首格 (%d,%d) 传送带的方向' % (r['源'], r['汇'], x, y)


def m_bridge2belt(d):
    for t in d['layout']['transport']:
        if t['id'] == 'T38_52':
            t.pop('H_in'); t.pop('V_in')
            t.update(type='belt', in_side=2, out_side=0)
    return '把 (38,52) 桥接器换成向右的传送带'


def m_rect(d):
    d['layout']['transport'].append({'id': 'T65_16', 'x': 65, 'y': 16, 'type': 'belt', 'in_side': 2, 'out_side': 0})
    return '在声明空矩形内 (65,16) 放一格传送带'


def m_extra(d):
    # 在某台机器空着的取货端口外放一格带，带的存货边朝机器
    occ = set()
    for k in ('machines', 'warehouse_outlets', 'power_poles'):
        for u in d['layout'][k]:
            occ |= {(x, y) for x in range(u['x0'], u['x1'] + 1) for y in range(u['y0'], u['y1'] + 1)}
    c = d['layout']['core']
    occ |= {(x, y) for x in range(c['x0'], c['x1'] + 1) for y in range(c['y0'], c['y1'] + 1)}
    occ |= {(t['x'], t['y']) for t in d['layout']['transport']}
    for m in d['layout']['machines']:
        if m['id'] != 'S1':
            continue
        s = (m['Din'] + 2) % 4
        DX = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
        if s in (1, 3):
            y = m['y1'] if s == 1 else m['y0']
            cells = [(x, y) for x in range(m['x0'], m['x1'] + 1)]
        else:
            x = m['x1'] if s == 0 else m['x0']
            cells = [(x, y) for y in range(m['y0'], m['y1'] + 1)]
        for (x, y) in cells:
            o = (x + DX[s][0], y + DX[s][1])
            if o not in occ:
                d['layout']['transport'].append({'id': 'TX%d_%d' % o, 'x': o[0], 'y': o[1], 'type': 'belt',
                                                 'in_side': (s + 2) % 4, 'out_side': s})
                return '在 S1 空着的取货端口外 %s 加一格传送带' % (o,)
    return '未施加'


def m_swap(d):
    for m in d['layout']['machines']:
        if m['id'] == 'B1':
            m['id'] = 'B2'
        elif m['id'] == 'B2':
            m['id'] = 'B1'
    return '交换 B1 与 B2 的身份'


def m_hin(d):
    for t in d['layout']['transport']:
        if t['id'] == 'T42_32':
            t['H_in'] = 2 if t['H_in'] == 0 else 0
    return '改 (42,32) 桥接器 H_in 声明'


def m_outlet(d):
    for o in d['layout']['warehouse_outlets']:
        if o['id'] == 'WFE1':
            o['y0'] = o['y1'] = 1
    return '把 WFE1 从下边界抬高一格'


def m_core(d):
    d['layout']['core']['output_items'][0]['item'] = '蓝铁矿'
    return '把协议核心一个取货端口改设蓝铁矿'


def m_eq(d):
    for m in d['layout']['machines']:
        if m['id'] == 'H6':
            m['id'] = 'H5'
        elif m['id'] == 'H5':
            m['id'] = 'H6'
    return '交换 H5 与 H6 的身份（H6→F4 不再是 1 格的那一路）'


def m_overlap(d):
    p = d['layout']['power_poles'][0]
    m = d['layout']['machines'][0]
    p['x0'], p['y0'] = m['x0'], m['y0']
    p['x1'], p['y1'] = m['x0'] + 1, m['y0'] + 1
    return '把一个供电桩挪到 RF1 机身上（重叠）'


res = {'原布局': dict(编码一=sa0, 编码二=sb0)}
for f in (m_pole, m_flip, m_bridge2belt, m_rect, m_extra, m_swap, m_hin, m_outlet, m_core, m_eq, m_overlap):
    d = copy.deepcopy(base)
    desc = f(d)
    tag = f.__name__
    p = os.path.join(MD, tag + '.json')
    json.dump(d, open(p, 'w'), ensure_ascii=False)
    sa, sb, a, b = run(p, tag)
    rej1 = sa['问题'] > sa0['问题'] or sa['已通'] < sa0['已通'] or sa['接法外'] > sa0['接法外']
    rej2 = sb['问题'] > sb0['问题'] or sb['已通'] < sb0['已通']
    newp = [x['说明'] for x in a['问题'] if x not in a0['问题']][:4]
    res[tag] = dict(改动=desc, 编码一=sa, 编码二=sb, 编码一拒绝=rej1, 编码二拒绝=rej2, 编码一新问题示例=newp)
    print(tag, desc, '编码一', rej1, sa, '编码二', rej2, sb)
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)

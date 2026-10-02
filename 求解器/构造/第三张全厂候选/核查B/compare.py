#!/usr/bin/env python3
"""核查B：主、副两套编码的关键数字互核，并记录输入与脚本指纹。输出 核查B/互核.json"""
import json, os, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, '结果-主.json')))
B = json.load(open(os.path.join(HERE, '结果-副.json')))
K = json.load(open(os.path.join(HERE, '结果-卡点.json')))

pairs = [
    ('候选SHA256', A['候选SHA256'], B['sha256']),
    ('总占格', A['总占格'], B['占格']),
    ('空格', A['空格'], B['空格']),
    ('机身占格', A['机身占格'], B['机身占格']),
    ('重建通道数', A['重建通道数'], B['通道去重数']),
    ('完成进路数', A['完成进路数'], B['完成进路']),
    ('前向通道数', A['前向通道数'], B['进路通道合计']),
    ('完成进路物品格', A['完成进路物品格总数'], B['进路物品格合计']),
    ('非前向通道数', len(A['相邻桥逆向通道']) + len(A['其他非前向通道']), len(B['不在进路上的通道'])),
    ('S2期望进路数', A['S2期望进路数'], B['S2期望总数']),
    ('缺进路数', A['缺进路数'], B['缺']),
    ('多余进路数', A['多余进路数'], B['多']),
    ('矿路完成数', A['矿路完成数'], B['矿路完成']),
    ('成品入库进路数', A['成品入库进路数'], B['成品入库']),
    ('已供电制造单位', A['已供电制造单位'], B['供电制造单位']),
    ('H6到F4', A['H6到F4物品格'], B['H6F4']),
    ('Q6到F4', A['Q6到F4物品格'], B['Q6F4']),
    ('最大空矩形', list(A['最大空矩形(面积,短边)']), list(B['最大空矩形'])),
    ('最大空矩形位置', [list(x) for x in A['最大空矩形全部位置']], [list(x) for x in B['位置']]),
]
rows = [{'项': n, '编码一': a, '编码二': b, '一致': a == b} for n, a, b in pairs]
extra_checks = {'副-重叠格': B['重叠格'], '副-共用物品格': B['被多条进路共用的物品格'],
                '副-倒追状态': B['倒追状态']}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
files = {
    '候选布局.json': os.path.join(HERE, '..', '构造B', '候选布局.json'),
    '规则快照': os.path.join(ROOT, '求解器/候选约束轮次/第107-109轮/前提快照/《明日方舟：终末地》游戏规则.txt'),
    '求解任务快照': os.path.join(ROOT, '求解器/候选约束轮次/第107-109轮/前提快照/求解任务.txt'),
    '求解约束快照': os.path.join(ROOT, '求解器/候选约束轮次/第107-109轮/前提快照/求解约束.txt'),
    '求解充分条件快照': os.path.join(ROOT, '求解器/候选约束轮次/第107-109轮/前提快照/求解充分条件.txt'),
    '临时规则': os.path.join(ROOT, '求解器/候选约束轮次/第107-109轮/临时规则.md'),
    'S2推导': os.path.join(ROOT, '求解器/候选约束轮次/第98-100轮/推导98S2.md'),
    'S2B推导': os.path.join(ROOT, '求解器/候选约束轮次/第107-109轮/推导107S2B.md'),
}
for f in ('check_main.py', 'check_alt.py', 'obstruct.py', 'mutations.py', 'compare.py', 'run_all.sh'):
    files[f] = os.path.join(HERE, f)
out = {'互核': rows, '全部一致': all(r['一致'] for r in rows), '副程序附带': extra_checks,
       '卡点分类': {k: K[k]['分类'] for k in ('不保留空矩形', '保留声明空矩形')},
       '端口不足台数(不保留/保留空矩形)': [len(K['端口不足的单位']), len(K['端口不足的单位-保留空矩形'])],
       '指纹': {k: sha(v) for k, v in files.items()}}
json.dump(out, open(os.path.join(HERE, '互核.json'), 'w'), ensure_ascii=False, indent=1)
for r in rows: print(('OK ' if r['一致'] else 'XX ') + r['项'], r['编码一'], r['编码二'])
print('全部一致', out['全部一致'])

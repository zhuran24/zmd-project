#!/usr/bin/env python3
"""两套编码的结果互核。用法：python3 cross.py 结果-主.json 结果-副.json 互核.json"""
import json, sys
from collections import Counter
A = json.load(open(sys.argv[1])); B = json.load(open(sys.argv[2]))
def na(s):
    return s.replace('仓库取货口:', '矿:') if s.startswith('仓库取货口:') else ('核心:源矿' if s == 'CORE' else s)
ma = Counter()
for m in A['接法']['缺路清单']:
    ma[(na(m['源']), m['汇'])] += m['缺条数']
mb = Counter(tuple(x) for x in B['missing'])
ra = Counter((r['源'], r['汇'], r['物品'], r['格数']) for r in A['已通进路'])
rb = Counter(tuple(x) for x in B['route_list'])
rows = {
 '通道数': (A['通道']['重建'], B['channels']),
 '逆向通道数': (A['通道']['相邻桥逆向'], len(B['reverse'])),
 '多余通道数': (A['通道']['多余'], len(B['other_channels'])),
 '进路数': (A['进路']['重建条数'], B['routes']),
 '运输物品格': (A['进路']['运输物品格'], B['item_cells']),
 '共用物品格': (A['进路']['被共用物品格'], len(B['shared_cells'])),
 '按接法已通': (A['接法']['已通（按接法计）'], B['matched']),
 '接法外进路': (A['接法']['接法外'], len(B['extra'])),
 '缺路清单相同': (True, ma == mb),
 '已通进路逐条（源、汇、物品、格数）相同': (True, ra == rb),
 'H6→F4': (A['等长']['H6→F4'], B['H6F4']),
 'Q6→F4': (A['等长']['Q6→F4'], B['Q6F4']),
 '无电': (A['供电']['无电制造单位'], B['unpowered']),
 '空矩形面积': (A['空矩形']['面积'], B['empty_rect']['area']),
 '空矩形短边': (A['空矩形']['短边'], B['empty_rect']['short']),
 '空矩形位置': (A['空矩形']['重算最优'], [list(x) for x in B['empty_rect']['where']]),
}
out = {k: {'编码一': a, '编码二': b, '一致': a == b} for k, (a, b) in rows.items()}
json.dump(out, open(sys.argv[3], 'w'), ensure_ascii=False, indent=1)
bad = [k for k, v in out.items() if not v['一致']]
print('互核项', len(out), '不一致', bad)

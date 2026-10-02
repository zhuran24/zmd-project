#!/usr/bin/env python3
"""逐台统计：每台制造单位按 S2 第 2 节应有的来路、去路条数，与候选实际接通的条数。读 结果-主.json、结果-可达.json，写 结果-逐台.json。"""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, '结果-主.json')))
R = json.load(open(os.path.join(HERE, '结果-可达.json')))
C = json.load(open(os.path.join(HERE, '..', '构造A', '未通过候选.json')))
imp = collections.Counter(tuple(x) for x in R['布不出清单(同号)'])
def key(s): return s if not (s.startswith('矿口') or s.startswith('核心')) else s
built = collections.Counter()
for r in A['routes']:
    s = r['src']
    if s.startswith('WFE'): s = '矿口:蓝铁矿'
    elif s.startswith('WO'): s = '矿口:源矿'
    elif s == 'CORE': s = '核心:源矿'
    built[(s, r['dst'])] += 1
miss = collections.Counter({(s, d): n for s, d, n in A['routes_missing']})
exp = built + miss
rows = {}
for m in C['layout']['machines'] + [{'id': 'CORE'}]:
    u = m['id']
    ei = sum(v for (s, d), v in exp.items() if d == u); bi = sum(v for (s, d), v in built.items() if d == u)
    eo = sum(v for (s, d), v in exp.items() if s == u); bo = sum(v for (s, d), v in built.items() if s == u)
    ii = sum(v for (s, d), v in imp.items() if d == u); io = sum(v for (s, d), v in imp.items() if s == u)
    rows[u] = {'来路应有': ei, '来路接通': bi, '来路布不出': ii, '去路应有': eo, '去路接通': bo, '去路布不出': io}
full = [u for u, r in rows.items() if r['来路应有'] == r['来路接通'] and r['去路应有'] == r['去路接通']]
none = [u for u, r in rows.items() if r['来路接通'] == 0 and r['去路接通'] == 0]
out = {'接法齐全的单位数': len(full), '接法齐全的单位': full, '一条都没接通的单位': none,
       '缺至少一条且其中有布不出的单位数': sum(1 for r in rows.values() if r['来路布不出'] + r['去路布不出'] > 0),
       '逐台': rows}
json.dump(out, open(os.path.join(HERE, '结果-逐台.json'), 'w'), ensure_ascii=False, indent=1)
print(len(full), len(none), out['缺至少一条且其中有布不出的单位数'])
print(none)
print('CORE', rows['CORE'])

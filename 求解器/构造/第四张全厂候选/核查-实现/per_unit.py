#!/usr/bin/env python3
"""逐台统计：每台制造单位及协议核心的来路、去路是否齐全；仓库取货口用了几个。
用法：python3 per_unit.py 结果-主.json 结果-可达.json 结果-逐台.json"""
import json, sys
from collections import Counter
r = json.load(open(sys.argv[1])); q = json.load(open(sys.argv[2]))
built = [(x['源'], x['汇']) for x in r['已通进路']]
miss = []
for m in r['接法']['缺路清单']:
    miss += [(m['源'], m['汇'])] * m['缺条数']
names = set(t for _, t in built + miss) | set(s for s, _ in built + miss)
names = {n for n in names if not n.startswith('W') and not n.startswith('仓库')}
rows = {}
for n in sorted(names):
    bi = sum(1 for s, t in built if t == n); bo = sum(1 for s, t in built if s == n)
    mi = sum(1 for s, t in miss if t == n); mo = sum(1 for s, t in miss if s == n)
    rows[n] = dict(来路已通=bi, 来路缺=mi, 去路已通=bo, 去路缺=mo)
full = [n for n, v in rows.items() if v['来路缺'] == 0 and v['去路缺'] == 0]
none = [n for n, v in rows.items() if v['来路已通'] == 0 and v['去路已通'] == 0]
outl = sorted({s for s, t in built if s.startswith('W')})
# 整条存货边或取货边外侧在基地外
edge = []
for c in q['端口容量不足单位']:
    if all(x[2] == '界外' for x in c['取货边外侧']):
        edge.append(dict(单位=c['单位'], 占格=c['占格'], 贴界的边='取货边'))
    if c['存货边外侧'] != '略' and all(x[2] == '界外' for x in c['存货边外侧']):
        edge.append(dict(单位=c['单位'], 占格=c['占格'], 贴界的边='存货边'))
out = dict(单位数=len(rows), 来去齐全=len(full), 一条都没通=none, 已用仓库取货口=len(outl), 已用取货口=outl,
           端口边整条在基地外=edge, 逐台=rows)
json.dump(out, open(sys.argv[3], 'w'), ensure_ascii=False, indent=1)
print('单位', len(rows), '齐全', len(full), '全无', none, '取货口已用', len(outl))
print('贴界', edge)

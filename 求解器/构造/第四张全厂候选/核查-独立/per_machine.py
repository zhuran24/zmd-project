#!/usr/bin/env python3
"""逐台统计：每台机器（及协议核心）要求的来路、去路中缺几条。用法：python3 per_machine.py 编码一结果.json 输出.json"""
import json, sys, collections
a = json.load(open(sys.argv[1]))
miss_in = collections.Counter(); miss_out = collections.Counter()
for k, v in a['缺路'].items():
    s, t = k.split('->')
    miss_in[t] += v
    if not s.startswith('OUTLET') and s != 'COREPORT': miss_out[s] += v
ids = set(miss_in) | set(miss_out)
rows = {u: dict(缺来路=miss_in[u], 缺去路=miss_out[u]) for u in sorted(ids)}
res = dict(有缺路的单位数=len(ids), 逐台=rows)
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
print(len(ids)); print(rows)

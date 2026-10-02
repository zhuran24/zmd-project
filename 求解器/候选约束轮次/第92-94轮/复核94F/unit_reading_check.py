#!/usr/bin/env python3
"""复核 94F：桥接器按整个单位读（第 31 行）时，没有「两轴都有元件来货」的网络里出现的差别，是否都来自「两轴都有来货（含非运输单位）」。
用法：python3 unit_reading_check.py <起始种子> <终止种子> <输出 json>（与 order_test.py 同样的网络与先后）"""
import json, random, sys
from genp import gen, features
from simp import Net
from order_test import run
from simp import default_orders, rank_orders
s0, s1, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
res = {'checked': 0, 'diff': 0, 'diff_with_two_axes_fed': 0, 'diff_without': []}
for seed in range(s0, s1):
    d = gen(seed)
    f = features(d)
    if f['shared_bridge']:
        continue
    def orders(net, seed=seed):
        rng = random.Random(seed * 7919 + 1)
        os = [rank_orders(net)]
        for _ in range(7):
            os.append(default_orders(net, rng))
        return os
    res['checked'] += 1
    if run(d, 'eager', 'unit', orders, 400) is not None:
        res['diff'] += 1
        if f['shared_bridge_any']:
            res['diff_with_two_axes_fed'] += 1
        else:
            res['diff_without'].append(seed)
json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
print(res)

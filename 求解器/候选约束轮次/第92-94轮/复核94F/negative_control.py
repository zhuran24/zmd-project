#!/usr/bin/env python3
"""复核 94F：反面对照（违反「往它送货的非运输单位至多一个」）：两个仓库取货口直接往同一个汇流器送，汇流器 -> 一段带 -> 收货侧。
换两个取货口的判定先后，两套编码各跑 400 步，记各取货口送出件数。"""
import json, sys
from simp import Net, World
from simq import Q
U = {'S1': {'type': 'src', 'kinds': ['o1']}, 'S2': {'type': 'src', 'kinds': ['o2']}, 'H': {'type': 'mer'},
     'b': {'type': 'seg', 'len': 3}, 'K': {'type': 'sink', 'open': ('always',)}}
C = [['S1', 'H', 0], ['S2', 'H', 1], ['H', 'b', 2], ['b', 'K', 3]]
d = {'units': U, 'chans': C, 'init': {}}
res = {}
for no in (['S1', 'S2', 'K'], ['S2', 'S1', 'K']):
    net = Net(U, C); w = World(net, {}); q = Q(d)
    eo = sorted(net.elems, key=lambda e: net.layer[e])
    for _ in range(400):
        w.step(eo, no); q.step(eo, no)
    kinds = [k for _, k in w.got['K']]
    res['先后 ' + '>'.join(no[:2])] = {'o1': kinds.count('o1'), 'o2': kinds.count('o2'), '编码丁收件': q.recv[q.idx['K']]}
json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
print(res)

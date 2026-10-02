#!/usr/bin/env python3
"""反面对照：去掉「至多一个非运输单位往同一运输物品格送货」这一前提，判定先后就会改变结果。
两台仓库取货口（设不同物品）直接往同一个汇流器送，汇流器再经一段传送带进协议核心。
非运输单位之间的判定先后不同，汇流器收到的物品序列不同。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from stepsim import Net, Sim

units = {
    'S1': dict(type='src', kinds=['a']), 'S2': dict(type='src', kinds=['b']),
    'H': dict(type='merger'), 'B': dict(type='belt', length=2),
    'K': dict(type='sink', open=lambda t: True),
}
ch = [('S1', 'H', 0), ('S2', 'H', 1), ('H', 'B', 2), ('B', 'K', 3)]
net = Net(units, ch, strict=False)
out = {}
for name, order in [('S1先', ['B', 'H', 'S1', 'S2']), ('S2先', ['B', 'H', 'S2', 'S1'])]:
    # 层数：B=1，H=2；元件按层数排
    order = sorted(['B', 'H'], key=lambda e: net.layer[e]) + order[2:]
    sim = Sim(net, {}, order=order)
    for _ in range(400):
        sim.step()
    got = sim.sink_got['K']
    out[name] = dict(first=[k for _, k in got[:12]], counts={k: sum(1 for _, x in got if x == k) for k in 'ab'})
print(json.dumps(out, ensure_ascii=False))

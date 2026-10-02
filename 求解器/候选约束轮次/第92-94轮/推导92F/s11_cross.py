#!/usr/bin/env python3
"""整厂接法（S11）上的两项核对，负载远高于随机小网络：
  一、编码甲换 4 种判定先后（同层元件之间、非运输单位之间随机），逐步比对整个状态；
  二、同一网络、同一起态（放种后）在编码乙（sim2，只在本脚本里补已知错 2）里跑，比对协议核心逐步收件序列。
用法：python3 s11_cross.py SEED_FROM SEED_TO STEPS
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import order_check as oc          # noqa: E402  （编码乙的搭建与 sim2 补丁）
import s11_sim as s11             # noqa: E402
from stepsim import Net, Sim      # noqa: E402


def desc_of(seed):
    U, channels, info = s11.build(seed, lambda t: True, core_ports=False)   # sim2 的 Source 不分端口设物品，这里 52 条各算一个取货口
    units = {}
    for u, d in U.items():
        d = dict(d)
        if d['type'] == 'sink':
            d.pop('open')
            d['spec'] = ['always']
        units[u] = d
    init = dict(cells={}, slots={}, outslot={}, cache={}, run={}, cursor={}, gate={})
    for (C, A, B, K, p) in info['units']:
        init['slots'][A] = [[f'{p}_seed', 50]]
        init['slots'][C] = [[f'{p}_plant', 50]]
    return dict(units=units, channels=[list(c) for c in channels], init=init), info


def main():
    a, b, steps = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    res = dict(nets=0, order_mismatch=[], ab_mismatch=[], steps=steps, receipts=[])
    for seed in range(a, b):
        desc, info = desc_of(seed)
        net = oc.build_a(desc)
        base = None
        for k in range(4):
            sim = Sim(net, json.loads(json.dumps(desc['init'])), order_seed=500 + 31 * seed + k)
            snaps = []
            for _ in range(steps):
                sim.step()
                snaps.append(sim.snapshot())
            if base is None:
                base, base_sim = snaps, sim
            elif snaps != base:
                i = next(j for j in range(steps) if snaps[j] != base[j])
                res['order_mismatch'].append(dict(seed=seed, order=k, first_step=i))
                break
        w, by, _ = oc.run_b(desc, order_seed=900 + seed, steps=steps)
        ea = list(base_sim.sink_got['core'])
        eb = [(t, k) for t, k in by['core'].received]
        if ea != eb:
            n = next((j for j in range(min(len(ea), len(eb))) if ea[j] != eb[j]), min(len(ea), len(eb)))
            res['ab_mismatch'].append(dict(seed=seed, first_diff=n, la=len(ea), lb=len(eb)))
        res['receipts'].append(dict(seed=seed, n=len(ea), BAT=sum(1 for _, k in ea if k == 'BAT'),
                                    CAP=sum(1 for _, k in ea if k == 'CAP')))
        res['nets'] += 1
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()

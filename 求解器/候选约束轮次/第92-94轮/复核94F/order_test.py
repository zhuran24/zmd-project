#!/usr/bin/env python3
"""复核 94F：换同层元件之间、非运输单位之间的判定先后，逐步比对整个状态（编码丙）。

用法：python3 order_test.py <起始种子> <网络数> <步数> <每网先后数> <输出 json>
对每个网络跑四种读法组合：settle ∈ {eager, judge} × bridge_group ∈ {axis, unit}。
记每种组合下有差别的网络数，并按网络特征（死路多格带段、桥接器两轴都有元件来货）分类。
"""
import json
import random
import sys

from genp import gen, features
from simp import Net, World, default_orders, rank_orders


def run(desc, settle, bg, orders, steps, trigger='first'):
    net = Net(desc['units'], desc['chans'], bridge_group=bg)
    trajs = []
    for eo, no in orders(net):
        w = World(net, desc['init'], settle=settle, trigger=trigger)
        tr = []
        for _ in range(steps):
            w.step(eo, no)
            tr.append(hash(w.snapshot()))
        trajs.append(tr)
    first = trajs[0]
    diff_at = None
    for tr in trajs[1:]:
        for k, (a, b) in enumerate(zip(first, tr)):
            if a != b:
                diff_at = k if diff_at is None else min(diff_at, k)
                break
    return diff_at


def main():
    s0, n, steps, k, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    combos = [('eager', 'axis'), ('judge', 'axis'), ('eager', 'unit'), ('judge', 'unit')]
    if len(sys.argv) > 6 and sys.argv[6] == 'sender':
        combos = [('eager', 'axis'), ('judge', 'axis')]
    trig = sys.argv[6] if len(sys.argv) > 6 else 'first'
    res = {f'{a}/{b}': {'nets': 0, 'diff': 0, 'diff_by_feat': {}, 'examples': []} for a, b in combos}
    feat_count = {}
    for seed in range(s0, s0 + n):
        desc = gen(seed)
        f = features(desc)
        fk = f"dead_multi={int(f['dead_multi'])},shared_bridge={int(f['shared_bridge'])}"
        feat_count[fk] = feat_count.get(fk, 0) + 1
        for a, b in combos:
            def orders(net, seed=seed):
                rng = random.Random(seed * 7919 + 1)
                os = [rank_orders(net)]
                for _ in range(k - 1):
                    os.append(default_orders(net, rng))
                return os
            d = run(desc, a, b, orders, steps, trig)
            r = res[f'{a}/{b}']
            r['nets'] += 1
            if d is not None:
                r['diff'] += 1
                r['diff_by_feat'][fk] = r['diff_by_feat'].get(fk, 0) + 1
                if len(r['examples']) < 5:
                    r['examples'].append({'seed': seed, 'first_diff_step': d})
    json.dump({'trigger': trig, 'seeds': [s0, s0 + n], 'steps': steps, 'orders_per_net': k, 'feature_count': feat_count,
               'results': res}, open(out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'feature_count': feat_count, 'results': {c: (v['nets'], v['diff'], v['diff_by_feat'])
                                                               for c, v in res.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()

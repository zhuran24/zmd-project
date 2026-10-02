#!/usr/bin/env python3
"""复核 94F：编码丙（simp）与编码丁（simq）在同一网络、同一判定先后下逐步比对状态摘要。

用法：python3 cross_pq.py <起始种子> <网络数> <步数> <输出 json>
"""
import json
import random
import sys

from genp import gen
from simp import Net, World, default_orders, rank_orders
from simq import Q, canon_p


def main():
    s0, n, steps, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    combos = [('eager', 'axis'), ('judge', 'axis'), ('eager', 'unit'), ('judge', 'unit')]
    res = {f'{a}/{b}': {'runs': 0, 'mismatch': 0, 'examples': [], 'sink_items': 0} for a, b in combos}
    for seed in range(s0, s0 + n):
        desc = gen(seed)
        for a, b in combos:
            net = Net(desc['units'], desc['chans'], bridge_group=b)
            rng = random.Random(seed)
            for eo, no in (rank_orders(net), default_orders(net, rng)):
                w = World(net, desc['init'], settle=a)
                q = Q(desc, settle=a, bridge_group=b)
                bad = None
                for k in range(steps):
                    w.step(eo, no)
                    q.step(eo, no)
                    if canon_p(w) != q.canon():
                        bad = k
                        break
                r = res[f'{a}/{b}']
                r['runs'] += 1
                r['sink_items'] += sum(len(v) for v in w.got.values())
                if bad is not None:
                    r['mismatch'] += 1
                    if len(r['examples']) < 5:
                        r['examples'].append({'seed': seed, 'step': bad})
    json.dump({'seeds': [s0, s0 + n], 'steps': steps, 'results': res}, open(out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""复核 94F：可穷举的小网络，换遍全部合法判定先后（同层元件全排列 × 非运输单位全排列），逐步比对整个状态。

用法：python3 order_exhaustive.py <起始种子> <找多少个网络> <步数> <先后数上限> <输出 json>
读法：带内前挪 eager、桥接器按轴（候选的读法）；另对同一批网络用 judge、unit 读法各跑一遍作对照。
"""
import itertools
import json
import math
import sys

from genp import gen, features
from simp import Net, World


def all_orders(net):
    by = {}
    for e in net.elems:
        by.setdefault(net.layer[e], []).append(e)
    layers = [by[L] for L in sorted(by)]
    eperms = [list(itertools.chain.from_iterable(p)) for p in
              itertools.product(*[list(itertools.permutations(g)) for g in layers])]
    nperms = [list(p) for p in itertools.permutations(net.nonts)]
    return [(eo, no) for eo in eperms for no in nperms]


def count_orders(net):
    by = {}
    for e in net.elems:
        by[net.layer[e]] = by.get(net.layer[e], 0) + 1
    c = math.factorial(len(net.nonts))
    for v in by.values():
        c *= math.factorial(v)
    return c


def main():
    s0, want, steps, cap, out = (int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]),
                                 sys.argv[5])
    combos = [('eager', 'axis'), ('judge', 'axis'), ('eager', 'unit')]
    res = {f'{a}/{b}': {'nets': 0, 'orders': 0, 'diff_nets': 0, 'diff_by_feat': {}} for a, b in combos}
    seed, found = s0, 0
    while found < want:
        desc = gen(seed)
        seed += 1
        net0 = Net(desc['units'], desc['chans'])
        c = count_orders(net0)
        if c < 2 or c > cap:
            continue
        found += 1
        f = features(desc)
        fk = f"dead_multi={int(f['dead_multi'])},bridge_two_axes_fed={int(f['shared_bridge_any'])}"
        for a, b in combos:
            net = Net(desc['units'], desc['chans'], bridge_group=b)
            ref, diff = None, False
            ords = all_orders(net)
            for eo, no in ords:
                w = World(net, desc['init'], settle=a)
                tr = []
                for _ in range(steps):
                    w.step(eo, no)
                    tr.append(hash(w.snapshot()))
                if ref is None:
                    ref = tr
                elif tr != ref:
                    diff = True
            r = res[f'{a}/{b}']
            r['nets'] += 1
            r['orders'] += len(ords)
            if diff:
                r['diff_nets'] += 1
                r['diff_by_feat'][fk] = r['diff_by_feat'].get(fk, 0) + 1
    json.dump({'seed_range': [s0, seed], 'steps': steps, 'cap': cap, 'results': res}, open(out, 'w'),
              ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()

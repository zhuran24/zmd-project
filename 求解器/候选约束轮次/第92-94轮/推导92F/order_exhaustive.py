#!/usr/bin/env python3
"""编码甲：对可穷举的随机小网络，枚举全部合法判定先后（同层元件之间的全部排列 × 非运输单位之间的全部排列，
总数不超过 CAP），逐步比对整个状态。用法：python3 order_exhaustive.py N_NETS STEPS CAP [first_seed]"""
import copy, itertools as it, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from netgen import gen
from order_check import build_a
from stepsim import Sim

def orders(net):
    lay = net.layer
    groups = [[e for e in net.elements if lay[e] == L] for L in sorted(set(lay.values()))]
    nts = [u for u in net.nontransport if net.units[u]['type'] != 'sink']
    sinks = [u for u in net.nontransport if net.units[u]['type'] == 'sink']
    for gs in it.product(*(it.permutations(g) for g in groups)):
        for ns in it.permutations(nts):
            yield [e for g in gs for e in g] + list(ns) + sinks

n, steps, cap = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
res = dict(nets=0, skipped_too_many=0, orders=0, mismatch=[])
seed = first
while res['nets'] < n:
    desc = gen(seed, allow_gate_filters=True, max_mach=3)
    seed += 1
    net = build_a(desc)
    lay = net.layer
    total = math.prod(math.factorial(sum(1 for e in net.elements if lay[e] == L)) for L in set(lay.values()))
    total *= math.factorial(sum(1 for u in net.nontransport if net.units[u]['type'] != 'sink'))
    if total > cap or total < 2:
        res['skipped_too_many'] += 1
        continue
    base = None
    for od in orders(net):
        sim = Sim(net, copy.deepcopy(desc['init']), order=od)
        snaps = []
        for _ in range(steps):
            sim.step(); snaps.append(sim.snapshot())
        res['orders'] += 1
        if base is None:
            base = snaps
        elif snaps != base:
            res['mismatch'].append(dict(seed=seed - 1)); break
    res['nets'] += 1
print(json.dumps(res, ensure_ascii=False))

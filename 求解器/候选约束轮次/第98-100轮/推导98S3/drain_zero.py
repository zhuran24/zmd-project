#!/usr/bin/env python3
"""98S3: push the repeated-stop drain past exhaustion.

Same construction and random stream as disturb_trace.py (seed, family,
gaplo/gaphi), engine A, histories reset on each rebuild.  Runs rounds of
(stop 2000..2649 steps, rebuild, free gap) until the lowest sand-leaf store
of any fast grinder during a gap reaches 0, then EXTRA more rounds, then lets
the plant run alone to an exact cycle.  Per round it records the lowest
sand-leaf store of each drained grinder and the highest blue-iron-powder
store of 铁研磨16 in the gap.
"""
import argparse, json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
from phase_search import cycle

ap = argparse.ArgumentParser()
ap.add_argument('--seed', type=int, default=11)
ap.add_argument('--family', default='random')
ap.add_argument('--gaplo', type=int, default=300)
ap.add_argument('--gaphi', type=int, default=600)
ap.add_argument('--extra', type=int, default=300)
ap.add_argument('--maxrounds', type=int, default=4000)
ap.add_argument('--output', default='drain_zero.json')
a = ap.parse_args()
seed = a.seed
rng = random.Random(seed * 31337 + 7)
f = S.A.Factory(seed, 3, 'thin')
fixed = dict(random=[],
             drain=[(0, ['铁研磨16', '铁研磨2', '铁研磨4']), (1, ['铁研磨14', '铁研磨0', '源研磨0']), (2, ['铁研磨15', '铁研磨6', '源研磨3'])])[a.family]
plan = S.plan_from(rng, fixed)
S.rewire_sand(f, plan)
S.set_core(f, list(range(28, 34)))
S.init_state(f, rng, 'dense')
for r in f.rs:
    r.cells = [-8] * len(r.cells)
S.rebuild(f, rng)
fast = [u for u in f.ms if '研磨' in u.name and u.name not in ('荞研磨4', '荞研磨5')]
g16 = S.by_name(f)['铁研磨16']
rows = []
zero_round = None
k = 0
while k < a.maxrounds:
    stop = rng.randrange(2000, 2650)
    gap = rng.randrange(a.gaplo, a.gaphi)
    f.open = False
    for _ in range(stop):
        f.step()
    S.rebuild(f, rng)
    f.open = True
    lo = {u.name: 50 for u in fast}
    hi_iron = 0
    b0 = g16.batches
    for _ in range(gap):
        f.step()
        for u in fast:
            v = u.stock['砂叶粉末']
            if v < lo[u.name]:
                lo[u.name] = v
        hi_iron = max(hi_iron, g16.stock['蓝铁粉末'])
    low = {n: v for n, v in lo.items() if v < 49}
    rows.append(dict(round=k, stop=stop, gap=gap, low=low, g16_iron_max=hi_iron, g16_batches=g16.batches - b0))
    if k % 100 == 0 or (zero_round is None and min(lo.values()) == 0):
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    if zero_round is None and min(lo.values()) == 0:
        zero_round = k
    k += 1
    if zero_round is not None and k > zero_round + a.extra:
        break
res = cycle(f, 120000)
out = dict(seed=seed, family=a.family, gaplo=a.gaplo, gaphi=a.gaphi, plan=plan, zero_round=zero_round,
           rounds=k, final_cycle=res, per_round=rows)
print(json.dumps(dict(zero_round=zero_round, rounds=k, final_cycle=res), ensure_ascii=False), flush=True)
(HERE / a.output).write_text(json.dumps(out, ensure_ascii=False) + '\n')

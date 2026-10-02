#!/usr/bin/env python3
"""98S3: continue one disturb_search.py case (same seed, same random stream)
for more rounds and record, per round, the lowest sand-leaf store of every
fast grinder during the free gap.  Shows which store drains and how fast.
After the last round the plant runs alone to an exact cycle.
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
ap.add_argument('--rounds', type=int, default=300)
ap.add_argument('--output', default='disturb_trace.json')
ap.add_argument('--gaplo', type=int, default=300)
ap.add_argument('--gaphi', type=int, default=3000)
a = ap.parse_args()
seed = a.seed
rng = random.Random(seed * 31337 + 7)
f = S.A.Factory(seed, 3, 'thin')
fixed = dict(chase=[(0, ['荞研磨4', '铁研磨16', '铁研磨14']), (1, ['荞研磨5', '铁研磨15', '铁研磨13'])], random=[],
             drain=[(0, ['铁研磨16', '铁研磨2', '铁研磨4']), (1, ['铁研磨14', '铁研磨0', '源研磨0']), (2, ['铁研磨15', '铁研磨6', '源研磨3'])])[a.family]
plan = S.plan_from(rng, fixed)
S.rewire_sand(f, plan)
S.set_core(f, list(range(28, 34)))
S.init_state(f, rng, 'dense')
for r in f.rs:
    r.cells = [-8] * len(r.cells)
S.rebuild(f, rng)
fast = [u for u in f.ms if '研磨' in u.name and u.name not in ('荞研磨4', '荞研磨5')]
rows = []
for k in range(a.rounds):
    stop = rng.randrange(2000, 2650)
    gap = rng.randrange(a.gaplo, a.gaphi)
    f.open = False
    for _ in range(stop):
        f.step()
    S.rebuild(f, rng)
    f.open = True
    lo = {u.name: 50 for u in fast}
    for _ in range(gap):
        f.step()
        for u in fast:
            v = u.stock['砂叶粉末']
            if v < lo[u.name]:
                lo[u.name] = v
    rows.append(dict(round=k, stop=stop, gap=gap, low={n: v for n, v in lo.items() if v < 49}))
    if k % 100 == 0:
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
res = cycle(f, 80000)
out = dict(seed=seed, family=a.family, plan=plan, rounds=a.rounds, final_cycle=res, per_round=rows)
print(json.dumps(dict(final_cycle=res), ensure_ascii=False), flush=True)
(HERE / a.output).write_text(json.dumps(out, ensure_ascii=False) + '\n')

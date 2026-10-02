#!/usr/bin/env python3
"""98S3: second encoding for the repeated-stop drain (report section 6, item 3).

Replays the first R rounds of disturb_trace.py --seed 11 --family random
(same random stream: gaps 300..2999) with engine A and engine B (95S EngineB)
in lockstep, comparing the whole state after every step; rebuilds are copied
into B with histories reset.  Records, from engine B's own stores, the lowest
sand-leaf store of 铁研磨16 in each free gap.
"""
import argparse, importlib.util, json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('probe95', ROOT / '第95-97轮' / '推导95S' / 'factory_probe.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)

ap = argparse.ArgumentParser()
ap.add_argument('--rounds', type=int, default=110)
a = ap.parse_args()
seed = 11
rng = random.Random(seed * 31337 + 7)
f = S.A.Factory(seed, 3, 'thin')
S.rewire_sand(f, S.plan_from(rng, []))
S.set_core(f, list(range(28, 34)))
S.init_state(f, rng, 'dense')
for r in f.rs:
    r.cells = [-8] * len(r.cells)
S.rebuild(f, rng)
b = P.EngineB(f)
b.compare(f)
gi = b.index[S.by_name(f)['铁研磨16']]
lows = []
steps = 0
for k in range(a.rounds):
    stop = rng.randrange(2000, 2650)
    gap = rng.randrange(300, 3000)
    f.open = False; b.open = False
    for _ in range(stop):
        f.step(); b.step(); b.compare(f); steps += 1
    S.rebuild(f, rng)
    b.copy_order(f, reset=True)
    f.open = True; b.open = True
    lo = 50
    for _ in range(gap):
        f.step(); b.step(); b.compare(f); steps += 1
        lo = min(lo, b.stock[gi].get('砂叶粉末', 0))
    lows.append(lo)
    if k % 10 == 0:
        print(k, lo, steps, flush=True)
out = dict(seed=seed, rounds=a.rounds, compared_steps=steps, low_gf16_engineB=lows)
(HERE / 'drain_cross.json').write_text(json.dumps(out) + '\n')
print(json.dumps(dict(rounds=a.rounds, compared_steps=steps, first=lows[:3], last=lows[-3:])), flush=True)

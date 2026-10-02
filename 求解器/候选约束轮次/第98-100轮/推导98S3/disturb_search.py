#!/usr/bin/env python3
"""98S3 repeated-disturbance runs from a full ('dense') start.

Every machine store full, every route full of mature on-line items, plant
units in the full S09 start.  Then many rounds of: warehouse stop of length
2000..2650 steps (long enough to fill the output stores of the packers and of
fillers 1-2 if they start low, too short for filler 3), random offline rebuild
(new connection order, histories reset), and a free gap.  Tracks the lowest
sand-leaf store of the fast grinders and the lowest ore store of the first
stage machines after each round, then runs to an exact cycle.
"""
import argparse, json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
from phase_search import cycle

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--count', type=int, default=2)
    ap.add_argument('--rounds', type=int, default=120)
    ap.add_argument('--family', default='chase')
    ap.add_argument('--output', default='disturb.json')
    a = ap.parse_args()
    out = []
    for seed in range(a.seed, a.seed + a.count):
        rng = random.Random(seed * 31337 + 7)
        f = S.A.Factory(seed, 3, 'thin')
        fixed = dict(chase=[(0, ['荞研磨4', '铁研磨16', '铁研磨14']), (1, ['荞研磨5', '铁研磨15', '铁研磨13'])],
                     random=[])[a.family]
        S.rewire_sand(f, S.plan_from(rng, fixed))
        S.set_core(f, list(range(28, 34)))
        S.init_state(f, rng, 'dense')
        for r in f.rs:
            r.cells = [-8] * len(r.cells)
        S.rebuild(f, rng)
        fast = [u for u in f.ms if '研磨' in u.name and u.name not in ('荞研磨4', '荞研磨5')]
        first = [r.target for r in f.ore_routes]
        trace = []
        for k in range(a.rounds):
            stop = rng.randrange(2000, 2650)
            gap = rng.randrange(300, 3000)
            f.open = False
            for _ in range(stop):
                f.step()
            S.rebuild(f, rng)
            f.open = True
            lo_s = lo_o = 50
            for _ in range(gap):
                f.step()
                lo_s = min(lo_s, min(u.stock['砂叶粉末'] for u in fast))
                lo_o = min(lo_o, min(sum(u.stock.values()) for u in first))
            trace.append((k, stop, gap, lo_s, lo_o))
        f.open = True
        res = cycle(f, 80000)
        res.update(seed=seed, family=a.family, rounds=a.rounds,
                   min_sand_store=min(x[3] for x in trace), min_ore_store=min(x[4] for x in trace),
                   last_rounds=trace[-5:])
        print(json.dumps(res, ensure_ascii=False), flush=True)
        out.append(dict(res, trace=trace))
        (HERE / a.output).write_text(json.dumps(out, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    main()

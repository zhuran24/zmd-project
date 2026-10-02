#!/usr/bin/env python3
"""98S3 forced-deficit-then-release search.

During a debug window the player keeps taking items out of the first cells of
chosen loop routes (one refill in every m is removed), for W steps, so the
whole plant settles into a deficit regime with matching buffers (full ore-side
slots, short sand-leaf slots, blocked lines behind slowed packers/fillers).
The window then ends; the state holds only on-line items, so it is an
admissible end-of-debug state.  The plant then runs alone to an exact cycle.
A sustained deficit after release would be a counterexample candidate.
"""
import argparse, json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
from phase_search import cycle
from loop_search import FAM, build

def prepare(seed, family, maxlen, window):
    """Exact released state of one forced case (deterministic in seed)."""
    f, rng, plan, core = build(seed, family, maxlen)
    spec = FAM[family]
    targets = set(spec['loop_sand'])
    routes = [r for r in f.rs if r.kind == '砂叶粉末' and r.target.name in targets]
    routes += [f.ore_routes[i] for i in spec['loop_ore']]
    if family == 'RND':
        routes += rng.sample([r for r in f.rs if r.kind == '砂叶粉末'], 6) + rng.sample(list(f.ore_routes), 3)
    if rng.random() < .5:
        extra = rng.sample([r for r in f.rs if r.kind == '砂叶粉末' and r not in routes], 3)
        routes += extra
    m = {r.index: rng.choice([2, 3, 5, 9, 17]) for r in routes}
    cnt = {r.index: 0 for r in routes}
    removed = 0
    for _ in range(window):
        f.step()
        for r in routes:
            if r.cells[0] == f.t - 1:
                cnt[r.index] += 1
                if cnt[r.index] % m[r.index] == 0:
                    r.cells[0] = None; removed += 1
    return f, plan, core, removed, m, routes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', default='L16')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--count', type=int, default=50)
    ap.add_argument('--maxlen', type=int, default=3)
    ap.add_argument('--window', type=int, default=12000)
    ap.add_argument('--limit', type=int, default=80000)
    ap.add_argument('--output', default='forced.json')
    a = ap.parse_args()
    out = []; bad = 0
    for seed in range(a.seed, a.seed + a.count):
        f, plan, core, removed, m, routes = prepare(seed, a.family, a.maxlen, a.window)
        deficit_window = None
        res = cycle(f, a.limit)
        res.update(seed=seed, core=core, removed=removed, mods=sorted(set(m.values())), forced=len(routes))
        out.append(res)
        if not res.get('ok'):
            bad += 1
            print(json.dumps(dict(res, plan=plan), ensure_ascii=False), flush=True)
    summary = dict(family=a.family, seeds=[a.seed, a.seed + a.count], maxlen=a.maxlen, window=a.window,
                   cases=len(out), not_ok=bad,
                   periods=sorted(set(x.get('period') for x in out if 'period' in x)),
                   max_cycle_start=max((x.get('start') or 0) for x in out))
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    (HERE / a.output).write_text(json.dumps(dict(summary=summary, cases=out), ensure_ascii=False) + '\n')

if __name__ == '__main__':
    main()

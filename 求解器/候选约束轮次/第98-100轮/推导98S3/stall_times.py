#!/usr/bin/env python3
"""98S3: check the stop-length window used in report section 6, item 3.

From a full-rate cycle (seed 11 'random' wiring of disturb_trace.py, and a few
more seeds), close the warehouse and record, for each packer/filler, the first
step after the close at which it holds a finished batch that cannot enter its
pickup slot (i.e. it stalls).  Rule estimate: packers and fillers 1-2 at
(50+l)*40 steps, filler 3 at about (50+l)*53.3 steps, l = product-route cells.
"""
import json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
from phase_search import cycle

out = []
for seed in (11, 12, 13, 14, 15):
    rng = random.Random(seed * 31337 + 7)
    f = S.A.Factory(seed, 3, 'thin')
    S.rewire_sand(f, S.plan_from(rng, []))
    S.set_core(f, list(range(28, 34)))
    S.init_state(f, rng, 'dense')
    for r in f.rs:
        r.cells = [-8] * len(r.cells)
    S.rebuild(f, rng)
    res = cycle(f, 80000)
    assert res.get('ok'), res
    finals = [u for u in f.ms if u.name.startswith(('封装', '灌装'))]
    plen = {u.name: len(r.cells) for u in finals for r in u.routes}
    f.open = False
    t0 = f.t
    first = {}
    for _ in range(3200):
        f.step()
        for u in finals:
            if u.name not in first and u.done and u.out + u.recipe[2] > 50:
                first[u.name] = f.t - t0
    row = dict(seed=seed, cycle=res, route_cells=plen, first_stall_after_close=first)
    out.append(row)
    print(json.dumps(dict(seed=seed, stall=first, cells=plen), ensure_ascii=False), flush=True)
(HERE / 'stall_times.json').write_text(json.dumps(out, ensure_ascii=False) + '\n')

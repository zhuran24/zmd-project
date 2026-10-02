#!/usr/bin/env python3
"""复核100S2：长路（1—30格）整厂例，扰动同 run_a。用法 run_long.py START COUNT"""
import sys, json, time
from engine_a import run_case
from run_a import multi_out_paths
a, n = int(sys.argv[1]), int(sys.argv[2])
for seed in range(a, a + n):
    hist = ['clear', 'keep', 'mix'][seed % 3]
    t0 = time.time()
    r = run_case(seed, maxlen=30, history=hist, disturb=True, extra_offline=10, stops=6)
    f = r.pop('f', None)
    p = r.get('period')
    rec = dict(seed=seed, history=hist, maxlen=30, period=p, cycle_start=r.get('cycle_start'),
               nviol=r.get('nviol'), secs=round(time.time() - t0, 1))
    if p:
        ore = [r['ore'][b.idx] for b in f.belts if b.src in f.src]
        rec.update(bat_per_tick_x100=round(100 * r['battery'] * 8 / p, 4), cap_per_tick_x100=round(100 * r['capsule'] * 8 / p, 4),
                   ore_per_tick=sorted(set(round(x * 8 / p, 6) for x in ore)),
                   multi_out_rej=sum(r['rej'][b.idx] for b in multi_out_paths(f)),
                   total_belt_cells=sum(b.tiles for b in f.belts))
    print(json.dumps(rec, ensure_ascii=False), flush=True)

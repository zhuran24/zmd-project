#!/usr/bin/env python3
"""98S3 second encoding for the key numbers.

Rebuilds chosen cases exactly (same seeds), then runs engine A (92D
factory_check, read-only) and engine B (95S EngineB, read-only: an age /
due-date implementation written separately) in lockstep from the released
state, comparing every machine store, cache, remaining time, batch count,
input cursor, every transport cell age, every sender count and history, and
deliveries after every step.  Each engine detects its own exact cycle with its
own state key; both cycles must start and end at the same step, and the rates
are recomputed from engine B's own counters.
"""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('probe95', ROOT / '第95-97轮' / '推导95S' / 'factory_probe.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
import loop_search as LS
import forced_search as FS

def lockstep(f, limit):
    b = P.EngineB(f)
    b.compare(f)
    seen_a, seen_b = {}, {}
    ore_idx = [r.index for r in f.ore_routes]
    steps = 0
    for _ in range(limit):
        f.step(); b.step(); b.compare(f); steps += 1
        if f.t % 8:
            continue
        ka = hashlib.sha256(repr(f.state()).encode()).digest()
        kb = hashlib.sha256(repr(P.state_b(b)).encode()).digest()
        na = (f.t,)
        nb = (b.time, dict(b.shipped), [b.sent[i] for i in ore_idx])
        if ka in seen_a or kb in seen_b:
            assert ka in seen_a and kb in seen_b and seen_a[ka] == seen_b[kb][0], 'cycle disagreement'
            t0 = seen_b[kb][0]; old = seen_b[kb]
            period = b.time - t0
            delivery = {k: b.shipped[k] - old[1].get(k, 0) for k in b.shipped}
            ore = [b.sent[i] - x for i, x in zip(ore_idx, old[2])]
            ok = all(x * 8 == period for x in ore) and delivery.get('高容谷地电池', 0) * 40 == period * 3 \
                and delivery.get('精选荞愈胶囊', 0) * 160 == period * 11
            return dict(start=t0, end=b.time, period=period, delivery=delivery,
                        ore_min=min(ore), ore_max=max(ore), ok=ok, compared_steps=steps)
        seen_a[ka] = f.t
        seen_b[kb] = nb
    return dict(status='no cycle', compared_steps=steps)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=['loop', 'forced'], default='loop')
    ap.add_argument('--family', default='L16')
    ap.add_argument('--seeds', default='1000-1009')
    ap.add_argument('--maxlen', type=int, default=4)
    ap.add_argument('--window', type=int, default=12000)
    ap.add_argument('--limit', type=int, default=80000)
    ap.add_argument('--output', default='crosscheck.json')
    a = ap.parse_args()
    lo, hi = map(int, a.seeds.split('-'))
    out = []
    for seed in range(lo, hi + 1):
        if a.kind == 'loop':
            f = LS.prepare(seed, a.family, a.maxlen)[0]
        else:
            f = FS.prepare(seed, a.family, a.maxlen, a.window)[0]
        res = lockstep(f, a.limit)
        res.update(seed=seed, kind=a.kind, family=a.family)
        print(json.dumps(res, ensure_ascii=False), flush=True)
        out.append(res)
    (HERE / a.output).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')

if __name__ == '__main__':
    main()

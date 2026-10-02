#!/usr/bin/env python3
"""98S3 measured step offsets used in report section 4 (both engines).

For a run that has reached its cycle, records over 960 steps:
  * every batch start (step t, machine) and every first-cell refill (t, route);
  * for each sand-leaf route: refill residue minus its grinder's start residue
    (0 = route is the binding input and flows freely; 1 = backed-up route
    refilled the step after its grinder started, lag 0);
  * for each slow route L_H (sand leaf into the two buckwheat grinders of the
    third filler): refill step minus the latest preceding start of filler 3.
Engine B (95S) is run in lockstep from the same state and must agree.
"""
import importlib.util, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('probe95', ROOT / '第95-97轮' / '推导95S' / 'factory_probe.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)

def measure(seed, init, fam_fixed, warm=6000, span=960):
    rng = random.Random(seed * 7919 + 98)
    f = S.A.Factory(seed, 3, 'thin')
    plan = S.plan_from(rng, fam_fixed)
    S.rewire_sand(f, plan)
    S.set_core(f, list(range(28, 34)))
    S.init_state(f, rng, init)
    S.rebuild(f, rng)
    for _ in range(warm):
        f.step()
    b = P.EngineB(f)
    starts = defaultdict(list); refills = defaultdict(list); starts_b = defaultdict(list); refills_b = defaultdict(list)
    for _ in range(span):
        t = f.t
        f.step(); b.step(); b.compare(f)
        for u in f.ms:
            if u.remaining == u.recipe[3]:
                starts[u.name].append(t)
        for r in f.rs:
            if r.cells[0] == t:
                refills[r.index].append(t)
        for i, u in enumerate(b.units):
            if b.recipes[i] is not None and b.due[i] == t + b.recipes[i][3]:
                starts_b[u.name].append(t)
        for j, cells in enumerate(b.cargo):
            if b.last[j] == t:
                refills_b[j].append(t)
    assert dict(starts) == dict(starts_b), 'start events differ'
    assert {k: v for k, v in refills.items()} == {k: v for k, v in refills_b.items()}, 'refills differ'
    sand = [r for r in f.rs if r.kind == '砂叶粉末']
    fast = Counter(); slow = Counter(); gaps = Counter()
    fill3 = starts['灌装2']
    for r in sand:
        g = r.target.name
        if g in ('荞研磨4', '荞研磨5'):
            for t in refills[r.index]:
                prev = [s for s in fill3 if s < t]
                if prev:
                    slow[t - prev[-1]] += 1
            continue
        res = Counter((t - s) % 8 for t in refills[r.index] for s in starts[g][-1:])
        rr = {t % 8 for t in refills[r.index]}; ss = {s % 8 for s in starts[g]}
        if len(rr) == 1 and len(ss) == 1:
            fast[(next(iter(rr)) - next(iter(ss))) % 8] += 1
        else:
            fast['not 8-periodic'] += 1
        gaps.update(b2 - a2 for a2, b2 in zip(refills[r.index], refills[r.index][1:]))
    return dict(seed=seed, init=init, fast_route_offset=dict(fast), slow_refill_after_filler3_start=dict(sorted(slow.items())),
                fast_refill_gaps=dict(gaps), filler3_starts_mod8=sorted({s % 8 for s in fill3}),
                compared_steps=span)

if __name__ == '__main__':
    out = []
    chase = [(0, ['荞研磨4', '铁研磨16', '铁研磨14']), (1, ['荞研磨5', '铁研磨15', '铁研磨13'])]
    for seed in range(3):
        for init in ('starve', 'dense'):
            res = measure(seed, init, chase)
            print(json.dumps(res, ensure_ascii=False), flush=True)
            out.append(res)
    (HERE / 'offsets.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')

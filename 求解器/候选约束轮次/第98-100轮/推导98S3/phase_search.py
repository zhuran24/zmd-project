#!/usr/bin/env python3
"""98S3 phase-perturbation search around a reached full-rate cycle.

Base: 'chase' style wiring (the sand-leaf crushers that feed the two buckwheat
grinders of the third filler also feed the blue-iron grinders whose steel goes
to shapers 5 and 6), start state 'starve' (every fast grinder short of sand-leaf
powder, so its sand-leaf route is the binding input), no disturbances.  Once
the run is in a cycle, a debug-style perturbation is applied: during a window,
whatever a chosen crusher puts into the first cell of a chosen route is taken
out again (stall d steps), and k bottles are taken out of filler 3.  Every
perturbed state still holds only on-line items, so it is an admissible state at
the end of debugging.  Then the run continues to an exact cycle.
"""
import argparse, copy, hashlib, itertools, json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S

def cycle(f, limit):
    seen = {}
    for _ in range(limit):
        f.step()
        if f.t % 8:
            continue
        key = hashlib.sha256(repr(f.state()).encode()).digest()
        now = (f.t, dict(f.delivered), [r.count for r in f.ore_routes])
        if key in seen:
            old = seen[key]; period = f.t - old[0]
            delivery = {k: f.delivered[k] - old[1].get(k, 0) for k in f.delivered}
            ore = [r.count - x for r, x in zip(f.ore_routes, old[2])]
            ok = all(x * 8 == period for x in ore) and delivery.get('高容谷地电池', 0) * 40 == period * 3 \
                and delivery.get('精选荞愈胶囊', 0) * 160 == period * 11
            return dict(start=old[0], end=f.t, period=period, delivery=delivery,
                        ore_min=min(ore), ore_max=max(ore), ok=ok)
        seen[key] = now
    return dict(status='no cycle', t=f.t)

def base(seed, family, maxlen):
    rng = random.Random(seed * 7919 + 98)
    f = S.A.Factory(seed, maxlen, 'thin')
    fixed = dict(chase=[(0, ['荞研磨4', '铁研磨16', '铁研磨14']), (1, ['荞研磨5', '铁研磨15', '铁研磨13'])],
                 chase2=[(10, ['荞研磨4', '铁研磨16']), (0, ['荞研磨5', '铁研磨15', '铁研磨14'])],
                 pack=[(0, ['源研磨0', '铁研磨0', '铁研磨1']), (1, ['源研磨1', '铁研磨2', '铁研磨3'])])[family]
    plan = S.plan_from(rng, fixed)
    S.rewire_sand(f, plan)
    S.set_core(f, list(range(28, 34)))
    S.init_state(f, rng, 'starve')
    S.rebuild(f, rng)
    for _ in range(4000):
        f.step()
    return f, rng, plan

def perturb(f, stalls, bottles, steelremove):
    """stalls: list of (route, d). Run d steps removing refills of that route."""
    names = S.by_name(f)
    fill = names['灌装2']
    fill.stock['钢质瓶'] = max(0, fill.stock['钢质瓶'] - bottles)
    for nm, k in steelremove:
        u = names[nm]; u.stock['钢块'] = max(0, u.stock['钢块'] - k)
    horizon = max([d for _, d in stalls] + [0])
    for s in range(horizon):
        f.step()
        for r, d in stalls:
            if s < d and r.cells[0] == f.t - 1:
                r.cells[0] = None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--family', default='chase')
    ap.add_argument('--maxlen', type=int, default=3)
    ap.add_argument('--part', type=int, default=0)
    ap.add_argument('--parts', type=int, default=1)
    ap.add_argument('--limit', type=int, default=40000)
    ap.add_argument('--output', default='phase.json')
    a = ap.parse_args()
    f0, rng, plan = base(a.seed, a.family, a.maxlen)
    ks = sorted([u for u in f0.ms if u.name.startswith('砂叶粉碎')], key=lambda u: int(u.name[4:]))
    lines = [r for k in ks[:2] + [ks[10]] for r in k.routes if r.target.name.startswith('铁研磨')]
    lines = lines[:3]
    combos = list(itertools.product(range(8), repeat=len(lines)))
    out = []
    bad = 0
    for idx, combo in enumerate(combos):
        if idx % a.parts != a.part:
            continue
        for bottles in (0, 3, 7):
            f = copy.deepcopy(f0)
            lmap = {r.index: r for r in f.rs}
            stalls = [(lmap[r.index], d) for r, d in zip(lines, combo)]
            perturb(f, stalls, bottles, [('塑形4', combo[0] % 2), ('塑形5', combo[1] % 2)])
            res = cycle(f, a.limit)
            res.update(combo=combo, bottles=bottles)
            out.append(res)
            if not res.get('ok'):
                bad += 1
                print(json.dumps(res, ensure_ascii=False), flush=True)
    summary = dict(seed=a.seed, family=a.family, maxlen=a.maxlen, plan=plan,
                   stalled=[(r.source.name, r.target.name, len(r.cells)) for r in lines],
                   cases=len(out), not_ok=bad,
                   periods=sorted(set(x.get('period') for x in out if 'period' in x)),
                   max_start=max(x.get('start', 0) for x in out))
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    (HERE / a.output).write_text(json.dumps(dict(summary=summary, cases=out), ensure_ascii=False) + '\n')

if __name__ == '__main__':
    main()

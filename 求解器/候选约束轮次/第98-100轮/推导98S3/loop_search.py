#!/usr/bin/env python3
"""98S3 designed-loop search.

Each family wires a closed 'push loop' that the residue count of the report
(section 4) does not exclude: free-flow route X_i loses a tie at a shared
sender to a backed-up route Y_i, Y_i is backed up because the machine fed
along X_{i-1} is short, and so on around the loop.  Start: every grinder short
of sand-leaf powder (binding sand-leaf route), ore chains backed up, random
cargo; then random stalls of the loop routes (debug-style removals) to set
their phases.  Run to an exact cycle and record whether all 52 ore routes are
at 1 item/tick.  Engine A only (read-only import, see search.py).
"""
import argparse, copy, json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S
from phase_search import cycle

FAM = {
    # (1,6): core{X: ore10 -> gf5 BIP, Y': ore0 -> pack0 part chain}; K0{X': go0 SLP, Y: gf5 SLP}
    'L16': dict(k={0: ['源研磨0', '铁研磨5']}, core=[0, 10], loop_sand=['源研磨0', '铁研磨5'], loop_ore=[0, 10]),
    # (3,4): core{X1: ore34 -> go0 -> pack0 dense, Y1: ore12 -> gf6}; K0{X2: gf6 SLP, Y2: gf0 SLP}
    'L34': dict(k={0: ['铁研磨6', '铁研磨0']}, core=[34, 12], loop_sand=['铁研磨6', '铁研磨0'], loop_ore=[34, 12]),
    # (2,2,2): filler3 -> L_H1 on K0 hits gf0 (pack0 parts); pack0 -> go0 SLP on K1 hits gf6 (filler0 bottles);
    #          filler0 -> 荞研磨0 SLP on K2 hits gf16 (shaper6 -> filler3)
    'L222': dict(k={0: ['荞研磨4', '铁研磨0'], 1: ['源研磨0', '铁研磨6'], 2: ['荞研磨0', '铁研磨16']},
                 core=[], loop_sand=['铁研磨0', '铁研磨6', '铁研磨16', '荞研磨4', '源研磨0', '荞研磨0'], loop_ore=[]),
    # mixed: both slow SLP routes with three shaper-5/6 grinders plus core on the same chains
    # random wiring and random core ports; forced routes drawn at random (forced_search only)
    'RND': dict(k={}, core=[], loop_sand=[], loop_ore=[]),
    'L3T': dict(k={0: ['荞研磨4', '铁研磨16', '铁研磨14'], 1: ['荞研磨5', '铁研磨15']},
                core=[28, 30, 32], loop_sand=['铁研磨16', '铁研磨14', '铁研磨15'], loop_ore=[28, 30, 32]),
}

def build(seed, fam, maxlen):
    rng = random.Random(seed * 104729 + 983)
    f = S.A.Factory(seed, maxlen, 'thin')
    spec = FAM[fam]
    fixed = list(spec['k'].items())
    plan = S.plan_from(rng, fixed)
    S.rewire_sand(f, plan)
    core = list(spec['core'])
    pool = [i for i in range(52) if i not in core]
    rng.shuffle(pool)
    core += pool[:6 - len(core)]
    S.set_core(f, core)
    S.init_state(f, rng, 'starve')
    S.rebuild(f, rng)
    return f, rng, plan, core

def prepare(seed, family, maxlen):
    """Exact start state of one loop case (deterministic in seed)."""
    spec = FAM[family]
    f, rng, plan, core = build(seed, family, maxlen)
    targets = set(spec['loop_sand'])
    stall_routes = [r for r in f.rs if r.kind == '砂叶粉末' and r.target.name in targets]
    stall_routes += [f.ore_routes[i] for i in spec['loop_ore']]
    stalls = [(r, rng.randrange(0, 16)) for r in stall_routes]
    start = rng.randrange(0, 400)
    for _ in range(start):
        f.step()
    horizon = max(d for _, d in stalls)
    for s in range(horizon):
        f.step()
        for r, d in stalls:
            if s < d and r.cells[0] == f.t - 1:
                r.cells[0] = None
    return f, plan, core, stalls, start

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', default='L16')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--maxlen', type=int, default=3)
    ap.add_argument('--limit', type=int, default=60000)
    ap.add_argument('--output', default='loop.json')
    a = ap.parse_args()
    spec = FAM[a.family]
    out = []
    bad = 0
    for seed in range(a.seed, a.seed + a.count):
        f, plan, core, stalls, start = prepare(seed, a.family, a.maxlen)
        res = cycle(f, a.limit)
        res.update(seed=seed, core=core, stalls=[d for _, d in stalls], start=res.get('start'), pre=start)
        out.append(res)
        if not res.get('ok'):
            bad += 1
            print(json.dumps(dict(res, plan=plan), ensure_ascii=False), flush=True)
    summary = dict(family=a.family, seeds=[a.seed, a.seed + a.count], maxlen=a.maxlen, cases=len(out), not_ok=bad,
                   periods=sorted(set(x.get('period') for x in out if 'period' in x)),
                   max_cycle_start=max((x.get('start') or 0) for x in out))
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    (HERE / a.output).write_text(json.dumps(dict(summary=summary, cases=out), ensure_ascii=False) + '\n')

if __name__ == '__main__':
    main()

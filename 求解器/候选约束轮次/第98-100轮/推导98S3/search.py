#!/usr/bin/env python3
"""98S3 targeted whole-plant search on the S11 wiring.

Engine A = read-only import of 第92-94轮/推导92D/factory_check.py (pure directed
belts, one step = complete/flush, belts by receiver with round robin, each
non-transport unit sends once to its least-recently-successful empty first
cell, then start recipes).  This script only rewires which sand-leaf crusher
outlet feeds which grinder, which warehouse/core port feeds which ore line,
sets route lengths and the start state, then runs and detects an exact cycle.
Writes only into this folder.
"""
import argparse, hashlib, importlib.util, json, random, sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('engineA', ROOT / '第92-94轮' / '推导92D' / 'factory_check.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)

def by_name(f):
    return {u.name: u for u in f.ms}

def rewire_sand(f, plan):
    """plan: list of 11 lists of grinder names (K0..K10), K10 gets 2."""
    names = by_name(f)
    ks = [u for u in f.ms if u.name.startswith('砂叶粉碎')]
    ks.sort(key=lambda u: int(u.name[4:]))
    assert sum(len(p) for p in plan) == 32
    for k, targets in zip(ks, plan):
        routes = [r for r in f.rs if r.source is k and r.kind == '砂叶粉末']
        assert len(routes) == len(targets), (k.name, len(routes), len(targets))
        for r, tn in zip(routes, targets):
            t = names[tn]
            f.incoming[r.target].remove(r)
            r.target = t
            f.incoming[t].append(r)
            t.accept_order[r.index] = r.index
    for u in f.ms:
        if '研磨' in u.name:
            assert sum(1 for r in f.incoming[u] if r.kind == '砂叶粉末') == 1, u.name

def set_core(f, core_lines):
    """core_lines: indices into f.ore_routes that the protocol core feeds."""
    ore = list(f.ore_routes)
    ports = [r.source for r in ore]
    # collect current non-core port objects
    free_ports = [p for p in ports if p is not f.core]
    for r in ore:
        r.source.routes.remove(r)
    f.core.routes = []
    it = iter(free_ports)
    for i, r in enumerate(ore):
        if i in core_lines:
            r.source = f.core
        else:
            r.source = next(it)
        r.source.routes.append(r)
        r.source.sent[r.index] = -1
        r.source.order[r.index] = r.index
    assert len(f.core.routes) == 6

def rebuild(f, rng):
    """Same physical-unit permutation reading as 95S rebuild_order (histories reset)."""
    units = f.ms + f.sources + [f.sink]
    keys = [('u', i) for i in range(len(units))]
    keys += [('c', r.index, p) for r in f.rs for p in range(len(r.cells))]
    rng.shuffle(keys)
    sink_alias = ('u', len(units) - 1)
    keys = [k for k in keys if k != sink_alias]
    rank = {k: i for i, k in enumerate(keys)}
    ui = {u: i for i, u in enumerate(units)}
    ui[f.sink] = ui[f.core]
    for r in f.rs:
        r.source.order[r.index] = max(rank['u', ui[r.source]], rank['c', r.index, 0])
        r.target.accept_order[r.index] = max(rank['u', ui[r.target]], rank['c', r.index, len(r.cells) - 1])
    for u, routes in f.incoming.items():
        routes.sort(key=lambda r: (u.accept_order[r.index], r.index))
        u.cursor = None
    for u in f.ms + f.sources:
        u.sent = {r.index: -1 for r in u.routes}

def init_state(f, rng, mode):
    for u in f.ms:
        u.stock = Counter(); u.out = 0; u.remaining = 0; u.done = False
    for r in f.rs:
        r.cells = [None] * len(r.cells)
    if mode in ('dense', 'random', 'half'):
        for u in f.ms:
            for k in u.recipe[0]:
                u.stock[k] = 50 if mode == 'dense' else (rng.randrange(51) if mode == 'random' else 25)
            u.out = 50 if mode == 'dense' else (rng.randrange(51) if mode == 'random' else 25)
            if rng.random() < .7:
                u.remaining = rng.randrange(1, u.recipe[3] + 1)
        for r in f.rs:
            r.cells = [(-rng.randrange(9) if (mode == 'dense' or rng.random() < .7) else None) for _ in r.cells]
    if mode == 'starve':
        # Ore chain backed up, fast grinders SLP-starved: every SLP line is binding.
        for u in f.ms:
            for k in u.recipe[0]:
                u.stock[k] = 50
            u.out = rng.randrange(0, 3)
            u.remaining = rng.randrange(0, u.recipe[3] + 1)
            if '研磨' in u.name and u.name not in ('荞研磨4', '荞研磨5'):
                u.stock['砂叶粉末'] = 0
                u.out = 0
            if u.name.startswith(('塑形', '灌装', '封装', '配件', '钢精炼')):
                for k in u.recipe[0]:
                    u.stock[k] = rng.randrange(0, 10)
        for r in f.rs:
            r.cells = [(-rng.randrange(9) if rng.random() < .5 else None) for _ in r.cells]
            if r.kind == '砂叶粉末' and r.target.name not in ('荞研磨4', '荞研磨5'):
                r.cells = [None] * len(r.cells)
    # Plant units always full (S09 start) so every K always has stock.
    for c, a, b, k, ca, ac in f.units:
        for u in (c, a, b, k):
            u.stock = Counter({item: 50 for item in u.recipe[0]})
            u.out = 50
            u.remaining = rng.randrange(1, 8)
            u.done = False
        for r in (ca, ac, c.routes[1], b.routes[0]):
            r.cells = [-rng.randrange(9) for _ in r.cells]

def run(f, rng, prefix, limit, closed, changes, sample=8):
    seen = {}
    for _ in range(prefix + limit):
        t = f.t
        f.open = not any(a <= t < z for a, z in closed)
        if t in changes:
            rebuild(f, rng)
        f.step()
        if f.t <= prefix or f.t % sample:
            continue
        key = hashlib.sha256(repr(f.state()).encode()).digest()
        now = (f.t, dict(f.delivered), [r.count for r in f.ore_routes], [u.batches for u in f.ms])
        if key in seen:
            old = seen[key]
            period = f.t - old[0]
            delivery = {k: f.delivered[k] - old[1].get(k, 0) for k in f.delivered}
            ore = [r.count - x for r, x in zip(f.ore_routes, old[2])]
            batches = {u.name: b - x for u, b, x in zip(f.ms, now[3], old[3])}
            ok = all(x * 8 == period for x in ore) and delivery.get('高容谷地电池', 0) * 40 == period * 3 \
                and delivery.get('精选荞愈胶囊', 0) * 160 == period * 11
            return dict(cycle_start=old[0], cycle_end=f.t, period=period, delivery=delivery,
                        ore=ore, batches=batches, pass_rates=ok)
        seen[key] = now
    return dict(status='no cycle', steps=f.t)

GF = ['铁研磨%d' % i for i in range(17)]
GO = ['源研磨%d' % i for i in range(9)]
GQ = ['荞研磨%d' % i for i in range(6)]

def plan_from(rng, fixed):
    """fixed: list of (k_index, [names]) placed first; rest random."""
    sizes = [3] * 10 + [2]
    plan = [[] for _ in range(11)]
    used = set()
    for k, names in fixed:
        plan[k] = list(names); used.update(names)
    rest = [n for n in GF + GO + GQ if n not in used]
    rng.shuffle(rest)
    for k in range(11):
        while len(plan[k]) < sizes[k]:
            plan[k].append(rest.pop())
    assert not rest
    return plan

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--count', type=int, default=1)
    ap.add_argument('--maxlen', type=int, default=3)
    ap.add_argument('--init', default='dense')
    ap.add_argument('--family', default='chase')
    ap.add_argument('--limit', type=int, default=60000)
    ap.add_argument('--output', default='search.json')
    ap.add_argument('--nodist', action='store_true')
    a = ap.parse_args()
    out = []
    for seed in range(a.seed, a.seed + a.count):
        rng = random.Random(seed * 7919 + 98)
        f = A.Factory(seed, a.maxlen, 'thin')
        fam = a.family
        if fam == 'chase':
            fixed = [(0, ['荞研磨4', '铁研磨16', '铁研磨14']), (1, ['荞研磨5', '铁研磨15', '铁研磨13'])]
        elif fam == 'chase2':
            fixed = [(10, ['荞研磨4', '铁研磨16']), (0, ['荞研磨5', '铁研磨15', '铁研磨14'])]
        elif fam == 'same':
            fixed = [(0, ['荞研磨4', '荞研磨5', '铁研磨16'])]
        elif fam == 'random':
            fixed = []
        else:
            raise SystemExit(fam)
        plan = plan_from(rng, fixed)
        rewire_sand(f, plan)
        core = list(range(28, 34)) if 'core' in a.init else list(range(6))
        set_core(f, core)
        init_state(f, rng, a.init.replace('core', '').strip('_') or 'dense')
        if a.nodist:
            pass
        rebuild(f, rng)
        if a.nodist:
            closed, changes, prefix = [], [], 8
        else:
            closed = [(200, 1200), (1700, 2900)]
            changes = [101, 300, 1000, 1650, 2000, 2800, 3199]
            prefix = 3200
        res = run(f, rng, prefix, a.limit, closed, changes)
        res.update(seed=seed, family=fam, init=a.init, maxlen=a.maxlen, plan=plan,
                   lengths=[len(r.cells) for r in f.rs])
        slim = {k: v for k, v in res.items() if k not in ('batches', 'lengths', 'plan')}
        print(json.dumps(slim, ensure_ascii=False), flush=True)
        out.append(res)
        (HERE / a.output).write_text(json.dumps(out, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    main()

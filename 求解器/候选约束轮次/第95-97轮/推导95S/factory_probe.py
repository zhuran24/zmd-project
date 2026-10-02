#!/usr/bin/env python3
"""S95 whole-plant probes. Writes only next to this file; no geometry claim.

Engine A is the read-only 92D factory implementation. Engine B below is a
separately written age / due-date implementation. They share the instantiated
graph, not a transition function. All routes are directed belts, so temporary
receipt rule 1 agrees with receiver grouping: different routes have disjoint
internal cells, and an ineligible tail cannot alter any receiver state.
"""
import argparse
import hashlib
import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / '第92-94轮' / '推导92D' / 'factory_check.py'
spec = importlib.util.spec_from_file_location('s95_reference_a', BASE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EngineB:
    """No calls to A.step, A.flush or its state encoder."""
    def __init__(self, f):
        self.time = f.t
        self.units = f.ms + f.sources + [f.sink]
        self.index = {u: i for i, u in enumerate(self.units)}
        self.recipes = [u.recipe for u in self.units]
        self.stock = [dict(u.stock) for u in self.units]
        self.out = [u.out for u in self.units]
        self.due = [self.time + u.remaining - 1 if u.remaining else None for u in self.units]
        self.complete = [u.done for u in self.units]
        self.batches = [u.batches for u in f.ms] + [0] * (len(f.sources) + 1)
        self.paths = []
        self.cargo = []
        self.sent = []
        self.received = []
        self.last = []
        for r in f.rs:
            self.paths.append((self.index[r.source], self.index[r.target], r.kind))
            self.cargo.append([None if x is None else min(8, self.time - x) for x in r.cells])
            self.sent.append(r.count)
            self.received.append(0)
            self.last.append(r.source.sent[r.index])
        self.incoming = [[] for _ in self.units]
        self.outgoing = [[] for _ in self.units]
        for j, (a, b, _) in enumerate(self.paths):
            self.outgoing[a].append(j)
            self.incoming[b].append(j)
        self.cursor = [None] * len(self.units)
        self.shipped = Counter(f.delivered)
        self.open = f.open
        self.copy_order(f, reset=False)

    def copy_order(self, f, reset):
        self.rank = [r.source.order[r.index] for r in f.rs]
        for u, routes in f.incoming.items():
            j = self.index[u]
            self.incoming[j] = [r.index for r in routes]
            self.cursor[j] = u.cursor
        if reset:
            self.last = [-1] * len(self.paths)
            self.cursor = [None] * len(self.units)

    def release_batch(self, i):
        recipe = self.recipes[i]
        if recipe is not None and self.complete[i]:
            k = recipe[2]
            if self.out[i] <= 50 - k:
                self.out[i] += k
                self.complete[i] = False

    def step(self):
        now = self.time
        for i, recipe in enumerate(self.recipes):
            if recipe is None:
                continue
            if self.due[i] is not None and self.due[i] <= now:
                self.due[i] = None
                self.complete[i] = True
                self.batches[i] += 1
            self.release_batch(i)
        # Tail receipts, independently grouped by receiving unit.
        for target, routes in enumerate(self.incoming):
            if not routes:
                continue
            start = 0 if self.cursor[target] is None else (routes.index(self.cursor[target]) + 1) % len(routes)
            for r in routes[start:] + routes[:start]:
                _, _, item = self.paths[r]
                cells = self.cargo[r]
                if cells[-1] == 8:
                    if self.recipes[target] is None:
                        accept = self.open
                    else:
                        accept = self.stock[target].get(item, 0) < 50
                    if accept:
                        if self.recipes[target] is None:
                            self.shipped[item] += 1
                        else:
                            self.stock[target][item] = self.stock[target].get(item, 0) + 1
                        cells[-1] = None
                        self.cursor[target] = r
                        self.received[r] += 1
        # No two routes share a transport cell. All tails have judged above.
        for cells in self.cargo:
            for p in reversed(range(len(cells) - 1)):
                if cells[p] == 8 and cells[p + 1] is None:
                    cells[p] = None
                    cells[p + 1] = 0
        for source, routes in enumerate(self.outgoing):
            if self.recipes[source] is not None and self.out[source] == 0:
                continue
            available = [r for r in routes if self.cargo[r][0] is None]
            if available:
                r = min(available, key=lambda j: (self.last[j], self.rank[j]))
                self.cargo[r][0] = 0
                self.last[r] = now
                self.sent[r] += 1
                if self.recipes[source] is not None:
                    self.out[source] -= 1
                    self.release_batch(source)
        for i, recipe in enumerate(self.recipes):
            if recipe is None or self.due[i] is not None or self.complete[i]:
                continue
            ingredients, _, _, duration = recipe
            if all(self.stock[i].get(item, 0) >= q for item, q in ingredients.items()):
                for item, q in ingredients.items():
                    self.stock[i][item] -= q
                self.due[i] = now + duration
        for cells in self.cargo:
            for p, age in enumerate(cells):
                if age is not None:
                    cells[p] = min(8, age + 1)
        self.time += 1

    def compare(self, f):
        assert self.time == f.t
        for u in f.ms:
            i = self.index[u]
            assert all(self.stock[i].get(k, 0) == u.stock[k] for k in u.recipe[0]), (f.t, u.name, 'stock')
            assert self.out[i] == u.out, (f.t, u.name, 'output')
            remaining = 0 if self.due[i] is None else self.due[i] - self.time + 1
            assert remaining == u.remaining, (f.t, u.name, 'remaining', remaining, u.remaining)
            assert self.complete[i] == u.done, (f.t, u.name, 'cache')
            assert self.batches[i] == u.batches, (f.t, u.name, 'batches')
            assert self.cursor[i] == u.cursor, (f.t, u.name, 'input cursor')
        for r in f.rs:
            ages = [None if x is None else min(8, f.t - x) for x in r.cells]
            assert ages == self.cargo[r.index], (f.t, r.index, 'transport')
            assert self.sent[r.index] == r.count, (f.t, r.index, 'source count')
            assert self.last[r.index] == r.source.sent[r.index], (f.t, r.index, 'send history')
        assert self.shipped == f.delivered, (f.t, 'deliveries')


def rebuild_order(f, rng, reset=True):
    """Derive channel times from one permutation of all physical units.

    Cells of a continuous belt are separate buildable physical units. Channel
    creation time is the later build time of its two endpoints. Ties are
    resolved by stable route index as one admitted ordering, not a claim that
    arbitrary independent permutations of all channels can be built.
    """
    units = f.ms + f.sources + [f.sink]
    keys = [('u', i) for i in range(len(units))]
    keys += [('c', r.index, p) for r in f.rs for p in range(len(r.cells))]
    rng.shuffle(keys)
    # Sending and receiving representations belong to ONE physical core.
    # Shuffle then discard its receiving-side alias, preserving the recorded
    # random stream while yielding a permutation of actual physical units.
    sink_alias = ('u', len(units) - 1)
    keys = [key for key in keys if key != sink_alias]
    rank = {k: i for i, k in enumerate(keys)}
    ui = {u: i for i, u in enumerate(units)}
    ui[f.sink] = ui[f.core]
    for r in f.rs:
        r.source.order[r.index] = max(rank['u', ui[r.source]], rank['c', r.index, 0])
        r.target.accept_order[r.index] = max(rank['u', ui[r.target]], rank['c', r.index, len(r.cells) - 1])
    for u, routes in f.incoming.items():
        routes.sort(key=lambda r: (u.accept_order[r.index], r.index))
        if reset:
            u.cursor = None
    if reset:
        for u in f.ms + f.sources:
            u.sent = {r.index: -1 for r in u.routes}


def setup(seed, maxlen, initial, grouping, core_blue=6):
    f = module.Factory(seed, maxlen, 'random' if initial == 'random' else 'thin')
    rng = random.Random(seed * 131 + 95)
    assert 0 <= core_blue <= 6
    replace = list(f.core.routes[core_blue:])
    ore_routes = [r for r in f.ore_routes if r.kind == '源矿']
    for blue_route, ore_route in zip(replace, ore_routes):
        port = ore_route.source
        port.routes = [blue_route]
        f.core.routes.remove(blue_route)
        f.core.routes.append(ore_route)
        blue_route.source, ore_route.source = port, f.core
    if initial in ('dense', 'middle'):
        for u in f.ms:
            u.stock = Counter({item: 50 if initial == 'dense' else 25 for item in u.recipe[0]})
            u.out = 50 if initial == 'dense' else 25
            u.remaining = rng.randrange(1, u.recipe[3] + 1)
            u.done = False
        for r in f.rs:
            r.cells = [-rng.randrange(9) for _ in r.cells]
    if initial != 'low':
        # Full S09 starting reservoir, independent of downstream initialization.
        for c, a, b, k, ca, ac in f.units:
            for u in (c, a, b, k):
                u.stock = Counter({item: 50 for item in u.recipe[0]})
                u.out = 50
                u.remaining = rng.randrange(1, 8)
                u.done = False
            for r in (ca, ac, c.routes[1], b.routes[0]):
                r.cells = [-rng.randrange(9) for _ in r.cells]
    if grouping == 'separated':
        sand = [u[3] for u in f.units if u[3].name.startswith('砂叶')]
        targets = sorted((u for u in f.ms if u.name.startswith('铁研磨')), key=lambda x: int(x.name[3:]))
        targets += sorted((u for u in f.ms if u.name.startswith('源研磨')), key=lambda x: int(x.name[3:]))
        targets += sorted((u for u in f.ms if u.name.startswith('荞研磨')), key=lambda x: int(x.name[3:]))
        routes = [r for u in sand for r in u.routes]
        for r, target in zip(routes, targets):
            f.incoming[r.target].remove(r)
            r.target = target
            f.incoming[target].append(r)
    rebuild_order(f, rng, reset=True)
    return f, rng


def state_b(b):
    """Independent finite state key: ages and relative history ranks."""
    queues = []
    for routes in b.outgoing:
        queues.append(tuple(sorted(routes, key=lambda r: (b.last[r], b.rank[r]))))
    return (tuple(tuple(sorted(x.items())) for x in b.stock), tuple(b.out),
            tuple(None if d is None else d - b.time for d in b.due), tuple(b.complete),
            tuple(tuple(x) for x in b.cargo), tuple(b.cursor), tuple(queues))


def run_case(seed, maxlen, initial, grouping, limit, cross, disturbances=True, core_blue=6):
    f, rng = setup(seed, maxlen, initial, grouping, core_blue)
    b = EngineB(f) if cross else None
    if b:
        b.compare(f)
    # More than one input-order change; restored cargo ages and machine progress
    # are retained. Resetting histories tests the stronger reading of rebuild.
    prefix = 3200 if disturbances else 0
    closed = [(200, 1200), (1700, 2900)] if disturbances else []
    changes = [101, 300, 1000, 1650, 2000, 2800, 3199] if disturbances else []
    seen = {}
    seen_b = {}
    recent_window = None
    min_stock = 50
    min_phi2 = [10**9] * 17
    core_total = 0
    for _ in range(prefix + limit):
        t = f.t
        f.open = not any(a <= t < z for a, z in closed)
        if t in changes:
            rebuild_order(f, rng, reset=True)
            if b:
                b.copy_order(f, reset=True)
        if b:
            b.open = f.open
        f.step()
        if b:
            b.step()
            b.compare(f)
        if f.t == prefix + limit - 8000:
            recent_window = (f.t, dict(f.delivered), [r.count for r in f.ore_routes])
        min_phi2 = [min(a, p) for a, p in zip(min_phi2, f.phi2())]
        if f.t <= prefix or f.t % 8:
            continue
        # Both keys cap residence age at 8 and retain all order-relevant state.
        key = hashlib.sha256(repr(f.state()).encode()).hexdigest()
        kb = hashlib.sha256(repr(state_b(b)).encode()).hexdigest() if b else None
        counts = (f.t, dict(f.delivered), [r.count for r in f.ore_routes])
        if key in seen:
            old = seen[key]
            period = f.t - old[0]
            delivery = {k: f.delivered[k] - old[1].get(k, 0) for k in f.delivered}
            ore = [r.count - x for r, x in zip(f.ore_routes, old[2])]
            if b:
                assert kb in seen_b and seen_b[kb][0] == old[0], (seed, 'cycle key')
                bo = seen_b[kb]
                bdelivery = {k: b.shipped[k] - bo[1].get(k, 0) for k in b.shipped}
                bore = [b.sent[r.index] - n for r, n in zip(f.ore_routes, bo[2])]
                assert bdelivery == delivery and bore == ore
            return dict(seed=seed, maxlen=maxlen, initial=initial, grouping=grouping,
                        cross=cross, compared_steps=f.t if cross else 0,
                        cycle_start=old[0], cycle_end=f.t, period_steps=period,
                        deliveries=delivery, mineral_counts=ore,
                        pass_rates=all(x * 8 == period for x in ore)
                        and delivery['高容谷地电池'] * 40 == period * 3
                        and delivery['精选荞愈胶囊'] * 160 == period * 11,
                        min_phi2=min_phi2, closed=closed, rebuild_steps=changes,
                        machines=len(f.ms), routes=len(f.rs),
                        transport_cells=sum(len(r.cells) for r in f.rs),
                        core_outlets=len(f.core.routes), core_blue_outlets=core_blue)
        seen[key] = counts
        if b:
            seen_b[kb] = (b.time, dict(b.shipped), [b.sent[r.index] for r in f.ore_routes])
    window = None
    if recent_window:
        wt, wd, wo = recent_window
        window = dict(start=wt, end=f.t,
                      deliveries={k: f.delivered[k] - wd.get(k, 0) for k in f.delivered},
                      mineral_counts=[r.count - x for r, x in zip(f.ore_routes, wo)])
    return dict(seed=seed, maxlen=maxlen, initial=initial, grouping=grouping,
                status='inconclusive: no repeated state within bound', steps=f.t,
                compared_steps=f.t if cross else 0, final_window=window,
                final_phi2=f.phi2(), min_phi2=min_phi2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=9500)
    ap.add_argument('--count', type=int, default=1)
    ap.add_argument('--maxlen', type=int, default=3)
    ap.add_argument('--initial', choices=['dense', 'middle', 'random', 'low'], default='dense')
    ap.add_argument('--grouping', choices=['mixed', 'separated'], default='mixed')
    ap.add_argument('--core-blue', type=int, default=6)
    ap.add_argument('--limit', type=int, default=40000)
    ap.add_argument('--cross', action='store_true')
    ap.add_argument('--no-disturbances', action='store_true')
    ap.add_argument('--output', default='factory_cases.json')
    args = ap.parse_args()
    result = []
    for seed in range(args.seed, args.seed + args.count):
        one = run_case(seed, args.maxlen, args.initial, args.grouping, args.limit,
                       args.cross, not args.no_disturbances, args.core_blue)
        result.append(one)
        print(json.dumps(one, ensure_ascii=False), flush=True)
        (HERE / args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Pure-route event model written for review 84, not a game kernel.

Time is an integer multiple of 1/q tick. Each transfer is an individual
zero-time action. Fixed action order is swept to quiescence. Competing
ordinary source ports are overapproximated by this order; no result here
certifies a physical layout or replaces a universal proof.
"""
from dataclasses import dataclass, field
from collections import Counter
import random


@dataclass
class Machine:
    name: str
    inp: dict
    product: str
    batch: int = 1
    duration: int = 1
    stock: dict = field(default_factory=dict)
    out: int = 0
    finish: object = None
    starts: int = 0
    deposits: int = 0
    cache_product: object = None


@dataclass
class Route:
    name: str
    source: str
    dest: str
    item: str
    cells: list
    quota: object = None
    window: object = None
    used: int = 0
    supplied: int = 0
    delivered: int = 0


class Net:
    def __init__(self, q=1):
        self.q = q
        self.ms = {}
        self.rs = []
        self.stores = {}
        self.ores = set()
        self.actions = []
        self.t = 0
        self.output_floor = {}

    def machine(self, name, inp, product, batch=1, duration=1):
        self.ms[name] = Machine(name, inp, product, batch, duration)
        return name

    def route(self, source, dest, item, length=1, quota=None):
        assert length >= 1
        r = Route(str(len(self.rs)), source, dest, item, [None] * length, quota)
        self.rs.append(r)
        return r

    def prepare(self, seed=0):
        self.actions = [(kind, name, 0) for name in self.ms for kind in ('put', 'start')]
        self.actions += [('move', i, j) for i, r in enumerate(self.rs) for j in range(len(r.cells) + 1)]
        random.Random(seed).shuffle(self.actions)

    def source_has(self, name):
        if name in self.ms:
            return self.ms[name].out > 0
        if name in self.stores:
            return self.stores[name][0] > 0
        return name in self.ores

    def source_pop(self, name):
        if name in self.ms:
            m = self.ms[name]
            m.out -= 1
            self.output_floor[name] = min(self.output_floor.get(name, m.out), m.out)
        elif name in self.stores:
            self.stores[name][0] -= 1

    def destination_has_room(self, name, item):
        if name in self.ms:
            m = self.ms[name]
            assert item in m.inp, (name, item, m.inp)
            return m.stock.get(item, 0) < 50
        if name in self.stores:
            return self.stores[name][0] < self.stores[name][1]
        return True

    def destination_push(self, name, item):
        if name in self.ms:
            m = self.ms[name]
            m.stock[item] = m.stock.get(item, 0) + 1
        elif name in self.stores:
            self.stores[name][0] += 1

    def step_action(self, a, request):
        typ, i, j = a
        if typ != 'move':
            m = self.ms[i]
            if typ == 'put':
                if m.cache_product is not None and m.cache_product != m.product:
                    # Special witness: a completed old recipe has the other
                    # plant's product; the still nonempty output cannot mix.
                    assert m.out > 0, 'witness leaves the wrong-cache blocked regime'
                    return False
                if m.finish is not None and m.finish <= self.t and m.out + m.batch <= 50:
                    m.out += m.batch
                    m.finish = None
                    m.deposits += 1
                    return True
            elif m.finish is None and all(m.stock.get(x, 0) >= n for x, n in m.inp.items()):
                for x, n in m.inp.items():
                    m.stock[x] -= n
                m.finish = self.t + m.duration * self.q
                m.starts += 1
                return True
            return False
        r = self.rs[i]
        if j == 0:
            if r.cells[0] is not None or not self.source_has(r.source):
                return False
            if r.quota:
                if r.window is None or self.t >= r.window + 5 * self.q:
                    r.window, r.used = self.t, 0
                if r.used >= r.quota:
                    return False
                r.used += 1
            self.source_pop(r.source)
            r.cells[0] = self.t
            r.supplied += 1
            return True
        birth = r.cells[j - 1]
        if birth is None or self.t - birth < self.q:
            return False
        if j < len(r.cells):
            if r.cells[j] is not None:
                return False
            r.cells[j - 1], r.cells[j] = None, self.t
            return True
        if r.dest == 'sink' and not request(self.t, i):
            return False
        if not self.destination_has_room(r.dest, r.item):
            return False
        r.cells[-1] = None
        self.destination_push(r.dest, r.item)
        r.delivered += 1
        return True

    def settle(self, t, request=lambda t, i: True):
        self.t = t
        successes = 0
        while True:
            changed = False
            for a in self.actions:
                if self.step_action(a, request):
                    changed = True
                    successes += 1
            if not changed:
                break
            assert successes < 1000000, 'zero-time closure exceeded guard'
        return successes

    def key(self):
        def remaining(f):
            return None if f is None else max(0, f - self.t)
        machines = tuple((tuple(m.stock.get(x, 0) for x in m.inp), m.out, remaining(m.finish)) for m in self.ms.values())
        routes = tuple((tuple(None if b is None else min(self.q, self.t - b) for b in r.cells),
                        None if r.window is None or self.t >= r.window + 5 * self.q else (r.window + 5 * self.q - self.t, r.used)) for r in self.rs)
        return machines, routes, tuple((k, v[0]) for k, v in self.stores.items())


def plant(net, prefix='p', k=2, lengths=(1, 1, 1, 1)):
    seed, herb, powder = prefix + 'seed', prefix + 'herb', prefix + 'powder'
    c = net.machine(prefix + 'C', {herb: 1}, seed, 2)
    a = net.machine(prefix + 'A', {seed: 1}, herb)
    b = net.machine(prefix + 'B', {seed: 1}, herb)
    x = net.machine(prefix + 'K', {herb: 1}, powder, k)
    ca = net.route(c, a, seed, lengths[0])
    ac = net.route(a, c, herb, lengths[1])
    cb = net.route(c, b, seed, lengths[2])
    bx = net.route(b, x, herb, lengths[3])
    return (c, a, b, x), (ca, ac, cb, bx)


def phi(net, nodes, routes):
    c, a, _, _ = (net.ms[n] for n in nodes)
    ca, ac = routes[:2]
    return (sum(b is not None for b in ca.cells + ac.cells)
            + sum(a.stock.values()) + (a.finish is not None) + a.out
            + sum(c.stock.values()) + (c.finish is not None) + c.out / 2)


def skeleton(length=1):
    n = Net()
    n.ores.update(('ore_fe', 'ore_src'))
    def m(name, inp, out, k=1, d=1):
        return n.machine(name, inp, out, k, d)
    def route(a, b, item):
        return n.route(a, b, item, length)
    irons, source, grinders_fe, grinders_src, grinders_herb = [], [], [], [], []
    for j in range(34):
        f = m(f'f{j}', {'ore_fe': 1}, 'block')
        x = m(f'x{j}', {'block': 1}, 'fe_pow')
        route('ore_fe', f, 'ore_fe'); route(f, x, 'block')
        irons.append(x)
    for j in range(18):
        x = m(f'o{j}', {'ore_src': 1}, 'src_pow')
        route('ore_src', x, 'ore_src'); source.append(x)
    for j in range(17):
        g = m(f'gf{j}', {'fe_pow': 2, 'sand': 1}, 'dense_fe')
        for x in irons[2*j:2*j+2]: route(x, g, 'fe_pow')
        grinders_fe.append(g)
    for j in range(9):
        g = m(f'gs{j}', {'src_pow': 2, 'sand': 1}, 'dense_src')
        for x in source[2*j:2*j+2]: route(x, g, 'src_pow')
        grinders_src.append(g)
    plants = []
    for j in range(6):
        nodes, paths = plant(n, f'h{j}', 2, (length,) * 4)
        n.ms[nodes[3]].product = 'herb_pow'
        g = m(f'gh{j}', {'herb_pow': 2, 'sand': 1}, 'fine_herb')
        for _ in range(2): route(nodes[3], g, 'herb_pow')
        grinders_herb.append(g); plants.append((nodes, paths))
    recipients = grinders_fe + grinders_src + grinders_herb
    for j in range(11):
        nodes, paths = plant(n, f's{j}', 3, (length,) * 4)
        n.ms[nodes[3]].product = 'sand'
        for g in recipients[3*j:3*j+3]: route(nodes[3], g, 'sand')
        plants.append((nodes, paths))
    steels = []
    for j, g in enumerate(grinders_fe):
        s = m(f'steel{j}', {'dense_fe': 1}, 'steel')
        route(g, s, 'dense_fe'); steels.append(s)
    parts, bottles = [], []
    for j in range(6):
        p = m(f'parts{j}', {'steel': 1}, 'part')
        route(steels[j], p, 'steel'); parts.append(p)
        b = m(f'bottles{j}', {'steel': 2}, 'bottle')
        for s in steels[6+2*j:min(8+2*j,17)]: route(s, b, 'steel')
        bottles.append(b)
    for j in range(3):
        b = m(f'battery{j}', {'part': 10, 'dense_src': 15}, 'battery', d=5)
        for p in parts[2*j:2*j+2]: route(p, b, 'part')
        for g in grinders_src[3*j:3*j+3]: route(g, b, 'dense_src')
        route(b, 'sink', 'battery')
        c = m(f'capsule{j}', {'bottle': 10, 'fine_herb': 10}, 'capsule', d=5)
        for p in bottles[2*j:2*j+2]: route(p, c, 'bottle')
        for g in grinders_herb[2*j:2*j+2]: route(g, c, 'fine_herb')
        route(c, 'sink', 'capsule')
    for nodes, _ in plants:
        a = n.ms[nodes[1]]
        a.stock = {next(iter(a.inp)): 50}
    assert len(n.ms) == 221 and len(n.rs) == 317
    return n, plants

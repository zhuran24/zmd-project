from collections import Counter

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
                        accept = self.open if isinstance(self.open, bool) else self.open[item]
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


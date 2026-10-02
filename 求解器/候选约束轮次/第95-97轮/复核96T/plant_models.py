"""Independent review models; neither imports sim2 nor any derivation script.

The endpoint acceptance schedules overapproximate possible downstream machines.
They are tests of the universal argument, not certificates of a physical layout.
Each route is a forward chain. Single-axis bridge scheduling is checked separately.
Model A uses absolute entry/completion times and last-success timestamps.
Model B uses countdowns, sparse cells, and a recency queue.
"""
import copy

PAIRS = [('C', 'A'), ('A', 'C'), ('C', 'B'), ('B', 'K')]
NAMES = ['C', 'A', 'B', 'K']


class AbsolutePlant:
    def __init__(self, init):
        self.k, self.n = init['k'], init['n']
        self.cap = init.get('cap', 50)
        self.products = dict(C=2, A=1, B=1, K=self.k)
        self.ins = dict(zip(NAMES, init['ins']))
        self.outs = dict(zip(NAMES, init['outs']))
        self.due = {m: None if r is None else -1+r
                    for m, r in zip(NAMES, init['remaining'])}
        self.roads = [[None if a is None else -1-a for a in r]
                      for r in init['ages']]
        self.last = {'C': list(init['lastC']), 'K': list(init['lastK'])}
        self.build = {'C': list(range(2)), 'K': list(range(self.n))}
        self.starts = dict.fromkeys(NAMES, 0)
        self.sent = dict.fromkeys(NAMES, 0)
        self.events = []

    def flush(self, m, t):
        if self.due[m] is not None and self.due[m] <= t:
            if self.outs[m]+self.products[m] <= self.cap:
                self.outs[m] += self.products[m]
                self.due[m] = None

    def choices(self, m):
        indices = range(len(self.last[m]))
        return sorted(indices, key=lambda j: (
            self.last[m][j] is not None,
            self.last[m][j] if self.last[m][j] is not None
            else self.build[m].index(j)))

    def step(self, t, accepts, order, builds, enabled):
        self.events = []
        self.build = builds
        for m in NAMES:
            if not enabled[m] and self.due[m] is not None and self.due[m] >= t:
                self.due[m] += 1
            self.flush(m, t)
        empty_before_sources = []
        for ri, r in enumerate(self.roads):
            for i in range(len(r)-1, -1, -1):
                entered = r[i]
                if entered is None or t-entered < 8:
                    continue
                if i+1 < len(r):
                    if r[i+1] is None:
                        r[i+1], r[i] = t, None
                elif ri < 4:
                    dst = PAIRS[ri][1]
                    if self.ins[dst] < self.cap:
                        self.ins[dst] += 1
                        r[i] = None
                elif accepts[ri-4]:
                    r[i] = None
            empty_before_sources.append(r[0] is None)
        for m in order:
            if not self.outs[m]:
                continue
            if m == 'C':
                options = [(j, [0, 2][j]) for j in self.choices(m)]
            elif m == 'K':
                options = [(j, 4+j) for j in self.choices(m)]
            else:
                options = [(0, 1 if m == 'A' else 3)]
            for j, ri in options:
                if self.roads[ri][0] is None:
                    self.roads[ri][0] = t
                    self.outs[m] -= 1
                    self.sent[m] += 1
                    self.events.append((m, ri))
                    if m in self.last:
                        self.last[m][j] = t
                    self.flush(m, t)
                    break
        for m in NAMES:
            if enabled[m] and self.due[m] is None and self.ins[m]:
                self.ins[m] -= 1
                self.due[m] = t+8
                self.starts[m] += 1
        return empty_before_sources

    def state(self, t):
        return (tuple(self.ins[m] for m in NAMES),
                tuple(self.outs[m] for m in NAMES),
                tuple(None if self.due[m] is None else max(0, self.due[m]-t)
                      for m in NAMES),
                tuple(tuple(None if x is None else min(8, t-x) for x in r)
                      for r in self.roads),
                tuple(tuple(self.choices(m)) for m in ('C', 'K')))

    def phi2(self):
        return 2*(sum(x is not None for r in self.roads[:2] for x in r)
                  +self.ins['A']+self.outs['A']+self.ins['C']
                  +int(self.due['A'] is not None)+int(self.due['C'] is not None)) \
                  +self.outs['C']


class CountdownPlant:
    def __init__(self, init):
        self.capacity = init.get('cap', 50)
        self.amount = [2, 1, 1, init['k']]
        self.stock = list(init['ins'])
        self.ready = list(init['outs'])
        self.batch = [-1 if r is None else r for r in init['remaining']]
        self.lengths = list(map(len, init['ages']))
        self.cells = {(r, i): 8-a for r, road in enumerate(init['ages'])
                      for i, a in enumerate(road) if a is not None}
        self.dest = [1, 0, 2, 3]+[-1]*init['n']
        self.routes = [[0, 2], [1], [3], list(range(4, 4+init['n']))]
        self.never, self.queue = {}, {}
        for m, times in [(0, init['lastC']), (3, init['lastK'])]:
            self.never[m] = {j for j, v in enumerate(times) if v is None}
            self.queue[m] = sorted((j for j, v in enumerate(times) if v is not None),
                                   key=lambda j: times[j])
        self.current_build = {0: list(range(2)), 3: list(range(init['n']))}
        self.events = []

    def transfer_batch(self, m):
        if self.batch[m] == 0 and self.ready[m] <= self.capacity-self.amount[m]:
            self.ready[m] += self.amount[m]
            self.batch[m] = -1

    def ordered(self, m):
        return [j for j in self.current_build[m] if j in self.never[m]]+self.queue[m]

    def step(self, t, accepts, order, builds, enabled):
        self.events = []
        self.current_build = {0: builds['C'], 3: builds['K']}
        for m in range(4):
            if enabled[NAMES[m]] and self.batch[m] > 0:
                self.batch[m] -= 1
            self.transfer_batch(m)
        for loc in self.cells:
            self.cells[loc] = max(0, self.cells[loc]-1)
        # Ready locations are collected once. A newly moved item cannot move twice.
        candidates = sorted((loc for loc, wait in self.cells.items() if wait == 0),
                            key=lambda loc: (loc[0], -loc[1]))
        for r, pos in candidates:
            if pos+1 == self.lengths[r]:
                m = self.dest[r]
                if m >= 0:
                    if self.stock[m] == self.capacity:
                        continue
                    self.stock[m] += 1
                elif not accepts[r-4]:
                    continue
            else:
                nxt = (r, pos+1)
                if nxt in self.cells:
                    continue
                self.cells[nxt] = 8
            del self.cells[(r, pos)]
        empty_before_sources = [(r, 0) not in self.cells for r in range(len(self.lengths))]
        for label in order:
            m = NAMES.index(label)
            if not self.ready[m]:
                continue
            ports = self.ordered(m) if m in self.queue else [0]
            chosen = next((j for j in ports if (self.routes[m][j], 0) not in self.cells), None)
            if chosen is not None:
                r = self.routes[m][chosen]
                self.ready[m] -= 1
                self.cells[(r, 0)] = 8
                self.events.append((label, r))
                if m in self.queue:
                    self.never[m].discard(chosen)
                    if chosen in self.queue[m]:
                        self.queue[m].remove(chosen)
                    self.queue[m].append(chosen)
                self.transfer_batch(m)
        for m in range(4):
            if enabled[NAMES[m]] and self.batch[m] == -1 and self.stock[m] > 0:
                self.stock[m] -= 1
                self.batch[m] = 8
        return empty_before_sources

    def state(self, t):
        return (tuple(self.stock), tuple(self.ready),
                tuple(None if p < 0 else p for p in self.batch),
                tuple(tuple(None if (r, i) not in self.cells else 8-self.cells[r, i]
                            for i in range(n)) for r, n in enumerate(self.lengths)),
                (tuple(self.ordered(0)), tuple(self.ordered(3))))

    def phi2(self):
        weighted = self.ready[0]
        weighted += sum(2 for r, _ in self.cells if r in (0, 1))
        weighted += 2*(self.stock[1]+self.ready[1]+self.stock[0])
        weighted += sum(2 for i in (0, 1) if self.batch[i] != -1)
        return weighted

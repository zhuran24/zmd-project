#!/usr/bin/env python3
"""Independent implementation A: plant unit, per-cell objects, integer steps.

No project simulator is imported. All four routes are uninterrupted belts.
K has two buckwheat-powder routes to one grinding machine without sand powder.
The latter's main-ingredient storage can accept 50 pieces and cannot start.
Each manufacturing judgment sends at most one piece. Manufacturing duration
is eight steps; transportation residence is at least eight steps per unit.
"""
import copy
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


class Cell:
    def __init__(self):
        self.enter = None


class Factory:
    def __init__(self, qty):
        self.stock = 0
        self.output = 0
        self.qty = qty
        self.batch = None  # None, ('running', finish), ('ready', qty)
        self.started = self.finished = 0
        self.enabled = True

    def flush(self):
        if self.batch and self.batch[0] == 'ready' and self.output + self.qty <= 50:
            self.output += self.qty
            self.batch = None


class Plant:
    def __init__(self, lengths=(7, 13, 31, 5, 5, 5), order=('A', 'B', 'C', 'K'),
                 route_order=('CA', 'CB', 'AC', 'BK', 'K0', 'K1'), sink_limit=50):
        self.t = 0
        self.machines = {x: Factory(2 if x in ('C', 'K') else 1) for x in 'ABCK'}
        self.end = {'CA': 'A', 'CB': 'B', 'AC': 'C', 'BK': 'K', 'K0': 'G', 'K1': 'G'}
        self.start = {'CA': 'C', 'CB': 'C', 'AC': 'A', 'BK': 'B', 'K0': 'K', 'K1': 'K'}
        self.routes = {r: [Cell() for _ in range(n)] for r, n in zip(self.end, lengths)}
        self.order, self.route_order = order, route_order
        self.rank = {r: i for i, r in enumerate(route_order)}
        self.last = {r: -1 for r in self.routes}
        self.sent = {r: 0 for r in self.routes}
        self.arrivals = {r: 0 for r in self.routes}
        self.sink = 0
        self.sink_limit = sink_limit
        self.receive_last = None
        self.trace = []

    def move_inside(self, route):
        cells = self.routes[route]
        for i in range(len(cells) - 2, -1, -1):
            if cells[i].enter is not None and self.t - cells[i].enter >= 8 and cells[i+1].enter is None:
                cells[i+1].enter, cells[i].enter = self.t, None

    def phi2(self):
        m = self.machines
        return (2 * (sum(c.enter is not None for c in self.routes['CA']) + m['A'].stock
                     + m['A'].output + sum(c.enter is not None for c in self.routes['AC'])
                     + m['C'].stock + (m['A'].batch is not None) + (m['C'].batch is not None))
                + m['C'].output)

    def state(self):
        return dict(step=self.t, phi2=self.phi2(),
                    stock={x: m.stock for x, m in self.machines.items()},
                    output={x: m.output for x, m in self.machines.items()},
                    batch={x: m.batch for x, m in self.machines.items()},
                    enabled={x: m.enabled for x, m in self.machines.items()},
                    route_counts={r: sum(c.enter is not None for c in cells) for r, cells in self.routes.items()},
                    sink=self.sink, sent=self.sent.copy(), arrivals=self.arrivals.copy())

    def canonical(self):
        return (self.t, tuple((x, m.stock, m.output, m.batch, m.started, m.finished, m.enabled)
                            for x, m in sorted(self.machines.items())),
                tuple((r, tuple(c.enter for c in cells), self.last[r], self.sent[r], self.arrivals[r])
                      for r, cells in sorted(self.routes.items())), self.sink, self.receive_last)

    def add(self, x, qty):
        m = self.machines[x]
        if m.stock + qty > 50:
            return False
        m.stock += qty
        return True

    def step(self):
        # End manufacture; internal belt motion is always attempted.
        for m in self.machines.values():
            if m.batch and m.batch[0] == 'running' and not m.enabled:
                m.batch = ('running', m.batch[1]+1)
            if m.batch and m.batch[0] == 'running' and m.batch[1] == self.t:
                m.batch = ('ready', m.qty)
                m.finished += 1
            m.flush()
        for r in self.routes:
            self.move_inside(r)
        judged = set()
        for route in self.route_order:
            if route in judged:
                continue
            dst = self.end[route]
            group = [r for r in self.routes if self.end[r] == dst]
            group.sort(key=lambda r: self.rank[r])
            if dst == 'G' and self.receive_last in group:
                k = group.index(self.receive_last) + 1
                group = group[k:] + group[:k]
            for r in group:
                judged.add(r)
                cell = self.routes[r][-1]
                if cell.enter is None or self.t - cell.enter < 8:
                    continue
                if dst == 'G':
                    accepts = self.sink < self.sink_limit
                else:
                    accepts = self.machines[dst].stock < 50
                if accepts:
                    cell.enter = None
                    self.arrivals[r] += 1
                    if dst == 'G':
                        self.sink += 1
                        self.receive_last = r
                    else:
                        self.machines[dst].stock += 1
                    self.move_inside(r)
        # All nontransport units act after every belt component.
        for x in self.order:
            m = self.machines[x]
            if not m.output:
                continue
            choices = sorted((r for r in self.routes if self.start[r] == x),
                             key=lambda r: (self.last[r], self.rank[r]))
            for r in choices:
                if self.routes[r][0].enter is None:
                    self.routes[r][0].enter = self.t
                    self.last[r] = self.t
                    self.sent[r] += 1
                    m.output -= 1
                    m.flush()
                    break
        for m in self.machines.values():
            if m.enabled and m.batch is None and m.stock:
                m.stock -= 1
                m.batch = ('running', self.t + 8)
                m.started += 1
        self.t += 1


def delayed_insertion(lengths=(7, 13, 31, 5, 5, 5), horizon=30000):
    w = Plant(lengths)
    w.add('A', 50)
    initial = w.state()
    first_nonempty = first_full = None
    minimum = w.phi2()
    for _ in range(horizon):
        w.step()
        minimum = min(minimum, w.phi2())
        if w.machines['C'].stock and first_nonempty is None:
            first_nonempty = w.state()
        if w.machines['C'].stock == 50:
            first_full = w.state()
            break
    assert first_full is not None
    accepted = w.add('C', 50)
    assert not accepted
    return dict(lengths=lengths, initial=initial, first_nonempty=first_nonempty,
                first_full=first_full, second_50_accepted=accepted, minimum_phi2=minimum)


def joint_insertion(lengths, horizon=10000):
    w = Plant(lengths, sink_limit=10**9)
    assert w.add('A', 50) and w.add('C', 50)
    low = w.phi2()
    for _ in range(horizon):
        w.step()
        low = min(low, w.phi2())
    return dict(lengths=lengths, minimum_phi2=low, end=w.state())


def main():
    results = dict(implementation='A', delayed=delayed_insertion(),
                   joint=[joint_insertion(z) for z in ((7,13,31,5,5,5), (48,7,49,5,3,3), (49,7,49,5,3,3))])
    (OUT / 'plant_a.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(delayed_step=results['delayed']['first_full']['step'],
                         first_nonempty_step=results['delayed']['first_nonempty']['step'],
                         joint_minimum_phi2=[x['minimum_phi2'] for x in results['joint']]), ensure_ascii=False))


if __name__ == '__main__':
    main()

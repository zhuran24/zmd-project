"""Independent reproduction of the report's actual seed circulation layout.

Two implementations use absolute birth times / countdown slots respectively.
The geometry and both physical-unit construction permutations are checked here.
No code or numeric data is imported from the derivation seat.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
LONG_A = [(x, 10) for x in range(1, 5)]+[(4, y) for y in range(11, 15)]+[
    (x, 14) for x in range(5, 9)]+[(8, y) for y in range(13, 9, -1)]
LONG_B = [(x, 2) for x in range(1, 12)]+[(11, y) for y in range(3, 8)]
COORDS = dict(P=(9, 10), S=(10, 10), M=(11, 10), N=(10, 11),
              U=(11, 9), Q=(11, 8), R0=(12, 10), T0=(11, 11), T1=(12, 11))
COORDS.update({f'A{i}': xy for i, xy in enumerate(LONG_A)})
COORDS.update({f'B{i}': xy for i, xy in enumerate(LONG_B)})
COMPONENTS = [[f'A{i}' for i in range(16)], [f'B{i}' for i in range(16)],
              ['R0'], ['T0', 'T1']]
EDGES = {f'A{i}': [f'A{i+1}' if i < 15 else 'P'] for i in range(16)}
EDGES.update({f'B{i}': [f'B{i+1}' if i < 15 else 'Q'] for i in range(16)})
EDGES.update(P=['S'], Q=['U'], U=['M'], S=['M', 'N'], M=['R0'], N=['T0'],
             R0=['core'], T0=['T1'], T1=['core'], W1=['A0'], W2=['B0'])


def geometry_and_builds():
    occupied = {}
    shape = dict(core=[(x, y) for x in range(13, 22) for y in range(9, 18)],
                 W1=[(0, y) for y in range(9, 12)], W2=[(0, y) for y in range(1, 4)])
    shape.update({u: [xy] for u, xy in COORDS.items()})
    for name, cells in shape.items():
        for xy in cells:
            assert all(0 <= a < 70 for a in xy) and xy not in occupied
            occupied[xy] = name
    assert len(LONG_A) == len(LONG_B) == 16
    incoming = {u: set() for u in COORDS}
    outgoing = {u: set() for u in COORDS}
    full_edges = [(u, v) for u, vs in EDGES.items() for v in vs]
    for u, v in full_edges:
        src = (0, 10) if u == 'W1' else (0, 2) if u == 'W2' else COORDS[u]
        dst = (13, src[1]) if v == 'core' else COORDS[v]
        assert sum(abs(x-y) for x, y in zip(src, dst)) == 1
        direction = (dst[0]-src[0], dst[1]-src[1])
        if u in outgoing:
            outgoing[u].add(direction)
        if v in incoming:
            incoming[v].add((-direction[0], -direction[1]))
        if v == 'core':
            assert dst[1]-9 in range(1, 8)
    cardinal = {(1, 0), (-1, 0), (0, 1), (0, -1)}
    for u in COORDS:
        if u in ('M', 'N'):
            incoming[u] = cardinal-outgoing[u]
        if u == 'S':
            outgoing[u] = cardinal-incoming[u]
    # Check automatic port contacts, including unintended adjacent contacts.
    actual = set()
    at = {xy: u for u, xy in COORDS.items()}
    at.update({(0, 10): 'W1', (0, 2): 'W2'})
    for u, xy in COORDS.items():
        for dx, dy in outgoing[u]:
            target_xy = (xy[0]+dx, xy[1]+dy)
            v = at.get(target_xy)
            if v in incoming and (-dx, -dy) in incoming[v]:
                actual.add((u, v))
            elif target_xy[0] == 13 and target_xy[1] in range(10, 17):
                actual.add((u, 'core'))
    actual.update([('W1', 'A0'), ('W2', 'B0')])
    assert actual == set(full_edges), (actual-set(full_edges), set(full_edges)-actual)
    builds = {}
    for mode, special in [('U', ['M', 'U', 'S', 'N', 'P', 'Q']),
                          ('S', ['M', 'S', 'N', 'U', 'P', 'Q'])]:
        names = ['core', 'W1', 'W2']+special+sum(COMPONENTS, [])
        constructed = {u: i for i, u in enumerate(names)}
        direct = {f'{u}>{v}': max(constructed[u], constructed[v]) for u, v in full_edges}
        events = {}
        present = set()
        for i, u in enumerate(names):
            present.add(u)
            for a, b in full_edges:
                if a in present and b in present:
                    events.setdefault(f'{a}>{b}', i)
        assert direct == events
        assert direct['S>M'] < direct['S>N']
        assert (direct['U>M'] < direct['S>M']) == (mode == 'U')
        builds[mode] = dict(unit_order=names, channel_times=direct)
    return dict(occupied_cells=len(occupied), physical_transport_units=len(COORDS),
                incoming={u: sorted(v) for u, v in incoming.items()},
                outgoing={u: sorted(v) for u, v in outgoing.items()}, builds=builds)


def judge_order(mode):
    return [['R0'], ['T0', 'T1'], ['M'], ['N']]+[
        [v] for v in (['U', 'S'] if mode == 'U' else ['S', 'U'])]+[
        ['P'], ['Q'], COMPONENTS[0], COMPONENTS[1]]


class BirthTimes:
    def __init__(self, mode):
        self.holds = {u: None for u in COORDS}
        self.window_start = {'P': None, 'Q': None}
        self.next_split = 1
        self.warehouse = 80000
        self.order = judge_order(mode)
        self.events = []

    def accept(self, v, t):
        if v == 'core':
            return self.warehouse < 80000
        if self.holds[v] is not None:
            return False
        if v in self.window_start:
            started = self.window_start[v]
            if started is not None and t-started < 40:
                return False
        return True

    def move(self, u, v, t):
        if not self.accept(v, t):
            return False
        if u in self.holds:
            self.holds[u] = None
        else:
            assert self.warehouse > 0
            self.warehouse -= 1
        if v == 'core':
            self.warehouse += 1
        else:
            self.holds[v] = t
        if v in self.window_start:
            self.window_start[v] = t
        self.events.append((u, v))
        return True

    def step(self, t):
        self.events = []
        for component in self.order:
            for u in reversed(component):
                if self.holds[u] is None or t-self.holds[u] < 8:
                    continue
                outputs = EDGES[u]
                if u == 'S':
                    outputs = [EDGES[u][self.next_split], EDGES[u][1-self.next_split]]
                for v in outputs:
                    if self.move(u, v, t):
                        if u == 'S':
                            self.next_split = 1-EDGES[u].index(v)
                        break
        for source in ['W1', 'W2']:
            if self.warehouse:
                self.move(source, EDGES[source][0], t)

    def state(self, t):
        return (tuple(None if self.holds[u] is None else min(8, t-self.holds[u]) for u in sorted(COORDS)),
                tuple(0 if self.window_start[u] is None else max(0, self.window_start[u]+40-t)
                      for u in ['P', 'Q']), self.next_split, self.warehouse)


class Timers:
    def __init__(self, mode):
        self.keys = sorted(COORDS)
        self.index = {u: i for i, u in enumerate(self.keys)}
        self.slots = [-1]*len(self.keys)  # -1 empty, 0 ready, 1..8 cooling
        self.quotas = [0, 0]
        self.pointer = 1
        self.inventory = 80000
        self.destinations = {self.index[u]: [self.index.get(v, -1) for v in vs]
                             for u, vs in EDGES.items() if u in self.index}
        self.order = [self.index[u] for component in judge_order(mode) for u in reversed(component)]
        self.gates = {self.index['P']: 0, self.index['Q']: 1}
        self.split = self.index['S']
        self.events = []

    def step(self, t):
        self.events = []
        self.slots = [max(0, v-1) if v >= 0 else -1 for v in self.slots]
        self.quotas = [max(0, v-1) for v in self.quotas]
        for u in self.order:
            if self.slots[u] != 0:
                continue
            targets = self.destinations[u]
            if u == self.split:
                targets = [targets[self.pointer], targets[1-self.pointer]]
            for v in targets:
                if v == -1:
                    if self.inventory == 80000:
                        continue
                    self.inventory += 1
                else:
                    if self.slots[v] != -1 or (v in self.gates and self.quotas[self.gates[v]]):
                        continue
                    self.slots[v] = 8
                    if v in self.gates:
                        self.quotas[self.gates[v]] = 40
                self.slots[u] = -1
                if u == self.split:
                    self.pointer = 1-self.destinations[u].index(v)
                self.events.append((self.keys[u], 'core' if v == -1 else self.keys[v]))
                break
        for source, target in [('W1', 'A0'), ('W2', 'B0')]:
            i = self.index[target]
            if self.inventory and self.slots[i] == -1:
                self.inventory -= 1
                self.slots[i] = 8
                self.events.append((source, target))

    def state(self, t):
        return (tuple(None if v == -1 else 8-v for v in self.slots),
                tuple(self.quotas), self.pointer, self.inventory)


def run():
    geometry = geometry_and_builds()
    result = {'geometry': geometry, 'cycles': {}}
    for mode in ['U', 'S']:
        a, b = BirthTimes(mode), Timers(mode)
        visited, trace, first_cycle = {}, [], None
        minimum = 80000
        for t in range(3000):
            a.step(t)
            b.step(t)
            assert a.state(t) == b.state(t) and a.events == b.events, (mode, t)
            minimum = min(minimum, a.warehouse)
            trace.append(dict(step=t, moves=a.events[:], state=a.state(t)))
            state = a.state(t)
            if first_cycle is None and state in visited:
                start = visited[state]
                period = t-start
                selected = [event for row in trace[start+1:t+1] for event in row['moves']]
                links = [('S', 'M'), ('S', 'N'), ('U', 'M')]
                count = {f'{u}>{v}': selected.count((u, v)) for u, v in links}
                first_cycle = dict(first=start, second=t, period_steps=period,
                                   counts=count, rates={edge: str(Fraction(8*n, period)) for edge, n in count.items()})
            visited.setdefault(state, t)
        first_cycle['minimum_warehouse'] = minimum
        first_cycle['compared_steps'] = len(trace)
        result['cycles'][mode] = first_cycle
        left, right = first_cycle['first'], first_cycle['second']
        (HERE/f'density_trace_{mode}.json').write_text(json.dumps(
            dict(mode=mode, cycle=first_cycle, trace=trace[max(0, left-8):right+1]),
            ensure_ascii=False, indent=2)+'\n')
    (HERE/'density_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result['cycles'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()

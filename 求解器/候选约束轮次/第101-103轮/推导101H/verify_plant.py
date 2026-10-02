"""Independent absolute-time / countdown checks for the four-machine unit.

The four internal routes are forward chains. verify_bridges.py separately
checks that the stated single-axis topology has this step semantics.
Output acceptance is an overapproximation of downstream service.
"""
from pathlib import Path
import hashlib
import json
import random

OUT = Path(__file__).resolve().parent
NAMES = ("C", "A", "B", "K")
TARGET = (1, 0, 2, 3)


class Absolute:
    def __init__(self, config):
        self.input = config["input"][:]
        self.output = config["output"][:]
        self.product = [2, 1, 1, config["k"]]
        self.batch = [None if x is None else -1+x for x in config["remaining"]]
        self.roads = [[None if a is None else -1-a for a in road] for road in config["ages"]]
        self.history = {0: config["lastC"][:], 3: config["lastK"][:]}
        self.connections = {0: [0, 1], 3: list(range(config["n"]))}
        self.events = []
        self.starts = [0]*4

    def order(self, m):
        return sorted(range(len(self.history[m])), key=lambda j: (
            self.history[m][j] is not None,
            self.history[m][j] if self.history[m][j] is not None else self.connections[m].index(j)))

    def offline(self, ports, clear):
        self.connections = {m: ports[m][:] for m in (0, 3)}
        if clear:
            self.history = {m: [None]*len(self.history[m]) for m in (0, 3)}

    def flush(self, m, t):
        if self.batch[m] is not None and self.batch[m] <= t:
            if self.output[m] + self.product[m] <= 50:
                self.output[m] += self.product[m]
                self.batch[m] = None

    def step(self, t, on, sinks, machine_order):
        self.events = []
        for m in range(4):
            if not on[m] and self.batch[m] is not None and self.batch[m] >= t:
                self.batch[m] += 1
            self.flush(m, t)
        for r, road in enumerate(self.roads):
            for pos in range(len(road)-1, -1, -1):
                if road[pos] is None or t-road[pos] < 8:
                    continue
                if pos+1 < len(road):
                    if road[pos+1] is not None:
                        continue
                    road[pos+1] = t
                elif r < 4:
                    if self.input[TARGET[r]] == 50:
                        continue
                    self.input[TARGET[r]] += 1
                elif not sinks[r-4]:
                    continue
                road[pos] = None
        empty = [r[0] is None for r in self.roads]
        for m in machine_order:
            if not self.output[m]:
                continue
            route_ids = [0, 2] if m == 0 else [1] if m == 1 else [3] if m == 2 else list(range(4, len(self.roads)))
            choices = self.order(m) if m in self.history else [0]
            for j in choices:
                r = route_ids[j]
                if self.roads[r][0] is None:
                    self.roads[r][0] = t
                    self.output[m] -= 1
                    if m in self.history:
                        self.history[m][j] = t
                    self.events.append([m, r])
                    self.flush(m, t)
                    break
        for m in range(4):
            if on[m] and self.batch[m] is None and self.input[m]:
                self.input[m] -= 1
                self.batch[m] = t+8
                self.starts[m] += 1
        return empty

    def state(self, t):
        return [self.input[:], self.output[:],
                [None if d is None else max(0, d-t) for d in self.batch],
                [[None if e is None else min(8, t-e) for e in road] for road in self.roads],
                [[self.order(m), [h is None for h in self.history[m]]] for m in (0, 3)]]

    def phi2(self):
        return (2*(sum(e is not None for road in self.roads[:2] for e in road)
                   + self.input[1]+self.output[1]+self.input[0]
                   +int(self.batch[0] is not None)+int(self.batch[1] is not None))
                + self.output[0])


class Remaining:
    def __init__(self, config):
        self.stock = {m: config["input"][m] for m in range(4)}
        self.ready = dict(enumerate(config["output"]))
        self.wait = {m: (-1 if x is None else x) for m, x in enumerate(config["remaining"])}
        self.yield_n = {0: 2, 1: 1, 2: 1, 3: config["k"]}
        self.length = list(map(len, config["ages"]))
        self.cells = {(r, p): max(0, 8-age) for r, road in enumerate(config["ages"])
                      for p, age in enumerate(road) if age is not None}
        self.route_map = {0: [0, 2], 1: [1], 2: [3], 3: list(range(4, 4+config["n"]))}
        self.unused, self.recent = {}, {}
        for m, times in ((0, config["lastC"]), (3, config["lastK"])):
            self.unused[m] = set(j for j, h in enumerate(times) if h is None)
            self.recent[m] = sorted((j for j, h in enumerate(times) if h is not None), key=times.__getitem__)
        self.connections = {0: [0, 1], 3: list(range(config["n"]))}
        self.events = []
        self.starts = [0]*4

    def offline(self, ports, clear):
        self.connections = {m: list(ports[m]) for m in (0, 3)}
        if clear:
            for m in (0, 3):
                self.unused[m] = set(range(len(self.route_map[m])))
                self.recent[m] = []

    def scan(self, m):
        return [j for j in self.connections[m] if j in self.unused[m]] + self.recent[m]

    def unload(self, m):
        if self.wait[m] == 0 and 50-self.ready[m] >= self.yield_n[m]:
            self.ready[m] += self.yield_n[m]
            self.wait[m] = -1

    def step(self, step, on, sinks, machine_order):
        self.events = []
        for m in self.wait:
            if on[m] and self.wait[m] > 0:
                self.wait[m] -= 1
            self.unload(m)
        for loc in list(self.cells):
            self.cells[loc] = max(0, self.cells[loc]-1)
        active = sorted((loc for loc in self.cells if self.cells[loc] == 0),
                        key=lambda loc: (loc[0], -loc[1]))
        for r, p in active:
            if p+1 == self.length[r]:
                if r >= 4:
                    if not sinks[r-4]:
                        continue
                else:
                    receiver = TARGET[r]
                    if self.stock[receiver] >= 50:
                        continue
                    self.stock[receiver] += 1
            else:
                destination = r, p+1
                if destination in self.cells:
                    continue
                self.cells[destination] = 8
            del self.cells[r, p]
        empty = [(r, 0) not in self.cells for r in range(len(self.length))]
        for m in machine_order:
            if self.ready[m] == 0:
                continue
            ports = self.scan(m) if m in self.recent else [0]
            available = [p for p in ports if (self.route_map[m][p], 0) not in self.cells]
            if not available:
                continue
            p = available[0]
            r = self.route_map[m][p]
            self.cells[r, 0] = 8
            self.ready[m] -= 1
            if m in self.recent:
                self.unused[m].discard(p)
                self.recent[m] = [j for j in self.recent[m] if j != p] + [p]
            self.events.append([m, r])
            self.unload(m)
        for m in range(4):
            if self.wait[m] < 0 and self.stock[m] > 0 and on[m]:
                self.stock[m] -= 1
                self.wait[m] = 8
                self.starts[m] += 1
        return empty

    def state(self, step):
        return [[self.stock[m] for m in range(4)], [self.ready[m] for m in range(4)],
                [None if self.wait[m] < 0 else self.wait[m] for m in range(4)],
                [[None if (r, p) not in self.cells else 8-self.cells[r, p] for p in range(n)]
                 for r, n in enumerate(self.length)],
                [[self.scan(m), [j in self.unused[m] for j in range(len(self.route_map[m]))]] for m in (0, 3)]]

    def phi2(self):
        score = self.ready[0] + 2*(self.stock[0]+self.stock[1]+self.ready[1])
        score += 2*sum(r < 2 for r, p in self.cells)
        score += 2*sum(self.wait[m] >= 0 for m in (0, 1))
        return score


def parameters(rng, full):
    k = rng.choice([2, 3])
    n = rng.randrange(k+1)
    ages = [[rng.randrange(9) if full or rng.randrange(3) else None
             for _ in range(rng.randrange(1, 7))] for _ in range(4)]
    ages += [[None] for _ in range(n)]
    return dict(k=k, n=n, input=[50]*4 if full else [rng.randrange(51) for _ in range(4)],
                output=[50]*4 if full else [rng.randrange(51) for _ in range(4)],
                remaining=[rng.randrange(9) for _ in range(4)] if full
                    else [rng.choice([None, 0, 1, 3, 7, 8]) for _ in range(4)],
                ages=ages, lastC=[None, None], lastK=[None]*n)


def run_case(config, mode, steps, seed, full=False, keep_trace=False):
    rng = random.Random(seed)
    a, b = Absolute(config), Remaining(config)
    initial = a.phi2()
    lengths = sum(map(len, config["ages"][:2]))
    h150, h176 = 2*(lengths+150), 2*(lengths+176)
    epoch_initial = initial
    normal_epoch = None
    normal_initial = None
    resets = normal_resets = 0
    pending = [None]*config["n"]
    max_wait = 0
    trace = []
    digest = hashlib.sha256()
    machine_order = [0, 1, 2, 3]
    min_phi = initial
    for t in range(steps):
        offline = t > 0 and rng.randrange(9) == 0
        if offline:
            ports = {0: [0, 1], 3: list(range(config["n"]))}
            rng.shuffle(ports[0])
            rng.shuffle(ports[3])
            rng.shuffle(machine_order)
            a.offline(ports, mode == "clear")
            b.offline(ports, mode == "clear")
            if mode == "clear":
                epoch_initial = a.phi2()
                normal_epoch = a.phi2()
                resets += 1
                normal_resets += 1
        enabled = [True]*4 if full else [True, True, (t % 127) < 90, (t % 157) < 80]
        sinks = [(t % 233) < 140 and rng.randrange(5) != 0 for _ in range(config["n"])]
        before = a.phi2()
        empty_a = a.step(t, enabled, sinks, machine_order)
        empty_b = b.step(t, enabled, sinks, machine_order)
        state = a.state(t)
        assert state == b.state(t) and a.events == b.events and empty_a == empty_b
        phi = a.phi2()
        assert phi == b.phi2()
        delta = sum(1 if r == 0 else -1 for m, r in a.events if m == 0)
        assert phi == before+delta
        assert phi >= min(epoch_initial-1, h150)
        assert phi >= min(initial-(resets+1), h150-resets)
        if initial >= 2:
            assert phi >= 1
        if normal_epoch is not None:
            assert phi >= min(normal_epoch-1, h176), (config, mode, t, phi, normal_epoch)
            assert phi >= min(normal_initial-(normal_resets+1), h176-normal_resets)
        if t == 0:
            normal_initial = normal_epoch = phi
            normal_resets = 0
        min_phi = min(min_phi, phi)
        if full:
            assert all(x is not None for x in state[2])
            assert min(state[0][2:]) >= 49
            assert state[1][2] >= 49 and state[1][3] >= 50-config["k"]
            assert state[3][2][0] is not None and state[3][3][0] is not None
            for j in range(config["n"]):
                if empty_a[4+j] and pending[j] is None:
                    pending[j] = t
                if [3, 4+j] in a.events:
                    if pending[j] is not None:
                        max_wait = max(max_wait, t-pending[j])
                    pending[j] = None
                if pending[j] is not None:
                    assert t < pending[j]+config["n"]-1
        row = dict(step=t, offline=offline, phi2=phi, events=a.events, state=state)
        digest.update(json.dumps(row, separators=(",", ":")).encode())
        if keep_trace:
            trace.append(row)
    return dict(steps=steps, resets=resets, initial_phi2=initial, minimum_phi2=min_phi,
                starts=a.starts, maximum_K_wait_steps=max_wait, sha256=digest.hexdigest(), trace=trace)


def counterexample(mode):
    # Initial step is -1; add one to all reported times if s=0 is preferred.
    c = dict(k=2, n=0, input=[0, 50, 0, 0], output=[2, 49, 0, 0],
             remaining=[None, 8, None, None], ages=[[0], [None], [None], [None]],
             lastC=[None, None], lastK=[])
    a, b = Absolute(c), Remaining(c)
    ports = {0: [1, 0], 3: []}
    a.offline(ports, False)
    b.offline(ports, False)
    rows = []
    for t in range(40):
        if t == 4:
            a.offline(ports, mode == "clear")
            b.offline(ports, mode == "clear")
        a.step(t, [True]*4, [], [0, 1, 2, 3])
        b.step(t, [True]*4, [], [0, 1, 2, 3])
        assert a.state(t) == b.state(t)
        rows.append(dict(step=t, phi2=a.phi2(), state=a.state(t), events=a.events))
    return dict(config=c, mode=mode, initial_phi2=204, minimum_phi2=min(r["phi2"] for r in rows), trace=rows)


def geometric_counterexample(mode):
    # Route lengths fit the coordinates in verify_bridges.py: 7, 31, 8, 4.
    # The observation s=0 is obtained by actually running the first enabled step.
    c = dict(k=2, n=2, input=[0, 48, 1, 2], output=[2, 0, 3, 48],
             remaining=[7, 1, 1, None],
             ages=[[None, 0, 0, 8, 8, 8, 1],
                   [8]*27+[7, None, 1, None], [1]+[8]*7,
                   [0, 1, 8, 0], [7], [1]],
             lastC=[None, None], lastK=[None, None])
    a, b = Absolute(c), Remaining(c)
    ports = {0: [1, 0], 3: [0, 1]}
    a.offline(ports, False)
    b.offline(ports, False)
    rows = []
    for t in range(24):
        if t == 16:
            a.offline(ports, mode == "clear")
            b.offline(ports, mode == "clear")
        a.step(t, [True]*4, [True]*2, [0, 1, 2, 3])
        b.step(t, [True]*4, [True]*2, [0, 1, 2, 3])
        assert a.state(t) == b.state(t) and a.events == b.events
        rows.append(dict(step=t, phi2=a.phi2(), state=a.state(t), events=a.events))
    return dict(config=c, mode=mode, observation_step=0, initial_phi2=rows[0]["phi2"],
                minimum_phi2=min(r["phi2"] for r in rows), trace=rows)


def main():
    rng = random.Random(10102)
    results = []
    for full, count, steps in ((False, 120, 900), (True, 80, 1200)):
        for i in range(count):
            config = parameters(rng, full)
            for mode in ("retain", "clear"):
                r = run_case(config, mode, steps, i+10000*int(full), full, i < 2)
                r.update(full=full, case=i, mode=mode)
                results.append(r)
    examples = {mode: counterexample(mode) for mode in ("retain", "clear")}
    assert examples["retain"]["minimum_phi2"] == 203
    assert examples["clear"]["minimum_phi2"] == 202
    for mode in ("retain", "clear"):
        examples["geometric_"+mode] = geometric_counterexample(mode)
    assert examples["geometric_clear"]["initial_phi2"] == 173
    assert examples["geometric_clear"]["minimum_phi2"] == 171
    assert examples["geometric_retain"]["minimum_phi2"] == 172
    summary = dict(cases=len(results), paired_step_states=sum(r["steps"] for r in results),
                   general_cases=sum(not r["full"] for r in results),
                   full_cases=sum(r["full"] for r in results),
                   maximum_K_wait_steps=max(r["maximum_K_wait_steps"] for r in results),
                   counterexample_min_phi2={m: r["minimum_phi2"] for m, r in examples.items()},
                   scope="Forward-chain interface models, with arbitrary downstream service; not full-factory certification.")
    (OUT/"plant_results.json").write_text(json.dumps(dict(summary=summary, runs=results, witnesses=examples),
                                                     ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

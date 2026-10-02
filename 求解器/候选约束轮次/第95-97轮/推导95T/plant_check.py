"""95T: independent absolute-time and countdown plant models.

Only writes beside this file. No project/sim2 import. A gate pause is an
explicit missing-service diagnostic, not a claim about an undocumented
implementation of offline simulation. All items remain in their slots.
"""
from pathlib import Path
import json
import random

OUT = Path(__file__).resolve().parent
KIND = {"C": 2, "A": 1, "B": 1, "K": 2}
ENDS = {"CA": ("C", "A"), "AC": ("A", "C"),
        "CB": ("C", "B"), "BK": ("B", "K"),
        "KO0": ("K", "warehouse"), "KO1": ("K", "warehouse")}


class Absolute:
    def __init__(self, lengths, remaining=None, ages=None):
        self.lengths = lengths
        self.m = {m: {"i": 50, "o": 50,
                      "finish": (remaining or {}).get(m, 0), "last": {}}
                  for m in KIND}
        self.p = {p: [-((ages or {}).get((p, j), 8)) for j in range(n)]
                  for p, n in lengths.items()}
        self.sent = {p: 0 for p in lengths}
        self.received = {p: 0 for p in lengths}
        self.batches = {m: 0 for m in KIND}
        self.warehouse = 0

    def flush(self, m, t):
        a = self.m[m]
        if a["finish"] is not None and a["finish"] <= t and a["o"] + KIND[m] <= 50:
            a["o"] += KIND[m]
            a["finish"] = None

    def step(self, t, stopped=False, gate_pause=False):
        for m in KIND:
            self.flush(m, t)
        for p, cells in self.p.items():
            _, dest = ENDS[p]
            for j in range(len(cells) - 1, -1, -1):
                if cells[j] is None or t - cells[j] < 8:
                    continue
                if j + 1 < len(cells):
                    if cells[j + 1] is None:
                        cells[j + 1], cells[j] = t, None
                elif dest == "warehouse":
                    if not stopped:
                        assert self.warehouse < 80000
                        self.warehouse += 1
                        cells[j] = None
                        self.sent[p] += 1
                elif self.m[dest]["i"] < 50:
                    self.m[dest]["i"] += 1
                    cells[j] = None
                    self.sent[p] += 1
        for m in KIND:
            a = self.m[m]
            paths = [p for p in self.p if ENDS[p][0] == m]
            paths.sort(key=lambda p: (a["last"].get(p, -10**12), p))
            if a["o"]:
                for p in paths:
                    if self.p[p][0] is None and not (p == "CA" and gate_pause):
                        self.p[p][0] = t
                        a["o"] -= 1
                        a["last"][p] = t
                        self.received[p] += 1
                        self.flush(m, t)
                        break
        for m in KIND:
            a = self.m[m]
            self.flush(m, t)
            if a["finish"] is None and a["i"]:
                a["i"] -= 1
                a["finish"] = t + 8
                self.batches[m] += 1

    def state(self, t):
        return {
            "machines": {m: [a["i"], a["o"], None if a["finish"] is None else max(0, a["finish"] - t)]
                         for m, a in self.m.items()},
            "paths": {p: [None if v is None else min(8, t-v) for v in cells]
                      for p, cells in self.p.items()},
            "sent": self.sent.copy(), "received": self.received.copy(),
            "batches": self.batches.copy(), "warehouse": self.warehouse,
            "poll_order": {m: sorted([p for p in self.p if ENDS[p][0] == m],
                                     key=lambda p: (a["last"].get(p, -10**12), p))
                           for m, a in self.m.items()},
            "phi2": self.phi2(),
        }

    def phi2(self):
        return (2 * (sum(x is not None for p in ("CA", "AC") for x in self.p[p])
                     + self.m["A"]["i"] + self.m["A"]["o"] + self.m["C"]["i"]
                     + (self.m["A"]["finish"] is not None)
                     + (self.m["C"]["finish"] is not None)) + self.m["C"]["o"])


class Countdown:
    """Independent transition implementation: numeric arrays and FIFO priorities."""
    def __init__(self, lengths, remaining=None, ages=None):
        self.names = list(KIND)
        self.labels = list(lengths)
        self.idx = {m: i for i, m in enumerate(self.names)}
        self.raw = [50] * 4
        self.product = [50] * 4
        self.rem = [(remaining or {}).get(m, 0) for m in self.names]
        self.batch = [KIND[m] for m in self.names]
        self.slots = [[(ages or {}).get((p, j), 8) for j in range(lengths[p])]
                      for p in self.labels]
        self.priority = [[q for q, p in enumerate(self.labels) if ENDS[p][0] == m]
                         for m in self.names]
        for q in self.priority:
            q.sort(key=lambda j: self.labels[j])
        self.ins = [0] * len(self.labels)
        self.outs = [0] * len(self.labels)
        self.started = [0] * 4
        self.stock = 0

    def step(self, t, stopped=False, gate_pause=False):
        if t:
            for cells in self.slots:
                for j in range(len(cells)):
                    if cells[j] is not None:
                        cells[j] = min(8, cells[j] + 1)
            for a in range(4):
                if self.rem[a] is not None:
                    self.rem[a] = max(0, self.rem[a] - 1)
        for a in range(4):
            if self.rem[a] == 0 and self.product[a] <= 50 - self.batch[a]:
                self.product[a] += self.batch[a]
                self.rem[a] = None
        # Different route order from Absolute: the routes are disjoint,
        # and no machine consumes raw material until the last phase.
        for q in range(len(self.labels) - 1, -1, -1):
            cells = self.slots[q]
            receiver = ENDS[self.labels[q]][1]
            for j in reversed(range(len(cells))):
                if cells[j] != 8:
                    continue
                if j == len(cells) - 1:
                    accepted = False
                    if receiver == "warehouse":
                        accepted = not stopped
                        if accepted:
                            assert self.stock < 80000
                            self.stock += 1
                    else:
                        a = self.idx[receiver]
                        if self.raw[a] != 50:
                            self.raw[a] += 1
                            accepted = True
                    if accepted:
                        cells[j] = None
                        self.outs[q] += 1
                elif cells[j + 1] is None:
                    cells[j] = None
                    cells[j + 1] = 0
        for a in reversed(range(4)):
            if self.product[a] > 0:
                chosen = None
                for q in self.priority[a]:
                    if self.slots[q][0] is None and not (self.labels[q] == "CA" and gate_pause):
                        chosen = q
                        break
                if chosen is not None:
                    self.slots[chosen][0] = 0
                    self.product[a] -= 1
                    self.ins[chosen] += 1
                    self.priority[a].remove(chosen)
                    self.priority[a].append(chosen)
            if self.rem[a] == 0 and self.product[a] <= 50 - self.batch[a]:
                self.product[a] += self.batch[a]
                self.rem[a] = None
        for a in range(4):
            if self.rem[a] is None and self.raw[a] > 0:
                self.raw[a] -= 1
                self.rem[a] = 8
                self.started[a] += 1

    def state(self, t):
        ca = self.labels.index("CA")
        ac = self.labels.index("AC")
        a, c = self.idx["A"], self.idx["C"]
        value = (2 * (sum(x is not None for q in [ca, ac] for x in self.slots[q])
                      + self.raw[a] + self.product[a] + self.raw[c]
                      + (self.rem[a] is not None) + (self.rem[c] is not None))
                 + self.product[c])
        return {
            "machines": {m: [self.raw[i], self.product[i], self.rem[i]] for i, m in enumerate(self.names)},
            "paths": {p: list(self.slots[q]) for q, p in enumerate(self.labels)},
            "sent": dict(zip(self.labels, self.outs)),
            "received": dict(zip(self.labels, self.ins)),
            "batches": dict(zip(self.names, self.started)),
            "warehouse": self.stock, "phi2": value,
            "poll_order": {m: [self.labels[q] for q in self.priority[i]]
                           for i, m in enumerate(self.names)},
        }


def geometry():
    paths = {
        "CA": [(x, 11) for x in range(15, 22)],
        "AC": ([(x, 11) for x in range(27, 31)] + [(30, y) for y in range(10, 6, -1)]
               + [(x, 7) for x in range(29, 6, -1)] + [(7, y) for y in range(8, 12)]
               + [(8, 11), (9, 11)]),
        "CB": ([(x, 13) for x in range(15, 18)] + [(17, y) for y in range(14, 24)]
               + [(x, 23) for x in range(18, 22)]),
        "BK": [(x, 23) for x in range(27, 33)],
        "KO0": [(x, 22) for x in range(36, 41)],
        "KO1": [(x, 23) for x in range(36, 41)],
    }
    rectangles = {"C": (10, 10, 5, 5), "A": (22, 10, 5, 5),
                  "B": (22, 22, 5, 5), "K": (33, 22, 3, 3),
                  "warehouse": (41, 20, 9, 9),
                  "power0": (18, 16, 2, 2), "power1": (31, 17, 2, 2)}
    occupied = set()
    for name, (x, y, w, h) in rectangles.items():
        squares = {(a, b) for a in range(x, x+w) for b in range(y, y+h)}
        assert not occupied & squares, name
        occupied |= squares
    for p, path in paths.items():
        assert len(path) == len(set(path))
        assert all(abs(a[0]-b[0])+abs(a[1]-b[1]) == 1 for a, b in zip(path, path[1:]))
        assert not occupied & set(path), p
        occupied |= set(path)
        src, dst = ENDS[p]
        x, y, w, h = rectangles[src]
        assert path[0][0] == x+w and y <= path[0][1] < y+h
        x, y, w, h = rectangles[dst]
        assert path[-1][0] == x-1 and y <= path[-1][1] < y+h
        if dst == "warehouse":
            assert 1 <= path[-1][1]-y <= 7
    for m in KIND:
        x, y, w, h = rectangles[m]
        assert any(x < px+7 and x+w > px-5 and y < py+7 and y+h > py-5
                   for pn, (px, py, _, _) in rectangles.items() if pn.startswith("power"))
    assert all(0 <= x < 70 and 0 <= y < 70 for x, y in occupied)
    return paths, rectangles


def run():
    paths, rectangles = geometry()
    lengths = {p: len(xs) for p, xs in paths.items()}
    a, b = Absolute(lengths), Countdown(lengths)
    initial = a.phi2()
    start, end = 4096, 8096
    first_low = first_cache = first_raw = None
    snapshots = []
    previous = None
    # The gate occupies CA's first square. During the diagnostic interval
    # it refuses new input; existing cargo still leaves normally.
    for t in range(9000):
        a.step(t, gate_pause=start <= t < end)
        b.step(t, gate_pause=start <= t < end)
        sa, sb = a.state(t), b.state(t)
        assert sa == sb, (t, sa, sb)
        if t == start-161:
            previous = sa["received"]["CA"]
        if t == start-1:
            assert sa["received"]["CA"]-previous == 20
        if t >= start and sa["phi2"] < min(initial-1, 2*(lengths["CA"]+lengths["AC"]+150)) and first_low is None:
            first_low = t
        if t >= start and any(sa["machines"][m][2] is None for m in KIND) and first_cache is None:
            first_cache = t
        if t >= start and any(sa["machines"][m][0] < 49 for m in ("B", "K")) and first_raw is None:
            first_raw = t
        if t in {start-1, start, first_low, first_cache, first_raw, end-1, 8999}:
            snapshots.append({"step": t, "state": sa})
    assert first_low is not None and first_cache is not None and first_raw is not None
    diagnostic = {
        "semantics": "Missing-service diagnostic; finite input pause without deleting/moving cargo. No undocumented gate mechanism is asserted.",
        "geometry": {"paths": paths, "rectangles": rectangles, "gate": [15, 11]},
        "lengths": lengths, "initial_phi": initial/2,
        "D_lower_bound": min((initial-1)/2, lengths["CA"]+lengths["AC"]+150),
        "gate_pause": [start, end], "gate_passes_in_previous_160_steps": 20,
        "first_lower_bound_failure": first_low, "first_cache_empty": first_cache,
        "first_B_or_K_input_below_49": first_raw,
        "snapshots": snapshots, "full_states_compared": 9000,
    }
    rng = random.Random(95097)
    checks = 0
    min_margin = None
    for trial in range(48):
        ls = {p: rng.randint(1, 10) for p in ENDS}
        rem = {m: rng.randint(0, 8) for m in KIND}
        ages = {(p, j): rng.randint(0, 8) for p, n in ls.items() for j in range(n)}
        a, b = Absolute(ls, rem, ages), Countdown(ls, rem, ages)
        startphi = a.phi2()
        for t in range(1600):
            stop = 127 <= t % 353 < 267
            a.step(t, stopped=stop)
            b.step(t, stopped=stop)
            sa, sb = a.state(t), b.state(t)
            assert sa == sb, (trial, t)
            assert all(sa["machines"][m][2] is not None for m in KIND)
            assert sa["machines"]["B"][0] >= 49 and sa["machines"]["K"][0] >= 49
            assert sa["machines"]["B"][1] >= 49 and sa["machines"]["K"][1] >= 48
            margin = sa["phi2"] - min(startphi-1, 2*(ls["CA"]+ls["AC"]+150))
            assert margin >= 0
            min_margin = margin if min_margin is None else min(min_margin, margin)
            checks += 1
    result = {"gate_diagnostic": diagnostic,
              "pure_belt_checks": {"cases": 48, "steps_each": 1600,
                                   "full_states_compared": checks, "minimum_phi_margin": min_margin/2,
                                   "scope": "finite local checks; universal claims rely on the report proofs"}}
    (OUT / "plant_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"gate": {k: v for k, v in diagnostic.items() if k not in ("geometry", "snapshots")},
                      "pure_belt": result["pure_belt_checks"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()

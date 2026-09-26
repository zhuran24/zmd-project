#!/usr/bin/env python3
"""Independent exact rational-time adversarial probes of the local relay lemma.

This is an enlarged local model, not a geometric factory certificate. A producer's
input is abstracted by the premise that it starts its next batch immediately.
Output batches, capacity 50, transport dwell, X recipes, and temporary gate
disconnects are explicit. No script from another review is imported.
"""
from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import argparse
import json
import random
import time
from audit_inputs import read_recipes

HERE = Path(__file__).resolve().parent


@dataclass
class Cell:
    item: str
    dest: tuple
    born: int | None
    origin: str | None = None
    limit: int | None = None
    end: int | None = None
    used: int = 0


class LocalModel:
    def __init__(self, recipe, seed, control="none"):
        self.rng = r = random.Random(seed)
        self.seed = seed
        self.control = control
        self.q = q = r.choice((1, 2, 3, 5, 7, 11, 13))
        self.t = 0
        self.recipe = recipe
        self.need = recipe["inputs"]
        self.xitem, self.xk = next(iter(recipe["outputs"].items()))
        self.xd = recipe["duration"] * q
        self.stock = {i: r.randrange(51) for i in self.need}
        self.xout = r.randrange(51)
        self.xdone = r.choice((None, 0, r.randrange(1, self.xd+1)))
        self.period = r.choice((20, 60, 120, 240)) * q
        self.sinks = []
        self.cells = []
        self.sources = {}
        self.routes = []
        self.heads = {"X": []}
        self.pointers = {"X": 0}
        self.export_style = {}
        self.actions = ["x_deposit", "x_start"]
        self.transfers = []  # (time, 'in' or 'out', head ID, origin)
        self.changes = []
        self.observations = []
        self.quota_heads = []
        self.source_output_excess = False
        recipes = read_recipes()
        producer = {}
        for rp in recipes:
            if rp["duration"] == 1:
                item, k = next(iter(rp["outputs"].items()))
                producer.setdefault(item, k)
        available_ports = 3 if len(self.need) == 1 and recipe["machine"] not in ("种植机", "采种机") else (5 if len(self.need) == 1 else 6)
        counts = {i: (a + recipe["duration"]-1)//recipe["duration"] for i, a in self.need.items()}
        while sum(counts.values()) < available_ports and r.randrange(3) == 0:
            counts[r.choice(list(counts))] += 1
        if control == "missing_input":
            # Use a shortage relative to the true minimum, not merely remove a spare.
            key = max(self.need, key=self.need.get)
            counts[key] = max(0, (self.need[key]+recipe["duration"]-1)//recipe["duration"] - 1)
        for item, count in counts.items():
            for n in range(count):
                name = f"S{len(self.sources)}"
                mineral = item in ("源矿", "蓝铁矿")
                k = 1 if mineral else producer[item]
                self.sources[name] = dict(item=item, k=k, mineral=mineral,
                    out=r.randrange(51), done=r.randrange(q+1))
                self.heads[name] = []
                self.pointers[name] = 0
                route = self.add_route(name, item, ("input", item), r.randrange(1, 7))
                self.routes.append(route)
                if not mineral:
                    extra = r.randrange(k)
                    if control == "too_many_outputs" and not self.source_output_excess and k <= 2:
                        extra = k
                        self.source_output_excess = True
                    for _ in range(extra):
                        sid = self.add_sink(side=True)
                        path = self.add_route(name, item, ("sink", sid), r.randrange(1, 4))
                        if r.randrange(2) == 0:
                            self.cells[path[0]].limit = r.randrange(1, 6)
                            self.quota_heads.append(path[0])
                    self.actions.append(("source_deposit", name))
        xcount = r.randrange(1, min(self.xk, available_ports)+1)
        for _ in range(xcount):
            sid = self.add_sink(side=False)
            self.add_route("X", self.xitem, ("sink", sid), r.randrange(1, 4))
        for name, hs in self.heads.items():
            r.shuffle(hs)
            self.export_style[name] = r.choice(("round_robin", "priority"))
            self.actions.append(("export", name))
        self.actions += [("move", n) for n in range(len(self.cells))]
        r.shuffle(self.actions)
        self.dedicated = [p[0] for p in self.routes]
        self.input_cells = [v for p in self.routes for v in p]
        self.checked_heads = self.dedicated + (self.heads["X"] if recipe["duration"] == 1 else [])

    def add_sink(self, side):
        q, r = self.q, self.rng
        opening = self.period if side and r.randrange(2) == 0 else r.randrange(1, self.period//q+1)*q
        self.sinks.append((opening, r.randrange(self.period)))
        return len(self.sinks)-1

    def add_route(self, origin, item, dest, length):
        ids = list(range(len(self.cells), len(self.cells)+length))
        for j, idx in enumerate(ids):
            born = -self.rng.randrange(self.q+2) if self.rng.randrange(4) else None
            cell = Cell(item=item, dest=("cell", ids[j+1]) if j+1 < length else dest,
                        born=born, origin=origin if j == 0 else None)
            self.cells.append(cell)
        self.heads[origin].append(ids[0])
        return ids

    def gate_accepts(self, c):
        return c.limit is None or c.end is None or self.t >= c.end or c.used < c.limit

    def receive(self, idx):
        c = self.cells[idx]
        assert c.born is None and self.gate_accepts(c)
        c.born = self.t
        if c.limit is not None:
            if c.end is None or self.t >= c.end:
                c.end, c.used = self.t+5*self.q, 0
            c.used += 1
        if c.origin is not None:
            self.transfers.append((self.t, "in", idx, c.origin))

    def attempt(self, action):
        t, q = self.t, self.q
        if action == "x_deposit":
            if self.xdone is not None and self.xdone <= t and self.xout+self.xk <= 50:
                self.xout += self.xk
                self.xdone = None
                return True
            return False
        if action == "x_start":
            if self.xdone is None and all(self.stock[i] >= a for i, a in self.need.items()):
                for i, a in self.need.items():
                    self.stock[i] -= a
                self.xdone = t+self.xd
                return True
            return False
        kind, value = action
        if kind == "source_deposit":
            s = self.sources[value]
            if s["done"] <= t and s["out"]+s["k"] <= 50:
                s["out"] += s["k"]
                s["done"] = t+q  # simultaneous next start, guaranteed by the premise
                return True
        elif kind == "export":
            mineral = value != "X" and self.sources[value]["mineral"]
            amount = self.xout if value == "X" else self.sources[value]["out"]
            if not mineral and amount == 0:
                return False
            hs = self.heads[value]
            start = self.pointers[value] if self.export_style[value] == "round_robin" else 0
            for delta in range(len(hs)):
                pointer = (start+delta) % len(hs)
                idx = hs[pointer]
                c = self.cells[idx]
                if c.born is None and self.gate_accepts(c):
                    self.receive(idx)
                    if value == "X":
                        self.xout -= 1
                    elif not mineral:
                        self.sources[value]["out"] -= 1
                    self.pointers[value] = (pointer+1) % len(hs)
                    return True
        elif kind == "move":
            c = self.cells[value]
            if c.born is None or t-c.born < q:
                return False
            k, v = c.dest
            if k == "cell":
                target = self.cells[v]
                if target.born is not None or not self.gate_accepts(target):
                    return False
                self.receive(v)
            elif k == "input":
                if self.stock[v] == 50:
                    return False
                self.stock[v] += 1
            else:
                opening, offset = self.sinks[v]
                if (t-offset) % self.period >= opening:
                    return False
            c.born = None
            if c.origin is not None:
                self.transfers.append((t, "out", value, c.origin))
            return True
        return False

    def close(self):
        # A fixed order is used in each run; different runs explore other orders.
        n = 0
        while True:
            moved = False
            for a in self.actions:
                if self.attempt(a):
                    moved = True
                    n += 1
            if not moved:
                break
            assert n < 10000
        if n:
            self.changes.append((self.t, n))
        assert all(0 <= x <= 50 for x in self.stock.values()) and 0 <= self.xout <= 50
        self.observations.append((self.t, self.xdone is None,
            any(self.cells[j].born is None for j in self.input_cells),
            any(self.cells[j].born is None for j in self.dedicated),
            self.recipe["duration"] == 1 and any(self.cells[j].born is None for j in self.heads["X"]),
            any(x == 50 for x in self.stock.values())))

    def state(self):
        t = self.t
        return (t % self.period, tuple(self.stock.values()), self.xout,
            None if self.xdone is None else max(0, self.xdone-t),
            tuple((s["out"], max(0, s["done"]-t)) if not s["mineral"] else (0, 0) for s in self.sources.values()),
            tuple((None if c.born is None else max(0, c.born+self.q-t),
                   (c.end-t, c.used) if c.end is not None and c.end > t else (0, 0)) for c in self.cells),
            tuple(self.pointers.values()))

    def next_time(self):
        t, q = self.t, self.q
        values = [(t//q+1)*q]
        values += [c.born+q for c in self.cells if c.born is not None and c.born+q > t]
        values += [c.end for c in self.cells if c.end is not None and c.end > t]
        values += [s["done"] for s in self.sources.values() if not s["mineral"] and s["done"] > t]
        if self.xdone is not None and self.xdone > t:
            values.append(self.xdone)
        for opening, offset in self.sinks:
            if opening == self.period:
                continue
            for boundary in (offset, offset+opening):
                values.append(boundary+((t-boundary)//self.period+1)*self.period)
        return min(values)

    def check_cycle(self, begin):
        obs = [o for o in self.observations if begin < o[0] <= self.t]
        events = [e for e in self.transfers if begin < e[0] <= self.t]
        flags = dict(X_empty=any(o[1] for o in obs), input_empty=any(o[2] for o in obs),
                     source_head_empty=any(o[3] for o in obs), X_head_empty=any(o[4] for o in obs))
        period = self.t-begin
        windows, bad_windows = 0, 0
        for idx in self.checked_heads:
            enters = [e[0] for e in events if e[1] == "in" and e[2] == idx]
            leaves = [e[0] for e in events if e[1] == "out" and e[2] == idx]
            # Extend the genuine repeated cycle to include windows across its boundary.
            all_in = [v + shift for shift in (-period, 0, period) for v in enters]
            all_out = [v + shift for shift in (-period, 0, period) for v in leaves]
            ordered = sorted(all_in)
            assert all(b-a >= self.q for a, b in zip(ordered, ordered[1:])), (self.seed, idx)
            for theta in sorted({0, self.q//3, (2*self.q)//3}):
                cin = Counter((v-theta)//self.q for v in all_in)
                ready = set((v-theta)//self.q for v in all_out)
                # Full windows lying in the middle cycle; readiness includes intermediate emptiness.
                for n in range((begin-theta+self.q-1)//self.q, (self.t-theta)//self.q):
                    windows += 1
                    if n in ready and cin[n] != 1:
                        bad_windows += 1
        return dict(seed=self.seed, recipe_line=self.recipe["line"], q=self.q,
                    begin=begin/self.q, period=period/self.q,
                    distinct_event_phases=len({t % self.q for t, _ in self.changes if begin < t <= self.t}),
                    backpressure=any(o[5] for o in obs), temporary_gate_count=len(self.quota_heads),
                    closed_states=len(obs), windows=windows, bad_windows=bad_windows,
                    all_flags=flags, source_output_excess=self.source_output_excess,
                    source_count=len(self.sources), input_line_count=len(self.routes))

    def run(self, limit=3000):
        seen = {}
        self.close()
        while self.t <= limit*self.q:
            if self.t % self.q == 0:
                state = self.state()
                if state in seen:
                    return self.check_cycle(seen[state])
                seen[state] = self.t
            self.t = self.next_time()
            self.close()
        return dict(seed=self.seed, recipe_line=self.recipe["line"], timeout=True)


def run_suite(number, seed0, control):
    recipes = read_recipes()
    records = []
    for n in range(number):
        recipe = recipes[n % len(recipes)]
        model = LocalModel(recipe, seed0+n, control)
        records.append(model.run())
        if n % 100 == 99:
            print(json.dumps(dict(progress=n+1, requested=number, control=control)), flush=True)
    finished = [x for x in records if not x.get("timeout")]
    out = dict(control=control, requested=number, cycles=len(finished), timeouts=number-len(finished),
        multiple_phase_cycles=sum(x["distinct_event_phases"] > 1 for x in finished),
        backpressure_cycles=sum(x["backpressure"] for x in finished),
        temporary_gate_cycles=sum(x["temporary_gate_count"] > 0 for x in finished),
        five_tick_cycles=sum(x["recipe_line"] in (111, 114) for x in finished),
        closed_states=sum(x["closed_states"] for x in finished),
        windows=sum(x["windows"] for x in finished), bad_windows=sum(x["bad_windows"] for x in finished),
        violations={key: sum(x["all_flags"][key] for x in finished) for key in ("X_empty", "input_empty", "source_head_empty", "X_head_empty")},
        changed_source_count_cases=sum(x["source_output_excess"] for x in finished), records=records)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=360)
    parser.add_argument("--seed", type=int, default=900000)
    parser.add_argument("--control", choices=("none", "missing_input", "too_many_outputs"), default="none")
    args = parser.parse_args()
    start = time.monotonic()
    result = run_suite(args.cases, args.seed, args.control)
    result["wall_seconds"] = time.monotonic()-start
    path = HERE / f"relay_{args.control}_{args.seed}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False), flush=True)
    if args.control == "none":
        assert not any(result["violations"].values()) and result["bad_windows"] == 0


if __name__ == "__main__":
    main()

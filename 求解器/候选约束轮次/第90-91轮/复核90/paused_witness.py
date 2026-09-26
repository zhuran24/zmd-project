#!/usr/bin/env python3
"""A reachable rule-level counterexample, independently implemented with Fractions."""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
from audit_inputs import read_recipes

HERE = Path(__file__).resolve().parent


def rectangle(x, y, w, h):
    return {(u, v) for u in range(x, x+w) for v in range(y, y+h)}


def geometry():
    bodies = {
        "core": rectangle(20, 20, 9, 9),
        "ore_outlet": rectangle(0, 10, 1, 3),
        "Y": rectangle(2, 10, 3, 3),
        "X": rectangle(6, 10, 3, 3),
        "power": rectangle(4, 15, 2, 2),
        "ore_belt": {(1, 11)},
        "block_belt": {(5, 11)},
    }
    occupied = set()
    for name, cells in bodies.items():
        assert not (occupied & cells), name
        assert all(0 <= x < 70 and 0 <= y < 70 for x, y in cells)
        occupied |= cells
    # Each port is represented by its body's boundary cell and outward direction.
    ins, outs = [], []
    for name, x in (("Y", 2), ("X", 6)):
        ins += [(name, (x, y), (-1, 0)) for y in range(10, 13)]
        outs += [(name, (x+2, y), (1, 0)) for y in range(10, 13)]
    for name, x in (("ore_belt", 1), ("block_belt", 5)):
        ins.append((name, (x, 11), (-1, 0)))
        outs.append((name, (x, 11), (1, 0)))
    outs.append(("ore_outlet", (0, 11), (1, 0)))
    for y in (20, 28):
        ins += [("core", (x, y), (0, -1 if y == 20 else 1)) for x in range(21, 28)]
    for x in (20, 28):
        outs += [("core", (x, y), (-1 if x == 20 else 1, 0)) for y in (21, 24, 27)]
    channels = []
    transports = {"ore_belt", "block_belt"}
    for a, pos, d in outs:
        neighbor = (pos[0]+d[0], pos[1]+d[1])
        for b, q, e in ins:
            if neighbor == q and e == (-d[0], -d[1]) and (a in transports or b in transports):
                channels.append([a, b])
    expected = [["Y", "block_belt"], ["ore_belt", "Y"], ["block_belt", "X"], ["ore_outlet", "ore_belt"]]
    assert sorted(channels) == sorted(expected), channels
    # The pole center is (5, 16), so its coverage is [-1,11] x [10,22].
    powered = {name: any(x < 11 and x+1 > -1 and y < 22 and y+1 > 10 for x, y in bodies[name])
               for name in ("Y", "X")}
    assert all(powered.values())
    return dict(bodies={n: sorted(c) for n, c in bodies.items()}, channels=channels,
                occupied_cells=len(occupied), transport_units=2, powered=powered,
                outlet_on_allowed_boundary=True)


class Witness:
    def __init__(self, pause_at=F(15, 2)):
        recipes = read_recipes()
        self.rec = {
            "Y": next(r for r in recipes if r["machine"] == "精炼炉" and r["inputs"] == {"蓝铁矿": 1}),
            "X": next(r for r in recipes if r["machine"] == "粉碎机" and r["inputs"] == {"蓝铁块": 1}),
        }
        self.t = F(0)
        self.pause_at = pause_at
        self.paused = False
        self.m = {n: dict(stock=0, output=0, cache=None, on=True, starts=0, completes=0) for n in self.rec}
        self.belts = {n: None for n in ("ore", "block")}
        self.exported_ore = 0
        self.log = []
        self.snapshots = {}

    def record(self, action):
        self.log.append(dict(time=str(self.t), action=action))

    def close(self):
        while True:
            changed = False
            for name in ("Y", "X"):
                m = self.m[name]
                cache = m["cache"]
                if cache and cache["finish"] is not None and cache["finish"] <= self.t:
                    cache["finish"] = None
                    cache["remaining"] = F(0)
                    cache["done"] = True
                    m["completes"] += 1
                    self.record(name + ":complete")
                    changed = True
                if cache and cache["done"] and m["output"] < 50:
                    m["output"] += 1
                    m["cache"] = None
                    self.record(name + ":batch_to_output")
                    changed = True
                if m["on"] and m["cache"] is None and m["stock"]:
                    m["stock"] -= 1
                    m["starts"] += 1
                    m["cache"] = dict(finish=self.t+1, remaining=None, done=False)
                    self.record(name + ":start")
                    changed = True
            if self.belts["ore"] is not None and self.t-self.belts["ore"] >= 1 and self.m["Y"]["stock"] < 50:
                self.belts["ore"] = None
                self.m["Y"]["stock"] += 1
                self.record("ore_belt->Y")
                changed = True
            if self.belts["block"] is not None and self.t-self.belts["block"] >= 1 and self.m["X"]["stock"] < 50:
                self.belts["block"] = None
                self.m["X"]["stock"] += 1
                self.record("block_belt->X")
                changed = True
            if self.belts["ore"] is None:
                self.belts["ore"] = self.t
                self.exported_ore += 1
                self.record("warehouse->ore_belt")
                changed = True
            if self.belts["block"] is None and self.m["Y"]["output"]:
                self.belts["block"] = self.t
                self.m["Y"]["output"] -= 1
                self.record("Y->block_belt")
                changed = True
            if not changed:
                break

    def state(self):
        machines = {}
        for n, m in self.m.items():
            c = m["cache"]
            cache = None
            if c:
                remain = c["remaining"] if c["finish"] is None else max(F(0), c["finish"]-self.t)
                cache = dict(done=c["done"], remaining=str(remain),
                             contents=self.rec[n]["outputs"] if c["done"] else self.rec[n]["inputs"])
            machines[n] = dict(on=m["on"], powered=True, stock=m["stock"], output=m["output"], cache=cache)
        return dict(machines=machines,
                    belts={n: None if born is None else dict(remaining_dwell=str(max(F(0), born+1-self.t)))
                           for n, born in self.belts.items()},
                    warehouse="six specified initial species full; other species empty; ore replenished externally",
                    connections="all four fixed; one channel at each connected side")

    def run(self):
        targets = [F(60), F(61), F(100), F(140)]
        self.close()
        while self.t < max(targets):
            events = [z for z in targets if z > self.t]
            if not self.paused:
                events.append(self.pause_at)
            events += [born+1 for born in self.belts.values() if born is not None and born+1 > self.t]
            events += [m["cache"]["finish"] for m in self.m.values()
                       if m["cache"] and m["cache"]["finish"] is not None and m["cache"]["finish"] > self.t]
            self.t = min(events)
            if self.t == self.pause_at and not self.paused:
                m = self.m["Y"]
                assert m["cache"] and m["cache"]["finish"] > self.t
                m["cache"]["remaining"] = m["cache"]["finish"]-self.t
                m["cache"]["finish"] = None
                m["on"] = False
                self.paused = True
                self.record("Y:switch_off")
            self.close()
            if self.t in targets:
                self.snapshots[str(self.t)] = self.state()
        vals = list(self.snapshots.values())
        assert all(s == vals[0] for s in vals)
        assert vals[0]["machines"]["Y"]["cache"]["remaining"] == str(8-self.pause_at)
        assert vals[0]["machines"]["X"]["cache"] is None
        assert self.m["X"]["output"] == 6
        assert not [e for e in self.log if F(e["time"]) >= 60]
        return dict(pause_at=str(self.pause_at), stable_state=vals[0], checked_times=list(self.snapshots),
                    stable_state_sha256=hashlib.sha256(json.dumps(vals[0], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                    starts={n: m["starts"] for n, m in self.m.items()},
                    completes={n: m["completes"] for n, m in self.m.items()}, exported_ore=self.exported_ore,
                    last_successful_event=self.log[-1], events=self.log)


def main():
    result = dict(geometry=geometry(), witness=Witness().run())
    # An open interval of possible switch times works: no tick-precise operation is required.
    interval_cases = [Witness(F(7)+F(n, 13)).run() for n in range(1, 13)]
    result["nonprecise_pause_check"] = dict(interval="(7,8)", representative_cases=len(interval_cases),
        all_stable_X_empty=all(c["stable_state"]["machines"]["X"]["cache"] is None for c in interval_cases))
    (HERE / "paused_witness.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"geometry": {k: v for k, v in result["geometry"].items() if k != "bodies"},
        "witness": {k: v for k, v in result["witness"].items() if k != "events"},
        "nonprecise_pause_check": result["nonprecise_pause_check"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

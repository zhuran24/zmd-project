#!/usr/bin/env python3
"""Legal small layouts and two implementations of their shipment traces."""
import itertools
import json
from pathlib import Path
from check_histories import Timestamps, Queues, prefix_span, direct_intervals


DIR = {"E": (1, 0), "W": (-1, 0), "N": (0, 1), "S": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


def unit(name, kind, x, y, w, h):
    return {"name": name, "kind": kind, "x": x, "y": y, "w": w, "h": h}


def layout(merger):
    return [unit("协议核心", "core", 35, 35, 9, 9),
            unit("供电桩", "power", 10, 7, 2, 2),
            unit("供料箱", "box", 6, 10, 3, 3),
            unit("粉碎机", "machine", 10, 10, 3, 3),
            unit("收货箱A", "box", 14, 9, 3, 3),
            unit("收货箱B", "box", 14, 12, 3, 3),
            unit("原料带", "belt", 9, 11, 1, 1),
            unit("首格A", "merger" if merger else "belt", 13, 10, 1, 1),
            unit("首格B", "belt", 13, 12, 1, 1)]


def ports(u):
    x, y, w, h, kind = (u[key] for key in ("x", "y", "w", "h", "kind"))
    if kind in ("machine", "box"):
        return ([(x, y + d, "W") for d in range(h)],
                [(x + w - 1, y + d, "E") for d in range(h)])
    if kind == "belt":
        return [(x, y, "W")], [(x, y, "E")]
    if kind == "merger":
        return [(x, y, d) for d in ("W", "N", "S")], [(x, y, "E")]
    if kind == "core":
        # Receiving west/east; taking north/south. There are no nearby units.
        return ([(x, y + d, "W") for d in range(1, 8)] +
                [(x + 8, y + d, "E") for d in range(1, 8)],
                [(x + d, y, "S") for d in (1, 4, 7)] +
                [(x + d, y + 8, "N") for d in (1, 4, 7)])
    return [], []


def geometry_a(units):
    occupied = {}
    for u in units:
        for x in range(u["x"], u["x"] + u["w"]):
            for y in range(u["y"], u["y"] + u["h"]):
                assert 0 <= x < 70 and 0 <= y < 70
                assert (x, y) not in occupied
                occupied[x, y] = u["name"]
    ins = {}
    for u in units:
        for p in ports(u)[0]:
            ins[p] = u
    edges = []
    for u in units:
        for x, y, direction in ports(u)[1]:
            dx, dy = DIR[direction]
            other = ins.get((x + dx, y + dy, OPP[direction]))
            if other and ({u["kind"], other["kind"]} & {"belt", "merger"}):
                edges.append((u["name"], other["name"]))
    return sorted(edges), len(occupied)


def geometry_b(units):
    # Rectangle intersections and pairwise oppositely directed port checks.
    total = sum(u["w"] * u["h"] for u in units)
    for a, b in itertools.combinations(units, 2):
        disjoint = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or
                    a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
        assert disjoint, (a["name"], b["name"])
    edges = []
    for a, b in itertools.permutations(units, 2):
        if a["kind"] not in ("belt", "merger") and b["kind"] not in ("belt", "merger"):
            continue
        for x1, y1, d1 in ports(a)[1]:
            for x2, y2, d2 in ports(b)[0]:
                if d1 != OPP[d2]:
                    continue
                if ((d1 == "E" and x2 == x1 + 1 and y2 == y1) or
                    (d1 == "W" and x2 == x1 - 1 and y2 == y1) or
                    (d1 == "N" and y2 == y1 + 1 and x2 == x1) or
                    (d1 == "S" and y2 == y1 - 1 and x2 == x1)):
                    edges.append((a["name"], b["name"]))
    return sorted(edges), total


def manufacture_a(merger, steps):
    # Supply box ships its sole buckwheat at t=0; one belt delivers at t=8.
    raw, finish = 0, 3 if merger else None
    batches = {}
    starts = []
    for t in range(steps):
        if finish == t:
            batches[t] = 2
            finish = None
        if t == 8:
            raw += 1
        if raw and finish is None:
            raw -= 1
            finish = t + 8
            starts.append(t)
    return batches, starts


def manufacture_b(merger, steps):
    # Independent resident-age countdown; starts occur after all judgments.
    remaining = 3 if merger else None
    belt_age, raw_count, shipped = None, 0, False
    batches, starts = {}, []
    for t in range(steps):
        if remaining == 0:
            batches[t] = 2
            remaining = None
        if belt_age == 8:
            raw_count += 1
            belt_age = None
        if not shipped:
            belt_age = 0
            shipped = True
        if remaining is None and raw_count:
            raw_count -= 1
            remaining = 8
            starts.append(t)
        if remaining is not None:
            remaining -= 1
        if belt_age is not None:
            belt_age += 1
    return batches, starts


def run(name, merger=False, clear=False, offline=False):
    steps, k = 40, 2
    batches_a, starts_a = manufacture_a(merger, steps)
    batches_b, starts_b = manufacture_b(merger, steps)
    assert (batches_a, starts_a) == (batches_b, starts_b)
    q0 = 1 if merger else 2
    a, b = Timestamps(k, q0, [0, 1], 2), Queues(k, q0, [0, 1], 2)
    trace, successes, sink_counts = [], [], [0, 0]
    connection = [0, 1]
    for t in range(steps):
        is_offline = offline and t == 12
        if is_offline:
            connection = [1, 0]
        departing = [j for j, release in enumerate(a.releases) if release == t]
        for j in departing:
            sink_counts[j] += 1
        cmd = {"offline": is_offline, "clear": clear, "connection": connection,
               "groups": [[0], [1]] if merger else [[0, 1]],
               "add": batches_a.get(t, 0)}
        before = a.stock + cmd["add"]
        ra, rb = a.step(t, cmd), b.step(t, cmd)
        assert ra == rb and a.canonical(t) == b.canonical(t)
        if ra is not None:
            successes.append({"step": t, "route": "AB"[ra]})
        trace.append({"step": t, "offline": is_offline, "clear": is_offline and clear,
                      "new_batch": cmd["add"], "stock_before_judgment": before,
                      "head_departures": ["AB"[j] for j in departing],
                      "success": None if ra is None else "AB"[ra],
                      "stock_after_judgment": a.stock, "sink_counts": sink_counts[:]})
    word = ["AB".index(s["route"]) for s in successes]
    assert prefix_span(word, k) == direct_intervals(word, k)
    interval = [8, 17] if merger else [1, 17]
    counts = [sum(s["route"] == r and interval[0] <= s["step"] < interval[1]
                  for s in successes) for r in "AB"]
    # Second interval encoding counts events by indexing the complete step trace.
    counts_b = [sum(row["success"] == r for row in trace[interval[0]:interval[1]])
                for r in "AB"]
    assert counts == counts_b
    units = layout(merger)
    geo_a, geo_b = geometry_a(units), geometry_b(units)
    assert geo_a == geo_b
    expected = sorted([("供料箱", "原料带"), ("原料带", "粉碎机"),
                       ("粉碎机", "首格A"), ("粉碎机", "首格B"),
                       ("首格A", "收货箱A"), ("首格B", "收货箱B")])
    assert geo_a[0] == expected
    original_build = ["协议核心", "供电桩", "供料箱", "粉碎机", "收货箱A", "收货箱B",
                      "首格A", "原料带", "首格B"]
    reordered = ["协议核心", "供电桩", "供料箱", "粉碎机", "收货箱A", "收货箱B",
                 "原料带", "首格B", "首格A"]
    def connection_ranks(build):
        return [max(build.index("粉碎机"), build.index("首格" + route)) for route in "AB"]
    initial_ranks, new_ranks = connection_ranks(original_build), connection_ranks(reordered)
    assert initial_ranks[0] < initial_ranks[1] and new_ranks[1] < new_ranks[0]
    assert max(sink_counts) < 50
    return {"name": name, "word": "".join(s["route"] for s in successes),
            "successes": successes, "interval_half_open": interval,
            "interval_route_counts_A_B": counts,
            "maximum_interval_difference": prefix_span(word, k),
            "production_batches": batches_a, "manufacture_starts": starts_a,
            "geometry": units, "connections": geo_a[0], "occupied_cells": geo_a[1],
            "original_build_order": original_build,
            "offline_build_order": reordered if offline else None,
            "initial_source_connection_ranks": initial_ranks,
            "offline_source_connection_ranks": new_ranks if offline else None,
            "source_head_layers": [1, 1],
            "all_boxes_transfer_switch": "off",
            "final_sink_counts": sink_counts, "encoding_mismatches": 0,
            "trace": trace}


def main():
    cases = [run("clear_records", clear=True, offline=True),
             run("retain_records", clear=False, offline=True),
             run("merger_without_other_inputs", merger=True)]
    assert [x["word"] for x in cases] == ["ABBA", "ABAB", "ABAAB"]
    assert [x["maximum_interval_difference"] for x in cases] == [2, 1, 2]
    Path(__file__).with_name("witnesses.json").write_text(
        json.dumps({"cases": cases}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{k: c[k] for k in ("name", "word", "successes",
                     "interval_route_counts_A_B", "maximum_interval_difference",
                     "occupied_cells", "encoding_mismatches")} for c in cases],
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

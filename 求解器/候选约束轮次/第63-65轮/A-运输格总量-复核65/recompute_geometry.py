#!/usr/bin/env python3
"""Review 65: independently build source-indexed rectangle packing models.

Does not import or execute any derivation-seat code. All writes are beside this file.
The decision problem retains only source positions, 3x3 body packing and distances.
"""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import ortools
from ortools.sat.python import cp_model

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
INPUTS = ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt"]


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def boundary(gleft, gbottom):
    # Fill each segment before/after the one missing cell using 3-cell outlets.
    def centers(g):
        starts = list(range(0, g, 3)) + list(range(g + 1, 68, 3))
        assert len(starts) == 23
        occupied = {p + d for p in starts for d in range(3)}
        assert occupied == set(range(70)) - {g}
        return [p + 1 for p in starts]
    assert gleft % 3 == gbottom % 3 == 0 and min(gleft, gbottom) == 0
    src = [(1, y) for y in centers(gleft)] + [(x, 1) for x in centers(gbottom)]
    assert len(src) == len(set(src)) == 46
    return src


def cells(x, y):
    return {(x + a, y + b) for a in range(3) for b in range(3)}


def dist(s, x, y):
    # Distance from a lattice cell to the inclusive 3x3 body.
    return max(x - s[0], 0, s[0] - x - 2) + max(y - s[1], 0, s[1] - y - 2)


def domain(src, budget, forbidden=()):
    ban = set(src) | set(forbidden)
    bodies = [(x, y) for x in range(1, 68) for y in range(1, 68)
              if not cells(x, y) & ban]
    domains = []
    for s in src:
        options = [(x, y, dist(s, x, y) - 1) for x, y in bodies
                   if dist(s, x, y) - 1 <= budget]
        assert options and min(c for x, y, c in options) >= 0
        domains.append(options)
    return bodies, domains


def check_assignments(src, assignments):
    assert len(assignments) == len(src) == 46
    used = set()
    details = []
    total = 0
    # Here distance is recomputed by 9-cell brute force, not dist().
    for s, xy in zip(src, assignments):
        x, y = xy
        assert 1 <= x <= 67 and 1 <= y <= 67
        body = cells(x, y)
        assert not body & set(src) and not body & used
        used |= body
        d = min(abs(s[0]-a) + abs(s[1]-b) for a, b in body)
        assert d >= 1
        total += d - 1
        details.append({"source": s, "body": xy, "distance": d, "extra": d-1})
    assert len(used) == 414
    return {"cost": total, "occupied_cells": len(used), "assignments": details}


def solve(gleft, gbottom, budget, seconds, forbidden=()):
    src = boundary(gleft, gbottom)
    bodies, domains = domain(src, budget, forbidden)
    model = cp_model.CpModel()
    xx, yy, cc, ix, iy = [], [], [], [], []
    for i, options in enumerate(domains):
        x = model.new_int_var_from_domain(cp_model.Domain.from_values(sorted({a for a,b,c in options})), f"x{i}")
        y = model.new_int_var_from_domain(cp_model.Domain.from_values(sorted({b for a,b,c in options})), f"y{i}")
        c = model.new_int_var(0, budget, f"c{i}")
        model.add_allowed_assignments([x, y, c], options)
        xx.append(x); yy.append(y); cc.append(c)
        ix.append(model.new_fixed_size_interval_var(x, 3, f"ix{i}"))
        iy.append(model.new_fixed_size_interval_var(y, 3, f"iy{i}"))
    model.add_no_overlap_2d(ix, iy)
    model.add(sum(cc) <= budget)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 2
    solver.parameters.random_seed = 65
    start = time.monotonic()
    status = solver.solve(model)
    record = {"gap_left": gleft, "gap_bottom": gbottom, "budget": budget,
              "bodies_before_cost_cutoff": len(bodies),
              "options": sum(map(len, domains)), "status": solver.status_name(status),
              "seconds": time.monotonic() - start, "response_stats": solver.response_stats()}
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        assignments = [(solver.value(x), solver.value(y)) for x, y in zip(xx, yy)]
        record["witness"] = check_assignments(src, assignments)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--mode", choices=["all", "probe", "witness"], default="all")
    args = parser.parse_args()
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS}
    records = []
    gaps = [(a,b) for a in range(0,70,3) for b in range(0,70,3) if min(a,b)==0]
    assert len(gaps) == 47
    if args.mode == "probe":
        gaps = [(0,0), (3,0), (0,3), (69,0)]
    if args.mode != "witness":
        for a, b in gaps:
            r = solve(a,b,7,args.seconds)
            records.append(r)
            print(json.dumps({k:v for k,v in r.items() if k not in ("response_stats","witness")}), flush=True)
            save(f"geometry_{args.mode}.json", {"inputs":hashes, "python":platform.python_version(),
                 "ortools":ortools.__version__, "cases":records})
    if args.mode in ("all","witness"):
        # One witness avoids the union of the four vertical holes.
        holes = [(49,y,21,53) for y in (6,7,9,17)]
        forbidden = {(x,y) for a,b,w,h in holes for x in range(a,a+w) for y in range(b,b+h)}
        r = solve(3,0,8,args.seconds,forbidden)
        save("independent_witness.json", r)
        print(json.dumps({k:v for k,v in r.items() if k not in ("response_stats","witness")}), flush=True)
        assert r["status"] in ("FEASIBLE","OPTIMAL") and r["witness"]["cost"] == 8
    assert hashes == {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS}
    if args.mode in ("all","probe"):
        assert all(r["status"] == "INFEASIBLE" for r in records)


if __name__ == "__main__":
    main()

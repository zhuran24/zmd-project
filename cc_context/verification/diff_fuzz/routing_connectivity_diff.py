"""Differential fuzz harness — routing global-connectivity (tier ② slice 1).

Hunts the A-1 class of soundness bug: the certified routing path returns
FEASIBLE + extract_routes(), but the extracted routes do NOT actually form a
valid global flow (some source dead-ends, some sink is unfed, or two routes
overlap on one ground cell).

The verifier here is DELIBERATELY INDEPENDENT of RoutingSubproblem's own
connectivity guard: it re-derives port-front geometry straight from port_specs
and walks the route dicts with a plain BFS. No shared code path => a bug in the
solver's guard cannot mask itself in the checker (no isomorphic blind spot).

Usage (run from repo root):
    python cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test
    python cc_context/verification/diff_fuzz/routing_connectivity_diff.py --batch 200 --seed 0
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem  # noqa: E402

# Independent geometry (matches project convention; verified against route fixtures).
DIR_DELTA = {"E": (1, 0), "W": (-1, 0), "N": (0, 1), "S": (0, -1)}
DIR_OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}
GROUND = 0

RouteNode = Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...], str]


def _node_of(route: Dict[str, Any]) -> RouteNode:
    return (
        int(route["x"]),
        int(route["y"]),
        int(route["layer"]),
        tuple(route["flow_in"]),
        tuple(route["flow_out"]),
        str(route["commodity"]),
    )


def _port_fronts(port_specs: List[Dict[str, Any]]):
    """Re-derive source/sink fronts independently of the solver."""
    source_fronts: Dict[str, Set[Tuple[int, int, str]]] = defaultdict(set)
    sink_fronts: Dict[str, Set[Tuple[int, int, str]]] = defaultdict(set)
    for ps in port_specs:
        px, py = int(ps["x"]), int(ps["y"])
        d = str(ps["dir"])
        c = str(ps["commodity"])
        dx, dy = DIR_DELTA[d]
        fx, fy = px + dx, py + dy
        if str(ps["type"]) == "out":
            source_fronts[c].add((fx, fy, DIR_OPP[d]))  # recv dir
        else:
            # send dir: the sink front cell sends back toward the facility
            # connector, i.e. against the outward normal (R2-Q2-01 polarity —
            # the old `d` key here was the same-source error as the solver's).
            sink_fronts[c].add((fx, fy, DIR_OPP[d]))
    return source_fronts, sink_fronts


def verify_routes_connectivity(
    routes: List[Dict[str, Any]],
    port_specs: List[Dict[str, Any]],
    commodities: List[str],
) -> Tuple[bool, List[str]]:
    """Independent brute-force check that `routes` is a valid global flow."""
    reasons: List[str] = []
    source_fronts, sink_fronts = _port_fronts(port_specs)

    nodes = [_node_of(r) for r in routes]
    node_set = set(nodes)

    # Capacity: the model adds AddAtMostOne per (cell, layer) ACROSS commodities
    # (routing_subproblem._add_capacity_constraints). A selected routing must put
    # at most one route-state on each (x, y, layer).
    cell_layer_count: Dict[Tuple[int, int, int], int] = defaultdict(int)
    for (x, y, layer, _fi, _fo, _c) in nodes:
        cell_layer_count[(x, y, layer)] += 1
    for (x, y, layer), cnt in cell_layer_count.items():
        if cnt > 1:
            reasons.append(f"capacity: ({x},{y},L{layer}) carries {cnt} route-states")

    # capacity: at most one ground route-state per (x,y) per commodity, and no
    # two distinct commodities share a ground cell (cell-layer capacity = 1).
    ground_cell_users: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
    ground_cell_count: Dict[Tuple[int, int, str], int] = defaultdict(int)
    for (x, y, layer, _fi, _fo, c) in nodes:
        if layer == GROUND:
            ground_cell_users[(x, y)].add(c)
            ground_cell_count[(x, y, c)] += 1
    for cell, users in ground_cell_users.items():
        if len(users) > 1:
            reasons.append(f"ground cell {cell} shared by commodities {sorted(users)}")
    for (x, y, c), n in ground_cell_count.items():
        if n > 1:
            reasons.append(f"ground cell ({x},{y}) has {n} states for {c}")

    # adjacency: u(flow_out=d) -> v at (x+d) with flow_in containing OPP[d], same
    # commodity, unless (x,y,d) is itself a sink front (terminal).
    by_input: Dict[Tuple[int, int, str, str], List[RouteNode]] = defaultdict(list)
    for node in node_set:
        x, y, _layer, fin, _fout, c = node
        for d in fin:
            by_input[(x, y, d, c)].append(node)
    adjacency: Dict[RouteNode, Set[RouteNode]] = defaultdict(set)
    for node in node_set:
        x, y, _layer, _fin, fout, c = node
        for d in fout:
            if (x, y, d) in sink_fronts.get(c, set()):
                continue
            dx, dy = DIR_DELTA[d]
            for dst in by_input.get((x + dx, y + dy, DIR_OPP[d], c), ()):
                adjacency[node].add(dst)

    def bfs(starts: Set[RouteNode]) -> Set[RouteNode]:
        seen: Set[RouteNode] = set()
        stack = list(starts)
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adjacency.get(cur, set()))
        return seen

    for c in sorted(set(commodities) | set(source_fronts) | set(sink_fronts)):
        s_fronts = source_fronts.get(c, set())
        k_fronts = sink_fronts.get(c, set())
        if not s_fronts and not k_fronts:
            continue
        # collect nodes sitting on each front
        src_nodes_by_front: Dict[Tuple[int, int, str], Set[RouteNode]] = defaultdict(set)
        sink_nodes_by_front: Dict[Tuple[int, int, str], Set[RouteNode]] = defaultdict(set)
        for node in node_set:
            x, y, layer, fin, fout, nc = node
            if nc != c or layer != GROUND:
                continue
            for d in fin:
                if (x, y, d) in s_fronts:
                    src_nodes_by_front[(x, y, d)].add(node)
            for d in fout:
                if (x, y, d) in k_fronts:
                    sink_nodes_by_front[(x, y, d)].add(node)

        all_sinks: Set[RouteNode] = set()
        for v in sink_nodes_by_front.values():
            all_sinks |= v

        # Port adherence: the model forces sum(states at front in that dir) == 1
        # per port (_add_port_adherence). Exactly one selected ground state must
        # sit on each front in the port direction.
        for front in s_fronts:
            cnt = len(src_nodes_by_front.get(front, set()))
            if cnt != 1:
                reasons.append(f"[{c}] source front {front} has {cnt} selected states (need exactly 1)")
        for front in k_fronts:
            cnt = len(sink_nodes_by_front.get(front, set()))
            if cnt != 1:
                reasons.append(f"[{c}] sink front {front} has {cnt} selected states (need exactly 1)")

        # every source front must reach a sink (drainage) ...
        for front, snodes in src_nodes_by_front.items():
            if not (bfs(snodes) & all_sinks):
                reasons.append(f"[{c}] source front {front} reaches no sink (dead-end)")
        # ... and every sink front must be reachable from some source (fed)
        all_src: Set[RouteNode] = set()
        for v in src_nodes_by_front.values():
            all_src |= v
        reach = bfs(all_src)
        for front, knodes in sink_nodes_by_front.items():
            if not (knodes & reach):
                reasons.append(f"[{c}] sink front {front} unreachable from any source")

    return (not reasons), reasons


# --------------------------------------------------------------------------- #
# Instance generator
# --------------------------------------------------------------------------- #
def _domain(active_by_commodity: Dict[str, Set[Tuple[int, int]]]) -> Dict[str, Any]:
    return {
        "status": "feasible",
        "commodity_component_cells": {
            c: [list(cell) for cell in sorted(cells)] for c, cells in active_by_commodity.items()
        },
        "commodity_active_cells": {
            c: [list(cell) for cell in sorted(cells)] for c, cells in active_by_commodity.items()
        },
        "domain_stats": {},
    }


def gen_instance(rng: random.Random) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    """Random tiny routing instance: small grid, 1-2 commodities, 1 src+1 sink each."""
    w = rng.randint(5, 9)
    h = rng.randint(4, 7)
    ncommod = rng.randint(1, 2)
    names = ["ore", "water"][:ncommod]
    port_specs: List[Dict[str, Any]] = []
    active: Dict[str, Set[Tuple[int, int]]] = {}
    for c in names:
        # full interior grid as active domain for this commodity
        cells = {(x, y) for x in range(w) for y in range(h)}
        active[c] = cells
        # source on the left edge emitting E, sink on the right edge receiving W
        sy = rng.randint(0, h - 1)
        ky = rng.randint(0, h - 1)
        port_specs.append(
            {"instance_id": f"{c}_src", "x": -1, "y": sy, "dir": "E", "type": "out", "commodity": c}
        )
        port_specs.append(
            {"instance_id": f"{c}_sink", "x": w, "y": ky, "dir": "W", "type": "in", "commodity": c}
        )
    return port_specs, names, _domain(active)


# --------------------------------------------------------------------------- #
# Self-test of the independent verifier (no solver involved)
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    port_specs = [
        {"instance_id": "ore_src1", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "ore_src2", "x": 0, "y": 3, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "ore_sink", "x": 6, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
    ]
    # A valid S1->sink path (no S2) — straight corridor under the corrected
    # sink polarity (R2-Q2-01): sink port (6,0,W) has front (5,0) whose state
    # sends flow_out=E back toward the connector.
    connected = [
        {"x": 1, "y": 0, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 2, "y": 0, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 3, "y": 0, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 4, "y": 0, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 5, "y": 0, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
    ]
    single_src = [p for p in port_specs if p["instance_id"] != "ore_src2"]
    ok, reasons = verify_routes_connectivity(connected, single_src, ["ore"])
    print(f"[self-test] connected single-source: ok={ok} reasons={reasons}")
    if not ok:
        print("SELF-TEST FAIL: a valid path was flagged.")
        return 1

    # The A-1 incumbent: S1->sink connected + S2 isolated loop -> must be flagged.
    a1 = connected + [
        {"x": 1, "y": 3, "layer": 0, "commodity": "ore", "component_type": "splitter", "flow_in": ["E", "W"], "flow_out": ["N"]},
        {"x": 1, "y": 4, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["S"], "flow_out": ["E"]},
        {"x": 2, "y": 4, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["S"]},
        {"x": 2, "y": 3, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["N"], "flow_out": ["W"]},
    ]
    ok2, reasons2 = verify_routes_connectivity(a1, port_specs, ["ore"])
    print(f"[self-test] A-1 dead-end source: ok={ok2} reasons={reasons2}")
    if ok2:
        print("SELF-TEST FAIL: the A-1 dead-end was NOT caught.")
        return 1

    # capacity violation: a second ore state on (2,0,L0) must be flagged
    cap = connected + [
        {"x": 2, "y": 0, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["S"], "flow_out": ["N"]},
    ]
    ok3, reasons3 = verify_routes_connectivity(cap, single_src, ["ore"])
    flagged_cap = any("capacity" in r for r in reasons3)
    print(f"[self-test] capacity dup-cell: ok={ok3} capacity_flagged={flagged_cap}")
    if ok3 or not flagged_cap:
        print("SELF-TEST FAIL: capacity overload not caught.")
        return 1

    print("[self-test] PASS — accepts valid flow; catches A-1 dead-end + capacity overload.")
    return 0


def _batch(n: int, seed: int) -> int:
    rng = random.Random(seed)
    feasible = mismatches = infeasible = errors = 0
    mismatch_cases: List[str] = []
    for i in range(n):
        port_specs, names, domain = gen_instance(rng)
        try:
            routing = RoutingSubproblem(RoutingGrid(set(), port_specs), names, domain_analysis=domain)
            routing.build()
            status = routing.solve(time_limit=5.0)
            if status in ("FEASIBLE",):
                feasible += 1
                routes = routing.extract_routes()
                ok, reasons = verify_routes_connectivity(routes, port_specs, names)
                if not ok:
                    mismatches += 1
                    mismatch_cases.append(f"seed-iter {i}: status={status} reasons={reasons[:3]}")
            else:
                infeasible += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            mismatch_cases.append(f"seed-iter {i}: EXC {type(exc).__name__}: {exc}")
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{n}  feasible={feasible} mismatch={mismatches} infeasible={infeasible} err={errors}")
    print("=" * 60)
    print(f"batch={n} seed={seed}: feasible={feasible} infeasible={infeasible} "
          f"mismatches={mismatches} errors={errors}")
    for case in mismatch_cases[:20]:
        print("  MISMATCH:", case)
    return 1 if (mismatches or errors) else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rc = 0
    if args.self_test:
        rc |= _self_test()
    if args.batch:
        rc |= _batch(args.batch, args.seed)
    if not args.self_test and not args.batch:
        rc |= _self_test()
        rc |= _batch(100, 0)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

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
from itertools import combinations
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


def _port_connector_cells(port_specs: List[Dict[str, Any]]) -> Set[Tuple[int, int]]:
    """Physical port connector cells are terminal nodes, not route-state cells."""

    cells: Set[Tuple[int, int]] = set()
    for ps in port_specs:
        x, y = int(ps["x"]), int(ps["y"])
        if 0 <= x < 70 and 0 <= y < 70:
            cells.add((x, y))
    return cells


def verify_routes_connectivity(
    routes: List[Dict[str, Any]],
    port_specs: List[Dict[str, Any]],
    commodities: List[str],
) -> Tuple[bool, List[str]]:
    """Independent brute-force check that `routes` is a valid global flow."""
    reasons: List[str] = []
    source_fronts, sink_fronts = _port_fronts(port_specs)
    port_connector_cells = _port_connector_cells(port_specs)

    nodes = [_node_of(r) for r in routes]
    node_set = set(nodes)

    for (x, y, layer, _fi, _fo, c) in nodes:
        if (x, y) in port_connector_cells:
            reasons.append(f"[{c}] route-state occupies physical port connector cell ({x},{y},L{layer})")

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
# Pattern-closure verifier (route-state legality), independent of the solver
# --------------------------------------------------------------------------- #
def _legal_pattern_sets() -> Tuple[Set[Tuple[frozenset, frozenset]], Set[Tuple[frozenset, frozenset]]]:
    """Independently re-derive the legal route-state pattern closed set.

    Derived straight from the rules, NOT from RoutingSubproblem._iter_state_patterns:
      * specs/03 §3.6.5 belt: 1 in, 1 out, in != out  -> 4*3 = 12
      * specs/03 §3.6.7 splitter: 1 in, 2-3 out, out ⊆ dirs\\{in}  -> 4*(C(3,2)+C(3,3)) = 16
      * specs/03 §3.6.8 merger: 2-3 in, 1 out, in ⊆ dirs\\{out}    -> 16
      * specs/09 §9.3.3 bridge (L1): straight only, in={d}, out={Opp(d)} -> 4
    L0 (ground) total = 44, L1 (elevated) total = 4 (sum 48). Returned as sets of
    (frozenset(flow_in), frozenset(flow_out)).
    """
    dirs = ("N", "S", "E", "W")
    dset = set(dirs)
    l0: Set[Tuple[frozenset, frozenset]] = set()
    for di in dirs:                                  # belt
        for do in dirs:
            if di != do:
                l0.add((frozenset({di}), frozenset({do})))
    for di in dirs:                                  # splitter (1 in, 2-3 out)
        others = sorted(dset - {di})
        for k in (2, 3):
            for combo in combinations(others, k):
                l0.add((frozenset({di}), frozenset(combo)))
    for do in dirs:                                  # merger (2-3 in, 1 out)
        others = sorted(dset - {do})
        for k in (2, 3):
            for combo in combinations(others, k):
                l0.add((frozenset(combo), frozenset({do})))
    l1: Set[Tuple[frozenset, frozenset]] = {
        (frozenset({d}), frozenset({DIR_OPP[d]})) for d in dirs
    }
    return l0, l1


_LEGAL_L0, _LEGAL_L1 = _legal_pattern_sets()
_STRAIGHT_L0 = {(frozenset({d}), frozenset({DIR_OPP[d]})) for d in DIR_DELTA}


def _classify_state(flow_in: frozenset, flow_out: frozenset, layer: int) -> str:
    if layer == 1:
        return "bridge"
    if len(flow_in) == 1 and len(flow_out) == 1:
        return "belt"
    if len(flow_in) == 1 and len(flow_out) >= 2:
        return "splitter"
    if len(flow_in) >= 2 and len(flow_out) == 1:
        return "merger"
    return "other"


def verify_pattern_closure(routes: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Each selected route-state must be a legal belt/splitter/merger/bridge,
    and every L1 bridge may only sit over an empty cell or a straight L0 belt
    (specs/09 §9.3.3). Illegal pattern accepted by the model => false-FEASIBLE.
    """
    reasons: List[str] = []
    l0_by_cell: Dict[Tuple[int, int], Tuple[frozenset, frozenset]] = {}
    bridge_cells: List[Tuple[int, int, str]] = []
    for r in routes:
        fi = frozenset(r["flow_in"])
        fo = frozenset(r["flow_out"])
        layer = int(r["layer"])
        x, y, c = int(r["x"]), int(r["y"]), str(r["commodity"])
        if layer == 0:
            if (fi, fo) not in _LEGAL_L0:
                reasons.append(f"[PAT] illegal L0 pattern ({x},{y}) [{c}]: in={sorted(fi)} out={sorted(fo)}")
            l0_by_cell[(x, y)] = (fi, fo)
        elif layer == 1:
            if (fi, fo) not in _LEGAL_L1:
                reasons.append(f"[PAT] illegal L1 bridge ({x},{y}) [{c}]: in={sorted(fi)} out={sorted(fo)} (bridge must be straight)")
            bridge_cells.append((x, y, c))
        else:
            reasons.append(f"[PAT] unknown layer {layer} at ({x},{y}) [{c}]")
    # Commodity is intentionally ignored here: the SUT's bridge/L0 coexistence
    # constraint is cell-keyed (a bridge of any commodity over a non-straight L0
    # of any commodity is illegal). Do NOT "fix" this into per-commodity.
    for (x, y, c) in bridge_cells:
        below = l0_by_cell.get((x, y))
        if below is not None and below not in _STRAIGHT_L0:
            reasons.append(
                f"[PAT] bridge ({x},{y}) [{c}] sits over non-straight L0 {sorted(below[0])}->{sorted(below[1])} (specs/09 §9.3.3)"
            )
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
    """Random tiny routing instance: small grid, 1-2 commodities.

    Per commodity the source/sink multiplicity is randomized so the solver is
    forced to use the full pattern alphabet, not just belts:
      * belt:     1 source (left, E) + 1 sink (right, W)
      * splitter: 1 source + 2 sinks (one source must feed two sinks)
      * merger:   2 sources + 1 sink (two sources must merge into one sink)
    L1 bridges arise on their own when two commodities' paths must cross.
    """
    w = rng.randint(5, 9)
    h = rng.randint(4, 7)
    ncommod = rng.randint(1, 2)
    names = ["ore", "water"][:ncommod]
    port_specs: List[Dict[str, Any]] = []
    active: Dict[str, Set[Tuple[int, int]]] = {}

    def distinct_ys(count: int) -> List[int]:
        # count is at most 2 (splitter/merger multiplicity) and h >= 4, so
        # distinct front rows always exist — no duplicate-front collisions.
        return rng.sample(range(h), count)

    for c in names:
        active[c] = {(x, y) for x in range(w) for y in range(h)}
        mode = rng.choice(["belt", "belt", "splitter", "merger"])  # belt weighted
        n_src, n_sink = {"belt": (1, 1), "splitter": (1, 2), "merger": (2, 1)}[mode]
        for i, sy in enumerate(distinct_ys(n_src)):
            port_specs.append(
                {"instance_id": f"{c}_src{i}", "x": -1, "y": sy, "dir": "E", "type": "out", "commodity": c}
            )
        for i, ky in enumerate(distinct_ys(n_sink)):
            port_specs.append(
                {"instance_id": f"{c}_sink{i}", "x": w, "y": ky, "dir": "W", "type": "in", "commodity": c}
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

    connector_ports = [
        {"instance_id": "ore_src", "x": 0, "y": 1, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "ore_sink", "x": 4, "y": 1, "dir": "W", "type": "in", "commodity": "ore"},
        {"instance_id": "water_src", "x": 2, "y": 1, "dir": "N", "type": "out", "commodity": "water"},
        {"instance_id": "water_sink", "x": 2, "y": 4, "dir": "S", "type": "in", "commodity": "water"},
    ]
    connector_reuse = [
        {"x": 1, "y": 1, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 2, "y": 1, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 3, "y": 1, "layer": 0, "commodity": "ore", "component_type": "belt", "flow_in": ["W"], "flow_out": ["E"]},
        {"x": 2, "y": 2, "layer": 0, "commodity": "water", "component_type": "belt", "flow_in": ["S"], "flow_out": ["N"]},
        {"x": 2, "y": 3, "layer": 0, "commodity": "water", "component_type": "belt", "flow_in": ["S"], "flow_out": ["N"]},
    ]
    ok4, reasons4 = verify_routes_connectivity(connector_reuse, connector_ports, ["ore", "water"])
    flagged_connector = any("port connector" in r for r in reasons4)
    print(f"[self-test] connector-cell reuse: ok={ok4} connector_flagged={flagged_connector}")
    if ok4 or not flagged_connector:
        print("SELF-TEST FAIL: port connector cell reuse not caught.")
        return 1

    # --- pattern-closure self-tests (independent of the solver) ---
    if len(_LEGAL_L0) != 44 or len(_LEGAL_L1) != 4:
        print(f"SELF-TEST FAIL: legal pattern counts L0={len(_LEGAL_L0)} (want 44) L1={len(_LEGAL_L1)} (want 4).")
        return 1
    print(f"[self-test] legal pattern closed set: L0={len(_LEGAL_L0)} L1={len(_LEGAL_L1)} (48 total)")

    # legal splitter (1 in, 2 out) + merger (2 in, 1 out) must pass.
    legal_pat = [
        {"x": 1, "y": 1, "layer": 0, "commodity": "ore", "flow_in": ["W"], "flow_out": ["E", "N"]},
        {"x": 2, "y": 2, "layer": 0, "commodity": "ore", "flow_in": ["W", "S"], "flow_out": ["E"]},
        {"x": 3, "y": 3, "layer": 1, "commodity": "ore", "flow_in": ["W"], "flow_out": ["E"]},
    ]
    okp, rp = verify_pattern_closure(legal_pat)
    print(f"[self-test] legal splitter/merger/bridge: ok={okp}")
    if not okp:
        print(f"SELF-TEST FAIL: legal patterns flagged: {rp}")
        return 1

    # illegal patterns must all be flagged.
    bad_cases = [
        ("U-turn belt in==out", [{"x": 0, "y": 0, "layer": 0, "commodity": "ore", "flow_in": ["E"], "flow_out": ["E"]}]),
        ("2-in-2-out crossing", [{"x": 0, "y": 0, "layer": 0, "commodity": "ore", "flow_in": ["N", "S"], "flow_out": ["E", "W"]}]),
        ("L1 turn bridge", [{"x": 0, "y": 0, "layer": 1, "commodity": "ore", "flow_in": ["W"], "flow_out": ["N"]}]),
        ("bridge over turn belt", [
            {"x": 5, "y": 5, "layer": 0, "commodity": "water", "flow_in": ["W"], "flow_out": ["N"]},
            {"x": 5, "y": 5, "layer": 1, "commodity": "ore", "flow_in": ["W"], "flow_out": ["E"]},
        ]),
    ]
    for label, routes in bad_cases:
        okb, rb = verify_pattern_closure(routes)
        print(f"[self-test] illegal '{label}': flagged={not okb}")
        if okb:
            print(f"SELF-TEST FAIL: illegal pattern '{label}' NOT caught.")
            return 1

    print("[self-test] PASS — connectivity (A-1/capacity/connector) + pattern closure (illegal belt/splitter/bridge) all caught.")
    return 0


def _batch(n: int, seed: int) -> int:
    rng = random.Random(seed)
    feasible = mismatches = infeasible = errors = 0
    seen = defaultdict(int)  # pattern-type telemetry across feasible cases
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
                ok_c, reasons_c = verify_routes_connectivity(routes, port_specs, names)
                ok_p, reasons_p = verify_pattern_closure(routes)
                for r in routes:
                    seen[_classify_state(frozenset(r["flow_in"]), frozenset(r["flow_out"]), int(r["layer"]))] += 1
                if not (ok_c and ok_p):
                    mismatches += 1
                    mismatch_cases.append(f"seed-iter {i}: status={status} reasons={(reasons_c + reasons_p)[:4]}")
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
    print(f"pattern states seen: {dict(seen)}")
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

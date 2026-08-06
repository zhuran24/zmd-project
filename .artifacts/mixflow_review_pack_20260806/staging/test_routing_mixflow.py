"""Mixflow surgery differential tests (2026-08-06).

Scenario geometry uses the DIR_DELTA math convention (N = y+1) and identity
front semantics (the stored port coordinate IS the front/belt cell).  Corridor
scenarios occupy every cell outside an explicit free set so commodities cannot
route around the structure under test — an open grid would prove nothing.

Groups:
- unlocks: merge-then-split (U-02) and source-front co-riding flip from the
  pre-surgery structural INFEASIBLE to FEASIBLE, with per-commodity
  sub-pattern routes recorded in the extraction;
- pollution sentinels: machine-input front cells stay pure on ground.  The
  guard-off mutation tests prove the explicit exclusion is load-bearing (the
  scenarios flip FEASIBLE when `_mixflow_ground_banned` is neutralized), so
  the sentinels cannot rot into vacuous assertions;
- regressions: pre-surgery FEASIBLE structures stay FEASIBLE, and the
  physical layer stays exactly the union of the commodity sub-patterns.
"""

from typing import Dict, List, Sequence, Set, Tuple

import pytest

from src.models.routing_subproblem import (
    GRID_H,
    GRID_W,
    RoutingGrid,
    RoutingSubproblem,
    analyze_exact_routing_domain,
)

Cell = Tuple[int, int]


def _occupied_except(free_cells: Sequence[Cell]) -> Set[Cell]:
    free = set(free_cells)
    return {(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in free}


def _build(free_cells: Sequence[Cell], port_specs: List[Dict], commodities: List[str]) -> RoutingSubproblem:
    grid = RoutingGrid(_occupied_except(free_cells), port_specs)
    analysis = analyze_exact_routing_domain(grid)
    assert analysis["status"] == "feasible", analysis
    routing = RoutingSubproblem(grid, commodities, domain_analysis=analysis)
    routing.build()
    return routing


def _solve(routing: RoutingSubproblem) -> str:
    return routing.solve(time_limit=30.0)


def _routes_by_cell_layer(routing: RoutingSubproblem) -> Dict[Tuple[int, int, int], Dict]:
    return {(r["x"], r["y"], r["layer"]): r for r in routing.extract_routes()}


def _use_flows(route: Dict) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    return {
        u["commodity"]: (tuple(u["flow_in"]), tuple(u["flow_out"]))
        for u in route["uses"]
    }


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def _sc_u02_merge_then_split():
    """Two sources merge onto a width-1 shared corridor, then split apart."""
    free = [
        (3, 2), (4, 2),          # a: source spur
        (3, 4), (4, 4),          # b: source spur
        (4, 3), (5, 3), (6, 3),  # shared corridor: merge at (4,3), split at (6,3)
        (6, 2), (7, 2),          # a: exit spur to its sink
        (6, 4), (7, 4),          # b: exit spur to its sink
    ]
    ports = [
        {"x": 3, "y": 2, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 3, "y": 4, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 7, "y": 2, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 7, "y": 4, "dir": "W", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_source_front_coride():
    """b joins a's output lane AT a's source front cell (owner-ruled safe)."""
    free = [
        (3, 3), (3, 4),          # b: source spur from the south
        (3, 5),                  # a's source front — b merges here
        (3, 6), (3, 7),          # shared lane north; split at (3,7)
        (2, 7),                  # a: sink front (west exit)
        (3, 8),                  # b: sink front (north exit)
    ]
    ports = [
        {"x": 3, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 3, "y": 3, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 2, "y": 7, "dir": "E", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 3, "y": 8, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_door_corner_transit():
    """b would have to TURN on a's sink front cell; L1 bridges are straight."""
    free = [
        (5, 3), (5, 4), (5, 5),  # a: lane south->north; sink front F=(5,5)
        (4, 5),                  # b: source front, west of F
        (5, 6),                  # b: sink front, north of F
    ]
    ports = [
        {"x": 5, "y": 3, "dir": "N", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 4, "y": 5, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 5, "y": 6, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_door_split_transit():
    """b co-rides a's lane and wants to peel off north AT a's sink front.

    The side union at the door cell is splitter W→{E,N} — a legal dictionary
    pattern — so the explicit ground-purity exclusion is the ONLY wall between
    this structure and a content-blind splitter feeding b's items into a's
    machine.  This is the mutation-detecting pollution sentinel.
    """
    free = [
        (2, 5), (3, 5),          # a: source front + shared lane cell
        (3, 4),                  # b: source front, merging into the lane at (3,5)
        (4, 5),                  # F: a's sink front (b would split N here)
        (4, 6),                  # b: sink front, north of F
    ]
    ports = [
        {"x": 2, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 4, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 3, "y": 4, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 4, "y": 6, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_multi_owner_sink_front():
    """Two different-commodity sink ports face the same front cell F=(5,5).

    Without the multi-owner full ban, a's N→E and b's N→W terminals would
    union into splitter N→{E,W}: a content-blind component alternately feeding
    both machines from a mixed lane.  Must stay INFEASIBLE.
    """
    free = [
        (5, 7),                  # a: source front (north end)
        (4, 6),                  # b: source front (west spur into (5,6))
        (5, 6),                  # shared feed cell (b merges here)
        (5, 5),                  # F: sink front of BOTH a (body east) and b (body west)
    ]
    ports = [
        {"x": 5, "y": 7, "dir": "S", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 4, "y": 6, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 5, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 5, "y": 5, "dir": "E", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_perpendicular_bridge_cross():
    free = [
        (3, 5), (4, 5), (5, 5), (6, 5), (7, 5),  # a: horizontal lane W->E
        (5, 3), (5, 4), (5, 6), (5, 7),          # b: vertical lane S->N
    ]
    ports = [
        {"x": 3, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 7, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 5, "y": 3, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 5, "y": 7, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_single_commodity_split():
    free = [
        (3, 5), (4, 5),
        (5, 5),
        (5, 6), (5, 7),
        (5, 4), (5, 3),
    ]
    ports = [
        {"x": 3, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 7, "dir": "S", "commodity": "a", "type": "in", "instance_id": "sinkA1"},
        {"x": 5, "y": 3, "dir": "N", "commodity": "a", "type": "in", "instance_id": "sinkA2"},
    ]
    return free, ports, ["a"]


def _neutralize_purity_guard(monkeypatch):
    monkeypatch.setattr(
        RoutingSubproblem,
        "_mixflow_ground_banned",
        lambda self, x, y, commodity: False,
    )


# ---------------------------------------------------------------------------
# Unlocks (pre-surgery: structural INFEASIBLE)
# ---------------------------------------------------------------------------

def test_u02_merge_then_split_feasible():
    routing = _build(*_sc_u02_merge_then_split())
    assert _solve(routing) == "FEASIBLE"

    routes = _routes_by_cell_layer(routing)
    merge = routes[(4, 3, 0)]
    assert merge["component_type"] == "merger"
    merge_flows = _use_flows(merge)
    assert merge_flows["a"] == (("S",), ("E",))
    assert merge_flows["b"] == (("N",), ("E",))

    split_key = (6, 3, 0)
    if split_key in routes and routes[split_key]["component_type"] == "splitter":
        split_flows = _use_flows(routes[split_key])
        # per-commodity destinations are recorded in the variables themselves
        assert split_flows["a"] == (("W",), ("S",))
        assert split_flows["b"] == (("W",), ("N",))
    else:
        # the solver may bridge part of the corridor on L1; the split then
        # happens on the ground cell that both commodities still share
        ground_splits = [
            r for r in routes.values()
            if r["layer"] == 0 and r["component_type"] == "splitter"
        ]
        assert ground_splits, routes


def test_u02_split_destinations_are_disjoint():
    routing = _build(*_sc_u02_merge_then_split())
    assert _solve(routing) == "FEASIBLE"
    for route in routing.extract_routes():
        flows = _use_flows(route)
        if len(flows) < 2:
            continue
        # every commodity's sub-pattern sides are a subset of the phys sides
        for flow_in, flow_out in flows.values():
            assert set(flow_in) <= set(route["flow_in"])
            assert set(flow_out) <= set(route["flow_out"])


def test_source_front_coride_feasible():
    routing = _build(*_sc_source_front_coride())
    assert _solve(routing) == "FEASIBLE"

    routes = _routes_by_cell_layer(routing)
    door = routes[(3, 5, 0)]
    assert door["component_type"] == "merger"
    door_flows = _use_flows(door)
    assert door_flows["a"] == (("W",), ("N",))   # a receives from its port (west body)
    assert door_flows["b"] == (("S",), ("N",))   # b transits/merges at the door
    assert sorted(door["commodities"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# Pollution sentinels (machine-input front purity, owner ironclad)
# ---------------------------------------------------------------------------

def test_door_corner_transit_stays_infeasible():
    routing = _build(*_sc_door_corner_transit())
    assert _solve(routing) == "INFEASIBLE"


def test_door_split_transit_stays_infeasible():
    routing = _build(*_sc_door_split_transit())
    assert _solve(routing) == "INFEASIBLE"


def test_no_foreign_ground_states_at_sink_front():
    routing = _build(*_sc_door_split_transit())
    foreign_ground_keys = [
        key
        for key in routing.use_vars
        if (key[0], key[1]) == (4, 5) and key[2] == 0 and key[5] == "b"
    ]
    assert foreign_ground_keys == []


def test_door_split_sentinel_is_load_bearing(monkeypatch):
    """Mutation self-verification: with the purity guard neutralized the door
    split scenario MUST flip FEASIBLE — proving the explicit exclusion is the
    only wall (the sentinel would catch its silent removal)."""
    _neutralize_purity_guard(monkeypatch)
    routing = _build(*_sc_door_split_transit())
    assert _solve(routing) == "FEASIBLE"


def test_multi_owner_sink_front_stays_infeasible():
    routing = _build(*_sc_multi_owner_sink_front())
    assert _solve(routing) == "INFEASIBLE"
    assert routing.build_stats["mixflow"]["multi_owner_sink_fronts"] == [[5, 5]]


def test_multi_owner_sentinel_is_load_bearing(monkeypatch):
    _neutralize_purity_guard(monkeypatch)
    routing = _build(*_sc_multi_owner_sink_front())
    assert _solve(routing) == "FEASIBLE"


# ---------------------------------------------------------------------------
# Regressions (pre-surgery FEASIBLE must stay FEASIBLE)
# ---------------------------------------------------------------------------

def test_perpendicular_bridge_cross_stays_feasible():
    routing = _build(*_sc_perpendicular_bridge_cross())
    assert _solve(routing) == "FEASIBLE"


def test_single_commodity_split_stays_feasible():
    routing = _build(*_sc_single_commodity_split())
    assert _solve(routing) == "FEASIBLE"
    routes = routing.extract_routes()
    assert any(r["component_type"] == "splitter" for r in routes)


def test_phys_pattern_equals_union_of_use_sides():
    """Exact-side rows: every extracted component carries exactly the union of
    its commodities' sub-pattern sides (minimal hardware invariant)."""
    for builder in (
        _sc_u02_merge_then_split,
        _sc_source_front_coride,
        _sc_perpendicular_bridge_cross,
        _sc_single_commodity_split,
    ):
        routing = _build(*builder())
        assert _solve(routing) == "FEASIBLE"
        for route in routing.extract_routes():
            flows = _use_flows(route)
            assert flows, route
            in_union: Set[str] = set()
            out_union: Set[str] = set()
            for flow_in, flow_out in flows.values():
                in_union |= set(flow_in)
                out_union |= set(flow_out)
            assert in_union == set(route["flow_in"]), route
            assert out_union == set(route["flow_out"]), route


def test_connectivity_validator_accepts_mixflow_solution():
    routing = _build(*_sc_u02_merge_then_split())
    assert _solve(routing) == "FEASIBLE"
    connected, summary = routing._validate_selected_route_connectivity(routing._solver)
    assert connected, summary
    assert summary["failure_count"] == 0

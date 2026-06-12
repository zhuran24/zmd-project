from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from src.models.routing_subproblem import (
    RoutingGrid,
    RoutingSubproblem,
    GROUND_LAYER,
    ELEVATED_LAYER,
    DIR_DELTA,
    DIR_OPP,
)

DIRECTIONS = ("N", "S", "E", "W")
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}


def tiny_domain(active_cells_by_commodity):
    return {
        "status": "feasible",
        "commodity_component_cells": {
            commodity: [list(cell) for cell in sorted(active_cells)]
            for commodity, active_cells in active_cells_by_commodity.items()
        },
        "commodity_active_cells": {
            commodity: [list(cell) for cell in sorted(active_cells)]
            for commodity, active_cells in active_cells_by_commodity.items()
        },
        "domain_stats": {},
    }


def normalize_pattern(pattern):
    return (
        tuple(pattern["flow_in"]),
        tuple(pattern["flow_out"]),
        str(pattern["component_type"]),
    )


def expected_patterns(layer):
    expected = set()
    if layer == ELEVATED_LAYER:
        for d_in in DIRECTIONS:
            expected.add(((d_in,), (OPP[d_in],), "bridge"))
        return expected

    for d_in in DIRECTIONS:
        for d_out in DIRECTIONS:
            if d_out != d_in:
                expected.add(((d_in,), (d_out,), "belt"))

    for d_in in DIRECTIONS:
        choices = tuple(d for d in DIRECTIONS if d != d_in)
        for degree in (2, 3):
            for outs in combinations(choices, degree):
                expected.add(((d_in,), tuple(outs), "splitter"))

    for d_out in DIRECTIONS:
        choices = tuple(d for d in DIRECTIONS if d != d_out)
        for degree in (2, 3):
            for ins in combinations(choices, degree):
                expected.add((tuple(ins), (d_out,), "merger"))
    return expected


def assert_pattern_enumeration_exact():
    grid = RoutingGrid(set(), [])
    routing = RoutingSubproblem(grid, [])
    observed_by_layer = {
        GROUND_LAYER: {normalize_pattern(p) for p in routing._iter_state_patterns(GROUND_LAYER)},
        ELEVATED_LAYER: {normalize_pattern(p) for p in routing._iter_state_patterns(ELEVATED_LAYER)},
    }
    counts = {}
    for layer in (GROUND_LAYER, ELEVATED_LAYER):
        expected = expected_patterns(layer)
        observed = observed_by_layer[layer]
        missing = expected - observed
        extra = observed - expected
        assert not missing, (layer, "missing", sorted(missing))
        assert not extra, (layer, "extra", sorted(extra))
        counts[layer] = Counter(component for _fin, _fout, component in observed)
    assert counts[GROUND_LAYER] == Counter({"belt": 12, "splitter": 16, "merger": 16})
    assert counts[ELEVATED_LAYER] == Counter({"bridge": 4})
    return counts


def all_cells_except(allowed):
    return {(x, y) for x in range(70) for y in range(70) if (x, y) not in allowed}


def assert_stale_domain_clipped_and_blocked_fronts_fail_closed():
    # Connector cells are intentionally listed as free here to prove the connector
    # subtraction works independently from ordinary occupied-cell exclusion.
    allowed = {(10, 10), (11, 10), (13, 10), (14, 10)}
    port_specs = [
        {"instance_id": "src", "x": 10, "y": 10, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "sink", "x": 14, "y": 10, "dir": "W", "type": "in", "commodity": "ore"},
    ]
    grid = RoutingGrid(all_cells_except(allowed), port_specs)
    stale = tiny_domain({"ore": {(10, 10), (11, 10), (12, 10), (13, 10), (14, 10), (-1, 10), (70, 10)}})
    routing = RoutingSubproblem(grid, ["ore"], domain_analysis=stale)
    routing.build()
    active = routing._commodity_active_cells["ore"]
    assert active == {(11, 10), (13, 10)}, active
    forbidden_cells = {(10, 10), (12, 10), (14, 10), (-1, 10), (70, 10)}
    assert not any((key[0], key[1]) in forbidden_cells for key in routing.r_vars)
    assert routing.solve(time_limit=2.0) == "INFEASIBLE"

    # Source-front cropped out of active domain: _add_port_adherence must add 0 == 1.
    corridor_allowed = {(1, 0), (2, 0), (3, 0)}
    corridor_ports = [
        {"instance_id": "src", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "sink", "x": 4, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
    ]
    grid = RoutingGrid(all_cells_except(corridor_allowed), corridor_ports)
    routing = RoutingSubproblem(grid, ["ore"], domain_analysis=tiny_domain({"ore": {(2, 0), (3, 0)}}))
    routing.build()
    assert routing.build_stats["port_adherence"]["blocked_ports"] >= 1
    assert routing.solve(time_limit=2.0) == "INFEASIBLE"

    # Sink-front cropped out of active domain: same fail-closed path, no early skip.
    routing = RoutingSubproblem(grid, ["ore"], domain_analysis=tiny_domain({"ore": {(1, 0), (2, 0)}}))
    routing.build()
    assert routing.build_stats["port_adherence"]["blocked_ports"] >= 1
    assert routing.solve(time_limit=2.0) == "INFEASIBLE"


def independent_adjacency(keys, sink_fronts):
    by_input = defaultdict(set)
    for key in keys:
        x, y, _layer, flow_in, _flow_out, commodity = key
        for direction in flow_in:
            by_input[(x, y, direction, commodity)].add(key)
    adjacency = defaultdict(set)
    for key in keys:
        x, y, _layer, _flow_in, flow_out, commodity = key
        for direction in flow_out:
            if (x, y, direction) in sink_fronts.get(commodity, set()):
                continue
            dx, dy = DIR_DELTA[direction]
            adjacency[key].update(by_input.get((x + dx, y + dy, DIR_OPP[direction], commodity), set()))
    return {key: set(value) for key, value in adjacency.items()}


class FakeSolver:
    def __init__(self, selected_vars):
        self.selected_vars = set(selected_vars)

    def Value(self, var):
        return 1 if var in self.selected_vars else 0


def assert_guard_adjacency_and_acceptance():
    port_specs = [
        {"instance_id": "src", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "sink", "x": 4, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
    ]
    routing = RoutingSubproblem(RoutingGrid(set(), port_specs), ["ore"])
    source = (1, 0, GROUND_LAYER, ("W",), ("E",), "ore")
    bridge = (2, 0, ELEVATED_LAYER, ("W",), ("E",), "ore")
    sink = (3, 0, GROUND_LAYER, ("W",), ("E",), "ore")
    selected = {source, bridge, sink}
    source_fronts, sink_fronts = routing._terminal_fronts_by_commodity()
    observed = {key: set(value) for key, value in routing._route_state_adjacency(selected, sink_fronts).items()}
    expected = independent_adjacency(selected, sink_fronts)
    assert observed == expected == {source: {bridge}, bridge: {sink}}

    vars_by_key = {key: object() for key in selected}
    routing.r_vars = vars_by_key
    ok, summary = routing._validate_selected_route_connectivity(FakeSolver(vars_by_key.values()))
    assert ok, summary

    disconnected_vars = {source: object(), sink: object()}
    routing.r_vars = disconnected_vars
    ok, summary = routing._validate_selected_route_connectivity(FakeSolver(disconnected_vars.values()))
    assert not ok
    assert summary["failure_count"] == 1
    assert summary["failures"][0]["unreachable_sink_fronts"] == [[3, 0, "E"]]
    assert summary["failures"][0]["source_fronts_without_sink"] == [[1, 0, "W"]]

    # Malformed selected state data raises instead of being accepted: no fail-open return path.
    routing.r_vars = {("bad",): object()}
    try:
        routing._validate_selected_route_connectivity(FakeSolver(routing.r_vars.values()))
    except Exception as exc:  # noqa: BLE001 - probe asserts fail-closed-by-exception behavior
        assert type(exc).__name__ in {"ValueError", "IndexError", "TypeError"}
    else:
        raise AssertionError("malformed route key was not rejected/raised")


if __name__ == "__main__":
    counts = assert_pattern_enumeration_exact()
    assert_stale_domain_clipped_and_blocked_fronts_fail_closed()
    assert_guard_adjacency_and_acceptance()
    print("pattern_counts", {layer: dict(counter) for layer, counter in counts.items()})
    print("domain_clip_and_front_adherence", "ok")
    print("guard_adjacency_and_fail_closed", "ok")

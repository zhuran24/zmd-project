#!/usr/bin/env python3
"""Adversarial probe for the v4 G1 hypergraph and G1 x OB6 claims."""
from __future__ import annotations

import json

from ortools.sat.python import cp_model

from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem


CENTER = (35, 35)
ACTIVE = {CENTER, (34, 35), (36, 35), (35, 34), (35, 36)}
OCCUPIED = {(x, y) for x in range(70) for y in range(70)} - ACTIVE
ANALYSIS = {
    "status": "feasible",
    "commodity_component_cells": {"buckwheat": [list(c) for c in sorted(ACTIVE)]},
    "commodity_active_cells": {"buckwheat": [list(c) for c in sorted(ACTIVE)]},
    "domain_stats": {},
}


def local_model() -> RoutingSubproblem:
    model = RoutingSubproblem(RoutingGrid(OCCUPIED, []), ["buckwheat"], domain_analysis=ANALYSIS)
    model._bind_domain_analysis(ANALYSIS, analysis_status="feasible")
    model._create_routing_variables()
    model._add_capacity_constraints()
    model._add_bridge_constraints()
    return model


def forced_pair_status(first: tuple, second: tuple) -> str:
    model = local_model()
    assert first in model.phys_vars
    assert second in model.phys_vars
    model.model.Add(model.phys_vars[first] == 1)
    model.model.Add(model.phys_vars[second] == 1)
    solver = cp_model.CpSolver()
    status = solver.Solve(model.model)
    return solver.StatusName(status)


def main() -> None:
    splitter = (35, 35, 0, ("W",), ("N", "S"), "splitter")
    merger = (35, 35, 0, ("E", "W"), ("N",), "merger")
    horizontal = (35, 35, 0, ("W",), ("E",), "belt")
    l1_vertical = (35, 35, 1, ("N",), ("S",), "bridge")
    l1_horizontal = (35, 35, 1, ("W",), ("E",), "bridge")
    checks = {
        "splitter_plus_perpendicular_L1": forced_pair_status(splitter, l1_vertical),
        "merger_plus_perpendicular_L1": forced_pair_status(merger, l1_vertical),
        "straight_plus_perpendicular_L1": forced_pair_status(horizontal, l1_vertical),
        "straight_plus_parallel_L1": forced_pair_status(horizontal, l1_horizontal),
    }
    receipt_path = (
        ".artifacts/p2_0_refresh_20260805/area_bound_work/refute_20260806/"
        "front_state_sharing_receipt.json"
    )
    with open(receipt_path, encoding="utf-8") as handle:
        receipt = json.load(handle)
    gadget = next(
        item for item in receipt["routing_gadgets"] if item["name"] == "dense_three_sources_one_sink"
    )
    vertex_count = len(gadget["port_specs"])
    ordinary_matching = 1
    actual_states = gadget["selected_physical_route_count"]
    checks["dense_hyperedge"] = {
        "ports": vertex_count,
        "ordinary_matching": ordinary_matching,
        "ports_minus_matching": vertex_count - ordinary_matching,
        "actual_states": actual_states,
        "required_savings_weight": vertex_count - actual_states,
    }
    print(json.dumps(checks, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

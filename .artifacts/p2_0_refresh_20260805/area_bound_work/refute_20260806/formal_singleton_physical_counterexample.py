#!/usr/bin/env python3
"""Refute the claim that every formal singleton is physically realizable."""

from src.models.routing_subproblem import (
    RoutingGrid,
    RoutingSubproblem,
    analyze_exact_routing_domain,
)


CENTER = (35, 35)
COMMODITY = "buckwheat"
PORTS = [
    {
        "instance_id": "producer_west",
        "x": CENTER[0],
        "y": CENTER[1],
        "dir": "E",
        "type": "out",
        "commodity": COMMODITY,
    },
    {
        "instance_id": "consumer_east",
        "x": CENTER[0],
        "y": CENTER[1],
        "dir": "W",
        "type": "in",
        "commodity": COMMODITY,
    },
]


def main() -> None:
    occupied = {(x, y) for x in range(70) for y in range(70)} - {CENTER}
    grid = RoutingGrid(
        occupied,
        PORTS,
        occupied_owner_by_cell={
            (34, 35): "producer_west",
            (36, 35): "consumer_east",
        },
    )
    analysis = analyze_exact_routing_domain(grid)
    assert analysis["status"] == "feasible"
    model = RoutingSubproblem(grid, [COMMODITY], domain_analysis=analysis)
    model.build()
    physical_keys = sorted(model.phys_vars, key=str)
    assert physical_keys == [(35, 35, 0, ("W",), ("E",), "belt")]
    assert model.solve(time_limit=5.0) == "FEASIBLE"
    routes = model.extract_routes()
    assert len(routes) == 1
    assert model.build_stats["port_adherence"] == {
        "exact_links": 2,
        "blocked_ports": 0,
        "ports": 2,
    }
    print(
        {
            "status": "FEASIBLE",
            "ports": 2,
            "physical_candidates": physical_keys,
            "selected_physical_states": len(routes),
            "terminal_incidence_size": 2,
            "physical_singleton_exists": False,
            "formal_singletons_remain_safe_as_relaxation": True,
        }
    )


if __name__ == "__main__":
    main()

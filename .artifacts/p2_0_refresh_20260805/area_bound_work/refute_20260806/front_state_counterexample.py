from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path("/home/zhuran24/zmd-pj")
sys.path.insert(0, str(ROOT))

from src.models.port_binding import enumerate_pose_level_port_bindings
from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem
from src.placement.placement_generator import build_placement_obj, get_edge_ports


CENTER = (20, 20)


def square_pose(x: int, y: int, size: int, in_edge: str, out_edge: str, mode: str):
    return build_placement_obj(
        x,
        y,
        0,
        mode,
        size,
        size,
        get_edge_ports(x, y, size, size, in_edge),
        get_edge_ports(x, y, size, size, out_edge),
    )


def choose_binding(operation: str, pose: dict, port_type: str, commodity: str, cell: tuple[int, int]):
    side = "output_ports" if port_type == "out" else "input_ports"
    for binding in enumerate_pose_level_port_bindings(operation, pose):
        for port in binding[side]:
            if port["commodity"] == commodity and (port["x"], port["y"]) == cell:
                return binding, port
    raise AssertionError((operation, port_type, commodity, cell))


def main() -> None:
    # Three canonical poses around one free cell.  Their bodies are disjoint.
    planter = square_pose(16, 15, 5, "bottom", "top", "BT")
    crusher = square_pose(18, 21, 3, "bottom", "top", "BT")
    collector = square_pose(21, 16, 5, "left", "right", "LR")
    bodies = {
        "planter_buckwheat": {tuple(c) for c in planter["occupied_cells"]},
        "crusher_buckwheat": {tuple(c) for c in crusher["occupied_cells"]},
        "seed_collector_buckwheat": {tuple(c) for c in collector["occupied_cells"]},
    }
    names = list(bodies)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            assert not (bodies[left] & bodies[right]), (left, right)
    assert CENTER not in set().union(*bodies.values())

    _pb, source = choose_binding("planter_buckwheat", planter, "out", "buckwheat", CENTER)
    _cb, sink_a = choose_binding("crusher_buckwheat", crusher, "in", "buckwheat", CENTER)
    _sb, sink_b = choose_binding("seed_collector_buckwheat", collector, "in", "buckwheat", CENTER)

    ports = [
        {"instance_id": "planter_resolved", "x": source["x"], "y": source["y"],
         "dir": source["dir"], "type": "out", "commodity": "buckwheat"},
        {"instance_id": "crusher_residual_half", "x": sink_a["x"], "y": sink_a["y"],
         "dir": sink_a["dir"], "type": "in", "commodity": "buckwheat"},
        {"instance_id": "collector_residual_half", "x": sink_b["x"], "y": sink_b["y"],
         "dir": sink_b["dir"], "type": "in", "commodity": "buckwheat"},
    ]
    assert [(p["dir"], p["type"]) for p in ports] == [("N", "out"), ("S", "in"), ("W", "in")]

    occupied = {(x, y) for x in range(70) for y in range(70) if (x, y) != CENTER}
    analysis = {
        "status": "feasible",
        "commodity_component_cells": {"buckwheat": [list(CENTER)]},
        "commodity_active_cells": {"buckwheat": [list(CENTER)]},
        "domain_stats": {},
    }
    routing = RoutingSubproblem(RoutingGrid(occupied, ports), ["buckwheat"], domain_analysis=analysis)
    routing.build()
    matching = [
        key
        for key, meta in routing._state_meta.items()
        if key[0:3] == (20, 20, 0)
        and set(meta["flow_in"]) == {"S"}
        and set(meta["flow_out"]) == {"N", "E"}
        and meta["component_type"] == "splitter"
    ]
    assert len(matching) == 1, matching
    chosen = matching[0]
    for key, var in routing.use_vars.items():
        routing.model.Add(var == int(key == chosen))
    status = routing.solve(time_limit=5.0)
    assert status == "FEASIBLE", routing.build_stats.get("last_solve")
    selected = routing.extract_routes()
    assert len(selected) == 1 and selected[0]["component_type"] == "splitter", selected

    print(json.dumps({
        "status": status,
        "center": CENTER,
        "canonical_operations": list(bodies),
        "bodies_pairwise_disjoint": True,
        "ports": ports,
        "selected_route_states": selected,
        "front_incidence": {"producer_fronts": 1, "consumer_fronts": 2, "physical_states": 1},
        "rate_assignment_items_per_tick": {
            "planter_output": "1",
            "crusher_residual_input": "1/2",
            "seed_collector_residual_input": "1/2",
            "splitter_aggregate": "1",
        },
    }, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

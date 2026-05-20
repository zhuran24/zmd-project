"""Tests for canonical blueprint output schema and serializer."""

from __future__ import annotations

import json
from pathlib import Path

from src.io.output_schema import normalize_blueprint_payload
from src.io.serializer import build_canonical_blueprint_payload, serialize_blueprint_payload
from src.render.blueprint_exporter import export_blueprint


def _sample_payload_inputs() -> tuple[dict, list[dict], dict, float, int, dict]:
    placement_solution = {
        "smelter_001": {
            "pose_idx": 0,
            "pose_id": "smelter_pose_0",
            "anchor": {"x": 3, "y": 4},
            "facility_type": "smelter",
        }
    }
    routing_solution = [
        {
            "x": 5,
            "y": 4,
            "layer": 0,
            "component_type": "belt",
            "commodity": "iron_plate",
            "flow_in": ["W"],
            "flow_out": ["E"],
        },
        {
            "x": 6,
            "y": 4,
            "layer": 1,
            "commodity": "iron_plate",
            "flow_in": ["W"],
            "flow_out": ["E"],
        },
    ]
    ghost_rect = {"w": 5, "h": 4, "area": 20, "anchor_x": 8, "anchor_y": 9}
    solve_time = 12.5
    benders_iterations = 3
    facility_pools = {
        "smelter": [
            {
                "pose_id": "smelter_pose_0",
                "anchor": {"x": 3, "y": 4},
                "pose_params": {"orientation": 1, "port_mode": "left_right"},
                "input_port_cells": [{"x": 3, "y": 4, "dir": "W", "commodity": "ore"}],
                "output_port_cells": [{"x": 4, "y": 4, "dir": "E", "commodity": "iron_plate"}],
                "occupied_cells": [[3, 4], [4, 4]],
                "power_coverage_cells": None,
            }
        ]
    }
    return placement_solution, routing_solution, ghost_rect, solve_time, benders_iterations, facility_pools


def test_blueprint_serializer_round_trip_is_canonical() -> None:
    placement_solution, routing_solution, ghost_rect, solve_time, benders_iterations, facility_pools = (
        _sample_payload_inputs()
    )

    payload = build_canonical_blueprint_payload(
        placement_solution=placement_solution,
        routing_solution=routing_solution,
        ghost_rect=ghost_rect,
        solve_time_seconds=solve_time,
        benders_iterations=benders_iterations,
        facility_pools=facility_pools,
        export_timestamp="2026-03-23T00:00:00Z",
    )
    serialized = serialize_blueprint_payload(payload)
    reparsed = normalize_blueprint_payload(json.loads(serialized))

    assert reparsed == payload
    assert payload["metadata"]["version"] == "1.0.0"
    assert payload["objective_achieved"]["empty_rect"]["score"] == 20.0
    assert payload["facilities"][0]["active_ports"][0]["commodity"] == "ore"
    assert payload["routing_network"]["L1_elevated"]["6,4"]["type"] == "bridge"


def test_blueprint_exporter_matches_canonical_serializer(tmp_path: Path) -> None:
    placement_solution, routing_solution, ghost_rect, solve_time, benders_iterations, facility_pools = (
        _sample_payload_inputs()
    )
    output_path = tmp_path / "optimal_blueprint.json"

    exported = export_blueprint(
        placement_solution=placement_solution,
        routing_solution=routing_solution,
        ghost_rect=ghost_rect,
        solve_time=solve_time,
        benders_iterations=benders_iterations,
        facility_pools=facility_pools,
        output_path=output_path,
    )

    expected = build_canonical_blueprint_payload(
        placement_solution=placement_solution,
        routing_solution=routing_solution,
        ghost_rect=ghost_rect,
        solve_time_seconds=solve_time,
        benders_iterations=benders_iterations,
        facility_pools=facility_pools,
        export_timestamp=exported["metadata"]["export_timestamp"],
    )

    assert exported == expected
    assert json.loads(output_path.read_text(encoding="utf-8")) == expected

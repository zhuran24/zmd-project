from __future__ import annotations

import json

from src.search.topology_guidance import (
    compute_topology_guidance_metrics,
    log_topology_guidance_observation,
)


class _ListLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, template: str, payload: str) -> None:
        self.messages.append(template % payload)


def _toy_skeleton() -> dict:
    return {
        "node_groups": [
            {
                "group_id": "operation:alpha",
                "operation_type": "alpha",
                "instance_ids": ["alpha_001"],
            },
            {
                "group_id": "operation:beta",
                "operation_type": "beta",
                "instance_ids": ["beta_001"],
            },
            {
                "group_id": "operation:gamma",
                "operation_type": "gamma",
                "instance_ids": ["gamma_001"],
            },
        ],
        "material_edges": [
            {
                "commodity_id": "steel_block",
                "producers": [{"group_id": "operation:alpha"}],
                "consumers": [
                    {"group_id": "operation:beta"},
                    {"group_id": "operation:gamma"},
                ],
            }
        ],
    }


def _toy_layout() -> dict:
    return {
        "alpha_001": {"operation_type": "alpha", "anchor": {"x": 0, "y": 0}},
        "beta_001": {"operation_type": "beta", "anchor": {"x": 10, "y": 0}},
        "gamma_001": {"operation_type": "gamma", "anchor": {"x": 0, "y": 10}},
    }


def test_topology_guidance_computes_distance_dispersion_and_partition_metrics() -> None:
    metrics = compute_topology_guidance_metrics(
        _toy_layout(),
        _toy_skeleton(),
        grid_width=12,
        grid_height=12,
        routing_failure_summary={"status": "front_blocked", "commodity": "steel_block"},
    )

    steel = metrics["commodity_metrics"]["steel_block"]
    assert steel["average_producer_consumer_manhattan"] == 10
    assert steel["endpoint_dispersion_manhattan"] == 8.888889
    assert steel["estimated_cross_partition_pairs"] == 2
    assert metrics["routing_failure_bottleneck_commodities"] == ["steel_block"]
    assert metrics["consumption_policy"] == {
        "may_change_candidate_verdict": False,
        "may_feed_gate": False,
        "may_feed_cut": False,
        "may_feed_proof": False,
        "throughput_capacity_metrics_in_scope": False,
    }


def test_topology_guidance_log_helper_preserves_candidate_verdict_bit_for_bit() -> None:
    logger = _ListLogger()
    verdict = {"status": "INFEASIBLE", "proof_summary": {"master_status": "INFEASIBLE"}}

    returned = log_topology_guidance_observation(
        logger,
        verdict=verdict,
        layout_solution=_toy_layout(),
        material_skeleton=_toy_skeleton(),
        routing_failure_summary={"status": "front_blocked"},
    )

    assert returned is verdict
    assert logger.messages
    prefix, payload = logger.messages[0].split(" ", 1)
    assert prefix == "topology_guidance_observation"
    decoded = json.loads(payload)
    assert decoded["classification"] == "diagnostic_observation_only"
    assert verdict == {"status": "INFEASIBLE", "proof_summary": {"master_status": "INFEASIBLE"}}

"""Observation-only material-topology metrics.

This module deliberately exposes pure helpers. It is not imported by the solver
entry points and it never writes candidate records, gates, cuts, receipts, or
publication artifacts.
"""

from __future__ import annotations

import json
import math
from typing import Any, Mapping, Sequence

DEFAULT_GRID_WIDTH = 70
DEFAULT_GRID_HEIGHT = 70


def compute_topology_guidance_metrics(
    layout_solution: Mapping[str, Any],
    material_skeleton: Mapping[str, Any],
    *,
    grid_width: int = DEFAULT_GRID_WIDTH,
    grid_height: int = DEFAULT_GRID_HEIGHT,
    routing_failure_summary: Any = None,
) -> dict[str, Any]:
    """Return human-readable topology metrics for a placed candidate layout."""

    operation_points = _operation_points(layout_solution, material_skeleton)
    partition_x = float(grid_width) / 2.0
    partition_y = float(grid_height) / 2.0
    commodity_metrics: dict[str, Any] = {}

    for edge in _material_edges(material_skeleton):
        commodity_id = str(edge.get("commodity_id", "")).strip()
        if not commodity_id:
            continue
        producer_points = _points_for_endpoints(edge.get("producers"), operation_points)
        consumer_points = _points_for_endpoints(edge.get("consumers"), operation_points)
        pair_distances = [
            _manhattan(producer, consumer)
            for producer in producer_points
            for consumer in consumer_points
        ]
        all_points = producer_points + consumer_points
        commodity_metrics[commodity_id] = {
            "producer_point_count": len(producer_points),
            "consumer_point_count": len(consumer_points),
            "average_producer_consumer_manhattan": _average(pair_distances),
            "endpoint_dispersion_manhattan": _endpoint_dispersion(all_points),
            "estimated_cross_partition_pairs": _cross_partition_count(
                producer_points,
                consumer_points,
                partition_x=partition_x,
                partition_y=partition_y,
            ),
            "observation_only": True,
        }

    return {
        "profile": "topology_guidance_observation_v1",
        "classification": "diagnostic_observation_only",
        "consumption_policy": {
            "may_change_candidate_verdict": False,
            "may_feed_gate": False,
            "may_feed_cut": False,
            "may_feed_proof": False,
            "throughput_capacity_metrics_in_scope": False,
        },
        "commodity_metrics": commodity_metrics,
        "routing_failure_bottleneck_commodities": identify_bottleneck_commodities(
            commodity_metrics,
            routing_failure_summary=routing_failure_summary,
        ),
    }


def log_topology_guidance_observation(
    logger: Any,
    *,
    verdict: Any,
    layout_solution: Mapping[str, Any],
    material_skeleton: Mapping[str, Any],
    routing_failure_summary: Any = None,
) -> Any:
    """Log metrics and return the original verdict unchanged."""

    metrics = compute_topology_guidance_metrics(
        layout_solution,
        material_skeleton,
        routing_failure_summary=routing_failure_summary,
    )
    logger.info(
        "topology_guidance_observation %s",
        json.dumps(metrics, sort_keys=True, separators=(",", ":"), allow_nan=False),
    )
    return verdict


def identify_bottleneck_commodities(
    commodity_metrics: Mapping[str, Mapping[str, Any]],
    *,
    routing_failure_summary: Any = None,
    limit: int = 5,
) -> list[str]:
    """Pick likely bottleneck commodities for a failed route observation."""

    failure_text = json.dumps(routing_failure_summary, sort_keys=True, default=str)
    explicit = [
        commodity_id
        for commodity_id in sorted(commodity_metrics)
        if commodity_id and commodity_id in failure_text
    ]
    if explicit:
        return explicit[:limit]
    if not routing_failure_summary:
        return []

    scored: list[tuple[float, str]] = []
    for commodity_id, metrics in commodity_metrics.items():
        distance = _optional_float(metrics.get("average_producer_consumer_manhattan"))
        dispersion = _optional_float(metrics.get("endpoint_dispersion_manhattan"))
        crossings = _optional_float(metrics.get("estimated_cross_partition_pairs")) or 0.0
        score = (distance or 0.0) + (dispersion or 0.0) + crossings
        if score > 0:
            scored.append((score, str(commodity_id)))
    return [commodity_id for _score, commodity_id in sorted(scored, reverse=True)[:limit]]


def _material_edges(material_skeleton: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    raw_edges = material_skeleton.get("material_edges", ())
    if not isinstance(raw_edges, Sequence) or isinstance(raw_edges, (str, bytes)):
        return ()
    return [edge for edge in raw_edges if isinstance(edge, Mapping)]


def _operation_points(
    layout_solution: Mapping[str, Any],
    material_skeleton: Mapping[str, Any],
) -> dict[str, list[tuple[float, float]]]:
    instance_to_operation = _instance_to_operation(material_skeleton)
    operation_points: dict[str, list[tuple[float, float]]] = {}
    for raw_instance_id, raw_entry in layout_solution.items():
        if not isinstance(raw_entry, Mapping):
            continue
        entry = dict(raw_entry)
        instance_id = str(entry.get("instance_id") or raw_instance_id)
        operation_type = str(entry.get("operation_type") or instance_to_operation.get(instance_id, ""))
        if not operation_type:
            continue
        point = _entry_point(entry)
        if point is None:
            continue
        operation_points.setdefault(operation_type, []).append(point)
    return operation_points


def _instance_to_operation(material_skeleton: Mapping[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    raw_groups = material_skeleton.get("node_groups", ())
    if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes)):
        return mapping
    for raw_group in raw_groups:
        if not isinstance(raw_group, Mapping):
            continue
        operation_type = str(raw_group.get("operation_type", ""))
        raw_instance_ids = raw_group.get("instance_ids", ())
        if not isinstance(raw_instance_ids, Sequence) or isinstance(raw_instance_ids, (str, bytes)):
            continue
        for instance_id in raw_instance_ids:
            mapping[str(instance_id)] = operation_type
    return mapping


def _points_for_endpoints(
    raw_endpoints: Any,
    operation_points: Mapping[str, Sequence[tuple[float, float]]],
) -> list[tuple[float, float]]:
    if not isinstance(raw_endpoints, Sequence) or isinstance(raw_endpoints, (str, bytes)):
        return []
    points: list[tuple[float, float]] = []
    for endpoint in raw_endpoints:
        if not isinstance(endpoint, Mapping):
            continue
        group_id = str(endpoint.get("group_id", ""))
        if not group_id.startswith("operation:"):
            continue
        operation_type = group_id.split(":", 1)[1]
        points.extend(operation_points.get(operation_type, ()))
    return points


def _entry_point(entry: Mapping[str, Any]) -> tuple[float, float] | None:
    occupied = entry.get("occupied_cells")
    if isinstance(occupied, Sequence) and not isinstance(occupied, (str, bytes)) and occupied:
        cells = []
        for cell in occupied:
            point = _xy_pair(cell)
            if point is not None:
                cells.append(point)
        if cells:
            return (
                sum(point[0] for point in cells) / len(cells),
                sum(point[1] for point in cells) / len(cells),
            )

    anchor = entry.get("anchor")
    point = _xy_pair(anchor)
    if point is not None:
        return point
    if "x" in entry and "y" in entry:
        return _xy_pair(entry)
    return None


def _xy_pair(value: Any) -> tuple[float, float] | None:
    if isinstance(value, Mapping):
        raw_x = value.get("x")
        raw_y = value.get("y")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        raw_x = value[0]
        raw_y = value[1]
    else:
        return None
    if isinstance(raw_x, bool) or isinstance(raw_y, bool):
        return None
    if not isinstance(raw_x, (int, float)) or not isinstance(raw_y, (int, float)):
        return None
    if not math.isfinite(float(raw_x)) or not math.isfinite(float(raw_y)):
        return None
    return float(raw_x), float(raw_y)


def _manhattan(left: tuple[float, float], right: tuple[float, float]) -> float:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _average(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _endpoint_dispersion(points: Sequence[tuple[float, float]]) -> float | None:
    if not points:
        return None
    centroid = (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
    return _average([_manhattan(point, centroid) for point in points])


def _cross_partition_count(
    producers: Sequence[tuple[float, float]],
    consumers: Sequence[tuple[float, float]],
    *,
    partition_x: float,
    partition_y: float,
) -> int:
    crossings = 0
    for producer in producers:
        for consumer in consumers:
            crosses_x = (producer[0] < partition_x <= consumer[0]) or (
                consumer[0] < partition_x <= producer[0]
            )
            crosses_y = (producer[1] < partition_y <= consumer[1]) or (
                consumer[1] < partition_y <= producer[1]
            )
            if crosses_x or crosses_y:
                crossings += 1
    return crossings


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)

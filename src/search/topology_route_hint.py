"""Topology-aware routing hints (diagnostic, unwired).

Given the exploratory material skeleton and a *placed* candidate layout, this
module derives, per commodity, a "corridor": the axis-aligned region between the
centroid of that commodity's placed producers and the centroid of its placed
consumers.  Elevated routing cells that fall *outside* the corridor are detours,
so the module suggests biasing them toward "not used" (hint value ``0``).

This is a pure planner returning data only.  It never adds constraints, never
shrinks a domain, never forces a variable to ``1``, never writes a checkpoint,
gate, cut, receipt, or publication artifact, and never feeds proof.  The hints
it emits are soft preferences in the exact sense of CP-SAT ``AddHint`` — they
cannot change the feasible set or the optimum.

Intended (future, separately reviewed) wire point:
``src/models/routing_subproblem.py::_add_bridge_count_hint`` already hints every
elevated (L1) cell var toward ``0`` ("prefer few bridges").  A topology-aware
extension would additionally hint *off-corridor* elevated cells toward ``0`` for
their commodity.  This module is deliberately NOT imported by the solver in this
change; wiring is deferred to a measured, gated step.

When wiring lands: because ``_add_bridge_count_hint`` already hints EVERY elevated
cell toward ``0``, these off-corridor ``0`` suggestions are a strict subset of that
blanket hint (the merged effect is identical and the value is always ``0``).  Never
emit a hint value other than ``0`` and never turn any of this into a constraint or a
variable fix.  ``margin`` is expected to be ``>= 0``.

Contributor note: ``src/search`` is scanned by the close-kernel proof-obligations
gate.  Keep this diagnostic module free of the certified terminal-status string
literals (the all-caps terminal status words) and the sink-marker phrase the gate
keys on — such literals here hard-fail the gate as an unregistered sink.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "compute_route_corridors",
    "compute_route_hints",
    "corridor_contains_cell",
]

OPERATION_GROUP_PREFIX = "operation:"


def compute_route_corridors(
    material_skeleton: Mapping[str, Any],
    placement: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return a per-commodity corridor derived from placed operation instances.

    A corridor exists only for commodities that have at least one placed
    producer *and* one placed consumer operation.  Pure read of the inputs.
    """

    operation_points = _operation_points(placement, material_skeleton)
    corridors: dict[str, dict[str, Any]] = {}
    for edge in _material_edges(material_skeleton):
        commodity_id = str(edge.get("commodity_id", "")).strip()
        if not commodity_id:
            continue
        producer_points = _endpoint_points(edge.get("producers"), operation_points)
        consumer_points = _endpoint_points(edge.get("consumers"), operation_points)
        if not producer_points or not consumer_points:
            continue
        producer_centroid = _centroid(producer_points)
        consumer_centroid = _centroid(consumer_points)
        xs = (producer_centroid[0], consumer_centroid[0])
        ys = (producer_centroid[1], consumer_centroid[1])
        corridors[commodity_id] = {
            "commodity_id": commodity_id,
            "producer_centroid": [producer_centroid[0], producer_centroid[1]],
            "consumer_centroid": [consumer_centroid[0], consumer_centroid[1]],
            "band": [min(xs), min(ys), max(xs), max(ys)],
        }
    return corridors


def corridor_contains_cell(
    corridor: Mapping[str, Any],
    cell: Any,
    *,
    margin: float = 0.0,
) -> bool:
    """True if ``cell`` lies within the corridor band (expanded by ``margin``)."""

    point = _xy_pair(cell)
    if point is None:
        return False
    band = corridor.get("band")
    if not isinstance(band, Sequence) or len(band) != 4:
        return False
    x_min, y_min, x_max, y_max = (float(band[0]), float(band[1]), float(band[2]), float(band[3]))
    return (
        x_min - margin <= point[0] <= x_max + margin
        and y_min - margin <= point[1] <= y_max + margin
    )


def compute_route_hints(
    material_skeleton: Mapping[str, Any],
    placement: Mapping[str, Any],
    commodity_cells: Mapping[str, Iterable[Any]],
    *,
    margin: float = 0.0,
) -> list[dict[str, Any]]:
    """Suggest ``hint=0`` for off-corridor elevated cells, per commodity.

    Only off-corridor cells get a suggestion, and the only suggested value is
    ``0`` (avoid) — never ``1``.  Deterministic: output is sorted by
    ``(commodity_id, x, y)``.  Cells with non-integer/garbage coordinates are
    ignored.  Pure; inputs are not mutated.
    """

    corridors = compute_route_corridors(material_skeleton, placement)
    hints: list[dict[str, Any]] = []
    for commodity_id, raw_cells in commodity_cells.items():
        commodity_key = str(commodity_id).strip()
        corridor = corridors.get(commodity_key)
        if corridor is None:
            continue
        seen: set[tuple[int, int]] = set()
        for raw_cell in _sequence(raw_cells):
            point = _int_cell(raw_cell)
            if point is None or point in seen:
                continue
            seen.add(point)
            if not corridor_contains_cell(corridor, point, margin=margin):
                hints.append(
                    {
                        "commodity_id": commodity_key,
                        "cell": [point[0], point[1]],
                        "suggested_hint": 0,
                    }
                )
    hints.sort(key=lambda item: (item["commodity_id"], item["cell"][0], item["cell"][1]))
    return hints


def _material_edges(material_skeleton: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [edge for edge in _sequence(material_skeleton.get("material_edges")) if isinstance(edge, Mapping)]


def _operation_points(
    placement: Mapping[str, Any],
    material_skeleton: Mapping[str, Any],
) -> dict[str, list[tuple[float, float]]]:
    instance_to_operation = _instance_to_operation(material_skeleton)
    points: dict[str, list[tuple[float, float]]] = {}
    for raw_instance_id, raw_entry in placement.items():
        if not isinstance(raw_entry, Mapping):
            continue
        instance_id = str(raw_entry.get("instance_id") or raw_instance_id)
        operation_type = str(
            raw_entry.get("operation_type") or instance_to_operation.get(instance_id, "")
        ).strip()
        if not operation_type:
            continue
        point = _entry_point(raw_entry)
        if point is not None:
            points.setdefault(operation_type, []).append(point)
    return points


def _instance_to_operation(material_skeleton: Mapping[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group in _sequence(material_skeleton.get("node_groups")):
        if not isinstance(group, Mapping):
            continue
        operation_type = str(group.get("operation_type", "")).strip()
        if not operation_type:
            continue
        for instance_id in _sequence(group.get("instance_ids")):
            instance_key = str(instance_id).strip()
            if instance_key:
                mapping[instance_key] = operation_type
    return mapping


def _endpoint_points(
    raw_endpoints: Any,
    operation_points: Mapping[str, Sequence[tuple[float, float]]],
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for endpoint in _sequence(raw_endpoints):
        if not isinstance(endpoint, Mapping):
            continue
        group_id = str(endpoint.get("group_id", ""))
        if not group_id.startswith(OPERATION_GROUP_PREFIX):
            continue
        operation_type = group_id[len(OPERATION_GROUP_PREFIX):]
        points.extend(operation_points.get(operation_type, ()))
    return points


def _entry_point(entry: Mapping[str, Any]) -> tuple[float, float] | None:
    occupied = entry.get("occupied_cells")
    cells: list[tuple[float, float]] = []
    for cell in _sequence(occupied):
        point = _xy_pair(cell)
        if point is not None:
            cells.append(point)
    if cells:
        return (
            sum(point[0] for point in cells) / len(cells),
            sum(point[1] for point in cells) / len(cells),
        )
    anchor_point = _xy_pair(entry.get("anchor"))
    if anchor_point is not None:
        return anchor_point
    if "x" in entry and "y" in entry:
        return _xy_pair(entry)
    return None


def _centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


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
    x_value = float(raw_x)
    y_value = float(raw_y)
    if x_value != x_value or y_value != y_value:  # NaN guard
        return None
    if x_value in (float("inf"), float("-inf")) or y_value in (float("inf"), float("-inf")):
        return None
    return x_value, y_value


def _int_cell(value: Any) -> tuple[int, int] | None:
    point = _xy_pair(value)
    if point is None:
        return None
    if point[0] != int(point[0]) or point[1] != int(point[1]):
        return None
    return int(point[0]), int(point[1])


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()

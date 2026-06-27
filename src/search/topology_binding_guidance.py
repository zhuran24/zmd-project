"""Topology-aware binding-search ordering (diagnostic, unwired).

This module derives a *branching order* over binding instances from the
exploratory material-connection skeleton.  It is a pure planner: given the
skeleton and a set of binding instance ids, it returns those same ids in a
topology-prioritised order.  It never adds constraints, never shrinks any
variable domain, never writes a checkpoint, gate, cut, receipt, or publication
artifact, and never feeds proof.

Intended (future, separately reviewed) wire point:
``src/models/binding_subproblem.py::_add_search_guidance`` currently iterates
``sorted(self.binding_vars)`` (instance ids in lexicographic order) and applies
``AddDecisionStrategy(ordered_vars, CHOOSE_FIRST, SELECT_MAX_VALUE)`` per
instance.  Replacing the lexicographic instance order with
``compute_topology_binding_order(skeleton, self.binding_vars)`` would only change
the *order* in which instances are branched — not the strategy, the constraints,
or the feasible set.  This module is deliberately NOT imported by the solver in
this change; wiring is deferred to a measured, gated step.

Rationale for the order: an operation that touches highly shared material pools
(many producers/consumers on one commodity edge, e.g. ``steel_block``) is more
entangled with the rest of the layout, so branching on it first tends to
propagate constraints earlier and fail faster.  This is a search heuristic only.

Contributor note: ``src/search`` is scanned by the close-kernel proof-obligations
gate (``scripts/check_p1_2_proof_obligations.py``).  Keep this diagnostic module
free of the certified terminal-status string literals (the all-caps terminal
status words) and the sink-marker phrase the gate keys on — adding such literals
here, even in a comment, hard-fails the gate as an unregistered sink.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "compute_operation_topology_weight",
    "compute_topology_binding_order",
]


def compute_operation_topology_weight(
    material_skeleton: Mapping[str, Any],
) -> dict[str, tuple[int, int, int, int]]:
    """Return a per-operation entanglement weight derived from the skeleton.

    The weight is a tuple ``(pool_pressure, shared_pool_count, commodity_count,
    machine_count)``; larger is "branch earlier".  Pure read of the skeleton.
    """

    edges_by_commodity = _edges_by_commodity(material_skeleton)
    weights: dict[str, tuple[int, int, int, int]] = {}
    for group in _node_groups(material_skeleton):
        operation_type = str(group.get("operation_type", "")).strip()
        if not operation_type:
            continue
        commodities = _group_commodities(group)
        pool_pressure = 0
        shared_pool_count = 0
        for commodity_id in commodities:
            edge = edges_by_commodity.get(commodity_id)
            if edge is None:
                continue
            producers = _edge_endpoints(edge.get("producers"))
            consumers = _edge_endpoints(edge.get("consumers"))
            pool_pressure += producers + consumers
            if bool(edge.get("pool_exchangeable")):
                shared_pool_count += 1
        machine_count = _non_negative_int(group.get("machine_count"))
        weights[operation_type] = (
            pool_pressure,
            shared_pool_count,
            len(commodities),
            machine_count,
        )
    return weights


def compute_topology_binding_order(
    material_skeleton: Mapping[str, Any],
    instance_ids: Iterable[str],
) -> list[str]:
    """Reorder ``instance_ids`` by descending operation topology weight.

    The result is a permutation of the unique input ids: every input id appears
    exactly once, nothing is added or dropped.  Operations are ordered by
    descending weight with a lexicographic tie-break; within an operation the
    instance ids are sorted ascending (matching the current lexicographic
    default).  Ids the skeleton does not know about are appended last, sorted.
    Deterministic and side-effect free.
    """

    unique_ids = sorted({str(instance_id) for instance_id in instance_ids})
    instance_to_operation = _instance_to_operation(material_skeleton)
    weights = compute_operation_topology_weight(material_skeleton)

    known: list[str] = []
    unknown: list[str] = []
    for instance_id in unique_ids:
        if instance_id in instance_to_operation:
            known.append(instance_id)
        else:
            unknown.append(instance_id)

    def order_key(instance_id: str) -> tuple[Any, ...]:
        operation_type = instance_to_operation[instance_id]
        pool_pressure, shared_pool_count, commodity_count, machine_count = weights.get(
            operation_type, (0, 0, 0, 0)
        )
        # Negative numerics => descending weight; operation_type / instance_id
        # ascending for a stable, deterministic tie-break.
        return (
            -pool_pressure,
            -shared_pool_count,
            -commodity_count,
            -machine_count,
            operation_type,
            instance_id,
        )

    known.sort(key=order_key)
    return known + unknown


def _edges_by_commodity(material_skeleton: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    edges: dict[str, Mapping[str, Any]] = {}
    for edge in _sequence(material_skeleton.get("material_edges")):
        if not isinstance(edge, Mapping):
            continue
        commodity_id = str(edge.get("commodity_id", "")).strip()
        if commodity_id:
            edges[commodity_id] = edge
    return edges


def _node_groups(material_skeleton: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [group for group in _sequence(material_skeleton.get("node_groups")) if isinstance(group, Mapping)]


def _instance_to_operation(material_skeleton: Mapping[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group in _node_groups(material_skeleton):
        operation_type = str(group.get("operation_type", "")).strip()
        if not operation_type:
            continue
        for instance_id in _sequence(group.get("instance_ids")):
            # Key by the same normalisation the caller uses for membership
            # (raw ``str(instance_id)``), so a known instance is never mis-bucketed
            # into the unknown tail; skip blank/whitespace-only ids.
            instance_key = str(instance_id)
            if instance_key.strip():
                mapping[instance_key] = operation_type
    return mapping


def _group_commodities(group: Mapping[str, Any]) -> set[str]:
    commodities: set[str] = set()
    for key in ("input_commodities", "output_commodities"):
        for commodity_id in _sequence(group.get(key)):
            commodity_key = str(commodity_id).strip()
            if commodity_key:
                commodities.add(commodity_key)
    return commodities


def _edge_endpoints(raw_endpoints: Any) -> int:
    return sum(1 for endpoint in _sequence(raw_endpoints) if isinstance(endpoint, Mapping))


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value if value > 0 else 0


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()

"""Deterministic replay and validation of a routing-aware shelf candidate.

The expensive search runs only in the cgroup-contracted worker.  This module
owns its explicit JSON hand-off: group-level manufacturing slots are replayed
against the current pinned inputs, assigned to strict required IDs, combined
with the fixed boundary/core geometry and poles, and checked locally before the
router is allowed to consume the result.  There is deliberately no implicit
"latest" artifact and no inline solver fallback.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
import importlib
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


geometry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.geometry"
)
network_router = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.network_router"
)
strict_contract = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.strict_contract"
)
cgroup_telemetry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.cgroup_telemetry"
)

Cell = tuple[int, int]
Anchor = tuple[int, int]
DirectedEdge = tuple[Cell, Cell]

GRID_WIDTH = 70
GRID_HEIGHT = 70
FIXED_BOUNDARY_PATTERN = geometry.BoundaryPattern(69, 0)
FIXED_CORE_ANCHOR: Anchor = (3, 53)
FIXED_CHORD_LEVELS = (5, 10, 14, 20, 24, 29, 33, 39, 43, 48, 52, 58, 63)
SHELF_RESULT_SCHEMA_VERSION = "witness_shelf_power_result_v1"
# The rotated 7x6 protected rectangle consumes one 5x5 shelf slot.  Interleaved
# 3x3/5x5/6x4 bands place the four spare 6x4 slots at four different heights,
# so the joint power model can distribute pole bays instead of clustering them
# below a monolithic template block.
SHELF_PROTECTED_RECT = geometry.Rect(2, 34, 7, 6)
CORE_WEST_BUS_X = 2
CORE_EAST_BUS_X = 12
CORE_BUS_LOWER_LEVEL = 52
CORE_BUS_UPPER_LEVEL = 63
CORE_BLOCKED_CHORD_LEVELS = (58,)
# A left-boundary source attaches at every y == 1 (mod 3).  Starting an
# eastbound chord at one of those cells would compile to a two-channel cross:
# the vertical outer-cycle lane and horizontal chord lane could not exchange
# flow.  Each affected chord therefore enters from the next body-row cell via
# a two-edge jog.  The y=52 jog is also the west half of the core bypass.
LEFT_CHORD_JOG_LEVELS = (10, 43, 52)
EXPECTED_REQUIRED_COUNTS = {
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
    "protocol_core": 1,
    "boundary_storage_port": 46,
}
MIN_FULL_WITNESS_POLES = 9


class ShelfConstructionError(ValueError):
    """Stable fail-closed error for shelf assembly or local validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, order=True)
class GeometrySlot:
    """One strict facility pose before a symmetric required ID is assigned."""

    template: str
    mode: str
    anchor: Anchor
    operation: str = ""


@dataclass(frozen=True)
class ShelfPlacement:
    instance_id: str
    template: str
    operation: str
    mode: str
    anchor: Anchor
    pose_idx: int
    body_cells: frozenset[Cell]
    input_front_cells: tuple[Cell, ...]
    output_front_cells: tuple[Cell, ...]

    @property
    def all_front_cells(self) -> tuple[Cell, ...]:
        return self.input_front_cells + self.output_front_cells

    def strict_record(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "template": self.template,
            "mode": self.mode,
            "anchor": {"x": self.anchor[0], "y": self.anchor[1]},
        }


@dataclass(frozen=True)
class ShelfCandidate:
    """Locally legal geometry ready for binding and deterministic routing."""

    placements: tuple[ShelfPlacement, ...]
    pole_placements: tuple[ShelfPlacement, ...]
    pole_bay_anchors: tuple[Anchor, ...]
    network_edges: frozenset[DirectedEdge]
    reserved_network_cells: frozenset[Cell]
    protected_rect: Any
    boundary_pattern: Any
    diagnostics: Mapping[str, Any]

    @property
    def all_placements(self) -> tuple[ShelfPlacement, ...]:
        return self.placements + self.pole_placements

    @property
    def pose_indices(self) -> Mapping[str, int]:
        return MappingProxyType(
            {placement.instance_id: placement.pose_idx for placement in self.all_placements}
        )


def fixed_network_edges(
    extra_edges: Iterable[DirectedEdge] = (),
    removed_edges: Iterable[DirectedEdge] = (),
) -> frozenset[DirectedEdge]:
    """Return the current audited shelf SCC with explicit test deltas applied."""

    edges = set(routing_aware_network_edges())
    missing = set(removed_edges) - edges
    if missing:
        raise ShelfConstructionError(
            "REMOVE_UNKNOWN_NETWORK_EDGE", repr(sorted(missing)[:4])
        )
    edges.difference_update(removed_edges)
    edges.update(extra_edges)
    network_router.assert_strongly_connected(edges)
    return frozenset(edges)


def routing_aware_network_edges() -> frozenset[DirectedEdge]:
    """Return the interleaved shelf bus with a local protocol-core bypass.

    Every ordinary shelf chord joins the clockwise outer cycle directly.  The
    generic full-height inner bus is removed.  The protocol core occupies two
    upper body bands; its west/east outputs attach to short southbound buses at
    ``x=2`` and ``x=12``.  Both buses branch from y=63 and rejoin the y=52
    chord, while the single chord through the core starts at the east bus.
    This keeps all core terminals on one component-typed SCC without consuming
    the four vertically distributed 6x4 pole-bay slots.
    """

    outer_only = network_router.ShelfNetworkSpec(chord_levels=())
    edges = set(network_router.shelf_network_edges(outer_only))
    # ``shelf_network_edges`` always emits its generic full-height inner bus.
    # It is not part of this capacity-local topology.
    edges = {
        edge
        for edge in edges
        if not (edge[0][0] == outer_only.inner_bus_x and edge[1][0] == outer_only.inner_bus_x)
    }
    for level in FIXED_CHORD_LEVELS:
        if level in CORE_BLOCKED_CHORD_LEVELS:
            network_router._add_line(edges, (CORE_EAST_BUS_X, level), (69, level))
            continue
        if level in LEFT_CHORD_JOG_LEVELS:
            network_router._add_line(edges, (2, level), (69, level))
            network_router._add_line(edges, (1, level + 1), (2, level + 1))
            network_router._add_line(edges, (2, level + 1), (2, level))
            continue
        network_router._add_line(edges, (1, level), (69, level))
    for column in (CORE_WEST_BUS_X, CORE_EAST_BUS_X):
        network_router._add_line(
            edges,
            (column, CORE_BUS_UPPER_LEVEL),
            (column, CORE_BUS_LOWER_LEVEL),
        )
    network_router.assert_strongly_connected(edges)
    return frozenset(edges)


def _strict_modes(instance: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(template_id), str(mode["id"])): mode
        for template_id, template in instance["facility_templates"].items()
        for mode in template["modes"]
    }


def _candidate_pose_index(bundle: Any) -> dict[tuple[str, str, int, int], tuple[int, Mapping[str, Any]]]:
    pools = bundle.candidate_poses.value["facility_pools"]
    result: dict[tuple[str, str, int, int], tuple[int, Mapping[str, Any]]] = {}
    for candidate_template, pool in pools.items():
        strict_template = strict_contract.CANDIDATE_TEMPLATE_TO_STRICT[candidate_template]
        for pose_idx, pose in enumerate(pool):
            candidate_mode = str(pose["pose_params"]["port_mode"])
            strict_mode = strict_contract.CANDIDATE_MODE_TO_STRICT[candidate_mode]
            anchor = pose["anchor"]
            key = (strict_template, strict_mode, int(anchor["x"]), int(anchor["y"]))
            if key in result:
                raise ShelfConstructionError("DUPLICATE_CANDIDATE_POSE", repr(key))
            result[key] = (pose_idx, pose)
    return result


def _required_by_template(instance: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for required in instance["required_instances"]:
        result[str(required["template"])].append(required)
    for values in result.values():
        values.sort(key=lambda value: str(value["id"]))
    return result


def _boundary_slots(instance: Mapping[str, Any]) -> list[GeometrySlot]:
    ids = [
        str(required["id"])
        for required in instance["required_instances"]
        if required["template"] == "boundary_storage_port"
    ]
    return [
        GeometrySlot("boundary_storage_port", placement.mode, placement.anchor)
        for placement in geometry.place_boundary_instances(ids, FIXED_BOUNDARY_PATTERN)
    ]


def _assign_required_ids(
    instance: Mapping[str, Any], manufacturing_slots: Sequence[GeometrySlot]
) -> list[tuple[Mapping[str, Any], GeometrySlot]]:
    required = _required_by_template(instance)
    has_operations = [bool(slot.operation) for slot in manufacturing_slots]
    if any(has_operations) and not all(has_operations):
        raise ShelfConstructionError(
            "MIXED_GROUP_SLOT_CONTRACT",
            "manufacturing slots must either all name operations or all omit them",
        )
    slots_by_template: dict[str, list[GeometrySlot]] = defaultdict(list)
    for slot in manufacturing_slots:
        if not slot.template.startswith("manufacturing_"):
            raise ShelfConstructionError(
                "NON_MANUFACTURING_SLOT", f"unexpected solver slot template {slot.template!r}"
            )
        slots_by_template[slot.template].append(slot)

    assigned: list[tuple[Mapping[str, Any], GeometrySlot]] = []
    if all(has_operations):
        required_by_group: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
        slots_by_group: dict[tuple[str, str], list[GeometrySlot]] = defaultdict(list)
        for template in ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4"):
            for item in required[template]:
                required_by_group[(template, str(item["operation"]))].append(item)
            for slot in slots_by_template.get(template, []):
                slots_by_group[(template, slot.operation)].append(slot)
        if set(required_by_group) != set(slots_by_group):
            raise ShelfConstructionError(
                "OPERATION_GROUP_SET",
                "solver operation groups do not match the strict required groups",
            )
        for key in sorted(required_by_group):
            group_required = sorted(required_by_group[key], key=lambda item: str(item["id"]))
            group_slots = sorted(
                slots_by_group[key], key=lambda slot: (slot.anchor[1], slot.anchor[0], slot.mode)
            )
            if len(group_required) != len(group_slots):
                raise ShelfConstructionError(
                    "OPERATION_GROUP_COUNT",
                    f"{key}: expected {len(group_required)}, got {len(group_slots)}",
                )
            assigned.extend(zip(group_required, group_slots, strict=True))
    else:
        for template in ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4"):
            template_slots = sorted(
                slots_by_template.get(template, []),
                key=lambda slot: (slot.anchor[1], slot.anchor[0], slot.mode),
            )
            template_required = required[template]
            if len(template_slots) != len(template_required):
                raise ShelfConstructionError(
                    "TEMPLATE_COUNT",
                    f"{template}: expected {len(template_required)}, got {len(template_slots)}",
                )
            assigned.extend(zip(template_required, template_slots, strict=True))

    core_required = required["protocol_core"]
    if len(core_required) != 1:
        raise ShelfConstructionError("CORE_COUNT", "strict instance must contain one core")
    assigned.append(
        (
            core_required[0],
            GeometrySlot("protocol_core", "inputs_north_south", FIXED_CORE_ANCHOR),
        )
    )

    boundary_required = required["boundary_storage_port"]
    boundary_slots = _boundary_slots(instance)
    if len(boundary_required) != len(boundary_slots):
        raise ShelfConstructionError("BOUNDARY_COUNT", "strict instance boundary count changed")
    assigned.extend(zip(boundary_required, boundary_slots, strict=True))
    return assigned


def _materialize_placement(
    required: Mapping[str, Any],
    slot: GeometrySlot,
    *,
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    pose_index: Mapping[tuple[str, str, int, int], tuple[int, Mapping[str, Any]]],
) -> ShelfPlacement:
    strict_mode = modes.get((slot.template, slot.mode))
    if strict_mode is None:
        raise ShelfConstructionError("UNKNOWN_STRICT_MODE", f"{slot.template}/{slot.mode}")
    strict_geometry = geometry.strict_mode_geometry(strict_mode, slot.anchor)
    key = (slot.template, slot.mode, slot.anchor[0], slot.anchor[1])
    candidate = pose_index.get(key)
    if candidate is None:
        raise ShelfConstructionError("POSE_NOT_IN_CURRENT_POOL", repr(key))
    pose_idx, pose = candidate
    candidate_geometry = geometry.candidate_pose_geometry(pose)
    if (
        candidate_geometry.body_cells != strict_geometry.body_cells
        or set(candidate_geometry.input_front_cells) != set(strict_geometry.input_front_cells)
        or set(candidate_geometry.output_front_cells) != set(strict_geometry.output_front_cells)
    ):
        raise ShelfConstructionError("STRICT_CANDIDATE_GEOMETRY_MISMATCH", repr(key))
    return ShelfPlacement(
        instance_id=str(required["id"]),
        template=slot.template,
        operation=str(required["operation"]),
        mode=slot.mode,
        anchor=slot.anchor,
        pose_idx=pose_idx,
        body_cells=strict_geometry.body_cells,
        input_front_cells=strict_geometry.input_front_cells,
        output_front_cells=strict_geometry.output_front_cells,
    )


def _materialize_pole(
    anchor: Anchor,
    index: int,
    *,
    modes: Mapping[tuple[str, str], Mapping[str, Any]],
    pose_index: Mapping[tuple[str, str, int, int], tuple[int, Mapping[str, Any]]],
) -> ShelfPlacement:
    required = {"id": f"research_power_pole_{index:03d}", "operation": "power_supply"}
    return _materialize_placement(
        required,
        GeometrySlot("power_pole", "fixed", anchor),
        modes=modes,
        pose_index=pose_index,
    )


def _free_component(occupied: set[Cell], start: Cell = (1, 1)) -> frozenset[Cell]:
    if start in occupied:
        raise ShelfConstructionError("NETWORK_START_BLOCKED", repr(start))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                0 <= neighbour[0] < GRID_WIDTH
                and 0 <= neighbour[1] < GRID_HEIGHT
                and neighbour not in occupied
                and neighbour not in seen
            ):
                seen.add(neighbour)
                queue.append(neighbour)
    return frozenset(seen)


def _front_needs(instance: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    needs: dict[str, tuple[int, int]] = {}
    for group in instance["operation_groups"]:
        input_count = sum(int(value) for value in group["port_needs"]["inputs"].values())
        output_count = sum(int(value) for value in group["port_needs"]["outputs"].values())
        for instance_id in group["instance_ids"]:
            needs[str(instance_id)] = (input_count, output_count)
    for required in instance["required_instances"]:
        if required["template"] == "boundary_storage_port":
            needs[str(required["id"])] = (0, 1)
        elif required["template"] == "protocol_core":
            needs[str(required["id"])] = (2, 6)
    return needs


def _directional_fronts(
    instance: Mapping[str, Any], placement: ShelfPlacement, *, kind: str
) -> tuple[tuple[Cell, str], ...]:
    modes = _strict_modes(instance)
    mode = modes[(placement.template, placement.mode)]
    result: list[tuple[Cell, str]] = []
    delta = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
    for port in mode["ports"]:
        if port["kind"] != kind:
            continue
        direction = str(port["direction"])
        body_cell = port["body_cell"]
        dx, dy = delta[direction]
        result.append(
            (
                (
                    placement.anchor[0] + int(body_cell["x"]) + dx,
                    placement.anchor[1] + int(body_cell["y"]) + dy,
                ),
                direction,
            )
        )
    return tuple(result)


def _validate_active_front_network(
    instance: Mapping[str, Any],
    placements: Sequence[ShelfPlacement],
    network_cells: set[Cell],
) -> None:
    """Require every selectable active terminal to be on the exact route SCC."""

    needs = _front_needs(instance)
    failures: list[str] = []
    for placement in placements:
        if placement.template == "protocol_core":
            inputs = _directional_fronts(instance, placement, kind="input")
            outputs = _directional_fronts(instance, placement, kind="output")
            south_inputs = sum(cell in network_cells for cell, direction in inputs if direction == "S")
            routed_outputs = sum(cell in network_cells for cell, _direction in outputs)
            if south_inputs < 2 or routed_outputs != 6:
                failures.append(
                    f"{placement.instance_id}: south inputs {south_inputs}/2, outputs {routed_outputs}/6"
                )
            continue
        need_inputs, need_outputs = needs[placement.instance_id]
        routed_inputs = sum(cell in network_cells for cell in placement.input_front_cells)
        routed_outputs = sum(cell in network_cells for cell in placement.output_front_cells)
        if routed_inputs < need_inputs or routed_outputs < need_outputs:
            failures.append(
                f"{placement.instance_id}: in {routed_inputs}/{need_inputs}, out {routed_outputs}/{need_outputs}"
            )
    if failures:
        raise ShelfConstructionError("ACTIVE_FRONT_NETWORK", "; ".join(failures[:8]))


def assert_full_witness_pole_lower_bound(*, required_count: int, pole_count: int) -> None:
    """Apply the independent P>=9 invariant only to a complete strict layout."""

    if required_count == 266 and pole_count < MIN_FULL_WITNESS_POLES:
        raise ShelfConstructionError(
            "POLE_LOWER_BOUND_BUG",
            f"full strict placement returned {pole_count} poles, below hard lower bound {MIN_FULL_WITNESS_POLES}",
        )


def _validate_local_candidate(
    *,
    instance: Mapping[str, Any],
    placements: Sequence[ShelfPlacement],
    poles: Sequence[ShelfPlacement],
    network_edges: frozenset[DirectedEdge],
    protected_rect: Any,
) -> dict[str, Any]:
    expected_ids = {str(required["id"]) for required in instance["required_instances"]}
    actual_ids = [placement.instance_id for placement in placements]
    if len(actual_ids) != 266 or set(actual_ids) != expected_ids or len(set(actual_ids)) != len(actual_ids):
        raise ShelfConstructionError("REQUIRED_ID_SET", "required placement IDs are incomplete or duplicated")
    counts = Counter(placement.template for placement in placements)
    if dict(counts) != EXPECTED_REQUIRED_COUNTS:
        raise ShelfConstructionError("REQUIRED_TEMPLATE_COUNTS", repr(dict(counts)))
    assert_full_witness_pole_lower_bound(
        required_count=len(placements), pole_count=len(poles)
    )

    all_placements = tuple(placements) + tuple(poles)
    owner_by_cell: dict[Cell, str] = {}
    for placement in all_placements:
        if not geometry.cells_in_grid(placement.body_cells):
            raise ShelfConstructionError("BODY_OUT_OF_GRID", placement.instance_id)
        for cell in placement.body_cells:
            previous = owner_by_cell.setdefault(cell, placement.instance_id)
            if previous != placement.instance_id:
                raise ShelfConstructionError(
                    "BODY_OVERLAP", f"{previous!r} and {placement.instance_id!r} at {cell}"
                )
    occupied = set(owner_by_cell)
    network_cells = set(network_router.network_cells(network_edges))
    if occupied & network_cells:
        raise ShelfConstructionError("BODY_BLOCKS_NETWORK", repr(sorted(occupied & network_cells)[:8]))
    if occupied & protected_rect.cells:
        raise ShelfConstructionError("PROTECTED_RECT_BLOCKED", repr(sorted(occupied & protected_rect.cells)[:8]))

    main_component = _free_component(occupied)
    if not network_cells <= main_component:
        raise ShelfConstructionError("NETWORK_NOT_IN_MAIN_FREE_COMPONENT", "network cells are disconnected by bodies")
    _validate_active_front_network(instance, placements, network_cells)

    pole_anchors = tuple(pole.anchor for pole in poles)
    power_failures: list[str] = []
    for placement in placements:
        template = instance["facility_templates"][placement.template]
        if not template["requires_power"]:
            continue
        if not any(
            placement.body_cells & geometry.pole_coverage_cells(anchor)
            for anchor in pole_anchors
        ):
            power_failures.append(placement.instance_id)
    if power_failures:
        raise ShelfConstructionError("POWER_UNCOVERED", repr(power_failures[:8]))

    return {
        "required_count": len(placements),
        "pole_count": len(poles),
        "required_template_counts": dict(sorted(counts.items())),
        "occupied_body_cells": len(occupied),
        "network_cells": len(network_cells),
        "main_free_component_cells": len(main_component),
        "protected_rect": [
            protected_rect.x,
            protected_rect.y,
            protected_rect.width,
            protected_rect.height,
        ],
        "front_failures": 0,
        "power_failures": 0,
        "pole_lower_bound_sentinel_satisfied": len(poles) >= MIN_FULL_WITNESS_POLES,
    }


def assemble_shelf_candidate(
    manufacturing_slots: Sequence[GeometrySlot],
    *,
    pole_anchors: Sequence[Anchor],
    protected_rect: Any,
    pole_bay_anchors: Sequence[Anchor] | None = None,
    network_edges: Iterable[DirectedEdge] | None = None,
    extra_network_edges: Iterable[DirectedEdge] = (),
    removed_network_edges: Iterable[DirectedEdge] = (),
    project_root: Path = strict_contract.PROJECT_ROOT,
) -> ShelfCandidate:
    """Assemble solver output and enforce all local geometry/front/power gates."""

    bundle = strict_contract.load_input_bundle(project_root)
    strict_contract.reconcile_inputs(bundle)
    instance = bundle.strict_instance.value
    modes = _strict_modes(instance)
    pose_index = _candidate_pose_index(bundle)
    assigned = _assign_required_ids(instance, manufacturing_slots)
    placements = tuple(
        _materialize_placement(required, slot, modes=modes, pose_index=pose_index)
        for required, slot in assigned
    )
    sorted_poles = tuple(sorted(set(pole_anchors), key=lambda anchor: (anchor[1], anchor[0])))
    if len(sorted_poles) != len(pole_anchors):
        raise ShelfConstructionError("DUPLICATE_POLE_ANCHOR", "pole anchors must be unique")
    poles = tuple(
        _materialize_pole(anchor, index, modes=modes, pose_index=pose_index)
        for index, anchor in enumerate(sorted_poles, 1)
    )
    if network_edges is None:
        edges = fixed_network_edges(extra_network_edges, removed_network_edges)
    else:
        if tuple(extra_network_edges) or tuple(removed_network_edges):
            raise ShelfConstructionError(
                "AMBIGUOUS_NETWORK_CONTRACT",
                "exact network_edges cannot be combined with edge deltas",
            )
        edges = frozenset(network_edges)
        network_router.assert_strongly_connected(edges)
    diagnostics = _validate_local_candidate(
        instance=instance,
        placements=placements,
        poles=poles,
        network_edges=edges,
        protected_rect=protected_rect,
    )
    bays = tuple(
        sorted(
            set(pole_bay_anchors if pole_bay_anchors is not None else pole_anchors),
            key=lambda anchor: (anchor[1], anchor[0]),
        )
    )
    if not set(sorted_poles) <= set(bays):
        raise ShelfConstructionError("POLE_NOT_IN_BAY_SET", "a selected pole is absent from pole_bay_anchors")
    return ShelfCandidate(
        placements=placements,
        pole_placements=poles,
        pole_bay_anchors=bays,
        network_edges=edges,
        reserved_network_cells=network_router.network_cells(edges),
        protected_rect=protected_rect,
        boundary_pattern=FIXED_BOUNDARY_PATTERN,
        diagnostics=MappingProxyType(diagnostics),
    )


def _result_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ShelfConstructionError("RESULT_SCHEMA", f"{label} must be an object")
    return value


def _result_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ShelfConstructionError("RESULT_SCHEMA", f"{label} must be an array")
    return value


def _result_integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ShelfConstructionError("RESULT_SCHEMA", f"{label} must be an integer")
    return value


def _result_coordinate(value: Any, label: str) -> Anchor:
    raw = _result_sequence(value, label)
    if len(raw) != 2:
        raise ShelfConstructionError("RESULT_SCHEMA", f"{label} must have length two")
    return (_result_integer(raw[0], f"{label}[0]"), _result_integer(raw[1], f"{label}[1]"))


def _result_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ShelfConstructionError(
            "RESULT_SCHEMA",
            f"{label} keys differ; missing={sorted(expected - set(value))}, extra={sorted(set(value) - expected)}",
        )


def _result_nonnegative(value: Any, label: str) -> int:
    parsed = _result_integer(value, label)
    if parsed < 0:
        raise ShelfConstructionError("RESULT_SCHEMA", f"{label} must be nonnegative")
    return parsed


def _canonical_cgroup_path(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", f"{label} must be a string")
    if value == "/":
        return value
    if not value.startswith("/") or value.endswith("/") or "//" in value:
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", f"{label} is not canonical")
    segments = value.split("/")[1:]
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", f"{label} is not canonical")
    return value


def _ancestor_cgroup_paths(leaf_path: str) -> tuple[str, ...]:
    segments = leaf_path.split("/")[1:]
    result: list[str] = []
    for length in range(len(segments) - 1, 0, -1):
        result.append("/" + "/".join(segments[:length]))
    result.append("/")
    return tuple(result)


def _validate_limit_record(value: Any, label: str) -> None:
    record = _result_object(value, label)
    _result_exact_keys(record, {"path", "memory.high", "memory.max", "memory.swap.max"}, label)
    _canonical_cgroup_path(record["path"], f"{label}.path")
    for key in ("memory.high", "memory.max", "memory.swap.max"):
        if record[key] != "max":
            _result_nonnegative(record[key], f"{label}.{key}")


def _validate_contract_snapshot(value: Any, label: str) -> Mapping[str, Any]:
    record = _result_object(value, label)
    _result_exact_keys(record, {"leaf", "ancestors", "effective"}, label)
    _validate_limit_record(record["leaf"], f"{label}.leaf")
    ancestors = _result_sequence(record["ancestors"], f"{label}.ancestors")
    for index, ancestor in enumerate(ancestors):
        _validate_limit_record(ancestor, f"{label}.ancestors[{index}]")
    effective = _result_object(record["effective"], f"{label}.effective")
    expected_limits = {
        "memory.high": cgroup_telemetry.MEMORY_HIGH_BYTES,
        "memory.max": cgroup_telemetry.MEMORY_MAX_BYTES,
        "memory.swap.max": cgroup_telemetry.MEMORY_SWAP_MAX_BYTES,
    }
    if dict(effective) != expected_limits:
        raise ShelfConstructionError("RESULT_CGROUP_CONTRACT", f"{label}.effective differs")
    leaf = _result_object(record["leaf"], f"{label}.leaf")
    if any(leaf[key] != expected for key, expected in expected_limits.items()):
        raise ShelfConstructionError("RESULT_CGROUP_CONTRACT", f"{label}.leaf differs")
    recomputed_effective = dict(expected_limits)
    for index, ancestor_raw in enumerate(ancestors):
        ancestor = _result_object(ancestor_raw, f"{label}.ancestors[{index}]")
        for key, expected in expected_limits.items():
            observed = ancestor[key]
            if observed == "max":
                continue
            if observed < expected:
                raise ShelfConstructionError(
                    "RESULT_CGROUP_CONTRACT",
                    f"{label}.ancestors[{index}].{key} is tighter than the worker contract",
                )
            recomputed_effective[key] = min(recomputed_effective[key], observed)
    if dict(effective) != recomputed_effective:
        raise ShelfConstructionError("RESULT_CGROUP_CONTRACT", f"{label}.effective is not recomputed")
    return record


def _validate_counter_snapshot(value: Any, label: str) -> Mapping[str, Any]:
    record = _result_object(value, label)
    expected = {
        "memory.current",
        "memory.peak",
        "memory.swap.current",
        "memory.swap.peak",
        "pids.current",
        "memory.events",
    }
    _result_exact_keys(record, expected, label)
    for key in expected - {"memory.events"}:
        _result_nonnegative(record[key], f"{label}.{key}")
    events = _result_object(record["memory.events"], f"{label}.memory.events")
    if not set(cgroup_telemetry.REQUIRED_MEMORY_EVENT_KEYS) <= set(events):
        raise ShelfConstructionError("RESULT_SCHEMA", f"{label}.memory.events lacks required keys")
    for key, value_raw in events.items():
        if not isinstance(key, str):
            raise ShelfConstructionError("RESULT_SCHEMA", f"{label}.memory.events key is invalid")
        _result_nonnegative(value_raw, f"{label}.memory.events.{key}")
    return record


def _validate_cgroup_telemetry(value: Any) -> None:
    telemetry = _result_object(value, "cgroup_telemetry")
    expected = {
        "schema_version",
        "expected_unit_name",
        "cgroup_path",
        "contract_start",
        "contract_end",
        "counters_start",
        "counters_end",
        "memory.events.delta",
        "oom_attribution",
    }
    _result_exact_keys(telemetry, expected, "cgroup_telemetry")
    if telemetry["schema_version"] != cgroup_telemetry.TELEMETRY_SCHEMA_VERSION:
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", repr(telemetry["schema_version"]))
    unit = telemetry["expected_unit_name"]
    path = telemetry["cgroup_path"]
    if not isinstance(unit, str) or cgroup_telemetry._SAFE_UNIT_RE.fullmatch(unit) is None:
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", "expected_unit_name is invalid")
    path = _canonical_cgroup_path(path, "cgroup_telemetry.cgroup_path")
    if not path.endswith("/" + unit):
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", "cgroup_path does not end in expected unit")
    contract_start = _validate_contract_snapshot(
        telemetry["contract_start"], "cgroup_telemetry.contract_start"
    )
    contract_end = _validate_contract_snapshot(
        telemetry["contract_end"], "cgroup_telemetry.contract_end"
    )
    if dict(contract_start) != dict(contract_end):
        raise ShelfConstructionError("RESULT_CGROUP_CONTRACT", "start/end contract snapshots differ")
    for label, contract in (("start", contract_start), ("end", contract_end)):
        leaf = _result_object(contract["leaf"], f"cgroup_telemetry.contract_{label}.leaf")
        if leaf["path"] != path:
            raise ShelfConstructionError(
                "RESULT_CGROUP_CONTRACT", f"contract_{label}.leaf path differs from cgroup_path"
            )
        ancestor_records = _result_sequence(
            contract["ancestors"], f"cgroup_telemetry.contract_{label}.ancestors"
        )
        observed_paths = tuple(
            _result_object(record, f"cgroup_telemetry.contract_{label}.ancestor")["path"]
            for record in ancestor_records
        )
        expected_paths = _ancestor_cgroup_paths(path)
        if observed_paths != expected_paths:
            raise ShelfConstructionError(
                "RESULT_CGROUP_CONTRACT",
                f"contract_{label} ancestor chain differs; expected={expected_paths!r}, observed={observed_paths!r}",
            )
    counters_start = _validate_counter_snapshot(
        telemetry["counters_start"], "cgroup_telemetry.counters_start"
    )
    counters_end = _validate_counter_snapshot(
        telemetry["counters_end"], "cgroup_telemetry.counters_end"
    )
    for key in ("memory.peak", "memory.swap.peak"):
        if counters_end[key] < counters_start[key]:
            raise ShelfConstructionError("RESULT_CGROUP_COUNTER", f"{key} decreased")
    delta = _result_object(telemetry["memory.events.delta"], "cgroup_telemetry.memory.events.delta")
    if not set(cgroup_telemetry.REQUIRED_MEMORY_EVENT_KEYS) <= set(delta):
        raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", "memory.events.delta lacks required keys")
    for key, value_raw in delta.items():
        if not isinstance(key, str):
            raise ShelfConstructionError("RESULT_CGROUP_SCHEMA", "memory.events.delta key is invalid")
        _result_nonnegative(value_raw, f"cgroup_telemetry.memory.events.delta.{key}")
    try:
        recomputed_delta = cgroup_telemetry.memory_events_delta(
            _result_object(counters_start["memory.events"], "counters_start.memory.events"),
            _result_object(counters_end["memory.events"], "counters_end.memory.events"),
        )
    except cgroup_telemetry.SupervisorError as exc:
        raise ShelfConstructionError("RESULT_CGROUP_COUNTER", str(exc)) from exc
    if dict(delta) != recomputed_delta:
        raise ShelfConstructionError("RESULT_CGROUP_COUNTER", "memory.events.delta differs from end-start")
    if delta.get("oom_kill", 0) > 0 or delta.get("oom_group_kill", 0) > 0:
        recomputed_oom = cgroup_telemetry.CGROUP_OOM_KILL
    elif delta.get("oom", 0) > 0:
        recomputed_oom = cgroup_telemetry.CGROUP_OOM_EVENT
    else:
        recomputed_oom = cgroup_telemetry.NO_CGROUP_OOM
    if telemetry["oom_attribution"] != recomputed_oom:
        raise ShelfConstructionError("RESULT_CGROUP_COUNTER", "oom_attribution differs from event delta")
    if recomputed_oom != cgroup_telemetry.NO_CGROUP_OOM:
        raise ShelfConstructionError("RESULT_CGROUP_OOM", repr(telemetry["oom_attribution"]))


def _load_shelf_result(
    result_path: Path, *, project_root: Path
) -> tuple[tuple[GeometrySlot, ...], tuple[Anchor, ...], tuple[Anchor, ...], frozenset[DirectedEdge]]:
    """Load one explicit x-exclusive worker result and reject contract drift."""

    path = Path(result_path)
    if path.is_symlink() or not path.is_file():
        raise ShelfConstructionError("RESULT_PATH", f"result must be a regular non-symlink file: {path}")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ShelfConstructionError("RESULT_READ", str(exc)) from exc
    try:
        record = _result_object(
            strict_contract.strict_json_loads(payload, label="shelf_power_result"),
            "shelf_power_result",
        )
    except strict_contract.InputContractError as exc:
        raise ShelfConstructionError("RESULT_JSON", str(exc)) from exc
    expected_keys = {
        "schema_version",
        "status",
        "input_sha256",
        "manufacturing_slots",
        "pole_anchors",
        "pole_bay_anchors",
        "protected_rect",
        "network_edges",
        "stats",
        "route_validation",
        "cgroup_telemetry",
        "failure",
    }
    if set(record) != expected_keys:
        raise ShelfConstructionError(
            "RESULT_SCHEMA",
            f"top-level keys differ; missing={sorted(expected_keys - set(record))}, "
            f"extra={sorted(set(record) - expected_keys)}",
        )
    if record["schema_version"] != SHELF_RESULT_SCHEMA_VERSION:
        raise ShelfConstructionError("RESULT_SCHEMA_VERSION", repr(record["schema_version"]))
    if record["status"] not in {"FEASIBLE", "OPTIMAL"} or record["failure"] is not None:
        raise ShelfConstructionError(
            "RESULT_NOT_ACCEPTED", f"status={record['status']!r}, failure={record['failure']!r}"
        )

    bundle = strict_contract.load_input_bundle(project_root)
    strict_contract.reconcile_inputs(bundle)
    hashes = _result_object(record["input_sha256"], "input_sha256")
    if dict(hashes) != bundle.hashes:
        raise ShelfConstructionError("RESULT_INPUT_DRIFT", "worker input hashes differ from current pinned inputs")
    _result_object(record["stats"], "stats")
    validation = _result_object(record["route_validation"], "route_validation")
    if validation.get("status") != "WITNESS_BUILT":
        raise ShelfConstructionError("RESULT_ROUTE_UNVALIDATED", repr(validation.get("status")))
    _validate_cgroup_telemetry(record["cgroup_telemetry"])

    raw_rect = _result_sequence(record["protected_rect"], "protected_rect")
    rect_tuple = tuple(_result_integer(value, f"protected_rect[{index}]") for index, value in enumerate(raw_rect))
    expected_rect = (
        SHELF_PROTECTED_RECT.x,
        SHELF_PROTECTED_RECT.y,
        SHELF_PROTECTED_RECT.width,
        SHELF_PROTECTED_RECT.height,
    )
    if rect_tuple != expected_rect:
        raise ShelfConstructionError("RESULT_PROTECTED_RECT", repr(rect_tuple))

    slots: list[GeometrySlot] = []
    for index, raw_slot in enumerate(_result_sequence(record["manufacturing_slots"], "manufacturing_slots")):
        slot = _result_object(raw_slot, f"manufacturing_slots[{index}]")
        if set(slot) != {"template", "mode", "anchor", "operation"}:
            raise ShelfConstructionError("RESULT_SCHEMA", f"manufacturing_slots[{index}] keys differ")
        if not all(isinstance(slot[key], str) for key in ("template", "mode", "operation")):
            raise ShelfConstructionError("RESULT_SCHEMA", f"manufacturing_slots[{index}] strings are invalid")
        slots.append(
            GeometrySlot(
                str(slot["template"]),
                str(slot["mode"]),
                _result_coordinate(slot["anchor"], f"manufacturing_slots[{index}].anchor"),
                str(slot["operation"]),
            )
        )
    if len(slots) != 219:
        raise ShelfConstructionError("RESULT_SLOT_COUNT", f"expected 219, observed {len(slots)}")

    pole_anchors = tuple(
        _result_coordinate(value, f"pole_anchors[{index}]")
        for index, value in enumerate(_result_sequence(record["pole_anchors"], "pole_anchors"))
    )
    pole_bays = tuple(
        _result_coordinate(value, f"pole_bay_anchors[{index}]")
        for index, value in enumerate(_result_sequence(record["pole_bay_anchors"], "pole_bay_anchors"))
    )
    if len(pole_anchors) != len(set(pole_anchors)) or len(pole_bays) != len(set(pole_bays)):
        raise ShelfConstructionError("RESULT_DUPLICATE_ANCHOR", "pole anchors and bays must be unique")

    raw_edges = _result_sequence(record["network_edges"], "network_edges")
    edges = frozenset(
        (
            _result_coordinate(_result_sequence(value, f"network_edges[{index}]")[0], f"network_edges[{index}][0]"),
            _result_coordinate(_result_sequence(value, f"network_edges[{index}]")[1], f"network_edges[{index}][1]"),
        )
        for index, value in enumerate(raw_edges)
        if len(_result_sequence(value, f"network_edges[{index}]")) == 2
    )
    if len(edges) != len(raw_edges):
        raise ShelfConstructionError("RESULT_NETWORK_EDGE", "network edges are malformed or duplicated")
    if edges != routing_aware_network_edges():
        raise ShelfConstructionError("RESULT_NETWORK_DRIFT", "worker topology differs from the accepted mini shelf")
    return tuple(slots), pole_anchors, pole_bays, edges


def construct_shelf_candidate(
    *, result_path: Path, project_root: Path = strict_contract.PROJECT_ROOT
) -> ShelfCandidate:
    """Replay one explicit worker result; this function never invokes CP-SAT."""

    slots, pole_anchors, pole_bays, edges = _load_shelf_result(
        result_path, project_root=project_root
    )
    return assemble_shelf_candidate(
        slots,
        pole_anchors=pole_anchors,
        pole_bay_anchors=pole_bays,
        protected_rect=SHELF_PROTECTED_RECT,
        network_edges=edges,
        project_root=project_root,
    )

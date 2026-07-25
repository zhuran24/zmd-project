"""Deterministic component-typed routing on a shelf corridor scaffold.

The routing-aware shelf layout reserves a directed outer cycle, a southbound
inner bus, and eastbound shelf chords.  Those edges form a strongly connected
network.  Consequently every active terminal can use the same commodity-labelled
network without a flow-capacity assumption: each output reaches a same-commodity
input and every input is reached by a same-commodity output.

This is a research constructor, not a replacement for the production router.
It emits the strict component vocabulary directly and fails closed whenever a
cell would require a component outside the 48 legal non-empty variants.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, cast


Direction = Literal["N", "E", "S", "W"]
Cell: TypeAlias = tuple[int, int]
DirectedEdge: TypeAlias = tuple[Cell, Cell]
LaneNode: TypeAlias = tuple[Cell, int]

_DIRECTIONS: tuple[Direction, ...] = ("N", "E", "S", "W")
_DIRECTION_RANK = {direction: index for index, direction in enumerate(_DIRECTIONS)}
_DELTA: dict[Direction, Cell] = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
_OPPOSITE: dict[Direction, Direction] = {"N": "S", "E": "W", "S": "N", "W": "E"}


class NetworkRoutingError(ValueError):
    """Stable fail-closed error raised by the deterministic router."""

    def __init__(self, code: str, message: str, *, cell: Cell | None = None) -> None:
        self.code = code
        self.cell = cell
        suffix = f" cell={cell}" if cell is not None else ""
        super().__init__(f"{code}: {message}{suffix}")


@dataclass(frozen=True)
class Terminal:
    instance_id: str
    port_id: str
    kind: Literal["input", "output"]
    commodity: str
    access: Cell
    outward: Direction


@dataclass(frozen=True)
class ShelfNetworkSpec:
    """Geometry needed to construct the universal directed shelf network."""

    width: int = 70
    height: int = 70
    left_cycle_x: int = 1
    inner_bus_x: int = 2
    right_cycle_x: int = 69
    bottom_cycle_y: int = 1
    top_cycle_y: int = 69
    chord_levels: tuple[int, ...] = ()
    core_anchor: Cell | None = None
    core_size: int = 9


def _direction_between(source: Cell, target: Cell) -> Direction:
    delta = (target[0] - source[0], target[1] - source[1])
    for direction, expected in _DELTA.items():
        if delta == expected:
            return direction
    raise NetworkRoutingError("NON_ADJACENT_EDGE", f"edge {source!r}->{target!r} is not unit orthogonal")


def _add_line(edges: set[DirectedEdge], start: Cell, end: Cell) -> None:
    """Add the inclusive-endpoint directed orthogonal line ``start -> end``."""

    dx = (end[0] > start[0]) - (end[0] < start[0])
    dy = (end[1] > start[1]) - (end[1] < start[1])
    if (dx == 0) == (dy == 0):
        raise NetworkRoutingError("INVALID_LINE", f"line must be nonempty and orthogonal: {start!r}->{end!r}")
    current = start
    while current != end:
        nxt = (current[0] + dx, current[1] + dy)
        edges.add((current, nxt))
        current = nxt


def shelf_network_edges(spec: ShelfNetworkSpec) -> frozenset[DirectedEdge]:
    """Build the outer cycle, inner bus, shelf chords, and optional core bypass.

    The core may block one or more chord levels.  A southbound bus immediately
    east of the core branches from the first free chord above it, feeds the
    right-hand chord fragments, and rejoins the first free chord below it.
    """

    if (spec.width, spec.height) != (70, 70):
        raise NetworkRoutingError("GRID_CONTRACT", "the strict witness grid must be 70x70")
    levels = tuple(sorted(set(spec.chord_levels)))
    if any(not (spec.bottom_cycle_y < y < spec.top_cycle_y) for y in levels):
        raise NetworkRoutingError("CHORD_LEVEL", "interior chord levels must exclude the outer cycle")

    edges: set[DirectedEdge] = set()
    # Clockwise outer cycle: bottom east, right north, top west, left south.
    _add_line(edges, (spec.left_cycle_x, spec.bottom_cycle_y), (spec.right_cycle_x, spec.bottom_cycle_y))
    _add_line(edges, (spec.right_cycle_x, spec.bottom_cycle_y), (spec.right_cycle_x, spec.top_cycle_y))
    _add_line(edges, (spec.right_cycle_x, spec.top_cycle_y), (spec.left_cycle_x, spec.top_cycle_y))
    _add_line(edges, (spec.left_cycle_x, spec.top_cycle_y), (spec.left_cycle_x, spec.bottom_cycle_y))
    # A directed chord of the outer cycle; all shelf chords branch from it.
    _add_line(edges, (spec.inner_bus_x, spec.top_cycle_y), (spec.inner_bus_x, spec.bottom_cycle_y))

    blocked_levels: tuple[int, ...] = ()
    bypass_x: int | None = None
    lower_level: int | None = None
    upper_level: int | None = None
    if spec.core_anchor is not None:
        core_x, core_y = spec.core_anchor
        core_top = core_y + spec.core_size - 1
        blocked_levels = tuple(y for y in levels if core_y <= y <= core_top)
        if blocked_levels:
            below = [y for y in levels if y < core_y]
            above = [y for y in levels if y > core_top]
            if not below or not above:
                raise NetworkRoutingError(
                    "CORE_BYPASS_UNANCHORED",
                    "a blocked chord needs a free chord immediately above and below the core",
                )
            lower_level = max(below)
            upper_level = min(above)
            bypass_x = core_x + spec.core_size
            if not (spec.inner_bus_x < bypass_x < spec.right_cycle_x):
                raise NetworkRoutingError("CORE_BYPASS_COLUMN", "core east ring is not an interior routing column")

    for y in levels:
        start_x = bypass_x if y in blocked_levels else spec.inner_bus_x
        assert start_x is not None
        _add_line(edges, (start_x, y), (spec.right_cycle_x, y))

    if bypass_x is not None:
        assert lower_level is not None and upper_level is not None
        _add_line(edges, (bypass_x, upper_level), (bypass_x, lower_level))

    return frozenset(edges)


def network_cells(edges: Iterable[DirectedEdge]) -> frozenset[Cell]:
    cells: set[Cell] = set()
    for source, target in edges:
        _direction_between(source, target)
        cells.add(source)
        cells.add(target)
    return frozenset(cells)


def assert_strongly_connected(edges: Iterable[DirectedEdge]) -> None:
    """Require every network cell to reach every other network cell."""

    edge_set = set(edges)
    cells = network_cells(edge_set)
    if not cells:
        raise NetworkRoutingError("EMPTY_NETWORK", "routing network has no cells")
    forward: dict[Cell, set[Cell]] = defaultdict(set)
    reverse: dict[Cell, set[Cell]] = defaultdict(set)
    for source, target in edge_set:
        forward[source].add(target)
        reverse[target].add(source)

    def visit(graph: Mapping[Cell, set[Cell]]) -> set[Cell]:
        start = min(cells)
        seen = {start}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            for nxt in graph.get(cell, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    if visit(forward) != set(cells) or visit(reverse) != set(cells):
        raise NetworkRoutingError("NETWORK_NOT_STRONGLY_CONNECTED", "directed scaffold is not one SCC")


def terminals_from_witness(
    instance: Mapping[str, Any],
    placements: Sequence[Mapping[str, Any]],
) -> tuple[Terminal, ...]:
    """Reconstruct active strict terminals from complete placement bindings."""

    modes = {
        (str(template_id), str(mode["id"])): mode
        for template_id, template in cast(Mapping[str, Any], instance["facility_templates"]).items()
        for mode in cast(Sequence[Mapping[str, Any]], template["modes"])
    }
    terminals: list[Terminal] = []
    for placement in placements:
        instance_id = str(placement["instance_id"])
        key = (str(placement["template"]), str(placement["mode"]))
        mode = modes.get(key)
        if mode is None:
            raise NetworkRoutingError("UNKNOWN_PLACEMENT_MODE", f"unknown strict mode {key!r}")
        anchor = cast(Mapping[str, Any], placement["anchor"])
        anchor_x, anchor_y = int(anchor["x"]), int(anchor["y"])
        bindings = cast(Mapping[str, Any], placement["port_bindings"])
        expected_ids = {str(port["id"]) for port in cast(Sequence[Mapping[str, Any]], mode["ports"])}
        if set(bindings) != expected_ids:
            raise NetworkRoutingError("INCOMPLETE_PORT_MAP", f"{instance_id!r} has an incomplete port map")
        for port in cast(Sequence[Mapping[str, Any]], mode["ports"]):
            port_id = str(port["id"])
            commodity = bindings[port_id]
            if commodity is None:
                continue
            outward = str(port["direction"])
            if outward not in _DIRECTIONS:
                raise NetworkRoutingError("INVALID_PORT_DIRECTION", f"invalid direction {outward!r}")
            body_cell = cast(Mapping[str, Any], port["body_cell"])
            dx, dy = _DELTA[cast(Direction, outward)]
            access = (anchor_x + int(body_cell["x"]) + dx, anchor_y + int(body_cell["y"]) + dy)
            kind = str(port["kind"])
            if kind not in {"input", "output"}:
                raise NetworkRoutingError("INVALID_PORT_KIND", f"invalid port kind {kind!r}")
            terminals.append(
                Terminal(
                    instance_id=instance_id,
                    port_id=port_id,
                    kind=cast(Literal["input", "output"], kind),
                    commodity=str(commodity),
                    access=access,
                    outward=cast(Direction, outward),
                )
            )
    return tuple(terminals)


def _sorted_directions(values: Iterable[Direction]) -> list[Direction]:
    return sorted(set(values), key=_DIRECTION_RANK.__getitem__)


def _component_for_cell(
    cell: Cell,
    inputs: set[Direction],
    outputs: set[Direction],
    commodities: Sequence[str],
) -> dict[str, Any]:
    if inputs & outputs:
        raise NetworkRoutingError("DIRECTION_REUSED", "a side cannot be both input and output", cell=cell)
    commodity_values = sorted(set(commodities))
    if len(inputs) == 1 and len(outputs) == 1:
        input_direction = next(iter(inputs))
        output_direction = next(iter(outputs))
        kind = "straight" if output_direction == _OPPOSITE[input_direction] else "turn"
    elif len(inputs) == 1 and len(outputs) in {2, 3}:
        if next(iter(inputs)) in outputs:
            raise NetworkRoutingError("INVALID_SPLITTER", "splitter input is also an output", cell=cell)
        kind = "splitter"
    elif len(outputs) == 1 and len(inputs) in {2, 3}:
        if next(iter(outputs)) in inputs:
            raise NetworkRoutingError("INVALID_MERGER", "merger output is also an input", cell=cell)
        kind = "merger"
    elif len(inputs) == 2 and len(outputs) == 2:
        if {_OPPOSITE[direction] for direction in inputs} != outputs:
            raise NetworkRoutingError(
                "INVALID_CROSS",
                "cross channels must both continue straight through",
                cell=cell,
            )
        ordered_inputs = sorted(
            inputs,
            key=lambda direction: (0 if direction in {"E", "W"} else 1, _DIRECTION_RANK[direction]),
        )
        return {
            "cell": {"x": cell[0], "y": cell[1]},
            "kind": "cross",
            "channels": [
                {
                    "inputs": [direction],
                    "outputs": [_OPPOSITE[direction]],
                    "commodities": commodity_values,
                }
                for direction in ordered_inputs
            ],
        }
    else:
        raise NetworkRoutingError(
            "UNREPRESENTABLE_COMPONENT",
            f"strict component cannot represent indegree={len(inputs)} outdegree={len(outputs)}",
            cell=cell,
        )
    return {
        "cell": {"x": cell[0], "y": cell[1]},
        "kind": kind,
        "inputs": _sorted_directions(inputs),
        "outputs": _sorted_directions(outputs),
        "commodities": commodity_values,
    }


@dataclass(frozen=True)
class _RouteLane:
    node: LaneNode
    inputs: frozenset[Direction]
    outputs: frozenset[Direction]
    commodities: frozenset[str]


def _component_lanes(components: Sequence[Mapping[str, Any]]) -> dict[Cell, tuple[_RouteLane, ...]]:
    """Expand strict components into transfer-isolated directed lanes."""

    lanes_by_cell: dict[Cell, tuple[_RouteLane, ...]] = {}
    for component in components:
        raw_cell = cast(Mapping[str, Any], component["cell"])
        cell = (int(raw_cell["x"]), int(raw_cell["y"]))
        if cell in lanes_by_cell:
            raise NetworkRoutingError("DUPLICATE_ROUTE_CELL", "more than one component occupies a route cell", cell=cell)

        kind = str(component["kind"])
        raw_lanes: Sequence[Mapping[str, Any]]
        if kind == "cross":
            raw_lanes = cast(Sequence[Mapping[str, Any]], component["channels"])
            if len(raw_lanes) != 2:
                raise NetworkRoutingError("INVALID_CROSS", "a cross must contain exactly two channels", cell=cell)
        else:
            raw_lanes = (component,)

        lanes: list[_RouteLane] = []
        used_directions: set[Direction] = set()
        for lane_index, raw_lane in enumerate(raw_lanes):
            inputs = frozenset(cast(Sequence[Direction], raw_lane["inputs"]))
            outputs = frozenset(cast(Sequence[Direction], raw_lane["outputs"]))
            commodities = frozenset(str(value) for value in cast(Sequence[str], raw_lane["commodities"]))
            if not inputs or not outputs or not commodities:
                raise NetworkRoutingError(
                    "INVALID_ROUTE_LANE",
                    "every route lane needs nonempty inputs, outputs, and commodities",
                    cell=cell,
                )
            if not (inputs | outputs) <= set(_DIRECTIONS):
                raise NetworkRoutingError("INVALID_ROUTE_LANE", "a route lane uses an invalid direction", cell=cell)
            if inputs & outputs:
                raise NetworkRoutingError("DIRECTION_REUSED", "a lane side cannot be both input and output", cell=cell)
            if used_directions & (inputs | outputs):
                raise NetworkRoutingError(
                    "CROSS_CHANNEL_TRANSFER",
                    "cross channels must not share an interface direction",
                    cell=cell,
                )
            used_directions.update(inputs | outputs)
            lanes.append(
                _RouteLane(
                    node=(cell, lane_index),
                    inputs=inputs,
                    outputs=outputs,
                    commodities=commodities,
                )
            )

        if kind == "cross":
            axes = []
            for lane in lanes:
                if len(lane.inputs) != 1 or len(lane.outputs) != 1:
                    raise NetworkRoutingError(
                        "INVALID_CROSS", "each cross channel must have one input and one output", cell=cell
                    )
                input_direction = next(iter(lane.inputs))
                output_direction = next(iter(lane.outputs))
                if output_direction != _OPPOSITE[input_direction]:
                    raise NetworkRoutingError("INVALID_CROSS", "cross channels must continue straight", cell=cell)
                axes.append("horizontal" if input_direction in {"E", "W"} else "vertical")
            if len(set(axes)) != 2:
                raise NetworkRoutingError("INVALID_CROSS", "cross channels must be perpendicular", cell=cell)

        lanes_by_cell[cell] = tuple(lanes)
    return lanes_by_cell


def assert_terminal_route_reachability(
    components: Sequence[Mapping[str, Any]],
    terminals: Sequence[Terminal],
    commodities: Sequence[str],
) -> None:
    """Validate strict lane-level source/sink coverage for every commodity.

    A non-cross component transfers from any of its inputs to any of its
    outputs.  A cross contributes two distinct nodes, so its perpendicular
    channels never transfer into one another.  The required pooled semantics
    are bidirectional coverage: every active sink is reachable from at least
    one same-commodity source, and every active source reaches at least one
    same-commodity sink.  Separate same-commodity islands remain legal when
    each island contains both roles.
    """

    commodity_set = set(commodities)
    lanes_by_cell = _component_lanes(components)
    lanes = {lane.node: lane for cell_lanes in lanes_by_cell.values() for lane in cell_lanes}
    adjacency: dict[LaneNode, set[LaneNode]] = defaultdict(set)
    for lane in lanes.values():
        cell = lane.node[0]
        for direction in lane.outputs:
            dx, dy = _DELTA[direction]
            neighbor = (cell[0] + dx, cell[1] + dy)
            for target in lanes_by_cell.get(neighbor, ()):
                if _OPPOSITE[direction] in target.inputs:
                    adjacency[lane.node].add(target.node)

    terminal_nodes: dict[Terminal, LaneNode] = {}
    for terminal in terminals:
        if terminal.commodity not in commodity_set:
            raise NetworkRoutingError("UNKNOWN_TERMINAL_COMMODITY", terminal.commodity, cell=terminal.access)
        required = _OPPOSITE[terminal.outward]
        matches = [
            lane.node
            for lane in lanes_by_cell.get(terminal.access, ())
            if terminal.commodity in lane.commodities
            and required in (lane.inputs if terminal.kind == "output" else lane.outputs)
        ]
        if len(matches) != 1:
            raise NetworkRoutingError(
                "TERMINAL_LANE_MISMATCH",
                f"{terminal.instance_id}/{terminal.port_id} attaches to {len(matches)} compatible lanes",
                cell=terminal.access,
            )
        terminal_nodes[terminal] = matches[0]

    def reachable(starts: Iterable[LaneNode], commodity: str) -> set[LaneNode]:
        seen = {node for node in starts if commodity in lanes[node].commodities}
        queue = deque(seen)
        while queue:
            node = queue.popleft()
            for nxt in adjacency.get(node, set()):
                if nxt not in seen and commodity in lanes[nxt].commodities:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    for commodity in sorted(commodity_set):
        sources = sorted(
            (terminal for terminal in terminals if terminal.kind == "output" and terminal.commodity == commodity),
            key=lambda terminal: (terminal.instance_id, terminal.port_id, terminal.access),
        )
        sinks = sorted(
            (terminal for terminal in terminals if terminal.kind == "input" and terminal.commodity == commodity),
            key=lambda terminal: (terminal.instance_id, terminal.port_id, terminal.access),
        )
        # Component-shape probes intentionally compile partial terminal sets.
        # Exact witness construction supplies both roles for every commodity;
        # only such complete commodity slices have a routing predicate to test.
        if not sources or not sinks:
            continue

        source_nodes = {terminal_nodes[terminal] for terminal in sources}
        sink_nodes = {terminal_nodes[terminal] for terminal in sinks}
        reachable_from_sources = reachable(source_nodes, commodity)
        unreachable_sinks = [terminal for terminal in sinks if terminal_nodes[terminal] not in reachable_from_sources]
        if unreachable_sinks:
            first = unreachable_sinks[0]
            raise NetworkRoutingError(
                "COMMODITY_SINK_UNREACHABLE",
                f"{commodity!r} sink {first.instance_id}/{first.port_id} is unreachable from every active source",
                cell=first.access,
            )

        dead_sources = [
            terminal
            for terminal in sources
            if not (reachable((terminal_nodes[terminal],), commodity) & sink_nodes)
        ]
        if dead_sources:
            first = dead_sources[0]
            raise NetworkRoutingError(
                "COMMODITY_SOURCE_DEAD_END",
                f"{commodity!r} source {first.instance_id}/{first.port_id} cannot reach any active sink",
                cell=first.access,
            )


def build_route_components(
    *,
    edges: Iterable[DirectedEdge],
    terminals: Sequence[Terminal],
    commodities: Sequence[str],
    occupied_cells: Iterable[Cell] = (),
    require_strong_connectivity: bool = True,
) -> list[dict[str, Any]]:
    """Compile a directed scaffold and terminal attachments to strict components."""

    edge_set = set(edges)
    if require_strong_connectivity:
        assert_strongly_connected(edge_set)
    cells = network_cells(edge_set)
    occupied = set(occupied_cells)
    collision = cells & occupied
    if collision:
        raise NetworkRoutingError("NETWORK_BODY_COLLISION", "route scaffold crosses a facility body", cell=min(collision))
    commodity_set = set(commodities)
    if not commodity_set:
        raise NetworkRoutingError("EMPTY_COMMODITY_SET", "route components need at least one commodity")

    inputs_by_cell: dict[Cell, set[Direction]] = defaultdict(set)
    outputs_by_cell: dict[Cell, set[Direction]] = defaultdict(set)
    for source, target in edge_set:
        direction = _direction_between(source, target)
        outputs_by_cell[source].add(direction)
        inputs_by_cell[target].add(_OPPOSITE[direction])

    for terminal in terminals:
        if terminal.commodity not in commodity_set:
            raise NetworkRoutingError("UNKNOWN_TERMINAL_COMMODITY", terminal.commodity, cell=terminal.access)
        if terminal.access not in cells:
            raise NetworkRoutingError(
                "TERMINAL_OFF_NETWORK",
                f"{terminal.instance_id}/{terminal.port_id} is not on the reserved scaffold",
                cell=terminal.access,
            )
        required = _OPPOSITE[terminal.outward]
        if terminal.kind == "output":
            inputs_by_cell[terminal.access].add(required)
        else:
            outputs_by_cell[terminal.access].add(required)

    components = [
        _component_for_cell(cell, inputs_by_cell[cell], outputs_by_cell[cell], tuple(commodity_set))
        for cell in sorted(cells, key=lambda value: (value[1], value[0]))
    ]
    assert_terminal_route_reachability(components, terminals, tuple(commodity_set))
    return components


def occupied_body_cells(
    instance: Mapping[str, Any], placements: Sequence[Mapping[str, Any]]
) -> frozenset[Cell]:
    modes = {
        (str(template_id), str(mode["id"])): mode
        for template_id, template in cast(Mapping[str, Any], instance["facility_templates"]).items()
        for mode in cast(Sequence[Mapping[str, Any]], template["modes"])
    }
    occupied: set[Cell] = set()
    for placement in placements:
        mode = modes[(str(placement["template"]), str(placement["mode"]))]
        body = cast(Mapping[str, Any], mode["body"])
        anchor = cast(Mapping[str, Any], placement["anchor"])
        for dx in range(int(body["width"])):
            for dy in range(int(body["height"])):
                cell = (int(anchor["x"]) + dx, int(anchor["y"]) + dy)
                if cell in occupied:
                    raise NetworkRoutingError("PLACEMENT_OVERLAP", "placements overlap", cell=cell)
                occupied.add(cell)
    return frozenset(occupied)

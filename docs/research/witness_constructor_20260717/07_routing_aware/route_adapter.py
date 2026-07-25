"""Fail-closed adapter from production routing states to the strict witness schema.

The production router represents a crossing as two selected physical states in
the same cell: a ground-layer straight ``belt`` and a perpendicular elevated
straight ``bridge``.  The strict witness schema instead represents that cell as
one ``cross`` component with two independent channels.  This module is the
research-only boundary between those representations.

The adapter deliberately accepts only the current ``extract_routes()`` contract
from :mod:`src.models.routing_subproblem`.  It does not repair, infer, or discard
malformed states: every mismatch raises :class:`RouteAdapterError` before a
witness can be serialized.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, TypedDict, cast


Direction = Literal["N", "E", "S", "W"]
Cell: TypeAlias = tuple[int, int]
PhysicalStateKey: TypeAlias = tuple[
    int,
    int,
    int,
    tuple[Direction, ...],
    tuple[Direction, ...],
    str,
]


class StrictChannel(TypedDict):
    """One directed, commodity-labelled channel in a strict component."""

    inputs: list[Direction]
    outputs: list[Direction]
    commodities: list[str]


class StrictNonCrossComponent(TypedDict):
    """Strict one-channel component representation."""

    cell: dict[str, int]
    kind: Literal["straight", "turn", "splitter", "merger"]
    inputs: list[Direction]
    outputs: list[Direction]
    commodities: list[str]


class StrictCrossComponent(TypedDict):
    """Strict two-channel crossing representation."""

    cell: dict[str, int]
    kind: Literal["cross"]
    channels: list[StrictChannel]


StrictRouteComponent: TypeAlias = StrictNonCrossComponent | StrictCrossComponent


_DIRECTIONS: tuple[Direction, ...] = ("N", "E", "S", "W")
_DIRECTION_SET = frozenset(_DIRECTIONS)
_DIRECTION_RANK = {direction: index for index, direction in enumerate(_DIRECTIONS)}
_OPPOSITE: dict[Direction, Direction] = {"N": "S", "E": "W", "S": "N", "W": "E"}


class RouteAdapterError(ValueError):
    """A stable, fail-closed adapter rejection.

    ``code`` is intended for attempt telemetry.  Callers must treat every code
    as an integrity failure, not as evidence that the underlying routing
    problem is mathematically infeasible.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        cell: Cell | None = None,
        layer: int | None = None,
        index: int | None = None,
    ) -> None:
        self.code = code
        self.cell = cell
        self.layer = layer
        self.index = index
        context = []
        if index is not None:
            context.append(f"index={index}")
        if cell is not None:
            context.append(f"cell={cell}")
        if layer is not None:
            context.append(f"layer={layer}")
        suffix = f" ({', '.join(context)})" if context else ""
        super().__init__(f"{code}: {message}{suffix}")


@dataclass(frozen=True)
class _ProductionState:
    cell: Cell
    layer: int
    component_type: str
    inputs: tuple[Direction, ...]
    outputs: tuple[Direction, ...]
    commodities: tuple[str, ...]
    strict_kind: Literal["straight", "turn", "splitter", "merger"]

    @property
    def axis(self) -> Literal["H", "V"] | None:
        directions = frozenset((*self.inputs, *self.outputs))
        if directions == {"E", "W"}:
            return "H"
        if directions == {"N", "S"}:
            return "V"
        return None


@dataclass(frozen=True)
class L1SupportRequirement:
    """One CP-SAT implication required by the strict crossing subset.

    When ``forbidden_at_terminal`` is false and compatible ground states exist,
    the intended constraint is::

        elevated_var <= sum(compatible_ground_vars)

    Otherwise the elevated variable must be fixed to zero.  The production
    router's existing bridge constraints remain responsible for excluding
    simultaneous non-perpendicular/non-straight L0 states; the adapter validates
    that invariant again on extracted selected states.
    """

    cell: Cell
    elevated_key: PhysicalStateKey
    compatible_ground_keys: tuple[PhysicalStateKey, ...]
    forbidden_at_terminal: bool


def _fail(
    code: str,
    message: str,
    *,
    state: _ProductionState | None = None,
    cell: Cell | None = None,
    layer: int | None = None,
    index: int | None = None,
) -> None:
    if state is not None:
        cell = state.cell
        layer = state.layer
    raise RouteAdapterError(code, message, cell=cell, layer=layer, index=index)


def _required(record: Mapping[str, object], field: str, *, index: int) -> object:
    if field not in record:
        _fail("MALFORMED_RECORD", f"missing required field {field!r}", index=index)
    return record[field]


def _integer(value: object, field: str, *, index: int) -> int:
    if type(value) is not int:
        _fail("MALFORMED_RECORD", f"{field} must be an integer", index=index)
    return cast(int, value)


def _sequence(value: object, field: str, *, index: int) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        _fail("MALFORMED_RECORD", f"{field} must be a list or tuple", index=index)
    return cast(Sequence[object], value)


def _direction_tuple(value: object, field: str, *, index: int) -> tuple[Direction, ...]:
    raw = _sequence(value, field, index=index)
    if any(type(direction) is not str or direction not in _DIRECTION_SET for direction in raw):
        _fail("INVALID_DIRECTIONS", f"{field} contains an unknown direction", index=index)
    directions = tuple(cast(Direction, direction) for direction in raw)
    if len(directions) != len(set(directions)):
        _fail("INVALID_DIRECTIONS", f"{field} contains duplicate directions", index=index)
    return directions


def _commodity_tuple(value: object, *, index: int) -> tuple[str, ...]:
    raw = _sequence(value, "commodities", index=index)
    if not raw or any(type(commodity) is not str or not commodity for commodity in raw):
        _fail("INVALID_COMMODITIES", "commodities must be nonempty strings", index=index)
    commodities = tuple(cast(str, commodity) for commodity in raw)
    if len(commodities) != len(set(commodities)):
        _fail("INVALID_COMMODITIES", "commodities must be unique", index=index)
    return tuple(sorted(commodities))


def _classify_ground_shape(
    component_type: str,
    inputs: tuple[Direction, ...],
    outputs: tuple[Direction, ...],
    *,
    index: int | None = None,
    cell: Cell | None = None,
) -> Literal["straight", "turn", "splitter", "merger"]:
    if set(inputs) & set(outputs):
        _fail(
            "INVALID_COMPONENT_SHAPE",
            "input and output sides must be disjoint",
            index=index,
            cell=cell,
            layer=0,
        )

    if component_type == "belt":
        if len(inputs) != 1 or len(outputs) != 1:
            _fail(
                "INVALID_COMPONENT_SHAPE",
                "belt requires exactly one input and one output",
                index=index,
                cell=cell,
                layer=0,
            )
        return "straight" if outputs[0] == _OPPOSITE[inputs[0]] else "turn"

    if component_type == "splitter":
        if len(inputs) != 1 or len(outputs) not in (2, 3):
            _fail(
                "INVALID_COMPONENT_SHAPE",
                "splitter requires one input and two or three outputs",
                index=index,
                cell=cell,
                layer=0,
            )
        return "splitter"

    if component_type == "merger":
        if len(outputs) != 1 or len(inputs) not in (2, 3):
            _fail(
                "INVALID_COMPONENT_SHAPE",
                "merger requires two or three inputs and one output",
                index=index,
                cell=cell,
                layer=0,
            )
        return "merger"

    _fail(
        "UNKNOWN_COMPONENT_TYPE",
        f"unsupported L0 component type {component_type!r}",
        index=index,
        cell=cell,
        layer=0,
    )


def _validate_bridge_shape(
    component_type: str,
    inputs: tuple[Direction, ...],
    outputs: tuple[Direction, ...],
    *,
    index: int | None = None,
    cell: Cell | None = None,
) -> None:
    if component_type != "bridge":
        _fail(
            "UNKNOWN_COMPONENT_TYPE",
            f"unsupported L1 component type {component_type!r}",
            index=index,
            cell=cell,
            layer=1,
        )
    if len(inputs) != 1 or len(outputs) != 1 or outputs[0] != _OPPOSITE[inputs[0]]:
        _fail(
            "INVALID_COMPONENT_SHAPE",
            "L1 bridge must be a directed straight",
            index=index,
            cell=cell,
            layer=1,
        )


def _validate_uses(
    record: Mapping[str, object],
    inputs: tuple[Direction, ...],
    outputs: tuple[Direction, ...],
    commodities: tuple[str, ...],
    *,
    index: int,
) -> None:
    raw_uses = _sequence(_required(record, "uses", index=index), "uses", index=index)
    seen: list[str] = []
    for use_index, raw_use in enumerate(raw_uses):
        if not isinstance(raw_use, Mapping):
            _fail("MALFORMED_RECORD", f"uses[{use_index}] must be an object", index=index)
        use = cast(Mapping[str, object], raw_use)
        commodity = use.get("commodity")
        if type(commodity) is not str or not commodity:
            _fail("USES_MISMATCH", f"uses[{use_index}] has an invalid commodity", index=index)
        use_inputs = _direction_tuple(use.get("flow_in"), f"uses[{use_index}].flow_in", index=index)
        use_outputs = _direction_tuple(use.get("flow_out"), f"uses[{use_index}].flow_out", index=index)
        if use_inputs != inputs or use_outputs != outputs:
            _fail("USES_MISMATCH", f"uses[{use_index}] flow differs from its physical state", index=index)
        seen.append(cast(str, commodity))
    if len(seen) != len(set(seen)) or set(seen) != set(commodities):
        _fail("USES_MISMATCH", "uses must contain each top-level commodity exactly once", index=index)


def _parse_extracted_state(record: Mapping[str, object], *, index: int) -> _ProductionState:
    x = _integer(_required(record, "x", index=index), "x", index=index)
    y = _integer(_required(record, "y", index=index), "y", index=index)
    layer = _integer(_required(record, "layer", index=index), "layer", index=index)
    cell = (x, y)
    if layer not in (0, 1):
        _fail("UNKNOWN_LAYER", f"unsupported routing layer {layer}", cell=cell, layer=layer, index=index)

    raw_type = record.get("type")
    raw_component_type = record.get("component_type")
    if raw_type is None and raw_component_type is None:
        _fail("MALFORMED_RECORD", "missing type/component_type", cell=cell, layer=layer, index=index)
    if raw_type is not None and type(raw_type) is not str:
        _fail("MALFORMED_RECORD", "type must be a string", cell=cell, layer=layer, index=index)
    if raw_component_type is not None and type(raw_component_type) is not str:
        _fail("MALFORMED_RECORD", "component_type must be a string", cell=cell, layer=layer, index=index)
    if raw_type is not None and raw_component_type is not None and raw_type != raw_component_type:
        _fail("TYPE_MISMATCH", "type and component_type disagree", cell=cell, layer=layer, index=index)
    component_type = cast(str, raw_component_type if raw_component_type is not None else raw_type)

    inputs = _direction_tuple(_required(record, "flow_in", index=index), "flow_in", index=index)
    outputs = _direction_tuple(_required(record, "flow_out", index=index), "flow_out", index=index)
    commodities = _commodity_tuple(_required(record, "commodities", index=index), index=index)
    _validate_uses(record, inputs, outputs, commodities, index=index)

    nested_flow = record.get("flow")
    if nested_flow is not None:
        if not isinstance(nested_flow, Mapping):
            _fail("MALFORMED_RECORD", "flow fallback must be an object", index=index)
        nested = cast(Mapping[str, object], nested_flow)
        if (
            _direction_tuple(nested.get("flow_in"), "flow.flow_in", index=index) != inputs
            or _direction_tuple(nested.get("flow_out"), "flow.flow_out", index=index) != outputs
        ):
            _fail("FLOW_MISMATCH", "nested flow disagrees with authoritative top-level flow", index=index)

    legacy_commodity = record.get("commodity")
    if legacy_commodity is not None and (len(commodities) != 1 or legacy_commodity != commodities[0]):
        _fail("COMMODITY_MISMATCH", "legacy commodity field disagrees with commodities", index=index)
    if "dir_in" in record and (len(inputs) != 1 or record["dir_in"] != inputs[0]):
        _fail("FLOW_MISMATCH", "dir_in disagrees with flow_in", index=index)
    if "dir_out" in record and (len(outputs) != 1 or record["dir_out"] != outputs[0]):
        _fail("FLOW_MISMATCH", "dir_out disagrees with flow_out", index=index)

    if layer == 0:
        strict_kind = _classify_ground_shape(component_type, inputs, outputs, index=index, cell=cell)
    else:
        _validate_bridge_shape(component_type, inputs, outputs, index=index, cell=cell)
        strict_kind = "straight"
    return _ProductionState(cell, layer, component_type, inputs, outputs, commodities, strict_kind)


def _terminal_cell_set(terminal_cells: Iterable[Cell]) -> frozenset[Cell]:
    normalized: set[Cell] = set()
    for index, cell in enumerate(terminal_cells):
        if not isinstance(cell, (tuple, list)) or len(cell) != 2:
            _fail("INVALID_TERMINAL_CELL", "terminal cell must be an (x, y) pair", index=index)
        x, y = cell
        if type(x) is not int or type(y) is not int:
            _fail("INVALID_TERMINAL_CELL", "terminal coordinates must be integers", index=index)
        normalized.add((x, y))
    return frozenset(normalized)


def _ordered_directions(directions: tuple[Direction, ...]) -> list[Direction]:
    return sorted(directions, key=_DIRECTION_RANK.__getitem__)


def _channel(state: _ProductionState) -> StrictChannel:
    return {
        "inputs": _ordered_directions(state.inputs),
        "outputs": _ordered_directions(state.outputs),
        "commodities": list(state.commodities),
    }


def _non_cross_component(state: _ProductionState) -> StrictNonCrossComponent:
    return {
        "cell": {"x": state.cell[0], "y": state.cell[1]},
        "kind": state.strict_kind,
        "inputs": _ordered_directions(state.inputs),
        "outputs": _ordered_directions(state.outputs),
        "commodities": list(state.commodities),
    }


def adapt_extracted_routes(
    extracted_routes: Iterable[Mapping[str, object]],
    *,
    terminal_cells: Iterable[Cell] = (),
) -> list[StrictRouteComponent]:
    """Convert selected production L0/L1 states into strict route components.

    Cells are returned in deterministic row-major order.  A cell may contain a
    single L0 state, or an L0/L1 pair that forms a perpendicular crossing.  L1
    is never emitted on its own and is forbidden on active terminal/front cells.
    """

    terminals = _terminal_cell_set(terminal_cells)
    by_cell: defaultdict[Cell, dict[int, _ProductionState]] = defaultdict(dict)
    for index, raw_record in enumerate(extracted_routes):
        if not isinstance(raw_record, Mapping):
            _fail("MALFORMED_RECORD", "route record must be an object", index=index)
        state = _parse_extracted_state(cast(Mapping[str, object], raw_record), index=index)
        if state.layer in by_cell[state.cell]:
            _fail(
                "DUPLICATE_LAYER_STATE",
                "more than one selected physical state occupies this cell/layer",
                state=state,
                index=index,
            )
        by_cell[state.cell][state.layer] = state

    components: list[StrictRouteComponent] = []
    for cell in sorted(by_cell, key=lambda value: (value[1], value[0])):
        states = by_cell[cell]
        ground = states.get(0)
        elevated = states.get(1)
        if elevated is None:
            if ground is None:  # Defensive: impossible after parsing a nonempty cell bucket.
                _fail("INTERNAL_ADAPTER_ERROR", "cell bucket has no state", cell=cell)
            components.append(_non_cross_component(ground))
            continue

        if cell in terminals:
            _fail("TERMINAL_ON_L1", "an active terminal/front cell cannot use L1", state=elevated)
        if ground is None:
            _fail("STANDALONE_L1", "L1 bridge has no same-cell L0 straight", state=elevated)
        if ground.strict_kind != "straight":
            _fail(
                "NON_STRAIGHT_CROSS",
                f"L1 bridge cannot cross an L0 {ground.strict_kind}",
                state=ground,
            )
        if ground.axis is None or elevated.axis is None:
            _fail("INVALID_COMPONENT_SHAPE", "crossing channels must both be straight", cell=cell)
        if ground.axis == elevated.axis:
            _fail("SAME_AXIS_CROSS", "crossing channels must be perpendicular", cell=cell)

        horizontal = ground if ground.axis == "H" else elevated
        vertical = ground if ground.axis == "V" else elevated
        components.append(
            {
                "cell": {"x": cell[0], "y": cell[1]},
                "kind": "cross",
                # Keeping two channel objects (rather than merging direction or
                # commodity sets) is the strict no-transfer representation.
                "channels": [_channel(horizontal), _channel(vertical)],
            }
        )
    return components


def _normalize_physical_key(raw_key: object) -> PhysicalStateKey:
    if not isinstance(raw_key, tuple) or len(raw_key) != 6:
        _fail("MALFORMED_PHYSICAL_KEY", "physical-state key must be a six-item tuple")
    x, y, layer, raw_inputs, raw_outputs, component_type = raw_key
    if type(x) is not int or type(y) is not int or type(layer) is not int or type(component_type) is not str:
        _fail("MALFORMED_PHYSICAL_KEY", "physical-state key has invalid scalar fields")
    cell = (cast(int, x), cast(int, y))
    typed_layer = cast(int, layer)
    if typed_layer not in (0, 1):
        _fail("UNKNOWN_LAYER", f"unsupported routing layer {typed_layer}", cell=cell, layer=typed_layer)
    inputs = _direction_tuple(raw_inputs, "physical_key.flow_in", index=-1)
    outputs = _direction_tuple(raw_outputs, "physical_key.flow_out", index=-1)
    typed_component = cast(str, component_type)
    if typed_layer == 0:
        _classify_ground_shape(typed_component, inputs, outputs, cell=cell)
    else:
        _validate_bridge_shape(typed_component, inputs, outputs, cell=cell)
    return (cell[0], cell[1], typed_layer, inputs, outputs, typed_component)


def build_l1_support_contract(
    physical_state_keys: Iterable[PhysicalStateKey],
    *,
    terminal_cells: Iterable[Cell] = (),
) -> tuple[L1SupportRequirement, ...]:
    """Build the pure L1-support contract for a production router model.

    Each returned record describes the perpendicular L0 straight candidates
    that may support one L1 bridge state.  An empty support tuple means that the
    bridge must be disabled.  Terminal cells always force that result.
    """

    terminals = _terminal_cell_set(terminal_cells)
    keys = tuple(_normalize_physical_key(key) for key in physical_state_keys)
    if len(keys) != len(set(keys)):
        _fail("DUPLICATE_PHYSICAL_KEY", "physical-state keys must be unique")

    ground_by_cell: defaultdict[Cell, list[PhysicalStateKey]] = defaultdict(list)
    elevated_keys: list[PhysicalStateKey] = []
    for key in keys:
        x, y, layer, _inputs, _outputs, _component_type = key
        if layer == 0:
            ground_by_cell[(x, y)].append(key)
        else:
            elevated_keys.append(key)

    requirements: list[L1SupportRequirement] = []
    for elevated_key in sorted(elevated_keys):
        x, y, _layer, elevated_inputs, elevated_outputs, _component_type = elevated_key
        cell = (x, y)
        elevated_axis = _axis(elevated_inputs, elevated_outputs)
        compatible = []
        if cell not in terminals:
            for ground_key in ground_by_cell.get(cell, ()):
                _gx, _gy, _glayer, ground_inputs, ground_outputs, ground_type = ground_key
                if (
                    ground_type == "belt"
                    and _is_straight(ground_inputs, ground_outputs)
                    and _axis(ground_inputs, ground_outputs) != elevated_axis
                ):
                    compatible.append(ground_key)
        requirements.append(
            L1SupportRequirement(
                cell=cell,
                elevated_key=elevated_key,
                compatible_ground_keys=tuple(sorted(compatible)),
                forbidden_at_terminal=cell in terminals,
            )
        )
    return tuple(requirements)


def add_l1_support_constraints(
    model: Any,
    physical_vars: Mapping[PhysicalStateKey, Any],
    *,
    terminal_cells: Iterable[Cell] = (),
) -> tuple[L1SupportRequirement, ...]:
    """Add the strict-subset L1 implications to a CP-SAT-like model.

    The object must expose OR-Tools-compatible ``Add`` and the mapped variables
    must support Boolean linear expressions.  This helper intentionally avoids
    importing OR-Tools so the serializer and its tests remain lightweight.
    Callers must retain the production router's existing per-layer capacity and
    bridge incompatibility constraints.
    """

    add = getattr(model, "Add", None)
    if not callable(add):
        _fail("INVALID_MODEL", "model does not expose a callable Add method")
    requirements = build_l1_support_contract(physical_vars, terminal_cells=terminal_cells)
    for requirement in requirements:
        elevated_var = physical_vars[requirement.elevated_key]
        if requirement.forbidden_at_terminal or not requirement.compatible_ground_keys:
            add(elevated_var == 0)
            continue
        support = sum((physical_vars[key] for key in requirement.compatible_ground_keys), start=0)
        add(elevated_var <= support)
    return requirements


def _is_straight(inputs: tuple[Direction, ...], outputs: tuple[Direction, ...]) -> bool:
    return len(inputs) == 1 and len(outputs) == 1 and outputs[0] == _OPPOSITE[inputs[0]]


def _axis(
    inputs: tuple[Direction, ...],
    outputs: tuple[Direction, ...],
) -> Literal["H", "V"] | None:
    directions = frozenset((*inputs, *outputs))
    if directions == {"E", "W"}:
        return "H"
    if directions == {"N", "S"}:
        return "V"
    return None


__all__ = [
    "Cell",
    "Direction",
    "L1SupportRequirement",
    "PhysicalStateKey",
    "RouteAdapterError",
    "StrictChannel",
    "StrictCrossComponent",
    "StrictNonCrossComponent",
    "StrictRouteComponent",
    "adapt_extracted_routes",
    "add_l1_support_constraints",
    "build_l1_support_contract",
]

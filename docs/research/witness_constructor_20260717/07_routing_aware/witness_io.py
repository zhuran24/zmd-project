"""Strict witness binding, serialization, and independent-checker boundary.

This research-only module keeps three representations explicit:

* geometry placements select a strict template, mode, and anchor;
* binding selections name strict physical port IDs;
* production router port specs store the already-derived access/front cell.

No function guesses a port assignment or repairs malformed data.  Every
contract mismatch raises :class:`WitnessIOError`, and checker subprocess output
is accepted only when its exit code, status, and error payload agree exactly.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Literal, TypedDict, cast


Cell = tuple[int, int]
Direction = Literal["N", "E", "S", "W"]

_DIRECTIONS: tuple[Direction, ...] = ("N", "E", "S", "W")
_DIRECTION_SET = frozenset(_DIRECTIONS)
_DIRECTION_RANK = {direction: index for index, direction in enumerate(_DIRECTIONS)}
_DELTA: dict[Direction, Cell] = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
_CHECKER_EXIT_BY_STATUS = {
    "LAYOUT_FEASIBLE": 0,
    "LAYOUT_INVALID": 1,
    "CONTRACT_ERROR": 2,
    "INTERNAL_ERROR": 3,
}
EXPECTED_CHECKER_SHA256 = "10952b0a253bacff788c261b6e405e656e05ad8525fe475746ba0b88c1aeaeba"
EXPECTED_CHECKER_PATH = (
    Path(__file__).resolve().parents[4] / "scripts/cleanroom_strict/validate_layout.py"
).resolve()
PINNED_CHECKER_EXECUTION_MODE = "stdin_stable_snapshot_v1"
_EXPECTED_CHECKER_CATEGORIES = {
    "J": "strict_json",
    "S": "document_shape",
    "I": "instance_integrity",
    "F": "facility_geometry",
    "P": "port_binding",
    "PW": "power",
    "R": "routing",
    "O": "objective",
}


class BoundPlacementSet(TypedDict):
    """Complete strict placements split by required/optional ownership."""

    required_placements: list[dict[str, Any]]
    optional_placements: list[dict[str, Any]]


class WitnessIOError(ValueError):
    """Stable fail-closed witness construction error."""

    def __init__(self, code: str, message: str, *, pointer: str | None = None) -> None:
        self.code = code
        self.pointer = pointer
        suffix = f" ({pointer})" if pointer else ""
        super().__init__(f"{code}: {message}{suffix}")


@dataclass(frozen=True)
class CheckerProcessResult:
    """Typed result from the independent checker subprocess."""

    classification: str
    exit_code: int | None
    status: str | None
    report: dict[str, Any] | None
    stdout: str
    stderr: str
    signal_number: int | None = None
    checker_trusted: bool = False
    checker_sha256: str | None = None
    checker_source_path: str | None = None
    checker_source_identity: tuple[int, int, int, int, int, int, int] | None = None
    checker_snapshot_size_bytes: int | None = None
    checker_python_executable: str | None = None
    checker_execution_mode: str | None = None

    @property
    def accepted(self) -> bool:
        return (
            self.classification == "LAYOUT_FEASIBLE"
            and self.exit_code == 0
            and self.status == "LAYOUT_FEASIBLE"
            and self.report is not None
            and self.report.get("errors") == []
            and _checker_report_schema_valid(self.report)
            and self.checker_trusted
            and self.checker_sha256 == EXPECTED_CHECKER_SHA256
            and self.checker_source_path == str(EXPECTED_CHECKER_PATH)
            and self.checker_source_identity is not None
            and len(self.checker_source_identity) == 7
            and self.checker_snapshot_size_bytes is not None
            and self.checker_snapshot_size_bytes > 0
            and self.checker_source_identity[4] == self.checker_snapshot_size_bytes
            and stat.S_ISREG(self.checker_source_identity[2])
            and self.checker_python_executable == str(Path(sys.executable).resolve())
            and self.checker_execution_mode == PINNED_CHECKER_EXECUTION_MODE
            and self.stderr == ""
        )


@dataclass(frozen=True)
class _CheckerSnapshot:
    """One immutable checker-source snapshot plus its open-file identity."""

    payload: bytes
    sha256: str
    size_bytes: int
    source_identity: tuple[int, int, int, int, int, int, int]


@dataclass(frozen=True)
class _PortSlot:
    instance_id: str
    port_id: str
    kind: Literal["input", "output"]
    direction: Direction
    access: Cell

    @property
    def endpoint(self) -> tuple[int, int, Direction, Literal["input", "output"]]:
        return (*self.access, self.direction, self.kind)


def _fail(code: str, message: str, *, pointer: str | None = None) -> None:
    raise WitnessIOError(code, message, pointer=pointer)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail("MALFORMED_INPUT", f"{name} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail("MALFORMED_INPUT", f"{name} must be an array")
    return cast(Sequence[object], value)


def _string(value: object, name: str) -> str:
    if type(value) is not str or not value:
        _fail("MALFORMED_INPUT", f"{name} must be a nonempty string")
    return cast(str, value)


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        _fail("MALFORMED_INPUT", f"{name} must be an integer")
    return cast(int, value)


def _instance_commodities(instance: Mapping[str, object]) -> frozenset[str]:
    commodities = _sequence(instance.get("commodities"), "instance.commodities")
    result = tuple(_string(value, "instance commodity") for value in commodities)
    if len(result) != len(set(result)):
        _fail("INSTANCE_CONTRACT_ERROR", "instance commodities are not unique")
    return frozenset(result)


def _template(instance: Mapping[str, object], template_id: str) -> Mapping[str, object]:
    templates = _mapping(instance.get("facility_templates"), "instance.facility_templates")
    if template_id not in templates:
        _fail("UNKNOWN_TEMPLATE", f"unknown strict template {template_id!r}")
    return _mapping(templates[template_id], f"template {template_id}")


def _mode(
    instance: Mapping[str, object],
    template_id: str,
    mode_id: str,
) -> Mapping[str, object]:
    modes = _sequence(_template(instance, template_id).get("modes"), f"template {template_id}.modes")
    matches = [
        _mapping(raw_mode, f"template {template_id} mode")
        for raw_mode in modes
        if isinstance(raw_mode, Mapping) and raw_mode.get("id") == mode_id
    ]
    if len(matches) != 1:
        code = "UNKNOWN_MODE" if not matches else "INSTANCE_CONTRACT_ERROR"
        _fail(code, f"expected exactly one mode {template_id}/{mode_id}, found {len(matches)}")
    return matches[0]


def _placement_base(placement: Mapping[str, object]) -> dict[str, Any]:
    instance_id = _string(placement.get("instance_id"), "placement.instance_id")
    template_id = _string(placement.get("template"), f"placement {instance_id}.template")
    mode_id = _string(placement.get("mode"), f"placement {instance_id}.mode")
    anchor = _mapping(placement.get("anchor"), f"placement {instance_id}.anchor")
    return {
        "instance_id": instance_id,
        "template": template_id,
        "mode": mode_id,
        "anchor": {
            "x": _integer(anchor.get("x"), f"placement {instance_id}.anchor.x"),
            "y": _integer(anchor.get("y"), f"placement {instance_id}.anchor.y"),
        },
    }


def _ports_by_id(mode: Mapping[str, object], *, context: str) -> dict[str, Mapping[str, object]]:
    ports: dict[str, Mapping[str, object]] = {}
    for raw_port in _sequence(mode.get("ports"), f"{context}.ports"):
        port = _mapping(raw_port, f"{context} port")
        port_id = _string(port.get("id"), f"{context} port.id")
        if port_id in ports:
            _fail("INSTANCE_CONTRACT_ERROR", f"duplicate physical port ID {port_id!r} in {context}")
        kind = port.get("kind")
        direction = port.get("direction")
        if kind not in ("input", "output") or direction not in _DIRECTION_SET:
            _fail("INSTANCE_CONTRACT_ERROR", f"invalid kind/direction for {context}/{port_id}")
        body_cell = _mapping(port.get("body_cell"), f"{context}/{port_id}.body_cell")
        _integer(body_cell.get("x"), f"{context}/{port_id}.body_cell.x")
        _integer(body_cell.get("y"), f"{context}/{port_id}.body_cell.y")
        ports[port_id] = port
    return ports


def complete_port_bindings(
    instance: Mapping[str, object],
    placement: Mapping[str, object],
    selected_port_bindings: Mapping[str, str],
) -> dict[str, Any]:
    """Return one strict placement with every physical port explicitly bound/null.

    ``selected_port_bindings`` contains active physical port IDs only.  Existing
    ``port_bindings`` on the geometry record are rejected so there is exactly one
    authority for binding selection.
    """

    if "port_bindings" in placement:
        _fail("PLACEMENT_ALREADY_BOUND", "geometry placement already contains port_bindings")
    base = _placement_base(placement)
    mode = _mode(instance, base["template"], base["mode"])
    ports = _ports_by_id(mode, context=f"{base['template']}/{base['mode']}")
    selected = _mapping(selected_port_bindings, f"selected bindings for {base['instance_id']}")
    unknown_ids = sorted(set(selected) - set(ports))
    if unknown_ids:
        _fail(
            "UNKNOWN_PORT_ID",
            f"selected bindings reference unknown physical ports {unknown_ids}",
            pointer=base["instance_id"],
        )
    commodities = _instance_commodities(instance)
    bindings: dict[str, str | None] = {}
    for port_id in sorted(ports):
        commodity = selected.get(port_id)
        if commodity is None:
            bindings[port_id] = None
            continue
        if type(commodity) is not str or commodity not in commodities:
            _fail(
                "UNKNOWN_COMMODITY",
                f"invalid commodity {commodity!r} selected for {port_id}",
                pointer=base["instance_id"],
            )
        bindings[port_id] = cast(str, commodity)
    return {**base, "port_bindings": bindings}


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {commodity: count for commodity, count in sorted(counter.items()) if count}


def _required_count_map(value: object, name: str) -> dict[str, int]:
    raw = _mapping(value, name)
    result: dict[str, int] = {}
    for raw_commodity, raw_count in raw.items():
        commodity = _string(raw_commodity, f"{name} commodity")
        count = _integer(raw_count, f"{name}.{commodity}")
        if count <= 0:
            _fail("INSTANCE_CONTRACT_ERROR", f"{name}.{commodity} must be positive")
        result[commodity] = count
    return dict(sorted(result.items()))


def _bound_counts(
    instance: Mapping[str, object],
    placement: Mapping[str, object],
) -> dict[str, Counter[str]]:
    base = _placement_base(placement)
    bindings = _mapping(placement.get("port_bindings"), f"placement {base['instance_id']}.port_bindings")
    mode = _mode(instance, base["template"], base["mode"])
    ports = _ports_by_id(mode, context=f"{base['template']}/{base['mode']}")
    if set(bindings) != set(ports):
        _fail(
            "INCOMPLETE_PORT_MAP",
            f"port map must contain exactly {sorted(ports)}",
            pointer=base["instance_id"],
        )
    commodities = _instance_commodities(instance)
    counts = {"input": Counter(), "output": Counter()}
    for port_id, port in ports.items():
        commodity = bindings[port_id]
        if commodity is None:
            continue
        if type(commodity) is not str or commodity not in commodities:
            _fail("UNKNOWN_COMMODITY", f"invalid binding on {port_id}", pointer=base["instance_id"])
        counts[cast(str, port["kind"])][cast(str, commodity)] += 1
    return counts


def bind_placements(
    instance: Mapping[str, object],
    *,
    required_placements: Sequence[Mapping[str, object]],
    optional_placements: Sequence[Mapping[str, object]] = (),
    selected_port_bindings: Mapping[str, Mapping[str, str]] | None = None,
    allowed_access_cells: Iterable[Cell] | None = None,
    core_final_input_access_cells: Iterable[Cell] | None = None,
    require_all_core_raw_outputs: bool = True,
) -> BoundPlacementSet:
    """Bind a complete strict layout and enforce exact manufacturing/generic counts.

    Supplying ``selected_port_bindings`` preserves explicit physical-port
    authority.  When it is omitted, :func:`choose_port_bindings` selects the
    lexicographically first exact assignment within the optional access-cell
    restrictions.
    """

    raw_required = _sequence(required_placements, "required_placements")
    raw_optional = _sequence(optional_placements, "optional_placements")
    required_records = [_mapping(value, "required placement") for value in raw_required]
    optional_records = [_mapping(value, "optional placement") for value in raw_optional]
    allowed = _cell_set(allowed_access_cells, "allowed_access_cells")
    requested_core_final = _cell_set(core_final_input_access_cells, "core_final_input_access_cells")
    if selected_port_bindings is None:
        selected_port_bindings = choose_port_bindings(
            instance,
            required_placements=required_records,
            optional_placements=optional_records,
            allowed_access_cells=allowed,
            core_final_input_access_cells=requested_core_final,
            require_all_core_raw_outputs=require_all_core_raw_outputs,
        )
    required_instance_rows = _sequence(instance.get("required_instances"), "instance.required_instances")
    required_by_id: dict[str, Mapping[str, object]] = {}
    for raw_required_instance in required_instance_rows:
        required_instance = _mapping(raw_required_instance, "required instance")
        required_id = _string(required_instance.get("id"), "required instance.id")
        if required_id in required_by_id:
            _fail("INSTANCE_CONTRACT_ERROR", f"duplicate required instance {required_id!r}")
        required_by_id[required_id] = required_instance

    geometry_by_id: dict[str, Mapping[str, object]] = {}
    required_ids: set[str] = set()
    for placement in required_records:
        base = _placement_base(placement)
        instance_id = base["instance_id"]
        if instance_id in geometry_by_id:
            _fail("DUPLICATE_PLACEMENT", f"duplicate placement {instance_id!r}")
        geometry_by_id[instance_id] = placement
        required_ids.add(instance_id)
        required = required_by_id.get(instance_id)
        if required is None:
            _fail("REQUIRED_PLACEMENT_MISMATCH", f"unknown required placement {instance_id!r}")
        if base["template"] != required.get("template"):
            _fail("REQUIRED_PLACEMENT_MISMATCH", f"template mismatch for {instance_id!r}")
    if required_ids != set(required_by_id):
        missing = sorted(set(required_by_id) - required_ids)
        extra = sorted(required_ids - set(required_by_id))
        _fail("REQUIRED_PLACEMENT_MISMATCH", f"required placement IDs differ; missing={missing}, extra={extra}")

    repeatable = {
        _string(value, "repeatable auxiliary")
        for value in _sequence(instance.get("repeatable_auxiliaries"), "instance.repeatable_auxiliaries")
    }
    optional_ids: set[str] = set()
    storage_box_count = 0
    for placement in optional_records:
        base = _placement_base(placement)
        instance_id = base["instance_id"]
        if instance_id in geometry_by_id:
            _fail("DUPLICATE_PLACEMENT", f"duplicate placement {instance_id!r}")
        if instance_id in required_by_id or base["template"] not in repeatable:
            _fail("OPTIONAL_PLACEMENT_MISMATCH", f"invalid optional placement {instance_id!r}")
        geometry_by_id[instance_id] = placement
        optional_ids.add(instance_id)
        storage_box_count += base["template"] == "storage_box"
    if storage_box_count > 2:
        _fail("TOO_MANY_STORAGE_BOXES", "at most two optional storage boxes are allowed")

    selected_by_id = _mapping(selected_port_bindings, "selected_port_bindings")
    unknown_binding_instances = sorted(set(selected_by_id) - set(geometry_by_id))
    if unknown_binding_instances:
        _fail("UNKNOWN_BINDING_INSTANCE", f"bindings reference unknown placements {unknown_binding_instances}")

    bound_by_id: dict[str, dict[str, Any]] = {}
    for instance_id, geometry in geometry_by_id.items():
        raw_selected = selected_by_id.get(instance_id, {})
        selected = _mapping(raw_selected, f"selected bindings for {instance_id}")
        bound_by_id[instance_id] = complete_port_bindings(
            instance,
            geometry,
            cast(Mapping[str, str], selected),
        )

    groups_by_id: dict[str, Mapping[str, object]] = {}
    manufacturing_group_by_instance: dict[str, Mapping[str, object]] = {}
    for raw_group in _sequence(instance.get("operation_groups"), "instance.operation_groups"):
        group = _mapping(raw_group, "operation group")
        group_id = _string(group.get("id"), "operation group.id")
        if group_id in groups_by_id:
            _fail("INSTANCE_CONTRACT_ERROR", f"duplicate operation group {group_id!r}")
        groups_by_id[group_id] = group
        for raw_instance_id in _sequence(group.get("instance_ids"), f"operation group {group_id}.instance_ids"):
            instance_id = _string(raw_instance_id, f"operation group {group_id} instance")
            if instance_id in manufacturing_group_by_instance:
                _fail("INSTANCE_CONTRACT_ERROR", f"manufacturing instance {instance_id!r} belongs to two groups")
            manufacturing_group_by_instance[instance_id] = group

    for instance_id, group in manufacturing_group_by_instance.items():
        if instance_id not in bound_by_id:
            _fail("REQUIRED_PLACEMENT_MISMATCH", f"manufacturing instance {instance_id!r} is not placed")
        counts = _bound_counts(instance, bound_by_id[instance_id])
        needs = _mapping(group.get("port_needs"), f"operation group {group.get('id')}.port_needs")
        expected_inputs = _required_count_map(needs.get("inputs"), "manufacturing inputs")
        expected_outputs = _required_count_map(needs.get("outputs"), "manufacturing outputs")
        actual_inputs = _counter_dict(counts["input"])
        actual_outputs = _counter_dict(counts["output"])
        if actual_inputs != expected_inputs or actual_outputs != expected_outputs:
            _fail(
                "MANUFACTURING_BINDING_MISMATCH",
                (
                    f"{instance_id} expected inputs={expected_inputs}, outputs={expected_outputs}; "
                    f"got inputs={actual_inputs}, outputs={actual_outputs}"
                ),
                pointer=instance_id,
            )

    generic = _mapping(instance.get("generic_requirements"), "instance.generic_requirements")
    raw_providers = {
        _string(value, "raw output provider")
        for value in _sequence(generic.get("raw_output_providers"), "generic raw_output_providers")
    }
    final_providers = {
        _string(value, "final input provider")
        for value in _sequence(generic.get("final_input_providers"), "generic final_input_providers")
    }
    raw_counts: Counter[str] = Counter()
    final_counts: Counter[str] = Counter()
    for instance_id, placement in bound_by_id.items():
        if instance_id in manufacturing_group_by_instance:
            continue
        template_id = cast(str, placement["template"])
        counts = _bound_counts(instance, placement)
        if template_id in raw_providers:
            raw_counts.update(counts["output"])
        elif counts["output"]:
            _fail("GENERIC_PROVIDER_MISMATCH", f"{instance_id} has active outputs but is not a raw provider")
        if template_id in final_providers:
            final_counts.update(counts["input"])
        elif counts["input"]:
            _fail("GENERIC_PROVIDER_MISMATCH", f"{instance_id} has active inputs but is not a final provider")
        if template_id == "storage_box":
            if counts["output"]:
                _fail("STORAGE_BOX_OUTPUT_ACTIVE", f"storage box {instance_id} has an active output")
            if not counts["input"]:
                _fail("EMPTY_STORAGE_BOX", f"selected storage box {instance_id} carries no final input")

    expected_raw = _required_count_map(generic.get("raw_outputs"), "generic raw outputs")
    expected_final = _required_count_map(generic.get("final_inputs"), "generic final inputs")
    actual_raw = _counter_dict(raw_counts)
    actual_final = _counter_dict(final_counts)
    if actual_raw != expected_raw or actual_final != expected_final:
        _fail(
            "GENERIC_BINDING_MISMATCH",
            (
                f"expected raw={expected_raw}, final={expected_final}; "
                f"got raw={actual_raw}, final={actual_final}"
            ),
        )

    bound_slots = _port_slots(instance, bound_by_id.values())
    for slot in bound_slots:
        commodity = bound_by_id[slot.instance_id]["port_bindings"][slot.port_id]
        if commodity is None:
            continue
        if allowed is not None and slot.access not in allowed:
            _fail(
                "ACCESS_RESTRICTION_VIOLATION",
                f"active port {slot.instance_id}/{slot.port_id} is outside allowed_access_cells",
            )
        template_id = cast(str, bound_by_id[slot.instance_id]["template"])
        if (
            requested_core_final is not None
            and slot.kind == "input"
            and template_id in final_providers
            and (template_id != "protocol_core" or slot.access not in requested_core_final)
        ):
            _fail(
                "CORE_FINAL_ACCESS_VIOLATION",
                f"final input {slot.instance_id}/{slot.port_id} is not on a requested protocol-core front",
            )
    if require_all_core_raw_outputs:
        inactive_core_outputs = [
            f"{slot.instance_id}/{slot.port_id}"
            for slot in bound_slots
            if slot.kind == "output"
            and bound_by_id[slot.instance_id]["template"] == "protocol_core"
            and bound_by_id[slot.instance_id]["port_bindings"][slot.port_id] is None
        ]
        if inactive_core_outputs:
            _fail(
                "CORE_RAW_OUTPUT_INACTIVE",
                f"all protocol-core outputs must carry raw commodities; inactive={inactive_core_outputs}",
            )

    return {
        "required_placements": [bound_by_id[instance_id] for instance_id in sorted(required_ids)],
        "optional_placements": [bound_by_id[instance_id] for instance_id in sorted(optional_ids)],
    }


def _port_slots(
    instance: Mapping[str, object],
    placements: Iterable[Mapping[str, object]],
) -> list[_PortSlot]:
    slots: list[_PortSlot] = []
    for placement in placements:
        base = _placement_base(placement)
        mode = _mode(instance, base["template"], base["mode"])
        ports = _ports_by_id(mode, context=f"{base['template']}/{base['mode']}")
        anchor_x = cast(int, base["anchor"]["x"])
        anchor_y = cast(int, base["anchor"]["y"])
        for port_id, port in ports.items():
            body_cell = _mapping(port["body_cell"], f"port {port_id}.body_cell")
            direction = cast(Direction, port["direction"])
            dx, dy = _DELTA[direction]
            access = (
                anchor_x + _integer(body_cell.get("x"), f"port {port_id}.body_cell.x") + dx,
                anchor_y + _integer(body_cell.get("y"), f"port {port_id}.body_cell.y") + dy,
            )
            slots.append(
                _PortSlot(
                    instance_id=base["instance_id"],
                    port_id=port_id,
                    kind=cast(Literal["input", "output"], port["kind"]),
                    direction=direction,
                    access=access,
                )
            )
    return slots


def _cell_set(value: Iterable[Cell] | None, name: str) -> frozenset[Cell] | None:
    if value is None:
        return None
    cells: set[Cell] = set()
    for index, raw_cell in enumerate(value):
        if not isinstance(raw_cell, (tuple, list)) or len(raw_cell) != 2:
            _fail("MALFORMED_ACCESS_SET", f"{name}[{index}] must be an (x, y) pair")
        x, y = raw_cell
        if type(x) is not int or type(y) is not int:
            _fail("MALFORMED_ACCESS_SET", f"{name}[{index}] coordinates must be integers")
        cells.add((x, y))
    return frozenset(cells)


def _slot_sort_key(slot: _PortSlot) -> tuple[str, str, int, int, int]:
    """Stable lexicographic physical-port order used by automatic binding."""

    return (
        slot.instance_id,
        slot.port_id,
        slot.access[0],
        slot.access[1],
        _DIRECTION_RANK[slot.direction],
    )


def _expanded_needs(value: object, name: str) -> list[str]:
    needs = _required_count_map(value, name)
    return [commodity for commodity, count in needs.items() for _ in range(count)]


def choose_port_bindings(
    instance: Mapping[str, object],
    *,
    required_placements: Sequence[Mapping[str, object]],
    optional_placements: Sequence[Mapping[str, object]] = (),
    allowed_access_cells: Iterable[Cell] | None = None,
    core_final_input_access_cells: Iterable[Cell] | None = None,
    require_all_core_raw_outputs: bool = True,
) -> dict[str, dict[str, str]]:
    """Choose exact bindings deterministically from allowed physical fronts.

    Ports are selected lexicographically by ``(instance_id, port_id, access)``.
    Manufacturing needs are fulfilled independently for every instance.  Raw
    generic outputs are allocated globally, with every protocol-core output
    forced active by default.  When ``core_final_input_access_cells`` is given,
    every final input is placed on the protocol core and on that requested set;
    this intentionally conflicts with selecting a storage box, which must carry
    at least one final input.
    """

    required_records = [
        _mapping(value, "required placement")
        for value in _sequence(required_placements, "required_placements")
    ]
    optional_records = [
        _mapping(value, "optional placement")
        for value in _sequence(optional_placements, "optional_placements")
    ]
    placements = [*required_records, *optional_records]
    bases = [_placement_base(placement) for placement in placements]
    ids = [cast(str, base["instance_id"]) for base in bases]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_PLACEMENT", "automatic binding received duplicate instance IDs")
    template_by_id = {cast(str, base["instance_id"]): cast(str, base["template"]) for base in bases}
    allowed = _cell_set(allowed_access_cells, "allowed_access_cells")
    requested_core_final = _cell_set(core_final_input_access_cells, "core_final_input_access_cells")
    all_slots = _port_slots(instance, placements)
    eligible_slots = [slot for slot in all_slots if allowed is None or slot.access in allowed]
    slots_by_instance_kind: defaultdict[tuple[str, str], list[_PortSlot]] = defaultdict(list)
    for slot in eligible_slots:
        slots_by_instance_kind[(slot.instance_id, slot.kind)].append(slot)
    for slots in slots_by_instance_kind.values():
        slots.sort(key=_slot_sort_key)

    selected: defaultdict[str, dict[str, str]] = defaultdict(dict)
    manufacturing_ids: set[str] = set()
    for raw_group in _sequence(instance.get("operation_groups"), "instance.operation_groups"):
        group = _mapping(raw_group, "operation group")
        group_id = _string(group.get("id"), "operation group.id")
        needs = _mapping(group.get("port_needs"), f"operation group {group_id}.port_needs")
        input_needs = _expanded_needs(needs.get("inputs"), f"{group_id}.inputs")
        output_needs = _expanded_needs(needs.get("outputs"), f"{group_id}.outputs")
        for raw_instance_id in _sequence(group.get("instance_ids"), f"{group_id}.instance_ids"):
            instance_id = _string(raw_instance_id, f"{group_id} instance")
            manufacturing_ids.add(instance_id)
            for kind, commodities in (("input", input_needs), ("output", output_needs)):
                candidates = slots_by_instance_kind.get((instance_id, kind), [])
                if len(candidates) < len(commodities):
                    _fail(
                        "AUTO_BINDING_INFEASIBLE",
                        f"{instance_id} has {len(candidates)} allowed {kind} ports for {len(commodities)} needs",
                    )
                for slot, commodity in zip(candidates, commodities, strict=False):
                    selected[instance_id][slot.port_id] = commodity

    generic = _mapping(instance.get("generic_requirements"), "instance.generic_requirements")
    raw_providers = {
        _string(value, "raw output provider")
        for value in _sequence(generic.get("raw_output_providers"), "generic raw_output_providers")
    }
    final_providers = {
        _string(value, "final input provider")
        for value in _sequence(generic.get("final_input_providers"), "generic final_input_providers")
    }
    raw_needs = _expanded_needs(generic.get("raw_outputs"), "generic raw outputs")
    final_needs = _expanded_needs(generic.get("final_inputs"), "generic final inputs")

    eligible_raw = sorted(
        (
            slot
            for slot in eligible_slots
            if slot.instance_id not in manufacturing_ids
            and slot.kind == "output"
            and template_by_id.get(slot.instance_id) in raw_providers
        ),
        key=_slot_sort_key,
    )
    all_core_outputs = sorted(
        (
            slot
            for slot in all_slots
            if slot.kind == "output" and template_by_id.get(slot.instance_id) == "protocol_core"
        ),
        key=_slot_sort_key,
    )
    mandatory_raw = all_core_outputs if require_all_core_raw_outputs else []
    if any(slot not in eligible_raw for slot in mandatory_raw):
        _fail("AUTO_BINDING_INFEASIBLE", "allowed access set excludes a required protocol-core raw output")
    if len(mandatory_raw) > len(raw_needs):
        _fail("AUTO_BINDING_INFEASIBLE", "raw demand cannot activate every protocol-core output")
    chosen_raw = list(mandatory_raw)
    chosen_raw_ids = {(slot.instance_id, slot.port_id) for slot in chosen_raw}
    for slot in eligible_raw:
        if len(chosen_raw) == len(raw_needs):
            break
        if (slot.instance_id, slot.port_id) not in chosen_raw_ids:
            chosen_raw.append(slot)
            chosen_raw_ids.add((slot.instance_id, slot.port_id))
    if len(chosen_raw) != len(raw_needs):
        _fail(
            "AUTO_BINDING_INFEASIBLE",
            f"only {len(chosen_raw)} allowed raw outputs are available for {len(raw_needs)} needs",
        )
    for slot, commodity in zip(sorted(chosen_raw, key=_slot_sort_key), raw_needs, strict=True):
        selected[slot.instance_id][slot.port_id] = commodity

    eligible_final = sorted(
        (
            slot
            for slot in eligible_slots
            if slot.instance_id not in manufacturing_ids
            and slot.kind == "input"
            and template_by_id.get(slot.instance_id) in final_providers
        ),
        key=_slot_sort_key,
    )
    storage_box_ids = sorted(
        instance_id for instance_id, template_id in template_by_id.items() if template_id == "storage_box"
    )
    if requested_core_final is not None:
        if storage_box_ids:
            _fail(
                "AUTO_BINDING_INFEASIBLE",
                "core-only final-input request cannot leave selected storage boxes empty",
            )
        final_candidates = [
            slot
            for slot in eligible_final
            if template_by_id.get(slot.instance_id) == "protocol_core" and slot.access in requested_core_final
        ]
        if len(final_candidates) < len(final_needs):
            _fail(
                "AUTO_BINDING_INFEASIBLE",
                f"requested core fronts provide {len(final_candidates)} slots for {len(final_needs)} final inputs",
            )
        chosen_final = final_candidates[: len(final_needs)]
    else:
        chosen_final = []
        chosen_final_ids: set[tuple[str, str]] = set()
        for box_id in storage_box_ids:
            box_candidates = [slot for slot in eligible_final if slot.instance_id == box_id]
            if not box_candidates:
                _fail("AUTO_BINDING_INFEASIBLE", f"storage box {box_id} has no allowed final-input port")
            chosen_final.append(box_candidates[0])
            chosen_final_ids.add((box_candidates[0].instance_id, box_candidates[0].port_id))
        if len(chosen_final) > len(final_needs):
            _fail("AUTO_BINDING_INFEASIBLE", "there are more selected storage boxes than final-input needs")
        for slot in eligible_final:
            if len(chosen_final) == len(final_needs):
                break
            if (slot.instance_id, slot.port_id) not in chosen_final_ids:
                chosen_final.append(slot)
                chosen_final_ids.add((slot.instance_id, slot.port_id))
        if len(chosen_final) != len(final_needs):
            _fail(
                "AUTO_BINDING_INFEASIBLE",
                f"only {len(chosen_final)} allowed final inputs are available for {len(final_needs)} needs",
            )
    for slot, commodity in zip(sorted(chosen_final, key=_slot_sort_key), final_needs, strict=True):
        selected[slot.instance_id][slot.port_id] = commodity

    return {instance_id: dict(sorted(bindings.items())) for instance_id, bindings in sorted(selected.items())}


def derive_production_port_specs(
    instance: Mapping[str, object],
    *,
    required_placements: Sequence[Mapping[str, object]],
    optional_placements: Sequence[Mapping[str, object]] = (),
) -> list[dict[str, Any]]:
    """Derive active production port specs using identity front-cell semantics."""

    placements = [
        *(_mapping(value, "required placement") for value in _sequence(required_placements, "required_placements")),
        *(_mapping(value, "optional placement") for value in _sequence(optional_placements, "optional_placements")),
    ]
    slots = _port_slots(instance, placements)
    slots_by_instance_port = {(slot.instance_id, slot.port_id): slot for slot in slots}
    if len(slots_by_instance_port) != len(slots):
        _fail("DUPLICATE_PLACEMENT", "port-slot identity is not unique")

    active_endpoint_owner: dict[tuple[int, int, Direction, str], tuple[str, str]] = {}
    specs: list[dict[str, Any]] = []
    for placement in placements:
        base = _placement_base(placement)
        bindings = _mapping(placement.get("port_bindings"), f"placement {base['instance_id']}.port_bindings")
        mode = _mode(instance, base["template"], base["mode"])
        ports = _ports_by_id(mode, context=f"{base['template']}/{base['mode']}")
        if set(bindings) != set(ports):
            _fail("INCOMPLETE_PORT_MAP", "cannot derive specs from an incomplete port map", pointer=base["instance_id"])
        for port_id in sorted(ports):
            commodity = bindings[port_id]
            if commodity is None:
                continue
            if type(commodity) is not str or commodity not in _instance_commodities(instance):
                _fail("UNKNOWN_COMMODITY", f"invalid active commodity on {port_id}", pointer=base["instance_id"])
            slot = slots_by_instance_port[(base["instance_id"], port_id)]
            production_type = "in" if slot.kind == "input" else "out"
            endpoint = (*slot.access, slot.direction, production_type)
            if endpoint in active_endpoint_owner:
                _fail(
                    "AMBIGUOUS_PORT_ENDPOINT",
                    f"active endpoint {endpoint} belongs to multiple physical ports",
                )
            active_endpoint_owner[endpoint] = (slot.instance_id, slot.port_id)
            specs.append(
                {
                    "instance_id": slot.instance_id,
                    # Identity contract: x/y is already the access/front cell.
                    "x": slot.access[0],
                    "y": slot.access[1],
                    "dir": slot.direction,
                    "type": production_type,
                    "commodity": commodity,
                }
            )
    return sorted(
        specs,
        key=lambda spec: (
            spec["instance_id"],
            spec["y"],
            spec["x"],
            _DIRECTION_RANK[cast(Direction, spec["dir"])],
            spec["type"],
            spec["commodity"],
        ),
    )


def backmap_port_specs_to_bindings(
    instance: Mapping[str, object],
    *,
    required_placements: Sequence[Mapping[str, object]],
    optional_placements: Sequence[Mapping[str, object]] = (),
    port_specs: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, str]]:
    """Map production specs to strict port IDs by ``(access, direction, kind)``."""

    placements = [
        *(_mapping(value, "required placement") for value in _sequence(required_placements, "required_placements")),
        *(_mapping(value, "optional placement") for value in _sequence(optional_placements, "optional_placements")),
    ]
    slots_by_endpoint: defaultdict[tuple[int, int, Direction, str], list[_PortSlot]] = defaultdict(list)
    for slot in _port_slots(instance, placements):
        production_type = "in" if slot.kind == "input" else "out"
        slots_by_endpoint[(*slot.access, slot.direction, production_type)].append(slot)

    selected: defaultdict[str, dict[str, str]] = defaultdict(dict)
    required_fields = {"instance_id", "x", "y", "dir", "type", "commodity"}
    for index, raw_spec in enumerate(_sequence(port_specs, "port_specs")):
        spec = _mapping(raw_spec, f"port_specs[{index}]")
        if set(spec) != required_fields:
            _fail("MALFORMED_PORT_SPEC", f"port_specs[{index}] fields differ from {sorted(required_fields)}")
        instance_id = _string(spec.get("instance_id"), f"port_specs[{index}].instance_id")
        x = _integer(spec.get("x"), f"port_specs[{index}].x")
        y = _integer(spec.get("y"), f"port_specs[{index}].y")
        direction = spec.get("dir")
        production_type = spec.get("type")
        commodity = _string(spec.get("commodity"), f"port_specs[{index}].commodity")
        if direction not in _DIRECTION_SET or production_type not in ("in", "out"):
            _fail("MALFORMED_PORT_SPEC", f"port_specs[{index}] has invalid direction/type")
        if commodity not in _instance_commodities(instance):
            _fail("UNKNOWN_COMMODITY", f"port_specs[{index}] references {commodity!r}")
        endpoint = (x, y, cast(Direction, direction), cast(str, production_type))
        matches = slots_by_endpoint.get(endpoint, [])
        if not matches:
            _fail(
                "PORT_SPEC_NO_MATCH",
                f"port_specs[{index}] does not match a strict access/direction/kind endpoint",
            )
        if len(matches) != 1:
            owners = sorted((slot.instance_id, slot.port_id) for slot in matches)
            _fail("AMBIGUOUS_PORT_ENDPOINT", f"port_specs[{index}] matches multiple physical ports {owners}")
        slot = matches[0]
        if slot.instance_id != instance_id:
            _fail(
                "PORT_SPEC_INSTANCE_MISMATCH",
                f"port_specs[{index}] names {instance_id!r} but endpoint belongs to {slot.instance_id!r}",
            )
        if slot.port_id in selected[instance_id]:
            _fail("DUPLICATE_PORT_SPEC", f"port_specs[{index}] selects {instance_id}/{slot.port_id} twice")
        selected[instance_id][slot.port_id] = commodity
    return {instance_id: dict(sorted(bindings.items())) for instance_id, bindings in sorted(selected.items())}


def bind_placements_from_port_specs(
    instance: Mapping[str, object],
    *,
    required_placements: Sequence[Mapping[str, object]],
    optional_placements: Sequence[Mapping[str, object]] = (),
    port_specs: Sequence[Mapping[str, object]],
) -> BoundPlacementSet:
    """Back-map production specs and enforce the complete strict binding contract."""

    selected = backmap_port_specs_to_bindings(
        instance,
        required_placements=required_placements,
        optional_placements=optional_placements,
        port_specs=port_specs,
    )
    return bind_placements(
        instance,
        required_placements=required_placements,
        optional_placements=optional_placements,
        selected_port_bindings=selected,
    )


def _json_copy(value: object, *, name: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        _fail("NON_JSON_VALUE", f"{name} is not strict JSON data: {exc}")


def _canonical_placement(placement: Mapping[str, object]) -> dict[str, Any]:
    base = _placement_base(placement)
    bindings = _mapping(placement.get("port_bindings"), f"placement {base['instance_id']}.port_bindings")
    normalized_bindings: dict[str, str | None] = {}
    for raw_port_id, commodity in sorted(bindings.items()):
        port_id = _string(raw_port_id, "port binding ID")
        if commodity is not None and (type(commodity) is not str or not commodity):
            _fail("MALFORMED_BINDING", f"invalid value for {base['instance_id']}/{port_id}")
        normalized_bindings[port_id] = cast(str | None, commodity)
    return {**base, "port_bindings": normalized_bindings}


def _canonical_directions(value: object, name: str) -> list[Direction]:
    directions = _sequence(value, name)
    if any(direction not in _DIRECTION_SET for direction in directions):
        _fail("MALFORMED_ROUTE_COMPONENT", f"{name} contains an invalid direction")
    normalized = [cast(Direction, direction) for direction in directions]
    if len(normalized) != len(set(normalized)):
        _fail("MALFORMED_ROUTE_COMPONENT", f"{name} contains duplicate directions")
    return sorted(normalized, key=_DIRECTION_RANK.__getitem__)


def _canonical_commodities(value: object, name: str) -> list[str]:
    commodities = [_string(item, name) for item in _sequence(value, name)]
    if not commodities or len(commodities) != len(set(commodities)):
        _fail("MALFORMED_ROUTE_COMPONENT", f"{name} must be nonempty and unique")
    return sorted(commodities)


def _canonical_channel(channel: Mapping[str, object]) -> dict[str, Any]:
    return {
        "inputs": _canonical_directions(channel.get("inputs"), "channel.inputs"),
        "outputs": _canonical_directions(channel.get("outputs"), "channel.outputs"),
        "commodities": _canonical_commodities(channel.get("commodities"), "channel.commodities"),
    }


def _channel_axis(channel: Mapping[str, object]) -> int:
    directions = set(cast(Sequence[str], channel["inputs"])) | set(cast(Sequence[str], channel["outputs"]))
    if directions == {"E", "W"}:
        return 0
    if directions == {"N", "S"}:
        return 1
    return 2


def _canonical_route(component: Mapping[str, object]) -> dict[str, Any]:
    cell = _mapping(component.get("cell"), "route component.cell")
    normalized_cell = {
        "x": _integer(cell.get("x"), "route component.cell.x"),
        "y": _integer(cell.get("y"), "route component.cell.y"),
    }
    kind = _string(component.get("kind"), "route component.kind")
    if kind == "cross":
        channels = [
            _canonical_channel(_mapping(value, "cross channel"))
            for value in _sequence(component.get("channels"), "cross channels")
        ]
        channels.sort(key=lambda channel: (_channel_axis(channel), json.dumps(channel, sort_keys=True)))
        return {"cell": normalized_cell, "kind": "cross", "channels": channels}
    if kind not in ("straight", "turn", "splitter", "merger"):
        _fail("MALFORMED_ROUTE_COMPONENT", f"unknown route component kind {kind!r}")
    return {
        "cell": normalized_cell,
        "kind": kind,
        "inputs": _canonical_directions(component.get("inputs"), "component.inputs"),
        "outputs": _canonical_directions(component.get("outputs"), "component.outputs"),
        "commodities": _canonical_commodities(component.get("commodities"), "component.commodities"),
    }


def assemble_strict_witness(
    *,
    instance_payload: bytes,
    required_placements: Sequence[Mapping[str, object]],
    optional_placements: Sequence[Mapping[str, object]],
    route_components: Sequence[Mapping[str, object]],
    claimed_objective: Mapping[str, object],
) -> dict[str, Any]:
    """Assemble a deterministic strict witness and digest the exact instance bytes."""

    if type(instance_payload) is not bytes:
        _fail("MALFORMED_INSTANCE_PAYLOAD", "instance_payload must be exact bytes")
    required = sorted(
        (_canonical_placement(_mapping(value, "required placement")) for value in required_placements),
        key=lambda placement: placement["instance_id"],
    )
    optional = sorted(
        (_canonical_placement(_mapping(value, "optional placement")) for value in optional_placements),
        key=lambda placement: placement["instance_id"],
    )
    all_ids = [placement["instance_id"] for placement in (*required, *optional)]
    if len(all_ids) != len(set(all_ids)):
        _fail("DUPLICATE_PLACEMENT", "witness placements contain duplicate instance IDs")
    routes = [_canonical_route(_mapping(value, "route component")) for value in route_components]
    route_cells = [(route["cell"]["x"], route["cell"]["y"]) for route in routes]
    if len(route_cells) != len(set(route_cells)):
        _fail("DUPLICATE_ROUTE_CELL", "more than one strict route component occupies a cell")
    routes.sort(key=lambda route: (route["cell"]["y"], route["cell"]["x"]))
    objective = _json_copy(claimed_objective, name="claimed_objective")
    if not isinstance(objective, dict):
        _fail("MALFORMED_OBJECTIVE", "claimed_objective must be an object")
    return {
        "schema_version": 1,
        "instance_digest": "sha256:" + hashlib.sha256(instance_payload).hexdigest(),
        "required_placements": required,
        "optional_placements": optional,
        "route_components": routes,
        "claimed_objective": objective,
    }


def canonical_json_bytes(value: object) -> bytes:
    """Encode strict JSON deterministically, with one trailing LF."""

    try:
        rendered = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        _fail("NON_JSON_VALUE", f"value cannot be encoded as strict JSON: {exc}")
    return (rendered + "\n").encode("ascii")


def _decode_capture(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _strict_json_object(payload: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value}")

    parsed = json.loads(payload, object_pairs_hook=reject_duplicate_keys, parse_constant=reject_constant)
    if not isinstance(parsed, dict):
        raise ValueError("checker report must be an object")
    return parsed


def _checker_report_schema_valid(report: Mapping[str, object]) -> bool:
    status = report.get("status")
    if type(status) is not str or status not in _CHECKER_EXIT_BY_STATUS:
        return False
    expected_keys = {"status", "categories", "errors"}
    if "recomputed_objective" in report:
        expected_keys.add("recomputed_objective")
    if set(report) != expected_keys or report.get("categories") != _EXPECTED_CHECKER_CATEGORIES:
        return False
    errors = report.get("errors")
    if not isinstance(errors, list):
        return False
    for error in errors:
        if not isinstance(error, Mapping) or set(error) != {"category", "pointer", "message"}:
            return False
        if (
            type(error.get("category")) is not str
            or error.get("category") not in _EXPECTED_CHECKER_CATEGORIES
            or type(error.get("pointer")) is not str
            or type(error.get("message")) is not str
        ):
            return False
    objective = report.get("recomputed_objective")
    if status == "LAYOUT_FEASIBLE" and not isinstance(objective, Mapping):
        return False
    if objective is not None:
        required = {"x", "y", "width", "height", "area", "min_side"}
        if not isinstance(objective, Mapping) or set(objective) != required:
            return False
        if any(type(objective.get(field)) is not int for field in required):
            return False
        x = cast(int, objective["x"])
        y = cast(int, objective["y"])
        width = cast(int, objective["width"])
        height = cast(int, objective["height"])
        area = cast(int, objective["area"])
        min_side = cast(int, objective["min_side"])
        if x < 0 or y < 0 or width < 1 or height < 1:
            return False
        if area != width * height or min_side != min(width, height):
            return False
    return True


def _checker_snapshot_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_checker_snapshot(path: Path) -> _CheckerSnapshot:
    """Read checker bytes once from one descriptor, rejecting in-read drift."""

    source = Path(path)
    try:
        descriptor = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        _fail("CHECKER_INTEGRITY_ERROR", f"cannot open checker {source}: {exc}")
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            _fail("CHECKER_INTEGRITY_ERROR", f"checker is not a regular file: {source}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        _fail("CHECKER_INTEGRITY_ERROR", f"cannot read checker {source}: {exc}")
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    before_identity = _checker_snapshot_identity(before)
    if before_identity != _checker_snapshot_identity(after) or len(payload) != before.st_size:
        _fail("CHECKER_INTEGRITY_ERROR", f"checker changed while it was read: {source}")
    return _CheckerSnapshot(
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        source_identity=before_identity,
    )


def run_independent_checker(
    instance_path: Path,
    witness_path: Path,
    *,
    checker_path: Path | None = None,
    python_executable: Path | None = None,
    timeout_seconds: float = 60.0,
) -> CheckerProcessResult:
    """Invoke the existing strict checker as an isolated subprocess.

    Acceptance additionally pins the repository checker path and exact bytes,
    requires its complete report schema/objective, and rejects checker stderr.
    All process, JSON, schema, and exit/status mismatches receive explicit
    fail-closed classifications.  An injected checker may be exercised by unit
    tests, but its result can never set :attr:`CheckerProcessResult.accepted`.
    """

    if timeout_seconds <= 0:
        _fail("INVALID_CHECKER_TIMEOUT", "timeout_seconds must be positive")
    expected_checker = EXPECTED_CHECKER_PATH
    checker = (checker_path or expected_checker).resolve()
    interpreter = (python_executable or Path(sys.executable)).resolve()
    try:
        checker_snapshot = _read_checker_snapshot(checker)
    except WitnessIOError as exc:
        return CheckerProcessResult(
            classification=exc.code,
            exit_code=None,
            status=None,
            report=None,
            stdout="",
            stderr=str(exc),
            checker_source_path=str(checker),
            checker_python_executable=str(interpreter),
            checker_execution_mode=PINNED_CHECKER_EXECUTION_MODE,
        )
    result_identity = {
        "checker_sha256": checker_snapshot.sha256,
        "checker_source_path": str(checker),
        "checker_source_identity": checker_snapshot.source_identity,
        "checker_snapshot_size_bytes": checker_snapshot.size_bytes,
        "checker_python_executable": str(interpreter),
        "checker_execution_mode": PINNED_CHECKER_EXECUTION_MODE,
    }
    checker_trusted = (
        checker == expected_checker
        and checker_snapshot.sha256 == EXPECTED_CHECKER_SHA256
        and interpreter == Path(sys.executable).resolve()
    )
    if checker_path is None and not checker_trusted:
        return CheckerProcessResult(
            classification="CHECKER_INTEGRITY_INVALID",
            exit_code=None,
            status=None,
            report=None,
            stdout="",
            stderr=(
                f"strict checker path/hash mismatch: path={checker}, sha256={checker_snapshot.sha256}, "
                f"expected={EXPECTED_CHECKER_SHA256}"
            ),
            checker_trusted=False,
            **result_identity,
        )
    # Isolated mode removes the script working directory and every ``PYTHON*``
    # variable; ``-S`` additionally disables all site-package initialization.
    # A deliberately tiny environment prevents inherited loader/import hooks
    # from becoming a second authority beside the pinned checker bytes.
    snapshot_bootstrap = (
        "import sys\n"
        "_checker_source = sys.stdin.buffer.read()\n"
        "exec(compile(_checker_source, '<pinned-independent-checker>', 'exec'), globals(), globals())\n"
    )
    command = [
        str(interpreter),
        "-I",
        "-S",
        "-c",
        snapshot_bootstrap,
        str(instance_path),
        str(witness_path),
    ]
    checker_environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": os.defpath,
    }
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            input=checker_snapshot.payload,
            timeout=timeout_seconds,
            env=checker_environment,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckerProcessResult(
            classification="CHECKER_TIMEOUT",
            exit_code=None,
            status=None,
            report=None,
            stdout=_decode_capture(exc.stdout),
            stderr=_decode_capture(exc.stderr),
            checker_trusted=checker_trusted,
            **result_identity,
        )
    except OSError as exc:
        return CheckerProcessResult(
            classification="PROCESS_START_ERROR",
            exit_code=None,
            status=None,
            report=None,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
            checker_trusted=checker_trusted,
            **result_identity,
        )

    stdout = _decode_capture(completed.stdout)
    stderr = _decode_capture(completed.stderr)
    try:
        checker_snapshot_after = _read_checker_snapshot(checker)
    except WitnessIOError as exc:
        return CheckerProcessResult(
            classification="CHECKER_INTEGRITY_INVALID",
            exit_code=completed.returncode,
            status=None,
            report=None,
            stdout=stdout,
            stderr=stderr or str(exc),
            checker_trusted=False,
            **result_identity,
        )
    if (
        checker_snapshot_after.sha256 != checker_snapshot.sha256
        or checker_snapshot_after.size_bytes != checker_snapshot.size_bytes
        or checker_snapshot_after.source_identity != checker_snapshot.source_identity
    ):
        return CheckerProcessResult(
            classification="CHECKER_INTEGRITY_INVALID",
            exit_code=completed.returncode,
            status=None,
            report=None,
            stdout=stdout,
            stderr=stderr or "checker source identity changed while the fixed snapshot was running",
            checker_trusted=False,
            **result_identity,
        )
    if completed.returncode < 0:
        return CheckerProcessResult(
            classification="CHECKER_SIGNAL",
            exit_code=completed.returncode,
            status=None,
            report=None,
            stdout=stdout,
            stderr=stderr,
            signal_number=-completed.returncode,
            checker_trusted=checker_trusted,
            **result_identity,
        )
    if completed.returncode not in _CHECKER_EXIT_BY_STATUS.values():
        return CheckerProcessResult(
            classification="PROCESS_NONZERO_EXIT",
            exit_code=completed.returncode,
            status=None,
            report=None,
            stdout=stdout,
            stderr=stderr,
            checker_trusted=checker_trusted,
            **result_identity,
        )
    try:
        report = _strict_json_object(stdout)
    except (json.JSONDecodeError, ValueError, TypeError):
        return CheckerProcessResult(
            classification="RESULT_MISSING_OR_INVALID",
            exit_code=completed.returncode,
            status=None,
            report=None,
            stdout=stdout,
            stderr=stderr,
            checker_trusted=checker_trusted,
            **result_identity,
        )

    status = report.get("status")
    errors = report.get("errors")
    if not _checker_report_schema_valid(report):
        return CheckerProcessResult(
            classification="RESULT_SCHEMA_INVALID",
            exit_code=completed.returncode,
            status=cast(str | None, status if isinstance(status, str) else None),
            report=report,
            stdout=stdout,
            stderr=stderr,
            checker_trusted=checker_trusted,
            **result_identity,
        )
    expected_exit = _CHECKER_EXIT_BY_STATUS.get(cast(str, status))
    if expected_exit is None or completed.returncode != expected_exit:
        return CheckerProcessResult(
            classification="RESULT_INTEGRITY_INVALID",
            exit_code=completed.returncode,
            status=cast(str, status),
            report=report,
            stdout=stdout,
            stderr=stderr,
            checker_trusted=checker_trusted,
            **result_identity,
        )
    if (status == "LAYOUT_FEASIBLE" and errors) or (status != "LAYOUT_FEASIBLE" and not errors):
        return CheckerProcessResult(
            classification="RESULT_INTEGRITY_INVALID",
            exit_code=completed.returncode,
            status=cast(str, status),
            report=report,
            stdout=stdout,
            stderr=stderr,
            checker_trusted=checker_trusted,
            **result_identity,
        )
    return CheckerProcessResult(
        classification=cast(str, status),
        exit_code=completed.returncode,
        status=cast(str, status),
        report=report,
        stdout=stdout,
        stderr=stderr,
        checker_trusted=checker_trusted,
        **result_identity,
    )


__all__ = [
    "BoundPlacementSet",
    "CheckerProcessResult",
    "EXPECTED_CHECKER_PATH",
    "EXPECTED_CHECKER_SHA256",
    "PINNED_CHECKER_EXECUTION_MODE",
    "WitnessIOError",
    "assemble_strict_witness",
    "backmap_port_specs_to_bindings",
    "bind_placements",
    "bind_placements_from_port_specs",
    "canonical_json_bytes",
    "choose_port_bindings",
    "complete_port_bindings",
    "derive_production_port_specs",
    "run_independent_checker",
]

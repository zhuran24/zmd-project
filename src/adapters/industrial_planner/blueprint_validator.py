"""Pure-Python offline validator for IndustrialPlanner blueprint exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.adapters.industrial_planner.mapping_registry import INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA

_REGISTRY_DIR = Path(__file__).resolve().parent
_DEVICE_REGISTRY_PATH = _REGISTRY_DIR / "device_type_registry.json"
_BASE_REGISTRY_PATH = _REGISTRY_DIR / "base_registry.json"
_ITEM_REGISTRY_PATH = _REGISTRY_DIR / "item_registry.json"

_VALID_ROTATIONS = {0, 90, 180, 270}
_OPPOSITE_EDGE = {"N": "S", "S": "N", "E": "W", "W": "E"}
_EDGE_DELTA = {
    "N": (0, -1),
    "S": (0, 1),
    "W": (-1, 0),
    "E": (1, 0),
}
_LOADER_TYPE_IDS = {
    "item_port_loader_1",
    "item_port_unloader_1",
    "item_port_udpipe_loader_1",
    "item_port_udpipe_unloader_1",
}


@dataclass(frozen=True)
class DevicePlacement:
    instance_id: str
    type_id: str
    origin_x: int
    origin_y: int
    rotation: int
    config: dict[str, Any] = field(default_factory=dict)
    is_foundation: bool = False


@dataclass(frozen=True)
class RotatedPort:
    instance_id: str
    type_id: str
    port_id: str
    direction: str
    edge: str
    x: int
    y: int
    allowed_items: Mapping[str, Any]
    allowed_types: Mapping[str, Any]


@dataclass(frozen=True)
class StaticRegistries:
    device_types_by_id: dict[str, dict[str, Any]]
    base_by_id: dict[str, dict[str, Any]]
    item_ids: frozenset[str]
    solid_item_ids: frozenset[str]
    liquid_item_ids: frozenset[str]
    recipe_input_item_ids: frozenset[str]
    recipe_output_item_ids: frozenset[str]
    belt_type_ids: frozenset[str]
    pipe_type_ids: frozenset[str]
    junction_type_ids: frozenset[str]
    pipe_junction_type_ids: frozenset[str]
    hidden_placeable_type_ids: frozenset[str]
    warehouse_bus_type_ids: frozenset[str]


@dataclass
class ValidationReport:
    is_import_compatible: bool
    is_layout_healthy: bool
    is_clean: bool

    schema_errors: list[str]
    registry_errors: list[str]
    lot_boundary_errors: list[str]
    placement_constraint_errors: list[str]
    unsupported_rule_errors: list[str]

    overlap_errors: list[str]
    port_mismatch_errors: list[str]
    port_warnings: list[str]

    device_count: int
    foundation_device_count: int
    cell_coverage: int
    lot_utilization_percent: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lot_utilization_percent"] = round(float(payload["lot_utilization_percent"]), 6)
        return payload

    def to_markdown(self) -> str:
        sections = [
            ("Schema / registry normalization", self.schema_errors + self.registry_errors),
            ("Lot boundary", self.lot_boundary_errors),
            ("Placement constraints", self.placement_constraint_errors + self.unsupported_rule_errors),
            ("Overlap", self.overlap_errors),
            ("Port audit", self.port_mismatch_errors),
        ]

        lines = [
            "# IndustrialPlanner Validation Report",
            "",
            f"- Import compatible: {'yes' if self.is_import_compatible else 'no'}",
            f"- Layout healthy: {'yes' if self.is_layout_healthy else 'no'}",
            f"- Clean export: {'yes' if self.is_clean else 'no'}",
            f"- User devices: {self.device_count}",
            f"- Foundation devices: {self.foundation_device_count}",
            f"- Occupied cells: {self.cell_coverage}",
            f"- Lot utilization: {round(self.lot_utilization_percent, 3)}%",
            "",
        ]
        for heading, messages in sections:
            lines.append(f"## {heading}")
            if messages:
                lines.extend(f"- {message}" for message in messages)
            else:
                lines.append("- none")
            lines.append("")
        lines.append("## Port warnings")
        if self.port_warnings:
            lines.extend(f"- {message}" for message in self.port_warnings)
        else:
            lines.append("- none")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"


@lru_cache(maxsize=4)
def load_static_registries(registry_dir: str | None = None) -> StaticRegistries:
    base_dir = Path(registry_dir) if registry_dir is not None else _REGISTRY_DIR
    device_payload = json.loads((base_dir / _DEVICE_REGISTRY_PATH.name).read_text(encoding="utf-8"))
    base_payload = json.loads((base_dir / _BASE_REGISTRY_PATH.name).read_text(encoding="utf-8"))
    item_payload = json.loads((base_dir / _ITEM_REGISTRY_PATH.name).read_text(encoding="utf-8"))

    device_types = {
        str(entry.get("id", "")).strip(): dict(entry)
        for entry in device_payload.get("device_types", [])
        if isinstance(entry, Mapping) and str(entry.get("id", "")).strip()
    }
    bases = {
        str(entry.get("id", "")).strip(): dict(entry)
        for entry in base_payload.get("bases", [])
        if isinstance(entry, Mapping) and str(entry.get("id", "")).strip()
    }
    item_ids = frozenset(
        str(entry.get("id", "")).strip()
        for entry in item_payload.get("items", [])
        if isinstance(entry, Mapping) and str(entry.get("id", "")).strip()
    )
    return StaticRegistries(
        device_types_by_id=device_types,
        base_by_id=bases,
        item_ids=item_ids,
        solid_item_ids=frozenset(str(value) for value in item_payload.get("solid_item_ids", [])),
        liquid_item_ids=frozenset(str(value) for value in item_payload.get("liquid_item_ids", [])),
        recipe_input_item_ids=frozenset(str(value) for value in item_payload.get("recipe_input_item_ids", [])),
        recipe_output_item_ids=frozenset(str(value) for value in item_payload.get("recipe_output_item_ids", [])),
        belt_type_ids=frozenset(str(value) for value in device_payload.get("belt_type_ids", [])),
        pipe_type_ids=frozenset(str(value) for value in device_payload.get("pipe_type_ids", [])),
        junction_type_ids=frozenset(str(value) for value in device_payload.get("junction_type_ids", [])),
        pipe_junction_type_ids=frozenset(str(value) for value in device_payload.get("pipe_junction_type_ids", [])),
        hidden_placeable_type_ids=frozenset(str(value) for value in device_payload.get("hidden_placeable_type_ids", [])),
        warehouse_bus_type_ids=frozenset(str(value) for value in device_payload.get("warehouse_bus_type_ids", [])),
    )


def validate_industrial_planner_blueprint(
    blueprint_payload: Mapping[str, Any],
    *,
    registry_dir: Path | None = None,
) -> ValidationReport:
    registries = load_static_registries(str(registry_dir) if registry_dir is not None else None)

    schema_errors: list[str] = []
    registry_errors: list[str] = []
    lot_boundary_errors: list[str] = []
    placement_constraint_errors: list[str] = []
    unsupported_rule_errors: list[str] = []
    overlap_errors: list[str] = []
    port_mismatch_errors: list[str] = []
    port_warnings: list[str] = []

    if not isinstance(blueprint_payload, Mapping):
        schema_errors.append("blueprint payload must be a mapping")
        return _finalize_report(
            schema_errors=schema_errors,
            registry_errors=registry_errors,
            lot_boundary_errors=lot_boundary_errors,
            placement_constraint_errors=placement_constraint_errors,
            unsupported_rule_errors=unsupported_rule_errors,
            overlap_errors=overlap_errors,
            port_mismatch_errors=port_mismatch_errors,
            port_warnings=port_warnings,
            device_count=0,
            foundation_device_count=0,
            cell_coverage=0,
            lot_utilization_percent=0.0,
        )

    schema = str(blueprint_payload.get("schema", "")).strip()
    if schema != INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA:
        schema_errors.append(
            f"unsupported schema {schema!r}; expected {INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA!r}"
        )

    base_id = str(blueprint_payload.get("baseId", "")).strip()
    base_def = registries.base_by_id.get(base_id)
    if base_def is None:
        registry_errors.append(f"unknown baseId {base_id!r}")

    raw_devices = blueprint_payload.get("devices")
    if not isinstance(raw_devices, list):
        schema_errors.append("blueprint.devices must be a list")
        raw_devices = []

    normalized_user_devices: list[DevicePlacement] = []
    device_count = len(raw_devices)

    for index, raw_device in enumerate(raw_devices):
        normalized_device = _normalize_user_device(
            raw_device,
            index=index,
            registries=registries,
            schema_errors=schema_errors,
            registry_errors=registry_errors,
        )
        if normalized_device is not None:
            normalized_user_devices.append(normalized_device)

    if base_def is not None:
        foundation_devices = _inject_foundation_devices(base_def)
    else:
        foundation_devices = []

    if base_def is not None:
        for device in normalized_user_devices:
            if not _is_device_within_allowed_placement_area(device, base_def, registries):
                lot_boundary_errors.append(
                    f"device {device.instance_id} ({device.type_id}) extends outside the allowed placement lot for base {base_id}"
                )

    working_devices = [*foundation_devices, *normalized_user_devices]

    occupancy_map = _build_occupancy_map(working_devices, registries)

    if base_def is not None:
        device_by_id = {entry.instance_id: entry for entry in working_devices}
        for device in working_devices:
            for rule in _device_placement_constraints(device.type_id, registries):
                kind = str(rule.get("kind", "")).strip()
                if kind != "edge_contact":
                    unsupported_rule_errors.append(
                        f"device {device.instance_id} ({device.type_id}) uses unsupported placement rule kind {kind!r}"
                    )
                    continue
                if not _check_edge_contact_rule(occupancy_map, device_by_id, device, rule, registries):
                    port_id = str(rule.get("portId", "")).strip() or "<default-port>"
                    target_tags = ",".join(str(tag) for tag in rule.get("targetTagsAny", []) if str(tag))
                    target_types = ",".join(str(value) for value in rule.get("targetTypeIds", []) if str(value))
                    target_desc = target_tags or target_types or "compatible neighbor"
                    placement_constraint_errors.append(
                        f"device {device.instance_id} ({device.type_id}) failed edge_contact rule on port {port_id}; required adjacency to {target_desc}"
                    )
    overlap_errors.extend(_detect_overlap_errors(occupancy_map, registries))
    port_mismatch_errors.extend(_detect_port_mismatch_errors(working_devices, registries))
    port_warnings.extend(_detect_port_warnings(working_devices, registries))

    lot_utilization_percent = 0.0
    if base_def is not None and int(base_def.get("placeableSize", 0)) > 0:
        lot_size = int(base_def.get("placeableSize", 0))
        occupied_in_lot = 0
        for key in occupancy_map:
            x_text, y_text = key.split(",", 1)
            x = int(x_text)
            y = int(y_text)
            if 0 <= x < lot_size and 0 <= y < lot_size:
                occupied_in_lot += 1
        lot_utilization_percent = (occupied_in_lot / float(lot_size * lot_size)) * 100.0

    return _finalize_report(
        schema_errors=schema_errors,
        registry_errors=registry_errors,
        lot_boundary_errors=lot_boundary_errors,
        placement_constraint_errors=placement_constraint_errors,
        unsupported_rule_errors=unsupported_rule_errors,
        overlap_errors=overlap_errors,
        port_mismatch_errors=port_mismatch_errors,
        port_warnings=port_warnings,
        device_count=device_count,
        foundation_device_count=len(foundation_devices),
        cell_coverage=len(occupancy_map),
        lot_utilization_percent=lot_utilization_percent,
    )


def write_validation_reports(
    report: ValidationReport,
    *,
    json_output_path: Path | None = None,
    markdown_output_path: Path | None = None,
) -> None:
    if json_output_path is not None:
        json_output_path = Path(json_output_path)
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if markdown_output_path is not None:
        markdown_output_path = Path(markdown_output_path)
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(report.to_markdown(), encoding="utf-8")


def validate_industrial_planner_blueprint_file(
    blueprint_path: Path,
    *,
    registry_dir: Path | None = None,
) -> ValidationReport:
    payload = json.loads(Path(blueprint_path).read_text(encoding="utf-8"))
    return validate_industrial_planner_blueprint(payload, registry_dir=registry_dir)


def _finalize_report(
    *,
    schema_errors: list[str],
    registry_errors: list[str],
    lot_boundary_errors: list[str],
    placement_constraint_errors: list[str],
    unsupported_rule_errors: list[str],
    overlap_errors: list[str],
    port_mismatch_errors: list[str],
    port_warnings: list[str],
    device_count: int,
    foundation_device_count: int,
    cell_coverage: int,
    lot_utilization_percent: float,
) -> ValidationReport:
    schema_errors = sorted(set(schema_errors))
    registry_errors = sorted(set(registry_errors))
    lot_boundary_errors = sorted(set(lot_boundary_errors))
    placement_constraint_errors = sorted(set(placement_constraint_errors))
    unsupported_rule_errors = sorted(set(unsupported_rule_errors))
    overlap_errors = sorted(set(overlap_errors))
    port_mismatch_errors = sorted(set(port_mismatch_errors))
    port_warnings = sorted(set(port_warnings))

    is_import_compatible = not any(
        (
            schema_errors,
            registry_errors,
            lot_boundary_errors,
            placement_constraint_errors,
            unsupported_rule_errors,
        )
    )
    is_layout_healthy = not any((overlap_errors, port_mismatch_errors))
    is_clean = is_import_compatible and is_layout_healthy and not port_warnings
    return ValidationReport(
        is_import_compatible=is_import_compatible,
        is_layout_healthy=is_layout_healthy,
        is_clean=is_clean,
        schema_errors=schema_errors,
        registry_errors=registry_errors,
        lot_boundary_errors=lot_boundary_errors,
        placement_constraint_errors=placement_constraint_errors,
        unsupported_rule_errors=unsupported_rule_errors,
        overlap_errors=overlap_errors,
        port_mismatch_errors=port_mismatch_errors,
        port_warnings=port_warnings,
        device_count=int(device_count),
        foundation_device_count=int(foundation_device_count),
        cell_coverage=int(cell_coverage),
        lot_utilization_percent=float(lot_utilization_percent),
    )


def _normalize_user_device(
    raw_device: Any,
    *,
    index: int,
    registries: StaticRegistries,
    schema_errors: list[str],
    registry_errors: list[str],
) -> DevicePlacement | None:
    if not isinstance(raw_device, Mapping):
        schema_errors.append(f"device[{index}] must be a mapping")
        return None

    type_id = str(raw_device.get("typeId", "")).strip()
    if not type_id:
        schema_errors.append(f"device[{index}] is missing typeId")
        return None
    if type_id not in registries.device_types_by_id:
        registry_errors.append(f"device[{index}] uses unknown typeId {type_id!r}")
        return None

    rotation = raw_device.get("rotation")
    if not _is_finite_integer(rotation) or int(rotation) not in _VALID_ROTATIONS:
        schema_errors.append(
            f"device[{index}] has illegal rotation {rotation!r}; expected one of {sorted(_VALID_ROTATIONS)}"
        )
        return None

    origin = raw_device.get("origin")
    if not isinstance(origin, Mapping):
        schema_errors.append(f"device[{index}] origin must be a mapping")
        return None

    x = origin.get("x")
    y = origin.get("y")
    if not _is_finite_integer(x) or not _is_finite_integer(y):
        schema_errors.append(f"device[{index}] origin coordinates must be finite integers")
        return None

    config = raw_device.get("config")
    if config is None:
        config = {}
    if not isinstance(config, Mapping):
        schema_errors.append(f"device[{index}] config must be a mapping when present")
        config = {}

    for item_path, item_id in _iter_config_item_ids(config):
        if str(item_id) not in registries.item_ids:
            registry_errors.append(
                f"device[{index}] config field {item_path} references unknown item id {item_id!r}"
            )

    return DevicePlacement(
        instance_id=f"user_{index:04d}_{type_id}",
        type_id=type_id,
        origin_x=int(x),
        origin_y=int(y),
        rotation=int(rotation),
        config=dict(config),
        is_foundation=False,
    )


def _inject_foundation_devices(base_def: Mapping[str, Any]) -> list[DevicePlacement]:
    devices: list[DevicePlacement] = []
    for index, raw_device in enumerate(base_def.get("foundationBuildings", [])):
        if not isinstance(raw_device, Mapping):
            continue
        origin = raw_device.get("origin")
        if not isinstance(origin, Mapping):
            continue
        devices.append(
            DevicePlacement(
                instance_id=str(raw_device.get("instanceId", f"foundation_{index:04d}")),
                type_id=str(raw_device.get("typeId", "")),
                origin_x=int(origin.get("x", 0)),
                origin_y=int(origin.get("y", 0)),
                rotation=int(raw_device.get("rotation", 0)),
                config=dict(raw_device.get("config") or {}),
                is_foundation=True,
            )
        )
    return devices


def _iter_config_item_ids(config: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    def _yield_if_present(path: str, value: Any) -> Iterable[tuple[str, str]]:
        if value is None:
            return []
        return [(path, str(value))]

    for key in ("pickupItemId", "admissionItemId", "pumpOutputItemId", "preloadInputItemId"):
        yield from _yield_if_present(f"config.{key}", config.get(key))

    for list_key in ("preloadInputs", "storagePreloadInputs"):
        values = config.get(list_key)
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            continue
        for index, entry in enumerate(values):
            if isinstance(entry, Mapping):
                yield from _yield_if_present(f"config.{list_key}[{index}].itemId", entry.get("itemId"))

    outputs = config.get("protocolHubOutputs")
    if isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes)):
        for index, entry in enumerate(outputs):
            if isinstance(entry, Mapping):
                yield from _yield_if_present(
                    f"config.protocolHubOutputs[{index}].itemId",
                    entry.get("itemId"),
                )

    storage_slots = config.get("storageSlots")
    if isinstance(storage_slots, Sequence) and not isinstance(storage_slots, (str, bytes)):
        for index, entry in enumerate(storage_slots):
            if not isinstance(entry, Mapping):
                continue
            yield from _yield_if_present(
                f"config.storageSlots[{index}].pinnedItemId",
                entry.get("pinnedItemId"),
            )
            yield from _yield_if_present(
                f"config.storageSlots[{index}].preloadItemId",
                entry.get("preloadItemId"),
            )

    reactor_pool = config.get("reactorPool")
    if isinstance(reactor_pool, Mapping):
        for key in (
            "solidOutputItemId",
            "liquidOutputItemId",
            "liquidOutputItemIdA",
            "liquidOutputItemIdB",
        ):
            yield from _yield_if_present(f"config.reactorPool.{key}", reactor_pool.get(key))


def _is_finite_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer()
    return False


def _device_def(type_id: str, registries: StaticRegistries) -> Mapping[str, Any]:
    return registries.device_types_by_id.get(type_id, {})


def _rotated_size(size: Mapping[str, Any], rotation: int) -> tuple[int, int]:
    width = int(size.get("width", 0))
    height = int(size.get("height", 0))
    if rotation in {90, 270}:
        return height, width
    return width, height


def _rotate_point(x: int, y: int, width: int, height: int, rotation: int) -> tuple[int, int]:
    if rotation == 0:
        return x, y
    if rotation == 90:
        return height - 1 - y, x
    if rotation == 180:
        return width - 1 - x, height - 1 - y
    return y, width - 1 - x


def _rotate_edge(edge: str, rotation: int) -> str:
    order = ["N", "E", "S", "W"]
    try:
        idx = order.index(edge)
    except ValueError:
        return edge
    steps = int(rotation // 90)
    return order[(idx + steps) % 4]


def _get_footprint_cells(device: DevicePlacement, registries: StaticRegistries) -> list[tuple[int, int]]:
    device_def = _device_def(device.type_id, registries)
    if not device_def:
        return []
    size = device_def.get("size") or {}
    width = int(size.get("width", 0))
    height = int(size.get("height", 0))
    cells: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            rot_x, rot_y = _rotate_point(x, y, width, height, device.rotation)
            cells.append((device.origin_x + rot_x, device.origin_y + rot_y))
    return cells


def _get_rotated_ports(device: DevicePlacement, registries: StaticRegistries) -> list[RotatedPort]:
    device_def = _device_def(device.type_id, registries)
    if not device_def:
        return []
    size = device_def.get("size") or {}
    width = int(size.get("width", 0))
    height = int(size.get("height", 0))
    ports: list[RotatedPort] = []
    for raw_port in device_def.get("ports0", []):
        if not isinstance(raw_port, Mapping):
            continue
        rot_x, rot_y = _rotate_point(
            int(raw_port.get("localCellX", 0)),
            int(raw_port.get("localCellY", 0)),
            width,
            height,
            device.rotation,
        )
        ports.append(
            RotatedPort(
                instance_id=device.instance_id,
                type_id=device.type_id,
                port_id=str(raw_port.get("id", "")),
                direction=str(raw_port.get("direction", "")),
                edge=_rotate_edge(str(raw_port.get("edge", "")), device.rotation),
                x=device.origin_x + rot_x,
                y=device.origin_y + rot_y,
                allowed_items=dict(raw_port.get("allowedItems") or {}),
                allowed_types=dict(raw_port.get("allowedTypes") or {}),
            )
        )
    return ports


def _allows_outer_ring(type_id: str, registries: StaticRegistries) -> bool:
    tags = _device_def(type_id, registries).get("tags") or []
    return "OuterRingAllowed" in tags


def _inner_ring_not_allowed(type_id: str, registries: StaticRegistries) -> bool:
    tags = _device_def(type_id, registries).get("tags") or []
    return "InnerRingNotAllowed" in tags


def _is_cell_within_placement_area(
    x: int,
    y: int,
    *,
    lot_size: int,
    outer_ring: Mapping[str, Any],
    allow_outer_ring: bool,
) -> bool:
    if allow_outer_ring:
        return (
            x >= -int(outer_ring.get("left", 0))
            and y >= -int(outer_ring.get("top", 0))
            and x < lot_size + int(outer_ring.get("right", 0))
            and y < lot_size + int(outer_ring.get("bottom", 0))
        )
    return 0 <= x < lot_size and 0 <= y < lot_size


def _is_device_within_allowed_placement_area(
    device: DevicePlacement,
    base_def: Mapping[str, Any],
    registries: StaticRegistries,
) -> bool:
    footprint = _get_footprint_cells(device, registries)
    if not footprint:
        return False
    lot_size = int(base_def.get("placeableSize", 0))
    outer_ring = base_def.get("outerRing") if isinstance(base_def.get("outerRing"), Mapping) else {}
    allow_outer_ring = _allows_outer_ring(device.type_id, registries)
    if not all(
        _is_cell_within_placement_area(
            cell_x,
            cell_y,
            lot_size=lot_size,
            outer_ring=outer_ring,
            allow_outer_ring=allow_outer_ring,
        )
        for cell_x, cell_y in footprint
    ):
        return False
    if not _inner_ring_not_allowed(device.type_id, registries):
        return True
    return all(not (0 <= cell_x < lot_size and 0 <= cell_y < lot_size) for cell_x, cell_y in footprint)


def _build_occupancy_map(
    devices: Sequence[DevicePlacement],
    registries: StaticRegistries,
) -> dict[str, list[tuple[str, str, bool]]]:
    occupancy: dict[str, list[tuple[str, str, bool]]] = {}
    for device in devices:
        for cell_x, cell_y in _get_footprint_cells(device, registries):
            key = f"{cell_x},{cell_y}"
            occupancy.setdefault(key, []).append((device.instance_id, device.type_id, device.is_foundation))
    return occupancy


def _is_belt_like(type_id: str, registries: StaticRegistries) -> bool:
    return type_id in registries.belt_type_ids or type_id in registries.junction_type_ids


def _is_pipe_like(type_id: str, registries: StaticRegistries) -> bool:
    return type_id in registries.pipe_type_ids or type_id in registries.pipe_junction_type_ids


def _is_track_like(type_id: str, registries: StaticRegistries) -> bool:
    return _is_belt_like(type_id, registries) or _is_pipe_like(type_id, registries)


def _detect_overlap_errors(
    occupancy_map: Mapping[str, Sequence[tuple[str, str, bool]]],
    registries: StaticRegistries,
) -> list[str]:
    errors: list[str] = []
    for cell_key, entries in occupancy_map.items():
        if len(entries) <= 1:
            continue
        belt_family_count = 0
        pipe_family_count = 0
        warehouse_bus_pass_through_count = 0
        has_other_type = False
        for _, type_id, _ in entries:
            if _is_belt_like(type_id, registries):
                belt_family_count += 1
                continue
            if _is_pipe_like(type_id, registries):
                pipe_family_count += 1
                continue
            if type_id in registries.warehouse_bus_type_ids:
                warehouse_bus_pass_through_count += 1
                continue
            has_other_type = True
        allow_belt_pipe_coexist = not has_other_type and belt_family_count <= 1 and pipe_family_count <= 1
        allow_pipe_warehouse_bus_coexist = (
            not has_other_type
            and belt_family_count == 0
            and pipe_family_count <= 1
            and warehouse_bus_pass_through_count >= 1
        )
        if allow_belt_pipe_coexist or allow_pipe_warehouse_bus_coexist:
            continue
        instance_ids = ", ".join(sorted(instance_id for instance_id, _, _ in entries))
        errors.append(f"cell {cell_key} has illegal multi-occupancy across [{instance_ids}]")
    return errors


def _device_placement_constraints(type_id: str, registries: StaticRegistries) -> list[dict[str, Any]]:
    device_def = _device_def(type_id, registries)
    return [dict(rule) for rule in device_def.get("placementConstraints") or [] if isinstance(rule, Mapping)]


def _resolve_rule_edge(device: DevicePlacement, rule: Mapping[str, Any], registries: StaticRegistries) -> str | None:
    if str(rule.get("edgeMode", "")).strip() == "explicit":
        edge = str(rule.get("edge", "")).strip()
        return edge or None
    rotated_ports = _get_rotated_ports(device, registries)
    port_id = str(rule.get("portId", "")).strip()
    base_port = None
    if port_id:
        for port in rotated_ports:
            if port.port_id == port_id:
                base_port = port
                break
    if base_port is None and rotated_ports:
        base_port = rotated_ports[0]
    if base_port is None:
        return None
    return _OPPOSITE_EDGE.get(base_port.edge)


def _boundary_cells_for_edge(
    device: DevicePlacement,
    edge: str,
    registries: StaticRegistries,
) -> list[tuple[int, int]]:
    device_def = _device_def(device.type_id, registries)
    if not device_def:
        return []
    width, height = _rotated_size(device_def.get("size") or {}, device.rotation)
    origin_x = device.origin_x
    origin_y = device.origin_y
    if edge == "N":
        return [(origin_x + index, origin_y) for index in range(width)]
    if edge == "S":
        return [(origin_x + index, origin_y + height - 1) for index in range(width)]
    if edge == "W":
        return [(origin_x, origin_y + index) for index in range(height)]
    return [(origin_x + width - 1, origin_y + index) for index in range(height)]


def _create_target_matcher(rule: Mapping[str, Any]):
    type_ids = {str(value) for value in rule.get("targetTypeIds", []) if str(value)} or None
    tag_ids = {str(value) for value in rule.get("targetTagsAny", []) if str(value)} or None

    def _matches(type_def: Mapping[str, Any]) -> bool:
        hit_type = type_ids is not None and str(type_def.get("id", "")) in type_ids
        tags = {str(tag) for tag in type_def.get("tags", []) if str(tag)}
        hit_tag = tag_ids is not None and bool(tags & tag_ids)
        if type_ids is None and tag_ids is None:
            return True
        return bool(hit_type or hit_tag)

    return _matches


def _check_edge_contact_rule(
    occupancy: Mapping[str, Sequence[tuple[str, str, bool]]],
    device_by_id: Mapping[str, DevicePlacement],
    device: DevicePlacement,
    rule: Mapping[str, Any],
    registries: StaticRegistries,
) -> bool:
    resolved_edge = _resolve_rule_edge(device, rule, registries)
    if not resolved_edge:
        return False
    dx, dy = _EDGE_DELTA[resolved_edge]
    boundary_cells = _boundary_cells_for_edge(device, resolved_edge, registries)
    is_target = _create_target_matcher(rule)
    min_adjacent_cells = int(rule.get("minAdjacentCells", 1))

    touched = 0
    for cell_x, cell_y in boundary_cells:
        neighbor_key = f"{cell_x + dx},{cell_y + dy}"
        neighbors = occupancy.get(neighbor_key, ())
        if not neighbors:
            continue
        matched = False
        for neighbor_instance_id, neighbor_type_id, _ in neighbors:
            neighbor_device = device_by_id.get(neighbor_instance_id)
            if neighbor_device is None:
                continue
            neighbor_type = _device_def(neighbor_type_id, registries)
            if not neighbor_type:
                continue
            if is_target(neighbor_type):
                matched = True
                break
        if matched:
            touched += 1
            if touched >= min_adjacent_cells:
                return True
    return False


def _boundary_key(x: int, y: int, edge: str) -> str:
    if edge == "E":
        return f"{x},{y}|E"
    if edge == "W":
        return f"{x - 1},{y}|E"
    if edge == "S":
        return f"{x},{y}|S"
    return f"{x},{y - 1}|S"


def _allowed_item_ids(port: RotatedPort, registries: StaticRegistries) -> frozenset[str] | None:
    mode = str(port.allowed_items.get("mode", "any"))
    if mode in {"any", "recipe_items"}:
        return None
    if mode == "recipe_inputs":
        return registries.recipe_input_item_ids
    if mode == "recipe_outputs":
        return registries.recipe_output_item_ids
    whitelist = port.allowed_items.get("whitelist")
    if isinstance(whitelist, Sequence) and not isinstance(whitelist, (str, bytes)):
        return frozenset(str(value) for value in whitelist if str(value))
    return frozenset()


def _allowed_type_set(port: RotatedPort) -> frozenset[str]:
    mode = str(port.allowed_types.get("mode", "whitelist"))
    if mode == "solid":
        return frozenset({"solid"})
    if mode == "liquid":
        return frozenset({"liquid"})
    whitelist = port.allowed_types.get("whitelist")
    if isinstance(whitelist, Sequence) and not isinstance(whitelist, (str, bytes)):
        return frozenset(str(value) for value in whitelist if str(value))
    return frozenset()


def _is_item_compatible(output_port: RotatedPort, input_port: RotatedPort, registries: StaticRegistries) -> bool:
    output_types = _allowed_type_set(output_port)
    input_types = _allowed_type_set(input_port)
    if not (output_types & input_types):
        return False
    output_items = _allowed_item_ids(output_port, registries)
    input_items = _allowed_item_ids(input_port, registries)
    if output_items is None or input_items is None:
        return True
    return bool(output_items & input_items)


def _port_buckets(devices: Sequence[DevicePlacement], registries: StaticRegistries) -> dict[str, list[RotatedPort]]:
    buckets: dict[str, list[RotatedPort]] = {}
    for device in devices:
        for port in _get_rotated_ports(device, registries):
            key = _boundary_key(port.x, port.y, port.edge)
            buckets.setdefault(key, []).append(port)
    return buckets


def _links_from_layout(
    devices: Sequence[DevicePlacement],
    registries: StaticRegistries,
) -> list[tuple[RotatedPort, RotatedPort]]:
    buckets = _port_buckets(devices, registries)
    is_track_like_by_id = {
        device.instance_id: _is_track_like(device.type_id, registries)
        for device in devices
    }
    links: list[tuple[RotatedPort, RotatedPort]] = []
    for ports in buckets.values():
        if len(ports) < 2:
            continue
        outputs = [port for port in ports if port.direction == "Output"]
        inputs = [port for port in ports if port.direction == "Input"]
        for output_port in outputs:
            for input_port in inputs:
                if output_port.instance_id == input_port.instance_id:
                    continue
                if not (
                    is_track_like_by_id.get(output_port.instance_id, False)
                    or is_track_like_by_id.get(input_port.instance_id, False)
                ):
                    continue
                if _OPPOSITE_EDGE.get(output_port.edge) != input_port.edge:
                    continue
                if not _is_item_compatible(output_port, input_port, registries):
                    continue
                links.append((output_port, input_port))
    return links


def _detect_port_mismatch_errors(
    devices: Sequence[DevicePlacement],
    registries: StaticRegistries,
) -> list[str]:
    buckets = _port_buckets(devices, registries)
    valid_pairs = {
        (
            output_port.instance_id,
            output_port.port_id,
            input_port.instance_id,
            input_port.port_id,
        )
        for output_port, input_port in _links_from_layout(devices, registries)
    }

    errors: list[str] = []
    for boundary, ports in buckets.items():
        if len(ports) < 2:
            continue
        outputs = [port for port in ports if port.direction == "Output"]
        inputs = [port for port in ports if port.direction == "Input"]
        for output_port in outputs:
            for input_port in inputs:
                if output_port.instance_id == input_port.instance_id:
                    continue
                pair_key = (
                    output_port.instance_id,
                    output_port.port_id,
                    input_port.instance_id,
                    input_port.port_id,
                )
                if pair_key in valid_pairs:
                    continue
                reasons: list[str] = []
                if not (
                    _is_track_like(output_port.type_id, registries)
                    or _is_track_like(input_port.type_id, registries)
                ):
                    reasons.append("neither side is track-like")
                if _OPPOSITE_EDGE.get(output_port.edge) != input_port.edge:
                    reasons.append(f"edges {output_port.edge} and {input_port.edge} are not opposing")
                if not _is_item_compatible(output_port, input_port, registries):
                    reasons.append("item/type allowances do not overlap")
                if reasons:
                    errors.append(
                        "boundary "
                        f"{boundary} has incompatible ports "
                        f"{output_port.instance_id}.{output_port.port_id} ({output_port.type_id}) -> "
                        f"{input_port.instance_id}.{input_port.port_id} ({input_port.type_id}): "
                        + ", ".join(reasons)
                    )
    return errors


def _detect_port_warnings(
    devices: Sequence[DevicePlacement],
    registries: StaticRegistries,
) -> list[str]:
    valid_links = _links_from_layout(devices, registries)
    link_count_by_instance: dict[str, int] = {}
    for output_port, input_port in valid_links:
        link_count_by_instance[output_port.instance_id] = link_count_by_instance.get(output_port.instance_id, 0) + 1
        link_count_by_instance[input_port.instance_id] = link_count_by_instance.get(input_port.instance_id, 0) + 1

    warnings: list[str] = []
    for device in devices:
        if device.is_foundation:
            continue
        link_count = link_count_by_instance.get(device.instance_id, 0)
        if _is_track_like(device.type_id, registries) and link_count == 0:
            warnings.append(
                f"track-like device {device.instance_id} ({device.type_id}) has no legal links"
            )
        if device.type_id in _LOADER_TYPE_IDS and link_count == 0:
            warnings.append(
                f"loader-like device {device.instance_id} ({device.type_id}) is isolated from any legal logistics link"
            )
    return warnings

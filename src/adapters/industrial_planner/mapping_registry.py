"""IndustrialPlanner target mapping registry.

This module keeps all target-specific mapping quirks away from the canonical
blueprint contract. The current repository continues to treat
`optimal_blueprint.json` as the internal layout truth; this file only describes
how that truth is projected into the IndustrialPlanner ecosystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.adapters.endfield_calc.semantic_mapping import (
    SemanticRegistry,
    current_repository_semantic_registry,
)
from src.adapters.industrial_planner.commodity_resolver import (
    resolve_recipe_for_facility,
    translate_canonical_item_id,
    translate_config_item_ids,
)
from src.interchange.target_capabilities import TargetCapabilities

INDUSTRIAL_PLANNER_TARGET = "industrial_planner"
INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA = "industrial-planner-blueprint"
INDUSTRIAL_PLANNER_BLUEPRINT_VERSION = "1.0"
INDUSTRIAL_PLANNER_BLUEPRINT_COMPAT_VERSION = "1"
DEFAULT_BASE_ID = "valley4_protocol_core"

PRECISION_MAPPED_FACILITY_TYPES = frozenset({
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
})

INDUSTRIAL_PLANNER_CAPABILITIES = TargetCapabilities(
    supports_power_overlay=True,
    supports_exact_proof_metadata=False,
    supports_dual_layer_routing="partial",
    supports_active_ports=True,
    supports_layout_editing=True,
    supports_persistence=True,
    supports_share_links=True,
    notes=(
        "IndustrialPlanner is treated as a viewer/editor target, not as a certified proof sink.",
        "The current exporter is one-way and may be lossy for generic facilities, dual-layer routing, and exact-only metadata.",
    ),
)

_ROTATION_BY_ORIENTATION = {
    0: 0,
    1: 90,
    2: 180,
    3: 270,
}

_DIRECTION_TO_ROTATION = {
    "E": 0,
    "S": 90,
    "W": 180,
    "N": 270,
}

_OPPOSITE_EDGE = {
    "N": "S",
    "S": "N",
    "E": "W",
    "W": "E",
}

_EDGE_DELTA = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}

_TURN_ROTATIONS = {
    frozenset({"N", "W"}): 0,
    frozenset({"N", "E"}): 90,
    frozenset({"E", "S"}): 180,
    frozenset({"S", "W"}): 270,
}

_LIQUID_HINTS = (
    "liquid",
    "fluid",
    "water",
    "sewage",
    "slurry",
    "oil",
    "acid",
    "coolant",
)


@dataclass(frozen=True)
class FacilityMapping:
    canonical_type: str
    target_type_id: str | None
    classification: str
    reason: str
    rotation_offset_degrees: int = 0
    default_config: Mapping[str, Any] = field(default_factory=dict)


_FACILITY_MAPPINGS: dict[str, FacilityMapping] = {
    "manufacturing_3x3": FacilityMapping(
        canonical_type="manufacturing_3x3",
        target_type_id="item_port_grinder_1",
        classification="lossy",
        reason="canonical facility type is generic; unresolved facilities fall back to a representative 3x3 IndustrialPlanner processor",
    ),
    "manufacturing_5x5": FacilityMapping(
        canonical_type="manufacturing_5x5",
        target_type_id="item_port_planter_1",
        classification="lossy",
        reason="canonical facility type is generic; unresolved facilities fall back to a representative 5x5 IndustrialPlanner agricultural processor",
    ),
    "manufacturing_6x4": FacilityMapping(
        canonical_type="manufacturing_6x4",
        target_type_id="item_port_filling_pd_mc_1",
        classification="lossy",
        reason="canonical facility type is generic; unresolved facilities fall back to a representative 6x4 IndustrialPlanner processor",
    ),
    "protocol_core": FacilityMapping(
        canonical_type="protocol_core",
        target_type_id=None,
        classification="dropped",
        reason="IndustrialPlanner encodes the playable base as blueprint.baseId; a movable protocol_core device is not emitted by this exporter",
    ),
    "protocol_storage_box": FacilityMapping(
        canonical_type="protocol_storage_box",
        target_type_id="item_port_storager_1",
        classification="lossy",
        reason="exported as the closest target-side storage box device with warehouse toggle config",
        default_config={"submitToWarehouse": False},
    ),
    "power_pole": FacilityMapping(
        canonical_type="power_pole",
        target_type_id="item_port_power_diffuser_1",
        classification="direct",
        reason="square power-coverage helper maps directly to the closest power diffuser device",
    ),
    "boundary_storage_port": FacilityMapping(
        canonical_type="boundary_storage_port",
        target_type_id="item_port_unloader_1",
        classification="derived",
        reason="loader / unloader / storage export is derived from boundary port directionality and translated commodity ids",
        rotation_offset_degrees=90,
    ),
}


@dataclass(frozen=True)
class ResolvedFacilityDevice:
    classification: str
    target_type_id: str | None
    origin: dict[str, int]
    rotation: int | None
    config: dict[str, Any]
    reason: str
    warnings: tuple[str, ...] = field(default_factory=tuple)
    auxiliary_devices: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    resolved_recipe_id: str | None = None
    resolution_mode: str = "direct"
    translation_miss_count: int = 0

    def to_device(self) -> dict[str, Any] | None:
        if self.target_type_id is None or self.rotation is None:
            return None
        payload: dict[str, Any] = {
            "typeId": self.target_type_id,
            "rotation": self.rotation,
            "origin": dict(self.origin),
        }
        if self.config:
            payload["config"] = dict(self.config)
        return payload


@dataclass(frozen=True)
class ResolvedRoutingDevice:
    target_type_id: str
    rotation: int
    origin: dict[str, int]
    classification: str
    reason: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_device(self) -> dict[str, Any]:
        return {
            "typeId": self.target_type_id,
            "rotation": self.rotation,
            "origin": dict(self.origin),
        }


def industrial_planner_target_capabilities() -> dict[str, Any]:
    return INDUSTRIAL_PLANNER_CAPABILITIES.to_dict()


def facility_mapping_table() -> dict[str, FacilityMapping]:
    return dict(_FACILITY_MAPPINGS)


def orientation_to_rotation(orientation: int, *, degrees_offset: int = 0) -> int:
    normalized = int(orientation) % 4
    base = _ROTATION_BY_ORIENTATION[normalized]
    return int((base + int(degrees_offset)) % 360)


def direction_to_rotation(direction: str) -> int:
    normalized = str(direction).strip().upper()
    return _DIRECTION_TO_ROTATION.get(normalized, 0)


def is_liquid_like_commodity(commodity: str) -> bool:
    text = str(commodity).strip().lower()
    return any(hint in text for hint in _LIQUID_HINTS)


def resolve_facility_device(
    facility: Mapping[str, Any],
    *,
    default_base_id: str = DEFAULT_BASE_ID,
    semantic_registry: SemanticRegistry | None = None,
) -> ResolvedFacilityDevice:
    return resolve_facility_device_precise(
        facility,
        default_base_id=default_base_id,
        semantic_registry=semantic_registry,
    )


def resolve_facility_device_precise(
    facility: Mapping[str, Any],
    *,
    default_base_id: str = DEFAULT_BASE_ID,
    semantic_registry: SemanticRegistry | None = None,
) -> ResolvedFacilityDevice:
    semantic_registry = semantic_registry or current_repository_semantic_registry()
    facility_type = str(facility.get("facility_type", "")).strip()
    facility_instance_id = str(facility.get("instance_id", "")).strip() or "<unknown>"
    mapping = _FACILITY_MAPPINGS.get(facility_type)

    if mapping is None:
        return ResolvedFacilityDevice(
            classification="lossy",
            target_type_id="item_port_storager_1",
            origin=_facility_origin(facility),
            rotation=orientation_to_rotation(int(facility.get("orientation", 0))),
            config={"submitToWarehouse": False},
            reason="unknown canonical facility type fell back to generic storage for editability",
            warnings=(f"unmapped facility_type={facility_type}",),
            resolution_mode="fallback",
        )

    if facility_type == "protocol_core":
        return ResolvedFacilityDevice(
            classification=mapping.classification,
            target_type_id=None,
            origin=_facility_origin(facility),
            rotation=None,
            config={},
            reason=mapping.reason,
            warnings=(
                f"protocol_core facility {facility_instance_id} is omitted; exporter uses blueprint.baseId={default_base_id!r} instead",
            ),
            resolution_mode="dropped",
        )

    if facility_type == "boundary_storage_port":
        return _resolve_boundary_storage_port_device(
            facility,
            mapping,
            semantic_registry=semantic_registry,
        )

    if facility_type in PRECISION_MAPPED_FACILITY_TYPES:
        precise_resolution = resolve_recipe_for_facility(
            facility,
            semantic_registry=semantic_registry,
        )
        if precise_resolution.resolved and precise_resolution.upstream_facility_id:
            return ResolvedFacilityDevice(
                classification="derived",
                target_type_id=precise_resolution.upstream_facility_id,
                origin=_facility_origin(facility),
                rotation=orientation_to_rotation(
                    int(facility.get("orientation", 0)),
                    degrees_offset=mapping.rotation_offset_degrees,
                ),
                config={},
                reason=precise_resolution.reason,
                warnings=tuple(sorted(set(precise_resolution.warnings))),
                resolved_recipe_id=precise_resolution.resolved_recipe_id,
                resolution_mode="precise",
                translation_miss_count=precise_resolution.translation_miss_count,
            )

        fallback_warnings = list(precise_resolution.warnings)
        fallback_warnings.append(
            f"precise resolution fallback for facility {facility_instance_id} ({facility_type}); exported as generic {mapping.target_type_id}"
        )
        config_audit = translate_config_item_ids(
            dict(mapping.default_config),
            semantic_registry=semantic_registry,
        )
        fallback_warnings.extend(config_audit.warnings)
        return ResolvedFacilityDevice(
            classification=mapping.classification,
            target_type_id=mapping.target_type_id,
            origin=_facility_origin(facility),
            rotation=orientation_to_rotation(
                int(facility.get("orientation", 0)),
                degrees_offset=mapping.rotation_offset_degrees,
            ),
            config=config_audit.translated_config,
            reason=f"{mapping.reason}; {precise_resolution.reason}",
            warnings=tuple(sorted(set(fallback_warnings))),
            resolution_mode="fallback",
            translation_miss_count=(
                precise_resolution.translation_miss_count + config_audit.translation_miss_count
            ),
        )

    config_audit = translate_config_item_ids(
        dict(mapping.default_config),
        semantic_registry=semantic_registry,
    )
    return ResolvedFacilityDevice(
        classification=mapping.classification,
        target_type_id=mapping.target_type_id,
        origin=_facility_origin(facility),
        rotation=orientation_to_rotation(
            int(facility.get("orientation", 0)),
            degrees_offset=mapping.rotation_offset_degrees,
        ),
        config=config_audit.translated_config,
        reason=mapping.reason,
        warnings=tuple(sorted(set(config_audit.warnings))),
        resolution_mode="direct",
        translation_miss_count=config_audit.translation_miss_count,
    )


def resolve_routing_device(
    *,
    x: int,
    y: int,
    layer_name: str,
    cell: Mapping[str, Any],
) -> ResolvedRoutingDevice:
    component_type = str(cell.get("type", "belt")).strip().lower()
    flow_in = tuple(str(direction) for direction in cell.get("flow_in", []) if str(direction))
    flow_out = tuple(str(direction) for direction in cell.get("flow_out", []) if str(direction))
    connected = frozenset(flow_in) | frozenset(flow_out)
    commodities = _routing_cell_commodities(cell)
    liquid_commodities = tuple(
        commodity for commodity in commodities if is_liquid_like_commodity(commodity)
    )
    is_mixed = len(commodities) > 1
    if is_mixed and liquid_commodities:
        raise ValueError(
            "mixed routing cell contains liquid-like commodities and cannot be "
            "safely projected into IndustrialPlanner logistics: "
            + ", ".join(liquid_commodities)
        )
    is_liquid = bool(liquid_commodities)
    warnings: list[str] = []
    classification = "direct"
    reason = "routing cell converted into a target-side logistics device"
    if is_mixed:
        warnings.append(
            "mixed item-like routing cell exported as belt-family logistics device "
            f"for commodities {', '.join(commodities)}"
        )

    if layer_name == "L1_elevated" or component_type == "bridge":
        classification = "lossy"
        warnings.append("elevated bridge semantics are flattened into a single-layer device export")
        reason = "dual-layer bridge semantics are approximated by planar devices in IndustrialPlanner"

    if component_type == "splitter":
        if is_liquid:
            classification = "lossy"
            warnings.append("liquid-like splitter exported through solid-family logistics because target-side liquid junction vocabulary is incomplete in the current adapter")
        return ResolvedRoutingDevice(
            target_type_id="item_log_splitter",
            rotation=_junction_rotation(flow_in=flow_in, flow_out=flow_out),
            origin={"x": int(x), "y": int(y)},
            classification=classification,
            reason=reason,
            warnings=tuple(warnings),
        )

    if component_type == "merger":
        if is_liquid:
            classification = "lossy"
            warnings.append("liquid-like merger exported through solid-family logistics because target-side liquid converger vocabulary is incomplete in the current adapter")
        return ResolvedRoutingDevice(
            target_type_id="item_log_converger",
            rotation=_junction_rotation(flow_in=flow_in, flow_out=flow_out),
            origin={"x": int(x), "y": int(y)},
            classification=classification,
            reason=reason,
            warnings=tuple(warnings),
        )

    family = "pipe" if is_liquid else "belt"
    if len(connected) == 2 and connected in {frozenset({"E", "W"}), frozenset({"N", "S"})}:
        rotation = 0 if connected == frozenset({"E", "W"}) else 90
        return ResolvedRoutingDevice(
            target_type_id=f"{family}_straight_1x1",
            rotation=rotation,
            origin={"x": int(x), "y": int(y)},
            classification=classification,
            reason=reason,
            warnings=tuple(warnings),
        )

    if len(connected) == 2 and connected in _TURN_ROTATIONS:
        rotation = _TURN_ROTATIONS[connected]
        return ResolvedRoutingDevice(
            target_type_id=f"{family}_turn_ccw_1x1",
            rotation=rotation,
            origin={"x": int(x), "y": int(y)},
            classification=classification,
            reason=reason,
            warnings=tuple(warnings),
        )

    classification = "lossy"
    warnings.append("routing cell shape is not represented exactly and fell back to a generic logistics connector")
    return ResolvedRoutingDevice(
        target_type_id="item_log_connector",
        rotation=_junction_rotation(flow_in=flow_in, flow_out=flow_out),
        origin={"x": int(x), "y": int(y)},
        classification=classification,
        reason="complex routing shape flattened to a generic connector",
        warnings=tuple(warnings),
    )


def _routing_cell_commodities(cell: Mapping[str, Any]) -> tuple[str, ...]:
    raw_commodities = cell.get("commodities")
    if isinstance(raw_commodities, Sequence) and not isinstance(raw_commodities, (str, bytes)):
        commodities = tuple(sorted({str(item) for item in raw_commodities}))
        if commodities:
            return commodities
    return (str(cell.get("commodity", "[TBD]")),)


def _resolve_boundary_storage_port_device(
    facility: Mapping[str, Any],
    mapping: FacilityMapping,
    *,
    semantic_registry: SemanticRegistry,
) -> ResolvedFacilityDevice:
    active_ports = facility.get("active_ports")
    if not isinstance(active_ports, Sequence):
        active_ports = []

    input_ports = [port for port in active_ports if str(port.get("type", "")).lower() == "input"]
    output_ports = [port for port in active_ports if str(port.get("type", "")).lower() == "output"]
    warnings: list[str] = []
    target_type_id = mapping.target_type_id or "item_port_unloader_1"
    config: dict[str, Any] = {}
    auxiliary_devices: list[dict[str, Any]] = []
    classification = "derived"
    resolution_mode = "direct"
    translation_miss_count = 0
    resolved_rotation = orientation_to_rotation(
        int(facility.get("orientation", 0)),
        degrees_offset=mapping.rotation_offset_degrees,
    )

    if output_ports and not input_ports:
        target_type_id = "item_port_unloader_1"
        selected_translation = None
        first_declared_commodity: str | None = None
        for port in output_ports:
            commodity = _normalize_port_commodity(port)
            if first_declared_commodity is None:
                first_declared_commodity = commodity
            translation = translate_canonical_item_id(
                commodity,
                semantic_registry=semantic_registry,
            )
            warnings.extend(translation.warnings)
            translation_miss_count += int(translation.is_translation_miss)
            if selected_translation is None and translation.translated_item_id is not None:
                selected_translation = translation

        if selected_translation is not None and selected_translation.translated_item_id is not None:
            config = {
                "pickupItemId": selected_translation.translated_item_id,
                "pickupIgnoreInventory": True,
                "protocolHubOutputs": [
                    {
                        "portId": "p_out_mid",
                        "itemId": selected_translation.translated_item_id,
                        "ignoreInventory": True,
                    }
                ],
            }
        elif first_declared_commodity is not None:
            warnings.append(
                f"boundary_storage_port output commodity {_describe_port_commodity(first_declared_commodity)} was unresolved; pickup/config binding was omitted"
            )
        else:
            warnings.append(
                "boundary_storage_port output commodity is unknown; exported without pickup item binding"
            )
    elif input_ports and not output_ports:
        target_type_id = "item_port_loader_1"
        if len(input_ports) > 1:
            warnings.append(
                "boundary_storage_port has multiple input ports; loader export keeps only geometric placement"
            )
        else:
            input_commodity = _normalize_port_commodity(input_ports[0])
            translation = translate_canonical_item_id(
                input_commodity,
                semantic_registry=semantic_registry,
            )
            warnings.extend(translation.warnings)
            translation_miss_count += int(translation.is_translation_miss)
            if translation.translated_item_id is not None:
                auxiliary_devices.append(
                    _build_loader_input_binding_device(
                        loader_origin=_facility_origin(facility),
                        loader_rotation=resolved_rotation,
                        translated_item_id=translation.translated_item_id,
                    )
                )
            elif input_commodity is not None:
                warnings.append(
                    f"boundary_storage_port input commodity {_describe_port_commodity(input_commodity)} was unresolved; loader admission binding was omitted"
                )
            else:
                warnings.append(
                    "boundary_storage_port input commodity is unknown; loader admission binding was omitted"
                )
    else:
        target_type_id = "item_port_storager_1"
        config = {"submitToWarehouse": False}
        classification = "lossy"
        resolution_mode = "fallback"
        warnings.append(
            "boundary_storage_port could not be reduced to a pure input or pure output port; fell back to storage"
        )

    if input_ports and output_ports:
        warnings.append(
            "boundary_storage_port mixes input and output semantics; target device choice is necessarily lossy"
        )

    config_audit = translate_config_item_ids(
        config,
        semantic_registry=semantic_registry,
    )
    warnings.extend(config_audit.warnings)
    translation_miss_count += config_audit.translation_miss_count

    return ResolvedFacilityDevice(
        classification=classification,
        target_type_id=target_type_id,
        origin=_facility_origin(facility),
        rotation=resolved_rotation,
        config=config_audit.translated_config,
        reason=mapping.reason,
        warnings=tuple(sorted(set(warnings))),
        auxiliary_devices=tuple(auxiliary_devices),
        resolution_mode=resolution_mode,
        translation_miss_count=int(translation_miss_count),
    )


def _build_loader_input_binding_device(
    *,
    loader_origin: Mapping[str, Any],
    loader_rotation: int,
    translated_item_id: str,
) -> dict[str, Any]:
    port_x, port_y, port_edge = _loader_input_port_geometry(
        loader_origin=loader_origin,
        loader_rotation=loader_rotation,
    )
    dx, dy = _EDGE_DELTA[port_edge]
    admission_rotation = direction_to_rotation(_OPPOSITE_EDGE[port_edge])
    return {
        "typeId": "item_log_admission",
        "rotation": admission_rotation,
        "origin": {"x": int(port_x + dx), "y": int(port_y + dy)},
        "config": {"admissionItemId": str(translated_item_id)},
    }


def _loader_input_port_geometry(
    *,
    loader_origin: Mapping[str, Any],
    loader_rotation: int,
) -> tuple[int, int, str]:
    rot_x, rot_y = _rotate_point(1, 0, 3, 1, loader_rotation)
    rotated_edge = _rotate_edge("N", loader_rotation)
    return (
        int(loader_origin.get("x", 0)) + rot_x,
        int(loader_origin.get("y", 0)) + rot_y,
        rotated_edge,
    )


def _rotate_point(x: int, y: int, width: int, height: int, rotation: int) -> tuple[int, int]:
    normalized_rotation = int(rotation) % 360
    if normalized_rotation == 0:
        return x, y
    if normalized_rotation == 90:
        return height - 1 - y, x
    if normalized_rotation == 180:
        return width - 1 - x, height - 1 - y
    return y, width - 1 - x


def _rotate_edge(edge: str, rotation: int) -> str:
    order = ["N", "E", "S", "W"]
    try:
        index = order.index(str(edge).strip().upper())
    except ValueError:
        return str(edge).strip().upper()
    steps = int((int(rotation) % 360) // 90)
    return order[(index + steps) % 4]


def _facility_origin(facility: Mapping[str, Any]) -> dict[str, int]:
    anchor = facility.get("anchor")
    if not isinstance(anchor, Mapping):
        anchor = {}
    return {
        "x": int(anchor.get("x", 0)),
        "y": int(anchor.get("y", 0)),
    }


def _normalize_port_commodity(port: Mapping[str, Any]) -> str:
    commodity = port.get("commodity", "")
    if commodity is None:
        return ""
    return str(commodity).strip()


def _describe_port_commodity(commodity: str) -> str:
    if not commodity:
        return "<empty>"
    return repr(str(commodity))


def _junction_rotation(*, flow_in: Sequence[str], flow_out: Sequence[str]) -> int:
    for candidate in list(flow_out) + list(flow_in):
        normalized = str(candidate).strip().upper()
        if normalized in _DIRECTION_TO_ROTATION:
            return _DIRECTION_TO_ROTATION[normalized]
    return 0

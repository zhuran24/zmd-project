"""Postprocess-only outer deployment transforms for IndustrialPlanner exports."""

from __future__ import annotations

from typing import Any, Mapping

from src.adapters.base_planner.outer_deployment_plan import (
    OuterBaseDeploymentPlan,
    outer_deployment_plan_from_dict,
)
from src.io.output_schema import normalize_blueprint_payload


def normalize_outer_deployment_plan(
    deployment_plan: OuterBaseDeploymentPlan | Mapping[str, Any],
) -> OuterBaseDeploymentPlan:
    return (
        deployment_plan
        if isinstance(deployment_plan, OuterBaseDeploymentPlan)
        else outer_deployment_plan_from_dict(deployment_plan)
    )



def materialize_outer_deployed_blueprint_payload(
    *,
    blueprint_payload: Mapping[str, Any],
    deployment_plan: OuterBaseDeploymentPlan | Mapping[str, Any],
) -> dict[str, Any]:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    plan = normalize_outer_deployment_plan(deployment_plan)
    mapping_by_instance = {entry.canonical_instance_id: entry for entry in plan.export_mappings}
    transformed_facilities: list[dict[str, Any]] = []

    for facility in normalized_blueprint.get("facilities", []):
        if not isinstance(facility, Mapping):
            continue
        instance_id = str(facility.get("instance_id", "")).strip()
        export_mapping = mapping_by_instance.get(instance_id)
        if export_mapping is None:
            raise ValueError(f"outer deployment plan has no export mapping for canonical instance {instance_id!r}")
        updated = {
            **facility,
            "anchor": export_mapping.exported_origin.to_dict(),
            "orientation": int(export_mapping.exported_rotation),
            "active_ports": [dict(port) for port in facility.get("active_ports", []) if isinstance(port, Mapping)],
        }
        canonical_anchor = facility.get("anchor") if isinstance(facility.get("anchor"), Mapping) else {}
        dx = int(export_mapping.exported_origin.x) - int(canonical_anchor.get("x", 0))
        dy = int(export_mapping.exported_origin.y) - int(canonical_anchor.get("y", 0))
        for port in updated["active_ports"]:
            port["x"] = int(port.get("x", 0)) + dx
            port["y"] = int(port.get("y", 0)) + dy
        transformed_facilities.append(updated)

    ox = int(plan.inner_island_origin.x)
    oy = int(plan.inner_island_origin.y)
    transformed_routing: dict[str, dict[str, Any]] = {"L0_ground": {}, "L1_elevated": {}}
    routing_network = (
        normalized_blueprint.get("routing_network")
        if isinstance(normalized_blueprint.get("routing_network"), Mapping)
        else {}
    )
    for layer_name in ("L0_ground", "L1_elevated"):
        layer = routing_network.get(layer_name) if isinstance(routing_network.get(layer_name), Mapping) else {}
        translated_layer: dict[str, Any] = {}
        for coord_key, cell in layer.items():
            x, y = _parse_coord_key(str(coord_key))
            translated_layer[f"{x + ox},{y + oy}"] = dict(cell) if isinstance(cell, Mapping) else cell
        transformed_routing[layer_name] = translated_layer

    return {
        "metadata": dict(normalized_blueprint["metadata"]),
        "objective_achieved": dict(normalized_blueprint.get("objective_achieved", {})),
        "facilities": transformed_facilities,
        "routing_network": transformed_routing,
    }



def build_postprocess_export_mapping_section(
    *,
    deployment_plan: OuterBaseDeploymentPlan | Mapping[str, Any],
    export_blueprint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    plan = normalize_outer_deployment_plan(deployment_plan)
    devices = export_blueprint.get("devices") if isinstance(export_blueprint, Mapping) and isinstance(export_blueprint.get("devices"), list) else ()
    entries: list[dict[str, Any]] = []
    for mapping in plan.export_mappings:
        exported_rotation = int(mapping.exported_rotation)
        exported_type_id = mapping.exported_type_id
        if devices:
            matched_device = _find_exported_device_for_mapping(mapping=mapping, devices=devices)
            if matched_device is not None:
                exported_rotation = int(matched_device.get("rotation", exported_rotation))
                if matched_device.get("typeId") is not None:
                    exported_type_id = str(matched_device.get("typeId"))
        entries.append(
            {
                "canonical_instance_id": str(mapping.canonical_instance_id),
                "exported_type_id": exported_type_id,
                "exported_origin": mapping.exported_origin.to_dict(),
                "exported_rotation": int(exported_rotation),
                "mapping_mode": str(mapping.mapping_mode),
                "notes": [str(note) for note in mapping.notes],
                "warnings": [str(warning) for warning in mapping.warnings],
            }
        )
    translated_mapping_count = sum(1 for entry in plan.export_mappings if entry.mapping_mode != "identity")
    return {
        "scope": "postprocess_only",
        "mapping_source": "outer_deployment_plan",
        "plan_version": str(plan.plan_version),
        "planning_status": str(plan.planning_status),
        "base_id": str(plan.base_id),
        "canonical_contract_size": int(plan.canonical_contract_size),
        "inner_island_origin": plan.inner_island_origin.to_dict(),
        "inner_island_size": int(plan.inner_island_size),
        "moat_thickness_by_edge": dict(plan.moat_thickness_by_edge),
        "mapping_count": len(entries),
        "translated_mapping_count": int(translated_mapping_count),
        "entries": entries,
        "warnings": [str(warning) for warning in plan.warnings],
    }




def _find_exported_device_for_mapping(
    *,
    mapping: Any,
    devices: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any] | None:
    target_x = int(mapping.exported_origin.x)
    target_y = int(mapping.exported_origin.y)
    target_type_id = mapping.exported_type_id
    for device in devices:
        if not isinstance(device, Mapping):
            continue
        origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
        if int(origin.get("x", -1)) != target_x or int(origin.get("y", -1)) != target_y:
            continue
        if target_type_id and str(device.get("typeId", "")).strip() != str(target_type_id):
            continue
        return device
    for device in devices:
        if not isinstance(device, Mapping):
            continue
        origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
        if int(origin.get("x", -1)) == target_x and int(origin.get("y", -1)) == target_y:
            return device
    return None


def _parse_coord_key(coord_key: str) -> tuple[int, int]:
    x_str, y_str = coord_key.split(",", 1)
    return int(x_str), int(y_str)


__all__ = [
    "build_postprocess_export_mapping_section",
    "materialize_outer_deployed_blueprint_payload",
    "normalize_outer_deployment_plan",
]

"""Report-shape builders inspired by grid/planner result summaries."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from src.io.output_schema import normalize_blueprint_payload
from src.io.serializer import build_pose_lookup, coerce_facility_pools_payload, pose_lookup_key


def build_blueprint_report(
    *,
    blueprint_payload: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    rules_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = normalize_blueprint_payload(blueprint_payload)
    pools = coerce_facility_pools_payload(facility_pools)
    rules_payload = dict(rules_payload or {})
    facility_templates = rules_payload.get("facility_templates") if isinstance(rules_payload.get("facility_templates"), Mapping) else {}

    selected_poses = _resolve_selected_poses(blueprint, pools)
    occupied_cells = set()
    power_cells = set()
    facility_type_counts: Counter[str] = Counter()
    port_mode_counts: Counter[str] = Counter()
    commodity_counts: Counter[str] = Counter()
    active_port_counts: Counter[str] = Counter()

    for facility in blueprint["facilities"]:
        facility_type = str(facility["facility_type"])
        pose = selected_poses.get(str(facility["instance_id"]))
        if "power_pole" in facility_type.lower() and pose is not None:
            power_cells.update(_pose_power_cell_keys(pose))

    needs_power_total = 0
    needs_power_covered = 0

    for facility in blueprint["facilities"]:
        instance_id = str(facility["instance_id"])
        facility_type = str(facility["facility_type"])
        facility_type_counts[facility_type] += 1
        port_mode_counts[str(facility["port_mode"])] += 1
        for active_port in facility.get("active_ports", []):
            active_port_counts[str(active_port["type"])] += 1
            commodity_counts[str(active_port["commodity"])] += 1

        pose = selected_poses.get(instance_id)
        pose_cells = set(_pose_occupied_cell_keys(pose))
        occupied_cells.update(pose_cells)

        template = facility_templates.get(facility_type) if isinstance(facility_templates, Mapping) else None
        needs_power = bool(template.get("needs_power", False)) if isinstance(template, Mapping) else False
        if needs_power:
            needs_power_total += 1
            if any(cell in power_cells for cell in pose_cells):
                needs_power_covered += 1

    routing_summary = _build_routing_summary(blueprint.get("routing_network", {}))
    empty_rect = blueprint["objective_achieved"]["empty_rect"]
    total_ports = sum(active_port_counts.values())

    return {
        "metadata": dict(blueprint["metadata"]),
        "layout": {
            "facility_count": len(blueprint["facilities"]),
            "occupied_cells": len(occupied_cells),
            "fill_ratio": round(len(occupied_cells) / 4900.0, 6),
            "ghost_rect": {
                "w": int(empty_rect["w"]),
                "h": int(empty_rect["h"]),
                "anchor_x": int(empty_rect["anchor_x"]),
                "anchor_y": int(empty_rect["anchor_y"]),
                "score": float(empty_rect["score"]),
            },
            "facility_type_counts": _counter_items(facility_type_counts),
            "port_mode_counts": _counter_items(port_mode_counts),
        },
        "ports": {
            "total_active_ports": total_ports,
            "input_ports": int(active_port_counts.get("input", 0)),
            "output_ports": int(active_port_counts.get("output", 0)),
            "commodities": _counter_items(commodity_counts),
        },
        "routing": routing_summary,
        "power": {
            "coverage_cells": len(power_cells),
            "pole_count": sum(count for name, count in facility_type_counts.items() if "power_pole" in name.lower()),
            "needs_power_facilities": needs_power_total,
            "covered_needs_power_facilities": needs_power_covered,
        },
        "debug": {
            "source_blueprint_version": str(blueprint["metadata"]["version"]),
            "resolved_pose_count": len(selected_poses),
        },
    }


def _resolve_selected_poses(
    blueprint_payload: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    pose_lookup = build_pose_lookup(facility_pools)
    selected: dict[str, Mapping[str, Any]] = {}
    for facility in blueprint_payload.get("facilities", []):
        key = pose_lookup_key(
            facility_type=str(facility.get("facility_type", "")),
            anchor_x=int((facility.get("anchor") or {}).get("x", 0)),
            anchor_y=int((facility.get("anchor") or {}).get("y", 0)),
            orientation=int(facility.get("orientation", 0)),
            port_mode=str(facility.get("port_mode", "default")),
        )
        matches = pose_lookup.get(key, ())
        if len(matches) == 1:
            selected[str(facility.get("instance_id", ""))] = matches[0][1]
    return selected


def _pose_occupied_cell_keys(pose: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(pose, Mapping):
        return set()
    return {f"{int(cell[0])},{int(cell[1])}" for cell in pose.get("occupied_cells", []) or []}


def _pose_power_cell_keys(pose: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(pose, Mapping):
        return set()
    return {f"{int(cell[0])},{int(cell[1])}" for cell in pose.get("power_coverage_cells", []) or []}


def _build_routing_summary(routing_network: Mapping[str, Any]) -> dict[str, Any]:
    routing_network = dict(routing_network or {})
    summary: dict[str, Any] = {}
    for layer_name in ("L0_ground", "L1_elevated"):
        raw_layer = routing_network.get(layer_name) if isinstance(routing_network.get(layer_name), Mapping) else {}
        component_counts: Counter[str] = Counter()
        commodity_counts: Counter[str] = Counter()
        for cell in raw_layer.values():
            if not isinstance(cell, Mapping):
                continue
            component_counts[str(cell.get("type", "unknown"))] += 1
            commodity_counts[str(cell.get("commodity", "[TBD]"))] += 1
        summary[layer_name] = {
            "cell_count": len(raw_layer),
            "components": _counter_items(component_counts),
            "commodities": _counter_items(commodity_counts),
        }
    summary["total_cells"] = int(summary["L0_ground"]["cell_count"] + summary["L1_elevated"]["cell_count"])
    return summary


def _counter_items(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": int(count)}
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]

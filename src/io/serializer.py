"""Canonical blueprint serializer and postprocess export helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.io.output_schema import (
    BLUEPRINT_SCHEMA_VERSION,
    blueprint_output_path,
    normalize_blueprint_payload,
)
from src.search.exact_campaign import atomic_write_json

_DIRECTION_ORDER = {"N": 0, "E": 1, "S": 2, "W": 3}


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def load_json_mapping(path: Path) -> Dict[str, Any]:
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(payload, Mapping):
        raise TypeError(f"expected JSON mapping at {path}")
    return dict(payload)


def load_candidate_placements(path: Path) -> Dict[str, Sequence[Mapping[str, Any]]]:
    return dict(coerce_facility_pools_payload(load_json_mapping(path)))


def load_canonical_blueprint(path: Path) -> Dict[str, Any]:
    return normalize_blueprint_payload(load_json_mapping(path))


def load_legacy_render_payload(path: Path) -> Dict[str, Any]:
    return load_json_mapping(path)


def _certified_empty_rect_anchor(ghost_rect: Mapping[str, Any]) -> Tuple[int, int]:
    if "anchor_x" not in ghost_rect or "anchor_y" not in ghost_rect:
        raise ValueError("certified blueprint empty_rect requires anchor_x and anchor_y")
    anchor_x = int(ghost_rect.get("anchor_x"))
    anchor_y = int(ghost_rect.get("anchor_y"))
    if anchor_x < 0 or anchor_y < 0:
        raise ValueError("certified blueprint empty_rect anchor must be non-negative")
    return anchor_x, anchor_y


def build_canonical_blueprint_payload(
    *,
    placement_solution: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    ghost_rect: Mapping[str, Any],
    routing_solution: Optional[Sequence[Mapping[str, Any]]] = None,
    solve_time_seconds: float = 0.0,
    benders_iterations: int = 0,
    export_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    facility_pools = coerce_facility_pools_payload(facility_pools)
    payload = {
        "metadata": {
            "version": BLUEPRINT_SCHEMA_VERSION,
            "solve_time_seconds": round(float(solve_time_seconds), 6),
            "benders_iterations": int(benders_iterations),
            "export_timestamp": export_timestamp or _now_export_timestamp(),
        },
        "objective_achieved": {
            "empty_rect": {
                "w": int(ghost_rect.get("w", 0)),
                "h": int(ghost_rect.get("h", 0)),
                "anchor_x": int(ghost_rect.get("anchor_x", -1)),
                "anchor_y": int(ghost_rect.get("anchor_y", -1)),
                "score": float(ghost_rect.get("area", int(ghost_rect.get("w", 0)) * int(ghost_rect.get("h", 0)))),
            }
        },
        "facilities": _build_facilities(placement_solution, facility_pools),
        "routing_network": _build_routing_network(routing_solution or []),
    }
    return normalize_blueprint_payload(payload)


def build_blueprint_payload_from_certified_result(
    *,
    result: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    routing_solution: Optional[Sequence[Mapping[str, Any]]] = None,
    export_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    search_stats = result.get("search_stats", {})
    if not isinstance(search_stats, Mapping):
        search_stats = {}
    ghost_rect = _mapping_or_empty(result.get("ghost_rect"))
    _certified_empty_rect_anchor(ghost_rect)
    resolved_routing_solution = (
        _routing_solution_from_result(result)
        if routing_solution is None
        else _coerce_routing_solution(routing_solution)
    )
    return build_canonical_blueprint_payload(
        placement_solution=_mapping_or_empty(result.get("placement_solution")),
        facility_pools=facility_pools,
        ghost_rect=ghost_rect,
        routing_solution=resolved_routing_solution,
        solve_time_seconds=float(search_stats.get("solve_time_seconds", 0.0)),
        benders_iterations=int(search_stats.get("benders_iterations", 0)),
        export_timestamp=export_timestamp,
    )


def serialize_blueprint_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(normalize_blueprint_payload(payload), indent=2, ensure_ascii=False) + "\n"


def _is_canonical_blueprint_output_path(output_path: Path) -> bool:
    parts = Path(output_path).resolve().parts
    return len(parts) >= 3 and parts[-3:] == (
        "data",
        "blueprints",
        "optimal_blueprint.json",
    )


def write_blueprint_payload(output_path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    if _is_canonical_blueprint_output_path(output_path):
        raise ValueError(
            "canonical optimal_blueprint.json writes must use the verified certified publisher"
        )
    normalized = normalize_blueprint_payload(payload)
    atomic_write_json(output_path, normalized)
    return normalized


def export_certified_blueprint(
    *,
    project_root: Path,
    result: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    routing_solution: Optional[Sequence[Mapping[str, Any]]] = None,
    output_path: Optional[Path] = None,
) -> Tuple[Path, Dict[str, Any]]:
    target_path = output_path or blueprint_output_path(project_root)
    if Path(target_path).resolve() == blueprint_output_path(Path(project_root)).resolve():
        raise ValueError(
            "canonical certified blueprint writes must use the verified publisher"
        )
    payload = build_blueprint_payload_from_certified_result(
        result=result,
        facility_pools=facility_pools,
        routing_solution=routing_solution,
    )
    normalized = write_blueprint_payload(target_path, payload)
    return target_path, normalized


def coerce_facility_pools_payload(
    payload: Mapping[str, Any],
) -> Dict[str, Sequence[Mapping[str, Any]]]:
    if not isinstance(payload, Mapping):
        raise TypeError("facility_pools payload must be a mapping")
    raw_pools = payload.get("facility_pools")
    if isinstance(raw_pools, Mapping):
        return {
            str(template): list(pool) if isinstance(pool, Sequence) else []
            for template, pool in raw_pools.items()
        }
    return {
        str(template): list(pool) if isinstance(pool, Sequence) else []
        for template, pool in payload.items()
    }


def recover_legacy_render_payload_from_blueprint(
    *,
    blueprint_payload: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    normalized_pools = coerce_facility_pools_payload(facility_pools)
    pose_lookup = build_pose_lookup(normalized_pools)
    placement_solution: Dict[str, Dict[str, Any]] = {}

    for facility in normalized_blueprint["facilities"]:
        key = pose_lookup_key(
            facility_type=str(facility["facility_type"]),
            anchor_x=int(facility["anchor"]["x"]),
            anchor_y=int(facility["anchor"]["y"]),
            orientation=int(facility["orientation"]),
            port_mode=str(facility["port_mode"]),
        )
        matches = pose_lookup.get(key, ())
        if not matches:
            raise ValueError(
                "no pose match for blueprint facility "
                f"{facility['instance_id']} using recovery key {key!r}"
            )
        if len(matches) > 1:
            raise ValueError(
                "ambiguous pose match for blueprint facility "
                f"{facility['instance_id']} using recovery key {key!r}"
            )
        pose_idx, pose = matches[0]
        placement_solution[str(facility["instance_id"])] = {
            "pose_idx": int(pose_idx),
            "pose_id": str(pose.get("pose_id", "")),
            "anchor": {
                "x": int(facility["anchor"]["x"]),
                "y": int(facility["anchor"]["y"]),
            },
            "facility_type": str(facility["facility_type"]),
            "orientation": int(facility["orientation"]),
            "port_mode": str(facility["port_mode"]),
        }

    empty_rect = normalized_blueprint["objective_achieved"]["empty_rect"]
    return {
        "ghost_rect": {
            "w": int(empty_rect["w"]),
            "h": int(empty_rect["h"]),
            "area": int(round(float(empty_rect["score"]))),
            "anchor_x": int(empty_rect["anchor_x"]),
            "anchor_y": int(empty_rect["anchor_y"]),
        },
        "placement_solution": placement_solution,
        # Blueprint recovery is a render-compatibility projection, not a proof
        # replay.  It must never mint a proof-bearing exact status on its own.
        "search_status": "UNKNOWN",
        "search_stats": {
            "output_contract_source": "optimal_blueprint.json",
            "blueprint_version": str(normalized_blueprint["metadata"]["version"]),
        },
    }


def build_pose_lookup(
    facility_pools: Mapping[str, Any],
) -> Dict[Tuple[str, int, int, int, str], Tuple[Tuple[int, Mapping[str, Any]], ...]]:
    normalized_pools = coerce_facility_pools_payload(facility_pools)
    pose_lookup: Dict[Tuple[str, int, int, int, str], list[Tuple[int, Mapping[str, Any]]]] = {}
    for facility_type, pool in normalized_pools.items():
        for pose_idx, raw_pose in enumerate(pool):
            pose = _mapping_or_empty(raw_pose)
            pose_params = _mapping_or_empty(pose.get("pose_params"))
            anchor = _mapping_or_empty(pose.get("anchor"))
            key = pose_lookup_key(
                facility_type=str(facility_type),
                anchor_x=int(anchor.get("x", 0)),
                anchor_y=int(anchor.get("y", 0)),
                orientation=int(pose_params.get("orientation", 0)),
                port_mode=str(pose_params.get("port_mode", "default")),
            )
            pose_lookup.setdefault(key, []).append((int(pose_idx), pose))
    return {key: tuple(matches) for key, matches in pose_lookup.items()}


def pose_lookup_key(
    *,
    facility_type: str,
    anchor_x: int,
    anchor_y: int,
    orientation: int,
    port_mode: str,
) -> Tuple[str, int, int, int, str]:
    return (
        str(facility_type),
        int(anchor_x),
        int(anchor_y),
        int(orientation),
        str(port_mode),
    )


def _build_facilities(
    placement_solution: Mapping[str, Any],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[Dict[str, Any]]:
    facilities: list[Dict[str, Any]] = []
    for instance_id in sorted(str(key) for key in placement_solution.keys()):
        if instance_id == "ghost_pick":
            continue
        solution_entry = _mapping_or_empty(placement_solution.get(instance_id))
        facility_type = str(solution_entry.get("facility_type", "unknown"))
        pose_idx = int(solution_entry.get("pose_idx", 0))
        pose = _resolve_pose(
            facility_pools=facility_pools,
            facility_type=facility_type,
            pose_idx=pose_idx,
            solution_entry=solution_entry,
        )
        pose_params = _mapping_or_empty(pose.get("pose_params"))
        facilities.append(
            {
                "instance_id": instance_id,
                "facility_type": facility_type,
                "anchor": _resolve_anchor(solution_entry, pose),
                "orientation": int(pose_params.get("orientation", 0)),
                "port_mode": str(pose_params.get("port_mode", "default")),
                "active_ports": _build_active_ports(pose),
            }
        )
    return facilities


def _build_active_ports(pose: Mapping[str, Any]) -> list[Dict[str, Any]]:
    # 导出语义标注 (front 错位事故批 2): 口的 x/y 是 identity 语义——stored
    # 坐标即口前带子格(本体外第 1 格), 不是口的体上格; 下游消费者不得再
    # +方向 delta 推 front。
    ports: list[Dict[str, Any]] = []
    for port_type, field_name in (("input", "input_port_cells"), ("output", "output_port_cells")):
        raw_ports = pose.get(field_name)
        if not isinstance(raw_ports, list):
            continue
        for raw_port in raw_ports:
            port_entry = _normalize_port(raw_port)
            if port_entry is None:
                continue
            ports.append(
                {
                    "type": port_type,
                    "x": port_entry["x"],
                    "y": port_entry["y"],
                    "dir": port_entry["dir"],
                    "commodity": port_entry["commodity"],
                }
            )
    return ports


def _build_routing_network(
    routing_solution: Sequence[Mapping[str, Any]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    l0: Dict[str, Dict[str, Any]] = {}
    l1: Dict[str, Dict[str, Any]] = {}
    for raw_segment in routing_solution:
        segment = _mapping_or_empty(raw_segment)
        x = int(segment.get("x", 0))
        y = int(segment.get("y", 0))
        layer = int(segment.get("layer", 0))
        key = f"{x},{y}"
        flow_in = _normalize_flow_list(segment.get("flow_in"), fallback_key="dir_in", segment=segment)
        flow_out = _normalize_flow_list(segment.get("flow_out"), fallback_key="dir_out", segment=segment)

        if "component_type" in segment:
            component_type = str(segment.get("component_type", "belt"))
        elif layer == 1:
            component_type = "bridge"
        else:
            component_type = "belt"

        commodities, uses = _segment_commodities_and_uses(
            segment,
            default_flow_in=flow_in,
            default_flow_out=flow_out,
        )
        entry = _routing_entry(
            component_type=component_type,
            flow_in=flow_in,
            flow_out=flow_out,
            commodities=commodities,
            uses=uses,
        )
        layer_map = l1 if layer == 1 else l0
        existing = layer_map.get(key)
        if existing is None:
            layer_map[key] = entry
            continue
        existing_pattern = (
            str(existing.get("type", "")),
            tuple(existing.get("flow_in", [])),
            tuple(existing.get("flow_out", [])),
        )
        incoming_pattern = (component_type, tuple(flow_in), tuple(flow_out))
        if existing_pattern != incoming_pattern:
            raise ValueError(
                "multiple physical routing patterns for "
                f"cell ({x},{y}) layer {layer}: {existing_pattern!r} vs {incoming_pattern!r}"
            )
        layer_map[key] = _routing_entry(
            component_type=component_type,
            flow_in=flow_in,
            flow_out=flow_out,
            commodities=sorted({str(item) for item in existing["commodities"]} | set(commodities)),
            uses=_merge_routing_uses(existing["uses"], uses),
        )
    return {"L0_ground": l0, "L1_elevated": l1}


def _normalize_flow_list(raw: Any, *, fallback_key: str, segment: Mapping[str, Any]) -> list[str]:
    if isinstance(raw, list):
        return _sort_directions([str(item) for item in raw])
    fallback = segment.get(fallback_key)
    if fallback is None:
        return []
    return _sort_directions([str(fallback)])


def _sort_directions(values: list[str]) -> list[str]:
    return sorted(values, key=lambda value: _DIRECTION_ORDER.get(value, 99))


def _segment_commodities_and_uses(
    segment: Mapping[str, Any],
    *,
    default_flow_in: list[str],
    default_flow_out: list[str],
) -> tuple[list[str], list[Dict[str, Any]]]:
    raw_commodities = segment.get("commodities")
    if isinstance(raw_commodities, list):
        commodities = sorted({str(item) for item in raw_commodities})
        if not commodities:
            raise ValueError("routing segment commodities must be non-empty")
    else:
        commodities = [str(segment.get("commodity", "[TBD]"))]

    raw_uses = segment.get("uses")
    if raw_uses is None:
        if len(commodities) > 1:
            raise ValueError("mixed-commodity routing segments require uses witnesses")
        uses = [
            {
                "commodity": commodities[0],
                "flow_in": list(default_flow_in),
                "flow_out": list(default_flow_out),
            }
        ]
    elif isinstance(raw_uses, list):
        uses = []
        for raw_use in raw_uses:
            if not isinstance(raw_use, Mapping):
                raise ValueError("routing segment use must be a mapping")
            if "commodity" not in raw_use:
                raise ValueError("routing segment use commodity is required")
            uses.append(
                {
                    "commodity": str(raw_use["commodity"]),
                    "flow_in": _normalize_flow_list(raw_use.get("flow_in"), fallback_key="dir_in", segment=raw_use),
                    "flow_out": _normalize_flow_list(raw_use.get("flow_out"), fallback_key="dir_out", segment=raw_use),
                }
            )
        uses = _merge_routing_uses(uses)
    else:
        raise ValueError("routing segment uses must be a list")

    use_commodities = sorted({str(use["commodity"]) for use in uses})
    if use_commodities != commodities:
        raise ValueError("routing segment commodities must match uses commodities")
    return commodities, uses


def _routing_entry(
    *,
    component_type: str,
    flow_in: list[str],
    flow_out: list[str],
    commodities: list[str],
    uses: list[Mapping[str, Any]],
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "type": str(component_type),
        "commodities": list(commodities),
        "uses": [dict(use) for use in uses],
        "flow_in": list(flow_in),
        "flow_out": list(flow_out),
    }
    if len(commodities) == 1:
        entry["commodity"] = commodities[0]
    return entry


def _merge_routing_uses(
    *use_groups: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    merged: dict[tuple[str, tuple[str, ...], tuple[str, ...]], Dict[str, Any]] = {}
    for uses in use_groups:
        for raw_use in uses:
            commodity = str(raw_use["commodity"])
            flow_in = _sort_directions([str(item) for item in raw_use.get("flow_in", [])])
            flow_out = _sort_directions([str(item) for item in raw_use.get("flow_out", [])])
            key = (commodity, tuple(flow_in), tuple(flow_out))
            merged[key] = {
                "commodity": commodity,
                "flow_in": flow_in,
                "flow_out": flow_out,
            }
    return [
        merged[key]
        for key in sorted(merged)
    ]


def _routing_solution_from_result(result: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    if "routing_solution" in result:
        return _coerce_routing_solution(result.get("routing_solution"))
    if "routing_network" in result:
        routing_network = result.get("routing_network")
        if routing_network in (None, {}):
            return []
        raise ValueError(
            "certified result routing_network is not a blueprint-projectable routing_solution"
        )
    return []


def _coerce_routing_solution(raw: Any) -> Sequence[Mapping[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("routing_solution must be a sequence of mapping segments")
    segments: list[Mapping[str, Any]] = []
    for index, segment in enumerate(raw):
        if not isinstance(segment, Mapping):
            raise ValueError(f"routing_solution segment {index} must be a mapping")
        segments.append(dict(segment))
    return segments


def _resolve_pose(
    *,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    facility_type: str,
    pose_idx: int,
    solution_entry: Mapping[str, Any],
) -> Mapping[str, Any]:
    pool = facility_pools.get(facility_type)
    if isinstance(pool, Sequence) and 0 <= pose_idx < len(pool):
        pose = pool[pose_idx]
        if isinstance(pose, Mapping):
            return pose
    return {
        "anchor": _mapping_or_empty(solution_entry.get("anchor")),
        "pose_params": {
            "orientation": int(solution_entry.get("orientation", 0)),
            "port_mode": str(solution_entry.get("port_mode", "default")),
        },
        "input_port_cells": [],
        "output_port_cells": [],
    }


def _resolve_anchor(solution_entry: Mapping[str, Any], pose: Mapping[str, Any]) -> Dict[str, int]:
    anchor = solution_entry.get("anchor")
    if isinstance(anchor, Mapping):
        return {"x": int(anchor.get("x", 0)), "y": int(anchor.get("y", 0))}
    pose_anchor = pose.get("anchor")
    if isinstance(pose_anchor, Mapping):
        return {"x": int(pose_anchor.get("x", 0)), "y": int(pose_anchor.get("y", 0))}
    return {"x": 0, "y": 0}


def _normalize_port(raw_port: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw_port, Mapping):
        return {
            "x": int(raw_port.get("x", 0)),
            "y": int(raw_port.get("y", 0)),
            "dir": str(raw_port.get("dir", "N")),
            "commodity": str(raw_port.get("commodity", "[TBD]")),
        }
    return None


def _mapping_or_empty(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw
    return {}


def _now_export_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

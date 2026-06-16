"""Canonical blueprint output contract helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Tuple

BLUEPRINT_SCHEMA_VERSION = "1.0.0"
BLUEPRINT_FILENAME = "optimal_blueprint.json"
_VALID_PORT_TYPES = {"input", "output"}
_VALID_DIRECTIONS = {"N", "S", "E", "W"}
_VALID_COMPONENT_TYPES = {"belt", "splitter", "merger", "bridge"}


def blueprint_output_path(project_root: Path) -> Path:
    return project_root / "data" / "blueprints" / BLUEPRINT_FILENAME


def validate_blueprint_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a blueprint payload into canonical JSON-safe order."""
    return normalize_blueprint_payload(payload)


def normalize_blueprint_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("blueprint payload must be a mapping")

    return {
        "metadata": _normalize_metadata(payload.get("metadata")),
        "objective_achieved": _normalize_objective(payload.get("objective_achieved")),
        "facilities": _normalize_facilities(payload.get("facilities")),
        "routing_network": _normalize_routing_network(payload.get("routing_network")),
    }


def _normalize_metadata(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("metadata must be a mapping")
    export_timestamp = str(raw.get("export_timestamp", "")).strip()
    if not export_timestamp:
        raise ValueError("metadata.export_timestamp is required")
    return {
        "version": str(raw.get("version", BLUEPRINT_SCHEMA_VERSION)),
        "solve_time_seconds": round(float(raw.get("solve_time_seconds", 0.0)), 6),
        "benders_iterations": int(raw.get("benders_iterations", 0)),
        "export_timestamp": export_timestamp,
    }


def _normalize_objective(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("objective_achieved must be a mapping")
    empty_rect = raw.get("empty_rect")
    if not isinstance(empty_rect, Mapping):
        raise ValueError("objective_achieved.empty_rect must be a mapping")
    width = int(empty_rect.get("w", 0))
    height = int(empty_rect.get("h", 0))
    if width < 0 or height < 0:
        raise ValueError("objective_achieved.empty_rect dimensions must be non-negative")
    return {
        "empty_rect": {
            "w": width,
            "h": height,
            "anchor_x": int(empty_rect.get("anchor_x", -1)),
            "anchor_y": int(empty_rect.get("anchor_y", -1)),
            "score": float(empty_rect.get("score", width * height)),
        }
    }


def _normalize_facilities(raw: Any) -> list[Dict[str, Any]]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError("facilities must be a list")

    facilities = [_normalize_facility(entry) for entry in raw]
    facilities.sort(
        key=lambda entry: (
            str(entry["instance_id"]),
            str(entry["facility_type"]),
            int(entry["anchor"]["x"]),
            int(entry["anchor"]["y"]),
        )
    )
    return facilities


def _normalize_facility(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("facility entry must be a mapping")
    active_ports = raw.get("active_ports")
    if active_ports is None:
        active_ports = []
    if not isinstance(active_ports, list):
        raise ValueError("facility.active_ports must be a list")

    return {
        "instance_id": str(raw.get("instance_id", "")).strip(),
        "facility_type": str(raw.get("facility_type", "")).strip(),
        "anchor": _normalize_anchor(raw.get("anchor"), field_name="facility.anchor"),
        "orientation": int(raw.get("orientation", 0)),
        "port_mode": str(raw.get("port_mode", "default")),
        "active_ports": _normalize_active_ports(active_ports),
    }


def _normalize_active_ports(raw_ports: Iterable[Any]) -> list[Dict[str, Any]]:
    ports = [_normalize_active_port(port) for port in raw_ports]
    ports.sort(
        key=lambda entry: (
            0 if entry["type"] == "input" else 1,
            int(entry["x"]),
            int(entry["y"]),
            str(entry["dir"]),
            str(entry["commodity"]),
        )
    )
    return ports


def _normalize_active_port(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("active port entry must be a mapping")
    port_type = str(raw.get("type", "")).strip()
    direction = str(raw.get("dir", "")).strip()
    if port_type not in _VALID_PORT_TYPES:
        raise ValueError(f"invalid active port type: {port_type}")
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"invalid active port dir: {direction}")
    return {
        "type": port_type,
        "x": int(raw.get("x", 0)),
        "y": int(raw.get("y", 0)),
        "dir": direction,
        "commodity": str(raw.get("commodity", "[TBD]")),
    }


def _normalize_routing_network(raw: Any) -> Dict[str, Dict[str, Dict[str, Any]]]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError("routing_network must be a mapping")

    l0_raw = raw.get("L0_ground")
    l1_raw = raw.get("L1_elevated")
    if l0_raw is None:
        l0_raw = {}
    if l1_raw is None:
        l1_raw = {}
    if not isinstance(l0_raw, Mapping) or not isinstance(l1_raw, Mapping):
        raise ValueError("routing_network layers must be mappings")

    return {
        "L0_ground": _normalize_routing_layer(l0_raw, layer_name="L0_ground"),
        "L1_elevated": _normalize_routing_layer(l1_raw, layer_name="L1_elevated"),
    }


def _normalize_routing_layer(
    raw_layer: Mapping[str, Any],
    *,
    layer_name: str,
) -> Dict[str, Dict[str, Any]]:
    normalized_items = []
    for raw_key, raw_value in raw_layer.items():
        x, y = _parse_coord_key(raw_key)
        normalized_items.append(((x, y), _normalize_routing_cell(raw_value, layer_name=layer_name)))

    normalized_items.sort(key=lambda item: (item[0][0], item[0][1]))
    return {
        f"{x},{y}": value
        for (x, y), value in normalized_items
    }


def _normalize_routing_cell(raw: Any, *, layer_name: str) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{layer_name} cell must be a mapping")
    component_type = str(raw.get("type", "")).strip()
    if component_type not in _VALID_COMPONENT_TYPES:
        raise ValueError(f"invalid routing component type: {component_type}")
    if layer_name == "L1_elevated" and component_type != "bridge":
        raise ValueError("L1_elevated cells must use bridge components")

    flow_in = _normalize_direction_list(raw.get("flow_in", []))
    flow_out = _normalize_direction_list(raw.get("flow_out", []))
    return {
        "type": component_type,
        "commodity": str(raw.get("commodity", "[TBD]")),
        "flow_in": flow_in,
        "flow_out": flow_out,
    }


def _normalize_direction_list(raw: Any) -> list[str]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError("routing flow direction set must be a list")
    values = [str(item).strip() for item in raw]
    for value in values:
        if value not in _VALID_DIRECTIONS:
            raise ValueError(f"invalid routing direction: {value}")
    order = {"N": 0, "E": 1, "S": 2, "W": 3}
    return sorted(values, key=lambda value: order[value])


def _normalize_anchor(raw: Any, *, field_name: str) -> Dict[str, int]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    x = int(raw.get("x", 0))
    y = int(raw.get("y", 0))
    if x < 0 or y < 0 or x > 69 or y > 69:
        raise ValueError(f"{field_name} out of 70x70 grid bounds")
    return {"x": x, "y": y}


def _parse_coord_key(raw_key: Any) -> Tuple[int, int]:
    try:
        text = str(raw_key)
        x_text, y_text = text.split(",", 1)
        return int(x_text), int(y_text)
    except Exception as exc:
        raise ValueError(f"invalid routing coordinate key: {raw_key}") from exc

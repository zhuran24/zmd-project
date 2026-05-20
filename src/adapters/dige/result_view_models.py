"""Viewer-facing result cards and warnings inspired by product-layer calculators."""

from __future__ import annotations

from typing import Any, Mapping


def build_result_cards(report_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    layout = _mapping(report_payload.get("layout"))
    ports = _mapping(report_payload.get("ports"))
    routing = _mapping(report_payload.get("routing"))
    power = _mapping(report_payload.get("power"))
    ghost = _mapping(layout.get("ghost_rect"))

    return [
        {
            "id": "layout",
            "title": "Layout",
            "primary": f"{int(layout.get('facility_count', 0))} facilities",
            "secondary": f"{int(layout.get('occupied_cells', 0))}/4900 occupied · {float(layout.get('fill_ratio', 0.0))*100:.1f}% fill",
        },
        {
            "id": "ghost",
            "title": "Ghost Rectangle",
            "primary": f"{int(ghost.get('w', 0))}×{int(ghost.get('h', 0))} = {int(round(float(ghost.get('score', 0.0))))}",
            "secondary": f"anchor ({int(ghost.get('anchor_x', -1))}, {int(ghost.get('anchor_y', -1))})",
        },
        {
            "id": "routing",
            "title": "Routing",
            "primary": (
                f"L0 {int(_mapping(routing.get('L0_ground')).get('cell_count', 0))} cells · "
                f"L1 {int(_mapping(routing.get('L1_elevated')).get('cell_count', 0))} cells"
            ),
            "secondary": f"total {int(routing.get('total_cells', 0))} routing cells",
        },
        {
            "id": "ports",
            "title": "Ports",
            "primary": f"{int(ports.get('total_active_ports', 0))} active ports",
            "secondary": f"inputs {int(ports.get('input_ports', 0))} · outputs {int(ports.get('output_ports', 0))}",
        },
        {
            "id": "power",
            "title": "Power",
            "primary": f"{int(power.get('pole_count', 0))} poles · {int(power.get('coverage_cells', 0))} covered cells",
            "secondary": f"covered facilities {int(power.get('covered_needs_power_facilities', 0))}/{int(power.get('needs_power_facilities', 0))}",
        },
    ]


def build_result_warnings(report_payload: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    layout = _mapping(report_payload.get("layout"))
    ports = _mapping(report_payload.get("ports"))
    routing = _mapping(report_payload.get("routing"))
    power = _mapping(report_payload.get("power"))

    if int(ports.get("total_active_ports", 0)) == 0:
        warnings.append("No active ports were recovered from the canonical blueprint payload.")
    if int(_mapping(routing.get("L0_ground")).get("cell_count", 0)) == 0 and int(_mapping(routing.get("L1_elevated")).get("cell_count", 0)) > 0:
        warnings.append("Elevated routing exists without any visible ground-layer routing cells.")
    if int(power.get("needs_power_facilities", 0)) > int(power.get("covered_needs_power_facilities", 0)):
        warnings.append("Some facilities marked as needing power are not covered by any selected power pole footprint.")
    if int(_mapping(layout.get("ghost_rect")).get("score", 0)) <= 0:
        warnings.append("Ghost rectangle score is zero; check whether the blueprint objective payload was populated.")
    return warnings


def build_viewer_defaults() -> dict[str, Any]:
    return {
        "layers": {
            "bodies": True,
            "power": True,
            "ghost": True,
            "grid": True,
            "routingGround": True,
            "routingElevated": True,
            "activePorts": True,
        },
        "pan_zoom": {
            "scale_mode": "fit_then_persist",
            "persist_state": True,
        },
        "cards": {
            "expanded": True,
            "warnings_expanded": True,
        },
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}

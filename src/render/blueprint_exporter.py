"""Blueprint exporter backed by the canonical output serializer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.adapters.industrial_planner.export_blueprint import (
    register_industrial_planner_exporter,
    write_industrial_planner_export_bundle,
)
from src.interchange.export_registry import ExportRegistry
from src.io.serializer import build_canonical_blueprint_payload, write_blueprint_payload


def export_blueprint(
    placement_solution: Mapping[str, Any],
    routing_solution: Optional[Sequence[Mapping[str, Any]]],
    ghost_rect: Mapping[str, Any],
    solve_time: float,
    benders_iterations: int,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    output_path: Path,
) -> Dict[str, Any]:
    """Export the canonical blueprint delivery artifact."""
    payload = build_canonical_blueprint_payload(
        placement_solution=placement_solution,
        routing_solution=routing_solution,
        ghost_rect=ghost_rect,
        solve_time_seconds=solve_time,
        benders_iterations=benders_iterations,
        facility_pools=facility_pools,
    )
    return write_blueprint_payload(output_path, payload)



def build_default_export_registry() -> ExportRegistry:
    registry = ExportRegistry()
    register_industrial_planner_exporter(registry)
    return registry


def export_target_blueprint(
    *,
    blueprint_payload: Mapping[str, Any],
    target: str,
    output_dir: Path,
    base_id: str | None = None,
) -> Dict[str, Any]:
    """Export the canonical blueprint into an additive downstream target bundle."""
    target = str(target).strip()
    if target == "industrial_planner":
        written = write_industrial_planner_export_bundle(
            output_dir=output_dir,
            blueprint_payload=blueprint_payload,
            base_id=base_id or "valley4_protocol_core",
        )
        return {
            "target": target,
            "blueprint_path": written.blueprint_path,
            "compatibility_manifest_path": written.compatibility_manifest_path,
            "validation_report_path": written.validation_report_path,
            "validation_report_markdown_path": written.validation_report_markdown_path,
            "throughput_report_path": written.throughput_report_path,
            "throughput_report_markdown_path": written.throughput_report_markdown_path,
            "warnings": list(written.warnings),
        }

    registry = build_default_export_registry()
    if not registry.has_target(target):
        raise KeyError(f"unknown export target: {target}")
    return dict(registry.export_target(target, blueprint_payload=blueprint_payload))

"""Probe adapter-side outer deployment plans against the real IndustrialPlanner validator."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Mapping, Sequence

from src.adapters.base_planner.outer_deployment_plan import (
    OuterBaseDeploymentPlan,
    PlanningDiagnostics,
)
from src.adapters.industrial_planner.deployment_transform import (
    materialize_outer_deployed_blueprint_payload,
    normalize_outer_deployment_plan,
)
from src.adapters.industrial_planner.blueprint_validator import validate_industrial_planner_blueprint
from src.adapters.industrial_planner.export_blueprint import (
    _build_boundary_input_bus_witness_devices,
    _build_boundary_output_bus_witness_devices,
    _parse_coord_key,
)
from src.adapters.industrial_planner.mapping_registry import (
    INDUSTRIAL_PLANNER_BLUEPRINT_COMPAT_VERSION,
    INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA,
    INDUSTRIAL_PLANNER_BLUEPRINT_VERSION,
    resolve_facility_device,
    resolve_routing_device,
)
from src.io.output_schema import normalize_blueprint_payload


@dataclass(frozen=True)
class OuterExportProbeBundle:
    deployment_plan: OuterBaseDeploymentPlan
    transformed_blueprint_payload: dict[str, Any]
    export_blueprint: dict[str, Any]
    validation_report: dict[str, Any]
    validation_report_markdown: str
    status: str
    blocker_classification: str | None
    error_message: str | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blocker_classification": self.blocker_classification,
            "error_message": self.error_message,
            "warnings": list(self.warnings),
            "validation_report": self.validation_report,
            "base_id": self.deployment_plan.base_id,
            "inner_island_origin": self.deployment_plan.inner_island_origin.to_dict(),
            "boundary_assignment_count": len(self.deployment_plan.boundary_assignments),
            "connector_reservation_count": len(self.deployment_plan.connector_reservations),
            "witness_reservation_count": len(self.deployment_plan.witness_reservations),
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Outer Export Probe",
            "",
            f"- Status: `{self.status}`",
            f"- Blocker classification: `{self.blocker_classification or '-'}`",
            f"- Base id: `{self.deployment_plan.base_id}`",
            f"- Inner island origin: ({self.deployment_plan.inner_island_origin.x}, {self.deployment_plan.inner_island_origin.y})",
            f"- Validator import-compatible: {self.validation_report.get('is_import_compatible')}",
            f"- Validator layout-healthy: {self.validation_report.get('is_layout_healthy')}",
            f"- Boundary assignments: {len(self.deployment_plan.boundary_assignments)}",
            f"- Connector reservations: {len(self.deployment_plan.connector_reservations)}",
            f"- Witness reservations: {len(self.deployment_plan.witness_reservations)}",
        ]
        if self.error_message:
            lines.extend(["", "## Error", "", self.error_message])
        errors = []
        for key in (
            "lot_boundary_errors",
            "placement_constraint_errors",
            "overlap_errors",
            "port_mismatch_errors",
        ):
            errors.extend(str(entry) for entry in self.validation_report.get(key, ()) if str(entry).strip())
        if errors:
            lines.extend(["", "## Validator errors", ""])
            lines.extend(f"- {entry}" for entry in errors[:20])
        if self.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {entry}" for entry in self.warnings)
        lines.append("")
        return "\n".join(lines)


def probe_outer_deployment_plan(
    *,
    blueprint_payload: Mapping[str, Any],
    deployment_plan: OuterBaseDeploymentPlan | Mapping[str, Any],
    export_name: str | None = None,
) -> OuterExportProbeBundle:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    plan = normalize_outer_deployment_plan(deployment_plan)
    transformed_blueprint = materialize_outer_deployed_blueprint_payload(
        blueprint_payload=normalized_blueprint,
        deployment_plan=plan,
    )

    warnings: list[str] = []
    primary_facility_devices: list[dict[str, Any]] = []
    auxiliary_facility_devices: list[dict[str, Any]] = []
    routing_devices: list[dict[str, Any]] = []

    for facility in transformed_blueprint["facilities"]:
        resolved = resolve_facility_device(facility, default_base_id=plan.base_id)
        warnings.extend(str(entry) for entry in resolved.warnings if str(entry).strip())
        device = resolved.to_device()
        if device is not None:
            primary_facility_devices.append(device)
        auxiliary_facility_devices.extend(dict(entry) for entry in resolved.auxiliary_devices)

    routing_network = transformed_blueprint.get("routing_network") if isinstance(transformed_blueprint.get("routing_network"), Mapping) else {}
    for layer_name in ("L0_ground", "L1_elevated"):
        layer = routing_network.get(layer_name) if isinstance(routing_network.get(layer_name), Mapping) else {}
        for coord_key, cell in layer.items():
            x, y = _parse_coord_key(str(coord_key))
            resolved_routing = resolve_routing_device(x=x, y=y, layer_name=layer_name, cell=cell)
            warnings.extend(str(entry) for entry in resolved_routing.warnings if str(entry).strip())
            routing_devices.append(resolved_routing.to_device())

    boundary_output_bus_witness_devices, boundary_output_bus_witness_warnings = _build_boundary_output_bus_witness_devices(
        blueprint_payload=transformed_blueprint,
        primary_facility_devices=primary_facility_devices,
        auxiliary_facility_devices=auxiliary_facility_devices,
        routing_devices=routing_devices,
        base_id=plan.base_id,
    )
    auxiliary_facility_devices.extend(boundary_output_bus_witness_devices)
    warnings.extend(str(entry) for entry in boundary_output_bus_witness_warnings if str(entry).strip())

    boundary_input_bus_witness_devices, boundary_input_bus_witness_warnings = _build_boundary_input_bus_witness_devices(
        blueprint_payload=transformed_blueprint,
        primary_facility_devices=primary_facility_devices,
        auxiliary_facility_devices=auxiliary_facility_devices,
        routing_devices=routing_devices,
        base_id=plan.base_id,
    )
    auxiliary_facility_devices.extend(boundary_input_bus_witness_devices)
    warnings.extend(str(entry) for entry in boundary_input_bus_witness_warnings if str(entry).strip())

    devices = [*primary_facility_devices, *auxiliary_facility_devices, *routing_devices]
    devices.sort(
        key=lambda entry: (
            int(entry["origin"]["x"]),
            int(entry["origin"]["y"]),
            str(entry["typeId"]),
            int(entry.get("rotation", 0)),
        )
    )

    export_timestamp = str(normalized_blueprint["metadata"]["export_timestamp"])
    export_hash = hashlib.sha256(
        json.dumps(normalized_blueprint, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    export_blueprint = {
        "schema": INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA,
        "id": f"OuterExport-{export_hash}",
        "version": INDUSTRIAL_PLANNER_BLUEPRINT_VERSION,
        "name": str(export_name or f"Outer Export {export_timestamp}"),
        "createdAt": export_timestamp,
        "baseId": str(plan.base_id),
        "devices": devices,
        "blueprintVersion": INDUSTRIAL_PLANNER_BLUEPRINT_COMPAT_VERSION,
    }
    validation_report_obj = validate_industrial_planner_blueprint(export_blueprint)
    validation_report = validation_report_obj.to_dict()
    validation_report_markdown = validation_report_obj.to_markdown()

    status, blocker_classification, error_message = _classify_probe_outcome(
        deployment_plan=plan,
        validation_report=validation_report,
        warnings=tuple(sorted(set(warnings))),
    )
    diagnostics = PlanningDiagnostics(
        exporter_status=("validator_clean_outer_export" if validation_report.get("is_import_compatible") else status),
        validator_import_compatible=bool(validation_report.get("is_import_compatible")),
        validator_layout_healthy=bool(validation_report.get("is_layout_healthy")),
        throughput_status=None,
        validation_probe_count=1,
        warnings=tuple(sorted(set(warnings))),
    )
    updated_plan = replace(plan, diagnostics=diagnostics)

    return OuterExportProbeBundle(
        deployment_plan=updated_plan,
        transformed_blueprint_payload=transformed_blueprint,
        export_blueprint=export_blueprint,
        validation_report=validation_report,
        validation_report_markdown=validation_report_markdown,
        status=status,
        blocker_classification=blocker_classification,
        error_message=error_message,
        warnings=tuple(sorted(set(warnings))),
    )



def _classify_probe_outcome(
    *,
    deployment_plan: OuterBaseDeploymentPlan,
    validation_report: Mapping[str, Any],
    warnings: Sequence[str],
) -> tuple[str, str | None, str | None]:
    if bool(validation_report.get("is_import_compatible")) and bool(validation_report.get("is_layout_healthy")):
        return "validator_clean_outer_export", None, None

    placement_errors = tuple(str(entry) for entry in validation_report.get("placement_constraint_errors", ()) if str(entry).strip())
    lot_boundary_errors = tuple(str(entry) for entry in validation_report.get("lot_boundary_errors", ()) if str(entry).strip())
    has_bus_edge_contact_failure = any(
        "edge_contact rule" in entry and "adjacency to bus" in entry
        for entry in [*placement_errors, *lot_boundary_errors]
    )
    if has_bus_edge_contact_failure:
        foundation_desc = ", ".join(deployment_plan.foundation_bus_edges) if deployment_plan.foundation_bus_edges else "(none)"
        return (
            "true_edge_witness_geometry_shortfall",
            "true_edge_witness_geometry_shortfall",
            (
                f"outer deployment reached the true lot edge for base {deployment_plan.base_id!r}, "
                f"but validator import still fails because the selected boundary geometry needs bus-side witness coverage "
                f"that the base cannot supply. Foundation bus edges: {foundation_desc}."
            ),
        )

    return (
        "validator_layout_conflict",
        "validator_layout_conflict",
        "outer deployment exported a translated blueprint, but the real IndustrialPlanner validator still reports placement/layout conflicts",
    )


__all__ = [
    "OuterExportProbeBundle",
    "materialize_outer_deployed_blueprint_payload",
    "probe_outer_deployment_plan",
]

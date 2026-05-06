"""Adapter-side outer deployment planning for larger IndustrialPlanner bases.

This module deliberately stays outside the certified solver boundary. It keeps
canonical 70x70 blueprint coordinates intact and emits a sidecar describing how
those canonical anchors would be deployed into a larger real base.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.adapters.industrial_planner.blueprint_validator import load_static_registries
from src.adapters.industrial_planner.mapping_registry import (
    _loader_input_port_geometry,
    orientation_to_rotation,
    resolve_facility_device,
)
from src.io.output_schema import normalize_blueprint_payload

_PLAN_VERSION = "0.2.0"
_PLANNING_STATUS = "planned_outer_deployment"
_BOUNDARY_BUS_WITNESS_ROTATION = 90
_BOUNDARY_INPUT_BUS_STAGING_DEPTH = 4
_EDGE_DELTA = {
    "N": (0, -1),
    "S": (0, 1),
    "W": (-1, 0),
    "E": (1, 0),
}


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": int(self.x), "y": int(self.y)}


@dataclass(frozen=True)
class BoundaryDemandSummary:
    required_boundary_output_slots: int
    required_boundary_input_slots: int
    output_commodity_counts: tuple[tuple[str, int], ...] = ()
    input_commodity_counts: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_boundary_output_slots": int(self.required_boundary_output_slots),
            "required_boundary_input_slots": int(self.required_boundary_input_slots),
            "output_commodity_counts": {name: int(count) for name, count in self.output_commodity_counts},
            "input_commodity_counts": {name: int(count) for name, count in self.input_commodity_counts},
        }


@dataclass(frozen=True)
class BoundaryAssignment:
    canonical_instance_id: str
    commodity_id: str
    direction: str
    true_edge: str
    true_edge_position: int
    canonical_anchor: Point
    handoff_anchor: Point
    exported_anchor: Point
    exported_orientation: int
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_instance_id": str(self.canonical_instance_id),
            "commodity_id": str(self.commodity_id),
            "direction": str(self.direction),
            "true_edge": str(self.true_edge),
            "true_edge_position": int(self.true_edge_position),
            "canonical_anchor": self.canonical_anchor.to_dict(),
            "handoff_anchor": self.handoff_anchor.to_dict(),
            "exported_anchor": self.exported_anchor.to_dict(),
            "exported_rotation": int(self.exported_orientation),
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ConnectorReservation:
    reservation_id: str
    canonical_instance_id: str
    commodity_id: str
    true_edge: str
    handoff_anchor: Point
    true_edge_anchor: Point
    reserved_cells: tuple[Point, ...] = ()
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reservation_id": str(self.reservation_id),
            "canonical_instance_id": str(self.canonical_instance_id),
            "commodity_id": str(self.commodity_id),
            "true_edge": str(self.true_edge),
            "handoff_anchor": self.handoff_anchor.to_dict(),
            "true_edge_anchor": self.true_edge_anchor.to_dict(),
            "reserved_cells": [cell.to_dict() for cell in self.reserved_cells],
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class WitnessReservation:
    reservation_id: str
    witness_type_id: str
    purpose: str
    commodity_id: str
    required_for_instance_id: str
    origin: Point
    rotation: int
    reserved_cells: tuple[Point, ...] = ()
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reservation_id": str(self.reservation_id),
            "witness_type_id": str(self.witness_type_id),
            "purpose": str(self.purpose),
            "commodity_id": str(self.commodity_id),
            "required_for_instance_id": str(self.required_for_instance_id),
            "origin": self.origin.to_dict(),
            "rotation": int(self.rotation),
            "reserved_cells": [cell.to_dict() for cell in self.reserved_cells],
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ExportMapping:
    canonical_instance_id: str
    exported_type_id: str | None
    exported_origin: Point
    exported_rotation: int
    mapping_mode: str
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_instance_id": str(self.canonical_instance_id),
            "exported_type_id": self.exported_type_id,
            "exported_origin": self.exported_origin.to_dict(),
            "exported_rotation": int(self.exported_rotation),
            "mapping_mode": str(self.mapping_mode),
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PlanningDiagnostics:
    exporter_status: str = "not_run"
    validator_import_compatible: bool | None = None
    validator_layout_healthy: bool | None = None
    throughput_status: str | None = None
    validation_probe_count: int = 0
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "exporter_status": str(self.exporter_status),
            "validator_import_compatible": self.validator_import_compatible,
            "validator_layout_healthy": self.validator_layout_healthy,
            "throughput_status": self.throughput_status,
            "validation_probe_count": int(self.validation_probe_count),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class OuterBaseDeploymentPlan:
    plan_version: str
    planning_status: str
    base_id: str
    base_lot_size: int
    canonical_contract_size: int
    inner_island_origin: Point
    inner_island_size: int
    foundation_bus_edges: tuple[str, ...]
    boundary_demand_summary: BoundaryDemandSummary
    boundary_assignments: tuple[BoundaryAssignment, ...] = ()
    connector_reservations: tuple[ConnectorReservation, ...] = ()
    witness_reservations: tuple[WitnessReservation, ...] = ()
    export_mappings: tuple[ExportMapping, ...] = ()
    diagnostics: PlanningDiagnostics = field(default_factory=PlanningDiagnostics)
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def moat_thickness_by_edge(self) -> dict[str, int]:
        left = int(self.inner_island_origin.x)
        top = int(self.inner_island_origin.y)
        right = int(self.base_lot_size - self.inner_island_size - left)
        bottom = int(self.base_lot_size - self.inner_island_size - top)
        return {
            "top": top,
            "right": right,
            "bottom": bottom,
            "left": left,
        }

    @property
    def boundary_assignment_summary_by_edge(self) -> dict[str, dict[str, int]]:
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        for entry in self.boundary_assignments:
            counts[str(entry.true_edge)]["total"] += 1
            if entry.direction == "required_output":
                counts[str(entry.true_edge)]["outputs"] += 1
            elif entry.direction == "required_input":
                counts[str(entry.true_edge)]["inputs"] += 1
        return {
            edge: {
                "total": int(counter.get("total", 0)),
                "outputs": int(counter.get("outputs", 0)),
                "inputs": int(counter.get("inputs", 0)),
            }
            for edge, counter in sorted(counts.items())
        }

    @property
    def connector_summary_by_edge(self) -> dict[str, int]:
        counter = Counter(str(entry.true_edge) for entry in self.connector_reservations)
        return {edge: int(counter[edge]) for edge in sorted(counter)}

    @property
    def witness_summary_by_purpose(self) -> dict[str, int]:
        counter = Counter(str(entry.purpose) for entry in self.witness_reservations)
        return {purpose: int(counter[purpose]) for purpose in sorted(counter)}

    @property
    def export_mapping_summary_by_mode(self) -> dict[str, int]:
        counter = Counter(str(entry.mapping_mode) for entry in self.export_mappings)
        return {mode: int(counter[mode]) for mode in sorted(counter)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_version": str(self.plan_version),
            "planning_status": str(self.planning_status),
            "base_id": str(self.base_id),
            "base_lot_size": int(self.base_lot_size),
            "canonical_contract_size": int(self.canonical_contract_size),
            "inner_island_origin": self.inner_island_origin.to_dict(),
            "inner_island_size": int(self.inner_island_size),
            "moat_thickness_by_edge": dict(self.moat_thickness_by_edge),
            "foundation_bus_edges": list(self.foundation_bus_edges),
            "boundary_demand_summary": self.boundary_demand_summary.to_dict(),
            "boundary_assignment_summary_by_edge": dict(self.boundary_assignment_summary_by_edge),
            "boundary_assignments": [entry.to_dict() for entry in self.boundary_assignments],
            "connector_summary_by_edge": dict(self.connector_summary_by_edge),
            "connector_reservations": [entry.to_dict() for entry in self.connector_reservations],
            "witness_summary_by_purpose": dict(self.witness_summary_by_purpose),
            "witness_reservations": [entry.to_dict() for entry in self.witness_reservations],
            "export_mapping_summary_by_mode": dict(self.export_mapping_summary_by_mode),
            "export_mappings": [entry.to_dict() for entry in self.export_mappings],
            "diagnostics": self.diagnostics.to_dict(),
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }

    def to_markdown(self) -> str:
        moat = self.moat_thickness_by_edge
        demand = self.boundary_demand_summary
        lines = [
            "# IndustrialPlanner Outer Base Deployment Plan",
            "",
            f"- Plan version: `{self.plan_version}`",
            f"- Planning status: `{self.planning_status}`",
            f"- Base id: `{self.base_id}`",
            f"- Base lot size: {self.base_lot_size}",
            f"- Canonical contract size: {self.canonical_contract_size}×{self.canonical_contract_size}",
            f"- Inner island origin: ({self.inner_island_origin.x}, {self.inner_island_origin.y})",
            f"- Inner island size: {self.inner_island_size}",
            (
                "- Moat thickness by edge: "
                f"top={moat['top']}, right={moat['right']}, bottom={moat['bottom']}, left={moat['left']}"
            ),
            (
                "- Foundation bus edges: "
                + (", ".join(self.foundation_bus_edges) if self.foundation_bus_edges else "(none)")
            ),
            (
                "- Boundary demand: "
                f"outputs {demand.required_boundary_output_slots}, inputs {demand.required_boundary_input_slots}"
            ),
            f"- Boundary assignments: {len(self.boundary_assignments)}",
            f"- Connector reservations: {len(self.connector_reservations)}",
            f"- Witness reservations: {len(self.witness_reservations)}",
            f"- Export mappings: {len(self.export_mappings)}",
            "",
            "## Boundary demand summary",
            "",
            "- Output commodity counts: "
            + ", ".join(f"{name}={count}" for name, count in demand.output_commodity_counts),
            "- Input commodity counts: "
            + ", ".join(f"{name}={count}" for name, count in demand.input_commodity_counts),
            "",
            "## Boundary assignment summary by edge",
            "",
        ]
        for edge, summary in self.boundary_assignment_summary_by_edge.items():
            lines.append(
                f"- {edge}: total={summary['total']}, outputs={summary['outputs']}, inputs={summary['inputs']}"
            )
        lines.extend(["", "## Connector reservation summary by edge", ""])
        for edge, count in self.connector_summary_by_edge.items():
            lines.append(f"- {edge}: {count}")
        lines.extend(["", "## Witness reservation summary by purpose", ""])
        for purpose, count in self.witness_summary_by_purpose.items():
            lines.append(f"- {purpose}: {count}")
        lines.extend(["", "## Export mapping summary by mode", ""])
        for mode, count in self.export_mapping_summary_by_mode.items():
            lines.append(f"- {mode}: {count}")
        diagnostics = self.diagnostics
        lines.extend(
            [
                "",
                "## Diagnostics",
                "",
                f"- Exporter status: `{diagnostics.exporter_status}`",
                f"- Validator import-compatible: {diagnostics.validator_import_compatible}",
                f"- Validator layout-healthy: {diagnostics.validator_layout_healthy}",
                f"- Throughput status: `{diagnostics.throughput_status or '(not_run)'}`",
                f"- Validation probes: {diagnostics.validation_probe_count}",
            ]
        )
        if self.notes:
            lines.extend(["", "## Notes", ""])
            lines.extend(f"- {note}" for note in self.notes)
        if self.warnings or diagnostics.warnings:
            lines.extend(["", "## Warnings", ""])
            for warning in [*self.warnings, *diagnostics.warnings]:
                lines.append(f"- {warning}")
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class BoundaryAssignmentCandidate:
    direction: str
    commodity_id: str
    exported_anchor: Point
    exported_orientation: int
    handoff_anchor: Point
    true_edge: str
    true_edge_position: int
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def build_outer_base_deployment_plan(
    *,
    blueprint_payload: Mapping[str, Any],
    base_id: str,
    canonical_contract_size: int = 70,
    inner_island_origin: tuple[int, int] | None = None,
) -> OuterBaseDeploymentPlan:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    registries = load_static_registries()
    base_def = registries.base_by_id.get(str(base_id))
    if not isinstance(base_def, Mapping):
        raise ValueError(f"unknown IndustrialPlanner base_id {base_id!r}")

    lot_size = int(base_def.get("placeableSize", 0))
    if lot_size < int(canonical_contract_size):
        raise ValueError(
            f"base {base_id!r} is smaller than the canonical {canonical_contract_size}×{canonical_contract_size} contract"
        )

    if inner_island_origin is None:
        ox = int((lot_size - canonical_contract_size) // 2)
        oy = int((lot_size - canonical_contract_size) // 2)
    else:
        ox = int(inner_island_origin[0])
        oy = int(inner_island_origin[1])
    if ox < 0 or oy < 0 or ox + canonical_contract_size > lot_size or oy + canonical_contract_size > lot_size:
        raise ValueError(
            f"inner_island_origin {(ox, oy)!r} does not fit canonical size {canonical_contract_size} inside base lot {lot_size}"
        )

    foundation_bus_edges = _foundation_bus_edges(base_def)
    boundary_assignments: list[BoundaryAssignment] = []
    connector_reservations: list[ConnectorReservation] = []
    witness_reservations: list[WitnessReservation] = []
    export_mappings: list[ExportMapping] = []

    output_counter: Counter[str] = Counter()
    input_counter: Counter[str] = Counter()

    for facility in normalized_blueprint.get("facilities", []):
        facility_type = str(facility.get("facility_type", "")).strip()
        instance_id = str(facility.get("instance_id", "")).strip()
        canonical_anchor = _point_from_anchor(facility.get("anchor"))
        canonical_orientation = int(facility.get("orientation", 0))

        candidate = _build_boundary_assignment_candidate(
            facility=facility,
            base_id=str(base_id),
            lot_size=lot_size,
            canonical_contract_size=int(canonical_contract_size),
            inner_island_origin=Point(ox, oy),
            foundation_bus_edges=foundation_bus_edges,
        )
        if candidate is not None:
            if candidate.direction == "required_output":
                output_counter[candidate.commodity_id] += 1
            elif candidate.direction == "required_input":
                input_counter[candidate.commodity_id] += 1
            assignment = BoundaryAssignment(
                canonical_instance_id=instance_id,
                commodity_id=candidate.commodity_id,
                direction=candidate.direction,
                true_edge=candidate.true_edge,
                true_edge_position=candidate.true_edge_position,
                canonical_anchor=canonical_anchor,
                handoff_anchor=candidate.handoff_anchor,
                exported_anchor=candidate.exported_anchor,
                exported_orientation=candidate.exported_orientation,
                notes=candidate.notes,
                warnings=candidate.warnings,
            )
            boundary_assignments.append(assignment)

            reserved_cells = tuple(
                Point(x, y)
                for x, y in _exclusive_cells_between(
                    candidate.handoff_anchor,
                    candidate.exported_anchor,
                )
            )
            if reserved_cells:
                connector_reservations.append(
                    ConnectorReservation(
                        reservation_id=f"corridor_{instance_id}",
                        canonical_instance_id=instance_id,
                        commodity_id=candidate.commodity_id,
                        true_edge=candidate.true_edge,
                        handoff_anchor=candidate.handoff_anchor,
                        true_edge_anchor=candidate.exported_anchor,
                        reserved_cells=reserved_cells,
                    )
                )

            witness_reservations.extend(
                _build_boundary_witness_reservations(
                    assignment=assignment,
                    lot_size=lot_size,
                    registries=registries,
                )
            )

            export_mappings.append(
                ExportMapping(
                    canonical_instance_id=instance_id,
                    exported_type_id=_resolve_exported_type_id(
                        facility=facility,
                        base_id=str(base_id),
                        exported_anchor=candidate.exported_anchor,
                        exported_orientation=candidate.exported_orientation,
                    ),
                    exported_origin=candidate.exported_anchor,
                    exported_rotation=candidate.exported_orientation,
                    mapping_mode=(
                        "identity"
                        if candidate.exported_anchor == canonical_anchor
                        and candidate.exported_orientation == canonical_orientation
                        else "translated_boundary_assignment"
                    ),
                )
            )
            continue

        exported_anchor = Point(canonical_anchor.x + ox, canonical_anchor.y + oy)
        exported_type_id = _resolve_exported_type_id(
            facility=facility,
            base_id=str(base_id),
            exported_anchor=exported_anchor,
            exported_orientation=canonical_orientation,
        )
        mapping_mode = (
            "identity"
            if exported_anchor == canonical_anchor and canonical_orientation == int(facility.get("orientation", 0))
            else "translated_by_outer_plan"
        )
        export_mappings.append(
            ExportMapping(
                canonical_instance_id=instance_id,
                exported_type_id=exported_type_id,
                exported_origin=exported_anchor,
                exported_rotation=canonical_orientation,
                mapping_mode=mapping_mode,
            )
        )

    demand_summary = BoundaryDemandSummary(
        required_boundary_output_slots=sum(output_counter.values()),
        required_boundary_input_slots=sum(input_counter.values()),
        output_commodity_counts=tuple(sorted((name, int(count)) for name, count in output_counter.items())),
        input_commodity_counts=tuple(sorted((name, int(count)) for name, count in input_counter.items())),
    )

    notes = [
        "outer deployment plan is adapter-side only; it does not widen the canonical blueprint schema or the certified_exact evidence boundary",
    ]
    if ox or oy:
        notes.append(
            f"selected deterministic centered inner-island origin ({ox}, {oy}) inside a {lot_size}×{lot_size} base"
        )
    else:
        notes.append("selected the degenerate zero-offset inner-island origin because the base already matches the canonical 70×70 contract")
    if foundation_bus_edges:
        notes.append(
            "selected base inherits foundation bus edges at " + ", ".join(foundation_bus_edges)
        )
    else:
        notes.append(
            "selected base exposes no foundation bus edges; pure-output witness reservations remain explicit on every true edge"
        )

    return OuterBaseDeploymentPlan(
        plan_version=_PLAN_VERSION,
        planning_status=_PLANNING_STATUS,
        base_id=str(base_id),
        base_lot_size=lot_size,
        canonical_contract_size=int(canonical_contract_size),
        inner_island_origin=Point(ox, oy),
        inner_island_size=int(canonical_contract_size),
        foundation_bus_edges=foundation_bus_edges,
        boundary_demand_summary=demand_summary,
        boundary_assignments=tuple(boundary_assignments),
        connector_reservations=tuple(connector_reservations),
        witness_reservations=tuple(witness_reservations),
        export_mappings=tuple(export_mappings),
        diagnostics=PlanningDiagnostics(),
        notes=tuple(notes),
        warnings=(),
    )


def outer_deployment_plan_from_dict(payload: Mapping[str, Any]) -> OuterBaseDeploymentPlan:
    boundary_summary = payload.get("boundary_demand_summary") if isinstance(payload.get("boundary_demand_summary"), Mapping) else {}
    return OuterBaseDeploymentPlan(
        plan_version=str(payload.get("plan_version", _PLAN_VERSION)),
        planning_status=str(payload.get("planning_status", _PLANNING_STATUS)),
        base_id=str(payload.get("base_id", "")),
        base_lot_size=int(payload.get("base_lot_size", 0)),
        canonical_contract_size=int(payload.get("canonical_contract_size", 70)),
        inner_island_origin=_point_from_anchor(payload.get("inner_island_origin")),
        inner_island_size=int(payload.get("inner_island_size", 70)),
        foundation_bus_edges=tuple(str(value) for value in payload.get("foundation_bus_edges", ())),
        boundary_demand_summary=BoundaryDemandSummary(
            required_boundary_output_slots=int(boundary_summary.get("required_boundary_output_slots", 0)),
            required_boundary_input_slots=int(boundary_summary.get("required_boundary_input_slots", 0)),
            output_commodity_counts=tuple(
                sorted((str(name), int(count)) for name, count in dict(boundary_summary.get("output_commodity_counts", {})).items())
            ),
            input_commodity_counts=tuple(
                sorted((str(name), int(count)) for name, count in dict(boundary_summary.get("input_commodity_counts", {})).items())
            ),
        ),
        boundary_assignments=tuple(
            BoundaryAssignment(
                canonical_instance_id=str(entry.get("canonical_instance_id", "")),
                commodity_id=str(entry.get("commodity_id", "")),
                direction=str(entry.get("direction", "")),
                true_edge=str(entry.get("true_edge", "")),
                true_edge_position=int(entry.get("true_edge_position", 0)),
                canonical_anchor=_point_from_anchor(entry.get("canonical_anchor")),
                handoff_anchor=_point_from_anchor(entry.get("handoff_anchor")),
                exported_anchor=_point_from_anchor(entry.get("exported_anchor")),
                exported_orientation=int(entry.get("exported_rotation", 0)),
                notes=tuple(str(note) for note in entry.get("notes", ())),
                warnings=tuple(str(warning) for warning in entry.get("warnings", ())),
            )
            for entry in payload.get("boundary_assignments", ())
            if isinstance(entry, Mapping)
        ),
        connector_reservations=tuple(
            ConnectorReservation(
                reservation_id=str(entry.get("reservation_id", "")),
                canonical_instance_id=str(entry.get("canonical_instance_id", "")),
                commodity_id=str(entry.get("commodity_id", "")),
                true_edge=str(entry.get("true_edge", "")),
                handoff_anchor=_point_from_anchor(entry.get("handoff_anchor")),
                true_edge_anchor=_point_from_anchor(entry.get("true_edge_anchor")),
                reserved_cells=tuple(_point_from_anchor(cell) for cell in entry.get("reserved_cells", ()) if isinstance(cell, Mapping)),
                notes=tuple(str(note) for note in entry.get("notes", ())),
                warnings=tuple(str(warning) for warning in entry.get("warnings", ())),
            )
            for entry in payload.get("connector_reservations", ())
            if isinstance(entry, Mapping)
        ),
        witness_reservations=tuple(
            WitnessReservation(
                reservation_id=str(entry.get("reservation_id", "")),
                witness_type_id=str(entry.get("witness_type_id", "")),
                purpose=str(entry.get("purpose", "")),
                commodity_id=str(entry.get("commodity_id", "")),
                required_for_instance_id=str(entry.get("required_for_instance_id", "")),
                origin=_point_from_anchor(entry.get("origin")),
                rotation=int(entry.get("rotation", 0)),
                reserved_cells=tuple(_point_from_anchor(cell) for cell in entry.get("reserved_cells", ()) if isinstance(cell, Mapping)),
                notes=tuple(str(note) for note in entry.get("notes", ())),
                warnings=tuple(str(warning) for warning in entry.get("warnings", ())),
            )
            for entry in payload.get("witness_reservations", ())
            if isinstance(entry, Mapping)
        ),
        export_mappings=tuple(
            ExportMapping(
                canonical_instance_id=str(entry.get("canonical_instance_id", "")),
                exported_type_id=str(entry.get("exported_type_id")) if entry.get("exported_type_id") is not None else None,
                exported_origin=_point_from_anchor(entry.get("exported_origin")),
                exported_rotation=int(entry.get("exported_rotation", 0)),
                mapping_mode=str(entry.get("mapping_mode", "identity")),
                notes=tuple(str(note) for note in entry.get("notes", ())),
                warnings=tuple(str(warning) for warning in entry.get("warnings", ())),
            )
            for entry in payload.get("export_mappings", ())
            if isinstance(entry, Mapping)
        ),
        diagnostics=PlanningDiagnostics(
            exporter_status=str(dict(payload.get("diagnostics", {})).get("exporter_status", "not_run")),
            validator_import_compatible=dict(payload.get("diagnostics", {})).get("validator_import_compatible"),
            validator_layout_healthy=dict(payload.get("diagnostics", {})).get("validator_layout_healthy"),
            throughput_status=dict(payload.get("diagnostics", {})).get("throughput_status"),
            validation_probe_count=int(dict(payload.get("diagnostics", {})).get("validation_probe_count", 0)),
            warnings=tuple(str(warning) for warning in dict(payload.get("diagnostics", {})).get("warnings", ())),
        ),
        notes=tuple(str(note) for note in payload.get("notes", ())),
        warnings=tuple(str(warning) for warning in payload.get("warnings", ())),
    )


def _build_boundary_assignment_candidate(
    *,
    facility: Mapping[str, Any],
    base_id: str,
    lot_size: int,
    canonical_contract_size: int,
    inner_island_origin: Point,
    foundation_bus_edges: Sequence[str],
) -> BoundaryAssignmentCandidate | None:
    if str(facility.get("facility_type", "")).strip() != "boundary_storage_port":
        return None
    anchor = _point_from_anchor(facility.get("anchor"))
    true_edge = _canonical_edge_for_anchor(anchor=anchor, canonical_contract_size=canonical_contract_size)
    if true_edge is None:
        return None
    direction, commodity_id = _boundary_direction_and_commodity(facility)
    if direction is None or commodity_id is None:
        return None
    canonical_orientation = int(facility.get("orientation", 0))
    exported_orientation = _exported_boundary_orientation(
        true_edge=true_edge,
        direction=direction,
        canonical_orientation=canonical_orientation,
        foundation_bus_edges=foundation_bus_edges,
    )
    exported_anchor, extra_notes, extra_warnings = _export_boundary_anchor(
        canonical_anchor=anchor,
        true_edge=true_edge,
        lot_size=lot_size,
        inner_island_origin=inner_island_origin,
        canonical_contract_size=canonical_contract_size,
        direction=direction,
        foundation_bus_edges=foundation_bus_edges,
    )
    handoff_anchor = _handoff_anchor(
        exported_anchor=exported_anchor,
        true_edge=true_edge,
        inner_island_origin=inner_island_origin,
        canonical_contract_size=canonical_contract_size,
    )
    true_edge_position = (anchor.x + inner_island_origin.x) if true_edge in {"top", "bottom"} else (anchor.y + inner_island_origin.y)
    return BoundaryAssignmentCandidate(
        direction=direction,
        commodity_id=commodity_id,
        exported_anchor=exported_anchor,
        exported_orientation=exported_orientation,
        handoff_anchor=handoff_anchor,
        true_edge=true_edge,
        true_edge_position=true_edge_position,
        notes=tuple(extra_notes),
        warnings=tuple(extra_warnings),
    )


def _point_from_anchor(raw_anchor: Any) -> Point:
    if not isinstance(raw_anchor, Mapping):
        return Point(0, 0)
    return Point(int(raw_anchor.get("x", 0)), int(raw_anchor.get("y", 0)))


def _foundation_bus_edges(base_def: Mapping[str, Any]) -> tuple[str, ...]:
    edges: set[str] = set()
    lot_size = int(base_def.get("placeableSize", 0))
    for entry in base_def.get("foundationBuildings", ()):
        if not isinstance(entry, Mapping):
            continue
        type_id = str(entry.get("typeId", "")).strip()
        if type_id not in {"item_port_log_hongs_bus", "item_port_log_hongs_bus_source"}:
            continue
        origin = entry.get("origin") if isinstance(entry.get("origin"), Mapping) else {}
        origin_x = int(origin.get("x", 0))
        origin_y = int(origin.get("y", 0))
        if origin_y < 0:
            edges.add("top")
        if origin_x < 0:
            edges.add("left")
        if origin_y >= lot_size:
            edges.add("bottom")
        if origin_x >= lot_size:
            edges.add("right")
    return tuple(sorted(edges))


def _boundary_direction_and_commodity(facility: Mapping[str, Any]) -> tuple[str | None, str | None]:
    active_ports = facility.get("active_ports") if isinstance(facility.get("active_ports"), Sequence) else ()
    input_ports = [entry for entry in active_ports if isinstance(entry, Mapping) and str(entry.get("type", "")).lower() == "input"]
    output_ports = [entry for entry in active_ports if isinstance(entry, Mapping) and str(entry.get("type", "")).lower() == "output"]
    if input_ports and not output_ports:
        return "required_input", str(input_ports[0].get("commodity", ""))
    if output_ports and not input_ports:
        return "required_output", str(output_ports[0].get("commodity", ""))
    return None, None


def _canonical_edge_for_anchor(*, anchor: Point, canonical_contract_size: int) -> str | None:
    max_coord = int(canonical_contract_size) - 1
    if anchor.y == 0:
        return "top"
    if anchor.x == 0:
        return "left"
    if anchor.y == max_coord:
        return "bottom"
    if anchor.x == max_coord:
        return "right"
    return None


def _export_boundary_anchor(
    *,
    canonical_anchor: Point,
    true_edge: str,
    lot_size: int,
    inner_island_origin: Point,
    canonical_contract_size: int,
    direction: str,
    foundation_bus_edges: Sequence[str],
) -> tuple[Point, tuple[str, ...], tuple[str, ...]]:
    if true_edge == "top":
        edge_anchor = Point(canonical_anchor.x + inner_island_origin.x, 0)
    elif true_edge == "left":
        edge_anchor = Point(0, canonical_anchor.y + inner_island_origin.y)
    elif true_edge == "bottom":
        edge_anchor = Point(canonical_anchor.x + inner_island_origin.x, lot_size - 1)
    else:
        edge_anchor = Point(lot_size - 1, canonical_anchor.y + inner_island_origin.y)

    if direction != "required_input" or str(true_edge) in {str(edge) for edge in foundation_bus_edges}:
        return edge_anchor, (), ()

    staged_anchor = _inboard_input_boundary_anchor(edge_anchor=edge_anchor, true_edge=true_edge)
    if staged_anchor == edge_anchor:
        return edge_anchor, (), ()
    return (
        staged_anchor,
        (
            f"shifted pure-input boundary loader {_BOUNDARY_INPUT_BUS_STAGING_DEPTH} cells inboard on the {true_edge} edge "
            "so the exporter can synthesize an in-lot grouped bus witness while keeping the admission filter explicit",
        ),
        (),
    )


def _handoff_anchor(
    *,
    exported_anchor: Point,
    true_edge: str,
    inner_island_origin: Point,
    canonical_contract_size: int,
) -> Point:
    max_coord = int(canonical_contract_size) - 1
    if true_edge == "top":
        return Point(exported_anchor.x, inner_island_origin.y)
    if true_edge == "left":
        return Point(inner_island_origin.x, exported_anchor.y)
    if true_edge == "bottom":
        return Point(exported_anchor.x, inner_island_origin.y + max_coord)
    return Point(inner_island_origin.x + max_coord, exported_anchor.y)


def _inboard_input_boundary_anchor(*, edge_anchor: Point, true_edge: str) -> Point:
    if true_edge == "top":
        return Point(edge_anchor.x, edge_anchor.y + _BOUNDARY_INPUT_BUS_STAGING_DEPTH)
    if true_edge == "left":
        return Point(edge_anchor.x + _BOUNDARY_INPUT_BUS_STAGING_DEPTH, edge_anchor.y)
    if true_edge == "bottom":
        return Point(edge_anchor.x, edge_anchor.y - _BOUNDARY_INPUT_BUS_STAGING_DEPTH)
    return Point(edge_anchor.x - _BOUNDARY_INPUT_BUS_STAGING_DEPTH, edge_anchor.y)


def _exported_boundary_orientation(
    *,
    true_edge: str,
    direction: str,
    canonical_orientation: int,
    foundation_bus_edges: Sequence[str],
) -> int:
    if direction == "required_input":
        return int(canonical_orientation)
    inside_facing = str(true_edge) not in {str(edge) for edge in foundation_bus_edges}
    return _boundary_orientation(edge=true_edge, inside_facing=inside_facing, direction=direction)


def _boundary_orientation(*, edge: str, inside_facing: bool, direction: str) -> int:
    if direction == "required_input":
        if edge != "top":
            raise ValueError("current full-demand outer-plan path only emits pure-input boundary loaders on the top edge")
        return 1
    orientation_by_edge_and_mode = {
        ("top", False): 1,
        ("top", True): 3,
        ("left", False): 0,
        ("left", True): 2,
        ("bottom", True): 1,
        ("right", True): 0,
    }
    return orientation_by_edge_and_mode[(edge, inside_facing)]


def _exclusive_cells_between(start: Point, end: Point) -> tuple[tuple[int, int], ...]:
    if start.x == end.x:
        lower = min(start.y, end.y) + 1
        upper = max(start.y, end.y)
        return tuple((start.x, y) for y in range(lower, upper))
    if start.y == end.y:
        lower = min(start.x, end.x) + 1
        upper = max(start.x, end.x)
        return tuple((x, start.y) for x in range(lower, upper))
    raise ValueError("connector reservations must be axis-aligned")


def _build_boundary_witness_reservations(
    *,
    assignment: BoundaryAssignment,
    lot_size: int,
    registries: Any,
) -> tuple[WitnessReservation, ...]:
    if assignment.direction == "required_input":
        loader_rotation = orientation_to_rotation(assignment.exported_orientation, degrees_offset=90)
        port_x, port_y, port_edge = _loader_input_port_geometry(
            loader_origin=assignment.exported_anchor.to_dict(),
            loader_rotation=loader_rotation,
        )
        dx, dy = _EDGE_DELTA[port_edge]
        admission_origin = Point(int(port_x + dx), int(port_y + dy))
        admission_warnings: list[str] = []
        if not (0 <= admission_origin.x < lot_size and 0 <= admission_origin.y < lot_size):
            admission_warnings.append(
                f"input admission witness for {assignment.canonical_instance_id} falls outside the {lot_size}×{lot_size} lot at ({admission_origin.x}, {admission_origin.y})"
            )

        reservations: list[WitnessReservation] = [
            WitnessReservation(
                reservation_id=f"witness_admission_{assignment.canonical_instance_id}",
                witness_type_id="item_log_admission",
                purpose="boundary_input_admission",
                commodity_id=assignment.commodity_id,
                required_for_instance_id=assignment.canonical_instance_id,
                origin=admission_origin,
                rotation=_direction_to_rotation(_opposite_edge(port_edge)),
                reserved_cells=(admission_origin,),
                warnings=tuple(admission_warnings),
            ),
        ]

        if assignment.exported_anchor == _edge_aligned_boundary_anchor(assignment=assignment, lot_size=lot_size):
            return tuple(reservations)

        required_side = _loader_required_bus_side(loader_rotation)
        adjacent_cells = _adjacent_target_cells_for_loader(
            origin=assignment.exported_anchor,
            rotation=loader_rotation,
            required_side=required_side,
            registries=registries,
        )
        in_lot_cells = [Point(x, y) for x, y in adjacent_cells if 0 <= x < lot_size and 0 <= y < lot_size]
        if in_lot_cells and assignment.exported_anchor != _edge_aligned_boundary_anchor(assignment=assignment, lot_size=lot_size):
            reservations.append(
                WitnessReservation(
                    reservation_id=f"witness_bus_{assignment.canonical_instance_id}",
                    witness_type_id="item_port_log_hongs_bus",
                    purpose="boundary_input_bus",
                    commodity_id=assignment.commodity_id,
                    required_for_instance_id=assignment.canonical_instance_id,
                    origin=in_lot_cells[0],
                    rotation=_BOUNDARY_BUS_WITNESS_ROTATION,
                    reserved_cells=tuple(in_lot_cells),
                    notes=(
                        "reserved_cells mark the in-lot bus-adjacent staging strip; the exporter may group multiple input reservations into a single witness device",
                    ),
                )
            )
        elif assignment.exported_anchor != _edge_aligned_boundary_anchor(assignment=assignment, lot_size=lot_size):
            reservations.append(
                WitnessReservation(
                    reservation_id=f"witness_bus_{assignment.canonical_instance_id}",
                    witness_type_id="item_port_log_hongs_bus",
                    purpose="boundary_input_bus",
                    commodity_id=assignment.commodity_id,
                    required_for_instance_id=assignment.canonical_instance_id,
                    origin=Point(*adjacent_cells[0]) if adjacent_cells else assignment.exported_anchor,
                    rotation=_BOUNDARY_BUS_WITNESS_ROTATION,
                    reserved_cells=tuple(Point(x, y) for x, y in adjacent_cells),
                    warnings=(
                        f"input bus witness for {assignment.canonical_instance_id} has no in-lot target cell on the required {required_side}-side face",
                    ),
                    notes=(
                        "reserved_cells mark the intended bus-adjacent staging strip even though it falls outside the lot",
                    ),
                )
            )
        return tuple(reservations)

    unloader_rotation = orientation_to_rotation(assignment.exported_orientation, degrees_offset=90)
    required_side = _unloader_required_bus_side(unloader_rotation)
    adjacent_cells = _adjacent_target_cells_for_unloader(
        origin=assignment.exported_anchor,
        rotation=unloader_rotation,
        required_side=required_side,
        registries=registries,
    )
    in_lot_cells = [Point(x, y) for x, y in adjacent_cells if 0 <= x < lot_size and 0 <= y < lot_size]
    warnings: list[str] = []
    if in_lot_cells:
        origin = in_lot_cells[0]
    else:
        origin = Point(*adjacent_cells[0]) if adjacent_cells else assignment.exported_anchor
        warnings.append(
            f"output bus witness for {assignment.canonical_instance_id} has no in-lot target cell on the required {required_side}-side face"
        )
    return (
        WitnessReservation(
            reservation_id=f"witness_bus_{assignment.canonical_instance_id}",
            witness_type_id="item_port_log_hongs_bus",
            purpose="boundary_output_bus",
            commodity_id=assignment.commodity_id,
            required_for_instance_id=assignment.canonical_instance_id,
            origin=origin,
            rotation=_BOUNDARY_BUS_WITNESS_ROTATION,
            reserved_cells=(origin,),
            warnings=tuple(warnings),
        ),
    )


def _edge_aligned_boundary_anchor(*, assignment: BoundaryAssignment, lot_size: int) -> Point:
    if assignment.true_edge == "top":
        return Point(assignment.true_edge_position, 0)
    if assignment.true_edge == "left":
        return Point(0, assignment.true_edge_position)
    if assignment.true_edge == "bottom":
        return Point(assignment.true_edge_position, lot_size - 1)
    return Point(lot_size - 1, assignment.true_edge_position)


def _loader_required_bus_side(rotation: int) -> str:
    _, _, port_edge = _loader_input_port_geometry(
        loader_origin={"x": 0, "y": 0},
        loader_rotation=rotation,
    )
    return _opposite_edge(port_edge)


def _adjacent_target_cells_for_loader(
    *,
    origin: Point,
    rotation: int,
    required_side: str,
    registries: Any,
) -> tuple[tuple[int, int], ...]:
    device_def = registries.device_types_by_id.get("item_port_loader_1")
    size_payload = device_def.get("size") if isinstance(device_def, Mapping) else {}
    width, height = _rotated_size(size_payload, rotation)
    if required_side == "N":
        boundary_cells = tuple((origin.x + index, origin.y) for index in range(width))
    elif required_side == "S":
        boundary_cells = tuple((origin.x + index, origin.y + height - 1) for index in range(width))
    elif required_side == "W":
        boundary_cells = tuple((origin.x, origin.y + index) for index in range(height))
    else:
        boundary_cells = tuple((origin.x + width - 1, origin.y + index) for index in range(height))
    dx, dy = _EDGE_DELTA[required_side]
    return tuple((cell_x + dx, cell_y + dy) for cell_x, cell_y in boundary_cells)


def _adjacent_target_cells_for_unloader(
    *,
    origin: Point,
    rotation: int,
    required_side: str,
    registries: Any,
) -> tuple[tuple[int, int], ...]:
    device_def = registries.device_types_by_id.get("item_port_unloader_1")
    size_payload = device_def.get("size") if isinstance(device_def, Mapping) else {}
    width, height = _rotated_size(size_payload, rotation)
    if required_side == "N":
        boundary_cells = tuple((origin.x + index, origin.y) for index in range(width))
    elif required_side == "S":
        boundary_cells = tuple((origin.x + index, origin.y + height - 1) for index in range(width))
    elif required_side == "W":
        boundary_cells = tuple((origin.x, origin.y + index) for index in range(height))
    else:
        boundary_cells = tuple((origin.x + width - 1, origin.y + index) for index in range(height))
    dx, dy = _EDGE_DELTA[required_side]
    return tuple((cell_x + dx, cell_y + dy) for cell_x, cell_y in boundary_cells)


def _rotated_size(size_payload: Mapping[str, Any], rotation: int) -> tuple[int, int]:
    width = int(size_payload.get("width", 0))
    height = int(size_payload.get("height", 0))
    if int(rotation) % 180 == 0:
        return width, height
    return height, width


def _resolve_exported_type_id(
    *,
    facility: Mapping[str, Any],
    base_id: str,
    exported_anchor: Point,
    exported_orientation: int,
) -> str | None:
    updated = dict(facility)
    updated["anchor"] = exported_anchor.to_dict()
    updated["orientation"] = int(exported_orientation)
    resolved = resolve_facility_device(updated, default_base_id=base_id)
    return str(resolved.target_type_id) if resolved.target_type_id is not None else None


def _unloader_required_bus_side(rotation: int) -> str:
    edge_order = ("N", "E", "S", "W")
    steps = int((int(rotation) % 360) // 90)
    port_edge = edge_order[steps % len(edge_order)]
    return _opposite_edge(port_edge)


def _opposite_edge(edge: str) -> str:
    return {
        "N": "S",
        "S": "N",
        "E": "W",
        "W": "E",
    }[str(edge).upper()]


def _direction_to_rotation(edge: str) -> int:
    return {
        "E": 0,
        "S": 90,
        "W": 180,
        "N": 270,
    }[str(edge).upper()]


__all__ = [
    "BoundaryAssignment",
    "BoundaryDemandSummary",
    "ConnectorReservation",
    "ExportMapping",
    "OuterBaseDeploymentPlan",
    "PlanningDiagnostics",
    "WitnessReservation",
    "build_outer_base_deployment_plan",
    "outer_deployment_plan_from_dict",
]

"""Static recipe/capacity conformance audit for the IndustrialPlanner adapter.

The audit intentionally stays outside the certified solver boundary. It consumes
canonical blueprint data, the already-built IndustrialPlanner export bundle, the
static target registry, and frozen preprocess artifacts to answer a narrower
question:

*Can the exported IndustrialPlanner devices be interpreted as a unique set of
exact target-side static recipes, and do they provide enough nominal full-speed
capacity lower bound for the canonical recipe requirements?*

This module does **not** simulate runtime flow balance, splitter fairness,
fluid pressure, or any other dynamic behavior.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.adapters.industrial_planner.blueprint_validator import validate_industrial_planner_blueprint
from src.adapters.industrial_planner.commodity_resolver import (
    canonical_rules_payload,
    translate_canonical_item_id,
)
from src.adapters.industrial_planner.mapping_registry import (
    DEFAULT_BASE_ID,
    PRECISION_MAPPED_FACILITY_TYPES,
    resolve_facility_device,
)
from src.adapters.industrial_planner.recipe_matcher import (
    TargetRecipeMatch,
    build_recipe_match_index,
)
from src.io.output_schema import normalize_blueprint_payload
from src.preprocess.demand_solver import (
    generate_generic_io_requirements,
    generate_port_budget,
    solve_demands_exact,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MANDATORY_EXACT_INSTANCES_PATH = _PROJECT_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"
_GENERIC_IO_REQUIREMENTS_PATH = _PROJECT_ROOT / "data" / "preprocessed" / "generic_io_requirements.json"

_DEFAULT_LIMITATIONS = (
    "This audit is static recipe/capacity conformance only.",
    "It does not prove runtime flow balance or steady-state behavior.",
    "It does not simulate splitter, buffer, warm-up, or deadlock behavior.",
    "It does not simulate liquid pressure or other fluid-runtime behavior.",
    "Protocol-core implicit capacity is not counted unless it is explicitly represented in the export.",
    "Generic or fallback facilities do not count as proven recipe capacity.",
)

_OPPOSITE_EDGE = {"N": "S", "S": "N", "E": "W", "W": "E"}
_EDGE_DELTA = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
_DIRECTION_TO_ROTATION = {"E": 0, "S": 90, "W": 180, "N": 270}


@dataclass(frozen=True)
class FacilityCapacityEvidence:
    instance_id: str
    facility_type: str
    inferred_canonical_recipe_id: str | None
    recovery_source: str
    resolution_mode: str
    exported_type_id: str | None
    target_recipe_match_status: str
    counts_toward_capacity: bool
    proof_status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeCapacityRollup:
    canonical_recipe_id: str
    required_fractional_runs: str
    proven_exported_capacity_units: int
    expected_machine_type: str | None
    exact_target_recipe_id: str | None
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BoundaryIORollup:
    commodity_id: str
    direction: str
    required_slots: int
    required_flow_per_tick: str
    proven_slots: int
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationDiagnostics:
    is_import_compatible: bool
    is_layout_healthy: bool
    summary_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ThroughputAuditReport:
    status: str
    summary: dict[str, Any]
    recipe_matches: tuple[TargetRecipeMatch, ...]
    facility_evidence: tuple[FacilityCapacityEvidence, ...]
    recipe_rollups: tuple[RecipeCapacityRollup, ...]
    boundary_io_rollups: tuple[BoundaryIORollup, ...]
    validation_diagnostics: ValidationDiagnostics
    limitations: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        return render_throughput_report_markdown(self)


@lru_cache(maxsize=1)
def _load_mandatory_exact_map() -> dict[str, str]:
    if not _MANDATORY_EXACT_INSTANCES_PATH.exists():
        return {}
    payload = json.loads(_MANDATORY_EXACT_INSTANCES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return {}
    mandatory_map: dict[str, str] = {}
    for raw_entry in payload:
        if not isinstance(raw_entry, Mapping):
            continue
        instance_id = str(raw_entry.get("instance_id", "")).strip()
        operation_type = str(raw_entry.get("operation_type", "")).strip()
        if instance_id and operation_type:
            mandatory_map[instance_id] = operation_type
    return mandatory_map


@lru_cache(maxsize=1)
def _load_generic_io_requirements_artifact() -> dict[str, Any] | None:
    if not _GENERIC_IO_REQUIREMENTS_PATH.exists():
        return None
    payload = json.loads(_GENERIC_IO_REQUIREMENTS_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, Mapping) else None


@lru_cache(maxsize=1)
def _load_port_max_throughput_per_tick() -> Fraction:
    rules_payload = canonical_rules_payload()
    globals_payload = rules_payload.get("globals") if isinstance(rules_payload.get("globals"), Mapping) else {}
    logistics_payload = globals_payload.get("logistics") if isinstance(globals_payload.get("logistics"), Mapping) else {}
    return _to_fraction(logistics_payload.get("port_max_throughput_per_tick", 1))


def recover_facility_recipe_intent(
    facility: Mapping[str, Any],
    mandatory_exact_map: Mapping[str, str],
    *,
    resolved_device: Any | None = None,
    base_id: str = DEFAULT_BASE_ID,
) -> tuple[str | None, str, tuple[str, ...]]:
    instance_id = str(facility.get("instance_id", "")).strip()
    if instance_id and instance_id in mandatory_exact_map:
        warnings: list[str] = []
        if resolved_device is None:
            resolved_device = resolve_facility_device(facility, default_base_id=base_id)
        resolved_recipe_id = getattr(resolved_device, "resolved_recipe_id", None)
        mandatory_recipe_id = str(mandatory_exact_map[instance_id]).strip()
        if resolved_recipe_id and str(resolved_recipe_id).strip() != mandatory_recipe_id:
            warnings.append(
                f"mandatory_exact intent {mandatory_recipe_id!r} overrides resolver recipe {resolved_recipe_id!r}"
            )
        return mandatory_recipe_id, "mandatory_exact", tuple(sorted(set(warnings)))

    if resolved_device is None:
        resolved_device = resolve_facility_device(facility, default_base_id=base_id)
    resolved_recipe_id = getattr(resolved_device, "resolved_recipe_id", None)
    if resolved_recipe_id:
        return str(resolved_recipe_id), "resolved_recipe_id", ()
    return None, "unresolved", ()


def build_industrial_planner_throughput_audit(
    *,
    blueprint_payload: Mapping[str, Any],
    export_blueprint: Mapping[str, Any],
    compatibility_manifest: Mapping[str, Any] | None = None,
    validation_report: Mapping[str, Any] | None = None,
    base_id: str = DEFAULT_BASE_ID,
) -> ThroughputAuditReport:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    resolved_validation_report = validation_report or validate_industrial_planner_blueprint(export_blueprint).to_dict()
    recipe_match_index = build_recipe_match_index()
    recipe_matches = tuple(recipe_match_index[recipe_id] for recipe_id in sorted(recipe_match_index))
    flows, machine_runs = solve_demands_exact()
    generic_io_requirements = _load_generic_io_requirements(flows=flows)
    mandatory_exact_map = _load_mandatory_exact_map()
    postprocess_export_mapping_index = _load_postprocess_export_mapping_index(compatibility_manifest)

    facility_evidence = _recover_facility_evidence(
        blueprint_payload=normalized_blueprint,
        export_blueprint=export_blueprint,
        recipe_match_index=recipe_match_index,
        mandatory_exact_map=mandatory_exact_map,
        base_id=base_id,
        postprocess_export_mapping_index=postprocess_export_mapping_index,
    )
    recipe_rollups = _rollup_recipe_capacity(
        facility_evidence=facility_evidence,
        recipe_match_index=recipe_match_index,
        required_machine_runs=machine_runs,
    )
    boundary_io_rollups = _audit_boundary_io(
        blueprint_payload=normalized_blueprint,
        export_blueprint=export_blueprint,
        flows=flows,
        generic_io_requirements=generic_io_requirements,
        postprocess_export_mapping_index=postprocess_export_mapping_index,
    )
    validation_diagnostics = _build_validation_diagnostics(resolved_validation_report)

    overall_status = _derive_overall_status(
        recipe_rollups=recipe_rollups,
        boundary_io_rollups=boundary_io_rollups,
        facility_evidence=facility_evidence,
        validation_diagnostics=validation_diagnostics,
    )
    summary = _build_summary(
        recipe_matches=recipe_matches,
        recipe_rollups=recipe_rollups,
        boundary_io_rollups=boundary_io_rollups,
        validation_diagnostics=validation_diagnostics,
    )

    warnings = _collect_report_warnings(
        recipe_matches=recipe_matches,
        facility_evidence=facility_evidence,
        recipe_rollups=recipe_rollups,
        boundary_io_rollups=boundary_io_rollups,
        validation_diagnostics=validation_diagnostics,
        compatibility_manifest=compatibility_manifest,
    )

    return ThroughputAuditReport(
        status=overall_status,
        summary=summary,
        recipe_matches=recipe_matches,
        facility_evidence=facility_evidence,
        recipe_rollups=recipe_rollups,
        boundary_io_rollups=boundary_io_rollups,
        validation_diagnostics=validation_diagnostics,
        limitations=_DEFAULT_LIMITATIONS,
        warnings=warnings,
    )


def _load_generic_io_requirements(*, flows: Mapping[str, Fraction]) -> dict[str, Any]:
    artifact = _load_generic_io_requirements_artifact()
    if artifact is not None:
        return dict(artifact)
    port_budget = generate_port_budget(flows)
    return generate_generic_io_requirements(flows, port_budget)


def _recover_facility_evidence(
    *,
    blueprint_payload: Mapping[str, Any],
    export_blueprint: Mapping[str, Any],
    recipe_match_index: Mapping[str, TargetRecipeMatch],
    mandatory_exact_map: Mapping[str, str],
    base_id: str,
    postprocess_export_mapping_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[FacilityCapacityEvidence, ...]:
    evidence: list[FacilityCapacityEvidence] = []
    for facility in blueprint_payload.get("facilities", []):
        if not isinstance(facility, Mapping):
            continue
        facility_type = str(facility.get("facility_type", "")).strip()
        if facility_type not in PRECISION_MAPPED_FACILITY_TYPES:
            continue

        resolved_device = resolve_facility_device(facility, default_base_id=base_id)
        inferred_recipe_id, recovery_source, recovery_warnings = recover_facility_recipe_intent(
            facility,
            mandatory_exact_map,
            resolved_device=resolved_device,
            base_id=base_id,
        )
        exported_device = _find_exported_device_for_facility(
            export_blueprint,
            facility,
            postprocess_export_mapping_index=postprocess_export_mapping_index,
        )
        exported_type_id = _optional_string(exported_device.get("typeId")) if isinstance(exported_device, Mapping) else None
        match = recipe_match_index.get(inferred_recipe_id) if inferred_recipe_id else None
        target_recipe_match_status = match.status if match is not None else "unresolved"

        counts_toward_capacity = bool(
            facility_type in PRECISION_MAPPED_FACILITY_TYPES
            and inferred_recipe_id is not None
            and resolved_device.resolution_mode == "precise"
            and match is not None
            and match.status == "exact_match"
            and exported_type_id is not None
            and exported_type_id == match.expected_machine_type
        )

        warnings: list[str] = [*recovery_warnings, *resolved_device.warnings]
        if inferred_recipe_id is None:
            warnings.append("could not recover canonical recipe intent for capacity proof")
        if resolved_device.resolution_mode != "precise":
            warnings.append(
                f"facility resolution_mode={resolved_device.resolution_mode!r} does not count toward proven capacity"
            )
        if exported_type_id is None:
            warnings.append("no serialized target device was found at the facility anchor or translated export mapping")
        if match is not None and match.status != "exact_match":
            warnings.append(f"target recipe match status is {match.status!r}, not exact_match")
        if match is not None and match.expected_machine_type and exported_type_id and exported_type_id != match.expected_machine_type:
            warnings.append(
                f"exported target type {exported_type_id!r} does not equal expected machine family {match.expected_machine_type!r}"
            )

        if counts_toward_capacity:
            proof_status = "proven"
        elif inferred_recipe_id is not None or exported_type_id is not None:
            proof_status = "partial"
        else:
            proof_status = "unproven"

        evidence.append(
            FacilityCapacityEvidence(
                instance_id=str(facility.get("instance_id", "")).strip(),
                facility_type=facility_type,
                inferred_canonical_recipe_id=inferred_recipe_id,
                recovery_source=recovery_source,
                resolution_mode=str(resolved_device.resolution_mode),
                exported_type_id=exported_type_id,
                target_recipe_match_status=target_recipe_match_status,
                counts_toward_capacity=counts_toward_capacity,
                proof_status=proof_status,
                warnings=tuple(sorted(set(warnings))),
            )
        )
    evidence.sort(key=lambda entry: (entry.instance_id, entry.facility_type))
    return tuple(evidence)


def _rollup_recipe_capacity(
    *,
    facility_evidence: Sequence[FacilityCapacityEvidence],
    recipe_match_index: Mapping[str, TargetRecipeMatch],
    required_machine_runs: Mapping[str, Fraction],
) -> tuple[RecipeCapacityRollup, ...]:
    evidence_by_recipe: defaultdict[str, list[FacilityCapacityEvidence]] = defaultdict(list)
    proven_capacity_by_recipe: defaultdict[str, int] = defaultdict(int)
    for entry in facility_evidence:
        if entry.inferred_canonical_recipe_id is None:
            continue
        evidence_by_recipe[entry.inferred_canonical_recipe_id].append(entry)
        if entry.counts_toward_capacity:
            proven_capacity_by_recipe[entry.inferred_canonical_recipe_id] += 1

    rollups: list[RecipeCapacityRollup] = []
    for canonical_recipe_id, required_runs in sorted(required_machine_runs.items()):
        required_runs = _to_fraction(required_runs)
        if required_runs <= 0:
            continue
        match = recipe_match_index.get(canonical_recipe_id)
        related_evidence = evidence_by_recipe.get(canonical_recipe_id, [])
        proven_capacity_units = int(proven_capacity_by_recipe.get(canonical_recipe_id, 0))
        warnings: list[str] = []
        status = "proven_equivalent"

        if match is None:
            status = "unproven_or_insufficient"
            warnings.append("no target recipe match record exists for this canonical recipe")
        elif match.status != "exact_match":
            status = "unproven_or_insufficient"
            warnings.append(f"recipe-equivalence match status is {match.status!r}, not exact_match")
            warnings.extend(match.warnings)

        if Fraction(proven_capacity_units, 1) < required_runs:
            status = "unproven_or_insufficient"
            warnings.append(
                f"proven exported capacity units {proven_capacity_units} are below required fractional runs {str(required_runs)}"
            )
        elif any(entry.proof_status != "proven" for entry in related_evidence):
            if status != "unproven_or_insufficient":
                status = "partially_proven"
                warnings.append("additional related facilities exist but do not count toward proven capacity")

        exact_target_recipe_id = match.matched_target_recipe_id if match and match.status == "exact_match" else None
        expected_machine_type = match.expected_machine_type if match is not None else None
        rollups.append(
            RecipeCapacityRollup(
                canonical_recipe_id=canonical_recipe_id,
                required_fractional_runs=str(required_runs),
                proven_exported_capacity_units=proven_capacity_units,
                expected_machine_type=expected_machine_type,
                exact_target_recipe_id=exact_target_recipe_id,
                status=status,
                warnings=tuple(sorted(set(warnings))),
            )
        )
    return tuple(rollups)


def _audit_boundary_io(
    *,
    blueprint_payload: Mapping[str, Any],
    export_blueprint: Mapping[str, Any],
    flows: Mapping[str, Fraction],
    generic_io_requirements: Mapping[str, Any],
    postprocess_export_mapping_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[BoundaryIORollup, ...]:
    required_output_slots = _normalize_required_slots(
        generic_io_requirements.get("required_generic_outputs"),
        flows=flows,
    )
    required_input_slots = _normalize_required_slots(
        generic_io_requirements.get("required_generic_inputs"),
        flows=flows,
    )
    all_required = {
        **{(commodity_id, "required_output"): slots for commodity_id, slots in required_output_slots.items()},
        **{(commodity_id, "required_input"): slots for commodity_id, slots in required_input_slots.items()},
    }

    proven_slots: defaultdict[tuple[str, str], int] = defaultdict(int)
    partial_surface: defaultdict[tuple[str, str], bool] = defaultdict(bool)
    warnings_by_key: defaultdict[tuple[str, str], list[str]] = defaultdict(list)

    for facility in blueprint_payload.get("facilities", []):
        if not isinstance(facility, Mapping):
            continue
        if str(facility.get("facility_type", "")).strip() != "boundary_storage_port":
            continue
        active_ports = facility.get("active_ports") if isinstance(facility.get("active_ports"), Sequence) else ()
        input_ports = [port for port in active_ports if isinstance(port, Mapping) and str(port.get("type", "")).lower() == "input"]
        output_ports = [port for port in active_ports if isinstance(port, Mapping) and str(port.get("type", "")).lower() == "output"]
        exported_device = _find_exported_device_for_facility(
            export_blueprint,
            facility,
            postprocess_export_mapping_index=postprocess_export_mapping_index,
        )
        exported_type_id = _optional_string(exported_device.get("typeId")) if isinstance(exported_device, Mapping) else None
        exported_config = dict(exported_device.get("config", {})) if isinstance(exported_device, Mapping) and isinstance(exported_device.get("config"), Mapping) else {}

        if output_ports and not input_ports:
            translated_output_ids = []
            for port in output_ports:
                raw_commodity = str(port.get("commodity", "")).strip()
                translation = translate_canonical_item_id(raw_commodity)
                key = (raw_commodity, "required_output")
                if key in all_required:
                    partial_surface[key] = True
                warnings_by_key[key].extend(translation.warnings)
                if translation.translated_item_id is None:
                    if key in all_required:
                        warnings_by_key[key].append("output commodity could not be translated for explicit export-side proof")
                    continue
                translated_output_ids.append((raw_commodity, translation.translated_item_id))

            pickup_item_id = _optional_string(exported_config.get("pickupItemId"))
            protocol_output_item_ids = {
                _optional_string(entry.get("itemId"))
                for entry in exported_config.get("protocolHubOutputs", [])
                if isinstance(entry, Mapping) and _optional_string(entry.get("itemId"))
            }
            counted_commodities: set[str] = set()
            for raw_commodity, translated_item_id in translated_output_ids:
                key = (raw_commodity, "required_output")
                if key not in all_required or raw_commodity in counted_commodities:
                    continue
                if (
                    exported_type_id == "item_port_unloader_1"
                    and pickup_item_id == translated_item_id
                    and translated_item_id in protocol_output_item_ids
                ):
                    proven_slots[key] += 1
                    partial_surface[key] = True
                    counted_commodities.add(raw_commodity)
                else:
                    partial_surface[key] = True
                    warnings_by_key[key].append(
                        "pure output boundary port is visible but lacks matching explicit unloader item binding"
                    )
        elif input_ports and not output_ports:
            counted_commodities: set[str] = set()
            for port in input_ports:
                raw_commodity = str(port.get("commodity", "")).strip()
                key = (raw_commodity, "required_input")
                if key not in all_required or raw_commodity in counted_commodities:
                    continue

                translation = translate_canonical_item_id(raw_commodity)
                warnings_by_key[key].extend(translation.warnings)
                if exported_type_id != "item_port_loader_1":
                    partial_surface[key] = True
                    warnings_by_key[key].append(
                        f"expected loader-like export for pure input boundary port, found {exported_type_id!r}"
                    )
                    continue
                if len(input_ports) != 1:
                    partial_surface[key] = True
                    warnings_by_key[key].append(
                        "pure input boundary port has multiple canonical input declarations; no unique loader admission binding can be proven"
                    )
                    continue
                if translation.translated_item_id is None:
                    partial_surface[key] = True
                    warnings_by_key[key].append(
                        "input commodity could not be translated for explicit loader admission proof"
                    )
                    continue
                if _loader_has_matching_admission_binding(
                    export_blueprint=export_blueprint,
                    exported_loader=exported_device,
                    translated_item_id=translation.translated_item_id,
                ):
                    proven_slots[key] += 1
                    counted_commodities.add(raw_commodity)
                else:
                    partial_surface[key] = True
                    warnings_by_key[key].append(
                        "pure input boundary loader is visible but lacks matching explicit admission-filter item binding"
                    )
        else:
            for port in active_ports:
                if not isinstance(port, Mapping):
                    continue
                raw_commodity = str(port.get("commodity", "")).strip()
                for direction in ("required_output", "required_input"):
                    key = (raw_commodity, direction)
                    if key in all_required:
                        partial_surface[key] = True
                        warnings_by_key[key].append(
                            "mixed boundary_storage_port does not count toward proven item-specific boundary throughput"
                        )

    rollups: list[BoundaryIORollup] = []
    for (commodity_id, direction), required_slots in sorted(all_required.items()):
        key = (commodity_id, direction)
        flow = _to_fraction(flows.get(commodity_id, Fraction(0)))
        proven = int(proven_slots.get(key, 0))
        warnings = list(warnings_by_key.get(key, []))
        if required_slots <= 0:
            status = "proven_equivalent"
        elif proven >= required_slots and not warnings:
            status = "proven_equivalent"
        elif partial_surface.get(key, False) or proven > 0:
            status = "partially_proven"
            if proven < required_slots:
                warnings.append(
                    f"explicit proven boundary slots {proven} are below required slots {required_slots}; remaining item-specific throughput is not proven"
                )
        else:
            status = "unproven_or_insufficient"
            warnings.append("no explicit export-side boundary proof was found for the required commodity")
        rollups.append(
            BoundaryIORollup(
                commodity_id=commodity_id,
                direction=direction,
                required_slots=int(required_slots),
                required_flow_per_tick=str(flow),
                proven_slots=proven,
                status=status,
                warnings=tuple(sorted(set(warnings))),
            )
        )
    return tuple(rollups)


def _build_validation_diagnostics(validation_report: Mapping[str, Any] | None) -> ValidationDiagnostics:
    payload = validation_report if isinstance(validation_report, Mapping) else {}
    is_import_compatible = bool(payload.get("is_import_compatible", False))
    is_layout_healthy = bool(payload.get("is_layout_healthy", False))
    summary_warnings: list[str] = []
    if not is_import_compatible:
        summary_warnings.append("export is not import-compatible")
    if not is_layout_healthy:
        summary_warnings.append("export is not layout-healthy")
    port_warnings = payload.get("port_warnings") if isinstance(payload.get("port_warnings"), Sequence) else ()
    if port_warnings:
        summary_warnings.append(f"validator reported {len(tuple(port_warnings))} port warning(s)")
    overlap_errors = payload.get("overlap_errors") if isinstance(payload.get("overlap_errors"), Sequence) else ()
    if overlap_errors:
        summary_warnings.append(f"validator reported {len(tuple(overlap_errors))} overlap error(s)")
    port_mismatch_errors = payload.get("port_mismatch_errors") if isinstance(payload.get("port_mismatch_errors"), Sequence) else ()
    if port_mismatch_errors:
        summary_warnings.append(f"validator reported {len(tuple(port_mismatch_errors))} port mismatch error(s)")
    return ValidationDiagnostics(
        is_import_compatible=is_import_compatible,
        is_layout_healthy=is_layout_healthy,
        summary_warnings=tuple(summary_warnings),
    )


def _derive_overall_status(
    *,
    recipe_rollups: Sequence[RecipeCapacityRollup],
    boundary_io_rollups: Sequence[BoundaryIORollup],
    facility_evidence: Sequence[FacilityCapacityEvidence],
    validation_diagnostics: ValidationDiagnostics,
) -> str:
    if not validation_diagnostics.is_import_compatible:
        return "unproven_or_insufficient"
    if any(entry.status == "unproven_or_insufficient" for entry in recipe_rollups):
        return "unproven_or_insufficient"
    if any(entry.status == "unproven_or_insufficient" for entry in boundary_io_rollups):
        return "unproven_or_insufficient"

    if not validation_diagnostics.is_layout_healthy:
        return "partially_proven"
    if any(entry.status == "partially_proven" for entry in recipe_rollups):
        return "partially_proven"
    if any(entry.status == "partially_proven" for entry in boundary_io_rollups):
        return "partially_proven"
    if any(entry.proof_status == "partial" for entry in facility_evidence):
        return "partially_proven"
    return "proven_equivalent"


def _build_summary(
    *,
    recipe_matches: Sequence[TargetRecipeMatch],
    recipe_rollups: Sequence[RecipeCapacityRollup],
    boundary_io_rollups: Sequence[BoundaryIORollup],
    validation_diagnostics: ValidationDiagnostics,
) -> dict[str, Any]:
    required_recipe_count = len(recipe_rollups)
    exact_match_recipe_count = sum(1 for entry in recipe_matches if entry.status == "exact_match")
    return {
        "required_recipe_count": required_recipe_count,
        "exact_match_recipe_count": exact_match_recipe_count,
        "proven_recipe_count": sum(1 for entry in recipe_rollups if entry.status == "proven_equivalent"),
        "partial_recipe_count": sum(1 for entry in recipe_rollups if entry.status == "partially_proven"),
        "insufficient_recipe_count": sum(1 for entry in recipe_rollups if entry.status == "unproven_or_insufficient"),
        "required_boundary_commodity_count": len(boundary_io_rollups),
        "proven_boundary_commodity_count": sum(1 for entry in boundary_io_rollups if entry.status == "proven_equivalent"),
        "partial_boundary_commodity_count": sum(1 for entry in boundary_io_rollups if entry.status == "partially_proven"),
        "insufficient_boundary_commodity_count": sum(1 for entry in boundary_io_rollups if entry.status == "unproven_or_insufficient"),
        "validator_import_compatible": bool(validation_diagnostics.is_import_compatible),
        "validator_layout_healthy": bool(validation_diagnostics.is_layout_healthy),
    }


def render_throughput_report_markdown(report: ThroughputAuditReport) -> str:
    lines = [
        "# IndustrialPlanner Throughput Audit Report",
        "",
        "## Overview",
        f"- Overall status: `{report.status}`",
        f"- Required recipes: {report.summary.get('required_recipe_count', 0)}",
        f"- Exact recipe matches: {report.summary.get('exact_match_recipe_count', 0)}",
        f"- Recipe rollups proven / partial / insufficient: {report.summary.get('proven_recipe_count', 0)} / {report.summary.get('partial_recipe_count', 0)} / {report.summary.get('insufficient_recipe_count', 0)}",
        f"- Boundary commodities proven / partial / insufficient: {report.summary.get('proven_boundary_commodity_count', 0)} / {report.summary.get('partial_boundary_commodity_count', 0)} / {report.summary.get('insufficient_boundary_commodity_count', 0)}",
        "",
        "## Recipe-equivalence matches",
    ]
    if report.recipe_matches:
        for entry in report.recipe_matches:
            target_desc = entry.matched_target_recipe_id or "<none>"
            machine_desc = entry.matched_machine_type or entry.expected_machine_type or "<unknown>"
            lines.append(
                f"- `{entry.canonical_recipe_id}`: `{entry.status}` — target recipe `{target_desc}`, machine `{machine_desc}`, cycle `{entry.expected_cycle_seconds or '<unknown>'}`"
            )
            for warning in entry.warnings:
                lines.append(f"  - warning: {warning}")
    else:
        lines.append("- none")
    lines.extend(["", "## Recipe capacity rollup"])
    if report.recipe_rollups:
        for entry in report.recipe_rollups:
            lines.append(
                f"- `{entry.canonical_recipe_id}`: required `{entry.required_fractional_runs}` run(s), proven capacity units `{entry.proven_exported_capacity_units}`, status `{entry.status}`"
            )
            if entry.expected_machine_type:
                lines.append(f"  - expected machine: `{entry.expected_machine_type}`")
            if entry.exact_target_recipe_id:
                lines.append(f"  - exact target recipe: `{entry.exact_target_recipe_id}`")
            for warning in entry.warnings:
                lines.append(f"  - warning: {warning}")
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary I/O audit"])
    if report.boundary_io_rollups:
        for entry in report.boundary_io_rollups:
            lines.append(
                f"- `{entry.commodity_id}` ({entry.direction}): required slots `{entry.required_slots}`, required flow/tick `{entry.required_flow_per_tick}`, proven slots `{entry.proven_slots}`, status `{entry.status}`"
            )
            for warning in entry.warnings:
                lines.append(f"  - warning: {warning}")
    else:
        lines.append("- none")
    lines.extend(["", "## Validator diagnostics"])
    lines.append(
        f"- Import compatible: {'yes' if report.validation_diagnostics.is_import_compatible else 'no'}"
    )
    lines.append(
        f"- Layout healthy: {'yes' if report.validation_diagnostics.is_layout_healthy else 'no'}"
    )
    if report.validation_diagnostics.summary_warnings:
        for warning in report.validation_diagnostics.summary_warnings:
            lines.append(f"- Diagnostic warning: {warning}")
    else:
        lines.append("- Diagnostic warning: none")

    lines.extend(["", "## Facility evidence"])
    if report.facility_evidence:
        for entry in report.facility_evidence:
            lines.append(
                f"- `{entry.instance_id}` ({entry.facility_type}): recipe `{entry.inferred_canonical_recipe_id or '<unknown>'}`, recovery `{entry.recovery_source}`, resolution `{entry.resolution_mode}`, exported type `{entry.exported_type_id or '<none>'}`, proof `{entry.proof_status}`"
            )
            for warning in entry.warnings:
                lines.append(f"  - warning: {warning}")
    else:
        lines.append("- none")

    lines.extend(["", "## Limitations / not proven"])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")
    if report.warnings:
        lines.extend(["", "## Global warnings"])
        for warning in report.warnings:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def _collect_report_warnings(
    *,
    recipe_matches: Sequence[TargetRecipeMatch],
    facility_evidence: Sequence[FacilityCapacityEvidence],
    recipe_rollups: Sequence[RecipeCapacityRollup],
    boundary_io_rollups: Sequence[BoundaryIORollup],
    validation_diagnostics: ValidationDiagnostics,
    compatibility_manifest: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if compatibility_manifest is not None:
        manifest_warnings = compatibility_manifest.get("warnings") if isinstance(compatibility_manifest.get("warnings"), Sequence) else ()
        warnings.extend(str(entry) for entry in manifest_warnings if str(entry).strip())
    warnings.extend(validation_diagnostics.summary_warnings)
    for bucket in (recipe_matches, facility_evidence, recipe_rollups, boundary_io_rollups):
        for entry in bucket:
            warnings.extend(getattr(entry, "warnings", ()))
    return tuple(sorted(set(warnings)))


def _normalize_required_slots(
    raw_mapping: Any,
    *,
    flows: Mapping[str, Fraction],
) -> dict[str, int]:
    mapping = raw_mapping if isinstance(raw_mapping, Mapping) else {}
    port_max = _load_port_max_throughput_per_tick()
    normalized: dict[str, int] = {}
    for commodity_id, raw_value in sorted(mapping.items()):
        normalized[str(commodity_id)] = int(raw_value)
    if normalized:
        return normalized

    fallback: dict[str, int] = {}
    for commodity_id, raw_flow in sorted(flows.items()):
        flow = _to_fraction(raw_flow)
        if flow <= 0:
            continue
        fallback[str(commodity_id)] = _ceil_fraction(flow / port_max)
    return fallback



def _load_postprocess_export_mapping_index(
    compatibility_manifest: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    manifest = compatibility_manifest if isinstance(compatibility_manifest, Mapping) else {}
    section = manifest.get("postprocess_export_mappings") if isinstance(manifest.get("postprocess_export_mappings"), Mapping) else {}
    entries = section.get("entries") if isinstance(section.get("entries"), Sequence) else ()
    index: dict[str, dict[str, Any]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            continue
        canonical_instance_id = str(raw_entry.get("canonical_instance_id", "")).strip()
        if not canonical_instance_id:
            continue
        origin = raw_entry.get("exported_origin") if isinstance(raw_entry.get("exported_origin"), Mapping) else {}
        index[canonical_instance_id] = {
            "origin_x": int(origin.get("x", 0)),
            "origin_y": int(origin.get("y", 0)),
            "rotation": int(raw_entry.get("exported_rotation", 0)),
            "type_id": _optional_string(raw_entry.get("exported_type_id")),
            "mapping_mode": str(raw_entry.get("mapping_mode", "identity") or "identity"),
        }
    return index


def _find_exported_device_for_facility(
    export_blueprint: Mapping[str, Any],
    facility: Mapping[str, Any],
    *,
    postprocess_export_mapping_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> Mapping[str, Any] | None:
    devices = export_blueprint.get("devices") if isinstance(export_blueprint.get("devices"), Sequence) else ()
    instance_id = str(facility.get("instance_id", "")).strip()
    if postprocess_export_mapping_index and instance_id in postprocess_export_mapping_index:
        mapping = postprocess_export_mapping_index[instance_id]
        target_x = int(mapping.get("origin_x", 0))
        target_y = int(mapping.get("origin_y", 0))
        target_rotation = int(mapping.get("rotation", 0))
        target_type_id = _optional_string(mapping.get("type_id"))
        for device in devices:
            if not isinstance(device, Mapping):
                continue
            origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
            if int(origin.get("x", -1)) != target_x or int(origin.get("y", -1)) != target_y:
                continue
            if target_type_id and _optional_string(device.get("typeId")) != target_type_id:
                continue
            if int(device.get("rotation", 0)) != target_rotation:
                continue
            return device
        for device in devices:
            if not isinstance(device, Mapping):
                continue
            origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
            if int(origin.get("x", -1)) == target_x and int(origin.get("y", -1)) == target_y:
                return device

    anchor = facility.get("anchor") if isinstance(facility.get("anchor"), Mapping) else {}
    anchor_x = int(anchor.get("x", 0))
    anchor_y = int(anchor.get("y", 0))
    for device in devices:
        if not isinstance(device, Mapping):
            continue
        origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
        if int(origin.get("x", -1)) == anchor_x and int(origin.get("y", -1)) == anchor_y:
            return device
    return None




def _loader_has_matching_admission_binding(
    *,
    export_blueprint: Mapping[str, Any],
    exported_loader: Mapping[str, Any] | None,
    translated_item_id: str,
) -> bool:
    if not isinstance(exported_loader, Mapping):
        return False
    if _optional_string(exported_loader.get("typeId")) != "item_port_loader_1":
        return False
    origin = exported_loader.get("origin") if isinstance(exported_loader.get("origin"), Mapping) else {}
    rotation = int(exported_loader.get("rotation", 0))
    port_x, port_y, port_edge = _loader_input_port_geometry(origin=origin, rotation=rotation)
    dx, dy = _EDGE_DELTA[port_edge]
    expected_origin = {"x": int(port_x + dx), "y": int(port_y + dy)}
    expected_rotation = _DIRECTION_TO_ROTATION[_OPPOSITE_EDGE[port_edge]]

    devices = export_blueprint.get("devices") if isinstance(export_blueprint.get("devices"), Sequence) else ()
    for device in devices:
        if not isinstance(device, Mapping):
            continue
        if _optional_string(device.get("typeId")) != "item_log_admission":
            continue
        device_origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
        if int(device_origin.get("x", -10**9)) != expected_origin["x"] or int(device_origin.get("y", -10**9)) != expected_origin["y"]:
            continue
        if int(device.get("rotation", -1)) != expected_rotation:
            continue
        config = device.get("config") if isinstance(device.get("config"), Mapping) else {}
        if _optional_string(config.get("admissionItemId")) == str(translated_item_id):
            return True
    return False


def _loader_input_port_geometry(*, origin: Mapping[str, Any], rotation: int) -> tuple[int, int, str]:
    rot_x, rot_y = _rotate_point(1, 0, 3, 1, rotation)
    rotated_edge = _rotate_edge("N", rotation)
    return int(origin.get("x", 0)) + rot_x, int(origin.get("y", 0)) + rot_y, rotated_edge


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

def _ceil_fraction(value: Fraction) -> int:
    if value <= 0:
        return 0
    return int((value.numerator + value.denominator - 1) // value.denominator)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _to_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid Fraction inputs")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    return Fraction(str(value))


__all__ = [
    "BoundaryIORollup",
    "FacilityCapacityEvidence",
    "RecipeCapacityRollup",
    "ThroughputAuditReport",
    "ValidationDiagnostics",
    "build_industrial_planner_throughput_audit",
    "recover_facility_recipe_intent",
    "render_throughput_report_markdown",
]

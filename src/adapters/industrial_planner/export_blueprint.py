"""One-way exporter from canonical `optimal_blueprint.json` to IndustrialPlanner."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable, Mapping, Sequence

from src.adapters.industrial_planner.blueprint_validator import (
    load_static_registries,
    validate_industrial_planner_blueprint,
)
from src.adapters.base_planner.outer_deployment_plan import OuterBaseDeploymentPlan
from src.adapters.industrial_planner.deployment_transform import (
    build_postprocess_export_mapping_section,
    materialize_outer_deployed_blueprint_payload,
    normalize_outer_deployment_plan,
)
from src.adapters.industrial_planner.compatibility_report import (
    build_industrial_planner_manifest,
    industrial_planner_mapping_entries,
)
from src.adapters.industrial_planner.mapping_registry import (
    DEFAULT_BASE_ID,
    INDUSTRIAL_PLANNER_BLUEPRINT_COMPAT_VERSION,
    INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA,
    INDUSTRIAL_PLANNER_BLUEPRINT_VERSION,
    INDUSTRIAL_PLANNER_TARGET,
    PRECISION_MAPPED_FACILITY_TYPES,
    _loader_input_port_geometry,
    industrial_planner_target_capabilities,
    resolve_facility_device,
    resolve_routing_device,
)
from src.adapters.industrial_planner.throughput_audit import build_industrial_planner_throughput_audit
from src.interchange.export_registry import ExportRegistry
from src.io.output_schema import normalize_blueprint_payload
from src.search.exact_campaign import atomic_write_json

INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME = "industrial_planner.blueprint.json"
INDUSTRIAL_PLANNER_MANIFEST_FILENAME = "industrial_planner.compatibility_manifest.json"
INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME = "validation_report.json"
INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME = "validation_report.md"
INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME = "throughput_report.json"
INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME = "throughput_report.md"
INDUSTRIAL_PLANNER_BUNDLE_FILENAMES = (
    INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME,
    INDUSTRIAL_PLANNER_MANIFEST_FILENAME,
    INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME,
    INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME,
    INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME,
    INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME,
)

_BOUNDARY_OUTPUT_BUS_WITNESS_TYPE_ID = "item_port_log_hongs_bus"
_BOUNDARY_OUTPUT_BUS_WITNESS_ROTATION = 90
_WAREHOUSE_BUS_TYPE_IDS = frozenset({"item_port_log_hongs_bus", "item_port_log_hongs_bus_source"})
_OPPOSITE_EDGE = {"N": "S", "S": "N", "W": "E", "E": "W"}
_EDGE_DELTA = {
    "N": (0, -1),
    "S": (0, 1),
    "W": (-1, 0),
    "E": (1, 0),
}


@dataclass(frozen=True)
class IndustrialPlannerExportBundle:
    blueprint: dict[str, Any]
    compatibility_manifest: dict[str, Any]
    validation_report: dict[str, Any]
    validation_report_markdown: str
    throughput_report: dict[str, Any]
    throughput_report_markdown: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IndustrialPlannerWrittenBundle:
    blueprint_path: Path
    compatibility_manifest_path: Path
    validation_report_path: Path
    validation_report_markdown_path: Path
    throughput_report_path: Path
    throughput_report_markdown_path: Path
    blueprint: dict[str, Any]
    compatibility_manifest: dict[str, Any]
    validation_report: dict[str, Any]
    validation_report_markdown: str
    throughput_report: dict[str, Any]
    throughput_report_markdown: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _BoundaryBusRequirement:
    requirement_id: str
    instance_id: str
    exported_origin: tuple[int, int]
    exported_rotation: int
    required_side: str
    target_cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _BoundaryBusCandidate:
    origin_x: int
    origin_y: int
    rotation: int
    footprint: tuple[tuple[int, int], ...]
    covered_requirement_ids: frozenset[str]
    covered_target_cell_count: int

    def to_device(self) -> dict[str, Any]:
        return {
            "typeId": _BOUNDARY_OUTPUT_BUS_WITNESS_TYPE_ID,
            "rotation": int(self.rotation),
            "origin": {"x": int(self.origin_x), "y": int(self.origin_y)},
        }


def build_industrial_planner_export_bundle(
    *,
    blueprint_payload: Mapping[str, Any],
    export_name: str | None = None,
    base_id: str = DEFAULT_BASE_ID,
    include_blueprint_version: bool = True,
    deployment_plan: OuterBaseDeploymentPlan | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    resolved_deployment_plan = (
        normalize_outer_deployment_plan(deployment_plan)
        if deployment_plan is not None
        else None
    )
    resolved_base_id = str(base_id)
    if resolved_deployment_plan is not None:
        if resolved_base_id and resolved_base_id != DEFAULT_BASE_ID and resolved_base_id != resolved_deployment_plan.base_id:
            raise ValueError(
                f"deployment_plan base_id {resolved_deployment_plan.base_id!r} does not match exporter base_id {resolved_base_id!r}"
            )
        resolved_base_id = str(resolved_deployment_plan.base_id)
    working_blueprint = (
        materialize_outer_deployed_blueprint_payload(
            blueprint_payload=normalized_blueprint,
            deployment_plan=resolved_deployment_plan,
        )
        if resolved_deployment_plan is not None
        else normalized_blueprint
    )
    warnings: list[str] = []
    primary_facility_devices: list[dict[str, Any]] = []
    auxiliary_facility_devices: list[dict[str, Any]] = []
    routing_devices: list[dict[str, Any]] = []
    exported_protocol_core_count = 0
    exported_auxiliary_device_count = 0
    used_liquid_heuristics = False
    has_elevated_layer = False
    precise_resolution_count = 0
    generic_fallback_count = 0
    unresolved_facility_count = 0
    commodity_translation_miss_count = 0

    for facility in working_blueprint["facilities"]:
        facility_type = str(facility.get("facility_type", "")).strip()
        resolved = resolve_facility_device(facility, default_base_id=resolved_base_id)
        warnings.extend(resolved.warnings)
        commodity_translation_miss_count += int(resolved.translation_miss_count)
        if facility_type in PRECISION_MAPPED_FACILITY_TYPES:
            if resolved.resolution_mode == "precise":
                precise_resolution_count += 1
            else:
                generic_fallback_count += 1
                unresolved_facility_count += 1
        if resolved.target_type_id is None:
            if facility_type == "protocol_core":
                exported_protocol_core_count += 1
            continue
        device = resolved.to_device()
        if device is not None:
            primary_facility_devices.append(device)
        if resolved.auxiliary_devices:
            auxiliary_facility_devices.extend(dict(entry) for entry in resolved.auxiliary_devices)
            exported_auxiliary_device_count += len(resolved.auxiliary_devices)

    routing_network = working_blueprint["routing_network"]
    for layer_name in ("L0_ground", "L1_elevated"):
        layer = routing_network.get(layer_name, {})
        if layer_name == "L1_elevated" and layer:
            has_elevated_layer = True
        for coord_key, cell in layer.items():
            x, y = _parse_coord_key(coord_key)
            resolved_routing = resolve_routing_device(x=x, y=y, layer_name=layer_name, cell=cell)
            warnings.extend(resolved_routing.warnings)
            if "liquid" in resolved_routing.target_type_id or "pipe_" in resolved_routing.target_type_id:
                used_liquid_heuristics = True
            routing_devices.append(resolved_routing.to_device())

    boundary_output_bus_witness_devices, boundary_output_bus_witness_warnings = _build_boundary_output_bus_witness_devices(
        blueprint_payload=working_blueprint,
        primary_facility_devices=primary_facility_devices,
        auxiliary_facility_devices=auxiliary_facility_devices,
        routing_devices=routing_devices,
        base_id=resolved_base_id,
    )
    if boundary_output_bus_witness_devices:
        auxiliary_facility_devices.extend(boundary_output_bus_witness_devices)
        exported_auxiliary_device_count += len(boundary_output_bus_witness_devices)
    warnings.extend(boundary_output_bus_witness_warnings)

    boundary_input_bus_witness_devices, boundary_input_bus_witness_warnings = _build_boundary_input_bus_witness_devices(
        blueprint_payload=working_blueprint,
        primary_facility_devices=primary_facility_devices,
        auxiliary_facility_devices=auxiliary_facility_devices,
        routing_devices=routing_devices,
        base_id=resolved_base_id,
    )
    if boundary_input_bus_witness_devices:
        auxiliary_facility_devices.extend(boundary_input_bus_witness_devices)
        exported_auxiliary_device_count += len(boundary_input_bus_witness_devices)
    warnings.extend(boundary_input_bus_witness_warnings)

    devices = primary_facility_devices + auxiliary_facility_devices + routing_devices
    devices.sort(
        key=lambda entry: (
            int(entry["origin"]["x"]),
            int(entry["origin"]["y"]),
            str(entry["typeId"]),
            int(entry["rotation"]),
        )
    )

    export_timestamp = str(normalized_blueprint["metadata"]["export_timestamp"])
    export_hash = hashlib.sha256(
        json.dumps(normalized_blueprint, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    resolved_name = str(export_name or f"Exact Export {export_timestamp}")

    target_blueprint = {
        "schema": INDUSTRIAL_PLANNER_BLUEPRINT_SCHEMA,
        "id": f"ExactExport-{export_hash}",
        "version": INDUSTRIAL_PLANNER_BLUEPRINT_VERSION,
        "name": resolved_name,
        "createdAt": export_timestamp,
        "baseId": str(resolved_base_id),
        "devices": devices,
    }
    if include_blueprint_version:
        target_blueprint["blueprintVersion"] = INDUSTRIAL_PLANNER_BLUEPRINT_COMPAT_VERSION

    validation_report_obj = validate_industrial_planner_blueprint(target_blueprint)
    validation_report = validation_report_obj.to_dict()
    validation_report_markdown = validation_report_obj.to_markdown()

    capabilities = industrial_planner_target_capabilities()
    manifest = build_industrial_planner_manifest(
        source_blueprint_version=str(normalized_blueprint["metadata"]["version"]),
        generated_at=export_timestamp,
        target_capabilities=capabilities,
        mapping_entries=industrial_planner_mapping_entries(
            exported_protocol_core_count=exported_protocol_core_count,
            exported_facility_count=len(primary_facility_devices),
            exported_routing_device_count=len(routing_devices),
            precise_resolution_count=precise_resolution_count,
            generic_fallback_count=generic_fallback_count,
            unresolved_facility_count=unresolved_facility_count,
            commodity_translation_miss_count=commodity_translation_miss_count,
            has_elevated_layer=has_elevated_layer,
            used_liquid_heuristics=used_liquid_heuristics,
            has_outer_deployment_plan=resolved_deployment_plan is not None,
        ),
        warnings=sorted(set(str(warning) for warning in warnings if str(warning).strip())),
        metadata_extensions={
            "source_facility_count": len(normalized_blueprint["facilities"]),
            "source_routing_cell_count": sum(len(layer) for layer in normalized_blueprint["routing_network"].values()),
            "target_device_count": len(devices),
            "exported_auxiliary_device_count": int(exported_auxiliary_device_count),
            "base_id": str(resolved_base_id),
            "export_id": f"ExactExport-{export_hash}",
            "precise_resolution_count": int(precise_resolution_count),
            "has_outer_deployment_plan": bool(resolved_deployment_plan is not None),
            "translated_export_mapping_count": (
                sum(1 for entry in resolved_deployment_plan.export_mappings if entry.mapping_mode != "identity")
                if resolved_deployment_plan is not None
                else 0
            ),
            "generic_fallback_count": int(generic_fallback_count),
            "unresolved_facility_count": int(unresolved_facility_count),
            "commodity_translation_miss_count": int(commodity_translation_miss_count),
            "has_commodity_translation_miss": bool(commodity_translation_miss_count > 0),
            "validation_is_import_compatible": bool(validation_report["is_import_compatible"]),
            "validation_is_layout_healthy": bool(validation_report["is_layout_healthy"]),
            "clean_export": bool(validation_report["is_import_compatible"] and validation_report["is_layout_healthy"]),
            **(
                {
                    "outer_deployment_plan_version": str(resolved_deployment_plan.plan_version),
                    "outer_deployment_planning_status": str(resolved_deployment_plan.planning_status),
                    "outer_deployment_inner_island_origin": resolved_deployment_plan.inner_island_origin.to_dict(),
                    "outer_deployment_moat_thickness_by_edge": dict(resolved_deployment_plan.moat_thickness_by_edge),
                }
                if resolved_deployment_plan is not None
                else {}
            ),
        },
        postprocess_export_mappings=(
            build_postprocess_export_mapping_section(
                deployment_plan=resolved_deployment_plan,
                export_blueprint=target_blueprint,
            )
            if resolved_deployment_plan is not None
            else None
        ),
    )

    throughput_report_obj = build_industrial_planner_throughput_audit(
        blueprint_payload=normalized_blueprint,
        export_blueprint=target_blueprint,
        compatibility_manifest=manifest,
        validation_report=validation_report,
        base_id=resolved_base_id,
    )
    throughput_report = throughput_report_obj.to_dict()
    throughput_report_markdown = throughput_report_obj.to_markdown()

    return {
        "target": INDUSTRIAL_PLANNER_TARGET,
        "mode": "one_way_lossy",
        "target_capabilities": capabilities,
        "blueprint": target_blueprint,
        "compatibility_manifest": manifest,
        "validation_report": validation_report,
        "validation_report_markdown": validation_report_markdown,
        "throughput_report": throughput_report,
        "throughput_report_markdown": throughput_report_markdown,
        "warnings": sorted(set(str(warning) for warning in warnings if str(warning).strip())),
    }


def write_industrial_planner_export_bundle(
    *,
    output_dir: Path,
    blueprint_payload: Mapping[str, Any],
    export_name: str | None = None,
    base_id: str = DEFAULT_BASE_ID,
    deployment_plan: OuterBaseDeploymentPlan | Mapping[str, Any] | None = None,
) -> IndustrialPlannerWrittenBundle:
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        bundle = build_industrial_planner_export_bundle(
            blueprint_payload=blueprint_payload,
            export_name=export_name,
            base_id=base_id,
            deployment_plan=deployment_plan,
        )
        with tempfile.TemporaryDirectory(
            prefix=".industrial-planner-generation-",
            dir=str(output_dir),
        ) as tmp:
            staging_dir = Path(tmp)
            _write_industrial_planner_bundle_files(staging_dir, bundle)
            _commit_industrial_planner_bundle(staging_dir=staging_dir, output_dir=output_dir)
    except Exception as exc:
        try:
            clear_industrial_planner_export_bundle(output_dir)
        except Exception as cleanup_exc:
            raise RuntimeError(
                "industrial planner bundle generation failed and cleanup failed: "
                f"{cleanup_exc}"
            ) from exc
        raise

    blueprint_path = output_dir / INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME
    manifest_path = output_dir / INDUSTRIAL_PLANNER_MANIFEST_FILENAME
    validation_report_path = output_dir / INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME
    validation_report_markdown_path = output_dir / INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME
    throughput_report_path = output_dir / INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME
    throughput_report_markdown_path = output_dir / INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME

    return IndustrialPlannerWrittenBundle(
        blueprint_path=blueprint_path,
        compatibility_manifest_path=manifest_path,
        validation_report_path=validation_report_path,
        validation_report_markdown_path=validation_report_markdown_path,
        throughput_report_path=throughput_report_path,
        throughput_report_markdown_path=throughput_report_markdown_path,
        blueprint=dict(bundle["blueprint"]),
        compatibility_manifest=dict(bundle["compatibility_manifest"]),
        validation_report=dict(bundle["validation_report"]),
        validation_report_markdown=str(bundle["validation_report_markdown"]),
        throughput_report=dict(bundle["throughput_report"]),
        throughput_report_markdown=str(bundle["throughput_report_markdown"]),
        warnings=tuple(bundle["warnings"]),
    )


def clear_industrial_planner_export_bundle(output_dir: Path) -> None:
    output_dir = Path(output_dir)
    cleanup_errors: list[str] = []
    for filename in INDUSTRIAL_PLANNER_BUNDLE_FILENAMES:
        artifact_path = output_dir / filename
        try:
            if artifact_path.is_dir() and not artifact_path.is_symlink():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - cleanup must attempt every bundle file.
            cleanup_errors.append(f"{artifact_path}:{type(exc).__name__}:{exc}")
    if output_dir.exists():
        for staging_dir in output_dir.glob(".industrial-planner-generation-*"):
            if not staging_dir.is_dir():
                continue
            try:
                shutil.rmtree(staging_dir)
            except FileNotFoundError:
                continue
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(f"{staging_dir}:{type(exc).__name__}:{exc}")
    if cleanup_errors:
        raise RuntimeError("industrial planner bundle cleanup failed: " + ";".join(cleanup_errors))


def _write_industrial_planner_bundle_files(
    output_dir: Path,
    bundle: Mapping[str, Any],
) -> None:
    atomic_write_json(output_dir / INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME, bundle["blueprint"])
    atomic_write_json(
        output_dir / INDUSTRIAL_PLANNER_MANIFEST_FILENAME,
        bundle["compatibility_manifest"],
    )
    atomic_write_json(
        output_dir / INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME,
        bundle["validation_report"],
    )
    (output_dir / INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME).write_text(
        str(bundle["validation_report_markdown"]),
        encoding="utf-8",
    )
    atomic_write_json(
        output_dir / INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME,
        bundle["throughput_report"],
    )
    (output_dir / INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME).write_text(
        str(bundle["throughput_report_markdown"]),
        encoding="utf-8",
    )


def _commit_industrial_planner_bundle(*, staging_dir: Path, output_dir: Path) -> None:
    try:
        for filename in INDUSTRIAL_PLANNER_BUNDLE_FILENAMES:
            (staging_dir / filename).replace(output_dir / filename)
    except Exception:
        clear_industrial_planner_export_bundle(output_dir)
        raise


def register_industrial_planner_exporter(registry: ExportRegistry) -> None:
    registry.register(
        INDUSTRIAL_PLANNER_TARGET,
        build_industrial_planner_export_bundle,
        description="One-way exporter from the canonical blueprint artifact into IndustrialPlanner-compatible blueprint JSON.",
        mode="one_way_lossy",
        target_capabilities=industrial_planner_target_capabilities(),
        provenance={
            "upstream_repository": "https://github.com/hsyhhssyy/IndustrialPlanner",
            "integration_type": "one_way_export",
        },
    )


def _build_boundary_output_bus_witness_devices(
    *,
    blueprint_payload: Mapping[str, Any],
    primary_facility_devices: Sequence[Mapping[str, Any]],
    auxiliary_facility_devices: Sequence[Mapping[str, Any]],
    routing_devices: Sequence[Mapping[str, Any]],
    base_id: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    registries = load_static_registries()
    base_def = registries.base_by_id.get(str(base_id))
    if base_def is None:
        return (), ()
    lot_size = int(base_def.get("placeableSize", 0))
    if lot_size <= 0:
        return (), ()

    existing_devices: list[Mapping[str, Any]] = [
        *primary_facility_devices,
        *auxiliary_facility_devices,
        *routing_devices,
        *_foundation_devices_for_base(base_def),
    ]
    occupied_cells = _collect_occupied_cells(existing_devices, registries=registries)
    bus_occupied_cells = _collect_bus_occupied_cells(existing_devices, registries=registries)

    requirements, requirement_warnings = _collect_boundary_output_bus_requirements(
        blueprint_payload=blueprint_payload,
        primary_facility_devices=primary_facility_devices,
        lot_size=lot_size,
        bus_occupied_cells=bus_occupied_cells,
        base_id=str(base_id),
        registries=registries,
    )
    witness_devices, witness_warnings = _select_boundary_bus_witness_devices(
        requirements=requirements,
        lot_size=lot_size,
        occupied_cells=occupied_cells,
        registries=registries,
    )
    return tuple(witness_devices), tuple(sorted(set([*requirement_warnings, *witness_warnings])))


def _build_boundary_input_bus_witness_devices(
    *,
    blueprint_payload: Mapping[str, Any],
    primary_facility_devices: Sequence[Mapping[str, Any]],
    auxiliary_facility_devices: Sequence[Mapping[str, Any]],
    routing_devices: Sequence[Mapping[str, Any]],
    base_id: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    registries = load_static_registries()
    base_def = registries.base_by_id.get(str(base_id))
    if base_def is None:
        return (), ()
    lot_size = int(base_def.get("placeableSize", 0))
    if lot_size <= 0:
        return (), ()

    existing_devices: list[Mapping[str, Any]] = [
        *primary_facility_devices,
        *auxiliary_facility_devices,
        *routing_devices,
        *_foundation_devices_for_base(base_def),
    ]
    occupied_cells = _collect_occupied_cells(existing_devices, registries=registries)
    bus_occupied_cells = _collect_bus_occupied_cells(existing_devices, registries=registries)

    requirements, requirement_warnings = _collect_boundary_input_bus_requirements(
        blueprint_payload=blueprint_payload,
        primary_facility_devices=primary_facility_devices,
        lot_size=lot_size,
        bus_occupied_cells=bus_occupied_cells,
        base_id=str(base_id),
        registries=registries,
    )
    witness_devices, witness_warnings = _select_boundary_bus_witness_devices(
        requirements=requirements,
        lot_size=lot_size,
        occupied_cells=occupied_cells,
        registries=registries,
    )
    return tuple(witness_devices), tuple(sorted(set([*requirement_warnings, *witness_warnings])))


def _collect_boundary_input_bus_requirements(
    *,
    blueprint_payload: Mapping[str, Any],
    primary_facility_devices: Sequence[Mapping[str, Any]],
    lot_size: int,
    bus_occupied_cells: set[tuple[int, int]],
    base_id: str,
    registries: Any,
) -> tuple[tuple[_BoundaryBusRequirement, ...], tuple[str, ...]]:
    requirements: list[_BoundaryBusRequirement] = []
    warnings: list[str] = []

    for facility in blueprint_payload.get("facilities", []):
        if not isinstance(facility, Mapping) or not _is_pure_input_boundary_port(facility):
            continue
        exported_device = _find_exported_device_at_origin(primary_facility_devices, facility)
        if exported_device is None or str(exported_device.get("typeId", "")).strip() != "item_port_loader_1":
            continue
        required_side = _loader_required_bus_side(int(exported_device.get("rotation", 0)))
        boundary_cells = _device_boundary_cells(exported_device, side=required_side, registries=registries)
        adjacent_cells = tuple(
            sorted(
                {
                    cell
                    for cell in _adjacent_cells_for_side(boundary_cells, side=required_side)
                }
            )
        )
        if adjacent_cells and any(cell in bus_occupied_cells for cell in adjacent_cells):
            continue

        in_lot_target_cells = tuple(cell for cell in adjacent_cells if _cell_within_lot(cell, lot_size=lot_size))
        instance_id = str(facility.get("instance_id", "")).strip() or "<unknown>"
        device_origin = exported_device.get("origin") if isinstance(exported_device.get("origin"), Mapping) else {}
        exported_origin = (int(device_origin.get("x", 0)), int(device_origin.get("y", 0)))
        if not in_lot_target_cells:
            warnings.append(
                "boundary input "
                f"{instance_id} at {exported_origin[0]},{exported_origin[1]} requires {required_side}-side bus coverage "
                f"outside base {base_id!r}; exporter could not synthesize an in-lot witness"
            )
            continue

        requirements.append(
            _BoundaryBusRequirement(
                requirement_id=instance_id,
                instance_id=instance_id,
                exported_origin=exported_origin,
                exported_rotation=int(exported_device.get("rotation", 0)),
                required_side=required_side,
                target_cells=in_lot_target_cells,
            )
        )

    requirements.sort(key=lambda entry: (entry.required_side, entry.exported_origin[1], entry.exported_origin[0], entry.instance_id))
    return tuple(requirements), tuple(sorted(set(warnings)))


def _collect_boundary_output_bus_requirements(
    *,
    blueprint_payload: Mapping[str, Any],
    primary_facility_devices: Sequence[Mapping[str, Any]],
    lot_size: int,
    bus_occupied_cells: set[tuple[int, int]],
    base_id: str,
    registries: Any,
) -> tuple[tuple[_BoundaryBusRequirement, ...], tuple[str, ...]]:
    requirements: list[_BoundaryBusRequirement] = []
    warnings: list[str] = []

    for facility in blueprint_payload.get("facilities", []):
        if not isinstance(facility, Mapping) or not _is_pure_output_boundary_port(facility):
            continue
        exported_device = _find_exported_device_at_origin(primary_facility_devices, facility)
        if exported_device is None or str(exported_device.get("typeId", "")).strip() != "item_port_unloader_1":
            continue
        required_side = _unloader_required_bus_side(int(exported_device.get("rotation", 0)))
        boundary_cells = _device_boundary_cells(exported_device, side=required_side, registries=registries)
        adjacent_cells = tuple(
            sorted(
                {
                    cell
                    for cell in _adjacent_cells_for_side(boundary_cells, side=required_side)
                }
            )
        )
        if adjacent_cells and any(cell in bus_occupied_cells for cell in adjacent_cells):
            continue

        in_lot_target_cells = tuple(cell for cell in adjacent_cells if _cell_within_lot(cell, lot_size=lot_size))
        instance_id = str(facility.get("instance_id", "")).strip() or "<unknown>"
        device_origin = exported_device.get("origin") if isinstance(exported_device.get("origin"), Mapping) else {}
        exported_origin = (int(device_origin.get("x", 0)), int(device_origin.get("y", 0)))
        if not in_lot_target_cells:
            warnings.append(
                "boundary output "
                f"{instance_id} at {exported_origin[0]},{exported_origin[1]} requires {required_side}-side bus coverage "
                f"outside base {base_id!r}; exporter could not synthesize an in-lot witness"
            )
            continue

        requirements.append(
            _BoundaryBusRequirement(
                requirement_id=instance_id,
                instance_id=instance_id,
                exported_origin=exported_origin,
                exported_rotation=int(exported_device.get("rotation", 0)),
                required_side=required_side,
                target_cells=in_lot_target_cells,
            )
        )

    requirements.sort(key=lambda entry: (entry.required_side, entry.exported_origin[1], entry.exported_origin[0], entry.instance_id))
    return tuple(requirements), tuple(sorted(set(warnings)))


def _select_boundary_bus_witness_devices(
    *,
    requirements: Sequence[_BoundaryBusRequirement],
    lot_size: int,
    occupied_cells: set[tuple[int, int]],
    registries: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not requirements:
        return [], []

    candidates = _enumerate_boundary_bus_candidates(
        requirements=requirements,
        lot_size=lot_size,
        occupied_cells=occupied_cells,
        registries=registries,
    )
    selected_devices: list[dict[str, Any]] = []
    warnings: list[str] = []
    blocked_cells = set(occupied_cells)
    uncovered = {entry.requirement_id for entry in requirements}

    while uncovered:
        best: _BoundaryBusCandidate | None = None
        best_key: tuple[int, int, int, int, int] | None = None
        for candidate in candidates:
            if any(cell in blocked_cells for cell in candidate.footprint):
                continue
            covered_now = candidate.covered_requirement_ids & uncovered
            if not covered_now:
                continue
            score = (
                len(covered_now),
                candidate.covered_target_cell_count,
                -int(candidate.rotation),
                -int(candidate.origin_y),
                -int(candidate.origin_x),
            )
            if best is None or score > best_key:
                best = candidate
                best_key = score
        if best is None:
            break
        selected_devices.append(best.to_device())
        blocked_cells.update(best.footprint)
        uncovered.difference_update(best.covered_requirement_ids)

    if uncovered:
        requirement_by_id = {entry.requirement_id: entry for entry in requirements}
        for requirement_id in sorted(uncovered):
            requirement = requirement_by_id[requirement_id]
            warnings.append(
                "no clean grouped bus witness could be placed for boundary output "
                f"{requirement.instance_id} at {requirement.exported_origin[0]},{requirement.exported_origin[1]} "
                f"requiring {requirement.required_side}-side bus coverage"
            )

    return selected_devices, warnings


def _enumerate_boundary_bus_candidates(
    *,
    requirements: Sequence[_BoundaryBusRequirement],
    lot_size: int,
    occupied_cells: set[tuple[int, int]],
    registries: Any,
) -> tuple[_BoundaryBusCandidate, ...]:
    bus_def = registries.device_types_by_id.get(_BOUNDARY_OUTPUT_BUS_WITNESS_TYPE_ID)
    if not isinstance(bus_def, Mapping):
        return ()
    size_payload = bus_def.get("size") if isinstance(bus_def.get("size"), Mapping) else {}
    candidate_payloads: dict[tuple[int, int, int], dict[str, Any]] = {}

    for requirement in requirements:
        target_cells = set(requirement.target_cells)
        for rotation in (0, _BOUNDARY_OUTPUT_BUS_WITNESS_ROTATION):
            width, height = _rotated_size(size_payload, rotation)
            if width <= 0 or height <= 0:
                continue
            for target_x, target_y in requirement.target_cells:
                min_origin_x = max(0, target_x - width + 1)
                max_origin_x = min(target_x, lot_size - width)
                min_origin_y = max(0, target_y - height + 1)
                max_origin_y = min(target_y, lot_size - height)
                for origin_x in range(min_origin_x, max_origin_x + 1):
                    for origin_y in range(min_origin_y, max_origin_y + 1):
                        key = (int(origin_x), int(origin_y), int(rotation))
                        payload = candidate_payloads.get(key)
                        if payload is None:
                            candidate_device = {
                                "typeId": _BOUNDARY_OUTPUT_BUS_WITNESS_TYPE_ID,
                                "rotation": int(rotation),
                                "origin": {"x": int(origin_x), "y": int(origin_y)},
                            }
                            footprint = _device_footprint_cells(candidate_device, registries=registries)
                            if not footprint or any(cell in occupied_cells for cell in footprint):
                                candidate_payloads[key] = {"invalid": True}
                                continue
                            footprint_set = set(footprint)
                            payload = {
                                "footprint": footprint,
                                "footprint_set": footprint_set,
                                "covered_requirement_ids": set(),
                                "covered_target_cells": set(),
                            }
                            candidate_payloads[key] = payload
                        if payload.get("invalid"):
                            continue
                        footprint_set = payload["footprint_set"]
                        if not (footprint_set & target_cells):
                            continue
                        payload["covered_requirement_ids"].add(requirement.requirement_id)
                        payload["covered_target_cells"].update(footprint_set & target_cells)

    candidates: list[_BoundaryBusCandidate] = []
    for (origin_x, origin_y, rotation), payload in sorted(candidate_payloads.items()):
        if payload.get("invalid") or not payload.get("covered_requirement_ids"):
            continue
        candidates.append(
            _BoundaryBusCandidate(
                origin_x=int(origin_x),
                origin_y=int(origin_y),
                rotation=int(rotation),
                footprint=tuple(payload["footprint"]),
                covered_requirement_ids=frozenset(str(value) for value in payload["covered_requirement_ids"]),
                covered_target_cell_count=len(payload["covered_target_cells"]),
            )
        )
    return tuple(candidates)


def _device_boundary_cells(
    device: Mapping[str, Any],
    *,
    side: str,
    registries: Any,
) -> tuple[tuple[int, int], ...]:
    type_id = str(device.get("typeId", "")).strip()
    device_def = registries.device_types_by_id.get(type_id)
    if not isinstance(device_def, Mapping):
        return ()
    size_payload = device_def.get("size") if isinstance(device_def.get("size"), Mapping) else {}
    width, height = _rotated_size(size_payload, int(device.get("rotation", 0)))
    origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
    origin_x = int(origin.get("x", 0))
    origin_y = int(origin.get("y", 0))
    if side == "N":
        return tuple((origin_x + index, origin_y) for index in range(width))
    if side == "S":
        return tuple((origin_x + index, origin_y + height - 1) for index in range(width))
    if side == "W":
        return tuple((origin_x, origin_y + index) for index in range(height))
    return tuple((origin_x + width - 1, origin_y + index) for index in range(height))


def _adjacent_cells_for_side(
    boundary_cells: Sequence[tuple[int, int]],
    *,
    side: str,
) -> tuple[tuple[int, int], ...]:
    delta_x, delta_y = _EDGE_DELTA.get(str(side).strip().upper(), (0, 0))
    return tuple((cell_x + delta_x, cell_y + delta_y) for cell_x, cell_y in boundary_cells)


def _cell_within_lot(cell: tuple[int, int], *, lot_size: int) -> bool:
    cell_x, cell_y = cell
    return 0 <= cell_x < lot_size and 0 <= cell_y < lot_size


def _collect_occupied_cells(
    devices: Iterable[Mapping[str, Any]],
    *,
    registries: Any,
) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for device in devices:
        occupied.update(_device_footprint_cells(device, registries=registries))
    return occupied


def _collect_bus_occupied_cells(
    devices: Iterable[Mapping[str, Any]],
    *,
    registries: Any,
) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for device in devices:
        type_id = str(device.get("typeId", "")).strip()
        if not type_id or type_id not in _WAREHOUSE_BUS_TYPE_IDS:
            continue
        occupied.update(_device_footprint_cells(device, registries=registries))
    return occupied


def _device_footprint_cells(device: Mapping[str, Any], *, registries: Any) -> tuple[tuple[int, int], ...]:
    type_id = str(device.get("typeId", "")).strip()
    device_def = registries.device_types_by_id.get(type_id)
    if not isinstance(device_def, Mapping):
        return ()
    size = device_def.get("size") if isinstance(device_def.get("size"), Mapping) else {}
    width = int(size.get("width", 0))
    height = int(size.get("height", 0))
    origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
    origin_x = int(origin.get("x", 0))
    origin_y = int(origin.get("y", 0))
    rotation = int(device.get("rotation", 0))
    cells: list[tuple[int, int]] = []
    for local_y in range(height):
        for local_x in range(width):
            rot_x, rot_y = _rotate_point(local_x, local_y, width, height, rotation)
            cells.append((origin_x + rot_x, origin_y + rot_y))
    return tuple(cells)


def _rotated_size(size_payload: Mapping[str, Any], rotation: int) -> tuple[int, int]:
    width = int(size_payload.get("width", 0))
    height = int(size_payload.get("height", 0))
    if int(rotation) % 180 == 0:
        return width, height
    return height, width


def _rotate_point(x: int, y: int, width: int, height: int, rotation: int) -> tuple[int, int]:
    normalized_rotation = int(rotation) % 360
    if normalized_rotation == 0:
        return x, y
    if normalized_rotation == 90:
        return height - 1 - y, x
    if normalized_rotation == 180:
        return width - 1 - x, height - 1 - y
    return y, width - 1 - x


def _foundation_devices_for_base(base_def: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    payload = base_def.get("foundationBuildings") if isinstance(base_def.get("foundationBuildings"), Sequence) else ()
    devices: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            continue
        origin = entry.get("origin") if isinstance(entry.get("origin"), Mapping) else {}
        devices.append(
            {
                "typeId": str(entry.get("typeId", "")).strip(),
                "rotation": int(entry.get("rotation", 0)),
                "origin": {"x": int(origin.get("x", 0)), "y": int(origin.get("y", 0))},
            }
        )
    return tuple(devices)


def _find_exported_device_at_origin(
    devices: Sequence[Mapping[str, Any]],
    facility: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    anchor = facility.get("anchor") if isinstance(facility.get("anchor"), Mapping) else {}
    anchor_x = int(anchor.get("x", 0))
    anchor_y = int(anchor.get("y", 0))
    for device in devices:
        origin = device.get("origin") if isinstance(device.get("origin"), Mapping) else {}
        if int(origin.get("x", -1)) == anchor_x and int(origin.get("y", -1)) == anchor_y:
            return device
    return None


def _loader_required_bus_side(rotation: int) -> str:
    _, _, port_edge = _loader_input_port_geometry(
        loader_origin={"x": 0, "y": 0},
        loader_rotation=int(rotation),
    )
    return _OPPOSITE_EDGE[port_edge]


def _is_pure_input_boundary_port(facility: Mapping[str, Any]) -> bool:
    if str(facility.get("facility_type", "")).strip() != "boundary_storage_port":
        return False
    active_ports = facility.get("active_ports") if isinstance(facility.get("active_ports"), Sequence) else ()
    input_count = 0
    output_count = 0
    for port in active_ports:
        if not isinstance(port, Mapping):
            continue
        port_type = str(port.get("type", "")).strip().lower()
        if port_type == "input":
            input_count += 1
        elif port_type == "output":
            output_count += 1
    return bool(input_count > 0 and output_count == 0)


def _is_pure_output_boundary_port(facility: Mapping[str, Any]) -> bool:
    if str(facility.get("facility_type", "")).strip() != "boundary_storage_port":
        return False
    active_ports = facility.get("active_ports") if isinstance(facility.get("active_ports"), Sequence) else ()
    input_count = 0
    output_count = 0
    for port in active_ports:
        if not isinstance(port, Mapping):
            continue
        port_type = str(port.get("type", "")).strip().lower()
        if port_type == "input":
            input_count += 1
        elif port_type == "output":
            output_count += 1
    return bool(output_count > 0 and input_count == 0)


def _unloader_required_bus_side(rotation: int) -> str:
    edge_order = ("N", "E", "S", "W")
    steps = int((int(rotation) % 360) // 90)
    port_edge = edge_order[steps % len(edge_order)]
    return {
        "N": "S",
        "S": "N",
        "E": "W",
        "W": "E",
    }[port_edge]


def _parse_coord_key(raw_key: str) -> tuple[int, int]:
    x_text, y_text = str(raw_key).split(",", 1)
    return int(x_text), int(y_text)

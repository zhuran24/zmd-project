"""Compatibility sidecar helpers for IndustrialPlanner export."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.interchange.compatibility_manifest import (
    build_compatibility_manifest,
    build_mapping_entry,
)


def build_industrial_planner_manifest(
    *,
    source_blueprint_version: str,
    target_capabilities: Mapping[str, Any],
    mapping_entries: Iterable[Mapping[str, Any]],
    warnings: Sequence[str],
    metadata_extensions: Mapping[str, Any] | None = None,
    postprocess_export_mappings: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    manifest = build_compatibility_manifest(
        target="industrial_planner",
        export_mode="one_way_lossy",
        source_blueprint_version=source_blueprint_version,
        target_capabilities=target_capabilities,
        mapping_entries=mapping_entries,
        warnings=warnings,
        metadata_extensions=metadata_extensions,
        generated_at=generated_at,
    )
    if postprocess_export_mappings:
        manifest["postprocess_export_mappings"] = dict(postprocess_export_mappings)
    return manifest


def industrial_planner_mapping_entries(
    *,
    exported_protocol_core_count: int,
    exported_facility_count: int,
    exported_routing_device_count: int,
    precise_resolution_count: int,
    generic_fallback_count: int,
    unresolved_facility_count: int,
    commodity_translation_miss_count: int,
    has_elevated_layer: bool,
    used_liquid_heuristics: bool,
    has_outer_deployment_plan: bool = False,
) -> list[dict[str, Any]]:
    entries = [
        build_mapping_entry(
            classification="direct",
            source_path="metadata.export_timestamp",
            target_path="createdAt",
            reason="canonical export timestamp is preserved in the target blueprint root",
        ),
    ]

    if has_outer_deployment_plan:
        entries.extend(
            [
                build_mapping_entry(
                    classification="derived",
                    source_path="facilities[].anchor",
                    target_path="devices[].origin",
                    reason="when an adapter-side outer deployment plan is supplied, canonical facility anchors are translated through explicit postprocess export mappings before serialization",
                ),
                build_mapping_entry(
                    classification="derived",
                    source_path="facilities[].orientation",
                    target_path="devices[].rotation",
                    reason="when an adapter-side outer deployment plan is supplied, canonical orientation is translated through explicit postprocess export mappings before serialization",
                ),
                build_mapping_entry(
                    classification="derived",
                    source_path="(postprocess sidecar) outer_deployment_plan.export_mappings[]",
                    target_path="postprocess_export_mappings.entries[]",
                    reason="postprocess-only export mappings bridge canonical instance ids to translated exported devices so downstream throughput audit can locate moved geometry without widening the canonical schema",
                ),
            ]
        )
    else:
        entries.extend(
            [
                build_mapping_entry(
                    classification="direct",
                    source_path="facilities[].anchor",
                    target_path="devices[].origin",
                    reason="facility anchors are forwarded as device origins",
                ),
                build_mapping_entry(
                    classification="direct",
                    source_path="facilities[].orientation",
                    target_path="devices[].rotation",
                    reason="canonical orientation is translated into IndustrialPlanner quarter-turn rotations",
                ),
            ]
        )

    entries.extend([
        build_mapping_entry(
            classification="derived",
            source_path="facilities[].active_ports[].commodity",
            target_path="devices[].typeId",
            reason="mapped canonical commodities are translated into upstream recipe evidence so semantically resolvable facilities can emit precise IndustrialPlanner machine families",
            target_value={
                "precise_resolution_count": int(precise_resolution_count),
            },
        ),
        build_mapping_entry(
            classification="lossy",
            source_path="facilities[].facility_type",
            target_path="devices[].typeId",
            reason="unresolved generic canonical facility templates fall back to representative IndustrialPlanner device ids with explicit warnings",
            target_value={
                "exported_facility_count": int(exported_facility_count),
                "generic_fallback_count": int(generic_fallback_count),
                "unresolved_facility_count": int(unresolved_facility_count),
            },
        ),
        build_mapping_entry(
            classification="derived",
            source_path="facilities[boundary_storage_port].active_ports[].commodity",
            target_path="devices[].config.*.itemId",
            reason="boundary port config item ids are translated into the IndustrialPlanner / upstream namespace before serialization",
            target_value={
                "commodity_translation_miss_count": int(commodity_translation_miss_count),
            },
        ),
        build_mapping_entry(
            classification="derived",
            source_path="routing_network",
            target_path="devices[]",
            reason="routing cells are flattened into target-side logistics devices",
            target_value={"exported_routing_device_count": int(exported_routing_device_count)},
        ),
        build_mapping_entry(
            classification="dropped",
            source_path="metadata.solve_time_seconds",
            reason="viewer/editor target has no certified solve-time field",
        ),
        build_mapping_entry(
            classification="dropped",
            source_path="metadata.benders_iterations",
            reason="viewer/editor target does not carry exact-proof iteration metadata",
        ),
        build_mapping_entry(
            classification="dropped",
            source_path="objective_achieved.empty_rect",
            reason="IndustrialPlanner blueprints do not model the certified empty-rectangle objective payload",
        ),
        build_mapping_entry(
            classification="derived",
            source_path="(export option)",
            target_path="baseId",
            reason="target blueprint baseId is chosen from exporter options instead of a canonical facility record",
        ),
    ])

    if exported_protocol_core_count > 0:
        entries.append(
            build_mapping_entry(
                classification="dropped",
                source_path="facilities[protocol_core]",
                reason="protocol_core instances are omitted and represented indirectly through blueprint.baseId",
                source_value={"dropped_protocol_core_count": int(exported_protocol_core_count)},
            )
        )

    if has_elevated_layer:
        entries.append(
            build_mapping_entry(
                classification="lossy",
                source_path="routing_network.L1_elevated",
                target_path="devices[]",
                reason="elevated bridge cells are collapsed into planar target devices",
            )
        )

    if used_liquid_heuristics:
        entries.append(
            build_mapping_entry(
                classification="lossy",
                source_path="routing_network.*.commodity",
                target_path="devices[].typeId",
                reason="liquid-like routing is inferred heuristically from commodity names; junction coverage is partial",
            )
        )

    return entries

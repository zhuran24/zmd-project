"""Tests for compatibility-manifest helpers."""

from __future__ import annotations

from src.interchange.compatibility_manifest import (
    build_compatibility_manifest,
    build_mapping_entry,
)
from src.interchange.target_capabilities import TargetCapabilities


def test_compatibility_manifest_buckets_entries_and_normalizes_capabilities() -> None:
    manifest = build_compatibility_manifest(
        target="industrial_planner",
        export_mode="one_way_lossy",
        source_blueprint_version="1.0.0",
        target_capabilities=TargetCapabilities(
            supports_power_overlay=True,
            supports_dual_layer_routing="partial",
            supports_active_ports=True,
        ),
        mapping_entries=[
            build_mapping_entry(classification="lossy", source_path="routing_network.L1_elevated", target_path="devices[]", reason="target bridge model differs"),
            build_mapping_entry(classification="direct", source_path="facilities[].anchor", target_path="devices[].origin"),
            build_mapping_entry(classification="dropped", source_path="metadata.benders_iterations", reason="target is viewer-facing only"),
            build_mapping_entry(classification="derived", source_path="routing_network.L0_ground", target_path="devices[].config", reason="flattened device fragments"),
        ],
        warnings=["lossy bridge flattening"],
        generated_at="2026-03-25T00:00:00Z",
    )

    assert manifest["metadata"]["target"] == "industrial_planner"
    assert manifest["metadata"]["source_blueprint_version"] == "1.0.0"
    assert manifest["target_capabilities"]["supports_power_overlay"] is True
    assert manifest["target_capabilities"]["supports_dual_layer_routing"] == "partial"
    assert len(manifest["direct_mappings"]) == 1
    assert len(manifest["lossy_mappings"]) == 1
    assert len(manifest["dropped_fields"]) == 1
    assert len(manifest["derived_mappings"]) == 1
    assert manifest["warnings"] == ["lossy bridge flattening"]

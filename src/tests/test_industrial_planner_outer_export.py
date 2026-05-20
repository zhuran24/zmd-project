"""Tests for IndustrialPlanner exporter support for outer deployment plans."""

from __future__ import annotations

from src.adapters.base_planner.outer_deployment_plan import build_outer_base_deployment_plan
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle



def _canonical_output_only_fixture() -> dict[str, object]:
    return {
        "metadata": {
            "version": "1.0.0",
            "solve_time_seconds": 0.0,
            "benders_iterations": 0,
            "export_timestamp": "2026-03-30T00:00:00Z",
        },
        "objective_achieved": {
            "empty_rect": {
                "w": 1,
                "h": 1,
                "anchor_x": 0,
                "anchor_y": 0,
                "score": 1.0,
            }
        },
        "facilities": [
            {
                "instance_id": "boundary_top",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 20, "y": 0},
                "orientation": 3,
                "port_mode": "default",
                "active_ports": [
                    {"type": "output", "x": 20, "y": 0, "dir": "N", "commodity": "blue_iron_ore"}
                ],
            },
            {
                "instance_id": "boundary_left",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 0, "y": 15},
                "orientation": 2,
                "port_mode": "default",
                "active_ports": [
                    {"type": "output", "x": 0, "y": 15, "dir": "N", "commodity": "blue_iron_ore"}
                ],
            },
            {
                "instance_id": "boundary_bottom",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 20, "y": 69},
                "orientation": 1,
                "port_mode": "default",
                "active_ports": [
                    {"type": "output", "x": 20, "y": 69, "dir": "N", "commodity": "blue_iron_ore"}
                ],
            },
            {
                "instance_id": "boundary_right",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 69, "y": 15},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [
                    {"type": "output", "x": 69, "y": 15, "dir": "N", "commodity": "blue_iron_ore"}
                ],
            },
        ],
        "routing_network": {"L0_ground": {}, "L1_elevated": {}},
    }



def test_outer_export_bundle_emits_postprocess_mapping_section_and_translated_origins() -> None:
    blueprint = _canonical_output_only_fixture()
    deployment_plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint,
        base_id="wuling_protocol_core",
    )

    bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint,
        deployment_plan=deployment_plan,
    )

    assert bundle["blueprint"]["baseId"] == "wuling_protocol_core"
    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is True

    manifest = bundle["compatibility_manifest"]
    assert manifest["metadata"]["extensions"]["has_outer_deployment_plan"] is True
    assert manifest["metadata"]["extensions"]["translated_export_mapping_count"] == 4

    postprocess_section = manifest["postprocess_export_mappings"]
    assert postprocess_section["scope"] == "postprocess_only"
    assert postprocess_section["mapping_source"] == "outer_deployment_plan"
    assert postprocess_section["base_id"] == "wuling_protocol_core"
    assert postprocess_section["inner_island_origin"] == {"x": 5, "y": 5}
    assert postprocess_section["translated_mapping_count"] == 4
    assert postprocess_section["mapping_count"] == 4

    derived_source_paths = {entry["source_path"] for entry in manifest["derived_mappings"]}
    assert "(postprocess sidecar) outer_deployment_plan.export_mappings[]" in derived_source_paths
    assert "facilities[].anchor" in derived_source_paths
    assert "facilities[].orientation" in derived_source_paths

    translated_unloaders = {
        (device["origin"]["x"], device["origin"]["y"], device["rotation"])
        for device in bundle["blueprint"]["devices"]
        if device["typeId"] == "item_port_unloader_1"
    }
    assert translated_unloaders == {
        (25, 0, 0),
        (0, 20, 270),
        (25, 79, 180),
        (79, 20, 90),
    }

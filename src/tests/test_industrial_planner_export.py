"""Tests for the IndustrialPlanner export bundle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.industrial_planner.export_blueprint import (
    INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME,
    INDUSTRIAL_PLANNER_MANIFEST_FILENAME,
    INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME,
    INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME,
    INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME,
    INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME,
    build_industrial_planner_export_bundle,
    write_industrial_planner_export_bundle,
)
from src.io.delivery_manifest import build_compatibility_exports_payload
from src.io.output_schema import blueprint_output_path
from src.io.serializer import write_blueprint_payload
from src.render.blueprint_exporter import export_target_blueprint

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"


def _sample_blueprint_payload() -> dict[str, object]:
    return {
        "metadata": {
            "version": "1.0.0",
            "solve_time_seconds": 12.5,
            "benders_iterations": 4,
            "export_timestamp": "2026-03-25T00:00:00Z",
        },
        "objective_achieved": {
            "empty_rect": {
                "w": 6,
                "h": 5,
                "anchor_x": 12,
                "anchor_y": 9,
                "score": 30.0,
            }
        },
        "facilities": [
            {
                "instance_id": "core_001",
                "facility_type": "protocol_core",
                "anchor": {"x": 8, "y": 8},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [],
            },
            {
                "instance_id": "storage_001",
                "facility_type": "protocol_storage_box",
                "anchor": {"x": 2, "y": 3},
                "orientation": 1,
                "port_mode": "default",
                "active_ports": [],
            },
            {
                "instance_id": "pole_001",
                "facility_type": "power_pole",
                "anchor": {"x": 6, "y": 3},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [],
            },
            {
                "instance_id": "port_001",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 0, "y": 0},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [
                    {
                        "type": "output",
                        "x": 0,
                        "y": 0,
                        "dir": "N",
                        "commodity": "blue_iron_ore",
                    }
                ],
            },
            {
                "instance_id": "mfg_001",
                "facility_type": "manufacturing_3x3",
                "anchor": {"x": 10, "y": 4},
                "orientation": 2,
                "port_mode": "left_right",
                "active_ports": [],
            },
        ],
        "routing_network": {
            "L0_ground": {
                "1,0": {
                    "type": "belt",
                    "commodity": "iron_plate",
                    "flow_in": ["W"],
                    "flow_out": ["E"],
                },
                "2,0": {
                    "type": "belt",
                    "commodity": "iron_plate",
                    "flow_in": ["W"],
                    "flow_out": ["S"],
                },
                "3,0": {
                    "type": "splitter",
                    "commodity": "iron_plate",
                    "flow_in": ["W"],
                    "flow_out": ["E", "S"],
                },
                "4,0": {
                    "type": "belt",
                    "commodity": "item_liquid_water",
                    "flow_in": ["W"],
                    "flow_out": ["E"],
                },
            },
            "L1_elevated": {
                "5,0": {
                    "type": "bridge",
                    "commodity": "iron_plate",
                    "flow_in": ["W"],
                    "flow_out": ["E"],
                }
            },
        },
    }


def _all_edge_boundary_output_fixture(*, lot_size: int, inside_facing_bus: bool) -> dict[str, object]:
    top_orientation = 3 if inside_facing_bus else 1
    left_orientation = 2 if inside_facing_bus else 0
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
                "orientation": top_orientation,
                "port_mode": "default",
                "active_ports": [
                    {"type": "output", "x": 20, "y": 0, "dir": "N", "commodity": "blue_iron_ore"}
                ],
            },
            {
                "instance_id": "boundary_left",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 0, "y": 15},
                "orientation": left_orientation,
                "port_mode": "default",
                "active_ports": [
                    {"type": "output", "x": 0, "y": 15, "dir": "N", "commodity": "blue_iron_ore"}
                ],
            },
            {
                "instance_id": "boundary_bottom",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 20, "y": lot_size - 1},
                "orientation": 1,
                "port_mode": "default",
                "active_ports": [
                    {
                        "type": "output",
                        "x": 20,
                        "y": lot_size - 1,
                        "dir": "N",
                        "commodity": "blue_iron_ore",
                    }
                ],
            },
            {
                "instance_id": "boundary_right",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": lot_size - 1, "y": 15},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [
                    {
                        "type": "output",
                        "x": lot_size - 1,
                        "y": 15,
                        "dir": "N",
                        "commodity": "blue_iron_ore",
                    }
                ],
            },
        ],
        "routing_network": {"L0_ground": {}, "L1_elevated": {}},
    }


def test_build_industrial_planner_export_bundle_shapes_target_payload_and_validation_sidecars() -> None:
    bundle = build_industrial_planner_export_bundle(blueprint_payload=_sample_blueprint_payload())

    target_blueprint = bundle["blueprint"]
    manifest = bundle["compatibility_manifest"]
    validation_report = bundle["validation_report"]
    type_ids = [device["typeId"] for device in target_blueprint["devices"]]

    assert target_blueprint["schema"] == "industrial-planner-blueprint"
    assert target_blueprint["version"] == "1.0"
    assert target_blueprint["blueprintVersion"] == "1"
    assert target_blueprint["baseId"] == "valley4_protocol_core"
    assert target_blueprint["createdAt"] == "2026-03-25T00:00:00Z"
    assert "item_port_unloader_1" in type_ids
    assert "item_port_storager_1" in type_ids
    assert "item_port_power_diffuser_1" in type_ids
    assert "belt_straight_1x1" in type_ids
    assert "belt_turn_ccw_1x1" in type_ids
    assert "item_log_splitter" in type_ids
    assert "pipe_straight_1x1" in type_ids
    assert all(device["typeId"] != "protocol_core" for device in target_blueprint["devices"])
    port_device = next(device for device in target_blueprint["devices"] if device["typeId"] == "item_port_unloader_1")
    assert port_device["config"]["pickupItemId"] == "item_iron_ore"

    assert manifest["metadata"]["target"] == "industrial_planner"
    assert manifest["metadata"]["source_blueprint_version"] == "1.0.0"
    assert manifest["metadata"]["generated_at"] == "2026-03-25T00:00:00Z"
    assert any(entry["source_path"] == "objective_achieved.empty_rect" for entry in manifest["dropped_fields"])
    assert any(entry["source_path"] == "routing_network.L1_elevated" for entry in manifest["lossy_mappings"])
    assert manifest["metadata"]["extensions"]["validation_is_import_compatible"] is True
    assert manifest["metadata"]["extensions"]["validation_is_layout_healthy"] is False
    assert validation_report["is_import_compatible"] is True
    assert validation_report["is_layout_healthy"] is False
    assert "# IndustrialPlanner Validation Report" in bundle["validation_report_markdown"]
    assert "throughput_report" in bundle
    assert "validation_diagnostics" in bundle["throughput_report"]
    assert "clean" not in bundle["throughput_report"]
    assert "# IndustrialPlanner Throughput Audit Report" in bundle["throughput_report_markdown"]
    assert any("protocol_core" in warning for warning in bundle["warnings"])


def test_precision_fixture_emits_loader_admission_binding_auxiliary_devices() -> None:
    blueprint_payload = json.loads((_FIXTURE_DIR / "precision_export_canonical_blueprint.json").read_text(encoding="utf-8"))

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint_payload)
    admission_devices = [
        device
        for device in bundle["blueprint"]["devices"]
        if device["typeId"] == "item_log_admission"
    ]

    assert len(admission_devices) == 1
    assert admission_devices[0]["rotation"] == 180
    assert admission_devices[0]["origin"] == {"x": 1, "y": 16}
    assert admission_devices[0]["config"]["admissionItemId"] == "item_iron_ore"
    assert bundle["compatibility_manifest"]["metadata"]["extensions"]["exported_auxiliary_device_count"] == 1




def test_full_demand_fixture_emits_grouped_boundary_bus_witness_auxiliary_devices() -> None:
    blueprint_payload = json.loads((_FIXTURE_DIR / "full_demand_recipe_capacity_canonical_blueprint.json").read_text(encoding="utf-8"))

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint_payload)
    bus_devices = [
        device
        for device in bundle["blueprint"]["devices"]
        if device["typeId"] == "item_port_log_hongs_bus"
    ]

    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is True
    assert len(bus_devices) == 4
    assert {(device["origin"]["x"], device["origin"]["y"], device["rotation"]) for device in bus_devices} == {
        (33, 65, 90),
        (45, 65, 90),
        (57, 65, 90),
        (61, 43, 90),
    }
    assert bundle["compatibility_manifest"]["metadata"]["extensions"]["exported_auxiliary_device_count"] == 6


@pytest.mark.parametrize(
    ("base_id", "lot_size", "expected_bus_origins"),
    (
        (
            "valley4_infra_outpost",
            40,
            {(1, 10, 0), (19, 1, 0), (19, 31, 0), (35, 10, 0)},
        ),
        (
            "wuling_tianwangping_aid",
            50,
            {(1, 10, 0), (19, 1, 0), (19, 41, 0), (45, 10, 0)},
        ),
    ),
)
def test_all_edge_boundary_outputs_gain_clean_bus_witnesses_on_multiple_bases(
    base_id: str,
    lot_size: int,
    expected_bus_origins: set[tuple[int, int, int]],
) -> None:
    blueprint_payload = _all_edge_boundary_output_fixture(lot_size=lot_size, inside_facing_bus=True)

    bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint_payload,
        base_id=base_id,
    )
    bus_devices = {
        (device["origin"]["x"], device["origin"]["y"], device["rotation"])
        for device in bundle["blueprint"]["devices"]
        if device["typeId"] == "item_port_log_hongs_bus"
    }

    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is True
    assert bus_devices == expected_bus_origins
    assert bundle["warnings"] == []


def test_unfixable_outside_bus_requirements_are_reported_explicitly() -> None:
    blueprint_payload = _all_edge_boundary_output_fixture(lot_size=50, inside_facing_bus=False)

    bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint_payload,
        base_id="wuling_tianwangping_aid",
    )

    assert bundle["validation_report"]["is_import_compatible"] is False
    assert any(
        "outside base 'wuling_tianwangping_aid'" in warning
        for warning in bundle["warnings"]
    )

def test_write_industrial_planner_bundle_and_delivery_manifest_scan(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    canonical_blueprint = _sample_blueprint_payload()
    write_blueprint_payload(blueprint_output_path(project_root), canonical_blueprint)
    written = write_industrial_planner_export_bundle(
        output_dir=project_root / "data" / "exports" / "industrial_planner",
        blueprint_payload=canonical_blueprint,
    )
    exports_payload = build_compatibility_exports_payload(project_root)

    assert written.blueprint_path.name == INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME
    assert written.compatibility_manifest_path.name == INDUSTRIAL_PLANNER_MANIFEST_FILENAME
    assert written.validation_report_path.name == INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME
    assert written.validation_report_markdown_path.name == INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME
    assert written.throughput_report_path.name == INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME
    assert written.throughput_report_markdown_path.name == INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME
    assert written.blueprint_path.exists()
    assert written.compatibility_manifest_path.exists()
    assert written.validation_report_path.exists()
    assert written.validation_report_markdown_path.exists()
    assert written.throughput_report_path.exists()
    assert written.throughput_report_markdown_path.exists()
    assert exports_payload["industrial_planner"]["blueprint"]["exists"] is True
    assert exports_payload["industrial_planner"]["compatibility_manifest"]["exists"] is True
    assert exports_payload["industrial_planner"]["validation_report"]["exists"] is True
    assert exports_payload["industrial_planner"]["validation_report_markdown"]["exists"] is True
    assert exports_payload["industrial_planner"]["throughput_report"]["exists"] is True
    assert exports_payload["industrial_planner"]["throughput_report_markdown"]["exists"] is True


def test_render_blueprint_export_wrapper_writes_target_bundle(tmp_path: Path) -> None:
    result = export_target_blueprint(
        blueprint_payload=_sample_blueprint_payload(),
        target="industrial_planner",
        output_dir=tmp_path / "exports" / "industrial_planner",
    )

    assert Path(result["blueprint_path"]).exists()
    assert Path(result["compatibility_manifest_path"]).exists()
    assert Path(result["validation_report_path"]).exists()
    assert Path(result["validation_report_markdown_path"]).exists()
    assert Path(result["throughput_report_path"]).exists()
    assert Path(result["throughput_report_markdown_path"]).exists()
    assert json.loads(Path(result["blueprint_path"]).read_text(encoding="utf-8"))["schema"] == "industrial-planner-blueprint"


def test_old_minimal_example_is_no_longer_the_success_oracle() -> None:
    blueprint_payload = json.loads((_FIXTURE_DIR / "minimal_canonical_blueprint.json").read_text(encoding="utf-8"))

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint_payload)

    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is False
    assert bundle["validation_report"]["overlap_errors"]

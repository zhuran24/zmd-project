"""Tests for IndustrialPlanner mapping helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.adapters.industrial_planner.mapping_registry import (
    direction_to_rotation,
    orientation_to_rotation,
    resolve_facility_device,
    resolve_routing_device,
)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"


def test_orientation_and_direction_rotation_helpers_cover_quarter_turns() -> None:
    assert orientation_to_rotation(0) == 0
    assert orientation_to_rotation(1) == 90
    assert orientation_to_rotation(2) == 180
    assert orientation_to_rotation(3) == 270
    assert orientation_to_rotation(0, degrees_offset=90) == 90

    assert direction_to_rotation("E") == 0
    assert direction_to_rotation("S") == 90
    assert direction_to_rotation("W") == 180
    assert direction_to_rotation("N") == 270


def test_boundary_storage_port_output_maps_to_unloader_config_and_translates_items() -> None:
    fixture = json.loads((_FIXTURE_DIR / "boundary_port_translation_fixture.json").read_text(encoding="utf-8"))
    boundary_out = next(entry for entry in fixture["facilities"] if entry["instance_id"] == "boundary_out")

    resolved = resolve_facility_device(boundary_out)

    assert resolved.target_type_id == "item_port_unloader_1"
    assert resolved.rotation == 90
    assert resolved.config["pickupItemId"] == "item_iron_ore"
    assert resolved.config["protocolHubOutputs"][0]["itemId"] == "item_iron_ore"


def test_protocol_core_is_dropped_in_favor_of_base_id() -> None:
    resolved = resolve_facility_device(
        {
            "instance_id": "core_001",
            "facility_type": "protocol_core",
            "anchor": {"x": 10, "y": 10},
            "orientation": 0,
            "active_ports": [],
        }
    )

    assert resolved.target_type_id is None
    assert resolved.classification == "dropped"
    assert "baseId" in resolved.reason or "baseId" in " ".join(resolved.warnings)


def test_precise_resolution_uses_semantic_recipe_evidence() -> None:
    fixture = json.loads((_FIXTURE_DIR / "precision_export_canonical_blueprint.json").read_text(encoding="utf-8"))
    crusher = next(entry for entry in fixture["facilities"] if entry["instance_id"] == "mfg_crusher_blue_iron")
    unresolved = next(entry for entry in fixture["facilities"] if entry["instance_id"] == "mfg_unresolved")

    crusher_resolved = resolve_facility_device(crusher)
    unresolved_resolved = resolve_facility_device(unresolved)

    assert crusher_resolved.target_type_id == "item_port_grinder_1"
    assert crusher_resolved.resolution_mode == "precise"
    assert crusher_resolved.resolved_recipe_id == "crusher_blue_iron"

    assert unresolved_resolved.target_type_id == "item_port_grinder_1"
    assert unresolved_resolved.resolution_mode == "fallback"
    assert any("precise resolution fallback" in warning for warning in unresolved_resolved.warnings)


def test_boundary_storage_port_direction_rules_cover_loader_and_storage_fallback() -> None:
    fixture = json.loads((_FIXTURE_DIR / "boundary_port_translation_fixture.json").read_text(encoding="utf-8"))
    boundary_in = next(entry for entry in fixture["facilities"] if entry["instance_id"] == "boundary_in")
    boundary_mixed = next(entry for entry in fixture["facilities"] if entry["instance_id"] == "boundary_mixed")

    loader = resolve_facility_device(boundary_in)
    storage = resolve_facility_device(boundary_mixed)

    assert loader.target_type_id == "item_port_loader_1"
    assert loader.config == {}
    assert len(loader.auxiliary_devices) == 1
    assert loader.auxiliary_devices[0] == {
        "typeId": "item_log_admission",
        "rotation": 180,
        "origin": {"x": 1, "y": 16},
        "config": {"admissionItemId": "item_iron_ore"},
    }
    assert storage.target_type_id == "item_port_storager_1"
    assert storage.resolution_mode == "fallback"
    assert any("fell back to storage" in warning for warning in storage.warnings)


def test_routing_corner_prefers_turn_device_and_elevated_bridge_is_lossy() -> None:
    turn = resolve_routing_device(
        x=3,
        y=4,
        layer_name="L0_ground",
        cell={
            "type": "belt",
            "commodity": "iron_plate",
            "flow_in": ["W"],
            "flow_out": ["S"],
        },
    )
    elevated = resolve_routing_device(
        x=4,
        y=4,
        layer_name="L1_elevated",
        cell={
            "type": "bridge",
            "commodity": "iron_plate",
            "flow_in": ["W"],
            "flow_out": ["E"],
        },
    )

    assert turn.target_type_id == "belt_turn_ccw_1x1"
    assert turn.rotation == 270
    assert elevated.target_type_id == "belt_straight_1x1"
    assert elevated.classification == "lossy"
    assert any("bridge" in warning or "elevated" in warning for warning in elevated.warnings)

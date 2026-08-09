"""Tests for Spec 22 precision export behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.endfield_calc.semantic_mapping import current_repository_semantic_registry
from src.adapters.industrial_planner.commodity_resolver import valid_upstream_item_ids
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle
from src.adapters.industrial_planner.mapping_registry import resolve_facility_device

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"


def _load_json(name: str) -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _boundary_output_blueprint(output_commodity: str) -> dict[str, object]:
    return {
        "metadata": {
            "version": "1.0.0",
            "solve_time_seconds": 1.25,
            "benders_iterations": 1,
            "export_timestamp": "2026-03-28T00:00:00Z",
        },
        "objective_achieved": {
            "empty_rect": {
                "w": 3,
                "h": 3,
                "anchor_x": 0,
                "anchor_y": 20,
                "score": 9.0,
            }
        },
        "facilities": [
            {
                "instance_id": "boundary_out",
                "facility_type": "boundary_storage_port",
                "anchor": {"x": 0, "y": 20},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [
                    {
                        "type": "output",
                        "x": 0,
                        "y": 0,
                        "dir": "N",
                        "commodity": output_commodity,
                    }
                ],
            }
        ],
        "routing_network": {
            "L0_ground": {},
            "L1_elevated": {},
        },
    }


def _registry_only_upstream_item_id() -> str:
    semantic_upstream_ids = {
        mapping.upstream_id for mapping in current_repository_semantic_registry().item_mappings
    }
    registry_only = sorted(valid_upstream_item_ids() - semantic_upstream_ids)
    assert registry_only, "expected at least one registry-only upstream item id for passthrough coverage"
    return registry_only[0]


def _manufacturing_output_blueprint(output_commodity: str) -> dict[str, object]:
    return {
        "metadata": {
            "version": "1.0.0",
            "solve_time_seconds": 1.25,
            "benders_iterations": 1,
            "export_timestamp": "2026-03-28T00:00:00Z",
        },
        "objective_achieved": {
            "empty_rect": {
                "w": 3,
                "h": 3,
                "anchor_x": 0,
                "anchor_y": 0,
                "score": 9.0,
            }
        },
        "facilities": [
            {
                "instance_id": "mfg_out",
                "facility_type": "manufacturing_3x3",
                "anchor": {"x": 0, "y": 0},
                "orientation": 0,
                "port_mode": "default",
                "active_ports": [
                    {
                        "type": "output",
                        "x": 1,
                        "y": 0,
                        "dir": "N",
                        "commodity": output_commodity,
                    }
                ],
            }
        ],
        "routing_network": {
            "L0_ground": {},
            "L1_elevated": {},
        },
    }


def test_precision_export_fixture_resolves_expected_machine_types() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")
    expected = _load_json("precision_export_expected_resolution.json")

    actual = {}
    for facility in blueprint["facilities"]:
        resolved = resolve_facility_device(facility)
        actual[facility["instance_id"]] = {
            "typeId": resolved.target_type_id,
            "resolution_mode": resolved.resolution_mode,
        }

    assert actual == expected


def test_precision_export_bundle_marks_clean_export_and_tracks_resolution_counts() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    extensions = bundle["compatibility_manifest"]["metadata"]["extensions"]

    assert extensions["precise_resolution_count"] == 9
    assert extensions["generic_fallback_count"] == 1
    assert extensions["unresolved_facility_count"] == 1
    assert extensions["commodity_translation_miss_count"] == 0
    assert extensions["has_commodity_translation_miss"] is False
    assert extensions["validation_is_import_compatible"] is True
    assert extensions["validation_is_layout_healthy"] is True
    assert extensions["clean_export"] is True
    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is True
    assert bundle["validation_report"]["port_warnings"]
    assert bundle["throughput_report"]["summary"]["exact_match_recipe_count"] == 17
    assert "clean" not in bundle["throughput_report"]


def test_precision_export_fallbacks_are_not_silent() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)

    assert any("precise resolution fallback" in warning for warning in bundle["warnings"])


def test_all_serialized_export_config_item_ids_use_upstream_namespace() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)

    item_ids: list[str] = []
    for device in bundle["blueprint"]["devices"]:
        config = device.get("config") or {}
        if "pickupItemId" in config:
            item_ids.append(str(config["pickupItemId"]))
        if "admissionItemId" in config:
            item_ids.append(str(config["admissionItemId"]))
        for entry in config.get("protocolHubOutputs", []):
            if isinstance(entry, dict) and entry.get("itemId") is not None:
                item_ids.append(str(entry["itemId"]))

    assert item_ids
    assert all(item_id.startswith("item_") for item_id in item_ids)
    assert "blue_iron_ore" not in item_ids


def test_invalid_upstream_like_item_is_not_serialized_into_export_payload() -> None:
    blueprint = _boundary_output_blueprint("item_not_real_but_prefixed")

    resolved = resolve_facility_device(blueprint["facilities"][0])
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    exported_unloader = next(
        device for device in bundle["blueprint"]["devices"] if device["typeId"] == "item_port_unloader_1"
    )
    exported_config = exported_unloader.get("config") or {}
    warnings = tuple(bundle["warnings"])
    serialized_blueprint = json.dumps(bundle["blueprint"], ensure_ascii=False, sort_keys=True)
    extensions = bundle["compatibility_manifest"]["metadata"]["extensions"]

    assert resolved.translation_miss_count == 1
    assert "pickupItemId" not in exported_config
    assert "protocolHubOutputs" not in exported_config
    assert extensions["commodity_translation_miss_count"] == 1
    assert extensions["has_commodity_translation_miss"] is True
    assert any("item_not_real_but_prefixed" in warning for warning in warnings)
    assert all("translation miss" not in warning.lower() for warning in warnings)
    assert "item_not_real_but_prefixed" not in serialized_blueprint


def test_registry_backed_upstream_passthrough_remains_allowed_without_miss() -> None:
    passthrough_item_id = _registry_only_upstream_item_id()
    blueprint = _boundary_output_blueprint(passthrough_item_id)

    resolved = resolve_facility_device(blueprint["facilities"][0])
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    exported_unloader = next(
        device for device in bundle["blueprint"]["devices"] if device["typeId"] == "item_port_unloader_1"
    )
    exported_config = exported_unloader.get("config") or {}
    extensions = bundle["compatibility_manifest"]["metadata"]["extensions"]

    assert resolved.translation_miss_count == 0
    assert exported_config["pickupItemId"] == passthrough_item_id
    assert exported_config["protocolHubOutputs"][0]["itemId"] == passthrough_item_id
    assert extensions["commodity_translation_miss_count"] == 0
    assert extensions["has_commodity_translation_miss"] is False
    assert not any("invalid upstream-like" in warning.lower() for warning in bundle["warnings"])


def test_manifest_translation_miss_count_comes_from_structured_audits_not_warning_keywords() -> None:
    blueprint = _boundary_output_blueprint("item_not_real_but_prefixed")

    resolved = resolve_facility_device(blueprint["facilities"][0])
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    extensions = bundle["compatibility_manifest"]["metadata"]["extensions"]

    assert resolved.translation_miss_count == 1
    assert extensions["commodity_translation_miss_count"] == resolved.translation_miss_count
    assert all("translation miss" not in warning.lower() for warning in bundle["warnings"])


@pytest.mark.parametrize(
    ("output_commodity", "warning_fragment"),
    [
        ("[TBD]", "placeholder commodity [TBD] cannot be translated"),
        ("", "empty commodity id cannot be translated"),
    ],
)
def test_boundary_output_placeholder_or_empty_commodities_count_as_translation_miss(
    output_commodity: str,
    warning_fragment: str,
) -> None:
    blueprint = _boundary_output_blueprint(output_commodity)

    resolved = resolve_facility_device(blueprint["facilities"][0])
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    exported_unloader = next(
        device for device in bundle["blueprint"]["devices"] if device["typeId"] == "item_port_unloader_1"
    )
    exported_config = exported_unloader.get("config") or {}
    extensions = bundle["compatibility_manifest"]["metadata"]["extensions"]

    assert resolved.translation_miss_count == 1
    assert "pickupItemId" not in exported_config
    assert "protocolHubOutputs" not in exported_config
    assert extensions["commodity_translation_miss_count"] == 1
    assert extensions["has_commodity_translation_miss"] is True
    assert any(warning_fragment in warning for warning in bundle["warnings"])


@pytest.mark.parametrize(
    ("output_commodity", "warning_fragment"),
    [
        ("[TBD]", "placeholder commodity [TBD] cannot be translated"),
        ("", "empty commodity id cannot be translated"),
    ],
)
def test_precise_resolution_placeholder_or_empty_outputs_are_counted_as_translation_misses(
    output_commodity: str,
    warning_fragment: str,
) -> None:
    blueprint = _manufacturing_output_blueprint(output_commodity)

    resolved = resolve_facility_device(blueprint["facilities"][0])
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    extensions = bundle["compatibility_manifest"]["metadata"]["extensions"]

    assert resolved.resolution_mode == "fallback"
    assert resolved.translation_miss_count == 1
    assert extensions["commodity_translation_miss_count"] == 1
    assert extensions["has_commodity_translation_miss"] is True
    assert any(warning_fragment in warning for warning in bundle["warnings"])

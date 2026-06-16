"""Tests for manifest-driven throughput audit on translated outer exports."""

from __future__ import annotations

import json
from pathlib import Path

from src.adapters.base_planner.outer_deployment_plan import build_outer_base_deployment_plan
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle
from src.adapters.industrial_planner.throughput_audit import build_industrial_planner_throughput_audit

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"



def _load_full_demand_blueprint() -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / "full_demand_recipe_capacity_canonical_blueprint.json").read_text(encoding="utf-8"))



def test_manifest_mapping_restores_translated_full_demand_throughput_evidence() -> None:
    blueprint = _load_full_demand_blueprint()
    deployment_plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint,
        base_id="wuling_protocol_core",
    )

    mapped_bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint,
        deployment_plan=deployment_plan,
    )
    mapped_report = mapped_bundle["throughput_report"]
    unmapped_report = build_industrial_planner_throughput_audit(
        blueprint_payload=blueprint,
        export_blueprint=mapped_bundle["blueprint"],
        compatibility_manifest=None,
        validation_report=mapped_bundle["validation_report"],
        base_id="wuling_protocol_core",
    ).to_dict()

    assert mapped_bundle["validation_report"]["is_import_compatible"] is True
    assert mapped_bundle["validation_report"]["is_layout_healthy"] is True
    assert mapped_report["status"] == "proven_equivalent"
    assert mapped_report["summary"]["proven_recipe_count"] == 17
    assert mapped_report["summary"]["insufficient_recipe_count"] == 0
    assert mapped_report["summary"]["proven_boundary_commodity_count"] == 4
    assert mapped_report["summary"]["validator_import_compatible"] is True
    assert mapped_report["summary"]["validator_layout_healthy"] is True

    assert unmapped_report["summary"]["proven_recipe_count"] == 0
    assert unmapped_report["summary"]["insufficient_recipe_count"] == 17
    assert unmapped_report["summary"]["proven_boundary_commodity_count"] == 0

    mapped_boundary_rollups = {
        (entry["commodity_id"], entry["direction"]): entry
        for entry in mapped_report["boundary_io_rollups"]
    }
    unmapped_boundary_rollups = {
        (entry["commodity_id"], entry["direction"]): entry
        for entry in unmapped_report["boundary_io_rollups"]
    }
    assert mapped_boundary_rollups[("blue_iron_ore", "required_output")]["proven_slots"] == 34
    assert mapped_boundary_rollups[("source_ore", "required_output")]["proven_slots"] == 18
    assert mapped_boundary_rollups[("qiaoyu_capsule", "required_input")]["proven_slots"] == 1
    assert mapped_boundary_rollups[("valley_battery", "required_input")]["proven_slots"] == 1
    assert unmapped_boundary_rollups[("blue_iron_ore", "required_output")]["proven_slots"] == 0
    assert unmapped_boundary_rollups[("qiaoyu_capsule", "required_input")]["proven_slots"] == 0

    assert sum(1 for entry in mapped_report["facility_evidence"] if entry["counts_toward_capacity"]) == 219
    assert sum(1 for entry in unmapped_report["facility_evidence"] if entry["counts_toward_capacity"]) == 0

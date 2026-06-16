"""Tests for the IndustrialPlanner static recipe/capacity audit."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle
from src.adapters.industrial_planner.recipe_matcher import (
    build_recipe_match_index,
    load_item_registry_payload,
)
from src.adapters.industrial_planner.throughput_audit import (
    BoundaryIORollup,
    FacilityCapacityEvidence,
    RecipeCapacityRollup,
    ValidationDiagnostics,
    _derive_overall_status,
    recover_facility_recipe_intent,
)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"


def _load_json(name: str) -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_all_current_canonical_recipes_exact_match_unique_target_recipes() -> None:
    match_index = build_recipe_match_index()

    assert len(match_index) == 17
    assert all(entry.status == "exact_match" for entry in match_index.values())
    assert len({entry.matched_target_recipe_id for entry in match_index.values()}) == 17
    assert all(entry.expected_machine_type for entry in match_index.values())
    assert not any(entry.status == "ambiguous" for entry in match_index.values())


def test_precision_fixture_counts_precise_facilities_and_excludes_unresolved_capacity() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    throughput = bundle["throughput_report"]
    evidence_by_id = {
        entry["instance_id"]: entry
        for entry in throughput["facility_evidence"]
    }

    assert evidence_by_id["mfg_crusher_blue_iron"]["counts_toward_capacity"] is True
    assert evidence_by_id["mfg_crusher_blue_iron"]["proof_status"] == "proven"
    assert evidence_by_id["mfg_unresolved"]["counts_toward_capacity"] is False
    assert evidence_by_id["mfg_unresolved"]["proof_status"] in {"partial", "unproven"}
    assert throughput["recipe_rollups"]
    assert any("static recipe/capacity conformance only" in entry.lower() for entry in throughput["limitations"])


def test_mixed_boundary_storage_does_not_count_toward_proven_slots() -> None:
    blueprint = _load_json("boundary_port_translation_fixture.json")
    blueprint["facilities"] = [
        entry
        for entry in blueprint["facilities"]
        if entry["instance_id"] == "boundary_mixed"
    ]

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    rollup_by_key = {
        (entry["commodity_id"], entry["direction"]): entry
        for entry in bundle["throughput_report"]["boundary_io_rollups"]
    }
    blue_iron_output = rollup_by_key[("blue_iron_ore", "required_output")]

    assert blue_iron_output["proven_slots"] == 0
    assert blue_iron_output["status"] == "partially_proven"
    assert any("mixed boundary_storage_port" in warning for warning in blue_iron_output["warnings"])


def test_cycle_and_io_mismatches_downgrade_recipe_match_status() -> None:
    base_registry = load_item_registry_payload()
    exact_match_index = build_recipe_match_index(item_registry_payload=base_registry)
    crusher_target_recipe_id = exact_match_index["crusher_blue_iron"].matched_target_recipe_id
    assert crusher_target_recipe_id

    patched_cycle_registry = copy.deepcopy(base_registry)
    for recipe in patched_cycle_registry["recipes"]:
        if recipe.get("id") == crusher_target_recipe_id:
            recipe["cycleSeconds"] = 999
            break
    cycle_match_index = build_recipe_match_index(item_registry_payload=patched_cycle_registry)
    assert cycle_match_index["crusher_blue_iron"].status == "cycle_mismatch"

    patched_io_registry = copy.deepcopy(base_registry)
    for recipe in patched_io_registry["recipes"]:
        if recipe.get("id") == crusher_target_recipe_id:
            recipe["outputs"] = [{"itemId": "item_iron_powder", "amount": 2}]
            break
    io_match_index = build_recipe_match_index(item_registry_payload=patched_io_registry)
    assert io_match_index["crusher_blue_iron"].status == "io_mismatch"


def test_throughput_report_exposes_validation_diagnostics_without_new_clean_field() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    throughput = bundle["throughput_report"]

    assert "validation_diagnostics" in throughput
    assert "clean" not in throughput
    assert "is_clean" not in throughput["validation_diagnostics"]
    assert bundle["compatibility_manifest"]["metadata"]["extensions"]["clean_export"] is True


def test_missing_mandatory_exact_entry_falls_back_to_resolved_recipe_id() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")
    crusher = next(entry for entry in blueprint["facilities"] if entry["instance_id"] == "mfg_crusher_blue_iron")

    recipe_id, recovery_source, warnings = recover_facility_recipe_intent(crusher, {})

    assert recipe_id == "crusher_blue_iron"
    assert recovery_source == "resolved_recipe_id"
    assert warnings == ()




def test_partial_boundary_rollups_reduce_overall_status_to_partially_proven() -> None:
    status = _derive_overall_status(
        recipe_rollups=(
            RecipeCapacityRollup(
                canonical_recipe_id="crusher_blue_iron",
                required_fractional_runs="34",
                proven_exported_capacity_units=34,
                expected_machine_type="item_port_grinder_1",
                exact_target_recipe_id="r_crusher_iron_powder_from_iron_nugget_basic",
                status="proven_equivalent",
            ),
        ),
        boundary_io_rollups=(
            BoundaryIORollup(
                commodity_id="blue_iron_ore",
                direction="required_output",
                required_slots=34,
                required_flow_per_tick="34",
                proven_slots=34,
                status="proven_equivalent",
            ),
            BoundaryIORollup(
                commodity_id="source_ore",
                direction="required_output",
                required_slots=18,
                required_flow_per_tick="18",
                proven_slots=4,
                status="partially_proven",
                warnings=("explicit proven boundary slots 4 are below required slots 18; remaining item-specific throughput is not proven",),
            ),
        ),
        facility_evidence=(
            FacilityCapacityEvidence(
                instance_id="crusher_blue_iron_001",
                facility_type="manufacturing_3x3",
                inferred_canonical_recipe_id="crusher_blue_iron",
                recovery_source="resolved_recipe_id",
                resolution_mode="precise",
                exported_type_id="item_port_grinder_1",
                target_recipe_match_status="exact_match",
                counts_toward_capacity=True,
                proof_status="proven",
            ),
        ),
        validation_diagnostics=ValidationDiagnostics(
            is_import_compatible=True,
            is_layout_healthy=True,
            summary_warnings=(),
        ),
    )

    assert status == "partially_proven"


def test_full_demand_fixture_reaches_proven_equivalent_with_full_boundary_cover() -> None:
    blueprint = _load_json("full_demand_recipe_capacity_canonical_blueprint.json")
    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    throughput = bundle["throughput_report"]

    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is True
    assert throughput["status"] == "proven_equivalent"
    assert throughput["summary"]["proven_recipe_count"] == 17
    assert throughput["summary"]["insufficient_recipe_count"] == 0
    assert throughput["summary"]["proven_boundary_commodity_count"] == 4
    assert throughput["summary"]["partial_boundary_commodity_count"] == 0
    assert throughput["summary"]["insufficient_boundary_commodity_count"] == 0

    boundary_rollups = {
        (entry["commodity_id"], entry["direction"]): entry
        for entry in throughput["boundary_io_rollups"]
    }
    assert boundary_rollups[("blue_iron_ore", "required_output")]["status"] == "proven_equivalent"
    assert boundary_rollups[("blue_iron_ore", "required_output")]["proven_slots"] == 34
    assert boundary_rollups[("source_ore", "required_output")]["status"] == "proven_equivalent"
    assert boundary_rollups[("source_ore", "required_output")]["proven_slots"] == 18
    assert boundary_rollups[("qiaoyu_capsule", "required_input")]["status"] == "proven_equivalent"
    assert boundary_rollups[("qiaoyu_capsule", "required_input")]["proven_slots"] == 1
    assert boundary_rollups[("valley_battery", "required_input")]["status"] == "proven_equivalent"
    assert boundary_rollups[("valley_battery", "required_input")]["proven_slots"] == 1
    assert all(entry["status"] == "proven_equivalent" for entry in throughput["recipe_rollups"])

def test_fractional_required_runs_accept_integer_capacity_lower_bound() -> None:
    blueprint = _load_json("precision_export_canonical_blueprint.json")
    base_facility = next(entry for entry in blueprint["facilities"] if entry["instance_id"] == "mfg_filling_capsule")
    for index in range(2, 4):
        clone = copy.deepcopy(base_facility)
        clone["instance_id"] = f"mfg_filling_capsule_{index}"
        x_offset = index * 7
        clone["anchor"]["x"] += x_offset
        for port in clone["active_ports"]:
            port["x"] += x_offset
        blueprint["facilities"].append(clone)

    bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint)
    rollup_by_recipe = {
        entry["canonical_recipe_id"]: entry
        for entry in bundle["throughput_report"]["recipe_rollups"]
    }
    filling_capsule = rollup_by_recipe["filling_capsule"]

    assert filling_capsule["required_fractional_runs"] == "11/4"
    assert filling_capsule["proven_exported_capacity_units"] == 3
    assert filling_capsule["status"] == "proven_equivalent"


def test_layout_unhealthy_caps_overall_status_at_partially_proven() -> None:
    status = _derive_overall_status(
        recipe_rollups=(
            RecipeCapacityRollup(
                canonical_recipe_id="crusher_blue_iron",
                required_fractional_runs="1",
                proven_exported_capacity_units=1,
                expected_machine_type="item_port_grinder_1",
                exact_target_recipe_id="r_crusher_iron_powder_from_iron_nugget_basic",
                status="proven_equivalent",
            ),
        ),
        boundary_io_rollups=(
            BoundaryIORollup(
                commodity_id="blue_iron_ore",
                direction="required_output",
                required_slots=1,
                required_flow_per_tick="1",
                proven_slots=1,
                status="proven_equivalent",
            ),
        ),
        facility_evidence=(
            FacilityCapacityEvidence(
                instance_id="crusher_blue_iron_001",
                facility_type="manufacturing_3x3",
                inferred_canonical_recipe_id="crusher_blue_iron",
                recovery_source="mandatory_exact",
                resolution_mode="precise",
                exported_type_id="item_port_grinder_1",
                target_recipe_match_status="exact_match",
                counts_toward_capacity=True,
                proof_status="proven",
            ),
        ),
        validation_diagnostics=ValidationDiagnostics(
            is_import_compatible=True,
            is_layout_healthy=False,
            summary_warnings=("export is not layout-healthy",),
        ),
    )

    assert status == "partially_proven"


def test_import_incompatible_directly_forbids_proven_equivalent() -> None:
    status = _derive_overall_status(
        recipe_rollups=(),
        boundary_io_rollups=(),
        facility_evidence=(),
        validation_diagnostics=ValidationDiagnostics(
            is_import_compatible=False,
            is_layout_healthy=True,
            summary_warnings=("export is not import-compatible",),
        ),
    )

    assert status == "unproven_or_insufficient"

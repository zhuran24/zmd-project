"""Tests for semantically aligning endfield-calc catalogs into the local canonical ID space."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.endfield_calc.diff_report import build_catalog_diff_report
from src.adapters.endfield_calc.semantic_mapping import (
    CURRENT_REPOSITORY_SEMANTIC_TARGET,
    project_catalog_to_current_repository_semantics,
    project_catalog_to_semantic_target,
)
from src.adapters.endfield_calc.snapshot_ingest import ingest_snapshot_source
from src.interchange.normalized_catalog import build_catalog_from_rules_payload

UPSTREAM_REPOSITORY_FIXTURE_DIR = Path("third_party_snapshots/endfield_calc/upstream_repository_fixture")
RULES_PATH = Path("rules/canonical_rules.json")


def test_project_catalog_to_current_repository_semantics_builds_partial_aligned_catalog() -> None:
    raw_catalog = ingest_snapshot_source(UPSTREAM_REPOSITORY_FIXTURE_DIR, source_format="typescript")

    aligned_catalog = project_catalog_to_current_repository_semantics(raw_catalog)

    assert aligned_catalog["metadata"]["source"].endswith(f"semantic alignment: {CURRENT_REPOSITORY_SEMANTIC_TARGET})")
    assert aligned_catalog["metadata"]["extensions"]["semantic_raw_item_count"] == 130
    assert aligned_catalog["metadata"]["extensions"]["semantic_raw_recipe_count"] == 172
    assert aligned_catalog["metadata"]["extensions"]["semantic_raw_facility_count"] == 14
    assert aligned_catalog["metadata"]["extensions"]["semantic_mapped_item_count"] == 19
    assert aligned_catalog["metadata"]["extensions"]["semantic_mapped_recipe_count"] == 17
    assert aligned_catalog["metadata"]["extensions"]["semantic_mapped_facility_count"] == 3

    assert {item["id"] for item in aligned_catalog["items"]} == {
        "blue_iron_block",
        "blue_iron_ore",
        "blue_iron_powder",
        "buckwheat",
        "buckwheat_powder",
        "buckwheat_seed",
        "dense_blue_iron_powder",
        "dense_source_powder",
        "fine_buckwheat_powder",
        "qiaoyu_capsule",
        "sandleaf",
        "sandleaf_powder",
        "sandleaf_seed",
        "source_ore",
        "source_powder",
        "steel_block",
        "steel_bottle",
        "steel_part",
        "valley_battery",
    }
    assert any(
        item["id"] == "qiaoyu_capsule"
        and "item_bottled_rec_hp_3" in item["aliases"]
        and item["metadata"]["semantic_mapping_reason"].startswith("Selected the restorative")
        for item in aligned_catalog["items"]
    )

    packaging_recipe = next(recipe for recipe in aligned_catalog["recipes"] if recipe["id"] == "packaging_battery")
    assert packaging_recipe["facility_type"] == "manufacturing_6x4"
    assert packaging_recipe["cycle_seconds"] == 10.0
    assert packaging_recipe["inputs"] == [
        {"item_id": "dense_source_powder", "amount": 15.0},
        {"item_id": "steel_part", "amount": 10.0},
    ]
    assert packaging_recipe["outputs"] == [{"item_id": "valley_battery", "amount": 1.0}]
    assert packaging_recipe["metadata"]["semantic_source_id"] == "tools_proc_battery_3_1"
    assert packaging_recipe["metadata"]["semantic_source_facility_id"] == "item_port_tools_asm_mc_1"

    assert [facility["id"] for facility in aligned_catalog["facilities"]] == [
        "manufacturing_3x3",
        "manufacturing_5x5",
        "manufacturing_6x4",
    ]
    assert any(
        facility["id"] == "manufacturing_6x4"
        and facility["footprint"] == {"w": 6, "h": 4}
        and facility["port_rule"] == "long_sides"
        and facility["metadata"]["semantic_source_ids"]
        == [
            "item_port_filling_pd_mc_1",
            "item_port_thickener_1",
            "item_port_tools_asm_mc_1",
        ]
        for facility in aligned_catalog["facilities"]
    )


def test_project_catalog_to_current_repository_semantics_matches_reference_core_for_the_mapped_slice() -> None:
    raw_catalog = ingest_snapshot_source(UPSTREAM_REPOSITORY_FIXTURE_DIR, source_format="typescript")
    aligned_catalog = project_catalog_to_current_repository_semantics(raw_catalog)
    reference_catalog = build_catalog_from_rules_payload(json.loads(RULES_PATH.read_text(encoding="utf-8")))

    report = build_catalog_diff_report(reference_catalog, aligned_catalog)

    assert report["items"]["reference_count"] == 19
    assert report["items"]["candidate_count"] == 19
    assert report["items"]["shared_count"] == 19
    assert report["items"]["shared_exact_count"] == 19
    assert report["items"]["shared_mismatched_count"] == 0
    assert report["items"]["only_in_reference"] == []
    assert report["items"]["only_in_candidate"] == []

    assert report["recipes"]["reference_count"] == 17
    assert report["recipes"]["candidate_count"] == 17
    assert report["recipes"]["shared_count"] == 17
    assert report["recipes"]["shared_exact_count"] == 17
    assert report["recipes"]["shared_mismatched_count"] == 0
    assert report["recipes"]["only_in_reference"] == []
    assert report["recipes"]["only_in_candidate"] == []

    assert report["facilities"]["reference_count"] == 7
    assert report["facilities"]["candidate_count"] == 3
    assert report["facilities"]["shared_count"] == 3
    assert report["facilities"]["shared_exact_count"] == 3
    assert report["facilities"]["shared_mismatched_count"] == 0
    assert report["facilities"]["only_in_reference"] == [
        "boundary_storage_port",
        "power_pole",
        "protocol_core",
        "protocol_storage_box",
    ]
    assert report["facilities"]["only_in_candidate"] == []

    assert report["power"]["reference_count"] == 0
    assert report["power"]["candidate_count"] == 0
    assert report["power"]["shared_count"] == 0


def test_project_catalog_to_current_repository_semantics_rejects_unmapped_recipe_flows() -> None:
    raw_catalog = ingest_snapshot_source(UPSTREAM_REPOSITORY_FIXTURE_DIR, source_format="typescript")
    broken_catalog = json.loads(json.dumps(raw_catalog, ensure_ascii=False))
    packaging_recipe = next(recipe for recipe in broken_catalog["recipes"] if recipe["id"] == "tools_proc_battery_3_1")
    packaging_recipe["inputs"][0]["item_id"] = "item_unknown_for_test"

    with pytest.raises(ValueError, match="item_unknown_for_test"):
        project_catalog_to_semantic_target(broken_catalog)

"""Tests for the Phase-1 neutral catalog contract."""

from __future__ import annotations

import json
from pathlib import Path

from src.interchange.normalized_catalog import (
    NormalizedCatalog,
    build_catalog_from_rules_payload,
    catalog_stable_hash,
    normalize_catalog_payload,
)


def test_normalized_catalog_sorts_entities_and_hashes_stably() -> None:
    payload = {
        "metadata": {
            "source": "test",
            "generated_at": "2026-03-25T00:00:00Z",
        },
        "items": [
            {"id": "z_item", "name": "Z"},
            {"id": "a_item", "name": "A"},
        ],
        "recipes": [
            {
                "id": "recipe_b",
                "facility_type": "smelter",
                "cycle_seconds": 3,
                "inputs": {"z_item": 1},
                "outputs": [{"item_id": "a_item", "amount": 2}],
            },
            {
                "id": "recipe_a",
                "facility_type": "smelter",
                "cycle_seconds": 1,
                "inputs": [],
                "outputs": [],
            },
        ],
        "facilities": [
            {
                "id": "smelter",
                "footprint": {"w": 3, "h": 3},
                "rotatable": True,
                "needs_power": True,
            }
        ],
        "power": [
            {"facility_id": "smelter", "mode": "consume", "value_kw": 10},
        ],
        "port_rules": [
            {
                "id": "rule_b",
                "input_sides": ["S", "N"],
                "output_sides": ["W", "E"],
            }
        ],
    }

    normalized = normalize_catalog_payload(payload)
    catalog = NormalizedCatalog.from_mapping(payload)

    assert [item["id"] for item in normalized["items"]] == ["a_item", "z_item"]
    assert [recipe["id"] for recipe in normalized["recipes"]] == ["recipe_a", "recipe_b"]
    assert normalized["port_rules"][0]["input_sides"] == ["N", "S"]
    assert catalog.stable_hash() == catalog_stable_hash(normalized)


def test_build_catalog_from_rules_payload_extracts_current_repository_boundaries() -> None:
    rules_payload = json.loads(Path("rules/canonical_rules.json").read_text(encoding="utf-8"))

    catalog = build_catalog_from_rules_payload(rules_payload)

    assert catalog["metadata"]["source"] == "current_repository_rules"
    assert any(facility["id"] == "manufacturing_3x3" and facility["needs_power"] for facility in catalog["facilities"])
    assert any(recipe["id"] == "packaging_battery" and recipe["facility_type"] == "manufacturing_6x4" for recipe in catalog["recipes"])
    assert any(item["id"] == "valley_battery" for item in catalog["items"])

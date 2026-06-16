"""Tests for normalized-catalog diff reports."""

from __future__ import annotations

from src.adapters.endfield_calc.diff_report import (
    build_catalog_diff_report,
    render_catalog_diff_markdown,
)
from src.interchange.normalized_catalog import build_catalog_from_rules_payload


def test_catalog_diff_report_summarizes_id_differences() -> None:
    reference_catalog = build_catalog_from_rules_payload(
        {
            "globals": {"time": {"tick_interval_seconds": 2.0}},
            "facility_templates": {
                "manufacturing_3x3": {
                    "dimensions": {"w": 3, "h": 3},
                    "needs_power": True,
                    "port_rule": "opposite_parallel_sides",
                }
            },
            "recipes": {
                "smelt_iron": {
                    "template": "manufacturing_3x3",
                    "ticks_per_cycle": 3,
                    "inputs": {"raw_ore": 2},
                    "outputs": {"iron_plate": 1},
                }
            },
        }
    )
    candidate_catalog = {
        "metadata": {
            "version": "0.1.0",
            "source": "candidate",
            "generated_at": "2026-03-25T00:00:00Z",
        },
        "items": [
            {"id": "raw_ore", "name": "raw_ore", "category": "ore", "unit": "item", "aliases": [], "metadata": {}},
            {"id": "iron_plate", "name": "iron_plate", "category": "plate", "unit": "item", "aliases": [], "metadata": {}},
            {"id": "slag", "name": "slag", "category": "byproduct", "unit": "item", "aliases": [], "metadata": {}},
        ],
        "recipes": [
            {
                "id": "smelt_iron",
                "name": "smelt_iron",
                "facility_type": "manufacturing_3x3",
                "cycle_seconds": 6.0,
                "inputs": [{"item_id": "raw_ore", "amount": 2.0}],
                "outputs": [{"item_id": "iron_plate", "amount": 1.0}],
                "power": {"consumption_kw": 5.0, "generation_kw": 0.0},
                "metadata": {},
            }
        ],
        "facilities": [
            {
                "id": "manufacturing_3x3",
                "name": "manufacturing_3x3",
                "footprint": {"w": 3, "h": 3},
                "rotatable": True,
                "needs_power": True,
                "power": {"consumption_kw": 5.0, "generation_kw": 0.0},
                "port_rule": "opposite_parallel_sides",
                "metadata": {},
            },
            {
                "id": "storage_box",
                "name": "storage_box",
                "footprint": {"w": 3, "h": 3},
                "rotatable": True,
                "needs_power": False,
                "power": {"consumption_kw": 0.0, "generation_kw": 0.0},
                "port_rule": "omni",
                "metadata": {},
            },
        ],
        "power": [
            {"facility_id": "manufacturing_3x3", "mode": "consume", "value_kw": 5.0, "metadata": {}},
        ],
        "port_rules": [
            {"id": "opposite_parallel_sides", "description": "opp", "input_sides": ["N", "S"], "output_sides": ["N", "S"], "restrictions": {}, "metadata": {}},
            {"id": "omni", "description": "omni", "input_sides": ["N", "E", "S", "W"], "output_sides": ["N", "E", "S", "W"], "restrictions": {}, "metadata": {}},
        ],
    }

    report = build_catalog_diff_report(reference_catalog, candidate_catalog)
    markdown = render_catalog_diff_markdown(report)

    assert report["items"]["candidate_count"] == 3
    assert report["items"]["only_in_candidate"] == ["slag"]
    assert report["items"]["shared_exact_count"] == 0
    assert report["items"]["shared_mismatched_count"] == 2
    assert report["facilities"]["only_in_candidate"] == ["storage_box"]
    assert report["recipes"]["shared_exact_count"] == 1
    assert report["power"]["candidate_count"] == 1
    assert "Catalog Diff Report" in markdown
    assert "Shared exact count" in markdown
    assert "slag" in markdown

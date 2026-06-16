"""Tests for snapshot ingest and normalization from endfield-calc-like fixtures."""

from __future__ import annotations

from pathlib import Path

from src.adapters.endfield_calc.snapshot_ingest import ingest_snapshot_dir, load_snapshot_dir


FIXTURE_DIR = Path("third_party_snapshots/endfield_calc/minimal_fixture")


def test_load_snapshot_dir_reads_required_files() -> None:
    loaded = load_snapshot_dir(FIXTURE_DIR)

    assert set(loaded.keys()) == {"items", "recipes", "facilities", "snapshot_metadata"}
    assert len(loaded["items"]) == 2
    assert loaded["snapshot_metadata"]["tick_interval_seconds"] == 2.0


def test_ingest_snapshot_dir_normalizes_fixture_into_neutral_catalog() -> None:
    catalog = ingest_snapshot_dir(FIXTURE_DIR)

    assert catalog["metadata"]["source"] == "synthetic endfield-calc fixture"
    assert catalog["metadata"]["extensions"]["tick_interval_seconds"] == 2.0
    assert any(item["id"] == "raw_ore" for item in catalog["items"])
    assert any(recipe["id"] == "smelt_iron" and recipe["cycle_seconds"] == 6.0 for recipe in catalog["recipes"])
    assert any(facility["id"] == "manufacturing_3x3" and facility["needs_power"] for facility in catalog["facilities"])
    assert any(power_entry["facility_id"] == "manufacturing_3x3" and power_entry["mode"] == "consume" for power_entry in catalog["power"])

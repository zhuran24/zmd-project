"""Sanity tests for the vendored IndustrialPlanner BASES snapshot.

Tests are refresh-friendly: they read SOURCE_METADATA.json so re-running
scripts/refresh_industrial_planner_bases.py does not require test edits as
long as the data shape stays valid.
"""
from __future__ import annotations

import json
from pathlib import Path

VENDORED_DIR = Path("third_party_snapshots/industrial_planner/bases")
BASES_PATH = VENDORED_DIR / "bases.json"
METADATA_PATH = VENDORED_DIR / "SOURCE_METADATA.json"

REQUIRED_BASE_FIELDS = {"id", "name", "placeableSize", "outerRing", "tags"}
REQUIRED_OUTER_RING_FIELDS = {"top", "right", "bottom", "left"}


def _load_bases() -> dict:
    return json.loads(BASES_PATH.read_text(encoding="utf-8"))


def _load_metadata() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_vendored_bases_file_exists_and_has_schema() -> None:
    payload = _load_bases()
    assert payload["schema"] == "industrial-planner-bases-vendored/v0"
    assert isinstance(payload["bases"], list)
    assert len(payload["bases"]) >= 1


def test_metadata_count_matches_actual_bases() -> None:
    payload = _load_bases()
    metadata = _load_metadata()
    assert metadata["observed_counts"]["bases"] == len(payload["bases"])


def test_each_base_has_required_fields() -> None:
    payload = _load_bases()
    for base in payload["bases"]:
        assert REQUIRED_BASE_FIELDS.issubset(base.keys()), (
            f"base {base.get('id')} missing fields: "
            f"{REQUIRED_BASE_FIELDS - set(base.keys())}"
        )
        assert isinstance(base["placeableSize"], int)
        assert base["placeableSize"] > 0
        assert REQUIRED_OUTER_RING_FIELDS.issubset(base["outerRing"].keys())
        assert isinstance(base["tags"], list)
        assert len(base["tags"]) >= 1


def test_active_scope_base_is_present() -> None:
    """PROJECT_LOCK active scope is valley4_protocol_core (70x70).

    If upstream renames or removes this base, exact-mode runs would break.
    """
    payload = _load_bases()
    by_id = {b["id"]: b for b in payload["bases"]}
    assert "valley4_protocol_core" in by_id, (
        "Active-scope base valley4_protocol_core missing from vendored snapshot"
    )
    assert by_id["valley4_protocol_core"]["placeableSize"] == 70


def test_base_count_does_not_silently_collapse() -> None:
    """Catch upstream rollbacks; deliberate shrinkage requires updating
    previous_observed_counts in SOURCE_METADATA.json."""
    metadata = _load_metadata()
    current = metadata["observed_counts"]["bases"]
    previous = (metadata.get("previous_observed_counts") or {}).get("bases")
    if isinstance(previous, int) and previous > 0:
        # Allow a single-base reduction noise floor; bigger shrinks must be
        # acknowledged via a manual SOURCE_METADATA edit.
        assert current >= previous - 1, (
            f"Base count {current} dropped sharply from previous {previous}; "
            "if intentional, update SOURCE_METADATA.json previous_observed_counts."
        )

"""Tests for proof-bound compatibility export entries in the delivery manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.industrial_planner import write_industrial_planner_export_bundle
from src.io.delivery_manifest import build_certified_delivery_manifest
from src.io.serializer import build_canonical_blueprint_payload
from src.tests.certified_frontier_helpers import persist_canonical_blueprint_for_test


def _write_canonical_industrial_planner_bundle(project_root: Path) -> None:
    blueprint = build_canonical_blueprint_payload(
        placement_solution={},
        facility_pools={},
        ghost_rect={"w": 1, "h": 1, "area": 1, "anchor_x": 0, "anchor_y": 0},
        export_timestamp="2026-03-25T00:00:00Z",
    )
    persist_canonical_blueprint_for_test(project_root, blueprint)
    write_industrial_planner_export_bundle(
        output_dir=project_root / "data" / "exports" / "industrial_planner",
        blueprint_payload=blueprint,
    )


def _open_campaign_state() -> dict[str, object]:
    return {
        "solve_mode": "certified_exact",
        "campaign_hours": 0.0,
        "schema_version": 2,
        "proof_summary_schema_version": 1,
        "updated_at": "2026-03-25T00:00:00Z",
    }


def test_delivery_manifest_includes_replayable_compatibility_exports_when_present(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_canonical_industrial_planner_bundle(project_root)

    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=_open_campaign_state(),
    )

    exports = payload["compatibility_exports"]["industrial_planner"]
    assert exports["blueprint"]["exists"] is True
    assert exports["compatibility_manifest"]["exists"] is True
    assert exports["validation_report"]["exists"] is True
    assert exports["validation_report_markdown"]["exists"] is True
    assert exports["throughput_report"]["exists"] is True
    assert exports["throughput_report_markdown"]["exists"] is True


def test_delivery_manifest_rejects_compatibility_export_not_derived_from_canonical_blueprint(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_canonical_industrial_planner_bundle(project_root)
    export_path = (
        project_root
        / "data"
        / "exports"
        / "industrial_planner"
        / "industrial_planner.blueprint.json"
    )
    export_path.write_text(
        json.dumps({"attacker": "unrelated-layout", "devices": [{"x": 999, "y": 999}]})
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="certified compatibility export"):
        build_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=_open_campaign_state(),
        )


def test_delivery_manifest_rejects_partial_compatibility_export_bundle(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    export_dir = project_root / "data" / "exports" / "industrial_planner"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "industrial_planner.blueprint.json").write_text("{}\n", encoding="utf-8")
    (export_dir / "industrial_planner.compatibility_manifest.json").write_text(
        "{}\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="complete regular-file bundle"):
        build_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=_open_campaign_state(),
        )

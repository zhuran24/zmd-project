"""Tests for optional compatibility export entries in the delivery manifest."""

from __future__ import annotations

from pathlib import Path

from src.io.delivery_manifest import build_certified_delivery_manifest


def test_delivery_manifest_includes_compatibility_exports_when_present(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    export_dir = project_root / "data" / "exports" / "industrial_planner"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "industrial_planner.blueprint.json").write_text("{}\n", encoding="utf-8")
    (export_dir / "industrial_planner.compatibility_manifest.json").write_text("{}\n", encoding="utf-8")

    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state={
            "solve_mode": "certified_exact",
            "campaign_hours": 0.0,
            "schema_version": 2,
            "proof_summary_schema_version": 1,
            "updated_at": "2026-03-25T00:00:00Z",
        },
    )

    assert payload["compatibility_exports"]["industrial_planner"]["blueprint"]["exists"] is True
    assert payload["compatibility_exports"]["industrial_planner"]["compatibility_manifest"]["exists"] is True
    assert payload["compatibility_exports"]["industrial_planner"]["throughput_report"]["exists"] is False
    assert payload["compatibility_exports"]["industrial_planner"]["throughput_report_markdown"]["exists"] is False

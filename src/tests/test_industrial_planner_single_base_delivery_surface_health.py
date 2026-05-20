"""Tests for the compact IndustrialPlanner current-surface health snapshot."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from src.render.industrial_planner_single_base_delivery_surface_health import (
    SingleBaseDeliverySurfaceHealthError,
    build_single_base_delivery_surface_health,
)



def _copy_checked_in_surface_alignment_tree(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    target_examples_root = project_root / "data" / "examples" / "industrial_planner"
    target_examples_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("data/examples/industrial_planner"), target_examples_root)
    source_surface_alignment_dir = Path(".artifacts/industrial_planner_single_base_delivery_surface_alignment")
    assert source_surface_alignment_dir.exists()
    target_surface_alignment_dir = (
        project_root / ".artifacts" / "industrial_planner_single_base_delivery_surface_alignment"
    )
    target_surface_alignment_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_surface_alignment_dir, target_surface_alignment_dir)
    return project_root



def test_build_single_base_delivery_surface_health_writes_compact_snapshot(tmp_path: Path) -> None:
    project_root = _copy_checked_in_surface_alignment_tree(tmp_path)

    result = build_single_base_delivery_surface_health(project_root=project_root)

    assert result.release_id == "valley4_protocol_core_70x70_r20260416"
    assert result.base_id == "valley4_protocol_core"
    assert result.delivery_status == "ready_for_single_base_delivery"
    assert result.exact_full_scale_certified_status == "open"
    assert result.status == "clean"
    assert result.is_clean is True
    assert result.checked_check_count >= 20
    assert result.drift_check_count == 0
    assert result.output_json_path.exists()
    assert result.output_markdown_path.exists()
    assert result.output_console_path.exists()

    payload = json.loads(result.output_json_path.read_text(encoding="utf-8"))
    assert payload["surface_health"]["status"] == "clean"
    assert payload["surface_health"]["badge"]["label"] == "current surface"
    assert payload["surface_health"]["summary_text"].startswith("clean · ")
    assert payload["active_contract"]["release_id"] == "valley4_protocol_core_70x70_r20260416"
    assert payload["exact_full_scale_certified"]["status"] == "open"
    assert payload["checked_consumer_surfaces"]["frontdoor_manifest_json"].endswith(
        "data/examples/industrial_planner/frontdoor_manifest.json"
    )

    markdown = result.output_markdown_path.read_text(encoding="utf-8")
    console = result.output_console_path.read_text(encoding="utf-8")
    assert "# IndustrialPlanner Current Surface Health" in markdown
    assert "current surface" in console
    assert "drift checks: 0" in console



def test_build_single_base_delivery_surface_health_fails_closed_when_surface_alignment_summary_is_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(
        SingleBaseDeliverySurfaceHealthError,
        match="surface-alignment JSON summary is missing",
    ):
        build_single_base_delivery_surface_health(project_root=project_root)

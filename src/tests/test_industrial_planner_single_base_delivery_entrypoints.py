"""Tests for the aggregated IndustrialPlanner single-base active-entrypoints builder."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from src.render.industrial_planner_single_base_delivery_entrypoints import (
    SingleBaseDeliveryEntrypointsError,
    build_single_base_delivery_entrypoints,
)



def _copy_checked_in_active_industrial_planner_tree(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    target_root = project_root / "data" / "examples" / "industrial_planner"
    target_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("data/examples/industrial_planner"), target_root)
    source_surface_alignment_dir = Path(".artifacts/industrial_planner_single_base_delivery_surface_alignment")
    if source_surface_alignment_dir.exists():
        target_surface_alignment_dir = (
            project_root / ".artifacts" / "industrial_planner_single_base_delivery_surface_alignment"
        )
        target_surface_alignment_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_surface_alignment_dir, target_surface_alignment_dir)
    return project_root



def test_build_single_base_delivery_entrypoints_writes_aggregate_manifest(tmp_path: Path) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)

    result = build_single_base_delivery_entrypoints(project_root=project_root)

    assert result.release_id == "valley4_protocol_core_70x70_r20260416"
    assert result.base_id == "valley4_protocol_core"
    assert result.lot_size == 70
    assert result.delivery_status == "ready_for_single_base_delivery"
    assert result.entrypoint_group_count == 6
    assert result.action_count >= 10
    assert result.exact_full_scale_certified_status == "open"

    output_json_path = project_root / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_entrypoints.json"
    output_markdown_path = project_root / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_entrypoints.md"
    assert output_json_path.exists()
    assert output_markdown_path.exists()

    payload = json.loads(output_json_path.read_text(encoding="utf-8"))
    assert payload["active_contract"]["release_id"] == "valley4_protocol_core_70x70_r20260416"
    assert payload["active_contract"]["delivery_status"] == "ready_for_single_base_delivery"
    assert payload["exact_full_scale_certified"]["status"] == "open"
    assert payload["actions"]["download_latest_bundle_zip"] == (
        "data/examples/industrial_planner/industrial_planner_latest_single_base_delivery_bundle.zip"
    )
    assert payload["actions"]["release_pointer_json"] == (
        "data/examples/industrial_planner/active_single_base_delivery_release.json"
    )
    assert payload["actions"]["viewer_pointer_json"] == (
        "data/examples/industrial_planner/active_single_base_delivery_viewer.json"
    )
    assert payload["actions"]["active_entrypoints_json"] == (
        "data/examples/industrial_planner/active_single_base_delivery_entrypoints.json"
    )
    assert payload["actions"]["surface_alignment_summary_json"] == (
        ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json"
    )
    assert payload["actions"]["current_surface_health_json"] == (
        "data/examples/industrial_planner/current_surface_health.json"
    )
    assert payload["current_entrypoints"]["viewer"]["index_html"].endswith(
        "data/examples/industrial_planner/viewers/valley4_protocol_core_70x70_r20260416/index.html"
    )
    assert payload["current_entrypoints"]["landing"]["current_bundle_zip"].endswith(
        "data/examples/industrial_planner/current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    )
    assert payload["current_entrypoints"]["latest_bundle"]["source_current_bundle_zip"] == (
        "data/examples/industrial_planner/current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    )
    assert payload["repo_frontdoor"]["index_html"] == "data/examples/industrial_planner/index.html"
    assert payload["repo_frontdoor"]["download_primary_href"] == (
        "data/examples/industrial_planner/industrial_planner_latest_single_base_delivery_bundle.zip"
    )
    assert payload["surface_alignment"]["status"] == "clean"
    assert payload["surface_alignment"]["drift_check_count"] == 0
    assert payload["surface_health"]["status"] == "clean"
    assert payload["surface_health"]["drift_check_count"] == 0
    assert payload["current_entrypoints"]["surface_alignment"]["json"] == (
        ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json"
    )
    assert payload["current_entrypoints"]["surface_health"]["json"] == (
        "data/examples/industrial_planner/current_surface_health.json"
    )

    markdown = output_markdown_path.read_text(encoding="utf-8")
    assert "# Active IndustrialPlanner Single-Base Entrypoints" in markdown
    assert "## Current entrypoint groups" in markdown
    assert "Release" in markdown
    assert "Latest Bundle" in markdown
    assert "Surface Alignment" in markdown
    assert "Surface Health" in markdown
    assert "## Current consumer-surface audit" in markdown
    assert "## Current surface health snapshot" in markdown



def test_build_single_base_delivery_entrypoints_fails_closed_when_release_ids_drift(tmp_path: Path) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)
    viewer_pointer_json_path = (
        project_root / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_viewer.json"
    )
    payload = json.loads(viewer_pointer_json_path.read_text(encoding="utf-8"))
    payload["current_viewer"]["release_id"] = "mismatched_release"
    viewer_pointer_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryEntrypointsError,
        match="release_id",
    ):
        build_single_base_delivery_entrypoints(project_root=project_root)



def test_build_single_base_delivery_entrypoints_fails_closed_when_latest_bundle_source_drifted(tmp_path: Path) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)
    latest_bundle_pointer_json_path = (
        project_root / "data" / "examples" / "industrial_planner" / "latest_single_base_delivery_bundle.json"
    )
    payload = json.loads(latest_bundle_pointer_json_path.read_text(encoding="utf-8"))
    payload["current_bundle"]["source_current_bundle_zip"] = "data/examples/industrial_planner/current_delivery/downloads/not_the_real_bundle.zip"
    latest_bundle_pointer_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryEntrypointsError,
        match="source_current_bundle_zip|missing",
    ):
        build_single_base_delivery_entrypoints(project_root=project_root)



def test_build_single_base_delivery_entrypoints_can_require_surface_alignment_summaries(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    target_root = project_root / "data" / "examples" / "industrial_planner"
    target_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("data/examples/industrial_planner"), target_root)

    with pytest.raises(
        SingleBaseDeliveryEntrypointsError,
        match="surface-alignment JSON/Markdown/TXT summaries are required",
    ):
        build_single_base_delivery_entrypoints(
            project_root=project_root,
            require_surface_alignment=True,
        )


def test_build_single_base_delivery_entrypoints_can_require_surface_health_snapshots(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    target_root = project_root / "data" / "examples" / "industrial_planner"
    target_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("data/examples/industrial_planner"), target_root)

    (target_root / "current_surface_health.json").unlink()
    (target_root / "current_surface_health.md").unlink()
    (target_root / "current_surface_health.txt").unlink()

    with pytest.raises(
        SingleBaseDeliveryEntrypointsError,
        match="current-surface-health JSON/Markdown/TXT snapshots are required",
    ):
        build_single_base_delivery_entrypoints(
            project_root=project_root,
            require_surface_health=True,
        )

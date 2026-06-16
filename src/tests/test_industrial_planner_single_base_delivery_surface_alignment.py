"""Tests for the checked-in IndustrialPlanner single-base delivery surface alignment audit."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from src.render.industrial_planner_single_base_delivery_surface_alignment import (
    build_single_base_delivery_surface_alignment_result,
    write_single_base_delivery_surface_alignment_outputs,
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



def test_build_single_base_delivery_surface_alignment_result_is_clean_for_checked_in_surface(
    tmp_path: Path,
) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)

    result = build_single_base_delivery_surface_alignment_result(project_root=project_root)

    assert result.release_id == "valley4_protocol_core_70x70_r20260416"
    assert result.base_id == "valley4_protocol_core"
    assert result.lot_size == 70
    assert result.delivery_status == "ready_for_single_base_delivery"
    assert result.exact_full_scale_certified_status == "open"
    assert result.checked_check_count >= 20
    assert result.helper_link_count >= 6
    assert result.is_clean is True
    assert result.drift_check_count == 0

    payload = result.to_dict()
    assert payload["summary"]["status"] == "clean"
    assert payload["active_contract"]["release_id"] == "valley4_protocol_core_70x70_r20260416"
    assert payload["exact_full_scale_certified"]["status"] == "open"
    assert any(
        check["check_id"] == "actions_active_entrypoints_json" and check["status"] == "clean"
        for check in payload["checks"]
    )
    assert any(
        check["check_id"] == "helper_active_entrypoints_json_href" and check["status"] == "clean"
        for check in payload["checks"]
    )
    assert any(
        check["check_id"] == "actions_surface_alignment_summary_json" and check["status"] == "clean"
        for check in payload["checks"]
    )
    assert any(
        check["check_id"] == "helper_surface_alignment_json_href" and check["status"] == "clean"
        for check in payload["checks"]
    )
    assert any(
        check["check_id"] == "actions_current_surface_health_json" and check["status"] == "clean"
        for check in payload["checks"]
    )
    assert any(
        check["check_id"] == "helper_surface_health_json_href" and check["status"] == "clean"
        for check in payload["checks"]
    )

    outputs = write_single_base_delivery_surface_alignment_outputs(
        result,
        json_output_path=tmp_path / "surface_alignment_summary.json",
        markdown_output_path=tmp_path / "surface_alignment_summary.md",
        console_output_path=tmp_path / "surface_alignment_summary.txt",
    )
    assert outputs.json_output_path.exists()
    assert outputs.markdown_output_path.exists()
    assert outputs.console_output_path.exists()
    written_payload = json.loads(outputs.json_output_path.read_text(encoding="utf-8"))
    assert written_payload["summary"]["status"] == "clean"
    assert "single-base delivery surface alignment audit" in outputs.markdown_output_path.read_text(encoding="utf-8")
    assert "overall status: clean" in outputs.console_output_path.read_text(encoding="utf-8")



def test_build_single_base_delivery_surface_alignment_result_detects_frontdoor_helper_link_drift(
    tmp_path: Path,
) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)
    frontdoor_index_html_path = (
        project_root / "data" / "examples" / "industrial_planner" / "index.html"
    )
    html = frontdoor_index_html_path.read_text(encoding="utf-8")
    html = html.replace(
        'href="active_single_base_delivery_entrypoints.json"',
        'href="broken_active_single_base_delivery_entrypoints.json"',
        1,
    )
    frontdoor_index_html_path.write_text(html, encoding="utf-8")

    result = build_single_base_delivery_surface_alignment_result(project_root=project_root)

    assert result.is_clean is False
    assert result.drift_check_count >= 1
    drift_checks = {check.check_id: check for check in result.checks if not check.is_clean}
    assert "helper_active_entrypoints_json_href" in drift_checks
    assert drift_checks["helper_active_entrypoints_json_href"].expected == "active_single_base_delivery_entrypoints.json"
    assert drift_checks["helper_active_entrypoints_json_href"].actual == "<missing>"



def test_build_single_base_delivery_surface_alignment_result_detects_entrypoints_frontdoor_drift(
    tmp_path: Path,
) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)
    entrypoints_json_path = (
        project_root / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_entrypoints.json"
    )
    payload = json.loads(entrypoints_json_path.read_text(encoding="utf-8"))
    payload["repo_frontdoor"]["download_primary_href"] = "data/examples/industrial_planner/not_the_latest_bundle.zip"
    entrypoints_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    result = build_single_base_delivery_surface_alignment_result(project_root=project_root)

    assert result.is_clean is False
    drift_checks = {check.check_id: check for check in result.checks if not check.is_clean}
    assert "download_primary_href" in drift_checks
    assert drift_checks["download_primary_href"].expected.endswith(
        "industrial_planner_latest_single_base_delivery_bundle.zip"
    )
    assert drift_checks["download_primary_href"].actual.endswith("not_the_latest_bundle.zip")



def test_build_single_base_delivery_surface_alignment_result_detects_surface_alignment_ref_drift(
    tmp_path: Path,
) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)
    entrypoints_json_path = (
        project_root / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_entrypoints.json"
    )
    payload = json.loads(entrypoints_json_path.read_text(encoding="utf-8"))
    payload["actions"]["surface_alignment_summary_json"] = ".artifacts/broken_surface_alignment_summary.json"
    payload["surface_alignment"]["json"] = ".artifacts/broken_surface_alignment_summary.json"
    payload["current_entrypoints"]["surface_alignment"]["json"] = ".artifacts/broken_surface_alignment_summary.json"
    entrypoints_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    result = build_single_base_delivery_surface_alignment_result(project_root=project_root)

    assert result.is_clean is False
    drift_checks = {check.check_id: check for check in result.checks if not check.is_clean}
    assert "actions_surface_alignment_summary_json" in drift_checks
    assert "surface_alignment_json" in drift_checks
    assert "current_entrypoints_surface_alignment_json" in drift_checks
    assert drift_checks["actions_surface_alignment_summary_json"].expected.endswith(
        "surface_alignment_summary.json"
    )
    assert drift_checks["actions_surface_alignment_summary_json"].actual.endswith(
        "broken_surface_alignment_summary.json"
    )


def test_build_single_base_delivery_surface_alignment_result_detects_surface_health_ref_drift(
    tmp_path: Path,
) -> None:
    project_root = _copy_checked_in_active_industrial_planner_tree(tmp_path)
    frontdoor_manifest_json_path = (
        project_root / "data" / "examples" / "industrial_planner" / "frontdoor_manifest.json"
    )
    payload = json.loads(frontdoor_manifest_json_path.read_text(encoding="utf-8"))
    payload["actions"]["current_surface_health_json"] = "broken_current_surface_health.json"
    payload["surface_health"]["json"] = "broken_current_surface_health.json"
    payload["current_frontdoor"]["current_surface_health_json"] = "broken_current_surface_health.json"
    frontdoor_manifest_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    result = build_single_base_delivery_surface_alignment_result(project_root=project_root)

    assert result.is_clean is False
    drift_checks = {check.check_id: check for check in result.checks if not check.is_clean}
    assert "actions_current_surface_health_json" in drift_checks
    assert "surface_health_json" in drift_checks
    assert "current_frontdoor_surface_health_json" in drift_checks
    assert drift_checks["actions_current_surface_health_json"].expected.endswith("current_surface_health.json")
    assert drift_checks["actions_current_surface_health_json"].actual.endswith("broken_current_surface_health.json")

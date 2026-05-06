"""Tests for the versioned IndustrialPlanner single-base delivery release builder."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from scripts.build_industrial_planner_single_base_delivery_release import (
    SingleBaseDeliveryReleaseError,
    build_single_base_delivery_release,
)


def _copy_checked_in_delivery_ready_run(tmp_path: Path) -> Path:
    source_run_dir = Path(".artifacts/industrial_planner_single_base_e2e")
    assert source_run_dir.exists()
    destination = tmp_path / "single_base_e2e"
    shutil.copytree(source_run_dir, destination)
    return destination



def test_build_single_base_delivery_release_writes_versioned_bundle_pointer_and_index(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)

    release_root = tmp_path / "releases"
    pointer_json_path = tmp_path / "active_single_base_delivery_release.json"
    pointer_markdown_path = tmp_path / "active_single_base_delivery_release.md"
    index_json_path = release_root / "release_index.json"
    index_markdown_path = release_root / "release_index.md"
    viewer_root = tmp_path / "viewers"
    viewer_pointer_json_path = tmp_path / "active_single_base_delivery_viewer.json"
    viewer_pointer_markdown_path = tmp_path / "active_single_base_delivery_viewer.md"
    viewer_index_json_path = viewer_root / "viewer_index.json"
    viewer_index_markdown_path = viewer_root / "viewer_index.md"
    landing_output_dir = tmp_path / "current_delivery"
    frontdoor_output_dir = tmp_path
    surface_alignment_json_path = tmp_path / ".artifacts" / "surface_alignment_summary.json"
    surface_alignment_markdown_path = tmp_path / ".artifacts" / "surface_alignment_summary.md"
    surface_alignment_console_path = tmp_path / ".artifacts" / "surface_alignment_summary.txt"

    result = build_single_base_delivery_release(
        source_run_dir=source_run_dir,
        release_root=release_root,
        release_id="valley4_protocol_core_70x70_r1",
        pointer_json_path=pointer_json_path,
        pointer_markdown_path=pointer_markdown_path,
        index_json_path=index_json_path,
        index_markdown_path=index_markdown_path,
        viewer_root=viewer_root,
        viewer_pointer_json_path=viewer_pointer_json_path,
        viewer_pointer_markdown_path=viewer_pointer_markdown_path,
        viewer_index_json_path=viewer_index_json_path,
        viewer_index_markdown_path=viewer_index_markdown_path,
        landing_output_dir=landing_output_dir,
        frontdoor_output_dir=frontdoor_output_dir,
        surface_alignment_json_path=surface_alignment_json_path,
        surface_alignment_markdown_path=surface_alignment_markdown_path,
        surface_alignment_console_path=surface_alignment_console_path,
        surface_health_json_path=tmp_path / "current_surface_health.json",
        surface_health_markdown_path=tmp_path / "current_surface_health.md",
        surface_health_console_path=tmp_path / "current_surface_health.txt",
    )

    assert result.release_id == "valley4_protocol_core_70x70_r1"
    assert result.delivery_status == "ready_for_single_base_delivery"
    assert result.exact_full_scale_certified_status == "open"
    assert result.payload_artifact_count == 24
    assert result.required_payload_artifact_count == 21
    assert result.viewer_bundle_status == "built"
    assert result.viewer_output_dir == viewer_root / "valley4_protocol_core_70x70_r1"
    assert result.viewer_selected_facility_type_count is not None
    assert result.viewer_selected_pose_count is not None
    assert result.viewer_payload_download_count == 24
    assert result.viewer_metadata_download_count is not None and result.viewer_metadata_download_count >= 5
    assert result.viewer_quick_download_count == 5
    assert result.landing_bundle_status == "built"
    assert result.landing_output_dir == landing_output_dir
    assert result.landing_quick_download_count == 5
    assert result.landing_download_group_count is not None and result.landing_download_group_count >= 4
    assert result.frontdoor_bundle_status == "built"
    assert result.frontdoor_output_dir == frontdoor_output_dir
    assert result.frontdoor_quick_download_count == 5
    assert result.frontdoor_download_group_count is not None and result.frontdoor_download_group_count >= 4
    assert result.entrypoints_bundle_status == "built"
    assert result.entrypoints_json_path == tmp_path / "active_single_base_delivery_entrypoints.json"
    assert result.entrypoints_markdown_path == tmp_path / "active_single_base_delivery_entrypoints.md"
    assert result.entrypoints_group_count == 6
    assert result.entrypoints_action_count is not None and result.entrypoints_action_count >= 10
    assert result.surface_alignment_status == "clean"
    assert result.surface_alignment_json_path == surface_alignment_json_path
    assert result.surface_alignment_markdown_path == surface_alignment_markdown_path
    assert result.surface_alignment_console_path == surface_alignment_console_path
    assert result.surface_alignment_check_count is not None and result.surface_alignment_check_count >= 20
    assert result.surface_alignment_drift_check_count == 0
    assert result.surface_health_status == "clean"
    assert result.surface_health_json_path == tmp_path / "current_surface_health.json"
    assert result.surface_health_markdown_path == tmp_path / "current_surface_health.md"
    assert result.surface_health_console_path == tmp_path / "current_surface_health.txt"
    assert result.surface_health_check_count == result.surface_alignment_check_count
    assert result.surface_health_drift_check_count == 0

    release_dir = release_root / "valley4_protocol_core_70x70_r1"
    assert (release_dir / "bundle" / "industrial_planner.blueprint.json").exists()
    assert (release_dir / "support_suite" / "full_demand_base_support_matrix.json").exists()
    assert (release_dir / "checks" / "checked_artifact_suite_summary.txt").exists()
    assert (release_dir / "run_summary.md").exists()
    assert (release_dir / "release_manifest.json").exists()
    assert (release_dir / "release_manifest.md").exists()
    assert (release_dir / "SHA256SUMS.txt").exists()

    manifest_payload = json.loads((release_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert manifest_payload["release"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert manifest_payload["release"]["delivery_status"] == "ready_for_single_base_delivery"
    assert manifest_payload["delivery_entrypoints"]["blueprint"].endswith(
        "bundle/industrial_planner.blueprint.json"
    )
    assert manifest_payload["source_run"]["overall_status"] == "success"
    assert manifest_payload["source_run"]["checked_artifact_status"] == "clean"
    assert manifest_payload["exact_full_scale_certified"]["status"] == "open"
    assert len(manifest_payload["artifacts"]) == 24

    pointer_payload = json.loads(pointer_json_path.read_text(encoding="utf-8"))
    assert pointer_payload["current_release"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert pointer_payload["current_release"]["blueprint"].endswith(
        "bundle/industrial_planner.blueprint.json"
    )
    assert pointer_payload["current_release"]["exact_full_scale_certified"]["status"] == "open"

    index_payload = json.loads(index_json_path.read_text(encoding="utf-8"))
    assert index_payload["current_release_id"] == "valley4_protocol_core_70x70_r1"
    assert index_payload["release_count"] == 1
    assert index_payload["releases"][0]["release_id"] == "valley4_protocol_core_70x70_r1"

    sha256_lines = (release_dir / "SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    assert any(line.endswith("bundle/industrial_planner.blueprint.json") for line in sha256_lines)
    assert any(line.endswith("release_manifest.json") for line in sha256_lines)

    viewer_dir = viewer_root / "valley4_protocol_core_70x70_r1"
    assert (viewer_dir / "index.html").exists()
    assert (viewer_dir / "release_viewer_manifest.json").exists()
    assert (viewer_dir / "downloads" / "release" / "bundle" / "industrial_planner.blueprint.json").exists()

    viewer_manifest_payload = json.loads((viewer_dir / "release_viewer_manifest.json").read_text(encoding="utf-8"))
    assert viewer_manifest_payload["current_release"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert viewer_manifest_payload["exact_full_scale_certified"]["status"] == "open"

    viewer_pointer_payload = json.loads(viewer_pointer_json_path.read_text(encoding="utf-8"))
    assert viewer_pointer_payload["current_viewer"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert viewer_pointer_payload["current_viewer"]["index_html"].endswith(
        "viewers/valley4_protocol_core_70x70_r1/index.html"
    )
    assert viewer_pointer_payload["current_viewer"]["quick_download_count"] == 5
    assert viewer_pointer_payload["current_viewer"]["exact_full_scale_certified"]["status"] == "open"

    viewer_index_payload = json.loads(viewer_index_json_path.read_text(encoding="utf-8"))
    assert viewer_index_payload["current_release_id"] == "valley4_protocol_core_70x70_r1"
    assert viewer_index_payload["viewer_count"] == 1
    assert viewer_index_payload["viewers"][0]["release_id"] == "valley4_protocol_core_70x70_r1"

    assert (landing_output_dir / "index.html").exists()
    assert (landing_output_dir / "landing_manifest.json").exists()
    assert (landing_output_dir / "viewer" / "index.html").exists()
    assert (landing_output_dir / "downloads" / "industrial_planner_current_single_base_delivery_bundle.zip").exists()
    assert (landing_output_dir / "downloads" / "current_single_base_delivery_bundle.json").exists()
    assert (landing_output_dir / "downloads" / "current_single_base_delivery_bundle.md").exists()
    landing_manifest_payload = json.loads((landing_output_dir / "landing_manifest.json").read_text(encoding="utf-8"))
    assert landing_manifest_payload["current_landing"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert landing_manifest_payload["current_landing"]["current_bundle_zip"] == "downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    assert landing_manifest_payload["current_bundle_archive"]["included_entry_count"] >= 2
    assert landing_manifest_payload["exact_full_scale_certified"]["status"] == "open"
    assert landing_manifest_payload["actions"]["open_viewer"] == "viewer/index.html"
    assert landing_manifest_payload["actions"]["download_current_bundle_zip"] == "downloads/industrial_planner_current_single_base_delivery_bundle.zip"

    assert (frontdoor_output_dir / "index.html").exists()
    assert (frontdoor_output_dir / "frontdoor_manifest.json").exists()
    assert (frontdoor_output_dir / "industrial_planner_latest_single_base_delivery_bundle.zip").exists()
    assert (frontdoor_output_dir / "latest_single_base_delivery_bundle.json").exists()
    assert (frontdoor_output_dir / "latest_single_base_delivery_bundle.md").exists()
    frontdoor_manifest_payload = json.loads((frontdoor_output_dir / "frontdoor_manifest.json").read_text(encoding="utf-8"))
    assert frontdoor_manifest_payload["current_frontdoor"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert frontdoor_manifest_payload["current_frontdoor"]["current_delivery_index_html"] == "current_delivery/index.html"
    assert frontdoor_manifest_payload["actions"]["open_current_delivery"] == "current_delivery/index.html"
    assert frontdoor_manifest_payload["actions"]["open_viewer"] == "current_delivery/viewer/index.html"
    assert frontdoor_manifest_payload["actions"]["download_current_bundle_zip"] == "current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    assert frontdoor_manifest_payload["actions"]["download_latest_bundle_zip"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert frontdoor_manifest_payload["actions"]["active_entrypoints_json"] == "active_single_base_delivery_entrypoints.json"
    assert frontdoor_manifest_payload["actions"]["active_entrypoints_markdown"] == "active_single_base_delivery_entrypoints.md"
    assert frontdoor_manifest_payload["actions"]["surface_alignment_summary_json"] == ".artifacts/surface_alignment_summary.json"
    assert frontdoor_manifest_payload["actions"]["current_surface_health_json"] == "current_surface_health.json"
    assert frontdoor_manifest_payload["current_frontdoor"]["latest_bundle_zip"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert frontdoor_manifest_payload["current_frontdoor"]["active_entrypoints_json"] == "active_single_base_delivery_entrypoints.json"
    assert frontdoor_manifest_payload["current_frontdoor"]["surface_alignment_status"] == "clean"
    assert frontdoor_manifest_payload["current_frontdoor"]["surface_health_status"] == "clean"
    assert frontdoor_manifest_payload["entry_modes"]["download_first"]["primary_action"]["href"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert frontdoor_manifest_payload["script_entrypoints"]["json"] == "active_single_base_delivery_entrypoints.json"
    assert frontdoor_manifest_payload["surface_alignment"]["json"] == ".artifacts/surface_alignment_summary.json"
    assert frontdoor_manifest_payload["surface_health"]["json"] == "current_surface_health.json"
    assert frontdoor_manifest_payload["exact_full_scale_certified"]["status"] == "open"
    assert "Active entrypoints JSON" in (frontdoor_output_dir / "index.html").read_text(encoding="utf-8")
    assert "Surface alignment JSON" in (frontdoor_output_dir / "index.html").read_text(encoding="utf-8")
    assert "Current surface health JSON" in (frontdoor_output_dir / "index.html").read_text(encoding="utf-8")

    assert (frontdoor_output_dir / "active_single_base_delivery_entrypoints.json").exists()
    assert (frontdoor_output_dir / "active_single_base_delivery_entrypoints.md").exists()
    entrypoints_payload = json.loads(
        (frontdoor_output_dir / "active_single_base_delivery_entrypoints.json").read_text(encoding="utf-8")
    )
    assert entrypoints_payload["active_contract"]["release_id"] == "valley4_protocol_core_70x70_r1"
    assert entrypoints_payload["current_entrypoints"]["release"]["pointer_json"].endswith(
        "active_single_base_delivery_release.json"
    )
    assert entrypoints_payload["current_entrypoints"]["viewer"]["pointer_json"].endswith(
        "active_single_base_delivery_viewer.json"
    )
    assert entrypoints_payload["current_entrypoints"]["landing"]["index_html"].endswith(
        "current_delivery/index.html"
    )
    assert entrypoints_payload["current_entrypoints"]["latest_bundle"]["bundle_zip"].endswith(
        "industrial_planner_latest_single_base_delivery_bundle.zip"
    )
    assert entrypoints_payload["current_entrypoints"]["surface_alignment"]["status"] == "clean"
    assert entrypoints_payload["current_entrypoints"]["surface_health"]["status"] == "clean"
    assert entrypoints_payload["repo_frontdoor"]["index_html"].endswith("index.html")
    assert entrypoints_payload["actions"]["active_entrypoints_json"].endswith(
        "active_single_base_delivery_entrypoints.json"
    )
    assert entrypoints_payload["actions"]["surface_alignment_summary_json"].endswith(
        ".artifacts/surface_alignment_summary.json"
    )
    assert entrypoints_payload["actions"]["current_surface_health_json"].endswith(
        "current_surface_health.json"
    )
    assert entrypoints_payload["exact_full_scale_certified"]["status"] == "open"

    surface_alignment_payload = json.loads(surface_alignment_json_path.read_text(encoding="utf-8"))
    assert surface_alignment_payload["summary"]["status"] == "clean"
    assert surface_alignment_payload["summary"]["drift_check_count"] == 0
    assert frontdoor_manifest_payload["current_frontdoor"]["surface_alignment_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert frontdoor_manifest_payload["current_frontdoor"]["surface_alignment_drift_check_count"] == (
        surface_alignment_payload["summary"]["drift_check_count"]
    )
    assert frontdoor_manifest_payload["surface_alignment"]["checked_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert entrypoints_payload["surface_alignment"]["checked_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert entrypoints_payload["current_entrypoints"]["surface_alignment"]["checked_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert entrypoints_payload["surface_summary"]["surface_alignment_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert entrypoints_payload["surface_summary"]["surface_health_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert any(
        check["check_id"] == "helper_active_entrypoints_json_href" and check["status"] == "clean"
        for check in surface_alignment_payload["checks"]
    )

    surface_health_payload = json.loads((tmp_path / "current_surface_health.json").read_text(encoding="utf-8"))
    assert surface_health_payload["surface_health"]["status"] == "clean"
    assert surface_health_payload["surface_health"]["checked_check_count"] == (
        surface_alignment_payload["summary"]["checked_check_count"]
    )
    assert surface_health_payload["surface_health"]["drift_check_count"] == 0
    assert surface_health_payload["surface_health"]["badge"]["label"] == "current surface"
    assert frontdoor_manifest_payload["surface_health"]["checked_check_count"] == surface_health_payload["surface_health"]["checked_check_count"]
    assert entrypoints_payload["surface_health"]["checked_check_count"] == surface_health_payload["surface_health"]["checked_check_count"]
    assert surface_health_payload["active_contract"]["release_id"] == "valley4_protocol_core_70x70_r1"



def test_build_single_base_delivery_release_fails_closed_when_source_run_is_not_ready(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)
    run_summary_path = source_run_dir / "run_summary.json"
    run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
    run_summary["overall_status"] = "failed"
    run_summary["deliverable_status"] = "not_ready"
    run_summary_path.write_text(json.dumps(run_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryReleaseError,
        match="delivery-ready source run summary",
    ):
        build_single_base_delivery_release(
            source_run_dir=source_run_dir,
            release_root=tmp_path / "releases",
            release_id="should_not_exist",
            pointer_json_path=tmp_path / "active_single_base_delivery_release.json",
            pointer_markdown_path=tmp_path / "active_single_base_delivery_release.md",
            index_json_path=tmp_path / "releases" / "release_index.json",
            index_markdown_path=tmp_path / "releases" / "release_index.md",
        )



def test_build_single_base_delivery_release_fails_closed_when_viewer_bundle_cannot_be_built(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)

    pointer_json_path = tmp_path / "active_single_base_delivery_release.json"
    pointer_markdown_path = tmp_path / "active_single_base_delivery_release.md"
    viewer_pointer_json_path = tmp_path / "active_single_base_delivery_viewer.json"
    viewer_pointer_markdown_path = tmp_path / "active_single_base_delivery_viewer.md"

    with pytest.raises(
        SingleBaseDeliveryReleaseError,
        match="viewer bundle build failed",
    ):
        build_single_base_delivery_release(
            source_run_dir=source_run_dir,
            release_root=tmp_path / "releases",
            release_id="should_fail_on_viewer",
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=tmp_path / "releases" / "release_index.json",
            index_markdown_path=tmp_path / "releases" / "release_index.md",
            viewer_root=tmp_path / "viewers",
            viewer_pointer_json_path=viewer_pointer_json_path,
            viewer_pointer_markdown_path=viewer_pointer_markdown_path,
            viewer_index_json_path=tmp_path / "viewers" / "viewer_index.json",
            viewer_index_markdown_path=tmp_path / "viewers" / "viewer_index.md",
            viewer_candidate_placements_path=tmp_path / "missing_candidate_placements.json",
        )

    assert not (tmp_path / "releases" / "should_fail_on_viewer").exists()
    assert not (tmp_path / "viewers" / "should_fail_on_viewer").exists()
    assert not pointer_json_path.exists()
    assert not pointer_markdown_path.exists()
    assert not viewer_pointer_json_path.exists()
    assert not viewer_pointer_markdown_path.exists()



def test_build_single_base_delivery_release_fails_closed_when_current_landing_cannot_be_built(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)

    pointer_json_path = tmp_path / "active_single_base_delivery_release.json"
    pointer_markdown_path = tmp_path / "active_single_base_delivery_release.md"
    viewer_pointer_json_path = tmp_path / "active_single_base_delivery_viewer.json"
    viewer_pointer_markdown_path = tmp_path / "active_single_base_delivery_viewer.md"
    landing_output_path = tmp_path / "current_delivery_blocker"
    landing_output_path.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryReleaseError,
        match="landing bundle build failed",
    ):
        build_single_base_delivery_release(
            source_run_dir=source_run_dir,
            release_root=tmp_path / "releases",
            release_id="should_fail_on_landing",
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=tmp_path / "releases" / "release_index.json",
            index_markdown_path=tmp_path / "releases" / "release_index.md",
            viewer_root=tmp_path / "viewers",
            viewer_pointer_json_path=viewer_pointer_json_path,
            viewer_pointer_markdown_path=viewer_pointer_markdown_path,
            viewer_index_json_path=tmp_path / "viewers" / "viewer_index.json",
            viewer_index_markdown_path=tmp_path / "viewers" / "viewer_index.md",
            landing_output_dir=landing_output_path,
        )

    assert not (tmp_path / "releases" / "should_fail_on_landing").exists()
    assert not (tmp_path / "viewers" / "should_fail_on_landing").exists()
    assert not pointer_json_path.exists()
    assert not pointer_markdown_path.exists()
    assert not viewer_pointer_json_path.exists()
    assert not viewer_pointer_markdown_path.exists()
    assert landing_output_path.exists()
    assert landing_output_path.is_file()


def test_build_single_base_delivery_release_fails_closed_when_repo_frontdoor_cannot_be_built(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)

    pointer_json_path = tmp_path / "active_single_base_delivery_release.json"
    pointer_markdown_path = tmp_path / "active_single_base_delivery_release.md"
    viewer_pointer_json_path = tmp_path / "active_single_base_delivery_viewer.json"
    viewer_pointer_markdown_path = tmp_path / "active_single_base_delivery_viewer.md"
    landing_output_dir = tmp_path / "current_delivery"
    landing_output_dir.mkdir(parents=True, exist_ok=True)
    marker_path = landing_output_dir / "marker.txt"
    marker_path.write_text("keep me\n", encoding="utf-8")

    frontdoor_output_path = tmp_path / "frontdoor_blocker"
    frontdoor_output_path.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryReleaseError,
        match="frontdoor build failed",
    ):
        build_single_base_delivery_release(
            source_run_dir=source_run_dir,
            release_root=tmp_path / "releases",
            release_id="should_fail_on_frontdoor",
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=tmp_path / "releases" / "release_index.json",
            index_markdown_path=tmp_path / "releases" / "release_index.md",
            viewer_root=tmp_path / "viewers",
            viewer_pointer_json_path=viewer_pointer_json_path,
            viewer_pointer_markdown_path=viewer_pointer_markdown_path,
            viewer_index_json_path=tmp_path / "viewers" / "viewer_index.json",
            viewer_index_markdown_path=tmp_path / "viewers" / "viewer_index.md",
            landing_output_dir=landing_output_dir,
            frontdoor_output_dir=frontdoor_output_path,
        )

    assert not (tmp_path / "releases" / "should_fail_on_frontdoor").exists()
    assert not (tmp_path / "viewers" / "should_fail_on_frontdoor").exists()
    assert not pointer_json_path.exists()
    assert not pointer_markdown_path.exists()
    assert not viewer_pointer_json_path.exists()
    assert not viewer_pointer_markdown_path.exists()
    assert marker_path.exists()
    assert marker_path.read_text(encoding="utf-8") == "keep me\n"
    assert not (landing_output_dir / "index.html").exists()
    assert frontdoor_output_path.exists()
    assert frontdoor_output_path.is_file()


def test_build_single_base_delivery_release_fails_closed_when_active_entrypoints_cannot_be_built(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)

    pointer_json_path = tmp_path / "active_single_base_delivery_release.json"
    pointer_markdown_path = tmp_path / "active_single_base_delivery_release.md"
    viewer_pointer_json_path = tmp_path / "active_single_base_delivery_viewer.json"
    viewer_pointer_markdown_path = tmp_path / "active_single_base_delivery_viewer.md"

    entrypoints_json_blocker = tmp_path / "active_single_base_delivery_entrypoints.json"
    entrypoints_json_blocker.mkdir(parents=True, exist_ok=True)

    with pytest.raises(
        SingleBaseDeliveryReleaseError,
        match="active entrypoints build failed",
    ):
        build_single_base_delivery_release(
            source_run_dir=source_run_dir,
            release_root=tmp_path / "releases",
            release_id="should_fail_on_entrypoints",
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=tmp_path / "releases" / "release_index.json",
            index_markdown_path=tmp_path / "releases" / "release_index.md",
            viewer_root=tmp_path / "viewers",
            viewer_pointer_json_path=viewer_pointer_json_path,
            viewer_pointer_markdown_path=viewer_pointer_markdown_path,
            viewer_index_json_path=tmp_path / "viewers" / "viewer_index.json",
            viewer_index_markdown_path=tmp_path / "viewers" / "viewer_index.md",
            landing_output_dir=tmp_path / "current_delivery",
            frontdoor_output_dir=tmp_path,
            entrypoints_json_path=entrypoints_json_blocker,
            entrypoints_markdown_path=tmp_path / "active_single_base_delivery_entrypoints.md",
        )

    assert not (tmp_path / "releases" / "should_fail_on_entrypoints").exists()
    assert not (tmp_path / "viewers" / "should_fail_on_entrypoints").exists()
    assert not pointer_json_path.exists()
    assert not pointer_markdown_path.exists()
    assert not viewer_pointer_json_path.exists()
    assert not viewer_pointer_markdown_path.exists()
    assert not (tmp_path / "current_delivery").exists()
    assert not (tmp_path / "index.html").exists()
    assert not (tmp_path / "frontdoor_manifest.json").exists()
    assert not (tmp_path / "industrial_planner_latest_single_base_delivery_bundle.zip").exists()
    assert not (tmp_path / "latest_single_base_delivery_bundle.json").exists()
    assert not (tmp_path / "latest_single_base_delivery_bundle.md").exists()
    assert entrypoints_json_blocker.exists()
    assert entrypoints_json_blocker.is_dir()


def test_build_single_base_delivery_release_fails_closed_when_surface_alignment_audit_cannot_be_written(
    tmp_path: Path,
) -> None:
    source_run_dir = _copy_checked_in_delivery_ready_run(tmp_path)

    pointer_json_path = tmp_path / "active_single_base_delivery_release.json"
    pointer_markdown_path = tmp_path / "active_single_base_delivery_release.md"
    viewer_pointer_json_path = tmp_path / "active_single_base_delivery_viewer.json"
    viewer_pointer_markdown_path = tmp_path / "active_single_base_delivery_viewer.md"

    surface_alignment_json_blocker = tmp_path / ".artifacts" / "surface_alignment_summary.json"
    surface_alignment_json_blocker.mkdir(parents=True, exist_ok=True)

    with pytest.raises(
        SingleBaseDeliveryReleaseError,
        match="surface alignment audit failed",
    ):
        build_single_base_delivery_release(
            source_run_dir=source_run_dir,
            release_root=tmp_path / "releases",
            release_id="should_fail_on_surface_alignment_audit",
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=tmp_path / "releases" / "release_index.json",
            index_markdown_path=tmp_path / "releases" / "release_index.md",
            viewer_root=tmp_path / "viewers",
            viewer_pointer_json_path=viewer_pointer_json_path,
            viewer_pointer_markdown_path=viewer_pointer_markdown_path,
            viewer_index_json_path=tmp_path / "viewers" / "viewer_index.json",
            viewer_index_markdown_path=tmp_path / "viewers" / "viewer_index.md",
            landing_output_dir=tmp_path / "current_delivery",
            frontdoor_output_dir=tmp_path,
            surface_alignment_json_path=surface_alignment_json_blocker,
            surface_alignment_markdown_path=tmp_path / ".artifacts" / "surface_alignment_summary.md",
            surface_alignment_console_path=tmp_path / ".artifacts" / "surface_alignment_summary.txt",
        )

    assert not (tmp_path / "releases" / "should_fail_on_surface_alignment_audit").exists()
    assert not (tmp_path / "viewers" / "should_fail_on_surface_alignment_audit").exists()
    assert not pointer_json_path.exists()
    assert not pointer_markdown_path.exists()
    assert not viewer_pointer_json_path.exists()
    assert not viewer_pointer_markdown_path.exists()
    assert not (tmp_path / "current_delivery").exists()
    assert not (tmp_path / "index.html").exists()
    assert not (tmp_path / "frontdoor_manifest.json").exists()
    assert not (tmp_path / "active_single_base_delivery_entrypoints.json").exists()
    assert not (tmp_path / "active_single_base_delivery_entrypoints.md").exists()
    assert surface_alignment_json_blocker.exists()
    assert surface_alignment_json_blocker.is_dir()

"""Tests for the repo-front IndustrialPlanner single-base delivery entry page."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.render.industrial_planner_single_base_delivery_frontdoor import (
    SingleBaseDeliveryFrontdoorError,
    build_single_base_delivery_frontdoor,
)



def test_build_single_base_delivery_frontdoor_writes_index_and_manifest(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "frontdoor"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "active_single_base_delivery_entrypoints.json").write_text("{}\n", encoding="utf-8")
    (output_dir / "active_single_base_delivery_entrypoints.md").write_text("# stub\n", encoding="utf-8")

    result = build_single_base_delivery_frontdoor(
        project_root=Path("."),
        output_dir=output_dir,
        entrypoints_json_path=output_dir / "active_single_base_delivery_entrypoints.json",
        entrypoints_markdown_path=output_dir / "active_single_base_delivery_entrypoints.md",
        require_entrypoints=True,
    )

    assert result.release_id == "valley4_protocol_core_70x70_r20260416"
    assert result.base_id == "valley4_protocol_core"
    assert result.delivery_status == "ready_for_single_base_delivery"
    assert result.quick_download_count == 5
    assert result.download_group_count >= 4
    assert result.exact_full_scale_certified_status == "open"

    index_html_path = output_dir / "index.html"
    manifest_path = output_dir / "frontdoor_manifest.json"
    assert index_html_path.exists()
    assert manifest_path.exists()
    latest_bundle_zip_path = output_dir / "industrial_planner_latest_single_base_delivery_bundle.zip"
    latest_bundle_pointer_json_path = output_dir / "latest_single_base_delivery_bundle.json"
    latest_bundle_pointer_markdown_path = output_dir / "latest_single_base_delivery_bundle.md"
    assert latest_bundle_zip_path.exists()
    assert latest_bundle_pointer_json_path.exists()
    assert latest_bundle_pointer_markdown_path.exists()

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["metadata"]["schema_version"] == "1.6.0"
    assert manifest_payload["current_frontdoor"]["release_id"] == result.release_id
    assert manifest_payload["current_frontdoor"]["current_delivery_index_html"].endswith("current_delivery/index.html")
    assert manifest_payload["current_frontdoor"]["viewer_index_html"].endswith(
        "current_delivery/viewer/index.html"
    )
    assert manifest_payload["current_frontdoor"]["current_bundle_zip"].endswith(
        "current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    )
    assert manifest_payload["current_frontdoor"]["latest_bundle_zip"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert manifest_payload["current_frontdoor"]["latest_bundle_pointer_json"] == "latest_single_base_delivery_bundle.json"
    assert manifest_payload["actions"]["open_current_delivery"].endswith("current_delivery/index.html")
    assert manifest_payload["actions"]["open_viewer"].endswith("current_delivery/viewer/index.html")
    assert manifest_payload["actions"]["download_current_bundle_zip"].endswith(
        "current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    )
    assert manifest_payload["actions"]["download_latest_bundle_zip"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert manifest_payload["actions"]["active_entrypoints_json"] == "active_single_base_delivery_entrypoints.json"
    assert manifest_payload["actions"]["active_entrypoints_markdown"] == "active_single_base_delivery_entrypoints.md"
    assert manifest_payload["actions"]["surface_alignment_summary_json"].endswith("surface_alignment_summary.json")
    assert manifest_payload["actions"]["surface_alignment_summary_markdown"].endswith("surface_alignment_summary.md")
    assert manifest_payload["actions"]["surface_alignment_summary_console"].endswith("surface_alignment_summary.txt")
    assert manifest_payload["actions"]["current_surface_health_json"].endswith("current_surface_health.json")
    assert manifest_payload["actions"]["current_surface_health_markdown"].endswith("current_surface_health.md")
    assert manifest_payload["actions"]["current_surface_health_console"].endswith("current_surface_health.txt")
    assert manifest_payload["actions"]["current_bundle_pointer_json"].endswith(
        "current_delivery/downloads/current_single_base_delivery_bundle.json"
    )
    assert manifest_payload["actions"]["latest_bundle_pointer_json"] == "latest_single_base_delivery_bundle.json"
    assert manifest_payload["script_entrypoints"]["json"] == "active_single_base_delivery_entrypoints.json"
    assert manifest_payload["script_entrypoints"]["markdown"] == "active_single_base_delivery_entrypoints.md"
    assert manifest_payload["surface_alignment"]["status"] == "clean"
    assert manifest_payload["surface_alignment"]["drift_check_count"] == 0
    assert manifest_payload["surface_health"]["status"] == "clean"
    assert manifest_payload["surface_health"]["drift_check_count"] == 0
    assert manifest_payload["current_frontdoor"]["current_surface_health_json"].endswith("current_surface_health.json")
    assert manifest_payload["current_frontdoor"]["surface_health_status"] == "clean"
    assert manifest_payload["linked_assets"]["active_entrypoints_json"] == "active_single_base_delivery_entrypoints.json"
    assert manifest_payload["linked_assets"]["surface_alignment_summary_json"].endswith("surface_alignment_summary.json")
    assert manifest_payload["linked_assets"]["current_surface_health_json"].endswith("current_surface_health.json")
    assert manifest_payload["exact_full_scale_certified"]["status"] == "open"
    assert len(manifest_payload["quick_downloads"]) == result.quick_download_count
    assert any(
        item["href"].endswith("current_delivery/viewer/downloads/release/bundle/industrial_planner.blueprint.json")
        for item in manifest_payload["quick_downloads"]
    )
    assert any(group["group_id"] == "metadata" for group in manifest_payload["download_groups"])
    latest_bundle_pointer_payload = json.loads(latest_bundle_pointer_json_path.read_text(encoding="utf-8"))
    assert latest_bundle_pointer_payload["current_bundle"]["bundle_zip"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert latest_bundle_pointer_payload["current_bundle"]["source_current_bundle_zip"].endswith(
        "current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    )

    browse_first = manifest_payload["entry_modes"]["browse_first"]
    download_first = manifest_payload["entry_modes"]["download_first"]
    assert browse_first["primary_action"]["href"].endswith("current_delivery/viewer/index.html")
    assert any(
        action["href"].endswith("current_delivery/index.html")
        for action in browse_first["secondary_actions"]
    )
    assert download_first["primary_action"]["href"] == "industrial_planner_latest_single_base_delivery_bundle.zip"
    assert any(
        action["href"].endswith("current_delivery/viewer/downloads/meta/SHA256SUMS.txt")
        for action in download_first["secondary_actions"]
    )
    assert any(
        action["href"] == "latest_single_base_delivery_bundle.json"
        for action in download_first["secondary_actions"]
    )

    html = index_html_path.read_text(encoding="utf-8")
    assert "Active entrypoints JSON" in html
    assert "Surface alignment JSON" in html
    assert "Current surface health JSON" in html
    assert "Surface health" in html
    assert "Surface audit" in html
    assert "Automation tip" in html
    assert "Browse first" in html
    assert "Download first" in html
    assert "Download latest bundle ZIP" in html
    assert "Open interactive viewer" in html



def test_build_single_base_delivery_frontdoor_can_fail_closed_when_surface_alignment_is_required_but_missing(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "frontdoor"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "active_single_base_delivery_entrypoints.json").write_text("{}\n", encoding="utf-8")
    (output_dir / "active_single_base_delivery_entrypoints.md").write_text("# stub\n", encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryFrontdoorError,
        match="surface-alignment JSON/Markdown/TXT",
    ):
        build_single_base_delivery_frontdoor(
            project_root=Path("."),
            output_dir=output_dir,
            entrypoints_json_path=output_dir / "active_single_base_delivery_entrypoints.json",
            entrypoints_markdown_path=output_dir / "active_single_base_delivery_entrypoints.md",
            require_entrypoints=True,
            surface_alignment_json_path=tmp_path / ".artifacts" / "surface_alignment_summary.json",
            surface_alignment_markdown_path=tmp_path / ".artifacts" / "surface_alignment_summary.md",
            surface_alignment_console_path=tmp_path / ".artifacts" / "surface_alignment_summary.txt",
            require_surface_alignment=True,
        )



def test_build_single_base_delivery_frontdoor_can_fail_closed_when_entrypoints_are_required_but_missing(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "frontdoor"

    with pytest.raises(
        SingleBaseDeliveryFrontdoorError,
        match="require active entrypoints JSON and Markdown",
    ):
        build_single_base_delivery_frontdoor(
            project_root=Path("."),
            output_dir=output_dir,
            entrypoints_json_path=output_dir / "active_single_base_delivery_entrypoints.json",
            entrypoints_markdown_path=output_dir / "active_single_base_delivery_entrypoints.md",
            require_entrypoints=True,
        )



def test_build_single_base_delivery_frontdoor_fails_closed_when_landing_manifest_has_no_current_landing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    landing_dir = project_root / "current_delivery"
    landing_dir.mkdir(parents=True, exist_ok=True)
    (landing_dir / "index.html").write_text("stub\n", encoding="utf-8")
    landing_manifest_path = landing_dir / "landing_manifest.json"
    landing_manifest_path.write_text(json.dumps({"metadata": {"schema_version": "1.0.0"}}), encoding="utf-8")

    with pytest.raises(
        SingleBaseDeliveryFrontdoorError,
        match="current_landing",
    ):
        build_single_base_delivery_frontdoor(
            project_root=project_root,
            landing_manifest_json_path=landing_manifest_path,
            output_dir=project_root / "frontdoor",
        )



def test_build_single_base_delivery_frontdoor_fails_closed_when_landing_manifest_lacks_dual_entry_actions(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    landing_dir = project_root / "current_delivery"
    landing_dir.mkdir(parents=True, exist_ok=True)
    (landing_dir / "index.html").write_text("stub\n", encoding="utf-8")
    landing_manifest_path = landing_dir / "landing_manifest.json"
    landing_manifest_path.write_text(
        json.dumps(
            {
                "metadata": {"schema_version": "1.0.0"},
                "current_landing": {
                    "release_id": "demo_release",
                    "base_id": "valley4_protocol_core",
                    "lot_size": 70,
                    "delivery_status": "ready_for_single_base_delivery",
                    "scope_note": "single-base only",
                },
                "current_release": {
                    "release_id": "demo_release",
                    "base_id": "valley4_protocol_core",
                    "lot_size": 70,
                    "delivery_status": "ready_for_single_base_delivery",
                    "scope_note": "single-base only",
                },
                "exact_full_scale_certified": {
                    "status": "open",
                    "note": "still open",
                },
                "actions": {
                    "landing_manifest_json": "landing_manifest.json",
                },
                "quick_downloads": [],
                "download_groups": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        SingleBaseDeliveryFrontdoorError,
        match="actions.open_viewer|actions.download_current_bundle_zip|actions.blueprint|download-first entry",
    ):
        build_single_base_delivery_frontdoor(
            project_root=project_root,
            landing_manifest_json_path=landing_manifest_path,
            output_dir=project_root / "frontdoor",
        )



def test_build_single_base_delivery_frontdoor_fails_closed_when_current_bundle_zip_source_is_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    landing_dir = project_root / "current_delivery"
    downloads_dir = landing_dir / "downloads"
    landing_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    (landing_dir / "index.html").write_text("stub\n", encoding="utf-8")
    (downloads_dir / "current_single_base_delivery_bundle.json").write_text("{}\n", encoding="utf-8")
    (downloads_dir / "current_single_base_delivery_bundle.md").write_text("# stub\n", encoding="utf-8")

    landing_manifest_path = landing_dir / "landing_manifest.json"
    landing_manifest_path.write_text(
        json.dumps(
            {
                "metadata": {"schema_version": "1.1.0"},
                "current_landing": {
                    "release_id": "demo_release",
                    "base_id": "valley4_protocol_core",
                    "lot_size": 70,
                    "delivery_status": "ready_for_single_base_delivery",
                    "scope_note": "single-base only",
                    "selected_facility_type_count": 1,
                    "selected_pose_count": 2,
                    "payload_download_count": 1,
                    "metadata_download_count": 1,
                },
                "current_release": {
                    "release_id": "demo_release",
                    "base_id": "valley4_protocol_core",
                    "lot_size": 70,
                    "delivery_status": "ready_for_single_base_delivery",
                    "scope_note": "single-base only",
                },
                "exact_full_scale_certified": {
                    "status": "open",
                    "note": "still open",
                },
                "actions": {
                    "open_viewer": "viewer/index.html",
                    "viewer_manifest_json": "viewer/release_viewer_manifest.json",
                    "landing_manifest_json": "landing_manifest.json",
                    "download_current_bundle_zip": "downloads/industrial_planner_current_single_base_delivery_bundle.zip",
                    "current_bundle_pointer_json": "downloads/current_single_base_delivery_bundle.json",
                    "current_bundle_pointer_markdown": "downloads/current_single_base_delivery_bundle.md",
                    "blueprint": "viewer/downloads/release/bundle/industrial_planner.blueprint.json",
                    "validation_report": "viewer/downloads/release/bundle/validation_report.json",
                    "throughput_report": "viewer/downloads/release/bundle/throughput_report.json",
                    "run_summary": "viewer/downloads/release/run_summary.json",
                    "release_manifest_json": "viewer/downloads/meta/release_manifest.json",
                    "sha256sums": "viewer/downloads/meta/SHA256SUMS.txt",
                },
                "quick_downloads": [
                    {
                        "id": "industrial_planner_blueprint",
                        "label": "Blueprint",
                        "href": "viewer/downloads/release/bundle/industrial_planner.blueprint.json",
                        "kind": "json",
                        "stage": "export",
                        "required_for_delivery": True,
                        "role": "bp",
                    }
                ],
                "download_groups": [
                    {
                        "group_id": "metadata",
                        "title": "Metadata",
                        "description": "desc",
                        "entries": [
                            {
                                "label": "Release manifest JSON",
                                "href": "viewer/downloads/meta/release_manifest.json",
                                "kind": "json",
                                "stage": "metadata",
                                "required_for_delivery": False,
                                "role": "meta",
                            }
                        ],
                    }
                ],
                "current_bundle_archive": {
                    "archive_sha256": "abc",
                    "archive_size_bytes": 1,
                    "payload_file_count": 1,
                    "metadata_file_count": 1,
                    "included_entry_count": 2,
                    "archive_root": "industrial_planner_current_single_base_delivery_bundle",
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SingleBaseDeliveryFrontdoorError,
        match="source ZIP is missing",
    ):
        build_single_base_delivery_frontdoor(
            project_root=project_root,
            landing_manifest_json_path=landing_manifest_path,
            output_dir=project_root / "frontdoor",
        )

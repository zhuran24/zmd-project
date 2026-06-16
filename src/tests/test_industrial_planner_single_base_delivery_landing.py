"""Tests for the stable IndustrialPlanner single-base current landing bundle builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.render.industrial_planner_single_base_delivery_landing import (
    SingleBaseDeliveryLandingBundleError,
    build_single_base_delivery_landing_bundle,
)



def test_build_single_base_delivery_landing_bundle_materializes_current_viewer(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "current_delivery"
    active_viewer_pointer = json.loads(
        Path("data/examples/industrial_planner/active_single_base_delivery_viewer.json").read_text(encoding="utf-8")
    )
    current_viewer = active_viewer_pointer["current_viewer"]

    result = build_single_base_delivery_landing_bundle(
        project_root=Path("."),
        output_dir=output_dir,
    )

    assert result.release_id == current_viewer["release_id"]
    assert result.base_id == current_viewer["base_id"]
    assert result.delivery_status == current_viewer["delivery_status"]
    assert result.quick_download_count == current_viewer["quick_download_count"]
    assert result.download_group_count >= 4
    assert result.exact_full_scale_certified_status == "open"

    assert (output_dir / "index.html").exists()
    assert (output_dir / "landing_manifest.json").exists()
    assert (output_dir / "viewer" / "index.html").exists()
    assert (output_dir / "viewer" / "release_viewer_manifest.json").exists()
    assert (output_dir / "viewer" / "downloads" / "release" / "bundle" / "industrial_planner.blueprint.json").exists()
    assert (output_dir / "downloads" / "industrial_planner_current_single_base_delivery_bundle.zip").exists()
    assert (output_dir / "downloads" / "current_single_base_delivery_bundle.json").exists()
    assert (output_dir / "downloads" / "current_single_base_delivery_bundle.md").exists()

    manifest_payload = json.loads((output_dir / "landing_manifest.json").read_text(encoding="utf-8"))
    assert manifest_payload["current_landing"]["release_id"] == result.release_id
    assert manifest_payload["current_landing"]["viewer_index_html"] == "viewer/index.html"
    assert manifest_payload["current_landing"]["current_bundle_zip"] == "downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    assert manifest_payload["current_release"]["delivery_status"] == result.delivery_status
    assert manifest_payload["exact_full_scale_certified"]["status"] == "open"
    assert manifest_payload["actions"]["open_viewer"] == "viewer/index.html"
    assert manifest_payload["actions"]["download_current_bundle_zip"] == "downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    assert manifest_payload["current_bundle_archive"]["bundle_zip"] == "downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    assert manifest_payload["current_bundle_archive"]["included_entry_count"] >= 2
    assert len(manifest_payload["quick_downloads"]) == result.quick_download_count
    assert any(
        item["href"].startswith("viewer/downloads/release/bundle/")
        for item in manifest_payload["quick_downloads"]
    )
    assert any(group["group_id"] == "metadata" for group in manifest_payload["download_groups"])
    assert any(
        entry["href"].startswith("viewer/downloads/meta/")
        for group in manifest_payload["download_groups"]
        for entry in group["entries"]
    )



def test_build_single_base_delivery_landing_bundle_fails_closed_when_pointer_lacks_viewer_manifest(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    pointer_json_path = project_root / "active_single_base_delivery_viewer.json"
    pointer_json_path.write_text(
        json.dumps(
            {
                "current_viewer": {
                    "release_id": "broken_release",
                    "viewer_dir": "missing_viewer_dir",
                }
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SingleBaseDeliveryLandingBundleError,
        match="viewer_manifest_json",
    ):
        build_single_base_delivery_landing_bundle(
            project_root=project_root,
            viewer_pointer_json_path=pointer_json_path,
            output_dir=project_root / "current_delivery",
        )


def test_build_single_base_delivery_landing_bundle_uses_repo_relative_paths_for_repo_local_outputs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    viewer_dir = project_root / "viewers" / "current"
    downloads_dir = viewer_dir / "downloads" / "release" / "bundle"
    meta_dir = viewer_dir / "downloads" / "meta"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    (downloads_dir / "industrial_planner.blueprint.json").write_text("{}\n", encoding="utf-8")
    (meta_dir / "release_manifest.json").write_text("{}\n", encoding="utf-8")
    (viewer_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")

    viewer_manifest_path = viewer_dir / "release_viewer_manifest.json"
    viewer_manifest_path.write_text(
        json.dumps(
            {
                "current_release": {
                    "release_id": "r1",
                    "base_id": "valley4_protocol_core",
                    "lot_size": 70,
                    "delivery_status": "ready_for_single_base_delivery",
                    "scope_note": "scope note",
                    "release_dir": "releases/r1",
                },
                "exact_full_scale_certified": {
                    "status": "open",
                    "note": "exact note",
                },
                "viewer_bundle": {
                    "selected_facility_type_count": 1,
                    "selected_pose_count": 2,
                },
                "quick_downloads": [
                    {
                        "id": "industrial_planner_blueprint",
                        "label": "Blueprint",
                        "href": "downloads/release/bundle/industrial_planner.blueprint.json",
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
                                "href": "downloads/meta/release_manifest.json",
                                "kind": "json",
                                "stage": "metadata",
                                "required_for_delivery": False,
                                "role": "meta",
                            }
                        ],
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    pointer_json_path = project_root / "pointers" / "active_single_base_delivery_viewer.json"
    pointer_json_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_json_path.write_text(
        json.dumps(
            {
                "current_viewer": {
                    "release_id": "r1",
                    "base_id": "valley4_protocol_core",
                    "lot_size": 70,
                    "delivery_status": "ready_for_single_base_delivery",
                    "viewer_dir": "viewers/current",
                    "viewer_manifest_json": "viewers/current/release_viewer_manifest.json",
                    "selected_facility_type_count": 1,
                    "selected_pose_count": 2,
                    "payload_download_count": 1,
                    "metadata_download_count": 1,
                    "scope_note": "scope note",
                }
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = Path("current_delivery")
    result = build_single_base_delivery_landing_bundle(
        project_root=project_root,
        viewer_pointer_json_path=Path("pointers/active_single_base_delivery_viewer.json"),
        output_dir=output_dir,
    )

    manifest_payload = json.loads(result.landing_manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["current_landing"]["output_dir"] == "current_delivery"
    assert manifest_payload["current_landing"]["current_bundle_zip"] == "downloads/industrial_planner_current_single_base_delivery_bundle.zip"
    assert manifest_payload["current_bundle_archive"]["pointer_json"] == "downloads/current_single_base_delivery_bundle.json"
    assert manifest_payload["current_bundle_archive"]["source_viewer_downloads_root"] == "viewer/downloads"
    assert (
        manifest_payload["current_landing"]["source_viewer_pointer_json"]
        == "pointers/active_single_base_delivery_viewer.json"
    )
    assert manifest_payload["current_landing"]["source_viewer_dir"] == "viewers/current"
    assert (
        manifest_payload["viewer_copy"]["viewer_source_manifest"]
        == "viewers/current/release_viewer_manifest.json"
    )

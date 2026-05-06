"""Tests for the active IndustrialPlanner single-base delivery viewer bundle builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.render.industrial_planner_single_base_delivery_viewer import (
    SingleBaseDeliveryViewerBundleError,
    build_single_base_delivery_viewer_bundle,
)



def test_build_single_base_delivery_viewer_bundle_materializes_current_release(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "viewer"
    active_pointer_payload = json.loads(
        Path("data/examples/industrial_planner/active_single_base_delivery_release.json").read_text(encoding="utf-8")
    )
    current_release = active_pointer_payload["current_release"]

    result = build_single_base_delivery_viewer_bundle(
        project_root=Path("."),
        output_dir=output_dir,
    )

    assert result.release_id == current_release["release_id"]
    assert result.base_id == current_release["base_id"]
    assert result.delivery_status == current_release["delivery_status"]
    assert result.payload_download_count == 24
    assert result.metadata_download_count >= 5
    assert result.quick_download_count == 5
    assert result.exact_full_scale_certified_status == "open"

    assert (output_dir / "index.html").exists()
    assert (output_dir / "optimal_blueprint.json").exists()
    assert (output_dir / "candidate_placements.json").exists()
    assert (output_dir / "final_solution.json").exists()
    assert (output_dir / "viewer_report.json").exists()
    assert (output_dir / "release_viewer_manifest.json").exists()
    assert (output_dir / "downloads" / "release" / "bundle" / "industrial_planner.blueprint.json").exists()
    assert (output_dir / "downloads" / "meta" / "release_manifest.json").exists()
    assert (output_dir / "downloads" / "meta" / "SHA256SUMS.txt").exists()

    viewer_manifest = json.loads((output_dir / "release_viewer_manifest.json").read_text(encoding="utf-8"))
    assert viewer_manifest["current_release"]["release_id"] == result.release_id
    assert viewer_manifest["current_release"]["base_id"] == result.base_id
    assert viewer_manifest["current_release"]["delivery_status"] == result.delivery_status
    assert viewer_manifest["exact_full_scale_certified"]["status"] == "open"
    assert viewer_manifest["viewer_bundle"]["selected_facility_type_count"] == result.selected_facility_type_count
    assert viewer_manifest["viewer_bundle"]["selected_pose_count"] == result.selected_pose_count
    assert any(group["group_id"] == "delivery_entrypoints" for group in viewer_manifest["download_groups"])
    assert any(group["group_id"] == "metadata" for group in viewer_manifest["download_groups"])
    assert any(
        item["href"].endswith("downloads/release/bundle/industrial_planner.blueprint.json")
        for item in viewer_manifest["quick_downloads"]
    )

    blueprint_payload = json.loads((output_dir / "optimal_blueprint.json").read_text(encoding="utf-8"))
    facility_types = {str(facility["facility_type"]) for facility in blueprint_payload["facilities"]}
    viewer_pools_payload = json.loads((output_dir / "candidate_placements.json").read_text(encoding="utf-8"))
    assert set(viewer_pools_payload["facility_pools"].keys()) == facility_types
    assert (output_dir / "candidate_placements.json").stat().st_size < Path(
        "data/preprocessed/candidate_placements.json"
    ).stat().st_size



def test_build_single_base_delivery_viewer_bundle_fails_closed_when_pointer_lacks_release_manifest(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    (project_root / "candidate_placements.json").write_text("{}\n", encoding="utf-8")
    (project_root / "rules.json").write_text("{}\n", encoding="utf-8")
    (project_root / "viewer.html").write_text("<html></html>\n", encoding="utf-8")

    pointer_json_path = project_root / "active_single_base_delivery_release.json"
    pointer_json_path.write_text(
        json.dumps(
            {
                "current_release": {
                    "release_id": "broken_release",
                }
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SingleBaseDeliveryViewerBundleError,
        match="release_manifest_json",
    ):
        build_single_base_delivery_viewer_bundle(
            project_root=project_root,
            pointer_json_path=pointer_json_path,
            output_dir=project_root / "viewer",
            candidate_placements_path=Path("candidate_placements.json"),
            rules_json_path=Path("rules.json"),
            viewer_html_path=Path("viewer.html"),
        )

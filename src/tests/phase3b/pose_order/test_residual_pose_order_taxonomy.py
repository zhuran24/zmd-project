from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.pose_order.residual_pose_order_taxonomy import (
    build_phase3b_residual_pose_order_taxonomy,
    render_phase3b_residual_pose_order_taxonomy_markdown,
    render_phase3b_residual_pose_order_taxonomy_text,
)


TARGET_GROUP = "group::manufacturing_5x5::planter_buckwheat::9"


def test_residual_pose_order_taxonomy_classifies_ordering_sensitive(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_anchor_artifacts(artifact_root, 159)

    report = build_phase3b_residual_pose_order_taxonomy(
        tmp_path,
        anchors=[159],
        artifact_root=artifact_root,
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "stable_ordering_sensitive_class_observed"
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["anchors"][0]["taxonomy_class"] == (
        "planter_buckwheat_xy_ordering_sensitive_diagnostic"
    )
    assert report["anchors"][0]["target_field_status"] == "INFEASIBLE"


def test_residual_pose_order_taxonomy_reports_missing_artifacts(tmp_path: Path) -> None:
    report = build_phase3b_residual_pose_order_taxonomy(tmp_path, anchors=[229])

    assert report["status"]["outcome"] == "all_artifacts_missing"
    assert report["status"]["artifact_missing_count"] == 1
    assert report["anchors"][0]["taxonomy_class"] == "missing_artifacts"
    assert report["anchors"][0]["artifact_status"]["group_delta"] == "missing"


def test_residual_pose_order_taxonomy_classifies_non_target_first_group(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_json(
        artifact_root
        / "phase3b_coordinate_validation_group_delta_anchor172"
        / "coordinate_validation_group_delta_anchor172.json",
        {
            "status": {"outcome": "coordinate_validation_delta_infeasible_found"},
            "delta": {
                "first_narrower_infeasible_entry": {
                    "case_id": (
                        "ghost_plus_each_group:"
                        "group::manufacturing_5x5::planter_sandleaf::10"
                    ),
                    "included_group_ids": [
                        "group::manufacturing_5x5::planter_sandleaf::10"
                    ],
                }
            },
        },
    )

    report = build_phase3b_residual_pose_order_taxonomy(
        tmp_path,
        anchors=[172],
        artifact_root=artifact_root,
    )

    assert report["anchors"][0]["taxonomy_class"] == (
        "non_target_first_group_delta_diagnostic"
    )
    assert report["anchors"][0]["group_first_infeasible_group_ids"] == [
        "group::manufacturing_5x5::planter_sandleaf::10"
    ]


def test_residual_pose_order_taxonomy_classifies_non_target_ordering_sensitive(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_json(
        artifact_root
        / "phase3b_coordinate_validation_group_delta_anchor172"
        / "coordinate_validation_group_delta_anchor172.json",
        {
            "status": {"outcome": "coordinate_validation_delta_infeasible_found"},
            "delta": {
                "first_narrower_infeasible_entry": {
                    "case_id": (
                        "ghost_plus_each_group:"
                        "group::manufacturing_5x5::planter_sandleaf::10"
                    ),
                    "included_group_ids": [
                        "group::manufacturing_5x5::planter_sandleaf::10"
                    ],
                }
            },
        },
    )
    _write_json(
        artifact_root
        / "phase3b_coordinate_validation_field_channel_delta_anchor172_planter_sandleaf_ghost_labels"
        / "field_channel_delta_anchor172_planter_sandleaf_ghost_labels.json",
        {
            "field_channel_delta": {
                "entries": [
                    {
                        "field_variant": "x_y",
                        "validation": {"status": "INFEASIBLE"},
                    }
                ]
            }
        },
    )
    _write_json(
        artifact_root
        / "phase3b_greedy_pose_order_comparison_anchor172_planter_sandleaf_xy"
        / "greedy_pose_order_comparison_anchor172_planter_sandleaf_xy.json",
        {"status": {"outcome": "ordering_sensitive_infeasible"}},
    )

    report = build_phase3b_residual_pose_order_taxonomy(
        tmp_path,
        anchors=[172],
        artifact_root=artifact_root,
    )

    assert report["anchors"][0]["taxonomy_class"] == (
        "non_target_first_group_ordering_sensitive_diagnostic"
    )
    assert report["anchors"][0]["first_group_field_status"] == "INFEASIBLE"
    assert report["anchors"][0]["first_group_greedy_outcome"] == (
        "ordering_sensitive_infeasible"
    )


def test_residual_pose_order_taxonomy_renders_text_outputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_anchor_artifacts(artifact_root, 171)
    report = build_phase3b_residual_pose_order_taxonomy(
        tmp_path,
        anchors=[171],
        artifact_root=artifact_root,
    )

    markdown = render_phase3b_residual_pose_order_taxonomy_markdown(report)
    text = render_phase3b_residual_pose_order_taxonomy_text(report)

    assert "Runtime promotion ready" in markdown
    assert "planter_buckwheat_xy_ordering_sensitive_diagnostic" in markdown
    assert "runtime_promotion_ready=False" in text


def test_residual_pose_order_taxonomy_cli_no_write(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_anchor_artifacts(artifact_root, 217)
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/pose_order/build_residual_pose_order_taxonomy.py",
            "--project-root",
            str(tmp_path),
            "--artifact-root",
            str(artifact_root),
            "--anchors",
            "217",
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b residual pose-order taxonomy" in completed.stdout
    assert not output_dir.exists()


def test_residual_pose_order_taxonomy_cli_writes_outputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_anchor_artifacts(artifact_root, 217)
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/pose_order/build_residual_pose_order_taxonomy.py",
            "--project-root",
            str(tmp_path),
            "--artifact-root",
            str(artifact_root),
            "--anchors",
            "217",
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "residual_pose_order_taxonomy.json").exists()
    assert (output_dir / "residual_pose_order_taxonomy.md").exists()
    assert (output_dir / "residual_pose_order_taxonomy.txt").exists()


def _write_anchor_artifacts(artifact_root: Path, anchor_idx: int) -> None:
    group_path = (
        artifact_root
        / f"phase3b_coordinate_validation_group_delta_anchor{anchor_idx}"
        / f"coordinate_validation_group_delta_anchor{anchor_idx}.json"
    )
    field_path = (
        artifact_root
        / f"phase3b_coordinate_validation_field_channel_delta_anchor{anchor_idx}_planter_buckwheat_ghost_labels"
        / f"field_channel_delta_anchor{anchor_idx}_planter_buckwheat_ghost_labels.json"
    )
    greedy_path = (
        artifact_root
        / f"phase3b_greedy_pose_order_comparison_anchor{anchor_idx}_planter_buckwheat_xy"
        / f"greedy_pose_order_comparison_anchor{anchor_idx}_planter_buckwheat_xy.json"
    )
    _write_json(group_path, _group_report(anchor_idx))
    _write_json(field_path, _field_report(anchor_idx))
    _write_json(greedy_path, _greedy_report(anchor_idx))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _group_report(anchor_idx: int) -> dict:
    return {
        "status": {"outcome": "coordinate_validation_delta_infeasible_found"},
        "delta": {
            "first_narrower_infeasible_entry": {
                "case_id": f"ghost_plus_each_group:{TARGET_GROUP}",
                "included_group_ids": [TARGET_GROUP],
            }
        },
    }


def _field_report(anchor_idx: int) -> dict:
    return {
        "status": {"outcome": "field_channel_infeasible_found"},
        "field_channel_delta": {
            "entries": [
                {
                    "field_variant": "x",
                    "validation": {"status": "UNKNOWN"},
                },
                {
                    "field_variant": "y",
                    "validation": {"status": "UNKNOWN"},
                },
                {
                    "field_variant": "x_y",
                    "group_id": TARGET_GROUP,
                    "validation": {"status": "INFEASIBLE"},
                },
            ]
        },
    }


def _greedy_report(anchor_idx: int) -> dict:
    return {
        "status": {"outcome": "ordering_sensitive_infeasible"},
        "comparison": {
            "single_group_blocked_vs_full_blocked": {
                "pose_intersection_count": 0,
                "label_intersection_count": 0,
            },
            "entries": [
                {
                    "strategy": "single_group_blocked",
                    "target_validation": {"status": "INFEASIBLE"},
                },
                {
                    "strategy": "full_blocked",
                    "target_validation": {"status": "UNKNOWN"},
                },
            ],
        },
    }

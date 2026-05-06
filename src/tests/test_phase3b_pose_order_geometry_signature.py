from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_pose_order_geometry_signature import (
    build_phase3b_pose_order_geometry_signature,
    render_phase3b_pose_order_geometry_signature_markdown,
)


BUCKWHEAT = "group::manufacturing_5x5::planter_buckwheat::9"
SANDLEAF = "group::manufacturing_5x5::planter_sandleaf::10"


def test_pose_order_geometry_signature_summarizes_buckwheat_anchor(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_taxonomy_inputs(artifact_root, 159, BUCKWHEAT, target=True)
    _write_greedy_artifact(artifact_root, 159, "planter_buckwheat", [0, 0, 0], [1, 6, 11])

    report = build_phase3b_pose_order_geometry_signature(
        tmp_path,
        anchors=[159],
        artifact_root=artifact_root,
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "geometry_signature_complete"
    assert report["status"]["runtime_promotion_ready"] is False
    anchor = report["anchors"][0]
    assert anchor["status_pattern"] == "single_group_blocked=INFEASIBLE"
    assert anchor["strategies"][0]["geometry"]["dominant_axis"] == "vertical_or_few_x_strip"
    assert anchor["strategies"][0]["geometry"]["normalized_dx_dy_mode"][1]["dy"] == 5
    assert anchor["strategies"][0]["geometry"]["sequence_fingerprint"]


def test_pose_order_geometry_signature_handles_non_target_followup(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_taxonomy_inputs(artifact_root, 172, SANDLEAF, target=False)
    _write_greedy_artifact(artifact_root, 172, "planter_sandleaf", [0, 5, 10], [1, 1, 1])

    report = build_phase3b_pose_order_geometry_signature(
        tmp_path,
        anchors=[172],
        artifact_root=artifact_root,
    )

    anchor = report["anchors"][0]
    assert anchor["taxonomy_class"] == "non_target_first_group_ordering_sensitive_diagnostic"
    assert anchor["greedy_artifact_status"] == "present"
    assert anchor["strategies"][0]["geometry"]["dominant_axis"] == "horizontal_or_few_y_strip"
    summary = report["class_summary"]["non_target_first_group_ordering_sensitive_diagnostic"]
    assert summary["dominant_axis_counts_by_status"]["INFEASIBLE"] == {
        "horizontal_or_few_y_strip": 1
    }


def test_pose_order_geometry_signature_cli_no_write(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_taxonomy_inputs(artifact_root, 159, BUCKWHEAT, target=True)
    _write_greedy_artifact(artifact_root, 159, "planter_buckwheat", [0, 0, 0], [1, 6, 11])
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_pose_order_geometry_signature.py",
            "--project-root",
            str(tmp_path),
            "--artifact-root",
            str(artifact_root),
            "--anchors",
            "159",
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b pose-order geometry signature" in completed.stdout
    assert not output_dir.exists()


def test_pose_order_geometry_signature_cli_writes_outputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_taxonomy_inputs(artifact_root, 159, BUCKWHEAT, target=True)
    _write_greedy_artifact(artifact_root, 159, "planter_buckwheat", [0, 0, 0], [1, 6, 11])
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_pose_order_geometry_signature.py",
            "--project-root",
            str(tmp_path),
            "--artifact-root",
            str(artifact_root),
            "--anchors",
            "159",
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "pose_order_geometry_signature.json").exists()
    assert (output_dir / "pose_order_geometry_signature.md").exists()
    assert (output_dir / "pose_order_geometry_signature.txt").exists()


def test_pose_order_geometry_signature_renders_markdown(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".artifacts"
    _write_taxonomy_inputs(artifact_root, 159, BUCKWHEAT, target=True)
    _write_greedy_artifact(artifact_root, 159, "planter_buckwheat", [0, 0, 0], [1, 6, 11])
    report = build_phase3b_pose_order_geometry_signature(
        tmp_path,
        anchors=[159],
        artifact_root=artifact_root,
    )

    markdown = render_phase3b_pose_order_geometry_signature_markdown(report)

    assert "Runtime promotion ready" in markdown
    assert "vertical_or_few_x_strip" in markdown


def _write_taxonomy_inputs(
    artifact_root: Path,
    anchor_idx: int,
    group_id: str,
    *,
    target: bool,
) -> None:
    group_path = (
        artifact_root
        / f"phase3b_coordinate_validation_group_delta_anchor{anchor_idx}"
        / f"coordinate_validation_group_delta_anchor{anchor_idx}.json"
    )
    group_report = {
        "status": {"outcome": "coordinate_validation_delta_infeasible_found"},
        "delta": {
            "first_narrower_infeasible_entry": {
                "case_id": f"ghost_plus_each_group:{group_id}",
                "included_group_ids": [group_id],
            }
        },
    }
    _write_json(group_path, group_report)
    if target:
        field_path = (
            artifact_root
            / f"phase3b_coordinate_validation_field_channel_delta_anchor{anchor_idx}_planter_buckwheat_ghost_labels"
            / f"field_channel_delta_anchor{anchor_idx}_planter_buckwheat_ghost_labels.json"
        )
    else:
        field_path = (
            artifact_root
            / f"phase3b_coordinate_validation_field_channel_delta_anchor{anchor_idx}_planter_sandleaf_ghost_labels"
            / f"field_channel_delta_anchor{anchor_idx}_planter_sandleaf_ghost_labels.json"
        )
    _write_json(
        field_path,
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


def _write_greedy_artifact(
    artifact_root: Path,
    anchor_idx: int,
    slug: str,
    xs: list[int],
    ys: list[int],
) -> None:
    greedy_path = (
        artifact_root
        / f"phase3b_greedy_pose_order_comparison_anchor{anchor_idx}_{slug}_xy"
        / f"greedy_pose_order_comparison_anchor{anchor_idx}_{slug}_xy.json"
    )
    labels = []
    for index, (x_value, y_value) in enumerate(zip(xs, ys)):
        labels.append(
            {
                "slot_index": index,
                "slot_key": str(index),
                "solution_id": f"item_{index}",
                "pose_index": index,
                "field": "x",
                "forced_value": x_value,
            }
        )
        labels.append(
            {
                "slot_index": index,
                "slot_key": str(index),
                "solution_id": f"item_{index}",
                "pose_index": index,
                "field": "y",
                "forced_value": y_value,
            }
        )
    _write_json(
        greedy_path,
        {
            "status": {"outcome": "ordering_sensitive_infeasible"},
            "comparison": {
                "entries": [
                    {
                        "strategy": "single_group_blocked",
                        "target_pose_indices": list(range(len(xs))),
                        "target_validation": {
                            "status": "INFEASIBLE",
                            "forced_slot_field_count": len(labels),
                            "force_equality_labels": labels,
                        },
                    }
                ]
            },
        },
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

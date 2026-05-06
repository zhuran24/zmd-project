from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_pose_order_unknown_resolution import (
    build_phase3b_pose_order_unknown_resolution,
)


def test_pose_order_unknown_resolution_reports_prefix_infeasible(tmp_path: Path) -> None:
    _write_comparison(tmp_path, [130, 131])
    _write_probe(tmp_path, 130, "prefix_infeasible")
    _write_probe(tmp_path, 131, "prefix_infeasible")

    report = build_phase3b_pose_order_unknown_resolution(tmp_path)

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "portfolio_unknowns_resolved_as_prefix_infeasible"
    assert [entry["anchor_idx"] for entry in report["probe_reports"]] == [130, 131]
    assert {entry["first_infeasible_group_id"] for entry in report["probe_reports"]} == {
        "group::protocol_core::protocol_core::18"
    }
    assert report["status"]["runtime_promotion_ready"] is False


def test_pose_order_unknown_resolution_missing_probe(tmp_path: Path) -> None:
    _write_comparison(tmp_path, [130])

    report = build_phase3b_pose_order_unknown_resolution(tmp_path)

    assert report["status"]["outcome"] == "missing_pose_order_probe"
    assert report["checks"][2]["status"] == "fail"


def test_pose_order_unknown_resolution_cli_no_write(tmp_path: Path) -> None:
    _write_comparison(tmp_path, [130])
    _write_probe(tmp_path, 130, "prefix_infeasible")
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_pose_order_unknown_resolution.py",
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b pose-order unknown resolution" in completed.stdout
    assert not output_dir.exists()


def test_pose_order_unknown_resolution_cli_writes_outputs(tmp_path: Path) -> None:
    _write_comparison(tmp_path, [130])
    _write_probe(tmp_path, 130, "prefix_infeasible")
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_pose_order_unknown_resolution.py",
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "pose_order_unknown_resolution.json").exists()
    assert (output_dir / "pose_order_unknown_resolution.md").exists()
    assert (output_dir / "pose_order_unknown_resolution.txt").exists()


def _write_comparison(root: Path, anchors: list[int]) -> None:
    _write_json(
        root
        / ".artifacts/phase3b_start_repair_portfolio_sample_comparison/portfolio_sample_comparison.json",
        {
            "rerun_start_compatibility_portfolio": {
                "unknown_samples": [
                    {
                        "anchor_idx": anchor,
                        "ordering": "y_then_x",
                        "source": "coordinate_validation",
                        "status": "UNKNOWN",
                        "reason": "unknown",
                        "forced_slot_field_count": 798,
                    }
                    for anchor in anchors
                ]
            }
        },
    )


def _write_probe(root: Path, anchor: int, outcome: str) -> None:
    _write_json(
        root
        / f".artifacts/phase3b_pose_order_validation_probe_anchor130_131_y_then_x_selected_block_20260422/pose_order_validation_probe_67x13_anchor{anchor}_y_then_x.json",
        {
            "status": {"outcome": outcome},
            "diagnostics": {
                "full_validation": {
                    "status": "INFEASIBLE",
                    "reason": "infeasible",
                    "wall_time": 0.6,
                    "branches": 0,
                    "conflicts": 0,
                },
                "prefix_probe": {
                    "first_infeasible_prefix_group_count": 2,
                    "first_infeasible_group": {
                        "group_id": "group::protocol_core::protocol_core::18",
                        "facility_type": "protocol_core",
                        "required_count": 1,
                    },
                },
            },
        },
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

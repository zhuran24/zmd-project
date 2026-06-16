from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.start.repair_portfolio_sample_comparison import (
    build_phase3b_start_repair_portfolio_sample_comparison,
)


def test_portfolio_sample_comparison_reports_reduced_unknowns(tmp_path: Path) -> None:
    _write_operator_summary(tmp_path, unknown_count=27)
    _write_start_compatibility_samples(tmp_path, unknown_anchors=[130, 131])

    report = build_phase3b_start_repair_portfolio_sample_comparison(tmp_path)

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "portfolio_unknowns_reduced_by_bounded_rerun"
    assert report["baseline_b5a_portfolio"]["unknown_count"] == 27
    assert report["rerun_start_compatibility_portfolio"]["unknown_count"] == 2
    assert [
        entry["anchor_idx"]
        for entry in report["rerun_start_compatibility_portfolio"]["unknown_samples"]
    ] == [130, 131]
    assert report["status"]["runtime_promotion_ready"] is False


def test_portfolio_sample_comparison_missing_rerun(tmp_path: Path) -> None:
    _write_operator_summary(tmp_path, unknown_count=27)

    report = build_phase3b_start_repair_portfolio_sample_comparison(tmp_path)

    assert report["status"]["outcome"] == "missing_start_compatibility_sample_rerun"
    assert report["checks"][2]["status"] == "fail"


def test_portfolio_sample_comparison_cli_no_write(tmp_path: Path) -> None:
    _write_operator_summary(tmp_path, unknown_count=27)
    _write_start_compatibility_samples(tmp_path, unknown_anchors=[130])
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/start/build_repair_portfolio_sample_comparison.py",
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b start-repair portfolio sample comparison" in completed.stdout
    assert not output_dir.exists()


def test_portfolio_sample_comparison_cli_writes_outputs(tmp_path: Path) -> None:
    _write_operator_summary(tmp_path, unknown_count=27)
    _write_start_compatibility_samples(tmp_path, unknown_anchors=[130])
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/start/build_repair_portfolio_sample_comparison.py",
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "portfolio_sample_comparison.json").exists()
    assert (output_dir / "portfolio_sample_comparison.md").exists()
    assert (output_dir / "portfolio_sample_comparison.txt").exists()


def _write_operator_summary(root: Path, *, unknown_count: int) -> None:
    _write_json(
        root / ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json",
        {
            "telemetry": {
                "aggregate": {
                    "ghost_aware_pose_order_portfolio_failure_reason_counts": {
                        "coordinate_validation_infeasible": 49,
                        "coordinate_validation_unknown": unknown_count,
                    }
                }
            }
        },
    )


def _write_start_compatibility_samples(root: Path, *, unknown_anchors: list[int]) -> None:
    samples = [
        {
            "anchor_idx": anchor,
            "ordering": "y_then_x",
            "source": "coordinate_validation",
            "failure_reason": "coordinate_validation_unknown",
            "status": "UNKNOWN",
            "reason": "unknown",
            "forced_slot_field_count": 798,
            "wall_time": 4.0,
            "deterministic_time": 0.0001181,
            "branches": 0,
            "conflicts": 0,
        }
        for anchor in unknown_anchors
    ]
    samples.append(
        {
            "anchor_idx": 118,
            "ordering": "y_then_x",
            "source": "coordinate_validation",
            "failure_reason": "coordinate_validation_infeasible",
            "status": "INFEASIBLE",
            "reason": "infeasible",
        }
    )
    _write_json(
        root
        / ".artifacts/phase3b_start_compatibility_selected_block_samples_20260422/start_compatibility_67x13.json",
        {
            "diagnostics": {
                "warm_start": {
                    "ghost_aware_pose_order_portfolio_failure_samples": samples
                }
            }
        },
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

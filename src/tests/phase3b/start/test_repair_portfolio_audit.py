from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.start.repair_portfolio_audit import (
    build_phase3b_start_repair_portfolio_audit,
)


def test_start_repair_portfolio_audit_marks_unlocalized_unknowns(tmp_path: Path) -> None:
    _write_telemetry(tmp_path, include_pose_order_samples=False)
    _write_evidence_surface(tmp_path)
    _write_profiler(tmp_path, "69x19")

    report = build_phase3b_start_repair_portfolio_audit(tmp_path, candidate="67x13")

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "portfolio_unknowns_unlocalized"
    assert report["portfolio_unknowns"]["diagnosis"] == (
        "portfolio_unknowns_unlocalized_no_rejection_samples"
    )
    assert report["portfolio_unknowns"]["count"] == 27
    assert report["start_repair_profiler"]["current_candidate_profile_count"] == 0
    assert report["start_repair_profiler"]["stale_candidate_keys"] == ["69x19"]
    assert report["status"]["runtime_promotion_ready"] is False


def test_start_repair_portfolio_audit_uses_current_profiler_when_present(
    tmp_path: Path,
) -> None:
    _write_telemetry(tmp_path, include_pose_order_samples=True)
    _write_evidence_surface(tmp_path)
    _write_profiler(tmp_path, "67x13")

    report = build_phase3b_start_repair_portfolio_audit(tmp_path, candidate="67x13")

    assert report["status"]["outcome"] == "portfolio_audit_ready_for_manual_review"
    assert report["portfolio_unknowns"]["localized"] is True
    assert report["start_repair_profiler"]["current_candidate_profile_count"] == 1


def test_start_repair_portfolio_audit_cli_no_write(tmp_path: Path) -> None:
    _write_telemetry(tmp_path, include_pose_order_samples=False)
    _write_evidence_surface(tmp_path)
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/start/build_repair_portfolio_audit.py",
            "--project-root",
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

    assert "phase3b start-repair portfolio audit" in completed.stdout
    assert not output_dir.exists()


def test_start_repair_portfolio_audit_cli_writes_outputs(tmp_path: Path) -> None:
    _write_telemetry(tmp_path, include_pose_order_samples=False)
    _write_evidence_surface(tmp_path)
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/start/build_repair_portfolio_audit.py",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "start_repair_portfolio_audit.json").exists()
    assert (output_dir / "start_repair_portfolio_audit.md").exists()
    assert (output_dir / "start_repair_portfolio_audit.txt").exists()


def _write_telemetry(root: Path, *, include_pose_order_samples: bool) -> None:
    pose_samples = [{"status": "UNKNOWN"}] if include_pose_order_samples else []
    portfolio_samples = (
        [{"failure_reason": "coordinate_validation_unknown"}]
        if include_pose_order_samples
        else []
    )
    _write_json(
        root / "data/checkpoints/exact_campaign_telemetry.json",
        {
            "waves": [
                {
                    "candidate_results": [
                        {
                            "candidate_key": "67x13",
                            "status": "UNKNOWN",
                            "proof_status_summary": {
                                "master_start_failure_attribution": {
                                    "attempted_anchor_count": 112,
                                    "failed_anchor_count": 112,
                                    "failure_reason_counts": {
                                        "coordinate_validation_infeasible": 8
                                    },
                                    "failed_anchor_samples": [
                                        {
                                            "anchor_idx": 217,
                                            "failure_reason": "coordinate_validation_infeasible",
                                        }
                                    ],
                                },
                                "master_warm_start": {
                                    "ghost_aware_pose_order_portfolio_attempt_count": 112,
                                    "ghost_aware_pose_order_portfolio_failed_anchor_count": 112,
                                    "ghost_aware_pose_order_portfolio_failure_reason_counts": {
                                        "coordinate_validation_unknown": 27,
                                        "coordinate_validation_infeasible": 49,
                                    },
                                    "ghost_aware_pose_order_validation_rejection_samples": pose_samples,
                                    "ghost_aware_pose_order_portfolio_failure_samples": portfolio_samples,
                                },
                            },
                        }
                    ]
                }
            ]
        },
    )


def _write_evidence_surface(root: Path) -> None:
    _write_json(
        root
        / ".artifacts/phase3b_start_repair_evidence_surface/start_repair_evidence_surface.json",
        {
            "status": {
                "final_failure_reason_counts": {"coordinate_validation_infeasible": 8},
                "portfolio_failure_reason_counts": {
                    "coordinate_validation_unknown": 27,
                    "coordinate_validation_infeasible": 49,
                },
            }
        },
    )


def _write_profiler(root: Path, candidate: str) -> None:
    _write_json(
        root / f".artifacts/phase3b_start_repair_profiler/start_repair_{candidate}.json",
        {
            "candidate": {"key": candidate},
            "status": {"outcome": "start_repair_not_found_in_budget"},
        },
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

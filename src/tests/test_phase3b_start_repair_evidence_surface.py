from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_start_repair_evidence_surface import (
    build_phase3b_start_repair_evidence_surface,
)


def test_start_repair_evidence_surface_separates_final_and_portfolio_counts(
    tmp_path: Path,
) -> None:
    _write_telemetry(tmp_path)
    _write_json(
        tmp_path / ".artifacts/phase3b_start_compatibility_current/start_compatibility_67x13.json",
        {"status": {"outcome": "start_incompatible"}},
    )

    report = build_phase3b_start_repair_evidence_surface(tmp_path)

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "start_repair_not_attempted_current_source"
    assert report["final_start_attribution"]["failure_reason_counts"] == {"final": 8}
    assert report["pose_order_portfolio"]["failure_reason_counts"] == {"portfolio": 27}
    assert report["local_repair"]["attempted"] is False


def test_start_repair_evidence_surface_cli_no_write(tmp_path: Path) -> None:
    _write_telemetry(tmp_path)
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_start_repair_evidence_surface.py",
            "--project-root",
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

    assert "phase3b start-repair evidence surface" in completed.stdout
    assert not output_dir.exists()


def test_start_repair_evidence_surface_cli_writes_outputs(tmp_path: Path) -> None:
    _write_telemetry(tmp_path)
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_start_repair_evidence_surface.py",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "start_repair_evidence_surface.json").exists()
    assert (output_dir / "start_repair_evidence_surface.md").exists()
    assert (output_dir / "start_repair_evidence_surface.txt").exists()


def test_start_repair_evidence_surface_reads_real_telemetry_proof_status_summary(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "data/checkpoints/exact_campaign_telemetry.json",
        {
            "aggregate": {
                "ghost_aware_pose_order_portfolio_failure_reason_counts": {"portfolio": 49},
            },
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
                                        "coordinate_validation_infeasible": 8,
                                        "coordinate_validation_signature_monotonic_forced_label_infeasible": 102,
                                    },
                                    "first_failed_anchor_idx": 118,
                                    "failed_anchor_samples": [{"anchor_idx": 118}],
                                },
                                "master_start_local_repair": {
                                    "local_repair_attempted": False,
                                },
                            },
                        }
                    ]
                }
            ],
        },
    )

    report = build_phase3b_start_repair_evidence_surface(tmp_path)

    assert report["campaign"]["candidate_key"] == "67x13"
    assert report["final_start_attribution"]["attempted_anchor_count"] == 112
    assert report["final_start_attribution"]["failure_reason_counts"] == {
        "coordinate_validation_infeasible": 8,
        "coordinate_validation_signature_monotonic_forced_label_infeasible": 102,
    }
    assert report["pose_order_portfolio"]["failure_reason_counts"] == {"portfolio": 49}


def _write_telemetry(root: Path) -> None:
    _write_json(
        root / "data/checkpoints/exact_campaign_telemetry.json",
        {
            "aggregate": {
                "ghost_aware_pose_order_portfolio_attempted_count": 1,
                "ghost_aware_pose_order_portfolio_attempt_count_sum": 112,
                "ghost_aware_pose_order_portfolio_failed_anchor_count_sum": 112,
                "ghost_aware_pose_order_portfolio_failure_reason_counts": {"portfolio": 27},
            },
            "waves": [
                {
                    "candidate_results": [
                        {
                            "status": "UNKNOWN",
                            "candidate": {"key": "67x13"},
                            "proof_summary": {
                                "master_start_failure_attribution": {
                                    "attempted_anchor_count": 112,
                                    "failed_anchor_count": 112,
                                    "failure_reason_counts": {"final": 8},
                                    "failed_anchor_samples": [{}, {}],
                                },
                                "master_start_local_repair": {
                                    "local_repair_attempted": False,
                                    "local_repair_success": False,
                                    "local_repair_attempt_count": 0,
                                },
                            },
                        }
                    ]
                }
            ],
        },
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

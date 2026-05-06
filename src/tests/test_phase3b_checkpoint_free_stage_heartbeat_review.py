from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_stage_heartbeat_review import (
    build_stage_heartbeat_review,
    write_stage_heartbeat_review,
)


def test_stage_heartbeat_review_identifies_master_solve_stall(tmp_path: Path) -> None:
    summary_path = tmp_path / "run_summary.json"
    heartbeats_path = tmp_path / "stage_heartbeats.jsonl"
    _write_summary(summary_path)
    _write_heartbeats(heartbeats_path)

    review = build_stage_heartbeat_review(
        run_summary_path=summary_path,
        stage_heartbeats_path=heartbeats_path,
    )

    assert review["schema"] == "phase3b-checkpoint-free-stage-heartbeat-review/v0"
    assert review["run"]["stage_heartbeat_count"] == 4
    assert review["interpretation"]["stalled_stage"] == "master_solve"
    assert review["interpretation"]["stalled_before_binding_or_routing"] is True
    assert review["interpretation"]["master_solve_completed"] is False
    assert review["recommendation"]["action"] == "prepare_master_solve_micro_diagnostics"
    assert review["safety"]["builder_executes_solver"] is False
    assert review["safety"]["checkpoint_written"] is False
    assert review["safety"]["proof_source"] is False


def test_stage_heartbeat_review_handles_missing_events(tmp_path: Path) -> None:
    summary_path = tmp_path / "run_summary.json"
    heartbeats_path = tmp_path / "stage_heartbeats.jsonl"
    _write_summary(summary_path, count=0)
    heartbeats_path.write_text("", encoding="utf-8")

    review = build_stage_heartbeat_review(
        run_summary_path=summary_path,
        stage_heartbeats_path=heartbeats_path,
    )

    assert review["interpretation"]["stalled_stage"] == "no_stage_heartbeat"
    assert review["interpretation"]["stalled_reason"] == "no_stage_heartbeat_before_timeout"
    assert review["recommendation"]["action"] == "hold_manual_stage_review"


def test_stage_heartbeat_review_write_mode(tmp_path: Path) -> None:
    summary_path = tmp_path / "run_summary.json"
    heartbeats_path = tmp_path / "stage_heartbeats.jsonl"
    output_dir = tmp_path / "out"
    _write_summary(summary_path)
    _write_heartbeats(heartbeats_path)

    paths = write_stage_heartbeat_review(
        build_stage_heartbeat_review(
            run_summary_path=summary_path,
            stage_heartbeats_path=heartbeats_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "stage_heartbeat_review.json"
    assert paths["md"] == output_dir / "stage_heartbeat_review.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["interpretation"]["stalled_stage"] == "master_solve"
    assert "Stalled stage: `master_solve`" in paths["md"].read_text(encoding="utf-8")


def _write_summary(path: Path, *, count: int = 4) -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": "stage_probe",
                "candidate_id": "local_hotspot_b0_1x1_global_normal",
                "status": "timeout",
                "requested_duration_seconds": 300,
                "checkpoint_free": True,
                "proof_source": False,
                "checkpoint_written": False,
                "execution": {
                    "result_count": 0,
                    "stage_heartbeat_count": count,
                    "resource_stop_triggered": False,
                },
                "sensitive_path_comparison": {"changed": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_heartbeats(path: Path) -> None:
    rows = [
        {"payload": {"stage": "exact_session", "event": "start", "updated_at": "t0"}},
        {"payload": {"stage": "exact_session", "event": "complete", "updated_at": "t1"}},
        {"payload": {"stage": "master_warm_start", "event": "start", "updated_at": "t2"}},
        {
            "candidate_key": "42x32",
            "payload": {
                "stage": "master_solve",
                "event": "start",
                "iteration": 1,
                "updated_at": "t3",
            },
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

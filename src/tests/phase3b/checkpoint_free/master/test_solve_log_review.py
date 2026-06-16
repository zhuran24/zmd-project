from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.master.build_solve_log_review import (
    build_master_solve_log_review,
    write_master_solve_log_review,
)


def test_master_solve_log_review_classifies_presolve_symmetry_bottleneck(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "run_summary.json"
    heartbeats_path = tmp_path / "stage_heartbeats.jsonl"
    _write_summary(summary_path)
    _write_master_log_heartbeats(heartbeats_path)

    review = build_master_solve_log_review(
        run_summary_path=summary_path,
        stage_heartbeats_path=heartbeats_path,
    )

    assert review["schema"] == "phase3b-checkpoint-free-master-solve-log-review/v0"
    assert review["run"]["status"] == "timeout"
    assert review["run"]["sensitive_path_changed"] is False
    assert review["log_summary"]["log_line_count"] == 5
    assert review["log_summary"]["log_limit_reached"] is True
    assert review["extracted_metrics"]["max_symmetry_nodes"] == 7_209_035
    assert review["extracted_metrics"]["max_symmetry_arcs"] == 16_951_962
    assert review["extracted_metrics"]["max_sat_presolve_vars"] == 1_146_372
    assert review["interpretation"]["search_started"] is False
    assert review["interpretation"]["log_limit_reached_before_search"] is True
    assert (
        review["interpretation"]["classification"]
        == "presolve_symmetry_scale_bottleneck_before_search"
    )
    assert review["recommendation"]["action"] == "prepare_master_presolve_parameter_micro_matrix"
    assert review["safety"]["builder_executes_solver"] is False
    assert review["safety"]["checkpoint_written"] is False
    assert review["safety"]["proof_source"] is False


def test_master_solve_log_review_handles_missing_log_lines(tmp_path: Path) -> None:
    summary_path = tmp_path / "run_summary.json"
    heartbeats_path = tmp_path / "stage_heartbeats.jsonl"
    _write_summary(summary_path, count=0)
    heartbeats_path.write_text("", encoding="utf-8")

    review = build_master_solve_log_review(
        run_summary_path=summary_path,
        stage_heartbeats_path=heartbeats_path,
    )

    assert review["log_summary"]["log_line_count"] == 0
    assert review["interpretation"]["classification"] == "manual_review_required"
    assert review["recommendation"]["action"] == "hold_manual_master_log_review"


def test_master_solve_log_review_write_mode(tmp_path: Path) -> None:
    summary_path = tmp_path / "run_summary.json"
    heartbeats_path = tmp_path / "stage_heartbeats.jsonl"
    output_dir = tmp_path / "out"
    _write_summary(summary_path)
    _write_master_log_heartbeats(heartbeats_path)

    paths = write_master_solve_log_review(
        build_master_solve_log_review(
            run_summary_path=summary_path,
            stage_heartbeats_path=heartbeats_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "master_solve_log_review.json"
    assert paths["md"] == output_dir / "master_solve_log_review.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert (
        payload["interpretation"]["classification"]
        == "presolve_symmetry_scale_bottleneck_before_search"
    )
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_summary(path: Path, *, count: int = 93) -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001",
                "candidate_id": "local_hotspot_b0_1x1_master_log_global_normal",
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


def _write_master_log_heartbeats(path: Path) -> None:
    texts = [
        "Starting CP-SAT solver v9.15.6755",
        "Parameters: max_time_in_seconds: 300 log_search_progress: true "
        "search_branching: FIXED_SEARCH num_search_workers: 1 "
        "cp_model_probing_level: 3 hint_conflict_limit: 1000 "
        "symmetry_level: 3 log_to_stdout: false",
        "Graph for symmetry has 7'209'035 nodes and 16'951'962 arcs.",
        "SAT presolve clauses:2'522'058 literals:7'314'804 vars:1'146'372 one_side_vars:0",
        "Probe #probed=7'470 #new_binary_clauses=97'536",
    ]
    rows = [
        {
            "candidate_key": "42x32",
            "payload": {
                "stage": "master_solve_log",
                "event": "line",
                "line_index": index,
                "line_limit": 80,
                "text": text,
            },
        }
        for index, text in enumerate(texts, start=1)
    ]
    rows[-1]["payload"]["line_index"] = 80
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.master.build_solve_micro_diagnostics import (
    MICRO_CANDIDATE_ID,
    build_master_solve_micro_diagnostics,
    write_master_solve_micro_diagnostics,
)


def test_master_solve_micro_diagnostics_builds_log_heartbeat_profile(tmp_path: Path) -> None:
    stage_review_path = tmp_path / "stage_heartbeat_review.json"
    readiness_path = tmp_path / "hotspot_augmented_readiness_packet.json"
    _write_stage_review(stage_review_path)
    _write_readiness(readiness_path)
    _write_instrumented_sources(tmp_path)

    strategy = build_master_solve_micro_diagnostics(
        project_root=tmp_path,
        stage_review_path=stage_review_path,
        augmented_readiness_path=readiness_path,
    )

    assert strategy["schema"] == "phase3b-checkpoint-free-master-solve-micro-diagnostics/v0"
    assert strategy["recommendation"]["action"] == "ready_for_single_master_solve_log_probe"
    assert strategy["instrumentation"]["all_markers_present"] is True
    profile = strategy["diagnostic_profile"]
    assert profile["candidate_id"] == MICRO_CANDIDATE_ID
    assert profile["process_count"] == 1
    assert profile["env"]["EXACT_CP_SAT_WORKERS"] == "1"
    assert profile["env"]["EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES"] == "80"
    assert profile["env"]["EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS"] == "1000"
    assert "planned_future_commands" not in profile
    command = strategy["recommendation"]["execute_command_after_review"]
    assert "--execute" in command
    assert "--wave-candidate-key" in command
    assert "42x32" in command
    assert "168h" not in command
    assert "--resume-campaign" not in command
    assert strategy["safety"]["builder_executes_solver"] is False
    assert strategy["safety"]["checkpoint_written"] is False
    assert strategy["safety"]["proof_source"] is False


def test_master_solve_micro_diagnostics_holds_without_instrumentation(tmp_path: Path) -> None:
    stage_review_path = tmp_path / "stage_heartbeat_review.json"
    readiness_path = tmp_path / "hotspot_augmented_readiness_packet.json"
    _write_stage_review(stage_review_path)
    _write_readiness(readiness_path)

    strategy = build_master_solve_micro_diagnostics(
        project_root=tmp_path,
        stage_review_path=stage_review_path,
        augmented_readiness_path=readiness_path,
    )

    assert strategy["instrumentation"]["all_markers_present"] is False
    assert strategy["recommendation"]["action"] == "hold_manual_review"
    assert strategy["recommendation"]["execute_command_after_review"] == []


def test_master_solve_micro_diagnostics_write_mode(tmp_path: Path) -> None:
    stage_review_path = tmp_path / "stage_heartbeat_review.json"
    readiness_path = tmp_path / "hotspot_augmented_readiness_packet.json"
    output_dir = tmp_path / "out"
    _write_stage_review(stage_review_path)
    _write_readiness(readiness_path)
    _write_instrumented_sources(tmp_path)

    paths = write_master_solve_micro_diagnostics(
        build_master_solve_micro_diagnostics(
            project_root=tmp_path,
            stage_review_path=stage_review_path,
            augmented_readiness_path=readiness_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "master_solve_micro_diagnostics.json"
    assert paths["md"] == output_dir / "master_solve_micro_diagnostics.md"
    assert paths["augmented_readiness"] == output_dir / "master_solve_micro_augmented_readiness_packet.json"
    assert paths["command_matrix"] == output_dir / "master_solve_micro_command_matrix.json"
    readiness = json.loads(paths["augmented_readiness"].read_text(encoding="utf-8"))
    ids = [candidate["candidate_id"] for candidate in readiness["candidates"]]
    assert MICRO_CANDIDATE_ID in ids
    matrix = json.loads(paths["command_matrix"].read_text(encoding="utf-8"))
    assert matrix["checkpoint_written"] is False
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_stage_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "run": {"run_id": "stage_probe"},
                "interpretation": {
                    "stalled_stage": "master_solve",
                    "stalled_reason": "last_stage_start_without_complete_before_timeout",
                },
                "recommendation": {
                    "action": "prepare_master_solve_micro_diagnostics",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_readiness(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "packet_kind": "checkpoint_free_hotspot_augmented_readiness_local_only",
                "augmented_candidate_ids": ["local_hotspot_b0_1x1_global_normal"],
                "candidates": [
                    {
                        "candidate_id": "local_hotspot_b0_1x1_global_normal",
                        "source_kind": "local_hotspot_narrow_strategy",
                        "source_profile_id": "local_hotspot_b0_1x1_global_normal",
                        "process_count": 1,
                        "env": {"EXACT_CP_SAT_WORKERS": "1"},
                        "risk": {"level": "low"},
                        "frontier_probe_mode": "auto",
                        "proof_source": False,
                        "checkpoint_written": False,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_instrumented_sources(root: Path) -> None:
    files = {
        "src/models/master_model.py": (
            "diagnostic_log_callback\nlog_search_progress\nlog_callback_enabled\n"
        ),
        "src/search/benders_loop.py": (
            "EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES\nmaster_solve_log\n"
        ),
    }
    for relative_path, text in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

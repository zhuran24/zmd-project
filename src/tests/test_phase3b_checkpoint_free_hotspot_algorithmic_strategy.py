from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_hotspot_algorithmic_strategy import (
    build_hotspot_algorithmic_strategy,
    write_hotspot_algorithmic_strategy,
)


def test_hotspot_algorithmic_strategy_allows_single_stage_probe_when_instrumented(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "hotspot_narrow_result_review.json"
    readiness_path = tmp_path / "hotspot_augmented_readiness_packet.json"
    _write_narrow_review(review_path)
    _write_instrumented_sources(tmp_path)

    strategy = build_hotspot_algorithmic_strategy(
        project_root=tmp_path,
        narrow_review_path=review_path,
        augmented_readiness_path=readiness_path,
    )

    assert strategy["schema"] == "phase3b-checkpoint-free-hotspot-algorithmic-strategy/v0"
    assert strategy["evidence"]["classification"] == "memory_controlled_compute_straggler_at_600s"
    assert strategy["instrumentation"]["all_markers_present"] is True
    assert strategy["recommendation"]["action"] == "ready_for_single_stage_heartbeat_probe"
    assert strategy["recommendation"]["first_probe_candidate_id"] == "local_hotspot_b0_1x1_global_normal"
    assert strategy["recommendation"]["first_probe_candidate_key"] == "42x32"
    assert strategy["recommendation"]["first_probe_duration_seconds"] == 300
    command = strategy["recommendation"]["execute_command_after_review"]
    assert "--execute" in command
    assert "--duration-seconds" in command
    assert "300" in command
    assert "--wave-candidate-key" in command
    assert "42x32" in command
    assert "168h" not in command
    assert "--resume-campaign" not in command
    assert strategy["safety"]["builder_executes_solver"] is False
    assert strategy["safety"]["checkpoint_written"] is False
    assert strategy["safety"]["proof_source"] is False


def test_hotspot_algorithmic_strategy_holds_when_instrumentation_missing(tmp_path: Path) -> None:
    review_path = tmp_path / "hotspot_narrow_result_review.json"
    readiness_path = tmp_path / "hotspot_augmented_readiness_packet.json"
    _write_narrow_review(review_path)

    strategy = build_hotspot_algorithmic_strategy(
        project_root=tmp_path,
        narrow_review_path=review_path,
        augmented_readiness_path=readiness_path,
    )

    assert strategy["instrumentation"]["all_markers_present"] is False
    assert strategy["recommendation"]["action"] == "hold_until_stage_heartbeat_instrumentation_verified"
    assert strategy["recommendation"]["execute_command_after_review"] == []


def test_hotspot_algorithmic_strategy_write_mode(tmp_path: Path) -> None:
    review_path = tmp_path / "hotspot_narrow_result_review.json"
    readiness_path = tmp_path / "hotspot_augmented_readiness_packet.json"
    output_dir = tmp_path / "out"
    _write_narrow_review(review_path)
    _write_instrumented_sources(tmp_path)

    paths = write_hotspot_algorithmic_strategy(
        build_hotspot_algorithmic_strategy(
            project_root=tmp_path,
            narrow_review_path=review_path,
            augmented_readiness_path=readiness_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "hotspot_algorithmic_strategy.json"
    assert paths["md"] == output_dir / "hotspot_algorithmic_strategy.md"
    assert paths["command_matrix"] == output_dir / "hotspot_stage_heartbeat_command_matrix.json"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["candidate_universe_changed"] is False
    matrix = json.loads(paths["command_matrix"].read_text(encoding="utf-8"))
    assert matrix["checkpoint_written"] is False
    assert matrix["commands"][0]["duration_seconds"] == 300
    assert "Stage-heartbeat instrumentation ready: `True`" in paths["md"].read_text(
        encoding="utf-8"
    )


def _write_narrow_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "memory_controlled_compute_straggler_at_600s",
                    "confirmation_600s_present": True,
                    "confirmation_600s_timeout_no_result": True,
                },
                "recommendation": {
                    "action": "hold_hotspot_algorithmic_strategy_review",
                },
                "runs": [{}, {}, {}, {}],
                "confirmation_runs": [{}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_instrumented_sources(root: Path) -> None:
    files = {
        "src/search/benders_loop.py": "heartbeat_callback\n_emit_campaign_heartbeat\n",
        "src/search/exact_parallel_scheduler.py": (
            'heartbeat_events\n"message_type": "HEARTBEAT"\n'
        ),
        "src/runtime/checkpoint_free_evaluator.py": (
            "stage_heartbeats_jsonl\nstage_heartbeat_count\n"
        ),
    }
    for relative_path, text in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

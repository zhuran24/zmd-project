from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_resource_hotspot_strategy import (
    build_resource_hotspot_strategy,
    write_resource_hotspot_strategy,
)


def test_resource_hotspot_strategy_extracts_isolated_and_straggler_keys(tmp_path: Path) -> None:
    wave_path = tmp_path / "wave.json"
    scoreboard_path = tmp_path / "scoreboard.json"
    _write_wave_diagnosis(wave_path)
    _write_scoreboard(scoreboard_path)

    strategy = build_resource_hotspot_strategy(
        wave_diagnosis_path=wave_path,
        scoreboard_path=scoreboard_path,
    )

    assert strategy["hotspot_keys"]["isolated_resource_stop_keys"] == ["42x32", "67x20"]
    assert strategy["hotspot_keys"]["straggler_keys"] == ["42x32"]
    assert strategy["hotspot_keys"]["interrupted_keys"] == ["42x32", "67x20"]
    assert strategy["hotspot_keys"]["completed_non_resource_keys"] == ["70x12"]
    assert strategy["recommendation"]["avoid_candidate_keys_for_wave_expansion"] == [
        "42x32",
        "67x20",
    ]
    assert strategy["recommendation"]["retry_only_with_changed_resource_strategy"] == [
        "42x32",
        "67x20",
    ]
    assert strategy["proof_source"] is False
    assert strategy["scheduler_integration"] is False


def test_resource_hotspot_strategy_write_mode(tmp_path: Path) -> None:
    wave_path = tmp_path / "wave.json"
    scoreboard_path = tmp_path / "scoreboard.json"
    output_dir = tmp_path / "out"
    _write_wave_diagnosis(wave_path)
    _write_scoreboard(scoreboard_path)

    paths = write_resource_hotspot_strategy(
        build_resource_hotspot_strategy(
            wave_diagnosis_path=wave_path,
            scoreboard_path=scoreboard_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "resource_hotspot_strategy.json"
    assert paths["md"] == output_dir / "resource_hotspot_strategy.md"
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["schema"] == (
        "phase3b-checkpoint-free-resource-hotspot-strategy/v0"
    )
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_wave_diagnosis(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "resource_stop_run_count": 3,
                    "timeout_run_count": 1,
                    "straggler_candidate_keys": ["42x32"],
                    "interrupted_candidate_keys": ["42x32", "67x20"],
                },
                "runs": [
                    {
                        "run_id": "safe",
                        "wave_selected_count": 1,
                        "planned_candidate_keys": ["70x12"],
                        "completed_candidate_keys": ["70x12"],
                        "timed_out": False,
                        "resource_stop_triggered": False,
                    },
                    {
                        "run_id": "hot_42",
                        "wave_selected_count": 1,
                        "planned_candidate_keys": ["42x32"],
                        "completed_candidate_keys": [],
                        "timed_out": False,
                        "resource_stop_triggered": True,
                    },
                    {
                        "run_id": "hot_67",
                        "wave_selected_count": 1,
                        "planned_candidate_keys": ["67x20"],
                        "completed_candidate_keys": [],
                        "timed_out": False,
                        "resource_stop_triggered": True,
                    },
                    {
                        "run_id": "multi",
                        "wave_selected_count": 3,
                        "planned_candidate_keys": ["70x12", "42x32", "67x20"],
                        "completed_candidate_keys": ["70x12"],
                        "timed_out": False,
                        "resource_stop_triggered": True,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_scoreboard(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "candidate_summaries": [{"candidate_id": "B0_prod_4x4"}],
                "safety": {"sensitive_path_mutation_detected": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )

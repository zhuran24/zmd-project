from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.hotspot.build_narrow_strategy import (
    build_hotspot_narrow_strategy,
    write_hotspot_narrow_strategy,
)


def test_hotspot_narrow_strategy_proposes_local_single_process_profiles(tmp_path: Path) -> None:
    timeout_review_path = tmp_path / "timeout_review.json"
    resource_revision_path = tmp_path / "resource_revision.json"
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    _write_timeout_review(timeout_review_path)
    _write_resource_revision(resource_revision_path)
    _write_scoreboard(scoreboard_path)
    _write_readiness(readiness_path)

    strategy = build_hotspot_narrow_strategy(
        timeout_review_path=timeout_review_path,
        resource_revision_path=resource_revision_path,
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )

    assert strategy["schema"] == "phase3b-checkpoint-free-hotspot-narrow-strategy/v0"
    assert strategy["hotspot"]["candidate_key"] == "42x32"
    assert strategy["current_readiness"]["single_process_profile_present"] is False
    assert strategy["recommendation"]["action"] == "prepare_narrow_local_profile_readiness_extension"
    assert strategy["recommendation"]["first_candidate_profile"] == "local_hotspot_b0_1x4_global_normal"
    assert strategy["safety"]["builder_executes_solver"] is False
    assert strategy["safety"]["checkpoint_written"] is False
    assert strategy["safety"]["proof_source"] is False

    profiles = {profile["candidate_id"]: profile for profile in strategy["proposed_local_profiles"]}
    first = profiles["local_hotspot_b0_1x4_global_normal"]
    assert first["process_count"] == 1
    assert first["env"] == {"EXACT_CP_SAT_WORKERS": "4"}
    assert first["total_worker_slots"] == 4
    assert first["duration_seconds"] == 300
    assert first["candidate_key"] == "42x32"
    assert first["execution_enabled"] is False
    assert first["execute_command"] == []
    assert "--execute" in first["future_execute_command_after_support"]
    assert "--readiness-packet" in first["future_execute_command_after_support"]
    assert "--wave-candidate-key" in first["future_execute_command_after_support"]
    assert "42x32" in first["future_execute_command_after_support"]
    augmented = strategy["augmented_readiness_packet"]
    assert augmented["packet_kind"] == "checkpoint_free_hotspot_augmented_readiness_local_only"
    assert augmented["local_readiness_candidate_list_extended"] is True
    assert "local_hotspot_b0_1x4_global_normal" in augmented["augmented_candidate_ids"]
    augmented_profile = next(
        candidate
        for candidate in augmented["candidates"]
        if candidate["candidate_id"] == "local_hotspot_b0_1x4_global_normal"
    )
    assert augmented_profile["process_count"] == 1
    assert augmented_profile["env"] == {"EXACT_CP_SAT_WORKERS": "4"}
    assert augmented_profile["proof_source"] is False
    assert augmented_profile["checkpoint_written"] is False


def test_hotspot_narrow_strategy_commands_avoid_forbidden_tokens(tmp_path: Path) -> None:
    timeout_review_path = tmp_path / "timeout_review.json"
    resource_revision_path = tmp_path / "resource_revision.json"
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    _write_timeout_review(timeout_review_path)
    _write_resource_revision(resource_revision_path)
    _write_scoreboard(scoreboard_path)
    _write_readiness(readiness_path)

    strategy = build_hotspot_narrow_strategy(
        timeout_review_path=timeout_review_path,
        resource_revision_path=resource_revision_path,
        scoreboard_path=scoreboard_path,
        readiness_path=readiness_path,
    )

    forbidden = {
        "168h",
        "--resume-campaign",
        "--checkpoint",
        "--proof-source",
        "certified_manifest",
        "frontdoor",
        "release",
        "viewer",
    }
    for profile in strategy["proposed_local_profiles"]:
        assert profile["duration_seconds"] == 300
        assert profile["execute_command"] == []
        assert not forbidden.intersection(profile["future_execute_command_after_support"])


def test_hotspot_narrow_strategy_write_mode(tmp_path: Path) -> None:
    timeout_review_path = tmp_path / "timeout_review.json"
    resource_revision_path = tmp_path / "resource_revision.json"
    scoreboard_path = tmp_path / "scoreboard.json"
    readiness_path = tmp_path / "readiness.json"
    output_dir = tmp_path / "out"
    _write_timeout_review(timeout_review_path)
    _write_resource_revision(resource_revision_path)
    _write_scoreboard(scoreboard_path)
    _write_readiness(readiness_path)

    paths = write_hotspot_narrow_strategy(
        build_hotspot_narrow_strategy(
            timeout_review_path=timeout_review_path,
            resource_revision_path=resource_revision_path,
            scoreboard_path=scoreboard_path,
            readiness_path=readiness_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "hotspot_narrow_strategy.json"
    assert paths["md"] == output_dir / "hotspot_narrow_strategy.md"
    assert paths["command_matrix"] == output_dir / "hotspot_narrow_command_matrix.json"
    assert paths["augmented_readiness"] == output_dir / "hotspot_augmented_readiness_packet.json"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["candidate_universe_changed"] is False
    augmented = json.loads(paths["augmented_readiness"].read_text(encoding="utf-8"))
    assert augmented["augmented_candidate_ids"] == [
        "local_hotspot_b0_1x4_global_normal",
        "local_hotspot_b0_1x2_global_normal",
        "local_hotspot_b0_1x1_global_normal",
    ]
    command_matrix = json.loads(paths["command_matrix"].read_text(encoding="utf-8"))
    assert command_matrix["proof_source"] is False
    assert command_matrix["checkpoint_written"] is False
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_timeout_review(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "run": {
                    "run_id": "B0_prod_4x4_300s_42x32_resource_probe_eval_001",
                    "candidate_id": "B0_prod_4x4",
                    "candidate_key": "42x32",
                    "status": "timeout",
                    "requested_duration_seconds": 300,
                    "resource_stop_triggered": False,
                    "sensitive_path_changed": False,
                },
                "interpretation": {"classification": "bounded_timeout_high_memory_straggler"},
                "telemetry_review": {
                    "peak_total_private_gib": 32.8,
                    "dominant_process_peak_private_gib": 21.8,
                },
                "recommendation": {
                    "action": "hold_hotspot_followups_pending_narrower_timeout_strategy",
                    "observed_peak_private_gib": 32.8,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_resource_revision(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "recommendation": {
                    "action": "hold_primary_hotspot_probe_timeout_review",
                    "primary_probe_id": "B0_prod_4x4_300s_42x32_resource_probe_001",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_scoreboard(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "B0_prod_4x4_300s_42x32_resource_probe_eval_001",
                        "candidate_id": "B0_prod_4x4",
                        "status": "timeout",
                        "wave_candidate_keys": ["42x32"],
                    }
                ],
                "safety": {"sensitive_path_mutation_detected": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_readiness(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "allowed_durations_seconds": [300, 600],
                "candidates": [
                    {
                        "candidate_id": "B0_prod_4x4",
                        "process_count": 4,
                        "env": {"EXACT_CP_SAT_WORKERS": "4"},
                        "total_worker_slots": 16,
                    },
                    {
                        "candidate_id": "experimental_13900ks_htoff_2x10_global_normal",
                        "process_count": 2,
                        "env": {"EXACT_CP_SAT_WORKERS": "10"},
                        "total_worker_slots": 20,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.resource.build_strategy_revision import (
    build_resource_strategy_revision,
    write_resource_strategy_revision,
)


def test_resource_strategy_revision_builds_bounded_micro_probe_plan(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    wave_path = tmp_path / "wave.json"
    hotspot_path = tmp_path / "hotspot.json"
    next_path = tmp_path / "next.json"
    _write_scoreboard(scoreboard_path)
    _write_wave_diagnosis(wave_path)
    _write_hotspot_strategy(hotspot_path)
    _write_next_decision(next_path)

    revision = build_resource_strategy_revision(
        scoreboard_path=scoreboard_path,
        wave_diagnosis_path=wave_path,
        hotspot_strategy_path=hotspot_path,
        next_decision_path=next_path,
    )

    assert revision["recommendation"]["action"] == "prepare_single_hotspot_micro_probe"
    assert revision["recommendation"]["primary_probe_id"] == "B0_prod_4x4_300s_42x32_resource_probe_001"
    assert revision["evidence_summary"]["avoid_candidate_keys"] == ["42x32", "67x20"]
    probes = {probe["probe_id"]: probe for probe in revision["micro_probe_plan"]}
    primary = probes["B0_prod_4x4_300s_42x32_resource_probe_001"]
    assert primary["duration_seconds"] == 300
    assert primary["max_wave_candidates"] == 1
    assert primary["status"] == "ready_for_single_checkpoint_free_probe"
    assert "--execute" in primary["execute_command"]
    assert "--wave-candidate-key" in primary["execute_command"]
    assert "42x32" in primary["execute_command"]
    forbidden_tokens = {"168h", "--resume-campaign", "--checkpoint", "--proof-source"}
    assert not forbidden_tokens.intersection(primary["execute_command"])
    assert primary["execution_enabled_by_builder"] is False
    assert revision["safety"]["builder_executes_solver"] is False


def test_resource_strategy_revision_blocks_prior_2x10_hotspot_retry(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    wave_path = tmp_path / "wave.json"
    hotspot_path = tmp_path / "hotspot.json"
    next_path = tmp_path / "next.json"
    _write_scoreboard(scoreboard_path)
    _write_wave_diagnosis(wave_path)
    _write_hotspot_strategy(hotspot_path)
    _write_next_decision(next_path)

    revision = build_resource_strategy_revision(
        scoreboard_path=scoreboard_path,
        wave_diagnosis_path=wave_path,
        hotspot_strategy_path=hotspot_path,
        next_decision_path=next_path,
    )

    blocked = next(
        probe
        for probe in revision["micro_probe_plan"]
        if probe["candidate_id"] == "experimental_13900ks_htoff_2x10_global_normal"
    )
    assert blocked["status"] == "blocked_prior_resource_stop"
    assert blocked["execute_command"] == []
    assert blocked["risk_level"] == "known_resource_stop"


def test_resource_strategy_revision_holds_after_primary_probe_timeout(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    wave_path = tmp_path / "wave.json"
    hotspot_path = tmp_path / "hotspot.json"
    next_path = tmp_path / "next.json"
    _write_scoreboard(scoreboard_path, include_primary_probe_timeout=True)
    _write_wave_diagnosis(wave_path)
    _write_hotspot_strategy(hotspot_path)
    _write_next_decision(next_path)

    revision = build_resource_strategy_revision(
        scoreboard_path=scoreboard_path,
        wave_diagnosis_path=wave_path,
        hotspot_strategy_path=hotspot_path,
        next_decision_path=next_path,
    )

    primary = revision["micro_probe_plan"][0]
    assert revision["recommendation"]["action"] == "hold_primary_hotspot_probe_timeout_review"
    assert primary["status"] == "primary_probe_timeout_no_resource_stop_review_required"
    assert primary["execute_command"] == []
    assert primary["existing_run_id"] == "B0_prod_4x4_300s_42x32_resource_probe_eval_001"
    secondary = next(probe for probe in revision["micro_probe_plan"] if probe["candidate_key"] == "67x20")
    assert secondary["status"] == "blocked_until_primary_probe_clean"
    comparable = next(
        probe
        for probe in revision["micro_probe_plan"]
        if probe["candidate_id"] == "experimental_13900ks_htoff_4x5_global_normal"
    )
    assert comparable["status"] == "blocked_pending_primary_timeout_review"
    assert comparable["execute_command"] == []


def test_resource_strategy_revision_write_mode(tmp_path: Path) -> None:
    scoreboard_path = tmp_path / "scoreboard.json"
    wave_path = tmp_path / "wave.json"
    hotspot_path = tmp_path / "hotspot.json"
    next_path = tmp_path / "next.json"
    output_dir = tmp_path / "out"
    _write_scoreboard(scoreboard_path)
    _write_wave_diagnosis(wave_path)
    _write_hotspot_strategy(hotspot_path)
    _write_next_decision(next_path)

    paths = write_resource_strategy_revision(
        build_resource_strategy_revision(
            scoreboard_path=scoreboard_path,
            wave_diagnosis_path=wave_path,
            hotspot_strategy_path=hotspot_path,
            next_decision_path=next_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "resource_strategy_revision.json"
    assert paths["md"] == output_dir / "resource_strategy_revision.md"
    assert paths["command_matrix"] == output_dir / "resource_strategy_command_matrix.json"
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["schema"] == (
        "phase3b-checkpoint-free-resource-strategy-revision/v0"
    )
    command_matrix = json.loads(paths["command_matrix"].read_text(encoding="utf-8"))
    assert command_matrix["checkpoint_written"] is False
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_scoreboard(path: Path, *, include_primary_probe_timeout: bool = False) -> None:
    runs = [
        _run(
            "B0_prod_4x4",
            "B0_prod_4x4_600s_reduced_frontier_no_hotspots_eval_001",
            status="completed",
            peak_private=14.3,
            keys=["70x12", "70x19"],
            excluded=["42x32", "67x20"],
        ),
        _run(
            "experimental_13900ks_htoff_4x5_global_normal",
            "experimental_13900ks_htoff_4x5_global_normal_600s_reduced_frontier_no_hotspots_eval_001",
            status="completed",
            peak_private=14.5,
            keys=["70x12", "70x19"],
            excluded=["42x32", "67x20"],
        ),
        _run(
            "experimental_13900ks_htoff_2x10_global_normal",
            "experimental_13900ks_htoff_2x10_global_normal_600s_reduced_frontier_no_hotspots_eval_001",
            status="completed",
            peak_private=7.6,
            keys=["70x12", "70x19"],
            excluded=["42x32", "67x20"],
        ),
        _run(
            "experimental_13900ks_htoff_2x10_global_normal",
            "experimental_13900ks_htoff_2x10_global_normal_300s_42x32_isolated_eval_001",
            status="stopped_resource_limit",
            peak_private=44.3,
            keys=["42x32"],
            resource_stop=True,
        ),
    ]
    if include_primary_probe_timeout:
        runs.append(
            _run(
                "B0_prod_4x4",
                "B0_prod_4x4_300s_42x32_resource_probe_eval_001",
                status="timeout",
                peak_private=32.8,
                keys=["42x32"],
                timed_out=True,
                requested=["42x32"],
            )
        )
    path.write_text(
        json.dumps(
            {
                "runs": runs,
                "safety": {"sensitive_path_mutation_detected": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _run(
    candidate_id: str,
    run_id: str,
    *,
    status: str,
    peak_private: float,
    keys: list[str],
    excluded: list[str] | None = None,
    requested: list[str] | None = None,
    resource_stop: bool = False,
    timed_out: bool = False,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "run_id": run_id,
        "status": status,
        "requested_duration_seconds": 300 if "300s" in run_id else 600,
        "wave_candidate_keys": keys,
        "wave_requested_candidate_keys": list(requested or []),
        "wave_excluded_candidate_keys": list(excluded or []),
        "wave_max_candidates": len(keys),
        "peak_private_gib": peak_private,
        "resource_stop_triggered": resource_stop,
        "timed_out": timed_out,
        "sensitive_path_changed": False,
    }


def _write_wave_diagnosis(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "resource_stop_run_count": 2,
                    "timeout_run_count": 1,
                    "straggler_candidate_keys": ["42x32"],
                    "interrupted_candidate_keys": ["42x32", "67x20"],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_hotspot_strategy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "recommendation": {
                    "avoid_candidate_keys_for_wave_expansion": ["42x32", "67x20"],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_next_decision(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "recommendation": {
                    "action": "hold_for_baseline_600s_full_wave_resource_stop",
                    "reduced_frontier_no_hotspots": {
                        "action": "hold_reduced_frontier_no_remaining_low_risk_candidates",
                    },
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

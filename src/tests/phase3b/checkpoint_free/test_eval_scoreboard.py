from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.build_eval_scoreboard import (
    build_checkpoint_free_eval_scoreboard,
    write_checkpoint_free_eval_scoreboard,
)


def test_checkpoint_free_scoreboard_filters_single_runs_and_normalizes_baseline(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_summary(
        runs_dir / "legacy" / "run_summary.json",
        run_id="B0_prod_4x4_300s_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=300.0,
        result_count=10,
    )
    _write_summary(
        runs_dir / "B0_prod_4x4_300s_single_eval_001" / "run_summary.json",
        run_id="B0_prod_4x4_300s_single_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=30.0,
        result_count=1,
    )
    _write_summary(
        runs_dir / "experimental_300s_single_eval_001" / "run_summary.json",
        run_id="experimental_300s_single_eval_001",
        candidate_id="experimental",
        duration_seconds=60.0,
        result_count=4,
    )
    _write_summary(
        runs_dir / "experimental_300s_42x32_isolated_eval_001" / "run_summary.json",
        run_id="experimental_300s_42x32_isolated_eval_001",
        candidate_id="experimental",
        duration_seconds=300.0,
        result_count=0,
        status="stopped_resource_limit",
        resource_stop=True,
    )
    _write_summary(
        runs_dir / "experimental_300s_reduced_frontier_no_hotspots_eval_001" / "run_summary.json",
        run_id="experimental_300s_reduced_frontier_no_hotspots_eval_001",
        candidate_id="experimental",
        duration_seconds=30.0,
        result_count=2,
        selected_count=2,
        selection_kind="deterministic_frontier_bounded_wave_excluding_keys_v0",
        excluded_candidate_keys=["42x32", "67x20"],
    )
    _write_summary(
        runs_dir / "B0_prod_4x4_300s_42x32_resource_probe_eval_001" / "run_summary.json",
        run_id="B0_prod_4x4_300s_42x32_resource_probe_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=330.0,
        result_count=0,
        status="timeout",
        selected_count=1,
        selection_kind="explicit_frontier_candidate_key_v0",
        requested_candidate_keys=["42x32"],
    )
    _write_summary(
        runs_dir / "local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001" / "run_summary.json",
        run_id="local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001",
        candidate_id="local_hotspot_b0_1x4_global_normal",
        duration_seconds=330.0,
        result_count=0,
        status="timeout",
        selected_count=1,
        selection_kind="explicit_frontier_candidate_key_v0",
        requested_candidate_keys=["42x32"],
    )
    _write_summary(
        runs_dir / "local_hotspot_b0_1x4_global_normal_300s_42x32_narrow_eval_001" / "run_summary.json",
        run_id="local_hotspot_b0_1x4_global_normal_300s_42x32_narrow_eval_001",
        candidate_id="local_hotspot_b0_1x4_global_normal",
        duration_seconds=330.0,
        result_count=0,
        status="timeout",
        selected_count=1,
        selection_kind="explicit_frontier_candidate_key_v0",
        requested_candidate_keys=["42x32"],
    )

    scoreboard = build_checkpoint_free_eval_scoreboard(runs_dir=runs_dir)

    assert [run["run_id"] for run in scoreboard["runs"]] == [
        "B0_prod_4x4_300s_42x32_resource_probe_eval_001",
        "B0_prod_4x4_300s_single_eval_001",
        "experimental_300s_42x32_isolated_eval_001",
        "experimental_300s_reduced_frontier_no_hotspots_eval_001",
        "experimental_300s_single_eval_001",
        "local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001",
        "local_hotspot_b0_1x4_global_normal_300s_42x32_narrow_eval_001",
    ]
    assert scoreboard["baseline"]["run_id"] == "B0_prod_4x4_300s_single_eval_001"
    by_candidate = {summary["candidate_id"]: summary for summary in scoreboard["candidate_summaries"]}
    assert by_candidate["experimental"]["best_baseline_normalized_throughput"] == 2.0
    reduced = next(run for run in scoreboard["runs"] if run["run_id"].endswith("reduced_frontier_no_hotspots_eval_001"))
    assert reduced["wave_selection_kind"] == "deterministic_frontier_bounded_wave_excluding_keys_v0"
    assert reduced["wave_excluded_candidate_keys"] == ["42x32", "67x20"]
    assert reduced["wave_candidate_keys"] == ["candidate_0", "candidate_1"]
    resource_probe = next(run for run in scoreboard["runs"] if run["run_id"].endswith("resource_probe_eval_001"))
    assert resource_probe["wave_selection_kind"] == "explicit_frontier_candidate_key_v0"
    assert resource_probe["wave_requested_candidate_keys"] == ["42x32"]
    narrow = next(run for run in scoreboard["runs"] if run["run_id"].endswith("narrow_eval_001"))
    assert narrow["candidate_id"] == "local_hotspot_b0_1x4_global_normal"
    assert narrow["wave_requested_candidate_keys"] == ["42x32"]
    assert scoreboard["safety"]["sensitive_path_mutation_detected"] is False


def test_checkpoint_free_scoreboard_reports_safety_mutation(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_summary(
        runs_dir / "B0_prod_4x4_300s_single_eval_001" / "run_summary.json",
        run_id="B0_prod_4x4_300s_single_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=30.0,
        result_count=1,
    )
    _write_summary(
        runs_dir / "mutating_300s_single_eval_001" / "run_summary.json",
        run_id="mutating_300s_single_eval_001",
        candidate_id="mutating",
        duration_seconds=60.0,
        result_count=1,
        sensitive_changed=True,
    )

    scoreboard = build_checkpoint_free_eval_scoreboard(runs_dir=runs_dir)

    assert scoreboard["safety"]["sensitive_path_mutation_detected"] is True
    mutating = next(summary for summary in scoreboard["candidate_summaries"] if summary["candidate_id"] == "mutating")
    assert mutating["any_sensitive_path_changed"] is True


def test_checkpoint_free_scoreboard_uses_duration_matched_baseline(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_summary(
        runs_dir / "B0_prod_4x4_300s_single_eval_001" / "run_summary.json",
        run_id="B0_prod_4x4_300s_single_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=30.0,
        result_count=1,
        requested_duration=300,
    )
    _write_summary(
        runs_dir / "B0_prod_4x4_600s_single_eval_001" / "run_summary.json",
        run_id="B0_prod_4x4_600s_single_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=240.0,
        result_count=2,
        requested_duration=600,
        status="stopped_resource_limit",
        resource_stop=True,
    )
    _write_summary(
        runs_dir / "experimental_300s_single_eval_001" / "run_summary.json",
        run_id="experimental_300s_single_eval_001",
        candidate_id="experimental",
        duration_seconds=60.0,
        result_count=4,
        requested_duration=300,
    )

    scoreboard = build_checkpoint_free_eval_scoreboard(runs_dir=runs_dir)

    assert scoreboard["baseline"]["run_id"] == "B0_prod_4x4_300s_single_eval_001"
    experimental = next(run for run in scoreboard["runs"] if run["candidate_id"] == "experimental")
    assert experimental["baseline_run_id_for_normalization"] == "B0_prod_4x4_300s_single_eval_001"
    assert experimental["baseline_normalization_match"] == "duration_and_wave"
    assert experimental["baseline_normalized_throughput"] == 2.0


def test_checkpoint_free_scoreboard_write_mode(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "out"
    _write_summary(
        runs_dir / "B0_prod_4x4_300s_single_eval_001" / "run_summary.json",
        run_id="B0_prod_4x4_300s_single_eval_001",
        candidate_id="B0_prod_4x4",
        duration_seconds=30.0,
        result_count=1,
    )

    scoreboard = build_checkpoint_free_eval_scoreboard(runs_dir=runs_dir)
    paths = write_checkpoint_free_eval_scoreboard(scoreboard, output_dir)

    assert paths["json"] == output_dir / "checkpoint_free_eval_scoreboard.json"
    assert paths["md"] == output_dir / "checkpoint_free_eval_scoreboard.md"
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["schema"] == (
        "phase3b-checkpoint-free-eval-scoreboard/v0"
    )
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_summary(
    path: Path,
    *,
    run_id: str,
    candidate_id: str,
    duration_seconds: float,
    result_count: int,
    sensitive_changed: bool = False,
    requested_duration: int = 300,
    status: str = "completed",
    resource_stop: bool = False,
    max_wave_candidates: int = 1,
    selected_count: int = 1,
    selection_kind: str = "deterministic_frontier_bounded_wave_v0",
    requested_candidate_keys: list[str] | None = None,
    excluded_candidate_keys: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "candidate_id": candidate_id,
                "status": status,
                "execute": True,
                "duration_seconds": duration_seconds,
                "requested_duration_seconds": requested_duration,
                "checkpoint_free": True,
                "main_py_executed": False,
                "exact_campaign_used": False,
                "proof_source": False,
                "checkpoint_written": False,
                "candidate_universe_changed": False,
                "production_profile_changed": False,
                "execution": {
                    "result_count": result_count,
                    "timed_out": False,
                    "resource_stop_triggered": resource_stop,
                    "elapsed_seconds": duration_seconds,
                },
                "telemetry_summary": {
                    "peak_total_private_bytes": 4 * 1024**3,
                    "peak_total_rss_bytes": 3 * 1024**3,
                    "peak_total_cpu_percent": 100.0,
                },
                "sensitive_path_comparison": {
                    "changed": sensitive_changed,
                    "changed_paths": ["data/checkpoints"] if sensitive_changed else [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (path.parent / "run_plan.json").write_text(
        json.dumps(
            {
                "wave": {
                    "selection_kind": selection_kind,
                    "max_wave_candidates": max_wave_candidates,
                    "selected_count": selected_count,
                    "requested_candidate_keys": list(requested_candidate_keys or []),
                    "excluded_candidate_keys": list(excluded_candidate_keys or []),
                    "entries": [
                        {"candidate_key": f"candidate_{idx}"}
                        for idx in range(max(0, int(selected_count)))
                    ],
                },
                "candidate_profile": {
                    "process_count": max_wave_candidates,
                    "total_worker_slots": max_wave_candidates * 4,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_wave_diagnosis import (
    build_checkpoint_free_wave_diagnosis,
    write_checkpoint_free_wave_diagnosis,
)


def test_wave_diagnosis_marks_timeout_straggler_from_existing_artifacts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "B0_600s_wave2_single_eval_001",
        run_id="B0_600s_wave2_single_eval_001",
        status="timeout",
        planned=["70x12", "42x32"],
        completed=["70x12"],
        timed_out=True,
    )

    diagnosis = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)

    assert diagnosis["summary"]["timeout_run_count"] == 1
    assert diagnosis["summary"]["straggler_candidate_keys"] == ["42x32"]
    row = diagnosis["runs"][0]
    assert row["completed_candidate_keys"] == ["70x12"]
    assert row["pending_candidate_keys"] == ["42x32"]
    assert row["straggler_candidate_keys"] == ["42x32"]
    assert row["proof_source"] if "proof_source" in row else diagnosis["proof_source"] is False


def test_wave_diagnosis_uses_summary_diagnostics_when_available(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "B0_600s_wave3_single_eval_001",
        run_id="B0_600s_wave3_single_eval_001",
        status="timeout",
        planned=["70x12", "42x32", "70x19"],
        completed=[],
        timed_out=True,
        summary_completed=["70x12", "70x19"],
    )

    row = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)["runs"][0]

    assert row["completed_candidate_keys"] == ["70x12", "70x19"]
    assert row["pending_candidate_keys"] == ["42x32"]


def test_wave_diagnosis_includes_explicit_isolated_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "experimental_300s_42x32_isolated_eval_001",
        run_id="experimental_300s_42x32_isolated_eval_001",
        status="stopped_resource_limit",
        planned=["42x32"],
        completed=[],
        resource_stop=True,
    )

    diagnosis = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)

    assert diagnosis["summary"]["resource_stop_run_count"] == 1
    assert diagnosis["summary"]["interrupted_candidate_keys"] == ["42x32"]
    assert diagnosis["runs"][0]["run_id"] == "experimental_300s_42x32_isolated_eval_001"


def test_wave_diagnosis_includes_reduced_frontier_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "experimental_300s_reduced_frontier_no_hotspots_eval_001",
        run_id="experimental_300s_reduced_frontier_no_hotspots_eval_001",
        status="completed",
        planned=["70x12", "70x19"],
        completed=["70x12", "70x19"],
    )

    diagnosis = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)

    assert diagnosis["summary"]["resource_stop_run_count"] == 0
    assert diagnosis["runs"][0]["completed_candidate_keys"] == ["70x12", "70x19"]


def test_wave_diagnosis_includes_resource_probe_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "B0_300s_42x32_resource_probe_eval_001",
        run_id="B0_300s_42x32_resource_probe_eval_001",
        status="timeout",
        planned=["42x32"],
        completed=[],
        timed_out=True,
    )

    diagnosis = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)

    assert diagnosis["summary"]["timeout_run_count"] == 1
    assert diagnosis["summary"]["straggler_candidate_keys"] == ["42x32"]
    assert diagnosis["runs"][0]["run_id"] == "B0_300s_42x32_resource_probe_eval_001"


def test_wave_diagnosis_includes_narrow_hotspot_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "local_hotspot_b0_1x4_global_normal_300s_42x32_narrow_eval_001",
        run_id="local_hotspot_b0_1x4_global_normal_300s_42x32_narrow_eval_001",
        status="timeout",
        planned=["42x32"],
        completed=[],
        timed_out=True,
    )

    diagnosis = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)

    assert diagnosis["summary"]["timeout_run_count"] == 1
    assert diagnosis["summary"]["straggler_candidate_keys"] == ["42x32"]
    assert diagnosis["runs"][0]["run_id"] == (
        "local_hotspot_b0_1x4_global_normal_300s_42x32_narrow_eval_001"
    )


def test_wave_diagnosis_includes_local_hotspot_eval_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(
        runs_dir / "local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001",
        run_id="local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001",
        status="timeout",
        planned=["42x32"],
        completed=[],
        timed_out=True,
    )

    diagnosis = build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir)

    assert diagnosis["summary"]["timeout_run_count"] == 1
    assert diagnosis["runs"][0]["run_id"] == "local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001"


def test_wave_diagnosis_write_mode(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "out"
    _write_run(
        runs_dir / "B0_300s_single_eval_001",
        run_id="B0_300s_single_eval_001",
        status="completed",
        planned=["70x12"],
        completed=["70x12"],
    )

    paths = write_checkpoint_free_wave_diagnosis(
        build_checkpoint_free_wave_diagnosis(runs_dir=runs_dir),
        output_dir,
    )

    assert json.loads(paths["json"].read_text(encoding="utf-8"))["schema"] == (
        "phase3b-checkpoint-free-wave-diagnosis/v0"
    )
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_run(
    run_dir: Path,
    *,
    run_id: str,
    status: str,
    planned: list[str],
    completed: list[str],
    timed_out: bool = False,
    resource_stop: bool = False,
    summary_completed: list[str] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for key in completed:
        with (run_dir / "checkpoint_free_eval_results.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"candidate_key": key, "status": "INFEASIBLE"}) + "\n")
    (run_dir / "run_plan.json").write_text(
        json.dumps(
            {
                "wave": {
                    "max_wave_candidates": len(planned),
                    "selected_count": len(planned),
                    "entries": [{"candidate_key": key} for key in planned],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    diagnostics = {}
    if summary_completed is not None:
        diagnostics = {"completed_candidate_keys": summary_completed}
    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "candidate_id": "B0_prod_4x4",
                "status": status,
                "execute": True,
                "requested_duration_seconds": 600,
                "execution": {
                    "result_count": len(completed),
                    "timed_out": timed_out,
                    "resource_stop_triggered": resource_stop,
                    "wave_result_diagnostics": diagnostics,
                },
                "telemetry_summary": {
                    "peak_total_private_bytes": 10 * 1024**3,
                    "peak_total_rss_bytes": 8 * 1024**3,
                },
                "sensitive_path_comparison": {"changed": False},
                "paths": {
                    "run_plan": str(run_dir / "run_plan.json"),
                    "results_jsonl": str(run_dir / "checkpoint_free_eval_results.jsonl"),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.phase3b.s3_lite.build_baseline_scorecard import (
    build_s3_lite_baseline_scorecard,
    extract_acceptance_profiles,
    write_s3_lite_baseline_scorecard,
)


def test_s3_lite_extracts_profile_metrics_and_scores() -> None:
    profiles = extract_acceptance_profiles(_fixture_acceptance())

    by_id = {profile["profile_id"]: profile for profile in profiles}
    assert sorted(by_id) == ["prod_2x4", "prod_4x4"]
    assert by_id["prod_4x4"]["metrics"]["candidate_result_count"] == 8
    assert by_id["prod_4x4"]["metrics"]["unknown_density"] == 0.875
    assert by_id["prod_4x4"]["metrics"]["peak_rss_gib"] is not None
    assert "baseline_normalized_score" not in by_id["prod_4x4"]


def test_s3_lite_scorecard_normalizes_to_requested_baseline(tmp_path: Path) -> None:
    acceptance_path = tmp_path / "acceptance.json"
    tuning_path = tmp_path / "matrix.json"
    acceptance_path.write_text(json.dumps(_fixture_acceptance()), encoding="utf-8")
    tuning_path.write_text(
        json.dumps({"run_count": 1, "runs": [{"profile_id": "dry"}], "safety": {"checkpoint_written": False}}),
        encoding="utf-8",
    )

    scorecard = build_s3_lite_baseline_scorecard(
        project_root=tmp_path,
        acceptance_summary_path=acceptance_path,
        tuning_matrix_summary_path=tuning_path,
        baseline_profile_id="prod_4x4",
    )

    by_id = {profile["profile_id"]: profile for profile in scorecard["profiles"]}
    assert scorecard["metadata"]["evidence_kind"] == "evidence_replay_scorecard"
    assert scorecard["metadata"]["fresh_benchmark_executed"] is False
    assert scorecard["metadata"]["proof_source"] is False
    assert scorecard["baseline"]["profile_id"] == "prod_4x4"
    assert by_id["prod_4x4"]["baseline_normalized_score"]["score"] == 1.0
    assert by_id["prod_2x4"]["baseline_normalized_score"]["score"] is not None
    assert scorecard["local_tuning_smoke"]["run_count"] == 1
    assert scorecard["guard_notes"]["true_s3_rerun_blocked"] is True
    assert scorecard["safety"]["checkpoint_written"] is False


def test_s3_lite_handles_missing_optional_fields(tmp_path: Path) -> None:
    acceptance = {
        "run_records": [
            {
                "label": "prod_minimal",
                "target": "production-campaign-run",
                "completed": True,
                "return_code": 0,
                "process_count": 1,
                "worker_count_per_process": 1,
                "campaign_valid_after_run": True,
                "campaign_telemetry_summary": {"status_counts": {"UNKNOWN": 1}},
            }
        ]
    }
    acceptance_path = tmp_path / "acceptance.json"
    acceptance_path.write_text(json.dumps(acceptance), encoding="utf-8")

    scorecard = build_s3_lite_baseline_scorecard(
        project_root=tmp_path,
        acceptance_summary_path=acceptance_path,
        tuning_matrix_summary_path=tmp_path / "missing-matrix.json",
        baseline_profile_id="prod_minimal",
    )

    profile = scorecard["profiles"][0]
    assert profile["metrics"]["duration_seconds"] is None
    assert profile["metrics"]["candidate_results_per_hour"] is None
    assert profile["metrics"]["unknown_density"] == 1.0
    assert profile["baseline_normalized_score"]["score"] is None
    assert scorecard["local_tuning_smoke"]["available"] is False


def test_s3_lite_write_only_touches_output_dir_and_preserves_sensitive_paths(tmp_path: Path) -> None:
    acceptance_path = tmp_path / "acceptance.json"
    acceptance_path.write_text(json.dumps(_fixture_acceptance()), encoding="utf-8")
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    scorecard = build_s3_lite_baseline_scorecard(
        project_root=tmp_path,
        acceptance_summary_path=acceptance_path,
        tuning_matrix_summary_path=tmp_path / "missing.json",
        baseline_profile_id="prod_4x4",
    )
    output_dir = tmp_path / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "03_baseline_reproduction"
    paths = write_s3_lite_baseline_scorecard(scorecard, output_dir)

    assert Path(paths["json"]).is_file()
    assert Path(paths["md"]).is_file()
    assert _fingerprint(sensitive_file) == before
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    entries = {
        entry["relative_path"]: entry
        for entry in payload["sensitive_path_audit"]["entries"]
    }
    assert entries["data/checkpoints/exact_campaign_state.json"]["exists"] is True
    assert payload["safety"]["scorecard_is_proof_source"] is False


def test_s3_lite_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "s3_lite" / "build_baseline_scorecard.py"
    acceptance_path = tmp_path / "acceptance.json"
    acceptance_path.write_text(json.dumps(_fixture_acceptance()), encoding="utf-8")
    output_dir = tmp_path / "scorecard"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--acceptance-summary",
            str(acceptance_path),
            "--tuning-matrix-summary",
            str(tmp_path / "missing.json"),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write.returncode == 0
    assert "evidence_kind=evidence_replay_scorecard" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--acceptance-summary",
            str(acceptance_path),
            "--tuning-matrix-summary",
            str(tmp_path / "missing.json"),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert (output_dir / "baseline_scorecard.json").exists()
    assert (output_dir / "baseline_scorecard.md").exists()


def _fixture_acceptance() -> dict[str, object]:
    return {
        "run_records": [
            _record(
                label="prod_2x4",
                process_count=2,
                worker_count=4,
                duration=160.0,
                candidate_throughput=0.025,
                peak_rss=20 * 1024**3,
                avg_cpu=17.0,
                status_counts={"INFEASIBLE": 3, "UNKNOWN": 5},
            ),
            _record(
                label="prod_4x4",
                process_count=4,
                worker_count=4,
                duration=200.0,
                candidate_throughput=0.04,
                peak_rss=30 * 1024**3,
                avg_cpu=18.0,
                status_counts={"INFEASIBLE": 1, "UNKNOWN": 7},
            ),
        ]
    }


def _record(
    *,
    label: str,
    process_count: int,
    worker_count: int,
    duration: float,
    candidate_throughput: float,
    peak_rss: int,
    avg_cpu: float,
    status_counts: dict[str, int],
) -> dict[str, object]:
    return {
        "label": label,
        "target": "production-campaign-run",
        "completed": True,
        "return_code": 0,
        "status": "UNKNOWN",
        "process_count": process_count,
        "worker_count_per_process": worker_count,
        "parallel_processes": process_count,
        "worker_profile": {
            "master": worker_count,
            "local_capacity": worker_count,
            "binding": worker_count,
            "routing": worker_count,
        },
        "campaign_valid_after_run": True,
        "campaign_write_mode": "coordinator_atomic_single_writer",
        "elapsed_seconds_parent": duration,
        "candidate_throughput_per_second": candidate_throughput,
        "peak_rss_bytes_external_total": peak_rss,
        "avg_process_cpu_pct": avg_cpu,
        "campaign_telemetry_summary": {
            "candidate_result_count": sum(status_counts.values()),
            "solve_attempt_count": status_counts.get("UNKNOWN", 0),
            "precheck_elimination_count": status_counts.get("INFEASIBLE", 0),
            "status_counts": status_counts,
            "outcome_counts": {"unknown": status_counts.get("UNKNOWN", 0)},
            "master_deterministic_time_sum": 5.0,
        },
    }


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    return (True, path.stat().st_size, path.stat().st_mtime_ns, path.read_text(encoding="utf-8"))

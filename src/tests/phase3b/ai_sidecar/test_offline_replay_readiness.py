from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.phase3b.ai_sidecar.build_offline_replay_readiness import (
    build_ai_offline_replay_readiness,
    read_candidate_runs_jsonl,
    write_ai_offline_replay_readiness,
)


def test_offline_replay_readiness_extracts_coverage_and_missing_telemetry(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    readiness = build_ai_offline_replay_readiness(project_root=tmp_path, **paths)

    assert readiness["schema"] == "phase3b-ai-offline-replay-readiness/v0"
    assert readiness["coverage"]["sample_count"] == 3
    assert readiness["coverage"]["candidate_count"] == 2
    assert readiness["coverage"]["profile_counts"] == {"prod_2x4": 1, "prod_4x4": 2}
    assert readiness["coverage"]["status_counts"] == {"INFEASIBLE": 1, "UNKNOWN": 2}
    assert readiness["coverage"]["label_counts"]["unknown_risk"] == 2
    missing = readiness["missing_telemetry"]["missing_counts"]
    assert missing["solver_metrics.deterministic_time"] == 2
    assert missing["frontier_candidate_metrics"] == 1
    assert "outcome_labels_present_use_only_as_labels_not_features" in readiness["leakage_risk"]["risks"]
    assert readiness["safety"]["model_trained"] is False
    assert readiness["safety"]["candidate_order_changed"] is False
    assert readiness["safety"]["proof_source"] is False


def test_candidate_runs_jsonl_reading_is_deterministic(tmp_path: Path) -> None:
    candidate_runs_path = tmp_path / "candidate_runs.jsonl"
    samples = [_sample("b", "prod_4x4", "UNKNOWN"), _sample("a", "prod_1x1", "INFEASIBLE")]
    candidate_runs_path.write_text(
        "\n".join(json.dumps(sample, sort_keys=True) for sample in samples) + "\n",
        encoding="utf-8",
    )

    first = read_candidate_runs_jsonl(candidate_runs_path)
    second = read_candidate_runs_jsonl(candidate_runs_path)

    assert first == second
    assert [sample["sample_id"] for sample in first] == ["a", "b"]


def test_offline_replay_readiness_write_preserves_sensitive_paths(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    readiness = build_ai_offline_replay_readiness(project_root=tmp_path, **paths)
    output_dir = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "02_offline_replay_readiness"
    output_paths = write_ai_offline_replay_readiness(readiness, output_dir)

    assert _fingerprint(sensitive_file) == before
    assert Path(output_paths["json"]).is_file()
    assert Path(output_paths["md"]).is_file()
    for path in output_paths.values():
        assert str(path).startswith(str(output_dir))
    payload = json.loads(Path(output_paths["json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["checkpoint_written"] is False
    assert payload["sensitive_path_audit"]["canonical_checkpoint_exists"] is True


def test_offline_replay_readiness_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "ai_sidecar" / "build_offline_replay_readiness.py"
    paths = _write_inputs(tmp_path)
    output_dir = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "02_offline_replay_readiness"

    base_args = [
        sys.executable,
        str(script),
        "--project-root",
        str(tmp_path),
        "--candidate-runs",
        str(paths["candidate_runs_path"]),
        "--dataset-summary",
        str(paths["dataset_summary_path"]),
        "--baseline-scorecard",
        str(paths["baseline_scorecard_path"]),
        "--config-matrix-manifest",
        str(paths["config_matrix_manifest_path"]),
        "--stage-worker-manifest",
        str(paths["stage_worker_manifest_path"]),
        "--priority-affinity-manifest",
        str(paths["priority_affinity_manifest_path"]),
        "--output-dir",
        str(output_dir),
    ]

    no_write = subprocess.run(
        [*base_args, "--no-write"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write.returncode == 0
    assert "model_trained=False" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        base_args,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert (output_dir / "offline_replay_readiness.json").exists()
    assert (output_dir / "offline_replay_readiness.md").exists()


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    candidate_runs_path = tmp_path / "candidate_runs.jsonl"
    dataset_summary_path = tmp_path / "dataset_summary.json"
    baseline_scorecard_path = tmp_path / "baseline_scorecard.json"
    config_matrix_manifest_path = tmp_path / "matrix_manifest.json"
    stage_worker_manifest_path = tmp_path / "stage_worker_manifest.json"
    priority_affinity_manifest_path = tmp_path / "affinity_priority_manifest.json"
    samples = [
        _sample("s1", "prod_4x4", "UNKNOWN", deterministic_time=1.0),
        _sample("s2", "prod_4x4", "INFEASIBLE", deterministic_time=None),
        _sample("s3", "prod_2x4", "UNKNOWN", deterministic_time=None, frontier=False),
    ]
    candidate_runs_path.write_text(
        "\n".join(json.dumps(sample, sort_keys=True) for sample in samples) + "\n",
        encoding="utf-8",
    )
    dataset_summary_path.write_text(
        json.dumps(
            {
                "schema": "phase3b_ai_feature_dataset_summary_v0",
                "sample_schema": "phase3b_ai_candidate_run_sample_v0",
                "sample_count": 3,
                "dataset_kind": "evidence_replay_shadow_dataset",
                "safety": {"proof_source": False, "model_trained": False},
            }
        ),
        encoding="utf-8",
    )
    for path in [
        baseline_scorecard_path,
        config_matrix_manifest_path,
        stage_worker_manifest_path,
        priority_affinity_manifest_path,
    ]:
        path.write_text(json.dumps({"schema": path.stem, "profiles": []}), encoding="utf-8")
    return {
        "candidate_runs_path": candidate_runs_path,
        "dataset_summary_path": dataset_summary_path,
        "baseline_scorecard_path": baseline_scorecard_path,
        "config_matrix_manifest_path": config_matrix_manifest_path,
        "stage_worker_manifest_path": stage_worker_manifest_path,
        "priority_affinity_manifest_path": priority_affinity_manifest_path,
    }


def _sample(
    sample_id: str,
    profile_id: str,
    status: str,
    *,
    deterministic_time: float | None = 1.0,
    frontier: bool = True,
) -> dict[str, object]:
    return {
        "schema": "phase3b_ai_candidate_run_sample_v0",
        "sample_id": sample_id,
        "candidate_key": "70x19" if sample_id != "s3" else "69x19",
        "profile_id": profile_id,
        "terminal": {"status": status, "classification": "master_unknown"},
        "labels": {
            "unknown_risk": status == "UNKNOWN",
            "precheck_eliminated": status == "INFEASIBLE",
        },
        "frontier_candidate_metrics": {"certification_prune_gain": 10} if frontier else {},
        "solver_metrics": {
            "wall_time": 10.0 if deterministic_time is not None else None,
            "deterministic_time": deterministic_time,
        },
        "resource_metrics": {
            "avg_process_cpu_percent": 20.0,
            "peak_rss_gib_record": 2.0,
            "rss_gib_at_window": 2.0,
        },
        "safety": {"proof_source": False, "scheduler_integration": False},
    }


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    return (True, path.stat().st_size, path.stat().st_mtime_ns, path.read_text(encoding="utf-8"))

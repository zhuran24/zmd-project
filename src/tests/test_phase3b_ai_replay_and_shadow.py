from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.build_phase3b_ai_offline_replay_v0 import (
    build_phase3b_ai_offline_replay_v0,
    write_phase3b_ai_offline_replay_v0,
)
from scripts.build_phase3b_ai_order_shadow import (
    build_phase3b_ai_order_shadow,
    write_phase3b_ai_order_shadow,
)
from src.ai_accel.feature_extract import stable_json_dumps
from src.ai_accel.replay_scheduler import (
    build_offline_replay_report,
    build_order_shadow_suggestions,
    build_rank_features,
    candidate_universe_hash,
    evaluate_ranked_samples,
    rank_samples,
)


def test_ranker_feature_whitelist_does_not_read_forbidden_fields() -> None:
    sample = _GuardedSample(
        _sample(
            "s1",
            "prod_4x4",
            "UNKNOWN",
            prune_gain=10,
            source_order=(0, 1, 2, 1),
        )
    )

    features = build_rank_features(sample)
    ranked = rank_samples([sample], "hybrid_v0")

    assert features["certification_prune_gain"] == 10.0
    assert ranked[0]["sample_id"] == "s1"


def test_offline_replay_metrics_compare_default_and_prune_gain() -> None:
    samples = [
        _sample("s1", "prod_4x4", "UNKNOWN", prune_gain=1, source_order=(0, 1, 0, 1)),
        _sample("s2", "prod_4x4", "INFEASIBLE", prune_gain=50, source_order=(0, 1, 1, 1)),
        _sample("s3", "prod_4x4", "UNKNOWN", prune_gain=5, source_order=(0, 1, 2, 1)),
    ]

    default_metrics = evaluate_ranked_samples(rank_samples(samples, "default_evidence_order"), top_k=2)
    prune_metrics = evaluate_ranked_samples(rank_samples(samples, "prune_gain_first"), top_k=2)

    assert default_metrics["first_useful_hit_index"] == 2
    assert prune_metrics["first_useful_hit_index"] == 1
    assert prune_metrics["top_k_useful_density"] >= default_metrics["top_k_useful_density"]
    assert prune_metrics["replay_score"] > default_metrics["replay_score"]


def test_offline_replay_report_and_shadow_suggestions_are_deterministic() -> None:
    samples = _fixture_samples()

    first_report = build_offline_replay_report(samples)
    second_report = build_offline_replay_report(samples)
    first_suggestions = build_order_shadow_suggestions(samples, first_report)
    second_suggestions = build_order_shadow_suggestions(samples, second_report)

    assert stable_json_dumps(first_report) == stable_json_dumps(second_report)
    assert stable_json_dumps(first_suggestions) == stable_json_dumps(second_suggestions)
    assert first_report["safety"]["model_trained"] is False
    assert first_report["safety"]["scheduler_integration"] is False
    assert first_suggestions["safety"]["candidate_order_changed"] is False


def test_shadow_suggestion_candidate_universe_contract() -> None:
    samples = _fixture_samples()
    report = build_offline_replay_report(samples)
    suggestions = build_order_shadow_suggestions(samples, report)

    assert suggestions["candidate_universe"]["input_hash"] == candidate_universe_hash(samples)
    assert suggestions["candidate_universe"]["input_hash"] == suggestions["candidate_universe"]["output_hash"]
    assert suggestions["candidate_universe"]["changed"] is False
    assert suggestions["candidate_universe"]["input_count"] == suggestions["candidate_universe"]["output_count"]
    assert suggestions["candidate_universe"]["has_duplicate_output_entries"] is False
    assert suggestions["ab_gate"]["status"] == "blocked_diagnostic_only"


def test_replay_and_shadow_builders_preserve_sensitive_paths(tmp_path: Path) -> None:
    candidate_runs_path, readiness_path = _write_replay_inputs(tmp_path)
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    report = build_phase3b_ai_offline_replay_v0(
        project_root=tmp_path,
        candidate_runs_path=candidate_runs_path,
        replay_readiness_path=readiness_path,
    )
    replay_output = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "03_offline_replay_v0"
    replay_paths = write_phase3b_ai_offline_replay_v0(report, replay_output)
    suggestions = build_phase3b_ai_order_shadow(
        project_root=tmp_path,
        candidate_runs_path=candidate_runs_path,
        offline_replay_report_path=Path(replay_paths["json"]),
    )
    shadow_output = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "04_order_shadow"
    shadow_paths = write_phase3b_ai_order_shadow(suggestions, shadow_output)

    assert _fingerprint(sensitive_file) == before
    assert Path(replay_paths["json"]).is_file()
    assert Path(replay_paths["md"]).is_file()
    assert Path(shadow_paths["json"]).is_file()
    assert Path(shadow_paths["md"]).is_file()
    assert report["sensitive_path_audit"]["canonical_checkpoint_exists"] is True
    assert suggestions["sensitive_path_audit"]["canonical_checkpoint_exists"] is True
    assert suggestions["safety"]["checkpoint_written"] is False


def test_replay_and_shadow_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    replay_script = repo_root / "scripts" / "build_phase3b_ai_offline_replay_v0.py"
    shadow_script = repo_root / "scripts" / "build_phase3b_ai_order_shadow.py"
    candidate_runs_path, readiness_path = _write_replay_inputs(tmp_path)
    replay_output = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "03_offline_replay_v0"
    shadow_output = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "04_order_shadow"

    replay_base_args = [
        sys.executable,
        str(replay_script),
        "--project-root",
        str(tmp_path),
        "--candidate-runs",
        str(candidate_runs_path),
        "--replay-readiness",
        str(readiness_path),
        "--output-dir",
        str(replay_output),
    ]
    replay_no_write = subprocess.run(
        [*replay_base_args, "--no-write"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert replay_no_write.returncode == 0
    assert "model_trained=False" in replay_no_write.stdout
    assert not replay_output.exists()

    replay_write = subprocess.run(
        replay_base_args,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert replay_write.returncode == 0
    replay_report_path = replay_output / "offline_replay_report.json"
    assert replay_report_path.exists()

    shadow_base_args = [
        sys.executable,
        str(shadow_script),
        "--project-root",
        str(tmp_path),
        "--candidate-runs",
        str(candidate_runs_path),
        "--offline-replay-report",
        str(replay_report_path),
        "--output-dir",
        str(shadow_output),
    ]
    shadow_no_write = subprocess.run(
        [*shadow_base_args, "--no-write"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert shadow_no_write.returncode == 0
    assert "scheduler_integration=False" in shadow_no_write.stdout
    assert not shadow_output.exists()

    shadow_write = subprocess.run(
        shadow_base_args,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert shadow_write.returncode == 0
    assert (shadow_output / "candidate_rank_suggestions.json").exists()
    assert (shadow_output / "shadow_order_diff.md").exists()


class _GuardedSample(dict):
    _forbidden = {"terminal", "labels", "solver_metrics", "precheck", "resource_metrics"}

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        if key in self._forbidden:
            raise AssertionError(f"ranker accessed forbidden field: {key}")
        return super().get(key, default)


def _write_replay_inputs(tmp_path: Path) -> tuple[Path, Path]:
    candidate_runs_path = tmp_path / "candidate_runs.jsonl"
    readiness_path = tmp_path / "offline_replay_readiness.json"
    candidate_runs_path.write_text(
        "\n".join(stable_json_dumps(sample) for sample in _fixture_samples()) + "\n",
        encoding="utf-8",
    )
    readiness_path.write_text(
        json.dumps(
            {
                "readiness": {"status": "ready_for_read_only_offline_replay_planning"},
                "coverage": {"sample_count": len(_fixture_samples()), "candidate_count": 3},
                "leakage_risk": {"risk_level": "medium"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return candidate_runs_path, readiness_path


def _fixture_samples() -> list[dict[str, object]]:
    return [
        _sample("s1", "prod_4x4", "UNKNOWN", prune_gain=1, source_order=(0, 1, 0, 1)),
        _sample("s2", "prod_4x4", "INFEASIBLE", prune_gain=50, source_order=(0, 1, 1, 1)),
        _sample("s3", "prod_4x4", "UNKNOWN", prune_gain=5, source_order=(0, 1, 2, 1)),
        _sample("s4", "prod_2x4", "UNKNOWN", prune_gain=1, source_order=(1, 1, 0, 1)),
        _sample("s5", "prod_2x4", "INFEASIBLE", prune_gain=25, source_order=(1, 1, 1, 1)),
    ]


def _sample(
    sample_id: str,
    profile_id: str,
    status: str,
    *,
    prune_gain: int,
    source_order: tuple[int, int, int, int],
) -> dict[str, object]:
    record_index, wave_index, dispatch_seq, attempt_index = source_order
    return {
        "schema": "phase3b_ai_candidate_run_sample_v0",
        "sample_id": sample_id,
        "candidate_key": "70x19" if sample_id not in {"s3", "s5"} else "69x19",
        "profile_id": profile_id,
        "source": {
            "record_index": record_index,
            "wave_index": wave_index,
            "dispatch_seq": dispatch_seq,
            "attempt_index": attempt_index,
        },
        "selection_reason": "prune_head",
        "frontier_candidate_metrics": {
            "certification_prune_gain": prune_gain,
            "anchor_count": 10,
        },
        "parallel_processes": 4,
        "process_count": 4,
        "worker_count_per_process": 4,
        "worker_profile": {"master": 4, "local_capacity": 4, "binding": 4, "routing": 4},
        "terminal": {"status": status, "classification": "master_unknown"},
        "labels": {
            "unknown_risk": status == "UNKNOWN",
            "precheck_eliminated": status == "INFEASIBLE",
            "high_prune_gain": prune_gain >= 25,
        },
        "solver_metrics": {"wall_time": None, "deterministic_time": None},
        "precheck": {"eliminated": status == "INFEASIBLE"},
        "resource_metrics": {"avg_process_cpu_percent": 20.0},
        "safety": {"proof_source": False, "scheduler_integration": False},
    }


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    return (True, path.stat().st_size, path.stat().st_mtime_ns, path.read_text(encoding="utf-8"))

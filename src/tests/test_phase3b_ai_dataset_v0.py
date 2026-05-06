from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_phase3b_ai_dataset_v0 import (
    build_phase3b_ai_dataset_v0,
    render_samples_for_test,
    write_phase3b_ai_dataset_v0,
)
from src.ai_accel.feature_extract import extract_candidate_run_samples


def test_ai_dataset_extracts_candidate_samples_from_acceptance_fixture() -> None:
    samples = extract_candidate_run_samples(
        _fixture_acceptance(),
        scorecard_payload=_fixture_scorecard(),
    )

    assert len(samples) == 3
    first = samples[0]
    assert first["schema"] == "phase3b_ai_candidate_run_sample_v0"
    assert first["profile_id"] == "prod_2x4"
    assert first["candidate_key"] == "70x19"
    assert first["precheck"]["eliminated"] is True
    assert first["terminal"]["classification"] == "precheck_eliminated"
    assert first["labels"]["precheck_eliminated"] is True
    unknown = [sample for sample in samples if sample["terminal"]["status"] == "UNKNOWN"][0]
    assert unknown["terminal"]["classification"] == "master_unknown"
    assert unknown["solver_metrics"]["deterministic_time"] == 5.25
    assert unknown["labels"]["unknown_risk"] is True
    assert unknown["safety"]["scheduler_integration"] is False


def test_ai_dataset_jsonl_is_deterministic_for_same_input() -> None:
    samples_a = extract_candidate_run_samples(_fixture_acceptance(), scorecard_payload=_fixture_scorecard())
    samples_b = extract_candidate_run_samples(_fixture_acceptance(), scorecard_payload=_fixture_scorecard())

    assert render_samples_for_test(samples_a) == render_samples_for_test(samples_b)


def test_ai_dataset_handles_missing_optional_telemetry() -> None:
    payload = {
        "run_records": [
            {
                "label": "prod_minimal",
                "target": "production-campaign-run",
                "campaign_wave_summaries": [
                    {
                        "wave_index": 1,
                        "candidate_results": [
                            {
                                "candidate_key": "1x1",
                                "status": "UNKNOWN",
                                "outcome_category": "unknown",
                                "proof_status_summary": {},
                            }
                        ],
                    }
                ],
            }
        ]
    }

    samples = extract_candidate_run_samples(payload)

    assert len(samples) == 1
    sample = samples[0]
    assert sample["solver_metrics"]["wall_time"] is None
    assert sample["resource_metrics"]["rss_gib_at_window"] is None
    assert sample["frontier_candidate_metrics"] == {}


def test_ai_dataset_write_only_ai_namespace_and_preserves_sensitive_paths(tmp_path: Path) -> None:
    acceptance_path = tmp_path / "acceptance.json"
    scorecard_path = tmp_path / "scorecard.json"
    acceptance_path.write_text(json.dumps(_fixture_acceptance()), encoding="utf-8")
    scorecard_path.write_text(json.dumps(_fixture_scorecard()), encoding="utf-8")
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    dataset = build_phase3b_ai_dataset_v0(
        project_root=tmp_path,
        acceptance_summary_path=acceptance_path,
        baseline_scorecard_path=scorecard_path,
    )
    output_dir = tmp_path / ".artifacts" / "phase3b_ai_accel_20260430" / "01_feature_dataset"
    paths = write_phase3b_ai_dataset_v0(dataset, output_dir)

    assert _fingerprint(sensitive_file) == before
    assert Path(paths["candidate_runs_jsonl"]).is_file()
    assert Path(paths["feature_schema_json"]).is_file()
    assert Path(paths["dataset_summary_json"]).is_file()
    assert Path(paths["dataset_summary_md"]).is_file()
    for path in paths.values():
        assert str(path).startswith(str(output_dir))
    summary = json.loads(Path(paths["dataset_summary_json"]).read_text(encoding="utf-8"))
    assert summary["safety"]["proof_source"] is False
    assert summary["safety"]["model_trained"] is False


def test_ai_dataset_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_ai_dataset_v0.py"
    acceptance_path = tmp_path / "acceptance.json"
    scorecard_path = tmp_path / "scorecard.json"
    output_dir = tmp_path / "dataset"
    acceptance_path.write_text(json.dumps(_fixture_acceptance()), encoding="utf-8")
    scorecard_path.write_text(json.dumps(_fixture_scorecard()), encoding="utf-8")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--acceptance-summary",
            str(acceptance_path),
            "--baseline-scorecard",
            str(scorecard_path),
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
    assert "sample_count=3" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--acceptance-summary",
            str(acceptance_path),
            "--baseline-scorecard",
            str(scorecard_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert (output_dir / "candidate_runs.jsonl").exists()
    assert (output_dir / "feature_schema.json").exists()
    assert (output_dir / "dataset_summary.json").exists()


def _fixture_acceptance() -> dict[str, object]:
    return {
        "logical_cpu_count": 24,
        "run_records": [
            _record("prod_4x4", 4, 4, ["70x19", "69x19"]),
            _record("prod_2x4", 2, 4, ["70x19"]),
        ],
    }


def _record(label: str, process_count: int, worker_count: int, candidates: list[str]) -> dict[str, object]:
    candidate_results = []
    for index, candidate_key in enumerate(candidates):
        if index == 0:
            candidate_results.append(
                {
                    "candidate_key": candidate_key,
                    "dispatch_seq": index,
                    "attempt_index": 1,
                    "wave_slot_index": index,
                    "selection_reason": "prune_head",
                    "status": "INFEASIBLE",
                    "outcome_category": "master_infeasible",
                    "proof_status_summary": {
                        "master_candidate_precheck": {
                            "triggered": True,
                            "master_solve_skipped": True,
                            "precheck_reason": "boundary_port_all_anchors_infeasible",
                            "screened_infeasible_anchor_count": 12,
                            "screen_pass_anchor_count": 0,
                        },
                        "frontier_candidate_metrics": {
                            "certification_prune_gain": 120,
                            "anchor_count": 10,
                        },
                    },
                }
            )
        else:
            candidate_results.append(
                {
                    "candidate_key": candidate_key,
                    "dispatch_seq": index,
                    "attempt_index": 1,
                    "wave_slot_index": index,
                    "selection_reason": "prune_head",
                    "status": "UNKNOWN",
                    "outcome_category": "unknown",
                    "proof_status_summary": {
                        "master_candidate_precheck": {
                            "triggered": False,
                            "master_solve_skipped": False,
                        },
                        "frontier_candidate_metrics": {
                            "certification_prune_gain": 20,
                            "anchor_count": 10,
                        },
                        "master_last_solve": {
                            "status": "UNKNOWN",
                            "wall_time": 30.0,
                            "deterministic_time": 5.25,
                            "branches": 0,
                            "conflicts": 0,
                            "hinted_literals": 99,
                            "search_profile": "test_profile",
                        },
                        "master_start_feasibility": {
                            "ghost_anchor_hint_status": "skipped_anchor_limit",
                        },
                    },
                }
            )
    return {
        "label": label,
        "target": "production-campaign-run",
        "process_count": process_count,
        "parallel_processes": process_count,
        "worker_count_per_process": worker_count,
        "worker_profile": {
            "master": worker_count,
            "local_capacity": worker_count,
            "binding": worker_count,
            "routing": worker_count,
        },
        "avg_process_cpu_pct": 24.0,
        "peak_rss_bytes_external_total": 2 * 1024**3,
        "output_json": f"{label}__fixture.json",
        "campaign_wave_summaries": [
            {
                "wave_index": 1,
                "elapsed_seconds": 10.0,
                "peak_rss_bytes_external_total": 2 * 1024**3,
                "candidate_results": candidate_results,
            }
        ],
    }


def _fixture_scorecard() -> dict[str, object]:
    return {
        "profiles": [
            {
                "profile_id": "prod_4x4",
                "baseline_normalized_score": {"score": 1.0, "baseline_profile_id": "prod_4x4"},
            },
            {
                "profile_id": "prod_2x4",
                "baseline_normalized_score": {"score": 1.2, "baseline_profile_id": "prod_4x4"},
            },
        ]
    }


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    return (True, path.stat().st_size, path.stat().st_mtime_ns, path.read_text(encoding="utf-8"))

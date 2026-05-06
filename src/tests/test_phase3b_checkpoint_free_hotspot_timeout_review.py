from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_hotspot_timeout_review import (
    build_hotspot_timeout_review,
    write_hotspot_timeout_review,
)


def test_hotspot_timeout_review_classifies_timeout_without_resource_stop(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    log_dir = tmp_path / "log"
    revision_path = tmp_path / "revision.json"
    _write_run_fixture(run_dir)
    _write_telemetry_fixture(log_dir)
    _write_revision(revision_path)

    review = build_hotspot_timeout_review(
        run_dir=run_dir,
        log_dir=log_dir,
        resource_strategy_revision_path=revision_path,
    )

    assert review["run"]["run_id"] == "B0_prod_4x4_300s_42x32_resource_probe_eval_001"
    assert review["run"]["candidate_key"] == "42x32"
    assert review["run"]["timed_out"] is True
    assert review["run"]["resource_stop_triggered"] is False
    assert review["interpretation"]["classification"] == "bounded_timeout_high_memory_straggler"
    assert review["recommendation"]["action"] == "hold_hotspot_followups_pending_narrower_timeout_strategy"
    assert review["recommendation"]["allowed_followup_probe_ids"] == []
    assert "do_not_run_67x20_hotspot_followup_yet" in review["recommendation"]["blocked_actions"]
    assert round(review["telemetry_review"]["peak_total_private_gib"], 3) == 32.0
    assert review["telemetry_review"]["dominant_process_pid"] == 42
    assert review["proof_source"] is False
    assert review["checkpoint_written"] is False


def test_hotspot_timeout_review_write_mode(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    log_dir = tmp_path / "log"
    revision_path = tmp_path / "revision.json"
    output_dir = tmp_path / "out"
    _write_run_fixture(run_dir)
    _write_telemetry_fixture(log_dir)
    _write_revision(revision_path)

    paths = write_hotspot_timeout_review(
        build_hotspot_timeout_review(
            run_dir=run_dir,
            log_dir=log_dir,
            resource_strategy_revision_path=revision_path,
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "hotspot_timeout_review.json"
    assert paths["md"] == output_dir / "hotspot_timeout_review.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema"] == "phase3b-checkpoint-free-hotspot-timeout-review/v0"
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_run_fixture(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "run_id": "B0_prod_4x4_300s_42x32_resource_probe_eval_001",
                "candidate_id": "B0_prod_4x4",
                "status": "timeout",
                "duration_seconds": 330.0,
                "requested_duration_seconds": 300,
                "checkpoint_free": True,
                "proof_source": False,
                "checkpoint_written": False,
                "execution": {
                    "result_count": 0,
                    "timed_out": True,
                    "resource_stop_triggered": False,
                    "wave_result_diagnostics": {
                        "pending_candidate_keys": ["42x32"],
                        "straggler_candidate_keys": ["42x32"],
                    },
                },
                "telemetry_summary": {
                    "peak_total_private_bytes": 32 * 1024**3,
                    "peak_total_rss_bytes": 26 * 1024**3,
                    "peak_total_cpu_percent": 500.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "run_plan.json").write_text(
        json.dumps(
            {
                "wave": {
                    "entries": [{"candidate_key": "42x32"}],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "sensitive_path_comparison.json").write_text(
        json.dumps({"changed": False, "changed_paths": []}) + "\n",
        encoding="utf-8",
    )


def _write_telemetry_fixture(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    samples = [
        _sample(10, 8, 100, [(1, 1, 1), (42, 4, 3)]),
        _sample(32, 26, 500, [(1, 1, 1), (42, 20, 18)]),
        _sample(31, 25, 300, [(1, 1, 1), (42, 19, 17)]),
    ]
    with (log_dir / "telemetry_samples.jsonl").open("w", encoding="utf-8") as fh:
        for sample in samples:
            fh.write(json.dumps(sample) + "\n")


def _sample(
    total_private_gib: int,
    total_rss_gib: int,
    cpu: float,
    processes: list[tuple[int, int, int]],
) -> dict[str, object]:
    return {
        "aggregate": {
            "process_count": len(processes),
            "thread_count": 10,
            "total_private_bytes": total_private_gib * 1024**3,
            "total_rss_bytes": total_rss_gib * 1024**3,
            "total_cpu_percent": cpu,
        },
        "processes": [
            {
                "pid": pid,
                "memory": {
                    "private_bytes": private_gib * 1024**3,
                    "rss_bytes": rss_gib * 1024**3,
                },
            }
            for pid, private_gib, rss_gib in processes
        ],
    }


def _write_revision(path: Path) -> None:
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

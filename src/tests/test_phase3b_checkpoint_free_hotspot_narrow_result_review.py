from __future__ import annotations

import json
from pathlib import Path

from scripts.build_phase3b_checkpoint_free_hotspot_narrow_result_review import (
    OPTIONAL_CONFIRMATION_RUN_IDS,
    RUN_IDS,
    build_hotspot_narrow_result_review,
    write_hotspot_narrow_result_review,
)


def test_hotspot_narrow_result_review_classifies_memory_controlled_straggler(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_chain(runs_dir)

    review = build_hotspot_narrow_result_review(
        runs_dir=runs_dir,
        augmented_readiness_path=tmp_path / "hotspot_augmented_readiness_packet.json",
    )

    assert review["interpretation"]["classification"] == "memory_controlled_compute_straggler_at_300s"
    assert review["interpretation"]["all_runs_clean"] is True
    assert review["interpretation"]["all_runs_timeout_no_result"] is True
    assert review["interpretation"]["monotonic_memory_reduction"] is True
    assert review["recommendation"]["action"] == "prepare_single_600s_1x1_confirmation_probe"
    assert review["recommendation"]["next_duration_seconds"] == 600
    command = review["recommendation"]["execute_command_after_review"]
    assert "--execute" in command
    assert "--duration-seconds" in command
    assert "600" in command
    assert "--wave-candidate-key" in command
    assert "42x32" in command
    assert review["safety"]["builder_executes_solver"] is False
    assert review["checkpoint_written"] is False
    assert review["proof_source"] is False


def test_hotspot_narrow_result_review_holds_after_600s_confirmation_timeout(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_chain(runs_dir)
    _write_summary(
        runs_dir / OPTIONAL_CONFIRMATION_RUN_IDS[0] / "run_summary.json",
        run_id=OPTIONAL_CONFIRMATION_RUN_IDS[0],
        peak_private_gib=11.9,
    )

    review = build_hotspot_narrow_result_review(
        runs_dir=runs_dir,
        augmented_readiness_path=tmp_path / "hotspot_augmented_readiness_packet.json",
    )

    assert review["interpretation"]["classification"] == "memory_controlled_compute_straggler_at_600s"
    assert review["interpretation"]["confirmation_600s_present"] is True
    assert review["interpretation"]["confirmation_600s_timeout_no_result"] is True
    assert review["recommendation"]["action"] == "hold_hotspot_algorithmic_strategy_review"
    assert review["recommendation"]["execute_command_after_review"] == []
    assert review["confirmation_runs"][0]["run_id"] == OPTIONAL_CONFIRMATION_RUN_IDS[0]


def test_hotspot_narrow_result_review_holds_on_sensitive_mutation(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_chain(runs_dir, sensitive_last=True)

    review = build_hotspot_narrow_result_review(
        runs_dir=runs_dir,
        augmented_readiness_path=tmp_path / "hotspot_augmented_readiness_packet.json",
    )

    assert review["recommendation"]["action"] == "hold_manual_review"
    assert review["recommendation"]["execute_command_after_review"] == []
    assert review["safety"]["sensitive_path_mutation_detected"] is True


def test_hotspot_narrow_result_review_write_mode(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "out"
    _write_chain(runs_dir)

    paths = write_hotspot_narrow_result_review(
        build_hotspot_narrow_result_review(
            runs_dir=runs_dir,
            augmented_readiness_path=tmp_path / "hotspot_augmented_readiness_packet.json",
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "hotspot_narrow_result_review.json"
    assert paths["md"] == output_dir / "hotspot_narrow_result_review.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema"] == "phase3b-checkpoint-free-hotspot-narrow-result-review/v0"
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")


def _write_chain(runs_dir: Path, *, sensitive_last: bool = False) -> None:
    peaks = [32.8, 22.7, 16.6, 11.9]
    for index, run_id in enumerate(RUN_IDS):
        _write_summary(
            runs_dir / run_id / "run_summary.json",
            run_id=run_id,
            peak_private_gib=peaks[index],
            sensitive_changed=sensitive_last and index == len(RUN_IDS) - 1,
        )


def _write_summary(
    path: Path,
    *,
    run_id: str,
    peak_private_gib: float,
    sensitive_changed: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "candidate_id": run_id.split("_300s_")[0],
                "status": "timeout",
                "requested_duration_seconds": 300,
                "duration_seconds": 330.0,
                "checkpoint_free": True,
                "proof_source": False,
                "checkpoint_written": False,
                "execution": {
                    "result_count": 0,
                    "timed_out": True,
                    "resource_stop_triggered": False,
                },
                "telemetry_summary": {
                    "peak_total_private_bytes": int(peak_private_gib * 1024**3),
                    "peak_total_rss_bytes": int((peak_private_gib - 2) * 1024**3),
                    "peak_total_cpu_percent": 100.0,
                },
                "sensitive_path_comparison": {"changed": sensitive_changed},
            }
        )
        + "\n",
        encoding="utf-8",
    )

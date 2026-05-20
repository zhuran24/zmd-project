from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
RUNS_DIR = ARTIFACT_ROOT / "08_checkpoint_free_evaluator"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "16_hotspot_narrow_strategy"
DEFAULT_AUGMENTED_READINESS = DEFAULT_OUTPUT_DIR / "hotspot_augmented_readiness_packet.json"

RUN_IDS = [
    "B0_prod_4x4_300s_42x32_resource_probe_eval_001",
    "local_hotspot_b0_1x4_global_normal_300s_42x32_eval_001",
    "local_hotspot_b0_1x2_global_normal_300s_42x32_eval_001",
    "local_hotspot_b0_1x1_global_normal_300s_42x32_eval_001",
]
OPTIONAL_CONFIRMATION_RUN_IDS = [
    "local_hotspot_b0_1x1_global_normal_600s_42x32_eval_001",
]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_hotspot_narrow_result_review(
        runs_dir=_resolve_path(PROJECT_ROOT, args.runs_dir),
        augmented_readiness_path=_resolve_path(PROJECT_ROOT, args.augmented_readiness),
    )
    print("phase3b checkpoint-free hotspot narrow result review")
    print(f"run_count={len(review['runs'])}")
    print(f"action={review['recommendation']['action']}")
    if not args.no_write:
        paths = write_hotspot_narrow_result_review(review, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"review_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"review_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize B0/1x4/1x2/1x1 42x32 hotspot narrow checkpoint-free results."
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--augmented-readiness", type=Path, default=DEFAULT_AUGMENTED_READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_hotspot_narrow_result_review(
    *,
    runs_dir: Path,
    augmented_readiness_path: Path,
) -> dict[str, Any]:
    runs_dir = Path(runs_dir)
    runs = [_run_row(_load_json(runs_dir / run_id / "run_summary.json")) for run_id in RUN_IDS]
    confirmation_runs = [
        _run_row(_load_json(summary_path))
        for run_id in OPTIONAL_CONFIRMATION_RUN_IDS
        for summary_path in [runs_dir / run_id / "run_summary.json"]
        if summary_path.exists()
    ]
    all_runs = [*runs, *confirmation_runs]
    clean = all(
        not run["sensitive_path_changed"] and not run["resource_stop_triggered"] for run in all_runs
    )
    all_timeout = all(run["status"] == "timeout" and run["result_count"] == 0 for run in runs)
    peak_values = [run["peak_private_gib"] for run in runs if run["peak_private_gib"] is not None]
    monotonic_memory_reduction = all(
        earlier >= later for earlier, later in zip(peak_values, peak_values[1:])
    )
    return {
        "schema": "phase3b-checkpoint-free-hotspot-narrow-result-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "review_kind": "local_checkpoint_free_hotspot_narrow_result_review",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "runs_dir": str(runs_dir),
        "augmented_readiness_path": str(augmented_readiness_path),
        "runs": runs,
        "confirmation_runs": confirmation_runs,
        "interpretation": {
            "all_runs_clean": clean,
            "all_runs_timeout_no_result": all_timeout,
            "confirmation_600s_present": bool(confirmation_runs),
            "confirmation_600s_timeout_no_result": all(
                run["status"] == "timeout" and run["result_count"] == 0 for run in confirmation_runs
            )
            if confirmation_runs
            else None,
            "monotonic_memory_reduction": monotonic_memory_reduction,
            "memory_reduction_b0_to_1x1_gib": (
                round(runs[0]["peak_private_gib"] - runs[-1]["peak_private_gib"], 3)
                if runs[0]["peak_private_gib"] is not None and runs[-1]["peak_private_gib"] is not None
                else None
            ),
            "classification": (
                "memory_controlled_compute_straggler_at_600s"
                if clean
                and all_timeout
                and monotonic_memory_reduction
                and confirmation_runs
                and all(run["status"] == "timeout" and run["result_count"] == 0 for run in confirmation_runs)
                else "memory_controlled_compute_straggler_at_300s"
                if clean and all_timeout and monotonic_memory_reduction
                else "manual_review_required"
            ),
        },
        "recommendation": _recommendation(
            clean,
            all_timeout,
            monotonic_memory_reduction,
            confirmation_runs=confirmation_runs,
        ),
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "scheduler_integration": False,
            "builder_executes_solver": False,
            "sensitive_path_mutation_detected": any(
                run["sensitive_path_changed"] for run in all_runs
            ),
            "resource_stop_detected": any(run["resource_stop_triggered"] for run in all_runs),
        },
    }


def write_hotspot_narrow_result_review(review: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hotspot_narrow_result_review.json"
    md_path = output_dir / "hotspot_narrow_result_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_hotspot_narrow_result_review_markdown(review), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_hotspot_narrow_result_review_markdown(review: Mapping[str, Any]) -> str:
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    lines = [
        "# Phase3B Hotspot Narrow Result Review",
        "",
        f"- Generated: `{review.get('generated_at')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- All runs clean: `{str(interpretation.get('all_runs_clean')).lower()}`",
        f"- All runs timeout/no-result: `{str(interpretation.get('all_runs_timeout_no_result')).lower()}`",
        f"- 600s confirmation present: `{str(interpretation.get('confirmation_600s_present')).lower()}`",
        f"- 600s confirmation timeout/no-result: `{interpretation.get('confirmation_600s_timeout_no_result')}`",
        f"- Monotonic memory reduction: `{str(interpretation.get('monotonic_memory_reduction')).lower()}`",
        f"- Memory reduction B0 to 1x1 GiB: `{interpretation.get('memory_reduction_b0_to_1x1_gib')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Runs",
        "",
        "| Run | Candidate | Status | Results | Peak private GiB | Peak CPU % | Sensitive changed | Resource stop |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for run in list(review.get("runs", []) or []):
        lines.append(
            "| {run_id} | {candidate_id} | {status} | {result_count} | {peak_private_gib:.3f} | {peak_cpu_percent:.1f} | {sensitive_path_changed} | {resource_stop_triggered} |".format(
                run_id=run.get("run_id"),
                candidate_id=run.get("candidate_id"),
                status=run.get("status"),
                result_count=run.get("result_count"),
                peak_private_gib=run.get("peak_private_gib") or 0.0,
                peak_cpu_percent=run.get("peak_cpu_percent") or 0.0,
                sensitive_path_changed=run.get("sensitive_path_changed"),
                resource_stop_triggered=run.get("resource_stop_triggered"),
            )
        )
    for run in list(review.get("confirmation_runs", []) or []):
        lines.append(
            "| {run_id} | {candidate_id} | {status} | {result_count} | {peak_private_gib:.3f} | {peak_cpu_percent:.1f} | {sensitive_path_changed} | {resource_stop_triggered} |".format(
                run_id=run.get("run_id"),
                candidate_id=run.get("candidate_id"),
                status=run.get("status"),
                result_count=run.get("result_count"),
                peak_private_gib=run.get("peak_private_gib") or 0.0,
                peak_cpu_percent=run.get("peak_cpu_percent") or 0.0,
                sensitive_path_changed=run.get("sensitive_path_changed"),
                resource_stop_triggered=run.get("resource_stop_triggered"),
            )
        )
    lines.extend(
        [
            "",
            "This review only prepares the next local diagnostic step. It does not authorize canonical checkpoints, proof promotion, production default changes, or full-wave retry.",
            "",
        ]
    )
    return "\n".join(lines)


def _run_row(summary: Mapping[str, Any]) -> dict[str, Any]:
    execution = _mapping(summary.get("execution"))
    telemetry = _mapping(summary.get("telemetry_summary"))
    sensitive = _mapping(summary.get("sensitive_path_comparison"))
    return {
        "run_id": str(summary.get("run_id")),
        "candidate_id": str(summary.get("candidate_id")),
        "status": str(summary.get("status")),
        "requested_duration_seconds": int(summary.get("requested_duration_seconds") or 0),
        "duration_seconds": _float(summary.get("duration_seconds")),
        "result_count": int(execution.get("result_count") or 0),
        "timed_out": bool(execution.get("timed_out")),
        "resource_stop_triggered": bool(execution.get("resource_stop_triggered")),
        "sensitive_path_changed": bool(sensitive.get("changed")),
        "peak_private_gib": _bytes_to_gib(telemetry.get("peak_total_private_bytes")),
        "peak_rss_gib": _bytes_to_gib(telemetry.get("peak_total_rss_bytes")),
        "peak_cpu_percent": _float(telemetry.get("peak_total_cpu_percent")) or 0.0,
        "checkpoint_free": bool(summary.get("checkpoint_free")),
        "proof_source": bool(summary.get("proof_source")),
        "checkpoint_written": bool(summary.get("checkpoint_written")),
    }


def _recommendation(
    clean: bool,
    all_timeout: bool,
    monotonic_memory_reduction: bool,
    *,
    confirmation_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ready = clean and all_timeout and monotonic_memory_reduction
    confirmation_timeout = bool(confirmation_runs) and all(
        run["status"] == "timeout" and run["result_count"] == 0 for run in confirmation_runs
    )
    command = [
        "python",
        "scripts/run_phase3b_checkpoint_free_evaluator.py",
        "--execute",
        "--readiness-packet",
        str(DEFAULT_AUGMENTED_READINESS),
        "--candidate-id",
        "local_hotspot_b0_1x1_global_normal",
        "--duration-seconds",
        "600",
        "--max-wave-candidates",
        "1",
        "--wave-candidate-key",
        "42x32",
        "--run-id",
        "local_hotspot_b0_1x1_global_normal_600s_42x32_eval_001",
    ]
    return {
        "action": (
            "hold_hotspot_algorithmic_strategy_review"
            if ready and confirmation_timeout
            else "prepare_single_600s_1x1_confirmation_probe"
            if ready
            else "hold_manual_review"
        ),
        "next_candidate_id": "local_hotspot_b0_1x1_global_normal"
        if ready and not confirmation_timeout
        else None,
        "next_candidate_key": "42x32" if ready and not confirmation_timeout else None,
        "next_duration_seconds": 600 if ready and not confirmation_timeout else None,
        "execute_command_after_review": command if ready and not confirmation_timeout else [],
        "next_engineering_step": (
            "stop extending short hotspot probes and design an algorithmic/candidate-level hotspot strategy"
            if ready and confirmation_timeout
            else "run the single 600s 1x1 confirmation probe"
            if ready
            else "manual safety review"
        ),
        "blocked_actions": [
            "do_not_run_67x20_hotspot_followup_yet",
            "do_not_run_4x5_hotspot_followup_yet",
            "do_not_retry_2x10_hotspot_profile",
            "do_not_run_longer_hotspot_probe_without_new_strategy",
            "do_not_run_full_wave_matrix",
            "do_not_promote_local_results_to_proof",
        ],
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bytes_to_gib(value: Any) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return parsed / (1024.0**3)


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

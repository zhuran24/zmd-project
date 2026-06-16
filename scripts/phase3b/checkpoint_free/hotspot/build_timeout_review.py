from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
LOG_ROOT = PROJECT_ROOT / ".codex_test_logs" / "phase3b" / "local_13900ks_tuning_20260430"
DEFAULT_RUN_ID = "B0_prod_4x4_300s_42x32_resource_probe_eval_001"
DEFAULT_RUN_DIR = ARTIFACT_ROOT / "08_checkpoint_free_evaluator" / DEFAULT_RUN_ID
DEFAULT_LOG_DIR = LOG_ROOT / "08_checkpoint_free_evaluator" / DEFAULT_RUN_ID
DEFAULT_REVISION = ARTIFACT_ROOT / "14_resource_strategy_revision" / "resource_strategy_revision.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "15_hotspot_timeout_review"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_hotspot_timeout_review(
        run_dir=_resolve_path(PROJECT_ROOT, args.run_dir),
        log_dir=_resolve_path(PROJECT_ROOT, args.log_dir),
        resource_strategy_revision_path=_resolve_path(PROJECT_ROOT, args.resource_strategy_revision),
    )
    print("phase3b checkpoint-free hotspot timeout review")
    print(f"run_id={review['run']['run_id']}")
    print(f"action={review['recommendation']['action']}")
    print(f"peak_private_gib={review['telemetry_review']['peak_total_private_gib']:.3f}")
    if not args.no_write:
        paths = write_hotspot_timeout_review(review, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"review_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"review_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a read-only review for the B0/42x32 checkpoint-free hotspot timeout probe."
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--resource-strategy-revision", type=Path, default=DEFAULT_REVISION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_hotspot_timeout_review(
    *,
    run_dir: Path,
    log_dir: Path,
    resource_strategy_revision_path: Path,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    log_dir = Path(log_dir)
    summary = _load_json(run_dir / "run_summary.json")
    run_plan = _load_json(run_dir / "run_plan.json")
    sensitive = _load_json(run_dir / "sensitive_path_comparison.json")
    revision = _load_json(resource_strategy_revision_path) if Path(resource_strategy_revision_path).exists() else {}
    samples = _load_telemetry_samples(log_dir / "telemetry_samples.jsonl")
    telemetry_review = _telemetry_review(samples, summary)
    run = _run_review(summary, run_plan, sensitive)
    return {
        "schema": "phase3b-checkpoint-free-hotspot-timeout-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "review_kind": "local_checkpoint_free_hotspot_timeout_review",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "run_dir": str(run_dir),
        "log_dir": str(log_dir),
        "resource_strategy_revision_path": str(resource_strategy_revision_path),
        "run": run,
        "telemetry_review": telemetry_review,
        "resource_strategy_revision": {
            "action": _mapping(revision.get("recommendation")).get("action"),
            "primary_probe_id": _mapping(revision.get("recommendation")).get("primary_probe_id"),
        },
        "interpretation": _interpretation(run, telemetry_review),
        "recommendation": _recommendation(run, telemetry_review),
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "scheduler_integration": False,
            "builder_executes_solver": False,
            "sensitive_path_changed": bool(sensitive.get("changed")),
        },
    }


def write_hotspot_timeout_review(review: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hotspot_timeout_review.json"
    md_path = output_dir / "hotspot_timeout_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_hotspot_timeout_review_markdown(review), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_hotspot_timeout_review_markdown(review: Mapping[str, Any]) -> str:
    run = _mapping(review.get("run"))
    telemetry = _mapping(review.get("telemetry_review"))
    recommendation = _mapping(review.get("recommendation"))
    interpretation = _mapping(review.get("interpretation"))
    lines = [
        "# Phase3B Hotspot Timeout Review",
        "",
        f"- Generated: `{review.get('generated_at')}`",
        f"- Run: `{run.get('run_id')}`",
        f"- Candidate/profile: `{run.get('candidate_id')}`",
        f"- Hotspot key: `{run.get('candidate_key')}`",
        f"- Status: `{run.get('status')}`",
        f"- Sensitive path changed: `{str(run.get('sensitive_path_changed')).lower()}`",
        f"- Resource stop: `{str(run.get('resource_stop_triggered')).lower()}`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Scheduler integration: `false`",
        f"- Peak private GiB: `{telemetry.get('peak_total_private_gib'):.3f}`",
        f"- Peak RSS GiB: `{telemetry.get('peak_total_rss_gib'):.3f}`",
        f"- Dominant process peak private GiB: `{telemetry.get('dominant_process_peak_private_gib'):.3f}`",
        "",
        "## Interpretation",
        "",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Memory finding: `{interpretation.get('memory_finding')}`",
        f"- Runtime finding: `{interpretation.get('runtime_finding')}`",
        "",
        "## Recommendation",
        "",
        f"- Action: `{recommendation.get('action')}`",
        f"- Next engineering step: `{recommendation.get('next_engineering_step')}`",
        f"- Allowed followup probes: `{', '.join(recommendation.get('allowed_followup_probe_ids', []))}`",
        f"- Blocked actions: `{', '.join(recommendation.get('blocked_actions', []))}`",
        "",
        "This is local diagnostic review only. It does not authorize canonical checkpoints, proof promotion, production default changes, full-wave retry, or scheduler integration.",
        "",
    ]
    return "\n".join(lines)


def _run_review(summary: Mapping[str, Any], run_plan: Mapping[str, Any], sensitive: Mapping[str, Any]) -> dict[str, Any]:
    wave = _mapping(run_plan.get("wave"))
    entries = [
        entry for entry in list(wave.get("entries", []) or []) if isinstance(entry, Mapping)
    ]
    candidate_key = str(entries[0].get("candidate_key")) if entries else None
    execution = _mapping(summary.get("execution"))
    diagnostics = _mapping(execution.get("wave_result_diagnostics"))
    return {
        "run_id": summary.get("run_id"),
        "candidate_id": summary.get("candidate_id"),
        "candidate_key": candidate_key,
        "status": summary.get("status"),
        "requested_duration_seconds": summary.get("requested_duration_seconds"),
        "duration_seconds": summary.get("duration_seconds"),
        "result_count": execution.get("result_count"),
        "timed_out": bool(execution.get("timed_out")),
        "resource_stop_triggered": bool(execution.get("resource_stop_triggered")),
        "sensitive_path_changed": bool(sensitive.get("changed")),
        "pending_candidate_keys": diagnostics.get("pending_candidate_keys", []),
        "straggler_candidate_keys": diagnostics.get("straggler_candidate_keys", []),
        "checkpoint_free": bool(summary.get("checkpoint_free")),
        "proof_source": bool(summary.get("proof_source")),
        "checkpoint_written": bool(summary.get("checkpoint_written")),
    }


def _telemetry_review(samples: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> dict[str, Any]:
    telemetry_summary = _mapping(summary.get("telemetry_summary"))
    if not samples:
        return {
            "sample_count": 0,
            "peak_total_private_gib": _bytes_to_gib(telemetry_summary.get("peak_total_private_bytes")),
            "peak_total_rss_gib": _bytes_to_gib(telemetry_summary.get("peak_total_rss_bytes")),
            "peak_total_cpu_percent": _float(telemetry_summary.get("peak_total_cpu_percent")) or 0.0,
            "dominant_process_peak_private_gib": 0.0,
            "private_growth_gib": None,
            "last_sample_total_private_gib": None,
        }
    aggregates = [_mapping(sample.get("aggregate")) for sample in samples]
    first = aggregates[0]
    last = aggregates[-1]
    peak_private = max(_float(agg.get("total_private_bytes")) or 0.0 for agg in aggregates)
    peak_rss = max(_float(agg.get("total_rss_bytes")) or 0.0 for agg in aggregates)
    peak_cpu = max(_float(agg.get("total_cpu_percent")) or 0.0 for agg in aggregates)
    dominant = _dominant_process(samples)
    return {
        "sample_count": len(samples),
        "peak_process_count": max(int(agg.get("process_count") or 0) for agg in aggregates),
        "peak_thread_count": max(int(agg.get("thread_count") or 0) for agg in aggregates),
        "peak_total_private_gib": _bytes_to_gib(peak_private),
        "peak_total_rss_gib": _bytes_to_gib(peak_rss),
        "peak_total_cpu_percent": peak_cpu,
        "first_sample_total_private_gib": _bytes_to_gib(first.get("total_private_bytes")),
        "last_sample_total_private_gib": _bytes_to_gib(last.get("total_private_bytes")),
        "private_growth_gib": _bytes_to_gib(
            (_float(last.get("total_private_bytes")) or 0.0)
            - (_float(first.get("total_private_bytes")) or 0.0)
        ),
        "dominant_process_pid": dominant["pid"],
        "dominant_process_peak_private_gib": dominant["peak_private_gib"],
        "dominant_process_peak_rss_gib": dominant["peak_rss_gib"],
    }


def _dominant_process(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    peaks: dict[int, dict[str, float]] = {}
    for sample in samples:
        for proc in list(sample.get("processes", []) or []):
            if not isinstance(proc, Mapping):
                continue
            pid = int(proc.get("pid") or 0)
            memory = _mapping(proc.get("memory"))
            private = _float(memory.get("private_bytes")) or 0.0
            rss = _float(memory.get("rss_bytes")) or 0.0
            entry = peaks.setdefault(pid, {"private": 0.0, "rss": 0.0})
            entry["private"] = max(entry["private"], private)
            entry["rss"] = max(entry["rss"], rss)
    if not peaks:
        return {"pid": None, "peak_private_gib": 0.0, "peak_rss_gib": 0.0}
    pid, values = max(peaks.items(), key=lambda item: item[1]["private"])
    return {
        "pid": pid,
        "peak_private_gib": _bytes_to_gib(values["private"]),
        "peak_rss_gib": _bytes_to_gib(values["rss"]),
    }


def _interpretation(run: Mapping[str, Any], telemetry: Mapping[str, Any]) -> dict[str, Any]:
    peak_private = _float(telemetry.get("peak_total_private_gib")) or 0.0
    resource_stop = bool(run.get("resource_stop_triggered"))
    timed_out = bool(run.get("timed_out"))
    if resource_stop:
        classification = "resource_stop_hotspot"
    elif timed_out and peak_private >= 30.0:
        classification = "bounded_timeout_high_memory_straggler"
    elif timed_out:
        classification = "bounded_timeout_compute_straggler"
    else:
        classification = "completed_or_non_timeout_hotspot"
    return {
        "classification": classification,
        "memory_finding": (
            "B0 hotspot probe stayed below the 44 GiB private-memory stop but still reached high local memory."
            if peak_private < 44.0
            else "Hotspot probe reached or exceeded the configured private-memory stop region."
        ),
        "runtime_finding": (
            "No candidate result was produced within the 300s checkpoint-free budget."
            if timed_out
            else "The probe did not time out."
        ),
    }


def _recommendation(run: Mapping[str, Any], telemetry: Mapping[str, Any]) -> dict[str, Any]:
    if bool(run.get("sensitive_path_changed")):
        action = "disqualified_sensitive_path_mutation"
        allowed: list[str] = []
    elif bool(run.get("resource_stop_triggered")):
        action = "hold_hotspot_resource_stop"
        allowed = []
    elif bool(run.get("timed_out")):
        action = "hold_hotspot_followups_pending_narrower_timeout_strategy"
        allowed = []
    else:
        action = "review_for_secondary_hotspot_probe"
        allowed = []
    return {
        "action": action,
        "allowed_followup_probe_ids": allowed,
        "next_engineering_step": (
            "design a narrower timeout strategy before 67x20 or 4x5 hotspot followups"
        ),
        "blocked_actions": [
            "do_not_run_67x20_hotspot_followup_yet",
            "do_not_run_4x5_hotspot_followup_yet",
            "do_not_retry_2x10_hotspot_profile",
            "do_not_run_full_wave_matrix",
            "do_not_promote_local_results_to_proof",
        ],
        "resource_stop_guard_required": True,
        "observed_peak_private_gib": telemetry.get("peak_total_private_gib"),
    }


def _load_telemetry_samples(path: Path) -> list[Mapping[str, Any]]:
    if not Path(path).exists():
        return []
    rows: list[Mapping[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(value)
    return rows


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bytes_to_gib(value: Any) -> float:
    parsed = _float(value)
    if parsed is None:
        return 0.0
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

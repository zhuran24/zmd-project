from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_RUNS_DIR = ARTIFACT_ROOT / "08_checkpoint_free_evaluator"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "09_checkpoint_free_scoreboard"
DEFAULT_BASELINE_CANDIDATE_ID = "B0_prod_4x4"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    runs_dir = _resolve_path(PROJECT_ROOT, args.runs_dir)
    output_dir = _resolve_path(PROJECT_ROOT, args.output_dir)
    scoreboard = build_checkpoint_free_eval_scoreboard(
        runs_dir=runs_dir,
        baseline_candidate_id=str(args.baseline_candidate_id),
        single_run_only=not args.include_legacy_runs,
    )
    print("phase3b checkpoint-free evaluator scoreboard")
    print(f"run_count={len(scoreboard['runs'])}")
    print(f"candidate_count={len(scoreboard['candidate_summaries'])}")
    print(f"baseline_candidate_id={scoreboard['baseline']['candidate_id']}")
    if not args.no_write:
        paths = write_checkpoint_free_eval_scoreboard(scoreboard, output_dir)
        print(f"scoreboard_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"scoreboard_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local non-proof scoreboard from checkpoint-free evaluator run summaries."
    )
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--baseline-candidate-id", default=DEFAULT_BASELINE_CANDIDATE_ID)
    parser.add_argument(
        "--include-legacy-runs",
        action="store_true",
        help="Include older non-single evaluator runs in addition to current *_single_eval_* runs.",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_checkpoint_free_eval_scoreboard(
    *,
    runs_dir: Path,
    baseline_candidate_id: str = DEFAULT_BASELINE_CANDIDATE_ID,
    single_run_only: bool = True,
) -> dict[str, Any]:
    runs = []
    for summary_path in sorted(Path(runs_dir).glob("*/run_summary.json")):
        payload = _load_json(summary_path)
        if not payload.get("execute"):
            continue
        if single_run_only and not _is_current_checkpoint_free_diagnostic_run(
            str(payload.get("run_id", ""))
        ):
            continue
        runs.append(_run_row(payload, summary_path))

    baseline = _select_baseline(runs, baseline_candidate_id)
    baselines_by_duration = _select_baselines_by_duration(runs, baseline_candidate_id)
    baselines_by_shape = _select_baselines_by_shape(runs, baseline_candidate_id)
    baseline_throughput = baseline.get("throughput_per_minute") if baseline else None
    for run in runs:
        shape_key = _normalization_shape_key(run)
        duration_baseline = baselines_by_duration.get(run.get("requested_duration_seconds"))
        shape_baseline = baselines_by_shape.get(shape_key)
        selected_baseline = shape_baseline or duration_baseline or baseline
        run["baseline_run_id_for_normalization"] = selected_baseline.get("run_id") if selected_baseline else None
        run["baseline_normalization_match"] = (
            "duration_and_wave"
            if shape_baseline
            else ("duration_only" if duration_baseline else ("primary_baseline" if baseline else None))
        )
        run["baseline_normalized_throughput"] = _safe_ratio(
            run.get("throughput_per_minute"),
            selected_baseline.get("throughput_per_minute") if selected_baseline else baseline_throughput,
        )

    candidate_summaries = _candidate_summaries(runs)
    return {
        "schema": "phase3b-checkpoint-free-eval-scoreboard/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scoreboard_kind": "local_checkpoint_free_efficiency_telemetry",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "runs_dir": str(Path(runs_dir)),
        "filters": {
            "execute_only": True,
            "single_run_only": bool(single_run_only),
        },
        "baseline": {
            "candidate_id": baseline_candidate_id,
            "run_id": baseline.get("run_id") if baseline else None,
            "available": baseline is not None,
            "throughput_per_minute": baseline_throughput,
            "selection_policy": "prefer_completed_non_mutating_non_resource_stopped_then_latest",
        },
        "baseline_normalization": {
            "policy": "match_requested_duration_seconds_and_wave_then_duration_then_primary_baseline",
            "by_requested_duration_seconds": {
                str(duration): {
                    "run_id": selected.get("run_id"),
                    "throughput_per_minute": selected.get("throughput_per_minute"),
                    "status": selected.get("status"),
                    "resource_stop_triggered": selected.get("resource_stop_triggered"),
                    "sensitive_path_changed": selected.get("sensitive_path_changed"),
                }
                for duration, selected in sorted(baselines_by_duration.items())
            },
            "by_requested_duration_seconds_and_wave": {
                f"{duration}s_wave{wave}": {
                    "run_id": selected.get("run_id"),
                    "throughput_per_minute": selected.get("throughput_per_minute"),
                    "status": selected.get("status"),
                    "resource_stop_triggered": selected.get("resource_stop_triggered"),
                    "sensitive_path_changed": selected.get("sensitive_path_changed"),
                }
                for (duration, wave), selected in sorted(baselines_by_shape.items())
            },
        },
        "runs": runs,
        "candidate_summaries": candidate_summaries,
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "sensitive_path_mutation_detected": any(run["sensitive_path_changed"] for run in runs),
        },
    }


def write_checkpoint_free_eval_scoreboard(scoreboard: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "checkpoint_free_eval_scoreboard.json"
    md_path = output_dir / "checkpoint_free_eval_scoreboard.md"
    json_path.write_text(json.dumps(scoreboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_scoreboard_markdown(scoreboard), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_scoreboard_markdown(scoreboard: Mapping[str, Any]) -> str:
    lines = [
        "# Phase3B Checkpoint-Free Evaluator Scoreboard",
        "",
        f"- Generated: `{scoreboard.get('generated_at')}`",
        f"- Kind: `{scoreboard.get('scoreboard_kind')}`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        f"- Baseline: `{scoreboard.get('baseline', {}).get('run_id')}`",
        "",
        "| Candidate | Run | Status | Results | Duration | Wave | Throughput/min | vs baseline | Norm match | Norm baseline | Peak private GiB | Peak RSS GiB | Sensitive changed |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for run in scoreboard.get("runs", []):
        lines.append(
            "| {candidate_id} | {run_id} | {status} | {result_count} | {duration_seconds:.3f} | "
            "{wave_selected_count}/{wave_max_candidates} | {throughput_per_minute:.3f} | "
            "{baseline_normalized_throughput:.3f} | {baseline_normalization_match} | "
            "{baseline_run_id_for_normalization} | "
            "{peak_private_gib:.2f} | {peak_rss_gib:.2f} | {sensitive_path_changed} |".format(
                candidate_id=run["candidate_id"],
                run_id=run["run_id"],
                status=run["status"],
                result_count=run["result_count"],
                duration_seconds=run["duration_seconds"],
                throughput_per_minute=run["throughput_per_minute"],
                baseline_normalized_throughput=run["baseline_normalized_throughput"]
                if run["baseline_normalized_throughput"] is not None
                else 0.0,
                baseline_normalization_match=run.get("baseline_normalization_match"),
                baseline_run_id_for_normalization=run.get("baseline_run_id_for_normalization"),
                wave_selected_count=run.get("wave_selected_count"),
                wave_max_candidates=run.get("wave_max_candidates"),
                peak_private_gib=run["peak_private_gib"],
                peak_rss_gib=run["peak_rss_gib"],
                sensitive_path_changed=str(run["sensitive_path_changed"]).lower(),
            )
        )
    lines.extend(
        [
            "",
            "This is local checkpoint-free telemetry only. It is not a certified proof source and does not change production defaults.",
            "",
        ]
    )
    return "\n".join(lines)


def _candidate_summaries(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    for run in runs:
        by_candidate.setdefault(str(run["candidate_id"]), []).append(run)
    summaries = []
    for candidate_id, candidate_runs in sorted(by_candidate.items()):
        best = max(
            candidate_runs,
            key=lambda run: (
                int(not run["sensitive_path_changed"]),
                int(not run["resource_stop_triggered"]),
                float(run["throughput_per_minute"]),
                int(run["result_count"]),
            ),
        )
        summaries.append(
            {
                "candidate_id": candidate_id,
                "run_count": len(candidate_runs),
                "best_run_id": best["run_id"],
                "best_status": best["status"],
                "best_throughput_per_minute": best["throughput_per_minute"],
                "best_baseline_normalized_throughput": best["baseline_normalized_throughput"],
                "any_sensitive_path_changed": any(run["sensitive_path_changed"] for run in candidate_runs),
                "any_resource_stop_triggered": any(run["resource_stop_triggered"] for run in candidate_runs),
            }
        )
    return summaries


def _run_row(payload: Mapping[str, Any], summary_path: Path) -> dict[str, Any]:
    execution = _mapping(payload.get("execution"))
    telemetry = _mapping(payload.get("telemetry_summary"))
    sensitive = _mapping(payload.get("sensitive_path_comparison"))
    plan = _load_run_plan(payload, summary_path)
    wave = _mapping(plan.get("wave"))
    wave_entries = [
        entry
        for entry in list(wave.get("entries", []) or [])
        if isinstance(entry, Mapping)
    ]
    candidate_profile = _mapping(plan.get("candidate_profile"))
    duration_seconds = _float(payload.get("duration_seconds")) or _float(execution.get("elapsed_seconds")) or 0.0
    result_count = int(execution.get("result_count") or 0)
    return {
        "run_id": str(payload.get("run_id")),
        "candidate_id": str(payload.get("candidate_id")),
        "status": str(payload.get("status")),
        "requested_duration_seconds": int(payload.get("requested_duration_seconds") or 0),
        "duration_seconds": duration_seconds,
        "elapsed_seconds": _float(execution.get("elapsed_seconds")),
        "result_count": result_count,
        "wave_max_candidates": int(wave.get("max_wave_candidates") or 0),
        "wave_selected_count": int(wave.get("selected_count") or 0),
        "wave_selection_kind": str(wave.get("selection_kind") or ""),
        "wave_requested_candidate_keys": [
            str(key)
            for key in list(wave.get("requested_candidate_keys", []) or [])
            if key is not None
        ],
        "wave_excluded_candidate_keys": [
            str(key)
            for key in list(wave.get("excluded_candidate_keys", []) or [])
            if key is not None
        ],
        "wave_candidate_keys": [
            str(entry.get("candidate_key"))
            for entry in wave_entries
            if entry.get("candidate_key")
        ],
        "process_count": int(candidate_profile.get("process_count") or 0),
        "total_worker_slots": candidate_profile.get("total_worker_slots"),
        "throughput_per_minute": result_count * 60.0 / duration_seconds if duration_seconds > 0 else 0.0,
        "timed_out": bool(execution.get("timed_out")),
        "resource_stop_triggered": bool(execution.get("resource_stop_triggered")),
        "checkpoint_free": bool(payload.get("checkpoint_free")),
        "main_py_executed": bool(payload.get("main_py_executed")),
        "exact_campaign_used": bool(payload.get("exact_campaign_used")),
        "proof_source": bool(payload.get("proof_source")),
        "checkpoint_written": bool(payload.get("checkpoint_written")),
        "candidate_universe_changed": bool(payload.get("candidate_universe_changed")),
        "production_profile_changed": bool(payload.get("production_profile_changed")),
        "sensitive_path_changed": bool(sensitive.get("changed")),
        "peak_private_gib": _bytes_to_gib(telemetry.get("peak_total_private_bytes")),
        "peak_rss_gib": _bytes_to_gib(telemetry.get("peak_total_rss_bytes")),
        "peak_cpu_percent": _float(telemetry.get("peak_total_cpu_percent")),
        "summary_path": str(summary_path),
    }


def _select_baseline(runs: Sequence[Mapping[str, Any]], baseline_candidate_id: str) -> Mapping[str, Any] | None:
    candidates = [run for run in runs if run.get("candidate_id") == baseline_candidate_id]
    if not candidates:
        return None
    return max(candidates, key=_baseline_quality_key)


def _select_baselines_by_duration(
    runs: Sequence[Mapping[str, Any]], baseline_candidate_id: str
) -> dict[int, Mapping[str, Any]]:
    selected: dict[int, Mapping[str, Any]] = {}
    for run in runs:
        if run.get("candidate_id") != baseline_candidate_id:
            continue
        duration = int(run.get("requested_duration_seconds") or 0)
        if duration <= 0:
            continue
        current = selected.get(duration)
        if current is None or _baseline_quality_key(run) > _baseline_quality_key(current):
            selected[duration] = run
    return selected


def _select_baselines_by_shape(
    runs: Sequence[Mapping[str, Any]], baseline_candidate_id: str
) -> dict[tuple[int, int], Mapping[str, Any]]:
    selected: dict[tuple[int, int], Mapping[str, Any]] = {}
    for run in runs:
        if run.get("candidate_id") != baseline_candidate_id:
            continue
        key = _normalization_shape_key(run)
        if key[0] <= 0 or key[1] <= 0:
            continue
        current = selected.get(key)
        if current is None or _baseline_quality_key(run) > _baseline_quality_key(current):
            selected[key] = run
    return selected


def _normalization_shape_key(run: Mapping[str, Any]) -> tuple[int, int]:
    return (
        int(run.get("requested_duration_seconds") or 0),
        int(run.get("wave_max_candidates") or 0),
    )


def _is_current_checkpoint_free_diagnostic_run(run_id: str) -> bool:
    return (
        "_single_eval_" in run_id
        or "_isolated_eval_" in run_id
        or ("_reduced_frontier_" in run_id and "_eval_" in run_id)
        or "_resource_probe_eval_" in run_id
        or "_narrow_eval_" in run_id
        or (run_id.startswith("local_hotspot_") and "_eval_" in run_id)
    )


def _baseline_quality_key(run: Mapping[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(not run.get("sensitive_path_changed")),
        int(not run.get("resource_stop_triggered")),
        int(str(run.get("status") or "") == "completed"),
        str(run.get("run_id", "")),
    )


def _load_run_plan(payload: Mapping[str, Any], summary_path: Path) -> Mapping[str, Any]:
    paths = _mapping(payload.get("paths"))
    raw_plan_path = paths.get("run_plan")
    candidates = []
    if raw_plan_path:
        candidates.append(Path(str(raw_plan_path)))
    candidates.append(Path(summary_path).parent / "run_plan.json")
    for plan_path in candidates:
        try:
            if plan_path.exists():
                return _load_json(plan_path)
        except OSError:
            continue
    return {}


def _safe_ratio(value: Any, baseline: Any) -> float | None:
    numerator = _float(value)
    denominator = _float(baseline)
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _bytes_to_gib(value: Any) -> float:
    parsed = _float(value)
    if parsed is None:
        return 0.0
    return parsed / (1024.0**3)


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_RUNS_DIR = ARTIFACT_ROOT / "08_checkpoint_free_evaluator"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "11_wave_straggler_diagnosis"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    diagnosis = build_checkpoint_free_wave_diagnosis(
        runs_dir=_resolve_path(PROJECT_ROOT, args.runs_dir),
    )
    print("phase3b checkpoint-free wave diagnosis")
    print(f"run_count={len(diagnosis['runs'])}")
    print(f"timeout_run_count={diagnosis['summary']['timeout_run_count']}")
    print(f"resource_stop_run_count={diagnosis['summary']['resource_stop_run_count']}")
    if not args.no_write:
        paths = write_checkpoint_free_wave_diagnosis(
            diagnosis,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"diagnosis_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"diagnosis_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build read-only per-candidate wave diagnostics from checkpoint-free evaluator artifacts."
    )
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_checkpoint_free_wave_diagnosis(*, runs_dir: Path) -> dict[str, Any]:
    runs = []
    for summary_path in sorted(Path(runs_dir).glob("*/run_summary.json")):
        summary = _load_json(summary_path)
        if not summary.get("execute"):
            continue
        if not _is_current_checkpoint_free_diagnostic_run(str(summary.get("run_id", ""))):
            continue
        runs.append(_run_wave_row(summary, summary_path))

    return {
        "schema": "phase3b-checkpoint-free-wave-diagnosis/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "diagnosis_kind": "local_checkpoint_free_per_candidate_wave_status",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "runs_dir": str(Path(runs_dir)),
        "summary": {
            "run_count": len(runs),
            "timeout_run_count": sum(1 for run in runs if run["timed_out"]),
            "resource_stop_run_count": sum(1 for run in runs if run["resource_stop_triggered"]),
            "sensitive_path_mutation_detected": any(run["sensitive_path_changed"] for run in runs),
            "straggler_candidate_keys": sorted(
                {
                    key
                    for run in runs
                    for key in run["straggler_candidate_keys"]
                }
            ),
            "interrupted_candidate_keys": sorted(
                {
                    key
                    for run in runs
                    for key in run["interrupted_candidate_keys"]
                }
            ),
        },
        "runs": runs,
    }


def write_checkpoint_free_wave_diagnosis(diagnosis: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "checkpoint_free_wave_diagnosis.json"
    md_path = output_dir / "checkpoint_free_wave_diagnosis.md"
    json_path.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_wave_diagnosis_markdown(diagnosis), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_wave_diagnosis_markdown(diagnosis: Mapping[str, Any]) -> str:
    summary = _mapping(diagnosis.get("summary"))
    lines = [
        "# Phase3B Checkpoint-Free Wave Diagnosis",
        "",
        f"- Generated: `{diagnosis.get('generated_at')}`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Fresh solver run started by builder: `false`",
        f"- Timeout runs: `{summary.get('timeout_run_count')}`",
        f"- Resource-stop runs: `{summary.get('resource_stop_run_count')}`",
        f"- Straggler candidate keys: `{', '.join(summary.get('straggler_candidate_keys', []))}`",
        "",
        "| Run | Status | Wave | Completed | Pending | Stragglers | Interrupted | Peak private GiB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in diagnosis.get("runs", []):
        lines.append(
            "| {run_id} | {status} | {wave_selected_count}/{wave_max_candidates} | {completed} | "
            "{pending} | {stragglers} | {interrupted} | {peak:.2f} |".format(
                run_id=run["run_id"],
                status=run["status"],
                wave_selected_count=run["wave_selected_count"],
                wave_max_candidates=run["wave_max_candidates"],
                completed=", ".join(run["completed_candidate_keys"]),
                pending=", ".join(run["pending_candidate_keys"]),
                stragglers=", ".join(run["straggler_candidate_keys"]),
                interrupted=", ".join(run["interrupted_candidate_keys"]),
                peak=run["peak_private_gib"],
            )
        )
    lines.extend(
        [
            "",
            "This artifact is local diagnostic telemetry only. It does not certify outcomes, write checkpoints, or change scheduler order.",
            "",
        ]
    )
    return "\n".join(lines)


def _run_wave_row(summary: Mapping[str, Any], summary_path: Path) -> dict[str, Any]:
    plan = _load_run_plan(summary, summary_path)
    wave = _mapping(plan.get("wave"))
    planned = [
        str(entry.get("candidate_key"))
        for entry in list(wave.get("entries", []) or [])
        if isinstance(entry, Mapping) and entry.get("candidate_key")
    ]
    completed = _completed_candidate_keys(summary, summary_path)
    pending = [key for key in planned if key not in set(completed)]
    execution = _mapping(summary.get("execution"))
    telemetry = _mapping(summary.get("telemetry_summary"))
    sensitive = _mapping(summary.get("sensitive_path_comparison"))
    timed_out = bool(execution.get("timed_out"))
    resource_stop = bool(execution.get("resource_stop_triggered"))
    return {
        "run_id": str(summary.get("run_id")),
        "candidate_id": str(summary.get("candidate_id")),
        "status": str(summary.get("status")),
        "requested_duration_seconds": int(summary.get("requested_duration_seconds") or 0),
        "wave_max_candidates": int(wave.get("max_wave_candidates") or len(planned)),
        "wave_selected_count": int(wave.get("selected_count") or len(planned)),
        "planned_candidate_keys": planned,
        "completed_candidate_keys": completed,
        "pending_candidate_keys": pending,
        "straggler_candidate_keys": pending if timed_out else [],
        "interrupted_candidate_keys": pending if resource_stop else [],
        "timed_out": timed_out,
        "resource_stop_triggered": resource_stop,
        "sensitive_path_changed": bool(sensitive.get("changed")),
        "result_count": int(execution.get("result_count") or len(completed)),
        "peak_private_gib": _bytes_to_gib(telemetry.get("peak_total_private_bytes")),
        "peak_rss_gib": _bytes_to_gib(telemetry.get("peak_total_rss_bytes")),
    }


def _completed_candidate_keys(summary: Mapping[str, Any], summary_path: Path) -> list[str]:
    diagnostics = _mapping(_mapping(summary.get("execution")).get("wave_result_diagnostics"))
    if diagnostics.get("completed_candidate_keys"):
        return [str(key) for key in diagnostics.get("completed_candidate_keys", [])]
    paths = _mapping(summary.get("paths"))
    raw_results_path = paths.get("results_jsonl")
    results_path = Path(str(raw_results_path)) if raw_results_path else summary_path.parent / "checkpoint_free_eval_results.jsonl"
    completed = []
    if not results_path.exists():
        return completed
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, Mapping) and payload.get("candidate_key"):
            completed.append(str(payload["candidate_key"]))
    return completed


def _is_current_checkpoint_free_diagnostic_run(run_id: str) -> bool:
    return (
        "_single_eval_" in run_id
        or "_isolated_eval_" in run_id
        or ("_reduced_frontier_" in run_id and "_eval_" in run_id)
        or "_resource_probe_eval_" in run_id
        or "_narrow_eval_" in run_id
        or (run_id.startswith("local_hotspot_") and "_eval_" in run_id)
    )


def _load_run_plan(summary: Mapping[str, Any], summary_path: Path) -> Mapping[str, Any]:
    paths = _mapping(summary.get("paths"))
    raw_plan_path = paths.get("run_plan")
    candidates = []
    if raw_plan_path:
        candidates.append(Path(str(raw_plan_path)))
    candidates.append(Path(summary_path).parent / "run_plan.json")
    for plan_path in candidates:
        if plan_path.exists():
            return _load_json(plan_path)
    return {}


def _bytes_to_gib(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value) / (1024.0**3)
    except (TypeError, ValueError):
        return 0.0


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

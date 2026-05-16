from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_NAMESPACE = "phase3b_local_13900ks_tuning_20260430"
RUN_ID = "local_hotspot_b0_1x1_global_normal_300s_42x32_stage_heartbeat_eval_001"
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / LOCAL_NAMESPACE
LOG_ROOT = PROJECT_ROOT / ".codex_test_logs" / "phase3b" / "local_13900ks_tuning_20260430"
DEFAULT_RUN_SUMMARY = ARTIFACT_ROOT / "08_checkpoint_free_evaluator" / RUN_ID / "run_summary.json"
DEFAULT_STAGE_HEARTBEATS = (
    LOG_ROOT / "08_checkpoint_free_evaluator" / RUN_ID / "stage_heartbeats.jsonl"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "18_stage_heartbeat_review"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_stage_heartbeat_review(
        run_summary_path=_resolve_path(PROJECT_ROOT, args.run_summary),
        stage_heartbeats_path=_resolve_path(PROJECT_ROOT, args.stage_heartbeats),
    )
    print("phase3b checkpoint-free stage heartbeat review")
    print(f"run_id={review['run']['run_id']}")
    print(f"stalled_stage={review['interpretation']['stalled_stage']}")
    print(f"action={review['recommendation']['action']}")
    if not args.no_write:
        paths = write_stage_heartbeat_review(review, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"review_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"review_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize stage-heartbeat telemetry for the 42x32 checkpoint-free hotspot."
    )
    parser.add_argument("--run-summary", type=Path, default=DEFAULT_RUN_SUMMARY)
    parser.add_argument("--stage-heartbeats", type=Path, default=DEFAULT_STAGE_HEARTBEATS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_stage_heartbeat_review(
    *,
    run_summary_path: Path,
    stage_heartbeats_path: Path,
) -> dict[str, Any]:
    summary = _load_json(run_summary_path)
    events = _load_jsonl(stage_heartbeats_path)
    event_rows = [_event_row(event) for event in events]
    stage_counts = _stage_counts(event_rows)
    completed_stages = sorted(
        {row["stage"] for row in event_rows if row["event"] == "complete" and row["stage"]}
    )
    started_stages = [row["stage"] for row in event_rows if row["event"] == "start" and row["stage"]]
    last_event = event_rows[-1] if event_rows else {}
    stalled_stage = str(last_event.get("stage") or "no_stage_heartbeat")
    stalled_reason = (
        "last_stage_start_without_complete_before_timeout"
        if last_event.get("event") == "start" and summary.get("status") == "timeout"
        else "no_stage_heartbeat_before_timeout"
        if not event_rows and summary.get("status") == "timeout"
        else "manual_review_required"
    )
    return {
        "schema": "phase3b-checkpoint-free-stage-heartbeat-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "review_kind": "local_checkpoint_free_stage_heartbeat_review",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "run_summary_path": str(run_summary_path),
        "stage_heartbeats_path": str(stage_heartbeats_path),
        "run": {
            "run_id": str(summary.get("run_id")),
            "candidate_id": str(summary.get("candidate_id")),
            "status": str(summary.get("status")),
            "requested_duration_seconds": int(summary.get("requested_duration_seconds") or 0),
            "checkpoint_free": bool(summary.get("checkpoint_free")),
            "result_count": int(_mapping(summary.get("execution")).get("result_count") or 0),
            "stage_heartbeat_count": int(
                _mapping(summary.get("execution")).get("stage_heartbeat_count") or len(event_rows)
            ),
            "sensitive_path_changed": bool(
                _mapping(summary.get("sensitive_path_comparison")).get("changed")
            ),
            "resource_stop_triggered": bool(
                _mapping(summary.get("execution")).get("resource_stop_triggered")
            ),
        },
        "stage_timeline": event_rows,
        "stage_counts": stage_counts,
        "completed_stages": completed_stages,
        "started_stages": started_stages,
        "last_event": last_event,
        "interpretation": {
            "stalled_stage": stalled_stage,
            "stalled_reason": stalled_reason,
            "master_solve_started": "master_solve" in started_stages,
            "master_solve_completed": "master_solve" in completed_stages,
            "binding_started": "binding" in started_stages,
            "routing_started": "routing" in started_stages,
            "stalled_before_binding_or_routing": (
                stalled_stage == "master_solve"
                and "binding" not in started_stages
                and "routing" not in started_stages
            ),
        },
        "recommendation": _recommendation(stalled_stage, stalled_reason),
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "scheduler_integration": False,
            "builder_executes_solver": False,
            "execution_enabled": False,
        },
    }


def write_stage_heartbeat_review(review: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "stage_heartbeat_review.json"
    md_path = output_dir / "stage_heartbeat_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_stage_heartbeat_review_markdown(review), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_stage_heartbeat_review_markdown(review: Mapping[str, Any]) -> str:
    run = _mapping(review.get("run"))
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    lines = [
        "# Phase3B Stage Heartbeat Review",
        "",
        f"- Generated: `{review.get('generated_at')}`",
        f"- Run id: `{run.get('run_id')}`",
        f"- Status: `{run.get('status')}`",
        f"- Stage heartbeat count: `{run.get('stage_heartbeat_count')}`",
        f"- Stalled stage: `{interpretation.get('stalled_stage')}`",
        f"- Stalled reason: `{interpretation.get('stalled_reason')}`",
        f"- Stalled before binding/routing: `{interpretation.get('stalled_before_binding_or_routing')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Timeline",
        "",
        "| # | Stage | Event | Iteration | Updated at |",
        "|---:|---|---|---:|---|",
    ]
    for index, event in enumerate(list(review.get("stage_timeline", []) or []), start=1):
        lines.append(
            f"| {index} | {event.get('stage')} | {event.get('event')} | {event.get('iteration')} | {event.get('updated_at')} |"
        )
    lines.extend(
        [
            "",
            "This review narrows the 42x32 hotspot to the master solve stage. It does not authorize longer runs, canonical checkpoint writes, production default changes, or proof promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def _event_row(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(event.get("payload"))
    return {
        "worker_index": int(event.get("worker_index", -1)),
        "dispatch_seq": int(event.get("dispatch_seq", -1)),
        "attempt_index": int(event.get("attempt_index", -1)),
        "candidate_key": str(event.get("candidate_key") or payload.get("candidate_key") or ""),
        "stage": str(payload.get("stage") or ""),
        "event": str(payload.get("event") or ""),
        "iteration": payload.get("iteration"),
        "updated_at": payload.get("updated_at"),
        "payload": dict(payload),
    }


def _stage_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        stage = str(row.get("stage") or "")
        event = str(row.get("event") or "")
        if not stage:
            continue
        counts.setdefault(stage, {})
        counts[stage][event] = counts[stage].get(event, 0) + 1
    return counts


def _recommendation(stalled_stage: str, stalled_reason: str) -> dict[str, Any]:
    if stalled_stage == "master_solve" and stalled_reason == "last_stage_start_without_complete_before_timeout":
        action = "prepare_master_solve_micro_diagnostics"
        next_step = (
            "add master-solve focused diagnostics such as CP-SAT log capture/stat extraction or "
            "a no-write master-only diagnostic before trying longer 42x32 runtime"
        )
    else:
        action = "hold_manual_stage_review"
        next_step = "review stage heartbeat timeline before selecting another diagnostic"
    return {
        "action": action,
        "next_engineering_step": next_step,
        "blocked_actions": [
            "do_not_run_67x20_hotspot_followup_yet",
            "do_not_run_4x5_hotspot_followup_yet",
            "do_not_retry_2x10_hotspot_profile",
            "do_not_extend_42x32_duration_without_master_solve_diagnostics",
            "do_not_run_full_wave_matrix",
            "do_not_promote_local_results_to_proof",
        ],
    }


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

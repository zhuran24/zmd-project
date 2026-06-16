from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
LOG_ROOT = PROJECT_ROOT / ".codex_test_logs" / "phase3b" / "local_13900ks_tuning_20260430"
RUN_ID = "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001"
DEFAULT_RUN_SUMMARY = ARTIFACT_ROOT / "08_checkpoint_free_evaluator" / RUN_ID / "run_summary.json"
DEFAULT_STAGE_HEARTBEATS = LOG_ROOT / "08_checkpoint_free_evaluator" / RUN_ID / "stage_heartbeats.jsonl"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "20_master_solve_log_review"

_SYMMETRY_GRAPH_RE = re.compile(r"Graph for symmetry has ([0-9']+) nodes and ([0-9']+) arcs")
_SAT_PRESOLVE_RE = re.compile(
    r"clauses:([0-9']+) literals:([0-9']+) vars:([0-9']+)"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_master_solve_log_review(
        run_summary_path=_resolve_path(PROJECT_ROOT, args.run_summary),
        stage_heartbeats_path=_resolve_path(PROJECT_ROOT, args.stage_heartbeats),
    )
    print("phase3b checkpoint-free master-solve log review")
    print(f"log_line_count={review['log_summary']['log_line_count']}")
    print(f"classification={review['interpretation']['classification']}")
    print(f"action={review['recommendation']['action']}")
    if not args.no_write:
        paths = write_master_solve_log_review(review, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"review_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"review_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review CP-SAT master-solve log heartbeats for the 42x32 hotspot."
    )
    parser.add_argument("--run-summary", type=Path, default=DEFAULT_RUN_SUMMARY)
    parser.add_argument("--stage-heartbeats", type=Path, default=DEFAULT_STAGE_HEARTBEATS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_master_solve_log_review(
    *,
    run_summary_path: Path,
    stage_heartbeats_path: Path,
) -> dict[str, Any]:
    summary = _load_json(run_summary_path)
    rows = _load_jsonl(stage_heartbeats_path)
    log_rows = [
        _mapping(row.get("payload"))
        for row in rows
        if _mapping(row.get("payload")).get("stage") == "master_solve_log"
    ]
    log_texts = [str(row.get("text") or "") for row in log_rows]
    extracted = _extract_log_metrics(log_texts)
    log_limit = max((int(row.get("line_limit") or 0) for row in log_rows), default=0)
    max_line = max((int(row.get("line_index") or 0) for row in log_rows), default=0)
    classification = _classify(extracted, log_texts, log_limit=log_limit, max_line=max_line)
    return {
        "schema": "phase3b-checkpoint-free-master-solve-log-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "review_kind": "local_checkpoint_free_master_solve_log_review",
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
            "stage_heartbeat_count": int(_mapping(summary.get("execution")).get("stage_heartbeat_count") or 0),
            "sensitive_path_changed": bool(
                _mapping(summary.get("sensitive_path_comparison")).get("changed")
            ),
            "resource_stop_triggered": bool(
                _mapping(summary.get("execution")).get("resource_stop_triggered")
            ),
        },
        "log_summary": {
            "log_line_count": len(log_rows),
            "line_limit": log_limit,
            "max_line_index": max_line,
            "log_limit_reached": bool(log_limit and max_line >= log_limit),
            "first_lines": log_texts[:8],
            "last_lines": log_texts[-8:],
        },
        "extracted_metrics": extracted,
        "interpretation": {
            "classification": classification,
            "presolve_started": any("Starting presolve" in text for text in log_texts),
            "search_started": any("Starting search" in text for text in log_texts),
            "symmetry_time_limit_reached": any("Time limit reached" in text for text in log_texts),
            "huge_symmetry_graph_seen": extracted["max_symmetry_nodes"] >= 1_000_000,
            "large_sat_presolve_seen": extracted["max_sat_presolve_vars"] >= 1_000_000,
            "log_limit_reached_before_search": bool(
                log_limit and max_line >= log_limit and not any("Starting search" in text for text in log_texts)
            ),
        },
        "recommendation": _recommendation(classification),
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


def write_master_solve_log_review(review: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "master_solve_log_review.json"
    md_path = output_dir / "master_solve_log_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_master_solve_log_review_markdown(review), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_master_solve_log_review_markdown(review: Mapping[str, Any]) -> str:
    run = _mapping(review.get("run"))
    log_summary = _mapping(review.get("log_summary"))
    metrics = _mapping(review.get("extracted_metrics"))
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    lines = [
        "# Phase3B Master-Solve Log Review",
        "",
        f"- Generated: `{review.get('generated_at')}`",
        f"- Run id: `{run.get('run_id')}`",
        f"- Status: `{run.get('status')}`",
        f"- Log lines: `{log_summary.get('log_line_count')}`",
        f"- Log limit reached: `{log_summary.get('log_limit_reached')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Max symmetry graph nodes: `{metrics.get('max_symmetry_nodes')}`",
        f"- Max symmetry graph arcs: `{metrics.get('max_symmetry_arcs')}`",
        f"- Max SAT presolve vars: `{metrics.get('max_sat_presolve_vars')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Last Log Lines",
        "",
    ]
    for line in list(log_summary.get("last_lines", []) or []):
        lines.append(f"- `{line}`")
    lines.extend(
        [
            "",
            "This review classifies the master-solve timeout as a presolve/symmetry-scale bottleneck before normal search starts. It does not authorize longer hotspot runs or proof promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def _extract_log_metrics(log_texts: Sequence[str]) -> dict[str, Any]:
    max_symmetry_nodes = 0
    max_symmetry_arcs = 0
    max_sat_clauses = 0
    max_sat_literals = 0
    max_sat_vars = 0
    for text in log_texts:
        symmetry = _SYMMETRY_GRAPH_RE.search(text)
        if symmetry:
            max_symmetry_nodes = max(max_symmetry_nodes, _parse_int(symmetry.group(1)))
            max_symmetry_arcs = max(max_symmetry_arcs, _parse_int(symmetry.group(2)))
        sat = _SAT_PRESOLVE_RE.search(text)
        if sat:
            max_sat_clauses = max(max_sat_clauses, _parse_int(sat.group(1)))
            max_sat_literals = max(max_sat_literals, _parse_int(sat.group(2)))
            max_sat_vars = max(max_sat_vars, _parse_int(sat.group(3)))
    return {
        "max_symmetry_nodes": max_symmetry_nodes,
        "max_symmetry_arcs": max_symmetry_arcs,
        "max_sat_presolve_clauses": max_sat_clauses,
        "max_sat_presolve_literals": max_sat_literals,
        "max_sat_presolve_vars": max_sat_vars,
    }


def _classify(
    metrics: Mapping[str, Any],
    log_texts: Sequence[str],
    *,
    log_limit: int,
    max_line: int,
) -> str:
    search_started = any("Starting search" in text for text in log_texts)
    if (
        not search_started
        and bool(log_limit and max_line >= log_limit)
        and int(metrics.get("max_symmetry_nodes") or 0) >= 1_000_000
        and int(metrics.get("max_sat_presolve_vars") or 0) >= 1_000_000
    ):
        return "presolve_symmetry_scale_bottleneck_before_search"
    if not search_started and bool(log_limit and max_line >= log_limit):
        return "presolve_bottleneck_before_search"
    return "manual_review_required"


def _recommendation(classification: str) -> dict[str, Any]:
    if classification == "presolve_symmetry_scale_bottleneck_before_search":
        action = "prepare_master_presolve_parameter_micro_matrix"
        next_step = (
            "build a manifest-only micro matrix for 42x32 with symmetry/probing/presolve parameter "
            "variants, starting with symmetry_level=0 and cp_model_probing_level=0 candidates"
        )
    else:
        action = "hold_manual_master_log_review"
        next_step = "review CP-SAT log lines before selecting another run"
    return {
        "action": action,
        "next_engineering_step": next_step,
        "blocked_actions": [
            "do_not_run_67x20_hotspot_followup_yet",
            "do_not_run_4x5_hotspot_followup_yet",
            "do_not_retry_2x10_hotspot_profile",
            "do_not_extend_42x32_duration_without_parameter_micro_matrix",
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


def _parse_int(text: str) -> int:
    return int(str(text).replace("'", ""))


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

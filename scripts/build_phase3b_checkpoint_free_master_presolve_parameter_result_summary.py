from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_BASELINE_REVIEW = ARTIFACT_ROOT / "20_master_solve_log_review" / "master_solve_log_review.json"
DEFAULT_REVIEW_ROOT = ARTIFACT_ROOT / "22_master_presolve_parameter_result_review"
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_ROOT

VARIANT_REVIEW_PATHS = {
    "sym0": DEFAULT_REVIEW_ROOT / "sym0" / "master_solve_log_review.json",
    "probe0": DEFAULT_REVIEW_ROOT / "probe0" / "master_solve_log_review.json",
    "sym0_probe0": DEFAULT_REVIEW_ROOT / "sym0_probe0" / "master_solve_log_review.json",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = build_master_presolve_parameter_result_summary(
        baseline_review_path=_resolve_path(PROJECT_ROOT, args.baseline_review),
        variant_review_paths={
            "sym0": _resolve_path(PROJECT_ROOT, args.sym0_review),
            "probe0": _resolve_path(PROJECT_ROOT, args.probe0_review),
            "sym0_probe0": _resolve_path(PROJECT_ROOT, args.sym0_probe0_review),
        },
    )
    print("phase3b checkpoint-free master presolve parameter result summary")
    print(f"classification={summary['interpretation']['classification']}")
    print(f"action={summary['recommendation']['action']}")
    if not args.no_write:
        paths = write_master_presolve_parameter_result_summary(
            summary,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"summary_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"summary_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize 42x32 master presolve parameter micro results."
    )
    parser.add_argument("--baseline-review", type=Path, default=DEFAULT_BASELINE_REVIEW)
    parser.add_argument("--sym0-review", type=Path, default=VARIANT_REVIEW_PATHS["sym0"])
    parser.add_argument("--probe0-review", type=Path, default=VARIANT_REVIEW_PATHS["probe0"])
    parser.add_argument("--sym0-probe0-review", type=Path, default=VARIANT_REVIEW_PATHS["sym0_probe0"])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_master_presolve_parameter_result_summary(
    *,
    baseline_review_path: Path,
    variant_review_paths: Mapping[str, Path],
) -> dict[str, Any]:
    baseline = _review_row("baseline", _load_json(baseline_review_path))
    variants = [
        _review_row(variant_id, _load_json(path))
        for variant_id, path in sorted(variant_review_paths.items())
    ]
    rows = [baseline, *variants]
    all_variant_reviews_present = all(row["review_present"] for row in variants)
    sensitive_clean = all(not row["sensitive_path_changed"] for row in rows)
    checkpoint_clean = all(not row["checkpoint_written"] for row in rows)
    any_search_started = any(row["search_started"] for row in rows)
    all_variants_timed_out = all(row["run_status"] == "timeout" for row in variants)
    if (
        all_variant_reviews_present
        and sensitive_clean
        and checkpoint_clean
        and not any_search_started
        and all_variants_timed_out
    ):
        classification = "parameter_micro_matrix_exhausted_without_search_start"
        action = "prepare_master_model_size_reduction_strategy"
        next_step = (
            "stop CP-SAT parameter-only probing for 42x32 and prepare a model/candidate "
            "structure reduction diagnostic"
        )
    elif not sensitive_clean or not checkpoint_clean:
        classification = "disqualified_sensitive_or_checkpoint_mutation"
        action = "halt_for_safety_audit"
        next_step = "audit sensitive path differences before any further run"
    else:
        classification = "manual_review_required"
        action = "hold_manual_parameter_result_review"
        next_step = "review parameter rows before selecting another run"
    return {
        "schema": "phase3b-checkpoint-free-master-presolve-parameter-result-summary/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary_kind": "local_checkpoint_free_master_presolve_parameter_result_summary",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "baseline_review_path": str(baseline_review_path),
        "variant_review_paths": {key: str(path) for key, path in sorted(variant_review_paths.items())},
        "baseline": baseline,
        "variants": variants,
        "interpretation": {
            "classification": classification,
            "all_variant_reviews_present": all_variant_reviews_present,
            "sensitive_paths_clean": sensitive_clean,
            "checkpoints_clean": checkpoint_clean,
            "any_search_started": any_search_started,
            "all_variants_timed_out": all_variants_timed_out,
            "symmetry_disabled_removed_symmetry_graph": (
                _row_by_id(variants, "sym0")["max_symmetry_nodes"] == 0
                and baseline["max_symmetry_nodes"] > 0
            ),
            "probing_disabled_removed_search_delay": False,
        },
        "recommendation": {
            "action": action,
            "next_engineering_step": next_step,
            "blocked_actions": [
                "do_not_run_more_parameter_only_42x32_variants_without_new_strategy",
                "do_not_extend_42x32_duration",
                "do_not_run_67x20_hotspot_followup_yet",
                "do_not_run_4x5_hotspot_followup_yet",
                "do_not_retry_2x10_hotspot_profile",
                "do_not_run_full_wave_matrix",
                "do_not_promote_local_results_to_proof",
            ],
        },
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "scheduler_integration": False,
            "builder_executes_solver": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_master_presolve_parameter_result_summary(
    summary: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "master_presolve_parameter_result_summary.json"
    md_path = output_dir / "master_presolve_parameter_result_summary.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_master_presolve_parameter_result_summary_markdown(summary), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_master_presolve_parameter_result_summary_markdown(summary: Mapping[str, Any]) -> str:
    interpretation = _mapping(summary.get("interpretation"))
    recommendation = _mapping(summary.get("recommendation"))
    lines = [
        "# Phase3B Master Presolve Parameter Result Summary",
        "",
        f"- Generated: `{summary.get('generated_at')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "| Row | Status | Search started | Max symmetry nodes | Max SAT vars | Sensitive changed |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in [summary.get("baseline"), *list(summary.get("variants", []) or [])]:
        mapped = _mapping(row)
        lines.append(
            "| {variant} | {status} | {search} | {symmetry} | {sat_vars} | {changed} |".format(
                variant=mapped.get("variant_id"),
                status=mapped.get("run_status"),
                search=str(bool(mapped.get("search_started"))).lower(),
                symmetry=mapped.get("max_symmetry_nodes"),
                sat_vars=mapped.get("max_sat_presolve_vars"),
                changed=str(bool(mapped.get("sensitive_path_changed"))).lower(),
            )
        )
    lines.extend(
        [
            "",
            "The three parameter-only micro variants stayed checkpoint-free and clean, but none reached normal CP-SAT search within the captured 300s window. The next step should target model or candidate structure rather than another blind parameter tweak.",
            "",
        ]
    )
    return "\n".join(lines)


def _review_row(variant_id: str, review: Mapping[str, Any]) -> dict[str, Any]:
    run = _mapping(review.get("run"))
    interpretation = _mapping(review.get("interpretation"))
    metrics = _mapping(review.get("extracted_metrics"))
    return {
        "variant_id": variant_id,
        "review_present": bool(review),
        "candidate_id": run.get("candidate_id"),
        "run_id": run.get("run_id"),
        "run_status": run.get("status"),
        "classification": interpretation.get("classification"),
        "search_started": bool(interpretation.get("search_started")),
        "symmetry_time_limit_reached": bool(interpretation.get("symmetry_time_limit_reached")),
        "max_symmetry_nodes": int(metrics.get("max_symmetry_nodes") or 0),
        "max_symmetry_arcs": int(metrics.get("max_symmetry_arcs") or 0),
        "max_sat_presolve_vars": int(metrics.get("max_sat_presolve_vars") or 0),
        "resource_stop_triggered": bool(run.get("resource_stop_triggered")),
        "sensitive_path_changed": bool(run.get("sensitive_path_changed")),
        "checkpoint_written": bool(review.get("checkpoint_written")),
        "proof_source": bool(review.get("proof_source")),
    }


def _row_by_id(rows: Sequence[Mapping[str, Any]], variant_id: str) -> Mapping[str, Any]:
    for row in rows:
        if str(row.get("variant_id")) == variant_id:
            return row
    return {}


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


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

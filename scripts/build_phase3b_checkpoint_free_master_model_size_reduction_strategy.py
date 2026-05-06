from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
LOG_ROOT = PROJECT_ROOT / ".codex_test_logs" / "phase3b" / "local_13900ks_tuning_20260430"

DEFAULT_PARAMETER_SUMMARY = (
    ARTIFACT_ROOT
    / "22_master_presolve_parameter_result_review"
    / "master_presolve_parameter_result_summary.json"
)
BASELINE_RUN_ID = "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001"
DEFAULT_BASELINE_RUN_PLAN = (
    ARTIFACT_ROOT / "08_checkpoint_free_evaluator" / BASELINE_RUN_ID / "run_plan.json"
)
DEFAULT_BASELINE_STAGE_HEARTBEATS = (
    LOG_ROOT / "08_checkpoint_free_evaluator" / BASELINE_RUN_ID / "stage_heartbeats.jsonl"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "23_master_model_size_reduction_strategy"

_MAX_CLIQUE_RE = re.compile(
    r"MaxClique\] Merged ([0-9']+) constraints with ([0-9']+) literals into "
    r"([0-9']+) constraints with ([0-9']+) literals"
)
_TRANSFORM_EXACTLY_ONE_RE = re.compile(
    r"TransformClausesToExactlyOne.*#num_amos=([0-9']+).*#num_clauses=([0-9']+)"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_master_model_size_reduction_strategy(
        parameter_summary_path=_resolve_path(PROJECT_ROOT, args.parameter_summary),
        baseline_run_plan_path=_resolve_path(PROJECT_ROOT, args.baseline_run_plan),
        baseline_stage_heartbeats_path=_resolve_path(PROJECT_ROOT, args.baseline_stage_heartbeats),
    )
    print("phase3b checkpoint-free master model size reduction strategy")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_master_model_size_reduction_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the next local-only strategy after 42x32 parameter-only probes are exhausted."
    )
    parser.add_argument("--parameter-summary", type=Path, default=DEFAULT_PARAMETER_SUMMARY)
    parser.add_argument("--baseline-run-plan", type=Path, default=DEFAULT_BASELINE_RUN_PLAN)
    parser.add_argument("--baseline-stage-heartbeats", type=Path, default=DEFAULT_BASELINE_STAGE_HEARTBEATS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_master_model_size_reduction_strategy(
    *,
    parameter_summary_path: Path,
    baseline_run_plan_path: Path,
    baseline_stage_heartbeats_path: Path,
) -> dict[str, Any]:
    parameter_summary = _load_json(parameter_summary_path)
    run_plan = _load_json(baseline_run_plan_path)
    log_rows = _load_stage_log_payloads(baseline_stage_heartbeats_path)
    log_metrics = _extract_log_scale_metrics(log_rows)
    parameter_interpretation = _mapping(parameter_summary.get("interpretation"))
    parameter_recommendation = _mapping(parameter_summary.get("recommendation"))
    wave = _mapping(run_plan.get("wave"))
    entries = [
        _mapping(entry)
        for entry in list(wave.get("entries", []) or [])
        if isinstance(entry, Mapping)
    ]
    primary_entry = entries[0] if entries else {}
    candidate_tuple = list(primary_entry.get("candidate", []) or [])
    candidate_key = str(primary_entry.get("candidate_key") or "")
    clean = bool(parameter_interpretation.get("sensitive_paths_clean")) and bool(
        parameter_interpretation.get("checkpoints_clean")
    )
    parameter_exhausted = (
        parameter_interpretation.get("classification")
        == "parameter_micro_matrix_exhausted_without_search_start"
        and parameter_recommendation.get("action") == "prepare_master_model_size_reduction_strategy"
    )
    ready = parameter_exhausted and clean and candidate_key == "42x32"
    return {
        "schema": "phase3b-checkpoint-free-master-model-size-reduction-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strategy_kind": "local_checkpoint_free_master_model_size_reduction_strategy_manifest_only",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "parameter_summary_path": str(parameter_summary_path),
        "baseline_run_plan_path": str(baseline_run_plan_path),
        "baseline_stage_heartbeats_path": str(baseline_stage_heartbeats_path),
        "target": {
            "candidate_key": candidate_key,
            "candidate_tuple": candidate_tuple,
            "ghost_rect": {
                "w": int(candidate_tuple[1]) if len(candidate_tuple) >= 3 else None,
                "h": int(candidate_tuple[2]) if len(candidate_tuple) >= 3 else None,
                "area": int(candidate_tuple[0]) if candidate_tuple else None,
            },
            "run_id": run_plan.get("run_id"),
            "duration_seconds": run_plan.get("duration_seconds"),
            "wave_selection_kind": wave.get("selection_kind"),
        },
        "evidence": {
            "parameter_matrix_classification": parameter_interpretation.get("classification"),
            "symmetry_disabled_removed_symmetry_graph": parameter_interpretation.get(
                "symmetry_disabled_removed_symmetry_graph"
            ),
            "any_search_started_in_parameter_matrix": parameter_interpretation.get("any_search_started"),
            "baseline_max_sat_presolve_vars": _mapping(parameter_summary.get("baseline")).get(
                "max_sat_presolve_vars"
            ),
            "baseline_max_symmetry_nodes": _mapping(parameter_summary.get("baseline")).get(
                "max_symmetry_nodes"
            ),
            "log_scale_metrics": log_metrics,
        },
        "interpretation": {
            "classification": (
                "master_model_size_reduction_required_before_more_42x32_runtime"
                if ready
                else "manual_review_required"
            ),
            "parameter_only_path_exhausted": parameter_exhausted,
            "safety_clean": clean,
            "target_confirmed": candidate_key == "42x32",
            "dominant_observation": (
                "CP-SAT parameters can remove symmetry graph work but do not materially reduce the SAT presolve scale."
                if ready
                else "Inputs do not yet justify model-size strategy."
            ),
        },
        "hypotheses": _hypotheses(log_metrics),
        "recommended_next_artifacts": _recommended_next_artifacts(ready),
        "recommendation": {
            "action": "prepare_no_solve_master_proto_inventory" if ready else "hold_manual_review",
            "next_engineering_step": (
                "build a no-solve 42x32 master proto/build_stats inventory that constructs the exact overlay but does not call CpSolver.Solve"
                if ready
                else "review parameter summary and run-plan inputs before proceeding"
            ),
            "blocked_actions": [
                "do_not_run_more_parameter_only_42x32_variants",
                "do_not_extend_42x32_duration",
                "do_not_run_67x20_hotspot_followup_yet",
                "do_not_run_4x5_hotspot_followup_yet",
                "do_not_retry_2x10_hotspot_profile",
                "do_not_run_full_wave_matrix",
                "do_not_promote_local_results_to_proof",
                "do_not_write_canonical_checkpoints",
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
            "next_artifact_must_be_no_solve": True,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_master_model_size_reduction_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "master_model_size_reduction_strategy.json"
    md_path = output_dir / "master_model_size_reduction_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_master_model_size_reduction_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_master_model_size_reduction_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    target = _mapping(strategy.get("target"))
    evidence = _mapping(strategy.get("evidence"))
    interpretation = _mapping(strategy.get("interpretation"))
    recommendation = _mapping(strategy.get("recommendation"))
    lines = [
        "# Phase3B Master Model Size Reduction Strategy",
        "",
        f"- Generated: `{strategy.get('generated_at')}`",
        f"- Target candidate: `{target.get('candidate_key')}`",
        f"- Ghost rect: `{target.get('ghost_rect')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Evidence",
        "",
        f"- Parameter matrix classification: `{evidence.get('parameter_matrix_classification')}`",
        f"- Baseline SAT presolve vars: `{evidence.get('baseline_max_sat_presolve_vars')}`",
        f"- Baseline symmetry nodes: `{evidence.get('baseline_max_symmetry_nodes')}`",
        "",
        "## Hypotheses",
        "",
    ]
    for item in list(strategy.get("hypotheses", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('summary')}")
    lines.extend(
        [
            "",
            "## Next Artifacts",
            "",
        ]
    )
    for item in list(strategy.get("recommended_next_artifacts", []) or []):
        lines.append(f"- `{item.get('artifact_id')}`: {item.get('purpose')}")
    lines.extend(
        [
            "",
            "This is a local diagnostic strategy only. It does not authorize more runtime, checkpoint writes, proof promotion, or production-default changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _hypotheses(log_metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "sat_presolve_scale_dominates_after_symmetry_removed",
            "summary": (
                "Symmetry can be removed, but SAT presolve still exposes roughly million-variable scale; "
                "model structure, not solver parameter selection, is now the primary target."
            ),
            "evidence_fields": ["baseline_max_sat_presolve_vars", "sym0_max_sat_presolve_vars"],
        },
        {
            "id": "large_at_most_one_and_exactly_one_conversion",
            "summary": (
                "Captured log lines show large MaxClique / TransformClausesToExactlyOne activity; "
                "the no-solve inventory should count constraint families and variable ownership before changing code."
            ),
            "evidence": {
                "max_clique_merged_constraints": log_metrics.get("max_clique_merged_constraints"),
                "transform_exactly_one_num_amos": log_metrics.get("transform_exactly_one_num_amos"),
            },
        },
        {
            "id": "warm_start_hint_sparse_relative_to_master_variables",
            "summary": (
                "The log reports only 798 of 58036 non-fixed variables hinted; model reduction should inspect "
                "whether unguided optional/pose channels dominate the 42x32 overlay."
            ),
            "evidence": {"hint_line_seen": bool(log_metrics.get("hint_line_seen"))},
        },
    ]


def _recommended_next_artifacts(ready: bool) -> list[dict[str, Any]]:
    if not ready:
        return []
    return [
        {
            "artifact_id": "24_master_proto_inventory",
            "purpose": (
                "Construct the 42x32 exact master overlay without CpSolver.Solve and write ModelProto/build_stats "
                "counts by variable and constraint family."
            ),
            "execution_mode": "no_solve_read_only_local_artifact",
            "must_not_call": ["CpSolver.Solve", "ExactCampaign.load_or_create", "main.py"],
        },
        {
            "artifact_id": "25_candidate_shape_inventory_comparison",
            "purpose": (
                "Compare no-solve model-size counts for 42x32 against already-seen safer shapes before any new runtime."
            ),
            "execution_mode": "no_solve_read_only_local_artifact",
            "requires": ["24_master_proto_inventory"],
        },
        {
            "artifact_id": "26_structure_reduction_patch_spec",
            "purpose": (
                "Only after inventory evidence, propose a default-off structure reduction patch with proof-semantics untouched."
            ),
            "execution_mode": "manifest_or_patch_spec_first",
            "requires": ["24_master_proto_inventory", "25_candidate_shape_inventory_comparison"],
        },
    ]


def _load_stage_log_payloads(path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, Mapping):
                payload = value.get("payload")
                if isinstance(payload, Mapping) and payload.get("stage") == "master_solve_log":
                    rows.append(payload)
    return rows


def _extract_log_scale_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    max_clique_merged_constraints = 0
    transform_exactly_one_num_amos = 0
    transform_exactly_one_num_clauses = 0
    hint_line_seen = False
    for row in rows:
        text = str(row.get("text") or "")
        if "The solution hint is incomplete" in text:
            hint_line_seen = True
        clique = _MAX_CLIQUE_RE.search(text)
        if clique:
            max_clique_merged_constraints = max(
                max_clique_merged_constraints,
                _parse_int(clique.group(1)),
                _parse_int(clique.group(3)),
            )
        exactly_one = _TRANSFORM_EXACTLY_ONE_RE.search(text)
        if exactly_one:
            transform_exactly_one_num_amos = max(
                transform_exactly_one_num_amos,
                _parse_int(exactly_one.group(1)),
            )
            transform_exactly_one_num_clauses = max(
                transform_exactly_one_num_clauses,
                _parse_int(exactly_one.group(2)),
            )
    return {
        "log_line_count": len(rows),
        "hint_line_seen": hint_line_seen,
        "max_clique_merged_constraints": max_clique_merged_constraints,
        "transform_exactly_one_num_amos": transform_exactly_one_num_amos,
        "transform_exactly_one_num_clauses": transform_exactly_one_num_clauses,
    }


def _parse_int(text: str) -> int:
    return int(str(text).replace("'", ""))


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

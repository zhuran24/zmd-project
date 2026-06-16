from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_SCOREBOARD = ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_eval_scoreboard.json"
DEFAULT_READINESS = ARTIFACT_ROOT / "07_short_run_readiness" / "short_run_readiness_packet.json"
DEFAULT_RESOURCE_STRATEGY = ARTIFACT_ROOT / "13_resource_hotspot_strategy" / "resource_hotspot_strategy.json"
DEFAULT_STAGE_HEARTBEAT_REVIEW = (
    ARTIFACT_ROOT / "18_stage_heartbeat_review" / "stage_heartbeat_review.json"
)
DEFAULT_MASTER_SOLVE_LOG_REVIEW = (
    ARTIFACT_ROOT / "20_master_solve_log_review" / "master_solve_log_review.json"
)
DEFAULT_MASTER_PRESOLVE_PARAMETER_MATRIX = (
    ARTIFACT_ROOT
    / "21_master_presolve_parameter_micro_matrix"
    / "master_presolve_parameter_micro_matrix.json"
)
DEFAULT_MASTER_PRESOLVE_PARAMETER_RESULT_SUMMARY = (
    ARTIFACT_ROOT
    / "22_master_presolve_parameter_result_review"
    / "master_presolve_parameter_result_summary.json"
)
DEFAULT_MASTER_MODEL_SIZE_REDUCTION_STRATEGY = (
    ARTIFACT_ROOT
    / "23_master_model_size_reduction_strategy"
    / "master_model_size_reduction_strategy.json"
)
DEFAULT_MASTER_PROTO_INVENTORY_REVIEW = (
    ARTIFACT_ROOT
    / "25_master_proto_inventory_review"
    / "master_proto_inventory_review.json"
)
DEFAULT_GHOST_OVERLAY_CONSTRAINT_REDUCTION_STRATEGY = (
    ARTIFACT_ROOT
    / "26_ghost_overlay_constraint_reduction_strategy"
    / "ghost_overlay_constraint_reduction_strategy.json"
)
DEFAULT_FAMILY_BOUND_ABLATION_PATCH_SPEC = (
    ARTIFACT_ROOT
    / "28_family_bound_ablation_patch_spec"
    / "family_bound_ablation_patch_spec.json"
)
DEFAULT_CANDIDATE_SHAPE_INVENTORY_COMPARISON = (
    ARTIFACT_ROOT
    / "29_candidate_shape_inventory_comparison"
    / "candidate_shape_inventory_comparison_exec_001"
    / "candidate_shape_inventory_comparison.json"
)
DEFAULT_CANDIDATE_SHAPE_SCALING_REVIEW = (
    ARTIFACT_ROOT
    / "30_candidate_shape_scaling_review"
    / "candidate_shape_scaling_review.json"
)
DEFAULT_VIA_POLE_SHAPE_INSTRUMENTATION_PATCH_SPEC = (
    ARTIFACT_ROOT
    / "31_via_pole_shape_instrumentation_patch_spec"
    / "via_pole_shape_instrumentation_patch_spec.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "09_checkpoint_free_scoreboard"

W3_W6_BLOCKER_ID = "W1_prod_4x4_stage_6_4_2_4"
BASELINE_ID = "B0_prod_4x4"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    decision = build_checkpoint_free_next_decision(
        scoreboard_path=_resolve_path(PROJECT_ROOT, args.scoreboard),
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        resource_strategy_path=_resolve_optional_path(PROJECT_ROOT, args.resource_strategy),
        stage_heartbeat_review_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.stage_heartbeat_review,
        ),
        master_solve_log_review_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.master_solve_log_review,
        ),
        master_presolve_parameter_matrix_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.master_presolve_parameter_matrix,
        ),
        master_presolve_parameter_result_summary_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.master_presolve_parameter_result_summary,
        ),
        master_model_size_reduction_strategy_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.master_model_size_reduction_strategy,
        ),
        master_proto_inventory_review_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.master_proto_inventory_review,
        ),
        ghost_overlay_constraint_reduction_strategy_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.ghost_overlay_constraint_reduction_strategy,
        ),
        family_bound_ablation_patch_spec_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.family_bound_ablation_patch_spec,
        ),
        candidate_shape_inventory_comparison_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.candidate_shape_inventory_comparison,
        ),
        candidate_shape_scaling_review_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.candidate_shape_scaling_review,
        ),
        via_pole_shape_instrumentation_patch_spec_path=_resolve_optional_path(
            PROJECT_ROOT,
            args.via_pole_shape_instrumentation_patch_spec,
        ),
    )
    print("phase3b checkpoint-free next decision")
    print(f"recommendation={decision['recommendation']['action']}")
    print(f"next_candidate_ids={','.join(decision['recommendation']['next_candidate_ids'])}")
    print(f"blocked_candidate_count={len(decision['blocked_candidates'])}")
    if not args.no_write:
        paths = write_checkpoint_free_next_decision(decision, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"decision_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"decision_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local non-proof next-run decision from checkpoint-free evaluator telemetry."
    )
    parser.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--resource-strategy", type=Path, default=DEFAULT_RESOURCE_STRATEGY)
    parser.add_argument("--stage-heartbeat-review", type=Path, default=DEFAULT_STAGE_HEARTBEAT_REVIEW)
    parser.add_argument("--master-solve-log-review", type=Path, default=DEFAULT_MASTER_SOLVE_LOG_REVIEW)
    parser.add_argument(
        "--master-presolve-parameter-matrix",
        type=Path,
        default=DEFAULT_MASTER_PRESOLVE_PARAMETER_MATRIX,
    )
    parser.add_argument(
        "--master-presolve-parameter-result-summary",
        type=Path,
        default=DEFAULT_MASTER_PRESOLVE_PARAMETER_RESULT_SUMMARY,
    )
    parser.add_argument(
        "--master-model-size-reduction-strategy",
        type=Path,
        default=DEFAULT_MASTER_MODEL_SIZE_REDUCTION_STRATEGY,
    )
    parser.add_argument(
        "--master-proto-inventory-review",
        type=Path,
        default=DEFAULT_MASTER_PROTO_INVENTORY_REVIEW,
    )
    parser.add_argument(
        "--ghost-overlay-constraint-reduction-strategy",
        type=Path,
        default=DEFAULT_GHOST_OVERLAY_CONSTRAINT_REDUCTION_STRATEGY,
    )
    parser.add_argument(
        "--family-bound-ablation-patch-spec",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_ABLATION_PATCH_SPEC,
    )
    parser.add_argument(
        "--candidate-shape-inventory-comparison",
        type=Path,
        default=DEFAULT_CANDIDATE_SHAPE_INVENTORY_COMPARISON,
    )
    parser.add_argument(
        "--candidate-shape-scaling-review",
        type=Path,
        default=DEFAULT_CANDIDATE_SHAPE_SCALING_REVIEW,
    )
    parser.add_argument(
        "--via-pole-shape-instrumentation-patch-spec",
        type=Path,
        default=DEFAULT_VIA_POLE_SHAPE_INSTRUMENTATION_PATCH_SPEC,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_checkpoint_free_next_decision(
    *,
    scoreboard_path: Path,
    readiness_path: Path,
    resource_strategy_path: Path | None = None,
    stage_heartbeat_review_path: Path | None = None,
    master_solve_log_review_path: Path | None = None,
    master_presolve_parameter_matrix_path: Path | None = None,
    master_presolve_parameter_result_summary_path: Path | None = None,
    master_model_size_reduction_strategy_path: Path | None = None,
    master_proto_inventory_review_path: Path | None = None,
    ghost_overlay_constraint_reduction_strategy_path: Path | None = None,
    family_bound_ablation_patch_spec_path: Path | None = None,
    candidate_shape_inventory_comparison_path: Path | None = None,
    candidate_shape_scaling_review_path: Path | None = None,
    via_pole_shape_instrumentation_patch_spec_path: Path | None = None,
) -> dict[str, Any]:
    scoreboard = _load_json(scoreboard_path)
    readiness = _load_json(readiness_path)
    resource_strategy = _load_json(resource_strategy_path) if resource_strategy_path and resource_strategy_path.exists() else {}
    stage_heartbeat_review = (
        _load_json(stage_heartbeat_review_path)
        if stage_heartbeat_review_path and stage_heartbeat_review_path.exists()
        else {}
    )
    master_solve_log_review = (
        _load_json(master_solve_log_review_path)
        if master_solve_log_review_path and master_solve_log_review_path.exists()
        else {}
    )
    master_presolve_parameter_matrix = (
        _load_json(master_presolve_parameter_matrix_path)
        if master_presolve_parameter_matrix_path and master_presolve_parameter_matrix_path.exists()
        else {}
    )
    master_presolve_parameter_result_summary = (
        _load_json(master_presolve_parameter_result_summary_path)
        if master_presolve_parameter_result_summary_path
        and master_presolve_parameter_result_summary_path.exists()
        else {}
    )
    master_model_size_reduction_strategy = (
        _load_json(master_model_size_reduction_strategy_path)
        if master_model_size_reduction_strategy_path
        and master_model_size_reduction_strategy_path.exists()
        else {}
    )
    master_proto_inventory_review = (
        _load_json(master_proto_inventory_review_path)
        if master_proto_inventory_review_path
        and master_proto_inventory_review_path.exists()
        else {}
    )
    ghost_overlay_constraint_reduction_strategy = (
        _load_json(ghost_overlay_constraint_reduction_strategy_path)
        if ghost_overlay_constraint_reduction_strategy_path
        and ghost_overlay_constraint_reduction_strategy_path.exists()
        else {}
    )
    family_bound_ablation_patch_spec = (
        _load_json(family_bound_ablation_patch_spec_path)
        if family_bound_ablation_patch_spec_path
        and family_bound_ablation_patch_spec_path.exists()
        else {}
    )
    candidate_shape_inventory_comparison = (
        _load_json(candidate_shape_inventory_comparison_path)
        if candidate_shape_inventory_comparison_path
        and candidate_shape_inventory_comparison_path.exists()
        else {}
    )
    candidate_shape_scaling_review = (
        _load_json(candidate_shape_scaling_review_path)
        if candidate_shape_scaling_review_path
        and candidate_shape_scaling_review_path.exists()
        else {}
    )
    via_pole_shape_instrumentation_patch_spec = (
        _load_json(via_pole_shape_instrumentation_patch_spec_path)
        if via_pole_shape_instrumentation_patch_spec_path
        and via_pole_shape_instrumentation_patch_spec_path.exists()
        else {}
    )
    selected_ids = [str(candidate_id) for candidate_id in readiness.get("selected_candidate_ids", [])]
    runs = [run for run in scoreboard.get("runs", []) if isinstance(run, Mapping)]
    runs_by_candidate = _latest_runs_by_candidate(runs)

    w1_resource_stopped = bool(_mapping(runs_by_candidate.get(W3_W6_BLOCKER_ID)).get("resource_stop_triggered"))
    baseline_600s_block_reason = _baseline_600s_block_reason(runs)
    sensitive_mutation_detected = bool(_mapping(scoreboard.get("safety")).get("sensitive_path_mutation_detected"))
    global_block_reason = (
        "sensitive_path_mutation_detected"
        if sensitive_mutation_detected
        else baseline_600s_block_reason
    )
    decisions = []
    for candidate_id in selected_ids:
        run = _mapping(runs_by_candidate.get(candidate_id))
        decisions.append(
            _candidate_decision(
                candidate_id,
                run,
                w1_resource_stopped=w1_resource_stopped,
                global_block_reason=global_block_reason,
            )
        )

    reduced_frontier = _reduced_frontier_no_hotspots_decision(
        runs,
        selected_ids,
        resource_strategy=resource_strategy,
        w1_resource_stopped=w1_resource_stopped,
        sensitive_mutation_detected=sensitive_mutation_detected,
    )
    blocked = [decision for decision in decisions if decision["decision"] in {"hold", "blocked"}]
    next_candidates = [
        decision["candidate_id"]
        for decision in decisions
        if decision["decision"] == "advance_600s"
    ]
    if global_block_reason:
        action = f"hold_for_{global_block_reason}"
        next_candidates = []
    else:
        action = "run_600s_control_then_best_experimental" if next_candidates else "hold_for_manual_review"
    stage_review_gate = _stage_heartbeat_review_gate(stage_heartbeat_review)
    master_log_gate = _master_solve_log_review_gate(master_solve_log_review)
    parameter_matrix_gate = _master_presolve_parameter_matrix_gate(
        master_presolve_parameter_matrix
    )
    parameter_result_gate = _master_presolve_parameter_result_summary_gate(
        master_presolve_parameter_result_summary
    )
    model_size_strategy_gate = _master_model_size_reduction_strategy_gate(
        master_model_size_reduction_strategy
    )
    proto_inventory_review_gate = _master_proto_inventory_review_gate(
        master_proto_inventory_review
    )
    ghost_overlay_strategy_gate = _ghost_overlay_constraint_reduction_strategy_gate(
        ghost_overlay_constraint_reduction_strategy
    )
    family_bound_patch_spec_gate = _family_bound_ablation_patch_spec_gate(
        family_bound_ablation_patch_spec
    )
    candidate_shape_inventory_gate = _candidate_shape_inventory_comparison_gate(
        candidate_shape_inventory_comparison
    )
    candidate_shape_scaling_review_gate = _candidate_shape_scaling_review_gate(
        candidate_shape_scaling_review
    )
    via_pole_shape_instrumentation_patch_spec_gate = (
        _via_pole_shape_instrumentation_patch_spec_gate(
            via_pole_shape_instrumentation_patch_spec
        )
    )
    parameter_matrix_active = bool(parameter_matrix_gate.get("active")) and not sensitive_mutation_detected
    if via_pole_shape_instrumentation_patch_spec_gate.get("active") and not sensitive_mutation_detected:
        action = str(via_pole_shape_instrumentation_patch_spec_gate["action"])
        global_block_reason = via_pole_shape_instrumentation_patch_spec_gate.get("global_block_reason")
        next_candidates = []
    elif candidate_shape_scaling_review_gate.get("active") and not sensitive_mutation_detected:
        action = str(candidate_shape_scaling_review_gate["action"])
        global_block_reason = candidate_shape_scaling_review_gate.get("global_block_reason")
        next_candidates = []
    elif candidate_shape_inventory_gate.get("active") and not sensitive_mutation_detected:
        action = str(candidate_shape_inventory_gate["action"])
        global_block_reason = candidate_shape_inventory_gate.get("global_block_reason")
        next_candidates = []
    elif family_bound_patch_spec_gate.get("active") and not sensitive_mutation_detected:
        action = str(family_bound_patch_spec_gate["action"])
        global_block_reason = family_bound_patch_spec_gate.get("global_block_reason")
        next_candidates = []
    elif ghost_overlay_strategy_gate.get("active") and not sensitive_mutation_detected:
        action = str(ghost_overlay_strategy_gate["action"])
        global_block_reason = ghost_overlay_strategy_gate.get("global_block_reason")
        next_candidates = []
    elif proto_inventory_review_gate.get("active") and not sensitive_mutation_detected:
        action = str(proto_inventory_review_gate["action"])
        global_block_reason = str(proto_inventory_review_gate["global_block_reason"])
        next_candidates = []
    elif model_size_strategy_gate.get("active") and not sensitive_mutation_detected:
        action = str(model_size_strategy_gate["action"])
        global_block_reason = str(model_size_strategy_gate["global_block_reason"])
        next_candidates = []
    elif parameter_result_gate.get("active") and not sensitive_mutation_detected:
        action = str(parameter_result_gate["action"])
        global_block_reason = str(parameter_result_gate["global_block_reason"])
        next_candidates = []
    elif parameter_matrix_gate.get("active") and not sensitive_mutation_detected:
        action = str(parameter_matrix_gate["action"])
        global_block_reason = parameter_matrix_gate.get("global_block_reason")
        next_candidates = [str(parameter_matrix_gate["candidate_id"])]
    elif master_log_gate.get("active") and not sensitive_mutation_detected:
        action = str(master_log_gate["action"])
        global_block_reason = str(master_log_gate["global_block_reason"])
        next_candidates = []
    elif stage_review_gate.get("active") and not sensitive_mutation_detected:
        action = str(stage_review_gate["action"])
        global_block_reason = str(stage_review_gate["global_block_reason"])
        next_candidates = []
    baseline_needed = BASELINE_ID in next_candidates
    duration_seconds = 300 if parameter_matrix_active and next_candidates else (600 if next_candidates else None)
    return {
        "schema": "phase3b-checkpoint-free-next-decision/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "decision_kind": "local_checkpoint_free_next_run_gate",
        "proof_source": False,
        "checkpoint_written": False,
        "fresh_solver_run_started_by_builder": False,
        "scoreboard_path": str(scoreboard_path),
        "readiness_path": str(readiness_path),
        "recommendation": {
            "action": action,
            "global_block_reason": global_block_reason,
            "next_candidate_ids": next_candidates,
            "run_order": next_candidates,
            "baseline_control_included": baseline_needed,
            "duration_seconds": duration_seconds,
            "notes": [
                "Run candidates one at a time with checkpoint-free evaluator only.",
                "Stop immediately if sensitive_path_comparison.changed=true or resource_stop_triggered=true.",
            ],
            "reduced_frontier_no_hotspots": reduced_frontier,
            "stage_heartbeat_review": stage_review_gate,
            "master_solve_log_review": master_log_gate,
            "master_presolve_parameter_matrix": parameter_matrix_gate,
            "master_presolve_parameter_result_summary": parameter_result_gate,
            "master_model_size_reduction_strategy": model_size_strategy_gate,
            "master_proto_inventory_review": proto_inventory_review_gate,
            "ghost_overlay_constraint_reduction_strategy": ghost_overlay_strategy_gate,
            "family_bound_ablation_patch_spec": family_bound_patch_spec_gate,
            "candidate_shape_inventory_comparison": candidate_shape_inventory_gate,
            "candidate_shape_scaling_review": candidate_shape_scaling_review_gate,
            "via_pole_shape_instrumentation_patch_spec": via_pole_shape_instrumentation_patch_spec_gate,
        },
        "candidate_decisions": decisions,
        "blocked_candidates": blocked,
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "sensitive_path_mutation_detected": bool(
                sensitive_mutation_detected
            ),
        },
    }


def write_checkpoint_free_next_decision(decision: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "checkpoint_free_next_decision.json"
    md_path = output_dir / "checkpoint_free_next_decision.md"
    json_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_next_decision_markdown(decision), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_next_decision_markdown(decision: Mapping[str, Any]) -> str:
    recommendation = _mapping(decision.get("recommendation"))
    lines = [
        "# Phase3B Checkpoint-Free Next Decision",
        "",
        f"- Generated: `{decision.get('generated_at')}`",
        f"- Action: `{recommendation.get('action')}`",
        f"- Global block reason: `{recommendation.get('global_block_reason')}`",
        f"- Next candidates: `{', '.join(recommendation.get('next_candidate_ids', []))}`",
        f"- Duration: `{recommendation.get('duration_seconds')}`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "| Candidate | Decision | Reason | Prior status | vs baseline | Peak private GiB |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for item in decision.get("candidate_decisions", []):
        lines.append(
            "| {candidate_id} | {decision} | {reason} | {status} | {score:.3f} | {peak:.2f} |".format(
                candidate_id=item["candidate_id"],
                decision=item["decision"],
                reason=item["reason"],
                status=item.get("prior_status"),
                score=item.get("baseline_normalized_throughput") or 0.0,
                peak=item.get("peak_private_gib") or 0.0,
            )
        )
    reduced = _mapping(recommendation.get("reduced_frontier_no_hotspots"))
    lines.extend(
        [
            "",
            "## Reduced Frontier No-Hotspots Path",
            "",
            f"- Action: `{reduced.get('action')}`",
            f"- Allowed: `{str(bool(reduced.get('allowed'))).lower()}`",
            f"- Avoid keys: `{', '.join(reduced.get('avoid_candidate_keys', []))}`",
            f"- Completed 600s candidates: `{', '.join(reduced.get('completed_candidate_ids', []))}`",
            f"- Next candidates: `{', '.join(reduced.get('next_candidate_ids', []))}`",
            f"- Duration: `{reduced.get('duration_seconds')}`",
            "",
        ]
    )
    stage_review = _mapping(recommendation.get("stage_heartbeat_review"))
    if stage_review:
        lines.extend(
            [
                "## Stage Heartbeat Gate",
                "",
                f"- Active: `{str(bool(stage_review.get('active'))).lower()}`",
                f"- Action: `{stage_review.get('action')}`",
                f"- Stalled stage: `{stage_review.get('stalled_stage')}`",
                f"- Next step: `{stage_review.get('next_engineering_step')}`",
                "",
            ]
        )
    master_log = _mapping(recommendation.get("master_solve_log_review"))
    if master_log:
        lines.extend(
            [
                "## Master-Solve Log Gate",
                "",
                f"- Active: `{str(bool(master_log.get('active'))).lower()}`",
                f"- Action: `{master_log.get('action')}`",
                f"- Classification: `{master_log.get('classification')}`",
                f"- Next step: `{master_log.get('next_engineering_step')}`",
                "",
            ]
        )
    parameter_matrix = _mapping(recommendation.get("master_presolve_parameter_matrix"))
    if parameter_matrix:
        lines.extend(
            [
                "## Master Presolve Parameter Matrix Gate",
                "",
                f"- Active: `{str(bool(parameter_matrix.get('active'))).lower()}`",
                f"- Action: `{parameter_matrix.get('action')}`",
                f"- Candidate id: `{parameter_matrix.get('candidate_id')}`",
                f"- Run id: `{parameter_matrix.get('run_id')}`",
                "",
            ]
        )
    parameter_result = _mapping(recommendation.get("master_presolve_parameter_result_summary"))
    if parameter_result:
        lines.extend(
            [
                "## Master Presolve Parameter Result Gate",
                "",
                f"- Active: `{str(bool(parameter_result.get('active'))).lower()}`",
                f"- Action: `{parameter_result.get('action')}`",
                f"- Classification: `{parameter_result.get('classification')}`",
                f"- Next step: `{parameter_result.get('next_engineering_step')}`",
                "",
            ]
        )
    model_strategy = _mapping(recommendation.get("master_model_size_reduction_strategy"))
    if model_strategy:
        lines.extend(
            [
                "## Master Model Size Reduction Strategy Gate",
                "",
                f"- Active: `{str(bool(model_strategy.get('active'))).lower()}`",
                f"- Action: `{model_strategy.get('action')}`",
                f"- Classification: `{model_strategy.get('classification')}`",
                f"- Next step: `{model_strategy.get('next_engineering_step')}`",
                "",
            ]
        )
    proto_review = _mapping(recommendation.get("master_proto_inventory_review"))
    if proto_review:
        lines.extend(
            [
                "## Master Proto Inventory Review Gate",
                "",
                f"- Active: `{str(bool(proto_review.get('active'))).lower()}`",
                f"- Action: `{proto_review.get('action')}`",
                f"- Classification: `{proto_review.get('classification')}`",
                f"- Next step: `{proto_review.get('next_engineering_step')}`",
                "",
            ]
        )
    ghost_strategy = _mapping(recommendation.get("ghost_overlay_constraint_reduction_strategy"))
    if ghost_strategy:
        lines.extend(
            [
                "## Ghost Overlay Constraint Strategy Gate",
                "",
                f"- Active: `{str(bool(ghost_strategy.get('active'))).lower()}`",
                f"- Action: `{ghost_strategy.get('action')}`",
                f"- Classification: `{ghost_strategy.get('classification')}`",
                f"- Command: `{ghost_strategy.get('command_template')}`",
                f"- Env: `{ghost_strategy.get('env')}`",
                "",
            ]
        )
    patch_spec = _mapping(recommendation.get("family_bound_ablation_patch_spec"))
    if patch_spec:
        lines.extend(
            [
                "## Family Bound Ablation Patch Spec Gate",
                "",
                f"- Active: `{str(bool(patch_spec.get('active'))).lower()}`",
                f"- Action: `{patch_spec.get('action')}`",
                f"- Classification: `{patch_spec.get('classification')}`",
                f"- Source mutation performed: `{patch_spec.get('source_mutation_performed')}`",
                f"- Next step: `{patch_spec.get('next_engineering_step')}`",
                "",
            ]
        )
    candidate_shape = _mapping(recommendation.get("candidate_shape_inventory_comparison"))
    if candidate_shape:
        lines.extend(
            [
                "## Candidate Shape Inventory Comparison Gate",
                "",
                f"- Active: `{str(bool(candidate_shape.get('active'))).lower()}`",
                f"- Action: `{candidate_shape.get('action')}`",
                f"- Classification: `{candidate_shape.get('classification')}`",
                f"- Completed non-baseline shapes: `{candidate_shape.get('non_baseline_completed_shape_count')}`",
                f"- Sensitive paths changed: `{candidate_shape.get('sensitive_paths_changed')}`",
                f"- Next step: `{candidate_shape.get('next_engineering_step')}`",
                "",
            ]
        )
    shape_review = _mapping(recommendation.get("candidate_shape_scaling_review"))
    if shape_review:
        lines.extend(
            [
                "## Candidate Shape Scaling Review Gate",
                "",
                f"- Active: `{str(bool(shape_review.get('active'))).lower()}`",
                f"- Action: `{shape_review.get('action')}`",
                f"- Classification: `{shape_review.get('classification')}`",
                f"- Source mutation performed: `{shape_review.get('source_mutation_performed')}`",
                f"- Next step: `{shape_review.get('next_engineering_step')}`",
                "",
            ]
        )
    via_pole_spec = _mapping(recommendation.get("via_pole_shape_instrumentation_patch_spec"))
    if via_pole_spec:
        lines.extend(
            [
                "## Via-Pole Shape Instrumentation Patch Spec Gate",
                "",
                f"- Active: `{str(bool(via_pole_spec.get('active'))).lower()}`",
                f"- Action: `{via_pole_spec.get('action')}`",
                f"- Classification: `{via_pole_spec.get('classification')}`",
                f"- Implementation allowed now: `{via_pole_spec.get('implementation_allowed_now')}`",
                f"- Source mutation authorized by this artifact: `{via_pole_spec.get('source_mutation_authorized_by_this_artifact')}`",
                f"- Next step: `{via_pole_spec.get('next_engineering_step')}`",
                "",
            ]
        )
    lines.extend(
        [
            "",
            "This gate is local tuning guidance only. It does not authorize final 168h, canonical checkpoints, proof promotion, or production default changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _stage_heartbeat_review_gate(review: Mapping[str, Any]) -> dict[str, Any]:
    if not review:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "stalled_stage": None,
            "next_engineering_step": None,
        }
    recommendation = _mapping(review.get("recommendation"))
    interpretation = _mapping(review.get("interpretation"))
    action = str(recommendation.get("action") or "")
    stalled_stage = str(interpretation.get("stalled_stage") or "")
    active = action == "prepare_master_solve_micro_diagnostics" and stalled_stage == "master_solve"
    return {
        "active": active,
        "action": "hold_for_master_solve_micro_diagnostics" if active else "hold_for_stage_review",
        "global_block_reason": "master_solve_hotspot_diagnostic_required"
        if active
        else "stage_heartbeat_review_present",
        "review_run_id": _mapping(review.get("run")).get("run_id"),
        "stalled_stage": stalled_stage or None,
        "stalled_reason": interpretation.get("stalled_reason"),
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _master_solve_log_review_gate(review: Mapping[str, Any]) -> dict[str, Any]:
    if not review:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "next_engineering_step": None,
        }
    recommendation = _mapping(review.get("recommendation"))
    interpretation = _mapping(review.get("interpretation"))
    action = str(recommendation.get("action") or "")
    classification = str(interpretation.get("classification") or "")
    active = (
        action == "prepare_master_presolve_parameter_micro_matrix"
        and classification == "presolve_symmetry_scale_bottleneck_before_search"
    )
    return {
        "active": active,
        "action": "hold_for_master_presolve_parameter_micro_matrix"
        if active
        else "hold_for_master_solve_log_review",
        "global_block_reason": "master_presolve_parameter_matrix_required"
        if active
        else "master_solve_log_review_present",
        "review_run_id": _mapping(review.get("run")).get("run_id"),
        "classification": classification or None,
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _master_presolve_parameter_matrix_gate(matrix: Mapping[str, Any]) -> dict[str, Any]:
    if not matrix:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "candidate_id": None,
            "run_id": None,
        }
    recommendation = _mapping(matrix.get("recommendation"))
    action = str(recommendation.get("action") or "")
    candidate_id = recommendation.get("first_candidate_id")
    run_id = recommendation.get("first_run_id")
    active = action == "ready_for_single_sym0_micro_probe" and bool(candidate_id)
    return {
        "active": active,
        "action": "run_single_master_presolve_parameter_micro_probe"
        if active
        else "hold_for_master_presolve_parameter_matrix_review",
        "global_block_reason": None if active else "master_presolve_parameter_matrix_present",
        "candidate_id": candidate_id,
        "run_id": run_id,
        "matrix_action": action,
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _master_presolve_parameter_result_summary_gate(summary: Mapping[str, Any]) -> dict[str, Any]:
    if not summary:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(summary.get("interpretation"))
    recommendation = _mapping(summary.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    clean = bool(interpretation.get("sensitive_paths_clean")) and bool(
        interpretation.get("checkpoints_clean")
    )
    active = classification == "parameter_micro_matrix_exhausted_without_search_start" and clean
    return {
        "active": active,
        "action": "hold_for_master_model_size_reduction_strategy"
        if active
        else "hold_for_parameter_result_summary_review",
        "global_block_reason": "master_model_size_reduction_strategy_required"
        if active
        else "master_presolve_parameter_result_summary_present",
        "classification": classification or None,
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _master_model_size_reduction_strategy_gate(strategy: Mapping[str, Any]) -> dict[str, Any]:
    if not strategy:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(strategy.get("interpretation"))
    recommendation = _mapping(strategy.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    active = (
        classification == "master_model_size_reduction_required_before_more_42x32_runtime"
        and action == "prepare_no_solve_master_proto_inventory"
    )
    return {
        "active": active,
        "action": "hold_for_no_solve_master_proto_inventory",
        "global_block_reason": "no_solve_master_proto_inventory_required",
        "classification": classification or None,
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _master_proto_inventory_review_gate(review: Mapping[str, Any]) -> dict[str, Any]:
    if not review:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    active = (
        classification == "ghost_overlay_constraint_build_dominates"
        and action == "prepare_ghost_overlay_constraint_reduction_strategy"
    )
    return {
        "active": active,
        "action": "hold_for_ghost_overlay_constraint_reduction_strategy"
        if active
        else "hold_for_master_proto_inventory_review",
        "global_block_reason": "ghost_overlay_constraint_reduction_strategy_required"
        if active
        else "master_proto_inventory_review_present",
        "classification": classification or None,
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _ghost_overlay_constraint_reduction_strategy_gate(strategy: Mapping[str, Any]) -> dict[str, Any]:
    if not strategy:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "command_template": None,
            "env": None,
        }
    interpretation = _mapping(strategy.get("interpretation"))
    recommendation = _mapping(strategy.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    first_action = next(
        (
            _mapping(item)
            for item in list(strategy.get("candidate_actions", []) or [])
            if _mapping(item).get("id") == "no_solve_enforced_family_bound_formulation_probe"
        ),
        {},
    )
    active = (
        classification == "family_bound_overlay_dominates"
        and action == "run_no_solve_enforced_family_bound_formulation_probe"
        and bool(first_action.get("allowed"))
    )
    return {
        "active": active,
        "action": "run_no_solve_enforced_family_bound_formulation_probe"
        if active
        else "hold_for_ghost_overlay_constraint_reduction_strategy",
        "global_block_reason": None if active else "ghost_overlay_constraint_strategy_present",
        "classification": classification or None,
        "command_template": first_action.get("command_template"),
        "env": first_action.get("env"),
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _family_bound_ablation_patch_spec_gate(spec: Mapping[str, Any]) -> dict[str, Any]:
    if not spec:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "source_mutation_performed": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(spec.get("interpretation"))
    recommendation = _mapping(spec.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    active = (
        classification == "patch_spec_ready_source_mutation_still_blocked"
        and action == "prepare_no_source_candidate_shape_inventory_comparison"
        and spec.get("source_mutation_performed") is False
    )
    return {
        "active": active,
        "action": "prepare_no_source_candidate_shape_inventory_comparison"
        if active
        else "hold_for_family_bound_ablation_patch_spec_review",
        "global_block_reason": None if active else "family_bound_ablation_patch_spec_present",
        "classification": classification or None,
        "source_mutation_performed": spec.get("source_mutation_performed"),
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _candidate_shape_inventory_comparison_gate(comparison: Mapping[str, Any]) -> dict[str, Any]:
    if not comparison:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "completed_shape_count": None,
            "non_baseline_completed_shape_count": None,
            "sensitive_paths_changed": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(comparison.get("interpretation"))
    recommendation = _mapping(comparison.get("recommendation"))
    sensitive_paths_changed = bool(
        _mapping(comparison.get("sensitive_path_comparison")).get("changed")
    )
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    active = (
        comparison.get("status") == "completed"
        and comparison.get("execute_no_solve") is True
        and classification == "candidate_shape_inventory_comparison_ready"
        and action == "review_no_source_shape_scaling_before_runtime"
        and not sensitive_paths_changed
        and comparison.get("cp_solver_solve_called") is False
        and comparison.get("checkpoint_written") is False
        and comparison.get("source_mutation_performed") is False
        and comparison.get("proof_source") is False
    )
    return {
        "active": active,
        "action": "review_no_source_shape_scaling_before_runtime"
        if active
        else "hold_for_candidate_shape_inventory_comparison_review",
        "global_block_reason": None if active else "candidate_shape_inventory_comparison_present",
        "classification": classification or None,
        "completed_shape_count": interpretation.get("completed_shape_count"),
        "non_baseline_completed_shape_count": interpretation.get(
            "non_baseline_completed_shape_count"
        ),
        "sensitive_paths_changed": sensitive_paths_changed,
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _candidate_shape_scaling_review_gate(review: Mapping[str, Any]) -> dict[str, Any]:
    if not review:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "source_mutation_performed": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    active = (
        review.get("status") == "completed"
        and classification == "shape_specific_via_pole_anchor_explosion"
        and action == "prepare_default_off_via_pole_shape_instrumentation_patch_spec"
        and review.get("cp_solver_solve_called") is False
        and review.get("checkpoint_written") is False
        and review.get("source_mutation_performed") is False
        and review.get("proof_source") is False
        and not bool(_mapping(review.get("sensitive_path_comparison")).get("changed"))
    )
    return {
        "active": active,
        "action": "prepare_default_off_via_pole_shape_instrumentation_patch_spec"
        if active
        else "hold_for_candidate_shape_scaling_review",
        "global_block_reason": None if active else "candidate_shape_scaling_review_present",
        "classification": classification or None,
        "source_mutation_performed": review.get("source_mutation_performed"),
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _via_pole_shape_instrumentation_patch_spec_gate(spec: Mapping[str, Any]) -> dict[str, Any]:
    if not spec:
        return {
            "active": False,
            "action": None,
            "global_block_reason": None,
            "classification": None,
            "implementation_allowed_now": None,
            "source_mutation_authorized_by_this_artifact": None,
            "next_engineering_step": None,
        }
    interpretation = _mapping(spec.get("interpretation"))
    recommendation = _mapping(spec.get("recommendation"))
    classification = str(interpretation.get("classification") or "")
    action = str(recommendation.get("action") or "")
    active = (
        classification == "patch_spec_ready_source_mutation_still_blocked"
        and action == "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
        and spec.get("source_mutation_performed") is False
        and interpretation.get("implementation_allowed_now") is False
        and interpretation.get("source_mutation_authorized_by_this_artifact") is False
    )
    return {
        "active": active,
        "action": "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
        if active
        else "hold_for_via_pole_shape_instrumentation_patch_spec_review",
        "global_block_reason": "source_mutation_authorization_required"
        if active
        else "via_pole_shape_instrumentation_patch_spec_present",
        "classification": classification or None,
        "implementation_allowed_now": interpretation.get("implementation_allowed_now"),
        "source_mutation_authorized_by_this_artifact": interpretation.get(
            "source_mutation_authorized_by_this_artifact"
        ),
        "next_engineering_step": recommendation.get("next_engineering_step"),
    }


def _latest_runs_by_candidate(runs: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for run in runs:
        candidate_id = str(run.get("candidate_id"))
        current = selected.get(candidate_id)
        if current is None or _run_recency_key(run) > _run_recency_key(current):
            selected[candidate_id] = run
    return selected


def _run_recency_key(run: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        int(run.get("requested_duration_seconds") or 0),
        int(run.get("wave_max_candidates") or 0),
        str(run.get("run_id") or ""),
    )


def _reduced_frontier_no_hotspots_decision(
    runs: Sequence[Mapping[str, Any]],
    selected_ids: Sequence[str],
    *,
    resource_strategy: Mapping[str, Any],
    w1_resource_stopped: bool,
    sensitive_mutation_detected: bool,
) -> dict[str, Any]:
    strategy_recommendation = _mapping(resource_strategy.get("recommendation"))
    avoid_keys = [
        str(key)
        for key in strategy_recommendation.get("avoid_candidate_keys_for_wave_expansion", [])
        if key is not None
    ]
    if not avoid_keys:
        avoid_keys = sorted(
            {
                str(key)
                for run in runs
                for key in list(run.get("wave_excluded_candidate_keys", []) or [])
                if key is not None
            }
        )
    reduced_runs = [
        run
        for run in runs
        if _is_safe_reduced_frontier_no_hotspots_run(run, avoid_keys)
    ]
    completed_by_candidate = _best_runs_by_candidate(reduced_runs)
    baseline_run = completed_by_candidate.get(BASELINE_ID)

    blocked_reasons: dict[str, str] = {}
    next_candidates: list[str] = []
    completed_ids = [candidate_id for candidate_id in selected_ids if candidate_id in completed_by_candidate]
    for candidate_id in selected_ids:
        if candidate_id == BASELINE_ID or candidate_id in completed_by_candidate:
            continue
        if candidate_id in {"W3_prod_4x4_stage_6_6_2_6", "W6_prod_3x_stage_8_6_2_6"} and w1_resource_stopped:
            blocked_reasons[candidate_id] = "blocked_after_w1_resource_stop"
            continue
        if not baseline_run:
            blocked_reasons[candidate_id] = "reduced_frontier_baseline_not_completed"
            continue
        if not _candidate_has_safe_low_memory_signal(candidate_id, runs):
            blocked_reasons[candidate_id] = "no_safe_low_memory_prior_signal"
            continue
        next_candidates.append(candidate_id)

    if sensitive_mutation_detected:
        action = "blocked_sensitive_path_mutation_detected"
        allowed = False
        next_candidates = []
    elif not avoid_keys:
        action = "blocked_no_hotspot_avoid_keys_available"
        allowed = False
        next_candidates = []
    elif not baseline_run:
        action = "run_reduced_frontier_no_hotspots_baseline_first"
        allowed = True
        next_candidates = [BASELINE_ID] if BASELINE_ID in selected_ids else []
    elif next_candidates:
        action = "continue_reduced_frontier_no_hotspots_only"
        allowed = True
    else:
        action = "hold_reduced_frontier_no_remaining_low_risk_candidates"
        allowed = False

    return {
        "action": action,
        "allowed": allowed,
        "duration_seconds": 600 if allowed or completed_ids else None,
        "avoid_candidate_keys": avoid_keys,
        "baseline_run_id": baseline_run.get("run_id") if baseline_run else None,
        "completed_candidate_ids": completed_ids,
        "completed_run_ids": [
            completed_by_candidate[candidate_id].get("run_id")
            for candidate_id in completed_ids
        ],
        "next_candidate_ids": next_candidates,
        "run_order": next_candidates,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This path is narrower than full-wave testing and must keep hotspot keys excluded.",
            "It does not authorize retrying hotspot keys, full-wave matrix runs, proof promotion, or production default changes.",
        ],
    }


def _is_safe_reduced_frontier_no_hotspots_run(run: Mapping[str, Any], avoid_keys: Sequence[str]) -> bool:
    if int(run.get("requested_duration_seconds") or 0) < 600:
        return False
    if str(run.get("status") or "") != "completed":
        return False
    if run.get("sensitive_path_changed") or run.get("resource_stop_triggered"):
        return False
    if int(run.get("wave_max_candidates") or 0) < 2:
        return False
    selection_kind = str(run.get("wave_selection_kind") or "")
    if selection_kind and selection_kind != "deterministic_frontier_bounded_wave_excluding_keys_v0":
        return False
    excluded_keys = {str(key) for key in list(run.get("wave_excluded_candidate_keys", []) or [])}
    if avoid_keys and not set(avoid_keys).issubset(excluded_keys):
        return False
    return True


def _best_runs_by_candidate(runs: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for run in runs:
        candidate_id = str(run.get("candidate_id"))
        current = selected.get(candidate_id)
        if current is None or _safe_run_quality_key(run) > _safe_run_quality_key(current):
            selected[candidate_id] = run
    return selected


def _safe_run_quality_key(run: Mapping[str, Any]) -> tuple[int, float, int, str]:
    return (
        int(str(run.get("status") or "") == "completed"),
        -(_float(run.get("peak_private_gib")) or 0.0),
        int(run.get("result_count") or 0),
        str(run.get("run_id") or ""),
    )


def _candidate_has_safe_low_memory_signal(candidate_id: str, runs: Sequence[Mapping[str, Any]]) -> bool:
    for run in runs:
        if str(run.get("candidate_id")) != candidate_id:
            continue
        if str(run.get("status") or "") != "completed":
            continue
        if run.get("sensitive_path_changed") or run.get("resource_stop_triggered"):
            continue
        if (_float(run.get("peak_private_gib")) or 999.0) >= 20.0:
            continue
        if int(run.get("result_count") or 0) <= 0:
            continue
        return True
    return False


def _candidate_decision(
    candidate_id: str,
    run: Mapping[str, Any],
    *,
    w1_resource_stopped: bool,
    global_block_reason: str | None,
) -> dict[str, Any]:
    if candidate_id in {"W3_prod_4x4_stage_6_6_2_6", "W6_prod_3x_stage_8_6_2_6"} and w1_resource_stopped:
        return _decision(candidate_id, run, "blocked", "blocked_after_w1_resource_stop")
    if not run:
        return _decision(candidate_id, run, "pending", "no_checkpoint_free_300s_run_yet")
    if run.get("sensitive_path_changed"):
        return _decision(candidate_id, run, "blocked", "sensitive_path_changed")
    if run.get("resource_stop_triggered"):
        return _decision(candidate_id, run, "hold", "resource_stop_triggered")
    if global_block_reason:
        return _decision(candidate_id, run, "hold", f"blocked_by_{global_block_reason}")
    score = _float(run.get("baseline_normalized_throughput")) or 0.0
    peak_private = _float(run.get("peak_private_gib")) or 0.0
    if run.get("timed_out") and (score < 0.5 or peak_private >= 40.0):
        return _decision(candidate_id, run, "hold", "timeout_or_high_memory_with_low_relative_throughput")
    if candidate_id == BASELINE_ID:
        return _decision(candidate_id, run, "advance_600s", "baseline_control_for_600s_confirmation")
    if score >= 1.0 and peak_private < 20.0:
        return _decision(candidate_id, run, "advance_600s", "safe_completed_candidate_at_or_above_baseline")
    return _decision(candidate_id, run, "hold", "insufficient_300s_evidence_for_600s")


def _baseline_600s_block_reason(runs: Sequence[Mapping[str, Any]]) -> str | None:
    baseline_600s_runs = [
        run
        for run in runs
        if run.get("candidate_id") == BASELINE_ID and int(run.get("requested_duration_seconds") or 0) >= 600
    ]
    for run in baseline_600s_runs:
        wave = int(run.get("wave_max_candidates") or 0)
        prefix = "baseline_600s_full_wave" if wave > 1 else "baseline_600s"
        if run.get("sensitive_path_changed"):
            return f"{prefix}_sensitive_path_changed"
        if run.get("resource_stop_triggered"):
            return f"{prefix}_resource_stop"
        status = str(run.get("status") or "")
        if status not in {"completed", "planned_only"}:
            return f"{prefix}_not_completed"
    return None


def _decision(candidate_id: str, run: Mapping[str, Any], decision: str, reason: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "decision": decision,
        "reason": reason,
        "prior_run_id": run.get("run_id"),
        "prior_status": run.get("status"),
        "baseline_normalized_throughput": run.get("baseline_normalized_throughput"),
        "peak_private_gib": run.get("peak_private_gib"),
        "peak_rss_gib": run.get("peak_rss_gib"),
        "resource_stop_triggered": bool(run.get("resource_stop_triggered")),
        "sensitive_path_changed": bool(run.get("sensitive_path_changed")),
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


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _resolve_optional_path(root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return _resolve_path(root, path)


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

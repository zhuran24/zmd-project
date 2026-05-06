from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_STRATEGY = ARTIFACT_ROOT / "36_signature_bucket_tightening_strategy" / "signature_bucket_tightening_strategy.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "37_signature_bucket_tightening_instrumentation_patch_spec"

TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    spec = build_signature_bucket_tightening_instrumentation_patch_spec(
        strategy_path=_resolve_path(PROJECT_ROOT, args.strategy),
    )
    print("phase3b checkpoint-free signature bucket tightening instrumentation patch spec")
    print(f"classification={spec['interpretation']['classification']}")
    print(f"action={spec['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_tightening_instrumentation_patch_spec(
            spec,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"spec_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"spec_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft a no-source-mutation spec for default-off signature bucket tightening instrumentation."
    )
    parser.add_argument("--strategy", type=Path, default=DEFAULT_STRATEGY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_tightening_instrumentation_patch_spec(
    *,
    strategy_path: Path,
) -> dict[str, Any]:
    strategy_path = Path(strategy_path)
    strategy = _load_json(strategy_path)
    interpretation = _mapping(strategy.get("interpretation"))
    recommendation = _mapping(strategy.get("recommendation"))
    ready = (
        strategy.get("status") == "completed"
        and interpretation.get("classification") == "signature_bucket_internal_loop_strategy_required"
        and recommendation.get("action")
        == "prepare_default_off_signature_bucket_tightening_instrumentation_patch_spec"
        and strategy.get("source_model_mutation") is False
        and strategy.get("source_mutation_performed") is False
        and strategy.get("no_solve") is True
    )
    return {
        "schema": "phase3b-checkpoint-free-signature-bucket-tightening-instrumentation-patch-spec/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "spec_kind": "default_off_source_patch_spec_no_mutation",
        "strategy_path": str(strategy_path),
        "fresh_solver_run_started_by_builder": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "no_solve": True,
        "proof_source": False,
        "checkpoint_written": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "evidence": {
            "strategy_classification": interpretation.get("classification"),
            "strategy_action": recommendation.get("action"),
            "hotspot_method": strategy.get("hotspot_method"),
            "strategy_evidence": strategy.get("evidence"),
        },
        "interpretation": {
            "classification": (
                "patch_spec_ready_source_mutation_still_blocked"
                if ready
                else "manual_review_required"
            ),
            "source_mutation_authorized_by_this_artifact": False,
            "implementation_allowed_now": False,
            "reason": (
                "S36 isolates the no-solve 42x32 hotspot inside a monolithic signature-bucket loop; "
                "default-off source instrumentation is the next reasonable diagnostic, but it touches "
                "proof-adjacent model construction and therefore still needs explicit source-patch authorization."
                if ready
                else "S36 strategy is not ready for a signature-bucket instrumentation patch spec."
            ),
        },
        "patch_spec": _patch_spec() if ready else {},
        "validation_plan": _validation_plan() if ready else [],
        "recommendation": {
            "action": (
                "hold_for_default_off_signature_bucket_tightening_source_authorization"
                if ready
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "request or wait for explicit authorization before mutating src/models; after authorization, "
                "implement only default-off instrumentation and validate with tests plus one no-solve 42x32 inventory/probe"
                if ready
                else "review S36 evidence before proceeding"
            ),
            "blocked_actions": [
                "do_not_mutate_src_models_without_explicit_authorization",
                "do_not_run_more_42x32_runtime",
                "do_not_run_67x20",
                "do_not_run_full_wave_matrix",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
        "safety": {
            "spec_only": True,
            "builder_executes_solver": False,
            "builder_constructs_model": False,
            "proof_source": False,
            "checkpoint_written": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_signature_bucket_tightening_instrumentation_patch_spec(
    spec: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_spec_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_tightening_instrumentation_patch_spec.json"
    md_path = output_dir / "signature_bucket_tightening_instrumentation_patch_spec.md"
    json_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_signature_bucket_tightening_instrumentation_patch_spec_markdown(spec), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_signature_bucket_tightening_instrumentation_patch_spec_markdown(spec: Mapping[str, Any]) -> str:
    interpretation = _mapping(spec.get("interpretation"))
    recommendation = _mapping(spec.get("recommendation"))
    patch = _mapping(spec.get("patch_spec"))
    lines = [
        "# Phase3B Signature Bucket Tightening Instrumentation Patch Spec",
        "",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Fresh solver run started by builder: `false`",
        "- No solve: `true`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Proposed Patch",
        "",
        f"- Target file: `{patch.get('target_file')}`",
        f"- Target method: `{patch.get('target_method')}`",
        f"- New env var: `{patch.get('env_var')}`",
        f"- Default behavior: `{patch.get('default_behavior')}`",
        f"- Diagnostic behavior: `{patch.get('diagnostic_behavior')}`",
        "",
        "## Instrumentation Fields",
        "",
    ]
    for item in list(patch.get("instrumentation_fields", []) or []):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Validation Plan", ""])
    for item in list(spec.get("validation_plan", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('check')}")
    lines.extend(
        [
            "",
            "This is a patch specification only. It does not authorize source mutation, proof promotion, canonical checkpoints, runtime, or production-default changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": TARGET_METHOD,
        "env_var": ENV_VAR,
        "default_behavior": "disabled; current model construction and build_stats remain unchanged when the env var is unset",
        "diagnostic_behavior": (
            "when explicitly set to 1/true/on for local no-solve experiments, record signature-bucket "
            "internal-loop counters and timings under build_stats without changing variables or constraints"
        ),
        "build_stats_output_path": (
            "build_stats.global_valid_inequalities.signature_bucket_capacity_bounds.signature_tightening_instrumentation"
        ),
        "instrumentation_fields": [
            "enabled",
            "phase_seconds.payload_build_mandatory",
            "phase_seconds.payload_build_required_optional",
            "phase_seconds.per_anchor_mandatory_scan",
            "phase_seconds.per_anchor_required_optional_scan",
            "phase_seconds.constraint_add",
            "phase_seconds.stats_finalize",
            "totals.evaluated_anchors",
            "totals.ghost_area",
            "totals.mandatory_payloads",
            "totals.required_optional_payloads",
            "totals.cells_scanned",
            "totals.pose_hits",
            "totals.unique_blocked_poses",
            "totals.bucket_reduction_checks",
            "totals.constraints_added",
            "histograms.cells_scanned_per_anchor",
            "histograms.pose_hits_per_anchor",
            "histograms.unique_blocked_poses_per_anchor",
            "histograms.bucket_reductions_per_anchor",
            "top_slow_anchors",
            "top_slow_groups",
            "top_slow_buckets",
            "top_group_bucket_reductions",
        ],
        "non_goals": [
            "do not disable, relax, or rewrite any signature bucket constraint",
            "do not change production defaults",
            "do not connect instrumentation output to proof semantics",
            "do not write canonical checkpoints",
            "do not alter scheduler order or candidate universe",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "default_off_regression",
            "check": "with env unset, focused signature-bucket and exact-contract tests continue to pass and model/proto/build_stats behavior remains unchanged where asserted",
        },
        {
            "id": "instrumentation_unit_test",
            "check": "with env enabled in a small fixture, signature_tightening_instrumentation fields are present and variables/constraints match the default-off model",
        },
        {
            "id": "no_solve_42x32_instrumented_inventory",
            "check": "after explicit authorization only, run exactly one 42x32 no-solve overlay inventory/probe with the env enabled to identify the dominant inner loop",
        },
        {
            "id": "sensitive_path_guard",
            "check": "confirm data/checkpoints, final solution, blueprint, certified manifest, preflight, viewer, release, and frontdoor fingerprints are unchanged",
        },
    ]


def _assert_spec_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "37_signature_bucket_tightening_instrumentation_patch_spec" not in normalized
    ):
        raise ValueError(
            f"Refusing to write outside signature bucket tightening instrumentation patch spec namespace: {path}"
        )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

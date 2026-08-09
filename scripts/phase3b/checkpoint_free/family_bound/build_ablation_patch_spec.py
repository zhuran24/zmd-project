from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_COMPARISON = (
    ARTIFACT_ROOT
    / "27_ghost_overlay_family_bound_formulation_comparison"
    / "family_bound_formulation_comparison.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "28_family_bound_ablation_patch_spec"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    spec = build_family_bound_ablation_patch_spec(
        comparison_path=_resolve_path(PROJECT_ROOT, args.comparison),
    )
    print("phase3b checkpoint-free family bound ablation patch spec")
    print(f"classification={spec['interpretation']['classification']}")
    print(f"action={spec['recommendation']['action']}")
    if not args.no_write:
        paths = write_family_bound_ablation_patch_spec(
            spec,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"spec_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"spec_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft a no-source-mutation patch spec for family-bound ablation/instrumentation."
    )
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_family_bound_ablation_patch_spec(*, comparison_path: Path) -> dict[str, Any]:
    comparison_path = Path(comparison_path)
    comparison = _load_json(comparison_path)
    interpretation = _mapping(comparison.get("interpretation"))
    recommendation = _mapping(comparison.get("recommendation"))
    ready = (
        interpretation.get("classification")
        == "formulation_switch_not_material_for_no_solve_model_size"
        and recommendation.get("action") == "prepare_default_off_family_bound_ablation_patch_spec"
    )
    return {
        "schema": "phase3b-checkpoint-free-family-bound-ablation-patch-spec/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "spec_kind": "default_off_source_patch_spec_no_mutation",
        "comparison_path": str(comparison_path),
        "fresh_solver_run_started_by_builder": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "evidence": {
            "comparison_classification": interpretation.get("classification"),
            "comparison_action": recommendation.get("action"),
            "proto_shape_identical": _mapping(comparison.get("evidence")).get(
                "proto_shape_identical"
            ),
            "deltas_enforced_minus_big_m": _mapping(comparison.get("evidence")).get(
                "deltas_enforced_minus_big_m"
            ),
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
                "the safe existing formulation switch did not reduce no-solve model size; a source patch would touch proof-adjacent model construction and needs explicit authorization"
                if ready
                else "comparison evidence does not justify a patch spec"
            ),
        },
        "patch_spec": _patch_spec() if ready else {},
        "validation_plan": _validation_plan() if ready else [],
        "recommendation": {
            "action": (
                "prepare_no_source_candidate_shape_inventory_comparison"
                if ready
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "continue with no-source no-solve candidate-shape inventory comparison; source mutation remains blocked unless explicitly authorized"
                if ready
                else "review comparison before proceeding"
            ),
            "blocked_actions": [
                "do_not_mutate_src_models_without_explicit_authorization",
                "do_not_run_solver",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
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


def write_family_bound_ablation_patch_spec(spec: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_spec_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "family_bound_ablation_patch_spec.json"
    md_path = output_dir / "family_bound_ablation_patch_spec.md"
    json_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_family_bound_ablation_patch_spec_markdown(spec), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_family_bound_ablation_patch_spec_markdown(spec: Mapping[str, Any]) -> str:
    interpretation = _mapping(spec.get("interpretation"))
    recommendation = _mapping(spec.get("recommendation"))
    patch = _mapping(spec.get("patch_spec"))
    lines = [
        "# Phase3B Family-Bound Ablation Patch Spec",
        "",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Proposed Patch",
        "",
        f"- Target file: `{patch.get('target_file')}`",
        f"- New env var: `{patch.get('env_var')}`",
        f"- Default behavior: `{patch.get('default_behavior')}`",
        f"- Diagnostic behavior: `{patch.get('diagnostic_behavior')}`",
        "",
        "## Validation Plan",
        "",
    ]
    for item in list(spec.get("validation_plan", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('check')}")
    lines.extend(
        [
            "",
            "This is a patch specification only. It does not authorize source mutation, proof promotion, canonical checkpoints, or production-default changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen",
        "env_var": "EXACT_GHOST_CONDITIONED_FAMILY_BOUNDS_ENABLED",
        "default_behavior": "enabled; current certified_exact behavior is unchanged when the env var is unset",
        "diagnostic_behavior": (
            "when explicitly set to 0/false/off for local no-solve experiments, skip adding ghost-conditioned family upper-bound constraints while still publishing build_stats showing skipped=true"
        ),
        "instrumentation": [
            "time family-bound preprocessing separately from Add() calls",
            "record candidate anchor count, family_reduction_anchor_count, and constraints skipped/added",
            "record whether any placements were disabled by the screen",
        ],
        "non_goals": [
            "do not change production defaults",
            "do not connect diagnostic ablation output to proof semantics",
            "do not write canonical checkpoints",
            "do not alter candidate ordering or scheduler integration",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "default_behavior_regression",
            "check": "with env unset, existing tests for ghost-conditioned family upper bounds continue to pass and build_stats stay compatible",
        },
        {
            "id": "diagnostic_env_unit_test",
            "check": "with env disabled in a small fixture, family-bound constraints are skipped and stats record the skip without solver execution",
        },
        {
            "id": "no_solve_inventory_ablation",
            "check": "run exactly one 42x32 no-solve inventory with the env disabled and compare proto/build_stats against big_m/enforced inventories",
        },
        {
            "id": "sensitive_path_guard",
            "check": "confirm data/checkpoints, final solution, blueprint, certified manifest, preflight, viewer, release, and frontdoor fingerprints are unchanged",
        },
    ]


def _assert_spec_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "28_family_bound_ablation_patch_spec" not in normalized:
        raise ValueError(f"Refusing to write outside family bound patch spec namespace: {path}")


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

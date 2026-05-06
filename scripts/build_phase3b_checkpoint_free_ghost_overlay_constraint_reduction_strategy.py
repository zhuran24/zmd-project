from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_REVIEW = (
    ARTIFACT_ROOT
    / "25_master_proto_inventory_review"
    / "master_proto_inventory_review.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "26_ghost_overlay_constraint_reduction_strategy"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_ghost_overlay_constraint_reduction_strategy(
        review_path=_resolve_path(PROJECT_ROOT, args.review),
    )
    print("phase3b checkpoint-free ghost overlay constraint reduction strategy")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_ghost_overlay_constraint_reduction_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local no-solve strategy for reducing 42x32 ghost-overlay model cost."
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_ghost_overlay_constraint_reduction_strategy(*, review_path: Path) -> dict[str, Any]:
    review_path = Path(review_path)
    review = _load_json(review_path)
    source_inventory_path = Path(str(review.get("source_inventory_path") or ""))
    inventory = _load_json(source_inventory_path) if source_inventory_path.exists() else {}
    evidence = _mapping(review.get("evidence"))
    proto = _mapping(evidence.get("proto"))
    timing = _mapping(evidence.get("timing_hotspots"))
    overlay_delta = _mapping(evidence.get("overlay_delta"))
    build_stats = _mapping(_mapping(inventory.get("inventory")).get("build_stats_summary"))
    gvi = _mapping(build_stats.get("global_valid_inequalities"))
    family = _mapping(gvi.get("ghost_aware_via_pole_feasibility"))
    signature = _mapping(gvi.get("signature_bucket_capacity_bounds"))
    residual = _mapping(gvi.get("residual_signature_bucket_capacity_bounds"))
    family_constraints = int(family.get("conditioned_family_upper_bound_constraints") or 0)
    overlay_constraints_added = int(overlay_delta.get("overlay_constraints_added") or 0)
    classification = _classification(review, family_constraints, overlay_constraints_added)
    return {
        "schema": "phase3b-checkpoint-free-ghost-overlay-constraint-reduction-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strategy_kind": "local_no_solve_ghost_overlay_constraint_reduction_strategy",
        "review_path": str(review_path),
        "source_inventory_path": str(source_inventory_path) if source_inventory_path else None,
        "target": review.get("target"),
        "fresh_solver_run_started_by_builder": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "evidence": {
            "review_classification": _mapping(review.get("interpretation")).get("classification"),
            "proto_constraints_by_type": proto.get("constraints_by_type"),
            "linear_constraint_dominance": _mapping(review.get("interpretation")).get(
                "linear_constraint_dominance"
            ),
            "overlay_constraints_added": overlay_constraints_added,
            "ghost_constraint_seconds": timing.get("ghost_constraint_seconds"),
            "ghost_constraint_fraction_of_model_build": timing.get(
                "ghost_constraint_fraction_of_model_build"
            ),
            "ghost_aware_via_pole_feasibility": {
                "conditioned_family_bound_formulation": family.get(
                    "conditioned_family_bound_formulation"
                ),
                "conditioned_family_upper_bound_constraints": family_constraints,
                "constraints_share_of_overlay_delta": _ratio(
                    family_constraints,
                    overlay_constraints_added,
                ),
                "disabled_placements": family.get("disabled_placements"),
                "surviving_placements": family.get("surviving_placements"),
                "family_reduction_anchor_count": family.get("family_reduction_anchor_count"),
                "template_fail_counts": family.get("template_fail_counts"),
            },
            "signature_bucket_capacity_bounds": {
                "ghost_conditioned_mandatory_bucket_constraints": signature.get(
                    "ghost_conditioned_mandatory_bucket_constraints"
                ),
                "ghost_conditioned_required_optional_bucket_constraints": signature.get(
                    "ghost_conditioned_required_optional_bucket_constraints"
                ),
                "ghost_signature_reduction_anchor_count": signature.get(
                    "ghost_signature_reduction_anchor_count"
                ),
            },
            "residual_signature_bucket_capacity_bounds": {
                "ghost_conditioned_residual_bucket_constraints": residual.get(
                    "ghost_conditioned_residual_bucket_constraints"
                ),
                "ghost_residual_signature_reduction_anchor_count": residual.get(
                    "ghost_residual_signature_reduction_anchor_count"
                ),
            },
        },
        "interpretation": {
            "classification": classification,
            "primary_hotspot": (
                "ghost_conditioned_family_upper_bound_constraints"
                if classification == "family_bound_overlay_dominates"
                else "manual_review_required"
            ),
            "existing_safe_knob_available": True,
            "existing_safe_knob": {
                "env_var": "EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION",
                "baseline_value": family.get("conditioned_family_bound_formulation") or "big_m",
                "first_variant_value": "enforced",
                "scope": "no_solve_inventory_first",
            },
            "disable_or_skip_family_bounds_requires_source_change": True,
        },
        "candidate_actions": _candidate_actions(classification),
        "recommendation": _recommendation(classification),
        "safety": {
            "strategy_only": True,
            "next_step_must_be_no_solve": True,
            "builder_executes_solver": False,
            "builder_constructs_model": False,
            "proof_source": False,
            "checkpoint_written": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_ghost_overlay_constraint_reduction_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ghost_overlay_constraint_reduction_strategy.json"
    md_path = output_dir / "ghost_overlay_constraint_reduction_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_ghost_overlay_constraint_reduction_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_ghost_overlay_constraint_reduction_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    evidence = _mapping(strategy.get("evidence"))
    interpretation = _mapping(strategy.get("interpretation"))
    recommendation = _mapping(strategy.get("recommendation"))
    family = _mapping(evidence.get("ghost_aware_via_pole_feasibility"))
    lines = [
        "# Phase3B Ghost Overlay Constraint Reduction Strategy",
        "",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Hotspot Evidence",
        "",
        f"- Ghost constraint seconds: `{evidence.get('ghost_constraint_seconds')}`",
        f"- Ghost fraction of model build: `{evidence.get('ghost_constraint_fraction_of_model_build')}`",
        f"- Overlay constraints added: `{evidence.get('overlay_constraints_added')}`",
        f"- Family bound constraints: `{family.get('conditioned_family_upper_bound_constraints')}`",
        f"- Family bound share of overlay delta: `{family.get('constraints_share_of_overlay_delta')}`",
        f"- Disabled placements: `{family.get('disabled_placements')}`",
        f"- Family reduction anchors: `{family.get('family_reduction_anchor_count')}`",
        "",
        "## Candidate Actions",
        "",
    ]
    for item in list(strategy.get("candidate_actions", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('purpose')}")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            str(recommendation.get("next_engineering_step")),
            "",
            "This strategy is diagnostic and local only. It does not authorize proof promotion, canonical checkpoints, production-default changes, or source mutation.",
            "",
        ]
    )
    return "\n".join(lines)


def _classification(
    review: Mapping[str, Any],
    family_constraints: int,
    overlay_constraints_added: int,
) -> str:
    if _mapping(review.get("interpretation")).get("classification") != "ghost_overlay_constraint_build_dominates":
        return "manual_review_required"
    if overlay_constraints_added <= 0:
        return "manual_review_required"
    if family_constraints / overlay_constraints_added >= 0.5:
        return "family_bound_overlay_dominates"
    return "ghost_overlay_multi_source_hotspot"


def _candidate_actions(classification: str) -> list[dict[str, Any]]:
    if classification != "family_bound_overlay_dominates":
        return []
    return [
        {
            "id": "no_solve_enforced_family_bound_formulation_probe",
            "purpose": (
                "Use the existing env knob to compare enforced literals against current big-M family upper-bound constraints without calling the solver."
            ),
            "env": {"EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION": "enforced"},
            "command_template": (
                "python scripts/build_phase3b_checkpoint_free_master_proto_inventory.py "
                "--execute-no-solve --run-id local_hotspot_42x32_master_proto_inventory_enforced_001"
            ),
            "allowed": True,
            "solver_allowed": False,
            "source_mutation_allowed": False,
        },
        {
            "id": "manifest_only_family_bound_disable_patch_spec",
            "purpose": (
                "Draft a default-off diagnostic patch spec only if the enforced no-solve probe still shows excessive model build cost."
            ),
            "allowed": False,
            "blocked_until": "enforced_no_solve_probe_reviewed",
            "solver_allowed": False,
            "source_mutation_allowed": False,
        },
        {
            "id": "search_guidance_rebuild_scale_followup",
            "purpose": (
                "Separately inspect 6k rebuilt decision strategies and multi-million optional literal lists after family-bound formulation is understood."
            ),
            "allowed": False,
            "blocked_until": "family_bound_overlay_path_classified",
            "solver_allowed": False,
            "source_mutation_allowed": False,
        },
    ]


def _recommendation(classification: str) -> dict[str, Any]:
    if classification == "family_bound_overlay_dominates":
        return {
            "action": "run_no_solve_enforced_family_bound_formulation_probe",
            "next_engineering_step": (
                "run one checkpoint-free no-solve 42x32 inventory with EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION=enforced, then compare against the big_m inventory"
            ),
            "blocked_actions": [
                "do_not_run_solver",
                "do_not_write_canonical_checkpoints",
                "do_not_mutate_proof_source",
                "do_not_disable_family_bounds_without_a_patch_spec",
                "do_not_extend_42x32_runtime",
            ],
        }
    return {
        "action": "hold_for_manual_ghost_overlay_review",
        "next_engineering_step": "review ghost overlay inventory before selecting any no-solve variant",
        "blocked_actions": ["do_not_run_solver", "do_not_write_canonical_checkpoints"],
    }


def _ratio(numerator: Any, denominator: Any) -> float | None:
    try:
        num = float(numerator)
        den = float(denominator)
    except (TypeError, ValueError):
        return None
    if den == 0.0:
        return None
    return num / den


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "26_ghost_overlay_constraint_reduction_strategy" not in normalized:
        raise ValueError(f"Refusing to write outside ghost overlay strategy namespace: {path}")


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

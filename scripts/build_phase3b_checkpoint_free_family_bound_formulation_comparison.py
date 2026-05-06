from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_BIG_M = (
    ARTIFACT_ROOT
    / "24_master_proto_inventory"
    / "local_hotspot_42x32_master_proto_inventory_exec_002"
    / "master_proto_inventory.json"
)
DEFAULT_ENFORCED = (
    ARTIFACT_ROOT
    / "24_master_proto_inventory"
    / "local_hotspot_42x32_master_proto_inventory_enforced_001"
    / "master_proto_inventory.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "27_ghost_overlay_family_bound_formulation_comparison"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    comparison = build_family_bound_formulation_comparison(
        big_m_inventory_path=_resolve_path(PROJECT_ROOT, args.big_m_inventory),
        enforced_inventory_path=_resolve_path(PROJECT_ROOT, args.enforced_inventory),
    )
    print("phase3b checkpoint-free family bound formulation comparison")
    print(f"classification={comparison['interpretation']['classification']}")
    print(f"action={comparison['recommendation']['action']}")
    if not args.no_write:
        paths = write_family_bound_formulation_comparison(
            comparison,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"comparison_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"comparison_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare big_m vs enforced ghost-conditioned family bound no-solve inventories."
    )
    parser.add_argument("--big-m-inventory", type=Path, default=DEFAULT_BIG_M)
    parser.add_argument("--enforced-inventory", type=Path, default=DEFAULT_ENFORCED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_family_bound_formulation_comparison(
    *,
    big_m_inventory_path: Path,
    enforced_inventory_path: Path,
) -> dict[str, Any]:
    big_m = _load_json(big_m_inventory_path)
    enforced = _load_json(enforced_inventory_path)
    big_metrics = _metrics(big_m)
    enforced_metrics = _metrics(enforced)
    deltas = {
        key: _delta(enforced_metrics.get(key), big_metrics.get(key))
        for key in [
            "elapsed_seconds",
            "model_build_seconds",
            "ghost_constraint_seconds",
            "variable_count",
            "constraint_count",
            "conditioned_family_upper_bound_constraints",
            "family_reduction_anchor_count",
            "disabled_placements",
        ]
    }
    same_shape = (
        big_metrics.get("variable_count") == enforced_metrics.get("variable_count")
        and big_metrics.get("constraint_count") == enforced_metrics.get("constraint_count")
        and big_metrics.get("constraints_by_type") == enforced_metrics.get("constraints_by_type")
    )
    clean = (
        _mapping(big_m.get("sensitive_path_comparison")).get("changed") is False
        and _mapping(enforced.get("sensitive_path_comparison")).get("changed") is False
    )
    classification = _classification(
        same_shape=same_shape,
        clean=clean,
        ghost_seconds_delta=float(deltas["ghost_constraint_seconds"] or 0.0),
    )
    return {
        "schema": "phase3b-checkpoint-free-family-bound-formulation-comparison/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "comparison_kind": "local_no_solve_big_m_vs_enforced_family_bound_formulation",
        "big_m_inventory_path": str(big_m_inventory_path),
        "enforced_inventory_path": str(enforced_inventory_path),
        "fresh_solver_run_started_by_builder": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "target": big_m.get("target"),
        "evidence": {
            "big_m": big_metrics,
            "enforced": enforced_metrics,
            "deltas_enforced_minus_big_m": deltas,
            "sensitive_paths_clean": clean,
            "proto_shape_identical": same_shape,
        },
        "interpretation": {
            "classification": classification,
            "formulation_switch_material_for_no_solve_size": classification
            == "formulation_switch_material",
            "observed_effect": (
                "enforced keeps the same proto size and only changes no-solve build time at noise scale"
                if classification == "formulation_switch_not_material_for_no_solve_model_size"
                else "manual review required"
            ),
        },
        "recommendation": _recommendation(classification),
        "safety": {
            "comparison_only": True,
            "builder_executes_solver": False,
            "proof_source": False,
            "checkpoint_written": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_family_bound_formulation_comparison(
    comparison: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_comparison_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "family_bound_formulation_comparison.json"
    md_path = output_dir / "family_bound_formulation_comparison.md"
    json_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_family_bound_formulation_comparison_markdown(comparison), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_family_bound_formulation_comparison_markdown(comparison: Mapping[str, Any]) -> str:
    evidence = _mapping(comparison.get("evidence"))
    interpretation = _mapping(comparison.get("interpretation"))
    recommendation = _mapping(comparison.get("recommendation"))
    deltas = _mapping(evidence.get("deltas_enforced_minus_big_m"))
    lines = [
        "# Phase3B Family-Bound Formulation Comparison",
        "",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Delta: enforced minus big_m",
        "",
        f"- Model build seconds: `{deltas.get('model_build_seconds')}`",
        f"- Ghost constraint seconds: `{deltas.get('ghost_constraint_seconds')}`",
        f"- Variables: `{deltas.get('variable_count')}`",
        f"- Constraints: `{deltas.get('constraint_count')}`",
        f"- Family-bound constraints: `{deltas.get('conditioned_family_upper_bound_constraints')}`",
        "",
        "## Next Step",
        "",
        str(recommendation.get("next_engineering_step")),
        "",
        "This comparison is local, no-solve, and diagnostic only. It does not authorize source mutation, proof promotion, checkpoint writes, or production-default changes.",
        "",
    ]
    return "\n".join(lines)


def _metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    inventory = _mapping(payload.get("inventory"))
    proto = _mapping(inventory.get("proto"))
    build_stats = _mapping(inventory.get("build_stats_summary"))
    core = _mapping(build_stats.get("exact_core_reuse"))
    family = _mapping(
        _mapping(build_stats.get("global_valid_inequalities")).get(
            "ghost_aware_via_pole_feasibility"
        )
    )
    return {
        "run_id": payload.get("run_id"),
        "status": payload.get("status"),
        "execute_no_solve": payload.get("execute_no_solve"),
        "sensitive_path_changed": _mapping(payload.get("sensitive_path_comparison")).get(
            "changed"
        ),
        "formulation": family.get("conditioned_family_bound_formulation"),
        "elapsed_seconds": _number(payload.get("elapsed_seconds")),
        "model_build_seconds": _number(inventory.get("model_build_seconds")),
        "ghost_constraint_seconds": _number(core.get("ghost_constraint_seconds")),
        "variable_count": int(proto.get("variable_count") or 0),
        "constraint_count": int(proto.get("constraint_count") or 0),
        "constraints_by_type": proto.get("constraints_by_type"),
        "conditioned_family_upper_bound_constraints": int(
            family.get("conditioned_family_upper_bound_constraints") or 0
        ),
        "family_reduction_anchor_count": int(family.get("family_reduction_anchor_count") or 0),
        "disabled_placements": int(family.get("disabled_placements") or 0),
    }


def _classification(*, same_shape: bool, clean: bool, ghost_seconds_delta: float) -> str:
    if not clean:
        return "disqualified_sensitive_path_mutation"
    if same_shape and abs(ghost_seconds_delta) < 2.0:
        return "formulation_switch_not_material_for_no_solve_model_size"
    if not same_shape or abs(ghost_seconds_delta) >= 2.0:
        return "formulation_switch_material"
    return "manual_review_required"


def _recommendation(classification: str) -> dict[str, Any]:
    if classification == "formulation_switch_not_material_for_no_solve_model_size":
        return {
            "action": "prepare_default_off_family_bound_ablation_patch_spec",
            "next_engineering_step": (
                "draft a source-level default-off diagnostic patch spec for family-bound ablation/instrumentation; do not mutate proof source until explicitly authorized"
            ),
            "blocked_actions": [
                "do_not_run_solver",
                "do_not_write_canonical_checkpoints",
                "do_not_mutate_proof_source_without_explicit_authorization",
                "do_not_extend_42x32_runtime",
            ],
        }
    return {
        "action": "hold_for_family_bound_comparison_review",
        "next_engineering_step": "review no-solve formulation comparison before proceeding",
        "blocked_actions": ["do_not_run_solver", "do_not_write_canonical_checkpoints"],
    }


def _delta(left: Any, right: Any) -> float | int | None:
    if left is None or right is None:
        return None
    if isinstance(left, int) and isinstance(right, int):
        return int(left) - int(right)
    try:
        return float(left) - float(right)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _assert_comparison_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "27_ghost_overlay_family_bound_formulation_comparison" not in normalized:
        raise ValueError(f"Refusing to write outside family bound comparison namespace: {path}")


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

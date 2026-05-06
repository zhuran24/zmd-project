from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_INVENTORY_DIR = ARTIFACT_ROOT / "24_master_proto_inventory"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "25_master_proto_inventory_review"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    inventory_path = (
        _resolve_path(PROJECT_ROOT, args.inventory)
        if args.inventory
        else find_latest_completed_inventory(DEFAULT_INVENTORY_DIR)
    )
    review = build_master_proto_inventory_review(inventory_path=inventory_path)
    print("phase3b checkpoint-free master proto inventory review")
    print(f"classification={review['interpretation']['classification']}")
    print(f"action={review['recommendation']['action']}")
    if not args.no_write:
        paths = write_master_proto_inventory_review(
            review,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"review_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"review_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a no-solve 42x32 master proto/build_stats inventory."
    )
    parser.add_argument("--inventory", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def find_latest_completed_inventory(inventory_dir: Path) -> Path:
    candidates = sorted(Path(inventory_dir).glob("*/master_proto_inventory.json"))
    completed: list[Path] = []
    for path in candidates:
        try:
            payload = _load_json(path)
        except Exception:
            continue
        if payload.get("status") == "completed" and payload.get("execute_no_solve") is True:
            completed.append(path)
    if not completed:
        raise FileNotFoundError(f"No completed no-solve inventory found under {inventory_dir}")
    return max(completed, key=lambda path: path.stat().st_mtime)


def build_master_proto_inventory_review(*, inventory_path: Path) -> dict[str, Any]:
    inventory_path = Path(inventory_path)
    payload = _load_json(inventory_path)
    inventory = _mapping(payload.get("inventory"))
    proto = _mapping(inventory.get("proto"))
    build_stats = _mapping(inventory.get("build_stats_summary"))
    core = _mapping(build_stats.get("exact_core_reuse"))
    ghost = _mapping(build_stats.get("ghost_rect"))
    guidance = _mapping(build_stats.get("search_guidance"))
    comparison = _mapping(payload.get("sensitive_path_comparison"))
    constraint_counts = _int_mapping(proto.get("constraints_by_type"))
    total_constraints = int(proto.get("constraint_count") or 0)
    core_constraints = int(core.get("core_proto_constraints") or 0)
    core_variables = int(core.get("core_proto_variables") or 0)
    variable_count = int(proto.get("variable_count") or 0)
    overlay_constraints_added = total_constraints - core_constraints if core_constraints else None
    overlay_variables_added = variable_count - core_variables if core_variables else None
    classification = _classification(
        payload=payload,
        comparison=comparison,
        constraint_counts=constraint_counts,
        ghost_constraint_seconds=_float(core.get("ghost_constraint_seconds")),
    )
    return {
        "schema": "phase3b-checkpoint-free-master-proto-inventory-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "review_kind": "local_no_solve_inventory_review",
        "source_inventory_path": str(inventory_path),
        "source_run_id": payload.get("run_id"),
        "target": payload.get("target"),
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
            "inventory_status": payload.get("status"),
            "execute_no_solve": payload.get("execute_no_solve"),
            "sensitive_paths_clean": comparison.get("changed") is False,
            "elapsed_seconds": _float(payload.get("elapsed_seconds")),
            "session_core_build_seconds": _float(inventory.get("session_core_build_seconds")),
            "model_build_seconds": _float(inventory.get("model_build_seconds")),
            "proto": {
                "variable_count": variable_count,
                "boolean_variable_count": int(proto.get("boolean_variable_count") or 0),
                "constraint_count": total_constraints,
                "constraints_by_type": constraint_counts,
                "top_constraint_types": _top_counts(constraint_counts, limit=8),
            },
            "overlay_delta": {
                "core_proto_variables": core_variables,
                "core_proto_constraints": core_constraints,
                "overlay_variables_added": overlay_variables_added,
                "overlay_constraints_added": overlay_constraints_added,
                "overlay_constraint_growth_ratio": _ratio(overlay_constraints_added, core_constraints),
            },
            "timing_hotspots": {
                "overlay_build_seconds": _float(core.get("overlay_build_seconds")),
                "ghost_constraint_seconds": _float(core.get("ghost_constraint_seconds")),
                "ghost_constraint_fraction_of_model_build": _ratio(
                    _float(core.get("ghost_constraint_seconds")),
                    _float(inventory.get("model_build_seconds")),
                ),
            },
            "ghost_rect": {
                "enabled": ghost.get("enabled"),
                "placements": ghost.get("placements"),
                "size": ghost.get("size"),
                "signature_tightening_anchor_reductions": ghost.get(
                    "signature_tightening_anchor_reductions"
                ),
            },
            "search_guidance_scale": {
                "mandatory_literals": guidance.get("mandatory_literals"),
                "ghost_literals": guidance.get("ghost_literals"),
                "residual_optional_literals": guidance.get("residual_optional_literals"),
                "optional_literals": guidance.get("optional_literals"),
                "cleared_existing_search_strategy_count": core.get(
                    "cleared_existing_search_strategy_count"
                ),
                "rebuilt_search_strategy_count": core.get("rebuilt_search_strategy_count"),
            },
        },
        "interpretation": {
            "classification": classification,
            "constraint_type_classification_usable": bool(
                constraint_counts and set(constraint_counts) != {"unknown"}
            ),
            "dominant_constraint_type": _top_counts(constraint_counts, limit=1)[0]["type"]
            if constraint_counts
            else None,
            "ghost_overlay_build_is_hotspot": _float(core.get("ghost_constraint_seconds")) >= 30.0,
            "linear_constraint_dominance": _ratio(constraint_counts.get("linear", 0), total_constraints),
            "search_guidance_literal_scale_is_large": _search_guidance_scale_large(guidance),
        },
        "recommendation": _recommendation(classification),
        "safety": {
            "no_solve_review_only": True,
            "builder_executes_solver": False,
            "builder_constructs_model": False,
            "proof_source": False,
            "checkpoint_written": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_master_proto_inventory_review(review: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_review_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "master_proto_inventory_review.json"
    md_path = output_dir / "master_proto_inventory_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_master_proto_inventory_review_markdown(review), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_master_proto_inventory_review_markdown(review: Mapping[str, Any]) -> str:
    evidence = _mapping(review.get("evidence"))
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    proto = _mapping(evidence.get("proto"))
    delta = _mapping(evidence.get("overlay_delta"))
    timings = _mapping(evidence.get("timing_hotspots"))
    lines = [
        "# Phase3B Master Proto Inventory Review",
        "",
        f"- Source run id: `{review.get('source_run_id')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Model Size",
        "",
        f"- Variables: `{proto.get('variable_count')}`",
        f"- Boolean variables: `{proto.get('boolean_variable_count')}`",
        f"- Constraints: `{proto.get('constraint_count')}`",
        f"- Overlay variables added: `{delta.get('overlay_variables_added')}`",
        f"- Overlay constraints added: `{delta.get('overlay_constraints_added')}`",
        "",
        "## Constraint Types",
        "",
    ]
    for item in list(proto.get("top_constraint_types", []) or []):
        lines.append(f"- `{item.get('type')}`: `{item.get('count')}`")
    lines.extend(
        [
            "",
            "## Hotspots",
            "",
            f"- Model build seconds: `{evidence.get('model_build_seconds')}`",
            f"- Ghost constraint seconds: `{timings.get('ghost_constraint_seconds')}`",
            f"- Ghost constraint fraction of model build: `{timings.get('ghost_constraint_fraction_of_model_build')}`",
            "",
            "## Next Step",
            "",
            str(recommendation.get("next_engineering_step")),
            "",
            "This review is local, no-solve, and diagnostic only. It does not authorize proof promotion, checkpoint writes, production-default changes, or more runtime.",
            "",
        ]
    )
    return "\n".join(lines)


def _classification(
    *,
    payload: Mapping[str, Any],
    comparison: Mapping[str, Any],
    constraint_counts: Mapping[str, int],
    ghost_constraint_seconds: float,
) -> str:
    if payload.get("status") != "completed" or payload.get("execute_no_solve") is not True:
        return "inventory_incomplete"
    if comparison.get("changed") is not False:
        return "disqualified_sensitive_path_mutation"
    if not constraint_counts or set(constraint_counts) == {"unknown"}:
        return "constraint_classification_unusable"
    if ghost_constraint_seconds >= 30.0:
        return "ghost_overlay_constraint_build_dominates"
    return "inventory_review_ready_for_candidate_shape_comparison"


def _recommendation(classification: str) -> dict[str, Any]:
    if classification == "ghost_overlay_constraint_build_dominates":
        return {
            "action": "prepare_ghost_overlay_constraint_reduction_strategy",
            "next_engineering_step": (
                "inspect ghost-overlay linear/interval/element constraint generation and search-guidance rebuild cost before running more 42x32 runtime"
            ),
            "blocked_actions": _blocked_actions(),
        }
    if classification == "inventory_review_ready_for_candidate_shape_comparison":
        return {
            "action": "prepare_candidate_shape_inventory_comparison",
            "next_engineering_step": (
                "compare no-solve proto/build_stats inventories across smaller candidate shapes before choosing another runtime test"
            ),
            "blocked_actions": _blocked_actions(),
        }
    return {
        "action": "hold_for_inventory_review_repair",
        "next_engineering_step": "repair or rerun the no-solve inventory before making optimization decisions",
        "blocked_actions": _blocked_actions(),
    }


def _blocked_actions() -> list[str]:
    return [
        "do_not_run_more_parameter_only_42x32_variants",
        "do_not_extend_42x32_duration",
        "do_not_run_full_wave_matrix",
        "do_not_promote_local_results_to_proof",
        "do_not_write_canonical_checkpoints",
    ]


def _top_counts(counts: Mapping[str, int], *, limit: int) -> list[dict[str, Any]]:
    return [
        {"type": key, "count": int(value)}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _search_guidance_scale_large(guidance: Mapping[str, Any]) -> bool:
    values = [guidance.get("mandatory_literals"), guidance.get("ghost_literals")]
    for mapping_key in ("residual_optional_literals", "optional_literals"):
        value = guidance.get(mapping_key)
        if isinstance(value, Mapping):
            values.extend(value.values())
    return any(isinstance(value, int | float) and value >= 1_000_000 for value in values)


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): int(count) for key, count in value.items()}


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: Any, denominator: Any) -> float | None:
    num = _float(numerator)
    den = _float(denominator)
    if den == 0.0:
        return None
    return num / den


def _assert_review_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "25_master_proto_inventory_review" not in normalized:
        raise ValueError(f"Refusing to write outside master proto inventory review namespace: {path}")


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

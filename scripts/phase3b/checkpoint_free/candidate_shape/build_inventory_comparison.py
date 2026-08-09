from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase3b.checkpoint_free.master.build_proto_inventory import (  # noqa: E402
    _model_inventory,
)
from src.models.master_model import MasterPlacementModel  # noqa: E402
from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.benders_loop import (  # noqa: E402
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    create_exact_search_session,
    evaluate_exact_candidate_pre_master_precheck,
)
from src.search.exact_campaign import atomic_write_json, now_iso  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_PATCH_SPEC = (
    ARTIFACT_ROOT
    / "28_family_bound_ablation_patch_spec"
    / "family_bound_ablation_patch_spec.json"
)
DEFAULT_BASELINE_INVENTORY = (
    ARTIFACT_ROOT
    / "24_master_proto_inventory"
    / "local_hotspot_42x32_master_proto_inventory_exec_002"
    / "master_proto_inventory.json"
)
DEFAULT_REDUCED_FRONTIER_PLAN = (
    ARTIFACT_ROOT
    / "08_checkpoint_free_evaluator"
    / "B0_prod_4x4_600s_reduced_frontier_no_hotspots_eval_001"
    / "run_plan.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "29_candidate_shape_inventory_comparison"
DEFAULT_RUN_ID = "candidate_shape_inventory_comparison_001"

SessionFactory = Callable[..., Any]
PrecheckFactory = Callable[..., Mapping[str, Any]]
ModelFactory = Callable[..., Any]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    comparison = build_candidate_shape_inventory_comparison(
        project_root=PROJECT_ROOT,
        patch_spec_path=_resolve_path(PROJECT_ROOT, args.patch_spec),
        baseline_inventory_path=_resolve_path(PROJECT_ROOT, args.baseline_inventory),
        reduced_frontier_plan_path=_resolve_path(PROJECT_ROOT, args.reduced_frontier_plan),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        execute_no_solve=bool(args.execute_no_solve),
    )
    print("phase3b checkpoint-free candidate shape inventory comparison")
    print(f"status={comparison['status']}")
    print(f"execute_no_solve={comparison['execute_no_solve']}")
    print(f"action={comparison['recommendation']['action']}")
    print(f"artifact_dir={_display_path(PROJECT_ROOT, Path(comparison['artifact_dir']))}")
    return 0 if comparison["status"] in {"planned_only", "completed"} else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare no-solve ModelProto/build_stats inventories across candidate shapes."
    )
    parser.add_argument("--patch-spec", type=Path, default=DEFAULT_PATCH_SPEC)
    parser.add_argument("--baseline-inventory", type=Path, default=DEFAULT_BASELINE_INVENTORY)
    parser.add_argument("--reduced-frontier-plan", type=Path, default=DEFAULT_REDUCED_FRONTIER_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument(
        "--execute-no-solve",
        action="store_true",
        help="Construct non-baseline candidate overlays without calling CpSolver.Solve.",
    )
    return parser.parse_args(argv)


def build_candidate_shape_inventory_comparison(
    *,
    project_root: Path,
    patch_spec_path: Path,
    baseline_inventory_path: Path,
    reduced_frontier_plan_path: Path,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    execute_no_solve: bool = False,
    session_factory: SessionFactory = create_exact_search_session,
    precheck_factory: PrecheckFactory = evaluate_exact_candidate_pre_master_precheck,
    model_factory: ModelFactory = MasterPlacementModel.from_exact_core,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    patch_spec_path = _resolve_path(project_root, patch_spec_path)
    baseline_inventory_path = _resolve_path(project_root, baseline_inventory_path)
    reduced_frontier_plan_path = _resolve_path(project_root, reduced_frontier_plan_path)
    output_dir = _resolve_path(project_root, output_dir)
    _assert_comparison_namespace(output_dir)
    artifact_dir = output_dir / str(run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    paths = _paths(artifact_dir)
    patch_spec = _load_json(patch_spec_path)
    baseline_payload = _load_json(baseline_inventory_path)
    reduced_plan = _load_json(reduced_frontier_plan_path)
    candidates = _candidate_rows_from_inputs(baseline_payload, reduced_plan)
    plan = _base_payload(
        project_root=project_root,
        artifact_dir=artifact_dir,
        run_id=str(run_id),
        patch_spec_path=patch_spec_path,
        baseline_inventory_path=baseline_inventory_path,
        reduced_frontier_plan_path=reduced_frontier_plan_path,
        execute_no_solve=execute_no_solve,
        patch_spec=patch_spec,
        candidates=candidates,
    )
    atomic_write_json(paths["plan"], plan)
    before = build_sensitive_path_fingerprint(project_root)
    atomic_write_json(paths["sensitive_before"], before)

    rows = [_row_from_existing_inventory(baseline_payload, source="baseline_42x32_inventory")]
    if not execute_no_solve:
        rows.extend(_planned_row(candidate) for candidate in candidates if not candidate["is_baseline"])
        after = build_sensitive_path_fingerprint(project_root)
        comparison = compare_sensitive_path_fingerprints(before, after)
        payload = _final_payload(
            plan,
            status="planned_only",
            rows=rows,
            sensitive_path_comparison=comparison,
            started_at=None,
            elapsed_seconds=0.0,
            error=None,
        )
        atomic_write_json(paths["sensitive_after"], after)
        atomic_write_json(paths["sensitive_comparison"], comparison)
        atomic_write_json(paths["comparison"], payload)
        paths["markdown"].write_text(render_candidate_shape_inventory_comparison_markdown(payload), encoding="utf-8")
        return payload

    started = time.perf_counter()
    started_at = now_iso()
    status = "completed"
    error: str | None = None
    try:
        session = session_factory(
            project_root,
            solve_mode="certified_exact",
            master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        )
        for candidate in candidates:
            if candidate["is_baseline"]:
                continue
            rows.append(
                _execute_candidate_inventory(
                    candidate=candidate,
                    session=session,
                    precheck_factory=precheck_factory,
                    model_factory=model_factory,
                )
            )
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"

    after = build_sensitive_path_fingerprint(project_root)
    comparison = compare_sensitive_path_fingerprints(before, after)
    if comparison.get("changed"):
        status = "disqualified_sensitive_path_mutation"
    payload = _final_payload(
        plan,
        status=status,
        rows=rows,
        sensitive_path_comparison=comparison,
        started_at=started_at,
        elapsed_seconds=float(time.perf_counter() - started),
        error=error,
    )
    atomic_write_json(paths["sensitive_after"], after)
    atomic_write_json(paths["sensitive_comparison"], comparison)
    atomic_write_json(paths["comparison"], payload)
    paths["markdown"].write_text(render_candidate_shape_inventory_comparison_markdown(payload), encoding="utf-8")
    return payload


def render_candidate_shape_inventory_comparison_markdown(payload: Mapping[str, Any]) -> str:
    recommendation = _mapping(payload.get("recommendation"))
    interpretation = _mapping(payload.get("interpretation"))
    lines = [
        "# Phase3B Candidate Shape Inventory Comparison",
        "",
        f"- Run id: `{payload.get('run_id')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Execute no-solve: `{payload.get('execute_no_solve')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "| Candidate | Source | Status | Vars | Constraints | Ghost seconds | Family constraints | vs 42x32 constraints |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in list(payload.get("rows", []) or []):
        lines.append(
            "| {candidate_key} | {source} | {status} | {variables} | {constraints} | {ghost_seconds:.3f} | {family_constraints} | {constraint_ratio:.3f} |".format(
                candidate_key=row.get("candidate_key"),
                source=row.get("source"),
                status=row.get("status"),
                variables=row.get("variable_count") or 0,
                constraints=row.get("constraint_count") or 0,
                ghost_seconds=float(row.get("ghost_constraint_seconds") or 0.0),
                family_constraints=row.get("conditioned_family_upper_bound_constraints") or 0,
                constraint_ratio=float(row.get("constraint_ratio_vs_baseline") or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            str(recommendation.get("next_engineering_step")),
            "",
            "This comparison is local, checkpoint-free, and no-solve only. It must not be used as proof evidence or scheduler input.",
            "",
        ]
    )
    return "\n".join(lines)


def _execute_candidate_inventory(
    *,
    candidate: Mapping[str, Any],
    session: Any,
    precheck_factory: PrecheckFactory,
    model_factory: ModelFactory,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        precheck = precheck_factory(
            ghost_w=int(candidate["w"]),
            ghost_h=int(candidate["h"]),
            exact_session=session,
            master_search_profile=str(
                getattr(session, "master_search_profile", DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE)
            ),
        )
        boundary = dict(
            _mapping(precheck).get(
                "boundary_port_precheck",
                MasterPlacementModel._default_exact_candidate_boundary_port_feasibility_payload(),
            )
        )
        model_started = time.perf_counter()
        model = model_factory(
            getattr(session, "core"),
            ghost_rect=(int(candidate["w"]), int(candidate["h"])),
            master_search_profile=str(
                getattr(session, "master_search_profile", DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE)
            ),
            precomputed_boundary_port_feasibility=boundary,
        )
        inventory = _model_inventory(
            model=model,
            session=session,
            precheck=precheck,
            model_build_seconds=time.perf_counter() - model_started,
        )
        return _row_from_inventory(
            candidate=candidate,
            inventory=inventory,
            status="completed",
            source=str(candidate.get("source")),
            elapsed_seconds=float(time.perf_counter() - started),
            error=None,
        )
    except Exception as exc:
        return {
            **_candidate_identity(candidate),
            "source": str(candidate.get("source")),
            "status": "failed",
            "elapsed_seconds": float(time.perf_counter() - started),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _candidate_rows_from_inputs(
    baseline_payload: Mapping[str, Any],
    reduced_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    baseline_target = _mapping(baseline_payload.get("target"))
    baseline_rect = _mapping(baseline_target.get("ghost_rect"))
    rows.append(
        {
            "candidate_key": str(baseline_target.get("candidate_key") or "42x32"),
            "candidate_tuple": list(baseline_target.get("candidate_tuple", []) or []),
            "w": int(baseline_rect.get("w") or 42),
            "h": int(baseline_rect.get("h") or 32),
            "area": int(baseline_rect.get("area") or 1344),
            "source": "baseline_42x32_inventory",
            "selection_reason": "hotspot_baseline",
            "is_baseline": True,
        }
    )
    seen = {rows[0]["candidate_key"]}
    wave = _mapping(reduced_plan.get("wave"))
    for entry in list(wave.get("entries", []) or []):
        if not isinstance(entry, Mapping):
            continue
        candidate_key = str(entry.get("candidate_key") or "")
        candidate_tuple = list(entry.get("candidate", []) or [])
        if not candidate_key or candidate_key in seen or len(candidate_tuple) < 3:
            continue
        seen.add(candidate_key)
        rows.append(
            {
                "candidate_key": candidate_key,
                "candidate_tuple": candidate_tuple,
                "area": int(candidate_tuple[0]),
                "w": int(candidate_tuple[1]),
                "h": int(candidate_tuple[2]),
                "source": "reduced_frontier_no_hotspots_run_plan",
                "selection_reason": entry.get("selection_reason"),
                "is_baseline": False,
            }
        )
    return rows


def _row_from_existing_inventory(payload: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    target = _mapping(payload.get("target"))
    rect = _mapping(target.get("ghost_rect"))
    return _row_from_inventory(
        candidate={
            "candidate_key": str(target.get("candidate_key") or "42x32"),
            "candidate_tuple": list(target.get("candidate_tuple", []) or []),
            "w": int(rect.get("w") or 0),
            "h": int(rect.get("h") or 0),
            "area": int(rect.get("area") or 0),
        },
        inventory=_mapping(payload.get("inventory")),
        status=str(payload.get("status") or "unknown"),
        source=source,
        elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
        error=payload.get("error"),
    )


def _row_from_inventory(
    *,
    candidate: Mapping[str, Any],
    inventory: Mapping[str, Any],
    status: str,
    source: str,
    elapsed_seconds: float,
    error: Any,
) -> dict[str, Any]:
    proto = _mapping(inventory.get("proto"))
    build_stats = _mapping(inventory.get("build_stats_summary"))
    core = _mapping(build_stats.get("exact_core_reuse"))
    family = _mapping(
        _mapping(build_stats.get("global_valid_inequalities")).get(
            "ghost_aware_via_pole_feasibility"
        )
    )
    return {
        **_candidate_identity(candidate),
        "source": source,
        "status": status,
        "elapsed_seconds": float(elapsed_seconds),
        "error": error,
        "model_build_seconds": _number(inventory.get("model_build_seconds")),
        "session_core_build_seconds": _number(inventory.get("session_core_build_seconds")),
        "ghost_constraint_seconds": _number(core.get("ghost_constraint_seconds")),
        "variable_count": int(proto.get("variable_count") or 0),
        "boolean_variable_count": int(proto.get("boolean_variable_count") or 0),
        "constraint_count": int(proto.get("constraint_count") or 0),
        "constraints_by_type": proto.get("constraints_by_type") or {},
        "conditioned_family_bound_formulation": family.get("conditioned_family_bound_formulation"),
        "conditioned_family_upper_bound_constraints": int(
            family.get("conditioned_family_upper_bound_constraints") or 0
        ),
        "disabled_placements": int(family.get("disabled_placements") or 0),
        "surviving_placements": int(family.get("surviving_placements") or 0),
        "family_reduction_anchor_count": int(family.get("family_reduction_anchor_count") or 0),
    }


def _planned_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_candidate_identity(candidate),
        "source": str(candidate.get("source")),
        "status": "planned_not_executed",
        "selection_reason": candidate.get("selection_reason"),
    }


def _candidate_identity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_key": str(candidate.get("candidate_key") or ""),
        "candidate_tuple": list(candidate.get("candidate_tuple", []) or []),
        "w": int(candidate.get("w") or 0),
        "h": int(candidate.get("h") or 0),
        "area": int(candidate.get("area") or 0),
    }


def _final_payload(
    plan: Mapping[str, Any],
    *,
    status: str,
    rows: list[dict[str, Any]],
    sensitive_path_comparison: Mapping[str, Any],
    started_at: str | None,
    elapsed_seconds: float,
    error: str | None,
) -> dict[str, Any]:
    normalized_rows = _with_baseline_ratios(rows)
    return {
        **dict(plan),
        "status": status,
        "started_at": started_at,
        "finished_at": now_iso(),
        "elapsed_seconds": float(elapsed_seconds),
        "error": error,
        "rows": normalized_rows,
        "interpretation": _interpretation(status, normalized_rows, sensitive_path_comparison),
        "recommendation": _recommendation(status, normalized_rows, sensitive_path_comparison),
        "sensitive_path_comparison": dict(sensitive_path_comparison),
    }


def _with_baseline_ratios(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = next((row for row in rows if row.get("candidate_key") == "42x32"), None)
    baseline_constraints = int(_mapping(baseline).get("constraint_count") or 0)
    baseline_ghost = float(_mapping(baseline).get("ghost_constraint_seconds") or 0.0)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["constraint_ratio_vs_baseline"] = _ratio(item.get("constraint_count"), baseline_constraints)
        item["ghost_seconds_ratio_vs_baseline"] = _ratio(item.get("ghost_constraint_seconds"), baseline_ghost)
        out.append(item)
    return out


def _interpretation(
    status: str,
    rows: Sequence[Mapping[str, Any]],
    sensitive_path_comparison: Mapping[str, Any],
) -> dict[str, Any]:
    completed = [row for row in rows if row.get("status") == "completed"]
    non_baseline_completed = [row for row in completed if row.get("candidate_key") != "42x32"]
    return {
        "classification": (
            "disqualified_sensitive_path_mutation"
            if sensitive_path_comparison.get("changed")
            else "candidate_shape_inventory_comparison_ready"
            if status == "completed" and len(non_baseline_completed) >= 2
            else "candidate_shape_inventory_comparison_planned"
            if status == "planned_only"
            else "manual_review_required"
        ),
        "completed_shape_count": len(completed),
        "non_baseline_completed_shape_count": len(non_baseline_completed),
        "baseline_candidate_key": "42x32",
        "source_mutation_performed": False,
    }


def _recommendation(
    status: str,
    rows: Sequence[Mapping[str, Any]],
    sensitive_path_comparison: Mapping[str, Any],
) -> dict[str, Any]:
    if sensitive_path_comparison.get("changed"):
        return {
            "action": "stop_for_sensitive_path_audit",
            "next_engineering_step": "inspect sensitive path mutation before any further local diagnostic",
            "blocked_actions": _blocked_actions(),
        }
    if status == "completed":
        best = _smallest_non_baseline_shape(rows)
        return {
            "action": "review_no_source_shape_scaling_before_runtime",
            "next_engineering_step": (
                f"review no-solve shape scaling; lowest observed non-baseline constraint ratio is {best.get('candidate_key') if best else 'n/a'} before deciding whether any runtime retry is justified"
            ),
            "lowest_constraint_ratio_candidate": best,
            "blocked_actions": _blocked_actions(),
        }
    return {
        "action": "run_candidate_shape_inventory_comparison_no_solve"
        if status == "planned_only"
        else "hold_for_manual_review",
        "next_engineering_step": "run the same builder with --execute-no-solve to construct reduced-frontier shape inventories without solver execution",
        "blocked_actions": _blocked_actions(),
    }


def _smallest_non_baseline_shape(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidates = [
        row
        for row in rows
        if row.get("candidate_key") != "42x32"
        and row.get("status") == "completed"
        and row.get("constraint_ratio_vs_baseline") is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda row: float(row.get("constraint_ratio_vs_baseline") or 999.0))


def _blocked_actions() -> list[str]:
    return [
        "do_not_run_solver",
        "do_not_write_canonical_checkpoints",
        "do_not_mutate_proof_source",
        "do_not_promote_local_results_to_proof",
        "do_not_change_production_defaults",
    ]


def _base_payload(
    *,
    project_root: Path,
    artifact_dir: Path,
    run_id: str,
    patch_spec_path: Path,
    baseline_inventory_path: Path,
    reduced_frontier_plan_path: Path,
    execute_no_solve: bool,
    patch_spec: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    recommendation = _mapping(patch_spec.get("recommendation"))
    interpretation = _mapping(patch_spec.get("interpretation"))
    if recommendation.get("action") != "prepare_no_source_candidate_shape_inventory_comparison":
        raise ValueError("Patch spec does not authorize no-source candidate-shape inventory comparison")
    if interpretation.get("source_mutation_authorized_by_this_artifact") is not False:
        raise ValueError("Patch spec must keep source mutation unauthorized")
    if patch_spec.get("source_mutation_performed") is not False:
        raise ValueError("Patch spec must be spec-only with no source mutation performed")
    return {
        "schema": "phase3b-checkpoint-free-candidate-shape-inventory-comparison/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "status": "planned_only",
        "execute_no_solve": bool(execute_no_solve),
        "project_root": str(project_root),
        "artifact_dir": str(artifact_dir),
        "patch_spec_path": str(patch_spec_path),
        "baseline_inventory_path": str(baseline_inventory_path),
        "reduced_frontier_plan_path": str(reduced_frontier_plan_path),
        "planned_candidates": [dict(candidate) for candidate in candidates],
        "excluded_hotspot_candidate_keys": ["67x20"],
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "scheduler_integration": False,
        "safety": {
            "builder_may_construct_model": bool(execute_no_solve),
            "builder_must_not_call_cp_solver_solve": True,
            "builder_must_not_write_checkpoints": True,
            "builder_must_not_mutate_src_models": True,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def _paths(artifact_dir: Path) -> dict[str, Path]:
    return {
        "plan": artifact_dir / "candidate_shape_inventory_comparison_plan.json",
        "comparison": artifact_dir / "candidate_shape_inventory_comparison.json",
        "markdown": artifact_dir / "candidate_shape_inventory_comparison.md",
        "sensitive_before": artifact_dir / "sensitive_path_before.json",
        "sensitive_after": artifact_dir / "sensitive_path_after.json",
        "sensitive_comparison": artifact_dir / "sensitive_path_comparison.json",
    }


def _assert_comparison_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "29_candidate_shape_inventory_comparison" not in normalized:
        raise ValueError(f"Refusing to write outside candidate shape comparison namespace: {path}")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: Any, denominator: Any) -> float | None:
    try:
        num = float(numerator)
        den = float(denominator)
    except (TypeError, ValueError):
        return None
    if den == 0.0:
        return None
    return num / den


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

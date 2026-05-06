from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import MasterPlacementModel
from src.runtime.sensitive_path_audit import (
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.benders_loop import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    create_exact_search_session,
    evaluate_exact_candidate_pre_master_precheck,
)
from src.search.exact_campaign import atomic_write_json, now_iso

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_STRATEGY = (
    ARTIFACT_ROOT
    / "23_master_model_size_reduction_strategy"
    / "master_model_size_reduction_strategy.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "24_master_proto_inventory"
DEFAULT_RUN_ID = "local_hotspot_42x32_master_proto_inventory_001"

SessionFactory = Callable[..., Any]
PrecheckFactory = Callable[..., Mapping[str, Any]]
ModelFactory = Callable[..., Any]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    inventory = build_or_run_master_proto_inventory(
        project_root=PROJECT_ROOT,
        strategy_path=_resolve_path(PROJECT_ROOT, args.strategy),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        execute_no_solve=bool(args.execute_no_solve),
    )
    print("phase3b checkpoint-free master proto inventory")
    print(f"status={inventory['status']}")
    print(f"execute_no_solve={inventory['execute_no_solve']}")
    print(f"candidate_key={inventory['target']['candidate_key']}")
    print(f"artifact_dir={_display_path(PROJECT_ROOT, Path(inventory['artifact_dir']))}")
    return 0 if inventory["status"] in {"planned_only", "completed"} else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve 42x32 master ModelProto/build_stats inventory."
    )
    parser.add_argument("--strategy", type=Path, default=DEFAULT_STRATEGY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument(
        "--execute-no-solve",
        action="store_true",
        help="Actually construct the exact master overlay but do not call CpSolver.Solve.",
    )
    return parser.parse_args(argv)


def build_or_run_master_proto_inventory(
    *,
    project_root: Path,
    strategy_path: Path,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    execute_no_solve: bool = False,
    session_factory: SessionFactory = create_exact_search_session,
    precheck_factory: PrecheckFactory = evaluate_exact_candidate_pre_master_precheck,
    model_factory: ModelFactory = MasterPlacementModel.from_exact_core,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    strategy_path = _resolve_path(project_root, strategy_path)
    output_dir = _resolve_path(project_root, output_dir)
    _assert_inventory_namespace(output_dir)
    artifact_dir = output_dir / str(run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    strategy = _load_json(strategy_path)
    target = _target_from_strategy(strategy)
    plan = _base_inventory_payload(
        project_root=project_root,
        strategy_path=strategy_path,
        artifact_dir=artifact_dir,
        run_id=str(run_id),
        target=target,
        execute_no_solve=execute_no_solve,
    )
    paths = _paths(artifact_dir)
    atomic_write_json(paths["plan"], plan)
    before = build_sensitive_path_fingerprint(project_root)
    atomic_write_json(paths["sensitive_before"], before)
    if not execute_no_solve:
        after = build_sensitive_path_fingerprint(project_root)
        comparison = compare_sensitive_path_fingerprints(before, after)
        atomic_write_json(paths["sensitive_after"], after)
        atomic_write_json(paths["sensitive_comparison"], comparison)
        payload = {**plan, "status": "planned_only", "sensitive_path_comparison": comparison}
        atomic_write_json(paths["inventory"], payload)
        paths["markdown"].write_text(render_master_proto_inventory_markdown(payload), encoding="utf-8")
        return payload

    started = time.perf_counter()
    status = "completed"
    error: str | None = None
    inventory: dict[str, Any] = {}
    try:
        session = session_factory(
            project_root,
            solve_mode="certified_exact",
            master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        )
        precheck = precheck_factory(
            ghost_w=int(target["ghost_rect"]["w"]),
            ghost_h=int(target["ghost_rect"]["h"]),
            exact_session=session,
            master_search_profile=str(getattr(session, "master_search_profile", DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE)),
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
            ghost_rect=(int(target["ghost_rect"]["w"]), int(target["ghost_rect"]["h"])),
            master_search_profile=str(getattr(session, "master_search_profile", DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE)),
            precomputed_boundary_port_feasibility=boundary,
        )
        inventory = _model_inventory(
            model=model,
            session=session,
            precheck=precheck,
            model_build_seconds=time.perf_counter() - model_started,
        )
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"

    after = build_sensitive_path_fingerprint(project_root)
    comparison = compare_sensitive_path_fingerprints(before, after)
    atomic_write_json(paths["sensitive_after"], after)
    atomic_write_json(paths["sensitive_comparison"], comparison)
    if comparison.get("changed"):
        status = "disqualified_sensitive_path_mutation"
    payload = {
        **plan,
        "status": status,
        "error": error,
        "finished_at": now_iso(),
        "elapsed_seconds": float(time.perf_counter() - started),
        "inventory": inventory,
        "sensitive_path_comparison": comparison,
    }
    atomic_write_json(paths["inventory"], payload)
    paths["markdown"].write_text(render_master_proto_inventory_markdown(payload), encoding="utf-8")
    return payload


def render_master_proto_inventory_markdown(payload: Mapping[str, Any]) -> str:
    target = _mapping(payload.get("target"))
    inventory = _mapping(payload.get("inventory"))
    proto = _mapping(inventory.get("proto"))
    lines = [
        "# Phase3B Master Proto Inventory",
        "",
        f"- Run id: `{payload.get('run_id')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Execute no-solve: `{payload.get('execute_no_solve')}`",
        f"- Candidate: `{target.get('candidate_key')}`",
        f"- Ghost rect: `{target.get('ghost_rect')}`",
        f"- Variables: `{proto.get('variable_count')}`",
        f"- Constraints: `{proto.get('constraint_count')}`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
    ]
    by_type = _mapping(proto.get("constraints_by_type"))
    if by_type:
        lines.extend(["## Constraint Types", ""])
        for key, value in sorted(by_type.items()):
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    lines.append(
        "This inventory is local and diagnostic only. It must not be used as proof evidence or scheduler input."
    )
    lines.append("")
    return "\n".join(lines)


def _model_inventory(
    *,
    model: Any,
    session: Any,
    precheck: Mapping[str, Any],
    model_build_seconds: float,
) -> dict[str, Any]:
    proto = model.model.Proto()
    build_stats = dict(getattr(model, "build_stats", {}) or {})
    return {
        "model_build_seconds": float(model_build_seconds),
        "session_core_build_seconds": float(getattr(session, "core_build_seconds", 0.0)),
        "master_search_profile": str(getattr(session, "master_search_profile", "")),
        "precheck": _compact_precheck(precheck),
        "proto": _proto_inventory(proto),
        "build_stats_summary": _build_stats_summary(build_stats),
    }


def _proto_inventory(proto: Any) -> dict[str, Any]:
    variables = list(getattr(proto, "variables", []) or [])
    constraints = list(getattr(proto, "constraints", []) or [])
    by_type: dict[str, int] = {}
    for constraint in constraints:
        kind = _constraint_kind(constraint)
        by_type[kind] = by_type.get(kind, 0) + 1
    return {
        "variable_count": len(variables),
        "boolean_variable_count": sum(1 for variable in variables if _is_boolean_domain(variable)),
        "constraint_count": len(constraints),
        "constraints_by_type": by_type,
        "has_objective": bool(getattr(proto, "objective", None)),
    }


_CONSTRAINT_FIELD_NAMES = (
    "bool_or",
    "bool_and",
    "at_most_one",
    "exactly_one",
    "bool_xor",
    "int_div",
    "int_mod",
    "int_prod",
    "lin_max",
    "linear",
    "all_diff",
    "element",
    "circuit",
    "routes",
    "table",
    "automaton",
    "inverse",
    "reservoir",
    "interval",
    "no_overlap",
    "no_overlap_2d",
    "cumulative",
    "dummy_constraint",
)


def _constraint_kind(constraint: Any) -> str:
    which = getattr(constraint, "WhichOneof", None)
    if callable(which):
        try:
            kind = which("constraint")
            if kind:
                return str(kind)
        except Exception:
            pass

    # Newer OR-Tools Python bindings expose lightweight proto wrappers with
    # has_linear()/has_bool_or() methods instead of protobuf WhichOneof().
    for name in _CONSTRAINT_FIELD_NAMES:
        has_field = getattr(constraint, f"has_{name}", None)
        if callable(has_field):
            try:
                if has_field():
                    return name
            except Exception:
                continue

    list_fields = getattr(constraint, "ListFields", None)
    if callable(list_fields):
        try:
            for field, _value in list_fields():
                name = str(getattr(field, "name", "") or "")
                if name in _CONSTRAINT_FIELD_NAMES:
                    return name
        except Exception:
            pass

    has_field = getattr(constraint, "HasField", None)
    if callable(has_field):
        for name in _CONSTRAINT_FIELD_NAMES:
            try:
                if has_field(name):
                    return name
            except Exception:
                continue

    return "unknown"


def _is_boolean_domain(variable: Any) -> bool:
    domain = list(getattr(variable, "domain", []) or [])
    return domain == [0, 1]


def _build_stats_summary(build_stats: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "exact_core_reuse",
        "ghost_rect",
        "search_guidance",
        "global_valid_inequalities",
        "greedy_hint",
        "exact_candidate_warm_start",
        "exact_candidate_mandatory_support_diagnostics",
    ]
    return {key: build_stats.get(key) for key in keys if key in build_stats}


def _compact_precheck(precheck: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "triggered": bool(precheck.get("triggered", False)),
        "reason": precheck.get("reason"),
        "has_boundary_port_precheck": isinstance(precheck.get("boundary_port_precheck"), Mapping),
    }


def _base_inventory_payload(
    *,
    project_root: Path,
    strategy_path: Path,
    artifact_dir: Path,
    run_id: str,
    target: Mapping[str, Any],
    execute_no_solve: bool,
) -> dict[str, Any]:
    return {
        "schema": "phase3b-checkpoint-free-master-proto-inventory/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "status": "planned_only",
        "execute_no_solve": bool(execute_no_solve),
        "project_root": str(project_root),
        "artifact_dir": str(artifact_dir),
        "strategy_path": str(strategy_path),
        "target": dict(target),
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "scheduler_integration": False,
        "safety": {
            "builder_may_construct_model": bool(execute_no_solve),
            "builder_must_not_call_cp_solver_solve": True,
            "builder_must_not_write_checkpoints": True,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def _target_from_strategy(strategy: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = _mapping(strategy.get("recommendation"))
    interpretation = _mapping(strategy.get("interpretation"))
    if recommendation.get("action") != "prepare_no_solve_master_proto_inventory":
        raise ValueError("Strategy does not authorize master proto inventory preparation")
    if interpretation.get("classification") != "master_model_size_reduction_required_before_more_42x32_runtime":
        raise ValueError("Strategy classification does not match no-solve inventory gate")
    target = _mapping(strategy.get("target"))
    ghost_rect = _mapping(target.get("ghost_rect"))
    return {
        "candidate_key": str(target.get("candidate_key") or ""),
        "candidate_tuple": list(target.get("candidate_tuple", []) or []),
        "ghost_rect": {
            "w": int(ghost_rect.get("w") or 0),
            "h": int(ghost_rect.get("h") or 0),
            "area": int(ghost_rect.get("area") or 0),
        },
        "source_run_id": target.get("run_id"),
    }


def _paths(artifact_dir: Path) -> dict[str, Path]:
    return {
        "plan": artifact_dir / "master_proto_inventory_plan.json",
        "inventory": artifact_dir / "master_proto_inventory.json",
        "markdown": artifact_dir / "master_proto_inventory.md",
        "sensitive_before": artifact_dir / "sensitive_path_before.json",
        "sensitive_after": artifact_dir / "sensitive_path_after.json",
        "sensitive_comparison": artifact_dir / "sensitive_path_comparison.json",
    }


def _assert_inventory_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "24_master_proto_inventory" not in normalized:
        raise ValueError(f"Refusing to write outside master proto inventory namespace: {path}")


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

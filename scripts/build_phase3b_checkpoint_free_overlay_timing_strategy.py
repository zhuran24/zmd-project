from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_PROTO_REVIEW = ARTIFACT_ROOT / "25_master_proto_inventory_review" / "master_proto_inventory_review.json"
DEFAULT_INSTRUMENTATION_REVIEW = (
    ARTIFACT_ROOT
    / "34_via_pole_shape_instrumentation_result_review"
    / "via_pole_shape_instrumentation_result_review.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "35_overlay_timing_strategy"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_overlay_timing_strategy(
        proto_review_path=_resolve_path(PROJECT_ROOT, args.proto_review),
        instrumentation_review_path=_resolve_path(PROJECT_ROOT, args.instrumentation_review),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b checkpoint-free overlay timing strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        print(f"strategy_json={_display_path(PROJECT_ROOT, Path(strategy['strategy_path']))}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a no-solve strategy for broader 42x32 overlay timing diagnostics."
    )
    parser.add_argument("--proto-review", type=Path, default=DEFAULT_PROTO_REVIEW)
    parser.add_argument("--instrumentation-review", type=Path, default=DEFAULT_INSTRUMENTATION_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_overlay_timing_strategy(
    *,
    proto_review_path: Path,
    instrumentation_review_path: Path,
    output_dir: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    output_dir = _resolve_path(PROJECT_ROOT, output_dir)
    _assert_strategy_namespace(output_dir)
    proto_review_path = _resolve_path(PROJECT_ROOT, proto_review_path)
    instrumentation_review_path = _resolve_path(PROJECT_ROOT, instrumentation_review_path)
    proto_review = _load_json(proto_review_path)
    instrumentation_review = _load_json(instrumentation_review_path)
    classification = _classify(proto_review, instrumentation_review)
    payload = {
        "schema": "phase3b-checkpoint-free-overlay-timing-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed",
        "strategy_kind": "broader_no_solve_overlay_timing_strategy",
        "project_root": str(PROJECT_ROOT),
        "proto_review_path": str(proto_review_path),
        "instrumentation_review_path": str(instrumentation_review_path),
        "output_dir": str(output_dir),
        "strategy_path": str(output_dir / "overlay_timing_strategy.json"),
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "target": _target(proto_review, instrumentation_review),
        "evidence": _evidence(proto_review, instrumentation_review),
        "interpretation": {
            "classification": classification,
            "summary": (
                "The prior no-solve inventory says ghost overlay/model-build dominates, while the "
                "default-off via-pole instrumentation explains only a small fraction of wall-clock "
                "build time. A broader wrapper-level no-solve timing probe is required before any "
                "more runtime or source changes."
                if classification == "broader_overlay_timing_required"
                else "Existing evidence is not sufficient to run the wrapper timing probe automatically."
            ),
        },
        "probe_plan": {
            "script": "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
            "default_mode": "plan_only",
            "allowed_execute_target": "42x32",
            "allowed_ghost_rect": {"w": 42, "h": 32, "area": 1344},
            "recommended_run_id": "local_hotspot_42x32_overlay_timing_probe_001",
            "records": [
                "from_exact_core_total_seconds",
                "CoordinateExactMasterDelegate._add_ghost_constraints",
                "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen",
                "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening",
                "CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening",
                "CpModel.AddExactlyOne",
                "CpModel.AddNoOverlap2D",
                "_rebuild_exact_core_overlay_search_guidance",
                "ghost_anchor_interval_and_outer_residual_seconds",
            ],
        },
        "recommendation": _recommendation(classification),
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "overlay_timing_strategy.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "overlay_timing_strategy.md").write_text(
            render_overlay_timing_strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def render_overlay_timing_strategy_markdown(payload: Mapping[str, Any]) -> str:
    interpretation = _mapping(payload.get("interpretation"))
    recommendation = _mapping(payload.get("recommendation"))
    evidence = _mapping(payload.get("evidence"))
    probe = _mapping(payload.get("probe_plan"))
    lines = [
        "# Phase3B Overlay Timing Strategy",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Source/model mutation: `false`",
        "",
        "## Evidence",
        "",
        f"- Prior ghost constraint seconds: `{_fmt(evidence.get('prior_ghost_constraint_seconds'))}`",
        f"- Prior model build seconds: `{_fmt(evidence.get('prior_model_build_seconds'))}`",
        f"- Instrumented phase seconds sum: `{_fmt(evidence.get('instrumented_phase_seconds_sum'))}`",
        f"- Instrumented phase/model ratio: `{_fmt(evidence.get('instrumented_phase_model_ratio'))}`",
        "",
        "## Probe Plan",
        "",
        f"- Script: `{probe.get('script')}`",
        f"- Default mode: `{probe.get('default_mode')}`",
        f"- Allowed execute target: `{probe.get('allowed_execute_target')}`",
        f"- Recommended run id: `{probe.get('recommended_run_id')}`",
        "",
        "This artifact is local diagnostic planning only. It does not authorize solver runtime, checkpoints, proof promotion, scheduler changes, or production-default changes.",
        "",
    ]
    return "\n".join(lines)


def _classify(proto_review: Mapping[str, Any], instrumentation_review: Mapping[str, Any]) -> str:
    proto_evidence = _mapping(proto_review.get("evidence"))
    proto_status = proto_review.get("status")
    proto_ready = (
        (proto_status in {None, "completed"})
        and (proto_evidence.get("inventory_status") in {None, "completed"})
        and _mapping(proto_review.get("interpretation")).get("classification")
        == "ghost_overlay_constraint_build_dominates"
        and proto_review.get("cp_solver_solve_called") is False
        and proto_review.get("checkpoint_written") is False
        and proto_review.get("proof_source") is False
    )
    inst_ready = (
        instrumentation_review.get("status") == "completed"
        and _mapping(instrumentation_review.get("interpretation")).get("classification")
        == "instrumentation_patch_safe_but_target_loop_not_primary_wall_clock_hotspot"
        and instrumentation_review.get("cp_solver_solve_called") is False
        and instrumentation_review.get("checkpoint_written") is False
        and instrumentation_review.get("proof_source") is False
        and _mapping(instrumentation_review.get("sensitive_path_comparison")).get("changed") is False
    )
    ratio = _float(_mapping(instrumentation_review.get("shape_instrumentation")).get("model_build_seconds_ratio"), default=1.0)
    if proto_ready and inst_ready and ratio < 0.05:
        return "broader_overlay_timing_required"
    return "manual_review_required"


def _recommendation(classification: str) -> dict[str, Any]:
    blocked = [
        "do_not_run_more_42x32_runtime",
        "do_not_run_67x20",
        "do_not_run_full_wave_matrix",
        "do_not_write_canonical_checkpoints",
        "do_not_promote_local_results_to_proof",
        "do_not_change_production_defaults",
    ]
    if classification == "broader_overlay_timing_required":
        return {
            "action": "run_single_42x32_wrapper_no_solve_overlay_timing_probe",
            "next_engineering_step": (
                "Run the plan-only wrapper timing probe first, then execute exactly one 42x32 no-solve "
                "overlay timing probe if the plan and guards are clean."
            ),
            "blocked_actions": blocked,
        }
    return {
        "action": "hold_for_manual_overlay_timing_review",
        "next_engineering_step": "Review S25/S34 evidence before any broader timing probe or runtime step.",
        "blocked_actions": blocked,
    }


def _target(proto_review: Mapping[str, Any], instrumentation_review: Mapping[str, Any]) -> dict[str, Any]:
    target = _mapping(instrumentation_review.get("target")) or _mapping(proto_review.get("target"))
    return {
        "candidate_key": str(target.get("candidate_key", "42x32")),
        "candidate_tuple": list(target.get("candidate_tuple", [1344, 42, 32]) or [1344, 42, 32]),
        "ghost_rect": dict(target.get("ghost_rect", {"w": 42, "h": 32, "area": 1344}) or {"w": 42, "h": 32, "area": 1344}),
    }


def _evidence(proto_review: Mapping[str, Any], instrumentation_review: Mapping[str, Any]) -> dict[str, Any]:
    proto_evidence = _mapping(proto_review.get("evidence"))
    timings = _mapping(proto_evidence.get("timing_hotspots"))
    shape_inst = _mapping(instrumentation_review.get("shape_instrumentation"))
    return {
        "proto_review_classification": _mapping(proto_review.get("interpretation")).get("classification"),
        "instrumentation_review_classification": _mapping(instrumentation_review.get("interpretation")).get("classification"),
        "prior_model_build_seconds": _float(proto_evidence.get("model_build_seconds")),
        "prior_ghost_constraint_seconds": _float(timings.get("ghost_constraint_seconds")),
        "prior_ghost_constraint_fraction": _float(timings.get("ghost_constraint_fraction_of_model_build")),
        "instrumented_model_build_seconds": _float(instrumentation_review.get("model_build_seconds")),
        "instrumented_phase_seconds_sum": _float(shape_inst.get("phase_seconds_sum")),
        "instrumented_phase_model_ratio": _float(shape_inst.get("model_build_seconds_ratio")),
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "35_overlay_timing_strategy" not in normalized:
        raise ValueError(f"Refusing to write outside overlay timing strategy namespace: {path}")


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any, *, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: Any) -> str:
    number = _float(value)
    return "null" if number is None else f"{number:.6f}"


if __name__ == "__main__":
    raise SystemExit(main())

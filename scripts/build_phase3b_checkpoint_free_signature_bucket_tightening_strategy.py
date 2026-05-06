from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_OVERLAY_TIMING_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_overlay_timing_probe_001"
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "36_signature_bucket_tightening_strategy"

HOTSPOT_PHASE = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_tightening_strategy(
        overlay_timing_probe_path=_resolve_path(PROJECT_ROOT, args.overlay_timing_probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b checkpoint-free signature bucket tightening strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        print(f"strategy_json={_display_path(PROJECT_ROOT, Path(strategy['strategy_path']))}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a no-solve strategy for 42x32 signature bucket tightening diagnostics."
    )
    parser.add_argument("--overlay-timing-probe", type=Path, default=DEFAULT_OVERLAY_TIMING_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_tightening_strategy(
    *,
    overlay_timing_probe_path: Path,
    output_dir: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    output_dir = _resolve_path(PROJECT_ROOT, output_dir)
    _assert_strategy_namespace(output_dir)
    overlay_timing_probe_path = _resolve_path(PROJECT_ROOT, overlay_timing_probe_path)
    probe = _load_json(overlay_timing_probe_path)
    evidence = _extract_evidence(probe)
    classification = _classify(probe, evidence)
    wrapper_timing_complete = classification == "signature_bucket_internal_loop_strategy_required"
    payload = {
        "schema": "phase3b-checkpoint-free-signature-bucket-tightening-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed",
        "strategy_kind": "signature_bucket_tightening_internal_loop_strategy",
        "project_root": str(PROJECT_ROOT),
        "overlay_timing_probe_path": str(overlay_timing_probe_path),
        "output_dir": str(output_dir),
        "strategy_path": str(output_dir / "signature_bucket_tightening_strategy.json"),
        "wrapper_timing_complete": wrapper_timing_complete,
        "hotspot_method": HOTSPOT_PHASE,
        "no_solve": True,
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
        "target": _target(probe),
        "evidence": evidence,
        "interpretation": {
            "classification": classification,
            "summary": _summary_for(classification),
        },
        "recommendation": _recommendation(classification),
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "signature_bucket_tightening_strategy.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "signature_bucket_tightening_strategy.md").write_text(
            render_signature_bucket_tightening_strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def render_signature_bucket_tightening_strategy_markdown(payload: Mapping[str, Any]) -> str:
    interpretation = _mapping(payload.get("interpretation"))
    recommendation = _mapping(payload.get("recommendation"))
    evidence = _mapping(payload.get("evidence"))
    lines = [
        "# Phase3B Signature Bucket Tightening Strategy",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Hotspot method: `{payload.get('hotspot_method')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- No solve: `true`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Source/model mutation: `false`",
        "",
        "## Evidence",
        "",
        f"- `from_exact_core` seconds: `{_fmt(evidence.get('from_exact_core_total_seconds'))}`",
        f"- Ghost constraints seconds: `{_fmt(evidence.get('ghost_constraints_seconds'))}`",
        f"- Signature bucket tightening seconds: `{_fmt(evidence.get('signature_bucket_tightening_seconds'))}`",
        f"- Signature/ghost fraction: `{_fmt(evidence.get('signature_bucket_fraction_of_ghost_constraints'))}`",
        f"- Signature/from_exact_core fraction: `{_fmt(evidence.get('signature_bucket_fraction_of_from_exact_core'))}`",
        f"- Ghost-conditioned mandatory constraints: `{evidence.get('ghost_conditioned_mandatory_bucket_constraints')}`",
        f"- Ghost-conditioned required-optional constraints: `{evidence.get('ghost_conditioned_required_optional_bucket_constraints')}`",
        f"- Ghost signature reduction anchors: `{evidence.get('ghost_signature_reduction_anchor_count')}`",
        f"- Ghost cell visits per mandatory payload lower bound: `{evidence.get('ghost_cell_visits_per_mandatory_payload_lower_bound')}`",
        "",
        "## Decision",
        "",
        str(interpretation.get("summary")),
        "",
        "This artifact is local diagnostic strategy only. It does not authorize runtime, source mutation, canonical checkpoints, proof promotion, scheduler changes, or production-default changes.",
        "",
    ]
    return "\n".join(lines)


def _classify(probe: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
    safety_ok = (
        probe.get("status") == "completed"
        and probe.get("no_solve") is True
        and probe.get("cp_solver_solve_called") is False
        and probe.get("checkpoint_written") is False
        and probe.get("proof_source") is False
        and probe.get("source_model_mutation") is False
        and _mapping(probe.get("sensitive_path_comparison")).get("changed") is False
    )
    timing_complete = (
        _mapping(_mapping(probe.get("timing")).get("coverage")).get("wrapper_level_only") is True
        and evidence.get("signature_bucket_tightening_seconds") is not None
        and evidence.get("ghost_constraints_seconds") is not None
        and evidence.get("from_exact_core_total_seconds") is not None
    )
    constraints_known = (
        evidence.get("ghost_conditioned_mandatory_bucket_constraints") is not None
        and evidence.get("ghost_conditioned_required_optional_bucket_constraints") is not None
        and evidence.get("ghost_signature_reduction_anchor_count") is not None
    )
    hotspot = (
        _float(evidence.get("signature_bucket_tightening_seconds"), default=0.0) >= 30.0
        and _float(evidence.get("signature_bucket_fraction_of_ghost_constraints"), default=0.0) >= 0.5
        and int(evidence.get("ghost_conditioned_mandatory_bucket_constraints") or 0) <= 100
        and int(evidence.get("ghost_conditioned_required_optional_bucket_constraints") or 0) == 0
    )
    if safety_ok and timing_complete and constraints_known and hotspot:
        return "signature_bucket_internal_loop_strategy_required"
    return "manual_review_required"


def _extract_evidence(probe: Mapping[str, Any]) -> dict[str, Any]:
    timing = _mapping(probe.get("timing"))
    phases = _phase_seconds(timing)
    inventory = _mapping(probe.get("inventory"))
    build_stats = _mapping(inventory.get("build_stats_summary"))
    ghost_rect = _mapping(build_stats.get("ghost_rect"))
    gvi = _mapping(build_stats.get("global_valid_inequalities"))
    signature = _mapping(gvi.get("signature_bucket_capacity_bounds"))
    residual = _mapping(gvi.get("residual_signature_bucket_capacity_bounds"))
    via_pole = _mapping(gvi.get("ghost_aware_via_pole_feasibility"))
    from_exact = _float(timing.get("from_exact_core_total_seconds"))
    ghost_seconds = _float(
        phases.get("CoordinateExactMasterDelegate._add_ghost_constraints"),
        default=_float(_mapping(timing.get("build_stats_exact_core_reuse")).get("ghost_constraint_seconds")),
    )
    signature_seconds = _float(phases.get(HOTSPOT_PHASE))
    residual_seconds = _float(
        phases.get("CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening")
    )
    placements = _int(ghost_rect.get("placements"), default=_int(via_pole.get("evaluated_placements")))
    area = _int(_mapping(_target(probe).get("ghost_rect")).get("area"), default=1344)
    mandatory_group_count = len(list(signature.get("mandatory_groups", []) or []))
    required_optional_group_count = len(list(signature.get("required_optional_groups", []) or []))
    return {
        "overlay_timing_status": probe.get("status"),
        "wrapper_level_only": _mapping(timing.get("coverage")).get("wrapper_level_only"),
        "from_exact_core_total_seconds": from_exact,
        "ghost_constraints_seconds": ghost_seconds,
        "signature_bucket_tightening_seconds": signature_seconds,
        "signature_bucket_fraction_of_ghost_constraints": _ratio(signature_seconds, ghost_seconds),
        "signature_bucket_fraction_of_from_exact_core": _ratio(signature_seconds, from_exact),
        "residual_signature_bucket_tightening_seconds": residual_seconds,
        "ghost_anchor_interval_and_outer_residual_seconds": _float(
            timing.get("ghost_anchor_interval_and_outer_residual_seconds")
        ),
        "recorded_phase_seconds_sum": _float(timing.get("recorded_phase_seconds_sum")),
        "recorded_phase_sum_double_counts_nested_methods": True,
        "mandatory_bucket_upper_bound_constraints": _optional_int(
            signature.get("mandatory_bucket_upper_bound_constraints")
        ),
        "required_optional_bucket_upper_bound_constraints": _optional_int(
            signature.get("required_optional_bucket_upper_bound_constraints")
        ),
        "ghost_conditioned_mandatory_bucket_constraints": _optional_int(
            signature.get("ghost_conditioned_mandatory_bucket_constraints")
        ),
        "ghost_conditioned_required_optional_bucket_constraints": _optional_int(
            signature.get("ghost_conditioned_required_optional_bucket_constraints")
        ),
        "ghost_signature_reduction_anchor_count": _optional_int(
            signature.get("ghost_signature_reduction_anchor_count")
        ),
        "mandatory_signature_payload_group_count": mandatory_group_count,
        "required_optional_signature_payload_group_count": required_optional_group_count,
        "residual_signature_bucket_constraints": _optional_int(
            residual.get("ghost_conditioned_residual_bucket_constraints")
        ),
        "residual_signature_reduction_anchor_count": _optional_int(
            residual.get("ghost_residual_signature_reduction_anchor_count")
        ),
        "evaluated_ghost_placements": placements,
        "ghost_area": area,
        "ghost_cell_visits_per_mandatory_payload_lower_bound": placements * area
        if placements is not None and area is not None
        else None,
        "ghost_cell_visits_all_mandatory_payloads_lower_bound": placements * area * mandatory_group_count
        if placements is not None and area is not None and mandatory_group_count
        else None,
        "observed_required_optional_signature_constraints_zero": (
            _optional_int(signature.get("ghost_conditioned_required_optional_bucket_constraints")) == 0
        ),
    }


def _phase_seconds(timing: Mapping[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in list(timing.get("phases", []) or []):
        if not isinstance(row, Mapping):
            continue
        phase = row.get("phase")
        if isinstance(phase, str):
            values[phase] = _float(row.get("total_seconds"))
    return values


def _summary_for(classification: str) -> str:
    if classification == "signature_bucket_internal_loop_strategy_required":
        return (
            "S35 wrapper timing is complete enough to isolate the no-solve 42x32 model-build hotspot "
            "inside signature bucket tightening. The method spends roughly a minute but emits only a "
            "small number of ghost-conditioned constraints, so the likely cost is payload construction, "
            "per-anchor cell/pose scanning, de-duplication, and bucket-reduction checks rather than the "
            "final Add() calls. The next safe step is a default-off source instrumentation spec, not more "
            "runtime."
        )
    return (
        "S35 timing or build_stats are missing or safety flags are not clean, so this needs manual review "
        "before any instrumentation spec or follow-up diagnostic."
    )


def _recommendation(classification: str) -> dict[str, Any]:
    blocked = [
        "do_not_run_more_42x32_runtime",
        "do_not_run_67x20",
        "do_not_run_full_wave_matrix",
        "do_not_mutate_src_models_without_explicit_authorization",
        "do_not_write_canonical_checkpoints",
        "do_not_promote_local_results_to_proof",
        "do_not_change_production_defaults",
    ]
    if classification == "signature_bucket_internal_loop_strategy_required":
        return {
            "action": "prepare_default_off_signature_bucket_tightening_instrumentation_patch_spec",
            "next_engineering_step": (
                "Generate the S37 spec-only authorization packet for default-off instrumentation inside "
                "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening, then wait "
                "for explicit source-patch authorization."
            ),
            "blocked_actions": blocked,
        }
    return {
        "action": "hold_for_manual_signature_bucket_tightening_review",
        "next_engineering_step": "Review S35 overlay timing/build_stats before preparing source instrumentation.",
        "blocked_actions": blocked,
    }


def _target(probe: Mapping[str, Any]) -> dict[str, Any]:
    target = _mapping(probe.get("target"))
    ghost_rect = dict(target.get("ghost_rect", {"w": 42, "h": 32, "area": 1344}) or {})
    if "area" not in ghost_rect:
        ghost_rect["area"] = _int(ghost_rect.get("w"), default=42) * _int(ghost_rect.get("h"), default=32)
    return {
        "candidate_key": str(target.get("candidate_key", "42x32")),
        "candidate_tuple": list(target.get("candidate_tuple", [1344, 42, 32]) or [1344, 42, 32]),
        "ghost_rect": ghost_rect,
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "36_signature_bucket_tightening_strategy" not in normalized
    ):
        raise ValueError(f"Refusing to write outside signature bucket tightening strategy namespace: {path}")


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any, *, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, *, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: Any) -> int | None:
    return _int(value)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0.0}:
        return None
    return numerator / denominator


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return "null"


if __name__ == "__main__":
    raise SystemExit(main())

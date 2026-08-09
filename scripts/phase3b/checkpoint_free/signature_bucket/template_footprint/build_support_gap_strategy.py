from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_S75 = (
    ARTIFACT_ROOT
    / "75_signature_bucket_template_footprint_probe_execution"
    / "signature_bucket_template_footprint_probe_execution.json"
)
DEFAULT_S73 = (
    ARTIFACT_ROOT
    / "73_signature_bucket_template_footprint_probe_review"
    / "signature_bucket_template_footprint_probe_review.json"
)
DEFAULT_S71 = (
    ARTIFACT_ROOT
    / "71_signature_bucket_template_footprint_support_implementation"
    / "s71_signature_bucket_template_footprint_support_implementation.json"
)
DEFAULT_AGENTS = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "76_signature_bucket_template_footprint_support_gap_strategy"

TARGET_CLASSIFICATION = "template_footprint_support_not_used_strategy_required"
TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
FUTURE_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION"
EXISTING_SIGNATURE_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
EXISTING_REGION_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
EXISTING_FALLBACK_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
EXISTING_TEMPLATE_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_template_footprint_support_gap_strategy(
        s75_path=_resolve_path(PROJECT_ROOT, args.s75),
        s73_path=_resolve_path(PROJECT_ROOT, args.s73),
        s71_path=_resolve_path(PROJECT_ROOT, args.s71),
        agents_path=_resolve_path(PROJECT_ROOT, args.agents),
        source_path=_resolve_path(PROJECT_ROOT, args.source),
    )
    print("phase3b signature bucket template-footprint support gap strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_template_footprint_support_gap_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the S76 review-first strategy after S75 showed template-footprint "
            "support was enabled but not used by the 42x32 no-solve overlay."
        )
    )
    parser.add_argument("--s75", type=Path, default=DEFAULT_S75)
    parser.add_argument("--s73", type=Path, default=DEFAULT_S73)
    parser.add_argument("--s71", type=Path, default=DEFAULT_S71)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_template_footprint_support_gap_strategy(
    *,
    s75_path: Path,
    s73_path: Path,
    s71_path: Path,
    agents_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    s75 = _load_json(s75_path)
    s73 = _load_json(s73_path)
    s71 = _load_json(s71_path)
    agents_text = Path(agents_path).read_text(encoding="utf-8")
    source_text = Path(source_path).read_text(encoding="utf-8")
    checks = _classify_inputs(
        s75=s75,
        s73=s73,
        s71=s71,
        agents_text=agents_text,
        source_text=source_text,
    )
    completed = all(check["status"] == "passed" for check in checks)
    classification = TARGET_CLASSIFICATION if completed else "manual_review_required"
    evidence = _evidence_summary(s75=s75, s73=s73)
    return {
        "schema": "phase3b-signature-bucket-template-footprint-support-gap-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "strategy_kind": "review_first_template_footprint_support_gap_no_source_mutation",
        "inputs": {
            "s75_execution": str(s75_path),
            "s73_probe_review": str(s73_path),
            "s71_implementation": str(s71_path),
            "agents": str(agents_path),
            "source": str(source_path),
        },
        "input_checks": checks,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "proof_source": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "runtime_execution_performed": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "scheduler_integration": False,
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "interpretation": {
            "classification": classification,
            "source_mutation_authorized_by_this_artifact": False,
            "implementation_allowed_now": False,
            "reason": (
                "S75 safely executed the single enabled 42x32 no-solve probe, but "
                "template-footprint support was not used: attempts were recorded, "
                "fast-path uses stayed at zero, and unsupported footprint fallbacks "
                "remained unchanged. The next safe step is review of a default-off "
                "support-gap diagnostic before any source patch or rerun."
                if completed
                else "S75/S73/S71 inputs, AGENTS gate, or source context do not prove the clean not-used support-gap state."
            ),
        },
        "evidence_summary": evidence,
        "future_diagnostic_spec": _future_diagnostic_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_template_footprint_support_gap_external_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S77 external review package for support-gap diagnostics"
                if completed
                else "inspect S75/S73/S71/source inputs manually"
            ),
            "blocked_actions": [
                "do_not_rerun_enabled_42x32_probe",
                "do_not_mutate_src_models_before_external_review_and_project_authorization",
                "do_not_run_runtime_solve",
                "do_not_run_67x20",
                "do_not_run_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }


def write_signature_bucket_template_footprint_support_gap_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_template_footprint_support_gap_strategy.json"
    md_path = output_dir / "signature_bucket_template_footprint_support_gap_strategy.md"
    json_path.write_text(
        json.dumps(strategy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        render_signature_bucket_template_footprint_support_gap_strategy_markdown(strategy),
        encoding="utf-8",
    )
    return {"json": json_path, "md": md_path}


def render_signature_bucket_template_footprint_support_gap_strategy_markdown(
    strategy: Mapping[str, Any],
) -> str:
    interpretation = _mapping(strategy.get("interpretation"))
    evidence = _mapping(strategy.get("evidence_summary"))
    spec = _mapping(strategy.get("future_diagnostic_spec"))
    lines = [
        "# Phase3B S76 Signature Bucket Template-Footprint Support Gap Strategy",
        "",
        f"- Status: `{strategy.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Review required before authorization: `true`",
        "",
        "## Evidence",
        "",
        f"- S73 classification: `{evidence.get('s73_classification')}`",
        f"- Template support attempts: `{evidence.get('template_footprint_support_attempts')}`",
        f"- Template support used: `{evidence.get('template_footprint_support_used')}`",
        f"- Template support fallbacks: `{evidence.get('template_footprint_support_fallbacks')}`",
        f"- Unsupported footprint fallbacks: `{evidence.get('unsupported_footprint_fallbacks')}`",
        f"- Unsupported reduction ratio: `{_fmt(evidence.get('unsupported_footprint_reduction_ratio'))}`",
        f"- Mandatory scan reduction ratio: `{_fmt(evidence.get('mandatory_scan_reduction_ratio'))}`",
        f"- Current mandatory scan seconds: `{_fmt(evidence.get('current_mandatory_scan_seconds'))}`",
        "",
        "## Future Diagnostic Spec",
        "",
        f"- Env gate: `{spec.get('env_var')}`",
        f"- Target method: `{spec.get('target_method')}`",
        f"- Enabled scope: `{spec.get('enabled_scope')}`",
        "",
        "This artifact is review preparation only; it is not authorization and not a source patch.",
        "",
    ]
    return "\n".join(lines)


def _classify_inputs(
    *,
    s75: Mapping[str, Any],
    s73: Mapping[str, Any],
    s71: Mapping[str, Any],
    agents_text: str,
    source_text: str,
) -> list[dict[str, str]]:
    s75_interpretation = _mapping(s75.get("interpretation"))
    s75_safety = _mapping(s75.get("safety"))
    s73_interpretation = _mapping(s73.get("interpretation"))
    s73_instr = _mapping(s73.get("signature_instrumentation"))
    s73_totals = _mapping(s73_instr.get("totals"))
    s73_fallback_reasons = _mapping(s73_instr.get("fallback_reasons"))
    s73_safety = _mapping(s73.get("probe_safety"))
    s73_actual_flags = _mapping(s73_safety.get("actual_flags"))
    s73_sensitive = _mapping(s73_safety.get("sensitive_path_comparison"))
    template_attempts = _int(s73_interpretation.get("template_footprint_support_attempts"))
    template_used = _int(s73_interpretation.get("template_footprint_support_used"))
    template_fallbacks = _int(s73_interpretation.get("template_footprint_support_fallbacks"))
    unsupported = _int(s73_interpretation.get("current_unsupported_footprint_fallbacks"))
    checks = [
        (
            "s75_completed_and_not_used",
            s75.get("status") == "completed"
            and s75.get("s73_status") == "completed"
            and s75.get("s73_classification") == "template_footprint_support_not_used"
            and s75_interpretation.get("next_engineering_step")
            == "review_template_footprint_support_coverage_or_fixture_gap",
        ),
        (
            "s73_completed_template_support_not_used",
            s73.get("status") == "completed"
            and s73_interpretation.get("classification") == "template_footprint_support_not_used",
        ),
        (
            "template_support_attempted_but_never_used",
            template_attempts > 0
            and template_used == 0
            and template_fallbacks > 0
            and _int(s73_totals.get("mandatory_template_footprint_support_attempts"))
            == template_attempts
            and _int(s73_totals.get("mandatory_template_footprint_support_used")) == 0,
        ),
        (
            "unsupported_fallback_unchanged_and_visible",
            unsupported > 0
            and unsupported == template_fallbacks
            and _int(s73_fallback_reasons.get("unsupported_or_missing_template_footprint"))
            == unsupported
            and _float(s73_interpretation.get("unsupported_footprint_reduction_ratio")) == 0.0,
        ),
        ("s75_safety_clean", _s75_safety_clean(s75_safety)),
        (
            "s73_safety_clean",
            s73_safety.get("status_completed") is True
            and s73_safety.get("run_id_matches") is True
            and s73_safety.get("candidate_key_42x32") is True
            and s73_safety.get("execute_no_solve") is True
            and s73_safety.get("hard_boundary_flags_literal_false") is True
            and all(s73_actual_flags.get(key) is False for key in _HARD_BOUNDARY_FLAGS)
            and s73_sensitive.get("schema") == "phase3b-sensitive-path-fingerprint-comparison/v0"
            and s73_sensitive.get("changed") is False
            and s73_sensitive.get("changed_paths") == []
            and s73_sensitive.get("changed_entries") == [],
        ),
        (
            "s71_implemented_and_verified",
            s71.get("status") == "implemented_and_verified"
            and _mapping(s71.get("env_gate")).get("name") == EXISTING_TEMPLATE_ENV_VAR,
        ),
        (
            "source_has_template_support_and_gap_observation_hooks",
            EXISTING_TEMPLATE_ENV_VAR in source_text
            and "mandatory_template_footprint_support_attempts" in source_text
            and "mandatory_template_footprint_support_used" in source_text
            and "unsupported_or_missing_template_footprint" in source_text,
        ),
        (
            "agents_records_s75_gate",
            "S75" in agents_text
            and "template_footprint_support_not_used" in agents_text
            and "review-first" in agents_text,
        ),
    ]
    return [
        {"name": name, "status": "passed" if passed else "failed"}
        for name, passed in checks
    ]


def _s75_safety_clean(safety: Mapping[str, Any]) -> bool:
    return (
        safety.get("execute_no_solve") is True
        and all(safety.get(key) is False for key in _S75_RECORDED_HARD_BOUNDARY_FLAGS)
        and safety.get("sensitive_path_changed") is False
        and safety.get("canonical_checkpoint_state_exists") is False
        and safety.get("canonical_checkpoint_telemetry_exists") is False
    )


def _evidence_summary(
    *,
    s75: Mapping[str, Any],
    s73: Mapping[str, Any],
) -> dict[str, Any]:
    s75_interpretation = _mapping(s75.get("interpretation"))
    s73_interpretation = _mapping(s73.get("interpretation"))
    instrumentation = _mapping(s73.get("signature_instrumentation"))
    totals = _mapping(instrumentation.get("totals"))
    return {
        "s75_run_id": s75.get("run_id"),
        "s75_probe_path": s75.get("probe_output"),
        "s75_review_output": s75.get("review_output"),
        "s73_classification": s73_interpretation.get("classification"),
        "model_build_seconds": s75.get("model_build_seconds"),
        "baseline_mandatory_scan_seconds": s73_interpretation.get(
            "baseline_mandatory_scan_seconds"
        )
        or s75_interpretation.get("baseline_mandatory_scan_seconds"),
        "current_mandatory_scan_seconds": s73_interpretation.get(
            "current_mandatory_scan_seconds"
        )
        or s75_interpretation.get("current_mandatory_scan_seconds"),
        "mandatory_scan_reduction_ratio": s73_interpretation.get(
            "mandatory_scan_reduction_ratio"
        )
        or s75_interpretation.get("mandatory_scan_reduction_ratio"),
        "unsupported_footprint_reduction_ratio": s73_interpretation.get(
            "unsupported_footprint_reduction_ratio"
        )
        if s73_interpretation.get("unsupported_footprint_reduction_ratio") is not None
        else s75_interpretation.get("unsupported_footprint_reduction_ratio"),
        "template_footprint_support_attempts": s73_interpretation.get(
            "template_footprint_support_attempts"
        )
        or totals.get("mandatory_template_footprint_support_attempts"),
        "template_footprint_support_used": s73_interpretation.get(
            "template_footprint_support_used"
        )
        if s73_interpretation.get("template_footprint_support_used") is not None
        else totals.get("mandatory_template_footprint_support_used"),
        "template_footprint_support_fallbacks": s73_interpretation.get(
            "template_footprint_support_fallbacks"
        )
        or totals.get("mandatory_template_footprint_support_fallbacks"),
        "unsupported_footprint_fallbacks": s73_interpretation.get(
            "current_unsupported_footprint_fallbacks"
        ),
        "fallback_reasons": dict(_mapping(instrumentation.get("fallback_reasons"))),
        "top_fallback_entries": list(instrumentation.get("top_fallback_entries", []) or [])[:10],
        "safety": dict(_mapping(s75.get("safety"))),
    }


def _future_diagnostic_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": TARGET_METHOD,
        "env_var": FUTURE_ENV_VAR,
        "required_existing_envs_for_visibility": [
            EXISTING_SIGNATURE_ENV_VAR,
            EXISTING_REGION_ENV_VAR,
            EXISTING_FALLBACK_ENV_VAR,
            EXISTING_TEMPLATE_ENV_VAR,
        ],
        "enabled_scope": (
            "observe why template-footprint support rejects mandatory region-counting "
            "payloads after S71, without changing fast-path decisions, legacy fallback, "
            "constraints, ModelProto, scheduler inputs, proof inputs, checkpoints, or "
            "production defaults"
        ),
        "default_off_contract": [
            f"`{FUTURE_ENV_VAR}` unset or false creates no new diagnostics and preserves S71 behavior.",
            "Enabled diagnostics are recorded only under existing signature_tightening_instrumentation.",
            "Invalid env values should fail fast and mention the env var name.",
        ],
        "proposed_fields": {
            "template_footprint_support_gap_reasons": [
                "missing_pose_occupied_cells",
                "empty_pose_occupied_cells",
                "non_rectangular_occupied_cells",
                "unstable_footprint_bounds_within_payload",
                "missing_template_or_group_metadata",
                "bucket_region_metadata_missing",
                "same_bucket_regions_overlap",
                "region_counting_guard_rejected",
                "legacy_scan_required_other",
            ],
            "top_template_footprint_gap_entries": [
                "rect_idx",
                "anchor",
                "group_id_or_template",
                "bucket_id",
                "reason",
                "pose_count",
                "occupied_cell_count",
                "footprint_bounds_when_available",
                "elapsed_seconds",
            ],
        },
        "review_questions": [
            "Is S75 sufficient evidence that the S71 support path was enabled but not used?",
            "Is the proposed default-off support-gap diagnostic narrow enough to request user/project-owner authorization later?",
            "Are the proposed rejection categories sufficient to distinguish fixture/source coverage gaps from real unsupported geometry?",
            "Can the diagnostic be stats-only without changing mandatory region-counting decisions or legacy fallback behavior?",
            "Are tests needed to prove no default-off delta, invalid-env fail-fast behavior, and enabled diagnostics without proto/constraint changes?",
        ],
        "non_goals": [
            "no source mutation in S76/S77",
            "no new enabled 42x32 probe in S76/S77",
            "no runtime solve",
            "no canonical checkpoint write/import/backfill",
            "no proof/preflight/release/viewer/frontdoor mutation",
            "no production default change",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "external_review_before_authorization",
            "check": "submit S77 package for review; request project authorization only if review passes",
        },
        {
            "id": "default_off_no_delta",
            "check": "future implementation must preserve S71 default-off ModelProto, constraints, build_stats, and decisions",
        },
        {
            "id": "enabled_observation_only",
            "check": "enabled diagnostics must observe support rejection categories without changing fast/fallback behavior",
        },
        {
            "id": "no_probe_or_runtime_in_this_slice",
            "check": "S76/S77 must not execute a new 42x32 probe, runtime solve, or checkpoint write",
        },
    ]


_HARD_BOUNDARY_FLAGS = (
    "fresh_solver_run_started",
    "main_py_executed",
    "exact_campaign_used",
    "cp_solver_solve_called",
    "checkpoint_written",
    "proof_source",
    "source_model_mutation",
    "source_mutation_performed",
    "candidate_universe_changed",
    "scheduler_integration",
    "runtime_execution_performed",
    "production_profile_changed",
)

_S75_RECORDED_HARD_BOUNDARY_FLAGS = tuple(
    flag for flag in _HARD_BOUNDARY_FLAGS if flag != "fresh_solver_run_started"
)


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "76_signature_bucket_template_footprint_support_gap_strategy" not in normalized
    ):
        raise ValueError(
            f"Refusing to write outside S76 template-footprint support gap strategy namespace: {path}"
        )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _fmt(value: Any) -> str:
    return f"{float(value):.6f}" if isinstance(value, (int, float)) else "n/a"


if __name__ == "__main__":
    raise SystemExit(main())

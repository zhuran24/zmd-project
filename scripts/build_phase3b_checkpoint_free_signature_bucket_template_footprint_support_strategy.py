from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_S68 = (
    ARTIFACT_ROOT
    / "68_signature_bucket_fallback_reason_probe_execution"
    / "signature_bucket_fallback_reason_probe_execution.json"
)
DEFAULT_S64 = (
    ARTIFACT_ROOT
    / "64_signature_bucket_fallback_reason_probe_review"
    / "signature_bucket_fallback_reason_probe_review.json"
)
DEFAULT_AGENTS = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "69_signature_bucket_template_footprint_support_strategy"

ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT"
CURRENT_SIGNATURE_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
)
CURRENT_REGION_COUNTING_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
CURRENT_FALLBACK_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
)
TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
TARGET_CLASSIFICATION = "unsupported_template_footprint_support_strategy_required"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_template_footprint_support_strategy(
        s68_path=_resolve_path(PROJECT_ROOT, args.s68),
        s64_path=_resolve_path(PROJECT_ROOT, args.s64),
        agents_path=_resolve_path(PROJECT_ROOT, args.agents),
        source_path=_resolve_path(PROJECT_ROOT, args.source),
    )
    print("phase3b signature bucket template-footprint support strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_template_footprint_support_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the S69 review-first strategy after S68/S64 showed that "
            "unsupported template footprints dominate mandatory region-counting fallback."
        )
    )
    parser.add_argument("--s68", type=Path, default=DEFAULT_S68)
    parser.add_argument("--s64", type=Path, default=DEFAULT_S64)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_template_footprint_support_strategy(
    *,
    s68_path: Path,
    s64_path: Path,
    agents_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    s68 = _load_json(s68_path)
    s64 = _load_json(s64_path)
    agents_text = Path(agents_path).read_text(encoding="utf-8")
    source_text = Path(source_path).read_text(encoding="utf-8")
    checks = _classify_inputs(
        s68=s68,
        s64=s64,
        agents_text=agents_text,
        source_text=source_text,
    )
    completed = all(check["status"] == "passed" for check in checks)
    classification = TARGET_CLASSIFICATION if completed else "manual_review_required"
    evidence = _evidence_summary(s68=s68, s64=s64)
    return {
        "schema": "phase3b-signature-bucket-template-footprint-support-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "strategy_kind": "review_first_template_footprint_support_no_source_mutation",
        "inputs": {
            "s68_execution": str(s68_path),
            "s64_probe_review": str(s64_path),
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
                "S68/S64 show the remaining mandatory region-counting fallback is dominated "
                "by unsupported_or_missing_template_footprint. The next safe step is external "
                "review of a narrow default-off template-footprint support patch before any "
                "source mutation or second enabled probe."
                if completed
                else "S68/S64 inputs, AGENTS gate, or source context are not in the expected clean unsupported-footprint state."
            ),
        },
        "evidence_summary": evidence,
        "future_patch_spec": _future_patch_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_template_footprint_support_external_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S70 external review package before requesting template-footprint support authorization"
                if completed
                else "inspect S68/S64/source inputs manually"
            ),
            "blocked_actions": [
                "do_not_rerun_enabled_42x32_probe",
                "do_not_mutate_src_models_before_external_review_and_user_authorization",
                "do_not_run_runtime_solve",
                "do_not_run_67x20",
                "do_not_run_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }


def write_signature_bucket_template_footprint_support_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_template_footprint_support_strategy.json"
    md_path = output_dir / "signature_bucket_template_footprint_support_strategy.md"
    json_path.write_text(
        json.dumps(strategy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        render_signature_bucket_template_footprint_support_strategy_markdown(strategy),
        encoding="utf-8",
    )
    return {"json": json_path, "md": md_path}


def render_signature_bucket_template_footprint_support_strategy_markdown(
    strategy: Mapping[str, Any],
) -> str:
    interpretation = _mapping(strategy.get("interpretation"))
    evidence = _mapping(strategy.get("evidence_summary"))
    spec = _mapping(strategy.get("future_patch_spec"))
    lines = [
        "# Phase3B S69 Signature Bucket Template-Footprint Support Strategy",
        "",
        f"- Status: `{strategy.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Review required before authorization: `true`",
        "",
        "## Evidence",
        "",
        f"- S64 classification: `{evidence.get('s64_classification')}`",
        f"- Dominant fallback reason: `{evidence.get('dominant_reason')}`",
        f"- Dominant reason count: `{evidence.get('dominant_reason_count')}`",
        f"- Dominant reason ratio: `{_fmt(evidence.get('dominant_reason_ratio'))}`",
        f"- Fallback reason total: `{evidence.get('fallback_reason_total')}`",
        f"- Mandatory region-counting attempts: `{evidence.get('mandatory_region_counting_attempts')}`",
        f"- Mandatory region-counting used: `{evidence.get('mandatory_region_counting_used')}`",
        f"- Mandatory region-counting fallbacks: `{evidence.get('mandatory_region_counting_fallbacks')}`",
        f"- Mandatory scan seconds: `{_fmt(evidence.get('mandatory_scan_seconds'))}`",
        "",
        "## Future Patch Spec",
        "",
        f"- Env gate: `{spec.get('env_var')}`",
        f"- Target method: `{spec.get('target_method')}`",
        f"- Enabled scope: `{spec.get('enabled_scope')}`",
        f"- Exactness contract: `{spec.get('exactness_contract')}`",
        "",
        "This artifact is review preparation only; it is not authorization and not a source patch.",
        "",
    ]
    return "\n".join(lines)


def _classify_inputs(
    *,
    s68: Mapping[str, Any],
    s64: Mapping[str, Any],
    agents_text: str,
    source_text: str,
) -> list[dict[str, str]]:
    s68_review = _mapping(s68.get("s64_review"))
    s68_safety = _mapping(s68.get("safety"))
    interpretation = _mapping(s64.get("interpretation"))
    instrumentation = _mapping(s64.get("signature_instrumentation"))
    fallback_reasons = _mapping(instrumentation.get("fallback_reasons"))
    probe_safety = _mapping(s64.get("probe_safety"))
    actual_flags = _mapping(probe_safety.get("actual_flags"))
    sensitive = _mapping(probe_safety.get("sensitive_path_comparison"))
    dominant_reason = str(interpretation.get("dominant_reason") or "")
    dominant_count = _int(interpretation.get("dominant_reason_count"))
    total = _int(interpretation.get("fallback_reason_total"))
    fallback_count = _int(fallback_reasons.get("unsupported_or_missing_template_footprint"))
    checks = [
        (
            "s68_completed_and_points_to_template_footprint_strategy",
            s68.get("status") == "completed"
            and s68.get("next_gate") == "prepare_template_footprint_support_strategy_or_review",
        ),
        (
            "s68_review_matches_unsupported_footprint",
            s68_review.get("status") == "completed"
            and s68_review.get("classification") == "unsupported_footprint_dominates"
            and s68_review.get("dominant_reason") == "unsupported_or_missing_template_footprint",
        ),
        (
            "s64_completed_unsupported_footprint_dominates",
            s64.get("status") == "completed"
            and interpretation.get("classification") == "unsupported_footprint_dominates"
            and dominant_reason == "unsupported_or_missing_template_footprint",
        ),
        (
            "fallback_reasons_visible_and_dominant",
            instrumentation.get("fallback_reason_visibility") == "fallback_reason_instrumentation_visible"
            and total > 0
            and dominant_count == total
            and fallback_count == total,
        ),
        (
            "region_counting_attempts_have_nontrivial_fallbacks",
            _int(s68_review.get("mandatory_region_counting_attempts")) > 0
            and _int(s68_review.get("mandatory_region_counting_used")) > 0
            and _int(s68_review.get("mandatory_region_counting_fallbacks")) > 0,
        ),
        ("s68_safety_clean", _s68_safety_clean(s68_safety)),
        (
            "s64_safety_clean",
            all(
                actual_flags.get(key) is False
                for key in (
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
            )
            and sensitive.get("schema") == "phase3b-sensitive-path-fingerprint-comparison/v0"
            and sensitive.get("changed") is False
            and sensitive.get("changed_paths") == []
            and sensitive.get("changed_entries") == [],
        ),
        (
            "source_has_current_footprint_and_region_counting_hooks",
            "_pose_has_template_rect_footprint" in source_text
            and "_mandatory_region_counting_payload" in source_text
            and "_mandatory_region_blocked_counts_for_domain" in source_text
            and "unsupported_pose_footprint" in source_text
            and "unsupported_or_missing_template_footprint" in source_text,
        ),
        (
            "agents_records_s68_gate",
            "Current S68 fallback-reason no-solve probe result" in agents_text
            and "unsupported_footprint_dominates" in agents_text
            and "review-first template-footprint support strategy" in agents_text,
        ),
    ]
    return [
        {"name": name, "status": "passed" if passed else "failed"}
        for name, passed in checks
    ]


def _s68_safety_clean(safety: Mapping[str, Any]) -> bool:
    return (
        safety.get("execute_no_solve") is True
        and safety.get("no_solve") is True
        and all(
            safety.get(key) is False
            for key in (
                "fresh_solver_run_started",
                "cp_solver_solve_called",
                "runtime_execution_performed",
                "main_py_executed",
                "exact_campaign_used",
                "checkpoint_written",
                "proof_source",
                "source_model_mutation",
                "source_mutation_performed",
                "candidate_universe_changed",
                "scheduler_integration",
                "production_profile_changed",
                "sensitive_path_comparison_changed",
                "canonical_checkpoint_state_exists_after",
                "canonical_checkpoint_telemetry_exists_after",
            )
        )
        and safety.get("sensitive_path_schema")
        == "phase3b-sensitive-path-fingerprint-comparison/v0"
        and safety.get("changed_paths") == []
        and safety.get("changed_entries") == []
    )


def _evidence_summary(
    *,
    s68: Mapping[str, Any],
    s64: Mapping[str, Any],
) -> dict[str, Any]:
    probe = _mapping(s68.get("probe"))
    s68_review = _mapping(s68.get("s64_review"))
    instrumentation = _mapping(s64.get("signature_instrumentation"))
    totals = _mapping(instrumentation.get("totals"))
    phases = _mapping(instrumentation.get("phase_seconds"))
    interpretation = _mapping(s64.get("interpretation"))
    fallback_reasons = _mapping(instrumentation.get("fallback_reasons"))
    return {
        "s68_run_id": _mapping(s68.get("probe")).get("run_id"),
        "s68_probe_path": probe.get("overlay_timing_probe_json"),
        "model_build_seconds": probe.get("model_build_seconds"),
        "signature_bucket_tightening_seconds": probe.get("signature_bucket_tightening_seconds"),
        "s64_classification": interpretation.get("classification"),
        "dominant_reason": interpretation.get("dominant_reason"),
        "dominant_reason_count": interpretation.get("dominant_reason_count"),
        "dominant_reason_ratio": interpretation.get("dominant_reason_ratio"),
        "fallback_reason_total": interpretation.get("fallback_reason_total"),
        "fallback_reasons": dict(fallback_reasons),
        "mandatory_scan_seconds": interpretation.get("mandatory_scan_seconds")
        or phases.get("per_anchor_mandatory_scan")
        or s68_review.get("mandatory_scan_seconds"),
        "mandatory_region_counting_attempts": totals.get("mandatory_region_counting_attempts")
        or s68_review.get("mandatory_region_counting_attempts"),
        "mandatory_region_counting_used": totals.get("mandatory_region_counting_used")
        or s68_review.get("mandatory_region_counting_used"),
        "mandatory_region_counting_fallbacks": totals.get("mandatory_region_counting_fallbacks")
        or s68_review.get("mandatory_region_counting_fallbacks"),
        "required_optional_payload_count": totals.get("required_optional_payload_count"),
        "top_fallback_entries": list(instrumentation.get("top_fallback_entries", []) or [])[:10],
        "safety": {
            "execute_no_solve": _mapping(s68.get("safety")).get("execute_no_solve"),
            "cp_solver_solve_called": _mapping(s68.get("safety")).get("cp_solver_solve_called"),
            "runtime_execution_performed": _mapping(s68.get("safety")).get(
                "runtime_execution_performed"
            ),
            "checkpoint_written": _mapping(s68.get("safety")).get("checkpoint_written"),
            "proof_source": _mapping(s68.get("safety")).get("proof_source"),
            "sensitive_path_comparison_changed": _mapping(s68.get("safety")).get(
                "sensitive_path_comparison_changed"
            ),
        },
    }


def _future_patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": TARGET_METHOD,
        "env_var": ENV_VAR,
        "current_signature_instrumentation_env_var": CURRENT_SIGNATURE_INSTRUMENTATION_ENV_VAR,
        "current_region_counting_env_var": CURRENT_REGION_COUNTING_ENV_VAR,
        "current_fallback_instrumentation_env_var": CURRENT_FALLBACK_INSTRUMENTATION_ENV_VAR,
        "enabled_scope": (
            "extend mandatory region-counting support only for template/pose footprint metadata "
            "that can be proven equivalent to the legacy pose-footprint blocked-count semantics"
        ),
        "exactness_contract": (
            "enabled support may replace fallback only when every counted pose footprint is proven "
            "as an exact integer rectangle/bounds equivalent to the legacy pose-footprint "
            "occupied-cell scan; otherwise the existing legacy fallback remains mandatory"
        ),
        "default_off_contract": [
            f"`{ENV_VAR}` unset or false preserves the current S62/S68 behavior and creates no new default output.",
            "Default-off ModelProto, variables, constraints, build_stats, candidate order, and scheduler/proof inputs remain unchanged.",
            "Invalid env values should fail fast and mention the env var name.",
        ],
        "review_questions": [
            "Is S68/S64 sufficient evidence that unsupported_or_missing_template_footprint dominates residual mandatory fallback?",
            "Is the proposed default-off template-footprint support scope narrow enough to request user/project-owner authorization later?",
            "Does the exactness contract preserve legacy pose-footprint blocked-count semantics?",
            "Is fallback-to-legacy sufficient for non-rectangular, overlapping, missing, rotated, or otherwise unproven geometry?",
            "Are the proposed tests enough to prove no default-off delta and enabled equivalence to legacy constraints/proto?",
        ],
        "validation_plan": [
            "default-off and false env preserve current S62 behavior, ModelProto text, variable count, constraint count, and constraint type counts",
            "enabled supported fixtures produce the same blocked counts and generated constraints as the legacy scan",
            "unsupported/non-proven geometry still falls back to legacy scan and remains proto/build_stats equivalent except explicit diagnostics",
            "fallback reason counters show unsupported_or_missing_template_footprint decreases only when support is proven",
            "required-optional path remains unchanged",
            "exact-core overlay path exposes diagnostics but keeps proto and constraints equal to baseline",
        ],
        "non_goals": [
            "no source mutation in S69/S70",
            "no second enabled 42x32 probe in S69/S70",
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
            "check": "submit S70 package for review; request user/project-owner authorization only if review passes",
        },
        {
            "id": "default_off_no_delta",
            "check": "later implementation must preserve current default-off S62 behavior and ModelProto/build_stats outputs",
        },
        {
            "id": "enabled_exact_equivalence",
            "check": "enabled support must prove exact blocked-count equivalence to the legacy occupied-cell scan for covered fixtures",
        },
        {
            "id": "legacy_fallback_for_unproven_geometry",
            "check": "non-rectangular or otherwise unproven footprint geometry must continue to use legacy scan",
        },
        {
            "id": "no_proof_or_checkpoint_integration",
            "check": "no scheduler, proof, checkpoint, preflight, release, viewer, frontdoor, or production-default integration",
        },
    ]


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "69_signature_bucket_template_footprint_support_strategy" not in normalized
    ):
        raise ValueError(
            f"Refusing to write outside S69 template-footprint support strategy namespace: {path}"
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

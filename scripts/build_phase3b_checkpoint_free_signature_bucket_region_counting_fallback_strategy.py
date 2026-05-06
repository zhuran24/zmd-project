from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_S51 = (
    ARTIFACT_ROOT
    / "51_signature_bucket_mandatory_region_counting_implementation"
    / "s51_signature_bucket_mandatory_region_counting_implementation.json"
)
DEFAULT_S53 = (
    ARTIFACT_ROOT
    / "53_signature_bucket_mandatory_region_counting_probe_review"
    / "signature_bucket_mandatory_region_counting_probe_review.json"
)
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
DEFAULT_AGENTS = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "60_signature_bucket_region_counting_fallback_strategy"

ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
CURRENT_REGION_COUNTING_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
CURRENT_SIGNATURE_INSTRUMENTATION_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
TARGET_CLASSIFICATION = "mandatory_region_counting_effective_but_fallback_residual_strategy_required"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_region_counting_fallback_strategy(
        s51_path=_resolve_path(PROJECT_ROOT, args.s51),
        s53_path=_resolve_path(PROJECT_ROOT, args.s53),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        agents_path=_resolve_path(PROJECT_ROOT, args.agents),
        source_path=_resolve_path(PROJECT_ROOT, args.source),
    )
    print("phase3b signature bucket region-counting fallback strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_region_counting_fallback_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the S60 residual fallback strategy after the S59 mandatory "
            "region-counting no-solve probe."
        )
    )
    parser.add_argument("--s51", type=Path, default=DEFAULT_S51)
    parser.add_argument("--s53", type=Path, default=DEFAULT_S53)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_region_counting_fallback_strategy(
    *,
    s51_path: Path,
    s53_path: Path,
    probe_path: Path,
    agents_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    s51 = _load_json(s51_path)
    s53 = _load_json(s53_path)
    probe = _load_json(probe_path)
    agents_text = Path(agents_path).read_text(encoding="utf-8")
    source_text = Path(source_path).read_text(encoding="utf-8")
    checks = _classify_inputs(
        s51=s51,
        s53=s53,
        probe=probe,
        agents_text=agents_text,
        source_text=source_text,
    )
    completed = all(check["status"] == "passed" for check in checks)
    classification = TARGET_CLASSIFICATION if completed else "manual_review_required"
    evidence = _evidence_summary(s51=s51, s53=s53, probe=probe)
    return {
        "schema": "phase3b-signature-bucket-region-counting-fallback-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "strategy_kind": "review_first_residual_fallback_reason_instrumentation_no_source_mutation",
        "inputs": {
            "s51_implementation": str(s51_path),
            "s53_probe_review": str(s53_path),
            "s59_probe": str(probe_path),
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
                "S59 proves mandatory region counting is effective, but the remaining "
                "mandatory scan is still dominated by fallback/legacy scan work. The next "
                "safe step is review of default-off fallback-reason instrumentation before "
                "attempting any broader optimization."
                if completed
                else "S51/S53/S59 inputs or source context are not in the expected clean residual-fallback state."
            ),
        },
        "evidence_summary": evidence,
        "future_patch_spec": _future_patch_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_region_counting_fallback_external_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S61 external review package before requesting fallback-instrumentation authorization"
                if completed
                else "inspect S51/S53/S59/source inputs manually"
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


def write_signature_bucket_region_counting_fallback_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_region_counting_fallback_strategy.json"
    md_path = output_dir / "signature_bucket_region_counting_fallback_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_signature_bucket_region_counting_fallback_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_signature_bucket_region_counting_fallback_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    interpretation = _mapping(strategy.get("interpretation"))
    evidence = _mapping(strategy.get("evidence_summary"))
    spec = _mapping(strategy.get("future_patch_spec"))
    lines = [
        "# Phase3B S60 Signature Bucket Region-Counting Fallback Strategy",
        "",
        f"- Status: `{strategy.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Review required before authorization: `true`",
        "",
        "## Evidence",
        "",
        f"- Baseline mandatory scan seconds: `{_fmt(evidence.get('baseline_mandatory_scan_seconds'))}`",
        f"- Current mandatory scan seconds: `{_fmt(evidence.get('current_mandatory_scan_seconds'))}`",
        f"- Mandatory scan speedup ratio: `{_fmt(evidence.get('mandatory_scan_speedup_ratio'))}`",
        f"- Region counting used ratio: `{_fmt(evidence.get('region_counting_used_ratio'))}`",
        f"- Region counting fallback ratio: `{_fmt(evidence.get('region_counting_fallback_ratio'))}`",
        f"- Mandatory region-counting attempts: `{evidence.get('mandatory_region_counting_attempts')}`",
        f"- Mandatory region-counting used: `{evidence.get('mandatory_region_counting_used')}`",
        f"- Mandatory region-counting fallbacks: `{evidence.get('mandatory_region_counting_fallbacks')}`",
        f"- Required-optional payload count: `{evidence.get('required_optional_payload_count')}`",
        "",
        "## Future Patch Spec",
        "",
        f"- Env gate: `{spec.get('env_var')}`",
        f"- Target method: `{spec.get('target_method')}`",
        f"- Enabled scope: `{spec.get('enabled_scope')}`",
        f"- Output contract: `{spec.get('output_contract')}`",
        "",
        "This artifact is review preparation only; it is not authorization and not a source patch.",
        "",
    ]
    return "\n".join(lines)


def _classify_inputs(
    *,
    s51: Mapping[str, Any],
    s53: Mapping[str, Any],
    probe: Mapping[str, Any],
    agents_text: str,
    source_text: str,
) -> list[dict[str, str]]:
    interpretation = _mapping(s53.get("interpretation"))
    instrumentation = _mapping(s53.get("signature_instrumentation"))
    totals = _mapping(instrumentation.get("totals"))
    phases = _mapping(instrumentation.get("phase_seconds"))
    probe_safety = _mapping(s53.get("probe_safety"))
    actual_flags = _mapping(probe_safety.get("actual_flags"))
    attempts = _int(totals.get("mandatory_region_counting_attempts"))
    used = _int(totals.get("mandatory_region_counting_used"))
    fallbacks = _int(totals.get("mandatory_region_counting_fallbacks"))
    current_scan = _float(phases.get("per_anchor_mandatory_scan"))
    baseline_scan = _float(interpretation.get("baseline_mandatory_scan_seconds"))
    checks = [
        ("s51_implemented_and_verified", s51.get("status") == "implemented_and_verified"),
        (
            "s53_completed_effective",
            s53.get("status") == "completed"
            and interpretation.get("classification") == "mandatory_region_counting_effective",
        ),
        (
            "s59_probe_completed_no_solve",
            probe.get("status") == "completed"
            and probe.get("execute_no_solve") is True
            and probe.get("cp_solver_solve_called") is False,
        ),
        (
            "region_counting_effective_but_fallback_nontrivial",
            attempts > 0 and used > 0 and fallbacks > 0 and used > fallbacks,
        ),
        (
            "residual_mandatory_scan_nontrivial",
            current_scan is not None
            and baseline_scan is not None
            and current_scan > 5.0
            and current_scan < baseline_scan,
        ),
        (
            "required_optional_inactive",
            _int(totals.get("required_optional_payload_count")) == 0
            and _float(phases.get("per_anchor_required_optional_scan")) == 0.0,
        ),
        (
            "s53_safety_clean",
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
            and _mapping(probe_safety.get("sensitive_path_comparison")).get("changed") is False
            and _mapping(probe_safety.get("sensitive_path_comparison")).get("changed_paths") == [],
        ),
        (
            "source_has_region_counting_and_fallback_paths",
            "_mandatory_region_counting_payload" in source_text
            and "_mandatory_region_blocked_counts_for_domain" in source_text
            and "mandatory_region_counting_fallbacks" in source_text
            and "for cell in domain.get(\"cells\", [])" in source_text,
        ),
        (
            "agents_records_s59_gate",
            "Current S59 enabled no-solve probe result" in agents_text
            and "mandatory_region_counting_effective" in agents_text,
        ),
    ]
    return [
        {"name": name, "status": "passed" if passed else "failed"}
        for name, passed in checks
    ]


def _evidence_summary(
    *,
    s51: Mapping[str, Any],
    s53: Mapping[str, Any],
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    interpretation = _mapping(s53.get("interpretation"))
    instrumentation = _mapping(s53.get("signature_instrumentation"))
    totals = _mapping(instrumentation.get("totals"))
    phases = _mapping(instrumentation.get("phase_seconds"))
    wrapper = _mapping(s53.get("wrapper_timing"))
    attempts = _int(totals.get("mandatory_region_counting_attempts"))
    used = _int(totals.get("mandatory_region_counting_used"))
    fallbacks = _int(totals.get("mandatory_region_counting_fallbacks"))
    baseline_scan = _float(interpretation.get("baseline_mandatory_scan_seconds"))
    current_scan = _float(phases.get("per_anchor_mandatory_scan"))
    return {
        "s51_env_var": _mapping(_mapping(s51.get("source_patch")).get("env_var")).get("name")
        or _mapping(s51.get("source_patch")).get("env_var"),
        "s53_classification": interpretation.get("classification"),
        "s59_run_id": s53.get("run_id"),
        "s59_probe_path": s53.get("probe_path"),
        "model_build_seconds": s53.get("model_build_seconds"),
        "from_exact_core_total_seconds": wrapper.get("from_exact_core_total_seconds"),
        "ghost_constraints_total_seconds": wrapper.get("ghost_constraints_total_seconds"),
        "ghost_signature_bucket_total_seconds": wrapper.get("ghost_signature_bucket_total_seconds"),
        "baseline_mandatory_scan_seconds": baseline_scan,
        "current_mandatory_scan_seconds": current_scan,
        "mandatory_scan_seconds_reduction": (
            baseline_scan - current_scan
            if baseline_scan is not None and current_scan is not None
            else None
        ),
        "mandatory_scan_speedup_ratio": (
            baseline_scan / current_scan
            if baseline_scan is not None and current_scan not in (None, 0.0)
            else None
        ),
        "mandatory_region_counting_attempts": attempts,
        "mandatory_region_counting_used": used,
        "mandatory_region_counting_fallbacks": fallbacks,
        "region_counting_used_ratio": used / attempts if attempts else None,
        "region_counting_fallback_ratio": fallbacks / attempts if attempts else None,
        "mandatory_cells_scanned": totals.get("mandatory_cells_scanned"),
        "mandatory_pose_hits": totals.get("mandatory_pose_hits"),
        "mandatory_unique_blocked_poses": totals.get("mandatory_unique_blocked_poses"),
        "mandatory_region_rectangles_evaluated": totals.get("mandatory_region_rectangles_evaluated"),
        "mandatory_region_overlap_counts": totals.get("mandatory_region_overlap_counts"),
        "mandatory_region_counted_blocked_poses": totals.get("mandatory_region_counted_blocked_poses"),
        "required_optional_payload_count": totals.get("required_optional_payload_count"),
        "required_optional_cells_scanned": totals.get("required_optional_cells_scanned"),
        "phase_seconds": dict(phases),
        "top_slow_entries": list(instrumentation.get("top_slow_entries", []) or [])[:10],
        "probe_safety_flags": {
            "execute_no_solve": probe.get("execute_no_solve"),
            "cp_solver_solve_called": probe.get("cp_solver_solve_called"),
            "checkpoint_written": probe.get("checkpoint_written"),
            "proof_source": probe.get("proof_source"),
            "runtime_execution_performed": probe.get("runtime_execution_performed"),
            "sensitive_path_comparison": probe.get("sensitive_path_comparison"),
        },
    }


def _future_patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": TARGET_METHOD,
        "env_var": ENV_VAR,
        "current_region_counting_env_var": CURRENT_REGION_COUNTING_ENV_VAR,
        "current_signature_instrumentation_env_var": CURRENT_SIGNATURE_INSTRUMENTATION_ENV_VAR,
        "enabled_scope": (
            "collect compact, bounded fallback-reason diagnostics for mandatory "
            "region-counting attempts that fall back to the legacy scan"
        ),
        "output_contract": (
            "when enabled alongside signature tightening instrumentation, publish "
            "fallback_reasons and top_fallback_entries under signature_tightening_instrumentation; "
            "when disabled, create no new key"
        ),
        "fallback_reason_categories": [
            "missing_compact_bucket_regions",
            "overlapping_same_bucket_regions",
            "unsupported_or_missing_template_footprint",
            "missing_bucket_region_metadata",
            "region_counting_guard_rejected",
            "legacy_scan_required_other",
        ],
        "top_fallback_entry_fields": [
            "rect_idx",
            "anchor",
            "group_id_or_template",
            "bucket_id",
            "reason",
            "legacy_scan_count",
            "legacy_pose_hits",
            "elapsed_seconds",
        ],
        "default_off_contract": [
            f"`{ENV_VAR}` unset or false creates no new instrumentation key.",
            "Default-off ModelProto, variables, constraints, and build_stats remain unchanged.",
            "Invalid env values should fail fast and mention the env var name.",
        ],
        "enabled_safety_contract": [
            "No changes to region-counting decisions or legacy fallback behavior.",
            "No candidate-universe, scheduler, proof, checkpoint, preflight, release, viewer, or frontdoor integration.",
            "Diagnostics must be bounded: counters plus at most top-N fallback entries, not per-event logs.",
        ],
        "non_goals": [
            "no source mutation in S60/S61",
            "no optimization behavior change in the proposed instrumentation patch",
            "no second enabled 42x32 probe in S60/S61",
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
            "check": "submit S61 package for review; request user/project-owner authorization only if review passes",
        },
        {
            "id": "default_off_no_delta",
            "check": "after later authorization/implementation, env unset and false preserve current S51 behavior and output",
        },
        {
            "id": "enabled_stats_only",
            "check": "enabled fallback instrumentation only adds bounded diagnostics under existing signature instrumentation output",
        },
        {
            "id": "reason_coverage",
            "check": "fixture tests cover missing regions, overlapping regions, unsupported footprints, and guard-rejected fallback reasons",
        },
        {
            "id": "no_proto_delta",
            "check": "enabled fallback instrumentation preserves ModelProto text, variable count, constraint count, and constraint type distribution",
        },
    ]


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "60_signature_bucket_region_counting_fallback_strategy" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S60 region-counting fallback strategy namespace: {path}")


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

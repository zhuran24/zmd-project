from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_S41 = (
    ARTIFACT_ROOT
    / "41_signature_bucket_instrumentation_implementation"
    / "s41_signature_bucket_instrumentation_implementation.json"
)
DEFAULT_S42 = (
    ARTIFACT_ROOT
    / "42_signature_bucket_enabled_no_solve_probe_readiness"
    / "signature_bucket_enabled_no_solve_probe_readiness.json"
)
DEFAULT_S43 = (
    ARTIFACT_ROOT
    / "43_signature_bucket_enabled_no_solve_probe_review"
    / "signature_bucket_enabled_no_solve_probe_review.json"
)
DEFAULT_AGENTS = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "44_signature_bucket_visibility_path_strategy"

ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
NORMAL_FINALIZATION_METHOD = "CoordinateExactMasterDelegate._add_global_valid_inequalities"
OVERLAY_FACTORY = "MasterPlacementModel.from_exact_core"
COLLECTION_STATS_PATH = (
    "_ghost_anchor_signature_bucket_tightening_stats.signature_tightening_instrumentation"
)
FINAL_BUILD_STATS_PATH = (
    "build_stats.global_valid_inequalities.signature_bucket_capacity_bounds."
    "signature_tightening_instrumentation"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_visibility_path_strategy(
        s41_path=_resolve_path(PROJECT_ROOT, args.s41),
        s42_path=_resolve_path(PROJECT_ROOT, args.s42),
        s43_path=_resolve_path(PROJECT_ROOT, args.s43),
        agents_path=_resolve_path(PROJECT_ROOT, args.agents),
    )
    print("phase3b signature bucket visibility path strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_visibility_path_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the S44 strategy/spec for the S43 signature-bucket "
            "instrumentation visibility gap on the exact-core overlay path."
        )
    )
    parser.add_argument("--s41", type=Path, default=DEFAULT_S41)
    parser.add_argument("--s42", type=Path, default=DEFAULT_S42)
    parser.add_argument("--s43", type=Path, default=DEFAULT_S43)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_visibility_path_strategy(
    *,
    s41_path: Path,
    s42_path: Path,
    s43_path: Path,
    agents_path: Path,
) -> dict[str, Any]:
    s41 = _load_json(s41_path)
    s42 = _load_json(s42_path)
    s43 = _load_json(s43_path)
    agents_text = Path(agents_path).read_text(encoding="utf-8")
    checks = _classify_inputs(s41=s41, s42=s42, s43=s43, agents_text=agents_text)
    completed = all(check["status"] == "passed" for check in checks)
    classification = (
        "exact_core_overlay_instrumentation_visibility_gap"
        if completed
        else "manual_review_required"
    )
    return {
        "schema": "phase3b-signature-bucket-visibility-path-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "strategy_kind": "review_first_visibility_path_patch_spec_no_source_mutation",
        "inputs": {
            "s41_implementation": str(s41_path),
            "s42_readiness": str(s42_path),
            "s43_probe_review": str(s43_path),
            "agents": str(agents_path),
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
                "S43 completed safely with the signature-bucket env enabled, but the "
                "instrumentation key was absent from final build_stats. The likely cause is "
                "that the exact-core overlay path calls _add_ghost_constraints and "
                "_finalize_build_stats without rerunning the normal _add_global_valid_inequalities "
                "companion-copy path."
                if completed
                else "S41/S42/S43 inputs are not in the expected clean visibility-gap state."
            ),
        },
        "evidence_summary": _evidence_summary(s41=s41, s42=s42, s43=s43),
        "future_patch_spec": _future_patch_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_visibility_path_external_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S45 external review package before requesting source-patch authorization"
                if completed
                else "inspect S41/S42/S43 inputs manually"
            ),
            "blocked_actions": [
                "do_not_rerun_enabled_42x32_probe",
                "do_not_mutate_src_models_before_external_review_and_user_authorization",
                "do_not_call_add_global_valid_inequalities_from_from_exact_core",
                "do_not_run_runtime_solve",
                "do_not_run_67x20",
                "do_not_run_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }


def write_signature_bucket_visibility_path_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_visibility_path_strategy.json"
    md_path = output_dir / "signature_bucket_visibility_path_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_signature_bucket_visibility_path_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_signature_bucket_visibility_path_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    interpretation = _mapping(strategy.get("interpretation"))
    spec = _mapping(strategy.get("future_patch_spec"))
    evidence = _mapping(strategy.get("evidence_summary"))
    lines = [
        "# Phase3B S44 Signature Bucket Visibility Path Strategy",
        "",
        f"- Status: `{strategy.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Review required before authorization: `true`",
        "",
        "## Evidence",
        "",
        f"- S43 instrumentation present: `{evidence.get('s43_signature_instrumentation_present')}`",
        f"- S43 wrapper signature-bucket seconds: `{_fmt(evidence.get('s43_ghost_signature_bucket_seconds'))}`",
        f"- S43 sensitive path changed: `{evidence.get('s43_sensitive_path_changed')}`",
        "",
        "## Future Patch Spec",
        "",
        f"- Target method: `{spec.get('target_method')}`",
        f"- Normal finalization method: `{spec.get('normal_finalization_method')}`",
        f"- Overlay factory: `{spec.get('exact_core_overlay_factory')}`",
        f"- Proposed overlay-visible copy point: `{spec.get('proposed_overlay_visible_copy_point')}`",
        "",
        "## Rejected Approach",
        "",
        f"- `{spec.get('rejected_approach')}`",
        "",
        "This artifact is review preparation only; it is not authorization and not a source patch.",
        "",
    ]
    return "\n".join(lines)


def _classify_inputs(
    *,
    s41: Mapping[str, Any],
    s42: Mapping[str, Any],
    s43: Mapping[str, Any],
    agents_text: str,
) -> list[dict[str, str]]:
    instrumentation = _mapping(s43.get("signature_instrumentation"))
    probe_safety = _mapping(s43.get("probe_safety"))
    actual_flags = _mapping(probe_safety.get("actual_flags"))
    checks = [
        (
            "s41_implemented_and_verified",
            s41.get("status") == "implemented_and_verified",
        ),
        (
            "s42_readiness_completed",
            s42.get("status") == "completed"
            and _mapping(s42.get("readiness")).get("classification")
            == "ready_for_readiness_review",
        ),
        (
            "s43_completed_inconclusive",
            s43.get("status") == "completed"
            and _mapping(s43.get("interpretation")).get("classification")
            == "instrumentation_inconclusive",
        ),
        (
            "s43_instrumentation_missing",
            instrumentation.get("present") is False
            and instrumentation.get("classification") == "instrumentation_missing",
        ),
        (
            "s43_safety_clean",
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
                    "production_profile_changed",
                )
            )
            and _mapping(probe_safety.get("sensitive_path_comparison")).get("changed")
            is False,
        ),
        (
            "agents_records_s43_gate",
            "Current S43 signature-bucket enabled no-solve probe result" in agents_text,
        ),
    ]
    return [
        {"name": name, "status": "passed" if passed else "failed"}
        for name, passed in checks
    ]


def _evidence_summary(
    *,
    s41: Mapping[str, Any],
    s42: Mapping[str, Any],
    s43: Mapping[str, Any],
) -> dict[str, Any]:
    wrapper = _mapping(s43.get("wrapper_timing"))
    return {
        "s41_env_var": _mapping(s41.get("implementation")).get("env_var"),
        "s41_finalization_scope": _mapping(s41.get("implementation")).get("finalization_scope"),
        "s42_readiness_classification": _mapping(s42.get("readiness")).get("classification"),
        "s43_classification": _mapping(s43.get("interpretation")).get("classification"),
        "s43_signature_instrumentation_present": _mapping(s43.get("signature_instrumentation")).get("present"),
        "s43_model_build_seconds": s43.get("model_build_seconds"),
        "s43_ghost_signature_bucket_seconds": wrapper.get("ghost_signature_bucket_total_seconds"),
        "s43_from_exact_core_seconds": wrapper.get("from_exact_core_total_seconds"),
        "s43_sensitive_path_changed": _mapping(
            _mapping(s43.get("probe_safety")).get("sensitive_path_comparison")
        ).get("changed"),
    }


def _future_patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "related_overlay_file": "src/models/master_model.py",
        "env_var": ENV_VAR,
        "target_method": TARGET_METHOD,
        "normal_finalization_method": NORMAL_FINALIZATION_METHOD,
        "exact_core_overlay_factory": OVERLAY_FACTORY,
        "collection_stats_path": COLLECTION_STATS_PATH,
        "final_build_stats_output_path": FINAL_BUILD_STATS_PATH,
        "proposed_overlay_visible_copy_point": (
            "inside _apply_ghost_anchor_signature_bucket_tightening, after the existing "
            "ghost_conditioned_* count writes to owner.build_stats.global_valid_inequalities."
            "signature_bucket_capacity_bounds"
        ),
        "rejected_approach": (
            "Do not call _add_global_valid_inequalities from MasterPlacementModel.from_exact_core; "
            "that method constructs constraints/stat payloads and could duplicate or change the overlay model."
        ),
        "implementation_outline": [
            "Leave collection in _apply_ghost_anchor_signature_bucket_tightening unchanged.",
            "Leave the normal-build _add_global_valid_inequalities companion copy unchanged.",
            "When instrumentation exists, copy it into the method-local signature_stats dict after the existing ghost-conditioned count writes.",
            "When env is unset/0/false/off/no, do not create signature_tightening_instrumentation anywhere.",
            "Do not add variables, constraints, hints, scheduler inputs, proof inputs, checkpoint writes, or candidate-order changes.",
        ],
        "default_off_contract": [
            f"`{ENV_VAR}` unset or false leaves no instrumentation key.",
            "Default-off ModelProto text, variable count, constraint count, and constraint type distribution remain unchanged.",
            "Default-off final build_stats remain unchanged.",
            "Invalid env values still raise ValueError mentioning the env var name.",
        ],
        "enabled_expected_output": {
            "path": FINAL_BUILD_STATS_PATH,
            "schema_keys": [
                "enabled",
                "phase_seconds",
                "totals",
                "top_slow_entries",
            ],
        },
        "non_goals": [
            "no S43 probe rerun in S44/S45",
            "no runtime solve",
            "no canonical checkpoint write/import/backfill",
            "no proof/preflight/release/viewer/frontdoor mutation",
            "no production default change",
            "no _add_global_valid_inequalities call from from_exact_core",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "external_review_before_authorization",
            "check": "submit S45 package for review; request user/project-owner authorization only if review passes",
        },
        {
            "id": "default_off_no_delta",
            "check": "after later authorization/implementation, env unset and env=0 preserve ModelProto and final build_stats",
        },
        {
            "id": "enabled_overlay_visibility",
            "check": "from_exact_core overlay fixture with env=1 exposes signature_tightening_instrumentation",
        },
        {
            "id": "normal_path_still_visible",
            "check": "normal build fixture with env=1 still exposes instrumentation through _add_global_valid_inequalities",
        },
        {
            "id": "forbid_global_valid_inequalities_overlay_call",
            "check": "tests or static assertion confirm from_exact_core does not call _add_global_valid_inequalities",
        },
    ]


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "44_signature_bucket_visibility_path_strategy" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S44 visibility path strategy namespace: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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

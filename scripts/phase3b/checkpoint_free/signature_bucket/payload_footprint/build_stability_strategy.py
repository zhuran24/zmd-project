from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_S82 = (
    ARTIFACT_ROOT
    / "82_signature_bucket_template_footprint_support_gap_probe_execution"
    / "signature_bucket_template_footprint_support_gap_probe_execution.json"
)
DEFAULT_S80 = (
    ARTIFACT_ROOT
    / "80_signature_bucket_template_footprint_support_gap_probe_review"
    / "signature_bucket_template_footprint_support_gap_probe_review.json"
)
DEFAULT_S81 = (
    ARTIFACT_ROOT
    / "81_signature_bucket_template_footprint_support_gap_probe_external_review_package"
    / "s79_s80_support_gap_probe_review_001"
    / "external_review_reply_summary.json"
)
DEFAULT_S78 = (
    ARTIFACT_ROOT
    / "78_signature_bucket_template_footprint_support_gap_instrumentation_implementation"
    / "s78_signature_bucket_template_footprint_support_gap_instrumentation_implementation.json"
)
DEFAULT_AGENTS = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "83_signature_bucket_payload_footprint_stability_strategy"

TARGET_CLASSIFICATION = "payload_footprint_stability_strategy_required"
DOMINANT_REASON = "unstable_footprint_bounds_within_payload"
FUTURE_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT"
TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_payload_footprint_stability_strategy(
        s82_path=_resolve_path(PROJECT_ROOT, args.s82),
        s80_path=_resolve_path(PROJECT_ROOT, args.s80),
        s81_path=_resolve_path(PROJECT_ROOT, args.s81),
        s78_path=_resolve_path(PROJECT_ROOT, args.s78),
        agents_path=_resolve_path(PROJECT_ROOT, args.agents),
        source_path=_resolve_path(PROJECT_ROOT, args.source),
    )
    print("phase3b signature bucket payload-footprint stability strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_payload_footprint_stability_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S83 after S82/S80 showed all template-footprint support-gap "
            "fallbacks are unstable footprint bounds within a mandatory payload."
        )
    )
    parser.add_argument("--s82", type=Path, default=DEFAULT_S82)
    parser.add_argument("--s80", type=Path, default=DEFAULT_S80)
    parser.add_argument("--s81", type=Path, default=DEFAULT_S81)
    parser.add_argument("--s78", type=Path, default=DEFAULT_S78)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_payload_footprint_stability_strategy(
    *,
    s82_path: Path,
    s80_path: Path,
    s81_path: Path,
    s78_path: Path,
    agents_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    s82 = _load_json(s82_path)
    s80 = _load_json(s80_path)
    s81 = _load_json(s81_path)
    s78 = _load_json(s78_path)
    agents_text = Path(agents_path).read_text(encoding="utf-8")
    source_text = Path(source_path).read_text(encoding="utf-8")
    evidence = _evidence_summary(s82=s82, s80=s80)
    checks = _classify_inputs(
        s82=s82,
        s80=s80,
        s81=s81,
        s78=s78,
        agents_text=agents_text,
        source_text=source_text,
        evidence=evidence,
    )
    completed = all(check["status"] == "passed" for check in checks)
    classification = TARGET_CLASSIFICATION if completed else "manual_review_required"
    return {
        "schema": "phase3b-signature-bucket-payload-footprint-stability-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "strategy_kind": "review_first_payload_footprint_stability_no_source_mutation",
        "inputs": {
            "s82_execution": str(s82_path),
            "s80_probe_review": str(s80_path),
            "s81_review_summary": str(s81_path),
            "s78_implementation": str(s78_path),
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
                "S82 safely executed the single enabled 42x32 no-solve support-gap "
                "probe and S80 showed every recorded support-gap fallback is caused "
                "by unstable footprint bounds within the mandatory payload. The next "
                "safe step is external review of a default-off payload-footprint "
                "stability patch proposal, not an immediate source edit."
                if completed
                else "S82/S80/S81/S78 evidence, AGENTS gate, or source context do not prove a clean unstable-footprint-bounds hotspot."
            ),
        },
        "evidence_summary": evidence,
        "future_patch_spec": _future_patch_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_payload_footprint_stability_external_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S84 external review package for payload-footprint stability support"
                if completed
                else "inspect S82/S80/S81/S78/source inputs manually"
            ),
            "blocked_actions": [
                "do_not_patch_solver_model_before_external_review_and_project_authorization",
                "do_not_rerun_enabled_42x32_probe",
                "do_not_run_runtime_solve",
                "do_not_run_67x20",
                "do_not_run_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }


def write_signature_bucket_payload_footprint_stability_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_payload_footprint_stability_strategy.json"
    md_path = output_dir / "signature_bucket_payload_footprint_stability_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_signature_bucket_payload_footprint_stability_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_signature_bucket_payload_footprint_stability_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    interpretation = _mapping(strategy.get("interpretation"))
    evidence = _mapping(strategy.get("evidence_summary"))
    spec = _mapping(strategy.get("future_patch_spec"))
    return "\n".join(
        [
            "# Phase3B S83 Signature Bucket Payload-Footprint Stability Strategy",
            "",
            f"- Status: `{strategy.get('status')}`",
            f"- Classification: `{interpretation.get('classification')}`",
            "- Source mutation performed: `false`",
            "- Implementation allowed now: `false`",
            "- Review required before authorization: `true`",
            "",
            "## Evidence",
            "",
            f"- S80 classification: `{evidence.get('s80_classification')}`",
            f"- Dominant reason: `{evidence.get('dominant_gap_reason')}`",
            f"- Dominant count: `{evidence.get('dominant_gap_count')}`",
            f"- Dominant ratio: `{_fmt(evidence.get('dominant_gap_ratio'))}`",
            f"- Template support used: `{evidence.get('template_footprint_support_used')}`",
            f"- Template support fallbacks: `{evidence.get('template_footprint_support_fallbacks')}`",
            f"- Current mandatory scan seconds: `{_fmt(evidence.get('current_mandatory_scan_seconds'))}`",
            "",
            "## Future Patch Spec For Review",
            "",
            f"- Env gate: `{spec.get('env_var')}`",
            f"- Target method: `{spec.get('target_method')}`",
            f"- Proposed behavior: `{spec.get('enabled_scope')}`",
            "",
            "This artifact is strategy/review preparation only; it is not authorization and not a source patch.",
            "",
        ]
    )


def _classify_inputs(
    *,
    s82: Mapping[str, Any],
    s80: Mapping[str, Any],
    s81: Mapping[str, Any],
    s78: Mapping[str, Any],
    agents_text: str,
    source_text: str,
    evidence: Mapping[str, Any],
) -> list[dict[str, str]]:
    s80_safety = _mapping(s80.get("probe_safety"))
    actual_flags = _mapping(s80_safety.get("actual_flags"))
    sensitive = _mapping(s80_safety.get("sensitive_path_comparison"))
    checks = [
        (
            "s81_review_passed_not_authorization",
            s81.get("review_verdict") == "pass"
            and s81.get("review_is_authorization") is False
            and s81.get("authorization_required_next") is True,
        ),
        (
            "s82_probe_completed_clean",
            s82.get("status") == "completed"
            and s82.get("probe_status") == "completed"
            and _mapping(s82.get("safety")).get("sensitive_path_comparison", {}).get("changed") is False
            and all(_mapping(s82.get("safety")).get(key) is False for key in _S82_SAFETY_FLAGS),
        ),
        (
            "s80_classification_unstable_bounds",
            s80.get("status") == "completed"
            and _mapping(s80.get("interpretation")).get("classification") == "unstable_footprint_bounds_dominates"
            and evidence.get("dominant_gap_reason") == DOMINANT_REASON
            and _float(evidence.get("dominant_gap_ratio")) == 1.0,
        ),
        (
            "support_gap_counts_match",
            _int(evidence.get("dominant_gap_count")) > 0
            and _int(evidence.get("dominant_gap_count")) == _int(evidence.get("template_footprint_support_fallbacks"))
            and _int(evidence.get("template_footprint_support_used")) == 0,
        ),
        (
            "s80_safety_clean",
            s80_safety.get("status_completed") is True
            and s80_safety.get("run_id_matches") is True
            and s80_safety.get("candidate_key_42x32") is True
            and s80_safety.get("execute_no_solve") is True
            and s80_safety.get("hard_boundary_flags_literal_false") is True
            and all(actual_flags.get(key) is False for key in _HARD_BOUNDARY_FLAGS)
            and sensitive.get("schema") == "phase3b-sensitive-path-fingerprint-comparison/v0"
            and sensitive.get("changed") is False
            and sensitive.get("changed_paths") == []
            and sensitive.get("changed_entries") == [],
        ),
        (
            "s78_implemented_gap_instrumentation",
            s78.get("status") == "implemented_and_verified"
            and "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION"
            in json.dumps(s78, sort_keys=True),
        ),
        (
            "source_has_support_gap_and_template_support_hooks",
            "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION" in source_text
            and "template_footprint_support_gap_reasons" in source_text
            and "unstable_footprint_bounds_within_payload" in source_text,
        ),
        (
            "agents_records_s82_gate",
            "S82" in agents_text
            and "unstable_footprint_bounds_dominates" in agents_text
            and "payload-footprint stability" in agents_text,
        ),
    ]
    return [{"name": name, "status": "passed" if passed else "failed"} for name, passed in checks]


def _evidence_summary(*, s82: Mapping[str, Any], s80: Mapping[str, Any]) -> dict[str, Any]:
    interpretation = _mapping(s80.get("interpretation"))
    signature = _mapping(s80.get("signature_instrumentation"))
    reasons = _mapping(signature.get("support_gap_reasons"))
    return {
        "s82_run_id": s82.get("run_id"),
        "s82_probe_path": s82.get("probe_path"),
        "s80_review_path": s82.get("review_path"),
        "s80_classification": interpretation.get("classification"),
        "model_build_seconds": s80.get("model_build_seconds"),
        "baseline_mandatory_scan_seconds": interpretation.get("baseline_mandatory_scan_seconds"),
        "current_mandatory_scan_seconds": interpretation.get("current_mandatory_scan_seconds"),
        "mandatory_scan_reduction_ratio": interpretation.get("mandatory_scan_reduction_ratio"),
        "template_footprint_support_attempts": interpretation.get("template_footprint_support_attempts"),
        "template_footprint_support_used": interpretation.get("template_footprint_support_used"),
        "template_footprint_support_fallbacks": interpretation.get("template_footprint_support_fallbacks"),
        "dominant_gap_reason": interpretation.get("dominant_gap_reason"),
        "dominant_gap_count": interpretation.get("dominant_gap_count"),
        "dominant_gap_ratio": interpretation.get("dominant_gap_ratio"),
        "support_gap_reasons": dict(reasons),
        "top_support_gap_entries": list(signature.get("top_support_gap_entries", []) or [])[:10],
    }


def _future_patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": TARGET_METHOD,
        "env_var": FUTURE_ENV_VAR,
        "enabled_scope": (
            "when mandatory region-counting is already enabled and payload poses have multiple "
            "individually rectangular but payload-unstable footprint bounds, split/count by "
            "proven-stable footprint-bound cohorts instead of rejecting the whole payload"
        ),
        "default_off_contract": [
            f"`{FUTURE_ENV_VAR}` unset or false preserves S82/S71/S78 behavior and build_stats.",
            "Enabled path must only replace blocked-count computation when equivalence to legacy occupied-cell overlap is proven.",
            "Unsupported, mixed, missing, or overlapping metadata must continue to use legacy scan.",
            "Invalid env values fail fast and mention the env var name.",
        ],
        "proposed_algorithm": [
            "derive per-pose relative rectangular footprint bounds using the existing S71 support proof",
            "partition a mandatory payload by identical footprint bounds only for counting, not for constraint semantics",
            "for each stable cohort, apply the existing exact bucket-region overlap counting formula using that cohort's bounds",
            "sum cohort blocked counts per bucket and compare against the same legacy capacity threshold",
            "fallback to legacy scan whenever cohort partitioning cannot prove exact equivalence",
        ],
        "diagnostics_when_existing_instrumentation_enabled": [
            "payload_footprint_stability_attempts",
            "payload_footprint_stability_used",
            "payload_footprint_stability_fallbacks",
            "payload_footprint_stability_cohorts",
            "top_payload_footprint_stability_entries",
        ],
        "review_questions": [
            "Does cohorting by identical relative footprint bounds preserve exact blocked bucket counts?",
            "Is summing cohort overlap counts equivalent to the legacy per-cell/per-pose-hit scan for covered geometry?",
            "Is fallback-to-legacy sufficient when any proof obligation fails?",
            "Can the patch remain default-off and avoid ModelProto, constraint, scheduler, proof, checkpoint, and production-default changes?",
            "Are the proposed tests sufficient to prove default-off no-delta and enabled proto/constraint equivalence?",
        ],
        "non_goals": [
            "no source mutation in S83/S84",
            "no new enabled 42x32 probe in S83/S84",
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
            "check": "submit S84 package for review; only after pass may offline/user authorization cover a future default-off source patch",
        },
        {
            "id": "default_off_no_delta",
            "check": "future patch must preserve default-off ModelProto text, constraints, build_stats, and region-counting decisions",
        },
        {
            "id": "enabled_equivalence",
            "check": "enabled cohort counting must match legacy blocked_counts on multi-footprint rectangular fixtures and exact-core overlays",
        },
        {
            "id": "fallback_on_unproven_geometry",
            "check": "any unproven footprint, missing metadata, overlap, or guard rejection must keep the legacy scan",
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

_S82_SAFETY_FLAGS = (
    "cp_solver_solve_called",
    "runtime_execution_performed",
    "main_py_executed",
    "exact_campaign_used",
    "checkpoint_written",
    "proof_source",
)


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "83_signature_bucket_payload_footprint_stability_strategy" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S83 payload-footprint stability strategy namespace: {path}")


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

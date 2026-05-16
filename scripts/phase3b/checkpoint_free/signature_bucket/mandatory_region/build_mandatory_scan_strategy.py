from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_S46 = (
    ARTIFACT_ROOT
    / "46_signature_bucket_visibility_path_patch_implementation"
    / "s46_signature_bucket_visibility_path_patch_implementation.json"
)
DEFAULT_S48 = (
    ARTIFACT_ROOT
    / "48_signature_bucket_visibility_probe_review"
    / "signature_bucket_visibility_probe_review.json"
)
DEFAULT_AGENTS = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "49_signature_bucket_mandatory_scan_strategy"

ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
CURRENT_INSTRUMENTATION_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
TARGET_CLASSIFICATION = "mandatory_signature_bucket_region_counting_strategy_required"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_signature_bucket_mandatory_scan_strategy(
        s46_path=_resolve_path(PROJECT_ROOT, args.s46),
        s48_path=_resolve_path(PROJECT_ROOT, args.s48),
        agents_path=_resolve_path(PROJECT_ROOT, args.agents),
        source_path=_resolve_path(PROJECT_ROOT, args.source),
    )
    print("phase3b signature bucket mandatory scan strategy")
    print(f"status={strategy['status']}")
    print(f"classification={strategy['interpretation']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_mandatory_scan_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if strategy["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the S49 strategy/spec for the S48 mandatory signature-bucket "
            "scan hotspot without mutating solver/model source."
        )
    )
    parser.add_argument("--s46", type=Path, default=DEFAULT_S46)
    parser.add_argument("--s48", type=Path, default=DEFAULT_S48)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_mandatory_scan_strategy(
    *,
    s46_path: Path,
    s48_path: Path,
    agents_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    s46 = _load_json(s46_path)
    s48 = _load_json(s48_path)
    agents_text = Path(agents_path).read_text(encoding="utf-8")
    source_text = Path(source_path).read_text(encoding="utf-8")
    checks = _classify_inputs(
        s46=s46,
        s48=s48,
        agents_text=agents_text,
        source_text=source_text,
    )
    completed = all(check["status"] == "passed" for check in checks)
    classification = TARGET_CLASSIFICATION if completed else "manual_review_required"
    return {
        "schema": "phase3b-signature-bucket-mandatory-scan-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "strategy_kind": "review_first_mandatory_scan_region_count_patch_spec_no_source_mutation",
        "inputs": {
            "s46_implementation": str(s46_path),
            "s48_probe_review": str(s48_path),
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
                "S48 made the S46 visibility path observable and classified the hotspot "
                "as mandatory scan dominated. The current mandatory path scans ghost-domain "
                "cells and per-cell pose hits even though compact SignatureRegion metadata "
                "already exists for signature buckets."
                if completed
                else "S46/S48 inputs or source context are not in the expected clean mandatory-scan state."
            ),
        },
        "evidence_summary": _evidence_summary(s46=s46, s48=s48),
        "future_patch_spec": _future_patch_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_mandatory_scan_region_count_external_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S50 external review package before requesting source-patch authorization"
                if completed
                else "inspect S46/S48/source inputs manually"
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


def write_signature_bucket_mandatory_scan_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_strategy_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_mandatory_scan_strategy.json"
    md_path = output_dir / "signature_bucket_mandatory_scan_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_signature_bucket_mandatory_scan_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_signature_bucket_mandatory_scan_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    interpretation = _mapping(strategy.get("interpretation"))
    evidence = _mapping(strategy.get("evidence_summary"))
    spec = _mapping(strategy.get("future_patch_spec"))
    lines = [
        "# Phase3B S49 Signature Bucket Mandatory Scan Strategy",
        "",
        f"- Status: `{strategy.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Review required before authorization: `true`",
        "",
        "## Evidence",
        "",
        f"- Dominant phase: `{evidence.get('dominant_phase')}`",
        f"- Dominant seconds: `{_fmt(evidence.get('dominant_phase_seconds'))}`",
        f"- Dominant fraction: `{_fmt(evidence.get('dominant_phase_fraction'))}`",
        f"- Mandatory cells scanned: `{evidence.get('mandatory_cells_scanned')}`",
        f"- Mandatory pose hits: `{evidence.get('mandatory_pose_hits')}`",
        f"- Required-optional cells scanned: `{evidence.get('required_optional_cells_scanned')}`",
        "",
        "## Future Patch Spec",
        "",
        f"- Env gate: `{spec.get('env_var')}`",
        f"- Target method: `{spec.get('target_method')}`",
        f"- Enabled scope: `{spec.get('enabled_scope')}`",
        f"- Fallback: `{spec.get('fallback_contract')}`",
        "",
        "This artifact is review preparation only; it is not authorization and not a source patch.",
        "",
    ]
    return "\n".join(lines)


def _classify_inputs(
    *,
    s46: Mapping[str, Any],
    s48: Mapping[str, Any],
    agents_text: str,
    source_text: str,
) -> list[dict[str, str]]:
    interpretation = _mapping(s48.get("interpretation"))
    instrumentation = _mapping(s48.get("signature_instrumentation"))
    totals = _mapping(instrumentation.get("totals"))
    probe_safety = _mapping(s48.get("probe_safety"))
    actual_flags = _mapping(probe_safety.get("actual_flags"))
    checks = [
        (
            "s46_implemented_and_verified",
            s46.get("status") == "implemented_and_verified",
        ),
        (
            "s48_completed_mandatory_scan_hotspot",
            s48.get("status") == "completed"
            and interpretation.get("classification") == "mandatory_scan_hotspot"
            and interpretation.get("dominant_phase") == "per_anchor_mandatory_scan",
        ),
        (
            "s48_instrumentation_visible",
            instrumentation.get("present") is True
            and instrumentation.get("visibility_status") == "instrumentation_visible",
        ),
        (
            "required_optional_inactive",
            int(totals.get("required_optional_cells_scanned", -1)) == 0
            and int(totals.get("required_optional_bucket_reductions", -1)) == 0,
        ),
        (
            "mandatory_scan_nontrivial",
            int(totals.get("mandatory_cells_scanned", 0)) > 0
            and int(totals.get("mandatory_pose_hits", 0)) > 0,
        ),
        (
            "s48_safety_clean",
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
            "source_has_region_metadata_and_legacy_scan",
            "class SignatureRegion" in source_text
            and "_mandatory_group_bucket_regions" in source_text
            and "for cell in domain.get(\"cells\", [])" in source_text
            and "blocked_pose_indices" in source_text,
        ),
        (
            "agents_records_s48_gate",
            "Current S48 signature-bucket visibility probe result" in agents_text,
        ),
    ]
    return [
        {"name": name, "status": "passed" if passed else "failed"}
        for name, passed in checks
    ]


def _evidence_summary(*, s46: Mapping[str, Any], s48: Mapping[str, Any]) -> dict[str, Any]:
    instrumentation = _mapping(s48.get("signature_instrumentation"))
    totals = _mapping(instrumentation.get("totals"))
    phases = _mapping(instrumentation.get("phase_seconds"))
    wrapper = _mapping(s48.get("wrapper_timing"))
    return {
        "s46_env_var": _mapping(s46.get("source_patch")).get("env_var"),
        "s48_classification": _mapping(s48.get("interpretation")).get("classification"),
        "s48_model_build_seconds": s48.get("model_build_seconds"),
        "s48_ghost_signature_bucket_seconds": wrapper.get("ghost_signature_bucket_total_seconds"),
        "dominant_phase": instrumentation.get("dominant_phase"),
        "dominant_phase_seconds": instrumentation.get("dominant_phase_seconds"),
        "dominant_phase_fraction": instrumentation.get("dominant_phase_fraction"),
        "mandatory_payload_count": totals.get("mandatory_payload_count"),
        "required_optional_payload_count": totals.get("required_optional_payload_count"),
        "mandatory_cells_scanned": totals.get("mandatory_cells_scanned"),
        "mandatory_pose_hits": totals.get("mandatory_pose_hits"),
        "mandatory_unique_blocked_poses": totals.get("mandatory_unique_blocked_poses"),
        "mandatory_bucket_reductions": totals.get("mandatory_bucket_reductions"),
        "mandatory_constraints_added": totals.get("mandatory_constraints_added"),
        "required_optional_cells_scanned": totals.get("required_optional_cells_scanned"),
        "required_optional_bucket_reductions": totals.get("required_optional_bucket_reductions"),
        "phase_seconds": dict(phases),
    }


def _future_patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": TARGET_METHOD,
        "env_var": ENV_VAR,
        "current_instrumentation_env_var": CURRENT_INSTRUMENTATION_ENV_VAR,
        "enabled_scope": (
            "replace only the mandatory blocked-count computation inside "
            "_apply_ghost_anchor_signature_bucket_tightening when compact region geometry "
            "can prove exact equivalence"
        ),
        "fallback_contract": "fallback to the legacy per-cell/per-pose-hit scan whenever geometry is unsupported or equivalence cannot be proven",
        "candidate_algorithm": [
            "Use existing SignatureRegion and _mandatory_group_bucket_regions metadata as the candidate compact geometry source.",
            "For each ghost anchor domain and mandatory group bucket, compute exact overlap between the ghost rectangle cells and bucket regions without enumerating per-cell pose hits.",
            "Convert overlap counts into the same blocked_counts per bucket currently produced by the legacy scan.",
            "Only add the same count_var <= conditioned_upper_bound + M*(1-u) constraints as the legacy path would add.",
            "Retain legacy scan as default and as enabled fallback for unsupported geometry.",
        ],
        "default_off_contract": [
            f"`{ENV_VAR}` unset or false leaves the existing legacy scan path unchanged.",
            "Default-off ModelProto text, variable count, constraint count, and constraint type distribution remain unchanged.",
            "Default-off final build_stats remain unchanged except for already-existing diagnostics.",
            "Invalid env values should fail fast and mention the env var name.",
        ],
        "enabled_safety_contract": [
            "No candidate-universe change.",
            "No scheduler integration.",
            "No proof/checkpoint/preflight/release/viewer/frontdoor integration.",
            "No production default change.",
            "Enabled fixtures must prove same blocked counts and same generated constraints as legacy for covered geometries.",
        ],
        "non_goals": [
            "no source mutation in S49/S50",
            "no runtime solve",
            "no 42x32 rerun in S49/S50",
            "no canonical checkpoint write/import/backfill",
            "no proof/preflight/release/viewer/frontdoor mutation",
            "no production default change",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "external_review_before_authorization",
            "check": "submit S50 package for review; request user/project-owner authorization only if review passes",
        },
        {
            "id": "default_off_no_delta",
            "check": "after later authorization/implementation, env unset and false preserve legacy scan, ModelProto, constraints, and build_stats",
        },
        {
            "id": "enabled_equals_legacy_blocked_counts",
            "check": "unit tests compare region-count blocked_counts against legacy per-cell/per-pose-hit scan on rectangular, split-edge, and ring-like bucket regions",
        },
        {
            "id": "enabled_equals_legacy_proto",
            "check": "enabled path produces identical constraints/proto counts to legacy on focused exact-core overlay fixtures",
        },
        {
            "id": "unsupported_geometry_fallback",
            "check": "unsupported compact geometry or missing bucket regions falls back to legacy scan without changing constraints",
        },
    ]


def _assert_strategy_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "49_signature_bucket_mandatory_scan_strategy" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S49 mandatory scan strategy namespace: {path}")


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

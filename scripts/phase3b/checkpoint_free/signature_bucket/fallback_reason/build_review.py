from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import build_sensitive_path_fingerprint  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_READINESS = (
    ARTIFACT_ROOT
    / "63_signature_bucket_fallback_reason_probe_readiness"
    / "signature_bucket_fallback_reason_probe_readiness.json"
)
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "64_signature_bucket_fallback_reason_probe_review"
EXPECTED_RUN_ID = "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001"
SIGNATURE_STATS_PATH = (
    "inventory.build_stats_summary.global_valid_inequalities."
    "signature_bucket_capacity_bounds.signature_tightening_instrumentation"
)
SENSITIVE_PATH_COMPARISON_SCHEMA = "phase3b-sensitive-path-fingerprint-comparison/v0"
NON_SUCCESS_CLASSIFICATIONS = {
    "safety_disqualified",
    "fallback_reason_inconclusive",
    "fallback_reason_instrumentation_missing",
}
HARD_BOUNDARY_FLAGS = (
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
REASON_CLASSIFICATION = {
    "missing_compact_bucket_regions": "compact_region_metadata_missing_dominates",
    "missing_bucket_region_metadata": "compact_region_metadata_missing_dominates",
    "overlapping_same_bucket_regions": "overlapping_region_guard_dominates",
    "unsupported_or_missing_template_footprint": "unsupported_footprint_dominates",
    "region_counting_guard_rejected": "other_guard_failure_dominates",
    "legacy_scan_required_other": "other_guard_failure_dominates",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=PROJECT_ROOT,
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket fallback-reason probe review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['paths']['review_json']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review the future S63-enabled 42x32 no-solve fallback-reason probe "
            "and classify whether S62 explains residual mandatory legacy scan."
        )
    )
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_fallback_reason_probe_review(
    *,
    project_root: Path,
    readiness_path: Path,
    probe_path: Path,
    output_dir: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_review_namespace(output_dir)
    readiness = _load_json(readiness_path)
    probe = _load_json(probe_path)
    current_sensitive = build_sensitive_path_fingerprint(project_root)
    probe_safety = _probe_safety(probe)
    signature_instrumentation = _signature_instrumentation_summary(probe)
    interpretation = _interpretation(
        readiness=readiness,
        probe_safety=probe_safety,
        signature_instrumentation=signature_instrumentation,
    )
    classification = str(interpretation["classification"])
    status = "completed" if classification not in NON_SUCCESS_CLASSIFICATIONS else classification
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-fallback-reason-probe-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "review_kind": "enabled_signature_bucket_fallback_reason_no_solve_probe_review",
        "project_root": str(project_root),
        "readiness_path": str(readiness_path),
        "probe_path": str(probe_path),
        "output_dir": str(output_dir),
        "target": dict(_mapping(probe.get("target"))),
        "run_id": probe.get("run_id"),
        "model_build_seconds": _float(_mapping(probe.get("inventory")).get("model_build_seconds")),
        "signature_instrumentation": signature_instrumentation,
        "interpretation": interpretation,
        "readiness_summary": {
            "status": readiness.get("status"),
            "classification": _mapping(readiness.get("readiness")).get("classification"),
            "probe_execution_enabled": readiness.get("probe_execution_enabled"),
            "next_probe_allowed_only_after_readiness_review": readiness.get(
                "next_probe_allowed_only_after_readiness_review"
            ),
        },
        "probe_safety": probe_safety,
        "current_sensitive_path_fingerprint": current_sensitive,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "proof_source": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "production_profile_changed": False,
        "candidate_universe_changed": False,
        "scheduler_integration": False,
        "runtime_execution_performed": False,
        "next_gate": _next_gate(interpretation),
        "paths": {key: str(path) for key, path in paths.items()},
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(paths["review_json"], payload)
        paths["review_md"].write_text(render_probe_review_markdown(payload), encoding="utf-8")
        atomic_write_json(paths["sensitive_path_fingerprint"], current_sensitive)
    return payload


def render_probe_review_markdown(payload: Mapping[str, Any]) -> str:
    interpretation = _mapping(payload.get("interpretation"))
    instr = _mapping(payload.get("signature_instrumentation"))
    lines = [
        "# Phase3B S64 Signature Bucket Fallback-Reason Probe Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Dominant reason: `{interpretation.get('dominant_reason')}`",
        f"- Dominant reason count: `{interpretation.get('dominant_reason_count')}`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Fallback Reasons",
        "",
    ]
    for reason, count in sorted(_mapping(instr.get("fallback_reasons")).items()):
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## Next Gate", "", str(_mapping(payload.get("next_gate")).get("status"))])
    return "\n".join(lines) + "\n"


def _probe_safety(probe: Mapping[str, Any]) -> dict[str, Any]:
    raw_comparison = probe.get("sensitive_path_comparison")
    comparison = _mapping(raw_comparison)
    actual_flags = {flag: probe.get(flag) for flag in HARD_BOUNDARY_FLAGS}
    literal_false_flags = {flag: actual_flags[flag] is False for flag in HARD_BOUNDARY_FLAGS}
    sensitive_path_comparison_valid = _sensitive_path_comparison_is_clean(raw_comparison)
    return {
        "status_completed": probe.get("status") == "completed",
        "run_id_matches": probe.get("run_id") == EXPECTED_RUN_ID,
        "candidate_key_42x32": _mapping(probe.get("target")).get("candidate_key") == "42x32",
        "execute_no_solve": probe.get("execute_no_solve") is True,
        "no_solve": probe.get("no_solve") is True,
        "hard_boundary_flags_literal_false": all(literal_false_flags.values()),
        "hard_boundary_flag_results": literal_false_flags,
        "actual_flags": actual_flags,
        "sensitive_path_comparison_valid": sensitive_path_comparison_valid,
        "sensitive_path_clean": sensitive_path_comparison_valid,
        "sensitive_path_changed": comparison.get("changed") is True,
        "sensitive_path_comparison": comparison,
    }


def _signature_instrumentation_summary(probe: Mapping[str, Any]) -> dict[str, Any]:
    signature_stats = _mapping(
        _mapping(
            _mapping(_mapping(probe.get("inventory")).get("build_stats_summary")).get(
                "global_valid_inequalities"
            )
        ).get("signature_bucket_capacity_bounds")
    )
    instrumentation = _mapping(signature_stats.get("signature_tightening_instrumentation"))
    if not instrumentation:
        return {
            "present": False,
            "fallback_reason_visibility": "signature_instrumentation_missing",
            "path": SIGNATURE_STATS_PATH,
            "phase_seconds": {},
            "totals": {},
            "fallback_reasons": {},
            "top_fallback_entries": [],
        }
    fallback_reasons = instrumentation.get("fallback_reasons")
    top_entries = instrumentation.get("top_fallback_entries")
    visible = isinstance(fallback_reasons, Mapping) and isinstance(top_entries, list)
    return {
        "present": True,
        "fallback_reason_visibility": (
            "fallback_reason_instrumentation_visible"
            if visible
            else "fallback_reason_instrumentation_missing"
        ),
        "path": SIGNATURE_STATS_PATH,
        "enabled": instrumentation.get("enabled"),
        "phase_seconds": {
            str(key): float(value)
            for key, value in _mapping(instrumentation.get("phase_seconds")).items()
            if isinstance(value, (int, float))
        },
        "totals": dict(_mapping(instrumentation.get("totals"))),
        "fallback_reasons": {
            str(key): int(value)
            for key, value in _mapping(fallback_reasons).items()
            if isinstance(value, int)
        },
        "top_fallback_entries": list(top_entries or [])[:10] if isinstance(top_entries, list) else [],
    }


def _interpretation(
    *,
    readiness: Mapping[str, Any],
    probe_safety: Mapping[str, Any],
    signature_instrumentation: Mapping[str, Any],
) -> dict[str, Any]:
    readiness_ok = (
        readiness.get("status") == "completed"
        and _mapping(readiness.get("readiness")).get("classification")
        == "ready_for_fallback_reason_probe_review"
    )
    safety_ok = all(
        bool(probe_safety.get(key))
        for key in (
            "status_completed",
            "run_id_matches",
            "candidate_key_42x32",
            "execute_no_solve",
            "no_solve",
            "hard_boundary_flags_literal_false",
            "sensitive_path_clean",
        )
    )
    if not safety_ok:
        return {
            "classification": "safety_disqualified",
            "reason": "The probe readiness or runtime safety flags are not clean.",
            "next_engineering_step": "return_to_safety_audit",
        }
    if not readiness_ok:
        return {
            "classification": "fallback_reason_inconclusive",
            "reason": "S63 readiness is missing or not accepted for this probe.",
            "next_engineering_step": "inspect_readiness_before_continuing",
        }
    if signature_instrumentation.get("fallback_reason_visibility") != (
        "fallback_reason_instrumentation_visible"
    ):
        return {
            "classification": "fallback_reason_instrumentation_missing",
            "reason": "fallback_reasons/top_fallback_entries are missing from final build_stats instrumentation.",
            "next_engineering_step": "return_to_fallback_reason_visibility_debug",
        }
    phases = _mapping(signature_instrumentation.get("phase_seconds"))
    totals = _mapping(signature_instrumentation.get("totals"))
    fallback_reasons = _mapping(signature_instrumentation.get("fallback_reasons"))
    mandatory_scan_seconds = _float(phases.get("per_anchor_mandatory_scan"))
    fallback_attempts = _int_or_none(totals.get("mandatory_region_counting_fallbacks"))
    if mandatory_scan_seconds is None or fallback_attempts is None:
        return {
            "classification": "fallback_reason_inconclusive",
            "reason": "Mandatory scan timing or fallback totals are missing.",
            "next_engineering_step": "manual_review_probe_schema_before_more_work",
        }
    if not fallback_reasons:
        classification = (
            "fallback_reason_instrumentation_visible"
            if fallback_attempts == 0
            else "fallback_reason_inconclusive"
        )
        return {
            "classification": classification,
            "reason": "Fallback reason fields are present but no fallback reasons were recorded.",
            "mandatory_scan_seconds": mandatory_scan_seconds,
            "mandatory_region_counting_fallbacks": fallback_attempts,
            "next_engineering_step": _next_step_for_classification(classification),
        }
    dominant_reason, dominant_count = max(
        ((str(reason), int(count)) for reason, count in fallback_reasons.items()),
        key=lambda item: (item[1], item[0]),
    )
    total_reasons = sum(int(count) for count in fallback_reasons.values())
    classification = (
        REASON_CLASSIFICATION.get(dominant_reason, "other_guard_failure_dominates")
        if total_reasons > 0 and dominant_count / total_reasons > 0.5
        else "fallback_reason_instrumentation_visible"
    )
    return {
        "classification": classification,
        "reason": "Fallback reason instrumentation is visible and classified from bounded counters.",
        "dominant_reason": dominant_reason,
        "dominant_reason_count": dominant_count,
        "dominant_reason_ratio": dominant_count / total_reasons if total_reasons else None,
        "fallback_reason_total": total_reasons,
        "mandatory_scan_seconds": mandatory_scan_seconds,
        "mandatory_region_counting_fallbacks": fallback_attempts,
        "next_engineering_step": _next_step_for_classification(classification),
    }


def _next_step_for_classification(classification: str) -> str:
    if classification == "compact_region_metadata_missing_dominates":
        return "prepare_compact_region_metadata_strategy_or_review"
    if classification == "overlapping_region_guard_dominates":
        return "prepare_overlap_guard_strategy_or_review"
    if classification == "unsupported_footprint_dominates":
        return "prepare_template_footprint_support_strategy_or_review"
    if classification == "other_guard_failure_dominates":
        return "prepare_guard_failure_strategy_or_review"
    if classification == "fallback_reason_instrumentation_missing":
        return "return_to_fallback_reason_visibility_debug"
    if classification == "safety_disqualified":
        return "return_to_safety_audit"
    if classification == "fallback_reason_inconclusive":
        return "manual_review_probe_schema_before_more_work"
    return "prepare_post_probe_strategy_from_visible_fallback_reasons"


def _next_gate(interpretation: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(interpretation.get("classification"))
    return {
        "status": (
            "hold_for_hotspot_specific_strategy"
            if classification
            not in {
                "safety_disqualified",
                "fallback_reason_instrumentation_missing",
                "fallback_reason_inconclusive",
            }
            else "hold_for_safety_or_manual_review"
        ),
        "next_engineering_step": interpretation.get("next_engineering_step"),
        "blocked_actions": [
            "do_not_run_runtime_solve",
            "do_not_run_67x20",
            "do_not_run_full_wave",
            "do_not_write_canonical_checkpoints",
            "do_not_promote_local_results_to_proof",
            "do_not_change_production_defaults",
        ],
    }


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "review_json": output_dir / "signature_bucket_fallback_reason_probe_review.json",
        "review_md": output_dir / "signature_bucket_fallback_reason_probe_review.md",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _load_json(path: Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _assert_review_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "64_signature_bucket_fallback_reason_probe_review" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S64 probe review namespace: {path}")


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else (project_root / path)


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sensitive_path_comparison_is_clean(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    changed_paths = value.get("changed_paths", None)
    changed_entries = value.get("changed_entries", None)
    if value.get("schema") != SENSITIVE_PATH_COMPARISON_SCHEMA:
        return False
    return (
        value.get("changed") is False
        and isinstance(changed_paths, list)
        and changed_paths == []
        and isinstance(changed_entries, list)
        and changed_entries == []
    )


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _int_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import build_sensitive_path_fingerprint  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_READINESS = (
    ARTIFACT_ROOT
    / "86_signature_bucket_payload_footprint_probe_readiness"
    / "signature_bucket_payload_footprint_probe_readiness.json"
)
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_payload_footprint_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "87_signature_bucket_payload_footprint_probe_review"
EXPECTED_RUN_ID = "local_hotspot_42x32_signature_bucket_payload_footprint_inst_no_solve_001"
SIGNATURE_STATS_PATH = (
    "inventory.build_stats_summary.global_valid_inequalities."
    "signature_bucket_capacity_bounds.signature_tightening_instrumentation"
)
SENSITIVE_PATH_COMPARISON_SCHEMA = "phase3b-sensitive-path-fingerprint-comparison/v0"
NON_SUCCESS_CLASSIFICATIONS = {
    "safety_disqualified",
    "support_gap_instrumentation_missing",
    "payload_footprint_probe_inconclusive",
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_signature_bucket_payload_footprint_probe_review(
        project_root=PROJECT_ROOT,
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket payload-footprint probe review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['paths']['review_json']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review the future S86-enabled 42x32 no-solve payload-footprint probe and "
            "classify whether S85 reduced unstable footprint-bound fallback."
        )
    )
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_payload_footprint_probe_review(
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
        "schema": "phase3b-signature-bucket-payload-footprint-probe-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "review_kind": "enabled_signature_bucket_payload_footprint_no_solve_probe_review",
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
        "# Phase3B S87 Signature Bucket Payload-Footprint Probe Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Payload stability used: `{interpretation.get('payload_footprint_stability_used')}`",
        f"- Unstable-bound fallback ratio: `{_fmt(interpretation.get('current_unstable_bounds_ratio'))}`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Support-Gap Reasons",
        "",
    ]
    for reason, count in sorted(_mapping(instr.get("support_gap_reasons")).items()):
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
            "support_gap_visibility": "signature_instrumentation_missing",
            "path": SIGNATURE_STATS_PATH,
            "phase_seconds": {},
            "totals": {},
            "support_gap_reasons": {},
            "top_support_gap_entries": [],
            "top_payload_footprint_stability_entries": [],
        }
    gap_reasons = instrumentation.get("template_footprint_support_gap_reasons")
    top_gap_entries = instrumentation.get("top_template_footprint_gap_entries")
    totals = dict(_mapping(instrumentation.get("totals")))
    top_stability_entries = instrumentation.get("top_payload_footprint_stability_entries")
    visible = isinstance(gap_reasons, Mapping) and isinstance(top_gap_entries, list)
    return {
        "present": True,
        "support_gap_visibility": (
            "support_gap_instrumentation_visible" if visible else "support_gap_instrumentation_missing"
        ),
        "path": SIGNATURE_STATS_PATH,
        "enabled": instrumentation.get("enabled"),
        "phase_seconds": {
            str(key): float(value)
            for key, value in _mapping(instrumentation.get("phase_seconds")).items()
            if isinstance(value, (int, float))
        },
        "totals": totals,
        "support_gap_reasons": {
            str(key): int(value)
            for key, value in _mapping(gap_reasons).items()
            if isinstance(value, int)
        },
        "top_support_gap_entries": list(top_gap_entries or [])[:10]
        if isinstance(top_gap_entries, list)
        else [],
        "top_payload_footprint_stability_entries": list(top_stability_entries or [])[:10]
        if isinstance(top_stability_entries, list)
        else [],
    }


def _interpretation(
    *,
    readiness: Mapping[str, Any],
    probe_safety: Mapping[str, Any],
    signature_instrumentation: Mapping[str, Any],
) -> dict[str, Any]:
    readiness_data = _mapping(readiness.get("readiness"))
    readiness_ok = (
        readiness.get("status") == "completed"
        and readiness_data.get("classification") == "ready_for_payload_footprint_probe_review"
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
            "classification": "payload_footprint_probe_inconclusive",
            "reason": "S86 readiness is missing or not accepted for this probe.",
            "next_engineering_step": "inspect_readiness_before_continuing",
        }
    if signature_instrumentation.get("support_gap_visibility") != "support_gap_instrumentation_visible":
        return {
            "classification": "support_gap_instrumentation_missing",
            "reason": "template-footprint support-gap diagnostics are missing from final build_stats instrumentation.",
            "next_engineering_step": "return_to_support_gap_visibility_debug",
        }
    phases = _mapping(signature_instrumentation.get("phase_seconds"))
    totals = _mapping(signature_instrumentation.get("totals"))
    reasons = _mapping(signature_instrumentation.get("support_gap_reasons"))
    baseline_scan = _float(readiness_data.get("baseline_mandatory_scan_seconds"))
    current_scan = _float(phases.get("per_anchor_mandatory_scan"))
    baseline_unstable = _int_or_none(readiness_data.get("baseline_unstable_footprint_bounds_fallbacks"))
    stability_attempts = _int_or_none(
        totals.get("mandatory_payload_footprint_stability_attempts")
    )
    stability_used = _int_or_none(totals.get("mandatory_payload_footprint_stability_used"))
    stability_fallbacks = _int_or_none(
        totals.get("mandatory_payload_footprint_stability_fallbacks")
    )
    stability_cohorts = _int_or_none(totals.get("mandatory_payload_footprint_stability_cohorts"))
    if (
        baseline_scan is None
        or current_scan is None
        or baseline_unstable is None
        or stability_attempts is None
        or stability_used is None
        or stability_fallbacks is None
        or stability_cohorts is None
    ):
        return {
            "classification": "payload_footprint_probe_inconclusive",
            "reason": "Timing, baseline fallback count, or payload-footprint totals are missing.",
            "next_engineering_step": "manual_review_probe_schema_before_more_work",
        }
    reason_total = sum(int(count) for count in reasons.values())
    if stability_fallbacks > 0 and reason_total <= 0:
        return {
            "classification": "payload_footprint_probe_inconclusive",
            "reason": "Payload-footprint fallbacks are present, but support-gap reason counts are missing.",
            "next_engineering_step": "manual_review_probe_schema_before_more_work",
        }
    current_unstable = int(reasons.get("unstable_footprint_bounds_within_payload", 0))
    current_unstable_ratio = current_unstable / reason_total if reason_total > 0 else 0.0
    scan_reduction = _ratio_reduction(baseline_scan, current_scan)
    unstable_reduction = _ratio_reduction(baseline_unstable, current_unstable)
    if stability_attempts > 0 and stability_used <= 0:
        classification = "payload_footprint_stability_not_used"
        next_step = "return_to_payload_footprint_stability_debug"
    elif current_unstable_ratio >= 0.5 and current_unstable >= max(1, int(baseline_unstable * 0.5)):
        classification = "unstable_bounds_still_dominates"
        next_step = "prepare_payload_footprint_stability_followup_strategy_or_review"
    elif current_scan >= max(10.0, baseline_scan * 0.75):
        classification = "mandatory_scan_still_hot"
        next_step = "prepare_mandatory_scan_residual_strategy_or_review"
    elif stability_used > 0 and unstable_reduction > 0 and scan_reduction > 0:
        classification = "payload_footprint_stability_effective"
        next_step = "prepare_next_residual_hotspot_strategy_or_review"
    else:
        classification = "payload_footprint_probe_inconclusive"
        next_step = "manual_review_probe_schema_before_more_work"
    return {
        "classification": classification,
        "reason": (
            f"Payload-footprint stability used {stability_used}/{stability_attempts}; "
            f"unstable-bound fallbacks are {current_unstable}/{reason_total}."
        ),
        "baseline_mandatory_scan_seconds": baseline_scan,
        "current_mandatory_scan_seconds": current_scan,
        "mandatory_scan_reduction_ratio": scan_reduction,
        "baseline_unstable_footprint_bounds_fallbacks": baseline_unstable,
        "current_unstable_footprint_bounds_fallbacks": current_unstable,
        "current_unstable_bounds_ratio": current_unstable_ratio,
        "unstable_footprint_bounds_reduction_ratio": unstable_reduction,
        "payload_footprint_stability_attempts": stability_attempts,
        "payload_footprint_stability_used": stability_used,
        "payload_footprint_stability_fallbacks": stability_fallbacks,
        "payload_footprint_stability_cohorts": stability_cohorts,
        "support_gap_reason_total": reason_total,
        "next_engineering_step": next_step,
    }


def _next_gate(interpretation: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(interpretation.get("classification"))
    return {
        "status": (
            "hold_for_payload_footprint_probe_result_strategy"
            if classification not in NON_SUCCESS_CLASSIFICATIONS
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
            "do_not_patch_solver_model_without_new_review_and_authorization",
        ],
    }


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "review_json": output_dir / "signature_bucket_payload_footprint_probe_review.json",
        "review_md": output_dir / "signature_bucket_payload_footprint_probe_review.md",
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
        or "87_signature_bucket_payload_footprint_probe_review" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S87 probe review namespace: {path}")


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


def _ratio_reduction(baseline: float | int, current: float | int) -> float:
    baseline_float = float(baseline)
    if baseline_float <= 0:
        return 0.0
    return (baseline_float - float(current)) / baseline_float


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _int_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


def _fmt(value: Any) -> str:
    return f"{float(value):.6f}" if isinstance(value, (int, float)) else "n/a"


if __name__ == "__main__":
    raise SystemExit(main())

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
    / "52_signature_bucket_mandatory_region_counting_probe_readiness"
    / "signature_bucket_mandatory_region_counting_probe_readiness.json"
)
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "53_signature_bucket_mandatory_region_counting_probe_review"
EXPECTED_RUN_ID = "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001"
SIGNATURE_STATS_PATH = (
    "inventory.build_stats_summary.global_valid_inequalities."
    "signature_bucket_capacity_bounds.signature_tightening_instrumentation"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=PROJECT_ROOT,
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket mandatory region-counting probe review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    print(f"region_counting_status={review['signature_instrumentation'].get('region_counting_status')}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['paths']['review_json']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review the future S52-enabled 42x32 no-solve mandatory region-counting "
            "probe and classify whether S51 reduced the mandatory scan hotspot."
        )
    )
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_mandatory_region_counting_probe_review(
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
    status = (
        "completed"
        if interpretation["classification"]
        not in {"safety_disqualified", "instrumentation_inconclusive"}
        else interpretation["classification"]
    )
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-mandatory-region-counting-probe-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "review_kind": "enabled_signature_bucket_mandatory_region_counting_no_solve_probe_review",
        "project_root": str(project_root),
        "readiness_path": str(readiness_path),
        "probe_path": str(probe_path),
        "output_dir": str(output_dir),
        "target": dict(_mapping(probe.get("target"))),
        "run_id": probe.get("run_id"),
        "model_build_seconds": _float(_mapping(probe.get("inventory")).get("model_build_seconds")),
        "wrapper_timing": _wrapper_timing_summary(probe),
        "signature_instrumentation": signature_instrumentation,
        "interpretation": interpretation,
        "readiness_summary": {
            "status": readiness.get("status"),
            "classification": _mapping(readiness.get("readiness")).get("classification"),
            "baseline_mandatory_scan_seconds": _mapping(readiness.get("readiness")).get(
                "baseline_mandatory_scan_seconds"
            ),
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
    phases = _mapping(instr.get("phase_seconds"))
    totals = _mapping(instr.get("totals"))
    lines = [
        "# Phase3B S53 Signature Bucket Mandatory Region Counting Probe Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Region-counting status: `{instr.get('region_counting_status')}`",
        f"- Mandatory scan seconds: `{_fmt(phases.get('per_anchor_mandatory_scan'))}`",
        f"- Baseline mandatory scan seconds: `{_fmt(_mapping(payload.get('readiness_summary')).get('baseline_mandatory_scan_seconds'))}`",
        f"- Model build seconds: `{_fmt(payload.get('model_build_seconds'))}`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Region Counting Totals",
        "",
    ]
    for key in (
        "mandatory_region_counting_attempts",
        "mandatory_region_counting_used",
        "mandatory_region_counting_fallbacks",
        "mandatory_region_rectangles_evaluated",
        "mandatory_region_overlap_counts",
        "mandatory_region_counted_blocked_poses",
        "mandatory_cells_scanned",
        "mandatory_pose_hits",
    ):
        lines.append(f"- `{key}`: `{totals.get(key)}`")
    lines.extend(["", "## Next Gate", "", str(_mapping(payload.get("next_gate")).get("status"))])
    return "\n".join(lines) + "\n"


def _probe_safety(probe: Mapping[str, Any]) -> dict[str, Any]:
    raw_comparison = probe.get("sensitive_path_comparison")
    comparison = _mapping(raw_comparison)
    sensitive_path_comparison_valid = _sensitive_path_comparison_is_clean(raw_comparison)
    actual_flags = {
        "fresh_solver_run_started": probe.get("fresh_solver_run_started"),
        "main_py_executed": probe.get("main_py_executed"),
        "exact_campaign_used": probe.get("exact_campaign_used"),
        "cp_solver_solve_called": probe.get("cp_solver_solve_called"),
        "checkpoint_written": probe.get("checkpoint_written"),
        "proof_source": probe.get("proof_source"),
        "source_model_mutation": probe.get("source_model_mutation"),
        "source_mutation_performed": probe.get("source_mutation_performed"),
        "candidate_universe_changed": probe.get("candidate_universe_changed"),
        "scheduler_integration": probe.get("scheduler_integration"),
        "runtime_execution_performed": probe.get("runtime_execution_performed"),
        "production_profile_changed": probe.get("production_profile_changed"),
    }
    return {
        "status_completed": probe.get("status") == "completed",
        "run_id_matches": probe.get("run_id") == EXPECTED_RUN_ID,
        "candidate_key_42x32": _mapping(probe.get("target")).get("candidate_key") == "42x32",
        "execute_no_solve": probe.get("execute_no_solve") is True,
        "no_solve": probe.get("no_solve") is True,
        "fresh_solver_run_not_started": actual_flags["fresh_solver_run_started"] is False,
        "main_py_not_executed": actual_flags["main_py_executed"] is False,
        "exact_campaign_not_used": actual_flags["exact_campaign_used"] is False,
        "cp_solver_solve_not_called": actual_flags["cp_solver_solve_called"] is False,
        "checkpoint_not_written": actual_flags["checkpoint_written"] is False,
        "not_proof_source": actual_flags["proof_source"] is False,
        "source_model_not_mutated": actual_flags["source_model_mutation"] is False,
        "source_mutation_not_performed": actual_flags["source_mutation_performed"] is False,
        "candidate_universe_not_changed": actual_flags["candidate_universe_changed"] is False,
        "scheduler_not_integrated": actual_flags["scheduler_integration"] is False,
        "runtime_execution_not_performed": actual_flags["runtime_execution_performed"] is False,
        "production_profile_not_changed": actual_flags["production_profile_changed"] is False,
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
            "visibility_status": "visibility_missing",
            "region_counting_status": "visibility_missing",
            "path": SIGNATURE_STATS_PATH,
            "phase_seconds": {},
            "totals": {},
            "top_slow_entries": [],
        }
    phases = {
        str(key): float(value)
        for key, value in _mapping(instrumentation.get("phase_seconds")).items()
        if isinstance(value, (int, float))
    }
    totals = dict(_mapping(instrumentation.get("totals")))
    used = int(totals.get("mandatory_region_counting_used", 0) or 0)
    fallbacks = int(totals.get("mandatory_region_counting_fallbacks", 0) or 0)
    attempts = int(totals.get("mandatory_region_counting_attempts", 0) or 0)
    if attempts <= 0:
        region_status = "mandatory_region_counting_not_used"
    elif used <= 0:
        region_status = "fallback_dominated" if fallbacks > 0 else "mandatory_region_counting_not_used"
    elif fallbacks > used:
        region_status = "fallback_dominated"
    else:
        region_status = "mandatory_region_counting_used"
    return {
        "present": True,
        "visibility_status": "instrumentation_visible",
        "region_counting_status": region_status,
        "path": SIGNATURE_STATS_PATH,
        "enabled": instrumentation.get("enabled"),
        "phase_seconds": phases,
        "phase_seconds_sum": float(sum(phases.values())),
        "totals": totals,
        "top_slow_entries": list(instrumentation.get("top_slow_entries", []) or [])[:10],
    }


def _wrapper_timing_summary(probe: Mapping[str, Any]) -> dict[str, Any]:
    timing = _mapping(probe.get("timing"))
    phases = {
        str(_mapping(row).get("phase")): _mapping(row)
        for row in list(timing.get("phases", []) or [])
        if _mapping(row).get("phase")
    }
    return {
        "from_exact_core_total_seconds": _float(timing.get("from_exact_core_total_seconds")),
        "recorded_phase_seconds_sum": _float(timing.get("recorded_phase_seconds_sum")),
        "ghost_signature_bucket_total_seconds": _float(
            _mapping(
                phases.get(
                    "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
                )
            ).get("total_seconds")
        ),
        "ghost_constraints_total_seconds": _float(
            _mapping(phases.get("CoordinateExactMasterDelegate._add_ghost_constraints")).get(
                "total_seconds"
            )
        ),
    }


def _interpretation(
    *,
    readiness: Mapping[str, Any],
    probe_safety: Mapping[str, Any],
    signature_instrumentation: Mapping[str, Any],
) -> dict[str, Any]:
    readiness_payload = _mapping(readiness.get("readiness"))
    readiness_ok = (
        readiness.get("status") == "completed"
        and readiness_payload.get("classification")
        == "ready_for_mandatory_region_counting_probe_review"
    )
    safety_ok = all(
        bool(probe_safety.get(key))
        for key in (
            "status_completed",
            "run_id_matches",
            "candidate_key_42x32",
            "execute_no_solve",
            "no_solve",
            "fresh_solver_run_not_started",
            "main_py_not_executed",
            "exact_campaign_not_used",
            "cp_solver_solve_not_called",
            "checkpoint_not_written",
            "not_proof_source",
            "source_model_not_mutated",
            "source_mutation_not_performed",
            "candidate_universe_not_changed",
            "scheduler_not_integrated",
            "runtime_execution_not_performed",
            "production_profile_not_changed",
        )
    )
    if not probe_safety.get("sensitive_path_clean") or not safety_ok:
        return {
            "classification": "safety_disqualified",
            "reason": "The probe readiness or runtime safety flags are not clean.",
            "next_engineering_step": "return_to_safety_audit",
        }
    if not readiness_ok:
        return {
            "classification": "instrumentation_inconclusive",
            "reason": "S52 readiness is missing or not accepted for this probe.",
            "next_engineering_step": "inspect_readiness_before_continuing",
        }
    if not signature_instrumentation.get("present"):
        return {
            "classification": "visibility_missing",
            "reason": "signature_tightening_instrumentation is missing from final build_stats.",
            "next_engineering_step": "return_to_visibility_or_probe_debug",
        }

    totals = _mapping(signature_instrumentation.get("totals"))
    phases = _mapping(signature_instrumentation.get("phase_seconds"))
    used = int(totals.get("mandatory_region_counting_used", 0) or 0)
    fallbacks = int(totals.get("mandatory_region_counting_fallbacks", 0) or 0)
    attempts = int(totals.get("mandatory_region_counting_attempts", 0) or 0)
    mandatory_scan_seconds = _float(phases.get("per_anchor_mandatory_scan"))
    baseline_seconds = _float(readiness_payload.get("baseline_mandatory_scan_seconds"))
    if baseline_seconds is None or mandatory_scan_seconds is None:
        classification = "instrumentation_inconclusive"
    elif attempts <= 0:
        classification = "mandatory_region_counting_not_used"
    elif used <= 0 or fallbacks > used:
        classification = "fallback_dominated"
    elif (
        mandatory_scan_seconds >= baseline_seconds * 0.75
    ):
        classification = "mandatory_scan_still_hot"
    elif used > 0:
        classification = "mandatory_region_counting_effective"
    else:
        classification = "instrumentation_inconclusive"
    return {
        "classification": classification,
        "reason": _reason_for_classification(
            classification,
            baseline_seconds=baseline_seconds,
            mandatory_scan_seconds=mandatory_scan_seconds,
            used=used,
            fallbacks=fallbacks,
            attempts=attempts,
        ),
        "baseline_mandatory_scan_seconds": baseline_seconds,
        "mandatory_scan_seconds": mandatory_scan_seconds,
        "mandatory_region_counting_attempts": attempts,
        "mandatory_region_counting_used": used,
        "mandatory_region_counting_fallbacks": fallbacks,
        "next_engineering_step": _next_step_for_classification(classification),
    }


def _reason_for_classification(
    classification: str,
    *,
    baseline_seconds: float | None,
    mandatory_scan_seconds: float | None,
    used: int,
    fallbacks: int,
    attempts: int,
) -> str:
    if classification == "mandatory_region_counting_effective":
        return (
            "Region counting was used and mandatory scan time dropped below the S48 "
            "baseline threshold."
        )
    if classification == "mandatory_region_counting_not_used":
        return "The probe produced instrumentation but did not attempt mandatory region counting."
    if classification == "fallback_dominated":
        return "Region counting attempts fell back to legacy scanning more often than they used the fast path."
    if classification == "mandatory_scan_still_hot":
        return "Region counting was used but mandatory scan time remains near the S48 baseline."
    return (
        "Unable to classify region-counting impact from attempts="
        f"{attempts}, used={used}, fallbacks={fallbacks}, baseline={baseline_seconds}, "
        f"mandatory_scan={mandatory_scan_seconds}."
    )


def _next_step_for_classification(classification: str) -> str:
    if classification == "mandatory_region_counting_effective":
        return "prepare_post_probe_strategy_or_review_for_next_hotspot"
    if classification == "mandatory_region_counting_not_used":
        return "inspect_region_counting_guard_conditions_before_any_rerun"
    if classification == "fallback_dominated":
        return "prepare_fallback_reason_strategy_before_source_patch_or_rerun"
    if classification == "mandatory_scan_still_hot":
        return "prepare_second_order_mandatory_scan_strategy_or_patch_spec"
    if classification == "visibility_missing":
        return "return_to_instrumentation_visibility_debug"
    if classification == "safety_disqualified":
        return "return_to_safety_audit"
    return "manual_review_instrumentation_before_more_work"


def _next_gate(interpretation: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(interpretation.get("classification"))
    return {
        "status": (
            "hold_for_post_probe_strategy"
            if classification
            not in {
                "safety_disqualified",
                "visibility_missing",
                "instrumentation_inconclusive",
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
        "review_json": output_dir / "signature_bucket_mandatory_region_counting_probe_review.json",
        "review_md": output_dir / "signature_bucket_mandatory_region_counting_probe_review.md",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _load_json(path: Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _assert_review_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "53_signature_bucket_mandatory_region_counting_probe_review" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S53 probe review namespace: {path}")


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
    changed_paths = value.get("changed_paths")
    return (
        value.get("changed") is False
        and isinstance(changed_paths, list)
        and not changed_paths
        and all(isinstance(path, str) for path in changed_paths)
    )


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _fmt(value: Any) -> str:
    return f"{float(value):.6f}" if isinstance(value, (int, float)) else "n/a"


if __name__ == "__main__":
    raise SystemExit(main())

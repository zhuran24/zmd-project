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
    / "47_signature_bucket_visibility_probe_readiness"
    / "signature_bucket_visibility_probe_readiness.json"
)
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_visibility_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "48_signature_bucket_visibility_probe_review"
EXPECTED_RUN_ID = "local_hotspot_42x32_signature_bucket_visibility_inst_no_solve_001"
SIGNATURE_STATS_PATH = (
    "inventory.build_stats_summary.global_valid_inequalities."
    "signature_bucket_capacity_bounds.signature_tightening_instrumentation"
)
PHASE_CLASSIFICATIONS = {
    "mandatory_payload_build": "payload_build_hotspot",
    "required_optional_payload_build": "payload_build_hotspot",
    "per_anchor_mandatory_scan": "mandatory_scan_hotspot",
    "per_anchor_required_optional_scan": "required_optional_scan_hotspot",
    "constraint_add": "constraint_add_hotspot",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_signature_bucket_visibility_probe_review(
        project_root=PROJECT_ROOT,
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket visibility probe review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    print(f"visibility_status={review['signature_instrumentation'].get('visibility_status')}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['paths']['review_json']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review the future S47-enabled 42x32 no-solve visibility-patch probe "
            "and classify whether S46 exposed instrumentation plus the dominant phase."
        )
    )
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_visibility_probe_review(
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
        not in {"manual_review_required", "disqualified_sensitive_path_mutation"}
        else interpretation["classification"]
    )
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-visibility-probe-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "review_kind": "enabled_signature_bucket_visibility_no_solve_probe_review",
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
        "# Phase3B S48 Signature Bucket Visibility Probe Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Visibility status: `{instr.get('visibility_status')}`",
        f"- Dominant phase: `{instr.get('dominant_phase')}`",
        f"- Dominant phase seconds: `{_fmt(instr.get('dominant_phase_seconds'))}`",
        f"- Model build seconds: `{_fmt(payload.get('model_build_seconds'))}`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Phase Seconds",
        "",
    ]
    for key in sorted(phases):
        lines.append(f"- `{key}`: `{_fmt(phases.get(key))}`")
    lines.extend(["", "## Totals", ""])
    for key in sorted(totals):
        lines.append(f"- `{key}`: `{totals.get(key)}`")
    lines.extend(["", "## Next Gate", "", str(_mapping(payload.get("next_gate")).get("status"))])
    return "\n".join(lines) + "\n"


def _probe_safety(probe: Mapping[str, Any]) -> dict[str, Any]:
    comparison = _mapping(probe.get("sensitive_path_comparison"))
    actual_flags = {
        "fresh_solver_run_started": probe.get("fresh_solver_run_started"),
        "main_py_executed": probe.get("main_py_executed"),
        "exact_campaign_used": probe.get("exact_campaign_used"),
        "cp_solver_solve_called": probe.get("cp_solver_solve_called"),
        "checkpoint_written": probe.get("checkpoint_written"),
        "proof_source": probe.get("proof_source"),
        "source_model_mutation": probe.get("source_model_mutation"),
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
        "production_profile_not_changed": actual_flags["production_profile_changed"] is False,
        "actual_flags": actual_flags,
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
            "visibility_status": "visibility_patch_failed",
            "path": SIGNATURE_STATS_PATH,
            "phase_seconds": {},
            "totals": {},
            "top_slow_entries": [],
            "dominant_phase": None,
            "dominant_phase_seconds": None,
        }
    phases = {
        str(key): float(value)
        for key, value in _mapping(instrumentation.get("phase_seconds")).items()
        if isinstance(value, (int, float))
    }
    totals = dict(_mapping(instrumentation.get("totals")))
    top_slow_entries = list(instrumentation.get("top_slow_entries", []) or [])[:10]
    dominant_phase = max(phases, key=lambda key: phases[key]) if phases else None
    dominant_seconds = phases.get(dominant_phase) if dominant_phase else None
    phase_total = sum(float(value) for value in phases.values())
    return {
        "present": True,
        "visibility_status": "instrumentation_visible",
        "path": SIGNATURE_STATS_PATH,
        "enabled": instrumentation.get("enabled"),
        "phase_seconds": phases,
        "phase_seconds_sum": float(phase_total),
        "totals": totals,
        "top_slow_entries": top_slow_entries,
        "dominant_phase": dominant_phase,
        "dominant_phase_seconds": dominant_seconds,
        "dominant_phase_fraction": (
            float(dominant_seconds) / float(phase_total)
            if dominant_seconds is not None and phase_total > 0.0
            else None
        ),
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
    readiness_ok = (
        readiness.get("status") == "completed"
        and _mapping(readiness.get("readiness")).get("classification")
        == "ready_for_visibility_probe_review"
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
            "production_profile_not_changed",
        )
    )
    if probe_safety.get("sensitive_path_changed") is True:
        return {
            "classification": "disqualified_sensitive_path_mutation",
            "reason": "The probe reported sensitive path changes; stop follow-up work.",
            "next_engineering_step": "return_to_safety_audit",
        }
    if not readiness_ok or not safety_ok:
        return {
            "classification": "manual_review_required",
            "reason": "Readiness or probe safety flags are not in the expected S48 state.",
            "next_engineering_step": "inspect_readiness_and_probe_safety_before_continuing",
        }
    if not signature_instrumentation.get("present"):
        return {
            "classification": "visibility_patch_failed",
            "reason": "S46 did not expose signature_tightening_instrumentation in final build_stats.",
            "next_engineering_step": "return_to_visibility_patch_debug_before_any_rerun",
        }
    dominant_phase = signature_instrumentation.get("dominant_phase")
    dominant_seconds = signature_instrumentation.get("dominant_phase_seconds")
    if dominant_phase is None or not isinstance(dominant_seconds, (int, float)) or dominant_seconds <= 0.0:
        classification = "instrumentation_visible"
    else:
        classification = PHASE_CLASSIFICATIONS.get(str(dominant_phase), "instrumentation_inconclusive")
    return {
        "classification": classification,
        "reason": f"S46 visibility is fixed; dominant S41 phase is {dominant_phase!r}.",
        "visibility_status": "instrumentation_visible",
        "dominant_phase": dominant_phase,
        "dominant_phase_seconds": dominant_seconds,
        "next_engineering_step": _next_step_for_classification(classification),
    }


def _next_step_for_classification(classification: str) -> str:
    if classification == "payload_build_hotspot":
        return "prepare_payload_build_optimization_strategy_or_patch_spec"
    if classification == "mandatory_scan_hotspot":
        return "prepare_mandatory_scan_optimization_strategy_or_patch_spec"
    if classification == "required_optional_scan_hotspot":
        return "prepare_required_optional_scan_optimization_strategy_or_patch_spec"
    if classification == "constraint_add_hotspot":
        return "prepare_constraint_add_optimization_strategy_or_patch_spec"
    if classification == "instrumentation_visible":
        return "inspect_visible_instrumentation_before_choosing_hotspot_patch"
    return "inspect_instrumentation_output_before_more_runtime"


def _next_gate(interpretation: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(interpretation.get("classification"))
    return {
        "status": (
            "hold_for_hotspot_specific_strategy"
            if classification
            not in {
                "manual_review_required",
                "disqualified_sensitive_path_mutation",
                "visibility_patch_failed",
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
        "review_json": output_dir / "signature_bucket_visibility_probe_review.json",
        "review_md": output_dir / "signature_bucket_visibility_probe_review.md",
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
        or "48_signature_bucket_visibility_probe_review" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S48 probe review namespace: {path}")


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


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _fmt(value: Any) -> str:
    return f"{float(value):.6f}" if isinstance(value, (int, float)) else "n/a"


if __name__ == "__main__":
    raise SystemExit(main())

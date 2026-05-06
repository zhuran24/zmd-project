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
    / "96_signature_bucket_residual_overlay_probe_readiness"
    / "signature_bucket_residual_overlay_probe_readiness.json"
)
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_residual_overlay_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "97_signature_bucket_residual_overlay_probe_review"
EXPECTED_RUN_ID = "local_hotspot_42x32_signature_bucket_residual_overlay_inst_no_solve_001"
SENSITIVE_PATH_COMPARISON_SCHEMA = "phase3b-sensitive-path-fingerprint-comparison/v0"
NON_SUCCESS_CLASSIFICATIONS = {
    "safety_disqualified",
    "residual_overlay_instrumentation_missing",
    "residual_overlay_probe_inconclusive",
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
HOTSPOT_LABELS = {
    "payload_region_metadata_build_seconds": "payload_region_metadata_hotspot",
    "payload_footprint_cohort_build_seconds": "payload_footprint_cohort_hotspot",
    "payload_bucket_region_rebuild_seconds": "payload_bucket_region_rebuild_hotspot",
    "payload_compactness_guard_seconds": "payload_compactness_guard_hotspot",
    "residual_signature_scan_seconds": "residual_signature_scan_hotspot",
    "residual_signature_constraint_add_seconds": "residual_signature_constraint_add_hotspot",
    "outer_exact_core_overlay_residual_seconds": "outer_exact_core_overlay_residual_hotspot",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_signature_bucket_residual_overlay_probe_review(
        project_root=PROJECT_ROOT,
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket residual-overlay probe review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['paths']['review_json']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review the future S96-enabled 42x32 no-solve residual-overlay probe and "
            "classify the dominant residual subphase."
        )
    )
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_residual_overlay_probe_review(
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
    residual_summary = _residual_overlay_summary(probe)
    interpretation = _interpretation(
        readiness=readiness,
        probe_safety=probe_safety,
        residual_summary=residual_summary,
    )
    classification = str(interpretation["classification"])
    status = "completed" if classification not in NON_SUCCESS_CLASSIFICATIONS else classification
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-residual-overlay-probe-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "review_kind": "enabled_signature_bucket_residual_overlay_no_solve_probe_review",
        "project_root": str(project_root),
        "readiness_path": str(readiness_path),
        "probe_path": str(probe_path),
        "output_dir": str(output_dir),
        "target": dict(_mapping(probe.get("target"))),
        "run_id": probe.get("run_id"),
        "model_build_seconds": _float(_mapping(probe.get("inventory")).get("model_build_seconds")),
        "residual_overlay_summary": residual_summary,
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
    residual = _mapping(payload.get("residual_overlay_summary"))
    lines = [
        "# Phase3B S97 Signature Bucket Residual Overlay Probe Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Dominant phase: `{interpretation.get('dominant_phase')}`",
        f"- Dominant seconds: `{_fmt(interpretation.get('dominant_seconds'))}`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Phase Seconds",
        "",
    ]
    for phase, seconds in sorted(_mapping(residual.get("phase_seconds")).items()):
        lines.append(f"- `{phase}`: `{_fmt(seconds)}`")
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


def _residual_overlay_summary(probe: Mapping[str, Any]) -> dict[str, Any]:
    gvi = _mapping(
        _mapping(_mapping(probe.get("inventory")).get("build_stats_summary")).get(
            "global_valid_inequalities"
        )
    )
    signature_instrumentation = _mapping(
        _mapping(gvi.get("signature_bucket_capacity_bounds")).get(
            "signature_tightening_instrumentation"
        )
    )
    signature_residual = _mapping(
        signature_instrumentation.get("residual_overlay_instrumentation")
    )
    residual_signature = _mapping(
        _mapping(gvi.get("residual_signature_bucket_capacity_bounds")).get(
            "residual_overlay_instrumentation"
        )
    )
    exact_core_reuse_residual = _mapping(
        _mapping(
            _mapping(probe.get("inventory")).get("build_stats_summary")
        ).get("exact_core_reuse")
    ).get("residual_overlay_instrumentation")
    exact_core_reuse_residual = _mapping(exact_core_reuse_residual)

    phase_seconds: dict[str, float] = {}
    for source in (
        _mapping(signature_residual.get("phase_seconds")),
        _mapping(residual_signature.get("phase_seconds")),
    ):
        for key, value in source.items():
            if isinstance(value, (int, float)):
                phase_seconds[str(key)] = phase_seconds.get(str(key), 0.0) + float(value)
    outer = exact_core_reuse_residual.get("outer_exact_core_overlay_residual_seconds")
    if isinstance(outer, (int, float)):
        phase_seconds["outer_exact_core_overlay_residual_seconds"] = float(outer)
    return {
        "signature_residual_present": bool(signature_residual),
        "residual_signature_present": bool(residual_signature),
        "exact_core_outer_present": bool(exact_core_reuse_residual),
        "all_required_sections_present": bool(
            signature_residual and residual_signature and exact_core_reuse_residual
        ),
        "phase_seconds": phase_seconds,
        "top_slow_payload_groups": list(signature_residual.get("top_slow_payload_groups") or [])[:10]
        if isinstance(signature_residual.get("top_slow_payload_groups"), list)
        else [],
        "top_slow_residual_signature_entries": list(
            residual_signature.get("top_slow_residual_signature_entries") or []
        )[:10]
        if isinstance(residual_signature.get("top_slow_residual_signature_entries"), list)
        else [],
    }


def _interpretation(
    *,
    readiness: Mapping[str, Any],
    probe_safety: Mapping[str, Any],
    residual_summary: Mapping[str, Any],
) -> dict[str, Any]:
    if not _safety_is_clean(probe_safety):
        return {"classification": "safety_disqualified", "reason": "probe_safety_not_clean"}
    if (
        _mapping(readiness.get("readiness")).get("classification")
        != "ready_for_residual_overlay_probe_review"
    ):
        return {
            "classification": "residual_overlay_probe_inconclusive",
            "reason": "readiness_not_ready_for_residual_overlay_probe_review",
        }
    if not residual_summary.get("all_required_sections_present"):
        return {
            "classification": "residual_overlay_instrumentation_missing",
            "reason": "one_or_more_required_residual_overlay_sections_missing",
        }
    phase_seconds = {
        str(key): float(value)
        for key, value in _mapping(residual_summary.get("phase_seconds")).items()
        if isinstance(value, (int, float))
    }
    if not phase_seconds:
        return {
            "classification": "residual_overlay_probe_inconclusive",
            "reason": "no_numeric_residual_overlay_phase_seconds",
        }
    dominant_phase, dominant_seconds = max(
        phase_seconds.items(),
        key=lambda item: (float(item[1]), str(item[0])),
    )
    classification = HOTSPOT_LABELS.get(
        dominant_phase,
        "residual_overlay_instrumentation_visible",
    )
    return {
        "classification": classification,
        "dominant_phase": dominant_phase,
        "dominant_seconds": float(dominant_seconds),
        "phase_seconds": phase_seconds,
    }


def _safety_is_clean(probe_safety: Mapping[str, Any]) -> bool:
    required_true = (
        "status_completed",
        "run_id_matches",
        "candidate_key_42x32",
        "execute_no_solve",
        "no_solve",
        "hard_boundary_flags_literal_false",
        "sensitive_path_clean",
    )
    return all(probe_safety.get(key) is True for key in required_true)


def _sensitive_path_comparison_is_clean(raw_comparison: Any) -> bool:
    comparison = _mapping(raw_comparison)
    return (
        comparison.get("schema") == SENSITIVE_PATH_COMPARISON_SCHEMA
        and comparison.get("changed") is False
        and comparison.get("changed_paths") == []
        and comparison.get("changed_entries") == []
    )


def _next_gate(interpretation: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(interpretation.get("classification"))
    if classification == "safety_disqualified":
        return {"status": "stop_for_safety_audit"}
    if classification in {
        "residual_overlay_instrumentation_missing",
        "residual_overlay_probe_inconclusive",
    }:
        return {"status": "prepare_review_first_repair_plan"}
    return {
        "status": "prepare_hotspot_specific_strategy_and_external_review",
        "classification": classification,
    }


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "review_json": output_dir / "signature_bucket_residual_overlay_probe_review.json",
        "review_md": output_dir / "signature_bucket_residual_overlay_probe_review.md",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _assert_review_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "97_signature_bucket_residual_overlay_probe_review" not in normalized:
        raise ValueError("S97 probe review namespace required")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _fmt(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.6f}"


def _resolve_path(project_root: Path, value: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

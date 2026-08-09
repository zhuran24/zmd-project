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
    / "117_signature_bucket_port_profile_cache_probe_readiness"
    / "signature_bucket_port_profile_cache_probe_readiness.json"
)
EXPECTED_RUN_ID = "local_hotspot_42x32_signature_bucket_port_profile_cache_inst_no_solve_001"
DEFAULT_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / EXPECTED_RUN_ID
    / "overlay_timing_probe.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "118_signature_bucket_port_profile_cache_probe_review"
SENSITIVE_PATH_COMPARISON_SCHEMA = "phase3b-sensitive-path-fingerprint-comparison/v0"
NON_SUCCESS_CLASSIFICATIONS = {
    "safety_disqualified",
    "port_profile_cache_instrumentation_missing",
    "port_profile_cache_probe_inconclusive",
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
    "index_container_initialization": "index_container_initialization_hotspot",
    "power_pole_index_build": "power_pole_index_hotspot",
    "per_template_pose_cache_build": "per_template_pose_cache_hotspot",
    "port_front_extraction": "port_front_extraction_hotspot",
    "local_signature_build": "local_signature_hotspot",
    "powered_anchor_shape_grouping": "powered_anchor_shape_grouping_hotspot",
    "powered_support_coverer_build": "powered_support_coverer_hotspot",
    "compact_capacity_signature_store": "compact_capacity_signature_store_hotspot",
    "exact_precompute_profile_update": "exact_precompute_profile_update_hotspot",
    "index_pools_unattributed_seconds": "index_pools_unattributed_hotspot",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_signature_bucket_port_profile_cache_probe_review(
        project_root=PROJECT_ROOT,
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
        probe_path=_resolve_path(PROJECT_ROOT, args.probe),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket port/profile cache probe review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['paths']['review_json']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review the future S117-enabled 42x32 no-solve port/profile cache "
            "probe and classify the dominant MasterPlacementModel._index_pools subphase."
        )
    )
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_port_profile_cache_probe_review(
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
    subphase_summary = _subphase_summary(probe)
    interpretation = _interpretation(
        readiness=readiness,
        probe_safety=probe_safety,
        subphase_summary=subphase_summary,
    )
    classification = str(interpretation["classification"])
    status = "completed" if classification not in NON_SUCCESS_CLASSIFICATIONS else classification
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-port-profile-cache-probe-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "review_kind": "enabled_signature_bucket_port_profile_cache_no_solve_probe_review",
        "project_root": str(project_root),
        "readiness_path": str(readiness_path),
        "probe_path": str(probe_path),
        "output_dir": str(output_dir),
        "target": dict(_mapping(probe.get("target"))),
        "run_id": probe.get("run_id"),
        "model_build_seconds": _float(_mapping(probe.get("inventory")).get("model_build_seconds")),
        "subphase_summary": subphase_summary,
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
    summary = _mapping(payload.get("subphase_summary"))
    lines = [
        "# Phase3B S118 Port/Profile Cache Probe Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Dominant phase: `{interpretation.get('dominant_phase')}`",
        f"- Dominant seconds: `{_fmt(interpretation.get('dominant_seconds'))}`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Port/Profile Cache Phase Seconds",
        "",
    ]
    for phase, seconds in sorted(_mapping(summary.get("phase_seconds")).items()):
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


def _subphase_summary(probe: Mapping[str, Any]) -> dict[str, Any]:
    build_stats = _mapping(_mapping(probe.get("inventory")).get("build_stats_summary"))
    residual = _mapping(
        _mapping(build_stats.get("exact_core_reuse")).get("residual_overlay_instrumentation")
    )
    port_profile = _mapping(residual.get("port_profile_cache_instrumentation"))
    raw_phase_seconds = _mapping(port_profile.get("phase_seconds"))
    phase_seconds = {
        str(key): float(value)
        for key, value in raw_phase_seconds.items()
        if isinstance(value, (int, float))
    }
    unattributed = _float(port_profile.get("index_pools_unattributed_seconds"))
    if unattributed is None:
        unattributed = _float(raw_phase_seconds.get("index_pools_unattributed_seconds"))
    if unattributed is not None:
        phase_seconds["index_pools_unattributed_seconds"] = unattributed
    subphase_total = _float(port_profile.get("index_pools_subphase_total_seconds"))
    if subphase_total is None and phase_seconds:
        subphase_total = sum(
            float(value)
            for key, value in phase_seconds.items()
            if key != "index_pools_unattributed_seconds"
        )
    total_seconds = _float(port_profile.get("index_pools_total_seconds"))
    if total_seconds is None:
        total_seconds = _float(port_profile.get("total_seconds"))
    if total_seconds is None and subphase_total is not None and unattributed is not None:
        total_seconds = subphase_total + unattributed
    required_numeric = {
        "index_pools_total_seconds": total_seconds,
        "index_pools_subphase_total_seconds": subphase_total,
        "index_pools_unattributed_seconds": unattributed,
    }
    return {
        "exact_core_reuse_residual_present": bool(residual),
        "port_profile_cache_instrumentation_present": bool(port_profile),
        "port_profile_cache_instrumentation_enabled": port_profile.get("enabled") is True,
        "has_phase_seconds": bool(raw_phase_seconds),
        "all_required_sections_present": bool(
            port_profile and port_profile.get("enabled") is True and raw_phase_seconds
        ),
        "required_numeric": required_numeric,
        "phase_seconds": phase_seconds,
        "totals": _mapping(port_profile.get("totals")),
        "top_slow_templates_or_groups": port_profile.get("top_slow_templates_or_groups"),
        "raw_port_profile_cache_instrumentation": port_profile,
    }


def _interpretation(
    *,
    readiness: Mapping[str, Any],
    probe_safety: Mapping[str, Any],
    subphase_summary: Mapping[str, Any],
) -> dict[str, Any]:
    if not _safety_is_clean(probe_safety):
        return {"classification": "safety_disqualified", "reason": "probe_safety_not_clean"}
    if (
        _mapping(readiness.get("readiness")).get("classification")
        != "ready_for_port_profile_cache_probe_review"
    ):
        return {
            "classification": "port_profile_cache_probe_inconclusive",
            "reason": "readiness_not_ready_for_port_profile_cache_probe_review",
        }
    if not subphase_summary.get("all_required_sections_present"):
        return {
            "classification": "port_profile_cache_instrumentation_missing",
            "reason": "port_profile_cache_instrumentation_missing",
        }
    required_numeric = _mapping(subphase_summary.get("required_numeric"))
    if not all(isinstance(value, (int, float)) for value in required_numeric.values()):
        return {
            "classification": "port_profile_cache_probe_inconclusive",
            "reason": "required_numeric_port_profile_cache_fields_missing",
        }
    phase_seconds = {
        str(key): float(value)
        for key, value in _mapping(subphase_summary.get("phase_seconds")).items()
        if isinstance(value, (int, float))
    }
    if not phase_seconds:
        return {
            "classification": "port_profile_cache_probe_inconclusive",
            "reason": "no_numeric_port_profile_cache_phase_seconds",
        }
    dominant_phase, dominant_seconds = max(
        phase_seconds.items(),
        key=lambda item: (float(item[1]), str(item[0])),
    )
    classification = HOTSPOT_LABELS.get(
        dominant_phase,
        "port_profile_cache_instrumentation_visible",
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
        "port_profile_cache_instrumentation_missing",
        "port_profile_cache_probe_inconclusive",
    }:
        return {"status": "prepare_review_first_repair_plan"}
    return {
        "status": "prepare_port_profile_cache_hotspot_specific_strategy_and_external_review",
        "classification": classification,
    }


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "review_json": output_dir / "signature_bucket_port_profile_cache_probe_review.json",
        "review_md": output_dir / "signature_bucket_port_profile_cache_probe_review.md",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _assert_review_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "118_signature_bucket_port_profile_cache_probe_review" not in normalized:
        raise ValueError("S118 probe review namespace required")


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

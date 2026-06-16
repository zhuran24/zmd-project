from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase3b.s3_lite.build_baseline_scorecard import build_sensitive_path_audit
from scripts.run_phase3b_local_tuning_profile import ARTIFACT_ROOT
from src.search.exact_campaign import atomic_write_json, now_iso

DEFAULT_BASELINE_SCORECARD = ARTIFACT_ROOT / "03_baseline_reproduction" / "baseline_scorecard.json"
DEFAULT_AI_DATASET_SUMMARY = Path(".artifacts/phase3b_ai_accel_20260430/01_feature_dataset/dataset_summary.json")
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "04_config_matrix"

CONFIG_MATRIX_CANDIDATES = (
    ("B0_prod_4x4", 4, 4, "baseline"),
    ("experimental_13900ks_htoff_3x6_global_normal", 3, 6, "18 worker slots; lower process replication"),
    ("experimental_13900ks_htoff_3x8_global_normal", 3, 8, "24 worker slots; medium memory risk"),
    ("experimental_13900ks_htoff_4x5_global_normal", 4, 5, "20 worker slots; keeps current process count"),
    ("experimental_13900ks_htoff_4x6_global_normal", 4, 6, "24 worker slots; higher memory/thermal risk"),
    ("experimental_13900ks_htoff_2x10_global_normal", 2, 10, "20 worker slots; low replication deeper search"),
    ("experimental_13900ks_htoff_2x12_global_normal", 2, 12, "24 worker slots; low process count high workers"),
    ("experimental_13900ks_htoff_1x16_global_normal", 1, 16, "single process deep-search contrast"),
    ("experimental_13900ks_htoff_1x24_global_normal", 1, 24, "single process max-thread short-test only"),
    ("experimental_13900ks_htoff_5x3_global_normal", 5, 3, "15 worker slots; more process replication"),
    ("experimental_13900ks_htoff_5x4_global_normal", 5, 4, "20 worker slots; RSS warning"),
)

STOP_CONDITIONS = (
    "peak_rss_gib_gt_42",
    "commit_charge_gib_gt_44",
    "pagefile_sustained_growth",
    "thermal_throttling_sustained",
    "canonical_path_mutation_detected",
    "system_or_codex_ui_unusable",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase3B S5 config-only matrix manifest without executing runs."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--baseline-scorecard", type=Path, default=DEFAULT_BASELINE_SCORECARD)
    parser.add_argument("--ai-dataset-summary", type=Path, default=DEFAULT_AI_DATASET_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    baseline_scorecard_path = _resolve_path(project_root, Path(args.baseline_scorecard))
    ai_dataset_summary_path = _resolve_path(project_root, Path(args.ai_dataset_summary))
    output_dir = _resolve_path(project_root, Path(args.output_dir))
    manifest = build_config_matrix_manifest(
        project_root=project_root,
        baseline_scorecard_path=baseline_scorecard_path,
        ai_dataset_summary_path=ai_dataset_summary_path,
    )
    print("phase3b config-only matrix manifest")
    print(f"profile_count={len(manifest['profiles'])}")
    print(f"execution_status={manifest['execution']['status']}")
    print(f"proof_source={manifest['safety']['proof_source']}")
    if not args.no_write:
        paths = write_config_matrix_manifest(manifest, output_dir)
        print(f"matrix_manifest_json={_display_path(project_root, Path(paths['json']))}")
        print(f"matrix_manifest_md={_display_path(project_root, Path(paths['md']))}")
    return 0


def build_config_matrix_manifest(
    *,
    project_root: Path,
    baseline_scorecard_path: Path,
    ai_dataset_summary_path: Path,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    scorecard = _load_json(baseline_scorecard_path)
    ai_dataset_summary = _load_optional_json(ai_dataset_summary_path)
    baseline_profile = _baseline_profile(scorecard)
    profiles = [
        _profile_entry(
            profile_id=profile_id,
            process_count=process_count,
            global_workers=global_workers,
            note=note,
            baseline_profile=baseline_profile,
        )
        for profile_id, process_count, global_workers, note in CONFIG_MATRIX_CANDIDATES
    ]
    return {
        "schema": "phase3b-config-only-matrix-manifest/v0",
        "generated_at": now_iso(),
        "matrix_kind": "s5_config_only_manifest",
        "execution": {
            "status": "not_executed_manifest_only",
            "fresh_solver_campaign_executed": False,
            "checkpoint_write_authorized": False,
            "true_matrix_runs_blocked": True,
            "blocked_reason": (
                "Config matrix candidates are prepared, but execution would require "
                "isolated short-run checkpoint writes or a checkpoint-free evaluator."
            ),
        },
        "source_artifacts": {
            "baseline_scorecard": _source_summary(baseline_scorecard_path),
            "ai_dataset_summary": _source_summary(ai_dataset_summary_path),
        },
        "baseline_reference": {
            "profile_id": baseline_profile.get("profile_id"),
            "process_count": baseline_profile.get("process_count"),
            "global_workers": baseline_profile.get("worker_count_per_process"),
            "peak_rss_gib": _mapping(baseline_profile.get("metrics")).get("peak_rss_gib"),
            "candidate_results_per_hour": _mapping(baseline_profile.get("metrics")).get(
                "candidate_results_per_hour"
            ),
        },
        "profiles": profiles,
        "readiness": {
            "ai_dataset_available": bool(ai_dataset_summary),
            "ai_dataset_sample_count": None
            if not isinstance(ai_dataset_summary, Mapping)
            else ai_dataset_summary.get("sample_count"),
            "recommended_first_profiles_when_authorized": [
                "B0_prod_4x4",
                "experimental_13900ks_htoff_3x6_global_normal",
                "experimental_13900ks_htoff_3x8_global_normal",
                "experimental_13900ks_htoff_2x10_global_normal",
            ],
        },
        "stop_conditions": list(STOP_CONDITIONS),
        "sensitive_path_audit": build_sensitive_path_audit(project_root),
        "safety": {
            "manifest_only": True,
            "proof_source": False,
            "production_profile_changed": False,
            "prod_4x4_normal_default_changed": False,
            "final_168h_started": False,
            "production_long_run_started": False,
            "checkpoint_written": False,
            "checkpoint_imported_back": False,
            "runtime_elimination_enabled": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
        },
    }


def write_config_matrix_manifest(manifest: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "matrix_manifest.json"
    md_path = output_dir / "matrix_manifest.md"
    atomic_write_json(json_path, dict(manifest))
    _atomic_write_text(md_path, render_config_matrix_manifest_markdown(manifest))
    return {"json": str(json_path), "md": str(md_path)}


def render_config_matrix_manifest_markdown(manifest: Mapping[str, Any]) -> str:
    execution = _mapping(manifest.get("execution"))
    lines = [
        "# Phase3B S5 Config-Only Matrix Manifest",
        "",
        f"- Execution status: `{execution.get('status')}`",
        f"- Fresh solver campaign executed: `{execution.get('fresh_solver_campaign_executed')}`",
        f"- Proof source: `{_mapping(manifest.get('safety')).get('proof_source')}`",
        f"- Blocked reason: {execution.get('blocked_reason')}",
        "",
        "| Profile | Processes | Global Workers | Worker Slots | Risk | Est. RSS GiB | Note |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for profile in manifest.get("profiles", []):
        if not isinstance(profile, Mapping):
            continue
        risk = _mapping(profile.get("risk"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(profile.get("profile_id")),
                    _markdown_cell(profile.get("process_count")),
                    _markdown_cell(profile.get("global_workers")),
                    _markdown_cell(profile.get("total_worker_slots")),
                    _markdown_cell(risk.get("level")),
                    _markdown_cell(profile.get("estimated_peak_rss_gib")),
                    _markdown_cell(profile.get("note")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            *[f"- `{condition}`" for condition in manifest.get("stop_conditions", [])],
        ]
    )
    return "\n".join(lines) + "\n"


def _profile_entry(
    *,
    profile_id: str,
    process_count: int,
    global_workers: int,
    note: str,
    baseline_profile: Mapping[str, Any],
) -> dict[str, Any]:
    total_worker_slots = int(process_count) * int(global_workers)
    estimated_rss_gib = _estimate_peak_rss_gib(
        process_count=process_count,
        global_workers=global_workers,
        baseline_profile=baseline_profile,
    )
    risk = _risk_assessment(
        process_count=process_count,
        global_workers=global_workers,
        total_worker_slots=total_worker_slots,
        estimated_peak_rss_gib=estimated_rss_gib,
    )
    return {
        "profile_id": profile_id,
        "process_count": int(process_count),
        "global_workers": int(global_workers),
        "total_worker_slots": int(total_worker_slots),
        "env": {"EXACT_CP_SAT_WORKERS": str(int(global_workers))},
        "process_priority": "normal",
        "frontier_probe_mode": "auto",
        "note": str(note),
        "estimated_peak_rss_gib": estimated_rss_gib,
        "risk": risk,
        "execution_status": "not_executed_manifest_only",
        "proof_source": False,
        "is_default_production": False,
        "candidate_command_template": [
            "python",
            "scripts/run_phase3b_local_tuning_profile.py",
            "--profile",
            profile_id,
            "--requires-future-runner-support",
        ],
    }


def _estimate_peak_rss_gib(
    *,
    process_count: int,
    global_workers: int,
    baseline_profile: Mapping[str, Any],
) -> float | None:
    metrics = _mapping(baseline_profile.get("metrics"))
    baseline_rss = _number_or_none(metrics.get("peak_rss_gib"))
    baseline_processes = _number_or_none(baseline_profile.get("process_count"))
    baseline_workers = _number_or_none(baseline_profile.get("worker_count_per_process"))
    if baseline_rss is None or not baseline_processes or not baseline_workers:
        return None
    process_factor = float(process_count) / float(baseline_processes)
    worker_factor = float(global_workers) / float(baseline_workers)
    # Process replication dominates memory; worker count mostly affects solver overhead.
    estimate = float(baseline_rss) * (0.75 * process_factor + 0.25 * worker_factor)
    return round(estimate, 6)


def _risk_assessment(
    *,
    process_count: int,
    global_workers: int,
    total_worker_slots: int,
    estimated_peak_rss_gib: float | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    level = "low"
    if total_worker_slots > 24:
        level = "high"
        reasons.append("worker_slots_gt_24")
    elif total_worker_slots > 20:
        level = "medium"
        reasons.append("worker_slots_gt_20")
    if process_count >= 5:
        level = _max_risk(level, "medium")
        reasons.append("process_count_ge_5")
    if global_workers >= 16:
        level = _max_risk(level, "medium")
        reasons.append("global_workers_ge_16")
    if estimated_peak_rss_gib is not None and estimated_peak_rss_gib > 42.0:
        level = "high"
        reasons.append("estimated_peak_rss_gt_42_gib")
    elif estimated_peak_rss_gib is not None and estimated_peak_rss_gib > 32.0:
        level = _max_risk(level, "medium")
        reasons.append("estimated_peak_rss_gt_32_gib")
    return {"level": level, "reasons": reasons}


def _max_risk(left: str, right: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return left if order[left] >= order[right] else right


def _baseline_profile(scorecard: Mapping[str, Any]) -> Mapping[str, Any]:
    requested = str(_mapping(scorecard.get("baseline")).get("profile_id") or "prod_4x4")
    for profile in scorecard.get("profiles", []) or []:
        if isinstance(profile, Mapping) and str(profile.get("profile_id")) == requested:
            return profile
    profiles = [profile for profile in scorecard.get("profiles", []) or [] if isinstance(profile, Mapping)]
    return profiles[0] if profiles else {}


def _source_summary(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": None}
    return {"path": str(path), "exists": True, "size_bytes": int(path.stat().st_size)}


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_optional_json(path: Path) -> Mapping[str, Any] | None:
    if not Path(path).exists():
        return None
    return _load_json(path)


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

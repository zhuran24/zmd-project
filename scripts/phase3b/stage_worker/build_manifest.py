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
DEFAULT_CONFIG_MATRIX_MANIFEST = ARTIFACT_ROOT / "04_config_matrix" / "matrix_manifest.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "05_stage_workers"

STAGE_WORKER_ENV = {
    "master": "EXACT_MASTER_CP_SAT_WORKERS",
    "local_capacity": "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
    "binding": "EXACT_BINDING_CP_SAT_WORKERS",
    "routing": "EXACT_ROUTING_CP_SAT_WORKERS",
}

STAGE_WORKER_CANDIDATES = (
    ("W0_prod_4x4_stage_4_4_4_4", 4, 4, 4, 4, 4, "current default baseline row"),
    ("W1_stage_4x_master6_local4_binding2_routing4", 4, 6, 4, 2, 4, "raise master, lower binding"),
    ("W2_stage_4x_master8_local4_binding2_routing4", 4, 8, 4, 2, 4, "master near built-in default"),
    ("W3_stage_4x_master6_local6_binding2_routing6", 4, 6, 6, 2, 6, "balanced stage-specific profile"),
    ("W4_stage_4x_master8_local6_binding2_routing6", 4, 8, 6, 2, 6, "master-heavy balanced profile"),
    ("W5_stage_3x_master8_local8_binding2_routing8", 3, 8, 8, 2, 8, "three-process high per-process profile"),
    ("W6_stage_3x_master8_local6_binding2_routing6", 3, 8, 6, 2, 6, "three-process conservative high-master profile"),
    ("W7_stage_2x_master12_local8_binding2_routing8", 2, 12, 8, 2, 8, "two-process deep-search profile"),
    ("W8_stage_2x_master16_local8_binding2_routing8", 2, 16, 8, 2, 8, "two-process very high master exploratory profile"),
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
        description="Build the Phase3B S6 stage-specific worker manifest without executing runs."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--baseline-scorecard", type=Path, default=DEFAULT_BASELINE_SCORECARD)
    parser.add_argument("--config-matrix-manifest", type=Path, default=DEFAULT_CONFIG_MATRIX_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    baseline_scorecard_path = _resolve_path(project_root, Path(args.baseline_scorecard))
    config_matrix_manifest_path = _resolve_path(project_root, Path(args.config_matrix_manifest))
    output_dir = _resolve_path(project_root, Path(args.output_dir))
    manifest = build_stage_worker_manifest(
        project_root=project_root,
        baseline_scorecard_path=baseline_scorecard_path,
        config_matrix_manifest_path=config_matrix_manifest_path,
    )
    print("phase3b stage-specific worker manifest")
    print(f"profile_count={len(manifest['profiles'])}")
    print(f"execution_status={manifest['execution']['status']}")
    print(f"proof_source={manifest['safety']['proof_source']}")
    if not args.no_write:
        paths = write_stage_worker_manifest(manifest, output_dir)
        print(f"stage_worker_manifest_json={_display_path(project_root, Path(paths['json']))}")
        print(f"stage_worker_manifest_md={_display_path(project_root, Path(paths['md']))}")
    return 0


def build_stage_worker_manifest(
    *,
    project_root: Path,
    baseline_scorecard_path: Path,
    config_matrix_manifest_path: Path,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    scorecard = _load_json(baseline_scorecard_path)
    config_manifest = _load_optional_json(config_matrix_manifest_path)
    baseline_profile = _baseline_profile(scorecard)
    profiles = [
        _profile_entry(
            profile_id=profile_id,
            process_count=process_count,
            master=master,
            local_capacity=local_capacity,
            binding=binding,
            routing=routing,
            purpose=purpose,
            baseline_profile=baseline_profile,
        )
        for profile_id, process_count, master, local_capacity, binding, routing, purpose
        in STAGE_WORKER_CANDIDATES
    ]
    return {
        "schema": "phase3b-stage-worker-manifest/v0",
        "generated_at": now_iso(),
        "matrix_kind": "s6_stage_specific_worker_manifest",
        "execution": {
            "status": "not_executed_manifest_only",
            "fresh_solver_campaign_executed": False,
            "checkpoint_write_authorized": False,
            "true_stage_worker_runs_blocked": True,
            "blocked_reason": (
                "Stage-specific worker candidates are prepared, but execution would require "
                "isolated short-run checkpoint writes or a checkpoint-free evaluator."
            ),
        },
        "source_artifacts": {
            "baseline_scorecard": _source_summary(baseline_scorecard_path),
            "config_matrix_manifest": _source_summary(config_matrix_manifest_path),
        },
        "baseline_reference": {
            "profile_id": baseline_profile.get("profile_id"),
            "process_count": baseline_profile.get("process_count"),
            "worker_count_per_process": baseline_profile.get("worker_count_per_process"),
            "peak_rss_gib": _mapping(baseline_profile.get("metrics")).get("peak_rss_gib"),
            "candidate_results_per_hour": _mapping(baseline_profile.get("metrics")).get(
                "candidate_results_per_hour"
            ),
        },
        "worker_env_precedence": [
            "stage-specific env",
            "EXACT_CP_SAT_WORKERS",
            "built-in defaults",
        ],
        "stage_env_names": dict(STAGE_WORKER_ENV),
        "profiles": profiles,
        "readiness": {
            "config_matrix_manifest_available": isinstance(config_manifest, Mapping),
            "config_matrix_profile_count": None
            if not isinstance(config_manifest, Mapping)
            else len(list(config_manifest.get("profiles", []) or [])),
            "recommended_first_profiles_when_authorized": [
                "W0_prod_4x4_stage_4_4_4_4",
                "W1_stage_4x_master6_local4_binding2_routing4",
                "W3_stage_4x_master6_local6_binding2_routing6",
                "W6_stage_3x_master8_local6_binding2_routing6",
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


def write_stage_worker_manifest(manifest: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "stage_worker_manifest.json"
    md_path = output_dir / "stage_worker_manifest.md"
    atomic_write_json(json_path, dict(manifest))
    _atomic_write_text(md_path, render_stage_worker_manifest_markdown(manifest))
    return {"json": str(json_path), "md": str(md_path)}


def render_stage_worker_manifest_markdown(manifest: Mapping[str, Any]) -> str:
    execution = _mapping(manifest.get("execution"))
    lines = [
        "# Phase3B S6 Stage-Specific Worker Manifest",
        "",
        f"- Execution status: `{execution.get('status')}`",
        f"- Fresh solver campaign executed: `{execution.get('fresh_solver_campaign_executed')}`",
        f"- Proof source: `{_mapping(manifest.get('safety')).get('proof_source')}`",
        f"- Blocked reason: {execution.get('blocked_reason')}",
        "",
        "| Profile | Proc | Master | Local | Binding | Routing | Max Slots | Risk | Est. RSS GiB | Purpose |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for profile in manifest.get("profiles", []):
        if not isinstance(profile, Mapping):
            continue
        workers = _mapping(profile.get("stage_workers"))
        risk = _mapping(profile.get("risk"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(profile.get("profile_id")),
                    _markdown_cell(profile.get("process_count")),
                    _markdown_cell(workers.get("master")),
                    _markdown_cell(workers.get("local_capacity")),
                    _markdown_cell(workers.get("binding")),
                    _markdown_cell(workers.get("routing")),
                    _markdown_cell(profile.get("max_stage_worker_slots")),
                    _markdown_cell(risk.get("level")),
                    _markdown_cell(profile.get("estimated_peak_rss_gib")),
                    _markdown_cell(profile.get("purpose")),
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
    master: int,
    local_capacity: int,
    binding: int,
    routing: int,
    purpose: str,
    baseline_profile: Mapping[str, Any],
) -> dict[str, Any]:
    stage_workers = {
        "master": int(master),
        "local_capacity": int(local_capacity),
        "binding": int(binding),
        "routing": int(routing),
    }
    max_stage_workers = max(stage_workers.values())
    stage_worker_sum = sum(stage_workers.values())
    max_stage_worker_slots = int(process_count) * int(max_stage_workers)
    estimated_rss_gib = _estimate_peak_rss_gib(
        process_count=process_count,
        max_stage_workers=max_stage_workers,
        stage_worker_sum=stage_worker_sum,
        baseline_profile=baseline_profile,
    )
    risk = _risk_assessment(
        process_count=process_count,
        max_stage_workers=max_stage_workers,
        max_stage_worker_slots=max_stage_worker_slots,
        estimated_peak_rss_gib=estimated_rss_gib,
    )
    env = {
        STAGE_WORKER_ENV["master"]: str(int(master)),
        STAGE_WORKER_ENV["local_capacity"]: str(int(local_capacity)),
        STAGE_WORKER_ENV["binding"]: str(int(binding)),
        STAGE_WORKER_ENV["routing"]: str(int(routing)),
    }
    return {
        "profile_id": profile_id,
        "process_count": int(process_count),
        "stage_workers": stage_workers,
        "stage_worker_sum_per_process": int(stage_worker_sum),
        "max_stage_workers_per_process": int(max_stage_workers),
        "max_stage_worker_slots": int(max_stage_worker_slots),
        "env": env,
        "process_priority": "normal",
        "frontier_probe_mode": "auto",
        "purpose": str(purpose),
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
            "--requires-future-stage-worker-runner-support",
        ],
    }


def _estimate_peak_rss_gib(
    *,
    process_count: int,
    max_stage_workers: int,
    stage_worker_sum: int,
    baseline_profile: Mapping[str, Any],
) -> float | None:
    metrics = _mapping(baseline_profile.get("metrics"))
    baseline_rss = _number_or_none(metrics.get("peak_rss_gib"))
    baseline_processes = _number_or_none(baseline_profile.get("process_count"))
    baseline_workers = _number_or_none(baseline_profile.get("worker_count_per_process"))
    if baseline_rss is None or not baseline_processes or not baseline_workers:
        return None
    process_factor = float(process_count) / float(baseline_processes)
    max_worker_factor = float(max_stage_workers) / float(baseline_workers)
    avg_worker_factor = float(stage_worker_sum) / (4.0 * float(baseline_workers))
    estimate = float(baseline_rss) * (
        0.70 * process_factor + 0.20 * max_worker_factor + 0.10 * avg_worker_factor
    )
    return round(estimate, 6)


def _risk_assessment(
    *,
    process_count: int,
    max_stage_workers: int,
    max_stage_worker_slots: int,
    estimated_peak_rss_gib: float | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    level = "low"
    if max_stage_worker_slots > 24:
        level = "high"
        reasons.append("max_stage_worker_slots_gt_24")
    elif max_stage_worker_slots > 20:
        level = "medium"
        reasons.append("max_stage_worker_slots_gt_20")
    if max_stage_workers >= 16:
        level = "high"
        reasons.append("max_stage_workers_ge_16")
    elif max_stage_workers >= 8:
        level = _max_risk(level, "medium")
        reasons.append("max_stage_workers_ge_8")
    if process_count >= 5:
        level = _max_risk(level, "medium")
        reasons.append("process_count_ge_5")
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

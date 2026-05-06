from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase3b_local_tuning_profile import ARTIFACT_ROOT
from src.search.exact_campaign import atomic_write_json, now_iso

DEFAULT_ACCEPTANCE_SUMMARY = Path(".codex_test_logs/phase3b/production_acceptance_after_change.json")
DEFAULT_TUNING_MATRIX_SUMMARY = ARTIFACT_ROOT / "10_final_recommendation" / "matrix_summary.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "03_baseline_reproduction"
DEFAULT_BASELINE_PROFILE_ID = "prod_4x4"

SENSITIVE_RELATIVE_PATHS = (
    "data/checkpoints/exact_campaign_state.json",
    "data/checkpoints/exact_campaign_telemetry.json",
    "data/solutions/final_solution.json",
    "data/blueprints/optimal_blueprint.json",
    "data/solutions/certified_delivery_manifest.json",
    ".artifacts/phase3b_long_run_preflight/preflight_summary.json",
    "data/examples/industrial_planner/current_delivery",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only Phase3B S3-lite baseline scorecard from existing "
            "production-acceptance evidence."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--acceptance-summary", type=Path, default=DEFAULT_ACCEPTANCE_SUMMARY)
    parser.add_argument("--tuning-matrix-summary", type=Path, default=DEFAULT_TUNING_MATRIX_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--baseline-profile-id", default=DEFAULT_BASELINE_PROFILE_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    acceptance_path = _resolve_path(project_root, Path(args.acceptance_summary))
    tuning_matrix_path = _resolve_path(project_root, Path(args.tuning_matrix_summary))
    output_dir = _resolve_path(project_root, Path(args.output_dir))
    scorecard = build_s3_lite_baseline_scorecard(
        project_root=project_root,
        acceptance_summary_path=acceptance_path,
        tuning_matrix_summary_path=tuning_matrix_path,
        baseline_profile_id=str(args.baseline_profile_id),
    )
    print("phase3b s3-lite baseline scorecard")
    print(f"evidence_kind={scorecard['metadata']['evidence_kind']}")
    print(f"profile_count={len(scorecard['profiles'])}")
    print(f"baseline_profile_id={scorecard['baseline']['profile_id']}")
    if not args.no_write:
        paths = write_s3_lite_baseline_scorecard(scorecard, output_dir)
        print(f"baseline_scorecard_json={_display_path(project_root, Path(paths['json']))}")
        print(f"baseline_scorecard_md={_display_path(project_root, Path(paths['md']))}")
    return 0


def build_s3_lite_baseline_scorecard(
    *,
    project_root: Path,
    acceptance_summary_path: Path,
    tuning_matrix_summary_path: Path,
    baseline_profile_id: str = DEFAULT_BASELINE_PROFILE_ID,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    acceptance_payload = _load_json(acceptance_summary_path)
    tuning_matrix_payload = _load_optional_json(tuning_matrix_summary_path)
    profiles = extract_acceptance_profiles(acceptance_payload)
    profiles = _attach_normalized_scores(profiles, baseline_profile_id=baseline_profile_id)
    baseline_profile = next(
        (profile for profile in profiles if profile["profile_id"] == baseline_profile_id),
        profiles[0] if profiles else None,
    )
    return {
        "schema": "phase3b-s3-lite-baseline-scorecard/v0",
        "metadata": {
            "generated_at": now_iso(),
            "evidence_kind": "evidence_replay_scorecard",
            "fresh_benchmark_executed": False,
            "proof_source": False,
            "production_long_run_started": False,
            "checkpoint_written": False,
            "project_root": str(project_root),
        },
        "source_artifacts": {
            "acceptance_summary": _source_artifact_summary(acceptance_summary_path),
            "tuning_matrix_summary": _source_artifact_summary(tuning_matrix_summary_path),
        },
        "baseline": {
            "requested_profile_id": str(baseline_profile_id),
            "profile_id": None if baseline_profile is None else str(baseline_profile["profile_id"]),
            "available": baseline_profile is not None,
        },
        "profiles": profiles,
        "local_tuning_smoke": _local_tuning_smoke_summary(tuning_matrix_payload),
        "sensitive_path_audit": build_sensitive_path_audit(project_root),
        "guard_notes": {
            "true_s3_rerun_blocked": True,
            "blocked_reason": (
                "Current checkpoint ban is treated as covering isolated benchmark workspace "
                "checkpoints; this scorecard only replays existing evidence."
            ),
            "fresh_rerun_requires": [
                "explicit authorization for isolated checkpoint writes",
                "or a checkpoint-free direct-evaluation runner",
            ],
        },
        "safety": {
            "final_168h_started": False,
            "final_168h_authorized": False,
            "production_long_run_started": False,
            "checkpoint_written": False,
            "checkpoint_imported_back": False,
            "runtime_elimination_enabled": False,
            "proof_source_mutated": False,
            "preflight_mutated": False,
            "release_viewer_frontdoor_promoted": False,
            "scorecard_is_proof_source": False,
        },
    }


def extract_acceptance_profiles(acceptance_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = [
        record
        for record in acceptance_payload.get("run_records", [])
        if isinstance(record, Mapping) and str(record.get("target", "")) == "production-campaign-run"
    ]
    profiles = [_profile_from_record(record) for record in records]
    return sorted(profiles, key=lambda profile: str(profile["profile_id"]))


def build_sensitive_path_audit(project_root: Path) -> dict[str, Any]:
    entries = []
    for relative_path in SENSITIVE_RELATIVE_PATHS:
        path = Path(project_root) / relative_path
        entries.append(_path_fingerprint(path, relative_path=relative_path))
    return {
        "schema": "phase3b-sensitive-path-audit/v0",
        "entries": entries,
        "canonical_checkpoint_exists": any(
            entry["exists"] and str(entry["relative_path"]).startswith("data/checkpoints/")
            for entry in entries
        ),
        "final_delivery_artifact_exists": any(
            entry["exists"]
            and str(entry["relative_path"])
            in {
                "data/solutions/final_solution.json",
                "data/blueprints/optimal_blueprint.json",
                "data/solutions/certified_delivery_manifest.json",
            }
            for entry in entries
        ),
    }


def write_s3_lite_baseline_scorecard(
    scorecard: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "baseline_scorecard.json"
    md_path = output_dir / "baseline_scorecard.md"
    atomic_write_json(json_path, dict(scorecard))
    _atomic_write_text(md_path, render_s3_lite_baseline_scorecard_markdown(scorecard))
    return {"json": str(json_path), "md": str(md_path)}


def render_s3_lite_baseline_scorecard_markdown(scorecard: Mapping[str, Any]) -> str:
    metadata = _mapping(scorecard.get("metadata"))
    guard_notes = _mapping(scorecard.get("guard_notes"))
    lines = [
        "# Phase3B S3-Lite Baseline Scorecard",
        "",
        f"- Evidence kind: `{metadata.get('evidence_kind')}`",
        f"- Fresh benchmark executed: `{metadata.get('fresh_benchmark_executed')}`",
        f"- Proof source: `{metadata.get('proof_source')}`",
        f"- True S3 rerun blocked: `{guard_notes.get('true_s3_rerun_blocked')}`",
        f"- Blocked reason: {guard_notes.get('blocked_reason')}",
        "",
        "| Profile | Completed | Campaign Valid | Duration s | Candidate/hour | UNKNOWN Density | Peak RSS GiB | Avg CPU % | Score |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile in scorecard.get("profiles", []):
        if not isinstance(profile, Mapping):
            continue
        metrics = _mapping(profile.get("metrics"))
        score = _mapping(profile.get("baseline_normalized_score"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(profile.get("profile_id")),
                    _markdown_cell(profile.get("completed")),
                    _markdown_cell(profile.get("campaign_valid_after_run")),
                    _markdown_cell(metrics.get("duration_seconds")),
                    _markdown_cell(metrics.get("candidate_results_per_hour")),
                    _markdown_cell(metrics.get("unknown_density")),
                    _markdown_cell(metrics.get("peak_rss_gib")),
                    _markdown_cell(metrics.get("avg_cpu_percent")),
                    _markdown_cell(score.get("score")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This scorecard replays existing evidence only.",
            "- It does not launch a solver campaign or write canonical checkpoints.",
            "- It is not certified proof and must not be connected to proof semantics.",
        ]
    )
    return "\n".join(lines) + "\n"


def _profile_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    campaign_summary = _mapping(record.get("campaign_telemetry_summary"))
    status_counts = _int_mapping(campaign_summary.get("status_counts"))
    candidate_result_count = _int_or_none(campaign_summary.get("candidate_result_count"))
    if candidate_result_count is None:
        candidate_result_count = sum(status_counts.values())
    unknown_count = int(status_counts.get("UNKNOWN", 0))
    duration_seconds = _first_number(
        record.get("elapsed_seconds_parent"),
        record.get("wall_seconds"),
        campaign_summary.get("wall_seconds"),
    )
    hours = None if duration_seconds is None or duration_seconds <= 0.0 else duration_seconds / 3600.0
    peak_rss_bytes = _first_int(
        record.get("peak_rss_bytes_external_total"),
        campaign_summary.get("peak_rss_bytes_external_total"),
        record.get("peak_rss_bytes_external"),
    )
    candidate_throughput_per_second = _first_number(record.get("candidate_throughput_per_second"))
    if candidate_throughput_per_second is None and duration_seconds and duration_seconds > 0:
        candidate_throughput_per_second = float(candidate_result_count) / float(duration_seconds)
    useful_terminal_count = max(int(candidate_result_count) - int(unknown_count), 0)
    metrics = {
        "duration_seconds": _round_or_none(duration_seconds),
        "candidate_result_count": int(candidate_result_count),
        "candidate_throughput_per_second": _round_or_none(candidate_throughput_per_second),
        "candidate_results_per_hour": _rate_per_hour(candidate_result_count, hours),
        "solve_attempt_count": int(_int_or_none(campaign_summary.get("solve_attempt_count")) or 0),
        "solve_attempts_per_hour": _rate_per_hour(
            _int_or_none(campaign_summary.get("solve_attempt_count")) or 0,
            hours,
        ),
        "precheck_elimination_count": int(
            _int_or_none(campaign_summary.get("precheck_elimination_count")) or 0
        ),
        "precheck_eliminations_per_hour": _rate_per_hour(
            _int_or_none(campaign_summary.get("precheck_elimination_count")) or 0,
            hours,
        ),
        "useful_terminal_result_count": useful_terminal_count,
        "useful_terminal_results_per_hour": _rate_per_hour(useful_terminal_count, hours),
        "unknown_count": unknown_count,
        "unknown_density": _ratio(unknown_count, candidate_result_count),
        "master_deterministic_time_sum": _round_or_none(
            _first_number(campaign_summary.get("master_deterministic_time_sum"))
        ),
        "peak_rss_bytes": peak_rss_bytes,
        "peak_rss_gib": _bytes_to_gib(peak_rss_bytes),
        "peak_internal_rss_bytes": _first_int(
            record.get("peak_rss_bytes_internal"),
            campaign_summary.get("peak_rss_bytes_internal_max_single_process"),
        ),
        "avg_cpu_percent": _round_or_none(_first_number(record.get("avg_process_cpu_pct"))),
    }
    return {
        "profile_id": str(record.get("label") or _infer_profile_id(record)),
        "target": str(record.get("target", "")),
        "completed": bool(record.get("completed", False)) and int(record.get("return_code", 0) or 0) == 0,
        "return_code": int(record.get("return_code", 0) or 0),
        "status": str(record.get("status", "")),
        "process_count": int(record.get("process_count", record.get("parallel_processes", 0)) or 0),
        "worker_count_per_process": _int_or_none(record.get("worker_count_per_process")),
        "worker_profile": dict(_mapping(record.get("worker_profile"))),
        "campaign_valid_after_run": bool(record.get("campaign_valid_after_run", False)),
        "campaign_write_mode": str(record.get("campaign_write_mode", "")),
        "status_counts": status_counts,
        "outcome_counts": _int_mapping(campaign_summary.get("outcome_counts")),
        "metrics": metrics,
        "source_paths": {
            "campaign_state_path": record.get("campaign_state_path"),
            "campaign_telemetry_path": record.get("campaign_telemetry_path"),
            "log_path": record.get("log_path"),
            "output_json": record.get("output_json"),
        },
    }


def _attach_normalized_scores(
    profiles: list[dict[str, Any]],
    *,
    baseline_profile_id: str,
) -> list[dict[str, Any]]:
    baseline = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == baseline_profile_id),
        profiles[0] if profiles else None,
    )
    for profile in profiles:
        profile["baseline_normalized_score"] = _baseline_normalized_score(profile, baseline)
    return profiles


def _baseline_normalized_score(
    profile: Mapping[str, Any],
    baseline: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if baseline is None:
        return {"score": None, "components": {}, "baseline_profile_id": None}
    metrics = _mapping(profile.get("metrics"))
    baseline_metrics = _mapping(baseline.get("metrics"))
    components = {
        "candidate_throughput": _positive_ratio(
            metrics.get("candidate_throughput_per_second"),
            baseline_metrics.get("candidate_throughput_per_second"),
        ),
        "duration_efficiency": _positive_ratio(
            baseline_metrics.get("duration_seconds"),
            metrics.get("duration_seconds"),
        ),
        "memory_efficiency": _positive_ratio(
            baseline_metrics.get("peak_rss_bytes"),
            metrics.get("peak_rss_bytes"),
        ),
        "unknown_quality": _positive_ratio(
            _non_unknown_fraction(metrics),
            _non_unknown_fraction(baseline_metrics),
        ),
        "useful_terminal_rate": _positive_ratio(
            metrics.get("useful_terminal_results_per_hour"),
            baseline_metrics.get("useful_terminal_results_per_hour"),
        ),
    }
    weights = {
        "candidate_throughput": 0.35,
        "duration_efficiency": 0.2,
        "memory_efficiency": 0.15,
        "unknown_quality": 0.15,
        "useful_terminal_rate": 0.15,
    }
    weighted = [
        (float(value), float(weights[name]))
        for name, value in components.items()
        if value is not None and name in weights
    ]
    if not weighted:
        score = None
    else:
        score = sum(value * weight for value, weight in weighted) / sum(
            weight for _value, weight in weighted
        )
    return {
        "score": _round_or_none(score),
        "components": {name: _round_or_none(value) for name, value in components.items()},
        "baseline_profile_id": str(baseline.get("profile_id")),
    }


def _local_tuning_smoke_summary(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"available": False, "run_count": 0, "safety": {}}
    runs = [run for run in payload.get("runs", []) if isinstance(run, Mapping)]
    return {
        "available": True,
        "run_count": int(payload.get("run_count", len(runs)) or 0),
        "profile_ids": [str(run.get("profile_id")) for run in runs],
        "safety": dict(_mapping(payload.get("safety"))),
    }


def _path_fingerprint(path: Path, *, relative_path: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "relative_path": str(relative_path).replace("\\", "/"),
            "path": str(path),
            "exists": False,
            "kind": "missing",
            "size_bytes": None,
            "mtime_ns": None,
            "sha256": None,
        }
    stat = path.stat()
    if path.is_file():
        kind = "file"
        size_bytes = int(stat.st_size)
        sha256 = _sha256_file(path)
    elif path.is_dir():
        kind = "directory"
        size_bytes = None
        sha256 = None
    else:
        kind = "other"
        size_bytes = None
        sha256 = None
    return {
        "relative_path": str(relative_path).replace("\\", "/"),
        "path": str(path),
        "exists": True,
        "kind": kind,
        "size_bytes": size_bytes,
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256,
    }


def _source_artifact_summary(path: Path) -> dict[str, Any]:
    return _path_fingerprint(Path(path), relative_path=str(path))


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


def _infer_profile_id(record: Mapping[str, Any]) -> str:
    process_count = int(record.get("process_count", record.get("parallel_processes", 0)) or 0)
    worker_count = _int_or_none(record.get("worker_count_per_process"))
    if worker_count is None:
        worker_profile = _mapping(record.get("worker_profile"))
        worker_count = _int_or_none(worker_profile.get("master")) or 0
    return f"prod_{process_count}x{worker_count}"


def _rate_per_hour(count: int | float, hours: float | None) -> float | None:
    if hours is None or hours <= 0.0:
        return None
    return round(float(count) / float(hours), 6)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if float(denominator) <= 0.0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _positive_ratio(value: Any, baseline_value: Any) -> float | None:
    value_float = _first_number(value)
    baseline_float = _first_number(baseline_value)
    if value_float is None or baseline_float is None or baseline_float <= 0.0:
        return None
    return float(value_float) / float(baseline_float)


def _non_unknown_fraction(metrics: Mapping[str, Any]) -> float | None:
    unknown_density = _first_number(metrics.get("unknown_density"))
    if unknown_density is None:
        return None
    return max(1.0 - float(unknown_density), 0.0)


def _bytes_to_gib(value: int | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / (1024 ** 3), 6)


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except Exception:
            continue
    return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except Exception:
            continue
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, raw_value in value.items():
        parsed = _int_or_none(raw_value)
        if parsed is not None:
            result[str(key)] = parsed
    return result


def _round_or_none(value: Any, *, digits: int = 6) -> float | None:
    number = _first_number(value)
    if number is None:
        return None
    return round(float(number), int(digits))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

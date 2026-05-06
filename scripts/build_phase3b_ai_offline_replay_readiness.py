from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_phase3b_s3_lite_baseline_scorecard import build_sensitive_path_audit
from scripts.run_phase3b_local_tuning_profile import ARTIFACT_ROOT
from src.ai_accel.feature_extract import stable_json_dumps
from src.search.exact_campaign import atomic_write_json, now_iso

DEFAULT_CANDIDATE_RUNS = Path(".artifacts/phase3b_ai_accel_20260430/01_feature_dataset/candidate_runs.jsonl")
DEFAULT_DATASET_SUMMARY = Path(".artifacts/phase3b_ai_accel_20260430/01_feature_dataset/dataset_summary.json")
DEFAULT_BASELINE_SCORECARD = ARTIFACT_ROOT / "03_baseline_reproduction" / "baseline_scorecard.json"
DEFAULT_CONFIG_MATRIX_MANIFEST = ARTIFACT_ROOT / "04_config_matrix" / "matrix_manifest.json"
DEFAULT_STAGE_WORKER_MANIFEST = ARTIFACT_ROOT / "05_stage_workers" / "stage_worker_manifest.json"
DEFAULT_PRIORITY_AFFINITY_MANIFEST = ARTIFACT_ROOT / "06_priority_affinity" / "affinity_priority_manifest.json"
DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_ai_accel_20260430/02_offline_replay_readiness")
AI_NAMESPACE = "phase3b_ai_accel_20260430"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase3B S9-lite AI offline replay readiness artifacts without training a model."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate-runs", type=Path, default=DEFAULT_CANDIDATE_RUNS)
    parser.add_argument("--dataset-summary", type=Path, default=DEFAULT_DATASET_SUMMARY)
    parser.add_argument("--baseline-scorecard", type=Path, default=DEFAULT_BASELINE_SCORECARD)
    parser.add_argument("--config-matrix-manifest", type=Path, default=DEFAULT_CONFIG_MATRIX_MANIFEST)
    parser.add_argument("--stage-worker-manifest", type=Path, default=DEFAULT_STAGE_WORKER_MANIFEST)
    parser.add_argument("--priority-affinity-manifest", type=Path, default=DEFAULT_PRIORITY_AFFINITY_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    readiness = build_ai_offline_replay_readiness(
        project_root=project_root,
        candidate_runs_path=_resolve_path(project_root, Path(args.candidate_runs)),
        dataset_summary_path=_resolve_path(project_root, Path(args.dataset_summary)),
        baseline_scorecard_path=_resolve_path(project_root, Path(args.baseline_scorecard)),
        config_matrix_manifest_path=_resolve_path(project_root, Path(args.config_matrix_manifest)),
        stage_worker_manifest_path=_resolve_path(project_root, Path(args.stage_worker_manifest)),
        priority_affinity_manifest_path=_resolve_path(project_root, Path(args.priority_affinity_manifest)),
    )
    print("phase3b ai offline replay readiness")
    print(f"sample_count={readiness['coverage']['sample_count']}")
    print(f"candidate_count={readiness['coverage']['candidate_count']}")
    print(f"readiness_status={readiness['readiness']['status']}")
    print(f"model_trained={readiness['safety']['model_trained']}")
    print(f"proof_source={readiness['safety']['proof_source']}")
    if not args.no_write:
        paths = write_ai_offline_replay_readiness(
            readiness,
            _resolve_path(project_root, Path(args.output_dir)),
        )
        print(f"offline_replay_readiness_json={_display_path(project_root, Path(paths['json']))}")
        print(f"offline_replay_readiness_md={_display_path(project_root, Path(paths['md']))}")
    return 0


def build_ai_offline_replay_readiness(
    *,
    project_root: Path,
    candidate_runs_path: Path,
    dataset_summary_path: Path,
    baseline_scorecard_path: Path,
    config_matrix_manifest_path: Path,
    stage_worker_manifest_path: Path,
    priority_affinity_manifest_path: Path,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    samples = read_candidate_runs_jsonl(candidate_runs_path)
    dataset_summary = _load_optional_json(dataset_summary_path)
    coverage = _coverage_summary(samples)
    missing_telemetry = _missing_telemetry_summary(samples)
    leakage = _leakage_risk_summary(samples)
    return {
        "schema": "phase3b-ai-offline-replay-readiness/v0",
        "generated_at": now_iso(),
        "readiness_kind": "s9_lite_offline_replay_readiness",
        "source_artifacts": {
            "candidate_runs": _source_summary(candidate_runs_path),
            "dataset_summary": _source_summary(dataset_summary_path),
            "baseline_scorecard": _source_summary(baseline_scorecard_path),
            "config_matrix_manifest": _source_summary(config_matrix_manifest_path),
            "stage_worker_manifest": _source_summary(stage_worker_manifest_path),
            "priority_affinity_manifest": _source_summary(priority_affinity_manifest_path),
        },
        "dataset_summary": _compact_dataset_summary(dataset_summary),
        "coverage": coverage,
        "missing_telemetry": missing_telemetry,
        "leakage_risk": leakage,
        "readiness": {
            "status": _readiness_status(coverage, missing_telemetry),
            "offline_replay_input_available": coverage["sample_count"] > 0,
            "training_allowed": False,
            "scheduler_integration_allowed": False,
            "candidate_order_change_allowed": False,
            "reason": (
                "This artifact only checks replay inputs. Model training, scheduler integration, "
                "and candidate ordering changes remain out of scope."
            ),
        },
        "sensitive_path_audit": build_sensitive_path_audit(project_root),
        "safety": {
            "shadow_only": True,
            "readiness_only": True,
            "proof_source": False,
            "model_trained": False,
            "scheduler_integration": False,
            "candidate_order_changed": False,
            "candidate_universe_changed": False,
            "checkpoint_written": False,
            "checkpoint_imported_back": False,
            "final_solution_written": False,
            "runtime_elimination_enabled": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
        },
    }


def write_ai_offline_replay_readiness(
    readiness: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    _assert_output_namespace(output_dir, AI_NAMESPACE)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "offline_replay_readiness.json"
    md_path = output_dir / "offline_replay_readiness.md"
    atomic_write_json(json_path, dict(readiness))
    _atomic_write_text(md_path, render_ai_offline_replay_readiness_markdown(readiness))
    return {"json": str(json_path), "md": str(md_path)}


def render_ai_offline_replay_readiness_markdown(readiness: Mapping[str, Any]) -> str:
    coverage = _mapping(readiness.get("coverage"))
    missing = _mapping(readiness.get("missing_telemetry"))
    safety = _mapping(readiness.get("safety"))
    status_counts = _mapping(coverage.get("status_counts"))
    lines = [
        "# Phase3B S9-Lite Offline Replay Readiness",
        "",
        f"- Readiness kind: `{readiness.get('readiness_kind')}`",
        f"- Status: `{_mapping(readiness.get('readiness')).get('status')}`",
        f"- Sample count: `{coverage.get('sample_count')}`",
        f"- Candidate count: `{coverage.get('candidate_count')}`",
        f"- Model trained: `{safety.get('model_trained')}`",
        f"- Scheduler integration: `{safety.get('scheduler_integration')}`",
        f"- Proof source: `{safety.get('proof_source')}`",
        "",
        "## Status Coverage",
        "",
        "| Status | Samples |",
        "| --- | ---: |",
    ]
    for status, count in status_counts.items():
        lines.append(f"| {_markdown_cell(status)} | {int(count)} |")
    lines.extend(
        [
            "",
            "## Missing Telemetry",
            "",
            "| Field | Missing Samples |",
            "| --- | ---: |",
        ]
    )
    for field, count in _mapping(missing.get("missing_counts")).items():
        lines.append(f"| {_markdown_cell(field)} | {int(count)} |")
    return "\n".join(lines) + "\n"


def read_candidate_runs_jsonl(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    samples: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, Mapping):
            samples.append(dict(payload))
    return sorted(samples, key=_sample_sort_key)


def _coverage_summary(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    sample_list = [dict(sample) for sample in samples]
    profile_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    candidate_keys: set[str] = set()
    for sample in sample_list:
        profile_id = str(sample.get("profile_id") or "")
        profile_counts[profile_id] = profile_counts.get(profile_id, 0) + 1
        candidate_key = str(sample.get("candidate_key") or "")
        if candidate_key:
            candidate_keys.add(candidate_key)
        terminal = _mapping(sample.get("terminal"))
        status = str(terminal.get("status") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
        labels = _mapping(sample.get("labels"))
        for label, value in labels.items():
            if bool(value):
                label_counts[str(label)] = label_counts.get(str(label), 0) + 1
    return {
        "sample_count": len(sample_list),
        "profile_count": len([key for key in profile_counts if key]),
        "candidate_count": len(candidate_keys),
        "profile_counts": dict(sorted(profile_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
    }


def _sample_sort_key(sample: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(sample.get("profile_id") or ""),
        str(sample.get("candidate_key") or ""),
        str(sample.get("sample_id") or stable_json_dumps(sample)),
    )


def _missing_telemetry_summary(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    sample_list = [dict(sample) for sample in samples]
    checks = {
        "resource_metrics.avg_process_cpu_percent": lambda sample: _mapping(sample.get("resource_metrics")).get("avg_process_cpu_percent"),
        "resource_metrics.peak_rss_gib_record": lambda sample: _mapping(sample.get("resource_metrics")).get("peak_rss_gib_record"),
        "resource_metrics.rss_gib_at_window": lambda sample: _mapping(sample.get("resource_metrics")).get("rss_gib_at_window"),
        "solver_metrics.wall_time": lambda sample: _mapping(sample.get("solver_metrics")).get("wall_time"),
        "solver_metrics.deterministic_time": lambda sample: _mapping(sample.get("solver_metrics")).get("deterministic_time"),
        "frontier_candidate_metrics": lambda sample: sample.get("frontier_candidate_metrics") or None,
    }
    missing_counts: dict[str, int] = {}
    for field, getter in checks.items():
        missing_counts[field] = sum(1 for sample in sample_list if getter(sample) in (None, {}, []))
    return {
        "sample_count": len(sample_list),
        "missing_counts": missing_counts,
        "all_required_for_readiness_present": bool(sample_list)
        and missing_counts["frontier_candidate_metrics"] < len(sample_list),
    }


def _leakage_risk_summary(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    sample_list = [dict(sample) for sample in samples]
    risks: list[str] = []
    if any(_mapping(sample.get("labels")) for sample in sample_list):
        risks.append("outcome_labels_present_use_only_as_labels_not_features")
    if any(_mapping(sample.get("terminal")).get("status") for sample in sample_list):
        risks.append("terminal_status_present_use_only_as_label_or_replay_outcome")
    if len(sample_list) < 100:
        risks.append("small_sample_count_requires_evidence_replay_only")
    profile_count = len({str(sample.get("profile_id") or "") for sample in sample_list if sample.get("profile_id")})
    if profile_count < 3:
        risks.append("low_profile_diversity")
    return {
        "risk_level": "medium" if risks else "low",
        "risks": risks,
        "required_controls_before_training": [
            "time_or_run_split",
            "feature_whitelist_excluding_terminal_outcomes",
            "candidate_universe_hash_check",
            "deterministic_replay_order_check",
        ],
    }


def _readiness_status(
    coverage: Mapping[str, Any],
    missing_telemetry: Mapping[str, Any],
) -> str:
    if int(coverage.get("sample_count") or 0) <= 0:
        return "blocked_missing_candidate_runs"
    if int(coverage.get("profile_count") or 0) < 2:
        return "limited_single_profile_replay_input"
    if not bool(missing_telemetry.get("all_required_for_readiness_present")):
        return "limited_optional_telemetry_missing"
    return "ready_for_read_only_offline_replay_planning"


def _compact_dataset_summary(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(summary, Mapping):
        return {"available": False}
    return {
        "available": True,
        "schema": summary.get("schema"),
        "sample_schema": summary.get("sample_schema"),
        "sample_count": summary.get("sample_count"),
        "dataset_kind": summary.get("dataset_kind"),
        "safety": dict(_mapping(summary.get("safety"))),
    }


def _source_summary(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": None}
    return {"path": str(path), "exists": True, "size_bytes": int(path.stat().st_size)}


def _load_optional_json(path: Path) -> Mapping[str, Any] | None:
    if not Path(path).exists():
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


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


def _assert_output_namespace(output_dir: Path, namespace: str) -> None:
    parts = set(Path(output_dir).parts)
    if ".artifacts" not in parts or namespace not in parts:
        raise ValueError(f"output_dir must be under .artifacts/{namespace}: {output_dir}")


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

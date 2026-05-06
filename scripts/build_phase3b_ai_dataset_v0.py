from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_phase3b_s3_lite_baseline_scorecard import (
    build_sensitive_path_audit,
)
from src.ai_accel.feature_extract import (
    build_feature_dataset_summary,
    build_feature_schema,
    extract_candidate_run_samples,
    render_dataset_summary_markdown,
    stable_json_dumps,
    write_candidate_runs_jsonl,
)
from src.search.exact_campaign import atomic_write_json

DEFAULT_ACCEPTANCE_SUMMARY = Path(".codex_test_logs/phase3b/production_acceptance_after_change.json")
DEFAULT_BASELINE_SCORECARD = Path(
    ".artifacts/phase3b_local_13900ks_tuning_20260430/03_baseline_reproduction/baseline_scorecard.json"
)
DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_ai_accel_20260430/01_feature_dataset")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase3B AI dataset v0 shadow feature artifacts."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--acceptance-summary", type=Path, default=DEFAULT_ACCEPTANCE_SUMMARY)
    parser.add_argument("--baseline-scorecard", type=Path, default=DEFAULT_BASELINE_SCORECARD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    acceptance_path = _resolve_path(project_root, Path(args.acceptance_summary))
    scorecard_path = _resolve_path(project_root, Path(args.baseline_scorecard))
    output_dir = _resolve_path(project_root, Path(args.output_dir))
    dataset = build_phase3b_ai_dataset_v0(
        project_root=project_root,
        acceptance_summary_path=acceptance_path,
        baseline_scorecard_path=scorecard_path,
    )
    print("phase3b ai dataset v0 shadow")
    print(f"sample_count={dataset['summary']['sample_count']}")
    print(f"dataset_kind={dataset['summary']['dataset_kind']}")
    print(f"proof_source={dataset['summary']['safety']['proof_source']}")
    if not args.no_write:
        paths = write_phase3b_ai_dataset_v0(dataset, output_dir)
        print(f"candidate_runs_jsonl={_display_path(project_root, Path(paths['candidate_runs_jsonl']))}")
        print(f"feature_schema_json={_display_path(project_root, Path(paths['feature_schema_json']))}")
        print(f"dataset_summary_json={_display_path(project_root, Path(paths['dataset_summary_json']))}")
        print(f"dataset_summary_md={_display_path(project_root, Path(paths['dataset_summary_md']))}")
    return 0


def build_phase3b_ai_dataset_v0(
    *,
    project_root: Path,
    acceptance_summary_path: Path,
    baseline_scorecard_path: Path,
) -> dict[str, Any]:
    acceptance_payload = _load_json(acceptance_summary_path)
    scorecard_payload = _load_json(baseline_scorecard_path)
    samples = extract_candidate_run_samples(
        acceptance_payload,
        scorecard_payload=scorecard_payload,
    )
    summary = build_feature_dataset_summary(
        samples,
        acceptance_summary_path=acceptance_summary_path,
        scorecard_path=baseline_scorecard_path,
    )
    summary["sensitive_path_audit"] = build_sensitive_path_audit(Path(project_root).resolve())
    return {
        "samples": samples,
        "feature_schema": build_feature_schema(),
        "summary": summary,
    }


def write_phase3b_ai_dataset_v0(
    dataset: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_runs_path = output_dir / "candidate_runs.jsonl"
    feature_schema_path = output_dir / "feature_schema.json"
    summary_json_path = output_dir / "dataset_summary.json"
    summary_md_path = output_dir / "dataset_summary.md"
    samples = list(dataset.get("samples", []))
    write_candidate_runs_jsonl(candidate_runs_path, samples)
    atomic_write_json(feature_schema_path, _mapping(dataset.get("feature_schema")))
    atomic_write_json(summary_json_path, _mapping(dataset.get("summary")))
    _atomic_write_text(summary_md_path, render_dataset_summary_markdown(_mapping(dataset.get("summary"))))
    return {
        "candidate_runs_jsonl": str(candidate_runs_path),
        "feature_schema_json": str(feature_schema_path),
        "dataset_summary_json": str(summary_json_path),
        "dataset_summary_md": str(summary_md_path),
    }


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
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


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def render_samples_for_test(samples: list[Mapping[str, Any]]) -> str:
    return "".join(stable_json_dumps(sample) + "\n" for sample in samples)


if __name__ == "__main__":
    raise SystemExit(main())

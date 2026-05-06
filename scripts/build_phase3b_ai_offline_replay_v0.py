from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_phase3b_s3_lite_baseline_scorecard import build_sensitive_path_audit
from src.ai_accel.replay_scheduler import (
    build_offline_replay_report,
    read_candidate_runs_jsonl,
    render_offline_replay_markdown,
)
from src.search.exact_campaign import atomic_write_json

DEFAULT_CANDIDATE_RUNS = Path(".artifacts/phase3b_ai_accel_20260430/01_feature_dataset/candidate_runs.jsonl")
DEFAULT_REPLAY_READINESS = Path(
    ".artifacts/phase3b_ai_accel_20260430/02_offline_replay_readiness/offline_replay_readiness.json"
)
DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_ai_accel_20260430/03_offline_replay_v0")
AI_NAMESPACE = "phase3b_ai_accel_20260430"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase3B S9 deterministic offline replay v0 artifacts without training a model."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate-runs", type=Path, default=DEFAULT_CANDIDATE_RUNS)
    parser.add_argument("--replay-readiness", type=Path, default=DEFAULT_REPLAY_READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    candidate_runs_path = _resolve_path(project_root, Path(args.candidate_runs))
    readiness_path = _resolve_path(project_root, Path(args.replay_readiness))
    output_dir = _resolve_path(project_root, Path(args.output_dir))
    report = build_phase3b_ai_offline_replay_v0(
        project_root=project_root,
        candidate_runs_path=candidate_runs_path,
        replay_readiness_path=readiness_path,
    )
    print("phase3b ai offline replay v0")
    print(f"sample_count={report['sample_count']}")
    print(f"profile_count={report['profile_count']}")
    print(f"best_policy={report['best_policy']['policy']}")
    print(f"order_only_ab_eligible={report['recommendation']['order_only_ab_eligible']}")
    print(f"model_trained={report['safety']['model_trained']}")
    print(f"proof_source={report['safety']['proof_source']}")
    if not args.no_write:
        paths = write_phase3b_ai_offline_replay_v0(report, output_dir)
        print(f"offline_replay_report_json={_display_path(project_root, Path(paths['json']))}")
        print(f"offline_replay_report_md={_display_path(project_root, Path(paths['md']))}")
    return 0


def build_phase3b_ai_offline_replay_v0(
    *,
    project_root: Path,
    candidate_runs_path: Path,
    replay_readiness_path: Path,
) -> dict[str, Any]:
    samples = read_candidate_runs_jsonl(candidate_runs_path)
    readiness_payload = _load_optional_json(replay_readiness_path)
    report = build_offline_replay_report(
        samples,
        source_artifacts={
            "candidate_runs": _source_summary(candidate_runs_path),
            "replay_readiness": _source_summary(replay_readiness_path),
        },
        readiness_payload=readiness_payload,
    )
    report["sensitive_path_audit"] = build_sensitive_path_audit(Path(project_root).resolve())
    return report


def write_phase3b_ai_offline_replay_v0(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    _assert_output_namespace(output_dir, AI_NAMESPACE)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "offline_replay_report.json"
    md_path = output_dir / "offline_replay_report.md"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(md_path, render_offline_replay_markdown(report))
    return {"json": str(json_path), "md": str(md_path)}


def _source_summary(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": None, "sha256": None}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(path.stat().st_size),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


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


if __name__ == "__main__":
    raise SystemExit(main())

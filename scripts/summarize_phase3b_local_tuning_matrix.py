from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase3b_local_tuning_profile import ARTIFACT_ROOT, LOG_ROOT
from src.search.exact_campaign import atomic_write_json, now_iso


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Phase3B local 13900KS tuning run artifacts."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--log-root", type=Path, default=LOG_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACT_ROOT / "10_final_recommendation",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    artifact_root = _resolve_output_dir(project_root, Path(args.artifact_root))
    log_root = _resolve_output_dir(project_root, Path(args.log_root))
    summary = build_tuning_matrix_summary(
        project_root=project_root,
        artifact_root=artifact_root,
        log_root=log_root,
    )
    print("phase3b local tuning matrix")
    print(f"run_count={summary['run_count']}")
    print(f"artifact_root={_display_path(project_root, artifact_root)}")
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, Path(args.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "matrix_summary.json"
        md_path = output_dir / "matrix_summary.md"
        atomic_write_json(json_path, summary)
        _atomic_write_text(md_path, render_tuning_matrix_markdown(summary))
        print(f"matrix_summary_json={_display_path(project_root, json_path)}")
        print(f"matrix_summary_md={_display_path(project_root, md_path)}")
    return 0


def build_tuning_matrix_summary(
    *,
    project_root: Path,
    artifact_root: Path,
    log_root: Path,
) -> dict[str, Any]:
    runs = _load_run_summaries(artifact_root)
    return {
        "schema": "phase3b-local-tuning-matrix-summary/v0",
        "generated_at": now_iso(),
        "project_root": str(Path(project_root).resolve()),
        "artifact_root": str(Path(artifact_root).resolve()),
        "log_root": str(Path(log_root).resolve()),
        "run_count": len(runs),
        "runs": runs,
        "best_completed_by_duration": _best_completed_by_duration(runs),
        "safety": {
            "final_168h_started": False,
            "production_long_run_started": False,
            "checkpoint_written": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
            "summary_is_proof_source": False,
        },
    }


def render_tuning_matrix_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Phase3B Local Tuning Matrix Summary",
        "",
        f"- Run count: `{summary.get('run_count')}`",
        f"- Best completed by duration: `{_mapping(summary.get('best_completed_by_duration')).get('run_id')}`",
        "",
        "| Profile | Run ID | Status | Duration s | Peak RSS bytes | Peak CPU % |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for run in summary.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        telemetry = _mapping(run.get("telemetry_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(run.get("profile_id")),
                    _markdown_cell(run.get("run_id")),
                    _markdown_cell(run.get("status")),
                    _markdown_cell(run.get("duration_seconds")),
                    _markdown_cell(telemetry.get("peak_total_rss_bytes", 0)),
                    _markdown_cell(telemetry.get("peak_total_cpu_percent", 0.0)),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _load_run_summaries(artifact_root: Path) -> list[dict[str, Any]]:
    root = Path(artifact_root)
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for summary_path in sorted(root.glob("*/run_summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            runs.append(payload)
    return runs


def _best_completed_by_duration(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed = [
        run for run in runs if run.get("status") in {"completed", "skipped_no_execute"}
    ]
    if not completed:
        return None
    return min(completed, key=lambda run: float(run.get("duration_seconds", 0.0) or 0.0))


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


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

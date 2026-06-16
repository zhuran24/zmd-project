from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.zero_branch.zero_branch_unknown_triage import (
    DEFAULT_FAILED_ANCHOR_INVENTORY_PATH,
    DEFAULT_MODEL_SLICE_DIR,
    DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    DEFAULT_SOLVER_MATRIX_PATH,
    build_phase3b_zero_branch_unknown_triage,
    render_phase3b_zero_branch_unknown_triage_markdown,
    render_phase3b_zero_branch_unknown_triage_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B zero-branch UNKNOWN triage from solver matrix and model-slice diagnostics."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--solver-matrix", type=Path, default=DEFAULT_SOLVER_MATRIX_PATH)
    parser.add_argument("--model-slice-dir", type=Path, default=DEFAULT_MODEL_SLICE_DIR)
    parser.add_argument(
        "--failed-anchor-inventory",
        type=Path,
        default=DEFAULT_FAILED_ANCHOR_INVENTORY_PATH,
    )
    parser.add_argument(
        "--power-coverage-anchor-delta",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_zero_branch_unknown_triage"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_zero_branch_unknown_triage(
        project_root,
        solver_matrix_path=args.solver_matrix,
        model_slice_dir=args.model_slice_dir,
        failed_anchor_inventory_path=args.failed_anchor_inventory,
        power_coverage_anchor_delta_path=args.power_coverage_anchor_delta,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "zero_branch_unknown_triage.json"
        md_path = output_dir / "zero_branch_unknown_triage.md"
        txt_path = output_dir / "zero_branch_unknown_triage.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_zero_branch_unknown_triage_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_zero_branch_unknown_triage_text(report))
        print(f"zero_branch_unknown_triage_json={_display_path(project_root, json_path)}")
        print(f"zero_branch_unknown_triage_md={_display_path(project_root, md_path)}")
        print(f"zero_branch_unknown_triage_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    matrix = _mapping(report.get("matrix"))
    power_delta = _mapping(report.get("power_coverage_anchor_delta"))
    model_slice = _mapping(report.get("model_slice"))
    print("phase3b zero-branch UNKNOWN triage")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- zero-branch UNKNOWN: {matrix.get('zero_branch_unknown_count', 0)}")
    print(f"- power family changed count: {power_delta.get('power_family_changed_count', 0)}")
    print(f"- power-delta findings: {power_delta.get('diagnostic_findings', [])}")
    print(f"- model-slice findings: {model_slice.get('diagnostic_findings', [])}")
    print(f"- recommendation: {report.get('recommendation')}")


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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

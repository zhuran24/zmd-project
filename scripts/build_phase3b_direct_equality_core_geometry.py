from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_direct_equality_core_geometry import (
    build_phase3b_direct_equality_core_geometry_report,
    render_phase3b_direct_equality_core_geometry_markdown,
    render_phase3b_direct_equality_core_geometry_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve geometry report for Phase 3B direct-equality cores."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--core-json",
        action="append",
        default=[],
        help="Direct-equality core JSON. May be repeated.",
    )
    parser.add_argument(
        "--candidate-placements",
        type=Path,
        default=Path("data/preprocessed/candidate_placements.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_direct_equality_core_geometry"),
    )
    parser.add_argument("--output-prefix", default="direct_equality_core_geometry")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    core_paths = [Path(item) for item in args.core_json]
    if not core_paths:
        core_paths = [
            Path(
                ".artifacts/phase3b_direct_equality_core_anchor_sweep_118_125/"
                "core_m5x5_planter_sandleaf_anchor119.json"
            ),
            Path(
                ".artifacts/phase3b_direct_equality_core_anchor_sweep_118_125/"
                "core_m6x4_grinder_dense_blue_iron_anchor119.json"
            ),
        ]
    report = build_phase3b_direct_equality_core_geometry_report(
        project_root,
        core_paths=core_paths,
        candidate_placements_path=args.candidate_placements,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = str(args.output_prefix)
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_direct_equality_core_geometry_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_direct_equality_core_geometry_text(report),
        )
        print(f"direct_equality_core_geometry_json={_display_path(project_root, json_path)}")
        print(f"direct_equality_core_geometry_md={_display_path(project_root, md_path)}")
        print(f"direct_equality_core_geometry_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: dict) -> None:
    summary = report.get("summary", {})
    print("phase3b direct-equality core geometry")
    print("- diagnostic semantics: no_solve_geometry_explanation_not_proof_source")
    print("- solver invoked: false")
    print(f"- core count: {summary.get('core_count')}")
    print(f"- final key count: {summary.get('final_key_count')}")
    print(f"- field counts: {summary.get('field_counts')}")
    print(f"- complete pose equality keys: {summary.get('complete_pose_equality_key_count')}")


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


if __name__ == "__main__":
    raise SystemExit(main())

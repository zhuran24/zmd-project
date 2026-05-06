from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_joined_xy_probe_synthesis import (
    build_phase3b_joined_xy_probe_synthesis,
    render_phase3b_joined_xy_probe_synthesis_markdown,
    render_phase3b_joined_xy_probe_synthesis_text,
    write_phase3b_joined_xy_probe_synthesis,
)

DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_joined_xy_probe_synthesis_20260423_r2")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B joined-XY probe synthesis."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_joined_xy_probe_synthesis(project_root)
    _print_summary(report)
    if not bool(args.no_write):
        paths = write_phase3b_joined_xy_probe_synthesis(
            report,
            _resolve(project_root, Path(args.output_dir)),
        )
        print(f"joined_xy_probe_synthesis_json={_display(project_root, Path(paths['json']))}")
        print(f"joined_xy_probe_synthesis_md={_display(project_root, Path(paths['md']))}")
        print(f"joined_xy_probe_synthesis_txt={_display(project_root, Path(paths['txt']))}")
    return 0


def _print_summary(report: dict) -> None:
    status = report.get("status", {})
    aggregate = report.get("aggregate", {})
    print("phase3b joined-XY probe synthesis")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- completed: {status.get('completed')}")
    print(f"- anchor count: {aggregate.get('anchor_count')}")
    print(f"- terminal anchors: {aggregate.get('terminal_anchor_indices')}")
    print(
        "- search-progress UNKNOWN anchors: "
        f"{aggregate.get('search_progress_unknown_anchor_indices')}"
    )
    print(f"- zero-branch UNKNOWN count: {aggregate.get('zero_branch_unknown_count')}")
    print("- proof_source: false")
    print("- solver_invoked: false")
    if bool(report.get("checks")):
        failed = [check for check in report["checks"] if check.get("status") != "pass"]
        print(f"- failed checks: {len(failed)}")


def _resolve(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

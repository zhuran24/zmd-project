from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.forced_anchor.master import _display_path, _mapping
from src.search.phase3b.grouped_xy.grouped_block_xy_profile_audit import (
    DEFAULT_GROUPED_BLOCK_XY_CANDIDATE,
    build_phase3b_grouped_block_xy_profile_audit,
    render_phase3b_grouped_block_xy_profile_audit_markdown,
    render_phase3b_grouped_block_xy_profile_audit_text,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_grouped_block_xy_profile_audit")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_grouped_block_xy_profile_audit(
        project_root,
        candidate=args.candidate,
        block_size=args.block_size,
        block_templates=args.block_templates,
        master_search_profile=args.master_search_profile,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "grouped_block_xy_profile_audit.json"
        md_path = output_dir / "grouped_block_xy_profile_audit.md"
        txt_path = output_dir / "grouped_block_xy_profile_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_grouped_block_xy_profile_audit_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_grouped_block_xy_profile_audit_text(report))
        print(f"grouped_block_xy_profile_audit_json={_display_path(project_root, json_path)}")
        print(f"grouped_block_xy_profile_audit_md={_display_path(project_root, md_path)}")
        print(f"grouped_block_xy_profile_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve grouped block x/y profile audit."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_GROUPED_BLOCK_XY_CANDIDATE)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--block-templates", default="")
    parser.add_argument(
        "--master-search-profile",
        default="exact_coordinate_guided_branching_v4",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    path = project_root / output_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _print_summary(report: dict[str, object]) -> None:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    print("phase3b grouped block x/y profile audit")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- grouped valid: {comparison.get('grouped_xy_profile_valid')}")
    print(f"- block x/y target delta: {comparison.get('block_xy_target_delta')}")
    print(f"- block element delta: {comparison.get('block_element_constraint_delta')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

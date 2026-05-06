from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_forced_anchor_master import _display_path, _mapping
from src.search.phase3b_grouped_xy_sat_expansion_audit import (
    build_phase3b_grouped_xy_sat_expansion_audit,
    render_phase3b_grouped_xy_sat_expansion_audit_markdown,
    render_phase3b_grouped_xy_sat_expansion_audit_text,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_grouped_xy_sat_expansion_audit")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_grouped_xy_sat_expansion_audit(project_root)
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "grouped_xy_sat_expansion_audit.json"
        md_path = output_dir / "grouped_xy_sat_expansion_audit.md"
        txt_path = output_dir / "grouped_xy_sat_expansion_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_grouped_xy_sat_expansion_audit_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_grouped_xy_sat_expansion_audit_text(report))
        print(f"grouped_xy_sat_expansion_audit_json={_display_path(project_root, json_path)}")
        print(f"grouped_xy_sat_expansion_audit_md={_display_path(project_root, md_path)}")
        print(f"grouped_xy_sat_expansion_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build grouped-XY SAT expansion audit from existing CP-SAT logs."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
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
    print("phase3b grouped xy sat expansion audit")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- integer blowup: {comparison.get('integer_encoding_blowup_detected')}")
    print(f"- integer ratio: {comparison.get('grouped_to_active_integer_encoding_ratio')}")
    print(f"- SAT boolean ratio: {comparison.get('grouped_to_active_sat_boolean_ratio')}")
    print(f"- next: {comparison.get('recommended_next_action')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

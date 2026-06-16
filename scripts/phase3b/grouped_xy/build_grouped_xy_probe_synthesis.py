from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.forced_anchor.master import _display_path, _mapping
from src.search.phase3b.grouped_xy.grouped_xy_probe_synthesis import (
    DEFAULT_COMPARATOR_PROBE_PATHS,
    DEFAULT_GROUPED_PROBE_PATHS,
    DEFAULT_PROFILE_AUDIT_PATH,
    build_phase3b_grouped_xy_probe_synthesis,
    render_phase3b_grouped_xy_probe_synthesis_markdown,
    render_phase3b_grouped_xy_probe_synthesis_text,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_grouped_xy_probe_synthesis")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_grouped_xy_probe_synthesis(
        project_root,
        profile_audit_path=args.profile_audit,
        grouped_probe_paths=args.grouped_probe,
        comparator_probe_paths=args.comparator_probe,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "grouped_xy_probe_synthesis.json"
        md_path = output_dir / "grouped_xy_probe_synthesis.md"
        txt_path = output_dir / "grouped_xy_probe_synthesis.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_grouped_xy_probe_synthesis_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_grouped_xy_probe_synthesis_text(report))
        print(f"grouped_xy_probe_synthesis_json={_display_path(project_root, json_path)}")
        print(f"grouped_xy_probe_synthesis_md={_display_path(project_root, md_path)}")
        print(f"grouped_xy_probe_synthesis_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build grouped-XY forced-anchor diagnostic synthesis."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--profile-audit", type=Path, default=DEFAULT_PROFILE_AUDIT_PATH)
    parser.add_argument("--grouped-probe", type=Path, action="append", default=list(DEFAULT_GROUPED_PROBE_PATHS))
    parser.add_argument("--comparator-probe", type=Path, action="append", default=list(DEFAULT_COMPARATOR_PROBE_PATHS))
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
    print("phase3b grouped xy probe synthesis")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- grouped search progress: {comparison.get('grouped_has_search_progress')}")
    print(f"- anchor118 terminal not reproduced: {comparison.get('anchor118_terminal_not_reproduced')}")
    print(f"- next: {comparison.get('recommended_next_action')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

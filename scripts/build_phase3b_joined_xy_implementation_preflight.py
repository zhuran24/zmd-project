from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_forced_anchor_master import _display_path, _mapping
from src.search.phase3b_joined_xy_implementation_preflight import (
    DEFAULT_GROUPED_BLOCK_XY_IMPLEMENTATION_PREFLIGHT_PATH,
    DEFAULT_GROUPED_BLOCK_XY_PROFILE_AUDIT_PATH,
    DEFAULT_GROUPED_XY_SAT_EXPANSION_AUDIT_PATH,
    build_phase3b_joined_xy_implementation_preflight,
    render_phase3b_joined_xy_implementation_preflight_markdown,
    render_phase3b_joined_xy_implementation_preflight_text,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_joined_xy_implementation_preflight")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_joined_xy_implementation_preflight(
        project_root,
        sat_expansion_audit_path=args.sat_expansion_audit,
        grouped_profile_audit_path=args.grouped_profile_audit,
        grouped_implementation_preflight_path=args.grouped_implementation_preflight,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "joined_xy_implementation_preflight.json"
        md_path = output_dir / "joined_xy_implementation_preflight.md"
        txt_path = output_dir / "joined_xy_implementation_preflight.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_joined_xy_implementation_preflight_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_joined_xy_implementation_preflight_text(report),
        )
        print(f"joined_xy_implementation_preflight_json={_display_path(project_root, json_path)}")
        print(f"joined_xy_implementation_preflight_md={_display_path(project_root, md_path)}")
        print(f"joined_xy_implementation_preflight_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve joined-XY implementation preflight."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--sat-expansion-audit",
        type=Path,
        default=DEFAULT_GROUPED_XY_SAT_EXPANSION_AUDIT_PATH,
    )
    parser.add_argument(
        "--grouped-profile-audit",
        type=Path,
        default=DEFAULT_GROUPED_BLOCK_XY_PROFILE_AUDIT_PATH,
    )
    parser.add_argument(
        "--grouped-implementation-preflight",
        type=Path,
        default=DEFAULT_GROUPED_BLOCK_XY_IMPLEMENTATION_PREFLIGHT_PATH,
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
    mode = _mapping(report.get("proposed_mode"))
    counts = _mapping(report.get("expected_no_solve_stats"))
    problem = _mapping(report.get("problem_statement"))
    print("phase3b joined-xy implementation preflight")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- ready: {bool(status.get('ready_for_default_off_model_edit', False))}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- mode: {mode.get('value')}")
    print(f"- grouped integer blowup: {problem.get('integer_encoding_blowup_detected')}")
    print(f"- expected padded idx vars: {counts.get('cover_choice_padded_idx_variables')}")
    print(f"- expected block elements: {counts.get('total_block_element_constraints')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

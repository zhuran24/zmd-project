from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.active_guard.block_xy_scale_equivalence import (
    DEFAULT_PROTO_SHAPE_AUDIT_PATH,
    DEFAULT_RESIDUAL_SURFACE_PATH,
    build_phase3b_active_guard_block_xy_scale_equivalence,
    render_phase3b_active_guard_block_xy_scale_equivalence_markdown,
    render_phase3b_active_guard_block_xy_scale_equivalence_text,
)
from src.search.phase3b.forced_anchor.master import _display_path, _mapping


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_active_guard_block_xy_scale_equivalence")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_active_guard_block_xy_scale_equivalence(
        project_root,
        proto_shape_audit_path=args.proto_shape_audit,
        residual_surface_path=args.residual_surface,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "active_guard_block_xy_scale_equivalence.json"
        md_path = output_dir / "active_guard_block_xy_scale_equivalence.md"
        txt_path = output_dir / "active_guard_block_xy_scale_equivalence.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_active_guard_block_xy_scale_equivalence_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_active_guard_block_xy_scale_equivalence_text(report),
        )
        print(f"active_guard_block_xy_scale_equivalence_json={_display_path(project_root, json_path)}")
        print(f"active_guard_block_xy_scale_equivalence_md={_display_path(project_root, md_path)}")
        print(f"active_guard_block_xy_scale_equivalence_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve ActiveGuard block x/y scale-equivalence report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--proto-shape-audit", type=Path, default=DEFAULT_PROTO_SHAPE_AUDIT_PATH)
    parser.add_argument("--residual-surface", type=Path, default=DEFAULT_RESIDUAL_SURFACE_PATH)
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
    baseline = _mapping(report.get("baseline"))
    direct = _mapping(_mapping(report.get("candidate_estimates")).get("direct_guarded_geometry"))
    rec = _mapping(report.get("recommendation"))
    print("phase3b active-guard block x/y scale-equivalence")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- relation rows: {baseline.get('relation_row_count')}")
    print(f"- direct guarded geometry net delta: {direct.get('net_constraint_delta')}")
    print(f"- classification: {rec.get('classification')}")
    print(f"- next: {rec.get('next_action')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

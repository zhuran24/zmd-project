from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_forced_anchor_master import _display_path, _mapping
from src.search.phase3b_grouped_block_xy_equivalence_oracle import (
    DEFAULT_PROTO_SHAPE_AUDIT_PATH,
    DEFAULT_RESIDUAL_SURFACE_PATH,
    DEFAULT_SCALE_EQUIVALENCE_PATH,
    DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
    build_phase3b_grouped_block_xy_equivalence_oracle,
    render_phase3b_grouped_block_xy_equivalence_oracle_markdown,
    render_phase3b_grouped_block_xy_equivalence_oracle_text,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_grouped_block_xy_equivalence_oracle")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_grouped_block_xy_equivalence_oracle(
        project_root,
        scale_equivalence_path=args.scale_equivalence,
        proto_shape_audit_path=args.proto_shape_audit,
        residual_surface_path=args.residual_surface,
        selected_block_equivalence_path=args.selected_block_equivalence,
        grouped_candidate_path=args.grouped_candidate,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "grouped_block_xy_equivalence_oracle.json"
        md_path = output_dir / "grouped_block_xy_equivalence_oracle.md"
        txt_path = output_dir / "grouped_block_xy_equivalence_oracle.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_grouped_block_xy_equivalence_oracle_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_grouped_block_xy_equivalence_oracle_text(report),
        )
        print(f"grouped_block_xy_equivalence_oracle_json={_display_path(project_root, json_path)}")
        print(f"grouped_block_xy_equivalence_oracle_md={_display_path(project_root, md_path)}")
        print(f"grouped_block_xy_equivalence_oracle_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve grouped block x/y equivalence oracle report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--scale-equivalence", type=Path, default=DEFAULT_SCALE_EQUIVALENCE_PATH)
    parser.add_argument("--proto-shape-audit", type=Path, default=DEFAULT_PROTO_SHAPE_AUDIT_PATH)
    parser.add_argument("--residual-surface", type=Path, default=DEFAULT_RESIDUAL_SURFACE_PATH)
    parser.add_argument(
        "--selected-block-equivalence",
        type=Path,
        default=DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
    )
    parser.add_argument("--grouped-candidate", type=Path, default=None)
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
    original = _mapping(report.get("original_relation_summary"))
    proposed = _mapping(report.get("proposed_grouped_relation_summary"))
    rec = _mapping(report.get("recommendation"))
    print("phase3b grouped block x/y equivalence oracle")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- ready: {bool(status.get('oracle_ready_for_default_off_implementation', False))}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- original relation rows: {original.get('relation_row_count')}")
    print(f"- grouped candidate present: {proposed.get('present')}")
    print(f"- classification: {rec.get('classification')}")
    print(f"- next: {rec.get('next_action')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

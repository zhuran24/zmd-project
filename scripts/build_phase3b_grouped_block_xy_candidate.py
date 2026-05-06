from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_forced_anchor_master import _display_path, _mapping
from src.search.phase3b_grouped_block_xy_candidate import (
    DEFAULT_GROUPED_ORACLE_PATH,
    GROUPED_BLOCK_XY_CANDIDATE_SOURCE,
    build_phase3b_grouped_block_xy_candidate,
    render_phase3b_grouped_block_xy_candidate_markdown,
    render_phase3b_grouped_block_xy_candidate_text,
)
from src.search.phase3b_grouped_block_xy_equivalence_oracle import (
    DEFAULT_PROTO_SHAPE_AUDIT_PATH,
    DEFAULT_SCALE_EQUIVALENCE_PATH,
    DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_grouped_block_xy_candidate")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_grouped_block_xy_candidate(
        project_root,
        scale_equivalence_path=args.scale_equivalence,
        selected_block_equivalence_path=args.selected_block_equivalence,
        proto_shape_audit_path=args.proto_shape_audit,
        grouped_oracle_path=args.grouped_oracle,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "grouped_block_xy_candidate.json"
        md_path = output_dir / "grouped_block_xy_candidate.md"
        txt_path = output_dir / "grouped_block_xy_candidate.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_grouped_block_xy_candidate_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_grouped_block_xy_candidate_text(report))
        print(f"grouped_block_xy_candidate_json={_display_path(project_root, json_path)}")
        print(f"grouped_block_xy_candidate_md={_display_path(project_root, md_path)}")
        print(f"grouped_block_xy_candidate_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve grouped block x/y candidate contract."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--scale-equivalence", type=Path, default=DEFAULT_SCALE_EQUIVALENCE_PATH)
    parser.add_argument(
        "--selected-block-equivalence",
        type=Path,
        default=DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
    )
    parser.add_argument("--proto-shape-audit", type=Path, default=DEFAULT_PROTO_SHAPE_AUDIT_PATH)
    parser.add_argument("--grouped-oracle", type=Path, default=DEFAULT_GROUPED_ORACLE_PATH)
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
    relation = _mapping(report.get("grouped_relation"))
    semantic = _mapping(relation.get("semantic_projection_equivalence"))
    print("phase3b grouped block x/y candidate")
    print(f"- source: {GROUPED_BLOCK_XY_CANDIDATE_SOURCE}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- relation rows: {relation.get('relation_row_count')}")
    print(f"- projection equivalent: {semantic.get('equivalent')}")
    print(f"- candidate hash: {semantic.get('candidate_relation_hash')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

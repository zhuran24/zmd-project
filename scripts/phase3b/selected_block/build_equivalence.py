from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.selected_block.equivalence import (
    DEFAULT_SELECTED_BLOCK_CANDIDATE,
    build_phase3b_selected_block_equivalence_audit,
    render_phase3b_selected_block_equivalence_markdown,
    render_phase3b_selected_block_equivalence_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B no-solve selected-block equivalence audit."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_SELECTED_BLOCK_CANDIDATE)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument(
        "--block-templates",
        default="",
        help="Comma-separated block templates; empty means all powered templates.",
    )
    parser.add_argument(
        "--master-search-profile",
        default="exact_coordinate_guided_branching_v4",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_selected_block_equivalence"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_selected_block_equivalence_audit(
        project_root,
        candidate=str(args.candidate),
        block_size=int(args.block_size),
        block_templates=str(args.block_templates),
        master_search_profile=str(args.master_search_profile),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "selected_block_equivalence.json"
        md_path = output_dir / "selected_block_equivalence.md"
        txt_path = output_dir / "selected_block_equivalence.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_selected_block_equivalence_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_selected_block_equivalence_text(report),
        )
        print(f"selected_block_equivalence_json={_display_path(project_root, json_path)}")
        print(f"selected_block_equivalence_md={_display_path(project_root, md_path)}")
        print(f"selected_block_equivalence_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    real = _mapping(relation.get("real_witness_relation"))
    target_delta = _mapping(relation.get("target_channel_delta"))
    print("phase3b selected-block equivalence")
    print("- diagnostic semantics: no_solve_witness_relation_equivalence_audit")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- real witness equivalent: {real.get('equivalent')}")
    print(f"- witness count: {real.get('witness_count')}")
    print(f"- relation rows: {real.get('relation_row_count')}")
    print(f"- padded values: {real.get('padded_block_value_count')}")
    print(
        "- final target channel delta: "
        f"{target_delta.get('final_target_channel_delta')}"
    )
    print(f"- recommendation: {status.get('recommendation')}")


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

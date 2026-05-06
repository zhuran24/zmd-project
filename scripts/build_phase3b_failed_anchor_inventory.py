from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_failed_anchor_inventory import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    DEFAULT_FORCED_ANCHOR_DIR,
    DEFAULT_SOLVER_MATRIX_DIR,
    build_phase3b_failed_anchor_inventory,
    render_phase3b_failed_anchor_inventory_markdown,
    render_phase3b_failed_anchor_inventory_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B failed-anchor inventory from campaign state and forced-anchor evidence."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--forced-anchor-dir", type=Path, default=DEFAULT_FORCED_ANCHOR_DIR)
    parser.add_argument("--solver-matrix-dir", type=Path, default=DEFAULT_SOLVER_MATRIX_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_failed_anchor_inventory"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_failed_anchor_inventory(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        forced_anchor_dir=args.forced_anchor_dir,
        solver_matrix_dir=args.solver_matrix_dir,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "failed_anchor_inventory.json"
        md_path = output_dir / "failed_anchor_inventory.md"
        txt_path = output_dir / "failed_anchor_inventory.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_failed_anchor_inventory_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_failed_anchor_inventory_text(report))
        print(f"failed_anchor_inventory_json={_display_path(project_root, json_path)}")
        print(f"failed_anchor_inventory_md={_display_path(project_root, md_path)}")
        print(f"failed_anchor_inventory_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    summary = _mapping(report.get("summary"))
    print("phase3b failed-anchor inventory")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- sample count: {summary.get('sample_count', 0)}")
    print(f"- classification counts: {summary.get('classification_counts', {})}")
    print(f"- forced status counts: {summary.get('forced_status_counts', {})}")
    print(
        "- forced zero-branch UNKNOWN count: "
        f"{summary.get('forced_zero_branch_unknown_count', 0)}"
    )
    print(f"- recommendation: {summary.get('recommendation')}")


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

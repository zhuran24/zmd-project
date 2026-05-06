from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.campaign_triage import (
    build_phase3b_unknown_triage_inventory,
    render_phase3b_unknown_triage_markdown,
    render_phase3b_unknown_triage_text,
)
from src.search.exact_campaign import atomic_write_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B UNKNOWN/UNPROVEN blocker inventory without mutating proof artifacts."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository/project root to inspect.",
    )
    parser.add_argument(
        "--campaign-state",
        type=Path,
        default=None,
        help="Campaign state JSON path. Defaults to data/checkpoints/exact_campaign_state.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_unknown_triage"),
        help="Directory for blocker_inventory.json/md/txt.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the inventory summary but do not write report files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    inventory = build_phase3b_unknown_triage_inventory(
        project_root=project_root,
        campaign_state_path=args.campaign_state,
    )
    _print_summary(inventory)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "blocker_inventory.json"
        md_path = output_dir / "blocker_inventory.md"
        txt_path = output_dir / "blocker_inventory.txt"
        atomic_write_json(json_path, inventory)
        _atomic_write_text(md_path, render_phase3b_unknown_triage_markdown(inventory))
        _atomic_write_text(txt_path, render_phase3b_unknown_triage_text(inventory))
        print(f"inventory_json={_display_path(project_root, json_path)}")
        print(f"inventory_md={_display_path(project_root, md_path)}")
        print(f"inventory_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(inventory: Mapping[str, Any]) -> None:
    summary = _mapping(inventory.get("summary"))
    print("phase3b unknown triage inventory")
    print(f"- campaign present: {bool(summary.get('campaign_present', False))}")
    print(f"- telemetry present: {bool(summary.get('telemetry_present', False))}")
    print(f"- telemetry waves: {int(summary.get('telemetry_wave_count', 0))}")
    print(f"- blocker count: {int(summary.get('blocker_count', 0))}")
    print(f"- status counts: {summary.get('status_counts')}")
    print(f"- classification counts: {summary.get('classification_counts')}")
    print(f"- subtype counts: {summary.get('subtype_counts')}")


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

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.pose_order.pose_order_unknown_resolution import (
    build_phase3b_pose_order_unknown_resolution,
    render_phase3b_pose_order_unknown_resolution_markdown,
    render_phase3b_pose_order_unknown_resolution_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize pose-order probe resolution for sampled portfolio UNKNOWNs."
    )
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--probe-dir", type=Path, default=None)
    parser.add_argument("--comparison-path", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_pose_order_unknown_resolution"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    report = build_phase3b_pose_order_unknown_resolution(
        workspace_root,
        probe_dir=args.probe_dir,
        comparison_path=args.comparison_path,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(workspace_root, args.output_dir)
        json_path = output_dir / "pose_order_unknown_resolution.json"
        md_path = output_dir / "pose_order_unknown_resolution.md"
        txt_path = output_dir / "pose_order_unknown_resolution.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_pose_order_unknown_resolution_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_pose_order_unknown_resolution_text(report))
        print(f"pose_order_unknown_resolution_json={_display_path(workspace_root, json_path)}")
        print(f"pose_order_unknown_resolution_md={_display_path(workspace_root, md_path)}")
        print(f"pose_order_unknown_resolution_txt={_display_path(workspace_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    print("phase3b pose-order unknown resolution")
    print(f"- outcome: {status.get('outcome')}")
    for entry in list(report.get("probe_reports", [])):
        if not isinstance(entry, Mapping):
            continue
        print(
            "- probe: "
            f"anchor={entry.get('anchor_idx')} "
            f"full={entry.get('full_validation_status')} "
            f"prefix={entry.get('first_infeasible_prefix_group_count')} "
            f"group={entry.get('first_infeasible_group_id')}"
        )
    print(f"- runtime promotion ready: {status.get('runtime_promotion_ready')}")


def _resolve_output_dir(workspace_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (workspace_root / output_dir).resolve()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

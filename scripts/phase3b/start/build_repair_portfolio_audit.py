from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.start.repair_portfolio_audit import (
    build_phase3b_start_repair_portfolio_audit,
    render_phase3b_start_repair_portfolio_audit_markdown,
    render_phase3b_start_repair_portfolio_audit_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a report-only Phase3B start-repair portfolio audit."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--workspace-root", type=Path, default=None)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_start_repair_portfolio_audit"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    workspace_root = Path(args.workspace_root).resolve() if args.workspace_root else project_root
    report = build_phase3b_start_repair_portfolio_audit(
        project_root,
        workspace_root=workspace_root,
        candidate=str(args.candidate),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(workspace_root, args.output_dir)
        json_path = output_dir / "start_repair_portfolio_audit.json"
        md_path = output_dir / "start_repair_portfolio_audit.md"
        txt_path = output_dir / "start_repair_portfolio_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_start_repair_portfolio_audit_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_start_repair_portfolio_audit_text(report))
        print(f"start_repair_portfolio_audit_json={_display_path(workspace_root, json_path)}")
        print(f"start_repair_portfolio_audit_md={_display_path(workspace_root, md_path)}")
        print(f"start_repair_portfolio_audit_txt={_display_path(workspace_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    unknowns = _mapping(report.get("portfolio_unknowns"))
    profiler = _mapping(report.get("start_repair_profiler"))
    print("phase3b start-repair portfolio audit")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- portfolio unknowns: {unknowns.get('count')} ({unknowns.get('diagnosis')})")
    print(f"- current candidate profiler count: {profiler.get('current_candidate_profile_count')}")
    print(f"- runtime promotion ready: {status.get('runtime_promotion_ready')}")
    print(f"- recommendation: {status.get('recommendation')}")


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

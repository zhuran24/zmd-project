from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.b5a.blocker_pivot import (
    build_phase3b_b5a_blocker_pivot,
    render_phase3b_b5a_blocker_pivot_markdown,
    render_phase3b_b5a_blocker_pivot_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a report-only Phase 3B B5A blocker pivot summary."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--workspace-root", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_b5a_blocker_pivot"),
    )
    parser.add_argument("--output-prefix", default="b5a_blocker_pivot")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_b5a_blocker_pivot(
        project_root,
        workspace_root=args.workspace_root,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = str(args.output_prefix)
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_b5a_blocker_pivot_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_b5a_blocker_pivot_text(report))
        print(f"b5a_blocker_pivot_json={_display_path(project_root, json_path)}")
        print(f"b5a_blocker_pivot_md={_display_path(project_root, md_path)}")
        print(f"b5a_blocker_pivot_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    open_branch = _mapping(report.get("open_branch"))
    print("phase3b b5a blocker pivot")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- closed branches: {status.get('closed_branch_count')}")
    print(f"- open branch: {open_branch.get('branch')}")
    print(f"- runtime promotion ready: {status.get('runtime_promotion_ready')}")
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

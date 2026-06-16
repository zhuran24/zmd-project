from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.start.repair_portfolio_sample_comparison import (
    build_phase3b_start_repair_portfolio_sample_comparison,
    render_phase3b_start_repair_portfolio_sample_comparison_markdown,
    render_phase3b_start_repair_portfolio_sample_comparison_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline B5A portfolio counts with a sampled start-compatibility rerun."
    )
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--start-compatibility-path", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_start_repair_portfolio_sample_comparison"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    report = build_phase3b_start_repair_portfolio_sample_comparison(
        workspace_root,
        start_compatibility_path=args.start_compatibility_path,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(workspace_root, args.output_dir)
        json_path = output_dir / "portfolio_sample_comparison.json"
        md_path = output_dir / "portfolio_sample_comparison.md"
        txt_path = output_dir / "portfolio_sample_comparison.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_start_repair_portfolio_sample_comparison_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_start_repair_portfolio_sample_comparison_text(report))
        print(f"portfolio_sample_comparison_json={_display_path(workspace_root, json_path)}")
        print(f"portfolio_sample_comparison_md={_display_path(workspace_root, md_path)}")
        print(f"portfolio_sample_comparison_txt={_display_path(workspace_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    baseline = _mapping(report.get("baseline_b5a_portfolio"))
    rerun = _mapping(report.get("rerun_start_compatibility_portfolio"))
    print("phase3b start-repair portfolio sample comparison")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- baseline counts: {baseline.get('failure_reason_counts')}")
    print(f"- rerun counts: {rerun.get('failure_reason_counts')}")
    print(f"- rerun unknown samples: {rerun.get('unknown_samples')}")
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

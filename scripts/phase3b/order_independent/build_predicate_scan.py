from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.order_independent.predicate_scan import (
    build_phase3b_order_independent_predicate_scan,
    render_phase3b_order_independent_predicate_scan_markdown,
    render_phase3b_order_independent_predicate_scan_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan pose-order geometry signatures for order-independent predicate candidates."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--geometry-signature-path", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_order_independent_predicate_scan"),
    )
    parser.add_argument("--output-prefix", default="order_independent_predicate_scan")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_order_independent_predicate_scan(
        project_root,
        geometry_signature_path=args.geometry_signature_path,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = str(args.output_prefix)
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_order_independent_predicate_scan_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_order_independent_predicate_scan_text(report),
        )
        print(f"order_independent_predicate_scan_json={_display_path(project_root, json_path)}")
        print(f"order_independent_predicate_scan_md={_display_path(project_root, md_path)}")
        print(f"order_independent_predicate_scan_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    print("phase3b order-independent predicate scan")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- candidate count: {status.get('candidate_count')}")
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

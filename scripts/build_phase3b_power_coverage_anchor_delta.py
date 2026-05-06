from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_power_coverage_anchor_delta import (
    DEFAULT_ANCHOR_DOMAIN_INVENTORY_PATH,
    build_phase3b_power_coverage_anchor_delta,
    render_phase3b_power_coverage_anchor_delta_markdown,
    render_phase3b_power_coverage_anchor_delta_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B power-coverage anchor delta from anchor-domain inventory."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--anchor-domain-inventory",
        type=Path,
        default=DEFAULT_ANCHOR_DOMAIN_INVENTORY_PATH,
    )
    parser.add_argument("--baseline-anchor", type=int, default=118)
    parser.add_argument("--comparison-anchor", type=int, default=119)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_power_coverage_anchor_delta"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_power_coverage_anchor_delta(
        project_root,
        anchor_domain_inventory_path=args.anchor_domain_inventory,
        baseline_anchor_idx=int(args.baseline_anchor),
        comparison_anchor_idx=int(args.comparison_anchor),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "power_coverage_anchor_delta.json"
        md_path = output_dir / "power_coverage_anchor_delta.md"
        txt_path = output_dir / "power_coverage_anchor_delta.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_power_coverage_anchor_delta_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_power_coverage_anchor_delta_text(report))
        print(f"power_coverage_anchor_delta_json={_display_path(project_root, json_path)}")
        print(f"power_coverage_anchor_delta_md={_display_path(project_root, md_path)}")
        print(f"power_coverage_anchor_delta_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    delta = _mapping(report.get("delta"))
    print("phase3b power-coverage anchor delta")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- changed power families: {delta.get('power_family_changed_count', 0)}")
    print(f"- positive delta sum: {delta.get('power_family_positive_delta_sum', 0)}")
    print(f"- negative delta sum: {delta.get('power_family_negative_delta_sum', 0)}")
    print(f"- mandatory survivor delta: {delta.get('mandatory_surviving_delta')}")
    print(f"- optional survivor delta: {delta.get('optional_surviving_delta')}")
    print(f"- diagnostic findings: {delta.get('diagnostic_findings', [])}")
    print(f"- recommendation: {report.get('recommendation')}")


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

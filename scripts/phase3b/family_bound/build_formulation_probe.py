from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.family_bound.formulation_probe import (
    DEFAULT_ALL_FAMILY_DIRECT_BOUND_SLICE_PATH,
    DEFAULT_DIRECT_BOUND_SLICE_PATH,
    DEFAULT_ENFORCED_FORMULATION_SLICE_PATH,
    DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    build_phase3b_family_bound_formulation_probe,
    render_phase3b_family_bound_formulation_probe_markdown,
    render_phase3b_family_bound_formulation_probe_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B diagnostic formulation probe for target conditioned family bound."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--direct-bound-slice",
        type=Path,
        default=DEFAULT_DIRECT_BOUND_SLICE_PATH,
    )
    parser.add_argument(
        "--enforced-formulation-slice",
        type=Path,
        default=DEFAULT_ENFORCED_FORMULATION_SLICE_PATH,
    )
    parser.add_argument(
        "--all-family-direct-bound-slice",
        type=Path,
        default=DEFAULT_ALL_FAMILY_DIRECT_BOUND_SLICE_PATH,
    )
    parser.add_argument(
        "--family-bound-semantic-audit",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_family_bound_formulation_probe"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_family_bound_formulation_probe(
        project_root,
        direct_bound_slice_path=args.direct_bound_slice,
        enforced_formulation_slice_path=args.enforced_formulation_slice,
        all_family_direct_bound_slice_path=args.all_family_direct_bound_slice,
        family_bound_semantic_audit_path=args.family_bound_semantic_audit,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "family_bound_formulation_probe.json"
        md_path = output_dir / "family_bound_formulation_probe.md"
        txt_path = output_dir / "family_bound_formulation_probe.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_family_bound_formulation_probe_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_family_bound_formulation_probe_text(report))
        print(f"family_bound_formulation_probe_json={_display_path(project_root, json_path)}")
        print(f"family_bound_formulation_probe_md={_display_path(project_root, md_path)}")
        print(f"family_bound_formulation_probe_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    comparison = _mapping(report.get("comparison"))
    print("phase3b family-bound formulation probe")
    print(f"- classification: {report.get('classification')}")
    print(f"- base status: {comparison.get('base_status')}")
    print(f"- direct status: {comparison.get('direct_status')}")
    print(f"- enforced status: {comparison.get('enforced_status')}")
    print(f"- all-family status: {comparison.get('all_family_status')}")
    print(f"- wall speedup: {comparison.get('wall_time_speedup')}")
    print(f"- direct bound value: {comparison.get('direct_bound_value')}")
    print(f"- direct count value: {comparison.get('direct_count_value')}")
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

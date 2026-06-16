from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.family_bound.semantic_audit import (
    DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    DEFAULT_TARGET_FAMILY_SLICE_PATH,
    build_phase3b_family_bound_semantic_audit,
    render_phase3b_family_bound_semantic_audit_markdown,
    render_phase3b_family_bound_semantic_audit_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B family-bound semantic audit from bound audit and target relaxed slice artifacts."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--family-bound-audit",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    )
    parser.add_argument(
        "--target-family-slice",
        type=Path,
        default=DEFAULT_TARGET_FAMILY_SLICE_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_family_bound_semantic_audit"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_family_bound_semantic_audit(
        project_root,
        family_bound_audit_path=args.family_bound_audit,
        target_family_slice_path=args.target_family_slice,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "family_bound_semantic_audit.json"
        md_path = output_dir / "family_bound_semantic_audit.md"
        txt_path = output_dir / "family_bound_semantic_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_family_bound_semantic_audit_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_family_bound_semantic_audit_text(report))
        print(f"family_bound_semantic_audit_json={_display_path(project_root, json_path)}")
        print(f"family_bound_semantic_audit_md={_display_path(project_root, md_path)}")
        print(f"family_bound_semantic_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    family = _mapping(report.get("family_bound"))
    relaxed = _mapping(report.get("target_family_slice"))
    print("phase3b family-bound semantic audit")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- classification: {report.get('classification')}")
    print(f"- target family: {family.get('target_power_family')}")
    print(f"- derived bound: {family.get('derived_conditioned_upper_bound')}")
    print(f"- relaxed count value: {relaxed.get('relaxed_power_family_count_value')}")
    print(f"- violation: {relaxed.get('relaxed_family_bound_violation')}")
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

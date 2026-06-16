from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.operating_profile.operating_profile import (
    build_phase3b_operating_profile_summary,
    render_phase3b_operating_profile_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase 3B operating profile lock summary."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository/project root to inspect.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_operating_profile"),
        help="Directory for operating_profile.json/md.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the operating profile summary but do not write report files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    summary = build_phase3b_operating_profile_summary(project_root)
    _print_summary(summary)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "operating_profile.json"
        md_path = output_dir / "operating_profile.md"
        atomic_write_json(json_path, summary)
        _atomic_write_text(md_path, render_phase3b_operating_profile_markdown(summary))
        print(f"operating_profile_json={_display_path(project_root, json_path)}")
        print(f"operating_profile_md={_display_path(project_root, md_path)}")
    return 0


def _print_summary(summary: Mapping[str, Any]) -> None:
    defaults = _mapping(summary.get("defaults"))
    policy = _mapping(summary.get("policy"))
    profile_by_id = _mapping(summary.get("profile_by_id"))
    production_profile = _mapping(
        profile_by_id.get(str(defaults.get("production_profile_id", "")))
    )
    diagnostic_profile = _mapping(
        profile_by_id.get(str(defaults.get("diagnostic_profile_id", "")))
    )
    formulation_profiles = sorted(
        str(profile_id)
        for profile_id, profile in profile_by_id.items()
        if bool(_mapping(profile).get("is_formulation_diagnostic", False))
    )
    print("phase3b operating profile")
    print(f"- default production: {defaults.get('production_profile_id')}")
    print(f"- production command: {production_profile.get('command')}")
    print(f"- default diagnostic: {defaults.get('diagnostic_profile_id')}")
    print(f"- diagnostic command: {diagnostic_profile.get('command')}")
    if formulation_profiles:
        print(f"- formulation diagnostics: {', '.join(formulation_profiles)}")
    print(f"- high priority default: {bool(policy.get('high_priority_default', False))}")


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

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_coordinate_validation_profile_probe import (
    DEFAULT_COORDINATE_VALIDATION_PROFILES,
    build_phase3b_coordinate_validation_profile_probe,
    render_phase3b_coordinate_validation_profile_probe_markdown,
    render_phase3b_coordinate_validation_profile_probe_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe ghost-aware coordinate validation across CP-SAT profiles."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-index", type=int, default=119)
    parser.add_argument(
        "--master-search-profile",
        default=None,
        help="Optional exact coordinate master search profile override.",
    )
    parser.add_argument(
        "--profiles-json",
        default=None,
        help="Optional JSON list of coordinate validation solver profiles.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_coordinate_validation_profile_probe"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    kwargs: dict[str, Any] = {
        "candidate": str(args.candidate),
        "anchor_idx": int(args.anchor_index),
        "profiles": _parse_profiles(args.profiles_json),
    }
    if args.master_search_profile is not None:
        kwargs["master_search_profile"] = str(args.master_search_profile)
    report = build_phase3b_coordinate_validation_profile_probe(project_root, **kwargs)
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "coordinate_validation_profile_probe.json"
        md_path = output_dir / "coordinate_validation_profile_probe.md"
        txt_path = output_dir / "coordinate_validation_profile_probe.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_profile_probe_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_profile_probe_text(report),
        )
        print(f"coordinate_validation_profile_probe_json={_display_path(project_root, json_path)}")
        print(f"coordinate_validation_profile_probe_md={_display_path(project_root, md_path)}")
        print(f"coordinate_validation_profile_probe_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    candidate = _mapping(report.get("candidate"))
    print("phase3b coordinate validation profile probe")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- anchor: {candidate.get('anchor_idx')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- status counts: {probe.get('status_counts', {})}")
    print(
        "- zero-branch UNKNOWN entries: "
        f"{unknowns.get('zero_branch_unknown_count', 0)}"
    )
    print(
        "- search-progress UNKNOWN entries: "
        f"{unknowns.get('search_progress_unknown_count', 0)}"
    )
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_profiles(raw_value: str | None) -> list[dict[str, Any]]:
    if raw_value is None or not str(raw_value).strip():
        return [dict(profile) for profile in DEFAULT_COORDINATE_VALIDATION_PROFILES]
    text = str(raw_value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = json.loads(text.replace("'", '"'))
    if not isinstance(parsed, list):
        raise ValueError("--profiles-json must be a JSON list")
    return [dict(item) for item in parsed if isinstance(item, Mapping)]


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

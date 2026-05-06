from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_coordinate_validation_assumption_core import (
    DEFAULT_ASSUMPTION_CORE_CASES,
    build_phase3b_coordinate_validation_assumption_core,
    render_phase3b_coordinate_validation_assumption_core_markdown,
    render_phase3b_coordinate_validation_assumption_core_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B coordinate-validation assumption-core diagnostic."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-index", type=int, default=119)
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument(
        "--case",
        action="append",
        default=None,
        help=(
            "Case in group_id:field_variant form. Repeatable/comma-separated. Defaults to "
            + ",".join(DEFAULT_ASSUMPTION_CORE_CASES)
        ),
    )
    parser.add_argument("--time-limit-seconds", type=float, default=2.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument(
        "--solver-profile-json",
        default=None,
        help="Optional JSON object merged into the validation solver profile.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_coordinate_validation_assumption_core"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_coordinate_validation_assumption_core(
        project_root,
        candidate=str(args.candidate),
        anchor_idx=int(args.anchor_index),
        cases=_parse_csv_values(args.case),
        master_search_profile=str(args.master_search_profile),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
        solver_parameter_profile=_parse_solver_profile(args.solver_profile_json),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or "coordinate_validation_assumption_core"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_assumption_core_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_assumption_core_text(report),
        )
        print(f"coordinate_validation_assumption_core_json={_display_path(project_root, json_path)}")
        print(f"coordinate_validation_assumption_core_md={_display_path(project_root, md_path)}")
        print(f"coordinate_validation_assumption_core_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    core = _mapping(report.get("assumption_core"))
    first_core = _mapping(core.get("first_extracted_core_entry"))
    print("phase3b coordinate validation assumption core")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- anchor: {candidate.get('anchor_idx')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- status counts: {core.get('status_counts', {})}")
    print(f"- core status counts: {core.get('core_status_counts', {})}")
    if first_core:
        validation = _mapping(first_core.get("validation"))
        print(
            "- first extracted core: "
            f"{first_core.get('group_id')} "
            f"field={first_core.get('field_variant')} "
            f"size={len(list(validation.get('infeasible_assumption_core', [])))}"
        )
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_csv_values(raw_values: list[str] | None) -> list[str]:
    if not raw_values:
        return []
    values: list[str] = []
    for raw in raw_values:
        for part in str(raw).split(","):
            text = part.strip()
            if text:
                values.append(text)
    return values


def _parse_solver_profile(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    text = str(raw_value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = json.loads(text.replace("'", '"'))
    if not isinstance(parsed, Mapping):
        raise ValueError("--solver-profile-json must be a JSON object")
    return dict(parsed)


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

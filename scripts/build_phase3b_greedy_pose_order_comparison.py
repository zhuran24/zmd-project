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
from src.search.phase3b_greedy_pose_order_comparison import (
    DEFAULT_FIELD_VARIANT,
    DEFAULT_STRATEGIES,
    DEFAULT_TARGET_GROUP_ID,
    build_phase3b_greedy_pose_order_comparison,
    render_phase3b_greedy_pose_order_comparison_markdown,
    render_phase3b_greedy_pose_order_comparison_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B greedy pose-order comparison diagnostic."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-index", type=int, default=159)
    parser.add_argument("--group-id", default=DEFAULT_TARGET_GROUP_ID)
    parser.add_argument("--field-variant", default=DEFAULT_FIELD_VARIANT)
    parser.add_argument(
        "--strategies",
        default=",".join(DEFAULT_STRATEGIES),
        help="Comma-separated strategies: " + ",".join(DEFAULT_STRATEGIES),
    )
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument("--time-limit-seconds", type=float, default=10.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument(
        "--solver-profile-json",
        default=None,
        help="Optional JSON object merged into the validation solver profile.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_greedy_pose_order_comparison"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_greedy_pose_order_comparison(
        project_root,
        candidate=str(args.candidate),
        anchor_idx=int(args.anchor_index),
        group_id=str(args.group_id),
        field_variant=str(args.field_variant),
        strategies=_parse_csv(args.strategies),
        master_search_profile=str(args.master_search_profile),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
        solver_parameter_profile=_parse_solver_profile(args.solver_profile_json),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or "greedy_pose_order_comparison"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_greedy_pose_order_comparison_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_greedy_pose_order_comparison_text(report),
        )
        print(f"greedy_pose_order_comparison_json={_display_path(project_root, json_path)}")
        print(f"greedy_pose_order_comparison_md={_display_path(project_root, md_path)}")
        print(f"greedy_pose_order_comparison_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    print("phase3b greedy pose order comparison")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- anchor: {candidate.get('anchor_idx')}")
    print(f"- group: {profile.get('group_id')}")
    print(f"- field variant: {profile.get('field_variant')}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- status counts: {comparison.get('status_counts', {})}")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in str(raw).split(",") if part.strip()]


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

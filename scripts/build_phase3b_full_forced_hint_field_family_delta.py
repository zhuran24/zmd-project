from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_full_forced_hint_field_family_delta import (
    build_phase3b_full_forced_hint_field_family_delta,
    render_phase3b_full_forced_hint_field_family_delta_markdown,
    render_phase3b_full_forced_hint_field_family_delta_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B full forced-hint field/family delta report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-start", type=int, default=118)
    parser.add_argument("--anchor-end", type=int, default=125)
    parser.add_argument("--anchors", default=None)
    parser.add_argument("--focus-anchor-index", type=int, default=119)
    parser.add_argument("--field-variants", default=None)
    parser.add_argument("--template-filters", default=None)
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument("--time-limit-seconds", type=float, default=2.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_full_forced_hint_field_family_delta"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_full_forced_hint_field_family_delta(
        project_root,
        candidate=str(args.candidate),
        anchor_indices=_parse_anchors(
            raw=args.anchors,
            anchor_start=int(args.anchor_start),
            anchor_end=int(args.anchor_end),
        ),
        focus_anchor_idx=int(args.focus_anchor_index),
        field_variants=_parse_csv(args.field_variants),
        template_filters=_parse_csv(args.template_filters),
        master_search_profile=str(args.master_search_profile),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or "full_forced_hint_field_family_delta"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_full_forced_hint_field_family_delta_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_full_forced_hint_field_family_delta_text(report),
        )
        print(f"full_forced_hint_field_family_delta_json={_display_path(project_root, json_path)}")
        print(f"full_forced_hint_field_family_delta_md={_display_path(project_root, md_path)}")
        print(f"full_forced_hint_field_family_delta_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: dict) -> None:
    status = report.get("status", {})
    summary = report.get("summary", {})
    print("phase3b full forced-hint field/family delta")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- field entries: {summary.get('field_entry_count')}")
    print(f"- template entries: {summary.get('template_entry_count')}")
    print(f"- same-x precheck hits: {summary.get('same_x_precheck_count')}")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchors(*, raw: str | None, anchor_start: int, anchor_end: int) -> list[int]:
    if raw is not None and str(raw).strip():
        return [int(token.strip()) for token in str(raw).split(",") if token.strip()]
    if int(anchor_end) < int(anchor_start):
        raise ValueError("--anchor-end must be >= --anchor-start")
    return list(range(int(anchor_start), int(anchor_end) + 1))


def _parse_csv(raw: str | None) -> list[str] | None:
    if raw is None or not str(raw).strip():
        return None
    return [token.strip() for token in str(raw).split(",") if token.strip()]


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


if __name__ == "__main__":
    raise SystemExit(main())

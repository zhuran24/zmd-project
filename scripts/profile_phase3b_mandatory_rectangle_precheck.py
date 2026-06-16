from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.mandatory_core.mandatory_rectangle_precheck_profiler import (
    DEFAULT_ANCHOR_LIMIT,
    DEFAULT_CANDIDATE,
    DEFAULT_GROUP_LIMIT,
    build_phase3b_mandatory_rectangle_precheck_profile,
    render_phase3b_mandatory_rectangle_precheck_profile_markdown,
    render_phase3b_mandatory_rectangle_precheck_profile_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile Phase 3B mandatory-rectangle precheck by group and anchor sample."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--master-search-profile",
        default="exact_coordinate_guided_branching_v4",
    )
    parser.add_argument("--boundary-port-precheck-max-anchors", type=int, default=None)
    parser.add_argument("--mandatory-rectangle-precheck-max-anchors", type=int, default=None)
    parser.add_argument("--anchor-offset", type=int, default=0)
    parser.add_argument("--anchor-limit", type=int, default=DEFAULT_ANCHOR_LIMIT)
    parser.add_argument("--group-limit", type=int, default=DEFAULT_GROUP_LIMIT)
    parser.add_argument(
        "--group-ids",
        default=None,
        help="Optional comma-separated exact group ids to profile.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_mandatory_rectangle_precheck_profiler"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_mandatory_rectangle_precheck_profile(
        project_root,
        candidate=str(args.candidate),
        master_search_profile=str(args.master_search_profile),
        boundary_port_precheck_max_anchors=args.boundary_port_precheck_max_anchors,
        mandatory_rectangle_precheck_max_anchors=args.mandatory_rectangle_precheck_max_anchors,
        anchor_offset=int(args.anchor_offset),
        anchor_limit=int(args.anchor_limit),
        group_limit=int(args.group_limit),
        group_ids=_parse_csv(args.group_ids),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or f"mandatory_rectangle_precheck_{str(args.candidate).lower()}"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_mandatory_rectangle_precheck_profile_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_mandatory_rectangle_precheck_profile_text(report),
        )
        print(f"mandatory_rectangle_precheck_profile_json={_display_path(project_root, json_path)}")
        print(f"mandatory_rectangle_precheck_profile_md={_display_path(project_root, md_path)}")
        print(f"mandatory_rectangle_precheck_profile_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    sample = _mapping(report.get("sample"))
    timing = _mapping(report.get("timing"))
    print("phase3b mandatory-rectangle precheck profile")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- sampled anchors: {sample.get('sampled_anchor_count')}/{sample.get('available_anchor_count')}")
    print(f"- sampled groups: {sample.get('sampled_group_count')}/{sample.get('available_group_count')}")
    print(f"- total seconds: {timing.get('total_seconds')}")
    for group in list(report.get("groups", []))[:5]:
        if isinstance(group, Mapping):
            print(
                "- group "
                f"{group.get('group_id')} "
                f"oracle={group.get('oracle_mode')} "
                f"seconds={group.get('elapsed_seconds')} "
                f"pass={group.get('screen_pass_anchor_count')} "
                f"infeasible={group.get('screened_infeasible_anchor_count')}"
            )
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_csv(raw_value: str | None) -> list[str] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    return [token.strip() for token in str(raw_value).split(",") if token.strip()]


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

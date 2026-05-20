from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.pose_order.pose_order_validation_probe import (
    build_phase3b_pose_order_validation_probe,
    render_phase3b_pose_order_validation_probe_markdown,
    render_phase3b_pose_order_validation_probe_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B pose-order coordinate validation prefix probe without mutating campaign state."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository/project root to inspect.",
    )
    parser.add_argument(
        "--candidate",
        default="68x19",
        help="Candidate key in WxH form. Default: 68x19.",
    )
    parser.add_argument(
        "--anchor-index",
        type=int,
        default=None,
        help="Ghost anchor index to force. Defaults to the first matching pose-order validation rejection sample.",
    )
    parser.add_argument(
        "--ordering",
        default="y_then_x",
        help="Pose ordering to replay. Default: y_then_x.",
    )
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        help="Exact coordinate master search profile.",
    )
    parser.add_argument(
        "--boundary-port-precheck-max-anchors",
        type=int,
        default=None,
        help="Temporary diagnostic override for EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS.",
    )
    parser.add_argument(
        "--mandatory-rectangle-precheck-max-anchors",
        type=int,
        default=None,
        help="Temporary diagnostic override for EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS.",
    )
    parser.add_argument(
        "--validation-seconds",
        type=float,
        default=None,
        help="Temporary diagnostic override for EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS.",
    )
    parser.add_argument(
        "--max-prefix-groups",
        type=int,
        default=None,
        help="Stop after this many prefix groups. Default evaluates until first infeasible prefix or all groups.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_pose_order_validation_probe"),
        help="Directory for pose_order_validation_probe_<candidate>_<anchor>_<ordering>.json/md/txt.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the diagnostics summary but do not write report files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_pose_order_validation_probe(
        project_root,
        candidate=str(args.candidate),
        anchor_idx=args.anchor_index,
        ordering=str(args.ordering),
        master_search_profile=str(args.master_search_profile),
        boundary_port_precheck_max_anchors=args.boundary_port_precheck_max_anchors,
        mandatory_rectangle_precheck_max_anchors=args.mandatory_rectangle_precheck_max_anchors,
        validation_seconds=args.validation_seconds,
        max_prefix_groups=args.max_prefix_groups,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        suffix = _output_suffix(report)
        json_path = output_dir / f"pose_order_validation_probe_{suffix}.json"
        md_path = output_dir / f"pose_order_validation_probe_{suffix}.md"
        txt_path = output_dir / f"pose_order_validation_probe_{suffix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_pose_order_validation_probe_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_pose_order_validation_probe_text(report))
        print(f"pose_order_validation_probe_json={_display_path(project_root, json_path)}")
        print(f"pose_order_validation_probe_md={_display_path(project_root, md_path)}")
        print(f"pose_order_validation_probe_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    status = _mapping(report.get("status"))
    prefix = _mapping(_mapping(report.get("diagnostics")).get("prefix_probe"))
    first_group = _mapping(prefix.get("first_infeasible_group"))
    print("phase3b pose-order validation probe")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- anchor: {candidate.get('anchor_idx')}")
    print(f"- ordering: {profile.get('ordering')}")
    print(f"- outcome: {status.get('outcome')}")
    print(
        "- first infeasible prefix: "
        f"{prefix.get('first_infeasible_prefix_group_count')}"
    )
    if first_group:
        print(
            "- first infeasible group: "
            f"{first_group.get('group_id')} "
            f"{first_group.get('facility_type')} "
            f"required={first_group.get('required_count')}"
        )


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


def _output_suffix(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    raw = (
        f"{candidate.get('key', 'unknown')}_"
        f"anchor{candidate.get('anchor_idx', 'auto')}_"
        f"{profile.get('ordering', 'ordering')}"
    )
    return "".join(ch if ch.isalnum() else "_" for ch in str(raw).lower()).strip("_")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

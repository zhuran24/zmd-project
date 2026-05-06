from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_pre_master_profiler import (
    DEFAULT_CANDIDATE,
    build_phase3b_pre_master_empty_hint_anchor_scan,
    build_phase3b_pre_master_precheck_profile,
    render_phase3b_pre_master_empty_hint_anchor_scan_markdown,
    render_phase3b_pre_master_empty_hint_anchor_scan_text,
    render_phase3b_pre_master_profile_markdown,
    render_phase3b_pre_master_profile_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile a Phase 3B candidate's bounded pre-master prechecks."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--master-search-profile",
        default="exact_coordinate_guided_branching_v4",
    )
    parser.add_argument("--boundary-port-precheck-max-anchors", type=int, default=None)
    parser.add_argument(
        "--mandatory-rectangle-precheck-max-anchors",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--pre-master-mandatory-rectangle-precheck-max-anchors",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--coordinate-validation-precheck-max-anchors",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--coordinate-validation-precheck-seconds",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--coordinate-validation-scan-anchors",
        default=None,
        help=(
            "Run an explicit empty-hint coordinate validation scan instead of the "
            "standard short-circuit profiler. Supports comma-separated indexes "
            "and ranges such as 0,118-125,127."
        ),
    )
    parser.add_argument(
        "--coordinate-validation-scan-seconds",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--coordinate-validation-scan-exhaustive",
        action="store_true",
        help="Record that the requested scan intends to cover all ghost anchors.",
    )
    parser.add_argument(
        "--skip-mandatory-rectangle-precheck",
        action="store_true",
        help="Profile mandatory support and boundary only.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_pre_master_precheck_profiler"),
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Defaults to pre_master_profile_<candidate>.",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = _resolve_output_dir(project_root, args.output_dir)
    scan_anchor_indices = (
        None
        if args.coordinate_validation_scan_anchors is None
        else _parse_anchor_indices(str(args.coordinate_validation_scan_anchors))
    )
    default_prefix = (
        f"pre_master_empty_hint_anchor_scan_{str(args.candidate).lower()}"
        if scan_anchor_indices is not None
        else f"pre_master_profile_{str(args.candidate).lower()}"
    )
    output_prefix = args.output_prefix or default_prefix
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"

    def write_progress(payload: Mapping[str, Any]) -> None:
        if args.no_write:
            return
        atomic_write_json(json_path, dict(payload))

    if scan_anchor_indices is not None:
        scan = build_phase3b_pre_master_empty_hint_anchor_scan(
            project_root=project_root,
            candidate=str(args.candidate),
            anchor_indices=scan_anchor_indices,
            master_search_profile=str(args.master_search_profile),
            time_limit_seconds=float(args.coordinate_validation_scan_seconds),
            exhaustive=bool(args.coordinate_validation_scan_exhaustive),
            progress_callback=write_progress,
        )
        _print_scan_summary(scan)
        if not args.no_write:
            atomic_write_json(json_path, scan)
            _atomic_write_text(
                md_path,
                render_phase3b_pre_master_empty_hint_anchor_scan_markdown(scan),
            )
            _atomic_write_text(
                txt_path,
                render_phase3b_pre_master_empty_hint_anchor_scan_text(scan),
            )
            print(f"empty_hint_anchor_scan_json={_display_path(project_root, json_path)}")
            print(f"empty_hint_anchor_scan_md={_display_path(project_root, md_path)}")
            print(f"empty_hint_anchor_scan_txt={_display_path(project_root, txt_path)}")
        return 0

    profile = build_phase3b_pre_master_precheck_profile(
        project_root=project_root,
        candidate=str(args.candidate),
        master_search_profile=str(args.master_search_profile),
        boundary_port_precheck_max_anchors=args.boundary_port_precheck_max_anchors,
        mandatory_rectangle_precheck_max_anchors=args.mandatory_rectangle_precheck_max_anchors,
        pre_master_mandatory_rectangle_precheck_max_anchors=(
            args.pre_master_mandatory_rectangle_precheck_max_anchors
        ),
        coordinate_validation_precheck_max_anchors=(
            args.coordinate_validation_precheck_max_anchors
        ),
        coordinate_validation_precheck_seconds=(
            args.coordinate_validation_precheck_seconds
        ),
        include_mandatory_rectangle_precheck=not bool(
            args.skip_mandatory_rectangle_precheck
        ),
        progress_callback=write_progress,
    )
    _print_summary(profile)
    if not args.no_write:
        atomic_write_json(json_path, profile)
        _atomic_write_text(md_path, render_phase3b_pre_master_profile_markdown(profile))
        _atomic_write_text(txt_path, render_phase3b_pre_master_profile_text(profile))
        print(f"pre_master_profile_json={_display_path(project_root, json_path)}")
        print(f"pre_master_profile_md={_display_path(project_root, md_path)}")
        print(f"pre_master_profile_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(profile: Mapping[str, Any]) -> None:
    candidate = _mapping(profile.get("candidate"))
    status = _mapping(profile.get("status"))
    print("phase3b pre-master precheck profile")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- completed: {bool(status.get('completed', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- running stage: {status.get('running_stage')}")
    print(f"- precheck reason: {status.get('precheck_reason')}")
    print(f"- recommendation: {status.get('recommendation')}")
    for stage_id, stage in _mapping(profile.get("stages")).items():
        if not isinstance(stage, Mapping):
            continue
        elapsed = stage.get("elapsed_seconds")
        elapsed_text = "" if elapsed is None else f"{float(elapsed):.3f}s"
        print(f"- stage {stage_id}: {stage.get('status')} {elapsed_text}")


def _print_scan_summary(scan: Mapping[str, Any]) -> None:
    candidate = _mapping(scan.get("candidate"))
    status = _mapping(scan.get("status"))
    scan_payload = _mapping(scan.get("scan"))
    print("phase3b pre-master empty-hint anchor scan")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- completed: {bool(status.get('completed', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- evaluated anchors: {scan_payload.get('evaluated_anchor_count')}")
    print(f"- status counts: {scan_payload.get('status_counts')}")
    print(
        "- candidate elimination claim: "
        f"{scan_payload.get('candidate_elimination_claim')} "
        f"({scan_payload.get('candidate_elimination_claim_reason')})"
    )
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchor_indices(raw: str) -> list[int]:
    anchors: list[int] = []
    seen: set[int] = set()
    for part in str(raw).split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if end < start:
                raise ValueError(f"Invalid descending anchor range: {token!r}")
            values = range(start, end + 1)
        else:
            values = (int(token),)
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            anchors.append(int(value))
    return anchors


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

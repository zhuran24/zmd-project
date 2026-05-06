from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_start_compatibility import (
    build_phase3b_start_compatibility_diagnostics,
    render_phase3b_start_compatibility_markdown,
    render_phase3b_start_compatibility_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B start-compatibility diagnostics for one exact candidate without mutating campaign state."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository/project root to inspect.",
    )
    parser.add_argument(
        "--candidate",
        default="69x19",
        help="Candidate key in WxH form. Default: 69x19.",
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
        "--portfolio-probe-sample-limit",
        type=int,
        default=0,
        help="Diagnostic-only: run extended portfolio probes for this many failed anchor samples. Default: 0.",
    )
    parser.add_argument(
        "--portfolio-probe-max-window-size",
        type=int,
        default=3,
        help="Diagnostic-only: maximum failed-group window size for portfolio probes. Default: 3.",
    )
    parser.add_argument(
        "--portfolio-probe-max-attempts-per-sample",
        type=int,
        default=64,
        help="Diagnostic-only: max portfolio attempts for each failed anchor sample. Default: 64.",
    )
    parser.add_argument(
        "--group-packing-probe-sample-limit",
        type=int,
        default=0,
        help="Diagnostic-only: run exact group packing probes for this many failed anchor samples. Default: 0.",
    )
    parser.add_argument(
        "--group-packing-time-limit-seconds",
        type=float,
        default=2.0,
        help="Diagnostic-only: CP-SAT time limit for each group packing probe. Default: 2.0.",
    )
    parser.add_argument(
        "--group-packing-max-candidates",
        type=int,
        default=2500,
        help="Diagnostic-only: skip group packing probes above this surviving candidate count. Default: 2500.",
    )
    parser.add_argument(
        "--failed-anchor-sample-limit",
        type=int,
        default=None,
        help="Diagnostic-only: override retained failed-anchor sample count. Default keeps runtime-safe limit.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_start_compatibility"),
        help="Directory for start_compatibility_<candidate>.json/md/txt.",
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
    diagnostics = build_phase3b_start_compatibility_diagnostics(
        project_root=project_root,
        candidate=str(args.candidate),
        master_search_profile=str(args.master_search_profile),
        boundary_port_precheck_max_anchors=args.boundary_port_precheck_max_anchors,
        mandatory_rectangle_precheck_max_anchors=args.mandatory_rectangle_precheck_max_anchors,
        portfolio_probe_sample_limit=args.portfolio_probe_sample_limit,
        portfolio_probe_max_window_size=args.portfolio_probe_max_window_size,
        portfolio_probe_max_attempts_per_sample=args.portfolio_probe_max_attempts_per_sample,
        group_packing_probe_sample_limit=args.group_packing_probe_sample_limit,
        group_packing_time_limit_seconds=args.group_packing_time_limit_seconds,
        group_packing_max_candidates=args.group_packing_max_candidates,
        failed_anchor_sample_limit=args.failed_anchor_sample_limit,
    )
    _print_summary(diagnostics)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        suffix = _safe_candidate_suffix(str(args.candidate))
        json_path = output_dir / f"start_compatibility_{suffix}.json"
        md_path = output_dir / f"start_compatibility_{suffix}.md"
        txt_path = output_dir / f"start_compatibility_{suffix}.txt"
        atomic_write_json(json_path, diagnostics)
        _atomic_write_text(md_path, render_phase3b_start_compatibility_markdown(diagnostics))
        _atomic_write_text(txt_path, render_phase3b_start_compatibility_text(diagnostics))
        print(f"start_compatibility_json={_display_path(project_root, json_path)}")
        print(f"start_compatibility_md={_display_path(project_root, md_path)}")
        print(f"start_compatibility_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(diagnostics: Mapping[str, Any]) -> None:
    candidate = _mapping(diagnostics.get("candidate"))
    status = _mapping(diagnostics.get("status"))
    diag = _mapping(diagnostics.get("diagnostics"))
    start_failure = _mapping(diag.get("start_failure_summary"))
    print("phase3b start compatibility diagnostics")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- compatible start found: {bool(status.get('compatible_start_found', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- failed anchors: {start_failure.get('failed_anchor_count', 0)}")
    print(f"- failure reasons: {start_failure.get('failure_reason_counts', {})}")
    portfolio_probe = _mapping(_mapping(diagnostics.get("diagnostics")).get("portfolio_probe"))
    if bool(portfolio_probe.get("enabled", False)):
        print(f"- portfolio probe success: {bool(portfolio_probe.get('success_found', False))}")
        print(f"- portfolio probe samples: {portfolio_probe.get('sample_count', 0)}")
    group_packing_probe = _mapping(_mapping(diagnostics.get("diagnostics")).get("group_packing_probe"))
    if bool(group_packing_probe.get("enabled", False)):
        print(f"- group packing feasible: {bool(group_packing_probe.get('feasible_found', False))}")
        print(f"- group packing samples: {group_packing_probe.get('sample_count', 0)}")
    first_group = _mapping(start_failure.get("first_failed_group"))
    if first_group:
        print(
            "- first failed group: "
            f"{first_group.get('group_id')} "
            f"position={first_group.get('position')} "
            f"surviving_at_failure={first_group.get('surviving_at_failure_count')}"
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


def _safe_candidate_suffix(candidate: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(candidate).lower()).strip("_")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

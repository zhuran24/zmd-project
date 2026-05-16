from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.coordinate_validation.precheck_candidate import (
    DEFAULT_FORCED_ANCHOR_SOLVER_MATRIX_PATH,
    DEFAULT_B5A_SUMMARY_PATH,
    DEFAULT_ANCHOR119_PAIR_X_CORE_SYNTHESIS_PATH,
    DEFAULT_ANCHOR119_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH,
    DEFAULT_ANCHOR119_ROW_DOMAIN_REVIEW_STATE_PATH,
    DEFAULT_ANCHOR119_ROW_DOMAIN_RUNTIME_PATCH_STATUS_PATH,
    DEFAULT_JOINED_XY_DELTA_SYNTHESIS_PATH,
    DEFAULT_JOINED_XY_PROFILE_PROBE_PATH,
    DEFAULT_ORDER_IMPLIED_CAPACITY_EXPLANATION_PATH,
    DEFAULT_START_COMPATIBILITY_PATH,
    build_phase3b_coordinate_validation_precheck_candidate_summary,
    render_phase3b_coordinate_validation_precheck_candidate_markdown,
    render_phase3b_coordinate_validation_precheck_candidate_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B coordinate-validation precheck candidate gate."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--start-compatibility",
        type=Path,
        default=DEFAULT_START_COMPATIBILITY_PATH,
        help="Path to start_compatibility_<candidate>.json.",
    )
    parser.add_argument(
        "--forced-anchor-solver-matrix",
        type=Path,
        default=DEFAULT_FORCED_ANCHOR_SOLVER_MATRIX_PATH,
        help="Path to forced_anchor_solver_matrix_<candidate>.json.",
    )
    parser.add_argument(
        "--joined-xy-profile-probe",
        type=Path,
        default=DEFAULT_JOINED_XY_PROFILE_PROBE_PATH,
        help="Path to joined-XY coordinate_validation_profile_probe json.",
    )
    parser.add_argument(
        "--joined-xy-delta-synthesis",
        type=Path,
        default=DEFAULT_JOINED_XY_DELTA_SYNTHESIS_PATH,
        help="Path to joined-XY coordinate_validation delta synthesis json.",
    )
    parser.add_argument(
        "--b5a-summary",
        type=Path,
        default=DEFAULT_B5A_SUMMARY_PATH,
        help="Path to joined-XY B5A operator summary json.",
    )
    parser.add_argument(
        "--anchor119-pair-x-core-synthesis",
        type=Path,
        default=DEFAULT_ANCHOR119_PAIR_X_CORE_SYNTHESIS_PATH,
        help="Path to anchor119 pair-x core synthesis json.",
    )
    parser.add_argument(
        "--anchor119-pair-x-no-ghost-space-synthesis",
        type=Path,
        default=DEFAULT_ANCHOR119_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH,
        help="Path to anchor119 pair-x no-ghost-space synthesis json.",
    )
    parser.add_argument(
        "--order-implied-capacity-explanation",
        type=Path,
        default=DEFAULT_ORDER_IMPLIED_CAPACITY_EXPLANATION_PATH,
        help="Path to order-implied capacity explanation json.",
    )
    parser.add_argument(
        "--anchor119-row-domain-runtime-patch-status",
        type=Path,
        default=DEFAULT_ANCHOR119_ROW_DOMAIN_RUNTIME_PATCH_STATUS_PATH,
        help="Path to anchor119 row-domain runtime patch status json.",
    )
    parser.add_argument(
        "--anchor119-row-domain-review-state",
        type=Path,
        default=None,
        help="Path to anchor119 row-domain repo-side review-state marker json.",
    )
    parser.add_argument("--min-rejected-anchor-count", type=int, default=1)
    parser.add_argument("--min-matrix-infeasible-count", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_coordinate_validation_precheck_candidate"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    summary = build_phase3b_coordinate_validation_precheck_candidate_summary(
        project_root,
        start_compatibility_path=args.start_compatibility,
        forced_anchor_solver_matrix_path=args.forced_anchor_solver_matrix,
        joined_xy_profile_probe_path=args.joined_xy_profile_probe,
        joined_xy_delta_synthesis_path=args.joined_xy_delta_synthesis,
        b5a_summary_path=args.b5a_summary,
        anchor119_pair_x_core_synthesis_path=args.anchor119_pair_x_core_synthesis,
        anchor119_pair_x_no_ghost_space_synthesis_path=args.anchor119_pair_x_no_ghost_space_synthesis,
        order_implied_capacity_explanation_path=args.order_implied_capacity_explanation,
        anchor119_row_domain_runtime_patch_status_path=args.anchor119_row_domain_runtime_patch_status,
        anchor119_row_domain_review_state_path=args.anchor119_row_domain_review_state,
        min_rejected_anchor_count=int(args.min_rejected_anchor_count),
        min_matrix_infeasible_count=int(args.min_matrix_infeasible_count),
    )
    _print_summary(summary)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "precheck_candidate.json"
        md_path = output_dir / "precheck_candidate.md"
        txt_path = output_dir / "precheck_candidate.txt"
        atomic_write_json(json_path, summary)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_precheck_candidate_markdown(summary),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_precheck_candidate_text(summary),
        )
        print(f"coordinate_precheck_candidate_json={_display_path(project_root, json_path)}")
        print(f"coordinate_precheck_candidate_md={_display_path(project_root, md_path)}")
        print(f"coordinate_precheck_candidate_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(summary: Mapping[str, Any]) -> None:
    candidate = _mapping(summary.get("candidate"))
    gate = _mapping(summary.get("gate"))
    validation = _mapping(summary.get("coordinate_validation"))
    matrix = _mapping(summary.get("forced_anchor_solver_matrix"))
    failed_checks = [
        str(check.get("check_id"))
        for check in list(summary.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b coordinate-validation precheck candidate gate")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- design gate passed: {bool(gate.get('design_gate_passed', False))}")
    print(f"- runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}")
    print(f"- coordinate rejected count: {validation.get('rejected_count', 0)}")
    print(f"- matrix outcome: {matrix.get('outcome')}")
    print(f"- recommendation: {gate.get('recommendation')}")
    if failed_checks:
        print(f"- failed checks: {failed_checks}")


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

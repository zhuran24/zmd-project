from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.phase3b.anchor119.mixed_lane_dp_crosscheck import (
    build_phase3b_anchor119_mixed_lane_dp_crosscheck,
    write_phase3b_anchor119_mixed_lane_dp_crosscheck,
)
from src.search.phase3b.anchor119.mixed_lane_tiling_verifier import (
    DEFAULT_ANCHOR_IDX,
    DEFAULT_CANDIDATE,
    DEFAULT_PLANTER_GROUP_ID,
    DEFAULT_PROTOCOL_GROUP_ID,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B anchor119 mixed-lane DP cross-check diagnostic."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--anchor-index", type=int, default=DEFAULT_ANCHOR_IDX)
    parser.add_argument("--planter-group-id", default=DEFAULT_PLANTER_GROUP_ID)
    parser.add_argument("--protocol-group-id", default=DEFAULT_PROTOCOL_GROUP_ID)
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument(
        "--reference-tiling-report",
        type=Path,
        default=Path(
            ".artifacts/phase3b_anchor119_mixed_lane_tiling_verifier_module_20260423/"
            "mixed_lane_tiling_verifier.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_anchor119_mixed_lane_dp_crosscheck"),
    )
    parser.add_argument("--output-prefix", default="mixed_lane_dp_crosscheck")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_anchor119_mixed_lane_dp_crosscheck(
        project_root,
        candidate=str(args.candidate),
        anchor_idx=int(args.anchor_index),
        planter_group_id=str(args.planter_group_id),
        protocol_group_id=str(args.protocol_group_id),
        master_search_profile=str(args.master_search_profile),
        reference_tiling_report_path=Path(args.reference_tiling_report),
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_anchor119_mixed_lane_dp_crosscheck(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        for key, value in paths.items():
            print(f"mixed_lane_dp_crosscheck_{key}={_display_path(project_root, Path(value))}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    cross = _mapping(report.get("crosscheck"))
    candidate = _mapping(report.get("candidate"))
    provenance = _mapping(report.get("provenance"))
    print("phase3b anchor119 mixed-lane DP cross-check")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- anchor_idx: {candidate.get('anchor_idx')}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- runtime_promotion_ready: {bool(status.get('runtime_promotion_ready', False))}")
    print(f"- final_cover_states: {cross.get('total_final_cover_states')}")
    print(f"- p9p10_pairs_checked: {cross.get('total_p9_p10_pairs_checked')}")
    print(f"- witness_found: {bool(report.get('witness'))}")
    print(f"- domain_hash_match: {provenance.get('domain_rows_sha256_matches_reference')}")
    print("- solver_invoked: false")
    print("- proof_source: false")


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())


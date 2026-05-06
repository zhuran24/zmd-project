from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.phase3b_signature_region_equivalence_audit import (
    DEFAULT_CANDIDATE,
    DEFAULT_GROUP_ID,
    build_phase3b_signature_region_equivalence_audit,
    render_phase3b_signature_region_equivalence_audit_markdown,
    render_phase3b_signature_region_equivalence_audit_text,
    write_phase3b_signature_region_equivalence_audit,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B no-solve signature-region equivalence audit."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--group-id", default=DEFAULT_GROUP_ID)
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument(
        "--disable-symmetry-breaking",
        action="store_true",
        help="Build the diagnostic overlay without coordinate symmetry breaking.",
    )
    parser.add_argument("--sample-limit", type=int, default=8)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_signature_region_equivalence_audit"),
    )
    parser.add_argument("--output-prefix", default="signature_region_equivalence_audit")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_signature_region_equivalence_audit(
        project_root,
        candidate=str(args.candidate),
        group_id=str(args.group_id),
        master_search_profile=str(args.master_search_profile),
        enable_symmetry_breaking=not bool(args.disable_symmetry_breaking),
        sample_limit=int(args.sample_limit),
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_signature_region_equivalence_audit(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        for key, value in paths.items():
            print(f"signature_region_equivalence_{key}={_display_path(project_root, Path(value))}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    target = _mapping(report.get("target_group"))
    eq = _mapping(report.get("equivalence"))
    print("phase3b signature-region equivalence audit")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- group: {target.get('group_id')}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- bucket_count: {eq.get('bucket_count')}")
    print(f"- mismatched_bucket_count: {eq.get('mismatched_bucket_count')}")
    print(f"- overlap_tuple_count: {eq.get('overlap_tuple_count')}")
    print(f"- recommendation: {status.get('recommendation')}")
    print("- solver_invoked: false")
    print("- diagnostic_semantics: no_solve_signature_region_equivalence_not_proof_source")
    if bool(report.get("model_error")):
        print(f"- model_error: {report.get('model_error')}")


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

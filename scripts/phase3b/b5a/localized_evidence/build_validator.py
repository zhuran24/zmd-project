from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.b5a.localized_evidence.validator import (
    DEFAULT_READINESS_PATH,
    build_phase3b_b5a_localized_evidence_validator,
    write_phase3b_b5a_localized_evidence_validator,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B B5A localized evidence validator artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--localized-evidence-readiness",
        type=Path,
        default=DEFAULT_READINESS_PATH,
    )
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_b5a_localized_evidence_validator_20260425"),
    )
    parser.add_argument("--output-prefix", default="b5a_localized_evidence_validator")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=args.localized_evidence_readiness,
        expected_candidate=str(args.candidate),
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_b5a_localized_evidence_validator(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        for key, value in paths.items():
            print(
                "b5a_localized_evidence_validator_"
                f"{key}={_display_path(project_root, Path(value))}"
            )
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    failed = [
        str(check.get("check_id"))
        for check in list(report.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b B5A localized evidence validator")
    print(
        "- validator ready: "
        f"{bool(status.get('localized_evidence_validator_ready', False))}"
    )
    print(
        "- current localized evidence validated: "
        f"{bool(status.get('current_localized_evidence_validated', False))}"
    )
    print(
        "- reviewer acceptance required: "
        f"{bool(status.get('reviewer_acceptance_required', False))}"
    )
    print(f"- certified anchor found: {bool(status.get('certified_anchor_found', False))}")
    print(f"- b5a anchor found: {bool(status.get('b5a_anchor_found', False))}")
    print(f"- proof_source: {bool(status.get('proof_source', False))}")
    print(
        "- runtime_semantics_changed: "
        f"{bool(status.get('runtime_semantics_changed', False))}"
    )
    print(f"- checkpoint_written: {bool(status.get('checkpoint_written', False))}")
    print(f"- recommended next step: {status.get('recommended_next_step')}")
    if failed:
        print(f"- failed checks: {failed}")


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

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.review_state import (
    build_phase3b_coordinate_validation_anchor119_row_domain_review_state,
    write_phase3b_coordinate_validation_anchor119_row_domain_review_state,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase 3B anchor119 repo-side reviewed-runtime-patch state marker."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--signoff-record-validator", type=Path, default=None)
    parser.add_argument("--ingest-review-record-validator", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_review_state_20260425"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_coordinate_validation_anchor119_row_domain_review_state(
        project_root,
        signoff_record_validator_path=args.signoff_record_validator,
        ingest_review_record_validator_path=args.ingest_review_record_validator,
    )
    status = report.get("status", {})

    if args.no_write:
        print("phase3b anchor119 row-domain review state")
        print("review_state_ready=" + str(bool(status.get("review_state_ready", False))))
        print(
            "repo_side_review_state_updated="
            + str(bool(status.get("repo_side_review_state_updated", False)))
        )
        print(
            "reviewed_runtime_patch_exists="
            + str(bool(status.get("reviewed_runtime_patch_exists", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(status.get("runtime_enablement_allowed", False)))
        )
        print(
            "production_acceptance_refresh_completed="
            + str(bool(status.get("production_acceptance_refresh_completed", False)))
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    output_dir = _resolve_output_dir(project_root, args.output_dir)
    written = write_phase3b_coordinate_validation_anchor119_row_domain_review_state(
        report,
        output_dir,
    )
    print("anchor119_row_domain_review_state_json=" + str(Path(written["json"]).resolve()))
    print("anchor119_row_domain_review_state_md=" + str(Path(written["md"]).resolve()))
    print("anchor119_row_domain_review_state_txt=" + str(Path(written["txt"]).resolve()))
    return 0


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


if __name__ == "__main__":
    raise SystemExit(main())

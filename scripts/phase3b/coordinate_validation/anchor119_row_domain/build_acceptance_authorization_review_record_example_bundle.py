from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_record_example_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_text,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain acceptance-authorization review "
            "record example bundle artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--acceptance-authorization-review-record-scaffold",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--acceptance-authorization-review-record-validator",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/"
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_record_example_bundle_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle(
            project_root,
            acceptance_authorization_review_record_scaffold_path=(
                args.acceptance_authorization_review_record_scaffold
            ),
            acceptance_authorization_review_record_validator_path=(
                args.acceptance_authorization_review_record_validator
            ),
        )
    )

    if args.no_write:
        print(
            render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_text(
                report
            ),
            end="",
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_record_example_bundle_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_record_example_bundle_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_record_example_bundle_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

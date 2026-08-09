from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain acceptance-authorization review "
            "record validator artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--acceptance-authorization-review-record-scaffold",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--acceptance-authorization-review-bundle",
        type=Path,
        default=None,
    )
    parser.add_argument("--acceptance-execution-gate", type=Path, default=None)
    parser.add_argument("--acceptance-result-validator", type=Path, default=None)
    parser.add_argument(
        "--acceptance-authorization-review-record-payload",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/"
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_record_validator_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            project_root,
            acceptance_authorization_review_record_scaffold_path=(
                args.acceptance_authorization_review_record_scaffold
            ),
            acceptance_authorization_review_bundle_path=(
                args.acceptance_authorization_review_bundle
            ),
            acceptance_execution_gate_path=args.acceptance_execution_gate,
            acceptance_result_validator_path=args.acceptance_result_validator,
            acceptance_authorization_review_record_payload_path=(
                args.acceptance_authorization_review_record_payload
            ),
        )
    )

    if args.no_write:
        print(
            render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text(
                report
            ),
            end="",
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_record_validator_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_record_validator_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_record_validator_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

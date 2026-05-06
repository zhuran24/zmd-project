from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain acceptance-authorization "
            "operator handoff bundle artifact."
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
        "--acceptance-authorization-review-record-example-bundle",
        type=Path,
        default=None,
    )
    parser.add_argument("--acceptance-execution-gate", type=Path, default=None)
    parser.add_argument("--acceptance-execution-staging", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_operator_handoff_bundle_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle(
            project_root,
            acceptance_authorization_review_record_scaffold_path=(
                args.acceptance_authorization_review_record_scaffold
            ),
            acceptance_authorization_review_record_validator_path=(
                args.acceptance_authorization_review_record_validator
            ),
            acceptance_authorization_review_record_example_bundle_path=(
                args.acceptance_authorization_review_record_example_bundle
            ),
            acceptance_execution_gate_path=args.acceptance_execution_gate,
            acceptance_execution_staging_path=args.acceptance_execution_staging,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        bundle = report.get("acceptance_authorization_operator_handoff_bundle", {})
        locked_execution_target = bundle.get("locked_execution_target", {})
        print(
            "phase3b anchor119 row-domain acceptance authorization operator handoff bundle"
        )
        print(
            "acceptance_authorization_operator_handoff_bundle_ready="
            + str(
                bool(
                    status.get(
                        "acceptance_authorization_operator_handoff_bundle_ready",
                        False,
                    )
                )
            )
        )
        print(
            "future_manual_authorization_review_prerequisites_met="
            + str(
                bool(
                    status.get(
                        "future_manual_authorization_review_prerequisites_met", False
                    )
                )
            )
        )
        print(
            "acceptance_execution_authorized="
            + str(bool(status.get("acceptance_execution_authorized", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(status.get("runtime_enablement_allowed", False)))
        )
        print("acceptance_executed=" + str(bool(status.get("acceptance_executed", False))))
        print(
            "actual_human_authorization_review_happened="
            + str(
                bool(status.get("actual_human_authorization_review_happened", False))
            )
        )
        print(
            "still_blocked_gate_ids="
            + ",".join(report.get("still_blocked_gate_ids", []))
        )
        print(
            "production_profile_id="
            + str(locked_execution_target.get("production_profile_id"))
        )
        print(
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command"))
        )
        print(
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path"))
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

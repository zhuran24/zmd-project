from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.ingest_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator,
    write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain ingest review record validator artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ingest-review-record-scaffold", type=Path, default=None)
    parser.add_argument("--reviewed-runtime-patch-ingest-gate", type=Path, default=None)
    parser.add_argument("--signoff-record-validator", type=Path, default=None)
    parser.add_argument("--ingest-review-record-payload", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            project_root,
            ingest_review_record_scaffold_path=args.ingest_review_record_scaffold,
            reviewed_runtime_patch_ingest_gate_path=args.reviewed_runtime_patch_ingest_gate,
            signoff_record_validator_path=args.signoff_record_validator,
            ingest_review_record_payload_path=args.ingest_review_record_payload,
        )
    )

    if args.no_write:
        validator = report.get("ingest_review_record_validator", {})
        locked_target = (
            validator.get("locked_target_review_state", {})
            if isinstance(validator, dict)
            else {}
        )
        actual_validation = (
            validator.get("actual_record_validation", {})
            if isinstance(validator, dict)
            else {}
        )
        print("phase3b anchor119 row-domain ingest review record validator")
        print(
            "ingest_review_record_validator_ready="
            + str(
                bool(
                    report.get("status", {}).get(
                        "ingest_review_record_validator_ready", False
                    )
                )
            )
        )
        print(
            "manual_ingest_review_record_provided="
            + str(
                bool(
                    report.get("status", {}).get(
                        "manual_ingest_review_record_provided", False
                    )
                )
            )
        )
        print(
            "manual_ingest_review_record_validated="
            + str(
                bool(
                    report.get("status", {}).get(
                        "manual_ingest_review_record_validated", False
                    )
                )
            )
        )
        print(
            "manual_ingest_review_record_validation_status="
            + str(
                report.get("status", {}).get(
                    "manual_ingest_review_record_validation_status"
                )
            )
        )
        print(
            "reviewed_runtime_patch_exists="
            + str(bool(report.get("status", {}).get("reviewed_runtime_patch_exists", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(report.get("status", {}).get("runtime_enablement_allowed", False)))
        )
        print(
            "recommended_next_step="
            + str(report.get("status", {}).get("recommended_next_step"))
        )
        print("record_identity=" + str(locked_target.get("record_identity")))
        print(
            "actual_record_payload_path="
            + str(actual_validation.get("record_payload_path"))
        )
        print(
            "actual_record_failed_rule_count="
            + str(actual_validation.get("failed_rule_count"))
        )
        print(
            "actual_record_validation_status="
            + str(actual_validation.get("validation_status"))
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            report, output_dir
        )
    )
    print(
        "anchor119_row_domain_ingest_review_record_validator_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_record_validator_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_record_validator_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

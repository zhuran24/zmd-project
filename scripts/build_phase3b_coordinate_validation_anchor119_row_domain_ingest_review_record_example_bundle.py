from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle,
    write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain ingest-review record example "
            "bundle artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ingest-review-record-scaffold", type=Path, default=None)
    parser.add_argument("--ingest-review-record-validator", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle(
            project_root,
            ingest_review_record_scaffold_path=args.ingest_review_record_scaffold,
            ingest_review_record_validator_path=args.ingest_review_record_validator,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        bundle = report.get("ingest_review_record_example_bundle", {})
        locked_target = (
            bundle.get("locked_target_review_state", {})
            if isinstance(bundle, dict)
            else {}
        )
        print("phase3b anchor119 row-domain ingest review record example bundle")
        print(
            "ingest_review_record_example_bundle_ready="
            + str(bool(status.get("ingest_review_record_example_bundle_ready", False)))
        )
        print(
            "synthetic_ingest_review_record_example_generated="
            + str(
                bool(
                    status.get(
                        "synthetic_ingest_review_record_example_generated", False
                    )
                )
            )
        )
        print(
            "synthetic_ingest_review_record_example_validated="
            + str(
                bool(
                    status.get(
                        "synthetic_ingest_review_record_example_validated", False
                    )
                )
            )
        )
        print(
            "synthetic_ingest_review_record_validation_status="
            + str(status.get("synthetic_ingest_review_record_validation_status"))
        )
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
        print("validator_target=" + str(bundle.get("validator_target")))
        print("record_identity=" + str(locked_target.get("record_identity")))
        print(
            "recommended_next_step=" + str(status.get("recommended_next_step"))
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle(
            report,
            output_dir,
        )
    )
    print(
        "anchor119_row_domain_ingest_review_record_example_bundle_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_record_example_bundle_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_record_example_bundle_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

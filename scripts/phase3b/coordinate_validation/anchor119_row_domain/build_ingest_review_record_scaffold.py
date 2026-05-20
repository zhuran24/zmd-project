from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.ingest_review_record_scaffold import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold,
    write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain ingest review record scaffold artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--reviewed-runtime-patch-ingest-gate", type=Path, default=None)
    parser.add_argument("--reviewer-record-collection", type=Path, default=None)
    parser.add_argument("--signoff-record-validator", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold(
            project_root,
            reviewed_runtime_patch_ingest_gate_path=args.reviewed_runtime_patch_ingest_gate,
            reviewer_record_collection_path=args.reviewer_record_collection,
            signoff_record_validator_path=args.signoff_record_validator,
        )
    )

    if args.no_write:
        scaffold = report.get("ingest_review_record_scaffold", {})
        target = (
            scaffold.get("locked_target_review_state", {})
            if isinstance(scaffold, dict)
            else {}
        )
        print("phase3b anchor119 row-domain ingest review record scaffold")
        print(
            "ingest_review_record_scaffold_ready="
            + str(
                bool(
                    report.get("status", {}).get(
                        "ingest_review_record_scaffold_ready", False
                    )
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
        print("record_identity=" + str(target.get("record_identity")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold(
            report, output_dir
        )
    )
    print(
        "anchor119_row_domain_ingest_review_record_scaffold_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_record_scaffold_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_record_scaffold_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

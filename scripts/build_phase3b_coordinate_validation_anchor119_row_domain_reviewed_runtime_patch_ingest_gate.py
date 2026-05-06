from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate import (
    build_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate,
    write_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain reviewed runtime patch ingest gate artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--signoff-record-validator", type=Path, default=None)
    parser.add_argument("--reviewer-record-collection", type=Path, default=None)
    parser.add_argument("--runtime-patch-status", type=Path, default=None)
    parser.add_argument("--runtime-patch-signoff-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate(
            project_root,
            signoff_record_validator_path=args.signoff_record_validator,
            reviewer_record_collection_path=args.reviewer_record_collection,
            runtime_patch_status_path=args.runtime_patch_status,
            runtime_patch_signoff_bundle_path=args.runtime_patch_signoff_bundle,
        )
    )

    if args.no_write:
        ingest_gate = report.get("reviewed_runtime_patch_ingest_gate", {})
        handoff = (
            ingest_gate.get("locked_reviewer_record_handoff", {})
            if isinstance(ingest_gate, dict)
            else {}
        )
        print("phase3b anchor119 row-domain reviewed runtime patch ingest gate")
        print(
            "reviewed_runtime_patch_ingest_gate_ready="
            + str(
                bool(
                    report.get("status", {}).get(
                        "reviewed_runtime_patch_ingest_gate_ready", False
                    )
                )
            )
        )
        print(
            "future_review_state_marking_prerequisites_met="
            + str(
                bool(
                    report.get("status", {}).get(
                        "future_review_state_marking_prerequisites_met", False
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
        print("handoff_path_shape=" + str(handoff.get("handoff_path_shape")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate(
            report, output_dir
        )
    )
    print(
        "anchor119_row_domain_reviewed_runtime_patch_ingest_gate_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_reviewed_runtime_patch_ingest_gate_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_reviewed_runtime_patch_ingest_gate_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

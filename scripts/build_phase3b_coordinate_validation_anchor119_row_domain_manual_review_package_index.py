from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index import (
    build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index,
    write_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain manual-review package index artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ingest-review-cover-note", type=Path, default=None)
    parser.add_argument("--acceptance-authorization-cover-note", type=Path, default=None)
    parser.add_argument("--ingest-review-instruction-packet", type=Path, default=None)
    parser.add_argument(
        "--acceptance-authorization-instruction-packet", type=Path, default=None
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index(
            project_root,
            ingest_review_cover_note_path=args.ingest_review_cover_note,
            acceptance_authorization_cover_note_path=args.acceptance_authorization_cover_note,
            ingest_review_instruction_packet_path=args.ingest_review_instruction_packet,
            acceptance_authorization_instruction_packet_path=args.acceptance_authorization_instruction_packet,
        )
    )

    status = report.get("status", {})
    if args.no_write:
        print("phase3b anchor119 row-domain manual review package index")
        print(
            "manual_review_package_index_ready="
            + str(bool(status.get("manual_review_package_index_ready", False)))
        )
        print("contract_compatible=" + str(bool(status.get("contract_compatible", False))))
        print(
            "required_artifacts_ready="
            + str(bool(status.get("required_artifacts_ready", False)))
        )
        print(
            "primary_entrypoints_available="
            + str(bool(status.get("primary_entrypoints_available", False)))
        )
        print(
            "global_blocker_gate_ids="
            + ",".join(status.get("global_blocker_gate_ids", []))
            if isinstance(status.get("global_blocker_gate_ids"), list)
            else "global_blocker_gate_ids="
        )
        print(
            "missing_ready_gate_ids="
            + ",".join(status.get("missing_ready_gate_ids", []))
            if isinstance(status.get("missing_ready_gate_ids"), list)
            else "missing_ready_gate_ids="
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    written = write_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index(
        report,
        output_dir,
    )
    print(
        "anchor119_row_domain_manual_review_package_index_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_manual_review_package_index_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_manual_review_package_index_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note,
    write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain ingest-review cover note artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--instruction-packet", type=Path, default=None)
    parser.add_argument("--operator-handoff-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note(
        project_root,
        ingest_review_instruction_packet_path=args.instruction_packet,
        ingest_review_operator_handoff_bundle_path=args.operator_handoff_bundle,
    )

    if args.no_write:
        status = report.get("status", {})
        paths = report.get("paths", {})
        print("phase3b anchor119 row-domain ingest review cover note")
        print(
            "ingest_review_cover_note_ready="
            + str(bool(status.get("ingest_review_cover_note_ready", False)))
        )
        print(
            "upstream_instruction_packet_ready="
            + str(bool(status.get("upstream_instruction_packet_ready", False)))
        )
        print(
            "upstream_operator_handoff_bundle_ready="
            + str(bool(status.get("upstream_operator_handoff_bundle_ready", False)))
        )
        print("contract_compatible=" + str(bool(status.get("contract_compatible", False))))
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
            "instruction_packet_path="
            + str(paths.get("ingest_review_instruction_packet"))
        )
        print(
            "operator_handoff_bundle_path="
            + str(paths.get("ingest_review_operator_handoff_bundle"))
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    written = write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note(
        report, output_dir
    )
    print(
        "anchor119_row_domain_ingest_review_cover_note_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_cover_note_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_cover_note_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

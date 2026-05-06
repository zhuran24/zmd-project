from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note,
    write_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain final human handoff note artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ingest-review-cover-note", type=Path, default=None)
    parser.add_argument("--ingest-review-instruction-packet", type=Path, default=None)
    parser.add_argument(
        "--acceptance-authorization-cover-note", type=Path, default=None
    )
    parser.add_argument(
        "--acceptance-authorization-instruction-packet", type=Path, default=None
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
            "final_human_handoff_note_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note(
            project_root,
            ingest_review_cover_note_path=args.ingest_review_cover_note,
            ingest_review_instruction_packet_path=args.ingest_review_instruction_packet,
            acceptance_authorization_cover_note_path=(
                args.acceptance_authorization_cover_note
            ),
            acceptance_authorization_instruction_packet_path=(
                args.acceptance_authorization_instruction_packet
            ),
        )
    )

    if args.no_write:
        status = report.get("status", {})
        candidate = report.get("candidate", {})
        print("phase3b anchor119 row-domain final human handoff note")
        print(
            "final_human_handoff_note_ready="
            + str(bool(status.get("final_human_handoff_note_ready", False)))
        )
        print("candidate_key=" + str(candidate.get("key")))
        print("anchor_idx=" + str(candidate.get("anchor_idx")))
        print(
            "formulation_profile=" + str(candidate.get("formulation_profile"))
        )
        print(
            "still_blocked_gate_ids="
            + ",".join(status.get("still_blocked_gate_ids", []))
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        print("final_handoff_summary=" + str(status.get("final_handoff_summary")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_final_human_handoff_note_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_final_human_handoff_note_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_final_human_handoff_note_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

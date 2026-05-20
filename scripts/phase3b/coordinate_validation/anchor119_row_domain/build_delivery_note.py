from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.delivery_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_delivery_note,
    write_phase3b_coordinate_validation_anchor119_row_domain_delivery_note,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain package delivery note artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--manual-review-package-index", type=Path, default=None)
    parser.add_argument("--final-human-handoff-note", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_delivery_note_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = build_phase3b_coordinate_validation_anchor119_row_domain_delivery_note(
        project_root,
        manual_review_package_index_path=args.manual_review_package_index,
        final_human_handoff_note_path=args.final_human_handoff_note,
    )

    status = report.get("status", {})
    note = report.get("delivery_note", {})
    note_target = note.get("note_target", {})

    if args.no_write:
        print("phase3b anchor119 row-domain delivery note")
        print("delivery_note_ready=" + str(bool(status.get("delivery_note_ready", False))))
        print("candidate_key=" + str(note_target.get("candidate_key")))
        print("anchor_idx=" + str(note_target.get("anchor_idx")))
        print("formulation_profile=" + str(note_target.get("formulation_profile")))
        print(
            "top_blocker_gate_ids="
            + ",".join(status.get("top_blocker_gate_ids", []))
            if isinstance(status.get("top_blocker_gate_ids"), list)
            else "top_blocker_gate_ids="
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    written = write_phase3b_coordinate_validation_anchor119_row_domain_delivery_note(
        report,
        Path(args.output_dir),
    )
    print(
        "anchor119_row_domain_delivery_note_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_delivery_note_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_delivery_note_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


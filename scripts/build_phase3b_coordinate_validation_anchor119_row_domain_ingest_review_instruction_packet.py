from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet,
    write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain ingest-review instruction packet artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--operator-handoff-bundle", type=Path, default=None)
    parser.add_argument("--ingest-review-record-validator", type=Path, default=None)
    parser.add_argument("--ingest-review-record-example-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet(
            project_root,
            ingest_review_operator_handoff_bundle_path=args.operator_handoff_bundle,
            ingest_review_record_validator_path=args.ingest_review_record_validator,
            ingest_review_record_example_bundle_path=args.ingest_review_record_example_bundle,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        packet = report.get("ingest_review_instruction_packet", {})
        validator_reference = (
            packet.get("validator_reference", {}) if isinstance(packet, dict) else {}
        )
        example_reference = (
            packet.get("example_reference", {}) if isinstance(packet, dict) else {}
        )
        locked_handoff_path_shape = (
            packet.get("locked_handoff_path_shape", {})
            if isinstance(packet, dict)
            else {}
        )
        print("phase3b anchor119 row-domain ingest review instruction packet")
        print(
            "ingest_review_instruction_packet_ready="
            + str(bool(status.get("ingest_review_instruction_packet_ready", False)))
        )
        print(
            "upstream_handoff_bundle_ready="
            + str(bool(status.get("upstream_handoff_bundle_ready", False)))
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
        print("validator_artifact_path=" + str(validator_reference.get("artifact_path")))
        print("example_bundle_artifact_path=" + str(example_reference.get("artifact_path")))
        print("locked_handoff_path_shape=" + str(locked_handoff_path_shape.get("path_shape")))
        print(
            "still_blocked_gate_ids="
            + ",".join(report.get("still_blocked_gate_ids", []))
            if isinstance(report.get("still_blocked_gate_ids"), list)
            else "still_blocked_gate_ids="
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    written = write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet(
        report,
        output_dir,
    )
    print(
        "anchor119_row_domain_ingest_review_instruction_packet_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_instruction_packet_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_ingest_review_instruction_packet_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit import (
    build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit,
    write_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain package artifact consistency audit."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--manual-review-package-index", type=Path, default=None)
    parser.add_argument("--final-human-handoff-note", type=Path, default=None)
    parser.add_argument("--delivery-note", type=Path, default=None)
    parser.add_argument("--guarded-precheck-spec", type=Path, default=None)
    parser.add_argument("--startline-manifest", type=Path, default=None)
    parser.add_argument("--b5a-operator-summary", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
            project_root,
            manual_review_package_index_path=args.manual_review_package_index,
            final_human_handoff_note_path=args.final_human_handoff_note,
            delivery_note_path=args.delivery_note,
            guarded_precheck_spec_path=args.guarded_precheck_spec,
            startline_manifest_path=args.startline_manifest,
            b5a_operator_summary_path=args.b5a_operator_summary,
        )
    )

    status = report.get("status", {})
    audit_target = report.get("audit_target", {})
    summary = report.get("summary", {})

    if args.no_write:
        print("phase3b anchor119 row-domain package artifact consistency audit")
        print(
            "package_artifact_consistency_audit_ready="
            + str(bool(status.get("package_artifact_consistency_audit_ready", False)))
        )
        print(
            "all_consistency_checks_pass="
            + str(bool(status.get("all_consistency_checks_pass", False)))
        )
        print("candidate_key=" + str(audit_target.get("candidate_key")))
        print("anchor_idx=" + str(audit_target.get("anchor_idx")))
        print("formulation_profile=" + str(audit_target.get("formulation_profile")))
        print(
            "remaining_blocker_gate_ids="
            + ",".join(summary.get("remaining_blocker_gate_ids", []))
            if isinstance(summary.get("remaining_blocker_gate_ids"), list)
            else "remaining_blocker_gate_ids="
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_package_artifact_consistency_audit_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_package_artifact_consistency_audit_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_package_artifact_consistency_audit_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain acceptance execution gate artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--signoff-record-validator", type=Path, default=None)
    parser.add_argument("--runtime-patch-signoff-bundle", type=Path, default=None)
    parser.add_argument("--acceptance-refresh-prep", type=Path, default=None)
    parser.add_argument("--pre-run-acceptance-validation", type=Path, default=None)
    parser.add_argument("--acceptance-execution-staging", type=Path, default=None)
    parser.add_argument("--acceptance-result-validator", type=Path, default=None)
    parser.add_argument("--review-state", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
            project_root,
            signoff_record_validator_path=args.signoff_record_validator,
            signoff_bundle_path=args.runtime_patch_signoff_bundle,
            acceptance_refresh_prep_path=args.acceptance_refresh_prep,
            pre_run_acceptance_validation_path=args.pre_run_acceptance_validation,
            acceptance_execution_staging_path=args.acceptance_execution_staging,
            acceptance_result_validator_path=args.acceptance_result_validator,
            review_state_path=args.review_state,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        execution_gate = report.get("acceptance_execution_gate", {})
        locked_execution_target = execution_gate.get("locked_execution_target", {})
        print("phase3b anchor119 row-domain acceptance execution gate")
        print(
            "acceptance_execution_gate_ready="
            + str(bool(status.get("acceptance_execution_gate_ready", False)))
        )
        print(
            "acceptance_execution_authorization_prerequisites_met="
            + str(
                bool(
                    status.get(
                        "acceptance_execution_authorization_prerequisites_met", False
                    )
                )
            )
        )
        print(
            "acceptance_execution_authorized="
            + str(bool(status.get("acceptance_execution_authorized", False)))
        )
        print(
            "reviewed_runtime_patch_exists="
            + str(bool(status.get("reviewed_runtime_patch_exists", False)))
        )
        print("production_profile_id=" + str(execution_gate.get("production_profile_id")))
        print(
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path"))
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_execution_gate_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_execution_gate_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_execution_gate_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

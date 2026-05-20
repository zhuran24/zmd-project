from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B anchor119 row-domain acceptance-authorization review "
            "bundle artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--acceptance-execution-gate", type=Path, default=None)
    parser.add_argument("--acceptance-refresh-prep", type=Path, default=None)
    parser.add_argument("--acceptance-execution-staging", type=Path, default=None)
    parser.add_argument("--acceptance-result-validator", type=Path, default=None)
    parser.add_argument("--runtime-patch-signoff-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle(
            project_root,
            acceptance_execution_gate_path=args.acceptance_execution_gate,
            acceptance_refresh_prep_path=args.acceptance_refresh_prep,
            acceptance_execution_staging_path=args.acceptance_execution_staging,
            acceptance_result_validator_path=args.acceptance_result_validator,
            runtime_patch_signoff_bundle_path=args.runtime_patch_signoff_bundle,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        bundle = report.get("acceptance_authorization_review_bundle", {})
        locked_execution_target = bundle.get("locked_execution_target", {})
        print("phase3b anchor119 row-domain acceptance authorization review bundle")
        print(
            "acceptance_authorization_review_bundle_ready="
            + str(bool(status.get("acceptance_authorization_review_bundle_ready", False)))
        )
        print(
            "future_execution_authorization_review_prerequisites_met="
            + str(
                bool(
                    status.get(
                        "future_execution_authorization_review_prerequisites_met",
                        False,
                    )
                )
            )
        )
        print(
            "acceptance_execution_authorized="
            + str(bool(status.get("acceptance_execution_authorized", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(status.get("runtime_enablement_allowed", False)))
        )
        print("acceptance_executed=" + str(bool(status.get("acceptance_executed", False))))
        print(
            "reviewed_runtime_patch_exists="
            + str(bool(status.get("reviewed_runtime_patch_exists", False)))
        )
        print("production_profile_id=" + str(bundle.get("production_profile_id")))
        print(
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path"))
        )
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_bundle_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_bundle_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_authorization_review_bundle_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

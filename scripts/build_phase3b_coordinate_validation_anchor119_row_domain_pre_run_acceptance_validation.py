from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation import (
    build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation,
    write_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain pre-run acceptance validation artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--acceptance-refresh-prep", type=Path, default=None)
    parser.add_argument("--signoff-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation(
        project_root,
        acceptance_refresh_prep_path=args.acceptance_refresh_prep,
        signoff_bundle_path=args.signoff_bundle,
    )

    if args.no_write:
        prep = report.get("pre_run_acceptance_validation", {})
        status = report.get("status", {})
        print("phase3b anchor119 row-domain pre-run acceptance validation")
        print(
            "acceptance_validation_ready_for_review="
            + str(bool(status.get("acceptance_validation_ready_for_review", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(status.get("runtime_enablement_allowed", False)))
        )
        print(
            "exact_future_acceptance_json_path="
            + str(prep.get("exact_future_acceptance_json_path"))
        )
        print("recommended_next_step=" + str(status.get("recommended_next_step")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_pre_run_acceptance_validation_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_pre_run_acceptance_validation_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_pre_run_acceptance_validation_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

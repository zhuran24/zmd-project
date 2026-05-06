from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain acceptance execution staging artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--pre-run-acceptance-validation", type=Path, default=None)
    parser.add_argument("--acceptance-refresh-prep", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging(
            project_root,
            pre_run_acceptance_validation_path=args.pre_run_acceptance_validation,
            acceptance_refresh_prep_path=args.acceptance_refresh_prep,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        staging = report.get("acceptance_execution_staging", {})
        print("phase3b anchor119 row-domain acceptance execution staging")
        print(
            "acceptance_execution_staging_ready="
            + str(bool(status.get("acceptance_execution_staging_ready", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(status.get("runtime_enablement_allowed", False)))
        )
        print("exact_command_to_run_later=" + str(staging.get("exact_command_to_run_later")))
        print("exact_future_output_path=" + str(staging.get("exact_future_output_path")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_execution_staging_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_execution_staging_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_execution_staging_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

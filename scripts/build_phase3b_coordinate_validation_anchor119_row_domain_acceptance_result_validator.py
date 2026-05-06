from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator,
    write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain acceptance result validator artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--acceptance-execution-staging", type=Path, default=None)
    parser.add_argument("--pre-run-acceptance-validation", type=Path, default=None)
    parser.add_argument("--acceptance-result", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
            project_root,
            acceptance_execution_staging_path=args.acceptance_execution_staging,
            pre_run_acceptance_validation_path=args.pre_run_acceptance_validation,
            acceptance_result_path=args.acceptance_result,
        )
    )

    if args.no_write:
        status = report.get("status", {})
        validator = report.get("acceptance_result_validator", {})
        print("phase3b anchor119 row-domain acceptance result validator")
        print(
            "acceptance_result_validator_ready="
            + str(bool(status.get("acceptance_result_validator_ready", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(status.get("runtime_enablement_allowed", False)))
        )
        print(
            "acceptance_result_validation_performed="
            + str(bool(status.get("acceptance_result_validation_performed", False)))
        )
        print("expected_result_path=" + str(validator.get("expected_result_path")))
        return 0

    written = (
        write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
            report,
            Path(args.output_dir),
        )
    )
    print(
        "anchor119_row_domain_acceptance_result_validator_json="
        + str(Path(written["json"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_result_validator_md="
        + str(Path(written["md"]).resolve())
    )
    print(
        "anchor119_row_domain_acceptance_result_validator_txt="
        + str(Path(written["txt"]).resolve())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold import (
    build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold,
    write_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain signoff record scaffold artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--reviewer-record-prep", type=Path, default=None)
    parser.add_argument("--signoff-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold(
        project_root,
        reviewer_record_prep_path=args.reviewer_record_prep,
        signoff_bundle_path=args.signoff_bundle,
    )

    if args.no_write:
        print("phase3b anchor119 row-domain signoff record scaffold")
        print(
            "signoff_record_scaffold_ready="
            + str(bool(report.get("status", {}).get("signoff_record_scaffold_ready", False)))
        )
        print(
            "reviewed_runtime_patch_exists="
            + str(bool(report.get("status", {}).get("reviewed_runtime_patch_exists", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(report.get("status", {}).get("runtime_enablement_allowed", False)))
        )
        print(
            "recommended_next_step="
            + str(report.get("status", {}).get("recommended_next_step"))
        )
        return 0

    written = write_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold(
        report, output_dir
    )
    print(f"anchor119_row_domain_signoff_record_scaffold_json={Path(written['json']).resolve()}")
    print(f"anchor119_row_domain_signoff_record_scaffold_md={Path(written['md']).resolve()}")
    print(f"anchor119_row_domain_signoff_record_scaffold_txt={Path(written['txt']).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

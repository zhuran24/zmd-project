from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_refresh_prep import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain acceptance refresh prep artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--signoff-bundle", type=Path, default=None)
    parser.add_argument("--enablement-gate-prep", type=Path, default=None)
    parser.add_argument("--review-state", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep(
        project_root,
        signoff_bundle_path=args.signoff_bundle,
        enablement_gate_prep_path=args.enablement_gate_prep,
        review_state_path=args.review_state,
    )

    if args.no_write:
        print("phase3b anchor119 row-domain acceptance refresh prep")
        print(
            "acceptance_refresh_prep_ready="
            + str(bool(report.get("status", {}).get("acceptance_refresh_prep_ready", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(report.get("status", {}).get("runtime_enablement_allowed", False)))
        )
        print(
            "reviewed_runtime_patch_exists="
            + str(
                bool(
                    report.get("status", {}).get(
                        "reviewed_runtime_patch_exists", False
                    )
                )
            )
        )
        print(
            "recommended_next_step="
            + str(report.get("status", {}).get("recommended_next_step"))
        )
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_acceptance_refresh_prep.json"
    md_path = output_dir / "anchor119_row_domain_acceptance_refresh_prep.md"
    txt_path = output_dir / "anchor119_row_domain_acceptance_refresh_prep.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"anchor119_row_domain_acceptance_refresh_prep_json={json_path.resolve()}")
    print(f"anchor119_row_domain_acceptance_refresh_prep_md={md_path.resolve()}")
    print(f"anchor119_row_domain_acceptance_refresh_prep_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

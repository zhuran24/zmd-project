from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.runtime_patch_proposal import (
    build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain runtime patch proposal artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--control-surface", type=Path, default=None)
    parser.add_argument("--patch-review-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal(
        project_root,
        control_surface_path=args.control_surface,
        patch_review_bundle_path=args.patch_review_bundle,
    )

    if args.no_write:
        print("phase3b anchor119 row-domain runtime patch proposal")
        print(
            "proposal_ready_for_review="
            + str(bool(report.get("status", {}).get("proposal_ready_for_review", False)))
        )
        print(
            "runtime_enablement_allowed="
            + str(bool(report.get("status", {}).get("runtime_enablement_allowed", False)))
        )
        print("recommended_next_step=" + str(report.get("status", {}).get("recommended_next_step")))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_runtime_patch_proposal.json"
    md_path = output_dir / "anchor119_row_domain_runtime_patch_proposal.md"
    txt_path = output_dir / "anchor119_row_domain_runtime_patch_proposal.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"anchor119_row_domain_runtime_patch_proposal_json={json_path.resolve()}")
    print(f"anchor119_row_domain_runtime_patch_proposal_md={md_path.resolve()}")
    print(f"anchor119_row_domain_runtime_patch_proposal_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

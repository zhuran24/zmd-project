from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.guard_patch_review_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain guard patch review bundle."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--guard-spec", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle(
        project_root,
        guard_spec_path=args.guard_spec,
    )

    if args.no_write:
        print("phase3b anchor119 row-domain guard patch review bundle")
        print(
            f"bundle_ready_for_review={bool(report.get('status', {}).get('bundle_ready_for_review', False))}"
        )
        print("recommended_next_step=" + str(report.get("status", {}).get("recommended_next_step")))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_guard_patch_review_bundle.json"
    md_path = output_dir / "anchor119_row_domain_guard_patch_review_bundle.md"
    txt_path = output_dir / "anchor119_row_domain_guard_patch_review_bundle.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"anchor119_row_domain_guard_patch_review_bundle_json={json_path.resolve()}")
    print(f"anchor119_row_domain_guard_patch_review_bundle_md={md_path.resolve()}")
    print(f"anchor119_row_domain_guard_patch_review_bundle_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

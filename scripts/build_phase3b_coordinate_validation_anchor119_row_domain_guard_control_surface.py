from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface import (
    build_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain guard control surface artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--patch-review-bundle", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface(
        project_root,
        patch_review_bundle_path=args.patch_review_bundle,
    )

    if args.no_write:
        print("phase3b anchor119 row-domain guard control surface")
        print(
            "control_surface_ready="
            + str(bool(report.get("status", {}).get("control_surface_ready", False)))
        )
        print(
            "runtime_activation_allowed="
            + str(bool(report.get("status", {}).get("runtime_activation_allowed", False)))
        )
        print("recommended_next_step=" + str(report.get("status", {}).get("recommended_next_step")))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_guard_control_surface.json"
    md_path = output_dir / "anchor119_row_domain_guard_control_surface.md"
    txt_path = output_dir / "anchor119_row_domain_guard_control_surface.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"anchor119_row_domain_guard_control_surface_json={json_path.resolve()}")
    print(f"anchor119_row_domain_guard_control_surface_md={md_path.resolve()}")
    print(f"anchor119_row_domain_guard_control_surface_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

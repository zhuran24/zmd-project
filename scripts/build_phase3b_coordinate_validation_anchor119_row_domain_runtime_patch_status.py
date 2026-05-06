from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status import (
    build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B anchor119 row-domain runtime patch status artifact."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--control-surface", type=Path, default=None)
    parser.add_argument("--runtime-patch-proposal", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_20260424"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status(
        project_root,
        control_surface_path=args.control_surface,
        runtime_patch_proposal_path=args.runtime_patch_proposal,
    )

    if args.no_write:
        print("phase3b anchor119 row-domain runtime patch status")
        print(
            "patch_status_ready="
            + str(bool(report.get("status", {}).get("patch_status_ready", False)))
        )
        print(
            "runtime_patch_authored_in_code="
            + str(
                bool(
                    report.get("status", {}).get("runtime_patch_authored_in_code", False)
                )
            )
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

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_runtime_patch_status.json"
    md_path = output_dir / "anchor119_row_domain_runtime_patch_status.md"
    txt_path = output_dir / "anchor119_row_domain_runtime_patch_status.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"anchor119_row_domain_runtime_patch_status_json={json_path.resolve()}")
    print(f"anchor119_row_domain_runtime_patch_status_md={md_path.resolve()}")
    print(f"anchor119_row_domain_runtime_patch_status_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

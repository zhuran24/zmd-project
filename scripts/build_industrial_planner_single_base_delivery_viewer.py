"""Build a static browser viewer bundle from the active IndustrialPlanner single-base delivery release."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.industrial_planner_single_base_delivery_viewer import (  # noqa: E402
    _DEFAULT_CANDIDATE_PLACEMENTS_JSON,
    _DEFAULT_OUTPUT_DIR,
    _DEFAULT_POINTER_JSON,
    _DEFAULT_RULES_JSON,
    _DEFAULT_VIEWER_HTML,
    SingleBaseDeliveryViewerBundleError,
    build_single_base_delivery_viewer_bundle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the checked-in active IndustrialPlanner single-base delivery release pointer and "
            "materialize a static viewer bundle with release/download metadata."
        )
    )
    parser.add_argument(
        "--pointer-json",
        type=Path,
        default=_DEFAULT_POINTER_JSON,
        help="Checked-in current-release pointer JSON. Defaults to the active single-base pointer.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Where to write the static viewer bundle. Defaults to .artifacts/industrial_planner_single_base_delivery_viewer.",
    )
    parser.add_argument(
        "--candidate-placements",
        type=Path,
        default=_DEFAULT_CANDIDATE_PLACEMENTS_JSON,
        help="Candidate-placements JSON used to recover the selected release poses for visualization.",
    )
    parser.add_argument(
        "--rules-json",
        type=Path,
        default=_DEFAULT_RULES_JSON,
        help="Rules JSON used when building the viewer-side report cards.",
    )
    parser.add_argument(
        "--viewer-html",
        type=Path,
        default=_DEFAULT_VIEWER_HTML,
        help="Static viewer HTML template to copy into the output bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = build_single_base_delivery_viewer_bundle(
            project_root=PROJECT_ROOT,
            pointer_json_path=args.pointer_json,
            output_dir=args.output_dir,
            candidate_placements_path=args.candidate_placements,
            rules_json_path=args.rules_json,
            viewer_html_path=args.viewer_html,
        )
    except SingleBaseDeliveryViewerBundleError as exc:
        print(f"[industrial_planner_single_base_delivery_viewer] error: {exc}", file=sys.stderr)
        return 1

    print("IndustrialPlanner single-base delivery viewer bundle built successfully.")
    print(f"- release id: {result.release_id}")
    print(f"- base id: {result.base_id}")
    print(f"- lot size: {result.lot_size}")
    print(f"- delivery status: {result.delivery_status}")
    print(f"- output dir: {result.output_dir}")
    print(f"- viewer manifest: {result.viewer_manifest_path}")
    print(f"- selected facility types: {result.selected_facility_type_count}")
    print(f"- selected poses: {result.selected_pose_count}")
    print(f"- payload downloads: {result.payload_download_count}")
    print(f"- metadata downloads: {result.metadata_download_count}")
    print(f"- quick downloads: {result.quick_download_count}")
    print(f"- full-scale exact CERTIFIED status: {result.exact_full_scale_certified_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

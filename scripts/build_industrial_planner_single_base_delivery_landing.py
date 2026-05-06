"""Build a stable current landing/download bundle from the active IndustrialPlanner single-base viewer pointer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.industrial_planner_single_base_delivery_landing import (  # noqa: E402
    _DEFAULT_OUTPUT_DIR,
    _DEFAULT_VIEWER_POINTER_JSON,
    SingleBaseDeliveryLandingBundleError,
    build_single_base_delivery_landing_bundle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the checked-in active IndustrialPlanner single-base current-viewer pointer and "
            "materialize one stable landing/download page with a copied viewer bundle under viewer/."
        )
    )
    parser.add_argument(
        "--viewer-pointer-json",
        type=Path,
        default=_DEFAULT_VIEWER_POINTER_JSON,
        help="Checked-in current-viewer pointer JSON. Defaults to the active single-base viewer pointer.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=(
            "Where to write the stable landing bundle. Defaults to "
            ".artifacts/industrial_planner_single_base_delivery_landing."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = build_single_base_delivery_landing_bundle(
            project_root=PROJECT_ROOT,
            viewer_pointer_json_path=args.viewer_pointer_json,
            output_dir=args.output_dir,
        )
    except SingleBaseDeliveryLandingBundleError as exc:
        print(f"[industrial_planner_single_base_delivery_landing] error: {exc}", file=sys.stderr)
        return 1

    print("IndustrialPlanner single-base delivery landing bundle built successfully.")
    print(f"- release id: {result.release_id}")
    print(f"- base id: {result.base_id}")
    print(f"- lot size: {result.lot_size}")
    print(f"- delivery status: {result.delivery_status}")
    print(f"- output dir: {result.output_dir}")
    print(f"- landing manifest: {result.landing_manifest_path}")
    print(f"- landing index: {result.landing_index_html_path}")
    print(f"- materialized viewer dir: {result.materialized_viewer_dir}")
    print(f"- current bundle ZIP: {result.current_bundle_zip_path}")
    print(f"- current bundle pointer JSON: {result.current_bundle_pointer_json_path}")
    print(f"- current bundle pointer Markdown: {result.current_bundle_pointer_markdown_path}")
    print(
        "- current bundle contents: "
        f"{result.current_bundle_payload_file_count} payload / "
        f"{result.current_bundle_metadata_file_count} metadata"
    )
    print(f"- quick downloads: {result.quick_download_count}")
    print(f"- grouped download sections: {result.download_group_count}")
    print(f"- full-scale exact CERTIFIED status: {result.exact_full_scale_certified_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

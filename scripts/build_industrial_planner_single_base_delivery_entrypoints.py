"""CLI for the active IndustrialPlanner single-base aggregated entrypoints manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.industrial_planner_single_base_delivery_entrypoints import (  # noqa: E402
    SingleBaseDeliveryEntrypointsError,
    build_single_base_delivery_entrypoints,
)

_DEFAULT_RELEASE_POINTER_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_release.json"
_DEFAULT_VIEWER_POINTER_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_viewer.json"
_DEFAULT_LANDING_MANIFEST_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_delivery" / "landing_manifest.json"
_DEFAULT_FRONTDOOR_MANIFEST_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "frontdoor_manifest.json"
_DEFAULT_LATEST_BUNDLE_POINTER_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "latest_single_base_delivery_bundle.json"
_DEFAULT_SURFACE_ALIGNMENT_JSON = (
    PROJECT_ROOT
    / ".artifacts"
    / "industrial_planner_single_base_delivery_surface_alignment"
    / "surface_alignment_summary.json"
)
_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN = (
    PROJECT_ROOT
    / ".artifacts"
    / "industrial_planner_single_base_delivery_surface_alignment"
    / "surface_alignment_summary.md"
)
_DEFAULT_SURFACE_ALIGNMENT_CONSOLE = (
    PROJECT_ROOT
    / ".artifacts"
    / "industrial_planner_single_base_delivery_surface_alignment"
    / "surface_alignment_summary.txt"
)
_DEFAULT_SURFACE_HEALTH_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_surface_health.json"
_DEFAULT_SURFACE_HEALTH_MARKDOWN = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_surface_health.md"
_DEFAULT_SURFACE_HEALTH_CONSOLE = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_surface_health.txt"
_DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_entrypoints.json"
_DEFAULT_OUTPUT_MARKDOWN = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_entrypoints.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one checked-in aggregate manifest that summarizes the current release pointer, "
            "viewer pointer, stable landing bundle, and top-level latest bundle alias for the active "
            "IndustrialPlanner single-base contract."
        )
    )
    parser.add_argument("--release-pointer-json", default=str(_DEFAULT_RELEASE_POINTER_JSON))
    parser.add_argument("--viewer-pointer-json", default=str(_DEFAULT_VIEWER_POINTER_JSON))
    parser.add_argument("--landing-manifest-json", default=str(_DEFAULT_LANDING_MANIFEST_JSON))
    parser.add_argument("--frontdoor-manifest-json", default=str(_DEFAULT_FRONTDOOR_MANIFEST_JSON))
    parser.add_argument("--latest-bundle-pointer-json", default=str(_DEFAULT_LATEST_BUNDLE_POINTER_JSON))
    parser.add_argument("--surface-alignment-json", default=str(_DEFAULT_SURFACE_ALIGNMENT_JSON))
    parser.add_argument("--surface-alignment-markdown", default=str(_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN))
    parser.add_argument("--surface-alignment-console", default=str(_DEFAULT_SURFACE_ALIGNMENT_CONSOLE))
    parser.add_argument(
        "--require-surface-alignment",
        action="store_true",
        help="Fail closed unless the surface-alignment JSON/Markdown/TXT summaries all exist.",
    )
    parser.add_argument("--surface-health-json", default=str(_DEFAULT_SURFACE_HEALTH_JSON))
    parser.add_argument("--surface-health-markdown", default=str(_DEFAULT_SURFACE_HEALTH_MARKDOWN))
    parser.add_argument("--surface-health-console", default=str(_DEFAULT_SURFACE_HEALTH_CONSOLE))
    parser.add_argument(
        "--require-surface-health",
        action="store_true",
        help="Fail closed unless the current-surface-health JSON/Markdown/TXT snapshots all exist.",
    )
    parser.add_argument("--output-json", default=str(_DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-markdown", default=str(_DEFAULT_OUTPUT_MARKDOWN))
    args = parser.parse_args()

    try:
        result = build_single_base_delivery_entrypoints(
            project_root=PROJECT_ROOT,
            release_pointer_json_path=Path(args.release_pointer_json),
            viewer_pointer_json_path=Path(args.viewer_pointer_json),
            landing_manifest_json_path=Path(args.landing_manifest_json),
            frontdoor_manifest_json_path=Path(args.frontdoor_manifest_json),
            latest_bundle_pointer_json_path=Path(args.latest_bundle_pointer_json),
            surface_alignment_json_path=Path(args.surface_alignment_json),
            surface_alignment_markdown_path=Path(args.surface_alignment_markdown),
            surface_alignment_console_path=Path(args.surface_alignment_console),
            require_surface_alignment=bool(args.require_surface_alignment),
            surface_health_json_path=Path(args.surface_health_json),
            surface_health_markdown_path=Path(args.surface_health_markdown),
            surface_health_console_path=Path(args.surface_health_console),
            require_surface_health=bool(args.require_surface_health),
            output_json_path=Path(args.output_json),
            output_markdown_path=Path(args.output_markdown),
        )
    except SingleBaseDeliveryEntrypointsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("IndustrialPlanner active single-base entrypoints manifest built successfully.")
    print(f"- release id: {result.release_id}")
    print(f"- base id: {result.base_id}")
    print(f"- lot size: {result.lot_size}")
    print(f"- delivery status: {result.delivery_status}")
    print(f"- output JSON: {result.output_json_path}")
    print(f"- output Markdown: {result.output_markdown_path}")
    print(f"- grouped entrypoints: {result.entrypoint_group_count}")
    print(f"- actions: {result.action_count}")
    print(f"- exact full-scale CERTIFIED status: {result.exact_full_scale_certified_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

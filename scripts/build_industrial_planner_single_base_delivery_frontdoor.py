"""CLI for the checked-in IndustrialPlanner single-base repo front door.

The generated repo-front page exposes explicit browse-first and download-first
entry modes above the stable current-delivery bundle.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.industrial_planner_single_base_delivery_frontdoor import (  # noqa: E402
    SingleBaseDeliveryFrontdoorError,
    build_single_base_delivery_frontdoor,
)

_DEFAULT_LANDING_MANIFEST_JSON = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_delivery" / "landing_manifest.json"
_DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "examples" / "industrial_planner"
_DEFAULT_ENTRYPOINTS_JSON = _DEFAULT_OUTPUT_DIR / "active_single_base_delivery_entrypoints.json"
_DEFAULT_ENTRYPOINTS_MARKDOWN = _DEFAULT_OUTPUT_DIR / "active_single_base_delivery_entrypoints.md"
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the checked-in repo-front IndustrialPlanner single-base entry page one level above the "
            "stable current_delivery/ landing bundle, with explicit browse-first/download-first paths."
        )
    )
    parser.add_argument(
        "--landing-manifest-json",
        default=str(_DEFAULT_LANDING_MANIFEST_JSON),
        help="Landing manifest that should be surfaced by the repo-front entry page.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help="Directory where index.html and frontdoor_manifest.json should be written.",
    )
    parser.add_argument(
        "--entrypoints-json",
        default=str(_DEFAULT_ENTRYPOINTS_JSON),
        help="Aggregate current-entrypoints JSON to surface in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--entrypoints-markdown",
        default=str(_DEFAULT_ENTRYPOINTS_MARKDOWN),
        help="Aggregate current-entrypoints Markdown to surface in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--require-entrypoints",
        action="store_true",
        help="Fail closed unless the aggregate current-entrypoints JSON and Markdown both exist.",
    )
    parser.add_argument(
        "--surface-alignment-json",
        default=str(_DEFAULT_SURFACE_ALIGNMENT_JSON),
        help="Surface-alignment audit JSON summary to expose in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--surface-alignment-markdown",
        default=str(_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN),
        help="Surface-alignment audit Markdown summary to expose in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--surface-alignment-console",
        default=str(_DEFAULT_SURFACE_ALIGNMENT_CONSOLE),
        help="Surface-alignment audit TXT console summary to expose in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--require-surface-alignment",
        action="store_true",
        help="Fail closed unless the surface-alignment JSON/Markdown/TXT summaries all exist.",
    )
    parser.add_argument(
        "--surface-health-json",
        default=str(_DEFAULT_SURFACE_HEALTH_JSON),
        help="Current surface-health JSON snapshot to expose in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--surface-health-markdown",
        default=str(_DEFAULT_SURFACE_HEALTH_MARKDOWN),
        help="Current surface-health Markdown snapshot to expose in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--surface-health-console",
        default=str(_DEFAULT_SURFACE_HEALTH_CONSOLE),
        help="Current surface-health TXT snapshot to expose in the repo-front helper links when present.",
    )
    parser.add_argument(
        "--require-surface-health",
        action="store_true",
        help="Fail closed unless the surface-health JSON/Markdown/TXT snapshots all exist.",
    )
    args = parser.parse_args()

    try:
        result = build_single_base_delivery_frontdoor(
            project_root=PROJECT_ROOT,
            landing_manifest_json_path=Path(args.landing_manifest_json),
            output_dir=Path(args.output_dir),
            entrypoints_json_path=Path(args.entrypoints_json),
            entrypoints_markdown_path=Path(args.entrypoints_markdown),
            require_entrypoints=bool(args.require_entrypoints),
            surface_alignment_json_path=Path(args.surface_alignment_json),
            surface_alignment_markdown_path=Path(args.surface_alignment_markdown),
            surface_alignment_console_path=Path(args.surface_alignment_console),
            require_surface_alignment=bool(args.require_surface_alignment),
            surface_health_json_path=Path(args.surface_health_json),
            surface_health_markdown_path=Path(args.surface_health_markdown),
            surface_health_console_path=Path(args.surface_health_console),
            require_surface_health=bool(args.require_surface_health),
        )
    except SingleBaseDeliveryFrontdoorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("IndustrialPlanner single-base repo front door built successfully.")
    print(f"- release id: {result.release_id}")
    print(f"- base id: {result.base_id}")
    print(f"- delivery status: {result.delivery_status}")
    print(f"- output dir: {result.output_dir}")
    print(f"- frontdoor HTML: {result.frontdoor_index_html_path}")
    print(f"- frontdoor manifest: {result.frontdoor_manifest_path}")
    print(f"- current delivery page: {result.current_delivery_index_html}")
    print(f"- latest bundle ZIP alias: {result.latest_bundle_zip_path}")
    print(f"- latest bundle pointer JSON: {result.latest_bundle_pointer_json_path}")
    print(
        "- downloads: "
        f"{result.quick_download_count} quick / {result.download_group_count} grouped sections"
    )
    print(f"- exact full-scale CERTIFIED status: {result.exact_full_scale_certified_status}")
    if result.surface_alignment_status:
        print(
            "- surface alignment: "
            f"{result.surface_alignment_status}"
            + (
                f" ({result.surface_alignment_check_count} checks / {result.surface_alignment_drift_check_count} drift)"
                if result.surface_alignment_check_count is not None
                and result.surface_alignment_drift_check_count is not None
                else ""
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

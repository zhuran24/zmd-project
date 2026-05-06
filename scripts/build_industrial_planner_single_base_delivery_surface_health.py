"""Build a compact current-surface health artifact for the active IndustrialPlanner line."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.industrial_planner_single_base_delivery_surface_health import (  # noqa: E402
    SingleBaseDeliverySurfaceHealthError,
    build_single_base_delivery_surface_health,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a compact current_surface_health.{json,md,txt} snapshot from the checked-in "
            "single-base consumer-surface alignment audit."
        )
    )
    parser.add_argument(
        "--surface-alignment-json",
        default=".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json",
        help="Machine-readable source audit summary.",
    )
    parser.add_argument(
        "--surface-alignment-markdown",
        default=".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md",
        help="Human-readable source audit summary.",
    )
    parser.add_argument(
        "--surface-alignment-console",
        default=".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt",
        help="Plain-text source audit summary.",
    )
    parser.add_argument(
        "--output-json",
        default="data/examples/industrial_planner/current_surface_health.json",
        help="Output JSON path for the compact current-surface health snapshot.",
    )
    parser.add_argument(
        "--output-markdown",
        default="data/examples/industrial_planner/current_surface_health.md",
        help="Output Markdown path for the compact current-surface health snapshot.",
    )
    parser.add_argument(
        "--output-console",
        default="data/examples/industrial_planner/current_surface_health.txt",
        help="Output console/TXT path for the compact current-surface health snapshot.",
    )
    args = parser.parse_args()

    try:
        result = build_single_base_delivery_surface_health(
            project_root=PROJECT_ROOT,
            surface_alignment_json_path=Path(args.surface_alignment_json),
            surface_alignment_markdown_path=Path(args.surface_alignment_markdown),
            surface_alignment_console_path=Path(args.surface_alignment_console),
            output_json_path=Path(args.output_json),
            output_markdown_path=Path(args.output_markdown),
            output_console_path=Path(args.output_console),
        )
    except SingleBaseDeliverySurfaceHealthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result.to_console_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

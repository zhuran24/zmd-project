"""Validate an IndustrialPlanner blueprint export with the offline Python validator."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.industrial_planner.blueprint_validator import (  # noqa: E402
    validate_industrial_planner_blueprint_file,
    write_validation_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an IndustrialPlanner blueprint JSON without Node.js or browser runtime dependencies."
    )
    parser.add_argument(
        "blueprint_path",
        help="Path to industrial_planner.blueprint.json or another IndustrialPlanner blueprint payload.",
    )
    parser.add_argument(
        "--report-output",
        default=None,
        help="Optional JSON output path for the structured validation report.",
    )
    parser.add_argument(
        "--report-markdown",
        default=None,
        help="Optional Markdown output path for the human-readable validation report.",
    )
    args = parser.parse_args()

    blueprint_path = Path(args.blueprint_path)
    report = validate_industrial_planner_blueprint_file(blueprint_path)
    write_validation_reports(
        report,
        json_output_path=Path(args.report_output) if args.report_output else None,
        markdown_output_path=Path(args.report_markdown) if args.report_markdown else None,
    )

    print(f"import compatible: {report.is_import_compatible}")
    print(f"layout healthy: {report.is_layout_healthy}")
    print(f"clean export: {report.is_clean}")
    print(f"schema errors: {len(report.schema_errors)}")
    print(f"registry errors: {len(report.registry_errors)}")
    print(f"lot boundary errors: {len(report.lot_boundary_errors)}")
    print(f"placement constraint errors: {len(report.placement_constraint_errors)}")
    print(f"unsupported rule errors: {len(report.unsupported_rule_errors)}")
    print(f"overlap errors: {len(report.overlap_errors)}")
    print(f"port mismatch errors: {len(report.port_mismatch_errors)}")
    print(f"port warnings: {len(report.port_warnings)}")

    if report.is_import_compatible and report.is_layout_healthy:
        return 0
    if not report.is_import_compatible:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

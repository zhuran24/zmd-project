"""Run the IndustrialPlanner static recipe/capacity audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.industrial_planner import build_industrial_planner_export_bundle
from src.io.serializer import load_canonical_blueprint
from src.search.exact_campaign import atomic_write_json

_EXIT_CODE_BY_STATUS = {
    "proven_equivalent": 0,
    "partially_proven": 2,
    "unproven_or_insufficient": 3,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the IndustrialPlanner static recipe/capacity conformance audit sidecars "
            "for a canonical blueprint."
        )
    )
    parser.add_argument(
        "blueprint_path",
        help="Path to the canonical blueprint payload.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional JSON output path for throughput_report.json.",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional Markdown output path for throughput_report.md.",
    )
    args = parser.parse_args()

    try:
        blueprint_payload = load_canonical_blueprint(Path(args.blueprint_path))
        bundle = build_industrial_planner_export_bundle(blueprint_payload=blueprint_payload)
        throughput_report = dict(bundle["throughput_report"])
        throughput_report_markdown = str(bundle["throughput_report_markdown"])

        if args.json_output:
            atomic_write_json(Path(args.json_output), throughput_report)
        if args.markdown_output:
            markdown_path = Path(args.markdown_output)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(throughput_report_markdown, encoding="utf-8")

        print(f"overall status: {throughput_report['status']}")
        summary = throughput_report.get("summary", {}) if isinstance(throughput_report.get("summary"), dict) else {}
        print(
            "recipe summary: "
            f"required={summary.get('required_recipe_count', 0)}, "
            f"exact_matches={summary.get('exact_match_recipe_count', 0)}, "
            f"proven={summary.get('proven_recipe_count', 0)}, "
            f"partial={summary.get('partial_recipe_count', 0)}, "
            f"insufficient={summary.get('insufficient_recipe_count', 0)}"
        )
        print(
            "boundary summary: "
            f"required={summary.get('required_boundary_commodity_count', 0)}, "
            f"proven={summary.get('proven_boundary_commodity_count', 0)}, "
            f"partial={summary.get('partial_boundary_commodity_count', 0)}, "
            f"insufficient={summary.get('insufficient_boundary_commodity_count', 0)}"
        )
        validation = throughput_report.get("validation_diagnostics", {}) if isinstance(throughput_report.get("validation_diagnostics"), dict) else {}
        print(
            "validator diagnostics: "
            f"import_compatible={bool(validation.get('is_import_compatible', False))}, "
            f"layout_healthy={bool(validation.get('is_layout_healthy', False))}"
        )
        if args.json_output:
            print(f"throughput json written: {Path(args.json_output)}")
        if args.markdown_output:
            print(f"throughput markdown written: {Path(args.markdown_output)}")
        return _EXIT_CODE_BY_STATUS.get(str(throughput_report.get("status", "")), 1)
    except Exception as exc:  # pragma: no cover - CLI guard.
        print(f"throughput audit failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Export the canonical blueprint into an IndustrialPlanner bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.industrial_planner import DEFAULT_BASE_ID, write_industrial_planner_export_bundle
from src.io.serializer import load_canonical_blueprint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export data/blueprints/optimal_blueprint.json into an IndustrialPlanner-compatible bundle."
    )
    parser.add_argument(
        "blueprint_path",
        nargs="?",
        default="data/blueprints/optimal_blueprint.json",
        help="Path to the canonical optimal_blueprint.json artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/exports/industrial_planner",
        help=(
            "Directory where industrial_planner.blueprint.json, the compatibility manifest, "
            "validation reports, and throughput audit sidecars should be written."
        ),
    )
    parser.add_argument(
        "--base-id",
        default=DEFAULT_BASE_ID,
        help="IndustrialPlanner baseId to encode at the blueprint root.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional display name for the exported target blueprint.",
    )
    parser.add_argument(
        "--deployment-plan",
        default=None,
        help=(
            "Optional path to an adapter-side outer deployment plan JSON. "
            "When provided, the exporter materializes an outer-deployment target export "
            "(translated larger-base or degenerate identity) without widening the canonical blueprint schema."
        ),
    )
    args = parser.parse_args()

    blueprint_payload = load_canonical_blueprint(Path(args.blueprint_path))
    deployment_plan = (
        json.loads(Path(args.deployment_plan).read_text(encoding="utf-8"))
        if args.deployment_plan
        else None
    )
    written = write_industrial_planner_export_bundle(
        output_dir=Path(args.output_dir),
        blueprint_payload=blueprint_payload,
        export_name=args.name,
        base_id=str(args.base_id),
        deployment_plan=deployment_plan,
    )
    print(f"industrial blueprint written: {written.blueprint_path}")
    print(f"compatibility manifest written: {written.compatibility_manifest_path}")
    print(f"validation report written: {written.validation_report_path}")
    print(f"validation markdown written: {written.validation_report_markdown_path}")
    print(f"throughput report written: {written.throughput_report_path}")
    print(f"throughput markdown written: {written.throughput_report_markdown_path}")
    if written.warnings:
        print("warnings:")
        for warning in written.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()

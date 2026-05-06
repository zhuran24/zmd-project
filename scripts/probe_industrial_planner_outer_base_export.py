"""Probe an outer deployment plan against the real IndustrialPlanner validator."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.base_planner.outer_deployment_plan import build_outer_base_deployment_plan
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle
from src.adapters.industrial_planner.outer_export_probe import probe_outer_deployment_plan
from src.search.exact_campaign import atomic_write_json

_DEFAULT_BLUEPRINT = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "full_demand_recipe_capacity_canonical_blueprint.json"
)
_DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "generated_outer_base_bundle"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an outer deployment plan and probe it with the real IndustrialPlanner validator."
    )
    parser.add_argument(
        "blueprint",
        nargs="?",
        default=str(_DEFAULT_BLUEPRINT),
        help="Canonical blueprint JSON used as the inner-island truth.",
    )
    parser.add_argument(
        "--base-id",
        default="wuling_protocol_core",
        help="IndustrialPlanner base id to deploy into. Defaults to 'wuling_protocol_core'.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help="Directory for the probe bundle outputs.",
    )
    args = parser.parse_args()

    blueprint_payload = json.loads(Path(args.blueprint).read_text(encoding="utf-8"))
    plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint_payload,
        base_id=str(args.base_id),
    )
    bundle = probe_outer_deployment_plan(
        blueprint_payload=blueprint_payload,
        deployment_plan=plan,
    )
    export_bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint_payload,
        deployment_plan=plan,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "outer_deployment_plan.json", bundle.deployment_plan.to_dict())
    (output_dir / "outer_deployment_plan.md").write_text(bundle.deployment_plan.to_markdown(), encoding="utf-8")
    atomic_write_json(output_dir / "outer_export_probe.json", bundle.to_dict())
    (output_dir / "outer_export_probe.md").write_text(bundle.to_markdown(), encoding="utf-8")
    atomic_write_json(output_dir / "outer_export.blueprint.json", bundle.export_blueprint)
    atomic_write_json(output_dir / "industrial_planner.blueprint.json", export_bundle["blueprint"])
    atomic_write_json(output_dir / "industrial_planner.compatibility_manifest.json", export_bundle["compatibility_manifest"])
    atomic_write_json(output_dir / "validation_report.json", export_bundle["validation_report"])
    (output_dir / "validation_report.md").write_text(str(export_bundle["validation_report_markdown"]), encoding="utf-8")
    atomic_write_json(output_dir / "throughput_report.json", export_bundle["throughput_report"])
    (output_dir / "throughput_report.md").write_text(str(export_bundle["throughput_report_markdown"]), encoding="utf-8")

    print(f"outer deployment probe written: {output_dir}")
    print(f"base id: {args.base_id}")
    print(f"status: {bundle.status}")
    print(f"blocker: {bundle.blocker_classification}")
    print(
        "validator import/layout: "
        f"{bundle.validation_report.get('is_import_compatible')}/"
        f"{bundle.validation_report.get('is_layout_healthy')}"
    )


if __name__ == "__main__":
    main()

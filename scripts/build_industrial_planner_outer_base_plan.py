"""Build an adapter-side outer deployment plan for IndustrialPlanner bases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.base_planner.outer_deployment_plan import build_outer_base_deployment_plan
from src.search.exact_campaign import atomic_write_json

_DEFAULT_BLUEPRINT = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "full_demand_recipe_capacity_canonical_blueprint.json"
)
_DEFAULT_JSON = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "generated_outer_base_bundle" / "outer_deployment_plan.json"
)
_DEFAULT_MARKDOWN = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "generated_outer_base_bundle" / "outer_deployment_plan.md"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an adapter-side outer deployment plan without changing the canonical blueprint schema."
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
        "--json-output",
        default=str(_DEFAULT_JSON),
        help="Where to write the outer deployment plan JSON.",
    )
    parser.add_argument(
        "--markdown-output",
        default=str(_DEFAULT_MARKDOWN),
        help="Where to write the outer deployment plan Markdown.",
    )
    args = parser.parse_args()

    blueprint_path = Path(args.blueprint)
    blueprint_payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
    plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint_payload,
        base_id=str(args.base_id),
    )

    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    atomic_write_json(json_output, plan.to_dict())
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(plan.to_markdown(), encoding="utf-8")

    print(f"outer deployment plan written: {json_output}")
    print(f"markdown summary written: {markdown_output}")
    print(f"base id: {args.base_id}")
    print(f"inner island origin: {plan.inner_island_origin}")
    print(f"boundary assignments: {len(plan.boundary_assignments)}")
    print(f"connector reservations: {len(plan.connector_reservations)}")
    print(f"witness reservations: {len(plan.witness_reservations)}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PLAN_JSON_PATH = PROJECT_ROOT / "rules" / "preprocess_plan.json"
PLAN_SCHEMA_PATH = PROJECT_ROOT / "rules" / "preprocess_plan.schema.json"


def test_preprocess_plan_matches_schema() -> None:
    plan_payload = json.loads(PLAN_JSON_PATH.read_text(encoding="utf-8"))
    schema_payload = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
    validate(instance=plan_payload, schema=schema_payload)


def test_overlay_only_plan_shape_is_valid() -> None:
    plan_payload = json.loads(PLAN_JSON_PATH.read_text(encoding="utf-8"))
    schema_payload = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
    minimal_overlay = {
        "$schema": plan_payload["$schema"],
        "metadata": plan_payload["metadata"],
        "cycle_groups": plan_payload["cycle_groups"],
        "utility_operations": plan_payload["utility_operations"],
    }
    validate(instance=minimal_overlay, schema=schema_payload)

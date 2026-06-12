from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError as JsonSchemaValidationError

from src.interchange.preprocess_context import (
    build_preprocess_context_from_rules_and_plan,
    load_default_preprocess_context,
    load_preprocess_context_from_paths,
)
from src.preprocess.demand_solver import (
    generate_ceil_machine_counts,
    generate_generic_io_requirements,
    generate_port_budget,
    normalize_json_numbers,
    solve_demands,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RULES_JSON_PATH = PROJECT_ROOT / "rules" / "canonical_rules.json"
PLAN_JSON_PATH = PROJECT_ROOT / "rules" / "preprocess_plan.json"
DATA_DIR = PROJECT_ROOT / "data" / "preprocessed"


def _canonicalize(value):
    value = normalize_json_numbers(value)
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(subvalue)
            for key, subvalue in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


@pytest.fixture(scope="module")
def raw_rules_dict() -> dict:
    return json.loads(RULES_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw_plan_dict() -> dict:
    return json.loads(PLAN_JSON_PATH.read_text(encoding="utf-8"))


def test_default_preprocess_context_loads_expected_counts() -> None:
    context = load_default_preprocess_context()

    assert context.metadata["source_rules_version"] == "1.1.0"
    assert context.metadata["source_plan_version"] == "0.2.0"
    assert context.metadata["recipe_source"] == "canonical_rules"
    assert float(context.tick_interval_seconds) == 2.0
    assert float(context.belt_capacity_per_tick) == 1.0
    assert len(context.recipes) == 17
    assert len(context.targets) == 2
    assert len(context.cycle_groups) == 2
    assert len(context.utility_operations) == 4
    assert context.recipes["packaging_battery"].template == "manufacturing_6x4"
    assert context.targets["valley_battery"].final_recipe_id == "packaging_battery"



def test_preprocess_context_path_loader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    rules_text = RULES_JSON_PATH.read_text(encoding="utf-8").replace(
        '"value": 3.0,\n      "final_recipe_id": "packaging_battery"',
        '"value": 3.0,\n      "value": 999.0,\n      "final_recipe_id": "packaging_battery"',
        1,
    )
    rules_path = tmp_path / "canonical_rules.json"
    plan_path = tmp_path / "preprocess_plan.json"
    rules_path.write_text(rules_text, encoding="utf-8")
    plan_path.write_text(PLAN_JSON_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON key: value"):
        load_preprocess_context_from_paths(rules_path=rules_path, plan_path=plan_path)


def test_preprocess_context_path_loader_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    rules_text = RULES_JSON_PATH.read_text(encoding="utf-8").replace(
        '"value": 3.0,\n      "final_recipe_id": "packaging_battery"',
        '"value": NaN,\n      "final_recipe_id": "packaging_battery"',
        1,
    )
    rules_path = tmp_path / "canonical_rules.json"
    plan_path = tmp_path / "preprocess_plan.json"
    rules_path.write_text(rules_text, encoding="utf-8")
    plan_path.write_text(PLAN_JSON_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON constant: NaN"):
        load_preprocess_context_from_paths(rules_path=rules_path, plan_path=plan_path)


def test_preprocess_context_path_loader_rejects_overflow_json_numbers(tmp_path: Path) -> None:
    rules_text = RULES_JSON_PATH.read_text(encoding="utf-8").replace(
        '"value": 3.0,\n      "final_recipe_id": "packaging_battery"',
        '"value": 1e309,\n      "final_recipe_id": "packaging_battery"',
        1,
    )
    rules_path = tmp_path / "canonical_rules.json"
    plan_path = tmp_path / "preprocess_plan.json"
    rules_path.write_text(rules_text, encoding="utf-8")
    plan_path.write_text(PLAN_JSON_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON number: 1e309"):
        load_preprocess_context_from_paths(rules_path=rules_path, plan_path=plan_path)


def test_preprocess_context_path_loader_rejects_schema_missing_required_rule_field(tmp_path: Path) -> None:
    rules_payload = json.loads(RULES_JSON_PATH.read_text(encoding="utf-8"))
    del rules_payload["globals"]["time"]["tick_interval_seconds"]

    rules_path = tmp_path / "canonical_rules.json"
    plan_path = tmp_path / "preprocess_plan.json"
    rules_path.write_text(json.dumps(rules_payload), encoding="utf-8")
    plan_path.write_text(PLAN_JSON_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(JsonSchemaValidationError, match="tick_interval_seconds"):
        load_preprocess_context_from_paths(rules_path=rules_path, plan_path=plan_path)


def test_preprocess_context_path_loader_rejects_schema_missing_required_plan_field(tmp_path: Path) -> None:
    plan_payload = json.loads(PLAN_JSON_PATH.read_text(encoding="utf-8"))
    del plan_payload["utility_operations"]["wireless_sink"]["generic_input_slots"]

    rules_path = tmp_path / "canonical_rules.json"
    plan_path = tmp_path / "preprocess_plan.json"
    rules_path.write_text(RULES_JSON_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    with pytest.raises(JsonSchemaValidationError, match="generic_input_slots"):
        load_preprocess_context_from_paths(rules_path=rules_path, plan_path=plan_path)


def test_preprocess_context_report_writer_rejects_nonfinite_numbers(tmp_path: Path) -> None:
    from scripts.build_current_preprocess_context import _atomic_write_json_strict

    output_path = tmp_path / "context.json"
    with pytest.raises(ValueError, match="Out of range float values"):
        _atomic_write_json_strict(output_path, {"bad": float("nan")})

    assert not output_path.exists()


def test_preprocess_context_plan_rejects_duplicate_slot_keys(tmp_path: Path) -> None:
    rules_path = tmp_path / "canonical_rules.json"
    plan_path = tmp_path / "preprocess_plan.json"
    rules_path.write_text(RULES_JSON_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    plan_path.write_text(
        '{"utility_operations":{"wireless_sink":{'
        '"facility_type":"protocol_storage_box",'
        '"generic_input_slots":3,'
        '"generic_input_slots":0}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_preprocess_context_from_paths(rules_path=rules_path, plan_path=plan_path)


def test_preprocess_context_rejects_loose_utility_slot_counts(
    raw_rules_dict,
    raw_plan_dict,
) -> None:
    mutated_plan = copy.deepcopy(raw_plan_dict)
    mutated_plan["utility_operations"]["wireless_sink"]["generic_input_slots"] = "3"

    with pytest.raises(TypeError, match="generic_input_slots"):
        build_preprocess_context_from_rules_and_plan(raw_rules_dict, mutated_plan)

def test_preprocess_context_accepts_overlay_only_plan(raw_rules_dict, raw_plan_dict) -> None:
    minimal_overlay = {
        "$schema": raw_plan_dict.get("$schema"),
        "metadata": raw_plan_dict["metadata"],
        "cycle_groups": raw_plan_dict["cycle_groups"],
        "utility_operations": raw_plan_dict["utility_operations"],
    }

    context = build_preprocess_context_from_rules_and_plan(raw_rules_dict, minimal_overlay)
    assert len(context.recipes) == 17
    assert len(context.targets) == 2
    assert context.commodity_roles["source_ore"].source_kind == "external_boundary"


@pytest.mark.parametrize("overlay_key", ["recipes", "production_targets", "commodity_roles"])
def test_preprocess_context_rejects_canonical_metadata_overrides(
    raw_rules_dict,
    raw_plan_dict,
    overlay_key,
) -> None:
    mutated_plan = copy.deepcopy(raw_plan_dict)
    mutated_plan[overlay_key] = {}

    with pytest.raises(ValueError, match="additive-only"):
        build_preprocess_context_from_rules_and_plan(raw_rules_dict, mutated_plan)


def test_preprocess_context_rejects_multiple_non_cycle_producers(raw_rules_dict, raw_plan_dict) -> None:
    mutated_rules = copy.deepcopy(raw_rules_dict)
    mutated_rules["recipes"]["duplicate_battery"] = {
        "template": "manufacturing_6x4",
        "ticks_per_cycle": 5,
        "inputs": {"dense_source_powder": 1},
        "outputs": {"valley_battery": 1},
    }

    with pytest.raises(ValueError, match="multiple producer recipes"):
        build_preprocess_context_from_rules_and_plan(mutated_rules, raw_plan_dict)


def test_preprocess_context_validates_target_final_recipe(raw_rules_dict, raw_plan_dict) -> None:
    mutated_rules = copy.deepcopy(raw_rules_dict)
    mutated_rules["production_targets"]["valley_battery"]["final_recipe_id"] = "parts_maker"

    with pytest.raises(ValueError, match="is not produced by its final recipe"):
        build_preprocess_context_from_rules_and_plan(mutated_rules, raw_plan_dict)


def test_context_driven_pipeline_matches_current_frozen_preprocess_artifacts() -> None:
    context = load_default_preprocess_context()
    flows, fractional = solve_demands(context=context)
    counts = generate_ceil_machine_counts(fractional)
    budget = generate_port_budget(flows, context=context)
    generic_io = generate_generic_io_requirements(flows, budget, context=context)

    assert _canonicalize(flows) == _canonicalize(json.loads((DATA_DIR / "commodity_demands.json").read_text(encoding="utf-8")))
    assert _canonicalize(counts) == _canonicalize(json.loads((DATA_DIR / "machine_counts.json").read_text(encoding="utf-8")))
    assert _canonicalize(budget) == _canonicalize(json.loads((DATA_DIR / "port_budget.json").read_text(encoding="utf-8")))
    assert _canonicalize(generic_io) == _canonicalize(json.loads((DATA_DIR / "generic_io_requirements.json").read_text(encoding="utf-8")))

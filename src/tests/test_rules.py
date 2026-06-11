"""
Tests for canonical rules, schema, models, and semantic validator.
Status: CURRENT_CODE_ALIGNED

目标：验证静态规则底座的合法性，并确保越权或违背物理真理的设定会被拦截。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from pydantic import ValidationError as PydanticValidationError

from src.rules.models import CanonicalRulesDocument
from src.rules.semantic_validator import SemanticValidationError, validate_canonical_document


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RULES_JSON_PATH = PROJECT_ROOT / "rules" / "canonical_rules.json"
SCHEMA_JSON_PATH = PROJECT_ROOT / "rules" / "canonical_rules.schema.json"


@pytest.fixture
def raw_rules_dict() -> dict:
    with RULES_JSON_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def raw_schema_dict() -> dict:
    with SCHEMA_JSON_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def valid_document(raw_rules_dict) -> CanonicalRulesDocument:
    return CanonicalRulesDocument.model_validate(raw_rules_dict)


def test_json_matches_schema(raw_rules_dict, raw_schema_dict):
    try:
        validate(instance=raw_rules_dict, schema=raw_schema_dict)
    except JsonSchemaValidationError as e:
        pytest.fail(f"规范 JSON 未能通过 Schema 校验: {e.message}")


def test_schema_rejects_unknown_fields(raw_rules_dict, raw_schema_dict):
    mutated_dict = copy.deepcopy(raw_rules_dict)
    mutated_dict["facility_templates"]["manufacturing_3x3"]["illegal_max_count"] = 50

    with pytest.raises(JsonSchemaValidationError) as exc_info:
        validate(instance=mutated_dict, schema=raw_schema_dict)
    assert "illegal_max_count" in exc_info.value.message


def test_pydantic_parsing(raw_rules_dict):
    doc = CanonicalRulesDocument.model_validate(raw_rules_dict)
    assert doc.globals.grid.width == 70
    assert doc.globals.empty_rectangle.objective == "max_lex_area_min_side"
    assert doc.globals.empty_rectangle.min_side_admissibility == 6
    assert doc.routing_rules.bridge_mechanics.can_turn is False
    assert "packaging_battery" in doc.recipes
    assert doc.production_targets["valley_battery"].final_recipe_id == "packaging_battery"
    assert doc.commodity_metadata["source_ore"].source_kind == "external_boundary"


def test_pydantic_frozen_immutability(valid_document):
    with pytest.raises(PydanticValidationError):
        valid_document.globals.grid.width = 999


def test_pydantic_forbids_extra_fields(raw_rules_dict):
    mutated_dict = copy.deepcopy(raw_rules_dict)
    mutated_dict["globals"]["sneaky_heuristic_flag"] = True

    with pytest.raises(PydanticValidationError) as exc_info:
        CanonicalRulesDocument.model_validate(mutated_dict)
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_semantic_validation_passes(valid_document):
    validate_canonical_document(valid_document)


def test_semantic_grid_size_violation(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["globals"]["grid"]["width"] = 71
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="必须为 70x70"):
        validate_canonical_document(doc)


def test_semantic_manufacturing_power_violation(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["facility_templates"]["manufacturing_5x5"]["needs_power"] = False
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="所有制造单位必须供电"):
        validate_canonical_document(doc)


def test_semantic_recipe_invalid_template(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["recipes"]["packaging_battery"]["template"] = "ghost_template"
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="外键冲突"):
        validate_canonical_document(doc)


def test_semantic_bridge_physics_violation(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["routing_rules"]["bridge_mechanics"]["can_turn"] = True
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="绝对不可转弯"):
        validate_canonical_document(doc)


def test_semantic_production_target_reference(valid_document):
    target = valid_document.production_targets["valley_battery"]
    assert target.final_recipe_id == "packaging_battery"
    assert "valley_battery" in valid_document.recipes[target.final_recipe_id].outputs


def test_semantic_recipe_no_outputs(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["recipes"]["refinery_steel"]["outputs"] = {}
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="没有任何输出"):
        validate_canonical_document(doc)


def test_semantic_recipe_self_loop(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["recipes"]["refinery_steel"]["inputs"]["steel_block"] = 1.0
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="无限死锁"):
        validate_canonical_document(doc)


def test_semantic_core_limits_dependency(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["facility_templates"]["manufacturing_3x3"]["core_limits"] = {"max_outputs": 1, "max_inputs": 1}
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="错误地携带了 'core_limits' 字段"):
        validate_canonical_document(doc)


def test_semantic_target_final_recipe_must_produce_target(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["production_targets"]["valley_battery"]["final_recipe_id"] = "parts_maker"
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="不是其 final_recipe"):
        validate_canonical_document(doc)


def test_semantic_cycle_internal_requires_cycle_group(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["commodity_metadata"]["buckwheat"]["cycle_group"] = None
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="必须声明 cycle_group"):
        validate_canonical_document(doc)


def test_semantic_production_target_requires_generic_input_sink(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["commodity_metadata"]["valley_battery"]["sink_kind"] = "none"
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="必须在 commodity_metadata 中声明 sink_kind='generic_input'"):
        validate_canonical_document(doc)


def test_semantic_generic_input_sink_must_not_be_recipe_input(raw_rules_dict):
    mutated = copy.deepcopy(raw_rules_dict)
    mutated["commodity_metadata"]["steel_part"]["sink_kind"] = "generic_input"
    mutated["production_targets"]["steel_part"] = {
        "mode": "equivalent_full_speed_lines",
        "value": 1.0,
        "final_recipe_id": "parts_maker",
    }
    doc = CanonicalRulesDocument.model_validate(mutated)

    with pytest.raises(SemanticValidationError, match="不能同时作为配方输入"):
        validate_canonical_document(doc)

"""Frozen-compatible preprocess context contract.

This module introduces the build-time `PreprocessContext` layer used by preprocess
regeneration. Canonical rules now carry the repository-owned recipe / target /
commodity metadata truth; `preprocess_plan.json` remains the additive overlay for
cycle groups and utility operations only.
The certified runtime still consumes frozen `data/preprocessed/*` artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import copy
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import validate as validate_json_schema

from src.io.strict_json import load_strict_json

PREPROCESS_PLAN_VERSION = "0.2.0"
PLAN_CANONICAL_OVERRIDE_KEYS = ("recipes", "production_targets", "commodity_roles")

_ALLOWED_TARGET_MODES = {"equivalent_full_speed_lines", "rate_per_tick"}
_ALLOWED_SOURCE_KINDS = {"external_boundary", "cycle_internal", "internal_only", None}
_ALLOWED_SINK_KINDS = {"generic_input", "none", None}


@dataclass(frozen=True)
class PreprocessRecipe:
    recipe_id: str
    template: str
    ticks_per_cycle: int
    inputs: Mapping[str, Fraction]
    outputs: Mapping[str, Fraction]

    def input_rate(self, commodity_id: str) -> Fraction:
        return self.inputs.get(commodity_id, Fraction(0)) / Fraction(self.ticks_per_cycle)

    def output_rate(self, commodity_id: str) -> Fraction:
        return self.outputs.get(commodity_id, Fraction(0)) / Fraction(self.ticks_per_cycle)


@dataclass(frozen=True)
class ProductionTarget:
    commodity_id: str
    mode: str
    value: Fraction
    final_recipe_id: str


@dataclass(frozen=True)
class CommodityRole:
    commodity_id: str
    source_kind: str | None
    sink_kind: str | None
    cycle_group: str | None


@dataclass(frozen=True)
class CycleGroup:
    group_id: str
    recipes: tuple[str, ...]
    internal_commodities: tuple[str, ...]
    net_export_commodities: tuple[str, ...]


@dataclass(frozen=True)
class UtilityOperation:
    operation_type: str
    facility_type: str
    generic_input_slots: int = 0
    generic_output_slots: int = 0


@dataclass(frozen=True)
class PreprocessContext:
    metadata: Mapping[str, Any]
    tick_interval_seconds: Fraction
    belt_capacity_per_tick: Fraction
    facility_templates: Mapping[str, Mapping[str, Any]]
    recipes: Mapping[str, PreprocessRecipe]
    targets: Mapping[str, ProductionTarget]
    commodity_roles: Mapping[str, CommodityRole]
    cycle_groups: Mapping[str, CycleGroup]
    utility_operations: Mapping[str, UtilityOperation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": dict(self.metadata),
            "tick_interval_seconds": _fraction_to_json_value(self.tick_interval_seconds),
            "belt_capacity_per_tick": _fraction_to_json_value(self.belt_capacity_per_tick),
            "facility_templates": copy.deepcopy(self.facility_templates),
            "recipes": {
                recipe_id: {
                    "template": recipe.template,
                    "ticks_per_cycle": recipe.ticks_per_cycle,
                    "inputs": _fraction_mapping_to_json(recipe.inputs),
                    "outputs": _fraction_mapping_to_json(recipe.outputs),
                }
                for recipe_id, recipe in sorted(self.recipes.items())
            },
            "production_targets": {
                commodity_id: {
                    "mode": target.mode,
                    "value": _fraction_to_json_value(target.value),
                    "final_recipe_id": target.final_recipe_id,
                }
                for commodity_id, target in sorted(self.targets.items())
            },
            "commodity_roles": {
                commodity_id: {
                    "source_kind": role.source_kind,
                    "sink_kind": role.sink_kind,
                    "cycle_group": role.cycle_group,
                }
                for commodity_id, role in sorted(self.commodity_roles.items())
            },
            "cycle_groups": {
                group_id: {
                    "recipes": list(group.recipes),
                    "internal_commodities": list(group.internal_commodities),
                    "net_export_commodities": list(group.net_export_commodities),
                }
                for group_id, group in sorted(self.cycle_groups.items())
            },
            "utility_operations": {
                operation_type: {
                    "facility_type": utility.facility_type,
                    "generic_input_slots": int(utility.generic_input_slots),
                    "generic_output_slots": int(utility.generic_output_slots),
                }
                for operation_type, utility in sorted(self.utility_operations.items())
            },
        }

    def commodity_role(self, commodity_id: str) -> CommodityRole:
        return self.commodity_roles.get(
            commodity_id,
            CommodityRole(
                commodity_id=str(commodity_id),
                source_kind=None,
                sink_kind="none",
                cycle_group=None,
            ),
        )


def build_preprocess_context_from_rules_and_plan(
    rules_payload: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
) -> PreprocessContext:
    if not isinstance(rules_payload, Mapping):
        raise TypeError("rules payload must be a mapping")
    if not isinstance(plan_payload, Mapping):
        raise TypeError("preprocess plan payload must be a mapping")

    globals_payload = _mapping_or_empty(rules_payload.get("globals"))
    time_payload = _mapping_or_empty(globals_payload.get("time"))
    logistics_payload = _mapping_or_empty(globals_payload.get("logistics"))
    tick_interval_seconds = _to_fraction(time_payload.get("tick_interval_seconds", 2.0))
    belt_capacity_per_tick = _to_fraction(logistics_payload.get("belt_capacity_per_tick", 1.0))
    if tick_interval_seconds <= 0:
        raise ValueError("tick_interval_seconds must be > 0")
    if belt_capacity_per_tick <= 0:
        raise ValueError("belt_capacity_per_tick must be > 0")

    facility_templates = _mapping_or_empty(rules_payload.get("facility_templates"))
    if not facility_templates:
        raise ValueError("rules payload must provide facility_templates")

    rules_metadata = _mapping_or_empty(rules_payload.get("metadata"))
    plan_metadata = _mapping_or_empty(plan_payload.get("metadata"))

    plan_override_keys = sorted(
        key for key in PLAN_CANONICAL_OVERRIDE_KEYS if key in plan_payload
    )
    if plan_override_keys:
        raise ValueError(
            "preprocess_plan.json must be additive-only; canonical recipe/target/"
            "commodity metadata overrides are not allowed: "
            + ", ".join(plan_override_keys)
        )

    merged_recipes = _mapping_or_empty(rules_payload.get("recipes"))
    merged_targets = _mapping_or_empty(rules_payload.get("production_targets"))
    merged_commodity_roles = _mapping_or_empty(rules_payload.get("commodity_metadata"))

    recipes = {
        recipe_id: _parse_recipe(recipe_id, raw_recipe)
        for recipe_id, raw_recipe in sorted(merged_recipes.items())
    }
    targets = {
        commodity_id: _parse_target(commodity_id, raw_target)
        for commodity_id, raw_target in sorted(merged_targets.items())
    }
    commodity_roles = {
        commodity_id: _parse_commodity_role(commodity_id, raw_role)
        for commodity_id, raw_role in sorted(merged_commodity_roles.items())
    }
    cycle_groups = {
        group_id: _parse_cycle_group(group_id, raw_group)
        for group_id, raw_group in sorted(_mapping_or_empty(plan_payload.get("cycle_groups")).items())
    }
    utility_operations = {
        operation_type: _parse_utility_operation(operation_type, raw_utility)
        for operation_type, raw_utility in sorted(_mapping_or_empty(plan_payload.get("utility_operations")).items())
    }

    context = PreprocessContext(
        metadata={
            "version": str(plan_metadata.get("version", PREPROCESS_PLAN_VERSION)),
            "description": str(
                plan_metadata.get(
                    "description",
                    "Build-time additive preprocess context overlay. Frozen-certified artifacts remain runtime truth.",
                )
            ),
            "source_rules_version": str(rules_metadata.get("version", "unknown")),
            "source_plan_version": str(plan_metadata.get("version", PREPROCESS_PLAN_VERSION)),
            "recipe_source": "canonical_rules",
            "target_source": "canonical_rules",
            "commodity_role_source": "canonical_rules",
        },
        tick_interval_seconds=tick_interval_seconds,
        belt_capacity_per_tick=belt_capacity_per_tick,
        facility_templates=copy.deepcopy(facility_templates),
        recipes=recipes,
        targets=targets,
        commodity_roles=commodity_roles,
        cycle_groups=cycle_groups,
        utility_operations=utility_operations,
    )
    validate_preprocess_context(context)
    return context


def validate_preprocess_context(context: PreprocessContext) -> None:
    if not context.recipes:
        raise ValueError("preprocess context must contain at least one recipe")
    if not context.targets:
        raise ValueError("preprocess context must contain at least one production target")

    for recipe in context.recipes.values():
        if recipe.template not in context.facility_templates:
            raise ValueError(
                f"preprocess recipe {recipe.recipe_id!r} references unknown template {recipe.template!r}"
            )

    producers = build_producer_index(context)
    consumers: dict[str, list[str]] = {}
    for recipe_id, recipe in context.recipes.items():
        for commodity_id in recipe.inputs:
            consumers.setdefault(str(commodity_id), []).append(str(recipe_id))

    for commodity_id, target in context.targets.items():
        if target.mode not in _ALLOWED_TARGET_MODES:
            raise ValueError(f"unknown production target mode: {target.mode!r}")
        if target.final_recipe_id not in context.recipes:
            raise ValueError(
                f"production target {commodity_id!r} references unknown final recipe {target.final_recipe_id!r}"
            )
        final_recipe = context.recipes[target.final_recipe_id]
        if commodity_id not in final_recipe.outputs:
            raise ValueError(
                f"production target {commodity_id!r} is not produced by its final recipe {target.final_recipe_id!r}"
            )
        if target.value <= 0:
            raise ValueError(f"production target {commodity_id!r} must be > 0")

    cycle_group_internal_commodities = {
        group_id: set(group.internal_commodities)
        for group_id, group in context.cycle_groups.items()
    }

    for role in context.commodity_roles.values():
        if role.source_kind not in _ALLOWED_SOURCE_KINDS:
            raise ValueError(f"unknown source_kind for commodity {role.commodity_id!r}: {role.source_kind!r}")
        if role.sink_kind not in _ALLOWED_SINK_KINDS:
            raise ValueError(f"unknown sink_kind for commodity {role.commodity_id!r}: {role.sink_kind!r}")
        if role.sink_kind == "generic_input":
            if role.commodity_id not in context.targets:
                raise ValueError(
                    f"generic_input commodity {role.commodity_id!r} must correspond to a production target"
                )
            if role.commodity_id in consumers:
                raise ValueError(
                    f"generic_input commodity {role.commodity_id!r} cannot also be a recipe input; "
                    f"consumer recipes: {', '.join(sorted(consumers[role.commodity_id]))}"
                )
        if role.source_kind == "cycle_internal":
            if not role.cycle_group:
                raise ValueError(f"cycle_internal commodity {role.commodity_id!r} must declare cycle_group")
            if role.cycle_group not in context.cycle_groups:
                raise ValueError(
                    f"commodity {role.commodity_id!r} references unknown cycle_group {role.cycle_group!r}"
                )
            if role.commodity_id not in cycle_group_internal_commodities[role.cycle_group]:
                raise ValueError(
                    f"cycle_internal commodity {role.commodity_id!r} declares cycle_group {role.cycle_group!r} "
                    "but is not listed in that group's internal_commodities"
                )
        elif role.cycle_group is not None:
            raise ValueError(
                f"non-cycle commodity {role.commodity_id!r} cannot declare cycle_group {role.cycle_group!r}"
            )

    for commodity_id in context.targets:
        role = context.commodity_roles.get(commodity_id)
        if role is None:
            raise ValueError(f"production target {commodity_id!r} is missing commodity_roles entry")
        if role.sink_kind != "generic_input":
            raise ValueError(
                f"production target {commodity_id!r} must declare sink_kind='generic_input'"
            )

    for group in context.cycle_groups.values():
        if len(group.internal_commodities) != len(group.recipes):
            raise ValueError(
                f"cycle group {group.group_id!r} must be square: recipes={len(group.recipes)} internal_commodities={len(group.internal_commodities)}"
            )
        internal_commodities = set(group.internal_commodities)
        for recipe_id in group.recipes:
            if recipe_id not in context.recipes:
                raise ValueError(f"cycle group {group.group_id!r} references unknown recipe {recipe_id!r}")
        outside_internal_by_recipe = _cycle_group_recipe_io_outside_internal(context, group)
        if outside_internal_by_recipe:
            raise ValueError(_format_cycle_group_io_closure_error(group.group_id, outside_internal_by_recipe))
        for commodity_id in group.internal_commodities:
            role = context.commodity_roles.get(commodity_id)
            if role is None:
                raise ValueError(
                    f"cycle group {group.group_id!r} commodity {commodity_id!r} is missing commodity_roles entry"
                )
            if role.cycle_group != group.group_id:
                raise ValueError(
                    f"commodity {commodity_id!r} declares cycle_group {role.cycle_group!r}, expected {group.group_id!r}"
                )
        for commodity_id in group.net_export_commodities:
            if commodity_id not in internal_commodities:
                raise ValueError(
                    f"cycle group {group.group_id!r} net_export_commodity {commodity_id!r} "
                    "is not listed in internal_commodities"
                )
        _solve_cycle_group_exact(context, group.group_id, {})
        for commodity_id in group.net_export_commodities:
            _solve_cycle_group_exact(context, group.group_id, {commodity_id: Fraction(1)})

    for commodity_id, recipe_ids in producers.items():
        role = context.commodity_role(commodity_id)
        if role.cycle_group is None and len(recipe_ids) > 1:
            raise ValueError(
                f"non-cycle commodity {commodity_id!r} has multiple producer recipes: {', '.join(recipe_ids)}"
            )

    for utility in context.utility_operations.values():
        if utility.facility_type not in context.facility_templates:
            raise ValueError(
                f"utility operation {utility.operation_type!r} references unknown facility_type {utility.facility_type!r}"
            )
        if utility.generic_input_slots < 0 or utility.generic_output_slots < 0:
            raise ValueError(f"utility operation {utility.operation_type!r} must have non-negative generic slot counts")




def _merge_overlay(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged.update(overlay)
    return merged

def build_producer_index(context: PreprocessContext) -> dict[str, tuple[str, ...]]:
    producers: dict[str, list[str]] = {}
    for recipe_id, recipe in context.recipes.items():
        for commodity_id in recipe.outputs:
            producers.setdefault(commodity_id, []).append(recipe_id)
    return {
        commodity_id: tuple(sorted(recipe_ids))
        for commodity_id, recipe_ids in sorted(producers.items())
    }


@lru_cache(maxsize=None)
def _load_json_schema(schema_name: str) -> Mapping[str, Any]:
    project_root = Path(__file__).resolve().parent.parent.parent
    return load_strict_json(project_root / "rules" / schema_name)


def _validate_preprocess_source_schemas(
    rules_payload: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
) -> None:
    """Validate strict-loaded source documents before applying context defaults."""
    validate_json_schema(
        instance=rules_payload,
        schema=_load_json_schema("canonical_rules.schema.json"),
    )
    validate_json_schema(
        instance=plan_payload,
        schema=_load_json_schema("preprocess_plan.schema.json"),
    )


@lru_cache(maxsize=1)
def load_default_preprocess_context() -> PreprocessContext:
    project_root = Path(__file__).resolve().parent.parent.parent
    rules_payload = load_strict_json(project_root / "rules" / "canonical_rules.json")
    plan_payload = load_strict_json(project_root / "rules" / "preprocess_plan.json")
    _validate_preprocess_source_schemas(rules_payload, plan_payload)
    return build_preprocess_context_from_rules_and_plan(rules_payload, plan_payload)


def load_preprocess_context_from_paths(
    *,
    rules_path: Path,
    plan_path: Path,
) -> PreprocessContext:
    rules_payload = load_strict_json(Path(rules_path))
    plan_payload = load_strict_json(Path(plan_path))
    _validate_preprocess_source_schemas(rules_payload, plan_payload)
    return build_preprocess_context_from_rules_and_plan(
        rules_payload,
        plan_payload,
    )


def build_template_mapping(context: PreprocessContext) -> dict[str, str]:
    return {
        recipe_id: recipe.template
        for recipe_id, recipe in sorted(context.recipes.items())
    }


def solve_cycle_group_exact(
    context: PreprocessContext,
    group_id: str,
    external_demands: Mapping[str, Fraction | int | float],
) -> dict[str, Fraction]:
    return _solve_cycle_group_exact(context, group_id, external_demands)


def _solve_cycle_group_exact(
    context: PreprocessContext,
    group_id: str,
    external_demands: Mapping[str, Fraction | int | float],
) -> dict[str, Fraction]:
    group = context.cycle_groups.get(group_id)
    if group is None:
        raise KeyError(f"unknown cycle group: {group_id}")

    outside_internal_by_recipe = _cycle_group_recipe_io_outside_internal(context, group)
    if outside_internal_by_recipe:
        raise ValueError(_format_cycle_group_io_closure_error(group_id, outside_internal_by_recipe))

    internal_commodities = set(group.internal_commodities)
    net_export_commodities = set(group.net_export_commodities)
    normalized_external_demands: dict[str, Fraction] = {}
    for raw_commodity_id, raw_demand in external_demands.items():
        commodity_id = str(raw_commodity_id)
        demand = _to_fraction(raw_demand)
        if demand < 0:
            raise ValueError(
                f"cycle group {group_id!r} external demand for commodity {commodity_id!r} "
                f"must be non-negative: {demand}"
            )
        if demand == 0:
            continue
        if commodity_id not in internal_commodities:
            raise ValueError(
                f"cycle group {group_id!r} external demand commodity {commodity_id!r} "
                "is not listed in internal_commodities"
            )
        if commodity_id not in net_export_commodities:
            raise ValueError(
                f"cycle group {group_id!r} external demand commodity {commodity_id!r} "
                "is not declared in net_export_commodities"
            )
        normalized_external_demands[commodity_id] = normalized_external_demands.get(
            commodity_id, Fraction(0)
        ) + demand

    matrix: list[list[Fraction]] = []
    rhs: list[Fraction] = []
    for commodity_id in group.internal_commodities:
        row: list[Fraction] = []
        for recipe_id in group.recipes:
            recipe = context.recipes[recipe_id]
            net_rate = recipe.output_rate(commodity_id) - recipe.input_rate(commodity_id)
            row.append(net_rate)
        matrix.append(row)
        rhs.append(normalized_external_demands.get(commodity_id, Fraction(0)))

    solution = _solve_square_linear_system(matrix, rhs)
    for index, run_rate in enumerate(solution):
        if run_rate < 0:
            recipe_id = group.recipes[index]
            raise ValueError(
                f"cycle group {group_id!r} produced negative run rate for recipe {recipe_id!r}: {run_rate}"
            )
    return {
        recipe_id: solution[index]
        for index, recipe_id in enumerate(group.recipes)
    }


def _cycle_group_recipe_io_outside_internal(
    context: PreprocessContext,
    group: CycleGroup,
) -> dict[str, tuple[str, ...]]:
    internal_commodities = set(group.internal_commodities)
    outside_by_recipe: dict[str, tuple[str, ...]] = {}
    for recipe_id in group.recipes:
        recipe = context.recipes.get(recipe_id)
        if recipe is None:
            continue
        referenced_commodities = set(recipe.inputs) | set(recipe.outputs)
        outside = tuple(sorted(referenced_commodities - internal_commodities))
        if outside:
            outside_by_recipe[recipe_id] = outside
    return outside_by_recipe


def _format_cycle_group_io_closure_error(
    group_id: str,
    outside_by_recipe: Mapping[str, tuple[str, ...]],
) -> str:
    details = "; ".join(
        f"{recipe_id}: {', '.join(commodities)}"
        for recipe_id, commodities in sorted(outside_by_recipe.items())
    )
    return (
        f"cycle group {group_id!r} recipes must reference only commodities listed in "
        f"internal_commodities; outside commodities: {details}"
    )


def _solve_square_linear_system(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    size = len(matrix)
    if size == 0:
        return []
    if any(len(row) != size for row in matrix):
        raise ValueError("cycle solver expects a square matrix")
    if len(rhs) != size:
        raise ValueError("cycle solver rhs length must match matrix size")

    augmented = [list(row) + [rhs_value] for row, rhs_value in zip(matrix, rhs)]
    for pivot_index in range(size):
        pivot_row = None
        for candidate in range(pivot_index, size):
            if augmented[candidate][pivot_index] != 0:
                pivot_row = candidate
                break
        if pivot_row is None:
            raise ValueError("cycle group matrix is singular and cannot be solved exactly")
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]

        pivot = augmented[pivot_index][pivot_index]
        augmented[pivot_index] = [value / pivot for value in augmented[pivot_index]]
        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            if factor == 0:
                continue
            augmented[row_index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row_index], augmented[pivot_index])
            ]

    return [augmented[index][-1] for index in range(size)]


def _parse_recipe(recipe_id: str, raw_recipe: Any) -> PreprocessRecipe:
    recipe = _mapping_or_empty(raw_recipe)
    inputs = {
        commodity_id: _to_fraction(amount)
        for commodity_id, amount in sorted(_mapping_or_empty(recipe.get("inputs")).items())
    }
    outputs = {
        commodity_id: _to_fraction(amount)
        for commodity_id, amount in sorted(_mapping_or_empty(recipe.get("outputs")).items())
    }
    if not outputs:
        raise ValueError(f"preprocess recipe {recipe_id!r} must provide at least one output")
    return PreprocessRecipe(
        recipe_id=str(recipe_id),
        template=str(recipe.get("template", "")).strip(),
        ticks_per_cycle=int(recipe.get("ticks_per_cycle", 0)),
        inputs=inputs,
        outputs=outputs,
    )


def _parse_target(commodity_id: str, raw_target: Any) -> ProductionTarget:
    target = _mapping_or_empty(raw_target)
    return ProductionTarget(
        commodity_id=str(commodity_id),
        mode=str(target.get("mode", "")).strip(),
        value=_to_fraction(target.get("value", 0)),
        final_recipe_id=str(target.get("final_recipe_id", "")).strip(),
    )


def _parse_commodity_role(commodity_id: str, raw_role: Any) -> CommodityRole:
    role = _mapping_or_empty(raw_role)
    source_kind = role.get("source_kind")
    sink_kind = role.get("sink_kind")
    cycle_group = role.get("cycle_group")
    return CommodityRole(
        commodity_id=str(commodity_id),
        source_kind=None if source_kind is None else str(source_kind),
        sink_kind=None if sink_kind is None else str(sink_kind),
        cycle_group=None if cycle_group is None or str(cycle_group) == "" else str(cycle_group),
    )


def _parse_cycle_group(group_id: str, raw_group: Any) -> CycleGroup:
    group = _mapping_or_empty(raw_group)
    return CycleGroup(
        group_id=str(group_id),
        recipes=tuple(str(recipe_id) for recipe_id in _iter_str_list(group.get("recipes"))),
        internal_commodities=tuple(str(commodity_id) for commodity_id in _iter_str_list(group.get("internal_commodities"))),
        net_export_commodities=tuple(str(commodity_id) for commodity_id in _iter_str_list(group.get("net_export_commodities"))),
    )


def _strict_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return int(value)


def _parse_utility_operation(operation_type: str, raw_utility: Any) -> UtilityOperation:
    utility = _mapping_or_empty(raw_utility)
    return UtilityOperation(
        operation_type=str(operation_type),
        facility_type=str(utility.get("facility_type", "")).strip(),
        generic_input_slots=_strict_nonnegative_int(
            utility.get("generic_input_slots", 0),
            f"utility_operations.{operation_type}.generic_input_slots",
        ),
        generic_output_slots=_strict_nonnegative_int(
            utility.get("generic_output_slots", 0),
            f"utility_operations.{operation_type}.generic_output_slots",
        ),
    )


def _iter_str_list(value: Any) -> Iterable[str]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a sequence of strings")
    return tuple(str(item) for item in value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _to_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid Fraction inputs")
    if isinstance(value, int):
        return Fraction(int(value), 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"cannot convert {type(value).__name__} to Fraction")


def _fraction_mapping_to_json(values: Mapping[str, Fraction]) -> dict[str, int | float]:
    return {
        commodity_id: _fraction_to_json_value(amount)
        for commodity_id, amount in sorted(values.items())
    }


def _fraction_to_json_value(value: Fraction) -> int | float:
    if value.denominator == 1:
        return int(value.numerator)
    rendered = round(float(value), 10)
    rounded_int = round(rendered)
    if abs(rendered - rounded_int) <= 1e-9:
        return int(rounded_int)
    return float(rendered)


__all__ = [
    "PREPROCESS_PLAN_VERSION",
    "CommodityRole",
    "CycleGroup",
    "PreprocessContext",
    "PreprocessRecipe",
    "ProductionTarget",
    "UtilityOperation",
    "build_preprocess_context_from_rules_and_plan",
    "build_producer_index",
    "build_template_mapping",
    "load_default_preprocess_context",
    "load_preprocess_context_from_paths",
    "solve_cycle_group_exact",
    "validate_preprocess_context",
]

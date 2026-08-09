"""Canonical operation-level commodity and port-slot profiles.

This module derives recipe-driven operation profiles from `PreprocessContext`
instead of maintaining a second hand-written truth table in Python.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import DefaultDict, Dict, Iterable, Mapping, Tuple

from src.interchange.preprocess_context import PreprocessContext, load_default_preprocess_context

EPSILON = 1e-9
DEFAULT_PREPROCESS_CONTEXT = load_default_preprocess_context()


@dataclass(frozen=True)
class OperationPortProfile:
    """Per-operation commodity rates and discrete port-slot requirements."""

    operation_type: str
    facility_type: str
    input_rates: Mapping[str, Fraction]
    output_rates: Mapping[str, Fraction]
    generic_input_slots: int = 0
    generic_output_slots: int = 0
    belt_capacity_per_tick: Fraction = Fraction(1, 1)

    @property
    def input_slots(self) -> Dict[str, int]:
        return {
            commodity: _rate_to_slots(rate, belt_capacity_per_tick=self.belt_capacity_per_tick)
            for commodity, rate in self.input_rates.items()
        }

    @property
    def output_slots(self) -> Dict[str, int]:
        return {
            commodity: _rate_to_slots(rate, belt_capacity_per_tick=self.belt_capacity_per_tick)
            for commodity, rate in self.output_rates.items()
        }



def _to_exact_fraction(value: object) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid rate inputs")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("rate inputs must be finite")
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"cannot convert {type(value).__name__} to Fraction")


def _rate_to_slots(rate: object, *, belt_capacity_per_tick: object = Fraction(1, 1)) -> int:
    """Convert per-tick rate to the exact minimum integer port-slot count."""
    rate_fraction = _to_exact_fraction(rate)
    if rate_fraction <= 0:
        return 0
    capacity = _to_exact_fraction(belt_capacity_per_tick)
    if capacity <= 0:
        raise ValueError("belt_capacity_per_tick must be > 0")
    required = rate_fraction / capacity
    return int((required.numerator + required.denominator - 1) // required.denominator)



def build_operation_port_profiles(
    context: PreprocessContext,
) -> Dict[str, OperationPortProfile]:
    belt_capacity_per_tick = context.belt_capacity_per_tick
    profiles: Dict[str, OperationPortProfile] = {}

    for recipe_id, recipe in sorted(context.recipes.items()):
        profiles[recipe_id] = OperationPortProfile(
            operation_type=recipe_id,
            facility_type=recipe.template,
            input_rates={
                commodity_id: recipe.input_rate(commodity_id)
                for commodity_id in sorted(recipe.inputs)
            },
            output_rates={
                commodity_id: recipe.output_rate(commodity_id)
                for commodity_id in sorted(recipe.outputs)
            },
            belt_capacity_per_tick=belt_capacity_per_tick,
        )

    for operation_type, utility in sorted(context.utility_operations.items()):
        profiles[operation_type] = OperationPortProfile(
            operation_type=operation_type,
            facility_type=utility.facility_type,
            input_rates={},
            output_rates={},
            generic_input_slots=int(utility.generic_input_slots),
            generic_output_slots=int(utility.generic_output_slots),
            belt_capacity_per_tick=belt_capacity_per_tick,
        )

    return profiles


OPERATION_PORT_PROFILES: Dict[str, OperationPortProfile] = build_operation_port_profiles(
    DEFAULT_PREPROCESS_CONTEXT
)


def get_operation_port_profile(operation_type: str) -> OperationPortProfile:
    return OPERATION_PORT_PROFILES[operation_type]



def find_unprofiled_operations(instances: Iterable[Mapping[str, object]]) -> Tuple[str, ...]:
    return tuple(sorted({
        str(inst["operation_type"])
        for inst in instances
        if "operation_type" in inst
        and str(inst["operation_type"]) not in OPERATION_PORT_PROFILES
    }))



def count_operations(
    instances: Iterable[Mapping[str, object]],
    mandatory_only: bool = False,
) -> Counter:
    counts: Counter = Counter()
    for inst in instances:
        if mandatory_only and not inst.get("is_mandatory"):
            continue
        operation_type = inst.get("operation_type")
        if operation_type:
            counts[str(operation_type)] += 1
    return counts



def aggregate_commodity_rates(
    operation_counts: Mapping[str, float],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    total_inputs: DefaultDict[str, float] = defaultdict(float)
    total_outputs: DefaultDict[str, float] = defaultdict(float)

    for operation_type, count in operation_counts.items():
        profile = OPERATION_PORT_PROFILES.get(operation_type)
        if not profile:
            continue
        for commodity, rate in profile.input_rates.items():
            total_inputs[commodity] += float(rate) * count
        for commodity, rate in profile.output_rates.items():
            total_outputs[commodity] += float(rate) * count

    return dict(total_inputs), dict(total_outputs)



def aggregate_port_slots(
    operation_counts: Mapping[str, int],
    *,
    profiles: Mapping[str, OperationPortProfile] | None = None,
) -> Dict[str, object]:
    """Aggregate slots against an explicit profile snapshot when provided.

    The default remains the import-time canonical profile map for production
    consumers.  Regeneration/parity tooling passes profiles derived from the
    context it is currently auditing, so writing a new context and summarizing
    it cannot accidentally reuse the previous process-global snapshot.
    """

    active_profiles = OPERATION_PORT_PROFILES if profiles is None else profiles
    input_slots: DefaultDict[str, int] = defaultdict(int)
    output_slots: DefaultDict[str, int] = defaultdict(int)
    generic_input_slots = 0
    generic_output_slots = 0

    for operation_type, count in operation_counts.items():
        profile = active_profiles.get(operation_type)
        if not profile:
            continue
        for commodity, slots in profile.input_slots.items():
            input_slots[commodity] += slots * count
        for commodity, slots in profile.output_slots.items():
            output_slots[commodity] += slots * count
        generic_input_slots += profile.generic_input_slots * count
        generic_output_slots += profile.generic_output_slots * count

    return {
        "input_slots": dict(input_slots),
        "output_slots": dict(output_slots),
        "generic_input_slots": generic_input_slots,
        "generic_output_slots": generic_output_slots,
    }


__all__ = [
    "DEFAULT_PREPROCESS_CONTEXT",
    "EPSILON",
    "OPERATION_PORT_PROFILES",
    "OperationPortProfile",
    "aggregate_commodity_rates",
    "aggregate_port_slots",
    "build_operation_port_profiles",
    "count_operations",
    "find_unprofiled_operations",
    "get_operation_port_profile",
]

"""Identity-only shadow of the four existing Benders generation branches."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping, cast

from src.tests.cuts.rule_cut_evolution.family_specs import SHADOW_FAMILY_SPECS_V1
from src.tests.cuts.rule_cut_evolution.rule_semantics import StaticSymbolIdentity


@dataclass(frozen=True, slots=True)
class GenerationBranchSpec:
    family: str
    production_order: int
    generator: StaticSymbolIdentity
    orchestrator: StaticSymbolIdentity
    enablement_gate: str
    preparation_steps: tuple[StaticSymbolIdentity, ...]

    def __post_init__(self) -> None:
        if type(self.family) is not str or not self.family:
            raise ValueError("GenerationBranchSpec.family must be a non-empty exact str")
        if type(self.production_order) is not int or self.production_order < 0:
            raise ValueError("production_order must be a non-negative exact int")
        if type(self.generator) is not StaticSymbolIdentity:
            raise TypeError("generator must be StaticSymbolIdentity")
        if type(self.orchestrator) is not StaticSymbolIdentity:
            raise TypeError("orchestrator must be StaticSymbolIdentity")
        if type(self.enablement_gate) is not str or not self.enablement_gate:
            raise ValueError("enablement_gate must be a non-empty exact str")
        if type(self.preparation_steps) is not tuple:
            raise TypeError("preparation_steps must be an exact tuple")
        if any(type(item) is not StaticSymbolIdentity for item in self.preparation_steps):
            raise TypeError("preparation_steps must contain StaticSymbolIdentity")


_GATES: Final = MappingProxyType(
    {
        "region_capacity": "enabled_family",
        "power_hitting_set": "solution_and_enabled_family_and_target_poses",
        "shape_packing_hall": "enabled_family_and_sot_region_demand_overrides",
        "pattern_nogood": "solution_and_enabled_family_and_full_assignment_literals",
    }
)


def _branch(family: str) -> GenerationBranchSpec:
    generation = SHADOW_FAMILY_SPECS_V1.generation(family)
    if generation.production_typed_order is None:
        raise ValueError(f"{family!r} has no typed generation order")
    if generation.generator.value is None or generation.orchestrator.value is None:
        raise ValueError(f"{family!r} has incomplete typed generation identities")
    return GenerationBranchSpec(
        family=family,
        production_order=generation.production_typed_order,
        generator=cast(StaticSymbolIdentity, generation.generator.value),
        orchestrator=cast(StaticSymbolIdentity, generation.orchestrator.value),
        enablement_gate=_GATES[family],
        preparation_steps=generation.preparation_steps,
    )


TYPED_GENERATION_BRANCHES_V1: Final[Mapping[str, GenerationBranchSpec]] = MappingProxyType(
    {family: _branch(family) for family in SHADOW_FAMILY_SPECS_V1.typed_generation_order}
)
TYPED_GENERATION_ORDER_V1: Final = tuple(
    row.family
    for row in sorted(
        TYPED_GENERATION_BRANCHES_V1.values(),
        key=lambda row: row.production_order,
    )
)

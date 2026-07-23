"""Static, uniform generation invokers for the typed cut families.

Milestone A exposes this module only to shadow consistency tests.  The current
``LBBDController`` still executes its existing per-family branches verbatim;
Milestone B may switch that call site to this closed map only after known-vector
parity is accepted.

The invokers preserve the current separation of roles:

* generators remain untrusted cut producers;
* family plugins remain proof verifiers/plan compilers;
* exact checkers remain independent;
* TCB exceptions are not converted into ordinary cut rejections.

There is no dynamic discovery, entry-point loading, arbitrary Python plugin, or
constraint DSL here.  The map is immutable and statically exhaustive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Protocol, TypeAlias

from src.cuts.lifecycle import BState, Cut, CutLiteral
from src.cuts.oracles.pattern_nogood_oracle import (
    generate_pattern_nogood_cuts,
    lookup_sub_problem_oracle,
    register_sub_problem_oracle,
)
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
from src.cuts.oracles.shape_packing_hall_oracle import (
    compute_sot_region_demand_overrides,
    generate_shape_packing_hall_cuts,
)
from src.search.f5_binding_empty_domain_adapter import (
    ADAPTER_NAME,
    build_binding_empty_domain_adapter,
)


MasterSolution: TypeAlias = Mapping[str, Mapping[str, Any]]


class FamilyGenerationController(Protocol):
    """The existing controller preparation surface consumed by invokers."""

    master: object

    def _framework_target_poses(
        self,
        solution: MasterSolution,
    ) -> list[tuple[str, str]]: ...

    def _framework_full_assignment_literals(
        self,
        solution: MasterSolution,
    ) -> tuple[CutLiteral, ...]: ...


@dataclass(frozen=True, slots=True)
class FamilyGenerationRequest:
    """Uniform immutable input passed to every typed-family invoker."""

    controller: FamilyGenerationController
    state: BState
    solution: MasterSolution | None
    iteration: int

    def __post_init__(self) -> None:
        if not isinstance(self.state, BState):
            raise TypeError("FamilyGenerationRequest.state must be BState")
        if self.solution is not None and not isinstance(self.solution, Mapping):
            raise TypeError(
                "FamilyGenerationRequest.solution must be a mapping or None"
            )
        if type(self.iteration) is not int:
            raise TypeError("FamilyGenerationRequest.iteration must be an exact int")


FamilyGenerationInvoker: TypeAlias = Callable[[FamilyGenerationRequest], list[Cut]]


def invoke_region_capacity_generation(
    request: FamilyGenerationRequest,
) -> list[Cut]:
    """Mirror the current F1 generation branch exactly."""

    return generate_region_capacity_cuts(
        request.state,
        request.state.canonical_rules or {},
        iter_index=request.iteration,
    )


def invoke_power_hitting_set_generation(
    request: FamilyGenerationRequest,
) -> list[Cut]:
    """Mirror the current solution-gated F7 generation branch exactly."""

    if request.solution is None:
        return []
    target_poses = request.controller._framework_target_poses(request.solution)
    if not target_poses:
        return []
    return generate_power_hitting_set_cuts(
        request.state,
        target_poses=target_poses,
        iter_index=request.iteration,
    )


def invoke_shape_packing_hall_generation(
    request: FamilyGenerationRequest,
) -> list[Cut]:
    """Mirror the current source-of-truth F6 override branch exactly."""

    region_demand_overrides = compute_sot_region_demand_overrides(request.state)
    if not region_demand_overrides:
        return []
    return generate_shape_packing_hall_cuts(
        request.state,
        region_demand_overrides=region_demand_overrides,
        iter_index=request.iteration,
    )


def invoke_pattern_nogood_generation(
    request: FamilyGenerationRequest,
) -> list[Cut]:
    """Mirror the current solution-gated F5 adapter branch exactly."""

    if request.solution is None:
        return []
    adapter = lookup_sub_problem_oracle(ADAPTER_NAME)
    if adapter is None:
        adapter = build_binding_empty_domain_adapter(
            getattr(request.controller.master, "_mandatory_groups", None) or []
        )
        register_sub_problem_oracle(adapter)
    full_literals = request.controller._framework_full_assignment_literals(
        request.solution
    )
    if not full_literals:
        return []
    return generate_pattern_nogood_cuts(
        request.state,
        sub_problem_oracle=adapter,
        full_assignment_literals=full_literals,
        iter_index=request.iteration,
    )


TYPED_FAMILY_GENERATION_INVOKERS_V1: Final[
    Mapping[str, FamilyGenerationInvoker]
] = MappingProxyType(
    {
        "region_capacity": invoke_region_capacity_generation,
        "power_hitting_set": invoke_power_hitting_set_generation,
        "shape_packing_hall": invoke_shape_packing_hall_generation,
        "pattern_nogood": invoke_pattern_nogood_generation,
    }
)
TYPED_FAMILY_GENERATION_ORDER_V1: Final = tuple(
    TYPED_FAMILY_GENERATION_INVOKERS_V1
)


def typed_family_generation_invoker(
    family: str,
) -> FamilyGenerationInvoker:
    """Resolve one statically registered typed invoker or fail closed."""

    if type(family) is not str or not family or family.strip() != family:
        raise KeyError("typed family generation invoker requires a stable family ID")
    try:
        return TYPED_FAMILY_GENERATION_INVOKERS_V1[family]
    except KeyError as exc:
        raise KeyError(
            f"unknown typed family generation invoker: {family!r}"
        ) from exc


__all__ = [
    "FamilyGenerationController",
    "FamilyGenerationInvoker",
    "FamilyGenerationRequest",
    "MasterSolution",
    "TYPED_FAMILY_GENERATION_INVOKERS_V1",
    "TYPED_FAMILY_GENERATION_ORDER_V1",
    "invoke_pattern_nogood_generation",
    "invoke_power_hitting_set_generation",
    "invoke_region_capacity_generation",
    "invoke_shape_packing_hall_generation",
    "typed_family_generation_invoker",
]

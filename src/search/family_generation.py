"""Static, uniform generation invokers for the typed cut families.

Milestone B routes ``LBBDController`` through this closed map in the manifest's
declared order.  Each invoker retains the former branch's internal gates and
imports its oracle/helper at invocation time, preserving the established
monkeypatch and import-timing seams.

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

from src.cuts.family_specs import (
    GenerationSurface,
    PRODUCTION_FAMILY_MANIFEST_V1,
    StaticSymbolIdentity,
)
from src.cuts.lifecycle import BState, Cut, CutLiteral


MasterSolution: TypeAlias = Mapping[str, Mapping[str, Any]]


class FamilyGenerationController(Protocol):
    """The existing controller preparation surface consumed by invokers."""

    @property
    def master(self) -> object: ...

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

    from src.cuts.oracles.region_capacity_oracle import (
        generate_region_capacity_cuts,
    )

    generator: Callable[..., list[Cut]] = generate_region_capacity_cuts
    return generator(
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
    from src.cuts.oracles.power_cover_oracle import (
        generate_power_hitting_set_cuts,
    )

    generator: Callable[..., list[Cut]] = generate_power_hitting_set_cuts
    return generator(
        request.state,
        target_poses=target_poses,
        iter_index=request.iteration,
    )


def invoke_shape_packing_hall_generation(
    request: FamilyGenerationRequest,
) -> list[Cut]:
    """Mirror the current source-of-truth F6 override branch exactly."""

    from src.cuts.oracles.shape_packing_hall_oracle import (
        compute_sot_region_demand_overrides,
    )

    region_demand_overrides = compute_sot_region_demand_overrides(request.state)
    if not region_demand_overrides:
        return []
    from src.cuts.oracles.shape_packing_hall_oracle import (
        generate_shape_packing_hall_cuts,
    )

    generator: Callable[..., list[Cut]] = generate_shape_packing_hall_cuts
    return generator(
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
    from src.cuts.oracles.pattern_nogood_oracle import (
        generate_pattern_nogood_cuts,
        lookup_sub_problem_oracle,
        register_sub_problem_oracle,
    )
    from src.search.f5_binding_empty_domain_adapter import (
        ADAPTER_NAME,
        build_binding_empty_domain_adapter,
    )

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
    generator: Callable[..., list[Cut]] = generate_pattern_nogood_cuts
    return generator(
        request.state,
        sub_problem_oracle=adapter,
        full_assignment_literals=full_literals,
        iter_index=request.iteration,
    )


@dataclass(frozen=True, slots=True)
class _StaticInvokerRegistration:
    family: str
    invoker: FamilyGenerationInvoker
    generator_identity: StaticSymbolIdentity


_TYPED_FAMILY_GENERATION_REGISTRATIONS_V1: Final = (
    _StaticInvokerRegistration(
        family="region_capacity",
        invoker=invoke_region_capacity_generation,
        generator_identity=StaticSymbolIdentity(
            module="src.cuts.oracles.region_capacity_oracle",
            qualname="generate_region_capacity_cuts",
        ),
    ),
    _StaticInvokerRegistration(
        family="power_hitting_set",
        invoker=invoke_power_hitting_set_generation,
        generator_identity=StaticSymbolIdentity(
            module="src.cuts.oracles.power_cover_oracle",
            qualname="generate_power_hitting_set_cuts",
        ),
    ),
    _StaticInvokerRegistration(
        family="shape_packing_hall",
        invoker=invoke_shape_packing_hall_generation,
        generator_identity=StaticSymbolIdentity(
            module="src.cuts.oracles.shape_packing_hall_oracle",
            qualname="generate_shape_packing_hall_cuts",
        ),
    ),
    _StaticInvokerRegistration(
        family="pattern_nogood",
        invoker=invoke_pattern_nogood_generation,
        generator_identity=StaticSymbolIdentity(
            module="src.cuts.oracles.pattern_nogood_oracle",
            qualname="generate_pattern_nogood_cuts",
        ),
    ),
)

TYPED_FAMILY_GENERATION_INVOKERS_V1: Final[
    Mapping[str, FamilyGenerationInvoker]
] = MappingProxyType(
    {
        registration.family: registration.invoker
        for registration in _TYPED_FAMILY_GENERATION_REGISTRATIONS_V1
    }
)
TYPED_FAMILY_GENERATION_ORDER_V1: Final = (
    PRODUCTION_FAMILY_MANIFEST_V1.typed_generation_order
)


def _validate_static_invoker_map_v1() -> None:
    """Fail import if the closed map drifts from the versioned manifest."""

    registrations = {
        registration.family: registration
        for registration in _TYPED_FAMILY_GENERATION_REGISTRATIONS_V1
    }
    expected_order = PRODUCTION_FAMILY_MANIFEST_V1.typed_generation_order
    if tuple(registrations) != expected_order:
        raise RuntimeError("typed family invoker registration order differs from manifest")
    if tuple(TYPED_FAMILY_GENERATION_INVOKERS_V1) != expected_order:
        raise RuntimeError("typed family invoker map order differs from manifest")

    for index, family in enumerate(expected_order):
        generation = PRODUCTION_FAMILY_MANIFEST_V1.generation(family)
        if generation.surface is not GenerationSurface.TYPED_ATTACH:
            raise RuntimeError(
                f"typed family invoker {family!r} lacks typed-attach manifest stage"
            )
        if generation.production_typed_order != index:
            raise RuntimeError(
                f"typed family invoker {family!r} has inconsistent manifest order"
            )

        generator_ref = generation.generator.require(
            family=family,
            capability="generator",
        )
        if type(generator_ref) is not StaticSymbolIdentity:
            raise RuntimeError(
                f"typed family invoker {family!r} lacks a static generator identity"
            )
        registration = registrations[family]
        if generator_ref != registration.generator_identity:
            raise RuntimeError(
                f"typed family invoker {family!r} generator identity differs from manifest"
            )

        invoker_identity = generation.generation_invoker.require(
            family=family,
            capability="generation invoker",
        )
        if type(invoker_identity) is not StaticSymbolIdentity:
            raise RuntimeError(
                f"typed family invoker {family!r} lacks a static invoker identity"
            )
        invoker = TYPED_FAMILY_GENERATION_INVOKERS_V1[family]
        actual_identity = StaticSymbolIdentity(
            module=invoker.__module__,
            qualname=invoker.__qualname__,
        )
        if actual_identity != invoker_identity:
            raise RuntimeError(
                f"typed family invoker {family!r} callable identity differs from manifest"
            )


_validate_static_invoker_map_v1()


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

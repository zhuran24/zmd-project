"""Pure-Python parity tests for the shadow typed generation invokers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

import src.search.family_generation as generation_module
from src.cuts.lifecycle import BState, Cut, CutLiteral
from src.search.family_generation import (
    FamilyGenerationRequest,
    TYPED_FAMILY_GENERATION_INVOKERS_V1,
    TYPED_FAMILY_GENERATION_ORDER_V1,
    typed_family_generation_invoker,
)


class _Controller:
    def __init__(self) -> None:
        self.master: object = SimpleNamespace(
            _mandatory_groups=[
                {"group_id": "g1", "operation_type": "op1"},
            ]
        )
        self.target_calls: list[object] = []
        self.literal_calls: list[object] = []
        self.target_poses: list[tuple[str, str]] = [("g1", "p1")]
        self.full_literals = cast(tuple[CutLiteral, ...], (object(),))

    def _framework_target_poses(
        self,
        solution: generation_module.MasterSolution,
    ) -> list[tuple[str, str]]:
        self.target_calls.append(solution)
        return self.target_poses

    def _framework_full_assignment_literals(
        self,
        solution: generation_module.MasterSolution,
    ) -> tuple[CutLiteral, ...]:
        self.literal_calls.append(solution)
        return self.full_literals


def _request(
    *,
    solution: generation_module.MasterSolution | None = None,
) -> FamilyGenerationRequest:
    return FamilyGenerationRequest(
        controller=_Controller(),
        state=BState(groups={}, canonical_rules={"rule": "value"}),
        solution=solution,
        iteration=7,
    )


def _sentinel_cuts() -> list[Cut]:
    return cast(list[Cut], [object()])


def test_static_invoker_map_is_closed_ordered_and_fail_closed() -> None:
    assert TYPED_FAMILY_GENERATION_ORDER_V1 == (
        "region_capacity",
        "power_hitting_set",
        "shape_packing_hall",
        "pattern_nogood",
    )
    assert tuple(TYPED_FAMILY_GENERATION_INVOKERS_V1) == (
        TYPED_FAMILY_GENERATION_ORDER_V1
    )
    for family, invoker in TYPED_FAMILY_GENERATION_INVOKERS_V1.items():
        assert typed_family_generation_invoker(family) is invoker

    with pytest.raises(KeyError, match="unknown typed family"):
        typed_family_generation_invoker("unknown")
    with pytest.raises(KeyError, match="stable family ID"):
        typed_family_generation_invoker(" region_capacity")
    with pytest.raises(TypeError):
        TYPED_FAMILY_GENERATION_INVOKERS_V1["new"] = (  # type: ignore[index]
            generation_module.invoke_region_capacity_generation
        )


def test_request_rejects_wrong_state_solution_and_iteration_types() -> None:
    request = _request()
    with pytest.raises(TypeError, match="state must be BState"):
        FamilyGenerationRequest(
            controller=request.controller,
            state=object(),  # type: ignore[arg-type]
            solution=None,
            iteration=1,
        )
    with pytest.raises(TypeError, match="mapping or None"):
        FamilyGenerationRequest(
            controller=request.controller,
            state=request.state,
            solution=[],  # type: ignore[arg-type]
            iteration=1,
        )
    with pytest.raises(TypeError, match="exact int"):
        FamilyGenerationRequest(
            controller=request.controller,
            state=request.state,
            solution=None,
            iteration=True,
        )


def test_region_capacity_invoker_preserves_current_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    expected = _sentinel_cuts()
    observed: dict[str, object] = {}

    def fake_generator(
        state: BState,
        canonical_rules: dict[str, Any],
        *,
        iter_index: int,
    ) -> list[Cut]:
        observed.update(
            state=state,
            canonical_rules=canonical_rules,
            iter_index=iter_index,
        )
        return expected

    monkeypatch.setattr(
        generation_module,
        "generate_region_capacity_cuts",
        fake_generator,
    )
    assert generation_module.invoke_region_capacity_generation(request) is expected
    assert observed == {
        "state": request.state,
        "canonical_rules": request.state.canonical_rules,
        "iter_index": request.iteration,
    }


def test_power_hitting_set_invoker_preserves_solution_gate_and_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    no_solution = _request()
    expected = _sentinel_cuts()
    generator_calls: list[tuple[object, object, int]] = []

    def fake_generator(
        state: BState,
        *,
        target_poses: list[tuple[str, str]],
        iter_index: int,
    ) -> list[Cut]:
        generator_calls.append((state, target_poses, iter_index))
        return expected

    monkeypatch.setattr(
        generation_module,
        "generate_power_hitting_set_cuts",
        fake_generator,
    )
    assert generation_module.invoke_power_hitting_set_generation(no_solution) == []
    assert generator_calls == []

    solution = {"i1": {"pose_idx": 0}}
    request = _request(solution=solution)
    controller = cast(_Controller, request.controller)
    assert generation_module.invoke_power_hitting_set_generation(request) is expected
    assert controller.target_calls == [solution]
    assert generator_calls == [
        (request.state, controller.target_poses, request.iteration)
    ]

    controller.target_poses = []
    assert generation_module.invoke_power_hitting_set_generation(request) == []
    assert len(generator_calls) == 1


def test_shape_packing_invoker_preserves_preparation_gate_and_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    expected = _sentinel_cuts()
    overrides: dict[tuple[str, str], int] = {("g1", "left_baseline"): 1}
    generator_calls: list[tuple[object, object, int]] = []

    monkeypatch.setattr(
        generation_module,
        "compute_sot_region_demand_overrides",
        lambda state: overrides,
    )

    def fake_generator(
        state: BState,
        *,
        region_demand_overrides: dict[tuple[str, str], int],
        iter_index: int,
    ) -> list[Cut]:
        generator_calls.append((state, region_demand_overrides, iter_index))
        return expected

    monkeypatch.setattr(
        generation_module,
        "generate_shape_packing_hall_cuts",
        fake_generator,
    )
    assert generation_module.invoke_shape_packing_hall_generation(request) is expected
    assert generator_calls == [(request.state, overrides, request.iteration)]

    monkeypatch.setattr(
        generation_module,
        "compute_sot_region_demand_overrides",
        lambda state: {},
    )
    assert generation_module.invoke_shape_packing_hall_generation(request) == []
    assert len(generator_calls) == 1


def test_pattern_nogood_invoker_preserves_adapter_and_literal_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solution = {"i1": {"pose_idx": 0}}
    request = _request(solution=solution)
    controller = cast(_Controller, request.controller)
    expected = _sentinel_cuts()
    adapter = object()
    built_from: list[object] = []
    registered: list[object] = []
    generator_calls: list[tuple[object, object, object, int]] = []

    monkeypatch.setattr(
        generation_module,
        "lookup_sub_problem_oracle",
        lambda name: None,
    )

    def fake_build(mandatory_groups: object) -> object:
        built_from.append(mandatory_groups)
        return adapter

    monkeypatch.setattr(
        generation_module,
        "build_binding_empty_domain_adapter",
        fake_build,
    )
    monkeypatch.setattr(
        generation_module,
        "register_sub_problem_oracle",
        registered.append,
    )

    def fake_generator(
        state: BState,
        *,
        sub_problem_oracle: object,
        full_assignment_literals: tuple[CutLiteral, ...],
        iter_index: int,
    ) -> list[Cut]:
        generator_calls.append(
            (
                state,
                sub_problem_oracle,
                full_assignment_literals,
                iter_index,
            )
        )
        return expected

    monkeypatch.setattr(
        generation_module,
        "generate_pattern_nogood_cuts",
        fake_generator,
    )
    assert generation_module.invoke_pattern_nogood_generation(request) is expected
    assert built_from == [getattr(controller.master, "_mandatory_groups")]
    assert registered == [adapter]
    assert controller.literal_calls == [solution]
    assert generator_calls == [
        (
            request.state,
            adapter,
            controller.full_literals,
            request.iteration,
        )
    ]

    controller.full_literals = ()
    assert generation_module.invoke_pattern_nogood_generation(request) == []
    assert len(generator_calls) == 1
    assert generation_module.invoke_pattern_nogood_generation(_request()) == []


def test_invoker_does_not_translate_tcb_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> list[Cut]:
        raise RuntimeError("tcb-probe")

    monkeypatch.setattr(
        generation_module,
        "generate_region_capacity_cuts",
        fail,
    )
    with pytest.raises(RuntimeError, match="tcb-probe"):
        generation_module.invoke_region_capacity_generation(_request())

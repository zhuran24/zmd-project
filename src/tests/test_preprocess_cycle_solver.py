from __future__ import annotations

import copy
from fractions import Fraction

import pytest

from src.interchange.preprocess_context import load_default_preprocess_context, solve_cycle_group_exact


def test_buckwheat_cycle_solver_matches_frozen_business_truth() -> None:
    context = load_default_preprocess_context()
    solution = solve_cycle_group_exact(
        context,
        "buckwheat_cycle",
        {"buckwheat": Fraction(11, 2), "buckwheat_seed": Fraction(0)},
    )

    assert solution["planter_buckwheat"] == Fraction(11, 1)
    assert solution["seed_collector_buckwheat"] == Fraction(11, 2)


def test_sandleaf_cycle_solver_matches_frozen_business_truth() -> None:
    context = load_default_preprocess_context()
    solution = solve_cycle_group_exact(
        context,
        "sandleaf_cycle",
        {"sandleaf": Fraction(21, 2), "sandleaf_seed": Fraction(0)},
    )

    assert solution["planter_sandleaf"] == Fraction(21, 1)
    assert solution["seed_collector_sandleaf"] == Fraction(21, 2)


def test_cycle_solver_rejects_positive_external_demand_for_non_export_internal_commodity() -> None:
    context = load_default_preprocess_context()

    with pytest.raises(ValueError, match="net_export"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat_seed": Fraction(1)})


def test_cycle_solver_rejects_unvalidated_context_with_cycle_recipe_io_outside_internal() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.recipes["planter_buckwheat"].inputs["source_ore"] = Fraction(1)

    with pytest.raises(ValueError, match="outside commodities: planter_buckwheat: source_ore"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


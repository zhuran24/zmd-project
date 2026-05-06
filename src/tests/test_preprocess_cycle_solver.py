from __future__ import annotations

from fractions import Fraction

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

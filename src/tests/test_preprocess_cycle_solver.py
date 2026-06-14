from __future__ import annotations

import copy
from dataclasses import replace
from fractions import Fraction

import pytest

from src.interchange.preprocess_context import (
    CommodityRole,
    PreprocessRecipe,
    load_default_preprocess_context,
    solve_cycle_group_exact,
)


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


def test_cycle_solver_rejects_unvalidated_context_with_outside_producer_for_cycle_internal_output() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.recipes["synthetic_buckwheat"] = PreprocessRecipe(
        recipe_id="synthetic_buckwheat",
        template="manufacturing_3x3",
        ticks_per_cycle=1,
        inputs={"source_ore": Fraction(1)},
        outputs={"buckwheat": Fraction(1)},
    )

    with pytest.raises(ValueError, match="synthetic_buckwheat.*outside cycle group 'buckwheat_cycle'"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


def test_cycle_solver_rejects_unvalidated_context_with_internal_role_group_mismatch() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.commodity_roles["buckwheat"] = replace(
        context.commodity_roles["buckwheat"],
        cycle_group="sandleaf_cycle",
    )

    with pytest.raises(ValueError, match="cycle_group 'sandleaf_cycle'.*expected 'buckwheat_cycle'"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


def test_cycle_solver_rejects_unvalidated_context_with_role_declaring_group_but_missing_from_internal() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.commodity_roles["ghost_spore"] = CommodityRole(
        commodity_id="ghost_spore",
        source_kind="cycle_internal",
        sink_kind="none",
        cycle_group="buckwheat_cycle",
    )

    with pytest.raises(ValueError, match="ghost_spore.*internal_commodities"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


def test_cycle_solver_rejects_unvalidated_context_with_role_key_identity_mismatch() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.commodity_roles["buckwheat"] = CommodityRole(
        commodity_id="buckwheat_seed",
        source_kind="cycle_internal",
        sink_kind="none",
        cycle_group="buckwheat_cycle",
    )

    with pytest.raises(ValueError, match=r"commodity_roles key 'buckwheat'.*role\.commodity_id 'buckwheat_seed'"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


def test_cycle_solver_rejects_unvalidated_context_with_recipe_key_identity_mismatch() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.recipes["planter_buckwheat"] = replace(
        context.recipes["planter_buckwheat"],
        recipe_id="alias_planter_buckwheat",
    )

    with pytest.raises(ValueError, match=r"preprocess recipes key 'planter_buckwheat'.*recipe\.recipe_id 'alias_planter_buckwheat'"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


def test_cycle_solver_rejects_unvalidated_context_with_nonpositive_cycle_recipe_amount() -> None:
    context = copy.deepcopy(load_default_preprocess_context())
    context.recipes["seed_collector_buckwheat"].outputs["buckwheat_seed"] = Fraction(0)

    with pytest.raises(ValueError, match="seed_collector_buckwheat.*output amount.*buckwheat_seed.*must be > 0"):
        solve_cycle_group_exact(context, "buckwheat_cycle", {"buckwheat": Fraction(1)})


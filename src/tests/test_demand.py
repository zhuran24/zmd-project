"""Tests for the pure-Python demand/preprocess chain."""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Tuple

import pytest

from src.preprocess.demand_solver import (
    ceil_machine_count,
    generate_ceil_machine_counts,
    generate_generic_io_requirements,
    generate_port_budget,
    normalize_artifact_number,
    normalize_json_numbers,
    save_preprocessed_artifacts,
    solve_demands,
)
from src.preprocess.instance_builder import build_manufacturing_instances, load_machine_counts


@pytest.fixture
def solved_data() -> Tuple[Dict[str, float], Dict[str, float], Dict[str, int], Dict[str, Any]]:
    flows, fractional = solve_demands()
    counts = generate_ceil_machine_counts(fractional)
    budget = generate_port_budget(flows)
    return flows, fractional, counts, budget



def test_load_machine_counts_rejects_duplicate_json_keys(tmp_path) -> None:
    path = tmp_path / "machine_counts.json"
    path.write_text('{"crusher_source": 18, "crusher_source": 1}', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON key: crusher_source"):
        load_machine_counts(path)


def test_load_machine_counts_rejects_nonfinite_json_constants(tmp_path) -> None:
    path = tmp_path / "machine_counts.json"
    path.write_text('{"crusher_source": NaN}', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON constant: NaN"):
        load_machine_counts(path)


def test_load_machine_counts_rejects_overflow_json_numbers(tmp_path) -> None:
    path = tmp_path / "machine_counts.json"
    path.write_text('{"crusher_source": 1e309}', encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON number: 1e309"):
        load_machine_counts(path)


@pytest.mark.parametrize("bad_count", [True, 1.5, "2"])
def test_build_manufacturing_instances_rejects_loose_direct_counts(bad_count) -> None:
    with pytest.raises(TypeError, match="machine_counts.packaging_battery must be an integer count"):
        build_manufacturing_instances({"packaging_battery": bad_count})


def test_build_manufacturing_instances_rejects_negative_direct_counts() -> None:
    with pytest.raises(ValueError, match="machine_counts.packaging_battery must be non-negative"):
        build_manufacturing_instances({"packaging_battery": -1})


def test_target_flows_accuracy(solved_data) -> None:
    flows, _, _, _ = solved_data
    assert math.isclose(flows["valley_battery"], 0.6)
    assert math.isclose(flows["qiaoyu_capsule"], 0.55)


def test_fractional_to_ceil_rounding_rule(solved_data) -> None:
    _, fractional, counts, _ = solved_data

    assert math.isclose(fractional["filling_capsule"], 2.75)
    assert counts["filling_capsule"] == 3

    assert math.isclose(fractional["crusher_sandleaf"], 10.5)
    assert counts["crusher_sandleaf"] == 11

    assert math.isclose(fractional["molding_bottle"], 5.5)
    assert counts["molding_bottle"] == 6


def test_agricultural_closed_loop_conservation(solved_data) -> None:
    _, fractional, _, _ = solved_data

    assert math.isclose(
        fractional["planter_buckwheat"],
        fractional["seed_collector_buckwheat"] * 2.0,
    )
    assert math.isclose(
        fractional["planter_sandleaf"],
        fractional["seed_collector_sandleaf"] * 2.0,
    )


def test_the_52_port_miracle(solved_data) -> None:
    _, _, _, budget = solved_data
    miracle = budget["miracle_52_budget"]

    assert math.isclose(float(miracle["blue_iron_ore_inputs_required"]), 34.0)
    assert math.isclose(float(miracle["source_ore_inputs_required"]), 18.0)
    assert math.isclose(float(miracle["total_boundary_and_core_ports_required"]), 52.0)
    assert budget["status"] == "FEASIBLE"


def test_absolute_total_machine_count(solved_data) -> None:
    _, _, counts, _ = solved_data
    assert sum(counts.values()) == 219


def test_full_recipe_chain_completeness(solved_data) -> None:
    _, _, counts, _ = solved_data
    produced_items = {
        "valley_battery": "packaging_battery",
        "qiaoyu_capsule": "filling_capsule",
        "steel_part": "parts_maker",
        "steel_bottle": "molding_bottle",
        "dense_source_powder": "grinder_dense_source",
        "fine_buckwheat_powder": "grinder_fine_buckwheat",
        "steel_block": "refinery_steel",
        "dense_blue_iron_powder": "grinder_dense_blue_iron",
        "source_powder": "crusher_source",
        "buckwheat_powder": "crusher_buckwheat",
        "sandleaf_powder": "crusher_sandleaf",
        "blue_iron_powder": "crusher_blue_iron",
        "blue_iron_block": "refinery_blue_iron",
    }
    for commodity, machine_type in produced_items.items():
        assert machine_type in counts, f"{commodity} missing producer machine {machine_type}"
        assert counts[machine_type] >= 1


def test_numeric_normalization_adversarial_inputs() -> None:
    assert normalize_artifact_number(0.9999999999) == 1
    assert normalize_artifact_number(1.0000000001) == 1
    assert ceil_machine_count(1.00000001) == 2
    assert normalize_json_numbers(
        {
            "a": 18.000000000000004,
            "b": [0.9999999999, 1.0000000001, 1.25],
        }
    ) == {
        "a": 18,
        "b": [1, 1, 1.25],
    }


def test_save_preprocessed_artifacts_cleans_binary_noise(tmp_path) -> None:
    flows = {
        "source_ore": 18.000000000000004,
        "blue_iron_ore": 33.99999999999999,
        "valley_battery": 0.6,
        "qiaoyu_capsule": 0.55,
    }
    machine_counts = {"alpha": 1, "beta": 2}
    port_budget = generate_port_budget(flows)
    generic_io_requirements = generate_generic_io_requirements(flows, port_budget)

    save_preprocessed_artifacts(
        output_dir=tmp_path,
        flows=flows,
        machine_counts=machine_counts,
        port_budget=port_budget,
        generic_io_requirements=generic_io_requirements,
    )

    commodity_demands = json.loads((tmp_path / "commodity_demands.json").read_text(encoding="utf-8"))
    saved_budget = json.loads((tmp_path / "port_budget.json").read_text(encoding="utf-8"))

    assert commodity_demands["source_ore"] == 18
    assert commodity_demands["blue_iron_ore"] == 34
    assert saved_budget["miracle_52_budget"]["source_ore_inputs_required"] == 18
    assert saved_budget["miracle_52_budget"]["blue_iron_ore_inputs_required"] == 34
    assert saved_budget["miracle_52_budget"]["total_boundary_and_core_ports_required"] == 52

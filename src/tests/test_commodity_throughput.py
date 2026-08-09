"""Tests for commodity throughput helper (Phase 3C P1 #9 hint 2 stage 1)."""

from __future__ import annotations

from src.search.commodity_throughput import (
    classify_commodity_flow,
    compute_commodity_throughput,
)


def test_compute_throughput_aggregates_outputs_across_recipes() -> None:
    rules = {
        "recipes": {
            "make_a": {
                "ticks_per_cycle": 5,
                "inputs": {"raw_a": 2},
                "outputs": {"item_a": 1},
            },
            "make_b": {
                "ticks_per_cycle": 10,
                "inputs": {"item_a": 4},
                "outputs": {"item_b": 1},
            },
        }
    }
    instances = [
        {"operation_type": "make_a"},
        {"operation_type": "make_a"},
        {"operation_type": "make_b"},
        {"operation_type": "boundary_io"},  # no recipe → ignored
    ]

    result = compute_commodity_throughput(rules, instances)

    # raw_a: consumed only, 2 instances of make_a × 2/5 = 0.8 per tick
    assert abs(result["raw_a"]["consumption_rate"] - 0.8) < 1e-9
    assert result["raw_a"]["production_rate"] == 0.0
    assert abs(result["raw_a"]["net_flow"] - (-0.8)) < 1e-9

    # item_a: produced 2 × 1/5 = 0.4, consumed 1 × 4/10 = 0.4 → balanced
    assert abs(result["item_a"]["production_rate"] - 0.4) < 1e-9
    assert abs(result["item_a"]["consumption_rate"] - 0.4) < 1e-9
    assert abs(result["item_a"]["net_flow"]) < 1e-9

    # item_b: produced only, 1 × 1/10 = 0.1
    assert abs(result["item_b"]["production_rate"] - 0.1) < 1e-9
    assert result["item_b"]["consumption_rate"] == 0.0
    assert abs(result["item_b"]["net_flow"] - 0.1) < 1e-9


def test_compute_throughput_skips_unknown_operation_types() -> None:
    rules = {"recipes": {"make_a": {"ticks_per_cycle": 5, "outputs": {"a": 1}}}}
    instances = [
        {"operation_type": "make_a"},
        {"operation_type": "unknown_recipe"},
        {"operation_type": "boundary_io"},
        {},  # no operation_type
    ]

    result = compute_commodity_throughput(rules, instances)

    # only make_a counted (1 instance, 1/5 = 0.2)
    assert "a" in result
    assert abs(result["a"]["production_rate"] - 0.2) < 1e-9


def test_compute_throughput_handles_zero_ticks_per_cycle() -> None:
    # Pathological recipe with ticks_per_cycle=0 must not raise (skipped)
    rules = {"recipes": {"broken": {"ticks_per_cycle": 0, "outputs": {"x": 1}}}}
    instances = [{"operation_type": "broken"}]

    result = compute_commodity_throughput(rules, instances)

    assert result == {}  # no commodities recorded


def test_classify_high_low_balanced() -> None:
    throughput = {
        "high_prod": {"production_rate": 10.0, "consumption_rate": 1.0, "net_flow": 9.0},
        "low_prod": {"production_rate": 1.0, "consumption_rate": 10.0, "net_flow": -9.0},
        "balanced": {"production_rate": 5.0, "consumption_rate": 5.0, "net_flow": 0.0},
        "near_balanced": {"production_rate": 5.0, "consumption_rate": 4.6, "net_flow": 0.4},
    }

    classification = classify_commodity_flow(throughput, threshold_ratio=0.1)

    assert classification["high_prod"] == "high_prod_low_demand"
    assert classification["low_prod"] == "low_prod_high_demand"
    assert classification["balanced"] == "balanced"
    # near_balanced: scale=5.0, threshold=0.5, |0.4| < 0.5 → balanced
    assert classification["near_balanced"] == "balanced"


def test_classify_threshold_ratio_strictness() -> None:
    throughput = {
        "marginal": {"production_rate": 10.0, "consumption_rate": 8.5, "net_flow": 1.5},
    }
    # threshold_ratio=0.1 → threshold=1.0, net=1.5 > 1.0 → high_prod_low_demand
    assert classify_commodity_flow(throughput, threshold_ratio=0.1)["marginal"] == "high_prod_low_demand"
    # threshold_ratio=0.2 → threshold=2.0, net=1.5 < 2.0 → balanced
    assert classify_commodity_flow(throughput, threshold_ratio=0.2)["marginal"] == "balanced"


def test_real_canonical_rules_smoke() -> None:
    """Smoke test against the actual project canonical_rules.json +
    mandatory_exact_instances.json. Verifies the helper runs without
    errors on real data and returns sensible counts.
    """
    import json
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    rules = json.loads((project_root / "rules" / "canonical_rules.json").read_text(encoding="utf-8"))
    instances = json.loads((project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").read_text(encoding="utf-8"))

    throughput = compute_commodity_throughput(rules, instances)
    classification = classify_commodity_flow(throughput)

    # Sanity: at least one commodity in each direction is expected
    # (otherwise the "balanced production line" assumption upstream is broken)
    high_count = sum(1 for c in classification.values() if c == "high_prod_low_demand")
    low_count = sum(1 for c in classification.values() if c == "low_prod_high_demand")
    balanced_count = sum(1 for c in classification.values() if c == "balanced")

    # Total should equal the number of distinct commodities seen
    assert high_count + low_count + balanced_count == len(classification)
    # Real project should have non-trivial commodity counts
    assert len(classification) >= 3

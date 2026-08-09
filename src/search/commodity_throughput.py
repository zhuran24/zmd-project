"""Commodity production / consumption rate computation.

Pure helper computing per-commodity throughput from project rules
(canonical_rules.json) and the mandatory-instance set
(mandatory_exact_instances.json). Used by Phase 3C P1 #9 hint 2
(storage-box overload separation) and any future precheck/audit that
needs commodity flow classification.

This module has NO model side effect — it returns plain dicts. Wiring
the result into a CP-SAT model is the caller's responsibility.

References:
- R10 audit transcript a9d8ba25a087fb653 (player consensus on storage
  box overload)
- Round 12 implementation blueprint a3f5ff65abb3f99fa (verdict SAFE
  for the throughput computation; RISKY only when combined with hard
  nogoods, which require a fallback ladder elsewhere)
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Mapping, Sequence

CommodityClassification = Dict[str, str]  # commodity -> "high_prod_low_demand" | "low_prod_high_demand" | "balanced"


def _instance_counts_by_operation_type(instances: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for inst in instances:
        operation_type = inst.get("operation_type")
        if operation_type:
            counter[str(operation_type)] += 1
    return dict(counter)


def compute_commodity_throughput(
    rules: Mapping[str, Any],
    instances: Sequence[Mapping[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Return per-commodity production_rate / consumption_rate / net_flow.

    Rates are aggregated over all mandatory instances whose operation_type
    matches a recipe key in rules['recipes']. Operation types without a
    matching recipe (boundary_io, protocol_core, power_pole, etc.) are
    skipped silently — they don't produce or consume commodities.

    Returns:
        Dict mapping commodity_id -> {
            "production_rate": float (units per tick),
            "consumption_rate": float,
            "net_flow": float (production - consumption),
        }
    """
    recipes = dict(rules.get("recipes", {}))
    operation_counts = _instance_counts_by_operation_type(instances)

    production: Dict[str, float] = defaultdict(float)
    consumption: Dict[str, float] = defaultdict(float)

    for operation_type, count in operation_counts.items():
        recipe = recipes.get(operation_type)
        if not isinstance(recipe, Mapping):
            continue
        ticks = float(recipe.get("ticks_per_cycle", 1))
        if ticks <= 0.0:
            continue
        for commodity, amount in dict(recipe.get("outputs", {})).items():
            production[str(commodity)] += float(amount) * float(count) / ticks
        for commodity, amount in dict(recipe.get("inputs", {})).items():
            consumption[str(commodity)] += float(amount) * float(count) / ticks

    all_commodities = set(production) | set(consumption)
    return {
        c: {
            "production_rate": production.get(c, 0.0),
            "consumption_rate": consumption.get(c, 0.0),
            "net_flow": production.get(c, 0.0) - consumption.get(c, 0.0),
        }
        for c in all_commodities
    }


def classify_commodity_flow(
    throughput: Mapping[str, Mapping[str, float]],
    *,
    threshold_ratio: float = 0.1,
) -> CommodityClassification:
    """Classify each commodity into high_prod_low_demand /
    low_prod_high_demand / balanced based on net_flow magnitude.

    threshold = max(production_rate, consumption_rate) * threshold_ratio.
    A commodity with abs(net_flow) below the threshold is classified
    "balanced" — not a candidate for nogood pairing.

    Returns:
        Dict commodity_id -> classification_label.
    """
    classification: CommodityClassification = {}
    for commodity, stats in throughput.items():
        prod = float(stats.get("production_rate", 0.0))
        cons = float(stats.get("consumption_rate", 0.0))
        net = float(stats.get("net_flow", prod - cons))
        scale = max(prod, cons)
        threshold = scale * threshold_ratio
        if net > threshold:
            classification[commodity] = "high_prod_low_demand"
        elif net < -threshold:
            classification[commodity] = "low_prod_high_demand"
        else:
            classification[commodity] = "balanced"
    return classification

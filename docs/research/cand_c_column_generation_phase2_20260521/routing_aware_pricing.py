"""Phase 2 Task 4 — routing-aware pricing seed (perimeter port bonus + Rent's-Rule).

Phase 4 will close the loop with a real routing subproblem.  Phase 2
seeds a cheap proxy:

(A) Port-direction perimeter bonus
    For each pose, count its perimeter ports paired (input adjacent to
    output on bbox boundary).  Pricing objective adds a small reward
    for poses whose port direction is balanced — reduces orphan-port
    columns that would later force long routing detours.

(B) Rent's-Rule constraint on commodity penetration
    Rent's Rule (interconnection): boundary signals ~ K * N^p with
    p ~ 0.6 for grid logic.  Applied here as a hard cap:
        commodity penetration <= K_window
    where commodity penetration = number of distinct (port direction)
    classes touching the column's bbox boundary.  Gemini round-2 Q3
    suggested ≤ 3 distinct commodity classes per column to keep the
    later routing subproblem tractable.

(C) Dual-of-Rent's: the RMP constraint sum_k λ_k * penetration_k ≤
    capacity_window is the linear projection of Rent's bound onto the
    column space.  Phase 2 records this dual; Phase 4 uses it for
    pricing reduced-cost seed.

Phase 2 metric m16 = m5 multi-pct after enabling routing-aware
pricing should stay ≥ 60% (vs 30% baseline threshold) — i.e. routing
awareness must not destroy column expressiveness.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple


# === Perimeter port direction bonus ===


def _is_perimeter_cell(cell: Tuple[int, int], region: Tuple[int, int, int, int]) -> bool:
    x, y = cell
    x_lo, y_lo, x_hi, y_hi = region
    return x == x_lo or x == x_hi or y == y_lo or y == y_hi


def perimeter_port_balance_bonus(
    pose: Any,
    region: Tuple[int, int, int, int],
) -> float:
    """Return [0, 1] bonus = (paired_perimeter_ports) / (all_perimeter_ports).

    "Paired" = port whose direction matches the cell's perimeter edge.
    Higher = more "expected" port orientation, fewer routing detours.
    """
    if not pose.typed_ports:
        return 0.0
    x_lo, y_lo, x_hi, y_hi = region
    perim_total = 0
    paired = 0
    for (px, py, pdir, _io) in pose.typed_ports:
        if not (x_lo <= px <= x_hi and y_lo <= py <= y_hi):
            continue
        # Cell on perimeter?
        on_perim = (px == x_lo) or (px == x_hi) or (py == y_lo) or (py == y_hi)
        if not on_perim:
            continue
        perim_total += 1
        # Direction-matches-perimeter check.
        if px == x_lo and pdir == "W":
            paired += 1
        elif px == x_hi and pdir == "E":
            paired += 1
        elif py == y_lo and pdir == "S":
            paired += 1
        elif py == y_hi and pdir == "N":
            paired += 1
    if perim_total == 0:
        return 0.0
    return paired / perim_total


def commodity_classes_in_pose(pose: Any) -> FrozenSet[str]:
    """Set of (io_type, direction) tuples — proxy for commodity classes.

    Phase 2 doesn't have a real commodity model yet; we use port
    (io, dir) tuples as a discriminator.  Phase 4 will replace this with
    the actual commodity registry.
    """
    classes: set = set()
    for (_x, _y, pdir, io) in pose.typed_ports:
        classes.add(f"{io}_{pdir}")
    return frozenset(classes)


# === Per-column commodity penetration ===


def column_commodity_penetration(
    pattern: Any,
    region: Tuple[int, int, int, int],
) -> int:
    """Count distinct (io, dir) classes touching the column's perimeter."""
    x_lo, y_lo, x_hi, y_hi = region
    seen: set = set()
    for (px, py, pdir, io) in pattern.typed_ports:
        if (
            (px == x_lo) or (px == x_hi)
            or (py == y_lo) or (py == y_hi)
        ):
            if x_lo <= px <= x_hi and y_lo <= py <= y_hi:
                seen.add(f"{io}_{pdir}")
    return len(seen)


# === Rent's-Rule cap for pricing CP-SAT ===


@dataclass
class RentsRuleConfig:
    """Rent's-Rule cap parameters."""

    max_commodity_classes: int = 3
    enable_perimeter_bonus: bool = True
    perimeter_bonus_weight: float = 0.05   # small additive vs reduced-cost.


def apply_rents_rule_to_pricing(
    model: Any,
    z_vars: Mapping[Tuple[str, int], Any],
    pose_lookup: Mapping[Tuple[str, int], Any],
    config: RentsRuleConfig,
) -> int:
    """Hard cap: number of distinct commodity classes selected <= K.

    Strategy: for each commodity class C, create a bool c_class[C]
    set to True iff any chosen pose contributes class C.  Then
    sum_C c_class[C] <= K.

    Returns number of class indicator vars created.
    """
    from ortools.sat.python import cp_model  # noqa: F401 (typing hint only)

    class_to_zvars: Dict[str, List[Any]] = defaultdict(list)
    for (iid, pose_idx), zv in z_vars.items():
        pose = pose_lookup.get((iid, pose_idx))
        if pose is None:
            continue
        for cls in commodity_classes_in_pose(pose):
            class_to_zvars[cls].append(zv)
    if not class_to_zvars:
        return 0
    class_indicators: List[Any] = []
    for cls, zvs in class_to_zvars.items():
        ind = model.NewBoolVar(f"cls_{cls}")
        # ind == True iff any z in zvs == 1.
        model.AddMaxEquality(ind, zvs) if hasattr(model, "AddMaxEquality") else None
        # Fallback when AddMaxEquality not available: enforce via
        # OnlyEnforceIf bidirectional implications.
        if not hasattr(model, "AddMaxEquality"):
            for zv in zvs:
                model.AddImplication(zv, ind)
            # ind=True -> at least one zv=True.
            model.Add(sum(zvs) >= 1).OnlyEnforceIf(ind)
        class_indicators.append(ind)
    model.Add(sum(class_indicators) <= config.max_commodity_classes)
    return len(class_indicators)


# === Reduced-cost adjustment for perimeter bonus ===


def perimeter_bonus_offset(
    chosen_poses: Sequence[Any],
    region: Tuple[int, int, int, int],
    config: RentsRuleConfig,
) -> float:
    """Phase 2 post-pricing adjustment: subtract bonus from reduced cost.

    Lower (more negative) reduced cost = pricing favours this column.
    Bonus is small so it doesn't dominate the LP dual.
    """
    if not config.enable_perimeter_bonus or not chosen_poses:
        return 0.0
    avg = sum(perimeter_port_balance_bonus(p, region) for p in chosen_poses) / len(chosen_poses)
    return -config.perimeter_bonus_weight * avg


# === Pricing-objective additive (integer form for CP-SAT) ===


def perimeter_bonus_terms(
    z_vars: Mapping[Tuple[str, int], Any],
    pose_lookup: Mapping[Tuple[str, int], Any],
    region: Tuple[int, int, int, int],
    config: RentsRuleConfig,
    scale: int = 1000,
) -> List[Any]:
    """Build integer-weighted objective terms (for `model.Minimize(sum(...))`).

    Each term is `int(-bonus * weight * scale) * z`, so larger bonus
    => more negative term => pricing solver prefers selecting that
    pose.  Returns empty list if perimeter bonus disabled.
    """
    if not config.enable_perimeter_bonus:
        return []
    terms: List[Any] = []
    w = config.perimeter_bonus_weight
    for (iid, pose_idx), zv in z_vars.items():
        pose = pose_lookup.get((iid, pose_idx))
        if pose is None:
            continue
        b = perimeter_port_balance_bonus(pose, region)
        coeff = int(round(-w * b * scale))
        if coeff != 0:
            terms.append(coeff * zv)
    return terms


__all__ = [
    "RentsRuleConfig",
    "perimeter_port_balance_bonus",
    "commodity_classes_in_pose",
    "column_commodity_penetration",
    "apply_rents_rule_to_pricing",
    "perimeter_bonus_offset",
    "perimeter_bonus_terms",
]

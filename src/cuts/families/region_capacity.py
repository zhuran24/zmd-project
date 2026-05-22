"""Family 1 region_capacity — production validator + evaluator + helpers.

Implements cut_family_specs/01_region_capacity.md v1.2 (Day 17g final).

Phase 1.1 P1.5 scope:
- ``validate_region_capacity(cut, state, canonical_rules)`` — 4 region kind
  独立重算 (left_baseline / bottom_baseline / interior_rect / ghost_complement).
- ``evaluate_geometric_region_capacity(cut, state)`` — propagation hot path
  (per spec §6 v1.1 简化: cap_R static → cert.demand_R > cert.cap_R 永 violate
  in scope, watcher 在 ghost change 时 invalidate).
- Helper functions (region cells / capacity / demand / placement rule mapping).

Deferred to Phase 1.5+ (per spec §10 open question #1):
- LP dual / Farkas algebraic check (cand C ``farkas_certificate.py`` 集成).
- Multi-region cut (cluster from LP dual ray).
- interior_rect generator enumeration heuristic.

This module is consumed by:
- ``src/cuts/oracles/region_capacity_oracle.py`` (generator)
- ``src/cuts/replay.py:FAMILY_VALIDATORS["region_capacity"]`` (re-registered to
  this production validator, replacing lifecycle.py PoC reference).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md v1.2
- cut_lifecycle_v2.md v3.2.2 §4-§6
- PROJECT_LOCK.md §3A invariants
"""
from __future__ import annotations

import base64
import json
import time
from typing import Dict, FrozenSet, List, Literal, Tuple

from src.cuts.lifecycle import BState, Cell, Cut, GroupId, ValidationResult


RegionKind = Literal[
    "left_baseline",
    "bottom_baseline",
    "interior_rect",
    "ghost_complement",
]


# Placement rule → applicable region kinds (per spec §1b).
# Used by validator to verify group ∈ contributing_groups maps into the cert's
# region_kind correctly.
_PLACEMENT_RULE_REGIONS: Dict[str, FrozenSet[str]] = {
    "left_or_bottom_boundary": frozenset({"left_baseline", "bottom_baseline"}),
    "left_baseline": frozenset({"left_baseline"}),
    "bottom_baseline": frozenset({"bottom_baseline"}),
    # "free" placement rule maps to no region (group can be anywhere — not a
    # specific region's demand contributor).
    "free": frozenset(),
}


def compute_region_cells(
    region_kind: RegionKind,
    state: BState,
    grid_size: int = 70,
) -> FrozenSet[Cell]:
    """Compute region cell set per region_kind.

    interior_rect / ghost_complement: 需要 state.ghost_rect (Phase 1.5+ 加
    generator enumeration; P1.5 仅 validator decode cert 用).
    """
    if region_kind == "left_baseline":
        return frozenset((x, 0) for x in range(grid_size))
    if region_kind == "bottom_baseline":
        return frozenset((0, y) for y in range(grid_size))
    if region_kind == "ghost_complement":
        if state.ghost_rect is None:
            return frozenset()
        return frozenset(state.ghost_cells)
    if region_kind == "interior_rect":
        # Generator 应 carry interior_rect 的具体 bitset in cert (Phase 1.5+).
        # 当前 P1.5 阶段, validator decode cert 的 bitset 不调此函数.
        raise NotImplementedError(
            "interior_rect 的 generic compute_region_cells defer Phase 1.5+; "
            "validator should decode region_cells_bitset_b64 from cert directly."
        )
    raise ValueError(f"unknown region_kind={region_kind!r}")


def compute_static_capacity(
    region_cells: FrozenSet[Cell],
    state: BState,
) -> int:
    """v1.1 static cap_R: |R| - |ghost ∩ R| - |exterior ∩ R| (不含 cell_owner).

    See spec §2a v1.1 critical fix (Gemini round 14 finding #3).
    """
    blocked = state.ghost_cells | state.exterior_blocks
    return len(region_cells) - len(blocked & region_cells)


def compute_demand(
    region_kind: RegionKind,
    contributing_groups: List[Tuple[GroupId, int]],
    cert_cells_per_pose: Dict[GroupId, int],
    state: BState,
) -> int:
    """Recompute demand_R from cert.contributing_groups + cert.cells_per_pose.

    v1.1 (Gemini round 14 finding #5): 用 cert 内 cells_per_pose, **不**走外部
    state, 防 canonical_rules pose shape 微调时全 cut quarantine.
    """
    demand = 0
    for gid, _demand_in_cert in contributing_groups:
        cpp = cert_cells_per_pose.get(gid)
        if cpp is None:
            raise KeyError(f"cert.cells_per_pose missing group {gid!r}")
        demand += state.groups[gid].demand * cpp
    return demand


def _group_falls_in_region(
    gid: GroupId,
    region_kind: RegionKind,
    canonical_rules: Dict,
) -> bool:
    """Verify group's placement_rule maps to region_kind (active_assumption 对齐).

    For "free" placement rule (e.g. crusher), the group can be placed anywhere
    — not a region-specific contributor. Spec §2b: only groups requiring
    P(g) ⊆ R count toward demand_R.
    """
    group_entry = canonical_rules.get(gid)
    if not isinstance(group_entry, dict):
        return False
    rule = group_entry.get("placement_rule")
    if rule is None:
        return False
    valid_regions = _PLACEMENT_RULE_REGIONS.get(rule, frozenset())
    return region_kind in valid_regions


def _decode_region_bitset(
    b64: str, grid_size: int = 70
) -> FrozenSet[Cell]:
    """Decode base64 bitset to cell set. Mirror lifecycle._decode_region_bitset."""
    arr = base64.b64decode(b64)
    cells = set()
    for x in range(grid_size):
        for y in range(grid_size):
            idx = x * grid_size + y
            if arr[idx // 8] & (1 << (idx % 8)):
                cells.add((x, y))
    return frozenset(cells)


def validate_region_capacity(
    cut: Cut,
    state: BState,
    canonical_rules: Dict,
) -> ValidationResult:
    """Production F1 validator. 4 region kind, independent recompute, witness check.

    Replaces lifecycle.step_5_validate_region_capacity (P1.1 PoC reference) when
    registered into FAMILY_VALIDATORS.

    Validates (per spec §7):
    1. cap_R = |R| - |blocked ∩ R| matches cert.
    2. Each contributing_group's placement_rule maps to cert.region_kind.
    3. cert.cells_per_pose matches current canonical_rules (防 source rotated).
    4. demand_R = Σ group.demand × cells_per_pose matches cert.
    5. Witness: demand_R > cap_R.
    """
    assert cut.geometric_payload is not None
    t0 = time.monotonic()
    try:
        cert_dict = json.loads(cut.geometric_payload)
        region_kind: RegionKind = cert_dict["region_kind"]

        # Decode region cells from cert bitset (canonical — independent of state).
        region_cells = _decode_region_bitset(cert_dict["region_cells_bitset_b64"])

        # 1. cap_R independent recompute
        recomputed_cap_R = compute_static_capacity(region_cells, state)
        cert_cap_R = cert_dict["cap_R"]
        if recomputed_cap_R != cert_cap_R:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"cap_R mismatch: cert={cert_cap_R}, recomputed={recomputed_cap_R}",
            )

        # 2-4. demand_R: placement_rule mapping + cells_per_pose source-of-truth + recompute
        cert_cells_per_pose = cert_dict.get("cells_per_pose", {})
        contributing_groups: List[Tuple[GroupId, int]] = [
            (g, d) for g, d in cert_dict["contributing_groups"]
        ]
        for gid, _ in contributing_groups:
            # 2. placement_rule → region mapping (skip if group is "free")
            if not _group_falls_in_region(gid, region_kind, canonical_rules):
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"group {gid!r} placement_rule 不映射 {region_kind!r}",
                )
            # 3. cells_per_pose source-of-truth check
            if gid not in cert_cells_per_pose:
                return ValidationResult(
                    kind="schema_err",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"cert.cells_per_pose missing group {gid!r}",
                )
            current_cpp = canonical_rules[gid].get("cells_per_pose")
            if cert_cells_per_pose[gid] != current_cpp:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"cells_per_pose mismatch for {gid!r}: "
                        f"cert={cert_cells_per_pose[gid]}, current={current_cpp} "
                        f"(canonical_rules pose shape rotated)"
                    ),
                )

        # 4. demand_R independent recompute
        try:
            recomputed_demand_R = compute_demand(
                region_kind, contributing_groups, cert_cells_per_pose, state,
            )
        except KeyError as e:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail=str(e),
            )

        cert_demand_R = cert_dict["demand_R"]
        if recomputed_demand_R != cert_demand_R:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"demand_R mismatch: cert={cert_demand_R}, recomputed={recomputed_demand_R}",
            )

        # 5. Witness: demand > cap
        if recomputed_demand_R <= recomputed_cap_R:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"witness fail: demand_R={recomputed_demand_R} ≤ cap_R={recomputed_cap_R}",
            )

        # LP dual / Farkas algebraic check defer Phase 1.5+ (spec §7b open question #1).

        return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - t0)

    except Exception as e:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate_geometric_region_capacity(cut: Cut, state: BState) -> bool:
    """Propagation hot path. Per spec §6 v1.1 简化版:

    cap_R static (ghost+exterior only) + cert.demand_R > cert.cap_R 已 generator
    时 oracle verify → scope 内永 violate. Re-attach 路径走 watcher invalidate
    + replay step 2 HOLD on ghost change (cut_lifecycle_v2 v3.2.2 dispatch).

    Sound iff: cap_R is static (Phase 1.0/1.1 v1.1 lock). 若回到 v1.0
    cell-owner-dependent cap (PROJECT_LOCK 禁) 此函数会变 FN/FP.
    """
    return True

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
from functools import lru_cache
from typing import Dict, FrozenSet, List, Literal, Tuple

from src.cuts.lifecycle import BState, Cell, Cut, GroupId, ValidationResult


RegionKind = Literal[
    "left_baseline",
    "bottom_baseline",
    "left_or_bottom_union",  # Gap 6 (Gemini round 30): 新 region kind, F1 boundary
                              # 真实数学 — left ∪ bottom = 139 cells (含 (0,0) 重叠).
                              # 跟 spec §2b "P(g) ⊆ R" 严格 sound. 替 per-side cut.
    "interior_rect",
    "ghost_complement",
]


# Placement rule → applicable region kinds (per spec §1b).
# Used by validator to verify group ∈ contributing_groups maps into the cert's
# region_kind correctly.
# Gap 6 (Gemini round 30): "left_or_bottom_boundary" → ONLY "left_or_bottom_union",
# **不**映射 single side (per-side cut 数学 b) FN — bottom ghost block 时 left
# demand 应升但 single-side cert demand_R static 不知道).
_PLACEMENT_RULE_REGIONS: Dict[str, FrozenSet[str]] = {
    "left_or_bottom_boundary": frozenset({"left_or_bottom_union"}),
    # Phase 1.5+ 可能加 single-side rules (实际项目 canonical_rules.json
    # **只** "left_or_bottom_boundary" 一种 placement_rule, 其他 free)
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
    if region_kind == "left_or_bottom_union":
        # Gap 6 (round 30): left ∪ bottom = 139 cells, (0,0) 共同 cell 去重.
        left = {(x, 0) for x in range(grid_size)}
        bottom = {(0, y) for y in range(grid_size)}
        return frozenset(left | bottom)
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
    state: BState,
) -> bool:
    """Verify group's placement_rule maps to region_kind (active_assumption 对齐).

    Phase 1.1 P1.5+ (Gap 8) 修: 经 helper, 不直接查 canonical_rules[gid].
    For "free" placement rule (e.g. crusher), group not region-specific
    contributor. Spec §2b: only groups requiring P(g) ⊆ R count toward demand_R.

    **此函数仅 placement_rule 必要条件 check, 不是充分条件**. 真 P(g)⊆R 验证
    经 _all_poses_in_region_strict() (GPT pro round 2 P0-1 fix).
    """
    from src.cuts.helpers.canonical_rules import placement_rule_for_group
    rule = placement_rule_for_group(state, gid)
    if rule in ("unknown", "free"):
        return False
    valid_regions = _PLACEMENT_RULE_REGIONS.get(rule, frozenset())
    return region_kind in valid_regions


def _all_poses_in_region_strict(
    gid: GroupId,
    region_cells: FrozenSet[Cell],
    state: BState,
) -> bool:
    """Strict P(g) ⊆ R verification (GPT pro round 2 P0-1).

    Returns True iff ALL pose 在 group.pose_domain 的 occupied_cells ⊆ R.
    Fail-closed (返 False) 若 candidate_placements 没 inject 或任一 pose
    lookup fail.

    真数据 (boundary_io): 54 pose 中 14 个占 (31,69)/(32,69)/(33,69) 等不在
    left ∪ bottom union → 整 group not P(g)⊆R → 不 contributing.
    """
    from src.cuts.helpers.candidate_placements import all_poses_in_region
    result = all_poses_in_region(state, gid, region_cells)
    return result is True


@lru_cache(maxsize=256)
def _decode_region_bitset(
    b64: str, grid_size: int = 70
) -> FrozenSet[Cell]:
    """Decode base64 bitset to cell set. Mirror lifecycle._decode_region_bitset.

    Gemini round 34 P0 性能 fix: hot path (evaluate_geometric_region_capacity)
    每 propagator call 调一次, 70x70=4900 iter Python 循环 + base64 decode.
    propagator 每秒可 10K 调用 → 4900 × 10K = 49M iter/sec → solver 退化数量级.

    lru_cache(256) 让相同 cert.region_cells_bitset_b64 (cert content-addressed)
    第一次 4900 iter 后续 O(1) lookup. 256 cap 足够 active cut count
    (Phase 1.1 ramp 实测 < 100 active cut/iter).
    """
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

    GPT pro round 2 fix: schema check 走 explicit if (`python -O` 防线).
    """
    t0 = time.monotonic()
    if cut.geometric_payload is None:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail="cut.geometric_payload is None (F1 schema invariant violated)",
        )
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

        # 2-4. demand_R: placement_rule mapping + P(g)⊆R strict + cells_per_pose
        # source-of-truth + recompute
        cert_cells_per_pose = cert_dict.get("cells_per_pose", {})
        contributing_groups: List[Tuple[GroupId, int]] = [
            (g, d) for g, d in cert_dict["contributing_groups"]
        ]

        # 2_pre. 去重: spec §2b demand_R = ∑_{g : P(g) ⊆ R} group.demand × cpp 是
        # group 集合上的求和, **不是 multiset**. attacker 把同 group 写两次让
        # demand_R 翻倍 → fake over-demand cut 误剪合法 state (GPT pro v3 P0).
        # 真数据反例: actual demand=70, cap=139 (合法), cert duplicate group →
        # demand=140 > cap=139 → 假证.
        seen_gids: set = set()
        for gid, _ in contributing_groups:
            if gid in seen_gids:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"duplicate contributing group {gid!r} — spec §2b demand_R 是 "
                        f"group 集合求和, 不允许 multiset (GPT pro v3 P0 反例)"
                    ),
                )
            seen_gids.add(gid)

        # Gap 8 (Gemini round 30) 修: cells_per_pose lookup 经 helper, 不直接
        # 查 canonical_rules[gid] (gid 是 operation_type 不是顶层 key).
        from src.cuts.helpers.canonical_rules import cells_per_pose_for_group
        for gid, demand_in_cert in contributing_groups:
            # 2a. placement_rule → region mapping (skip if group is "free") — 必要 NOT 充分
            if not _group_falls_in_region(gid, region_kind, state):
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"group {gid!r} placement_rule 不映射 {region_kind!r}",
                )
            # 2b. strict P(g) ⊆ R (GPT pro round 2 P0-1) — 充分条件
            if not _all_poses_in_region_strict(gid, region_cells, state):
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"group {gid!r} 不满足 P(g) ⊆ R: ∃ pose 占格 在 region 外 "
                        f"(spec §2b 严格充分条件 / GPT pro round 2 P0-1). "
                        f"真数据示例: boundary_io 14/54 pose 在 left∪bottom union 外 "
                        f"(e.g. viewer::boundary_required_output_source_ore_005 占 "
                        f"(31,69)/(32,69)/(33,69))"
                    ),
                )
            # 3. cells_per_pose source-of-truth check (via helper)
            if gid not in cert_cells_per_pose:
                return ValidationResult(
                    kind="schema_err",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"cert.cells_per_pose missing group {gid!r}",
                )
            current_cpp = cells_per_pose_for_group(state, gid)
            if current_cpp is None:
                return ValidationResult(
                    kind="schema_err",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"cannot resolve cells_per_pose for {gid!r} — "
                        f"facility_templates / instance_to_facility_type 未 inject"
                    ),
                )
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
            # 3b. demand_in_cert tuple entry 真等 group.demand × current_cpp
            # (GPT pro v3 P0: 防 cert tuple 内 fake demand_in_cert 跟其它 field 配
            # 合伪造 over-demand)
            expected_demand_in_cert = state.groups[gid].demand * current_cpp
            if demand_in_cert != expected_demand_in_cert:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"contributing_groups tuple demand mismatch for {gid!r}: "
                        f"cert={demand_in_cert}, expected={expected_demand_in_cert} "
                        f"(= group.demand × cells_per_pose)"
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

        # 4b. GPT pro v6 P0 fix: scope.ghost_rect_id == GHOST_AGNOSTIC 合法性 check.
        # 反例: attacker 把 ghost-dependent cut 错标 GHOST_AGNOSTIC, replay 后
        # store 不挂 by_ghost_watcher → ghost 变化不 invalidate → 失效 cut 残留
        # active. F1 spec §3 (01_region_capacity.md:83-89) GHOST_AGNOSTIC 仅当
        # ghost_cells ∩ region_cells == ∅ 允许. oracle 已按此判 (oracle.py:170-177),
        # 但 validator 不再 trust generator, 必独立 verify.
        from src.cuts.lifecycle import GHOST_AGNOSTIC
        if cut.scope is not None and cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
            ghost_in_region = state.ghost_cells & region_cells
            if ghost_in_region:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"scope.ghost_rect_id=GHOST_AGNOSTIC 但 ghost_cells 跟 region "
                        f"有交集 ({len(ghost_in_region)} cells, sample={sorted(ghost_in_region)[:3]}) — "
                        f"spec §3 仅当 ghost ∩ R == ∅ 允许 GHOST_AGNOSTIC"
                    ),
                )

        # 5. Witness: demand > cap
        if recomputed_demand_R <= recomputed_cap_R:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"witness fail: demand_R={recomputed_demand_R} ≤ cap_R={recomputed_cap_R}",
            )

        # 6. gap consistency (GPT pro v3 推荐顺手补): cert.gap 必 == demand - cap
        # + 必 > 0. 防 cert tuple 内部 field 互相 inconsistent 走过.
        cert_gap = cert_dict.get("gap")
        if cert_gap is None:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail="cert missing gap field",
            )
        expected_gap = recomputed_demand_R - recomputed_cap_R
        if cert_gap != expected_gap:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"gap mismatch: cert={cert_gap}, expected={expected_gap}",
            )
        if cert_gap <= 0:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"non-positive gap: {cert_gap} (cut 须 strict demand > cap)",
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
    """Propagation hot path — recompute cap_R + verify still violating.

    **Phase 1.1 scope**: 此函数在 lifecycle.step_7_evaluate_cut 调用一次/cut
    (post-attach), **不**在 CP-SAT propagator 真 hot path (Phase 1.3 P1.21
    step_8_apply_to_master 才接 propagator). 当前调用频率 ≤ 1/cut/iter, json.loads
    + decode 单调 ms 内不构成 perf bottleneck.

    **Phase 1.3 P1.21 必修 (defer)** — Gemini round 35 perf hypotheses:
    1. `json.loads(cut.geometric_payload)` per call → cache parsed cert_dict
       on Cut object (now-frozen, 加 mutable side cache attr or attach store
       cache).
    2. `_decode_region_bitset` lru_cache(256) 已 land — Phase 1.3 跨 cut
       hot path 反复调时 cache miss risk → 改 attach-time eager decode + 持有
       FrozenSet 于 Cut.scope.
    3. by_exterior_watcher 加 + master 改 exterior_blocks 时 trigger replay
       (sound 不需要 — evaluate 重算保 cut 一致 — 但 efficiency 必须避免
       million-call/sec evaluator over wide search tree).

    Gemini round 33 P0 fix (此函数原 v1.1 简化版无条件返 True): exterior_blocks
    在 cut attach 后被 master 修改 (移除 block) → cap_R 增 → cut 不再 violate.
    但 propagator 仍调此函数返 True → cut emit constraint → 假剪合法 state.

    Step F 修法: 重算 current cap_R = compute_static_capacity(region_cells, state),
    比 cert.demand_R > current_cap. 不 violate → False (propagator skip cut).

    Sound: per spec §2a v1.1 cap_R = |R| - |(ghost ∪ exterior) ∩ R|. 任何
    ghost/exterior change 都触发 evaluate recompute. cert.demand_R 是 oracle
    时锁定 — 真生产 demand 不变.
    """
    if cut.geometric_payload is None:
        return False
    try:
        cert_dict = json.loads(cut.geometric_payload)
        region_cells = _decode_region_bitset(cert_dict["region_cells_bitset_b64"])
        current_cap = compute_static_capacity(region_cells, state)
        return cert_dict["demand_R"] > current_cap
    except Exception:
        # Fail-safe: cert 解析错就不报 violate, 等 replay quarantine
        return False

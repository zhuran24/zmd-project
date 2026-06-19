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
from typing import Any, Dict, FrozenSet, List, Literal, Tuple, cast

from src.cuts.lifecycle import BState, Cell, Cut, GroupId, ValidationResult, validate_cert_payload


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


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_strict_int(value: object, field_name: str) -> int:
    if not _is_strict_int(value):
        raise ValueError(f"{field_name} must be int (bool/str rejected)")
    return cast(int, value)


def _parse_non_empty_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be non-empty str")
    return value


def _parse_region_kind(value: object) -> RegionKind:
    region_kind = _parse_non_empty_str(value, "region_kind")
    if region_kind not in {
        "left_baseline",
        "bottom_baseline",
        "left_or_bottom_union",
        "interior_rect",
        "ghost_complement",
    }:
        raise ValueError(f"unsupported region_kind={region_kind!r}")
    return cast(RegionKind, region_kind)


def _parse_contributing_groups(value: object) -> List[Tuple[GroupId, int]]:
    if not isinstance(value, list):
        raise ValueError("contributing_groups must be list")
    parsed: List[Tuple[GroupId, int]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"contributing_groups[{idx}] must be [group_id, demand]")
        gid = _parse_non_empty_str(item[0], f"contributing_groups[{idx}][0]")
        demand = _parse_strict_int(item[1], f"contributing_groups[{idx}][1]")
        parsed.append((gid, demand))
    return parsed


def _parse_cells_per_pose(value: object) -> Dict[GroupId, int]:
    if not isinstance(value, dict):
        raise ValueError("cells_per_pose must be dict[str, int]")
    parsed: Dict[GroupId, int] = {}
    for raw_gid, raw_cpp in value.items():
        gid = _parse_non_empty_str(raw_gid, "cells_per_pose key")
        parsed[gid] = _parse_strict_int(raw_cpp, f"cells_per_pose[{gid!r}]")
    return parsed


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
    arr = base64.b64decode(b64, validate=True)
    expected_len = grid_size * grid_size // 8 + 1
    if len(arr) != expected_len:
        raise ValueError(f"bitset length mismatch: got {len(arr)}, expected {expected_len}")
    cells = set()
    for x in range(grid_size):
        for y in range(grid_size):
            idx = x * grid_size + y
            if arr[idx // 8] & (1 << (idx % 8)):
                cells.add((x, y))
    extra_bits = len(arr) * 8 - grid_size * grid_size
    if extra_bits > 0 and arr[-1] >> (8 - extra_bits):
        raise ValueError("bitset has cells outside grid set")
    return frozenset(cells)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


def _validation_result(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def _validate_unique_contributing_groups(
    contributing_groups: List[Tuple[GroupId, int]],
    t0: float,
) -> ValidationResult | None:
    seen_gids: set[GroupId] = set()
    for gid, _ in contributing_groups:
        if gid in seen_gids:
            return _validation_result(
                "unsound",
                t0,
                f"duplicate contributing group {gid!r} — spec §2b demand_R 是 group 集合求和, 不允许 multiset",
            )
        seen_gids.add(gid)
    return None


def _validate_region_capacity_contributors(
    region_kind: RegionKind,
    region_cells: FrozenSet[Cell],
    contributing_groups: List[Tuple[GroupId, int]],
    cert_cells_per_pose: Dict[GroupId, int],
    state: BState,
    t0: float,
) -> ValidationResult | None:
    from src.cuts.helpers.canonical_rules import cells_per_pose_for_group

    for gid, demand_in_cert in contributing_groups:
        if not _group_falls_in_region(gid, region_kind, state):
            return _validation_result("unsound", t0, f"group {gid!r} placement_rule 不映射 {region_kind!r}")
        if not _all_poses_in_region_strict(gid, region_cells, state):
            return _validation_result(
                "unsound",
                t0,
                f"group {gid!r} 不满足 P(g) ⊆ R: ∃ pose 占格 在 region 外",
            )
        if gid not in cert_cells_per_pose:
            return _validation_result("schema_err", t0, f"cert.cells_per_pose missing group {gid!r}")
        current_cpp = cells_per_pose_for_group(state, gid)
        if current_cpp is None:
            return _validation_result(
                "schema_err",
                t0,
                f"cannot resolve cells_per_pose for {gid!r} — facility_templates / instance_to_facility_type 未 inject",
            )
        if cert_cells_per_pose[gid] != current_cpp:
            return _validation_result(
                "unsound",
                t0,
                f"cells_per_pose mismatch for {gid!r}: cert={cert_cells_per_pose[gid]}, current={current_cpp}",
            )
        expected_demand_in_cert = state.groups[gid].demand * current_cpp
        if demand_in_cert != expected_demand_in_cert:
            return _validation_result(
                "unsound",
                t0,
                f"contributing_groups tuple demand mismatch for {gid!r}: cert={demand_in_cert}, expected={expected_demand_in_cert}",
            )
    return None


def _validate_region_capacity_ghost_scope(
    cut: Cut,
    region_cells: FrozenSet[Cell],
    state: BState,
    t0: float,
) -> ValidationResult | None:
    from src.cuts.lifecycle import GHOST_AGNOSTIC

    if cut.scope is not None and cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        ghost_in_region = state.ghost_cells & region_cells
        if ghost_in_region:
            return _validation_result(
                "unsound",
                t0,
                f"scope.ghost_rect_id=GHOST_AGNOSTIC but ghost intersects region ({len(ghost_in_region)} cells)",
            )
    return None


def _validate_region_capacity_gap(
    cert_dict: Dict[str, Any],
    recomputed_demand_R: int,
    recomputed_cap_R: int,
    t0: float,
) -> ValidationResult | None:
    if recomputed_demand_R <= recomputed_cap_R:
        return _validation_result(
            "unsound",
            t0,
            f"witness fail: demand_R={recomputed_demand_R} ≤ cap_R={recomputed_cap_R}",
        )
    if "gap" not in cert_dict:
        return _validation_result("schema_err", t0, "cert missing gap field")
    try:
        cert_gap = _parse_strict_int(cert_dict["gap"], "gap")
    except ValueError as e:
        return _validation_result("schema_err", t0, str(e))
    expected_gap = recomputed_demand_R - recomputed_cap_R
    if cert_gap != expected_gap:
        return _validation_result("unsound", t0, f"gap mismatch: cert={cert_gap}, expected={expected_gap}")
    if cert_gap <= 0:
        return _validation_result("unsound", t0, f"non-positive gap: {cert_gap} (cut 须 strict demand > cap)")
    return None


def validate_region_capacity(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """Production F1 validator. Independent recompute + witness check."""
    t0 = time.monotonic()
    del canonical_rules
    if cut.geometric_payload is None:
        return _validation_result("schema_err", t0, "cut.geometric_payload is None (F1 schema invariant violated)")
    try:
        cert_dict = validate_cert_payload("region_capacity", cut.geometric_payload)
        region_kind = _parse_region_kind(cert_dict.get("region_kind"))
        region_cells_b64 = _parse_non_empty_str(cert_dict.get("region_cells_bitset_b64"), "region_cells_bitset_b64")
        region_cells = _decode_region_bitset(region_cells_b64)
        cert_cap_R = _parse_strict_int(cert_dict.get("cap_R"), "cap_R")
        cert_demand_R = _parse_strict_int(cert_dict.get("demand_R"), "demand_R")
        recomputed_cap_R = compute_static_capacity(region_cells, state)
        if recomputed_cap_R != cert_cap_R:
            return _validation_result("unsound", t0, f"cap_R mismatch: cert={cert_cap_R}, recomputed={recomputed_cap_R}")
        cert_cells_per_pose = _parse_cells_per_pose(cert_dict.get("cells_per_pose", {}))
        contributing_groups = _parse_contributing_groups(cert_dict.get("contributing_groups"))
        for error in (
            _validate_unique_contributing_groups(contributing_groups, t0),
            _validate_region_capacity_contributors(region_kind, region_cells, contributing_groups, cert_cells_per_pose, state, t0),
            _validate_region_capacity_ghost_scope(cut, region_cells, state, t0),
        ):
            if error is not None:
                return error
        try:
            recomputed_demand_R = compute_demand(region_kind, contributing_groups, cert_cells_per_pose, state)
        except KeyError as e:
            return _validation_result("schema_err", t0, str(e))
        if recomputed_demand_R != cert_demand_R:
            return _validation_result("unsound", t0, f"demand_R mismatch: cert={cert_demand_R}, recomputed={recomputed_demand_R}")
        gap_error = _validate_region_capacity_gap(cert_dict, recomputed_demand_R, recomputed_cap_R, t0)
        if gap_error is not None:
            return gap_error
        return _validation_result("ok", t0)
    except Exception as e:
        return _validation_result("schema_err", t0, f"{type(e).__name__}: {e}")

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
        return bool(cert_dict["demand_R"] > current_cap)
    except Exception:
        # Fail-safe: cert 解析错就不报 violate, 等 replay quarantine
        return False

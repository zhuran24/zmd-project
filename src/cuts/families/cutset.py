"""Family 2 cutset — production validator + evaluator + helpers.

Implements cut_family_specs/02_cutset.md v1.0.

Phase 1.1 P1.6 scope (minimum viable):
- ``validate_cutset(cut, state, canonical_rules)`` — 验 cert structure +
  cross-partition edge recompute on state.free_cells + witness (demand > cut_size).
- ``evaluate_geometric_cutset(cut, state)`` — propagation hot path 重算 cur
  cut edges, True iff still violating (demand > current_cut_size).

Phase 1.5+ extends (per spec §9 open questions):
- Patch belt CP-SAT min-cut extraction via patch_routing_core (Path 14 PCR-CUT
  helper 复用 — Phase 0 验 770 cells cover 98% SAC slack).
- Multi-commodity vertex split graph (commodity demand > cut_size 多 commodity 分配).
- Max-flow LP witness algebraic check (verify_max_flow_witness from witness_blob).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md v1.0
"""
from __future__ import annotations

import base64
import json
import time
from typing import Dict, FrozenSet, List, Tuple

from src.cuts.lifecycle import BState, Cell, Cut, ValidationResult


# Cross-partition edge between two adjacent cells (Manhattan 4-neighborhood).
PartitionEdge = Tuple[Cell, Cell]


def _decode_bitset(b64: str, grid_size: int = 70) -> FrozenSet[Cell]:
    arr = base64.b64decode(b64)
    cells = set()
    for x in range(grid_size):
        for y in range(grid_size):
            idx = x * grid_size + y
            if arr[idx // 8] & (1 << (idx % 8)):
                cells.add((x, y))
    return frozenset(cells)


def _free_cells(state: BState, grid_size: int = 70) -> FrozenSet[Cell]:
    """state_machine_v2 §3 I3: free_cells = all_cells \\ ghost_cells \\ cell_owner.keys().

    P1.6 minimum viable — Phase 1.5+ 可改 state 持 free_cells field.
    """
    all_cells = {(x, y) for x in range(grid_size) for y in range(grid_size)}
    return frozenset(all_cells - set(state.ghost_cells) - set(state.cell_owner.keys()))


def _cross_partition_edges(
    side_a: FrozenSet[Cell],
    side_b: FrozenSet[Cell],
    free_cells: FrozenSet[Cell],
) -> FrozenSet[PartitionEdge]:
    """Return undirected edges (a, b) where a ∈ A, b ∈ B, both ∈ free_cells, and
    a/b Manhattan-adjacent. Canonicalize order (smaller first) to dedupe."""
    edges = set()
    for cell in side_a & free_cells:
        x, y = cell
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = (x + dx, y + dy)
            if neighbor in side_b and neighbor in free_cells:
                edge = (cell, neighbor) if cell <= neighbor else (neighbor, cell)
                edges.add(edge)
    return frozenset(edges)


def _has_patch_escape(
    patch: FrozenSet[Cell],
    free_cells: FrozenSet[Cell],
) -> bool:
    """patch 内 cell 相邻 patch 外 free cell → 流可绕过 patch, partition 不 enclose.

    Returns True iff ∃ p ∈ patch, q ∈ free_cells \\ patch, q is 4-neighbor of p.
    Used by validator to fail-closed on non-enclosed partition (GPT pro round 2
    P0-3): F2 spec §1a partition (A, B) of V — V 必 = patch universe, patch 外
    的 free cell 不在 partition 但流可走 → cut_size 假证.
    """
    outside_free = free_cells - patch
    if not outside_free:
        return False
    for cell in patch:
        x, y = cell
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if (x + dx, y + dy) in outside_free:
                return True
    return False


def _canonical_edges(edges: FrozenSet[PartitionEdge]) -> List:
    """Canonical sorted edge list for cert byte-equal compare."""
    return sorted([list(e) for e in edges])


def validate_cutset(
    cut: Cut,
    state: BState,
    canonical_rules: Dict,
) -> ValidationResult:
    """Production F2 validator.

    Checks (GPT pro round 2 P0-3 加强):
    1. cert.side_a ∩ side_b == ∅ (partition disjoint)
    2. (A ∪ B) ⊆ current free_cells — partition cells 必 free (attacker 不能塞
       ghost/cell_owner cell 进 partition 制造小 cut_size).
    3. patch enclosure: A ∪ B 没相邻 patch 外 free cell — 否则流可走 patch
       外 (cut 不 sound, spec §1a partition (A,B) of V 必含全 graph node).
    4. cur_cut_size = |cross_partition_edges| matches cert.cut_size.
    5. cert.cut_edges (canonical sorted edge list) ⇔ recomputed edges set
       byte-equal (cert 完整性: 不准只 size 对而 edges 不对).
    6. commodity_demand > cut_size (witness Menger violation).

    GPT pro round 2 fix: schema check 走 explicit if (`python -O` 防线).
    """
    t0 = time.monotonic()
    if cut.geometric_payload is None:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail="cut.geometric_payload is None (F2 schema invariant violated)",
        )
    # GPT pro v6 P0 fix: F2 spec §3 cut.scope.ghost_rect_id 必绑当前 ghost
    # (02_cutset.md:87-89). attacker 错标 GHOST_AGNOSTIC → store 不挂
    # by_ghost_watcher → ghost 变化不 invalidate → 失效 cut 残留 active.
    # Phase 1.1 fail-closed reject GHOST_AGNOSTIC; Phase 1.5+ 如果有 cut 真不
    # 依赖 ghost (理论可能 — 全 patch 内 cell_owner 占, partition 不含 free)
    # 时再 unlock.
    from src.cuts.lifecycle import GHOST_AGNOSTIC
    if cut.scope is not None and cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return ValidationResult(
            kind="unsound",
            elapsed_seconds=time.monotonic() - t0,
            detail=(
                "F2 cutset 不允 GHOST_AGNOSTIC scope (spec §3 必绑当前 ghost — "
                "Phase 1.1 fail-closed)"
            ),
        )
    try:
        cert_dict = json.loads(cut.geometric_payload)
        side_a = _decode_bitset(cert_dict["side_a_bitset_b64"])
        side_b = _decode_bitset(cert_dict["side_b_bitset_b64"])

        # 1. Partition disjoint
        if side_a & side_b:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"partition not disjoint (|A ∩ B|={len(side_a & side_b)})",
            )

        free_cells = _free_cells(state)
        patch = side_a | side_b

        # 2. Partition cells 必 ⊆ free_cells (GPT pro round 2 P0-3)
        non_free = patch - free_cells
        if non_free:
            sample = sorted(non_free)[:3]
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"partition contains {len(non_free)} non-free cell(s) "
                    f"(ghost/cell_owner): sample={sample}"
                ),
            )

        # 3. Patch enclosure — A∪B 没相邻 patch 外 free cell (GPT pro round 2 P0-3)
        if _has_patch_escape(patch, free_cells):
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    "partition not enclosed: ∃ patch cell 相邻 patch 外 free cell — "
                    "流可绕过 partition, spec §1a partition (A,B) of V 不成立"
                ),
            )

        # 4. Cross-partition edge count matches cert
        recomputed_edges = _cross_partition_edges(side_a, side_b, free_cells)
        recomputed_cut_size = len(recomputed_edges)
        cert_cut_size = cert_dict["cut_size"]
        if recomputed_cut_size != cert_cut_size:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"cut_size mismatch: cert={cert_cut_size}, recomputed={recomputed_cut_size}",
            )

        # 5. cert.cut_edges canonical set 等 recomputed (cert 完整性, GPT pro
        # round 2: 不允 attacker 改 cut_size 跟 edges set 不一致). Spec §3 cert
        # schema 含 cut_edges field, 必填.
        if "cut_edges" not in cert_dict:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail="cert missing cut_edges field (F2 spec §3 schema 必填)",
            )
        cert_canonical = sorted(
            [sorted([list(e[0]), list(e[1])]) for e in cert_dict["cut_edges"]]
        )
        recomputed_canonical = sorted(
            [sorted([list(e[0]), list(e[1])]) for e in recomputed_edges]
        )
        if cert_canonical != recomputed_canonical:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"cut_edges set mismatch: cert={len(cert_canonical)} edges, "
                    f"recomputed={len(recomputed_canonical)} edges (or different set)"
                ),
            )

        # 6. commodity_demand 必有 source-of-truth registry (GPT pro v4 P0 fix).
        # 反例: external cert 写 commodity_demand=999, validator 没 registry 重算
        # → 假 over-demand cut ATTACH. fail-closed: state.commodity_demands 没
        # inject → schema_err.
        if state.commodity_demands is None:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    "F2 cutset validator 需 state.commodity_demands registry "
                    "(GPT pro v4 P0 — Phase 1.1 default None fail-closed)"
                ),
            )
        # GPT pro v5 P0-1 fix: 还需 state.commodity_routes 验 cross-partition.
        if state.commodity_routes is None:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    "F2 cutset validator 需 state.commodity_routes registry "
                    "(GPT pro v5 P0-1 — 验 route 真跨 partition)"
                ),
            )
        # 6a. cert.contributing_commodities 必跟 state.commodity_demands 一致
        contributing = cert_dict.get("contributing_commodities", [])
        if not contributing:
            return ValidationResult(
                kind="schema_err",
                elapsed_seconds=time.monotonic() - t0,
                detail="F2 cert missing contributing_commodities",
            )
        # 6b. GPT pro v5 P0-1 fix: contributing 不允 duplicate. spec §2 commodity
        # 集合语义不是 multiset, 同 id 重复算 demand 是数学 unsound.
        # 反例: contributing=["c","c"], demand_R 被翻倍.
        seen_commodities: set = set()
        for c in contributing:
            if c in seen_commodities:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"duplicate contributing commodity {c!r} (spec §2 集合语义)",
                )
            seen_commodities.add(c)
        # 6c. 任一 commodity 必真在 registry (防 fake commodity_id)
        for c in contributing:
            if c not in state.commodity_demands:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"contributing commodity {c!r} not in commodity_demands registry",
                )
            if c not in state.commodity_routes:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"contributing commodity {c!r} not in commodity_routes registry",
                )
        # 6d. GPT pro v5 P0-1 fix: 每个 contributing commodity 的 route 必跨 partition
        # (src 在 A sink 在 B 或反). 反例: route src=sink=(0,0) (都在 A), validator
        # 之前接受 ok → 实际 cross-partition demand=0, cert demand=2 假证. spec §1
        # demand 是跨 cut 路径需求, 同 side route 不该贡献.
        for c in contributing:
            route = state.commodity_routes[c]
            r_src = tuple(route.get("src", ()))
            r_sink = tuple(route.get("sink", ()))
            in_a_src, in_b_src = r_src in side_a, r_src in side_b
            in_a_sink, in_b_sink = r_sink in side_a, r_sink in side_b
            crosses = (in_a_src and in_b_sink) or (in_b_src and in_a_sink)
            if not crosses:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"commodity {c!r} route 不跨 partition: "
                        f"src={r_src} sink={r_sink}, 不满足 spec §1 cross-cut 需求"
                    ),
                )
        # 6e. demand sum from registry == cert.commodity_demand (去重后)
        registry_demand = sum(state.commodity_demands[c] for c in seen_commodities)
        commodity_demand = cert_dict["commodity_demand"]
        if registry_demand != commodity_demand:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"commodity_demand mismatch: cert={commodity_demand}, "
                    f"registry sum={registry_demand} (commodities={sorted(seen_commodities)})"
                ),
            )
        # 7. Witness: demand > cut_size
        if commodity_demand <= cert_cut_size:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"witness fail: demand={commodity_demand} ≤ cut_size={cert_cut_size}",
            )

        # max_flow_LP algebraic check defer Phase 1.5+ (spec §7 verify_max_flow_witness)

        return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - t0)

    except Exception as e:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate_geometric_cutset(cut: Cut, state: BState) -> bool:
    """Hot path: re-check Menger violation on current free_cells.

    GPT pro v2 round 2 fix: 原版只重算 cut_edges, 漏验 partition enclosure. 反例:
    initial state patch 被 ghost 围住, validator OK; 后续 state 旁边 free cell 打
    开, 流可绕路 → validator 报 unsound, 但 evaluator 仍返 True. hot path 必须
    同步验 (A∪B) ⊆ free + enclosure (跟 validator step 2/3 一致).

    Returns True iff cut 仍 violating (partition 闭合 + demand > current_cut_size).
    """
    if cut.geometric_payload is None:
        return False  # fail-safe: schema 缺失不报 violate
    cert_dict = json.loads(cut.geometric_payload)
    side_a = _decode_bitset(cert_dict["side_a_bitset_b64"])
    side_b = _decode_bitset(cert_dict["side_b_bitset_b64"])
    free_cells = _free_cells(state)
    patch = side_a | side_b
    # partition cells must remain free (cell_owner / ghost 变化后 partition 失效)
    if patch - free_cells:
        return False
    # patch enclosure: state 变化引入 patch 外 free cell 让流绕路 → 不再 violating
    if _has_patch_escape(patch, free_cells):
        return False
    current_edges = _cross_partition_edges(side_a, side_b, free_cells)
    return cert_dict["commodity_demand"] > len(current_edges)

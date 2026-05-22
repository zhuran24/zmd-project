"""Family 4 component_reach — production validator + evaluator.

Implements cut_family_specs/04_component_reach.md v1.1.

Phase 1.1 P1.8 scope (minimum viable):
- ``validate_component_reach(cut, state, canonical_rules)`` — 3 步 check
  (per v1.1 Gemini round 16 A1: geometric 只认 spatial 不校验 blocking pose ID):
  1. src_component ∩ sink_component == ∅ (partition disjoint).
  2. src_cell ∈ src_component, sink_cell ∈ sink_component (membership).
  3. Recompute BFS components on current free_cells; src/sink仍 disconnected.
- ``evaluate_geometric_component_reach(cut, state)`` — hot path 重算 BFS,
  True iff disconnect still holds.

Phase 1.5+ extends:
- Wrap src/search/d2_separator.py for generator (compute_bfs_components +
  find_separator).
- ghost-cause vs cell_owner-cause sub-kinds (类 F7 causation split).
- Multi-commodity reachability matrix (cf Family 2).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md v1.1
"""
from __future__ import annotations

import json
import time
from collections import deque
from typing import Dict, FrozenSet, Set

from src.cuts.families.cutset import _decode_bitset, _free_cells
from src.cuts.lifecycle import BState, Cell, Cut, ValidationResult


def _bfs_component(start: Cell, free_cells: FrozenSet[Cell]) -> Set[Cell]:
    """4-neighborhood BFS over free_cells from start."""
    if start not in free_cells:
        return set()
    visited = {start}
    q: deque[Cell] = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = (x + dx, y + dy)
            if neighbor in free_cells and neighbor not in visited:
                visited.add(neighbor)
                q.append(neighbor)
    return visited


def validate_component_reach(
    cut: Cut,
    state: BState,
    canonical_rules: Dict,
) -> ValidationResult:
    """F4 component_reach validator.

    Phase 1.1 P1.8 minimum-viable per v1.1 (Gemini r16 A1 fix): geometric mode
    only verifies **spatial** invariants, NOT blocking_facilities 具体 pose ID
    (causation split is literal-based, not geometric — F3/F7's territory).

    GPT pro round 2 fix: schema check 走 explicit if (`python -O` 防线).
    """
    t0 = time.monotonic()
    if cut.geometric_payload is None:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail="cut.geometric_payload is None (F4 schema invariant violated)",
        )
    try:
        cert_dict = json.loads(cut.geometric_payload)
        src_cell = tuple(cert_dict["src_cell"])
        sink_cell = tuple(cert_dict["sink_cell"])
        src_comp = _decode_bitset(cert_dict["src_component_bitset_b64"])
        sink_comp = _decode_bitset(cert_dict["sink_component_bitset_b64"])

        # 1. Partition disjoint (src and sink not in same component per cert)
        if src_comp & sink_comp:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"src/sink components 重叠 |∩|={len(src_comp & sink_comp)}",
            )

        # 2. Membership: src_cell ∈ src_comp, sink_cell ∈ sink_comp
        if src_cell not in src_comp:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"src_cell {src_cell} not in src_component",
            )
        if sink_cell not in sink_comp:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"sink_cell {sink_cell} not in sink_component",
            )

        # 3. Recompute BFS components on current free_cells; verify still disconnect
        free_cells = _free_cells(state)
        if src_cell not in free_cells:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"src_cell {src_cell} no longer in free_cells (cell_owner/ghost changed)",
            )
        if sink_cell not in free_cells:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"sink_cell {sink_cell} no longer in free_cells",
            )

        # 4. cert.src_component == recomputed BFS(src_cell) (GPT pro round 2 cert
        # 完整性: attacker 不准谎报 src_component 含 sink_cell 邻接 cell — validator
        # 必精确等). Spec 04_component_reach.md §6 cert bitset 必须可独立重算.
        current_src_comp = frozenset(_bfs_component(src_cell, free_cells))
        if current_src_comp != src_comp:
            extra = src_comp - current_src_comp
            missing = current_src_comp - src_comp
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"src_component cert mismatch: |cert|={len(src_comp)}, "
                    f"|recomputed|={len(current_src_comp)}, extra_in_cert={len(extra)}, "
                    f"missing_in_cert={len(missing)}"
                ),
            )

        # 5. cert.sink_component == recomputed BFS(sink_cell) (同上)
        current_sink_comp = frozenset(_bfs_component(sink_cell, free_cells))
        if current_sink_comp != sink_comp:
            extra = sink_comp - current_sink_comp
            missing = current_sink_comp - sink_comp
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=(
                    f"sink_component cert mismatch: |cert|={len(sink_comp)}, "
                    f"|recomputed|={len(current_sink_comp)}, extra_in_cert={len(extra)}, "
                    f"missing_in_cert={len(missing)}"
                ),
            )

        # 6. Witness: sink not in src component (Menger min-cut > 0 已经隐含)
        if sink_cell in current_src_comp:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail="witness fail: src/sink now reachable (free_cells changed reconnect)",
            )

        # 7. separator_cells 全在 cell_owner ∪ ghost (不是 free) — spec 04 line 148
        # GPT pro v2 round 2 High fix: 原 Gemini r33 修法只验 not-in-free, 漏验
        # in-grid + explicit ∈ cell_owner ∪ ghost. attacker 放 (999,999) 等
        # out-of-grid cell, 既不在 free 也不在任何集合 → silent pass. 防御策略:
        # 显式 ⊆ (cell_owner ∪ ghost) ∩ in-grid.
        separator_cells = cert_dict.get("separator_cells", [])
        for sep_cell_raw in separator_cells:
            sep_cell = tuple(sep_cell_raw)
            # 7a. in-grid (70x70 hardcoded per project grid 约定)
            if not (
                len(sep_cell) == 2
                and isinstance(sep_cell[0], int) and isinstance(sep_cell[1], int)
                and 0 <= sep_cell[0] < 70 and 0 <= sep_cell[1] < 70
            ):
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=f"separator cell {sep_cell} not in grid (0-69 x 0-69)",
                )
            # 7b. ∈ cell_owner ∪ ghost (explicit positive check, 不只 not-in-free)
            if sep_cell not in state.cell_owner and sep_cell not in state.ghost_cells:
                return ValidationResult(
                    kind="unsound",
                    elapsed_seconds=time.monotonic() - t0,
                    detail=(
                        f"separator cell {sep_cell} not in cell_owner ∪ ghost_cells "
                        f"(spec 04_component_reach.md line 148)"
                    ),
                )

        # 8. commodity_id (spec 04 §3 line 50 必填字段, allowed but verifier defer).
        #
        # Gemini round 34 High 升级 fix: 原 Step D fail-closed (schema_err on
        # carry) 跟 spec 必填字段冲突 — Phase 1.5+ Oracle 按 spec 输出后 100%
        # F4 cut Quarantine 瘫痪. 改 spec-aligned 允许 carry.
        #
        # Soundness 不依赖 commodity_id: 当前 v1.1 minimum-viable 是 geometric-only
        # (BFS connectivity 不看 commodity name). attacker 塞 fake commodity_id
        # 不影响 src/sink_component bitset 重算严等 + separator_cells 验. cert
        # 几何 soundness 由 step 4-7 保证.
        #
        # commodity_id 作 metadata (causation tracing / debug audit) 通过. Phase
        # 1.5+ commodity_route assumption verifier 落地后再 enforce 真验存在.
        # 防 attacker 借此 metadata field spread misinfo — 当前 acceptable risk
        # (metadata 不入 cut application 真证明路径).

        return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - t0)

    except Exception as e:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate_geometric_component_reach(cut: Cut, state: BState) -> bool:
    """Hot path: recompute BFS reachability on current free_cells.

    **Phase 1.1 scope**: 此函数在 lifecycle.step_7_evaluate_cut 调用一次/cut
    (post-attach), 不在 CP-SAT propagator 真 hot path. 4900-cell BFS 单调
    ms 级内, ≤ 1/cut/iter 不构成 bottleneck.

    **Phase 1.3 P1.21 必修 (defer)** — Gemini round 35 perf hypothesis:
    若 Phase 1.3 接 CP-SAT propagator 真 hot path (10K calls/sec), 必须改
    incremental connectivity check (e.g. union-find with rollback, 或 cache
    last-known component bitset 比 dirty-flag check). 当前 O(|Grid|) BFS 当
    Phase 1.3 集成时数量级退化.

    Returns True iff src/sink still disconnected (cut still violating).
    """
    if cut.geometric_payload is None:
        return False  # fail-safe: schema 缺失不报 violate
    cert_dict = json.loads(cut.geometric_payload)
    src_cell = tuple(cert_dict["src_cell"])
    sink_cell = tuple(cert_dict["sink_cell"])
    free_cells = _free_cells(state)
    if src_cell not in free_cells or sink_cell not in free_cells:
        # Either endpoint no longer free — cut soundness violated; eval False
        return False
    current_src_comp = _bfs_component(src_cell, free_cells)
    return sink_cell not in current_src_comp

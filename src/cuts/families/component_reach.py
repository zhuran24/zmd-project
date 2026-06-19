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
from typing import Any, Dict, FrozenSet, Literal, Set

from src.cuts.families.cutset import _decode_bitset, _free_cells, _parse_cell
from src.cuts.lifecycle import BState, Cell, Cut, ValidationResult, validate_cert_payload


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


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def _validate_component_scope(cut: Cut, t0: float) -> ValidationResult | None:
    from src.cuts.lifecycle import GHOST_AGNOSTIC

    if cut.scope is not None and cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return _vr("unsound", t0, "F4 component_reach 不允 GHOST_AGNOSTIC scope")
    return None


def _validate_component_membership(
    src_cell: Cell,
    sink_cell: Cell,
    src_comp: FrozenSet[Cell],
    sink_comp: FrozenSet[Cell],
    t0: float,
) -> ValidationResult | None:
    if src_comp & sink_comp:
        return _vr("unsound", t0, f"src/sink components 重叠 |∩|={len(src_comp & sink_comp)}")
    if src_cell not in src_comp:
        return _vr("unsound", t0, f"src_cell {src_cell} not in src_component")
    if sink_cell not in sink_comp:
        return _vr("unsound", t0, f"sink_cell {sink_cell} not in sink_component")
    return None


def _validate_recomputed_components(
    src_cell: Cell,
    sink_cell: Cell,
    src_comp: FrozenSet[Cell],
    sink_comp: FrozenSet[Cell],
    state: BState,
    t0: float,
) -> ValidationResult | None:
    free_cells = _free_cells(state)
    if src_cell not in free_cells:
        return _vr("unsound", t0, f"src_cell {src_cell} no longer in free_cells")
    if sink_cell not in free_cells:
        return _vr("unsound", t0, f"sink_cell {sink_cell} no longer in free_cells")
    current_src_comp = frozenset(_bfs_component(src_cell, free_cells))
    if current_src_comp != src_comp:
        return _vr(
            "unsound",
            t0,
            f"src_component cert mismatch: |cert|={len(src_comp)}, |recomputed|={len(current_src_comp)}",
        )
    current_sink_comp = frozenset(_bfs_component(sink_cell, free_cells))
    if current_sink_comp != sink_comp:
        return _vr(
            "unsound",
            t0,
            f"sink_component cert mismatch: |cert|={len(sink_comp)}, |recomputed|={len(current_sink_comp)}",
        )
    if sink_cell in current_src_comp:
        return _vr("unsound", t0, "witness fail: src/sink now reachable")
    return None


def _validate_separator_cells(
    separator_cells: object,
    state: BState,
    t0: float,
) -> ValidationResult | None:
    if not isinstance(separator_cells, list):
        return _vr("schema_err", t0, "separator_cells must be a list")
    for idx, sep_cell_raw in enumerate(separator_cells):
        try:
            sep_cell = _parse_cell(sep_cell_raw, f"separator_cells[{idx}]")
        except ValueError as e:
            if "out of grid" in str(e):
                return _vr("unsound", t0, f"separator cell {sep_cell_raw!r} not in grid (0-69 x 0-69)")
            return _vr("schema_err", t0, str(e))
        if sep_cell not in state.cell_owner and sep_cell not in state.ghost_cells:
            return _vr("unsound", t0, f"separator cell {sep_cell} not in cell_owner ∪ ghost_cells")
    return None


def _validate_component_commodity(
    commodity_id: object,
    src_cell: Cell,
    sink_cell: Cell,
    state: BState,
    t0: float,
) -> ValidationResult | None:
    if not isinstance(commodity_id, str) or commodity_id == "":
        return _vr("schema_err", t0, "F4 cert missing/non-string commodity_id (spec 04 §3 必填)")
    if state.commodity_routes is None:
        return _vr("schema_err", t0, "F4 component_reach validator 需 state.commodity_routes registry")
    route = state.commodity_routes.get(commodity_id)
    if route is None:
        return _vr("unsound", t0, f"commodity_id {commodity_id!r} not in commodity_routes registry")
    try:
        registry_src = _parse_cell(route.get("src"), f"commodity_routes[{commodity_id!r}].src")
        registry_sink = _parse_cell(route.get("sink"), f"commodity_routes[{commodity_id!r}].sink")
    except ValueError as e:
        return _vr("schema_err", t0, str(e))
    if registry_src != src_cell:
        return _vr("unsound", t0, f"src_cell mismatch: cert={src_cell}, registry route src={registry_src}")
    if registry_sink != sink_cell:
        return _vr("unsound", t0, f"sink_cell mismatch: cert={sink_cell}, registry route sink={registry_sink}")
    return None


def validate_component_reach(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """F4 component_reach validator."""
    t0 = time.monotonic()
    del canonical_rules
    if cut.geometric_payload is None:
        return _vr("schema_err", t0, "cut.geometric_payload is None (F4 schema invariant violated)")
    try:
        cert_dict = validate_cert_payload("component_reach", cut.geometric_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))
    scope_error = _validate_component_scope(cut, t0)
    if scope_error is not None:
        return scope_error
    try:
        src_cell = _parse_cell(cert_dict.get("src_cell"), "src_cell")
        sink_cell = _parse_cell(cert_dict.get("sink_cell"), "sink_cell")
        src_comp = _decode_bitset(cert_dict["src_component_bitset_b64"])
        sink_comp = _decode_bitset(cert_dict["sink_component_bitset_b64"])
        for error in (
            _validate_component_membership(src_cell, sink_cell, src_comp, sink_comp, t0),
            _validate_recomputed_components(src_cell, sink_cell, src_comp, sink_comp, state, t0),
            _validate_separator_cells(cert_dict.get("separator_cells", []), state, t0),
            _validate_component_commodity(cert_dict.get("commodity_id"), src_cell, sink_cell, state, t0),
        ):
            if error is not None:
                return error
        return _vr("ok", t0)
    except Exception as e:
        return _vr("schema_err", t0, f"{type(e).__name__}: {e}")

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
    try:
        cert_dict = json.loads(cut.geometric_payload)
        src_cell = _parse_cell(cert_dict.get("src_cell"), "src_cell")
        sink_cell = _parse_cell(cert_dict.get("sink_cell"), "sink_cell")
    except Exception:
        return False
    free_cells = _free_cells(state)
    if src_cell not in free_cells or sink_cell not in free_cells:
        # Either endpoint no longer free — cut soundness violated; eval False
        return False
    current_src_comp = _bfs_component(src_cell, free_cells)
    return sink_cell not in current_src_comp

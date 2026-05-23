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
from typing import Any, Dict, FrozenSet, Literal, Tuple

from src.cuts.lifecycle import BState, Cell, Cut, ValidationResult


# Cross-partition edge between two adjacent cells (Manhattan 4-neighborhood).
PartitionEdge = Tuple[Cell, Cell]


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_cell(raw: object, field_name: str, grid_size: int = 70) -> Cell:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"{field_name} must be a length-2 cell")
    x_raw, y_raw = raw
    if not _is_strict_int(x_raw) or not _is_strict_int(y_raw):
        raise ValueError(f"{field_name} must contain strict ints, got {raw!r}")
    x = int(x_raw)
    y = int(y_raw)
    if not (0 <= x < grid_size and 0 <= y < grid_size):
        raise ValueError(f"{field_name} out of grid: {(x, y)!r}")
    return (x, y)


def _decode_bitset(b64: str, grid_size: int = 70) -> FrozenSet[Cell]:
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


def _free_cells(state: BState, grid_size: int = 70) -> FrozenSet[Cell]:
    """Belt-usable cells: all grid cells minus ghost/exterior/occupied cells.

    F2/F4 reason over routes. ``exterior_blocks`` are forbidden just like ghost
    cells; ignoring them would let replay validate a path through static blocks.
    """
    all_cells = {(x, y) for x in range(grid_size) for y in range(grid_size)}
    return frozenset(
        all_cells
        - set(state.ghost_cells)
        - set(state.exterior_blocks)
        - set(state.cell_owner.keys())
    )


def _cross_partition_edges(
    side_a: FrozenSet[Cell],
    side_b: FrozenSet[Cell],
    free_cells: FrozenSet[Cell],
) -> FrozenSet[PartitionEdge]:
    """Return undirected edges (a, b) where a ∈ A, b ∈ B, both ∈ free_cells, and
    a/b Manhattan-adjacent. Canonicalize order (smaller first) to dedupe."""
    edges: set[PartitionEdge] = set()
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


def _canonical_edges_from_cert(raw_edges: object) -> FrozenSet[PartitionEdge]:
    parsed: set[PartitionEdge] = set()
    if not isinstance(raw_edges, list):
        raise ValueError("cut_edges must be a list")
    for raw in raw_edges:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError(f"bad cut edge entry: {raw!r}")
        c1_raw, c2_raw = raw
        c1 = _parse_cell(c1_raw, "cut_edges.cell_a")
        c2 = _parse_cell(c2_raw, "cut_edges.cell_b")
        edge = (c1, c2) if c1 <= c2 else (c2, c1)
        parsed.add(edge)
    return frozenset(parsed)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def _validate_cutset_scope(cut: Cut, t0: float) -> ValidationResult | None:
    from src.cuts.lifecycle import GHOST_AGNOSTIC

    if cut.scope is not None and cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return _vr("unsound", t0, "F2 cutset 不允 GHOST_AGNOSTIC scope")
    return None


def _validate_partition_geometry(
    side_a: FrozenSet[Cell],
    side_b: FrozenSet[Cell],
    free_cells: FrozenSet[Cell],
    t0: float,
) -> ValidationResult | None:
    if side_a & side_b:
        return _vr("unsound", t0, f"partition not disjoint (|A ∩ B|={len(side_a & side_b)})")
    patch = side_a | side_b
    non_free = patch - free_cells
    if non_free:
        return _vr("unsound", t0, f"partition contains {len(non_free)} non-free cell(s): sample={sorted(non_free)[:3]}")
    if _has_patch_escape(patch, free_cells):
        return _vr("unsound", t0, "partition not enclosed: patch has adjacent outside free cell")
    return None


def _validate_cut_edges(
    cert_dict: Dict[str, Any],
    side_a: FrozenSet[Cell],
    side_b: FrozenSet[Cell],
    free_cells: FrozenSet[Cell],
    t0: float,
) -> tuple[ValidationResult | None, int]:
    current_cut_edges = _cross_partition_edges(side_a, side_b, free_cells)
    if "cut_edges" not in cert_dict:
        return _vr("schema_err", t0, "cert missing cut_edges field"), 0
    cert_cut_size = int(cert_dict["cut_size"])
    if len(current_cut_edges) != cert_cut_size:
        return _vr("unsound", t0, f"cut_size mismatch: cert={cert_cut_size}, recomputed={len(current_cut_edges)}"), cert_cut_size
    cert_edges = _canonical_edges_from_cert(cert_dict.get("cut_edges", []))
    if cert_edges != current_cut_edges:
        return _vr("unsound", t0, "cut_edges set mismatch against recomputed cross-partition edges"), cert_cut_size
    return None, cert_cut_size


def _validate_cutset_registries(state: BState, t0: float) -> ValidationResult | None:
    if state.commodity_demands is None:
        return _vr("schema_err", t0, "F2 cutset validator 需 state.commodity_demands registry")
    if state.commodity_routes is None:
        return _vr("schema_err", t0, "F2 cutset validator 需 state.commodity_routes registry")
    return None


def _validate_contributing_commodities(
    contributing: object,
    state: BState,
    t0: float,
) -> tuple[ValidationResult | None, set[str]]:
    if not isinstance(contributing, list) or not contributing:
        return _vr("schema_err", t0, "F2 cert missing contributing_commodities"), set()
    if state.commodity_demands is None or state.commodity_routes is None:
        return _vr("schema_err", t0, "F2 commodity registries missing after registry gate"), set()
    commodity_demands = state.commodity_demands
    commodity_routes = state.commodity_routes
    seen: set[str] = set()
    for raw_c in contributing:
        c = str(raw_c)
        if c in seen:
            return _vr("unsound", t0, f"duplicate contributing commodity {c!r} (spec §2 集合语义)"), seen
        seen.add(c)
        if c not in commodity_demands:
            return _vr("unsound", t0, f"contributing commodity {c!r} not in commodity_demands registry"), seen
        if c not in commodity_routes:
            return _vr("unsound", t0, f"contributing commodity {c!r} not in commodity_routes registry"), seen
    return None, seen


def _validate_cross_partition_routes(
    commodities: set[str],
    side_a: FrozenSet[Cell],
    side_b: FrozenSet[Cell],
    state: BState,
    t0: float,
) -> ValidationResult | None:
    if state.commodity_routes is None:
        return _vr("schema_err", t0, "F2 commodity_routes missing after registry gate")
    commodity_routes = state.commodity_routes
    for c in commodities:
        route = commodity_routes[c]
        r_src = _parse_cell(route.get("src"), f"commodity_routes[{c!r}].src")
        r_sink = _parse_cell(route.get("sink"), f"commodity_routes[{c!r}].sink")
        crosses = (r_src in side_a and r_sink in side_b) or (r_src in side_b and r_sink in side_a)
        if not crosses:
            return _vr("unsound", t0, f"commodity {c!r} route 不跨 partition: src={r_src} sink={r_sink}")
    return None


def _validate_commodity_demand(
    cert_dict: Dict[str, Any],
    commodities: set[str],
    cert_cut_size: int,
    state: BState,
    t0: float,
) -> ValidationResult | None:
    if state.commodity_demands is None:
        return _vr("schema_err", t0, "F2 commodity_demands missing after registry gate")
    commodity_demands = state.commodity_demands
    registry_demand = sum(commodity_demands[c] for c in commodities)
    commodity_demand = int(cert_dict["commodity_demand"])
    if registry_demand != commodity_demand:
        return _vr("unsound", t0, f"commodity_demand mismatch: cert={commodity_demand}, registry sum={registry_demand}")
    if commodity_demand <= cert_cut_size:
        return _vr("unsound", t0, f"witness fail: demand={commodity_demand} ≤ cut_size={cert_cut_size}")
    return None


def validate_cutset(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """Production F2 validator."""
    t0 = time.monotonic()
    del canonical_rules
    if cut.geometric_payload is None:
        return _vr("schema_err", t0, "cut.geometric_payload is None (F2 schema invariant violated)")
    scope_error = _validate_cutset_scope(cut, t0)
    if scope_error is not None:
        return scope_error
    try:
        cert_dict: Dict[str, Any] = json.loads(cut.geometric_payload)
        side_a = _decode_bitset(cert_dict["side_a_bitset_b64"])
        side_b = _decode_bitset(cert_dict["side_b_bitset_b64"])
        free_cells = _free_cells(state)
        for error in (
            _validate_partition_geometry(side_a, side_b, free_cells, t0),
            _validate_cutset_registries(state, t0),
        ):
            if error is not None:
                return error
        edge_error, cert_cut_size = _validate_cut_edges(cert_dict, side_a, side_b, free_cells, t0)
        if edge_error is not None:
            return edge_error
        contributing_error, commodities = _validate_contributing_commodities(cert_dict.get("contributing_commodities"), state, t0)
        if contributing_error is not None:
            return contributing_error
        route_error = _validate_cross_partition_routes(commodities, side_a, side_b, state, t0)
        if route_error is not None:
            return route_error
        demand_error = _validate_commodity_demand(cert_dict, commodities, cert_cut_size, state, t0)
        if demand_error is not None:
            return demand_error
        return _vr("ok", t0)
    except Exception as e:
        return _vr("schema_err", t0, f"{type(e).__name__}: {e}")

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
    return bool(cert_dict["commodity_demand"] > len(current_edges))

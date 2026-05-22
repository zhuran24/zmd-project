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
from typing import Dict, FrozenSet, Tuple

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


def validate_cutset(
    cut: Cut,
    state: BState,
    canonical_rules: Dict,
) -> ValidationResult:
    """Production F2 validator.

    Checks:
    1. cert.side_a ∩ side_b == ∅ (partition disjoint)
    2. cur_cut_size = |cross_partition_edges(A, B, current_free_cells)| matches
       cert.cut_size (signal that cell_owner change invalidates this cut).
    3. commodity_demand > cut_size (witness Menger violation).

    GPT pro round 2 fix: schema check 走 explicit if (`python -O` 防线).
    """
    t0 = time.monotonic()
    if cut.geometric_payload is None:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail="cut.geometric_payload is None (F2 schema invariant violated)",
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

        # 2. Cross-partition edge count matches cert
        free_cells = _free_cells(state)
        recomputed_edges = _cross_partition_edges(side_a, side_b, free_cells)
        recomputed_cut_size = len(recomputed_edges)
        cert_cut_size = cert_dict["cut_size"]
        if recomputed_cut_size != cert_cut_size:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail=f"cut_size mismatch: cert={cert_cut_size}, recomputed={recomputed_cut_size}",
            )

        # 3. Witness: demand > cut_size
        commodity_demand = cert_dict["commodity_demand"]
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

    Returns True iff demand > current_cut_size (cut still violating).
    """
    if cut.geometric_payload is None:
        return False  # fail-safe: schema 缺失不报 violate
    cert_dict = json.loads(cut.geometric_payload)
    side_a = _decode_bitset(cert_dict["side_a_bitset_b64"])
    side_b = _decode_bitset(cert_dict["side_b_bitset_b64"])
    free_cells = _free_cells(state)
    current_edges = _cross_partition_edges(side_a, side_b, free_cells)
    return cert_dict["commodity_demand"] > len(current_edges)

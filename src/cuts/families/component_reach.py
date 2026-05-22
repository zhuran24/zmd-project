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
    """
    assert cut.geometric_payload is not None
    t0 = time.monotonic()
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

        current_src_comp = _bfs_component(src_cell, free_cells)
        if sink_cell in current_src_comp:
            return ValidationResult(
                kind="unsound",
                elapsed_seconds=time.monotonic() - t0,
                detail="witness fail: src/sink now reachable (free_cells changed reconnect)",
            )

        return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - t0)

    except Exception as e:
        return ValidationResult(
            kind="schema_err",
            elapsed_seconds=time.monotonic() - t0,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate_geometric_component_reach(cut: Cut, state: BState) -> bool:
    """Hot path: recompute BFS reachability on current free_cells.

    Returns True iff src/sink still disconnected (cut still violating).
    """
    assert cut.geometric_payload is not None
    cert_dict = json.loads(cut.geometric_payload)
    src_cell = tuple(cert_dict["src_cell"])
    sink_cell = tuple(cert_dict["sink_cell"])
    free_cells = _free_cells(state)
    if src_cell not in free_cells or sink_cell not in free_cells:
        # Either endpoint no longer free — cut soundness violated; eval False
        return False
    current_src_comp = _bfs_component(src_cell, free_cells)
    return sink_cell not in current_src_comp

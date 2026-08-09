"""Phase 2 Task 5 — boundary equality constraints in RMP.

Phase 1 froze the `BoundarySignature` schema (perimeter ports + cells)
but did not enforce inter-column matching.  Phase 4 will hard-enforce
boundary-port equality for the routing layer.  Phase 2 implements the
*RMP-level* equality constraints + measures their dual sparsity, which
is the cheapest precursor evidence:

    For each (cell, dir) on shared bbox boundary between columns A
    and B:
        sum_{a covers cell on side A} λ_a * port_at(cell, dir, a)
        == sum_{b covers cell on side B} λ_b * port_at(cell, dir, b)

Phase 2 RMP encodes this as *per-cell-direction equality constraints*
(design decision in README §"boundary equality"):
    + Pro: per-cell granularity → routing-equivalent (Phase 4 can
      consume the same constraint structure).
    + Con: O(boundary_cells * 4 dirs) constraints (~ 70*70*4 = 19600
      slots worst case but realistically ~ 2-5K active).

Metric m17 = dual_sparsity = pct of boundary constraints with
non-zero dual at the LP optimum.  Threshold ≤ 30% (target ≤ 10%) —
high active rate predicts routing-layer infeasibility once Phase 4
adds the real constraint.

Phase 2 doesn't yet *block* infeasible boundary configurations — it
records the duals so we can verify the Phase 1 BoundarySignature
schema is the right shape before committing to the Phase 4 routing
build.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple


CellCoord = Tuple[int, int]
PortDir = str    # "N" | "S" | "E" | "W"
BoundaryKey = Tuple[int, int, str]   # (cell_x, cell_y, dir)


# === Helpers ===


def column_boundary_ports(
    pattern: Any,
) -> List[Tuple[int, int, str, str]]:
    """Return the column's perimeter typed ports.

    Reads `pattern.boundary_signature.perimeter_ports` (Phase 1 schema).
    """
    bsig = getattr(pattern, "boundary_signature", None)
    if bsig is None:
        return []
    return list(bsig.perimeter_ports)


def boundary_port_index(
    columns: Sequence[Any],
) -> Dict[BoundaryKey, List[Tuple[int, str]]]:
    """Index: (cell_x, cell_y, dir) -> [(column_idx, io_type), ...].

    Each entry tells us which columns expose a port at this
    boundary slot.  Used to construct the equality constraints.
    """
    idx: Dict[BoundaryKey, List[Tuple[int, str]]] = defaultdict(list)
    for k, col in enumerate(columns):
        for (cx, cy, pdir, io) in column_boundary_ports(col):
            idx[(cx, cy, pdir)].append((k, io))
    return idx


# === Equality constraints ===


@dataclass
class BoundaryEqualityResult:
    """Telemetry from one RMP solve with boundary equalities."""

    n_boundary_keys_total: int = 0
    n_boundary_constraints_added: int = 0
    n_active_constraints: int = 0    # |dual| > eps
    n_significant_constraints: int = 0  # |dual| >= 0.1
    duals_by_key: Dict[BoundaryKey, float] = field(default_factory=dict)
    dual_sparsity_pct: float = 0.0
    dual_active_pct: float = 0.0
    max_abs_dual: float = 0.0


# How boundary equality is encoded:
#   Let n_in(k, key) = 1 iff column k has an input port at `key`
#   Let n_out(k, key) = 1 iff column k has an output port at `key`
#   Constraint per key:
#       sum_k λ_k * (n_in(k, key) - n_out(k, key)) == 0
#   Interpretation: net flow at every boundary slot is zero (input
#   matches output).  Equivalent to "every shared cell has paired
#   input + output across the boundary".


def add_boundary_equality_constraints(
    solver: Any,
    lambda_vars: Sequence[Any],
    columns: Sequence[Any],
    *,
    name_prefix: str = "be",
) -> Tuple[Dict[BoundaryKey, Any], int]:
    """Add boundary equality constraints to a pywraplp solver.

    Each constraint forces net (input - output) flow at every boundary
    slot to zero.

    Returns (constraint_map, count) where constraint_map[key] is the
    pywraplp Constraint handle (used later to recover dual values).
    """
    idx = boundary_port_index(columns)
    ctrs: Dict[BoundaryKey, Any] = {}
    added = 0
    for key, members in idx.items():
        # Skip slots with only one direction (input or output) — can't
        # form an equality without both sides.
        ios = {io for (_k, io) in members}
        if len(ios) < 2:
            continue
        # Active member set: at least one input + one output column.
        ctr = solver.Constraint(0.0, 0.0, f"{name_prefix}_{key[0]}_{key[1]}_{key[2]}")
        for (k, io) in members:
            coeff = 1.0 if io == "input" else -1.0
            ctr.SetCoefficient(lambda_vars[k], coeff)
        ctrs[key] = ctr
        added += 1
    return ctrs, added


def collect_boundary_duals(
    constraint_map: Mapping[BoundaryKey, Any],
    *,
    nonzero_eps: float = 1e-7,
    significant_eps: float = 0.1,
) -> BoundaryEqualityResult:
    """Pull dual values from active boundary constraints."""
    res = BoundaryEqualityResult(
        n_boundary_constraints_added=len(constraint_map),
    )
    for key, ctr in constraint_map.items():
        try:
            dv = ctr.dual_value()
        except Exception:
            dv = 0.0
        res.duals_by_key[key] = dv
        if abs(dv) > nonzero_eps:
            res.n_active_constraints += 1
        if abs(dv) >= significant_eps:
            res.n_significant_constraints += 1
        if abs(dv) > res.max_abs_dual:
            res.max_abs_dual = abs(dv)
    n = max(1, res.n_boundary_constraints_added)
    res.dual_active_pct = 100.0 * res.n_active_constraints / n
    res.dual_sparsity_pct = 100.0 * res.n_significant_constraints / n
    return res


def boundary_keys_seen(columns: Sequence[Any]) -> int:
    """Total distinct (cell, dir) boundary slots across the column pool."""
    return len(boundary_port_index(columns))


__all__ = [
    "BoundaryKey",
    "BoundaryEqualityResult",
    "column_boundary_ports",
    "boundary_port_index",
    "add_boundary_equality_constraints",
    "collect_boundary_duals",
    "boundary_keys_seen",
]

"""Phase 1 column grammar — canonical Pattern + BoundarySignature (see README.md)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple


# --- type aliases (frozen, hashable) -----------------------------------------

CellCoord = Tuple[int, int]
PortTuple = Tuple[int, int, str, str]  # (cell_x, cell_y, dir, io_type)
FacilityAssignment = Tuple[str, str, int]  # (instance_id, facility_type, pose_idx)
RegionBBox = Tuple[int, int, int, int]   # (x_lo, y_lo, x_hi, y_hi)


# === Boundary signature schema (Phase 1: record, Phase 4: enforce) ===


@dataclass(frozen=True)
class BoundarySignature:
    """Column bbox perimeter ports + cells.  Phase 1 records; Phase 4 enforces."""

    perimeter_ports: Tuple[PortTuple, ...] = ()
    perimeter_cells: FrozenSet[CellCoord] = frozenset()

    def canonical_bytes(self) -> bytes:
        """Deterministic bytes for hashing (stable across Python sessions)."""
        parts: List[str] = []
        parts.append("ports:" + ";".join(
            f"{x},{y},{d},{io}" for (x, y, d, io) in self.perimeter_ports
        ))
        parts.append("cells:" + ";".join(
            f"{x},{y}" for (x, y) in sorted(self.perimeter_cells)
        ))
        return "|".join(parts).encode("utf-8")


def compute_boundary_signature(
    occupied_cells: FrozenSet[CellCoord],
    typed_ports: Sequence[PortTuple],
    region: RegionBBox,
) -> BoundarySignature:
    """Boundary signature: cells/ports on the bbox edge (region = column bbox)."""
    x_lo, y_lo, x_hi, y_hi = region
    on_perim_cells = frozenset(
        (x, y) for (x, y) in occupied_cells
        if x == x_lo or x == x_hi or y == y_lo or y == y_hi
    )
    on_perim_ports_list = [
        (x, y, d, io) for (x, y, d, io) in typed_ports
        if x == x_lo or x == x_hi or y == y_lo or y == y_hi
    ]
    # canonical sort (stable across runs).
    on_perim_ports_list.sort()
    return BoundarySignature(
        perimeter_ports=tuple(on_perim_ports_list),
        perimeter_cells=on_perim_cells,
    )


# === Pattern (canonical column) ===


def _canonical_column_id(
    facility_assignments: Sequence[FacilityAssignment],
    occupied_cells: FrozenSet[CellCoord],
) -> str:
    """Stable id = sha1(sorted facility_assignments | sorted cells)."""
    fa_sorted = sorted(facility_assignments)
    cells_sorted = sorted(occupied_cells)
    blob = "|".join([
        ",".join(f"{iid}:{tpl}:{p}" for (iid, tpl, p) in fa_sorted),
        ",".join(f"{x}:{y}" for (x, y) in cells_sorted),
    ])
    h = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
    return f"col_{h}"


@dataclass(frozen=True)
class Pattern:
    """Phase 1 canonical column (read-only). Equality / hash by column_id."""

    column_id: str
    occupied_cells: FrozenSet[CellCoord]
    facility_assignments: Tuple[FacilityAssignment, ...]
    port_cells: FrozenSet[CellCoord]
    typed_ports: Tuple[PortTuple, ...]
    boundary_signature: BoundarySignature
    region: RegionBBox
    cost: int = 1

    @property
    def covered_instance_ids(self) -> FrozenSet[str]:
        return frozenset(iid for (iid, _tpl, _p) in self.facility_assignments)

    @property
    def facility_count(self) -> int:
        return len(self.facility_assignments)

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash(self.column_id)

    def __eq__(self, other: object) -> bool:  # pragma: no cover - trivial
        return isinstance(other, Pattern) and self.column_id == other.column_id


def build_pattern(
    *,
    facility_assignments: Sequence[FacilityAssignment],
    occupied_cells: FrozenSet[CellCoord],
    typed_ports: Sequence[PortTuple],
    region: Optional[RegionBBox] = None,
    cost: int = 1,
) -> Pattern:
    """Canonical Pattern builder: sort assignments, compute id + boundary sig."""
    fa_sorted = tuple(sorted(facility_assignments))
    occ_frozen = frozenset(occupied_cells)
    port_cells_frozen = frozenset((x, y) for (x, y, _d, _io) in typed_ports)
    if region is None:
        if occ_frozen:
            xs = [x for (x, _y) in occ_frozen]
            ys = [y for (_x, y) in occ_frozen]
            region_use: RegionBBox = (min(xs), min(ys), max(xs), max(ys))
        else:
            region_use = (0, 0, 0, 0)
    else:
        region_use = region
    bsig = compute_boundary_signature(occ_frozen, typed_ports, region_use)
    cid = _canonical_column_id(fa_sorted, occ_frozen)
    return Pattern(
        column_id=cid,
        occupied_cells=occ_frozen,
        facility_assignments=fa_sorted,
        port_cells=port_cells_frozen,
        typed_ports=tuple(sorted(typed_ports)),
        boundary_signature=bsig,
        region=region_use,
        cost=cost,
    )


# === Equivalence class for integer validator (Phase 1 Task 2) ===


def assignment_equivalence_key(assignment: FacilityAssignment) -> Tuple[str, str]:
    """Equiv class = (iid, tpl); pose_idx label relaxed iff cells match (validator)."""
    iid, tpl, _pose_idx = assignment
    return (iid, tpl)


def assignment_strict_key(assignment: FacilityAssignment) -> Tuple[str, str, int]:
    """Strict (pose_idx-sensitive) key."""
    return tuple(assignment)  # type: ignore[return-value]


# === Public surface ===


__all__ = [
    "Pattern",
    "BoundarySignature",
    "build_pattern",
    "compute_boundary_signature",
    "assignment_equivalence_key",
    "assignment_strict_key",
    "CellCoord",
    "PortTuple",
    "FacilityAssignment",
    "RegionBBox",
]

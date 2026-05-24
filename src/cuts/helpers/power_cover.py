"""F7 power_hitting_set CoverSet helper.

Computes ``CoverSet(facility_pose, state)``: the set of pole anchor cells that
(a) host a 2×2 pole entirely within ``free_cells`` and (b) place at least one
of the pole's cells within ``pole_radius`` of at least one facility cell.

Two variants:
- ``compute_cover_set(...)``: pole anchors against the FULL free-cell mask
  (ghost ∪ exterior ∪ cell_owner blocked). Empty → facility has no power.
- ``compute_cover_set_ghost_only(...)``: pole anchors against the GHOST/EXTERIOR
  mask only (ignoring cell_owner). Used by F7 validator phase 7 to ensure the
  ghost is the true cause; if this set is non-empty but the full one is, the
  failure is a cell_owner causation case (defer Phase 1.5+ multi-literal).

Per ``canonical_rules.facility_templates.power_pole``: dimensions w=2, h=2.
``power_coverage_radius`` carries the Euclidean radius (cell units; no
explicit metric label in the schema, project consensus: Euclidean).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md v1.1
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F7
"""
from __future__ import annotations

import math
from typing import FrozenSet, Iterable, Tuple


Cell = Tuple[int, int]


_DEFAULT_GRID_SIZE: int = 70
_POLE_SIZE: int = 2  # canonical_rules.facility_templates.power_pole.dimensions.{w,h}


def _pole_cells(anchor: Cell, pole_size: int = _POLE_SIZE) -> Tuple[Cell, ...]:
    px, py = anchor
    return tuple((px + dx, py + dy) for dx in range(pole_size) for dy in range(pole_size))


def _min_cell_distance(facility_cell: Cell, anchor: Cell, pole_size: int = _POLE_SIZE) -> float:
    """Min Euclidean distance from one facility cell to any cell of a pole.

    A 2×2 pole at ``anchor`` occupies (anchor + (0..1, 0..1)). Coverage is
    computed cell-to-cell (cell centers are integer coordinates).
    """
    fx, fy = facility_cell
    px, py = anchor
    min_sq = (fx - px) ** 2 + (fy - py) ** 2
    for dx in range(pole_size):
        for dy in range(pole_size):
            sq = (fx - (px + dx)) ** 2 + (fy - (py + dy)) ** 2
            if sq < min_sq:
                min_sq = sq
    return math.sqrt(min_sq)


def _covers_any_facility_cell(
    anchor: Cell,
    facility_cells: Iterable[Cell],
    pole_radius: float,
    pole_size: int = _POLE_SIZE,
) -> bool:
    for fc in facility_cells:
        if _min_cell_distance(fc, anchor, pole_size) <= pole_radius:
            return True
    return False


def _enumerate_valid_pole_anchors(
    free_cells: FrozenSet[Cell],
    grid_size: int = _DEFAULT_GRID_SIZE,
    pole_size: int = _POLE_SIZE,
) -> Iterable[Cell]:
    """Iterate anchors whose 2×2 footprint lies entirely in ``free_cells``."""
    for px in range(grid_size - pole_size + 1):
        for py in range(grid_size - pole_size + 1):
            cells = _pole_cells((px, py), pole_size)
            if all(c in free_cells for c in cells):
                yield (px, py)


def compute_cover_set(
    facility_cells: Iterable[Cell],
    free_cells: FrozenSet[Cell],
    pole_radius: float,
    *,
    grid_size: int = _DEFAULT_GRID_SIZE,
    pole_size: int = _POLE_SIZE,
) -> FrozenSet[Cell]:
    """Return pole anchor cells covering ``facility_cells`` within ``pole_radius``.

    ``free_cells`` is the full mask (grid minus ghost, exterior, cell_owner).
    Empty result ⇒ facility cannot be powered in the current state.
    """
    facility_list = list(facility_cells)
    if not facility_list:
        return frozenset()
    if pole_radius <= 0.0:
        return frozenset()
    out: set[Cell] = set()
    for anchor in _enumerate_valid_pole_anchors(free_cells, grid_size, pole_size):
        if _covers_any_facility_cell(anchor, facility_list, pole_radius, pole_size):
            out.add(anchor)
    return frozenset(out)


def compute_cover_set_ghost_only(
    facility_cells: Iterable[Cell],
    ghost_cells: FrozenSet[Cell],
    exterior_blocks: FrozenSet[Cell],
    pole_radius: float,
    *,
    grid_size: int = _DEFAULT_GRID_SIZE,
    pole_size: int = _POLE_SIZE,
) -> FrozenSet[Cell]:
    """Variant of ``compute_cover_set`` that masks only ghost+exterior.

    Returns the CoverSet assuming ``cell_owner`` is empty — used by F7
    validator phase 7 to verify the failure cause is ghost-only (single
    literal cut is sound). If this set is non-empty but
    ``compute_cover_set(... full free_cells)`` is empty, then cell_owner
    is the true cause and the cert violates Phase 1.2's ``empty_coverset_ghost``
    invariant.
    """
    blocked = ghost_cells | exterior_blocks
    free = frozenset(
        (x, y)
        for x in range(grid_size)
        for y in range(grid_size)
        if (x, y) not in blocked
    )
    return compute_cover_set(
        facility_cells,
        free,
        pole_radius,
        grid_size=grid_size,
        pole_size=pole_size,
    )

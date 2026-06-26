"""F7 power_hitting_set CoverSet helper.

Computes ``CoverSet(facility_pose, state)``: the set of pole anchor cells that
(a) host a 2×2 pole entirely within ``free_cells`` and (b) place at least one
of the pole's cells within ``pole_radius`` of at least one facility cell.

Two variants:
- ``compute_cover_set(...)``: pole anchors against the FULL free-cell mask
  (ghost ∪ exterior ∪ cell_owner ∪ facility_cells blocked). Empty → facility
  has no power. Callers build the mask explicitly so the
  ``facility_cells`` exclusion (Gemini F7 round 1 BLOCKER #1 fix) is visible
  at each call site (validator phase 6/7 + oracle generator).

Per ``canonical_rules.facility_templates.power_pole``: dimensions w=2, h=2.
This helper uses the older F7/F8 Euclidean cell-distance model for
``power_coverage_radius``.  The active certified path and frozen candidate
geometry use the owner-confirmed 12x12 square coverage stencil instead
(``placement_generator.gen_power_pole`` and
``ExactCoordinateMaster._supports_rectangular_power_coverage``).  F7/F8 remain
non-certified / not applied to the master until P1.3 reconciles this landmine;
do not treat this helper as the canonical live coverage semantics.

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


def enumerate_valid_pole_anchors(
    free_cells: FrozenSet[Cell],
    *,
    grid_size: int = _DEFAULT_GRID_SIZE,
    pole_size: int = _POLE_SIZE,
) -> FrozenSet[Cell]:
    """Public: all pole anchors whose 2×2 footprint lies in ``free_cells``.

    F8 needs this to build the *full* power network (not just the CoverSet
    near a single facility) — Gemini F8 round 1 Finding #1.
    """
    return frozenset(_enumerate_valid_pole_anchors(free_cells, grid_size, pole_size))


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


# NOTE: ``compute_cover_set_ghost_only`` was retired Round 2 (Gemini F7
# round 2 LOW #3). Callers now inline the ghost-only mask construction
# (validator phase 7 + oracle generator) to make the "facility_cells must
# also be excluded" R1 fix explicit at the call site. The helper had no
# remaining callers and was removed to keep the module surface tight.

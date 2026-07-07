"""F7 power_hitting_set CoverSet helper.

Computes ``CoverSet(facility_pose, state)``: the set of pole anchor cells that
(a) host a 2×2 pole entirely within ``free_cells`` and (b) cover at least one
facility cell under the canonical 12×12 square coverage stencil.

Two variants:
- ``compute_cover_set(...)``: pole anchors against the FULL free-cell mask
  (ghost ∪ exterior ∪ cell_owner ∪ facility_cells blocked). Empty → facility
  has no power. Callers build the mask explicitly so the
  ``facility_cells`` exclusion (Gemini F7 round 1 BLOCKER #1 fix) is visible
  at each call site (validator phase 6/7 + oracle generator).

Coverage semantics (owner ruling 2026-07-08, M2 reconcile): the single
source-of-truth is the canonical 12×12 square stencil with intersection
predicate — a 2×2 pole anchored at ``(px, py)`` covers exactly the cells
``X ∈ [px-R, px+1+R], Y ∈ [py-R, py+1+R]`` with canonical
``power_coverage_radius R = 5`` (Chebyshev expansion of the pole footprint).
This is byte-for-byte the same rectangle as
``rules/canonical_rules.json:power_coverage_stencil``,
``placement_generator.gen_power_pole`` (frozen candidate geometry) and
``ExactCoordinateMaster._supports_rectangular_power_coverage`` (live master).
The pre-M2 Euclidean cell-distance model is retired and must not be
reintroduced anywhere on a certified path (see memory card
``p1-3-m2-coverage-stencil-ruling``).

Per ``canonical_rules.facility_templates.power_pole``: dimensions w=2, h=2.

Refs:
- rules/canonical_rules.json ``power_coverage_stencil`` (authoritative rectangle)
- docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md v1.1
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F7
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple


Cell = Tuple[int, int]


_DEFAULT_GRID_SIZE: int = 70
_POLE_SIZE: int = 2  # canonical_rules.facility_templates.power_pole.dimensions.{w,h}


def _pole_cells(anchor: Cell, pole_size: int = _POLE_SIZE) -> Tuple[Cell, ...]:
    px, py = anchor
    return tuple((px + dx, py + dy) for dx in range(pole_size) for dy in range(pole_size))


def _stencil_covers_cell(
    anchor: Cell,
    facility_cell: Cell,
    coverage_radius: float,
    pole_size: int = _POLE_SIZE,
) -> bool:
    """Canonical 12×12 square stencil membership for one facility cell.

    A ``pole_size × pole_size`` pole anchored at ``(px, py)`` covers the
    rectangle ``X ∈ [px-R, px+(pole_size-1)+R], Y ∈ [py-R, py+(pole_size-1)+R]``
    (Chebyshev distance ≤ R from the nearest pole cell). With the canonical
    R=5 and a 2×2 pole this is exactly the 12×12 stencil of
    ``placement_generator.gen_power_pole``.
    """
    fx, fy = facility_cell
    px, py = anchor
    reach = float(coverage_radius) + float(pole_size - 1)
    return (px - coverage_radius <= fx <= px + reach) and (
        py - coverage_radius <= fy <= py + reach
    )


def _covers_any_facility_cell(
    anchor: Cell,
    facility_cells: Iterable[Cell],
    pole_radius: float,
    pole_size: int = _POLE_SIZE,
) -> bool:
    for fc in facility_cells:
        if _stencil_covers_cell(anchor, fc, pole_radius, pole_size):
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
    """Return pole anchors whose 12×12 stencil intersects ``facility_cells``.

    ``pole_radius`` is the canonical ``power_coverage_radius`` (5), i.e. the
    stencil half-extent, NOT a Euclidean radius. ``free_cells`` is the full
    mask (grid minus ghost, exterior, cell_owner). Empty result ⇒ facility
    cannot be powered in the current state.
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

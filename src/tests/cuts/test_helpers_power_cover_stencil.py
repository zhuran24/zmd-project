"""M2 reconcile regressions — power_cover helper vs canonical 12×12 stencil.

Owner ruling 2026-07-08 (memory card ``p1-3-m2-coverage-stencil-ruling``):
the F7/F8 CoverSet helper must follow the canonical 12×12 square coverage
stencil (intersection predicate), byte-for-byte the same rectangle as
``rules/canonical_rules.json:power_coverage_stencil`` and
``placement_generator.gen_power_pole``. These tests pin that equivalence and
the divergence band where the retired Euclidean model gave the OPPOSITE
answer — the false-INFEASIBLE landmine that kept F7/F8 non-certified.

Pre-M2 the whole suite passed with the Euclidean helper because no case sat
in the square-vs-circle divergence band; the band cases below are therefore
load-bearing, do not delete them when refactoring.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import FrozenSet, Set, Tuple

import pytest

from src.cuts.helpers.power_cover import (
    _stencil_covers_cell,
    compute_cover_set,
)

Cell = Tuple[int, int]

_GRID = 70
_RADIUS = 5.0
_POLE = 2
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _helper_coverage_cells(anchor: Cell) -> Set[Cell]:
    """All in-grid cells the helper considers covered by ``anchor``."""
    return {
        (x, y)
        for x in range(_GRID)
        for y in range(_GRID)
        if _stencil_covers_cell(anchor, (x, y), _RADIUS, _POLE)
    }


def _canonical_rectangle_cells(anchor: Cell) -> Set[Cell]:
    """rules/canonical_rules.json power_coverage_stencil: X∈[x-5,x+6], Y∈[y-5,y+6], grid-clipped."""
    ax, ay = anchor
    return {
        (x, y)
        for x in range(max(0, ax - 5), min(_GRID, ax + 7))
        for y in range(max(0, ay - 5), min(_GRID, ay + 7))
    }


def _euclid_covers_cell(anchor: Cell, cell: Cell) -> bool:
    """The RETIRED pre-M2 model, reproduced here only to pin the divergence."""
    fx, fy = cell
    px, py = anchor
    best = min(
        math.sqrt((fx - (px + dx)) ** 2 + (fy - (py + dy)) ** 2)
        for dx in range(_POLE)
        for dy in range(_POLE)
    )
    return best <= _RADIUS


_SAMPLE_ANCHORS = (
    # corners / edges (grid clipping paths) + interior
    (0, 0), (0, 34), (68, 0), (68, 68), (5, 5), (6, 6),
    (30, 30), (34, 12), (12, 61), (61, 34), (20, 47), (47, 20),
)


@pytest.mark.parametrize("anchor", _SAMPLE_ANCHORS)
def test_helper_matches_canonical_rectangle(anchor: Cell) -> None:
    assert _helper_coverage_cells(anchor) == _canonical_rectangle_cells(anchor)


@pytest.mark.parametrize("anchor", [(0, 0), (30, 30), (68, 68)])
def test_helper_matches_placement_generator_coverage(anchor: Cell) -> None:
    """helper ↔ gen_power_pole: the frozen-candidate-geometry source of truth."""
    from src.placement.placement_generator import gen_power_pole

    by_anchor = {
        (p["anchor"]["x"], p["anchor"]["y"]): {
            tuple(c) for c in p["power_coverage_cells"]
        }
        for p in gen_power_pole()
    }
    assert _helper_coverage_cells(anchor) == by_anchor[anchor]


def test_canonical_rules_stencil_constants_unchanged() -> None:
    """Pin the canonical_rules fields this suite encodes (drift alarm)."""
    rules = json.loads(
        (_PROJECT_ROOT / "rules" / "canonical_rules.json").read_text(encoding="utf-8")
    )
    stencil = rules["semantics"]["power_coverage_stencil"]
    assert stencil["power_coverage_radius"] == 5
    assert stencil["anchor_footprint"] == {"w": 2, "h": 2}
    assert stencil["coverage_shape"]["kind"] == "axis_aligned_square"
    assert stencil["coverage_shape"]["width"] == 12
    assert stencil["coverage_shape"]["height"] == 12
    pole = rules["facility_templates"]["power_pole"]
    assert pole["power_coverage_radius"] == 5


def test_divergence_band_follows_stencil_not_euclid() -> None:
    """Diagonal band cells: stencil covers, retired Euclidean model did not.

    anchor (30,30), facility cell (36,36): Chebyshev distance to nearest pole
    cell (31,31) is 5 → inside the 12×12 stencil; Euclidean distance is
    √50 ≈ 7.07 > 5 → the retired model said "not covered". Pre-M2 this exact
    disagreement could mint a false-INFEASIBLE F7 cut killing a layout the
    certified master considers legal.
    """
    anchor = (30, 30)
    band = [(36, 36), (36, 25), (25, 36), (25, 25)]  # four stencil corners
    for cell in band:
        assert _stencil_covers_cell(anchor, cell, _RADIUS, _POLE), cell
        assert not _euclid_covers_cell(anchor, cell), cell
    # just outside the stencil in every direction: not covered
    for cell in [(37, 36), (36, 37), (24, 25), (25, 24), (37, 37), (24, 24)]:
        assert not _stencil_covers_cell(anchor, cell, _RADIUS, _POLE), cell


def test_euclid_coverage_implies_stencil_coverage() -> None:
    """Retired circle ⊂ canonical square: the swap only ever widens coverage.

    Guarantees the reconcile direction is monotone — no cell that the old
    model covered is lost, so no previously-sound emptiness witness becomes
    vacuously stronger.
    """
    anchor = (30, 30)
    for x in range(20, 41):
        for y in range(20, 41):
            if _euclid_covers_cell(anchor, (x, y)):
                assert _stencil_covers_cell(anchor, (x, y), _RADIUS, _POLE), (x, y)


def test_cover_set_divergence_band_end_to_end() -> None:
    """End-to-end defuse: a facility whose ONLY candidate anchor sits in the
    divergence band gets an empty CoverSet under the retired model (→ F7
    would cut = false-INFEASIBLE) but a non-empty one under the stencil.
    """
    facility_cells = ((36, 36),)
    anchor = (30, 30)
    free_cells: FrozenSet[Cell] = frozenset(
        (anchor[0] + dx, anchor[1] + dy) for dx in range(_POLE) for dy in range(_POLE)
    )
    cover = compute_cover_set(facility_cells, free_cells, _RADIUS)
    assert cover == frozenset({anchor})
    assert not _euclid_covers_cell(anchor, facility_cells[0])

"""W0 G1: the 25-region decomposition, its fixed furniture and its golden masks.

research-only.  These are the numbers every later stage divides by, so they are
pinned cell by cell rather than by count alone.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import g1_region_model as rm  # noqa: E402

pytestmark = pytest.mark.evidence

#: (name, multiplicity, fixed cells, reserved cells, usable cells)
GOLDEN_REGION_CLASSES = (
    ("BOTTOM_I1", 1, 14, 11, 171),
    ("BOTTOM_I2", 1, 14, 11, 171),
    ("BOTTOM_I3", 1, 14, 10, 172),
    ("BOTTOM_I4", 1, 14, 11, 171),
    ("CLEAN", 16, 0, 8, 188),
    ("CORE", 1, 95, 31, 70),
    ("CORNER", 1, 26, 12, 158),
    ("LEFT_J1", 1, 14, 11, 171),
    ("LEFT_J2", 1, 14, 11, 171),
    ("LEFT_J3", 1, 14, 10, 172),
)


def test_regions_tile_the_board_exactly() -> None:
    """[6] 25 regions, no gap, no overlap, 4900 cells."""
    covered: set[tuple[int, int]] = set()
    for i, j in rm.REGION_COORDS:
        cells = {
            rm.to_global((u, v), i, j)
            for u in range(rm.REGION_SIZE)
            for v in range(rm.REGION_SIZE)
        }
        assert not (cells & covered), f"T[{i},{j}] overlaps an earlier region"
        covered |= cells
    assert len(rm.REGION_COORDS) == 25
    assert len(covered) == 70 * 70
    assert covered == {(x, y) for x in range(70) for y in range(70)}


def test_fixed_furniture_cells_are_golden() -> None:
    """[7] 46 boundary ports (138 cells) + 1 core (81 cells) = 219, (0,0) free."""
    boundary = [f for f in rm.FIXED_FURNITURE if f.kind == "boundary_storage_port"]
    cores = [f for f in rm.FIXED_FURNITURE if f.kind == "protocol_core"]
    assert len(boundary) == 46
    assert len(cores) == 1
    assert cores[0].anchor == (3, 59)
    assert cores[0].size == (9, 9)
    assert cores[0].orientation == 1

    boundary_cells = {cell for item in boundary for cell in item.cells}
    assert boundary_cells == (
        {(0, y) for y in range(1, 70)} | {(x, 0) for x in range(1, 70)}
    )
    assert len(boundary_cells) == 138
    assert len(cores[0].cells) == 81
    assert len(rm.FIXED_CELLS) == 219
    assert (0, 0) not in rm.FIXED_CELLS


def test_reserved_front_cells_are_golden() -> None:
    """[8] 46 boundary + 20 core front cells, none of them inside a fixed body."""
    boundary_fronts = {
        cell
        for item in rm.FIXED_FURNITURE
        if item.kind == "boundary_storage_port"
        for cell in item.front_cells
    }
    core_fronts = {
        cell
        for item in rm.FIXED_FURNITURE
        if item.kind == "protocol_core"
        for cell in item.front_cells
    }
    assert boundary_fronts == (
        {(1, 2 + 3 * k) for k in range(23)} | {(2 + 3 * k, 1) for k in range(23)}
    )
    assert len(boundary_fronts) == 46
    assert core_fronts == (
        {(2, 59 + i) for i in range(1, 8)}
        | {(12, 59 + i) for i in range(1, 8)}
        | {(3 + i, 68) for i in (1, 4, 7)}
        | {(3 + i, 58) for i in (1, 4, 7)}
    )
    assert len(core_fronts) == 20
    assert len(rm.FIXED_FRONT_CELLS) == 66
    assert not (rm.FIXED_FRONT_CELLS & rm.FIXED_CELLS)


def test_region_class_table_is_golden() -> None:
    """[9] Ten classes with pinned masks; 4435 usable cells board-wide."""
    actual = tuple(
        (
            name,
            rm.REGION_CLASSES[name].multiplicity,
            len(rm.REGION_CLASSES[name].fixed_local),
            len(rm.REGION_CLASSES[name].reserved_local),
            rm.REGION_CLASSES[name].usable,
        )
        for name in rm.REGION_CLASS_ORDER
    )
    assert actual == GOLDEN_REGION_CLASSES
    assert rm.TOTAL_USABLE_CELLS == 4435
    assert sum(entry[1] for entry in GOLDEN_REGION_CLASSES) == 25


def test_clean_regions_share_one_translated_mask() -> None:
    """[9b] All 16 CLEAN regions are the same picture, which is the collapse."""
    clean = rm.REGION_CLASSES["CLEAN"]
    assert clean.multiplicity == 16
    assert clean.regions == tuple(
        (i, j) for i in range(1, 5) for j in range(1, 5)
    )
    assert clean.fixed_local == frozenset()
    assert clean.reserved_local == frozenset(rm.PORTAL_STUBS)
    for i, j in clean.regions:
        local_fixed = {
            rm.to_local(cell, i, j)
            for cell in rm.FIXED_CELLS
            if 14 * i <= cell[0] < 14 * i + 14 and 14 * j <= cell[1] < 14 * j + 14
        }
        assert local_fixed == frozenset()


def test_left_and_bottom_phases_are_genuinely_different() -> None:
    """[9c] Boundary period 3 against region period 14 gives three phases."""
    phases = {
        name: sorted(
            v for (u, v) in rm.REGION_CLASSES[name].fixed_front_local if u == 1
        )
        for name in ("LEFT_J1", "LEFT_J2", "LEFT_J3")
    }
    assert phases["LEFT_J1"] == [0, 3, 6, 9, 12]
    assert phases["LEFT_J2"] == [1, 4, 7, 10, 13]
    assert phases["LEFT_J3"] == [2, 5, 8, 11]


def test_portal_stubs_touch_across_every_internal_seam() -> None:
    """[10] R-PORTAL-FIXED's whole point: neighbours' stubs are 4-adjacent.

    That is what lets per-pattern connectivity compose into board-wide free-space
    connectivity with zero constraints in the master.
    """
    pairs = rm.stub_seam_pairs()
    # 4 internal seams per axis x 5 lanes x 2 stubs = 40 per axis.
    assert len(pairs) == 80
    for (ax, ay), (bx, by) in pairs:
        assert abs(ax - bx) + abs(ay - by) == 1, ((ax, ay), (bx, by))


def test_core_region_reserves_every_core_front() -> None:
    """[10b] All 20 core fronts plus 5 boundary fronts land in region T[0,4]."""
    core = rm.REGION_CLASSES["CORE"]
    assert core.regions == ((0, 4),)
    assert len(core.fixed_local) == 95  # 14 boundary column cells + 81 core cells
    assert len(core.fixed_front_local) == 25  # 20 core + 5 boundary
    assert len(core.live_stubs) == 6  # the two west stubs sit under the boundary

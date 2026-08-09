"""W0 front-aware G1: the 70x70 -> 25 region decomposition and its fixed furniture.

research-only.  No authority, no bound, no ledger effect.

The board is cut into the twenty-five 14x14 power cells of the W0 framework,
``T[i,j] = [14i, 14i+13] x [14j, 14j+13]``, which tile 70x70 exactly.  A *region*
is one such cell; the G1 catalog is generated per region **class**, not per
region, because the fixed furniture masks collapse 25 regions onto 10 classes.

Fixed furniture (outside the decision space, pinned by the W0 framework
``15_w0_recon_artifacts/W0_power_cycle_domino_framework_v1.json``):

* 46 ``boundary_storage_port`` bodies -- 23 on the left baseline at anchors
  ``(0, 1+3k)`` (1x3) and 23 on the bottom baseline at anchors ``(1+3k, 0)``
  (3x1), zero gap, ``k = 0..22``.  Together they occupy the whole ``x = 0``
  column for ``y in [1,69]`` and the whole ``y = 0`` row for ``x in [1,69]``;
  ``(0,0)`` stays free.  138 cells.
* 1 ``protocol_core`` at anchor ``(3,59)``, 9x9, orientation 1
  (framework ``inputs_east_west``).  81 cells.

219 fixed cells in total -- numerically equal to the 219 manufacturing bodies by
coincidence, not by construction.

Sufficient restrictions registered by this module (charter section 4).  Each is a
deliberate over-constraint: a layout obeying them is legal, and the restriction
is what makes the exact-cover master free of any seam variable.

``BODY_IN_REGION``   R-BODY-IN-REGION   every decision body lies wholly in one region
``FRONT_IN_REGION``  R-FRONT-IN-REGION  every *active* front lies in its body's region
``PORTAL_STUBS``     R-PORTAL-FIXED     two body-free stub cells per region edge
``RESERVED_FRONTS``  R-CORE-FRONT-RESERVE  all 66 fixed-furniture front cells stay free
``FIXED_FURNITURE``  R-BOUNDARY-LAYOUT  the pinned boundary + core layout above

R-FRONT-IN-REGION is what removes cross-region front coupling: whether a front
cell is free depends only on its own region's bodies.  R-PORTAL-FIXED is what
removes the seam-compatibility constraints: region ``(i,j)``'s east stubs at
``x = 14i+13`` sit 4-adjacent to region ``(i+1,j)``'s west stubs at
``x = 14i+14``, so per-pattern internal connectivity (R-PAT-CONN, enforced by the
evaluator) implies global free-space connectivity by construction.

Runtime contract: stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Tuple

from g1_port_semantics import GRID_HEIGHT, GRID_WIDTH

__all__ = [
    "REGION_SIZE",
    "REGION_CELLS",
    "REGIONS_PER_AXIS",
    "REGION_COORDS",
    "BODY_IN_REGION",
    "FRONT_IN_REGION",
    "PORTAL_STUBS",
    "RESERVED_FRONTS",
    "FIXED_FURNITURE",
    "FIXED_CELLS",
    "FIXED_FRONT_CELLS",
    "RegionClass",
    "REGION_CLASSES",
    "REGION_CLASS_ORDER",
    "REGION_CLASS_OF",
    "TOTAL_USABLE_CELLS",
    "region_origin",
    "region_class_name",
    "to_local",
    "to_global",
]

Cell = Tuple[int, int]

REGION_SIZE = 14
REGION_CELLS = REGION_SIZE * REGION_SIZE  # 196
REGIONS_PER_AXIS = 5
REGION_COORDS: Tuple[Tuple[int, int], ...] = tuple(
    (i, j) for i in range(REGIONS_PER_AXIS) for j in range(REGIONS_PER_AXIS)
)

# --- registered sufficient restrictions (code anchors for derived_theorems.json)
BODY_IN_REGION = "R-BODY-IN-REGION"
FRONT_IN_REGION = "R-FRONT-IN-REGION"

#: R-PORTAL-FIXED.  Two stub cells per region edge, in region-local coordinates.
#: Every edge reserves stubs, including edges on the board rim that have no
#: neighbour: paying ~30 wasted cells buys 16 geometrically identical CLEAN
#: regions, hence a 16-fold archetype collapse in the master.
PORTAL_STUBS: Tuple[Cell, ...] = (
    (REGION_SIZE - 1, 6),
    (REGION_SIZE - 1, 7),  # east
    (0, 6),
    (0, 7),  # west
    (6, REGION_SIZE - 1),
    (7, REGION_SIZE - 1),  # north
    (6, 0),
    (7, 0),  # south
)


@dataclass(frozen=True)
class FixedFurniture:
    """One pinned, non-decision facility body plus its port front cells."""

    kind: str
    anchor: Cell
    size: Tuple[int, int]
    orientation: int
    front_cells: Tuple[Cell, ...]

    @property
    def cells(self) -> Tuple[Cell, ...]:
        ax, ay = self.anchor
        w, h = self.size
        return tuple((ax + dx, ay + dy) for dx in range(w) for dy in range(h))


def _build_fixed_furniture() -> Tuple[FixedFurniture, ...]:
    items: List[FixedFurniture] = []
    # Left baseline: anchor (0, 1+3k), 1x3, inward port on the middle cell facing
    # east.  ``gen_boundary_ports`` stores the front cell itself (identity
    # semantics), i.e. (1, 2+3k) -- one cell outside the body.
    for k in range(23):
        items.append(
            FixedFurniture(
                kind="boundary_storage_port",
                anchor=(0, 1 + 3 * k),
                size=(1, 3),
                orientation=0,
                front_cells=((1, 2 + 3 * k),),
            )
        )
    # Bottom baseline: anchor (1+3k, 0), 3x1, inward port facing north.
    for k in range(23):
        items.append(
            FixedFurniture(
                kind="boundary_storage_port",
                anchor=(1 + 3 * k, 0),
                size=(3, 1),
                orientation=1,
                front_cells=((2 + 3 * k, 1),),
            )
        )
    # Protocol core, anchor (3,59), 9x9, orientation 1 = inputs east/west.
    # Inputs: local indices 1..7 on the left and right sides (14 cells).
    # Outputs: local indices 1,4,7 on the top and bottom sides (6 cells).
    core_x, core_y = 3, 59
    core_fronts: List[Cell] = []
    for index in range(1, 8):
        core_fronts.append((core_x - 1, core_y + index))
        core_fronts.append((core_x + 9, core_y + index))
    for index in (1, 4, 7):
        core_fronts.append((core_x + index, core_y + 9))
        core_fronts.append((core_x + index, core_y - 1))
    items.append(
        FixedFurniture(
            kind="protocol_core",
            anchor=(core_x, core_y),
            size=(9, 9),
            orientation=1,
            front_cells=tuple(sorted(core_fronts)),
        )
    )
    return tuple(items)


#: R-BOUNDARY-LAYOUT.
FIXED_FURNITURE: Tuple[FixedFurniture, ...] = _build_fixed_furniture()

FIXED_CELLS: FrozenSet[Cell] = frozenset(
    cell for item in FIXED_FURNITURE for cell in item.cells
)

#: R-CORE-FRONT-RESERVE.  The 46 boundary + 20 core front cells that must stay
#: body-free for the fixed furniture to remain connectable at all.  Stronger than
#: the true requirement (the core only needs two generic inputs served), and
#: deliberately so: it is a constant mask, hence free for the master.
FIXED_FRONT_CELLS: FrozenSet[Cell] = frozenset(
    cell for item in FIXED_FURNITURE for cell in item.front_cells
)
RESERVED_FRONTS = "R-CORE-FRONT-RESERVE"


def region_origin(i: int, j: int) -> Cell:
    return (REGION_SIZE * i, REGION_SIZE * j)


def to_local(cell: Cell, i: int, j: int) -> Cell:
    ox, oy = region_origin(i, j)
    return (cell[0] - ox, cell[1] - oy)


def to_global(cell: Cell, i: int, j: int) -> Cell:
    ox, oy = region_origin(i, j)
    return (cell[0] + ox, cell[1] + oy)


def _in_region(cell: Cell, i: int, j: int) -> bool:
    ox, oy = region_origin(i, j)
    return ox <= cell[0] < ox + REGION_SIZE and oy <= cell[1] < oy + REGION_SIZE


def region_class_name(i: int, j: int) -> str:
    """Region class of ``T[i,j]``.

    Left and bottom baselines are *not* mirror-equal: the boundary port period is
    3 while the region period is 14, so the front-cell phase inside the region
    differs per index.  Hence LEFT_J1/J2/J3 and BOTTOM_I1..I4 stay separate.
    """
    if (i, j) == (0, 0):
        return "CORNER"
    if (i, j) == (0, REGIONS_PER_AXIS - 1):
        return "CORE"
    if i == 0:
        return f"LEFT_J{j}"
    if j == 0:
        return f"BOTTOM_I{i}"
    return "CLEAN"


@dataclass(frozen=True)
class RegionClass:
    """A translation-equivalence class of regions, keyed by its two masks."""

    name: str
    regions: Tuple[Tuple[int, int], ...]
    fixed_local: FrozenSet[Cell]
    reserved_local: FrozenSet[Cell]

    @property
    def multiplicity(self) -> int:
        return len(self.regions)

    @property
    def live_stubs(self) -> Tuple[Cell, ...]:
        return tuple(stub for stub in PORTAL_STUBS if stub not in self.fixed_local)

    @property
    def fixed_front_local(self) -> FrozenSet[Cell]:
        return frozenset(self.reserved_local) - frozenset(self.live_stubs)

    @property
    def blocked_local(self) -> FrozenSet[Cell]:
        """Cells no decision body may occupy: fixed bodies plus reserved cells."""
        return self.fixed_local | self.reserved_local

    @property
    def usable(self) -> int:
        return REGION_CELLS - len(self.fixed_local) - len(self.reserved_local)

    def free_before_bodies(self) -> FrozenSet[Cell]:
        """Local cells not occupied by fixed furniture (reserved cells included)."""
        return frozenset(
            (u, v)
            for u in range(REGION_SIZE)
            for v in range(REGION_SIZE)
            if (u, v) not in self.fixed_local
        )


def _build_region_classes() -> Dict[str, RegionClass]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for i, j in REGION_COORDS:
        name = region_class_name(i, j)
        fixed_local = frozenset(
            to_local(cell, i, j) for cell in FIXED_CELLS if _in_region(cell, i, j)
        )
        fronts_local = frozenset(
            to_local(cell, i, j)
            for cell in FIXED_FRONT_CELLS
            if _in_region(cell, i, j)
        )
        stubs = frozenset(stub for stub in PORTAL_STUBS if stub not in fixed_local)
        reserved_local = fronts_local | stubs
        entry = grouped.get(name)
        if entry is None:
            grouped[name] = {
                "regions": [(i, j)],
                "fixed_local": fixed_local,
                "reserved_local": reserved_local,
            }
            continue
        if entry["fixed_local"] != fixed_local or entry["reserved_local"] != reserved_local:
            raise AssertionError(
                f"region class {name} is not mask-homogeneous at T[{i},{j}]"
            )
        regions = entry["regions"]
        assert isinstance(regions, list)
        regions.append((i, j))

    classes: Dict[str, RegionClass] = {}
    for name, entry in grouped.items():
        regions = entry["regions"]
        assert isinstance(regions, list)
        fixed_local = entry["fixed_local"]
        reserved_local = entry["reserved_local"]
        assert isinstance(fixed_local, frozenset)
        assert isinstance(reserved_local, frozenset)
        classes[name] = RegionClass(
            name=name,
            regions=tuple(sorted(regions)),
            fixed_local=fixed_local,
            reserved_local=reserved_local,
        )
    return classes


REGION_CLASSES: Dict[str, RegionClass] = _build_region_classes()
REGION_CLASS_ORDER: Tuple[str, ...] = tuple(sorted(REGION_CLASSES))
REGION_CLASS_OF: Dict[Tuple[int, int], str] = {
    (i, j): region_class_name(i, j) for i, j in REGION_COORDS
}
TOTAL_USABLE_CELLS: int = sum(
    region_class.usable * region_class.multiplicity
    for region_class in REGION_CLASSES.values()
)


def stub_seam_pairs() -> Tuple[Tuple[Cell, Cell], ...]:
    """Every ``(cell_a, cell_b)`` stub pair that straddles an internal seam.

    Used by the region-model tests to pin R-PORTAL-FIXED's whole point: the stubs
    of neighbouring regions are 4-adjacent, so per-pattern connectivity composes
    into global connectivity with zero master constraints.
    """
    pairs: List[Tuple[Cell, Cell]] = []
    for i, j in REGION_COORDS:
        if i + 1 < REGIONS_PER_AXIS:
            for local_a, local_b in (((REGION_SIZE - 1, 6), (0, 6)), ((REGION_SIZE - 1, 7), (0, 7))):
                pairs.append((to_global(local_a, i, j), to_global(local_b, i + 1, j)))
        if j + 1 < REGIONS_PER_AXIS:
            for local_a, local_b in (((6, REGION_SIZE - 1), (6, 0)), ((7, REGION_SIZE - 1), (7, 0))):
                pairs.append((to_global(local_a, i, j), to_global(local_b, i, j + 1)))
    return tuple(pairs)


def summary() -> Dict[str, object]:
    return {
        "grid": [GRID_WIDTH, GRID_HEIGHT],
        "region_size": REGION_SIZE,
        "regions": len(REGION_COORDS),
        "fixed_cells": len(FIXED_CELLS),
        "fixed_front_cells": len(FIXED_FRONT_CELLS),
        "total_usable_cells": TOTAL_USABLE_CELLS,
        "classes": [
            {
                "name": name,
                "multiplicity": REGION_CLASSES[name].multiplicity,
                "regions": [list(region) for region in REGION_CLASSES[name].regions],
                "fixed": len(REGION_CLASSES[name].fixed_local),
                "reserved": len(REGION_CLASSES[name].reserved_local),
                "usable": REGION_CLASSES[name].usable,
            }
            for name in REGION_CLASS_ORDER
        ],
    }


if __name__ == "__main__":  # pragma: no cover - operator convenience
    import json as _json

    print(_json.dumps(summary(), indent=2))

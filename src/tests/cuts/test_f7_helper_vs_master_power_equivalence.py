"""F7 helper-vs-master power-coverage equivalence regressions (M4-A).

PROJECT_LOCK lists "helper-vs-master equivalence regressions in place" as one
of the three prerequisites for ever moving EXACT_CUT_FRAMEWORK_ATTACH out of
the certified unsafe map. These tests pin the two sides to each other:

- Layer 1 (pure geometry, exhaustive): for EVERY 2×2 pole anchor on the 70×70
  grid, the helper's stencil semantics (_stencil_covers_cell), the canonical
  pose generator (gen_power_pole's power_coverage_cells), and the master's
  rectangular re-derivation formula must produce the identical coverage set.
  A sampled subset additionally exercises the helper predicate cell-by-cell
  so the formula-level pin cannot drift away from the actual implementation.

- Layer 2 (real master build): on a small synthetic pool with
  skip_power_coverage=False, the master's own coverer table
  (_power_coverers_by_template_pose = stencil-intersection ∧ footprint-
  disjoint) must agree pole-by-pole with the helper's compute_cover_set under
  the equivalent free-mask. This is the literal helper-vs-master table
  cross-check — if the helper ever says "CoverSet empty" while the master
  still sees a coverer, an attached F7 cut would over-prune a legal layout.

The attach-time runtime gate inside add_power_pose_exclusion_cut re-checks
the same table per cut (tested in test_step_8_apply_to_master); these
regressions guard the semantics the gate relies on.
"""
from __future__ import annotations

import random

from src.cuts.helpers.power_cover import (
    _POLE_SIZE,
    _stencil_covers_cell,
    compute_cover_set,
)
from src.models.master_model import MasterPlacementModel
from src.placement.placement_generator import gen_power_pole

_GRID = 70
_RADIUS = 5


def _formula_coverage(px: int, py: int) -> frozenset:
    """Master-side rectangular re-derivation: [x-R, x+1+R] × [y-R, y+1+R],
    clamped to the grid (exact_coordinate_master._supports_rectangular_
    power_coverage recomputes exactly this box; gen_power_pole emits it)."""
    return frozenset(
        (cx, cy)
        for cx in range(max(0, px - _RADIUS), min(_GRID, px + 2 + _RADIUS))
        for cy in range(max(0, py - _RADIUS), min(_GRID, py + 2 + _RADIUS))
    )


def test_layer1_all_anchors_helper_equals_canonical_equals_master_formula() -> None:
    poles = gen_power_pole()
    assert len(poles) == (_GRID - 1) * (_GRID - 1)  # 69×69 anchors
    for pose in poles:
        px = int(pose["anchor"]["x"])
        py = int(pose["anchor"]["y"])
        canonical = frozenset((int(c[0]), int(c[1])) for c in pose["power_coverage_cells"])
        assert canonical == _formula_coverage(px, py), (px, py)


def test_layer1_sampled_anchors_match_helper_predicate_cell_by_cell() -> None:
    """Formula-level layer 1 could in principle drift from the helper's real
    predicate; sample anchors (corners, edges, centre, random) and scan every
    grid cell through _stencil_covers_cell itself."""
    rng = random.Random(20260708)
    anchors = {(0, 0), (0, 68), (68, 0), (68, 68), (34, 34), (30, 30)}
    anchors.update((rng.randrange(69), rng.randrange(69)) for _ in range(10))
    for px, py in anchors:
        helper_cells = frozenset(
            (cx, cy)
            for cx in range(_GRID)
            for cy in range(_GRID)
            if _stencil_covers_cell((px, py), (cx, cy), _RADIUS, _POLE_SIZE)
        )
        assert helper_cells == _formula_coverage(px, py), (px, py)


# ---------------------------------------------------------------------------
# Layer 2: real master coverer table vs helper CoverSet
# ---------------------------------------------------------------------------

_L2_GRID = 20


def _l2_pole_pool() -> list:
    poles = []
    for x in range(_L2_GRID - 1):
        for y in range(_L2_GRID - 1):
            poles.append(
                {
                    "pose_id": f"pole_{x:02d}_{y:02d}",
                    "anchor": {"x": x, "y": y},
                    "occupied_cells": [[x, y], [x + 1, y], [x, y + 1], [x + 1, y + 1]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [
                        [cx, cy]
                        for cx in range(max(0, x - _RADIUS), min(_L2_GRID, x + 2 + _RADIUS))
                        for cy in range(max(0, y - _RADIUS), min(_L2_GRID, y + 2 + _RADIUS))
                    ],
                }
            )
    return poles


def _l2_master() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": "pose_corner",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_centre",
                "anchor": {"x": 10, "y": 10},
                "occupied_cells": [[10, 10]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": _l2_pole_pool(),
    }
    rules = {
        "globals": {"grid": {"width": _L2_GRID, "height": _L2_GRID}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 2, "h": 2},
                "needs_power": False,
                "power_coverage_radius": _RADIUS,
            },
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=False
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_layer2_master_coverer_table_equals_helper_cover_set() -> None:
    master = _l2_master()
    table = master._power_coverers_by_template_pose.get("miner")
    assert isinstance(table, dict) and table, "fixture must build the coverer table"

    pole_pool = master.facility_pools["power_pole"]
    miner_pool = master.facility_pools["miner"]
    grid_cells = {(x, y) for x in range(_L2_GRID) for y in range(_L2_GRID)}

    for pose_idx, miner_pose in enumerate(miner_pool):
        facility_cells = tuple(
            (int(c[0]), int(c[1])) for c in miner_pose["occupied_cells"]
        )
        # Helper semantics: anchors whose footprint fits in free cells (grid
        # minus the facility body — the free-mask mechanism) and whose stencil
        # intersects the facility.
        helper_anchors = compute_cover_set(
            facility_cells,
            frozenset(grid_cells - set(facility_cells)),
            float(_RADIUS),
            grid_size=_L2_GRID,
        )
        master_coverers = table.get(pose_idx)
        assert master_coverers is not None, pose_idx
        master_anchors = {
            (
                int(pole_pool[int(i)]["anchor"]["x"]),
                int(pole_pool[int(i)]["anchor"]["y"]),
            )
            for i in master_coverers
        }
        assert set(helper_anchors) == master_anchors, (
            f"pose_idx={pose_idx}: helper CoverSet and master coverer table "
            f"diverge — helper-only={set(helper_anchors) - master_anchors} "
            f"master-only={master_anchors - set(helper_anchors)}"
        )

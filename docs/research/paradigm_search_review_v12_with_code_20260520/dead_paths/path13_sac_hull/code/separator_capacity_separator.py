"""SAC-Hull Phase 2: dynamic separator separation.

Given master OPTIMAL layout, scan separator library, find violations
(required_crossings > 2 * free_wall_cells), return top-K to feed back as
master cuts.

Cuts added are unconditional capacity hulls (same form as Phase 1 static
build) but for axis V/H separators that the **current layout** violates.
This catches layout-specific corridor bottlenecks that ghost moat hull misses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Set, Tuple

from src.models.separator_capacity_hull import (
    Separator, build_static_separator_library, classify_pose_commodity_side,
)


@dataclass
class SeparatorViolation:
    separator: Separator
    crossing_commodities: List[str]
    required_crossings: int
    free_wall_cells: int
    capacity_upper_bound: int
    slack: int


def analyze_layout_for_separator_violations(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Any],
    instances_by_id: Mapping[str, Any],
    grid_w: int,
    grid_h: int,
    ghost_anchor: Tuple[int, int] | None = None,
    ghost_size: Tuple[int, int] | None = None,
    include_axis: bool = True,
    include_ghost_moat: bool = False,  # Phase 1 已加 ghost moat static, Phase 2 不重复
    separator_limit: int = 140,
) -> List[SeparatorViolation]:
    """Scan separator library, return violations sorted by slack ascending (most negative first)."""
    seps = build_static_separator_library(
        grid_w=grid_w, grid_h=grid_h,
        ghost_anchor=ghost_anchor, ghost_size=ghost_size,
        include_axis=include_axis, include_ghost_moat=include_ghost_moat,
        limit=separator_limit,
    )

    occupied: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        for cell in pool[pose_idx].get("occupied_cells", []) or []:
            occupied.add((int(cell[0]), int(cell[1])))

    violations: List[SeparatorViolation] = []
    for sep in seps:
        free_wall = len(sep.wall_cells - occupied)
        capacity = 2 * free_wall
        commodity_force: Dict[str, Dict[str, bool]] = {}
        for iid, sol in placement_solution.items():
            inst = instances_by_id.get(str(iid))
            if not inst:
                continue
            operation_type = str(inst.get("operation_type", ""))
            tpl = str(sol.get("facility_type", ""))
            pool = facility_pools.get(tpl, [])
            pose_idx = int(sol.get("pose_idx", -1))
            if pose_idx < 0 or pose_idx >= len(pool):
                continue
            classification = classify_pose_commodity_side(
                operation_type, pool[pose_idx], sep, grid_w, grid_h,
            )
            for c, sides in classification.items():
                cf = commodity_force.setdefault(c, {
                    "source_L": False, "source_R": False,
                    "sink_L": False, "sink_R": False,
                })
                if sides.source_side == "L":
                    cf["source_L"] = True
                elif sides.source_side == "R":
                    cf["source_R"] = True
                if sides.sink_side == "L":
                    cf["sink_L"] = True
                elif sides.sink_side == "R":
                    cf["sink_R"] = True

        crossing_commodities: List[str] = []
        for c, cf in commodity_force.items():
            if (cf["source_L"] and cf["sink_R"]) or (cf["source_R"] and cf["sink_L"]):
                crossing_commodities.append(c)
        required = len(crossing_commodities)
        if required > capacity:
            violations.append(SeparatorViolation(
                separator=sep,
                crossing_commodities=sorted(crossing_commodities),
                required_crossings=required,
                free_wall_cells=free_wall,
                capacity_upper_bound=capacity,
                slack=capacity - required,
            ))

    violations.sort(key=lambda v: v.slack)
    return violations

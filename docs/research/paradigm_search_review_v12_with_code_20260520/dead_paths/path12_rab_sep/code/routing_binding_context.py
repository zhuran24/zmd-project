"""RAB-SEP Phase 1: Routing-aware binding context.

Given a master layout, expose per-port front-cell status (in-grid / free /
component id / blocker) so that PortBindingModel can filter raw binding domains
to routing-feasible patterns.

GPT plan reference:
  - C2 必要条件 (port front-free + component-consistent) 前移到 binding domain
  - layout-local, 不污染 raw binding cache

Public API:
  - PortFrontStatus dataclass
  - RoutingBindingContext dataclass
  - build_routing_binding_context(placement_solution, facility_pools, grid_w,
    grid_h) -> RoutingBindingContext
  - port_front_status(port_spec, context) -> PortFrontStatus
  - is_port_front_usable(port_spec, context, owner_instance_id) -> bool
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Set, Tuple


_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0),
}


@dataclass(frozen=True)
class PortFrontStatus:
    port_key: str
    front_cell: Tuple[int, int]
    in_grid: bool
    is_free: bool
    component_id: Optional[int]
    blocker_instance_id: Optional[str]


@dataclass(frozen=True)
class RoutingBindingContext:
    grid_width: int
    grid_height: int
    occupied_cells: frozenset
    component_by_cell: Mapping[Tuple[int, int], int]
    cells_by_component: Mapping[int, Set[Tuple[int, int]]]
    occupied_owner_by_cell: Mapping[Tuple[int, int], str]


def build_routing_binding_context(
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Any],
    grid_w: int,
    grid_h: int,
) -> RoutingBindingContext:
    from src.models.routing_subproblem import RoutingPlacementCore

    occupied: Set[Tuple[int, int]] = set()
    owner_by_cell: Dict[Tuple[int, int], str] = {}
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for cell in pose.get("occupied_cells", []) or []:
            xy = (int(cell[0]), int(cell[1]))
            occupied.add(xy)
            owner_by_cell[xy] = str(iid)

    core = RoutingPlacementCore.from_occupied_cells(
        occupied, occupied_owner_by_cell=owner_by_cell,
    )
    return RoutingBindingContext(
        grid_width=int(grid_w),
        grid_height=int(grid_h),
        occupied_cells=frozenset(occupied),
        component_by_cell=dict(core.component_by_cell),
        cells_by_component={k: set(v) for k, v in core.cells_by_component.items()},
        occupied_owner_by_cell=dict(owner_by_cell),
    )


def port_front_status(
    port: Mapping[str, Any],
    context: RoutingBindingContext,
    owner_instance_id: Optional[str] = None,
) -> PortFrontStatus:
    """Compute front-cell status of a single port. owner_instance_id allows
    the port's own occupied cells to not be treated as blockers (a port's
    own facility wouldn't block itself)."""
    px, py = int(port.get("x", 0)), int(port.get("y", 0))
    direction = str(port.get("dir", ""))
    dx, dy = _DIR_DELTA.get(direction, (0, 0))
    fx, fy = px + dx, py + dy
    front_cell = (fx, fy)
    in_grid = (0 <= fx < context.grid_width) and (0 <= fy < context.grid_height)
    if not in_grid:
        return PortFrontStatus(
            port_key=f"{px},{py},{direction}",
            front_cell=front_cell,
            in_grid=False,
            is_free=False,
            component_id=None,
            blocker_instance_id=None,
        )
    if front_cell in context.occupied_cells:
        blocker = context.occupied_owner_by_cell.get(front_cell)
        # port 的 owner 自己占的 cell 不算 blocker (port pose 自带 occupied cells)
        if owner_instance_id is not None and blocker == owner_instance_id:
            # self-occupied — 实际不可能 (port front 是 outside facility), 但 defensive
            return PortFrontStatus(
                port_key=f"{px},{py},{direction}",
                front_cell=front_cell,
                in_grid=True,
                is_free=True,
                component_id=context.component_by_cell.get(front_cell),
                blocker_instance_id=None,
            )
        return PortFrontStatus(
            port_key=f"{px},{py},{direction}",
            front_cell=front_cell,
            in_grid=True,
            is_free=False,
            component_id=None,
            blocker_instance_id=blocker,
        )
    return PortFrontStatus(
        port_key=f"{px},{py},{direction}",
        front_cell=front_cell,
        in_grid=True,
        is_free=True,
        component_id=context.component_by_cell.get(front_cell),
        blocker_instance_id=None,
    )


def is_port_front_usable(
    port: Mapping[str, Any],
    context: RoutingBindingContext,
    owner_instance_id: Optional[str] = None,
) -> bool:
    s = port_front_status(port, context, owner_instance_id)
    return s.in_grid and s.is_free

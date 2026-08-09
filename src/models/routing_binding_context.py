"""RAB-SEP Phase 1: Routing-aware binding context.

Given a master layout, expose per-port front-cell status (in-grid / free /
component id / blocker) so that PortBindingModel can filter raw binding domains
to routing-feasible patterns.

Front geometry (front-offset incident fix, 2026-07-18; authority
docs/research/front_offset_incident_20260718/00 + owner in-game adjudication):
the stored port coordinate in candidate_placements.json IS the belt/front
cell — the first cell outside the facility body along the port's outward
normal (599,384 records, zero exceptions). The physical port sits on the
adjacent body-edge cell. A front cell is usable iff it is in-grid and not
occupied by ANY facility body (power poles count as body; belts do NOT
block — belt/belt co-location is adjudicated by the routing layer's
cross-junction constraints, never here).

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


# Outward normal of a port direction. MUST NOT be used to derive the front
# cell from a stored port coordinate (the stored coordinate already IS the
# front cell — identity semantics). Kept for direction validation and for
# body-side reconstruction (front - delta ∈ body).
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
    from src.models.binding_subproblem import _is_non_facility_placement_marker
    from src.models.routing_subproblem import RoutingPlacementCore

    occupied: Set[Tuple[int, int]] = set()
    owner_by_cell: Dict[Tuple[int, int], str] = {}
    for iid, sol in placement_solution.items():
        # ghost_pick 等非设施 marker 显式排除（镜像 benders_loop
        # _extract_occupied_cells 的 V88 语义）：empty-domain 判定必须
        # ghost-agnostic——由此发出的 placement nogood 是 unconditioned
        # 全 anchor 应用的，ghost cell 一旦混入 occupied 会把判定变成
        # ghost-dependent 而 cut 仍全局生效 = 跨 ghost 超杀。此前无害仅因
        # facility_pools 无 ghost_rect key（空池 continue 的巧合安全），
        # 2026-07-16 对抗审查（V4 双席）后升级为结构保证。
        if _is_non_facility_placement_marker(iid):
            continue
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
    """Compute front-cell status of a single port.

    Identity semantics (front-offset incident fix 2026-07-18): the stored
    port coordinate IS the front/belt cell — no direction offset is applied.
    ``owner_instance_id`` grants NO exemption: frozen-pool geometry
    guarantees a pose never occupies its own front cell (599,384 records,
    zero exceptions); if data ever violates that, the front is blocked —
    fail closed, attributed to the occupying owner."""
    px, py = int(port.get("x", 0)), int(port.get("y", 0))
    direction = str(port.get("dir", ""))
    del owner_instance_id  # no self-exemption under identity semantics
    front_cell = (px, py)
    in_grid = (0 <= px < context.grid_width) and (0 <= py < context.grid_height)
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

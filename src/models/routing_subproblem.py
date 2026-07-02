"""
Exact grid-routing subproblem.

This version keeps the exact state semantics, but shrinks the routing core to the
commodity-scoped terminal-connected domain before building CP-SAT variables.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model

from src.models.cp_sat_worker_config import (
    DEFAULT_ROUTING_CP_SAT_WORKERS,
    apply_subproblem_memory_cap,
    resolve_cp_sat_worker_count,
)

GRID_W = 70
GRID_H = 70
DIRECTIONS = ["N", "S", "E", "W"]
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
DIR_OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
LAYERS = [0, 1]
GROUND_LAYER = 0
ELEVATED_LAYER = 1
ROUTING_DOMAIN_STATUS_FEASIBLE = "feasible"
ROUTING_DOMAIN_PROOF_REJECT_STATUSES = {"front_blocked", "relaxed_disconnected"}
ROUTING_DOMAIN_VERIFIED_STATUSES = (
    {ROUTING_DOMAIN_STATUS_FEASIBLE} | ROUTING_DOMAIN_PROOF_REJECT_STATUSES
)
ROUTING_DOMAIN_MISSING_STATUS = "MISSING_STATUS"


RouteStateKey = Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...], str]
PhysicalStateKey = Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...], str]


@dataclass
class RoutingPlacementCore:
    occupied_cells: Set[Tuple[int, int]]
    occupied_owner_by_cell: Dict[Tuple[int, int], str]
    free_cells: Set[Tuple[int, int]]
    free_neighbors_by_cell: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]]
    component_by_cell: Dict[Tuple[int, int], int]
    cells_by_component: Dict[int, Set[Tuple[int, int]]]

    @classmethod
    def from_occupied_cells(
        cls,
        occupied_cells: Set[Tuple[int, int]],
        *,
        occupied_owner_by_cell: Optional[Mapping[Tuple[int, int], str]] = None,
    ) -> "RoutingPlacementCore":
        occupied = {(int(x), int(y)) for x, y in occupied_cells}
        owner_map = {
            (int(cell[0]), int(cell[1])): str(owner)
            for cell, owner in dict(occupied_owner_by_cell or {}).items()
        }
        free_cells: Set[Tuple[int, int]] = set()
        for x in range(GRID_W):
            for y in range(GRID_H):
                if (x, y) not in occupied:
                    free_cells.add((x, y))

        free_neighbors_by_cell = {
            cell: tuple(
                sorted(
                    neighbor
                    for neighbor in _cell_neighbors(cell)
                    if neighbor in free_cells
                )
            )
            for cell in free_cells
        }
        component_by_cell, cells_by_component = _compute_free_components(
            free_cells,
            free_neighbors_by_cell=free_neighbors_by_cell,
        )
        return cls(
            occupied_cells=occupied,
            occupied_owner_by_cell=owner_map,
            free_cells=free_cells,
            free_neighbors_by_cell=free_neighbors_by_cell,
            component_by_cell=component_by_cell,
            cells_by_component=cells_by_component,
        )


def _dirs_tag(dirs: Iterable[str]) -> str:
    ordered = list(dirs)
    return "".join(ordered) if ordered else "none"


def _is_straight_state(flow_in: Tuple[str, ...], flow_out: Tuple[str, ...]) -> bool:
    return (
        len(flow_in) == 1
        and len(flow_out) == 1
        and DIR_OPP[flow_in[0]] == flow_out[0]
    )


def _state_axis(flow_in: Tuple[str, ...], flow_out: Tuple[str, ...]) -> Optional[str]:
    if set(flow_in) | set(flow_out) == {"E", "W"}:
        return "H"
    if set(flow_in) | set(flow_out) == {"N", "S"}:
        return "V"
    return None


def _sorted_cells(cells: Iterable[Tuple[int, int]]) -> List[List[int]]:
    return [[int(x), int(y)] for x, y in sorted(cells)]


def _cell_neighbors(cell: Tuple[int, int]) -> List[Tuple[int, int]]:
    x, y = cell
    neighbors: List[Tuple[int, int]] = []
    for dx, dy in DIR_DELTA.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
            neighbors.append((nx, ny))
    return neighbors


def _in_grid_cell(cell: Tuple[int, int]) -> bool:
    x, y = cell
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def _port_connector_cells(port_specs: Sequence[Mapping[str, Any]]) -> Set[Tuple[int, int]]:
    """Return in-grid physical port connector cells.

    Binding/candidate placements encode a port as the outside-adjacent connector
    cell plus an outward normal; routing variables live on the front cell
    ``port + dir``.  Connector cells are terminal nodes, not free belt cells.
    """

    cells: Set[Tuple[int, int]] = set()
    for spec in port_specs:
        cell = (int(spec["x"]), int(spec["y"]))
        if _in_grid_cell(cell):
            cells.add(cell)
    return cells


def _duplicate_terminal_front_keys(
    port_specs: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Detect repeated physical-port terminal keys.

    Port adherence is exact-one per physical port.  Canonical placement geometry
    must not generate two ports with the same front cell, terminal direction,
    commodity, and type; if an external/future port_specs entry does, reusing the
    same exact-one row would collapse multiplicity.  Fail closed instead.
    """

    by_key: Dict[Tuple[int, int, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for spec in port_specs:
        px = int(spec["x"])
        py = int(spec["y"])
        direction = str(spec["dir"])
        commodity = str(spec.get("commodity", ""))
        port_type = str(spec.get("type", ""))
        dx, dy = DIR_DELTA[direction]
        fx, fy = px + dx, py + dy
        terminal_dir = DIR_OPP[direction]
        by_key[(fx, fy, terminal_dir, commodity, port_type)].append(
            {
                "instance_id": str(spec.get("instance_id", "")),
                "port_cell": [px, py],
                "front_cell": [fx, fy],
                "dir": direction,
                "terminal_dir": terminal_dir,
                "commodity": commodity,
                "type": port_type,
            }
        )

    duplicates: List[Dict[str, Any]] = []
    for (fx, fy, terminal_dir, commodity, port_type), specs_for_key in sorted(by_key.items()):
        if len(specs_for_key) <= 1:
            continue
        instance_ids = [str(item["instance_id"]) for item in specs_for_key if item.get("instance_id")]
        duplicates.append(
            {
                "reason": "duplicate_terminal_front_key",
                "commodity": commodity,
                "type": port_type,
                "front_cell": [fx, fy],
                "terminal_dir": terminal_dir,
                "multiplicity": len(specs_for_key),
                "instance_ids": instance_ids,
                "ports": specs_for_key,
            }
        )
    return duplicates


def _filter_free_neighbors(
    free_cells: Set[Tuple[int, int]],
    free_neighbors_by_cell: Optional[Mapping[Tuple[int, int], Sequence[Tuple[int, int]]]],
) -> Optional[Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]]]:
    if free_neighbors_by_cell is None:
        return None
    return {
        cell: tuple(neighbor for neighbor in free_neighbors_by_cell.get(cell, ()) if neighbor in free_cells)
        for cell in free_cells
    }


def _annotate_port_connector_owners(
    owner_map: Dict[Tuple[int, int], str],
    port_specs: Sequence[Mapping[str, Any]],
) -> None:
    for spec in port_specs:
        cell = (int(spec["x"]), int(spec["y"]))
        if not _in_grid_cell(cell):
            continue
        instance_id = str(spec.get("instance_id", ""))
        if instance_id:
            owner_map.setdefault(cell, instance_id)


def _compute_free_components(
    free_cells: Set[Tuple[int, int]],
    *,
    free_neighbors_by_cell: Optional[Mapping[Tuple[int, int], Sequence[Tuple[int, int]]]] = None,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, Set[Tuple[int, int]]]]:
    component_by_cell: Dict[Tuple[int, int], int] = {}
    cells_by_component: Dict[int, Set[Tuple[int, int]]] = {}
    component_id = 0

    for cell in free_cells:
        if cell in component_by_cell:
            continue
        stack = [cell]
        component_by_cell[cell] = component_id
        component_cells: Set[Tuple[int, int]] = {cell}
        while stack:
            current = stack.pop()
            neighbors = (
                free_neighbors_by_cell.get(current, ())
                if free_neighbors_by_cell is not None
                else _cell_neighbors(current)
            )
            for neighbor in neighbors:
                if neighbor not in free_cells or neighbor in component_by_cell:
                    continue
                component_by_cell[neighbor] = component_id
                component_cells.add(neighbor)
                stack.append(neighbor)
        cells_by_component[component_id] = component_cells
        component_id += 1

    return component_by_cell, cells_by_component


def _peel_terminal_core(
    component_cells: Set[Tuple[int, int]],
    terminal_cells: Set[Tuple[int, int]],
    *,
    free_neighbors_by_cell: Optional[Mapping[Tuple[int, int], Sequence[Tuple[int, int]]]] = None,
) -> Set[Tuple[int, int]]:
    if not component_cells:
        return set()

    neighbor_map: Dict[Tuple[int, int], Set[Tuple[int, int]]] = {}
    degree: Dict[Tuple[int, int], int] = {}
    for cell in component_cells:
        base_neighbors = (
            free_neighbors_by_cell.get(cell, ())
            if free_neighbors_by_cell is not None
            else _cell_neighbors(cell)
        )
        neighbors = {neighbor for neighbor in base_neighbors if neighbor in component_cells}
        neighbor_map[cell] = neighbors
        degree[cell] = len(neighbors)

    removed: Set[Tuple[int, int]] = set()
    queue = deque(
        cell
        for cell in component_cells
        if cell not in terminal_cells and degree.get(cell, 0) < 2
    )
    while queue:
        cell = queue.popleft()
        if cell in removed or cell in terminal_cells:
            continue
        if degree.get(cell, 0) >= 2:
            continue
        removed.add(cell)
        for neighbor in neighbor_map.get(cell, set()):
            if neighbor in removed:
                continue
            degree[neighbor] = degree.get(neighbor, 0) - 1
            if neighbor not in terminal_cells and degree.get(neighbor, 0) < 2:
                queue.append(neighbor)

    return {cell for cell in component_cells if cell not in removed}


def _empty_domain_stats() -> Dict[str, Any]:
    return {
        "commodity_component_cells": {},
        "commodity_active_cells": {},
        "commodity_terminal_cells": {},
        "domain_cells": 0,
        "terminal_core_cells": 0,
        "front_terminal_cells": 0,
        "blocked_ports": 0,
        "disconnected_commodity_count": 0,
    }


def _resolve_routing_domain_context(
    *,
    grid: Optional["RoutingGrid"] = None,
    placement_core: Optional[RoutingPlacementCore] = None,
    port_specs: Optional[Sequence[Mapping[str, Any]]] = None,
    occupied_owner_by_cell: Optional[Mapping[Tuple[int, int], str]] = None,
) -> Tuple[
    Optional["RoutingGrid"],
    List[Dict[str, Any]],
    Set[Tuple[int, int]],
    Dict[Tuple[int, int], str],
    Dict[Tuple[int, int], int],
    Dict[int, Set[Tuple[int, int]]],
    Optional[Mapping[Tuple[int, int], Sequence[Tuple[int, int]]]],
]:
    resolved_grid = grid
    resolved_core = placement_core
    if resolved_grid is None and resolved_core is None:
        raise ValueError("analyze_exact_routing_domain requires either grid or placement_core")

    if resolved_grid is not None:
        if resolved_core is None:
            resolved_core = getattr(resolved_grid, "placement_core", None)
        resolved_port_specs = [dict(spec) for spec in resolved_grid.port_specs]
    else:
        resolved_port_specs = [dict(spec) for spec in list(port_specs or [])]

    port_connector_cells = _port_connector_cells(resolved_port_specs)

    if resolved_core is not None:
        owner_map = dict(resolved_core.occupied_owner_by_cell)
        if occupied_owner_by_cell is not None:
            owner_map.update(
                {
                    (int(cell[0]), int(cell[1])): str(owner)
                    for cell, owner in dict(occupied_owner_by_cell).items()
                }
            )
        _annotate_port_connector_owners(owner_map, resolved_port_specs)
        resolved_free_cells = set(resolved_core.free_cells) - port_connector_cells
        resolved_free_neighbors = _filter_free_neighbors(
            resolved_free_cells,
            resolved_core.free_neighbors_by_cell,
        )
        component_by_cell, cells_by_component = _compute_free_components(
            resolved_free_cells,
            free_neighbors_by_cell=resolved_free_neighbors,
        )
        return (
            resolved_grid,
            resolved_port_specs,
            resolved_free_cells,
            owner_map,
            component_by_cell,
            cells_by_component,
            resolved_free_neighbors,
        )

    resolved_free_cells = set(getattr(resolved_grid, "free_cells", set())) - port_connector_cells
    owner_map = {
        (int(cell[0]), int(cell[1])): str(owner)
        for cell, owner in dict(
            occupied_owner_by_cell
            if occupied_owner_by_cell is not None
            else getattr(resolved_grid, "occupied_owner_by_cell", {})
        ).items()
    }
    _annotate_port_connector_owners(owner_map, resolved_port_specs)
    component_by_cell, cells_by_component = _compute_free_components(resolved_free_cells)
    return (
        resolved_grid,
        resolved_port_specs,
        resolved_free_cells,
        owner_map,
        component_by_cell,
        cells_by_component,
        None,
    )


def analyze_exact_routing_domain(
    grid: Optional["RoutingGrid"] = None,
    *,
    placement_core: Optional[RoutingPlacementCore] = None,
    port_specs: Optional[Sequence[Mapping[str, Any]]] = None,
    occupied_owner_by_cell: Optional[Dict[Tuple[int, int], str]] = None,
) -> Dict[str, Any]:
    _resolved_grid, resolved_port_specs, resolved_free_cells, resolved_owner_map, component_by_cell, cells_by_component, free_neighbors_by_cell = _resolve_routing_domain_context(
        grid=grid,
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=occupied_owner_by_cell,
    )
    duplicate_terminal_keys = _duplicate_terminal_front_keys(resolved_port_specs)
    if duplicate_terminal_keys:
        placement_level_conflict_set: List[str] = []
        for duplicate in duplicate_terminal_keys:
            for instance_id in duplicate.get("instance_ids", []):
                if instance_id and instance_id not in placement_level_conflict_set:
                    placement_level_conflict_set.append(str(instance_id))
        domain_stats = _empty_domain_stats()
        domain_stats["blocked_ports"] = len(duplicate_terminal_keys)
        return {
            "status": "front_blocked",
            "binding_selection_safe_reject": True,
            "placement_level_conflict_set": placement_level_conflict_set,
            "blocked_ports": duplicate_terminal_keys,
            "disconnected_commodities": [],
            "commodity_front_metadata": {},
            "commodity_component_cells": {},
            "commodity_active_cells": {},
            "domain_stats": domain_stats,
        }

    blocked_ports: List[Dict[str, Any]] = []
    commodity_fronts: Dict[str, Set[Tuple[int, int]]] = defaultdict(set)
    commodity_source_fronts: Dict[str, Set[Tuple[int, int]]] = defaultdict(set)
    commodity_sink_fronts: Dict[str, Set[Tuple[int, int]]] = defaultdict(set)

    for spec in resolved_port_specs:
        px = int(spec["x"])
        py = int(spec["y"])
        direction = str(spec["dir"])
        commodity = str(spec.get("commodity", ""))
        dx, dy = DIR_DELTA[direction]
        fx, fy = px + dx, py + dy
        front_cell = (fx, fy)

        in_grid = 0 <= fx < GRID_W and 0 <= fy < GRID_H
        if not in_grid or front_cell not in resolved_free_cells:
            conflict_ids: List[str] = []
            instance_id = str(spec.get("instance_id", ""))
            if instance_id:
                conflict_ids.append(instance_id)

            blocking_instance_id = resolved_owner_map.get(front_cell)
            if blocking_instance_id and blocking_instance_id not in conflict_ids:
                conflict_ids.append(str(blocking_instance_id))

            blocked_ports.append(
                {
                    "instance_id": instance_id,
                    "commodity": commodity,
                    "dir": direction,
                    "port_cell": [px, py],  # B1 Phase 5: cell-pattern cut 需要 port cell
                    "front_cell": [fx, fy],
                    "blocking_instance_ids": (
                        []
                        if blocking_instance_id is None
                        else [str(blocking_instance_id)]
                    ),
                    "placement_level_conflict_set": conflict_ids,
                }
            )
            continue

        commodity_fronts[commodity].add(front_cell)
        if str(spec["type"]) == "out":
            commodity_source_fronts[commodity].add(front_cell)
        else:
            commodity_sink_fronts[commodity].add(front_cell)

    commodity_front_metadata = {
        commodity: {
            "front_cells": _sorted_cells(fronts),
            "source_front_cells": _sorted_cells(commodity_source_fronts.get(commodity, set())),
            "sink_front_cells": _sorted_cells(commodity_sink_fronts.get(commodity, set())),
        }
        for commodity, fronts in sorted(commodity_fronts.items())
    }

    if blocked_ports:
        placement_level_conflict_set: List[str] = []
        for blocked in blocked_ports:
            for instance_id in blocked["placement_level_conflict_set"]:
                if instance_id not in placement_level_conflict_set:
                    placement_level_conflict_set.append(instance_id)
        domain_stats = _empty_domain_stats()
        domain_stats["blocked_ports"] = len(blocked_ports)
        return {
            "status": "front_blocked",
            "binding_selection_safe_reject": True,
            "placement_level_conflict_set": placement_level_conflict_set,
            "blocked_ports": blocked_ports,
            "disconnected_commodities": [],
            "commodity_front_metadata": commodity_front_metadata,
            "commodity_component_cells": {},
            "commodity_active_cells": {},
            "domain_stats": domain_stats,
        }

    disconnected_commodities: List[Dict[str, Any]] = []
    commodity_component_cells: Dict[str, Set[Tuple[int, int]]] = {}
    commodity_active_cells: Dict[str, Set[Tuple[int, int]]] = {}

    for commodity, front_cells in sorted(commodity_fronts.items()):
        source_fronts = set(commodity_source_fronts.get(commodity, set()))
        sink_fronts = set(commodity_sink_fronts.get(commodity, set()))
        fronts_by_component: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)
        for cell in front_cells:
            fronts_by_component[component_by_cell.get(cell, -1)].add(cell)

        if not source_fronts or not sink_fronts:
            component_ids = set(fronts_by_component)
            if len(component_ids) > 1:
                disconnected_commodities.append(
                    {
                        "commodity": commodity,
                        "front_cells": _sorted_cells(front_cells),
                        "component_ids": sorted(component_ids),
                    }
                )
                commodity_component_cells[commodity] = set()
                commodity_active_cells[commodity] = set()
                continue

            component_id = next(iter(component_ids), -1)
            component_cells = set(cells_by_component.get(component_id, set()))
            commodity_component_cells[commodity] = component_cells
            commodity_active_cells[commodity] = _peel_terminal_core(
                component_cells,
                set(front_cells),
                free_neighbors_by_cell=free_neighbors_by_cell,
            )
            continue

        missing_counterpart_components: List[Dict[str, Any]] = []
        component_union: Set[Tuple[int, int]] = set()
        active_union: Set[Tuple[int, int]] = set()

        for component_id, component_fronts in sorted(fronts_by_component.items()):
            component_sources = component_fronts & source_fronts
            component_sinks = component_fronts & sink_fronts
            if not component_sources or not component_sinks:
                missing_counterpart_components.append(
                    {
                        "component_id": component_id,
                        "front_cells": _sorted_cells(component_fronts),
                        "source_front_cells": _sorted_cells(component_sources),
                        "sink_front_cells": _sorted_cells(component_sinks),
                    }
                )
                continue

            component_cells = set(cells_by_component.get(component_id, set()))
            component_union.update(component_cells)
            active_union.update(
                _peel_terminal_core(
                    component_cells,
                    component_fronts,
                    free_neighbors_by_cell=free_neighbors_by_cell,
                )
            )

        if missing_counterpart_components:
            disconnected_commodities.append(
                {
                    "commodity": commodity,
                    "front_cells": _sorted_cells(front_cells),
                    "component_ids": sorted(fronts_by_component),
                    "components": missing_counterpart_components,
                }
            )
            commodity_component_cells[commodity] = set()
            commodity_active_cells[commodity] = set()
            continue

        commodity_component_cells[commodity] = component_union
        commodity_active_cells[commodity] = active_union

    domain_stats = {
        "commodity_component_cells": {
            commodity: len(cells)
            for commodity, cells in sorted(commodity_component_cells.items())
        },
        "commodity_active_cells": {
            commodity: len(cells)
            for commodity, cells in sorted(commodity_active_cells.items())
        },
        "commodity_terminal_cells": {
            commodity: len(commodity_fronts.get(commodity, set()))
            for commodity in sorted(commodity_fronts)
        },
        "domain_cells": sum(len(cells) for cells in commodity_component_cells.values()),
        "terminal_core_cells": sum(len(cells) for cells in commodity_active_cells.values()),
        "front_terminal_cells": sum(len(cells) for cells in commodity_fronts.values()),
        "blocked_ports": 0,
        "disconnected_commodity_count": len(disconnected_commodities),
    }

    if disconnected_commodities:
        return {
            "status": "relaxed_disconnected",
            "binding_selection_safe_reject": True,
            "placement_level_conflict_set": [],
            "blocked_ports": [],
            "disconnected_commodities": disconnected_commodities,
            "commodity_front_metadata": commodity_front_metadata,
            "commodity_component_cells": {
                commodity: _sorted_cells(cells)
                for commodity, cells in sorted(commodity_component_cells.items())
            },
            "commodity_active_cells": {
                commodity: _sorted_cells(cells)
                for commodity, cells in sorted(commodity_active_cells.items())
            },
            "domain_stats": domain_stats,
        }

    return {
        "status": "feasible",
        "binding_selection_safe_reject": False,
        "placement_level_conflict_set": [],
        "blocked_ports": [],
        "disconnected_commodities": [],
        "commodity_front_metadata": commodity_front_metadata,
        "commodity_component_cells": {
            commodity: _sorted_cells(cells)
            for commodity, cells in sorted(commodity_component_cells.items())
        },
        "commodity_active_cells": {
            commodity: _sorted_cells(cells)
            for commodity, cells in sorted(commodity_active_cells.items())
        },
        "domain_stats": domain_stats,
    }


def run_exact_routing_precheck(
    grid: Optional["RoutingGrid"] = None,
    *,
    placement_core: Optional[RoutingPlacementCore] = None,
    port_specs: Optional[Sequence[Mapping[str, Any]]] = None,
    occupied_owner_by_cell: Optional[Dict[Tuple[int, int], str]] = None,
) -> Dict[str, Any]:
    analysis = analyze_exact_routing_domain(
        grid,
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=occupied_owner_by_cell,
    )
    return {
        "status": str(analysis["status"]),
        "binding_selection_safe_reject": bool(analysis["binding_selection_safe_reject"]),
        "placement_level_conflict_set": list(analysis.get("placement_level_conflict_set", [])),
        "blocked_ports": list(analysis.get("blocked_ports", [])),
        "disconnected_commodities": list(analysis.get("disconnected_commodities", [])),
        "domain_stats": dict(analysis.get("domain_stats", {})),
        "_analysis": analysis,
    }


class RoutingGrid:
    """3D grid domain for the routing subproblem."""

    def __init__(
        self,
        occupied_cells: Set[Tuple[int, int]],
        port_specs: List[Dict[str, Any]],
        *,
        occupied_owner_by_cell: Optional[Mapping[Tuple[int, int], str]] = None,
    ):
        self.occupied = {(int(x), int(y)) for x, y in occupied_cells}
        self.port_specs = [dict(spec) for spec in port_specs]
        self.occupied_owner_by_cell = {
            (int(cell[0]), int(cell[1])): str(owner)
            for cell, owner in dict(occupied_owner_by_cell or {}).items()
        }
        self.placement_core: Optional[RoutingPlacementCore] = None

        self.free_cells: Set[Tuple[int, int]] = set()
        for x in range(GRID_W):
            for y in range(GRID_H):
                if (x, y) not in self.occupied:
                    self.free_cells.add((x, y))

        self.port_cells: Set[Tuple[int, int]] = set()
        for ps in port_specs:
            self.port_cells.add((int(ps["x"]), int(ps["y"])))

        self.routable_cells = self.free_cells | self.port_cells

    @classmethod
    def from_placement_core(
        cls,
        placement_core: RoutingPlacementCore,
        port_specs: Sequence[Mapping[str, Any]],
    ) -> "RoutingGrid":
        grid = cls.__new__(cls)
        grid.occupied = set(placement_core.occupied_cells)
        grid.port_specs = [dict(spec) for spec in port_specs]
        grid.occupied_owner_by_cell = dict(placement_core.occupied_owner_by_cell)
        grid.placement_core = placement_core
        grid.free_cells = set(placement_core.free_cells)
        grid.port_cells = {
            (int(ps["x"]), int(ps["y"]))
            for ps in grid.port_specs
        }
        grid.routable_cells = grid.free_cells | grid.port_cells
        return grid

    def neighbors(self, x: int, y: int) -> List[Tuple[int, int, str]]:
        result = []
        for d, (dx, dy) in DIR_DELTA.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H and (nx, ny) in self.routable_cells:
                result.append((nx, ny, d))
        return result


class RoutingSubproblem:
    """CP-SAT routing model with belt / splitter / merger / bridge states."""

    def __init__(
        self,
        grid: RoutingGrid,
        commodities: List[str],
        *,
        domain_analysis: Optional[Mapping[str, Any]] = None,
    ):
        self.grid = grid
        self._placement_core: Optional[RoutingPlacementCore] = getattr(
            grid,
            "placement_core",
            None,
        )
        self.commodities = commodities
        self.model = cp_model.CpModel()

        self.use_vars: Dict[RouteStateKey, Any] = {}
        # Compatibility alias: legacy callers/tests treat r_vars as selected
        # commodity route states, which are now the use layer.
        self.r_vars = self.use_vars
        self.phys_vars: Dict[PhysicalStateKey, Any] = {}
        self._use_to_phys_key: Dict[RouteStateKey, PhysicalStateKey] = {}
        self._phys_uses: Dict[PhysicalStateKey, List[Any]] = defaultdict(list)
        self._phys_by_cell_layer: Dict[Tuple[int, int, int], List[Any]] = defaultdict(list)
        self._phys_keys_by_cell: Dict[Tuple[int, int], List[PhysicalStateKey]] = defaultdict(list)
        self._use_by_cell_layer_dir_out_commodity: Dict[
            Tuple[int, int, int, str, str], List[Any]
        ] = defaultdict(list)
        self._use_by_cell_layer_dir_in_commodity: Dict[
            Tuple[int, int, int, str, str], List[Any]
        ] = defaultdict(list)
        self._use_by_cell_dir_out_commodity: Dict[Tuple[int, int, str, str], List[Any]] = defaultdict(list)
        self._use_by_cell_dir_in_commodity: Dict[Tuple[int, int, str, str], List[Any]] = defaultdict(list)
        self._l1_phys_vars: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
        self._phys_meta: Dict[PhysicalStateKey, Dict[str, Any]] = {}
        self._state_meta: Dict[RouteStateKey, Dict[str, Any]] = {}
        self._solver: Optional[cp_model.CpSolver] = None
        self._status = None
        self._connectivity_guard_accepted = False
        self._domain_status_contract_violation: Optional[str] = None
        self.build_stats: Dict[str, Any] = {}

        self._domain_analysis: Optional[Mapping[str, Any]] = dict(domain_analysis) if domain_analysis else None
        self._domain_stats: Dict[str, Any] = {}
        self._commodity_active_cells: Dict[str, Set[Tuple[int, int]]] = {
            commodity: set() for commodity in self.commodities
        }
        self._commodity_component_cells: Dict[str, Set[Tuple[int, int]]] = {
            commodity: set() for commodity in self.commodities
        }

        self._duplicate_terminal_front_keys = _duplicate_terminal_front_keys(self.grid.port_specs)
        self._source_port_fronts: Dict[Tuple[int, int, str, str], int] = defaultdict(int)
        self._sink_port_fronts: Dict[Tuple[int, int, str, str], int] = defaultdict(int)
        self._index_port_fronts()
        self._patterns_by_layer = {
            layer: list(self._iter_state_patterns(layer))
            for layer in LAYERS
        }
        self._pattern_count_per_cell = sum(len(patterns) for patterns in self._patterns_by_layer.values())

    @classmethod
    def from_placement_core(
        cls,
        placement_core: RoutingPlacementCore,
        port_specs: Sequence[Mapping[str, Any]],
        commodities: List[str],
        *,
        domain_analysis: Optional[Mapping[str, Any]] = None,
    ) -> "RoutingSubproblem":
        return cls(
            RoutingGrid.from_placement_core(placement_core, port_specs),
            commodities,
            domain_analysis=domain_analysis,
        )

    def _index_port_fronts(self) -> None:
        for ps in self.grid.port_specs:
            px = int(ps["x"])
            py = int(ps["y"])
            direction = str(ps["dir"])
            commodity = str(ps["commodity"])
            dx, dy = DIR_DELTA[direction]
            fx, fy = px + dx, py + dy
            if str(ps["type"]) == "out":
                recv_dir = DIR_OPP[direction]
                self._source_port_fronts[(fx, fy, recv_dir, commodity)] += 1
            else:
                send_dir = DIR_OPP[direction]
                self._sink_port_fronts[(fx, fy, send_dir, commodity)] += 1

    def build(self, time_limit: float = 60.0):
        del time_limit
        t0 = time.time()
        analysis = (
            dict(self._domain_analysis)
            if self._domain_analysis is not None
            else analyze_exact_routing_domain(
                self.grid,
                placement_core=self._placement_core,
            )
        )
        analysis_status = self._domain_analysis_status(analysis)
        self._bind_domain_analysis(analysis, analysis_status=analysis_status)

        if analysis_status not in ROUTING_DOMAIN_VERIFIED_STATUSES:
            self._domain_status_contract_violation = analysis_status
            self.build_stats["domain_status_contract_violation"] = {
                "status": analysis_status,
                "action": "fail_closed_unknown",
            }
            elapsed = time.time() - t0
            print(f"[Routing Model] build {elapsed:.1f}s")
            return

        if self._duplicate_terminal_front_keys:
            self.model.Add(0 == 1)
            self.build_stats["duplicate_terminal_front_keys"] = list(self._duplicate_terminal_front_keys)
            elapsed = time.time() - t0
            print(f"[Routing Model] build {elapsed:.1f}s")
            return

        if analysis_status != ROUTING_DOMAIN_STATUS_FEASIBLE:
            self.model.Add(0 == 1)
            self._record_state_space_stats(defaultdict(int), local_pattern_pruned_states=0)
            self._add_gap_rule()
            elapsed = time.time() - t0
            print(f"[Routing Model] build {elapsed:.1f}s")
            return

        self._create_routing_variables()
        self._add_obstacle_exclusion()
        self._add_capacity_constraints()
        self._add_bridge_constraints()
        self._add_continuity_constraints()
        self._add_directed_edge_balance_constraints()
        self._add_port_adherence()
        self._add_gap_rule()
        self._add_bridge_count_hint()
        elapsed = time.time() - t0
        print(f"[Routing Model] build {elapsed:.1f}s")

    def _domain_analysis_status(self, analysis: Mapping[str, Any]) -> str:
        if "status" not in analysis:
            return ROUTING_DOMAIN_MISSING_STATUS
        return str(analysis["status"])

    def _bind_domain_analysis(
        self,
        analysis: Mapping[str, Any],
        *,
        analysis_status: Optional[str] = None,
    ) -> None:
        self._domain_analysis = dict(analysis)
        self._domain_stats = dict(analysis.get("domain_stats", {}))

        raw_component_cells = dict(analysis.get("commodity_component_cells", {}))
        raw_active_cells = dict(analysis.get("commodity_active_cells", {}))
        port_connector_cells = _port_connector_cells(self.grid.port_specs)
        routable_domain_cells = set(self.grid.free_cells) - port_connector_cells
        for commodity in self.commodities:
            component_cells = {
                (int(cell[0]), int(cell[1]))
                for cell in raw_component_cells.get(commodity, [])
            } & routable_domain_cells
            active_cells = {
                (int(cell[0]), int(cell[1]))
                for cell in raw_active_cells.get(commodity, [])
            } & routable_domain_cells
            self._commodity_component_cells[commodity] = component_cells
            self._commodity_active_cells[commodity] = active_cells

        self.build_stats["domain_analysis"] = {
            "status": str(
                analysis_status
                if analysis_status is not None
                else self._domain_analysis_status(analysis)
            ),
            "domain_stats": dict(self._domain_stats),
            "used_placement_core_reuse": bool(self._placement_core),
        }

    def _iter_state_patterns(self, layer: int) -> Iterable[Dict[str, Any]]:
        if layer == ELEVATED_LAYER:
            for d_in in DIRECTIONS:
                yield {
                    "flow_in": (d_in,),
                    "flow_out": (DIR_OPP[d_in],),
                    "component_type": "bridge",
                }
            return

        for d_in in DIRECTIONS:
            for d_out in DIRECTIONS:
                if d_out == d_in:
                    continue
                yield {
                    "flow_in": (d_in,),
                    "flow_out": (d_out,),
                    "component_type": "belt",
                }

        for d_in in DIRECTIONS:
            remaining = [d for d in DIRECTIONS if d != d_in]
            for out_deg in (2, 3):
                for out_dirs in combinations(remaining, out_deg):
                    yield {
                        "flow_in": (d_in,),
                        "flow_out": tuple(out_dirs),
                        "component_type": "splitter",
                    }

        for d_out in DIRECTIONS:
            remaining = [d for d in DIRECTIONS if d != d_out]
            for in_deg in (2, 3):
                for in_dirs in combinations(remaining, in_deg):
                    yield {
                        "flow_in": tuple(in_dirs),
                        "flow_out": (d_out,),
                        "component_type": "merger",
                    }

    def _neighbor_in_active_domain(self, x: int, y: int, direction: str, commodity: str) -> bool:
        dx, dy = DIR_DELTA[direction]
        return (x + dx, y + dy) in self._commodity_active_cells.get(commodity, set())

    def _incoming_dir_supported(self, x: int, y: int, layer: int, direction: str, commodity: str) -> bool:
        if self._neighbor_in_active_domain(x, y, direction, commodity):
            return True
        if layer != GROUND_LAYER:
            return False
        return self._source_port_fronts.get((x, y, direction, commodity), 0) > 0

    def _outgoing_dir_supported(self, x: int, y: int, layer: int, direction: str, commodity: str) -> bool:
        if self._neighbor_in_active_domain(x, y, direction, commodity):
            return True
        if layer != GROUND_LAYER:
            return False
        return self._sink_port_fronts.get((x, y, direction, commodity), 0) > 0

    def _pattern_is_locally_supported(
        self,
        x: int,
        y: int,
        layer: int,
        commodity: str,
        flow_in: Tuple[str, ...],
        flow_out: Tuple[str, ...],
    ) -> bool:
        return all(
            self._incoming_dir_supported(x, y, layer, direction, commodity)
            for direction in flow_in
        ) and all(
            self._outgoing_dir_supported(x, y, layer, direction, commodity)
            for direction in flow_out
        )

    def _create_routing_variables(self):
        state_counter = defaultdict(int)
        local_pattern_pruned_states = 0

        for commodity in self.commodities:
            for (x, y) in sorted(self._commodity_active_cells.get(commodity, set())):
                for layer in LAYERS:
                    for pattern in self._patterns_by_layer[layer]:
                        flow_in = tuple(pattern["flow_in"])
                        flow_out = tuple(pattern["flow_out"])
                        component_type = str(pattern["component_type"])
                        if not self._pattern_is_locally_supported(
                            x,
                            y,
                            layer,
                            commodity,
                            flow_in,
                            flow_out,
                        ):
                            local_pattern_pruned_states += 1
                            continue

                        phys_key: PhysicalStateKey = (
                            x,
                            y,
                            layer,
                            flow_in,
                            flow_out,
                            component_type,
                        )
                        if phys_key not in self.phys_vars:
                            phys_var = self.model.NewBoolVar(
                                f"phys_{x}_{y}_{layer}_{_dirs_tag(flow_in)}_{_dirs_tag(flow_out)}_{component_type}"
                            )
                            self.phys_vars[phys_key] = phys_var
                            self._phys_meta[phys_key] = {
                                "flow_in": flow_in,
                                "flow_out": flow_out,
                                "component_type": component_type,
                            }
                            self._phys_by_cell_layer[(x, y, layer)].append(phys_var)
                            self._phys_keys_by_cell[(x, y)].append(phys_key)
                            if layer == ELEVATED_LAYER:
                                self._l1_phys_vars[(x, y)].append(phys_var)

                        use_var = self.model.NewBoolVar(
                            f"use_{x}_{y}_{layer}_{_dirs_tag(flow_in)}_{_dirs_tag(flow_out)}_{commodity}"
                        )
                        key: RouteStateKey = (x, y, layer, flow_in, flow_out, commodity)
                        self.use_vars[key] = use_var
                        self._use_to_phys_key[key] = phys_key
                        self._phys_uses[phys_key].append(use_var)
                        self._state_meta[key] = {
                            "flow_in": flow_in,
                            "flow_out": flow_out,
                            "component_type": component_type,
                        }
                        self.model.Add(use_var <= self.phys_vars[phys_key])
                        for d_out in flow_out:
                            self._use_by_cell_layer_dir_out_commodity[(x, y, layer, d_out, commodity)].append(use_var)
                            self._use_by_cell_dir_out_commodity[(x, y, d_out, commodity)].append(use_var)
                        for d_in in flow_in:
                            self._use_by_cell_layer_dir_in_commodity[(x, y, layer, d_in, commodity)].append(use_var)
                            self._use_by_cell_dir_in_commodity[(x, y, d_in, commodity)].append(use_var)
                        state_counter[(layer, component_type)] += 1

        for phys_key, use_vars in self._phys_uses.items():
            self.model.AddMaxEquality(self.phys_vars[phys_key], use_vars)

        self._record_state_space_stats(state_counter, local_pattern_pruned_states)

    def _record_state_space_stats(
        self,
        state_counter: Mapping[Tuple[int, str], int],
        local_pattern_pruned_states: int,
    ) -> None:
        commodity_component_cells = {
            commodity: int(self._domain_stats.get("commodity_component_cells", {}).get(commodity, 0))
            for commodity in self.commodities
            if commodity in self._domain_stats.get("commodity_component_cells", {})
        }
        commodity_active_cells = {
            commodity: int(self._domain_stats.get("commodity_active_cells", {}).get(commodity, 0))
            for commodity in self.commodities
            if commodity in self._domain_stats.get("commodity_active_cells", {})
        }
        naive_full_domain_vars = len(self.grid.free_cells) * len(self.commodities) * self._pattern_count_per_cell

        self.build_stats["state_space"] = {
            "commodities": len(self.commodities),
            "vars": len(self.use_vars),
            "use_vars": len(self.use_vars),
            "phys_vars": len(self.phys_vars),
            "ground_belt_states": int(state_counter.get((GROUND_LAYER, "belt"), 0)),
            "ground_splitter_states": int(state_counter.get((GROUND_LAYER, "splitter"), 0)),
            "ground_merger_states": int(state_counter.get((GROUND_LAYER, "merger"), 0)),
            "elevated_bridge_states": int(state_counter.get((ELEVATED_LAYER, "bridge"), 0)),
            "used_placement_core_reuse": bool(self._placement_core),
            "commodity_component_cells": commodity_component_cells,
            "commodity_active_cells": commodity_active_cells,
            "domain_cells": int(self._domain_stats.get("domain_cells", 0)),
            "terminal_core_cells": int(self._domain_stats.get("terminal_core_cells", 0)),
            "local_pattern_pruned_states": int(local_pattern_pruned_states),
            "naive_full_domain_vars": int(naive_full_domain_vars),
        }

    def _add_obstacle_exclusion(self):
        # Obstacle exclusion is implemented by only creating variables on active free cells.
        return

    def _add_capacity_constraints(self):
        for phys_vars_on_cell_layer in self._phys_by_cell_layer.values():
            if phys_vars_on_cell_layer:
                self.model.AddAtMostOne(phys_vars_on_cell_layer)

    def _add_bridge_constraints(self):
        for cell, phys_keys in self._phys_keys_by_cell.items():
            l0_keys = [key for key in phys_keys if key[2] == GROUND_LAYER]
            l1_keys = [key for key in phys_keys if key[2] == ELEVATED_LAYER]
            if not l0_keys or not l1_keys:
                continue
            for l0_key in l0_keys:
                _x0, _y0, _layer0, l0_flow_in, l0_flow_out, l0_component_type = l0_key
                l0_axis = _state_axis(l0_flow_in, l0_flow_out)
                l0_is_crossable = (
                    l0_component_type == "belt"
                    and _is_straight_state(l0_flow_in, l0_flow_out)
                    and l0_axis is not None
                )
                for l1_key in l1_keys:
                    _x1, _y1, _layer1, l1_flow_in, l1_flow_out, _l1_component_type = l1_key
                    l1_axis = _state_axis(l1_flow_in, l1_flow_out)
                    if l0_is_crossable and l1_axis is not None and l0_axis != l1_axis:
                        continue
                    self.model.Add(self.phys_vars[l0_key] + self.phys_vars[l1_key] <= 1)

    def _add_bridge_count_hint(self):
        """P1 #9 hint 1 (Endfield player consensus): prefer routings that
        use few elevated bridges. Each l1 var (elevated layer cell) gets
        an `add_hint(var, 0)`; CP-SAT treats this as a soft preference,
        not a hard constraint, so feasibility is unchanged.

        Rationale: players report bridge_hop ≤ 2 is the throughput sweet
        spot; this hint biases the search toward those layouts without
        constraining anything. Per AI Safety Contract: order_only / hint
        only, no checkpoint writes, no proof-source modification.
        """
        for cell_vars in self._l1_phys_vars.values():
            for var in cell_vars:
                self.model.AddHint(var, 0)

    def _add_continuity_constraints(self):
        for commodity in self.commodities:
            for (x, y) in self._commodity_active_cells.get(commodity, set()):
                for layer in LAYERS:
                    for d_out in DIRECTIONS:
                        self._add_successor_constraints(x, y, layer, d_out, commodity)
                    for d_in in DIRECTIONS:
                        self._add_predecessor_constraints(x, y, layer, d_in, commodity)

    def _add_directed_edge_balance_constraints(self) -> None:
        """Conserve selected route channels across every interior grid edge.

        The predecessor/successor support constraints are intentionally local:
        a selected state with an outgoing side needs some compatible receiver,
        and a selected state with an incoming side needs some compatible sender.
        With two physical layers, however, a ground belt and an elevated bridge
        may legally occupy the same 2-D cell.  Counting support only as
        ``>= 1`` would let one sender simultaneously justify both layer states,
        creating a phantom splitter/merger at a bridge overlap.  The real grid
        has one channel crossing per selected side, so the number of selected
        senders and receivers must match on each directed cell-to-cell edge.

        Source and sink terminals are not cell-to-cell edges: a source injects
        into its front cell from the port side, and a sink consumes from its
        front cell toward the port side.  Those terminal sides are already
        handled exactly by _add_port_adherence and are skipped here.
        """

        edge_balance_constraints = 0
        for commodity in self.commodities:
            active_cells = self._commodity_active_cells.get(commodity, set())
            for x, y in active_cells:
                for d_out, (dx, dy) in DIR_DELTA.items():
                    if self._sink_port_fronts.get((x, y, d_out, commodity), 0) > 0:
                        continue

                    nx, ny = x + dx, y + dy
                    if (nx, ny) not in active_cells:
                        continue

                    recv_dir = DIR_OPP[d_out]
                    if self._source_port_fronts.get((nx, ny, recv_dir, commodity), 0) > 0:
                        continue

                    send_vars = self._use_by_cell_dir_out_commodity.get(
                        (x, y, d_out, commodity),
                        [],
                    )
                    recv_vars = self._use_by_cell_dir_in_commodity.get(
                        (nx, ny, recv_dir, commodity),
                        [],
                    )
                    if not send_vars and not recv_vars:
                        continue
                    self.model.Add(sum(send_vars) == sum(recv_vars))
                    edge_balance_constraints += 1

        self.build_stats["directed_edge_balance"] = {
            "constraints": int(edge_balance_constraints),
        }

    def _add_successor_constraints(
        self,
        x: int,
        y: int,
        layer: int,
        d_out: str,
        commodity: str,
    ) -> None:
        out_vars = self._use_by_cell_layer_dir_out_commodity.get((x, y, layer, d_out, commodity), [])
        if not out_vars:
            return

        if layer == GROUND_LAYER and self._sink_port_fronts.get((x, y, d_out, commodity), 0) > 0:
            return

        dx, dy = DIR_DELTA[d_out]
        nx, ny = x + dx, y + dy
        if (nx, ny) not in self._commodity_active_cells.get(commodity, set()):
            for var in out_vars:
                self.model.Add(var == 0)
            return

        recv_dir = DIR_OPP[d_out]
        if self._source_port_fronts.get((nx, ny, recv_dir, commodity), 0) > 0:
            for var in out_vars:
                self.model.Add(var == 0)
            return

        recv_vars = self._use_by_cell_dir_in_commodity.get((nx, ny, recv_dir, commodity), [])
        if not recv_vars:
            for var in out_vars:
                self.model.Add(var == 0)
            return

        recv_sum = sum(recv_vars)
        for var in out_vars:
            self.model.Add(recv_sum >= 1).OnlyEnforceIf(var)

    def _add_predecessor_constraints(
        self,
        x: int,
        y: int,
        layer: int,
        d_in: str,
        commodity: str,
    ) -> None:
        in_vars = self._use_by_cell_layer_dir_in_commodity.get((x, y, layer, d_in, commodity), [])
        if not in_vars:
            return

        if layer == GROUND_LAYER and self._source_port_fronts.get((x, y, d_in, commodity), 0) > 0:
            return

        dx, dy = DIR_DELTA[d_in]
        px, py = x + dx, y + dy
        if (px, py) not in self._commodity_active_cells.get(commodity, set()):
            for var in in_vars:
                self.model.Add(var == 0)
            return

        send_dir = DIR_OPP[d_in]
        if self._sink_port_fronts.get((px, py, send_dir, commodity), 0) > 0:
            for var in in_vars:
                self.model.Add(var == 0)
            return

        send_vars = self._use_by_cell_dir_out_commodity.get((px, py, send_dir, commodity), [])
        if not send_vars:
            for var in in_vars:
                self.model.Add(var == 0)
            return

        send_sum = sum(send_vars)
        for var in in_vars:
            self.model.Add(send_sum >= 1).OnlyEnforceIf(var)

    def _add_port_adherence(self):
        exact_links = 0
        blocked_ports = 0

        for ps in self.grid.port_specs:
            px, py = int(ps["x"]), int(ps["y"])
            direction = str(ps["dir"])
            commodity = str(ps["commodity"])
            dx, dy = DIR_DELTA[direction]
            fx, fy = px + dx, py + dy

            if (fx, fy) not in self._commodity_active_cells.get(commodity, set()):
                self.model.Add(0 == 1)
                blocked_ports += 1
                continue

            if str(ps["type"]) == "out":
                recv_dir = DIR_OPP[direction]
                vars_for_port = self._use_by_cell_layer_dir_in_commodity.get(
                    (fx, fy, GROUND_LAYER, recv_dir, commodity),
                    [],
                )
            else:
                send_dir = DIR_OPP[direction]
                vars_for_port = self._use_by_cell_layer_dir_out_commodity.get(
                    (fx, fy, GROUND_LAYER, send_dir, commodity),
                    [],
                )

            if not vars_for_port:
                self.model.Add(0 == 1)
                blocked_ports += 1
                continue

            self.model.Add(sum(vars_for_port) == 1)
            exact_links += 1

        self.build_stats["port_adherence"] = {
            "exact_links": exact_links,
            "blocked_ports": blocked_ports,
            "ports": len(self.grid.port_specs),
        }

    def _add_gap_rule(self):
        # The 1-cell minimum-gap rule is enforced by the placement layer's port-clearance
        # plus the fact that ports connect through their dedicated front free cell.
        self.build_stats["gap_rule"] = {"handled_by_front_cell_model": True}

    def _terminal_fronts_by_commodity(
        self,
    ) -> Tuple[
        Dict[str, Set[Tuple[int, int, str]]],
        Dict[str, Set[Tuple[int, int, str]]],
    ]:
        source_fronts: Dict[str, Set[Tuple[int, int, str]]] = defaultdict(set)
        sink_fronts: Dict[str, Set[Tuple[int, int, str]]] = defaultdict(set)
        for fx, fy, direction, commodity in self._source_port_fronts:
            source_fronts[str(commodity)].add((int(fx), int(fy), str(direction)))
        for fx, fy, direction, commodity in self._sink_port_fronts:
            sink_fronts[str(commodity)].add((int(fx), int(fy), str(direction)))
        return source_fronts, sink_fronts

    def _selected_route_keys(self, solver: cp_model.CpSolver) -> Set[RouteStateKey]:
        selected: Set[RouteStateKey] = set()
        for key, var in self.use_vars.items():
            if solver.Value(var) == 1:
                selected.add(key)
        return selected

    def _front_triples_for_diagnostic(
        self,
        triples: Iterable[Tuple[int, int, str]],
    ) -> List[List[Any]]:
        return [
            [int(x), int(y), str(direction)]
            for x, y, direction in sorted(triples)
        ]

    def _route_state_keys_for_diagnostic(
        self,
        keys: Iterable[RouteStateKey],
        *,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        diagnostics: List[Dict[str, Any]] = []
        for x, y, layer, flow_in, flow_out, commodity in sorted(keys)[:limit]:
            diagnostics.append(
                {
                    "x": int(x),
                    "y": int(y),
                    "layer": int(layer),
                    "flow_in": list(flow_in),
                    "flow_out": list(flow_out),
                    "commodity": str(commodity),
                }
            )
        return diagnostics

    def _route_state_input_index(
        self,
        keys: Iterable[RouteStateKey],
    ) -> Dict[Tuple[int, int, str, str], List[RouteStateKey]]:
        by_input: Dict[Tuple[int, int, str, str], List[RouteStateKey]] = defaultdict(list)
        for key in keys:
            x, y, _layer, flow_in, _flow_out, commodity = key
            for direction in flow_in:
                by_input[(int(x), int(y), str(direction), str(commodity))].append(key)
        return by_input

    def _terminal_nodes_by_front_for_keys(
        self,
        keys: Iterable[RouteStateKey],
        source_fronts: Mapping[str, Set[Tuple[int, int, str]]],
        sink_fronts: Mapping[str, Set[Tuple[int, int, str]]],
    ) -> Tuple[
        Dict[Tuple[str, int, int, str], Set[RouteStateKey]],
        Dict[Tuple[str, int, int, str], Set[RouteStateKey]],
    ]:
        source_nodes_by_front: Dict[Tuple[str, int, int, str], Set[RouteStateKey]] = defaultdict(set)
        sink_nodes_by_front: Dict[Tuple[str, int, int, str], Set[RouteStateKey]] = defaultdict(set)
        for key in keys:
            x, y, layer, flow_in, flow_out, commodity = key
            commodity = str(commodity)
            if layer != GROUND_LAYER:
                continue
            for direction in flow_in:
                front = (int(x), int(y), str(direction))
                if front in source_fronts.get(commodity, set()):
                    source_nodes_by_front[(commodity, front[0], front[1], front[2])].add(key)
            for direction in flow_out:
                front = (int(x), int(y), str(direction))
                if front in sink_fronts.get(commodity, set()):
                    sink_nodes_by_front[(commodity, front[0], front[1], front[2])].add(key)
        return source_nodes_by_front, sink_nodes_by_front

    def _route_state_adjacency(
        self,
        keys: Iterable[RouteStateKey],
        sink_fronts: Mapping[str, Set[Tuple[int, int, str]]],
    ) -> Dict[RouteStateKey, Set[RouteStateKey]]:
        key_set = set(keys)
        by_input = self._route_state_input_index(key_set)
        adjacency: Dict[RouteStateKey, Set[RouteStateKey]] = defaultdict(set)
        for key in key_set:
            x, y, _layer, _flow_in, flow_out, commodity = key
            commodity = str(commodity)
            for direction in flow_out:
                if (int(x), int(y), str(direction)) in sink_fronts.get(commodity, set()):
                    continue
                dx, dy = DIR_DELTA[str(direction)]
                nx, ny = int(x) + dx, int(y) + dy
                recv_dir = DIR_OPP[str(direction)]
                for dst in by_input.get((nx, ny, recv_dir, commodity), []):
                    adjacency[key].add(dst)
        return adjacency

    def _reachable_route_states(
        self,
        starts: Iterable[RouteStateKey],
        adjacency: Mapping[RouteStateKey, Set[RouteStateKey]],
        *,
        removed: Optional[Set[RouteStateKey]] = None,
    ) -> Set[RouteStateKey]:
        blocked = removed or set()
        reachable: Set[RouteStateKey] = set()
        stack = [node for node in starts if node not in blocked]
        while stack:
            current = stack.pop()
            if current in blocked or current in reachable:
                continue
            reachable.add(current)
            for nxt in adjacency.get(current, set()):
                if nxt not in blocked and nxt not in reachable:
                    stack.append(nxt)
        return reachable

    def _commodity_source_start_nodes(
        self,
        commodity: str,
        expected_sources: Iterable[Tuple[int, int, str]],
        source_nodes_by_front: Mapping[Tuple[str, int, int, str], Set[RouteStateKey]],
    ) -> Set[RouteStateKey]:
        starts: Set[RouteStateKey] = set()
        for front in expected_sources:
            starts.update(source_nodes_by_front.get((commodity, front[0], front[1], front[2]), set()))
        return starts

    def _commodity_sink_nodes_by_plain_front(
        self,
        commodity: str,
        expected_sinks: Iterable[Tuple[int, int, str]],
        sink_nodes_by_front: Mapping[Tuple[str, int, int, str], Set[RouteStateKey]],
    ) -> Dict[Tuple[int, int, str], Set[RouteStateKey]]:
        sink_nodes_by_plain_front: Dict[Tuple[int, int, str], Set[RouteStateKey]] = defaultdict(set)
        for front in expected_sinks:
            nodes = set(sink_nodes_by_front.get((commodity, front[0], front[1], front[2]), set()))
            sink_nodes_by_plain_front[front].update(nodes)
        return sink_nodes_by_plain_front

    def _potential_route_keys_for_commodity(self, commodity: str) -> Set[RouteStateKey]:
        return {key for key in self.use_vars if str(key[5]) == str(commodity)}

    def _compute_selected_source_side_closure(
        self,
        selected: Set[RouteStateKey],
        commodity: str,
        expected_sources: Set[Tuple[int, int, str]],
        source_fronts: Mapping[str, Set[Tuple[int, int, str]]],
        sink_fronts: Mapping[str, Set[Tuple[int, int, str]]],
    ) -> Tuple[
        Set[RouteStateKey],
        Dict[Tuple[str, int, int, str], Set[RouteStateKey]],
        Dict[Tuple[str, int, int, str], Set[RouteStateKey]],
    ]:
        selected_for_commodity = {key for key in selected if str(key[5]) == commodity}
        selected_source_nodes_by_front, selected_sink_nodes_by_front = self._terminal_nodes_by_front_for_keys(
            selected_for_commodity,
            source_fronts,
            sink_fronts,
        )
        selected_adjacency = self._route_state_adjacency(selected_for_commodity, sink_fronts)
        starts = self._commodity_source_start_nodes(
            commodity,
            expected_sources,
            selected_source_nodes_by_front,
        )
        return (
            self._reachable_route_states(starts, selected_adjacency),
            selected_source_nodes_by_front,
            selected_sink_nodes_by_front,
        )

    def _source_side_crossing_boundary(
        self,
        commodity: str,
        w_closure: Set[RouteStateKey],
        expected_sources: Set[Tuple[int, int, str]],
        source_fronts: Mapping[str, Set[Tuple[int, int, str]]],
        sink_fronts: Mapping[str, Set[Tuple[int, int, str]]],
    ) -> Set[RouteStateKey]:
        potential_keys = self._potential_route_keys_for_commodity(commodity)
        potential_source_nodes_by_front, _potential_sink_nodes_by_front = self._terminal_nodes_by_front_for_keys(
            potential_keys,
            source_fronts,
            sink_fronts,
        )
        potential_adjacency = self._route_state_adjacency(potential_keys, sink_fronts)

        crossing: Set[RouteStateKey] = set()
        for front in expected_sources:
            for key in potential_source_nodes_by_front.get((commodity, front[0], front[1], front[2]), set()):
                if key not in w_closure:
                    crossing.add(key)
        for src in w_closure:
            for dst in potential_adjacency.get(src, set()):
                if dst not in w_closure:
                    crossing.add(dst)
        return crossing

    def _self_check_source_side_connectivity_cut(
        self,
        *,
        selected: Set[RouteStateKey],
        commodity: str,
        crossing: Set[RouteStateKey],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        source_fronts, sink_fronts = self._terminal_fronts_by_commodity()
        expected_sources = set(source_fronts.get(commodity, set()))
        expected_sinks = set(sink_fronts.get(commodity, set()))
        diagnostics: Dict[str, Any] = {
            "commodity": commodity,
            "source_fronts": self._front_triples_for_diagnostic(expected_sources),
            "sink_fronts": self._front_triples_for_diagnostic(expected_sinks),
        }
        if not expected_sources:
            return False, "missing_source_fronts", diagnostics
        if not expected_sinks:
            return False, "missing_sink_fronts", diagnostics

        potential_keys = self._potential_route_keys_for_commodity(commodity)
        if not crossing <= potential_keys:
            diagnostics["crossing_outside_potential"] = int(len(crossing - potential_keys))
            return False, "crossing_outside_potential_graph", diagnostics

        w_recomputed, selected_source_nodes_by_front, _selected_sink_nodes_by_front = (
            self._compute_selected_source_side_closure(
                selected,
                commodity,
                expected_sources,
                source_fronts,
                sink_fronts,
            )
        )
        diagnostics["w_size"] = int(len(w_recomputed))
        diagnostics["x_size"] = int(len(crossing))

        missing_sources = {
            front
            for front in expected_sources
            if not (
                selected_source_nodes_by_front.get((commodity, front[0], front[1], front[2]), set())
                & w_recomputed
            )
        }
        _potential_source_nodes_by_front, potential_sink_nodes_by_front = self._terminal_nodes_by_front_for_keys(
            potential_keys,
            source_fronts,
            sink_fronts,
        )
        sink_fronts_inside_w = {
            front
            for front in expected_sinks
            if potential_sink_nodes_by_front.get((commodity, front[0], front[1], front[2]), set())
            & w_recomputed
        }
        if missing_sources:
            diagnostics["missing_sources_in_w"] = self._front_triples_for_diagnostic(missing_sources)
            return False, "source_front_not_in_w", diagnostics
        if sink_fronts_inside_w:
            diagnostics["sink_fronts_inside_w"] = self._front_triples_for_diagnostic(sink_fronts_inside_w)
            return False, "sink_front_inside_w", diagnostics

        potential_adjacency = self._route_state_adjacency(potential_keys, sink_fronts)
        potential_source_nodes_by_front, potential_sink_nodes_by_front = self._terminal_nodes_by_front_for_keys(
            potential_keys,
            source_fronts,
            sink_fronts,
        )
        potential_starts = self._commodity_source_start_nodes(
            commodity,
            expected_sources,
            potential_source_nodes_by_front,
        )
        reachable_after_removal = self._reachable_route_states(
            potential_starts,
            potential_adjacency,
            removed=set(crossing),
        )
        sink_nodes_by_front = self._commodity_sink_nodes_by_plain_front(
            commodity,
            expected_sinks,
            potential_sink_nodes_by_front,
        )
        reachable_sink_fronts = {
            front for front, nodes in sink_nodes_by_front.items() if nodes & reachable_after_removal
        }
        if reachable_sink_fronts:
            diagnostics["reachable_sink_fronts_after_x_removal"] = self._front_triples_for_diagnostic(
                reachable_sink_fronts
            )
            return False, "x_not_complete_crossing_boundary", diagnostics

        selected_crossing = selected & crossing
        if selected_crossing:
            diagnostics["selected_crossing_states"] = int(len(selected_crossing))
            return False, "incumbent_intersects_crossing", diagnostics

        return True, "ok", diagnostics

    def _add_source_side_connectivity_cut(
        self,
        solver: cp_model.CpSolver,
        commodity: str,
    ) -> Dict[str, Any]:
        selected = self._selected_route_keys(solver)
        source_fronts, sink_fronts = self._terminal_fronts_by_commodity()
        expected_sources = set(source_fronts.get(commodity, set()))
        expected_sinks = set(sink_fronts.get(commodity, set()))
        if not expected_sources:
            return {"kind": "fallback", "commodity": commodity, "reason": "missing_source_fronts"}
        if not expected_sinks:
            return {"kind": "fallback", "commodity": commodity, "reason": "missing_sink_fronts"}

        w_closure, _selected_source_nodes_by_front, _selected_sink_nodes_by_front = (
            self._compute_selected_source_side_closure(
                selected,
                commodity,
                expected_sources,
                source_fronts,
                sink_fronts,
            )
        )
        crossing = self._source_side_crossing_boundary(
            commodity,
            w_closure,
            expected_sources,
            source_fronts,
            sink_fronts,
        )
        ok, reason, diagnostics = self._self_check_source_side_connectivity_cut(
            selected=selected,
            commodity=commodity,
            crossing=crossing,
        )
        if not ok:
            return {
                "kind": "fallback",
                "commodity": commodity,
                "reason": reason,
                "diagnostics": diagnostics,
            }

        cut_vars = [self.use_vars[key] for key in sorted(crossing)]
        if cut_vars:
            self.model.Add(sum(cut_vars) >= 1)
        else:
            self.model.Add(0 == 1)
        return {
            "kind": "cut",
            "commodity": commodity,
            "size": int(len(cut_vars)),
            "w_size": int(len(w_closure)),
            "self_check": diagnostics,
        }

    def _validate_selected_route_connectivity(
        self,
        solver: cp_model.CpSolver,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate global source→sink reachability for a CP-SAT incumbent.

        The CP-SAT model encodes local predecessor/successor support.  That is
        not enough to prove a commodity has a directed path from every selected
        source front to a sink front, nor that every sink front is fed.  This
        post-solve guard rebuilds the selected route-state graph and rejects any
        incumbent that is only locally closed.
        """

        selected = self._selected_route_keys(solver)
        source_fronts, sink_fronts = self._terminal_fronts_by_commodity()
        source_nodes_by_front, sink_nodes_by_front = self._terminal_nodes_by_front_for_keys(
            selected,
            source_fronts,
            sink_fronts,
        )
        adjacency = self._route_state_adjacency(selected, sink_fronts)
        reverse_adjacency: Dict[RouteStateKey, Set[RouteStateKey]] = defaultdict(set)
        for src, dsts in adjacency.items():
            for dst in dsts:
                reverse_adjacency[dst].add(src)

        failures: List[Dict[str, Any]] = []
        commodities_to_check = sorted(set(source_fronts) | set(sink_fronts) | set(self.commodities))
        for commodity in commodities_to_check:
            selected_for_commodity = {key for key in selected if str(key[5]) == commodity}
            expected_sources = set(source_fronts.get(commodity, set()))
            expected_sinks = set(sink_fronts.get(commodity, set()))
            if not expected_sources and not expected_sinks:
                continue
            missing_sources = {
                front
                for front in expected_sources
                if not source_nodes_by_front.get((commodity, front[0], front[1], front[2]))
            }
            missing_sinks = {
                front
                for front in expected_sinks
                if not sink_nodes_by_front.get((commodity, front[0], front[1], front[2]))
            }

            all_source_nodes = self._commodity_source_start_nodes(
                commodity,
                expected_sources,
                source_nodes_by_front,
            )
            sink_nodes_by_plain_front = self._commodity_sink_nodes_by_plain_front(
                commodity,
                expected_sinks,
                sink_nodes_by_front,
            )
            all_sink_nodes: Set[RouteStateKey] = set()
            for nodes in sink_nodes_by_plain_front.values():
                all_sink_nodes.update(nodes)

            reachable_from_any_source = self._reachable_route_states(all_source_nodes, adjacency)
            sink_reaches_back = self._reachable_route_states(all_sink_nodes, reverse_adjacency)
            valid_witness_closure = reachable_from_any_source & sink_reaches_back
            orphan_selected_route_states = selected_for_commodity - valid_witness_closure
            unreachable_sinks = {
                front
                for front, nodes in sink_nodes_by_plain_front.items()
                if not (nodes & reachable_from_any_source)
            }

            source_fronts_without_sink: Set[Tuple[int, int, str]] = set()
            for front in expected_sources:
                front_nodes = set(source_nodes_by_front.get((commodity, front[0], front[1], front[2]), set()))
                reachable_from_front = self._reachable_route_states(front_nodes, adjacency)
                if not (reachable_from_front & all_sink_nodes):
                    source_fronts_without_sink.add(front)

            if (
                missing_sources
                or missing_sinks
                or unreachable_sinks
                or source_fronts_without_sink
                or orphan_selected_route_states
                or not expected_sources
                or not expected_sinks
            ):
                failures.append(
                    {
                        "commodity": str(commodity),
                        "source_fronts": self._front_triples_for_diagnostic(expected_sources),
                        "sink_fronts": self._front_triples_for_diagnostic(expected_sinks),
                        "missing_source_fronts": self._front_triples_for_diagnostic(missing_sources),
                        "missing_sink_fronts": self._front_triples_for_diagnostic(missing_sinks),
                        "unreachable_sink_fronts": self._front_triples_for_diagnostic(unreachable_sinks),
                        "source_fronts_without_sink": self._front_triples_for_diagnostic(
                            source_fronts_without_sink
                        ),
                        "orphan_selected_route_state_count": int(len(orphan_selected_route_states)),
                        "orphan_selected_route_states": self._route_state_keys_for_diagnostic(
                            orphan_selected_route_states
                        ),
                    }
                )

        summary = {
            "selected_route_states": int(len(selected)),
            "checked_commodities": int(len(commodities_to_check)),
            "failure_count": int(len(failures)),
            "failures": failures,
        }
        return not failures, summary

    def _add_selected_route_nogood(self, solver: cp_model.CpSolver) -> int:
        selected_vars = [
            var
            for key, var in self.use_vars.items()
            if solver.Value(var) == 1 and key in self.use_vars
        ]
        if selected_vars:
            self.model.AddBoolOr([var.Not() for var in selected_vars])
            return int(len(selected_vars))
        self.model.Add(0 == 1)
        return 0

    def _connectivity_guard_telemetry(
        self,
        *,
        attempts: List[Dict[str, Any]],
        rejected_incumbents: int,
        cuts_added: int,
        cut_sizes: List[int],
        fallback_nogoods: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "attempts": attempts,
            "rejected_incumbents": int(rejected_incumbents),
            "cuts_added": int(cuts_added),
            "cut_sizes": [int(size) for size in cut_sizes],
            "fallback_nogoods": [dict(item) for item in fallback_nogoods],
        }

    def _failed_connectivity_commodities(self, connectivity_summary: Mapping[str, Any]) -> List[str]:
        commodities: List[str] = []
        for failure in list(connectivity_summary.get("failures", [])):
            if not isinstance(failure, Mapping):
                continue
            commodity = str(failure.get("commodity", ""))
            if commodity and commodity not in commodities:
                commodities.append(commodity)
        return commodities

    def solve(self, time_limit: float = 60.0) -> str:
        deadline = time.perf_counter() + max(0.0, float(time_limit))
        self._connectivity_guard_accepted = False
        attempts: List[Dict[str, Any]] = []
        rejected_incumbents = 0
        cuts_added = 0
        cut_sizes: List[int] = []
        fallback_nogoods: List[Dict[str, Any]] = []

        if self._domain_status_contract_violation is not None:
            self._solver = None
            self._status = cp_model.UNKNOWN
            self.build_stats["last_solve"] = {
                "status": "ROUTING_DOMAIN_STATUS_CONTRACT_VIOLATION",
                "domain_analysis_status": str(self._domain_status_contract_violation),
                "connectivity_guard": self._connectivity_guard_telemetry(
                    attempts=attempts,
                    rejected_incumbents=rejected_incumbents,
                    cuts_added=cuts_added,
                    cut_sizes=cut_sizes,
                    fallback_nogoods=fallback_nogoods,
                ),
            }
            return "TIMEOUT"

        while True:
            remaining = deadline - time.perf_counter()
            if attempts and remaining <= 0.0:
                self._solver = None
                self._status = cp_model.UNKNOWN
                self.build_stats["last_solve"] = {
                    "status": "CONNECTIVITY_GUARD_TIMEOUT",
                    "wall_time": float(max(0.0, float(time_limit) - max(0.0, remaining))),
                    "connectivity_guard": self._connectivity_guard_telemetry(
                        attempts=attempts,
                        rejected_incumbents=rejected_incumbents,
                        cuts_added=cuts_added,
                        cut_sizes=cut_sizes,
                        fallback_nogoods=fallback_nogoods,
                    ),
                }
                return "TIMEOUT"

            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = max(0.001, float(remaining))
            solver.parameters.num_workers = resolve_cp_sat_worker_count(
                env_name="EXACT_ROUTING_CP_SAT_WORKERS",
                default=DEFAULT_ROUTING_CP_SAT_WORKERS,
            )
            apply_subproblem_memory_cap(solver)

            status = solver.Solve(self.model)
            self._solver = solver
            self._status = status
            attempt_summary: Dict[str, Any] = {
                "status": solver.StatusName(status),
                "wall_time": solver.WallTime(),
                "branches": solver.NumBranches(),
                "conflicts": solver.NumConflicts(),
            }

            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                connected, connectivity_summary = self._validate_selected_route_connectivity(solver)
                attempt_summary["connectivity"] = connectivity_summary
                attempts.append(attempt_summary)
                if connected:
                    self._connectivity_guard_accepted = True
                    self.build_stats["last_solve"] = {
                        **attempt_summary,
                        "connectivity_guard": self._connectivity_guard_telemetry(
                            attempts=attempts,
                            rejected_incumbents=rejected_incumbents,
                            cuts_added=cuts_added,
                            cut_sizes=cut_sizes,
                            fallback_nogoods=fallback_nogoods,
                        ),
                    }
                    return "FEASIBLE"

                rejected_incumbents += 1
                cut_actions: List[Dict[str, Any]] = []
                cut_fallbacks: List[Dict[str, Any]] = []
                failed_commodities = self._failed_connectivity_commodities(connectivity_summary)
                if failed_commodities:
                    for commodity in failed_commodities:
                        action = self._add_source_side_connectivity_cut(solver, commodity)
                        cut_actions.append(action)
                        if action.get("kind") == "cut":
                            cuts_added += 1
                            cut_sizes.append(int(action.get("size", 0)))
                        else:
                            cut_fallbacks.append(action)
                else:
                    cut_fallbacks.append(
                        {
                            "kind": "fallback",
                            "commodity": "",
                            "reason": "no_failed_commodity_diagnostics",
                        }
                    )

                if cut_fallbacks:
                    nogood_size = self._add_selected_route_nogood(solver)
                    attempt_summary["connectivity_nogood_size"] = int(nogood_size)
                    for fallback in cut_fallbacks:
                        fallback_record = {
                            "commodity": str(fallback.get("commodity", "")),
                            "reason": str(fallback.get("reason", "unknown")),
                            "nogood_size": int(nogood_size),
                        }
                        if "diagnostics" in fallback:
                            fallback_record["diagnostics"] = dict(fallback.get("diagnostics", {}))
                        fallback_nogoods.append(fallback_record)
                attempt_summary["connectivity_cut_actions"] = cut_actions or cut_fallbacks
                continue

            attempts.append(attempt_summary)
            self.build_stats["last_solve"] = {
                **attempt_summary,
                "connectivity_guard": self._connectivity_guard_telemetry(
                    attempts=attempts,
                    rejected_incumbents=rejected_incumbents,
                    cuts_added=cuts_added,
                    cut_sizes=cut_sizes,
                    fallback_nogoods=fallback_nogoods,
                ),
            }

            if status == cp_model.INFEASIBLE:
                return "INFEASIBLE"
            return "TIMEOUT"

    def extract_routes(self) -> List[Dict[str, Any]]:
        if (
            self._status not in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            or not bool(getattr(self, "_connectivity_guard_accepted", False))
        ):
            return []

        routes_by_phys: Dict[PhysicalStateKey, List[RouteStateKey]] = defaultdict(list)
        for key, var in self.use_vars.items():
            if self._solver is None or self._solver.Value(var) != 1:
                continue
            routes_by_phys[self._use_to_phys_key[key]].append(key)

        routes = []
        for phys_key, use_keys in sorted(routes_by_phys.items()):
            x, y, layer, flow_in, flow_out, component_type = phys_key
            uses = [
                {
                    "commodity": str(commodity),
                    "flow_in": list(use_flow_in),
                    "flow_out": list(use_flow_out),
                }
                for _ux, _uy, _ulayer, use_flow_in, use_flow_out, commodity in sorted(use_keys)
            ]
            commodities = sorted({str(use["commodity"]) for use in uses})
            route = {
                "x": x,
                "y": y,
                "layer": layer,
                "type": component_type,
                "component_type": component_type,
                "commodities": commodities,
                "uses": uses,
                "flow_in": list(flow_in),
                "flow_out": list(flow_out),
                "flow": {
                    "flow_in": list(flow_in),
                    "flow_out": list(flow_out),
                },
            }
            if len(commodities) == 1:
                route["commodity"] = commodities[0]
            if len(flow_in) == 1:
                route["dir_in"] = flow_in[0]
            if len(flow_out) == 1:
                route["dir_out"] = flow_out[0]
            routes.append(route)
        return routes

    def extract_conflict_set(self) -> Optional[Dict[str, int]]:
        return None

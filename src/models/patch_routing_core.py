"""PCR-CUT Phase 1 — Patch-restricted exact belt CP-SAT.

跟 routing_subproblem.RoutingSubproblem 同结构, 但:
- 只在 patch.cells 内建 vars
- 出 patch boundary 用 boundary_out/in 虚拟 vars 不约束总数 (over-approx, 保
  INFEASIBLE sound)
- 每个 owner 的 binding pattern 选择是 assumption literal — patch INFEASIBLE
  时从 UNSAT core 抽 PoseAssumption.

Sound guarantee: 全图 routing FEASIBLE ⇒ patch routing FEASIBLE.
逆否: patch routing INFEASIBLE ⇒ 全图也 INFEASIBLE 给定那组 pose+binding pattern.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, FrozenSet, Iterable, List, Literal, Mapping, Optional, Sequence, Set, Tuple

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

PatchRouteStateKey = Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...], str]


@dataclass(frozen=True)
class PatchSpec:
    """Patch geometry. cells = 所有要 model 的格子 (free + occupied 都算), boundary_cells
    = patch 内但邻居含 patch 外的 cell."""
    patch_id: str
    cells: FrozenSet[Tuple[int, int]]
    boundary_cells: FrozenSet[Tuple[int, int]]
    bbox: Tuple[int, int, int, int]
    source_witness: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_cells(
        patch_id: str,
        cells: Iterable[Tuple[int, int]],
        *,
        source_witness: Optional[Mapping[str, Any]] = None,
    ) -> "PatchSpec":
        cell_set = frozenset((int(x), int(y)) for x, y in cells)
        if not cell_set:
            return PatchSpec(patch_id, frozenset(), frozenset(), (0, 0, -1, -1), dict(source_witness or {}))
        xs = [c[0] for c in cell_set]
        ys = [c[1] for c in cell_set]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        boundary: Set[Tuple[int, int]] = set()
        for (x, y) in cell_set:
            for d, (dx, dy) in DIR_DELTA.items():
                nx, ny = x + dx, y + dy
                if (nx, ny) not in cell_set:
                    boundary.add((x, y))
                    break
        return PatchSpec(
            patch_id=patch_id,
            cells=cell_set,
            boundary_cells=frozenset(boundary),
            bbox=bbox,
            source_witness=dict(source_witness or {}),
        )


@dataclass(frozen=True)
class PoseAssumption:
    """Master-level decision contributing to this patch.

    instance_id: owner facility instance.
    pose_idx: which pose master picked.
    local_signature: pose footprint + port-front cells inside patch (lifted by Phase 3).
    assumption_name: CP-SAT BoolVar name for UNSAT-core extraction.
    """
    instance_id: str
    pose_idx: int
    local_signature: str
    assumption_name: str


@dataclass(frozen=True)
class PoseLocalSignature:
    """Phase 3 — pose signature local to a patch.

    Two poses share the same signature iff they are interchangeable from the patch
    router's perspective: identical footprint cells inside patch, identical port-front
    cells inside patch with identical (direction, commodity, type) tuples, and
    identical operation/facility metadata. This is the equivalence relation that
    signature lifting exploits: a core nogood on one pose covers all signature-equivalent
    poses of the same owner.

    `key` is a stable hashable representation suitable for use as a dict key.
    """
    facility_type: str
    operation_type: str
    footprint_in_patch: FrozenSet[Tuple[int, int]]
    ports_in_patch: Tuple[Tuple[int, int, str, str, str], ...]  # (x, y, dir, commodity, type)

    @property
    def key(self) -> Tuple[str, str, FrozenSet[Tuple[int, int]], Tuple[Tuple[int, int, str, str, str], ...]]:
        return (self.facility_type, self.operation_type, self.footprint_in_patch, self.ports_in_patch)


def build_local_pose_signature(
    *,
    facility_type: str,
    operation_type: str,
    pose: Mapping[str, Any],
    patch_cells: FrozenSet[Tuple[int, int]],
) -> PoseLocalSignature:
    """Compute the patch-local signature of a pose.

    Only patch-overlapping geometry contributes; ports whose port_cell is outside the
    patch are dropped because they are not constrained by the patch router. The
    resulting signature is the equivalence class under "same patch routing
    requirements", which is exactly the relation that justifies a single core cut
    covering multiple poses.
    """
    occupied = pose.get("occupied_cells") or []
    footprint = frozenset(
        (int(c[0]), int(c[1]))
        for c in occupied
        if (int(c[0]), int(c[1])) in patch_cells
    )
    port_entries: List[Tuple[int, int, str, str, str]] = []
    for side_key, side_type in (("input_port_cells", "in"), ("output_port_cells", "out")):
        for port in pose.get(side_key, []) or []:
            x = int(port["x"])
            y = int(port["y"])
            if (x, y) not in patch_cells:
                continue
            d = str(port.get("dir", ""))
            commodity = str(port.get("commodity", ""))
            port_entries.append((x, y, d, commodity, side_type))
    port_entries.sort()
    return PoseLocalSignature(
        facility_type=str(facility_type),
        operation_type=str(operation_type),
        footprint_in_patch=footprint,
        ports_in_patch=tuple(port_entries),
    )


@dataclass
class PatchRoutingCoreResult:
    status: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    patch_id: str
    wall_s: float
    var_count: int
    constraint_count: int
    core: List[PoseAssumption] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def _dirs_tag(dirs: Iterable[str]) -> str:
    return "".join(dirs) or "none"


def _is_straight_state(flow_in: Tuple[str, ...], flow_out: Tuple[str, ...]) -> bool:
    return (
        len(flow_in) == 1
        and len(flow_out) == 1
        and DIR_OPP[flow_in[0]] == flow_out[0]
    )


def _iter_state_patterns(layer: int) -> Iterable[Dict[str, Any]]:
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


@dataclass
class PatchPortSpec:
    """A port that lies inside the patch (its port cell is in patch.cells)."""
    instance_id: str
    x: int
    y: int
    direction: str  # facility-side outward direction
    commodity: str
    type: str  # "in" | "out"
    pose_idx: int


class PatchRoutingCore:
    """Patch-restricted exact belt CP-SAT, with boundary relaxation + assumption-keyed
    binding pattern selection."""

    def __init__(
        self,
        patch_spec: PatchSpec,
        *,
        full_grid_occupied: Iterable[Tuple[int, int]],
        full_grid_active_cells: Mapping[str, Iterable[Tuple[int, int]]],
        patch_port_specs: Sequence[PatchPortSpec],
        pose_assumptions: Sequence[PoseAssumption],
        boundary_relaxation: bool = True,
    ):
        self.patch_spec = patch_spec
        self.boundary_relaxation = bool(boundary_relaxation)
        self.full_grid_occupied: Set[Tuple[int, int]] = {
            (int(x), int(y)) for x, y in full_grid_occupied
        }
        self.full_grid_active_cells: Dict[str, Set[Tuple[int, int]]] = {
            str(c): {(int(x), int(y)) for x, y in cells}
            for c, cells in full_grid_active_cells.items()
        }
        self.patch_port_specs: List[PatchPortSpec] = list(patch_port_specs)
        self.pose_assumptions: List[PoseAssumption] = list(pose_assumptions)

        self.model = cp_model.CpModel()
        self._assumption_vars: Dict[str, Any] = {}
        self._r_vars: Dict[PatchRouteStateKey, Any] = {}
        self._state_meta: Dict[PatchRouteStateKey, Dict[str, Any]] = {}
        self._vars_by_cell_layer: Dict[Tuple[int, int, int], List[Any]] = defaultdict(list)
        self._vars_by_cell_layer_dir_out_commodity: Dict[Tuple[int, int, int, str, str], List[Any]] = defaultdict(list)
        self._vars_by_cell_layer_dir_in_commodity: Dict[Tuple[int, int, int, str, str], List[Any]] = defaultdict(list)
        self._vars_by_cell_dir_out_commodity: Dict[Tuple[int, int, str, str], List[Any]] = defaultdict(list)
        self._vars_by_cell_dir_in_commodity: Dict[Tuple[int, int, str, str], List[Any]] = defaultdict(list)
        self._l1_vars: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
        self._l0_nonstraight_vars: Dict[Tuple[int, int], List[Any]] = defaultdict(list)

        # Boundary virtual vars: (cell, layer, dir, commodity) → BoolVar
        # boundary_out: route exits patch through this cell along dir
        # boundary_in: route enters patch through this cell from dir
        self._boundary_out_vars: Dict[Tuple[int, int, int, str, str], Any] = {}
        self._boundary_in_vars: Dict[Tuple[int, int, int, str, str], Any] = {}

        self._patch_free_cells: Set[Tuple[int, int]] = set()
        self._patch_active_cells_by_commodity: Dict[str, Set[Tuple[int, int]]] = {}
        self._patterns_by_layer = {
            layer: list(_iter_state_patterns(layer))
            for layer in LAYERS
        }
        self._patch_port_fronts_source: Dict[Tuple[int, int, str, str], int] = defaultdict(int)
        self._patch_port_fronts_sink: Dict[Tuple[int, int, str, str], int] = defaultdict(int)
        self._build_stats: Dict[str, Any] = {}

        self._solver: Optional[cp_model.CpSolver] = None
        self._status: Optional[int] = None

    @property
    def commodities(self) -> List[str]:
        return sorted(self.full_grid_active_cells.keys())

    def build(self) -> None:
        t0 = time.perf_counter()
        self._compute_patch_cells()
        if not self._patch_free_cells:
            self.model.Add(0 == 1)
            self._build_stats = {"empty_patch": True}
            return
        self._index_port_fronts()
        self._create_assumption_vars()
        self._create_routing_variables()
        self._create_boundary_vars()
        self._add_capacity_constraints()
        self._add_bridge_constraints()
        self._add_continuity_constraints()
        self._add_port_adherence()
        elapsed = time.perf_counter() - t0
        self._build_stats["wall_build_s"] = round(elapsed, 3)
        self._build_stats["var_count"] = len(self._r_vars) + len(self._boundary_out_vars) + len(self._boundary_in_vars) + len(self._assumption_vars)
        self._build_stats["constraint_count"] = self.model.Proto().constraints.__len__()

    def _compute_patch_cells(self) -> None:
        patch_set = self.patch_spec.cells
        self._patch_free_cells = {cell for cell in patch_set if cell not in self.full_grid_occupied}
        for commodity, full_active in self.full_grid_active_cells.items():
            self._patch_active_cells_by_commodity[commodity] = full_active & self._patch_free_cells

    def _index_port_fronts(self) -> None:
        """Patch 内 port 的 front cell — 跟 routing_subproblem._index_port_fronts 同语义."""
        for ps in self.patch_port_specs:
            px, py = ps.x, ps.y
            if (px, py) not in self.patch_spec.cells:
                # port lies outside patch → ignore (cross-patch interface goes via boundary relaxation)
                continue
            dx, dy = DIR_DELTA[ps.direction]
            fx, fy = px + dx, py + dy
            if (fx, fy) not in self._patch_free_cells:
                continue
            if ps.type == "out":
                recv_dir = DIR_OPP[ps.direction]
                self._patch_port_fronts_source[(fx, fy, recv_dir, ps.commodity)] += 1
            else:
                self._patch_port_fronts_sink[(fx, fy, ps.direction, ps.commodity)] += 1

    def _create_assumption_vars(self) -> None:
        for pa in self.pose_assumptions:
            v = self.model.NewBoolVar(pa.assumption_name)
            self._assumption_vars[pa.assumption_name] = v

    def _neighbor_in_active_domain(self, x: int, y: int, direction: str, commodity: str) -> bool:
        dx, dy = DIR_DELTA[direction]
        return (x + dx, y + dy) in self._patch_active_cells_by_commodity.get(commodity, set())

    def _neighbor_is_outside_patch_but_in_full_active(self, x: int, y: int, direction: str, commodity: str) -> bool:
        dx, dy = DIR_DELTA[direction]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
            return False
        if (nx, ny) in self.patch_spec.cells:
            return False
        return (nx, ny) in self.full_grid_active_cells.get(commodity, set())

    def _incoming_dir_supported(self, x: int, y: int, layer: int, direction: str, commodity: str) -> bool:
        if self._neighbor_in_active_domain(x, y, direction, commodity):
            return True
        if layer == GROUND_LAYER and self._patch_port_fronts_source.get((x, y, direction, commodity), 0) > 0:
            return True
        # boundary relaxation: incoming from outside patch but inside full active
        if self.boundary_relaxation and self._neighbor_is_outside_patch_but_in_full_active(x, y, direction, commodity):
            return True
        return False

    def _outgoing_dir_supported(self, x: int, y: int, layer: int, direction: str, commodity: str) -> bool:
        if self._neighbor_in_active_domain(x, y, direction, commodity):
            return True
        if layer == GROUND_LAYER and self._patch_port_fronts_sink.get((x, y, direction, commodity), 0) > 0:
            return True
        if self.boundary_relaxation and self._neighbor_is_outside_patch_but_in_full_active(x, y, direction, commodity):
            return True
        return False

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
            self._incoming_dir_supported(x, y, layer, d, commodity)
            for d in flow_in
        ) and all(
            self._outgoing_dir_supported(x, y, layer, d, commodity)
            for d in flow_out
        )

    def _create_routing_variables(self) -> None:
        for commodity in self.commodities:
            active = self._patch_active_cells_by_commodity.get(commodity, set())
            for (x, y) in sorted(active):
                for layer in LAYERS:
                    for pattern in self._patterns_by_layer[layer]:
                        flow_in = tuple(pattern["flow_in"])
                        flow_out = tuple(pattern["flow_out"])
                        component_type = str(pattern["component_type"])
                        if not self._pattern_is_locally_supported(x, y, layer, commodity, flow_in, flow_out):
                            continue
                        var = self.model.NewBoolVar(
                            f"pr_{x}_{y}_{layer}_{_dirs_tag(flow_in)}_{_dirs_tag(flow_out)}_{commodity}"
                        )
                        key: PatchRouteStateKey = (x, y, layer, flow_in, flow_out, commodity)
                        self._r_vars[key] = var
                        self._state_meta[key] = {
                            "flow_in": flow_in,
                            "flow_out": flow_out,
                            "component_type": component_type,
                        }
                        self._vars_by_cell_layer[(x, y, layer)].append(var)
                        for d_out in flow_out:
                            self._vars_by_cell_layer_dir_out_commodity[(x, y, layer, d_out, commodity)].append(var)
                            self._vars_by_cell_dir_out_commodity[(x, y, d_out, commodity)].append(var)
                        for d_in in flow_in:
                            self._vars_by_cell_layer_dir_in_commodity[(x, y, layer, d_in, commodity)].append(var)
                            self._vars_by_cell_dir_in_commodity[(x, y, d_in, commodity)].append(var)
                        if layer == ELEVATED_LAYER:
                            self._l1_vars[(x, y)].append(var)
                        elif component_type != "belt" or not _is_straight_state(flow_in, flow_out):
                            self._l0_nonstraight_vars[(x, y)].append(var)

    def _create_boundary_vars(self) -> None:
        """For each patch boundary cell, create boundary_in/out vars for each direction that
        crosses out of patch (per commodity, ground layer only — bridges don't cross boundary)."""
        if not self.boundary_relaxation:
            return
        for cell in self.patch_spec.boundary_cells:
            if cell not in self._patch_free_cells:
                continue
            x, y = cell
            for commodity in self.commodities:
                if cell not in self._patch_active_cells_by_commodity.get(commodity, set()):
                    continue
                for d in DIRECTIONS:
                    if self._neighbor_is_outside_patch_but_in_full_active(x, y, d, commodity):
                        out_key = (x, y, GROUND_LAYER, d, commodity)
                        self._boundary_out_vars[out_key] = self.model.NewBoolVar(
                            f"bdry_out_{x}_{y}_{d}_{commodity}"
                        )
                        in_key = (x, y, GROUND_LAYER, d, commodity)
                        self._boundary_in_vars[in_key] = self.model.NewBoolVar(
                            f"bdry_in_{x}_{y}_{d}_{commodity}"
                        )

    def _add_capacity_constraints(self) -> None:
        # one belt-state per (cell, layer). boundary vars do not consume cell capacity
        # because they represent route segments outside the patch.
        for vars_on_cell_layer in self._vars_by_cell_layer.values():
            if vars_on_cell_layer:
                self.model.AddAtMostOne(vars_on_cell_layer)

    def _add_bridge_constraints(self) -> None:
        for cell, l1_vars in self._l1_vars.items():
            if not l1_vars:
                continue
            l0_nonstraight = self._l0_nonstraight_vars.get(cell, [])
            if not l0_nonstraight:
                continue
            x, y = cell
            l1_any = self.model.NewBoolVar(f"pl1_any_{x}_{y}")
            self.model.AddMaxEquality(l1_any, l1_vars)
            for var in l0_nonstraight:
                self.model.AddImplication(l1_any, var.Not())

    def _add_continuity_constraints(self) -> None:
        for commodity in self.commodities:
            active = self._patch_active_cells_by_commodity.get(commodity, set())
            for (x, y) in active:
                for layer in LAYERS:
                    for d_out in DIRECTIONS:
                        self._add_successor_constraint(x, y, layer, d_out, commodity)
                    for d_in in DIRECTIONS:
                        self._add_predecessor_constraint(x, y, layer, d_in, commodity)

    def _add_successor_constraint(self, x: int, y: int, layer: int, d_out: str, commodity: str) -> None:
        out_vars = self._vars_by_cell_layer_dir_out_commodity.get((x, y, layer, d_out, commodity), [])
        if not out_vars:
            return

        # sink port: route can terminate at this port
        if layer == GROUND_LAYER and self._patch_port_fronts_sink.get((x, y, d_out, commodity), 0) > 0:
            return

        dx, dy = DIR_DELTA[d_out]
        nx, ny = x + dx, y + dy

        # successor cell is inside patch active domain
        if (nx, ny) in self._patch_active_cells_by_commodity.get(commodity, set()):
            recv_dir = DIR_OPP[d_out]
            recv_vars = self._vars_by_cell_dir_in_commodity.get((nx, ny, recv_dir, commodity), [])
            if not recv_vars:
                for var in out_vars:
                    self.model.Add(var == 0)
                return
            recv_sum = sum(recv_vars)
            for var in out_vars:
                self.model.Add(recv_sum >= 1).OnlyEnforceIf(var)
            return

        # successor is outside patch — boundary relaxation
        if layer == GROUND_LAYER and self.boundary_relaxation:
            bdry_var = self._boundary_out_vars.get((x, y, GROUND_LAYER, d_out, commodity))
            if bdry_var is not None:
                for var in out_vars:
                    self.model.AddImplication(var, bdry_var)
                return

        # no successor support
        for var in out_vars:
            self.model.Add(var == 0)

    def _add_predecessor_constraint(self, x: int, y: int, layer: int, d_in: str, commodity: str) -> None:
        in_vars = self._vars_by_cell_layer_dir_in_commodity.get((x, y, layer, d_in, commodity), [])
        if not in_vars:
            return

        # source port: route can originate from this port
        if layer == GROUND_LAYER and self._patch_port_fronts_source.get((x, y, d_in, commodity), 0) > 0:
            return

        dx, dy = DIR_DELTA[d_in]
        px, py = x + dx, y + dy

        if (px, py) in self._patch_active_cells_by_commodity.get(commodity, set()):
            send_dir = DIR_OPP[d_in]
            send_vars = self._vars_by_cell_dir_out_commodity.get((px, py, send_dir, commodity), [])
            if not send_vars:
                for var in in_vars:
                    self.model.Add(var == 0)
                return
            send_sum = sum(send_vars)
            for var in in_vars:
                self.model.Add(send_sum >= 1).OnlyEnforceIf(var)
            return

        if layer == GROUND_LAYER and self.boundary_relaxation:
            bdry_var = self._boundary_in_vars.get((x, y, GROUND_LAYER, d_in, commodity))
            if bdry_var is not None:
                for var in in_vars:
                    self.model.AddImplication(var, bdry_var)
                return

        for var in in_vars:
            self.model.Add(var == 0)

    def _add_port_adherence(self) -> None:
        """Patch 内 port 在对应 owner 的 assumption literal 为真时必有恰好一条 belt-edge
        接驳. assumption 为假时 port 不强制 — 这让 UNSAT core 能定位到具体 owner."""
        # Build instance_id → assumption literals lookup
        assumption_by_instance: Dict[str, List[Any]] = defaultdict(list)
        for pa in self.pose_assumptions:
            v = self._assumption_vars.get(pa.assumption_name)
            if v is not None:
                assumption_by_instance[pa.instance_id].append(v)

        exact_links = 0
        blocked_ports = 0
        unconditional_links = 0
        for ps in self.patch_port_specs:
            px, py = ps.x, ps.y
            if (px, py) not in self.patch_spec.cells:
                continue
            dx, dy = DIR_DELTA[ps.direction]
            fx, fy = px + dx, py + dy

            assumption_lits = assumption_by_instance.get(ps.instance_id, [])

            if (fx, fy) not in self._patch_active_cells_by_commodity.get(ps.commodity, set()):
                # Front cell not in patch-local active set. Two cases:
                # (a) front is outside the patch but inside full-grid active → boundary
                #     relaxation absorbs the requirement (over-approx: route assumed to
                #     leave the patch and complete outside).
                # (b) front is truly blocked (occupied or out-of-bounds) → INFEASIBLE
                #     for this owner.
                front_in_full = (fx, fy) in self.full_grid_active_cells.get(ps.commodity, set())
                if self.boundary_relaxation and front_in_full:
                    unconditional_links += 1  # accept trivially via boundary
                    continue
                if assumption_lits:
                    for v in assumption_lits:
                        self.model.AddBoolOr([v.Not()])  # forbid this owner
                else:
                    self.model.Add(0 == 1)
                blocked_ports += 1
                continue

            if ps.type == "out":
                recv_dir = DIR_OPP[ps.direction]
                vars_for_port = self._vars_by_cell_layer_dir_in_commodity.get(
                    (fx, fy, GROUND_LAYER, recv_dir, ps.commodity), []
                )
            else:
                vars_for_port = self._vars_by_cell_layer_dir_out_commodity.get(
                    (fx, fy, GROUND_LAYER, ps.direction, ps.commodity), []
                )

            if not vars_for_port:
                if assumption_lits:
                    for v in assumption_lits:
                        self.model.AddBoolOr([v.Not()])
                else:
                    self.model.Add(0 == 1)
                blocked_ports += 1
                continue

            if assumption_lits:
                # link == 1 only when all owner's assumption literals are true
                # represented as: sum(vars_for_port) == 1 OnlyEnforceIf the conjunction
                # For a single assumption per owner this is straightforward.
                for v in assumption_lits:
                    self.model.Add(sum(vars_for_port) == 1).OnlyEnforceIf(v)
                exact_links += 1
            else:
                self.model.Add(sum(vars_for_port) == 1)
                unconditional_links += 1

        self._build_stats["port_adherence"] = {
            "exact_links": exact_links,
            "unconditional_links": unconditional_links,
            "blocked_ports": blocked_ports,
            "patch_ports": len(self.patch_port_specs),
        }

    def solve(self, time_limit: float = 5.0) -> str:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_PATCH_ROUTING_CP_SAT_WORKERS",
            default=DEFAULT_ROUTING_CP_SAT_WORKERS,
        )
        apply_subproblem_memory_cap(solver)

        # Mark assumption literals so we can extract a sufficient core on INFEASIBLE.
        for name, var in self._assumption_vars.items():
            self.model.AddAssumption(var)

        t0 = time.perf_counter()
        status = solver.Solve(self.model)
        elapsed = time.perf_counter() - t0
        self._solver = solver
        self._status = status
        self._build_stats["wall_solve_s"] = round(elapsed, 3)
        self._build_stats["solver_status"] = solver.StatusName(status)
        self._build_stats["branches"] = solver.NumBranches()
        self._build_stats["conflicts"] = solver.NumConflicts()

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return "FEASIBLE"
        if status == cp_model.INFEASIBLE:
            return "INFEASIBLE"
        return "UNKNOWN"

    def extract_core(self) -> List[PoseAssumption]:
        """On INFEASIBLE, return the subset of pose_assumptions that suffice for infeasibility."""
        if self._solver is None or self._status != cp_model.INFEASIBLE:
            return []
        try:
            core_var_indices = self._solver.SufficientAssumptionsForInfeasibility()
        except AttributeError:
            return list(self.pose_assumptions)
        if not core_var_indices:
            return []
        # SufficientAssumptionsForInfeasibility returns proto var indices; map back via name.
        # Build index → name lookup.
        proto = self.model.Proto()
        index_to_name = {i: var.name for i, var in enumerate(proto.variables)}
        core_names = {index_to_name.get(abs(int(i))) for i in core_var_indices}
        result: List[PoseAssumption] = []
        for pa in self.pose_assumptions:
            if pa.assumption_name in core_names:
                result.append(pa)
        return result

    def build_result(self) -> PatchRoutingCoreResult:
        status_str: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
        if self._status is None:
            status_str = "MODEL_INVALID"
        elif self._status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            status_str = "FEASIBLE"
        elif self._status == cp_model.INFEASIBLE:
            status_str = "INFEASIBLE"
        else:
            status_str = "UNKNOWN"
        core = self.extract_core() if status_str == "INFEASIBLE" else []
        return PatchRoutingCoreResult(
            status=status_str,
            patch_id=self.patch_spec.patch_id,
            wall_s=float(self._build_stats.get("wall_solve_s", 0.0)),
            var_count=int(self._build_stats.get("var_count", 0)),
            constraint_count=int(self._build_stats.get("constraint_count", 0)),
            core=core,
            stats=dict(self._build_stats),
        )


def solve_patch_routing_core(
    patch_spec: PatchSpec,
    *,
    full_grid_occupied: Iterable[Tuple[int, int]],
    full_grid_active_cells: Mapping[str, Iterable[Tuple[int, int]]],
    patch_port_specs: Sequence[PatchPortSpec],
    pose_assumptions: Sequence[PoseAssumption],
    time_limit: float = 5.0,
    boundary_relaxation: bool = True,
) -> PatchRoutingCoreResult:
    core = PatchRoutingCore(
        patch_spec=patch_spec,
        full_grid_occupied=full_grid_occupied,
        full_grid_active_cells=full_grid_active_cells,
        patch_port_specs=patch_port_specs,
        pose_assumptions=pose_assumptions,
        boundary_relaxation=boundary_relaxation,
    )
    core.build()
    core.solve(time_limit=time_limit)
    return core.build_result()


# ============================================================
# Phase 2 — replay validation + QuickXplain core minimization
# ============================================================


@dataclass
class PatchCoreValidationResult:
    """Outcome of replay-validating a candidate core.

    invalid=True when the replay did NOT reproduce INFEASIBLE under the candidate core
    alone, or any candidate name does not correspond to an actual assumption literal.
    Any 'accepted' downstream cut MUST come from invalid=False results — fail-closed.
    """
    status: Literal["INFEASIBLE", "FEASIBLE", "UNKNOWN"]
    candidate_core: List[PoseAssumption]
    replay_wall_s: float
    invalid: bool
    invalid_reason: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)


def _add_assumption_subset(model: cp_model.CpModel, assumption_vars: Mapping[str, Any], subset: Iterable[str]) -> None:
    """Reset model.Proto().assumptions and re-add only the named literal indices.

    OR-Tools CP-SAT doesn't expose a public Clear API; the proto's `assumptions`
    repeated field is the source of truth, so we mutate it directly.
    """
    proto = model.Proto()
    proto.assumptions.clear()
    for name in subset:
        v = assumption_vars.get(name)
        if v is None:
            continue
        model.AddAssumption(v)


def _solve_with_subset(
    core: "PatchRoutingCore",
    subset_names: Iterable[str],
    *,
    time_limit: float,
    presolve: bool,
    workers: int,
) -> Tuple[str, float, int]:
    """Re-solve the same model with a fresh assumption subset. Used by validate + QuickXplain.

    Returns (status_str, wall_s, status_code).
    """
    _add_assumption_subset(core.model, core._assumption_vars, subset_names)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    if not presolve:
        solver.parameters.cp_model_presolve = False
    if workers > 0:
        solver.parameters.num_workers = workers
    else:
        solver.parameters.num_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_PATCH_ROUTING_CP_SAT_WORKERS",
            default=DEFAULT_ROUTING_CP_SAT_WORKERS,
        )
    apply_subproblem_memory_cap(solver)
    t0 = time.perf_counter()
    status = solver.Solve(core.model)
    elapsed = time.perf_counter() - t0
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return "FEASIBLE", elapsed, status
    if status == cp_model.INFEASIBLE:
        return "INFEASIBLE", elapsed, status
    return "UNKNOWN", elapsed, status


def validate_patch_core(
    core: PatchRoutingCore,
    candidate_core: Sequence[PoseAssumption],
    *,
    time_limit: float = 5.0,
    presolve: bool = False,
    workers: int = 1,
) -> PatchCoreValidationResult:
    """Replay: with ONLY candidate_core's assumption literals enabled, is the patch model
    still INFEASIBLE? Defaults: presolve=false, workers=1 for determinism.

    fail-closed: any non-assumption literal in candidate → invalid; FEASIBLE/UNKNOWN → invalid.
    """
    valid_names = {pa.assumption_name for pa in core.pose_assumptions}
    candidate_names = {pa.assumption_name for pa in candidate_core}
    invalid_names = candidate_names - valid_names
    if invalid_names:
        return PatchCoreValidationResult(
            status="UNKNOWN",
            candidate_core=list(candidate_core),
            replay_wall_s=0.0,
            invalid=True,
            invalid_reason=f"non_assumption_literals: {sorted(invalid_names)}",
        )

    status_str, wall_s, _status_code = _solve_with_subset(
        core,
        candidate_names,
        time_limit=time_limit,
        presolve=presolve,
        workers=workers,
    )
    is_valid = status_str == "INFEASIBLE"
    return PatchCoreValidationResult(
        status=status_str,  # type: ignore[arg-type]
        candidate_core=list(candidate_core),
        replay_wall_s=round(wall_s, 3),
        invalid=not is_valid,
        invalid_reason="replay_not_infeasible" if not is_valid else "",
        stats={
            "presolve": presolve,
            "workers": workers,
            "core_size": len(candidate_core),
        },
    )


@dataclass
class QuickXplainResult:
    minimal_core: List[PoseAssumption]
    raw_core: List[PoseAssumption]
    oracle_calls: int
    capped: bool
    wall_s: float


def minimize_patch_core_quickxplain(
    core: PatchRoutingCore,
    raw_core: Sequence[PoseAssumption],
    *,
    time_limit_per_call: float = 5.0,
    oracle_call_cap: int = 32,
    presolve: bool = False,
    workers: int = 1,
) -> QuickXplainResult:
    """Junker's QuickXplain to find a minimal subset of raw_core whose assumption is
    still sufficient for INFEASIBLE.

    Oracle is `solve_with_subset(...) == 'INFEASIBLE'`. When the cap fires, we return
    the conservative remaining candidate set (super-set of the true minimal) — caller
    must then re-validate before use.
    """
    name_to_pa: Dict[str, PoseAssumption] = {pa.assumption_name: pa for pa in raw_core}
    sorted_names = sorted(name_to_pa.keys())

    call_count = [0]
    capped = [False]
    t_start = time.perf_counter()

    def oracle(assumed: Set[str]) -> bool:
        if call_count[0] >= oracle_call_cap:
            capped[0] = True
            return True
        call_count[0] += 1
        status, _, _ = _solve_with_subset(
            core, assumed, time_limit=time_limit_per_call, presolve=presolve, workers=workers,
        )
        return status == "INFEASIBLE"

    def quickxplain(background: Set[str], candidates: List[str]) -> Set[str]:
        if capped[0]:
            return set(candidates)
        if not candidates:
            return set()
        if oracle(background):
            return set()
        if len(candidates) == 1:
            return {candidates[0]}
        k = len(candidates) // 2
        c1 = candidates[:k]
        c2 = candidates[k:]
        x2 = quickxplain(background | set(c1), c2)
        x1 = quickxplain(background | x2, c1)
        return x1 | x2

    minimal_names = quickxplain(set(), sorted_names)
    minimal_core = [name_to_pa[n] for n in sorted(minimal_names) if n in name_to_pa]
    return QuickXplainResult(
        minimal_core=minimal_core,
        raw_core=list(raw_core),
        oracle_calls=call_count[0],
        capped=capped[0],
        wall_s=round(time.perf_counter() - t_start, 3),
    )


def extract_and_validate_patch_core(
    core: PatchRoutingCore,
    *,
    minimize: bool = True,
    time_limit_per_call: float = 5.0,
    oracle_call_cap: int = 32,
) -> Dict[str, Any]:
    """Composite: extract solver core → validate raw → optionally minimize via QuickXplain
    → validate minimized. Returns full lifecycle metadata.

    Any cut accepted downstream MUST be the `minimized_validation`'s candidate_core
    when `accepted=True`. accepted=False ⇒ fail-closed, no cut.
    """
    raw_core = core.extract_core()
    if not raw_core:
        return {
            "accepted": False,
            "reason": "no_raw_core_from_solver",
            "raw_core_size": 0,
            "minimized_core_size": 0,
            "raw_validation": None,
            "minimized_validation": None,
            "quickxplain": None,
        }

    raw_validation = validate_patch_core(core, raw_core, time_limit=time_limit_per_call)
    if raw_validation.invalid:
        return {
            "accepted": False,
            "reason": f"raw_replay_invalid: {raw_validation.invalid_reason}",
            "raw_core_size": len(raw_core),
            "minimized_core_size": 0,
            "raw_validation": raw_validation,
            "minimized_validation": None,
            "quickxplain": None,
        }

    if not minimize:
        return {
            "accepted": True,
            "reason": "raw_validated",
            "raw_core_size": len(raw_core),
            "minimized_core_size": len(raw_core),
            "raw_validation": raw_validation,
            "minimized_validation": raw_validation,
            "quickxplain": None,
        }

    qx = minimize_patch_core_quickxplain(
        core, raw_core,
        time_limit_per_call=time_limit_per_call,
        oracle_call_cap=oracle_call_cap,
    )
    minimized_validation = validate_patch_core(core, qx.minimal_core, time_limit=time_limit_per_call)
    if minimized_validation.invalid:
        # fall back to raw_validation (which we already proved valid above)
        return {
            "accepted": True,
            "reason": "minimization_failed_replay_fallback_raw",
            "raw_core_size": len(raw_core),
            "minimized_core_size": len(raw_core),
            "raw_validation": raw_validation,
            "minimized_validation": raw_validation,
            "quickxplain": qx,
        }
    return {
        "accepted": True,
        "reason": "minimized_validated",
        "raw_core_size": len(raw_core),
        "minimized_core_size": len(qx.minimal_core),
        "raw_validation": raw_validation,
        "minimized_validation": minimized_validation,
        "quickxplain": qx,
    }

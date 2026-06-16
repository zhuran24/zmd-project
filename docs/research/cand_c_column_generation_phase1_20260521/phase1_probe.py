"""Phase 1 probe — CG upgrade with integer reconstruction (see README.md)."""

from __future__ import annotations

import argparse
import json
import os
import random
import resource
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple,
)

# Local Phase 1 modules (loaded via package path manipulation so we don't
# need to install as a package).
HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
# Re-export under the phase1 package namespace so the validator's
# `from .column_grammar import ...` works.
_pkg_init = HERE / "__init__.py"
if not _pkg_init.exists():
    _pkg_init.write_text("")
sys.path.insert(0, str(HERE.parent))
from cand_c_column_generation_phase1_20260521.column_grammar import (  # noqa: E402
    BoundarySignature,
    CellCoord,
    FacilityAssignment,
    Pattern,
    PortTuple,
    RegionBBox,
    build_pattern,
    compute_boundary_signature,
)
from cand_c_column_generation_phase1_20260521.integer_validator import (  # noqa: E402
    DirectMasterPoseIndex,
    PHASE1_GHOST_ANCHOR,
    PHASE1_GHOST_SIZE,
    ValidationReport,
    build_direct_master_pose_index,
    is_in_ghost_rect,
    validate_integer_reconstruction,
)


# === Paths + IO ===

PROJECT_ROOT = HERE.parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "preprocessed"
RESULTS_PATH = HERE / "phase1_results.json"
STATUS_PATH = HERE / "phase1_status.json"


# === Phase 1 thresholds ===
# Phase 0 thresholds carried forward + new m10/m11/m12.

GO_THRESHOLDS_5 = {
    "m1_generated_columns_max": 2636,
    "m2_pricing_p95_seconds_max": 10.0,
    "m3_rmp_lp_p95_seconds_max": 5.0,
    "m4_rss_gb_max": 4.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
    "m9_proxy_dual_active_pct_max": 30.0,
    "m9_proxy_dual_sparsity_max": 20.0,
    # 5-inst is size-artifact territory: Phase 0 already noted m5/m6 NO-GO
    # on this size; Phase 1 keeps soft m5/m6 (advisory only) and only hard
    # gates m7/m8/m10.
    "soft_m5_m6": True,
    "m10_integer_reconstruction_required": False,  # 5-inst trivial.
    "m11_branching_nodes_max": 200,
    "m12_avg_facilities_per_column_max": 15.0,
}
GO_THRESHOLDS_20 = {
    "m1_generated_columns_max": 5272,
    "m2_pricing_p95_seconds_max": 30.0,
    "m3_rmp_lp_p95_seconds_max": 5.0,
    "m4_rss_gb_max": 4.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
    "m9_proxy_dual_active_pct_max": 30.0,
    "m9_proxy_dual_sparsity_max": 20.0,
    "soft_m5_m6": False,
    "m10_integer_reconstruction_required": True,
    "m11_branching_nodes_max": 500,
    "m12_avg_facilities_per_column_max": 15.0,
}
GO_THRESHOLDS_40 = {
    "m1_generated_columns_max": 10000,           # 40 inst, ~10x leeway over 5-inst.
    "m2_pricing_p95_seconds_max": 45.0,
    "m3_rmp_lp_p95_seconds_max": 5.0,
    "m4_rss_gb_max": 4.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
    "m9_proxy_dual_active_pct_max": 30.0,
    "m9_proxy_dual_sparsity_max": 20.0,
    "soft_m5_m6": False,
    "m10_integer_reconstruction_required": True,
    "m11_branching_nodes_max": 1000,
    "m12_avg_facilities_per_column_max": 15.0,
}
GO_THRESHOLDS_80 = {
    "m1_generated_columns_max": 20000,
    "m2_pricing_p95_seconds_max": 60.0,
    "m3_rmp_lp_p95_seconds_max": 8.0,
    "m4_rss_gb_max": 8.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
    "m9_proxy_dual_active_pct_max": 30.0,
    "m9_proxy_dual_sparsity_max": 20.0,
    "soft_m5_m6": False,
    "m10_integer_reconstruction_required": True,
    "m11_branching_nodes_max": 1000,
    "m12_avg_facilities_per_column_max": 15.0,
}

PROXY_DUAL_NONZERO_EPS = 1e-7
PROXY_DUAL_SIGNIFICANT_EPS = 0.1


def _peak_rss_gb() -> float:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return float(ru.ru_maxrss) / (1024.0 * 1024.0)


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, int(round(0.95 * (len(s) - 1))))
    return float(s[k])


def _log(msg: str) -> None:
    print(f"[phase1 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# === Pose loading (re-implementation; Phase 1 doesn't import from src/) ===


@dataclass(frozen=True)
class PoseRecord:
    tpl: str
    pose_idx: int
    cells: FrozenSet[CellCoord]
    anchor: Tuple[int, int]
    typed_ports: Tuple[PortTuple, ...]  # (x, y, dir, io)
    port_cells: FrozenSet[CellCoord]
    port_count: int


def load_pose_pools() -> Dict[str, List[PoseRecord]]:
    raw = json.loads((DATA_DIR / "candidate_placements.json").read_text("utf-8"))
    pools = raw["facility_pools"]
    out: Dict[str, List[PoseRecord]] = {}
    for tpl, pose_list in pools.items():
        recs: List[PoseRecord] = []
        for idx, pose in enumerate(pose_list):
            cells = frozenset(
                (int(c[0]), int(c[1])) for c in pose.get("occupied_cells", [])
            )
            anchor = (int(pose["anchor"]["x"]), int(pose["anchor"]["y"]))
            in_ports = pose.get("input_port_cells") or []
            out_ports = pose.get("output_port_cells") or []
            typed: List[PortTuple] = []
            for p in in_ports:
                typed.append((int(p["x"]), int(p["y"]), str(p.get("dir", "?")), "input"))
            for p in out_ports:
                typed.append((int(p["x"]), int(p["y"]), str(p.get("dir", "?")), "output"))
            port_cells_set = frozenset((x, y) for (x, y, _d, _io) in typed)
            recs.append(
                PoseRecord(
                    tpl=tpl,
                    pose_idx=idx,
                    cells=cells,
                    anchor=anchor,
                    typed_ports=tuple(typed),
                    port_cells=port_cells_set,
                    port_count=len(typed),
                )
            )
        out[tpl] = recs
    return out


def load_mandatory() -> List[Dict[str, Any]]:
    return json.loads((DATA_DIR / "mandatory_exact_instances.json").read_text("utf-8"))


# === Subset selection (mirrors Phase 0) ===


def select_subset(
    mandatory: List[Dict[str, Any]],
    n_target: int,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in mandatory:
        by_type[m["facility_type"]].append(m)
    keys = sorted(by_type.keys())
    rng.shuffle(keys)
    chosen: List[Dict[str, Any]] = []
    pointers = {k: 0 for k in keys}
    while len(chosen) < n_target:
        progress = False
        for k in keys:
            if len(chosen) >= n_target:
                break
            if pointers[k] < len(by_type[k]):
                chosen.append(by_type[k][pointers[k]])
                pointers[k] += 1
                progress = True
        if not progress:
            break
    return chosen


# === m9 perimeter I/O capacity proxy windows ===


def build_proxy_windows(
    grid_w: int = 70, grid_h: int = 70, window_size: int = 12
) -> List[RegionBBox]:
    windows: List[RegionBBox] = []
    for x_lo in range(0, grid_w, window_size):
        for y_lo in range(0, grid_h, window_size):
            x_hi = min(x_lo + window_size - 1, grid_w - 1)
            y_hi = min(y_lo + window_size - 1, grid_h - 1)
            windows.append((x_lo, y_lo, x_hi, y_hi))
    return windows


def proxy_window_capacity(window: RegionBBox) -> int:
    x_lo, y_lo, x_hi, y_hi = window
    w = x_hi - x_lo + 1
    h = y_hi - y_lo + 1
    perimeter_cells = max(0, 2 * (w + h) - 4)
    raw = perimeter_cells * 4
    corner_penalty = 4 * 4 if w >= 2 and h >= 2 else 0
    return max(0, raw - corner_penalty)


def pattern_port_count_in_window(
    pattern: Pattern, window: RegionBBox
) -> int:
    x_lo, y_lo, x_hi, y_hi = window
    return sum(
        1 for (cx, cy) in pattern.port_cells
        if x_lo <= cx <= x_hi and y_lo <= cy <= y_hi
    )


# === Pose -> Pattern builders ===


def pose_within_region(pose: PoseRecord, region: RegionBBox) -> bool:
    x_lo, y_lo, x_hi, y_hi = region
    return all(
        x_lo <= cx <= x_hi and y_lo <= cy <= y_hi for cx, cy in pose.cells
    )


def enumerate_poses_in_region(
    tpl: str,
    pools: Dict[str, List[PoseRecord]],
    region: RegionBBox,
    max_poses: int = 4096,
) -> List[PoseRecord]:
    out: List[PoseRecord] = []
    for pose in pools[tpl]:
        if pose_within_region(pose, region):
            out.append(pose)
            if len(out) >= max_poses:
                break
    return out


def pose_to_pattern(instance_id: str, tpl: str, pose: PoseRecord) -> Pattern:
    return build_pattern(
        facility_assignments=[(instance_id, tpl, pose.pose_idx)],
        occupied_cells=pose.cells,
        typed_ports=pose.typed_ports,
        region=None,
    )


def column_from_pricing_assignment(
    chosen: Sequence[Tuple[str, str, int]],
    pose_lookup: Mapping[Tuple[str, int], PoseRecord],
    region: RegionBBox,
) -> Pattern:
    occupied: Set[CellCoord] = set()
    typed_ports: List[PortTuple] = []
    for (iid, _tpl, pose_idx) in chosen:
        pose = pose_lookup[(iid, pose_idx)]
        occupied.update(pose.cells)
        typed_ports.extend(pose.typed_ports)
    return build_pattern(
        facility_assignments=chosen,
        occupied_cells=frozenset(occupied),
        typed_ports=typed_ports,
        region=region,
    )


def degenerate_singleton_columns(
    instances: Sequence[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
) -> List[Pattern]:
    cols: List[Pattern] = []
    committed: Set[CellCoord] = set()
    for inst in instances:
        tpl = inst["facility_type"]
        iid = inst["instance_id"]
        chosen: Optional[PoseRecord] = None
        for pose in pools[tpl]:
            if not pose.cells:
                continue
            if pose.cells.isdisjoint(committed):
                # Reject poses that drop into the ghost rect.
                if any(is_in_ghost_rect(c) for c in pose.cells):
                    continue
                chosen = pose
                break
        if chosen is None:
            # Fall back: pose that doesn't intersect ghost rect even if it
            # collides with already-committed cells.  RMP will pay a
            # penalty but stays LP-feasible.
            for pose in pools[tpl]:
                if not pose.cells:
                    continue
                if any(is_in_ghost_rect(c) for c in pose.cells):
                    continue
                chosen = pose
                break
        if chosen is None:
            continue
        cols.append(pose_to_pattern(iid, tpl, chosen))
        committed.update(chosen.cells)
    return cols


# === RMP (LP) + ghost-rect-aware ===


@dataclass
class RMPSolveResult:
    objective: float
    lp_seconds: float
    lambda_values: List[float]
    facility_duals: Dict[str, float]
    cell_duals: Dict[CellCoord, float]
    status_str: str
    proxy_duals: Dict[RegionBBox, float] = field(default_factory=dict)


def _filter_active_cells(columns: Sequence[Pattern]) -> FrozenSet[CellCoord]:
    cells: Set[CellCoord] = set()
    for col in columns:
        cells.update(col.occupied_cells)
    return frozenset(cells)


def solve_rmp(
    columns: Sequence[Pattern],
    instance_ids: Sequence[str],
    proxy_windows: Optional[Sequence[RegionBBox]] = None,
    branching_fixed: Optional[Dict[int, int]] = None,
) -> RMPSolveResult:
    """LP relaxation of set-partitioning RMP.  branching_fixed pins λ_k for B&P."""
    from ortools.linear_solver import pywraplp

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("GLOP solver unavailable")
    solver.SuppressOutput()
    infty = solver.infinity()

    lambda_vars = []
    for k in range(len(columns)):
        lo, hi = 0.0, 1.0
        if branching_fixed and k in branching_fixed:
            lo = float(branching_fixed[k])
            hi = float(branching_fixed[k])
        lambda_vars.append(solver.NumVar(lo, hi, f"l_{k}"))

    # Set-partitioning: each instance covered EXACTLY once.  Phase 0 used
    # ≥1 (cover); Phase 1 hardens to ==1 so the LP optimum is the
    # integer feasible region's relaxation (Task 2 requires partition).
    cov_ctrs: Dict[str, Any] = {}
    for iid in instance_ids:
        ctr = solver.Constraint(1.0, 1.0, f"cov_{iid}")
        cov_ctrs[iid] = ctr
    for k, pat in enumerate(columns):
        for iid in pat.covered_instance_ids:
            if iid in cov_ctrs:
                cov_ctrs[iid].SetCoefficient(lambda_vars[k], 1.0)

    # Cell exclusivity (<=1).
    all_cells = _filter_active_cells(columns)
    cell_ctrs: Dict[CellCoord, Any] = {}
    for cell in all_cells:
        ctr = solver.Constraint(-infty, 1.0, f"cell_{cell[0]}_{cell[1]}")
        cell_ctrs[cell] = ctr
    for k, pat in enumerate(columns):
        for cell in pat.occupied_cells:
            if cell in cell_ctrs:
                cell_ctrs[cell].SetCoefficient(lambda_vars[k], 1.0)

    # m9 proxy windows (perimeter I/O capacity).
    proxy_ctrs: Dict[RegionBBox, Any] = {}
    if proxy_windows:
        for w in proxy_windows:
            cap = proxy_window_capacity(w)
            ctr = solver.Constraint(
                -infty, float(cap),
                f"proxy_{w[0]}_{w[1]}_{w[2]}_{w[3]}"
            )
            proxy_ctrs[w] = ctr
        for k, pat in enumerate(columns):
            if not pat.port_cells:
                continue
            for w, ctr in proxy_ctrs.items():
                ports_in_w = pattern_port_count_in_window(pat, w)
                if ports_in_w:
                    ctr.SetCoefficient(lambda_vars[k], float(ports_in_w))

    obj = solver.Objective()
    obj.SetMinimization()
    for k, pat in enumerate(columns):
        obj.SetCoefficient(lambda_vars[k], float(pat.cost))

    t0 = time.perf_counter()
    status = solver.Solve()
    lp_seconds = time.perf_counter() - t0

    status_map = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
        pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
        pywraplp.Solver.ABNORMAL: "ABNORMAL",
        pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    }
    status_str = status_map.get(status, f"UNKNOWN_{status}")
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return RMPSolveResult(
            objective=float("inf"),
            lp_seconds=lp_seconds,
            lambda_values=[0.0] * len(columns),
            facility_duals={iid: 0.0 for iid in instance_ids},
            cell_duals={cell: 0.0 for cell in all_cells},
            status_str=status_str,
            proxy_duals={w: 0.0 for w in proxy_ctrs},
        )

    facility_duals = {iid: cov_ctrs[iid].dual_value() for iid in instance_ids}
    cell_duals = {cell: -cell_ctrs[cell].dual_value() for cell in all_cells}
    proxy_duals = {w: -proxy_ctrs[w].dual_value() for w in proxy_ctrs}
    return RMPSolveResult(
        objective=obj.Value(),
        lp_seconds=lp_seconds,
        lambda_values=[v.solution_value() for v in lambda_vars],
        facility_duals=facility_duals,
        cell_duals=cell_duals,
        status_str=status_str,
        proxy_duals=proxy_duals,
    )


# === Pricing CP-SAT (region-bounded) — ghost-rect aware ===


@dataclass
class PricingResult:
    reduced_cost: float
    pattern: Optional[Pattern]
    var_count: int
    wall_seconds: float
    status_str: str


def solve_pricing(
    instances: Sequence[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
    region: RegionBBox,
    facility_duals: Mapping[str, float],
    cell_duals: Mapping[CellCoord, float],
    max_facilities: int = 15,
    time_limit_s: float = 5.0,
) -> PricingResult:
    """Region-bounded CP-SAT pricing; Phase 1 drops ghost-rect-overlapping poses."""
    from ortools.sat.python import cp_model

    SCALE = 1000
    model = cp_model.CpModel()
    z_vars: Dict[Tuple[str, int], Any] = {}
    pose_lookup: Dict[Tuple[str, int], PoseRecord] = {}
    by_cell: Dict[CellCoord, List[Any]] = defaultdict(list)
    by_instance: Dict[str, List[Any]] = defaultdict(list)

    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        for pose in enumerate_poses_in_region(tpl, pools, region):
            if any(is_in_ghost_rect(c) for c in pose.cells):
                continue
            v = model.NewBoolVar(f"z_{iid}_{pose.pose_idx}")
            key = (iid, pose.pose_idx)
            z_vars[key] = v
            pose_lookup[key] = pose
            by_instance[iid].append(v)
            for cell in pose.cells:
                by_cell[cell].append(v)

    if not z_vars:
        return PricingResult(
            reduced_cost=0.0,
            pattern=None,
            var_count=0,
            wall_seconds=0.0,
            status_str="EMPTY",
        )

    for iid, vs in by_instance.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)
    for cell, vs in by_cell.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)

    total = sum(z_vars.values())
    model.Add(total <= max_facilities)
    model.Add(total >= 2)

    obj_terms = []
    for (iid, pose_idx), v in z_vars.items():
        pose = pose_lookup[(iid, pose_idx)]
        pi = float(facility_duals.get(iid, 0.0))
        cell_penalty = sum(float(cell_duals.get(c, 0.0)) for c in pose.cells)
        coeff = -(pi + cell_penalty)
        obj_terms.append(int(round(coeff * SCALE)) * v)

    if obj_terms:
        model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 4
    solver.parameters.log_search_progress = False

    t0 = time.perf_counter()
    status = solver.Solve(model)
    wall = time.perf_counter() - t0
    status_str = solver.StatusName(status)
    var_count = len(z_vars)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return PricingResult(
            reduced_cost=0.0,
            pattern=None,
            var_count=var_count,
            wall_seconds=wall,
            status_str=status_str,
        )

    reduced_cost = 1.0 + float(solver.ObjectiveValue()) / SCALE
    chosen: List[FacilityAssignment] = []
    for (iid, pose_idx), v in z_vars.items():
        if solver.Value(v) == 1:
            pose = pose_lookup[(iid, pose_idx)]
            inst = next(i for i in instances if i["instance_id"] == iid)
            chosen.append((iid, inst["facility_type"], pose_idx))

    if not chosen:
        return PricingResult(
            reduced_cost=reduced_cost,
            pattern=None,
            var_count=var_count,
            wall_seconds=wall,
            status_str=status_str,
        )
    pat = column_from_pricing_assignment(chosen, pose_lookup, region)
    return PricingResult(
        reduced_cost=reduced_cost,
        pattern=pat,
        var_count=var_count,
        wall_seconds=wall,
        status_str=status_str,
    )


# === Region iteration ===


def iter_regions(
    grid_w: int, grid_h: int, region_size: int, stride: int,
    rng: random.Random,
) -> List[RegionBBox]:
    regions: List[RegionBBox] = []
    for x_lo in range(0, max(1, grid_w - region_size + 1), stride):
        for y_lo in range(0, max(1, grid_h - region_size + 1), stride):
            regions.append((x_lo, y_lo, x_lo + region_size - 1, y_lo + region_size - 1))
    rng.shuffle(regions)
    return regions


# === Direct master (for m7/m8/m10 sanity) ===


@dataclass
class DirectMasterResult:
    var_count: int
    lp_objective: float
    integer_objective: float
    wall_seconds: float
    status_str: str
    pose_index: Optional[DirectMasterPoseIndex] = None


def solve_direct_mini_master(
    instances: Sequence[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
    region: RegionBBox,
    time_limit_s: float = 30.0,
    build_pose_index: bool = True,
) -> DirectMasterResult:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    z_vars: Dict[Tuple[str, int], Any] = {}
    by_cell: Dict[CellCoord, List[Any]] = defaultdict(list)
    by_instance: Dict[str, List[Any]] = defaultdict(list)

    # Build pose index for direct-master equivalence checks.
    pose_pools_by_iid: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        for pose in enumerate_poses_in_region(tpl, pools, region):
            if any(is_in_ghost_rect(c) for c in pose.cells):
                continue
            v = model.NewBoolVar(f"d_{iid}_{pose.pose_idx}")
            z_vars[(iid, pose.pose_idx)] = v
            by_instance[iid].append(v)
            for cell in pose.cells:
                by_cell[cell].append(v)
            pose_pools_by_iid[iid].append({
                "pose_idx": pose.pose_idx, "cells": list(pose.cells),
            })

    for iid in (inst["instance_id"] for inst in instances):
        vs = by_instance.get(iid, [])
        if not vs:
            model.Add(0 == 1)
        else:
            model.Add(sum(vs) == 1)
    for cell, vs in by_cell.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)

    model.Minimize(sum(z_vars.values()) if z_vars else 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 4
    t0 = time.perf_counter()
    status = solver.Solve(model)
    wall = time.perf_counter() - t0
    status_str = solver.StatusName(status)
    obj_int = float(solver.ObjectiveValue()) if status in (
        cp_model.OPTIMAL, cp_model.FEASIBLE,
    ) else float("inf")

    pose_index = None
    if build_pose_index:
        pose_index = build_direct_master_pose_index(instances, pose_pools_by_iid)

    return DirectMasterResult(
        var_count=len(z_vars),
        lp_objective=obj_int,
        integer_objective=obj_int,
        wall_seconds=wall,
        status_str=status_str,
        pose_index=pose_index,
    )


# === Manual depth-first branching tree ===


@dataclass
class BranchNode:
    fixed: Dict[int, int]
    depth: int


@dataclass
class BranchStats:
    nodes_explored: int = 0
    integer_leaves_found: int = 0
    best_objective: float = float("inf")
    best_lambda: Optional[List[float]] = None
    timed_out: bool = False
    max_depth_reached: int = 0


def most_fractional_index(
    lambda_values: Sequence[float], fixed: Mapping[int, int],
    tol: float = 1e-6,
) -> Optional[int]:
    best_idx: Optional[int] = None
    best_dist = 0.0
    for k, lam in enumerate(lambda_values):
        if k in fixed:
            continue
        if tol < lam < 1.0 - tol:
            d = min(lam, 1.0 - lam)
            if d > best_dist:
                best_dist = d
                best_idx = k
    return best_idx


def branch_and_price_depth_first(
    columns: Sequence[Pattern],
    instance_ids: Sequence[str],
    *,
    max_depth: int = 5,
    max_nodes: int = 1000,
    integer_tol: float = 1e-6,
    wall_budget_s: float = 60.0,
    proxy_windows: Optional[Sequence[RegionBBox]] = None,
) -> BranchStats:
    """DFS B&P over the fixed column pool (no re-pricing inside tree)."""
    stats = BranchStats()
    t0 = time.perf_counter()

    stack: List[BranchNode] = [BranchNode(fixed={}, depth=0)]
    while stack:
        if time.perf_counter() - t0 > wall_budget_s:
            stats.timed_out = True
            break
        if stats.nodes_explored >= max_nodes:
            break
        node = stack.pop()
        stats.nodes_explored += 1
        stats.max_depth_reached = max(stats.max_depth_reached, node.depth)

        rmp_res = solve_rmp(
            columns, instance_ids,
            proxy_windows=proxy_windows,
            branching_fixed=node.fixed,
        )
        if rmp_res.status_str not in ("OPTIMAL", "FEASIBLE"):
            # infeasible node, prune.
            continue
        if rmp_res.objective >= stats.best_objective - 1e-9:
            # bound-prune.
            continue

        frac_idx = most_fractional_index(
            rmp_res.lambda_values, node.fixed, tol=integer_tol,
        )
        if frac_idx is None:
            # All integer in unfixed vars.  We have an integer feasible.
            stats.integer_leaves_found += 1
            if rmp_res.objective < stats.best_objective:
                stats.best_objective = rmp_res.objective
                stats.best_lambda = list(rmp_res.lambda_values)
            continue

        if node.depth >= max_depth:
            # Hit depth cap; treat as fractional terminal, don't claim
            # an integer leaf here.
            continue
        # Push down-branch first (LIFO → up-branch explored first).
        down_fixed = dict(node.fixed); down_fixed[frac_idx] = 0
        up_fixed = dict(node.fixed); up_fixed[frac_idx] = 1
        stack.append(BranchNode(fixed=down_fixed, depth=node.depth + 1))
        stack.append(BranchNode(fixed=up_fixed, depth=node.depth + 1))

    return stats


# === Column generation loop ===


@dataclass
class CGRunStats:
    label: str
    n_instances: int
    columns_total: int = 0
    columns_multi: int = 0
    columns_single: int = 0
    multi_pct: float = 0.0
    single_pct: float = 0.0
    pricing_walls: List[float] = field(default_factory=list)
    rmp_walls: List[float] = field(default_factory=list)
    pricing_var_counts: List[int] = field(default_factory=list)
    final_rmp_objective: float = float("inf")
    iterations: int = 0
    direct_master_vars: int = 0
    direct_master_objective: float = float("inf")
    direct_master_wall: float = 0.0
    peak_rss_gb: float = 0.0
    exit_reason: str = "unknown"
    proxy_dual_samples: List[List[float]] = field(default_factory=list)
    proxy_window_count: int = 0
    # Phase 1 additions.
    avg_facilities_per_column: float = 0.0
    max_facilities_per_column: int = 0
    branching: Optional[BranchStats] = None
    validation: Optional[ValidationReport] = None


def run_column_generation_phase1(
    instances: List[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
    label: str,
    *,
    grid_w: int = 70, grid_h: int = 70,
    region_size: int = 12, stride: int = 6,
    max_iterations: int = 60,
    pricing_time_limit: float = 5.0,
    rng_seed: int = 17,
    branching_max_depth: int = 5,
    branching_max_nodes: int = 1000,
    branching_wall_budget_s: float = 60.0,
    skip_branching: bool = False,
) -> CGRunStats:
    rng = random.Random(rng_seed)
    instance_ids = [m["instance_id"] for m in instances]

    columns: List[Pattern] = degenerate_singleton_columns(instances, pools)
    _log(f"[{label}] bootstrapped {len(columns)} singleton columns")

    regions = iter_regions(grid_w, grid_h, region_size, stride, rng)
    proxy_windows = build_proxy_windows(grid_w, grid_h, region_size)
    _log(f"[{label}] {len(regions)} regions, {len(proxy_windows)} proxy windows")

    stats = CGRunStats(label=label, n_instances=len(instances),
                       proxy_window_count=len(proxy_windows))

    region_cursor = 0
    EPSILON = -1e-6
    for it in range(max_iterations):
        rmp_res = solve_rmp(
            columns, instance_ids,
            proxy_windows=proxy_windows,
        )
        stats.rmp_walls.append(rmp_res.lp_seconds)
        if rmp_res.status_str not in ("OPTIMAL", "FEASIBLE"):
            stats.exit_reason = f"rmp_{rmp_res.status_str}_at_iter_{it}"
            _log(f"[{label}] RMP not optimal: {rmp_res.status_str}, abort")
            break
        if rmp_res.proxy_duals:
            stats.proxy_dual_samples.append(
                [rmp_res.proxy_duals[w] for w in proxy_windows]
            )
        if it % 5 == 0 or it < 3:
            _log(
                f"[{label}] iter {it}  cols={len(columns)}  "
                f"rmp_obj={rmp_res.objective:.3f}  "
                f"rmp_wall={rmp_res.lp_seconds:.3f}s"
            )

        TRIES_PER_ITER = 4
        tried = 0
        best_neg: Optional[PricingResult] = None
        while tried < TRIES_PER_ITER and region_cursor < len(regions) * 4:
            region = regions[region_cursor % len(regions)]
            region_cursor += 1
            tried += 1
            pricing_res = solve_pricing(
                instances, pools, region,
                rmp_res.facility_duals, rmp_res.cell_duals,
                time_limit_s=pricing_time_limit,
            )
            stats.pricing_walls.append(pricing_res.wall_seconds)
            if pricing_res.var_count:
                stats.pricing_var_counts.append(pricing_res.var_count)
            if (
                pricing_res.pattern is not None
                and pricing_res.reduced_cost < EPSILON
            ):
                if best_neg is None or pricing_res.reduced_cost < best_neg.reduced_cost:
                    best_neg = pricing_res

        if best_neg is None or best_neg.pattern is None:
            stats.exit_reason = f"no_negative_rc_at_iter_{it}"
            _log(
                f"[{label}] no negative-reduced-cost column at iter {it}; stopping"
            )
            break

        # Phase 1: dedupe via column_id.
        new_pat = best_neg.pattern
        existing = {c.column_id for c in columns}
        if new_pat.column_id in existing:
            stats.exit_reason = f"duplicate_column_at_iter_{it}"
            _log(f"[{label}] pricing produced a duplicate column at iter {it}; stopping")
            break
        columns.append(new_pat)
        stats.iterations = it + 1
        _log(
            f"[{label}] iter {it}+ added col size={new_pat.facility_count} "
            f"rc={best_neg.reduced_cost:+.3f} "
            f"region={new_pat.region}"
        )

    # Final RMP solve.
    final_res = solve_rmp(
        columns, instance_ids,
        proxy_windows=proxy_windows,
    )
    stats.final_rmp_objective = final_res.objective
    if final_res.proxy_duals:
        stats.proxy_dual_samples.append(
            [final_res.proxy_duals[w] for w in proxy_windows]
        )
    stats.columns_total = len(columns)
    stats.columns_multi = sum(1 for c in columns if c.facility_count >= 2)
    stats.columns_single = sum(1 for c in columns if c.facility_count == 1)
    if stats.columns_total:
        stats.multi_pct = 100.0 * stats.columns_multi / stats.columns_total
        stats.single_pct = 100.0 * stats.columns_single / stats.columns_total
        total_fac = sum(c.facility_count for c in columns)
        stats.avg_facilities_per_column = total_fac / stats.columns_total
        stats.max_facilities_per_column = max(c.facility_count for c in columns)

    # Direct mini master.
    if columns:
        xs = [c[0] for pat in columns for c in pat.occupied_cells]
        ys = [c[1] for pat in columns for c in pat.occupied_cells]
        bb: RegionBBox = (min(xs), min(ys), max(xs), max(ys))
    else:
        bb = (0, 0, grid_w - 1, grid_h - 1)
    _log(f"[{label}] direct mini master on bbox={bb}")
    dm = solve_direct_mini_master(instances, pools, bb, time_limit_s=20.0)
    stats.direct_master_vars = dm.var_count
    stats.direct_master_objective = dm.integer_objective
    stats.direct_master_wall = dm.wall_seconds

    # Phase 1: integer branching + validation.
    if not skip_branching and columns:
        _log(f"[{label}] branch-and-price (depth≤{branching_max_depth}, nodes≤{branching_max_nodes})")
        bstats = branch_and_price_depth_first(
            columns, instance_ids,
            max_depth=branching_max_depth,
            max_nodes=branching_max_nodes,
            wall_budget_s=branching_wall_budget_s,
            proxy_windows=proxy_windows,
        )
        stats.branching = bstats
        _log(
            f"[{label}] branching: nodes={bstats.nodes_explored} "
            f"leaves={bstats.integer_leaves_found} "
            f"best_obj={bstats.best_objective:.3f} "
            f"depth_max={bstats.max_depth_reached}"
        )
        if bstats.best_lambda is not None:
            report = validate_integer_reconstruction(
                columns, bstats.best_lambda, instance_ids,
                pose_index=dm.pose_index,
                leaf_depth=bstats.max_depth_reached,
            )
            stats.validation = report
            _log(
                f"[{label}] validation: integer_feasible={report.integer_feasible} "
                f"set_partition={report.set_partitioning_pass} "
                f"ghost_rect={report.ghost_rect_pass} "
                f"direct_master={report.direct_master_pass} "
                + (f"err={report.error_message}" if report.error_message else "ok")
            )
        else:
            _log(f"[{label}] no integer leaf found within budget; m10 fails")

    stats.peak_rss_gb = _peak_rss_gb()
    return stats


# === Metrics + verdict ===


def compute_phase1_metrics(stats: CGRunStats, thresholds: Mapping[str, Any]) -> Dict[str, Any]:
    pricing_p95 = _p95(stats.pricing_walls)
    rmp_p95 = _p95(stats.rmp_walls)
    pricing_vars_max = max(stats.pricing_var_counts) if stats.pricing_var_counts else 0
    direct_vars = stats.direct_master_vars or 1
    m7_ratio = float(pricing_vars_max) / float(direct_vars) if direct_vars else 0.0
    m8_match = (
        stats.direct_master_objective != float("inf")
        and stats.final_rmp_objective != float("inf")
        and stats.final_rmp_objective > 0
    )
    if stats.proxy_dual_samples:
        tail = stats.proxy_dual_samples[-5:]
        n_windows = max(1, stats.proxy_window_count or len(tail[0]))
        active_counts = [
            sum(1 for d in snap if abs(d) > PROXY_DUAL_NONZERO_EPS)
            for snap in tail
        ]
        sig_counts = [
            sum(1 for d in snap if abs(d) >= PROXY_DUAL_SIGNIFICANT_EPS)
            for snap in tail
        ]
        m9_active_pct = 100.0 * (sum(active_counts) / len(active_counts)) / n_windows
        m9_sparsity_pct = 100.0 * (sum(sig_counts) / len(sig_counts)) / n_windows
        m9_max_dual = max((abs(d) for snap in tail for d in snap), default=0.0)
    else:
        m9_active_pct = 0.0
        m9_sparsity_pct = 0.0
        m9_max_dual = 0.0

    # Phase 1 additions.
    m10_match = bool(
        stats.validation is not None
        and stats.validation.integer_feasible
        and stats.validation.set_partitioning_pass
        and stats.validation.cell_exclusive_pass
        and stats.validation.ghost_rect_pass
        and stats.validation.direct_master_pass
    )
    m11_nodes = stats.branching.nodes_explored if stats.branching else -1
    m12_avg = stats.avg_facilities_per_column

    metrics: Dict[str, Any] = {
        "m1_generated_columns": stats.columns_total,
        "m2_pricing_p95_seconds": pricing_p95,
        "m3_rmp_lp_p95_seconds": rmp_p95,
        "m4_rss_gb": stats.peak_rss_gb,
        "m5_multi_facility_column_pct": stats.multi_pct,
        "m6_single_facility_column_pct": stats.single_pct,
        "m7_pricing_vars_vs_direct_ratio": m7_ratio,
        "m8_mini_exactness_match": bool(m8_match),
        "m9_proxy_dual_active_pct": m9_active_pct,
        "m9_proxy_dual_sparsity": m9_sparsity_pct,
        "m9_proxy_dual_max": m9_max_dual,
        "m10_integer_reconstruction_match": m10_match,
        "m11_branching_nodes": m11_nodes,
        "m12_avg_facilities_per_column": m12_avg,
        "m12_max_facilities_per_column": stats.max_facilities_per_column,
        "iterations": stats.iterations,
        "final_rmp_objective": stats.final_rmp_objective,
        "direct_master_objective": stats.direct_master_objective,
        "direct_master_vars": stats.direct_master_vars,
        "exit_reason": stats.exit_reason,
    }
    if stats.validation is not None:
        metrics["validation_error"] = stats.validation.error_message
        metrics["validation_direct_master"] = stats.validation.direct_master_telemetry

    failures: List[str] = []
    if metrics["m1_generated_columns"] > thresholds["m1_generated_columns_max"]:
        failures.append("m1_too_many_columns")
    if metrics["m2_pricing_p95_seconds"] > thresholds["m2_pricing_p95_seconds_max"]:
        failures.append("m2_pricing_slow")
    if metrics["m3_rmp_lp_p95_seconds"] > thresholds["m3_rmp_lp_p95_seconds_max"]:
        failures.append("m3_rmp_slow")
    if metrics["m4_rss_gb"] > thresholds["m4_rss_gb_max"]:
        failures.append("m4_rss_over")
    soft_56 = bool(thresholds.get("soft_m5_m6", False))
    if not soft_56 and metrics["m5_multi_facility_column_pct"] < thresholds["m5_multi_facility_column_pct_min"]:
        failures.append("m5_not_enough_multi_facility_columns")
    if not soft_56 and metrics["m6_single_facility_column_pct"] > thresholds["m6_single_facility_column_pct_max"]:
        failures.append("m6_too_many_singleton_columns")
    if metrics["m7_pricing_vars_vs_direct_ratio"] > thresholds["m7_pricing_vars_vs_direct_ratio_max"]:
        failures.append("m7_pricing_not_smaller_than_master")
    if not metrics["m8_mini_exactness_match"]:
        failures.append("m8_sound_check_failed")
    if metrics["m9_proxy_dual_active_pct"] > thresholds["m9_proxy_dual_active_pct_max"]:
        failures.append("m9_proxy_dual_too_active")
    if metrics["m9_proxy_dual_sparsity"] > thresholds["m9_proxy_dual_sparsity_max"]:
        failures.append("m9_proxy_dual_too_dense")
    if thresholds.get("m10_integer_reconstruction_required", False) and not m10_match:
        failures.append("m10_integer_reconstruction_failed")
    if m11_nodes > thresholds["m11_branching_nodes_max"]:
        failures.append("m11_branching_explodes")
    if m12_avg > thresholds["m12_avg_facilities_per_column_max"]:
        failures.append("m12_column_grain_too_large")
    metrics["verdict"] = "GO" if not failures else "NO-GO"
    metrics["verdict_failures"] = failures
    metrics["thresholds"] = {k: v for k, v in thresholds.items() if not callable(v)}
    return metrics


# === Main ===


def run_dry_run() -> int:
    _log("dry-run start")
    pools = load_pose_pools()
    mandatory = load_mandatory()
    _log(f"loaded {len(mandatory)} mandatory instances")
    _log(f"loaded {len(pools)} facility-type pose pools")
    for tpl, poses in pools.items():
        _log(f"  pool {tpl}: {len(poses)} poses")
    rng = random.Random(42)
    for n in (5, 20, 40, 80):
        subset = select_subset(mandatory, n, rng)
        _log(f"subset {n}: {len(subset)} instances, types: " + ", ".join(
            sorted({m['facility_type'] for m in subset})
        ))
    # Toy RMP + Pattern grammar smoke.
    subset5 = select_subset(mandatory, 5, random.Random(42))
    cols = degenerate_singleton_columns(subset5, pools)
    _log(f"singleton columns built: {len(cols)}")
    if cols:
        c0 = cols[0]
        _log(f"  sample col_id={c0.column_id}")
        _log(f"  sample cells={sorted(c0.occupied_cells)[:4]}")
        _log(f"  sample boundary_sig: {len(c0.boundary_signature.perimeter_ports)} ports,"
             f" {len(c0.boundary_signature.perimeter_cells)} perim cells")
    proxy_windows = build_proxy_windows(70, 70, 12)
    rmp = solve_rmp(cols, [m["instance_id"] for m in subset5],
                    proxy_windows=proxy_windows)
    _log(f"toy RMP status={rmp.status_str} obj={rmp.objective:.3f} "
         f"lp_wall={rmp.lp_seconds:.3f}s")
    _log(f"toy m9 proxy: {len(proxy_windows)} windows, "
         f"window_capacity={proxy_window_capacity(proxy_windows[0])}")
    pr = solve_pricing(subset5, pools, (0, 0, 11, 11),
                      rmp.facility_duals, rmp.cell_duals,
                      max_facilities=15, time_limit_s=2.0)
    _log(f"toy pricing status={pr.status_str} vars={pr.var_count} "
         f"wall={pr.wall_seconds:.3f}s rc={pr.reduced_cost:+.3f}")
    # Tiny branching smoke (single iter, low budget).
    if cols:
        bstats = branch_and_price_depth_first(
            cols, [m["instance_id"] for m in subset5],
            max_depth=2, max_nodes=10, wall_budget_s=5.0,
            proxy_windows=proxy_windows,
        )
        _log(f"toy branching: nodes={bstats.nodes_explored} "
             f"leaves={bstats.integer_leaves_found} "
             f"best_obj={bstats.best_objective:.3f}")
    _log("dry-run complete (no measurement written)")
    return 0


def run_measure(args: argparse.Namespace) -> int:
    _log("measurement start")
    pools = load_pose_pools()
    mandatory = load_mandatory()
    rng_base = random.Random(args.seed)

    runs: List[Tuple[str, int, Mapping[str, Any], float, int]] = [
        ("5inst", 5, GO_THRESHOLDS_5, args.pricing_time_limit_5, args.max_iter_5),
        ("20inst", 20, GO_THRESHOLDS_20, args.pricing_time_limit_20, args.max_iter_20),
        ("40inst", 40, GO_THRESHOLDS_40, args.pricing_time_limit_40, args.max_iter_40),
        ("80inst", 80, GO_THRESHOLDS_80, args.pricing_time_limit_80, args.max_iter_80),
    ]
    all_metrics: Dict[str, Any] = {}
    overall_failures: List[str] = []
    for (label, n, thresholds, pricing_time_limit, max_iter) in runs:
        _log(f"--- {label} ({n} instances) ---")
        # Use a fresh deterministic rng per ramp so subset selection is stable.
        rng = random.Random(args.seed + n)
        subset = select_subset(mandatory, n, rng)
        stats = run_column_generation_phase1(
            subset, pools, label=label,
            region_size=args.region_size, stride=args.stride,
            max_iterations=max_iter,
            pricing_time_limit=pricing_time_limit,
            rng_seed=args.seed + n,
            branching_max_depth=args.branching_max_depth,
            branching_max_nodes=args.branching_max_nodes,
            branching_wall_budget_s=args.branching_wall_budget_s,
            skip_branching=(n <= 5 and not args.branch_5),
        )
        metrics = compute_phase1_metrics(stats, thresholds)
        all_metrics[label] = metrics
        if metrics["verdict"] != "GO":
            overall_failures.append(f"{label}:{','.join(metrics['verdict_failures'])}")

    summary: Dict[str, Any] = {
        "paradigm": "column_generation_branch_and_price",
        "phase": "phase1_integer_reconstruction",
        "date": time.strftime("%Y-%m-%d"),
        "verdict": "GO" if not overall_failures else "NO-GO",
        "verdict_failures": overall_failures,
        "ramps": all_metrics,
        "args": vars(args),
        "peak_rss_gb_overall": _peak_rss_gb(),
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2, default=str))
    _log(f"wrote results to {RESULTS_PATH}")
    _log(f"VERDICT: {summary['verdict']}")
    if overall_failures:
        for f in overall_failures:
            _log(f"  FAIL {f}")
    return 0 if not overall_failures else 2


def main() -> int:
    p = argparse.ArgumentParser(description="cand C Phase 1 — integer reconstruction probe")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--measure", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--region-size", type=int, default=12)
    p.add_argument("--stride", type=int, default=6)
    p.add_argument("--max-iter-5", type=int, default=60)
    p.add_argument("--max-iter-20", type=int, default=120)
    p.add_argument("--max-iter-40", type=int, default=180)
    p.add_argument("--max-iter-80", type=int, default=240)
    p.add_argument("--pricing-time-limit-5", type=float, default=5.0)
    p.add_argument("--pricing-time-limit-20", type=float, default=10.0)
    p.add_argument("--pricing-time-limit-40", type=float, default=15.0)
    p.add_argument("--pricing-time-limit-80", type=float, default=20.0)
    p.add_argument("--branching-max-depth", type=int, default=5)
    p.add_argument("--branching-max-nodes", type=int, default=1000)
    p.add_argument("--branching-wall-budget-s", type=float, default=60.0)
    p.add_argument("--branch-5", action="store_true",
                   help="run branching on 5-inst (default skipped, trivial)")
    args = p.parse_args()

    t0 = time.perf_counter()
    try:
        if args.dry_run:
            rc = run_dry_run()
        elif args.measure:
            rc = run_measure(args)
        else:
            _log("error: pass either --dry-run or --measure")
            rc = 64
    except Exception as exc:
        STATUS_PATH.write_text(json.dumps({
            "status": "crashed", "error": repr(exc),
            "elapsed_s": time.perf_counter() - t0,
        }, indent=2))
        _log(f"CRASH: {exc!r}")
        raise
    STATUS_PATH.write_text(json.dumps({
        "status": "ok", "rc": rc,
        "mode": "dry-run" if args.dry_run else "measure",
        "elapsed_s": time.perf_counter() - t0,
        "peak_rss_gb": _peak_rss_gb(),
    }, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())

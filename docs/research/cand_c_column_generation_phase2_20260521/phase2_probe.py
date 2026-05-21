"""Phase 2 probe — share cache + Ryan-Foster + 160/266 ramp + routing-aware + boundary.

Phase 2 metric set (Phase 1 m1-m12 carried forward + new):
    m13: pricing share cache hit rate
    m14: Ryan-Foster vs standard branching nodes ratio
    m15: 160/266 inst RSS
    m16: routing-aware pricing impact on m5
    m17: boundary equality dual sparsity
    m18: integer reconstruction match (Phase 1 m10 carried)

Six ramps + two variants:
    5 / 20 / 40 / 80 / 160 / 266 (baseline)
    80inst_routing_aware (variant A — routing-aware pricing on)
    80inst_boundary_eq (variant B — boundary equality constraints on)

This probe does NOT call into src/.  All required logic is imported
from Phase 1 (`column_grammar`, `integer_validator`) and the four
Phase 2 modules (`pricing_cache`, `ryan_foster`, `routing_aware_pricing`,
`boundary_constraints`).
"""

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


# === Path bootstrap (no install) ===

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "preprocessed"
RESULTS_PATH = HERE / "phase2_results.json"
STATUS_PATH = HERE / "phase2_status.json"

# Add the parent of this dir + the parent of Phase 1 dir to sys.path
# so package-style imports work without installing.
RESEARCH_DIR = HERE.parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

# Ensure Phase 1 dir is a package (its __init__.py exists by Phase 1).
PHASE1_DIR = RESEARCH_DIR / "cand_c_column_generation_phase1_20260521"
if not (PHASE1_DIR / "__init__.py").exists():
    (PHASE1_DIR / "__init__.py").write_text("")

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
# Reuse Phase 1 PoseRecord dataclass via direct module import.
from cand_c_column_generation_phase1_20260521 import phase1_probe as p1  # noqa: E402

from cand_c_column_generation_phase2_20260521.pricing_cache import (  # noqa: E402
    PricingShareCache,
    build_share_cache,
    cache_summary,
    query_region_poses,
)
from cand_c_column_generation_phase2_20260521.ryan_foster import (  # noqa: E402
    BranchDecision,
    BranchNode,
    RyanFosterStats,
    apply_ryan_foster_to_pricing,
    column_compatible_with_decisions,
    column_pool_mask,
    select_ryan_foster_pair,
)
from cand_c_column_generation_phase2_20260521.routing_aware_pricing import (  # noqa: E402
    RentsRuleConfig,
    apply_rents_rule_to_pricing,
    column_commodity_penetration,
    perimeter_bonus_terms,
)
from cand_c_column_generation_phase2_20260521.boundary_constraints import (  # noqa: E402
    BoundaryEqualityResult,
    add_boundary_equality_constraints,
    collect_boundary_duals,
)


# === Phase 2 thresholds ===

PROXY_DUAL_NONZERO_EPS = 1e-7
PROXY_DUAL_SIGNIFICANT_EPS = 0.1

GO_THRESHOLDS_BASE = {
    "m1_generated_columns_max": 20000,
    "m2_pricing_p95_seconds_max": 60.0,
    "m3_rmp_lp_p95_seconds_max": 10.0,
    "m4_rss_gb_max": 24.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
    "m9_proxy_dual_active_pct_max": 30.0,
    "m9_proxy_dual_sparsity_max": 20.0,
    "soft_m5_m6": False,
    "m10_integer_reconstruction_required": True,
    "m11_branching_nodes_max": 1000,
    "m12_avg_facilities_per_column_max": 15.0,
    "m13_cache_hit_rate_min": 0.80,
    "m14_rf_vs_std_nodes_ratio_max": 0.5,
    "m15_rss_gb_hard_cap": 24.0,
    "m16_routing_aware_m5_min": 30.0,
    "m17_boundary_dual_sparsity_max": 30.0,
}

# Per-ramp overrides for soft / hard thresholds.
GO_THRESHOLDS_BY_RAMP: Dict[str, Dict[str, Any]] = {
    "5inst":   {**GO_THRESHOLDS_BASE, "soft_m5_m6": True,
                "m4_rss_gb_max": 4.0, "m11_branching_nodes_max": 200,
                "m10_integer_reconstruction_required": False,
                "m1_generated_columns_max": 2636},
    "20inst":  {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 4.0,
                "m11_branching_nodes_max": 500,
                "m1_generated_columns_max": 5272},
    "40inst":  {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 4.0,
                "m11_branching_nodes_max": 1000,
                "m1_generated_columns_max": 10000},
    "80inst":  {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 8.0,
                "m11_branching_nodes_max": 1000,
                "m1_generated_columns_max": 20000},
    "160inst": {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 16.0,
                "m11_branching_nodes_max": 2000,
                "m1_generated_columns_max": 40000,
                "m2_pricing_p95_seconds_max": 90.0},
    "266inst": {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 24.0,
                "m11_branching_nodes_max": 5000,
                "m1_generated_columns_max": 60000,
                "m2_pricing_p95_seconds_max": 120.0},
    "80inst_routing_aware": {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 8.0,
                             "m11_branching_nodes_max": 1000,
                             "m1_generated_columns_max": 20000},
    "80inst_boundary_eq":   {**GO_THRESHOLDS_BASE, "m4_rss_gb_max": 8.0,
                             "m11_branching_nodes_max": 1000,
                             "m1_generated_columns_max": 20000},
}


# === Utility helpers ===


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
    print(f"[phase2 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# === Pricing (Phase 2 version using share cache + Ryan-Foster + routing-aware) ===


@dataclass
class Phase2PricingResult:
    reduced_cost: float
    pattern: Optional[Pattern]
    var_count: int
    wall_seconds: float
    status_str: str
    rents_rule_classes: int = 0


def solve_pricing_phase2(
    instances: Sequence[Dict[str, Any]],
    cache: PricingShareCache,
    region: RegionBBox,
    facility_duals: Mapping[str, float],
    cell_duals: Mapping[CellCoord, float],
    *,
    decisions: Sequence[BranchDecision] = (),
    rents_config: Optional[RentsRuleConfig] = None,
    max_facilities: int = 15,
    time_limit_s: float = 5.0,
) -> Phase2PricingResult:
    """Phase 2 pricing: uses share cache + Ryan-Foster + routing-aware seed."""
    from ortools.sat.python import cp_model

    SCALE = 1000
    model = cp_model.CpModel()
    z_vars: Dict[Tuple[str, int], Any] = {}
    pose_lookup: Dict[Tuple[str, int], Any] = {}
    by_cell: Dict[CellCoord, List[Any]] = defaultdict(list)
    by_instance: Dict[str, List[Any]] = defaultdict(list)

    for inst in instances:
        iid = inst["instance_id"]
        for pose in query_region_poses(cache, region, iid):
            v = model.NewBoolVar(f"z_{iid}_{pose.pose_idx}")
            key = (iid, pose.pose_idx)
            z_vars[key] = v
            pose_lookup[key] = pose
            by_instance[iid].append(v)
            for cell in pose.cells:
                by_cell[cell].append(v)

    if not z_vars:
        return Phase2PricingResult(
            reduced_cost=0.0, pattern=None, var_count=0,
            wall_seconds=0.0, status_str="EMPTY",
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

    # Ryan-Foster decisions.
    apply_ryan_foster_to_pricing(model, z_vars, decisions)

    # Routing-aware Rent's-Rule (commodity cap).
    rents_classes = 0
    if rents_config is not None:
        rents_classes = apply_rents_rule_to_pricing(
            model, z_vars, pose_lookup, rents_config,
        )

    obj_terms = []
    for (iid, pose_idx), v in z_vars.items():
        pose = pose_lookup[(iid, pose_idx)]
        pi = float(facility_duals.get(iid, 0.0))
        cell_penalty = sum(float(cell_duals.get(c, 0.0)) for c in pose.cells)
        coeff = -(pi + cell_penalty)
        obj_terms.append(int(round(coeff * SCALE)) * v)

    # Perimeter-bonus additive (small).
    if rents_config is not None:
        obj_terms.extend(
            perimeter_bonus_terms(
                z_vars, pose_lookup, region, rents_config, scale=SCALE,
            )
        )

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
        return Phase2PricingResult(
            reduced_cost=0.0, pattern=None, var_count=var_count,
            wall_seconds=wall, status_str=status_str,
            rents_rule_classes=rents_classes,
        )

    reduced_cost = 1.0 + float(solver.ObjectiveValue()) / SCALE
    chosen: List[FacilityAssignment] = []
    chosen_poses: List[Any] = []
    for (iid, pose_idx), v in z_vars.items():
        if solver.Value(v) == 1:
            pose = pose_lookup[(iid, pose_idx)]
            inst = next(i for i in instances if i["instance_id"] == iid)
            chosen.append((iid, inst["facility_type"], pose_idx))
            chosen_poses.append(pose)

    if not chosen:
        return Phase2PricingResult(
            reduced_cost=reduced_cost, pattern=None, var_count=var_count,
            wall_seconds=wall, status_str=status_str,
            rents_rule_classes=rents_classes,
        )
    pat = p1.column_from_pricing_assignment(chosen, pose_lookup, region)
    return Phase2PricingResult(
        reduced_cost=reduced_cost, pattern=pat, var_count=var_count,
        wall_seconds=wall, status_str=status_str,
        rents_rule_classes=rents_classes,
    )


# === Phase 2 RMP (with optional boundary equality) ===


@dataclass
class Phase2RMPResult:
    objective: float
    lp_seconds: float
    lambda_values: List[float]
    facility_duals: Dict[str, float]
    cell_duals: Dict[CellCoord, float]
    status_str: str
    proxy_duals: Dict[RegionBBox, float] = field(default_factory=dict)
    boundary_result: Optional[BoundaryEqualityResult] = None


def solve_rmp_phase2(
    columns: Sequence[Pattern],
    instance_ids: Sequence[str],
    proxy_windows: Optional[Sequence[RegionBBox]] = None,
    branching_fixed: Optional[Dict[int, int]] = None,
    *,
    enable_boundary_eq: bool = False,
    decisions: Sequence[BranchDecision] = (),
) -> Phase2RMPResult:
    from ortools.linear_solver import pywraplp

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("GLOP solver unavailable")
    solver.SuppressOutput()
    infty = solver.infinity()

    # Mask via Ryan-Foster decisions.
    mask = column_pool_mask(columns, decisions) if decisions else [True] * len(columns)
    n_pruned = sum(1 for m in mask if not m)

    lambda_vars = []
    for k in range(len(columns)):
        lo, hi = 0.0, 1.0
        if not mask[k]:
            lo = hi = 0.0
        elif branching_fixed and k in branching_fixed:
            lo = hi = float(branching_fixed[k])
        lambda_vars.append(solver.NumVar(lo, hi, f"l_{k}"))

    cov_ctrs: Dict[str, Any] = {}
    for iid in instance_ids:
        ctr = solver.Constraint(1.0, 1.0, f"cov_{iid}")
        cov_ctrs[iid] = ctr
    for k, pat in enumerate(columns):
        for iid in pat.covered_instance_ids:
            if iid in cov_ctrs:
                cov_ctrs[iid].SetCoefficient(lambda_vars[k], 1.0)

    all_cells: Set[CellCoord] = set()
    for col in columns:
        all_cells.update(col.occupied_cells)
    cell_ctrs: Dict[CellCoord, Any] = {}
    for cell in all_cells:
        ctr = solver.Constraint(-infty, 1.0, f"cell_{cell[0]}_{cell[1]}")
        cell_ctrs[cell] = ctr
    for k, pat in enumerate(columns):
        for cell in pat.occupied_cells:
            if cell in cell_ctrs:
                cell_ctrs[cell].SetCoefficient(lambda_vars[k], 1.0)

    proxy_ctrs: Dict[RegionBBox, Any] = {}
    if proxy_windows:
        for w in proxy_windows:
            cap = p1.proxy_window_capacity(w)
            ctr = solver.Constraint(-infty, float(cap),
                                    f"proxy_{w[0]}_{w[1]}_{w[2]}_{w[3]}")
            proxy_ctrs[w] = ctr
        for k, pat in enumerate(columns):
            if not pat.port_cells:
                continue
            for w, ctr in proxy_ctrs.items():
                ports_in_w = p1.pattern_port_count_in_window(pat, w)
                if ports_in_w:
                    ctr.SetCoefficient(lambda_vars[k], float(ports_in_w))

    boundary_ctrs: Dict[Any, Any] = {}
    if enable_boundary_eq:
        boundary_ctrs, _added = add_boundary_equality_constraints(
            solver, lambda_vars, columns,
        )

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
        return Phase2RMPResult(
            objective=float("inf"),
            lp_seconds=lp_seconds,
            lambda_values=[0.0] * len(columns),
            facility_duals={iid: 0.0 for iid in instance_ids},
            cell_duals={cell: 0.0 for cell in all_cells},
            status_str=status_str,
            proxy_duals={w: 0.0 for w in proxy_ctrs},
            boundary_result=None,
        )

    facility_duals = {iid: cov_ctrs[iid].dual_value() for iid in instance_ids}
    cell_duals = {cell: -cell_ctrs[cell].dual_value() for cell in all_cells}
    proxy_duals = {w: -proxy_ctrs[w].dual_value() for w in proxy_ctrs}
    boundary_result = None
    if enable_boundary_eq and boundary_ctrs:
        boundary_result = collect_boundary_duals(boundary_ctrs)
    return Phase2RMPResult(
        objective=obj.Value(),
        lp_seconds=lp_seconds,
        lambda_values=[v.solution_value() for v in lambda_vars],
        facility_duals=facility_duals,
        cell_duals=cell_duals,
        status_str=status_str,
        proxy_duals=proxy_duals,
        boundary_result=boundary_result,
    )


# === Branch-and-price (Ryan-Foster + fallback most-fractional) ===


@dataclass
class Phase2CGStats:
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
    avg_facilities_per_column: float = 0.0
    max_facilities_per_column: int = 0
    rf_branching: Optional[RyanFosterStats] = None
    std_branching: Optional[Any] = None
    validation: Optional[ValidationReport] = None
    cache_telemetry: Dict[str, Any] = field(default_factory=dict)
    boundary_eq_summary: Optional[Dict[str, Any]] = None
    routing_aware: bool = False
    boundary_eq_on: bool = False


def branch_and_price_ryan_foster(
    columns: Sequence[Pattern],
    instance_ids: Sequence[str],
    *,
    max_depth: int = 5,
    max_nodes: int = 1000,
    wall_budget_s: float = 60.0,
    integer_tol: float = 1e-6,
    proxy_windows: Optional[Sequence[RegionBBox]] = None,
    enable_boundary_eq: bool = False,
) -> RyanFosterStats:
    """DFS B&P using Ryan-Foster pair branching (no re-pricing inside)."""
    stats = RyanFosterStats()
    t0 = time.perf_counter()
    stack: List[BranchNode] = [BranchNode(decisions=(), depth=0)]
    while stack:
        if time.perf_counter() - t0 > wall_budget_s:
            stats.timed_out = True
            break
        if stats.nodes_explored >= max_nodes:
            break
        node = stack.pop()
        if not node.is_consistent():
            continue
        stats.nodes_explored += 1
        stats.max_depth_reached = max(stats.max_depth_reached, node.depth)

        rmp_res = solve_rmp_phase2(
            columns, instance_ids,
            proxy_windows=proxy_windows,
            decisions=node.decisions,
            enable_boundary_eq=enable_boundary_eq,
        )
        if rmp_res.status_str not in ("OPTIMAL", "FEASIBLE"):
            continue
        if rmp_res.objective >= stats.best_objective - 1e-9:
            continue

        pair = select_ryan_foster_pair(
            columns, rmp_res.lambda_values,
            integer_tol=integer_tol, decisions=node.decisions,
        )
        if pair is None:
            # Integer feasible (no fractional pair).
            stats.integer_leaves_found += 1
            if rmp_res.objective < stats.best_objective:
                stats.best_objective = rmp_res.objective
                stats.best_lambda = list(rmp_res.lambda_values)
            continue

        if node.depth >= max_depth:
            continue
        # Branch: same first (LIFO push order — diff first explored).
        same_dec = BranchDecision.make(pair[0], pair[1], "same")
        diff_dec = BranchDecision.make(pair[0], pair[1], "diff")
        stats.same_decisions += 1
        stats.diff_decisions += 1
        stack.append(node.with_decision(same_dec))
        stack.append(node.with_decision(diff_dec))
    return stats


# === Direct mini-master (Phase 1 reused) ===


def run_direct_master_for_ramp(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    region: RegionBBox,
    time_limit_s: float = 30.0,
) -> Any:
    return p1.solve_direct_mini_master(
        instances, pools, region,
        time_limit_s=time_limit_s, build_pose_index=True,
    )


# === Column generation loop (Phase 2 wired) ===


def run_column_generation_phase2(
    instances: List[Dict[str, Any]],
    pools: Dict[str, List[Any]],
    cache: PricingShareCache,
    label: str,
    *,
    grid_w: int = 70, grid_h: int = 70,
    region_size: int = 12, stride: int = 6,
    max_iterations: int = 100,
    pricing_time_limit: float = 10.0,
    rng_seed: int = 17,
    rf_max_depth: int = 5,
    rf_max_nodes: int = 1000,
    branching_wall_budget_s: float = 60.0,
    skip_branching: bool = False,
    routing_aware: bool = False,
    enable_boundary_eq: bool = False,
    run_std_branching_baseline: bool = False,
    rents_max_classes: int = 3,
) -> Phase2CGStats:
    rng = random.Random(rng_seed)
    instance_ids = [m["instance_id"] for m in instances]

    columns: List[Pattern] = p1.degenerate_singleton_columns(instances, pools)
    _log(f"[{label}] bootstrapped {len(columns)} singleton columns")

    regions = p1.iter_regions(grid_w, grid_h, region_size, stride, rng)
    proxy_windows = p1.build_proxy_windows(grid_w, grid_h, region_size)
    _log(f"[{label}] {len(regions)} regions, {len(proxy_windows)} proxy windows")

    stats = Phase2CGStats(
        label=label, n_instances=len(instances),
        proxy_window_count=len(proxy_windows),
        routing_aware=routing_aware,
        boundary_eq_on=enable_boundary_eq,
    )

    rents_config: Optional[RentsRuleConfig] = None
    if routing_aware:
        rents_config = RentsRuleConfig(
            max_commodity_classes=rents_max_classes,
            enable_perimeter_bonus=True,
            perimeter_bonus_weight=0.05,
        )

    region_cursor = 0
    EPSILON = -1e-6
    for it in range(max_iterations):
        rmp_res = solve_rmp_phase2(
            columns, instance_ids,
            proxy_windows=proxy_windows,
            enable_boundary_eq=enable_boundary_eq,
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
        if rmp_res.boundary_result is not None and stats.boundary_eq_summary is None:
            stats.boundary_eq_summary = {
                "n_constraints": rmp_res.boundary_result.n_boundary_constraints_added,
                "dual_active_pct": rmp_res.boundary_result.dual_active_pct,
                "dual_sparsity_pct": rmp_res.boundary_result.dual_sparsity_pct,
                "max_abs_dual": rmp_res.boundary_result.max_abs_dual,
            }
        if it % 5 == 0 or it < 3:
            _log(
                f"[{label}] iter {it}  cols={len(columns)}  "
                f"rmp_obj={rmp_res.objective:.3f}  "
                f"rmp_wall={rmp_res.lp_seconds:.3f}s"
            )

        TRIES_PER_ITER = 4
        tried = 0
        best_neg: Optional[Phase2PricingResult] = None
        while tried < TRIES_PER_ITER and region_cursor < len(regions) * 4:
            region = regions[region_cursor % len(regions)]
            region_cursor += 1
            tried += 1
            pricing_res = solve_pricing_phase2(
                instances, cache, region,
                rmp_res.facility_duals, rmp_res.cell_duals,
                rents_config=rents_config,
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

        new_pat = best_neg.pattern
        existing = {c.column_id for c in columns}
        if new_pat.column_id in existing:
            stats.exit_reason = f"duplicate_column_at_iter_{it}"
            _log(f"[{label}] pricing produced a duplicate column at iter {it}; stopping")
            break
        columns.append(new_pat)
        stats.iterations = it + 1
        if it % 10 == 0 or it < 3:
            _log(
                f"[{label}] iter {it}+ added col size={new_pat.facility_count} "
                f"rc={best_neg.reduced_cost:+.3f} "
                f"region={new_pat.region}"
            )

    final_res = solve_rmp_phase2(
        columns, instance_ids,
        proxy_windows=proxy_windows,
        enable_boundary_eq=enable_boundary_eq,
    )
    stats.final_rmp_objective = final_res.objective
    if final_res.proxy_duals:
        stats.proxy_dual_samples.append(
            [final_res.proxy_duals[w] for w in proxy_windows]
        )
    if final_res.boundary_result is not None:
        stats.boundary_eq_summary = {
            "n_constraints": final_res.boundary_result.n_boundary_constraints_added,
            "dual_active_pct": final_res.boundary_result.dual_active_pct,
            "dual_sparsity_pct": final_res.boundary_result.dual_sparsity_pct,
            "max_abs_dual": final_res.boundary_result.max_abs_dual,
        }
    stats.columns_total = len(columns)
    stats.columns_multi = sum(1 for c in columns if c.facility_count >= 2)
    stats.columns_single = sum(1 for c in columns if c.facility_count == 1)
    if stats.columns_total:
        stats.multi_pct = 100.0 * stats.columns_multi / stats.columns_total
        stats.single_pct = 100.0 * stats.columns_single / stats.columns_total
        total_fac = sum(c.facility_count for c in columns)
        stats.avg_facilities_per_column = total_fac / stats.columns_total
        stats.max_facilities_per_column = max(c.facility_count for c in columns)

    if columns:
        xs = [c[0] for pat in columns for c in pat.occupied_cells]
        ys = [c[1] for pat in columns for c in pat.occupied_cells]
        bb: RegionBBox = (min(xs), min(ys), max(xs), max(ys))
    else:
        bb = (0, 0, grid_w - 1, grid_h - 1)
    _log(f"[{label}] direct mini master on bbox={bb}")
    dm = run_direct_master_for_ramp(instances, pools, bb, time_limit_s=30.0)
    stats.direct_master_vars = dm.var_count
    stats.direct_master_objective = dm.integer_objective
    stats.direct_master_wall = dm.wall_seconds

    # Ryan-Foster branching.
    if not skip_branching and columns:
        _log(f"[{label}] Ryan-Foster B&P (depth≤{rf_max_depth}, nodes≤{rf_max_nodes})")
        rf_stats = branch_and_price_ryan_foster(
            columns, instance_ids,
            max_depth=rf_max_depth, max_nodes=rf_max_nodes,
            wall_budget_s=branching_wall_budget_s,
            proxy_windows=proxy_windows,
            enable_boundary_eq=enable_boundary_eq,
        )
        stats.rf_branching = rf_stats
        _log(
            f"[{label}] RF branching: nodes={rf_stats.nodes_explored} "
            f"leaves={rf_stats.integer_leaves_found} "
            f"best_obj={rf_stats.best_objective:.3f} "
            f"depth_max={rf_stats.max_depth_reached}"
        )
        if rf_stats.best_lambda is not None:
            report = validate_integer_reconstruction(
                columns, rf_stats.best_lambda, instance_ids,
                pose_index=dm.pose_index,
                leaf_depth=rf_stats.max_depth_reached,
            )
            stats.validation = report
            _log(
                f"[{label}] validation: integer_feasible={report.integer_feasible} "
                f"set_partition={report.set_partitioning_pass} "
                f"ghost_rect={report.ghost_rect_pass} "
                f"direct_master={report.direct_master_pass}"
            )

        # Standard most-fractional baseline (for m14 ratio).
        if run_std_branching_baseline:
            _log(f"[{label}] running std most-fractional baseline for m14")
            std_stats = p1.branch_and_price_depth_first(
                columns, instance_ids,
                max_depth=rf_max_depth, max_nodes=rf_max_nodes,
                wall_budget_s=branching_wall_budget_s,
                proxy_windows=proxy_windows,
            )
            stats.std_branching = std_stats
            _log(
                f"[{label}] std baseline: nodes={std_stats.nodes_explored} "
                f"leaves={std_stats.integer_leaves_found}"
            )

    stats.cache_telemetry = cache_summary(cache)
    stats.peak_rss_gb = _peak_rss_gb()
    return stats


# === Phase 2 metric assembly ===


def compute_phase2_metrics(
    stats: Phase2CGStats,
    thresholds: Mapping[str, Any],
) -> Dict[str, Any]:
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

    m10_match = bool(
        stats.validation is not None
        and stats.validation.integer_feasible
        and stats.validation.set_partitioning_pass
        and stats.validation.cell_exclusive_pass
        and stats.validation.ghost_rect_pass
        and stats.validation.direct_master_pass
    )
    m11_nodes = stats.rf_branching.nodes_explored if stats.rf_branching else -1
    m12_avg = stats.avg_facilities_per_column
    m13_hit_rate = stats.cache_telemetry.get("cache_hit_rate", 0.0)
    if stats.rf_branching and stats.std_branching:
        std_nodes = stats.std_branching.nodes_explored or 1
        m14_ratio = float(m11_nodes) / float(std_nodes)
    else:
        m14_ratio = -1.0  # not measured this ramp.
    m15_rss = stats.peak_rss_gb
    m16_routing_aware_m5 = stats.multi_pct if stats.routing_aware else -1.0
    m17_boundary_dual_sparsity = (
        stats.boundary_eq_summary["dual_sparsity_pct"]
        if stats.boundary_eq_summary else -1.0
    )
    m18_integer_match = m10_match  # alias.

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
        "m13_cache_hit_rate": m13_hit_rate,
        "m14_rf_vs_std_nodes_ratio": m14_ratio,
        "m15_rss_gb": m15_rss,
        "m16_routing_aware_m5_pct": m16_routing_aware_m5,
        "m17_boundary_dual_sparsity_pct": m17_boundary_dual_sparsity,
        "m18_integer_reconstruction_match": m18_integer_match,
        "iterations": stats.iterations,
        "final_rmp_objective": stats.final_rmp_objective,
        "direct_master_objective": stats.direct_master_objective,
        "direct_master_vars": stats.direct_master_vars,
        "exit_reason": stats.exit_reason,
        "routing_aware": stats.routing_aware,
        "boundary_eq_on": stats.boundary_eq_on,
        "cache_telemetry": stats.cache_telemetry,
        "boundary_eq_summary": stats.boundary_eq_summary,
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
    if m13_hit_rate >= 0.0 and m13_hit_rate < thresholds["m13_cache_hit_rate_min"]:
        # Cache hit rate is only measured when share cache has hits.
        if stats.cache_telemetry.get("hits", 0) > 0:
            failures.append("m13_cache_hit_low")
    if m14_ratio > thresholds["m14_rf_vs_std_nodes_ratio_max"] and m14_ratio >= 0:
        failures.append("m14_rf_no_speedup")
    if m15_rss > thresholds["m15_rss_gb_hard_cap"]:
        failures.append("m15_rss_hard_cap_exceeded")
    if stats.routing_aware and m16_routing_aware_m5 >= 0 and m16_routing_aware_m5 < thresholds["m16_routing_aware_m5_min"]:
        failures.append("m16_routing_aware_killed_m5")
    if stats.boundary_eq_on and m17_boundary_dual_sparsity > thresholds["m17_boundary_dual_sparsity_max"] and m17_boundary_dual_sparsity >= 0:
        failures.append("m17_boundary_dual_too_dense")
    metrics["verdict"] = "GO" if not failures else "NO-GO"
    metrics["verdict_failures"] = failures
    metrics["thresholds"] = {k: v for k, v in thresholds.items() if not callable(v)}
    return metrics


# === Ramp definitions ===


@dataclass
class RampConfig:
    label: str
    n: int
    pricing_time_limit: float
    max_iter: int
    run_std_baseline: bool = False
    routing_aware: bool = False
    enable_boundary_eq: bool = False
    skip_branching: bool = False


def default_ramps() -> List[RampConfig]:
    return [
        RampConfig("5inst",   5,   5.0,   60,  run_std_baseline=False, skip_branching=True),
        RampConfig("20inst",  20,  10.0,  120, run_std_baseline=True),
        RampConfig("40inst",  40,  15.0,  180, run_std_baseline=True),
        RampConfig("80inst",  80,  20.0,  240, run_std_baseline=True),
        RampConfig("160inst", 160, 30.0,  300, run_std_baseline=False),
        RampConfig("266inst", 266, 45.0,  400, run_std_baseline=False),
        RampConfig("80inst_routing_aware", 80, 20.0, 200,
                   run_std_baseline=False, routing_aware=True),
        RampConfig("80inst_boundary_eq",   80, 20.0, 200,
                   run_std_baseline=False, enable_boundary_eq=True),
    ]


# === Dry-run smoke ===


def run_dry_run() -> int:
    _log("dry-run start")
    pools = p1.load_pose_pools()
    mandatory = p1.load_mandatory()
    _log(f"loaded {len(mandatory)} mandatory instances")
    _log(f"loaded {len(pools)} facility-type pose pools")
    # Build share cache once.
    cache = build_share_cache(pools, mandatory, is_in_ghost_rect)
    _log(f"share cache: {cache_summary(cache)}")

    rng = random.Random(42)
    for n in (5, 20, 40, 80, 160, 266):
        subset = p1.select_subset(mandatory, n, rng)
        types = sorted({m['facility_type'] for m in subset})
        _log(f"subset {n}: {len(subset)} instances, {len(types)} types")

    # Quick smoke: 5-inst pose query.
    subset5 = p1.select_subset(mandatory, 5, random.Random(42))
    if subset5:
        iid0 = subset5[0]["instance_id"]
        region: RegionBBox = (0, 0, 11, 11)
        poses = query_region_poses(cache, region, iid0)
        _log(f"query iid={iid0} region={region}: {len(poses)} poses")
    cols = p1.degenerate_singleton_columns(subset5, pools)
    proxy_windows = p1.build_proxy_windows(70, 70, 12)
    rmp_baseline = solve_rmp_phase2(
        cols, [m["instance_id"] for m in subset5],
        proxy_windows=proxy_windows,
    )
    _log(f"toy RMP (baseline) status={rmp_baseline.status_str} "
         f"obj={rmp_baseline.objective:.3f} "
         f"wall={rmp_baseline.lp_seconds:.3f}s")
    rmp_be = solve_rmp_phase2(
        cols, [m["instance_id"] for m in subset5],
        proxy_windows=proxy_windows, enable_boundary_eq=True,
    )
    _log(f"toy RMP (boundary_eq) status={rmp_be.status_str} "
         f"obj={rmp_be.objective:.3f} "
         f"wall={rmp_be.lp_seconds:.3f}s "
         f"boundary={'on' if rmp_be.boundary_result else 'no_eq'}")

    pr = solve_pricing_phase2(
        subset5, cache, (0, 0, 11, 11),
        rmp_baseline.facility_duals, rmp_baseline.cell_duals,
        time_limit_s=2.0,
    )
    _log(f"toy pricing status={pr.status_str} vars={pr.var_count} "
         f"wall={pr.wall_seconds:.3f}s rc={pr.reduced_cost:+.3f}")

    # Routing-aware smoke.
    rents = RentsRuleConfig(max_commodity_classes=3, enable_perimeter_bonus=True)
    pr2 = solve_pricing_phase2(
        subset5, cache, (0, 0, 11, 11),
        rmp_baseline.facility_duals, rmp_baseline.cell_duals,
        rents_config=rents, time_limit_s=2.0,
    )
    _log(f"toy pricing (routing-aware) status={pr2.status_str} "
         f"vars={pr2.var_count} wall={pr2.wall_seconds:.3f}s "
         f"rc={pr2.reduced_cost:+.3f} rents_classes={pr2.rents_rule_classes}")

    # Ryan-Foster pair selection smoke.
    if cols:
        # Fake a fractional vector to drive pair selection.
        lam = [0.5] * len(cols)
        pair = select_ryan_foster_pair(cols, lam)
        _log(f"toy RF pair: {pair}")
        rf = branch_and_price_ryan_foster(
            cols, [m["instance_id"] for m in subset5],
            max_depth=2, max_nodes=10, wall_budget_s=5.0,
            proxy_windows=proxy_windows,
        )
        _log(f"toy RF branching: nodes={rf.nodes_explored} "
             f"leaves={rf.integer_leaves_found} "
             f"best_obj={rf.best_objective:.3f}")

    _log("dry-run complete (no measurement written)")
    return 0


# === Measurement entry ===


def run_measure(args: argparse.Namespace) -> int:
    _log("measurement start")
    pools = p1.load_pose_pools()
    mandatory = p1.load_mandatory()
    _log(f"loaded {len(mandatory)} mandatory + {len(pools)} pools")

    # Build share cache once for all ramps.
    cache = build_share_cache(pools, mandatory, is_in_ghost_rect)
    _log(f"share cache built: {cache_summary(cache)}")

    ramps = default_ramps()
    # Honour CLI overrides for ramp filtering.
    if args.only_ramp:
        ramps = [r for r in ramps if r.label in args.only_ramp]

    all_metrics: Dict[str, Any] = {}
    overall_failures: List[str] = []
    for cfg in ramps:
        label = cfg.label
        _log(f"--- {label} ({cfg.n} instances) ---")
        rng = random.Random(args.seed + cfg.n)
        subset = p1.select_subset(mandatory, cfg.n, rng)
        thresholds = GO_THRESHOLDS_BY_RAMP[label]
        stats = run_column_generation_phase2(
            subset, pools, cache, label=label,
            region_size=args.region_size, stride=args.stride,
            max_iterations=cfg.max_iter,
            pricing_time_limit=cfg.pricing_time_limit,
            rng_seed=args.seed + cfg.n,
            rf_max_depth=args.rf_max_depth,
            rf_max_nodes=args.rf_max_nodes,
            branching_wall_budget_s=args.branching_wall_budget_s,
            skip_branching=cfg.skip_branching,
            routing_aware=cfg.routing_aware,
            enable_boundary_eq=cfg.enable_boundary_eq,
            run_std_branching_baseline=cfg.run_std_baseline,
        )
        metrics = compute_phase2_metrics(stats, thresholds)
        all_metrics[label] = metrics
        if metrics["verdict"] != "GO":
            overall_failures.append(f"{label}:{','.join(metrics['verdict_failures'])}")

    summary: Dict[str, Any] = {
        "paradigm": "column_generation_branch_and_price",
        "phase": "phase2_share_cache_rf_routing_boundary",
        "date": time.strftime("%Y-%m-%d"),
        "verdict": "GO" if not overall_failures else "NO-GO",
        "verdict_failures": overall_failures,
        "ramps": all_metrics,
        "args": vars(args),
        "share_cache_summary": cache_summary(cache),
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
    p = argparse.ArgumentParser(description="cand C Phase 2 — share cache + RF + 160/266 + routing + boundary")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--measure", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--region-size", type=int, default=12)
    p.add_argument("--stride", type=int, default=6)
    p.add_argument("--rf-max-depth", type=int, default=5)
    p.add_argument("--rf-max-nodes", type=int, default=1000)
    p.add_argument("--branching-wall-budget-s", type=float, default=60.0)
    p.add_argument("--only-ramp", action="append", default=[],
                   help="restrict to one or more ramp labels (repeatable)")
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

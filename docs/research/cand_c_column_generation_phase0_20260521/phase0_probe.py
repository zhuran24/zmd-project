"""Phase 0 cheap gate probe — Column Generation / Branch-and-Price paradigm.

Hypothesis under test
=====================
A *pattern* (column) of 5-15 facility instances packed into a small region
(8x8..12x12) exists as a useful intermediate granularity between
single-facility poses and the full 70x70 master. If patterns degenerate
to single-facility-per-column or pricing collapses to the original master,
the paradigm dies.

This probe does NOT touch src/. It builds two miniature column-generation
loops (5-instance toy, then 20-instance ramp) and measures 8 metrics to
decide GO / NO-GO before any production investment.

Scope (Phase 0 cheap gate)
--------------------------
- Mandatory facility instances only (a curated mixed-type subset).
- Cell exclusivity + facility-coverage constraints.
- NO power coverage, NO routing, NO ghost rectangle anchoring.
- RMP is a continuous LP via ortools.linear_solver (GLOP).
- Pricing subproblem is a small CP-SAT model bounded to a moving region.

Hard constraints
----------------
- LOC ceiling 1500 (probe + README combined).
- Wall budget 2h.  Probe itself just builds infra; the long measurement
  is queued via --measure on a separate run.
- Do NOT import from src/ (we re-derive the data we need; we read the
  preprocessed JSON only).

GO/NO-GO metrics
----------------
(see README.md for the full table; this script writes phase0_results.json)

Usage
-----
    python -u phase0_probe.py --dry-run     # smoke test, no measurement
    python -u phase0_probe.py --measure     # full Phase 0 measurement
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
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# -----------------------------------------------------------------------------
# Paths + IO
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "preprocessed"
PROBE_DIR = Path(__file__).resolve().parent
RESULTS_PATH = PROBE_DIR / "phase0_results.json"
STATUS_PATH = PROBE_DIR / "phase0_status.json"

# Phase 0 thresholds (see README.md).
GO_THRESHOLDS_5 = {
    "m1_generated_columns_max": 2636,           # <= 50% of 5272 baseline.
    "m2_pricing_p95_seconds_max": 10.0,
    "m3_rmp_lp_p95_seconds_max": 5.0,
    "m4_rss_gb_max": 4.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
}
GO_THRESHOLDS_20 = {
    "m1_generated_columns_max": 5272,           # <= 25% of 21086 baseline.
    "m2_pricing_p95_seconds_max": 30.0,
    "m3_rmp_lp_p95_seconds_max": 5.0,
    "m4_rss_gb_max": 4.0,
    "m5_multi_facility_column_pct_min": 30.0,
    "m6_single_facility_column_pct_max": 50.0,
    "m7_pricing_vars_vs_direct_ratio_max": 0.50,
}

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _peak_rss_gb() -> float:
    """Return peak RSS in GB (Linux: ru_maxrss is in kB)."""
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return float(ru.ru_maxrss) / (1024.0 * 1024.0)


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, int(round(0.95 * (len(s) - 1))))
    return float(s[k])


def _log(msg: str) -> None:
    print(f"[probe {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# -----------------------------------------------------------------------------
# Pose data loading
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PoseRecord:
    tpl: str
    pose_idx: int
    cells: FrozenSet[Tuple[int, int]]
    anchor: Tuple[int, int]


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
            recs.append(PoseRecord(tpl=tpl, pose_idx=idx, cells=cells, anchor=anchor))
        out[tpl] = recs
    return out


def load_mandatory() -> List[Dict[str, Any]]:
    return json.loads((DATA_DIR / "mandatory_exact_instances.json").read_text("utf-8"))


# -----------------------------------------------------------------------------
# Phase 0 toy/ramp subset selection
# -----------------------------------------------------------------------------


def select_subset(
    mandatory: List[Dict[str, Any]],
    n_target: int,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Pick a mixed-type subset of mandatory instances.

    For Phase 0, we want the subset to *look* like a slice of the real
    problem (multiple facility types, multiple operation_types) so the
    pattern grammar sees realistic packing pressure.
    """
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in mandatory:
        by_type[m["facility_type"]].append(m)
    # round-robin pick (deterministic given rng) to mix types.
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


# -----------------------------------------------------------------------------
# Pattern grammar
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Pattern:
    """A column.

    occupied_cells: union of all facility-occupied cells.
    facility_assignments: ordered list of (instance_id, tpl, pose_idx).
    cost: Phase 0 = facility count.  (Phase 1+ may switch to lex/area.)
    region: (x_lo, y_lo, x_hi, y_hi) bounding box (inclusive).
    """

    occupied_cells: FrozenSet[Tuple[int, int]]
    facility_assignments: Tuple[Tuple[str, str, int], ...]
    cost: int
    region: Tuple[int, int, int, int]

    @property
    def covered_instance_ids(self) -> FrozenSet[str]:
        return frozenset(iid for iid, _tpl, _p in self.facility_assignments)

    @property
    def facility_count(self) -> int:
        return len(self.facility_assignments)


def _pose_within_region(
    pose: PoseRecord, region: Tuple[int, int, int, int]
) -> bool:
    x_lo, y_lo, x_hi, y_hi = region
    return all(
        x_lo <= cx <= x_hi and y_lo <= cy <= y_hi for cx, cy in pose.cells
    )


def _enumerate_poses_in_region(
    tpl: str,
    pools: Dict[str, List[PoseRecord]],
    region: Tuple[int, int, int, int],
    max_poses: int = 4096,
) -> List[PoseRecord]:
    out: List[PoseRecord] = []
    for pose in pools[tpl]:
        if _pose_within_region(pose, region):
            out.append(pose)
            if len(out) >= max_poses:
                break
    return out


def degenerate_singleton_columns(
    instances: Sequence[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
    max_poses_per_instance: int = 1,
) -> List[Pattern]:
    """Seed RMP with single-facility columns (one pose each) so LP feasible.

    Pick poses greedily so the seed set has disjoint cells (RMP must be
    LP-feasible).  We scan each instance's pose pool and take the first
    pose that doesn't collide with already-committed cells; on collision
    we keep scanning.  If every pose collides (very crowded), we still
    emit the first pose so RMP picks up the issue as a high-cost LP
    rather than silently dropping the instance.
    """
    cols: List[Pattern] = []
    committed: Set[Tuple[int, int]] = set()
    for inst in instances:
        tpl = inst["facility_type"]
        iid = inst["instance_id"]
        chosen: Optional[PoseRecord] = None
        for pose in pools[tpl]:
            if not pose.cells:
                continue
            if pose.cells.isdisjoint(committed):
                chosen = pose
                break
        if chosen is None:
            chosen = pools[tpl][0] if pools[tpl] else None
        if chosen is None:
            continue
        xs = [c[0] for c in chosen.cells]
        ys = [c[1] for c in chosen.cells]
        region = (min(xs), min(ys), max(xs), max(ys))
        cols.append(
            Pattern(
                occupied_cells=chosen.cells,
                facility_assignments=((iid, tpl, chosen.pose_idx),),
                cost=1,
                region=region,
            )
        )
        committed.update(chosen.cells)
        # Phase 0 cap: only the first max_poses_per_instance pose seeded
        # per instance (we already break on first non-colliding pose).
        _ = max_poses_per_instance
    return cols


# -----------------------------------------------------------------------------
# RMP: LP via ortools GLOP
# -----------------------------------------------------------------------------


@dataclass
class RMPSolveResult:
    objective: float
    lp_seconds: float
    lambda_values: List[float]
    facility_duals: Dict[str, float]
    cell_duals: Dict[Tuple[int, int], float]
    status_str: str


def solve_rmp(
    columns: List[Pattern],
    instance_ids: List[str],
    all_cells_in_play: FrozenSet[Tuple[int, int]],
) -> RMPSolveResult:
    """Solve the LP relaxation of the set-partitioning RMP.

    min  sum_k cost_k * lambda_k
    s.t. for each instance i in instance_ids:
           sum_{k covers i} lambda_k >= 1     (dual pi_i >= 0)
         for each cell (x,y) in all_cells_in_play:
           sum_{k uses (x,y)} lambda_k <= 1   (dual mu_xy <= 0)
         lambda_k >= 0

    Returns the duals: pi_i ("facility duals") and -mu_xy ("cell duals",
    sign-flipped to a positive penalty for pricing convenience).
    """
    from ortools.linear_solver import pywraplp

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("GLOP solver unavailable")
    solver.SuppressOutput()
    infty = solver.infinity()

    lambda_vars = [solver.NumVar(0.0, 1.0, f"l_{k}") for k in range(len(columns))]

    # Facility coverage constraints (>= 1).
    cov_ctrs: Dict[str, Any] = {}
    for iid in instance_ids:
        ctr = solver.Constraint(1.0, infty, f"cov_{iid}")
        cov_ctrs[iid] = ctr
    for k, pat in enumerate(columns):
        for iid in pat.covered_instance_ids:
            if iid in cov_ctrs:
                cov_ctrs[iid].SetCoefficient(lambda_vars[k], 1.0)

    # Cell exclusivity constraints (<= 1).
    cell_ctrs: Dict[Tuple[int, int], Any] = {}
    for cell in all_cells_in_play:
        ctr = solver.Constraint(-infty, 1.0, f"cell_{cell[0]}_{cell[1]}")
        cell_ctrs[cell] = ctr
    for k, pat in enumerate(columns):
        for cell in pat.occupied_cells:
            if cell in cell_ctrs:
                cell_ctrs[cell].SetCoefficient(lambda_vars[k], 1.0)

    # Objective.
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
            cell_duals={cell: 0.0 for cell in all_cells_in_play},
            status_str=status_str,
        )

    facility_duals = {iid: cov_ctrs[iid].dual_value() for iid in instance_ids}
    # Cell exclusivity has constraint <= 1 with dual <= 0.  Negate to a
    # positive penalty used in pricing reduced-cost computation.
    cell_duals = {
        cell: -cell_ctrs[cell].dual_value() for cell in all_cells_in_play
    }
    return RMPSolveResult(
        objective=obj.Value(),
        lp_seconds=lp_seconds,
        lambda_values=[v.solution_value() for v in lambda_vars],
        facility_duals=facility_duals,
        cell_duals=cell_duals,
        status_str=status_str,
    )


# -----------------------------------------------------------------------------
# Pricing subproblem (CP-SAT, region-bounded)
# -----------------------------------------------------------------------------


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
    region: Tuple[int, int, int, int],
    facility_duals: Mapping[str, float],
    cell_duals: Mapping[Tuple[int, int], float],
    max_facilities: int = 15,
    time_limit_s: float = 5.0,
) -> PricingResult:
    """Region-bounded CP-SAT pricing subproblem.

    Decision vars:
      z[(iid, pose_idx)] = 1  iff instance iid is placed at pose pose_idx
                              within region.
    Constraints:
      sum_p z[(iid, p)] <= 1   (each instance used at most once per col)
      sum_{(iid,p): cell in pose_p.cells} z[(iid,p)] <= 1 per cell
      sum_(iid,p) z <= max_facilities
      sum_(iid,p) z >= 2       (Phase 0: require multi-facility columns —
                               degenerate single-pose columns already in
                               the basis)
    Objective:
      min  cost - sum_iid (pi_iid * is_covered_iid)
                - sum_cell (mu_cell * is_used_cell)
    where cost = #facilities in the column.

    Returns reduced_cost = obj_value (the LP-improvement direction).
    """
    from ortools.sat.python import cp_model

    SCALE = 1000  # int scaling for CP-SAT objective.
    x_lo, y_lo, x_hi, y_hi = region

    model = cp_model.CpModel()
    z_vars: Dict[Tuple[str, int], Any] = {}
    pose_lookup: Dict[Tuple[str, int], PoseRecord] = {}
    by_cell: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    by_instance: Dict[str, List[Any]] = defaultdict(list)

    # Per-instance pose enumeration (region-bounded).
    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        for pose in _enumerate_poses_in_region(tpl, pools, region):
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

    # At-most-one pose per instance.
    for iid, vs in by_instance.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)

    # Cell exclusivity.
    for cell, vs in by_cell.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)

    # Cardinality + multi-facility lower bound.
    total = sum(z_vars.values())
    model.Add(total <= max_facilities)
    model.Add(total >= 2)

    # Objective:  cost (sum z, each *SCALE)  -  dual rewards.
    obj_terms = []
    for (iid, pose_idx), v in z_vars.items():
        pose = pose_lookup[(iid, pose_idx)]
        pi = float(facility_duals.get(iid, 0.0))
        cell_penalty = sum(float(cell_duals.get(c, 0.0)) for c in pose.cells)
        # Per-z contribution:  cost(=1) - pi - cell_penalty.
        coeff = (1.0 - pi - cell_penalty)
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

    reduced_cost = float(solver.ObjectiveValue()) / SCALE
    chosen: List[Tuple[str, str, int]] = []
    occupied: Set[Tuple[int, int]] = set()
    for (iid, pose_idx), v in z_vars.items():
        if solver.Value(v) == 1:
            pose = pose_lookup[(iid, pose_idx)]
            inst = next(i for i in instances if i["instance_id"] == iid)
            chosen.append((iid, inst["facility_type"], pose_idx))
            occupied.update(pose.cells)

    if not chosen:
        return PricingResult(
            reduced_cost=reduced_cost,
            pattern=None,
            var_count=var_count,
            wall_seconds=wall,
            status_str=status_str,
        )

    pattern = Pattern(
        occupied_cells=frozenset(occupied),
        facility_assignments=tuple(chosen),
        cost=len(chosen),
        region=region,
    )
    return PricingResult(
        reduced_cost=reduced_cost,
        pattern=pattern,
        var_count=var_count,
        wall_seconds=wall,
        status_str=status_str,
    )


# -----------------------------------------------------------------------------
# Region generator
# -----------------------------------------------------------------------------


def iter_regions(
    grid_w: int,
    grid_h: int,
    region_size: int,
    stride: int,
    rng: random.Random,
    shuffle: bool = True,
) -> List[Tuple[int, int, int, int]]:
    regions: List[Tuple[int, int, int, int]] = []
    for x_lo in range(0, max(1, grid_w - region_size + 1), stride):
        for y_lo in range(0, max(1, grid_h - region_size + 1), stride):
            regions.append((x_lo, y_lo, x_lo + region_size - 1, y_lo + region_size - 1))
    if shuffle:
        rng.shuffle(regions)
    return regions


# -----------------------------------------------------------------------------
# Direct mini pose-bool master (for m7 / m8 sanity)
# -----------------------------------------------------------------------------


@dataclass
class DirectMasterResult:
    var_count: int
    lp_objective: float
    integer_objective: float
    wall_seconds: float
    status_str: str


def solve_direct_mini_master(
    instances: Sequence[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
    region: Tuple[int, int, int, int],
    time_limit_s: float = 30.0,
) -> DirectMasterResult:
    """Mirror of the production pose-bool master, restricted to the same
    instance subset + region.  Used to compute:

      m7 = pricing_vars / direct_vars (we want pricing to be << direct)
      m8 = match check: direct integer objective ≈ CG integer objective
           (here we use facility count as the cost — both should equal
           |instances| if a feasible packing exists).
    """
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    z_vars: Dict[Tuple[str, int], Any] = {}
    by_cell: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    by_instance: Dict[str, List[Any]] = defaultdict(list)

    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        for pose in _enumerate_poses_in_region(tpl, pools, region):
            v = model.NewBoolVar(f"d_{iid}_{pose.pose_idx}")
            z_vars[(iid, pose.pose_idx)] = v
            by_instance[iid].append(v)
            for cell in pose.cells:
                by_cell[cell].append(v)

    # Each instance covered exactly once (forces full packing).
    for iid in (inst["instance_id"] for inst in instances):
        vs = by_instance.get(iid, [])
        if not vs:
            # No feasible pose at all — model is infeasible.
            model.Add(0 == 1)
        else:
            model.Add(sum(vs) == 1)
    for cell, vs in by_cell.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)

    # Phase 0: trivial objective (facility count = constant if all forced).
    model.Minimize(sum(z_vars.values()) if z_vars else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 4

    t0 = time.perf_counter()
    status = solver.Solve(model)
    wall = time.perf_counter() - t0
    status_str = solver.StatusName(status)
    obj_int = float(solver.ObjectiveValue()) if status in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ) else float("inf")
    return DirectMasterResult(
        var_count=len(z_vars),
        lp_objective=obj_int,
        integer_objective=obj_int,
        wall_seconds=wall,
        status_str=status_str,
    )


# -----------------------------------------------------------------------------
# Column generation loop
# -----------------------------------------------------------------------------


@dataclass
class CGRunStats:
    label: str
    n_instances: int
    columns_total: int
    columns_multi: int
    columns_single: int
    multi_pct: float
    single_pct: float
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


def run_column_generation(
    instances: List[Dict[str, Any]],
    pools: Dict[str, List[PoseRecord]],
    label: str,
    *,
    grid_w: int = 70,
    grid_h: int = 70,
    region_size: int = 12,
    stride: int = 6,
    max_iterations: int = 60,
    pricing_time_limit: float = 5.0,
    rng_seed: int = 17,
) -> CGRunStats:
    rng = random.Random(rng_seed)
    instance_ids = [m["instance_id"] for m in instances]

    # Bootstrap basis: single-facility columns for every instance.
    columns: List[Pattern] = degenerate_singleton_columns(instances, pools)
    _log(f"[{label}] bootstrapped {len(columns)} singleton columns")

    all_cells: Set[Tuple[int, int]] = set()
    for pat in columns:
        all_cells.update(pat.occupied_cells)

    regions = iter_regions(grid_w, grid_h, region_size, stride, rng)
    _log(f"[{label}] {len(regions)} candidate regions of size {region_size}")

    stats = CGRunStats(
        label=label,
        n_instances=len(instances),
        columns_total=0,
        columns_multi=0,
        columns_single=0,
        multi_pct=0.0,
        single_pct=0.0,
    )

    region_cursor = 0
    consecutive_failures = 0
    EPSILON = -1e-6  # negative reduced cost threshold.
    for it in range(max_iterations):
        rmp_res = solve_rmp(columns, instance_ids, frozenset(all_cells))
        stats.rmp_walls.append(rmp_res.lp_seconds)
        if rmp_res.status_str not in ("OPTIMAL", "FEASIBLE"):
            stats.exit_reason = f"rmp_{rmp_res.status_str}_at_iter_{it}"
            _log(f"[{label}] RMP not optimal: {rmp_res.status_str}, abort")
            break

        if it % 5 == 0 or it < 3:
            _log(
                f"[{label}] iter {it}  cols={len(columns)}  "
                f"rmp_obj={rmp_res.objective:.3f}  "
                f"rmp_wall={rmp_res.lp_seconds:.3f}s"
            )

        # Try a few regions per iter, pick the best negative reduced cost.
        tried = 0
        best_neg: Optional[PricingResult] = None
        TRIES_PER_ITER = 4
        while tried < TRIES_PER_ITER and region_cursor < len(regions) * 4:
            region = regions[region_cursor % len(regions)]
            region_cursor += 1
            tried += 1
            pricing_res = solve_pricing(
                instances,
                pools,
                region,
                rmp_res.facility_duals,
                rmp_res.cell_duals,
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
            consecutive_failures += 1
            stats.exit_reason = f"no_negative_rc_at_iter_{it}"
            _log(
                f"[{label}] no negative-reduced-cost column at iter {it} "
                f"(tried {tried} regions); stopping"
            )
            break

        new_pat = best_neg.pattern
        columns.append(new_pat)
        all_cells.update(new_pat.occupied_cells)
        stats.iterations = it + 1
        _log(
            f"[{label}] iter {it}+ added col size={new_pat.facility_count} "
            f"rc={best_neg.reduced_cost:+.3f} "
            f"region={new_pat.region}"
        )

    final_res = solve_rmp(columns, instance_ids, frozenset(all_cells))
    stats.final_rmp_objective = final_res.objective
    stats.columns_total = len(columns)
    stats.columns_multi = sum(1 for c in columns if c.facility_count >= 2)
    stats.columns_single = sum(1 for c in columns if c.facility_count == 1)
    if stats.columns_total:
        stats.multi_pct = 100.0 * stats.columns_multi / stats.columns_total
        stats.single_pct = 100.0 * stats.columns_single / stats.columns_total

    # Direct mini master on the same instance set & a representative region
    # (use the bounding box of all bootstrap columns so all instances feasible).
    if columns:
        xs = [c[0] for pat in columns for c in pat.occupied_cells]
        ys = [c[1] for pat in columns for c in pat.occupied_cells]
        bb = (min(xs), min(ys), max(xs), max(ys))
    else:
        bb = (0, 0, grid_w - 1, grid_h - 1)
    _log(f"[{label}] direct mini master on bbox={bb}")
    dm = solve_direct_mini_master(instances, pools, bb, time_limit_s=20.0)
    stats.direct_master_vars = dm.var_count
    stats.direct_master_objective = dm.integer_objective
    stats.direct_master_wall = dm.wall_seconds

    stats.peak_rss_gb = _peak_rss_gb()
    return stats


# -----------------------------------------------------------------------------
# Verdict
# -----------------------------------------------------------------------------


def compute_metrics(stats: CGRunStats, thresholds: Mapping[str, float]) -> Dict[str, Any]:
    pricing_p95 = _p95(stats.pricing_walls)
    rmp_p95 = _p95(stats.rmp_walls)
    pricing_vars_max = max(stats.pricing_var_counts) if stats.pricing_var_counts else 0
    direct_vars = stats.direct_master_vars or 1
    m7_ratio = float(pricing_vars_max) / float(direct_vars) if direct_vars else 0.0
    m8_match = (
        stats.direct_master_objective != float("inf")
        and stats.final_rmp_objective != float("inf")
        and abs(stats.final_rmp_objective - stats.direct_master_objective) <= 1.0
    )

    metrics = {
        "m1_generated_columns": stats.columns_total,
        "m2_pricing_p95_seconds": pricing_p95,
        "m3_rmp_lp_p95_seconds": rmp_p95,
        "m4_rss_gb": stats.peak_rss_gb,
        "m5_multi_facility_column_pct": stats.multi_pct,
        "m6_single_facility_column_pct": stats.single_pct,
        "m7_pricing_vars_vs_direct_ratio": m7_ratio,
        "m8_mini_exactness_match": bool(m8_match),
        "iterations": stats.iterations,
        "final_rmp_objective": stats.final_rmp_objective,
        "direct_master_objective": stats.direct_master_objective,
        "direct_master_vars": stats.direct_master_vars,
        "exit_reason": stats.exit_reason,
    }
    verdict_failures = []
    if metrics["m1_generated_columns"] > thresholds["m1_generated_columns_max"]:
        verdict_failures.append("m1_too_many_columns")
    if metrics["m2_pricing_p95_seconds"] > thresholds["m2_pricing_p95_seconds_max"]:
        verdict_failures.append("m2_pricing_slow")
    if metrics["m3_rmp_lp_p95_seconds"] > thresholds["m3_rmp_lp_p95_seconds_max"]:
        verdict_failures.append("m3_rmp_slow")
    if metrics["m4_rss_gb"] > thresholds["m4_rss_gb_max"]:
        verdict_failures.append("m4_rss_over")
    if metrics["m5_multi_facility_column_pct"] < thresholds["m5_multi_facility_column_pct_min"]:
        verdict_failures.append("m5_not_enough_multi_facility_columns")
    if metrics["m6_single_facility_column_pct"] > thresholds["m6_single_facility_column_pct_max"]:
        verdict_failures.append("m6_too_many_singleton_columns")
    if metrics["m7_pricing_vars_vs_direct_ratio"] > thresholds["m7_pricing_vars_vs_direct_ratio_max"]:
        verdict_failures.append("m7_pricing_not_smaller_than_master")
    if not metrics["m8_mini_exactness_match"]:
        verdict_failures.append("m8_sound_check_failed")

    metrics["verdict"] = "GO" if not verdict_failures else "NO-GO"
    metrics["verdict_failures"] = verdict_failures
    metrics["thresholds"] = dict(thresholds)
    return metrics


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def run_dry_run() -> int:
    _log("dry-run start")
    pools = load_pose_pools()
    mandatory = load_mandatory()
    _log(f"loaded {len(mandatory)} mandatory instances")
    _log(f"loaded {len(pools)} facility-type pose pools")
    for tpl, poses in pools.items():
        _log(f"  pool {tpl}: {len(poses)} poses (sample cells: {sorted(list(poses[0].cells))[:4]})")
    rng = random.Random(42)
    subset5 = select_subset(mandatory, 5, rng)
    _log("subset5 facility_types: " + ", ".join(m["facility_type"] for m in subset5))
    # Toy RMP smoke (2 cols only).
    cols = degenerate_singleton_columns(subset5, pools, max_poses_per_instance=1)
    cells = frozenset({c for p in cols for c in p.occupied_cells})
    res = solve_rmp(cols, [m["instance_id"] for m in subset5], cells)
    _log(f"toy RMP status={res.status_str} obj={res.objective:.3f} lp_wall={res.lp_seconds:.3f}s")
    # Toy pricing smoke (one tiny region).
    pricing = solve_pricing(
        subset5, pools, (0, 0, 11, 11),
        res.facility_duals, res.cell_duals,
        max_facilities=15, time_limit_s=2.0,
    )
    _log(
        f"toy pricing status={pricing.status_str} "
        f"vars={pricing.var_count} wall={pricing.wall_seconds:.3f}s "
        f"reduced_cost={pricing.reduced_cost:+.3f}"
    )
    _log("dry-run complete (no measurement written)")
    return 0


def run_measure(args: argparse.Namespace) -> int:
    _log("measurement start")
    pools = load_pose_pools()
    mandatory = load_mandatory()
    rng = random.Random(args.seed)

    subset5 = select_subset(mandatory, 5, rng)
    subset20 = select_subset(mandatory, 20, rng)

    _log("phase 5-instance toy")
    stats5 = run_column_generation(
        subset5,
        pools,
        label="5inst",
        region_size=args.region_size,
        stride=args.stride,
        max_iterations=args.max_iter_5,
        pricing_time_limit=args.pricing_time_limit_5,
        rng_seed=args.seed,
    )
    metrics5 = compute_metrics(stats5, GO_THRESHOLDS_5)

    _log("phase 20-instance ramp")
    stats20 = run_column_generation(
        subset20,
        pools,
        label="20inst",
        region_size=args.region_size,
        stride=args.stride,
        max_iterations=args.max_iter_20,
        pricing_time_limit=args.pricing_time_limit_20,
        rng_seed=args.seed + 1,
    )
    metrics20 = compute_metrics(stats20, GO_THRESHOLDS_20)

    overall_go = metrics5["verdict"] == "GO" and metrics20["verdict"] == "GO"
    summary: Dict[str, Any] = {
        "paradigm": "column_generation_branch_and_price",
        "phase": "phase0_cheap_gate",
        "date": "2026-05-21",
        "verdict": "GO" if overall_go else "NO-GO",
        "5_instance": metrics5,
        "20_instance": metrics20,
        "args": vars(args),
        "peak_rss_gb_overall": max(stats5.peak_rss_gb, stats20.peak_rss_gb),
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2, default=str))
    _log(f"wrote results to {RESULTS_PATH}")
    _log(f"VERDICT: {summary['verdict']}")
    if not overall_go:
        _log(
            "FAILURES (5inst): "
            + ", ".join(metrics5["verdict_failures"] or ["-"])
        )
        _log(
            "FAILURES (20inst): "
            + ", ".join(metrics20["verdict_failures"] or ["-"])
        )
    return 0 if overall_go else 2


def main() -> int:
    p = argparse.ArgumentParser(description="cand C column generation Phase 0 cheap gate")
    p.add_argument("--dry-run", action="store_true", help="smoke test, no measurement")
    p.add_argument("--measure", action="store_true", help="run full Phase 0 measurement")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--region-size", type=int, default=12)
    p.add_argument("--stride", type=int, default=6)
    p.add_argument("--max-iter-5", type=int, default=60)
    p.add_argument("--max-iter-20", type=int, default=120)
    p.add_argument("--pricing-time-limit-5", type=float, default=5.0)
    p.add_argument("--pricing-time-limit-20", type=float, default=10.0)
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
        STATUS_PATH.write_text(
            json.dumps(
                {
                    "status": "crashed",
                    "error": repr(exc),
                    "elapsed_s": time.perf_counter() - t0,
                },
                indent=2,
            )
        )
        _log(f"CRASH: {exc!r}")
        raise
    STATUS_PATH.write_text(
        json.dumps(
            {
                "status": "ok",
                "rc": rc,
                "mode": "dry-run" if args.dry_run else "measure",
                "elapsed_s": time.perf_counter() - t0,
                "peak_rss_gb": _peak_rss_gb(),
            },
            indent=2,
        )
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())

"""Phase 2 v3 A1 — alternative blueprint generator (fallback for A3).

Phase 2 v3 strategy
====================

Phase 2 v3 lands the A3 set-covering LP relaxation as the primary fix
for the 160/266-inst RMP-INFEASIBLE-at-iter-0 failure mode.  If A3
alone restores LP feasibility but the integer reconstruction phase
caps out (e.g. ≥30% of ramps end UNPROVEN after the branching
budget), A1 turns on as a complement: detect LP-congested cells (where
the cover sum approaches the cell-exclusivity limit 1.0) and generate
*alternative* blueprints — multi-facility columns that explicitly
avoid those cells — to break the over-cover ↔ cell-conflict deadlock.

The A1 work is implemented but env-gated OFF by default (Phase 2 v3
default = A3-only).  Enable for the next measurement round if A3
proves insufficient.

Env flag
========

    EXACT_CANDC_A1_ALTERNATIVE_BP=1    enable A1 generation
    EXACT_CANDC_A1_CONGESTION_THRESH=  cell load ≥ threshold → high
                                       congestion (default 0.85)
    EXACT_CANDC_A1_MAX_PER_ROUND=      alternatives per round (default 10)
    EXACT_CANDC_A1_MAX_ROUNDS=         total rounds per CG iter (default 3)

How it integrates with the main loop
====================================

After the iter-N RMP solve returns OPTIMAL (under set covering),
`run_column_generation_phase2` checks:

    if a1_enabled and rmp_res.over_covered_instances and round < max_rounds:
        congested = detect_high_congestion_cells(...)
        alt_cols = generate_alternative_columns(
            instances, pools, exclude=congested, cap=max_per_round,
        )
        columns.extend(alt_cols)
        resolve RMP and try again before going into pricing CP-SAT.

The alternatives are added to the column pool just like pricing-
generated columns; the next RMP iteration sees them.  Importantly,
they are NOT counted as pricing columns (m1 / m12 stay clean).

This module does NOT touch src/.  Reuses Phase 2 `feasibility_bootstrap`
machinery internally — specifically, Layer 2's region-multi-facility
CP-SAT — with an extra `exclude_cells` hard constraint.
"""

from __future__ import annotations

import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

# Phase 1 reuse.
from cand_c_column_generation_phase1_20260521.column_grammar import (  # type: ignore
    CellCoord,
    Pattern,
    RegionBBox,
)
from cand_c_column_generation_phase1_20260521 import phase1_probe as p1  # type: ignore
from cand_c_column_generation_phase1_20260521.integer_validator import (  # type: ignore
    is_in_ghost_rect,
)


def a1_enabled() -> bool:
    """Resolve A1 env flag.  Default OFF — A3-only is the v3 baseline."""
    return os.environ.get("EXACT_CANDC_A1_ALTERNATIVE_BP", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def congestion_threshold() -> float:
    return _env_float("EXACT_CANDC_A1_CONGESTION_THRESH", 0.85)


def max_alternatives_per_round() -> int:
    return _env_int("EXACT_CANDC_A1_MAX_PER_ROUND", 10)


def max_rounds_per_iter() -> int:
    return _env_int("EXACT_CANDC_A1_MAX_ROUNDS", 3)


# === High-congestion cell detection ===


def detect_high_congestion_cells(
    columns: Sequence[Pattern],
    lambda_values: Sequence[float],
    *,
    threshold: Optional[float] = None,
    top_k: int = 100,
) -> List[Tuple[CellCoord, float]]:
    """Return cells whose Σ_k λ_k [(x,y)∈k] ≥ threshold.

    Returns descending by load.  Cap at top_k cells to avoid generating
    over-constrained alternatives.  threshold defaults to the env flag
    `EXACT_CANDC_A1_CONGESTION_THRESH` (default 0.85).

    Mathematically:
        cell_load(x, y) = Σ_k λ_k * 1[(x,y) ∈ pattern_k.occupied_cells]
    """
    thr = threshold if threshold is not None else congestion_threshold()
    cell_load: Dict[CellCoord, float] = defaultdict(float)
    for k, lam in enumerate(lambda_values):
        if lam <= 1e-9:
            continue
        for cell in columns[k].occupied_cells:
            cell_load[cell] += lam
    high = [(c, v) for c, v in cell_load.items() if v >= thr]
    high.sort(key=lambda kv: -kv[1])
    return high[:top_k]


def detect_raw_conflict_cells(
    columns: Sequence[Pattern],
    *,
    min_conflict_count: int = 2,
    top_k: int = 100,
) -> List[Tuple[CellCoord, int]]:
    """LP-free congestion detector for the INFEASIBLE-iter-0 path.

    When the RMP is INFEASIBLE at iter 0 there is no λ vector to query.
    Fall back to a structural metric: count, for each cell (x, y), the
    number of bootstrap columns that occupy it.  Cells touched by ≥
    min_conflict_count columns are the LP infeasibility hotspots — the
    cell-exclusivity constraint Σλ ≤ 1 collides with mandatory
    coverage Σλ ≥ 1 on every iid contributing to those columns.

    Returns descending by conflict count.  This is the trigger A1 uses
    to seed alternative blueprints when set covering alone could not
    restore LP feasibility.
    """
    cell_count: Dict[CellCoord, int] = defaultdict(int)
    for col in columns:
        for cell in col.occupied_cells:
            cell_count[cell] += 1
    high = [(c, n) for c, n in cell_count.items() if n >= min_conflict_count]
    high.sort(key=lambda kv: -kv[1])
    return high[:top_k]


# === Alternative column generator ===


@dataclass
class A1GenerationResult:
    """Outcome of one A1 generation round.

    Fields:
        columns: newly generated alternative blueprints (multi-facility).
        n_congested: number of cells flagged high-congestion this round.
        n_regions_attempted: how many regions the CP-SAT was run on.
        n_columns_produced: == len(columns) (mirror for telemetry).
        wall_seconds: total wall time for this round.
    """

    columns: List[Pattern] = field(default_factory=list)
    n_congested: int = 0
    n_regions_attempted: int = 0
    n_columns_produced: int = 0
    wall_seconds: float = 0.0


def generate_alternative_columns(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    exclude_cells: Set[CellCoord],
    *,
    grid_w: int = 70,
    grid_h: int = 70,
    region_size: int = 12,
    stride: int = 6,
    time_limit_per_region_s: float = 3.0,
    max_facilities_per_region: int = 12,
    max_alternatives: int = 10,
    rng_seed: int = 0xA12026,
) -> A1GenerationResult:
    """Generate multi-facility columns that avoid exclude_cells.

    Identical to feasibility_bootstrap._layer2_region_columns, but with
    a hard constraint: no pose whose cells intersect exclude_cells may
    be selected.  Returns at most max_alternatives columns (caller
    caps total per round).  The first few "easy" regions are tried
    first — the loop short-circuits once enough alternatives are
    produced.
    """
    from ortools.sat.python import cp_model

    t0 = time.perf_counter()
    result = A1GenerationResult()

    rng = random.Random(rng_seed)
    regions = p1.iter_regions(grid_w, grid_h, region_size, stride, rng)

    for region in regions:
        if len(result.columns) >= max_alternatives:
            break
        # Skip regions entirely inside exclude — saves CP-SAT build cost.
        x0, y0, x1, y1 = region
        region_cells: Set[CellCoord] = set(
            (x, y)
            for x in range(x0, x1 + 1)
            for y in range(y0, y1 + 1)
        )
        if region_cells.issubset(exclude_cells):
            continue
        # Run CP-SAT with exclude_cells filter.
        model = cp_model.CpModel()
        z_vars: Dict[Tuple[str, int], Any] = {}
        pose_lookup: Dict[Tuple[str, int], Any] = {}
        by_cell: Dict[CellCoord, List[Any]] = defaultdict(list)
        by_instance: Dict[str, List[Any]] = defaultdict(list)
        for inst in instances:
            iid = inst["instance_id"]
            tpl = inst["facility_type"]
            for pose in p1.enumerate_poses_in_region(tpl, pools, region):
                # Hard avoid: skip poses that touch any congested cell.
                if any(c in exclude_cells for c in pose.cells):
                    continue
                if any(is_in_ghost_rect(c) for c in pose.cells):
                    continue
                v = model.NewBoolVar(f"a_{iid}_{pose.pose_idx}")
                z_vars[(iid, pose.pose_idx)] = v
                pose_lookup[(iid, pose.pose_idx)] = pose
                by_instance[iid].append(v)
                for cell in pose.cells:
                    by_cell[cell].append(v)
        if not z_vars:
            continue
        result.n_regions_attempted += 1

        for _iid, vs in by_instance.items():
            if len(vs) > 1:
                model.AddAtMostOne(vs)
        for _cell, vs in by_cell.items():
            if len(vs) > 1:
                model.AddAtMostOne(vs)
        total = sum(z_vars.values())
        model.Add(total >= 2)
        model.Add(total <= max_facilities_per_region)
        model.Maximize(total)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_per_region_s
        solver.parameters.num_search_workers = 2
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            continue
        chosen: List[Tuple[str, str, int]] = []
        chosen_poses: List[Any] = []
        for (iid, pidx), v in z_vars.items():
            if solver.Value(v) == 1:
                pose = pose_lookup[(iid, pidx)]
                inst = next(i for i in instances if i["instance_id"] == iid)
                chosen.append((iid, inst["facility_type"], pidx))
                chosen_poses.append(pose)
        if len(chosen) < 2:
            continue
        pat = p1.column_from_pricing_assignment(chosen, pose_lookup, region)
        result.columns.append(pat)

    result.n_columns_produced = len(result.columns)
    result.wall_seconds = time.perf_counter() - t0
    return result


# === Round driver — used by phase2_probe main loop ===


@dataclass
class A1RoundLog:
    """Aggregate telemetry across all A1 rounds within one CG iter."""

    rounds_run: int = 0
    total_alternatives: int = 0
    total_wall_seconds: float = 0.0
    congestion_thresholds: List[float] = field(default_factory=list)


def run_a1_rounds(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    columns: List[Pattern],            # mutated: alternatives appended.
    lambda_values: Sequence[float],
    *,
    grid_w: int = 70,
    grid_h: int = 70,
    region_size: int = 12,
    stride: int = 6,
    log: Optional[Any] = None,
) -> A1RoundLog:
    """Run up to N rounds of (detect congestion -> generate alternatives).

    Mutates `columns` in place — appends generated alternatives.  Caller
    should solve RMP again on the augmented pool after this returns.

    Returns A1RoundLog with telemetry.  If A1 is env-disabled, returns
    an empty log immediately.
    """
    summary = A1RoundLog()
    if not a1_enabled():
        return summary
    if not columns or not lambda_values:
        return summary

    thr = congestion_threshold()
    cap = max_alternatives_per_round()
    max_rounds = max_rounds_per_iter()

    def _emit(m: str) -> None:
        if log is not None:
            log(f"[A1] {m}")

    # Track newly-introduced cells across rounds so we don't recursively
    # bias against our own alternatives.
    accumulated_excludes: Set[CellCoord] = set()
    current_lambda: List[float] = list(lambda_values)
    for r in range(max_rounds):
        congested_list = detect_high_congestion_cells(
            columns, current_lambda, threshold=thr,
        )
        if not congested_list:
            _emit(
                f"round {r}: no cells ≥ threshold {thr:.3f}, A1 done"
            )
            break
        exclude = {c for c, _v in congested_list} | accumulated_excludes
        _emit(
            f"round {r}: {len(congested_list)} congested cells "
            f"(top load {congested_list[0][1]:.3f}), generating ≤{cap} alternatives"
        )
        gen_res = generate_alternative_columns(
            instances, pools, exclude,
            grid_w=grid_w, grid_h=grid_h,
            region_size=region_size, stride=stride,
            max_alternatives=cap,
            rng_seed=0xA12026 + r,
        )
        if not gen_res.columns:
            _emit(
                f"round {r}: no alternatives feasible "
                f"(regions tried={gen_res.n_regions_attempted})"
            )
            break
        before = len(columns)
        columns.extend(gen_res.columns)
        accumulated_excludes |= exclude
        summary.rounds_run += 1
        summary.total_alternatives += len(gen_res.columns)
        summary.total_wall_seconds += gen_res.wall_seconds
        summary.congestion_thresholds.append(thr)
        _emit(
            f"round {r}: +{len(gen_res.columns)} alternatives "
            f"(pool {before}→{len(columns)} wall={gen_res.wall_seconds:.2f}s)"
        )
        # Lambda no longer matches the augmented column pool — caller
        # must re-solve RMP and call this driver again for round r+1.
        # We stop after one round here to keep this function single-
        # round; phase2_probe loops externally.
        break

    return summary


__all__ = [
    "a1_enabled",
    "congestion_threshold",
    "max_alternatives_per_round",
    "max_rounds_per_iter",
    "detect_high_congestion_cells",
    "detect_raw_conflict_cells",
    "generate_alternative_columns",
    "A1GenerationResult",
    "A1RoundLog",
    "run_a1_rounds",
]

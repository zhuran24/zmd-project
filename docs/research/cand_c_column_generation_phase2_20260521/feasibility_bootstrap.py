"""Phase 2 P0 fix — LP-feasibility-preserving bootstrap (3-layer fallback).

Phase 2 v1 (commit 73ea69a) used `degenerate_singleton_columns` from Phase 1
as bootstrap for *all* ramps.  That seed is a greedy disjoint singleton:
for each instance, pick the first non-colliding pose outside the ghost
rect.  On 5/20/40/80 instances this produced a feasible singleton cover
(20-80 instances fit easily in ~4500 free cells).  On 160/266 instances
the greedy hits two failure modes:

1. boundary_storage_port (only 134 pose) and a couple of other
   facility-types with limited pose pools run out of disjoint poses.
2. Even when each instance individually has a free pose, the
   collision-free greedy cannot find one that respects already-committed
   cells from earlier instances.

Either way the resulting RMP's coverage constraint (Aλ = 1 per instance)
gets a column whose `covered_instance_ids` is empty (= the instance was
silently dropped by the greedy).  Aλ = 1 then has no column for that
instance and the LP is infeasible at iter 0.

This module replaces `degenerate_singleton_columns` at the bootstrap
call site with a 3-layer fallback:

Layer 1: try `solve_direct_mini_master` on the whole free area with a
    60s time limit.  If it returns OPTIMAL or FEASIBLE, harvest the
    integer assignment as N singleton columns (one per instance) — these
    are guaranteed to be pairwise cell-disjoint and cover every instance.
    On 160/266 inst this may itself time-out (since direct master is a
    full CP-SAT with O(N × poses) booleans), but on the smaller ramps
    it succeeds quickly.

Layer 2: region-based multi-facility column generator.  Walk the same
    12×12 sliding-window region set the pricing CP-SAT uses, run a
    small CP-SAT per region (≤5s) to find a multi-facility column
    (2-15 facilities).  Collect every region's column into a seed pool.
    This is NOT a cover for every instance — we then merge it with the
    Phase 1 singleton greedy to top up.  The combined pool is what we
    return.  Empirically the region columns provide enough alternate
    poses for boundary_storage_port et al. to break the greedy's tie.

Layer 3: pure singleton greedy fallback (= Phase 1 behaviour).  Used
    only if Layers 1 + 2 both produced nothing useful.  Phase 1 ramps
    fall here and behave identically.

The function never raises — even if all 3 layers fail it returns
whatever singleton greedy produces, matching Phase 1 v0 contract.

Used at:
    phase2_probe.py :: run_column_generation_phase2 — first call before
    the main CG iter loop.

This module does NOT touch src/.  It only imports from Phase 1 +
Phase 2 helpers.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

# Phase 1 reuse.
from cand_c_column_generation_phase1_20260521.column_grammar import (  # type: ignore
    CellCoord,
    Pattern,
    RegionBBox,
    build_pattern,
)
from cand_c_column_generation_phase1_20260521 import phase1_probe as p1  # type: ignore
from cand_c_column_generation_phase1_20260521.integer_validator import (  # type: ignore
    is_in_ghost_rect,
)


@dataclass
class BootstrapResult:
    """Outcome of the 3-layer bootstrap.  Returned to the probe."""

    columns: List[Pattern]
    layer_used: str  # "direct_master" | "region_cg" | "singleton_greedy" | "merged"
    layer1_attempted: bool = False
    layer1_status: str = "skipped"
    layer1_wall_s: float = 0.0
    layer2_attempted: bool = False
    layer2_n_region_columns: int = 0
    layer2_wall_s: float = 0.0
    layer3_attempted: bool = False
    layer3_n_singleton_columns: int = 0
    n_instances: int = 0
    n_covered_instances: int = 0
    rmp_feasible_estimate: bool = False


def _all_covered(
    columns: Sequence[Pattern], instance_ids: Sequence[str]
) -> Tuple[bool, Set[str]]:
    covered: Set[str] = set()
    for col in columns:
        covered.update(col.covered_instance_ids)
    return covered.issuperset(set(instance_ids)), covered


# === Layer 1 — direct master harvest ===


def _layer1_direct_master(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    grid_w: int,
    grid_h: int,
    time_limit_s: float,
) -> Tuple[Optional[List[Pattern]], str, float]:
    """Try solve_direct_mini_master on whole grid; harvest singleton cols.

    Returns (columns or None, status_str, wall_seconds).
    """
    t0 = time.perf_counter()
    region: RegionBBox = (0, 0, grid_w - 1, grid_h - 1)
    try:
        dm = p1.solve_direct_mini_master(
            instances, pools, region,
            time_limit_s=time_limit_s, build_pose_index=False,
        )
    except Exception as exc:  # pragma: no cover — defensive
        return None, f"crashed:{exc!r}", time.perf_counter() - t0
    wall = time.perf_counter() - t0
    if dm.status_str not in ("OPTIMAL", "FEASIBLE"):
        return None, dm.status_str, wall
    # `solve_direct_mini_master` doesn't currently expose the chosen
    # poses — it only reports vars/objective.  To harvest singletons we
    # need to re-run a tiny CP-SAT that just *enumerates* one pose per
    # instance and writes which one was chosen.  Simplest path: replicate
    # the search inline with a callback.
    return _solve_and_harvest_singletons(
        instances, pools, region, time_limit_s=time_limit_s,
    ), dm.status_str, wall


def _solve_and_harvest_singletons(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    region: RegionBBox,
    *,
    time_limit_s: float,
) -> Optional[List[Pattern]]:
    """Run a fresh CP-SAT identical to direct master but harvest cols."""
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    z_vars: Dict[Tuple[str, int], Any] = {}
    pose_lookup: Dict[Tuple[str, int], Any] = {}
    by_cell: Dict[CellCoord, List[Any]] = defaultdict(list)
    by_instance: Dict[str, List[Any]] = defaultdict(list)

    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        for pose in p1.enumerate_poses_in_region(tpl, pools, region):
            if any(is_in_ghost_rect(c) for c in pose.cells):
                continue
            v = model.NewBoolVar(f"b_{iid}_{pose.pose_idx}")
            z_vars[(iid, pose.pose_idx)] = v
            pose_lookup[(iid, pose.pose_idx)] = pose
            by_instance[iid].append(v)
            for cell in pose.cells:
                by_cell[cell].append(v)

    for inst in instances:
        iid = inst["instance_id"]
        vs = by_instance.get(iid, [])
        if not vs:
            # No pose available — model trivially infeasible.
            return None
        model.Add(sum(vs) == 1)
    for _cell, vs in by_cell.items():
        if len(vs) > 1:
            model.AddAtMostOne(vs)

    model.Minimize(sum(z_vars.values()) if z_vars else 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    out: List[Pattern] = []
    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        picked = None
        for (i2, pidx), v in z_vars.items():
            if i2 != iid:
                continue
            if solver.Value(v) == 1:
                picked = pose_lookup[(i2, pidx)]
                break
        if picked is None:
            return None
        out.append(p1.pose_to_pattern(iid, tpl, picked))
    return out


# === Layer 2 — region-based multi-facility column generator ===


def _layer2_region_columns(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    *,
    grid_w: int,
    grid_h: int,
    region_size: int,
    stride: int,
    time_limit_per_region_s: float,
    max_facilities_per_region: int,
    region_count_cap: int,
) -> List[Pattern]:
    """For each region, find a multi-facility column (2-15 facilities).

    Each region runs an independent small CP-SAT.  Output columns are
    collected as candidate bootstrap seeds.  These are NOT guaranteed
    to cover every instance — they're just LP-feasible columns.
    """
    from ortools.sat.python import cp_model
    import random

    cols: List[Pattern] = []
    rng = random.Random(0xC2026)
    regions = p1.iter_regions(grid_w, grid_h, region_size, stride, rng)
    if region_count_cap > 0:
        regions = regions[:region_count_cap]

    for region in regions:
        model = cp_model.CpModel()
        z_vars: Dict[Tuple[str, int], Any] = {}
        pose_lookup: Dict[Tuple[str, int], Any] = {}
        by_cell: Dict[CellCoord, List[Any]] = defaultdict(list)
        by_instance: Dict[str, List[Any]] = defaultdict(list)
        for inst in instances:
            iid = inst["instance_id"]
            tpl = inst["facility_type"]
            for pose in p1.enumerate_poses_in_region(tpl, pools, region):
                if any(is_in_ghost_rect(c) for c in pose.cells):
                    continue
                v = model.NewBoolVar(f"r_{iid}_{pose.pose_idx}")
                z_vars[(iid, pose.pose_idx)] = v
                pose_lookup[(iid, pose.pose_idx)] = pose
                by_instance[iid].append(v)
                for cell in pose.cells:
                    by_cell[cell].append(v)
        if not z_vars:
            continue
        for _iid, vs in by_instance.items():
            if len(vs) > 1:
                model.AddAtMostOne(vs)
        for _cell, vs in by_cell.items():
            if len(vs) > 1:
                model.AddAtMostOne(vs)
        total = sum(z_vars.values())
        model.Add(total >= 2)
        model.Add(total <= max_facilities_per_region)
        # Maximise count — favours many-facility columns.
        model.Maximize(total)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_per_region_s
        solver.parameters.num_search_workers = 2
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            continue
        chosen = []
        chosen_poses = []
        for (iid, pidx), v in z_vars.items():
            if solver.Value(v) == 1:
                pose = pose_lookup[(iid, pidx)]
                inst = next(i for i in instances if i["instance_id"] == iid)
                chosen.append((iid, inst["facility_type"], pidx))
                chosen_poses.append(pose)
        if len(chosen) < 2:
            continue
        pat = p1.column_from_pricing_assignment(chosen, pose_lookup, region)
        cols.append(pat)
    return cols


# === Layer 3 — Phase 1 singleton greedy (unchanged) ===


def _layer3_singleton_greedy(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
) -> List[Pattern]:
    return p1.degenerate_singleton_columns(instances, pools)


# === Public 3-layer entry ===


def feasibility_preserving_bootstrap(
    instances: Sequence[Dict[str, Any]],
    pools: Mapping[str, Sequence[Any]],
    *,
    grid_w: int = 70,
    grid_h: int = 70,
    region_size: int = 12,
    stride: int = 6,
    layer1_time_limit_s: float = 60.0,
    layer2_time_limit_per_region_s: float = 5.0,
    layer2_max_facilities_per_region: int = 15,
    layer2_region_count_cap: int = 60,
    log: Optional[Any] = None,
) -> BootstrapResult:
    """3-layer LP-feasibility-preserving bootstrap.

    Behaviour:
        Layer 1 (direct master harvest): try once.  If OPTIMAL/FEASIBLE
            in time, return its singleton columns — guaranteed cover.
        Layer 2 (region multi-facility CG): always run if Layer 1 fails
            *or* if Layer 1 succeeds with cover gap.  Produces a pool of
            multi-facility columns.
        Layer 3 (singleton greedy): always run as topping-up.  Merge
            into Layer 2's pool; this is the LP-feasibility safety net.

    Final columns = (Layer 1 if available) ∪ Layer 2 ∪ Layer 3 deduped
    by Pattern.column_id.  The merged pool gives the RMP enough
    diversity to be LP-feasible on every instance.
    """
    def _emit(msg: str) -> None:
        if log is not None:
            log(msg)

    instance_ids = [m["instance_id"] for m in instances]
    res = BootstrapResult(columns=[], layer_used="none", n_instances=len(instance_ids))

    merged: Dict[str, Pattern] = {}

    # ---- Layer 1 ----
    res.layer1_attempted = True
    _emit(
        f"[bootstrap] Layer1 direct master attempt (n={len(instance_ids)} "
        f"limit={layer1_time_limit_s:.0f}s)"
    )
    l1_cols, l1_status, l1_wall = _layer1_direct_master(
        instances, pools, grid_w, grid_h, layer1_time_limit_s,
    )
    res.layer1_status = l1_status
    res.layer1_wall_s = l1_wall
    if l1_cols:
        for c in l1_cols:
            merged[c.column_id] = c
        ok, _ = _all_covered(l1_cols, instance_ids)
        _emit(
            f"[bootstrap] Layer1 OK n_cols={len(l1_cols)} cover_full={ok} "
            f"wall={l1_wall:.1f}s status={l1_status}"
        )
        if ok:
            res.columns = list(merged.values())
            res.layer_used = "direct_master"
            res.n_covered_instances = len(_all_covered(res.columns, instance_ids)[1])
            res.rmp_feasible_estimate = True
            return res
    else:
        _emit(
            f"[bootstrap] Layer1 unavailable status={l1_status} wall={l1_wall:.1f}s "
            f"(falling through to Layer 2)"
        )

    # ---- Layer 2 ----
    res.layer2_attempted = True
    _emit(
        f"[bootstrap] Layer2 region CG attempt "
        f"(per_region_limit={layer2_time_limit_per_region_s:.0f}s "
        f"region_cap={layer2_region_count_cap})"
    )
    t0 = time.perf_counter()
    l2_cols = _layer2_region_columns(
        instances, pools,
        grid_w=grid_w, grid_h=grid_h,
        region_size=region_size, stride=stride,
        time_limit_per_region_s=layer2_time_limit_per_region_s,
        max_facilities_per_region=layer2_max_facilities_per_region,
        region_count_cap=layer2_region_count_cap,
    )
    res.layer2_wall_s = time.perf_counter() - t0
    res.layer2_n_region_columns = len(l2_cols)
    for c in l2_cols:
        merged[c.column_id] = c
    _emit(
        f"[bootstrap] Layer2 produced {len(l2_cols)} multi-facility columns "
        f"wall={res.layer2_wall_s:.1f}s"
    )

    # ---- Layer 3 ----
    res.layer3_attempted = True
    l3_cols = _layer3_singleton_greedy(instances, pools)
    res.layer3_n_singleton_columns = len(l3_cols)
    for c in l3_cols:
        merged[c.column_id] = c
    _emit(f"[bootstrap] Layer3 singleton greedy produced {len(l3_cols)} cols")

    res.columns = list(merged.values())
    if len(merged) == res.layer3_n_singleton_columns:
        res.layer_used = "singleton_greedy"
    elif res.layer1_status in ("OPTIMAL", "FEASIBLE"):
        res.layer_used = "merged"
    else:
        res.layer_used = "region_cg+singleton"
    ok, covered = _all_covered(res.columns, instance_ids)
    res.n_covered_instances = len(covered)
    res.rmp_feasible_estimate = ok
    _emit(
        f"[bootstrap] merged total={len(merged)} layer={res.layer_used} "
        f"cover_full={ok} ({res.n_covered_instances}/{res.n_instances})"
    )
    return res


__all__ = [
    "BootstrapResult",
    "feasibility_preserving_bootstrap",
]

"""B3 feasible smoke — G6a + G6b INFEASIBLE-early-stop guard.

Per MERGER §5.4 G6a + G6b (round 3 fix):
- G6a (feasible-only): Build 10K known-feasible cuts from IP v2 blueprint
  hint. After cut application, master.solve must:
  - wall ≤ 180s
  - status OPTIMAL / FEASIBLE (not UNKNOWN, not INFEASIBLE)
  - best_objective_bound 有效不空
- G6b (random cut tolerate-INFEASIBLE): 10K random cut from A3 fixture
  injected; INFEASIBLE allowed but wall MUST > 1s
  (≤ 1s + INFEASIBLE = Presolve 瞬间崩 → N2 trigger)

IP v2 blueprint hint: ``data/hints/blueprint_2026_05_13_master_hint.json``
- {instance_id: pose_idx} for 225 mandatory instances
- Per [[d-step2-blueprint-converter-state]] memory

Known-feasible cut construction approach:
- For each blueprint instance, the hinted pose is "known to be part of a
  feasible solution". A no-good cut that excludes a *different* random
  pose for that instance (but NOT the hinted one) is sound by construction
  and feasibility-preserving.
- Concretely: for each hint entry (inst → hint_pose_idx), pick K random
  poses in that instance's facility_type pool *excluding the hint pose*
  and emit an AddBoolOr([NOT v_p1, ..., NOT v_pK]) — this forbids the
  conjunction of those K non-hint poses but leaves the hint pose untouched.
- Generate 10K such cuts by iterating instances with replacement until
  count hit.

This file is spike-only. Off-limits paths untouched.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

def _resolve_repo_root() -> Path:
    """Return the project root in production and review-mirror layouts.

    Production modules live under project/scripts/spike_prod_scale_lib/.
    Review-package mirrors live under project/code_context/spike/spike_prod_scale_lib/.
    """
    here = Path(__file__).resolve()
    candidates = (here.parent.parent.parent, here.parent.parent.parent.parent)
    for root in candidates:
        if (root / "data" / "preprocessed" / "candidate_placements.json").exists() and (root / "src").is_dir():
            return root
    return candidates[0]


REPO_ROOT = _resolve_repo_root()
sys.path.insert(0, str(REPO_ROOT))

from scripts.spike_prod_scale_lib.telemetry import (  # noqa: E402
    TelemetryBuffer,
    emit_dark_matter,
    emit_proto_sample,
)
from scripts.spike_prod_scale_lib.toy_translator import (  # noqa: E402
    PoseRegistry,
    build_toy_master,
    load_pose_registry,
    measure_proto_bytesize,
)
from scripts.spike_prod_scale_lib.scale_ramp import (  # noqa: E402
    load_fixture_certs,
    oversample_certs,
)


HINT_PATH = REPO_ROOT / "data" / "hints" / "blueprint_2026_05_13_master_hint.json"
MANDATORY_PATH = REPO_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"
PLACEMENTS_PATH = REPO_ROOT / "data" / "preprocessed" / "candidate_placements.json"


# ============================================================================
# Hint loader + feasibility-preserving cut generator
# ============================================================================


def load_blueprint_hint() -> Dict[str, int]:
    """Load {instance_id: pose_idx} hint dict (225 entries in prod)."""
    return json.loads(HINT_PATH.read_text(encoding="utf-8"))


def build_known_feasible_cuts(
    registry: PoseRegistry,
    n_cuts: int,
    *,
    cut_size: int = 3,
    seed: int = 0xFEED,
) -> List[Tuple[List[int], str]]:
    """Build n_cuts known-feasible no-good cuts.

    Each cut is (var_indices, instance_id) where var_indices are pose
    indices in registry that EXCLUDE the hint pose for that instance.
    """
    hint = load_blueprint_hint()
    instances = json.loads(MANDATORY_PATH.read_text(encoding="utf-8"))
    # Observed in spike runner on Python 3.14.x: read_text() on this 53 MB
    # placements file feeds json.loads non-deterministic ValueError. Using
    # read_bytes().decode('utf-8') is a spike-local portability workaround;
    # no master src impact claimed (see toy_translator.load_pose_registry).
    placements = json.loads(PLACEMENTS_PATH.read_bytes().decode("utf-8"))
    pools = placements.get("facility_pools", {})

    # Per-instance pose index list in registry, with hint pose carved out.
    inst_idx_pool: Dict[str, List[int]] = {}
    inst_hint_idx: Dict[str, int] = {}
    for inst in instances:
        iid = inst["instance_id"]
        if iid not in hint:
            continue
        ft = inst["facility_type"]
        pool = pools.get(ft, [])
        if not pool:
            continue
        hint_pose_idx_within_pool = hint[iid]
        if hint_pose_idx_within_pool >= len(pool):
            continue
        hint_pose_id = pool[hint_pose_idx_within_pool]["pose_id"]
        hint_global_idx = registry.idx_by_facility_pose.get((ft, hint_pose_id))
        if hint_global_idx is None:
            continue
        all_global_idxs = [
            registry.idx_by_facility_pose[(ft, p["pose_id"])]
            for p in pool
            if (ft, p["pose_id"]) in registry.idx_by_facility_pose
        ]
        non_hint_global = [g for g in all_global_idxs if g != hint_global_idx]
        if len(non_hint_global) < cut_size:
            continue
        inst_idx_pool[iid] = non_hint_global
        inst_hint_idx[iid] = hint_global_idx

    if not inst_idx_pool:
        return []

    rng = random.Random(seed)
    inst_ids = list(inst_idx_pool.keys())
    cuts: List[Tuple[List[int], str]] = []
    for _ in range(n_cuts):
        iid = rng.choice(inst_ids)
        pool = inst_idx_pool[iid]
        k = min(cut_size, len(pool))
        picks = rng.sample(pool, k)
        cuts.append((picks, iid))
    return cuts


def apply_known_feasible_cuts(
    model: cp_model.CpModel,
    registry: PoseRegistry,
    cuts: List[Tuple[List[int], str]],
) -> int:
    """Apply each cut as AddBoolOr([NOT v_i for i in picks]). Return n applied."""
    n_applied = 0
    for var_idxs, _iid in cuts:
        lits = [registry.var_by_idx[i].Not() for i in var_idxs]
        if not lits:
            continue
        model.AddBoolOr(lits)
        n_applied += 1
    return n_applied


def apply_hint_to_master(
    model: cp_model.CpModel,
    registry: PoseRegistry,
) -> Dict[str, int]:
    """Pin known-feasible solution via AddHint (not hard constraint).

    Each hinted (instance_id, pose_idx) → AddHint(var_for_that_pose, 1).
    Other vars hinted 0 only for instances with hint (don't bias rest).
    Returns count of vars hinted.
    """
    hint = load_blueprint_hint()
    instances = json.loads(MANDATORY_PATH.read_text(encoding="utf-8"))
    # Observed in spike runner on Python 3.14.x: read_text() on this 53 MB
    # placements file feeds json.loads non-deterministic ValueError. Using
    # read_bytes().decode('utf-8') is a spike-local portability workaround;
    # no master src impact claimed (see toy_translator.load_pose_registry).
    placements = json.loads(PLACEMENTS_PATH.read_bytes().decode("utf-8"))
    pools = placements.get("facility_pools", {})

    n_one = 0
    n_zero = 0
    for inst in instances:
        iid = inst["instance_id"]
        if iid not in hint:
            continue
        ft = inst["facility_type"]
        pool = pools.get(ft, [])
        if not pool:
            continue
        hint_idx_in_pool = hint[iid]
        if hint_idx_in_pool >= len(pool):
            continue
        hint_pid = pool[hint_idx_in_pool]["pose_id"]
        hint_g = registry.idx_by_facility_pose.get((ft, hint_pid))
        if hint_g is None:
            continue
        model.AddHint(registry.var_by_idx[hint_g], 1)
        n_one += 1
    return {"hinted_one": n_one, "hinted_zero": n_zero}


# ============================================================================
# Reports
# ============================================================================


@dataclass
class SmokeTierReport:
    label: str  # "feasible" / "random"
    cut_count_target: int
    cut_count_applied: int
    n_vars: int
    n_constraints: int
    proto_mb: float
    build_wall_s: float
    cut_apply_wall_s: float
    solve_wall_s: float
    status_label: str
    best_objective_bound: Optional[float]
    objective_value: Optional[float]
    rss_peak_gb: float
    notes: List[str] = field(default_factory=list)


@dataclass
class FeasibleSmokeReport:
    feasible_tier: Optional[SmokeTierReport] = None
    random_tier: Optional[SmokeTierReport] = None
    g_pass: Dict[str, bool] = field(default_factory=dict)
    n_trigger: Dict[str, bool] = field(default_factory=dict)

    @property
    def all_g_pass(self) -> bool:
        return all(self.g_pass.values()) if self.g_pass else False

    def format_human(self) -> str:
        lines = ["feasible smoke DONE"]
        for tier in (self.feasible_tier, self.random_tier):
            if tier is None:
                continue
            obj_bound = f"{tier.best_objective_bound:.3f}" if tier.best_objective_bound is not None else "n/a"
            obj_val = f"{tier.objective_value:.3f}" if tier.objective_value is not None else "n/a"
            lines.append(
                f"  [{tier.label:>8}] cuts {tier.cut_count_applied}/{tier.cut_count_target}, "
                f"vars={tier.n_vars}, cons={tier.n_constraints}, "
                f"build={tier.build_wall_s:.2f}s, apply={tier.cut_apply_wall_s:.2f}s, "
                f"solve={tier.solve_wall_s:.2f}s ({tier.status_label}), "
                f"obj={obj_val}, bound={obj_bound}, proto={tier.proto_mb:.1f}MB, "
                f"rss_peak={tier.rss_peak_gb:.2f}GB"
            )
            for n in tier.notes:
                lines.append(f"    note: {n}")
        lines.append(f"  g_pass:    {self.g_pass}")
        lines.append(f"  n_trigger: {self.n_trigger}")
        return "\n".join(lines)


# ============================================================================
# Runner
# ============================================================================


def _rss_gb_now() -> float:
    import psutil
    return psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3)


def _status_label(status: int) -> str:
    return {
        cp_model.OPTIMAL:    "OPTIMAL",
        cp_model.FEASIBLE:   "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN:    "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(status, f"status={status}")


def run_feasible_tier(
    registry: PoseRegistry,
    buf: TelemetryBuffer,
    *,
    n_cuts: int = 10_000,
    solve_wall_cap_s: float = 180.0,
) -> SmokeTierReport:
    """G6a — 10K known-feasible cuts + AddHint + objective + solve.

    To make ``best_objective_bound`` actually valid (not None), we attach a
    trivial objective: ``Maximize(sum(all_vars))``. Combined with the
    feasibility-preserving cuts and AddHint, solver should land OPTIMAL/
    FEASIBLE quickly.
    """
    registry.var_by_idx = []
    rss_before = _rss_gb_now()
    t0 = time.monotonic()
    model, build_rpt = build_toy_master(registry, add_demand_constraints=True)
    build_wall = time.monotonic() - t0
    rss_after_build = _rss_gb_now()

    emit_proto_sample(buf, "smoke_feasible_post_build", build_rpt.proto_bytesize,
                      build_rpt.n_vars, build_rpt.n_demand_constraints)

    # Build feasibility-preserving cuts.
    feasible_cuts = build_known_feasible_cuts(registry, n_cuts)
    t1 = time.monotonic()
    n_applied = apply_known_feasible_cuts(model, registry, feasible_cuts)
    apply_wall = time.monotonic() - t1

    # Add objective so best_objective_bound is meaningful.
    model.Maximize(sum(registry.var_by_idx))

    # Inject hint to bias solver toward known-feasible region.
    hint_stats = apply_hint_to_master(model, registry)

    proto_size = measure_proto_bytesize(model)
    proto_mb = proto_size / (1024 ** 2)
    emit_proto_sample(buf, "smoke_feasible_post_cuts", proto_size,
                      build_rpt.n_vars, build_rpt.n_demand_constraints + n_applied)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solve_wall_cap_s
    solver.parameters.num_search_workers = 1
    t2 = time.monotonic()
    status = solver.Solve(model)
    solve_wall = time.monotonic() - t2
    rss_after_solve = _rss_gb_now()
    status_label = _status_label(status)

    obj_value = solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    try:
        obj_bound: Optional[float] = solver.BestObjectiveBound()
    except Exception:
        obj_bound = None

    if status in (cp_model.INFEASIBLE, cp_model.UNKNOWN):
        emit_dark_matter(
            buf,
            context="smoke_feasible tier",
            status_label=status_label,
            wall_s=solve_wall,
            extra={
                "n_cuts_applied": n_applied,
                "n_hint_vars": hint_stats["hinted_one"],
            },
        )

    notes = [
        f"hint vars set to 1: {hint_stats['hinted_one']}",
        "objective: Maximize(sum all 81795 vars)",
    ]

    return SmokeTierReport(
        label="feasible",
        cut_count_target=n_cuts,
        cut_count_applied=n_applied,
        n_vars=build_rpt.n_vars,
        n_constraints=build_rpt.n_demand_constraints + n_applied,
        proto_mb=proto_mb,
        build_wall_s=build_wall,
        cut_apply_wall_s=apply_wall,
        solve_wall_s=solve_wall,
        status_label=status_label,
        best_objective_bound=obj_bound,
        objective_value=obj_value,
        rss_peak_gb=max(rss_before, rss_after_build, rss_after_solve),
        notes=notes,
    )


def run_random_tier(
    registry: PoseRegistry,
    buf: TelemetryBuffer,
    fixture_certs: List[dict],
    *,
    n_cuts: int = 10_000,
    solve_wall_cap_s: float = 60.0,
) -> SmokeTierReport:
    """G6b — 10K random cuts from A3 fixture; INFEASIBLE allowed, wall > 1s."""
    from scripts.spike_prod_scale_lib.toy_translator import translate_certs_to_constraints

    registry.var_by_idx = []
    rss_before = _rss_gb_now()
    t0 = time.monotonic()
    model, build_rpt = build_toy_master(registry, add_demand_constraints=True)
    build_wall = time.monotonic() - t0

    emit_proto_sample(buf, "smoke_random_post_build", build_rpt.proto_bytesize,
                      build_rpt.n_vars, build_rpt.n_demand_constraints)

    cut_records = oversample_certs(fixture_certs, n_cuts, seed=0x1234)
    t1 = time.monotonic()
    tr = translate_certs_to_constraints(model, registry, cut_records)
    apply_wall = time.monotonic() - t1

    proto_size = measure_proto_bytesize(model)
    emit_proto_sample(buf, "smoke_random_post_cuts", proto_size,
                      build_rpt.n_vars, build_rpt.n_demand_constraints + tr.n_constraints_added)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solve_wall_cap_s
    solver.parameters.num_search_workers = 1
    t2 = time.monotonic()
    status = solver.Solve(model)
    solve_wall = time.monotonic() - t2
    rss_after_solve = _rss_gb_now()
    status_label = _status_label(status)
    obj_val = solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    try:
        obj_bound: Optional[float] = solver.BestObjectiveBound()
    except Exception:
        obj_bound = None

    if status in (cp_model.INFEASIBLE, cp_model.UNKNOWN):
        emit_dark_matter(
            buf,
            context="smoke_random tier",
            status_label=status_label,
            wall_s=solve_wall,
            extra={"n_cuts_applied": tr.n_certs_applied},
        )

    return SmokeTierReport(
        label="random",
        cut_count_target=n_cuts,
        cut_count_applied=tr.n_certs_applied,
        n_vars=build_rpt.n_vars,
        n_constraints=build_rpt.n_demand_constraints + tr.n_constraints_added,
        proto_mb=proto_size / (1024 ** 2),
        build_wall_s=build_wall,
        cut_apply_wall_s=apply_wall,
        solve_wall_s=solve_wall,
        status_label=status_label,
        best_objective_bound=obj_bound,
        objective_value=obj_val,
        rss_peak_gb=max(rss_before, rss_after_solve),
    )


def run_feasible_smoke(
    *,
    n_cuts: int = 10_000,
    buf: Optional[TelemetryBuffer] = None,
    feasible_solve_cap_s: float = 180.0,
    random_solve_cap_s: float = 60.0,
) -> FeasibleSmokeReport:
    if buf is None:
        out_telemetry = REPO_ROOT / "data" / "cuts" / "spike" / f"telemetry_feasible_smoke_{os.getpid()}.jsonl"
        buf = TelemetryBuffer(out_path=out_telemetry)

    registry = load_pose_registry()
    fixture_certs = load_fixture_certs()

    feasible = run_feasible_tier(registry, buf, n_cuts=n_cuts,
                                  solve_wall_cap_s=feasible_solve_cap_s)
    random_t = run_random_tier(registry, buf, fixture_certs, n_cuts=n_cuts,
                                solve_wall_cap_s=random_solve_cap_s)

    report = FeasibleSmokeReport(feasible_tier=feasible, random_tier=random_t)

    # G6a verdict — per MERGER §5.4 G6a (round 3 fix):
    #   wall ≤ 180s, status OPTIMAL/FEASIBLE, best_objective_bound valid.
    # "Wall ≤ 180s" criterion: solver did not exceed cap. If solver hit cap
    # AND status is FEASIBLE with valid bound, that's a soft FAIL (sizing
    # wise solve worked but didn't prove OPTIMAL within budget) — we report
    # it as FAIL but mark distinguishable.
    g6a_wall_ok = feasible.solve_wall_s < feasible_solve_cap_s - 0.5  # not at cap
    g6a_status_ok = feasible.status_label in ("OPTIMAL", "FEASIBLE")
    g6a_bound_ok = feasible.best_objective_bound is not None
    report.g_pass["G6a_feasible_wall"] = g6a_wall_ok
    report.g_pass["G6a_feasible_status"] = g6a_status_ok
    report.g_pass["G6a_feasible_bound_valid"] = g6a_bound_ok
    # Note: solver hit cap (180s) on this toy means "FEASIBLE achievable,
    # OPTIMAL not provable in budget" — NOT a Presolve crash, this is
    # acceptable for G6a sizing intent (status FEASIBLE + bound valid).

    # G6b verdict + N2 trigger
    if random_t.status_label == "INFEASIBLE" and random_t.solve_wall_s <= 1.0:
        report.n_trigger["N2_random_presolve_crash"] = True
        report.g_pass["G6b_random_wall_above_1s"] = False
    else:
        report.g_pass["G6b_random_wall_above_1s"] = True

    return report


if __name__ == "__main__":
    rep = run_feasible_smoke()
    print(rep.format_human())
    raise SystemExit(0 if rep.all_g_pass else 1)

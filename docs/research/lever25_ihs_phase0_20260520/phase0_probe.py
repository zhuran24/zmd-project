"""Lever 25 IHS Phase 0 cheap gate probe.

See README.md for full hypothesis / stage gate / known risks. TL;DR: monkey-patch
PoseBoolExactMasterDelegate's add_benders_cut + add_patch_routing_core_cut to
record (iter, source, core_size, literals), then judge GO/NO-GO from the
core-size distribution and an offline-batch minimum hitting set ILP over the
accumulated cores.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROBE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROBE_ROOT.parents[2]
sys.path.insert(0, str(REPO_ROOT))


# ----------------------------------------------------------------------------
# Telemetry container
# ----------------------------------------------------------------------------

class IhsTelemetry:
    """Accumulator for per-iter core observations + Stage 2 HS solver records."""

    def __init__(self) -> None:
        # iter -> list of (source, core_size, literals as tuple of (iid, pose))
        self.iter_cores: Dict[int, List[Dict[str, Any]]] = {}
        # iter -> HS optimizer record (wall, hs_size, compression_ratio)
        self.iter_hs: Dict[int, Dict[str, Any]] = {}
        # global current iter (set by hook from outside via setter)
        self.current_iter: int = 0
        # all literals across all iters — needed for HS optimizer + union baseline
        self.all_cores: List[Dict[str, Any]] = []
        # stage 1 gate decision (filled by gate logic)
        self.stage1_verdict: Optional[str] = None
        # Whether stage 2 is active (set after gate)
        self.stage2_active: bool = False

    def record_core(
        self,
        *,
        source: str,
        core_size: int,
        literals: Sequence[Tuple[str, int]],
    ) -> None:
        record = {
            "iter": self.current_iter,
            "source": source,
            "core_size": int(core_size),
            "literals": [(str(a), int(b)) for (a, b) in literals],
        }
        self.iter_cores.setdefault(self.current_iter, []).append(record)
        self.all_cores.append(record)

    def core_sizes_so_far(self) -> List[int]:
        return [r["core_size"] for r in self.all_cores]


_TELEMETRY = IhsTelemetry()


# ----------------------------------------------------------------------------
# Stage 1 gate
# ----------------------------------------------------------------------------

def stage1_decide(sizes: Sequence[int]) -> Tuple[str, Dict[str, Any]]:
    """Decide Stage 1 GO/NO-GO based on sizes seen so far.

    GO:      p50 >= 3 AND >= 50% sizes > 1
    NO-GO:   p50 < 3  OR  >= 80% sizes == 1
    PENDING: otherwise (not enough data / borderline; keep collecting)
    """
    if not sizes:
        return "PENDING", {"n": 0}
    n = len(sizes)
    p50 = statistics.median(sizes)
    pct_eq_1 = sum(1 for s in sizes if s == 1) / n
    pct_gt_1 = sum(1 for s in sizes if s > 1) / n
    dist = dict(Counter(sizes))
    summary = {
        "n": n,
        "p50": float(p50),
        "pct_eq_1": float(pct_eq_1),
        "pct_gt_1": float(pct_gt_1),
        "distribution": {str(k): int(v) for k, v in dist.items()},
    }
    if p50 >= 3 and pct_gt_1 >= 0.5:
        return "GO", summary
    if p50 < 3 or pct_eq_1 >= 0.8:
        return "NO-GO", summary
    return "PENDING", summary


# ----------------------------------------------------------------------------
# Stage 2 — Hitting Set ILP
# ----------------------------------------------------------------------------

def solve_minimum_hitting_set(
    cores: Sequence[Sequence[Tuple[str, int]]],
    *,
    time_limit_s: float = 5.0,
) -> Dict[str, Any]:
    """Min hitting set ILP via CP-SAT.

    Vars: x_lit ∈ {0,1} for each unique literal across all cores.
    Constraints: for each core C: sum(x_lit for lit in C) >= 1.
    Obj: minimize sum(x_lit).
    """
    from ortools.sat.python import cp_model

    unique_lits: List[Tuple[str, int]] = sorted({lit for core in cores for lit in core})
    if not unique_lits:
        return {
            "status": "EMPTY",
            "hs_size": 0,
            "union_size": 0,
            "compression": 1.0,
            "wall_s": 0.0,
            "hitting_set": [],
        }

    model = cp_model.CpModel()
    x_by_lit: Dict[Tuple[str, int], cp_model.IntVar] = {
        lit: model.NewBoolVar(f"x_{idx}") for idx, lit in enumerate(unique_lits)
    }
    for core_idx, core in enumerate(cores):
        if not core:
            # empty core — vacuously hit; skip
            continue
        model.Add(sum(x_by_lit[lit] for lit in core) >= 1)
    model.Minimize(sum(x_by_lit.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.num_workers = 1
    t0 = time.perf_counter()
    status = solver.Solve(model)
    wall = time.perf_counter() - t0
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name,
            "hs_size": 0,
            "union_size": len(unique_lits),
            "compression": 1.0,
            "wall_s": round(wall, 4),
            "hitting_set": [],
        }

    hs = [lit for lit, var in x_by_lit.items() if solver.Value(var) == 1]
    return {
        "status": status_name,
        "hs_size": len(hs),
        "union_size": len(unique_lits),
        "compression": len(hs) / max(1, len(unique_lits)),
        "wall_s": round(wall, 4),
        "hitting_set": [list(lit) for lit in hs],
    }


# ----------------------------------------------------------------------------
# Delegate hook installer
# ----------------------------------------------------------------------------

def install_delegate_class_hooks() -> None:
    """Patch PoseBoolExactMasterDelegate's add_benders_cut +
    add_patch_routing_core_cut at the CLASS level so every instance gets the
    wrapper. Cleaner than per-instance because the delegate is created inside
    MasterPlacementModel.__init__ before any external observer can grab it.

    Both wrappers:
        1. Record (source, core_size, literals) into _TELEMETRY.
        2. Forward to the original method unmodified.
    Stage 2 compression measurement runs OFFLINE on accumulated cores after the
    LBBD run completes — keeps zero risk of breaking the convergence semantics
    while still answering the gate question (does the HS optimizer find a set
    strictly smaller than the union of all observed literals?).
    """
    from src.models.pose_bool_exact_master import PoseBoolExactMasterDelegate

    orig_add_benders = PoseBoolExactMasterDelegate.add_benders_cut

    def wrapped_add_benders(self, conflict_set, *args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            lits = [(str(k), int(v)) for k, v in dict(conflict_set).items()]
            _TELEMETRY.record_core(
                source="add_benders_cut",
                core_size=len(lits),
                literals=lits,
            )
        except Exception as exc:
            print(f"[ihs-hook] add_benders_cut record err: {exc}", flush=True)
        return orig_add_benders(self, conflict_set, *args, **kwargs)

    PoseBoolExactMasterDelegate.add_benders_cut = wrapped_add_benders  # type: ignore[assignment]

    orig_add_patch = getattr(PoseBoolExactMasterDelegate, "add_patch_routing_core_cut", None)
    if orig_add_patch is not None:
        def wrapped_add_patch(self, core_terms, patch_cells, *args, **kwargs):  # type: ignore[no-untyped-def]
            try:
                lits = [(str(a), int(b)) for (a, b) in core_terms]
                _TELEMETRY.record_core(
                    source="add_patch_routing_core_cut",
                    core_size=len(lits),
                    literals=lits,
                )
            except Exception as exc:
                print(f"[ihs-hook] add_patch_routing_core_cut record err: {exc}", flush=True)
            return orig_add_patch(self, core_terms, patch_cells, *args, **kwargs)
        PoseBoolExactMasterDelegate.add_patch_routing_core_cut = wrapped_add_patch  # type: ignore[assignment]

    print(
        f"[ihs-hook] class-level hooks installed on PoseBoolExactMasterDelegate "
        f"(add_benders_cut + add_patch_routing_core_cut)",
        flush=True,
    )


# ----------------------------------------------------------------------------
# Iter counter — patch outer LBBD loop print to bump telemetry.current_iter
# ----------------------------------------------------------------------------

def install_iter_tracker() -> None:
    """We need to know which LBBD iter each cut belongs to. Cheapest hook:
    wrap builtins.print to detect '[LBBD Exact Loop] Iteration N/M' lines.
    """
    import builtins
    real_print = builtins.print

    def hooked_print(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            msg = " ".join(str(a) for a in args)
            if "[LBBD Exact Loop] Iteration" in msg:
                # form: "--- [LBBD Exact Loop] Iteration 3/10 ---"
                tail = msg.split("Iteration", 1)[1].strip()
                num_str = tail.split("/", 1)[0].strip()
                _TELEMETRY.current_iter = int(num_str)
        except Exception:
            pass
        return real_print(*args, **kwargs)

    builtins.print = hooked_print  # type: ignore[assignment]


# ----------------------------------------------------------------------------
# Verdict logic
# ----------------------------------------------------------------------------

def compute_verdict(*, lbbd_status: Optional[str], elapsed_s: float) -> Dict[str, Any]:
    sizes_all = _TELEMETRY.core_sizes_so_far()
    s1_verdict, s1_summary = stage1_decide(sizes_all)
    n_iter = max(_TELEMETRY.current_iter, len(_TELEMETRY.iter_cores))

    # accumulated cores → union baseline + HS optimizer (offline batch, regardless
    # of whether stage 2 was "live" wired — we just want the compression metric)
    cores_lits = [tuple(r["literals"]) for r in _TELEMETRY.all_cores]
    hs_offline = solve_minimum_hitting_set(cores_lits, time_limit_s=5.0)

    stage2_eligible = s1_verdict == "GO" and len(sizes_all) >= 5
    stage2_pass = False
    stage2_reason = ""
    if stage2_eligible:
        compression = hs_offline.get("compression", 1.0)
        hs_wall = hs_offline.get("wall_s", 0.0)
        status_ok = lbbd_status in ("CERTIFIED", "INFEASIBLE")
        if not status_ok:
            stage2_reason = f"final_status={lbbd_status} not CERTIFIED/INFEASIBLE"
        elif hs_wall > 60.0:
            stage2_reason = f"hs_wall={hs_wall}s > 60s"
        elif compression >= 1.0:
            stage2_reason = f"compression={compression} >= 1.0 (no shrink)"
        else:
            stage2_pass = True
            stage2_reason = "ok"

    final_verdict: str
    if s1_verdict == "NO-GO":
        final_verdict = "NO-GO"
        reason = "stage1_no_go"
    elif s1_verdict == "PENDING":
        final_verdict = "INCONCLUSIVE"
        reason = "stage1_pending_after_full_run"
    elif s1_verdict == "GO":
        if not stage2_eligible:
            final_verdict = "INCONCLUSIVE"
            reason = "stage1_go_but_too_few_cores_for_stage2"
        elif stage2_pass:
            final_verdict = "GO"
            reason = "stage1_go_and_stage2_pass"
        else:
            final_verdict = "NO-GO"
            reason = f"stage1_go_but_stage2_fail:{stage2_reason}"
    else:
        final_verdict = "INCONCLUSIVE"
        reason = "no_cores_observed"

    return {
        "final_verdict": final_verdict,
        "reason": reason,
        "stage1": {"verdict": s1_verdict, "summary": s1_summary},
        "stage2": {
            "eligible": stage2_eligible,
            "pass": stage2_pass,
            "reason": stage2_reason,
            "hs_offline": hs_offline,
        },
        "lbbd_final_status": lbbd_status,
        "total_iters_observed": n_iter,
        "total_cores": len(_TELEMETRY.all_cores),
        "elapsed_s": round(elapsed_s, 2),
    }


# ----------------------------------------------------------------------------
# Main probe
# ----------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify import + hook install + HS optimizer skeleton only.",
    )
    parser.add_argument("--max-iter", type=int, default=10)
    parser.add_argument("--master-seconds", type=float, default=120.0)
    parser.add_argument("--routing-seconds", type=float, default=60.0)
    parser.add_argument("--binding-seconds", type=float, default=30.0)
    parser.add_argument("--anchor", default="22,28")
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument(
        "--results-json",
        default=str(PROBE_ROOT / "phase0_results.json"),
    )
    args = parser.parse_args(argv)

    # Always env-set first so all imports below see them.
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE"] = "1"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_TOP_K"] = "3"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_SECONDS"] = "15"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_PER_PATCH_SECONDS"] = "5"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS"] = "900"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_QX_CAP"] = "24"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = args.anchor
    # Clear competing experiment flags so PCR-CUT path is the live cut source.
    for k in (
        "EXACT_B1_SEPARATOR_HULL",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT",
        "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK",
        "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE",
        "EXACT_B1_ROUTING_AWARE_BINDING",
        "EXACT_B1_D2_COMMODITY_FLOW",
    ):
        os.environ.pop(k, None)

    # Banner
    print("=" * 70, flush=True)
    print("Lever 25 IHS — Phase 0 cheap gate probe", flush=True)
    print(
        f"  anchor={args.anchor} ghost={args.ghost_w}x{args.ghost_h} "
        f"max_iter={args.max_iter} master_sec={args.master_seconds} "
        f"dry_run={args.dry_run}",
        flush=True,
    )
    print(
        "  Stage 1 GO: core p50>=3 AND >=50% size>1.  "
        "Stage 1 NO-GO: p50<3 OR >=80% size==1.",
        flush=True,
    )
    print("=" * 70, flush=True)

    # Install hooks at the class level BEFORE the first MasterPlacementModel
    # constructs its PoseBoolExactMasterDelegate (which happens inside the
    # first run_benders_for_ghost_rect call).
    install_delegate_class_hooks()
    install_iter_tracker()

    # Quick HS sanity check (always run, even in dry-run)
    sample_cores = [
        [("a", 1), ("b", 2)],
        [("a", 1), ("c", 3)],
        [("b", 2), ("d", 4)],
    ]
    hs_sanity = solve_minimum_hitting_set(sample_cores, time_limit_s=2.0)
    print(f"[ihs-sanity] HS optimizer on toy {sample_cores}: {hs_sanity}", flush=True)
    assert hs_sanity["hs_size"] >= 2, "HS optimizer sanity failed"
    assert hs_sanity["status"] in {"OPTIMAL", "FEASIBLE"}, "HS sanity status bad"

    if args.dry_run:
        # Just import LBBD entry to validate API resolution; do not run.
        from src.search.benders_loop import run_benders_for_ghost_rect  # noqa: F401
        print("[dry-run] all imports/hooks resolved ok. exiting.", flush=True)
        return 0

    # Real LBBD run
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status: Optional[str] = None
    exc_info: Optional[str] = None
    try:
        status, _meta = run_benders_for_ghost_rect(
            ghost_w=args.ghost_w,
            ghost_h=args.ghost_h,
            max_iterations=args.max_iter,
            project_root=Path(REPO_ROOT),
            solve_mode="certified_exact",
            master_seconds=args.master_seconds,
            binding_seconds=args.binding_seconds,
            routing_seconds=args.routing_seconds,
            flow_seconds=10.0,
            campaign=None,
            session=None,
            disable_master_warm_start=True,
        )
    except Exception as exc:
        exc_info = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        print(f"[ihs-probe] LBBD raised: {exc_info}", flush=True)
    elapsed = time.perf_counter() - t0
    print(f"\n[ihs-probe] LBBD done in {elapsed:.1f}s status={status}", flush=True)

    verdict = compute_verdict(lbbd_status=status, elapsed_s=elapsed)
    out_payload: Dict[str, Any] = {
        "schema_version": 1,
        "probe": "lever25_ihs_phase0",
        "anchor": args.anchor,
        "ghost_size": f"{args.ghost_w}x{args.ghost_h}",
        "args": {
            "max_iter": args.max_iter,
            "master_seconds": args.master_seconds,
            "routing_seconds": args.routing_seconds,
            "binding_seconds": args.binding_seconds,
        },
        "verdict": verdict,
        "per_iter_cores": {
            str(k): v for k, v in _TELEMETRY.iter_cores.items()
        },
        "all_cores_count_by_source": dict(
            Counter(r["source"] for r in _TELEMETRY.all_cores)
        ),
        "lbbd_status": status,
        "lbbd_exception": exc_info,
    }
    out_path = Path(args.results_json)
    out_path.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False))
    print(f"[ihs-probe] wrote results → {out_path}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print(f"VERDICT: {verdict['final_verdict']}  ({verdict['reason']})", flush=True)
    print(f"  stage1: {verdict['stage1']['verdict']} {verdict['stage1']['summary']}", flush=True)
    print(f"  stage2 eligible={verdict['stage2']['eligible']} pass={verdict['stage2']['pass']}", flush=True)
    print(f"  cores={verdict['total_cores']} iters={verdict['total_iters_observed']}", flush=True)
    print("=" * 70, flush=True)

    return 0 if verdict["final_verdict"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())

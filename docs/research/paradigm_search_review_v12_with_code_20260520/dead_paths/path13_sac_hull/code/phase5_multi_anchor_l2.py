"""SAC-Hull Phase 5 — multi-anchor campaign with L2 enabled.

GO: 任一 non-corner anchor certified FEASIBLE / INFEASIBLE
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


ANCHORS = [
    (27, 15, 22, 28, "interior_22_28"),
    (27, 15, 10, 10, "interior_10_10"),
    (27, 15, 44, 30, "interior_44_30"),
    (27, 15, 15, 40, "interior_15_40"),
    (27, 15, 0, 0, "corner_0_0_NEGATIVE"),
    (10, 10, 25, 25, "small_10x10"),
    (15, 10, 22, 28, "small_15x10"),
    (15, 15, 22, 28, "small_15x15"),
]


def run_one(ghost_w, ghost_h, ax, ay, label, max_iter=5):
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_ABSTRACT_ROUTING_LAYER"] = "1"
    os.environ["EXACT_B1_ABSTRACT_ROUTING_SECONDS"] = "10"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC_MAX_PER_ITER"] = "2"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)
    print(f"\n>>> {label}: {ghost_w}×{ghost_h} ({ax},{ay}) max_iter={max_iter}", flush=True)
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    try:
        status, _ = run_benders_for_ghost_rect(
            ghost_w=ghost_w, ghost_h=ghost_h,
            max_iterations=max_iter,
            project_root=Path("."),
            solve_mode="certified_exact",
            master_seconds=180.0,
            binding_seconds=30.0,
            routing_seconds=60.0,
            flow_seconds=10.0,
            campaign=None,
            session=None,
            disable_master_warm_start=True,
        )
    except Exception as exc:
        print(f"    ERROR: {exc}", flush=True)
        return label, "ERROR", time.perf_counter() - t0
    elapsed = time.perf_counter() - t0
    print(f"    {label}: {status} in {elapsed:.1f}s", flush=True)
    return label, status, elapsed


def main() -> int:
    print("=== SAC-Hull Phase 5 — multi-anchor verdict (L2 enabled) ===")
    results = [run_one(*cfg) for cfg in ANCHORS]
    print("\n=== Phase 5 SAC-L2 summary ===")
    for label, status, elapsed in results:
        print(f"  {label:30s} {status:15s} {elapsed:7.1f}s")
    if any(r[1] == "CERTIFIED" for r in results):
        print(">>> ✅ SAC-Hull L2 BREAKTHROUGH")
        return 0
    print(">>> 🟡 multi-anchor 仍未拿 certified")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""RAB-SEP Phase 5 — multi-anchor verdict campaign.

跑 4 个 non-corner 27×15 anchor + (0,0) corner negative control + 4 small candidate.

每 anchor max_iter=5 (省时间, 看 cert convergence trajectory).

GO 条件 (任一满足):
- ≥ 1 non-corner anchor → CERTIFIED
- 至少 1 anchor empty_owners monotonic decrease ≥ 50%
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
    (20, 10, 22, 28, "small_20x10"),
    (15, 15, 22, 28, "small_15x15"),
]


def run_one(ghost_w, ghost_h, ax, ay, label, max_iter=5):
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_ROUTING_AWARE_BINDING"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    print(f"\n>>> ANCHOR {label}: {ghost_w}×{ghost_h} ({ax},{ay}) max_iter={max_iter}", flush=True)
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    try:
        status, _ = run_benders_for_ghost_rect(
            ghost_w=ghost_w, ghost_h=ghost_h,
            max_iterations=max_iter,
            project_root=Path("."),
            solve_mode="certified_exact",
            master_seconds=120.0,
            binding_seconds=30.0,
            routing_seconds=60.0,
            flow_seconds=10.0,
            campaign=None,
            session=None,
            disable_master_warm_start=True,
        )
    except Exception as exc:
        print(f"    ERROR: {exc}")
        return label, "ERROR", time.perf_counter() - t0
    elapsed = time.perf_counter() - t0
    print(f"    {label}: {status} in {elapsed:.1f}s", flush=True)
    return label, status, elapsed


def main() -> int:
    for k in (
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE",
    ):
        os.environ.pop(k, None)

    print("=== RAB-SEP Phase 5 — multi-anchor verdict campaign ===")
    results = []
    for cfg in ANCHORS:
        ghost_w, ghost_h, ax, ay, label = cfg
        results.append(run_one(ghost_w, ghost_h, ax, ay, label))

    print("\n=== Phase 5 summary ===")
    for label, status, elapsed in results:
        print(f"  {label:30s} {status:15s} {elapsed:7.1f}s")

    certified = [r for r in results if r[1] in ("CERTIFIED", "INFEASIBLE")]
    print(f"\n{len(certified)}/{len(results)} certified")
    if any(r[1] == "CERTIFIED" for r in results):
        print(">>> ✅ at least one anchor FEASIBLE — RAB-SEP BREAKTHROUGH")
        return 0
    print(">>> 🟡 no FEASIBLE — paradigm 没 break-through")
    return 1


if __name__ == "__main__":
    sys.exit(main())

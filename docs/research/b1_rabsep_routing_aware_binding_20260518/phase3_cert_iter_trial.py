"""RAB-SEP Phase 3 — cert-based iter trial.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_ROUTING_AWARE_BINDING=1

期望: 10 iter 内
- master 加 cert cut 后给 routing-aware-er layout (empty owners 减少)
- 某 iter binding FEASIBLE → routing precheck clean → certified

GO 条件: certified FEASIBLE
Structural GO: master 持续 progress, empty owners 单调减少, cert core p90 ≤ 60
NO-GO: master UNKNOWN 或 cert core 持续 > 80 不收敛
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_ROUTING_AWARE_BINDING"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE",
    ):
        os.environ.pop(k, None)

    print("=== RAB-SEP Phase 3 — cert-based iter trial ===")
    print("27×15 anchor (22,28), max_iter=10")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=10,
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
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 3 trial → {status} in {elapsed:.1f}s ===")
    if status == "CERTIFIED":
        print(">>> ✅ certified FEASIBLE — RAB-SEP BREAKTHROUGH")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ certified INFEASIBLE")
        return 0
    print(f">>> {status}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

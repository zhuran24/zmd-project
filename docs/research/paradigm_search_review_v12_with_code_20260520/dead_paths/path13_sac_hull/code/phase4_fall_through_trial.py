"""SAC-Hull Phase 4 — fall-through trial.

trajectory 22 → 65 → 7 → 4 → ... 在 4-14 floor 徘徊. paradigm 真减 violations
80%+ 但 floor 不可消. fall-through: 当 violations ≤ K 时不 cut, 进 binding/
routing 真 verifier 看是否真可路由.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_SEPARATOR_HULL_DYNAMIC=1
- EXACT_B1_SEPARATOR_HULL_DYNAMIC_MAX_PER_ITER=2  (累积加快)
- EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH=5  (≤ 5 violations 进 binding)

GO:
- certified FEASIBLE (paradigm 真 break-through)
或
- 进 binding/routing 后 routing INFEASIBLE (paradigm 帮 routing 找 sound INFEASIBLE)
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC"] = "1"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC_MAX_PER_ITER"] = "2"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH"] = "5"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_SEPARATOR_HULL",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print("=== SAC-Hull Phase 4 — fall-through trial (threshold ≤ 5) ===")
    print("27×15 anchor (22,28), max_iter=10, max_per_iter=2, threshold=5")

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=10,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=300.0,
        binding_seconds=30.0,
        routing_seconds=60.0,
        flow_seconds=10.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 4 fall-through trial → {status} in {elapsed:.1f}s ===")
    if status == "CERTIFIED":
        print(">>> ✅ certified FEASIBLE — SAC-Hull paradigm BREAKTHROUGH ✓")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ certified INFEASIBLE — sound verdict")
        return 0
    print(f">>> {status}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

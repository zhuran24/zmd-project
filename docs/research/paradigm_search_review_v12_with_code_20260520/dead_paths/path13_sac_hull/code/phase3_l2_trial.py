"""SAC-Hull Phase 3 trial — L2 abstract routing layer.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_ABSTRACT_ROUTING_LAYER=1
- (Phase 2 dynamic 自动 disable, L2 替之)

GO:
- L2 FEASIBLE on most layouts → 进 binding/routing 真 verifier
- certified FEASIBLE / INFEASIBLE (paradigm break-through)
- 或 L2 不断 INFEASIBLE 加 cut converge
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_ABSTRACT_ROUTING_LAYER"] = "1"
    os.environ["EXACT_B1_ABSTRACT_ROUTING_SECONDS"] = "10"
    os.environ["EXACT_B1_ABSTRACT_ROUTING_MAX_SEPARATORS"] = "64"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC_MAX_PER_ITER"] = "2"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print("=== SAC-Hull Phase 3 — L2 abstract routing layer trial ===")
    print("27×15 anchor (22,28), max_iter=10, L2 seconds=10")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=10,
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
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 3 L2 trial → {status} in {elapsed:.1f}s ===")
    if status == "CERTIFIED":
        print(">>> ✅ certified FEASIBLE — SAC-Hull L2 paradigm BREAKTHROUGH")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ certified INFEASIBLE")
        return 0
    print(f">>> {status}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

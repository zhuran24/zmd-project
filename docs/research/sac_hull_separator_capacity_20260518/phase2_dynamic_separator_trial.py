"""SAC-Hull Phase 2 trial — dynamic separator separation.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_SEPARATOR_HULL_DYNAMIC=1
- (Phase 1 static ghost moat 不开, 完全靠 dynamic axis V/H)

期望: 27×15 anchor (22,28) max_iter=5
- iter 1 master OPTIMAL → oracle 找 violations (Phase 0 已知 22 个) → 加 top-4 cut
- iter 2 master 加 cut 后给新 layout → oracle 找 fewer violations → 加更多 cut
- 收敛: 加 几 iter cut 后 master 出 violation-free layout → 进 binding/routing

GO 标准:
- ≥ 3 cut 加
- master each iter ≤ 60s
- 第 5 iter routing precheck blocked_ports 中位数 ≤ 100, 或直接 routing.solve
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC"] = "1"
    os.environ["EXACT_B1_SEPARATOR_HULL_DYNAMIC_MAX_PER_ITER"] = "1"  # 每 iter 1 cut, 减重
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    # Phase 1 static 不开
    for k in (
        "EXACT_B1_SEPARATOR_HULL",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print("=== SAC-Hull Phase 2 — dynamic separator separation trial ===")
    print("27×15 anchor (22,28), max_iter=5, dynamic axis V/H separation only")

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=5,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=80.0,
        binding_seconds=30.0,
        routing_seconds=60.0,
        flow_seconds=10.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 2 trial → {status} in {elapsed:.1f}s ===")
    if status == "CERTIFIED":
        print(">>> ✅ certified FEASIBLE — SAC-Hull paradigm BREAKTHROUGH")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ certified INFEASIBLE")
        return 0
    print(f">>> {status}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

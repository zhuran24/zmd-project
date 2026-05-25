"""B1 Phase 6 第 2+3 条 + 架构改: routing INFEASIBLE 走 iter continue 真 enumerate.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_BYPASS_ROUTING_PRECHECK=1
- EXACT_B1_SKIP_BINDING_ALT_LOOP=1
- EXACT_B1_DELETION_CORE_CUT=1
- EXACT_B1_ITER_ON_ROUTING_INFEASIBLE=1  ← 新, 改架构

工作流:
- iter 1: master 53s OPTIMAL → routing.solve INFEASIBLE → 加 whole-layout nogood → continue iter 2
- iter 2-N: master 加 cut 后解次优 layout → routing 真跑
- 直到 routing FEASIBLE (certified ✓) 或 master INFEASIBLE (certified ✓) 或 max_iter (UNPROVEN)

期望: 5-10 iter 内拿真 certified verdict.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_BYPASS_ROUTING_PRECHECK"] = "1"
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = "5"  # binding 最多 enumerate 5 alt, 防 Phase 4 卡 42 min
    os.environ["EXACT_B1_DELETION_CORE_CUT"] = "1"
    os.environ["EXACT_B1_ITER_ON_ROUTING_INFEASIBLE"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    print("=== B1 Phase 6 第 2+3 条 + iter 架构改 ===")
    print("27×15 anchor (22,28), max_iter=10, routing INFEASIBLE 走 iter continue")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=10,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=60.0,
        routing_seconds=300.0,
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== 27×15 (22,28) → {status} in {elapsed:.1f}s ===")
    if status == "CERTIFIED":
        print(">>> ✅ certified FEASIBLE — B1 paradigm 通!")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ certified INFEASIBLE — sound verdict")
        return 0
    print(f">>> {status} — 还没收敛")
    return 1


if __name__ == "__main__":
    sys.exit(main())

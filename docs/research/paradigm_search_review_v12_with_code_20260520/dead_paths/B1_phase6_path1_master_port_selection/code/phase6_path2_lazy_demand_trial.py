"""B1 Phase 6 路线 2 (lazy demand cut) 端到端实测.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_LAZY_DEMAND_CUT=1

跑 27×15 anchor (22,28) + max_iter=10 LBBD:
- iter 1: master 53s OPTIMAL → binding 0.1s → routing 反馈 blocked → add lazy cut
- iter 2+: master incremental + 累积 cut, 期望逐渐收敛

verdict:
- FEASIBLE / OPTIMAL → 路线 2 ✅
- 10 iter UNPROVEN → 路线 2 ❌ (cut 不收敛)
- master UNKNOWN → 路线 2 ❌ (cut 累积让 master 解不动)
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_LAZY_DEMAND_CUT"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    print("=== B1 Phase 6 路线 2 lazy demand cut trial ===")
    print("27×15 anchor (22,28), max_iter=10")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=10,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,  # 比 Phase 4 baseline 60s 多, 加 cut 后可能慢点
        binding_seconds=60.0,
        routing_seconds=60.0,
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== 27×15 (22,28) → {status} in {elapsed:.1f}s ===")
    if status in {"FEASIBLE", "OPTIMAL"}:
        print(">>> ✅ 路线 2 GO — 拿到 certified FEASIBLE/OPTIMAL")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ 路线 2 GO — 拿到 certified INFEASIBLE (sound verdict)")
        return 0
    print(f">>> ❌ 路线 2 verdict 死 ({status}) — cut 不收敛或 master 解不动")
    return 1


if __name__ == "__main__":
    sys.exit(main())

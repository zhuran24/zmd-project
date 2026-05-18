"""B1 Phase 6 第 2 条 (deletion-core) 端到端实测.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_DELETION_CORE_CUT=1

routing reject 时, run minimizer 缩 layout → minimal core (~10-30 instances) →
加 instance-level placement_local_nogood. 比 Phase 5 cell_cut + lazy_demand 都
tighter.

预期: master 53s OPTIMAL → routing reject → minimizer ~30s → 加 1 条 tight cut
→ master 加 cut 后再 solve → 10 iter 可能收敛.

收敛 → certified FEASIBLE; 不收敛 → 加第 3 条 routing precheck permissive.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_DELETION_CORE_CUT"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    print("=== B1 Phase 6 第 2 条 deletion-core trial ===")
    print("27×15 anchor (22,28), max_iter=10")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=10,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=60.0,
        routing_seconds=60.0,
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== 27×15 (22,28) → {status} in {elapsed:.1f}s ===")
    if status in {"FEASIBLE", "OPTIMAL", "INFEASIBLE"}:
        print(">>> ✅ 第 2 条 GO — certified verdict")
        return 0
    print(f">>> ❌ 第 2 条 verdict ({status})")
    return 1


if __name__ == "__main__":
    sys.exit(main())

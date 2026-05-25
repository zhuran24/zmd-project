"""B1 Phase 6 第 3 条 (routing precheck permissive) + 第 2 条 (deletion-core) 一起.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_BYPASS_ROUTING_PRECHECK=1  (precheck bypass, routing CP-SAT 真跑)
- EXACT_B1_SKIP_BINDING_ALT_LOOP=1    (Phase 4 卡 42 min 的 binding alt loop disable)
- EXACT_B1_DELETION_CORE_CUT=1        (precheck reject 时缩 core, 这次 bypass 后实际不进 precheck branch, 只 routing.solve)

routing.solve verdict 路径:
- FEASIBLE → certified ✓
- INFEASIBLE → skip binding alt → break → master whole-layout nogood + iter
- TIMEOUT → UNKNOWN
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_BYPASS_ROUTING_PRECHECK"] = "1"
    os.environ["EXACT_B1_SKIP_BINDING_ALT_LOOP"] = "1"
    os.environ["EXACT_B1_DELETION_CORE_CUT"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    print("=== B1 Phase 6 第 2+3 条: bypass precheck + skip binding-alt + deletion-core ===")
    print("27×15 anchor (22,28), max_iter=5 (routing.solve 慢, 不跑 10 iter)")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=5,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=60.0,
        routing_seconds=300.0,  # routing CP-SAT 真跑给充足时间
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== 27×15 (22,28) → {status} in {elapsed:.1f}s ===")
    if status in {"FEASIBLE", "OPTIMAL"}:
        print(">>> ✅ 第 2+3 条 GO — certified FEASIBLE!!")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ 第 2+3 条 GO — certified INFEASIBLE")
        return 0
    print(f">>> ❌ ({status}) — B1 paradigm 全死")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Path 17 D2 Phase 1 LBBD hook trial — single anchor 5 iter.

env-gated D2 separator in benders_loop. 验证:
1. master OPTIMAL each iter (no UNKNOWN)
2. D2 INFEASIBLE 5/5 iter (per Phase 0b 7/7 INFEASIBLE 结果)
3. D2 cut_added per iter (master 真 collapse layout)
4. cut accumulation 不让 master 慢 / UNKNOWN

GO 信号:
- 5/5 iter cut_added=True
- master 全 OPTIMAL no UNKNOWN
- iter wall ≤ 180s each
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_D2_COMMODITY_FLOW"] = "1"
    os.environ["EXACT_B1_D2_FLOW_SECONDS"] = "30"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
        "EXACT_B1_PATCH_ROUTING_CORE",
    ):
        os.environ.pop(k, None)

    print("=== Path 17 D2 Phase 1 — LBBD hook trial ===")
    print("  anchor (22,28), 27×15, max_iter=5, master_seconds=180, D2_seconds=30\n")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=5,
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
    print(f"\n=== Phase 1 trial done: {status} in {elapsed:.1f}s ===")
    return 0 if status in ("CERTIFIED", "UNPROVEN") else 1


if __name__ == "__main__":
    sys.exit(main())

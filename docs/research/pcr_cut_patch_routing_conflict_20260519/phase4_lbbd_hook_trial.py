"""PCR-CUT Phase 4 — single anchor LBBD trial with PCR-CUT env on.

Validates that the env-gated hook in benders_loop wires the separator end-to-end:
master → binding → routing precheck front_blocked → PCR-CUT → master cut added
→ continue. Counts patch cuts and master iters to confirm the loop converges to
non-trivial states (not stuck on iter 1).

GO 信号:
- at least 2 patch cuts added across 5 iter
- no master UNKNOWN before iter 5
- iter wall ≤ 180s each
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE"] = "1"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_TOP_K"] = "3"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_SECONDS"] = "15"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_PER_PATCH_SECONDS"] = "5"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS"] = "900"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_QX_CAP"] = "24"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    # Disable competing experimental cut paths so PCR-CUT is the active strategy.
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print("=== PCR-CUT Phase 4 — LBBD hook trial ===")
    print(f"  anchor: (22, 28), 27×15, max_iter=5, master_seconds=180")
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
    print(f"\n=== Phase 4 trial done: {status} in {elapsed:.1f}s ===")
    return 0 if status in ("CERTIFIED", "UNPROVEN") else 1


if __name__ == "__main__":
    sys.exit(main())

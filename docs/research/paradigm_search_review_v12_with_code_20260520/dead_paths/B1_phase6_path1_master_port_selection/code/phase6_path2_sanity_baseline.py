"""sanity: pose-bool master without any Phase 6 env (路线 1 / 路线 2 都 off).
应跟 Phase 4 baseline 一致 — 53s OPTIMAL.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ.pop("EXACT_USE_PORT_ACTIVE", None)
    os.environ.pop("EXACT_B1_LAZY_DEMAND_CUT", None)
    os.environ.pop("EXACT_B1_PORT_CLEARANCE_HARD", None)
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    print("=== sanity baseline (no Phase 6 env) ===")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=1,
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
    print(f"\n27x15 (22,28) → {status} in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

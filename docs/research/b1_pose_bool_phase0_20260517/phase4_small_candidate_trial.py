"""B1 Phase 4 fallback: 跑小 candidate 验端到端 LBBD certified verdict.

策略: 27×15 master 端通但 routing front_blocked 持续 (master 不知 port direction).
跑小 candidate (geometry 宽松) 验整 LBBD 能给 certified FEASIBLE / INFEASIBLE.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def run_one(ghost_w: int, ghost_h: int, anchor_x: int, anchor_y: int, max_iter: int = 5) -> str:
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{anchor_x},{anchor_y}"
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    print(f"\n>>>>>> {ghost_w}x{ghost_h} anchor ({anchor_x},{anchor_y}) <<<<<<", flush=True)
    status, _solution = run_benders_for_ghost_rect(
        ghost_w=ghost_w, ghost_h=ghost_h,
        max_iterations=max_iter,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=60.0,
        routing_seconds=180.0,
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f">>>>>> {ghost_w}x{ghost_h} ({anchor_x},{anchor_y}) → {status} in {elapsed:.1f}s <<<<<<", flush=True)
    return status


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_PORT_CLEARANCE_HARD"] = "1"  # Phase 5d
    print("=== B1 small candidate end-to-end ===")

    # 候选: 小 candidate, geometry 宽松, port 容易绕路
    candidates = [
        (10, 10, 30, 30),  # area=100, dead center
        (15, 10, 28, 30),  # area=150
        (20, 10, 25, 30),  # area=200
        (15, 15, 28, 28),  # area=225
    ]
    results = {}
    for gw, gh, ax, ay in candidates:
        status = run_one(gw, gh, ax, ay, max_iter=5)
        results[(gw, gh, ax, ay)] = status
        if status == "FEASIBLE":
            print(f"\n!!! end-to-end FEASIBLE @ {gw}x{gh} ({ax},{ay}) !!!")
            break

    print(f"\n=== summary ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    feas = [k for k, v in results.items() if v == "FEASIBLE"]
    if feas:
        print(f"\n>>> 🎯 端到端 FEASIBLE: {feas} <<<")
    else:
        print(f"\n>>> 没 candidate 端到端通 <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

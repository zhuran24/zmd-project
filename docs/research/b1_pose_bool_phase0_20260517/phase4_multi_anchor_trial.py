"""B1 Phase 4: 多 anchor 试 LBBD, 看是不是 (22,28) 这个 anchor 特定 binding 卡.

策略: 27×15 candidate 在几个不同 interior anchor 跑短 LBBD (max_iter=3, 时间限定),
看哪个 anchor 第一 iter binding 直接通 (= 整个端到端 GO).

候选 anchor 选: Phase 0 prototype 验过 OPTIMAL 的 (22,28) + 邻近 interior 位置.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def run_one_anchor(anchor_x: int, anchor_y: int, *, master_seconds: float = 120.0,
                   binding_seconds: float = 60.0, routing_seconds: float = 180.0,
                   max_iter: int = 3) -> str:
    """Run LBBD for one anchor, return final status string."""
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{anchor_x},{anchor_y}"

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    print(f"\n>>>>>> anchor ({anchor_x},{anchor_y}) start <<<<<<", flush=True)
    status, _solution = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=max_iter,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=master_seconds,
        binding_seconds=binding_seconds,
        routing_seconds=routing_seconds,
        flow_seconds=60.0,
        campaign=None,
        session=None,  # 每次 reload session (otherwise cached state 跨 anchor 干扰)
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f">>>>>> anchor ({anchor_x},{anchor_y}) → {status} in {elapsed:.1f}s <<<<<<", flush=True)
    return status


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"

    # Candidate anchors: Phase 0 prototype verified OPTIMAL @ (22,28), (20,28), (18,28).
    # Plus a few more interior positions.
    anchors = [
        (22, 28),  # phase 0 + phase 1 baseline
        (20, 28),
        (18, 28),
        (25, 28),
        (15, 30),
        (10, 25),
    ]

    print(f"=== B1 Phase 4 multi-anchor LBBD trial ===")
    print(f"27×15 candidate, {len(anchors)} anchors, max_iter=3 each")

    results = {}
    for ax, ay in anchors:
        status = run_one_anchor(ax, ay, max_iter=3)
        results[(ax, ay)] = status
        if status in ("FEASIBLE",):
            print(f"\n!!! anchor ({ax},{ay}) FEASIBLE — STOPPING early !!!")
            break

    print(f"\n=== summary ===")
    for k, v in results.items():
        print(f"  anchor {k}: {v}")
    feasible = [k for k, v in results.items() if v == "FEASIBLE"]
    if feasible:
        print(f"\n>>> 🎯 端到端 FEASIBLE anchors: {feasible} <<<")
    else:
        print(f"\n>>> 所有 anchor binding 都没过, 需要别的策略 (port-aware master / hint / 等) <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""B1 Phase 3 verdict trial: full LBBD end-to-end with pose-bool master.

通过 env `EXACT_USE_POSE_BOOL_MASTER=1` + `EXACT_MASTER_GHOST_ANCHOR_FILTER=22,28`
让 outer_search/run_benders_for_ghost_rect 走 direct pose-bool master 路径
跑 27×15 candidate 完整 LBBD (master + binding + routing + cut loop).

Phase 3 GO 信号: candidate 给出明确 verdict (FEASIBLE / INFEASIBLE), 不是
UNKNOWN. coordinate baseline 同 candidate 30 min UNKNOWN.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22)
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--master-seconds", type=float, default=180.0)
    parser.add_argument("--binding-seconds", type=float, default=120.0)
    parser.add_argument("--routing-seconds", type=float, default=300.0)
    parser.add_argument("--max-iterations", type=int, default=10)
    args = parser.parse_args()

    # B1 env flag — must set before importing
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{args.anchor_x},{args.anchor_y}"

    print(f"=== B1 Phase 3 full LBBD trial ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")
    print(f"env: EXACT_USE_POSE_BOOL_MASTER=1, EXACT_MASTER_GHOST_ANCHOR_FILTER={args.anchor_x},{args.anchor_y}")
    print(f"max iter={args.max_iterations}, master={args.master_seconds}s, binding={args.binding_seconds}s, routing={args.routing_seconds}s")

    from src.search.benders_loop import (
        create_exact_search_session,
        run_benders_for_ghost_rect,
    )

    project_root = Path(".")
    t0 = time.perf_counter()
    print(f"[session_create] start (this builds the shared exact_core via build_exact_core — coordinate path, one-time setup) ...", flush=True)
    exact_session = create_exact_search_session(project_root, solve_mode="certified_exact")
    print(f"[session_create] {time.perf_counter()-t0:.1f}s, core_build_seconds={exact_session.core_build_seconds:.1f}s")

    t1 = time.perf_counter()
    print(f"[run_benders] start ...", flush=True)
    status, solution = run_benders_for_ghost_rect(
        ghost_w=args.ghost_w,
        ghost_h=args.ghost_h,
        max_iterations=args.max_iterations,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        flow_seconds=60.0,
        campaign=None,
        session=exact_session,
        disable_master_warm_start=True,  # pose-bool warm_start 没 implement, 跳过
    )
    elapsed = time.perf_counter() - t1

    print(f"\n=== verdict ===")
    print(f"status: {status}")
    print(f"elapsed: {elapsed:.1f}s")
    print(f"total wall: {time.perf_counter()-t0:.1f}s")
    if solution:
        print(f"solution: {len(solution)} keys: {list(solution.keys())[:10]}")

    # Final verdict 判定
    if status == "FEASIBLE":
        print(f"\n>>> 🎯 B1 Phase 3 CERTIFIED FEASIBLE — {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y}) <<<")
    elif status == "INFEASIBLE":
        print(f"\n>>> B1 Phase 3 INFEASIBLE — anchor 不可行 (geometry blocking) — 仍是明确 verdict (非 UNKNOWN) <<<")
    elif status == "UNKNOWN":
        print(f"\n>>> B1 Phase 3 UNKNOWN — LBBD 仍卡在某 stage <<<")
    else:
        print(f"\n>>> B1 Phase 3 other status: {status} <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Step A baseline: 单 anchor (22,28) 27x15 candidate 跑 LBBD, 看 CP-SAT master 多久 verdict.

跳过 outer_search frontier 排序 (avoid 67x6 抢先). 直接 run_benders_for_ghost_rect.

EXACT_MASTER_GHOST_ANCHOR_FILTER="22,28" 限定 anchor.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# anchor filter 必须在 import 前 set
os.environ.setdefault("EXACT_MASTER_GHOST_ANCHOR_FILTER", "22,28")

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.search.benders_loop import run_benders_for_ghost_rect  # noqa: E402


def main() -> int:
    cand_w = int(os.environ.get("POC_GHOST_W", 27))
    cand_h = int(os.environ.get("POC_GHOST_H", 15))
    master_secs = float(os.environ.get("POC_MASTER_SECONDS", 300.0))
    max_iter = int(os.environ.get("POC_MAX_ITER", 2))
    anchor_str = os.environ.get("EXACT_MASTER_GHOST_ANCHOR_FILTER", "?,?")

    print(f"=== Step A baseline ===")
    print(f"candidate: {cand_w}x{cand_h} area={cand_w*cand_h}")
    print(f"anchor_filter: {anchor_str}")
    print(f"master_seconds: {master_secs}")
    print(f"max_iter: {max_iter}")
    print(f"start: {time.strftime('%H:%M:%S')}")
    print(flush=True)

    t0 = time.time()
    try:
        status, summary = run_benders_for_ghost_rect(
            ghost_w=cand_w,
            ghost_h=cand_h,
            max_iterations=max_iter,
            master_seconds=master_secs,
            binding_seconds=30.0,
            routing_seconds=30.0,
            flow_seconds=30.0,
        )
    except Exception as exc:
        wall = time.time() - t0
        print(f"\nEXCEPTION after {wall:.1f}s: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 2

    wall = time.time() - t0
    print(f"\n=== verdict ===")
    print(f"wall: {wall:.1f}s")
    print(f"status: {status}")
    if isinstance(summary, dict):
        ms = summary.get("master_status")
        bi = summary.get("benders_iterations")
        print(f"master_status: {ms}")
        print(f"benders_iterations: {bi}")
        print(f"upstream_anchor_filter_count: {summary.get('upstream_anchor_filter_count')}")
        print(f"reason: {summary.get('reason')}")
        out_path = Path(__file__).parent / "logs" / f"step_a_summary_{cand_w}x{cand_h}_anchor_{anchor_str.replace(',','_')}.json"
        out_path.parent.mkdir(exist_ok=True)
        try:
            with out_path.open("w") as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"summary -> {out_path}")
        except Exception as exc:
            print(f"summary dump failed: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

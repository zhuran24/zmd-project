"""Phase 6.1.5 PoC: 假设 wireless_sink (protocol_storage_box) port 是
a priori clearance over-restriction 唯一来源.

验证: a priori clearance ON + skip storage box port. 27×15 anchor (22,28)
之前 Phase 5b 实测 INFEASIBLE 47s. 如果 PoC 切到 OPTIMAL → 假设成立,
Phase 6 scope 缩窄到 ~150 LOC (只对 wireless_sink 加 port_active +
conditional clearance). 否则需要继续 audit fixed op / boundary_io.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def run_one(ghost_w: int, ghost_h: int, anchor_x: int, anchor_y: int) -> str:
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{anchor_x},{anchor_y}"
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    print(f"\n>>>>>> {ghost_w}x{ghost_h} anchor ({anchor_x},{anchor_y}) <<<<<<", flush=True)
    status, _solution = run_benders_for_ghost_rect(
        ghost_w=ghost_w, ghost_h=ghost_h,
        max_iterations=1,  # 看 master 一次, 不需 LBBD iter
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=300.0,
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
    os.environ["EXACT_B1_PORT_CLEARANCE_HARD"] = "1"
    os.environ["EXACT_B1_PORT_CLEARANCE_SKIP_STORAGE_BOX"] = "1"
    print("=== Phase 6.1.5 PoC: a priori clearance + skip storage box ===")

    # 主目标: 27×15 anchor (22,28) — Phase 5b 实测 INFEASIBLE 47s 的同位置
    candidates = [
        (27, 15, 22, 28),  # 主验证
        (15, 10, 28, 30),  # 之前小 candidate 也 INFEASIBLE 55.3s
    ]
    results = {}
    for gw, gh, ax, ay in candidates:
        status = run_one(gw, gh, ax, ay)
        results[(gw, gh, ax, ay)] = status

    print(f"\n=== summary ===")
    for k, v in results.items():
        marker = "✅ assumption holds" if v in {"FEASIBLE", "OPTIMAL", "UNPROVEN"} else "❌ INFEASIBLE — assumption failed"
        print(f"  {k}: {v}  {marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

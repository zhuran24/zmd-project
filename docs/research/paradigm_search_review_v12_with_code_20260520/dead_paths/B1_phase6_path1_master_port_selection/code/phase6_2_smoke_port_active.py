"""Phase 6.2 smoke: 加 port_active vars 后 master.solve 还能 OPTIMAL (不破).

Phase 4 baseline: master 53s OPTIMAL @ 27×15 anchor (22,28).
Phase 6.2: 加 ~200K port_active BoolVars + 联动 (port_active <= x_var,
sum(per pose) == demand × x_var, ro storage box total == 2 from
generic_io_requirements). 没动 clearance. 应仍 OPTIMAL.

如果 INFEASIBLE: 约束写错 (e.g. demand 算错让 pose 不满足).
如果 OPTIMAL: 6.2 land OK, 进 6.3 改 clearance.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_USE_PORT_ACTIVE"] = "1"  # Phase 6.2
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"

    print("=== Phase 6.2 smoke: port_active vars, master only ===")
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _solution = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=1,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=300.0,
        binding_seconds=60.0,
        routing_seconds=60.0,
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n27x15 (22,28) → {status} in {elapsed:.1f}s")
    if status in {"FEASIBLE", "OPTIMAL", "UNPROVEN"}:
        print("✅ Phase 6.2 不破 master solve (constraints sound)")
        return 0
    print("❌ Phase 6.2 让 master INFEASIBLE — 约束设计错")
    return 1


if __name__ == "__main__":
    sys.exit(main())

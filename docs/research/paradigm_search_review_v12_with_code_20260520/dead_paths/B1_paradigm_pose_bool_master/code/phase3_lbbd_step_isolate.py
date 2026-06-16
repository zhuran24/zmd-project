"""Phase 3.5 isolation: 通过 LBBD 内部 wiring 走 master, 但跳过 _run_certified_exact 直接 master.solve().

目的: 找出 production LBBD 80s INFEASIBLE 跟 Phase 5 53s OPTIMAL 的差异点.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"


def main() -> int:
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import create_exact_search_session

    project_root = Path(".")
    t0 = time.perf_counter()
    exact_session = create_exact_search_session(project_root, solve_mode="certified_exact")
    print(f"[session_create] {time.perf_counter()-t0:.1f}s")

    t1 = time.perf_counter()
    print(f"[master_init] direct ...", flush=True)
    master = MasterPlacementModel(
        list(exact_session.core.source_instances),
        exact_session.core.facility_pools,
        exact_session.core.rules,
        ghost_rect=(27, 15),
        skip_power_coverage=bool(exact_session.core.skip_power_coverage),
        enable_symmetry_breaking=bool(exact_session.core.enable_symmetry_breaking),
        generic_io_requirements=exact_session.core.generic_io_requirements,
        exact_required_pose_optional_counts=dict(
            exact_session.core.exact_required_pose_optional_counts
        ),
        solve_mode="certified_exact",
        ghost_anchor_filter={(22, 28)},
    )
    print(f"[master_init] {time.perf_counter()-t1:.1f}s")
    print(f"  delegate={type(master._coordinate_delegate).__name__}")

    t2 = time.perf_counter()
    master.build()
    print(f"[build] {time.perf_counter()-t2:.1f}s")
    print(f"  pose_bool_stats: {master.build_stats.get('pose_bool_master', {})}")
    print(f"  ghost_rect: {master.build_stats.get('ghost_rect', {})}")

    # 复现 LBBD inner wrapper 调用
    t_ws = time.perf_counter()
    print(f"[warm_start] master.build_exact_candidate_warm_start() ...", flush=True)
    warm_start = master.build_exact_candidate_warm_start()
    print(f"[warm_start] {time.perf_counter()-t_ws:.1f}s, solution_hint size={len(warm_start.get('solution_hint', {}))}")

    t_bpf = time.perf_counter()
    print(f"[boundary_port_precheck] ...", flush=True)
    bpf = master.evaluate_exact_candidate_boundary_port_feasibility()
    print(f"[boundary_port_precheck] {time.perf_counter()-t_bpf:.1f}s, supported={bpf.get('supported')}, screen_pass={bpf.get('screen_pass_anchor_count')}")

    t_diag = time.perf_counter()
    print(f"[mandatory_support_diagnostics] ...", flush=True)
    diag = master.evaluate_exact_candidate_mandatory_support_diagnostics()
    print(f"[mandatory_support_diagnostics] {time.perf_counter()-t_diag:.1f}s, unsupported_groups={len(diag.get('groups', []))}")

    t3 = time.perf_counter()
    print(f"[solve] direct master.solve() no hint ...", flush=True)
    status = master.solve(time_limit_seconds=180.0)
    elapsed = time.perf_counter() - t3
    from ortools.sat.python import cp_model
    name = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN"}.get(int(status), str(status))
    print(f"\n=== verdict ===")
    print(f"status: {name} in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

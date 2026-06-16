"""B1 Phase 5 verdict trial: production pose-bool master + binding subproblem.

通过 env `EXACT_USE_POSE_BOOL_MASTER=1` 让 MasterPlacementModel 创建
PoseBoolExactMasterDelegate (跟 CoordinateExactMasterDelegate 平行).
跑 27×15 anchor (22,28) — 跟 Phase 0 standalone prototype 同 anchor.

Phase 5 GO 信号: master.solve < 60s OPTIMAL (类比 Phase 0 prototype 53s).

注意: 这是 production master, 不是 standalone prototype. 通过 master_model.py 真路径
验证 B1 paradigm 在生产代码下也工作.
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
    parser.add_argument("--time-limit", type=float, default=180.0)
    args = parser.parse_args()

    # B1 env flag — 关键: must set BEFORE importing MasterPlacementModel
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{args.anchor_x},{args.anchor_y}"

    print(f"=== B1 Phase 5 production trial ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")
    print(f"env: EXACT_USE_POSE_BOOL_MASTER=1, EXACT_MASTER_GHOST_ANCHOR_FILTER={args.anchor_x},{args.anchor_y}")

    from src.models.master_model import (
        MasterPlacementModel,
        infer_exact_required_pose_optional_counts,
        load_generic_io_requirements_artifact,
        load_project_data,
    )

    t0 = time.perf_counter()
    instances, pools, rules = load_project_data(Path("."), "certified_exact")
    generic = load_generic_io_requirements_artifact(Path("."))
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print(f"[load] {time.perf_counter()-t0:.1f}s")

    # Direct instantiation (跳 build_exact_core/from_exact_core share-core 机制
    # — 那是 coordinate-specific proto sharing, pose-bool delegate 走独立 build).
    t1 = time.perf_counter()
    anchor_filter = {(args.anchor_x, args.anchor_y)}
    m = MasterPlacementModel(
        instances, pools, rules,
        ghost_rect=(args.ghost_w, args.ghost_h),
        skip_power_coverage=True,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts,
        solve_mode="certified_exact",
        ghost_anchor_filter=anchor_filter,
    )
    print(f"[master_init] {time.perf_counter()-t1:.1f}s")
    print(f"  exact_mode={m.exact_mode}")
    print(f"  delegate type={type(m._coordinate_delegate).__name__ if m._coordinate_delegate else 'None'}")
    print(f"  master_representation={m.build_stats.get('master_representation', '?')}")

    t3 = time.perf_counter()
    print(f"[build] master.build() ...", flush=True)
    m.build()
    print(f"[build] {time.perf_counter()-t3:.1f}s")
    if "pose_bool_master" in m.build_stats:
        pbm = m.build_stats["pose_bool_master"]
        print(f"  pose_bool_master stats: {pbm}")

    t4 = time.perf_counter()
    print(f"[solve] master.solve(time_limit={args.time_limit}) ...", flush=True)
    status = m.solve(time_limit_seconds=args.time_limit)
    elapsed = time.perf_counter() - t4

    from ortools.sat.python import cp_model as _cp_model
    status_name = {
        _cp_model.OPTIMAL: "OPTIMAL", _cp_model.FEASIBLE: "FEASIBLE",
        _cp_model.INFEASIBLE: "INFEASIBLE", _cp_model.UNKNOWN: "UNKNOWN",
    }.get(int(status), str(status))
    feasible = int(status) in (_cp_model.OPTIMAL, _cp_model.FEASIBLE)

    print(f"\n=== verdict ===")
    print(f"master status: {status_name}, solve elapsed: {elapsed:.1f}s")
    if not feasible:
        print(f">>> B1 Phase 5 master NO-GO: {status_name} <<<")
        return 0

    solution = m.extract_solution()
    print(f"extract_solution: {len(solution)} instances")

    # binding check
    from src.models.binding_subproblem import PortBindingModel
    t5 = time.perf_counter()
    binding_model = PortBindingModel(
        solution, m.facility_pools, m.source_instances, project_root=Path("."),
    )
    binding_model.build()
    binding_status = binding_model.solve(time_limit_seconds=120.0)
    print(f"binding: {binding_status} in {time.perf_counter()-t5:.1f}s")

    if elapsed < 60 and feasible and binding_status == "FEASIBLE":
        print(f"\n>>> 🎯 B1 Phase 5 GO — production pose-bool master {elapsed:.1f}s {status_name} + binding FEASIBLE <<<")
    else:
        print(f"\n>>> B1 Phase 5 partial — master {status_name} {elapsed:.1f}s, binding {binding_status} <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

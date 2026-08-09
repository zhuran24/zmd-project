"""Step B prototype 2: 直接调 master.solve, 详细打印 build_stats 看为啥 0.0s."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.models.master_model import (  # noqa: E402
    MasterPlacementModel,
    infer_exact_required_pose_optional_counts,
    load_generic_io_requirements_artifact,
    load_project_data,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=0)
    parser.add_argument("--anchor-y", type=int, default=0)
    parser.add_argument("--time-limit", type=float, default=120.0)
    parser.add_argument("--skip-power", action="store_true")
    parser.add_argument("--no-anchor-filter", action="store_true",
                        help="不传 ghost_anchor_filter 给 from_exact_core (default 传)")
    args = parser.parse_args()

    project_root = Path(".")
    print(f"=== minimum + master direct PoC ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")
    print(f"skip_power={args.skip_power} no_anchor_filter={args.no_anchor_filter}")

    t0 = time.perf_counter()
    print(f"[load] project data ...", flush=True)
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print(f"[load] {time.perf_counter()-t0:.1f}s")

    t1 = time.perf_counter()
    print(f"[build] master exact core (skip_power={args.skip_power}) ...", flush=True)
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules,
        skip_power_coverage=args.skip_power,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts,
    )
    print(f"[core] {time.perf_counter()-t1:.1f}s")

    t2 = time.perf_counter()
    if args.no_anchor_filter:
        m = MasterPlacementModel.from_exact_core(core, ghost_rect=(args.ghost_w, args.ghost_h))
        print(f"[overlay] no anchor filter")
    else:
        anchor_filter = frozenset([(args.anchor_x, args.anchor_y)])
        m = MasterPlacementModel.from_exact_core(
            core, ghost_rect=(args.ghost_w, args.ghost_h),
            ghost_anchor_filter=anchor_filter,
        )
        print(f"[overlay] anchor filter = {anchor_filter}")
    print(f"[overlay] {time.perf_counter()-t2:.1f}s")

    t_finalize = time.perf_counter()
    m.build()
    print(f"[finalize] m.build() {time.perf_counter()-t_finalize:.1f}s")

    print(f"[build_stats] {json.dumps({k:v for k,v in m.build_stats.items() if isinstance(v,(int,float,str,bool,type(None)))}, indent=2, default=str)[:800]}")

    print(f"[solve] m.solve(time_limit={args.time_limit}) ...", flush=True)
    t3 = time.perf_counter()
    status_int = m.solve(time_limit_seconds=args.time_limit)
    elapsed = time.perf_counter() - t3

    from ortools.sat.python import cp_model
    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(status_int, f"raw({status_int})")

    last_solve = m.build_stats.get("last_solve", {})
    print(f"\n=== verdict ===")
    print(f"status: {status_name}")
    print(f"elapsed (script): {elapsed:.3f}s")
    print(f"build_stats.last_solve: {json.dumps(last_solve, indent=2, default=str)[:1500]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Probe existing pose-bool path in master_model.py.

走 exploratory mode (避开 coordinate_delegate), 给定 ghost_rect, 看
master.build()+solve() 时间跟 standalone prototype 是否一致 — 验证
master_model.py 现有的 _create_variables / _add_set_packing_constraints /
_add_power_coverage_constraints 等 pose-bool path 跟 prototype 数学等价.

注意: exploratory mode 跟 certified_exact 数学语义不同 (有 caps), 但 pose-bool
表达形式相同, 这里只验 "现有 pose-bool path 真能 build + solve 不卡".
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ortools.sat.python import cp_model  # noqa: E402

from src.models.master_model import (  # noqa: E402
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--time-limit", type=float, default=180.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    project_root = Path(".")
    print(f"=== probe existing pose-bool path (exploratory mode + ghost_rect) ===")
    print(f"ghost {args.ghost_w}x{args.ghost_h}")

    t_load = time.perf_counter()
    instances, pools, rules = load_project_data(project_root, "exploratory")
    generic = load_generic_io_requirements_artifact(project_root)
    print(f"[load] {time.perf_counter()-t_load:.1f}s")

    t0 = time.perf_counter()
    print("[init] MasterPlacementModel exploratory ...", flush=True)
    m = MasterPlacementModel(
        instances, pools, rules,
        solve_mode="exploratory",
        ghost_rect=(args.ghost_w, args.ghost_h),
        generic_io_requirements=generic,
    )
    print(f"[init] {time.perf_counter()-t0:.1f}s")
    print(f"  exact_mode={m.exact_mode}, coordinate_delegate={'set' if m._coordinate_delegate else 'None'}")
    print(f"  mandatory groups: {len(m._mandatory_groups)}")

    t1 = time.perf_counter()
    print("[build] master.build() ...", flush=True)
    m.build()
    build_secs = time.perf_counter() - t1
    print(f"[build] {build_secs:.1f}s")
    print(f"  z_vars groups: {len(m.z_vars)}")
    print(f"  optional_pose_vars templates: {list(m.optional_pose_vars.keys())}")
    print(f"  u_vars (ghost anchor placements): {len(m.u_vars)}")
    print(f"  build_stats keys: {list(m.build_stats.keys())[:10]}")

    t2 = time.perf_counter()
    print(f"[solve] master.solve(time_limit={args.time_limit}, workers={args.workers}) ...", flush=True)
    # solve signature 不接 num_search_workers, 它通过 master_search_profile / 内部默认走
    status = m.solve(time_limit_seconds=args.time_limit)
    elapsed = time.perf_counter() - t2

    print(f"\n=== verdict ===")
    print(f"status: {status}")
    print(f"elapsed: {elapsed:.1f}s")
    print(f"total wall: {time.perf_counter()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

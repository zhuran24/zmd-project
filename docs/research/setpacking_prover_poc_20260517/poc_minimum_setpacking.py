"""Step B prototype 1: minimum set-packing model (CP-SAT) — bare bones.

只含三类约束:
  1. demand: sum_p x_{g,p} = d_g (每 group g 必须放 d_g 个)
  2. cell exclusivity: sum_overlap_pose x_{g,p} <= 1 (每 cell 最多 1 pose)
  3. ghost forbidden: x_{g,p} = 0 if pose p covers anchor B

跳过: power_coverage, port_binding, connector, boundary_port, LBBD cuts...

目的: 看 CP-SAT 在剥光的 minimum 上 single anchor 多快 verdict.
如果 minimum 也 UNKNOWN → 问题在 set-packing 核心难度, 不在 master 多余 constraint.
如果 minimum INFEASIBLE fast → 问题在 master 多余 constraint 干扰 CP-SAT.

跑 27x15 anchor (22,28) interior.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ortools.sat.python import cp_model  # noqa: E402

from src.models.master_model import (  # noqa: E402
    MasterPlacementModel,
    infer_exact_required_pose_optional_counts,
    load_generic_io_requirements_artifact,
    load_project_data,
)


def build_mandatory_groups(model: MasterPlacementModel):
    delegate = model._coordinate_delegate
    groups = []
    for group in model._mandatory_groups:
        group_id = str(group["group_id"])
        tpl = str(group["facility_type"])
        required = int(len(delegate.mandatory_slots.get(group_id, [])))
        if required <= 0:
            required = int(len(list(group.get("instance_ids", []))))
        if required <= 0:
            continue
        tpl_poses = delegate._template_pose_tuple_by_idx.get(tpl, {})
        pose_cells = []
        for pose_idx in tpl_poses:
            cells = model._pose_cells(tpl, int(pose_idx))
            pose_cells.append([(int(c[0]), int(c[1])) for c in cells])
        groups.append({"group_id": group_id, "demand": required, "pose_cells": pose_cells})
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22)
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    project_root = Path(".")
    print(f"=== minimum set-packing PoC ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")
    print(f"time_limit={args.time_limit}s workers={args.workers}")

    t0 = time.perf_counter()
    print(f"[load] project data ...", flush=True)
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print(f"[load] {time.perf_counter()-t0:.1f}s")

    t1 = time.perf_counter()
    print(f"[build] master exact core ...", flush=True)
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts)
    m = MasterPlacementModel.from_exact_core(core, ghost_rect=(args.ghost_w, args.ghost_h))
    groups = build_mandatory_groups(m)
    print(f"[build] {time.perf_counter()-t1:.1f}s, {len(groups)} groups, total demand={sum(g['demand'] for g in groups)}")

    # 构造 forbidden cells (ghost rect)
    forbidden: Set[Tuple[int, int]] = {
        (args.anchor_x + dx, args.anchor_y + dy)
        for dx in range(args.ghost_w) for dy in range(args.ghost_h)
    }
    print(f"[ghost] forbidden cells={len(forbidden)}")

    # 过滤 feasible poses (不碰 forbidden, 不出 grid)
    grid_w = int(rules["globals"]["grid"]["width"])
    grid_h = int(rules["globals"]["grid"]["height"])
    feas_groups = []
    total_poses = 0
    for g in groups:
        feas = []
        for cells in g["pose_cells"]:
            if any(not (0 <= c[0] < grid_w and 0 <= c[1] < grid_h) for c in cells):
                continue
            if any((c[0], c[1]) in forbidden for c in cells):
                continue
            feas.append(cells)
        if not feas:
            print(f"  group {g['group_id']} has 0 feasible poses → trivial INFEASIBLE")
            return 0
        feas_groups.append({"group_id": g["group_id"], "demand": g["demand"], "poses": feas})
        total_poses += len(feas)
    print(f"[filter] {total_poses} total feasible poses across {len(feas_groups)} groups")

    # build CP-SAT minimum
    t2 = time.perf_counter()
    print(f"[cpsat] building model ...", flush=True)
    model = cp_model.CpModel()
    x_vars: Dict[Tuple[int, int], object] = {}
    cell_poses: Dict[Tuple[int, int], List[object]] = {}
    for gi, g in enumerate(feas_groups):
        group_vars = []
        for pi, cells in enumerate(g["poses"]):
            v = model.NewBoolVar(f"x_{gi}_{pi}")
            x_vars[(gi, pi)] = v
            group_vars.append(v)
            for c in cells:
                cell_poses.setdefault(c, []).append(v)
        # demand
        model.Add(sum(group_vars) == g["demand"])

    # cell exclusivity
    for c, vars_in_cell in cell_poses.items():
        if len(vars_in_cell) > 1:
            model.AddAtMostOne(vars_in_cell)
    print(f"[cpsat] built in {time.perf_counter()-t2:.1f}s, {len(x_vars)} bool vars, "
          f"{len(cell_poses)} cells with overlap")

    # solve
    t3 = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(args.time_limit)
    solver.parameters.num_search_workers = int(args.workers)
    solver.parameters.log_search_progress = False
    print(f"[cpsat] solving (time={args.time_limit}s, workers={args.workers}) ...", flush=True)
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t3

    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(status, f"raw({status})")

    print(f"\n=== verdict ===")
    print(f"status: {status_name}")
    print(f"elapsed: {elapsed:.1f}s")
    print(f"branches: {solver.NumBranches()}")
    print(f"conflicts: {solver.NumConflicts()}")
    print(f"objective_value: {solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 'n/a'}")
    print(f"best_obj_bound: {solver.BestObjectiveBound() if status != cp_model.MODEL_INVALID else 'n/a'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

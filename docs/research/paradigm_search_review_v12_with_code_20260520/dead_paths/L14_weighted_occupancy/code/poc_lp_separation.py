"""L14 PoC step 2: LP separation 找最优 cell-level λ.

dual LP (per fixed ghost forbidden mask B):
    max sum_g d_g μ_g
    s.t.
      sum_c λ_c = 1
      λ_c >= 0  for c in C\\B
      μ_g <= sum_{c in F(p)} λ_c   for each g, p in P_g(B)

如果 optimal value > 1, 则存在加权 occupancy 不等式证明 ghost B 下 infeasible.

PoC 用 cutting plane (separation) 而不是一次性塞 303k constraints:
1. 从少量 pose constraint 开始 (每 group 几个 pose)
2. 解 LP
3. 对每个 group 找 weight-minimizing pose (argmin)
4. 如果 argmin pose 违反 μ_g <= score, 加进 LP, 重解
5. 收敛后报告 LP value
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.linear_solver import pywraplp

from src.models.master_model import (
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


def filter_feasible_poses(groups, forbidden: set):
    """对每个 group, 只保留不碰 forbidden 的 pose."""
    out = []
    for g in groups:
        feasible = [cells for cells in g["pose_cells"]
                    if not any((cx, cy) in forbidden for cx, cy in cells)]
        if not feasible:
            return None  # group 无合法 pose, 直接 infeasible
        out.append({"group_id": g["group_id"], "demand": g["demand"], "feasible_poses": feasible})
    return out


def lp_separation(
    grid: Tuple[int, int],
    forbidden: set,
    groups,
    max_iter: int = 30,
    pose_per_group_init: int = 3,
    margin_tol: float = 1e-7,
    verbose: bool = False,
) -> Dict:
    """Cutting-plane LP separation. Returns dict with:
      - status: "solved" | "max_iter" | "trivial_infeasible" | "infeasible"
      - lp_objective: float
      - iterations: int
      - violating_added: list per iter
    """
    grid_w, grid_h = grid
    feas = filter_feasible_poses(groups, forbidden)
    if feas is None:
        return {"status": "trivial_infeasible", "lp_objective": float("inf"), "iterations": 0}

    # 初始 constraint set: 每 group 前 N pose (按 feasible_poses 顺序, 应该 random shuffle 更鲁棒但 PoC simple)
    active_constraints = []  # (group_idx, pose_cells)
    for gi, g in enumerate(feas):
        for cells in g["feasible_poses"][:pose_per_group_init]:
            active_constraints.append((gi, cells))

    cells_universe = [(x, y) for x in range(grid_w) for y in range(grid_h) if (x, y) not in forbidden]

    for it in range(max_iter):
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            return {"status": "solver_unavailable", "lp_objective": 0.0, "iterations": it}

        # variables
        lam = {}
        for c in cells_universe:
            lam[c] = solver.NumVar(0.0, solver.infinity(), f"λ_{c[0]}_{c[1]}")
        mu = []
        for gi, g in enumerate(feas):
            mu.append(solver.NumVar(-solver.infinity(), solver.infinity(), f"μ_{gi}"))

        # normalization: sum λ = 1
        norm = solver.Constraint(1.0, 1.0)
        for c in cells_universe:
            norm.SetCoefficient(lam[c], 1.0)

        # active per-pose constraints: μ_g <= sum_{c in F(p)} λ_c
        # 写成: sum λ_c - μ_g >= 0
        for gi, pose_cells in active_constraints:
            ct = solver.Constraint(0.0, solver.infinity())
            ct.SetCoefficient(mu[gi], -1.0)
            for c in pose_cells:
                ct.SetCoefficient(lam[c], 1.0)

        # objective: max sum_g d_g μ_g
        obj = solver.Objective()
        for gi, g in enumerate(feas):
            obj.SetCoefficient(mu[gi], float(g["demand"]))
        obj.SetMaximization()

        status = solver.Solve()
        if status != pywraplp.Solver.OPTIMAL:
            return {"status": f"lp_status_{status}", "lp_objective": 0.0, "iterations": it}

        lp_val = solver.Objective().Value()
        lam_vals = {c: lam[c].solution_value() for c in cells_universe}
        mu_vals = [mu[gi].solution_value() for gi in range(len(feas))]

        # separation: 对每 group 找 weight-min pose
        violations = []
        for gi, g in enumerate(feas):
            best = None
            best_cells = None
            for cells in g["feasible_poses"]:
                s = sum(lam_vals.get(c, 0.0) for c in cells)
                if best is None or s < best:
                    best = s
                    best_cells = cells
            # μ_g <= sum λ_c ?  if μ_g - sum > tol then violated
            if mu_vals[gi] - best > margin_tol:
                violations.append((gi, best_cells, mu_vals[gi] - best))

        if verbose:
            print(f"    iter {it}: lp={lp_val:.6f}, μ={[round(v,4) for v in mu_vals]}, "
                  f"violations={len(violations)}")

        if not violations:
            return {
                "status": "solved",
                "lp_objective": lp_val,
                "iterations": it + 1,
                "lp_certifies": lp_val > 1.0 + margin_tol,
                "mu_values": [float(v) for v in mu_vals],
                "lambda_nonzero_count": sum(1 for v in lam_vals.values() if v > 1e-9),
            }

        # 加最 violating 的 pose 进 active (每 group 最多加 1 个 violating, 最 violating 的)
        for gi, cells, _vio in violations:
            active_constraints.append((gi, cells))

    return {"status": "max_iter", "lp_objective": lp_val, "iterations": max_iter}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22, help="default = blueprint exact match")
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--max-iter", type=int, default=30)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    project_root = Path(".")
    print(f"[load] project data ... ", end="", flush=True)
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print("OK")
    print(f"[build] exact core ... ", end="", flush=True)
    t0 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts)
    print(f"OK ({time.perf_counter()-t0:.1f}s)")
    m = MasterPlacementModel.from_exact_core(core, ghost_rect=(args.ghost_w, args.ghost_h))
    groups = build_mandatory_groups(m)
    print(f"[groups] {len(groups)} groups, "
          f"total demand={sum(g['demand'] for g in groups)}, "
          f"total pose entries={sum(len(g['pose_cells']) for g in groups)}")

    anchor = (args.anchor_x, args.anchor_y)
    forbidden = {(anchor[0] + dx, anchor[1] + dy)
                 for dx in range(args.ghost_w) for dy in range(args.ghost_h)}
    print(f"\n[LP] ghost {args.ghost_w}x{args.ghost_h} @ anchor {anchor}, forbidden cells={len(forbidden)}")
    t0 = time.perf_counter()
    result = lp_separation((70, 70), forbidden, groups,
                           max_iter=args.max_iter, verbose=args.verbose)
    elapsed = time.perf_counter() - t0
    print(f"\n[LP result] elapsed={elapsed:.1f}s, status={result['status']}, "
          f"iterations={result.get('iterations')}, lp_objective={result.get('lp_objective'):.6f}")
    if result.get("lp_certifies"):
        print(f"  ✓ LP > 1 certifies INFEASIBLE under weighted occupancy family")
    elif result["status"] == "solved":
        print(f"  ✗ LP <= 1, weighted occupancy 数学不可达 cover 这个 anchor")
    if "mu_values" in result:
        print(f"  μ values: {[round(v,3) for v in result['mu_values']]}")
        print(f"  λ nonzero count: {result['lambda_nonzero_count']}")


if __name__ == "__main__":
    main()

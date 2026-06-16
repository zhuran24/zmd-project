"""B1 Phase 0: pose-bool master + power_coverage standalone prototype.

跟 Step B 的 minimum set-packing PoC (poc_minimum_setpacking.py) 比, 增加:
  - residual_optional 'power_pole' 的 pose-bool vars (y_{p}), demand 不固定
  - required_optional 'protocol_storage_box' 的 pose-bool vars (1 slot demand=1)
  - power_coverage 约束: 每 mandatory powered pose 必须有 ≥ 1 coverer pole pose 被选

不包括 (在 Benders subproblem 处理):
  - port_binding
  - boundary_port_feasibility (master 内只有 mandatory boundary_storage_port 几何放置)
  - routing
  - flow

目的: 验证 pose-bool form 加 power_coverage 这一层后是否仍快.

Step B baseline: 27×15 anchor (22,28) interior, minimum form 7.2s FEASIBLE.
B1 verdict gate: 加 power_coverage 后能否 < 60s feasible.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22)
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-power", action="store_true",
                        help="跳 power_coverage (回到 Step B 对照, 验证 prototype harness 本身没引入 regression)")
    args = parser.parse_args()

    project_root = Path(".")
    print(f"=== B1 Phase 0 pose-bool + power_coverage PoC ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")
    print(f"time_limit={args.time_limit}s workers={args.workers} skip_power={args.skip_power}")

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
    delegate = m._coordinate_delegate
    grid_w = int(rules["globals"]["grid"]["width"])
    grid_h = int(rules["globals"]["grid"]["height"])
    print(f"[build] {time.perf_counter()-t1:.1f}s, grid={grid_w}x{grid_h}")

    forbidden: Set[Tuple[int, int]] = {
        (args.anchor_x + dx, args.anchor_y + dy)
        for dx in range(args.ghost_w) for dy in range(args.ghost_h)
    }
    print(f"[ghost] forbidden cells={len(forbidden)}")

    # ============ 准备 mandatory groups (含 powered 标记) ============
    mandatory_groups = []
    for group in m._mandatory_groups:
        gid = str(group["group_id"])
        tpl = str(group["facility_type"])
        demand = len(delegate.mandatory_slots.get(gid, []))
        if demand <= 0:
            demand = len(list(group.get("instance_ids", [])))
        if demand <= 0:
            continue
        is_powered = (tpl in m._powered_templates and tpl != "power_pole")
        tpl_poses = delegate._template_pose_tuple_by_idx.get(tpl, {})
        feas_poses = []  # list of (orig_pose_idx, cells)
        for pose_idx in sorted(tpl_poses.keys()):
            cells = m._pose_cells(tpl, int(pose_idx))
            cells_tup = [(int(c[0]), int(c[1])) for c in cells]
            if any(not (0 <= c[0] < grid_w and 0 <= c[1] < grid_h) for c in cells_tup):
                continue
            if any(c in forbidden for c in cells_tup):
                continue
            feas_poses.append((int(pose_idx), cells_tup))
        if not feas_poses:
            print(f"  [INFEASIBLE] group {gid} 0 feasible pose")
            return 0
        mandatory_groups.append({
            "group_id": gid,
            "template": tpl,
            "demand": demand,
            "is_powered": is_powered,
            "feas_poses": feas_poses,  # list of (pose_idx, cells)
        })

    # ============ 准备 required_optional protocol_storage_box (1 slot demand=1) ============
    ro_groups = []
    for tpl, slots in delegate.required_optional_slots.items():
        demand = len(slots)
        if demand <= 0:
            continue
        is_powered = (tpl in m._powered_templates and tpl != "power_pole")
        tpl_poses = delegate._template_pose_tuple_by_idx.get(tpl, {})
        feas_poses = []
        for pose_idx in sorted(tpl_poses.keys()):
            cells = m._pose_cells(tpl, int(pose_idx))
            cells_tup = [(int(c[0]), int(c[1])) for c in cells]
            if any(not (0 <= c[0] < grid_w and 0 <= c[1] < grid_h) for c in cells_tup):
                continue
            if any(c in forbidden for c in cells_tup):
                continue
            feas_poses.append((int(pose_idx), cells_tup))
        if not feas_poses:
            print(f"  [INFEASIBLE] required_optional {tpl} 0 feasible pose")
            return 0
        ro_groups.append({
            "group_id": f"ro::{tpl}",
            "template": tpl,
            "demand": demand,
            "is_powered": is_powered,
            "feas_poses": feas_poses,
        })

    # ============ 准备 pole pool (residual_optional, no demand fix) ============
    # pole pose 是 facility_pools["power_pole"] 全集 (anchor cell 上 2x2)
    pole_pool = m.facility_pools.get("power_pole", [])
    pole_feas: List[Tuple[int, List[Tuple[int, int]], List[Tuple[int, int]]]] = []
    # list of (pose_idx, occupied_cells, coverage_cells)
    for pose_idx, pose in enumerate(pole_pool):
        occ = pose.get("occupied_cells", [])
        if not occ:
            continue
        cells_tup = [(int(c[0]), int(c[1])) for c in occ]
        if any(not (0 <= c[0] < grid_w and 0 <= c[1] < grid_h) for c in cells_tup):
            continue
        if any(c in forbidden for c in cells_tup):
            continue
        cov = pose.get("power_coverage_cells", []) or []
        cov_tup = [(int(c[0]), int(c[1])) for c in cov]
        pole_feas.append((pose_idx, cells_tup, cov_tup))

    total_mand_poses = sum(len(g["feas_poses"]) for g in mandatory_groups)
    total_ro_poses = sum(len(g["feas_poses"]) for g in ro_groups)
    powered_groups = [g for g in mandatory_groups + ro_groups if g["is_powered"]]
    print(f"[filter] mandatory {len(mandatory_groups)} groups, {total_mand_poses} pose-bool vars")
    print(f"[filter] required_optional {len(ro_groups)} groups, {total_ro_poses} pose-bool vars")
    print(f"[filter] pole pool: {len(pole_feas)} feasible pose-bool vars (out of {len(pole_pool)})")
    print(f"[filter] powered group count: {len(powered_groups)}")

    # ============ build CP-SAT model ============
    t2 = time.perf_counter()
    print(f"[cpsat] building pose-bool model ...", flush=True)
    model = cp_model.CpModel()
    x_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}  # mandatory + required_optional
    pose_idx_to_var: Dict[Tuple[str, int], cp_model.IntVar] = {}  # (template, pose_idx) → first var encountered (used as fallback)
    # for cell exclusivity: per cell, list of all BoolVars whose pose covers it
    cell_poses: Dict[Tuple[int, int], List[cp_model.IntVar]] = {}

    # mandatory + ro groups (uniform handling)
    for g in mandatory_groups + ro_groups:
        gid = g["group_id"]
        group_vars = []
        for pose_idx, cells in g["feas_poses"]:
            v = model.NewBoolVar(f"x_{gid}_{pose_idx}")
            x_vars[(gid, pose_idx)] = v
            group_vars.append(v)
            for c in cells:
                cell_poses.setdefault(c, []).append(v)
        # demand
        model.Add(sum(group_vars) == g["demand"])

    # pole vars (no demand fix - residual_optional)
    pole_vars: Dict[int, cp_model.IntVar] = {}
    for pose_idx, cells, _cov in pole_feas:
        v = model.NewBoolVar(f"y_pole_{pose_idx}")
        pole_vars[pose_idx] = v
        for c in cells:
            cell_poses.setdefault(c, []).append(v)

    # cell exclusivity (excluding ghost cells - they have no pose anyway)
    cell_exclusivity_count = 0
    for c, vars_in_cell in cell_poses.items():
        if len(vars_in_cell) > 1:
            model.AddAtMostOne(vars_in_cell)
            cell_exclusivity_count += 1

    # ============ power coverage 约束 ============
    coverage_constraints = 0
    if not args.skip_power:
        coverers_table = m._power_coverers_by_template_pose
        # 对每个 powered group g, pose p: x_{g,p} <= sum_{coverer pole pose} y_{pole}
        for g in powered_groups:
            tpl = g["template"]
            tpl_cov = coverers_table.get(tpl, {})
            for pose_idx, _cells in g["feas_poses"]:
                coverer_pole_indices = tpl_cov.get(int(pose_idx), [])
                # 只保留在 pole_vars (即 feasible) 里的
                cov_vars = [pole_vars[int(idx)] for idx in coverer_pole_indices if int(idx) in pole_vars]
                x_var = x_vars[(g["group_id"], pose_idx)]
                if cov_vars:
                    # x_{g,p} <= sum(cov_vars)
                    model.Add(x_var <= sum(cov_vars))
                else:
                    # 无 coverer → 此 pose 不可选
                    model.Add(x_var == 0)
                coverage_constraints += 1

    print(f"[cpsat] built in {time.perf_counter()-t2:.1f}s")
    print(f"  bool vars: {len(x_vars) + len(pole_vars)} "
          f"(x={len(x_vars)}, y_pole={len(pole_vars)})")
    print(f"  cell exclusivity constraints: {cell_exclusivity_count}")
    print(f"  power coverage constraints: {coverage_constraints}")

    # ============ solve ============
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

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # count pole used
        pole_used = sum(1 for pv in pole_vars.values() if solver.Value(pv))
        print(f"poles placed: {pole_used}")

    # verdict gate
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and elapsed < 60:
        print(f"\n>>> B1 Phase 0 GO: < 60s feasible <<<")
    else:
        print(f"\n>>> B1 Phase 0 NO-GO: {status_name} in {elapsed:.1f}s <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

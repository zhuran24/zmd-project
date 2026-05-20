"""B1 Phase 1 trial: pose-bool master + PortBindingModel end-to-end.

跑 27×15 anchor (22,28) interior:
1. pose-bool master 解出 layout (Phase 0 prototype 逻辑)
2. 把 layout 转成 placement_solution dict (instance_id → {facility_type, pose_idx, anchor})
3. 调 PortBindingModel.solve() 验 port match feasible

如果 binding 也 FEASIBLE, 这就是 partial certified (master + binding 都 pass,
还差 routing). 完整 certified 需要 routing subproblem 也 pass.
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


def solve_pose_bool_master(args, m, delegate, grid_w, grid_h):
    """同 Phase 0 prototype, 但返回 selected (group_id, pose_idx) + pole_pose_idx 列表."""
    forbidden: Set[Tuple[int, int]] = {
        (args.anchor_x + dx, args.anchor_y + dy)
        for dx in range(args.ghost_w) for dy in range(args.ghost_h)
    }

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
            print(f"  [INFEASIBLE] group {gid} 0 feasible pose")
            return None
        mandatory_groups.append({
            "group_id": gid,
            "instance_ids": list(group.get("instance_ids", [])),
            "template": tpl,
            "demand": demand,
            "is_powered": is_powered,
            "feas_poses": feas_poses,
        })

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
            return None
        ro_groups.append({
            "group_id": f"ro::{tpl}",
            "template": tpl,
            "demand": demand,
            "is_powered": is_powered,
            "feas_poses": feas_poses,
        })

    pole_pool = m.facility_pools.get("power_pole", [])
    pole_feas: List[Tuple[int, List[Tuple[int, int]]]] = []
    for pose_idx, pose in enumerate(pole_pool):
        occ = pose.get("occupied_cells", [])
        if not occ:
            continue
        cells_tup = [(int(c[0]), int(c[1])) for c in occ]
        if any(not (0 <= c[0] < grid_w and 0 <= c[1] < grid_h) for c in cells_tup):
            continue
        if any(c in forbidden for c in cells_tup):
            continue
        pole_feas.append((pose_idx, cells_tup))

    powered_groups = [g for g in mandatory_groups + ro_groups if g["is_powered"]]
    print(f"  mandatory {len(mandatory_groups)} groups, ro {len(ro_groups)} groups, pole feas {len(pole_feas)}")

    model = cp_model.CpModel()
    x_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
    cell_poses: Dict[Tuple[int, int], List[cp_model.IntVar]] = {}

    for g in mandatory_groups + ro_groups:
        gid = g["group_id"]
        group_vars = []
        for pose_idx, cells in g["feas_poses"]:
            v = model.NewBoolVar(f"x_{gid}_{pose_idx}")
            x_vars[(gid, pose_idx)] = v
            group_vars.append(v)
            for c in cells:
                cell_poses.setdefault(c, []).append(v)
        model.Add(sum(group_vars) == g["demand"])

    pole_vars: Dict[int, cp_model.IntVar] = {}
    for pose_idx, cells in pole_feas:
        v = model.NewBoolVar(f"y_pole_{pose_idx}")
        pole_vars[pose_idx] = v
        for c in cells:
            cell_poses.setdefault(c, []).append(v)

    for c, vars_in_cell in cell_poses.items():
        if len(vars_in_cell) > 1:
            model.AddAtMostOne(vars_in_cell)

    coverers_table = m._power_coverers_by_template_pose
    for g in powered_groups:
        tpl = g["template"]
        tpl_cov = coverers_table.get(tpl, {})
        for pose_idx, _cells in g["feas_poses"]:
            coverer_pole_indices = tpl_cov.get(int(pose_idx), [])
            cov_vars = [pole_vars[int(idx)] for idx in coverer_pole_indices if int(idx) in pole_vars]
            x_var = x_vars[(g["group_id"], pose_idx)]
            if cov_vars:
                model.Add(x_var <= sum(cov_vars))
            else:
                model.Add(x_var == 0)

    t = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(args.master_time_limit)
    solver.parameters.num_search_workers = int(args.workers)
    solver.parameters.log_search_progress = False
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t
    status_name = {
        cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN",
    }.get(status, f"raw({status})")
    print(f"  master.solve: {status_name} in {elapsed:.1f}s, {solver.NumBranches()} branches")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    selected: Dict[str, List[int]] = {}  # group_id → list of pose_idx
    for g in mandatory_groups + ro_groups:
        gid = g["group_id"]
        chosen = [pose_idx for pose_idx, _ in g["feas_poses"]
                  if solver.Value(x_vars[(gid, pose_idx)]) == 1]
        selected[gid] = chosen
    pole_chosen = [idx for idx, v in pole_vars.items() if solver.Value(v) == 1]
    return {
        "mandatory_groups": mandatory_groups,
        "ro_groups": ro_groups,
        "selected": selected,
        "pole_chosen": pole_chosen,
        "elapsed": elapsed,
        "status": status_name,
    }


def build_placement_solution(layout, pole_pool, m):
    """把 pose-bool layout 转成 PortBindingModel 需要的 placement_solution dict."""
    placement = {}
    for g in layout["mandatory_groups"] + layout["ro_groups"]:
        gid = g["group_id"]
        tpl = g["template"]
        chosen_poses = layout["selected"].get(gid, [])
        instance_ids = list(g.get("instance_ids", []))
        if not instance_ids:
            # synthetic id (ro)
            instance_ids = [f"pose_optional::{tpl}::{pose_idx}" for pose_idx in chosen_poses]
        for inst_id, pose_idx in zip(instance_ids, chosen_poses):
            pose = m.facility_pools[tpl][pose_idx]
            placement[str(inst_id)] = {
                "instance_id": str(inst_id),
                "facility_type": tpl,
                "pose_idx": int(pose_idx),
                "pose_id": pose["pose_id"],
                "anchor": dict(pose["anchor"]),
            }
    # poles as synthetic optionals
    for pose_idx in layout["pole_chosen"]:
        pose = pole_pool[pose_idx]
        sid = f"pose_optional::power_pole::{pose['pose_id']}"
        placement[sid] = {
            "instance_id": sid,
            "facility_type": "power_pole",
            "pose_idx": int(pose_idx),
            "pose_id": pose["pose_id"],
            "anchor": dict(pose["anchor"]),
        }
    return placement


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22)
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--master-time-limit", type=float, default=120.0)
    parser.add_argument("--binding-time-limit", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    project_root = Path(".")
    print(f"=== B1 Phase 1 end-to-end (master + binding) ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")

    t0 = time.perf_counter()
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print(f"[load] {time.perf_counter()-t0:.1f}s")

    t1 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts)
    m = MasterPlacementModel.from_exact_core(core, ghost_rect=(args.ghost_w, args.ghost_h))
    delegate = m._coordinate_delegate
    grid_w = int(rules["globals"]["grid"]["width"])
    grid_h = int(rules["globals"]["grid"]["height"])
    print(f"[master_core_build] {time.perf_counter()-t1:.1f}s")

    print(f"[master_solve] start ...", flush=True)
    layout = solve_pose_bool_master(args, m, delegate, grid_w, grid_h)
    if layout is None:
        print("[master_solve] no feasible layout — abort")
        return 0

    print(f"\n[binding] building placement_solution from pose-bool layout ...", flush=True)
    pole_pool = m.facility_pools.get("power_pole", [])
    placement_solution = build_placement_solution(layout, pole_pool, m)
    print(f"  placement_solution size: {len(placement_solution)} instances")

    # import here so 之前 import 错不影响
    from src.models.binding_subproblem import PortBindingModel

    t3 = time.perf_counter()
    binding_model = PortBindingModel(
        placement_solution,
        m.facility_pools,
        instances,
        project_root=project_root,
    )
    binding_model.build()
    print(f"[binding_build] {time.perf_counter()-t3:.1f}s")

    t4 = time.perf_counter()
    binding_status = binding_model.solve(time_limit_seconds=args.binding_time_limit)
    print(f"[binding_solve] status={binding_status} in {time.perf_counter()-t4:.1f}s")

    if binding_status != "FEASIBLE":
        summary = binding_model.extract_conflict_summary()
        print(f"binding conflict summary keys: {list(summary.keys())}")
        empty_inst = summary.get("empty_binding_domain_instances", [])
        if empty_inst:
            print(f"  empty binding domain instances: {len(empty_inst)}")
        missing = summary.get("missing_instance_ids", [])
        if missing:
            print(f"  missing instance ids: {len(missing)} sample: {missing[:5]}")
        print(f"\n=== verdict ===")
        print(f"master: {layout['status']} {layout['elapsed']:.1f}s | binding: {binding_status}")
        print(f"\n>>> B1 Phase 1 binding FAIL <<<")
        return 0

    # =========== routing 阶段 ===========
    print(f"\n[routing] wiring ...", flush=True)
    from src.models.routing_subproblem import (
        RoutingPlacementCore, RoutingGrid, RoutingSubproblem,
    )
    try:
        from src.models.routing_subproblem import run_exact_routing_precheck
    except ImportError:
        run_exact_routing_precheck = None

    occupied_cells = set()
    occupied_owner_by_cell = {}
    for inst_id, sol in placement_solution.items():
        tpl = sol["facility_type"]
        pose = m.facility_pools[tpl][int(sol["pose_idx"])]
        for cell in pose.get("occupied_cells", []):
            c = (int(cell[0]), int(cell[1]))
            occupied_cells.add(c)
            occupied_owner_by_cell[c] = inst_id

    t5 = time.perf_counter()
    routing_placement_core = RoutingPlacementCore.from_occupied_cells(
        occupied_cells, occupied_owner_by_cell=occupied_owner_by_cell,
    )
    print(f"[routing_core_build] {time.perf_counter()-t5:.1f}s, occupied_cells={len(occupied_cells)}")

    port_specs = binding_model.extract_port_specs()
    print(f"  port_specs: {len(port_specs)}")
    commodities = sorted({str(p["commodity"]) for p in port_specs})
    print(f"  commodities: {len(commodities)}")

    t6 = time.perf_counter()
    routing_grid = RoutingGrid.from_placement_core(routing_placement_core, port_specs)
    print(f"[routing_grid_build] {time.perf_counter()-t6:.1f}s")

    # precheck
    routing_precheck = None
    if run_exact_routing_precheck is not None:
        try:
            routing_precheck = run_exact_routing_precheck(
                placement_core=routing_placement_core,
                port_specs=port_specs,
                occupied_owner_by_cell=occupied_owner_by_cell,
            )
        except TypeError:
            try:
                routing_precheck = run_exact_routing_precheck(
                    routing_grid, occupied_owner_by_cell=occupied_owner_by_cell,
                )
            except TypeError:
                routing_precheck = run_exact_routing_precheck(routing_grid)
        precheck_status = (routing_precheck or {}).get("status", "unknown")
        print(f"[routing_precheck] status={precheck_status}")
        if precheck_status not in ("feasible", "unknown"):
            print(f"\n>>> B1 Phase 1 routing precheck FAIL: {precheck_status} <<<")
            return 0
    domain_analysis = (routing_precheck or {}).get("_analysis")

    t7 = time.perf_counter()
    if hasattr(RoutingSubproblem, "from_placement_core"):
        routing_model = RoutingSubproblem.from_placement_core(
            routing_placement_core, port_specs, commodities,
            domain_analysis=domain_analysis,
        )
    else:
        routing_model = RoutingSubproblem(routing_grid, commodities, domain_analysis=domain_analysis)
    routing_model.build()
    print(f"[routing_build] {time.perf_counter()-t7:.1f}s")

    t8 = time.perf_counter()
    routing_status = routing_model.solve(time_limit=float(args.binding_time_limit))
    print(f"[routing_solve] status={routing_status} in {time.perf_counter()-t8:.1f}s")

    print(f"\n=== verdict ===")
    print(f"master: {layout['status']} {layout['elapsed']:.1f}s")
    print(f"binding: {binding_status}")
    print(f"routing: {routing_status}")
    if routing_status == "FEASIBLE":
        print(f"\n>>> 🎯 B1 Phase 1 FULL CERTIFIED FEASIBLE — 27×15 anchor ({args.anchor_x},{args.anchor_y}) <<<")
    else:
        print(f"\n>>> B1 Phase 1 routing {routing_status}, partial certified only <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

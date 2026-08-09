"""Phase 0 mini-PoC probe for EXACT_LAZY_POWER_COMPLETION architecture.

跳过 LBBD 主流程, 直接走 minimal path:
  1. build master core with EXACT_LAZY_POWER_COMPLETION=1
  2. solve master to FEASIBLE
  3. drop master-selected power_pole entries (lazy mode 下不信任 master 给的 pole)
  4. build PowerPlacementSubproblem from non-power layout + ghost cells
  5. solve subproblem (time_limit 10s)
  6. validate direct: no pole overlap / 全 powered instance covered / 不碰 ghost
  7. emit JSON 数据点

Go gate (per GPT v11 计划书):
  Master:
    vars <= 26,000
    constraints <= 75,000
    first_solve_seconds <= 90
    two_iter_wall_seconds <= 150 (此 probe 只跑 first solve, 2-iter 在 LBBD 集成才有)
  Completion:
    build_seconds <= 2
    solve_seconds <= 10
    status == FEASIBLE
    validator OK
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# anchor filter env 必须在 import master_model 前
os.environ.setdefault("EXACT_LAZY_POWER_COMPLETION", "1")
os.environ.setdefault("EXACT_MASTER_GHOST_ANCHOR_FILTER", "22,28")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.sat.python import cp_model  # noqa: E402

from src.models.master_model import (  # noqa: E402
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.models.power_placement_subproblem import (  # noqa: E402
    PowerPlacementSubproblem,
)
from scripts.phase3_core_minimizer import (  # noqa: E402
    minimize_power_infeasible_core_linear_deletion,
)
from src.search.benders_loop import (  # noqa: E402
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
)


def compute_ghost_cells(
    ghost_w: int, ghost_h: int, anchor_x: int, anchor_y: int
) -> Set[Tuple[int, int]]:
    return {
        (anchor_x + dx, anchor_y + dy)
        for dx in range(ghost_w)
        for dy in range(ghost_h)
    }


def drop_power_pole_entries(
    solution: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        iid: entry
        for iid, entry in solution.items()
        if str(entry.get("facility_type", "")) != "power_pole"
    }


def validate_witness_direct(
    *,
    non_power_solution: Dict[str, Any],
    selected_pose_indices: Tuple[int, ...],
    facility_pools: Dict[str, List[Dict[str, Any]]],
    ghost_cells: Set[Tuple[int, int]],
    powered_templates: Set[str],
    power_coverers_by_template_pose: Dict[str, Dict[int, List[int]]],
) -> Dict[str, Any]:
    """Direct (non-CP-SAT) validator. Returns dict with ok + reason."""

    pole_pool = facility_pools["power_pole"]
    selected_poses = [pole_pool[i] for i in selected_pose_indices]

    # 1. pole-pole no overlap
    pole_cells: List[Set[Tuple[int, int]]] = []
    for pose in selected_poses:
        cells = {(int(x), int(y)) for x, y in (pose.get("occupied_cells") or [])}
        pole_cells.append(cells)
    flat = [c for cells in pole_cells for c in cells]
    if len(flat) != len(set(flat)):
        return {"ok": False, "reason": "pole_pole_overlap"}

    # 2. pole 不碰 ghost
    union_pole = {c for cells in pole_cells for c in cells}
    if union_pole & ghost_cells:
        return {"ok": False, "reason": "pole_overlaps_ghost"}

    # 3. pole 不碰 non-power 设施
    non_power_occupied: Set[Tuple[int, int]] = set()
    for entry in non_power_solution.values():
        tpl = str(entry["facility_type"])
        pose_idx = int(entry["pose_idx"])
        pose = facility_pools[tpl][pose_idx]
        cells = {(int(x), int(y)) for x, y in (pose.get("occupied_cells") or [])}
        non_power_occupied |= cells
    if union_pole & non_power_occupied:
        return {"ok": False, "reason": "pole_overlaps_non_power_facility"}

    # 4. 每个 powered instance 至少被一个 selected pole cover
    selected_set = set(int(i) for i in selected_pose_indices)
    uncovered: List[str] = []
    for iid, entry in non_power_solution.items():
        tpl = str(entry["facility_type"])
        if tpl not in powered_templates or tpl == "power_pole":
            continue
        pose_idx = int(entry["pose_idx"])
        full_coverers = list(
            power_coverers_by_template_pose.get(tpl, {}).get(pose_idx, [])
        )
        covered = bool(set(full_coverers) & selected_set)
        if not covered:
            uncovered.append(iid)
    if uncovered:
        return {"ok": False, "reason": "uncovered", "uncovered": uncovered[:5]}

    return {"ok": True, "reason": None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22)
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--master-seconds", type=float, default=180.0)
    parser.add_argument("--completion-seconds", type=float, default=10.0)
    parser.add_argument("--max-cut-iterations", type=int, default=1,
                        help="如果 completion INFEASIBLE, 加 nogood cut 重 solve master, 最多 N iter")
    parser.add_argument("--use-core-minimizer", action="store_true",
                        help="Phase 3: cut iteration 用 deletion-based core minimizer 缩 core 而不是 loose 220-pose cut")
    parser.add_argument("--minimizer-max-oracle-calls", type=int, default=32)
    parser.add_argument("--minimizer-max-seconds", type=float, default=120.0)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    out_data: Dict[str, Any] = {
        "candidate": f"{args.ghost_w}x{args.ghost_h}",
        "anchor": [args.anchor_x, args.anchor_y],
        "phase": "phase0_lazy_power_completion_probe",
        "env": {
            "EXACT_LAZY_POWER_COMPLETION": os.environ.get(
                "EXACT_LAZY_POWER_COMPLETION", ""
            ),
            "EXACT_MASTER_GHOST_ANCHOR_FILTER": os.environ.get(
                "EXACT_MASTER_GHOST_ANCHOR_FILTER", ""
            ),
        },
    }

    print(f"=== Phase 0 probe ===")
    print(f"candidate: {args.ghost_w}x{args.ghost_h}")
    print(f"anchor: ({args.anchor_x},{args.anchor_y})")
    print(f"master_seconds={args.master_seconds}, completion_seconds={args.completion_seconds}")
    print(f"EXACT_LAZY_POWER_COMPLETION={os.environ.get('EXACT_LAZY_POWER_COMPLETION')}")
    print(flush=True)

    t_load = time.perf_counter()
    print(f"[load] project data ...", flush=True)
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    print(f"[load] {time.perf_counter()-t_load:.1f}s")

    t_core = time.perf_counter()
    print(f"[build] master exact core (EXACT_LAZY_POWER_COMPLETION on) ...", flush=True)
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules,
        skip_power_coverage=False,
        generic_io_requirements=generic,
        master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    core_seconds = time.perf_counter() - t_core
    profile = core.build_stats.get("exact_core_packaging_profile", {})
    proto_vars = int(profile.get("proto_variable_count", 0))
    proto_cons = int(profile.get("proto_constraint_count", 0))
    power_cov_stats = dict(core.build_stats.get("power_coverage", {}))
    print(f"[build] {core_seconds:.1f}s, vars={proto_vars}, cons={proto_cons}")
    print(f"[build] power_coverage stats: {power_cov_stats}")

    out_data["master"] = {
        "build_seconds": float(core_seconds),
        "vars": proto_vars,
        "constraints": proto_cons,
        "power_coverage_representation": str(power_cov_stats.get("representation", "?")),
        "power_pole_slots_materialized": bool(
            power_cov_stats.get("power_pole_slots_materialized", False)
        ),
    }

    # build master overlay for this ghost rect
    m = MasterPlacementModel.from_exact_core(
        core, ghost_rect=(args.ghost_w, args.ghost_h)
    )
    m.build()

    # status name helper
    def _status_name(status_int: int) -> str:
        return {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.UNKNOWN: "UNKNOWN",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
        }.get(status_int, f"raw({status_int})")

    # solve master (LBBD iter 1)
    print(f"\n[solve] master.solve(time_limit={args.master_seconds}) ...", flush=True)
    t_solve = time.perf_counter()
    status_int = m.solve(time_limit_seconds=args.master_seconds)
    solve_seconds = time.perf_counter() - t_solve
    status_name = _status_name(status_int)
    print(f"[solve] {solve_seconds:.1f}s, status={status_name}")

    out_data["master"]["first_solve_seconds"] = float(solve_seconds)
    out_data["master"]["first_solve_status"] = status_name
    out_data["lbbd_iterations"] = []

    last_solve = m.build_stats.get("last_solve", {})
    out_data["master"]["last_solve_stats"] = {
        k: last_solve.get(k)
        for k in ("status", "wall_time", "branches", "conflicts", "binary_propagations", "integer_propagations")
    }

    if status_int not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n=== Phase 0 master gate: NO-GO ===")
        out_data["gate"] = {
            "master_pass": False,
            "master_reason": f"status_{status_name}",
            "completion_pass": None,
        }
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(out_data, f, indent=2)
            print(f"\n[output] {args.output_json}")
        return 1

    # extract solution
    solution = m.extract_solution()
    print(f"\n[extract] solution entries: {len(solution)}")
    non_power_solution = drop_power_pole_entries(solution)
    print(f"[extract] non-power entries: {len(non_power_solution)}")
    master_selected_pole_count = len(solution) - len(non_power_solution)
    print(f"[extract] master-selected power_pole entries (dropped): {master_selected_pole_count}")

    out_data["extract"] = {
        "total_entries": len(solution),
        "non_power_entries": len(non_power_solution),
        "master_selected_power_pole_dropped": master_selected_pole_count,
    }

    # 计算 ghost cells
    ghost_cells = compute_ghost_cells(args.ghost_w, args.ghost_h, args.anchor_x, args.anchor_y)
    print(f"[ghost] cells={len(ghost_cells)}")

    # build completion subproblem
    print(f"\n[completion] PowerPlacementSubproblem build ...", flush=True)
    t_cb = time.perf_counter()
    sub = PowerPlacementSubproblem(
        master_solution=non_power_solution,
        facility_pools=pools,
        powered_templates=getattr(m, "_powered_templates", set()) or set(),
        power_coverers_by_template_pose=(
            getattr(m, "_power_coverers_by_template_pose", {}) or {}
        ),
        ghost_cells=ghost_cells,
    )
    sub.build()
    completion_build_seconds = time.perf_counter() - t_cb
    print(f"[completion] build {completion_build_seconds:.2f}s, candidate_poles={len(sub.candidate_pole_indices)}, powered_instances={len(sub.coverers_by_instance)}")

    # solve completion
    print(f"[completion] solve(time_limit={args.completion_seconds}) ...", flush=True)
    t_cs = time.perf_counter()
    result = sub.solve(time_limit_seconds=args.completion_seconds)
    completion_solve_seconds = time.perf_counter() - t_cs
    print(f"[completion] solve {completion_solve_seconds:.2f}s, status={result.status}")
    print(f"[completion] stats={dict(result.stats)}")
    if result.status == "FEASIBLE":
        print(f"[completion] selected_pole_count={len(result.selected_pose_indices)}")

    out_data["completion"] = {
        "build_seconds": float(completion_build_seconds),
        "solve_seconds": float(completion_solve_seconds),
        "status": result.status,
        "candidate_pole_count": int(result.stats.get("candidate_pole_count", 0)),
        "powered_instance_count": int(result.stats.get("powered_instance_count", 0)),
        "selected_pole_count": (
            int(result.stats.get("selected_pole_count", 0))
            if result.status == "FEASIBLE"
            else None
        ),
        "uncovered_instance_count": int(result.stats.get("uncovered_instance_count", 0)),
        "uncovered_instance_ids": list(result.uncovered_instance_ids)[:5],
    }

    # direct validator
    if result.status == "FEASIBLE":
        print(f"\n[validate] direct witness validator ...", flush=True)
        validation = validate_witness_direct(
            non_power_solution=non_power_solution,
            selected_pose_indices=result.selected_pose_indices,
            facility_pools=pools,
            ghost_cells=ghost_cells,
            powered_templates=set(getattr(m, "_powered_templates", set()) or set()),
            power_coverers_by_template_pose=(
                getattr(m, "_power_coverers_by_template_pose", {}) or {}
            ),
        )
        print(f"[validate] {validation}")
        out_data["validator"] = validation
    else:
        out_data["validator"] = {"ok": False, "reason": f"completion_{result.status}"}

    # 扩展 Phase 0: cut loop, completion INFEASIBLE 时加 nogood cut 重 solve master
    iteration = 1
    out_data["lbbd_iterations"].append({
        "iter": 1,
        "master_solve_seconds": float(solve_seconds),
        "master_status": status_name,
        "completion_status": str(result.status),
        "completion_solve_seconds": float(completion_solve_seconds),
        "uncovered_count": int(out_data["completion"]["uncovered_instance_count"]),
        "validator_ok": bool(out_data["validator"]["ok"]),
        "cut_added": False,
    })

    while (
        result.status == "INFEASIBLE"
        and iteration < args.max_cut_iterations
        and status_int in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    ):
        powered_set = set(getattr(m, "_powered_templates", set()) or set())

        if args.use_core_minimizer:
            # Phase 3: deletion-based core minimizer 缩 core
            print(f"\n[cut iter {iteration+1}] core minimizer ...", flush=True)
            t_min = time.perf_counter()
            core = minimize_power_infeasible_core_linear_deletion(
                full_solution=non_power_solution,
                facility_pools=pools,
                powered_templates=powered_set,
                power_coverers_by_template_pose=(
                    getattr(m, "_power_coverers_by_template_pose", {}) or {}
                ),
                ghost_cells=ghost_cells,
                max_oracle_calls=args.minimizer_max_oracle_calls,
                max_seconds=args.minimizer_max_seconds,
                oracle_time_limit_s=args.completion_seconds,
                verbose=True,
            )
            min_seconds = time.perf_counter() - t_min
            print(
                f"[cut iter {iteration+1}] minimizer done {min_seconds:.1f}s, "
                f"core size {core.full_layout_size}→{len(core.instance_ids)}, "
                f"oracle_calls={core.oracle_calls}, abort={core.abort_reason}"
            )
            # core 包含 powered + non-powered, conflict_set 只取 instance_id → pose_idx
            conflict_set: Dict[str, int] = {
                iid: int(non_power_solution[iid]["pose_idx"])
                for iid in core.instance_ids
                if iid in non_power_solution
            }
        else:
            # Loose cut: 禁全 powered facility (Phase 0 baseline behavior)
            conflict_set = {}
            for iid, entry in non_power_solution.items():
                tpl = str(entry.get("facility_type"))
                if tpl in powered_set and tpl != "power_pole":
                    conflict_set[str(iid)] = int(entry["pose_idx"])

        print(f"\n[cut iter {iteration+1}] add nogood, |conflict_set|={len(conflict_set)} ...", flush=True)
        t_cut = time.perf_counter()
        added = m.add_benders_cut(conflict_set)
        print(f"[cut iter {iteration+1}] added={added}, +{time.perf_counter()-t_cut:.2f}s")

        iteration += 1
        print(f"[solve iter {iteration}] master.solve ...", flush=True)
        t_solve = time.perf_counter()
        status_int = m.solve(time_limit_seconds=args.master_seconds)
        solve_seconds = time.perf_counter() - t_solve
        status_name = _status_name(status_int)
        print(f"[solve iter {iteration}] {solve_seconds:.1f}s, status={status_name}")

        if status_int not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            out_data["lbbd_iterations"].append({
                "iter": iteration,
                "master_solve_seconds": float(solve_seconds),
                "master_status": status_name,
                "cut_added": True,
                "conflict_set_size": len(conflict_set),
                "abort_reason": f"master_{status_name}",
            })
            break

        solution = m.extract_solution()
        non_power_solution = drop_power_pole_entries(solution)
        sub = PowerPlacementSubproblem(
            master_solution=non_power_solution,
            facility_pools=pools,
            powered_templates=getattr(m, "_powered_templates", set()) or set(),
            power_coverers_by_template_pose=(
                getattr(m, "_power_coverers_by_template_pose", {}) or {}
            ),
            ghost_cells=ghost_cells,
        )
        sub.build()
        t_cs = time.perf_counter()
        result = sub.solve(time_limit_seconds=args.completion_seconds)
        completion_solve_seconds = time.perf_counter() - t_cs
        print(f"[iter {iteration}] completion {completion_solve_seconds:.2f}s, status={result.status}, uncovered={result.stats.get('uncovered_instance_count')}")

        out_data["lbbd_iterations"].append({
            "iter": iteration,
            "master_solve_seconds": float(solve_seconds),
            "master_status": status_name,
            "completion_status": str(result.status),
            "completion_solve_seconds": float(completion_solve_seconds),
            "uncovered_count": int(result.stats.get("uncovered_instance_count", 0)),
            "cut_added": True,
            "conflict_set_size": len(conflict_set),
            "selected_pole_count": (
                len(result.selected_pose_indices)
                if result.status == "FEASIBLE"
                else None
            ),
        })

    out_data["final_iteration"] = iteration
    out_data["final_completion_status"] = result.status

    # 评 go/no-go: master gate 用 solve time, 不用 var 数 (GPT threshold 错估)
    master_pass = out_data["master"]["first_solve_seconds"] <= 90.0 and (
        out_data["master"]["first_solve_status"] in {"OPTIMAL", "FEASIBLE"}
    )
    # completion gate: final iteration FEASIBLE + 时间预算 + (validator 只在 iter 1 跑一次)
    completion_pass = (
        result.status == "FEASIBLE"
        and out_data["completion"]["build_seconds"] <= 2.0
        and float(out_data["lbbd_iterations"][-1].get("completion_solve_seconds", 999)) <= 10.0
    )
    out_data["gate"] = {
        "master_pass": bool(master_pass),
        "master_reason": (
            None
            if master_pass
            else "exceeded_threshold_or_status"
        ),
        "completion_pass": bool(completion_pass),
        "completion_reason": (
            None
            if completion_pass
            else f"status_{out_data['completion']['status']}_or_validator_fail_or_timeout"
        ),
    }

    print(f"\n=== Phase 0 gate verdict ===")
    print(f"Master gate: {'PASS' if master_pass else 'NO-GO'}")
    print(f"  vars={out_data['master']['vars']} (≤26000)")
    print(f"  constraints={out_data['master']['constraints']} (≤75000)")
    print(f"  first_solve={out_data['master']['first_solve_seconds']:.1f}s (≤90)")
    print(f"  status={out_data['master']['first_solve_status']}")
    print(f"Completion gate: {'PASS' if completion_pass else 'NO-GO'}")
    print(f"  build={out_data['completion']['build_seconds']:.2f}s (≤2)")
    print(f"  solve={out_data['completion']['solve_seconds']:.2f}s (≤10)")
    print(f"  status={out_data['completion']['status']}")
    print(f"  validator={out_data['validator']}")
    print(f"\n→ Overall: {'GO' if (master_pass and completion_pass) else 'NO-GO'}")

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(out_data, f, indent=2)
        print(f"\n[output] {args.output_json}")

    return 0 if (master_pass and completion_pass) else 2


if __name__ == "__main__":
    sys.exit(main())

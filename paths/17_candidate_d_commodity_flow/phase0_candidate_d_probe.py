"""Candidate D (Path 17) Phase 0 cheap gate — commodity cell-flow master probe.

GPT v7 plan Candidate D 数学描述:
- 主变量 u[k,c] ∈ {0,1}: commodity k may use cell c (ground layer simplification)
- capacity: sum_k u[k,c] ≤ 1 (cell exclusivity across commodities)
- port adherence: for each owner port (commodity k, front_cell), enforce u[k, front_cell] = 1
- (Phase 1 增强: 加 e[k,arc] directed-arc vars + channeling + flow conservation)

Phase 0 D1 simplification — 只 u vars, 不 e/arc, 不分 layer. 验证:
- 在 master OPTIMAL layout + binding 选定 ports 上, 加 commodity cell-flow constraints 后
  model 在 wall budget (600s, 10x current 60s cap) 内能否给出 SAT verdict.
- vars / constraints / RSS 是否 fit 资源 cap.

GO 条件:
- ≥5/7 eligible anchor 给 INFEASIBLE in ≤ 600s (D1 提供了 production routing 之外的信息)
- vars ≤ 250K, constraints ≤ 650K, RSS ≤ 12 GB

NO-GO:
- ≥3 TIMEOUT (wall 不够 even at 10x)
- ≥3 FEASIBLE (D1 太松, port-front-clear necessary 没增量信息)
- RAM 爆

D1 INFEASIBLE 信号最有意义 — paradigm 起点 OK 可投资 Phase 1 加 connectivity.

实施: monkey-patch binding.solve 拿 layout + port_specs, 在 layout 上 standalone build
Candidate D CP-SAT model + solve.
"""

from __future__ import annotations

import gc
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ortools.sat.python import cp_model

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT_FILE = Path("paths/17_candidate_d_commodity_flow/phase0_candidate_d_stats.json")

GRID_W = 70
GRID_H = 70
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}

ANCHORS = [
    (27, 15, 22, 28, "interior_22_28"),
    (27, 15, 10, 10, "interior_10_10"),
    (27, 15, 44, 30, "interior_44_30"),
    (27, 15, 15, 40, "interior_15_40"),
    (27, 15, 0, 0, "corner_0_0_NEGATIVE"),
    (10, 10, 25, 25, "small_10x10"),
    (15, 10, 22, 28, "small_15x10"),
    (15, 15, 22, 28, "small_15x15"),
]


def _reset_env(ax: int, ay: int) -> None:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
        "EXACT_B1_PATCH_ROUTING_CORE",
    ):
        os.environ.pop(k, None)


def _build_and_solve_candidate_d(
    occupied: Set[Tuple[int, int]],
    port_specs: List[Dict[str, Any]],
    time_limit: float = 600.0,
) -> Dict[str, Any]:
    """Build Candidate D D1 model (only u[k,c] vars, capacity + port-front adherence) and solve."""
    free_cells: Set[Tuple[int, int]] = {
        (x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occupied
    }
    commodities = sorted({str(ps["commodity"]) for ps in port_specs})

    model = cp_model.CpModel()
    t_build0 = time.perf_counter()

    # u[k, c] BoolVar
    u_vars: Dict[Tuple[str, int, int], Any] = {}
    for k in commodities:
        for (x, y) in free_cells:
            u_vars[(k, x, y)] = model.NewBoolVar(f"u_{k}_{x}_{y}")

    # capacity: sum_k u[k, c] <= 1 per cell
    for (x, y) in free_cells:
        cell_u_vars = [u_vars[(k, x, y)] for k in commodities]
        if cell_u_vars:
            model.AddAtMostOne(cell_u_vars)

    # port adherence: for each port (i, p, k, dir), enforce u[k, front_cell] = 1
    # — only for front-clear ports (skip front_blocked to测 paradigm incremental value
    # beyond production routing precheck which already detects front_blocked).
    # Candidate D 想测的是: front-clear ports 之间 capacity 冲突 (production precheck 看不到).
    blocked_port_count = 0
    forced_port_count = 0
    for ps in port_specs:
        px, py = int(ps["x"]), int(ps["y"])
        direction = str(ps.get("dir", ""))
        commodity = str(ps.get("commodity", ""))
        if commodity not in {k for k in commodities}:
            continue
        dx, dy = DIR_DELTA.get(direction, (0, 0))
        fx, fy = px + dx, py + dy
        if (fx, fy) not in free_cells:
            # port front blocked — skip 不短路 model. paradigm 测的是 front-clear 之上 capacity 冲突
            blocked_port_count += 1
            continue
        u_var = u_vars.get((commodity, fx, fy))
        if u_var is None:
            continue
        model.Add(u_var == 1)
        forced_port_count += 1

    build_wall = time.perf_counter() - t_build0
    try:
        constraints_count = len(model.Proto().constraints)
    except Exception:
        constraints_count = -1

    # Solve with 600s budget, single worker for determinism
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8

    gc.collect()
    rss_pre_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

    t_solve0 = time.perf_counter()
    status = solver.Solve(model)
    solve_wall = time.perf_counter() - t_solve0

    rss_post_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

    status_str = {
        cp_model.OPTIMAL: "OPTIMAL/SAT",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(status, f"UNKNOWN_STATUS_{status}")

    return {
        "free_cells_count": len(free_cells),
        "commodities_count": len(commodities),
        "u_vars_count": len(u_vars),
        "constraints_count": constraints_count,
        "build_wall_s": round(build_wall, 2),
        "solve_wall_s": round(solve_wall, 2),
        "solve_status": status_str,
        "blocked_port_count": blocked_port_count,
        "forced_port_count": forced_port_count,
        "rss_pre_mb": round(rss_pre_mb, 1),
        "rss_post_mb": round(rss_post_mb, 1),
    }


def _capture_layout_and_probe():
    """Monkey-patch binding.solve to capture layout + port_specs, then run Candidate D model."""
    import src.models.binding_subproblem as bm

    captured: Dict[str, Any] = {"done": False}
    orig_solve = bm.PortBindingModel.solve

    def patched_solve(self, time_limit_seconds: float = 30.0) -> str:
        binding_result = orig_solve(self, time_limit_seconds=time_limit_seconds)
        if captured["done"]:
            return binding_result
        if binding_result not in ("FEASIBLE", "OPTIMAL"):
            captured["binding_status"] = binding_result
            return binding_result
        try:
            port_specs = self.extract_port_specs()
        except Exception as exc:
            print(f"  [capture] extract_port_specs failed: {exc}", flush=True)
            return binding_result

        occupied: Set[Tuple[int, int]] = set()
        for iid, sol in self.placement_solution.items():
            tpl = str(sol.get("facility_type", ""))
            pool = self.facility_pools.get(tpl, [])
            pose_idx = int(sol.get("pose_idx", -1))
            if pose_idx < 0 or pose_idx >= len(pool):
                continue
            for cell in pool[pose_idx].get("occupied_cells", []) or []:
                occupied.add((int(cell[0]), int(cell[1])))

        captured["binding_status"] = binding_result
        captured["port_spec_count"] = len(port_specs)
        captured["owners_count"] = len(self.placement_solution)

        print(
            f"  [capture] binding OK, ports={len(port_specs)} occupied={len(occupied)}; "
            f"building Candidate D model + solving (600s budget)...",
            flush=True,
        )
        try:
            result = _build_and_solve_candidate_d(occupied, port_specs, time_limit=600.0)
            captured.update(result)
            print(
                f"  [candidate-d] vars={result['u_vars_count']} cstr={result['constraints_count']} "
                f"build={result['build_wall_s']}s solve={result['solve_wall_s']}s "
                f"status={result['solve_status']} rss={result['rss_post_mb']}MB",
                flush=True,
            )
        except Exception as exc:
            captured["candidate_d_error"] = f"{type(exc).__name__}: {exc}"
            print(f"  [candidate-d] error: {exc}", flush=True)

        captured["done"] = True
        return binding_result

    bm.PortBindingModel.solve = patched_solve
    return captured, lambda: setattr(bm.PortBindingModel, "solve", orig_solve)


def probe_one_anchor(ghost_w: int, ghost_h: int, ax: int, ay: int, label: str) -> Dict[str, Any]:
    _reset_env(ax, ay)
    captured, restore = _capture_layout_and_probe()

    print(f"\n>>> {label}: {ghost_w}×{ghost_h} ({ax},{ay})", flush=True)
    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    try:
        outer_status, _ = run_benders_for_ghost_rect(
            ghost_w=ghost_w, ghost_h=ghost_h,
            max_iterations=1,
            project_root=Path("."),
            solve_mode="certified_exact",
            master_seconds=180.0,
            binding_seconds=30.0,
            routing_seconds=60.0,
            flow_seconds=10.0,
            campaign=None,
            session=None,
            disable_master_warm_start=True,
        )
    except Exception as exc:
        restore()
        return {
            "label": label, "anchor": (ax, ay), "ghost_size": (ghost_w, ghost_h),
            "outer_status": f"ERROR: {type(exc).__name__}: {exc}",
            "elapsed_s": round(time.perf_counter() - t0, 1),
        }
    restore()
    elapsed = round(time.perf_counter() - t0, 1)

    record: Dict[str, Any] = {
        "label": label,
        "anchor": (ax, ay),
        "ghost_size": (ghost_w, ghost_h),
        "outer_status": outer_status,
        "elapsed_s": elapsed,
        "captured": captured.get("done", False),
    }
    record.update({k: v for k, v in captured.items() if k != "done"})

    if captured.get("done"):
        status = record.get("solve_status", "")
        wall = record.get("solve_wall_s", 99999)
        vars_count = record.get("u_vars_count", 999999)
        cstr = record.get("constraints_count", 999999)
        rss = record.get("rss_post_mb", 999999)
        record["pre1_infeasible_in_budget"] = status == "INFEASIBLE" and wall <= 600
        record["pre1_feasible"] = status in {"OPTIMAL/SAT", "FEASIBLE"}
        record["pre1_unknown_timeout"] = status == "UNKNOWN" or wall > 600
        record["pre2_vars_ok"] = vars_count <= 250_000
        record["pre2_cstr_ok"] = cstr <= 650_000
        record["pre2_rss_ok"] = rss <= 12 * 1024
        record["pre2_all_ok"] = record["pre2_vars_ok"] and record["pre2_cstr_ok"] and record["pre2_rss_ok"]

    return record


def main() -> int:
    print("=== Candidate D (Path 17) Phase 0 cheap gate ===")
    print("  8 anchor × (pose-bool master + binding solve + Candidate D D1 model build/solve 600s)\n")

    results: List[Dict[str, Any]] = []
    for cfg in ANCHORS:
        results.append(probe_one_anchor(*cfg))

    print("\n=== Phase 0 verdict ===")
    print(f"{'label':30s} {'outer':12s} {'D-status':14s} {'wall':>7s} {'vars':>8s} {'cstr':>8s} {'rss_mb':>8s} {'Pre1':>6s} {'Pre2':>6s}")

    pre1_infeasible_count = 0
    pre1_feasible_count = 0
    pre1_unknown_count = 0
    pre2_pass_count = 0
    pre_eligible = 0

    for r in results:
        ds = r.get("solve_status", "?")
        wall = r.get("solve_wall_s", "?")
        v = r.get("u_vars_count", "?")
        c = r.get("constraints_count", "?")
        rss = r.get("rss_post_mb", "?")
        pre1 = r.get("pre1_infeasible_in_budget", False)
        pre2 = r.get("pre2_all_ok", False)
        p1 = "INF" if pre1 else ("FEA" if r.get("pre1_feasible") else ("UNK" if r.get("pre1_unknown_timeout") else "-"))
        p2 = "OK" if pre2 else "FAIL"
        print(f"{r['label']:30s} {r['outer_status']:12s} {str(ds):14s} {str(wall):>7s} {str(v):>8s} {str(c):>8s} {str(rss):>8s} {p1:>6s} {p2:>6s}")
        if r.get("captured"):
            pre_eligible += 1
            if pre1:
                pre1_infeasible_count += 1
            if r.get("pre1_feasible"):
                pre1_feasible_count += 1
            if r.get("pre1_unknown_timeout"):
                pre1_unknown_count += 1
            if pre2:
                pre2_pass_count += 1

    print(f"\nPre1 (Candidate D INFEASIBLE in 600s): INF={pre1_infeasible_count}/{pre_eligible}, FEA={pre1_feasible_count}, UNK/TIMEOUT={pre1_unknown_count}")
    print(f"Pre2 (vars ≤250K + cstr ≤650K + RSS ≤12GB): {pre2_pass_count}/{pre_eligible}")

    out = {
        "phase": "Candidate D (Path 17) Phase 0 cheap gate — D1 simplification (u vars only, no e/arc, no layer)",
        "scope_note": "Phase 0 only validates D1 cheap version (cell × commodity occupancy + cell capacity + port-front adherence). Phase 1+ would add e[k,arc] directed arcs + connectivity/flow conservation per GPT v7 plan Candidate D 完整描述.",
        "wall_budget_seconds": 600.0,
        "anchors_run": len(results),
        "pre_eligible_anchors": pre_eligible,
        "pre1_infeasible_count": pre1_infeasible_count,
        "pre1_feasible_count": pre1_feasible_count,
        "pre1_unknown_count": pre1_unknown_count,
        "pre2_all_ok_count": pre2_pass_count,
        "results": results,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[dumped] {OUT_FILE}")

    pre1_go = pre1_infeasible_count >= 5
    pre2_go = pre2_pass_count >= 5

    if pre1_go and pre2_go:
        print(">>> ✅ Phase 0 GO — D1 INFEASIBLE 在 budget 内 + 资源 OK. Investigate Phase 1 (加 connectivity vars).")
        return 0
    if pre1_feasible_count >= 3:
        print(f">>> ❌ D1 太松 — {pre1_feasible_count}/7 anchor FEASIBLE. port-front-clear 之外没增量信息. paradigm 需 Phase 1 连通性才有意义.")
    if pre1_unknown_count >= 3:
        print(f">>> ❌ Wall 不够 — {pre1_unknown_count}/7 anchor UNKNOWN/TIMEOUT at 600s. 10x budget 仍不够.")
    if not pre2_go:
        print(f">>> ❌ 资源不 fit ({pre2_pass_count}/7 anchor 资源 OK). 即使时间够, vars/RSS 撞 cap.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

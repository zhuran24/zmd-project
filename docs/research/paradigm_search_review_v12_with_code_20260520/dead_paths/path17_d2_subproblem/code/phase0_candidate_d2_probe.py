"""Candidate D (Path 17) Phase 0b — D2 加 arc + flow conservation probe.

D2 在 D1 (u vars + cell capacity + port front adherence) 之上加:
- e[k, arc] ∈ {0,1}: commodity k 是否走 directed arc (从 c1 到 c2)
- channeling: e[k, (c1,c2)] => u[k,c1] AND u[k,c2]
- flow conservation per (commodity, cell):
    in_flow(k, c) - out_flow(k, c) = terminal_balance(k, c)
    其中 terminal_balance = #input_ports_at_c - #output_ports_at_c (commodity k)

D2 才是 GPT v7 plan Candidate D 完整 directed-arc skeleton + flow conservation 版本.
D1 实测 NO-GO (5/7 anchor FEASIBLE, 跟 production routing precheck 无增量), 必须 D2 才能
test paradigm 是否有 connectivity-level 增量信号.

预估资源:
- u vars: K * |free_cells| ≈ 10 * 1200 = 12K
- e vars: K * 4 * |free_cells| ≈ 10 * 4 * 1200 = 48K (4 dir per cell, some arcs point out of free_cells, drop)
- total vars: ~60K
- constraints: capacity ~1200 + channeling ~96K + flow conservation ~12K = ~110K
- 在 cap 内 (vars ≤ 250K, cstr ≤ 650K)

GO: ≥5/7 anchor INFEASIBLE in 600s + 资源 OK
NO-GO: ≥3 TIMEOUT (跟 Path 08 同 dead zone) 或 ≥3 FEASIBLE (D2 仍无增量)
"""

from __future__ import annotations

import gc
import json
import os
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ortools.sat.python import cp_model

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT_FILE = Path("paths/17_candidate_d_commodity_flow/phase0_candidate_d2_stats.json")

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


def _build_and_solve_candidate_d2(
    occupied: Set[Tuple[int, int]],
    port_specs: List[Dict[str, Any]],
    time_limit: float = 600.0,
) -> Dict[str, Any]:
    """Build D2 (u + e arc + channeling + flow conservation) and solve."""
    free_cells: Set[Tuple[int, int]] = {
        (x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occupied
    }
    commodities = sorted({str(ps["commodity"]) for ps in port_specs})

    model = cp_model.CpModel()
    t_build0 = time.perf_counter()

    # u[k, c] BoolVar — commodity k uses cell c
    u_vars: Dict[Tuple[str, int, int], Any] = {}
    for k in commodities:
        for (x, y) in free_cells:
            u_vars[(k, x, y)] = model.NewBoolVar(f"u_{k}_{x}_{y}")

    # e[k, (c1, c2)] BoolVar — commodity k uses directed arc from c1 to c2
    e_vars: Dict[Tuple[str, int, int, int, int], Any] = {}
    for k in commodities:
        for (x, y) in free_cells:
            for d, (dx, dy) in DIR_DELTA.items():
                nx, ny = x + dx, y + dy
                if (nx, ny) not in free_cells:
                    continue
                e_vars[(k, x, y, nx, ny)] = model.NewBoolVar(f"e_{k}_{x}_{y}_{nx}_{ny}")

    # capacity: sum_k u[k, c] <= 1 per cell
    for (x, y) in free_cells:
        cell_u_vars = [u_vars[(k, x, y)] for k in commodities]
        if cell_u_vars:
            model.AddAtMostOne(cell_u_vars)

    # channeling: e[k, (c1, c2)] => u[k, c1] AND u[k, c2]
    for (k, x1, y1, x2, y2), e_var in e_vars.items():
        model.AddImplication(e_var, u_vars[(k, x1, y1)])
        model.AddImplication(e_var, u_vars[(k, x2, y2)])

    # Build terminal balance per (commodity, cell): output_ports at front cell = sources (+1),
    # input_ports at front cell = sinks (-1).
    # 实际 production routing 里 output port means "facility 产 commodity", 它要走到某个 input port.
    # 所以 output port front cell 是 source (有 +1 net out_flow), input port front cell 是 sink (+1 net in_flow).
    terminal_balance: Dict[Tuple[str, int, int], int] = defaultdict(int)
    blocked_port_count = 0
    forced_port_count = 0
    forced_source_ports: Dict[Tuple[str, int, int], int] = defaultdict(int)
    forced_sink_ports: Dict[Tuple[str, int, int], int] = defaultdict(int)
    for ps in port_specs:
        px, py = int(ps["x"]), int(ps["y"])
        direction = str(ps.get("dir", ""))
        commodity = str(ps.get("commodity", ""))
        port_type = str(ps.get("type", ""))
        if commodity not in {k for k in commodities}:
            continue
        dx, dy = DIR_DELTA.get(direction, (0, 0))
        fx, fy = px + dx, py + dy
        if (fx, fy) not in free_cells:
            blocked_port_count += 1
            continue
        # port_type == "out": owner facility 产 commodity 输出, front cell 必须有 commodity 流出 → source
        # port_type == "in": owner facility 收 commodity 输入, front cell 必须有 commodity 流入 → sink
        if port_type == "out":
            terminal_balance[(commodity, fx, fy)] += 1  # net out_flow = +1 (产)
            forced_source_ports[(commodity, fx, fy)] += 1
        elif port_type == "in":
            terminal_balance[(commodity, fx, fy)] -= 1  # net in_flow = +1 → net out_flow = -1
            forced_sink_ports[(commodity, fx, fy)] += 1
        else:
            continue
        # force u[k, front_cell] = 1
        u_var = u_vars.get((commodity, fx, fy))
        if u_var is not None:
            model.Add(u_var == 1)
        forced_port_count += 1

    # flow conservation per (commodity, cell): out_flow - in_flow = terminal_balance
    # out_flow(k, c) = sum_{(c, c') arc} e[k, (c, c')]
    # in_flow(k, c) = sum_{(c', c) arc} e[k, (c', c)]
    out_arcs_by_kc: Dict[Tuple[str, int, int], List[Any]] = defaultdict(list)
    in_arcs_by_kc: Dict[Tuple[str, int, int], List[Any]] = defaultdict(list)
    for (k, x1, y1, x2, y2), e_var in e_vars.items():
        out_arcs_by_kc[(k, x1, y1)].append(e_var)
        in_arcs_by_kc[(k, x2, y2)].append(e_var)

    for k in commodities:
        for (x, y) in free_cells:
            out_flow = sum(out_arcs_by_kc[(k, x, y)])
            in_flow = sum(in_arcs_by_kc[(k, x, y)])
            balance = terminal_balance.get((k, x, y), 0)
            model.Add(out_flow - in_flow == balance)

    build_wall = time.perf_counter() - t_build0
    try:
        constraints_count = len(model.Proto().constraints)
    except Exception:
        constraints_count = -1

    # Solve with budget
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
        "e_vars_count": len(e_vars),
        "total_vars_count": len(u_vars) + len(e_vars),
        "constraints_count": constraints_count,
        "build_wall_s": round(build_wall, 2),
        "solve_wall_s": round(solve_wall, 2),
        "solve_status": status_str,
        "blocked_port_count": blocked_port_count,
        "forced_port_count": forced_port_count,
        "forced_source_count": sum(forced_source_ports.values()),
        "forced_sink_count": sum(forced_sink_ports.values()),
        "rss_pre_mb": round(rss_pre_mb, 1),
        "rss_post_mb": round(rss_post_mb, 1),
    }


def _capture_layout_and_probe():
    """Monkey-patch binding.solve to capture layout + port_specs, then run D2 model."""
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
            f"building Candidate D2 model + solving (600s budget)...",
            flush=True,
        )
        try:
            result = _build_and_solve_candidate_d2(occupied, port_specs, time_limit=600.0)
            captured.update(result)
            print(
                f"  [candidate-d2] u={result['u_vars_count']} e={result['e_vars_count']} "
                f"cstr={result['constraints_count']} build={result['build_wall_s']}s "
                f"solve={result['solve_wall_s']}s status={result['solve_status']} "
                f"rss={result['rss_post_mb']}MB",
                flush=True,
            )
        except Exception as exc:
            captured["candidate_d2_error"] = f"{type(exc).__name__}: {exc}"
            print(f"  [candidate-d2] error: {exc}", flush=True)

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
        total_vars = record.get("total_vars_count", 999999)
        cstr = record.get("constraints_count", 999999)
        rss = record.get("rss_post_mb", 999999)
        record["pre1_infeasible_in_budget"] = status == "INFEASIBLE" and wall <= 600
        record["pre1_feasible"] = status in {"OPTIMAL/SAT", "FEASIBLE"}
        record["pre1_unknown_timeout"] = status == "UNKNOWN" or wall > 600
        record["pre2_vars_ok"] = total_vars <= 250_000
        record["pre2_cstr_ok"] = cstr <= 650_000
        record["pre2_rss_ok"] = rss <= 12 * 1024
        record["pre2_all_ok"] = record["pre2_vars_ok"] and record["pre2_cstr_ok"] and record["pre2_rss_ok"]

    return record


def main() -> int:
    print("=== Candidate D2 (Path 17 Phase 0b) — D1 + arc + flow conservation ===")
    print("  8 anchor × (pose-bool master + binding solve + D2 model build/solve 600s)\n")

    results: List[Dict[str, Any]] = []
    for cfg in ANCHORS:
        results.append(probe_one_anchor(*cfg))

    print("\n=== Phase 0b verdict ===")
    print(f"{'label':30s} {'outer':12s} {'D-status':14s} {'wall':>7s} {'vars':>8s} {'cstr':>8s} {'rss_mb':>8s} {'Pre1':>6s} {'Pre2':>6s}")

    pre1_infeasible_count = 0
    pre1_feasible_count = 0
    pre1_unknown_count = 0
    pre2_pass_count = 0
    pre_eligible = 0

    for r in results:
        ds = r.get("solve_status", "?")
        wall = r.get("solve_wall_s", "?")
        v = r.get("total_vars_count", "?")
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

    print(f"\nPre1 (D2 INFEASIBLE in 600s): INF={pre1_infeasible_count}/{pre_eligible}, FEA={pre1_feasible_count}, UNK/TIMEOUT={pre1_unknown_count}")
    print(f"Pre2 (total_vars ≤250K + cstr ≤650K + RSS ≤12GB): {pre2_pass_count}/{pre_eligible}")

    out = {
        "phase": "Candidate D2 (Path 17 Phase 0b) — D1 + arc + flow conservation",
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
        print(">>> ✅ Phase 0b GO — D2 INFEASIBLE 在 budget 内 + 资源 OK. Investigate Phase 1 production integration.")
        return 0
    if pre1_feasible_count >= 3:
        print(f">>> ❌ D2 仍太松 — {pre1_feasible_count}/7 anchor FEASIBLE. flow conservation 也没足够信息. paradigm 退化.")
    if pre1_unknown_count >= 3:
        print(f">>> ❌ D2 wall 不够 — {pre1_unknown_count}/7 anchor UNKNOWN/TIMEOUT at 600s. 跟 Path 08 同 dead zone.")
    if not pre2_go:
        print(f">>> ❌ D2 资源不 fit ({pre2_pass_count}/7 anchor 资源 OK).")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""GOC-C2 (Path 16) Phase 0 cheap gate — Pre1 + Pre2 资源 baseline.

针对 GOC paradigm 6 个前提中**最高风险的 2 个**:

- **Pre1**: V(L) all-active (S = A(L)) 在 production C2 全图 routing 模型上能 in ≤25s 给
  INFEASIBLE. GOC paradigm 假设 production routing 在 master OPTIMAL layout 上
  INFEASIBLE 是 norm (Path 11 + Path 14 evidence).
- **Pre2**: V(L) 全图模型资源 OK (vars ≤ 180K, constraints ≤ 650K, peak RSS ≤ 12 GB).
  GOC variant 是 production routing + 加 owner-optional BoolVars (~266 微小增量) +
  virtual terminal 放宽; production routing baseline 是 GOC 资源下界.

不做的 (cost 太高, Phase 1+ 范畴):
- binding existential 实现
- virtual terminal relaxation 实现
- QuickXplain core minimization
- master cut accumulation test (3 cut after master ≤60s OPTIMAL)

Scope: 单 file ~250 LOC, ~1-1.5h Claude pace. 不改 production code.

输出 paths/16_global_optional_owner_core/phase0_goc_stats.json.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT_FILE = Path("paths/16_global_optional_owner_core/phase0_goc_stats.json")

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


def _capture_and_probe_full_routing():
    """Monkey-patch binding.solve to: capture port_specs, then build a GOC-style full-grid
    routing model on the 70x70 grid, solve with ≤25s budget, record metrics.

    GOC variant simulation: monkey-patch analyze_exact_routing_domain to always return
    status='feasible' with active_cells = all free_cells per commodity. This is the
    maximal relaxation (virtual terminal: any free cell can carry any commodity flow),
    so production routing precheck's front_blocked early-reject is bypassed and
    RoutingSubproblem builds full vars/constraints.
    """
    import src.models.binding_subproblem as bm
    import src.models.routing_subproblem as rsm
    from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem, GRID_W, GRID_H

    # Save originals for restore
    orig_solve = bm.PortBindingModel.solve
    orig_analyze = rsm.analyze_exact_routing_domain

    def _goc_analyze_override(*args, **kwargs):
        """Force status='feasible' + active_cells = full free_cells set per commodity.
        Resolves grid → free_cells, then enumerates commodities from port_specs."""
        grid = kwargs.get("grid")
        if grid is None and args:
            grid = args[0]
        port_specs = kwargs.get("port_specs")
        if port_specs is None and grid is not None:
            port_specs = getattr(grid, "port_specs", [])
        if port_specs is None:
            port_specs = []
        free_cells = set(getattr(grid, "free_cells", set())) if grid is not None else set()
        if not free_cells:
            free_cells = {(x, y) for x in range(GRID_W) for y in range(GRID_H)}
        commodities = sorted({str(ps.get("commodity", "")) for ps in port_specs})
        active = {c: free_cells for c in commodities}
        component_cells = {c: free_cells for c in commodities}
        return {
            "status": "feasible",
            "binding_selection_safe_reject": False,
            "placement_level_conflict_set": [],
            "blocked_ports": [],
            "disconnected_commodities": [],
            "commodity_front_metadata": {},
            "commodity_component_cells": {c: sorted(list(cells)) for c, cells in component_cells.items()},
            "commodity_active_cells": {c: sorted(list(cells)) for c, cells in active.items()},
            "domain_stats": {
                "commodity_component_cells": {c: len(cells) for c, cells in component_cells.items()},
                "commodity_active_cells": {c: len(cells) for c, cells in active.items()},
                "domain_cells": sum(len(cells) for cells in active.values()),
                "terminal_core_cells": 0,
                "front_terminal_cells": 0,
                "blocked_ports": 0,
                "disconnected_commodity_count": 0,
            },
        }

    rsm.analyze_exact_routing_domain = _goc_analyze_override
    # Also need to silence the routing precheck path called from benders_loop's
    # _run_exact_binding_and_routing — it uses run_exact_routing_precheck which
    # internally calls analyze. Since the precheck wraps analyze, the override
    # propagates. But benders_loop itself reacts to precheck_status='front_blocked'
    # to add cuts and skip routing.solve. We don't care about that branch here
    # because we run routing build/solve manually inside patched_solve.

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

        # placement → occupied
        occupied: Set[Tuple[int, int]] = set()
        occupied_owner: Dict[Tuple[int, int], str] = {}
        for iid, sol in self.placement_solution.items():
            tpl = str(sol.get("facility_type", ""))
            pool = self.facility_pools.get(tpl, [])
            pose_idx = int(sol.get("pose_idx", -1))
            if pose_idx < 0 or pose_idx >= len(pool):
                continue
            for cell in pool[pose_idx].get("occupied_cells", []) or []:
                cell_t = (int(cell[0]), int(cell[1]))
                occupied.add(cell_t)
                occupied_owner[cell_t] = str(iid)

        commodities = sorted({str(ps["commodity"]) for ps in port_specs})
        captured["binding_status"] = binding_result
        captured["port_spec_count"] = len(port_specs)
        captured["commodities_count"] = len(commodities)
        captured["owners_count"] = len(self.placement_solution)

        # Pre1+Pre2: build full RoutingSubproblem, solve with 25s budget, collect metrics
        try:
            gc.collect()
            rss_pre_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
            grid = RoutingGrid(
                occupied_cells=occupied,
                port_specs=port_specs,
                occupied_owner_by_cell=occupied_owner,
            )
            sub = RoutingSubproblem(grid, commodities)
            t_build_0 = time.perf_counter()
            sub.build(time_limit=60.0)  # build is cheap; solve is the timed part
            build_wall = time.perf_counter() - t_build_0
            build_stats = dict(sub.build_stats)
            state_space = dict(build_stats.get("state_space", {})) if "state_space" in build_stats else {}
            captured["routing_build_wall_s"] = round(build_wall, 2)
            captured["routing_var_count"] = int(state_space.get("vars", 0)) if state_space else 0
            try:
                proto_constraints = len(sub.model.Proto().constraints)
            except Exception:
                proto_constraints = -1
            captured["routing_constraint_count"] = int(proto_constraints)

            t_solve_0 = time.perf_counter()
            solve_status = sub.solve(time_limit=25.0)
            solve_wall = time.perf_counter() - t_solve_0
            rss_post_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
            captured["routing_solve_status"] = solve_status
            captured["routing_solve_wall_s"] = round(solve_wall, 2)
            captured["rss_pre_mb"] = round(rss_pre_mb, 1)
            captured["rss_post_mb"] = round(rss_post_mb, 1)
            captured["rss_delta_mb"] = round(rss_post_mb - rss_pre_mb, 1)
            captured["build_stats_summary"] = {
                "state_space": state_space,
                "port_adherence": dict(build_stats.get("port_adherence", {})),
                "domain_analysis": dict(build_stats.get("domain_analysis", {})),
            }
        except Exception as exc:
            captured["routing_error"] = f"{type(exc).__name__}: {exc}"

        captured["done"] = True
        return binding_result

    bm.PortBindingModel.solve = patched_solve

    def restore():
        bm.PortBindingModel.solve = orig_solve
        rsm.analyze_exact_routing_domain = orig_analyze

    return captured, restore


def probe_one_anchor(ghost_w: int, ghost_h: int, ax: int, ay: int, label: str) -> Dict[str, Any]:
    _reset_env(ax, ay)
    captured, restore = _capture_and_probe_full_routing()

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
    record.update({
        k: v for k, v in captured.items()
        if k not in {"done", "build_stats_summary"}
    })
    if "build_stats_summary" in captured:
        record["build_stats_summary"] = captured["build_stats_summary"]

    # Pre1 + Pre2 verdict per anchor:
    rss_ok = captured.get("rss_post_mb", 999999) <= 12 * 1024  # 12 GB in MB
    vars_ok = captured.get("routing_var_count", 999999) <= 180_000
    cstr_ok = captured.get("routing_constraint_count", 999999) <= 650_000
    solve_wall = captured.get("routing_solve_wall_s", 99999)
    wall_ok = solve_wall <= 25.0
    status = captured.get("routing_solve_status", "")
    pre1_infeasible = status == "INFEASIBLE"
    pre1_feasible = status == "FEASIBLE"
    pre1_unknown = status in {"UNKNOWN", "TIMEOUT", ""}

    record["pre1_infeasible"] = pre1_infeasible
    record["pre1_feasible"] = pre1_feasible
    record["pre1_unknown"] = pre1_unknown
    record["pre2_vars_ok"] = vars_ok
    record["pre2_cstr_ok"] = cstr_ok
    record["pre2_rss_ok"] = rss_ok
    record["pre2_wall_ok"] = wall_ok
    record["pre2_all_ok"] = vars_ok and cstr_ok and rss_ok and wall_ok

    print(
        f"    outer={outer_status} captured={record['captured']} "
        f"routing_status={status} wall={solve_wall}s "
        f"vars={captured.get('routing_var_count')} "
        f"rss={captured.get('rss_post_mb')}MB",
        flush=True,
    )
    return record


def main() -> int:
    print("=== GOC-C2 (Path 16) Phase 0 cheap gate (Pre1 + Pre2 资源 baseline) ===")
    print("  7 anchor × 1 iter master+binding, 全图 production routing solve ≤25s each\n")

    results: List[Dict[str, Any]] = []
    for cfg in ANCHORS:
        results.append(probe_one_anchor(*cfg))

    print("\n=== Phase 0 verdict ===")
    print(f"{'label':30s} {'outer':12s} {'routing':12s} {'wall':>7s} {'vars':>8s} {'cstr':>8s} {'rss_mb':>8s} {'Pre1':>6s} {'Pre2':>6s}")

    pre1_infeasible_count = 0
    pre1_feasible_count = 0
    pre1_unknown_count = 0
    pre2_pass_count = 0
    pre_eligible = 0  # corner negative excluded (master INFEASIBLE, no binding to probe)

    for r in results:
        rs = r.get("routing_solve_status", "?")
        wall = r.get("routing_solve_wall_s", "?")
        v = r.get("routing_var_count", "?")
        c = r.get("routing_constraint_count", "?")
        rss = r.get("rss_post_mb", "?")
        pre1 = r.get("pre1_infeasible", False)
        pre2 = r.get("pre2_all_ok", False)
        p1 = "INF" if pre1 else ("FEA" if r.get("pre1_feasible") else ("UNK" if r.get("pre1_unknown") else "-"))
        p2 = "OK" if pre2 else "FAIL"
        print(f"{r['label']:30s} {r['outer_status']:12s} {str(rs):12s} {str(wall):>7s} {str(v):>8s} {str(c):>8s} {str(rss):>8s} {p1:>6s} {p2:>6s}")
        if r.get("captured"):
            pre_eligible += 1
            if pre1:
                pre1_infeasible_count += 1
            if r.get("pre1_feasible"):
                pre1_feasible_count += 1
            if r.get("pre1_unknown"):
                pre1_unknown_count += 1
            if pre2:
                pre2_pass_count += 1

    print(f"\nPre1 (V(L) INFEASIBLE in 25s): INF={pre1_infeasible_count}/{pre_eligible}, FEA={pre1_feasible_count}, UNK/TIMEOUT={pre1_unknown_count}")
    print(f"Pre2 (vars ≤180K + cstr ≤650K + RSS ≤12GB + wall ≤25s): {pre2_pass_count}/{pre_eligible}")

    out = {
        "phase": "GOC-C2 Phase 0 cheap gate (Pre1 + Pre2 资源 baseline, full production routing on master OPTIMAL layout)",
        "scope_note": "Phase 0 ONLY validates Pre1 (V(L) INFEASIBLE in 25s) + Pre2 (resource fit) on full production routing. Phase 0 does NOT implement: binding existential / virtual terminal relaxation / QuickXplain / master cut. Those are Phase 1+ work. Production routing here is GOC paradigm's resource lower bound; GOC variant adds owner-optional BoolVars (+266) and virtual terminal relaxation (potential +49K vars). 实际 GOC vars ≈ baseline + 49K, must still fit 180K cap.",
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

    # GO criteria:
    #   - Pre1 INFEASIBLE ≥5/7 eligible (paradigm starting condition)
    #   - Pre2 all_ok ≥5/7 eligible (resource fit baseline)
    pre1_go = pre1_infeasible_count >= 5
    pre2_go = pre2_pass_count >= 5

    if pre1_go and pre2_go:
        print(">>> ✅ Phase 0 GO — Pre1 + Pre2 both pass. Investigate Phase 0b (virtual terminal relaxation) before committing to Phase 1.")
        return 0
    if not pre1_go:
        print(f">>> ❌ Pre1 NO-GO — production routing 在 master OPTIMAL layout 上不能稳定 INFEASIBLE in 25s (INF={pre1_infeasible_count}/7). GOC paradigm 起点不成立.")
    if not pre2_go:
        print(f">>> ❌ Pre2 NO-GO — production routing 资源已撞墙 (pass={pre2_pass_count}/7). GOC variant 加 owner-optional + virtual terminal 后必更糟.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""PCR-CUT Phase 1 — patch belt CP-SAT PoC on 8 anchors.

For each anchor:
  1. master OPTIMAL layout (1 iter)
  2. binding solves; capture port_specs + active_cells
  3. on the captured layout, find top-3 patch candidates (Phase 0 oracle)
  4. for each patch, instantiate PatchRoutingCore with per-owner assumption literals
  5. solve (5s budget); record status, wall, vars, constraints, INFEASIBLE-core size

GO: p95 solve ≤ 5s, vars p95 ≤ 160K, constraints p95 ≤ 500K, ≥ 3 anchors return INFEASIBLE
NO-GO: p95 > 15s 或 vars > 300K 或 all FEASIBLE/UNKNOWN.
"""

from __future__ import annotations
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

OUT_FILE = Path("docs/research/pcr_cut_patch_routing_conflict_20260519/phase1_patch_router_stats.json")

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


def _reset_env_for_run(ax: int, ay: int) -> None:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)


def _capture_layout_and_ports():
    """Patch binding.solve to capture placement_solution, port_specs, full active_cells.

    Active cells use the over-approximation 'all free cells', not routing-precheck-component
    cells — because master OPTIMAL layouts commonly leave routing precheck front-blocked
    even when binding solves FEASIBLE. PCR-CUT paradigm tests whether patch-belt CP-SAT
    can detect that infeasibility locally with a small assumption core.
    """
    import src.models.binding_subproblem as bm
    from src.models.routing_subproblem import GRID_W, GRID_H

    captured: Dict[str, Any] = {"done": False}
    orig_solve = bm.PortBindingModel.solve

    def patched_solve(self, time_limit_seconds: float = 30.0) -> str:
        result = orig_solve(self, time_limit_seconds=time_limit_seconds)
        if captured["done"]:
            return result
        if result not in ("FEASIBLE", "OPTIMAL"):
            return result
        try:
            port_specs = self.extract_port_specs()
        except Exception as exc:
            print(f"  [capture] extract_port_specs failed: {exc}", flush=True)
            return result

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

        free_cells: Set[Tuple[int, int]] = {
            (x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occupied
        }
        commodities = {str(ps["commodity"]) for ps in port_specs}
        active_cells: Dict[str, Set[Tuple[int, int]]] = {
            commodity: set(free_cells) for commodity in commodities
        }

        captured["done"] = True
        captured["placement_solution"] = dict(self.placement_solution)
        captured["facility_pools"] = dict(self.facility_pools)
        captured["instances_by_id"] = dict(self.instances_by_id)
        captured["port_specs"] = port_specs
        captured["occupied"] = occupied
        captured["occupied_owner"] = occupied_owner
        captured["active_cells"] = active_cells
        captured["domain_status"] = "over_approx_all_free"
        return result

    bm.PortBindingModel.solve = patched_solve
    return captured, lambda: setattr(bm.PortBindingModel, "solve", orig_solve)


def _find_top_patches(captured: Dict[str, Any], ghost_anchor: Tuple[int, int], ghost_size: Tuple[int, int]) -> List[Dict[str, Any]]:
    """Reuse phase0 oracle logic to find top-3 patches on the captured layout."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase0_patch_oracle_probe import analyze_patches  # type: ignore
    from src.models.routing_subproblem import GRID_W, GRID_H

    candidates, _, _ = analyze_patches(
        captured["placement_solution"], captured["facility_pools"], captured["instances_by_id"],
        GRID_W, GRID_H, ghost_anchor=ghost_anchor, ghost_size=ghost_size,
    )
    return [
        {"patch_id": c.patch_id, "cells": list(c.cells), "kind": c.kind, "bbox": list(c.bbox)}
        for c in candidates[:3]
    ]


def _build_patch_port_specs(patch_cells: Set[Tuple[int, int]], port_specs: List[Dict[str, Any]]) -> List[Any]:
    """Filter port_specs to ports whose port_cell lies in patch."""
    from src.models.patch_routing_core import PatchPortSpec
    out: List[PatchPortSpec] = []
    for ps in port_specs:
        cell = (int(ps["x"]), int(ps["y"]))
        if cell not in patch_cells:
            continue
        out.append(PatchPortSpec(
            instance_id=str(ps.get("instance_id", "")),
            x=int(ps["x"]),
            y=int(ps["y"]),
            direction=str(ps["dir"]),
            commodity=str(ps["commodity"]),
            type=str(ps["type"]),
            pose_idx=int(ps.get("pose_idx", -1)),
        ))
    return out


def _build_pose_assumptions(patch_port_specs: List[Any], placement_solution: Dict[str, Any]) -> List[Any]:
    """One assumption literal per (instance_id, pose_idx) touching this patch."""
    from src.models.patch_routing_core import PoseAssumption
    seen_instances: Set[str] = set()
    out: List[PoseAssumption] = []
    for ps in patch_port_specs:
        iid = ps.instance_id
        if iid in seen_instances:
            continue
        seen_instances.add(iid)
        pose_idx = int(placement_solution.get(iid, {}).get("pose_idx", -1))
        sig = f"{iid}_p{pose_idx}"
        out.append(PoseAssumption(
            instance_id=iid,
            pose_idx=pose_idx,
            local_signature=sig,
            assumption_name=f"assum_{iid}",
        ))
    return out


def _run_patch_solve(captured: Dict[str, Any], patch_meta: Dict[str, Any], time_limit: float = 5.0) -> Dict[str, Any]:
    from src.models.patch_routing_core import (
        PatchSpec,
        PatchRoutingCore,
    )

    patch_cells: Set[Tuple[int, int]] = {(int(c[0]), int(c[1])) for c in patch_meta["cells"]}
    patch_spec = PatchSpec.from_cells(patch_meta["patch_id"], patch_cells, source_witness={"kind": patch_meta["kind"], "bbox": patch_meta["bbox"]})
    patch_ports = _build_patch_port_specs(patch_cells, captured["port_specs"])
    pose_assumptions = _build_pose_assumptions(patch_ports, captured["placement_solution"])

    core = PatchRoutingCore(
        patch_spec=patch_spec,
        full_grid_occupied=captured["occupied"],
        full_grid_active_cells=captured["active_cells"],
        patch_port_specs=patch_ports,
        pose_assumptions=pose_assumptions,
        boundary_relaxation=True,
    )
    t0 = time.perf_counter()
    core.build()
    build_wall = time.perf_counter() - t0
    status = core.solve(time_limit=time_limit)
    result = core.build_result()
    return {
        "patch_id": patch_meta["patch_id"],
        "kind": patch_meta["kind"],
        "bbox": patch_meta["bbox"],
        "cells": len(patch_cells),
        "patch_ports": len(patch_ports),
        "assumptions": len(pose_assumptions),
        "build_wall_s": round(build_wall, 3),
        "solve_wall_s": result.wall_s,
        "var_count": result.var_count,
        "constraint_count": result.constraint_count,
        "status": result.status,
        "core_size": len(result.core),
        "stats": result.stats,
    }


def trial_one_anchor(ghost_w: int, ghost_h: int, ax: int, ay: int, label: str) -> Dict[str, Any]:
    _reset_env_for_run(ax, ay)
    captured, restore = _capture_layout_and_ports()
    print(f"\n>>> {label}: {ghost_w}×{ghost_h} ({ax},{ay})", flush=True)
    from src.search.benders_loop import run_benders_for_ghost_rect
    t0 = time.perf_counter()
    try:
        status, _ = run_benders_for_ghost_rect(
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
        return {"label": label, "anchor": (ax, ay), "outer_status": f"ERROR: {exc}", "elapsed_s": time.perf_counter() - t0, "patches": []}
    restore()
    elapsed = time.perf_counter() - t0
    print(f"    outer status: {status} elapsed={elapsed:.1f}s captured={captured.get('done')}", flush=True)

    if not captured.get("done"):
        return {"label": label, "anchor": (ax, ay), "outer_status": status, "elapsed_s": elapsed, "patches": [], "note": "no binding capture"}

    top_patches = _find_top_patches(captured, (ax, ay), (ghost_w, ghost_h))
    print(f"    found {len(top_patches)} candidate patches", flush=True)

    patch_results: List[Dict[str, Any]] = []
    for pm in top_patches:
        try:
            r = _run_patch_solve(captured, pm, time_limit=5.0)
        except Exception as exc:
            r = {"patch_id": pm["patch_id"], "error": str(exc)}
        patch_results.append(r)
        print(f"    patch {pm['patch_id']}: {r.get('status', 'ERR')} vars={r.get('var_count')} solve={r.get('solve_wall_s')}s", flush=True)

    return {
        "label": label,
        "anchor": (ax, ay),
        "outer_status": status,
        "elapsed_s": elapsed,
        "patches": patch_results,
    }


def main() -> int:
    print("=== PCR-CUT Phase 1 — 8-anchor patch belt CP-SAT PoC ===")

    results: List[Dict[str, Any]] = []
    for cfg in ANCHORS:
        results.append(trial_one_anchor(*cfg))

    # Aggregate metrics
    all_solve = []
    all_vars = []
    all_cstr = []
    anchor_infeasible_count = 0
    anchor_any_status: Dict[str, str] = {}
    for r in results:
        anchor_label = r["label"]
        statuses = [p.get("status") for p in r.get("patches", []) if "status" in p]
        anchor_any_status[anchor_label] = ",".join(statuses) if statuses else "NO_PATCH"
        for p in r.get("patches", []):
            if "error" in p:
                continue
            all_solve.append(p.get("solve_wall_s", 0))
            all_vars.append(p.get("var_count", 0))
            all_cstr.append(p.get("constraint_count", 0))
        if any(p.get("status") == "INFEASIBLE" for p in r.get("patches", [])):
            anchor_infeasible_count += 1

    def p95(xs):
        if not xs:
            return None
        s = sorted(xs)
        idx = max(0, min(len(s) - 1, int(round(0.95 * (len(s) - 1)))))
        return s[idx]

    summary = {
        "anchors_run": len(results),
        "anchor_infeasible_count": anchor_infeasible_count,
        "anchor_status_summary": anchor_any_status,
        "solve_wall_p95_s": p95(all_solve),
        "var_count_p95": p95(all_vars),
        "constraint_count_p95": p95(all_cstr),
        "solve_wall_max_s": max(all_solve, default=0),
        "var_count_max": max(all_vars, default=0),
        "constraint_count_max": max(all_cstr, default=0),
        "patches_total": len(all_solve),
    }

    out = {"summary": summary, "results": results}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[dumped] {OUT_FILE}")

    # GO/NO-GO verdict
    print("\n=== Phase 1 verdict ===")
    print(f"  patches solved: {len(all_solve)}")
    print(f"  p95 solve: {summary['solve_wall_p95_s']}s (target ≤ 5)")
    print(f"  p95 vars: {summary['var_count_p95']} (target ≤ 160K)")
    print(f"  p95 constraints: {summary['constraint_count_p95']} (target ≤ 500K)")
    print(f"  INFEASIBLE anchors: {anchor_infeasible_count}/{len(results)} (target ≥ 3)")

    p95_solve = summary["solve_wall_p95_s"] or 0
    p95_v = summary["var_count_p95"] or 0
    p95_c = summary["constraint_count_p95"] or 0

    go = (
        p95_solve <= 5.0
        and p95_v <= 160_000
        and p95_c <= 500_000
        and anchor_infeasible_count >= 3
    )
    if go:
        print(">>> ✅ Phase 1 GO")
        return 0
    if p95_solve > 15 or p95_v > 300_000:
        print(">>> ❌ NO-GO: resource blowup")
        return 1
    print(">>> 🟡 PARTIAL: 资源 OK 但 INFEASIBLE 数不够 / 边界 relaxation 过松, 需调参")
    return 1


if __name__ == "__main__":
    sys.exit(main())

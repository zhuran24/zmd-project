"""PGW (Positive Global Witness + UB Closure) Phase 0 cheap gate probe.

针对 v4 计划书的 6 个硬前提, 聚焦 2 个最高风险 — P0.1 + P0.3:

- **P0.1 C1 上界闭合**: 现 master OPT_C1 vs target_score (anchor 几何 max area). 实际数据
  上 Path 4-14 多次看到 master 出 OPTIMAL 但 routing 全堵 — 强烈暗示 OPT(R) > OPT(F).
- **P0.3 routing residual locality**: master OPTIMAL layout 的 routing residual 是否
  集中可 LNS repair (top-5 cluster ≥55% blocker / blocked owners ≤120 / SAC ≤5), 还是
  baseline 500-610 全域均匀坏 (Path 05/12/13/14 已观察后者).

8 anchor sample = Path 12/13/14 同 set, 方便 apples-to-apples.

不做的 (cost 太高 / 风险已知低):
- P0.2 seed compat (Plan B-self-seed 兜底, 总有 master OPTIMAL layout 当 seed)
- P0.4 fixed verifier 预算 (Path 14 已 routing solve 60s 内)
- P0.5 pinned master (Phase 2 才真用)
- P0.6 lift_count (设计上规避)

输出 `paths/15_positive_global_witness/phase0_pgw_stats.json`.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT_FILE = Path("paths/15_positive_global_witness/phase0_pgw_stats.json")

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


def _capture_master_and_binding():
    """Monkey-patch binding.solve to capture: master_obj_value (from ghost rect), placement,
    port_specs, blocked_ports from routing precheck, SAC violations."""
    import src.models.binding_subproblem as bm
    from src.models.routing_subproblem import (
        run_exact_routing_precheck,
        RoutingGrid,
        GRID_W,
        GRID_H,
    )
    from src.search.separator_capacity_separator import (
        analyze_layout_for_separator_violations,
    )

    captured: Dict[str, Any] = {"done": False}
    orig_solve = bm.PortBindingModel.solve

    def patched_solve(self, time_limit_seconds: float = 30.0) -> str:
        result = orig_solve(self, time_limit_seconds=time_limit_seconds)
        if captured["done"]:
            return result
        if result not in ("FEASIBLE", "OPTIMAL"):
            captured["binding_status"] = result
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

        # routing precheck — 拿 blocked_ports
        try:
            grid = RoutingGrid(
                occupied_cells=occupied,
                port_specs=port_specs,
                occupied_owner_by_cell=occupied_owner,
            )
            precheck = run_exact_routing_precheck(grid, occupied_owner_by_cell=occupied_owner)
        except Exception as exc:
            print(f"  [capture] routing_precheck failed: {exc}", flush=True)
            return result

        precheck_status = str(precheck.get("status", "feasible"))
        blocked_ports = list(precheck.get("blocked_ports", []))

        # blocked owners 统计 + top-K cluster coverage
        blocked_owner_set: Set[str] = set()
        blocked_cells_per_owner: Counter = Counter()
        for bp in blocked_ports:
            iid = str(bp.get("instance_id", ""))
            if iid:
                blocked_owner_set.add(iid)
                blocked_cells_per_owner[iid] += 1
            for bid in bp.get("placement_level_conflict_set", []) or []:
                blocked_owner_set.add(str(bid))

        # top-5 cluster coverage (blocked owners sorted by their blocker count)
        top5_owners = [iid for iid, _ in blocked_cells_per_owner.most_common(5)]
        top5_blocker_count = sum(blocked_cells_per_owner[iid] for iid in top5_owners)
        total_blocker_count = sum(blocked_cells_per_owner.values())
        top5_coverage = (
            top5_blocker_count / total_blocker_count if total_blocker_count > 0 else 0.0
        )

        # SAC violations
        try:
            sac_violations = analyze_layout_for_separator_violations(
                placement_solution=self.placement_solution,
                facility_pools=self.facility_pools,
                instances_by_id=self.instances_by_id,
                grid_w=GRID_W, grid_h=GRID_H,
                ghost_anchor=captured["ghost_anchor"],
                ghost_size=captured["ghost_size"],
                include_axis=True, include_ghost_moat=True,
                separator_limit=140,
            )
            sac_violation_count = sum(1 for v in sac_violations if getattr(v, "slack", 0) < 0)
        except Exception as exc:
            print(f"  [capture] SAC analysis failed: {exc}", flush=True)
            sac_violation_count = -1

        captured["done"] = True
        captured["binding_status"] = result
        captured["precheck_status"] = precheck_status
        captured["blocked_owner_count"] = len(blocked_owner_set)
        captured["blocked_ports_count"] = len(blocked_ports)
        captured["top5_blocker_owners"] = top5_owners
        captured["top5_blocker_count"] = top5_blocker_count
        captured["total_blocker_count"] = total_blocker_count
        captured["top5_blocker_coverage"] = round(top5_coverage, 3)
        captured["sac_violation_count"] = int(sac_violation_count)
        captured["port_spec_count"] = len(port_specs)
        return result

    bm.PortBindingModel.solve = patched_solve

    def restore():
        bm.PortBindingModel.solve = orig_solve

    return captured, restore


def probe_one_anchor(ghost_w: int, ghost_h: int, ax: int, ay: int, label: str) -> Dict[str, Any]:
    _reset_env(ax, ay)
    captured, restore = _capture_master_and_binding()
    captured["ghost_anchor"] = (ax, ay)
    captured["ghost_size"] = (ghost_w, ghost_h)

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
        return {
            "label": label, "anchor": (ax, ay), "ghost_size": (ghost_w, ghost_h),
            "outer_status": f"ERROR: {type(exc).__name__}",
            "elapsed_s": round(time.perf_counter() - t0, 1),
        }
    restore()
    elapsed = round(time.perf_counter() - t0, 1)

    target_area = ghost_w * ghost_h
    target_min_side = min(ghost_w, ghost_h)
    target_score = (target_area, target_min_side)

    # P0.1: master OPTIMAL on this candidate ⇒ UB_C1 ≥ target_score (it's a feasible candidate)
    # master_obj_value 不直接拿 — outer_status 在 UNPROVEN 时表示 master 在 iter 1 OPTIMAL 但
    # binding/routing reject. 这意味 candidate area=ghost_w*ghost_h 是 C1-feasible 上界.
    # 若 status==INFEASIBLE (corner negative), candidate C1-infeasible.
    p01_master_optimal = status in ("UNPROVEN", "CERTIFIED")
    p01_master_infeasible = status == "INFEASIBLE"

    record = {
        "label": label,
        "anchor": (ax, ay),
        "ghost_size": (ghost_w, ghost_h),
        "target_score": list(target_score),
        "outer_status": status,
        "elapsed_s": elapsed,
        "captured": captured.get("done", False),
        "p01_master_c1_feasible": p01_master_optimal,
        "p01_master_c1_infeasible": p01_master_infeasible,
    }

    if captured.get("done"):
        record["binding_status"] = captured["binding_status"]
        record["precheck_status"] = captured["precheck_status"]
        record["blocked_owner_count"] = captured["blocked_owner_count"]
        record["blocked_ports_count"] = captured["blocked_ports_count"]
        record["top5_blocker_owners"] = captured["top5_blocker_owners"]
        record["top5_blocker_count"] = captured["top5_blocker_count"]
        record["total_blocker_count"] = captured["total_blocker_count"]
        record["top5_blocker_coverage"] = captured["top5_blocker_coverage"]
        record["sac_violation_count"] = captured["sac_violation_count"]
        record["port_spec_count"] = captured["port_spec_count"]

        # P0.3 verdict per anchor (per v4 plan):
        # GO at-least-one-of: blocked_owner_count <= 120 OR top5_coverage >= 0.55 OR sac <= 5
        blocked_ok = captured["blocked_owner_count"] <= 120
        cluster_ok = captured["top5_blocker_coverage"] >= 0.55
        sac_ok = 0 <= captured["sac_violation_count"] <= 5
        record["p03_blocked_owner_ok"] = blocked_ok
        record["p03_top5_cluster_ok"] = cluster_ok
        record["p03_sac_violation_ok"] = sac_ok
        record["p03_any_locality_signal"] = blocked_ok or cluster_ok or sac_ok
    else:
        record["note"] = "binding never produced port_specs — capture incomplete"
        record["p03_any_locality_signal"] = False

    print(
        f"    outer={status} elapsed={elapsed}s "
        f"blocked_owners={record.get('blocked_owner_count', '?')} "
        f"top5_cov={record.get('top5_blocker_coverage', '?')} "
        f"sac={record.get('sac_violation_count', '?')}",
        flush=True,
    )
    return record


def main() -> int:
    print("=== PGW Phase 0 cheap gate probe (P0.1 + P0.3) ===")
    print("  8 anchor × 1 iter master, ≤30 min wall total expected\n")

    results: List[Dict[str, Any]] = []
    for cfg in ANCHORS:
        results.append(probe_one_anchor(*cfg))

    # Aggregate verdict
    print("\n=== Phase 0 verdict ===")
    print(f"{'label':30s} {'outer':12s} {'blocked':>8s} {'top5_cov':>9s} {'sac':>5s} {'P0.3':>8s}")
    p01_feasible = 0
    p01_infeasible_corner = 0
    p03_pass = 0
    p03_eligible = 0
    for r in results:
        bo = r.get("blocked_owner_count", "?")
        tc = r.get("top5_blocker_coverage", "?")
        sac = r.get("sac_violation_count", "?")
        p03 = r.get("p03_any_locality_signal", False)
        print(f"{r['label']:30s} {r['outer_status']:12s} {str(bo):>8s} {str(tc):>9s} {str(sac):>5s} {'GO' if p03 else 'NO-GO':>8s}")
        if r["p01_master_c1_feasible"]:
            p01_feasible += 1
        if r["p01_master_c1_infeasible"]:
            p01_infeasible_corner += 1
        if r.get("captured"):
            p03_eligible += 1
            if p03:
                p03_pass += 1

    print()
    print(f"P0.1 master C1-feasible (UNPROVEN/CERTIFIED): {p01_feasible}/8 (corner_negative INFEASIBLE = sound: {p01_infeasible_corner}/8)")
    print(f"P0.3 locality signal (any of: blocked≤120 / top5_cov≥0.55 / sac≤5): {p03_pass}/{p03_eligible} eligible anchors")

    # Verdict: P0.1 is GO if master OPTIMAL — but we still need to compare to true OPT(F).
    # We can't compute OPT(F) here (would need to find any FEASIBLE witness). So P0.1 partial verdict:
    # P0.1 confirmed: C1-OPTIMAL exists for target_score (UB_C1 ≥ target_score is implicit).
    # The HARD question — is UB_C1 == OPT(F)? — remains open until Phase 1+ finds a witness.
    # Phase 0 only checks "UB exists" not "UB closes".
    p01_partial_go = p01_feasible >= 4  # ≥ half non-corner anchors
    p03_go = p03_pass >= 4  # ≥ half eligible anchors show locality signal

    out = {
        "phase": "PGW Phase 0 cheap gate (P0.1 + P0.3 PoC)",
        "anchors_run": len(results),
        "p01_master_c1_feasible_count": p01_feasible,
        "p01_corner_negative_infeasible_count": p01_infeasible_corner,
        "p01_partial_go": p01_partial_go,
        "p01_caveat": "Phase 0 only checks UB_C1 exists, NOT that UB closes to OPT(F). True closure requires Phase 1+ witness.",
        "p03_locality_signal_pass": p03_pass,
        "p03_eligible_anchors": p03_eligible,
        "p03_go": p03_go,
        "results": results,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[dumped] {OUT_FILE}")

    if p01_partial_go and p03_go:
        print(">>> ✅ Phase 0 PARTIAL GO — P0.1 has UB candidates + P0.3 locality signal present. Investigate Phase 1+.")
        return 0
    if not p03_go:
        print(">>> ❌ P0.3 NO-GO — routing residual not local enough for LNS repair. PGW main line dead.")
    if not p01_partial_go:
        print(">>> ❌ P0.1 partial NO-GO — too few master C1-feasible anchors. Hard UB closure investigation needed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

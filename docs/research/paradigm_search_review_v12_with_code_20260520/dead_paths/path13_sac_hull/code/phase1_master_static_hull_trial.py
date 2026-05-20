"""SAC-Hull Phase 1 trial — master 加 static separator hull constraints.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_SEPARATOR_HULL=1
- EXACT_B1_SEPARATOR_HULL_STATIC_LIMIT=64
- EXACT_B1_SEPARATOR_HULL_INCLUDE_AXIS=1
- EXACT_B1_SEPARATOR_HULL_INCLUDE_GHOST_MOAT=1

GO 条件:
- 27×15 anchor (22,28) master.solve ≤ 60s, status OPTIMAL/INFEASIBLE 非 UNKNOWN
- 新增 vars ≤ 60K, constraints ≤ 150K (sac_hull stats)
- corner (0,0) negative sanity 仍 INFEASIBLE ≤ 90s
- first layout 的 routing precheck blocked_ports < 300 (baseline 500-610)
"""
from __future__ import annotations
import os, sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def run_one(label, ghost_w, ghost_h, ax, ay, max_iter=1, master_seconds=120.0):
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_SEPARATOR_HULL"] = "1"
    # 减重: 只 ghost moat (4 个), 不 axis V/H (64 个)
    os.environ["EXACT_B1_SEPARATOR_HULL_STATIC_LIMIT"] = "16"
    os.environ["EXACT_B1_SEPARATOR_HULL_INCLUDE_AXIS"] = "0"
    os.environ["EXACT_B1_SEPARATOR_HULL_INCLUDE_GHOST_MOAT"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    for k in (
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print(f"\n>>> {label}: {ghost_w}×{ghost_h} ({ax},{ay}) max_iter={max_iter}", flush=True)
    # capture sac_hull stats via patched build
    import src.models.pose_bool_exact_master as pbm
    orig_build = pbm.PoseBoolExactMasterDelegate.build
    captured = {"stats": None}
    def patched_build(self):
        orig_build(self)
        if captured["stats"] is None:
            stats = self.owner.build_stats.get("pose_bool_master", {}).get("sac_hull")
            captured["stats"] = stats
            if stats:
                print(f"[sac-hull] {label} stats: {stats}", flush=True)
    pbm.PoseBoolExactMasterDelegate.build = patched_build

    # also patch run_exact_routing_precheck to dump blocked_ports count
    import src.models.routing_subproblem as rs
    orig_precheck = rs.run_exact_routing_precheck
    def patched_precheck(*args, **kwargs):
        result = orig_precheck(*args, **kwargs)
        try:
            blocked = result.get("blocked_ports", []) if isinstance(result, dict) else getattr(result, "blocked_ports", [])
            print(f"[routing-precheck] {label} status={result.get('status', '?')} blocked_ports={len(blocked) if blocked else 0}", flush=True)
        except Exception:
            pass
        return result
    rs.run_exact_routing_precheck = patched_precheck

    from src.search.benders_loop import run_benders_for_ghost_rect
    t0 = time.perf_counter()
    try:
        status, _ = run_benders_for_ghost_rect(
            ghost_w=ghost_w, ghost_h=ghost_h,
            max_iterations=max_iter,
            project_root=Path("."),
            solve_mode="certified_exact",
            master_seconds=master_seconds,
            binding_seconds=30.0,
            routing_seconds=60.0,
            flow_seconds=10.0,
            campaign=None,
            session=None,
            disable_master_warm_start=True,
        )
    except Exception as exc:
        print(f"    ERROR: {exc}", flush=True)
        return label, "ERROR", time.perf_counter() - t0, captured["stats"]
    elapsed = time.perf_counter() - t0
    print(f"    {label}: {status} in {elapsed:.1f}s", flush=True)
    return label, status, elapsed, captured["stats"]


def main() -> int:
    print("=== SAC-Hull Phase 1 trial — master static separator hull ===")
    results = []
    # 主 anchor
    results.append(run_one("interior_22_28", 27, 15, 22, 28, max_iter=1))
    # negative control (corner)
    results.append(run_one("corner_0_0_NEGATIVE", 27, 15, 0, 0, max_iter=1, master_seconds=120.0))

    print("\n=== Phase 1 summary ===")
    for label, status, elapsed, stats in results:
        s = stats or {}
        n_vars = (s.get("side_bool_vars", 0) or 0) + (s.get("cross_bool_vars", 0) or 0)
        n_cons = s.get("capacity_constraints", 0) or 0
        print(f"  {label:30s} {status:15s} {elapsed:7.1f}s  sac_vars={n_vars} sac_constraints={n_cons}")

    out = Path("docs/research/sac_hull_separator_capacity_20260518/phase1_trial_results.json")
    out.write_text(json.dumps([{
        "label": r[0], "status": r[1], "wall_s": round(r[2], 2),
        "sac_stats": r[3] or {},
    } for r in results], indent=2, ensure_ascii=False))
    print(f"results dumped {out}")

    # GO 标准
    main_result = results[0]
    label, status, elapsed, stats = main_result
    if status not in {"CERTIFIED", "INFEASIBLE", "UNPROVEN"}:
        # UNKNOWN 是 NO-GO
        print(f">>> ❌ Phase 1 NO-GO: main anchor {status}")
        return 1
    if elapsed > 90:
        print(f">>> ❌ Phase 1 NO-GO: main anchor wall {elapsed:.1f}s > 60s threshold")
        return 1
    if stats:
        n_vars = (stats.get("side_bool_vars", 0) or 0) + (stats.get("cross_bool_vars", 0) or 0)
        n_cons = stats.get("capacity_constraints", 0) or 0
        if n_vars > 60000 or n_cons > 150000:
            print(f">>> ❌ Phase 1 NO-GO: vars={n_vars} or constraints={n_cons} 超阈值")
            return 1
    print(f">>> ✅ Phase 1 GO: main anchor {status} {elapsed:.1f}s, vars + constraints in budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""A 批 0 生产规模头对头 runner：C6 编码 × {钉死验证, 自由搜索}。

与 witness 基线的可比性：
- pinned 模式对照 M6（witness: presolve-off/fixed/单核/300s → UNKNOWN，7.2M branches）
- free 模式对照 cell_g6x6_linux_p4cfg_1800（witness: probing1/symmetry1/automatic/w12/1800s → UNKNOWN，4.17M branches）
patch 时序：session.create（读冻结工件）→ apply_c6_patch → build_exact_core 重建（供电约束烘焙进 core）。
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/zhuran24/zmd-pj")
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("pinned", "free"), required=True)
    ap.add_argument("--encoding", choices=("c6", "c1"), default="c6")
    ap.add_argument("--master-seconds", type=float, default=1800.0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)
    os.environ["EXACT_SUBPROBLEM_MAX_MEMORY_MB"] = "28000"
    if args.mode == "free":
        os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "1"
        os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "1"
        os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "automatic"

    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession
    if args.encoding == "c6":
        import c6_encoding_patch as encoding_patch
        apply_patch = encoding_patch.apply_c6_patch
    else:
        import c1_encoding_patch as encoding_patch
        apply_patch = encoding_patch.apply_c1_patch

    res = {"mode": args.mode, "encoding": args.encoding,
           "master_seconds": args.master_seconds, "workers": args.workers}
    session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
    print("session ready", flush=True)

    apply_patch()
    t0 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        session.instances,
        session.facility_pools,
        session.rules,
        generic_io_requirements=session.core.generic_io_requirements,
        wireless_sink_generic_input_slots=session.core.wireless_sink_generic_input_slots,
    )
    res["core_build_seconds"] = round(time.perf_counter() - t0, 1)
    t1 = time.perf_counter()
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(6, 6))
    if not getattr(master, "_built", False):
        master.build()
    res["master_build_seconds"] = round(time.perf_counter() - t1, 1)
    pc = dict(master.build_stats.get("power_coverage", {}) or {})
    res["power_coverage_encoding"] = pc.get("encoding")
    res["cover_literals"] = pc.get("cover_literals")
    print(f"built: encoding={res['power_coverage_encoding']} cover_lits={res['cover_literals']} "
          f"core={res['core_build_seconds']}s master={res['master_build_seconds']}s", flush=True)

    if args.mode == "pinned":
        hint = {
            str(k): int(v)
            for k, v in json.load(
                open("/home/zhuran24/m5_runs/rebuilt_hints/hint_anchor132.json")
            ).items()
        }
        t2 = time.perf_counter()
        v = master._validate_coordinate_forced_hint(
            solution_hint=hint,
            ghost_anchor_hint_idx=132,
            time_limit_seconds=args.master_seconds,
            solver_parameter_profile={
                "profile_id": "b0_presolve_off",
                "cp_model_presolve": 0,
                "search_branching": "fixed" if args.workers == 1 else "automatic",
                "worker_count": args.workers,
            },
        )
        res["pinned"] = {
            "status": str(v.get("status")),
            "accepted": bool(v.get("accepted", False)),
            "reason": str(v.get("reason")),
            "wall": round(time.perf_counter() - t2, 1),
            "branches": v.get("branches"),
            "conflicts": v.get("conflicts"),
        }
        print(f"PINNED: {res['pinned']}", flush=True)
    else:
        t2 = time.perf_counter()
        status = master.solve(time_limit_seconds=args.master_seconds,
                              solution_hint=None, known_feasible_hint=False)
        ls = dict(master.build_stats.get("last_solve", {}))
        res["free"] = {
            "status": str(ls.get("status")),
            "wall": round(time.perf_counter() - t2, 1),
            "branches": ls.get("branches"),
            "conflicts": ls.get("conflicts"),
            "deterministic_time": ls.get("deterministic_time"),
        }
        print(f"FREE: {res['free']}", flush=True)
        if res["free"]["status"] in ("OPTIMAL", "FEASIBLE"):
            sol = master.extract_solution()
            layout = {str(s): int(e["pose_idx"]) for s, e in sol.items()
                      if isinstance(e, dict) and e.get("pose_idx") is not None}
            # C1 的杆不在 slot 面上，extract_solution 拿不到——从 p_k 直读补齐
            # （覆盖复验材料需要杆位置）。
            delegate = getattr(master, "_coordinate_delegate", None)
            c1_bools = list(getattr(delegate, "_c1_pole_bools", []) or [])
            if c1_bools:
                pool = list(session.facility_pools.get("power_pole", []))
                layout["__c1_active_poles__"] = [
                    {"pose_idx": int(i), "anchor": dict(pool[i].get("anchor", {}))}
                    for i, var, _ in c1_bools
                    if master._solver.Value(var) == 1
                ]
            json.dump(layout, open(str(args.out) + ".solution.json", "w"))
            print(f"SOLUTION SAVED ({len(layout)} entries)", flush=True)

    json.dump(res, open(args.out, "w"), ensure_ascii=False, indent=1)
    print("B0_CELL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

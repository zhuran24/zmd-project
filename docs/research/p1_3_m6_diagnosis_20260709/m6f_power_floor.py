"""M6f：可行性地板判决——无 ghost + 供电全开 + 自由搜索。
供电可行的 266 布局到底存不存在（找得到吗）？
OPTIMAL = 存在（且拿到种子布局）；UNKNOWN = 搜索无引导连地板都够不到；INFEASIBLE = 模型过约束警报。
"""
import json, os, sys, time
sys.path.insert(0, "/home/zhuran24/zmd-pj")
os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
os.environ["EXACT_CP_SAT_WORKERS"] = "12"
os.environ["EXACT_SUBPROBLEM_MAX_MEMORY_MB"] = "28000"
os.environ["EXACT_MASTER_CP_MODEL_PRESOLVE"] = "0"
os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "automatic"
from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession
session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)
master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=None)
if not getattr(master, "_built", False):
    master.build()
print("full-power no-ghost master built", flush=True)
t0 = time.perf_counter()
status = master.solve(time_limit_seconds=900.0, solution_hint=None, known_feasible_hint=False)
ls = dict(master.build_stats.get("last_solve", {}))
e = {"status": str(ls.get("status")), "wall": round(time.perf_counter() - t0, 1),
     "branches": ls.get("branches"), "conflicts": ls.get("conflicts")}
print(f"POWER_FLOOR: {e['status']} wall={e['wall']}s branches={e['branches']}", flush=True)
if e["status"] in ("OPTIMAL", "FEASIBLE"):
    sol = master.extract_solution()
    layout = {str(s): int(v["pose_idx"]) for s, v in sol.items()
              if isinstance(v, dict) and v.get("is_mandatory") and v.get("pose_idx") is not None}
    poles = {str(s): int(v["pose_idx"]) for s, v in sol.items()
             if isinstance(v, dict) and not v.get("is_mandatory") and v.get("pose_idx") is not None}
    json.dump({"mandatory": layout, "optionals": poles}, open("/home/zhuran24/m5_runs/m6f_power_feasible_layout.json", "w"))
    e["layout_saved"] = True
    e["n_poles"] = len(poles)
    print(f"POWER-FEASIBLE LAYOUT SAVED: {len(layout)} mandatory + {len(poles)} optionals", flush=True)
json.dump(e, open("/home/zhuran24/m5_runs/m6f_verdict.json", "w"), ensure_ascii=False, indent=1)
print("M6F_DONE", flush=True)

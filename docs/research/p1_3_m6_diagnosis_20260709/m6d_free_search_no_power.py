"""M6d：诊断最后一块拼图——自由布局 + 无供电 + 全 anchor 6×6。

若快速出解 ⇒「自由搜索下纯打包可解，供电是唯一主墙」定案；
若 UNKNOWN ⇒ 打包规模是共犯，诊断改双病灶。
600s / w12 / presolve-off / automatic。
"""
import json
import os
import sys
import time

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
core_np = MasterPlacementModel.build_exact_core(
    session.instances,
    session.facility_pools,
    session.rules,
    skip_power_coverage=True,
    generic_io_requirements=session.core.generic_io_requirements,
    wireless_sink_generic_input_slots=session.core.wireless_sink_generic_input_slots,
)
master = MasterPlacementModel.from_exact_core(core_np, ghost_rect=(6, 6))
if not getattr(master, "_built", False):
    master.build()
print("no-power master built (free layout, all anchors)", flush=True)

t0 = time.perf_counter()
status = master.solve(time_limit_seconds=600.0, solution_hint=None, known_feasible_hint=False)
ls = dict(master.build_stats.get("last_solve", {}))
e = {
    "status_code": int(status),
    "status": str(ls.get("status")),
    "wall": round(time.perf_counter() - t0, 1),
    "branches": ls.get("branches"),
    "conflicts": ls.get("conflicts"),
}
print(f"FREE+NOPOWER: {e['status']} wall={e['wall']}s branches={e['branches']}", flush=True)
with open("/home/zhuran24/m5_runs/m6d_verdict.json", "w") as f:
    json.dump(e, f, ensure_ascii=False, indent=1)
print("M6D_DONE", flush=True)

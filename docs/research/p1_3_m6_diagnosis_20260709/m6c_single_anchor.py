"""M6c：单 anchor 全模型判决——4225 ghost 析取砍成 1，供电保留，布局自由。

三个 anchor 采样（132 / (0,0) 附近 / 棋盘中心附近），各 600s，presolve-off + automatic + w12。
判读：出解 = anchor 多重性×供电联合墙（修复=anchor 分片并行）；
     UNKNOWN = 供电编码单 anchor 也溺死（编码墙实锤）；
     INFEASIBLE = 该 anchor 下 6×6 问题真无解（需多采样判全局）。
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

from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession

OUT = "/home/zhuran24/m5_runs/m6c_verdicts.json"
results = []

session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)

# anchor 采样（(x,y) 坐标）：角落 / 重建带（idx132 邻域）/ 棋盘中心
for anchor_idx in ((0, 0), (2, 2), (32, 32)):
    master = MasterPlacementModel.from_exact_core(
        session.core, ghost_rect=(6, 6), ghost_anchor_filter=[anchor_idx]
    )
    if not getattr(master, "_built", False):
        master.build()
    t0 = time.perf_counter()
    status = master.solve(
        time_limit_seconds=600.0,
        solution_hint=None,
        known_feasible_hint=False,
    )
    ls = dict(master.build_stats.get("last_solve", {}))
    e = {
        "anchor_xy": list(anchor_idx),
        "status_code": int(status),
        "status": str(ls.get("status")),
        "wall": round(time.perf_counter() - t0, 1),
        "branches": ls.get("branches"),
        "conflicts": ls.get("conflicts"),
    }
    print(f"ANCHOR {anchor_idx}: {e['status']} wall={e['wall']}s branches={e['branches']}", flush=True)
    results.append(e)
    del master

with open(OUT, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("M6C_DONE", flush=True)

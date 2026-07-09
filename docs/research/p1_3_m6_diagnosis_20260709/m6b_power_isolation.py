"""M6b：供电族隔离判决。

A 段：skip_power_coverage=True 重建 core，同样的全钉死验证（presolve-off/fixed/单核/120s）。
     秒过 FEASIBLE = 供电补全就是首解之墙（布局几何+ghost 无辜，证据无混杂）。
B 段：供电保留，全钉死 + presolve-off + automatic + w12 + 600s——给电线杆搜索真火力。
     若 FEASIBLE = 当前模型首解到手（战场开）。
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/zhuran24/zmd-pj")
os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
os.environ["EXACT_CP_SAT_WORKERS"] = "1"

from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession

OUT = "/home/zhuran24/m5_runs/m6b_verdicts.json"
results = {"A_skip_power": [], "B_full_power_firepower": []}

session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)

# ===== A 段：无供电 core =====
core_np = MasterPlacementModel.build_exact_core(
    session.instances,
    session.facility_pools,
    session.rules,
    skip_power_coverage=True,
    generic_io_requirements=session.core.generic_io_requirements,
    wireless_sink_generic_input_slots=session.core.wireless_sink_generic_input_slots,
)
master_np = MasterPlacementModel.from_exact_core(core_np, ghost_rect=(6, 6))
if not getattr(master_np, "_built", False):
    master_np.build()
print("A: no-power master built", flush=True)

PROF_FIXED = {
    "profile_id": "m6b_presolve_off_fixed",
    "cp_model_presolve": 0,
    "search_branching": "fixed",
    "worker_count": 1,
}
for anchor in (132, 133, 134):
    hint = {
        str(k): int(v)
        for k, v in json.load(
            open(f"/home/zhuran24/m5_runs/rebuilt_hints/hint_anchor{anchor}.json")
        ).items()
    }
    t0 = time.perf_counter()
    v = master_np._validate_coordinate_forced_hint(
        solution_hint=hint,
        ghost_anchor_hint_idx=anchor,
        time_limit_seconds=120.0,
        solver_parameter_profile=PROF_FIXED,
    )
    e = {"anchor": anchor, "status": str(v.get("status")), "accepted": bool(v.get("accepted", False)),
         "reason": str(v.get("reason")), "wall": round(time.perf_counter() - t0, 1),
         "branches": v.get("branches"), "conflicts": v.get("conflicts")}
    print(f"A ANCHOR {anchor}: {e['status']} wall={e['wall']}s branches={e['branches']}", flush=True)
    results["A_skip_power"].append(e)

del master_np, core_np

# ===== B 段：全供电 + 真火力 =====
master_fp = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(6, 6))
if not getattr(master_fp, "_built", False):
    master_fp.build()
print("B: full-power master built", flush=True)

PROF_FIRE = {
    "profile_id": "m6b_presolve_off_auto_w12",
    "cp_model_presolve": 0,
    "search_branching": "automatic",
    "worker_count": 12,
}
hint = {
    str(k): int(v)
    for k, v in json.load(open("/home/zhuran24/m5_runs/rebuilt_hints/hint_anchor132.json")).items()
}
t0 = time.perf_counter()
v = master_fp._validate_coordinate_forced_hint(
    solution_hint=hint,
    ghost_anchor_hint_idx=132,
    time_limit_seconds=600.0,
    solver_parameter_profile=PROF_FIRE,
)
e = {"anchor": 132, "status": str(v.get("status")), "accepted": bool(v.get("accepted", False)),
     "reason": str(v.get("reason")), "wall": round(time.perf_counter() - t0, 1),
     "branches": v.get("branches"), "conflicts": v.get("conflicts")}
print(f"B ANCHOR 132: {e['status']} wall={e['wall']}s branches={e['branches']}", flush=True)
results["B_full_power_firepower"].append(e)

with open(OUT, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("M6B_DONE", flush=True)

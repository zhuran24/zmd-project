"""M6e：两阶段路线生死判决。

阶段一：无供电 master 自由求解（M6d 复现）+ 提取布局与 anchor。
阶段二：完整模型钉死该布局（杆自由）+ presolve-off + automatic + w12 + 600s 验证。
FEASIBLE ⇒ 首解到手（两阶段修复路线成立，M5 战场开）。
INFEASIBLE ⇒ 纯打包解供电不可行，修复走 power-aware 打包/编码手术。
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

OUT = "/home/zhuran24/m5_runs/m6e_verdict.json"
res = {}

session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)

# ===== 阶段一：无供电自由解 =====
core_np = MasterPlacementModel.build_exact_core(
    session.instances,
    session.facility_pools,
    session.rules,
    skip_power_coverage=True,
    generic_io_requirements=session.core.generic_io_requirements,
    wireless_sink_generic_input_slots=session.core.wireless_sink_generic_input_slots,
)
m1 = MasterPlacementModel.from_exact_core(core_np, ghost_rect=(6, 6))
if not getattr(m1, "_built", False):
    m1.build()
t0 = time.perf_counter()
status = m1.solve(time_limit_seconds=900.0, solution_hint=None, known_feasible_hint=False)
sol = m1.extract_solution()
res["stage1"] = {
    "status": str(dict(m1.build_stats.get("last_solve", {})).get("status")),
    "wall": round(time.perf_counter() - t0, 1),
    "n_instances": len(sol or {}),
}
print(f"STAGE1: {res['stage1']}", flush=True)
if not sol:
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("M6E_DONE (stage1 no solution)", flush=True)
    sys.exit(0)

# 提取 {solution_id: pose_idx} hint 与 ghost anchor
hint = {
    str(sid): int(entry["pose_idx"])
    for sid, entry in sol.items()
    if isinstance(entry, dict) and entry.get("is_mandatory") and entry.get("pose_idx") is not None
}
anchor_idx = None
d = getattr(m1, "_coordinate_delegate", None)
uv = getattr(d, "u_vars", None) if d is not None else None
solver = getattr(m1, "_solver", None) or (getattr(d, "owner", None) and getattr(d.owner, "_solver", None))
if uv and solver is not None:
    try:
        items = uv.items() if hasattr(uv, "items") else enumerate(uv)
        for idx, u in items:
            if solver.Value(u) == 1:
                anchor_idx = int(idx)
                break
    except Exception as exc:
        print("anchor extract failed:", exc, flush=True)
res["stage1"]["hint_len"] = len(hint)
res["stage1"]["anchor_idx"] = anchor_idx
json.dump(hint, open("/home/zhuran24/m5_runs/m6e_stage1_layout.json", "w"))
print(f"layout saved: {len(hint)} instances, anchor_idx={anchor_idx}", flush=True)
del m1, core_np

# ===== 阶段二：完整模型钉死验证 =====
m2 = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(6, 6))
if not getattr(m2, "_built", False):
    m2.build()
PROF = {
    "profile_id": "m6e_presolve_off_auto_w12",
    "cp_model_presolve": 0,
    "search_branching": "automatic",
    "worker_count": 12,
}
t1 = time.perf_counter()
v = m2._validate_coordinate_forced_hint(
    solution_hint=hint,
    ghost_anchor_hint_idx=anchor_idx,
    time_limit_seconds=600.0,
    solver_parameter_profile=PROF,
)
res["stage2"] = {
    "status": str(v.get("status")),
    "accepted": bool(v.get("accepted", False)),
    "reason": str(v.get("reason")),
    "wall": round(time.perf_counter() - t1, 1),
    "forced": v.get("forced_slot_field_count"),
    "branches": v.get("branches"),
}
print(f"STAGE2: {res['stage2']}", flush=True)

json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
print("M6E_DONE", flush=True)

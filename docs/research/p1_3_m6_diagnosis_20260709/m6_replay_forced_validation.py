"""M6 诊断判决实验：重建布局 × presolve-off 强制验证。

对 anchor 132/133/134 的三份重建布局（离线几何验证 0 重叠、含 6×6 洞），
在当前 6×6 coordinate master 上全钉死验证：
- 主判据 profile：presolve 全关 + fixed + 单核 —— 全钉死模型靠纯传播出结论，
  绕过此前绞死一切验证的 presolve 税（该组合从未试过）。
- FEASIBLE ⇒ 当前模型首解直接到手（战场开）。
- INFEASIBLE ⇒ 复跑 use_assumptions=True 提取不可行核 —— 违反的约束族当场点名。
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

OUT = "/home/zhuran24/m5_runs/m6_replay_verdicts.json"
MAIN_PROFILE = {
    "profile_id": "replay_presolve_off_fixed",
    "cp_model_presolve": 0,
    "search_branching": "fixed",
    "worker_count": 1,
}

session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)
master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(6, 6))
if not getattr(master, "_built", False):
    master.build()
print("master built", flush=True)

results = []
for anchor in (132, 133, 134):
    hint = {
        str(k): int(v)
        for k, v in json.load(
            open(f"/home/zhuran24/m5_runs/rebuilt_hints/hint_anchor{anchor}.json")
        ).items()
    }
    t0 = time.perf_counter()
    v = master._validate_coordinate_forced_hint(
        solution_hint=hint,
        ghost_anchor_hint_idx=anchor,
        time_limit_seconds=300.0,
        solver_parameter_profile=MAIN_PROFILE,
    )
    entry = {
        "anchor": anchor,
        "status": str(v.get("status")),
        "accepted": bool(v.get("accepted", False)),
        "reason": str(v.get("reason")),
        "wall": round(time.perf_counter() - t0, 1),
        "forced_slot_field_count": v.get("forced_slot_field_count"),
        "branches": v.get("branches"),
        "conflicts": v.get("conflicts"),
    }
    print(f"ANCHOR {anchor}: {entry['status']} accepted={entry['accepted']} "
          f"reason={entry['reason']} wall={entry['wall']}s", flush=True)
    if entry["status"] == "INFEASIBLE":
        t1 = time.perf_counter()
        core = master._validate_coordinate_forced_hint(
            solution_hint=hint,
            ghost_anchor_hint_idx=anchor,
            time_limit_seconds=300.0,
            solver_parameter_profile=MAIN_PROFILE,
            use_assumptions=True,
        )
        entry["infeasible_core_status"] = str(core.get("infeasible_assumption_core_status"))
        entry["infeasible_core"] = list(core.get("infeasible_assumption_core", []))[:40]
        entry["core_wall"] = round(time.perf_counter() - t1, 1)
        print(f"  core({entry['infeasible_core_status']}): "
              f"{entry['infeasible_core'][:10]}", flush=True)
    results.append(entry)

with open(OUT, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("M6_REPLAY_DONE", flush=True)

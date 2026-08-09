"""M5 探针：直接抽取 ghost-aware 重建的完整布局（绕过被 presolve 税绞死的验收）。

对 6×6 ghost 的合格 anchor 逐个跑 greedy 重建，收集前 N 份 complete 布局，
落盘为 EXACT_COMMUNITY_BLUEPRINT_HINT_PATH 可直接消费的 {solution_id: pose_idx} JSON。
build-only，无 CP-SAT solve。
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/zhuran24/zmd-pj")
os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
os.environ["EXACT_CP_SAT_WORKERS"] = "1"
os.environ["EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS"] = "5000"

from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession

N_KEEP = 3
OUT_DIR = "/home/zhuran24/m5_runs/rebuilt_hints"
os.makedirs(OUT_DIR, exist_ok=True)

session = ExactSearchSession.create("/home/zhuran24/zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)
master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(6, 6))
if not getattr(master, "_built", False):
    master.build()
print("master built", flush=True)

cands = {
    str(g["group_id"]): master._candidate_pose_indices_for_group(g)
    for g in master._mandatory_groups
}
ordered = master._ordered_mandatory_groups_for_greedy(cands)

bpf = master.evaluate_exact_candidate_boundary_port_feasibility()
screen_pass = tuple(int(i) for i in bpf.get("screen_pass_anchor_indices", ()))
rebuild_idx = tuple(int(i) for i in bpf.get("rebuild_anchor_indices", ()))
eligible = screen_pass or rebuild_idx
print(f"eligible anchors: {len(eligible)} (screen_pass={len(screen_pass)})", flush=True)

kept = 0
attempts = 0
t0 = time.perf_counter()
for rect_idx in eligible:
    domain = master._ghost_domains[int(rect_idx)]
    blocked = {(int(c[0]), int(c[1])) for c in list(domain.get("cells", []))}
    attempts += 1
    hint = master._run_mandatory_greedy_pass(
        ordered_groups=ordered,
        candidates_by_group=cands,
        blocked_cells=blocked,
        stop_on_first_failure=True,
    )
    if bool(hint.get("complete", False)):
        sol = {str(k): int(v) for k, v in dict(hint.get("solution_hint", {})).items()}
        path = os.path.join(OUT_DIR, f"hint_anchor{int(rect_idx)}.json")
        with open(path, "w") as f:
            json.dump(sol, f)
        print(f"KEPT anchor={rect_idx} instances={len(sol)} -> {path}", flush=True)
        kept += 1
        if kept >= N_KEEP:
            break
    if attempts % 50 == 0:
        print(f"...{attempts} attempts, {kept} kept, {time.perf_counter()-t0:.0f}s", flush=True)

print(f"DONE kept={kept} attempts={attempts} wall={time.perf_counter()-t0:.0f}s", flush=True)

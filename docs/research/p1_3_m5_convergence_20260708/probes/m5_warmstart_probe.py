"""M5 diagnostic probe: does build_exact_candidate_warm_start produce a usable
hint for the scanned ghost rects? Build-only, no master solve."""
import json
import os
import sys
import time

sys.path.insert(0, r"C:\claude pj\zmd-pj")
os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
os.environ["EXACT_CP_SAT_WORKERS"] = "1"

from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession

session = ExactSearchSession.create(r"C:\claude pj\zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)

for g in ((26, 26), (8, 8)):
    master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=g)
    t = time.perf_counter()
    ws = master.build_exact_candidate_warm_start()
    hint = ws.get("solution_hint") or {}
    out = {
        "ghost": list(g),
        "warm_start_seconds": round(time.perf_counter() - t, 1),
        "hint_len": len(hint),
    }
    for k in sorted(ws.keys()):
        if k == "solution_hint":
            continue
        out[k] = ws[k]
    print(json.dumps(out, ensure_ascii=False, default=str), flush=True)
print("PROBE_DONE", flush=True)

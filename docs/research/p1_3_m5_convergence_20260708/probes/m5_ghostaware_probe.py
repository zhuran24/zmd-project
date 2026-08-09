"""M5 probe: unlock the ghost-aware warm-start pipeline (anchor limit 64 ->
4096) and dump its full telemetry for an 8x8 ghost. Build-only, no solve."""
import json
import os
import sys
import time

sys.path.insert(0, r"C:\claude pj\zmd-pj")
os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
os.environ["EXACT_CP_SAT_WORKERS"] = "1"
os.environ["EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS"] = "4096"
os.environ["EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS"] = "32"

from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession

session = ExactSearchSession.create(r"C:\claude pj\zmd-pj", solve_mode="certified_exact")
print("session ready", flush=True)

master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(8, 8))
t = time.perf_counter()
ws = master.build_exact_candidate_warm_start()
out = {
    "ghost": [8, 8],
    "warm_start_seconds": round(time.perf_counter() - t, 1),
    "hint_len": len(ws.get("solution_hint") or {}),
}
for k in sorted(ws.keys()):
    if k == "solution_hint":
        continue
    out[k] = ws[k]
print(json.dumps(out, ensure_ascii=False, default=str, indent=1), flush=True)
print("PROBE_DONE", flush=True)

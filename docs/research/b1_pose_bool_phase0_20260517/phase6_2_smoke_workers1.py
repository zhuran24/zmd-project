"""Phase 6.2 v3 workers=1 + 600s — 看是不是 mem/workers contention 让 master UNKNOWN.

baseline 8 worker × 4GB = 32 GB peak, propagator state 大.
1 worker = 1/8 mem, search depth-first 可能 cheaper.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
os.environ["EXACT_USE_PORT_ACTIVE"] = "1"
os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
os.environ["EXACT_MASTER_CP_SAT_WORKERS"] = "1"

print("=== Phase 6.2 v3 smoke (workers=1, 600s) ===")
from src.search.benders_loop import run_benders_for_ghost_rect

t0 = time.perf_counter()
status, _ = run_benders_for_ghost_rect(
    ghost_w=27, ghost_h=15,
    max_iterations=1,
    project_root=Path("."),
    solve_mode="certified_exact",
    master_seconds=600.0,
    binding_seconds=60.0,
    routing_seconds=60.0,
    flow_seconds=60.0,
    campaign=None,
    session=None,
    disable_master_warm_start=True,
)
elapsed = time.perf_counter() - t0
print(f"\n27x15 (22,28) → {status} in {elapsed:.1f}s")

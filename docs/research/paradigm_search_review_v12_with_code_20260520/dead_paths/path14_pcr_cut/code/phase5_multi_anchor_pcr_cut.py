"""PCR-CUT Phase 5 — multi-anchor campaign with the LBBD hook on.

Reuses Path 12 / Path 13 anchor set so verdict is directly comparable. Per
v3 plan, the GO criterion is "≥ 1 non-corner anchor reaches CERTIFIED" or
"≥ 4/8 non-negative anchors reach 'patch-pass then no real routing reject
within ≤ 12 iter'".
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

ANCHORS = [
    (27, 15, 22, 28, "interior_22_28"),
    (27, 15, 10, 10, "interior_10_10"),
    (27, 15, 44, 30, "interior_44_30"),
    (27, 15, 15, 40, "interior_15_40"),
    (27, 15, 0, 0, "corner_0_0_NEGATIVE"),
    (10, 10, 25, 25, "small_10x10"),
    (15, 10, 22, 28, "small_15x10"),
    (15, 15, 22, 28, "small_15x15"),
]


def _reset_env(ax: int, ay: int) -> None:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE"] = "1"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_TOP_K"] = "3"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_SECONDS"] = "15"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_PER_PATCH_SECONDS"] = "5"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS"] = "900"
    os.environ["EXACT_B1_PATCH_ROUTING_CORE_QX_CAP"] = "24"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)


def run_one(ghost_w: int, ghost_h: int, ax: int, ay: int, label: str, max_iter: int = 10):
    _reset_env(ax, ay)
    print(f"\n>>> {label}: {ghost_w}×{ghost_h} ({ax},{ay}) max_iter={max_iter}", flush=True)
    from src.search.benders_loop import run_benders_for_ghost_rect
    t0 = time.perf_counter()
    try:
        status, _ = run_benders_for_ghost_rect(
            ghost_w=ghost_w, ghost_h=ghost_h,
            max_iterations=max_iter,
            project_root=Path("."),
            solve_mode="certified_exact",
            master_seconds=180.0,
            binding_seconds=30.0,
            routing_seconds=60.0,
            flow_seconds=10.0,
            campaign=None,
            session=None,
            disable_master_warm_start=True,
        )
    except Exception as exc:
        return label, f"ERROR: {type(exc).__name__}", time.perf_counter() - t0
    elapsed = time.perf_counter() - t0
    print(f"    {label}: {status} in {elapsed:.1f}s", flush=True)
    return label, status, elapsed


def main() -> int:
    print("=== PCR-CUT Phase 5 — 8-anchor LBBD campaign ===")
    results = [run_one(*cfg) for cfg in ANCHORS]
    print("\n=== Phase 5 summary ===")
    for label, status, elapsed in results:
        print(f"  {label:30s} {status:18s} {elapsed:7.1f}s")
    cert_count = sum(1 for r in results if r[1] == "CERTIFIED")
    if cert_count >= 1:
        print(">>> ✅ Phase 5 BREAKTHROUGH ({} anchor certified)".format(cert_count))
        return 0
    print(">>> 🟡 Phase 5: 0/8 CERTIFIED — paradigm not breakthrough at this scale")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""HiGHS Phase 3 PoC: real data, full model w/ power_coverage, 70x6 ghost.

跟 Phase 2 minimum (4.81 GB build, 6.34 GB solve plateau) 对比, 加 power_pole +
power_coverage 约束后 build/solve RAM 涨多少.

跑前必须停 168h-v1. 跑完 print summary + 退出.
"""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.highs_master_model import build_highs_minimum_model  # noqa: E402


def _rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def main() -> int:
    print(f"[{time.strftime('%H:%M:%S')}] start, RSS={_rss_gb():.2f}GB")

    with open(PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json") as f:
        payload = json.load(f)
    instances = payload.get("instances", payload) if isinstance(payload, dict) else payload
    with open(PROJECT_ROOT / "data/preprocessed/candidate_placements.json") as f:
        pools_payload = json.load(f)
    facility_pools = pools_payload.get("facility_pools", pools_payload)
    with open(PROJECT_ROOT / "rules/canonical_rules.json") as f:
        rules = json.load(f)
    print(f"[{time.strftime('%H:%M:%S')}] loaded data, RSS={_rss_gb():.2f}GB")

    ghost_rect = (70, 6)
    print(f"[{time.strftime('%H:%M:%S')}] BUILD include_power_coverage=True ghost_rect={ghost_rect}")

    t0 = time.time()
    model = build_highs_minimum_model(
        instances,
        facility_pools,
        rules,
        ghost_rect=ghost_rect,
        include_power_coverage=True,
    )
    t1 = time.time()
    rss_after_build = _rss_gb()
    print(f"[{time.strftime('%H:%M:%S')}] BUILD done in {t1-t0:.1f}s, RSS={rss_after_build:.2f}GB")
    print(f"  build_stats: {model.build_stats}")

    print(f"[{time.strftime('%H:%M:%S')}] SOLVE (cap 180s, short PoC)...")
    t2 = time.time()
    status, solution = model.solve(time_limit_seconds=180.0)
    t3 = time.time()
    rss_after_solve = _rss_gb()
    print(f"[{time.strftime('%H:%M:%S')}] SOLVE done in {t3-t2:.1f}s, RSS={rss_after_solve:.2f}GB")
    print(f"  status: {status}")
    if solution is not None:
        print(f"  selected_poses: {len(solution['selected_poses'])}")
        print(f"  ghost_anchor: {solution['ghost_anchor']}")

    print()
    print("==== PHASE 3 FULL MODEL SUMMARY ====")
    print(f"build_time: {t1-t0:.1f}s")
    print(f"solve_time: {t3-t2:.1f}s")
    peak = max(rss_after_build, rss_after_solve)
    print(f"peak_rss: {peak:.2f} GB")
    print(f"status: {status}")
    print(f"vs OR-Tools 30 GB baseline: HiGHS full model {peak:.2f} GB ({100*(1-peak/30):.0f}% reduction)")
    print(f"vs HiGHS minimum (4.81 GB build, 6.34 GB solve plateau): "
          f"add power_coverage cost ~{peak-6.34:.1f} GB")

    return 0


if __name__ == "__main__":
    sys.exit(main())

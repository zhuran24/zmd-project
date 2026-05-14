#!/usr/bin/env python3
"""HiGHS Phase 2 PoC: real project data, build + solve smallest ghost candidate.

加载 data/preprocessed/ 真数据, build HiGHS model for 70x6 ghost (smallest in
state.json), 量 build/solve RAM + wall-time. 跟 OR-Tools baseline 30 GB peak +
swap thrash 对比.

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
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # ru_maxrss is KB on Linux


def main() -> int:
    print(f"[{time.strftime('%H:%M:%S')}] start, RSS={_rss_gb():.2f}GB")

    with open(PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json") as f:
        payload = json.load(f)
    instances = payload.get("instances", payload) if isinstance(payload, dict) else payload
    print(f"[{time.strftime('%H:%M:%S')}] loaded {len(instances)} mandatory instances")

    with open(PROJECT_ROOT / "data/preprocessed/candidate_placements.json") as f:
        pools_payload = json.load(f)
    facility_pools = pools_payload.get("facility_pools", pools_payload)
    print(f"[{time.strftime('%H:%M:%S')}] loaded {len(facility_pools)} templates")
    total_poses = sum(len(p) for p in facility_pools.values())
    print(f"[{time.strftime('%H:%M:%S')}] total poses: {total_poses}")

    with open(PROJECT_ROOT / "rules/canonical_rules.json") as f:
        rules = json.load(f)
    print(f"[{time.strftime('%H:%M:%S')}] loaded rules, RSS={_rss_gb():.2f}GB")

    # smallest ghost in state.json non-terminal list: 70x6 (memory check)
    ghost_rect = (70, 6)
    print(f"[{time.strftime('%H:%M:%S')}] BUILD: ghost_rect={ghost_rect}")

    t0 = time.time()
    model = build_highs_minimum_model(
        instances,
        facility_pools,
        rules,
        ghost_rect=ghost_rect,
    )
    t1 = time.time()
    rss_after_build = _rss_gb()
    print(f"[{time.strftime('%H:%M:%S')}] BUILD done in {t1-t0:.1f}s, RSS={rss_after_build:.2f}GB")
    print(f"  build_stats: {model.build_stats}")

    print(f"[{time.strftime('%H:%M:%S')}] SOLVE (cap 300s)...")
    t2 = time.time()
    status, solution = model.solve(time_limit_seconds=300.0)
    t3 = time.time()
    rss_after_solve = _rss_gb()
    print(f"[{time.strftime('%H:%M:%S')}] SOLVE done in {t3-t2:.1f}s, RSS={rss_after_solve:.2f}GB")
    print(f"  status: {status}")
    if solution is not None:
        print(f"  selected_poses: {len(solution['selected_poses'])} facilities")
        print(f"  ghost_anchor: {solution['ghost_anchor']}")

    print()
    print("==== SUMMARY ====")
    print(f"build_time: {t1-t0:.1f}s")
    print(f"solve_time: {t3-t2:.1f}s")
    print(f"peak_rss: {max(rss_after_build, rss_after_solve):.2f} GB")
    print(f"status: {status}")
    print(f"vs OR-Tools baseline ~30 GB peak + swap thrash → HiGHS peak {max(rss_after_build, rss_after_solve):.2f} GB")

    return 0


if __name__ == "__main__":
    sys.exit(main())

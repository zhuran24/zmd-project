#!/usr/bin/env python3
"""SCIP Phase 4 PoC: full model with power_coverage as lazy separator, 70x6.

跟 HiGHS Phase 3 PoC (42 GB build with explicit power_coverage) 对比, SCIP 用
lazy separator 应该 build RAM 跟 minimum (~5 GB) 类似, solve 阶段渐增累 cut.

跑前必须停 168h-v1. 跑完 print summary.
"""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.scip_master_model import build_scip_minimum_model  # noqa: E402


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
    print(f"[{time.strftime('%H:%M:%S')}] BUILD SCIP with_power_coverage_separator=True ghost_rect={ghost_rect}")

    t0 = time.time()
    model = build_scip_minimum_model(
        instances,
        facility_pools,
        rules,
        ghost_rect=ghost_rect,
        with_power_coverage_separator=True,
    )
    t1 = time.time()
    rss_after_build = _rss_gb()
    print(f"[{time.strftime('%H:%M:%S')}] BUILD done in {t1-t0:.1f}s, RSS={rss_after_build:.2f}GB")
    print(f"  build_stats: {model.build_stats}")

    print(f"[{time.strftime('%H:%M:%S')}] SOLVE (cap 180s)...")
    t2 = time.time()
    status, solution = model.solve(time_limit_seconds=180.0)
    t3 = time.time()
    rss_after_solve = _rss_gb()
    print(f"[{time.strftime('%H:%M:%S')}] SOLVE done in {t3-t2:.1f}s, RSS={rss_after_solve:.2f}GB")
    print(f"  status: {status}")

    print()
    print("==== SCIP PHASE 4 SUMMARY ====")
    print(f"build_time: {t1-t0:.1f}s")
    print(f"solve_time: {t3-t2:.1f}s")
    peak = max(rss_after_build, rss_after_solve)
    print(f"peak_rss: {peak:.2f} GB")
    print(f"status: {status}")
    print(f"vs OR-Tools 30 GB baseline: SCIP full {peak:.2f} GB ({100*(1-peak/30):.0f}% reduction)")
    print(f"vs HiGHS minimum 4.81 GB build / full 42 GB build:")
    print(f"  SCIP {peak:.2f} GB — {'good' if peak<15 else 'marginal' if peak<25 else 'bad'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

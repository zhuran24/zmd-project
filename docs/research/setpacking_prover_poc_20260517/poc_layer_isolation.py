"""Step D: layer-by-layer isolation — 找出 master 哪一层让 CP-SAT stuck.

逐层 strip master 的约束, 看 master.solve verdict 时间变化.

Layer 0: full master (baseline, 已知 30 min UNKNOWN)
Layer -1: skip_power_coverage=True (去掉 power_coverage 4M 行)
Layer -2 / -3: 暂没现成 skip 开关, 需要 modify src 才能往下拆 — 留作后续

只测 anchor (22,28) interior 27×15 一个 anchor, 看 power_coverage 单独影响.

用法:
  POC_SKIP_POWER=1 .venv/bin/python -u poc_layer_isolation.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# anchor filter env 必须在 import 前
os.environ.setdefault("EXACT_MASTER_GHOST_ANCHOR_FILTER", "22,28")

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.models.master_model import (  # noqa: E402
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.search.exact_campaign import (  # noqa: E402
    compute_exact_artifact_hashes,
)
from src.search.benders_loop import (  # noqa: E402
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    PROJECT_ROOT,
    ExactSearchSession,
    run_benders_for_ghost_rect,
)


def main() -> int:
    cand_w = int(os.environ.get("POC_GHOST_W", 27))
    cand_h = int(os.environ.get("POC_GHOST_H", 15))
    master_secs = float(os.environ.get("POC_MASTER_SECONDS", 300.0))
    skip_power = os.environ.get("POC_SKIP_POWER", "0").strip() in {"1", "true", "yes"}
    anchor_str = os.environ.get("EXACT_MASTER_GHOST_ANCHOR_FILTER", "?,?")

    print(f"=== layer isolation PoC ===")
    print(f"candidate: {cand_w}x{cand_h}")
    print(f"anchor: {anchor_str}")
    print(f"master_seconds: {master_secs}")
    print(f"SKIP_POWER_COVERAGE: {skip_power}")
    print(flush=True)

    project_root = PROJECT_ROOT

    # 手动 build core 加 skip_power_coverage 开关
    t0 = time.perf_counter()
    print(f"[load] project data ...", flush=True)
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    print(f"[load] {time.perf_counter()-t0:.1f}s")

    t1 = time.perf_counter()
    print(f"[core build] skip_power={skip_power} ...", flush=True)
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules,
        skip_power_coverage=skip_power,
        generic_io_requirements=generic,
        master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    print(f"[core build] {time.perf_counter()-t1:.1f}s")
    print(f"[core stats] vars={core.build_stats.get('exact_core_packaging_profile', {}).get('proto_variable_count')}, "
          f"cons={core.build_stats.get('exact_core_packaging_profile', {}).get('proto_constraint_count')}")

    artifact_hashes = compute_exact_artifact_hashes(project_root)
    session = ExactSearchSession(
        project_root=project_root,
        solve_mode="certified_exact",
        instances=instances,
        facility_pools=pools,
        rules=rules,
        artifact_hashes=artifact_hashes,
        master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        core=core,
        core_build_seconds=time.perf_counter() - t1,
    )

    print(f"\n[solve] run_benders_for_ghost_rect ghost={cand_w}x{cand_h} ...", flush=True)
    t2 = time.perf_counter()
    try:
        status, summary = run_benders_for_ghost_rect(
            ghost_w=cand_w,
            ghost_h=cand_h,
            max_iterations=2,
            master_seconds=master_secs,
            binding_seconds=30.0,
            routing_seconds=30.0,
            flow_seconds=30.0,
            session=session,
        )
    except Exception as exc:
        wall = time.perf_counter() - t2
        print(f"\nEXCEPTION after {wall:.1f}s: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 2

    wall = time.perf_counter() - t2
    print(f"\n=== verdict ===")
    print(f"wall: {wall:.1f}s")
    print(f"status: {status}")
    if isinstance(summary, dict):
        ms = summary.get("master_status")
        print(f"master_status: {ms}")
        print(f"reason: {summary.get('reason')}")
        bi = summary.get("benders_iterations")
        print(f"benders_iterations: {bi}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

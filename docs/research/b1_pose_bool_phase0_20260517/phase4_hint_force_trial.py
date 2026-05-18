"""B1 Phase 4.2 fallback: 用已知 binding-friendly layout 当 master hint, 强 force
production LBBD 走那个 layout, 验证端到端 (master + binding + routing) FEASIBLE.

策略:
1. 跑 standalone Phase 5 trial (env on direct instantiation) 拿 binding FEASIBLE layout
2. 提取 layout 成 hint dict {instance_id: pose_idx}
3. 把 hint 写盘 (或直接 inline)
4. 跑 production LBBD 启用 EXACT_COMMUNITY_BLUEPRINT_HINT_PATH 让 master 复用该 hint
5. binding 应通 (因为 layout 跟 standalone same), routing 接着跑

注意: 这是端到端 verdict 验证, 不是 generally robust solution. 拿到 1 个
FEASIBLE 后, paradigm 端 + LBBD wiring 完整 verified.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def step1_standalone_layout() -> Dict[str, Any]:
    """走 production master path 直接拿 binding-FEASIBLE layout."""
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"

    from src.models.master_model import (
        MasterPlacementModel,
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    from src.models.binding_subproblem import PortBindingModel

    instances, pools, rules = load_project_data(Path("."), "certified_exact")
    generic = load_generic_io_requirements_artifact(Path("."))

    m = MasterPlacementModel(
        instances, pools, rules,
        ghost_rect=(27, 15),
        skip_power_coverage=True,
        generic_io_requirements=generic,
        solve_mode="certified_exact",
        ghost_anchor_filter={(22, 28)},
    )
    m.build()
    t = time.perf_counter()
    print(f"[standalone] master.solve ...", flush=True)
    status = m.solve(time_limit_seconds=180.0)
    print(f"[standalone] master {status} in {time.perf_counter()-t:.1f}s", flush=True)
    solution = m.extract_solution()
    print(f"[standalone] solution {len(solution)} instances")

    binding_model = PortBindingModel(solution, m.facility_pools, instances, project_root=Path("."))
    binding_model.build()
    binding_status = binding_model.solve(time_limit_seconds=60.0)
    print(f"[standalone] binding {binding_status}")
    return {"solution": solution, "binding_status": binding_status}


def main() -> int:
    print(f"=== B1 Phase 4.2 hint force trial ===")

    layout = step1_standalone_layout()
    if layout["binding_status"] != "FEASIBLE":
        print(f"\n>>> Step 1 standalone binding {layout['binding_status']}, hint force 没用 <<<")
        return 0

    # Step 2: 提取 mandatory instance_id → pose_idx hint
    hint: Dict[str, int] = {}
    for inst_id, sol in layout["solution"].items():
        if sol.get("is_mandatory", False):
            hint[str(inst_id)] = int(sol["pose_idx"])
    print(f"[hint] {len(hint)} mandatory instance hints")

    hint_path = Path("/tmp/b1_phase4_hint.json")
    hint_path.write_text(json.dumps(hint))
    print(f"[hint] written to {hint_path}")

    # Step 3: 跑 production LBBD with this hint
    print(f"\n>>>>>> production LBBD with hint <<<<<<", flush=True)
    os.environ["EXACT_COMMUNITY_BLUEPRINT_HINT_PATH"] = str(hint_path)

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, solution = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=3,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=180.0,
        binding_seconds=120.0,
        routing_seconds=300.0,
        flow_seconds=60.0,
        campaign=None,
        session=None,
        disable_master_warm_start=False,  # 启用 hint apply
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== verdict ===")
    print(f"LBBD status: {status} in {elapsed:.1f}s")

    if status == "FEASIBLE":
        print(f"\n>>> 🎯 端到端 FEASIBLE — paradigm + LBBD + hint integration complete <<<")
    elif status == "INFEASIBLE":
        print(f"\n>>> LBBD INFEASIBLE — hint 没传到 master / 或 binding 还卡 (不应该, 但要查) <<<")
    else:
        print(f"\n>>> LBBD {status} <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""RAB-SEP Phase 0 — routing-aware binding filter probe.

策略: monkey-patch PortBindingModel.solve, 在 baseline binding solve 之前
dump probe stats:
  - 每 owner instance enumerate raw binding patterns
  - 算 front cell occupied / out-of-grid → filter
  - 算 commodity component consistency
  - 统计 raw / filtered / empty owner counts

GO 条件:
  - 每 owner filtered patterns ≥ 1
  - blocked front 占比 < 100% (一些 raw pattern 通过 filter)
  - 总 wall ≤ 10s (master 53s + probe < 1s)

NO-GO 条件:
  - 任 owner 0 filtered pattern → 该 layout 不可救 → cut 反馈
  - filter 实施 bug (probe 验证模型: filter 后 binding solve, routing precheck
    应 front_blocked=0; Phase 1 才真做 filter, 这里只 stat)
"""

from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0),
}

OUT_FILE = Path("docs/research/b1_rabsep_routing_aware_binding_20260518/phase0_probe_stats.json")


def compute_filter_stats(
    placement_solution: Dict[str, Dict[str, Any]],
    facility_pools: Dict[str, Any],
    instances_by_id: Dict[str, Any],
) -> Dict[str, Any]:
    from src.models.routing_subproblem import (
        RoutingPlacementCore, GRID_W, GRID_H,
    )
    from src.models.port_binding import (
        enumerate_pose_level_port_bindings,
        supports_exact_pose_level_binding,
    )

    # build occupied + components
    occupied_cells: Set[Tuple[int, int]] = set()
    occupied_owner: Dict[Tuple[int, int], str] = {}
    for iid, sol in placement_solution.items():
        tpl = str(sol["facility_type"])
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol["pose_idx"])
        if pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for cell in pose.get("occupied_cells", []) or []:
            xy = (int(cell[0]), int(cell[1]))
            occupied_cells.add(xy)
            occupied_owner[xy] = str(iid)

    core = RoutingPlacementCore.from_occupied_cells(
        occupied_cells, occupied_owner_by_cell=occupied_owner,
    )

    stats: Dict[str, Any] = {
        "free_cells": len(core.free_cells),
        "component_count": len(core.cells_by_component),
        "component_sizes": sorted(
            [len(c) for c in core.cells_by_component.values()], reverse=True,
        )[:10],
        "total_owners": 0,
        "skipped_owners": 0,
        "owners_with_empty_filtered": [],
        "raw_patterns_total": 0,
        "filtered_patterns_total": 0,
        "owners": [],
        "blocker_instances": set(),
        "active_port_blocked": 0,
        "active_port_out_of_grid": 0,
        "active_port_free": 0,
    }

    for iid, sol in placement_solution.items():
        inst = instances_by_id.get(str(iid))
        if not inst:
            stats["skipped_owners"] += 1
            continue
        operation_type = str(inst.get("operation_type", ""))
        if not supports_exact_pose_level_binding(operation_type):
            stats["skipped_owners"] += 1
            continue

        tpl = str(sol["facility_type"])
        pose = facility_pools[tpl][int(sol["pose_idx"])]
        raw_patterns = enumerate_pose_level_port_bindings(operation_type, pose)
        stats["total_owners"] += 1
        stats["raw_patterns_total"] += len(raw_patterns)

        filtered = []
        for pattern in raw_patterns:
            ok = True
            for port_role in ("input_ports", "output_ports"):
                for port in pattern.get(port_role, []):
                    px, py = int(port["x"]), int(port["y"])
                    direction = str(port["dir"])
                    dx, dy = _DIR_DELTA.get(direction, (0, 0))
                    fx, fy = px + dx, py + dy
                    if not (0 <= fx < GRID_W and 0 <= fy < GRID_H):
                        ok = False
                        stats["active_port_out_of_grid"] += 1
                        break
                    if (fx, fy) in occupied_cells:
                        blocker = occupied_owner.get((fx, fy), "unknown")
                        if blocker != iid:
                            ok = False
                            stats["active_port_blocked"] += 1
                            stats["blocker_instances"].add(blocker)
                            break
                    stats["active_port_free"] += 1
                if not ok:
                    break
            if ok:
                filtered.append(pattern)

        stats["filtered_patterns_total"] += len(filtered)
        if not filtered:
            stats["owners_with_empty_filtered"].append(iid)
        stats["owners"].append({
            "instance_id": iid,
            "operation_type": operation_type,
            "raw_patterns": len(raw_patterns),
            "filtered_patterns": len(filtered),
        })

    stats["blocker_instances"] = sorted(stats["blocker_instances"])
    if stats["raw_patterns_total"] > 0:
        stats["filter_keep_rate"] = round(
            stats["filtered_patterns_total"] / stats["raw_patterns_total"], 4,
        )
    return stats


def main() -> int:
    os.environ.setdefault("EXACT_USE_POSE_BOOL_MASTER", "1")
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    # 关掉所有 B1 phase 6 死路 env (sanity)
    for k in (
        "EXACT_B1_DELETION_CORE_CUT",
        "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK",
        "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE",
    ):
        os.environ.pop(k, None)

    print("=== RAB-SEP Phase 0 — bind filter probe ===")
    print("27×15 anchor (22,28), max_iter=1 (probe-only)")

    import src.models.binding_subproblem as bm

    orig_solve = bm.PortBindingModel.solve
    probe_state = {"done": False, "wall": None}

    def patched_solve(self, time_limit_seconds=30.0):
        if not probe_state["done"]:
            probe_state["done"] = True
            t0 = time.perf_counter()
            stats = compute_filter_stats(
                self.placement_solution,
                self.facility_pools,
                self.instances_by_id,
            )
            probe_state["wall"] = time.perf_counter() - t0
            stats["probe_wall_seconds"] = round(probe_state["wall"], 3)
            OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OUT_FILE, "w") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            print(f"[probe] dumped {OUT_FILE}", flush=True)
            print(f"[probe] free_cells={stats['free_cells']} components={stats['component_count']}", flush=True)
            print(f"[probe] owners={stats['total_owners']} skipped={stats['skipped_owners']}", flush=True)
            print(f"[probe] raw_patterns={stats['raw_patterns_total']} filtered={stats['filtered_patterns_total']} keep_rate={stats.get('filter_keep_rate')}", flush=True)
            print(f"[probe] active_port: free={stats['active_port_free']} blocked={stats['active_port_blocked']} out_of_grid={stats['active_port_out_of_grid']}", flush=True)
            print(f"[probe] empty_filtered_owners={len(stats['owners_with_empty_filtered'])}", flush=True)
            print(f"[probe] probe_wall={probe_state['wall']:.3f}s", flush=True)
        return orig_solve(self, time_limit_seconds)

    bm.PortBindingModel.solve = patched_solve

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=1,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=10.0,
        routing_seconds=30.0,
        flow_seconds=10.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    total_wall = time.perf_counter() - t0
    print(f"\n=== Phase 0 probe done: master+binding flow → {status} in {total_wall:.1f}s ===")

    if not probe_state["done"]:
        print(">>> ❌ probe 没 fire (master 没出 OPTIMAL layout?)")
        return 1

    with open(OUT_FILE) as f:
        stats = json.load(f)

    empty_count = len(stats["owners_with_empty_filtered"])
    if empty_count == 0:
        print(f">>> ✅ Phase 0 GO: 所有 {stats['total_owners']} owners 至少 1 filtered pattern")
        print(f">>> filter keep_rate={stats.get('filter_keep_rate')}, blocker_instances={len(stats['blocker_instances'])}")
        return 0
    print(f">>> ❌ Phase 0 NO-GO: {empty_count} owners 0 filtered pattern")
    print(f">>> empty owners: {stats['owners_with_empty_filtered'][:10]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

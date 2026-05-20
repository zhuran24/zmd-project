"""SAC-Hull Phase 0 — separator violation oracle PoC.

跑 master.solve 拿 OPTIMAL layout, 构 separator library, 算每 separator 的
- required_crossings (forced-side commodity crossing 数)
- free_wall_cells (墙内 free 格子数)
- capacity_upper_bound = 2 × free_wall_cells (cell-layer)
- violation iff required_crossings > capacity_upper_bound

GO 条件:
- 至少 1 个 violation per layout (前提验证)
- analysis < 5s
- 不依赖 binding decisions (forced side 只看 pose 几何)

跟 RAB-SEP / port_active 不同: SAC-Hull cut 是 (sep, commodity set, capacity)
全局 inequality, 不是 (owner, blocker) 局部 conjunction.
"""

from __future__ import annotations
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0),
}

OUT_FILE = Path("docs/research/sac_hull_separator_capacity_20260518/phase0_oracle_stats.json")


@dataclass(frozen=True)
class Separator:
    sep_id: str
    kind: str  # "axis_V" | "axis_H" | "ghost_moat_top" | "ghost_moat_bot" | ...
    wall_cells: frozenset  # cells in W
    is_left_of_wall: Any   # callable (x, y) -> bool, True if cell in L

    def left_count(self, cells: Set[Tuple[int, int]]) -> int:
        return sum(1 for c in cells if self.is_left_of_wall(c[0], c[1]))


def build_separator_library(grid_w: int, grid_h: int, ghost_anchor: Tuple[int, int] | None,
                            ghost_size: Tuple[int, int] | None) -> List[Separator]:
    seps: List[Separator] = []
    # axis vertical V_x: W = {(x, y) for y in 0..grid_h-1}, L = {x' < x}, R = {x' > x}
    for x in range(1, grid_w - 1):
        wall = frozenset((x, y) for y in range(grid_h))
        seps.append(Separator(
            sep_id=f"V_{x}", kind="axis_V", wall_cells=wall,
            is_left_of_wall=lambda cx, cy, x0=x: cx < x0,
        ))
    # axis horizontal H_y: W = {(x, y) for x in 0..grid_w-1}, L = y' < y
    for y in range(1, grid_h - 1):
        wall = frozenset((x, y) for x in range(grid_w))
        seps.append(Separator(
            sep_id=f"H_{y}", kind="axis_H", wall_cells=wall,
            is_left_of_wall=lambda cx, cy, y0=y: cy < y0,
        ))
    # ghost moat: 4 个 collar
    if ghost_anchor is not None and ghost_size is not None:
        ax, ay = ghost_anchor
        gw, gh = ghost_size
        # top moat (ghost top edge line)
        top_y = ay + gh
        if 0 <= top_y < grid_h:
            wall = frozenset((x, top_y) for x in range(ax, ax + gw) if 0 <= x < grid_w)
            seps.append(Separator(
                sep_id=f"GM_top_{top_y}", kind="ghost_moat_top", wall_cells=wall,
                is_left_of_wall=lambda cx, cy, y0=top_y, ax_=ax, gw_=gw: (cy > y0 and ax_ <= cx < ax_ + gw_),
            ))
        # bot moat
        bot_y = ay - 1
        if 0 <= bot_y < grid_h:
            wall = frozenset((x, bot_y) for x in range(ax, ax + gw) if 0 <= x < grid_w)
            seps.append(Separator(
                sep_id=f"GM_bot_{bot_y}", kind="ghost_moat_bot", wall_cells=wall,
                is_left_of_wall=lambda cx, cy, y0=bot_y, ax_=ax, gw_=gw: (cy < y0 and ax_ <= cx < ax_ + gw_),
            ))
        # left moat
        left_x = ax - 1
        if 0 <= left_x < grid_w:
            wall = frozenset((left_x, y) for y in range(ay, ay + gh) if 0 <= y < grid_h)
            seps.append(Separator(
                sep_id=f"GM_left_{left_x}", kind="ghost_moat_left", wall_cells=wall,
                is_left_of_wall=lambda cx, cy, x0=left_x, ay_=ay, gh_=gh: (cx < x0 and ay_ <= cy < ay_ + gh_),
            ))
        # right moat
        right_x = ax + gw
        if 0 <= right_x < grid_w:
            wall = frozenset((right_x, y) for y in range(ay, ay + gh) if 0 <= y < grid_h)
            seps.append(Separator(
                sep_id=f"GM_right_{right_x}", kind="ghost_moat_right", wall_cells=wall,
                is_left_of_wall=lambda cx, cy, x0=right_x, ay_=ay, gh_=gh: (cx > x0 and ay_ <= cy < ay_ + gh_),
            ))
    return seps


def classify_pose_commodity_side(
    pose: Mapping[str, Any],
    operation_type: str,
    sep: Separator,
    grid_w: int,
    grid_h: int,
) -> Dict[str, Dict[str, str]]:
    """For each commodity, classify whether the pose's port fronts force the
    commodity's source/sink onto L, R, or are ambiguous.

    Returns {commodity: {"source_side": "L"|"R"|"AMBIG"|"NONE", "sink_side": ...}}
    """
    from src.preprocess.operation_profiles import get_operation_port_profile
    try:
        profile = get_operation_port_profile(operation_type)
    except Exception:
        return {}
    input_commodities = set(profile.input_slots.keys()) if hasattr(profile, "input_slots") else set()
    output_commodities = set(profile.output_slots.keys()) if hasattr(profile, "output_slots") else set()

    def front(port):
        dx, dy = _DIR_DELTA.get(str(port["dir"]), (0, 0))
        return (int(port["x"]) + dx, int(port["y"]) + dy)

    def side_of(cell) -> str:
        cx, cy = cell
        if not (0 <= cx < grid_w and 0 <= cy < grid_h):
            return "OOG"  # out of grid 不计
        if cell in sep.wall_cells:
            return "W"
        return "L" if sep.is_left_of_wall(cx, cy) else "R"

    # input ports → sink, output ports → source
    input_sides = {side_of(front(p)) for p in pose.get("input_port_cells", []) or []}
    output_sides = {side_of(front(p)) for p in pose.get("output_port_cells", []) or []}

    def reduce_sides(sides: Set[str]) -> str:
        # 只看 L/R; 忽略 OOG/W
        lr = sides - {"OOG", "W"}
        if not lr:
            return "NONE"
        if lr == {"L"}:
            return "L"
        if lr == {"R"}:
            return "R"
        return "AMBIG"

    sink_side = reduce_sides(input_sides)
    source_side = reduce_sides(output_sides)

    result: Dict[str, Dict[str, str]] = {}
    for c in input_commodities:
        result.setdefault(c, {"source_side": "NONE", "sink_side": "NONE"})
        result[c]["sink_side"] = sink_side
    for c in output_commodities:
        result.setdefault(c, {"source_side": "NONE", "sink_side": "NONE"})
        result[c]["source_side"] = source_side
    return result


def analyze_separator_violations(
    placement_solution: Dict[str, Dict[str, Any]],
    facility_pools: Dict[str, Any],
    instances_by_id: Dict[str, Any],
    seps: List[Separator],
    grid_w: int,
    grid_h: int,
) -> List[Dict[str, Any]]:
    """Per separator, aggregate commodity forced sides across all owners.

    crossing(c, sep) is True iff:
      (some pose forces source_L for c AND some pose forces sink_R for c) OR
      (some pose forces source_R for c AND some pose forces sink_L for c)

    required_crossings = #c with crossing(c, sep) == True
    capacity_upper_bound = 2 * free_wall_cells
    violation iff required_crossings > capacity_upper_bound
    """
    # build occupied
    occupied: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        for cell in pool[pose_idx].get("occupied_cells", []) or []:
            occupied.add((int(cell[0]), int(cell[1])))

    violations: List[Dict[str, Any]] = []
    for sep in seps:
        free_wall = len(sep.wall_cells - occupied)
        capacity = 2 * free_wall
        # aggregate forced sides per commodity
        commodity_force: Dict[str, Dict[str, bool]] = {}
        # key: commodity → {source_L, source_R, sink_L, sink_R: bool}
        for iid, sol in placement_solution.items():
            inst = instances_by_id.get(str(iid))
            if not inst:
                continue
            operation_type = str(inst.get("operation_type", ""))
            tpl = str(sol.get("facility_type", ""))
            pool = facility_pools.get(tpl, [])
            pose_idx = int(sol.get("pose_idx", -1))
            if pose_idx < 0 or pose_idx >= len(pool):
                continue
            pose = pool[pose_idx]
            classification = classify_pose_commodity_side(
                pose, operation_type, sep, grid_w, grid_h,
            )
            for c, sides in classification.items():
                cf = commodity_force.setdefault(c, {
                    "source_L": False, "source_R": False,
                    "sink_L": False, "sink_R": False,
                })
                if sides["source_side"] == "L":
                    cf["source_L"] = True
                elif sides["source_side"] == "R":
                    cf["source_R"] = True
                if sides["sink_side"] == "L":
                    cf["sink_L"] = True
                elif sides["sink_side"] == "R":
                    cf["sink_R"] = True

        crossing_commodities: List[str] = []
        for c, cf in commodity_force.items():
            cross_lr = cf["source_L"] and cf["sink_R"]
            cross_rl = cf["source_R"] and cf["sink_L"]
            if cross_lr or cross_rl:
                crossing_commodities.append(c)
        required = len(crossing_commodities)
        violations.append({
            "sep_id": sep.sep_id,
            "kind": sep.kind,
            "wall_size": len(sep.wall_cells),
            "free_wall_cells": free_wall,
            "capacity_upper_bound": capacity,
            "required_crossings": required,
            "crossing_commodities": crossing_commodities,
            "slack": capacity - required,
            "violation": required > capacity,
        })
    return violations


def main() -> int:
    os.environ.setdefault("EXACT_USE_POSE_BOOL_MASTER", "1")
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print("=== SAC-Hull Phase 0 — separator violation oracle PoC ===")
    print("27×15 anchor (22,28), 1 master OPTIMAL layout")

    # monkey-patch binding.build, dump separator analysis after we have placement
    import src.models.binding_subproblem as bm
    orig_build = bm.PortBindingModel.build
    captured = {"done": False}

    def patched_build(self):
        orig_build(self)
        if captured["done"]:
            return
        captured["done"] = True
        t0 = time.perf_counter()
        from src.models.routing_subproblem import GRID_W, GRID_H
        ghost_anchor = (22, 28)
        ghost_size = (27, 15)
        seps = build_separator_library(GRID_W, GRID_H, ghost_anchor, ghost_size)
        print(f"[oracle] separator count: {len(seps)}", flush=True)
        violations = analyze_separator_violations(
            self.placement_solution, self.facility_pools, self.instances_by_id,
            seps, GRID_W, GRID_H,
        )
        analysis_wall = time.perf_counter() - t0
        violating = [v for v in violations if v["violation"]]
        tight = [v for v in violations if v["slack"] <= 0 and not v["violation"]]
        crossing_distrib = [v["required_crossings"] for v in violations]
        slack_distrib = [v["slack"] for v in violations]
        crossing_distrib.sort(reverse=True)
        slack_distrib.sort()
        top_violations = sorted(violations, key=lambda v: v["slack"])[:20]
        out = {
            "separator_count": len(seps),
            "violation_count": len(violating),
            "tight_count": len(tight),
            "analysis_wall_s": round(analysis_wall, 3),
            "top_required_crossings": crossing_distrib[:15],
            "bottom_slack": slack_distrib[:15],
            "top_violations": top_violations,
        }
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_FILE, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"[oracle] violations: {len(violating)}, tight (slack=0): {len(tight)}, analysis_wall={analysis_wall:.3f}s", flush=True)
        print(f"[oracle] top required_crossings: {crossing_distrib[:10]}", flush=True)
        print(f"[oracle] bottom slack: {slack_distrib[:10]}", flush=True)
        if violating:
            print(f"[oracle] top violation: {top_violations[0]}", flush=True)
        print(f"[oracle] dumped {OUT_FILE}", flush=True)

    bm.PortBindingModel.build = patched_build

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
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 0 PoC done: {status} in {elapsed:.1f}s ===")
    if not captured["done"]:
        print(">>> ❌ oracle 没 fire")
        return 1
    with open(OUT_FILE) as f:
        out = json.load(f)
    if out["violation_count"] >= 1:
        print(f">>> ✅ Phase 0 GO: {out['violation_count']} separator violation(s) found, paradigm 前提验证")
        return 0
    if out["tight_count"] >= 5:
        print(f">>> 🟡 Phase 0 PARTIAL: 0 violation, but {out['tight_count']} tight separators (slack=0) — paradigm 有戏需要 layer-refined capacity")
        return 0
    print(f">>> ❌ Phase 0 NO-GO: 0 violation, {out['tight_count']} tight — corridor bottleneck 不是主因")
    return 1


if __name__ == "__main__":
    sys.exit(main())

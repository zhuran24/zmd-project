"""Path 17 D2 Phase 3 — Augmented master Candidate D cheap gate probe.

跟 phase0_candidate_d2_probe.py 不同: D2 vars 直接注入 **master** CP-SAT model,
不是 sub-problem 后台跑. master.solve 600s 看能否在 augmented form 下出
OPTIMAL/INFEASIBLE, 检验 augmented master paradigm 资源 + 可解性.

Phase 0 cheap gate 用 **单 commodity aggregation** (no per-commodity differentiation):
- u[c] BoolVar per grid cell
- e[(c1, c2)] BoolVar per directed arc within grid
- per pose: 若 x_{i, p_i}=1, 则 pose.occupied_cells 上 u=0, port front_cell 上 u=1
- per cell: out_flow - in_flow = sum_{output port at c} x_{...} - sum_{input port at c} x_{...}

GO 信号:
- master.solve 600s 出 OPTIMAL or INFEASIBLE (不 UNKNOWN)
- vars ≤ 250K, constraints ≤ 650K, RSS peak ≤ 12 GB

NO-GO:
- 600s UNKNOWN (跟 Path 08 同 dead zone)
- RAM 爆 (跟 Path 16 GOC-C2 同 pattern)
- master FEASIBLE 但 routing 真 verify reject (paradigm necessary 不 sufficient)
  → 但 routing verify 不在 Phase 0 范围, 留 Phase 1+

Single-commodity 是 cheap gate 简化: 真 D2 paradigm 用 per-commodity flow. 若 single
commodity 都跑不动, multi-commodity (10x vars) 100% 跑不动. 反之 single OK 才进 Phase 1
做 multi-commodity 真版.
"""

from __future__ import annotations

import gc
import json
import os
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ortools.sat.python import cp_model

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT_FILE = Path("paths/17_candidate_d_commodity_flow/phase3_augmented_master_stats.json")

GRID_W = 70
GRID_H = 70
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}

ANCHOR = (27, 15, 22, 28, "interior_22_28")  # cheap gate: 单 anchor


def _reset_env(ax: int, ay: int) -> None:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ax},{ay}"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_SEPARATOR_HULL_DYNAMIC_FALL_THROUGH",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
        "EXACT_B1_PATCH_ROUTING_CORE", "EXACT_B1_D2_COMMODITY_FLOW",
        "EXACT_USE_PORT_ACTIVE", "EXACT_B1_PORT_CLEARANCE_HARD",
    ):
        os.environ.pop(k, None)


def _augment_master_with_d2_single_commodity(master: Any) -> Dict[str, int]:
    """Bolt-on D2 single-commodity vars + constraints into master.model.

    master must be PoseBoolExactMasterDelegate built. Uses master._coordinate_delegate's
    x_vars / ro_vars + facility_pools to derive pose port/occupied cells.

    Skips power_pole vars (pole has no I/O ports).
    """
    model = master.model
    delegate = master._coordinate_delegate
    x_vars = delegate.x_vars  # (gid, pose_idx) -> BoolVar
    ro_vars = delegate.ro_vars  # (tpl, pose_idx) -> BoolVar

    forbidden_cells = delegate._forbidden_cells()  # ghost anchor cells

    # u[c] BoolVar per grid cell (incl. forbidden — but pose covers ghost cells so u must be 0)
    u_vars: Dict[Tuple[int, int], Any] = {}
    for x in range(GRID_W):
        for y in range(GRID_H):
            u_vars[(x, y)] = model.NewBoolVar(f"d2_u_{x}_{y}")

    # ghost cells: u must be 0 (route 不能穿过 ghost)
    for c in forbidden_cells:
        if c in u_vars:
            model.Add(u_vars[c] == 0)

    # e[(c1, c2)] BoolVar per directed arc within grid (excluding ghost cells)
    e_vars: Dict[Tuple[int, int, int, int], Any] = {}
    for (x, y) in u_vars:
        if (x, y) in forbidden_cells:
            continue
        for _d, (dx, dy) in DIR_DELTA.items():
            nx, ny = x + dx, y + dy
            if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
                continue
            if (nx, ny) in forbidden_cells:
                continue
            e_vars[(x, y, nx, ny)] = model.NewBoolVar(f"d2_e_{x}_{y}_{nx}_{ny}")

    # channeling: e ⇒ u[c1] AND e ⇒ u[c2]
    channeling_count = 0
    for (x1, y1, x2, y2), e_var in e_vars.items():
        model.AddImplication(e_var, u_vars[(x1, y1)])
        model.AddImplication(e_var, u_vars[(x2, y2)])
        channeling_count += 2

    # Per cell: out_flow - in_flow = balance (per-cell linear equation)
    # balance(c) = sum_{output port front at c} x_pose - sum_{input port front at c} x_pose
    out_arcs_by_c: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    in_arcs_by_c: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    for (x1, y1, x2, y2), e_var in e_vars.items():
        out_arcs_by_c[(x1, y1)].append(e_var)
        in_arcs_by_c[(x2, y2)].append(e_var)

    # iterate pose vars, derive per-pose port/occupied cells
    # pose_pool_for_pose_var: (pose_var, pose_dict)
    pose_data: List[Tuple[Any, Dict[str, Any]]] = []
    for (gid, pose_idx), x_var in x_vars.items():
        tpl = delegate._mandatory_template_by_group[gid]
        pool = master.facility_pools.get(tpl, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose_data.append((x_var, pool[pose_idx]))
    for (tpl, pose_idx), ro_var in ro_vars.items():
        pool = master.facility_pools.get(tpl, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose_data.append((ro_var, pool[pose_idx]))

    # Per cell balance terms (linear): build map cell -> list of (sign, pose_var)
    out_port_terms: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    in_port_terms: Dict[Tuple[int, int], List[Any]] = defaultdict(list)
    u_force_by_cell: Dict[Tuple[int, int], List[Any]] = defaultdict(list)  # 这些 pose 选则 u[c]=1
    u_block_by_cell: Dict[Tuple[int, int], List[Any]] = defaultdict(list)  # 这些 pose 选则 u[c]=0
    forced_port_count = 0
    blocked_port_count = 0

    for (pose_var, pose) in pose_data:
        # occupied cells: u must be 0 if pose selected
        for c in pose.get("occupied_cells", []) or []:
            cx, cy = int(c[0]), int(c[1])
            u_block_by_cell[(cx, cy)].append(pose_var)
        # output port front cells: +1 balance + u=1
        for port in pose.get("output_port_cells", []) or []:
            direction = str(port.get("dir", ""))
            dx, dy = DIR_DELTA.get(direction, (0, 0))
            fx, fy = int(port.get("x", 0)) + dx, int(port.get("y", 0)) + dy
            if not (0 <= fx < GRID_W and 0 <= fy < GRID_H):
                blocked_port_count += 1
                continue
            if (fx, fy) in forbidden_cells:
                blocked_port_count += 1
                continue
            out_port_terms[(fx, fy)].append(pose_var)
            u_force_by_cell[(fx, fy)].append(pose_var)
            forced_port_count += 1
        # input port front cells: -1 balance + u=1
        for port in pose.get("input_port_cells", []) or []:
            direction = str(port.get("dir", ""))
            dx, dy = DIR_DELTA.get(direction, (0, 0))
            fx, fy = int(port.get("x", 0)) + dx, int(port.get("y", 0)) + dy
            if not (0 <= fx < GRID_W and 0 <= fy < GRID_H):
                blocked_port_count += 1
                continue
            if (fx, fy) in forbidden_cells:
                blocked_port_count += 1
                continue
            in_port_terms[(fx, fy)].append(pose_var)
            u_force_by_cell[(fx, fy)].append(pose_var)
            forced_port_count += 1

    # u-block: pose_var=1 ⇒ u[c]=0 (cell exclusivity 已 enforce 但加这条让 u 跟 pose 显式 channel)
    u_block_count = 0
    for cell, blockers in u_block_by_cell.items():
        if not blockers:
            continue
        # sum(blockers) + u[cell] <= 1
        model.Add(u_vars[cell] + sum(blockers) <= 1)
        u_block_count += 1

    # u-force: pose_var=1 ⇒ u[c]=1 (port adherence)
    u_force_count = 0
    for cell, forcers in u_force_by_cell.items():
        if not forcers:
            continue
        for fv in forcers:
            model.Add(u_vars[cell] == 1).OnlyEnforceIf(fv)
            u_force_count += 1

    # Per cell flow conservation: out_flow - in_flow = sum(output port terms) - sum(input port terms)
    flow_cons_count = 0
    for (x, y) in u_vars:
        if (x, y) in forbidden_cells:
            continue
        out_flow = sum(out_arcs_by_c.get((x, y), []))
        in_flow = sum(in_arcs_by_c.get((x, y), []))
        out_ports = out_port_terms.get((x, y), [])
        in_ports = in_port_terms.get((x, y), [])
        # out_flow - in_flow - sum(out_ports) + sum(in_ports) == 0
        lhs_terms: List[Any] = [out_flow, -in_flow]
        lhs_terms.extend([-v for v in out_ports])
        lhs_terms.extend([v for v in in_ports])
        if isinstance(out_flow, int) and out_flow == 0 and isinstance(in_flow, int) and in_flow == 0 \
                and not out_ports and not in_ports:
            continue  # 空约束跳
        model.Add(sum(lhs_terms) == 0)
        flow_cons_count += 1

    return {
        "u_vars": len(u_vars),
        "e_vars": len(e_vars),
        "channeling_implications": channeling_count,
        "u_block_constraints": u_block_count,
        "u_force_constraints": u_force_count,
        "flow_conservation_constraints": flow_cons_count,
        "pose_data_count": len(pose_data),
        "forced_port_count": forced_port_count,
        "blocked_port_count": blocked_port_count,
        "ghost_cells_count": len(forbidden_cells),
    }


def probe_single_anchor(ghost_w: int, ghost_h: int, ax: int, ay: int, label: str,
                         wall_seconds: float = 600.0) -> Dict[str, Any]:
    _reset_env(ax, ay)

    print(f"\n>>> {label}: {ghost_w}x{ghost_h} ({ax},{ay}) wall={wall_seconds}s", flush=True)

    from src.search.benders_loop import create_exact_search_session
    from src.models.master_model import (
        MasterPlacementModel,
        infer_exact_required_pose_optional_counts,
    )

    project_root = Path(".").resolve()

    t0 = time.perf_counter()
    session = create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    session_wall = time.perf_counter() - t0

    inferred_counts = infer_exact_required_pose_optional_counts(
        session.core.rules, session.core.generic_io_requirements
    )

    t1 = time.perf_counter()
    master = MasterPlacementModel(
        list(session.core.source_instances),
        dict(session.core.facility_pools),
        session.core.rules,
        ghost_rect=(int(ghost_w), int(ghost_h)),
        skip_power_coverage=bool(session.core.skip_power_coverage),
        enable_symmetry_breaking=bool(session.core.enable_symmetry_breaking),
        generic_io_requirements=session.core.generic_io_requirements,
        exact_required_pose_optional_counts=inferred_counts,
        solve_mode="certified_exact",
        ghost_anchor_filter=[(ax, ay)],
    )
    master.build()
    base_build_wall = time.perf_counter() - t1

    # Baseline vars/constraints before augmentation
    try:
        proto = master.model.Proto()
        base_vars = len(proto.variables)
        base_cstr = len(proto.constraints)
    except Exception:
        base_vars = -1
        base_cstr = -1

    print(f"  [base] build={base_build_wall:.1f}s vars={base_vars} cstr={base_cstr}", flush=True)

    # Augment
    t2 = time.perf_counter()
    augment_stats = _augment_master_with_d2_single_commodity(master)
    augment_wall = time.perf_counter() - t2

    try:
        proto = master.model.Proto()
        total_vars = len(proto.variables)
        total_cstr = len(proto.constraints)
    except Exception:
        total_vars = -1
        total_cstr = -1

    print(
        f"  [augment] +{augment_stats['u_vars']} u + {augment_stats['e_vars']} e, "
        f"+{augment_stats['flow_conservation_constraints']} flow_cons, "
        f"build_aug={augment_wall:.1f}s total_vars={total_vars} total_cstr={total_cstr}",
        flush=True,
    )

    gc.collect()
    rss_pre_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

    # solve master with wall budget
    print(f"  [solve] starting master.solve(time_limit_seconds={wall_seconds})...", flush=True)
    t3 = time.perf_counter()
    try:
        status = master.solve(time_limit_seconds=wall_seconds)
    except Exception as exc:
        return {
            "label": label,
            "anchor": (ax, ay),
            "ghost_size": (ghost_w, ghost_h),
            "session_wall_s": round(session_wall, 1),
            "base_build_wall_s": round(base_build_wall, 1),
            "augment_wall_s": round(augment_wall, 1),
            "augment_stats": augment_stats,
            "base_vars": base_vars,
            "base_cstr": base_cstr,
            "total_vars": total_vars,
            "total_cstr": total_cstr,
            "solve_status": f"ERROR: {type(exc).__name__}: {exc}",
            "solve_wall_s": round(time.perf_counter() - t3, 1),
            "rss_pre_mb": round(rss_pre_mb, 1),
            "rss_post_mb": -1,
        }
    solve_wall = time.perf_counter() - t3

    rss_post_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

    status_str = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(int(status), f"UNKNOWN_{status}")

    print(
        f"  [solve] status={status_str} wall={solve_wall:.1f}s "
        f"rss_pre={rss_pre_mb:.1f}MB rss_post={rss_post_mb:.1f}MB",
        flush=True,
    )

    return {
        "label": label,
        "anchor": (ax, ay),
        "ghost_size": (ghost_w, ghost_h),
        "session_wall_s": round(session_wall, 1),
        "base_build_wall_s": round(base_build_wall, 1),
        "augment_wall_s": round(augment_wall, 1),
        "augment_stats": augment_stats,
        "base_vars": base_vars,
        "base_cstr": base_cstr,
        "total_vars": total_vars,
        "total_cstr": total_cstr,
        "solve_status": status_str,
        "solve_wall_s": round(solve_wall, 1),
        "rss_pre_mb": round(rss_pre_mb, 1),
        "rss_post_mb": round(rss_post_mb, 1),
    }


def main() -> int:
    print("=== Path 17 Phase 3 — Augmented master Candidate D cheap gate ===")
    print("  Single anchor (22,28) 27x15, wall=600s, single-commodity aggregation\n")

    wall_seconds = float(os.environ.get("EXACT_B1_MASTER_AUGMENT_D2_WALL_SECONDS", "600"))
    result = probe_single_anchor(*ANCHOR, wall_seconds=wall_seconds)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[dumped] {OUT_FILE}")

    print("\n=== Phase 3 cheap gate verdict ===")
    status = result.get("solve_status", "?")
    wall = result.get("solve_wall_s", 99999)
    vars_ = result.get("total_vars", 999999)
    cstr = result.get("total_cstr", 999999)
    rss = result.get("rss_post_mb", 999999)

    print(f"  status: {status}")
    print(f"  solve_wall: {wall}s (budget {wall_seconds}s)")
    print(f"  total_vars: {vars_} (target ≤ 250K)")
    print(f"  total_cstr: {cstr} (target ≤ 650K)")
    print(f"  rss_post: {rss:.0f} MB (target ≤ 12288 MB)")

    pre1_solve_ok = status in {"OPTIMAL", "INFEASIBLE"} and wall <= wall_seconds
    pre2_vars_ok = vars_ <= 250_000
    pre2_cstr_ok = cstr <= 650_000
    pre2_rss_ok = rss <= 12 * 1024

    print(f"\n  Pre1 (solve OPTIMAL/INFEASIBLE in budget): {'OK' if pre1_solve_ok else 'FAIL'}")
    print(f"  Pre2 vars: {'OK' if pre2_vars_ok else 'FAIL'}")
    print(f"  Pre2 cstr: {'OK' if pre2_cstr_ok else 'FAIL'}")
    print(f"  Pre2 RSS: {'OK' if pre2_rss_ok else 'FAIL'}")

    if pre1_solve_ok and pre2_vars_ok and pre2_cstr_ok and pre2_rss_ok:
        print(">>> ✅ Phase 3 GO — augmented master single-commodity works; proceed to Phase 1 multi-commodity")
        return 0
    print(">>> ❌ Phase 3 NO-GO")
    if not pre1_solve_ok:
        print(f"     solve verdict 不 sound: status={status} wall={wall}s")
    if not pre2_vars_ok:
        print(f"     vars 爆: {vars_} > 250K")
    if not pre2_cstr_ok:
        print(f"     cstr 爆: {cstr} > 650K")
    if not pre2_rss_ok:
        print(f"     RAM 爆: {rss} MB > 12 GB")
    return 1


if __name__ == "__main__":
    sys.exit(main())

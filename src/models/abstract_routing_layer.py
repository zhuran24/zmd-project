"""SAC-Hull Phase 3: L2 abstract routing layer.

Given master OPTIMAL layout, run a lightweight CP-SAT subproblem (L2) that:
- 决策: per ambiguous port choose side (L/R) per separator; per generic IO slot
  choose (commodity, side)
- 约束: SAC capacity hull per separator (sum of commodity crossings <= 2 * free
  wall cells)

L2 result:
- FEASIBLE: all separators satisfied under best ambiguous side choices → 进
  binding/routing
- INFEASIBLE: no side choice satisfies all separators → SAC cut to master
- TIMEOUT: 走 binding/routing baseline

L2 比 master 小很多: 不重 decide pose placement, 只 decide ambiguous side. 估
vars ≤ 5K, constraints ≤ 5K. L2 solve ≤ 5s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from ortools.sat.python import cp_model

from src.models.separator_capacity_hull import (
    Separator,
    build_static_separator_library,
    _DIR_DELTA,
)


@dataclass
class AbstractRoutingResult:
    status: str  # "FEASIBLE" | "INFEASIBLE" | "TIMEOUT"
    wall_seconds: float
    violations: List[Any]  # SeparatorViolation list if INFEASIBLE
    stats: Dict[str, Any]


def _front_side_class(port: Mapping[str, Any], sep: Separator, grid_w: int, grid_h: int) -> str:
    """Return 'L', 'R', 'W' (in wall), or 'OOG' (out of grid)."""
    dx, dy = _DIR_DELTA.get(str(port.get("dir", "")), (0, 0))
    fx, fy = int(port.get("x", 0)) + dx, int(port.get("y", 0)) + dy
    if not (0 <= fx < grid_w and 0 <= fy < grid_h):
        return "OOG"
    if (fx, fy) in sep.wall_cells:
        return "W"
    return "L" if sep.is_left_of_wall(fx, fy) else "R"


def solve_abstract_routing(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Any],
    instances_by_id: Mapping[str, Any],
    grid_w: int,
    grid_h: int,
    ghost_anchor: Tuple[int, int] | None = None,
    ghost_size: Tuple[int, int] | None = None,
    time_limit_seconds: float = 5.0,
    separator_limit: int = 64,
    include_axis: bool = True,
    include_ghost_moat: bool = True,
    routing_free_sink_commodities: Optional[Set[str]] = None,
) -> AbstractRoutingResult:
    """L2 abstract routing subproblem.

    For each pose in placement_solution + each commodity it has, determine
    its "forced" or "ambiguous" side w.r.t. each separator. For ambiguous
    ports, L2 decides best side. Then enforce SAC capacity hull.

    Returns AbstractRoutingResult.
    """
    import time
    t_start = time.perf_counter()

    seps = build_static_separator_library(
        grid_w=grid_w, grid_h=grid_h,
        ghost_anchor=ghost_anchor, ghost_size=ghost_size,
        include_axis=include_axis, include_ghost_moat=include_ghost_moat,
        limit=separator_limit,
    )

    # build occupied for capacity calc
    occupied: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        for cell in pool[pose_idx].get("occupied_cells", []) or []:
            occupied.add((int(cell[0]), int(cell[1])))

    # L2 CP-SAT model
    model = cp_model.CpModel()
    # decision vars: 每 (owner, sep, commodity, role) 的 ambiguous side
    # commodity 来自 owner operation_type 的 input/output commodities
    # role: input (sink) or output (source)
    # 实际 forced side 不需 decision var (fixed contribution). 只 ambiguous 加 var.

    from src.preprocess.operation_profiles import get_operation_port_profile

    # forced_side_count[sep_id][commodity][role][side] = count of forced poses
    # role: "source" (output) or "sink" (input)
    # side: "L" or "R"
    forced_count: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {
        s.sep_id: {} for s in seps
    }

    # ambiguous_decision_vars[(sep_id, owner_id, commodity, role)] = BoolVar
    # 表示 "该 owner 对该 commodity (role) 在该 sep 上选 L (False=L, True=R), 但
    # 只对 truly ambiguous ports (input or output 有 ports on both sides)"
    ambig_vars: Dict[Tuple[str, str, str, str], Any] = {}
    stats: Dict[str, Any] = {
        "separator_count": len(seps),
        "ambiguous_vars": 0,
        "forced_classifications": 0,
        "capacity_constraints": 0,
    }

    for iid, sol in placement_solution.items():
        inst = instances_by_id.get(str(iid))
        if not inst:
            continue
        operation_type = str(inst.get("operation_type", ""))
        try:
            profile = get_operation_port_profile(operation_type)
        except Exception:
            continue
        routing_free_outputs = {str(c) for c in (routing_free_sink_commodities or set())}
        input_commodities = set(profile.input_slots.keys()) if hasattr(profile, "input_slots") else set()
        output_commodities = (
            {
                str(c)
                for c in profile.output_slots.keys()
                if str(c) not in routing_free_outputs
            }
            if hasattr(profile, "output_slots")
            else set()
        )
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]

        for sep in seps:
            # 对每 commodity, 算 input ports / output ports 的 side 分布
            input_sides = {_front_side_class(p, sep, grid_w, grid_h)
                           for p in pose.get("input_port_cells", []) or []}
            output_sides = {_front_side_class(p, sep, grid_w, grid_h)
                            for p in pose.get("output_port_cells", []) or []}
            input_lr = input_sides - {"OOG", "W"}
            output_lr = output_sides - {"OOG", "W"}

            for c in input_commodities:
                # role: sink
                stats["forced_classifications"] += 1
                if input_lr == {"L"}:
                    fc = forced_count[sep.sep_id].setdefault(c, {}).setdefault("sink", {"L": 0, "R": 0})
                    fc["L"] = 1
                elif input_lr == {"R"}:
                    fc = forced_count[sep.sep_id].setdefault(c, {}).setdefault("sink", {"L": 0, "R": 0})
                    fc["R"] = 1
                elif input_lr == {"L", "R"}:
                    # ambiguous: L2 decides
                    var = model.NewBoolVar(f"ambig_{sep.sep_id}_{iid}_{c}_sink")
                    ambig_vars[(sep.sep_id, str(iid), c, "sink")] = var
                    stats["ambiguous_vars"] += 1
            for c in output_commodities:
                stats["forced_classifications"] += 1
                if output_lr == {"L"}:
                    fc = forced_count[sep.sep_id].setdefault(c, {}).setdefault("source", {"L": 0, "R": 0})
                    fc["L"] = 1
                elif output_lr == {"R"}:
                    fc = forced_count[sep.sep_id].setdefault(c, {}).setdefault("source", {"L": 0, "R": 0})
                    fc["R"] = 1
                elif output_lr == {"L", "R"}:
                    var = model.NewBoolVar(f"ambig_{sep.sep_id}_{iid}_{c}_source")
                    ambig_vars[(sep.sep_id, str(iid), c, "source")] = var
                    stats["ambiguous_vars"] += 1

    # capacity hull per sep:
    # 对每 commodity: source_L = forced_count[source][L] OR any ambig with var=False (=L)
    # source_R 同, sink_L 同
    # cross_LR = source_L AND sink_R, cross_RL = source_R AND sink_L
    # cross = OR(cross_LR, cross_RL)
    # sum_c cross <= 2 * (|W| - occupied)
    for sep in seps:
        free_wall = len(sep.wall_cells - occupied)
        capacity = 2 * free_wall
        commodity_cross_vars: List[Any] = []
        sep_forced = forced_count.get(sep.sep_id, {})
        all_commodities = set(sep_forced.keys()) | {
            key[2] for key in ambig_vars if key[0] == sep.sep_id
        }
        for c in all_commodities:
            roles = sep_forced.get(c, {})
            # source_L: forced count L > 0 OR any ambig source var = 0 (L)
            source_L_var = model.NewBoolVar(f"sL_{sep.sep_id}_{c}_L2")
            source_R_var = model.NewBoolVar(f"sR_{sep.sep_id}_{c}_L2")
            sink_L_var = model.NewBoolVar(f"kL_{sep.sep_id}_{c}_L2")
            sink_R_var = model.NewBoolVar(f"kR_{sep.sep_id}_{c}_L2")

            source_fc = roles.get("source", {"L": 0, "R": 0})
            sink_fc = roles.get("sink", {"L": 0, "R": 0})

            # source_L: forced source L OR (ambig source var == 0, i.e., var.Not())
            source_L_lits: List[Any] = []
            source_R_lits: List[Any] = []
            sink_L_lits: List[Any] = []
            sink_R_lits: List[Any] = []
            for (sep_id, iid, comm, role), var in ambig_vars.items():
                if sep_id != sep.sep_id or comm != c:
                    continue
                if role == "source":
                    source_L_lits.append(var.Not())
                    source_R_lits.append(var)
                elif role == "sink":
                    sink_L_lits.append(var.Not())
                    sink_R_lits.append(var)

            # source_L = 1 iff source_fc['L'] > 0 OR any source_L_lit = 1
            if source_fc["L"] > 0:
                model.Add(source_L_var == 1)
            elif source_L_lits:
                model.AddMaxEquality(source_L_var, source_L_lits)
            else:
                model.Add(source_L_var == 0)
            if source_fc["R"] > 0:
                model.Add(source_R_var == 1)
            elif source_R_lits:
                model.AddMaxEquality(source_R_var, source_R_lits)
            else:
                model.Add(source_R_var == 0)
            if sink_fc["L"] > 0:
                model.Add(sink_L_var == 1)
            elif sink_L_lits:
                model.AddMaxEquality(sink_L_var, sink_L_lits)
            else:
                model.Add(sink_L_var == 0)
            if sink_fc["R"] > 0:
                model.Add(sink_R_var == 1)
            elif sink_R_lits:
                model.AddMaxEquality(sink_R_var, sink_R_lits)
            else:
                model.Add(sink_R_var == 0)

            cross_LR = model.NewBoolVar(f"cLR_{sep.sep_id}_{c}_L2")
            model.Add(cross_LR >= source_L_var + sink_R_var - 1)
            model.Add(cross_LR <= source_L_var)
            model.Add(cross_LR <= sink_R_var)
            cross_RL = model.NewBoolVar(f"cRL_{sep.sep_id}_{c}_L2")
            model.Add(cross_RL >= source_R_var + sink_L_var - 1)
            model.Add(cross_RL <= source_R_var)
            model.Add(cross_RL <= sink_L_var)
            cross = model.NewBoolVar(f"c_{sep.sep_id}_{c}_L2")
            model.AddMaxEquality(cross, [cross_LR, cross_RL])
            commodity_cross_vars.append(cross)

        if commodity_cross_vars:
            model.Add(sum(commodity_cross_vars) <= capacity)
            stats["capacity_constraints"] += 1

    # solve L2
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = 4
    status_int = solver.Solve(model)
    wall = time.perf_counter() - t_start

    if status_int == cp_model.OPTIMAL or status_int == cp_model.FEASIBLE:
        status = "FEASIBLE"
    elif status_int == cp_model.INFEASIBLE:
        status = "INFEASIBLE"
    else:
        status = "TIMEOUT"

    # If INFEASIBLE, find violations under the BEST attempt (most ambiguous selected
    # towards minimize crossing — but CP-SAT proved no assignment works).
    # 简化: 同 Phase 2 analyze (forced + best ambig 已 incorporated by L2).
    violations: List[Any] = []
    if status == "INFEASIBLE":
        # 这里我们 simply use original analyze without ambiguous resolution as
        # violation report. Phase 2 dynamic cut 已经在使用这条数据.
        from src.search.separator_capacity_separator import analyze_layout_for_separator_violations
        violations = analyze_layout_for_separator_violations(
            placement_solution=placement_solution,
            facility_pools=facility_pools,
            instances_by_id=instances_by_id,
            grid_w=grid_w, grid_h=grid_h,
            ghost_anchor=ghost_anchor, ghost_size=ghost_size,
            include_axis=include_axis, include_ghost_moat=include_ghost_moat,
            separator_limit=separator_limit,
            routing_free_sink_commodities=routing_free_sink_commodities,
        )

    return AbstractRoutingResult(
        status=status,
        wall_seconds=wall,
        violations=violations,
        stats=stats,
    )

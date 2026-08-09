"""Path 17 D2 — Commodity cell-flow separator orchestrator.

Pipeline: master OPTIMAL + binding FEASIBLE + port_specs → build D2 model →
solve in budget → if INFEASIBLE, extract assumption core → master no-good cut.

D2 cut form: `sum_{(i,p_i) in core} x_{i,p_i} ≤ |core| - 1` (instance-pose
conjunction no-good, 跟 RAB-SEP cert 同形式).

soundness: D2 model 是 production C2 routing 的 relaxation (cell capacity ≤ 1
per layer 是 必要 condition, flow conservation 也是 必要 condition). 如果
relaxation INFEASIBLE under owner subset S, 任何包含 S 的 master layout 也
production C2-INFEASIBLE. cut sound.

fail-closed: D2 exception / UNKNOWN / FEASIBLE 都不写 cut, 让 LBBD loop fall
through 到现有 binding/routing path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from src.models.d2_commodity_flow_core import (
    D2CommodityFlowCore,
    D2CoreResult,
    D2PoseAssumption,
)

GRID_W = 70
GRID_H = 70


@dataclass
class D2SeparationResult:
    """One D2 separation pass on a master OPTIMAL layout."""
    cut_added: bool
    d2_status: str  # FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID / ERROR
    d2_wall_s: float
    d2_total_vars: int
    d2_constraints: int
    raw_core_size: int
    cut_metadata: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


def _placement_to_occupied(
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Set[Tuple[int, int]]:
    occupied: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        for cell in pool[pose_idx].get("occupied_cells", []) or []:
            occupied.add((int(cell[0]), int(cell[1])))
    return occupied


def _build_pose_assumptions_for_owners_with_ports(
    placement_solution: Mapping[str, Mapping[str, Any]],
    port_specs: Sequence[Mapping[str, Any]],
) -> List[D2PoseAssumption]:
    """One assumption literal per owner that has at least one port in port_specs."""
    seen_instances: Set[str] = set()
    assumptions: List[D2PoseAssumption] = []
    for ps in port_specs:
        iid = str(ps.get("instance_id", ""))
        if not iid or iid in seen_instances:
            continue
        seen_instances.add(iid)
        sol = placement_solution.get(iid, {})
        pose_idx = int(sol.get("pose_idx", -1))
        assumptions.append(D2PoseAssumption(
            instance_id=iid,
            pose_idx=pose_idx,
            assumption_name=f"d2_assum_{iid}",
        ))
    return assumptions


def _build_d2_cut_metadata(
    *,
    d2_result: D2CoreResult,
    raw_core: Sequence[D2PoseAssumption],
) -> Dict[str, Any]:
    return {
        "kind": "d2_commodity_flow_core_cut",
        "core_size": len(raw_core),
        "core_owners": [pa.instance_id for pa in raw_core],
        "d2_wall_s": d2_result.wall_s,
        "d2_total_vars": d2_result.u_vars_count + d2_result.e_vars_count,
        "d2_constraints": d2_result.constraints_count,
        "d2_blocked_port_count": d2_result.blocked_port_count,
        "d2_forced_port_count": d2_result.forced_port_count,
    }


def run_d2_separation(
    *,
    master_delegate: Any,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    port_specs: Sequence[Mapping[str, Any]],
    time_limit: float = 30.0,
) -> D2SeparationResult:
    """End-to-end D2 separation:
    1. Build D2 model on full grid based on placement + port_specs.
    2. Solve with time budget.
    3. If INFEASIBLE, extract assumption core.
    4. Add master no-good cut `sum x_{i,p_i} <= |core|-1`.
    5. Return result with metadata.
    """
    t_start = time.perf_counter()

    if not placement_solution or not port_specs:
        return D2SeparationResult(
            cut_added=False, d2_status="ERROR", d2_wall_s=0.0,
            d2_total_vars=0, d2_constraints=0, raw_core_size=0,
            reason="empty_placement_or_ports",
        )

    occupied = _placement_to_occupied(placement_solution, facility_pools)
    assumptions = _build_pose_assumptions_for_owners_with_ports(placement_solution, port_specs)
    if not assumptions:
        return D2SeparationResult(
            cut_added=False, d2_status="ERROR", d2_wall_s=0.0,
            d2_total_vars=0, d2_constraints=0, raw_core_size=0,
            reason="no_assumption_owners",
        )

    try:
        d2 = D2CommodityFlowCore(
            occupied_cells=occupied,
            port_specs=port_specs,
            pose_assumptions=assumptions,
        )
        d2.build()
        status_str = d2.solve(time_limit=time_limit)
        result = d2.build_result()
    except Exception as exc:
        return D2SeparationResult(
            cut_added=False, d2_status="ERROR", d2_wall_s=time.perf_counter() - t_start,
            d2_total_vars=0, d2_constraints=0, raw_core_size=0,
            reason=f"d2_build_or_solve_error: {type(exc).__name__}",
        )

    if status_str != "INFEASIBLE":
        return D2SeparationResult(
            cut_added=False,
            d2_status=status_str,
            d2_wall_s=result.wall_s,
            d2_total_vars=result.u_vars_count + result.e_vars_count,
            d2_constraints=result.constraints_count,
            raw_core_size=0,
            reason=f"d2_status_{status_str}",
        )

    raw_core = result.core
    if not raw_core:
        return D2SeparationResult(
            cut_added=False,
            d2_status=status_str,
            d2_wall_s=result.wall_s,
            d2_total_vars=result.u_vars_count + result.e_vars_count,
            d2_constraints=result.constraints_count,
            raw_core_size=0,
            reason="d2_infeasible_but_empty_core",
        )

    # cut form: instance-pose conjunction no-good 跟 RAB-SEP 同形式.
    # 用 master.add_benders_cut (existing) 而非 add_patch_routing_core_cut —
    # 后者跟 PCR-CUT signature lifting 绑死, empty patch_cells 会让 owner 全 pose
    # 都同 signature, cut 退化为 forbid owner 整体跟 mandatory exactly-one 冲突 →
    # immediate INFEASIBLE (unsound).
    # add_benders_cut form: sum(x_{i,p_i} for i,p_i in core) <= |core|-1
    # — 只 forbid 当前 (instance, pose_idx) tuple, sound.
    conflict_set: Dict[str, int] = {pa.instance_id: int(pa.pose_idx) for pa in raw_core}
    cut_metadata = _build_d2_cut_metadata(d2_result=result, raw_core=raw_core)

    try:
        cut_added_bool = master_delegate.add_benders_cut(conflict_set)
    except Exception as exc:
        return D2SeparationResult(
            cut_added=False,
            d2_status=status_str,
            d2_wall_s=result.wall_s,
            d2_total_vars=result.u_vars_count + result.e_vars_count,
            d2_constraints=result.constraints_count,
            raw_core_size=len(raw_core),
            cut_metadata=cut_metadata,
            reason=f"master_add_cut_error: {type(exc).__name__}",
        )

    cut_added = bool(cut_added_bool)
    cut_metadata["master_add_reason"] = "ok" if cut_added else "master_rejected"
    return D2SeparationResult(
        cut_added=cut_added,
        d2_status=status_str,
        d2_wall_s=result.wall_s,
        d2_total_vars=result.u_vars_count + result.e_vars_count,
        d2_constraints=result.constraints_count,
        raw_core_size=len(raw_core),
        cut_metadata=cut_metadata,
        reason="ok" if cut_added else "master_rejected",
    )

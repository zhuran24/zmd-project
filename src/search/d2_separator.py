"""Path 17 D2 — Commodity cell-flow separator orchestrator.

Pipeline: master OPTIMAL + binding FEASIBLE + port_specs → build D2 model →
solve in budget → if INFEASIBLE, extract assumption core → master no-good cut.

D2 cut form: support-augmented instance-pose conjunction no-good over the
terminal owners and placement footprints that were compiled into the D2 proof
context.

soundness: D2's CP-SAT core is not itself the certified production-routing
relaxation boundary.  A D2 cut is emitted only when the production routing
precheck already proves the same occupied grid + terminal context impossible
(front_blocked / relaxed_disconnected); the D2 core may then shrink the logged
terminal core, while the master cut remains support-augmented to the full
precheck/D2 context.

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
from src.models.routing_subproblem import RoutingGrid, run_exact_routing_precheck

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
        # V88/CUT-R8-H1: ghost_pick is the empty-rectangle provenance marker, not
        # a facility.  Keep D2's compiled occupancy口径 identical to the routing
        # production path and to the support tuple below.
        if str(iid) == "ghost_pick":
            continue
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


def _build_occupancy_support_pose_terms(
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Dict[str, int]:
    """Return every selected owner whose footprint is encoded as a D2 constant.

    D2's grid domain is built from `occupied_cells` as constants, not from
    assumption literals.  A valid master nogood must therefore be conditioned on
    all selected poses that contributed occupied cells; otherwise a core over
    terminal owners could be replayed under a different obstacle layout.
    """

    support: Dict[str, int] = {}
    for iid, sol in placement_solution.items():
        instance_id = str(iid)
        if instance_id == "ghost_pick":
            continue
        tpl = str(sol.get("facility_type", ""))
        try:
            pose_idx = int(sol.get("pose_idx", -1))
        except Exception:
            continue
        if pose_idx < 0:
            continue
        pool = facility_pools.get(tpl, [])
        if pose_idx >= len(pool):
            continue
        if pool[pose_idx].get("occupied_cells", []) or []:
            support[instance_id] = pose_idx
    return support


def _build_d2_supported_conflict_set(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    assumptions: Sequence[D2PoseAssumption],
    raw_core: Sequence[D2PoseAssumption],
) -> Dict[str, int]:
    """Lift a D2 UNSAT core to the full context actually used by the model.

    The solver core identifies terminal-owner assumptions sufficient under the
    current D2 model.  The model also contains two kinds of unguarded context:
    all non-core terminal owners are free helper literals at their current
    positions, and every selected footprint is compiled into constant occupied
    cells.  Adding both sets to the master nogood only weakens the cut, and makes
    the forbidden tuple no broader than the proof context.
    """

    conflict: Dict[str, int] = {}
    for pa in assumptions:
        conflict[str(pa.instance_id)] = int(pa.pose_idx)
    for instance_id, pose_idx in _build_occupancy_support_pose_terms(
        placement_solution, facility_pools
    ).items():
        conflict[str(instance_id)] = int(pose_idx)
    for pa in raw_core:
        conflict[str(pa.instance_id)] = int(pa.pose_idx)
    return conflict


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


def _d2_port_owner_validation_error(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    port_specs: Sequence[Mapping[str, Any]],
) -> str:
    """Return a fail-closed reason when a port spec has no selected owner.

    Port owners are part of the support-augmented proof context: D2 assumption
    literals and the final master tuple both rely on mapping each terminal back to
    a concrete selected pose.  Treat missing/None/blank owners, ghost owners, and
    owners absent from the current placement as uncertified instead of letting
    them become synthetic strings such as ``"None"`` or pose ``-1``.
    """

    placement_owner_ids = {
        str(instance_id)
        for instance_id in placement_solution
        if str(instance_id) != "ghost_pick"
    }
    for ps in port_specs:
        raw_instance_id = ps.get("instance_id")
        if raw_instance_id is None:
            return "unowned_port_spec_not_certified_for_d2_cut"
        instance_id = str(raw_instance_id)
        if not instance_id.strip():
            return "unowned_port_spec_not_certified_for_d2_cut"
        if instance_id not in placement_owner_ids:
            return "port_spec_owner_not_in_placement_not_certified_for_d2_cut"
    return ""


def _d2_precheck_status_for_cut_context(
    *,
    occupied: Set[Tuple[int, int]],
    port_specs: Sequence[Mapping[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """Return the production routing precheck status that certifies D2 context.

    D2 is a separator only when its support-augmented tuple is no broader than a
    production routing proof context.  The current D2 CP-SAT core is intentionally
    coarse and may be stricter than production routing (for example it has no
    explicit two-layer bridge semantics and uses flow conservation rather than
    splitter/merger topology).  Therefore D2 cuts are accepted only when the
    production precheck already classifies the same occupied grid + terminals as a
    layout-local routing impossibility.  Otherwise D2 may still be a diagnostic,
    but it is not a certified master-cut source.
    """

    summary = run_exact_routing_precheck(
        RoutingGrid(set(occupied), [dict(ps) for ps in port_specs])
    )
    return str(summary.get("status", "unknown")), dict(summary)


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
    4. Add a support-augmented master no-good cut over the D2 proof context.
    5. Return result with metadata.
    """
    t_start = time.perf_counter()

    if not placement_solution or not port_specs:
        return D2SeparationResult(
            cut_added=False, d2_status="ERROR", d2_wall_s=0.0,
            d2_total_vars=0, d2_constraints=0, raw_core_size=0,
            reason="empty_placement_or_ports",
        )

    port_owner_error = _d2_port_owner_validation_error(
        placement_solution=placement_solution,
        port_specs=port_specs,
    )
    if port_owner_error:
        return D2SeparationResult(
            cut_added=False, d2_status="ERROR", d2_wall_s=0.0,
            d2_total_vars=0, d2_constraints=0, raw_core_size=0,
            reason=port_owner_error,
        )

    occupied = _placement_to_occupied(placement_solution, facility_pools)
    try:
        precheck_status, precheck_summary = _d2_precheck_status_for_cut_context(
            occupied=occupied,
            port_specs=port_specs,
        )
    except Exception as exc:
        return D2SeparationResult(
            cut_added=False,
            d2_status="ERROR",
            d2_wall_s=time.perf_counter() - t_start,
            d2_total_vars=0,
            d2_constraints=0,
            raw_core_size=0,
            reason=f"routing_precheck_error: {type(exc).__name__}",
        )

    if precheck_status not in {"front_blocked", "relaxed_disconnected"}:
        return D2SeparationResult(
            cut_added=False,
            d2_status="MODEL_INVALID",
            d2_wall_s=time.perf_counter() - t_start,
            d2_total_vars=0,
            d2_constraints=0,
            raw_core_size=0,
            cut_metadata={
                "routing_precheck_status": precheck_status,
                "routing_precheck_domain_stats": dict(
                    precheck_summary.get("domain_stats", {})
                ),
            },
            reason=f"routing_precheck_{precheck_status}_not_certified_for_d2_cut",
        )

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
    #
    # D2 的 occupied grid 和所有当前 terminal helper literals 都是 proof context.
    # UNSAT core 只返回一部分 terminal assumptions; 直接按 raw_core 加 cut 会把
    # “当前障碍/当前其它 terminal 下不可行” 升级成 “这些 core poses 本身
    # 不可行”. 这里把所有 port owners + occupancy contributors 纳入 conflict，
    # 只会弱化 cut，但让 cut 的生效范围不超过 D2 实际证明范围。
    conflict_set = _build_d2_supported_conflict_set(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        assumptions=assumptions,
        raw_core=raw_core,
    )
    cut_metadata = _build_d2_cut_metadata(d2_result=result, raw_core=raw_core)
    cut_metadata["routing_precheck_status"] = precheck_status
    cut_metadata["routing_precheck_domain_stats"] = dict(
        precheck_summary.get("domain_stats", {})
    )
    cut_metadata["support_conflict_size"] = len(conflict_set)
    cut_metadata["support_owners"] = sorted(conflict_set.keys())

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

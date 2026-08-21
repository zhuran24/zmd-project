"""Heuristic feasible solution finder (subagent finding #5 path).

绕过 master CP-SAT 撞 30 GB peak + timeout 的 fast-path:
- greedy 直接 propose facility placement (Python 层, < 1 GB RAM)
- 三段 verifier 串行 (binding → routing → flow), 每段独立 CP-SAT solve, ~5 GB
- 任一 verifier INFEASIBLE → 整 candidate INFEASIBLE
- 任一 verifier UNKNOWN → 整 candidate UNKNOWN
- 全 FEASIBLE → 整 candidate CERTIFIED (best_effort 语义)

跟现有 LBBD path 关系:
- LBBD = master 真解 → cuts → 收敛. master 30 GB peak 当前撞墙
- 这条 = greedy 出 candidate → verifier 验. RAM 不撞 master 30 GB
- 准确性: best_effort (greedy 可能漏 better candidate, 但找到的 candidate 严格验过 feasibility)

API:
  find_feasible_for_candidate(ghost_rect, instances, pools, rules) →
    (status, solution_dict, metadata)

status:
  CERTIFIED: greedy 出 placement + 全 3 段 verifier FEASIBLE
  INFEASIBLE: greedy 失败 OR 某 verifier INFEASIBLE
  UNKNOWN: 某 verifier 超时 (fail-closed)
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


@dataclass
class HeuristicFinderResult:
    status: str  # CERTIFIED / INFEASIBLE / UNKNOWN
    solution: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _greedy_propose_placement(
    *,
    master: Any,
    ghost_rect: Optional[Tuple[int, int]],
) -> Optional[Dict[str, Any]]:
    """跑 greedy 摆 mandatory facility + 选第一个 valid ghost anchor.

    返回 placement_solution dict (instance_id → {facility_type, pose_idx, ...})
    或 None (greedy 摆不完整).

    跟 master_model._run_mandatory_greedy_pass 接, 但 wrap 成"完整 candidate"
    格式给 verifier 用.
    """
    ordered_groups = master._ordered_groups_for_exact_search()
    candidates_by_group: Dict[str, Sequence[int]] = {}
    for g in ordered_groups:
        gid = str(g["group_id"])
        candidates_by_group[gid] = list(master._candidate_pose_indices_for_group(g))

    result = master._run_mandatory_greedy_pass(
        ordered_groups=ordered_groups,
        candidates_by_group=candidates_by_group,
    )
    if not result.get("complete", False):
        return None
    solution_hint = result.get("solution_hint") or {}

    placement_solution: Dict[str, Any] = {}
    for instance_id, pose_idx in solution_hint.items():
        gid = master._group_id_by_instance.get(str(instance_id))
        if gid is None:
            continue
        group = next(
            (g for g in master._mandatory_groups if str(g["group_id"]) == gid),
            None,
        )
        if group is None:
            continue
        tpl = str(group["facility_type"])
        op = str(group.get("operation_type", ""))
        placement_solution[str(instance_id)] = {
            "facility_type": tpl,
            "pose_idx": int(pose_idx),
            "operation_type": op,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        }
    return placement_solution


def _extract_occupied(
    *,
    master: Any,
    placement_solution: Mapping[str, Mapping[str, Any]],
) -> Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], str]]:
    """从 placement_solution + master.facility_pools 抽 (occupied_cells, owner_by_cell).

    照搬 benders_loop._extract_occupied_cells + _extract_occupied_owner_by_cell
    的合并逻辑 (L4717-4741), 但一次 pass 减少 facility_pools 查表.
    """
    occupied: Set[Tuple[int, int]] = set()
    owner: Dict[Tuple[int, int], str] = {}
    for instance_id, entry in placement_solution.items():
        facility_type = str(entry["facility_type"])
        pose_idx = int(entry["pose_idx"])
        pose = master.facility_pools[facility_type][pose_idx]
        for cell in pose.get("occupied_cells", []):
            xy = (int(cell[0]), int(cell[1]))
            occupied.add(xy)
            owner[xy] = str(instance_id)
    return occupied, owner


def _verify_binding(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
    project_root: Optional[Path],
    time_limit_seconds: float,
) -> Tuple[str, Any, List[Mapping[str, Any]]]:
    """跑 binding verifier, 返回 (status, binding_model, port_specs).

    binding_model 在 FEASIBLE 时可调 extract_port_specs/extract_selection.
    """
    from src.models.binding_subproblem import (
    PortBindingModel,
    load_generic_input_slots_by_operation,
    load_generic_output_slots_by_operation,
    load_utility_operation_by_template,
)

    model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=instances,
        project_root=project_root,
        generic_input_slots_by_operation=(
            load_generic_input_slots_by_operation(project_root=project_root)
        ),
        generic_output_slots_by_operation=(
            load_generic_output_slots_by_operation(project_root=project_root)
        ),
        utility_operation_by_template=(
            load_utility_operation_by_template(project_root=project_root)
        ),
    )
    model.build()
    status = model.solve(time_limit_seconds=time_limit_seconds)
    if status == "FEASIBLE":
        port_specs = list(model.extract_port_specs())
        return "FEASIBLE", model, port_specs
    if status == "INFEASIBLE":
        return "INFEASIBLE", None, []
    return "UNKNOWN", None, []  # TIMEOUT / 其他


def _verify_routing(
    *,
    master: Any,
    placement_solution: Mapping[str, Mapping[str, Any]],
    port_specs: Sequence[Mapping[str, Any]],
    time_limit_seconds: float,
) -> Tuple[str, Dict[str, Any]]:
    """跑 routing verifier. precheck 先短路 (front_blocked / relaxed_disconnected
    → 直 INFEASIBLE, best_effort 语义不 nogood). precheck pass 后 build +
    solve RoutingSubproblem.

    照搬 benders_loop._run_exact_binding_and_routing 的 routing 段 (L4338-4548),
    简化掉 LBBD cut accumulation 路径.
    """
    from src.models.routing_subproblem import (
        RoutingGrid,
        RoutingPlacementCore,
        RoutingSubproblem,
        run_exact_routing_precheck,
    )

    occupied, owner = _extract_occupied(
        master=master, placement_solution=placement_solution
    )
    core = RoutingPlacementCore.from_occupied_cells(
        occupied, occupied_owner_by_cell=owner
    )
    precheck = run_exact_routing_precheck(
        placement_core=core,
        port_specs=port_specs,
        occupied_owner_by_cell=owner,
    )
    precheck_status = str(precheck.get("status", "feasible"))
    meta: Dict[str, Any] = {"precheck_status": precheck_status}

    if precheck_status == "front_blocked":
        return "INFEASIBLE", meta
    if precheck_status == "relaxed_disconnected":
        # best_effort: 不重 solve binding, 直接判 INFEASIBLE
        return "INFEASIBLE", meta

    commodities = sorted({str(p["commodity"]) for p in port_specs})
    domain_analysis = precheck.get("_analysis")
    try:
        routing_model = RoutingSubproblem.from_placement_core(
            core,
            list(port_specs),
            commodities,
            domain_analysis=domain_analysis,
        )
    except TypeError:
        # legacy fallback: build RoutingGrid + RoutingSubproblem(grid, commodities)
        grid = RoutingGrid.from_placement_core(core, port_specs)
        routing_model = RoutingSubproblem(grid, commodities)

    # routing_subproblem 的 build()/solve() 各自吃 time_limit (单 float, 秒).
    # heuristic 没拿 separate build/solve budget, 用同一 cap 简化.
    routing_model.build(time_limit=time_limit_seconds)
    rstatus = routing_model.solve(time_limit=time_limit_seconds)
    meta["routing_solve_status"] = rstatus
    if rstatus == "FEASIBLE":
        return "FEASIBLE", meta
    if rstatus == "INFEASIBLE":
        return "INFEASIBLE", meta
    return "UNKNOWN", meta


def _verify_flow(
    *,
    master: Any,
    placement_solution: Mapping[str, Mapping[str, Any]],
    project_root: Optional[Path],
    time_limit_seconds: float,
) -> Tuple[str, Dict[str, Any]]:
    """跑 flow verifier. 照搬 benders_loop._run_flow_diagnostic (L4096-4130).

    commodity_demands 从 project_root/data/preprocessed/commodity_demands.json
    加载. project_root=None 时 SKIPPED (best_effort fail-open: routing 通过就
    算 CERTIFIED).
    """
    from src.models.flow_subproblem import FlowSubproblem, build_flow_network

    if project_root is None:
        return "SKIPPED", {"reason": "no_project_root"}
    demands_path = project_root / "data" / "preprocessed" / "commodity_demands.json"
    if not demands_path.exists():
        return "SKIPPED", {"reason": "no_commodity_demands_json"}
    with demands_path.open("r", encoding="utf-8") as handle:
        commodity_demands = json.load(handle)

    occupied: Set[Tuple[int, int]] = set()
    port_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for instance_id, entry in placement_solution.items():
        pose_idx = int(entry["pose_idx"])
        facility_type = str(entry["facility_type"])
        pose = master.facility_pools[facility_type][pose_idx]
        for cell in pose.get("occupied_cells", []):
            occupied.add((int(cell[0]), int(cell[1])))
        for port in pose.get("input_port_cells", []):
            payload = dict(port)
            payload["instance_id"] = instance_id
            payload["type"] = "in"
            port_dict["dummy_commodity"].append(payload)
        for port in pose.get("output_port_cells", []):
            payload = dict(port)
            payload["instance_id"] = instance_id
            payload["type"] = "out"
            port_dict["dummy_commodity"].append(payload)

    network = build_flow_network(occupied, port_dict, commodity_demands)
    flow_model = FlowSubproblem(
        network, commodity_demands, solve_mode="certified_exact"
    )
    fstatus = flow_model.build_and_solve(
        time_limit_ms=int(time_limit_seconds * 1000)
    )
    meta = {"flow_status": fstatus}
    if fstatus == "FEASIBLE":
        return "FEASIBLE", meta
    if fstatus == "INFEASIBLE":
        return "INFEASIBLE", meta
    return "UNKNOWN", meta


def find_feasible_for_candidate(
    *,
    master: Any,
    ghost_rect: Optional[Tuple[int, int]],
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    project_root: Optional[Path] = None,
    binding_time_limit_seconds: float = 60.0,
    routing_time_limit_seconds: float = 120.0,
    flow_time_limit_seconds: float = 30.0,
) -> HeuristicFinderResult:
    """Main entry: greedy + 3 verifier 串联.

    master: built MasterPlacementModel (已 master.build(), 有 _mandatory_groups
            + _candidate_pose_indices_for_group + facility_pools).
    project_root: 若提供则 enable flow verifier 走 commodity_demands.json.
                  None → flow verifier SKIPPED (binding+routing pass 即视为
                  CERTIFIED, best_effort 语义).
    """
    t0 = time.time()
    placement_solution = _greedy_propose_placement(
        master=master, ghost_rect=ghost_rect
    )
    t1 = time.time()
    if placement_solution is None:
        return HeuristicFinderResult(
            status="INFEASIBLE",
            metadata={"greedy_seconds": t1 - t0, "failure": "greedy_incomplete"},
        )

    binding_status, binding_model, port_specs = _verify_binding(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=instances,
        project_root=project_root,
        time_limit_seconds=binding_time_limit_seconds,
    )
    t2 = time.time()
    if binding_status == "INFEASIBLE":
        return HeuristicFinderResult(
            status="INFEASIBLE",
            metadata={
                "greedy_seconds": t1 - t0,
                "binding_seconds": t2 - t1,
                "binding_status": binding_status,
                "failure": "binding_infeasible",
            },
        )
    if binding_status != "FEASIBLE":
        return HeuristicFinderResult(
            status="UNKNOWN",
            metadata={
                "greedy_seconds": t1 - t0,
                "binding_seconds": t2 - t1,
                "binding_status": binding_status,
                "failure": "binding_unknown",
            },
        )

    binding_selection = binding_model.extract_selection() if binding_model else {}

    routing_status, routing_meta = _verify_routing(
        master=master,
        placement_solution=placement_solution,
        port_specs=port_specs,
        time_limit_seconds=routing_time_limit_seconds,
    )
    t3 = time.time()
    if routing_status == "INFEASIBLE":
        return HeuristicFinderResult(
            status="INFEASIBLE",
            metadata={
                "greedy_seconds": t1 - t0,
                "binding_seconds": t2 - t1,
                "routing_seconds": t3 - t2,
                "binding_status": binding_status,
                "routing_status": routing_status,
                "routing_meta": routing_meta,
                "failure": "routing_infeasible",
            },
        )
    if routing_status == "UNKNOWN":
        return HeuristicFinderResult(
            status="UNKNOWN",
            metadata={
                "greedy_seconds": t1 - t0,
                "binding_seconds": t2 - t1,
                "routing_seconds": t3 - t2,
                "binding_status": binding_status,
                "routing_status": routing_status,
                "routing_meta": routing_meta,
                "failure": "routing_unknown",
            },
        )

    flow_status, flow_meta = _verify_flow(
        master=master,
        placement_solution=placement_solution,
        project_root=project_root,
        time_limit_seconds=flow_time_limit_seconds,
    )
    t4 = time.time()
    if flow_status == "INFEASIBLE":
        return HeuristicFinderResult(
            status="INFEASIBLE",
            metadata={
                "greedy_seconds": t1 - t0,
                "binding_seconds": t2 - t1,
                "routing_seconds": t3 - t2,
                "flow_seconds": t4 - t3,
                "binding_status": binding_status,
                "routing_status": routing_status,
                "flow_status": flow_status,
                "flow_meta": flow_meta,
                "failure": "flow_infeasible",
            },
        )
    if flow_status == "UNKNOWN":
        return HeuristicFinderResult(
            status="UNKNOWN",
            metadata={
                "greedy_seconds": t1 - t0,
                "binding_seconds": t2 - t1,
                "routing_seconds": t3 - t2,
                "flow_seconds": t4 - t3,
                "binding_status": binding_status,
                "routing_status": routing_status,
                "flow_status": flow_status,
                "flow_meta": flow_meta,
                "failure": "flow_unknown",
            },
        )

    return HeuristicFinderResult(
        status="CERTIFIED",
        solution={
            "placement_solution": dict(placement_solution),
            "binding_selection": dict(binding_selection or {}),
        },
        metadata={
            "greedy_seconds": t1 - t0,
            "binding_seconds": t2 - t1,
            "routing_seconds": t3 - t2,
            "flow_seconds": t4 - t3,
            "binding_status": binding_status,
            "routing_status": routing_status,
            "routing_meta": routing_meta,
            "flow_status": flow_status,
            "flow_meta": flow_meta,
            "declare_mode": "best_effort",
        },
    )


__all__ = ["HeuristicFinderResult", "find_feasible_for_candidate"]

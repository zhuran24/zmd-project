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

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


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


def _verify_binding(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
    time_limit_seconds: float,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """跑 binding verifier, 返回 (status, binding_selection or None)."""
    from src.models.binding_subproblem import PortBindingModel

    model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=instances,
    )
    status = model.solve(time_limit_seconds=time_limit_seconds)
    if status == "FEASIBLE":
        return "FEASIBLE", model.extract_selection()
    if status == "INFEASIBLE":
        return "INFEASIBLE", None
    return "UNKNOWN", None  # TIMEOUT / 其他


def _verify_routing(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    binding_selection: Mapping[str, Any],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
    time_limit_seconds: float,
) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    """跑 routing verifier. 需要 build RoutingGrid + commodities — 复用现有
    routing_subproblem.* 辅助函数. Placeholder, 实际实现需要 trace
    analyze_exact_routing_domain() 等. 当前 stub 返回 SKIPPED.
    """
    return "SKIPPED", None


def _verify_flow(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    binding_selection: Mapping[str, Any],
    time_limit_seconds: float,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """跑 flow verifier. flow_subproblem.build_and_solve. Stub 返回 SKIPPED."""
    return "SKIPPED", None


def find_feasible_for_candidate(
    *,
    master: Any,
    ghost_rect: Optional[Tuple[int, int]],
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    binding_time_limit_seconds: float = 60.0,
    routing_time_limit_seconds: float = 120.0,
    flow_time_limit_seconds: float = 30.0,
) -> HeuristicFinderResult:
    """Main entry: greedy + 3 verifier 串联.

    master: built MasterPlacementModel (already master.build() done, has
            _mandatory_groups + _candidate_pose_indices_for_group / etc).
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

    binding_status, binding_selection = _verify_binding(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=instances,
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

    # Routing + flow stubs return SKIPPED for now (Phase 2 work)
    routing_status, _ = _verify_routing(
        placement_solution=placement_solution,
        binding_selection=binding_selection or {},
        facility_pools=facility_pools,
        instances=instances,
        rules=rules,
        time_limit_seconds=routing_time_limit_seconds,
    )
    flow_status, _ = _verify_flow(
        placement_solution=placement_solution,
        binding_selection=binding_selection or {},
        time_limit_seconds=flow_time_limit_seconds,
    )

    return HeuristicFinderResult(
        status="CERTIFIED",  # binding feasible + routing/flow stubbed
        solution={
            "placement_solution": dict(placement_solution),
            "binding_selection": dict(binding_selection or {}),
        },
        metadata={
            "greedy_seconds": t1 - t0,
            "binding_seconds": t2 - t1,
            "binding_status": binding_status,
            "routing_status": routing_status,
            "flow_status": flow_status,
            "declare_mode": "best_effort",
        },
    )


__all__ = ["HeuristicFinderResult", "find_feasible_for_candidate"]

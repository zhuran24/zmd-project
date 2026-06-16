"""Phase 6 第 2 条: routing front-blocked deletion-based core minimizer.

输入: full master layout (Dict[instance_id, {pose_idx, facility_type, ...}])
输出: minimal instance subset 使得 routing precheck 仍 front_blocked.

Oracle: cheap front-blocked check (不调 routing CP-SAT, 只算 occupied + port front
overlap). O(N port) per call, milliseconds.

算法 (类似 L16 scripts/phase3_core_minimizer.py):
  S = list(all_instance_ids)
  for instance_id in deletion_order(S):
    trial = S - {instance_id}
    if oracle_still_front_blocked(trial):
      S = trial
  return S as deletion-minimal core

Cut: instance-level placement_local_nogood — sum(x_var for I in core) <= |core| - 1.
比 Phase 5 cell-level cut 切得 tighter (一次切整 core), 比 routine instance-level
nogood (Phase 3/4 baseline) 切得 minimal (core 是 minimal, 不是 full layout).

预算: max_oracle_calls 默认 64, max_seconds 默认 30.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1),
    "S": (0, -1),
    "E": (1, 0),
    "W": (-1, 0),
}

RoutingVisiblePortKey = Tuple[int, int, str, str]


def build_routing_visible_port_keys_by_instance(
    port_specs: Sequence[Mapping[str, Any]],
) -> Dict[str, Set[RoutingVisiblePortKey]]:
    """Normalize selected routing-visible binding port specs for the oracle.

    The deletion-core oracle is deliberately cheaper than routing precheck, but
    it must consume the same *visible terminal* set.  In particular, wireless
    final producer outputs are absent from ``extract_port_specs()`` and must not
    be resurrected from raw pose geometry here.
    """

    result: Dict[str, Set[RoutingVisiblePortKey]] = {}
    for spec in port_specs:
        instance_id = str(spec.get("instance_id", ""))
        if not instance_id:
            continue
        port_type = str(spec.get("type", ""))
        if port_type not in {"in", "out"}:
            continue
        result.setdefault(instance_id, set()).add(
            (
                int(spec["x"]),
                int(spec["y"]),
                str(spec["dir"]),
                port_type,
            )
        )
    return result


@dataclass
class RoutingCoreResult:
    instance_ids: Tuple[str, ...]  # minimal core (instance_id 顺序确定)
    pose_idx_by_id: Dict[str, int]  # core 内 instance → pose_idx (cut 需要)
    oracle_calls: int
    oracle_seconds_total: float
    full_layout_size: int
    deletion_attempts: int
    abort_reason: str  # "completed" | "max_oracle_calls" | "max_seconds" | "fallback_no_deletion"


def _oracle_front_blocked(
    layout_subset: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    grid_w: int,
    grid_h: int,
    *,
    routing_visible_port_keys_by_instance: Optional[
        Mapping[str, Set[RoutingVisiblePortKey]]
    ] = None,
) -> bool:
    """Cheap oracle: 给 layout subset, 任一 instance 的某 port front 被另一 instance
    占 → return True (仍 front_blocked).

    跟 routing_subproblem._analyze_routing_domain (line 280+) 的 precheck 逻辑等价
    简化版 (这里 not 用 belt routing CP-SAT).
    """
    # 算 occupied_cells set
    occupied: Set[Tuple[int, int]] = set()
    occupier_of: Dict[Tuple[int, int], str] = {}
    for iid, entry in layout_subset.items():
        tpl = str(entry.get("facility_type", ""))
        pose_idx = int(entry.get("pose_idx", -1))
        if pose_idx < 0 or not tpl:
            continue
        pool = facility_pools.get(tpl, [])
        if pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for cell in pose.get("occupied_cells", []) or []:
            cell_xy = (int(cell[0]), int(cell[1]))
            occupied.add(cell_xy)
            occupier_of[cell_xy] = str(iid)

    # 对每 instance 每 port 检 front_cell 是否被另一 instance 占
    for iid, entry in layout_subset.items():
        tpl = str(entry.get("facility_type", ""))
        pose_idx = int(entry.get("pose_idx", -1))
        if pose_idx < 0 or not tpl:
            continue
        pool = facility_pools.get(tpl, [])
        if pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for port_list_key, port_type in (("input_port_cells", "in"), ("output_port_cells", "out")):
            visible_keys = (
                None
                if routing_visible_port_keys_by_instance is None
                else set(routing_visible_port_keys_by_instance.get(str(iid), set()))
            )
            for port in pose.get(port_list_key, []) or []:
                px = int(port.get("x", 0))
                py = int(port.get("y", 0))
                direction = str(port.get("dir", ""))
                if visible_keys is not None and (px, py, direction, port_type) not in visible_keys:
                    continue
                dx, dy = _DIR_DELTA.get(direction, (0, 0))
                fx, fy = px + dx, py + dy
                if not (0 <= fx < grid_w and 0 <= fy < grid_h):
                    return True  # 出 grid 永远 blocked
                front_cell = (fx, fy)
                if front_cell in occupied and occupier_of.get(front_cell) != iid:
                    return True
    return False


def _deletion_order(
    instance_ids: Sequence[str],
    blocker_ids: Set[str],
) -> List[str]:
    """优先删 blocker (occupier of someone's front cell): 它们才是真 root cause.
    Non-blocker 删了 oracle 仍 blocked, 浪费 oracle call.

    blocker_ids 来自 routing 反馈 (placement_level_conflict_set 里的 instances).
    """
    blockers = [iid for iid in instance_ids if iid in blocker_ids]
    others = [iid for iid in instance_ids if iid not in blocker_ids]
    return sorted(blockers) + sorted(others)


def minimize_routing_front_blocked_core(
    *,
    full_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    grid_w: int,
    grid_h: int,
    blocker_instance_ids: Set[str],  # 从 routing blocked_ports.placement_level_conflict_set 集
    routing_visible_port_keys_by_instance: Optional[
        Mapping[str, Set[RoutingVisiblePortKey]]
    ] = None,
    max_oracle_calls: int = 64,
    max_seconds: float = 30.0,
    verbose: bool = False,
) -> RoutingCoreResult:
    S: Set[str] = {str(k) for k in full_solution.keys()}
    full_layout_size = len(S)
    order = _deletion_order(list(S), blocker_instance_ids)

    start_time = time.perf_counter()
    oracle_calls = 0
    oracle_seconds_total = 0.0
    deletion_attempts = 0
    abort_reason = "completed"

    # Initial oracle check — confirm full layout indeed front_blocked.
    t_o0 = time.perf_counter()
    initial_blocked = _oracle_front_blocked(
        full_solution,
        facility_pools,
        grid_w,
        grid_h,
        routing_visible_port_keys_by_instance=routing_visible_port_keys_by_instance,
    )
    oracle_seconds_total += time.perf_counter() - t_o0
    oracle_calls += 1
    if not initial_blocked:
        return RoutingCoreResult(
            instance_ids=tuple(sorted(S)),
            pose_idx_by_id={str(k): int(v.get("pose_idx", -1)) for k, v in full_solution.items()},
            oracle_calls=oracle_calls,
            oracle_seconds_total=oracle_seconds_total,
            full_layout_size=full_layout_size,
            deletion_attempts=0,
            abort_reason="fallback_no_deletion",  # full layout not blocked — caller mistake
        )

    for iid in order:
        if oracle_calls >= max_oracle_calls:
            abort_reason = "max_oracle_calls"
            break
        if time.perf_counter() - start_time >= max_seconds:
            abort_reason = "max_seconds"
            break
        if iid not in S:
            continue
        deletion_attempts += 1
        trial = S - {iid}
        sub_layout = {k: full_solution[k] for k in trial}
        t_o = time.perf_counter()
        still_blocked = _oracle_front_blocked(
            sub_layout,
            facility_pools,
            grid_w,
            grid_h,
            routing_visible_port_keys_by_instance=routing_visible_port_keys_by_instance,
        )
        oracle_seconds_total += time.perf_counter() - t_o
        oracle_calls += 1
        if still_blocked:
            S = trial
            if verbose:
                print(f"  delete {iid} → core size {len(S)}")

    pose_idx_by_id = {
        iid: int(full_solution[iid].get("pose_idx", -1))
        for iid in S
        if iid in full_solution
    }
    return RoutingCoreResult(
        instance_ids=tuple(sorted(S)),
        pose_idx_by_id=pose_idx_by_id,
        oracle_calls=oracle_calls,
        oracle_seconds_total=oracle_seconds_total,
        full_layout_size=full_layout_size,
        deletion_attempts=deletion_attempts,
        abort_reason=abort_reason,
    )

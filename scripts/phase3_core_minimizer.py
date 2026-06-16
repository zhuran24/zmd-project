"""Phase 3 deletion-based power-infeasible core minimizer.

输入: master 的 non-power solution + ghost cells + pools + powered_templates +
power_coverers. 该 layout 已知 PowerPlacementSubproblem 返回 INFEASIBLE.

算法 (GPT v11 计划书 linear_deletion_v1):
  S = list(all_non_pole_instance_ids)
  for instance_id in deletion_order(S):
    trial = S - {instance_id}
    sub = PowerPlacementSubproblem(restrict(solution, trial))
    if sub.solve() == INFEASIBLE:
      S = trial
  return S as minimized core

Exactness: 每次删除后重新证明 subset INFEASIBLE. 返回的 S 是 deletion-minimal,
即 "任何 layout 包含 S 都 INFEASIBLE", cut S 是 exact-safe.

预算控制:
  max_oracle_calls (默认 32)
  max_seconds (默认 120)
  oracle_time_limit (默认 10)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from src.models.power_placement_subproblem import PowerPlacementSubproblem


@dataclass
class CoreResult:
    instance_ids: Tuple[str, ...]
    oracle_calls: int
    oracle_seconds_total: float
    full_layout_size: int
    deletion_attempts: int
    abort_reason: str  # "completed" | "max_oracle_calls" | "max_seconds" | "fallback_no_deletion"


def _deletion_order(
    instance_ids: Sequence[str],
    powered_instance_ids: Set[str],
) -> List[str]:
    """优先试删 powered (它们才是 power coverage 的真 blocker).

    实测 (Phase 3 trial3, 2026-05-17): 先删 non-powered (boundary_port 等) 是 误判.
    Non-powered 不需要 cover, 删它们不改变 powered 的 coverer 可用性, subproblem
    仍 INFEASIBLE → minimizer 浪费 oracle call 删 non-powered, 32 个 budget 用完都
    没碰 powered. 真正能 shrink core 的是删 critical powered instance.

    现 order: 先 powered (字典序), 再 non-powered (字典序). max_oracle_calls 应
    ≥ powered 数量 (~220).
    """
    powered = [iid for iid in instance_ids if iid in powered_instance_ids]
    non_powered = [iid for iid in instance_ids if iid not in powered_instance_ids]
    return sorted(powered) + sorted(non_powered)


def restrict_solution(
    solution: Mapping[str, Mapping[str, Any]],
    keep_ids: Set[str],
) -> Dict[str, Dict[str, Any]]:
    return {str(k): dict(v) for k, v in solution.items() if str(k) in keep_ids}


def minimize_power_infeasible_core_linear_deletion(
    *,
    full_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    powered_templates: Set[str],
    power_coverers_by_template_pose: Mapping[str, Mapping[int, Sequence[int]]],
    ghost_cells: Set[Tuple[int, int]],
    max_oracle_calls: int = 32,
    max_seconds: float = 120.0,
    oracle_time_limit_s: float = 10.0,
    verbose: bool = False,
) -> CoreResult:
    # 1. 准备 powered_instance_ids 集合 (用于 deletion_order)
    powered_ids: Set[str] = set()
    for iid, entry in full_solution.items():
        tpl = str(entry.get("facility_type"))
        if tpl in powered_templates and tpl != "power_pole":
            powered_ids.add(str(iid))

    # 2. 初始 S = 全 non-pole instance_id
    S = sorted(str(k) for k in full_solution.keys())
    full_layout_size = len(S)
    if verbose:
        print(f"[minimize] start S size={full_layout_size} powered={len(powered_ids)}")

    order = _deletion_order(S, powered_ids)
    start_time = time.perf_counter()
    oracle_calls = 0
    oracle_seconds_total = 0.0
    deletion_attempts = 0
    abort_reason = "completed"

    for iid in order:
        if iid not in set(S):
            continue  # 已被前面删了

        if oracle_calls >= max_oracle_calls:
            abort_reason = "max_oracle_calls"
            break
        if time.perf_counter() - start_time >= max_seconds:
            abort_reason = "max_seconds"
            break

        trial = set(S) - {iid}
        trial_solution = restrict_solution(full_solution, trial)
        deletion_attempts += 1

        sub = PowerPlacementSubproblem(
            master_solution=trial_solution,
            facility_pools=facility_pools,
            powered_templates=powered_templates,
            power_coverers_by_template_pose=power_coverers_by_template_pose,
            ghost_cells=ghost_cells,
        )
        sub.build()
        t_solve = time.perf_counter()
        result = sub.solve(time_limit_seconds=oracle_time_limit_s)
        elapsed = time.perf_counter() - t_solve
        oracle_seconds_total += elapsed
        oracle_calls += 1

        if result.status == "INFEASIBLE":
            S = sorted(trial)
            if verbose:
                print(f"  [{oracle_calls}] del {iid}: INFEASIBLE, S size={len(S)}, +{elapsed:.2f}s")
        elif result.status == "FEASIBLE":
            # 删了 iid 后 layout feasible → iid 是 critical, 必须留
            if verbose:
                print(f"  [{oracle_calls}] del {iid}: FEASIBLE (keep), S size={len(S)}, +{elapsed:.2f}s")
        else:  # TIMEOUT
            # 不确定, 保守留
            if verbose:
                print(f"  [{oracle_calls}] del {iid}: TIMEOUT (keep conservatively), +{elapsed:.2f}s")

    if deletion_attempts == 0:
        abort_reason = "fallback_no_deletion"

    return CoreResult(
        instance_ids=tuple(S),
        oracle_calls=oracle_calls,
        oracle_seconds_total=oracle_seconds_total,
        full_layout_size=full_layout_size,
        deletion_attempts=deletion_attempts,
        abort_reason=abort_reason,
    )


if __name__ == "__main__":
    print("This is a module. Import minimize_power_infeasible_core_linear_deletion.")

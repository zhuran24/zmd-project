"""HiGHS-backed certified candidate evaluator (Phase 3 production integration).

包装 build_highs_minimum_model + solve 成跟 OR-Tools run_benders_for_ghost_rect
等价的接口, 给 outer_search / Benders campaign 调用.

跟 OR-Tools 路径关系:
- env `EXACT_USE_HIGHS_MASTER` 控制 outer_search 是否选 HiGHS 路径
- default off → 保留 OR-Tools 默认行为
- on → 用 HighsCandidateEvaluator 评估每个 candidate

注意:
- 这个 evaluator 是 **monolithic** master (HiGHS LP-MIP), 不走 LBBD Benders
  loop. 单一 model 完整解, 没 master/subproblem 拆分.
- 对小 candidate (70x6 等) 解得快; 对大 candidate (42x32) 估计也比 OR-Tools
  LBBD 慢 (LP relaxation 弱), 但 RAM 不撞墙.
- proof completeness 由 model 等价性保证 (跟 cp_sat_minimum_model 在小 case 上
  status 等价已验). 加 power_coverage 后须重验等价性.

API:
  evaluator = HighsCandidateEvaluator(project_root=..., include_power_coverage=True)
  status, solution = evaluator.evaluate(ghost_rect=(70, 6), time_limit_seconds=600)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.models.highs_master_model import build_highs_minimum_model


@dataclass
class HighsCandidateEvaluator:
    """Build + solve HiGHS model for a single ghost-rect candidate."""

    project_root: Optional[Path] = None
    include_power_coverage: bool = False
    instances: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]] = field(
        default_factory=dict
    )
    rules: Mapping[str, Any] = field(default_factory=dict)
    _loaded: bool = False

    @classmethod
    def from_in_memory(
        cls,
        *,
        instances: Sequence[Mapping[str, Any]],
        facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
        rules: Mapping[str, Any],
        include_power_coverage: bool = False,
    ) -> "HighsCandidateEvaluator":
        """In-memory data 注入, 跳过 project_root file loading (unit test 用)."""
        return cls(
            project_root=None,
            include_power_coverage=include_power_coverage,
            instances=tuple(instances),
            facility_pools=facility_pools,
            rules=rules,
            _loaded=True,
        )

    def _load_project_data(self) -> None:
        if self._loaded:
            return
        if self.project_root is None:
            raise ValueError(
                "HighsCandidateEvaluator: 既无 project_root 又未通过 "
                "from_in_memory 注入 instances/pools/rules"
            )
        root = Path(self.project_root)
        with open(root / "data/preprocessed/mandatory_exact_instances.json") as f:
            payload = json.load(f)
        instances = (
            payload.get("instances", payload)
            if isinstance(payload, dict)
            else payload
        )
        with open(root / "data/preprocessed/candidate_placements.json") as f:
            pools_payload = json.load(f)
        facility_pools = pools_payload.get("facility_pools", pools_payload)
        with open(root / "rules/canonical_rules.json") as f:
            rules = json.load(f)
        self.instances = tuple(instances)
        self.facility_pools = facility_pools
        self.rules = rules
        self._loaded = True

    def evaluate(
        self,
        *,
        ghost_rect: Tuple[int, int],
        time_limit_seconds: Optional[float] = 600.0,
    ) -> Tuple[str, Optional[Dict[str, Any]], Dict[str, Any]]:
        """Build + solve HiGHS model for one ghost-rect candidate.

        Returns (status_str, solution_or_None, metadata_dict).

        status_str ∈ {OPTIMAL, INFEASIBLE, UNKNOWN, UNBOUNDED}.
        - OPTIMAL: candidate feasible (CERTIFIED in OR-Tools 语义)
        - INFEASIBLE: candidate infeasible (proven)
        - UNKNOWN: time limit / solver internal limit hit, fail-closed
        - UNBOUNDED: should not happen for feasibility-only model
        """
        self._load_project_data()

        import time
        import resource

        t0 = time.time()
        model = build_highs_minimum_model(
            self.instances,
            self.facility_pools,
            self.rules,
            ghost_rect=ghost_rect,
            include_power_coverage=self.include_power_coverage,
        )
        t1 = time.time()
        build_seconds = t1 - t0

        status, solution = model.solve(time_limit_seconds=time_limit_seconds)
        t2 = time.time()
        solve_seconds = t2 - t1

        peak_rss_gb = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        )
        metadata = {
            "build_seconds": build_seconds,
            "solve_seconds": solve_seconds,
            "peak_rss_gb": peak_rss_gb,
            "include_power_coverage": self.include_power_coverage,
            "build_stats": dict(model.build_stats),
        }
        return status, solution, metadata


__all__ = ["HighsCandidateEvaluator"]

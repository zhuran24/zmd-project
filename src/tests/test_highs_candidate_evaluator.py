"""HighsCandidateEvaluator integration test — Phase 3 重写组件.

用 in-memory micro data 验 evaluator API surface 正确, 不依赖 real project
files. Production evaluator (project_root path) 由 Phase 3 PoC script 验.
"""

from __future__ import annotations

from src.models.highs_candidate_evaluator import HighsCandidateEvaluator


def _minimal_5x5() -> dict:
    return {
        "globals": {"grid": {"width": 5, "height": 5}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }


def test_evaluator_in_memory_feasible() -> None:
    instances = [
        {"instance_id": "m1", "facility_type": "miner", "is_mandatory": True},
        {"instance_id": "m2", "facility_type": "miner", "is_mandatory": True},
    ]
    pools = {
        "miner": [
            {"pose_id": "p0", "anchor": {"x": 0, "y": 0}, "occupied_cells": [[0, 0]]},
            {"pose_id": "p1", "anchor": {"x": 4, "y": 4}, "occupied_cells": [[4, 4]]},
            {"pose_id": "p2", "anchor": {"x": 2, "y": 2}, "occupied_cells": [[2, 2]]},
        ]
    }
    evaluator = HighsCandidateEvaluator.from_in_memory(
        instances=instances,
        facility_pools=pools,
        rules=_minimal_5x5(),
        include_power_coverage=False,
    )
    status, solution, metadata = evaluator.evaluate(
        ghost_rect=(2, 2), time_limit_seconds=10.0
    )
    assert status == "OPTIMAL"
    assert solution is not None
    assert len(solution["selected_poses"]) == 2
    assert solution["ghost_anchor"] is not None
    assert metadata["include_power_coverage"] is False
    assert metadata["build_seconds"] > 0
    assert metadata["build_stats"]["mandatory_group_count"] == 2


def test_evaluator_in_memory_infeasible() -> None:
    instances = [
        {"instance_id": "m1", "facility_type": "miner", "is_mandatory": True},
        {"instance_id": "m2", "facility_type": "miner", "is_mandatory": True},
    ]
    pools = {
        "miner": [{"pose_id": "p0", "anchor": {"x": 2, "y": 2}, "occupied_cells": [[2, 2]]}]
    }
    evaluator = HighsCandidateEvaluator.from_in_memory(
        instances=instances,
        facility_pools=pools,
        rules=_minimal_5x5(),
    )
    status, solution, _ = evaluator.evaluate(
        ghost_rect=None, time_limit_seconds=5.0
    )
    assert status == "INFEASIBLE"
    assert solution is None


def test_evaluator_no_root_no_data_raises() -> None:
    import pytest
    evaluator = HighsCandidateEvaluator()
    with pytest.raises(ValueError, match="既无 project_root"):
        evaluator.evaluate(ghost_rect=(1, 1), time_limit_seconds=1.0)

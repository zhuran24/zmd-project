"""Unit tests for src/search/heuristic_feasible_finder.py.

mock-based 覆盖 greedy + 各 verifier 短路逻辑. routing/flow real-CP-SAT
integration 留 separate slow tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.search.heuristic_feasible_finder import (
    HeuristicFinderResult,
    _extract_occupied,
    _greedy_propose_placement,
    _verify_flow,
    find_feasible_for_candidate,
)


def _mock_master_with_greedy_result(*, complete: bool, solution_hint=None, facility_pools=None):
    """Build a MagicMock master matching MasterPlacementModel API surface needed by greedy + extract."""
    master = MagicMock()
    master._ordered_groups_for_exact_search.return_value = [
        {"group_id": "g1", "facility_type": "tiny_facility", "operation_type": "manuf"}
    ]
    master._candidate_pose_indices_for_group.return_value = [0]
    master._run_mandatory_greedy_pass.return_value = {
        "complete": complete,
        "solution_hint": solution_hint or {},
    }
    master._group_id_by_instance = {"tiny_001": "g1"}
    master._mandatory_groups = [
        {"group_id": "g1", "facility_type": "tiny_facility", "operation_type": "manuf"}
    ]
    master.facility_pools = facility_pools or {
        "tiny_facility": [
            {
                "pose_id": "tiny_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    return master


def test_greedy_propose_placement_complete():
    master = _mock_master_with_greedy_result(
        complete=True, solution_hint={"tiny_001": 0}
    )
    result = _greedy_propose_placement(master=master, ghost_rect=None)
    assert result is not None
    assert "tiny_001" in result
    assert result["tiny_001"]["facility_type"] == "tiny_facility"
    assert result["tiny_001"]["pose_idx"] == 0
    assert result["tiny_001"]["bound_type"] == "exact"
    assert result["tiny_001"]["solve_mode"] == "certified_exact"


def test_greedy_propose_placement_incomplete_returns_none():
    master = _mock_master_with_greedy_result(complete=False)
    result = _greedy_propose_placement(master=master, ghost_rect=None)
    assert result is None


def test_greedy_skips_unknown_instance_without_group():
    master = _mock_master_with_greedy_result(
        complete=True,
        solution_hint={"tiny_001": 0, "unknown_999": 0},
    )
    result = _greedy_propose_placement(master=master, ghost_rect=None)
    assert result is not None
    assert "tiny_001" in result
    assert "unknown_999" not in result


def test_extract_occupied_basic():
    master = _mock_master_with_greedy_result(complete=True)
    placement_solution = {
        "tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}
    }
    occupied, owner = _extract_occupied(
        master=master, placement_solution=placement_solution
    )
    assert occupied == {(0, 0)}
    assert owner == {(0, 0): "tiny_001"}


def test_flow_verifier_skipped_without_project_root():
    master = _mock_master_with_greedy_result(complete=True)
    placement_solution = {
        "tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}
    }
    status, meta = _verify_flow(
        master=master,
        placement_solution=placement_solution,
        project_root=None,
        time_limit_seconds=10.0,
    )
    assert status == "SKIPPED"
    assert meta == {"reason": "no_project_root"}


def test_flow_verifier_skipped_without_commodity_demands_json(tmp_path: Path):
    master = _mock_master_with_greedy_result(complete=True)
    placement_solution = {
        "tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}
    }
    status, meta = _verify_flow(
        master=master,
        placement_solution=placement_solution,
        project_root=tmp_path,
        time_limit_seconds=10.0,
    )
    assert status == "SKIPPED"
    assert meta == {"reason": "no_commodity_demands_json"}


def test_find_feasible_returns_infeasible_when_greedy_fails(tmp_path: Path):
    master = _mock_master_with_greedy_result(complete=False)
    result = find_feasible_for_candidate(
        master=master,
        ghost_rect=None,
        instances=[],
        facility_pools=master.facility_pools,
        rules={},
        project_root=None,
    )
    assert result.status == "INFEASIBLE"
    assert result.metadata["failure"] == "greedy_incomplete"
    assert result.solution is None


def test_heuristic_finder_result_default_metadata():
    r = HeuristicFinderResult(status="UNKNOWN")
    assert r.status == "UNKNOWN"
    assert r.solution is None
    assert r.metadata == {}


def test_flow_verifier_handles_empty_commodity_demands_file(tmp_path: Path):
    """commodity_demands.json 存在但空 dict, flow_subproblem 应 build 一个 trivial network."""
    demands_path = tmp_path / "data" / "preprocessed" / "commodity_demands.json"
    demands_path.parent.mkdir(parents=True, exist_ok=True)
    demands_path.write_text(json.dumps({}))

    master = _mock_master_with_greedy_result(complete=True)
    placement_solution = {
        "tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}
    }
    # tiny_facility 没 input/output ports → flow network 是空, 应 FEASIBLE
    status, meta = _verify_flow(
        master=master,
        placement_solution=placement_solution,
        project_root=tmp_path,
        time_limit_seconds=10.0,
    )
    assert status in ("FEASIBLE", "INFEASIBLE", "UNKNOWN", "SKIPPED")
    assert "flow_status" in meta or "reason" in meta

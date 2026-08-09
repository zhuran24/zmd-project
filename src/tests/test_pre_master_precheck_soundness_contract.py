"""Soundness contracts for certified pre-master INFEASIBLE skips."""

from __future__ import annotations

import copy

import src.search.benders_loop as benders_loop_module
import src.search.outer_search as outer_search_module
from src.models.cut_manager import RUN_STATUS_INFEASIBLE


def _boundary_precheck_outcome() -> dict:
    return {
        "triggered": True,
        "status": RUN_STATUS_INFEASIBLE,
        "proof_summary": {
            "master_status": RUN_STATUS_INFEASIBLE,
            "master_boundary_port_feasibility": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 2,
                "screen_pass_anchor_count": 0,
                "unsupported_anchor_count": 0,
                "max_packable_min": 17,
                "max_packable_max": 17,
                "first_infeasible_anchor_idx": 0,
                "first_infeasible_anchor_max_packable": 17,
            },
            "master_candidate_precheck": {
                "triggered": True,
                "precheck_reason": "boundary_port_all_anchors_infeasible",
                "master_solve_skipped": True,
                "supported": True,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 2,
                "screen_pass_anchor_count": 0,
                "max_packable_min": 17,
                "max_packable_max": 17,
                "first_infeasible_anchor_idx": 0,
                "first_infeasible_anchor_max_packable": 17,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            },
        },
    }


def _coordinate_precheck_outcome() -> dict:
    return {
        "triggered": True,
        "status": RUN_STATUS_INFEASIBLE,
        "proof_summary": {
            "master_status": RUN_STATUS_INFEASIBLE,
            "coordinate_validation_precheck": {
                "evaluated": True,
                "triggered": True,
                "skipped_due_to_anchor_limit": False,
                "considered_anchor_count": 2,
                "evaluated_anchor_count": 2,
                "infeasible_anchor_count": 2,
                "accepted_anchor_count": 0,
                "unknown_anchor_count": 0,
                "skipped_anchor_count": 0,
                "short_circuited_after_non_triggering_anchor": False,
                "status_counts": {"INFEASIBLE": 2},
                "rejected_anchors": [
                    {"anchor_idx": 10, "status": "INFEASIBLE"},
                    {"anchor_idx": 11, "status": "INFEASIBLE"},
                ],
                "non_triggering_anchors": [],
            },
            "master_candidate_precheck": {
                "triggered": True,
                "precheck_reason": "coordinate_validation_infeasible",
                "master_solve_skipped": True,
                "supported": True,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 2,
                "screen_pass_anchor_count": 0,
                "max_packable_min": None,
                "max_packable_max": None,
                "first_infeasible_anchor_idx": 10,
                "first_infeasible_anchor_max_packable": None,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            },
        },
    }


def test_pre_master_precheck_contract_accepts_complete_boundary_proof() -> None:
    outcome = _boundary_precheck_outcome()

    assert benders_loop_module.is_valid_pre_master_precheck_elimination(outcome)
    assert outer_search_module._is_valid_pre_master_precheck_elimination(outcome)


def test_pre_master_precheck_contract_rejects_unknown_reason_shell() -> None:
    outcome = _boundary_precheck_outcome()
    outcome["proof_summary"]["master_candidate_precheck"]["precheck_reason"] = (
        "just_trust_me_all_anchors_infeasible"
    )

    assert not benders_loop_module.is_valid_pre_master_precheck_elimination(outcome)
    assert not outer_search_module._is_valid_pre_master_precheck_elimination(outcome)


def test_pre_master_precheck_contract_rejects_boundary_count_mismatch() -> None:
    outcome = _boundary_precheck_outcome()
    outcome["proof_summary"]["master_boundary_port_feasibility"][
        "screened_infeasible_anchor_count"
    ] = 1

    assert not benders_loop_module.is_valid_pre_master_precheck_elimination(outcome)
    assert not outer_search_module._is_valid_pre_master_precheck_elimination(outcome)


def test_pre_master_precheck_contract_accepts_complete_coordinate_proof() -> None:
    outcome = _coordinate_precheck_outcome()

    assert benders_loop_module.is_valid_pre_master_precheck_elimination(outcome)
    assert outer_search_module._is_valid_pre_master_precheck_elimination(outcome)


def test_pre_master_precheck_contract_rejects_coordinate_unknown_anchor() -> None:
    outcome = _coordinate_precheck_outcome()
    outcome["proof_summary"]["coordinate_validation_precheck"]["unknown_anchor_count"] = 1
    outcome["proof_summary"]["coordinate_validation_precheck"]["status_counts"] = {
        "INFEASIBLE": 1,
        "UNKNOWN": 1,
    }

    assert not benders_loop_module.is_valid_pre_master_precheck_elimination(outcome)
    assert not outer_search_module._is_valid_pre_master_precheck_elimination(outcome)


def test_pre_master_precheck_contract_rejects_mutated_shallow_copy() -> None:
    outcome = _boundary_precheck_outcome()
    mutated = copy.deepcopy(outcome)
    del mutated["proof_summary"]["master_boundary_port_feasibility"]

    assert benders_loop_module.is_valid_pre_master_precheck_elimination(outcome)
    assert not benders_loop_module.is_valid_pre_master_precheck_elimination(mutated)

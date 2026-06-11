"""Tests for the P1.2 proof-obligation consolidation gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_p1_2_proof_obligations


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "data" / "proof_obligations" / "p1_2_proof_obligations.json"


def test_p1_2_proof_obligation_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_p1_2_proof_obligations.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "P1.2 proof obligation check passed: 8 obligations anchored" in result.stdout


def test_p1_2_proof_obligation_manifest_has_required_ids() -> None:
    manifest = check_p1_2_proof_obligations._load_json(MANIFEST_PATH)
    obligation_ids = {item["id"] for item in manifest["obligations"]}

    assert check_p1_2_proof_obligations.REQUIRED_OBLIGATION_IDS <= obligation_ids
    assert "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS" in obligation_ids
    assert manifest["phase_gate_required_anchor"] == "v91_nested_public_field_sealing"


def test_p1_2_proof_obligation_gate_rejects_boolean_schema_version() -> None:
    with pytest.raises(check_p1_2_proof_obligations.CheckError, match="schema_version must be an integer"):
        check_p1_2_proof_obligations._require_int(True, "schema_version")


def test_p1_2_proof_obligation_manifest_is_strict_json(tmp_path: Path) -> None:
    duplicate_key_manifest = tmp_path / "duplicate.json"
    duplicate_key_manifest.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")

    with pytest.raises(check_p1_2_proof_obligations.CheckError, match="duplicate JSON object key"):
        check_p1_2_proof_obligations._load_json(duplicate_key_manifest)


def test_p1_2_proof_obligation_manifest_lists_lifecycle_regressions_by_compartment() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    obligations = {item["id"]: set(item["required_tests"]) for item in manifest["obligations"]}

    replay_tests = obligations["PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS"]
    assert "test_persisted_cut_replay_fails_closed_on_unresolved_conflict_member" in replay_tests
    assert "test_coordinate_replay_alias_collision_fails_closed_instead_of_one_literal_ban" in replay_tests
    assert "test_pose_bool_replay_alias_collision_fails_closed" in replay_tests
    assert "test_legacy_benders_cut_alias_collision_fails_closed" in replay_tests
    assert "test_benders_cut_from_dict_rejects_condition_required_power_cut_with_unknown_condition_key" in replay_tests
    assert "test_certified_solver_ignores_persisted_exact_safe_cuts_until_revalidated" in replay_tests
    assert "test_resume_does_not_replay_persisted_exact_safe_cuts_into_master" in replay_tests
    assert "test_v83_binding_whole_layout_nogood_continues_lbbd" in replay_tests

    master_domain_tests = obligations["PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS"]
    assert "test_v63_outer_search_blocks_ghost_anchor_filter_env_before_session" in master_domain_tests
    assert "test_v65_outer_search_blocks_power_witness_encoding_env_before_session" in master_domain_tests
    assert "test_v65_direct_exact_search_session_create_blocks_power_witness_env_before_project_load" in master_domain_tests
    assert "test_v80_certified_exact_env_guard_blocks_unclassified_exact_knob" in master_domain_tests
    assert "test_v80_certified_exact_env_guard_blocks_known_proof_knob" in master_domain_tests
    assert "test_v80_certified_exact_env_guard_allows_production_wrapper_operational_envs" in master_domain_tests
    assert "test_v81_mandatory_rectangle_partial_time_budget_group_is_not_infeasible" in master_domain_tests
    assert "test_v81_mandatory_rectangle_complete_group_still_triggers_infeasible" in master_domain_tests
    assert "test_v83_certified_loader_rejects_non_mandatory_record_in_mandatory_exact_artifact" in master_domain_tests

    frontier_tests = obligations["PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE"]
    assert "test_exact_campaign_resume_rejects_certified_final_result_without_terminal_frontier_evidence" in frontier_tests
    assert "test_v62_partial_frontier_unknown_does_not_export_incumbent_as_certified" in frontier_tests
    assert "test_v80_resume_rejects_terminal_evidence_unknown_candidate_generation_key" in frontier_tests
    assert "test_v80_resume_rejects_terminal_evidence_min_side_admissibility_mismatch" in frontier_tests
    assert "test_v80_resume_rejects_v1_terminal_frontier_evidence_schema" in frontier_tests
    assert "test_v80_resume_rejects_terminal_final_result_below_project_admissibility" in frontier_tests
    assert "test_full_frontier_candidate_domain_keeps_oriented_dimensions" in frontier_tests

    export_tests = obligations["PO-CERTIFIED-EXPORT-SURFACE"]
    assert "test_delivery_manifest_rejects_certified_status_without_terminal_frontier_evidence" in export_tests
    assert "test_inspector_hides_stale_final_result_without_terminal_frontier_evidence" in export_tests
    assert "test_b5a_anchor_sprint_does_not_promote_stale_certified_final_result" in export_tests
    assert "test_v65_terminal_result_is_committed_before_final_solution_export" in export_tests
    assert "test_v77_delivery_manifest_export_rejects_memory_campaign_when_disk_checkpoint_differs" in export_tests
    assert "test_v77_delivery_manifest_export_rejects_symlink_campaign_checkpoint_for_best_result" in export_tests
    assert "test_v78_delivery_manifest_export_rejects_certified_best_result_to_noncanonical_output_path" in export_tests
    assert "test_v78_write_certified_delivery_manifest_rejects_direct_best_result_payload" in export_tests
    assert "test_v78_delivery_manifest_export_rejects_symlink_canonical_output_for_best_result" in export_tests
    assert "test_v80_resume_rejects_terminal_final_result_below_project_admissibility" in export_tests
    assert "test_v81_release_rejects_self_claimed_certified_run_summary" in export_tests
    assert "test_v81_release_rejects_lowercase_certified_claim" in export_tests
    assert "test_v81_release_accepts_open_exact_certified_status" in export_tests
    assert "test_v83_publishable_surface_rejects_certified_result_without_empty_rect_witness" in export_tests
    assert "test_v84_terminal_project_validation_rejects_layout_with_better_empty_rectangle" in export_tests
    assert "test_v84_terminal_project_validation_rejects_unknown_extra_blocker_instance" in export_tests
    assert "test_v85_terminal_project_validation_rejects_missing_required_pose_optional" in export_tests
    assert "test_terminal_project_validator_rejects_powered_facility_without_selected_power_coverer" in export_tests
    assert "test_terminal_project_validator_accepts_selected_power_coverer" in export_tests
    assert "test_terminal_project_validator_rejects_occupied_claimed_ghost_anchor" in export_tests
    assert "test_terminal_project_validator_rejects_unforced_power_pole_blocker" in export_tests
    assert "test_terminal_project_validator_requires_ghost_anchor" in export_tests
    assert "test_certified_blueprint_builder_rejects_missing_ghost_anchor" in export_tests
    assert "test_outer_search_certified_result_carries_ghost_anchor" in export_tests
    assert "test_terminal_solution_match_ignores_candidate_record_ghost_marker" in export_tests
    assert "test_terminal_project_validator_rejects_missing_candidate_ghost_pick" in export_tests
    assert "test_terminal_project_validator_rejects_mismatched_candidate_ghost_pick_anchor" in export_tests
    assert "test_terminal_project_validator_accepts_bound_candidate_ghost_pick_anchor" in export_tests
    assert "test_v91_rejects_nested_ghost_rect_fake_certified_claim" in export_tests
    assert "test_v91_rejects_search_stats_fake_certified_claim" in export_tests
    assert "test_v91_rejects_contradictory_mandatory_solution_metadata" in export_tests
    assert "test_v91_rejects_mandatory_operation_type_metadata_mismatch" in export_tests

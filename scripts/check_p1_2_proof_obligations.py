#!/usr/bin/env python3
"""Check the P1.2 proof-obligation consolidation manifest.

This is a small structural gate, not a theorem prover.  It makes the P1.2
postmortems concrete enough that future reviews cannot silently drift back to
local, duplicated proof checks.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, NoReturn, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "proof_obligations" / "p1_2_proof_obligations.json"
PHASE_GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"
PHASE_GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_phase_review_gate.py"
LIFECYCLE_PATH = PROJECT_ROOT / "src" / "cuts" / "lifecycle.py"
CANDIDATE_PLACEMENTS_PATH = PROJECT_ROOT / "src" / "cuts" / "helpers" / "candidate_placements.py"
CUT_MANAGER_PATH = PROJECT_ROOT / "src" / "models" / "cut_manager.py"
EXACT_CAMPAIGN_PATH = PROJECT_ROOT / "src" / "search" / "exact_campaign.py"
EXACT_CAMPAIGN_INSPECTOR_PATH = PROJECT_ROOT / "src" / "search" / "exact_campaign_inspector.py"
CERTIFIED_FRONTIER_PATH = PROJECT_ROOT / "src" / "search" / "certified_frontier.py"
CERTIFIED_SURFACE_PATH = PROJECT_ROOT / "src" / "search" / "certified_surface.py"
CANDIDATE_PROOF_REPLAY_PATH = PROJECT_ROOT / "src" / "search" / "candidate_proof_replay.py"
PR2_L0_MICRO_VERIFIER_PATH = PROJECT_ROOT / "src" / "search" / "pr2_l0_micro_verifier_core.py"
PR2_L0_TRUE_VERIFIER_CHILD_PATH = (
    PROJECT_ROOT / "src" / "search" / "pr2_l0_true_verifier_child.py"
)
PR2_DEPENDENCY_FLOOR_MANIFEST_REL = "data/proof_obligations/pr2_dependency_floor_manifest.json"
PR2_DEPENDENCY_FLOOR_GENERATOR_REL = "scripts/generate_pr2_dependency_floor_manifest.py"
PR2_DEPENDENCY_FLOOR_MANIFEST_PATH = PROJECT_ROOT / PR2_DEPENDENCY_FLOOR_MANIFEST_REL
PR2_DEPENDENCY_FLOOR_GENERATOR_PATH = PROJECT_ROOT / PR2_DEPENDENCY_FLOOR_GENERATOR_REL
PR2_DEPENDENCY_FLOOR_AUTHORITY = "pr2_l0_dependency_floor_manifest_v1"
PR2_DEPENDENCY_FLOOR_MANIFEST_SHA256 = (
    "41008dbb0bf03e1b413c493a96f5a5f47719721cc33112b353ed7c6bea240b90"
)
PR2_DEPENDENCY_FLOOR_MANIFEST_SIZE = 574082
PR2_DEPENDENCY_FLOOR_ROOT_SENTINEL = "PYTHON_SYSCONFIG_PURELIB"
PR2_DEPENDENCY_FLOOR_GENERATOR_SHA256 = (
    "0555322552375a2036ccac71afac85a29fc3773a7ac37ad09ad03b167bb6503c"
)
TERMINAL_FIXED_WITNESS_CAPSULE_PATH = (
    PROJECT_ROOT / "src" / "search" / "terminal_fixed_witness_capsule.py"
)
INDEPENDENT_INFEASIBILITY_REVERIFIER_PATH = (
    PROJECT_ROOT / "src" / "search" / "independent_infeasibility_reverifier.py"
)
OUTER_SEARCH_PATH = PROJECT_ROOT / "src" / "search" / "outer_search.py"
BENDERS_LOOP_PATH = PROJECT_ROOT / "src" / "search" / "benders_loop.py"
DELIVERY_MANIFEST_PATH = PROJECT_ROOT / "src" / "io" / "delivery_manifest.py"
SERIALIZER_PATH = PROJECT_ROOT / "src" / "io" / "serializer.py"
BLUEPRINT_EXPORTER_PATH = PROJECT_ROOT / "src" / "render" / "blueprint_exporter.py"
MASTER_MODEL_PATH = PROJECT_ROOT / "src" / "models" / "master_model.py"
EXACT_COORDINATE_MASTER_PATH = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
POSE_BOOL_EXACT_MASTER_PATH = PROJECT_ROOT / "src" / "models" / "pose_bool_exact_master.py"
SINGLE_BASE_RELEASE_BUILDER_PATH = (
    PROJECT_ROOT / "scripts" / "build_industrial_planner_single_base_delivery_release.py"
)
TEST_ROOT = PROJECT_ROOT / "src" / "tests"
VERIFIED_PRODUCER_TEST_SUPPORT_PATH = TEST_ROOT / "verified_producer_test_support.py"

REQUIRED_OBLIGATION_IDS = frozenset(
    {
        "PO-STEP7-ATTACH-MIRROR",
        "PO-SOURCE-DIGEST-COVERAGE",
        "PO-RUNTIME-CACHE-NON-AUTHORITY",
        "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS",
        "PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS",
        "PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE",
        "PO-CERTIFIED-EXPORT-SURFACE",
        "PO-PHASE-GATE-PROVENANCE",
        "PO-P1-2-CLOSE-KERNEL-SEALING",
        "PO-CANDIDATE-SINK-REPLAY-AUTHORITY",
        "PO-ISOLATED-EXEC-BYTECODE-BINDING",
        "PO-TERMINAL-FIXED-WITNESS-VERIFIER",
        "PO-EXACT-ARTIFACT-ATOMIC-SNAPSHOT",
        "PO-INDEPENDENT-INFEASIBILITY-REVERIFY",
    }
)
REQUIRED_TESTS_BY_OBLIGATION_ID = {
    "PO-INDEPENDENT-INFEASIBILITY-REVERIFY": frozenset(
        {
            "test_independent_infeasibility_reverify_confirms_binding_infeasible_allows_cut",
            "test_independent_infeasibility_reverify_divergent_feasible_blocks_cut_unknown",
            "test_independent_infeasibility_reverify_timeout_blocks_cut_unknown",
            "test_independent_infeasibility_reverify_exception_blocks_cut_unknown",
            "test_independent_infeasibility_reverify_routing_exhaustion_without_binding_confirmation_unknown",
            "test_p1_2_checker_rejects_whole_layout_reverify_gate_removal",
            "test_p1_2_checker_rejects_inflight_cache_read_in_infeasibility_reverifier",
            "test_p1_2_checker_rejects_env_reader_in_infeasibility_reverifier",
        }
    ),
    "PO-CANDIDATE-SINK-REPLAY-AUTHORITY": frozenset(
        {
            "test_p1_2_mutating_verified_writer_closure_cell_cannot_publish_false_certified",
            "test_p1_2_forged_proof_bearing_infeasible_cannot_prune_better_feasible_candidate",
            "test_p1_2_forged_certified_cannot_enter_terminal_manifest_or_public_surface",
            "test_p1_2_module_rebinding_monkeypatch_and_test_helper_do_not_grant_authority",
            "test_p1_2_strong_status_without_sink_replayable_proof_fails_closed",
            "test_p1_2_legitimate_certified_exact_path_survives_all_sink_replays",
            "test_p1_2_checker_rejects_candidate_replay_isolation_removal",
            "test_p1_2_checker_rejects_frontier_sink_replay_bypass",
        }
    ),
    "PO-ISOLATED-EXEC-BYTECODE-BINDING": frozenset(
        {
            "test_candidate_replay_isolated_subprocess_uses_fresh_pycache_prefix",
            "test_fixed_witness_capsule_isolated_subprocess_uses_fresh_pycache_prefix",
            "test_isolated_replay_ignores_repo_pycache_bytecode_injection",
            "test_p1_2_checker_rejects_isolated_exec_bytecode_binding_removal",
        }
    ),
    "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS": frozenset(
        {
            "test_benders_cut_from_dict_rejects_string_exact_safe_flag",
            "test_collect_certification_blockers_rejects_non_bool_exact_safe_object",
            "test_benders_cut_from_dict_rejects_string_conflict_pose_index",
            "test_benders_cut_from_dict_rejects_bool_conflict_pose_index",
            "test_benders_cut_from_dict_rejects_bool_condition_anchor_index",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_without_condition_set",
            "test_benders_cut_to_dict_rejects_condition_required_power_cut_without_condition_set",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_with_unknown_condition_key",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_metadata_mismatch",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_rect_idx_mismatch",
            "test_benders_cut_from_dict_rejects_noncanonical_ghost_anchor_condition_keys",
            "test_collect_certification_blockers_rejects_bool_conflict_pose_index",
            "test_exact_campaign_resume_rejects_malformed_exact_safe_cut",
            "test_exact_campaign_resume_rejects_bool_conflict_pose_index",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_without_condition_set",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_with_unknown_condition_key",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_metadata_mismatch",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_rect_idx_not_resolver_supported",
            "test_exact_campaign_resume_accepts_condition_required_power_cut_with_resolver_supported_anchor",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_anchor_outside_domain",
            "test_cut_manager_load_rejects_duplicate_exact_safe_key",
            "test_exact_campaign_resume_rejects_duplicate_json_key",
            "test_exact_campaign_resume_rejects_json_nan_constant",
            "test_cut_manager_load_rejects_json_nan_constant",
            "test_persisted_cut_replay_fails_closed_on_unresolved_conflict_member",
            "test_whole_layout_cut_dilution_fails_closed_when_synthetic_pole_loses_literal",
            "test_whole_layout_nogood_propagates_master_rejection_for_unresolved_member",
            "test_routing_front_blocked_unencodable_optional_conflict_fails_closed",
            "test_coordinate_replay_alias_collision_fails_closed_instead_of_one_literal_ban",
            "test_pose_bool_replay_alias_collision_fails_closed",
            "test_legacy_benders_cut_alias_collision_fails_closed",
            "test_resolver_fails_closed_on_malformed_ghost_anchor_key",
            "test_certified_solver_ignores_persisted_exact_safe_cuts_until_revalidated",
            "test_resume_does_not_replay_persisted_exact_safe_cuts_into_master",
            "test_v83_binding_whole_layout_nogood_continues_lbbd",
        }
    ),
    "PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS": frozenset(
        {
            "test_exact_campaign_state_persists_full_master_domain_contract",
            "test_exact_campaign_resume_rejects_filtered_master_domain_contract",
            "test_certified_exact_blocks_ghost_anchor_filter_env_before_candidate_terminal_status",
            "test_certified_exact_blocks_pose_bool_master_env_before_session",
            "test_certified_exact_blocks_power_pole_slot_override_before_session",
            "test_certified_exact_blocks_power_representation_env_before_session",
            "test_create_exact_search_session_blocks_power_representation_env_before_session",
            "test_v64_outer_search_blocks_power_representation_env_before_session",
            "test_v62_outer_search_blocks_unsafe_master_domain_env_before_session",
            "test_v63_outer_search_blocks_ghost_anchor_filter_env_before_session",
            "test_v65_outer_search_blocks_power_witness_encoding_env_before_session",
            "test_v65_direct_exact_search_session_create_blocks_power_witness_env_before_project_load",
            "test_v80_certified_exact_env_guard_blocks_unclassified_exact_knob",
            "test_v80_certified_exact_env_guard_blocks_known_proof_knob",
            "test_v80_certified_exact_env_guard_allows_production_wrapper_operational_envs",
            "test_v81_mandatory_rectangle_partial_time_budget_group_is_not_infeasible",
            "test_v81_mandatory_rectangle_complete_group_still_triggers_infeasible",
            "test_v83_certified_loader_rejects_non_mandatory_record_in_mandatory_exact_artifact",
        }
    ),
    "PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE": frozenset(
        {
            "test_exact_campaign_resume_rejects_float_state_schema_version",
            "test_exact_campaign_resume_rejects_float_proof_summary_schema_version",
            "test_exact_campaign_resume_rejects_bool_generated_cut_count",
            "test_exact_campaign_resume_rejects_best_effort_final_result",
            "test_exact_campaign_resume_rejects_missing_declare_mode",
            "test_certified_outer_search_blocks_skip_unknown_env_before_fake_certified",
            "test_v62_partial_frontier_unknown_does_not_export_incumbent_as_certified",
            "test_exact_campaign_resume_rejects_certified_final_result_without_terminal_frontier_evidence",
            "test_v75_resume_rejects_terminal_certified_without_replayable_frontier_evidence",
            "test_v75_resume_rejects_terminal_evidence_with_unexhausted_frontier",
            "test_v75_resume_rejects_terminal_evidence_from_start_area_slice",
            "test_v79_resume_rejects_terminal_evidence_from_aspect_ratio_slice",
            "test_v79_resume_rejects_terminal_evidence_from_min_side_slice",
            "test_v76_best_certified_result_rejects_frontier_evidence_not_bound_to_project_domain",
            "test_v68_resume_rejects_certified_candidate_without_solution",
            "test_v69_resume_inspector_and_b5a_reject_terminal_final_result_not_best_candidate",
            "test_v80_resume_rejects_terminal_evidence_unknown_candidate_generation_key",
            "test_v80_resume_rejects_terminal_evidence_min_side_admissibility_mismatch",
            "test_v80_resume_rejects_v1_terminal_frontier_evidence_schema",
            "test_v80_resume_rejects_terminal_final_result_below_project_admissibility",
            "test_full_frontier_candidate_domain_keeps_oriented_dimensions",
            "test_save_rejects_dict_subclass_that_mutates_after_guard",
        }
    ),
    "PO-CERTIFIED-EXPORT-SURFACE": frozenset(
        {
            "test_delivery_manifest_rejects_best_effort_final_result",
            "test_v62_best_effort_exhaustion_blocks_before_final_solution_export",
            "test_delivery_manifest_rejects_certified_status_without_terminal_frontier_evidence",
            "test_delivery_manifest_rejects_stale_certified_final_result_without_terminal_frontier_evidence",
            "test_inspector_hides_stale_final_result_without_terminal_frontier_evidence",
            "test_inspector_hides_stale_delivery_manifest_best_result_without_terminal_evidence",
            "test_b5a_anchor_sprint_does_not_promote_stale_certified_final_result",
            "test_v65_unsafe_env_block_clears_resumed_terminal_final_result",
            "test_v65_terminal_result_is_committed_before_final_solution_export",
            "test_v66_unsafe_env_block_clears_stale_certified_delivery_artifacts",
            "test_v66_terminal_export_failure_clears_terminal_state_and_artifacts",
            "test_v68_terminal_commit_failure_clears_stale_certified_delivery_artifacts",
            "test_v68_inspector_requires_current_campaign_evidence_for_terminal_manifest",
            "test_v68_delivery_manifest_rejects_best_result_before_delivery_artifacts",
            "test_v69_delivery_manifest_rejects_stale_final_solution_artifact",
            "test_v69_delivery_manifest_rejects_stale_optimal_blueprint_artifact",
            "test_v69_inspector_rejects_manifest_best_result_that_only_partially_matches_campaign",
            "test_v71_delivery_manifest_rejects_stale_exact_artifact_hash_before_best_result",
            "test_v71_delivery_manifest_rejects_tampered_blueprint_active_ports",
            "test_v71_inspector_and_b5a_reject_manifest_with_stale_artifact_table",
            "test_v72_delivery_manifest_rejects_blueprint_with_extra_raw_fields",
            "test_v72_manifest_currentness_rejects_extra_metadata_fields",
            "test_v72_delivery_manifest_rejects_blueprint_missing_terminal_routing_solution",
            "test_v72_blocked_campaign_cleanup_runs_even_when_checkpoint_save_fails",
            "test_v73_inspector_uses_certified_surface_verifier_for_public_certified",
            "test_v73_b5a_uses_certified_surface_verifier_for_anchor_publication",
            "test_v73_certified_surface_verdict_is_single_gate_for_inspector_and_b5a",
            "test_v73_certified_surface_rejects_non_regular_manifest_path",
            "test_v74_certified_surface_rejects_memory_manifest_when_disk_manifest_stale",
            "test_v74_certified_surface_rejects_memory_campaign_when_disk_checkpoint_differs",
            "test_v74_certified_surface_recomputes_exact_hashes_even_when_caller_claims_resume_ok",
            "test_v74_inspector_rejects_duplicate_key_delivery_manifest",
            "test_v74_delivery_manifest_rejects_duplicate_key_final_solution_artifact",
            "test_v77_delivery_manifest_export_rejects_memory_campaign_when_disk_checkpoint_differs",
            "test_v77_delivery_manifest_export_rejects_symlink_campaign_checkpoint_for_best_result",
            "test_v78_delivery_manifest_export_rejects_certified_best_result_to_noncanonical_output_path",
            "test_v78_write_certified_delivery_manifest_rejects_direct_best_result_payload",
            "test_v78_delivery_manifest_export_rejects_symlink_canonical_output_for_best_result",
            "test_v79_delivery_manifest_rejects_non_instance_placement_solution",
            "test_aspect_ratio_sliced_search_cannot_claim_terminal_certified",
            "test_v81_release_rejects_self_claimed_certified_run_summary",
            "test_v81_release_rejects_lowercase_certified_claim",
            "test_v81_release_accepts_open_exact_certified_status",
            "test_v92_release_rejects_embedded_certified_claim",
            "test_v92_release_rejects_non_allowlisted_exact_status",
            "test_v93_release_rejects_forged_exact_note_with_open_status",
            "test_v93_rejects_solution_entry_fake_certified_claim",
            "test_v93_rejects_public_final_result_ghost_pick_marker",
            "test_terminal_project_validator_rejects_surplus_protocol_storage_box_blockers",
            "test_v95_rejects_contradictory_pose_optional_public_metadata",
            "test_v95_rejects_terminal_public_last_stop_reason_extra_claim_field",
            "test_v96_certified_surface_rejects_manifest_under_symlinked_solutions_parent",
            "test_v97_delivery_manifest_rejects_certified_shadow_campaign_checkpoint",
            "test_v97_certified_surface_rejects_certified_shadow_campaign_checkpoint",
            "test_v97_certified_surface_rejects_symlink_campaign_path_to_canonical_checkpoint",
            "test_v97_inspector_preserves_symlink_campaign_path_until_surface_verifier",
            "test_v98_b5a_preserves_symlink_campaign_path_until_surface_verifier",
            "test_unchecked_certified_surface_writer_is_not_module_importable",
            "test_generic_blueprint_writer_rejects_canonical_certified_path",
            "test_delivery_manifest_rejects_chameleon_mapping_that_skips_disk_authority",
            "test_p1_2_checker_rejects_raw_canonical_writer_bypass",
            "test_p1_2_checker_rejects_publisher_rollback_removal",
            "test_p1_2_checker_rejects_publisher_canonical_write_before_bundle_commit",
            "test_p1_2_checker_rejects_publisher_bundle_commit_removal",
            "test_p1_2_checker_rejects_publisher_staged_commit_removal",
            "test_p1_2_checker_rejects_manifest_mapping_snapshot_removal",
            "test_p1_2_checker_rejects_manifest_snapshot_token_comment_decoy",
            "test_p1_2_checker_rejects_staged_manifest_artifact_binding_removal",
            "test_clear_certified_delivery_surface_artifacts_attempts_all_after_unlink_failure",
            "test_serve_viewer_partial_generation_commit_clears_all_public_outputs",
            "test_serve_viewer_requires_current_candidate_placements_and_clears_stale_copy",
            "test_publish_viewer_report_clears_stale_output_when_build_fails",
            "test_write_viewer_report_rejects_canonical_public_path",
            "test_main_visualization_clears_stale_png_when_surface_not_publishable",
            "test_main_visualization_renderer_failure_clears_all_png_outputs",
            "test_write_industrial_planner_bundle_partial_commit_clears_all_outputs",
            "test_clear_industrial_planner_export_bundle_attempts_all_files_after_failure",
            "test_render_blueprint_export_wrapper_rejects_repo_canonical_export_dir",
            "test_industrial_export_frontdoor_gate_block_clears_stale_bundle",
            "test_industrial_export_frontdoor_refresh_failure_clears_written_bundle",
            "test_p1_2_publish_open_gate_blocks_open_statuses",
            "test_p1_2_publish_open_gate_missing_file_fails_closed",
            "test_p1_2_publish_open_gate_rejects_malformed_gate_files",
            "test_p1_2_publish_open_gate_closed_manual_decision_allows_publishable_surface",
            "test_p1_2_publish_open_gate_rejects_contradictory_closed_gate",
            "test_p1_2_publish_open_gate_inherited_public_surfaces_fail_closed",
            "test_resolve_p1_2_publish_open_gate_fail_closed_branches",
            "test_v83_publishable_surface_rejects_certified_result_without_empty_rect_witness",
            "test_v84_terminal_project_validation_rejects_layout_with_better_empty_rectangle",
            "test_v84_terminal_project_validation_rejects_unknown_extra_blocker_instance",
            "test_v85_terminal_project_validation_rejects_missing_required_pose_optional",
            "test_terminal_project_validator_rejects_powered_facility_without_selected_power_coverer",
            "test_terminal_project_validator_accepts_selected_power_coverer",
            "test_terminal_project_validator_rejects_occupied_claimed_ghost_anchor",
            "test_terminal_project_validator_rejects_unforced_power_pole_blocker",
            "test_terminal_project_validator_requires_ghost_anchor",
            "test_certified_blueprint_builder_rejects_missing_ghost_anchor",
            "test_outer_search_certified_result_carries_ghost_anchor",
            "test_terminal_solution_match_ignores_candidate_record_ghost_marker",
            "test_terminal_project_validator_rejects_missing_candidate_ghost_pick",
            "test_terminal_project_validator_rejects_mismatched_candidate_ghost_pick_anchor",
            "test_terminal_project_validator_accepts_bound_candidate_ghost_pick_anchor",
            "test_v91_rejects_nested_ghost_rect_fake_certified_claim",
            "test_v91_rejects_search_stats_fake_certified_claim",
            "test_v91_rejects_contradictory_mandatory_solution_metadata",
            "test_v91_rejects_mandatory_operation_type_metadata_mismatch",
        }
    ),
    "PO-PHASE-GATE-PROVENANCE": frozenset(
        {
            "test_phase_review_gate_manifest_is_consistent",
            "test_require_ready_fails_while_manual_gate_blocked",
            "test_manual_gate_rejects_auto_counter_fields",
            "test_manual_gate_rejects_next_phase_allowed_without_owner_decision",
            "test_manual_gate_rejects_closed_status_without_owner_decision",
            "test_manual_gate_requires_step_8_fail_closed_when_blocked",
            "test_manual_gate_accepts_owner_decision_authority_fixture",
            "test_manual_gate_receipts_are_informational_only",
            "test_p1_2_fix_3_phase_gate_requires_fixed_witness_verifier_present",
            "test_p1_2_fix_3_phase_gate_witness_bound_close_condition_stays_blocked",
            "test_p1_2_fix_3_publish_binding_detects_unwired_verifier",
            "test_p1_2_fix_3_provenance_requires_check_gate_fixed_witness_binding",
            "test_fix_3_phase_checker_rejects_two_empty_function_verifier_stub",
            "test_fix_3_phase_checker_rejects_fake_capsule_projection",
            "test_fix_3_publish_wiring_rejects_required_symbol_shadowing",
            "test_fix_3_publish_wiring_rejects_dead_branch_capsule_call",
            "test_fix_3_current_phase_gate_stays_blocked",
        }
    ),
    "PO-TERMINAL-FIXED-WITNESS-VERIFIER": frozenset(
        {
            "test_fixed_witness_rejects_binding_routing_witness_split",
            "test_fixed_witness_rejects_non_r_star_ghost_origin",
            "test_fixed_witness_timeout_unknown_demotes_unproven",
            "test_fixed_witness_binding_infeasible_demotes_unproven_not_infeasible",
            "test_fixed_witness_rejects_consistent_tamper_after_precheck_accepts",
            "test_fixed_witness_round_trip_rejects_post_write_tampered_witness_bytes",
            "test_fixed_witness_projection_copy_failure_demotes_unproven",
            "test_fixed_witness_does_not_mutate_record_solution_or_solution_digest",
            "test_fixed_witness_accepts_valid_r_star_pi_star",
            "test_fixed_witness_rejects_connector_cell_occupied_by_other_body",
            "test_fixed_witness_rejects_forged_publishable_verdict_on_unchanged_bad_witness",
            "test_fixed_witness_verify_time_reruns_and_ignores_stored_verdict",
            "test_build_then_verify_uses_fresh_projection_without_status_digest_mismatch",
            "test_fixed_witness_unproven_durable_record_keeps_solution_bytes",
        }
    ),
    "PO-EXACT-ARTIFACT-ATOMIC-SNAPSHOT": frozenset(
        {
            "test_fix5_snapshot_hash_attests_returned_text_bytes",
            "test_fix5_snapshot_hashes_match_compute_exact_artifact_hashes",
            "test_fix5_text_loaders_are_faithful_to_path_loaders",
            "test_fix5_read_once_regular_file_bytes_rejects_non_regular",
            "test_fix5_create_uses_atomic_snapshot_not_second_read",
        }
    ),
    "PO-P1-2-CLOSE-KERNEL-SEALING": frozenset(
        {
            "test_p1_2_close_kernel_rejects_unregistered_certified_sink",
            "test_p1_2_close_kernel_rejects_guard_token_removal",
            "test_p1_2_close_kernel_rejects_registered_sink_hash_drift",
            "test_p1_2_close_kernel_manifest_is_strict_json",
            "test_p1_2_close_kernel_self_binding_rejects_removed_close_kernel_call",
            "test_p1_2_close_kernel_rejects_dependency_floor_generator_drift",
            "test_p1_2_close_kernel_rejects_dependency_floor_manifest_drift",
            "test_l0_canonical_dependency_floor_manifest_missing_fails_closed",
            "test_l0_canonical_dependency_floor_manifest_drift_fails_closed",
            "test_l0_canonical_dependency_floor_manifest_current_bytes_are_pinned",
            "test_locked_close_kernel_ignores_parent_sitecustomize_bypass",
            "test_locked_close_kernel_identityless_process_modes_do_not_bypass_subprocess",
            "test_p1_2_close_kernel_strong_status_gate_ignores_parent_sitecustomize",
            "test_p1_2_close_kernel_source_floor_pins_runtime_guard_and_l0_floor_loader",
            "test_fix_3_unknown_review_anchor_fails_closed",
            "test_fix_3_coordinated_anchor_and_source_hash_reseal_is_rejected",
            "test_fix_3_v99_static_floor_runs_without_any_v99_anchor",
            "test_fix_3_capsule_name_guard_dead_branch_manifest_reseal_is_rejected",
            "test_package_review_snapshot_default_targeted_tests_exist",
            "test_package_review_snapshot_excludes_agent_memory_and_review_packets",
            "test_package_review_snapshot_binds_commit_tree_and_dirty_state",
            "test_package_review_snapshot_records_renamed_dirty_paths",
            "test_package_review_snapshot_embedded_manifest_records_verification_receipt",
            "test_package_review_snapshot_skip_tests_marker_is_embedded",
            "test_package_review_snapshot_selftest_disables_pytest_plugin_autoload",
        }
    ),
}


class CheckError(RuntimeError):
    pass


def _rel(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise CheckError(f"invalid JSON constant {value!r}; proof-obligation JSON must be strict JSON")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except Exception as exc:  # noqa: BLE001
        raise CheckError(f"cannot read {_rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise CheckError(f"{_rel(path)} must contain a JSON object")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CheckError(f"{label} must be a non-empty string")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CheckError(f"{label} must be a list")
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CheckError(f"{label} must be an integer")
    return value


def _parse_python(path: Path) -> ast.Module:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        raise CheckError(f"cannot parse {_rel(path)}: {exc}") from exc
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_p1_2_parent", parent)
    return tree


def _parse_lifecycle() -> ast.Module:
    return _parse_python(LIFECYCLE_PATH)


def _function_def(tree: ast.Module, name: str, *, path: Path = LIFECYCLE_PATH) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise CheckError(f"function not found in {_rel(path)}: {name}")


def _class_def(tree: ast.Module, name: str, *, path: Path) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise CheckError(f"class not found in {_rel(path)}: {name}")


def _method_def(class_node: ast.ClassDef, name: str, *, path: Path) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise CheckError(f"method not found in {_rel(path)}: {class_node.name}.{name}")


def _calls_function(node: ast.AST, name: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name:
            return True
    return False


def _calls_function_with_keyword_constant(
    node: ast.AST,
    function_name: str,
    keyword_name: str,
    expected_value: object,
) -> bool:
    """Return True only for one direct call with the exact literal keyword.

    Source-token checks can be satisfied by comments or dead strings.  The
    candidate replay boundary is proof-authoritative, so its witness-binding
    mode is checked in the AST of the actual call instead.
    """

    calls = [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == function_name
    ]
    if len(calls) != 1:
        return False
    keywords = [keyword for keyword in calls[0].keywords if keyword.arg == keyword_name]
    if len(keywords) != 1:
        return False
    value = keywords[0].value
    return isinstance(value, ast.Constant) and value.value is expected_value


def _calls_function_with_keyword_expr(
    node: ast.AST,
    function_name: str,
    keyword_name: str,
    expected_expr: str,
) -> bool:
    """Return True when a direct call binds a keyword to the exact expression."""

    for child in ast.walk(node):
        if not (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == function_name
        ):
            continue
        for keyword in child.keywords:
            if keyword.arg != keyword_name:
                continue
            try:
                if ast.unparse(keyword.value) == expected_expr:
                    return True
            except Exception:
                return False
    return False


def _top_level_imports_exact_name(tree: ast.Module, *, module: str, name: str) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != module:
            continue
        for alias in node.names:
            if alias.name == name and alias.asname is None:
                return True
    return False


def _function_imports_exact_name(node: ast.AST, *, module: str, name: str) -> bool:
    found = False

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.generic_visit(child)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.generic_visit(child)

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            nonlocal found
            if child.level == 0 and child.module == module:
                for alias in child.names:
                    if alias.name == name and alias.asname is None:
                        found = True

    Visitor().visit(node)
    return found


def _ast_root(node: ast.AST) -> ast.AST:
    root = node
    while True:
        parent = getattr(root, "_p1_2_parent", None)
        if parent is None:
            return root
        root = parent


def _store_target_names(target: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(target):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
    return names


def _assign_targets(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return set()
    names: set[str] = set()
    for target in targets:
        names.update(_store_target_names(target))
    return names


def _constant_bool_value(
    value: ast.AST | None,
    false_names: set[str] | None = None,
    true_names: set[str] | None = None,
) -> bool | None:
    if isinstance(value, ast.Constant):
        return bool(value.value)
    if isinstance(value, ast.Name):
        if value.id == "TYPE_CHECKING" or value.id in (false_names or set()):
            return False
        if value.id in (true_names or set()):
            return True
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not):
        operand_value = _constant_bool_value(value.operand, false_names, true_names)
        if operand_value is not None:
            return not operand_value
    if isinstance(value, ast.BoolOp):
        if isinstance(value.op, ast.And):
            for operand in value.values:
                operand_value = _constant_bool_value(operand, false_names, true_names)
                if operand_value is False:
                    return False
                if operand_value is None:
                    return None
            return True
        if isinstance(value.op, ast.Or):
            for operand in value.values:
                operand_value = _constant_bool_value(operand, false_names, true_names)
                if operand_value is True:
                    return True
                if operand_value is None:
                    return None
            return False
    return None


def _is_constant_false(value: ast.AST | None) -> bool:
    return _constant_bool_value(value) is False


def _module_constant_bool_names(node: ast.AST) -> tuple[set[str], set[str]]:
    root = _ast_root(node)
    if not isinstance(root, ast.Module):
        return set(), set()
    false_names: set[str] = set()
    true_names: set[str] = set()
    for statement in root.body:
        targets = _assign_targets(statement)
        if not targets:
            continue
        value = None
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = _constant_bool_value(statement.value, false_names, true_names)
        if value is False:
            false_names.update(targets)
            true_names.difference_update(targets)
        elif value is True:
            true_names.update(targets)
            false_names.difference_update(targets)
        else:
            false_names.difference_update(targets)
            true_names.difference_update(targets)
    return false_names, true_names


def _module_constant_false_names(node: ast.AST) -> set[str]:
    false_names, _true_names = _module_constant_bool_names(node)
    return false_names


def _function_scope_binding_names(node: ast.AST) -> set[str]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    names = {
        argument.arg
        for argument in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        )
    }
    if node.args.vararg is not None:
        names.add(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.add(node.args.kwarg.arg)

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.generic_visit(child)
            else:
                names.add(child.name)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.generic_visit(child)
            else:
                names.add(child.name)

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            names.add(child.name)

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_Assign(self, child: ast.Assign) -> None:
            names.update(_assign_targets(child))
            self.visit(child.value)

        def visit_AnnAssign(self, child: ast.AnnAssign) -> None:
            names.update(_assign_targets(child))
            if child.value is not None:
                self.visit(child.value)

        def visit_AugAssign(self, child: ast.AugAssign) -> None:
            names.update(_assign_targets(child))
            self.visit(child.value)

        def visit_For(self, child: ast.For) -> None:
            names.update(_store_target_names(child.target))
            self.generic_visit(child)

        def visit_AsyncFor(self, child: ast.AsyncFor) -> None:
            names.update(_store_target_names(child.target))
            self.generic_visit(child)

        def visit_With(self, child: ast.With) -> None:
            for item in child.items:
                if item.optional_vars is not None:
                    names.update(_store_target_names(item.optional_vars))
            self.generic_visit(child)

        def visit_AsyncWith(self, child: ast.AsyncWith) -> None:
            for item in child.items:
                if item.optional_vars is not None:
                    names.update(_store_target_names(item.optional_vars))
            self.generic_visit(child)

        def visit_ExceptHandler(self, child: ast.ExceptHandler) -> None:
            if child.name is not None:
                names.add(child.name)
            self.generic_visit(child)

        def visit_Import(self, child: ast.Import) -> None:
            for alias in child.names:
                names.add(alias.asname or alias.name.split(".")[0])

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            for alias in child.names:
                names.add(alias.asname or alias.name)

    Visitor().visit(node)
    return names


def _constant_guard_value(
    test: ast.AST,
    false_names: set[str],
    true_names: set[str],
) -> bool | None:
    return _constant_bool_value(test, false_names, true_names)


def _reachable_direct_call(node: ast.AST, predicate: Callable[[ast.Call], bool]) -> bool:
    found = False
    module_false_names, module_true_names = _module_constant_bool_names(node)
    function_bindings = _function_scope_binding_names(node)
    false_names = module_false_names - function_bindings
    true_names = module_true_names - function_bindings

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.false_names = set(false_names)
            self.true_names = set(true_names)

        def visit_statements(self, statements: Sequence[ast.stmt]) -> None:
            for statement in statements:
                self.visit(statement)
                if isinstance(statement, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    break

        def _record_assignment(self, targets: set[str], value: bool | None) -> None:
            if value is False:
                self.false_names.update(targets)
                self.true_names.difference_update(targets)
            elif value is True:
                self.true_names.update(targets)
                self.false_names.difference_update(targets)
            else:
                self.false_names.difference_update(targets)
                self.true_names.difference_update(targets)

        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.visit_statements(child.body)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.visit_statements(child.body)

        def visit_Module(self, child: ast.Module) -> None:
            if child is node:
                self.visit_statements(child.body)

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_Assign(self, child: ast.Assign) -> None:
            self.visit(child.value)
            targets = _assign_targets(child)
            value = _constant_bool_value(child.value, self.false_names, self.true_names)
            self._record_assignment(targets, value)

        def visit_AnnAssign(self, child: ast.AnnAssign) -> None:
            if child.value is not None:
                self.visit(child.value)
            targets = _assign_targets(child)
            value = _constant_bool_value(child.value, self.false_names, self.true_names)
            self._record_assignment(targets, value)

        def visit_AugAssign(self, child: ast.AugAssign) -> None:
            self.visit(child.value)
            targets = _assign_targets(child)
            self.false_names.difference_update(targets)
            self.true_names.difference_update(targets)

        def visit_If(self, child: ast.If) -> None:
            guard_value = _constant_guard_value(child.test, self.false_names, self.true_names)
            if guard_value is False:
                self.visit_statements(child.orelse)
                return
            if guard_value is True:
                self.visit_statements(child.body)
                return
            self.visit(child.test)
            saved_false = set(self.false_names)
            saved_true = set(self.true_names)
            self.visit_statements(child.body)
            self.false_names = set(saved_false)
            self.true_names = set(saved_true)
            self.visit_statements(child.orelse)
            self.false_names = saved_false
            self.true_names = saved_true

        def visit_While(self, child: ast.While) -> None:
            guard_value = _constant_guard_value(child.test, self.false_names, self.true_names)
            if guard_value is False:
                self.visit_statements(child.orelse)
                return
            self.visit(child.test)
            saved_false = set(self.false_names)
            saved_true = set(self.true_names)
            self.visit_statements(child.body)
            self.false_names = set(saved_false)
            self.true_names = set(saved_true)
            self.visit_statements(child.orelse)
            self.false_names = saved_false
            self.true_names = saved_true

        def visit_IfExp(self, child: ast.IfExp) -> None:
            guard_value = _constant_guard_value(child.test, self.false_names, self.true_names)
            if guard_value is False:
                self.visit(child.orelse)
                return
            if guard_value is True:
                self.visit(child.body)
                return
            self.visit(child.test)
            self.visit(child.body)
            self.visit(child.orelse)

        def visit_BoolOp(self, child: ast.BoolOp) -> None:
            if isinstance(child.op, ast.And):
                for operand in child.values:
                    self.visit(operand)
                    operand_value = _constant_bool_value(operand, self.false_names, self.true_names)
                    if operand_value is False:
                        break
                return
            if isinstance(child.op, ast.Or):
                for operand in child.values:
                    self.visit(operand)
                    operand_value = _constant_bool_value(operand, self.false_names, self.true_names)
                    if operand_value is True:
                        break
                return
            self.generic_visit(child)

        def visit_Import(self, child: ast.Import) -> None:
            for alias in child.names:
                name = alias.asname or alias.name.split(".")[0]
                self.false_names.discard(name)
                self.true_names.discard(name)

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            for alias in child.names:
                name = alias.asname or alias.name
                self.false_names.discard(name)
                self.true_names.discard(name)

        def visit_For(self, child: ast.For) -> None:
            targets = _store_target_names(child.target)
            self.false_names.difference_update(targets)
            self.true_names.difference_update(targets)
            self.visit(child.iter)
            self.visit_statements(child.body)
            self.visit_statements(child.orelse)

        def visit_AsyncFor(self, child: ast.AsyncFor) -> None:
            targets = _store_target_names(child.target)
            self.false_names.difference_update(targets)
            self.true_names.difference_update(targets)
            self.visit(child.iter)
            self.visit_statements(child.body)
            self.visit_statements(child.orelse)

        def visit_With(self, child: ast.With) -> None:
            for item in child.items:
                self.visit(item.context_expr)
                if item.optional_vars is not None:
                    targets = _store_target_names(item.optional_vars)
                    self.false_names.difference_update(targets)
                    self.true_names.difference_update(targets)
            self.visit_statements(child.body)

        def visit_AsyncWith(self, child: ast.AsyncWith) -> None:
            for item in child.items:
                self.visit(item.context_expr)
                if item.optional_vars is not None:
                    targets = _store_target_names(item.optional_vars)
                    self.false_names.difference_update(targets)
                    self.true_names.difference_update(targets)
            self.visit_statements(child.body)

        def visit_Try(self, child: ast.Try) -> None:
            self.visit_statements(child.body)
            for handler in child.handlers:
                self.visit(handler)
            self.visit_statements(child.orelse)
            self.visit_statements(child.finalbody)

        def visit_ExceptHandler(self, child: ast.ExceptHandler) -> None:
            if child.name is not None:
                self.false_names.discard(child.name)
                self.true_names.discard(child.name)
            if child.type is not None:
                self.visit(child.type)
            self.visit_statements(child.body)

        def visit_Call(self, child: ast.Call) -> None:
            nonlocal found
            if predicate(child):
                found = True
            self.generic_visit(child)

    Visitor().visit(node)
    return found


def _direct_calls_name(node: ast.AST, name: str) -> bool:
    return _reachable_direct_call(
        node,
        lambda child: isinstance(child.func, ast.Name) and child.func.id == name,
    )


def _direct_calls_attr(node: ast.AST, attr: str) -> bool:
    return _reachable_direct_call(
        node,
        lambda child: isinstance(child.func, ast.Attribute) and child.func.attr == attr,
    )


def _function_shadows_name(
    node: ast.FunctionDef,
    name: str,
    *,
    allowed_import_module: str | None = None,
) -> bool:
    arguments = (
        list(node.args.posonlyargs)
        + list(node.args.args)
        + list(node.args.kwonlyargs)
    )
    if node.args.vararg is not None:
        arguments.append(node.args.vararg)
    if node.args.kwarg is not None:
        arguments.append(node.args.kwarg)
    if any(argument.arg == name for argument in arguments):
        return True

    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == name:
            return True
        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: list[ast.AST] = []
            if isinstance(child, ast.Assign):
                targets.extend(child.targets)
            else:
                targets.append(child.target)
            if any(name in _store_target_names(target) for target in targets):
                return True
        if isinstance(child, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith)):
            targets = []
            if isinstance(child, (ast.For, ast.AsyncFor)):
                targets.append(child.target)
            else:
                targets.extend(item.optional_vars for item in child.items if item.optional_vars is not None)
            if any(name in _store_target_names(target) for target in targets):
                return True
        if isinstance(child, ast.ExceptHandler) and child.name == name:
            return True
        if isinstance(child, ast.Import):
            for alias in child.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound == name:
                    return True
        if isinstance(child, ast.ImportFrom):
            for alias in child.names:
                bound = alias.asname or alias.name
                if bound != name:
                    continue
                if (
                    allowed_import_module is not None
                    and child.level == 0
                    and child.module == allowed_import_module
                    and alias.name == name
                    and alias.asname is None
                ):
                    continue
                return True
    return False


def _imported_direct_call_errors(
    *,
    tree: ast.Module,
    function: ast.FunctionDef,
    path: Path,
    function_label: str,
    module: str,
    name: str,
    allow_local_import: bool = False,
) -> list[str]:
    errors: list[str] = []
    has_top_level_import = _top_level_imports_exact_name(tree, module=module, name=name)
    has_local_import = allow_local_import and _function_imports_exact_name(function, module=module, name=name)
    if not has_top_level_import and not has_local_import:
        errors.append(
            f"{function_label} must import {name} from {module} without aliasing"
        )
    allowed_module = module if allow_local_import else None
    if _function_shadows_name(function, name, allowed_import_module=allowed_module):
        errors.append(
            f"{function_label} shadows imported fixed-witness capsule symbol {name}"
        )
    if not _direct_calls_name(function, name):
        errors.append(
            f"{function_label} must call imported fixed-witness capsule symbol {name} "
            f"on the reachable main path in {_rel(path)}"
        )
    return errors


def _calls_attr(node: ast.AST, attr: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == attr:
            return True
    return False


def _returns_constant(node: ast.AST, value: object) -> bool:
    return any(isinstance(child, ast.Return) and isinstance(child.value, ast.Constant) and child.value.value is value for child in ast.walk(node))


def _raises_value_error(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Raise):
            continue
        exc = child.exc
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "ValueError":
            return True
        if isinstance(exc, ast.Name) and exc.id == "ValueError":
            return True
    return False


def _source_text(path: Path, node: ast.AST) -> str:
    source = path.read_text(encoding="utf-8")
    return ast.get_source_segment(source, node) or ""


def _call_symbol(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _is_call_to(call: ast.Call, name: str) -> bool:
    return _call_symbol(call) == name


def _call_linenos(node: ast.AST, name: str) -> list[int]:
    return sorted(
        child.lineno
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and _is_call_to(child, name)
        and hasattr(child, "lineno")
    )


def _first_call_lineno(node: ast.AST, name: str) -> int | None:
    lines = _call_linenos(node, name)
    return lines[0] if lines else None


def _loads_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Name)
        and isinstance(child.ctx, ast.Load)
        and child.id == name
        for child in ast.walk(node)
    )


def _is_descendant_of(node: ast.AST, ancestor: ast.AST) -> bool:
    current = node
    while True:
        parent = getattr(current, "_p1_2_parent", None)
        if parent is None:
            return False
        if parent is ancestor:
            return True
        current = parent


def _node_in_statement_sequence(node: ast.AST, statements: Sequence[ast.stmt]) -> bool:
    return any(node is statement or _is_descendant_of(node, statement) for statement in statements)


def _atomic_write_json_calls(node: ast.AST) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and _is_call_to(child, "atomic_write_json")
    ]


def _atomic_write_target_name(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Name):
        return call.args[0].id
    if call.args and isinstance(call.args[0], ast.Attribute):
        return call.args[0].attr
    return None


def _atomic_write_target_expr(call: ast.Call) -> str | None:
    if not call.args:
        return None
    try:
        return ast.unparse(call.args[0])
    except Exception:
        return _atomic_write_target_name(call)


def _call_has_keyword_name(call: ast.Call, keyword_name: str, expected_name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        try:
            return ast.unparse(keyword.value) == expected_name
        except Exception:
            return isinstance(keyword.value, ast.Name) and keyword.value.id == expected_name
    return False


def _has_direct_call_with_keywords(
    node: ast.AST,
    function_name: str,
    expected_keywords: Mapping[str, str],
) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not _is_call_to(child, function_name):
            continue
        if all(
            _call_has_keyword_name(child, keyword_name, expected_name)
            for keyword_name, expected_name in expected_keywords.items()
        ):
            return True
    return False


def _has_staged_replace_call(
    node: ast.AST,
    *,
    staged_attr: str,
    target_name: str,
) -> bool:
    return _staged_replace_call_lineno(
        node,
        staged_attr=staged_attr,
        target_name=target_name,
    ) is not None


def _staged_replace_call_lineno(
    node: ast.AST,
    *,
    staged_attr: str,
    target_name: str,
) -> int | None:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "replace"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == staged_attr
        ):
            continue
        if len(child.args) == 1 and isinstance(child.args[0], ast.Name) and child.args[0].id == target_name:
            return child.lineno if hasattr(child, "lineno") else -1
    return None


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_call_to_name(node: ast.AST | None, name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


def _is_dict_campaign_state_call(node: ast.AST) -> bool:
    return (
        _is_call_to_name(node, "dict")
        and len(node.args) == 1
        and _is_name(node.args[0], "campaign_state")
    )


def _call_keyword_is_false(call: ast.Call, keyword_name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return isinstance(keyword.value, ast.Constant) and keyword.value.value is False
    return False


def _snapshot_helper_uses_json_roundtrip(snapshot_fn: ast.FunctionDef) -> bool:
    has_json_dump = False
    has_strict_load = False
    has_return_copy = False
    for child in ast.walk(snapshot_fn):
        if isinstance(child, ast.Call):
            if (
                isinstance(child.func, ast.Attribute)
                and child.func.attr == "dumps"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "json"
                and child.args
                and _is_dict_campaign_state_call(child.args[0])
                and _call_keyword_is_false(child, "allow_nan")
            ):
                has_json_dump = True
            if (
                _is_call_to(child, "_loads_strict_json_object")
                and len(child.args) == 1
                and _is_name(child.args[0], "snapshot_bytes")
            ):
                has_strict_load = True
        if (
            isinstance(child, ast.Return)
            and _is_call_to_name(child.value, "dict")
            and len(child.value.args) == 1
            and _is_name(child.value.args[0], "snapshot")
        ):
            has_return_copy = True
    return has_json_dump and has_strict_load and has_return_copy


def _handler_catches_all_exceptions(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
        return True
    return isinstance(handler.type, ast.Attribute) and handler.type.attr == "Exception"


def _handler_raises(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(child, ast.Raise) for child in ast.walk(handler))


def _publisher_production_scan_paths(project_root: Path) -> list[Path]:
    paths: list[Path] = []
    for root_rel in ("src", "scripts"):
        root = project_root / root_rel
        if not root.exists():
            continue
        candidates = root.rglob("*.py") if root.is_dir() else [root]
        for path in candidates:
            rel_path = path.relative_to(project_root).as_posix()
            if (
                rel_path.startswith("src/tests/")
                or "/__pycache__/" in rel_path
                or rel_path.endswith("/__init__.py")
            ):
                continue
            paths.append(path)
    return paths


def _enclosing_function_name(node: ast.AST) -> str:
    current = node
    function_name: str | None = None
    class_name: str | None = None
    while True:
        parent = getattr(current, "_p1_2_parent", None)
        if parent is None:
            break
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and function_name is None:
            function_name = parent.name
        elif isinstance(parent, ast.ClassDef) and class_name is None:
            class_name = parent.name
        current = parent
    if function_name is None:
        return "<module>"
    if class_name is not None:
        return f"{class_name}.{function_name}"
    return function_name


def _publisher_direct_call_sites(
    *,
    project_root: Path,
    scan_paths: Sequence[Path] | None = None,
) -> set[tuple[str, str]]:
    call_sites: set[tuple[str, str]] = set()
    for path in scan_paths or _publisher_production_scan_paths(project_root):
        try:
            tree = _parse_python(path)
        except CheckError:
            raise
        for child in ast.walk(tree):
            if isinstance(child, ast.Call) and _is_call_to(
                child,
                "publish_verified_certified_delivery_surface",
            ):
                call_sites.add((path.relative_to(project_root).as_posix(), _enclosing_function_name(child)))
    return call_sites


def _check_publisher_transaction_shape(
    publisher_fn: ast.FunctionDef,
    *,
    path: Path,
) -> list[str]:
    errors: list[str] = []
    module_tree = _ast_root(publisher_fn)
    if not isinstance(module_tree, ast.Module):
        return ["verified publisher AST root is not a module"]

    top_level_tries = [statement for statement in publisher_fn.body if isinstance(statement, ast.Try)]
    if len(top_level_tries) != 1:
        errors.append("verified publisher must wrap canonical publication in one top-level try/except rollback block")
        return errors
    transaction_try = top_level_tries[0]

    if _atomic_write_json_calls(publisher_fn):
        errors.append("verified publisher must not write canonical artifacts directly; writes must be staged")

    for required_call in (
        "evaluate_certified_delivery_surface",
        "clear_certified_delivery_surface_artifacts",
        "_load_strict_json_mapping",
        "_mapping_or_none",
        "_json_equivalent",
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        "resolve_p1_2_publish_open_gate",
        "blueprint_output_path",
        "delivery_manifest_output_path",
        "_stage_verified_certified_delivery_surface_artifacts",
        "_commit_staged_certified_delivery_surface_artifacts",
        "verify_certified_delivery_surface",
    ):
        if not _direct_calls_name(transaction_try, required_call):
            errors.append(f"verified publisher transaction missing reachable call: {required_call}")

    stage_line = _first_call_lineno(transaction_try, "_stage_verified_certified_delivery_surface_artifacts")
    commit_line = _first_call_lineno(transaction_try, "_commit_staged_certified_delivery_surface_artifacts")
    verify_line = _first_call_lineno(transaction_try, "verify_certified_delivery_surface")
    if stage_line is None or commit_line is None or verify_line is None:
        errors.append("verified publisher must stage, atomically commit, then verify the final surface")
    elif not stage_line < commit_line < verify_line:
        errors.append("verified publisher transaction order must be stage -> commit -> final verifier")

    gate_lines = _call_linenos(transaction_try, "resolve_p1_2_publish_open_gate")
    if len(gate_lines) < 2:
        errors.append("verified publisher must check the publish-open gate before staging and before commit")
    else:
        if stage_line is not None and not any(line < stage_line for line in gate_lines):
            errors.append("verified publisher must check the publish-open gate before staging")
        if (
            stage_line is not None
            and commit_line is not None
            and not any(stage_line < line < commit_line for line in gate_lines)
        ):
            errors.append("verified publisher must recheck the publish-open gate before commit")
        if commit_line is not None and gate_lines[-1] > commit_line:
            errors.append("verified publisher final publish-open gate check must dominate commit")

    rollback_handlers = [
        handler for handler in transaction_try.handlers if _handler_catches_all_exceptions(handler)
    ]
    if not rollback_handlers:
        errors.append("verified publisher rollback must catch Exception for the full publication block")
    for handler in rollback_handlers:
        if not (
            _direct_calls_name(handler, "_restore_certified_delivery_surface_backup")
            and _direct_calls_name(handler, "clear_certified_delivery_surface_artifacts")
        ):
            errors.append("verified publisher rollback handler must restore backed-up artifacts or clear stale artifacts")
        if not _handler_raises(handler):
            errors.append("verified publisher rollback handler must re-raise a fail-closed exception")
    if not _direct_calls_name(transaction_try, "_cleanup_certified_delivery_surface_temp_dirs"):
        errors.append("verified publisher transaction must cleanup staging directories in finally")
    if not _direct_calls_name(transaction_try, "_discard_certified_delivery_surface_backup"):
        errors.append("verified publisher transaction must discard backups only after final verification")

    stage_fn = _function_def(
        module_tree,
        "_stage_verified_certified_delivery_surface_artifacts",
        path=path,
    )
    stage_writes = _atomic_write_json_calls(stage_fn)
    stage_targets = {_atomic_write_target_expr(call) for call in stage_writes}
    expected_stage_targets = {
        "staged.final_solution_path",
        "staged.blueprint_path",
        "staged.manifest_path",
    }
    if len(stage_writes) != 3 or stage_targets != expected_stage_targets:
        errors.append("staged publisher must write exactly final_solution, blueprint, and manifest stage files through staged paths")
    for required_call in (
        "build_blueprint_payload_from_certified_result",
        "build_certified_delivery_manifest",
        "validate_certified_delivery_manifest_matches_campaign",
    ):
        if not _direct_calls_name(stage_fn, required_call):
            errors.append(f"staged publisher missing manifest/currentness call: {required_call}")
    for function_name in (
        "build_certified_delivery_manifest",
        "validate_certified_delivery_manifest_matches_campaign",
    ):
        if not _has_direct_call_with_keywords(
            stage_fn,
            function_name,
            {
                "final_solution_artifact_path": "staged.final_solution_path",
                "optimal_blueprint_artifact_path": "staged.blueprint_path",
            },
        ):
            errors.append(
                "staged publisher must bind manifest validation to staged artifact bytes: "
                f"{function_name}"
            )

    commit_fn = _function_def(
        module_tree,
        "_commit_staged_certified_delivery_surface_artifacts",
        path=path,
    )
    replace_lines: dict[str, int] = {}
    for staged_attr, target_name in (
        ("final_solution_path", "final_solution_path"),
        ("blueprint_path", "blueprint_path"),
        ("manifest_path", "manifest_path"),
    ):
        replace_line = _staged_replace_call_lineno(
            commit_fn,
            staged_attr=staged_attr,
            target_name=target_name,
        )
        if replace_line is None:
            errors.append(f"verified publisher commit must atomically replace {target_name} from staged bytes")
        else:
            replace_lines[target_name] = replace_line
    manifest_replace_line = replace_lines.get("manifest_path")
    if manifest_replace_line is not None and any(
        replace_lines.get(target_name, manifest_replace_line) > manifest_replace_line
        for target_name in ("final_solution_path", "blueprint_path")
    ):
        errors.append("verified publisher commit must replace the manifest last")
    if not _direct_calls_name(commit_fn, "_prepare_certified_delivery_surface_backup"):
        errors.append("verified publisher commit must prepare rollback backups before replace")
    if not _direct_calls_name(commit_fn, "_restore_certified_delivery_surface_backup"):
        errors.append("verified publisher commit must rollback staged replace failure")

    publisher_source = _source_text(path, publisher_fn)
    if "surface.publishable" not in publisher_source:
        errors.append("verified publisher must reject non-publishable post-write surface verification")
    return errors


def _check_manifest_mapping_snapshot_shape(
    delivery_manifest_path: Path,
) -> list[str]:
    errors: list[str] = []
    delivery_tree = _parse_python(delivery_manifest_path)
    snapshot_fn = _function_def(
        delivery_tree,
        "_snapshot_manifest_campaign_state",
        path=delivery_manifest_path,
    )
    if not _snapshot_helper_uses_json_roundtrip(snapshot_fn):
        errors.append(
            "manifest Mapping snapshot helper must isolate caller payload via "
            "json.dumps(dict(campaign_state), allow_nan=False), "
            "_loads_strict_json_object(snapshot_bytes), and return dict(snapshot)"
        )

    build_fn = _function_def(
        delivery_tree,
        "build_certified_delivery_manifest",
        path=delivery_manifest_path,
    )
    snapshot_statement_index: int | None = None
    for index, statement in enumerate(build_fn.body):
        if not isinstance(statement, ast.Assign):
            continue
        if len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        value = statement.value
        if not (
            isinstance(target, ast.Name)
            and target.id == "campaign_state"
            and isinstance(value, ast.Call)
            and _is_call_to(value, "_snapshot_manifest_campaign_state")
            and len(value.args) == 1
            and isinstance(value.args[0], ast.Name)
            and value.args[0].id == "campaign_state"
        ):
            continue
        snapshot_statement_index = index
        break
    if snapshot_statement_index is None:
        errors.append("certified delivery manifest must assign campaign_state from one snapshot call")
        return errors
    for statement in build_fn.body[:snapshot_statement_index]:
        if _loads_name(statement, "campaign_state"):
            errors.append("certified delivery manifest must not read caller campaign_state before snapshot")
            break
    snapshot_line = build_fn.body[snapshot_statement_index].lineno
    best_line = _first_call_lineno(build_fn, "_build_best_certified_result_payload")
    for required_call in (
        "has_certified_export_surface",
        "_canonical_disk_campaign_state_if_regular",
        "_validate_campaign_state_matches_disk_authority",
    ):
        call_line = _first_call_lineno(build_fn, required_call)
        if call_line is None or call_line <= snapshot_line:
            errors.append(
                "certified delivery manifest must snapshot caller Mapping before disk/certification gate: "
                f"{required_call}"
            )
        if best_line is not None and call_line is not None and call_line >= best_line:
            errors.append(
                "certified delivery manifest must finish disk-authority gating before best-result build: "
                f"{required_call}"
            )
    return errors


def _check_certified_publication_boundary_contract(
    *,
    project_root: Path = PROJECT_ROOT,
    certified_surface_path: Path = CERTIFIED_SURFACE_PATH,
    delivery_manifest_path: Path = DELIVERY_MANIFEST_PATH,
    publisher_scan_paths: Sequence[Path] | None = None,
) -> list[str]:
    """Check PR1 public publication reachability, rollback, and Mapping snapshot guards."""

    errors: list[str] = []
    surface_tree = _parse_python(certified_surface_path)
    publisher_fn = _function_def(
        surface_tree,
        "publish_verified_certified_delivery_surface",
        path=certified_surface_path,
    )
    errors.extend(_check_publisher_transaction_shape(publisher_fn, path=certified_surface_path))

    allowed_writer_functions = {
        "publish_verified_certified_delivery_surface",
        "_stage_verified_certified_delivery_surface_artifacts",
        "export_and_verify_certified_delivery_manifest",
    }
    for node in ast.walk(surface_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in allowed_writer_functions:
            continue
        if _atomic_write_json_calls(node):
            errors.append(
                "certified surface raw canonical writer bypass is not allowed outside "
                f"the verified publisher: {node.name}"
            )

    allowed_call_sites = {
        ("src/search/certified_surface.py", "save_certified_final_solution_and_blueprint"),
        ("scripts/export_industrial_planner_bundle.py", "main"),
    }
    actual_call_sites = _publisher_direct_call_sites(
        project_root=project_root,
        scan_paths=publisher_scan_paths,
    )
    unexpected_call_sites = actual_call_sites - allowed_call_sites
    for rel_path, function_name in sorted(unexpected_call_sites):
        errors.append(
            "publish_verified_certified_delivery_surface has an unsealed production caller: "
            f"{rel_path}::{function_name}"
        )
    missing_call_sites = allowed_call_sites - actual_call_sites
    for rel_path, function_name in sorted(missing_call_sites):
        if (project_root / rel_path).exists():
            errors.append(
                "publish_verified_certified_delivery_surface lost sealed production caller: "
                f"{rel_path}::{function_name}"
            )

    errors.extend(_check_manifest_mapping_snapshot_shape(delivery_manifest_path))
    return errors


def _uses_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _function_returns_status_tuple(node: ast.FunctionDef, status_name: str) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Return) or not isinstance(child.value, ast.Tuple):
            continue
        if not child.value.elts:
            continue
        status_expr = child.value.elts[0]
        if isinstance(status_expr, ast.Name) and status_expr.id == status_name:
            return True
    return False


def _uses_constant(node: ast.AST, value: str) -> bool:
    return any(isinstance(child, ast.Constant) and child.value == value for child in ast.walk(node))


def _argv_string_marker(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(value.value for value in node.values if isinstance(value, ast.Constant) and isinstance(value.value, str))
    return None


def _subprocess_run_argv_nodes(node: ast.AST) -> list[list[ast.AST]]:
    argv_nodes: list[list[ast.AST]] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not (
            isinstance(child.func, ast.Attribute)
            and child.func.attr == "run"
            and child.args
            and isinstance(child.args[0], ast.List)
        ):
            continue
        argv_nodes.append(list(child.args[0].elts))
    return argv_nodes


def _argv_index(markers: Sequence[str | None], value: str) -> int:
    try:
        return list(markers).index(value)
    except ValueError:
        return -1


def _contains_sys_executable(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Attribute)
        and child.attr == "executable"
        and isinstance(child.value, ast.Name)
        and child.value.id == "sys"
        for child in ast.walk(node)
    )


def _assigned_sys_executable_names(function: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(function):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if value is None or not _contains_sys_executable(value):
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _uses_name_in_expr(node: ast.AST, names: set[str]) -> bool:
    return any(isinstance(child, ast.Name) and child.id in names for child in ast.walk(node))


def _mkdtemp_target_names(function: ast.FunctionDef, *, label: str, errors: list[str]) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(function):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "mkdtemp"
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "tempfile"
        ):
            continue
        if any(keyword.arg == "dir" for keyword in value.keywords):
            errors.append(f"{label} pycache prefix tempfile must not be rooted in the repository")
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _joined_str_has_pycache_prefix_from_name(node: ast.AST, names: set[str]) -> bool:
    if not isinstance(node, ast.JoinedStr):
        return False
    has_prefix = any(
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and "pycache_prefix=" in value.value
        for value in node.values
    )
    has_temp_name = any(
        isinstance(value, ast.FormattedValue)
        and isinstance(value.value, ast.Name)
        and value.value.id in names
        for value in node.values
    )
    return has_prefix and has_temp_name


def _has_rmtree_cleanup_for_name(function: ast.FunctionDef, names: set[str]) -> bool:
    for child in ast.walk(function):
        if not (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "rmtree"
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "shutil"
            and child.args
            and isinstance(child.args[0], ast.Name)
            and child.args[0].id in names
        ):
            continue
        if any(
            keyword.arg == "ignore_errors"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in child.keywords
        ):
            return True
    return False


def _check_isolated_pycache_hardened_argv(
    *,
    function: ast.FunctionDef,
    path: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    source = _source_text(path, function)
    required_tokens = (
        '"-I"',
        '"-B"',
        '"-X"',
        "pycache_prefix=",
        "tempfile.mkdtemp",
        "shutil.rmtree",
        "ignore_errors=True",
    )
    for token in required_tokens:
        if token not in source:
            errors.append(f"{label} isolated subprocess missing PYC-EXEC-DIGEST hardening token: {token}")
    forbidden_env_prefix_forms = (
        'env["PYTHONPYCACHEPREFIX"]',
        "env['PYTHONPYCACHEPREFIX']",
        '"PYTHONPYCACHEPREFIX":',
        "'PYTHONPYCACHEPREFIX':",
        "os.environ",
    )
    if any(form in source for form in forbidden_env_prefix_forms):
        errors.append(f"{label} isolated subprocess must not rely on PYTHONPYCACHEPREFIX under -I")
    if "dir=source_root" in source or "dir=project_root" in source:
        errors.append(f"{label} pycache prefix must be a per-run tempfile, not a repository path")

    argv_nodes = _subprocess_run_argv_nodes(function)
    if len(argv_nodes) != 1:
        errors.append(f"{label} must have exactly one direct subprocess.run argv list")
        return errors
    sys_executable_names = _assigned_sys_executable_names(function)
    if not (
        _contains_sys_executable(argv_nodes[0][0])
        or _uses_name_in_expr(argv_nodes[0][0], sys_executable_names)
    ):
        errors.append(f"{label} argv executable must be derived from sys.executable")
    mkdtemp_names = _mkdtemp_target_names(function, label=label, errors=errors)
    if not mkdtemp_names:
        errors.append(f"{label} pycache prefix must come from tempfile.mkdtemp")
    elif not _has_rmtree_cleanup_for_name(function, mkdtemp_names):
        errors.append(f"{label} pycache prefix tempfile must be cleaned with shutil.rmtree(ignore_errors=True)")
    markers = [_argv_string_marker(element) for element in argv_nodes[0]]
    isolated_index = _argv_index(markers, "-I")
    no_bytecode_index = _argv_index(markers, "-B")
    x_index = _argv_index(markers, "-X")
    pycache_index = next(
        (
            index
            for index, marker in enumerate(markers)
            if isinstance(marker, str) and marker.startswith("pycache_prefix=")
        ),
        -1,
    )
    if min(isolated_index, no_bytecode_index, x_index, pycache_index) < 0:
        errors.append(f"{label} argv must contain -I, -B, -X, and pycache_prefix=<dir>")
    elif not (
        isolated_index < no_bytecode_index < x_index
        and pycache_index == x_index + 1
    ):
        errors.append(f"{label} argv must order hardening as -I -B -X pycache_prefix=<dir>")
    elif mkdtemp_names and not _joined_str_has_pycache_prefix_from_name(argv_nodes[0][pycache_index], mkdtemp_names):
        errors.append(f"{label} pycache_prefix argv must use the tempfile.mkdtemp directory")
    return errors


def _imports_lifecycle_constants() -> tuple[int, tuple[str, ...], tuple[str, ...], dict[str, tuple[str, ...]]]:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.cuts.lifecycle import (  # pylint: disable=import-outside-toplevel
        SOURCE_DIGEST_FIELD_NAMES,
        SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH,
        SOURCE_DIGEST_SCHEMA_VERSION,
        STEP_7_EVALUATION_GUARD_OBLIGATIONS,
    )

    runtime_cache_keys = {
        ".".join(path): tuple(sorted(keys)) for path, keys in SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH.items()
    }
    return (
        SOURCE_DIGEST_SCHEMA_VERSION,
        tuple(SOURCE_DIGEST_FIELD_NAMES),
        tuple(STEP_7_EVALUATION_GUARD_OBLIGATIONS),
        runtime_cache_keys,
    )


def _test_symbols() -> set[str]:
    symbols: set[str] = set()
    for path in TEST_ROOT.rglob("test_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            raise CheckError(f"cannot parse test file {_rel(path)}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                symbols.add(node.name)
    return symbols


def _check_step7_contract(manifest: dict[str, Any], tree: ast.Module) -> list[str]:
    errors: list[str] = []
    contract = manifest.get("step_7_contract")
    if not isinstance(contract, dict):
        return ["step_7_contract must be an object"]

    decision_name = _require_str(contract.get("decision_function"), "step_7_contract.decision_function")
    canonical_name = _require_str(
        contract.get("canonical_transition_function"),
        "step_7_contract.canonical_transition_function",
    )
    bool_guard_name = _require_str(
        contract.get("boolean_guard_function"),
        "step_7_contract.boolean_guard_function",
    )

    decision_fn = _function_def(tree, decision_name)
    bool_guard_fn = _function_def(tree, bool_guard_name)
    step7_fn = _function_def(tree, "step_7_evaluate_cut")
    literal_fn = _function_def(tree, "evaluate_literal_multiset")

    if not _calls_function(decision_fn, canonical_name):
        errors.append(f"{decision_name} must call {canonical_name}")
    if not _calls_function(bool_guard_fn, decision_name):
        errors.append(f"{bool_guard_name} must delegate to {decision_name}")
    if not _calls_function(step7_fn, bool_guard_name):
        errors.append(f"step_7_evaluate_cut must call {bool_guard_name}")
    if not _calls_function(literal_fn, bool_guard_name):
        errors.append(f"evaluate_literal_multiset must call {bool_guard_name}")
    return errors


def _uses_dunder_prefix_skip(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not isinstance(func, ast.Attribute) or func.attr != "startswith":
            continue
        if not child.args:
            continue
        arg = child.args[0]
        if isinstance(arg, ast.Constant) and arg.value == "__":
            return True
    return False


def _assigns_name(tree: ast.Module, name: str) -> bool:
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return True
    return False


def _assignment_source(tree: ast.Module, name: str, *, path: Path) -> str:
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return _source_text(path, node)
    raise CheckError(f"assignment not found in {_rel(path)}: {name}")


def _calls_id_on_candidate_placements(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Name) or child.func.id != "id":
            continue
        if child.args and isinstance(child.args[0], ast.Name) and child.args[0].id in {"cp", "candidate_placements"}:
            return True
    return False


def _check_runtime_cache_policy(manifest: dict[str, Any], lifecycle_tree: ast.Module) -> list[str]:
    errors: list[str] = []
    source_contract = manifest.get("source_digest_contract")
    if not isinstance(source_contract, dict):
        return ["source_digest_contract must be an object"]

    _, _, _, code_cache_keys = _imports_lifecycle_constants()
    manifest_cache_raw = source_contract.get("runtime_cache_keys_by_path")
    if not isinstance(manifest_cache_raw, dict):
        errors.append("source_digest_contract.runtime_cache_keys_by_path must be an object")
    else:
        manifest_cache_keys: dict[str, tuple[str, ...]] = {}
        for raw_path, raw_keys in manifest_cache_raw.items():
            path = _require_str(raw_path, "source_digest_contract.runtime_cache_keys_by_path key")
            keys = tuple(sorted(str(key) for key in _require_list(raw_keys, f"runtime cache keys for {path}")))
            manifest_cache_keys[path] = keys
        if manifest_cache_keys != code_cache_keys:
            errors.append(
                "source_digest_contract.runtime_cache_keys_by_path disagrees with "
                "SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH: "
                f"manifest={manifest_cache_keys!r}, code={code_cache_keys!r}"
            )

    source_jsonable_fn = _function_def(lifecycle_tree, "_source_jsonable")
    if _uses_dunder_prefix_skip(source_jsonable_fn):
        errors.append("_source_jsonable must not ignore every key with startswith('__')")

    candidate_tree = _parse_python(CANDIDATE_PLACEMENTS_PATH)
    cache_jsonable_fn = _function_def(
        candidate_tree,
        "_cache_jsonable",
        path=CANDIDATE_PLACEMENTS_PATH,
    )
    if _uses_dunder_prefix_skip(cache_jsonable_fn):
        errors.append("_cache_jsonable must not ignore schema-valid facility pool keys with startswith('__')")

    find_pose_fn = _function_def(
        candidate_tree,
        "find_pose",
        path=CANDIDATE_PLACEMENTS_PATH,
    )
    if _assigns_name(candidate_tree, "_POSE_CACHE_BY_CP_ID"):
        errors.append("candidate placement runtime cache must not be keyed by candidate_placements object id")
    if _calls_id_on_candidate_placements(find_pose_fn):
        errors.append("find_pose must not key runtime cache by id(candidate_placements)")
    return errors


def _check_source_digest_contract(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_contract = manifest.get("source_digest_contract")
    if not isinstance(source_contract, dict):
        return ["source_digest_contract must be an object"]

    schema_version, field_names, guard_obligations, _ = _imports_lifecycle_constants()
    manifest_schema = source_contract.get("schema_version")
    if manifest_schema != schema_version:
        errors.append(
            "source_digest_contract.schema_version disagrees with "
            f"SOURCE_DIGEST_SCHEMA_VERSION: manifest={manifest_schema!r}, code={schema_version!r}"
        )
    manifest_fields = tuple(
        str(item) for item in _require_list(source_contract.get("fields"), "source_digest_contract.fields")
    )
    if manifest_fields != field_names:
        errors.append(
            "source_digest_contract.fields disagree with SOURCE_DIGEST_FIELD_NAMES: "
            f"manifest={manifest_fields!r}, code={field_names!r}"
        )

    contract = manifest.get("step_7_contract")
    if isinstance(contract, dict):
        manifest_obligations = tuple(
            str(item) for item in _require_list(contract.get("guard_obligations"), "step_7_contract.guard_obligations")
        )
        if manifest_obligations != guard_obligations:
            errors.append(
                "step_7_contract.guard_obligations disagree with "
                "STEP_7_EVALUATION_GUARD_OBLIGATIONS: "
                f"manifest={manifest_obligations!r}, code={guard_obligations!r}"
            )
    return errors


def _check_source_digest_uses_contract(tree: ast.Module) -> list[str]:
    errors: list[str] = []
    _function_def(tree, "source_digest_payload")
    compute_fn = _function_def(tree, "compute_source_digest")
    if not _calls_function(compute_fn, "source_digest_payload"):
        errors.append("compute_source_digest must hash source_digest_payload(state)")
    return errors


def _check_evidence_and_tests(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    test_symbols = _test_symbols()
    obligations = _require_list(manifest.get("obligations"), "obligations")
    if not obligations:
        errors.append("obligations must not be empty")
        return errors

    seen_ids: set[str] = set()
    listed_tests_by_obligation: dict[str, set[str]] = {}
    for index, raw_obligation in enumerate(obligations):
        if not isinstance(raw_obligation, dict):
            errors.append(f"obligations[{index}] must be an object")
            continue
        obligation_id = _require_str(raw_obligation.get("id"), f"obligations[{index}].id")
        if obligation_id in seen_ids:
            errors.append(f"duplicate obligation id: {obligation_id}")
        seen_ids.add(obligation_id)
        for raw_path in _require_list(raw_obligation.get("evidence_paths"), f"{obligation_id}.evidence_paths"):
            rel_path = _require_str(raw_path, f"{obligation_id}.evidence_paths[]")
            if not (PROJECT_ROOT / rel_path).exists():
                errors.append(f"{obligation_id} missing evidence path: {rel_path}")
        listed_tests: set[str] = set()
        for raw_test in _require_list(raw_obligation.get("required_tests"), f"{obligation_id}.required_tests"):
            test_name = _require_str(raw_test, f"{obligation_id}.required_tests[]")
            listed_tests.add(test_name)
            if test_name not in test_symbols:
                errors.append(f"{obligation_id} missing required test symbol: {test_name}")
        listed_tests_by_obligation[obligation_id] = listed_tests

    missing_obligation_ids = REQUIRED_OBLIGATION_IDS - seen_ids
    for obligation_id in sorted(missing_obligation_ids):
        errors.append(f"missing required obligation id: {obligation_id}")

    for obligation_id, required_tests in sorted(REQUIRED_TESTS_BY_OBLIGATION_ID.items()):
        if obligation_id not in seen_ids:
            continue
        missing_tests = required_tests - listed_tests_by_obligation.get(obligation_id, set())
        for test_name in sorted(missing_tests):
            errors.append(f"{obligation_id} omits required regression test: {test_name}")
    return errors


def _check_close_kernel_checker_self_binding(*, checker_path: Path = Path(__file__).resolve()) -> list[str]:
    """Fail closed if the proof-obligation checker stops invoking its close-kernel.

    The checker source is itself a registered proof-bearing sink.  This
    lightweight AST guard catches the specific mutation where a later edit
    removes the close-kernel or phase-anchor call before that same call would
    have a chance to notice source hash drift.
    """
    errors: list[str] = []
    tree = _parse_python(checker_path)
    main_fn = _function_def(tree, "main", path=checker_path)
    for required_call in (
        "_check_candidate_sink_replay_contract",
        "_check_certified_publication_boundary_contract",
        "_check_strong_status_write_allowlist_gate",
        "_check_close_kernel_contract",
        "_check_phase_gate_provenance_contract",
        "_check_phase_anchor",
        "_check_exact_session_atomic_snapshot_contract",
        "_check_independent_infeasibility_reverifier_contract",
    ):
        if not _calls_function(main_fn, required_call):
            errors.append(f"proof-obligation checker main must call {required_call}")
    return errors


def _check_strong_status_write_allowlist_gate() -> list[str]:
    script_path = PROJECT_ROOT / "scripts" / "check_strong_status_write_allowlist.py"
    pycache_prefix = tempfile.mkdtemp(prefix="zmd_strong_status_allowlist_pycache_")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                f"pycache_prefix={pycache_prefix}",
                str(script_path),
                "--root",
                str(PROJECT_ROOT),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return [f"strong-status write allowlist checker failed to run: {type(exc).__name__}: {exc}"]
    finally:
        shutil.rmtree(pycache_prefix, ignore_errors=True)
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        if len(detail) > 1000:
            detail = detail[:1000] + "..."
        return [f"strong-status write allowlist checker failed: {detail}"]
    return []



def _check_candidate_sink_replay_contract(
    *,
    candidate_replay_path: Path = CANDIDATE_PROOF_REPLAY_PATH,
    exact_campaign_path: Path = EXACT_CAMPAIGN_PATH,
    certified_frontier_path: Path = CERTIFIED_FRONTIER_PATH,
    outer_search_path: Path = OUTER_SEARCH_PATH,
    delivery_manifest_path: Path = DELIVERY_MANIFEST_PATH,
    certified_surface_path: Path = CERTIFIED_SURFACE_PATH,
    test_support_path: Path = VERIFIED_PRODUCER_TEST_SUPPORT_PATH,
) -> list[str]:
    """Seal the P1.2 strong-status authority at sink-side isolated replay.

    Source hashes detect drift, but hashes alone do not prove that the authority
    boundary still exists.  These AST/source guards require each certified sink
    to consume data-only replay requests through a fresh ``python -I`` child that
    recomputes project/source artifacts and runs the certified_exact solver.  No
    writer identity, closure, module symbol, test helper, or process-local
    freshness registry is accepted as proof authority.
    """

    errors: list[str] = []
    replay_tree = _parse_python(candidate_replay_path)
    replay_source = candidate_replay_path.read_text(encoding="utf-8")
    for function_name in (
        "build_candidate_replay_proof",
        "candidate_proof_shape_violation",
        "verify_candidate_records_at_sink",
        "project_candidate_records_for_sink",
        "_invoke_isolated_replay",
        "_replay_response_violation",
        "_validate_child_proof",
        "_replay_one_proof",
        "_materialize_replay_snapshot",
        "_execute_isolated_replay_request",
        "isolated_replay_main",
    ):
        _function_def(replay_tree, function_name, path=candidate_replay_path)

    for token in (
        "CANDIDATE_PROOF_AUTHORITY",
        "certified_exact_isolated_solver_replay_v1",
        "candidate_sink_replay_proof_missing",
        "candidate_sink_replay_status_mismatch",
        "candidate_sink_replay_invocation_failed",
        "candidate_sink_replay_artifact_binding_mismatch",
        "candidate_sink_replay_source_binding_mismatch",
        "candidate_sink_replay_project_binding_mismatch",
        "candidate_sink_replay_campaign_binding_mismatch",
        "campaign_context_digest",
        "solution_digest",
        "request_digest",
    ):
        if token not in replay_source:
            errors.append(f"candidate replay authority is missing fail-closed token: {token}")

    invoke_fn = _function_def(replay_tree, "_invoke_isolated_replay", path=candidate_replay_path)
    invoke_source = _source_text(candidate_replay_path, invoke_fn)
    if not _calls_attr(invoke_fn, "run"):
        errors.append("candidate replay must launch an external subprocess")
    for token in (
        '"-I"',
        "_ISOLATED_REPLAY_BOOTSTRAP",
        "nonce",
        "expected_proofs",
        '"PATH"',
        "os.defpath",
        "check=False",
    ):
        if token not in invoke_source:
            errors.append(f"candidate replay subprocess boundary missing: {token}")
    if "shell=True" in invoke_source:
        errors.append("candidate replay subprocess must never use shell=True")
    if "os.environ" in invoke_source:
        errors.append("candidate replay subprocess must not inherit producer environment state")
    for inherited_loader_state in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        if inherited_loader_state in invoke_source:
            errors.append(
                "candidate replay subprocess must not inherit Python loader state: "
                f"{inherited_loader_state}"
            )

    verify_fn = _function_def(
        replay_tree,
        "verify_candidate_records_at_sink",
        path=candidate_replay_path,
    )
    for required_call in (
        "candidate_proof_shape_violation",
        "_invoke_isolated_replay",
        "_replay_response_violation",
    ):
        if not _calls_function(verify_fn, required_call):
            errors.append(f"sink candidate verifier must call {required_call}")
    verify_source = _source_text(candidate_replay_path, verify_fn)
    for token in ("replay_status != claimed_status", "candidate_sink_replay_status_mismatch"):
        if token not in verify_source:
            errors.append(f"sink candidate verifier must compare replayed strong status: {token}")

    project_fn = _function_def(
        replay_tree,
        "project_candidate_records_for_sink",
        path=candidate_replay_path,
    )
    project_source = _source_text(candidate_replay_path, project_fn)
    if not _calls_function(project_fn, "verify_candidate_records_at_sink"):
        errors.append("sink projection must call verify_candidate_records_at_sink")
    for token in (
        'record["status"] = "UNPROVEN"',
        'record.pop("solution", None)',
        "record.pop(CANDIDATE_PROOF_FIELD, None)",
    ):
        if token not in project_source:
            errors.append(f"sink projection must demote rejected strong claims: {token}")

    snapshot_fn = _function_def(
        replay_tree,
        "_materialize_replay_snapshot",
        path=candidate_replay_path,
    )
    snapshot_source = _source_text(candidate_replay_path, snapshot_fn)
    if not _calls_attr(snapshot_fn, "copyfile"):
        errors.append("isolated replay must copy hash-bound project inputs into a snapshot")
    if not _calls_function(snapshot_fn, "compute_exact_artifact_hashes"):
        errors.append("isolated replay snapshot must recompute exact artifact hashes")
    for token in (
        "follow_symlinks=False",
        "normalized_replay_hashes != normalized_current_hashes",
        "replay snapshot artifact binding mismatch",
    ):
        if token not in snapshot_source:
            errors.append(f"isolated replay snapshot binding is missing: {token}")

    child_request_fn = _function_def(
        replay_tree,
        "_execute_isolated_replay_request",
        path=candidate_replay_path,
    )
    child_request_source = _source_text(candidate_replay_path, child_request_fn)
    for token in (
        "compute_exact_artifact_hashes",
        "create_exact_search_session",
        'solve_mode="certified_exact"',
        "current_artifact_hashes",
        "TemporaryDirectory",
        "_materialize_replay_snapshot",
        "replay_project_root",
    ):
        if token not in child_request_source:
            errors.append(f"isolated child must recompute exact proof context: {token}")

    replay_one_fn = _function_def(replay_tree, "_replay_one_proof", path=candidate_replay_path)
    replay_one_source = _source_text(candidate_replay_path, replay_one_fn)
    if not _calls_function(replay_one_fn, "run_benders_for_ghost_rect"):
        errors.append("isolated child must replay via run_benders_for_ghost_rect")
    for token in (
        'solve_mode="certified_exact"',
        "campaign=None",
        "preloaded_exact_safe_cuts=[]",
        "disable_master_warm_start=True",
    ):
        if token not in replay_one_source:
            errors.append(f"isolated solver replay is missing fixed certified configuration: {token}")

    child_proof_fn = _function_def(
        replay_tree,
        "_validate_child_proof",
        path=candidate_replay_path,
    )
    child_proof_source = _source_text(candidate_replay_path, child_proof_fn)
    for token in (
        "project_binding",
        "artifact_hashes",
        "source_digest",
        "campaign_context",
        "campaign_context_digest",
        "solution_digest",
        "replay_config",
    ):
        if token not in child_proof_source:
            errors.append(f"isolated child proof validator is missing binding: {token}")

    exact_tree = _parse_python(exact_campaign_path)
    exact_source = exact_campaign_path.read_text(encoding="utf-8")
    terminal_wrapper_fn = _function_def(
        exact_tree,
        "terminal_certified_final_result_violation_for_project",
        path=exact_campaign_path,
    )
    terminal_wrapper_source = _source_text(exact_campaign_path, terminal_wrapper_fn)
    for token in (
        "authority_bytes = authority_path.read_bytes()",
        "bytes(serialized_state_bytes) != authority_bytes",
        "loads_strict_json",
        "_terminal_certified_final_result_violation_for_project_authority",
    ):
        if token not in terminal_wrapper_source:
            errors.append(f"terminal project validator wrapper is missing disk authority guard: {token}")
    terminal_fn = _function_def(
        exact_tree,
        "_terminal_certified_final_result_violation_for_project_authority",
        path=exact_campaign_path,
    )
    terminal_source = _source_text(exact_campaign_path, terminal_fn)
    if not _calls_function(terminal_fn, "project_candidate_records_for_sink"):
        errors.append("terminal project validator must execute candidate sink replay")
    if not _calls_function_with_keyword_constant(
        terminal_fn,
        "project_candidate_records_for_sink",
        "require_record_solution_match",
        True,
    ):
        errors.append(
            "terminal project validator must preserve the digest-bound stored witness after status replay"
        )
    for token in (
        "terminal_candidate_sink_replay_failed",
        "candidate_records_override=replayed_records",
        "authority_state",
        "authority_bytes",
        "_supervisor_seal_state_violation",
    ):
        if token not in terminal_source:
            errors.append(f"terminal project validator is missing replay guard: {token}")
    exact_class = _class_def(exact_tree, "ExactCampaign", path=exact_campaign_path)
    writer_fn = _method_def(
        exact_class,
        "_mark_candidate_result_from_verified_producer",
        path=exact_campaign_path,
    )
    if not _calls_attr(writer_fn, "mark_candidate_result"):
        errors.append("compatibility candidate writer must only delegate to mark_candidate_result")
    writer_source = _source_text(exact_campaign_path, writer_fn)
    if "sys._getframe" in writer_source or "__closure__" in writer_source:
        errors.append("candidate writer must not derive authority from caller/function identity")
    for forbidden in (
        "FreshProofBearingCandidateRecord",
        "_grant_candidate_status_freshness_from_verified_producer",
        "_build_candidate_freshness_runtime",
        "_bind_verified_candidate_producer",
        "_bind_verified_candidate_writer",
        "proof_bearing_candidate_status_freshness_violation",
        "terminal_proof_bearing_candidate_freshness_violation",
    ):
        if forbidden in exact_source:
            errors.append(f"process-local writer/freshness authority must remain absent: {forbidden}")

    frontier_tree = _parse_python(certified_frontier_path)
    frontier_replay_modes = {
        "compute_sink_verified_terminal_frontier_projection": False,
        "build_sink_verified_terminal_frontier_evidence": True,
    }
    for function_name, preserve_stored_witness in frontier_replay_modes.items():
        function = _function_def(frontier_tree, function_name, path=certified_frontier_path)
        if not _calls_function(function, "project_candidate_records_for_sink"):
            errors.append(f"{function_name} must execute project_candidate_records_for_sink")
        if not _calls_function_with_keyword_constant(
            function,
            "project_candidate_records_for_sink",
            "require_record_solution_match",
            preserve_stored_witness,
        ):
            errors.append(
                f"{function_name} has the wrong replay witness policy: "
                f"require_record_solution_match={preserve_stored_witness}"
            )

    outer_tree = _parse_python(outer_search_path)
    frontier_state_fn = _function_def(outer_tree, "_compute_exact_frontier_state", path=outer_search_path)
    if not _calls_function(frontier_state_fn, "compute_sink_verified_terminal_frontier_projection"):
        errors.append("frontier pruning must use sink-verified candidate projection")
    frontier_state_source = _source_text(outer_search_path, frontier_state_fn)
    if 'campaign.state["candidates"] = candidate_records' not in frontier_state_source:
        errors.append(
            "frontier must adopt replay demotions/rebindings before candidate lifecycle decisions"
        )
    run_outer_fn = _function_def(outer_tree, "run_outer_search", path=outer_search_path)
    if not _calls_function(run_outer_fn, "build_candidate_replay_proof"):
        errors.append("certified outer search must call build_candidate_replay_proof")
    for call in (node for node in ast.walk(run_outer_fn) if isinstance(node, ast.Call)):
        is_verified_writer = (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "_mark_candidate_result_from_verified_producer"
        )
        is_selected_writer = isinstance(call.func, ast.Name) and call.func.id == "candidate_result_writer"
        if (is_verified_writer or is_selected_writer) and not any(
            keyword.arg == "candidate_proof" for keyword in call.keywords
        ):
            errors.append(
                "every certified outer-search strong-status writer must carry a data-only candidate_proof request"
            )
    commit_fn = _function_def(
        outer_tree,
        "_commit_terminal_full_frontier_certified_result",
        path=outer_search_path,
    )
    commit_source = _source_text(outer_search_path, commit_fn)
    load_proposal_fn = _method_def(
        exact_class,
        "_load_supervisor_proposal_authority",
        path=exact_campaign_path,
    )
    load_proposal_source = _source_text(exact_campaign_path, load_proposal_fn)
    if not _calls_function(load_proposal_fn, "load_proposal_ready_marker"):
        errors.append("supervisor seal authority loader must read proposal_ready marker")
    for token in (
        "self.path.read_bytes()",
        "checkpoint_sha256",
        "CANDIDATE_PROPOSED_STATUS",
        "_proposal_state_violation",
        "run_id",
    ):
        if token not in load_proposal_source:
            errors.append(f"supervisor seal authority loader must bind checkpoint bytes: {token}")
    seal_fn = _method_def(exact_class, "supervisor_seal", path=exact_campaign_path)
    seal_source = _source_text(exact_campaign_path, seal_fn)
    forbidden_seal_authority_args = {
        "final_result",
        "terminal_frontier_evidence",
        "candidate_records",
    }
    seal_arg_names = {
        arg.arg
        for arg in [*seal_fn.args.args, *seal_fn.args.kwonlyargs]
    }
    for forbidden_arg in sorted(forbidden_seal_authority_args & seal_arg_names):
        errors.append(f"supervisor_seal must not accept caller authority argument: {forbidden_arg}")
    if not _calls_function(seal_fn, "run_l0_supervisor_seal"):
        errors.append("supervisor_seal must delegate terminal mint authority to PR2 L0")
    for token in (
        "L0SupervisorSealRequest",
        "self.proposal_ready_marker_path",
        "expected_campaign_instance_id",
        "PR2_L0_SEALED",
    ):
        if token not in seal_source:
            errors.append(f"supervisor_seal must bind the PR2 L0 request: {token}")
    if "campaign_path=None" in seal_source:
        errors.append("supervisor_seal must not validate terminal evidence with campaign_path=None")
    if "_save_supervisor_certified_state" in exact_source:
        errors.append("supervisor certified checkpoint writer must not be exposed as a method/helper")

    l0_tree = _parse_python(PR2_L0_MICRO_VERIFIER_PATH)
    l0_seal_fn = _function_def(
        l0_tree,
        "run_l0_supervisor_seal",
        path=PR2_L0_MICRO_VERIFIER_PATH,
    )
    l0_seal_source = _source_text(PR2_L0_MICRO_VERIFIER_PATH, l0_seal_fn)
    for required_call in (
        "_load_canonical_dependency_floor_manifest",
        "_read_regular_file_bytes",
        "_proposal_ready_marker_violation",
        "_proposal_authority_violation",
        "_strong_status_keys",
        "_strong_proof_binding_violation",
        "run_l0_micro_verifier_round_trip",
        "_domain_response_violation",
        "_checkpoint_write_lock_l0",
        "_atomic_replace_bytes",
        "_postwrite_state_violation",
    ):
        if not _calls_function(l0_seal_fn, required_call):
            errors.append(f"PR2 L0 supervisor seal must call {required_call}")
    for token in (
        "marker_bytes = _read_regular_file_bytes(marker_path)",
        "checkpoint_bytes = _read_regular_file_bytes(campaign_path)",
        "checkpoint_sha256",
        '"authority_state_b64": base64.b64encode(checkpoint_bytes)',
        '"proposal_final_result_digest": _canonical_digest(certified_final_result)',
        '"proposal_candidate_records_digest": _canonical_digest',
        "verifier_module=TRUE_VERIFIER_MODULE",
        "extra_snapshot_modules=_discover_project_snapshot_modules(source_root)",
        '"transition": "proposal_to_certified_v1"',
        '"proposal_authority_b64"',
        "certified_state_sha256",
        "pending_state_bytes",
        "current_marker_bytes = _read_regular_file_bytes(marker_path)",
        "current_checkpoint_bytes = _read_regular_file_bytes(campaign_path)",
        "_atomic_replace_bytes(campaign_path, checkpoint_bytes)",
        "write_isolation",
        '"third_party_native": "NAMED-TCB"',
    ):
        if token not in l0_seal_source:
            errors.append(f"PR2 L0 supervisor seal must bind and atomically validate P->Q authority: {token}")

    child_tree = _parse_python(PR2_L0_TRUE_VERIFIER_CHILD_PATH)
    child_domain_fn = _function_def(
        child_tree,
        "_verify_supervisor_domain",
        path=PR2_L0_TRUE_VERIFIER_CHILD_PATH,
    )
    child_domain_source = _source_text(PR2_L0_TRUE_VERIFIER_CHILD_PATH, child_domain_fn)
    for required_call in (
        "_project_candidate_records_direct",
        "_run_fixed_witness_direct",
        "build_terminal_frontier_evidence",
        "terminal_certified_final_result_project_precheck_violation",
    ):
        if not _calls_function(child_domain_fn, required_call):
            errors.append(f"PR2 true verifier child domain path must call {required_call}")
    for token in (
        "authority_state_b64",
        "terminal candidate sink replay failed",
        "terminal fixed witness verifier failed",
        "proposal_final_result_digest",
        "proposal_terminal_frontier_evidence_digest",
        "proposal_candidate_records_digest",
        '"sink_replay_violations": {}',
        '"fixed_witness_violations": {}',
        '"third_party_native": "NAMED-TCB"',
        "windows_write_isolation_residual",
    ):
        if token not in child_domain_source:
            errors.append(f"PR2 true verifier child must fail closed and report bounded domain evidence: {token}")
    child_project_fn = _function_def(
        child_tree,
        "_project_candidate_records_direct",
        path=PR2_L0_TRUE_VERIFIER_CHILD_PATH,
    )
    child_project_source = _source_text(PR2_L0_TRUE_VERIFIER_CHILD_PATH, child_project_fn)
    for required_call in (
        "candidate_proof_shape_violation",
        "_execute_isolated_replay_request",
        "_replay_response_violation",
    ):
        if not _calls_function(child_project_fn, required_call):
            errors.append(f"PR2 child candidate projection must call {required_call}")
    for token in (
        "set(expected_proofs) | set(violations) != set(strong_keys)",
        "candidate_sink_replay_strong_key_coverage_mismatch",
        "replay_status != claimed_status",
        "candidate_sink_replay_status_mismatch",
    ):
        if token not in child_project_source:
            errors.append(f"PR2 child candidate projection must enforce exact strong-key coverage: {token}")
    seal_state_fn = _function_def(
        exact_tree,
        "_supervisor_seal_state_violation",
        path=exact_campaign_path,
    )
    seal_state_source = _source_text(exact_campaign_path, seal_state_fn)
    for token in (
        "_load_sealed_proposal_authority",
        "_supervisor_certified_transition_violation",
        "proposal_to_certified_v1",
    ):
        if token not in seal_state_source:
            errors.append(f"supervisor seal validator must recheck proposal authority bytes: {token}")
    load_sealed_fn = _function_def(
        exact_tree,
        "_load_sealed_proposal_authority",
        path=exact_campaign_path,
    )
    load_sealed_source = _source_text(exact_campaign_path, load_sealed_fn)
    for token in (
        "proposal_authority_b64",
        "base64.b64decode",
        "proposal_checkpoint_sha256",
        "loads_strict_json",
    ):
        if token not in load_sealed_source:
            errors.append(f"supervisor seal proposal authority decoder missing token: {token}")
    transition_fn = _function_def(
        exact_tree,
        "_supervisor_certified_transition_violation",
        path=exact_campaign_path,
    )
    transition_source = _source_text(exact_campaign_path, transition_fn)
    for token in (
        "CANDIDATE_PROPOSED_STATUS",
        "_final_result_certified_transition",
        "canonical_state_bytes_for_fixed_witness(expected)",
        "SUPERVISOR_PROPOSAL_STATE_KEY",
    ):
        if token not in transition_source:
            errors.append(f"supervisor P->Q transition gate missing token: {token}")
    precommit_fn = _method_def(
        exact_class,
        "_validate_supervisor_certified_state_before_commit",
        path=exact_campaign_path,
    )
    precommit_source = _source_text(exact_campaign_path, precommit_fn)
    for forbidden in ("TemporaryDirectory", "NamedTemporaryFile", "tempfile"):
        if forbidden in precommit_source:
            errors.append("supervisor precommit validator must not bind final validation to temp checkpoint paths")
    for token in (
        "loads_strict_json(bytes(authority_bytes).decode",
        "campaign_path=self.path",
        "authority_bytes=bytes(authority_bytes)",
    ):
        if token not in precommit_source:
            errors.append(f"supervisor precommit validator must use canonical campaign path and pending bytes: {token}")
    best_fn = _method_def(exact_class, "best_certified_result", path=exact_campaign_path)
    best_source = _source_text(exact_campaign_path, best_fn)
    for token in (
        "evaluate_certified_delivery_surface",
        "campaign_state=None",
        "if not surface.publishable",
    ):
        if token not in best_source:
            errors.append(f"best_certified_result must require central publishable disk surface: {token}")

    surface_tree = _parse_python(certified_surface_path)
    certified_surface_source_text = certified_surface_path.read_text(encoding="utf-8")
    if "_write_certified_final_solution_and_blueprint_unchecked" in certified_surface_source_text:
        errors.append("certified surface must not expose an importable unchecked canonical writer")
    evaluate_surface_fn = _function_def(
        surface_tree,
        "evaluate_certified_delivery_surface",
        path=certified_surface_path,
    )
    evaluate_surface_source = _source_text(certified_surface_path, evaluate_surface_fn)
    for token in (
        "_load_verified_surface_snapshot",
        "final_solution_payload",
        "optimal_blueprint_payload",
    ):
        if token not in evaluate_surface_source:
            errors.append(f"certified surface must return verified snapshot payloads: {token}")
    publisher_fn = _function_def(
        surface_tree,
        "publish_verified_certified_delivery_surface",
        path=certified_surface_path,
    )
    errors.extend(_check_publisher_transaction_shape(publisher_fn, path=certified_surface_path))
    if _direct_calls_name(publisher_fn, "export_certified_delivery_manifest"):
        errors.append("verified publisher must own canonical writes directly, not delegate to export_certified_delivery_manifest")
    if _direct_calls_name(publisher_fn, "write_blueprint_payload"):
        errors.append("verified publisher must own canonical writes directly, not delegate to write_blueprint_payload")
    manifest_export_fn = _function_def(
        surface_tree,
        "export_and_verify_certified_delivery_manifest",
        path=certified_surface_path,
    )
    manifest_export_source = _source_text(certified_surface_path, manifest_export_fn)
    for token in (
        "build_certified_delivery_manifest",
        "publishable certified delivery manifests must use",
        "publish_verified_certified_delivery_surface",
        "atomic_write_json(manifest_path, payload)",
    ):
        if token not in manifest_export_source:
            errors.append(f"non-publisher manifest export must fail closed on publishable payloads: {token}")
    if "export_certified_delivery_manifest" in manifest_export_source:
        errors.append("non-publisher manifest export must not call the generic manifest writer")
    if not _calls_function(run_outer_fn, "_commit_terminal_full_frontier_certified_result"):
        errors.append("certified outer search must use the terminal proposal commit")
    if _function_returns_status_tuple(run_outer_fn, "RUN_STATUS_CERTIFIED"):
        errors.append("certified outer search producer must not return public CERTIFIED terminal status")
    if not _function_returns_status_tuple(run_outer_fn, "CANDIDATE_PROPOSED_STATUS"):
        errors.append("certified outer search producer must return CANDIDATE_PROPOSED terminal status")
    for token in (
        "CANDIDATE_PROPOSED_STATUS",
        "set_supervisor_proposal_run_id",
        "write_proposal_ready_marker",
        "terminal_frontier_evidence",
    ):
        if token not in commit_source:
            errors.append(f"terminal proposal commit must preserve supervisor handoff: {token}")
    for token in ("sink_replay_violations", "terminal candidate sink replay failed"):
        if token not in child_domain_source:
            errors.append(f"PR2 true verifier child must fail closed on replay rejection: {token}")

    delivery_tree = _parse_python(delivery_manifest_path)
    delivery_build_fn = _function_def(
        delivery_tree,
        "build_certified_delivery_manifest",
        path=delivery_manifest_path,
    )
    best_payload_fn = _function_def(
        delivery_tree,
        "_build_best_certified_result_payload",
        path=delivery_manifest_path,
    )
    if not _calls_function(delivery_build_fn, "terminal_certified_final_result_violation_for_project"):
        errors.append("delivery manifest must call project-bound terminal replay validator")
    if not _calls_function(best_payload_fn, "has_valid_terminal_full_frontier_certified_evidence_for_project"):
        errors.append("delivery manifest best result must call project-bound terminal replay validator")
    for function in (delivery_build_fn, best_payload_fn):
        if "campaign_path=" not in _source_text(delivery_manifest_path, function):
            errors.append("delivery manifest replay validation must bind campaign_path")

    surface_tree = _parse_python(certified_surface_path)
    surface_fn = _function_def(
        surface_tree,
        "evaluate_certified_delivery_surface",
        path=certified_surface_path,
    )
    surface_source = _source_text(certified_surface_path, surface_fn)
    if not _calls_function(surface_fn, "has_valid_terminal_full_frontier_certified_evidence_for_project"):
        errors.append("public certified surface must call project-bound terminal replay validator")
    if not _calls_function(surface_fn, "resolve_p1_2_publish_open_gate"):
        errors.append("public certified surface must consult P1.2 publish open-gate")
    if "campaign_path=resolved_campaign_path" not in surface_source:
        errors.append("public certified surface replay validation must bind canonical campaign_path")

    helper_source = test_support_path.read_text(encoding="utf-8")
    if "build_candidate_replay_proof" not in helper_source:
        errors.append("test candidate helper must only attach replay-request data")
    for forbidden in (
        "monkeypatch",
        "setattr(",
        "_grant_candidate_status_freshness_from_verified_producer",
        "_bind_verified_candidate_producer",
        "_bind_verified_candidate_writer",
    ):
        if forbidden in helper_source:
            errors.append(f"test candidate helper must not grant production authority: {forbidden}")
    return errors


def _check_isolated_exec_bytecode_binding_contract(
    *,
    candidate_replay_path: Path = CANDIDATE_PROOF_REPLAY_PATH,
    terminal_capsule_path: Path = TERMINAL_FIXED_WITNESS_CAPSULE_PATH,
) -> list[str]:
    """Require certified isolated replay children to execute source-derived bytecode.

    ``python -I`` removes PYTHON* environment influence but still reads valid
    repository ``__pycache__`` files.  PYC-EXEC-DIGEST closes that by adding
    ``-B`` and command-line ``-X pycache_prefix=<per-run tempfile>`` to every
    certified authority child so bytecode lookup misses repo caches and compiles
    from the ``.py`` source already covered by the certified source digest.
    """

    errors: list[str] = []
    replay_tree = _parse_python(candidate_replay_path)
    replay_invoke = _function_def(
        replay_tree,
        "_invoke_isolated_replay",
        path=candidate_replay_path,
    )
    errors.extend(
        _check_isolated_pycache_hardened_argv(
            function=replay_invoke,
            path=candidate_replay_path,
            label="candidate replay",
        )
    )

    capsule_tree = _parse_python(terminal_capsule_path)
    capsule_invoke = _function_def(
        capsule_tree,
        "_invoke_isolated_capsule",
        path=terminal_capsule_path,
    )
    errors.extend(
        _check_isolated_pycache_hardened_argv(
            function=capsule_invoke,
            path=terminal_capsule_path,
            label="fixed-witness capsule",
        )
    )
    return errors


def _check_phase_gate_provenance_contract() -> list[str]:
    """Check that the phase gate is now a small manual fail-closed gate.

    V37-V50 showed that parsing receipts, prose reports, package metadata, and
    Git authority had become a separate security protocol.  The proof-obligation
    gate now anchors the opposite contract: P1.3B can only be opened by an owner
    manual decision; receipts are informational and the repository does not
    derive clean-review count.
    """
    errors: list[str] = []
    tree = _parse_python(PHASE_GATE_SCRIPT_PATH)

    for required_symbol in (
        "_check_manual_review_standard",
        "_check_owner_manual_state",
        "_check_owner_manual_decision",
        "_step_8_apply_to_master_is_fail_closed",
        "_check_step_8_boundary",
        "_check_fixed_witness_close_binding",
        "_fixed_witness_verifier_functions_present",
        "_fixed_witness_verifier_semantics_errors",
        "_fixed_witness_capsule_semantics_errors",
        "check_gate",
    ):
        _function_def(tree, required_symbol, path=PHASE_GATE_SCRIPT_PATH)

    check_gate_fn = _function_def(tree, "check_gate", path=PHASE_GATE_SCRIPT_PATH)
    for required_call in (
        "_check_manual_review_standard",
        "_check_owner_manual_state",
        "_check_owner_manual_decision",
        "_check_step_8_boundary",
        "_check_fixed_witness_close_binding",
    ):
        if not _calls_function(check_gate_fn, required_call):
            errors.append(f"manual phase gate check_gate must call {required_call}")

    fixed_witness_binding_fn = _function_def(
        tree, "_check_fixed_witness_close_binding", path=PHASE_GATE_SCRIPT_PATH
    )
    if not _calls_function(fixed_witness_binding_fn, "_fixed_witness_verifier_functions_present"):
        errors.append(
            "manual phase gate close binding must consult the fixed-witness verifier presence check"
        )
    presence_fn = _function_def(
        tree, "_fixed_witness_verifier_functions_present", path=PHASE_GATE_SCRIPT_PATH
    )
    if not _uses_name(presence_fn, "FIXED_WITNESS_VERIFIER_PATH"):
        errors.append(
            "fixed-witness verifier presence check must read FIXED_WITNESS_VERIFIER_PATH"
        )
    if not _uses_name(presence_fn, "FIXED_WITNESS_CAPSULE_PATH"):
        errors.append(
            "fixed-witness verifier presence check must read FIXED_WITNESS_CAPSULE_PATH"
        )
    for required_call in (
        "_fixed_witness_verifier_semantics_errors",
        "_fixed_witness_capsule_semantics_errors",
    ):
        if not _calls_function(presence_fn, required_call):
            errors.append(f"fixed-witness close binding must call {required_call}")
    if not _uses_name(check_gate_fn, "APPROVED_REVIEW_ANCHOR"):
        errors.append("manual phase gate check_gate must require the approved review anchor")

    manual_standard_fn = _function_def(tree, "_check_manual_review_standard", path=PHASE_GATE_SCRIPT_PATH)
    if not (_uses_constant(manual_standard_fn, "owner_manual_count_outside_repo") or _uses_name(manual_standard_fn, "COUNTING_AUTHORITY")):
        errors.append("manual review standard must require owner_manual_count_outside_repo")
    if not (_uses_constant(manual_standard_fn, "informational_record_only") or _uses_name(manual_standard_fn, "RECEIPT_ROLE")):
        errors.append("manual review standard must require informational receipt role")

    step8_boundary_fn = _function_def(tree, "_check_step_8_boundary", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(step8_boundary_fn, "_step_8_apply_to_master_is_fail_closed"):
        errors.append("manual phase gate must verify step_8 remains fail-closed while blocked")

    forbidden_symbols = (
        "_validate_clean_review_receipt",
        "_validate_current_review_package",
        "_extract_evidence_metadata",
        "_project_git_head",
    )
    for symbol in forbidden_symbols:
        try:
            _function_def(tree, symbol, path=PHASE_GATE_SCRIPT_PATH)
        except CheckError:
            continue
        errors.append(f"manual phase gate should not retain automatic authority parser: {symbol}")
    return errors


def _check_certified_cut_replay_contract(manifest: dict[str, Any]) -> list[str]:
    """Anchor the V53-V56 certified-cut replay faithful-encoding contract.

    This is intentionally structural.  V53-V56 showed that a persisted
    exact-safe Benders cut is only safe if every handoff in the replay chain is
    fail-closed: strict payload parsing, resume validation, all-or-nothing
    conflict member resolution, one-to-one member-to-literal encoding, and
    register/count only after master application succeeds.
    """

    errors: list[str] = []
    contract = manifest.get("certified_cut_replay_contract")
    if not isinstance(contract, dict):
        return ["certified_cut_replay_contract must be an object"]

    for raw_path in _require_list(contract.get("backend_scope"), "certified_cut_replay_contract.backend_scope"):
        rel_path = _require_str(raw_path, "certified_cut_replay_contract.backend_scope[]")
        if not (PROJECT_ROOT / rel_path).exists():
            errors.append(f"certified replay backend scope path missing: {rel_path}")

    cut_manager_tree = _parse_python(CUT_MANAGER_PATH)
    benders_cut_class = _class_def(cut_manager_tree, "BendersCut", path=CUT_MANAGER_PATH)
    from_dict_fn = _method_def(benders_cut_class, "from_dict", path=CUT_MANAGER_PATH)
    to_dict_fn = _method_def(benders_cut_class, "to_dict", path=CUT_MANAGER_PATH)
    cut_manager_class = _class_def(cut_manager_tree, "CutManager", path=CUT_MANAGER_PATH)
    load_fn = _method_def(cut_manager_class, "load", path=CUT_MANAGER_PATH)

    for helper_name in (
        "_strict_int",
        "_strict_bool",
        "_strict_int_mapping",
        "_loads_strict_json_object",
        "_reject_json_constant",
        "_cut_requires_condition_set",
        "_parse_canonical_nonnegative_coord",
        "_parse_ghost_anchor_condition_key",
        "_validate_certified_condition_shape",
        "_validate_condition_required_power_metadata",
        "_validate_certified_condition_requirement",
    ):
        _function_def(cut_manager_tree, helper_name, path=CUT_MANAGER_PATH)
    strict_int_fn = _function_def(cut_manager_tree, "_strict_int", path=CUT_MANAGER_PATH)
    strict_bool_fn = _function_def(cut_manager_tree, "_strict_bool", path=CUT_MANAGER_PATH)
    strict_json_fn = _function_def(cut_manager_tree, "_loads_strict_json_object", path=CUT_MANAGER_PATH)
    parse_coord_fn = _function_def(
        cut_manager_tree,
        "_parse_canonical_nonnegative_coord",
        path=CUT_MANAGER_PATH,
    )
    parse_condition_key_fn = _function_def(
        cut_manager_tree,
        "_parse_ghost_anchor_condition_key",
        path=CUT_MANAGER_PATH,
    )
    condition_shape_fn = _function_def(
        cut_manager_tree,
        "_validate_certified_condition_shape",
        path=CUT_MANAGER_PATH,
    )
    condition_metadata_fn = _function_def(
        cut_manager_tree,
        "_validate_condition_required_power_metadata",
        path=CUT_MANAGER_PATH,
    )
    if not (_uses_name(strict_int_fn, "bool") and _raises_value_error(strict_int_fn)):
        errors.append("_strict_int must reject bool-as-int certified replay payloads")
    if not (_uses_name(strict_bool_fn, "bool") and _raises_value_error(strict_bool_fn)):
        errors.append("_strict_bool must reject truthy/falsy non-bool exact_safe payloads")
    if "parse_constant" not in _source_text(CUT_MANAGER_PATH, strict_json_fn):
        errors.append("CutManager strict JSON loader must reject NaN/Infinity constants")
    parse_coord_source = _source_text(CUT_MANAGER_PATH, parse_coord_fn)
    for needle in (
        'startswith("0")',
        '"0" <= char <= "9"',
        "MAX_GHOST_ANCHOR_CONDITION_COORD",
    ):
        if needle not in parse_coord_source:
            errors.append(f"condition_set coordinate parser must enforce canonical non-negative decimal token: {needle}")
    parse_condition_key_source = _source_text(CUT_MANAGER_PATH, parse_condition_key_fn)
    if "GHOST_ANCHOR_CONDITION_PREFIX" not in parse_condition_key_source or "len(parts) != 2" not in parse_condition_key_source:
        errors.append("condition_set ghost anchors must use a strict ghost_anchor::(x,y) parser")
    if "_parse_canonical_nonnegative_coord" not in parse_condition_key_source:
        errors.append("condition_set ghost anchors must reject whitespace, sign, underscore, negative, and overflow-like coordinates")
    if ".strip" in parse_condition_key_source or "int(parts" in parse_condition_key_source:
        errors.append("condition_set ghost anchor parser must not normalize malformed coordinate keys")
    condition_shape_source = _source_text(CUT_MANAGER_PATH, condition_shape_fn)
    if "_parse_ghost_anchor_condition_key" not in condition_shape_source or "rect_idx" not in condition_shape_source:
        errors.append("certified condition_set payloads must reject unsupported or malformed condition anchors")
    condition_metadata_source = _source_text(CUT_MANAGER_PATH, condition_metadata_fn)
    for needle in (
        "len(condition_set) != 1",
        "metadata.ghost_rect_idx",
        "metadata.ghost_anchor",
        "_parse_ghost_anchor_condition_key",
    ):
        if needle not in condition_metadata_source:
            errors.append(f"condition-required power cuts must validate {needle}")
    for fn_name, fn in (("BendersCut.from_dict", from_dict_fn), ("BendersCut.to_dict", to_dict_fn)):
        for helper_name in ("_strict_bool", "_strict_int", "_strict_int_mapping"):
            if not _calls_function(fn, helper_name):
                errors.append(f"{fn_name} must call {helper_name}")
        if not _calls_function(fn, "_validate_certified_condition_requirement"):
            errors.append(f"{fn_name} must enforce certified condition requirements")
    if not _calls_function(load_fn, "_loads_strict_json_object"):
        errors.append("CutManager.load must use strict JSON duplicate-key rejection")

    exact_campaign_tree = _parse_python(EXACT_CAMPAIGN_PATH)
    exact_campaign_strict_json_fn = _function_def(exact_campaign_tree, "_loads_strict_json_object", path=EXACT_CAMPAIGN_PATH)
    _function_def(exact_campaign_tree, "_reject_json_constant", path=EXACT_CAMPAIGN_PATH)
    if "parse_constant" not in _source_text(EXACT_CAMPAIGN_PATH, exact_campaign_strict_json_fn):
        errors.append("ExactCampaign strict JSON loader must reject NaN/Infinity constants")
    for helper_name in (
        "_load_exact_grid_dimensions",
        "_strict_candidate_ghost_rect",
        "_expected_unfiltered_ghost_anchor_index",
        "_validate_cut_condition_domain",
        "_default_master_domain_contract",
        "_validate_master_domain_contract",
    ):
        _function_def(exact_campaign_tree, helper_name, path=EXACT_CAMPAIGN_PATH)
    validate_record_fn = _function_def(exact_campaign_tree, "_validate_candidate_record", path=EXACT_CAMPAIGN_PATH)
    validate_source = _source_text(EXACT_CAMPAIGN_PATH, validate_record_fn)
    if "BendersCut.from_dict" not in validate_source:
        errors.append("ExactCampaign resume validation must parse every exact_safe_cut with BendersCut.from_dict")
    if "cut.exact_safe is not True" not in validate_source:
        errors.append("ExactCampaign resume validation must require cut.exact_safe is True, not truthy")
    if "_validate_cut_condition_domain" not in validate_source:
        errors.append("ExactCampaign resume validation must reject condition_set keys that cannot resolve in the candidate ghost domain")
    resume_fn = _function_def(exact_campaign_tree, "_validate_resume_state", path=EXACT_CAMPAIGN_PATH)
    resume_source = _source_text(EXACT_CAMPAIGN_PATH, resume_fn)
    if "_load_exact_grid_dimensions" not in resume_source or "project_root" not in resume_source:
        errors.append("ExactCampaign resume validation must load current grid dimensions for condition resolver support checks")
    if "_validate_master_domain_contract" not in resume_source:
        errors.append("ExactCampaign resume validation must reject restricted or missing master domain contracts")
    exact_campaign_source = EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8")
    pr2_l0_source = PR2_L0_MICRO_VERIFIER_PATH.read_text(encoding="utf-8")
    pr2_child_source = PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(encoding="utf-8")
    if "master_domain_contract" not in exact_campaign_source:
        errors.append("ExactCampaign state must persist an explicit full master-domain contract")
    for needle in (
        '_strict_resume_int(state.get("schema_version")',
        'state.get("proof_summary_schema_version")',
        "declare_mode",
        "final_result_declare_mode_not_strict",
        "final_result_requires_strict_declare_mode",
    ):
        if needle not in exact_campaign_source:
            errors.append(f"ExactCampaign resume/final evidence contract must fail closed on non-strict or non-strictly-typed state: {needle}")

    outer_tree = _parse_python(OUTER_SEARCH_PATH)
    run_outer_fn = _function_def(outer_tree, "run_outer_search", path=OUTER_SEARCH_PATH)
    run_outer_source = _source_text(OUTER_SEARCH_PATH, run_outer_fn)
    outer_source = OUTER_SEARCH_PATH.read_text(encoding="utf-8")
    for needle in (
        "EXACT_OUTER_SKIP_UNKNOWN_ENV",
        "outer_skip_unknown_not_certified",
        "_certified_outer_skip_unknown_blocker",
    ):
        if needle not in outer_source:
            errors.append(
                "certified outer search must define a fail-closed UNKNOWN-skip blocker: "
                f"{needle}"
            )
    for needle in (
        "_outer_skip_unknown_enabled()",
        "_certified_outer_skip_unknown_blocker",
        "mark_campaign_stopped",
        "RUN_STATUS_UNPROVEN",
        "terminal_certified_export_failed",
    ):
        if needle not in run_outer_source:
            errors.append(
                "certified outer search must fail closed before candidate subset/best-effort evidence: "
                f"{needle}"
            )
    mark_blocked_fn = _function_def(
        outer_tree,
        "_mark_certified_campaign_blocked",
        path=OUTER_SEARCH_PATH,
    )
    mark_blocked_source = _source_text(OUTER_SEARCH_PATH, mark_blocked_fn)
    for needle in (
        "_clear_certified_delivery_solution_artifacts",
        "_refresh_certified_delivery_manifest_if_any",
        "RUN_STATUS_UNPROVEN",
        "save_error",
        "cleanup_error",
    ):
        if needle not in mark_blocked_source:
            errors.append(
                "certified outer blocker paths must purge stale certified-looking "
                f"delivery artifacts and refresh the manifest: {needle}"
            )
    clear_artifacts_fn = _function_def(
        outer_tree,
        "_clear_certified_delivery_solution_artifacts",
        path=OUTER_SEARCH_PATH,
    )
    clear_artifacts_source = _source_text(OUTER_SEARCH_PATH, clear_artifacts_fn)
    certified_surface_tree = _parse_python(CERTIFIED_SURFACE_PATH)
    certified_surface_source_text = CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
    # V97: the certified surface must pin the publishing authority to the
    # canonical in-project checkpoint and reject non-canonical shadow paths.
    if "campaign_state_path_not_canonical" not in certified_surface_source_text:
        errors.append(
            "certified surface must reject a non-canonical campaign checkpoint "
            "authority: campaign_state_path_not_canonical"
        )
    clear_surface_fn = _function_def(
        certified_surface_tree,
        "clear_certified_delivery_surface_artifacts",
        path=CERTIFIED_SURFACE_PATH,
    )
    clear_surface_source = _source_text(CERTIFIED_SURFACE_PATH, clear_surface_fn)
    if "clear_certified_delivery_surface_artifacts" not in clear_artifacts_source:
        errors.append(
            "certified outer blocker artifact purge must delegate to the central "
            "certified surface artifact cleanup helper"
        )
    for needle in (
        '"final_solution.json"',
        "blueprint_output_path",
        "delivery_manifest_output_path",
        ".unlink()",
    ):
        if (
            needle not in clear_artifacts_source
            and needle not in clear_surface_source
            and needle not in certified_surface_source_text
        ):
            errors.append(
                "certified outer blocker artifact purge must remove stale solution "
                f"surfaces through the central verifier module: {needle}"
            )

    delivery_manifest_tree = _parse_python(DELIVERY_MANIFEST_PATH)
    build_manifest_fn = _function_def(
        delivery_manifest_tree,
        "build_certified_delivery_manifest",
        path=DELIVERY_MANIFEST_PATH,
    )
    build_manifest_source = _source_text(DELIVERY_MANIFEST_PATH, build_manifest_fn)
    delivery_manifest_source_text = DELIVERY_MANIFEST_PATH.read_text(encoding="utf-8")
    for needle in ("declare_mode", "strict", "certified delivery manifest requires strict declare_mode"):
        if needle not in build_manifest_source:
            errors.append(
                "certified delivery manifest must reject non-strict final_result inheritance: "
                f"{needle}"
            )
    for needle in (
        "has_terminal_full_frontier_certified_evidence",
        "has_certified_export_surface",
        "certified delivery manifest requires exhausted strict candidate frontier",
        "certified delivery manifest requires terminal final_result evidence",
    ):
        if needle not in build_manifest_source and needle not in delivery_manifest_source_text:
            errors.append(
                "certified delivery manifest must share the terminal full-frontier evidence guard: "
                f"{needle}"
            )
    for needle in (
        "_validate_campaign_resume_compatible_with_current_artifacts",
        "validate_exact_campaign_resume_state",
        "compute_exact_artifact_hashes",
        "build_blueprint_payload_from_certified_result",
        "validate_certified_delivery_manifest_matches_campaign",
    ):
        if needle not in delivery_manifest_source_text:
            errors.append(
                "certified delivery manifest currentness must be structurally anchored to "
                f"campaign hash compatibility, canonical blueprint export, and manifest/artifact compare: {needle}"
            )
    for needle in (
        "_validate_campaign_state_matches_disk_authority",
        "_campaign_path_for_regular_file_check",
        "_snapshot_manifest_campaign_state(campaign_state)",
        "_canonical_disk_campaign_state_if_regular",
        "snapshot_has_certified_surface",
        "has_certified_export_surface(disk_campaign_state)",
        "campaign_state = _validate_campaign_state_matches_disk_authority",
        "disk checkpoint authority",
        "_is_regular_file(raw_state_path)",
        "_load_json_mapping(raw_state_path",
        "_json_equivalent(disk_payload, campaign_state)",
    ):
        if needle not in delivery_manifest_source_text:
            errors.append(
                "certified delivery manifest writer must treat the regular disk checkpoint as "
                f"authority before writing best_certified_result: {needle}"
            )
    snapshot_pos = build_manifest_source.find(
        "campaign_state = _snapshot_manifest_campaign_state(campaign_state)"
    )
    certified_surface_pos = build_manifest_source.find(
        "snapshot_has_certified_surface = has_certified_export_surface(campaign_state)"
    )
    best_payload_pos = build_manifest_source.find("best_result = _build_best_certified_result_payload")
    if snapshot_pos < 0 or certified_surface_pos < 0 or snapshot_pos > certified_surface_pos:
        errors.append("certified delivery manifest must snapshot caller Mapping before certification checks")
    if best_payload_pos >= 0 and certified_surface_pos >= 0 and best_payload_pos < certified_surface_pos:
        errors.append("certified delivery manifest must finish disk-authority gating before best-result build")
    for needle in (
        "_validate_certified_manifest_output_path",
        "direct certified delivery manifest writes",
        "canonical output path for best_certified_result",
        "regular canonical delivery manifest output",
        "publish_verified_certified_delivery_surface",
        "target_path.is_absolute()",
        "atomic_write_json(target_path, normalized)",
        "raw_output_path.parent.resolve().relative_to(project_root)",
    ):
        if needle not in delivery_manifest_source_text:
            errors.append(
                "certified delivery manifest writer must keep best_certified_result on the "
                f"canonical in-project manifest surface and block raw direct writers: {needle}"
            )
    if "allow_certified_payload" in delivery_manifest_source_text:
        errors.append(
            "certified delivery manifest raw writer must not expose a certified-payload override"
        )
    for needle in (
        "set(metadata.keys())",
        '"export_timestamp"',
        "raw_blueprint_payload",
        "_json_equivalent(raw_blueprint_payload, expected_blueprint)",
        "instance-shaped placement_solution",
    ):
        if needle not in delivery_manifest_source_text:
            errors.append(
                "certified delivery manifest must compare raw current artifacts and only exempt "
                f"the manifest export timestamp: {needle}"
            )

    serializer_source_text = SERIALIZER_PATH.read_text(encoding="utf-8")
    for needle in (
        "_routing_solution_from_result",
        "_coerce_routing_solution",
        '"routing_solution"',
        '"routing_network"',
        "blueprint-projectable routing_solution",
    ):
        if needle not in serializer_source_text:
            errors.append(
                "certified blueprint projection must fail closed on terminal routing results "
                f"that cannot be projected into optimal_blueprint: {needle}"
            )
    for needle in (
        "_is_canonical_blueprint_output_path",
        "canonical optimal_blueprint.json writes must use the verified certified publisher",
        "canonical certified blueprint writes must use the verified publisher",
    ):
        if needle not in serializer_source_text:
            errors.append(
                "generic blueprint writers must reject canonical optimal_blueprint.json writes: "
                f"{needle}"
            )
    blueprint_exporter_source_text = BLUEPRINT_EXPORTER_PATH.read_text(encoding="utf-8")
    for needle in (
        "write_blueprint_payload",
        "optimal_blueprint.json",
        "verified certified publisher",
    ):
        if needle not in blueprint_exporter_source_text:
            errors.append(
                "blueprint exporter must remain guarded by the canonical serializer writer: "
                f"{needle}"
            )

    for needle in (
        "CERTIFIED_SURFACE_VERIFIER_SOURCE",
        "evaluate_certified_delivery_surface",
        "verify_certified_delivery_surface",
        "_resolve_campaign_state_payload",
        "campaign_state_payload_mismatch",
        "delivery_manifest_payload_mismatch",
        "_load_strict_json_mapping",
        "_reject_duplicate_json_keys",
        "provided_exact_artifact_hashes_stale",
        "validate_delivery_artifacts_match_campaign",
        "validate_certified_delivery_manifest_matches_campaign",
        "has_valid_terminal_full_frontier_certified_evidence",
        "redact_certified_status",
        "redact_certified_stop_reason",
        "clear_certified_delivery_surface_artifacts",
        "export_and_verify_certified_delivery_manifest",
    ):
        if needle not in certified_surface_source_text:
            errors.append(
                "certified public surfaces must share the central verifier/cleanup/export gate: "
                f"{needle}"
            )

    resume_verifier_fn = _function_def(
        certified_surface_tree,
        "_resolve_resume_validation_reason",
        path=CERTIFIED_SURFACE_PATH,
    )
    resume_verifier_source = _source_text(CERTIFIED_SURFACE_PATH, resume_verifier_fn)
    if "campaign_resume_compatible is True" in resume_verifier_source:
        errors.append(
            "certified surface verifier must not trust caller-supplied resume-compatible=True; "
            "it must recompute exact artifact hashes before publishing CERTIFIED"
        )

    for needle in (
        "_reject_duplicate_json_keys",
        "_reject_json_constant",
        "_loads_strict_json_object",
        "strict readable JSON",
    ):
        if needle not in delivery_manifest_source_text:
            errors.append(
                "certified delivery artifact validation must use strict JSON loads for raw artifacts: "
                f"{needle}"
            )
    for needle in ("_reject_duplicate_json_keys", "_reject_json_constant"):
        if needle not in serializer_source_text:
            errors.append(
                "certified blueprint/candidate placement readers must reject duplicate keys and JSON constants: "
                f"{needle}"
            )

    inspector_tree = _parse_python(EXACT_CAMPAIGN_INSPECTOR_PATH)
    delivery_summary_fn = _function_def(
        inspector_tree,
        "_delivery_manifest_summary",
        path=EXACT_CAMPAIGN_INSPECTOR_PATH,
    )
    delivery_summary_source = _source_text(EXACT_CAMPAIGN_INSPECTOR_PATH, delivery_summary_fn)
    inspector_source_text = EXACT_CAMPAIGN_INSPECTOR_PATH.read_text(encoding="utf-8")
    for needle in (
        "validate_certified_delivery_manifest_matches_campaign",
        "campaign_resume_compatible",
        "has_valid_terminal_full_frontier_certified_evidence",
        "certified_delivery_current",
    ):
        if (
            needle not in delivery_summary_source
            and needle not in inspector_source_text
            and needle not in certified_surface_source_text
        ):
            errors.append(
                "campaign inspector manifest terminal predicate must be a current campaign + "
                f"current manifest + current artifact conjunction via the central certified surface verifier: {needle}"
            )

    exact_campaign_tree = _parse_python(EXACT_CAMPAIGN_PATH)
    resume_fn = _function_def(exact_campaign_tree, "_validate_resume_state", path=EXACT_CAMPAIGN_PATH)
    resume_source = _source_text(EXACT_CAMPAIGN_PATH, resume_fn)
    exact_campaign_source = EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8")
    for needle in (
        "has_terminal_full_frontier_certified_evidence",
        "certified_terminal_evidence_violation",
        "terminal_certified_frontier_evidence_invalid",
        "terminal_frontier_evidence",
        "terminal_frontier_evidence_violation",
        "_load_exact_safe_area_upper_bound",
        "_load_exact_min_side_admissibility",
        "safe_area_upper_bound",
        "min_side_admissibility",
        "terminal_certified_final_result_below_admissibility",
    ):
        if needle not in resume_source and needle not in exact_campaign_source:
            errors.append(
                "campaign resume/import must reject stale or contradictory terminal certified evidence: "
                f"{needle}"
            )

    certified_frontier_tree = _parse_python(CERTIFIED_FRONTIER_PATH)
    certified_frontier_source = CERTIFIED_FRONTIER_PATH.read_text(encoding="utf-8")
    for helper_name in (
        "generate_candidate_sizes",
        "normalize_terminal_frontier_domain_contract",
        "candidate_generation_kwargs",
        "candidate_key",
        "candidate_objective",
        "candidate_sort_key",
        "compute_terminal_frontier_projection",
        "compute_sink_verified_terminal_frontier_projection",
        "build_terminal_frontier_evidence",
        "build_sink_verified_terminal_frontier_evidence",
        "terminal_frontier_evidence_violation",
        "_candidate_status_digest",
    ):
        _function_def(certified_frontier_tree, helper_name, path=CERTIFIED_FRONTIER_PATH)
    for needle in (
        "TERMINAL_FRONTIER_EVIDENCE_SOURCE",
        "TERMINAL_FRONTIER_EVIDENCE_SCHEMA_VERSION = 2",
        "certified_terminal_frontier_evidence_v2",
        "TERMINAL_FRONTIER_DOMAIN_AUTHORITY",
        "TERMINAL_FRONTIER_OBJECTIVE",
        "_TERMINAL_FRONTIER_DOMAIN_CONTRACT_KEYS",
        "candidate_status_digest",
        "potential_domain_size",
        "frontier_keys",
        "safe_area_upper_bound",
        "terminal_frontier_start_area_not_full_domain",
        "terminal_frontier_area_upper_bound_not_authoritative",
        "terminal_frontier_aspect_ratio_sliced_domain",
        "terminal_frontier_min_side_sliced_domain",
        "terminal_frontier_candidate_generation_unknown_key",
        "terminal_frontier_min_side_admissibility_mismatch",
        "terminal_frontier_final_result_below_admissibility",
        "TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY",
        "terminal_frontier_candidate_status_digest_mismatch",
        "terminal_frontier_potential_domain_not_exhausted",
        # V82: the candidate domain is oriented; half-domain evidence must be
        # rejected explicitly via the bumped authority string.
        "outer_search_static_area_bound_oriented_v2",
        "Do not canonicalize",
    ):
        if needle not in certified_frontier_source:
            errors.append(
                "terminal CERTIFIED frontier evidence must be replayable, authority-bound, and digest-sealed: "
                f"{needle}"
            )

    outer_source_text = OUTER_SEARCH_PATH.read_text(encoding="utf-8")
    for needle in (
        "compute_sink_verified_terminal_frontier_projection",
        "candidate_generation",
        "candidate_generation_kwargs",
        "TERMINAL_FRONTIER_DOMAIN_AUTHORITY",
        "safe_area_upper_bound",
        "min_side_admissibility",
        "terminal_frontier_evidence",
    ):
        if needle not in outer_source_text:
            errors.append(
                "outer search must commit replayable full-domain terminal frontier evidence before CERTIFIED export: "
                f"{needle}"
            )
    pr2_supervisor_source = pr2_l0_source + "\n" + pr2_child_source
    for needle in (
        "run_l0_supervisor_seal",
        "_project_candidate_records_direct",
        "candidate_generation_kwargs",
        "generate_candidate_sizes",
        "sink_replay_violations",
        "terminal candidate sink replay failed",
    ):
        if needle not in pr2_supervisor_source:
            errors.append(
                "PR2 supervisor seal must replay terminal frontier evidence before CERTIFIED mint: "
                f"{needle}"
            )

    inspector_source = EXACT_CAMPAIGN_INSPECTOR_PATH.read_text(encoding="utf-8")
    for needle in (
        "verify_certified_delivery_surface",
        "certified_surface",
        "terminal_full_frontier_certified",
    ):
        if needle not in inspector_source:
            errors.append(
                "campaign inspector/report must publish terminal evidence through the central certified surface verifier: "
                f"{needle}"
            )
    if "has_terminal_full_frontier_certified_evidence" not in certified_surface_source_text:
        errors.append(
            "campaign inspector/report must share terminal full-frontier evidence via certified_surface.py"
        )

    b5a_source = (PROJECT_ROOT / "src" / "search" / "phase3b" / "b5a" / "b5_anchor_sprint.py").read_text(encoding="utf-8")
    for needle in ("certified_surface", "certified_surface_publishable", "anchor_found"):
        if needle not in b5a_source:
            errors.append(
                "B5A wrapper must consume the inspector certified surface verdict before publishing an anchor: "
                f"{needle}"
            )

    benders_tree = _parse_python(BENDERS_LOOP_PATH)
    run_benders_fn = _function_def(
        benders_tree,
        "run_benders_for_ghost_rect",
        path=BENDERS_LOOP_PATH,
    )
    run_benders_source = _source_text(BENDERS_LOOP_PATH, run_benders_fn)
    for needle in (
        "EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV",
        "ghost_anchor_filter_not_certified",
        "_collect_forbidden_certified_master_domain_env_overrides",
        "unsafe_certified_exact_master_domain_env",
        "_publish_last_run_metadata",
        "RUN_STATUS_UNPROVEN",
    ):
        if needle not in run_benders_source:
            errors.append(
                "certified exact run entrypoint must fail closed when the "
                f"ghost-anchor domain is env-filtered: {needle}"
            )
    create_session_fn = _function_def(
        benders_tree,
        "create_exact_search_session",
        path=BENDERS_LOOP_PATH,
    )
    create_session_source = _source_text(BENDERS_LOOP_PATH, create_session_fn)
    for needle in (
        "_collect_forbidden_certified_master_domain_env_overrides",
        "ExactSearchSession construction",
    ):
        if needle not in create_session_source:
            errors.append(
                "certified exact session factory must fail closed before session construction on unsafe master-domain/power-representation envs: "
                f"{needle}"
            )

    forbidden_env_fn = _function_def(
        benders_tree,
        "_collect_forbidden_certified_master_domain_env_overrides",
        path=BENDERS_LOOP_PATH,
    )
    forbidden_env_source = _source_text(BENDERS_LOOP_PATH, forbidden_env_fn)
    unsafe_env_map_source = _assignment_source(
        benders_tree,
        "_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES",
        path=BENDERS_LOOP_PATH,
    )
    power_witness_env_map_source = _assignment_source(
        benders_tree,
        "_CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS",
        path=BENDERS_LOOP_PATH,
    )
    benders_loop_source = BENDERS_LOOP_PATH.read_text(encoding="utf-8")
    for needle in (
        "_CERTIFIED_KNOWN_ENV_NAMES",
        "_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST",
        "_CERTIFIED_UNCLASSIFIED_ENV_BLOCKER_CODE",
        "_CERTIFIED_PROOF_SEMANTICS_ENV_BLOCKER_CODE",
        "unclassified_exact_env_not_certified",
        "proof_semantics_exact_env_not_certified",
        "EXACT_COMMUNITY_BLUEPRINT_HINT_PATH",
        "GATE_WORKER_PEAK_RSS_GIB",
    ):
        if needle not in benders_loop_source:
            errors.append(
                "certified exact env guard must be a closed allowlist that fails closed on unknown or proof-semantics EXACT_* knobs: "
                f"{needle}"
            )
    # V83: terminal certified results require project-bound geometric evidence,
    # whole-layout nogoods must not escalate to candidate INFEASIBLE, and the
    # certified mandatory loader is deny-unknown.
    exact_campaign_source_v83 = EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8")
    for needle in (
        "terminal_certified_final_result_empty_rect_not_witnessed",
        "terminal_certified_final_result_solution_missing_mandatory_instance",
        '== "ghost_pick"',
    ):
        if needle not in exact_campaign_source_v83:
            errors.append(
                f"terminal certified final_result must carry project-bound geometric evidence: {needle}"
            )
    master_model_source_v83 = MASTER_MODEL_PATH.read_text(encoding="utf-8")
    if "is_mandatory must be true" not in master_model_source_v83:
        errors.append(
            "certified mandatory_exact_instances loader must be deny-unknown: is_mandatory must be true"
        )
    # V84: the terminal witness must be the layout's best empty rectangle,
    # artifact hashing must reject symlinks, and unknown extra placement
    # instances must fail closed.
    for needle in (
        "terminal_certified_final_result_layout_has_better_empty_rect",
        "terminal_certified_final_result_solution_unknown_instance",
        "exact artifact must be a regular file",
        "terminal_certified_final_result_solution_missing_required_optional_instance",
        "infer_certified_optional_lower_bounds",
        "terminal_certified_final_result_solution_power_coverage_missing",
        "terminal_certified_final_result_solution_unforced_power_pole_instance",
        "terminal_certified_final_result_solution_excess_protocol_storage_box_instance",
        "terminal_certified_final_result_solution_metadata_mismatch",
        "terminal_certified_last_stop_reason_unknown_field",
        "terminal_certified_final_result_ghost_rect_anchor_occupied",
        "terminal_certified_final_result_ghost_rect_anchor_missing",
        "terminal_certified_candidate_solution_ghost_pick_missing",
        "terminal_certified_candidate_solution_ghost_pick_mismatch",
        "terminal_certified_final_result_unknown_field",
        "terminal_certified_final_result_ghost_rect_unknown_field",
        "terminal_certified_final_result_search_stats_unknown_field",
    ):
        if needle not in exact_campaign_source_v83:
            errors.append(
                f"V84 layout-optimality/artifact-boundary sealing must stay wired: {needle}"
            )
    # V82: persisted exact_safe_cuts are telemetry, not proof objects; certified
    # runs must regenerate cuts instead of replaying checkpoint/IPC payloads.
    for needle in (
        "persisted_exact_safe_cut_replay_input_count",
        "persisted_exact_safe_cut_replay_enabled",
    ):
        if needle not in benders_loop_source:
            errors.append(
                "certified cut replay must not consume persisted exact_safe_cuts "
                f"as proof objects: {needle}"
            )
    # V81: a time-budget-interrupted mandatory-rectangle precheck group must not
    # be consumed as a complete all-anchors-infeasible candidate proof.
    if benders_loop_source.count(
        'not bool(entry.get("partial_due_to_time_budget", False))'
    ) < 2:
        errors.append(
            "mandatory-rectangle precheck consumers must exclude "
            "partial_due_to_time_budget groups in both trigger predicates "
            "(benders_loop helper and run_benders_for_ghost_rect inline)"
        )
    single_base_release_source = SINGLE_BASE_RELEASE_BUILDER_PATH.read_text(encoding="utf-8")
    for needle in (
        "exact_full_scale_certified",
        "may not claim 'CERTIFIED'",
        "normalize_non_authoritative_exact_status",
        "normalize_non_authoritative_exact_note",
        "certified_delivery_manifest/certified_surface verifier",
    ):
        if needle not in single_base_release_source:
            errors.append(
                "single-base release readiness validation must fail closed on a "
                f"self-claimed CERTIFIED run summary: {needle}"
            )
    for needle in (
        "EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV",
        "ghost_anchor_filter_not_certified",
        "EXACT_USE_POSE_BOOL_MASTER_ENV",
        "pose_bool_master_not_certified",
        "EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE_ENV",
        "power_pole_slot_upper_bound_override_not_certified",
        "EXACT_LAZY_POWER_COMPLETION_ENV",
        "lazy_power_completion_not_certified",
        "EXACT_POWER_PLACEMENT_SUBPROBLEM_ENV",
        "power_placement_subproblem_not_certified",
        "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST_ENV",
        "power_placement_forensic_bypass_not_certified",
    ):
        if needle not in forbidden_env_source and needle not in unsafe_env_map_source:
            errors.append(
                "certified exact master-domain env blocker must reject every master-domain/power-representation override from the centralized unsafe map: "
                f"{needle}"
            )
        if needle not in benders_loop_source:
            errors.append(
                "certified exact master-domain env blocker must retain the declared env/code symbol: "
                f"{needle}"
            )
    for needle in (
        "EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV",
        "power_family_lookup_encoding_not_certified",
        "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV",
        "power_pole_shell_distance_encoding_not_certified",
        "EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV",
        "power_coverage_witness_encoding_not_certified",
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV",
        "power_coverage_witness_block_geometry_not_certified",
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV",
        "power_coverage_witness_block_size_not_certified",
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV",
        "power_coverage_witness_block_templates_not_certified",
        "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV",
        "power_coverage_selected_interval_encoding_not_certified",
    ):
        if needle not in forbidden_env_source and needle not in power_witness_env_map_source:
            errors.append(
                "certified exact power-witness env blocker must reject every non-canonical representation override: "
                f"{needle}"
            )
        if needle not in benders_loop_source:
            errors.append(
                "certified exact power-witness env blocker must retain the declared env/code symbol: "
                f"{needle}"
            )
    resolve_condition_fn = _function_def(
        benders_tree,
        "_resolve_condition_lits_from_condition_set",
        path=BENDERS_LOOP_PATH,
    )
    resolve_condition_source = _source_text(BENDERS_LOOP_PATH, resolve_condition_fn)
    if "_parse_ghost_anchor_condition_key" not in resolve_condition_source:
        errors.append("condition_set replay resolver must share the strict ghost_anchor parser")

    controller_class = _class_def(benders_tree, "LBBDController", path=BENDERS_LOOP_PATH)
    persisted_fn = _method_def(controller_class, "_add_exact_persisted_nogood", path=BENDERS_LOOP_PATH)
    persisted_source = _source_text(BENDERS_LOOP_PATH, persisted_fn)
    if "BendersCut.from_dict(cut.to_dict())" not in persisted_source:
        errors.append("generated certified cuts must round-trip through BendersCut validation before master apply")
    required_order = (
        "self.master.add_benders_cut",
        "self.cut_manager.register_structured_cut",
        "self.generated_exact_safe_cuts.append",
    )
    positions = [persisted_source.find(needle) for needle in required_order]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append(
            "_add_exact_persisted_nogood must apply to master, then register, then count generated exact-safe cuts"
        )

    master_tree = _parse_python(MASTER_MODEL_PATH)
    master_class = _class_def(master_tree, "MasterPlacementModel", path=MASTER_MODEL_PATH)
    master_add_fn = _method_def(master_class, "add_benders_cut", path=MASTER_MODEL_PATH)
    master_source = _source_text(MASTER_MODEL_PATH, master_add_fn)
    if "seen_names" not in master_source or not _returns_constant(master_add_fn, False):
        errors.append("MasterPlacementModel.add_benders_cut must fail closed on missing or aliasing literals")

    coordinate_tree = _parse_python(EXACT_COORDINATE_MASTER_PATH)
    coordinate_class = _class_def(coordinate_tree, "CoordinateExactMasterDelegate", path=EXACT_COORDINATE_MASTER_PATH)
    entries_fn = _method_def(coordinate_class, "_conflict_pose_entries", path=EXACT_COORDINATE_MASTER_PATH)
    coordinate_add_fn = _method_def(coordinate_class, "add_benders_cut", path=EXACT_COORDINATE_MASTER_PATH)
    entries_source = _source_text(EXACT_COORDINATE_MASTER_PATH, entries_fn)
    if "seen" not in entries_source or "return []" not in entries_source:
        errors.append("CoordinateExactMasterDelegate._conflict_pose_entries must reject missing or aliasing members")
    if not _calls_attr(coordinate_add_fn, "_conflict_pose_entries") or not _returns_constant(coordinate_add_fn, False):
        errors.append("CoordinateExactMasterDelegate.add_benders_cut must fail closed when entries/literals are unresolved")

    pose_bool_tree = _parse_python(POSE_BOOL_EXACT_MASTER_PATH)
    pose_bool_class = _class_def(pose_bool_tree, "PoseBoolExactMasterDelegate", path=POSE_BOOL_EXACT_MASTER_PATH)
    pose_bool_add_fn = _method_def(pose_bool_class, "add_benders_cut", path=POSE_BOOL_EXACT_MASTER_PATH)
    pose_bool_source = _source_text(POSE_BOOL_EXACT_MASTER_PATH, pose_bool_add_fn)
    if "seen_lit_names" not in pose_bool_source or not _returns_constant(pose_bool_add_fn, False):
        errors.append("PoseBoolExactMasterDelegate.add_benders_cut must fail closed on missing or aliasing literals")

    return errors


CLOSE_KERNEL_REQUIRED_ATTACK_CATEGORIES = frozenset(
    {
        "direct_writer_bypass",
        "status_synonym_or_free_text_claim",
        "stale_checkpoint_or_manifest_authority",
        "path_symlink_or_shadow_authority",
        "malformed_json_or_weak_typing",
        "unsafe_env_or_config_semantics",
        "parallel_resume_or_crash_partial_authority",
        "gate_or_obligation_mutation",
        "same_process_function_or_closure_authority",
        "producer_monkeypatch_or_module_rebinding",
        "missing_or_unreplayable_candidate_proof",
        "sink_replay_bypass_or_binding_drift",
    }
)
CLOSE_KERNEL_ALLOWED_CLASSIFICATIONS = frozenset(
    {
        "p1_2_certified_path",
        "p1_2_public_surface",
        "p1_2_close_kernel",
        "out_of_scope_future_phase3b",
        "non_authoritative_projection",
        "diagnostic_or_telemetry_non_authority",
        "exploratory_or_heuristic_non_authority",
    }
)

# Named TCB boundary: this checker source owns the approved review anchor and
# the V99 static source-hash / required-file floor below, including the
# terminal fixed-witness capsule.  The checker cannot recursively prove its own
# source integrity; git history and human review are the trust boundary.  A
# legitimate floor reseal must therefore change this checker code, not only
# mutable manifest/gate data.
CLOSE_KERNEL_APPROVED_REVIEW_ANCHOR = "v99_p1_2_close_kernel_sealing"
CLOSE_KERNEL_V99_STATIC_REVIEW_ANCHOR = CLOSE_KERNEL_APPROVED_REVIEW_ANCHOR
CLOSE_KERNEL_V99_REQUIRED_PROOF_BEARING_TOKENS = frozenset(
    {
        "CERTIFIED",
        "INFEASIBLE",
        "RUN_STATUS_CERTIFIED",
        "RUN_STATUS_INFEASIBLE",
        "terminal_frontier_evidence",
        "best_certified_result",
        "certified_surface",
        "proof_source",
        "certified_delivery_manifest.json",
        "final_solution.json",
        "optimal_blueprint.json",
        "proof-bearing",
        "proof_bearing",
        "candidate_proof",
        "candidate_sink_replay",
        "certified_exact_isolated_solver_replay_v1",
    }
)
CLOSE_KERNEL_V99_REQUIRED_SCAN_ROOTS = frozenset(
    {
        "src",
        "scripts/check_p1_2_proof_obligations.py",
        "scripts/check_strong_status_write_allowlist.py",
        "scripts/build_industrial_planner_single_base_delivery_release.py",
    }
)
CLOSE_KERNEL_V99_REQUIRED_SINK_CLASSIFICATION_BY_PATH = {
    'scripts/build_industrial_planner_single_base_delivery_release.py': 'p1_2_public_surface',
    'scripts/check_p1_2_proof_obligations.py': 'p1_2_close_kernel',
    'scripts/check_strong_status_write_allowlist.py': 'p1_2_close_kernel',
    'src/adapters/industrial_planner/export_blueprint.py': 'non_authoritative_projection',
    'src/adapters/industrial_planner/mapping_registry.py': 'non_authoritative_projection',
    'src/cuts/cert_schema.py': 'out_of_scope_future_phase3b',
    'src/cuts/families/pattern_nogood.py': 'out_of_scope_future_phase3b',
    'src/cuts/helpers/bounded_core_minimizer.py': 'out_of_scope_future_phase3b',
    'src/cuts/lifecycle.py': 'out_of_scope_future_phase3b',
    'src/cuts/oracles/pattern_nogood_oracle.py': 'out_of_scope_future_phase3b',
    'src/cuts/oracles/power_cover_oracle.py': 'out_of_scope_future_phase3b',
    'src/cuts/oracles/region_capacity_oracle.py': 'out_of_scope_future_phase3b',
    'src/cuts/oracles/shape_packing_hall_oracle.py': 'out_of_scope_future_phase3b',
    'src/io/delivery_manifest.py': 'p1_2_public_surface',
    'src/io/output_schema.py': 'p1_2_public_surface',
    'src/io/serializer.py': 'p1_2_public_surface',
    'src/models/abstract_routing_layer.py': 'p1_2_certified_path',
    'src/models/binding_subproblem.py': 'p1_2_certified_path',
    'src/models/cpsat_minimum_model.py': 'p1_2_certified_path',
    'src/models/cut_manager.py': 'p1_2_certified_path',
    'src/models/d2_commodity_flow_core.py': 'p1_2_certified_path',
    'src/models/exact_coordinate_master.py': 'p1_2_certified_path',
    'src/models/flow_subproblem.py': 'p1_2_certified_path',
    'src/models/highs_candidate_evaluator.py': 'p1_2_certified_path',
    'src/models/highs_master_model.py': 'p1_2_certified_path',
    'src/models/master_model.py': 'p1_2_certified_path',
    'src/models/patch_routing_core.py': 'p1_2_certified_path',
    'src/models/power_placement_subproblem.py': 'p1_2_certified_path',
    'src/models/routing_subproblem.py': 'p1_2_certified_path',
    'src/models/scip_master_model.py': 'p1_2_certified_path',
    'src/render/industrial_planner_exact_status.py': 'non_authoritative_projection',
    'src/render/industrial_planner_single_base_delivery_entrypoints.py': 'non_authoritative_projection',
    'src/render/industrial_planner_single_base_delivery_frontdoor.py': 'non_authoritative_projection',
    'src/render/industrial_planner_single_base_delivery_landing.py': 'non_authoritative_projection',
    'src/render/industrial_planner_single_base_delivery_surface_alignment.py': 'non_authoritative_projection',
    'src/render/industrial_planner_single_base_delivery_surface_health.py': 'non_authoritative_projection',
    'src/render/industrial_planner_single_base_delivery_viewer.py': 'non_authoritative_projection',
    'src/render/blueprint_exporter.py': 'non_authoritative_projection',
    'src/render/report_builder.py': 'non_authoritative_projection',
    'src/render/serve.py': 'non_authoritative_projection',
    'src/search/benders_loop.py': 'p1_2_certified_path',
    'src/search/campaign_telemetry.py': 'diagnostic_or_telemetry_non_authority',
    'src/search/campaign_triage.py': 'diagnostic_or_telemetry_non_authority',
    'src/search/candidate_proof_replay.py': 'p1_2_certified_path',
    'src/search/certified_frontier.py': 'p1_2_certified_path',
    'src/search/certified_surface.py': 'p1_2_public_surface',
    'src/search/d2_separator.py': 'p1_2_certified_path',
    'src/search/exact_campaign.py': 'p1_2_certified_path',
    'src/search/exact_campaign_inspector.py': 'p1_2_public_surface',
    'src/search/exact_parallel_scheduler.py': 'p1_2_certified_path',
    'src/search/heuristic_feasible_finder.py': 'exploratory_or_heuristic_non_authority',
    'src/search/independent_infeasibility_reverifier.py': 'p1_2_certified_path',
    'src/search/outer_search.py': 'p1_2_certified_path',
    'src/search/patch_conflict_separator.py': 'p1_2_certified_path',
    'src/search/pr2_l0_micro_verifier_core.py': 'p1_2_certified_path',
    'src/search/pr2_l0_true_verifier_child.py': 'p1_2_certified_path',
    'src/search/smt_mt_outer_pruning.py': 'p1_2_certified_path',
    'src/search/terminal_fixed_witness_capsule.py': 'p1_2_public_surface',
    'src/search/terminal_fixed_witness_verifier.py': 'p1_2_certified_path',
}
CLOSE_KERNEL_V99_REQUIRED_SINK_PATHS = frozenset(CLOSE_KERNEL_V99_REQUIRED_SINK_CLASSIFICATION_BY_PATH)
CLOSE_KERNEL_V99_REQUIRED_CRITICAL_GATE_FILES = frozenset(
    {
        "scripts/check_p1_2_proof_obligations.py",
        "scripts/check_strong_status_write_allowlist.py",
        PR2_DEPENDENCY_FLOOR_GENERATOR_REL,
        "data/proof_obligations/p1_2_proof_obligations.json",
        PR2_DEPENDENCY_FLOOR_MANIFEST_REL,
        "src/search/certified_surface.py",
        "src/search/certified_artifact_contract.py",
        "src/io/delivery_manifest.py",
        "src/search/candidate_proof_replay.py",
        "src/search/certified_frontier.py",
        "src/search/exact_campaign.py",
        "src/search/pr2_l0_micro_verifier_core.py",
        "src/search/pr2_l0_true_verifier_child.py",
        "src/search/outer_search.py",
        "src/search/exact_parallel_scheduler.py",
        "src/search/benders_loop.py",
        "src/search/terminal_fixed_witness_capsule.py",
        "src/render/industrial_planner_exact_status.py",
        "scripts/build_industrial_planner_single_base_delivery_release.py",
    }
)

# Checker-owned human-review surface for AST structural gates.  These files are
# inspected by the publish-wiring guard and the phase-gate verifier/capsule
# checks.  The reachability scanner is a redundant second layer; the primary
# anti-drift defense is that every structurally checked source is also pinned by
# the V99 source-hash floor below.
CLOSE_KERNEL_V99_STRUCTURAL_GATE_SOURCE_PATHS = frozenset(
    {
        "src/search/certified_frontier.py",
        "src/search/certified_surface.py",
        "src/search/exact_campaign.py",
        "src/search/pr2_l0_micro_verifier_core.py",
        "src/search/pr2_l0_true_verifier_child.py",
        "src/io/delivery_manifest.py",
        "src/io/serializer.py",
        "src/render/blueprint_exporter.py",
        "src/search/terminal_fixed_witness_capsule.py",
        "src/search/terminal_fixed_witness_verifier.py",
    }
)

CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH = {
    'scripts/build_industrial_planner_single_base_delivery_release.py': '6cd8480f4b3c97b55b4867460a651b980aac42c9c678e7d60f75cecac879da92',
    'scripts/check_strong_status_write_allowlist.py': '4964fcdea6f987d424013e25cc34355c1bc3371d2e2c8d9e68f96fa84cd1a9ff',
    'src/search/certified_artifact_contract.py': 'e45f4ded38b209601ec5306bc9ab6152ab3dca34a86bb5b0827212d59563cd07',
    'scripts/generate_pr2_dependency_floor_manifest.py': '0555322552375a2036ccac71afac85a29fc3773a7ac37ad09ad03b167bb6503c',
    'src/adapters/industrial_planner/export_blueprint.py': '01afafc85b4e7f27c0bf8c0293845785b45bc71ad332da483936b753a7d9eb5e',
    'src/adapters/industrial_planner/mapping_registry.py': '7e20051ff2a4eddc551ea1f1f109e61127b597b65fa070dddb8528d180106ce3',
    'src/cuts/cert_schema.py': 'e7535dac7597f6829b3149ec09d90faf3d15af43f43d1154feba941cd4a4f05e',
    'src/cuts/families/pattern_nogood.py': '3083df0a2eaa71d0f2823a60ad9156bcc6bc744e4ff4bc26f9544d7dabe6230b',
    'src/cuts/helpers/bounded_core_minimizer.py': 'da3184e860ea49fa88a45da2db09c7b09fd742fc7eb10b6f7018eb1e5b98985b',
    'src/cuts/lifecycle.py': '430bf565af94490972b92599a0c85de18ea7ea94a3cad87463019be3f908d29d',
    'src/cuts/oracles/pattern_nogood_oracle.py': '019d808d18619c9fc3e3692d476040cad3c8b360b5671bce54c6b8ac9003ef37',
    'src/cuts/oracles/power_cover_oracle.py': '161e513cde4fbfa0fd5dc30039f067e705728b2ff0a9d0125a39dd3d284457b9',
    'src/cuts/oracles/region_capacity_oracle.py': '52b18886e7d613997553a785bb258875cf1df642fe47a6cbb19d8be857c12e83',
    'src/cuts/oracles/shape_packing_hall_oracle.py': '44111273420eaf00052e13785ed8039a722e752b4af0f0a1121f2b31d26f9934',
    'src/io/delivery_manifest.py': '19d2bb353f4bfbc1a4473ec6a4aa2e214dd47083b94d516d4f70962e05e79a09',
    'src/io/output_schema.py': '78900b3f252534e3674043b985441a27cadf3c507c5891f4e3752a8a11b3da4c',
    'src/io/serializer.py': 'f40ede9bacee8fbfd1526973eb5f9985184930b70f84d946bb8b8c80d9e4fa9d',
    'src/models/abstract_routing_layer.py': '1f1f71258a840d872d85afe5e18760c100eda671848bef94c6cf972ccee0df16',
    'src/models/binding_subproblem.py': '9af9a256c03ebfd937642248fd329ca9b307f28a0fec8280dc76634b8910cac1',
    'src/models/cpsat_minimum_model.py': '92d9e9eed88dbf6672db12766a8a1422c660e8314480b9fa599ce4b0e71b7104',
    'src/models/cut_manager.py': '50b46f98cd2ca1947b807262a78a2460f822b6755d94c0845749d2c02c416a01',
    'src/models/d2_commodity_flow_core.py': '55aee97d9162541efd0014c5f4682c1d4d60c1fb0ef9246a657dfbb3ff17775e',
    'src/models/exact_coordinate_master.py': '8d4d9f1c09f8f2d2e16b4507f0f42444e327b737764a76d64124e6c32abaca9f',
    'src/models/flow_subproblem.py': '1d3d0f174e23feb6df01858941cb713af6f8f676315bba7568211b9d45f9e94d',
    'src/models/highs_candidate_evaluator.py': '1709e1536a49f11ed057ab6dc1e904d9acac8d25c910c4299789b5309986f419',
    'src/models/highs_master_model.py': 'ab366573359ec1db835c6c78e03f9ecd7387abc3ea5bb0aaa31cebaed64f191a',
    'src/models/master_model.py': '1c72cc6e5b042900975cc18b8284c75531f01d3ca4f46ef553dcbea49b61710f',
    'src/models/patch_routing_core.py': '371cdf69c6d30a1499dbd596750dfc1802eb4e1aa652e3042c044c3136c17b98',
    'src/models/power_placement_subproblem.py': '88573b3ebdf26a334d740d718d4f90a5216745936291ef6b87b877f99594a597',
    'src/models/routing_subproblem.py': '25c56e1f5f383f8696f93d876282f1cd5c26a37e610e6bc7d6ca8ffcd737ba49',
    'src/models/scip_master_model.py': 'd3590b07088e4e67c5b714aca78e39acddd0da8b59a7b96a68ae7b4b270f2bea',
    'src/render/industrial_planner_exact_status.py': '22875159909302a5d5dde77bd832539be1b01a10e40606d8d459996714c56183',
    'src/render/industrial_planner_single_base_delivery_entrypoints.py': 'e80cc8d6c4badadad9c23a2c6c8c645e653425b2b0002879baadb29c3dd6759c',
    'src/render/industrial_planner_single_base_delivery_frontdoor.py': '5e530baaa4e49e149755c96452521daa93ece7a3c29b6e05545fcd5819530fdb',
    'src/render/industrial_planner_single_base_delivery_landing.py': '085212ba166c2211a12a590c12d07a6a8cf6f38429d49a4d97b79633296b8da9',
    'src/render/industrial_planner_single_base_delivery_surface_alignment.py': 'f3bc8bec1160f97c25c39c170077a14ffd4ffcafbb3150dab9c61235dc3dd97c',
    'src/render/industrial_planner_single_base_delivery_surface_health.py': '788fd78ad6fcf6d9d4b8e8d4a9f57a4323295c4341730874ccb7af98736eeddf',
    'src/render/industrial_planner_single_base_delivery_viewer.py': '79993549328337748060db557392268791812ab39a00b471cc4439e16d1b6bf9',
    'src/render/blueprint_exporter.py': '8ee3b21bc137493fc930b08bd5ea368e23bcd1090ddf51a56bb7264d4d31a61f',
    'src/render/report_builder.py': '860ff758d6c64ac0029f2e22ad087c6b520d37d40e0264a8b464302a36c7cff6',
    'src/render/serve.py': '45a03f847c80595ef72b3e859eeccf01169ed16e87faebd7b75be4c788ff7262',
    'src/search/benders_loop.py': '67e42c75bd6bcdb0a6374b4cae548e7ad60e383a83eacbbf7e3ceddccbed338a',
    'src/search/campaign_telemetry.py': 'b6582c452b39c444d32a07e9f949fbbfc16558b5d99e9a0a3824d86cdc4e76f6',
    'src/search/campaign_triage.py': '0ce473249d0a78e4dd837df140a218f1a109c4e304a223910dd2c918109dd376',
    'src/search/candidate_proof_replay.py': '841e73765464f755fc1021bd3ec1649612a61d57cb4fe220329fec719bd658d5',
    'src/search/certified_frontier.py': '80c72be1110bfa83fb1c5ca02513e41f9107f1e5aedd304642fbf2fa2bda2b74',
    'src/search/certified_surface.py': 'd4430f5ea523afbd2771cdf0c3e0e9d28c5aca10635e3f2751a2533a9b595cf4',
    'src/search/d2_separator.py': '0263f50142b72833f87653e34a60e9a7f2c5495b90b86ef368dc25f2e0d2327e',
    'src/search/exact_campaign.py': '2b44f7cbfd61d1b7914659fb7a5d10688bd011412919b83aac9c74ca39dd1f1c',
    'src/search/exact_campaign_inspector.py': 'ca16b9a7272d633a6ca19d8257cfde73d5c1858711b503aa222fd7d5c7dd53da',
    'src/search/exact_parallel_scheduler.py': 'e07c926505e030ed2ab4220afe612c7a187e0e19c222c841c5f68a0d02f7c441',
    'src/search/heuristic_feasible_finder.py': '0f9723671ddee8dd8b53659ae204f2ca1d7967d2ad3d63db0c093f8586302903',
    'src/search/independent_infeasibility_reverifier.py': '18355474ef6f2a13ed1117aeb99f3863adf5e65f6ba8f73a9e081519380b8188',
    'src/search/outer_search.py': '0ca6b4c45e6e8890a28962b68e05685a53fe748745e827f953e84d00d8d1ed3b',
    'src/search/patch_conflict_separator.py': '4c468f34bb620dbf136641281ad337dabe255f5e7465585781887e8f6bc0a775',
    'src/search/pr2_l0_micro_verifier_core.py': 'ae74acb1403106400ff31efe30873fe4f2062ab6899264eed6e2edefdf7e13dc',
    'src/search/pr2_l0_true_verifier_child.py': '3a5aa031feaa3e64c4a91ce1474d99a7e0cc29b130e3ecbc4745dacd3e2da335',
    'src/search/smt_mt_outer_pruning.py': '004ce7151b8fc4dc7caf2cc32352b9090f2227f9de8fa2c7e55d9b04cbf4bf91',
    'src/search/terminal_fixed_witness_capsule.py': 'eba3fa8c396e45d6f86f74b73a21a1599201379b76ffa26c05afbe0f499084d9',
    'src/search/terminal_fixed_witness_verifier.py': '2feab8d5f08c9d070e6343805f667a41f27573888c24c55327c50d0a9e924531',
}
CLOSE_KERNEL_V99_MIN_SINK_COUNT = len(CLOSE_KERNEL_V99_REQUIRED_SINK_PATHS)

def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _is_excluded_path(rel_path: str, excluded_subpaths: Sequence[str]) -> bool:
    normalized = rel_path.replace("\\", "/").strip("/")
    for raw_excluded in excluded_subpaths:
        excluded = raw_excluded.replace("\\", "/").strip("/")
        if not excluded:
            continue
        if normalized == excluded or normalized.startswith(excluded + "/"):
            return True
    return False


def _scan_close_kernel_token_files(
    *,
    project_root: Path,
    scan_roots: Sequence[str],
    tokens: Sequence[str],
    excluded_subpaths: Sequence[str],
) -> set[str]:
    found: set[str] = set()
    for raw_root in scan_roots:
        root_rel = _require_str(raw_root, "close_kernel_contract.scan_roots[]")
        root = project_root / root_rel
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.py")
        for path in paths:
            if path.is_dir() or path.suffix != ".py":
                continue
            rel_path = path.relative_to(project_root).as_posix()
            if _is_excluded_path(rel_path, excluded_subpaths):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in text for token in tokens):
                found.add(rel_path)
    return found


def _approved_review_anchor_error(label: str, value: str) -> str | None:
    if value == CLOSE_KERNEL_APPROVED_REVIEW_ANCHOR:
        return None
    return (
        f"{label} must equal approved checker anchor "
        f"{CLOSE_KERNEL_APPROVED_REVIEW_ANCHOR!r}; got {value!r}"
    )



def _check_close_kernel_v99_static_floor(
    *,
    tokens: Sequence[str],
    scan_roots: Sequence[str],
    excluded_subpaths: Sequence[str],
    critical_gate_files: Sequence[str],
    registered: dict[str, dict[str, Any]],
    project_root: Path,
) -> list[str]:
    """Enforce the non-self-authored v99 close-kernel floor.

    The manifest may describe extra roots/sinks, but the v99 close claim must not
    be able to shrink its own authority surface or reseal source drift by editing
    only ``p1_2_proof_obligations.json``.  This is still a structural gate, not a
    theorem prover.  The checker source that contains the approved anchor and
    floor hashes is the named close-kernel TCB; changing it reopens review.
    """
    errors: list[str] = []
    declared_tokens = set(tokens)
    missing_tokens = CLOSE_KERNEL_V99_REQUIRED_PROOF_BEARING_TOKENS - declared_tokens
    for token in sorted(missing_tokens):
        errors.append(f"close_kernel_contract.proof_bearing_tokens missing v99 sealed token: {token}")

    declared_scan_roots = set(scan_roots)
    missing_scan_roots = CLOSE_KERNEL_V99_REQUIRED_SCAN_ROOTS - declared_scan_roots
    for rel_path in sorted(missing_scan_roots):
        errors.append(f"close_kernel_contract.scan_roots missing v99 sealed scan root: {rel_path}")

    for rel_path in sorted(CLOSE_KERNEL_V99_REQUIRED_SINK_PATHS):
        if _is_excluded_path(rel_path, excluded_subpaths):
            errors.append(f"close_kernel_contract.excluded_subpaths must not exclude v99 sealed sink: {rel_path}")

    registered_paths = set(registered)
    if len(registered_paths) < CLOSE_KERNEL_V99_MIN_SINK_COUNT:
        errors.append(
            "close_kernel_contract.sink_files shrank below the v99 sealed floor: "
            f"{len(registered_paths)} < {CLOSE_KERNEL_V99_MIN_SINK_COUNT}"
        )
    missing_sinks = CLOSE_KERNEL_V99_REQUIRED_SINK_PATHS - registered_paths
    for rel_path in sorted(missing_sinks):
        errors.append(f"close_kernel_contract missing v99 sealed sink path: {rel_path}")

    for rel_path, expected_classification in sorted(CLOSE_KERNEL_V99_REQUIRED_SINK_CLASSIFICATION_BY_PATH.items()):
        entry = registered.get(rel_path)
        if entry is None:
            continue
        actual_classification = entry.get("classification")
        if actual_classification != expected_classification:
            errors.append(
                f"{rel_path} v99 classification changed from {expected_classification!r} "
                f"to {actual_classification!r}"
            )

    declared_critical_gate_files = set(critical_gate_files)
    missing_critical_gate_files = CLOSE_KERNEL_V99_REQUIRED_CRITICAL_GATE_FILES - declared_critical_gate_files
    for rel_path in sorted(missing_critical_gate_files):
        errors.append(f"close_kernel_contract.critical_gate_files missing v99 sealed gate file: {rel_path}")

    for rel_path in sorted(CLOSE_KERNEL_V99_STRUCTURAL_GATE_SOURCE_PATHS):
        if rel_path not in CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH:
            errors.append(
                f"{rel_path} is structurally checked by P1.2 gates but missing from "
                "the v99 source-hash floor"
            )

    for rel_path, expected_sha256 in sorted(CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH.items()):
        entry = registered.get(rel_path)
        if entry is not None:
            declared_sha256 = entry.get("source_sha256")
            if declared_sha256 != expected_sha256:
                errors.append(
                    f"{rel_path} v99 source_sha256 changed without checker-floor reseal"
                )
        path = project_root / rel_path
        if path.exists() and _sha256_file(path) != expected_sha256:
            errors.append(f"{rel_path} current source hash drifted from the v99 sealed floor")
    return errors


def _check_dependency_floor_provenance_contract(
    manifest: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    """Bind the PR2 L0 dependency-floor manifest and its generator.

    The floor manifest is host-generated data rather than a proof-bearing Python
    sink, so this check pins its exact bytes separately from the Python source
    sink inventory. The generator is source and is additionally sealed by the
    V99 source-hash floor above.
    """

    errors: list[str] = []
    contract = manifest.get("close_kernel_contract")
    if not isinstance(contract, dict):
        return ["close_kernel_contract must be an object"]
    provenance = contract.get("dependency_floor_provenance")
    if not isinstance(provenance, dict):
        return ["close_kernel_contract.dependency_floor_provenance must be an object"]

    expected_fields: dict[str, object] = {
        "schema_version": 1,
        "manifest_path": PR2_DEPENDENCY_FLOOR_MANIFEST_REL,
        "manifest_sha256": PR2_DEPENDENCY_FLOOR_MANIFEST_SHA256,
        "manifest_size": PR2_DEPENDENCY_FLOOR_MANIFEST_SIZE,
        "manifest_authority": PR2_DEPENDENCY_FLOOR_AUTHORITY,
        "manifest_floor_root": PR2_DEPENDENCY_FLOOR_ROOT_SENTINEL,
        "generator_path": PR2_DEPENDENCY_FLOOR_GENERATOR_REL,
        "generator_sha256": PR2_DEPENDENCY_FLOOR_GENERATOR_SHA256,
        "loader_constant": "DEPENDENCY_FLOOR_MANIFEST_REL",
        "mutation_policy": "dependency_floor_drift_reopens_p1_2_close_claim",
    }
    for field, expected in expected_fields.items():
        actual = provenance.get(field)
        if actual != expected:
            errors.append(
                "close_kernel_contract.dependency_floor_provenance."
                f"{field} must be {expected!r}; got {actual!r}"
            )

    source_floor_sha = CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH.get(
        PR2_DEPENDENCY_FLOOR_GENERATOR_REL
    )
    if source_floor_sha != PR2_DEPENDENCY_FLOOR_GENERATOR_SHA256:
        errors.append("dependency floor generator missing from the v99 source-hash floor")

    loader_source = PR2_L0_MICRO_VERIFIER_PATH.read_text(encoding="utf-8")
    for token in (
        "DEPENDENCY_FLOOR_MANIFEST_REL",
        "DEPENDENCY_FLOOR_MANIFEST_SHA256",
        "DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES",
        "DEPENDENCY_FLOOR_ROOT_SENTINEL",
        PR2_DEPENDENCY_FLOOR_MANIFEST_REL,
        PR2_DEPENDENCY_FLOOR_MANIFEST_SHA256,
        str(PR2_DEPENDENCY_FLOOR_MANIFEST_SIZE),
        PR2_DEPENDENCY_FLOOR_ROOT_SENTINEL,
        "canonical dependency floor manifest hash drift",
    ):
        if token not in loader_source:
            errors.append(f"PR2 L0 canonical floor loader missing pinned token: {token}")
    if "_generate_default_dependency_floor_manifest" in loader_source:
        errors.append("PR2 L0 canonical floor loader must not auto-generate reviewed floor bytes")

    manifest_path = project_root / PR2_DEPENDENCY_FLOOR_MANIFEST_REL
    if not manifest_path.exists():
        errors.append(f"dependency floor manifest missing: {PR2_DEPENDENCY_FLOOR_MANIFEST_REL}")
    else:
        manifest_bytes = manifest_path.read_bytes()
        current_size = len(manifest_bytes)
        current_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        if current_size != PR2_DEPENDENCY_FLOOR_MANIFEST_SIZE:
            errors.append(
                "dependency floor manifest size drift reopens P1.2 close claim: "
                f"{current_size} != {PR2_DEPENDENCY_FLOOR_MANIFEST_SIZE}"
            )
        if current_sha256 != PR2_DEPENDENCY_FLOOR_MANIFEST_SHA256:
            errors.append(
                "dependency floor manifest hash drift reopens P1.2 close claim: "
                f"{current_sha256} != {PR2_DEPENDENCY_FLOOR_MANIFEST_SHA256}"
            )
        try:
            floor_manifest = _load_json(manifest_path)
        except CheckError as exc:
            errors.append(f"dependency floor manifest is not strict JSON: {exc}")
        else:
            if floor_manifest.get("schema_version") != 1:
                errors.append("dependency floor manifest schema_version must be 1")
            if floor_manifest.get("authority") != PR2_DEPENDENCY_FLOOR_AUTHORITY:
                errors.append(
                    "dependency floor manifest authority must be "
                    f"{PR2_DEPENDENCY_FLOOR_AUTHORITY}"
                )
            if floor_manifest.get("floor_root") != PR2_DEPENDENCY_FLOOR_ROOT_SENTINEL:
                errors.append(
                    "dependency floor manifest floor_root must be "
                    f"{PR2_DEPENDENCY_FLOOR_ROOT_SENTINEL}"
                )
            files = floor_manifest.get("files")
            if not isinstance(files, dict) or not files:
                errors.append("dependency floor manifest files must be a non-empty object")
            named_tcb = floor_manifest.get("named_tcb")
            if not isinstance(named_tcb, dict):
                errors.append("dependency floor manifest named_tcb must be an object")
            elif named_tcb.get("third_party_native_semantics") != "NAMED-TCB":
                errors.append(
                    "dependency floor manifest third_party_native_semantics must be NAMED-TCB"
                )

    generator_path = project_root / PR2_DEPENDENCY_FLOOR_GENERATOR_REL
    if not generator_path.exists():
        errors.append(f"dependency floor generator missing: {PR2_DEPENDENCY_FLOOR_GENERATOR_REL}")
    elif _sha256_file(generator_path) != PR2_DEPENDENCY_FLOOR_GENERATOR_SHA256:
        errors.append(
            "dependency floor generator hash drift reopens P1.2 close claim: "
            f"{PR2_DEPENDENCY_FLOOR_GENERATOR_REL}"
        )
    return errors


def _check_close_kernel_contract(manifest: dict[str, Any], *, project_root: Path = PROJECT_ROOT) -> list[str]:
    """Check the P1.2 close-kernel contract.

    This deliberately remains a small structural gate.  It does not certify a
    candidate and it does not reason about geometry.  It seals the proof-bearing
    authority surface: every current source file that speaks strong status
    language must be registered, hash-bound, assigned to a proof obligation, and
    guarded by local tokens that make bypass/removal show up as a gate failure.
    """

    errors: list[str] = []
    contract = manifest.get("close_kernel_contract")
    if not isinstance(contract, dict):
        return ["close_kernel_contract must be an object"]

    schema_version = _require_int(contract.get("schema_version"), "close_kernel_contract.schema_version")
    if schema_version != 1:
        errors.append("close_kernel_contract.schema_version must be 1")
    contract_review_anchor = _require_str(contract.get("review_anchor"), "close_kernel_contract.review_anchor")
    manifest_review_anchor = _require_str(manifest.get("review_anchor"), "review_anchor")
    if contract_review_anchor != manifest_review_anchor:
        errors.append("close_kernel_contract.review_anchor must match manifest.review_anchor")
    phase_required_anchor = _require_str(manifest.get("phase_gate_required_anchor"), "phase_gate_required_anchor")
    for label, value in (
        ("review_anchor", manifest_review_anchor),
        ("phase_gate_required_anchor", phase_required_anchor),
        ("close_kernel_contract.review_anchor", contract_review_anchor),
    ):
        error = _approved_review_anchor_error(label, value)
        if error is not None:
            errors.append(error)

    tcb = _require_list(contract.get("trusted_computing_base"), "close_kernel_contract.trusted_computing_base")
    if len(tcb) < 5:
        errors.append("close_kernel_contract.trusted_computing_base must explicitly list the close-kernel TCB")
    not_claimed = _require_list(contract.get("not_claimed"), "close_kernel_contract.not_claimed")
    if len(not_claimed) < 4:
        errors.append("close_kernel_contract.not_claimed must explicitly narrow the close claim")

    attack_categories = {
        _require_str(value, "close_kernel_contract.attack_categories[]")
        for value in _require_list(contract.get("attack_categories"), "close_kernel_contract.attack_categories")
    }
    for missing in sorted(CLOSE_KERNEL_REQUIRED_ATTACK_CATEGORIES - attack_categories):
        errors.append(f"close_kernel_contract missing attack category: {missing}")

    tokens = [
        _require_str(value, "close_kernel_contract.proof_bearing_tokens[]")
        for value in _require_list(contract.get("proof_bearing_tokens"), "close_kernel_contract.proof_bearing_tokens")
    ]
    scan_roots = [
        _require_str(value, "close_kernel_contract.scan_roots[]")
        for value in _require_list(contract.get("scan_roots"), "close_kernel_contract.scan_roots")
    ]
    excluded_subpaths = [
        _require_str(value, "close_kernel_contract.excluded_subpaths[]")
        for value in _require_list(contract.get("excluded_subpaths", []), "close_kernel_contract.excluded_subpaths")
    ]
    sink_entries = _require_list(contract.get("sink_files"), "close_kernel_contract.sink_files")
    if not sink_entries:
        errors.append("close_kernel_contract.sink_files must not be empty")

    obligation_ids = {
        _require_str(item.get("id"), "obligations[].id")
        for item in _require_list(manifest.get("obligations"), "obligations")
        if isinstance(item, dict)
    }
    registered: dict[str, dict[str, Any]] = {}
    for index, raw_entry in enumerate(sink_entries):
        if not isinstance(raw_entry, dict):
            errors.append(f"close_kernel_contract.sink_files[{index}] must be an object")
            continue
        rel_path = _require_str(raw_entry.get("path"), f"close_kernel_contract.sink_files[{index}].path")
        if rel_path in registered:
            errors.append(f"close_kernel_contract duplicate sink path: {rel_path}")
        registered[rel_path] = raw_entry

        classification = _require_str(raw_entry.get("classification"), f"{rel_path}.classification")
        if classification not in CLOSE_KERNEL_ALLOWED_CLASSIFICATIONS:
            errors.append(f"{rel_path} has unknown close-kernel classification: {classification}")
        obligation_id = _require_str(raw_entry.get("obligation_id"), f"{rel_path}.obligation_id")
        if obligation_id not in obligation_ids:
            errors.append(f"{rel_path} references unknown proof obligation: {obligation_id}")
        mutation_policy = _require_str(raw_entry.get("mutation_policy"), f"{rel_path}.mutation_policy")
        if mutation_policy != "source_sha256_drift_reopens_p1_2_close_claim":
            errors.append(f"{rel_path} must use source_sha256_drift_reopens_p1_2_close_claim")

        path = project_root / rel_path
        if not path.exists():
            errors.append(f"registered close-kernel sink missing: {rel_path}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        source_sha256 = _require_str(raw_entry.get("source_sha256"), f"{rel_path}.source_sha256")
        current_sha256 = _sha256_file(path)
        if source_sha256 != current_sha256:
            errors.append(f"registered close-kernel sink hash drift reopens P1.2 close claim: {rel_path}")
        terms = [
            _require_str(value, f"{rel_path}.terms[]")
            for value in _require_list(raw_entry.get("terms"), f"{rel_path}.terms")
        ]
        if not terms or not any(term in text for term in terms):
            errors.append(f"registered close-kernel sink no longer contains its declared proof-bearing terms: {rel_path}")
        guard_tokens = [
            _require_str(value, f"{rel_path}.required_guard_tokens[]")
            for value in _require_list(raw_entry.get("required_guard_tokens"), f"{rel_path}.required_guard_tokens")
        ]
        if not guard_tokens:
            errors.append(f"registered close-kernel sink has no guard tokens: {rel_path}")
        for guard_token in guard_tokens:
            if guard_token not in text:
                errors.append(f"registered close-kernel sink missing guard token {guard_token!r}: {rel_path}")

    critical_files = [
        _require_str(value, "close_kernel_contract.critical_gate_files[]")
        for value in _require_list(contract.get("critical_gate_files"), "close_kernel_contract.critical_gate_files")
    ]
    for rel_path in critical_files:
        if not (project_root / rel_path).exists():
            errors.append(f"close-kernel critical gate file missing: {rel_path}")

    errors.extend(
        _check_close_kernel_v99_static_floor(
            tokens=tokens,
            scan_roots=scan_roots,
            excluded_subpaths=excluded_subpaths,
            critical_gate_files=critical_files,
            registered=registered,
            project_root=project_root,
        )
    )

    found = _scan_close_kernel_token_files(
        project_root=project_root,
        scan_roots=scan_roots,
        tokens=tokens,
        excluded_subpaths=excluded_subpaths,
    )
    unregistered = found - set(registered)
    for rel_path in sorted(unregistered):
        errors.append(f"unregistered proof-bearing close-kernel sink: {rel_path}")
    stale = set(registered) - found
    for rel_path in sorted(stale):
        errors.append(f"registered close-kernel sink no longer appears in scanned proof-bearing surface: {rel_path}")

    for rel_path in sorted(CLOSE_KERNEL_V99_REQUIRED_CRITICAL_GATE_FILES):
        if rel_path not in critical_files:
            errors.append(f"close-kernel critical gate file not declared: {rel_path}")
    errors.extend(_check_dependency_floor_provenance_contract(manifest, project_root=project_root))
    return errors


def _fixed_witness_publish_binding_errors(
    *,
    certified_frontier_path: Path = CERTIFIED_FRONTIER_PATH,
    exact_campaign_path: Path = EXACT_CAMPAIGN_PATH,
    capsule_path: Path = TERMINAL_FIXED_WITNESS_CAPSULE_PATH,
) -> list[str]:
    """Require the certified publish path to call the isolated fixed-witness capsule.

    Phase A moves public authority from the in-process diagnostic verifier to
    ``terminal_fixed_witness_capsule.build_terminal_fixed_witness_projection_at_sink``.
    P1.2-FIX-3 makes that exact capsule wiring a hard proof obligation: the
    phase gate's witness-bound close condition cannot be satisfied by a local
    same-name function, an alias, a dead branch, or a path that ignores the
    capsule projection when publishing terminal records.
    """
    errors: list[str] = []
    errors.extend(_fixed_witness_capsule_wiring_errors(capsule_path=capsule_path))
    frontier_tree = _parse_python(certified_frontier_path)
    build_fn = _function_def(
        frontier_tree,
        "build_sink_verified_terminal_frontier_evidence",
        path=certified_frontier_path,
    )
    errors.extend(
        _imported_direct_call_errors(
            tree=frontier_tree,
            function=build_fn,
            path=certified_frontier_path,
            function_label="sink-verified terminal frontier evidence",
            module="src.search.terminal_fixed_witness_capsule",
            name="build_terminal_fixed_witness_projection_at_sink",
        )
    )
    frontier_source = _source_text(certified_frontier_path, build_fn)
    for keyword_name, expected_expr in (
        ("campaign_path", "campaign_path"),
        ("serialized_state_bytes", "serialized_state_bytes"),
    ):
        if not _calls_function_with_keyword_expr(
            build_fn,
            "build_terminal_fixed_witness_projection_at_sink",
            keyword_name,
            expected_expr,
        ):
            errors.append(
                "sink-verified terminal frontier evidence must bind fixed-witness capsule authority: "
                f"{keyword_name}={expected_expr}"
            )
    for token in (
        "fixed_witness_projection.durable_candidate_records",
        "fixed_witness_projection.candidate_records",
        "fixed_witness_projection.verdict.to_dict()",
        "fixed_witness_projection.publishable",
    ):
        if token not in frontier_source:
            errors.append(f"sink-verified terminal frontier evidence must publish capsule field: {token}")
    campaign_tree = _parse_python(exact_campaign_path)
    wrapper_fn = _function_def(
        campaign_tree,
        "terminal_certified_final_result_violation_for_project",
        path=exact_campaign_path,
    )
    wrapper_source = _source_text(exact_campaign_path, wrapper_fn)
    if "_terminal_certified_final_result_violation_for_project_authority" not in wrapper_source:
        errors.append("project-bound terminal validator must delegate to disk authority helper")
    violation_fn = _function_def(
        campaign_tree,
        "_terminal_certified_final_result_violation_for_project_authority",
        path=exact_campaign_path,
    )
    errors.extend(
        _imported_direct_call_errors(
            tree=campaign_tree,
            function=violation_fn,
            path=exact_campaign_path,
            function_label="project-bound terminal validator",
            module="src.search.terminal_fixed_witness_capsule",
            name="build_terminal_fixed_witness_projection_at_sink",
        )
    )
    violation_source = _source_text(exact_campaign_path, violation_fn)
    if not _calls_function_with_keyword_expr(
        violation_fn,
        "build_terminal_fixed_witness_projection_at_sink",
        "campaign_path",
        "campaign_path",
    ):
        errors.append("project-bound terminal validator must bind fixed-witness capsule campaign_path")
    if not _calls_function_with_keyword_expr(
        violation_fn,
        "build_terminal_fixed_witness_projection_at_sink",
        "serialized_state_bytes",
        "authority_bytes",
    ):
        errors.append("project-bound terminal validator must bind fixed-witness capsule authority bytes")
    for token in (
        "fixed_witness_projection.candidate_records",
        "candidate_records_override=replayed_records",
        "terminal_certified_final_result_violation(",
    ):
        if token not in violation_source:
            errors.append(f"project-bound terminal validator must gate on capsule field: {token}")
    return errors


def _check_independent_infeasibility_reverifier_contract(
    *,
    benders_loop_path: Path = BENDERS_LOOP_PATH,
    reverifier_path: Path = INDEPENDENT_INFEASIBILITY_REVERIFIER_PATH,
) -> list[str]:
    """Require whole-layout nogoods to pass independent ∀ re-verification first."""

    errors: list[str] = []
    benders_tree = _parse_python(benders_loop_path)
    if not _top_level_imports_exact_name(
        benders_tree,
        module="src.search.independent_infeasibility_reverifier",
        name="reverify_whole_layout_infeasibility",
    ):
        errors.append(
            "whole-layout nogood funnel must import reverify_whole_layout_infeasibility "
            "from src.search.independent_infeasibility_reverifier without aliasing"
        )
    controller_class = _class_def(benders_tree, "LBBDController", path=benders_loop_path)
    funnel_fn = _method_def(
        controller_class,
        "_add_exact_whole_layout_nogood",
        path=benders_loop_path,
    )
    if _function_shadows_name(funnel_fn, "reverify_whole_layout_infeasibility"):
        errors.append("whole-layout nogood funnel shadows the independent reverifier")
    funnel_source = _source_text(benders_loop_path, funnel_fn)
    reverify_pos = funnel_source.find("reverify_whole_layout_infeasibility(")
    mint_pos = funnel_source.find("self._add_exact_persisted_nogood(")
    if reverify_pos < 0:
        errors.append(
            "whole-layout nogood funnel must call independent infeasibility reverifier"
        )
    if mint_pos < 0:
        errors.append("whole-layout nogood funnel no longer calls persisted nogood mint")
    if reverify_pos >= 0 and mint_pos >= 0 and reverify_pos > mint_pos:
        errors.append(
            "whole-layout nogood funnel must call independent reverifier before "
            "_add_exact_persisted_nogood"
        )
    for token in (
        "independent_infeasibility_reverifier",
        "whole_layout_nogood_independent_reverify_divergence",
        "whole_layout_nogood_independent_reverify_unknown",
        "fail_closed_unknown",
    ):
        if token not in funnel_source:
            errors.append(f"whole-layout nogood reverify gate missing token: {token}")

    reverifier_tree = _parse_python(reverifier_path)
    reverifier_source = reverifier_path.read_text(encoding="utf-8")
    for function_name in (
        "reverify_whole_layout_infeasibility",
        "_reverify_binding_infeasible",
        "_solve_with_independent_cp_sat",
    ):
        _function_def(reverifier_tree, function_name, path=reverifier_path)
    for token in (
        "NAMED-TCB",
        "∀ = INFEASIBLE",
        "PortBindingModel(",
        "cp_model.CpSolver()",
        "cp_model.PORTFOLIO_SEARCH",
        "random_seed",
        "randomize_search",
        "num_search_workers",
        "routing_exhaustion_phase1_conservative_unknown",
    ):
        if token not in reverifier_source:
            errors.append(f"independent infeasibility reverifier missing token: {token}")
    if ".solve(" in reverifier_source:
        errors.append(
            "independent infeasibility reverifier must not call subproblem solve(); "
            "it must use its own heterogeneous CpSolver"
        )
    for child in ast.walk(reverifier_tree):
        if isinstance(child, ast.Import):
            for alias in child.names:
                if alias.name == "os":
                    errors.append(
                        "independent infeasibility reverifier must not import os or "
                        "read EXACT_* env"
                    )
        if isinstance(child, ast.ImportFrom) and child.module == "os":
            errors.append(
                "independent infeasibility reverifier must not import os env helpers"
            )
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "os"
            and child.attr in {"environ", "getenv"}
        ):
            errors.append("independent infeasibility reverifier must not read EXACT_* env")
        if (
            isinstance(child, ast.Attribute)
            and child.attr in {"master", "_solver"}
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
        ):
            errors.append(
                "independent infeasibility reverifier must not read in-flight "
                f"cache authority: self.{child.attr}"
            )
    return errors


def _fixed_witness_capsule_wiring_errors(
    *,
    capsule_path: Path = TERMINAL_FIXED_WITNESS_CAPSULE_PATH,
) -> list[str]:
    errors: list[str] = []
    capsule_tree = _parse_python(capsule_path)
    build_fn = _function_def(
        capsule_tree,
        "build_terminal_fixed_witness_projection_at_sink",
        path=capsule_path,
    )
    for required_call in (
        "_invoke_isolated_capsule",
        "_verdict_from_capsule_response",
        "_capsule_response_violation",
        "_project_terminal_fixed_witness_records_from_capsule",
    ):
        if not _direct_calls_name(build_fn, required_call):
            errors.append(f"fixed-witness capsule must call {required_call}")

    invoke_fn = _function_def(capsule_tree, "_invoke_isolated_capsule", path=capsule_path)
    invoke_source = _source_text(capsule_path, invoke_fn)
    if not _direct_calls_attr(invoke_fn, "run"):
        errors.append("fixed-witness capsule must launch an external subprocess")
    for token in ('"-I"', "nonce", "check=False", "shell=True"):
        if token == "shell=True":
            if token in invoke_source:
                errors.append("fixed-witness capsule subprocess must never use shell=True")
            continue
        if token not in invoke_source:
            errors.append(f"fixed-witness capsule subprocess boundary missing: {token}")

    execute_fn = _function_def(
        capsule_tree,
        "_execute_isolated_capsule_request",
        path=capsule_path,
    )
    errors.extend(
        _imported_direct_call_errors(
            tree=capsule_tree,
            function=execute_fn,
            path=capsule_path,
            function_label="fixed-witness capsule child executor",
            module="src.search.terminal_fixed_witness_verifier",
            name="verify_terminal_fixed_witness",
            allow_local_import=True,
        )
    )
    execute_source = _source_text(capsule_path, execute_fn)
    for token in (
        "compute_exact_artifact_hashes",
        "_materialize_replay_snapshot",
        "canonical_state_bytes_for_fixed_witness",
    ):
        if token not in execute_source:
            errors.append(f"fixed-witness capsule child executor missing binding token: {token}")

    response_fn = _function_def(capsule_tree, "_capsule_response_violation", path=capsule_path)
    response_source = _source_text(capsule_path, response_fn)
    for token in (
        "verdict.publishable",
        "verdict.binding_status",
        "verdict.routing_status",
        '"FEASIBLE"',
    ):
        if token not in response_source:
            errors.append(f"fixed-witness capsule response gate missing: {token}")
    return errors


def _check_phase_gate_fixed_witness_close_binding(*, next_allowed: Any) -> list[str]:
    """Witness-bound close condition for the manual phase gate (P1.2-FIX-3).

    Replaces the prior generic ``next_allowed must stay False`` anchor.  Two
    parts, deliberately separated:

    * The fixed-witness publish binding is enforced **unconditionally** so that
      lifting the stay-blocked sentinel below never silently removes it.  This is
      the durable witness predicate the generic anchor lacked.
    * The stay-blocked sentinel keeps the gate fail-closed while the P1.2
      soundness reopen is unresolved.  When the owner eventually opens P1.3B, the
      witness binding above remains enforced rather than reverting to a shape +
      acknowledgement-only close.
    """
    errors = _fixed_witness_publish_binding_errors()
    if next_allowed is not False:
        errors.append(
            "phase gate must remain blocked while P1.2 soundness reopen is unresolved; "
            "opening P1.3B requires the fixed-witness verifier wired into the publish path"
        )
    return errors


def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_anchor = _require_str(
        manifest.get("phase_gate_required_anchor"),
        "phase_gate_required_anchor",
    )
    manifest_anchor = _require_str(manifest.get("review_anchor"), "review_anchor")
    if manifest_anchor != required_anchor:
        errors.append("manifest.review_anchor must match phase_gate_required_anchor")
    close_kernel = manifest.get("close_kernel_contract")
    close_kernel_anchor = None
    if isinstance(close_kernel, dict):
        close_kernel_anchor = _require_str(
            close_kernel.get("review_anchor"),
            "close_kernel_contract.review_anchor",
        )
        if close_kernel_anchor != required_anchor:
            errors.append("close_kernel_contract.review_anchor must match phase_gate_required_anchor")
    phase_gate = _load_json(PHASE_GATE_PATH)
    current_anchor = phase_gate.get("current_review_anchor")
    owner_state = phase_gate.get("owner_manual_state")
    owner_anchor = owner_state.get("current_review_anchor") if isinstance(owner_state, dict) else None
    next_phase_entry = phase_gate.get("next_phase_entry")
    next_allowed = next_phase_entry.get("allowed") if isinstance(next_phase_entry, dict) else None
    receipt_policy = phase_gate.get("receipt_policy")
    receipt_can_open = receipt_policy.get("can_open_p1_3b") if isinstance(receipt_policy, dict) else None
    for label, value in (
        ("review_anchor", manifest_anchor),
        ("phase_gate_required_anchor", required_anchor),
        ("close_kernel_contract.review_anchor", close_kernel_anchor),
        ("phase gate current_review_anchor", current_anchor),
        ("phase gate owner_manual_state.current_review_anchor", owner_anchor),
    ):
        if isinstance(value, str):
            error = _approved_review_anchor_error(label, value)
        else:
            error = (
                f"{label} must equal approved checker anchor "
                f"{CLOSE_KERNEL_APPROVED_REVIEW_ANCHOR!r}; got {value!r}"
            )
        if error is not None:
            errors.append(error)
    if current_anchor != required_anchor:
        errors.append(f"phase gate current_review_anchor {current_anchor!r} != required {required_anchor!r}")
    if owner_anchor != required_anchor:
        errors.append(f"phase gate owner_manual_state.current_review_anchor {owner_anchor!r} != required {required_anchor!r}")
    errors.extend(_check_phase_gate_fixed_witness_close_binding(next_allowed=next_allowed))
    if receipt_can_open is not False:
        errors.append("phase gate receipt_policy.can_open_p1_3b must remain false")
    return errors


def _check_exact_session_atomic_snapshot_contract(
    *,
    benders_loop_path: Path = BENDERS_LOOP_PATH,
) -> list[str]:
    """Anchor the P1.2-FIX-5 atomic-snapshot contract.

    ExactSearchSession.create must snapshot the frozen artifacts once
    (read_once_exact_artifact_snapshot) and build from those bytes; it must not
    recompute artifact hashes from a second, independent disk read
    (compute_exact_artifact_hashes), which would re-open the load->hash TOCTOU window
    where the recorded hash no longer attests the bytes the master core is built from.
    """

    errors: list[str] = []
    tree = _parse_python(benders_loop_path)
    session_class = _class_def(tree, "ExactSearchSession", path=benders_loop_path)
    create_fn = _method_def(session_class, "create", path=benders_loop_path)
    if not _calls_function(create_fn, "read_once_exact_artifact_snapshot"):
        errors.append(
            "ExactSearchSession.create must snapshot frozen artifacts atomically via "
            "read_once_exact_artifact_snapshot"
        )
    if not _calls_function(create_fn, "load_project_data_from_texts"):
        errors.append(
            "ExactSearchSession.create must parse project data from the snapshotted texts "
            "(load_project_data_from_texts)"
        )
    if _calls_function(create_fn, "compute_exact_artifact_hashes"):
        errors.append(
            "ExactSearchSession.create must not recompute artifact hashes from a second "
            "disk read (TOCTOU)"
        )
    return errors


def main() -> int:
    try:
        manifest = _load_json(MANIFEST_PATH)
        errors: list[str] = []
        try:
            schema_version = _require_int(manifest.get("schema_version"), "schema_version")
        except CheckError as exc:
            errors.append(str(exc))
        else:
            if schema_version != 1:
                errors.append("schema_version must be 1")
        if manifest.get("gate_id") != "p1_2_proof_obligation_consolidation":
            errors.append("gate_id must be p1_2_proof_obligation_consolidation")
        lifecycle_tree = _parse_lifecycle()
        errors.extend(_check_step7_contract(manifest, lifecycle_tree))
        errors.extend(_check_source_digest_contract(manifest))
        errors.extend(_check_source_digest_uses_contract(lifecycle_tree))
        errors.extend(_check_runtime_cache_policy(manifest, lifecycle_tree))
        errors.extend(_check_certified_cut_replay_contract(manifest))
        errors.extend(_check_candidate_sink_replay_contract())
        errors.extend(_check_certified_publication_boundary_contract())
        errors.extend(_check_strong_status_write_allowlist_gate())
        errors.extend(_check_isolated_exec_bytecode_binding_contract())
        errors.extend(_check_evidence_and_tests(manifest))
        errors.extend(_check_close_kernel_checker_self_binding())
        errors.extend(_check_close_kernel_contract(manifest))
        errors.extend(_check_phase_gate_provenance_contract())
        errors.extend(_check_phase_anchor(manifest))
        errors.extend(_check_exact_session_atomic_snapshot_contract())
        errors.extend(_check_independent_infeasibility_reverifier_contract())
    except CheckError as exc:
        print(f"P1.2 proof obligation check failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"P1.2 proof obligation check failed: {len(errors)} issue(s)")
        for error in errors[:50]:
            print(f"  - {error}")
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more")
        return 1

    obligations = len(manifest.get("obligations", []))
    close_kernel = manifest.get("close_kernel_contract")
    sink_count = len(close_kernel.get("sink_files", [])) if isinstance(close_kernel, dict) else 0
    if sink_count:
        print(f"P1.2 proof obligation check passed: {obligations} obligations anchored; {sink_count} proof-bearing sink files sealed")
    else:
        print(f"P1.2 proof obligation check passed: {obligations} obligations anchored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check the P1.2 proof-obligation consolidation manifest.

This is a small structural gate, not a theorem prover.  It makes the P1.2
postmortems concrete enough that future reviews cannot silently drift back to
local, duplicated proof checks.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import weakref
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, NoReturn, Sequence

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
CERTIFIED_ARTIFACT_CONTRACT_PATH = PROJECT_ROOT / "src" / "search" / "certified_artifact_contract.py"
PR2_L0_MICRO_VERIFIER_PATH = PROJECT_ROOT / "src" / "search" / "pr2_l0_micro_verifier_core.py"
PR2_L0_ARTIFACT_CORE_PATH = PROJECT_ROOT / "src" / "search" / "pr2_l0_artifact_core.py"
PR2_L0_FRONTIER_CORE_PATH = PROJECT_ROOT / "src" / "search" / "pr2_l0_frontier_core.py"
PR2_L0_REPLAY_CORE_PATH = PROJECT_ROOT / "src" / "search" / "pr2_l0_replay_core.py"
PR2_L0_FIXED_WITNESS_CORE_PATH = PROJECT_ROOT / "src" / "search" / "pr2_l0_fixed_witness_core.py"
PR2_L0_TRUE_VERIFIER_CHILD_PATH = (
    PROJECT_ROOT / "src" / "search" / "pr2_l0_true_verifier_child.py"
)
PR2_DEPENDENCY_FLOOR_MANIFEST_REL = "data/proof_obligations/pr2_dependency_floor_manifest.json"
PR2_DEPENDENCY_FLOOR_GENERATOR_REL = "scripts/generate_pr2_dependency_floor_manifest.py"
STRONG_STATUS_WRITE_ALLOWLIST_REL = "data/proof_obligations/strong_status_write_allowlist.json"
PR2_DEPENDENCY_FLOOR_MANIFEST_PATH = PROJECT_ROOT / PR2_DEPENDENCY_FLOOR_MANIFEST_REL
PR2_DEPENDENCY_FLOOR_GENERATOR_PATH = PROJECT_ROOT / PR2_DEPENDENCY_FLOOR_GENERATOR_REL
STRONG_STATUS_WRITE_ALLOWLIST_PATH = PROJECT_ROOT / STRONG_STATUS_WRITE_ALLOWLIST_REL
PR2_DEPENDENCY_FLOOR_AUTHORITY = "pr2_l0_dependency_floor_manifest_v1"
PR2_DEPENDENCY_FLOOR_MANIFEST_SHA256 = (
    "a0fe4bdc520cf8aa4b142eb23cf5dc1933c061d973df0be9f3fe1cca1adc2a74"
)
PR2_DEPENDENCY_FLOOR_MANIFEST_SIZE = 567602
PR2_DEPENDENCY_FLOOR_ROOT_SENTINEL = "PYTHON_SYSCONFIG_PURELIB"
PR2_DEPENDENCY_FLOOR_PROVENANCE_STATUS = (
    "deploy_pending_placeholder_regenerate_on_production_cachyos_py313"
)
PR2_DEPENDENCY_FLOOR_GENERATOR_SHA256 = (
    "9efbc3f2f32a56e6b9746604346efd7b6e1ef394fdd3ac9fa6fa7ece3ad33d8c"
)
STRONG_STATUS_WRITE_ALLOWLIST_SHA256 = (
    "7472bba0be7f4de3dc4881ffe5c300ea81b163d9865c0d296b238f91169947c8"
)
STRONG_STATUS_WRITE_ALLOWLIST_SIZE = 51908
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
        "PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION",
    }
)
REQUIRED_TESTS_BY_OBLIGATION_ID = {
    "PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION": frozenset(
        {
            "test_t1_redundant_power_pole_is_pruned_and_non_poles_are_unchanged",
            "test_t2_minimal_covering_set_is_a_noop",
            "test_t3_pruning_iterates_to_a_deterministic_fixed_point",
            "test_t4_all_optional_poles_are_pruned_when_nothing_needs_power",
            "test_t5_mandatory_poles_are_never_pruned_but_affect_reverification",
            "test_t6_positive_required_count_skips_pruning_and_reverifies",
            "test_t7_required_layout_with_unforced_pole_fails_closed",
            "test_t8_malformed_pose_data_always_fails_closed",
            "test_t9_normalization_is_byte_deterministic",
            "test_t10_c1_certified_endpoint_returns_normalized_power_poles",
            "test_t11_legacy_witness_certified_endpoint_is_rejected_fail_closed",
            "test_t12_reverification_matches_terminal_r1_r3_semantics",
            "test_t13_normalization_failure_turns_feasible_routing_into_unknown",
            "test_t14_s3_certified_path_prunes_redundant_pole_without_mutating_input",
        }
    ),
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
            "test_routing_front_blocked_c1_optional_conflict_emits_exact_safe_cut",
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
            "test_batch1d_certified_env_guard_treats_legacy_witness_envs_as_unknown",
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
            "test_v82_terminal_frontier_certified_prune_keeps_one_wider_pending_candidate_canary",
            "test_v82_terminal_frontier_shape_frontier_keeps_transposed_equal_area_canary",
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
            "test_fixed_witness_capsule_projection_rejects_publishable_non_feasible_statuses",
            "test_child_publishable_capsule_verdict_requires_feasible_statuses",
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
            "test_p1_2_close_kernel_self_binding_rejects_dead_branch_calls",
            "test_p1_2_round11_close_kernel_def_time_and_class_body_hardening",
            "test_p1_2_round11_close_kernel_import_dependency_shape_rejects_import_time_mutation",
            "test_p1_2_round13_current_scope_binding_walker_rejects_walrus_and_delete_smuggling",
            "test_p1_2_round13_close_kernel_rejects_import_and_builtin_shadow",
            "test_p1_2_round13_close_kernel_rejects_decorator_drift",
            "test_p1_2_round13_checker_error_collector_integrity",
            "test_p1_2_round13_self_binding_requires_new_gates_and_self_call",
            "test_p1_2_round13_manifest_semantic_projection_rejects_resealed_gutting",
            "test_p1_2_round13_source_text_includes_parenthesized_decorator_start",
            "test_p1_2_round14_close_kernel_rejects_lambda_default_walrus_hidden_bindings",
            "test_p1_2_round14_close_kernel_rejects_runtime_member_hooks_and_writes",
            "test_p1_2_round14_function_shadow_guard_rejects_walrus_and_match_capture",
            "test_p1_2_round14_strong_status_allowlist_bytes_are_pinned",
            "test_p1_2_round14_checker_errors_whitelist_rejects_alias_reflection_and_mutation",
            "test_p1_2_round14_checker_self_integrity_preflight_is_fail_fast",
            "test_p1_2_round14_checker_failure_gate_rejects_exit_and_none_returns",
            "test_p1_2_round14_checker_required_callee_floor_rejects_rebind_and_shrink",
            "test_p1_2_round14_runtime_anchor_rejects_manifest_semantic_projection_mismatch",
            "test_p1_2_round14_close_kernel_accepts_class_builtin_member_without_def_time_use",
            "test_p1_2_round14_checker_accepts_errors_iadd_required_call",
            "test_p1_2_round15_manifest_projection_rejects_top_level_key_drift",
            "test_p1_2_round15_close_kernel_rejects_runtime_reflection_primitive_writes",
            "test_p1_2_round15_close_kernel_rejects_ctypes_native_member_write",
            "test_p1_2_round15_close_kernel_allows_known_safe_runtime_member_forms",
            "test_p1_2_round15_witness_shadow_rejects_comprehension_and_namespace_writes",
            "test_p1_2_round15_witness_shadow_rejects_statement_and_type_binding_forms",
            "test_p1_2_round15_checker_required_callees_are_runtime_bound_before_subprocess",
            "test_p1_2_round15_checker_top_level_closed_world_rejects_dynamic_namespace_rebind",
            "test_p1_2_round15_checker_rejects_errors_match_capture_and_other_rebinds",
            "test_p1_2_round15_checker_rejects_unapproved_accumulator_callee_and_frame_escape",
            "test_p1_2_round15_checker_rejects_side_effectful_errors_append_args",
            "test_p1_2_round15_checker_rejects_floor_tuple_walrus_rebind",
            "test_p1_2_round15_try_star_and_literal_accumulator_concern_canaries",
            "test_p1_2_close_kernel_source_floor_covers_import_time_closure",
            "test_p1_2_close_kernel_rejects_import_time_dependency_drift",
            "test_p1_2_close_kernel_rejects_dependency_floor_generator_drift",
            "test_p1_2_close_kernel_rejects_dependency_floor_manifest_drift",
            "test_p1_2_checker_accepts_pr2_supervisor_ast_pins_current_sources",
            "test_p1_2_checker_rejects_pr2_5_ast_pin_bypass_variants",
            "test_l0_supervisor_seal_mints_strict_declare_mode_from_best_effort_proposal",
            "test_l0_postwrite_state_violation_rejects_non_strict_declare_mode",
            "test_exact_campaign_supervisor_transition_promotes_declare_mode_to_strict",
            "test_true_verifier_child_precheck_receives_strict_certified_scratch_state",
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
    _attach_parent_links(tree)
    return tree


def _attach_parent_links(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_p1_2_parent", weakref.ref(parent))


def _p1_2_parent(node: ast.AST) -> ast.AST | None:
    parent = getattr(node, "_p1_2_parent", None)
    if parent is None:
        return None
    if isinstance(parent, weakref.ReferenceType):
        return parent()
    return parent


def _parse_lifecycle() -> ast.Module:
    return _parse_python(LIFECYCLE_PATH)


def _import_bound_names(stmt: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(stmt, ast.Import):
        return {alias.asname or alias.name.split(".", 1)[0] for alias in stmt.names}
    return {alias.asname or alias.name for alias in stmt.names}


def _target_name_bindings(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names.update(_target_name_bindings(element))
        return names
    if isinstance(target, ast.Starred):
        return _target_name_bindings(target.value)
    return set()


def _pattern_bound_names(pattern: ast.AST) -> set[str]:
    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_MatchAs(self, node: ast.MatchAs) -> None:
            if node.name is not None:
                names.add(node.name)
            if node.pattern is not None:
                self.visit(node.pattern)

        def visit_MatchStar(self, node: ast.MatchStar) -> None:
            if node.name is not None:
                names.add(node.name)

        def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
            if node.rest is not None:
                names.add(node.rest)
            for pattern_node in node.patterns:
                self.visit(pattern_node)

    Visitor().visit(pattern)
    return names


def _type_alias_bound_names(stmt: ast.stmt) -> set[str]:
    type_alias_cls = getattr(ast, "TypeAlias", None)
    if type_alias_cls is None or not isinstance(stmt, type_alias_cls):
        return set()
    name_node = getattr(stmt, "name", None)
    if isinstance(name_node, ast.Name):
        return {name_node.id}
    return set()


def _collect_current_scope_namedexpr_targets(node: ast.AST) -> set[str]:
    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, child: ast.Lambda) -> None:
            for default in child.args.defaults:
                self.visit(default)
            for default in child.args.kw_defaults:
                if default is not None:
                    self.visit(default)

        def visit_NamedExpr(self, child: ast.NamedExpr) -> None:
            names.update(_target_name_bindings(child.target))
            self.visit(child.value)

    Visitor().visit(node)
    return names


def _function_def_time_nodes(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    values: list[ast.AST] = [*node.decorator_list]
    values.extend(node.args.defaults)
    values.extend(default for default in node.args.kw_defaults if default is not None)
    values.extend(arg.annotation for arg in node.args.posonlyargs if arg.annotation is not None)
    values.extend(arg.annotation for arg in node.args.args if arg.annotation is not None)
    values.extend(arg.annotation for arg in node.args.kwonlyargs if arg.annotation is not None)
    if node.args.vararg is not None and node.args.vararg.annotation is not None:
        values.append(node.args.vararg.annotation)
    if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
        values.append(node.args.kwarg.annotation)
    if node.returns is not None:
        values.append(node.returns)
    values.extend(getattr(node, "type_params", ()))
    return values


def _class_def_time_nodes(node: ast.ClassDef) -> list[ast.AST]:
    values: list[ast.AST] = [*node.decorator_list, *node.bases]
    values.extend(keyword.value for keyword in node.keywords)
    values.extend(getattr(node, "type_params", ()))
    return values


_AST_TRY_TYPES = (ast.Try, getattr(ast, "TryStar", ast.Try))


def _type_param_bound_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for type_param in getattr(node, "type_params", ()):
        name = getattr(type_param, "name", None)
        if isinstance(name, str):
            names.add(name)
        elif isinstance(name, ast.Name):
            names.add(name.id)
    return names


def _child_statement_scope_bound_names(statements: Sequence[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for child in statements:
        names.update(_current_scope_bound_names(child))
    return names


def _current_scope_bound_names(stmt: ast.stmt) -> set[str]:
    names: set[str] = set()
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.add(stmt.name)
        names.update(_type_param_bound_names(stmt))
        for node in _function_def_time_nodes(stmt):
            names.update(_collect_current_scope_namedexpr_targets(node))
        return names
    if isinstance(stmt, ast.ClassDef):
        names.add(stmt.name)
        names.update(_type_param_bound_names(stmt))
        for node in _class_def_time_nodes(stmt):
            names.update(_collect_current_scope_namedexpr_targets(node))
        return names
    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            names.update(_target_name_bindings(target))
        names.update(_collect_current_scope_namedexpr_targets(stmt.value))
    elif isinstance(stmt, ast.AnnAssign):
        names.update(_target_name_bindings(stmt.target))
        if stmt.annotation is not None:
            names.update(_collect_current_scope_namedexpr_targets(stmt.annotation))
        if stmt.value is not None:
            names.update(_collect_current_scope_namedexpr_targets(stmt.value))
    elif isinstance(stmt, ast.AugAssign):
        names.update(_target_name_bindings(stmt.target))
        names.update(_collect_current_scope_namedexpr_targets(stmt.value))
    elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
        names.update(_import_bound_names(stmt))
    elif isinstance(stmt, ast.Delete):
        for target in stmt.targets:
            names.update(_target_name_bindings(target))
    elif isinstance(stmt, (ast.Global, ast.Nonlocal)):
        names.update(stmt.names)
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        names.update(_target_name_bindings(stmt.target))
        names.update(_collect_current_scope_namedexpr_targets(stmt.iter))
        names.update(_child_statement_scope_bound_names(stmt.body))
        names.update(_child_statement_scope_bound_names(stmt.orelse))
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        for item in stmt.items:
            if item.optional_vars is not None:
                names.update(_target_name_bindings(item.optional_vars))
            names.update(_collect_current_scope_namedexpr_targets(item.context_expr))
        names.update(_child_statement_scope_bound_names(stmt.body))
    elif isinstance(stmt, _AST_TRY_TYPES):
        names.update(_child_statement_scope_bound_names(stmt.body))
        names.update(_child_statement_scope_bound_names(stmt.orelse))
        names.update(_child_statement_scope_bound_names(stmt.finalbody))
        for handler in stmt.handlers:
            if handler.type is not None:
                names.update(_collect_current_scope_namedexpr_targets(handler.type))
            if handler.name is not None:
                names.add(handler.name)
            names.update(_child_statement_scope_bound_names(handler.body))
    elif isinstance(stmt, ast.While):
        # round-20 (G2): a ``while`` body executes at import/class-exec time, so a
        # rebind inside it (``while True: witness = _noop; break``) must count as a
        # scope binding just like ``if``/``for``/``with``.
        names.update(_collect_current_scope_namedexpr_targets(stmt.test))
        names.update(_child_statement_scope_bound_names(stmt.body))
        names.update(_child_statement_scope_bound_names(stmt.orelse))
    elif isinstance(stmt, ast.If):
        names.update(_collect_current_scope_namedexpr_targets(stmt.test))
        names.update(_child_statement_scope_bound_names(stmt.body))
        names.update(_child_statement_scope_bound_names(stmt.orelse))
    elif isinstance(stmt, ast.Match):
        names.update(_collect_current_scope_namedexpr_targets(stmt.subject))
        for case in stmt.cases:
            names.update(_pattern_bound_names(case.pattern))
            if case.guard is not None:
                names.update(_collect_current_scope_namedexpr_targets(case.guard))
            names.update(_child_statement_scope_bound_names(case.body))
    else:
        names.update(_type_alias_bound_names(stmt))
        names.update(_collect_current_scope_namedexpr_targets(stmt))
    names.update(_type_alias_bound_names(stmt))
    return names


def _direct_statement_bound_names(stmt: ast.stmt) -> set[str]:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {stmt.name}
    if isinstance(stmt, ast.Assign):
        names: set[str] = set()
        for target in stmt.targets:
            names.update(_target_name_bindings(target))
        return names
    if isinstance(stmt, ast.AnnAssign):
        return _target_name_bindings(stmt.target)
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return _import_bound_names(stmt)
    return _type_alias_bound_names(stmt)


def _hidden_current_scope_bound_names(stmt: ast.stmt) -> set[str]:
    return _current_scope_bound_names(stmt) - _direct_statement_bound_names(stmt)


def _top_level_binding_points(tree: ast.Module, name: str) -> list[ast.stmt]:
    return [node for node in tree.body if name in _current_scope_bound_names(node)]


def _class_stmt_bound_names(stmt: ast.stmt) -> set[str]:
    return _current_scope_bound_names(stmt)


def _class_body_binding_points(class_node: ast.ClassDef, name: str) -> list[ast.stmt]:
    return [stmt for stmt in class_node.body if name in _class_stmt_bound_names(stmt)]


def _format_binding_lines(nodes: Sequence[ast.AST]) -> str:
    return ", ".join(str(getattr(node, "lineno", "?")) for node in nodes)


def _function_def(tree: ast.Module, name: str, *, path: Path = LIFECYCLE_PATH) -> ast.FunctionDef:
    binding_points = _top_level_binding_points(tree, name)
    if len(binding_points) > 1:
        lines = _format_binding_lines(binding_points)
        raise CheckError(f"top-level binding for {_rel(path)}::{name} must be unique; found lines {lines}")
    if len(binding_points) == 1:
        node = binding_points[0]
        if isinstance(node, ast.FunctionDef):
            if node.name != name:
                raise CheckError(
                    f"top-level binding for {_rel(path)}::{name} resolved to {node.name}"
                )
            return node
        raise CheckError(f"top-level binding for {_rel(path)}::{name} is not a FunctionDef")
    raise CheckError(f"function not found in {_rel(path)}: {name}")


def _class_def(tree: ast.Module, name: str, *, path: Path) -> ast.ClassDef:
    binding_points = _top_level_binding_points(tree, name)
    if len(binding_points) > 1:
        lines = _format_binding_lines(binding_points)
        raise CheckError(f"top-level binding for {_rel(path)}::{name} must be unique; found lines {lines}")
    if len(binding_points) == 1:
        node = binding_points[0]
        if isinstance(node, ast.ClassDef):
            if node.name != name:
                raise CheckError(
                    f"top-level binding for {_rel(path)}::{name} resolved to {node.name}"
                )
            return node
        raise CheckError(f"top-level binding for {_rel(path)}::{name} is not a ClassDef")
    raise CheckError(f"class not found in {_rel(path)}: {name}")


def _method_def(class_node: ast.ClassDef, name: str, *, path: Path) -> ast.FunctionDef:
    binding_points = _class_body_binding_points(class_node, name)
    qualified = f"{class_node.name}.{name}"
    if len(binding_points) > 1:
        lines = _format_binding_lines(binding_points)
        raise CheckError(f"class binding for {_rel(path)}::{qualified} must be unique; found lines {lines}")
    if len(binding_points) == 1:
        node = binding_points[0]
        if isinstance(node, ast.FunctionDef):
            if node.name != name:
                raise CheckError(
                    f"class binding for {_rel(path)}::{qualified} resolved to {node.name}"
                )
            return node
        raise CheckError(f"class binding for {_rel(path)}::{qualified} is not a FunctionDef")
    raise CheckError(f"method not found in {_rel(path)}: {qualified}")


def _resolve_class_source_pin_node(
    class_node: ast.ClassDef,
    parts: Sequence[str],
    *,
    path: Path,
    prefix: str,
) -> ast.AST:
    if not parts:
        return class_node
    member_name = parts[0]
    qualified = f"{prefix}.{member_name}"
    binding_points = _class_body_binding_points(class_node, member_name)
    if len(binding_points) > 1:
        lines = _format_binding_lines(binding_points)
        raise CheckError(f"class binding for {_rel(path)}::{qualified} must be unique; found lines {lines}")
    if len(binding_points) != 1:
        raise CheckError(f"source pin target not uniquely resolvable in {_rel(path)}: {qualified}")
    node = binding_points[0]
    if len(parts) == 1:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name != member_name:
                raise CheckError(
                    f"source pin target in {_rel(path)} resolved to {node.name}: {qualified}"
                )
            return node
        raise CheckError(f"source pin target in {_rel(path)} is not a def/class: {qualified}")
    if isinstance(node, ast.ClassDef):
        return _resolve_class_source_pin_node(
            node,
            parts[1:],
            path=path,
            prefix=qualified,
        )
    raise CheckError(
        f"source pin target not uniquely resolvable in {_rel(path)}: "
        f"{qualified}.{'.'.join(parts[1:])}"
    )


def _resolve_source_pin_node(tree: ast.Module, name: str, *, path: Path) -> ast.AST:
    """Resolve a source-pin key to its AST node.

    Supports top-level functions/classes, class methods, async members, and
    nested class members. Duplicate or later rebinding of a pinned class member
    fails closed before a hash can be taken from the wrong binding.
    """
    if "." in name:
        class_name, rest = name.split(".", 1)
        class_node = _class_def(tree, class_name, path=path)
        return _resolve_class_source_pin_node(
            class_node,
            rest.split("."),
            path=path,
            prefix=class_name,
        )
    points = _top_level_binding_points(tree, name)
    if len(points) == 1 and isinstance(points[0], (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if points[0].name != name:
            raise CheckError(
                f"source pin target in {_rel(path)} resolved to {points[0].name}: {name}"
            )
        return points[0]
    raise CheckError(f"source pin target not uniquely resolvable in {_rel(path)}: {name}")


def _calls_function(node: ast.AST, name: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name:
            return True
    return False


def _direct_name_call(value: ast.AST) -> ast.Call | None:
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return value
    return None


def _accumulator_callee_call_from_statement(
    stmt: ast.stmt,
    *,
    accumulator_names: frozenset[str],
) -> ast.Call | None:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        if (
            not call.keywords
            and len(call.args) == 1
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "extend"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in accumulator_names
        ):
            return _direct_name_call(call.args[0])
    if (
        isinstance(stmt, ast.AugAssign)
        and isinstance(stmt.op, ast.Add)
        and isinstance(stmt.target, ast.Name)
        and stmt.target.id in accumulator_names
    ):
        return _direct_name_call(stmt.value)
    return None


def _is_errors_extend_call_statement(stmt: ast.stmt, function_name: str) -> bool:
    call = _accumulator_callee_call_from_statement(
        stmt,
        accumulator_names=frozenset({"errors"}),
    )
    return call is not None and call.func.id == function_name


def _statement_sequence_has_live_errors_extend_call(
    statements: Sequence[ast.stmt],
    function_name: str,
    *,
    allow_outer_try: bool = False,
) -> bool:
    return _statement_sequence_has_live_accumulator_call(
        statements,
        function_name,
        accumulator_names=frozenset({"errors"}),
        allow_outer_try=allow_outer_try,
    )


def _statement_sequence_has_live_accumulator_call(
    statements: Sequence[ast.stmt],
    function_name: str,
    *,
    accumulator_names: frozenset[str],
    allow_outer_try: bool = False,
) -> bool:
    for stmt in statements:
        call = _accumulator_callee_call_from_statement(
            stmt,
            accumulator_names=accumulator_names,
        )
        if call is not None and call.func.id == function_name:
            return True
        if allow_outer_try and isinstance(stmt, (ast.Try, ast.TryStar)):
            if _statement_sequence_has_live_accumulator_call(
                stmt.body,
                function_name,
                accumulator_names=accumulator_names,
                allow_outer_try=False,
            ):
                return True
        if isinstance(stmt, (ast.Return, ast.Raise)) or (
            not isinstance(stmt, (ast.Try, ast.TryStar)) and _stmt_has_control_exit(stmt)
        ):
            return False
    return False


def _has_live_errors_extend_call(
    function: ast.FunctionDef,
    function_name: str,
    *,
    allow_outer_try: bool = False,
) -> bool:
    return _statement_sequence_has_live_errors_extend_call(
        function.body,
        function_name,
        allow_outer_try=allow_outer_try,
    )


def _has_live_accumulator_call(
    function: ast.FunctionDef,
    function_name: str,
    *,
    accumulator_names: frozenset[str],
    allow_outer_try: bool = False,
) -> bool:
    return _statement_sequence_has_live_accumulator_call(
        function.body,
        function_name,
        accumulator_names=accumulator_names,
        allow_outer_try=allow_outer_try,
    )


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


def _top_level_import_stmt_imports_exact_name(
    stmt: ast.stmt, *, module: str, name: str
) -> bool:
    if not isinstance(stmt, ast.ImportFrom) or stmt.level != 0 or stmt.module != module:
        return False
    return any(alias.name == name and alias.asname is None for alias in stmt.names)


def _top_level_imports_exact_name(tree: ast.Module, *, module: str, name: str) -> bool:
    return any(
        _top_level_import_stmt_imports_exact_name(node, module=module, name=name)
        for node in tree.body
    )


def _class_body_exec_scope_has_global_or_nonlocal(
    class_node: ast.ClassDef, names: set[str] | None = None
) -> bool:
    """Detect class-body global/nonlocal declarations that execute at import time.

    A top-level class body is executable module code with a temporary local
    namespace.  ``global main; main = ...`` therefore rebinds the module's
    runtime object while remaining invisible to plain top-level binding scans.
    Do not descend into function/lambda bodies, which are definition-time only;
    do descend into nested class bodies because they execute while the outer
    class body executes.
    """

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.found = False

        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            return

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_Global(self, child: ast.Global) -> None:
            if names is None or any(name in names for name in child.names):
                self.found = True

        def visit_Nonlocal(self, child: ast.Nonlocal) -> None:
            if names is None or any(name in names for name in child.names):
                self.found = True

    visitor = Visitor()
    for body_stmt in class_node.body:
        visitor.visit(body_stmt)
        if visitor.found:
            return True
    return False


def _checker_top_level_class_is_inert_exception(stmt: ast.ClassDef) -> bool:
    """Only the checker exception carrier may be a top-level class."""

    return (
        stmt.name == "CheckError"
        and not stmt.decorator_list
        and tuple(ast.unparse(base) for base in stmt.bases) == ("RuntimeError",)
        and not stmt.keywords
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], ast.Pass)
    )


def _top_level_class_global_binding_points(tree: ast.Module, name: str) -> list[ast.ClassDef]:
    return [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and _class_body_exec_scope_has_global_or_nonlocal(node, {name})
    ]


def _module_global_or_nonlocal_declaration_points(
    tree: ast.Module, name: str
) -> list[ast.Global | ast.Nonlocal]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names
    ]


def _top_level_exact_import_runtime_binding_errors(
    tree: ast.Module,
    *,
    module: str,
    name: str,
    path: Path,
    label: str,
) -> list[str]:
    bindings: list[ast.stmt] = list(_top_level_binding_points(tree, name))
    bindings.extend(_top_level_class_global_binding_points(tree, name))
    exact_imports = [
        node
        for node in bindings
        if _top_level_import_stmt_imports_exact_name(node, module=module, name=name)
    ]
    global_declarations = _module_global_or_nonlocal_declaration_points(tree, name)
    # round-20 (G2): a ``from other import *`` after the exact import can shadow
    # ``name`` at runtime while contributing no ``Name`` binding point, and a
    # multi-alias ``from M import name, fake as name`` binds ``name`` twice inside
    # a single statement (one binding point, but the second alias wins at runtime).
    # Neither was caught by the statement-level binding count.
    wildcard_imports = [
        stmt
        for stmt in tree.body
        if isinstance(stmt, ast.ImportFrom)
        and any(alias.name == "*" for alias in stmt.names)
    ]
    unclean_exact_imports = [
        node for node in exact_imports if not _import_from_binds_name_cleanly(node, name)
    ]
    errors: list[str] = []
    if not (len(bindings) == 1 and len(exact_imports) == 1 and not global_declarations):
        lines = _format_binding_lines(bindings) if bindings else "none"
        declaration_lines = (
            _format_binding_lines(global_declarations) if global_declarations else "none"
        )
        errors.append(
            f"{label} imported symbol {_rel(path)}::{name} must have exactly one "
            f"module-level runtime binding, the exact import from {module}; "
            f"found binding lines {lines}; global/nonlocal declaration lines {declaration_lines}"
        )
    if wildcard_imports:
        errors.append(
            f"{label} imported symbol {_rel(path)}::{name} must not share the module "
            f"top level with a wildcard import (from ... import *); found lines "
            f"{_format_binding_lines(wildcard_imports)}"
        )
    if unclean_exact_imports:
        errors.append(
            f"{label} imported symbol {_rel(path)}::{name} must be bound by a single "
            f"unaliased exact import from {module}; the import statement also rebinds "
            f"{name} via a second alias"
        )
    return errors


def _import_from_binds_name_cleanly(stmt: ast.stmt, name: str) -> bool:
    """round-20 (G2): whether ``stmt`` binds ``name`` via exactly one unaliased
    ``from M import name`` alias and no other alias in the same statement rebinds
    ``name`` (``from M import name, fake as name``)."""
    if not isinstance(stmt, ast.ImportFrom):
        return False
    binding_aliases = [alias for alias in stmt.names if (alias.asname or alias.name) == name]
    return (
        len(binding_aliases) == 1
        and binding_aliases[0].asname is None
        and binding_aliases[0].name == name
    )


def _top_level_protected_binding_rebind_errors(
    tree: ast.Module,
    *,
    path: Path,
    label: str,
    protected_names: frozenset[str],
) -> list[str]:
    """round-20 (G3): fail closed on a module-top-level dynamic rebind of a
    protected witness/carrier symbol in a witness-carrier file.

    The witness-binding contract counts ``Name`` binding points, but a carrier
    file can rebind a protected symbol without producing a ``Name`` binding: via
    a dynamic namespace write (``globals()["witness"] = _noop``), a module/class
    attribute write (``LBBDController._add_exact_whole_layout_nogood = _noop``,
    ``carrier.__code__ = other.__code__``), a bare ``setattr(...)``, or an
    import-time ``_x = globals().__setitem__("witness", _noop)`` on an otherwise
    ``Name``-target assignment.  Carriers are large real modules, so unlike the
    checker's own whitelist closed world this is a targeted denylist keyed on the
    protected names -- it leaves unrelated top-level attribute writes alone.
    """
    errors: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for target in targets:
                if isinstance(target, ast.Subscript):
                    errors.append(
                        f"{label} {_rel(path)} must not dynamically write a module or "
                        f"class namespace at module top level (line {stmt.lineno})"
                    )
                elif isinstance(target, ast.Attribute):
                    base_is_protected = (
                        isinstance(target.value, ast.Name)
                        and target.value.id in protected_names
                    )
                    if target.attr in protected_names or base_is_protected:
                        errors.append(
                            f"{label} {_rel(path)} must not rebind a protected symbol via "
                            f"an attribute write at module top level (line {stmt.lineno})"
                        )
            if _expr_contains_import_time_rebind_primitive(getattr(stmt, "value", None)) is not None:
                errors.append(
                    f"{label} {_rel(path)} must not evaluate a namespace-write primitive "
                    f"at module top level (line {stmt.lineno})"
                )
            if _expr_contains_import_time_rebind_primitive(getattr(stmt, "annotation", None)) is not None:
                errors.append(
                    f"{label} {_rel(path)} must not evaluate a namespace-write primitive "
                    f"in a module-top-level annotation (line {stmt.lineno})"
                )
        elif isinstance(stmt, ast.Expr):
            if _expr_contains_import_time_rebind_primitive(stmt.value) is not None:
                errors.append(
                    f"{label} {_rel(path)} must not call a namespace-write primitive "
                    f"at module top level (line {stmt.lineno})"
                )
    return errors


_PROTECTED_CLASS_LOOKUP_HOOK_NAMES = frozenset(
    {"__getattribute__", "__getattr__", "__setattr__", "__delattr__"}
)


def _class_defines_attribute_lookup_hooks(class_node: ast.ClassDef) -> list[str]:
    """round-20 (G3): names of instance attribute lookup/write hooks defined on a
    class body.  Such a hook can redirect ``self.<method>(...)`` at runtime even
    though the checked ``FunctionDef`` for ``<method>`` is unchanged."""
    return [
        member.name
        for member in class_node.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and member.name in _PROTECTED_CLASS_LOOKUP_HOOK_NAMES
    ]


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
        parent = _p1_2_parent(root)
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
            for default in child.args.defaults:
                self.visit(default)
            for default in child.args.kw_defaults:
                if default is not None:
                    self.visit(default)

        def _visit_comprehension_outer_inputs(
            self,
            generators: Sequence[ast.comprehension],
        ) -> None:
            if not generators:
                return
            first = generators[0]
            self.visit(first.iter)
            for if_clause in first.ifs:
                self.visit(if_clause)

        def visit_ListComp(self, child: ast.ListComp) -> None:
            self._visit_comprehension_outer_inputs(child.generators)

        def visit_SetComp(self, child: ast.SetComp) -> None:
            self._visit_comprehension_outer_inputs(child.generators)

        def visit_DictComp(self, child: ast.DictComp) -> None:
            self._visit_comprehension_outer_inputs(child.generators)

        def visit_GeneratorExp(self, child: ast.GeneratorExp) -> None:
            self._visit_comprehension_outer_inputs(child.generators)

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


def _literal_string_value(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _slice_literal_string_value(node: ast.AST) -> str | None:
    return _literal_string_value(node)


def _call_returns_dynamic_namespace_object(call: ast.Call) -> bool:
    call_name = _call_func_name(call)
    return call_name in {"globals", "locals", "vars"}


def _node_is_dynamic_namespace_object(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_returns_dynamic_namespace_object(node)


def _namespace_key_may_name(node: ast.AST | None, name: str) -> bool:
    value = _literal_string_value(node) if node is not None else None
    return value is None or value == name


def _dict_literal_may_set_key(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Dict):
        return True
    for key in node.keys:
        if key is None or _namespace_key_may_name(key, name):
            return True
    return False


def _dynamic_namespace_subscript_shadows_name(node: ast.Subscript, name: str) -> bool:
    if not _node_is_dynamic_namespace_object(node.value):
        return False
    return _namespace_key_may_name(node.slice, name)


def _dynamic_namespace_write_shadows_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Subscript)
                and _dynamic_namespace_subscript_shadows_name(target, name)
            ):
                return True
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if not _node_is_dynamic_namespace_object(node.func.value):
        return False
    method = node.func.attr
    if method == "clear":
        return True
    if method in {"__setitem__", "setdefault", "pop"}:
        return _namespace_key_may_name(node.args[0] if node.args else None, name)
    if method == "update":
        if not node.args:
            return bool(node.keywords)
        return _dict_literal_may_set_key(node.args[0], name) or bool(node.keywords)
    return False


# round-17 (A4 convergence): a proof direct-call witness function rebinds its
# fixed-witness symbol only by writing the module global namespace, which must
# route through one of a finite set of namespace/dynamic-exec/reflection
# primitives.  round-16 only caught ``exec``/``eval``/``__import__``; the panel
# then found ``operator.setitem(globals(), ...)`` / ``dict.__setitem__(globals(),
# ...)`` / ``getattr(globals(), "__setitem__")`` / ``types.FunctionType(compile(
# ...), globals())()``.  Rather than keep enumerating call shapes (a denylist
# that keeps leaking), fail closed on *any reference* to the whole primitive
# surface inside a witness body -- every rebind construction names at least one
# of these.  All current proof witnesses reference none of them.
_PR2_WITNESS_BODY_FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "compile",
        "ctypes",
        "delattr",
        "eval",
        "exec",
        "gc",
        "globals",
        "importlib",
        "inspect",
        "locals",
        "operator",
        "setattr",
        "types",
        "vars",
    }
)
# round-18 (owner decision 2026-07-02): the A4 witness-body dynamic-reflection
# rebind surface does NOT converge as a denylist -- ``func.__globals__[name]=`` /
# ``sys._getframe().f_globals[name]=`` / ``sys.modules[__name__].name=`` all reach
# the module namespace by yet another primitive.  The witness source files are
# byte-pinned (source_sha256 / V99 floor), so editing a witness body to rebind is
# a conspicuous diff caught by human clean-review -- the SAME accepted-residual
# class as F (#5-F import-time execution integrity) and the checker-self residual.
# Per owner ruling this is treated as a BEST-EFFORT gate + conspicuous-edit /
# clean-review residual, NOT a release blocker.  These sets catch the known forms
# (dynamic-exec + namespace/frame/function-object reach + attribute-target rebind);
# completeness of the reflection surface is a clean-review responsibility.
_PR2_WITNESS_BODY_FORBIDDEN_ATTRS = frozenset(
    {
        "__delattr__",
        "__dict__",
        "__globals__",
        "__setattr__",
        "__setitem__",
        "f_back",
        "f_globals",
        "f_locals",
        "tb_frame",
    }
)


def _function_shadows_name(
    node: ast.FunctionDef,
    name: str,
    *,
    allowed_import_module: str | None = None,
) -> bool:
    if name in _type_param_bound_names(node):
        return True
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
        if _dynamic_namespace_write_shadows_name(child, name):
            return True
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (
            child.name == name or name in _type_param_bound_names(child)
        ):
            return True
        if isinstance(child, ast.NamedExpr):
            if name in _target_name_bindings(child.target):
                return True
        if isinstance(child, ast.comprehension):
            if name in _store_target_names(child.target):
                return True
        if isinstance(child, ast.Match):
            for case in child.cases:
                if name in _pattern_bound_names(case.pattern):
                    return True
        if isinstance(child, (ast.Global, ast.Nonlocal)) and name in child.names:
            return True
        if name in _type_alias_bound_names(child):
            return True
        if isinstance(child, ast.Delete):
            if any(name in _target_name_bindings(target) for target in child.targets):
                return True
        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: list[ast.AST] = []
            if isinstance(child, ast.Assign):
                targets.extend(child.targets)
            else:
                targets.append(child.target)
            if any(name in _store_target_names(target) for target in targets):
                return True
            # round-18 (owner best-effort residual): ``<module-expr>.<name> = ...``
            # (an Attribute-target assign whose attr is the witness symbol, e.g.
            # ``sys.modules[__name__].build_terminal_... = fake``) rebinds the
            # module global via attribute write; catch it as a shadow.
            if any(
                isinstance(target, ast.Attribute) and target.attr == name
                for target in targets
            ):
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
        if isinstance(child, ast.Name) and child.id in _PR2_WITNESS_BODY_FORBIDDEN_NAMES:
            return True
        if isinstance(child, ast.Attribute) and child.attr in _PR2_WITNESS_BODY_FORBIDDEN_ATTRS:
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
    if has_top_level_import:
        errors.extend(
            _top_level_exact_import_runtime_binding_errors(
                tree, module=module, name=name, path=path, label=function_label
            )
        )
    if function.decorator_list:
        errors.append(
            f"{function_label} must be undecorated so its runtime binding is the "
            f"checked FunctionDef in {_rel(path)}"
        )
    function_global_declarations = _module_global_or_nonlocal_declaration_points(
        tree, function.name
    )
    if function_global_declarations:
        errors.append(
            f"{function_label} checked function {_rel(path)}::{function.name} must not "
            "be named by module-level global/nonlocal declarations; found lines "
            f"{_format_binding_lines(function_global_declarations)}"
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
    errors.extend(
        _top_level_protected_binding_rebind_errors(
            tree,
            path=path,
            label=function_label,
            protected_names=frozenset({name, function.name}),
        )
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
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.decorator_list:
        start_lineno = min(
            getattr(decorator, "lineno", getattr(node, "lineno", 1))
            for decorator in node.decorator_list
        )
        end_lineno = getattr(node, "end_lineno", None)
        if end_lineno is not None:
            lines = source.splitlines(keepends=True)
            while start_lineno > 1 and not lines[start_lineno - 1].lstrip().startswith("@"):
                previous = lines[start_lineno - 2]
                if previous.lstrip().startswith("@"):
                    start_lineno -= 1
                    break
                start_lineno -= 1
            return "".join(lines[start_lineno - 1 : end_lineno])
    return ast.get_source_segment(source, node) or ""


def _normalized_source_text(path: Path, node: ast.AST) -> str:
    return textwrap.dedent(_source_text(path, node)).rstrip("\n")


def _normalized_source_sha256(path: Path, node: ast.AST) -> str:
    return hashlib.sha256(_normalized_source_text(path, node).encode("utf-8")).hexdigest()


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
        parent = _p1_2_parent(current)
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
        parent = _p1_2_parent(current)
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


P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELD = "semantic_projection_sha256"
P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256 = (
    "01417c60a776c460ad2123af6f5f558e86cb33259a6a38e704048c6059fec262"
)
_P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELDS = (
    "schema_version",
    "gate_id",
    "status",
    "review_anchor",
    "summary",
    "phase_gate_required_anchor",
    "step_7_contract",
    "source_digest_contract",
    "certified_cut_replay_contract",
    "obligations",
    "close_kernel_contract",
)
_P1_2_PROOF_OBLIGATION_REVIEWED_TOP_LEVEL_FIELDS = frozenset(
    _P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELDS
    + (
        "updated_at",
        P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELD,
    )
)
_PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR = (
    "_check_step7_contract",
    "_check_source_digest_contract",
    "_check_source_digest_uses_contract",
    "_check_runtime_cache_policy",
    "_check_certified_cut_replay_contract",
    "_check_candidate_sink_replay_contract",
    "_check_certified_publication_boundary_contract",
    "_check_strong_status_write_allowlist_gate",
    "_check_isolated_exec_bytecode_binding_contract",
    "_check_evidence_and_tests",
    "_check_close_kernel_checker_self_binding",
    "_check_error_collector_integrity",
    "_check_main_self_integrity_preflight_shape",
    "_check_main_error_reporting_shape",
    "_check_error_collector_return_shape",
    "_check_proof_obligation_manifest_semantic_projection",
    "_check_close_kernel_contract",
    "_check_certified_artifact_contract_runtime_anchor",
    "_check_phase_gate_provenance_contract",
    "_check_phase_anchor",
    "_check_exact_session_atomic_snapshot_contract",
    "_check_independent_infeasibility_reverifier_contract",
)
_PR2_CHECKER_MAIN_REQUIRED_CALLS = (
    "_check_step7_contract",
    "_check_source_digest_contract",
    "_check_source_digest_uses_contract",
    "_check_runtime_cache_policy",
    "_check_certified_cut_replay_contract",
    "_check_candidate_sink_replay_contract",
    "_check_certified_publication_boundary_contract",
    "_check_strong_status_write_allowlist_gate",
    "_check_isolated_exec_bytecode_binding_contract",
    "_check_evidence_and_tests",
    "_check_close_kernel_checker_self_binding",
    "_check_error_collector_integrity",
    "_check_main_self_integrity_preflight_shape",
    "_check_main_error_reporting_shape",
    "_check_error_collector_return_shape",
    "_check_proof_obligation_manifest_semantic_projection",
    "_check_close_kernel_contract",
    "_check_certified_artifact_contract_runtime_anchor",
    "_check_phase_gate_provenance_contract",
    "_check_phase_anchor",
    "_check_exact_session_atomic_snapshot_contract",
    "_check_independent_infeasibility_reverifier_contract",
)
_PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS_FLOOR = (
    "_check_unique_top_level_bindings",
    "_check_terminal_final_result_violation_structure",
    "_check_terminal_project_precheck_structure",
    "_check_validate_terminal_solution_structure",
    "_check_terminal_ghost_pick_structure",
    "_check_exact_runtime_tcb_source_pins",
    "_check_l0_runtime_tcb_bindings",
    "_check_l0_supervisor_seal_body",
    "_check_literal_strict_slot_assignment",
    "_check_live_top_level_postwrite_guard",
    "_check_l0_child_verdict_dataflow",
    "_check_l0_supervisor_gate_result_flow",
    "_check_l0_supervisor_seal_state_body",
    "_check_child_module_toplevel_closed_world",
    "_check_true_child_runtime_tcb_source_pins",
    "_check_close_kernel_import_dependency_import_time_shape",
    "_check_true_verifier_entrypoint_body",
    "_check_child_verify_supervisor_domain_body",
    "_check_call_result_flow_to_truthy_consumer",
    "_check_call_assignment_no_rebind",
    "_check_expr_result_flow_to_truthy_consumer",
    "_check_true_verifier_child_domain_elevation_window",
    "_check_true_verifier_child_closed_world",
    "_check_true_verifier_child_return_dict_closed_world",
    "_check_child_project_records_body",
    "_check_child_project_candidate_records_direct_structure",
    "_check_child_fixed_witness_body",
    "_check_child_fixed_witness_direct_structure",
    "_check_publisher_transaction_shape",
    "_check_close_kernel_files_fully_pinned",
)
_PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS = (
    "_check_unique_top_level_bindings",
    "_check_terminal_final_result_violation_structure",
    "_check_terminal_project_precheck_structure",
    "_check_validate_terminal_solution_structure",
    "_check_terminal_ghost_pick_structure",
    "_check_exact_runtime_tcb_source_pins",
    "_check_l0_runtime_tcb_bindings",
    "_check_l0_supervisor_seal_body",
    "_check_literal_strict_slot_assignment",
    "_check_live_top_level_postwrite_guard",
    "_check_l0_child_verdict_dataflow",
    "_check_l0_supervisor_gate_result_flow",
    "_check_l0_supervisor_seal_state_body",
    "_check_child_module_toplevel_closed_world",
    "_check_true_child_runtime_tcb_source_pins",
    "_check_close_kernel_import_dependency_import_time_shape",
    "_check_true_verifier_entrypoint_body",
    "_check_child_verify_supervisor_domain_body",
    "_check_call_result_flow_to_truthy_consumer",
    "_check_call_assignment_no_rebind",
    "_check_expr_result_flow_to_truthy_consumer",
    "_check_true_verifier_child_domain_elevation_window",
    "_check_true_verifier_child_closed_world",
    "_check_true_verifier_child_return_dict_closed_world",
    "_check_child_project_records_body",
    "_check_child_project_candidate_records_direct_structure",
    "_check_child_fixed_witness_body",
    "_check_child_fixed_witness_direct_structure",
    "_check_publisher_transaction_shape",
    "_check_close_kernel_files_fully_pinned",
)
_PR2_ERROR_DESTRUCTIVE_METHODS = frozenset(
    {
        "__delitem__",
        "__init__",
        "__setitem__",
        "clear",
        "insert",
        "pop",
        "remove",
        "reverse",
        "sort",
    }
)
_PR2_DYNAMIC_EXECUTION_NAMES = frozenset(
    {
        "__import__",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "object.__setattr__",
        "setattr",
        "type.__setattr__",
        "vars",
    }
)
_PR2_DYNAMIC_EXECUTION_ATTRS = frozenset({"f_globals", "f_locals", "f_back"})


def _clone_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _clone_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    return value


def _proof_obligation_manifest_semantic_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    projection: dict[str, Any] = {}
    for field in _P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELDS:
        value = _clone_json_value(manifest.get(field))
        if field == "close_kernel_contract" and isinstance(value, dict):
            sink_files = value.get("sink_files")
            if isinstance(sink_files, list):
                value["sink_files"] = [
                    {
                        key: item
                        for key, item in sink.items()
                        if key != "source_sha256"
                    }
                    if isinstance(sink, dict)
                    else sink
                    for sink in sink_files
                ]
        projection[field] = value
    return projection


def _proof_obligation_manifest_semantic_projection_sha256(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(
        _proof_obligation_manifest_semantic_projection(manifest),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_proof_obligation_manifest_semantic_projection(
    manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    actual_fields = frozenset(manifest)
    extra_fields = actual_fields - _P1_2_PROOF_OBLIGATION_REVIEWED_TOP_LEVEL_FIELDS
    missing_fields = _P1_2_PROOF_OBLIGATION_REVIEWED_TOP_LEVEL_FIELDS - actual_fields
    if extra_fields:
        errors.append(
            "proof-obligation manifest has unreviewed top-level fields outside the "
            f"semantic projection floor: {sorted(extra_fields)!r}"
        )
    if missing_fields:
        errors.append(
            "proof-obligation manifest is missing reviewed top-level fields from the "
            f"semantic projection floor: {sorted(missing_fields)!r}"
        )
    declared = manifest.get(P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELD)
    if declared != P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256:
        errors.append(
            "proof-obligation manifest semantic projection digest field must match "
            "the checker-reviewed P1.2 floor"
        )
    actual = _proof_obligation_manifest_semantic_projection_sha256(manifest)
    if actual != P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256:
        errors.append(
            "proof-obligation manifest semantic projection drifted from the reviewed P1.2 floor"
        )
    return errors


def _iter_current_function_scope_nodes(function: ast.FunctionDef) -> Iterator[ast.AST]:
    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.nodes: list[ast.AST] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is function:
                self.nodes.append(node)
                for stmt in node.body:
                    self.visit(stmt)
                return
            self.nodes.append(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.nodes.append(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.nodes.append(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            self.nodes.append(node)

        def generic_visit(self, node: ast.AST) -> None:
            self.nodes.append(node)
            super().generic_visit(node)

    visitor = Visitor()
    visitor.visit(function)
    return iter(visitor.nodes)


def _function_local_binding_names(function: ast.FunctionDef) -> set[str]:
    names = set(_function_scope_binding_names(function))
    for node in _iter_current_function_scope_nodes(function):
        if isinstance(node, ast.NamedExpr):
            names.update(_target_name_bindings(node.target))
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                names.update(_target_name_bindings(target))
        elif isinstance(node, ast.Match):
            for case in node.cases:
                names.update(_pattern_bound_names(case.pattern))
    return names


def _is_errors_literal_list_initialization(stmt: ast.AST) -> bool:
    if isinstance(stmt, ast.AnnAssign):
        return (
            isinstance(stmt.target, ast.Name)
            and stmt.target.id == "errors"
            and ast.unparse(stmt.annotation) == "list[str]"
            and isinstance(stmt.value, ast.List)
            and not stmt.value.elts
        )
    return False


def _is_str_constant_list(node: ast.AST) -> bool:
    return isinstance(node, ast.List) and all(
        isinstance(item, ast.Constant) and isinstance(item.value, str)
        for item in node.elts
    )


def _is_errors_literal_extend_or_iadd_statement(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        return (
            not call.keywords
            and len(call.args) == 1
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "extend"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "errors"
            and _is_str_constant_list(call.args[0])
        )
    return (
        isinstance(stmt, ast.AugAssign)
        and isinstance(stmt.op, ast.Add)
        and isinstance(stmt.target, ast.Name)
        and stmt.target.id == "errors"
        and _is_str_constant_list(stmt.value)
    )


def _is_print_errors_call(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "_print_p1_2_errors"
        and len(stmt.value.args) == 1
        and not stmt.value.keywords
        and isinstance(stmt.value.args[0], ast.Name)
        and stmt.value.args[0].id == "errors"
    )


def _errors_failure_gate_has_allowed_body(stmt: ast.If) -> bool:
    if len(stmt.body) == 1:
        return _direct_return_value(stmt.body[0], 1)
    if len(stmt.body) == 2:
        return _is_print_errors_call(stmt.body[0]) and _direct_return_value(stmt.body[1], 1)
    return False


def _statement_is_errors_failure_gate(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.If):
        return False
    if not (isinstance(stmt.test, ast.Name) and stmt.test.id == "errors"):
        return False
    return not stmt.orelse and _errors_failure_gate_has_allowed_body(stmt)


def _errors_failure_gate(function: ast.FunctionDef) -> ast.If | None:
    for stmt in function.body:
        if _statement_is_errors_failure_gate(stmt):
            return stmt
    return None


def _direct_return_value(stmt: ast.stmt, value: object) -> bool:
    return (
        isinstance(stmt, ast.Return)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value == value
    )


def _enclosing_statement(node: ast.AST) -> ast.stmt | None:
    current = node
    while True:
        parent = _p1_2_parent(current)
        if parent is None:
            return None
        if isinstance(parent, ast.stmt):
            return parent
        current = parent


def _is_errors_append_statement(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and stmt.value.func.attr == "append"
        and isinstance(stmt.value.func.value, ast.Name)
        and stmt.value.func.value.id == "errors"
    )


def _is_errors_extend_or_iadd_callee_statement(stmt: ast.stmt) -> bool:
    return (
        _accumulator_callee_call_from_statement(
            stmt,
            accumulator_names=frozenset({"errors"}),
        )
        is not None
    )


def _errors_name_reference_is_whitelisted(
    node: ast.Name,
    *,
    function_name: str,
) -> bool:
    stmt = _enclosing_statement(node)
    if stmt is None:
        return False
    parent = _p1_2_parent(node)
    if _is_errors_literal_list_initialization(stmt):
        return isinstance(stmt, ast.AnnAssign) and stmt.target is node
    if _is_errors_literal_extend_or_iadd_statement(stmt):
        if isinstance(stmt, ast.AugAssign):
            return stmt.target is node
        return (
            isinstance(parent, ast.Attribute)
            and parent.value is node
            and parent.attr == "extend"
        )
    if _is_errors_extend_or_iadd_callee_statement(stmt):
        if isinstance(stmt, ast.AugAssign):
            return stmt.target is node
        return (
            isinstance(parent, ast.Attribute)
            and parent.value is node
            and parent.attr == "extend"
        )
    if _is_errors_append_statement(stmt):
        return (
            isinstance(parent, ast.Attribute)
            and parent.value is node
            and parent.attr == "append"
        )
    if _statement_is_errors_failure_gate(stmt):
        if isinstance(stmt, ast.If) and stmt.test is node:
            return True
        if (
            isinstance(parent, ast.Call)
            and _call_func_name(parent) == "_print_p1_2_errors"
            and parent.args == [node]
        ):
            return True
        return False
    if function_name == "_check_candidate_sink_replay_contract":
        return isinstance(stmt, ast.Return) and stmt.value is node
    return False


def _call_is_dynamic_checker_primitive(call: ast.Call) -> str | None:
    call_name = _call_func_name(call)
    if call_name in _PR2_DYNAMIC_EXECUTION_NAMES:
        return call_name
    if call_name is not None and call_name.startswith("importlib."):
        return call_name
    if call_name in {"sys._getframe", "inspect.currentframe"}:
        return call_name
    return None


def _node_references_dynamic_checker_namespace(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        if node.attr in _PR2_DYNAMIC_EXECUTION_ATTRS:
            return node.attr
        if node.attr == "_getframe" and isinstance(node.value, ast.Name) and node.value.id == "sys":
            return "sys._getframe"
        if node.attr == "modules" and isinstance(node.value, ast.Name) and node.value.id == "sys":
            return "sys.modules"
        if isinstance(node.value, ast.Name) and node.value.id == "importlib":
            return f"importlib.{node.attr}"
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "modules"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
    ):
        return "sys.modules[...]"
    return None


def _expr_is_side_effect_free_errors_append_arg(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        return False
    if isinstance(node, (ast.NamedExpr, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return False
    if isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
        return False
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Attribute):
        return _expr_is_side_effect_free_errors_append_arg(node.value)
    if isinstance(node, ast.JoinedStr):
        return all(
            isinstance(value, ast.Constant)
            or (
                isinstance(value, ast.FormattedValue)
                and _expr_is_side_effect_free_errors_append_arg(value.value)
            )
            for value in node.values
        )
    if isinstance(node, ast.BinOp):
        return _expr_is_side_effect_free_errors_append_arg(node.left) and _expr_is_side_effect_free_errors_append_arg(node.right)
    if isinstance(node, ast.Subscript):
        return _expr_is_side_effect_free_errors_append_arg(node.value) and _expr_is_side_effect_free_errors_append_arg(node.slice)
    if isinstance(node, ast.Tuple):
        return all(_expr_is_side_effect_free_errors_append_arg(item) for item in node.elts)
    if isinstance(node, ast.UnaryOp):
        return _expr_is_side_effect_free_errors_append_arg(node.operand)
    return False


def _errors_append_purity_errors(stmt: ast.stmt, *, label: str) -> list[str]:
    if not _is_errors_append_statement(stmt):
        return []
    assert isinstance(stmt, ast.Expr)
    call = stmt.value
    assert isinstance(call, ast.Call)
    errors: list[str] = []
    if call.keywords or len(call.args) != 1:
        errors.append(f"{label} errors.append must take exactly one positional pure argument")
        return errors
    if not _expr_is_side_effect_free_errors_append_arg(call.args[0]):
        errors.append(
            f"{label} errors.append argument must be side-effect-free at line "
            f"{getattr(call, 'lineno', '?')}"
        )
    return errors


def _errors_binding_integrity_errors(function: ast.FunctionDef, *, label: str) -> list[str]:
    errors: list[str] = []
    init_count = 0
    arguments = (
        list(function.args.posonlyargs)
        + list(function.args.args)
        + list(function.args.kwonlyargs)
    )
    if function.args.vararg is not None:
        arguments.append(function.args.vararg)
    if function.args.kwarg is not None:
        arguments.append(function.args.kwarg)
    for argument in arguments:
        if argument.arg == "errors":
            errors.append(f"{label} must not bind errors as a parameter")
    for node in _iter_current_function_scope_nodes(function):
        if node is function:
            continue
        if isinstance(node, ast.AnnAssign) and _is_errors_literal_list_initialization(node):
            init_count += 1
            continue
        if isinstance(node, ast.AugAssign) and (
            _is_errors_literal_extend_or_iadd_statement(node)
            or _is_errors_extend_or_iadd_callee_statement(node)
        ):
            continue
        binds_errors = False
        if isinstance(node, ast.NamedExpr):
            binds_errors = "errors" in _target_name_bindings(node.target)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            binds_errors = any("errors" in _store_target_names(target) for target in targets)
        elif isinstance(node, ast.Delete):
            binds_errors = any("errors" in _target_name_bindings(target) for target in node.targets)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            binds_errors = "errors" in _store_target_names(node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            binds_errors = any(
                item.optional_vars is not None
                and "errors" in _store_target_names(item.optional_vars)
                for item in node.items
            )
        elif isinstance(node, ast.ExceptHandler):
            binds_errors = node.name == "errors"
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            binds_errors = "errors" in _import_bound_names(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            binds_errors = node.name == "errors" or "errors" in _type_param_bound_names(node)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            binds_errors = "errors" in node.names
        elif isinstance(node, ast.Match):
            binds_errors = any(
                "errors" in _pattern_bound_names(case.pattern)
                for case in node.cases
            )
        elif isinstance(node, ast.comprehension):
            binds_errors = "errors" in _store_target_names(node.target)
        elif "errors" in _type_alias_bound_names(node):
            binds_errors = True
        if binds_errors:
            errors.append(
                f"{label} must not bind errors except errors: list[str] = [] "
                f"at line {getattr(node, 'lineno', '?')}"
            )
    if init_count != 1:
        errors.append(f"{label} must initialize errors exactly once as errors: list[str] = []")
    return errors


_PR2_ACCUMULATOR_CALLEE_DYNAMIC_MODULES = frozenset(
    {"ctypes", "operator", "functools", "importlib"}
)
_PR2_ACCUMULATOR_CALLEE_DYNAMIC_IMPORT_MODULES = frozenset(
    {"ctypes", "operator", "functools", "importlib", "inspect", "gc", "sys"}
)
_PR2_ACCUMULATOR_CALLEE_DYNAMIC_BUILTINS = frozenset(
    {"__import__", "compile", "delattr", "eval", "exec", "globals", "locals", "setattr", "vars"}
)
_PR2_ACCUMULATOR_CALLEE_FRAME_CALLS = frozenset(
    {
        "sys._getframe",
        "sys._current_frames",
        "inspect.currentframe",
        "inspect.stack",
        "inspect.trace",
        "gc.get_objects",
        "gc.get_referrers",
    }
)
_PR2_ACCUMULATOR_CALLEE_FRAME_ATTRS = frozenset(
    {"__dict__", "__getattribute__", "f_locals", "f_globals", "f_back", "tb_frame"}
)


def _static_string_value(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string_value(node.left)
        right = _static_string_value(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    return None


def _accumulator_getattr_dynamic_primitive(call: ast.Call) -> str | None:
    if _call_func_name(call) != "getattr":
        return None
    if len(call.args) < 2:
        return "getattr dynamic member name"
    receiver = call.args[0]
    member_name = _static_string_value(call.args[1])
    receiver_name = receiver.id if isinstance(receiver, ast.Name) else None
    if receiver_name in {"sys", "inspect", "gc"} and member_name is None:
        return "getattr dynamic member name"
    if member_name in _PR2_ACCUMULATOR_CALLEE_FRAME_ATTRS:
        return f"getattr {member_name}"
    if receiver_name == "sys" and member_name in {"_getframe", "_current_frames"}:
        return f"getattr sys.{member_name}"
    if receiver_name == "inspect" and member_name in {"currentframe", "stack", "trace"}:
        return f"getattr inspect.{member_name}"
    if receiver_name == "gc" and member_name in {"get_objects", "get_referrers"}:
        return f"getattr gc.{member_name}"
    return None


def _accumulator_callee_body_dynamic_primitive(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            root = alias.name.split(".", 1)[0]
            module = root if isinstance(node, ast.Import) else (node.module or "").split(".", 1)[0]
            if root in _PR2_ACCUMULATOR_CALLEE_DYNAMIC_IMPORT_MODULES or module in _PR2_ACCUMULATOR_CALLEE_DYNAMIC_IMPORT_MODULES:
                return root if root in _PR2_ACCUMULATOR_CALLEE_DYNAMIC_IMPORT_MODULES else module
    if isinstance(node, ast.Call):
        call_name = _call_func_name(node)
        if call_name in _PR2_ACCUMULATOR_CALLEE_DYNAMIC_BUILTINS:
            return call_name
        getattr_primitive = _accumulator_getattr_dynamic_primitive(node)
        if getattr_primitive is not None:
            return getattr_primitive
        if call_name in _PR2_ACCUMULATOR_CALLEE_FRAME_CALLS:
            return call_name
        if call_name is not None and call_name.startswith("importlib."):
            return call_name
    if isinstance(node, ast.Attribute):
        if node.attr in _PR2_ACCUMULATOR_CALLEE_FRAME_ATTRS:
            return node.attr
        if isinstance(node.value, ast.Name) and node.value.id in _PR2_ACCUMULATOR_CALLEE_DYNAMIC_MODULES:
            return f"{node.value.id}.{node.attr}"
    if isinstance(node, ast.Name) and node.id in {"ctypes", "operator", "functools"}:
        return node.id
    return None


def _check_accumulator_callee_integrity(
    *,
    tree: ast.Module,
    function: ast.FunctionDef,
    required_calls: Sequence[str],
    accumulator_names: frozenset[str],
    label: str,
    path: Path,
) -> list[str]:
    errors: list[str] = []
    required_call_set = set(required_calls)
    for stmt in ast.walk(function):
        if not isinstance(stmt, ast.stmt):
            continue
        callee_call = _accumulator_callee_call_from_statement(
            stmt,
            accumulator_names=accumulator_names,
        )
        if callee_call is None:
            continue
        callee = callee_call.func.id
        if callee not in required_call_set:
            errors.append(f"{label} accumulator callee {callee} is not in the required-callee floor")
    for callee in sorted(required_call_set):
        try:
            callee_def = _function_def(tree, callee, path=path)
        except CheckError:
            continue
        for node in ast.walk(callee_def):
            primitive = _accumulator_callee_body_dynamic_primitive(node)
            if primitive is not None:
                errors.append(
                    f"{label} accumulator callee {callee} body must not use "
                    f"caller-frame/dynamic primitive {primitive}"
                )
                break
    return errors


def _check_function_errors_whitelist(function: ast.FunctionDef, *, label: str) -> list[str]:
    errors: list[str] = []
    errors.extend(_errors_binding_integrity_errors(function, label=label))
    for node in ast.walk(function):
        if node is function:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            errors.append(f"{label} must not define nested executable scope at line {getattr(node, 'lineno', '?')}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            errors.append(f"{label} must not import inside error collector at line {getattr(node, 'lineno', '?')}")
        if isinstance(node, ast.stmt):
            errors.extend(_errors_append_purity_errors(node, label=label))
        if isinstance(node, ast.Name) and node.id == "errors":
            if not _errors_name_reference_is_whitelisted(node, function_name=function.name):
                errors.append(
                    f"{label} has non-whitelisted errors reference at line "
                    f"{getattr(node, 'lineno', '?')}"
                )
        if isinstance(node, ast.Call):
            primitive = _call_is_dynamic_checker_primitive(node)
            if primitive is not None:
                errors.append(f"{label} must not use reflection/dynamic primitive {primitive}")
        namespace = _node_references_dynamic_checker_namespace(node)
        if namespace is not None:
            errors.append(f"{label} must not reference reflection/dynamic namespace {namespace}")
    return errors


def _literal_str_tuple_top_level(
    tree: ast.Module,
    name: str,
    *,
    path: Path,
) -> tuple[tuple[str, ...] | None, list[str]]:
    errors: list[str] = []
    bindings = _top_level_binding_points(tree, name)
    if len(bindings) != 1:
        return None, [f"{_rel(path)} must define {name} exactly once"]
    stmt = bindings[0]
    if not isinstance(stmt, (ast.Assign, ast.AnnAssign)) or name not in _direct_statement_bound_names(stmt):
        return None, [f"{_rel(path)} {name} must be a direct top-level tuple binding"]
    value = stmt.value
    if not isinstance(value, ast.Tuple):
        return None, [f"{_rel(path)} {name} must be a literal tuple floor"]
    items: list[str] = []
    for item in value.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            errors.append(f"{_rel(path)} {name} must contain only string literals")
            continue
        items.append(item.value)
    return tuple(items), errors


def _check_required_call_tuple_floor(
    tree: ast.Module,
    *,
    path: Path,
    floor_name: str,
    runtime_name: str,
    expected_floor: tuple[str, ...],
    label: str,
) -> tuple[tuple[str, ...], list[str]]:
    errors: list[str] = []
    parsed_floor, floor_errors = _literal_str_tuple_top_level(tree, floor_name, path=path)
    errors.extend(floor_errors)
    parsed_runtime, runtime_errors = _literal_str_tuple_top_level(tree, runtime_name, path=path)
    errors.extend(runtime_errors)
    if parsed_floor is None:
        parsed_floor = ()
    if parsed_runtime is None:
        parsed_runtime = ()
    for callee in sorted(set(expected_floor) - set(parsed_floor)):
        errors.append(f"{label} required-call floor missing {callee}")
    for callee in sorted(set(parsed_floor) - set(parsed_runtime)):
        errors.append(f"{label} required-call runtime tuple shrank below floor: {callee}")
    return parsed_runtime, errors


def _check_required_callee_definitions(
    tree: ast.Module,
    callees: Sequence[str],
    *,
    path: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    for callee in sorted(set(callees)):
        bindings = _top_level_binding_points(tree, callee)
        if len(bindings) != 1:
            errors.append(f"{label} required callee {callee} must resolve to exactly one top-level FunctionDef")
            continue
        definition = bindings[0]
        if not isinstance(definition, ast.FunctionDef) or definition.name != callee:
            errors.append(f"{label} required callee {callee} must resolve to exactly one top-level FunctionDef")
            continue
        if definition.decorator_list:
            errors.append(f"{label} required callee {callee} must be undecorated")
    return errors


def _main_preflight_prefix_matches(main_fn: ast.FunctionDef) -> bool:
    expected = (
        "preflight_errors: list[str] = []",
        "preflight_errors.extend(_check_close_kernel_checker_self_binding())",
        "preflight_errors.extend(_check_error_collector_integrity())",
        "if preflight_errors:\n"
        "    _print_p1_2_errors(preflight_errors)\n"
        "    return 1",
    )
    return len(main_fn.body) >= len(expected) and all(
        _stmt_matches_source(stmt, source)
        for stmt, source in zip(main_fn.body, expected)
    )


def _main_preflight_prefix_len(main_fn: ast.FunctionDef) -> int:
    return 4 if _main_preflight_prefix_matches(main_fn) else 0


_PR2_PROCESS_EXIT_CALL_NAMES = frozenset(
    {"exit", "quit", "os._exit", "sys.exit", "builtins.exit", "builtins.quit"}
)
_PR2_PROCESS_EXIT_ATTRS = frozenset({"_exit", "exit", "quit"})


def _expr_qualified_name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = [node.attr]
        value = node.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
            return ".".join(reversed(parts))
    return None


def _expr_is_process_exit_callable(
    node: ast.AST | None,
    *,
    process_exit_aliases: frozenset[str] = frozenset(),
) -> str | None:
    name = _expr_qualified_name(node)
    if name in process_exit_aliases:
        return name
    if name in _PR2_PROCESS_EXIT_CALL_NAMES:
        return name
    if isinstance(node, ast.Attribute) and node.attr in _PR2_PROCESS_EXIT_ATTRS:
        return name or node.attr
    return None


def _process_exit_alias_names(
    nodes: Sequence[ast.AST],
    *,
    initial_aliases: frozenset[str] = frozenset(),
) -> frozenset[str]:
    aliases = set(initial_aliases)
    walk_nodes = [child for node in nodes for child in ast.walk(node)]
    changed = True
    while changed:
        changed = False
        for node in walk_nodes:
            if isinstance(node, ast.ImportFrom) and node.module in {"builtins", "os", "sys"}:
                for alias in node.names:
                    qualified = f"{node.module}.{alias.name}"
                    if qualified in _PR2_PROCESS_EXIT_CALL_NAMES or alias.name in _PR2_PROCESS_EXIT_ATTRS:
                        bound = alias.asname or alias.name
                        if bound not in aliases:
                            aliases.add(bound)
                            changed = True
            elif isinstance(node, ast.Assign) and _expr_is_process_exit_callable(
                node.value,
                process_exit_aliases=frozenset(aliases),
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and _expr_is_process_exit_callable(
                node.value,
                process_exit_aliases=frozenset(aliases),
            ):
                if isinstance(node.target, ast.Name) and node.target.id not in aliases:
                    aliases.add(node.target.id)
                    changed = True
    return frozenset(aliases)


def _call_is_process_exit(
    call: ast.Call,
    *,
    process_exit_aliases: frozenset[str] = frozenset(),
) -> str | None:
    if isinstance(call.func, ast.Name) and call.func.id in process_exit_aliases:
        return call.func.id
    call_name = _call_func_name(call)
    if call_name in _PR2_PROCESS_EXIT_CALL_NAMES:
        return call_name
    if isinstance(call.func, ast.Attribute) and call.func.attr in _PR2_PROCESS_EXIT_ATTRS:
        return call_name or call.func.attr
    return None


def _stmt_has_control_exit(
    stmt: ast.stmt,
    *,
    process_exit_aliases: frozenset[str] = frozenset(),
) -> bool:
    for node in ast.walk(stmt):
        if isinstance(node, (ast.Return, ast.Raise)):
            return True
        if isinstance(node, ast.Call) and _call_is_process_exit(
            node,
            process_exit_aliases=process_exit_aliases,
        ) is not None:
            return True
    return False


def _main_has_live_required_call(main_fn: ast.FunctionDef, required_call: str) -> bool:
    preflight_required = {
        "_check_close_kernel_checker_self_binding",
        "_check_error_collector_integrity",
    }
    if required_call in preflight_required:
        return _statement_sequence_has_live_accumulator_call(
            main_fn.body[:3],
            required_call,
            accumulator_names=frozenset({"preflight_errors"}),
            allow_outer_try=False,
        )
    prefix_len = _main_preflight_prefix_len(main_fn)
    return _statement_sequence_has_live_accumulator_call(
        main_fn.body[prefix_len:],
        required_call,
        accumulator_names=frozenset({"errors"}),
        allow_outer_try=True,
    )


def _required_call_statement_linenos(
    statements: Sequence[ast.stmt],
    required_call: str,
    *,
    accumulator_names: frozenset[str],
    allow_outer_try: bool,
) -> list[int]:
    lines: list[int] = []
    for stmt in statements:
        call = _accumulator_callee_call_from_statement(
            stmt,
            accumulator_names=accumulator_names,
        )
        if call is not None and call.func.id == required_call:
            lines.append(getattr(stmt, "lineno", getattr(call, "lineno", -1)))
        if allow_outer_try and isinstance(stmt, (ast.Try, ast.TryStar)):
            lines.extend(
                _required_call_statement_linenos(
                    stmt.body,
                    required_call,
                    accumulator_names=accumulator_names,
                    allow_outer_try=False,
                )
            )
    return lines


def _check_error_collector_integrity(
    *,
    checker_path: Path = Path(__file__).resolve(),
) -> list[str]:
    errors: list[str] = []
    tree = _parse_python(checker_path)
    for function_name in ("main", "_check_candidate_sink_replay_contract"):
        function = _function_def(tree, function_name, path=checker_path)
        required_calls = (
            _PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR
            if function_name == "main"
            else _PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS_FLOOR
        )
        local_bindings = _function_local_binding_names(function)
        for callee in sorted(set(required_calls) & local_bindings):
            errors.append(f"{function_name} must not locally shadow required callee {callee}")
        errors.extend(_check_function_errors_whitelist(function, label=function_name))
        errors.extend(
            _check_accumulator_callee_integrity(
                tree=tree,
                function=function,
                required_calls=required_calls,
                accumulator_names=(
                    frozenset({"preflight_errors", "errors"})
                    if function_name == "main"
                    else frozenset({"errors"})
                ),
                label=function_name,
                path=checker_path,
            )
        )
    return errors


def _check_main_self_integrity_preflight_shape(
    *,
    checker_path: Path = Path(__file__).resolve(),
) -> list[str]:
    tree = _parse_python(checker_path)
    main_fn = _function_def(tree, "main", path=checker_path)
    if _main_preflight_prefix_matches(main_fn):
        return []
    return [
        "proof-obligation checker main must start with fail-fast self-integrity "
        "preflight before shared errors"
    ]


def _check_main_error_reporting_shape(
    *,
    checker_path: Path = Path(__file__).resolve(),
) -> list[str]:
    errors: list[str] = []
    tree = _parse_python(checker_path)
    main_fn = _function_def(tree, "main", path=checker_path)
    required_call_lines: list[int] = []
    prefix_len = _main_preflight_prefix_len(main_fn)
    preflight_required = {
        "_check_close_kernel_checker_self_binding",
        "_check_error_collector_integrity",
    }
    for required_call in _PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR:
        if required_call in preflight_required:
            lines = _required_call_statement_linenos(
                main_fn.body[:3],
                required_call,
                accumulator_names=frozenset({"preflight_errors"}),
                allow_outer_try=False,
            )
        else:
            lines = _required_call_statement_linenos(
                main_fn.body[prefix_len:],
                required_call,
                accumulator_names=frozenset({"errors"}),
                allow_outer_try=True,
            )
        if not lines:
            continue
        required_call_lines.extend(lines)
    process_exit_aliases = _process_exit_alias_names(
        main_fn.body,
        initial_aliases=_process_exit_alias_names(tree.body),
    )
    failure_gate = _errors_failure_gate(main_fn)
    gate_lineno = None if failure_gate is None else failure_gate.lineno
    if failure_gate is None:
        errors.append("proof-obligation checker main must have reachable if errors: return 1")
    elif required_call_lines and gate_lineno <= max(required_call_lines):
        errors.append("proof-obligation checker main failure gate must follow required calls")
    exception_handlers = [
        handler
        for node in ast.walk(main_fn)
        if isinstance(node, (ast.Try, ast.TryStar))
        for handler in node.handlers
    ]
    if len(exception_handlers) != 1:
        errors.append("proof-obligation checker main must have exactly one exception handler")
    else:
        handler = exception_handlers[0]
        if not (
            isinstance(handler.type, ast.Name)
            and handler.type.id == "CheckError"
            and handler.name is None
        ):
            errors.append("proof-obligation checker main exception handler must catch only CheckError")
        if len(handler.body) != 1 or not _direct_return_value(handler.body[0], 2):
            errors.append("proof-obligation checker main CheckError handler must only return 2")
    return_zero_lines: list[int] = []
    for node in ast.walk(main_fn):
        if isinstance(node, ast.Return):
            if not isinstance(node.value, ast.Constant) or type(node.value.value) is not int:
                errors.append(
                    "proof-obligation checker main must return only integer literals 0, 1, or 2"
                )
                continue
            if node.value.value not in {0, 1, 2}:
                errors.append(
                    "proof-obligation checker main must return only integer literals 0, 1, or 2"
                )
            if node.value.value == 0:
                return_zero_lines.append(node.lineno)
        if isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                errors.append("proof-obligation checker main must not raise SystemExit")
            if isinstance(exc, ast.Call) and _call_func_name(exc) == "SystemExit":
                errors.append("proof-obligation checker main must not raise SystemExit")
        if isinstance(node, ast.Call) and _call_is_process_exit(
            node,
            process_exit_aliases=process_exit_aliases,
        ) is not None:
            errors.append("proof-obligation checker main must not call process exit before failure gate")
    if failure_gate is not None and (
        not _errors_failure_gate_has_allowed_body(failure_gate) or failure_gate.orelse
    ):
        errors.append("proof-obligation checker main failure gate body must only return 1")
    if not return_zero_lines:
        errors.append("proof-obligation checker main must have success return 0")
    elif gate_lineno is not None and any(line < gate_lineno for line in return_zero_lines):
        errors.append("proof-obligation checker main must not return 0 before errors gate")
    if failure_gate is not None:
        for stmt in main_fn.body[prefix_len:]:
            if stmt is failure_gate:
                break
            if isinstance(stmt, (ast.Try, ast.TryStar)):
                checked_bodies = [*stmt.body, *stmt.orelse, *stmt.finalbody]
                if any(
                    _stmt_has_control_exit(
                        inner_stmt,
                        process_exit_aliases=process_exit_aliases,
                    )
                    for inner_stmt in checked_bodies
                ):
                    errors.append("proof-obligation checker main must not exit before errors gate")
            elif _stmt_has_control_exit(stmt, process_exit_aliases=process_exit_aliases):
                errors.append("proof-obligation checker main must not exit before errors gate")
    return errors


def _check_error_collector_return_shape(
    *,
    checker_path: Path = Path(__file__).resolve(),
) -> list[str]:
    tree = _parse_python(checker_path)
    function = _function_def(tree, "_check_candidate_sink_replay_contract", path=checker_path)
    if not function.body:
        return ["_check_candidate_sink_replay_contract must end with return errors"]
    tail = function.body[-1]
    errors: list[str] = []
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    if not (
        isinstance(tail, ast.Return)
        and isinstance(tail.value, ast.Name)
        and tail.value.id == "errors"
    ):
        errors.append("_check_candidate_sink_replay_contract must end with direct return errors")
    if returns != [tail]:
        errors.append("_check_candidate_sink_replay_contract must have only the final return errors")
    return errors


_CHECKER_ALLOWED_IMPORTS = frozenset(
    {
        "ast",
        "builtins",
        "hashlib",
        "json",
        "shutil",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "weakref",
    }
)
_CHECKER_ALLOWED_FROM_IMPORTS = {
    "__future__": frozenset({"annotations"}),
    "pathlib": frozenset({"Path"}),
    "typing": frozenset({"Any", "Callable", "Iterator", "Mapping", "NoReturn", "Sequence"}),
}


_IMPORT_TIME_REBIND_NAME_PRIMITIVES = frozenset(
    {
        "__import__",
        "compile",
        "delattr",
        "eval",
        "exec",
        "globals",
        "locals",
        "setattr",
        "vars",
    }
)
_IMPORT_TIME_REBIND_ATTR_PRIMITIVES = frozenset(
    {"__delattr__", "__dict__", "__setattr__", "__setitem__"}
)


def _expr_contains_import_time_rebind_primitive(node: ast.AST | None) -> str | None:
    """round-16 (BLOCK 1): report a namespace-write/dynamic-exec primitive inside
    an import-time-evaluated expression.

    The checker module top-level closed-world previously only checked statement
    *type*; a namespace-write hidden in an *allowed* statement's import-time
    expression (``_x = globals().__setitem__("main", lambda: 0)``, a
    ``FunctionDef`` default ``def f(_x=globals().__setitem__(...))``, or a
    ``ClassDef`` body ``class C: globals()["main"] = lambda: 0``) still rebinds a
    protected global at module exec time, before the canonical entrypoint runs.
    Reject any of these primitives in import-time-evaluated positions.
    """
    if node is None:
        return None
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in _IMPORT_TIME_REBIND_NAME_PRIMITIVES:
            return child.id
        if isinstance(child, ast.Attribute) and child.attr in _IMPORT_TIME_REBIND_ATTR_PRIMITIVES:
            return child.attr
    return None


def _checker_import_statement_allowed(stmt: ast.Import | ast.ImportFrom) -> bool:
    if isinstance(stmt, ast.Import):
        return all(
            alias.asname is None and alias.name in _CHECKER_ALLOWED_IMPORTS
            for alias in stmt.names
        )
    if stmt.level != 0 or stmt.module not in _CHECKER_ALLOWED_FROM_IMPORTS:
        return False
    allowed_names = _CHECKER_ALLOWED_FROM_IMPORTS[stmt.module]
    return all(alias.asname is None and alias.name in allowed_names for alias in stmt.names)


def _checker_class_body_statement_allowed(stmt: ast.stmt, *, is_first: bool) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    return (
        is_first
        and isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _checker_module_top_level_statement_allowed(
    stmt: ast.stmt, *, is_first: bool, is_last: bool
) -> bool:
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return _checker_import_statement_allowed(stmt)
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # round-20 (G1): scan every def-time-evaluated expression, including
        # ``*args``/``**kwargs`` annotations and type params, for an import-time
        # rebind primitive.  The previous manual list omitted vararg/kwarg
        # annotations; mirror ``_function_def_time_nodes`` so this closed world and
        # the parent's ``_locked_checker_top_level_statement_allowed`` stay aligned.
        for expr in _function_def_time_nodes(stmt):
            if _expr_contains_import_time_rebind_primitive(expr) is not None:
                return False
        return True
    if isinstance(stmt, ast.ClassDef):
        return _checker_top_level_class_is_inert_exception(stmt)
    if isinstance(stmt, ast.Assign):
        if not (bool(stmt.targets) and all(isinstance(target, ast.Name) for target in stmt.targets)):
            return False
        if _expr_contains_import_time_rebind_primitive(stmt.value) is not None:
            return False
        return _expr_is_process_exit_callable(stmt.value) is None
    if isinstance(stmt, ast.AnnAssign):
        if not isinstance(stmt.target, ast.Name):
            return False
        if _expr_contains_import_time_rebind_primitive(stmt.annotation) is not None:
            return False
        if _expr_contains_import_time_rebind_primitive(stmt.value) is not None:
            return False
        return _expr_is_process_exit_callable(stmt.value) is None
    if isinstance(stmt, ast.AugAssign):
        if not isinstance(stmt.target, ast.Name):
            return False
        if _expr_contains_import_time_rebind_primitive(stmt.value) is not None:
            return False
        return _expr_is_process_exit_callable(stmt.value) is None
    if (
        is_first
        and isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    ):
        return True
    if is_last and isinstance(stmt, ast.If):
        return _checker_module_is_canonical_entrypoint(stmt)
    return False


def _checker_module_is_canonical_entrypoint(stmt: ast.If) -> bool:
    test = stmt.test
    if not (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
        and not stmt.orelse
        and len(stmt.body) == 1
    ):
        return False
    raise_stmt = stmt.body[0]
    if not isinstance(raise_stmt, ast.Raise) or not isinstance(raise_stmt.exc, ast.Call):
        return False
    exc = raise_stmt.exc
    return (
        isinstance(exc.func, ast.Name)
        and exc.func.id == "SystemExit"
        and len(exc.args) == 1
        and not exc.keywords
        and isinstance(exc.args[0], ast.Call)
        and isinstance(exc.args[0].func, ast.Name)
        and exc.args[0].func.id == "main"
        and not exc.args[0].args
        and not exc.args[0].keywords
    )


def _check_checker_module_top_level_closed_world(tree: ast.Module) -> list[str]:
    """Fail closed on any module-level dynamic namespace write in the checker.

    ``main`` and the required callees are byte-pinned as top-level ``FunctionDef``
    nodes, but a module-level dynamic write such as
    ``globals()["_check_close_kernel_contract"] = lambda manifest: []`` (an
    ``Assign`` with a ``Subscript`` target) rebinds the runtime object without
    producing a ``Name`` binding point, so the unique-binding check would not
    notice it.  Enforce a closed-world top level: only the module docstring,
    imports, ``def``/``class``, ``Name``-target assignments, and the canonical
    entrypoint are allowed.  The runtime anchor enforces the same closed world
    from the parent process (covering the ``main`` rebind case that would
    otherwise short-circuit every self-check).
    """
    errors: list[str] = []
    last_index = len(tree.body) - 1
    for index, stmt in enumerate(tree.body):
        if not _checker_module_top_level_statement_allowed(
            stmt, is_first=(index == 0), is_last=(index == last_index)
        ):
            errors.append(
                "proof-obligation checker module top level contains disallowed statement "
                f"{type(stmt).__name__} at line {getattr(stmt, 'lineno', '?')}"
            )
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
    errors.extend(_check_checker_module_top_level_closed_world(tree))
    main_calls, main_tuple_errors = _check_required_call_tuple_floor(
        tree,
        path=checker_path,
        floor_name="_PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR",
        runtime_name="_PR2_CHECKER_MAIN_REQUIRED_CALLS",
        expected_floor=_PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR,
        label="proof-obligation checker main",
    )
    errors.extend(main_tuple_errors)
    sink_calls, sink_tuple_errors = _check_required_call_tuple_floor(
        tree,
        path=checker_path,
        floor_name="_PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS_FLOOR",
        runtime_name="_PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS",
        expected_floor=_PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS_FLOOR,
        label="candidate sink replay contract",
    )
    errors.extend(sink_tuple_errors)
    errors.extend(
        _check_required_callee_definitions(
            tree,
            ("main", *main_calls, *sink_calls),
            path=checker_path,
            label="proof-obligation checker",
        )
    )
    main_fn = _function_def(tree, "main", path=checker_path)
    for required_call in _PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR:
        if not _main_has_live_required_call(main_fn, required_call):
            errors.append(f"proof-obligation checker main must call {required_call}")
    sink_replay_fn = _function_def(
        tree, "_check_candidate_sink_replay_contract", path=checker_path
    )
    for required_call in _PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS_FLOOR:
        if not _has_live_errors_extend_call(sink_replay_fn, required_call):
            errors.append(f"candidate sink replay contract must call {required_call}")
    errors.extend(_check_main_self_integrity_preflight_shape(checker_path=checker_path))
    errors.extend(_check_error_collector_integrity(checker_path=checker_path))
    errors.extend(_check_main_error_reporting_shape(checker_path=checker_path))
    errors.extend(_check_error_collector_return_shape(checker_path=checker_path))
    return errors


def _check_strong_status_write_allowlist_bytes(
    *,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    path = project_root / STRONG_STATUS_WRITE_ALLOWLIST_REL
    if not path.exists():
        return [f"strong-status write allowlist missing: {STRONG_STATUS_WRITE_ALLOWLIST_REL}"]
    allowlist_bytes = path.read_bytes()
    size = len(allowlist_bytes)
    sha256 = hashlib.sha256(allowlist_bytes).hexdigest()
    errors: list[str] = []
    if size != STRONG_STATUS_WRITE_ALLOWLIST_SIZE:
        errors.append(
            "strong-status write allowlist size drift reopens P1.2 close claim: "
            f"{size} != {STRONG_STATUS_WRITE_ALLOWLIST_SIZE}"
        )
    if sha256 != STRONG_STATUS_WRITE_ALLOWLIST_SHA256:
        errors.append(
            "strong-status write allowlist hash drift reopens P1.2 close claim: "
            f"{sha256} != {STRONG_STATUS_WRITE_ALLOWLIST_SHA256}"
        )
    return errors


def _check_strong_status_write_allowlist_gate() -> list[str]:
    byte_errors = _check_strong_status_write_allowlist_bytes()
    if byte_errors:
        return byte_errors
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
    return _check_strong_status_write_allowlist_bytes()


_PR2_CHILD_ELEVATION_SLOTS = frozenset(
    {
        "final_result",
        "final_status",
        "declare_mode",
        "last_stop_reason",
        "terminal_frontier_evidence",
        "candidates",
    }
)
_PR2_MUTATING_MAPPING_METHODS = frozenset(
    {
        "update",
        "clear",
        "setdefault",
        "__setitem__",
        "__delitem__",
        "__ior__",
        "pop",
        "popitem",
    }
)
_PR2_CHILD_AUTHORITY_IMPORT_MODULE = "src.search.pr2_l0_artifact_core"
_PR2_CHILD_AUTHORITY_NAMES = frozenset(
    {
        "canonical_candidate_geometry_rederivation_violation",
        "terminal_certified_final_result_project_precheck_violation",
        "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON",
    }
)
_PR2_CHILD_RESERVED_RUNTIME_NAMES = frozenset(
    {
        "bool",
        "dict",
        "frozenset",
        "getattr",
        "list",
        "Path",
        "str",
        "tuple",
        "_canonical_digest",
        "_stable_fixed_witness_candidate_records",
        "payload",
        "authority_state",
        "certified_final_result",
        "evidence",
        "durable_records",
        "project_root",
        "scratch_state",
    }
) | _PR2_CHILD_AUTHORITY_NAMES
_PR2_CHILD_POST_PRECHECK_PROTECTED_NAMES = frozenset(
    {"certified_final_result", "evidence", "durable_records"}
)
_PR2_CHILD_DYNAMIC_MODULE_CALLS = frozenset(
    {"__import__", "compile", "eval", "exec", "globals", "locals", "setattr", "delattr", "vars"}
)
_PR2_CHILD_FRAME_CALLS = frozenset({"sys._getframe", "inspect.currentframe"})
_PR2_CHILD_FRAME_ATTRS = frozenset({"f_locals", "f_globals", "f_back"})
_PR2_CHILD_DOMAIN_IMPORTFROM_ALLOWLIST = {
    "src.search.pr2_l0_frontier_core": frozenset(
        {
            "build_terminal_frontier_evidence",
            "candidate_generation_kwargs",
            "generate_candidate_sizes",
        }
    ),
    "src.search.pr2_l0_artifact_core": frozenset(
        {
            "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON",
            "canonical_candidate_geometry_rederivation_violation",
            "terminal_certified_final_result_project_precheck_violation",
        }
    ),
}
_PR2_CHILD_MODULE_IMPORT_ALLOWLIST = frozenset(
    {
        ("import", "base64", None),
        ("import", "hashlib", None),
        ("import", "importlib.machinery", None),
        ("import", "json", None),
        ("import", "os", None),
        ("import", "sys", None),
        ("import", "sysconfig", None),
        ("import", "tempfile", None),
        ("import", "traceback", None),
        ("from", "__future__", "annotations"),
        ("from", "collections.abc", "Iterable"),
        ("from", "pathlib", "Path"),
        ("from", "typing", "Any"),
        ("from", "typing", "Mapping"),
    }
)
_PR2_CHILD_RETURN_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "nonce",
        "verdict",
        "reason",
        "strong_keys",
        "final_result",
        "terminal_frontier_evidence",
        "candidate_records",
        "final_result_digest",
        "terminal_frontier_evidence_digest",
        "candidate_records_digest",
        "fixed_witness_publishable",
        "sink_replay_violations",
        "fixed_witness_violations",
        "tcb",
    }
)
_PR2_CHILD_RETURN_PINNED_EXPRESSIONS = {
    "schema_version": "DOMAIN_SCHEMA_VERSION",
    "authority": "DOMAIN_AUTHORITY",
    "nonce": "nonce",
    "verdict": "SEALED",
    "reason": '"domain_verified"',
    "strong_keys": "list(strong_keys)",
    "final_result": "certified_final_result",
    "terminal_frontier_evidence": "evidence",
    "candidate_records": "durable_records",
    "final_result_digest": "final_digest",
    "terminal_frontier_evidence_digest": "evidence_digest",
    "candidate_records_digest": "records_digest",
    "fixed_witness_publishable": 'bool(getattr(fixed_verdict, "publishable", False))',
    "sink_replay_violations": "{}",
    "fixed_witness_violations": "{}",
    "tcb": (
        "{"
        '"python_interpreter": "NAMED-TCB", '
        '"stdlib": "NAMED-TCB", '
        '"third_party_native": "NAMED-TCB", '
        '"os_process_file_isolation": "NAMED-TCB", '
        '"windows_write_isolation_residual": '
        '"protocol_only_child_snapshot_no_write_fd_pr2c_linux_uid_namespace_pending"'
        "}"
    ),
}
_PR2_CHILD_GETATTR_ALLOWLIST = frozenset(
    {
        ("fixed_verdict", "publishable", False),
        ("fixed_verdict", "candidate_key", None),
        ("fixed_verdict", "reason", None),
    }
)
_PR2_CHILD_TOP_LEVEL_CONSTANT_SOURCES = {
    "SEALED": '"SEALED"',
    "REJECTED": '"REJECTED"',
    "DOMAIN_AUTHORITY": '"pr2_l0_true_supervisor_domain_v1"',
    "DOMAIN_SCHEMA_VERSION": "1",
    "FLOOR_AUTHORITY": '"pr2_l0_dependency_floor_manifest_v1"',
    "FLOOR_ROOT_SENTINEL": '"PYTHON_SYSCONFIG_PURELIB"',
    "IMPORT_FILE_SUFFIXES": (
        "tuple(importlib.machinery.SOURCE_SUFFIXES + "
        "importlib.machinery.EXTENSION_SUFFIXES)"
    ),
    "_FIXED_WITNESS_AUDIT_FIELD": '"terminal_fixed_witness_verifier"',
    "_FIXED_WITNESS_STABLE_FIELD_ORDER": (
        "("
        '"schema_version", "authority", "publishable", "projected_status", '
        '"candidate_key", "solution_digest", "ghost_rect_digest", '
        '"ghost_cells_digest", "witness_input_digest", '
        '"binding_assignment_digest", "port_specs_digest", '
        '"routing_occupancy_digest", "binding_status", "routing_status", '
        '"reason", "details"'
        ")"
    ),
    "_FIXED_WITNESS_STABLE_FIELDS": "frozenset(_FIXED_WITNESS_STABLE_FIELD_ORDER)",
    "_FIXED_WITNESS_VOLATILE_FIELDS": 'frozenset({"fresh_run_token"})',
}
_PR2_CHILD_TOP_LEVEL_FUNCTIONS = frozenset(
    {
        "verify",
        "_dependency_floor_root",
        "_install_third_party_floor",
        "_is_within",
        "_is_within_any",
        "_stdlib_paths",
        "_valid_top_level_name",
        "_dependency_file_top_level",
        "_dependency_named_tcb_violation",
        "_index_dependency_package_dirs",
        "_verify_supervisor_domain",
        "_project_candidate_records_direct",
        "_materialize_import_default_artifacts",
        "_run_fixed_witness_direct",
        "_strict_int",
        "_strict_string",
        "_require_mapping",
        "_string_list",
        "_json_copy",
        "_canonical_bytes",
        "_canonical_digest",
        "_stable_fixed_witness_payload",
        "_stable_fixed_witness_candidate_records",
        "_is_lower_sha256",
        "_safe_rel",
    }
)
_PR2_CHILD_TOP_LEVEL_CLASSES = frozenset(
    {
        "_StdlibOnlyPathFinder",
        "_RestrictedThirdPartyFinder",
        "_RehashingSourceFileLoader",
        "_RehashingExtensionFileLoader",
    }
)
_PR2_CHILD_CLASS_BASE_SOURCES = {
    "_StdlibOnlyPathFinder": (),
    "_RestrictedThirdPartyFinder": (),
    "_RehashingSourceFileLoader": ("importlib.machinery.SourceFileLoader",),
    "_RehashingExtensionFileLoader": ("importlib.machinery.ExtensionFileLoader",),
}
_PR2_CHILD_CLASS_METHODS = {
    "_StdlibOnlyPathFinder": frozenset({"__init__", "find_spec"}),
    "_RestrictedThirdPartyFinder": frozenset({"__init__", "find_spec"}),
    "_RehashingSourceFileLoader": frozenset({"__init__", "get_data", "get_code"}),
    "_RehashingExtensionFileLoader": frozenset({"__init__", "create_module"}),
}
_PR2_CHILD_CLASS_ALLOWED_DYNAMIC_CALLS = frozenset(
    {"compile", "importlib.machinery.PathFinder.find_spec"}
)
_PR2_CHILD_CLASS_METHOD_BODIES = {
    ("_StdlibOnlyPathFinder", "__init__"): (
        "self.stdlib_paths = [path.resolve() for path in stdlib_paths]",
    ),
    ("_StdlibOnlyPathFinder", "find_spec"): (
        "if path is None:\n"
        "    search_path = [str(path) for path in self.stdlib_paths]\n"
        "elif isinstance(path, (list, tuple)):\n"
        "    search_path = []\n"
        "    for raw_path in path:\n"
        "        candidate = Path(str(raw_path)).resolve()\n"
        "        if _is_within_any(candidate, self.stdlib_paths):\n"
        "            search_path.append(str(candidate))\n"
        "else:\n"
        "    return None",
        "if not search_path:\n    return None",
        "return importlib.machinery.PathFinder.find_spec(fullname, search_path, target)",
    ),
    ("_RestrictedThirdPartyFinder", "__init__"): (
        "self.floor_root = floor_root.resolve()",
        "self.allowed_top_level = allowed_top_level",
        "self.allowed_files = {\n"
        "    path.resolve(): str(sha256) for path, sha256 in allowed_files.items()\n"
        "}",
        "self.allowed_package_dirs = frozenset(path.resolve() for path in allowed_package_dirs)",
        "self.allowed_namespace_dirs = {\n"
        "    str(name): frozenset(path.resolve() for path in paths)\n"
        "    for name, paths in allowed_namespace_dirs.items()\n"
        "}",
    ),
    ("_RestrictedThirdPartyFinder", "find_spec"): (
        'top_level = fullname.split(".", 1)[0]',
        "if top_level not in self.allowed_top_level:\n    return None",
        "if path is None:\n"
        "    search_path = [str(self.floor_root)]\n"
        "elif isinstance(path, Iterable) and not isinstance(path, (str, bytes)):\n"
        "    search_path = [str(item) for item in path]\n"
        "else:\n"
        "    return None",
        "for raw_path in search_path:\n"
        "    candidate = Path(raw_path).resolve()\n"
        "    try:\n"
        "        if os.path.commonpath([str(self.floor_root), str(candidate)]) != str(self.floor_root):\n"
        "            return None\n"
        "    except ValueError:\n"
        "        return None",
        "spec = importlib.machinery.PathFinder.find_spec(fullname, search_path, target)",
        "if spec is None:\n    return None",
        'locations = getattr(spec, "submodule_search_locations", None)',
        "if locations is not None:\n"
        "    package_dirs: list[Path] = []\n"
        "    for raw_location in list(locations):\n"
        "        location = Path(str(raw_location)).resolve()\n"
        "        if location not in self.allowed_package_dirs:\n"
        "            return None\n"
        "        package_dirs.append(location)",
        'origin = getattr(spec, "origin", None)',
        "if origin in {None, \"namespace\"}:\n"
        "    namespace_dirs = self.allowed_namespace_dirs.get(fullname)\n"
        "    if namespace_dirs is None or not locations:\n"
        "        return None\n"
        "    if any(path not in namespace_dirs for path in package_dirs):\n"
        "        return None\n"
        "elif origin in {\"built-in\", \"frozen\"}:\n"
        "    return None\n"
        "else:\n"
        "    origin_path = Path(str(origin)).resolve()\n"
        "    expected_sha256 = self.allowed_files.get(origin_path)\n"
        "    if expected_sha256 is None:\n"
        "        return None\n"
        "    origin_suffix = origin_path.suffix\n"
        "    if origin_suffix in importlib.machinery.SOURCE_SUFFIXES:\n"
        "        spec.loader = _RehashingSourceFileLoader(\n"
        "            fullname, str(origin_path), expected_sha256=expected_sha256\n"
        "        )\n"
        "    elif origin_suffix in importlib.machinery.EXTENSION_SUFFIXES:\n"
        "        spec.loader = _RehashingExtensionFileLoader(\n"
        "            fullname, str(origin_path), expected_sha256=expected_sha256\n"
        "        )\n"
        "    else:\n"
        "        return None",
        "return spec",
    ),
    ("_RehashingSourceFileLoader", "__init__"): (
        "super().__init__(fullname, path)",
        "self._expected_sha256 = expected_sha256",
    ),
    ("_RehashingSourceFileLoader", "get_data"): (
        "data = super().get_data(path)",
        "if hashlib.sha256(data).hexdigest() != self._expected_sha256:\n"
        "    raise ImportError(f\"dependency floor load-time digest mismatch:{path}\")",
        "return data",
    ),
    ("_RehashingSourceFileLoader", "get_code"): (
        "source_bytes = self.get_data(self.path)",
        'return compile(source_bytes, self.path, "exec", dont_inherit=True)',
    ),
    ("_RehashingExtensionFileLoader", "__init__"): (
        "super().__init__(fullname, path)",
        "self._expected_sha256 = expected_sha256",
    ),
    ("_RehashingExtensionFileLoader", "create_module"): (
        "data = Path(self.path).read_bytes()",
        "if hashlib.sha256(data).hexdigest() != self._expected_sha256:\n"
        "    raise ImportError(f\"dependency floor load-time digest mismatch:{self.path}\")",
        "return super().create_module(spec)",
    ),
}
_PR2_CHILD_RESERVED_SHADOW_NAMES = _PR2_CHILD_RESERVED_RUNTIME_NAMES - frozenset(
    {
        "payload",
        "authority_state",
        "certified_final_result",
        "evidence",
        "durable_records",
        "project_root",
        "scratch_state",
    }
)
_PR2_CHILD_HELPER_IMPORTFROM_ALLOWLIST = frozenset(
    {
        "src.search.pr2_l0_artifact_core",
        "src.search.pr2_l0_fixed_witness_core",
        "src.search.pr2_l0_frontier_core",
        "src.search.pr2_l0_replay_core",
    }
)


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_constant(node: ast.AST, value: object) -> bool:
    return isinstance(node, ast.Constant) and node.value == value


def _ast_shape_equal(left: ast.AST, right: ast.AST) -> bool:
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def _expr_matches_source(node: ast.AST, source: str) -> bool:
    return _ast_shape_equal(node, ast.parse(source, mode="eval").body)


def _stmt_matches_source(node: ast.AST, source: str) -> bool:
    try:
        parsed = ast.parse(source).body
    except SyntaxError:
        lines = source.splitlines()
        if not lines:
            return False
        normalized = "\n".join(
            [lines[0], *[line[4:] if line.startswith("    ") else line for line in lines[1:]]]
        )
        parsed = ast.parse(normalized).body
    return len(parsed) == 1 and _ast_shape_equal(node, parsed[0])


def _call_func_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        value = func.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
            return ".".join(reversed(parts))
    return None


def _subscript_constant_slot(node: ast.AST, base_name: str) -> str | None:
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == base_name
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ):
        return node.slice.value
    return None


def _target_contains_name(target: ast.AST, name: str) -> bool:
    return any(isinstance(node, ast.Name) and node.id == name for node in ast.walk(target))


def _target_bound_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names.update(_target_bound_names(element))
        return names
    if isinstance(target, ast.Starred):
        return _target_bound_names(target.value)
    return set()


def _target_dynamic_namespace_writes(target: ast.AST) -> set[str]:
    namespaces: set[str] = set()
    for node in ast.walk(target):
        if not isinstance(node, ast.Subscript):
            continue
        if (
            isinstance(node.value, ast.Call)
            and _call_func_name(node.value) in {"globals", "locals", "vars"}
            and not node.value.args
            and not node.value.keywords
        ):
            namespaces.add(_call_func_name(node.value) or "<dynamic>")
    return namespaces


def _target_reserved_attribute_writes(target: ast.AST) -> set[str]:
    attrs: set[str] = set()
    for node in ast.walk(target):
        if isinstance(node, ast.Attribute) and node.attr in _PR2_CHILD_RESERVED_RUNTIME_NAMES:
            attrs.add(node.attr)
    return attrs


def _stmt_bound_names(stmt: ast.AST) -> set[str]:
    if isinstance(stmt, ast.Assign):
        names: set[str] = set()
        for target in stmt.targets:
            names.update(_target_bound_names(target))
        return names
    if isinstance(stmt, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return _target_bound_names(stmt.target)
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return _target_bound_names(stmt.target)
    if isinstance(stmt, ast.With):
        names: set[str] = set()
        for item in stmt.items:
            if item.optional_vars is not None:
                names.update(_target_bound_names(item.optional_vars))
        return names
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {stmt.name}
    if isinstance(stmt, ast.Import):
        return {
            alias.asname or alias.name.split(".", 1)[0]
            for alias in stmt.names
        }
    if isinstance(stmt, ast.ImportFrom):
        return {alias.asname or alias.name for alias in stmt.names}
    return set()


def _assigns_name(stmt: ast.AST, name: str) -> bool:
    if isinstance(stmt, ast.Assign):
        return any(isinstance(target, ast.Name) and target.id == name for target in stmt.targets)
    if isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
        return isinstance(stmt.target, ast.Name) and stmt.target.id == name
    if isinstance(stmt, ast.NamedExpr):
        return isinstance(stmt.target, ast.Name) and stmt.target.id == name
    return False


def _is_dict_copy_from_authority_state(stmt: ast.Assign) -> bool:
    return (
        len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and stmt.targets[0].id == "scratch_state"
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "dict"
        and len(stmt.value.args) == 1
        and _is_name(stmt.value.args[0], "authority_state")
        and not stmt.value.keywords
    )


def _payload_get_call(node: ast.AST, key: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _is_name(node.func.value, "payload")
        and len(node.args) == 1
        and _is_constant(node.args[0], key)
        and not node.keywords
    )


def _strict_string_payload_get_call(node: ast.AST, key: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and _call_func_name(node) == "_strict_string"
        and len(node.args) == 2
        and _payload_get_call(node.args[0], key)
        and _is_constant(node.args[1], key)
        and not node.keywords
    )


def _is_project_root_init(stmt: ast.AST) -> bool:
    if not (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"project_root"}
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and stmt.value.func.attr == "resolve"
        and not stmt.value.args
        and not stmt.value.keywords
    ):
        return False
    path_call = stmt.value.func.value
    return (
        isinstance(path_call, ast.Call)
        and _call_func_name(path_call) == "Path"
        and len(path_call.args) == 1
        and _strict_string_payload_get_call(path_call.args[0], "project_root")
        and not path_call.keywords
    )


def _is_authority_state_init(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"authority_state"}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "_json_copy"
        and len(stmt.value.args) == 1
        and isinstance(stmt.value.args[0], ast.Call)
        and _call_func_name(stmt.value.args[0]) == "_require_mapping"
        and len(stmt.value.args[0].args) == 2
        and _payload_get_call(stmt.value.args[0].args[0], "authority_state")
        and _is_constant(stmt.value.args[0].args[1], "authority_state")
        and not stmt.value.keywords
        and not stmt.value.args[0].keywords
    )


def _is_certified_final_result_init(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"certified_final_result"}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "dict"
        and len(stmt.value.args) == 1
        and _is_name(stmt.value.args[0], "final_result")
        and not stmt.value.keywords
    )


def _is_durable_records_init(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and "durable_records" in _stmt_bound_names(stmt)
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "_run_fixed_witness_direct"
    )


def _is_evidence_init(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"evidence"}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "build_terminal_frontier_evidence"
    )


def _is_allowed_child_reserved_binding(
    node: ast.AST,
    name: str,
    *,
    scratch_state_init_id: int | None,
) -> bool:
    if name == "scratch_state":
        return isinstance(node, ast.Assign) and id(node) == scratch_state_init_id
    if name == "project_root":
        return _is_project_root_init(node)
    if name == "authority_state":
        return _is_authority_state_init(node)
    if name == "certified_final_result":
        return _is_certified_final_result_init(node)
    if name == "durable_records":
        return _is_durable_records_init(node)
    if name == "evidence":
        return _is_evidence_init(node)
    return False


def _child_reserved_binding_error(name: str) -> str:
    if name == "scratch_state":
        return "PR2 true verifier child must not rebind scratch_state"
    if name in _PR2_CHILD_AUTHORITY_NAMES:
        return f"PR2 true verifier child must not shadow {name}"
    return f"PR2 true verifier child must not shadow/rebind {name}"


def _is_supervisor_proposal_pop(stmt: ast.AST) -> bool:
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return False
    call = stmt.value
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "pop"
        and _is_name(call.func.value, "scratch_state")
        and len(call.args) == 2
        and _is_constant(call.args[0], "supervisor_proposal")
        and _is_constant(call.args[1], None)
        and not call.keywords
    )


def _last_stop_reason_terminal_dict_ok(value: ast.AST) -> bool:
    if not isinstance(value, ast.Dict) or len(value.keys) != 2:
        return False
    items: dict[str, ast.AST] = {}
    for key, item_value in zip(value.keys, value.values):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return False
        items[key.value] = item_value
    reason_value = items.get("reason")
    status_value = items.get("status")
    return (
        set(items) == {"reason", "status"}
        and isinstance(reason_value, ast.Name)
        and reason_value.id == "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON"
        and _is_constant(status_value, "CERTIFIED")
    )


def _child_elevation_slot_rhs_ok(slot: str, value: ast.AST) -> bool:
    canonical_names = {
        "final_result": "certified_final_result",
        "terminal_frontier_evidence": "evidence",
        "candidates": "durable_records",
    }
    if slot in canonical_names:
        return _is_name(value, canonical_names[slot])
    if slot == "final_status":
        return _is_constant(value, "CERTIFIED")
    if slot == "declare_mode":
        return _is_constant(value, "strict")
    if slot == "last_stop_reason":
        return _last_stop_reason_terminal_dict_ok(value)
    return False


def _child_elevation_slot_rhs_error(slot: str) -> str:
    canonical_names = {
        "final_result": 'Name("certified_final_result")',
        "terminal_frontier_evidence": 'Name("evidence")',
        "candidates": 'Name("durable_records")',
        "final_status": 'constant "CERTIFIED"',
        "declare_mode": 'constant "strict"',
        "last_stop_reason": 'exactly {"reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON, "status": "CERTIFIED"}',
    }
    return (
        f'PR2 true verifier child scratch_state["{slot}"] RHS must be '
        f"{canonical_names[slot]}"
    )


def _is_precheck_assign(stmt: ast.AST) -> tuple[str, ast.Call] | None:
    if (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value)
        == "terminal_certified_final_result_project_precheck_violation"
    ):
        return stmt.targets[0].id, stmt.value
    return None


def _is_geometry_rederivation_assign(stmt: ast.AST) -> tuple[str, ast.Call] | None:
    if (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "canonical_candidate_geometry_rederivation_violation"
    ):
        return stmt.targets[0].id, stmt.value
    return None


def _if_consumes_precheck_result(stmt: ast.AST, result_name: str) -> bool:
    if not isinstance(stmt, ast.If):
        return False
    test = stmt.test
    if not (
        isinstance(test, ast.Compare)
        and _is_name(test.left, result_name)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and len(test.comparators) == 1
        and _is_constant(test.comparators[0], None)
    ):
        return False
    return len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Raise) and not stmt.orelse


def _canonical_digest_assign(stmt: ast.AST, target_name: str, arg: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {target_name}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "_canonical_digest"
        and len(stmt.value.args) == 1
        and ast.dump(stmt.value.args[0], include_attributes=False)
        == ast.dump(arg, include_attributes=False)
        and not stmt.value.keywords
    )


def _payload_get_digest_compare(node: ast.AST, digest_name: str, payload_key: str) -> bool:
    return (
        isinstance(node, ast.Compare)
        and _is_name(node.left, digest_name)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.NotEq)
        and len(node.comparators) == 1
        and _payload_get_call(node.comparators[0], payload_key)
    )


def _digest_mismatch_if(stmt: ast.AST, digest_name: str, payload_key: str) -> bool:
    return (
        isinstance(stmt, ast.If)
        and _payload_get_digest_compare(stmt.test, digest_name, payload_key)
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], ast.Raise)
        and not stmt.orelse
    )


def _return_domain_uses_canonical_names(stmt: ast.AST) -> bool:
    if not isinstance(stmt, ast.Return):
        return False
    items = _return_dict_items(stmt)
    return items is not None and set(items) == _PR2_CHILD_RETURN_KEYS and all(
        _expr_matches_source(items[key], expected)
        for key, expected in _PR2_CHILD_RETURN_PINNED_EXPRESSIONS.items()
    )


def _return_dict_items(stmt: ast.Return) -> dict[str, ast.AST] | None:
    if not isinstance(stmt.value, ast.Dict):
        return None
    items: dict[str, ast.AST] = {}
    for key, value in zip(stmt.value.keys, stmt.value.values):
        if key is None:
            return None
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return None
        if key.value in items:
            return None
        items[key.value] = value
    return items


def _check_true_verifier_child_return_dict_closed_world(
    child_domain_fn: ast.FunctionDef,
) -> list[str]:
    errors: list[str] = []
    returns = [node for node in ast.walk(child_domain_fn) if isinstance(node, ast.Return)]
    if len(returns) != 1:
        errors.append(
            "PR2 true verifier child must have exactly one Return: the pinned final domain return"
        )
        return errors
    final_return = returns[0]
    if not child_domain_fn.body or child_domain_fn.body[-1] is not final_return:
        errors.append("PR2 true verifier child sole Return must be the final top-level statement")
        return errors
    items = _return_dict_items(final_return)
    if items is None or set(items) != _PR2_CHILD_RETURN_KEYS:
        errors.append(
            "PR2 true verifier child final return domain dict must exactly match "
            "the pinned key set and must not use ** unpacking"
        )
        return errors
    for key in sorted(_PR2_CHILD_RETURN_KEYS):
        expected = _PR2_CHILD_RETURN_PINNED_EXPRESSIONS[key]
        if not _expr_matches_source(items[key], expected):
            errors.append(
                "PR2 true verifier child final return domain key "
                f"{key} must match pinned expression {expected}"
            )
    return errors


def _check_child_unique_final_return(child_domain_fn: ast.FunctionDef) -> list[str]:
    returns = [node for node in ast.walk(child_domain_fn) if isinstance(node, ast.Return)]
    if len(returns) != 1:
        return [
            "PR2 true verifier child must have exactly one Return: the pinned final domain return"
        ]
    if not child_domain_fn.body or child_domain_fn.body[-1] is not returns[0]:
        return ["PR2 true verifier child sole Return must be the final top-level statement"]
    return []


def _check_child_precheck_call_exact(call: ast.Call) -> list[str]:
    if (
        len(call.args) == 1
        and _is_name(call.args[0], "scratch_state")
        and len(call.keywords) == 1
        and call.keywords[0].arg == "project_root"
        and _is_name(call.keywords[0].value, "project_root")
    ):
        return []
    return [
        "PR2 true verifier child terminal precheck call must be exactly "
        "terminal_certified_final_result_project_precheck_violation(scratch_state, project_root=project_root)"
    ]


def _check_child_geometry_rederivation_call_exact(call: ast.Call) -> list[str]:
    if (
        not call.args
        and len(call.keywords) == 1
        and call.keywords[0].arg == "project_root"
        and _is_name(call.keywords[0].value, "project_root")
    ):
        return []
    return [
        "PR2 true verifier child candidate-geometry rederivation call must be exactly "
        "canonical_candidate_geometry_rederivation_violation(project_root=project_root)"
    ]


def _check_child_post_precheck_tail(body: Sequence[ast.stmt], consume_idx: int) -> list[str]:
    errors: list[str] = []
    expected_arg_records = ast.Call(
        func=ast.Name(id="_stable_fixed_witness_candidate_records", ctx=ast.Load()),
        args=[ast.Name(id="durable_records", ctx=ast.Load())],
        keywords=[],
    )
    expected_tail: list[tuple[str, Callable[[ast.stmt], bool]]] = [
        (
            "geometry_reason = canonical_candidate_geometry_rederivation_violation(project_root=project_root)",
            lambda stmt: (
                (assign := _is_geometry_rederivation_assign(stmt)) is not None
                and assign[0] == "geometry_reason"
                and not _check_child_geometry_rederivation_call_exact(assign[1])
            ),
        ),
        (
            "if geometry_reason is not None: raise ...",
            lambda stmt: _if_consumes_precheck_result(stmt, "geometry_reason"),
        ),
        (
            "final_digest = _canonical_digest(certified_final_result)",
            lambda stmt: _canonical_digest_assign(
                stmt, "final_digest", ast.Name(id="certified_final_result", ctx=ast.Load())
            ),
        ),
        (
            "evidence_digest = _canonical_digest(evidence)",
            lambda stmt: _canonical_digest_assign(
                stmt, "evidence_digest", ast.Name(id="evidence", ctx=ast.Load())
            ),
        ),
        (
            "records_digest = _canonical_digest(_stable_fixed_witness_candidate_records(durable_records))",
            lambda stmt: _canonical_digest_assign(stmt, "records_digest", expected_arg_records),
        ),
        (
            "if final_digest != payload.get(\"proposal_final_result_digest\"): raise ...",
            lambda stmt: _digest_mismatch_if(stmt, "final_digest", "proposal_final_result_digest"),
        ),
        (
            "if evidence_digest != payload.get(\"proposal_terminal_frontier_evidence_digest\"): raise ...",
            lambda stmt: _digest_mismatch_if(
                stmt,
                "evidence_digest",
                "proposal_terminal_frontier_evidence_digest",
            ),
        ),
        (
            "if records_digest != payload.get(\"proposal_candidate_records_digest\"): raise ...",
            lambda stmt: _digest_mismatch_if(
                stmt,
                "records_digest",
                "proposal_candidate_records_digest",
            ),
        ),
        (
            "return domain with canonical final_result/evidence/durable_records names",
            _return_domain_uses_canonical_names,
        ),
    ]
    tail = list(body[consume_idx + 1 :])
    if len(tail) != len(expected_tail):
        errors.append(
            "PR2 true verifier child post-precheck tail must be exactly "
            "the geometry rederivation gate, 3 digest assignments, "
            "3 digest mismatch raises, and the final return"
        )
        return errors
    for offset, (description, predicate) in enumerate(expected_tail):
        if not predicate(tail[offset]):
            errors.append(
                "PR2 true verifier child post-precheck tail statement "
                f"{offset + 1} must be {description}"
            )
    return errors


def _call_has_direct_name_arg(call: ast.Call, name: str) -> bool:
    if any(_is_name(arg, name) for arg in call.args):
        return True
    return any(keyword.value is not None and _is_name(keyword.value, name) for keyword in call.keywords)


def _nested_scratch_slot(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Subscript):
        return _subscript_constant_slot(node.value, "scratch_state")
    return None


def _check_true_verifier_child_domain_elevation_window(
    child_domain_fn: ast.FunctionDef,
) -> list[str]:
    errors: list[str] = _check_child_unique_final_return(child_domain_fn)
    body = child_domain_fn.body
    init_positions: list[tuple[int, ast.Assign]] = []
    precheck_positions: list[tuple[int, str, ast.Assign, ast.Call]] = []
    for idx, stmt in enumerate(body):
        if isinstance(stmt, ast.Assign) and _is_dict_copy_from_authority_state(stmt):
            init_positions.append((idx, stmt))
        precheck = _is_precheck_assign(stmt)
        if precheck is not None:
            result_name, call = precheck
            assert isinstance(stmt, ast.Assign)
            precheck_positions.append((idx, result_name, stmt, call))

    init_stmt: ast.Assign | None = None
    precheck_call: ast.Call | None = None
    allowed_slot_assign_ids: set[int] = set()

    if len(init_positions) != 1:
        errors.append(
            "PR2 true verifier child must have exactly one top-level "
            "scratch_state = dict(authority_state) init"
        )
    else:
        _init_idx, init_stmt = init_positions[0]

    if len(precheck_positions) != 1:
        errors.append(
            "PR2 true verifier child must have exactly one top-level assignment from "
            "terminal_certified_final_result_project_precheck_violation(...)"
        )

    if init_positions and precheck_positions:
        init_idx, init_stmt = init_positions[0]
        precheck_idx, precheck_result_name, _precheck_stmt, precheck_call = precheck_positions[0]
        if init_idx >= precheck_idx:
            errors.append("PR2 true verifier child scratch_state init must precede terminal precheck")
        slot_assigns: dict[str, ast.Assign] = {}
        pop_count = 0
        for stmt in body[init_idx + 1 : precheck_idx]:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and (slot := _subscript_constant_slot(stmt.targets[0], "scratch_state"))
                in _PR2_CHILD_ELEVATION_SLOTS
            ):
                if slot in slot_assigns:
                    errors.append(
                        f'PR2 true verifier child canonical window assigns scratch_state["{slot}"] more than once'
                    )
                slot_assigns[slot] = stmt
                allowed_slot_assign_ids.add(id(stmt))
                continue
            if _is_supervisor_proposal_pop(stmt):
                pop_count += 1
                continue
            errors.append(
                "PR2 true verifier child canonical elevation window contains disallowed "
                f"top-level statement at line {getattr(stmt, 'lineno', '?')}"
            )
        missing_slots = sorted(_PR2_CHILD_ELEVATION_SLOTS - set(slot_assigns))
        if missing_slots:
            errors.append(
                "PR2 true verifier child canonical window missing scratch_state slots: "
                + ", ".join(missing_slots)
            )
        if pop_count != 1:
            errors.append(
                'PR2 true verifier child canonical window must have exactly one '
                'scratch_state.pop("supervisor_proposal", None)'
            )
        for slot, stmt in sorted(slot_assigns.items()):
            if not _child_elevation_slot_rhs_ok(slot, stmt.value):
                errors.append(_child_elevation_slot_rhs_error(slot))
        errors.extend(_check_child_precheck_call_exact(precheck_call))
        consume_idx = precheck_idx + 1
        if consume_idx >= len(body) or not _if_consumes_precheck_result(body[consume_idx], precheck_result_name):
            errors.append(
                "PR2 true verifier child terminal precheck result must be consumed by "
                f"the immediately following if {precheck_result_name} is not None: raise ..."
            )
        else:
            errors.extend(_check_child_post_precheck_tail(body, consume_idx))
            for stmt in body[consume_idx + 1 :]:
                for node in ast.walk(stmt):
                    bound = _stmt_bound_names(node)
                    for name in sorted(bound & _PR2_CHILD_POST_PRECHECK_PROTECTED_NAMES):
                        errors.append(
                            f"PR2 true verifier child must not rebind {name} after terminal precheck"
                        )
                    if (
                        isinstance(node, ast.Delete)
                        and any(
                            _target_bound_names(target) & _PR2_CHILD_POST_PRECHECK_PROTECTED_NAMES
                            for target in node.targets
                        )
                    ):
                        errors.append("PR2 true verifier child must not delete post-precheck domain locals")
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in _PR2_CHILD_POST_PRECHECK_PROTECTED_NAMES
                        and node.func.attr in _PR2_MUTATING_MAPPING_METHODS
                    ):
                        errors.append(
                            "PR2 true verifier child must not mutate "
                            f"{node.func.value.id}.{node.func.attr}(...) after terminal precheck"
                        )
        for stmt in body[precheck_idx + 1 :]:
            for node in ast.walk(stmt):
                if _assigns_name(node, precheck_result_name):
                    errors.append("PR2 true verifier child must not clobber the terminal precheck result")

    init_id = id(init_stmt) if init_stmt is not None else None
    precheck_call_id = id(precheck_call) if precheck_call is not None else None
    supervisor_pop_calls = [
        node
        for node in ast.walk(child_domain_fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pop"
        and _is_name(node.func.value, "scratch_state")
        and len(node.args) == 2
        and _is_constant(node.args[0], "supervisor_proposal")
        and _is_constant(node.args[1], None)
    ]
    if len(supervisor_pop_calls) != 1:
        errors.append(
            'PR2 true verifier child must have exactly one full-function '
            'scratch_state.pop("supervisor_proposal", None)'
        )
    authority_import_counts = {name: 0 for name in _PR2_CHILD_AUTHORITY_NAMES}
    for node in ast.walk(child_domain_fn):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            errors.append("PR2 true verifier child must not use global/nonlocal declarations")
        if isinstance(node, ast.Lambda):
            errors.append("PR2 true verifier child must not use lambda expressions")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for namespace in sorted(_target_dynamic_namespace_writes(target)):
                    errors.append(
                        f"PR2 true verifier child must not write dynamic namespace mapping {namespace}(...)"
                    )
                for attr_name in sorted(_target_reserved_attribute_writes(target)):
                    errors.append(
                        f"PR2 true verifier child must not assign authority/reserved attribute {attr_name}"
                    )
                for bound_name in sorted(_target_bound_names(target) & _PR2_CHILD_RESERVED_RUNTIME_NAMES):
                    if not _is_allowed_child_reserved_binding(
                        node,
                        bound_name,
                        scratch_state_init_id=init_id,
                    ):
                        errors.append(_child_reserved_binding_error(bound_name))
                direct_slot = _subscript_constant_slot(target, "scratch_state")
                if direct_slot is not None and id(node) not in allowed_slot_assign_ids:
                    errors.append(
                        f'PR2 true verifier child has non-canonical scratch_state["{direct_slot}"] assignment'
                    )
                nested_slot = _nested_scratch_slot(target)
                if nested_slot in _PR2_CHILD_ELEVATION_SLOTS:
                    errors.append(
                        f'PR2 true verifier child must not mutate nested scratch_state["{nested_slot}"][...]'
                    )
            if isinstance(node.value, ast.Name) and node.value.id == "scratch_state":
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id != "scratch_state":
                        errors.append("PR2 true verifier child must not alias scratch_state")
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            target = node.target
            for namespace in sorted(_target_dynamic_namespace_writes(target)):
                errors.append(
                    f"PR2 true verifier child must not write dynamic namespace mapping {namespace}(...)"
                )
            for attr_name in sorted(_target_reserved_attribute_writes(target)):
                errors.append(
                    f"PR2 true verifier child must not assign authority/reserved attribute {attr_name}"
                )
            for bound_name in sorted(_target_bound_names(target) & _PR2_CHILD_RESERVED_RUNTIME_NAMES):
                errors.append(_child_reserved_binding_error(bound_name))
            if _target_contains_name(target, "scratch_state"):
                errors.append("PR2 true verifier child must not AugAssign/AnnAssign scratch_state or its slots")
        elif isinstance(node, ast.Delete):
            if any(_target_contains_name(target, "scratch_state") for target in node.targets):
                errors.append("PR2 true verifier child must not delete scratch_state or its slots")
            for target in node.targets:
                for namespace in sorted(_target_dynamic_namespace_writes(target)):
                    errors.append(
                        f"PR2 true verifier child must not delete dynamic namespace mapping {namespace}(...)"
                    )
                for attr_name in sorted(_target_reserved_attribute_writes(target)):
                    errors.append(
                        f"PR2 true verifier child must not delete authority/reserved attribute {attr_name}"
                    )
                for bound_name in sorted(_target_bound_names(target) & _PR2_CHILD_RESERVED_RUNTIME_NAMES):
                    errors.append(f"PR2 true verifier child must not delete {bound_name}")
        elif isinstance(node, ast.NamedExpr):
            for bound_name in sorted(_target_bound_names(node.target) & _PR2_CHILD_RESERVED_RUNTIME_NAMES):
                errors.append(_child_reserved_binding_error(bound_name))
            if _target_contains_name(node.target, "scratch_state"):
                errors.append("PR2 true verifier child must not mutate scratch_state with assignment expressions")
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for bound_name in sorted(_target_bound_names(node.target) & _PR2_CHILD_RESERVED_RUNTIME_NAMES):
                errors.append(f"PR2 true verifier child must not bind reserved name {bound_name} in a loop target")
            if _target_contains_name(node.target, "scratch_state"):
                errors.append("PR2 true verifier child must not bind scratch_state in a loop target")
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars is not None:
                    for bound_name in sorted(
                        _target_bound_names(item.optional_vars) & _PR2_CHILD_RESERVED_RUNTIME_NAMES
                    ):
                        errors.append(
                            f"PR2 true verifier child must not bind reserved name {bound_name} in a with target"
                        )
                if item.optional_vars is not None and _target_contains_name(item.optional_vars, "scratch_state"):
                    errors.append("PR2 true verifier child must not bind scratch_state in a with target")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not child_domain_fn:
            if node.name in _PR2_CHILD_RESERVED_RUNTIME_NAMES:
                errors.append(f"PR2 true verifier child must not define reserved name {node.name}")
        elif isinstance(node, ast.Import):
            errors.append("PR2 true verifier child must not use bare import statements")
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                if bound_name in _PR2_CHILD_RESERVED_RUNTIME_NAMES:
                    errors.append(f"PR2 true verifier child must not import-as reserved name {bound_name}")
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    errors.append("PR2 true verifier child must not import importlib dynamically")
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound_name = alias.asname or alias.name
                if alias.name in _PR2_CHILD_AUTHORITY_NAMES or bound_name in _PR2_CHILD_AUTHORITY_NAMES:
                    if (
                        node.module != _PR2_CHILD_AUTHORITY_IMPORT_MODULE
                        or alias.asname is not None
                        or alias.name != bound_name
                    ):
                        errors.append(
                            "PR2 true verifier child authority imports must come directly from "
                            f"{_PR2_CHILD_AUTHORITY_IMPORT_MODULE}"
                        )
                    else:
                        authority_import_counts[alias.name] += 1
                if (
                    bound_name in _PR2_CHILD_RESERVED_RUNTIME_NAMES
                    and alias.name not in _PR2_CHILD_AUTHORITY_NAMES
                ):
                    errors.append(f"PR2 true verifier child must not import-as reserved name {bound_name}")
        elif isinstance(node, ast.Call):
            call_name = _call_func_name(node)
            if call_name in _PR2_CHILD_DYNAMIC_MODULE_CALLS or (
                call_name is not None and call_name.startswith("importlib.")
            ):
                errors.append(f"PR2 true verifier child must not use dynamic module capability {call_name}")
            if call_name in _PR2_CHILD_FRAME_CALLS:
                errors.append(f"PR2 true verifier child must not use frame access {call_name}")
            if (
                isinstance(node.func, ast.Attribute)
                and _is_name(node.func.value, "scratch_state")
                and node.func.attr in _PR2_MUTATING_MAPPING_METHODS
            ):
                if not (
                    node.func.attr == "pop"
                    and len(node.args) == 2
                    and _is_constant(node.args[0], "supervisor_proposal")
                    and _is_constant(node.args[1], None)
                ):
                    errors.append(
                        f"PR2 true verifier child must not call scratch_state.{node.func.attr}(...)"
                    )
            if isinstance(node.func, ast.Attribute) and node.func.attr in _PR2_MUTATING_MAPPING_METHODS:
                nested_slot = _subscript_constant_slot(node.func.value, "scratch_state")
                if nested_slot in _PR2_CHILD_ELEVATION_SLOTS:
                    errors.append(
                        f'PR2 true verifier child must not call scratch_state["{nested_slot}"].{node.func.attr}(...)'
                    )
            if _call_has_direct_name_arg(node, "scratch_state"):
                if not (
                    call_name == "dict"
                    or (
                        call_name == "terminal_certified_final_result_project_precheck_violation"
                        and id(node) == precheck_call_id
                    )
                ):
                    errors.append(
                        "PR2 true verifier child must not pass scratch_state to helper calls "
                        "other than dict(...) or the terminal precheck"
                    )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "modules"
            and _is_name(node.value, "sys")
        ):
            errors.append("PR2 true verifier child must not access sys.modules")
        elif isinstance(node, ast.Attribute):
            if node.attr == "_getframe" and _is_name(node.value, "sys"):
                errors.append("PR2 true verifier child must not access sys._getframe")
            if node.attr in _PR2_CHILD_FRAME_ATTRS:
                errors.append(f"PR2 true verifier child must not access frame attribute {node.attr}")
            if node.attr == "__dict__":
                errors.append("PR2 true verifier child must not access __dict__")
    for name, count in sorted(authority_import_counts.items()):
        if count != 1:
            errors.append(
                "PR2 true verifier child must import authority name exactly once from "
                f"{_PR2_CHILD_AUTHORITY_IMPORT_MODULE}: {name}"
            )
    return errors


def _getattr_call_allowed(call: ast.Call) -> bool:
    if _call_func_name(call) != "getattr" or call.keywords:
        return False
    if len(call.args) not in {2, 3}:
        return False
    if not isinstance(call.args[0], ast.Name):
        return False
    if not isinstance(call.args[1], ast.Constant) or not isinstance(call.args[1].value, str):
        return False
    default: object = None
    if len(call.args) == 3:
        if not isinstance(call.args[2], ast.Constant):
            return False
        default = call.args[2].value
    return (call.args[0].id, call.args[1].value, default) in _PR2_CHILD_GETATTR_ALLOWLIST


def _importfrom_allowed(node: ast.ImportFrom) -> bool:
    if node.level != 0 or node.module not in _PR2_CHILD_DOMAIN_IMPORTFROM_ALLOWLIST:
        return False
    if any(alias.asname is not None for alias in node.names):
        return False
    allowed = _PR2_CHILD_DOMAIN_IMPORTFROM_ALLOWLIST[node.module]
    imported = {alias.name for alias in node.names}
    return imported <= allowed


def _check_true_verifier_child_closed_world(
    child_domain_fn: ast.FunctionDef,
) -> list[str]:
    errors: list[str] = []
    authority_import_counts: dict[tuple[str, str], int] = {
        (module, name): 0
        for module, names in _PR2_CHILD_DOMAIN_IMPORTFROM_ALLOWLIST.items()
        for name in names
    }
    for node in ast.walk(child_domain_fn):
        if node is not child_domain_fn and isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            errors.append("PR2 true verifier child closed-world body must not define nested code objects")
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            errors.append("PR2 true verifier child closed-world body must not reference __builtins__")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                errors.append(
                    "PR2 true verifier child closed-world body must not access dunder attribute "
                    f"{node.attr}"
                )
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if any(isinstance(child, ast.Attribute) for child in ast.walk(target)):
                    errors.append(
                        "PR2 true verifier child closed-world body must not assign to attributes"
                    )
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if any(isinstance(child, ast.Attribute) for child in ast.walk(target)):
                    errors.append(
                        "PR2 true verifier child closed-world body must not delete attributes"
                    )
        if isinstance(node, ast.ImportFrom):
            if not _importfrom_allowed(node):
                errors.append(
                    "PR2 true verifier child closed-world ImportFrom outside pinned allowlist"
                )
            else:
                assert node.module is not None
                for alias in node.names:
                    authority_import_counts[(node.module, alias.name)] += 1
        if isinstance(node, ast.Call) and _call_func_name(node) == "getattr":
            if not _getattr_call_allowed(node):
                errors.append(
                    "PR2 true verifier child closed-world getattr call outside pinned allowlist"
                )
    for (module, name), count in sorted(authority_import_counts.items()):
        if count != 1:
            errors.append(
                "PR2 true verifier child closed-world import pin must import "
                f"{name} exactly once from {module}"
            )
    return errors


def _child_module_import_allowed(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Import):
        return all(
            ("import", alias.name, alias.asname) in _PR2_CHILD_MODULE_IMPORT_ALLOWLIST
            for alias in stmt.names
        )
    if isinstance(stmt, ast.ImportFrom):
        return all(
            ("from", stmt.module, alias.name) in _PR2_CHILD_MODULE_IMPORT_ALLOWLIST
            and alias.asname is None
            and stmt.level == 0
            for alias in stmt.names
        )
    return False


def _inert_default_value(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_inert_default_value(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            key is not None and _inert_default_value(key) and _inert_default_value(value)
            for key, value in zip(node.keys, node.values)
        )
    return False


def _check_function_import_time_shape(function: ast.FunctionDef, *, label: str) -> list[str]:
    errors: list[str] = []
    if function.decorator_list:
        errors.append(f"{label} must not use decorators")
    defaults = list(function.args.defaults) + [
        default for default in function.args.kw_defaults if default is not None
    ]
    for default in defaults:
        if not _inert_default_value(default):
            errors.append(f"{label} defaults must be inert literals or None")
    return errors


_PR2_DANGEROUS_DUNDER_ATTRS = frozenset(
    {
        "__bases__",
        "__class__",
        "__code__",
        "__delattr__",
        "__delitem__",
        "__dict__",
        "__getattribute__",
        "__globals__",
        "__ior__",
        "__mro__",
        "__setattr__",
        "__setitem__",
        "__subclasses__",
    }
)


def _check_child_runtime_function_closed_world(
    function: ast.FunctionDef,
    *,
    label: str,
    allowed_dynamic_module_calls: frozenset[str] = frozenset(),
    check_reserved_shadow: bool = True,
) -> list[str]:
    errors: list[str] = []
    reserved_shadow_names = _PR2_CHILD_RESERVED_SHADOW_NAMES if check_reserved_shadow else frozenset()
    for node in ast.walk(function):
        if node is not function and isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            errors.append(f"{label} body must not define nested code objects")
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            errors.append(f"{label} body must not reference __builtins__")
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for namespace in sorted(_target_dynamic_namespace_writes(target)):
                    errors.append(f"{label} body must not write dynamic namespace mapping {namespace}(...)")
                for bound_name in sorted(_target_bound_names(target) & reserved_shadow_names):
                    errors.append(f"{label} body must not shadow/rebind {bound_name}")
                for child in ast.walk(target):
                    if (
                        isinstance(child, ast.Attribute)
                        and child.attr in _PR2_DANGEROUS_DUNDER_ATTRS
                    ):
                        errors.append(f"{label} body must not assign to dunder attribute {child.attr}")
        if isinstance(node, ast.Delete):
            for target in node.targets:
                for namespace in sorted(_target_dynamic_namespace_writes(target)):
                    errors.append(f"{label} body must not delete dynamic namespace mapping {namespace}(...)")
                for bound_name in sorted(_target_bound_names(target) & reserved_shadow_names):
                    errors.append(f"{label} body must not delete {bound_name}")
                for child in ast.walk(target):
                    if (
                        isinstance(child, ast.Attribute)
                        and child.attr in _PR2_DANGEROUS_DUNDER_ATTRS
                    ):
                        errors.append(f"{label} body must not delete dunder attribute {child.attr}")
        if isinstance(node, ast.Import):
            errors.append(f"{label} body must not use bare import statements")
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                if bound_name in reserved_shadow_names:
                    errors.append(f"{label} body must not import-as reserved name {bound_name}")
        if isinstance(node, ast.ImportFrom):
            if (
                node.level != 0
                or node.module not in _PR2_CHILD_HELPER_IMPORTFROM_ALLOWLIST
                or any(alias.asname is not None for alias in node.names)
            ):
                errors.append(f"{label} ImportFrom outside pinned helper allowlist")
            for alias in node.names:
                bound_name = alias.asname or alias.name
                if bound_name in reserved_shadow_names:
                    errors.append(f"{label} body must not import-as reserved name {bound_name}")
        if isinstance(node, ast.NamedExpr):
            for bound_name in sorted(_target_bound_names(node.target) & reserved_shadow_names):
                errors.append(f"{label} body must not shadow/rebind {bound_name}")
        if isinstance(node, (ast.For, ast.AsyncFor)):
            for bound_name in sorted(_target_bound_names(node.target) & reserved_shadow_names):
                errors.append(f"{label} body must not bind reserved name {bound_name} in a loop target")
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is None:
                    continue
                for bound_name in sorted(
                    _target_bound_names(item.optional_vars) & reserved_shadow_names
                ):
                    errors.append(f"{label} body must not bind reserved name {bound_name} in a with target")
        if isinstance(node, ast.Call):
            call_name = _call_func_name(node)
            if (
                call_name is not None
                and call_name not in allowed_dynamic_module_calls
                and (
                    call_name in _PR2_CHILD_DYNAMIC_MODULE_CALLS
                    or call_name.startswith("importlib.")
                )
            ):
                errors.append(f"{label} body must not use dynamic module capability {call_name}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in _PR2_DANGEROUS_DUNDER_ATTRS:
                errors.append(f"{label} body must not call dunder attribute {node.func.attr}")
        if isinstance(node, ast.Attribute):
            if node.attr in _PR2_DANGEROUS_DUNDER_ATTRS:
                errors.append(f"{label} body must not access dunder attribute {node.attr}")
            if node.attr == "modules" and _is_name(node.value, "sys"):
                errors.append(f"{label} body must not access sys.modules")
            if node.attr == "_getframe" and _is_name(node.value, "sys"):
                errors.append(f"{label} body must not access sys._getframe")
            if node.attr in _PR2_CHILD_FRAME_ATTRS:
                errors.append(f"{label} body must not access frame attribute {node.attr}")
    return errors


def _check_child_class_closed_world(class_node: ast.ClassDef) -> list[str]:
    label = f"PR2 true verifier child class {class_node.name}"
    errors: list[str] = []
    if class_node.decorator_list:
        errors.append(f"{label} must not use decorators")
    if class_node.keywords:
        errors.append(f"{label} must not use metaclass/keywords")
    expected_bases = _PR2_CHILD_CLASS_BASE_SOURCES.get(class_node.name)
    actual_bases = tuple(ast.unparse(base) for base in class_node.bases)
    if actual_bases != expected_bases:
        errors.append(f"{label} bases must match the pinned loader base list")
    expected_methods = _PR2_CHILD_CLASS_METHODS.get(class_node.name, frozenset())
    actual_methods = {stmt.name for stmt in class_node.body if isinstance(stmt, ast.FunctionDef)}
    if actual_methods != expected_methods:
        errors.append(
            f"{label} method set must be exactly {sorted(expected_methods)}"
        )
    for stmt in class_node.body:
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue
        if isinstance(stmt, ast.FunctionDef):
            errors.extend(_check_function_import_time_shape(stmt, label=f"{label}.{stmt.name}"))
            errors.extend(
                _check_child_runtime_function_closed_world(
                    stmt,
                    label=f"{label}.{stmt.name}",
                    allowed_dynamic_module_calls=_PR2_CHILD_CLASS_ALLOWED_DYNAMIC_CALLS,
                )
            )
            expected_body = _PR2_CHILD_CLASS_METHOD_BODIES.get((class_node.name, stmt.name))
            if expected_body is None:
                errors.append(f"{label}.{stmt.name} has no pinned loader method body")
            else:
                errors.extend(
                    _check_top_level_body_closed_world(
                        stmt,
                        expected_body=expected_body,
                        label=f"{label}.{stmt.name}",
                    )
                )
            continue
        errors.append(
            f"{label} body contains import-time executable statement "
            f"{type(stmt).__name__} at line {getattr(stmt, 'lineno', '?')}"
        )
    return errors


def _check_unique_top_level_bindings(
    tree: ast.Module,
    names: frozenset[str],
    *,
    path: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    for name in sorted(names):
        points = _top_level_binding_points(tree, name)
        if len(points) > 1:
            lines = ", ".join(str(getattr(node, "lineno", "?")) for node in points)
            errors.append(f"{label} top-level binding for {name} must be unique; found lines {lines}")
    return errors


def _check_child_module_assignment(stmt: ast.Assign) -> list[str]:
    if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
        return ["PR2 true verifier child module top level must not assign non-Name targets"]
    name = stmt.targets[0].id
    expected_source = _PR2_CHILD_TOP_LEVEL_CONSTANT_SOURCES.get(name)
    if expected_source is None:
        return [f"PR2 true verifier child module top level must not bind {name}"]
    if not _expr_matches_source(stmt.value, expected_source):
        return [f"PR2 true verifier child module constant {name} must match pinned source"]
    return []


def _check_child_module_toplevel_closed_world(child_tree: ast.Module) -> list[str]:
    errors: list[str] = []
    watched_bindings = (
        frozenset(_PR2_CHILD_TOP_LEVEL_CONSTANT_SOURCES)
        | _PR2_CHILD_TOP_LEVEL_FUNCTIONS
        | _PR2_CHILD_TOP_LEVEL_CLASSES
        | _PR2_CHILD_RESERVED_RUNTIME_NAMES
    )
    errors.extend(
        _check_unique_top_level_bindings(
            child_tree,
            watched_bindings,
            path=PR2_L0_TRUE_VERIFIER_CHILD_PATH,
            label="PR2 true verifier child module",
        )
    )
    for stmt in child_tree.body:
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue
        if _child_module_import_allowed(stmt):
            continue
        if isinstance(stmt, ast.Assign):
            errors.extend(_check_child_module_assignment(stmt))
            continue
        if isinstance(stmt, ast.AnnAssign):
            errors.append("PR2 true verifier child module top level must not use AnnAssign")
            continue
        if isinstance(stmt, ast.AsyncFunctionDef):
            errors.append("PR2 true verifier child module top level must not define async functions")
            continue
        if isinstance(stmt, ast.FunctionDef):
            if stmt.name not in _PR2_CHILD_TOP_LEVEL_FUNCTIONS:
                errors.append(f"PR2 true verifier child module top level has unpinned function {stmt.name}")
                continue
            errors.extend(
                _check_function_import_time_shape(
                    stmt,
                    label=f"PR2 true verifier child function {stmt.name}",
                )
            )
            errors.extend(
                _check_child_runtime_function_closed_world(
                    stmt,
                    label=f"PR2 true verifier child function {stmt.name}",
                    check_reserved_shadow=stmt.name != "_verify_supervisor_domain",
                )
            )
            continue
        if isinstance(stmt, ast.ClassDef):
            if stmt.name not in _PR2_CHILD_TOP_LEVEL_CLASSES:
                errors.append(f"PR2 true verifier child module top level has unpinned class {stmt.name}")
                continue
            errors.extend(_check_child_class_closed_world(stmt))
            continue
        errors.append(
            "PR2 true verifier child module top level contains disallowed statement "
            f"{type(stmt).__name__} at line {getattr(stmt, 'lineno', '?')}"
        )
    return errors


def _check_true_verifier_child_module_closed_world(child_tree: ast.Module) -> list[str]:
    return _check_child_module_toplevel_closed_world(child_tree)


def _slot_assignment_lineno(stmt: ast.Assign) -> int:
    return int(getattr(stmt, "end_lineno", getattr(stmt, "lineno", 0)) or 0)


def _node_starts_after(node: ast.AST, anchor: ast.AST) -> bool:
    node_pos = (
        int(getattr(node, "lineno", 0) or 0),
        int(getattr(node, "col_offset", 0) or 0),
    )
    anchor_pos = (
        int(getattr(anchor, "lineno", 0) or 0),
        int(getattr(anchor, "col_offset", 0) or 0),
    )
    return node_pos > anchor_pos


def _check_no_direct_top_level_exit_before_node(
    function: ast.FunctionDef,
    anchor: ast.AST,
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []
    for stmt in function.body:
        if stmt is anchor:
            break
        if not hasattr(stmt, "lineno") or _node_starts_after(stmt, anchor):
            break
        if isinstance(stmt, (ast.Return, ast.Raise)):
            errors.append(
                f"{label} must not have an unconditional top-level "
                f"{type(stmt).__name__} before its pinned live statement"
            )
    return errors


_PR2_SUPERVISOR_TRANSITION_STRICT_PREFIX = (
    'if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n'
    '    return "supervisor_seal_proposal_status_invalid"',
    "if SUPERVISOR_SEAL_STATE_KEY in proposal_state:\n"
    '    return "supervisor_seal_proposal_already_sealed"',
    "proposal_record = proposal_state.get(SUPERVISOR_PROPOSAL_STATE_KEY)",
    "proposal_violation = _proposal_state_violation("
    "proposal_record, "
    "expected_campaign_instance_id=str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY))"
    ")",
    "if proposal_violation is not None:\n"
    '    return f"supervisor_seal_{proposal_violation}"',
    "if not isinstance(proposal_record, Mapping):\n"
    '    return "supervisor_seal_supervisor_proposal_invalid"',
    'if str(proposal_record.get("run_id")) != str(seal_record.get("proposal_run_id")):\n'
    '    return "supervisor_seal_proposal_run_id_mismatch"',
    "if str(proposal_state.get(CAMPAIGN_INSTANCE_ID_KEY)) != "
    "str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY)):\n"
    '    return "supervisor_seal_proposal_campaign_instance_id_mismatch"',
    "expected = dict(proposal_state)",
    'expected["final_status"] = "CERTIFIED"',
)
_PR2_L0_POSTWRITE_STRICT_GUARD_PREFIX = (
    "if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:\n"
    '    return "supervisor_seal_certified_state_sha256_mismatch"',
)
_PR2_L0_SUPERVISOR_TRANSITION_BODY = (
    "if str(proposal_state.get('final_status')) != CANDIDATE_PROPOSED_STATUS:\n"
    "    return 'supervisor_seal_proposal_status_invalid'",
    "if SUPERVISOR_SEAL_STATE_KEY in proposal_state:\n"
    "    return 'supervisor_seal_proposal_already_sealed'",
    "proposal_record = proposal_state.get(SUPERVISOR_PROPOSAL_STATE_KEY)",
    "proposal_violation = _proposal_state_violation("
    "proposal_record, "
    "expected_campaign_instance_id=str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY))"
    ")",
    "if proposal_violation is not None:\n"
    "    return f'supervisor_seal_{proposal_violation}'",
    "if not isinstance(proposal_record, Mapping):\n"
    "    return 'supervisor_seal_supervisor_proposal_invalid'",
    "if str(proposal_record.get('run_id')) != str(seal_record.get('proposal_run_id')):\n"
    "    return 'supervisor_seal_proposal_run_id_mismatch'",
    "if str(proposal_state.get(CAMPAIGN_INSTANCE_ID_KEY)) != "
    "str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY)):\n"
    "    return 'supervisor_seal_proposal_campaign_instance_id_mismatch'",
    "expected = dict(proposal_state)",
    "expected['final_status'] = 'CERTIFIED'",
    "expected['declare_mode'] = 'strict'",
    "final_result = proposal_state.get('final_result')",
    "if not isinstance(final_result, Mapping):\n"
    "    return 'supervisor_seal_proposal_final_result_invalid'",
    "expected_final_result = dict(final_result)",
    "expected_final_result['search_status'] = 'CERTIFIED'",
    "expected['final_result'] = expected_final_result",
    "expected.pop(SUPERVISOR_PROPOSAL_STATE_KEY, None)",
    "expected[SUPERVISOR_SEAL_STATE_KEY] = dict(seal_record)",
    "certified_stop = certified_state.get('last_stop_reason')",
    "if not isinstance(certified_stop, Mapping):\n"
    "    return 'supervisor_seal_certified_stop_invalid'",
    "try:\n"
    "    stop_timestamp = _strict_timestamp(certified_stop.get('updated_at'))\n"
    "    updated_at = _strict_timestamp(certified_state.get('updated_at'))\n"
    "except Exception:\n"
    "    return 'supervisor_seal_certified_updated_at_invalid'",
    "expected['last_stop_reason'] = {"
    "'reason': TERMINAL_CERTIFIED_REASON, "
    "'status': 'CERTIFIED', "
    "'updated_at': stop_timestamp"
    "}",
    "expected['updated_at'] = updated_at",
    "try:\n"
    "    if _canonical_bytes(expected) != _canonical_bytes(certified_state):\n"
    "        return 'supervisor_seal_transition_mismatch'\n"
    "except Exception:\n"
    "    return 'supervisor_seal_transition_invalid'",
    "return None",
)
_PR2_EXACT_SUPERVISOR_TRANSITION_BODY = (
    "if str(proposal_state.get('final_status')) != CANDIDATE_PROPOSED_STATUS:\n"
    "    return 'supervisor_seal_proposal_status_invalid'",
    "if SUPERVISOR_SEAL_STATE_KEY in proposal_state:\n"
    "    return 'supervisor_seal_proposal_already_sealed'",
    "proposal_record = proposal_state.get(SUPERVISOR_PROPOSAL_STATE_KEY)",
    "proposal_violation = _proposal_state_violation("
    "proposal_record, "
    "expected_campaign_instance_id=str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY))"
    ")",
    "if proposal_violation is not None:\n"
    "    return f'supervisor_seal_{proposal_violation}'",
    "if not isinstance(proposal_record, Mapping):\n"
    "    return 'supervisor_seal_supervisor_proposal_invalid'",
    "if str(proposal_record.get('run_id')) != str(seal_record.get('proposal_run_id')):\n"
    "    return 'supervisor_seal_proposal_run_id_mismatch'",
    "if str(proposal_state.get(CAMPAIGN_INSTANCE_ID_KEY)) != "
    "str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY)):\n"
    "    return 'supervisor_seal_proposal_campaign_instance_id_mismatch'",
    "expected = dict(proposal_state)",
    "expected['final_status'] = 'CERTIFIED'",
    "expected['declare_mode'] = 'strict'",
    "expected_final_result = _final_result_certified_transition(proposal_state.get('final_result'))",
    "if expected_final_result is None:\n"
    "    return 'supervisor_seal_proposal_final_result_invalid'",
    "expected['final_result'] = expected_final_result",
    "expected.pop(SUPERVISOR_PROPOSAL_STATE_KEY, None)",
    "expected[SUPERVISOR_SEAL_STATE_KEY] = dict(seal_record)",
    "certified_stop = certified_state.get('last_stop_reason')",
    "if not isinstance(certified_stop, Mapping):\n"
    "    return 'supervisor_seal_certified_stop_invalid'",
    "certified_stop_timestamp = certified_stop.get('updated_at')",
    "try:\n"
    "    _strict_resume_timestamp(certified_stop_timestamp, 'last_stop_reason.updated_at')\n"
    "except Exception:\n"
    "    return 'supervisor_seal_certified_stop_timestamp_invalid'",
    "expected['last_stop_reason'] = {"
    "'reason': TERMINAL_FULL_FRONTIER_CERTIFIED_REASON, "
    "'status': 'CERTIFIED', "
    "'updated_at': str(certified_stop_timestamp)"
    "}",
    "certified_updated_at = certified_state.get('updated_at')",
    "try:\n"
    "    _strict_resume_timestamp(certified_updated_at, 'updated_at')\n"
    "except Exception:\n"
    "    return 'supervisor_seal_certified_updated_at_invalid'",
    "expected['updated_at'] = str(certified_updated_at)",
    "try:\n"
    "    if canonical_state_bytes_for_fixed_witness(expected) != "
    "canonical_state_bytes_for_fixed_witness(certified_state):\n"
    "        return 'supervisor_seal_transition_mismatch'\n"
    "except Exception:\n"
    "    return 'supervisor_seal_transition_invalid'",
    "return None",
)
_PR2_L0_POSTWRITE_BODY = (
    "if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:\n"
    "    return 'supervisor_seal_certified_state_sha256_mismatch'",
    "if str(disk_state.get('declare_mode')) != 'strict':\n"
    "    return 'postwrite_declare_mode_not_strict'",
    "if _canonical_digest(disk_state.get('final_result')) != "
    "expected_domain.get('final_result_digest'):\n"
    "    return 'postwrite_final_result_digest_mismatch'",
    "if _canonical_digest(disk_state.get('terminal_frontier_evidence')) != "
    "expected_domain.get('terminal_frontier_evidence_digest'):\n"
    "    return 'postwrite_terminal_frontier_evidence_digest_mismatch'",
    "candidates = disk_state.get('candidates')",
    "if not isinstance(candidates, Mapping):\n"
    "    return 'postwrite_candidate_records_invalid'",
    "if _canonical_digest(_stable_fixed_witness_candidate_records_l0(candidates)) != "
    "expected_domain.get('candidate_records_digest'):\n"
    "    return 'postwrite_candidate_records_digest_mismatch'",
    "return _supervisor_seal_state_violation_l0("
    "disk_state.get(SUPERVISOR_SEAL_STATE_KEY), state=disk_state"
    ")",
)
_PR2_CHILD_VERIFY_BODY = (
    'nonce = str(request.get("nonce", ""))',
    'payload = request.get("payload")',
    'if not isinstance(payload, Mapping):\n'
    '    raise ValueError("payload must be a mapping")',
    'if payload.get("action") != "supervisor_domain":\n'
    '    return {"verdict": REJECTED, "nonce": nonce, "reason": "unsupported_action"}',
    'try:\n'
    '    _install_third_party_floor(payload.get("dependency_floor"))\n'
    '    domain = _verify_supervisor_domain(payload, nonce=nonce)\n'
    'except Exception as exc:\n'
    '    detail = "|".join(traceback.format_exc(limit=8).splitlines()[-8:])\n'
    '    return {\n'
    '        "verdict": REJECTED,\n'
    '        "nonce": nonce,\n'
    '        "reason": f"true_verifier_exception:{type(exc).__name__}:{exc}:{detail}",\n'
    '    }',
    'return {\n'
    '    "verdict": SEALED,\n'
    '    "nonce": nonce,\n'
    '    "reason": "domain_verified",\n'
    '    "domain": domain,\n'
    '}',
)
_PR2_CHILD_VERIFY_SUPERVISOR_DOMAIN_BODY = (
    'required = {\n        "action",\n        "schema_version",\n        "authority",\n        "project_root",\n        "authority_state",\n        "authority_state_b64",\n        "strong_keys",\n        "proposal_final_result_digest",\n        "proposal_terminal_frontier_evidence_digest",\n        "proposal_candidate_records_digest",\n        "dependency_floor",\n    }',
    'if set(payload.keys()) != required:\n        raise ValueError("supervisor domain request fields invalid")',
    'if _strict_int(payload.get("schema_version"), "domain.schema_version") != DOMAIN_SCHEMA_VERSION:\n        raise ValueError("supervisor domain request schema invalid")',
    'if payload.get("authority") != DOMAIN_AUTHORITY:\n        raise ValueError("supervisor domain request authority invalid")',
    'project_root = Path(_strict_string(payload.get("project_root"), "project_root")).resolve()',
    '_materialize_import_default_artifacts(project_root)',
    'authority_state = _json_copy(_require_mapping(payload.get("authority_state"), "authority_state"))',
    'authority_bytes = base64.b64decode(\n        _strict_string(payload.get("authority_state_b64"), "authority_state_b64").encode("ascii"),\n        validate=True,\n    )',
    'if _json_copy(json.loads(authority_bytes.decode("utf-8"))) != authority_state:\n        raise ValueError("authority_state_bytes_mismatch")',
    'strong_keys = _string_list(payload.get("strong_keys"))',
    'if strong_keys != sorted(str(key) for key in strong_keys):\n        raise ValueError("strong_keys_not_sorted")',
    'final_result = _require_mapping(authority_state.get("final_result"), "final_result")',
    'certified_final_result = dict(final_result)',
    'certified_final_result["search_status"] = "CERTIFIED"',
    'replayed_records, replay_violations = _project_candidate_records_direct(\n        state=authority_state,\n        project_root=project_root,\n        strong_keys=strong_keys,\n    )',
    'if replay_violations:\n        first_key = sorted(replay_violations)[0]\n        raise ValueError(f"terminal candidate sink replay failed:{replay_violations[first_key]}")',
    'durable_records, public_records, fixed_verdict = _run_fixed_witness_direct(\n        state=authority_state,\n        project_root=project_root,\n        candidate_records=replayed_records,\n        final_result=certified_final_result,\n    )',
    'fixed_violations: dict[str, str] = {}',
    'if getattr(fixed_verdict, "publishable", False) is not True:\n        fixed_violations[str(getattr(fixed_verdict, "candidate_key", None) or "*")] = str(\n            getattr(fixed_verdict, "reason", None) or "terminal_fixed_witness_rejected"\n        )',
    'if fixed_violations:\n        first_key = sorted(fixed_violations)[0]\n        raise ValueError(f"terminal fixed witness verifier failed:{fixed_violations[first_key]}")',
    'from src.search.pr2_l0_frontier_core import (\n        build_terminal_frontier_evidence,\n        candidate_generation_kwargs,\n        generate_candidate_sizes,\n    )',
    'from src.search.pr2_l0_artifact_core import (\n        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n        canonical_candidate_geometry_rederivation_violation,\n        terminal_certified_final_result_project_precheck_violation,\n    )',
    'proposal_evidence = _require_mapping(\n        authority_state.get("terminal_frontier_evidence"),\n        "terminal_frontier_evidence",\n    )',
    'candidate_generation = _require_mapping(\n        proposal_evidence.get("candidate_generation"),\n        "candidate_generation",\n    )',
    'candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))',
    'evidence = build_terminal_frontier_evidence(\n        candidates=candidates,\n        candidate_records=public_records,\n        final_result=certified_final_result,\n        candidate_generation=candidate_generation,\n    )',
    'scratch_state = dict(authority_state)',
    'scratch_state["final_result"] = certified_final_result',
    'scratch_state["final_status"] = "CERTIFIED"',
    'scratch_state["declare_mode"] = "strict"',
    'scratch_state["last_stop_reason"] = {\n        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n        "status": "CERTIFIED",\n    }',
    'scratch_state["terminal_frontier_evidence"] = evidence',
    'scratch_state["candidates"] = durable_records',
    'scratch_state.pop("supervisor_proposal", None)',
    'precheck_reason = terminal_certified_final_result_project_precheck_violation(\n        scratch_state,\n        project_root=project_root,\n    )',
    'if precheck_reason is not None:\n        raise ValueError(f"terminal project precheck failed:{precheck_reason}")',
    'geometry_reason = canonical_candidate_geometry_rederivation_violation(\n        project_root=project_root,\n    )',
    'if geometry_reason is not None:\n        raise ValueError(\n            f"terminal candidate geometry rederivation failed:{geometry_reason}"\n        )',
    'final_digest = _canonical_digest(certified_final_result)',
    'evidence_digest = _canonical_digest(evidence)',
    'records_digest = _canonical_digest(_stable_fixed_witness_candidate_records(durable_records))',
    'if final_digest != payload.get("proposal_final_result_digest"):\n        raise ValueError("proposal final_result mismatch after domain verification")',
    'if evidence_digest != payload.get("proposal_terminal_frontier_evidence_digest"):\n        raise ValueError("proposal terminal_frontier_evidence mismatch after domain verification")',
    'if records_digest != payload.get("proposal_candidate_records_digest"):\n        raise ValueError("proposal candidate_records mismatch after domain verification")',
    'return {\n        "schema_version": DOMAIN_SCHEMA_VERSION,\n        "authority": DOMAIN_AUTHORITY,\n        "nonce": nonce,\n        "verdict": SEALED,\n        "reason": "domain_verified",\n        "strong_keys": list(strong_keys),\n        "final_result": certified_final_result,\n        "terminal_frontier_evidence": evidence,\n        "candidate_records": durable_records,\n        "final_result_digest": final_digest,\n        "terminal_frontier_evidence_digest": evidence_digest,\n        "candidate_records_digest": records_digest,\n        "fixed_witness_publishable": bool(getattr(fixed_verdict, "publishable", False)),\n        "sink_replay_violations": {},\n        "fixed_witness_violations": {},\n        "tcb": {\n            "python_interpreter": "NAMED-TCB",\n            "stdlib": "NAMED-TCB",\n            "third_party_native": "NAMED-TCB",\n            "os_process_file_isolation": "NAMED-TCB",\n            "windows_write_isolation_residual": "protocol_only_child_snapshot_no_write_fd_pr2c_linux_uid_namespace_pending",\n        },\n    }',
)
_PR2_CHILD_PROJECT_RECORDS_BODY = (
    'from src.search.pr2_l0_replay_core import (\n        CANDIDATE_PROOF_FIELD,\n        _invoke_isolated_replay,\n        _json_copy,\n        _replay_response_violation,\n        candidate_proof_shape_violation,\n        canonical_digest,\n    )',
    'raw_records = state.get("candidates")',
    'if not isinstance(raw_records, Mapping):\n        return {}, {"*": "candidate_sink_replay_records_missing"}',
    'expected_proofs: dict[str, dict[str, Any]] = {}',
    'violations: dict[str, str] = {}',
    'for key in strong_keys:\n        record = raw_records.get(key)\n        if not isinstance(record, Mapping):\n            violations[key] = f"candidate_sink_replay_record_invalid:{key}"\n            continue\n        proof = record.get(CANDIDATE_PROOF_FIELD)\n        violation = candidate_proof_shape_violation(\n            proof=proof,\n            record_key=key,\n            record=record,\n            state=state,\n            project_root=project_root,\n            campaign_path=None,\n        )\n        if violation is not None:\n            violations[key] = violation\n            continue\n        expected_proofs[key] = _json_copy(proof)',
    'if set(expected_proofs) | set(violations) != set(strong_keys):\n        violations["*"] = "candidate_sink_replay_strong_key_coverage_mismatch"',
    'if violations:\n        return {}, violations',
    'if not expected_proofs:\n        return {\n            str(key): _json_copy(value)\n            for key, value in raw_records.items()\n            if isinstance(value, Mapping)\n        }, {}',
    'response = _invoke_isolated_replay(\n        project_root=project_root,\n        expected_proofs=expected_proofs,\n    )',
    'envelope_violation = _replay_response_violation(\n        response=response,\n        project_root=project_root,\n        expected_proofs=expected_proofs,\n    )',
    'if envelope_violation is not None:\n        return {}, {key: envelope_violation for key in expected_proofs}',
    'results = response.get("results")',
    'if not isinstance(results, list):\n        return {}, {"*": "candidate_sink_replay_response_result_invalid"}',
    'results_by_key = {\n        str(item.get("candidate_key")): item for item in results if isinstance(item, Mapping)\n    }',
    'verified: dict[str, dict[str, Any]] = {}',
    'for key, proof in expected_proofs.items():\n        record = raw_records.get(key)\n        result = results_by_key.get(key)\n        if not isinstance(record, Mapping) or not isinstance(result, Mapping):\n            violations[key] = f"candidate_sink_replay_result_missing:{key}"\n            continue\n        claimed_status = str(proof.get("claimed_status", ""))\n        replay_status = str(result.get("replay_status", ""))\n        if replay_status != claimed_status:\n            violations[key] = (\n                f"candidate_sink_replay_status_mismatch:{key}:"\n                f"claimed={claimed_status}:replayed={replay_status}"\n            )\n            continue\n        replayed_record = _json_copy(record)\n        if claimed_status == "CERTIFIED":\n            stored_solution = record.get("solution")\n            if not isinstance(stored_solution, Mapping):\n                violations[key] = f"candidate_sink_replay_solution_missing:{key}"\n                continue\n            if proof.get("solution_digest") != canonical_digest(stored_solution):\n                violations[key] = f"candidate_sink_replay_solution_binding_mismatch:{key}"\n                continue\n            replayed_record["solution"] = _json_copy(stored_solution)\n        else:\n            replayed_record.pop("solution", None)\n        verified[key] = replayed_record',
    'if violations:\n        return {}, violations',
    'projected: dict[str, dict[str, Any]] = {}',
    'for raw_key, raw_record in raw_records.items():\n        key = str(raw_key)\n        if not isinstance(raw_record, Mapping):\n            continue\n        projected[key] = verified.get(key, _json_copy(raw_record))',
    'return projected, {}',
)
_PR2_CHILD_FIXED_WITNESS_BODY = (
    'from src.search.pr2_l0_replay_core import _materialize_replay_snapshot',
    'from src.search.pr2_l0_artifact_core import compute_exact_artifact_hashes',
    'from src.search.pr2_l0_fixed_witness_core import (\n        _apply_terminal_fixed_witness_audit_fields,\n        _copy_candidate_records,\n        _identity_from_current_records,\n        _project_terminal_fixed_witness_records_from_capsule,\n        canonical_state_bytes_for_fixed_witness,\n        verify_terminal_fixed_witness,\n    )',
    'authority_state = _json_copy(state)',
    'authority_state["candidates"] = _json_copy(candidate_records)',
    'authority_state["final_result"] = _json_copy(final_result)',
    'current_hashes = compute_exact_artifact_hashes(project_root)',
    'with tempfile.TemporaryDirectory(prefix="zmd_pr2_true_fixed_witness_") as temp_dir:\n        replay_project_root = Path(temp_dir) / "project"\n        _materialize_replay_snapshot(\n            project_root=project_root,\n            replay_project_root=replay_project_root,\n            current_artifact_hashes=current_hashes,\n        )\n        state_copy = _json_copy(authority_state)\n        verdict = verify_terminal_fixed_witness(\n            state=state_copy,\n            project_root=replay_project_root,\n            serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state_copy),\n        )',
    'durable_records = _copy_candidate_records(candidate_records)',
    'identity = _identity_from_current_records(durable_records, final_result)',
    'record = durable_records.get(identity.candidate_key)',
    'if isinstance(record, dict):\n        _apply_terminal_fixed_witness_audit_fields(\n            record,\n            verdict=verdict,\n            publishable=bool(verdict.publishable),\n            projected_status="CERTIFIED" if verdict.publishable else "UNPROVEN",\n            rejected_reason=verdict.reason,\n        )',
    'public_projection = _project_terminal_fixed_witness_records_from_capsule(\n        candidate_records=_copy_candidate_records(candidate_records),\n        final_result=final_result,\n        verdict=verdict,\n    )',
    'return durable_records, public_projection.candidate_records, verdict',
)
_PR2_L0_SUPERVISOR_SEAL_STATE_BODY = (
    "keys = {\n"
    '    "schema_version",\n'
    '    "authority",\n'
    '    "transition",\n'
    '    "proposal_run_id",\n'
    '    "proposal_checkpoint_sha256",\n'
    '    "proposal_authority_b64",\n'
    "    CAMPAIGN_INSTANCE_ID_KEY,\n"
    '    "certified_state_sha256",\n'
    '    "sealed_at",\n'
    "}",
    'if not isinstance(value, Mapping):\n    return "supervisor_seal_invalid"',
    'if set(value.keys()) != keys:\n    return "supervisor_seal_fields_invalid"',
    "try:\n"
    "    if _strict_int(value.get(\"schema_version\"), \"supervisor_seal.schema_version\") != SUPERVISOR_SEAL_SCHEMA_VERSION:\n"
    "        return \"supervisor_seal_schema_invalid\"\n"
    "except Exception:\n"
    "    return \"supervisor_seal_schema_invalid\"",
    'if value.get("authority") != SUPERVISOR_SEAL_AUTHORITY:\n'
    '    return "supervisor_seal_authority_invalid"',
    'if value.get("transition") != "proposal_to_certified_v1":\n'
    '    return "supervisor_seal_transition_invalid"',
    'if not _valid_supervisor_proposal_run_id(value.get("proposal_run_id")):\n'
    '    return "supervisor_seal_proposal_run_id_invalid"',
    'if not _is_lower_sha256(value.get("proposal_checkpoint_sha256")):\n'
    '    return "supervisor_seal_proposal_checkpoint_sha256_invalid"',
    "campaign_instance_id = value.get(CAMPAIGN_INSTANCE_ID_KEY)",
    'if not _valid_campaign_instance_id(campaign_instance_id):\n'
    '    return "supervisor_seal_campaign_instance_id_invalid"',
    'if str(campaign_instance_id) != str(state.get(CAMPAIGN_INSTANCE_ID_KEY)):\n'
    '    return "supervisor_seal_campaign_instance_id_mismatch"',
    "proposal_state, _proposal_bytes, proposal_reason = _load_sealed_proposal_authority_l0(value)",
    "if proposal_reason is not None:\n    return proposal_reason",
    "transition_reason = _supervisor_certified_transition_violation_l0(\n"
    "    proposal_state=proposal_state,\n"
    "    certified_state=state,\n"
    "    seal_record=value,\n"
    ")",
    "if transition_reason is not None:\n    return transition_reason",
    'if not _is_lower_sha256(value.get("certified_state_sha256")):\n'
    '    return "supervisor_seal_certified_state_sha256_invalid"',
    'if str(value.get("certified_state_sha256")) != _certified_state_payload_sha256_l0(state):\n'
    '    return "supervisor_seal_certified_state_sha256_mismatch"',
    "try:\n"
    '    _strict_timestamp(value.get("sealed_at"))\n'
    "except Exception:\n"
    '    return "supervisor_seal_sealed_at_invalid"',
    "return None",
)
_PR2_L0_RUN_SUPERVISOR_SEAL_BODY = (
    '"""Validate and atomically mint a supervisor seal through the PR2 L0 path."""',
    "nonce = secrets.token_hex(32)",
    "source_root = Path(__file__).resolve().parents[2]",
    "project_root = Path(request.project_root).resolve()",
    "campaign_path = Path(request.campaign_path).resolve()",
    "marker_path = Path(request.marker_path).resolve()",
    '''try:
        # B2: the durable mint loads ONLY the canonical host-pinned floor. The wrapper
        # takes no path argument by construction, so there is no caller-selected-floor
        # entry into this mint (the loader's explicit-path form is reachable only by tests).
        dependency_floor = _load_canonical_dependency_floor_manifest(source_root)
        try:
            marker_bytes = _read_regular_file_bytes(marker_path)
        except Exception:
            return _reject(nonce, "proposal_ready_marker_unreadable")
        try:
            checkpoint_bytes = _read_regular_file_bytes(campaign_path)
        except Exception:
            return _reject(nonce, "proposal_ready_marker_checkpoint_missing")
        checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        marker = _parse_mapping(marker_bytes, "proposal_ready_marker")
        marker_violation = _proposal_ready_marker_violation(
            marker,
            checkpoint_sha256=checkpoint_sha256,
            expected_campaign_instance_id=str(request.expected_campaign_instance_id),
        )
        if marker_violation is not None:
            return _reject(nonce, marker_violation)
        authority_state = _parse_mapping(checkpoint_bytes, "proposal_checkpoint")
        authority_violation = _proposal_authority_violation(
            authority_state=authority_state,
            marker=marker,
            expected_campaign_instance_id=str(request.expected_campaign_instance_id),
        )
        if authority_violation is not None:
            return _reject(nonce, authority_violation)
        strong_keys = _strong_status_keys(authority_state)
        proof_binding_violation = _strong_proof_binding_violation(
            authority_state=authority_state,
            strong_keys=strong_keys,
            project_root=project_root,
            campaign_path=campaign_path,
        )
        if proof_binding_violation is not None:
            return _reject(nonce, proof_binding_violation)

        proposal_final_result = _require_mapping(
            authority_state.get("final_result"),
            "proposal final_result invalid",
        )
        certified_final_result = dict(proposal_final_result)
        certified_final_result["search_status"] = "CERTIFIED"
        proposal_evidence = _require_mapping(
            authority_state.get("terminal_frontier_evidence"),
            "proposal terminal_frontier_evidence invalid",
        )
        proposal_candidates = _require_mapping(
            authority_state.get("candidates"),
            "proposal candidate_records invalid",
        )
        child_payload = {
            "action": "supervisor_domain",
            "schema_version": SUPERVISOR_DOMAIN_SCHEMA_VERSION,
            "authority": SUPERVISOR_DOMAIN_AUTHORITY,
            "project_root": str(project_root),
            "authority_state": authority_state,
            "authority_state_b64": base64.b64encode(checkpoint_bytes).decode("ascii"),
            "strong_keys": strong_keys,
            "proposal_final_result_digest": _canonical_digest(certified_final_result),
            "proposal_terminal_frontier_evidence_digest": _canonical_digest(proposal_evidence),
            "proposal_candidate_records_digest": _canonical_digest(
                _stable_fixed_witness_candidate_records_l0(proposal_candidates)
            ),
            "dependency_floor": dependency_floor,
        }
        child_verdict = run_l0_micro_verifier_round_trip(
            child_payload,
            timeout_seconds=float(request.timeout_seconds),
            verifier_module=TRUE_VERIFIER_MODULE,
            extra_snapshot_modules=_discover_project_snapshot_modules(source_root),
        )
        if child_verdict.status != SEALED:
            return child_verdict
        domain = child_verdict.response.get("domain")
        domain_violation = _domain_response_violation(
            domain,
            nonce=child_verdict.nonce,
            strong_keys=strong_keys,
            proposal_final_result_digest=str(child_payload["proposal_final_result_digest"]),
            proposal_evidence_digest=str(child_payload["proposal_terminal_frontier_evidence_digest"]),
            proposal_candidate_records_digest=str(child_payload["proposal_candidate_records_digest"]),
        )
        if domain_violation is not None:
            return _reject(nonce, domain_violation, floor_digest=child_verdict.floor_digest)
        assert isinstance(domain, Mapping)

        commit_timestamp = _now_iso()
        scratch_state = dict(authority_state)
        scratch_state["final_result"] = dict(domain["final_result"])
        scratch_state["final_status"] = "CERTIFIED"
        scratch_state["declare_mode"] = "strict"
        scratch_state["last_stop_reason"] = {
            "reason": TERMINAL_CERTIFIED_REASON,
            "status": "CERTIFIED",
            "updated_at": commit_timestamp,
        }
        scratch_state.pop(SUPERVISOR_PROPOSAL_STATE_KEY, None)
        scratch_state["terminal_frontier_evidence"] = dict(
            domain["terminal_frontier_evidence"]
        )
        scratch_state["candidates"] = dict(domain["candidate_records"])
        scratch_state["updated_at"] = commit_timestamp
        seal_record = {
            "schema_version": SUPERVISOR_SEAL_SCHEMA_VERSION,
            "authority": SUPERVISOR_SEAL_AUTHORITY,
            "transition": "proposal_to_certified_v1",
            "proposal_run_id": str(marker["run_id"]),
            "proposal_checkpoint_sha256": checkpoint_sha256,
            "proposal_authority_b64": base64.b64encode(checkpoint_bytes).decode("ascii"),
            CAMPAIGN_INSTANCE_ID_KEY: str(marker[CAMPAIGN_INSTANCE_ID_KEY]),
            "certified_state_sha256": _certified_state_payload_sha256_l0(scratch_state),
            "sealed_at": commit_timestamp,
        }
        scratch_state[SUPERVISOR_SEAL_STATE_KEY] = seal_record
        seal_violation = _supervisor_seal_state_violation_l0(seal_record, state=scratch_state)
        if seal_violation is not None:
            return _reject(nonce, seal_violation, floor_digest=child_verdict.floor_digest)
        pending_state_bytes = _atomic_json_bytes(scratch_state)

        with _checkpoint_write_lock_l0(campaign_path):
            current_marker_bytes = _read_regular_file_bytes(marker_path)
            current_checkpoint_bytes = _read_regular_file_bytes(campaign_path)
            current_marker = _parse_mapping(current_marker_bytes, "proposal_ready_marker")
            if dict(current_marker) != dict(marker):
                return _reject(
                    nonce,
                    "proposal authority changed before mint: proposal_ready_marker_changed_before_mint",
                    floor_digest=child_verdict.floor_digest,
                )
            if hashlib.sha256(current_checkpoint_bytes).hexdigest() != checkpoint_sha256:
                return _reject(
                    nonce,
                    "proposal checkpoint changed before mint",
                    floor_digest=child_verdict.floor_digest,
                )
            try:
                _atomic_replace_bytes(campaign_path, pending_state_bytes)
                disk_bytes = _read_regular_file_bytes(campaign_path)
                if disk_bytes != pending_state_bytes:
                    raise RuntimeError("certified checkpoint bytes mismatch")
                disk_state = _parse_mapping(disk_bytes, "certified_checkpoint")
                postwrite_violation = _postwrite_state_violation(
                    disk_state,
                    expected_domain=domain,
                    expected_payload_sha=str(seal_record["certified_state_sha256"]),
                )
                if postwrite_violation is not None:
                    raise RuntimeError(postwrite_violation)
            except Exception as exc:
                _atomic_replace_bytes(campaign_path, checkpoint_bytes)
                return _reject(
                    nonce,
                    f"postwrite_validation_failed:{type(exc).__name__}:{exc}",
                    floor_digest=child_verdict.floor_digest,
                )
            try:
                latest_marker = _parse_mapping(
                    _read_regular_file_bytes(marker_path),
                    "proposal_ready_marker",
                )
            except Exception:
                latest_marker = None
            if isinstance(latest_marker, Mapping) and dict(latest_marker) == dict(marker):
                try:
                    marker_path.unlink()
                except FileNotFoundError:
                    pass
        response = dict(child_verdict.response)
        response["l0_seal"] = {
            "schema_version": SUPERVISOR_SEAL_SCHEMA_VERSION,
            "authority": SUPERVISOR_SEAL_AUTHORITY,
            "checkpoint_sha256": hashlib.sha256(pending_state_bytes).hexdigest(),
            "strong_key_count": len(strong_keys),
            "write_isolation": "protocol_l0_parent_writer_child_snapshot_only_named_tcb",
            "third_party_native": "NAMED-TCB",
        }
        return L0MicroVerdict(
            status=SEALED,
            nonce=nonce,
            reason="supervisor_sealed",
            floor_digest=child_verdict.floor_digest,
            response=response,
        )
    except Exception as exc:
        return _reject(nonce, f"parent_exception:{type(exc).__name__}:{exc}")''',
)
_PR2_L0_TCB_FUNCTION_SOURCE_SHA256 = {
    "L0MicroVerdict": "8db2ad64d98d763800b5c86235b129bf636b798483150eedfbdd27a34f43fc07",
    "L0SupervisorSealRequest": "73fe4c7cf6a53bc9034584cd0fe2eb8afb47ddc9ac535f0fb01bc2d39cc10233",
    "_atomic_json_bytes": "54dcce4647f5a113e3eaf0b8403bcac4901f22629ed7e7b48dc57ba61c3a15da",
    "_atomic_replace_bytes": "56db2e99dd91259add629655664eda9dee64ab97dacd322a1f5f7a1b43edf8e7",
    "_canonical_bytes": "b4db84319aa7517fc03f6ee151f703ab0ea45d3ed309c5780659728478d5672a",
    "_canonical_digest": "8c05dd916c7f2615e0bb2fbb4ed5a6cac62cce500f7fee05ccc89e91869659aa",
    "_certified_state_payload_sha256_l0": "252327a9f21bcec55299fca6c83c9dce4ffa43118054b4348aa96781faa6bd13",
    "_checkpoint_write_lock_l0": "00dfd3beffaf69900295f94434cd48ec752d7bf9a1422c263d40fceb63e9e4ca",
    "_child_env": "950e48d22bee9d0f0048eb2bb0f4e12b22fd157b7a69d4eeb2b32e3ec7628300",
    "_dependency_file_top_level": "bbd81b3a8476689a5f8835820952e3131f51a584e54954dd751fb3544ed33c4c",
    "_dependency_floor_root": "0768d2a1aea729323527c198a067431e011fc9bf3f7074e139c5dbaa189a82af",
    "_dependency_named_tcb_violation": "24bf66ab8b3f2fcc7d000e7149dd15958cc8baab25b21f53300a7b6ea30bff94",
    "_discover_project_snapshot_modules": "9da720e1f3da63efc98fb2e1730c4b267ab979e62d739c8411dd0eb4765daf8f",
    "_domain_response_violation": "a58fcb21065c7aab4b4a0b0a4779cb2c93e397aaef6e031cd98b37b594d4eedb",
    "_floor_digest": "f99a8a573213baec45deba01692d5f12d07ff150f85a886c484dce260187b4fb",
    "_is_lower_sha256": "ded6acd02fdcc155cfcb652ccc14fb3dc525c114ab607bc2d60093277628f427",
    "_json_bytes": "96dd857ef05e7b95c1ec5d347e52354f10cfe6d1b280e4136ce23d24253a90dc",
    "_load_canonical_dependency_floor_manifest": "b1644ba2f13dfbcdbdb93f96882352f9d7351ae952525cec0b2afa6a402559e9",
    "_load_dependency_floor_manifest": "4546cb698a974577201947e4381667e6daed7b5fae8c82281ca420f79d327989",
    "_load_dependency_floor_manifest_bytes": "879027a5f0c60d085e27d9e187db55172691d775b50f86bc2808e8c619fc3f51",
    "_load_sealed_proposal_authority_l0": "1ee82b52cb023ecc2cb59362586bf9fefb034a157d33774fb053c68d28127c8d",
    "_materialize_snapshot": "dd3ba44abe31e066568334347a1bc7f8d91d8f9915db35343917c14b23425b90",
    "_materialize_snapshot_import_defaults": "315bafa58d6f1219f0dc3b788a40c1d940e1e54df0995f2d79c4f703baf21d93",
    "_module_relpath": "cf023dc99a8b7f998fe0c5f0949bbda89a113277c560b48588ecfd9266341d71",
    "_now_iso": "1111d4064b0970758ae53c6402d741da67c3968a43a83d1d7ec022574778cd3f",
    "_parse_json_float": "48e5eef600d6fbcc4a290e129dd2338edbf0ef2fc0b4849633efb03177520577",
    "_parse_mapping": "00326c1b9e1ae90d2736d3fcdf14d84d4a31a78c58a4bfd5a950c820805e648d",
    "_path_has_symlink_component": "904c9a3c93f5399c88a146b5a4933f846c5479b293fd1a1463d5b9de11558395",
    "_postwrite_state_violation": "706e8157cff76d6915996fd1c58e9224b2fff48e675ee3049dc27ef5d257cba5",
    "_proposal_authority_violation": "153a95947beeab0713a4703754747249b9f0088fd02503550bd394aa54fbcf18",
    "_proposal_ready_marker_violation": "9b3349e6e7393df874409c18e0e1497ad9b84d4f9e5215eb6d30184009ef08e9",
    "_proposal_state_violation": "182fadf09080c98f75a2fce98cb96ac0ef91dbc7414c5a29d9340151c6b026a8",
    "_read_regular_file_bytes": "41f6be53a4ed2c7e38da0f1a17fb87e4d6f9f2bf3a38beb36506e981e97fd8c0",
    "_reject": "18af5ccc78c6e86b76065ea7217c9043317ee91537b30babac1539b334cbe819",
    "_reject_duplicate_json_keys": "ea9b0f61afffe3586249499d690cc671b9b2ec47e1178850b35e16c7a6fe00df",
    "_reject_json_constant": "0bcffd83f5daf49c5cb1fbfaa2340ed3a881a3b5600abcf00a78e4cd579ad6bc",
    "_require_mapping": "0afb06873b1d9d8050a1aadc83cbee73929b76a7cb4fb8230cb278243817ee25",
    "_response_violation": "b4c4f6be6aa42b9321c62b4d0b7b55969059136db5ae58f44eb00326f446db6f",
    "_safe_manifest_relpath": "3e27b6df0c2d8603f155cf42404e40a864fcf6f48cdcb31d47fe9675656a554f",
    "_snapshot_module_paths": "a85df1ab9b53818f544faea01f2dd2c5039d4be4503ba976d020036e731854e7",
    "_source_digest_relpaths": "52fc1d20e3f3d7654dac024e47d9e1b32a1b486dc9fca9eee48ae773bc7c0ab4",
    "_stable_fixed_witness_candidate_records_l0": "c8b9445d129191dfb1d91378798f6204586766abfffc7359dc76abb81b038904",
    "_stable_fixed_witness_payload_l0": "03fc2efe2dfa60449761b82eab9d26114e0bb6be7bef180cc2522eba2854524f",
    "_strict_int": "5b876ae9cebb315f00b2cd92e2f2b8126b381caf271da26405a65301ac83ff69",
    "_strict_timestamp": "be3b3c947b04b3ec3834af77be85af32df891cbeba177db6c7de5ffe36c94884",
    "_strong_proof_binding_violation": "8ad77b3035b07a73abb82b9d5554de89fd5c2415608be0b6db0e4b9aa29021df",
    "_strong_status_keys": "6efd4d21cd333c8a1c023b3d87bb31a422b0276195b67e11e2b7c265a14281d4",
    "_supervisor_certified_transition_violation_l0": "d2d605b01c6b1d01984a76dda4f256beb74294d11c5d6acf26b91fab9925f707",
    "_supervisor_seal_state_violation_l0": "7dd6b76be7f589058f756182d91c887579a05b82ff9bd69bc761474a44d6f3a0",
    "_valid_campaign_instance_id": "b939b1b49efc6f90fbe8eb984c193c1061d9a494ec530d8b7a128c28d28afb45",
    "_valid_dependency_top_level": "3d9ad01addc9677349af2ff66f389d63d691ce231cb692f6eb38bcfcf40846b3",
    "_valid_supervisor_proposal_run_id": "ce24774a70a38c89d40d511b76f759d6ddc48a291cf01c4f5c9740c5261216e5",
    "_verdict_from_completed_process": "9b1659bb1f09b4d6d06a7f8513505eed531ba966c068410af749e041fe70471b",
    "loads_l0_strict_json": "ee77ffbacc5b38c4f26780e22689574d289bf249ded9cde3f66fe0173a95ccaf",
    "run_l0_micro_verifier_round_trip": "6b8678f0ace83b10f99516ed8c921b82799175b5bcf112495780bb6be95f9e8b",
    "run_l0_supervisor_seal": "b2925b27116dcdd705bdeaf23a238a155b9a0a88b4b949b3d0a8ce2ad643b5b7",
}
_PR2_TRUE_CHILD_TCB_FUNCTION_SOURCE_SHA256 = {
    "_RehashingExtensionFileLoader": "57416b8287ed64774f1676a6040b8d164a556d0599c0c0994eb639e4e54c53b9",
    "_RehashingExtensionFileLoader.__init__": "464b196bcf03717f7f5d1cc00c59bb21fbe8d7bf2ceaeab7f53fa17389c4be09",
    "_RehashingExtensionFileLoader.create_module": "156de74675fcfa072e24c5df8dcda4b3b2a3958e7509e530100ac84391a821fa",
    "_RehashingSourceFileLoader": "37990b1f8ef407c517ecbb4e57514649559f503869840d82cfe5c4deb3d00963",
    "_RehashingSourceFileLoader.__init__": "464b196bcf03717f7f5d1cc00c59bb21fbe8d7bf2ceaeab7f53fa17389c4be09",
    "_RehashingSourceFileLoader.get_code": "6c43c00a120c26577894700ddafdb1df367e64f1e1583b3f6c4cf76f37a49d3f",
    "_RehashingSourceFileLoader.get_data": "cacaea6382dec4e4100ddc64e90732ea49bec07c3a275917c5c502d5dc2b33df",
    "_RestrictedThirdPartyFinder": "605f0eeace8b8857d676d861f6189d95c8002930965ffff13ab0a0d7718eb8f1",
    "_RestrictedThirdPartyFinder.__init__": "58a5a98c38718362c22291b3b2e624d06ff3476fe4460c456f9cbd80a7c60bbc",
    "_RestrictedThirdPartyFinder.find_spec": "22488735a19c094196c7ca529b72b9d94f5b2aa7cd2d654acc7b7372a2914941",
    "_StdlibOnlyPathFinder": "7a672d9c93e0066dcef626423c130d6823648792a4145ee77e03928e42e31aab",
    "_StdlibOnlyPathFinder.__init__": "1e1b9bb79d7ee0583b9c1be0fddf9839eb8d011fbf0f61c97a159262ef8a1c7c",
    "_StdlibOnlyPathFinder.find_spec": "fa8e1f1460ef2f644901aa44282b13ea73dfd6bc92d10d7bd5d228bb0a78dde3",
    "_canonical_bytes": "6fd507d684d9171dad64369d2b4b0584edf256520be3e1113d37db0de3c44471",
    "_canonical_digest": "8c05dd916c7f2615e0bb2fbb4ed5a6cac62cce500f7fee05ccc89e91869659aa",
    "_dependency_file_top_level": "dd225ab13ec9917236f9cebeafa5d47b7e732d52ef8bb96c5b1891facd6dc2e1",
    "_dependency_floor_root": "052fba15f27936a0a16a8979bff7db04ec1f6b0312ae218087b57c20e3d2d5a1",
    "_dependency_named_tcb_violation": "a83946abe627f35c319f70e7ea27917808930a2b243da7ecb794d8fa01fdd773",
    "_index_dependency_package_dirs": "90350bc225dd904c07b72ba646737d762d6ff83e2fb39b9586192837c3881b14",
    "_install_third_party_floor": "3ae425a7f3357ac1be6d3dbaf1a7bb073c37361c720b037a203ca71ee57155f8",
    "_is_lower_sha256": "ded6acd02fdcc155cfcb652ccc14fb3dc525c114ab607bc2d60093277628f427",
    "_is_within": "232ae2feae6f6bf8dfc2909bbc5fb6acae40ca3fd02c153fad3706d1886bed4a",
    "_is_within_any": "79abd86e1e8a39d021a225212b009b307adb74928e192652e20e6b1545dc63de",
    "_json_copy": "71d6048581ec811d9d28f4c60b69287aaa2fee791246e8e50850e9db54380f8e",
    "_materialize_import_default_artifacts": "ec2a13d3338721ffd5819e6d0098685f51a81f5b1c00da39cde1c368f19f09e5",
    "_project_candidate_records_direct": "dbffd63bdb911b624dabd127ef7a45a3a8aabcf17b7d82000433e8e042f1753e",
    "_require_mapping": "104f33d630f36f0f78076bf3c859fc86367f92237002231fd653d943699bdd44",
    "_run_fixed_witness_direct": "eb9c35e49ec0d7a2c35d9caf688042b84c7641fe4a623b95680252f9d9c22af7",
    "_safe_rel": "510d425350d3e866ea0523fbfce04af46793936ff22503f4e2390d0782e7c957",
    "_stable_fixed_witness_candidate_records": "1e1a8147e512e9d3c200be076bd6fb3178090d3be21e7a98a627cade94b5ac11",
    "_stable_fixed_witness_payload": "698f25a09ab52aed1857169733588790c3db9eb1f73bddadf571e3b657729af3",
    "_stdlib_paths": "0624a2443f48c0ae315746bd6e5ef6d9af30f8fece3cc5da141c0d8f7d201ce9",
    "_strict_int": "5b876ae9cebb315f00b2cd92e2f2b8126b381caf271da26405a65301ac83ff69",
    "_strict_string": "0eb6e1751b768a278a8056f2327d16fae030eb5c2fb5bfdec3bb6b8eaafaa103",
    "_string_list": "3e11de384e5809b24713779aae4ce234ba8278b3831ef2ea567333bfc0a5c00a",
    "_valid_top_level_name": "1d0d7e89abcb04884eb05becb12fbf4f75f48d14eb296ebd1feec8f7f73e2ba7",
    "_verify_supervisor_domain": "0b5fa0b48282dd4eca526cf4682fd2380758d6a7bbc75a0c08cb260077c3e81f",
    "verify": "1bcf13acf3e89d51a1cb4707ad8927e9218ba09b7875857d3ca60c75c6738b76",
}
_PR2_L0_TCB_CONSTANT_SOURCES = {
    'AUTHORITY': 'AUTHORITY = "pr2_l0_micro_verifier_v1"',
    'CAMPAIGN_INSTANCE_ID_KEY': 'CAMPAIGN_INSTANCE_ID_KEY = "campaign_instance_id"',
    'CANDIDATE_PROPOSED_STATUS': 'CANDIDATE_PROPOSED_STATUS = "CANDIDATE_PROPOSED"',
    'CHILD_STAGE_TRACE': 'CHILD_STAGE_TRACE = (\n    "floor_verified",\n    "loader_installed",\n    "verifier_imported",\n    "verifier_ran",\n)',
    'DEFAULT_VERIFIER_FUNCTION': 'DEFAULT_VERIFIER_FUNCTION = "verify"',
    'DEFAULT_VERIFIER_MODULE': 'DEFAULT_VERIFIER_MODULE = "src.search.pr2_l0_trivial_child"',
    'DEPENDENCY_FLOOR_MANIFEST_REL': 'DEPENDENCY_FLOOR_MANIFEST_REL = "data/proof_obligations/pr2_dependency_floor_manifest.json"',
    'DEPENDENCY_FLOOR_MANIFEST_SHA256': 'DEPENDENCY_FLOOR_MANIFEST_SHA256 = "a0fe4bdc520cf8aa4b142eb23cf5dc1933c061d973df0be9f3fe1cca1adc2a74"',
    'DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES': 'DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES = 567602',
    'DEPENDENCY_FLOOR_ROOT_SENTINEL': 'DEPENDENCY_FLOOR_ROOT_SENTINEL = "PYTHON_SYSCONFIG_PURELIB"',
    'PROPOSAL_READY_MARKER_AUTHORITY': 'PROPOSAL_READY_MARKER_AUTHORITY = "certified_exact_producer_proposal_ready_v1"',
    'PROPOSAL_READY_MARKER_SCHEMA_VERSION': 'PROPOSAL_READY_MARKER_SCHEMA_VERSION = 2',
    'PROPOSAL_RUN_ID_ALLOWED_CHARS': 'PROPOSAL_RUN_ID_ALLOWED_CHARS = frozenset(\n    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"\n)',
    'REJECTED': 'REJECTED = "REJECTED"',
    'SCHEMA_VERSION': 'SCHEMA_VERSION = 1',
    'SEALED': 'SEALED = "SEALED"',
    'STRONG_STATUSES': 'STRONG_STATUSES = frozenset({"CERTIFIED", "INFEASIBLE"})',
    'SUPERVISOR_DOMAIN_AUTHORITY': 'SUPERVISOR_DOMAIN_AUTHORITY = "pr2_l0_true_supervisor_domain_v1"',
    'SUPERVISOR_DOMAIN_SCHEMA_VERSION': 'SUPERVISOR_DOMAIN_SCHEMA_VERSION = 1',
    'SUPERVISOR_PROPOSAL_STATE_KEY': 'SUPERVISOR_PROPOSAL_STATE_KEY = "supervisor_proposal"',
    'SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION': 'SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION = 2',
    'SUPERVISOR_SEAL_AUTHORITY': 'SUPERVISOR_SEAL_AUTHORITY = "certified_exact_supervisor_seal_v1"',
    'SUPERVISOR_SEAL_SCHEMA_VERSION': 'SUPERVISOR_SEAL_SCHEMA_VERSION = 2',
    'SUPERVISOR_SEAL_STATE_KEY': 'SUPERVISOR_SEAL_STATE_KEY = "supervisor_seal"',
    'TERMINAL_CERTIFIED_REASON': 'TERMINAL_CERTIFIED_REASON = "search_exhausted_all_candidates"',
    'TRUE_VERIFIER_MODULE': 'TRUE_VERIFIER_MODULE = "src.search.pr2_l0_true_verifier_child"',
    '_FIXED_WITNESS_AUDIT_FIELD': '_FIXED_WITNESS_AUDIT_FIELD = "terminal_fixed_witness_verifier"',
    '_FIXED_WITNESS_STABLE_FIELDS': '_FIXED_WITNESS_STABLE_FIELDS = frozenset(_FIXED_WITNESS_STABLE_FIELD_ORDER)',
    '_FIXED_WITNESS_STABLE_FIELD_ORDER': '_FIXED_WITNESS_STABLE_FIELD_ORDER = (\n    "schema_version",\n    "authority",\n    "publishable",\n    "projected_status",\n    "candidate_key",\n    "solution_digest",\n    "ghost_rect_digest",\n    "ghost_cells_digest",\n    "witness_input_digest",\n    "binding_assignment_digest",\n    "port_specs_digest",\n    "routing_occupancy_digest",\n    "binding_status",\n    "routing_status",\n    "reason",\n    "details",\n)',
    '_FIXED_WITNESS_VOLATILE_FIELDS': '_FIXED_WITNESS_VOLATILE_FIELDS = frozenset({"fresh_run_token"})',
}
_PR2_L0_CHILD_BOOTSTRAP_SOURCE_VALUE_SHA256 = (
    "1141436f87f6573c4fb19f58d60dd063e1f33b34b2f768e42c76908550004d8d"
)
_PR2_L0_FORBIDDEN_TOP_LEVEL_SHADOW_NAMES = frozenset(
    {
        "dict",
        "tuple",
        "json",
        "hashlib",
        "base64",
        "os",
        "secrets",
        "shutil",
        "subprocess",
        "sys",
        "sysconfig",
        "tempfile",
        "time",
        "uuid",
        "Any",
        "Mapping",
        "Path",
        "Sequence",
    }
)
_PR2_L0_ALLOWED_IMPORT_BINDINGS = {
    "base64": ("import", "base64", None),
    "hashlib": ("import", "hashlib", None),
    "json": ("import", "json", None),
    "os": ("import", "os", None),
    "secrets": ("import", "secrets", None),
    "shutil": ("import", "shutil", None),
    "subprocess": ("import", "subprocess", None),
    "sys": ("import", "sys", None),
    "sysconfig": ("import", "sysconfig", None),
    "tempfile": ("import", "tempfile", None),
    "time": ("import", "time", None),
    "uuid": ("import", "uuid", None),
    "Path": ("from", "pathlib", "Path"),
    "Any": ("from", "typing", "Any"),
    "Mapping": ("from", "typing", "Mapping"),
    "Sequence": ("from", "typing", "Sequence"),
}
_PR2_EXACT_TCB_SOURCE_SHA256 = {
    "ExactCampaign": "70a32c787de0abe4e4dc9407dc747c72ecbd460bd073ac1f6c532a5199c309ce",
    "ExactCampaign._assert_proposal_marker_still_current": "3d10cf234a0735c502b15e33ec9689ff00c3a1fb2bf78d3174ef5d6bc83d64b5",
    "ExactCampaign._clear_proposal_ready_marker_if_unchanged": "daf25bf754ab1c9d19103437f42dd2af40851eba46fe626c20d1a313a15199ec",
    "ExactCampaign._load_supervisor_proposal_authority": "a7cdd131ef01765990b206d71f8cbdb9d4b55ac7f906cc17c402af048cfabc5f",
    "ExactCampaign._mark_candidate_result_from_verified_producer": "a33d7803375d438f99e04b5cfb640f671dd7219afdd7af8c185f40b1cdfb5911",
    "ExactCampaign._validate_supervisor_certified_state_before_commit": "4e413c5a849ffacbd97342f918142dd042fe5d63dc592e4356a2bc7bab278d92",
    "ExactCampaign.artifact_hashes": "dd2f3a8c73fcf68a673db67dd9275e151118c8ac8d3fd7e88c5d69566463b253",
    "ExactCampaign.best_certified_result": "b1a29ea660eb727fae3dfadf3d6931e6181675c3fd829c0b00c77584b6fe7553",
    "ExactCampaign.campaign_hours": "368292448266b53a3ae0771da0de390858b4818ce05130039cbac1718c51c884",
    "ExactCampaign.clear_proposal_ready_marker": "93df4638ea2abb25c24c7ee87f015aa9e27d9b80adcff9d5dc1c3c9f941219a0",
    "ExactCampaign.elapsed_seconds": "0a10b3c4cb40687ff1ec2a6e3e12e725c80d7f4c18add315c59d5b41e9240910",
    "ExactCampaign.get_audit_log": "bdd4f0634775ba836bc1417422c21be2a9a7d31ca2892eef446c0ff5443b1a3e",
    "ExactCampaign.get_candidate_bound_state": "f69b67167ab0811f6da96361adbdfbece051bd20021721390a2486700c873522",
    "ExactCampaign.get_candidate_cuts": "20930219a5451ebcf1d240aedeb91bc85b05f1a4b6238ae54da3bbe29f41320a",
    "ExactCampaign.get_candidate_record": "4bb677bd720f5d694f4800dcad3c633d0327a974ce8eda88491d0a870bfa78a7",
    "ExactCampaign.is_compatible_with_current_hashes": "b77688d529b9247cbc4b8489bc7d88907fdaaa810bcac7316c8378c57e82a558",
    "ExactCampaign.load_or_create": "420bc70a229049048b39edf56d6e6b87b0d00cdaa0212fe476c678c520d57a4c",
    "ExactCampaign.mark_campaign_stopped": "cac850cbadee274259ba9c22fbf004f0a97403d809e98501ad21bf833adbe35a",
    "ExactCampaign.mark_candidate_result": "5a3349e5e0fc118d776f7314cc79ce1b79dfcd9461c1c3977ed02e5af11bcb2d",
    "ExactCampaign.mark_candidate_started": "00a7cb22fd3cd235908867ddad425eaffec0a5b7036f13f38891d394be6b52e2",
    "ExactCampaign.proposal_ready_marker_path": "e1dee6c63023b1da53f9b42f8bb41e50aa0df7562a2b5393690249396dbed493",
    "ExactCampaign.remaining_seconds": "ed261f09594be2adc28ad89b850e457746943d3a0da7dd0c933cca131f242e23",
    "ExactCampaign.reset_reason": "8f3035d6e3baec97186b894294571ac9a65515aef183f83c4fd4e19a4f1bb223",
    "ExactCampaign.save": "d069c600b6040fbccc86b1a479d8c3439ffdd9e9be2fe0c99e863d247b0d5d64",
    "ExactCampaign.set_supervisor_proposal_run_id": "231dbd964485c78a2b0a74816b2feefbbc288872b1079fd13b48edf7fe58103e",
    "ExactCampaign.supervisor_seal": "70ccaa80366b5873bd14b65e75c10e7b6b33fe2170d82a8a2eea9d0058115c43",
    "ExactCampaign.update_candidate_bound_state": "3c680cd8d1b0d4756323452b9e51d2e4c5bc29b22ab3914caef8b178ba9c0c87",
    "ExactCampaign.update_candidate_running_proof_summary": "29826a12e6437ea39118fe49e879a65e38a3ad2e7248f48e4426158265412088",
    "ExactCampaign.write_proposal_ready_marker": "69777257042617c56acd6732dbcd036ac3b9292a15ff845fbe6d3a1785f40baf",
    "_atomic_json_bytes": "7c4cc9d1e8b3fd7dead4c4a4d9fcbf85416da657e5cbb674d6df042673dae373",
    "_atomic_write_json_bytes": "e1a6360777b8336cd6905e9fbe4f9be475353843e27cec43cd5384773a56954c",
    "_best_empty_rect_objective": "98dac9bae0a315fca2025ac8b6ce5c4b4c8e03b149369dc234498c87e4b29710",
    "_bound_state_defaults": "bd3ec491b202c1f744ac18d786b3ee9a24b84c10d70ca2d6847bf2a5b0b0a7ec",
    "_build_initial_state": "78e5c072217c66e27d585a85112f1c9bc40e534a181a96c5bc7c87d2ee9135fb",
    "_build_occupancy_prefix": "73f55efe3e23d8b6b3cdfab5d48af68c43cff66af393a46634ff4502ab66486f",
    "_candidate_defaults": "47a4506ceb4ceec718f33ef185b196da3cb6df2ab2b429b1bbe95dcf3898f1d4",
    "_candidate_objective_from_rect": "09268e0e9ac5cb0e8e56601b0e9a82f3fe78fbe665a8641acfeb11f720f579a0",
    "_candidate_proposed_resume_authority_violation": "75d4f8934e2d37cfcc6a46207f272befc0f0fe860499ac79d56b9ea19f898e4a",
    "_canonical_digest": "0aab947c8f0c14f1dfa2a14984c1d2a99ce862bb70908aaa8381d982bb31ff99",
    "_certified_state_payload_sha256": "e25fe7fea36684825230a67189bf82bf573f1828610877b6ce1bc365df91aada",
    "_checkpoint_write_lock": "1e60c3cd076def414ccfd006c0af03ca6127df19bd2ddd1bf9ae94f3bc7d884c",
    "_clear_certified_delivery_surface_artifacts_for_campaign_resume": "268378d78c281929b8075c7bbd65c91e35fd8d277dddc77c285815d333cd5e43",
    "_default_master_domain_contract": "f30cf366d102149c0ace83d39b035364bb17e2afc850bfc42f4fb50b97f83f8c",
    "_demote_candidate_proposed_resume_state": "693000e2e616227633fed718951c2123f2d12ca9b7d4482331c4a75caa050a1f",
    "_discover_certified_exact_source_hash_files": "d8031fd906a3631d6ce61c7b7deb68deb96114d55262805ee5969966e64600d5",
    "_empty_rect_exists": "1b32cef7e198f26e597525a8d33148834b045140e267d2f1fdf055cf63ec7414",
    "_expected_unfiltered_ghost_anchor_index": "b2407c6047a7231264c7502a15f877626f0c75a52a1a6843cc77ac81b974f267",
    "_final_result_certified_transition": "ff40cc5bbd0f0fecd3e430a9311e23f67e709aa63f5c5bdcbe044f026c68d822",
    "_final_result_objective": "2845a0f3d07c15873847c13855cc5eada34be108344e504342da92de9dfe23b5",
    "_fsync_directory": "bfb18d668c53c59dc521f4564192e0ae9cb9c5077fe423856c5f8b7ba8e3d53b",
    "_has_certified_final_result": "b7d65d0868c2cd5ed14f9780766a643dda2b65f891270bd5fb69813b41c65c76",
    "_has_unsupervised_certified_checkpoint_claim": "9c99d69c30dc7642b8631f758e99b9f960b1d7cba2296c8870cac6fd552f74b8",
    "_is_authorized_exact_pose_optional_solution_entry": "8ad2a938faebe2e55a33ef1d30fa9c08eb3540845a93e263e54470c7bd5c2294",
    "_is_lower_sha256": "ded6acd02fdcc155cfcb652ccc14fb3dc525c114ab607bc2d60093277628f427",
    "_load_exact_facility_pools": "7eb8132e1fbd338aa79c7cd004232b9bc6241053314013500733822bae84e787",
    "_load_exact_facility_templates": "f29a5f71fa0d356a3cb7c23225f95b4a1758ebb4b32271d99664cb7c134fa324",
    "_load_exact_grid_dimensions": "f77537e75b23073d519685c4c9b99dd1c97ef132fb53ad369e74ac93b7091040",
    "_load_exact_min_side_admissibility": "38dee46b35c6df48b719e2dec75b80a22045e4be569027c498eb292a86cf691a",
    "_load_exact_required_optional_lower_bounds": "e7c83418c0239701a95cec5c6383b53a5c3bb2c7aeb533ce3c824611dc011a0d",
    "_load_exact_safe_area_upper_bound": "623b44e02e3a6677252c2f6dda02ddc8d79591c5db1b865d7019814e75da6e18",
    "_load_sealed_proposal_authority": "08a3e24dd6bcec9550a9399bed7514bb1056352cdf8b424d6bce23485aaefa3e",
    "_load_validated_mandatory_exact_instances": "0f58fdfde46f04ee235f3c42ece7658cb891339828bd86db3f4c7271932d994f",
    "_loads_strict_json_object": "c986086daa844b67ccac811515930976a5b52848bde6252b37adb7ff8304f621",
    "_mandatory_solution_entry_metadata_violation": "d9d5d8ee29d9b5bc6afd63a7881564c3405a3b6a5ed4d344d6f961e6986da460",
    "_nonnegative_number": "f89fde36e653b09ea5a935ab408cd8d94a20af1e896a1661cf9a8c35d7aa5d6c",
    "_occupied_count_in_rect": "0326d0e818f9ddc0369ef10e2ee4ddcc922a02b69e98620bacf2c55a082e85c5",
    "_path_has_symlink_component": "e64dd1865d28060ea064597d28385a7081d7a1446cb899fc46ddd5ada8209ba5",
    "_pose_occupied_cells": "dae7a4b135cc7dcaaf886613de9186aaf8aa76c965cbcf10c1c4d9dd3ab1e9d2",
    "_pose_optional_solution_entry_metadata_violation": "6093cf2390189718f9f7e460fd29c58f105f77ec2da0580f17e17072f8211d31",
    "_pose_pool_min_occupied_cell_count": "17ebcc6a49bd34b5a8d625dcdd375106564e51346fd37e3b845e72df2f93e23d",
    "_pose_power_coverage_cells": "d4461a00badd7f04046d52abd3b5a2ce9ff216bf17b9af9b131b3664e2b6f4e3",
    "_proposal_state_violation": "c1e384770d1d6a70a22e731fd34b2aaf719628a52a592e3efeb409c1f0870444",
    "_read_once_regular_file_bytes": "2ae95096da7aa78ef91c192faf54273b16fbce11eb1448752c251d8ba3438a93",
    "_reject_duplicate_json_keys": "7c89f3fa862a6bd7d108b3551d66005f35b3edec787420bc0bf88ffb0878ffae",
    "_reject_json_constant": "0bcffd83f5daf49c5cb1fbfaa2340ed3a881a3b5600abcf00a78e4cd579ad6bc",
    "_resume_strong_status_replay_reason": "e2a3d82029493c9353f2c350de156771d47d019c039912f7b848d10f50890ec4",
    "_resume_verified_sealed_terminal_state_violation": "0330dff3c3163277e4b58bdd20f709d9e6fb422fe7e9ebce1e349e858445d29b",
    "_sanitize_resume_state_for_untrusted_candidate_evidence": "da1b61124fc0027858314db1e0a195ac92b9d21d752c168fe1fa1c8d884df175",
    "_sha256_file": "e538cec01ddc50ee5df522ded653bddc214414e3f0a76fb1dcf11d5c45e0c0ad",
    "_snapshot_campaign_state_for_nonterminal_save": "538b0095d5cac74d1d0651920d0ff7e2451ad43ba0286279df191897fa45ebd1",
    "_solution_without_ghost_marker": "87e3799b244288813e8fa9da4424eb09b8182590ea48983aafb72ea59ac0a6dc",
    "_stable_fixed_witness_candidate_records_for_supervisor_compare": "5df4e1e9b6e4911fcb0d5118892fe3c41e5fb19af6d71e0e3ff02bbeb00fdbd1",
    "_strict_candidate_ghost_rect": "0c8256117ff19bed0aa4427e56ec9118cc6e7f7756be51eebf9c3b90d5cf83d3",
    "_strict_nonempty_string": "a24b61737df419582bfd4a5a4fcdf445ee6944658241c71eef26e6c7214f287f",
    "_strict_proposal_exit_code": "e7aa604764c32db5a013a39c08610c4efa10721ad96064f8301bfe34311a75e7",
    "_strict_resume_int": "e6cb161b475997b1411c4897b2dbddb816454d53be8ed695d20e21c9c6464de4",
    "_strict_resume_nonnegative_float": "19531f29f12322c372c0ea452a206575dd9d65b0bd0d321b90b05568b4619393",
    "_strict_resume_timestamp": "3dd5743ae9088d952697f73a92b624df4e85a089266f4ac1e764d7a73bf92a89",
    "_supervisor_certified_transition_violation": "81684bb69595c118d69434ca150b122d3eb435d7a1e081cd9527e9757f19a119",
    "_supervisor_seal_state_violation": "e2ee931494ed8db0c74ab0e417977127342a70c400906fde91d8615efc4f4963",
    "_terminal_candidate_ghost_pick_binding_violation": "c1ed1b701f052e76a8189bc40a0256d280a7553a21868f94261fae1bb322eb4d",
    "_terminal_certified_final_result_violation_for_project_authority": "69f9ccf931a47242b460814420ef82a04aacbc4a96feb517cfd06cbe658fe7a5",
    "_terminal_certified_ghost_rect_unknown_field": "6ee40c61dcfea24aa601a8e8dead3497f2b7ee4c10ce5e7636d24747c5e3443e",
    "_terminal_certified_last_stop_reason_violation": "63ff8409d8d7c3155d5a75023bab72e035b0e634906781f31edeed74e5e05297",
    "_terminal_certified_proof_surface_digest": "da2b4eaf711a4a98b94c5f1fcc0fd471cce549b06bcfa119ea4d55a5435d63b0",
    "_terminal_certified_search_stats_violation": "d056a83ca959d6cd3c0a9a9b0691bde628ca7159833d85e41187fd8f30052d07",
    "_terminal_certified_solution_entry_unknown_field": "bbc3e49b39b1d01228caaca871a4b04297dd2261ba0204ae50714a1ec27d073a",
    "_terminal_solution_entry_pose_metadata_violation": "fdaa0d82562ac9b2f1c8d72521e9e8704f941c51993b278b40e8e7e5e72fae85",
    "_valid_campaign_instance_id": "b939b1b49efc6f90fbe8eb984c193c1061d9a494ec530d8b7a128c28d28afb45",
    "_valid_supervisor_proposal_run_id": "bf9a4f80248d5d305803d5e7a7a9fd3c3b46a4db267d85c32cd5bfd4e1a8932c",
    "_validate_candidate_record": "76856438a45a59056397a40aec57747082a4f7df0bebdd91a4bc69feacfdd695",
    "_validate_cut_condition_domain": "f466a64322426b03193d7a7570e3dbaa87be0d6610578990628b2b7c1c31bce0",
    "_validate_master_domain_contract": "468d176a99e86bb85e418c3efc9db7313e406cb77e424be45ac52ed8f0e7baff",
    "_validate_resume_state": "28f61c420fe62c38f5f3a78f2f25eb6ab32117b2eb40f337c161261f66ace8b9",
    "_validate_terminal_solution_against_project": "4f3a169921674bded70e1c2d6fd405de1b4dc0088bad2be2aa692eb17df03f85",
    "_validated_mandatory_exact_instances_payload": "b307dd5161420576911d556b064c97d7957e36f0d5c7f760d4d8fbe71c3fe276",
    "atomic_write_json": "557fc8ea38e175d35898f7028cc97849e8deafe8e27287486580c59126582bd0",
    "candidate_key": "0a3b51c9d97a58f62dc099850c417c5927b3cf397458836997abd0ebfbd4b1be",
    "canonical_candidate_geometry_rederivation_violation": "978f918a852e80a108cdda7912ba2e1495ac76ae61430c227090104db49acf28",
    "certified_terminal_evidence_violation": "04acdf7b4a65cc32014e8a5ef8c916a88204f52b5e477dd487bf573701cc81bf",
    "compute_certified_exact_source_digest": "b255a4ed3c05bbde4fe4a1db1968c06aba7dacaf46af361b67e89c86b949c2c9",
    "compute_exact_artifact_hashes": "db24b961f4836f373d9078117936ed34760dfecc7b9fb888dd64a62f6e8be130",
    "has_certified_export_surface": "ba6b6a213989dae97084033ab96ea9cf4bee3dfe26b69ca340237a06a06f46ef",
    "has_terminal_full_frontier_certified_evidence": "67902c4f61e15b168b57f5de9b5cd95773d6342cb922c5f16ce53859777066a9",
    "has_valid_terminal_full_frontier_certified_evidence": "ddf26ea3d76344e37d23e351db1660c3d871e3e277a93d69ef23bcbd52d76610",
    "has_valid_terminal_full_frontier_certified_evidence_for_project": "1f41f3ae51a01eb71c769626841ea0d9328f60d55a4505effddb4de342678c09",
    "iso_to_ts": "c1ccebe9c5359007f522272bdde840db603325ae93390fbe4dbcd0e2dae555a7",
    "load_proposal_ready_marker": "4f83a0d773b64f3f231123cb195d16e20777ba08c063fec50ff8e42617f18e07",
    "new_campaign_instance_id": "c306f8a70bc709506635c125523ab58da2dee42df58f3fe69cb1163481cef506",
    "new_supervisor_proposal_run_id": "487bb1e82ac0a1655a0c5067bb5d267e82d9ab56b3dcf71cd7e64f8db9841523",
    "now_iso": "f719c310ad532c6a7759c6d6c8289ab87a488cc6e822a24082922470c4fac06f",
    "now_ts": "e64abec07a9c497e814226bd83c696ec2da6b6fd27935d494bfea28d4238b3ed",
    "proposal_ready_marker_path_for_campaign": "504243efdfb35b3348a334dcd47c3d0fdbd8250ede3e92e2e813c0202fad6ce8",
    "proposal_ready_marker_violation": "454f97a4438b94386215edf20055bbcc9eec8e6ba3f40ef054e095325010dee4",
    "read_once_exact_artifact_snapshot": "3bba071e4728f2909651f4aedd0472c7ee3837dda07f4235b606a294d0a81f1b",
    "sha256_file": "85a7a51ff9fe1c3ab43bf2d96c17441558e8b8badd42da90dd4bbffaa429c6ef",
    "terminal_certified_final_result_project_precheck_violation": "77c23099c757be50960e7b434ba7ccaded34721976a3752868edb66fe7fd5461",
    "terminal_certified_final_result_violation": "541538711a5376519cc8c18b6b60b7dece66630628ad0d4ae47044457685b0ae",
    "terminal_certified_final_result_violation_for_project": "b8a7cdc965e54ef8dcd2a7204de0539c566118e9bce63bbe9ead75b3824f9d38",
    "validate_exact_campaign_resume_state": "425fe007ae9120094c6994e368bddf7e5f93053e1e8c020e6ea6056e73c6dfe3",
}
_PR2_EXACT_TCB_ARTIFACT_CORE_SOURCE_PIN_NAMES = frozenset(
    {
        "compute_exact_artifact_hashes",
        "canonical_candidate_geometry_rederivation_violation",
        "terminal_certified_final_result_project_precheck_violation",
    }
)

_PR2_EXACT_TCB_CONSTANT_SOURCES = {
    'CAMPAIGN_INSTANCE_ID_KEY': 'CAMPAIGN_INSTANCE_ID_KEY = "campaign_instance_id"',
    'CAMPAIGN_SCHEMA_VERSION': 'CAMPAIGN_SCHEMA_VERSION = 6',
    'CANDIDATE_PROPOSED_STATUS': 'CANDIDATE_PROPOSED_STATUS = "CANDIDATE_PROPOSED"',
    'CERTIFIED_EXACT_SOURCE_DIGEST_KEY': 'CERTIFIED_EXACT_SOURCE_DIGEST_KEY = "certified_exact_source_tree"',
    'CERTIFIED_EXACT_SOURCE_HASH_FILES': 'CERTIFIED_EXACT_SOURCE_HASH_FILES = _discover_certified_exact_source_hash_files()',
    'CHECKPOINT_WRITE_LOCK_TIMEOUT_SECONDS': 'CHECKPOINT_WRITE_LOCK_TIMEOUT_SECONDS = 30.0',
    'DEFAULT_CAMPAIGN_FILENAME': 'DEFAULT_CAMPAIGN_FILENAME = "exact_campaign_state.json"',
    'EXACT_HASH_FILES': 'EXACT_HASH_FILES = {\n    key: LOCKED_EXACT_ARTIFACT_PATHS[key]\n    for key in (\n        "mandatory_exact_instances",\n        "candidate_placements",\n        "canonical_rules",\n        "generic_io_requirements",\n    )\n}',
    'MASTER_DOMAIN_CONTRACT_SCHEMA_VERSION': 'MASTER_DOMAIN_CONTRACT_SCHEMA_VERSION = 1',
    'MISSING_OPTIONAL_EXACT_ARTIFACT_HASH': 'MISSING_OPTIONAL_EXACT_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"',
    'OPTIONAL_EXACT_HASH_FILES': 'OPTIONAL_EXACT_HASH_FILES = {\n    # Runtime preprocess profiles still consume utility/cycle-group declarations\n    # from preprocess_plan.json.  Bind it to checkpoints when present so a plan\n    # edit cannot ride on stale exact artifacts.\n    "preprocess_plan": LOCKED_EXACT_ARTIFACT_PATHS["preprocess_plan"],\n    # The exact flow verifier reads this file directly when present.  Treat its\n    # absence as an explicit artifact state and bind its bytes whenever present.\n    "commodity_demands": "data/preprocessed/commodity_demands.json",\n}',
    'PROOF_BEARING_TERMINAL_STATUSES': 'PROOF_BEARING_TERMINAL_STATUSES = frozenset({"CERTIFIED", "INFEASIBLE"})',
    'PROOF_SUMMARY_SCHEMA_VERSION': 'PROOF_SUMMARY_SCHEMA_VERSION = 1',
    'PROPOSAL_READY_MARKER_AUTHORITY': 'PROPOSAL_READY_MARKER_AUTHORITY = "certified_exact_producer_proposal_ready_v1"',
    'PROPOSAL_READY_MARKER_SCHEMA_VERSION': 'PROPOSAL_READY_MARKER_SCHEMA_VERSION = 2',
    'PROPOSAL_READY_MARKER_SUFFIX': 'PROPOSAL_READY_MARKER_SUFFIX = ".proposal_ready.json"',
    'REQUIRED_CANDIDATE_FIELDS': 'REQUIRED_CANDIDATE_FIELDS = {\n    "ghost_rect",\n    "attempts",\n    "started_at",\n    "updated_at",\n    "finished_at",\n    "status",\n    "proof_summary",\n    "exact_safe_cuts",\n    "loaded_exact_safe_cut_count",\n    "generated_exact_safe_cut_count",\n}',
    'REQUIRED_STATE_FIELDS': 'REQUIRED_STATE_FIELDS = {\n    "schema_version",\n    "solve_mode",\n    CAMPAIGN_INSTANCE_ID_KEY,\n    "campaign_hours",\n    "created_at",\n    "updated_at",\n    "artifact_hashes",\n    "master_domain_contract",\n    "proof_summary_schema_version",\n    "reset_reason",\n    "final_result",\n    "final_status",\n    "last_stop_reason",\n    "terminal_frontier_evidence",\n    "declare_mode",\n    "candidates",\n}',
    'STRONG_CANDIDATE_STATUSES': 'STRONG_CANDIDATE_STATUSES = frozenset({"CERTIFIED", "INFEASIBLE"})',
    'SUPERVISOR_PROPOSAL_STATE_KEY': 'SUPERVISOR_PROPOSAL_STATE_KEY = "supervisor_proposal"',
    'SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION': 'SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION = 2',
    'SUPERVISOR_SEAL_AUTHORITY': 'SUPERVISOR_SEAL_AUTHORITY = "certified_exact_supervisor_seal_v1"',
    'SUPERVISOR_SEAL_SCHEMA_VERSION': 'SUPERVISOR_SEAL_SCHEMA_VERSION = 2',
    'SUPERVISOR_SEAL_STATE_KEY': 'SUPERVISOR_SEAL_STATE_KEY = "supervisor_seal"',
    'TERMINAL_CERTIFIED_FINAL_RESULT_ALLOWED_FIELDS': 'TERMINAL_CERTIFIED_FINAL_RESULT_ALLOWED_FIELDS = frozenset(\n    {\n        "ghost_rect",\n        "placement_solution",\n        "search_status",\n        "search_stats",\n    }\n)',
    'TERMINAL_CERTIFIED_FRONTIER_METRIC_ALLOWED_FIELDS': 'TERMINAL_CERTIFIED_FRONTIER_METRIC_ALLOWED_FIELDS = frozenset(\n    {\n        "selection_score_num",\n        "selection_score_den",\n        "certification_prune_gain",\n        "infeasible_prune_gain",\n        "anchor_count",\n        "frontier_size",\n        "potential_domain_size",\n        "probe_candidate",\n        "probe_prune_gain",\n        "probe_resume_pending",\n    }\n)',
    'TERMINAL_CERTIFIED_GHOST_RECT_ALLOWED_FIELDS': 'TERMINAL_CERTIFIED_GHOST_RECT_ALLOWED_FIELDS = frozenset(\n    {\n        "w",\n        "h",\n        "area",\n        "anchor_x",\n        "anchor_y",\n    }\n)',
    'TERMINAL_CERTIFIED_LAST_STOP_REASON_ALLOWED_FIELDS': 'TERMINAL_CERTIFIED_LAST_STOP_REASON_ALLOWED_FIELDS = frozenset(\n    {\n        "reason",\n        "status",\n        "updated_at",\n    }\n)',
    'TERMINAL_CERTIFIED_PLACEMENT_SOLUTION_ENTRY_ALLOWED_FIELDS': 'TERMINAL_CERTIFIED_PLACEMENT_SOLUTION_ENTRY_ALLOWED_FIELDS = frozenset(\n    {\n        "facility_type",\n        "pose_idx",\n        "pose_id",\n        "anchor",\n        "orientation",\n        "port_mode",\n        "instance_id",\n        "operation_type",\n        "is_mandatory",\n        "bound_type",\n        "solve_mode",\n    }\n)',
    'TERMINAL_CERTIFIED_SEARCH_STATS_ALLOWED_FIELDS': 'TERMINAL_CERTIFIED_SEARCH_STATS_ALLOWED_FIELDS = frozenset(\n    {\n        "attempts",\n        "explicit_candidate_solves",\n        "solve_mode",\n        "campaign_resumed",\n        "frontier_peak_size",\n        "derived_pruned_candidates",\n        "frontier_selection_policy",\n        "frontier_candidate_metrics",\n        "solve_time_seconds",\n        "benders_iterations",\n    }\n)',
    'TERMINAL_FULL_FRONTIER_CERTIFIED_REASON': 'TERMINAL_FULL_FRONTIER_CERTIFIED_REASON = "search_exhausted_all_candidates"',
    'VALID_CANDIDATE_STATUSES': 'VALID_CANDIDATE_STATUSES = {\n    "RUNNING",\n    "CERTIFIED",\n    "INFEASIBLE",\n    "UNKNOWN",\n    "UNPROVEN",\n    # P1 #7a prep: ε-Certified status. status="EPSILON_CERTIFIED" 表示 candidate\n    # 求到 ε-bound 内但未 ε=0 完整 certified。bound_state.epsilon_target 记录\n    # 是哪个 ε 阶段（0.05/0.01/0.0）。final_status 同样可以是 EPSILON_CERTIFIED。\n    "EPSILON_CERTIFIED",\n}',
    'VALID_FINAL_STATUSES': 'VALID_FINAL_STATUSES = frozenset(\n    {\n        "CERTIFIED",\n        "INFEASIBLE",\n        "UNKNOWN",\n        "UNPROVEN",\n        "EPSILON_CERTIFIED",\n        CANDIDATE_PROPOSED_STATUS,\n    }\n)',
    '_PROPOSAL_READY_MARKER_KEYS': '_PROPOSAL_READY_MARKER_KEYS = frozenset(\n    {\n        "schema_version",\n        "authority",\n        "run_id",\n        "exit_code",\n        "checkpoint_sha256",\n        CAMPAIGN_INSTANCE_ID_KEY,\n    }\n)',
    '_PROPOSAL_RUN_ID_ALLOWED_CHARS': '_PROPOSAL_RUN_ID_ALLOWED_CHARS = frozenset(\n    string.ascii_letters + string.digits + "._:-"\n)',
    '_RESUME_CERTIFIED_REPLAY_REASON': '_RESUME_CERTIFIED_REPLAY_REASON = (\n    "certified_candidate_requires_fresh_replay_after_checkpoint_resume"\n)',
    '_RESUME_INFEASIBLE_REPLAY_REASON': '_RESUME_INFEASIBLE_REPLAY_REASON = (\n    "infeasible_candidate_requires_fresh_replay_after_checkpoint_resume"\n)',
    '_SUPERVISOR_PROPOSAL_STATE_KEYS': '_SUPERVISOR_PROPOSAL_STATE_KEYS = frozenset(\n    {"schema_version", "authority", "run_id", CAMPAIGN_INSTANCE_ID_KEY}\n)',
    '_SUPERVISOR_SEAL_STATE_KEYS': '_SUPERVISOR_SEAL_STATE_KEYS = frozenset(\n    {\n        "schema_version",\n        "authority",\n        "transition",\n        "proposal_run_id",\n        "proposal_checkpoint_sha256",\n        "proposal_authority_b64",\n        CAMPAIGN_INSTANCE_ID_KEY,\n        "certified_state_sha256",\n        "sealed_at",\n    }\n)',
    '_SUPERVISOR_SEAL_TOKEN': '_SUPERVISOR_SEAL_TOKEN = object()',
}
_PR2_EXACT_TCB_ARTIFACT_CORE_CONSTANT_NAMES = frozenset(
    {
        "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON",
    }
)


def _check_top_level_prefix_closed_world(
    function: ast.FunctionDef,
    anchor: ast.AST,
    *,
    expected_prefix: Sequence[str],
    label: str,
    ) -> list[str]:
    prefix: list[ast.stmt] = []
    for stmt in function.body:
        if stmt is anchor:
            break
        prefix.append(stmt)
    else:
        return [f"{label} pinned live statement must be a top-level statement"]
    if len(prefix) != len(expected_prefix):
        return [
            f"{label} must have the canonical top-level prefix before its pinned live statement"
        ]
    errors: list[str] = []
    for idx, (stmt, expected_source) in enumerate(zip(prefix, expected_prefix), start=1):
        if not _stmt_matches_source(stmt, expected_source):
            errors.append(
                f"{label} canonical top-level prefix statement {idx} drifted before "
                "its pinned live statement"
            )
    return errors


def _check_top_level_body_closed_world(
    function: ast.FunctionDef,
    *,
    expected_body: Sequence[str],
    label: str,
) -> list[str]:
    if len(function.body) != len(expected_body):
        return [
            f"{label} must match the canonical top-level prefix/body "
            "through its final return"
        ]
    errors: list[str] = []
    for idx, (stmt, expected_source) in enumerate(zip(function.body, expected_body), start=1):
        if not _stmt_matches_source(stmt, expected_source):
            errors.append(
                f"{label} canonical top-level prefix/body statement {idx} drifted"
            )
    return errors


def _check_supervisor_transition_strict_prefix_closed_world(
    function: ast.FunctionDef,
    *,
    strict_assignment: ast.Assign,
    label: str,
) -> list[str]:
    del strict_assignment
    if function.name == "_supervisor_certified_transition_violation_l0":
        expected_body = _PR2_L0_SUPERVISOR_TRANSITION_BODY
    elif function.name == "_supervisor_certified_transition_violation":
        expected_body = _PR2_EXACT_SUPERVISOR_TRANSITION_BODY
    else:
        return [f"{label} has no pinned full-body supervisor transition contract"]
    return _check_top_level_body_closed_world(
        function,
        expected_body=expected_body,
        label=label,
    )


def _check_postwrite_strict_guard_prefix_closed_world(
    function: ast.FunctionDef,
    *,
    guard: ast.If,
    label: str,
) -> list[str]:
    del guard
    return _check_top_level_body_closed_world(
        function,
        expected_body=_PR2_L0_POSTWRITE_BODY,
        label=label,
    )


def _call_first_arg_is_name(call: ast.Call, name: str) -> bool:
    return bool(call.args and _is_name(call.args[0], name))


def _dynamic_namespace_mapping_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript):
        namespace = node.value
        if (
            isinstance(namespace, ast.Call)
            and _call_func_name(namespace) in {"locals", "globals", "vars"}
            and not namespace.args
            and not namespace.keywords
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            return node.slice.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Call)
        and _call_func_name(node.func.value) in {"locals", "globals", "vars"}
        and not node.func.value.args
        and not node.func.value.keywords
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _expr_may_reference_mapping(node: ast.AST, mapping_names: frozenset[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in mapping_names or node.id.startswith("proposal_")
    dynamic_name = _dynamic_namespace_mapping_name(node)
    if dynamic_name in mapping_names:
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return any(_expr_may_reference_mapping(item, mapping_names) for item in node.elts)
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if key is None and _expr_may_reference_mapping(value, mapping_names):
                return True
            if key is not None and _expr_may_reference_mapping(key, mapping_names):
                return True
            if _expr_may_reference_mapping(value, mapping_names):
                return True
        return False
    if isinstance(node, ast.Attribute):
        return _expr_may_reference_mapping(node.value, mapping_names)
    if isinstance(node, ast.Subscript):
        return _expr_may_reference_mapping(node.value, mapping_names)
    if isinstance(node, ast.Call):
        return (
            _expr_may_reference_mapping(node.func, mapping_names)
            or any(_expr_may_reference_mapping(arg, mapping_names) for arg in node.args)
            or any(
                _expr_may_reference_mapping(keyword.value, mapping_names)
                for keyword in node.keywords
            )
        )
    return False


def _subscript_constant_slot_for_names(node: ast.AST, base_names: frozenset[str]) -> tuple[str, str] | None:
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in base_names
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ):
        return node.value.id, node.slice.value
    return None


def _call_may_clobber_mapping_slot(
    call: ast.Call,
    mapping_name: str,
    slot: str,
    *,
    aliases: frozenset[str] = frozenset(),
) -> bool:
    mapping_names = frozenset({mapping_name}) | aliases
    if isinstance(call.func, ast.Attribute):
        if _expr_may_reference_mapping(call.func.value, mapping_names):
            if call.func.attr in {
                "update",
                "clear",
                "setdefault",
                "__setitem__",
                "__delitem__",
                "__ior__",
                "popitem",
            }:
                return True
            if call.func.attr == "pop":
                if not call.args:
                    return True
                if _is_constant(call.args[0], slot):
                    return True
                if isinstance(call.args[0], ast.Name) and call.args[0].id == "SUPERVISOR_PROPOSAL_STATE_KEY":
                    return False
                return not isinstance(call.args[0], ast.Constant)
        dotted = _call_func_name(call)
        if dotted in {
            "dict.update",
            "dict.__setitem__",
            "dict.__delitem__",
            "dict.__ior__",
            "type.__setitem__",
            "type.__delitem__",
            "type.__ior__",
            "operator.setitem",
            "operator.ior",
        }:
            return bool(call.args and _expr_may_reference_mapping(call.args[0], mapping_names))
    if (
        _call_func_name(call) == "getattr"
        and call.args
        and _expr_may_reference_mapping(call.args[0], mapping_names)
    ):
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            return call.args[1].value in _PR2_MUTATING_MAPPING_METHODS
        return True
    return False


def _check_literal_strict_slot_assignment(
    function: ast.FunctionDef,
    *,
    mapping_name: str,
    slot: str,
    label: str,
    require_live_top_level: bool = False,
) -> list[str]:
    errors: list[str] = []
    assignments: list[ast.Assign] = []
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _subscript_constant_slot(target, mapping_name) == slot:
                    assignments.append(node)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if _subscript_constant_slot(node.target, mapping_name) == slot:
                errors.append(f'{label} must not use AnnAssign/AugAssign for {mapping_name}["{slot}"]')
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if _subscript_constant_slot(target, mapping_name) == slot:
                    errors.append(f'{label} must not delete {mapping_name}["{slot}"]')
    if len(assignments) != 1:
        errors.append(
            f'{label} must have exactly one AST assignment {mapping_name}["{slot}"] = "strict"'
        )
        return errors
    assignment = assignments[0]
    if not _is_constant(assignment.value, "strict"):
        errors.append(f'{label} must assign literal "strict" to {mapping_name}["{slot}"]')
    if require_live_top_level:
        if mapping_name == "expected" and slot == "declare_mode":
            errors.extend(
                _check_supervisor_transition_strict_prefix_closed_world(
                    function,
                    strict_assignment=assignment,
                    label=label,
                )
            )
        errors.extend(
            _check_no_direct_top_level_exit_before_node(
                function,
                assignment,
                label=label,
            )
        )
    ordered_nodes = sorted(
        (node for node in ast.walk(function) if hasattr(node, "lineno")),
        key=lambda node: (
            int(getattr(node, "lineno", 0) or 0),
            int(getattr(node, "col_offset", 0) or 0),
        ),
    )
    aliases: set[str] = set()
    for node in ordered_nodes:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in {mapping_name} | aliases:
            for target in node.targets:
                for bound_name in _target_bound_names(target):
                    if bound_name != mapping_name:
                        aliases.add(bound_name)
        if _node_starts_after(node, assignment):
            break
    for node in ordered_nodes:
        if node is assignment or not hasattr(node, "lineno"):
            continue
        if not _node_starts_after(node, assignment):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == mapping_name:
                    errors.append(f"{label} must not rebind {mapping_name} after strict assignment")
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id in {mapping_name} | aliases
                    and target.id != mapping_name
                    if isinstance(target, ast.Name)
                    else False
                ):
                    aliases.add(target.id)  # type: ignore[union-attr]
                matched_slot = _subscript_constant_slot_for_names(target, frozenset({mapping_name}) | frozenset(aliases))
                if matched_slot is not None and matched_slot[1] == slot:
                    errors.append(f'{label} must not clobber {mapping_name}["{slot}"] after strict assignment')
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(node.target, ast.Name) and node.target.id == mapping_name:
                errors.append(f"{label} must not rebind {mapping_name} after strict assignment")
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in aliases:
                errors.append(f'{label} must not clobber {mapping_name}["{slot}"] through alias {node.target.id}')
            matched_slot = _subscript_constant_slot_for_names(
                node.target,
                frozenset({mapping_name}) | frozenset(aliases),
            )
            if matched_slot is not None and matched_slot[1] == slot:
                errors.append(f'{label} must not clobber {mapping_name}["{slot}"] after strict assignment')
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == mapping_name:
                    errors.append(f"{label} must not delete {mapping_name} after strict assignment")
                matched_slot = _subscript_constant_slot_for_names(
                    target,
                    frozenset({mapping_name}) | frozenset(aliases),
                )
                if matched_slot is not None and matched_slot[1] == slot:
                    errors.append(f'{label} must not delete {mapping_name}["{slot}"] after strict assignment')
        elif (
            isinstance(node, ast.Call)
            and _call_may_clobber_mapping_slot(
                node,
                mapping_name,
                slot,
                aliases=frozenset(aliases),
            )
        ):
            errors.append(f'{label} must not call a mutator that can clobber {mapping_name}["{slot}"]')
    return errors


def _postwrite_strict_declare_mode_guard(stmt: ast.stmt) -> bool:
    if not (
        isinstance(stmt, ast.If)
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], ast.Return)
        and _is_constant(stmt.body[0].value, "postwrite_declare_mode_not_strict")
        and not stmt.orelse
        and isinstance(stmt.test, ast.Compare)
        and len(stmt.test.ops) == 1
        and isinstance(stmt.test.ops[0], ast.NotEq)
        and len(stmt.test.comparators) == 1
        and _is_constant(stmt.test.comparators[0], "strict")
        and isinstance(stmt.test.left, ast.Call)
        and _call_func_name(stmt.test.left) == "str"
        and len(stmt.test.left.args) == 1
        and not stmt.test.left.keywords
    ):
        return False
    declare_mode_get = stmt.test.left.args[0]
    return (
        isinstance(declare_mode_get, ast.Call)
        and isinstance(declare_mode_get.func, ast.Attribute)
        and declare_mode_get.func.attr == "get"
        and _is_name(declare_mode_get.func.value, "disk_state")
        and len(declare_mode_get.args) == 1
        and _is_constant(declare_mode_get.args[0], "declare_mode")
        and not declare_mode_get.keywords
    )


def _check_live_top_level_postwrite_guard(function: ast.FunctionDef) -> list[str]:
    guards = [stmt for stmt in function.body if _postwrite_strict_declare_mode_guard(stmt)]
    if len(guards) != 1:
        return [
            "PR2 L0 postwrite validator must have exactly one live top-level "
            "declare_mode strict guard returning postwrite_declare_mode_not_strict"
        ]
    return _check_no_direct_top_level_exit_before_node(
        function,
        guards[0],
        label="PR2 L0 postwrite validator",
    ) + _check_postwrite_strict_guard_prefix_closed_world(
        function,
        guard=guards[0],
        label="PR2 L0 postwrite validator",
    )


def _returns_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Return) and (
        node.value is None
        or (
            isinstance(node.value, ast.Constant)
            and node.value.value is None
        )
    )


def _semantic_body(function: ast.FunctionDef) -> list[ast.stmt]:
    body = list(function.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _iter_statement_sequences(statements: Sequence[ast.stmt]) -> Iterator[Sequence[ast.stmt]]:
    yield statements
    for stmt in statements:
        if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            yield from _iter_statement_sequences(stmt.body)
            yield from _iter_statement_sequences(stmt.orelse)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            yield from _iter_statement_sequences(stmt.body)
        elif isinstance(stmt, ast.Try):
            yield from _iter_statement_sequences(stmt.body)
            yield from _iter_statement_sequences(stmt.orelse)
            yield from _iter_statement_sequences(stmt.finalbody)
            for handler in stmt.handlers:
                yield from _iter_statement_sequences(handler.body)


def _if_test_name_is_not_none(test: ast.AST, name: str) -> bool:
    return (
        isinstance(test, ast.Compare)
        and _is_name(test.left, name)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    )


def _if_consumes_guard_result(stmt: ast.stmt, result_name: str, *, effect: str) -> bool:
    if not (
        isinstance(stmt, ast.If)
        and _if_test_name_is_not_none(stmt.test, result_name)
        and len(stmt.body) == 1
        and not stmt.orelse
    ):
        return False
    if effect == "return":
        return isinstance(stmt.body[0], ast.Return)
    if effect == "raise":
        return isinstance(stmt.body[0], ast.Raise)
    return False


def _assigns_name_from_call(stmt: ast.AST, target_name: str, call_name: str) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {target_name}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == call_name
    )


def _binds_name_from_call(stmt: ast.AST, target_name: str, call_name: str) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and target_name in _target_bound_names(stmt.targets[0])
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == call_name
    )


def _binds_name_from_expr_source(stmt: ast.AST, target_name: str, source: str) -> bool:
    if isinstance(stmt, ast.Assign):
        return (
            len(stmt.targets) == 1
            and _target_bound_names(stmt.targets[0]) == {target_name}
            and _expr_matches_source(stmt.value, source)
        )
    if isinstance(stmt, ast.AnnAssign):
        return (
            _target_bound_names(stmt.target) == {target_name}
            and stmt.value is not None
            and _expr_matches_source(stmt.value, source)
        )
    return False


def _stmt_binds_name(stmt: ast.AST, name: str) -> bool:
    return name in _stmt_bound_names(stmt)


def _delete_targets_name(stmt: ast.Delete, name: str) -> bool:
    return any(name in _target_bound_names(target) for target in stmt.targets)


def _expr_is_direct_alias_for_names(node: ast.AST, names: frozenset[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in names


def _target_writes_attribute_of_names(target: ast.AST, names: frozenset[str]) -> bool:
    for node in ast.walk(target):
        if isinstance(node, ast.Attribute) and _expr_may_reference_mapping(node.value, names):
            return True
    return False


def _expr_is_no_clobber_mutator_callable(node: ast.AST, names: frozenset[str]) -> bool:
    if isinstance(node, ast.Attribute) and _expr_may_reference_mapping(node.value, names):
        return node.attr in _PR2_MUTATING_MAPPING_METHODS
    if not isinstance(node, ast.Call) or _call_func_name(node) != "getattr":
        return False
    if not node.args or not _expr_may_reference_mapping(node.args[0], names):
        return False
    if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
        return True
    return node.args[1].value in _PR2_MUTATING_MAPPING_METHODS


def _call_mutates_no_clobber_name(call: ast.Call, names: frozenset[str]) -> bool:
    call_name = _call_func_name(call)
    if call_name in {"setattr", "delattr", "vars"} and any(
        _expr_may_reference_mapping(arg, names) for arg in call.args
    ):
        return True
    if call_name in {
        "dict.clear",
        "dict.pop",
        "dict.popitem",
        "dict.__setitem__",
        "dict.__delitem__",
        "dict.__ior__",
        "operator.setitem",
        "operator.delitem",
        "operator.ior",
    }:
        return bool(call.args and _expr_may_reference_mapping(call.args[0], names))
    if isinstance(call.func, ast.Attribute):
        if (
            call.func.attr in _PR2_MUTATING_MAPPING_METHODS
            and _expr_may_reference_mapping(call.func.value, names)
        ):
            return True
        if (
            call.func.attr in _PR2_MUTATING_MAPPING_METHODS
            and call.args
            and _expr_may_reference_mapping(call.args[0], names)
        ):
            return True
    if isinstance(call.func, ast.Call) and _call_func_name(call.func) == "getattr":
        getattr_call = call.func
        if not getattr_call.args or not _expr_may_reference_mapping(getattr_call.args[0], names):
            return False
        if len(getattr_call.args) < 2 or not isinstance(getattr_call.args[1], ast.Constant):
            return True
        return getattr_call.args[1].value in _PR2_MUTATING_MAPPING_METHODS
    return False


def _ordered_nodes(root: ast.AST) -> list[ast.AST]:
    return sorted(
        (node for node in ast.walk(root) if hasattr(node, "lineno")),
        key=lambda node: (
            int(getattr(node, "lineno", 0) or 0),
            int(getattr(node, "col_offset", 0) or 0),
        ),
    )


def _matching_nodes_after(
    function: ast.FunctionDef,
    anchor: ast.AST,
    predicate: Callable[[ast.AST], bool],
) -> list[ast.AST]:
    return [
        node
        for node in _ordered_nodes(function)
        if _node_starts_after(node, anchor) and predicate(node)
    ]


def _check_name_not_rebound_after(
    function: ast.FunctionDef,
    *,
    name: str,
    anchor: ast.AST,
    label: str,
    until: ast.AST | None = None,
) -> list[str]:
    errors: list[str] = []
    protected_names: set[str] = {name}
    protected_mutator_callables: set[str] = set()
    for node in _ordered_nodes(function):
        if _node_starts_after(node, anchor):
            break
        if node is not anchor and _stmt_binds_name(node, name):
            errors.append(f"{label} must not pre-bind {name} before its pinned assignment")
    for node in _ordered_nodes(function):
        if node is anchor or not _node_starts_after(node, anchor):
            continue
        if until is not None and (node is until or _node_starts_after(node, until)):
            break
        frozen_names = frozenset(protected_names)
        if _stmt_binds_name(node, name):
            errors.append(f"{label} must not clobber {name} after its pinned assignment")
        if isinstance(node, ast.Delete) and _delete_targets_name(node, name):
            errors.append(f"{label} must not delete {name} after its pinned assignment")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bound_names = _target_bound_names(target)
                for bound_name in sorted(bound_names & protected_names):
                    errors.append(
                        f"{label} must not clobber {name} after its pinned assignment"
                    )
                if _target_writes_attribute_of_names(target, frozen_names):
                    errors.append(f"{label} must not mutate {name} after its pinned assignment")
                if _expr_is_direct_alias_for_names(node.value, frozen_names):
                    protected_names.update(bound_names)
                elif _expr_is_no_clobber_mutator_callable(node.value, frozen_names):
                    protected_mutator_callables.update(bound_names)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            bound_names = _target_bound_names(node.target)
            for bound_name in sorted(bound_names & protected_names):
                errors.append(f"{label} must not clobber {name} after its pinned assignment")
            if _target_writes_attribute_of_names(node.target, frozen_names):
                errors.append(f"{label} must not mutate {name} after its pinned assignment")
            if (
                isinstance(node, ast.AnnAssign)
                and node.value is not None
                and _expr_is_direct_alias_for_names(node.value, frozen_names)
            ):
                protected_names.update(bound_names)
        elif isinstance(node, ast.NamedExpr):
            bound_names = _target_bound_names(node.target)
            for bound_name in sorted(bound_names & protected_names):
                errors.append(f"{label} must not clobber {name} after its pinned assignment")
            if _expr_is_direct_alias_for_names(node.value, frozen_names):
                protected_names.update(bound_names)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if _target_writes_attribute_of_names(target, frozen_names):
                    errors.append(f"{label} must not mutate {name} after its pinned assignment")
        elif isinstance(node, ast.Call):
            if _call_mutates_no_clobber_name(node, frozen_names):
                errors.append(f"{label} must not mutate {name} after its pinned assignment")
            if isinstance(node.func, ast.Name) and node.func.id in protected_mutator_callables:
                errors.append(f"{label} must not mutate {name} after its pinned assignment")
    return errors


def _if_truthy_consumes_result(stmt: ast.stmt, result_name: str, *, effect: str) -> bool:
    if not (isinstance(stmt, ast.If) and _is_name(stmt.test, result_name) and not stmt.orelse):
        return False
    if effect == "raise":
        return any(isinstance(child, ast.Raise) for child in stmt.body)
    if effect == "return":
        return any(isinstance(child, ast.Return) for child in stmt.body)
    return False


def _check_result_flow_to_truthy_consumer(
    function: ast.FunctionDef,
    *,
    result_name: str,
    assignment_predicate: Callable[[ast.AST], bool],
    effect: str,
    label: str,
) -> list[str]:
    assignments = [
        node
        for node in _ordered_nodes(function)
        if assignment_predicate(node)
    ]
    if len(assignments) != 1:
        return [f"{label} must assign {result_name} exactly once from its pinned source"]
    assignment = assignments[0]
    consumers = _matching_nodes_after(
        function,
        assignment,
        lambda node: isinstance(node, ast.If)
        and _if_truthy_consumes_result(node, result_name, effect=effect),
    )
    if len(consumers) != 1:
        return [f"{label} must consume {result_name} in exactly one fail-closed truthy gate"]
    return _check_name_not_rebound_after(
        function,
        name=result_name,
        anchor=assignment,
        until=consumers[0],
        label=label,
    )


def _check_call_result_flow_to_truthy_consumer(
    function: ast.FunctionDef,
    *,
    call_name: str,
    result_name: str,
    effect: str,
    label: str,
) -> list[str]:
    return _check_result_flow_to_truthy_consumer(
        function,
        result_name=result_name,
        assignment_predicate=lambda node: _binds_name_from_call(node, result_name, call_name),
        effect=effect,
        label=label,
    )


def _check_expr_result_flow_to_truthy_consumer(
    function: ast.FunctionDef,
    *,
    source: str,
    result_name: str,
    effect: str,
    label: str,
) -> list[str]:
    return _check_result_flow_to_truthy_consumer(
        function,
        result_name=result_name,
        assignment_predicate=lambda node: _binds_name_from_expr_source(node, result_name, source),
        effect=effect,
        label=label,
    )


def _check_call_assignment_no_rebind(
    function: ast.FunctionDef,
    *,
    call_name: str,
    result_name: str,
    label: str,
) -> list[str]:
    assignments = [
        node
        for node in _ordered_nodes(function)
        if _binds_name_from_call(node, result_name, call_name)
    ]
    if len(assignments) != 1:
        return [f"{label} must assign {result_name} exactly once from {call_name}(...)"]
    return _check_name_not_rebound_after(
        function,
        name=result_name,
        anchor=assignments[0],
        label=label,
    )


def _compare_gate_has_effect(stmt: ast.If, effect: str) -> bool:
    if stmt.orelse:
        return False
    if effect == "return":
        return len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Return)
    if effect == "raise":
        return len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Raise)
    if effect == "violation_continue":
        if len(stmt.body) != 2 or not isinstance(stmt.body[1], ast.Continue):
            return False
        first = stmt.body[0]
        if not isinstance(first, ast.Assign) or len(first.targets) != 1:
            return False
        target = first.targets[0]
        return isinstance(target, ast.Subscript) and _is_name(target.value, "violations")
    return False


def _check_result_flow_to_compare_gate(
    function: ast.FunctionDef,
    *,
    result_name: str,
    call_name: str | None = None,
    source: str | None = None,
    compare_test: str,
    effect: str,
    label: str,
) -> list[str]:
    if (call_name is None) == (source is None):
        return [f"{label} result-flow checker must pin exactly one assignment source"]
    if call_name is not None:
        def assignment_predicate(node: ast.AST) -> bool:
            return _binds_name_from_call(node, result_name, call_name)
        assignment_description = f"{call_name}(...)"
    else:
        def assignment_predicate(node: ast.AST) -> bool:
            return _binds_name_from_expr_source(node, result_name, source or "")
        assignment_description = source or "<source>"
    assignments = [
        node
        for node in _ordered_nodes(function)
        if assignment_predicate(node)
    ]
    if len(assignments) != 1:
        return [f"{label} must assign {result_name} exactly once from {assignment_description}"]
    assignment = assignments[0]
    consumers = _matching_nodes_after(
        function,
        assignment,
        lambda node: isinstance(node, ast.If) and _expr_matches_source(node.test, compare_test),
    )
    if len(consumers) != 1:
        return [f"{label} must consume {result_name} in the pinned compare gate"]
    consumer = consumers[0]
    if not _compare_gate_has_effect(consumer, effect):
        return [f"{label} compare gate for {result_name} must have live fail-closed effect: {effect}"]
    return _check_name_not_rebound_after(
        function,
        name=result_name,
        anchor=assignment,
        until=consumer,
        label=label,
    )


def _check_guard_result_flow(
    function: ast.FunctionDef,
    *,
    call_name: str,
    result_name: str,
    effect: str,
    label: str,
) -> list[str]:
    assignments = []
    for sequence in _iter_statement_sequences(_semantic_body(function)):
        assignments.extend(
            (sequence, index)
            for index, stmt in enumerate(sequence)
            if _assigns_name_from_call(stmt, result_name, call_name)
        )
    if len(assignments) != 1:
        return [f"{label} must assign {result_name} exactly once from {call_name}(...)"]
    sequence, assignment_index = assignments[0]
    guard_index = assignment_index + 1
    if guard_index >= len(sequence) or not _if_consumes_guard_result(
        sequence[guard_index],
        result_name,
        effect=effect,
    ):
        return [
            f"{label} must immediately consume {result_name} with "
            f"if {result_name} is not None: {effect}"
        ]
    return []


def _check_l0_supervisor_gate_result_flow(l0_seal_fn: ast.FunctionDef) -> list[str]:
    errors: list[str] = []
    for call_name, result_name, effect in (
        ("_domain_response_violation", "domain_violation", "return"),
        ("_supervisor_seal_state_violation_l0", "seal_violation", "return"),
        ("_postwrite_state_violation", "postwrite_violation", "raise"),
    ):
        errors.extend(
            _check_guard_result_flow(
                l0_seal_fn,
                call_name=call_name,
                result_name=result_name,
                effect=effect,
                label="PR2 L0 supervisor seal",
            )
        )
    return errors


def _check_true_verifier_entrypoint_body(verify_fn: ast.FunctionDef) -> list[str]:
    return _check_top_level_body_closed_world(
        verify_fn,
        expected_body=_PR2_CHILD_VERIFY_BODY,
        label="PR2 true verifier child verify entrypoint",
    )


def _check_l0_supervisor_seal_state_body(seal_state_fn: ast.FunctionDef) -> list[str]:
    return _check_top_level_body_closed_world(
        seal_state_fn,
        expected_body=_PR2_L0_SUPERVISOR_SEAL_STATE_BODY,
        label="PR2 L0 supervisor seal state validator",
    )


def _check_l0_supervisor_seal_body(l0_seal_fn: ast.FunctionDef) -> list[str]:
    return _check_top_level_body_closed_world(
        l0_seal_fn,
        expected_body=_PR2_L0_RUN_SUPERVISOR_SEAL_BODY,
        label="PR2 L0 supervisor seal durable writer",
    )


def _check_child_verify_supervisor_domain_body(child_domain_fn: ast.FunctionDef) -> list[str]:
    return _check_top_level_body_closed_world(
        child_domain_fn,
        expected_body=_PR2_CHILD_VERIFY_SUPERVISOR_DOMAIN_BODY,
        label="PR2 true verifier child supervisor domain chokepoint",
    )


def _check_child_project_records_body(child_project_fn: ast.FunctionDef) -> list[str]:
    return _check_top_level_body_closed_world(
        child_project_fn,
        expected_body=_PR2_CHILD_PROJECT_RECORDS_BODY,
        label="PR2 child candidate projection chokepoint",
    )


def _check_child_fixed_witness_body(child_fixed_fn: ast.FunctionDef) -> list[str]:
    return _check_top_level_body_closed_world(
        child_fixed_fn,
        expected_body=_PR2_CHILD_FIXED_WITNESS_BODY,
        label="PR2 child fixed witness chokepoint",
    )


def _check_l0_import_binding_pins(l0_tree: ast.Module) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {name: 0 for name in _PR2_L0_ALLOWED_IMPORT_BINDINGS}
    for stmt in l0_tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                expected = _PR2_L0_ALLOWED_IMPORT_BINDINGS.get(bound_name)
                if expected is None:
                    if bound_name in _PR2_L0_FORBIDDEN_TOP_LEVEL_SHADOW_NAMES:
                        errors.append(f"PR2 L0 runtime TCB must not shadow/rebind {bound_name}")
                    continue
                if expected[0] != "import" or alias.name != expected[1] or alias.asname != expected[2]:
                    errors.append(
                        f"PR2 L0 runtime TCB import binding for {bound_name} must match pinned source"
                    )
                seen[bound_name] += 1
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                bound_name = alias.asname or alias.name
                expected = _PR2_L0_ALLOWED_IMPORT_BINDINGS.get(bound_name)
                if expected is None:
                    if bound_name in _PR2_L0_FORBIDDEN_TOP_LEVEL_SHADOW_NAMES:
                        errors.append(f"PR2 L0 runtime TCB must not shadow/rebind {bound_name}")
                    continue
                if (
                    expected[0] != "from"
                    or stmt.level != 0
                    or stmt.module != expected[1]
                    or alias.name != expected[2]
                    or alias.asname is not None
                ):
                    errors.append(
                        f"PR2 L0 runtime TCB import binding for {bound_name} must match pinned source"
                    )
                seen[bound_name] += 1
    for name, count in sorted(seen.items()):
        if count != 1:
            errors.append(f"PR2 L0 runtime TCB import binding for {name} must be unique")
    return errors


def _check_l0_runtime_tcb_bindings(l0_tree: ast.Module, *, path: Path) -> list[str]:
    errors: list[str] = []
    tcb_names = (
        frozenset(_PR2_L0_TCB_FUNCTION_SOURCE_SHA256)
        | frozenset(_PR2_L0_TCB_CONSTANT_SOURCES)
        | frozenset({"CHILD_BOOTSTRAP_SOURCE"})
    )
    errors.extend(
        _check_unique_top_level_bindings(
            l0_tree,
            tcb_names,
            path=path,
            label="PR2 L0 runtime TCB",
        )
    )
    for name in sorted(_PR2_L0_FORBIDDEN_TOP_LEVEL_SHADOW_NAMES):
        points = [
            node
            for node in _top_level_binding_points(l0_tree, name)
            if not isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if points:
            lines = ", ".join(str(getattr(node, "lineno", "?")) for node in points)
            errors.append(f"PR2 L0 runtime TCB must not shadow/rebind {name}; found lines {lines}")
    errors.extend(_check_l0_import_binding_pins(l0_tree))
    for name, expected_sha256 in sorted(_PR2_L0_TCB_FUNCTION_SOURCE_SHA256.items()):
        function = _resolve_source_pin_node(l0_tree, name, path=path)
        if _normalized_source_sha256(path, function) != expected_sha256:
            errors.append(f"PR2 L0 runtime TCB source sha256 drifted for {name}")
    for name, expected_source in sorted(_PR2_L0_TCB_CONSTANT_SOURCES.items()):
        bindings = _top_level_binding_points(l0_tree, name)
        if len(bindings) != 1 or not isinstance(bindings[0], ast.Assign):
            errors.append(f"PR2 L0 runtime TCB constant {name} must have one top-level assignment")
            continue
        if _normalized_source_text(path, bindings[0]) != expected_source:
            errors.append(f"PR2 L0 runtime TCB constant {name} must match pinned source")
    bootstrap_bindings = _top_level_binding_points(l0_tree, "CHILD_BOOTSTRAP_SOURCE")
    if len(bootstrap_bindings) != 1 or not isinstance(bootstrap_bindings[0], ast.Assign):
        errors.append("PR2 L0 runtime TCB CHILD_BOOTSTRAP_SOURCE must have one top-level assignment")
    else:
        try:
            bootstrap_value = ast.literal_eval(bootstrap_bindings[0].value)
        except Exception:
            bootstrap_value = None
        if not isinstance(bootstrap_value, str):
            errors.append("PR2 L0 runtime TCB CHILD_BOOTSTRAP_SOURCE must be a string literal")
        elif hashlib.sha256(bootstrap_value.encode("utf-8")).hexdigest() != (
            _PR2_L0_CHILD_BOOTSTRAP_SOURCE_VALUE_SHA256
        ):
            errors.append("PR2 L0 runtime TCB CHILD_BOOTSTRAP_SOURCE value sha256 drifted")
    return errors


def _check_true_child_runtime_tcb_source_pins(
    child_tree: ast.Module,
    *,
    path: Path,
) -> list[str]:
    errors: list[str] = []
    for name, expected_sha256 in sorted(_PR2_TRUE_CHILD_TCB_FUNCTION_SOURCE_SHA256.items()):
        function = _resolve_source_pin_node(child_tree, name, path=path)
        if _normalized_source_sha256(path, function) != expected_sha256:
            errors.append(
                f"PR2 true verifier child TCB source sha256 drifted for {name}"
            )
    return errors


def _check_exact_runtime_tcb_source_pins(
    exact_tree: ast.Module,
    exact_class: ast.ClassDef,
    *,
    path: Path,
    artifact_core_tree: ast.Module | None = None,
    artifact_core_path: Path = PR2_L0_ARTIFACT_CORE_PATH,
) -> list[str]:
    errors: list[str] = []
    if artifact_core_tree is None:
        artifact_core_tree = _parse_python(artifact_core_path)
    for name, expected_sha256 in sorted(_PR2_EXACT_TCB_SOURCE_SHA256.items()):
        source_tree = (
            artifact_core_tree
            if name in _PR2_EXACT_TCB_ARTIFACT_CORE_SOURCE_PIN_NAMES
            else exact_tree
        )
        source_path = (
            artifact_core_path
            if name in _PR2_EXACT_TCB_ARTIFACT_CORE_SOURCE_PIN_NAMES
            else path
        )
        function = _resolve_source_pin_node(source_tree, name, path=source_path)
        if _normalized_source_sha256(source_path, function) != expected_sha256:
            errors.append(f"ExactCampaign save TCB source sha256 drifted for {name}")
    for name, expected_source in sorted(_PR2_EXACT_TCB_CONSTANT_SOURCES.items()):
        source_tree = (
            artifact_core_tree
            if name in _PR2_EXACT_TCB_ARTIFACT_CORE_CONSTANT_NAMES
            else exact_tree
        )
        source_path = (
            artifact_core_path
            if name in _PR2_EXACT_TCB_ARTIFACT_CORE_CONSTANT_NAMES
            else path
        )
        bindings = _top_level_binding_points(source_tree, name)
        if len(bindings) != 1 or not isinstance(bindings[0], (ast.Assign, ast.AnnAssign)):
            errors.append(
                f"PR2 exact runtime TCB constant {name} must have one top-level assignment"
            )
            continue
        if _normalized_source_text(source_path, bindings[0]) != expected_source:
            errors.append(f"PR2 exact runtime TCB constant {name} must match pinned source")
    return errors


_PR2_CLOSE_KERNEL_SPECIAL_CONSTANTS: dict[str, frozenset[str]] = {
    "PR2 L0 micro-verifier": frozenset({"CHILD_BOOTSTRAP_SOURCE"}),
    "PR2 true verifier child": frozenset(),
    "PR2 exact campaign": frozenset(),
}


_PR2_CLOSE_KERNEL_CLASS_DEF_SHAPES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "PR2 L0 micro-verifier.L0MicroVerdict": ((), ()),
    "PR2 L0 micro-verifier.L0SupervisorSealRequest": ((), ()),
    "PR2 true verifier child._StdlibOnlyPathFinder": ((), ()),
    "PR2 true verifier child._RestrictedThirdPartyFinder": ((), ()),
    "PR2 true verifier child._RehashingSourceFileLoader": (
        ("importlib.machinery.SourceFileLoader",),
        (),
    ),
    "PR2 true verifier child._RehashingExtensionFileLoader": (
        ("importlib.machinery.ExtensionFileLoader",),
        (),
    ),
    "PR2 exact campaign.ExactCampaign": ((), ()),
}

_PR2_CLOSE_KERNEL_CLASS_FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "PR2 L0 micro-verifier.L0MicroVerdict": (
        "status: str",
        "nonce: str",
        "reason: str",
        "floor_digest: str | None = None",
        "response: Mapping[str, Any] = field(default_factory=dict)",
    ),
    "PR2 L0 micro-verifier.L0SupervisorSealRequest": (
        "project_root: Path",
        "campaign_path: Path",
        "marker_path: Path",
        "expected_campaign_instance_id: str",
        "timeout_seconds: float = 3600.0",
    ),
    "PR2 true verifier child._StdlibOnlyPathFinder": (),
    "PR2 true verifier child._RestrictedThirdPartyFinder": (),
    "PR2 true verifier child._RehashingSourceFileLoader": (),
    "PR2 true verifier child._RehashingExtensionFileLoader": (),
    "PR2 exact campaign.ExactCampaign": (
        "project_root: Path",
        "path: Path",
        "state: Dict[str, Any]",
        "resumed: bool",
        "compatible_hashes: bool",
    ),
}
_PR2_CLOSE_KERNEL_FORBIDDEN_CLASS_RUNTIME_HOOKS = frozenset(
    {
        "__delattr__",
        "__getattr__",
        "__getattribute__",
        "__post_init__",
        "__setattr__",
    }
)
_PR2_CLOSE_KERNEL_CLASS_RUNTIME_MEMBER_LAYOUTS: dict[str, tuple[tuple[str, str], ...]] = {
    "PR2 L0 micro-verifier.L0MicroVerdict": (
        ("field", "status"),
        ("field", "nonce"),
        ("field", "reason"),
        ("field", "floor_digest"),
        ("field", "response"),
    ),
    "PR2 L0 micro-verifier.L0SupervisorSealRequest": (
        ("field", "project_root"),
        ("field", "campaign_path"),
        ("field", "marker_path"),
        ("field", "expected_campaign_instance_id"),
        ("field", "timeout_seconds"),
    ),
    "PR2 true verifier child._StdlibOnlyPathFinder": (
        ("method", "__init__"),
        ("method", "find_spec"),
    ),
    "PR2 true verifier child._RestrictedThirdPartyFinder": (
        ("method", "__init__"),
        ("method", "find_spec"),
    ),
    "PR2 true verifier child._RehashingSourceFileLoader": (
        ("method", "__init__"),
        ("method", "get_data"),
        ("method", "get_code"),
    ),
    "PR2 true verifier child._RehashingExtensionFileLoader": (
        ("method", "__init__"),
        ("method", "create_module"),
    ),
    "PR2 exact campaign.ExactCampaign": (
        ("field", "project_root"),
        ("field", "path"),
        ("field", "state"),
        ("field", "resumed"),
        ("field", "compatible_hashes"),
        ("method", "load_or_create"),
        ("method", "artifact_hashes"),
        ("method", "campaign_hours"),
        ("method", "reset_reason"),
        ("method", "remaining_seconds"),
        ("method", "elapsed_seconds"),
        ("method", "is_compatible_with_current_hashes"),
        ("method", "get_candidate_record"),
        ("method", "get_candidate_cuts"),
        ("method", "get_candidate_bound_state"),
        ("method", "update_candidate_bound_state"),
        ("method", "get_audit_log"),
        ("method", "mark_candidate_started"),
        ("method", "mark_candidate_result"),
        ("method", "_mark_candidate_result_from_verified_producer"),
        ("method", "update_candidate_running_proof_summary"),
        ("method", "proposal_ready_marker_path"),
        ("method", "set_supervisor_proposal_run_id"),
        ("method", "clear_proposal_ready_marker"),
        ("method", "write_proposal_ready_marker"),
        ("method", "_load_supervisor_proposal_authority"),
        ("method", "_assert_proposal_marker_still_current"),
        ("method", "_clear_proposal_ready_marker_if_unchanged"),
        ("method", "_validate_supervisor_certified_state_before_commit"),
        ("method", "supervisor_seal"),
        ("method", "mark_campaign_stopped"),
        ("method", "best_certified_result"),
        ("method", "save"),
    ),
}
_PR2_CLOSE_KERNEL_DECORATOR_SOURCES: dict[str, tuple[str, ...]] = {
    "PR2 exact campaign.ExactCampaign": ("dataclass",),
    "PR2 exact campaign.ExactCampaign.artifact_hashes": ("property",),
    "PR2 exact campaign.ExactCampaign.campaign_hours": ("property",),
    "PR2 exact campaign.ExactCampaign.load_or_create": ("classmethod",),
    "PR2 exact campaign.ExactCampaign.proposal_ready_marker_path": ("property",),
    "PR2 exact campaign.ExactCampaign.reset_reason": ("property",),
    "PR2 exact campaign._checkpoint_write_lock": ("contextmanager",),
    "PR2 L0 micro-verifier.L0MicroVerdict": ("dataclass(frozen=True)",),
    "PR2 L0 micro-verifier.L0SupervisorSealRequest": ("dataclass(frozen=True)",),
    "PR2 L0 micro-verifier._checkpoint_write_lock_l0": ("contextmanager",),
}

_PR2_CLOSE_KERNEL_IMPORT_CLOSURE_ROOT_REL_PATHS: tuple[str, ...] = (
    "src/search/exact_campaign.py",
    "src/search/pr2_l0_micro_verifier_core.py",
    "src/search/pr2_l0_true_verifier_child.py",
)

_PR2_IMPORT_TIME_DYNAMIC_CALL_NAMES = frozenset(
    {
        "globals",
        "locals",
        "vars",
        "setattr",
        "delattr",
        "object.__setattr__",
        "type.__setattr__",
        "exec",
        "eval",
        "compile",
        "__import__",
        "importlib.import_module",
    }
)

_PR2_IMPORT_TIME_DYNAMIC_IMPORT_ATTRS = frozenset({"__import__", "import_module"})

_PR2_DYNAMIC_NAMESPACE_MUTATOR_METHODS = frozenset(
    {
        "__delitem__",
        "__ior__",
        "__setitem__",
        "append",
        "clear",
        "extend",
        "insert",
        "pop",
        "popitem",
        "remove",
        "setdefault",
        "update",
    }
)

_PR2_IMPORT_TIME_NAMESPACE_MUTATOR_CALL_NAMES = frozenset(
    {
        "delattr",
        "dict.__delitem__",
        "dict.__ior__",
        "dict.__setitem__",
        "dict.clear",
        "dict.pop",
        "dict.popitem",
        "dict.setdefault",
        "dict.update",
        "object.__setattr__",
        "operator.delitem",
        "operator.ior",
        "operator.setitem",
        "setattr",
        "type.__setattr__",
    }
)


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _function_default_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    return [
        *function.decorator_list,
        *function.args.defaults,
        *[node for node in function.args.kw_defaults if node is not None],
    ]


def _expr_is_sys_modules_ref(node: ast.AST, *, sys_aliases: set[str] | None = None) -> bool:
    aliases = sys_aliases or {"sys"}
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "modules"
        and isinstance(node.value, ast.Name)
        and node.value.id in aliases
    )


def _expr_is_sys_meta_path_ref(node: ast.AST, *, sys_aliases: set[str] | None = None) -> bool:
    aliases = sys_aliases or {"sys"}
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "meta_path"
        and isinstance(node.value, ast.Name)
        and node.value.id in aliases
    )


def _expr_is_importlib_module_ref(
    node: ast.AST,
    *,
    importlib_aliases: set[str] | None = None,
) -> bool:
    aliases = importlib_aliases or {"importlib"}
    return isinstance(node, ast.Name) and node.id in aliases


def _expr_dynamic_namespace_call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    call_name = _call_func_name(node)
    if call_name in {"globals", "locals"} and not node.args and not node.keywords:
        return call_name
    if call_name == "vars" and not node.keywords:
        return call_name
    return None


def _expr_import_time_namespace_reason(
    node: ast.AST,
    *,
    sys_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
) -> str | None:
    aliases = namespace_aliases or set()
    if isinstance(node, ast.Name):
        if node.id == "__builtins__":
            return "__builtins__"
        if node.id in aliases:
            return node.id
    dynamic_namespace = _expr_dynamic_namespace_call_name(node)
    if dynamic_namespace is not None:
        return f"{dynamic_namespace}()"
    if _expr_is_sys_modules_ref(node, sys_aliases=sys_aliases):
        return "sys.modules"
    if _expr_is_sys_meta_path_ref(node, sys_aliases=sys_aliases):
        return "sys.meta_path"
    if isinstance(node, ast.Attribute):
        if node.attr == "__dict__":
            return "__dict__"
        return _expr_import_time_namespace_reason(
            node.value,
            sys_aliases=sys_aliases,
            namespace_aliases=namespace_aliases,
        )
    if isinstance(node, ast.Subscript):
        return _expr_import_time_namespace_reason(
            node.value,
            sys_aliases=sys_aliases,
            namespace_aliases=namespace_aliases,
        )
    return None


def _expr_is_module_namespace_object(
    node: ast.AST,
    *,
    sys_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
    importlib_aliases: set[str] | None = None,
) -> bool:
    if _expr_import_time_namespace_reason(
        node,
        sys_aliases=sys_aliases,
        namespace_aliases=namespace_aliases,
    ):
        return True
    if isinstance(node, ast.Subscript) and _expr_is_sys_modules_ref(
        node.value,
        sys_aliases=sys_aliases,
    ):
        return True
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        value = node.value
        if isinstance(value, ast.Subscript) and _expr_is_sys_modules_ref(
            value.value,
            sys_aliases=sys_aliases,
        ):
            return True
        if (
            isinstance(value, ast.Call)
            and _call_func_name(value) in {"importlib.import_module", "__import__"}
        ):
            return True
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr in _PR2_IMPORT_TIME_DYNAMIC_IMPORT_ATTRS
            and _expr_is_importlib_module_ref(
                value.func.value,
                importlib_aliases=importlib_aliases,
            )
        ):
            return True
    return False


def _call_import_time_namespace_write_reasons(
    call: ast.Call,
    *,
    sys_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
) -> set[str]:
    reasons: set[str] = set()
    call_name = _call_func_name(call)
    if call_name in _PR2_IMPORT_TIME_NAMESPACE_MUTATOR_CALL_NAMES and call.args:
        reason = _expr_import_time_namespace_reason(
            call.args[0],
            sys_aliases=sys_aliases,
            namespace_aliases=namespace_aliases,
        )
        if reason is not None:
            reasons.add(reason)
    if isinstance(call.func, ast.Attribute):
        if call.func.attr in _PR2_DYNAMIC_NAMESPACE_MUTATOR_METHODS:
            receiver_reason = _expr_import_time_namespace_reason(
                call.func.value,
                sys_aliases=sys_aliases,
                namespace_aliases=namespace_aliases,
            )
            if receiver_reason is not None:
                reasons.add(receiver_reason)
            elif call.args:
                arg_reason = _expr_import_time_namespace_reason(
                    call.args[0],
                    sys_aliases=sys_aliases,
                    namespace_aliases=namespace_aliases,
                )
                if arg_reason is not None:
                    reasons.add(arg_reason)
    if isinstance(call.func, ast.Call) and _call_func_name(call.func) == "getattr":
        getattr_call = call.func
        if getattr_call.args:
            receiver_reason = _expr_import_time_namespace_reason(
                getattr_call.args[0],
                sys_aliases=sys_aliases,
                namespace_aliases=namespace_aliases,
            )
            if receiver_reason is not None:
                if len(getattr_call.args) < 2 or not isinstance(getattr_call.args[1], ast.Constant):
                    reasons.add(receiver_reason)
                elif getattr_call.args[1].value in _PR2_DYNAMIC_NAMESPACE_MUTATOR_METHODS:
                    reasons.add(receiver_reason)
    return reasons


def _call_is_dynamic_namespace_mutator(call: ast.Call) -> bool:
    if _call_import_time_namespace_write_reasons(call):
        return True
    return False


def _call_is_import_time_dynamic(call: ast.Call) -> bool:
    return (
        (_call_func_name(call) in _PR2_IMPORT_TIME_DYNAMIC_CALL_NAMES)
        or _call_is_dynamic_namespace_mutator(call)
    )


def _expr_dynamic_execution_reasons(node: ast.AST) -> list[str]:
    reasons: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _call_is_import_time_dynamic(child):
            reasons.append(_call_func_name(child) or ast.unparse(child.func))
    return reasons


def _target_module_namespace_writes(
    target: ast.AST,
    *,
    sys_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
) -> set[str]:
    namespaces: set[str] = set()
    for node in ast.walk(target):
        reason = _expr_import_time_namespace_reason(
            node,
            sys_aliases=sys_aliases,
            namespace_aliases=namespace_aliases,
        )
        if reason is not None:
            namespaces.add(reason)
    return namespaces


def _stmt_dynamic_namespace_writes(
    stmt: ast.stmt,
    *,
    sys_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
) -> list[str]:
    targets: list[ast.AST] = []
    if isinstance(stmt, ast.Assign):
        targets.extend(stmt.targets)
    elif isinstance(stmt, ast.AnnAssign):
        targets.append(stmt.target)
    elif isinstance(stmt, ast.AugAssign):
        targets.append(stmt.target)
    elif isinstance(stmt, ast.Delete):
        targets.extend(stmt.targets)
    namespaces: list[str] = []
    for target in targets:
        namespaces.extend(sorted(_target_dynamic_namespace_writes(target)))
        namespaces.extend(
            sorted(
                _target_module_namespace_writes(
                    target,
                    sys_aliases=sys_aliases,
                    namespace_aliases=namespace_aliases,
                )
            )
        )
    return namespaces


def _first_party_module_to_rel_path(module: str, *, project_root: Path) -> str | None:
    if not (module == "src" or module.startswith("src.")):
        return None
    module_path = Path(*module.split("."))
    file_path = project_root / module_path.with_suffix(".py")
    if file_path.is_file():
        return file_path.relative_to(project_root).as_posix()
    package_path = project_root / module_path / "__init__.py"
    if package_path.is_file():
        return package_path.relative_to(project_root).as_posix()
    return None


def _module_name_for_rel_path(rel_path: str) -> str:
    parts = Path(rel_path).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_import_from_base_module(stmt: ast.ImportFrom, *, current_rel_path: str) -> str | None:
    module = stmt.module or ""
    if stmt.level == 0:
        return module
    current_module_parts = _module_name_for_rel_path(current_rel_path).split(".")
    package_parts = current_module_parts[:-1]
    if stmt.level > len(package_parts) + 1:
        return None
    base_parts = package_parts[: len(package_parts) - stmt.level + 1]
    if module:
        base_parts.extend(module.split("."))
    return ".".join(part for part in base_parts if part)


def _first_party_import_modules_from_stmt(
    stmt: ast.stmt,
    *,
    current_rel_path: str,
    project_root: Path,
) -> set[str]:
    modules: set[str] = set()
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            name = alias.name
            if _first_party_module_to_rel_path(name, project_root=project_root) is not None:
                modules.add(name)
        return modules
    if not isinstance(stmt, ast.ImportFrom):
        return modules
    base_module = _resolve_import_from_base_module(stmt, current_rel_path=current_rel_path)
    if not base_module:
        return modules
    if _first_party_module_to_rel_path(base_module, project_root=project_root) is not None:
        modules.add(base_module)
    if base_module == "src" or base_module.startswith("src."):
        for alias in stmt.names:
            if alias.name == "*":
                continue
            candidate = f"{base_module}.{alias.name}"
            if _first_party_module_to_rel_path(candidate, project_root=project_root) is not None:
                modules.add(candidate)
    return modules


def _iter_import_time_child_statements(stmt: ast.stmt) -> Iterator[ast.stmt]:
    if isinstance(stmt, ast.If):
        yield from stmt.body
        yield from stmt.orelse
    elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        yield from stmt.body
        yield from stmt.orelse
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        yield from stmt.body
    elif isinstance(stmt, ast.Try):
        yield from stmt.body
        yield from stmt.orelse
        yield from stmt.finalbody
        for handler in stmt.handlers:
            yield from handler.body
    elif isinstance(stmt, ast.Match):
        for case in stmt.cases:
            yield from case.body
    elif isinstance(stmt, ast.ClassDef):
        yield from stmt.body


def _first_party_import_time_modules(
    tree: ast.Module,
    *,
    current_rel_path: str,
    project_root: Path,
) -> set[str]:
    modules: set[str] = set()
    for stmt in ast.walk(tree):
        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        modules.update(
            _first_party_import_modules_from_stmt(
                stmt,
                current_rel_path=current_rel_path,
                project_root=project_root,
            )
        )
    return modules


def _close_kernel_import_time_closure_source_paths(
    *,
    project_root: Path = PROJECT_ROOT,
    roots: Sequence[str] = _PR2_CLOSE_KERNEL_IMPORT_CLOSURE_ROOT_REL_PATHS,
) -> tuple[str, ...]:
    closure: set[str] = set()
    stack = list(reversed(tuple(roots)))
    while stack:
        rel_path = stack.pop().replace("\\", "/")
        if rel_path in closure:
            continue
        path = project_root / rel_path
        if not path.is_file():
            raise CheckError(f"close-kernel import-time closure file missing: {rel_path}")
        closure.add(rel_path)
        tree = _parse_python(path)
        for module in sorted(
            _first_party_import_time_modules(
                tree,
                current_rel_path=rel_path,
                project_root=project_root,
            )
        ):
            imported_rel_path = _first_party_module_to_rel_path(
                module,
                project_root=project_root,
            )
            if imported_rel_path is not None and imported_rel_path not in closure:
                stack.append(imported_rel_path)
    return tuple(sorted(closure))


def _direct_simple_call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            names.add(child.func.id)
    return names


def _dynamic_import_reference_reasons(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    dynamic_import_aliases: set[str],
) -> set[str]:
    reasons: set[str] = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Name)
            and isinstance(child.ctx, ast.Load)
            and child.id in dynamic_import_aliases
        ):
            reasons.add(child.id)
        elif (
            isinstance(child, ast.Attribute)
            and child.attr in _PR2_IMPORT_TIME_DYNAMIC_IMPORT_ATTRS
            and _expr_is_importlib_module_ref(
                child.value,
                importlib_aliases=importlib_aliases,
            )
        ):
            reasons.add(f"{ast.unparse(child.value)}.{child.attr}")
        elif isinstance(child, ast.Call) and _call_func_name(child) == "getattr":
            if not child.args or not _expr_is_importlib_module_ref(
                child.args[0],
                importlib_aliases=importlib_aliases,
            ):
                continue
            if len(child.args) < 2 or not isinstance(child.args[1], ast.Constant):
                reasons.add(f"getattr({ast.unparse(child.args[0])}, <dynamic>)")
            elif child.args[1].value in _PR2_IMPORT_TIME_DYNAMIC_IMPORT_ATTRS:
                reasons.add(f"getattr({ast.unparse(child.args[0])}, {child.args[1].value!r})")
    return reasons


def _bind_import_time_aliases_from_import(
    stmt: ast.Import | ast.ImportFrom,
    *,
    importlib_aliases: set[str],
    sys_aliases: set[str],
    dynamic_import_aliases: set[str],
    namespace_aliases: set[str],
) -> list[str]:
    errors: list[str] = []
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            bound_name = alias.asname or alias.name.split(".", 1)[0]
            if alias.name == "sys":
                sys_aliases.add(bound_name)
            if alias.name == "importlib":
                importlib_aliases.add(bound_name)
            if alias.name in {"importlib.import_module", "importlib.__import__"}:
                dynamic_import_aliases.add(bound_name)
                errors.append(
                    "import-time code must not bind dynamic import primitive "
                    f"{alias.name} as {bound_name}"
                )
        return errors
    module = stmt.module or ""
    if module == "sys":
        for alias in stmt.names:
            bound_name = alias.asname or alias.name
            if alias.name == "modules":
                namespace_aliases.add(bound_name)
            elif alias.name == "meta_path":
                namespace_aliases.add(bound_name)
    if module in {"builtins", "__builtin__"}:
        for alias in stmt.names:
            if alias.name == "__import__":
                bound_name = alias.asname or alias.name
                dynamic_import_aliases.add(bound_name)
                errors.append(
                    "import-time code must not bind dynamic import primitive "
                    f"{module}.{alias.name} as {bound_name}"
                )
    if module == "importlib":
        for alias in stmt.names:
            if alias.name == "*":
                errors.append("import-time code must not star-import importlib")
                continue
            bound_name = alias.asname or alias.name
            if alias.name in _PR2_IMPORT_TIME_DYNAMIC_IMPORT_ATTRS:
                dynamic_import_aliases.add(bound_name)
                errors.append(
                    "import-time code must not bind dynamic import primitive "
                    f"importlib.{alias.name} as {bound_name}"
                )
            elif alias.name == "importlib":
                importlib_aliases.add(bound_name)
    return errors


def _bind_import_time_aliases_from_assignment(
    stmt: ast.Assign | ast.AnnAssign | ast.NamedExpr,
    *,
    importlib_aliases: set[str],
    sys_aliases: set[str],
    dynamic_import_aliases: set[str],
    namespace_aliases: set[str],
) -> None:
    if isinstance(stmt, ast.Assign):
        value = stmt.value
        targets = stmt.targets
    else:
        value = stmt.value
        targets = [stmt.target]
    bound_names: set[str] = set()
    for target in targets:
        bound_names.update(_target_bound_names(target))
    if not bound_names:
        return
    if _expr_is_importlib_module_ref(value, importlib_aliases=importlib_aliases):
        importlib_aliases.update(bound_names)
    if isinstance(value, ast.Name) and value.id in sys_aliases:
        sys_aliases.update(bound_names)
    if _dynamic_import_reference_reasons(
        value,
        importlib_aliases=importlib_aliases,
        dynamic_import_aliases=dynamic_import_aliases,
    ):
        dynamic_import_aliases.update(bound_names)
    if _expr_import_time_namespace_reason(
        value,
        sys_aliases=sys_aliases,
        namespace_aliases=namespace_aliases,
    ):
        namespace_aliases.update(bound_names)


def _check_import_time_expression(
    node: ast.AST,
    *,
    label: str,
    local_functions: Mapping[str, ast.FunctionDef] | None = None,
    seen: set[str] | None = None,
    importlib_aliases: set[str] | None = None,
    sys_aliases: set[str] | None = None,
    dynamic_import_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if importlib_aliases is None:
        importlib_aliases = {"importlib"}
    if sys_aliases is None:
        sys_aliases = {"sys"}
    if dynamic_import_aliases is None:
        dynamic_import_aliases = {"__import__"}
    if namespace_aliases is None:
        namespace_aliases = set()
    for reason in sorted(
        _dynamic_import_reference_reasons(
            node,
            importlib_aliases=importlib_aliases,
            dynamic_import_aliases=dynamic_import_aliases,
        )
    ):
        errors.append(f"{label} must not reference dynamic import primitive {reason}")
    for call_name in sorted(set(_expr_dynamic_execution_reasons(node))):
        errors.append(f"{label} must not execute dynamic import-time call {call_name}")
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        for reason in sorted(
            _call_import_time_namespace_write_reasons(
                child,
                sys_aliases=sys_aliases,
                namespace_aliases=namespace_aliases,
            )
        ):
            errors.append(f"{label} must not write through {reason} at import/def time")
    if local_functions is None:
        return errors
    if seen is None:
        seen = set()
    for call_name in sorted(_direct_simple_call_names(node)):
        function = local_functions.get(call_name)
        if function is None or call_name in seen:
            continue
        seen.add(call_name)
        helper_importlib_aliases = set(importlib_aliases)
        helper_sys_aliases = set(sys_aliases)
        helper_dynamic_import_aliases = set(dynamic_import_aliases)
        helper_namespace_aliases = set(namespace_aliases)
        for stmt in function.body:
            errors.extend(
                _check_import_time_statement(
                    stmt,
                    label=f"{label}->{call_name}",
                    local_functions=local_functions,
                    seen=seen,
                    importlib_aliases=helper_importlib_aliases,
                    sys_aliases=helper_sys_aliases,
                    dynamic_import_aliases=helper_dynamic_import_aliases,
                    namespace_aliases=helper_namespace_aliases,
                )
            )
    return errors


def _check_import_time_statement(
    stmt: ast.stmt,
    *,
    label: str,
    local_functions: Mapping[str, ast.FunctionDef] | None = None,
    seen: set[str] | None = None,
    importlib_aliases: set[str] | None = None,
    sys_aliases: set[str] | None = None,
    dynamic_import_aliases: set[str] | None = None,
    namespace_aliases: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if importlib_aliases is None:
        importlib_aliases = {"importlib"}
    if sys_aliases is None:
        sys_aliases = {"sys"}
    if dynamic_import_aliases is None:
        dynamic_import_aliases = {"__import__"}
    if namespace_aliases is None:
        namespace_aliases = set()

    def check_expr(node: ast.AST) -> list[str]:
        return _check_import_time_expression(
            node,
            label=label,
            local_functions=local_functions,
            seen=seen,
            importlib_aliases=importlib_aliases,
            sys_aliases=sys_aliases,
            dynamic_import_aliases=dynamic_import_aliases,
            namespace_aliases=namespace_aliases,
        )

    def check_stmt(node: ast.stmt) -> list[str]:
        return _check_import_time_statement(
            node,
            label=label,
            local_functions=local_functions,
            seen=seen,
            importlib_aliases=importlib_aliases,
            sys_aliases=sys_aliases,
            dynamic_import_aliases=dynamic_import_aliases,
            namespace_aliases=namespace_aliases,
        )

    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return _bind_import_time_aliases_from_import(
            stmt,
            importlib_aliases=importlib_aliases,
            sys_aliases=sys_aliases,
            dynamic_import_aliases=dynamic_import_aliases,
            namespace_aliases=namespace_aliases,
        )

    for namespace in _stmt_dynamic_namespace_writes(
        stmt,
        sys_aliases=sys_aliases,
        namespace_aliases=namespace_aliases,
    ):
        suffix = "()" if namespace in {"globals", "locals", "vars"} else ""
        errors.append(f"{label} must not write through {namespace}{suffix} at import/def time")
    if isinstance(stmt, ast.Expr):
        errors.extend(check_expr(stmt.value))
    elif isinstance(stmt, ast.Assign):
        errors.extend(check_expr(stmt.value))
        _bind_import_time_aliases_from_assignment(
            stmt,
            importlib_aliases=importlib_aliases,
            sys_aliases=sys_aliases,
            dynamic_import_aliases=dynamic_import_aliases,
            namespace_aliases=namespace_aliases,
        )
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        errors.extend(check_expr(stmt.value))
        _bind_import_time_aliases_from_assignment(
            stmt,
            importlib_aliases=importlib_aliases,
            sys_aliases=sys_aliases,
            dynamic_import_aliases=dynamic_import_aliases,
            namespace_aliases=namespace_aliases,
        )
    elif isinstance(stmt, ast.AugAssign):
        errors.extend(check_expr(stmt.value))
    elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for node in _function_default_nodes(stmt):
            errors.extend(check_expr(node))
    elif isinstance(stmt, ast.ClassDef):
        for node in [*stmt.decorator_list, *stmt.bases, *[kw.value for kw in stmt.keywords]]:
            errors.extend(check_expr(node))
        for item in stmt.body:
            if _is_docstring_stmt(item):
                continue
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for node in _function_default_nodes(item):
                    errors.extend(check_expr(node))
            else:
                errors.extend(check_stmt(item))
    elif isinstance(stmt, ast.Return) and stmt.value is not None:
        errors.extend(check_expr(stmt.value))
    elif isinstance(stmt, ast.If):
        errors.extend(check_expr(stmt.test))
        for item in [*stmt.body, *stmt.orelse]:
            errors.extend(check_stmt(item))
    elif isinstance(stmt, ast.While):
        errors.extend(check_expr(stmt.test))
        for item in [*stmt.body, *stmt.orelse]:
            errors.extend(check_stmt(item))
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        errors.extend(check_expr(stmt.iter))
        for item in [*stmt.body, *stmt.orelse]:
            errors.extend(check_stmt(item))
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        for item in stmt.items:
            errors.extend(check_expr(item.context_expr))
            if item.optional_vars is not None:
                for namespace in _target_dynamic_namespace_writes(item.optional_vars):
                    errors.append(f"{label} must not write through {namespace}() at import/def time")
        for item in stmt.body:
            errors.extend(check_stmt(item))
    elif isinstance(stmt, ast.Try):
        for item in [*stmt.body, *stmt.orelse, *stmt.finalbody]:
            errors.extend(check_stmt(item))
        for handler in stmt.handlers:
            if handler.type is not None:
                errors.extend(check_expr(handler.type))
            for item in handler.body:
                errors.extend(check_stmt(item))
    elif isinstance(stmt, ast.Match):
        errors.extend(check_expr(stmt.subject))
        for case in stmt.cases:
            if case.guard is not None:
                errors.extend(check_expr(case.guard))
            for item in case.body:
                errors.extend(check_stmt(item))
    return errors


def _runtime_import_bound_names(stmt: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
        return set()
    return _import_bound_names(stmt)


def _non_dunder_builtin_names() -> frozenset[str]:
    return frozenset(
        name
        for name in dir(builtins)
        if not (name.startswith("__") and name.endswith("__"))
    )


def _forbidden_shadow_names(import_bound_names: set[str]) -> frozenset[str]:
    return frozenset(import_bound_names) | _non_dunder_builtin_names()


def _decorator_sources(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[str, ...]:
    return tuple(ast.unparse(decorator) for decorator in node.decorator_list)


def _check_close_kernel_decorator_sources(
    label: str,
    qualified_name: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> list[str]:
    key = f"{label}.{qualified_name}"
    expected = _PR2_CLOSE_KERNEL_DECORATOR_SOURCES.get(key, ())
    actual = _decorator_sources(node)
    if actual != expected:
        return [f"{key} decorators drifted: expected {expected!r}, found {actual!r}"]
    return []


def _expr_loads_any_name(node: ast.AST, names: set[str] | frozenset[str]) -> set[str]:
    loaded: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_Name(self, child: ast.Name) -> None:
            if isinstance(child.ctx, ast.Load) and child.id in names:
                loaded.add(child.id)

    Visitor().visit(node)
    return loaded


def _stmt_def_time_nodes(stmt: ast.stmt) -> list[ast.AST]:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _function_def_time_nodes(stmt)
    if isinstance(stmt, ast.ClassDef):
        return _class_def_time_nodes(stmt)
    if isinstance(stmt, ast.Assign):
        return [stmt.value]
    if isinstance(stmt, ast.AnnAssign):
        nodes: list[ast.AST] = [stmt.annotation]
        if stmt.value is not None:
            nodes.append(stmt.value)
        return nodes
    return []


def _check_class_def_time_local_resolution(
    item: ast.stmt,
    *,
    label: str,
    class_bound_names: set[str],
) -> list[str]:
    errors: list[str] = []
    if not class_bound_names:
        return errors
    for node in _stmt_def_time_nodes(item):
        for name in sorted(_expr_loads_any_name(node, class_bound_names)):
            errors.append(
                f"{label} def-time expression must not resolve to prior class local {name}"
            )
    return errors


def _check_close_kernel_class_def_time_shape(
    class_node: ast.ClassDef,
    *,
    label: str,
    local_functions: Mapping[str, ast.FunctionDef],
) -> list[str]:
    errors: list[str] = []
    expected_shape = _PR2_CLOSE_KERNEL_CLASS_DEF_SHAPES.get(label)
    actual_bases = tuple(ast.unparse(base) for base in class_node.bases)
    actual_keywords = tuple(f"{kw.arg}={ast.unparse(kw.value)}" for kw in class_node.keywords)
    if expected_shape is None:
        errors.append(f"{label} class def-time base/keyword allowlist missing")
    elif (actual_bases, actual_keywords) != expected_shape:
        errors.append(
            f"{label} def-time bases/keywords drifted: expected {expected_shape!r}, "
            f"found {(actual_bases, actual_keywords)!r}"
        )
    for node in [*class_node.decorator_list, *class_node.bases, *[kw.value for kw in class_node.keywords]]:
        errors.extend(
            _check_import_time_expression(
                node,
                label=f"{label} class def-time shape",
                local_functions=local_functions,
            )
        )
    return errors


def _class_field_value(stmt: ast.Assign | ast.AnnAssign) -> ast.AST | None:
    if isinstance(stmt, ast.Assign):
        return stmt.value
    return stmt.value


def _class_runtime_member_layout(class_node: ast.ClassDef) -> tuple[tuple[str, str], ...]:
    members: list[tuple[str, str]] = []
    for index, item in enumerate(class_node.body):
        if index == 0 and _is_docstring_stmt(item):
            continue
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            members.append(("method", item.name))
        elif isinstance(item, ast.ClassDef):
            members.append(("class", item.name))
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    members.append(("field", target.id))
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            members.append(("field", item.target.id))
    return tuple(members)


def _close_kernel_protected_runtime_member_names(
    label: str,
    prefix: str,
) -> frozenset[str]:
    layout = _PR2_CLOSE_KERNEL_CLASS_RUNTIME_MEMBER_LAYOUTS.get(f"{label}.{prefix}", ())
    method_names = {name for kind, name in layout if kind in {"method", "class"}}
    return frozenset(method_names) | _PR2_CLOSE_KERNEL_FORBIDDEN_CLASS_RUNTIME_HOOKS


def _target_writes_close_kernel_instance_dict(target: ast.AST) -> bool:
    for node in ast.walk(target):
        if isinstance(node, ast.Attribute) and node.attr == "__dict__":
            return True
        if isinstance(node, ast.Call) and _call_func_name(node) == "vars":
            return True
    return False


def _target_writes_close_kernel_protected_member(
    target: ast.AST,
    protected_names: frozenset[str],
) -> str | None:
    for node in ast.walk(target):
        if isinstance(node, ast.Attribute) and node.attr in protected_names:
            return node.attr
    return None


def _call_writes_close_kernel_runtime_member(
    call: ast.Call,
    protected_names: frozenset[str],
) -> str | None:
    call_name = _call_func_name(call)
    if call_name in {"setattr", "delattr"}:
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            return str(call.args[1].value)
        return "<dynamic>"
    if call_name in {"object.__setattr__", "object.__delattr__", "type.__setattr__"}:
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            return str(call.args[1].value)
        return "<dynamic>"
    if isinstance(call.func, ast.Attribute) and call.func.attr in {"__setattr__", "__delattr__"}:
        return call.func.attr
    if isinstance(call.func, ast.Attribute) and call.func.attr in {"__setitem__", "update"}:
        if _target_writes_close_kernel_instance_dict(call.func.value):
            return "__dict__"
    for arg in call.args:
        if _target_writes_close_kernel_instance_dict(arg):
            return "__dict__"
    for keyword in call.keywords:
        if _target_writes_close_kernel_instance_dict(keyword.value):
            return "__dict__"
    return None


_PR2_CLOSE_KERNEL_RUNTIME_REFLECTION_NAME_PRIMITIVES = frozenset(
    {
        "__import__",
        "compile",
        "ctypes",
        "delattr",
        "eval",
        "exec",
        "gc",
        "globals",
        "inspect",
        "locals",
        "setattr",
        "vars",
        "_current_frames",
        "_getframe",
        "currentframe",
        "get_objects",
        "get_referrers",
        "stack",
        "trace",
    }
)
_PR2_CLOSE_KERNEL_RUNTIME_REFLECTION_ATTR_PRIMITIVES = frozenset(
    {
        "__bases__",
        "__class__",
        "__closure__",
        "__code__",
        "__defaults__",
        "__delattr__",
        "__dict__",
        "__func__",
        "__getattr__",
        "__getattribute__",
        "__globals__",
        "__init_subclass__",
        "__kwdefaults__",
        "__mro__",
        "__self__",
        "__set_name__",
        "__setattr__",
        "__subclasses__",
        "__wrapped__",
    }
)
_PR2_CLOSE_KERNEL_RUNTIME_DYNAMIC_MODULE_PRIMITIVES = frozenset({"ctypes", "gc", "inspect"})
_PR2_CLOSE_KERNEL_RUNTIME_SYS_FRAME_PRIMITIVES = frozenset(
    {"_current_frames", "_getframe"}
)


def _is_dunder_string(value: str) -> bool:
    return value.startswith("__") and value.endswith("__")


def _getattr_call_runtime_reflection_violation(call: ast.Call) -> str | None:
    if _call_func_name(call) != "getattr":
        return None
    if len(call.args) < 2:
        return "getattr dynamic member name"
    member_name = _literal_string_value(call.args[1])
    if member_name is None:
        return "getattr dynamic member name"
    if _is_dunder_string(member_name):
        return f"getattr dunder member {member_name}"
    return None


def _name_is_allowed_getattr_call_func(node: ast.Name) -> bool:
    parent = _p1_2_parent(node)
    return (
        node.id == "getattr"
        and isinstance(parent, ast.Call)
        and parent.func is node
        and _getattr_call_runtime_reflection_violation(parent) is None
    )


def _attribute_path_name(node: ast.Attribute) -> str | None:
    parts = [node.attr]
    value = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
        return ".".join(reversed(parts))
    return None


def _close_kernel_runtime_import_reflection_primitive(
    node: ast.Import | ast.ImportFrom,
) -> str | None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            root = alias.name.split(".", 1)[0]
            if root in _PR2_CLOSE_KERNEL_RUNTIME_DYNAMIC_MODULE_PRIMITIVES:
                return root
        return None
    module = (node.module or "").split(".", 1)[0]
    if module in _PR2_CLOSE_KERNEL_RUNTIME_DYNAMIC_MODULE_PRIMITIVES:
        return module
    if module == "sys":
        for alias in node.names:
            if alias.name in _PR2_CLOSE_KERNEL_RUNTIME_SYS_FRAME_PRIMITIVES:
                return f"sys.{alias.name}"
    return None


def _close_kernel_runtime_reflection_primitive(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _close_kernel_runtime_import_reflection_primitive(node)
    if isinstance(node, ast.Call):
        getattr_violation = _getattr_call_runtime_reflection_violation(node)
        if getattr_violation is not None:
            return getattr_violation
        call_name = _call_func_name(node)
        if call_name in _PR2_ACCUMULATOR_CALLEE_FRAME_CALLS:
            return call_name
    if isinstance(node, ast.Name):
        if _name_is_allowed_getattr_call_func(node):
            return None
        if node.id == "getattr":
            return "getattr"
        if node.id in _PR2_CLOSE_KERNEL_RUNTIME_REFLECTION_NAME_PRIMITIVES:
            return node.id
    if isinstance(node, ast.Attribute):
        attr_path = _attribute_path_name(node)
        if attr_path in _PR2_ACCUMULATOR_CALLEE_FRAME_CALLS:
            return attr_path
        if (
            attr_path is not None
            and attr_path.split(".", 1)[0]
            in _PR2_CLOSE_KERNEL_RUNTIME_DYNAMIC_MODULE_PRIMITIVES
        ):
            return attr_path
        if (
            attr_path is not None
            and attr_path.startswith("sys.")
            and node.attr in _PR2_CLOSE_KERNEL_RUNTIME_SYS_FRAME_PRIMITIVES
        ):
            return attr_path
        if node.attr in _PR2_ACCUMULATOR_CALLEE_FRAME_ATTRS:
            return node.attr
        if node.attr in _PR2_CLOSE_KERNEL_RUNTIME_REFLECTION_ATTR_PRIMITIVES:
            return node.attr
        if isinstance(node.value, ast.Name) and node.value.id in {"object", "type"} and node.attr in {
            "__setattr__",
            "__delattr__",
            "__getattribute__",
        }:
            return f"{node.value.id}.{node.attr}"
    return None


def _allowed_close_kernel_compile_call(
    label: str,
    prefix: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    node: ast.AST,
) -> bool:
    parent = _p1_2_parent(node)
    if not (
        label == "PR2 true verifier child"
        and prefix == "_RehashingSourceFileLoader"
        and function.name == "get_code"
        and isinstance(node, ast.Name)
        and node.id == "compile"
        and isinstance(parent, ast.Call)
        and parent.func is node
        and len(parent.args) == 3
        and isinstance(parent.args[0], ast.Name)
        and parent.args[0].id == "source_bytes"
        and isinstance(parent.args[1], ast.Attribute)
        and parent.args[1].attr == "path"
        and isinstance(parent.args[2], ast.Constant)
        and parent.args[2].value == "exec"
    ):
        return False
    return any(
        keyword.arg == "dont_inherit"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in parent.keywords
    )


def _check_close_kernel_class_runtime_layout(
    label: str,
    prefix: str,
    class_node: ast.ClassDef,
) -> list[str]:
    errors: list[str] = []
    key = f"{label}.{prefix}"
    expected_layout = _PR2_CLOSE_KERNEL_CLASS_RUNTIME_MEMBER_LAYOUTS.get(key)
    actual_layout = _class_runtime_member_layout(class_node)
    if expected_layout is None:
        errors.append(f"{key} class runtime member layout floor missing")
    elif actual_layout != expected_layout:
        errors.append(
            f"{key} class runtime member layout drifted: "
            f"expected {expected_layout!r}, found {actual_layout!r}"
        )
    for kind, name in actual_layout:
        if kind in {"method", "field", "class"} and name in _PR2_CLOSE_KERNEL_FORBIDDEN_CLASS_RUNTIME_HOOKS:
            errors.append(f"{key} class runtime member must not define hook {name}")
    return errors


def _check_close_kernel_runtime_member_writes(
    label: str,
    prefix: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    errors: list[str] = []
    _attach_parent_links(function)
    protected_names = _close_kernel_protected_runtime_member_names(label, prefix)
    for stmt in function.body:
        for node in ast.walk(stmt):
            primitive = _close_kernel_runtime_reflection_primitive(node)
            if primitive == "compile" and _allowed_close_kernel_compile_call(
                label,
                prefix,
                function,
                node,
            ):
                primitive = None
            if primitive is not None:
                errors.append(
                    f"{label}.{prefix}.{function.name} must not reference runtime "
                    f"reflection primitive {primitive}"
                )
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if _target_writes_close_kernel_instance_dict(target):
                        errors.append(
                            f"{label}.{prefix}.{function.name} must not write through instance __dict__"
                        )
                    protected_name = _target_writes_close_kernel_protected_member(
                        target,
                        protected_names,
                    )
                    if protected_name is not None:
                        errors.append(
                            f"{label}.{prefix}.{function.name} must not write runtime member "
                            f"{protected_name}"
                        )
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    if _target_writes_close_kernel_instance_dict(target):
                        errors.append(
                            f"{label}.{prefix}.{function.name} must not delete through instance __dict__"
                        )
                    protected_name = _target_writes_close_kernel_protected_member(
                        target,
                        protected_names,
                    )
                    if protected_name is not None:
                        errors.append(
                            f"{label}.{prefix}.{function.name} must not delete runtime member "
                            f"{protected_name}"
                        )
            elif isinstance(node, ast.Call):
                written_name = _call_writes_close_kernel_runtime_member(node, protected_names)
                if written_name is not None:
                    errors.append(
                        f"{label}.{prefix}.{function.name} must not dynamically write runtime "
                        f"member {written_name}"
                    )
    return errors


def _close_kernel_class_field_value_allowed(value: ast.AST) -> bool:
    if _inert_default_value(value):
        return True
    if not isinstance(value, ast.Call) or _call_func_name(value) != "field" or value.args:
        return False
    for keyword in value.keywords:
        if keyword.arg == "default" and _inert_default_value(keyword.value):
            continue
        if (
            keyword.arg == "default_factory"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id in {"dict", "list", "set", "tuple"}
        ):
            continue
        return False
    return True


def _check_close_kernel_class_body_fully_pinned(
    label: str,
    fmap: Mapping[str, str],
    class_node: ast.ClassDef,
    *,
    prefix: str,
    local_functions: Mapping[str, ast.FunctionDef],
    forbidden_shadow_names: frozenset[str],
) -> list[str]:
    errors: list[str] = []
    errors.extend(_check_close_kernel_class_runtime_layout(label, prefix, class_node))
    seen: dict[str, list[ast.stmt]] = {}
    class_bound_names: set[str] = set()
    actual_fields: list[str] = []
    saw_non_field = False
    for item in class_node.body:
        for bound_name in _class_stmt_bound_names(item):
            seen.setdefault(bound_name, []).append(item)
    for bound_name, bindings in sorted(seen.items()):
        if len(bindings) > 1:
            errors.append(
                f"{label} close-kernel class binding must be unique: "
                f"{prefix}.{bound_name} at lines {_format_binding_lines(bindings)}"
            )

    for index, item in enumerate(class_node.body):
        if index == 0 and _is_docstring_stmt(item):
            continue
        errors.extend(
            _check_class_def_time_local_resolution(
                item,
                label=f"{label}.{prefix}",
                class_bound_names=class_bound_names,
            )
        )
        bound_names = _class_stmt_bound_names(item)
        for bound_name in sorted(_hidden_current_scope_bound_names(item)):
            errors.append(
                f"{label} close-kernel class hidden binding is forbidden: "
                f"{prefix}.{bound_name} at line {getattr(item, 'lineno', '?')}"
            )
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            saw_non_field = True
            key = f"{prefix}.{item.name}"
            errors.extend(_check_close_kernel_decorator_sources(label, key, item))
            errors.extend(_check_close_kernel_runtime_member_writes(label, prefix, item))
            if key not in fmap:
                errors.append(f"{label} close-kernel method not source-pinned: {key}")
            for node in _function_default_nodes(item):
                errors.extend(
                    _check_import_time_expression(
                        node,
                        label=f"{label}.{key}",
                        local_functions=local_functions,
                    )
                )
            class_bound_names.update(bound_names)
            continue
        if isinstance(item, ast.ClassDef):
            saw_non_field = True
            key = f"{prefix}.{item.name}"
            errors.extend(_check_close_kernel_decorator_sources(label, key, item))
            if key not in fmap:
                errors.append(f"{label} close-kernel nested class not source-pinned: {key}")
            errors.extend(
                _check_close_kernel_class_def_time_shape(
                    item,
                    label=f"{label}.{key}",
                    local_functions=local_functions,
                )
            )
            errors.extend(
                _check_close_kernel_class_body_fully_pinned(
                    label,
                    fmap,
                    item,
                    prefix=key,
                    local_functions=local_functions,
                    forbidden_shadow_names=forbidden_shadow_names,
                )
            )
            class_bound_names.update(bound_names)
            continue
        if isinstance(item, (ast.Assign, ast.AnnAssign)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if not isinstance(target, ast.Name):
                    errors.append(
                        f"{label} close-kernel class binding must be a plain name at line "
                        f"{getattr(item, 'lineno', '?')}"
                    )
                    continue
                key = f"{prefix}.{target.id}"
                if key in fmap:
                    errors.append(
                        f"{label} close-kernel class binding shadows source-pinned member: {key}"
                    )
            value = _class_field_value(item)
            if value is not None:
                errors.extend(
                    _check_import_time_expression(
                        value,
                        label=f"{label} class field",
                        local_functions=local_functions,
                    )
                )
                if not _close_kernel_class_field_value_allowed(value):
                    errors.append(
                        f"{label} close-kernel class field default must be inert at line "
                        f"{getattr(item, 'lineno', '?')}"
                    )
            if saw_non_field:
                errors.append(
                    f"{label} close-kernel class {prefix} has an unexpected body "
                    f"{type(item).__name__} at line {getattr(item, 'lineno', '?')}"
                )
            else:
                actual_fields.append(ast.unparse(item))
            class_bound_names.update(bound_names)
            continue
        errors.append(
            f"{label} close-kernel class {prefix} has an unexpected body "
            f"{type(item).__name__} at line {getattr(item, 'lineno', '?')}"
        )
        class_bound_names.update(bound_names)
    expected_fields = _PR2_CLOSE_KERNEL_CLASS_FIELD_SOURCES.get(f"{label}.{prefix}")
    if expected_fields is None:
        errors.append(f"{label}.{prefix} class def-time field layout allowlist missing")
    elif tuple(actual_fields) != expected_fields:
        errors.append(
            f"{label}.{prefix} class def-time field layout drifted: "
            f"expected {expected_fields!r}, found {tuple(actual_fields)!r}"
        )
    return errors


def _check_close_kernel_import_dependency_import_time_shape(
    *,
    project_root: Path = PROJECT_ROOT,
    roots: Sequence[str] = _PR2_CLOSE_KERNEL_IMPORT_CLOSURE_ROOT_REL_PATHS,
) -> list[str]:
    errors: list[str] = []
    try:
        closure_paths = _close_kernel_import_time_closure_source_paths(
            project_root=project_root,
            roots=roots,
        )
    except CheckError as exc:
        return [str(exc)]
    for rel_path in closure_paths:
        path = project_root / rel_path
        tree = _parse_python(path)
        local_functions = {
            stmt.name: stmt
            for stmt in tree.body
            if isinstance(stmt, ast.FunctionDef)
        }
        importlib_aliases = {"importlib"}
        sys_aliases = {"sys"}
        dynamic_import_aliases = {"__import__"}
        namespace_aliases: set[str] = set()
        for index, stmt in enumerate(tree.body):
            if index == 0 and _is_docstring_stmt(stmt):
                continue
            errors.extend(
                _check_import_time_statement(
                    stmt,
                    label=f"{rel_path}:{getattr(stmt, 'lineno', '?')}",
                    local_functions=local_functions,
                    importlib_aliases=importlib_aliases,
                    sys_aliases=sys_aliases,
                    dynamic_import_aliases=dynamic_import_aliases,
                    namespace_aliases=namespace_aliases,
                )
            )
    return errors


def _check_close_kernel_files_fully_pinned(
    l0_tree: ast.Module,
    child_tree: ast.Module,
    exact_tree: ast.Module,
) -> list[str]:
    """Round-10 closure: every def + class + module constant in the 3 close-kernel files
    must be source-pinned, and no other top-level statement form is allowed.

    This makes "did we cover every reachable cert-path helper" structurally impossible to get
    wrong: reachability is moot when *every* function/class/method/constant in the file is
    pinned, and the closed-world top-level check forbids smuggling proof-gutting logic into a
    fresh module-level ``if``/``try``/expression that runs at import. A future symbol added to
    any of these files fails this check until it is pinned. (V99 whole-file floor already
    freezes these files; per-symbol pinning adds no edit friction — it only converts a silent
    re-floor into a visible per-symbol diff in this checker.)
    """
    errors: list[str] = []

    def _imp(*names: tuple[str, str | None]) -> tuple[str, tuple[tuple[str, str | None], ...]]:
        return ("import", names)

    def _from(
        module: str,
        *names: tuple[str, str | None],
    ) -> tuple[str, int, str, tuple[tuple[str, str | None], ...]]:
        return ("from", 0, module, names)

    def _import_signature(
        stmt: ast.Import | ast.ImportFrom,
    ) -> tuple[str, tuple[tuple[str, str | None], ...]] | tuple[
        str, int, str, tuple[tuple[str, str | None], ...]
    ]:
        if isinstance(stmt, ast.Import):
            return _imp(*((alias.name, alias.asname) for alias in stmt.names))
        return (
            "from",
            stmt.level,
            stmt.module or "",
            tuple((alias.name, alias.asname) for alias in stmt.names),
        )

    specs = (
        (
            "PR2 L0 micro-verifier",
            PR2_L0_MICRO_VERIFIER_PATH.name,
            l0_tree,
            _PR2_L0_TCB_FUNCTION_SOURCE_SHA256,
            _PR2_L0_TCB_CONSTANT_SOURCES,
            (
                _from("__future__", ("annotations", None)),
                _imp(("base64", None)),
                _from("contextlib", ("contextmanager", None)),
                _from("dataclasses", ("dataclass", None), ("field", None)),
                _imp(("hashlib", None)),
                _imp(("json", None)),
                _imp(("math", None)),
                _imp(("os", None)),
                _from("pathlib", ("Path", None)),
                _imp(("secrets", None)),
                _imp(("shutil", None)),
                _imp(("subprocess", None)),
                _imp(("sys", None)),
                _imp(("sysconfig", None)),
                _imp(("tempfile", None)),
                _imp(("time", None)),
                _imp(("uuid", None)),
                _from("typing", ("Any", None), ("Mapping", None), ("Sequence", None)),
            ),
        ),
        (
            "PR2 true verifier child",
            PR2_L0_TRUE_VERIFIER_CHILD_PATH.name,
            child_tree,
            _PR2_TRUE_CHILD_TCB_FUNCTION_SOURCE_SHA256,
            _PR2_CHILD_TOP_LEVEL_CONSTANT_SOURCES,
            (
                _from("__future__", ("annotations", None)),
                _imp(("base64", None)),
                _from("collections.abc", ("Iterable", None)),
                _imp(("hashlib", None)),
                _imp(("importlib.machinery", None)),
                _imp(("json", None)),
                _imp(("os", None)),
                _from("pathlib", ("Path", None)),
                _imp(("sys", None)),
                _imp(("sysconfig", None)),
                _imp(("tempfile", None)),
                _imp(("traceback", None)),
                _from("typing", ("Any", None), ("Mapping", None)),
            ),
        ),
        (
            "PR2 exact campaign",
            EXACT_CAMPAIGN_PATH.name,
            exact_tree,
            _PR2_EXACT_TCB_SOURCE_SHA256,
            _PR2_EXACT_TCB_CONSTANT_SOURCES,
            (
                _from("__future__", ("annotations", None)),
                _imp(("calendar", None)),
                _imp(("base64", None)),
                _imp(("hashlib", None)),
                _imp(("json", None)),
                _imp(("math", None)),
                _imp(("os", None)),
                _imp(("string", None)),
                _imp(("tempfile", None)),
                _imp(("time", None)),
                _imp(("uuid", None)),
                _from("contextlib", ("contextmanager", None)),
                _from("dataclasses", ("dataclass", None)),
                _from("pathlib", ("Path", None)),
                _from(
                    "typing",
                    ("Any", None),
                    ("Dict", None),
                    ("Iterator", None),
                    ("Mapping", None),
                    ("Optional", None),
                    ("Sequence", None),
                    ("Tuple", None),
                ),
                _from(
                    "src.models.cut_manager",
                    ("BendersCut", None),
                    ("_parse_ghost_anchor_condition_key", None),
                ),
                _from("src.io.strict_json", ("loads_strict_json", None)),
                _from(
                    "src.models.master_model",
                    ("POSE_LEVEL_OPTIONAL_OPERATIONS", None),
                    ("POSE_LEVEL_OPTIONAL_TEMPLATES", None),
                    ("infer_certified_optional_lower_bounds_for_instances", None),
                    ("load_generic_io_requirements_artifact", None),
                ),
                _from(
                    "src.search.certified_artifact_contract",
                    ("LOCKED_EXACT_ARTIFACT_PATHS", None),
                    ("validate_locked_exact_artifact_contract", None),
                    ("validate_locked_p1_2_close_kernel", None),
                ),
                _from(
                    "src.search.certified_frontier",
                    ("TERMINAL_FRONTIER_OBJECTIVE", None),
                    ("terminal_frontier_evidence_violation", None),
                ),
                _from(
                    "src.search.pr2_l0_artifact_core",
                    ("TERMINAL_FULL_FRONTIER_CERTIFIED_REASON", None),
                    ("compute_exact_artifact_hashes", None),
                    ("terminal_certified_final_result_project_precheck_violation", None),
                ),
                _from(
                    "src.search.candidate_proof_replay",
                    ("CANDIDATE_PROOF_FIELD", None),
                    ("project_candidate_records_for_sink", None),
                ),
                _from(
                    "src.search.terminal_fixed_witness_verifier",
                    ("TERMINAL_FIXED_WITNESS_AUDIT_FIELD", None),
                    ("canonical_state_bytes_for_fixed_witness", None),
                    ("stable_terminal_fixed_witness_verdict_payload", None),
                ),
                _from(
                    "src.search.terminal_fixed_witness_capsule",
                    ("build_terminal_fixed_witness_projection_at_sink", None),
                ),
            ),
        ),
    )
    for label, filename, tree, fmap, cmap, expected_imports in specs:
        special = _PR2_CLOSE_KERNEL_SPECIAL_CONSTANTS[label]
        local_functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        past_import_block = False
        import_bound_names: set[str] = set()
        import_binding_lines: dict[str, int] = {}
        import_index = 0
        for index, stmt in enumerate(tree.body):
            if not isinstance(stmt, (ast.Import, ast.ImportFrom)) and not (
                index == 0 and _is_docstring_stmt(stmt)
            ):
                forbidden_shadow_names = _forbidden_shadow_names(import_bound_names)
                for bound_name in sorted(_hidden_current_scope_bound_names(stmt)):
                    errors.append(
                        f"{label} close-kernel top-level hidden binding is forbidden: "
                        f"{bound_name} at line {getattr(stmt, 'lineno', '?')}"
                    )
                for bound_name in sorted(_current_scope_bound_names(stmt) & forbidden_shadow_names):
                    errors.append(
                        f"{label} close-kernel top-level binding must not shadow "
                        f"import/builtin name {bound_name}"
                    )
            if isinstance(stmt, ast.FunctionDef):
                past_import_block = True
                errors.extend(_check_close_kernel_decorator_sources(label, stmt.name, stmt))
                for expr in _function_default_nodes(stmt):
                    errors.extend(
                        _check_import_time_expression(
                            expr,
                            label=f"{label}.{stmt.name}",
                            local_functions=local_functions,
                        )
                    )
                if stmt.name not in fmap:
                    errors.append(
                        f"{label} close-kernel function not source-pinned: {stmt.name}"
                    )
            elif isinstance(stmt, ast.ClassDef):
                past_import_block = True
                errors.extend(_check_close_kernel_decorator_sources(label, stmt.name, stmt))
                errors.extend(
                    _check_close_kernel_class_def_time_shape(
                        stmt,
                        label=f"{label}.{stmt.name}",
                        local_functions=local_functions,
                    )
                )
                if stmt.name not in fmap:
                    errors.append(
                        f"{label} close-kernel class not source-pinned: {stmt.name}"
                    )
                errors.extend(
                    _check_close_kernel_class_body_fully_pinned(
                        label,
                        fmap,
                        stmt,
                        prefix=stmt.name,
                        local_functions=local_functions,
                        forbidden_shadow_names=_forbidden_shadow_names(import_bound_names),
                    )
                )
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                past_import_block = True
                errors.extend(
                    _check_import_time_statement(
                        stmt,
                        label=f"{label} module constant",
                        local_functions=local_functions,
                    )
                )
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for target in targets:
                    if not isinstance(target, ast.Name):
                        errors.append(
                            f"{label} close-kernel module binding must be a plain name at line "
                            f"{getattr(stmt, 'lineno', '?')}"
                        )
                    elif target.id in special or target.id in cmap:
                        continue
                    else:
                        errors.append(
                            f"{label} close-kernel module constant not pinned: {target.id}"
                        )
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for bound_name in sorted(_runtime_import_bound_names(stmt)):
                    previous_line = import_binding_lines.get(bound_name)
                    if previous_line is not None:
                        errors.append(
                            f"{label} close-kernel import binding must be unique: "
                            f"{bound_name} at lines {previous_line}, {getattr(stmt, 'lineno', '?')}"
                        )
                    import_binding_lines[bound_name] = getattr(stmt, "lineno", -1)
                    import_bound_names.add(bound_name)
                if past_import_block:
                    errors.append(
                        f"tail import after definitions in {filename}: {ast.dump(stmt)}"
                    )
                else:
                    actual_import = _import_signature(stmt)
                    if import_index >= len(expected_imports):
                        errors.append(
                            f"{label} close-kernel import not allowlisted in "
                            f"{filename}: {ast.dump(stmt)}"
                        )
                    elif actual_import != expected_imports[import_index]:
                        errors.append(
                            f"{label} close-kernel import drift in {filename} "
                            f"at import slot {import_index + 1}: {ast.dump(stmt)}"
                        )
                    import_index += 1
                continue
            elif index == 0 and _is_docstring_stmt(stmt):
                continue  # module docstring
            else:
                errors.append(
                    f"{label} close-kernel file has an unexpected top-level "
                    f"{type(stmt).__name__} at line {getattr(stmt, 'lineno', '?')}"
                )
        if import_index != len(expected_imports):
            errors.append(
                f"{label} close-kernel import block incomplete in {filename}: "
                f"expected {len(expected_imports)} import(s), found {import_index}"
            )
    return errors


def _check_single_final_return_none(function: ast.FunctionDef, *, label: str) -> list[str]:
    none_returns = [node for node in ast.walk(function) if _returns_none(node)]
    body = _semantic_body(function)
    if len(none_returns) != 1 or not body or body[-1] is not none_returns[0]:
        return [f"{label} must have return None only as its final top-level statement"]
    return []


def _return_value_is_fail_closed_reason(
    value: ast.AST | None,
    *,
    allowed_names: frozenset[str],
    allowed_calls: frozenset[str] = frozenset(),
) -> bool:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return True
    if isinstance(value, ast.JoinedStr):
        return True
    if isinstance(value, ast.Name) and value.id in allowed_names:
        return True
    if isinstance(value, ast.Call) and (_call_func_name(value) in allowed_calls):
        return True
    return False


def _check_fail_closed_terminal_return_shape(
    function: ast.FunctionDef,
    *,
    label: str,
    allowed_none_returns: Sequence[ast.Return] = (),
    allowed_reason_names: frozenset[str] = frozenset(),
    allowed_reason_calls: frozenset[str] = frozenset(),
) -> list[str]:
    errors: list[str] = []
    body = _semantic_body(function)
    final_none_return = body[-1] if body and _returns_none(body[-1]) else None
    allowed_none_ids = {id(node) for node in allowed_none_returns}
    if final_none_return is not None:
        allowed_none_ids.add(id(final_none_return))
    for node in ast.walk(function):
        if isinstance(node, ast.Raise):
            errors.append(f"{label} must not raise; return a fail-closed reason instead")
        if not isinstance(node, ast.Return):
            continue
        if _returns_none(node):
            if id(node) not in allowed_none_ids:
                errors.append(f"{label} must not return None before its pinned success gate")
            continue
        if not _return_value_is_fail_closed_reason(
            node.value,
            allowed_names=allowed_reason_names,
            allowed_calls=allowed_reason_calls,
        ):
            errors.append(f"{label} must only return canonical fail-closed reasons")
    return errors


def _stmt_contains_return_none(stmt: ast.stmt) -> bool:
    return any(_returns_none(node) for node in ast.walk(stmt))


def _top_level_assignment_index(function: ast.FunctionDef, target_name: str, call_name: str) -> int | None:
    body = _semantic_body(function)
    matches = [
        index
        for index, stmt in enumerate(body)
        if _assigns_name_from_call(stmt, target_name, call_name)
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _direct_function_calls(function: ast.FunctionDef) -> set[str]:
    return {
        call_name
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        for call_name in [_call_func_name(node)]
        if call_name is not None
    }


def _check_required_direct_calls(
    function: ast.FunctionDef,
    required: frozenset[str],
    *,
    label: str,
) -> list[str]:
    calls = _direct_function_calls(function)
    return [
        f"{label} must call {call_name}"
        for call_name in sorted(required)
        if call_name not in calls
    ]


def _check_terminal_final_result_violation_structure(function: ast.FunctionDef) -> list[str]:
    label = "terminal certified final result validator"
    errors: list[str] = []
    body = _semantic_body(function)
    errors.extend(
        _check_required_direct_calls(
            function,
            frozenset(
                {
                    "_candidate_objective_from_rect",
                    "_strict_candidate_ghost_rect",
                    "_terminal_certified_ghost_rect_unknown_field",
                    "_terminal_certified_last_stop_reason_violation",
                    "_terminal_certified_search_stats_violation",
                    "candidate_key",
                    "terminal_frontier_evidence_violation",
                }
            ),
            label=label,
        )
    )
    if not body or not _stmt_matches_source(
        body[0],
        "if not has_terminal_full_frontier_certified_evidence(state):\n    return None",
    ):
        errors.append(
            "terminal certified final result validator must start with only the "
            "frontier-evidence absence return None"
        )
    allowed_none_returns = []
    if body and _stmt_matches_source(
        body[0],
        "if not has_terminal_full_frontier_certified_evidence(state):\n    return None",
    ):
        allowed_none_returns.append(body[0].body[0])
    errors.extend(
        _check_fail_closed_terminal_return_shape(
            function,
            label=label,
            allowed_none_returns=allowed_none_returns,
            allowed_reason_names=frozenset(
                {
                    "frontier_reason",
                    "ghost_rect_unknown_field",
                    "search_stats_reason",
                    "stop_reason",
                }
            ),
        )
    )
    for call_name, result_name in (
        ("_terminal_certified_last_stop_reason_violation", "stop_reason"),
        ("_terminal_certified_search_stats_violation", "search_stats_reason"),
    ):
        errors.extend(
            _check_guard_result_flow(
                function,
                call_name=call_name,
                result_name=result_name,
                effect="return",
                label=label,
            )
        )
    errors.extend(
        _check_result_flow_to_compare_gate(
            function,
            call_name="_candidate_objective_from_rect",
            result_name="final_objective",
            compare_test="_candidate_objective_from_rect(other_w, other_h) > final_objective",
            effect="return",
            label=label,
        )
    )
    frontier_index = _top_level_assignment_index(
        function,
        "frontier_reason",
        "terminal_frontier_evidence_violation",
    )
    if frontier_index is None:
        errors.append(
            "terminal certified final result validator must assign frontier_reason "
            "from terminal_frontier_evidence_violation(...)"
        )
    elif frontier_index + 1 >= len(body) or not _if_consumes_guard_result(
        body[frontier_index + 1],
        "frontier_reason",
        effect="return",
    ):
        errors.append(
            "terminal certified final result validator must immediately return "
            "frontier_reason when it is not None"
        )
    allowed_none_returns = []
    if body and _stmt_matches_source(
        body[0],
        "if not has_terminal_full_frontier_certified_evidence(state):\n    return None",
    ):
        allowed_none_returns.append(body[0].body[0])
    if body and _returns_none(body[-1]):
        allowed_none_returns.append(body[-1])
    none_returns = [node for node in ast.walk(function) if _returns_none(node)]
    if sorted(map(id, none_returns)) != sorted(map(id, allowed_none_returns)):
        errors.append(
            "terminal certified final result validator must not return None except "
            "for the frontier-evidence absence gate and final success"
        )
    return errors


def _check_terminal_project_precheck_structure(function: ast.FunctionDef) -> list[str]:
    label = "terminal certified final result project precheck"
    errors: list[str] = []
    body = _semantic_body(function)
    errors.extend(
        _check_fail_closed_terminal_return_shape(
            function,
            label=label,
            allowed_reason_names=frozenset({"reason", "solution_reason"}),
            allowed_reason_calls=frozenset({"_terminal_candidate_ghost_pick_binding_violation"}),
        )
    )
    errors.extend(
        _check_required_direct_calls(
            function,
            frozenset(
                {
                    "_terminal_candidate_ghost_pick_binding_violation",
                    "_validate_terminal_solution_against_project",
                    "terminal_certified_final_result_violation",
                }
            ),
            label=label,
        )
    )
    reason_index = _top_level_assignment_index(
        function,
        "reason",
        "terminal_certified_final_result_violation",
    )
    if reason_index is None:
        errors.append(
            "terminal certified final result project precheck must assign reason "
            "from terminal_certified_final_result_violation(...)"
        )
    else:
        for stmt in body[:reason_index]:
            if _stmt_contains_return_none(stmt):
                errors.append(
                    "terminal certified final result project precheck must not return None "
                    "before terminal_certified_final_result_violation(...)"
                )
        if reason_index + 1 >= len(body) or not _if_consumes_guard_result(
            body[reason_index + 1],
            "reason",
            effect="return",
        ):
            errors.append(
                "terminal certified final result project precheck must immediately return "
                "reason when it is not None"
            )
    final_result_guards = [
        stmt
        for stmt in body
        if isinstance(stmt, ast.If)
        and _expr_matches_source(stmt.test, "isinstance(final_result, Mapping)")
    ]
    if len(final_result_guards) != 1:
        errors.append(
            "terminal certified final result project precheck must have exactly one "
            "live final_result Mapping guard"
        )
    else:
        guard = final_result_guards[0]
        expected_body = (
            "solution_reason = _validate_terminal_solution_against_project(\n"
            "    final_result=final_result,\n"
            "    project_root=resolved_project_root,\n"
            "    grid_dimensions=grid_dimensions,\n"
            "    min_side_admissibility=min_side_admissibility,\n"
            ")",
            "if solution_reason is not None:\n    return solution_reason",
            "return _terminal_candidate_ghost_pick_binding_violation(\n"
            "    state,\n"
            "    final_result=final_result,\n"
            "    grid_dimensions=grid_dimensions,\n"
            ")",
        )
        if len(guard.body) != len(expected_body) or any(
            not _stmt_matches_source(stmt, expected)
            for stmt, expected in zip(guard.body, expected_body)
        ):
            errors.append(
                "terminal certified final result project precheck must run solution "
                "validation and ghost-pick validation inside the Mapping guard"
            )
    return errors


def _check_validate_terminal_solution_structure(function: ast.FunctionDef) -> list[str]:
    label = "terminal solution project validator"
    errors = _check_single_final_return_none(function, label=label)
    errors.extend(
        _check_fail_closed_terminal_return_shape(
            function,
            label=label,
            allowed_reason_names=frozenset(
                {
                    "mandatory_metadata_reason",
                    "optional_metadata_reason",
                    "pose_metadata_reason",
                }
            ),
        )
    )
    errors.extend(
        _check_required_direct_calls(
            function,
            frozenset(
                {
                    "_best_empty_rect_objective",
                    "_build_occupancy_prefix",
                    "_empty_rect_exists",
                    "_load_exact_facility_pools",
                    "_load_exact_facility_templates",
                    "_load_exact_required_optional_lower_bounds",
                    "_load_validated_mandatory_exact_instances",
                    "_occupied_count_in_rect",
                }
            ),
            label=label,
        )
    )
    errors.extend(
        _check_result_flow_to_compare_gate(
            function,
            call_name="_best_empty_rect_objective",
            result_name="best_empty_objective",
            compare_test="best_empty_objective > claimed_objective",
            effect="return",
            label=label,
        )
    )
    return errors


def _check_terminal_ghost_pick_structure(function: ast.FunctionDef) -> list[str]:
    label = "terminal candidate ghost-pick binding validator"
    errors = _check_single_final_return_none(function, label=label)
    errors.extend(
        _check_fail_closed_terminal_return_shape(
            function,
            label=label,
            allowed_reason_names=frozenset({"ghost_rect_unknown_field"}),
        )
    )
    errors.extend(
        _check_required_direct_calls(
            function,
            frozenset({"_expected_unfiltered_ghost_anchor_index", "candidate_key"}),
            label=label,
        )
    )
    errors.extend(
        _check_result_flow_to_compare_gate(
            function,
            call_name="_expected_unfiltered_ghost_anchor_index",
            result_name="expected_pose_idx",
            compare_test="expected_pose_idx is None or int(pose_idx) != int(expected_pose_idx)",
            effect="return",
            label=label,
        )
    )
    return errors


def _allowed_child_project_pre_replay_return(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.If)
        and any(isinstance(child, ast.Return) for child in stmt.body)
        and (
            _expr_matches_source(stmt.test, "not isinstance(raw_records, Mapping)")
            or _is_name(stmt.test, "violations")
            or _expr_matches_source(stmt.test, "not expected_proofs")
        )
    )


def _check_child_project_candidate_records_direct_structure(function: ast.FunctionDef) -> list[str]:
    label = "PR2 child candidate projection"
    errors: list[str] = []
    body = _semantic_body(function)
    errors.extend(
        _check_required_direct_calls(
            function,
            frozenset(
                {
                    "_invoke_isolated_replay",
                    "_replay_response_violation",
                    "candidate_proof_shape_violation",
                    "canonical_digest",
                }
            ),
            label=label,
        )
    )
    errors.extend(
        _check_guard_result_flow(
            function,
            call_name="_replay_response_violation",
            result_name="envelope_violation",
            effect="return",
            label=label,
        )
    )
    errors.extend(
        _check_result_flow_to_compare_gate(
            function,
            source='str(result.get("replay_status", ""))',
            result_name="replay_status",
            compare_test="replay_status != claimed_status",
            effect="violation_continue",
            label=label,
        )
    )
    replay_index = _top_level_assignment_index(function, "response", "_invoke_isolated_replay")
    if replay_index is None:
        errors.append(
            "PR2 child candidate projection must assign response exactly once from "
            "_invoke_isolated_replay(...)"
        )
    else:
        for stmt in body[:replay_index]:
            if isinstance(stmt, ast.Return) or (
                isinstance(stmt, ast.If)
                and any(isinstance(child, ast.Return) for child in ast.walk(stmt))
                and not _allowed_child_project_pre_replay_return(stmt)
            ):
                errors.append(
                    "PR2 child candidate projection must not return before isolated "
                    "replay except for shape/coverage rejection gates"
                )
                break
    if not body or not _stmt_matches_source(body[-1], "return projected, {}"):
        errors.append("PR2 child candidate projection must finish by returning projected, {}")
    return errors


def _check_child_fixed_witness_direct_structure(function: ast.FunctionDef) -> list[str]:
    label = "PR2 child fixed witness direct verifier"
    errors: list[str] = []
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    body = _semantic_body(function)
    if len(returns) != 1 or not body or body[-1] is not returns[0] or not _stmt_matches_source(
        body[-1],
        "return durable_records, public_projection.candidate_records, verdict",
    ):
        errors.append(
            "PR2 child fixed witness direct verifier must have exactly one final "
            "return of durable_records, projected candidate records, and verdict"
        )
    errors.extend(
        _check_required_direct_calls(
            function,
            frozenset(
                {
                    "_apply_terminal_fixed_witness_audit_fields",
                    "_copy_candidate_records",
                    "_identity_from_current_records",
                    "_materialize_replay_snapshot",
                    "_project_terminal_fixed_witness_records_from_capsule",
                    "canonical_state_bytes_for_fixed_witness",
                    "verify_terminal_fixed_witness",
                }
            ),
            label=label,
        )
    )
    errors.extend(
        _check_call_assignment_no_rebind(
            function,
            call_name="verify_terminal_fixed_witness",
            result_name="verdict",
            label=label,
        )
    )
    return errors


def _assigns_child_verdict_from_round_trip(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"child_verdict"}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "run_l0_micro_verifier_round_trip"
    )


def _assigns_domain_from_child_verdict(stmt: ast.AST) -> bool:
    if not (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"domain"}
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and stmt.value.func.attr == "get"
        and len(stmt.value.args) == 1
        and _is_constant(stmt.value.args[0], "domain")
        and not stmt.value.keywords
    ):
        return False
    receiver = stmt.value.func.value
    return (
        isinstance(receiver, ast.Attribute)
        and receiver.attr == "response"
        and _is_name(receiver.value, "child_verdict")
    )


def _sealed_l0_micro_verdict_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or _call_func_name(node) != "L0MicroVerdict":
        return False
    return any(keyword.arg == "status" and _is_name(keyword.value, "SEALED") for keyword in node.keywords)


def _is_pinned_final_l0_sealed_return(function: ast.FunctionDef, node: ast.Call) -> bool:
    parent = _p1_2_parent(node)
    if not isinstance(parent, ast.Return):
        return False
    required_keywords = {
        "status": "SEALED",
        "nonce": "nonce",
        "reason": '"supervisor_sealed"',
        "floor_digest": "child_verdict.floor_digest",
        "response": "response",
    }
    if node.args or {keyword.arg for keyword in node.keywords} != set(required_keywords):
        return False
    return all(
        keyword.arg is not None
        and _expr_matches_source(keyword.value, required_keywords[keyword.arg])
        for keyword in node.keywords
    )


def _target_has_attribute_write_to_name(target: ast.AST, names: frozenset[str]) -> bool:
    for node in ast.walk(target):
        if isinstance(node, ast.Attribute):
            current = node.value
            while isinstance(current, ast.Attribute):
                current = current.value
            if isinstance(current, ast.Name) and current.id in names:
                return True
    return False


def _target_clobbers_watched_mapping(target: ast.AST, names: frozenset[str]) -> bool:
    if isinstance(target, ast.Subscript) and _expr_may_reference_mapping(target.value, names):
        return True
    return _target_has_attribute_write_to_name(target, names)


def _assigns_response_copy_from_child_verdict(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and _target_bound_names(stmt.targets[0]) == {"response"}
        and isinstance(stmt.value, ast.Call)
        and _call_func_name(stmt.value) == "dict"
        and len(stmt.value.args) == 1
        and not stmt.value.keywords
        and _expr_matches_source(stmt.value.args[0], "child_verdict.response")
    )


def _target_is_response_l0_seal_assignment(target: ast.AST) -> bool:
    return (
        isinstance(target, ast.Subscript)
        and _is_name(target.value, "response")
        and _is_constant(target.slice, "l0_seal")
    )


def _call_references_watched_l0_data(call: ast.Call, names: frozenset[str]) -> bool:
    if _expr_may_reference_mapping(call.func, names):
        return True
    return any(_expr_may_reference_mapping(arg, names) for arg in call.args) or any(
        _expr_may_reference_mapping(keyword.value, names) for keyword in call.keywords
    )


def _expr_is_watched_l0_mutator_callable(node: ast.AST, names: frozenset[str]) -> bool:
    if isinstance(node, ast.Attribute) and _expr_may_reference_mapping(node.value, names):
        return node.attr in _PR2_MUTATING_MAPPING_METHODS
    if not isinstance(node, ast.Call) or _call_func_name(node) != "getattr":
        return False
    if not node.args or not _expr_may_reference_mapping(node.args[0], names):
        return False
    if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
        return True
    return node.args[1].value in _PR2_MUTATING_MAPPING_METHODS


def _call_mutates_watched_l0_data(call: ast.Call, names: frozenset[str]) -> bool:
    call_name = _call_func_name(call)
    if (
        call_name in {"setattr", "delattr", "vars"}
        and _call_references_watched_l0_data(call, names)
    ):
        return True
    if (
        call_name in {"dict.update", "dict.__setitem__", "dict.__delitem__", "operator.setitem"}
        and call.args
        and _expr_may_reference_mapping(call.args[0], names)
    ):
        return True
    if not isinstance(call.func, ast.Attribute):
        return False
    if call.func.attr in _PR2_MUTATING_MAPPING_METHODS and _expr_may_reference_mapping(
        call.func.value,
        names,
    ):
        return True
    if (
        call.func.attr in _PR2_MUTATING_MAPPING_METHODS
        and call.args
        and _expr_may_reference_mapping(call.args[0], names)
    ):
        return True
    if (
        call.func.attr.startswith("__")
        and call.func.attr.endswith("__")
        and _call_references_watched_l0_data(call, names)
    ):
        return True
    if isinstance(call.func.value, ast.Call) and _call_func_name(call.func.value) == "getattr":
        getattr_call = call.func.value
        if getattr_call.args and _expr_may_reference_mapping(getattr_call.args[0], names):
            return True
    return False


def _check_l0_child_verdict_dataflow(l0_seal_fn: ast.FunctionDef) -> list[str]:
    errors: list[str] = []
    assignments = [
        node
        for node in ast.walk(l0_seal_fn)
        if _assigns_child_verdict_from_round_trip(node)
    ]
    if len(assignments) != 1:
        errors.append(
            "PR2 L0 supervisor seal must assign child_verdict exactly once "
            "from run_l0_micro_verifier_round_trip(...)"
        )
        return errors
    assign_stmt = assignments[0]
    watched_names: set[str] = {"child_verdict", "child_payload"}
    watched_callables: set[str] = set()
    domain_assignment_seen = False
    response_copy_seen = False
    ordered_nodes = sorted(
        (node for node in ast.walk(l0_seal_fn) if hasattr(node, "lineno")),
        key=lambda node: (
            int(getattr(node, "lineno", 0) or 0),
            int(getattr(node, "col_offset", 0) or 0),
        ),
    )
    sealed_calls = [node for node in ordered_nodes if _sealed_l0_micro_verdict_call(node)]
    if len(sealed_calls) != 1:
        errors.append("PR2 L0 supervisor seal must have exactly one sealed L0MicroVerdict construction")
    for node in sealed_calls:
        if not _is_pinned_final_l0_sealed_return(l0_seal_fn, node):
            errors.append(
                "PR2 L0 supervisor seal must not construct a forged sealed L0MicroVerdict "
                "outside the pinned final return"
            )
    for stmt in ordered_nodes:
        if stmt is assign_stmt or not _node_starts_after(stmt, assign_stmt):
            continue
        if _assigns_domain_from_child_verdict(stmt):
            if domain_assignment_seen:
                errors.append("PR2 L0 supervisor seal must not rebind domain after child verdict validation")
            domain_assignment_seen = True
            watched_names.add("domain")
            continue
        if _assigns_response_copy_from_child_verdict(stmt):
            if response_copy_seen:
                errors.append("PR2 L0 supervisor seal must not rebind response after child verdict validation")
            response_copy_seen = True
            watched_names.add("response")
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            frozen_watched_names = frozenset(watched_names)
            for target in targets:
                bound_names = _target_bound_names(target)
                for name in sorted(bound_names):
                    if (
                        name in watched_names
                        or name.startswith("proposal_")
                    ):
                        errors.append(
                            "PR2 L0 supervisor seal must not rebind child/domain/proposal data "
                            f"after child_verdict: {name}"
                        )
                    elif isinstance(stmt, ast.Assign) and _expr_is_watched_l0_mutator_callable(
                        stmt.value,
                        frozen_watched_names,
                    ):
                        watched_callables.add(name)
                    elif isinstance(stmt, ast.Assign) and _expr_may_reference_mapping(
                        stmt.value,
                        frozen_watched_names,
                    ):
                        watched_names.add(name)
                if (
                    _target_clobbers_watched_mapping(target, frozen_watched_names)
                    and not _target_is_response_l0_seal_assignment(target)
                ):
                    errors.append(
                        "PR2 L0 supervisor seal must not write child/domain/proposal mapping data "
                        "after child_verdict"
                    )
        elif isinstance(stmt, ast.Delete):
            frozen_watched_names = frozenset(watched_names)
            for target in stmt.targets:
                bound_names = _target_bound_names(target)
                for name in sorted(bound_names):
                    if (
                        name in watched_names
                        or name.startswith("proposal_")
                    ):
                        errors.append(
                            "PR2 L0 supervisor seal must not delete child/domain/proposal data "
                            f"after child_verdict: {name}"
                        )
                if _target_clobbers_watched_mapping(target, frozen_watched_names):
                    errors.append(
                        "PR2 L0 supervisor seal must not delete child/domain/proposal mapping data "
                        "after child_verdict"
                    )
        elif isinstance(stmt, (ast.Return, ast.Raise, ast.If, ast.For, ast.AsyncFor, ast.With, ast.Try)):
            continue
        elif isinstance(stmt, ast.Call):
            if _call_mutates_watched_l0_data(stmt, frozenset(watched_names)):
                errors.append(
                    "PR2 L0 supervisor seal must not call a mutator/reflection hook "
                    "on child/domain/proposal data after child_verdict"
                )
            if isinstance(stmt.func, ast.Name) and stmt.func.id in watched_callables:
                errors.append(
                    "PR2 L0 supervisor seal must not call a mutator/reflection hook "
                    "on child/domain/proposal data after child_verdict"
                )
            continue
        else:
            continue
    if not domain_assignment_seen:
        errors.append(
            'PR2 L0 supervisor seal must bind domain exactly once from child_verdict.response.get("domain")'
        )
    return errors



def _check_candidate_sink_replay_contract(
    *,
    candidate_replay_path: Path = CANDIDATE_PROOF_REPLAY_PATH,
    candidate_replay_core_path: Path = PR2_L0_REPLAY_CORE_PATH,
    exact_campaign_path: Path = EXACT_CAMPAIGN_PATH,
    certified_frontier_path: Path = CERTIFIED_FRONTIER_PATH,
    pr2_artifact_core_path: Path = PR2_L0_ARTIFACT_CORE_PATH,
    outer_search_path: Path = OUTER_SEARCH_PATH,
    delivery_manifest_path: Path = DELIVERY_MANIFEST_PATH,
    certified_surface_path: Path = CERTIFIED_SURFACE_PATH,
    test_support_path: Path = VERIFIED_PRODUCER_TEST_SUPPORT_PATH,
    pr2_l0_path: Path = PR2_L0_MICRO_VERIFIER_PATH,
    pr2_true_child_path: Path = PR2_L0_TRUE_VERIFIER_CHILD_PATH,
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
    replay_core_tree = _parse_python(candidate_replay_core_path)
    replay_facade_source = candidate_replay_path.read_text(encoding="utf-8")
    replay_source = (
        replay_facade_source
        + "\n"
        + candidate_replay_core_path.read_text(encoding="utf-8")
    )
    for function_name in (
        "build_candidate_replay_proof",
        "verify_candidate_records_at_sink",
        "project_candidate_records_for_sink",
    ):
        _function_def(replay_tree, function_name, path=candidate_replay_path)
    for function_name in (
        "candidate_proof_shape_violation",
        "_replay_response_violation",
        "_validate_child_proof",
        "_replay_one_proof",
        "_materialize_replay_snapshot",
        "_invoke_isolated_replay",
        "_execute_isolated_replay_request",
        "isolated_replay_main",
    ):
        _function_def(replay_core_tree, function_name, path=candidate_replay_core_path)
    for facade_token in (
        "_invoke_isolated_replay,",
        "isolated_replay_main,",
        '"_invoke_isolated_replay"',
        '"isolated_replay_main"',
    ):
        if facade_token not in replay_facade_source:
            errors.append(f"candidate replay facade must re-export replay core symbol: {facade_token}")

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

    invoke_fn = _function_def(
        replay_core_tree,
        "_invoke_isolated_replay",
        path=candidate_replay_core_path,
    )
    invoke_source = _source_text(candidate_replay_core_path, invoke_fn)
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
        replay_core_tree,
        "_materialize_replay_snapshot",
        path=candidate_replay_core_path,
    )
    snapshot_source = _source_text(candidate_replay_core_path, snapshot_fn)
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
        replay_core_tree,
        "_execute_isolated_replay_request",
        path=candidate_replay_core_path,
    )
    child_request_source = _source_text(candidate_replay_core_path, child_request_fn)
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

    replay_one_fn = _function_def(
        replay_core_tree,
        "_replay_one_proof",
        path=candidate_replay_core_path,
    )
    replay_one_source = _source_text(candidate_replay_core_path, replay_one_fn)
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
        replay_core_tree,
        "_validate_child_proof",
        path=candidate_replay_core_path,
    )
    child_proof_source = _source_text(candidate_replay_core_path, child_proof_fn)
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
    artifact_core_tree = _parse_python(pr2_artifact_core_path)
    errors.extend(
        _check_unique_top_level_bindings(
            exact_tree,
            frozenset({"_supervisor_certified_transition_violation"}),
            path=exact_campaign_path,
            label="ExactCampaign supervisor runtime",
        )
    )
    errors.extend(
        _check_terminal_final_result_violation_structure(
            _function_def(
                exact_tree,
                "terminal_certified_final_result_violation",
                path=exact_campaign_path,
            )
        )
    )
    errors.extend(
        _check_terminal_project_precheck_structure(
            _function_def(
                artifact_core_tree,
                "terminal_certified_final_result_project_precheck_violation",
                path=pr2_artifact_core_path,
            )
        )
    )
    errors.extend(
        _check_validate_terminal_solution_structure(
            _function_def(
                exact_tree,
                "_validate_terminal_solution_against_project",
                path=exact_campaign_path,
            )
        )
    )
    errors.extend(
        _check_terminal_ghost_pick_structure(
            _function_def(
                exact_tree,
                "_terminal_candidate_ghost_pick_binding_violation",
                path=exact_campaign_path,
            )
        )
    )
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
    errors.extend(
        _check_exact_runtime_tcb_source_pins(
            exact_tree,
            exact_class,
            path=exact_campaign_path,
            artifact_core_tree=artifact_core_tree,
            artifact_core_path=pr2_artifact_core_path,
        )
    )
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

    l0_tree = _parse_python(pr2_l0_path)
    errors.extend(_check_l0_runtime_tcb_bindings(l0_tree, path=pr2_l0_path))
    errors.extend(
        _check_unique_top_level_bindings(
            l0_tree,
            frozenset(
                {
                    "run_l0_supervisor_seal",
                    "_postwrite_state_violation",
                    "_supervisor_certified_transition_violation_l0",
                    "_supervisor_seal_state_violation_l0",
                }
            ),
            path=pr2_l0_path,
            label="PR2 L0 supervisor runtime",
        )
    )
    l0_seal_fn = _function_def(
        l0_tree,
        "run_l0_supervisor_seal",
        path=pr2_l0_path,
    )
    l0_seal_source = _source_text(pr2_l0_path, l0_seal_fn)
    errors.extend(_check_l0_supervisor_seal_body(l0_seal_fn))
    for required_call in (
        "_load_canonical_dependency_floor_manifest",
        "_read_regular_file_bytes",
        "_proposal_ready_marker_violation",
        "_proposal_authority_violation",
        "_strong_status_keys",
        "_strong_proof_binding_violation",
        "run_l0_micro_verifier_round_trip",
        "_domain_response_violation",
        "_supervisor_seal_state_violation_l0",
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
        # PR2 #5 review hardening: the durable CERTIFIED mint must canonicalize
        # declare_mode to the supervisor-owned strict terminal label, so a producer
        # declare_mode!="strict" cannot be persisted into the sealed state.
        'scratch_state["declare_mode"] = "strict"',
    ):
        if token not in l0_seal_source:
            errors.append(f"PR2 L0 supervisor seal must bind and atomically validate P->Q authority: {token}")
    errors.extend(
        _check_literal_strict_slot_assignment(
            l0_seal_fn,
            mapping_name="scratch_state",
            slot="declare_mode",
            label="PR2 L0 supervisor durable mint",
        )
    )
    l0_transition_fn = _function_def(
        l0_tree,
        "_supervisor_certified_transition_violation_l0",
        path=pr2_l0_path,
    )
    errors.extend(
        _check_literal_strict_slot_assignment(
            l0_transition_fn,
            mapping_name="expected",
            slot="declare_mode",
            label="PR2 L0 supervisor transition gate",
            require_live_top_level=True,
        )
    )
    l0_postwrite_fn = _function_def(
        l0_tree,
        "_postwrite_state_violation",
        path=pr2_l0_path,
    )
    errors.extend(_check_live_top_level_postwrite_guard(l0_postwrite_fn))
    errors.extend(_check_l0_child_verdict_dataflow(l0_seal_fn))
    errors.extend(_check_l0_supervisor_gate_result_flow(l0_seal_fn))
    errors.extend(
        _check_l0_supervisor_seal_state_body(
            _function_def(
                l0_tree,
                "_supervisor_seal_state_violation_l0",
                path=pr2_l0_path,
            )
        )
    )

    child_tree = _parse_python(pr2_true_child_path)
    errors.extend(_check_child_module_toplevel_closed_world(child_tree))
    errors.extend(
        _check_true_child_runtime_tcb_source_pins(
            child_tree,
            path=pr2_true_child_path,
        )
    )
    errors.extend(
        _check_close_kernel_files_fully_pinned(l0_tree, child_tree, exact_tree)
    )
    errors.extend(_check_close_kernel_import_dependency_import_time_shape())
    errors.extend(
        _check_true_verifier_entrypoint_body(
            _function_def(child_tree, "verify", path=pr2_true_child_path)
        )
    )
    child_domain_fn = _function_def(
        child_tree,
        "_verify_supervisor_domain",
        path=pr2_true_child_path,
    )
    errors.extend(_check_child_verify_supervisor_domain_body(child_domain_fn))
    child_domain_source = _source_text(pr2_true_child_path, child_domain_fn)
    for required_call in (
        "_project_candidate_records_direct",
        "_run_fixed_witness_direct",
        "build_terminal_frontier_evidence",
        "canonical_candidate_geometry_rederivation_violation",
        "terminal_certified_final_result_project_precheck_violation",
    ):
        if not _calls_function(child_domain_fn, required_call):
            errors.append(f"PR2 true verifier child domain path must call {required_call}")
    errors.extend(
        _check_call_result_flow_to_truthy_consumer(
            child_domain_fn,
            call_name="_project_candidate_records_direct",
            result_name="replay_violations",
            effect="raise",
            label="PR2 true verifier child domain replay gate",
        )
    )
    errors.extend(
        _check_call_assignment_no_rebind(
            child_domain_fn,
            call_name="_run_fixed_witness_direct",
            result_name="fixed_verdict",
            label="PR2 true verifier child fixed-witness verdict",
        )
    )
    errors.extend(
        _check_expr_result_flow_to_truthy_consumer(
            child_domain_fn,
            source="{}",
            result_name="fixed_violations",
            effect="raise",
            label="PR2 true verifier child fixed-witness violation gate",
        )
    )
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
        # PR2 #5: the child must elevate the proposal to the strict terminal
        # full-frontier labels so the exhaustion / best-candidate / canonical
        # candidate-domain validation runs unconditionally (not gated off by a
        # producer-controlled declare_mode / last_stop_reason).
        'scratch_state["declare_mode"] = "strict"',
        'scratch_state["last_stop_reason"] = {',
        "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON",
    ):
        if token not in child_domain_source:
            errors.append(f"PR2 true verifier child must fail closed and report bounded domain evidence: {token}")
    errors.extend(_check_true_verifier_child_domain_elevation_window(child_domain_fn))
    errors.extend(_check_true_verifier_child_closed_world(child_domain_fn))
    errors.extend(_check_true_verifier_child_return_dict_closed_world(child_domain_fn))
    child_project_fn = _function_def(
        child_tree,
        "_project_candidate_records_direct",
        path=pr2_true_child_path,
    )
    errors.extend(_check_child_project_records_body(child_project_fn))
    child_project_source = _source_text(pr2_true_child_path, child_project_fn)
    for required_call in (
        "candidate_proof_shape_violation",
        "_invoke_isolated_replay",
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
    errors.extend(_check_child_project_candidate_records_direct_structure(child_project_fn))
    # The AST gate is intentionally structural: these sha-sealed verifier modules
    # are left to source-hash review rather than re-proving their math here.
    errors.extend(
        _check_child_fixed_witness_body(
            _function_def(
                child_tree,
                "_run_fixed_witness_direct",
                path=pr2_true_child_path,
            )
        )
    )
    errors.extend(
        _check_child_fixed_witness_direct_structure(
            _function_def(
                child_tree,
                "_run_fixed_witness_direct",
                path=pr2_true_child_path,
            )
        )
    )
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
        # PR2 #5 review hardening: the transition gate canonicalizes declare_mode to
        # strict, matching the durable mint -- so a producer non-strict declare_mode
        # is neither persisted nor falsely accepted by the byte-equality check.
        'expected["declare_mode"] = "strict"',
    ):
        if token not in transition_source:
            errors.append(f"supervisor P->Q transition gate missing token: {token}")
    errors.extend(
        _check_literal_strict_slot_assignment(
            transition_fn,
            mapping_name="expected",
            slot="declare_mode",
            label="ExactCampaign supervisor transition gate",
            require_live_top_level=True,
        )
    )
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
    candidate_replay_core_path: Path = PR2_L0_REPLAY_CORE_PATH,
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
    replay_tree = _parse_python(candidate_replay_core_path)
    replay_invoke = _function_def(
        replay_tree,
        "_invoke_isolated_replay",
        path=candidate_replay_core_path,
    )
    errors.extend(
        _check_isolated_pycache_hardened_argv(
            function=replay_invoke,
            path=candidate_replay_core_path,
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
    if not _uses_name(presence_fn, "FIXED_WITNESS_CORE_PATH"):
        errors.append(
            "fixed-witness verifier presence check must read FIXED_WITNESS_CORE_PATH"
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


def _check_certified_cut_replay_contract(
    manifest: dict[str, Any],
    *,
    frontier_core_path: Path = PR2_L0_FRONTIER_CORE_PATH,
) -> list[str]:
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
    frontier_core_tree = _parse_python(frontier_core_path)
    frontier_core_source = frontier_core_path.read_text(encoding="utf-8")
    for helper_name in (
        "generate_candidate_sizes",
        "normalize_terminal_frontier_domain_contract",
        "candidate_generation_kwargs",
        "candidate_key",
        "candidate_objective",
        "candidate_sort_key",
        "compute_terminal_frontier_projection",
        "build_terminal_frontier_evidence",
        "terminal_frontier_evidence_violation",
        "_candidate_status_digest",
    ):
        _function_def(frontier_core_tree, helper_name, path=frontier_core_path)
    for helper_name in (
        "compute_sink_verified_terminal_frontier_projection",
        "build_sink_verified_terminal_frontier_evidence",
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
        if needle not in frontier_core_source:
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
        "EXACT_CUT_FRAMEWORK_ATTACH_ENV",
        "cut_framework_attach_not_certified",
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
    # Batch 1D (owner decision 2026-07-10): C1 is the certified-default power
    # representation and the seven legacy witness-only representation envs were
    # removed from BOTH the canonical power-witness defaults and the certified
    # known-name allowlist, so they now fail closed as unknown EXACT_* names.
    # The obligation direction flips: these env names must NOT reappear in any
    # certified env classification surface.  Re-adding one to the known names
    # or the operational allowlist without a canonical lock would silently
    # downgrade it to unvalidated pass-through, which is strictly weaker than
    # both the pre-1D canonical lock and the post-1D unknown fail-closed state.
    known_env_names_source = _assignment_source(
        benders_tree,
        "_CERTIFIED_KNOWN_ENV_NAMES",
        path=BENDERS_LOOP_PATH,
    )
    operational_allowlist_source = _assignment_source(
        benders_tree,
        "_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST",
        path=BENDERS_LOOP_PATH,
    )
    for legacy_witness_env_name in (
        "EXACT_POWER_FAMILY_LOOKUP_ENCODING",
        "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING",
        "EXACT_POWER_COVERAGE_WITNESS_ENCODING",
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY",
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE",
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES",
        "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING",
    ):
        quoted = f'"{legacy_witness_env_name}"'
        if quoted in known_env_names_source:
            errors.append(
                "legacy power-witness env must stay unknown/fail-closed in certified runs "
                "(batch 1D owner decision): remove from _CERTIFIED_KNOWN_ENV_NAMES: "
                f"{legacy_witness_env_name}"
            )
        if quoted in operational_allowlist_source:
            errors.append(
                "legacy power-witness env must never become an operational allowlist entry: "
                f"{legacy_witness_env_name}"
            )
        if legacy_witness_env_name in power_witness_env_map_source:
            errors.append(
                "legacy power-witness env must not regain a canonical certified default: "
                f"{legacy_witness_env_name}"
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
    'src/search/f5_binding_empty_domain_adapter.py': 'out_of_scope_future_phase3b',
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
    'src/search/pr2_l0_artifact_core.py': 'p1_2_certified_path',
    'src/search/pr2_l0_fixed_witness_core.py': 'p1_2_certified_path',
    'src/search/pr2_l0_frontier_core.py': 'p1_2_certified_path',
    'src/search/pr2_l0_micro_verifier_core.py': 'p1_2_certified_path',
    'src/search/pr2_l0_replay_core.py': 'p1_2_certified_path',
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
        STRONG_STATUS_WRITE_ALLOWLIST_REL,
        PR2_DEPENDENCY_FLOOR_MANIFEST_REL,
        "src/search/certified_surface.py",
        "src/search/certified_artifact_contract.py",
        "src/io/delivery_manifest.py",
        "src/search/candidate_proof_replay.py",
        "src/search/certified_frontier.py",
        "src/search/exact_campaign.py",
        "src/search/pr2_l0_artifact_core.py",
        "src/search/pr2_l0_frontier_core.py",
        "src/search/pr2_l0_micro_verifier_core.py",
        "src/search/pr2_l0_replay_core.py",
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
        "src/search/pr2_l0_fixed_witness_core.py",
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
    'scripts/generate_pr2_dependency_floor_manifest.py': '9efbc3f2f32a56e6b9746604346efd7b6e1ef394fdd3ac9fa6fa7ece3ad33d8c',
    'src/adapters/base_planner/outer_deployment_plan.py': '99bff4c012eb3959165cffbf4b441493637197abc01674aaa276368622604b4d',
    'src/adapters/endfield_calc/semantic_mapping.py': 'a8ec810110116507abcfa0d708251ce740c6be3129ab375801c2539307a0c1a8',
    'src/adapters/industrial_planner/__init__.py': '190e47cf085073253e14e2c038a9c29ebb5d25953271b3b2870f4d789d91ed4a',
    'src/adapters/industrial_planner/blueprint_validator.py': 'a578225317685229d0b7469685e82d848cf125c0e70a8218de96995406474fd3',
    'src/adapters/industrial_planner/commodity_resolver.py': '69ce68d7e69b3834a28d7089a77c70c1d14eae032d979d83b1cd1041eff6017d',
    'src/adapters/industrial_planner/compatibility_report.py': '51d0103d41622940045a7b2cd060db2d2801e1891fb2cd3b856ddf8ee5cd375f',
    'src/adapters/industrial_planner/deployment_transform.py': 'dc1edc539ccd0f25a6ea9f4684990e30757bed9a9690533d90d448c3af705221',
    'src/adapters/industrial_planner/export_blueprint.py': '01afafc85b4e7f27c0bf8c0293845785b45bc71ad332da483936b753a7d9eb5e',
    'src/adapters/industrial_planner/mapping_registry.py': 'ca5f0bcffc40cd9d40d92d8407752d9236b79a19a43ee25fc35c8092e3f0772e',
    'src/adapters/industrial_planner/recipe_matcher.py': '83d1aba6e61256819287f9f60eed53311bd1cd5c3946776c02465862821676e1',
    'src/adapters/industrial_planner/throughput_audit.py': 'ecd30296a411ddf55b166f52f02ececa032e9ea1acb4302004064b9eb39c87f4',
    'src/cuts/__init__.py': '9be32e7f81eeb9be616475a83cc187940af6a3230ec5cd5a3a7d864f6e7bc4e1',
    'src/cuts/assumptions/verifiers.py': 'ac73dd4d53297c01d9e8067148215e9052eb7009ea6e5f9df247c8892fbf239a',
    'src/cuts/cert_schema.py': 'e5b46431ac2b4e81cb884dcad3c9564f797b938b9d6b3bb7022c87aa35b4226b',
    'src/cuts/families/component_reach.py': 'e1ca76d1606c8b761e09126288edf4c5e380c35b87d0d281ffc641b62fcc28f2',
    'src/cuts/families/cutset.py': 'f3a2f264dd1441f2bfb2dcf7ffe00f7769aca180020774ff4b4f10d55d1da9b2',
    'src/cuts/families/density_envelope.py': 'c7640c7805ee51685095bb4f91e0032797524aeafa42dcdecd300d3d555bfe2d',
    'src/cuts/families/pattern_nogood.py': '30b0dea92503d2b8c015b3e06e47d893af93a19b9569963658d56acb28e15e41',
    'src/cuts/families/port_exposure.py': 'd34e7b2529ad19f3be55595d6e296fefc0e19d5011cd897fbbb9a61bcea0394e',
    'src/cuts/families/power_hitting_set.py': '83a3a9d477460d39ec277b1ee43378d363513aef4c9606a9ed2364207dd347db',
    'src/cuts/families/region_capacity.py': 'c0a05ffacb3e9117db14f1e4ab10285560edaeabfe6febda4d06a877ddd9aeaa',
    'src/cuts/families/power_hitting_set_typed.py': '3867defcb9baebc5826733b13edf7a909c0d73e7c7b277deb5b4093523bc6277',
    'src/cuts/families/region_capacity_typed.py': '8e8e8f8b3ccf123fb38a6e68b03dfca46eedeb54c9a364f7e389e2d1e2d10b40',
    'src/cuts/families/shape_packing_hall.py': 'bcb6fcd211067214582fd720d356c2717b4d938f02e1551700c0aba65eeace4e',
    'src/cuts/families/shape_packing_hall_typed.py': '468b69376197156b7c52045062f7e3e33a78e25ff69198c999b981261c84ffbe',
    'src/cuts/frozen_artifacts.py': '5db14b2536dd119eda42dd801c0f1a75e4b7925db1548efbe02ed50195f88925',
    'src/cuts/helpers/__init__.py': 'd806ce5534678bc5b52a672a3c6533d7734e2edfa1beebf506f8e73246e48a20',
    'src/cuts/helpers/baseline_partition.py': 'a411932dade8039c471fcd073920af9f32acd06e52529df843a14fff022f58cf',
    'src/cuts/helpers/bounded_core_minimizer.py': 'd5999fb05366df2266b1810ac3b02a3d8515da6f779fe4ec42b84c528abaabfa',
    'src/cuts/helpers/candidate_placements.py': 'c1287947ab7cfd861a3572e994d11fe0bee13bf111202de42ee0b0fa2c4cde63',
    'src/cuts/helpers/canonical_rules.py': 'fa54e027a442fe7b0015613b3284ad05776b0c1d3063b305de1e60a880ac90c9',
    'src/cuts/helpers/canonical_sot.py': '8cedd39192a319e6179e52c53fe7dc420dc0917f92b3ca75747f1a0868c4dc1d',
    'src/cuts/helpers/power_cover.py': '4b574d736f701d5cf0219ecb6145d11ff8e2c21751cff27c486b9c84e6f16e93',
    'src/cuts/lifecycle.py': '9b944572c3bc787317a2e9bfaaf4e3ce472ba8fd953269772b24535bbef1ac1a',
    'src/cuts/oracles/pattern_nogood_oracle.py': '16a570d7b5df8a69f8d7dfdbb5736e47ed790227b2b1ffd5ad83f90e00578fca',
    'src/cuts/oracles/power_cover_oracle.py': '4fa58a4508f5c7d5674d5e0da2f1e5ef8c304a61fc5605f130eecdc95dacf2e5',
    'src/cuts/oracles/region_capacity_oracle.py': 'c3bcb690d068fd9551e93b7b4e3e7e6ebb0b6382c06053844cf66f519a547381',
    'src/cuts/oracles/shape_packing_hall_oracle.py': '5cca906742209d22d38afa6fb1e56fc979f8db591b7929348c7c62fa3ca0a3e7',
    'src/cuts/replay.py': '50a03470b0f9ddea85bb9b8fce246e326fa10a870ea930c7ebbf0c025604feed',
    'src/cuts/state_snapshot.py': '7ff01d18c049e6b1d2fde89d72afdc7d190426fcd24c0b3175482e6141eb9796',
    'src/cuts/store.py': '6266f86dd37f1ca9d6654cb8596ffbece47e420ff526ecb112be505b60870b37',
    'src/cuts/typed_apply.py': '5619589235b24fe04137721a4385e8f967bc51b5b638da6bc2c7471bc6eaa1f5',
    'src/cuts/typed_platform.py': 'cce881457c63647dbba58750e1c4884351a31987057ac72b9cd0aeecaf44b45b',
    'src/cuts/verifiers/binding_empty_domain_verifier.py': 'cbb2adcec7c9dd9813911b3501525dc6742f05288e4ba4d896f7db8635a1e693',
    'src/interchange/compatibility_manifest.py': '2ceba41d6be16fa15b252f50538a378f054b85270d06a08ad38f9adcbb5efaea',
    'src/interchange/export_registry.py': 'f1b8a08b5a728e800c8fe8af5510115e67e08c46b084550551af91636a036f21',
    'src/interchange/normalized_catalog.py': '63ffb299752349369a572e80996086ee79cf86c810450299a3d5fff9fc82c879',
    'src/interchange/preprocess_context.py': '5fa213035b9ac3e3ae78f0f12f8293e16c08d3cd913824f45bb34197fcb9f5d0',
    'src/interchange/target_capabilities.py': '9572b1a6b4fa53ba8f2a18407884815a51268bc9ba0eb76307131d6508c521f5',
    'src/io/delivery_manifest.py': '2585ec5d8008a4f74dcca2a7c98bea08fd261e59a943100ae411f7b267ef13de',
    'src/io/output_schema.py': '110e41cfd9315f00a26918d085b84c67d76f7890c7db3a05901f7c6d9e597d16',
    'src/io/serializer.py': 'ae41d33bbd9fa7f43f0e6eaec003752f4c7b928afffb924691ad6dce6a9ef52a',
    'src/io/strict_json.py': '65293ed7c0a108e906b16bee206acb1ca7f598040aa85b372023dc954574c45a',
    'src/models/_cpsat_compat.py': 'c8e4ae4b9df87bb7b3bb3f823974b940a6c10e4d651ab811be13ca1d10810d89',
    'src/models/abstract_routing_layer.py': '2e58b99dc54ca9a6dc917fe9c0515516eda8e54cfb9d7bdbf572291c0b21f520',
    'src/models/binding_subproblem.py': '1c89f6ee2cb958568c7365289a0b3d6e69a32f3162d4c925f02695705efc7ee9',
    'src/models/cp_sat_worker_config.py': '4f9a4847f179f1ed15d61b17bcdc2340c82c1ec2494abd1eb7402f919c84ba50',
    'src/models/cpsat_minimum_model.py': '92d9e9eed88dbf6672db12766a8a1422c660e8314480b9fa599ce4b0e71b7104',
    'src/models/cut_manager.py': '50b46f98cd2ca1947b807262a78a2460f822b6755d94c0845749d2c02c416a01',
    'src/models/d2_commodity_flow_core.py': 'b77f39bd7ca067f3c422552f763aec73d7c87501947dba7e87f22f33efdf3230',
    'src/models/exact_coordinate_master.py': '565062a0b438fc613634d53a5ae256addceb4b05010f42a7a3eea2c6bbbed45c',
    'src/models/flow_subproblem.py': '948c4fee4495264c339c335b353de1925a9c7b5f9ebc12e1088ac2d0a7c3d06a',
    'src/models/highs_candidate_evaluator.py': '1709e1536a49f11ed057ab6dc1e904d9acac8d25c910c4299789b5309986f419',
    'src/models/highs_master_model.py': 'ab366573359ec1db835c6c78e03f9ecd7387abc3ea5bb0aaa31cebaed64f191a',
    'src/models/master_model.py': '761890e0c799c3c0f6f19832d7b7031e93c9898d7a6a10188afc8ed59cb5daf7',
    'src/models/patch_routing_core.py': '8e7f147c4779716dc721ef7add1d17b92be75efd29d8089de424389534affd2d',
    'src/models/port_binding.py': '9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53',
    'src/models/pose_bool_exact_master.py': '8991b7f98b95ee255c4967b13fc2d22bf6eed5ec54ad1f0e48377a44db0dbd90',
    'src/models/power_placement_subproblem.py': '88573b3ebdf26a334d740d718d4f90a5216745936291ef6b87b877f99594a597',
    'src/models/routing_binding_context.py': '9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2',
    'src/models/routing_subproblem.py': '7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718',
    'src/models/scip_master_model.py': 'd3590b07088e4e67c5b714aca78e39acddd0da8b59a7b96a68ae7b4b270f2bea',
    'src/models/separator_capacity_hull.py': '3c34725e06d5227e9c3512d6ef0cfc318d3144607c5136d4ec1ced6ee9957dfe',
    'src/models/solution_hint_parser.py': '3767cbdae4ae7f560f4bb3ddfc3197f8958484e42b575fa357ec16d4efa34a32',
    'src/preprocess/demand_solver.py': 'e737df49effd148962768816e66c86f415f9026acd7ff562fbebcf528ba2ee92',
    'src/preprocess/operation_profiles.py': '0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79',
    'src/render/blueprint_exporter.py': '8ee3b21bc137493fc930b08bd5ea368e23bcd1090ddf51a56bb7264d4d31a61f',
    'src/render/industrial_planner_exact_status.py': '22875159909302a5d5dde77bd832539be1b01a10e40606d8d459996714c56183',
    'src/render/industrial_planner_single_base_delivery_entrypoints.py': 'e80cc8d6c4badadad9c23a2c6c8c645e653425b2b0002879baadb29c3dd6759c',
    'src/render/industrial_planner_single_base_delivery_frontdoor.py': '5e530baaa4e49e149755c96452521daa93ece7a3c29b6e05545fcd5819530fdb',
    'src/render/industrial_planner_single_base_delivery_landing.py': '085212ba166c2211a12a590c12d07a6a8cf6f38429d49a4d97b79633296b8da9',
    'src/render/industrial_planner_single_base_delivery_surface_alignment.py': 'f3bc8bec1160f97c25c39c170077a14ffd4ffcafbb3150dab9c61235dc3dd97c',
    'src/render/industrial_planner_single_base_delivery_surface_health.py': '788fd78ad6fcf6d9d4b8e8d4a9f57a4323295c4341730874ccb7af98736eeddf',
    'src/render/industrial_planner_single_base_delivery_viewer.py': '439cd60a64436c13e15e6cc16ecda2c1884e38a34e194999820a7c77437bc9be',
    'src/render/report_builder.py': '860ff758d6c64ac0029f2e22ad087c6b520d37d40e0264a8b464302a36c7cff6',
    'src/render/serve.py': '45a03f847c80595ef72b3e859eeccf01169ed16e87faebd7b75be4c788ff7262',
    'src/runtime/subproblem_invocation_counter.py': '6f5ac40b2674a1a2b99d9932dc262e4c57c2f622e27e4b83dc39d9bcc270c759',
    'src/search/benders_loop.py': 'a8f7aa3b6e25d247be4ea636b7e42ecb9100b46a188ab454748b575dad1fedd9',
    'src/search/f5_binding_empty_domain_adapter.py': '76d072161b85f8ce5e87682769434291b5c7ccdb005623dc8a3265fb4c48b6df',
    'src/search/orbit_homogeneity.py': '633d41eae5a2b6db987a350ca6862324df9a8551dd0191f1f3ffa264b71cc4c9',
    'src/search/campaign_telemetry.py': 'b6582c452b39c444d32a07e9f949fbbfc16558b5d99e9a0a3824d86cdc4e76f6',
    'src/search/campaign_triage.py': '0ce473249d0a78e4dd837df140a218f1a109c4e304a223910dd2c918109dd376',
    'src/search/candidate_proof_replay.py': '0a6dd3089cda9e0229cac482737b000b724f51acac51085e345f533c1238547b',
    'src/search/certified_artifact_contract.py': '6e4596d0405254013884313d842b12dd43621ef5e773bd8e5d80f15108b0514d',
    'src/search/certified_frontier.py': 'b823ba698b66850e626ad474eb83511a98c128401972f0ea44dc30c2c3947aa0',
    'src/search/certified_surface.py': '9e76bed7a8a426466c3f5df97c512084295f08e99cb0c6baf12c43309c4d0354',
    'src/search/commodity_throughput.py': '2379bd1d48071ce11ca5444797e760860986e8cf5789afea9563dc71fea61e89',
    'src/search/d2_separator.py': '0263f50142b72833f87653e34a60e9a7f2c5495b90b86ef368dc25f2e0d2327e',
    'src/search/exact_campaign.py': 'd893e59a9f1bd573208a39905bdb7d677046f97367543958cc201a90b21d1a04',
    'src/search/exact_campaign_inspector.py': 'ca16b9a7272d633a6ca19d8257cfde73d5c1858711b503aa222fd7d5c7dd53da',
    'src/search/exact_parallel_scheduler.py': 'e07c926505e030ed2ab4220afe612c7a187e0e19c222c841c5f68a0d02f7c441',
    'src/search/heuristic_feasible_finder.py': '0f9723671ddee8dd8b53659ae204f2ca1d7967d2ad3d63db0c093f8586302903',
    'src/search/independent_infeasibility_reverifier.py': 'a71cc162bad123a5d68070dfa7eb4c127d2cd47ddc7781640b8e368d2bab63f9',
    'src/search/master_hint_persistence.py': '2c1c51977a6eff577e08ac62ef97eee7605e05fdbd51ea9328f13e99c405ff4e',
    'src/search/outer_search.py': 'f7082617304e8c733ac669f9e8ba5b5fe98e980db4ea4966bb3390a04af681e1',
    'src/search/patch_conflict_separator.py': '42368fc82b79b6fe5f31186ba197accecd73d425dce2ae5fad3316f6388e64e5',
    'src/search/phase3b/anchor119/guard_controls.py': '505490c75a1ee029cc378b8ff784b213d01b3f8c0da425fea21d504e3f434c9a',
    'src/search/phase3b/anchor119/guarded_precheck_runtime.py': '4c8ebb13c4c9e0fd9e3c6e614a185183e975fd365421ef95cbf2eb5ae5098aa2',
    'src/search/phase3b/anchor119/guarded_precheck_spec.py': '2a8c414eedaf42e6685a58922a9812e8a531821cadbe5fdfce860948fea3f86c',
    'src/placement/placement_generator.py': '01f48f8025f2261a685c9c6813d25e28b08a6370ea0653a003d4d57aeb51c44d',
    'src/search/pr2_l0_artifact_core.py': '4db9e77b03e8176fbec399c3bafc78239597d960a252174afab8d0af649a33c7',
    'src/search/pr2_l0_fixed_witness_core.py': '265963175a1c8facda251fa0bc1e39781c800bcbaff7084c2bb8a382566ee17c',
    'src/search/pr2_l0_frontier_core.py': 'b658d418908b686061281dde24b9c1b89333c1659faa736cf082dcd7bbdb109b',
    'src/search/pr2_l0_micro_verifier_core.py': 'df37936427ac6d2ffb0f4163963cc1adf9f28daa4b7dc11947a0a5f78546edbb',
    'src/search/pr2_l0_replay_core.py': 'f41d06064aa09ac92f24086076b7948f638e6ebba10385232236a061d7f50df2',
    'src/search/pr2_l0_true_verifier_child.py': 'a62927ea934d135af820c4880f96c729caaf0c1c9f3e7cd97502f2e8708362cf',
    'src/search/routing_deletion_core_minimizer.py': 'eca5da516e4b32a501d4c76ee455c69394518f9213d531c8f39b98abbd1618db',
    'src/search/separator_capacity_separator.py': 'bfe7498cd31abd22999333e00d9886de862def4997d9e67246896416f0ada0e9',
    'src/search/smt_mt_outer_pruning.py': '004ce7151b8fc4dc7caf2cc32352b9090f2227f9de8fa2c7e55d9b04cbf4bf91',
    'src/search/terminal_fixed_witness_capsule.py': '017b22c4f2001f31491501c2758df845cfdcde28d3ede3ac68ed6fc033ddff84',
    'src/search/terminal_fixed_witness_verifier.py': '6822795d3d2480750d91d3558b3749ce7d84db5f9a843a1d5463e306ed285d3d'
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

    try:
        import_time_closure_paths = _close_kernel_import_time_closure_source_paths(
            project_root=project_root
        )
    except CheckError as exc:
        errors.append(str(exc))
        import_time_closure_paths = ()
    for rel_path in import_time_closure_paths:
        if rel_path not in CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH:
            errors.append(
                f"{rel_path} is in the close-kernel first-party import-time closure "
                "but missing from the v99 source-hash floor"
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
        "manifest_provenance_status": PR2_DEPENDENCY_FLOOR_PROVENANCE_STATUS,
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



def _literal_tuple_constant_assignment(
    tree: ast.Module,
    name: str,
    *,
    path: Path,
) -> tuple[object, ...] | None:
    bindings = _top_level_binding_points(tree, name)
    if len(bindings) != 1:
        return None
    stmt = bindings[0]
    value: ast.AST | None = None
    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == name:
            value = stmt.value
    elif isinstance(stmt, ast.AnnAssign):
        if isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            value = stmt.value
    if value is None:
        return None
    try:
        literal = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(literal, tuple):
        return None
    return literal


def _literal_str_constant_assignment(
    tree: ast.Module,
    name: str,
    *,
    path: Path,
) -> str | None:
    bindings = _top_level_binding_points(tree, name)
    if len(bindings) != 1:
        return None
    stmt = bindings[0]
    value: ast.AST | None = None
    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == name:
            value = stmt.value
    elif isinstance(stmt, ast.AnnAssign):
        if isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            value = stmt.value
    if value is None:
        return None
    try:
        literal = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    return literal if isinstance(literal, str) else None


def _contract_function_has_statement(function: ast.FunctionDef, source: str) -> bool:
    return any(_stmt_matches_source(stmt, source) for stmt in function.body)


def _contract_executable_body(function: ast.FunctionDef) -> list[ast.stmt]:
    body = list(function.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _contract_statement_sequence_matches(
    function: ast.FunctionDef,
    expected_sources: Sequence[str],
) -> bool:
    body = _contract_executable_body(function)
    return len(body) == len(expected_sources) and all(
        _stmt_matches_source(stmt, source)
        for stmt, source in zip(body, expected_sources)
    )


def _contract_reachable_call_count(function: ast.FunctionDef, call_name: str) -> int:
    return sum(
        1
        for child in ast.walk(function)
        if isinstance(child, ast.Call) and _call_func_name(child) == call_name
    )


def _contract_has_subprocess_checker_invocation(function: ast.FunctionDef) -> bool:
    calls = [
        child
        for child in ast.walk(function)
        if isinstance(child, ast.Call) and _call_func_name(child) == "subprocess.run"
    ]
    if len(calls) != 1:
        return False
    call = calls[0]
    if not call.args or not isinstance(call.args[0], ast.List):
        return False
    argv = call.args[0].elts
    required_argv_shapes = (
        "sys.executable",
        "'-I'",
        "'-S'",
        "'-B'",
        "'-X'",
        "f'pycache_prefix={pycache_prefix}'",
        "str(checker_path)",
    )
    for expected in required_argv_shapes:
        if not any(_expr_matches_source(item, expected) for item in argv):
            return False
    keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}
    expected_keywords = {
        "cwd": "str(root)",
        "capture_output": "True",
        "text": "True",
        "timeout": "float(checker_timeout_seconds)",
        "check": "False",
    }
    return all(
        name in keywords and _expr_matches_source(keywords[name], expected)
        for name, expected in expected_keywords.items()
    )


_LOCKED_CONTRACT_ANCHORED_FUNCTION_NAMES = (
    "certified_project_uses_locked_artifact_contract",
    "_locked_close_kernel_manifest_projection_violation",
    "_locked_close_kernel_checker_ast_anchor_violation",
    "locked_p1_2_close_kernel_violation",
    "validate_locked_p1_2_close_kernel",
)
# round-20 (G1): imports the parent gate resolves at runtime while running the
# checker subprocess.  A module-top-level rebind of any of these (``subprocess =
# _fake`` -> second binding, or ``subprocess.run = _noop`` -> attribute write)
# would let the gate ``subprocess.run([...])`` call resolve to a forged object
# even though the pinned call shape is unchanged, so the anchor pins each to a
# single module-level binding and forbids dynamic writes against them.
_LOCKED_CONTRACT_CRITICAL_RUNTIME_NAMES = frozenset(
    {"ast", "json", "shutil", "subprocess", "sys", "tempfile", "Path"}
)
_LOCKED_CONTRACT_PROTECTED_RUNTIME_NAMES = _LOCKED_CONTRACT_CRITICAL_RUNTIME_NAMES | frozenset(
    _LOCKED_CONTRACT_ANCHORED_FUNCTION_NAMES
)


def _check_certified_artifact_contract_runtime_anchor(
    *,
    path: Path = CERTIFIED_ARTIFACT_CONTRACT_PATH,
) -> list[str]:
    """Statically anchor the runtime parent gate that runs this checker.

    ``src/search/certified_artifact_contract.py`` is not merely another sink: it is
    the parent process that decides whether a locked campaign must execute the
    checker before self-sealing.  Source-sha floors make edits visible, but a
    faithful floor reseal would still allow a one-line parent no-op unless the
    checker also verifies the parent anchor's own control-flow skeleton.
    """

    errors: list[str] = []
    try:
        tree = _parse_python(path)
    except CheckError as exc:
        return [str(exc)]

    expected_required_paths = (
        "data/proof_obligations/p1_2_proof_obligations.json",
        "data/proof_obligations/strong_status_write_allowlist.json",
        "scripts/check_p1_2_proof_obligations.py",
    )
    actual_required_paths = _literal_tuple_constant_assignment(
        tree,
        "LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS",
        path=path,
    )
    if actual_required_paths != expected_required_paths:
        errors.append(
            "certified artifact runtime anchor must hard-code the close-kernel required paths"
        )

    actual_projection_sha = _literal_str_constant_assignment(
        tree,
        "LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256",
        path=path,
    )
    if actual_projection_sha != P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256:
        errors.append(
            "certified artifact runtime anchor semantic projection sha must match checker floor"
        )

    expected_protected_callees = tuple(
        dict.fromkeys(
            (*_PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR, *_PR2_CHECKER_CANDIDATE_SINK_REQUIRED_CALLS_FLOOR)
        )
    )
    actual_protected_callees = _literal_tuple_constant_assignment(
        tree,
        "LOCKED_P1_2_CHECKER_PROTECTED_CALLEES",
        path=path,
    )
    if actual_protected_callees != expected_protected_callees:
        errors.append(
            "certified artifact runtime anchor must protect every checker main/sink callee"
        )

    try:
        uses_locked = _function_def(
            tree,
            "certified_project_uses_locked_artifact_contract",
            path=path,
        )
        manifest_projection = _function_def(
            tree,
            "_locked_close_kernel_manifest_projection_violation",
            path=path,
        )
        checker_ast_anchor = _function_def(
            tree,
            "_locked_close_kernel_checker_ast_anchor_violation",
            path=path,
        )
        violation = _function_def(tree, "locked_p1_2_close_kernel_violation", path=path)
        validate = _function_def(tree, "validate_locked_p1_2_close_kernel", path=path)
    except CheckError as exc:
        errors.append(str(exc))
        return errors

    # round-20 (G1): the anchor already requires each checker protected callee to
    # be an undecorated top-level FunctionDef; make the parent gate's own five
    # anchored functions symmetric -- a ``@_noop`` decorator would leave the body
    # sequence intact while replacing the runtime object with a wrapper.
    for anchored_fn in (uses_locked, manifest_projection, checker_ast_anchor, violation, validate):
        if anchored_fn.decorator_list:
            errors.append(
                f"certified artifact runtime anchor parent gate function "
                f"{anchored_fn.name} must be undecorated so its runtime binding is the "
                f"checked FunctionDef"
            )

    # round-20 (G1): the parent module has no top-level closed world of its own --
    # only its five function bodies were pinned.  A ``globals()["validate_..."] =
    # _noop`` (Subscript-target assign) or ``subprocess.run = _noop`` (attribute
    # write) at parent top level rebinds the runtime object without a ``Name``
    # binding point, so the checker enforces the same denylist the parent applies
    # to the checker it runs, plus single-binding uniqueness for the runtime names
    # the gate resolves.
    errors.extend(
        _top_level_protected_binding_rebind_errors(
            tree,
            path=path,
            label="certified artifact runtime anchor parent gate",
            protected_names=_LOCKED_CONTRACT_PROTECTED_RUNTIME_NAMES,
        )
    )
    for critical_name in sorted(_LOCKED_CONTRACT_CRITICAL_RUNTIME_NAMES):
        if len(_top_level_binding_points(tree, critical_name)) != 1:
            errors.append(
                f"certified artifact runtime anchor parent module runtime name "
                f"{critical_name} must have exactly one module-level binding"
            )

    uses_locked_required = (
        "root = Path(project_root).resolve()",
        "source_root = Path(__file__).resolve().parents[2]",
        "if root == source_root:\n    return True",
        "marker = root / LOCKED_EXACT_PROJECT_MARKER",
        "return marker.exists() or marker.is_symlink()",
    )
    if not _contract_statement_sequence_matches(uses_locked, uses_locked_required):
        errors.append(
            "certified_project_uses_locked_artifact_contract lost locked-source/marker shape"
        )

    manifest_projection_required = (
        "try:\n"
        "    manifest = _load_locked_close_kernel_manifest(path)\n"
        "except (OSError, ValueError, json.JSONDecodeError):\n"
        "    return \"locked_p1_2_close_kernel_manifest_invalid\"",
        'declared = manifest.get("semantic_projection_sha256")',
        "if declared != LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256:\n"
        "    return \"locked_p1_2_close_kernel_semantic_projection_mismatch\"",
        "return None",
    )
    if not _contract_statement_sequence_matches(manifest_projection, manifest_projection_required):
        errors.append("locked close-kernel manifest projection guard lost semantic shape")

    checker_ast_required = (
        "try:\n"
        "    tree = ast.parse(checker_path.read_text(encoding=\"utf-8-sig\"))\n"
        "except (OSError, SyntaxError, ValueError):\n"
        "    return \"locked_p1_2_close_kernel_checker_ast_invalid\"",
        "if not _locked_checker_has_canonical_entrypoint(tree):\n"
        "    return \"locked_p1_2_close_kernel_checker_entrypoint_invalid\"",
        "top_level_violation = _locked_checker_top_level_closed_world_violation(tree)",
        "if top_level_violation is not None:\n    return top_level_violation",
        'for name in ("main", *LOCKED_P1_2_CHECKER_PROTECTED_CALLEES):\n'
        "    bindings = _locked_top_level_binding_points(tree, name)\n"
        "    if len(bindings) != 1:\n"
        "        return f\"locked_p1_2_close_kernel_checker_protected_binding:{name}\"\n"
        "    binding = bindings[0]\n"
        "    if not isinstance(binding, ast.FunctionDef) or binding.name != name:\n"
        "        return f\"locked_p1_2_close_kernel_checker_protected_binding:{name}\"\n"
        "    if binding.decorator_list:\n"
        "        return f\"locked_p1_2_close_kernel_checker_protected_binding:{name}\"",
        "return None",
    )
    if not _contract_statement_sequence_matches(checker_ast_anchor, checker_ast_required):
        errors.append("locked close-kernel checker AST parent anchor lost protected-binding shape")

    violation_required = (
        "if not certified_project_uses_locked_artifact_contract(project_root):\n    return None",
        "root = Path(project_root)",
        "for relative_path in LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS:\n"
        "    path = root / relative_path\n"
        "    if not path.exists():\n"
        "        return f\"locked_p1_2_close_kernel_missing:{relative_path}\"\n"
        "    if _path_has_symlink_component(path) or not path.is_file():\n"
        "        return f\"locked_p1_2_close_kernel_not_regular:{relative_path}\"",
        "manifest_relative_path = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS[0]",
        "manifest_violation = _locked_close_kernel_manifest_projection_violation(\n"
        "    root / manifest_relative_path\n"
        ")",
        "if manifest_violation is not None:\n    return manifest_violation",
        "checker_relative_path = \"scripts/check_p1_2_proof_obligations.py\"",
        "checker_path = root / checker_relative_path",
        "checker_anchor_violation = _locked_close_kernel_checker_ast_anchor_violation(checker_path)",
        "if checker_anchor_violation is not None:\n    return checker_anchor_violation",
        "pycache_prefix = tempfile.mkdtemp(prefix=\"zmd_p1_2_close_kernel_pycache_\")",
        "try:\n"
        "    result = subprocess.run(\n"
        "        [\n"
        "            sys.executable,\n"
        "            \"-I\",\n"
        "            \"-S\",\n"
        "            \"-B\",\n"
        "            \"-X\",\n"
        "            f\"pycache_prefix={pycache_prefix}\",\n"
        "            str(checker_path),\n"
        "        ],\n"
        "        cwd=str(root),\n"
        "        capture_output=True,\n"
        "        text=True,\n"
        "        timeout=float(checker_timeout_seconds),\n"
        "        check=False,\n"
        "    )\n"
        "except subprocess.TimeoutExpired:\n"
        "    return \"locked_p1_2_close_kernel_checker_timeout\"\n"
        "except OSError as exc:\n"
        "    return f\"locked_p1_2_close_kernel_checker_error:{type(exc).__name__}\"\n"
        "finally:\n"
        "    shutil.rmtree(pycache_prefix, ignore_errors=True)",
        "if result.returncode != 0:\n"
        "    return f\"locked_p1_2_close_kernel_checker_rejected:{result.returncode}\"",
        "return None",
    )
    if not _contract_statement_sequence_matches(violation, violation_required):
        errors.append("locked_p1_2_close_kernel_violation lost fail-closed parent-gate shape")
    if _contract_reachable_call_count(violation, "subprocess.run") != 1:
        errors.append("locked_p1_2_close_kernel_violation must run exactly one checker subprocess")
    elif not _contract_has_subprocess_checker_invocation(violation):
        errors.append("locked_p1_2_close_kernel_violation checker subprocess lost isolated argv/keyword shape")

    validate_body = _contract_executable_body(validate)
    if len(validate_body) != 3:
        errors.append("validate_locked_p1_2_close_kernel must keep reason-gate-raise body shape")
    else:
        if not _stmt_matches_source(
            validate_body[0],
            "reason = locked_p1_2_close_kernel_violation(project_root)",
        ):
            errors.append("validate_locked_p1_2_close_kernel must call violation helper first")
        if not _stmt_matches_source(validate_body[1], "if reason is None:\n    return"):
            errors.append("validate_locked_p1_2_close_kernel must return only after a clean violation helper")
        final_stmt = validate_body[2]
        if not (
            isinstance(final_stmt, ast.Raise)
            and isinstance(final_stmt.exc, ast.Call)
            and isinstance(final_stmt.exc.func, ast.Name)
            and final_stmt.exc.func.id == "LockedExactArtifactContractError"
        ):
            errors.append("validate_locked_p1_2_close_kernel must raise LockedExactArtifactContractError")

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
    else:
        errors.extend(
            _top_level_exact_import_runtime_binding_errors(
                benders_tree,
                module="src.search.independent_infeasibility_reverifier",
                name="reverify_whole_layout_infeasibility",
                path=benders_loop_path,
                label="whole-layout nogood funnel",
            )
        )
    controller_class = _class_def(benders_tree, "LBBDController", path=benders_loop_path)
    if controller_class.decorator_list or controller_class.bases or controller_class.keywords:
        errors.append(
            "whole-layout nogood controller class must have no decorators, bases, "
            "or metaclass keywords so checked methods resolve on LBBDController itself"
        )
    lookup_hooks = _class_defines_attribute_lookup_hooks(controller_class)
    if lookup_hooks:
        errors.append(
            "whole-layout nogood controller class must not define instance attribute "
            "lookup/write hooks (" + ", ".join(sorted(lookup_hooks)) + ") that could "
            "redirect the checked method at runtime"
        )
    errors.extend(
        _top_level_protected_binding_rebind_errors(
            benders_tree,
            path=benders_loop_path,
            label="whole-layout nogood funnel",
            protected_names=frozenset(
                {
                    "reverify_whole_layout_infeasibility",
                    "LBBDController",
                    "_add_exact_whole_layout_nogood",
                }
            ),
        )
    )
    funnel_fn = _method_def(
        controller_class,
        "_add_exact_whole_layout_nogood",
        path=benders_loop_path,
    )
    if funnel_fn.decorator_list:
        errors.append(
            "whole-layout nogood funnel must be undecorated so its runtime binding "
            "is the checked FunctionDef"
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
        "verdict.details",
        "verdict.port_specs_digest",
        "_validated_terminal_fixed_witness_port_carrier",
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
    # Stay-blocked sentinel lifted: owner 2026-07-07 closed P1.2 and opened P1.3B by an
    # explicit owner_manual_decision (the exact transition this function's docstring
    # anticipates). The fixed-witness publish binding below remains enforced unconditionally
    # — opening P1.3B never silently drops it — while next_allowed no longer forces blocked.
    del next_allowed
    return _fixed_witness_publish_binding_errors()


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


def _print_p1_2_errors(messages: Sequence[str]) -> None:
    print(f"P1.2 proof obligation check failed: {len(messages)} issue(s)")
    for message in messages[:50]:
        print(f"  - {message}")
    if len(messages) > 50:
        print(f"  ... {len(messages) - 50} more")


def main() -> int:
    preflight_errors: list[str] = []
    preflight_errors.extend(_check_close_kernel_checker_self_binding())
    preflight_errors.extend(_check_error_collector_integrity())
    if preflight_errors:
        _print_p1_2_errors(preflight_errors)
        return 1
    try:
        manifest = _load_json(MANIFEST_PATH)
        errors: list[str] = []
        schema_version = manifest.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            errors.append("schema_version must be an integer")
        elif schema_version != 1:
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
        errors.extend(_check_main_self_integrity_preflight_shape())
        errors.extend(_check_main_error_reporting_shape())
        errors.extend(_check_error_collector_return_shape())
        errors.extend(_check_proof_obligation_manifest_semantic_projection(manifest))
        errors.extend(_check_close_kernel_contract(manifest))
        errors.extend(_check_certified_artifact_contract_runtime_anchor())
        errors.extend(_check_phase_gate_provenance_contract())
        errors.extend(_check_phase_anchor(manifest))
        errors.extend(_check_exact_session_atomic_snapshot_contract())
        errors.extend(_check_independent_infeasibility_reverifier_contract())
    except CheckError:
        return 2

    if errors:
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

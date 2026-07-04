"""Tests for the P1.2 proof-obligation consolidation gate."""
from __future__ import annotations

import ast
import copy
import json
import shutil
import subprocess
import sys
import tempfile
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
        # The checker runs ~15s standalone (full AST analysis of the 3
        # close-kernel files + 60-file import-time closure hashing + an
        # isolated sub-checker subprocess). Under `pytest -n auto` the suite
        # saturates every core, so this redundant subprocess re-run of the
        # gate can be starved well past a tight 30s budget even though the
        # gate itself passes directly (preflight step 14) and standalone.
        # Give generous headroom so parallel execution does not false-red.
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "P1.2 proof obligation check passed: 14 obligations anchored" in result.stdout
    assert "proof-bearing sink files sealed" in result.stdout


def test_p1_2_proof_obligation_manifest_has_required_ids() -> None:
    manifest = check_p1_2_proof_obligations._load_json(MANIFEST_PATH)
    obligation_ids = {item["id"] for item in manifest["obligations"]}

    assert check_p1_2_proof_obligations.REQUIRED_OBLIGATION_IDS <= obligation_ids
    assert "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS" in obligation_ids
    assert "PO-CANDIDATE-SINK-REPLAY-AUTHORITY" in obligation_ids
    assert "PO-ISOLATED-EXEC-BYTECODE-BINDING" in obligation_ids
    assert manifest["phase_gate_required_anchor"] == "v99_p1_2_close_kernel_sealing"
    assert "close_kernel_contract" in manifest


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

    sink_replay_tests = obligations["PO-CANDIDATE-SINK-REPLAY-AUTHORITY"]
    assert "test_p1_2_mutating_verified_writer_closure_cell_cannot_publish_false_certified" in sink_replay_tests
    assert "test_p1_2_forged_proof_bearing_infeasible_cannot_prune_better_feasible_candidate" in sink_replay_tests
    assert "test_p1_2_forged_certified_cannot_enter_terminal_manifest_or_public_surface" in sink_replay_tests
    assert "test_p1_2_module_rebinding_monkeypatch_and_test_helper_do_not_grant_authority" in sink_replay_tests
    assert "test_p1_2_strong_status_without_sink_replayable_proof_fails_closed" in sink_replay_tests
    assert "test_p1_2_legitimate_certified_exact_path_survives_all_sink_replays" in sink_replay_tests
    assert "test_p1_2_checker_rejects_candidate_replay_isolation_removal" in sink_replay_tests
    assert "test_p1_2_checker_rejects_frontier_sink_replay_bypass" in sink_replay_tests
    assert "test_save_rejects_caller_memory_terminal_certified_checkpoint" in sink_replay_tests
    assert "test_checkpoint_write_lock_fails_closed_when_already_held" in sink_replay_tests
    assert "test_resume_false_invalidates_old_proposal_marker" in sink_replay_tests
    assert "test_supervisor_seal_rejects_marker_campaign_instance_id_mismatch" in sink_replay_tests
    assert (
        "test_supervisor_seal_rechecks_marker_before_mint_and_preserves_concurrent_proposal"
        in sink_replay_tests
    )

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
    assert "test_v82_terminal_frontier_dominance_keeps_smaller_pending_candidate_canary" in frontier_tests

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
    assert "test_v92_release_rejects_embedded_certified_claim" in export_tests
    assert "test_v92_release_rejects_non_allowlisted_exact_status" in export_tests
    assert "test_v93_release_rejects_forged_exact_note_with_open_status" in export_tests
    assert "test_v93_rejects_solution_entry_fake_certified_claim" in export_tests
    assert "test_v93_rejects_public_final_result_ghost_pick_marker" in export_tests
    assert "test_terminal_project_validator_rejects_surplus_protocol_storage_box_blockers" in export_tests
    assert "test_v95_rejects_contradictory_pose_optional_public_metadata" in export_tests
    assert "test_v95_rejects_terminal_public_last_stop_reason_extra_claim_field" in export_tests
    assert "test_v96_certified_surface_rejects_manifest_under_symlinked_solutions_parent" in export_tests
    assert "test_v97_delivery_manifest_rejects_certified_shadow_campaign_checkpoint" in export_tests
    assert "test_v97_certified_surface_rejects_certified_shadow_campaign_checkpoint" in export_tests
    assert "test_v97_certified_surface_rejects_symlink_campaign_path_to_canonical_checkpoint" in export_tests
    assert "test_v97_inspector_preserves_symlink_campaign_path_until_surface_verifier" in export_tests
    assert "test_v98_b5a_preserves_symlink_campaign_path_until_surface_verifier" in export_tests
    assert (
        "test_serve_viewer_rejects_forged_canonical_outputs_and_removes_stale_viewer_copies"
        in export_tests
    )
    assert (
        "test_report_builder_rejects_forged_canonical_outputs_without_publishable_surface"
        in export_tests
    )
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

    close_kernel_tests = obligations["PO-P1-2-CLOSE-KERNEL-SEALING"]
    assert "test_p1_2_checker_detects_multiline_public_certified_return" in close_kernel_tests
    assert "test_p1_2_close_kernel_rejects_dependency_floor_generator_drift" in close_kernel_tests
    assert "test_p1_2_close_kernel_rejects_dependency_floor_manifest_drift" in close_kernel_tests
    assert "test_p1_2_round12_close_kernel_import_closure_follows_match_case_import" in close_kernel_tests
    assert "test_p1_2_round12_close_kernel_import_closure_follows_helper_body_import" in close_kernel_tests
    assert "test_p1_2_round12_close_kernel_rejects_dynamic_import_alias" in close_kernel_tests
    assert "test_p1_2_round12_close_kernel_rejects_namespace_mutator_target" in close_kernel_tests
    assert "test_p1_2_round13_current_scope_binding_walker_rejects_walrus_and_delete_smuggling" in close_kernel_tests
    assert "test_p1_2_round13_close_kernel_rejects_import_and_builtin_shadow" in close_kernel_tests
    assert "test_p1_2_round13_close_kernel_rejects_decorator_drift" in close_kernel_tests
    assert "test_p1_2_round13_checker_error_collector_integrity" in close_kernel_tests
    assert "test_p1_2_round13_self_binding_requires_new_gates_and_self_call" in close_kernel_tests
    assert "test_p1_2_round13_manifest_semantic_projection_rejects_resealed_gutting" in close_kernel_tests
    assert "test_p1_2_round13_source_text_includes_parenthesized_decorator_start" in close_kernel_tests
    assert "test_p1_2_checker_rejects_pr2_5_round8_close_kernel_bypasses" in close_kernel_tests
    assert "test_p1_2_checker_rejects_pr2_5_round9_gate_helper_hollows" in close_kernel_tests
    assert "test_p1_2_empty_rect_leaf_math_oracle" in close_kernel_tests
    assert "test_p1_2_child_path_confinement_leaf_canary" in close_kernel_tests
    assert "test_p1_2_close_kernel_strict_json_leaf_canaries" in close_kernel_tests
    assert "test_p1_2_round10_close_kernel_full_pin_enforcement" in close_kernel_tests
    assert "test_p1_2_round15_manifest_projection_rejects_top_level_key_drift" in close_kernel_tests
    assert "test_p1_2_round15_close_kernel_rejects_runtime_reflection_primitive_writes" in close_kernel_tests
    assert "test_p1_2_round15_close_kernel_rejects_ctypes_native_member_write" in close_kernel_tests
    assert "test_p1_2_round15_close_kernel_allows_known_safe_runtime_member_forms" in close_kernel_tests
    assert "test_p1_2_round15_witness_shadow_rejects_comprehension_and_namespace_writes" in close_kernel_tests
    assert "test_p1_2_round15_witness_shadow_rejects_statement_and_type_binding_forms" in close_kernel_tests
    assert "test_p1_2_round15_checker_required_callees_are_runtime_bound_before_subprocess" in close_kernel_tests
    assert (
        "test_p1_2_round15_checker_top_level_closed_world_rejects_dynamic_namespace_rebind"
        in close_kernel_tests
    )
    assert "test_p1_2_round15_checker_rejects_errors_match_capture_and_other_rebinds" in close_kernel_tests
    assert "test_p1_2_round15_checker_rejects_unapproved_accumulator_callee_and_frame_escape" in close_kernel_tests
    assert "test_p1_2_round15_checker_rejects_side_effectful_errors_append_args" in close_kernel_tests
    assert "test_p1_2_round15_checker_rejects_floor_tuple_walrus_rebind" in close_kernel_tests
    assert "test_p1_2_round15_try_star_and_literal_accumulator_concern_canaries" in close_kernel_tests
    assert "test_p1_2_round18_checker_rejects_class_body_import_time_main_rebind" in close_kernel_tests
    assert "test_p1_2_round18_checker_rejects_checkerror_shadowing_handler" in close_kernel_tests
    assert "test_p1_2_round18_checker_rejects_process_exit_aliases_before_error_gate" in close_kernel_tests
    assert "test_p1_2_round18_checker_rejects_accumulator_alias_frame_escape" in close_kernel_tests
    assert "test_locked_close_kernel_rejects_import_time_class_body_main_rebind" in close_kernel_tests
    assert "test_p1_2_round20_parent_anchor_rejects_decorated_parent_gate_function" in close_kernel_tests
    assert "test_p1_2_round20_parent_anchor_rejects_top_level_dynamic_namespace_write" in close_kernel_tests
    assert "test_p1_2_round20_parent_anchor_rejects_critical_name_attribute_monkeypatch" in close_kernel_tests
    assert "test_p1_2_round20_parent_anchor_rejects_critical_name_rebind" in close_kernel_tests
    assert "test_p1_2_round20_witness_binding_rejects_while_body_rebind" in close_kernel_tests
    assert "test_p1_2_round20_witness_binding_rejects_wildcard_import" in close_kernel_tests
    assert "test_p1_2_round20_benders_contract_rejects_class_attribute_method_rebind" in close_kernel_tests
    assert "test_p1_2_round20_benders_contract_rejects_instance_lookup_hook" in close_kernel_tests
    assert "test_p1_2_round20_witness_carrier_rejects_function_code_swap" in close_kernel_tests
    assert (
        "test_p1_2_round20_checker_closed_world_rejects_vararg_annotation_primitive"
        in close_kernel_tests
    )
    assert "test_p1_2_round20_parent_binding_walker_mirrors_checker" in close_kernel_tests
    assert (
        "test_locked_close_kernel_rejects_main_rebind_hidden_in_argument_annotation"
        in close_kernel_tests
    )


def _publisher_scan_paths() -> list[Path]:
    return [
        check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH,
        PROJECT_ROOT / "scripts" / "export_industrial_planner_bundle.py",
    ]


def _replace_once(source: str, old: str, new: str) -> str:
    assert old in source
    return source.replace(old, new, 1)


def _candidate_sink_replay_errors_for_sources(
    tmp_path: Path,
    *,
    child_source: str | None = None,
    l0_source: str | None = None,
    exact_source: str | None = None,
    artifact_core_source: str | None = None,
    replay_core_source: str | None = None,
) -> list[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_root = Path(tempfile.mkdtemp(prefix="zmd_candidate_sink_sources_"))
    try:
        child_path = source_root / "pr2_l0_true_verifier_child.py"
        l0_path = source_root / "pr2_l0_micro_verifier_core.py"
        exact_path = source_root / "exact_campaign.py"
        artifact_core_path = source_root / "pr2_l0_artifact_core.py"
        replay_core_path = source_root / "pr2_l0_replay_core.py"
        child_path.write_text(
            child_source
            if child_source is not None
            else check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
            newline="\n",
        )
        l0_path.write_text(
            l0_source
            if l0_source is not None
            else check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
            newline="\n",
        )
        exact_path.write_text(
            exact_source
            if exact_source is not None
            else check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
            newline="\n",
        )
        artifact_core_path.write_text(
            artifact_core_source
            if artifact_core_source is not None
            else check_p1_2_proof_obligations.PR2_L0_ARTIFACT_CORE_PATH.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
            newline="\n",
        )
        replay_core_path.write_text(
            replay_core_source
            if replay_core_source is not None
            else check_p1_2_proof_obligations.PR2_L0_REPLAY_CORE_PATH.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
            newline="\n",
        )
        try:
            return check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
                exact_campaign_path=exact_path,
                candidate_replay_core_path=replay_core_path,
                pr2_artifact_core_path=artifact_core_path,
                pr2_l0_path=l0_path,
                pr2_true_child_path=child_path,
            )
        except check_p1_2_proof_obligations.CheckError as exc:
            return [str(exc)]
    finally:
        shutil.rmtree(source_root, ignore_errors=True)


def _checker_source() -> str:
    return (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )


def _write_checker_source(tmp_path: Path, name: str, source: str) -> Path:
    checker_path = tmp_path / name
    checker_path.write_text(source, encoding="utf-8", newline="\n")
    return checker_path


def _checker_source_before_entrypoint(source: str, addition: str) -> str:
    marker = '\n\nif __name__ == "__main__":\n'
    assert marker in source
    return source.replace(marker, f"\n{addition}\n{marker}", 1)


def _checker_self_binding_errors_for_source(
    tmp_path: Path,
    source: str,
    *,
    name: str = "checker_round15.py",
) -> list[str]:
    checker_path = _write_checker_source(tmp_path, name, source)
    return check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path,
    )


def _checker_error_integrity_errors_for_source(
    tmp_path: Path,
    source: str,
    *,
    name: str = "checker_round15_errors.py",
) -> list[str]:
    checker_path = _write_checker_source(tmp_path, name, source)
    return check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path,
    )


def _locked_close_kernel_violation_for_checker_source(
    tmp_path: Path,
    source: str,
) -> str | None:
    from src.search.certified_artifact_contract import locked_p1_2_close_kernel_violation

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "PROJECT_LOCK.md").write_text("locked\n", encoding="utf-8", newline="\n")
    manifest_path = tmp_path / "data/proof_obligations/p1_2_proof_obligations.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(MANIFEST_PATH.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    allowlist_path = tmp_path / "data/proof_obligations/strong_status_write_allowlist.json"
    allowlist_path.write_text(
        check_p1_2_proof_obligations.STRONG_STATUS_WRITE_ALLOWLIST_PATH.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
        newline="\n",
    )
    checker_path = tmp_path / "scripts/check_p1_2_proof_obligations.py"
    checker_path.parent.mkdir(exist_ok=True)
    checker_path.write_text(source, encoding="utf-8", newline="\n")
    return locked_p1_2_close_kernel_violation(tmp_path, checker_timeout_seconds=0.01)


def _fixed_witness_errors_for_exact_source(tmp_path: Path, exact_source: str) -> list[str]:
    exact_path = tmp_path / "exact_campaign.py"
    exact_path.write_text(exact_source, encoding="utf-8", newline="\n")
    return check_p1_2_proof_obligations._fixed_witness_publish_binding_errors(
        exact_campaign_path=exact_path,
    )


def _move_child_final_status_after_precheck(source: str) -> str:
    source = _replace_once(source, '    scratch_state["final_status"] = "CERTIFIED"\n', "")
    precheck_call = (
        "    precheck_reason = terminal_certified_final_result_project_precheck_violation(\n"
        "        scratch_state,\n"
        "        project_root=project_root,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        precheck_call,
        precheck_call + '    scratch_state["final_status"] = "CERTIFIED"\n',
    )


def _child_rebinds_scratch_state(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["final_status"] = "CERTIFIED"\n',
        '    scratch_state["final_status"] = "CERTIFIED"\n'
        "    scratch_state = dict(authority_state)\n",
    )


def _child_aliases_scratch_state(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        "    s = scratch_state\n"
        '    s["declare_mode"] = "best_effort"\n',
    )


def _child_dunder_setitem_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    scratch_state.__setitem__("declare_mode", "best_effort")\n',
    )


def _child_dict_setitem_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    dict.__setitem__(scratch_state, "declare_mode", "best_effort")\n',
    )


def _child_operator_setitem_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    operator.setitem(scratch_state, "declare_mode", "best_effort")\n',
    )


def _child_getattr_setitem_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    getattr(scratch_state, "__setitem__")("declare_mode", "best_effort")\n',
    )


def _child_helper_call_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        "    _mutate(scratch_state)\n",
    )


def _child_augassign_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    scratch_state |= {"declare_mode": "best_effort"}\n',
    )


def _child_deletes_terminal_slot(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    del scratch_state["declare_mode"]\n',
    )


def _child_pop_terminal_slot(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["declare_mode"] = "strict"\n',
        '    scratch_state["declare_mode"] = "strict"\n'
        '    scratch_state.pop("declare_mode", None)\n',
    )


def _child_nested_update_clobber(source: str) -> str:
    last_stop_assignment = (
        '    scratch_state["last_stop_reason"] = {\n'
        "        \"reason\": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        \"status\": \"CERTIFIED\",\n"
        "    }\n"
    )
    return _replace_once(
        source,
        last_stop_assignment,
        last_stop_assignment
        + '    scratch_state["last_stop_reason"].update({"status": "CANDIDATE_PROPOSED"})\n',
    )


def _child_nested_slot_assignment_clobber(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["last_stop_reason"] = {\n'
        "        \"reason\": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        \"status\": \"CERTIFIED\",\n"
        "    }\n",
        '    scratch_state["last_stop_reason"] = {\n'
        "        \"reason\": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        \"status\": \"CERTIFIED\",\n"
        "    }\n"
        '    scratch_state["last_stop_reason"]["status"] = "CANDIDATE_PROPOSED"\n',
    )


def _child_shadows_precheck(source: str) -> str:
    return _replace_once(
        source,
        "    scratch_state = dict(authority_state)\n",
        "    terminal_certified_final_result_project_precheck_violation = lambda *_args, **_kwargs: None\n"
        "    scratch_state = dict(authority_state)\n",
    )


def _child_shadows_terminal_reason(source: str) -> str:
    return _replace_once(
        source,
        "    scratch_state = dict(authority_state)\n",
        '    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON = "not_terminal"\n'
        "    scratch_state = dict(authority_state)\n",
    )


def _child_wrong_project_root_precheck(source: str) -> str:
    precheck_call = (
        "    precheck_reason = terminal_certified_final_result_project_precheck_violation(\n"
        "        scratch_state,\n"
        "        project_root=project_root,\n"
        "    )\n"
    )
    wrong_precheck_call = precheck_call.replace("        project_root=project_root,\n", "        project_root=None,\n")
    return _replace_once(source, precheck_call, wrong_precheck_call)


def _child_ignores_precheck_result(source: str) -> str:
    return _replace_once(
        source,
        '    if precheck_reason is not None:\n'
        '        raise ValueError(f"terminal project precheck failed:{precheck_reason}")\n',
        "    if precheck_reason is not None:\n"
        "        pass\n",
    )


def _child_rhs_locals_setitem(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["candidates"] = durable_records\n',
        '    scratch_state["candidates"] = (locals()["scratch_state"].__setitem__("declare_mode", "best_effort") or durable_records)\n',
    )


def _child_rhs_ior_tuple(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["terminal_frontier_evidence"] = evidence\n',
        '    scratch_state["terminal_frontier_evidence"] = (scratch_state.__ior__({"declare_mode": "best_effort"}), evidence)[1]\n',
    )


def _child_rhs_walrus_alias(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["final_result"] = certified_final_result\n',
        '    scratch_state["final_result"] = ((alias := scratch_state).__setitem__("declare_mode", "best_effort") or certified_final_result)\n',
    )


def _child_rhs_exec(source: str) -> str:
    return _replace_once(
        source,
        '    scratch_state["candidates"] = durable_records\n',
        '    scratch_state["candidates"] = (exec("scratch_state[\\"declare_mode\\"] = \\"best_effort\\"") or durable_records)\n',
    )


def _child_global_globals_setitem(source: str) -> str:
    source = _replace_once(
        source,
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n",
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n"
        "    global scratch_state\n",
    )
    return _replace_once(
        source,
        '    scratch_state["candidates"] = durable_records\n',
        '    scratch_state["candidates"] = (globals().__setitem__("scratch_state", {"declare_mode": "best_effort"}) or durable_records)\n',
    )


def _child_local_def_shadow_precheck(source: str) -> str:
    import_block = (
        "    from src.search.pr2_l0_artifact_core import (\n"
        "        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        terminal_certified_final_result_project_precheck_violation,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        import_block,
        import_block
        + "    def terminal_certified_final_result_project_precheck_violation(*_args: object, **_kwargs: object) -> None:\n"
        + "        return None\n",
    )


def _child_imports_fake_precheck_module(source: str) -> str:
    return _replace_once(
        source,
        "    from src.search.pr2_l0_artifact_core import (\n",
        "    from fake.search.pr2_l0_artifact_core import (\n",
    )


def _child_setattr_monkeypatches_precheck(source: str) -> str:
    import_block = (
        "    from src.search.pr2_l0_artifact_core import (\n"
        "        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        terminal_certified_final_result_project_precheck_violation,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        import_block,
        "    import src.search.pr2_l0_artifact_core as artifact_core_module\n"
        '    setattr(artifact_core_module, "terminal_certified_final_result_project_precheck_violation", lambda *_args, **_kwargs: None)\n'
        + import_block,
    )


def _child_rebinds_project_root(source: str) -> str:
    return _replace_once(
        source,
        "    proposal_evidence = _require_mapping(\n",
        '    project_root = Path("/tmp/evil").resolve()\n'
        "    proposal_evidence = _require_mapping(\n",
    )


def _child_dead_nested_precheck_raise(source: str) -> str:
    return _replace_once(
        source,
        '    if precheck_reason is not None:\n'
        '        raise ValueError(f"terminal project precheck failed:{precheck_reason}")\n',
        "    if precheck_reason is not None:\n"
        "        if False:\n"
        '            raise ValueError(f"terminal project precheck failed:{precheck_reason}")\n',
    )


def _child_delays_precheck_consumption_after_return(source: str) -> str:
    consume = (
        '    if precheck_reason is not None:\n'
        '        raise ValueError(f"terminal project precheck failed:{precheck_reason}")\n'
    )
    return _replace_once(
        source,
        consume,
        '    return {"schema_version": DOMAIN_SCHEMA_VERSION}\n' + consume,
    )


def _child_mutates_evidence_after_precheck(source: str) -> str:
    consume = (
        '    if precheck_reason is not None:\n'
        '        raise ValueError(f"terminal project precheck failed:{precheck_reason}")\n'
    )
    return _replace_once(
        source,
        consume,
        consume + "    evidence.clear()\n    evidence.update(proposal_evidence)\n",
    )


def _child_rebinds_durable_records_after_precheck(source: str) -> str:
    consume = (
        '    if precheck_reason is not None:\n'
        '        raise ValueError(f"terminal project precheck failed:{precheck_reason}")\n'
    )
    return _replace_once(source, consume, consume + "    durable_records = replayed_records\n")


def _child_shadows_dict(source: str) -> str:
    return _replace_once(
        source,
        "    proposal_evidence = _require_mapping(\n",
        "    dict = _evil_dict\n"
        "    proposal_evidence = _require_mapping(\n",
    )


def _l0_parent_washes_declare_mode(source: str) -> str:
    return _replace_once(
        source,
        '        scratch_state["declare_mode"] = "strict"\n',
        '        scratch_state["declare_mode"] = str(authority_state.get("declare_mode", "best_effort"))\n',
    )


def _l0_transition_washes_declare_mode(source: str) -> str:
    return _replace_once(
        source,
        '    expected["declare_mode"] = "strict"\n',
        '    expected["declare_mode"] = str(proposal_state.get("declare_mode", "best_effort"))\n',
    )


def _exact_transition_update_clobbers_declare_mode(source: str) -> str:
    return _replace_once(
        source,
        '    expected["declare_mode"] = "strict"\n',
        '    expected["declare_mode"] = "strict"\n'
        '    dict.update(expected, {"declare_mode": "best_effort"})\n',
    )


def _l0_parent_augassign_ior_after_strict(source: str) -> str:
    return _replace_once(
        source,
        '        scratch_state["declare_mode"] = "strict"\n',
        '        scratch_state["declare_mode"] = "strict"\n'
        '        scratch_state |= {"declare_mode": "best_effort"}\n',
    )


def _l0_parent_alias_clobbers_declare_mode(source: str) -> str:
    return _replace_once(
        source,
        '        scratch_state["declare_mode"] = "strict"\n',
        '        scratch_state["declare_mode"] = "strict"\n'
        "        s = scratch_state\n"
        '        s["declare_mode"] = "best_effort"\n',
    )


def _l0_parent_dunder_ior_after_strict(source: str) -> str:
    return _replace_once(
        source,
        '        scratch_state["declare_mode"] = "strict"\n',
        '        scratch_state["declare_mode"] = "strict"\n'
        '        scratch_state.__ior__({"declare_mode": "best_effort"})\n',
    )


def _exact_transition_locals_mutator(source: str) -> str:
    return _replace_once(
        source,
        '    expected["declare_mode"] = "strict"\n',
        '    expected["declare_mode"] = "strict"\n'
        '    locals()["expected"].__setitem__("declare_mode", "best_effort")\n',
    )


def _l0_postwrite_dead_guard_token(source: str) -> str:
    return _replace_once(
        source,
        '    if str(disk_state.get("declare_mode")) != "strict":\n'
        '        return "postwrite_declare_mode_not_strict"\n',
        '    if False and str(disk_state.get("declare_mode")) != "strict":\n'
        '        return "postwrite_declare_mode_not_strict"\n',
    )


def _insert_child_before_proposal_evidence(source: str, injected: str) -> str:
    anchor = "    proposal_evidence = _require_mapping(\n"
    return _replace_once(source, anchor, injected + anchor)


def _child_exec_rebinds_precheck(source: str) -> str:
    return _insert_child_before_proposal_evidence(
        source,
        '    exec("global terminal_certified_final_result_project_precheck_violation\\n'
        'terminal_certified_final_result_project_precheck_violation = lambda *a, **k: None")\n',
    )


def _child_globals_subscript_rebinds_precheck(source: str) -> str:
    return _insert_child_before_proposal_evidence(
        source,
        '    globals()["terminal_certified_final_result_project_precheck_violation"] = '
        "terminal_certified_final_result_project_precheck_violation\n",
    )


def _child_import_alias_rebinds_precheck(source: str) -> str:
    return _insert_child_before_proposal_evidence(
        source,
        "    import src.search.pr2_l0_artifact_core as _authority_module\n"
        "    _authority_module.terminal_certified_final_result_project_precheck_violation = "
        "terminal_certified_final_result_project_precheck_violation\n",
    )


def _child_frame_globals_rebinds_precheck(source: str) -> str:
    return _insert_child_before_proposal_evidence(
        source,
        '    sys._getframe(0).f_globals["terminal_certified_final_result_project_precheck_violation"] = '
        "terminal_certified_final_result_project_precheck_violation\n",
    )


def _child_dunder_dict_rebind_surface(source: str) -> str:
    return _insert_child_before_proposal_evidence(
        source,
        "    terminal_certified_final_result_project_precheck_violation.__dict__\n",
    )


def _disable_pr2_5_closed_world_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    def _legacy_accepts(*_args: object, **_kwargs: object) -> list[str]:
        return []

    def _legacy_function_def(
        tree: ast.Module,
        name: str,
        *,
        path: Path = check_p1_2_proof_obligations.LIFECYCLE_PATH,
    ) -> ast.FunctionDef:
        del path
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise check_p1_2_proof_obligations.CheckError(f"missing function {name}")

    for helper_name in (
        "_check_child_module_toplevel_closed_world",
        "_check_true_verifier_child_module_closed_world",
        "_check_true_verifier_child_closed_world",
        "_check_true_verifier_child_domain_elevation_window",
        "_check_true_verifier_child_return_dict_closed_world",
        "_check_function_import_time_shape",
        "_check_child_runtime_function_closed_world",
        "_check_child_class_closed_world",
        "_check_unique_top_level_bindings",
        "_check_top_level_body_closed_world",
        "_check_child_unique_final_return",
        "_check_child_precheck_call_exact",
        "_check_supervisor_transition_strict_prefix_closed_world",
        "_check_postwrite_strict_guard_prefix_closed_world",
        "_check_no_direct_top_level_exit_before_node",
        "_check_live_top_level_postwrite_guard",
        "_check_l0_child_verdict_dataflow",
        "_check_l0_runtime_tcb_bindings",
        "_check_true_child_runtime_tcb_source_pins",
        "_check_exact_runtime_tcb_source_pins",
    ):
        monkeypatch.setattr(check_p1_2_proof_obligations, helper_name, _legacy_accepts)
    monkeypatch.setattr(
        check_p1_2_proof_obligations,
        "_return_domain_uses_canonical_names",
        lambda _stmt: True,
    )
    monkeypatch.setattr(check_p1_2_proof_obligations, "_function_def", _legacy_function_def)


def _disable_pr2_5_g6_prefix_pins(monkeypatch: pytest.MonkeyPatch) -> None:
    def _legacy_accepts(*_args: object, **_kwargs: object) -> list[str]:
        return []

    for helper_name in (
        "_check_supervisor_transition_strict_prefix_closed_world",
        "_check_postwrite_strict_guard_prefix_closed_world",
        "_check_l0_runtime_tcb_bindings",
        "_check_exact_runtime_tcb_source_pins",
    ):
        monkeypatch.setattr(check_p1_2_proof_obligations, helper_name, _legacy_accepts)


def _child_early_return_before_precheck(source: str) -> str:
    return _replace_once(
        source,
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n"
        "    required = {\n",
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n"
        '    return {"schema_version": DOMAIN_SCHEMA_VERSION}\n'
        "    required = {\n",
    )


def _child_code_object_monkeypatches_precheck(source: str) -> str:
    import_block = (
        "    from src.search.pr2_l0_artifact_core import (\n"
        "        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        terminal_certified_final_result_project_precheck_violation,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        import_block,
        import_block
        + "    def _noop_precheck(*_args: object, **_kwargs: object) -> None:\n"
        + "        return None\n"
        + "    terminal_certified_final_result_project_precheck_violation.__code__ = _noop_precheck.__code__\n",
    )


def _child_globals_monkeypatches_precheck(source: str) -> str:
    import_block = (
        "    from src.search.pr2_l0_artifact_core import (\n"
        "        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        terminal_certified_final_result_project_precheck_violation,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        import_block,
        import_block
        + "    def _noop_precheck(*_args: object, **_kwargs: object) -> None:\n"
        + "        return None\n"
        + '    terminal_certified_final_result_project_precheck_violation.__globals__["terminal_certified_final_result_project_precheck_violation"] = _noop_precheck\n',
    )


def _child_importfrom_builtins_setattr_alias(source: str) -> str:
    import_block = (
        "    from src.search.pr2_l0_artifact_core import (\n"
        "        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        terminal_certified_final_result_project_precheck_violation,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        import_block,
        import_block
        + "    from builtins import setattr as _b\n"
        + '    _b(terminal_certified_final_result_project_precheck_violation, "__doc__", "patched")\n',
    )


def _child_builtins_dict_facade(source: str) -> str:
    return _insert_child_before_proposal_evidence(
        source,
        '    __builtins__["dict"] = _evil_dict\n',
    )


def _child_module_top_level_monkeypatch(source: str) -> str:
    return _replace_once(
        source,
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n",
        "from src.search import pr2_l0_artifact_core as _m\n"
        "_m.terminal_certified_final_result_project_precheck_violation = lambda *_args, **_kwargs: None\n"
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n",
    )


def _child_return_unpack_overrides_domain(source: str) -> str:
    return _replace_once(
        source,
        '        "fixed_witness_violations": {},\n'
        '        "tcb": {\n',
        '        "fixed_witness_violations": {},\n'
        "        **evil_domain,\n"
        '        "tcb": {\n',
    )


def _child_return_tcb_side_effect_call(source: str) -> str:
    tcb_block = (
        '        "tcb": {\n'
        '            "python_interpreter": "NAMED-TCB",\n'
        '            "stdlib": "NAMED-TCB",\n'
        '            "third_party_native": "NAMED-TCB",\n'
        '            "os_process_file_isolation": "NAMED-TCB",\n'
        '            "windows_write_isolation_residual": "protocol_only_child_snapshot_no_write_fd_pr2c_linux_uid_namespace_pending",\n'
        "        },\n"
    )
    return _replace_once(
        source,
        tcb_block,
        '        "tcb": _evil_mutate_mapping(evidence),\n'
        '        # "third_party_native": "NAMED-TCB"\n'
        '        # "windows_write_isolation_residual"\n',
    )


def _child_precheck_extra_kwarg(source: str) -> str:
    return _replace_once(
        source,
        "        project_root=project_root,\n"
        "    )\n",
        "        project_root=project_root,\n"
        "        weaken_terminal=True,\n"
        "    )\n",
    )


def _l0_child_verdict_forged_rebind(source: str) -> str:
    return _replace_once(
        source,
        "        if child_verdict.status != SEALED:\n",
        "        child_verdict = L0MicroVerdict(\n"
        "            status=SEALED,\n"
        "            nonce=nonce,\n"
        '            reason="forged_child_verdict",\n'
        "            floor_digest=child_verdict.floor_digest,\n"
        "            response=child_verdict.response,\n"
        "        )\n"
        "        if child_verdict.status != SEALED:\n",
    )


def _l0_transition_starts_with_return(source: str) -> str:
    return _replace_once(
        source,
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
        "    return None\n"
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
    )


def _l0_transition_starts_with_true_return_branch(source: str) -> str:
    return _replace_once(
        source,
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
        "    if True:\n"
        "        return None\n"
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
    )


def _exact_transition_starts_with_return(source: str) -> str:
    return _replace_once(
        source,
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
        "    return None\n"
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
    )


def _exact_transition_starts_with_true_return_branch(source: str) -> str:
    return _replace_once(
        source,
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
        "    if True:\n"
        "        return None\n"
        '    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:\n',
    )


def _l0_postwrite_starts_with_return(source: str) -> str:
    return _replace_once(
        source,
        "    if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:\n",
        "    return None\n"
        "    if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:\n",
    )


def _l0_postwrite_starts_with_true_return_branch(source: str) -> str:
    return _replace_once(
        source,
        "    if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:\n",
        "    if True:\n"
        "        return None\n"
        "    if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:\n",
    )


def _child_duplicate_verify_supervisor_domain(source: str) -> str:
    return (
        source
        + "\n\ndef _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n"
        + "    del payload, nonce\n"
        + '    return {"schema_version": DOMAIN_SCHEMA_VERSION}\n'
    )


def _l0_duplicate_run_l0_supervisor_seal(source: str) -> str:
    return (
        source
        + "\n\ndef run_l0_supervisor_seal(request: SupervisorSealRequest) -> L0MicroVerdict:\n"
        + "    del request\n"
        + "    return _reject(\"\", \"forged_duplicate\")\n"
    )


def _exact_duplicate_transition_helper(source: str) -> str:
    return (
        source
        + "\n\ndef _supervisor_certified_transition_violation(\n"
        + "    proposal_state: Mapping[str, Any],\n"
        + "    certified_state: Mapping[str, Any],\n"
        + "    *,\n"
        + "    seal_record: Mapping[str, Any],\n"
        + ") -> str | None:\n"
        + "    del proposal_state, certified_state, seal_record\n"
        + "    return None\n"
    )


def _child_decorated_verify_supervisor_domain(source: str) -> str:
    return _replace_once(
        source,
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n",
        "@verify\n"
        "def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:\n",
    )


def _child_top_level_rebinds_verify(source: str) -> str:
    return source + "\n\nverify = _verify_supervisor_domain\n"


def _child_helper_code_swap(source: str) -> str:
    return _replace_once(
        source,
        "def _materialize_import_default_artifacts(project_root: Path) -> None:\n"
        "    del project_root\n",
        "def _materialize_import_default_artifacts(project_root: Path) -> None:\n"
        "    del project_root\n"
        "    _canonical_digest.__code__ = _json_copy.__code__\n",
    )


def _child_shadows_getattr(source: str) -> str:
    return _insert_child_before_proposal_evidence(source, "    getattr = _fake_getattr\n")


def _child_class_body_side_effect(source: str) -> str:
    return _replace_once(
        source,
        "class _StdlibOnlyPathFinder:\n"
        "    def __init__(self, stdlib_paths: list[Path]) -> None:\n",
        "class _StdlibOnlyPathFinder:\n"
        "    injected = _evil_import_time_call()\n"
        "    def __init__(self, stdlib_paths: list[Path]) -> None:\n",
    )


def _l0_transition_returns_after_strict(source: str) -> str:
    return _replace_once(
        source,
        '    expected["declare_mode"] = "strict"\n',
        '    expected["declare_mode"] = "strict"\n'
        "    return None\n",
    )


def _exact_transition_returns_after_strict(source: str) -> str:
    return _replace_once(
        source,
        '    expected["declare_mode"] = "strict"\n',
        '    expected["declare_mode"] = "strict"\n'
        "    return None\n",
    )


def _l0_postwrite_returns_after_strict_guard(source: str) -> str:
    return _replace_once(
        source,
        '    if str(disk_state.get("declare_mode")) != "strict":\n'
        '        return "postwrite_declare_mode_not_strict"\n',
        '    if str(disk_state.get("declare_mode")) != "strict":\n'
        '        return "postwrite_declare_mode_not_strict"\n'
        "    return None\n",
    )


def _l0_object_setattr_forges_child_verdict(source: str) -> str:
    return _replace_once(
        source,
        "        if child_verdict.status != SEALED:\n",
        '        object.__setattr__(child_verdict, "response", {"domain": {}})\n'
        "        if child_verdict.status != SEALED:\n",
    )


def _l0_domain_update_after_assignment(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        '        domain.update({"final_result_digest": "0" * 64})\n',
    )


def _l0_child_verdict_response_update(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        '        child_verdict.response.update({"domain": {}})\n',
    )


def _l0_child_payload_update_after_verdict(source: str) -> str:
    return _replace_once(
        source,
        "        if child_verdict.status != SEALED:\n",
        '        child_payload.update({"proposal_final_result_digest": "0" * 64})\n'
        "        if child_verdict.status != SEALED:\n",
    )


def _l0_type_setitem_domain(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        '        type(domain).__setitem__(domain, "candidate_records_digest", "0" * 64)\n',
    )


def _l0_class_setitem_domain(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        '        domain.__class__.__setitem__(domain, "candidate_records_digest", "0" * 64)\n',
    )


def _child_verify_echoes_payload_domain(source: str) -> str:
    old = (
        "    try:\n"
        '        _install_third_party_floor(payload.get("dependency_floor"))\n'
        "        domain = _verify_supervisor_domain(payload, nonce=nonce)\n"
        "    except Exception as exc:  # noqa: BLE001\n"
        '        detail = "|".join(traceback.format_exc(limit=8).splitlines()[-8:])\n'
        "        return {\n"
        '            "verdict": REJECTED,\n'
        '            "nonce": nonce,\n'
        '            "reason": f"true_verifier_exception:{type(exc).__name__}:{exc}:{detail}",\n'
        "        }\n"
        "    return {\n"
        '        "verdict": SEALED,\n'
        '        "nonce": nonce,\n'
        '        "reason": "domain_verified",\n'
        '        "domain": domain,\n'
        "    }\n"
    )
    new = (
        "    return {\n"
        '        "verdict": SEALED,\n'
        '        "nonce": nonce,\n'
        '        "reason": "domain_verified",\n'
        '        "domain": dict(payload.get("authority_state", {})),\n'
        "    }\n"
    )
    return _replace_once(source, old, new)


def _exact_terminal_final_result_returns_none_before_frontier(source: str) -> str:
    return _replace_once(
        source,
        "    if not has_terminal_full_frontier_certified_evidence(state):\n",
        "    return None\n"
        "    if not has_terminal_full_frontier_certified_evidence(state):\n",
    )


def _exact_terminal_precheck_returns_none_before_reason(source: str) -> str:
    return _replace_once(
        source,
        "    reason = terminal_certified_final_result_violation(\n",
        "    if True:\n"
        "        return None\n"
        "    reason = terminal_certified_final_result_violation(\n",
    )


def _exact_validate_terminal_solution_returns_none_early(source: str) -> str:
    return _replace_once(
        source,
        '    placement_solution = final_result.get("placement_solution")\n',
        "    return None\n"
        '    placement_solution = final_result.get("placement_solution")\n',
    )


def _exact_ghost_pick_returns_none_early(source: str) -> str:
    return _replace_once(
        source,
        '    ghost_rect = final_result.get("ghost_rect")\n',
        "    return None\n"
        '    ghost_rect = final_result.get("ghost_rect")\n',
    )


def _child_project_records_return_before_replay(source: str) -> str:
    return _replace_once(
        source,
        "    response = _execute_isolated_replay_request(request)\n",
        "    return {\n"
        "        str(key): _json_copy(value)\n"
        "        for key, value in raw_records.items()\n"
        "        if isinstance(value, Mapping)\n"
        "    }, {}\n"
        "    response = _execute_isolated_replay_request(request)\n",
    )


def _child_fixed_witness_returns_early(source: str) -> str:
    return _replace_once(
        source,
        "    from src.search.pr2_l0_replay_core import _materialize_replay_snapshot\n",
        "    return {}, {}, None\n"
        "    from src.search.pr2_l0_replay_core import _materialize_replay_snapshot\n",
    )


def _l0_domain_violation_guard_and_false(source: str) -> str:
    return _replace_once(
        source,
        "        if domain_violation is not None:\n",
        "        if domain_violation is not None and False:\n",
    )


def _l0_seal_violation_guard_and_false(source: str) -> str:
    return _replace_once(
        source,
        "        if seal_violation is not None:\n",
        "        if seal_violation is not None and False:\n",
    )


def _l0_postwrite_violation_guard_and_false(source: str) -> str:
    return _replace_once(
        source,
        "                if postwrite_violation is not None:\n",
        "                if postwrite_violation is not None and False:\n",
    )


def _l0_seal_state_returns_none_early(source: str) -> str:
    return _replace_once(
        source,
        "def _supervisor_seal_state_violation_l0(value: Any, *, state: Mapping[str, Any]) -> str | None:\n"
        "    keys = {\n",
        "def _supervisor_seal_state_violation_l0(value: Any, *, state: Mapping[str, Any]) -> str | None:\n"
        "    return None\n"
        "    keys = {\n",
    )


def _child_loader_injects_extra_method(source: str) -> str:
    return _replace_once(
        source,
        "class _StdlibOnlyPathFinder:\n"
        "    def __init__(self, stdlib_paths: list[Path]) -> None:\n",
        "class _StdlibOnlyPathFinder:\n"
        "    def __init_subclass__(cls) -> None:\n"
        "        return None\n"
        "\n"
        "    def __init__(self, stdlib_paths: list[Path]) -> None:\n",
    )


def _child_source_loader_skips_digest_rehash(source: str) -> str:
    return _replace_once(
        source,
        "    def get_data(self, path: str) -> bytes:\n"
        "        data = super().get_data(path)\n"
        "        if hashlib.sha256(data).hexdigest() != self._expected_sha256:\n"
        '            raise ImportError(f"dependency floor load-time digest mismatch:{path}")\n'
        "        return data\n",
        "    def get_data(self, path: str) -> bytes:\n"
        "        return super().get_data(path)\n",
    )


def _child_non_domain_helper_shadows_getattr(source: str) -> str:
    return _replace_once(
        source,
        "def _materialize_import_default_artifacts(project_root: Path) -> None:\n"
        "    del project_root\n",
        "def _materialize_import_default_artifacts(project_root: Path) -> None:\n"
        "    getattr = _json_copy\n"
        "    del project_root\n",
    )


def _l0_domain_container_alias_mutation(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        "        boxed_domain = [domain]\n"
        '        boxed_domain[0]["final_result_digest"] = "0" * 64\n',
    )


def _child_clobbers_replay_violations(source: str) -> str:
    return _replace_once(
        source,
        "    if replay_violations:\n",
        "    replay_violations = {}\n"
        "    if replay_violations:\n",
    )


def _child_clobbers_fixed_verdict(source: str) -> str:
    return _replace_once(
        source,
        '    if getattr(fixed_verdict, "publishable", False) is not True:\n',
        "    fixed_verdict = object()\n"
        '    if getattr(fixed_verdict, "publishable", False) is not True:\n',
    )


def _child_clobbers_fixed_violations(source: str) -> str:
    return _replace_once(
        source,
        "    if fixed_violations:\n",
        "    fixed_violations = {}\n"
        "    if fixed_violations:\n",
    )


def _child_clobbers_envelope_violation(source: str) -> str:
    return _replace_once(
        source,
        "    if envelope_violation is not None:\n",
        "    envelope_violation = None\n"
        "    if envelope_violation is not None:\n",
    )


def _child_clobbers_replay_status(source: str) -> str:
    return _replace_once(
        source,
        "        if replay_status != claimed_status:\n",
        "        replay_status = claimed_status\n"
        "        if replay_status != claimed_status:\n",
    )


def _child_clobbers_terminal_fixed_witness_verdict(source: str) -> str:
    return _replace_once(
        source,
        "        )\n    durable_records = _copy_candidate_records(candidate_records)\n",
        "        )\n"
        "        verdict = object()\n"
        "    durable_records = _copy_candidate_records(candidate_records)\n",
    )


def _exact_clobbers_stop_reason(source: str) -> str:
    return _replace_once(
        source,
        "    if stop_reason is not None:\n",
        "    stop_reason = None\n"
        "    if stop_reason is not None:\n",
    )


def _exact_clobbers_search_stats_reason(source: str) -> str:
    return _replace_once(
        source,
        "    if search_stats_reason is not None:\n",
        "    search_stats_reason = None\n"
        "    if search_stats_reason is not None:\n",
    )


def _exact_clobbers_final_objective(source: str) -> str:
    return _replace_once(
        source,
        "    final_objective = _candidate_objective_from_rect(ghost_w, ghost_h)\n",
        "    final_objective = _candidate_objective_from_rect(ghost_w, ghost_h)\n"
        "    final_objective = (99999, 99999)\n",
    )


def _exact_clobbers_best_empty_objective(source: str) -> str:
    return _replace_once(
        source,
        "    claimed_objective = (int(ghost_w) * int(ghost_h), min(int(ghost_w), int(ghost_h)))\n",
        "    best_empty_objective = (0, 0)\n"
        "    claimed_objective = (int(ghost_w) * int(ghost_h), min(int(ghost_w), int(ghost_h)))\n",
    )


def _exact_clobbers_expected_pose_idx(source: str) -> str:
    return _replace_once(
        source,
        "        if expected_pose_idx is None or int(pose_idx) != int(expected_pose_idx):\n",
        "        expected_pose_idx = int(pose_idx)\n"
        "        if expected_pose_idx is None or int(pose_idx) != int(expected_pose_idx):\n",
    )


def _l0_tampers_scratch_state_after_seal_gate(source: str) -> str:
    return _replace_once(
        source,
        "        pending_state_bytes = _atomic_json_bytes(scratch_state)\n",
        '        scratch_state["candidates"] = {}\n'
        "        pending_state_bytes = _atomic_json_bytes(scratch_state)\n",
    )


def _l0_forges_helper_after_seal_gate(source: str) -> str:
    return _replace_once(
        source,
        "        pending_state_bytes = _atomic_json_bytes(scratch_state)\n",
        "        def _forge_self_consistent_certificate() -> None:\n"
        '            scratch_state["candidates"] = {}\n'
        "        _forge_self_consistent_certificate()\n"
        "        pending_state_bytes = _atomic_json_bytes(scratch_state)\n",
    )


def _l0_bound_update_alias(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        "        mutator = domain.update\n"
        '        mutator({"final_result_digest": "0" * 64})\n',
    )


def _l0_getattr_update_alias(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        '        mutator = getattr(domain, "update")\n'
        '        mutator({"final_result_digest": "0" * 64})\n',
    )


def _l0_dict_unpack_alias_mutation(source: str) -> str:
    return _replace_once(
        source,
        '        domain = child_verdict.response.get("domain")\n',
        '        domain = child_verdict.response.get("domain")\n'
        "        domain_copy = {**domain}\n"
        '        domain_copy.update({"final_result_digest": "0" * 64})\n',
    )


def _exact_terminal_final_result_returns_true_before_frontier(source: str) -> str:
    return _replace_once(
        source,
        "    if not has_terminal_full_frontier_certified_evidence(state):\n",
        "    return True\n"
        "    if not has_terminal_full_frontier_certified_evidence(state):\n",
    )


def _exact_terminal_precheck_raises_before_reason(source: str) -> str:
    return _replace_once(
        source,
        "    reason = terminal_certified_final_result_violation(\n",
        '    raise RuntimeError("skip terminal precheck")\n'
        "    reason = terminal_certified_final_result_violation(\n",
    )


def _exact_validate_terminal_solution_returns_true_early(source: str) -> str:
    return _replace_once(
        source,
        '    placement_solution = final_result.get("placement_solution")\n',
        "    return True\n"
        '    placement_solution = final_result.get("placement_solution")\n',
    )


def _exact_ghost_pick_raises_early(source: str) -> str:
    return _replace_once(
        source,
        '    ghost_rect = final_result.get("ghost_rect")\n',
        '    raise RuntimeError("skip ghost pick binding")\n'
        '    ghost_rect = final_result.get("ghost_rect")\n',
    )


def _child_clears_replay_violations(source: str) -> str:
    anchor = (
        "    replayed_records, replay_violations = _project_candidate_records_direct(\n"
        "        state=authority_state,\n"
        "        project_root=project_root,\n"
        "        strong_keys=strong_keys,\n"
        "    )\n"
    )
    return _replace_once(source, anchor, anchor + "    replay_violations.clear()\n")


def _child_dead_branches_project_records_after_prebind(source: str) -> str:
    anchor = (
        "    replayed_records, replay_violations = _project_candidate_records_direct(\n"
        "        state=authority_state,\n"
        "        project_root=project_root,\n"
        "        strong_keys=strong_keys,\n"
        "    )\n"
    )
    replacement = (
        "    replay_violations = {}\n"
        "    if False:\n"
        "        replayed_records, replay_violations = _project_candidate_records_direct(\n"
        "            state=authority_state,\n"
        "            project_root=project_root,\n"
        "            strong_keys=strong_keys,\n"
        "        )\n"
    )
    return _replace_once(source, anchor, replacement)


def _child_swallows_replay_gate(source: str) -> str:
    gate = (
        "    if replay_violations:\n"
        "        first_key = sorted(replay_violations)[0]\n"
        "        raise ValueError(f\"terminal candidate sink replay failed:{replay_violations[first_key]}\")\n"
    )
    replacement = (
        "    try:\n"
        "        if replay_violations:\n"
        "            first_key = sorted(replay_violations)[0]\n"
        "            raise ValueError(f\"terminal candidate sink replay failed:{replay_violations[first_key]}\")\n"
        "    except Exception:\n"
        "        pass\n"
    )
    return _replace_once(source, gate, replacement)


def _child_switches_replayed_records_sibling(source: str) -> str:
    gate = (
        "    if replay_violations:\n"
        "        first_key = sorted(replay_violations)[0]\n"
        "        raise ValueError(f\"terminal candidate sink replay failed:{replay_violations[first_key]}\")\n"
    )
    return _replace_once(
        source,
        gate,
        gate + '    replayed_records = dict(authority_state.get("candidates", {}))\n',
    )


def _child_mutates_fixed_verdict_publishable(source: str) -> str:
    anchor = (
        "    durable_records, public_records, fixed_verdict = _run_fixed_witness_direct(\n"
        "        state=authority_state,\n"
        "        project_root=project_root,\n"
        "        candidate_records=replayed_records,\n"
        "        final_result=certified_final_result,\n"
        "    )\n"
    )
    return _replace_once(source, anchor, anchor + "    fixed_verdict.publishable = True\n")


def _child_clears_durable_records_after_fixed_witness(source: str) -> str:
    gate = (
        "    if fixed_violations:\n"
        "        first_key = sorted(fixed_violations)[0]\n"
        "        raise ValueError(f\"terminal fixed witness verifier failed:{fixed_violations[first_key]}\")\n"
    )
    return _replace_once(source, gate, gate + "    durable_records.clear()\n")


def _child_project_records_empties_strong_keys(source: str) -> str:
    anchor = (
        "    if not isinstance(raw_records, Mapping):\n"
        "        return {}, {\"*\": \"candidate_sink_replay_records_missing\"}\n"
    )
    return _replace_once(source, anchor, anchor + "    strong_keys = []\n")


def _l0_appends_round_trip_stub(source: str) -> str:
    return (
        source
        + "\n\ndef run_l0_micro_verifier_round_trip(*args, **kwargs):\n"
        + "    return L0MicroVerdict(status=SEALED, nonce=\"forged\", reason=\"forged\", response={\"domain\": {}})\n"
    )


def _l0_rebinds_true_verifier_module(source: str) -> str:
    return _replace_once(
        source,
        'TRUE_VERIFIER_MODULE = "src.search.pr2_l0_true_verifier_child"',
        'TRUE_VERIFIER_MODULE = "src.search.pr2_l0_forged_child"',
    )


def _l0_noops_domain_response_violation(source: str) -> str:
    anchor = (
        "def _domain_response_violation(\n"
        "    domain: Any,\n"
        "    *,\n"
        "    nonce: str,\n"
        "    strong_keys: Sequence[str],\n"
        "    proposal_final_result_digest: str,\n"
        "    proposal_evidence_digest: str,\n"
        "    proposal_candidate_records_digest: str,\n"
        ") -> str | None:\n"
    )
    return _replace_once(source, anchor, anchor + "    return None\n")


def _l0_shadows_dict_top_level(source: str) -> str:
    return _replace_once(
        source,
        "from typing import Any, Mapping, Sequence\n\n",
        "from typing import Any, Mapping, Sequence\n\ndict = lambda *args, **kwargs: {}\n\n",
    )


def _exact_noops_unsupervised_certified_guard(source: str) -> str:
    return _replace_once(
        source,
        '    """Return True when a checkpoint tries to mint terminal CERTIFIED state."""\n\n',
        '    """Return True when a checkpoint tries to mint terminal CERTIFIED state."""\n\n'
        "    return False\n",
    )


def _exact_save_dead_branches_unsupervised_guard(source: str) -> str:
    return _replace_once(
        source,
        "            if _has_unsupervised_certified_checkpoint_claim(checked_state):\n",
        "            if False and _has_unsupervised_certified_checkpoint_claim(checked_state):\n",
    )


def _exact_final_objective_compare_pass(source: str) -> str:
    return _replace_once(
        source,
        '            return "terminal_certified_final_result_not_best_candidate"\n',
        "            pass\n",
    )


def _exact_best_empty_compare_pass(source: str) -> str:
    return _replace_once(
        source,
        '        return "terminal_certified_final_result_layout_has_better_empty_rect"\n',
        "        pass\n",
    )


def _child_replay_status_compare_pass(source: str) -> str:
    gate = (
        "        if replay_status != claimed_status:\n"
        "            violations[key] = (\n"
        "                f\"candidate_sink_replay_status_mismatch:{key}:\"\n"
        "                f\"claimed={claimed_status}:replayed={replay_status}\"\n"
        "            )\n"
        "            continue\n"
    )
    return _replace_once(source, gate, "        if replay_status != claimed_status:\n            pass\n")


_PR2_ROUND9_GATE_HELPERS = (
    ("child", "_canonical_bytes"),
    ("child", "_canonical_digest"),
    ("child", "_dependency_file_top_level"),
    ("child", "_dependency_floor_root"),
    ("child", "_dependency_named_tcb_violation"),
    ("child", "_index_dependency_package_dirs"),
    ("child", "_install_third_party_floor"),
    ("child", "_is_lower_sha256"),
    ("child", "_json_copy"),
    ("child", "_materialize_import_default_artifacts"),
    ("child", "_require_mapping"),
    ("child", "_safe_rel"),
    ("child", "_stable_fixed_witness_candidate_records"),
    ("child", "_stable_fixed_witness_payload"),
    ("child", "_stdlib_paths"),
    ("child", "_strict_int"),
    ("child", "_strict_string"),
    ("child", "_string_list"),
    ("child", "_valid_top_level_name"),
    ("exact", "_atomic_json_bytes"),
    ("exact", "_atomic_write_json_bytes"),
    ("exact", "_best_empty_rect_objective"),
    ("exact", "_build_occupancy_prefix"),
    ("exact", "_candidate_objective_from_rect"),
    ("exact", "_certified_state_payload_sha256"),
    ("exact", "_checkpoint_write_lock"),
    ("exact", "_empty_rect_exists"),
    ("exact", "_expected_unfiltered_ghost_anchor_index"),
    ("exact", "_final_result_certified_transition"),
    ("exact", "_fsync_directory"),
    ("exact", "_is_authorized_exact_pose_optional_solution_entry"),
    ("exact", "_is_lower_sha256"),
    ("exact", "_load_exact_facility_pools"),
    ("exact", "_load_exact_facility_templates"),
    ("exact", "_load_exact_grid_dimensions"),
    ("exact", "_load_exact_min_side_admissibility"),
    ("exact", "_load_exact_required_optional_lower_bounds"),
    ("exact", "_load_exact_safe_area_upper_bound"),
    ("exact", "_load_sealed_proposal_authority"),
    ("exact", "_load_validated_mandatory_exact_instances"),
    ("exact", "_loads_strict_json_object"),
    ("exact", "_mandatory_solution_entry_metadata_violation"),
    ("exact", "_nonnegative_number"),
    ("exact", "_occupied_count_in_rect"),
    ("exact", "_path_has_symlink_component"),
    ("exact", "_pose_occupied_cells"),
    ("exact", "_pose_optional_solution_entry_metadata_violation"),
    ("exact", "_pose_pool_min_occupied_cell_count"),
    ("exact", "_pose_power_coverage_cells"),
    ("exact", "_proposal_state_violation"),
    ("exact", "_snapshot_campaign_state_for_nonterminal_save"),
    ("exact", "_solution_without_ghost_marker"),
    ("exact", "_strict_candidate_ghost_rect"),
    ("exact", "_strict_nonempty_string"),
    ("exact", "_strict_resume_int"),
    ("exact", "_strict_resume_timestamp"),
    ("exact", "_supervisor_certified_transition_violation"),
    ("exact", "_supervisor_seal_state_violation"),
    ("exact", "_terminal_candidate_ghost_pick_binding_violation"),
    ("exact", "_terminal_certified_ghost_rect_unknown_field"),
    ("exact", "_terminal_certified_last_stop_reason_violation"),
    ("exact", "_terminal_certified_search_stats_violation"),
    ("exact", "_terminal_certified_solution_entry_unknown_field"),
    ("exact", "_terminal_solution_entry_pose_metadata_violation"),
    ("exact", "_valid_campaign_instance_id"),
    ("exact", "_valid_supervisor_proposal_run_id"),
    ("exact", "_validate_terminal_solution_against_project"),
    ("exact", "_validated_mandatory_exact_instances_payload"),
    ("exact", "candidate_key"),
    ("exact", "compute_certified_exact_source_digest"),
    ("artifact_core", "compute_exact_artifact_hashes"),
    ("exact", "has_terminal_full_frontier_certified_evidence"),
    ("exact", "now_iso"),
    ("exact", "now_ts"),
    ("exact", "sha256_file"),
    ("artifact_core", "terminal_certified_final_result_project_precheck_violation"),
    ("exact", "terminal_certified_final_result_violation"),
    ("l0", "_atomic_json_bytes"),
    ("l0", "_canonical_bytes"),
    ("l0", "_certified_state_payload_sha256_l0"),
    ("l0", "_checkpoint_write_lock_l0"),
    ("l0", "_dependency_file_top_level"),
    ("l0", "_dependency_floor_root"),
    ("l0", "_dependency_named_tcb_violation"),
    ("l0", "_is_lower_sha256"),
    ("l0", "_json_bytes"),
    ("l0", "_load_dependency_floor_manifest_bytes"),
    ("l0", "_load_sealed_proposal_authority_l0"),
    ("l0", "_materialize_snapshot_import_defaults"),
    ("l0", "_now_iso"),
    ("l0", "_parse_mapping"),
    ("l0", "_path_has_symlink_component"),
    ("l0", "_postwrite_state_violation"),
    ("l0", "_proposal_authority_violation"),
    ("l0", "_proposal_ready_marker_violation"),
    ("l0", "_proposal_state_violation"),
    ("l0", "_require_mapping"),
    ("l0", "_safe_manifest_relpath"),
    ("l0", "_stable_fixed_witness_payload_l0"),
    ("l0", "_strict_int"),
    ("l0", "_strict_timestamp"),
    ("l0", "_strong_proof_binding_violation"),
    ("l0", "_strong_status_keys"),
    ("l0", "_supervisor_certified_transition_violation_l0"),
    ("l0", "_valid_campaign_instance_id"),
    ("l0", "_valid_dependency_top_level"),
    ("l0", "_valid_supervisor_proposal_run_id"),
    ("l0", "loads_l0_strict_json"),
)


def _round9_hollow_return_source(helper_name: str) -> str:
    if helper_name == "_strong_status_keys" or helper_name.endswith("_paths"):
        return "[]"
    if (
        "mapping" in helper_name
        or "payload" in helper_name
        or "records" in helper_name
        or helper_name.endswith("_bytes")
    ):
        return "{}"
    return "None"


def _find_round9_helper_node(tree: ast.Module, helper_name: str) -> ast.FunctionDef:
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == helper_name:
            return stmt
    raise AssertionError(f"round-9 helper not found: {helper_name}")


def _hollow_round9_helper(source: str, helper_name: str) -> str:
    tree = ast.parse(source)
    function = _find_round9_helper_node(tree, helper_name)
    assert function.body
    insertion_line = function.body[0].lineno - 1
    lines = source.splitlines(keepends=True)
    first_body_line = lines[insertion_line]
    indent = first_body_line[: len(first_body_line) - len(first_body_line.lstrip())]
    inserted = f"{indent}return {_round9_hollow_return_source(helper_name)}\n"
    return "".join(lines[:insertion_line] + [inserted] + lines[insertion_line:])


def test_p1_2_checker_accepts_pr2_supervisor_ast_pins_current_sources(tmp_path: Path) -> None:
    errors = _candidate_sink_replay_errors_for_sources(tmp_path)

    assert errors == []


@pytest.mark.parametrize(
    ("source_kind", "helper_name"),
    _PR2_ROUND9_GATE_HELPERS,
    ids=[f"round9-{source_kind}-{helper_name}" for source_kind, helper_name in _PR2_ROUND9_GATE_HELPERS],
)
def test_p1_2_checker_rejects_pr2_5_round9_gate_helper_hollows(
    tmp_path: Path,
    source_kind: str,
    helper_name: str,
) -> None:
    child_source = l0_source = exact_source = artifact_core_source = None
    if source_kind == "child":
        child_source = _hollow_round9_helper(
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            ),
            helper_name,
        )
    elif source_kind == "l0":
        l0_source = _hollow_round9_helper(
            check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            ),
            helper_name,
        )
    elif source_kind == "exact":
        exact_source = _hollow_round9_helper(
            check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8"),
            helper_name,
        )
    elif source_kind == "artifact_core":
        artifact_core_source = _hollow_round9_helper(
            check_p1_2_proof_obligations.PR2_L0_ARTIFACT_CORE_PATH.read_text(
                encoding="utf-8"
            ),
            helper_name,
        )
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
        artifact_core_source=artifact_core_source,
    )

    expected_error = f"source sha256 drifted for {helper_name}"
    assert any(expected_error in error for error in errors), errors


@pytest.mark.parametrize(
    ("source_kind", "mutator", "expected_error"),
    [
        ("child", _child_clears_replay_violations, "supervisor domain chokepoint"),
        ("child", _child_dead_branches_project_records_after_prebind, "supervisor domain chokepoint"),
        ("child", _child_swallows_replay_gate, "supervisor domain chokepoint"),
        ("child", _child_switches_replayed_records_sibling, "supervisor domain chokepoint"),
        ("child", _child_mutates_fixed_verdict_publishable, "supervisor domain chokepoint"),
        ("child", _child_clears_durable_records_after_fixed_witness, "supervisor domain chokepoint"),
        ("child", _child_project_records_empties_strong_keys, "candidate projection chokepoint"),
        (
            "l0",
            _l0_appends_round_trip_stub,
            "source pin target not uniquely resolvable",
        ),
        (
            "l0",
            _l0_rebinds_true_verifier_module,
            "constant TRUE_VERIFIER_MODULE must match pinned source",
        ),
        (
            "l0",
            _l0_noops_domain_response_violation,
            "source sha256 drifted for _domain_response_violation",
        ),
        ("l0", _l0_shadows_dict_top_level, "must not shadow/rebind dict"),
        (
            "exact",
            _exact_noops_unsupervised_certified_guard,
            "source sha256 drifted for _has_unsupervised_certified_checkpoint_claim",
        ),
        (
            "exact",
            _exact_save_dead_branches_unsupervised_guard,
            "source sha256 drifted for ExactCampaign.save",
        ),
        (
            "exact",
            _exact_final_objective_compare_pass,
            "compare gate for final_objective must have live fail-closed effect",
        ),
        (
            "exact",
            _exact_best_empty_compare_pass,
            "compare gate for best_empty_objective must have live fail-closed effect",
        ),
        (
            "child",
            _child_replay_status_compare_pass,
            "compare gate for replay_status must have live fail-closed effect",
        ),
    ],
    ids=[
        "round8-child-replay-violations-clear",
        "round8-child-dead-branch-prebind",
        "round8-child-try-except-swallow",
        "round8-child-replayed-records-sibling-switch",
        "round8-child-fixed-verdict-attr-mutate",
        "round8-child-durable-records-clear",
        "round8-child-project-records-strong-keys-empty",
        "round8-l0-round-trip-stub-after-binding",
        "round8-l0-true-verifier-module-rebind",
        "round8-l0-domain-response-violation-noop",
        "round8-l0-dict-shadow",
        "round8-exact-unsupervised-guard-noop",
        "round8-exact-save-guard-dead-branch",
        "round8-exact-final-objective-pass",
        "round8-exact-best-empty-pass",
        "round8-child-replay-status-pass",
    ],
)
def test_p1_2_checker_rejects_pr2_5_round8_close_kernel_bypasses(
    tmp_path: Path,
    source_kind: str,
    mutator: object,
    expected_error: str,
) -> None:
    assert callable(mutator)
    child_source = l0_source = exact_source = None
    if source_kind == "child":
        child_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            )
        )
    elif source_kind == "l0":
        l0_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            )
        )
    elif source_kind == "exact":
        exact_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8")
        )
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
    )

    assert any(expected_error in error for error in errors), errors


def test_p1_2_empty_rect_leaf_math_oracle() -> None:
    from src.search.exact_campaign import (
        _best_empty_rect_objective,
        _build_occupancy_prefix,
        _empty_rect_exists,
        _occupied_count_in_rect,
    )

    right_prefix = _build_occupancy_prefix(
        occupied_cells={(0, 0), (1, 0), (2, 0)},
        grid_w=5,
        grid_h=2,
    )
    assert _empty_rect_exists(
        occupancy_prefix=right_prefix,
        grid_w=5,
        grid_h=2,
        rect_w=2,
        rect_h=2,
    )

    bottom_prefix = _build_occupancy_prefix(
        occupied_cells={(0, 0), (0, 1), (0, 2)},
        grid_w=2,
        grid_h=5,
    )
    assert _empty_rect_exists(
        occupancy_prefix=bottom_prefix,
        grid_w=2,
        grid_h=5,
        rect_w=2,
        rect_h=2,
    )

    empty_prefix = _build_occupancy_prefix(occupied_cells=set(), grid_w=4, grid_h=3)
    assert _best_empty_rect_objective(
        occupancy_prefix=empty_prefix,
        grid_w=4,
        grid_h=3,
        min_side_admissibility=1,
    ) == (12, 3)
    threshold_prefix = _build_occupancy_prefix(occupied_cells=set(), grid_w=5, grid_h=2)
    assert _best_empty_rect_objective(
        occupancy_prefix=threshold_prefix,
        grid_w=5,
        grid_h=2,
        min_side_admissibility=2,
    ) == (10, 2)
    assert _empty_rect_exists(
        occupancy_prefix=empty_prefix,
        grid_w=3,
        grid_h=3,
        rect_w=3,
        rect_h=3,
    )

    prefix = _build_occupancy_prefix(
        occupied_cells={(0, 0), (1, 2), (2, 2)},
        grid_w=3,
        grid_h=3,
    )
    assert _occupied_count_in_rect(
        occupancy_prefix=prefix,
        anchor_x=0,
        anchor_y=0,
        rect_w=1,
        rect_h=1,
    ) == 1
    assert _occupied_count_in_rect(
        occupancy_prefix=prefix,
        anchor_x=0,
        anchor_y=0,
        rect_w=3,
        rect_h=3,
    ) == 3
    assert _occupied_count_in_rect(
        occupancy_prefix=prefix,
        anchor_x=0,
        anchor_y=2,
        rect_w=3,
        rect_h=1,
    ) == 2
    assert _occupied_count_in_rect(
        occupancy_prefix=prefix,
        anchor_x=1,
        anchor_y=1,
        rect_w=1,
        rect_h=1,
    ) == 0

    boundary_best_prefix = _build_occupancy_prefix(
        occupied_cells={(x, 0) for x in range(4)} | {(0, y) for y in range(4)},
        grid_w=4,
        grid_h=4,
    )
    assert _best_empty_rect_objective(
        occupancy_prefix=boundary_best_prefix,
        grid_w=4,
        grid_h=4,
        min_side_admissibility=2,
    ) == (9, 3)


def test_p1_2_child_path_confinement_leaf_canary(tmp_path: Path) -> None:
    from src.search.pr2_l0_true_verifier_child import _is_within, _is_within_any

    root = tmp_path / "root"
    inside = root / "nested" / "module.py"
    outside = tmp_path / "outside" / "module.py"
    inside.parent.mkdir(parents=True)
    outside.parent.mkdir(parents=True)
    inside.write_text("# inside\n", encoding="utf-8")
    outside.write_text("# outside\n", encoding="utf-8")
    root = root.resolve()

    assert _is_within(root, inside)
    assert not _is_within(root, outside)
    assert _is_within_any(inside, [root])
    assert not _is_within_any(outside, [root])


def test_p1_2_close_kernel_strict_json_leaf_canaries() -> None:
    from src.search.exact_campaign import _loads_strict_json_object
    from src.search.pr2_l0_micro_verifier_core import loads_l0_strict_json

    with pytest.raises(ValueError, match="duplicate JSON key: a"):
        loads_l0_strict_json('{"a": 1, "a": 2}')
    with pytest.raises(ValueError, match="invalid JSON constant: NaN"):
        loads_l0_strict_json('{"a": NaN}')
    with pytest.raises(ValueError, match="non-finite JSON number: 1e999"):
        loads_l0_strict_json('{"a": 1e999}')

    with pytest.raises(ValueError, match="duplicate JSON key: a"):
        _loads_strict_json_object('{"a": 1, "a": 2}')
    with pytest.raises(ValueError, match="invalid JSON constant: NaN"):
        _loads_strict_json_object('{"a": NaN}')


def test_p1_2_round10_close_kernel_full_pin_enforcement() -> None:
    l0_source = check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
        encoding="utf-8"
    )
    l0_tree = ast.parse(l0_source)
    child_tree = ast.parse(
        check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
            encoding="utf-8"
        )
    )
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_tree = ast.parse(exact_source)

    assert (
        check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
            l0_tree,
            child_tree,
            exact_tree,
        )
        == []
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(l0_source + "\n\ndef __round10_unpinned():\n    return None\n"),
        child_tree,
        exact_tree,
    )
    assert any("function not source-pinned: __round10_unpinned" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(l0_source + "\nif True:\n    pass\n"),
        child_tree,
        exact_tree,
    )
    assert any("unexpected top-level If" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(l0_source + "\nROUND10_UNPINNED_CONST = 1\n"),
        child_tree,
        exact_tree,
    )
    assert any("module constant not pinned: ROUND10_UNPINNED_CONST" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_source + "\nimport os\n"),
    )
    assert any(
        "tail import after definitions in exact_campaign.py" in error
        for error in errors
    )

    exact_lines = exact_source.splitlines()
    exact_import_insert_line = 0
    for node in exact_tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            exact_import_insert_line = getattr(node, "end_lineno", node.lineno)
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            exact_import_insert_line = getattr(node, "end_lineno", node.lineno)
            continue
        break
    exact_with_extra_import = (
        "\n".join(
            exact_lines[:exact_import_insert_line]
            + ["import src.search.pr2_false_certify_patch"]
            + exact_lines[exact_import_insert_line:]
        )
        + "\n"
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_extra_import),
    )
    assert any("close-kernel import not allowlisted" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(l0_source + "\nfrom pathlib import Path as XPath\n"),
        child_tree,
        exact_tree,
    )
    assert any(
        "tail import after definitions in pr2_l0_micro_verifier_core.py" in error
        for error in errors
    )


def test_p1_2_round11_close_kernel_def_time_and_class_body_hardening(tmp_path: Path) -> None:
    l0_source = check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
        encoding="utf-8"
    )
    l0_tree = ast.parse(l0_source)
    child_tree = ast.parse(
        check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
            encoding="utf-8"
        )
    )
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_tree = ast.parse(exact_source)
    artifact_core_source = check_p1_2_proof_obligations.PR2_L0_ARTIFACT_CORE_PATH.read_text(
        encoding="utf-8"
    )

    exact_with_relative_import_alias = exact_source.replace(
        "from dataclasses import dataclass\n",
        "from .dataclasses import dataclass\n",
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_relative_import_alias),
    )
    assert any("close-kernel import drift" in error for error in errors)

    exact_with_decorator_side_effect = exact_source.replace(
        "@dataclass\nclass ExactCampaign:",
        (
            "@(globals().__setitem__('terminal_frontier_evidence_violation', "
            "lambda **_: None) or dataclass)\n"
            "class ExactCampaign:"
        ),
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_decorator_side_effect),
    )
    assert any("dynamic import-time call globals" in error and "ExactCampaign" in error for error in errors)

    mutated_exact_path = tmp_path / "exact_campaign.py"
    mutated_exact_path.write_text(exact_with_decorator_side_effect, encoding="utf-8")
    mutated_exact_tree = ast.parse(exact_with_decorator_side_effect)
    errors = check_p1_2_proof_obligations._check_exact_runtime_tcb_source_pins(
        mutated_exact_tree,
        check_p1_2_proof_obligations._class_def(
            mutated_exact_tree,
            "ExactCampaign",
            path=mutated_exact_path,
        ),
        path=mutated_exact_path,
    )
    assert any("source sha256 drifted for ExactCampaign" in error for error in errors)

    exact_with_base = exact_source.replace(
        "@dataclass\nclass ExactCampaign:",
        "@dataclass\nclass ExactCampaign(BendersCut):",
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_base),
    )
    assert any("def-time bases/keywords drifted" in error for error in errors)

    artifact_core_with_constant_side_effect = _replace_once(
        artifact_core_source,
        'TERMINAL_FULL_FRONTIER_CERTIFIED_REASON = "search_exhausted_all_candidates"',
        (
            "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON = "
            "(globals().__setitem__('terminal_frontier_evidence_violation', "
            "lambda **_: None) or 'search_exhausted_all_candidates')"
        ),
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        artifact_core_source=artifact_core_with_constant_side_effect,
    )
    assert any(
        "PR2 exact runtime TCB constant TERMINAL_FULL_FRONTIER_CERTIFIED_REASON must match pinned source"
        in error
        for error in errors
    )

    exact_with_helper_side_effect = exact_source.replace(
        "    source_root = Path(__file__).resolve().parent.parent.parent\n",
        (
            "    globals().__setitem__('terminal_frontier_evidence_violation', "
            "lambda **_: None)\n"
            "    source_root = Path(__file__).resolve().parent.parent.parent\n"
        ),
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_helper_side_effect),
    )
    assert any(
        "module constant->_discover_certified_exact_source_hash_files" in error
        and "dynamic import-time call globals" in error
        for error in errors
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(l0_source + "\nasync def __round11_async_unpinned():\n    return None\n"),
        child_tree,
        exact_tree,
    )
    assert any("unexpected top-level AsyncFunctionDef" in error for error in errors)

    exact_with_class_async = exact_source.replace(
        "    def best_certified_result(self) -> Optional[Dict[str, Any]]:\n",
        (
            "    async def __round11_async_smuggle("
            "_=globals().__setitem__('terminal_frontier_evidence_violation', "
            "lambda **_: None)):\n"
            "        pass\n\n"
            "    def best_certified_result(self) -> Optional[Dict[str, Any]]:\n"
        ),
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_class_async),
    )
    assert any("method not source-pinned: ExactCampaign.__round11_async_smuggle" in error for error in errors)
    assert any("dynamic import-time call globals" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_source + "\n    save = lambda self: None\n"),
    )
    assert any("class binding must be unique: ExactCampaign.save" in error for error in errors)
    assert any("class binding shadows source-pinned member: ExactCampaign.save" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_source + "\n    def save(self) -> None:\n        return None\n"),
    )
    assert any("class binding must be unique: ExactCampaign.save" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_source + "\n    class _Round11Nested:\n        def hollow(self):\n            return None\n"),
    )
    assert any("nested class not source-pinned: ExactCampaign._Round11Nested" in error for error in errors)
    assert any("method not source-pinned: ExactCampaign._Round11Nested.hollow" in error for error in errors)

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_source + "\n    if True:\n        save = lambda self: None\n"),
    )
    assert any("class ExactCampaign has an unexpected body If" in error for error in errors)


def test_p1_2_round11_close_kernel_import_dependency_shape_rejects_import_time_mutation(
    tmp_path: Path,
) -> None:
    root_rel_path = "src/search/exact_campaign.py"
    root_path = tmp_path / root_rel_path
    root_path.parent.mkdir(parents=True)
    root_path.write_text(
        "from src.io.strict_json import loads_strict_json\n",
        encoding="utf-8",
    )

    rel_path = "src/io/strict_json.py"
    dependency_path = tmp_path / rel_path
    dependency_path.parent.mkdir(parents=True)
    dependency_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "globals().__setitem__('terminal_frontier_evidence_violation', lambda **_: None)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    closure = check_p1_2_proof_obligations._close_kernel_import_time_closure_source_paths(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )
    assert rel_path in closure

    errors = check_p1_2_proof_obligations._check_close_kernel_import_dependency_import_time_shape(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )

    assert any("dynamic import-time call globals" in error for error in errors)


def test_p1_2_round12_close_kernel_import_closure_follows_match_case_import(
    tmp_path: Path,
) -> None:
    root_rel_path = "src/search/exact_campaign.py"
    root_path = tmp_path / root_rel_path
    root_path.parent.mkdir(parents=True)
    root_path.write_text(
        "from src.io.strict_json import loads_strict_json\n",
        encoding="utf-8",
    )

    strict_json_path = tmp_path / "src/io/strict_json.py"
    strict_json_path.parent.mkdir(parents=True)
    strict_json_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "match 0:",
                "    case 0:",
                "        from src.io import round12_match_probe",
                "",
            ]
        ),
        encoding="utf-8",
    )
    probe_path = tmp_path / "src/io/round12_match_probe.py"
    probe_path.write_text(
        "from __future__ import annotations\n"
        "globals().__setitem__('round12_match_probe', 1)\n",
        encoding="utf-8",
    )

    match_stmt = ast.parse(strict_json_path.read_text(encoding="utf-8")).body[1]
    assert any(
        isinstance(child, ast.ImportFrom)
        for child in check_p1_2_proof_obligations._iter_import_time_child_statements(match_stmt)
    )
    closure = check_p1_2_proof_obligations._close_kernel_import_time_closure_source_paths(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )
    assert "src/io/round12_match_probe.py" in closure

    errors = check_p1_2_proof_obligations._check_close_kernel_import_dependency_import_time_shape(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )

    assert any("src/io/round12_match_probe.py" in error for error in errors)
    assert any("dynamic import-time call globals" in error for error in errors)


def test_p1_2_round12_close_kernel_import_closure_follows_helper_body_import(
    tmp_path: Path,
) -> None:
    root_rel_path = "src/search/exact_campaign.py"
    root_path = tmp_path / root_rel_path
    root_path.parent.mkdir(parents=True)
    root_path.write_text(
        "from src.io.strict_json import loads_strict_json\n",
        encoding="utf-8",
    )

    strict_json_path = tmp_path / "src/io/strict_json.py"
    strict_json_path.parent.mkdir(parents=True)
    strict_json_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "def _round12_import_time_helper():",
                "    from src.io import round12_helper_probe",
                "_round12_import_time_helper()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    probe_path = tmp_path / "src/io/round12_helper_probe.py"
    probe_path.write_text(
        "from __future__ import annotations\n"
        "globals().__setitem__('round12_helper_probe', 1)\n",
        encoding="utf-8",
    )

    closure = check_p1_2_proof_obligations._close_kernel_import_time_closure_source_paths(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )
    assert "src/io/round12_helper_probe.py" in closure

    errors = check_p1_2_proof_obligations._check_close_kernel_import_dependency_import_time_shape(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )

    assert any("src/io/round12_helper_probe.py" in error for error in errors)
    assert any("dynamic import-time call globals" in error for error in errors)


def test_p1_2_round12_close_kernel_rejects_dynamic_import_alias(
    tmp_path: Path,
) -> None:
    root_rel_path = "src/search/exact_campaign.py"
    root_path = tmp_path / root_rel_path
    root_path.parent.mkdir(parents=True)
    root_path.write_text(
        "from src.io.strict_json import loads_strict_json\n",
        encoding="utf-8",
    )

    strict_json_path = tmp_path / "src/io/strict_json.py"
    strict_json_path.parent.mkdir(parents=True)
    strict_json_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import importlib",
                "from importlib import import_module as round12_import_module",
                "round12_getattr = getattr(importlib, 'import_module')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_import_dependency_import_time_shape(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )

    assert any("dynamic import primitive importlib.import_module" in error for error in errors)
    assert any("getattr(importlib, 'import_module')" in error for error in errors)


def test_p1_2_round12_close_kernel_rejects_namespace_mutator_target(
    tmp_path: Path,
) -> None:
    root_rel_path = "src/search/exact_campaign.py"
    root_path = tmp_path / root_rel_path
    root_path.parent.mkdir(parents=True)
    root_path.write_text(
        "from src.io.strict_json import loads_strict_json\n",
        encoding="utf-8",
    )

    strict_json_path = tmp_path / "src/io/strict_json.py"
    strict_json_path.parent.mkdir(parents=True)
    strict_json_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import operator",
                "import sys",
                "dict.__setitem__(sys.modules[__name__].__dict__, 'round12_probe', 1)",
                "operator.setitem(globals(), 'round12_probe_2', 2)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_import_dependency_import_time_shape(
        project_root=tmp_path,
        roots=(root_rel_path,),
    )

    assert any("must not write through __dict__ at import/def time" in error for error in errors)
    assert any("must not write through globals() at import/def time" in error for error in errors)


def test_p1_2_round13_current_scope_binding_walker_rejects_walrus_and_delete_smuggling(
    tmp_path: Path,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_with_module_walrus = exact_source.replace(
        '_RESUME_INFEASIBLE_REPLAY_REASON = (\n'
        '    "infeasible_candidate_requires_fresh_replay_after_checkpoint_resume"\n'
        ')\n',
        "_RESUME_INFEASIBLE_REPLAY_REASON = (\n"
        "    ((_supervisor_seal_state_violation := (lambda *args, **kwargs: None)),\n"
        '     "infeasible_candidate_requires_fresh_replay_after_checkpoint_resume")[1]\n'
        ")\n",
        1,
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_with_module_walrus,
    )
    assert any(
        error.endswith(
            "exact_campaign.py: _supervisor_seal_state_violation"
        )
        and "source pin target not uniquely resolvable" in error
        for error in errors
    )

    exact_with_class_walrus = exact_source.replace(
        "    def save(self) -> None:\n",
        "    def save(self, _=(supervisor_seal := (lambda self, **kwargs: None))) -> None:\n",
        1,
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_with_class_walrus,
    )
    assert any(
        "class binding for" in error
        and "ExactCampaign.supervisor_seal must be unique" in error
        for error in errors
    )

    exact_with_delete = exact_source.replace(
        "\n@dataclass\nclass ExactCampaign:",
        "\ndel _supervisor_seal_state_violation\n\n@dataclass\nclass ExactCampaign:",
        1,
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_with_delete,
    )
    assert any(
        error.endswith(
            "exact_campaign.py: _supervisor_seal_state_violation"
        )
        and "source pin target not uniquely resolvable" in error
        for error in errors
    )


def test_p1_2_round13_close_kernel_rejects_import_and_builtin_shadow(
    tmp_path: Path,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    l0_tree = ast.parse(
        check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
            encoding="utf-8"
        )
    )
    child_tree = ast.parse(
        check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
            encoding="utf-8"
        )
    )

    exact_with_import_shadow = exact_source.replace(
        "\ndef _atomic_json_bytes(",
        "\ndef terminal_frontier_evidence_violation(*args, **kwargs):\n"
        "    return None\n\n"
        "def _atomic_json_bytes(",
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_import_shadow),
    )
    assert any(
        "top-level binding must not shadow import/builtin name "
        "terminal_frontier_evidence_violation" in error
        for error in errors
    )

    exact_with_class_builtin_shadow = exact_source.replace(
        "    @property\n    def artifact_hashes(self) -> Dict[str, str]:\n",
        "    def property(fn):\n"
        "        return fn\n\n"
        "    @property\n"
        "    def artifact_hashes(self) -> Dict[str, str]:\n",
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        l0_tree,
        child_tree,
        ast.parse(exact_with_class_builtin_shadow),
    )
    assert not any(
        "class binding must not shadow import/builtin name ExactCampaign.property" in error
        for error in errors
    )
    assert any(
        "def-time expression must not resolve to prior class local property" in error
        for error in errors
    )


def test_p1_2_round13_close_kernel_rejects_decorator_drift() -> None:
    l0_source = check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
        encoding="utf-8"
    )
    l0_with_decorator = l0_source.replace(
        "def run_l0_supervisor_seal(",
        "@contextmanager\ndef run_l0_supervisor_seal(",
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(l0_with_decorator),
        ast.parse(
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            )
        ),
        ast.parse(
            check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
                encoding="utf-8"
            )
        ),
    )
    assert any(
        "PR2 L0 micro-verifier.run_l0_supervisor_seal decorators drifted" in error
        for error in errors
    )


def test_p1_2_round13_checker_error_collector_integrity(tmp_path: Path) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )

    checker_path = tmp_path / "checker_errors_clear.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_close_kernel_contract(manifest))\n",
            "        errors.extend(_check_close_kernel_contract(manifest))\n"
            "        errors.clear()\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path
    )
    assert any("non-whitelisted errors reference" in error for error in errors)

    checker_path = tmp_path / "checker_errors_clear_method_alias.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_close_kernel_contract(manifest))\n",
            "        errors.extend(_check_close_kernel_contract(manifest))\n"
            "        _sink = errors.clear\n"
            "        _sink()\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path
    )
    assert any("non-whitelisted errors reference" in error for error in errors)

    checker_path = tmp_path / "checker_errors_clear_getattr_alias.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_close_kernel_contract(manifest))\n",
            "        errors.extend(_check_close_kernel_contract(manifest))\n"
            '        _sink = getattr(errors, "clear")\n'
            "        _sink()\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path
    )
    assert any("reflection/dynamic primitive getattr" in error for error in errors)

    checker_path = tmp_path / "checker_errors_for_rebind.py"
    checker_path.write_text(
        source.replace(
            "        errors: list[str] = []\n",
            "        errors: list[str] = []\n"
            "        for errors in ([],):\n"
            "            pass\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path
    )
    assert any("non-whitelisted errors reference" in error for error in errors)

    checker_path = tmp_path / "checker_shadow_callee.py"
    checker_path.write_text(
        source.replace(
            "        errors: list[str] = []\n",
            "        errors: list[str] = []\n"
            "        _check_close_kernel_contract = lambda manifest: []\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path
    )
    assert any(
        "must not locally shadow required callee _check_close_kernel_contract" in error
        for error in errors
    )

    checker_path = tmp_path / "checker_return_empty.py"
    checker_path.write_text(
        source.replace(
            "    return errors\n\n\ndef _check_isolated_exec_bytecode_binding_contract",
            "    return []\n\n\ndef _check_isolated_exec_bytecode_binding_contract",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_error_collector_return_shape(
        checker_path=checker_path
    )
    assert "_check_candidate_sink_replay_contract must end with direct return errors" in errors

    checker_path = tmp_path / "checker_dead_error_gate.py"
    checker_path.write_text(
        source.replace(
            "    if errors:\n",
            "    if False and errors:\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_main_error_reporting_shape(
        checker_path=checker_path
    )
    assert "proof-obligation checker main must have reachable if errors: return 1" in errors


def test_p1_2_round13_self_binding_requires_new_gates_and_self_call(
    tmp_path: Path,
) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )
    checker_path = tmp_path / "checker_removed_self_binding.py"
    checker_path.write_text(
        source.replace(
            "    preflight_errors.extend(_check_close_kernel_checker_self_binding())\n",
            "    # mutation: removed self-binding call\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path
    )
    assert "proof-obligation checker main must call _check_close_kernel_checker_self_binding" in errors

    checker_path = tmp_path / "checker_removed_semantic_projection.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_proof_obligation_manifest_semantic_projection(manifest))\n",
            "        # mutation: removed semantic projection call\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path
    )
    assert (
        "proof-obligation checker main must call "
        "_check_proof_obligation_manifest_semantic_projection"
    ) in errors


def test_p1_2_round13_manifest_semantic_projection_rejects_resealed_gutting() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    manifest["summary"] = "GUTTED"
    manifest["obligations"][0]["title"] = "GUTTED"
    manifest[check_p1_2_proof_obligations.P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_FIELD] = (
        check_p1_2_proof_obligations._proof_obligation_manifest_semantic_projection_sha256(
            manifest
        )
    )

    errors = check_p1_2_proof_obligations._check_proof_obligation_manifest_semantic_projection(
        manifest
    )

    assert (
        "proof-obligation manifest semantic projection drifted from the reviewed P1.2 floor"
        in errors
    )


def test_p1_2_round13_source_text_includes_parenthesized_decorator_start(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "decorator_probe.py"
    source_path.write_text(
        "@(\n"
        "    contextmanager\n"
        ")\n"
        "def decorated():\n"
        "    yield\n",
        encoding="utf-8",
        newline="\n",
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    assert check_p1_2_proof_obligations._source_text(source_path, function).startswith("@(\n")


def test_p1_2_round14_close_kernel_rejects_lambda_default_walrus_hidden_bindings(
    tmp_path: Path,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_with_top_level_hidden = exact_source.replace(
        "_RESUME_INFEASIBLE_REPLAY_REASON = (\n"
        '    "infeasible_candidate_requires_fresh_replay_after_checkpoint_resume"\n'
        ")\n",
        "_RESUME_INFEASIBLE_REPLAY_REASON = (\n"
        "    ((_round14_hidden := 1),\n"
        '     "infeasible_candidate_requires_fresh_replay_after_checkpoint_resume")[1]\n'
        ")\n",
        1,
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_with_top_level_hidden,
    )
    assert any("top-level hidden binding is forbidden: _round14_hidden" in error for error in errors)

    exact_with_class_lambda_default = exact_source.replace(
        "    def save(self) -> None:\n",
        "    def save(self, _probe=(lambda _=(supervisor_seal := None): None)) -> None:\n",
        1,
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(
            check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            )
        ),
        ast.parse(
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            )
        ),
        ast.parse(exact_with_class_lambda_default),
    )
    assert any(
        "class hidden binding is forbidden: ExactCampaign.supervisor_seal" in error
        for error in errors
    )


def test_p1_2_round14_close_kernel_rejects_runtime_member_hooks_and_writes(
    tmp_path: Path,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_source + "\n    def __getattr__(self, name):\n        return None\n",
    )
    assert any("class runtime member must not define hook __getattr__" in error for error in errors)

    exact_with_member_write = exact_source.replace(
        "    def save(self) -> None:\n",
        "    def save(self) -> None:\n"
        "        self.supervisor_seal = None\n",
        1,
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_with_member_write,
    )
    assert any("must not write runtime member supervisor_seal" in error for error in errors)

    exact_with_dynamic_member_write = exact_source.replace(
        "    def save(self) -> None:\n",
        "    def save(self) -> None:\n"
        '        object.__setattr__(self, "supervisor_seal", None)\n',
        1,
    )
    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_with_dynamic_member_write,
    )
    assert any("must not dynamically write runtime member supervisor_seal" in error for error in errors)


def test_p1_2_round14_function_shadow_guard_rejects_walrus_and_match_capture() -> None:
    tree = ast.parse(
        "def probe(value):\n"
        "    if (reverify_whole_layout_infeasibility := value):\n"
        "        return None\n"
    )
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert check_p1_2_proof_obligations._function_shadows_name(
        function,
        "reverify_whole_layout_infeasibility",
    )

    tree = ast.parse(
        "def probe(value):\n"
        "    match value:\n"
        "        case reverify_whole_layout_infeasibility:\n"
        "            return None\n"
    )
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert check_p1_2_proof_obligations._function_shadows_name(
        function,
        "reverify_whole_layout_infeasibility",
    )


def test_p1_2_round14_strong_status_allowlist_bytes_are_pinned(tmp_path: Path) -> None:
    allowlist_path = tmp_path / check_p1_2_proof_obligations.STRONG_STATUS_WRITE_ALLOWLIST_REL
    allowlist_path.parent.mkdir(parents=True)
    allowlist_bytes = check_p1_2_proof_obligations.STRONG_STATUS_WRITE_ALLOWLIST_PATH.read_bytes()
    allowlist_path.write_bytes(allowlist_bytes)
    assert check_p1_2_proof_obligations._check_strong_status_write_allowlist_bytes(
        project_root=tmp_path,
    ) == []

    mutated = bytearray(allowlist_bytes)
    mutated[-1] = mutated[-1] ^ 1
    allowlist_path.write_bytes(bytes(mutated))
    errors = check_p1_2_proof_obligations._check_strong_status_write_allowlist_bytes(
        project_root=tmp_path,
    )
    assert any("strong-status write allowlist hash drift" in error for error in errors)


def test_p1_2_round14_checker_errors_whitelist_rejects_alias_reflection_and_mutation(
    tmp_path: Path,
) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )
    checker_path = tmp_path / "checker_errors_alias_reflection.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_close_kernel_contract(manifest))\n",
            "        errors.extend(_check_close_kernel_contract(manifest))\n"
            "        _round14_alias = errors\n"
            '        sys._getframe().f_locals["errors"] = []\n',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )

    errors = check_p1_2_proof_obligations._check_error_collector_integrity(
        checker_path=checker_path,
    )

    assert any("non-whitelisted errors reference" in error for error in errors)
    assert any("sys._getframe" in error for error in errors)
    assert any("f_locals" in error for error in errors)


def test_p1_2_round14_checker_self_integrity_preflight_is_fail_fast(
    tmp_path: Path,
) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )
    checker_path = tmp_path / "checker_preflight_removed.py"
    checker_path.write_text(
        source.replace(
            "    preflight_errors.extend(_check_close_kernel_checker_self_binding())\n",
            "    # mutation: removed fail-fast self-binding preflight\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )

    errors = check_p1_2_proof_obligations._check_main_self_integrity_preflight_shape(
        checker_path=checker_path,
    )

    assert any("fail-fast self-integrity preflight" in error for error in errors)


def test_p1_2_round14_checker_failure_gate_rejects_exit_and_none_returns(
    tmp_path: Path,
) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )
    checker_path = tmp_path / "checker_exit_gate.py"
    checker_path.write_text(
        source.replace(
            "    if errors:\n        return 1\n",
            "    if errors:\n        sys.exit(1)\n        return 1\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_main_error_reporting_shape(
        checker_path=checker_path,
    )
    assert any("process exit" in error or "failure gate body" in error for error in errors)

    checker_path = tmp_path / "checker_return_none.py"
    checker_path.write_text(
        source.replace("    return 0\n", "    return None\n", 1),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_main_error_reporting_shape(
        checker_path=checker_path,
    )
    assert any("return only integer literals 0, 1, or 2" in error for error in errors)


def test_p1_2_round14_checker_required_callee_floor_rejects_rebind_and_shrink(
    tmp_path: Path,
) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )
    checker_path = tmp_path / "checker_required_tuple_shrink.py"
    head, marker, tail = source.partition("_PR2_CHECKER_MAIN_REQUIRED_CALLS = (\n")
    assert marker
    checker_path.write_text(
        head
        + marker
        + tail.replace(
            '    "_check_close_kernel_contract",\n'
            '    "_check_certified_artifact_contract_runtime_anchor",\n'
            '    "_check_phase_gate_provenance_contract",\n',
            '    "_check_certified_artifact_contract_runtime_anchor",\n'
            '    "_check_phase_gate_provenance_contract",\n',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path,
    )
    assert any("runtime tuple shrank below floor: _check_close_kernel_contract" in error for error in errors)

    checker_path = tmp_path / "checker_required_callee_decorated.py"
    checker_path.write_text(
        source.replace(
            "def _check_close_kernel_contract(manifest: dict[str, Any], *, project_root: Path = PROJECT_ROOT) -> list[str]:\n",
            "@staticmethod\n"
            "def _check_close_kernel_contract(manifest: dict[str, Any], *, project_root: Path = PROJECT_ROOT) -> list[str]:\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path,
    )
    assert any("required callee _check_close_kernel_contract must be undecorated" in error for error in errors)


def test_p1_2_round14_runtime_anchor_rejects_manifest_semantic_projection_mismatch(
    tmp_path: Path,
) -> None:
    from src.search.certified_artifact_contract import locked_p1_2_close_kernel_violation

    (tmp_path / "PROJECT_LOCK.md").write_text("locked\n", encoding="utf-8")
    manifest_path = tmp_path / "data/proof_obligations/p1_2_proof_obligations.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        '{"semantic_projection_sha256": "0"}\n',
        encoding="utf-8",
        newline="\n",
    )
    allowlist_path = tmp_path / "data/proof_obligations/strong_status_write_allowlist.json"
    allowlist_path.write_text("[]\n", encoding="utf-8", newline="\n")
    checker_path = tmp_path / "scripts/check_p1_2_proof_obligations.py"
    checker_path.parent.mkdir()
    checker_path.write_text("raise SystemExit(0)\n", encoding="utf-8", newline="\n")

    assert (
        locked_p1_2_close_kernel_violation(tmp_path)
        == "locked_p1_2_close_kernel_semantic_projection_mismatch"
    )


def test_p1_2_round14_close_kernel_accepts_class_builtin_member_without_def_time_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_with_builtin_member = exact_source.replace(
        "    compatible_hashes: bool\n",
        "    compatible_hashes: bool\n"
        "    id: int = 0\n",
        1,
    )
    field_sources = dict(check_p1_2_proof_obligations._PR2_CLOSE_KERNEL_CLASS_FIELD_SOURCES)
    field_sources["PR2 exact campaign.ExactCampaign"] = (
        *field_sources["PR2 exact campaign.ExactCampaign"],
        "id: int = 0",
    )
    runtime_layouts = dict(
        check_p1_2_proof_obligations._PR2_CLOSE_KERNEL_CLASS_RUNTIME_MEMBER_LAYOUTS
    )
    exact_layout = list(runtime_layouts["PR2 exact campaign.ExactCampaign"])
    exact_layout.insert(5, ("field", "id"))
    runtime_layouts["PR2 exact campaign.ExactCampaign"] = tuple(exact_layout)
    monkeypatch.setattr(
        check_p1_2_proof_obligations,
        "_PR2_CLOSE_KERNEL_CLASS_FIELD_SOURCES",
        field_sources,
    )
    monkeypatch.setattr(
        check_p1_2_proof_obligations,
        "_PR2_CLOSE_KERNEL_CLASS_RUNTIME_MEMBER_LAYOUTS",
        runtime_layouts,
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_files_fully_pinned(
        ast.parse(
            check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            )
        ),
        ast.parse(
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            )
        ),
        ast.parse(exact_with_builtin_member),
    )

    assert not any("ExactCampaign.id" in error for error in errors)


def test_p1_2_round14_checker_accepts_errors_iadd_required_call(tmp_path: Path) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(
        encoding="utf-8"
    )
    checker_path = tmp_path / "checker_iadd_required.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_close_kernel_contract(manifest))\n",
            "        errors += _check_close_kernel_contract(manifest)\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )

    assert check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path,
    ) == []


def test_p1_2_round15_manifest_projection_rejects_top_level_key_drift() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    manifest["round15_unreviewed_claim"] = {"status": "CERTIFIED"}

    errors = check_p1_2_proof_obligations._check_proof_obligation_manifest_semantic_projection(
        manifest
    )

    assert any("unreviewed top-level fields" in error for error in errors)
    assert any("round15_unreviewed_claim" in error for error in errors)

    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    del manifest["updated_at"]

    errors = check_p1_2_proof_obligations._check_proof_obligation_manifest_semantic_projection(
        manifest
    )

    assert any("missing reviewed top-level fields" in error for error in errors)
    assert any("updated_at" in error for error in errors)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            '        self.__dict__["supervisor_seal"] = None\n',
            "runtime reflection primitive __dict__",
        ),
        (
            '        vars(self)["supervisor_seal"] = None\n',
            "runtime reflection primitive vars",
        ),
        (
            '        w = setattr\n        w(self, "supervisor_seal", None)\n',
            "runtime reflection primitive setattr",
        ),
        (
            '        w = object.__setattr__\n        w(self, "supervisor_seal", None)\n',
            "runtime reflection primitive __setattr__",
        ),
        (
            '        getattr(type, "__setattr__")(ExactCampaign, "supervisor_seal", None)\n',
            "getattr dunder member __setattr__",
        ),
        (
            '        type.__dict__["__setattr__"](ExactCampaign, "supervisor_seal", None)\n',
            "runtime reflection primitive __dict__",
        ),
        (
            "        sys._getframe()\n",
            "runtime reflection primitive sys._getframe",
        ),
        (
            "        inspect.stack()\n",
            "runtime reflection primitive inspect.stack",
        ),
        (
            "        gc.get_objects()\n",
            "runtime reflection primitive gc.get_objects",
        ),
    ],
)
def test_p1_2_round15_close_kernel_rejects_runtime_reflection_primitive_writes(
    tmp_path: Path,
    payload: str,
    expected: str,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_source = _replace_once(
        exact_source,
        "    def save(self) -> None:\n"
        "        with _checkpoint_write_lock(self.path):\n",
        "    def save(self) -> None:\n"
        f"{payload}"
        "        with _checkpoint_write_lock(self.path):\n",
    )

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_source,
    )

    assert any(expected in error for error in errors)


def test_p1_2_round15_close_kernel_allows_known_safe_runtime_member_forms() -> None:
    tree = ast.parse(
        "def probe(self, spec):\n"
        "    self.state = {}\n"
        '    origin = getattr(spec, "origin", None)\n'
    )
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    assert (
        check_p1_2_proof_obligations._check_close_kernel_runtime_member_writes(
            "round15", "ExactCampaign", function
        )
        == []
    )

    tree = ast.parse(
        "def probe(value=(lambda _=build_terminal_fixed_witness_projection_at_sink: _)):\n"
        "    return build_terminal_fixed_witness_projection_at_sink()\n"
    )
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert not check_p1_2_proof_obligations._function_shadows_name(
        function,
        "build_terminal_fixed_witness_projection_at_sink",
    )


@pytest.mark.parametrize(
    "injection",
    [
        "    [None for build_terminal_fixed_witness_projection_at_sink in (0,)]\n",
        '    globals()["build_terminal_fixed_witness_projection_at_sink"] = lambda **kwargs: None\n',
        '    locals().update({"build_terminal_fixed_witness_projection_at_sink": None})\n',
        '    vars()["build_terminal_fixed_witness_projection_at_sink"] = None\n',
    ],
)
def test_p1_2_round15_witness_shadow_rejects_comprehension_and_namespace_writes(
    tmp_path: Path,
    injection: str,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_source = _replace_once(
        exact_source,
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(\n",
        f"{injection}"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(\n",
    )

    errors = _fixed_witness_errors_for_exact_source(
        tmp_path,
        exact_source,
    )

    assert any(
        "shadows imported fixed-witness capsule symbol "
        "build_terminal_fixed_witness_projection_at_sink" in error
        for error in errors
    )


@pytest.mark.parametrize(
    "injection",
    [
        "    global build_terminal_fixed_witness_projection_at_sink\n",
        "    del build_terminal_fixed_witness_projection_at_sink\n",
        "    type build_terminal_fixed_witness_projection_at_sink = int\n",
        "    def _round15_type_param[build_terminal_fixed_witness_projection_at_sink]():\n"
        "        pass\n",
        "    build_terminal_fixed_witness_projection_at_sink = None\n"
        "    def _round15_nonlocal():\n"
        "        nonlocal build_terminal_fixed_witness_projection_at_sink\n",
    ],
)
def test_p1_2_round15_witness_shadow_rejects_statement_and_type_binding_forms(
    tmp_path: Path,
    injection: str,
) -> None:
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_source = _replace_once(
        exact_source,
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(\n",
        f"{injection}"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(\n",
    )

    errors = _fixed_witness_errors_for_exact_source(
        tmp_path,
        exact_source,
    )

    assert any(
        "shadows imported fixed-witness capsule symbol "
        "build_terminal_fixed_witness_projection_at_sink" in error
        for error in errors
    )


def test_p1_2_round15_checker_required_callees_are_runtime_bound_before_subprocess(
    tmp_path: Path,
) -> None:
    source = _checker_source()
    checker_source = _checker_source_before_entrypoint(
        source,
        "_check_close_kernel_contract = lambda manifest: []\n",
    )
    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        checker_source,
        name="checker_late_callee_rebind.py",
    )
    assert any(
        "required callee _check_close_kernel_contract must resolve to exactly one "
        "top-level FunctionDef" in error
        for error in errors
    )

    checker_source = source.replace(
        'if __name__ == "__main__":\n    raise SystemExit(main())\n',
        "if True:\n    raise SystemExit(main())\n",
        1,
    )
    assert (
        _locked_close_kernel_violation_for_checker_source(tmp_path / "entry", checker_source)
        == "locked_p1_2_close_kernel_checker_entrypoint_invalid"
    )

    checker_source = _checker_source_before_entrypoint(source, "main = lambda: 0\n")
    assert (
        _locked_close_kernel_violation_for_checker_source(tmp_path / "main_rebind", checker_source)
        == "locked_p1_2_close_kernel_checker_protected_binding:main"
    )


def test_p1_2_round15_checker_top_level_closed_world_rejects_dynamic_namespace_rebind(
    tmp_path: Path,
) -> None:
    source = _checker_source()

    # round-15 Finding A: ``globals()["main"] = lambda: 0`` is an ``Assign`` with a
    # ``Subscript`` target, so the binding-point count misses it while it still
    # rebinds ``main`` at module-exec time (the real ``main`` never runs, the
    # subprocess exits 0).  Only the parent-process runtime anchor can catch this,
    # via the module top-level closed-world check.
    main_rebind_source = _checker_source_before_entrypoint(
        source,
        'globals()["main"] = lambda: 0\n',
    )
    violation = _locked_close_kernel_violation_for_checker_source(
        tmp_path / "globals_main_rebind", main_rebind_source
    )
    assert violation is not None
    assert violation.startswith(
        "locked_p1_2_close_kernel_checker_top_level_disallowed:Assign"
    )

    # Defense in depth: the checker-side self-binding guard rejects the same
    # module-level dynamic write when it rebinds a required callee (``main`` still
    # runs in that case).
    callee_rebind_source = _checker_source_before_entrypoint(
        source,
        'globals()["_check_close_kernel_contract"] = lambda manifest: []\n',
    )
    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        callee_rebind_source,
        name="checker_globals_callee_rebind.py",
    )
    assert any(
        "module top level contains disallowed statement Assign" in error
        for error in errors
    )


def test_p1_2_round18_checker_rejects_class_body_import_time_main_rebind(
    tmp_path: Path,
) -> None:
    source = _checker_source()
    checker_source = _checker_source_before_entrypoint(
        source,
        "_round18_modules = sys.modules\n"
        "class _Round18Probe:\n"
        "    _round18_modules[__name__].main = lambda: 0\n",
    )

    violation = _locked_close_kernel_violation_for_checker_source(
        tmp_path / "class_body_main_rebind", checker_source
    )
    assert violation is not None
    assert violation.startswith(
        "locked_p1_2_close_kernel_checker_top_level_disallowed:ClassDef"
    )

    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        checker_source,
        name="checker_class_body_main_rebind.py",
    )
    assert any(
        "module top level contains disallowed statement ClassDef" in error
        for error in errors
    )


def test_p1_2_round18_checker_rejects_checkerror_shadowing_handler(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _checker_source(),
        "    except CheckError:\n"
        "        return 2\n"
        "\n"
        "    if errors:\n",
        "    except Exception:\n"
        "        pass\n"
        "    except CheckError:\n"
        "        return 2\n"
        "\n"
        "    if errors:\n",
    )

    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        source,
        name="checker_broad_except_shadow.py",
    )

    assert any("main must have exactly one exception handler" in error for error in errors)


def test_p1_2_round18_checker_rejects_process_exit_aliases_before_error_gate(
    tmp_path: Path,
) -> None:
    source = _checker_source_before_entrypoint(
        _checker_source(),
        "_round18_exit = sys.exit\n",
    )
    source = _replace_once(
        source,
        "        errors: list[str] = []\n",
        "        errors: list[str] = []\n"
        "        _round18_exit(0)\n",
    )

    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        source,
        name="checker_top_level_exit_alias.py",
    )

    assert any("module top level contains disallowed statement Assign" in error for error in errors)
    assert any("main must not call process exit before failure gate" in error for error in errors)
    assert any("main must not exit before errors gate" in error for error in errors)

    source = _replace_once(
        _checker_source(),
        "        errors: list[str] = []\n",
        "        errors: list[str] = []\n"
        "        _round18_exit = sys.exit\n"
        "        _round18_exit(0)\n",
    )
    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        source,
        name="checker_local_exit_alias.py",
    )
    assert any("main must not call process exit before failure gate" in error for error in errors)


def test_p1_2_round18_checker_rejects_accumulator_alias_frame_escape(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _checker_source(),
        "def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:\n"
        "    errors: list[str] = []\n",
        "def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:\n"
        '    _frame = getattr(sys, "_get" + "frame")()\n'
        '    _locs = getattr(_frame, "f_" + "locals")\n'
        '    if "errors" in _locs:\n'
        '        _locs["errors"].clear()\n'
        "    errors: list[str] = []\n",
    )

    errors = _checker_error_integrity_errors_for_source(
        tmp_path,
        source,
        name="checker_alias_frame_escape.py",
    )

    assert any("caller-frame/dynamic primitive getattr f_locals" in error for error in errors)


def test_p1_2_round15_close_kernel_rejects_ctypes_native_member_write(
    tmp_path: Path,
) -> None:
    # round-15 Finding B: native ``ctypes`` C-API attribute writes are a member
    # override vector not covered by the Python-level primitive set.
    exact_source = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    exact_source = _replace_once(
        exact_source,
        "    def save(self) -> None:\n"
        "        with _checkpoint_write_lock(self.path):\n",
        "    def save(self) -> None:\n"
        '        ctypes.pythonapi.PyObject_SetAttr(self, b"supervisor_seal", None)\n'
        "        with _checkpoint_write_lock(self.path):\n",
    )

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        exact_source=exact_source,
    )

    assert any(
        "runtime reflection primitive ctypes.pythonapi.PyObject_SetAttr" in error
        for error in errors
    )


@pytest.mark.parametrize(
    "injection",
    [
        "        match []:\n"
        "            case errors:\n"
        "                pass\n",
        "        try:\n"
        "            raise RuntimeError()\n"
        "        except RuntimeError as errors:\n"
        "            pass\n",
        "        with open(__file__, encoding=\"utf-8\") as errors:\n"
        "            pass\n",
    ],
)
def test_p1_2_round15_checker_rejects_errors_match_capture_and_other_rebinds(
    tmp_path: Path,
    injection: str,
) -> None:
    source = _replace_once(
        _checker_source(),
        "        errors: list[str] = []\n",
        "        errors: list[str] = []\n"
        f"{injection}",
    )

    errors = _checker_error_integrity_errors_for_source(tmp_path, source)

    assert any("must not bind errors except errors: list[str] = []" in error for error in errors)


def test_p1_2_round15_checker_rejects_unapproved_accumulator_callee_and_frame_escape(
    tmp_path: Path,
) -> None:
    source = _checker_source()
    source_with_unapproved_callee = _checker_source_before_entrypoint(
        _replace_once(
            source,
            "        errors.extend(_check_close_kernel_contract(manifest))\n",
            "        errors.extend(_check_close_kernel_contract(manifest))\n"
            "        errors.extend(_round15_unapproved_errors())\n",
        ),
        "def _round15_unapproved_errors() -> list[str]:\n"
        "    return []\n",
    )
    errors = _checker_error_integrity_errors_for_source(
        tmp_path,
        source_with_unapproved_callee,
        name="checker_unapproved_accumulator.py",
    )
    assert any(
        "accumulator callee _round15_unapproved_errors is not in the required-callee floor"
        in error
        for error in errors
    )

    source_with_frame_escape = _replace_once(
        source,
        "def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:\n"
        "    errors: list[str] = []\n",
        "def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:\n"
        "    sys._getframe()\n"
        "    errors: list[str] = []\n",
    )
    errors = _checker_error_integrity_errors_for_source(
        tmp_path,
        source_with_frame_escape,
        name="checker_frame_escape.py",
    )
    assert any("caller-frame/dynamic primitive sys._getframe" in error for error in errors)


def test_p1_2_round15_checker_rejects_side_effectful_errors_append_args(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _checker_source(),
        "        errors: list[str] = []\n",
        "        errors: list[str] = []\n"
        "        errors.append(_round15_side_effect())\n",
    )

    errors = _checker_error_integrity_errors_for_source(tmp_path, source)

    assert any("errors.append argument must be side-effect-free" in error for error in errors)


def test_p1_2_round15_checker_rejects_floor_tuple_walrus_rebind(
    tmp_path: Path,
) -> None:
    source = _checker_source_before_entrypoint(
        _checker_source(),
        "(_PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR := ())\n",
    )

    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        source,
        name="checker_floor_walrus.py",
    )

    assert any(
        "must define _PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR exactly once" in error
        for error in errors
    )


def test_p1_2_round15_try_star_and_literal_accumulator_concern_canaries(
    tmp_path: Path,
) -> None:
    source = _checker_source_before_entrypoint(
        _checker_source(),
        "try:\n"
        "    pass\n"
        "except* Exception as _PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR:\n"
        "    pass\n",
    )
    errors = _checker_self_binding_errors_for_source(
        tmp_path,
        source,
        name="checker_trystar_floor.py",
    )
    assert any(
        "must define _PR2_CHECKER_MAIN_REQUIRED_CALLS_FLOOR exactly once" in error
        for error in errors
    )

    source = _replace_once(
        _checker_source(),
        "        errors.extend(_check_close_kernel_contract(manifest))\n",
        "        errors.extend(_check_close_kernel_contract(manifest))\n"
        '        errors.extend(["round15 literal list extension"])\n'
        '        errors += ["round15 literal iadd"]\n',
    )
    errors = _checker_error_integrity_errors_for_source(
        tmp_path,
        source,
        name="checker_literal_accumulators.py",
    )
    assert not any("round15 literal" in error for error in errors)
    assert not any("non-whitelisted errors reference" in error for error in errors)
    assert not any("is not in the required-callee floor" in error for error in errors)

    source = _replace_once(
        _checker_source(),
        "    if errors:\n        return 1\n",
        "    if errors:\n        _print_p1_2_errors(errors)\n        return 1\n",
    )
    checker_path = _write_checker_source(tmp_path, "checker_print_then_return.py", source)
    assert check_p1_2_proof_obligations._check_main_error_reporting_shape(
        checker_path=checker_path,
    ) == []


def test_p1_2_close_kernel_source_floor_covers_import_time_closure() -> None:
    closure = check_p1_2_proof_obligations._close_kernel_import_time_closure_source_paths()
    for rel_path in (
        "src/interchange/preprocess_context.py",
        "src/io/strict_json.py",
        "src/models/_cpsat_compat.py",
        "src/models/cp_sat_worker_config.py",
        "src/models/port_binding.py",
        "src/models/pose_bool_exact_master.py",
        "src/models/solution_hint_parser.py",
        "src/preprocess/operation_profiles.py",
        "src/search/commodity_throughput.py",
    ):
        assert rel_path in closure
        assert (
            rel_path
            in check_p1_2_proof_obligations.CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH
        )


def test_p1_2_close_kernel_rejects_import_time_dependency_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_rel_path = "src/search/exact_campaign.py"
    root_path = tmp_path / root_rel_path
    root_path.parent.mkdir(parents=True)
    root_path.write_text(
        "from src.io.strict_json import loads_strict_json\n",
        encoding="utf-8",
    )
    strict_json_path = tmp_path / "src/io/strict_json.py"
    strict_json_path.parent.mkdir(parents=True)
    strict_json_path.write_text(
        "from __future__ import annotations\n# mutated import-time dependency\n",
        encoding="utf-8",
    )
    for rel_path in (
        "src/search/pr2_l0_micro_verifier_core.py",
        "src/search/pr2_l0_true_verifier_child.py",
    ):
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    floor = {
        root_rel_path: check_p1_2_proof_obligations._sha256_file(root_path),
        "src/search/pr2_l0_micro_verifier_core.py": check_p1_2_proof_obligations._sha256_file(
            tmp_path / "src/search/pr2_l0_micro_verifier_core.py"
        ),
        "src/search/pr2_l0_true_verifier_child.py": check_p1_2_proof_obligations._sha256_file(
            tmp_path / "src/search/pr2_l0_true_verifier_child.py"
        ),
        "src/io/strict_json.py": "0" * 64,
    }
    monkeypatch.setattr(
        check_p1_2_proof_obligations,
        "CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH",
        floor,
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_v99_static_floor(
        tokens=tuple(check_p1_2_proof_obligations.CLOSE_KERNEL_V99_REQUIRED_PROOF_BEARING_TOKENS),
        scan_roots=tuple(check_p1_2_proof_obligations.CLOSE_KERNEL_V99_REQUIRED_SCAN_ROOTS),
        excluded_subpaths=(),
        critical_gate_files=tuple(check_p1_2_proof_obligations.CLOSE_KERNEL_V99_REQUIRED_CRITICAL_GATE_FILES),
        registered={},
        project_root=tmp_path,
    )

    assert any("src/io/strict_json.py current source hash drifted" in error for error in errors)


@pytest.mark.parametrize(
    ("source_kind", "mutator", "expected_error"),
    [
        ("child", _child_clobbers_replay_violations, "must not clobber replay_violations"),
        ("child", _child_clobbers_fixed_verdict, "must not clobber fixed_verdict"),
        (
            "child",
            _child_clobbers_fixed_violations,
            "must assign fixed_violations exactly once",
        ),
        ("child", _child_clobbers_envelope_violation, "must immediately consume envelope_violation"),
        ("child", _child_clobbers_replay_status, "must not clobber replay_status"),
        (
            "child",
            _child_clobbers_terminal_fixed_witness_verdict,
            "must not clobber verdict",
        ),
        ("exact", _exact_clobbers_stop_reason, "must immediately consume stop_reason"),
        (
            "exact",
            _exact_clobbers_search_stats_reason,
            "must immediately consume search_stats_reason",
        ),
        ("exact", _exact_clobbers_final_objective, "must not clobber final_objective"),
        (
            "exact",
            _exact_clobbers_best_empty_objective,
            "must not clobber best_empty_objective",
        ),
        ("exact", _exact_clobbers_expected_pose_idx, "must not clobber expected_pose_idx"),
        (
            "l0",
            _l0_tampers_scratch_state_after_seal_gate,
            "PR2 L0 supervisor seal durable writer canonical top-level prefix/body",
        ),
        (
            "l0",
            _l0_forges_helper_after_seal_gate,
            "PR2 L0 supervisor seal durable writer canonical top-level prefix/body",
        ),
        ("l0", _l0_bound_update_alias, "mutator/reflection hook"),
        ("l0", _l0_getattr_update_alias, "mutator/reflection hook"),
        ("l0", _l0_dict_unpack_alias_mutation, "mutator/reflection hook"),
        (
            "exact",
            _exact_terminal_final_result_returns_true_before_frontier,
            "must only return canonical fail-closed reasons",
        ),
        (
            "artifact_core",
            _exact_terminal_precheck_raises_before_reason,
            "must not raise",
        ),
        (
            "exact",
            _exact_validate_terminal_solution_returns_true_early,
            "must only return canonical fail-closed reasons",
        ),
        ("exact", _exact_ghost_pick_raises_early, "must not raise"),
    ],
    ids=[
        "round7-child-replay-violations-clobber",
        "round7-child-fixed-verdict-clobber",
        "round7-child-fixed-violations-clobber",
        "round7-child-envelope-violation-clobber",
        "round7-child-replay-status-clobber",
        "round7-child-terminal-fixed-witness-verdict-clobber",
        "round7-exact-stop-reason-clobber",
        "round7-exact-search-stats-reason-clobber",
        "round7-exact-final-objective-clobber",
        "round7-exact-best-empty-objective-clobber",
        "round7-exact-expected-pose-clobber",
        "round7-l0-post-seal-scratch-state-tamper",
        "round7-l0-post-seal-helper-forge",
        "round7-l0-bound-update-alias",
        "round7-l0-getattr-update-alias",
        "round7-l0-dict-unpack-alias",
        "round7-exact-terminal-final-result-return-true",
        "round7-exact-terminal-precheck-raise",
        "round7-exact-terminal-solution-return-true",
        "round7-exact-ghost-pick-raise",
    ],
)
def test_p1_2_checker_rejects_pr2_5_round7_result_flow_bypasses(
    tmp_path: Path,
    source_kind: str,
    mutator: object,
    expected_error: str,
) -> None:
    assert callable(mutator)
    child_source = l0_source = exact_source = artifact_core_source = None
    if source_kind == "child":
        child_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            )
        )
    elif source_kind == "l0":
        l0_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            )
        )
    elif source_kind == "exact":
        exact_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8")
        )
    elif source_kind == "artifact_core":
        artifact_core_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_ARTIFACT_CORE_PATH.read_text(
                encoding="utf-8"
            )
        )
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
        artifact_core_source=artifact_core_source,
    )

    assert any(expected_error in error for error in errors), errors


@pytest.mark.parametrize(
    ("source_kind", "mutator", "expected_error"),
    [
        (
            "child",
            _child_verify_echoes_payload_domain,
            "PR2 true verifier child verify entrypoint must match the canonical top-level prefix/body",
        ),
        (
            "exact",
            _exact_terminal_final_result_returns_none_before_frontier,
            "terminal certified final result validator must start",
        ),
        (
            "artifact_core",
            _exact_terminal_precheck_returns_none_before_reason,
            "terminal certified final result project precheck must not return None",
        ),
        (
            "exact",
            _exact_validate_terminal_solution_returns_none_early,
            "terminal solution project validator must have return None only as its final",
        ),
        (
            "exact",
            _exact_ghost_pick_returns_none_early,
            "terminal candidate ghost-pick binding validator must have return None only",
        ),
        (
            "child",
            _child_project_records_return_before_replay,
            "must not return before isolated replay",
        ),
        (
            "child",
            _child_fixed_witness_returns_early,
            "fixed witness direct verifier must have exactly one final return",
        ),
        (
            "l0",
            _l0_domain_violation_guard_and_false,
            "must immediately consume domain_violation",
        ),
        (
            "l0",
            _l0_seal_violation_guard_and_false,
            "must immediately consume seal_violation",
        ),
        (
            "l0",
            _l0_postwrite_violation_guard_and_false,
            "must immediately consume postwrite_violation",
        ),
        (
            "l0",
            _l0_seal_state_returns_none_early,
            "PR2 L0 supervisor seal state validator must match the canonical top-level prefix/body",
        ),
        (
            "child",
            _child_loader_injects_extra_method,
            "method set must be exactly",
        ),
        (
            "child",
            _child_source_loader_skips_digest_rehash,
            "_RehashingSourceFileLoader.get_data must match the canonical top-level prefix/body",
        ),
        (
            "child",
            _child_non_domain_helper_shadows_getattr,
            "must not shadow/rebind getattr",
        ),
        (
            "l0",
            _l0_domain_container_alias_mutation,
            "must not write child/domain/proposal mapping data",
        ),
    ],
    ids=[
        "round6-verify-entrypoint-echoes-domain",
        "round6-terminal-final-result-top-return-none",
        "round6-terminal-project-precheck-top-return-none",
        "round6-terminal-solution-validator-top-return-none",
        "round6-terminal-ghost-pick-top-return-none",
        "round6-child-project-records-pre-replay-return",
        "round6-child-fixed-witness-direct-early-return",
        "round6-l0-domain-gate-and-false",
        "round6-l0-seal-state-gate-and-false",
        "round6-l0-postwrite-gate-and-false",
        "round6-l0-seal-state-body-early-return",
        "round6-loader-extra-method",
        "round6-source-loader-skips-rehash",
        "round6-non-domain-helper-shadows-getattr",
        "round6-g7-container-alias-domain-mutation",
    ],
)
def test_p1_2_checker_rejects_pr2_5_round6_structural_bypasses(
    tmp_path: Path,
    source_kind: str,
    mutator: object,
    expected_error: str,
) -> None:
    assert callable(mutator)
    base_child = check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
        encoding="utf-8"
    )
    base_l0 = check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
        encoding="utf-8"
    )
    base_exact = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    base_artifact_core = check_p1_2_proof_obligations.PR2_L0_ARTIFACT_CORE_PATH.read_text(
        encoding="utf-8"
    )
    child_source = base_child
    l0_source = base_l0
    exact_source = base_exact
    artifact_core_source = base_artifact_core
    if source_kind == "child":
        child_source = mutator(base_child)  # type: ignore[operator]
    elif source_kind == "l0":
        l0_source = mutator(base_l0)  # type: ignore[operator]
    elif source_kind == "exact":
        exact_source = mutator(base_exact)  # type: ignore[operator]
    elif source_kind == "artifact_core":
        artifact_core_source = mutator(base_artifact_core)  # type: ignore[operator]
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
        artifact_core_source=artifact_core_source,
    )

    assert any(expected_error in error for error in errors), errors


@pytest.mark.parametrize(
    (
        "source_kind",
        "mutator",
        "expected_error",
        "round10_full_pin_independently_rejects",
    ),
    [
        ("child", _child_early_return_before_precheck, "exactly one Return", False),
        (
            "child",
            _child_code_object_monkeypatches_precheck,
            "dunder attribute __code__",
            False,
        ),
        (
            "child",
            _child_globals_monkeypatches_precheck,
            "dunder attribute __globals__",
            False,
        ),
        (
            "child",
            _child_importfrom_builtins_setattr_alias,
            "ImportFrom outside pinned allowlist",
            False,
        ),
        ("child", _child_builtins_dict_facade, "must not reference __builtins__", False),
        (
            "child",
            _child_module_top_level_monkeypatch,
            "PR2 true verifier child module top level must not assign non-Name targets",
            True,
        ),
        (
            "child",
            _child_return_unpack_overrides_domain,
            "must exactly match the pinned key set",
            False,
        ),
        (
            "child",
            _child_return_tcb_side_effect_call,
            "final return domain key tcb must match pinned expression",
            False,
        ),
        (
            "child",
            _child_precheck_extra_kwarg,
            "terminal precheck call must be exactly",
            False,
        ),
        (
            "l0",
            _l0_child_verdict_forged_rebind,
            "must not rebind child/domain/proposal data",
            False,
        ),
        (
            "child",
            _child_duplicate_verify_supervisor_domain,
            "source pin target not uniquely resolvable",
            False,
        ),
        (
            "l0",
            _l0_duplicate_run_l0_supervisor_seal,
            "source pin target not uniquely resolvable",
            False,
        ),
        (
            "exact",
            _exact_duplicate_transition_helper,
            "source pin target not uniquely resolvable",
            False,
        ),
        ("child", _child_decorated_verify_supervisor_domain, "must not use decorators", True),
        (
            "child",
            _child_top_level_rebinds_verify,
            "source pin target not uniquely resolvable",
            True,
        ),
        ("child", _child_helper_code_swap, "dunder attribute __code__", False),
        ("child", _child_shadows_getattr, "must not shadow/rebind getattr", False),
        (
            "child",
            _child_class_body_side_effect,
            "body contains import-time executable statement",
            True,
        ),
        ("l0", _l0_object_setattr_forges_child_verdict, "mutator/reflection hook", False),
        ("l0", _l0_domain_update_after_assignment, "mutator/reflection hook", False),
        ("l0", _l0_child_verdict_response_update, "mutator/reflection hook", False),
        (
            "l0",
            _l0_child_payload_update_after_verdict,
            "mutator/reflection hook",
            False,
        ),
        ("l0", _l0_type_setitem_domain, "mutator/reflection hook", False),
        ("l0", _l0_class_setitem_domain, "mutator/reflection hook", False),
        ("l0", _l0_transition_starts_with_return, "unconditional top-level Return", False),
        (
            "exact",
            _exact_transition_starts_with_return,
            "unconditional top-level Return",
            False,
        ),
        ("l0", _l0_postwrite_starts_with_return, "unconditional top-level Return", False),
    ],
    ids=[
        "g1-child-early-return-before-precheck",
        "g2-child-code-object-monkeypatch",
        "g2-child-globals-monkeypatch",
        "g2-child-importfrom-builtins-setattr-alias",
        "g2-child-builtins-dict-facade",
        "g3-child-module-top-level-monkeypatch",
        "g4-child-return-unpack-override",
        "g4-child-return-unpinned-side-effect",
        "g5-child-precheck-extra-kwarg",
        "g7-l0-child-verdict-forged-rebind",
        "round5-child-duplicate-domain-helper",
        "round5-l0-duplicate-supervisor-seal",
        "round5-exact-duplicate-transition-helper",
        "round5-child-decorator-wrapper",
        "round5-child-rebind-verify",
        "round5-child-helper-code-swap",
        "round5-child-shadow-getattr",
        "round5-child-class-body-side-effect",
        "round5-g7-object-setattr-child-verdict",
        "round5-g7-domain-update",
        "round5-g7-child-verdict-response-update",
        "round5-g7-child-payload-update",
        "round5-g7-type-setitem-domain",
        "round5-g7-class-setitem-domain",
        "g6-l0-transition-dead-strict-assignment",
        "g6-exact-transition-dead-strict-assignment",
        "g6-l0-postwrite-dead-strict-guard",
    ],
)
def test_p1_2_checker_rejects_pr2_5_closed_world_reachability_bypasses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_kind: str,
    mutator: object,
    expected_error: str,
    round10_full_pin_independently_rejects: bool,
) -> None:
    assert callable(mutator)
    base_child = check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
        encoding="utf-8"
    )
    base_l0 = check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
        encoding="utf-8"
    )
    base_exact = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    child_source = base_child
    l0_source = base_l0
    exact_source = base_exact
    if source_kind == "child":
        child_source = mutator(base_child)  # type: ignore[operator]
    elif source_kind == "l0":
        l0_source = mutator(base_l0)  # type: ignore[operator]
    elif source_kind == "exact":
        exact_source = mutator(base_exact)  # type: ignore[operator]
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
    )

    assert any(expected_error in error for error in errors), errors

    _disable_pr2_5_closed_world_guards(monkeypatch)
    legacy_errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
    )

    if round10_full_pin_independently_rejects:
        # round-10 full-pin — and, for decorator mutations, the round-13
        # decorator allowlist (FIX-3) — is an independent defense-in-depth line:
        # it still rejects this bypass after the old closed-world guard is
        # disabled.
        assert legacy_errors != []
    else:
        assert legacy_errors == []


@pytest.mark.parametrize(
    ("source_kind", "mutator", "expected_error"),
    [
        (
            "l0",
            _l0_transition_starts_with_true_return_branch,
            "canonical top-level prefix",
        ),
        (
            "exact",
            _exact_transition_starts_with_true_return_branch,
            "canonical top-level prefix",
        ),
        (
            "l0",
            _l0_postwrite_starts_with_true_return_branch,
            "canonical top-level prefix",
        ),
        (
            "l0",
            _l0_transition_returns_after_strict,
            "canonical top-level prefix/body",
        ),
        (
            "exact",
            _exact_transition_returns_after_strict,
            "canonical top-level prefix/body",
        ),
        (
            "l0",
            _l0_postwrite_returns_after_strict_guard,
            "canonical top-level prefix/body",
        ),
    ],
    ids=[
        "g6-l0-transition-constant-true-early-return",
        "g6-exact-transition-constant-true-early-return",
        "g6-l0-postwrite-constant-true-early-return",
        "round5-g6-l0-transition-post-anchor-return",
        "round5-g6-exact-transition-post-anchor-return",
        "round5-g6-l0-postwrite-post-anchor-return",
    ],
)
def test_p1_2_checker_rejects_pr2_5_g6_constant_true_prefix_bypasses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_kind: str,
    mutator: object,
    expected_error: str,
) -> None:
    assert callable(mutator)
    base_l0 = check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
        encoding="utf-8"
    )
    base_exact = check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
        encoding="utf-8"
    )
    l0_source = base_l0
    exact_source = base_exact
    if source_kind == "l0":
        l0_source = mutator(base_l0)  # type: ignore[operator]
    elif source_kind == "exact":
        exact_source = mutator(base_exact)  # type: ignore[operator]
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        l0_source=l0_source,
        exact_source=exact_source,
    )

    assert any(expected_error in error for error in errors), errors

    _disable_pr2_5_g6_prefix_pins(monkeypatch)
    legacy_errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        l0_source=l0_source,
        exact_source=exact_source,
    )

    assert legacy_errors == []


@pytest.mark.parametrize(
    ("source_kind", "mutator", "expected_error"),
    [
        (
            "child",
            _move_child_final_status_after_precheck,
            "canonical window missing scratch_state slots: final_status",
        ),
        ("child", _child_rebinds_scratch_state, "must not rebind scratch_state"),
        ("child", _child_aliases_scratch_state, "must not alias scratch_state"),
        ("child", _child_dunder_setitem_clobber, "must not call scratch_state.__setitem__"),
        ("child", _child_dict_setitem_clobber, "must not pass scratch_state to helper calls"),
        ("child", _child_operator_setitem_clobber, "must not pass scratch_state to helper calls"),
        ("child", _child_getattr_setitem_clobber, "must not pass scratch_state to helper calls"),
        ("child", _child_helper_call_clobber, "must not pass scratch_state to helper calls"),
        ("child", _child_augassign_clobber, "must not AugAssign/AnnAssign scratch_state"),
        ("child", _child_deletes_terminal_slot, "must not delete scratch_state"),
        ("child", _child_pop_terminal_slot, "must not call scratch_state.pop"),
        (
            "child",
            _child_nested_update_clobber,
            'must not call scratch_state["last_stop_reason"].update',
        ),
        (
            "child",
            _child_nested_slot_assignment_clobber,
            'must not mutate nested scratch_state["last_stop_reason"][...]',
        ),
        ("child", _child_shadows_precheck, "must not shadow terminal_certified_final_result_project_precheck_violation"),
        ("child", _child_shadows_terminal_reason, "must not shadow TERMINAL_FULL_FRONTIER_CERTIFIED_REASON"),
        ("child", _child_wrong_project_root_precheck, "project_root=project_root"),
        ("child", _child_ignores_precheck_result, "precheck result must be consumed"),
        ("child", _child_rhs_locals_setitem, 'scratch_state["candidates"] RHS must be Name("durable_records")'),
        (
            "child",
            _child_rhs_ior_tuple,
            'scratch_state["terminal_frontier_evidence"] RHS must be Name("evidence")',
        ),
        (
            "child",
            _child_rhs_walrus_alias,
            'scratch_state["final_result"] RHS must be Name("certified_final_result")',
        ),
        ("child", _child_rhs_exec, 'scratch_state["candidates"] RHS must be Name("durable_records")'),
        ("child", _child_global_globals_setitem, "must not use global/nonlocal declarations"),
        (
            "child",
            _child_local_def_shadow_precheck,
            "must not define reserved name terminal_certified_final_result_project_precheck_violation",
        ),
        (
            "child",
            _child_imports_fake_precheck_module,
            "must import authority name exactly once from src.search.pr2_l0_artifact_core",
        ),
        ("child", _child_setattr_monkeypatches_precheck, "dynamic module capability setattr"),
        ("child", _child_rebinds_project_root, "must not shadow/rebind project_root"),
        (
            "child",
            _child_dead_nested_precheck_raise,
            "terminal precheck result must be consumed by the immediately following",
        ),
        (
            "child",
            _child_delays_precheck_consumption_after_return,
            "terminal precheck result must be consumed by the immediately following",
        ),
        ("child", _child_mutates_evidence_after_precheck, "must not mutate evidence.clear"),
        (
            "child",
            _child_rebinds_durable_records_after_precheck,
            "must not rebind durable_records after terminal precheck",
        ),
        ("child", _child_shadows_dict, "must not shadow/rebind dict"),
        ("child", _child_exec_rebinds_precheck, "dynamic module capability exec"),
        (
            "child",
            _child_globals_subscript_rebinds_precheck,
            "must not write dynamic namespace mapping globals",
        ),
        (
            "child",
            _child_import_alias_rebinds_precheck,
            "must not use bare import statements",
        ),
        ("child", _child_frame_globals_rebinds_precheck, "frame access sys._getframe"),
        ("child", _child_dunder_dict_rebind_surface, "must not access __dict__"),
        ("l0", _l0_parent_washes_declare_mode, "durable mint must assign literal \"strict\""),
        ("l0", _l0_transition_washes_declare_mode, "transition gate must assign literal \"strict\""),
        ("l0", _l0_parent_augassign_ior_after_strict, "durable mint must not rebind scratch_state"),
        (
            "l0",
            _l0_parent_alias_clobbers_declare_mode,
            'durable mint must not clobber scratch_state["declare_mode"]',
        ),
        ("l0", _l0_parent_dunder_ior_after_strict, "durable mint must not call a mutator"),
        (
            "exact",
            _exact_transition_update_clobbers_declare_mode,
            'ExactCampaign supervisor transition gate must not call a mutator',
        ),
        (
            "exact",
            _exact_transition_locals_mutator,
            'ExactCampaign supervisor transition gate must not call a mutator',
        ),
        (
            "l0",
            _l0_postwrite_dead_guard_token,
            "postwrite validator must have exactly one live top-level declare_mode strict guard",
        ),
    ],
    ids=[
        "child-final-status-after-precheck",
        "child-rebind-scratch-state",
        "child-alias-scratch-state",
        "child-dunder-setitem",
        "child-dict-setitem",
        "child-operator-setitem",
        "child-getattr-setitem",
        "child-helper-call",
        "child-ior",
        "child-delete",
        "child-pop-terminal-slot",
        "child-nested-update",
        "child-nested-slot-assignment",
        "child-shadow-precheck",
        "child-shadow-terminal-reason",
        "child-wrong-project-root",
        "child-ignore-precheck",
        "child-rhs-locals-setitem",
        "child-rhs-ior-tuple",
        "child-rhs-walrus-alias",
        "child-rhs-exec",
        "child-global-globals-setitem",
        "child-local-def-shadow-precheck",
        "child-imports-fake-precheck-module",
        "child-setattr-monkeypatches-precheck",
        "child-rebinds-project-root",
        "child-dead-nested-precheck-raise",
        "child-delays-precheck-consumption-after-return",
        "child-mutates-evidence-after-precheck",
        "child-rebinds-durable-records-after-precheck",
        "child-shadows-dict",
        "child-exec-rebinds-precheck",
        "child-globals-subscript-rebinds-precheck",
        "child-import-alias-rebinds-precheck",
        "child-frame-globals-rebinds-precheck",
        "child-dunder-dict-rebind-surface",
        "l0-parent-wash-declare-mode",
        "l0-transition-wash-declare-mode",
        "l0-parent-augassign-ior-after-strict",
        "l0-parent-alias-clobbers-declare-mode",
        "l0-parent-dunder-ior-after-strict",
        "exact-transition-update-clobber",
        "exact-transition-locals-mutator",
        "l0-postwrite-dead-guard-token",
    ],
)
def test_p1_2_checker_rejects_pr2_5_ast_pin_bypass_variants(
    tmp_path: Path,
    source_kind: str,
    mutator: object,
    expected_error: str,
) -> None:
    assert callable(mutator)
    child_source = l0_source = exact_source = None
    if source_kind == "child":
        child_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_TRUE_VERIFIER_CHILD_PATH.read_text(
                encoding="utf-8"
            )
        )
    elif source_kind == "l0":
        l0_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.PR2_L0_MICRO_VERIFIER_PATH.read_text(
                encoding="utf-8"
            )
        )
    elif source_kind == "exact":
        exact_source = mutator(  # type: ignore[operator]
            check_p1_2_proof_obligations.EXACT_CAMPAIGN_PATH.read_text(
                encoding="utf-8"
            )
        )
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(source_kind)

    errors = _candidate_sink_replay_errors_for_sources(
        tmp_path,
        child_source=child_source,
        l0_source=l0_source,
        exact_source=exact_source,
    )

    assert any(expected_error in error for error in errors), errors


def test_p1_2_checker_rejects_raw_canonical_writer_bypass(tmp_path: Path) -> None:
    surface_path = tmp_path / "certified_surface.py"
    surface_path.write_text(
        check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
        + "\n\ndef _rogue_canonical_writer(project_root):\n"
        + "    final_solution_path = project_root / \"data\" / \"solutions\" / \"final_solution.json\"\n"
        + "    atomic_write_json(final_solution_path, {\"search_status\": \"CERTIFIED\"})\n",
        encoding="utf-8",
        newline="\n",
    )

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        certified_surface_path=surface_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("raw canonical writer bypass" in error for error in errors)


def test_p1_2_checker_rejects_publisher_rollback_removal(tmp_path: Path) -> None:
    surface_path = tmp_path / "certified_surface.py"
    source = check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "except Exception as exc:  # noqa: BLE001 - publication must fail closed.",
        "except ValueError as exc:  # noqa: BLE001 - publication must fail closed.",
        1,
    )
    surface_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        certified_surface_path=surface_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("rollback must catch Exception" in error for error in errors)


def test_p1_2_checker_rejects_publisher_canonical_write_before_bundle_commit(tmp_path: Path) -> None:
    surface_path = tmp_path / "certified_surface.py"
    source = check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "        atomic_write_json(staged.final_solution_path, result)\n",
        "        atomic_write_json(final_solution_path, result)\n",
        1,
    )
    surface_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        certified_surface_path=surface_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("stage files through staged paths" in error for error in errors)


def test_p1_2_checker_rejects_publisher_bundle_commit_removal(tmp_path: Path) -> None:
    surface_path = tmp_path / "certified_surface.py"
    source = check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "commit_backup = _commit_staged_certified_delivery_surface_artifacts(",
        "commit_backup = _removed_staged_certified_delivery_surface_artifacts(",
        1,
    )
    surface_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        certified_surface_path=surface_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any(
        "transaction missing reachable call: _commit_staged_certified_delivery_surface_artifacts" in error
        for error in errors
    )
    assert any("stage, atomically commit, then verify" in error for error in errors)


def test_p1_2_checker_rejects_publisher_staged_commit_removal(tmp_path: Path) -> None:
    surface_path = tmp_path / "certified_surface.py"
    source = check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "        staged.manifest_path.replace(manifest_path)\n",
        "",
        1,
    )
    surface_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        certified_surface_path=surface_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("atomically replace manifest_path from staged bytes" in error for error in errors)


def test_p1_2_checker_rejects_manifest_mapping_snapshot_removal(tmp_path: Path) -> None:
    manifest_path = tmp_path / "delivery_manifest.py"
    source = check_p1_2_proof_obligations.DELIVERY_MANIFEST_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "    campaign_state = _snapshot_manifest_campaign_state(campaign_state)\n",
        "    # campaign_state snapshot intentionally removed by this negative fixture\n",
        1,
    )
    manifest_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        delivery_manifest_path=manifest_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("must assign campaign_state from one snapshot call" in error for error in errors)


def test_p1_2_checker_rejects_manifest_snapshot_token_comment_decoy(tmp_path: Path) -> None:
    manifest_path = tmp_path / "delivery_manifest.py"
    source = check_p1_2_proof_obligations.DELIVERY_MANIFEST_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "            dict(campaign_state),\n",
        "            campaign_state,\n",
        1,
    )
    source = source.replace(
        "    if not isinstance(snapshot, Mapping):\n",
        "    # decoy tokens: json.dumps dict(campaign_state) "
        "_loads_strict_json_object return dict(snapshot)\n"
        "    if not isinstance(snapshot, Mapping):\n",
        1,
    )
    manifest_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        delivery_manifest_path=manifest_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("json.dumps(dict(campaign_state), allow_nan=False)" in error for error in errors)


def test_p1_2_checker_rejects_staged_manifest_artifact_binding_removal(tmp_path: Path) -> None:
    surface_path = tmp_path / "certified_surface.py"
    source = check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "            final_solution_artifact_path=staged.final_solution_path,\n",
        "",
        1,
    )
    surface_path.write_text(source, encoding="utf-8", newline="\n")

    errors = check_p1_2_proof_obligations._check_certified_publication_boundary_contract(
        certified_surface_path=surface_path,
        publisher_scan_paths=_publisher_scan_paths(),
    )

    assert any("staged artifact bytes" in error for error in errors)


def _minimal_close_kernel_manifest(tmp_path: Path, *, sink_entries: list[dict[str, object]]) -> dict[str, object]:
    anchor = "v99_p1_2_close_kernel_sealing"
    return {
        "review_anchor": anchor,
        "phase_gate_required_anchor": anchor,
        "obligations": [
            {
                "id": "PO-P1-2-CLOSE-KERNEL-SEALING",
                "required_tests": [],
                "evidence_paths": [],
            }
        ],
        "close_kernel_contract": {
            "schema_version": 1,
            "review_anchor": anchor,
            "trusted_computing_base": ["python", "source", "filesystem", "pytest", "reviewer"],
            "not_claimed": ["all bugs impossible", "future safe", "owner automated", "runtime infallible"],
            "attack_categories": sorted(check_p1_2_proof_obligations.CLOSE_KERNEL_REQUIRED_ATTACK_CATEGORIES),
            "proof_bearing_tokens": ["CERTIFIED", "INFEASIBLE"],
            "scan_roots": ["src"],
            "excluded_subpaths": [],
            "critical_gate_files": [
                "scripts/check_p1_2_proof_obligations.py",
                "data/proof_obligations/p1_2_proof_obligations.json",
                "src/search/certified_surface.py",
                "src/io/delivery_manifest.py",
                "src/search/certified_frontier.py",
                "src/search/exact_campaign.py",
                "src/search/outer_search.py",
                "src/search/exact_parallel_scheduler.py",
            ],
            "sink_files": sink_entries,
        },
    }


def _copy_dependency_floor_provenance_inputs(tmp_path: Path) -> dict[str, object]:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    for rel_path in (
        check_p1_2_proof_obligations.PR2_DEPENDENCY_FLOOR_MANIFEST_REL,
        check_p1_2_proof_obligations.PR2_DEPENDENCY_FLOOR_GENERATOR_REL,
    ):
        source_path = PROJECT_ROOT / rel_path
        target_path = tmp_path / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_path.read_bytes())
    return manifest


def test_p1_2_close_kernel_rejects_unregistered_certified_sink(tmp_path: Path) -> None:
    rogue = tmp_path / "src" / "search" / "rogue_certified_sink.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text('def publish():\n    return {"status": "CERTIFIED"}\n', encoding="utf-8")
    manifest = _minimal_close_kernel_manifest(tmp_path, sink_entries=[])

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest, project_root=tmp_path)

    assert "unregistered proof-bearing close-kernel sink: src/search/rogue_certified_sink.py" in errors


def test_p1_2_close_kernel_rejects_guard_token_removal(tmp_path: Path) -> None:
    sink = tmp_path / "src" / "search" / "registered_sink.py"
    sink.parent.mkdir(parents=True)
    sink.write_text('def publish():\n    return {"status": "CERTIFIED"}\n', encoding="utf-8")
    manifest = _minimal_close_kernel_manifest(
        tmp_path,
        sink_entries=[
            {
                "path": "src/search/registered_sink.py",
                "classification": "p1_2_close_kernel",
                "obligation_id": "PO-P1-2-CLOSE-KERNEL-SEALING",
                "terms": ["CERTIFIED"],
                "required_guard_tokens": ["MISSING_CLOSE_GUARD_TOKEN"],
                "source_sha256": check_p1_2_proof_obligations._sha256_file(sink),
                "mutation_policy": "source_sha256_drift_reopens_p1_2_close_claim",
            }
        ],
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest, project_root=tmp_path)

    assert any("missing guard token 'MISSING_CLOSE_GUARD_TOKEN'" in error for error in errors)


def test_p1_2_close_kernel_rejects_registered_sink_hash_drift(tmp_path: Path) -> None:
    sink = tmp_path / "src" / "search" / "registered_sink.py"
    sink.parent.mkdir(parents=True)
    sink.write_text('def publish():\n    return {"status": "CERTIFIED"}\n', encoding="utf-8")
    source_hash = check_p1_2_proof_obligations._sha256_file(sink)
    sink.write_text('def publish():\n    return {"status": "CERTIFIED", "changed": True}\n', encoding="utf-8")
    manifest = _minimal_close_kernel_manifest(
        tmp_path,
        sink_entries=[
            {
                "path": "src/search/registered_sink.py",
                "classification": "p1_2_close_kernel",
                "obligation_id": "PO-P1-2-CLOSE-KERNEL-SEALING",
                "terms": ["CERTIFIED"],
                "required_guard_tokens": ["CERTIFIED"],
                "source_sha256": source_hash,
                "mutation_policy": "source_sha256_drift_reopens_p1_2_close_claim",
            }
        ],
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest, project_root=tmp_path)

    assert any("hash drift reopens P1.2 close claim" in error for error in errors)


def test_p1_2_close_kernel_manifest_is_strict_json(tmp_path: Path) -> None:
    duplicate_key_manifest = tmp_path / "duplicate_close_kernel.json"
    duplicate_key_manifest.write_text(
        '{"close_kernel_contract": {}, "close_kernel_contract": {}}',
        encoding="utf-8",
    )

    with pytest.raises(check_p1_2_proof_obligations.CheckError, match="duplicate JSON object key"):
        check_p1_2_proof_obligations._load_json(duplicate_key_manifest)


def test_p1_2_close_kernel_rejects_dependency_floor_generator_drift(tmp_path: Path) -> None:
    manifest = _copy_dependency_floor_provenance_inputs(tmp_path)
    generator_path = tmp_path / check_p1_2_proof_obligations.PR2_DEPENDENCY_FLOOR_GENERATOR_REL
    generator_path.write_text(
        generator_path.read_text(encoding="utf-8") + "\n# mutation: unreviewed generator drift\n",
        encoding="utf-8",
        newline="\n",
    )

    errors = check_p1_2_proof_obligations._check_dependency_floor_provenance_contract(
        manifest,
        project_root=tmp_path,
    )

    assert any("dependency floor generator hash drift reopens P1.2 close claim" in error for error in errors)


def test_p1_2_close_kernel_rejects_dependency_floor_manifest_drift(tmp_path: Path) -> None:
    manifest = _copy_dependency_floor_provenance_inputs(tmp_path)
    floor_path = tmp_path / check_p1_2_proof_obligations.PR2_DEPENDENCY_FLOOR_MANIFEST_REL
    floor_path.write_bytes(floor_path.read_bytes() + b"\n")

    errors = check_p1_2_proof_obligations._check_dependency_floor_provenance_contract(
        manifest,
        project_root=tmp_path,
    )

    assert any("dependency floor manifest hash drift reopens P1.2 close claim" in error for error in errors)


def test_p1_2_close_kernel_strong_status_gate_ignores_parent_sitecustomize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "check_strong_status_write_allowlist.py").write_text(
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    poison_dir = tmp_path / "poison"
    poison_dir.mkdir()
    (poison_dir / "sitecustomize.py").write_text(
        "import os\nos._exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(poison_dir))
    monkeypatch.setattr(check_p1_2_proof_obligations, "PROJECT_ROOT", tmp_path)

    errors = check_p1_2_proof_obligations._check_strong_status_write_allowlist_gate()

    assert any("strong-status write allowlist checker failed" in error for error in errors)



def test_p1_2_close_kernel_rejects_runtime_parent_anchor_noop(tmp_path: Path) -> None:
    contract_path = tmp_path / "certified_artifact_contract.py"
    source = (PROJECT_ROOT / "src" / "search" / "certified_artifact_contract.py").read_text(
        encoding="utf-8"
    )
    contract_path.write_text(
        source.replace(
            "def validate_locked_p1_2_close_kernel(project_root: Path) -> None:\n"
            "    \"\"\"Fail closed before a locked project can self-seal a fresh campaign.\"\"\"\n\n"
            "    reason = locked_p1_2_close_kernel_violation(project_root)",
            "def validate_locked_p1_2_close_kernel(project_root: Path) -> None:\n"
            "    \"\"\"Fail closed before a locked project can self-seal a fresh campaign.\"\"\"\n\n"
            "    return\n"
            "    reason = locked_p1_2_close_kernel_violation(project_root)",
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_certified_artifact_contract_runtime_anchor(
        path=contract_path
    )

    assert "validate_locked_p1_2_close_kernel must keep reason-gate-raise body shape" in errors


def test_p1_2_close_kernel_rejects_runtime_parent_checker_subprocess_noop(tmp_path: Path) -> None:
    contract_path = tmp_path / "certified_artifact_contract.py"
    source = (PROJECT_ROOT / "src" / "search" / "certified_artifact_contract.py").read_text(
        encoding="utf-8"
    )
    contract_path.write_text(
        source.replace(
            "    pycache_prefix = tempfile.mkdtemp(prefix=\"zmd_p1_2_close_kernel_pycache_\")",
            "    return None\n\n    pycache_prefix = tempfile.mkdtemp(prefix=\"zmd_p1_2_close_kernel_pycache_\")",
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_certified_artifact_contract_runtime_anchor(
        path=contract_path
    )

    assert any("locked_p1_2_close_kernel_violation" in error for error in errors)

def test_p1_2_close_kernel_source_floor_pins_runtime_guard_and_l0_floor_loader() -> None:
    floor = check_p1_2_proof_obligations.CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH
    for rel_path in (
        "src/search/certified_artifact_contract.py",
        "src/search/pr2_l0_micro_verifier_core.py",
    ):
        assert rel_path in floor
        assert floor[rel_path] == check_p1_2_proof_obligations._sha256_file(
            PROJECT_ROOT / rel_path
        )


def test_p1_2_close_kernel_rejects_v99_manifest_scan_root_shrink() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    manifest["close_kernel_contract"]["scan_roots"] = [
        "scripts/check_p1_2_proof_obligations.py"
    ]

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert "close_kernel_contract.scan_roots missing v99 sealed scan root: src" in errors
    assert (
        "close_kernel_contract.scan_roots missing v99 sealed scan root: "
        "scripts/build_industrial_planner_single_base_delivery_release.py"
    ) in errors


def test_p1_2_close_kernel_rejects_v99_manifest_sink_floor_shrink() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    contract = manifest["close_kernel_contract"]
    contract["sink_files"] = [
        entry
        for entry in contract["sink_files"]
        if entry["path"] == "scripts/check_p1_2_proof_obligations.py"
    ]
    contract["scan_roots"] = ["scripts/check_p1_2_proof_obligations.py"]

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert any("sink_files shrank below the v99 sealed floor" in error for error in errors)
    assert "close_kernel_contract missing v99 sealed sink path: src/search/certified_surface.py" in errors
    assert "close_kernel_contract missing v99 sealed sink path: src/search/outer_search.py" in errors


def test_p1_2_close_kernel_rejects_v99_source_sha_manifest_reseal_without_checker_floor() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    entry = next(
        item
        for item in manifest["close_kernel_contract"]["sink_files"]
        if item["path"] == "src/search/certified_surface.py"
    )
    entry["source_sha256"] = "0" * 64

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert "src/search/certified_surface.py v99 source_sha256 changed without checker-floor reseal" in errors


def test_p1_2_close_kernel_rejects_v99_manifest_token_floor_shrink() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    contract = manifest["close_kernel_contract"]
    contract["proof_bearing_tokens"] = [
        token for token in contract["proof_bearing_tokens"] if token != "proof_bearing"
    ]

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert "close_kernel_contract.proof_bearing_tokens missing v99 sealed token: proof_bearing" in errors


def test_p1_2_close_kernel_rejects_v99_manifest_required_sink_exclusion() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    victim = "src/search/outer_search.py"
    contract = manifest["close_kernel_contract"]
    contract["excluded_subpaths"] = list(contract.get("excluded_subpaths", [])) + [victim]

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert f"close_kernel_contract.excluded_subpaths must not exclude v99 sealed sink: {victim}" in errors


def test_p1_2_close_kernel_rejects_v99_manifest_critical_gate_floor_shrink() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    victim = "src/search/benders_loop.py"
    contract = manifest["close_kernel_contract"]
    contract["critical_gate_files"] = [
        rel_path for rel_path in contract["critical_gate_files"] if rel_path != victim
    ]

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert f"close_kernel_contract.critical_gate_files missing v99 sealed gate file: {victim}" in errors


def test_p1_2_proof_obligation_review_anchor_matches_phase_anchor() -> None:
    manifest = copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))
    manifest["review_anchor"] = "unit_fake_anchor"
    manifest["close_kernel_contract"]["review_anchor"] = "unit_fake_anchor"

    errors = check_p1_2_proof_obligations._check_phase_anchor(manifest)

    assert "manifest.review_anchor must match phase_gate_required_anchor" in errors


def test_p1_2_close_kernel_self_binding_rejects_removed_close_kernel_call(tmp_path: Path) -> None:
    checker_path = tmp_path / "check_p1_2_proof_obligations.py"
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(encoding="utf-8")
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_close_kernel_contract(manifest))",
            "        # mutation: removed close-kernel contract call",
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path
    )

    assert "proof-obligation checker main must call _check_close_kernel_contract" in errors


def test_p1_2_close_kernel_self_binding_rejects_dead_branch_calls(tmp_path: Path) -> None:
    source = (PROJECT_ROOT / "scripts" / "check_p1_2_proof_obligations.py").read_text(encoding="utf-8")

    checker_path = tmp_path / "check_p1_2_proof_obligations_dead_forced.py"
    checker_path.write_text(
        source.replace(
            "    errors.extend(\n"
            "        _check_close_kernel_files_fully_pinned(l0_tree, child_tree, exact_tree)\n"
            "    )\n",
            "    if False:\n"
            "        errors.extend(\n"
            "            _check_close_kernel_files_fully_pinned(l0_tree, child_tree, exact_tree)\n"
            "        )\n",
        ),
        encoding="utf-8",
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path
    )
    assert "candidate sink replay contract must call _check_close_kernel_files_fully_pinned" in errors

    checker_path = tmp_path / "check_p1_2_proof_obligations_dead_main.py"
    checker_path.write_text(
        source.replace(
            "        errors.extend(_check_candidate_sink_replay_contract())\n",
            "        if False:\n"
            "            errors.extend(_check_candidate_sink_replay_contract())\n",
        ),
        encoding="utf-8",
    )
    errors = check_p1_2_proof_obligations._check_close_kernel_checker_self_binding(
        checker_path=checker_path
    )
    assert "proof-obligation checker main must call _check_candidate_sink_replay_contract" in errors


def test_p1_2_checker_detects_multiline_public_certified_return() -> None:
    tree = ast.parse(
        """
def run_outer_search():
    return (
        RUN_STATUS_CERTIFIED,
        {"search_status": RUN_STATUS_CERTIFIED},
    )
"""
    )
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    assert check_p1_2_proof_obligations._function_returns_status_tuple(
        function,
        "RUN_STATUS_CERTIFIED",
    )
    assert not check_p1_2_proof_obligations._function_returns_status_tuple(
        function,
        "CANDIDATE_PROPOSED_STATUS",
    )


def test_p1_2_checker_rejects_candidate_replay_isolation_removal(tmp_path: Path) -> None:
    replay_path = tmp_path / "candidate_proof_replay.py"
    source = check_p1_2_proof_obligations.CANDIDATE_PROOF_REPLAY_PATH.read_text(
        encoding="utf-8"
    )
    replay_path.write_text(
        source.replace('            "-I",', '            "-s",', 1),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
        candidate_replay_path=replay_path
    )

    assert 'candidate replay subprocess boundary missing: "-I"' in errors

    replay_core_source = check_p1_2_proof_obligations.PR2_L0_REPLAY_CORE_PATH.read_text(
        encoding="utf-8"
    )
    snapshot_path = tmp_path / "pr2_l0_replay_core_snapshot_bypass.py"
    snapshot_path.write_text(
        replay_core_source.replace(
            "normalized_replay_hashes != normalized_current_hashes",
            "False",
            1,
        ),
        encoding="utf-8",
    )
    snapshot_errors = (
        check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
            candidate_replay_core_path=snapshot_path
        )
    )
    assert (
        "isolated replay snapshot binding is missing: "
        "normalized_replay_hashes != normalized_current_hashes"
    ) in snapshot_errors


def test_p1_2_checker_rejects_frontier_sink_replay_bypass(tmp_path: Path) -> None:
    source = check_p1_2_proof_obligations.CERTIFIED_FRONTIER_PATH.read_text(
        encoding="utf-8"
    )
    frontier_path = tmp_path / "certified_frontier_bypass.py"
    frontier_path.write_text(
        source.replace(
            "project_candidate_records_for_sink(",
            "unchecked_candidate_records(",
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
        certified_frontier_path=frontier_path
    )

    assert (
        "compute_sink_verified_terminal_frontier_projection must execute "
        "project_candidate_records_for_sink"
    ) in errors
    assert (
        "build_sink_verified_terminal_frontier_evidence must execute "
        "project_candidate_records_for_sink"
    ) in errors

    weakened_path = tmp_path / "certified_frontier_weakened.py"
    weakened_path.write_text(
        source.replace(
            "require_record_solution_match=False,",
            "require_record_solution_match=True,",
        ),
        encoding="utf-8",
    )

    weakened_errors = check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
        certified_frontier_path=weakened_path
    )

    assert (
        "compute_sink_verified_terminal_frontier_projection has the wrong replay "
        "witness policy: require_record_solution_match=False"
    ) in weakened_errors

    weakened_terminal_path = tmp_path / "certified_frontier_terminal_weakened.py"
    weakened_terminal_path.write_text(
        source.replace(
            "require_record_solution_match=True,",
            "require_record_solution_match=False,",
            1,
        ),
        encoding="utf-8",
    )
    weakened_terminal_errors = (
        check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
            certified_frontier_path=weakened_terminal_path
        )
    )
    assert (
        "build_sink_verified_terminal_frontier_evidence has the wrong replay "
        "witness policy: require_record_solution_match=True"
    ) in weakened_terminal_errors

    outer_source = check_p1_2_proof_obligations.OUTER_SEARCH_PATH.read_text(
        encoding="utf-8"
    )
    outer_path = tmp_path / "outer_search_projection_not_adopted.py"
    outer_path.write_text(
        outer_source.replace(
            '        campaign.state["candidates"] = candidate_records\n',
            "",
            1,
        ),
        encoding="utf-8",
    )
    outer_errors = check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
        outer_search_path=outer_path
    )
    assert (
        "frontier must adopt replay demotions/rebindings before candidate lifecycle "
        "decisions"
    ) in outer_errors


# ---------------------------------------------------------------------------
# round-20: parent-anchor symmetry (G1), shared-walker completeness (G2), and
# witness-carrier dynamic-rebind backstop (G3).  Threat model (owner, 2026-07-03):
# a reseal-capable half-trusted adversary who recomputes every pinned hash, so a
# structural mutation must be caught by the anchors, not merely made visible by
# the source-sha floor.
# ---------------------------------------------------------------------------

_CERTIFIED_ARTIFACT_CONTRACT_PATH = (
    PROJECT_ROOT / "src" / "search" / "certified_artifact_contract.py"
)
_BENDERS_LOOP_PATH = PROJECT_ROOT / "src" / "search" / "benders_loop.py"
_CERTIFIED_FRONTIER_PATH = PROJECT_ROOT / "src" / "search" / "certified_frontier.py"

_BENDERS_REVERIFIER_IMPORT = (
    "from src.search.independent_infeasibility_reverifier import (\n"
    "    REVERIFY_STATUS_DIVERGED_FEASIBLE,\n"
    "    reverify_whole_layout_infeasibility,\n"
    ")\n"
)


def _parent_source() -> str:
    return _CERTIFIED_ARTIFACT_CONTRACT_PATH.read_text(encoding="utf-8")


def _contract_anchor_errors_for_parent_source(tmp_path: Path, source: str) -> list[str]:
    parent_path = tmp_path / "certified_artifact_contract.py"
    parent_path.write_text(source, encoding="utf-8", newline="\n")
    return check_p1_2_proof_obligations._check_certified_artifact_contract_runtime_anchor(
        path=parent_path
    )


def _benders_source() -> str:
    return _BENDERS_LOOP_PATH.read_text(encoding="utf-8")


def _reverifier_contract_errors_for_benders_source(tmp_path: Path, source: str) -> list[str]:
    benders_path = tmp_path / "benders_loop.py"
    benders_path.write_text(source, encoding="utf-8", newline="\n")
    return check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path
    )


def test_p1_2_round20_parent_anchor_rejects_decorated_parent_gate_function(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _parent_source(),
        "def validate_locked_p1_2_close_kernel(project_root: Path) -> None:",
        "def _r20_noop_dec(fn):\n    return fn\n\n\n@_r20_noop_dec\n"
        "def validate_locked_p1_2_close_kernel(project_root: Path) -> None:",
    )
    errors = _contract_anchor_errors_for_parent_source(tmp_path, source)
    assert any(
        "must be undecorated so its runtime binding is the" in error for error in errors
    )


def test_p1_2_round20_parent_anchor_rejects_top_level_dynamic_namespace_write(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _parent_source(),
        'LOCKED_EXACT_PROJECT_MARKER = "PROJECT_LOCK.md"\n',
        'LOCKED_EXACT_PROJECT_MARKER = "PROJECT_LOCK.md"\n'
        'globals()["validate_locked_p1_2_close_kernel"] = lambda project_root: None\n',
    )
    errors = _contract_anchor_errors_for_parent_source(tmp_path, source)
    assert any(
        "must not dynamically write a module or class namespace" in error
        for error in errors
    )


def test_p1_2_round20_parent_anchor_rejects_critical_name_attribute_monkeypatch(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _parent_source(),
        'LOCKED_EXACT_PROJECT_MARKER = "PROJECT_LOCK.md"\n',
        'LOCKED_EXACT_PROJECT_MARKER = "PROJECT_LOCK.md"\n'
        "subprocess.run = lambda *a, **k: None\n",
    )
    errors = _contract_anchor_errors_for_parent_source(tmp_path, source)
    assert any(
        "must not rebind a protected symbol via an attribute write" in error
        for error in errors
    )


def test_p1_2_round20_parent_anchor_rejects_critical_name_rebind(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _parent_source(),
        "import subprocess\n",
        "import subprocess\nsubprocess = subprocess\n",
    )
    errors = _contract_anchor_errors_for_parent_source(tmp_path, source)
    assert any(
        "must have exactly one module-level binding" in error for error in errors
    )


def test_p1_2_round20_witness_binding_rejects_while_body_rebind(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _benders_source(),
        _BENDERS_REVERIFIER_IMPORT,
        _BENDERS_REVERIFIER_IMPORT
        + "while True:\n    reverify_whole_layout_infeasibility = None\n    break\n",
    )
    errors = _reverifier_contract_errors_for_benders_source(tmp_path, source)
    assert any(
        "must have exactly one module-level runtime binding" in error for error in errors
    )


def test_p1_2_round20_witness_binding_rejects_wildcard_import(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _benders_source(),
        _BENDERS_REVERIFIER_IMPORT,
        _BENDERS_REVERIFIER_IMPORT + "from json import *\n",
    )
    errors = _reverifier_contract_errors_for_benders_source(tmp_path, source)
    assert any(
        "must not share the module top level with a wildcard import" in error
        for error in errors
    )


def test_p1_2_round20_benders_contract_rejects_class_attribute_method_rebind(
    tmp_path: Path,
) -> None:
    source = (
        _benders_source()
        + "\n\ndef _r20_noop_nogood(self, **kwargs):\n    return True\n\n\n"
        "LBBDController._add_exact_whole_layout_nogood = _r20_noop_nogood\n"
    )
    errors = _reverifier_contract_errors_for_benders_source(tmp_path, source)
    assert any(
        "must not rebind a protected symbol via an attribute write" in error
        for error in errors
    )


def test_p1_2_round20_benders_contract_rejects_instance_lookup_hook(
    tmp_path: Path,
) -> None:
    source = _replace_once(
        _benders_source(),
        "class LBBDController:",
        "class LBBDController:\n"
        "    def __getattribute__(self, name):\n"
        "        return object.__getattribute__(self, name)\n",
    )
    errors = _reverifier_contract_errors_for_benders_source(tmp_path, source)
    assert any(
        "must not define instance attribute lookup/write hooks" in error
        for error in errors
    )


def test_p1_2_round20_witness_carrier_rejects_function_code_swap() -> None:
    source = (
        _CERTIFIED_FRONTIER_PATH.read_text(encoding="utf-8")
        + "\n\ndef _r20_noop_ev(*a, **k):\n    return {}\n\n\n"
        "build_sink_verified_terminal_frontier_evidence.__code__ = _r20_noop_ev.__code__\n"
    )
    tree = ast.parse(source)
    function = check_p1_2_proof_obligations._function_def(
        tree,
        "build_sink_verified_terminal_frontier_evidence",
        path=_CERTIFIED_FRONTIER_PATH,
    )
    errors = check_p1_2_proof_obligations._imported_direct_call_errors(
        tree=tree,
        function=function,
        path=_CERTIFIED_FRONTIER_PATH,
        function_label="terminal frontier evidence",
        module="src.search.terminal_fixed_witness_capsule",
        name="build_terminal_fixed_witness_projection_at_sink",
    )
    assert any(
        "must not rebind a protected symbol via an attribute write" in error
        for error in errors
    )


def test_p1_2_round20_checker_closed_world_rejects_vararg_annotation_primitive(
    tmp_path: Path,
) -> None:
    source = _checker_source_before_entrypoint(
        _checker_source(),
        'def _r20_vararg(**_kw: globals().__setitem__("main", lambda: 0)) -> None:\n'
        "    return None\n",
    )
    errors = _checker_self_binding_errors_for_source(
        tmp_path, source, name="checker_vararg_annotation_primitive.py"
    )
    assert any(
        "module top level contains disallowed statement FunctionDef" in error
        for error in errors
    )


def test_p1_2_round20_parent_binding_walker_mirrors_checker() -> None:
    from src.search import certified_artifact_contract as cac

    checker_walker = check_p1_2_proof_obligations._current_scope_bound_names
    parent_walker = cac._locked_current_scope_bound_names
    walker_samples = (
        "def f(*a: (x := 0), **k: (y := 1)) -> None:\n    pass\n",
        "def f(p: (z := 2)) -> None:\n    pass\n",
        "while True:\n    w = None\n    break\n",
        "try:\n    pass\nexcept (e := ValueError):\n    pass\n",
        "class C(B, metaclass=(m := type)):\n    pass\n",
        "with open('x') as g:\n    pass\n",
        "for q in [(r := 0)]:\n    s = None\n",
    )
    for src in walker_samples:
        node = ast.parse(src).body[0]
        assert checker_walker(node) == parent_walker(node), src

    checker_closed_world = check_p1_2_proof_obligations._checker_module_top_level_statement_allowed
    parent_closed_world = cac._locked_checker_top_level_statement_allowed
    closed_world_samples = (
        'def f(**k: globals().__setitem__("main", lambda: 0)) -> int:\n    return 0\n',
        "def f(*a: setattr) -> int:\n    return 0\n",
        "x = 1\n",
        "import sys\n",
    )
    for src in closed_world_samples:
        node = ast.parse(src).body[0]
        assert checker_closed_world(
            node, is_first=False, is_last=False
        ) == parent_closed_world(node, is_first=False, is_last=False), src

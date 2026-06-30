"""Tests for the P1.2 proof-obligation consolidation gate."""
from __future__ import annotations

import ast
import copy
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
) -> list[str]:
    child_path = tmp_path / "pr2_l0_true_verifier_child.py"
    l0_path = tmp_path / "pr2_l0_micro_verifier_core.py"
    exact_path = tmp_path / "exact_campaign.py"
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
    try:
        return check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
            exact_campaign_path=exact_path,
            pr2_l0_path=l0_path,
            pr2_true_child_path=child_path,
        )
    except check_p1_2_proof_obligations.CheckError as exc:
        return [str(exc)]


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
        "    from src.search.exact_campaign import (\n"
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
        "    from src.search.exact_campaign import (\n",
        "    from fake.search.exact_campaign import (\n",
    )


def _child_setattr_monkeypatches_precheck(source: str) -> str:
    import_block = (
        "    from src.search.exact_campaign import (\n"
        "        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,\n"
        "        terminal_certified_final_result_project_precheck_violation,\n"
        "    )\n"
    )
    return _replace_once(
        source,
        import_block,
        "    import src.search.exact_campaign as exact_campaign_module\n"
        '    setattr(exact_campaign_module, "terminal_certified_final_result_project_precheck_violation", lambda *_args, **_kwargs: None)\n'
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
        "    import src.search.exact_campaign as _authority_module\n"
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
        "    from src.search.exact_campaign import (\n"
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
        "    from src.search.exact_campaign import (\n"
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
        "    from src.search.exact_campaign import (\n"
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
        "from src.search import exact_campaign as _m\n"
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
        "    from src.search.candidate_proof_replay import _materialize_replay_snapshot\n",
        "    return {}, {}, None\n"
        "    from src.search.candidate_proof_replay import _materialize_replay_snapshot\n",
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


def test_p1_2_checker_accepts_pr2_supervisor_ast_pins_current_sources(tmp_path: Path) -> None:
    errors = _candidate_sink_replay_errors_for_sources(tmp_path)

    assert errors == []


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
            "exact",
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


@pytest.mark.parametrize(
    ("source_kind", "mutator", "expected_error"),
    [
        ("child", _child_early_return_before_precheck, "exactly one Return"),
        ("child", _child_code_object_monkeypatches_precheck, "dunder attribute __code__"),
        ("child", _child_globals_monkeypatches_precheck, "dunder attribute __globals__"),
        ("child", _child_importfrom_builtins_setattr_alias, "ImportFrom outside pinned allowlist"),
        ("child", _child_builtins_dict_facade, "must not reference __builtins__"),
        ("child", _child_module_top_level_monkeypatch, "module top level must not assign non-Name targets"),
        ("child", _child_return_unpack_overrides_domain, "must exactly match the pinned key set"),
        ("child", _child_return_tcb_side_effect_call, "final return domain key tcb must match pinned expression"),
        ("child", _child_precheck_extra_kwarg, "terminal precheck call must be exactly"),
        ("l0", _l0_child_verdict_forged_rebind, "must not rebind child/domain/proposal data"),
        ("child", _child_duplicate_verify_supervisor_domain, "must be unique"),
        ("l0", _l0_duplicate_run_l0_supervisor_seal, "must be unique"),
        ("exact", _exact_duplicate_transition_helper, "must be unique"),
        ("child", _child_decorated_verify_supervisor_domain, "must not use decorators"),
        ("child", _child_top_level_rebinds_verify, "must be unique"),
        ("child", _child_helper_code_swap, "dunder attribute __code__"),
        ("child", _child_shadows_getattr, "must not shadow/rebind getattr"),
        ("child", _child_class_body_side_effect, "body contains import-time executable statement"),
        ("l0", _l0_object_setattr_forges_child_verdict, "mutator/reflection hook"),
        ("l0", _l0_domain_update_after_assignment, "mutator/reflection hook"),
        ("l0", _l0_child_verdict_response_update, "mutator/reflection hook"),
        ("l0", _l0_child_payload_update_after_verdict, "mutator/reflection hook"),
        ("l0", _l0_type_setitem_domain, "mutator/reflection hook"),
        ("l0", _l0_class_setitem_domain, "mutator/reflection hook"),
        ("l0", _l0_transition_starts_with_return, "unconditional top-level Return"),
        ("exact", _exact_transition_starts_with_return, "unconditional top-level Return"),
        ("l0", _l0_postwrite_starts_with_return, "unconditional top-level Return"),
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
            "authority imports must come directly from src.search.exact_campaign",
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

    snapshot_path = tmp_path / "candidate_proof_replay_snapshot_bypass.py"
    snapshot_path.write_text(
        source.replace(
            "normalized_replay_hashes != normalized_current_hashes",
            "False",
            1,
        ),
        encoding="utf-8",
    )
    snapshot_errors = (
        check_p1_2_proof_obligations._check_candidate_sink_replay_contract(
            candidate_replay_path=snapshot_path
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

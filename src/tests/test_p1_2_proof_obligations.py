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


def _publisher_scan_paths() -> list[Path]:
    return [
        check_p1_2_proof_obligations.CERTIFIED_SURFACE_PATH,
        PROJECT_ROOT / "scripts" / "export_industrial_planner_bundle.py",
    ]


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

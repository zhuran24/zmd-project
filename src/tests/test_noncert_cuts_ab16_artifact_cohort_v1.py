from __future__ import annotations

import copy
from pathlib import Path

import pytest

from docs.research.noncert_cuts_ab16_20260724 import ab16_artifact_cohort_v1 as cohort


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PROSPECTIVE_SCHEMAS = {
    "resource_profile_set": "noncert-cuts-ab16-resource-profile-set-v2",
    "stage_resource_admission": "noncert-cuts-ab16-stage-resource-admission-v2",
    "calibration_declaration": "noncert-cuts-ab16-resource-calibration-declaration-v1",
    "calibration_sample": "noncert-cuts-ab16-resource-calibration-sample-v1",
    "calibration_validation": "noncert-cuts-ab16-resource-calibration-validation-v1",
    "calibration_aggregate": "noncert-cuts-ab16-resource-calibration-aggregate-v1",
    "calibration_profile_candidate": "noncert-cuts-ab16-resource-calibration-profile-candidate-v1",
    "calibration_outside_replay": "noncert-cuts-ab16-resource-calibration-outside-replay-v1",
    "gate_a_receipt": "noncert-cuts-ab16-bootstrap-gate-a-receipt-v3",
    "gate_a_candidate": "noncert-cuts-ab16-bootstrap-offline-candidate-v3",
    "gate_a_full_preflight": "noncert-cuts-ab16-gate-a-full-preflight-receipt-v7",
    "gate_a_publication_commit": "noncert-cuts-ab16-gate-a-preflight-publication-commit-v2",
    "gate_b_qualification": "noncert-cuts-ab16-gate-b-qualification-v3",
    "gate_b_resource_gate": "noncert-cuts-ab16-gate-b-resource-gate-v3",
    "gate_b_owner_request": "noncert-cuts-ab16-gate-b-owner-request-v2",
    "gate_b_owner_response": "noncert-cuts-ab16-gate-b-owner-response-v2",
    "gate_b_owner_release": "noncert-cuts-ab16-gate-b-owner-release-v2",
    "gate_b_epoch_observation": "noncert-cuts-ab16-gate-b-epoch-observation-v5",
    "gate_b_approval": "noncert-cuts-ab16-bootstrap-gate-b-approval-v6",
    "gate_b_handoff_request": "noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v2",
    "gate_b_handoff_response": "noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v2",
    "terminal_history_freeze": "noncert-cuts-ab16-terminal-reference-history-freeze-v1",
    "terminal_history_replay": "noncert-cuts-ab16-terminal-reference-history-replay-v2",
    "bootstrap_manager_capture": "noncert-cuts-ab16-bootstrap-manager-epoch-capture-v3",
    "bootstrap_result": "noncert-cuts-ab16-campaign-bootstrap-result-v5",
    "repository_snapshot": "noncert-cuts-ab16-repository-snapshot-v1",
    "repository_snapshot_materialization": (
        "noncert-cuts-ab16-repository-snapshot-materialization-v1"
    ),
    "external_platform_assumptions": "noncert-cuts-ab16-external-platform-assumptions-v2",
    "path_preregistration": "noncert-cuts-ab16-path-preregistration-v5",
    "bootstrap_budget_contract": "noncert-cuts-ab16-bootstrap-budget-contract-v1",
    "bootstrap_budget_terminal": "noncert-cuts-ab16-bootstrap-budget-terminal-v1",
    "bootstrap_package_failure_closeout": "noncert-cuts-ab16-bootstrap-package-failure-closeout-v1",
    "formal_root_budget_contract": "noncert-cuts-ab16-formal-root-budget-contract-v1",
    "formal_root_budget_journal": "noncert-cuts-ab16-formal-root-budget-journal-v1",
    "formal_root_budget_terminal": "noncert-cuts-ab16-formal-root-budget-terminal-v1",
    "arm_budget_allocation": "noncert-cuts-ab16-arm-budget-allocation-v1",
    "arm_budget_terminal": "noncert-cuts-ab16-arm-budget-terminal-v1",
    "package_independent_replay": "noncert-cuts-ab16-campaign-package-independent-replay-v1",
    "formal_launch_context": "noncert-cuts-ab16-formal-launch-context-v4",
    "formal_owner_request": "noncert-cuts-ab16-formal-launch-owner-request-v2",
    "formal_owner_response": "noncert-cuts-ab16-formal-launch-owner-response-v2",
    "formal_admission": "noncert-cuts-ab16-formal-launch-admission-v3",
    "formal_guardian_ready": "noncert-cuts-ab16-formal-guardian-ready-v2",
    "formal_attempt_consumption": "noncert-cuts-ab16-formal-attempt-consumption-v2",
    "formal_selection": "noncert-cuts-ab16-formal-launch-selection-v2",
    "formal_outer_prelaunch": "noncert-cuts-ab16-outer-formal-prelaunch-v3",
    "formal_outer_start": "noncert-cuts-ab16-outer-formal-start-v3",
    "continuation_authorization": "noncert-cuts-gate1-v4-continuation-authorization-v1",
    "baseline_admission": "noncert-cuts-ab16-baseline-admission-v1",
    "common_prestate": "noncert-cuts-ab16-common-prestate-v1",
    "campaign_manifest": "noncert-cuts-ab16-organic-manifest-v3",
    "suite_selection": "noncert-cuts-ab16-suite-selection-v3",
    "arm_binding": "noncert-cuts-ab16-arm-binding-v2",
    "arm_pre_run": "noncert-cuts-ab16-organic-pre-run-authority-v3",
    "arm_selection": "noncert-cuts-ab16-organic-arm-selection-v2",
    "arm_result": "noncert-cuts-ab16-organic-arm-result-v2",
    "arm_module_origin": "noncert-cuts-ab16-organic-arm-module-origin-receipt-v2",
    "supervisor_module_origin": "noncert-cuts-ab16-organic-supervisor-module-origin-receipt-v1",
    "lifecycle_inner": "noncert-cuts-ab16-inner-lifecycle-v3",
    "lifecycle_preterminal": "noncert-cuts-ab16-preterminal-resource-v3",
    "lifecycle_release": "noncert-cuts-ab16-release-token-v3",
    "lifecycle_terminal": "noncert-cuts-ab16-terminal-envelope-v3",
    "lifecycle_cleanup": "noncert-cuts-ab16-cleanup-v3",
    "reference_acquisition": "noncert-cuts-ab16-unit-reference-acquisition-v2",
    "reference_release": "noncert-cuts-ab16-unit-reference-release-v2",
    "reference_manager_epoch": "noncert-cuts-ab16-manager-epoch-observation-v2",
    "reference_capability_transcript": "noncert-cuts-ab16-reference-capability-transcript-v1",
    "reference_lifecycle": "noncert-cuts-ab16-formal-reference-lifecycle-v1",
    "detached_resource_terminal": "noncert-cuts-ab16-detached-resource-terminal-v3",
    "independent_resource_terminal_replay": (
        "noncert-cuts-ab16-independent-resource-terminal-replay-v1"
    ),
    "arm_cut_free_replay": "noncert-cuts-ab16-organic-cut-free-incumbent-replay-v1",
    "fixed_baseline_replay": "noncert-cuts-ab16-fixed-assignment-replay-v2",
    "arm_arithmetic_replay": "noncert-cuts-ab16-independent-organic-arm-replay-v2",
    "arm_credibility": "noncert-cuts-ab16-arm-credibility-gate-v3",
    "terminal_classification": "noncert-cuts-ab16-terminal-classification-v3",
    "arm_attempt_manifest": "noncert-cuts-ab16-organic-attempt-artifact-manifest-v1",
    "arm_attempt_root_replay": "noncert-cuts-ab16-organic-attempt-root-replay-v1",
    "arm_consumption": "noncert-cuts-ab16-organic-arm-consumption-v3",
    "arm_allocation_unselected_terminal": (
        "noncert-cuts-ab16-arm-allocation-unselected-terminal-v1"
    ),
    "arm_consumed_incomplete": "noncert-cuts-ab16-arm-consumed-incomplete-v1",
    "immediate_stop": "noncert-cuts-ab16-immediate-stop-v2",
    "formal_arm_prelaunch": "noncert-cuts-ab16-formal-arm-prelaunch-v3",
    "formal_controller_result": "noncert-cuts-ab16-formal-controller-result-v3",
    "reference_post_unref_absence": "noncert-cuts-ab16-unit-reference-post-unref-absence-v1",
    "reference_terminal": "noncert-cuts-ab16-unit-reference-terminal-v1",
    "reference_connection_close": "noncert-cuts-ab16-unit-reference-connection-close-v1",
    "recovery_disarm_intent": "noncert-cuts-ab16-recovery-disarm-intent-v1",
    "recovery_disarm_terminal": "noncert-cuts-ab16-recovery-disarm-terminal-v1",
    "closure_actor_ready": "noncert-cuts-ab16-closure-actor-ready-v1",
    "formal_containment": "noncert-cuts-ab16-formal-containment-v2",
    "success_pre_release": "noncert-cuts-ab16-formal-pre-release-success-v3",
    "success_guardian_lock_close": "noncert-cuts-ab16-outer-guardian-lock-close-v2",
    "success_guardian_absence": "noncert-cuts-ab16-formal-guardian-absence-v2",
    "success_dual_lock_release": "noncert-cuts-ab16-formal-dual-lock-release-v3",
    "formal_markerless_incomplete": "noncert-cuts-ab16-formal-markerless-incomplete-v1",
    "formal_consumed_incomplete": "noncert-cuts-ab16-formal-consumed-incomplete-v3",
    "incomplete_pre_release": "noncert-cuts-ab16-formal-pre-release-failure-v4",
    "incomplete_detached": "noncert-cuts-ab16-formal-detached-incomplete-v4",
    "incomplete_terminal_release": "noncert-cuts-ab16-formal-failure-terminal-release-v4",
}


def test_prospective_cohort_expands_to_the_exact_launch_blocked_matrix() -> None:
    document = cohort.expanded_prospective_cohort()

    assert document["schema_version"] == "noncert-cuts-ab16-artifact-cohort-v1"
    assert document["cohort_id"] == "noncert-cuts-ab16-resource-budget-authority-readiness-v1"
    assert document["authority_scope"] == "AB16_RESEARCH_ONLY"
    assert document["launch_ready"] is False
    assert document["historical_replay_only"] is False
    assert document["a039_in_scope"] is False
    assert document["package_roles"] == {
        "independent_verifier": "package_independent_verifier_v1",
    }
    assert document["schemas"] == EXPECTED_PROSPECTIVE_SCHEMAS
    assert cohort.validate_prospective_cohort(document) is document


def test_current_matrix_is_separate_replay_only_and_does_not_authorize_a039() -> None:
    historical = cohort.expanded_historical_cohort()
    prospective = cohort.expanded_prospective_cohort()

    assert historical["cohort_id"] == "noncert-cuts-ab16-current-authority-cohort-v1"
    assert historical["launch_ready"] is False
    assert historical["historical_replay_only"] is True
    assert historical["immutable_roots_are_bound_to_own_pinned_bytes"] is True
    assert historical["immutable_roots"] == [
        "A031",
        "A032",
        "A033",
        "A034",
        "A035",
        "A036",
        "A037",
        "A038",
    ]
    assert historical["schemas"] is not prospective["schemas"]
    assert historical["schemas"]["gate_b_approval"].endswith("-v5")
    assert prospective["schemas"]["gate_b_approval"].endswith("-v6")
    assert "A039" not in historical["immutable_roots"]


@pytest.mark.parametrize(
    "mutation",
    (
        "omit",
        "unknown",
        "legacy_mix",
        "role_mix",
        "launch_ready",
    ),
)
def test_prospective_cohort_rejects_any_omission_addition_or_mix(mutation: str) -> None:
    document = cohort.expanded_prospective_cohort()

    if mutation == "omit":
        del document["schemas"]["arm_attempt_root_replay"]
    elif mutation == "unknown":
        document["schemas"]["auxiliary_unversioned_escape"] = "noncert-cuts-ab16-unknown-v1"
    elif mutation == "legacy_mix":
        document["schemas"]["gate_b_approval"] = cohort.HISTORICAL_ACCEPTED_SCHEMAS["gate_b_approval"]
    elif mutation == "role_mix":
        document["package_roles"]["independent_verifier"] = "ambient_repository_verifier"
    else:
        document["launch_ready"] = True

    with pytest.raises(cohort.CohortContractError):
        cohort.validate_no_cross_cohort_mix(document)


def test_every_changed_historical_discriminator_fails_when_substituted() -> None:
    shared_keys = set(cohort.HISTORICAL_ACCEPTED_SCHEMAS) & set(cohort.PROSPECTIVE_SCHEMAS)
    changed_keys = {
        key
        for key in shared_keys
        if cohort.HISTORICAL_ACCEPTED_SCHEMAS[key] != cohort.PROSPECTIVE_SCHEMAS[key]
    }
    assert changed_keys

    for key in changed_keys:
        document = cohort.expanded_prospective_cohort()
        document["schemas"][key] = cohort.HISTORICAL_ACCEPTED_SCHEMAS[key]
        with pytest.raises(cohort.CohortContractError, match=rf"\.schemas\.{key}: value drifted"):
            cohort.validate_prospective_cohort(document)


def test_root_and_outside_replay_closure_are_non_self_referential_and_closed() -> None:
    document = cohort.expanded_prospective_cohort()
    root = document["root_closure"]
    outside = document["outside_replay_closure"]

    assert root == {
        "fixed_terminal_member_kind": "manifest",
        "exact_member_formula": (
            "manifest_entry_paths UNION {fixed_manifest_path} == complete_root_descendant_paths"
        ),
        "manifest_path_excluded_from_entries": True,
        "manifest_contains_own_sha256": False,
        "manifest_contains_own_size": False,
        "entries_bind_node_type": True,
        "regular_entries_bind_mode_size_sha256": True,
        "directory_entries_bind_mode": True,
        "symlinks_allowed": False,
        "special_nodes_allowed": False,
        "writes_after_manifest": False,
    }
    assert outside == {
        "fixed_terminal_member_kind": "receipt",
        "exact_member_formula": (
            "receipt_manifest_entry_paths UNION {fixed_receipt_path} "
            "== complete_replay_root_descendant_paths"
        ),
        "receipt_path_excluded_from_entries": True,
        "receipt_contains_own_sha256": False,
        "receipt_contains_own_size": False,
        "entries_bind_node_type": True,
        "regular_entries_bind_mode_size_sha256": True,
        "directory_entries_bind_mode": True,
        "symlinks_allowed": False,
        "special_nodes_allowed": False,
        "writes_after_receipt": False,
    }

    for field in ("root_closure", "outside_replay_closure"):
        tampered = copy.deepcopy(document)
        tampered[field]["writes_after_manifest" if field == "root_closure" else "writes_after_receipt"] = True
        with pytest.raises(cohort.CohortContractError):
            cohort.validate_prospective_cohort(tampered)


def test_all_authority_expansion_flags_remain_false() -> None:
    document = cohort.expanded_prospective_cohort()

    assert document["authority_flags"] == {
        "changes_upper_bound": False,
        "changes_lower_bound": False,
        "cut_authority": False,
        "whole_witness_authority": False,
        "production_authority": False,
        "certified_authority": False,
        "stage_b_promotion_authority": False,
    }
    assert all(value is False for value in document["authority_flags"].values())


def test_project_lock_registers_every_prospective_schema_without_auxiliary_escape() -> None:
    lock_text = (ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    section = lock_text.split(
        "The prospective resource-budget authority-readiness cohort is exactly",
        maxsplit=1,
    )[1].split(
        "The terminal-reference history freeze remains",
        maxsplit=1,
    )[0]
    normalized_section = " ".join(section.split())

    assert "`noncert-cuts-ab16-resource-budget-authority-readiness-v1`" in section
    assert "`launch_ready=false`" in section
    assert "There is no auxiliary-schema escape" in normalized_section
    assert "`package_independent_verifier_v1`" in section
    for schema in EXPECTED_PROSPECTIVE_SCHEMAS.values():
        assert f"`{schema}`" in section

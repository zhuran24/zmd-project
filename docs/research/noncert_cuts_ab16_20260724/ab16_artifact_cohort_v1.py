"""Closed schema cohort for the prospective AB16 resource-budget authority.

This module is a declaration and validator only.  It performs no filesystem
operation, owns no descriptor, publishes no artifact, and grants no launch
authority.  Historical roots remain replayable only by their own pinned
bytes.  The prospective cohort stays blocked until its separately specified
implementation, calibration, and launch gates are complete.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, NoReturn


COHORT_DOCUMENT_SCHEMA: Final = "noncert-cuts-ab16-artifact-cohort-v1"
HISTORICAL_COHORT_ID: Final = "noncert-cuts-ab16-current-authority-cohort-v1"
PROSPECTIVE_COHORT_ID: Final = "noncert-cuts-ab16-resource-budget-authority-readiness-v1"
AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"
PACKAGE_VERIFIER_ROLE: Final = "tool.package_independent_verifier_v1.py"
NATIVE_HELPER_WRAPPER_ROLE: Final = "tool.ab16_native_budget_helper_v1.py"
NATIVE_HELPER_BINARY_ROLE: Final = "system.native_budget_helper.bin"
FINAL_RELEASE_ACTOR_ROLE: Final = "tool.ab16_final_release_actor_v1.py"

IMMUTABLE_HISTORICAL_ROOTS: Final = (
    "A031",
    "A032",
    "A033",
    "A034",
    "A035",
    "A036",
    "A037",
    "A038",
)

FALSE_AUTHORITY_FLAGS: Final = MappingProxyType(
    {
        "changes_upper_bound": False,
        "changes_lower_bound": False,
        "cut_authority": False,
        "whole_witness_authority": False,
        "production_authority": False,
        "certified_authority": False,
        "stage_b_promotion_authority": False,
    }
)

# The accepted current matrix is retained only to classify immutable historical
# roots.  It is never a fallback for the prospective cohort.
HISTORICAL_ACCEPTED_SCHEMAS: Final = MappingProxyType(
    {
        "resource_profile_set": "noncert-cuts-ab16-resource-profile-set-v1",
        "stage_resource_admission": "noncert-cuts-ab16-stage-resource-admission-v1",
        "gate_a_receipt": "noncert-cuts-ab16-bootstrap-gate-a-receipt-v2",
        "gate_a_candidate": "noncert-cuts-ab16-bootstrap-offline-candidate-v2",
        "gate_a_full_preflight": "noncert-cuts-ab16-gate-a-full-preflight-receipt-v6",
        "gate_a_publication_commit": "noncert-cuts-ab16-gate-a-preflight-publication-commit-v1",
        "gate_b_qualification": "noncert-cuts-ab16-gate-b-qualification-v2",
        "gate_b_resource_gate": "noncert-cuts-ab16-gate-b-resource-gate-v2",
        "gate_b_owner_request": "noncert-cuts-ab16-gate-b-owner-request-v1",
        "gate_b_owner_response": "noncert-cuts-ab16-gate-b-owner-response-v1",
        "gate_b_owner_release": "noncert-cuts-ab16-gate-b-owner-release-v1",
        "gate_b_epoch_observation": "noncert-cuts-ab16-gate-b-epoch-observation-v4",
        "gate_b_approval": "noncert-cuts-ab16-bootstrap-gate-b-approval-v5",
        "gate_b_handoff_request": "noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v1",
        "gate_b_handoff_response": "noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v1",
        "terminal_history_freeze": "noncert-cuts-ab16-terminal-reference-history-freeze-v1",
        "terminal_history_replay": "noncert-cuts-ab16-terminal-reference-history-replay-v2",
        "bootstrap_manager_capture": "noncert-cuts-ab16-bootstrap-manager-capture-v2",
        "bootstrap_result": "noncert-cuts-ab16-campaign-bootstrap-result-v4",
        "repository_snapshot": "noncert-cuts-ab16-repository-snapshot-v1",
        "repository_snapshot_materialization": (
            "noncert-cuts-ab16-repository-snapshot-materialization-v1"
        ),
        "external_platform_assumptions": "noncert-cuts-ab16-external-platform-assumptions-v2",
        "path_preregistration": "noncert-cuts-ab16-path-preregistration-v4",
        "formal_launch_context": "noncert-cuts-ab16-formal-launch-context-v3",
        "formal_owner_request": "noncert-cuts-ab16-formal-launch-owner-request-v1",
        "formal_owner_response": "noncert-cuts-ab16-formal-launch-owner-response-v1",
        "formal_admission": "noncert-cuts-ab16-formal-launch-admission-v2",
        "formal_guardian_ready": "noncert-cuts-ab16-outer-guardian-ready-v1",
        "formal_attempt_consumption": "noncert-cuts-ab16-formal-attempt-consumption-v1",
        "formal_selection": "noncert-cuts-ab16-formal-launch-selection-v1",
        "formal_outer_prelaunch": "noncert-cuts-ab16-formal-outer-prelaunch-v2",
        "formal_outer_start": "noncert-cuts-ab16-formal-outer-start-v2",
        "continuation_authorization": "noncert-cuts-gate1-v4-continuation-authorization-v1",
        "baseline_admission": "noncert-cuts-ab16-baseline-admission-v1",
        "common_prestate": "noncert-cuts-ab16-common-prestate-v1",
        "campaign_manifest": "noncert-cuts-ab16-organic-manifest-v2",
        "suite_selection": "noncert-cuts-ab16-suite-selection-v2",
        "arm_binding": "noncert-cuts-ab16-arm-binding-v2",
        "arm_pre_run": "noncert-cuts-ab16-organic-pre-run-authority-v2",
        "arm_selection": "noncert-cuts-ab16-organic-arm-selection-v1",
        "arm_consumption": "noncert-cuts-ab16-organic-arm-consumption-v2",
        "formal_arm_prelaunch": "noncert-cuts-ab16-formal-arm-prelaunch-v2",
        "formal_controller_result": "noncert-cuts-ab16-formal-controller-result-v2",
        "immediate_stop": "noncert-cuts-ab16-immediate-stop-v1",
        "success_pre_release": "noncert-cuts-ab16-formal-pre-release-success-v2",
        "success_guardian_lock_close": "noncert-cuts-ab16-outer-guardian-lock-close-v1",
        "success_guardian_absence": "noncert-cuts-ab16-formal-guardian-absence-v1",
        "success_dual_lock_release": "noncert-cuts-ab16-formal-dual-lock-release-v2",
        "formal_consumed_incomplete": "noncert-cuts-ab16-formal-consumed-incomplete-v2",
        "incomplete_pre_release": "noncert-cuts-ab16-formal-pre-release-failure-v3",
        "incomplete_detached": "noncert-cuts-ab16-formal-detached-incomplete-v3",
        "incomplete_terminal_release": "noncert-cuts-ab16-formal-failure-terminal-release-v3",
        "markerless_incomplete": "noncert-cuts-ab16-formal-markerless-incomplete-v1",
        "reference_lifecycle": "noncert-cuts-ab16-formal-reference-lifecycle-v1",
        "containment_hold": "noncert-cuts-ab16-formal-containment-hold-v1",
        "containment_guardian_absence": "noncert-cuts-ab16-containment-guardian-absence-v1",
        "containment_cleared": "noncert-cuts-ab16-formal-containment-cleared-after-hold-v1",
        "formal_lock_release": "noncert-cuts-ab16-formal-lock-release-v1",
    }
)

# These are the only additional historical discriminator literals allowed in a
# package source.  The reverse AST check combines this set with the exact
# accepted historical matrix above; an unregistered literal is never inferred
# to be a compatibility path merely because it has an older-looking suffix.
HISTORICAL_SCHEMA_LITERAL_ALLOWLIST: Final = frozenset(
    {
        *HISTORICAL_ACCEPTED_SCHEMAS.values(),
        "noncert-cuts-ab16-abort-cleanup-v1",
        "noncert-cuts-ab16-arm-binding-v1",
        "noncert-cuts-ab16-arm-credibility-gate-v1",
        "noncert-cuts-ab16-arm-credibility-gate-v2",
        "noncert-cuts-ab16-bootstrap-gate-a-receipt-v1",
        "noncert-cuts-ab16-bootstrap-gate-b-approval-v1",
        "noncert-cuts-ab16-bootstrap-manager-capture-v1",
        "noncert-cuts-ab16-bootstrap-offline-candidate-v1",
        "noncert-cuts-ab16-campaign-bootstrap-result-v1",
        "noncert-cuts-ab16-cleanup-v1",
        "noncert-cuts-ab16-cleanup-v2",
        "noncert-cuts-ab16-containment-guardian-absence-v1",
        "noncert-cuts-ab16-detached-resource-terminal-v1",
        "noncert-cuts-ab16-detached-resource-terminal-v2",
        "noncert-cuts-ab16-disposable-drill-authority-result-v1",
        "noncert-cuts-ab16-disposable-drill-authority-v1",
        "noncert-cuts-ab16-disposable-drill-control-v1",
        "noncert-cuts-ab16-disposable-drill-package-manifest-v1",
        "noncert-cuts-ab16-disposable-drill-root-v1",
        "noncert-cuts-ab16-external-platform-assumptions-v2",
        "noncert-cuts-ab16-fixed-assignment-replay-v1",
        "noncert-cuts-ab16-formal-containment-cleared-after-hold-v1",
        "noncert-cuts-ab16-formal-containment-hold-v1",
        "noncert-cuts-ab16-formal-detached-incomplete-v3",
        "noncert-cuts-ab16-formal-launch-owner-request-v1",
        "noncert-cuts-ab16-formal-launch-owner-response-v1",
        "noncert-cuts-ab16-formal-launch-selection-v2",
        "noncert-cuts-ab16-formal-lock-release-v1",
        "noncert-cuts-ab16-immediate-stop-v1",
        "noncert-cuts-ab16-independent-organic-arm-replay-v1",
        "noncert-cuts-ab16-inner-lifecycle-v1",
        "noncert-cuts-ab16-inner-lifecycle-v2",
        "noncert-cuts-ab16-launch-environment-v1",
        "noncert-cuts-ab16-manager-epoch-observation-v1",
        "noncert-cuts-ab16-organic-arm-consumption-v2",
        "noncert-cuts-ab16-organic-arm-selection-v1",
        "noncert-cuts-ab16-organic-manifest-v1",
        "noncert-cuts-ab16-organic-manifest-v2",
        "noncert-cuts-ab16-organic-pre-run-authority-v1",
        "noncert-cuts-ab16-organic-pre-run-authority-v2",
        "noncert-cuts-ab16-outer-guardian-lock-close-v1",
        "noncert-cuts-ab16-path-preregistration-v1",
        "noncert-cuts-ab16-preterminal-resource-v1",
        "noncert-cuts-ab16-preterminal-resource-v2",
        "noncert-cuts-ab16-release-token-v1",
        "noncert-cuts-ab16-release-token-v2",
        "noncert-cuts-ab16-resource-calibration-fd-loader-v1",
        "noncert-cuts-ab16-resource-execution-surface-v2",
        "noncert-cuts-ab16-resource-profile-set-v1",
        "noncert-cuts-ab16-resource-verification-v1",
        "noncert-cuts-ab16-selected-byte-launch-v1",
        "noncert-cuts-ab16-stage-resource-admission-v1",
        "noncert-cuts-ab16-suite-selection-v1",
        "noncert-cuts-ab16-suite-selection-v2",
        "noncert-cuts-ab16-terminal-classification-v1",
        "noncert-cuts-ab16-terminal-classification-v2",
        "noncert-cuts-ab16-terminal-envelope-v1",
        "noncert-cuts-ab16-terminal-envelope-v2",
        "noncert-cuts-ab16-unit-reference-acquisition-v1",
        "noncert-cuts-ab16-unit-reference-release-v1",
    }
)

COHORT_METADATA_LITERAL_ALLOWLIST: Final = frozenset(
    {
        COHORT_DOCUMENT_SCHEMA,
        HISTORICAL_COHORT_ID,
        PROSPECTIVE_COHORT_ID,
    }
)

# Every artifact or proof record with an independent discriminator is explicit.
# Unchanged schemas remain entries; a missing entry cannot be treated as an
# unversioned package helper.
PROSPECTIVE_SCHEMAS: Final = MappingProxyType(
    {
        "resource_profile_set": "noncert-cuts-ab16-resource-profile-set-v2",
        "stage_resource_admission": "noncert-cuts-ab16-stage-resource-admission-v3",
        "same_uid_process_baseline": (
            "noncert-cuts-ab16-same-uid-process-baseline-v1"
        ),
        "resource_budget_profile": "noncert-cuts-ab16-resource-budget-profile-v1",
        "resource_execution_surface": "noncert-cuts-ab16-resource-execution-surface-v3",
        "calibration_declaration": "noncert-cuts-ab16-resource-calibration-declaration-v1",
        "calibration_sample": "noncert-cuts-ab16-resource-calibration-sample-v1",
        "calibration_validation": "noncert-cuts-ab16-resource-calibration-validation-v1",
        "calibration_aggregate": "noncert-cuts-ab16-resource-calibration-aggregate-v1",
        "calibration_profile_candidate": (
            "noncert-cuts-ab16-resource-calibration-profile-candidate-v1"
        ),
        "calibration_outside_replay": "noncert-cuts-ab16-resource-calibration-outside-replay-v1",
        "calibration_authorization_bundle": (
            "noncert-cuts-ab16-resource-calibration-authorization-bundle-v1"
        ),
        "calibration_authorization_bundle_set": (
            "noncert-cuts-ab16-resource-calibration-authorization-bundle-set-v1"
        ),
        "calibration_observer_protocol": "noncert-cuts-ab16-calibration-observer-protocol-v1",
        "calibration_observer_result": (
            "noncert-cuts-ab16-resource-calibration-observer-result-v1"
        ),
        "calibration_harness_result": "noncert-cuts-ab16-calibration-observer-result-v1",
        "calibration_package": "noncert-cuts-ab16-resource-calibration-package-v2",
        "calibration_fd_loader": "noncert-cuts-ab16-resource-calibration-fd-loader-v2",
        "calibration_root_receipt": (
            "noncert-cuts-ab16-resource-calibration-root-receipt-v1"
        ),
        "calibration_bundle_set_receipt": (
            "noncert-cuts-ab16-resource-calibration-bundle-set-receipt-v1"
        ),
        "calibration_stage_terminal": (
            "noncert-cuts-ab16-resource-calibration-stage-terminal-v1"
        ),
        "calibration_workload_result": (
            "noncert-cuts-ab16-resource-calibration-workload-result-v1"
        ),
        "calibration_gate_b_fixture": (
            "noncert-cuts-ab16-resource-calibration-gate-b-fixture-v1"
        ),
        "calibration_formal_fixture": (
            "noncert-cuts-ab16-resource-calibration-formal-fixture-v1"
        ),
        "calibration_exact_formal_fixture": (
            "noncert-cuts-ab16-resource-calibration-formal-fixture-v2"
        ),
        "calibration_prelaunch_admission": (
            "noncert-cuts-ab16-calibration-prelaunch-resource-admission-v2"
        ),
        "calibration_controller_plan": (
            "noncert-cuts-ab16-resource-calibration-controller-plan-v1"
        ),
        "calibration_controller_terminal": (
            "noncert-cuts-ab16-resource-calibration-controller-terminal-v1"
        ),
        "calibration_controller_inspection": (
            "noncert-cuts-ab16-resource-calibration-controller-inspection-v1"
        ),
        "calibration_acceptance_terminal": (
            "noncert-cuts-ab16-resource-calibration-acceptance-terminal-v1"
        ),
        "calibration_cohort_incomplete": (
            "noncert-cuts-ab16-resource-calibration-cohort-incomplete-v1"
        ),
        "gate_a_receipt": "noncert-cuts-ab16-bootstrap-gate-a-receipt-v3",
        "gate_a_candidate": "noncert-cuts-ab16-bootstrap-offline-candidate-v4",
        "gate_a_full_preflight": "noncert-cuts-ab16-gate-a-full-preflight-receipt-v7",
        "gate_a_publication_commit": "noncert-cuts-ab16-gate-a-preflight-publication-commit-v2",
        "gate_b_qualification": "noncert-cuts-ab16-gate-b-qualification-v3",
        "gate_b_resource_gate": "noncert-cuts-ab16-gate-b-resource-gate-v3",
        "gate_b_owner_request": "noncert-cuts-ab16-gate-b-owner-request-v2",
        "gate_b_owner_response": "noncert-cuts-ab16-gate-b-owner-response-v2",
        "gate_b_owner_release": "noncert-cuts-ab16-gate-b-owner-release-v2",
        "gate_b_epoch_observation": "noncert-cuts-ab16-gate-b-epoch-observation-v5",
        "gate_b_approval": "noncert-cuts-ab16-bootstrap-gate-b-approval-v7",
        "gate_b_handoff_request": "noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v2",
        "gate_b_handoff_response": "noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v2",
        "terminal_history_freeze": "noncert-cuts-ab16-terminal-reference-history-freeze-v1",
        "terminal_history_replay": "noncert-cuts-ab16-terminal-reference-history-replay-v2",
        "bootstrap_manager_capture": "noncert-cuts-ab16-bootstrap-manager-epoch-capture-v3",
        "bootstrap_result": "noncert-cuts-ab16-campaign-bootstrap-result-v6",
        "repository_snapshot": "noncert-cuts-ab16-repository-snapshot-v1",
        "repository_snapshot_materialization": (
            "noncert-cuts-ab16-repository-snapshot-materialization-v1"
        ),
        "external_platform_assumptions": "noncert-cuts-ab16-external-platform-assumptions-v3",
        "path_preregistration": "noncert-cuts-ab16-path-preregistration-v5",
        "bootstrap_budget_contract": "noncert-cuts-ab16-bootstrap-budget-contract-v1",
        "bootstrap_budget_terminal": "noncert-cuts-ab16-bootstrap-budget-terminal-v1",
        "bootstrap_retained_directory_handoff": (
            "noncert-cuts-ab16-bootstrap-retained-directory-handoff-v1"
        ),
        "bootstrap_staging_handoff": (
            "noncert-cuts-ab16-bootstrap-staging-handoff-v1"
        ),
        "bootstrap_budget_account_handoff": (
            "noncert-cuts-ab16-bootstrap-budget-account-handoff-v1"
        ),
        "bootstrap_structural_handoff": (
            "noncert-cuts-ab16-bootstrap-structural-handoff-v1"
        ),
        "bootstrap_package_failure_closeout": (
            "noncert-cuts-ab16-bootstrap-package-failure-closeout-v1"
        ),
        "bootstrap_broker_runtime": "noncert-cuts-ab16-bootstrap-broker-runtime-v2",
        "budget_contract": "noncert-cuts-ab16-budget-contract-v1",
        "budget_root_closure": "noncert-cuts-ab16-budget-root-closure-v1",
        "budget_published_artifact": "noncert-cuts-ab16-budget-published-artifact-v1",
        "budget_retained_staging": "noncert-cuts-ab16-budget-retained-staging-v1",
        "budget_retained_directory": "noncert-cuts-ab16-budget-retained-directory-v1",
        "budget_ownership_handoff": "noncert-cuts-ab16-budget-ownership-handoff-v1",
        "budget_broker_request": "noncert-cuts-ab16-budget-broker-request-v1",
        "budget_broker_response": "noncert-cuts-ab16-budget-broker-response-v1",
        "budget_broker_actor": "noncert-cuts-ab16-budget-broker-actor-v1",
        "budget_broker_authentication": (
            "noncert-cuts-ab16-budget-broker-authentication-v1"
        ),
        "budget_broker_endpoint": "noncert-cuts-ab16-budget-broker-endpoint-v1",
        "budget_broker_prepared_extent": "noncert-cuts-ab16-budget-prepared-extent-v1",
        "budget_broker_root_inventory": "noncert-cuts-ab16-formal-root-inventory-v1",
        "budget_broker_manager_openfile_authentication": (
            "noncert-cuts-ab16-budget-broker-manager-openfile-authentication-v1"
        ),
        "budget_broker_manager_openfile_grant": (
            "noncert-cuts-ab16-budget-broker-manager-openfile-grant-v1"
        ),
        "manager_openfile_selection_binding_schema": (
            "noncert-cuts-ab16-budget-broker-manager-openfile-selection-binding-v1"
        ),
        "budget_broker_manager_openfile_arm_authentication": (
            "noncert-cuts-ab16-budget-broker-manager-openfile-arm-authentication-v1"
        ),
        "budget_broker_manager_openfile_arm_grant": (
            "noncert-cuts-ab16-budget-broker-manager-openfile-arm-grant-v1"
        ),
        "budget_broker_session_grant": (
            "noncert-cuts-ab16-budget-broker-session-grant-v1"
        ),
        "budget_broker_transfer_ack": "noncert-cuts-ab16-budget-broker-transfer-ack-v1",
        "budget_broker_abandoned_reservation": (
            "noncert-cuts-ab16-abandoned-reservation-v1"
        ),
        "budget_broker_detached_transfer_incomplete": (
            "noncert-cuts-ab16-detached-transfer-incomplete-v1"
        ),
        "formal_root_budget_handoff": "noncert-cuts-ab16-formal-root-budget-handoff-v2",
        "formal_root_budget_contract": "noncert-cuts-ab16-formal-root-budget-contract-v1",
        "formal_root_budget_journal": "noncert-cuts-ab16-budget-broker-journal-event-v1",
        "formal_root_budget_terminal": "noncert-cuts-ab16-formal-root-budget-terminal-v2",
        "outside_final_release_capability": (
            "noncert-cuts-ab16-outside-final-release-capability-v1"
        ),
        "outside_final_release_adopted_handoff": (
            "noncert-cuts-ab16-outside-final-release-adopted-handoff-v1"
        ),
        "formal_launch_owner_broker_handoff_schema": (
            "noncert-cuts-ab16-formal-launch-owner-broker-handoff-v1"
        ),
        "formal_launch_owner_claim_authentication": (
            "noncert-cuts-ab16-formal-launch-owner-claim-authentication-v1"
        ),
        "formal_launch_owner_claim_identity": (
            "noncert-cuts-ab16-formal-launch-owner-claim-identity-v1"
        ),
        "formal_supervisor_session": (
            "noncert-cuts-ab16-formal-supervisor-session-v1"
        ),
        "formal_closeout_owner_broker_handoff_schema": (
            "noncert-cuts-ab16-formal-closeout-owner-broker-handoff-v1"
        ),
        "formal_root_outside_replay_primary": (
            "noncert-cuts-ab16-formal-root-outside-replay-primary-v1"
        ),
        "formal_root_outside_replay_alternate": (
            "noncert-cuts-ab16-formal-root-outside-replay-alternate-v1"
        ),
        "formal_root_replay_receipt": (
            "noncert-cuts-ab16-formal-root-replay-receipt-v1"
        ),
        "final_terminal_predecessor_join": (
            "noncert-cuts-ab16-final-terminal-predecessor-join-v1"
        ),
        "arm_budget_allocation": "noncert-cuts-ab16-arm-budget-allocation-v1",
        "arm_budget_reconcile": "noncert-cuts-ab16-arm-budget-reconcile-v1",
        "arm_budget_terminal": "noncert-cuts-ab16-arm-budget-terminal-v1",
        "arm_seal_response_accepted": (
            "noncert-cuts-ab16-prior-arm-seal-response-accepted-v1"
        ),
        "package_independent_replay": "noncert-cuts-ab16-campaign-package-independent-replay-v2",
        "package_writer_inventory": (
            "noncert-cuts-ab16-package-writer-inventory-v1"
        ),
        "formal_launch_context": "noncert-cuts-ab16-formal-launch-context-v6",
        "formal_owner_request": "noncert-cuts-ab16-formal-launch-owner-request-v2",
        "formal_owner_response": "noncert-cuts-ab16-formal-launch-owner-response-v2",
        "formal_admission": "noncert-cuts-ab16-formal-launch-admission-v3",
        "formal_guardian_ready": "noncert-cuts-ab16-formal-guardian-ready-v2",
        "formal_attempt_consumption": "noncert-cuts-ab16-formal-attempt-consumption-v2",
        "formal_selection": "noncert-cuts-ab16-formal-launch-selection-v3",
        "formal_manager_openfile_grant": (
            "noncert-cuts-ab16-formal-manager-openfile-grant-v1"
        ),
        "formal_package_selected_fd_transport": (
            "noncert-cuts-ab16-package-selected-fd-transport-v1"
        ),
        "formal_worker_session": "noncert-cuts-ab16-formal-worker-session-v1",
        "formal_loader_context": "noncert-cuts-ab16-formal-loader-context-v1",
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
        "supervisor_module_origin": (
            "noncert-cuts-ab16-organic-supervisor-module-origin-receipt-v1"
        ),
        "lifecycle_inner": "noncert-cuts-ab16-inner-lifecycle-v3",
        "lifecycle_preterminal": "noncert-cuts-ab16-preterminal-resource-v3",
        "lifecycle_release": "noncert-cuts-ab16-release-token-v3",
        "lifecycle_terminal": "noncert-cuts-ab16-terminal-envelope-v3",
        "lifecycle_cleanup": "noncert-cuts-ab16-cleanup-v3",
        "reference_acquisition": "noncert-cuts-ab16-unit-reference-acquisition-v2",
        "reference_release": "noncert-cuts-ab16-unit-reference-release-v2",
        "reference_manager_epoch": "noncert-cuts-ab16-manager-epoch-observation-v2",
        "reference_capability_transcript": (
            "noncert-cuts-ab16-reference-capability-transcript-v1"
        ),
        "reference_lifecycle": "noncert-cuts-ab16-formal-reference-lifecycle-v1",
        "detached_resource_terminal": "noncert-cuts-ab16-detached-resource-terminal-v3",
        "independent_resource_terminal_replay": (
            "noncert-cuts-ab16-independent-resource-terminal-replay-v1"
        ),
        "arm_cut_free_replay": "noncert-cuts-ab16-organic-cut-free-incumbent-replay-v1",
        "fixed_baseline_replay": "noncert-cuts-ab16-fixed-assignment-replay-v2",
        "arm_arithmetic_replay": "noncert-cuts-ab16-independent-organic-arm-replay-v2",
        "applied_assignment": "noncert-cuts-ab16-applied-assignment-v1",
        "concrete_inequality_corpus": "noncert-cuts-ab16-concrete-inequality-corpus-v1",
        "compile_attach_journal": "noncert-cuts-ab16-compile-attach-journal-v1",
        "budget_segment_bundle": "noncert-cuts-ab16-budget-segment-bundle-v1",
        "baseline_rebuild": "noncert-cuts-ab16-baseline-rebuild-v1",
        "rebuilt_model_metadata": "noncert-cuts-ab16-rebuilt-model-metadata-v2",
        "campaign_snapshot_provenance": (
            "noncert-cuts-ab16-campaign-snapshot-provenance-v1"
        ),
        "controller_terminal": "noncert-cuts-ab16-controller-terminal-v1",
        "resource_verification": "noncert-cuts-ab16-resource-verification-v2",
        "sealed_execution_source": "noncert-cuts-ab16-sealed-execution-source-v1",
        "selected_byte_launch": "noncert-cuts-ab16-selected-byte-launch-v2",
        "launch_environment": "noncert-cuts-ab16-launch-environment-v2",
        "formal_arm_budget_handoff": "noncert-cuts-ab16-formal-arm-budget-handoff-v2",
        "abort_cleanup": "noncert-cuts-ab16-abort-cleanup-v2",
        "abort_reference_release": "noncert-cuts-ab16-abort-reference-release-v1",
        "module_origin": "noncert-cuts-ab16-module-origin-receipt-v1",
        "experiment_contract": "noncert-cuts-ab16-experiment-contract-v1",
        "consumption_state": "noncert-cuts-ab16-consumption-state-v1",
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
        "reference_post_unref_absence": (
            "noncert-cuts-ab16-unit-reference-post-unref-absence-v1"
        ),
        "reference_terminal": "noncert-cuts-ab16-unit-reference-terminal-v1",
        "reference_connection_close": "noncert-cuts-ab16-unit-reference-connection-close-v1",
        "formal_child_audit": "noncert-cuts-ab16-formal-child-audit-v1",
        "formal_gate1_prelaunch_ownership": (
            "noncert-cuts-ab16-formal-gate1-prelaunch-ownership-v1"
        ),
        "formal_outer_barrier": "noncert-cuts-ab16-outer-barrier-release-v1",
        "formal_guardian_lock_handoff": (
            "noncert-cuts-ab16-outer-guardian-lock-handoff-v1"
        ),
        "formal_guardian_selection_activation": (
            "noncert-cuts-ab16-outer-guardian-selection-activation-v1"
        ),
        "formal_guardian_ledger_update": (
            "noncert-cuts-ab16-outer-guardian-ledger-update-v1"
        ),
        "formal_guardian_preselection_cancel": (
            "noncert-cuts-ab16-outer-guardian-preselection-cancel-v1"
        ),
        "formal_guardian_preselection_ack": (
            "noncert-cuts-ab16-outer-guardian-preselection-ack-v1"
        ),
        "formal_guardian_terminal_command": (
            "noncert-cuts-ab16-outer-guardian-terminal-command-v1"
        ),
        "formal_supervisor_death": "noncert-cuts-ab16-supervisor-death-v1",
        "recovery_disarm_intent": "noncert-cuts-ab16-recovery-disarm-intent-v1",
        "recovery_disarm_terminal": "noncert-cuts-ab16-recovery-disarm-terminal-v1",
        "recovery_request": "noncert-cuts-ab16-recovery-request-v1",
        "recovery_response": "noncert-cuts-ab16-recovery-response-v1",
        "recovery_actor": "noncert-cuts-ab16-recovery-actor-v1",
        "recovery_disarm_observation": (
            "noncert-cuts-ab16-recovery-disarm-observation-v1"
        ),
        "recovery_lock_consumption": "noncert-cuts-ab16-recovery-lock-consumption-v1",
        "recovery_owner_handoff": "noncert-cuts-ab16-recovery-owner-handoff-v1",
        "recovery_owner_observation": "noncert-cuts-ab16-recovery-owner-observation-v2",
        "recovery_prepared": "noncert-cuts-ab16-prepared-recovery-v2",
        "recovery_unused_closeout": "noncert-cuts-ab16-recovery-unused-closeout-v1",
        "recovery_takeover_consumed_incomplete": (
            "noncert-cuts-ab16-recovery-takeover-consumed-incomplete-v1"
        ),
        "closure_actor_ready": "noncert-cuts-ab16-closure-actor-ready-v1",
        "closure_request": "noncert-cuts-ab16-closure-request-v1",
        "closure_response": "noncert-cuts-ab16-closure-response-v1",
        "closure_actor": "noncert-cuts-ab16-closure-actor-v1",
        "closure_lock_consumption": "noncert-cuts-ab16-closure-lock-consumption-v1",
        "closure_owner_handoff": "noncert-cuts-ab16-closure-owner-handoff-v1",
        "closure_control_transfer": "noncert-cuts-ab16-closure-control-transfer-v1",
        "closure_formal_manifest": "noncert-cuts-ab16-formal-manifest-v2",
        "closure_result": "noncert-cuts-ab16-closure-result-v2",
        "final_release_actor_ready": "noncert-cuts-ab16-final-release-actor-ready-v1",
        "final_release_request": "noncert-cuts-ab16-final-release-request-v1",
        "final_release_response": "noncert-cuts-ab16-final-release-response-v1",
        "final_release_actor": "noncert-cuts-ab16-final-release-actor-v1",
        "final_release_owner_handoff": (
            "noncert-cuts-ab16-final-release-owner-handoff-v1"
        ),
        "post_root_closure_evidence": (
            "noncert-cuts-ab16-post-root-closure-evidence-v1"
        ),
        "final_release_result": "noncert-cuts-ab16-final-release-result-v1",
        "formal_containment": "noncert-cuts-ab16-formal-containment-v2",
        "success_pre_release": "noncert-cuts-ab16-formal-pre-release-success-v3",
        "success_guardian_lock_close": "noncert-cuts-ab16-outer-guardian-lock-close-v2",
        "success_guardian_absence": "noncert-cuts-ab16-formal-guardian-absence-v2",
        "success_dual_lock_release": "noncert-cuts-ab16-formal-dual-lock-release-v4",
        "formal_supervisor_raw_lock_release": (
            "noncert-cuts-ab16-formal-supervisor-raw-lock-release-v1"
        ),
        "formal_markerless_incomplete": "noncert-cuts-ab16-formal-markerless-incomplete-v2",
        "formal_consumed_incomplete": "noncert-cuts-ab16-formal-consumed-incomplete-v3",
        "incomplete_pre_release": "noncert-cuts-ab16-formal-pre-release-failure-v4",
        "incomplete_detached": "noncert-cuts-ab16-formal-detached-incomplete-v4",
        "incomplete_terminal_release": "noncert-cuts-ab16-formal-failure-terminal-release-v5",
        "pytest_collection_binding": "noncert-cuts-ab16-pytest-collection-binding-v1",
        "gate_a_recovery_inputs": "noncert-cuts-ab16-gate-a-recovery-inputs-v1",
        "native_budget_helper": "noncert-cuts-ab16-native-budget-helper-v1",
        "drill_authority": "noncert-cuts-ab16-disposable-drill-authority-v2",
        "drill_authority_result": "noncert-cuts-ab16-disposable-drill-authority-result-v2",
        "drill_control": "noncert-cuts-ab16-disposable-drill-control-v2",
        "drill_package_manifest": (
            "noncert-cuts-ab16-disposable-drill-package-manifest-v2"
        ),
        "drill_root": "noncert-cuts-ab16-disposable-drill-root-v2",
        "drill_source_snapshot": "noncert-cuts-ab16-disposable-source-snapshot-v1",
        "drill_source_snapshot_materialization": (
            "noncert-cuts-ab16-disposable-source-snapshot-materialization-v1"
        ),
        "drill_selection": "noncert-cuts-ab16-organic-drill-selection-v1",
        "drill_result": "noncert-cuts-ab16-organic-arm-result-v1",
        "reference_capability": "noncert-cuts-ab16-reference-capability-v1",
    }
)

PROSPECTIVE_SCHEMA_PRODUCERS: Final = MappingProxyType(
    {
        'resource_profile_set': ('tool.ab16_resource_admission_v1.py', 'PROSPECTIVE_PROFILE_SET_ID'),
        'stage_resource_admission': ('tool.ab16_resource_admission_v1.py', 'PROSPECTIVE_RESOURCE_ADMISSION_SCHEMA'),
        'same_uid_process_baseline': ('tool.ab16_resource_admission_v1.py', 'SAME_UID_PROCESS_BASELINE_SCHEMA'),
        'resource_budget_profile': ('tool.ab16_campaign_bootstrap_v2.py', 'RESOURCE_BUDGET_PROFILE_SCHEMA'),
        'resource_execution_surface': ('tool.ab16_resource_calibration_v1.py', 'EXECUTION_SURFACE_SCHEMA'),
        'calibration_declaration': ('tool.ab16_resource_calibration_v1.py', 'DECLARATION_SCHEMA'),
        'calibration_sample': ('tool.ab16_resource_calibration_v1.py', 'SAMPLE_SCHEMA'),
        'calibration_validation': ('tool.ab16_resource_calibration_v1.py', 'VALIDATION_SCHEMA'),
        'calibration_aggregate': ('tool.ab16_resource_calibration_v1.py', 'AGGREGATE_SCHEMA'),
        'calibration_profile_candidate': ('tool.ab16_resource_calibration_v1.py', 'PROFILE_CANDIDATE_SCHEMA'),
        'calibration_outside_replay': ('tool.ab16_resource_admission_v1.py', 'CALIBRATION_OUTSIDE_REPLAY_SCHEMA'),
        'calibration_authorization_bundle': ('tool.ab16_resource_admission_v1.py', 'CALIBRATION_AUTHORIZATION_BUNDLE_SCHEMA'),
        'calibration_authorization_bundle_set': ('tool.ab16_resource_calibration_v1.py', 'BUNDLE_SET_SCHEMA'),
        'calibration_observer_protocol': ('tool.ab16_resource_calibration_harness_v1.py', 'PROTOCOL_SCHEMA'),
        'calibration_observer_result': ('tool.ab16_resource_calibration_v1.py', 'OBSERVER_RESULT_SCHEMA'),
        'calibration_harness_result': ('tool.ab16_resource_calibration_harness_v1.py', 'RESULT_SCHEMA'),
        'calibration_package': ('tool.ab16_resource_calibration_package_v1.py', 'PACKAGE_SCHEMA'),
        'calibration_fd_loader': ('tool.ab16_resource_calibration_fd_loader_v1.py', 'LOADER_SCHEMA'),
        'calibration_root_receipt': ('tool.ab16_resource_calibration_runner_v1.py', 'RECEIPT_SCHEMA'),
        'calibration_bundle_set_receipt': ('tool.ab16_resource_calibration_runner_v1.py', 'BUNDLE_SET_RECEIPT_SCHEMA'),
        'calibration_stage_terminal': ('tool.ab16_resource_calibration_runner_v1.py', 'STAGE_TERMINAL_SCHEMA'),
        'calibration_workload_result': ('tool.ab16_resource_calibration_workloads_v1.py', 'RESULT_SCHEMA'),
        'calibration_gate_b_fixture': ('tool.ab16_resource_calibration_workloads_v1.py', 'GATE_B_FIXTURE_SCHEMA'),
        'calibration_formal_fixture': ('tool.ab16_resource_calibration_workloads_v1.py', 'FORMAL_FIXTURE_SCHEMA'),
        'calibration_exact_formal_fixture': ('tool.ab16_resource_calibration_workloads_v1.py', 'EXACT_FORMAL_FIXTURE_SCHEMA'),
        'calibration_prelaunch_admission': ('tool.ab16_resource_admission_v1.py', 'CALIBRATION_PRELAUNCH_RESOURCE_ADMISSION_SCHEMA'),
        'calibration_controller_plan': ('tool.ab16_resource_calibration_runner_v1.py', 'CONTROLLER_PLAN_SCHEMA'),
        'calibration_controller_terminal': ('tool.ab16_resource_calibration_runner_v1.py', 'CONTROLLER_TERMINAL_SCHEMA'),
        'calibration_controller_inspection': ('tool.ab16_resource_calibration_runner_v1.py', 'CONTROLLER_INSPECTION_SCHEMA'),
        'calibration_acceptance_terminal': ('tool.ab16_resource_calibration_runner_v1.py', 'ACCEPTANCE_TERMINAL_SCHEMA'),
        'calibration_cohort_incomplete': ('tool.ab16_resource_calibration_runner_v1.py', 'COHORT_INCOMPLETE_SCHEMA'),
        'gate_a_receipt': ('tool.ab16_authority_v2.py', 'GATE_A_SCHEMA'),
        'gate_a_candidate': ('tool.ab16_campaign_bootstrap_v2.py', 'CANDIDATE_SCHEMA'),
        'gate_a_full_preflight': ('tool.ab16_authority_v2.py', 'FINAL_FULL_PREFLIGHT_SCHEMA'),
        'gate_a_publication_commit': ('tool.ab16_authority_v2.py', 'FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA'),
        'gate_b_qualification': ('tool.ab16_gate_b_qualification_v1.py', 'QUALIFICATION_SCHEMA'),
        'gate_b_resource_gate': ('tool.ab16_authority_v2.py', 'GATE_B_RESOURCE_GATE_SCHEMA'),
        'gate_b_owner_request': ('tool.ab16_gate_b_qualification_v1.py', 'OWNER_REQUEST_SCHEMA'),
        'gate_b_owner_response': ('tool.ab16_gate_b_qualification_v1.py', 'OWNER_RESPONSE_SCHEMA'),
        'gate_b_owner_release': ('tool.ab16_gate_b_qualification_v1.py', 'OWNER_RELEASE_SCHEMA'),
        'gate_b_epoch_observation': ('tool.ab16_authority_v2.py', 'GATE_B_EPOCH_SCHEMA'),
        'gate_b_approval': ('tool.ab16_authority_v2.py', 'GATE_B_SCHEMA'),
        'gate_b_handoff_request': ('tool.ab16_campaign_bootstrap_v2.py', 'GATE_B_HANDOFF_REQUEST_SCHEMA'),
        'gate_b_handoff_response': ('tool.ab16_campaign_bootstrap_v2.py', 'GATE_B_HANDOFF_RESPONSE_SCHEMA'),
        'terminal_history_freeze': ('tool.disposable_drill_authority_v2.py', 'HISTORY_FREEZE_SCHEMA'),
        'terminal_history_replay': ('tool.disposable_drill_authority_v2.py', 'HISTORY_REPLAY_SCHEMA'),
        'bootstrap_manager_capture': ('tool.ab16_campaign_bootstrap_v2.py', 'CAPTURE_SCHEMA'),
        'bootstrap_result': ('tool.ab16_campaign_bootstrap_v2.py', 'RESULT_SCHEMA'),
        'repository_snapshot': ('tool.ab16_authority_v2.py', 'REPOSITORY_SNAPSHOT_SCHEMA'),
        'repository_snapshot_materialization': ('tool.ab16_authority_v2.py', 'SNAPSHOT_MATERIALIZATION_SCHEMA'),
        'external_platform_assumptions': ('tool.ab16_authority_v2.py', 'EXTERNAL_PLATFORM_SCHEMA'),
        'path_preregistration': ('tool.ab16_authority_v2.py', 'PATH_PREREGISTRATION_SCHEMA'),
        'bootstrap_budget_contract': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_BUDGET_CONTRACT_SCHEMA'),
        'bootstrap_budget_terminal': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_BUDGET_TERMINAL_SCHEMA'),
        'bootstrap_retained_directory_handoff': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_RETAINED_DIRECTORY_HANDOFF_SCHEMA'),
        'bootstrap_staging_handoff': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_STAGING_HANDOFF_SCHEMA'),
        'bootstrap_budget_account_handoff': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_BUDGET_ACCOUNT_HANDOFF_SCHEMA'),
        'bootstrap_structural_handoff': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA'),
        'bootstrap_package_failure_closeout': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_PACKAGE_FAILURE_CLOSEOUT_SCHEMA'),
        'bootstrap_broker_runtime': ('tool.ab16_campaign_bootstrap_v2.py', 'BOOTSTRAP_BROKER_RUNTIME_SCHEMA'),
        'budget_contract': ('tool.ab16_budget_authority_v1.py', 'BUDGET_CONTRACT_SCHEMA'),
        'budget_root_closure': ('tool.ab16_budget_authority_v1.py', 'BUDGET_CLOSURE_SCHEMA'),
        'budget_published_artifact': ('tool.ab16_budget_authority_v1.py', 'PUBLISHED_ARTIFACT_SCHEMA'),
        'budget_retained_staging': ('tool.ab16_budget_authority_v1.py', 'BUDGET_RETAINED_STAGING_SCHEMA'),
        'budget_retained_directory': ('tool.ab16_budget_authority_v1.py', 'BUDGET_RETAINED_DIRECTORY_SCHEMA'),
        'budget_ownership_handoff': ('tool.ab16_budget_authority_v1.py', 'BUDGET_OWNERSHIP_HANDOFF_SCHEMA'),
        'budget_broker_request': ('tool.ab16_budget_broker_v1.py', 'REQUEST_SCHEMA'),
        'budget_broker_response': ('tool.ab16_budget_broker_v1.py', 'RESPONSE_SCHEMA'),
        'budget_broker_actor': ('tool.ab16_budget_broker_v1.py', 'ACTOR_SCHEMA'),
        'budget_broker_authentication': ('tool.ab16_budget_broker_v1.py', 'AUTHENTICATION_SCHEMA'),
        'budget_broker_endpoint': ('tool.ab16_budget_broker_v1.py', 'ENDPOINT_SCHEMA'),
        'budget_broker_prepared_extent': ('tool.ab16_budget_broker_v1.py', 'PREPARED_EXTENT_SCHEMA'),
        'budget_broker_root_inventory': ('tool.ab16_arm_attempt_closure_v1.py', 'ROOT_INVENTORY_SCHEMA'),
        'budget_broker_manager_openfile_authentication': ('tool.ab16_budget_broker_v1.py', 'MANAGER_OPENFILE_AUTHENTICATION_SCHEMA'),
        'budget_broker_manager_openfile_grant': ('tool.ab16_budget_broker_v1.py', 'MANAGER_OPENFILE_GRANT_SCHEMA'),
        'manager_openfile_selection_binding_schema': ('tool.ab16_budget_broker_v1.py', 'MANAGER_OPENFILE_SELECTION_BINDING_SCHEMA'),
        'budget_broker_manager_openfile_arm_authentication': ('tool.ab16_budget_broker_v1.py', 'MANAGER_OPENFILE_ARM_AUTHENTICATION_SCHEMA'),
        'budget_broker_manager_openfile_arm_grant': ('tool.ab16_budget_broker_v1.py', 'MANAGER_OPENFILE_ARM_GRANT_SCHEMA'),
        'budget_broker_session_grant': ('tool.ab16_budget_broker_v1.py', 'SESSION_GRANT_SCHEMA'),
        'budget_broker_transfer_ack': ('tool.ab16_budget_broker_v1.py', 'TRANSFER_ACK_SCHEMA'),
        'budget_broker_abandoned_reservation': ('tool.ab16_budget_broker_v1.py', 'ABANDONED_RESERVATION_SCHEMA'),
        'budget_broker_detached_transfer_incomplete': ('tool.ab16_budget_broker_v1.py', 'DETACHED_TRANSFER_INCOMPLETE_SCHEMA'),
        'formal_root_budget_handoff': ('tool.ab16_budget_broker_v1.py', 'BOOTSTRAP_HANDOFF_SCHEMA'),
        'formal_root_budget_contract': ('tool.ab16_campaign_bootstrap_v2.py', 'FORMAL_ROOT_BUDGET_CONTRACT_SCHEMA'),
        'formal_root_budget_journal': ('tool.ab16_budget_broker_v1.py', 'JOURNAL_SCHEMA'),
        'formal_root_budget_terminal': ('tool.ab16_closure_actor_v1.py', 'BUDGET_TERMINAL_SCHEMA'),
        'outside_final_release_capability': ('tool.ab16_budget_broker_v1.py', 'OUTSIDE_FINAL_RELEASE_CAPABILITY_SCHEMA'),
        'outside_final_release_adopted_handoff': ('tool.ab16_budget_broker_v1.py', 'FINAL_RELEASE_PARENT_HANDOFF_SCHEMA'),
        'formal_launch_owner_broker_handoff_schema': ('tool.ab16_budget_broker_v1.py', 'FORMAL_LAUNCH_OWNER_HANDOFF_SCHEMA'),
        'formal_launch_owner_claim_authentication': ('tool.ab16_budget_broker_v1.py', 'FORMAL_LAUNCH_OWNER_CLAIM_AUTHENTICATION_SCHEMA'),
        'formal_launch_owner_claim_identity': ('tool.ab16_budget_broker_v1.py', 'FORMAL_LAUNCH_OWNER_CLAIM_IDENTITY_SCHEMA'),
        'formal_supervisor_session': ('tool.ab16_formal_orchestrator_v1.py', 'FORMAL_SUPERVISOR_SESSION_SCHEMA'),
        'formal_closeout_owner_broker_handoff_schema': ('tool.ab16_budget_broker_v1.py', 'FORMAL_CLOSEOUT_OWNER_HANDOFF_SCHEMA'),
        'formal_root_outside_replay_primary': ('tool.replay_ab16_formal_root_v1.py', 'REPLAY_SCHEMA'),
        'formal_root_outside_replay_alternate': ('tool.replay_ab16_formal_root_alt_v1.py', 'REPLAY_SCHEMA'),
        'formal_root_replay_receipt': ('tool.ab16_final_release_actor_v1.py', 'REPLAY_RECEIPT_SCHEMA'),
        'final_terminal_predecessor_join': ('tool.ab16_formal_campaign_v1.py', 'FINAL_TERMINAL_PREDECESSOR_JOIN_SCHEMA'),
        'arm_budget_allocation': ('tool.ab16_budget_broker_v1.py', 'ARM_ALLOCATION_SCHEMA'),
        'arm_budget_reconcile': ('tool.ab16_arm_attempt_closure_v1.py', 'ARM_BUDGET_RECONCILE_SCHEMA'),
        'arm_budget_terminal': ('tool.ab16_arm_attempt_closure_v1.py', 'ARM_BUDGET_TERMINAL_SCHEMA'),
        'arm_seal_response_accepted': ('tool.ab16_budget_broker_v1.py', 'PRIOR_SEAL_RESPONSE_ACCEPTED_SCHEMA'),
        'package_independent_replay': ('tool.ab16_authority_v2.py', 'PACKAGE_INDEPENDENT_REPLAY_SCHEMA'),
        'package_writer_inventory': ('tool.ab16_package_writer_inventory_v1.py', 'PACKAGE_WRITER_INVENTORY_SCHEMA'),
        'formal_launch_context': ('tool.ab16_formal_launch_validator_v1.py', 'FORMAL_CONTEXT_SCHEMA'),
        'formal_owner_request': ('tool.ab16_formal_orchestrator_v1.py', 'REQUEST_SCHEMA'),
        'formal_owner_response': ('tool.ab16_formal_orchestrator_v1.py', 'RESPONSE_SCHEMA'),
        'formal_admission': ('tool.ab16_formal_launch_validator_v1.py', 'FORMAL_ADMISSION_SCHEMA'),
        'formal_guardian_ready': ('tool.ab16_formal_launch_validator_v1.py', 'GUARDIAN_READY_SCHEMA'),
        'formal_attempt_consumption': ('tool.ab16_formal_launch_validator_v1.py', 'ATTEMPT_CONSUMPTION_SCHEMA'),
        'formal_selection': ('tool.ab16_formal_launch_validator_v1.py', 'FORMAL_SELECTION_SCHEMA_V3'),
        'formal_manager_openfile_grant': ('tool.ab16_formal_launch_validator_v1.py', 'MANAGER_OPENFILE_GRANT_SCHEMA'),
        'formal_package_selected_fd_transport': ('tool.ab16_campaign_bootstrap_v2.py', 'PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA'),
        'formal_worker_session': ('tool.ab16_formal_controller_v1.py', 'FORMAL_WORKER_SESSION_SCHEMA'),
        'formal_loader_context': ('tool.ab16_formal_loader_v1.py', 'LOADER_CONTEXT_SCHEMA'),
        'formal_outer_prelaunch': ('tool.ab16_formal_success_verifier_v1.py', 'OUTER_PRELAUNCH_SCHEMA'),
        'formal_outer_start': ('tool.ab16_formal_success_verifier_v1.py', 'OUTER_START_SCHEMA'),
        'continuation_authorization': ('tool.ab16_authority_v1.py', 'CONTINUATION_SCHEMA'),
        'baseline_admission': ('tool.ab16_authority_v1.py', 'BASELINE_ADMISSION_SCHEMA'),
        'common_prestate': ('tool.ab16_authority_v1.py', 'COMMON_PRESTATE_SCHEMA'),
        'campaign_manifest': ('tool.ab16_authority_v2.py', 'MANIFEST_SCHEMA'),
        'suite_selection': ('tool.ab16_authority_v2.py', 'SUITE_SELECTION_SCHEMA'),
        'arm_binding': ('tool.ab16_authority_v2.py', 'ARM_BINDING_SCHEMA'),
        'arm_pre_run': ('tool.ab16_authority_v2.py', 'PRE_RUN_AUTHORITY_SCHEMA'),
        'arm_selection': ('tool.ab16_authority_v2.py', 'ARM_SELECTION_SCHEMA'),
        'arm_result': ('tool.ab16_terminal_gate_v3.py', 'RESULT_SCHEMA'),
        'arm_module_origin': ('tool.organic_arm_runner_v1.py', 'FORMAL_MODULE_ORIGIN_RECEIPT_SCHEMA'),
        'supervisor_module_origin': ('tool.organic_resource_lifecycle_v2.py', 'SUPERVISOR_MODULE_ORIGIN_RECEIPT_SCHEMA'),
        'lifecycle_inner': ('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_INNER_SCHEMA'),
        'lifecycle_preterminal': ('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_PRETERMINAL_SCHEMA'),
        'lifecycle_release': ('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_RELEASE_SCHEMA'),
        'lifecycle_terminal': ('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_TERMINAL_SCHEMA'),
        'lifecycle_cleanup': ('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_CLEANUP_SCHEMA'),
        'reference_acquisition': ('tool.ab16_outer_closeout_state_v1.py', 'REFERENCE_ACQUISITION_SCHEMA_V2'),
        'reference_release': ('tool.ab16_outer_closeout_state_v1.py', 'REFERENCE_RELEASE_SCHEMA_V2'),
        'reference_manager_epoch': ('tool.organic_resource_lifecycle_v2.py', 'EPOCH_OBSERVATION_SCHEMA'),
        'reference_capability_transcript': ('tool.organic_resource_verifier_v2.py', 'REFERENCE_CAPABILITY_TRANSCRIPT_SCHEMA'),
        'reference_lifecycle': ('tool.ab16_outer_closeout_state_v1.py', 'REFERENCE_SCHEMA'),
        'detached_resource_terminal': ('tool.ab16_terminal_gate_v3.py', 'RESOURCE_SCHEMA'),
        'independent_resource_terminal_replay': ('tool.organic_resource_verifier_v2.py', 'INDEPENDENT_RESOURCE_REPLAY_SCHEMA'),
        'arm_cut_free_replay': ('tool.cut_free_incumbent_replay_v1.py', 'ARM_SCHEMA'),
        'fixed_baseline_replay': ('tool.baseline_admission_v1.py', 'REPLAY_SCHEMA'),
        'arm_arithmetic_replay': ('tool.ab16_terminal_gate_v3.py', 'ARITHMETIC_SCHEMA'),
        'applied_assignment': ('tool.organic_arm_replay_v1.py', 'ASSIGNMENT_SCHEMA'),
        'concrete_inequality_corpus': ('tool.organic_arm_replay_v1.py', 'CORPUS_SCHEMA'),
        'compile_attach_journal': ('tool.organic_arm_replay_v1.py', 'JOURNAL_SCHEMA'),
        'budget_segment_bundle': ('tool.organic_arm_replay_v1.py', 'BUDGET_SEGMENT_BUNDLE_SCHEMA'),
        'baseline_rebuild': ('tool.baseline_rebuild_v1.py', 'SCHEMA'),
        'rebuilt_model_metadata': ('tool.baseline_admission_v1.py', 'METADATA_SCHEMA'),
        'campaign_snapshot_provenance': ('tool.baseline_admission_v1.py', 'CAMPAIGN_PROVENANCE_SCHEMA'),
        'controller_terminal': ('tool.ab16_terminal_gate_v1.py', 'CONTROLLER_TERMINAL_SCHEMA'),
        'resource_verification': ('tool.ab16_terminal_gate_v2.py', 'RESOURCE_PRETERMINAL_SCHEMA'),
        'sealed_execution_source': ('tool.organic_arm_runner_v1.py', 'SEALED_EXECUTION_SOURCE_SCHEMA'),
        'selected_byte_launch': ('tool.organic_arm_runner_v1.py', 'SELECTED_BYTE_LAUNCH_SCHEMA_V2'),
        'launch_environment': ('tool.organic_resource_lifecycle_v2.py', 'LAUNCH_ENVIRONMENT_SCHEMA'),
        'formal_arm_budget_handoff': ('tool.organic_resource_lifecycle_v2.py', 'FORMAL_BUDGET_HANDOFF_SCHEMA'),
        'abort_cleanup': ('tool.organic_unit_orchestrator_v2.py', 'ABORT_CLEANUP_SCHEMA'),
        'abort_reference_release': ('tool.organic_unit_orchestrator_v2.py', 'ABORT_REFERENCE_RELEASE_SCHEMA'),
        'module_origin': ('tool.organic_arm_runner_v1.py', 'MODULE_ORIGIN_RECEIPT_SCHEMA'),
        'experiment_contract': ('tool.ab16_budget_authority_v1.py', 'EXPERIMENT_CONTRACT_SCHEMA'),
        'consumption_state': ('tool.ab16_contract_v1.py', 'STATE_SCHEMA'),
        'arm_credibility': ('tool.ab16_terminal_gate_v3.py', 'ARM_GATE_SCHEMA'),
        'terminal_classification': ('tool.ab16_terminal_gate_v3.py', 'SUITE_GATE_SCHEMA'),
        'arm_attempt_manifest': ('tool.ab16_arm_attempt_closure_v1.py', 'MANIFEST_SCHEMA'),
        'arm_attempt_root_replay': ('tool.ab16_arm_attempt_closure_v1.py', 'REPLAY_SCHEMA'),
        'arm_consumption': ('tool.ab16_authority_v2.py', 'ARM_CONSUMPTION_SCHEMA'),
        'arm_allocation_unselected_terminal': ('tool.ab16_authority_v2.py', 'ARM_UNSELECTED_TERMINAL_SCHEMA'),
        'arm_consumed_incomplete': ('tool.ab16_authority_v2.py', 'ARM_CONSUMED_INCOMPLETE_SCHEMA'),
        'immediate_stop': ('tool.ab16_authority_v2.py', 'CAMPAIGN_STOP_SCHEMA'),
        'formal_arm_prelaunch': ('tool.ab16_formal_success_verifier_v1.py', 'ARM_PRELAUNCH_SCHEMA'),
        'formal_controller_result': ('tool.ab16_formal_controller_v1.py', 'CONTROLLER_RESULT_SCHEMA'),
        'reference_post_unref_absence': ('tool.ab16_outer_closeout_state_v1.py', 'REFERENCE_POST_UNREF_ABSENCE_SCHEMA'),
        'reference_terminal': ('tool.ab16_outer_closeout_state_v1.py', 'REFERENCE_TERMINAL_SCHEMA'),
        'reference_connection_close': ('tool.ab16_outer_closeout_state_v1.py', 'REFERENCE_CONNECTION_CLOSE_SCHEMA'),
        'formal_child_audit': ('tool.ab16_formal_success_verifier_v1.py', 'CHILD_AUDIT_SCHEMA'),
        'formal_gate1_prelaunch_ownership': ('tool.ab16_formal_success_verifier_v1.py', 'GATE1_OWNERSHIP_SCHEMA'),
        'formal_outer_barrier': ('tool.ab16_formal_controller_v1.py', 'OUTER_BARRIER_SCHEMA'),
        'formal_guardian_lock_handoff': ('tool.ab16_outer_guardian_v1.py', 'LOCK_HANDOFF_SCHEMA'),
        'formal_guardian_selection_activation': ('tool.ab16_outer_guardian_v1.py', 'GUARDIAN_ACTIVATION_SCHEMA'),
        'formal_guardian_ledger_update': ('tool.ab16_outer_guardian_v1.py', 'GUARDIAN_LEDGER_UPDATE_SCHEMA'),
        'formal_guardian_preselection_cancel': ('tool.ab16_outer_guardian_v1.py', 'GUARDIAN_PRESELECTION_CANCEL_SCHEMA'),
        'formal_guardian_preselection_ack': ('tool.ab16_outer_guardian_v1.py', 'GUARDIAN_PRESELECTION_ACK_SCHEMA'),
        'formal_guardian_terminal_command': ('tool.ab16_outer_guardian_v1.py', 'GUARDIAN_TERMINAL_SCHEMA'),
        'formal_supervisor_death': ('tool.ab16_outer_guardian_v1.py', 'SUPERVISOR_DEATH_SCHEMA'),
        'recovery_disarm_intent': ('tool.ab16_recovery_closeout_v1.py', 'DISARM_INTENT_SCHEMA'),
        'recovery_disarm_terminal': ('tool.ab16_closure_actor_v1.py', 'RECOVERY_TERMINAL_SCHEMA'),
        'recovery_request': ('tool.ab16_recovery_closeout_v1.py', 'REQUEST_SCHEMA'),
        'recovery_response': ('tool.ab16_recovery_closeout_v1.py', 'RESPONSE_SCHEMA'),
        'recovery_actor': ('tool.ab16_recovery_closeout_v1.py', 'ACTOR_SCHEMA'),
        'recovery_disarm_observation': ('tool.ab16_recovery_closeout_v1.py', 'DISARM_OBSERVATION_SCHEMA'),
        'recovery_lock_consumption': ('tool.ab16_recovery_closeout_v1.py', 'LOCK_CONSUMPTION_SCHEMA'),
        'recovery_owner_handoff': ('tool.ab16_recovery_closeout_v1.py', 'OWNER_HANDOFF_SCHEMA'),
        'recovery_owner_observation': ('tool.ab16_recovery_closeout_v1.py', 'OWNER_OBSERVATION_SCHEMA'),
        'recovery_prepared': ('tool.ab16_recovery_closeout_v1.py', 'PREPARED_RECOVERY_SCHEMA'),
        'recovery_unused_closeout': ('tool.ab16_recovery_closeout_v1.py', 'UNUSED_CLOSEOUT_SCHEMA'),
        'recovery_takeover_consumed_incomplete': ('tool.ab16_recovery_closeout_v1.py', 'TAKEOVER_CLOSEOUT_SCHEMA'),
        'closure_actor_ready': ('tool.ab16_closure_actor_v1.py', 'READY_SCHEMA'),
        'closure_request': ('tool.ab16_closure_actor_v1.py', 'REQUEST_SCHEMA'),
        'closure_response': ('tool.ab16_closure_actor_v1.py', 'RESPONSE_SCHEMA'),
        'closure_actor': ('tool.ab16_closure_actor_v1.py', 'ACTOR_SCHEMA'),
        'closure_lock_consumption': ('tool.ab16_closure_actor_v1.py', 'LOCK_CONSUMPTION_SCHEMA'),
        'closure_owner_handoff': ('tool.ab16_closure_actor_v1.py', 'OWNER_HANDOFF_SCHEMA'),
        'closure_control_transfer': ('tool.ab16_budget_broker_v1.py', 'CLOSURE_CONTROL_TRANSFER_SCHEMA'),
        'closure_formal_manifest': ('tool.ab16_closure_actor_v1.py', 'FORMAL_MANIFEST_SCHEMA'),
        'closure_result': ('tool.ab16_closure_actor_v1.py', 'CLOSURE_RESULT_SCHEMA'),
        'final_release_actor_ready': ('tool.ab16_final_release_actor_v1.py', 'READY_SCHEMA'),
        'final_release_request': ('tool.ab16_final_release_actor_v1.py', 'REQUEST_SCHEMA'),
        'final_release_response': ('tool.ab16_final_release_actor_v1.py', 'RESPONSE_SCHEMA'),
        'final_release_actor': ('tool.ab16_final_release_actor_v1.py', 'ACTOR_SCHEMA'),
        'final_release_owner_handoff': ('tool.ab16_final_release_actor_v1.py', 'HANDOFF_SCHEMA'),
        'post_root_closure_evidence': ('tool.ab16_final_release_actor_v1.py', 'EVIDENCE_SCHEMA'),
        'final_release_result': ('tool.ab16_final_release_actor_v1.py', 'RESULT_SCHEMA'),
        'formal_containment': ('tool.ab16_formal_success_verifier_v1.py', 'FORMAL_CONTAINMENT_SCHEMA'),
        'success_pre_release': ('tool.ab16_formal_success_verifier_v1.py', 'SUCCESS_RECEIPT_SCHEMA'),
        'success_guardian_lock_close': ('tool.ab16_formal_success_verifier_v1.py', 'GUARDIAN_LOCK_CLOSE_SCHEMA'),
        'success_guardian_absence': ('tool.ab16_formal_success_verifier_v1.py', 'GUARDIAN_ABSENCE_SCHEMA'),
        'success_dual_lock_release': ('tool.ab16_formal_success_verifier_v1.py', 'DUAL_LOCK_RELEASE_SCHEMA'),
        'formal_supervisor_raw_lock_release': ('tool.ab16_outer_closeout_state_v1.py', 'SUPERVISOR_RAW_LOCK_RELEASE_SCHEMA'),
        'formal_markerless_incomplete': ('tool.ab16_outer_closeout_state_v1.py', 'MARKERLESS_SCHEMA'),
        'formal_consumed_incomplete': ('tool.ab16_outer_closeout_state_v1.py', 'INCOMPLETE_SCHEMA'),
        'incomplete_pre_release': ('tool.ab16_formal_campaign_v1.py', 'FAILURE_RELEASE_SCHEMA'),
        'incomplete_detached': ('tool.ab16_formal_success_verifier_v1.py', 'INCOMPLETE_RECEIPT_SCHEMA'),
        'incomplete_terminal_release': ('tool.ab16_formal_campaign_v1.py', 'FAILURE_TERMINAL_RELEASE_SCHEMA'),
        'pytest_collection_binding': ('tool.ab16_pytest_collection_protocol_v1.py', 'COLLECTION_BINDING_SCHEMA'),
        'gate_a_recovery_inputs': ('tool.gate_a_recovery_inputs_v1.py', 'SCHEMA_VERSION'),
        'native_budget_helper': ('tool.ab16_native_budget_helper_v1.py', 'NATIVE_HELPER_SCHEMA'),
        'drill_authority': ('tool.disposable_drill_authority_v2.py', 'AUTHORITY_SCHEMA'),
        'drill_authority_result': ('tool.disposable_drill_authority_v2.py', 'RESULT_SCHEMA'),
        'drill_control': ('tool.disposable_drill_authority_v2.py', 'CONTROL_SCHEMA'),
        'drill_package_manifest': ('tool.disposable_drill_authority_v2.py', 'PACKAGE_SCHEMA'),
        'drill_root': ('tool.disposable_drill_authority_v2.py', 'ROOT_SCHEMA'),
        'drill_source_snapshot': ('tool.disposable_drill_authority_v2.py', 'SOURCE_SNAPSHOT_SCHEMA'),
        'drill_source_snapshot_materialization': ('tool.disposable_drill_authority_v2.py', 'SOURCE_SNAPSHOT_MATERIALIZATION_SCHEMA'),
        'drill_selection': ('tool.disposable_drill_payload_v1.py', 'SELECTION_SCHEMA'),
        'drill_result': ('tool.disposable_drill_payload_v1.py', 'RESULT_SCHEMA'),
        'reference_capability': ('tool.organic_resource_verifier_v2.py', 'REFERENCE_CAPABILITY_SCHEMA'),
    }
)

PROSPECTIVE_SCHEMA_CONSUMERS: Final = MappingProxyType(
    {
        'bootstrap_retained_directory_handoff': (
            ('tool.ab16_budget_broker_v1.py', 'BOOTSTRAP_RETAINED_DIRECTORY_HANDOFF_SCHEMA'),
        ),
        'bootstrap_staging_handoff': (
            ('tool.ab16_budget_broker_v1.py', 'BOOTSTRAP_STAGING_HANDOFF_SCHEMA'),
        ),
        'bootstrap_budget_account_handoff': (
            ('tool.ab16_budget_broker_v1.py', 'BOOTSTRAP_BUDGET_ACCOUNT_HANDOFF_SCHEMA'),
        ),
        'bootstrap_structural_handoff': (
            ('tool.ab16_budget_broker_v1.py', 'BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA'),
        ),
        'resource_budget_profile': (('tool.ab16_formal_controller_v1.py', 'RESOURCE_BUDGET_PROFILE_SCHEMA'), ('tool.ab16_resource_admission_v1.py', 'BUDGET_PROFILE_SCHEMA')),
        'resource_execution_surface': (('tool.ab16_resource_admission_v1.py', 'CALIBRATION_EXECUTION_SURFACE_SCHEMA'), ('tool.replay_ab16_resource_calibration_alt_v1.py', 'EXECUTION_SURFACE_SCHEMA'), ('tool.replay_ab16_resource_calibration_v1.py', 'EXECUTION_SURFACE_SCHEMA')),
        'calibration_validation': (('tool.replay_ab16_resource_calibration_v1.py', 'VALIDATION_SCHEMA'),),
        'calibration_aggregate': (('tool.ab16_resource_calibration_aggregator_v1.py', 'AGGREGATE_SCHEMA'),),
        'calibration_outside_replay': (('tool.ab16_resource_calibration_v1.py', 'OUTSIDE_REPLAY_SCHEMA'), ('tool.replay_ab16_resource_calibration_alt_v1.py', 'REPLAY_SCHEMA'), ('tool.replay_ab16_resource_calibration_v1.py', 'REPLAY_SCHEMA')),
        'calibration_authorization_bundle': (('tool.ab16_resource_calibration_v1.py', 'AUTHORIZATION_BUNDLE_SCHEMA'),),
        'calibration_observer_protocol': (('tool.ab16_resource_calibration_runner_v1.py', 'OBSERVER_PROTOCOL_SCHEMA'),),
        'calibration_package': (('tool.ab16_resource_admission_v1.py', 'CALIBRATION_PACKAGE_SCHEMA'), ('tool.ab16_resource_calibration_fd_loader_v1.py', 'PACKAGE_SCHEMA'), ('tool.ab16_resource_calibration_v1.py', 'CALIBRATION_PACKAGE_SCHEMA'), ('tool.replay_ab16_resource_calibration_alt_v1.py', 'CALIBRATION_PACKAGE_SCHEMA'), ('tool.replay_ab16_resource_calibration_v1.py', 'CALIBRATION_PACKAGE_SCHEMA')),
        'calibration_root_receipt': (('tool.replay_ab16_resource_calibration_alt_v1.py', 'ROOT_SCHEMA'), ('tool.replay_ab16_resource_calibration_v1.py', 'RECEIPT_SCHEMA')),
        'gate_a_receipt': (('tool.ab16_campaign_bootstrap_v2.py', 'GATE_A_SCHEMA'), ('tool.gate_a_validation_v2.py', 'GATE_A_SCHEMA')),
        'gate_a_full_preflight': (('tool.ab16_campaign_bootstrap_v2.py', 'FINAL_FULL_PREFLIGHT_SCHEMA'), ('tool.gate_a_validation_v2.py', 'PREFLIGHT_SCHEMA')),
        'gate_a_publication_commit': (('tool.ab16_campaign_bootstrap_v2.py', 'FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA'), ('tool.gate_a_validation_v2.py', 'PREFLIGHT_PUBLICATION_COMMIT_SCHEMA')),
        'gate_b_resource_gate': (('tool.ab16_campaign_bootstrap_v2.py', 'GATE_B_RESOURCE_GATE_SCHEMA'), ('tool.ab16_gate_b_qualification_v1.py', 'RESOURCE_GATE_SCHEMA')),
        'gate_b_epoch_observation': (('tool.ab16_campaign_bootstrap_v2.py', 'GATE_B_EPOCH_SCHEMA'),),
        'gate_b_approval': (('tool.ab16_campaign_bootstrap_v2.py', 'GATE_B_SCHEMA'),),
        'gate_b_handoff_request': (('tool.ab16_gate_b_qualification_v1.py', 'HANDOFF_REQUEST_SCHEMA'),),
        'gate_b_handoff_response': (('tool.ab16_gate_b_qualification_v1.py', 'HANDOFF_RESPONSE_SCHEMA'),),
        'terminal_history_freeze': (('tool.organic_resource_verifier_v2.py', 'HISTORY_FREEZE_SCHEMA'),),
        'terminal_history_replay': (('tool.organic_resource_verifier_v2.py', 'HISTORY_REPLAY_SCHEMA'),),
        'repository_snapshot': (('tool.ab16_campaign_bootstrap_v2.py', 'REPOSITORY_SNAPSHOT_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'SNAPSHOT_MANIFEST_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'SNAPSHOT_MANIFEST_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'SNAPSHOT_MANIFEST_SCHEMA')),
        'repository_snapshot_materialization': (('tool.ab16_campaign_bootstrap_v2.py', 'SNAPSHOT_MATERIALIZATION_SCHEMA'), ('tool.baseline_admission_v1.py', 'MATERIALIZATION_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'SNAPSHOT_MATERIALIZATION_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'SNAPSHOT_MATERIALIZATION_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'SNAPSHOT_MATERIALIZATION_SCHEMA')),
        'external_platform_assumptions': (('tool.ab16_campaign_bootstrap_v2.py', 'EXTERNAL_PLATFORM_SCHEMA'),),
        'path_preregistration': (('tool.ab16_campaign_bootstrap_v2.py', 'PATH_PREREGISTRATION_SCHEMA'),),
        'budget_broker_root_inventory': (('tool.ab16_budget_broker_v1.py', 'ROOT_INVENTORY_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'ARM_ROOT_INVENTORY_SCHEMA')),
        'budget_broker_manager_openfile_arm_grant': (('tool.organic_arm_runner_v1.py', 'MANAGER_OPENFILE_ARM_GRANT_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'MANAGER_OPENFILE_ARM_GRANT_SCHEMA')),
        'formal_root_budget_handoff': (('tool.ab16_campaign_bootstrap_v2.py', 'FORMAL_ROOT_BUDGET_HANDOFF_SCHEMA'),),
        'formal_root_budget_journal': (('tool.ab16_arm_attempt_closure_v1.py', 'BROKER_JOURNAL_SCHEMA'),),
        'formal_root_budget_terminal': (
            ('tool.replay_ab16_formal_root_v1.py', 'BUDGET_TERMINAL_SCHEMA'),
            ('tool.replay_ab16_formal_root_alt_v1.py', 'BUDGET_TERMINAL_SCHEMA'),
        ),
        'formal_launch_context': (
            ('tool.ab16_authority_v2.py', 'FORMAL_LAUNCH_CONTEXT_SCHEMA'),
        ),
        'recovery_disarm_intent': (
            ('tool.ab16_budget_broker_v1.py', 'RECOVERY_DISARM_INTENT_SCHEMA'),
        ),
        'formal_launch_owner_claim_identity': (
            ('tool.ab16_formal_loader_v1.py', 'FORMAL_LAUNCH_CLAIM_IDENTITY_SCHEMA'),
        ),
        'formal_supervisor_session': (
            ('tool.ab16_formal_campaign_v1.py', 'FORMAL_SUPERVISOR_SESSION_SCHEMA'),
        ),
        'formal_root_outside_replay_primary': (
            ('tool.ab16_final_release_actor_v1.py', 'PRIMARY_REPLAY_SCHEMA'),
            ('tool.ab16_formal_campaign_v1.py', 'PRIMARY_FORMAL_ROOT_REPLAY_SCHEMA'),
        ),
        'formal_root_outside_replay_alternate': (
            ('tool.ab16_final_release_actor_v1.py', 'ALTERNATE_REPLAY_SCHEMA'),
            ('tool.ab16_formal_campaign_v1.py', 'ALTERNATE_FORMAL_ROOT_REPLAY_SCHEMA'),
        ),
        'closure_formal_manifest': (
            ('tool.replay_ab16_formal_root_v1.py', 'FORMAL_MANIFEST_SCHEMA'),
            ('tool.replay_ab16_formal_root_alt_v1.py', 'MANIFEST_SCHEMA'),
        ),
        'closure_result': (
            ('tool.ab16_final_release_actor_v1.py', 'CLOSURE_RESULT_SCHEMA'),
        ),
        'final_release_actor': (
            ('tool.ab16_closure_actor_v1.py', 'FINAL_RELEASE_ACTOR_SCHEMA'),
        ),
        'post_root_closure_evidence': (
            ('tool.ab16_formal_success_verifier_v1.py', 'POST_ROOT_CLOSURE_EVIDENCE_SCHEMA'),
        ),
        'final_release_result': (
            ('tool.ab16_formal_campaign_v1.py', 'FINAL_RELEASE_RESULT_SCHEMA'),
        ),
        'success_dual_lock_release': (
            ('tool.ab16_final_release_actor_v1.py', 'SUCCESS_TERMINAL_SCHEMA'),
        ),
        'incomplete_terminal_release': (
            ('tool.ab16_formal_success_verifier_v1.py', 'FAILURE_TERMINAL_RELEASE_SCHEMA'),
            ('tool.ab16_final_release_actor_v1.py', 'FAILURE_TERMINAL_SCHEMA'),
        ),
        'arm_budget_reconcile': (('tool.ab16_budget_broker_v1.py', 'ARM_RECONCILE_SCHEMA'),),
        'arm_budget_terminal': (('tool.ab16_budget_broker_v1.py', 'ARM_TERMINAL_SCHEMA'),),
        'package_independent_replay': (('tool.ab16_campaign_bootstrap_v2.py', 'PACKAGE_INDEPENDENT_REPLAY_SCHEMA'), ('tool.package_independent_verifier_v1.py', 'RESULT_SCHEMA')),
        'formal_attempt_consumption': (('tool.ab16_outer_closeout_state_v1.py', 'CONSUMPTION_SCHEMA'),),
        'formal_package_selected_fd_transport': (('tool.ab16_formal_launch_validator_v1.py', 'SELECTED_FD_TRANSPORT_SCHEMA'),),
        'formal_worker_session': (('tool.ab16_formal_loader_v1.py', 'FORMAL_WORKER_SESSION_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'FORMAL_WORKER_SESSION_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'FORMAL_WORKER_SESSION_SCHEMA')),
        'continuation_authorization': (('tool.ab16_authority_v2.py', 'CONTINUATION_SCHEMA'),),
        'baseline_admission': (('tool.ab16_authority_v2.py', 'BASELINE_ADMISSION_SCHEMA'), ('tool.baseline_admission_v1.py', 'ADMISSION_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'BASELINE_ADMISSION_SCHEMA')),
        'common_prestate': (('tool.ab16_authority_v2.py', 'COMMON_PRESTATE_SCHEMA'),),
        'campaign_manifest': (('tool.organic_arm_runner_v1.py', 'PROSPECTIVE_FORMAL_MANIFEST_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_FORMAL_MANIFEST_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_FORMAL_MANIFEST_SCHEMA')),
        'arm_pre_run': (('tool.organic_resource_lifecycle_v2.py', 'FORMAL_PRE_RUN_AUTHORITY_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'FORMAL_PRE_RUN_SCHEMA'), ('tool.organic_unit_orchestrator_v2.py', 'FORMAL_PRE_RUN_SCHEMA')),
        'arm_selection': (('tool.ab16_terminal_gate_v3.py', 'SELECTION_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'FORMAL_SELECTION_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'FORMAL_RUNNER_SELECTION_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'FORMAL_RUNNER_SELECTION_SCHEMA'), ('tool.organic_unit_orchestrator_v2.py', 'FORMAL_RUNNER_SELECTION_SCHEMA')),
        'arm_result': (('tool.organic_arm_replay_v1.py', 'FORMAL_RESULT_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'FORMAL_RESULT_SCHEMA')),
        'supervisor_module_origin': (('tool.organic_resource_verifier_v2.py', 'SUPERVISOR_MODULE_ORIGIN_RECEIPT_SCHEMA'),),
        'lifecycle_inner': (('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_INNER_SCHEMA'),),
        'lifecycle_preterminal': (('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_PRETERMINAL_SCHEMA'),),
        'lifecycle_release': (('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_RELEASE_SCHEMA'),),
        'lifecycle_terminal': (('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_TERMINAL_SCHEMA'),),
        'lifecycle_cleanup': (('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_CLEANUP_SCHEMA'),),
        'reference_acquisition': (('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_REFERENCE_ACQUISITION_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_REFERENCE_ACQUISITION_SCHEMA')),
        'reference_release': (('tool.organic_resource_lifecycle_v2.py', 'PROSPECTIVE_REFERENCE_RELEASE_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_REFERENCE_RELEASE_SCHEMA')),
        'reference_manager_epoch': (('tool.organic_resource_verifier_v2.py', 'EPOCH_SCHEMA'),),
        'detached_resource_terminal': (('tool.organic_resource_verifier_v2.py', 'PROSPECTIVE_DETACHED_SCHEMA'),),
        'arm_cut_free_replay': (('tool.organic_arm_replay_v1.py', 'FORMAL_CUT_FREE_SCHEMA'),),
        'arm_arithmetic_replay': (('tool.organic_arm_replay_v1.py', 'FORMAL_RECEIPT_SCHEMA'),),
        'compile_attach_journal': (('tool.organic_arm_runner_v1.py', 'JOURNAL_SCHEMA'),),
        'budget_segment_bundle': (('tool.organic_arm_runner_v1.py', 'BUDGET_SEGMENT_BUNDLE_SCHEMA'),),
        'controller_terminal': (('tool.ab16_terminal_gate_v2.py', 'CONTROLLER_TERMINAL_SCHEMA'), ('tool.ab16_terminal_gate_v3.py', 'CONTROLLER_TERMINAL_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'CONTROLLER_TERMINAL_SCHEMA')),
        'resource_verification': (('tool.ab16_terminal_gate_v3.py', 'RESOURCE_PRETERMINAL_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'RESOURCE_VERIFICATION_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'RESOURCE_SCHEMA')),
        'sealed_execution_source': (('tool.organic_resource_lifecycle_v2.py', 'SEALED_EXECUTION_SOURCE_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'SEALED_EXECUTION_SOURCE_SCHEMA')),
        'selected_byte_launch': (('tool.organic_resource_lifecycle_v2.py', 'SELECTED_BYTE_LAUNCH_SCHEMA_V2'), ('tool.organic_resource_verifier_v2.py', 'SELECTED_BYTE_LAUNCH_SCHEMA_V2')),
        'launch_environment': (('tool.organic_resource_verifier_v2.py', 'LAUNCH_ENVIRONMENT_SCHEMA'), ('tool.organic_unit_orchestrator_v2.py', 'LAUNCH_ENVIRONMENT_SCHEMA')),
        'formal_arm_prelaunch': (('tool.ab16_outer_refunit_closeout_v1.py', 'ARM_PRELAUNCH_SCHEMA'),),
        'formal_controller_result': (('tool.ab16_formal_success_verifier_v1.py', 'CONTROLLER_RESULT_SCHEMA'),),
        'formal_child_audit': (('tool.ab16_outer_refunit_closeout_v1.py', 'CHILD_AUDIT_SCHEMA'),),
        'formal_gate1_prelaunch_ownership': (('tool.ab16_outer_refunit_closeout_v1.py', 'GATE1_OWNERSHIP_SCHEMA'),),
        'incomplete_pre_release': (('tool.ab16_formal_success_verifier_v1.py', 'FAILURE_RELEASE_SCHEMA'),),
        'pytest_collection_binding': (('tool.gate_a_validation_v2.py', 'PYTEST_COLLECTION_BINDING_SCHEMA'),),
        'drill_selection': (('tool.organic_resource_lifecycle_v1.py', 'DRILL_SELECTION_SCHEMA'), ('tool.organic_resource_lifecycle_v2.py', 'DRILL_SELECTION_SCHEMA'), ('tool.organic_resource_verifier_v1.py', 'DRILL_SELECTION_SCHEMA'), ('tool.organic_resource_verifier_v2.py', 'DRILL_SELECTION_SCHEMA'), ('tool.organic_unit_orchestrator_v1.py', 'DRILL_SELECTION_SCHEMA'), ('tool.organic_unit_orchestrator_v2.py', 'DRILL_SELECTION_SCHEMA')),
        'drill_result': (('tool.organic_arm_replay_v1.py', 'RESULT_SCHEMA'), ('tool.organic_arm_runner_v1.py', 'RESULT_SCHEMA')),
    }
)

PROSPECTIVE_SCHEMA_BINDINGS: Final = MappingProxyType(
    {
        key: MappingProxyType(
            {
                "schema": schema,
                "producer": PROSPECTIVE_SCHEMA_PRODUCERS[key],
                "consumers": PROSPECTIVE_SCHEMA_CONSUMERS.get(key, ()),
            }
        )
        for key, schema in PROSPECTIVE_SCHEMAS.items()
    }
)

# These package tools are required even when they do not own a discriminator
# producer constant (the cohort document itself and the calibration transport
# roles are the important cases).  Consumer roles discovered by the AST parity
# test are added to this set before comparing the bootstrap and authority maps.
PROSPECTIVE_REQUIRED_PACKAGE_TOOL_FILES: Final = (
    "ab16_artifact_cohort_v1.py",
    "ab16_arm_attempt_closure_v1.py",
    "ab16_budgeted_writers_v1.py",
    "ab16_final_release_actor_v1.py",
    "ab16_package_writer_inventory_v1.py",
    "ab16_resource_calibration_aggregator_v1.py",
    "ab16_resource_calibration_fd_loader_v1.py",
    "ab16_resource_calibration_harness_v1.py",
    "ab16_resource_calibration_package_v1.py",
    "ab16_resource_calibration_runner_v1.py",
    "ab16_resource_calibration_v1.py",
    "ab16_resource_calibration_workloads_v1.py",
    "replay_ab16_formal_root_alt_v1.py",
    "replay_ab16_formal_root_v1.py",
    "replay_ab16_resource_calibration_alt_v1.py",
    "replay_ab16_resource_calibration_v1.py",
)

ROOT_CLOSURE_CONTRACT: Final = MappingProxyType(
    {
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
)

OUTSIDE_REPLAY_CLOSURE_CONTRACT: Final = MappingProxyType(
    {
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
)


class CohortContractError(ValueError):
    """A cohort document omitted, added, or changed one closed field."""


def _clone(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clone(member) for key, member in value.items()}
    if isinstance(value, tuple):
        return [_clone(member) for member in value]
    if isinstance(value, list):
        return [_clone(member) for member in value]
    return value


def _reject(path: str, message: str) -> NoReturn:
    raise CohortContractError(f"{path}: {message}")


def _require_exact(actual: object, expected: object, path: str) -> None:
    if isinstance(expected, Mapping):
        if type(actual) is not dict:
            _reject(path, "expected an object")
        actual_mapping = actual
        if set(actual_mapping) != set(expected):
            _reject(path, "key set drifted")
        for key, expected_member in expected.items():
            _require_exact(actual_mapping[key], expected_member, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if type(actual) is not list:
            _reject(path, "expected an array")
        actual_sequence = actual
        if len(actual_sequence) != len(expected):
            _reject(path, "array length drifted")
        for index, (actual_member, expected_member) in enumerate(
            zip(actual_sequence, expected, strict=True)
        ):
            _require_exact(actual_member, expected_member, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        _reject(path, "value drifted")


def expanded_historical_cohort() -> dict[str, object]:
    """Return the closed replay-only classification of the current cohort."""

    value = {
        "schema_version": COHORT_DOCUMENT_SCHEMA,
        "cohort_id": HISTORICAL_COHORT_ID,
        "authority_scope": AUTHORITY_SCOPE,
        "launch_ready": False,
        "historical_replay_only": True,
        "immutable_roots": IMMUTABLE_HISTORICAL_ROOTS,
        "immutable_roots_are_bound_to_own_pinned_bytes": True,
        "schemas": HISTORICAL_ACCEPTED_SCHEMAS,
        "authority_flags": FALSE_AUTHORITY_FLAGS,
    }
    cloned = _clone(value)
    assert isinstance(cloned, dict)
    return cloned


def expanded_prospective_cohort() -> dict[str, object]:
    """Return the one fully expanded, launch-blocked successor cohort."""

    value = {
        "schema_version": COHORT_DOCUMENT_SCHEMA,
        "cohort_id": PROSPECTIVE_COHORT_ID,
        "authority_scope": AUTHORITY_SCOPE,
        "launch_ready": False,
        "historical_replay_only": False,
        "a039_in_scope": False,
        "package_roles": {
            "independent_verifier": PACKAGE_VERIFIER_ROLE,
            "native_helper_binary": NATIVE_HELPER_BINARY_ROLE,
            "native_helper_wrapper": NATIVE_HELPER_WRAPPER_ROLE,
            "final_release_actor": FINAL_RELEASE_ACTOR_ROLE,
        },
        "schemas": PROSPECTIVE_SCHEMAS,
        "root_closure": ROOT_CLOSURE_CONTRACT,
        "outside_replay_closure": OUTSIDE_REPLAY_CLOSURE_CONTRACT,
        "authority_flags": FALSE_AUTHORITY_FLAGS,
    }
    cloned = _clone(value)
    assert isinstance(cloned, dict)
    return cloned


def validate_historical_cohort(value: object) -> dict[str, object]:
    """Accept only the byte-for-byte-equivalent historical cohort expansion."""

    expected = expanded_historical_cohort()
    _require_exact(value, expected, "$")
    assert isinstance(value, dict)
    return value


def validate_prospective_cohort(value: object) -> dict[str, object]:
    """Accept only the complete successor cohort; every version is coupled."""

    expected = expanded_prospective_cohort()
    _require_exact(value, expected, "$")
    assert isinstance(value, dict)
    return value


def validate_no_cross_cohort_mix(value: object) -> dict[str, object]:
    """Alias naming the launch-side fail-closed validation boundary."""

    return validate_prospective_cohort(value)

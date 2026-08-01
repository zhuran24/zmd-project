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
PACKAGE_VERIFIER_ROLE: Final = "package_independent_verifier_v1"

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

# Every artifact or proof record with an independent discriminator is explicit.
# Unchanged schemas remain entries; a missing entry cannot be treated as an
# unversioned package helper.
PROSPECTIVE_SCHEMAS: Final = MappingProxyType(
    {
        "resource_profile_set": "noncert-cuts-ab16-resource-profile-set-v2",
        "stage_resource_admission": "noncert-cuts-ab16-stage-resource-admission-v2",
        "calibration_declaration": "noncert-cuts-ab16-resource-calibration-declaration-v1",
        "calibration_sample": "noncert-cuts-ab16-resource-calibration-sample-v1",
        "calibration_validation": "noncert-cuts-ab16-resource-calibration-validation-v1",
        "calibration_aggregate": "noncert-cuts-ab16-resource-calibration-aggregate-v1",
        "calibration_profile_candidate": (
            "noncert-cuts-ab16-resource-calibration-profile-candidate-v1"
        ),
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
        "bootstrap_package_failure_closeout": (
            "noncert-cuts-ab16-bootstrap-package-failure-closeout-v1"
        ),
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

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
REVIEWER_RECORD_COLLECTION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1"
)
RUNTIME_PATCH_STATUS_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
REVIEWED_RUNTIME_PATCH_INGEST_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_v1"
)
DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_20260424/"
    "anchor119_row_domain_signoff_record_validator.json"
)
DEFAULT_REVIEWER_RECORD_COLLECTION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
    "anchor119_row_domain_reviewer_record_collection.json"
)
DEFAULT_RUNTIME_PATCH_STATUS_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_20260424/"
    "anchor119_row_domain_runtime_patch_status.json"
)
DEFAULT_RUNTIME_PATCH_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)
INGEST_GATE_NOTICE = (
    "Review-only/default-off ingest gate contract only. No actual reviewer-signed "
    "runtime patch signoff record has been provided or ingested into repo-side "
    "review state. This artifact formalizes the future manual validation and "
    "ingest-review contract only; it does not set reviewed_runtime_patch_exists=true "
    "and does not allow runtime enablement."
)
NO_ACTUAL_RECORD_DETAIL = (
    "No actual reviewer-signed runtime patch signoff record has been provided to "
    "this ingest gate. reviewed_runtime_patch_exists remains false, repo-side "
    "review state is unchanged, and runtime enablement remains disallowed."
)
INGEST_REVIEW_DETAIL = (
    "A future manual ingest review should first validate the reviewer-signed JSON "
    "against the locked validator rules and reviewer-record handoff contract, then "
    "decide in a separate review whether repo-side review state can record the patch "
    "as reviewed. This builder does not perform that validation or ingest."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate(
    project_root: Path,
    *,
    signoff_record_validator_path: Optional[Path] = None,
    reviewer_record_collection_path: Optional[Path] = None,
    runtime_patch_status_path: Optional[Path] = None,
    runtime_patch_signoff_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    signoff_record_validator_resolved = _resolve_path(
        project_root,
        signoff_record_validator_path
        if signoff_record_validator_path is not None
        else DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH,
    )
    reviewer_record_collection_resolved = _resolve_path(
        project_root,
        reviewer_record_collection_path
        if reviewer_record_collection_path is not None
        else DEFAULT_REVIEWER_RECORD_COLLECTION_PATH,
    )
    runtime_patch_status_resolved = _resolve_path(
        project_root,
        runtime_patch_status_path
        if runtime_patch_status_path is not None
        else DEFAULT_RUNTIME_PATCH_STATUS_PATH,
    )
    runtime_patch_signoff_bundle_resolved = _resolve_path(
        project_root,
        runtime_patch_signoff_bundle_path
        if runtime_patch_signoff_bundle_path is not None
        else DEFAULT_RUNTIME_PATCH_SIGNOFF_BUNDLE_PATH,
    )

    signoff_record_validator_report, signoff_record_validator_error = _load_json_mapping(
        signoff_record_validator_resolved
    )
    reviewer_record_collection_report, reviewer_record_collection_error = (
        _load_json_mapping(reviewer_record_collection_resolved)
    )
    runtime_patch_status_report, runtime_patch_status_error = _load_json_mapping(
        runtime_patch_status_resolved
    )
    runtime_patch_signoff_bundle_report, runtime_patch_signoff_bundle_error = (
        _load_json_mapping(runtime_patch_signoff_bundle_resolved)
    )

    signoff_record_validator_meta = (
        _mapping(signoff_record_validator_report.get("metadata"))
        if signoff_record_validator_report
        else {}
    )
    signoff_record_validator_status = (
        _mapping(signoff_record_validator_report.get("status"))
        if signoff_record_validator_report
        else {}
    )
    signoff_record_validator = (
        _mapping(signoff_record_validator_report.get("signoff_record_validator"))
        if signoff_record_validator_report
        else {}
    )
    reviewer_record_collection_meta = (
        _mapping(reviewer_record_collection_report.get("metadata"))
        if reviewer_record_collection_report
        else {}
    )
    reviewer_record_collection_status = (
        _mapping(reviewer_record_collection_report.get("status"))
        if reviewer_record_collection_report
        else {}
    )
    reviewer_record_collection = (
        _mapping(reviewer_record_collection_report.get("reviewer_record_collection"))
        if reviewer_record_collection_report
        else {}
    )
    runtime_patch_status_meta = (
        _mapping(runtime_patch_status_report.get("metadata"))
        if runtime_patch_status_report
        else {}
    )
    runtime_patch_status = (
        _mapping(runtime_patch_status_report.get("status"))
        if runtime_patch_status_report
        else {}
    )
    runtime_patch_code_status = (
        _mapping(runtime_patch_status_report.get("code_status"))
        if runtime_patch_status_report
        else {}
    )
    runtime_patch_signoff_bundle_meta = (
        _mapping(runtime_patch_signoff_bundle_report.get("metadata"))
        if runtime_patch_signoff_bundle_report
        else {}
    )
    runtime_patch_signoff_bundle_status = (
        _mapping(runtime_patch_signoff_bundle_report.get("status"))
        if runtime_patch_signoff_bundle_report
        else {}
    )
    runtime_patch_signoff_bundle = (
        _mapping(runtime_patch_signoff_bundle_report.get("signoff_bundle"))
        if runtime_patch_signoff_bundle_report
        else {}
    )
    candidate = (
        _mapping(reviewer_record_collection_report.get("candidate"))
        if reviewer_record_collection_report
        else _mapping(signoff_record_validator_report.get("candidate"))
        if signoff_record_validator_report
        else _mapping(runtime_patch_status_report.get("candidate"))
        if runtime_patch_status_report
        else _mapping(runtime_patch_signoff_bundle_report.get("candidate"))
        if runtime_patch_signoff_bundle_report
        else {}
    )

    signoff_record_validator_present = bool(
        signoff_record_validator_report is not None
        and signoff_record_validator_error is None
        and signoff_record_validator_meta.get("source") == SIGNOFF_RECORD_VALIDATOR_SOURCE
    )
    reviewer_record_collection_present = bool(
        reviewer_record_collection_report is not None
        and reviewer_record_collection_error is None
        and reviewer_record_collection_meta.get("source")
        == REVIEWER_RECORD_COLLECTION_SOURCE
    )
    runtime_patch_status_present = bool(
        runtime_patch_status_report is not None
        and runtime_patch_status_error is None
        and runtime_patch_status_meta.get("source") == RUNTIME_PATCH_STATUS_SOURCE
    )
    runtime_patch_signoff_bundle_present = bool(
        runtime_patch_signoff_bundle_report is not None
        and runtime_patch_signoff_bundle_error is None
        and runtime_patch_signoff_bundle_meta.get("source")
        == RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE
    )

    signoff_record_validator_ready = bool(
        signoff_record_validator_status.get("signoff_record_validator_ready", False)
    )
    reviewer_record_collection_ready = bool(
        reviewer_record_collection_status.get("reviewer_record_collection_ready", False)
    )
    runtime_patch_status_ready = bool(
        runtime_patch_status.get("patch_status_ready", False)
    )
    runtime_patch_authored_but_not_enableable = bool(
        runtime_patch_status.get("authored_but_not_enableable", False)
    )
    runtime_patch_signoff_bundle_ready = bool(
        runtime_patch_signoff_bundle_status.get("signoff_bundle_ready", False)
    )
    upstream_reviewed_runtime_patch_exists = bool(
        signoff_record_validator_status.get("reviewed_runtime_patch_exists", False)
        or reviewer_record_collection_status.get("reviewed_runtime_patch_exists", False)
        or runtime_patch_status.get("reviewed_runtime_patch_exists", False)
        or runtime_patch_signoff_bundle_status.get("reviewed_runtime_patch_exists", False)
    )
    upstream_runtime_enablement_allowed = bool(
        signoff_record_validator_status.get("runtime_enablement_allowed", False)
        or reviewer_record_collection_status.get("runtime_enablement_allowed", False)
        or runtime_patch_status.get("runtime_enablement_allowed", False)
        or runtime_patch_signoff_bundle_status.get("runtime_enablement_allowed", False)
    )

    target_record_identity = _mapping(
        reviewer_record_collection.get("target_record_identity")
    )
    expected_collection_source = _mapping(
        reviewer_record_collection.get("expected_collection_source")
    )
    expected_handoff = _mapping(reviewer_record_collection.get("expected_handoff"))
    preserved_contract = _mapping(
        reviewer_record_collection.get("preserved_contract")
    )
    collection_state = _mapping(reviewer_record_collection.get("collection_state"))
    validator_rules = _mapping(signoff_record_validator.get("validator_rules"))
    actual_record_validation = _mapping(
        signoff_record_validator.get("actual_record_validation")
    )
    signoff_record_template = _mapping(
        runtime_patch_signoff_bundle.get("signoff_record_template")
    )
    required_reviewer_statements = _mapping_list(
        runtime_patch_signoff_bundle.get("required_reviewer_statements")
    )

    record_identity = str(target_record_identity.get("record_identity") or "").strip()
    record_type = (
        str(target_record_identity.get("record_type") or "").strip()
        or str(signoff_record_validator.get("target_record_type") or "").strip()
        or str(signoff_record_template.get("record_type") or "").strip()
    )
    scope = (
        str(target_record_identity.get("scope") or "").strip()
        or str(signoff_record_validator.get("scope") or "").strip()
        or str(signoff_record_template.get("scope") or "").strip()
        or str(runtime_patch_signoff_bundle.get("scope") or "").strip()
    )
    handoff_format = str(expected_handoff.get("handoff_format") or "").strip()
    handoff_dir = str(expected_handoff.get("handoff_dir") or "").strip()
    handoff_path_shape = str(expected_handoff.get("handoff_path_shape") or "").strip()
    handoff_filename_tokens = _string_list(
        expected_handoff.get("handoff_filename_tokens")
    )
    base_payload_template = _mapping(
        expected_collection_source.get("base_payload_template")
    )
    validator_template_payload = _mapping(
        signoff_record_validator.get("expected_template_payload")
    )

    collection_required_record_fields = _mapping_list(
        preserved_contract.get("required_record_fields")
    )
    validator_required_record_fields = _mapping_list(
        validator_rules.get("required_fields")
    )
    collection_required_field_names = _field_names(collection_required_record_fields)
    validator_required_field_names = _field_names(validator_required_record_fields)

    collection_required_statement_ids = _string_list(
        preserved_contract.get("required_reviewer_statement_ids")
    )
    validator_required_statement_ids = _string_list(
        signoff_record_validator.get("required_reviewer_statement_ids")
    )
    signoff_bundle_statement_ids = [
        str(entry.get("statement_id"))
        for entry in required_reviewer_statements
        if entry.get("statement_id")
    ]

    collection_still_blocked_gate_ids = _string_list(
        preserved_contract.get("still_blocked_gate_ids")
    )
    validator_still_blocked_gate_ids = _string_list(
        _mapping(validator_rules.get("still_blocked_gate_ids")).get("required_ids")
    )
    signoff_template_still_blocked_gate_ids = _string_list(
        signoff_record_template.get("still_blocked_gate_ids")
    )
    current_still_blocked_gate_ids = (
        collection_still_blocked_gate_ids
        or validator_still_blocked_gate_ids
        or signoff_template_still_blocked_gate_ids
    )
    post_ingest_still_blocked_gate_ids = [
        gate_id
        for gate_id in current_still_blocked_gate_ids
        if gate_id != "reviewed_runtime_patch_exists"
    ]

    repo_side_review_target_defined = bool(record_identity and record_type and scope)
    locked_handoff_contract_defined = bool(
        handoff_format == "json"
        and handoff_dir
        and handoff_path_shape
        and handoff_filename_tokens
    )
    template_contract_aligned = bool(
        record_type
        and scope
        and str(base_payload_template.get("record_type") or "").strip() == record_type
        and str(validator_template_payload.get("record_type") or "").strip() == record_type
        and str(signoff_record_template.get("record_type") or "").strip() == record_type
        and str(base_payload_template.get("scope") or "").strip() == scope
        and str(validator_template_payload.get("scope") or "").strip() == scope
        and str(signoff_record_template.get("scope") or "").strip() == scope
        and str(signoff_record_validator.get("target_record_type") or "").strip()
        == record_type
        and str(signoff_record_validator.get("scope") or "").strip() == scope
    )
    required_record_fields_locked = bool(
        collection_required_field_names
        and validator_required_field_names
        and collection_required_field_names == validator_required_field_names
    )
    reviewer_statement_ids_locked = bool(
        collection_required_statement_ids
        and validator_required_statement_ids
        and signoff_bundle_statement_ids
        and collection_required_statement_ids == validator_required_statement_ids
        and validator_required_statement_ids == signoff_bundle_statement_ids
    )
    still_blocked_gate_ids_locked = bool(
        current_still_blocked_gate_ids
        and current_still_blocked_gate_ids == validator_still_blocked_gate_ids
        and current_still_blocked_gate_ids == signoff_template_still_blocked_gate_ids
    )
    post_ingest_still_blocked_gate_ids_defined = bool(post_ingest_still_blocked_gate_ids)
    default_off_retained = bool(
        signoff_record_validator_present
        and reviewer_record_collection_present
        and runtime_patch_status_present
        and runtime_patch_signoff_bundle_present
        and bool(signoff_record_validator_meta.get("default_off", False))
        and bool(reviewer_record_collection_meta.get("default_off", False))
        and bool(runtime_patch_status_meta.get("default_off", False))
        and bool(runtime_patch_signoff_bundle_meta.get("default_off", False))
        and not upstream_runtime_enablement_allowed
    )
    actual_record_not_provided_yet = bool(
        not reviewer_record_collection_status.get("actual_reviewer_record_collected", False)
        and not collection_state.get("actual_record_collected", False)
        and not collection_state.get("reviewer_signed_record_present", False)
        and not actual_record_validation.get("record_payload_provided", False)
        and not actual_record_validation.get("record_payload_validated", False)
    )

    checks = [
        _check(
            "signoff_record_validator_present",
            "pass" if signoff_record_validator_present else "fail",
            "signoff record validator loaded"
            if signoff_record_validator_present
            else signoff_record_validator_error
            or (
                f"unexpected_source:{signoff_record_validator_meta.get('source')}"
                if signoff_record_validator_report is not None
                else f"missing:{_display_path(project_root, signoff_record_validator_resolved)}"
            ),
        ),
        _check(
            "reviewer_record_collection_present",
            "pass" if reviewer_record_collection_present else "fail",
            "reviewer record collection loaded"
            if reviewer_record_collection_present
            else reviewer_record_collection_error
            or (
                f"unexpected_source:{reviewer_record_collection_meta.get('source')}"
                if reviewer_record_collection_report is not None
                else f"missing:{_display_path(project_root, reviewer_record_collection_resolved)}"
            ),
        ),
        _check(
            "runtime_patch_status_present",
            "pass" if runtime_patch_status_present else "fail",
            "runtime patch status loaded"
            if runtime_patch_status_present
            else runtime_patch_status_error
            or (
                f"unexpected_source:{runtime_patch_status_meta.get('source')}"
                if runtime_patch_status_report is not None
                else f"missing:{_display_path(project_root, runtime_patch_status_resolved)}"
            ),
        ),
        _check(
            "runtime_patch_signoff_bundle_present",
            "pass" if runtime_patch_signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if runtime_patch_signoff_bundle_present
            else runtime_patch_signoff_bundle_error
            or (
                f"unexpected_source:{runtime_patch_signoff_bundle_meta.get('source')}"
                if runtime_patch_signoff_bundle_report is not None
                else f"missing:{_display_path(project_root, runtime_patch_signoff_bundle_resolved)}"
            ),
        ),
        _check(
            "signoff_record_validator_ready",
            "pass" if signoff_record_validator_ready else "fail",
            str(signoff_record_validator_ready),
        ),
        _check(
            "reviewer_record_collection_ready",
            "pass" if reviewer_record_collection_ready else "fail",
            str(reviewer_record_collection_ready),
        ),
        _check(
            "runtime_patch_status_ready",
            "pass" if runtime_patch_status_ready else "fail",
            str(runtime_patch_status_ready),
        ),
        _check(
            "runtime_patch_authored_but_not_enableable",
            "pass" if runtime_patch_authored_but_not_enableable else "fail",
            str(runtime_patch_authored_but_not_enableable),
        ),
        _check(
            "runtime_patch_signoff_bundle_ready",
            "pass" if runtime_patch_signoff_bundle_ready else "fail",
            str(runtime_patch_signoff_bundle_ready),
        ),
        _check(
            "repo_side_review_target_defined",
            "pass" if repo_side_review_target_defined else "fail",
            record_identity or "missing",
        ),
        _check(
            "locked_handoff_contract_defined",
            "pass" if locked_handoff_contract_defined else "fail",
            handoff_path_shape or "missing",
        ),
        _check(
            "template_contract_aligned",
            "pass" if template_contract_aligned else "fail",
            "collection base payload, validator template, signoff template, and target identity are aligned"
            if template_contract_aligned
            else "record_type_or_scope_mismatch_between_collection_validator_and_signoff_bundle",
        ),
        _check(
            "required_record_fields_locked",
            "pass" if required_record_fields_locked else "fail",
            ",".join(collection_required_field_names)
            if required_record_fields_locked
            else "required_field_names_mismatch",
        ),
        _check(
            "required_reviewer_statement_ids_locked",
            "pass" if reviewer_statement_ids_locked else "fail",
            ",".join(collection_required_statement_ids)
            if reviewer_statement_ids_locked
            else "required_reviewer_statement_ids_mismatch",
        ),
        _check(
            "still_blocked_gate_ids_locked",
            "pass" if still_blocked_gate_ids_locked else "fail",
            ",".join(current_still_blocked_gate_ids)
            if still_blocked_gate_ids_locked
            else "still_blocked_gate_ids_mismatch",
        ),
        _check(
            "post_ingest_still_blocked_gate_ids_defined",
            "pass" if post_ingest_still_blocked_gate_ids_defined else "fail",
            ",".join(post_ingest_still_blocked_gate_ids)
            if post_ingest_still_blocked_gate_ids_defined
            else "missing_post_ingest_still_blocked_gate_ids",
        ),
        _check(
            "default_off_retained",
            "pass" if default_off_retained else "fail",
            "default-off retained and runtime enablement remains blocked"
            if default_off_retained
            else "expected default_off=true and runtime_enablement_allowed=false upstream",
        ),
        _check(
            "upstream_reviewed_runtime_patch_absent_as_expected",
            "pass" if not upstream_reviewed_runtime_patch_exists else "fail",
            str(upstream_reviewed_runtime_patch_exists),
        ),
        _check(
            "upstream_runtime_enablement_blocked_as_expected",
            "pass" if not upstream_runtime_enablement_allowed else "fail",
            str(upstream_runtime_enablement_allowed),
        ),
        _check(
            "actual_reviewed_runtime_patch_record_not_provided_yet",
            "pass" if actual_record_not_provided_yet else "fail",
            NO_ACTUAL_RECORD_DETAIL
            if actual_record_not_provided_yet
            else "actual_record_or_validation_state_present_but_ingest_gate_must_remain_pre_ingest",
        ),
    ]

    reviewed_runtime_patch_ingest_gate_ready = all(
        check["status"] == "pass" for check in checks
    )

    gates = [
        _gate(
            "signoff_record_validator_ready",
            signoff_record_validator_ready,
            True,
            "The future ingest review depends on the locked validator contract already being ready.",
        ),
        _gate(
            "reviewer_record_collection_ready",
            reviewer_record_collection_ready,
            True,
            "The future ingest review depends on the locked reviewer-record collection contract already being ready.",
        ),
        _gate(
            "runtime_patch_status_authored_but_not_enableable",
            runtime_patch_status_ready and runtime_patch_authored_but_not_enableable,
            True,
            "The reviewed runtime patch must remain authored-but-not-enableable before and after any future ingest review.",
        ),
        _gate(
            "runtime_patch_signoff_bundle_ready",
            runtime_patch_signoff_bundle_ready,
            True,
            "The signoff bundle must already define the required reviewer statements and signoff template.",
        ),
        _gate(
            "locked_future_record_identity_defined",
            repo_side_review_target_defined,
            True,
            "The target reviewed-runtime-patch record identity and scope must stay locked.",
        ),
        _gate(
            "locked_future_handoff_path_shape_defined",
            locked_handoff_contract_defined,
            True,
            "The future reviewer-side handoff path shape must stay locked before any manual ingest review.",
        ),
        _gate(
            "locked_validator_contract_available",
            template_contract_aligned
            and required_record_fields_locked
            and reviewer_statement_ids_locked
            and still_blocked_gate_ids_locked,
            True,
            "The future ingest review depends on a locked cross-artifact contract for fields, statement ids, and still-blocked gate ids.",
        ),
        _gate(
            "current_review_state_still_pending_manual_ingest",
            not upstream_reviewed_runtime_patch_exists,
            True,
            "repo-side review state must still show reviewed_runtime_patch_exists=false until a separate future ingest review explicitly marks it reviewed.",
        ),
        _gate(
            "runtime_enablement_still_blocked",
            not upstream_runtime_enablement_allowed,
            True,
            "Any future ingest review must preserve runtime_enablement_allowed=false.",
        ),
        _gate(
            "reviewer_signed_record_supplied_for_review",
            False,
            True,
            "A future reviewer-signed runtime patch signoff record must be supplied at the locked handoff path before manual ingest review can mark the patch as reviewed.",
        ),
        _gate(
            "reviewer_signed_record_validates_against_locked_contract",
            False,
            True,
            "The future reviewer-signed record must be manually validated against signoff_record_validator.validator_rules before manual ingest review can mark the patch as reviewed.",
        ),
        _gate(
            "separate_manual_ingest_review_approved",
            False,
            True,
            "A separate future review must explicitly approve the repo-side review-state update; this artifact does not perform ingest.",
        ),
        _gate(
            "post_ingest_still_blocked_gate_ids_defined",
            post_ingest_still_blocked_gate_ids_defined,
            False,
            "The gate contract preserves which blockers remain after a future review marks the patch as reviewed.",
        ),
        _gate(
            "review_only_artifact_does_not_ingest",
            True,
            False,
            "This artifact formalizes the future ingest-review contract only. It does not validate an actual reviewer-signed record and does not modify repo-side review state.",
        ),
    ]

    future_review_state_marking_prerequisites_met = all(
        bool(gate.get("satisfied"))
        for gate in gates
        if bool(gate.get("blocking"))
    )
    missing_prerequisite_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if bool(gate.get("blocking")) and not bool(gate.get("satisfied"))
    ]

    if not reviewed_runtime_patch_ingest_gate_ready:
        recommended_next_step = "repair_reviewed_runtime_patch_ingest_gate_inputs"
        handoff_recommendation = (
            "Reviewed runtime patch ingest gate contract is blocked; repair the missing "
            "validator, reviewer-record collection, runtime-patch status, or signoff "
            "bundle prerequisites before planning any future manual validation or ingest "
            "review."
        )
    elif missing_prerequisite_gate_ids:
        recommended_next_step = (
            "manually_validate_reviewer_record_then_run_separate_ingest_review_without_enablement"
        )
        handoff_recommendation = (
            "Reviewed runtime patch ingest gate contract is ready for review only: keep "
            "reviewed_runtime_patch_exists=false, repo_side_review_state_updated=false, "
            "and runtime_enablement_allowed=false. The locked reviewer record "
            "identity/path and validator/signoff contract are explicit, but a future "
            "manual ingest review still cannot mark the patch as reviewed until the "
            "reviewer-signed JSON is supplied at the locked handoff path, validated "
            "against the locked contract, and separately approved for repo-side review "
            "state update."
        )
    else:
        recommended_next_step = (
            "run_separate_repo_state_review_marking_without_runtime_enablement"
        )
        handoff_recommendation = (
            "Reviewed runtime patch ingest gate contract and its future prerequisites "
            "are satisfied, but this artifact remains review-only and still does not "
            "perform ingest. A separate manual review may mark "
            "reviewed_runtime_patch_exists=true in repo-side review state while leaving "
            "runtime_enablement_allowed=false and preserving the post-ingest blocked "
            "gate set."
        )

    required_reviewer_statement_ids = (
        collection_required_statement_ids
        or validator_required_statement_ids
        or signoff_bundle_statement_ids
    )
    guard_id = (
        runtime_patch_code_status.get("guard_id")
        or runtime_patch_signoff_bundle.get("guard_id")
        or None
    )
    payload_id = (
        runtime_patch_code_status.get("payload_id")
        or runtime_patch_signoff_bundle.get("payload_id")
        or None
    )

    return {
        "metadata": {
            "source": REVIEWED_RUNTIME_PATCH_INGEST_GATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_reviewed_runtime_patch_ingest_gate_contract_not_actual_ingest"
            ),
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "paths": {
            "project_root": str(project_root),
            "signoff_record_validator": _display_path(
                project_root, signoff_record_validator_resolved
            ),
            "reviewer_record_collection": _display_path(
                project_root, reviewer_record_collection_resolved
            ),
            "runtime_patch_status": _display_path(
                project_root, runtime_patch_status_resolved
            ),
            "runtime_patch_signoff_bundle": _display_path(
                project_root, runtime_patch_signoff_bundle_resolved
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "reviewed_runtime_patch_ingest_gate_ready": bool(
                reviewed_runtime_patch_ingest_gate_ready
            ),
            "future_review_state_marking_prerequisites_met": bool(
                future_review_state_marking_prerequisites_met
            ),
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "current_phase": "review_only_ingest_contract_only",
            "missing_prerequisite_gate_ids": missing_prerequisite_gate_ids,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "reviewed_runtime_patch_ingest_gate": {
            "repo_side_review_state_target": {
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": record_identity,
                "record_type": record_type,
                "scope": scope,
                "guard_id": guard_id,
                "payload_id": payload_id,
                "current_field_value": False,
                "future_manual_ingest_review_may_mark_true": True,
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": handoff_format,
                "handoff_dir": handoff_dir,
                "handoff_path_shape": handoff_path_shape,
                "handoff_filename_tokens": handoff_filename_tokens,
                "detail": str(expected_handoff.get("detail") or ""),
            },
            "expected_review_input": {
                "collection_mode": str(
                    expected_collection_source.get("collection_mode") or ""
                ),
                "collection_phase": str(
                    expected_collection_source.get("collection_phase") or ""
                ),
                "source_artifact_chain": _string_list(
                    expected_collection_source.get("source_artifact_chain")
                ),
                "base_payload_template": dict(base_payload_template),
            },
            "ingest_review_contract": {
                "validator_target": str(
                    signoff_record_validator.get("validator_target") or ""
                ),
                "required_record_fields": [
                    dict(entry) for entry in collection_required_record_fields
                ],
                "required_reviewer_statement_ids": list(
                    required_reviewer_statement_ids
                ),
                "current_still_blocked_gate_ids": list(current_still_blocked_gate_ids),
                "post_ingest_still_blocked_gate_ids": list(
                    post_ingest_still_blocked_gate_ids
                ),
                "runtime_enablement_allowed_after_ingest_review": False,
                "detail": INGEST_REVIEW_DETAIL,
            },
            "actual_record_state": {
                "reviewer_signed_record_provided": False,
                "record_validation_completed": False,
                "record_validation_status": "not_run",
                "repo_side_review_state_updated": False,
                "ingest_review_status": "not_run",
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "detail": NO_ACTUAL_RECORD_DETAIL,
            },
            "ingest_gate_notice": INGEST_GATE_NOTICE,
            "recommended_manual_next_step": (
                "Have a reviewer place the completed JSON at the locked handoff path, "
                "manually validate it against signoff_record_validator.validator_rules, "
                "then run a separate ingest review that may mark reviewed_runtime_patch_exists=true "
                "in repo-side review state while keeping runtime_enablement_allowed=false."
            ),
        },
        "still_blocked_gate_ids": list(current_still_blocked_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    ingest_gate = _mapping(report.get("reviewed_runtime_patch_ingest_gate"))
    review_target = _mapping(ingest_gate.get("repo_side_review_state_target"))
    handoff = _mapping(ingest_gate.get("locked_reviewer_record_handoff"))
    expected_review_input = _mapping(ingest_gate.get("expected_review_input"))
    ingest_review_contract = _mapping(ingest_gate.get("ingest_review_contract"))
    actual_record_state = _mapping(ingest_gate.get("actual_record_state"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Reviewed Runtime Patch Ingest Gate",
        "",
        f"- Ingest gate ready: `{status.get('reviewed_runtime_patch_ingest_gate_ready')}`",
        f"- Future review-state marking prerequisites met: `{status.get('future_review_state_marking_prerequisites_met')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Current phase: `{status.get('current_phase')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Missing prerequisite gate ids: `{', '.join(_string_list(status.get('missing_prerequisite_gate_ids'))) or '(none)'}`",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Ingest gate notice: {ingest_gate.get('ingest_gate_notice')}",
        "",
        "## Repo-Side Review Target",
        "",
        f"- Review state kind: `{review_target.get('review_state_kind')}`",
        f"- Tracked field: `{review_target.get('tracked_field')}`",
        f"- Record identity: `{review_target.get('record_identity')}`",
        f"- Record type: `{review_target.get('record_type')}`",
        f"- Scope: `{review_target.get('scope')}`",
        f"- Guard id: `{review_target.get('guard_id')}`",
        f"- Payload id: `{review_target.get('payload_id')}`",
        f"- Current field value: `{review_target.get('current_field_value')}`",
        f"- Future manual ingest review may mark true: `{review_target.get('future_manual_ingest_review_may_mark_true')}`",
        "",
        "## Locked Reviewer Record Handoff",
        "",
        f"- Handoff format: `{handoff.get('handoff_format')}`",
        f"- Handoff dir: `{handoff.get('handoff_dir')}`",
        f"- Handoff path shape: `{handoff.get('handoff_path_shape')}`",
        f"- Filename tokens: `{', '.join(_string_list(handoff.get('handoff_filename_tokens'))) or '(none)'}`",
        f"- Detail: {handoff.get('detail')}",
        "",
        "## Expected Review Input",
        "",
        f"- Collection mode: `{expected_review_input.get('collection_mode')}`",
        f"- Collection phase: `{expected_review_input.get('collection_phase')}`",
        f"- Source artifact chain: `{', '.join(_string_list(expected_review_input.get('source_artifact_chain'))) or '(none)'}`",
        "",
        "## Future Mark-Reviewed Preconditions",
        "",
        "| Gate | Satisfied | Blocking | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for gate in list(report.get("gates", [])):
        if isinstance(gate, Mapping):
            lines.append(
                f"| {_markdown_cell(gate.get('gate_id'))} | "
                f"{_markdown_cell(gate.get('satisfied'))} | "
                f"{_markdown_cell(gate.get('blocking'))} | "
                f"{_markdown_cell(gate.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Ingest Review Contract",
            "",
            f"- Validator target: `{ingest_review_contract.get('validator_target')}`",
            f"- Required reviewer statement ids: `{', '.join(_string_list(ingest_review_contract.get('required_reviewer_statement_ids'))) or '(none)'}`",
            f"- Current still blocked gate ids: `{', '.join(_string_list(ingest_review_contract.get('current_still_blocked_gate_ids'))) or '(none)'}`",
            f"- Post-ingest still blocked gate ids: `{', '.join(_string_list(ingest_review_contract.get('post_ingest_still_blocked_gate_ids'))) or '(none)'}`",
            f"- Runtime enablement allowed after ingest review: `{ingest_review_contract.get('runtime_enablement_allowed_after_ingest_review')}`",
            f"- Detail: {ingest_review_contract.get('detail')}",
            "",
            "## Actual Record State",
            "",
            f"- Reviewer signed record provided: `{actual_record_state.get('reviewer_signed_record_provided')}`",
            f"- Record validation completed: `{actual_record_state.get('record_validation_completed')}`",
            f"- Record validation status: `{actual_record_state.get('record_validation_status')}`",
            f"- Repo-side review state updated: `{actual_record_state.get('repo_side_review_state_updated')}`",
            f"- Ingest review status: `{actual_record_state.get('ingest_review_status')}`",
            f"- Detail: {actual_record_state.get('detail')}",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    ingest_gate = _mapping(report.get("reviewed_runtime_patch_ingest_gate"))
    review_target = _mapping(ingest_gate.get("repo_side_review_state_target"))
    handoff = _mapping(ingest_gate.get("locked_reviewer_record_handoff"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain reviewed runtime patch ingest gate",
            f"reviewed_runtime_patch_ingest_gate_ready={status.get('reviewed_runtime_patch_ingest_gate_ready')}",
            "future_review_state_marking_prerequisites_met="
            + str(status.get("future_review_state_marking_prerequisites_met")),
            f"repo_side_review_state_updated={status.get('repo_side_review_state_updated')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"record_identity={review_target.get('record_identity')}",
            f"handoff_path_shape={handoff.get('handoff_path_shape')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_reviewed_runtime_patch_ingest_gate",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _field_names(entries: list[Mapping[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in entries:
        field = str(entry.get("field") or "").strip()
        if field:
            names.append(field)
    return names


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not path.exists():
            return None, f"missing:{path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None, "json root is not an object"
        return payload, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[Mapping[str, Any]] = []
    for entry in value:
        if isinstance(entry, Mapping):
            result.append(entry)
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

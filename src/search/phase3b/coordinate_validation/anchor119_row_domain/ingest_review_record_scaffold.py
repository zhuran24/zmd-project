from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

REVIEWED_RUNTIME_PATCH_INGEST_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_v1"
)
REVIEWER_RECORD_COLLECTION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1"
)
SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1"
)
INGEST_REVIEW_RECORD_TYPE = "reviewed_runtime_patch_ingest_review_record_v0"
DEFAULT_REVIEWED_RUNTIME_PATCH_INGEST_GATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_20260424/"
    "anchor119_row_domain_reviewed_runtime_patch_ingest_gate.json"
)
DEFAULT_REVIEWER_RECORD_COLLECTION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
    "anchor119_row_domain_reviewer_record_collection.json"
)
DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_20260424/"
    "anchor119_row_domain_signoff_record_validator.json"
)
SCAFFOLD_NOTICE = (
    "Future human ingest-review record scaffold only. No actual ingest review has been "
    "performed, reviewed_runtime_patch_exists remains false, repo-side review state is "
    "unchanged, and runtime enablement remains disallowed/default-off."
)
NO_ACTUAL_INGEST_REVIEW_DETAIL = (
    "No actual human ingest review record has been completed. reviewed_runtime_patch_exists "
    "remains false, repo-side review state is unchanged, and runtime enablement remains "
    "disallowed."
)
PRESERVED_BLOCKED_GATES_DETAIL = (
    "This scaffold preserves both the current still-blocked gates and the post-ingest "
    "blocked gates that must remain after any future human review decides whether repo-side "
    "review state may mark the runtime patch as reviewed."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold(
    project_root: Path,
    *,
    reviewed_runtime_patch_ingest_gate_path: Optional[Path] = None,
    reviewer_record_collection_path: Optional[Path] = None,
    signoff_record_validator_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    reviewed_runtime_patch_ingest_gate_resolved = _resolve_path(
        project_root,
        reviewed_runtime_patch_ingest_gate_path
        if reviewed_runtime_patch_ingest_gate_path is not None
        else DEFAULT_REVIEWED_RUNTIME_PATCH_INGEST_GATE_PATH,
    )
    reviewer_record_collection_resolved = _resolve_path(
        project_root,
        reviewer_record_collection_path
        if reviewer_record_collection_path is not None
        else DEFAULT_REVIEWER_RECORD_COLLECTION_PATH,
    )
    signoff_record_validator_resolved = _resolve_path(
        project_root,
        signoff_record_validator_path
        if signoff_record_validator_path is not None
        else DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH,
    )

    ingest_gate_report, ingest_gate_error = _load_json_mapping(
        reviewed_runtime_patch_ingest_gate_resolved
    )
    reviewer_record_collection_report, reviewer_record_collection_error = _load_json_mapping(
        reviewer_record_collection_resolved
    )
    signoff_record_validator_report, signoff_record_validator_error = _load_json_mapping(
        signoff_record_validator_resolved
    )

    ingest_gate_meta = (
        _mapping(ingest_gate_report.get("metadata")) if ingest_gate_report else {}
    )
    ingest_gate_status = (
        _mapping(ingest_gate_report.get("status")) if ingest_gate_report else {}
    )
    reviewed_runtime_patch_ingest_gate = (
        _mapping(ingest_gate_report.get("reviewed_runtime_patch_ingest_gate"))
        if ingest_gate_report
        else {}
    )
    reviewer_meta = (
        _mapping(reviewer_record_collection_report.get("metadata"))
        if reviewer_record_collection_report
        else {}
    )
    reviewer_status = (
        _mapping(reviewer_record_collection_report.get("status"))
        if reviewer_record_collection_report
        else {}
    )
    reviewer_record_collection = (
        _mapping(reviewer_record_collection_report.get("reviewer_record_collection"))
        if reviewer_record_collection_report
        else {}
    )
    validator_meta = (
        _mapping(signoff_record_validator_report.get("metadata"))
        if signoff_record_validator_report
        else {}
    )
    validator_status = (
        _mapping(signoff_record_validator_report.get("status"))
        if signoff_record_validator_report
        else {}
    )
    signoff_record_validator = (
        _mapping(signoff_record_validator_report.get("signoff_record_validator"))
        if signoff_record_validator_report
        else {}
    )
    candidate = (
        _mapping(ingest_gate_report.get("candidate"))
        if ingest_gate_report
        else _mapping(reviewer_record_collection_report.get("candidate"))
        if reviewer_record_collection_report
        else _mapping(signoff_record_validator_report.get("candidate"))
        if signoff_record_validator_report
        else {}
    )

    ingest_gate_present = bool(
        ingest_gate_report is not None
        and ingest_gate_error is None
        and ingest_gate_meta.get("source") == REVIEWED_RUNTIME_PATCH_INGEST_GATE_SOURCE
    )
    reviewer_record_collection_present = bool(
        reviewer_record_collection_report is not None
        and reviewer_record_collection_error is None
        and reviewer_meta.get("source") == REVIEWER_RECORD_COLLECTION_SOURCE
    )
    signoff_record_validator_present = bool(
        signoff_record_validator_report is not None
        and signoff_record_validator_error is None
        and validator_meta.get("source") == SIGNOFF_RECORD_VALIDATOR_SOURCE
    )

    ingest_gate_ready = bool(
        ingest_gate_status.get("reviewed_runtime_patch_ingest_gate_ready", False)
    )
    reviewer_record_collection_ready = bool(
        reviewer_status.get("reviewer_record_collection_ready", False)
    )
    signoff_record_validator_ready = bool(
        validator_status.get("signoff_record_validator_ready", False)
    )
    upstream_reviewed_runtime_patch_exists = bool(
        ingest_gate_status.get("reviewed_runtime_patch_exists", False)
        or reviewer_status.get("reviewed_runtime_patch_exists", False)
        or validator_status.get("reviewed_runtime_patch_exists", False)
    )
    upstream_runtime_enablement_allowed = bool(
        ingest_gate_status.get("runtime_enablement_allowed", False)
        or reviewer_status.get("runtime_enablement_allowed", False)
        or validator_status.get("runtime_enablement_allowed", False)
    )

    locked_target_review_state = _mapping(
        reviewed_runtime_patch_ingest_gate.get("repo_side_review_state_target")
    )
    locked_handoff = _mapping(
        reviewed_runtime_patch_ingest_gate.get("locked_reviewer_record_handoff")
    )
    ingest_review_contract = _mapping(
        reviewed_runtime_patch_ingest_gate.get("ingest_review_contract")
    )
    collection_target_identity = _mapping(
        reviewer_record_collection.get("target_record_identity")
    )
    collection_expected_source = _mapping(
        reviewer_record_collection.get("expected_collection_source")
    )
    collection_expected_handoff = _mapping(
        reviewer_record_collection.get("expected_handoff")
    )
    collection_preserved_contract = _mapping(
        reviewer_record_collection.get("preserved_contract")
    )
    validator_rules = _mapping(signoff_record_validator.get("validator_rules"))
    validator_expected_template_payload = _mapping(
        signoff_record_validator.get("expected_template_payload")
    )

    review_state_kind = (
        str(locked_target_review_state.get("review_state_kind") or "").strip()
        or "repo_side_review_state"
    )
    tracked_field = (
        str(locked_target_review_state.get("tracked_field") or "").strip()
        or "reviewed_runtime_patch_exists"
    )
    target_record_identity = (
        str(locked_target_review_state.get("record_identity") or "").strip()
        or str(collection_target_identity.get("record_identity") or "").strip()
    )
    target_record_type = (
        str(locked_target_review_state.get("record_type") or "").strip()
        or str(collection_target_identity.get("record_type") or "").strip()
        or str(signoff_record_validator.get("target_record_type") or "").strip()
    )
    scope = (
        str(locked_target_review_state.get("scope") or "").strip()
        or str(collection_target_identity.get("scope") or "").strip()
        or str(signoff_record_validator.get("scope") or "").strip()
    )
    current_field_value = bool(locked_target_review_state.get("current_field_value", False))
    handoff_format = (
        str(locked_handoff.get("handoff_format") or "").strip()
        or str(collection_expected_handoff.get("handoff_format") or "").strip()
    )
    handoff_dir = (
        str(locked_handoff.get("handoff_dir") or "").strip()
        or str(collection_expected_handoff.get("handoff_dir") or "").strip()
    )
    handoff_path_shape = (
        str(locked_handoff.get("handoff_path_shape") or "").strip()
        or str(collection_expected_handoff.get("handoff_path_shape") or "").strip()
    )
    handoff_filename_tokens = _string_list(
        locked_handoff.get("handoff_filename_tokens")
    ) or _string_list(collection_expected_handoff.get("handoff_filename_tokens"))

    expected_reviewer_record_template = _mapping(
        collection_expected_source.get("base_payload_template")
    ) or validator_expected_template_payload
    validator_target = (
        str(ingest_review_contract.get("validator_target") or "").strip()
        or str(signoff_record_validator.get("validator_target") or "").strip()
    )
    required_record_fields = _mapping_list(
        ingest_review_contract.get("required_record_fields")
    )
    if not required_record_fields:
        required_record_fields = _mapping_list(
            collection_preserved_contract.get("required_record_fields")
        )
    if not required_record_fields:
        required_record_fields = _mapping_list(validator_rules.get("required_fields"))

    required_reviewer_statement_ids = _string_list(
        ingest_review_contract.get("required_reviewer_statement_ids")
    )
    if not required_reviewer_statement_ids:
        required_reviewer_statement_ids = _string_list(
            collection_preserved_contract.get("required_reviewer_statement_ids")
        )
    if not required_reviewer_statement_ids:
        required_reviewer_statement_ids = _string_list(
            signoff_record_validator.get("required_reviewer_statement_ids")
        )

    current_still_blocked_gate_ids = _string_list(
        ingest_review_contract.get("current_still_blocked_gate_ids")
    )
    if not current_still_blocked_gate_ids:
        current_still_blocked_gate_ids = _string_list(
            collection_preserved_contract.get("still_blocked_gate_ids")
        )
    if not current_still_blocked_gate_ids:
        current_still_blocked_gate_ids = _string_list(
            _mapping(validator_rules.get("still_blocked_gate_ids")).get("required_ids")
        )

    post_ingest_still_blocked_gate_ids = _string_list(
        ingest_review_contract.get("post_ingest_still_blocked_gate_ids")
    )
    missing_prerequisite_gate_ids = _string_list(
        ingest_gate_status.get("missing_prerequisite_gate_ids")
    )
    gate_details_by_id = _gate_detail_map(ingest_gate_report)

    target_review_state_defined = bool(
        review_state_kind
        and tracked_field
        and target_record_identity
        and target_record_type
        and scope
    )
    locked_handoff_contract_defined = bool(
        handoff_format == "json"
        and handoff_dir
        and handoff_path_shape
        and handoff_filename_tokens
    )
    validator_contract_available = bool(
        validator_target
        and _mapping_list(validator_rules.get("required_fields"))
        and _mapping(validator_rules.get("agreed_statement_ids"))
        and _mapping(validator_rules.get("still_blocked_gate_ids"))
    )
    reviewer_record_template_aligned = bool(
        target_record_type
        and scope
        and str(expected_reviewer_record_template.get("record_type") or "").strip()
        == target_record_type
        and str(validator_expected_template_payload.get("record_type") or "").strip()
        == target_record_type
        and str(expected_reviewer_record_template.get("scope") or "").strip() == scope
        and str(validator_expected_template_payload.get("scope") or "").strip() == scope
    )
    required_record_fields_preserved = bool(required_record_fields)
    required_reviewer_statement_ids_preserved = bool(required_reviewer_statement_ids)
    current_still_blocked_gate_ids_preserved = bool(current_still_blocked_gate_ids)
    post_ingest_still_blocked_gate_ids_defined = bool(post_ingest_still_blocked_gate_ids)
    future_manual_review_prerequisite_gate_ids_captured = bool(missing_prerequisite_gate_ids)

    required_review_conclusions = _build_required_review_conclusions(
        missing_prerequisite_gate_ids,
        gate_details_by_id=gate_details_by_id,
        review_state_kind=review_state_kind,
        tracked_field=tracked_field,
        current_field_value=current_field_value,
        post_ingest_still_blocked_gate_ids=post_ingest_still_blocked_gate_ids,
    )
    required_review_conclusions_defined = bool(required_review_conclusions)

    ingest_review_record_template = _build_ingest_review_record_template(
        review_state_kind=review_state_kind,
        tracked_field=tracked_field,
        target_record_identity=target_record_identity,
        target_record_type=target_record_type,
        scope=scope,
        handoff_path_shape=handoff_path_shape,
        validator_target=validator_target,
        required_reviewer_statement_ids=required_reviewer_statement_ids,
        required_review_conclusions=required_review_conclusions,
        current_still_blocked_gate_ids=current_still_blocked_gate_ids,
        post_ingest_still_blocked_gate_ids=post_ingest_still_blocked_gate_ids,
    )
    ingest_review_record_template_present = bool(ingest_review_record_template)
    default_off_retained = bool(
        ingest_gate_present
        and reviewer_record_collection_present
        and signoff_record_validator_present
        and bool(ingest_gate_meta.get("default_off", False))
        and bool(reviewer_meta.get("default_off", False))
        and bool(validator_meta.get("default_off", False))
        and not upstream_runtime_enablement_allowed
    )

    carry_forward_gate_entries = _ensure_gate_entries(
        _merge_gate_entries(
            _blocked_gate_entries(reviewer_record_collection_report),
            _blocked_gate_entries(signoff_record_validator_report),
        ),
        current_still_blocked_gate_ids=current_still_blocked_gate_ids,
    )

    checks = [
        _check(
            "reviewed_runtime_patch_ingest_gate_present",
            "pass" if ingest_gate_present else "fail",
            "reviewed runtime patch ingest gate loaded"
            if ingest_gate_present
            else ingest_gate_error
            or (
                f"unexpected_source:{ingest_gate_meta.get('source')}"
                if ingest_gate_report is not None
                else f"missing:{_display_path(project_root, reviewed_runtime_patch_ingest_gate_resolved)}"
            ),
        ),
        _check(
            "reviewer_record_collection_present",
            "pass" if reviewer_record_collection_present else "fail",
            "reviewer record collection loaded"
            if reviewer_record_collection_present
            else reviewer_record_collection_error
            or (
                f"unexpected_source:{reviewer_meta.get('source')}"
                if reviewer_record_collection_report is not None
                else f"missing:{_display_path(project_root, reviewer_record_collection_resolved)}"
            ),
        ),
        _check(
            "signoff_record_validator_present",
            "pass" if signoff_record_validator_present else "fail",
            "signoff record validator loaded"
            if signoff_record_validator_present
            else signoff_record_validator_error
            or (
                f"unexpected_source:{validator_meta.get('source')}"
                if signoff_record_validator_report is not None
                else f"missing:{_display_path(project_root, signoff_record_validator_resolved)}"
            ),
        ),
        _check(
            "reviewed_runtime_patch_ingest_gate_ready",
            "pass" if ingest_gate_ready else "fail",
            str(ingest_gate_ready),
        ),
        _check(
            "reviewer_record_collection_ready",
            "pass" if reviewer_record_collection_ready else "fail",
            str(reviewer_record_collection_ready),
        ),
        _check(
            "signoff_record_validator_ready",
            "pass" if signoff_record_validator_ready else "fail",
            str(signoff_record_validator_ready),
        ),
        _check(
            "target_review_state_defined",
            "pass" if target_review_state_defined else "fail",
            target_record_identity or "missing",
        ),
        _check(
            "locked_handoff_contract_defined",
            "pass" if locked_handoff_contract_defined else "fail",
            handoff_path_shape or "missing",
        ),
        _check(
            "validator_contract_available",
            "pass" if validator_contract_available else "fail",
            validator_target or "missing",
        ),
        _check(
            "reviewer_record_template_aligned",
            "pass" if reviewer_record_template_aligned else "fail",
            "ingest gate review input, reviewer collection payload, and validator template are aligned"
            if reviewer_record_template_aligned
            else "record_type_or_scope_mismatch_between_ingest_gate_collection_and_validator",
        ),
        _check(
            "required_record_fields_preserved",
            "pass" if required_record_fields_preserved else "fail",
            ",".join(
                str(entry.get("field"))
                for entry in required_record_fields
                if entry.get("field")
            )
            if required_record_fields_preserved
            else "missing",
        ),
        _check(
            "required_reviewer_statement_ids_preserved",
            "pass" if required_reviewer_statement_ids_preserved else "fail",
            ",".join(required_reviewer_statement_ids)
            if required_reviewer_statement_ids_preserved
            else "missing",
        ),
        _check(
            "current_still_blocked_gate_ids_preserved",
            "pass" if current_still_blocked_gate_ids_preserved else "fail",
            ",".join(current_still_blocked_gate_ids)
            if current_still_blocked_gate_ids_preserved
            else "missing",
        ),
        _check(
            "post_ingest_still_blocked_gate_ids_defined",
            "pass" if post_ingest_still_blocked_gate_ids_defined else "fail",
            ",".join(post_ingest_still_blocked_gate_ids)
            if post_ingest_still_blocked_gate_ids_defined
            else "missing",
        ),
        _check(
            "future_manual_review_prerequisite_gate_ids_captured",
            "pass" if future_manual_review_prerequisite_gate_ids_captured else "fail",
            ",".join(missing_prerequisite_gate_ids)
            if future_manual_review_prerequisite_gate_ids_captured
            else "missing",
        ),
        _check(
            "required_review_conclusions_defined",
            "pass" if required_review_conclusions_defined else "fail",
            ",".join(
                str(entry.get("conclusion_id"))
                for entry in required_review_conclusions
                if entry.get("conclusion_id")
            )
            if required_review_conclusions_defined
            else "missing",
        ),
        _check(
            "ingest_review_record_template_present",
            "pass" if ingest_review_record_template_present else "fail",
            "pending ingest-review record template present"
            if ingest_review_record_template_present
            else "missing",
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
    ]

    ingest_review_record_scaffold_ready = all(
        check["status"] == "pass" for check in checks
    )

    gates = [
        _gate(
            "reviewed_runtime_patch_ingest_gate_ready",
            ingest_gate_ready,
            True,
            "This scaffold depends on the reviewed runtime patch ingest gate already being ready.",
        ),
        _gate(
            "reviewer_record_collection_ready",
            reviewer_record_collection_ready,
            True,
            "This scaffold depends on the reviewer-record collection contract already being ready.",
        ),
        _gate(
            "signoff_record_validator_ready",
            signoff_record_validator_ready,
            True,
            "This scaffold depends on the signoff record validator contract already being ready.",
        ),
        _gate(
            "locked_target_review_state_defined",
            target_review_state_defined,
            True,
            "The locked repo-side review-state target identity, field, and scope must stay explicit.",
        ),
        _gate(
            "locked_reviewer_record_handoff_defined",
            locked_handoff_contract_defined,
            True,
            "The locked reviewer-record handoff path must remain explicit for any future manual ingest review.",
        ),
        _gate(
            "locked_validator_contract_available",
            validator_contract_available and reviewer_record_template_aligned,
            True,
            "The future manual ingest review depends on an aligned reviewer-record template and validator contract.",
        ),
        _gate(
            "future_manual_review_prerequisite_gate_ids_captured",
            future_manual_review_prerequisite_gate_ids_captured,
            True,
            "The scaffold must preserve which future manual-review prerequisite gates still need a human decision.",
        ),
        _gate(
            "required_review_conclusions_defined",
            required_review_conclusions_defined,
            True,
            "The scaffold must carry the required future review conclusions that a human will fill later.",
        ),
        _gate(
            "ingest_review_record_template_present",
            ingest_review_record_template_present,
            True,
            "The scaffold must expose a pending ingest-review record payload/template without performing the review.",
        ),
        _gate(
            "default_off_retained_for_ingest_review_record_scaffold",
            default_off_retained,
            True,
            "This scaffold remains explicit default-off and does not allow runtime enablement.",
        ),
        _gate(
            "actual_manual_ingest_review_record_completed",
            False,
            False,
            NO_ACTUAL_INGEST_REVIEW_DETAIL,
        ),
        _gate(
            "review_only_scaffold_not_applied",
            True,
            False,
            SCAFFOLD_NOTICE,
        ),
    ]
    gates.extend(carry_forward_gate_entries)

    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    if ingest_review_record_scaffold_ready:
        recommended_next_step = (
            "manually_complete_ingest_review_record_then_run_separate_repo_side_review_decision_without_enablement"
        )
        handoff_recommendation = (
            "Ingest-review record scaffold is ready: hand the scaffolded payload to a human "
            "reviewer, have them fill the pending review conclusions against the locked target "
            "review-state identity, reviewer-record handoff path, and validator contract, and "
            "keep reviewed_runtime_patch_exists=false plus runtime_enablement_allowed=false "
            "until a later manual ingest review is completed and separately applied."
        )
    else:
        recommended_next_step = "repair_ingest_review_record_scaffold_inputs"
        handoff_recommendation = (
            "Ingest-review record scaffold is blocked; repair the missing reviewed-runtime-patch "
            "ingest-gate, reviewer-record collection, or signoff-record validator prerequisites "
            "before asking a human reviewer to fill the future ingest-review scaffold."
        )

    return {
        "metadata": {
            "source": INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_ingest_review_record_scaffold_not_actual_ingest_review"
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
            "reviewed_runtime_patch_ingest_gate": _display_path(
                project_root, reviewed_runtime_patch_ingest_gate_resolved
            ),
            "reviewer_record_collection": _display_path(
                project_root, reviewer_record_collection_resolved
            ),
            "signoff_record_validator": _display_path(
                project_root, signoff_record_validator_resolved
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "ingest_review_record_scaffold_ready": bool(
                ingest_review_record_scaffold_ready
            ),
            "manual_ingest_review_record_completed": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "ingest_review_record_scaffold": {
            "record_type": INGEST_REVIEW_RECORD_TYPE,
            "locked_target_review_state": {
                "review_state_kind": review_state_kind,
                "tracked_field": tracked_field,
                "record_identity": target_record_identity,
                "record_type": target_record_type,
                "scope": scope,
                "current_field_value": current_field_value,
                "proposed_field_value_if_approved": True,
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": handoff_format,
                "handoff_dir": handoff_dir,
                "handoff_path_shape": handoff_path_shape,
                "handoff_filename_tokens": list(handoff_filename_tokens),
                "detail": str(
                    locked_handoff.get("detail")
                    or collection_expected_handoff.get("detail")
                    or ""
                ),
            },
            "validator_contract_reference": {
                "validator_target": validator_target,
                "required_record_fields": [dict(entry) for entry in required_record_fields],
                "required_reviewer_statement_ids": list(required_reviewer_statement_ids),
                "expected_reviewer_record_template": dict(
                    validator_expected_template_payload or expected_reviewer_record_template
                ),
                "required_validator_rules": {
                    "agreed_statement_ids": dict(
                        _mapping(validator_rules.get("agreed_statement_ids"))
                    ),
                    "still_blocked_gate_ids": dict(
                        _mapping(validator_rules.get("still_blocked_gate_ids"))
                    ),
                },
            },
            "required_review_conclusions": [
                dict(entry) for entry in required_review_conclusions
            ],
            "preserved_blocked_gates": {
                "current_still_blocked_gate_ids": list(current_still_blocked_gate_ids),
                "post_ingest_still_blocked_gate_ids": list(
                    post_ingest_still_blocked_gate_ids
                ),
                "runtime_enablement_allowed_after_review": False,
                "detail": PRESERVED_BLOCKED_GATES_DETAIL,
            },
            "ingest_review_record_template": ingest_review_record_template,
            "scaffold_notice": SCAFFOLD_NOTICE,
            "recommended_manual_next_step": (
                "Have a human reviewer validate the completed reviewer-signed JSON against "
                "the locked contract, fill this ingest-review scaffold with a manual decision "
                "about whether repo-side review state may mark reviewed_runtime_patch_exists=true, "
                "and keep runtime_enablement_allowed=false plus the post-ingest blocked gates "
                "unchanged even if that future review approves the repo-side state update."
            ),
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    scaffold = _mapping(report.get("ingest_review_record_scaffold"))
    target = _mapping(scaffold.get("locked_target_review_state"))
    handoff = _mapping(scaffold.get("locked_reviewer_record_handoff"))
    validator_contract = _mapping(scaffold.get("validator_contract_reference"))
    blocked_gates = _mapping(scaffold.get("preserved_blocked_gates"))
    template = _mapping(scaffold.get("ingest_review_record_template"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Ingest Review Record Scaffold",
        "",
        f"- Ingest review record scaffold ready: `{status.get('ingest_review_record_scaffold_ready')}`",
        f"- Manual ingest review record completed: `{status.get('manual_ingest_review_record_completed')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Scaffold notice: {scaffold.get('scaffold_notice')}",
        "",
        "## Locked Target Review State",
        "",
        f"- Review state kind: `{target.get('review_state_kind')}`",
        f"- Tracked field: `{target.get('tracked_field')}`",
        f"- Record identity: `{target.get('record_identity')}`",
        f"- Record type: `{target.get('record_type')}`",
        f"- Scope: `{target.get('scope')}`",
        f"- Current field value: `{target.get('current_field_value')}`",
        f"- Proposed field value if approved later: `{target.get('proposed_field_value_if_approved')}`",
        "",
        "## Locked Reviewer Record Handoff",
        "",
        f"- Handoff format: `{handoff.get('handoff_format')}`",
        f"- Handoff dir: `{handoff.get('handoff_dir')}`",
        f"- Handoff path shape: `{handoff.get('handoff_path_shape')}`",
        f"- Filename tokens: `{', '.join(_string_list(handoff.get('handoff_filename_tokens'))) or '(none)'}`",
        f"- Detail: {handoff.get('detail')}",
        "",
        "## Validator Contract Reference",
        "",
        f"- Validator target: `{validator_contract.get('validator_target')}`",
        f"- Required reviewer statement ids: `{', '.join(_string_list(validator_contract.get('required_reviewer_statement_ids'))) or '(none)'}`",
        "",
        "## Required Record Fields",
        "",
        "| Field | Required | Template value | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(validator_contract.get("required_record_fields", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(entry.get('template_value'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Required Review Conclusions",
            "",
            "| Conclusion | Required | Template value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(scaffold.get("required_review_conclusions", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('conclusion_id'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(entry.get('template_value'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Preserved Blocked Gates",
            "",
            f"- Current still blocked gate ids: `{', '.join(_string_list(blocked_gates.get('current_still_blocked_gate_ids'))) or '(none)'}`",
            f"- Post-ingest still blocked gate ids: `{', '.join(_string_list(blocked_gates.get('post_ingest_still_blocked_gate_ids'))) or '(none)'}`",
            f"- Runtime enablement allowed after review: `{blocked_gates.get('runtime_enablement_allowed_after_review')}`",
            f"- Detail: {blocked_gates.get('detail')}",
            "",
            "## Ingest Review Record Template",
            "",
            f"- Record type: `{template.get('record_type')}`",
            f"- Review decision: `{template.get('review_decision')}`",
            f"- Reviewer record validation status: `{template.get('reviewer_record_validation_status')}`",
            f"- Required review conclusion ids: `{', '.join(_string_list(template.get('required_review_conclusion_ids'))) or '(none)'}`",
            "",
            "## Gates",
            "",
            "| Gate | Satisfied | Blocking | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
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


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    scaffold = _mapping(report.get("ingest_review_record_scaffold"))
    target = _mapping(scaffold.get("locked_target_review_state"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain ingest review record scaffold",
            "ingest_review_record_scaffold_ready="
            + str(status.get("ingest_review_record_scaffold_ready")),
            "manual_ingest_review_record_completed="
            + str(status.get("manual_ingest_review_record_completed")),
            "repo_side_review_state_updated="
            + str(status.get("repo_side_review_state_updated")),
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            f"record_identity={target.get('record_identity')}",
            f"tracked_field={target.get('tracked_field')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_ingest_review_record_scaffold",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_required_review_conclusions(
    missing_prerequisite_gate_ids: list[str],
    *,
    gate_details_by_id: Mapping[str, str],
    review_state_kind: str,
    tracked_field: str,
    current_field_value: bool,
    post_ingest_still_blocked_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    conclusions: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for gate_id in missing_prerequisite_gate_ids:
        gate_id_text = str(gate_id).strip()
        if not gate_id_text or gate_id_text in seen:
            continue
        conclusions.append(
            {
                "conclusion_id": gate_id_text,
                "required": True,
                "template_value": "pending",
                "detail": gate_details_by_id.get(
                    gate_id_text,
                    "Future human review must resolve this ingest-review prerequisite explicitly.",
                ),
            }
        )
        seen.add(gate_id_text)
    for conclusion_id, detail in [
        (
            "repo_side_review_state_may_mark_reviewed_runtime_patch",
            f"Human review decides whether {review_state_kind}.{tracked_field} may change "
            f"from `{current_field_value}` to `True` for the locked target record identity.",
        ),
        (
            "runtime_enablement_remains_blocked_after_review",
            "Any future approval must still leave runtime_enablement_allowed=false.",
        ),
        (
            "post_ingest_still_blocked_gate_ids_preserved",
            "Any future approval must preserve these post-ingest blocked gates: "
            + ",".join(post_ingest_still_blocked_gate_ids),
        ),
    ]:
        if conclusion_id in seen:
            continue
        conclusions.append(
            {
                "conclusion_id": conclusion_id,
                "required": True,
                "template_value": "pending",
                "detail": detail,
            }
        )
        seen.add(conclusion_id)
    return conclusions


def _build_ingest_review_record_template(
    *,
    review_state_kind: str,
    tracked_field: str,
    target_record_identity: str,
    target_record_type: str,
    scope: str,
    handoff_path_shape: str,
    validator_target: str,
    required_reviewer_statement_ids: list[str],
    required_review_conclusions: list[Mapping[str, Any]],
    current_still_blocked_gate_ids: list[str],
    post_ingest_still_blocked_gate_ids: list[str],
) -> Dict[str, Any]:
    if not (
        review_state_kind
        and tracked_field
        and target_record_identity
        and target_record_type
        and scope
        and handoff_path_shape
        and validator_target
        and required_review_conclusions
    ):
        return {}
    return {
        "record_type": INGEST_REVIEW_RECORD_TYPE,
        "review_state_kind": review_state_kind,
        "tracked_field": tracked_field,
        "target_record_identity": target_record_identity,
        "target_record_type": target_record_type,
        "scope": scope,
        "proposed_field_value_if_approved": True,
        "ingest_reviewer_id": "",
        "ingest_reviewed_at": "",
        "review_decision": "pending",
        "decision_notes": "",
        "reviewer_record_handoff_path": handoff_path_shape,
        "reviewer_record_validation_status": "pending_manual_validation",
        "validator_target": validator_target,
        "required_reviewer_statement_ids": list(required_reviewer_statement_ids),
        "required_review_conclusion_ids": [
            str(entry.get("conclusion_id"))
            for entry in required_review_conclusions
            if entry.get("conclusion_id")
        ],
        "review_conclusions": [
            {
                "conclusion_id": str(entry.get("conclusion_id")),
                "decision": "pending",
                "notes": "",
            }
            for entry in required_review_conclusions
            if entry.get("conclusion_id")
        ],
        "current_still_blocked_gate_ids": list(current_still_blocked_gate_ids),
        "post_ingest_still_blocked_gate_ids": list(post_ingest_still_blocked_gate_ids),
        "repo_side_review_state_updated": False,
        "reviewed_runtime_patch_exists": False,
        "runtime_enablement_allowed": False,
    }


def _blocked_gate_entries(report: Optional[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    if not report:
        return []
    entries: list[Dict[str, Any]] = []
    for gate in list(report.get("gates", [])):
        if not isinstance(gate, Mapping):
            continue
        gate_id = str(gate.get("gate_id") or "")
        if not gate_id:
            continue
        blocking = bool(gate.get("blocking"))
        satisfied = bool(gate.get("satisfied"))
        if blocking and not satisfied:
            entries.append(
                {
                    "gate_id": gate_id,
                    "satisfied": False,
                    "blocking": True,
                    "detail": str(gate.get("detail") or "carry-forward blocked gate"),
                }
            )
    return entries


def _merge_gate_entries(*gate_groups: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for gate_group in gate_groups:
        for gate in gate_group:
            gate_id = str(gate.get("gate_id") or "")
            if not gate_id or gate_id in seen:
                continue
            merged.append(
                {
                    "gate_id": gate_id,
                    "satisfied": bool(gate.get("satisfied")),
                    "blocking": bool(gate.get("blocking")),
                    "detail": str(gate.get("detail") or ""),
                }
            )
            seen.add(gate_id)
    return merged


def _ensure_gate_entries(
    entries: list[Dict[str, Any]], *, current_still_blocked_gate_ids: list[str]
) -> list[Dict[str, Any]]:
    seen = {str(entry.get("gate_id")) for entry in entries if entry.get("gate_id")}
    for gate_id in current_still_blocked_gate_ids:
        gate_id_text = str(gate_id).strip()
        if not gate_id_text or gate_id_text in seen:
            continue
        entries.append(
            {
                "gate_id": gate_id_text,
                "satisfied": False,
                "blocking": True,
                "detail": "Preserved still-blocked gate carried forward into the ingest-review scaffold.",
            }
        )
        seen.add(gate_id_text)
    return entries


def _gate_detail_map(report: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    details: Dict[str, str] = {}
    if not report:
        return details
    for gate in list(report.get("gates", [])):
        if not isinstance(gate, Mapping):
            continue
        gate_id = str(gate.get("gate_id") or "").strip()
        if gate_id and gate_id not in details:
            details[gate_id] = str(gate.get("detail") or "")
    return details


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


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


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

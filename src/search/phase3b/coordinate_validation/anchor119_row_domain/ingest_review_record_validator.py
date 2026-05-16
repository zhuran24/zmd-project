from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1"
)
REVIEWED_RUNTIME_PATCH_INGEST_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_v1"
)
SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_TARGET = "future_completed_ingest_review_record_payload"
DEFAULT_INGEST_REVIEW_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_20260424/"
    "anchor119_row_domain_ingest_review_record_scaffold.json"
)
DEFAULT_REVIEWED_RUNTIME_PATCH_INGEST_GATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_20260424/"
    "anchor119_row_domain_reviewed_runtime_patch_ingest_gate.json"
)
DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_20260424/"
    "anchor119_row_domain_signoff_record_validator.json"
)
VALIDATOR_NOTICE = (
    "Review-only/default-off validator. Supplying and even successfully validating a "
    "future human-completed ingest-review record payload does not update repo-side "
    "review state, does not set reviewed_runtime_patch_exists=true, and does not "
    "allow runtime enablement."
)
ACTUAL_RECORD_VALIDATION_DETAIL = (
    "No actual human-completed ingest-review record payload was supplied. The "
    "validator is ready as a locked scaffold/contract only, repo-side review state "
    "remains unchanged, reviewed_runtime_patch_exists remains false, and runtime "
    "enablement remains disallowed/default-off."
)
REVIEW_ONLY_VALIDATION_EFFECT_DETAIL = (
    "Validation remains review-only/default-off: repo_side_review_state_updated stays "
    "false, reviewed_runtime_patch_exists stays false, and "
    "runtime_enablement_allowed stays false."
)
BLOCKED_GATE_CONTRACT_DETAIL = (
    "Future ingest-review record validation may confirm the record contract only. It "
    "must still preserve the current blocked gates, carry forward the post-ingest "
    "blocked gates, keep repo_side_review_state_updated=false during validation, keep "
    "reviewed_runtime_patch_exists=false during validation, and keep "
    "runtime_enablement_allowed=false."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
    project_root: Path,
    *,
    ingest_review_record_scaffold_path: Optional[Path] = None,
    reviewed_runtime_patch_ingest_gate_path: Optional[Path] = None,
    signoff_record_validator_path: Optional[Path] = None,
    ingest_review_record_payload_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ingest_review_record_scaffold_resolved = _resolve_path(
        project_root,
        ingest_review_record_scaffold_path
        if ingest_review_record_scaffold_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_SCAFFOLD_PATH,
    )
    reviewed_runtime_patch_ingest_gate_resolved = _resolve_path(
        project_root,
        reviewed_runtime_patch_ingest_gate_path
        if reviewed_runtime_patch_ingest_gate_path is not None
        else DEFAULT_REVIEWED_RUNTIME_PATCH_INGEST_GATE_PATH,
    )
    signoff_record_validator_resolved = _resolve_path(
        project_root,
        signoff_record_validator_path
        if signoff_record_validator_path is not None
        else DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH,
    )
    ingest_review_record_payload_resolved = (
        _resolve_path(project_root, ingest_review_record_payload_path)
        if ingest_review_record_payload_path is not None
        else None
    )

    scaffold_report, scaffold_error = _load_json_mapping(
        ingest_review_record_scaffold_resolved
    )
    ingest_gate_report, ingest_gate_error = _load_json_mapping(
        reviewed_runtime_patch_ingest_gate_resolved
    )
    signoff_validator_report, signoff_validator_error = _load_json_mapping(
        signoff_record_validator_resolved
    )
    ingest_review_record_payload_report, ingest_review_record_payload_error = (
        _load_json_mapping(ingest_review_record_payload_resolved)
        if ingest_review_record_payload_resolved is not None
        else (None, None)
    )

    scaffold_meta = _mapping(scaffold_report.get("metadata")) if scaffold_report else {}
    scaffold_status = _mapping(scaffold_report.get("status")) if scaffold_report else {}
    scaffold = (
        _mapping(scaffold_report.get("ingest_review_record_scaffold"))
        if scaffold_report
        else {}
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
    signoff_validator_meta = (
        _mapping(signoff_validator_report.get("metadata"))
        if signoff_validator_report
        else {}
    )
    signoff_validator_status = (
        _mapping(signoff_validator_report.get("status"))
        if signoff_validator_report
        else {}
    )
    signoff_record_validator = (
        _mapping(signoff_validator_report.get("signoff_record_validator"))
        if signoff_validator_report
        else {}
    )
    candidate = (
        _mapping(scaffold_report.get("candidate"))
        if scaffold_report
        else _mapping(ingest_gate_report.get("candidate"))
        if ingest_gate_report
        else _mapping(signoff_validator_report.get("candidate"))
        if signoff_validator_report
        else {}
    )

    ingest_review_record_scaffold_present = bool(
        scaffold_report is not None
        and scaffold_error is None
        and scaffold_meta.get("source") == INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE
    )
    reviewed_runtime_patch_ingest_gate_present = bool(
        ingest_gate_report is not None
        and ingest_gate_error is None
        and ingest_gate_meta.get("source") == REVIEWED_RUNTIME_PATCH_INGEST_GATE_SOURCE
    )
    signoff_record_validator_present = bool(
        signoff_validator_report is not None
        and signoff_validator_error is None
        and signoff_validator_meta.get("source") == SIGNOFF_RECORD_VALIDATOR_SOURCE
    )

    ingest_review_record_scaffold_ready = bool(
        scaffold_status.get("ingest_review_record_scaffold_ready", False)
    )
    reviewed_runtime_patch_ingest_gate_ready = bool(
        ingest_gate_status.get("reviewed_runtime_patch_ingest_gate_ready", False)
    )
    signoff_record_validator_ready = bool(
        signoff_validator_status.get("signoff_record_validator_ready", False)
    )
    upstream_repo_side_review_state_updated = bool(
        scaffold_status.get("repo_side_review_state_updated", False)
        or ingest_gate_status.get("repo_side_review_state_updated", False)
        or bool(scaffold_meta.get("repo_side_review_state_updated", False))
        or bool(ingest_gate_meta.get("repo_side_review_state_updated", False))
    )
    upstream_reviewed_runtime_patch_exists = bool(
        scaffold_status.get("reviewed_runtime_patch_exists", False)
        or ingest_gate_status.get("reviewed_runtime_patch_exists", False)
        or signoff_validator_status.get("reviewed_runtime_patch_exists", False)
    )
    upstream_runtime_enablement_allowed = bool(
        scaffold_status.get("runtime_enablement_allowed", False)
        or ingest_gate_status.get("runtime_enablement_allowed", False)
        or signoff_validator_status.get("runtime_enablement_allowed", False)
    )

    locked_target_review_state = _mapping(scaffold.get("locked_target_review_state"))
    locked_reviewer_record_handoff = _mapping(
        scaffold.get("locked_reviewer_record_handoff")
    )
    validator_contract_reference = _mapping(
        scaffold.get("validator_contract_reference")
    )
    required_review_conclusions = _mapping_list(
        scaffold.get("required_review_conclusions")
    )
    preserved_blocked_gates = _mapping(scaffold.get("preserved_blocked_gates"))
    ingest_review_record_template = _mapping(scaffold.get("ingest_review_record_template"))

    ingest_gate_target = _mapping(
        reviewed_runtime_patch_ingest_gate.get("repo_side_review_state_target")
    )
    ingest_gate_handoff = _mapping(
        reviewed_runtime_patch_ingest_gate.get("locked_reviewer_record_handoff")
    )
    ingest_review_contract = _mapping(
        reviewed_runtime_patch_ingest_gate.get("ingest_review_contract")
    )

    signoff_validator_rules = _mapping(signoff_record_validator.get("validator_rules"))
    signoff_actual_record_validation = _mapping(
        signoff_record_validator.get("actual_record_validation")
    )

    review_state_kind = (
        str(locked_target_review_state.get("review_state_kind") or "").strip()
        or str(ingest_gate_target.get("review_state_kind") or "").strip()
    )
    tracked_field = (
        str(locked_target_review_state.get("tracked_field") or "").strip()
        or str(ingest_gate_target.get("tracked_field") or "").strip()
    )
    target_record_identity = (
        str(locked_target_review_state.get("record_identity") or "").strip()
        or str(ingest_gate_target.get("record_identity") or "").strip()
    )
    locked_target_record_type = (
        str(locked_target_review_state.get("record_type") or "").strip()
        or str(ingest_gate_target.get("record_type") or "").strip()
    )
    scope = (
        str(locked_target_review_state.get("scope") or "").strip()
        or str(ingest_gate_target.get("scope") or "").strip()
        or str(scaffold.get("scope") or "").strip()
        or str(signoff_record_validator.get("scope") or "").strip()
    )
    current_field_value = bool(locked_target_review_state.get("current_field_value", False))
    proposed_field_value_if_approved = bool(
        locked_target_review_state.get("proposed_field_value_if_approved", True)
    )
    ingest_review_record_type = (
        str(scaffold.get("record_type") or "").strip()
        or str(ingest_review_record_template.get("record_type") or "").strip()
    )

    handoff_format = (
        str(locked_reviewer_record_handoff.get("handoff_format") or "").strip()
        or str(ingest_gate_handoff.get("handoff_format") or "").strip()
    )
    handoff_dir = (
        str(locked_reviewer_record_handoff.get("handoff_dir") or "").strip()
        or str(ingest_gate_handoff.get("handoff_dir") or "").strip()
    )
    handoff_path_shape = (
        str(locked_reviewer_record_handoff.get("handoff_path_shape") or "").strip()
        or str(ingest_gate_handoff.get("handoff_path_shape") or "").strip()
    )
    handoff_filename_tokens = _string_list(
        locked_reviewer_record_handoff.get("handoff_filename_tokens")
    ) or _string_list(ingest_gate_handoff.get("handoff_filename_tokens"))

    locked_reviewer_record_validator_target = (
        str(validator_contract_reference.get("validator_target") or "").strip()
        or str(ingest_review_contract.get("validator_target") or "").strip()
        or str(signoff_record_validator.get("validator_target") or "").strip()
    )
    required_reviewer_statement_ids = _string_list(
        ingest_review_record_template.get("required_reviewer_statement_ids")
    ) or _string_list(validator_contract_reference.get("required_reviewer_statement_ids")) or _string_list(
        ingest_review_contract.get("required_reviewer_statement_ids")
    ) or _string_list(signoff_record_validator.get("required_reviewer_statement_ids"))
    required_review_conclusion_ids = _string_list(
        ingest_review_record_template.get("required_review_conclusion_ids")
    )
    if not required_review_conclusion_ids:
        required_review_conclusion_ids = [
            str(entry.get("conclusion_id"))
            for entry in required_review_conclusions
            if entry.get("conclusion_id")
        ]
    current_still_blocked_gate_ids = _string_list(
        ingest_review_record_template.get("current_still_blocked_gate_ids")
    ) or _string_list(preserved_blocked_gates.get("current_still_blocked_gate_ids")) or _string_list(
        ingest_review_contract.get("current_still_blocked_gate_ids")
    ) or _string_list(
        _mapping(signoff_validator_rules.get("still_blocked_gate_ids")).get("required_ids")
    )
    post_ingest_still_blocked_gate_ids = _string_list(
        ingest_review_record_template.get("post_ingest_still_blocked_gate_ids")
    ) or _string_list(preserved_blocked_gates.get("post_ingest_still_blocked_gate_ids")) or _string_list(
        ingest_review_contract.get("post_ingest_still_blocked_gate_ids")
    )

    signoff_required_statement_ids = _string_list(
        signoff_record_validator.get("required_reviewer_statement_ids")
    ) or _string_list(
        _mapping(signoff_validator_rules.get("agreed_statement_ids")).get("required_ids")
    )
    signoff_current_still_blocked_gate_ids = _string_list(
        _mapping(signoff_validator_rules.get("still_blocked_gate_ids")).get("required_ids")
    )
    scaffold_post_ingest_still_blocked_gate_ids = _string_list(
        preserved_blocked_gates.get("post_ingest_still_blocked_gate_ids")
    )
    ingest_gate_post_ingest_still_blocked_gate_ids = _string_list(
        ingest_review_contract.get("post_ingest_still_blocked_gate_ids")
    )
    ingest_gate_missing_prerequisite_gate_ids = _string_list(
        ingest_gate_status.get("missing_prerequisite_gate_ids")
    )

    locked_target_review_state_defined = bool(
        review_state_kind
        and tracked_field
        and target_record_identity
        and locked_target_record_type
        and scope
    )
    locked_target_review_state_aligned = bool(
        locked_target_review_state_defined
        and ingest_gate_target
        and review_state_kind == str(ingest_gate_target.get("review_state_kind") or "").strip()
        and tracked_field == str(ingest_gate_target.get("tracked_field") or "").strip()
        and target_record_identity
        == str(ingest_gate_target.get("record_identity") or "").strip()
        and locked_target_record_type
        == str(ingest_gate_target.get("record_type") or "").strip()
        and scope == str(ingest_gate_target.get("scope") or "").strip()
    )
    locked_reviewer_record_handoff_defined = bool(
        handoff_format == "json"
        and handoff_dir
        and handoff_path_shape
        and handoff_filename_tokens
    )
    locked_reviewer_record_handoff_aligned = bool(
        locked_reviewer_record_handoff_defined
        and ingest_gate_handoff
        and handoff_format == str(ingest_gate_handoff.get("handoff_format") or "").strip()
        and handoff_dir == str(ingest_gate_handoff.get("handoff_dir") or "").strip()
        and handoff_path_shape
        == str(ingest_gate_handoff.get("handoff_path_shape") or "").strip()
        and handoff_filename_tokens
        == _string_list(ingest_gate_handoff.get("handoff_filename_tokens"))
    )
    ingest_review_record_template_present = bool(ingest_review_record_template)
    locked_reviewer_record_validator_target_defined = bool(
        locked_reviewer_record_validator_target
    )
    signoff_validator_contract_available = bool(
        _mapping_list(signoff_validator_rules.get("required_fields"))
        and _mapping(signoff_validator_rules.get("agreed_statement_ids"))
        and _mapping(signoff_validator_rules.get("still_blocked_gate_ids"))
    )
    required_review_conclusions_defined = bool(required_review_conclusions)

    required_field_rules = _build_required_field_rules(
        ingest_review_record_template,
        locked_reviewer_record_validator_target=locked_reviewer_record_validator_target,
    )
    reviewer_record_handoff_path_rule = _build_reviewer_record_handoff_path_rule(
        handoff_format=handoff_format,
        handoff_path_shape=handoff_path_shape,
        handoff_filename_tokens=handoff_filename_tokens,
    )
    required_reviewer_statement_ids_rule = _build_required_ids_rule(
        field="required_reviewer_statement_ids",
        required_ids=required_reviewer_statement_ids,
        validation_rule="must_match_locked_required_reviewer_statement_ids_exactly",
        detail=(
            "Future completed ingest-review record must carry forward the locked reviewer "
            "statement ids from the scaffold/signoff validator contract."
        ),
    )
    required_review_conclusion_ids_rule = _build_required_ids_rule(
        field="required_review_conclusion_ids",
        required_ids=required_review_conclusion_ids,
        validation_rule="must_match_locked_required_review_conclusion_ids_exactly",
        detail=(
            "Future completed ingest-review record must carry forward the locked review "
            "conclusion ids from the scaffold."
        ),
    )
    review_conclusions_rule = _build_review_conclusions_rule(
        required_ids=required_review_conclusion_ids
    )
    current_still_blocked_gate_ids_rule = _build_required_ids_rule(
        field="current_still_blocked_gate_ids",
        required_ids=current_still_blocked_gate_ids,
        validation_rule="must_match_locked_current_still_blocked_gate_ids_exactly",
        detail=(
            "Future completed ingest-review record must preserve the current still-blocked "
            "gate ids exactly as locked by the scaffold/validator chain."
        ),
    )
    post_ingest_still_blocked_gate_ids_rule = _build_required_ids_rule(
        field="post_ingest_still_blocked_gate_ids",
        required_ids=post_ingest_still_blocked_gate_ids,
        validation_rule="must_match_locked_post_ingest_still_blocked_gate_ids_exactly",
        detail=(
            "Future completed ingest-review record must preserve the post-ingest blocked "
            "gate ids that still remain even after validation."
        ),
    )

    required_field_rules_ready = bool(required_field_rules)
    reviewer_record_handoff_path_rule_ready = bool(reviewer_record_handoff_path_rule)
    required_reviewer_statement_ids_rule_ready = bool(
        required_reviewer_statement_ids_rule
    )
    required_review_conclusion_ids_rule_ready = bool(
        required_review_conclusion_ids_rule
    )
    review_conclusions_rule_ready = bool(review_conclusions_rule)
    current_still_blocked_gate_ids_rule_ready = bool(
        current_still_blocked_gate_ids_rule
    )
    post_ingest_still_blocked_gate_ids_rule_ready = bool(
        post_ingest_still_blocked_gate_ids_rule
    )
    actual_record_validation = _build_actual_ingest_review_record_validation(
        project_root=project_root,
        payload_path=ingest_review_record_payload_resolved,
        payload_report=ingest_review_record_payload_report,
        payload_error=ingest_review_record_payload_error,
        required_field_rules=required_field_rules,
        reviewer_record_handoff_path_rule=reviewer_record_handoff_path_rule,
        required_reviewer_statement_ids_rule=required_reviewer_statement_ids_rule,
        required_review_conclusion_ids_rule=required_review_conclusion_ids_rule,
        review_conclusions_rule=review_conclusions_rule,
        current_still_blocked_gate_ids_rule=current_still_blocked_gate_ids_rule,
        post_ingest_still_blocked_gate_ids_rule=post_ingest_still_blocked_gate_ids_rule,
    )

    template_target_fields_aligned = bool(
        ingest_review_record_template_present
        and ingest_review_record_type
        == str(ingest_review_record_template.get("record_type") or "").strip()
        and review_state_kind
        == str(ingest_review_record_template.get("review_state_kind") or "").strip()
        and tracked_field
        == str(ingest_review_record_template.get("tracked_field") or "").strip()
        and target_record_identity
        == str(ingest_review_record_template.get("target_record_identity") or "").strip()
        and locked_target_record_type
        == str(ingest_review_record_template.get("target_record_type") or "").strip()
        and scope == str(ingest_review_record_template.get("scope") or "").strip()
        and proposed_field_value_if_approved
        == bool(ingest_review_record_template.get("proposed_field_value_if_approved", False))
        and locked_reviewer_record_validator_target
        == str(ingest_review_record_template.get("validator_target") or "").strip()
    )
    required_reviewer_statement_ids_aligned = bool(
        required_reviewer_statement_ids
        and signoff_required_statement_ids
        and required_reviewer_statement_ids == signoff_required_statement_ids
    )
    required_review_conclusion_ids_aligned = bool(
        required_review_conclusion_ids
        and required_review_conclusions
        and required_review_conclusion_ids
        == [
            str(entry.get("conclusion_id"))
            for entry in required_review_conclusions
            if entry.get("conclusion_id")
        ]
        and all(
            gate_id in required_review_conclusion_ids
            for gate_id in ingest_gate_missing_prerequisite_gate_ids
        )
    )
    current_still_blocked_gate_ids_aligned = bool(
        current_still_blocked_gate_ids
        and signoff_current_still_blocked_gate_ids
        and current_still_blocked_gate_ids == signoff_current_still_blocked_gate_ids
    )
    post_ingest_still_blocked_gate_ids_aligned = bool(
        post_ingest_still_blocked_gate_ids
        and scaffold_post_ingest_still_blocked_gate_ids
        and ingest_gate_post_ingest_still_blocked_gate_ids
        and post_ingest_still_blocked_gate_ids
        == scaffold_post_ingest_still_blocked_gate_ids
        == ingest_gate_post_ingest_still_blocked_gate_ids
    )
    review_only_spec_only_retained = bool(
        bool(scaffold_meta.get("review_only", False))
        and bool(scaffold_meta.get("spec_only", False))
        and bool(ingest_gate_meta.get("review_only", False))
        and bool(ingest_gate_meta.get("spec_only", False))
        and bool(signoff_validator_meta.get("spec_only", False))
    )
    default_off_retained = bool(
        ingest_review_record_scaffold_present
        and reviewed_runtime_patch_ingest_gate_present
        and signoff_record_validator_present
        and bool(scaffold_meta.get("default_off", False))
        and bool(ingest_gate_meta.get("default_off", False))
        and bool(signoff_validator_meta.get("default_off", False))
        and not upstream_runtime_enablement_allowed
    )
    proof_preserving_flags_retained = bool(
        not bool(scaffold_meta.get("proof_source", True))
        and not bool(ingest_gate_meta.get("proof_source", True))
        and not bool(signoff_validator_meta.get("proof_source", True))
        and not bool(scaffold_meta.get("solver_invoked", True))
        and not bool(ingest_gate_meta.get("solver_invoked", True))
        and not bool(signoff_validator_meta.get("solver_invoked", True))
    )
    signoff_actual_record_validation_not_run = bool(
        not signoff_actual_record_validation.get("record_payload_provided", False)
        and not signoff_actual_record_validation.get("record_payload_validated", False)
    )
    supplied_ingest_review_record_payload_provided = bool(
        actual_record_validation.get("record_payload_provided", False)
    )
    supplied_ingest_review_record_payload_loaded = bool(
        actual_record_validation.get("record_payload_loaded", False)
    )
    supplied_ingest_review_record_payload_validated = bool(
        actual_record_validation.get("record_payload_validated", False)
    )

    checks = [
        _check(
            "ingest_review_record_scaffold_present",
            "pass" if ingest_review_record_scaffold_present else "fail",
            "ingest review record scaffold loaded"
            if ingest_review_record_scaffold_present
            else scaffold_error
            or (
                f"unexpected_source:{scaffold_meta.get('source')}"
                if scaffold_report is not None
                else f"missing:{_display_path(project_root, ingest_review_record_scaffold_resolved)}"
            ),
        ),
        _check(
            "reviewed_runtime_patch_ingest_gate_present",
            "pass" if reviewed_runtime_patch_ingest_gate_present else "fail",
            "reviewed runtime patch ingest gate loaded"
            if reviewed_runtime_patch_ingest_gate_present
            else ingest_gate_error
            or (
                f"unexpected_source:{ingest_gate_meta.get('source')}"
                if ingest_gate_report is not None
                else f"missing:{_display_path(project_root, reviewed_runtime_patch_ingest_gate_resolved)}"
            ),
        ),
        _check(
            "signoff_record_validator_present",
            "pass" if signoff_record_validator_present else "fail",
            "signoff record validator loaded"
            if signoff_record_validator_present
            else signoff_validator_error
            or (
                f"unexpected_source:{signoff_validator_meta.get('source')}"
                if signoff_validator_report is not None
                else f"missing:{_display_path(project_root, signoff_record_validator_resolved)}"
            ),
        ),
        _check(
            "ingest_review_record_scaffold_ready",
            "pass" if ingest_review_record_scaffold_ready else "fail",
            str(ingest_review_record_scaffold_ready),
        ),
        _check(
            "reviewed_runtime_patch_ingest_gate_ready",
            "pass" if reviewed_runtime_patch_ingest_gate_ready else "fail",
            str(reviewed_runtime_patch_ingest_gate_ready),
        ),
        _check(
            "signoff_record_validator_ready",
            "pass" if signoff_record_validator_ready else "fail",
            str(signoff_record_validator_ready),
        ),
        _check(
            "locked_target_review_state_defined",
            "pass" if locked_target_review_state_defined else "fail",
            target_record_identity or "missing",
        ),
        _check(
            "locked_target_review_state_aligned",
            "pass" if locked_target_review_state_aligned else "fail",
            "scaffold target review-state identity matches ingest gate"
            if locked_target_review_state_aligned
            else "locked_target_review_state_mismatch_between_scaffold_and_ingest_gate",
        ),
        _check(
            "locked_reviewer_record_handoff_defined",
            "pass" if locked_reviewer_record_handoff_defined else "fail",
            handoff_path_shape or "missing",
        ),
        _check(
            "locked_reviewer_record_handoff_aligned",
            "pass" if locked_reviewer_record_handoff_aligned else "fail",
            "scaffold handoff contract matches ingest gate"
            if locked_reviewer_record_handoff_aligned
            else "locked_reviewer_record_handoff_mismatch_between_scaffold_and_ingest_gate",
        ),
        _check(
            "ingest_review_record_template_present",
            "pass" if ingest_review_record_template_present else "fail",
            "pending ingest-review record template present"
            if ingest_review_record_template_present
            else "missing",
        ),
        _check(
            "locked_reviewer_record_validator_target_defined",
            "pass" if locked_reviewer_record_validator_target_defined else "fail",
            locked_reviewer_record_validator_target or "missing",
        ),
        _check(
            "signoff_validator_contract_available",
            "pass" if signoff_validator_contract_available else "fail",
            "signoff validator rules present"
            if signoff_validator_contract_available
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
            "required_field_rules_ready",
            "pass" if required_field_rules_ready else "fail",
            ",".join(rule["field"] for rule in required_field_rules)
            if required_field_rules_ready
            else "missing",
        ),
        _check(
            "reviewer_record_handoff_path_rule_ready",
            "pass" if reviewer_record_handoff_path_rule_ready else "fail",
            handoff_path_shape if reviewer_record_handoff_path_rule_ready else "missing",
        ),
        _check(
            "required_reviewer_statement_ids_rule_ready",
            "pass" if required_reviewer_statement_ids_rule_ready else "fail",
            ",".join(required_reviewer_statement_ids)
            if required_reviewer_statement_ids_rule_ready
            else "missing",
        ),
        _check(
            "required_review_conclusion_ids_rule_ready",
            "pass" if required_review_conclusion_ids_rule_ready else "fail",
            ",".join(required_review_conclusion_ids)
            if required_review_conclusion_ids_rule_ready
            else "missing",
        ),
        _check(
            "review_conclusions_rule_ready",
            "pass" if review_conclusions_rule_ready else "fail",
            ",".join(required_review_conclusion_ids)
            if review_conclusions_rule_ready
            else "missing",
        ),
        _check(
            "current_still_blocked_gate_ids_rule_ready",
            "pass" if current_still_blocked_gate_ids_rule_ready else "fail",
            ",".join(current_still_blocked_gate_ids)
            if current_still_blocked_gate_ids_rule_ready
            else "missing",
        ),
        _check(
            "post_ingest_still_blocked_gate_ids_rule_ready",
            "pass" if post_ingest_still_blocked_gate_ids_rule_ready else "fail",
            ",".join(post_ingest_still_blocked_gate_ids)
            if post_ingest_still_blocked_gate_ids_rule_ready
            else "missing",
        ),
        _check(
            "template_target_fields_aligned",
            "pass" if template_target_fields_aligned else "fail",
            "ingest-review template matches locked target review-state identity"
            if template_target_fields_aligned
            else "template_locked_target_field_mismatch",
        ),
        _check(
            "required_reviewer_statement_ids_aligned",
            "pass" if required_reviewer_statement_ids_aligned else "fail",
            ",".join(required_reviewer_statement_ids)
            if required_reviewer_statement_ids_aligned
            else "required_reviewer_statement_ids_mismatch_vs_signoff_validator",
        ),
        _check(
            "required_review_conclusion_ids_aligned",
            "pass" if required_review_conclusion_ids_aligned else "fail",
            ",".join(required_review_conclusion_ids)
            if required_review_conclusion_ids_aligned
            else "required_review_conclusion_ids_mismatch_vs_scaffold_or_ingest_gate",
        ),
        _check(
            "current_still_blocked_gate_ids_aligned",
            "pass" if current_still_blocked_gate_ids_aligned else "fail",
            ",".join(current_still_blocked_gate_ids)
            if current_still_blocked_gate_ids_aligned
            else "current_still_blocked_gate_ids_mismatch_vs_signoff_validator",
        ),
        _check(
            "post_ingest_still_blocked_gate_ids_aligned",
            "pass" if post_ingest_still_blocked_gate_ids_aligned else "fail",
            ",".join(post_ingest_still_blocked_gate_ids)
            if post_ingest_still_blocked_gate_ids_aligned
            else "post_ingest_still_blocked_gate_ids_mismatch_between_scaffold_and_ingest_gate",
        ),
        _check(
            "review_only_spec_only_retained",
            "pass" if review_only_spec_only_retained else "fail",
            "review_only/spec_only retained across upstream contracts"
            if review_only_spec_only_retained
            else "expected review_only/spec_only flags across scaffold+ingest_gate+validator",
        ),
        _check(
            "default_off_retained",
            "pass" if default_off_retained else "fail",
            "default-off retained and runtime enablement remains blocked"
            if default_off_retained
            else "expected default_off=true and runtime_enablement_allowed=false upstream",
        ),
        _check(
            "proof_preserving_flags_retained",
            "pass" if proof_preserving_flags_retained else "fail",
            "proof_source=false and solver_invoked=false preserved upstream"
            if proof_preserving_flags_retained
            else "expected proof_source=false and solver_invoked=false upstream",
        ),
        _check(
            "signoff_actual_record_validation_not_run",
            "pass" if signoff_actual_record_validation_not_run else "fail",
            str(signoff_actual_record_validation_not_run),
        ),
        _check(
            "upstream_reviewed_runtime_patch_absent_as_expected",
            "pass" if not upstream_reviewed_runtime_patch_exists else "fail",
            str(upstream_reviewed_runtime_patch_exists),
        ),
        _check(
            "upstream_repo_side_review_state_unchanged_as_expected",
            "pass" if not upstream_repo_side_review_state_updated else "fail",
            str(upstream_repo_side_review_state_updated),
        ),
        _check(
            "upstream_runtime_enablement_blocked_as_expected",
            "pass" if not upstream_runtime_enablement_allowed else "fail",
            str(upstream_runtime_enablement_allowed),
        ),
    ]
    if supplied_ingest_review_record_payload_provided:
        checks.extend(
            [
                _check(
                    "ingest_review_record_payload_loaded",
                    "pass" if supplied_ingest_review_record_payload_loaded else "fail",
                    str(actual_record_validation.get("detail")),
                ),
                _check(
                    "actual_ingest_review_record_payload_validated",
                    "pass"
                    if supplied_ingest_review_record_payload_validated
                    else "fail",
                    str(actual_record_validation.get("detail")),
                ),
            ]
        )
    else:
        checks.append(
            _check(
                "actual_ingest_review_record_validation_not_run",
                "pass",
                ACTUAL_RECORD_VALIDATION_DETAIL,
            )
        )

    ingest_review_record_validator_ready = all(
        check["status"] == "pass"
        for check in checks
        if check["check_id"]
        not in {
            "actual_ingest_review_record_validation_not_run",
            "ingest_review_record_payload_loaded",
            "actual_ingest_review_record_payload_validated",
        }
    )

    gates = [
        _gate(
            "ingest_review_record_scaffold_ready",
            ingest_review_record_scaffold_ready,
            True,
            "This validator depends on the ingest-review record scaffold already being ready.",
        ),
        _gate(
            "reviewed_runtime_patch_ingest_gate_ready",
            reviewed_runtime_patch_ingest_gate_ready,
            True,
            "This validator depends on the reviewed runtime patch ingest gate already being ready.",
        ),
        _gate(
            "signoff_record_validator_ready",
            signoff_record_validator_ready,
            True,
            "This validator depends on the upstream signoff record validator already being ready.",
        ),
        _gate(
            "locked_target_review_state_defined",
            locked_target_review_state_defined and locked_target_review_state_aligned,
            True,
            "The locked target review-state identity must stay explicit and aligned with the ingest gate.",
        ),
        _gate(
            "locked_reviewer_record_handoff_defined",
            locked_reviewer_record_handoff_defined
            and locked_reviewer_record_handoff_aligned,
            True,
            "The locked reviewer-record handoff path must stay explicit and aligned with the ingest gate.",
        ),
        _gate(
            "locked_ingest_review_record_template_present",
            ingest_review_record_template_present and template_target_fields_aligned,
            True,
            "The validator must compare future completed records against the locked scaffold template.",
        ),
        _gate(
            "validator_required_field_rules_ready",
            required_field_rules_ready,
            True,
            "Required field validation rules must be derivable from the locked ingest-review scaffold.",
        ),
        _gate(
            "validator_required_review_conclusion_rules_ready",
            required_review_conclusion_ids_rule_ready
            and review_conclusions_rule_ready
            and required_review_conclusions_defined,
            True,
            "The validator must carry explicit rules for all required review conclusions.",
        ),
        _gate(
            "validator_current_still_blocked_gate_ids_rule_ready",
            current_still_blocked_gate_ids_rule_ready,
            True,
            "The validator must preserve the current still-blocked gate ids.",
        ),
        _gate(
            "validator_post_ingest_still_blocked_gate_ids_rule_ready",
            post_ingest_still_blocked_gate_ids_rule_ready,
            True,
            "The validator must preserve the blocked gates that still remain even after validation.",
        ),
        _gate(
            "default_off_retained_for_ingest_review_record_validator",
            default_off_retained
            and review_only_spec_only_retained
            and proof_preserving_flags_retained,
            True,
            "This validator remains review-only/default-off/spec-only/proof-preserving and does not allow runtime enablement.",
        ),
        _gate(
            "actual_ingest_review_record_payload_validated",
            supplied_ingest_review_record_payload_validated,
            False,
            str(actual_record_validation.get("detail")),
        ),
    ]
    gates.extend(
        _ensure_gate_entries(
            _merge_gate_entries(
                _blocked_gate_entries(scaffold_report),
                _blocked_gate_entries(ingest_gate_report),
                _blocked_gate_entries(signoff_validator_report),
            ),
            current_still_blocked_gate_ids=current_still_blocked_gate_ids,
            post_ingest_still_blocked_gate_ids=post_ingest_still_blocked_gate_ids,
        )
    )

    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    if not ingest_review_record_validator_ready:
        recommended_next_step = "repair_ingest_review_record_validator_inputs"
        handoff_recommendation = (
            "Ingest-review record validator contract is blocked; repair the missing "
            "ingest-review scaffold, reviewed-runtime-patch ingest gate, or signoff "
            "validator prerequisites before using this contract for any future completed "
            "ingest-review record."
        )
    elif supplied_ingest_review_record_payload_provided:
        if supplied_ingest_review_record_payload_validated:
            recommended_next_step = (
                "review_only_validated_ingest_review_record_payload_retains_blocked_gates"
            )
            handoff_recommendation = (
                "Supplied ingest-review record payload validated successfully against "
                "the locked scaffold/contract. Validation remains review-only: it does "
                "not update repo-side review state, does not set "
                "reviewed_runtime_patch_exists=true, and does not allow runtime "
                "enablement."
            )
        else:
            recommended_next_step = (
                "repair_supplied_ingest_review_record_payload_against_locked_contract"
            )
            handoff_recommendation = (
                "Supplied ingest-review record payload did not validate against the "
                "locked scaffold/contract. Repair the payload using the per-rule "
                "validation results; repo-side review state remains unchanged and "
                "runtime enablement remains blocked/default-off."
            )
    else:
        recommended_next_step = (
            "handoff_ingest_review_record_validator_contract_for_future_manual_validation"
        )
        handoff_recommendation = (
            "Ingest-review record validator contract is ready: use it to compare a future "
            "human-completed ingest-review record against the locked scaffold fields, "
            "required review conclusions, reviewer-record handoff contract, and preserved "
            "blocked-gate sets. This artifact does not validate an actual record yet, does "
            "not update repo-side review state, and does not allow runtime enablement."
        )

    return {
        "metadata": {
            "source": INGEST_REVIEW_RECORD_VALIDATOR_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_ingest_review_record_validator_contract_not_actual_validation"
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
            "ingest_review_record_scaffold": _display_path(
                project_root, ingest_review_record_scaffold_resolved
            ),
            "reviewed_runtime_patch_ingest_gate": _display_path(
                project_root, reviewed_runtime_patch_ingest_gate_resolved
            ),
            "signoff_record_validator": _display_path(
                project_root, signoff_record_validator_resolved
            ),
            "ingest_review_record_payload": (
                _display_path(project_root, ingest_review_record_payload_resolved)
                if ingest_review_record_payload_resolved is not None
                else None
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "ingest_review_record_validator_ready": bool(
                ingest_review_record_validator_ready
            ),
            "manual_ingest_review_record_provided": supplied_ingest_review_record_payload_provided,
            "manual_ingest_review_record_validated": supplied_ingest_review_record_payload_validated,
            "manual_ingest_review_record_validation_status": str(
                actual_record_validation.get("validation_status")
            ),
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "ingest_review_record_validator": {
            "validator_target": INGEST_REVIEW_RECORD_VALIDATOR_TARGET,
            "target_record_type": ingest_review_record_type,
            "scope": scope,
            "locked_target_review_state": {
                "review_state_kind": review_state_kind,
                "tracked_field": tracked_field,
                "record_identity": target_record_identity,
                "record_type": locked_target_record_type,
                "scope": scope,
                "current_field_value": current_field_value,
                "proposed_field_value_if_approved": proposed_field_value_if_approved,
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": handoff_format,
                "handoff_dir": handoff_dir,
                "handoff_path_shape": handoff_path_shape,
                "handoff_filename_tokens": list(handoff_filename_tokens),
            },
            "locked_reviewer_record_validator_target": (
                locked_reviewer_record_validator_target
            ),
            "expected_template_payload": dict(ingest_review_record_template),
            "required_review_conclusions": [
                dict(entry) for entry in required_review_conclusions
            ],
            "blocked_gate_contract": {
                "current_still_blocked_gate_ids": list(current_still_blocked_gate_ids),
                "post_ingest_still_blocked_gate_ids": list(
                    post_ingest_still_blocked_gate_ids
                ),
                "repo_side_review_state_updated_after_validation": False,
                "reviewed_runtime_patch_exists_after_validation": False,
                "runtime_enablement_allowed_after_validation": False,
                "detail": BLOCKED_GATE_CONTRACT_DETAIL,
            },
            "validator_rules": {
                "required_fields": required_field_rules,
                "reviewer_record_handoff_path": reviewer_record_handoff_path_rule,
                "required_reviewer_statement_ids": (
                    required_reviewer_statement_ids_rule
                ),
                "required_review_conclusion_ids": (
                    required_review_conclusion_ids_rule
                ),
                "review_conclusions": review_conclusions_rule,
                "current_still_blocked_gate_ids": (
                    current_still_blocked_gate_ids_rule
                ),
                "post_ingest_still_blocked_gate_ids": (
                    post_ingest_still_blocked_gate_ids_rule
                ),
            },
            "actual_record_validation": actual_record_validation,
            "validator_notice": VALIDATOR_NOTICE,
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("ingest_review_record_validator"))
    locked_target = _mapping(validator.get("locked_target_review_state"))
    locked_handoff = _mapping(validator.get("locked_reviewer_record_handoff"))
    blocked_gate_contract = _mapping(validator.get("blocked_gate_contract"))
    validator_rules = _mapping(validator.get("validator_rules"))
    actual_validation = _mapping(validator.get("actual_record_validation"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Ingest Review Record Validator",
        "",
        f"- Ingest review record validator ready: `{status.get('ingest_review_record_validator_ready')}`",
        f"- Manual ingest-review record provided: `{status.get('manual_ingest_review_record_provided')}`",
        f"- Manual ingest-review record validated: `{status.get('manual_ingest_review_record_validated')}`",
        f"- Manual ingest-review record validation status: `{status.get('manual_ingest_review_record_validation_status')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Validator notice: {validator.get('validator_notice')}",
        "",
        "## Target Contract",
        "",
        f"- Validator target: `{validator.get('validator_target')}`",
        f"- Target record type: `{validator.get('target_record_type')}`",
        f"- Scope: `{validator.get('scope')}`",
        f"- Locked reviewer-record validator target: `{validator.get('locked_reviewer_record_validator_target')}`",
        "",
        "## Locked Target Review State",
        "",
        f"- Review state kind: `{locked_target.get('review_state_kind')}`",
        f"- Tracked field: `{locked_target.get('tracked_field')}`",
        f"- Record identity: `{locked_target.get('record_identity')}`",
        f"- Record type: `{locked_target.get('record_type')}`",
        f"- Scope: `{locked_target.get('scope')}`",
        f"- Current field value: `{locked_target.get('current_field_value')}`",
        f"- Proposed field value if approved: `{locked_target.get('proposed_field_value_if_approved')}`",
        "",
        "## Locked Reviewer Record Handoff",
        "",
        f"- Handoff format: `{locked_handoff.get('handoff_format')}`",
        f"- Handoff dir: `{locked_handoff.get('handoff_dir')}`",
        f"- Handoff path shape: `{locked_handoff.get('handoff_path_shape')}`",
        f"- Filename tokens: `{', '.join(_string_list(locked_handoff.get('handoff_filename_tokens'))) or '(none)'}`",
        "",
        "## Required Review Conclusions",
        "",
        "| Conclusion | Required | Template value | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(validator.get("required_review_conclusions", [])):
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
            "## Actual Record Validation State",
            "",
            f"- Record payload provided: `{actual_validation.get('record_payload_provided')}`",
            f"- Record payload path: `{actual_validation.get('record_payload_path') or '(not provided)'}`",
            f"- Record payload loaded: `{actual_validation.get('record_payload_loaded')}`",
            f"- Record payload validated: `{actual_validation.get('record_payload_validated')}`",
            f"- Validation status: `{actual_validation.get('validation_status')}`",
            f"- Passed rule count: `{actual_validation.get('passed_rule_count')}`",
            f"- Failed rule count: `{actual_validation.get('failed_rule_count')}`",
            f"- Detail: {actual_validation.get('detail')}",
        "",
            "## Per-Rule Validation Results",
            "",
            "| Rule | Status | Field | Validation rule | Detail |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for rule_result in list(actual_validation.get("rule_results", [])):
        if isinstance(rule_result, Mapping):
            lines.append(
                f"| {_markdown_cell(rule_result.get('rule_id'))} | "
                f"{_markdown_cell(rule_result.get('status'))} | "
                f"{_markdown_cell(rule_result.get('field'))} | "
                f"{_markdown_cell(rule_result.get('validation_rule'))} | "
                f"{_markdown_cell(rule_result.get('detail'))} |"
            )
    if not list(actual_validation.get("rule_results", [])):
        lines.append("| `(not run)` | `not_run` |  |  | No payload supplied. |")
    lines.extend(
        [
            "",
            "## Required Field Rules",
            "",
            "| Field | Required | Template value | Validation rule | Validator detail |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for rule in list(validator_rules.get("required_fields", [])):
        if isinstance(rule, Mapping):
            lines.append(
                f"| {_markdown_cell(rule.get('field'))} | "
                f"{_markdown_cell(rule.get('required'))} | "
                f"{_markdown_cell(rule.get('template_value'))} | "
                f"{_markdown_cell(rule.get('validation_rule'))} | "
                f"{_markdown_cell(rule.get('validator_detail'))} |"
            )
    handoff_rule = _mapping(validator_rules.get("reviewer_record_handoff_path"))
    lines.extend(
        [
            "",
            "## Reviewer Record Handoff Path Rule",
            "",
            f"- Validation rule: `{handoff_rule.get('validation_rule')}`",
            f"- Locked format: `{handoff_rule.get('required_format')}`",
            f"- Locked path shape: `{handoff_rule.get('locked_path_shape')}`",
            f"- Locked filename tokens: `{', '.join(_string_list(handoff_rule.get('locked_filename_tokens'))) or '(none)'}`",
            f"- Detail: {handoff_rule.get('detail')}",
        ]
    )
    for section_title, rule_key in [
        ("Required Reviewer Statement Ids Rule", "required_reviewer_statement_ids"),
        ("Required Review Conclusion Ids Rule", "required_review_conclusion_ids"),
        ("Review Conclusions Rule", "review_conclusions"),
        ("Current Still Blocked Gate Ids Rule", "current_still_blocked_gate_ids"),
        ("Post-Ingest Still Blocked Gate Ids Rule", "post_ingest_still_blocked_gate_ids"),
    ]:
        rule = _mapping(validator_rules.get(rule_key))
        lines.extend(
            [
                "",
                f"## {section_title}",
                "",
                f"- Required ids: `{', '.join(_string_list(rule.get('required_ids'))) or '(none)'}`",
                f"- Validation rule: `{rule.get('validation_rule')}`",
                f"- Detail: {rule.get('detail')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Blocked Gate Contract",
            "",
            f"- Current still blocked gate ids: `{', '.join(_string_list(blocked_gate_contract.get('current_still_blocked_gate_ids'))) or '(none)'}`",
            f"- Post-ingest still blocked gate ids: `{', '.join(_string_list(blocked_gate_contract.get('post_ingest_still_blocked_gate_ids'))) or '(none)'}`",
            f"- Repo-side review state updated after validation: `{blocked_gate_contract.get('repo_side_review_state_updated_after_validation')}`",
            f"- Reviewed runtime patch exists after validation: `{blocked_gate_contract.get('reviewed_runtime_patch_exists_after_validation')}`",
            f"- Runtime enablement allowed after validation: `{blocked_gate_contract.get('runtime_enablement_allowed_after_validation')}`",
            f"- Detail: {blocked_gate_contract.get('detail')}",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("ingest_review_record_validator"))
    locked_target = _mapping(validator.get("locked_target_review_state"))
    actual_validation = _mapping(validator.get("actual_record_validation"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain ingest review record validator",
            "ingest_review_record_validator_ready="
            + str(status.get("ingest_review_record_validator_ready")),
            "manual_ingest_review_record_provided="
            + str(status.get("manual_ingest_review_record_provided")),
            "manual_ingest_review_record_validated="
            + str(status.get("manual_ingest_review_record_validated")),
            "manual_ingest_review_record_validation_status="
            + str(status.get("manual_ingest_review_record_validation_status")),
            "repo_side_review_state_updated="
            + str(status.get("repo_side_review_state_updated")),
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            f"target_record_type={validator.get('target_record_type')}",
            f"record_identity={locked_target.get('record_identity')}",
            f"actual_record_payload_path={actual_validation.get('record_payload_path')}",
            f"actual_record_validation_status={actual_validation.get('validation_status')}",
            f"actual_record_failed_rule_count={actual_validation.get('failed_rule_count')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_ingest_review_record_validator",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_required_field_rules(
    template_payload: Mapping[str, Any],
    *,
    locked_reviewer_record_validator_target: str,
) -> list[Dict[str, Any]]:
    rules: list[Dict[str, Any]] = []
    for field, template_value in template_payload.items():
        validation_rule, validator_detail = _derive_field_validation_rule(
            field,
            template_value,
            locked_reviewer_record_validator_target=locked_reviewer_record_validator_target,
        )
        rules.append(
            {
                "field": str(field),
                "required": True,
                "template_value": template_value,
                "validation_rule": validation_rule,
                "validator_detail": validator_detail,
            }
        )
    return rules


def _derive_field_validation_rule(
    field: str,
    template_value: Any,
    *,
    locked_reviewer_record_validator_target: str,
) -> tuple[str, str]:
    if field in {
        "record_type",
        "review_state_kind",
        "tracked_field",
        "target_record_identity",
        "target_record_type",
        "scope",
        "proposed_field_value_if_approved",
        "repo_side_review_state_updated",
        "reviewed_runtime_patch_exists",
        "runtime_enablement_allowed",
    }:
        return (
            "must_equal_template_value",
            "Future completed payload must carry forward this exact locked scaffold value.",
        )
    if field in {"ingest_reviewer_id", "ingest_reviewed_at", "decision_notes"}:
        return (
            "must_be_present_and_non_empty",
            "Future completed payload must replace the empty scaffold placeholder with a non-empty human-authored value.",
        )
    if field == "review_decision":
        return (
            "must_be_present_and_not_pending",
            "Future completed payload must replace `pending` with an explicit manual ingest-review decision, but that decision still does not apply repo-side state or allow runtime enablement.",
        )
    if field == "reviewer_record_handoff_path":
        return (
            "validated_by_reviewer_record_handoff_path_rule",
            "This field is validated by the explicit reviewer_record_handoff_path rule below.",
        )
    if field == "reviewer_record_validation_status":
        return (
            "must_be_present_and_not_pending_manual_validation",
            "Future completed payload must explicitly show that the reviewer-signed record was manually checked against the locked validator contract before the ingest-review record is considered complete.",
        )
    if field == "validator_target":
        detail = (
            "Future completed payload must carry forward the locked reviewer-record "
            "validator target."
        )
        if locked_reviewer_record_validator_target:
            detail += f" Expected `{locked_reviewer_record_validator_target}`."
        return ("must_equal_template_value", detail)
    if field == "required_reviewer_statement_ids":
        return (
            "validated_by_required_reviewer_statement_ids_rule",
            "This field is validated by the explicit required_reviewer_statement_ids rule below.",
        )
    if field == "required_review_conclusion_ids":
        return (
            "validated_by_required_review_conclusion_ids_rule",
            "This field is validated by the explicit required_review_conclusion_ids rule below.",
        )
    if field == "review_conclusions":
        return (
            "validated_by_review_conclusions_rule",
            "This field is validated by the explicit review_conclusions rule below.",
        )
    if field == "current_still_blocked_gate_ids":
        return (
            "validated_by_current_still_blocked_gate_ids_rule",
            "This field is validated by the explicit current_still_blocked_gate_ids rule below.",
        )
    if field == "post_ingest_still_blocked_gate_ids":
        return (
            "validated_by_post_ingest_still_blocked_gate_ids_rule",
            "This field is validated by the explicit post_ingest_still_blocked_gate_ids rule below.",
        )
    return (
        "must_be_present",
        f"Future completed payload must provide the scaffolded field `{field}`.",
    )


def _build_reviewer_record_handoff_path_rule(
    *,
    handoff_format: str,
    handoff_path_shape: str,
    handoff_filename_tokens: list[str],
) -> Dict[str, Any]:
    if not (
        handoff_format == "json" and handoff_path_shape and handoff_filename_tokens
    ):
        return {}
    return {
        "field": "reviewer_record_handoff_path",
        "required": True,
        "required_format": handoff_format,
        "locked_path_shape": handoff_path_shape,
        "locked_filename_tokens": list(handoff_filename_tokens),
        "validation_rule": "must_reference_locked_reviewer_record_handoff_json",
        "detail": (
            "Future completed ingest-review record must reference the reviewer-record "
            "handoff JSON using the locked path shape/tokens rather than an arbitrary path."
        ),
    }


def _build_required_ids_rule(
    *,
    field: str,
    required_ids: list[str],
    validation_rule: str,
    detail: str,
) -> Dict[str, Any]:
    if not required_ids:
        return {}
    return {
        "field": field,
        "required": True,
        "required_ids": list(required_ids),
        "validation_rule": validation_rule,
        "detail": detail,
    }


def _build_review_conclusions_rule(required_ids: list[str]) -> Dict[str, Any]:
    if not required_ids:
        return {}
    return {
        "field": "review_conclusions",
        "required": True,
        "required_ids": list(required_ids),
        "validation_rule": (
            "must_include_each_required_conclusion_with_non_pending_decision_and_notes"
        ),
        "detail": (
            "Future completed ingest-review record must include one entry for each locked "
            "required review conclusion id, with a non-`pending` decision and non-empty notes."
        ),
    }


def _build_actual_ingest_review_record_validation(
    *,
    project_root: Path,
    payload_path: Optional[Path],
    payload_report: Optional[Mapping[str, Any]],
    payload_error: Optional[str],
    required_field_rules: list[Mapping[str, Any]],
    reviewer_record_handoff_path_rule: Mapping[str, Any],
    required_reviewer_statement_ids_rule: Mapping[str, Any],
    required_review_conclusion_ids_rule: Mapping[str, Any],
    review_conclusions_rule: Mapping[str, Any],
    current_still_blocked_gate_ids_rule: Mapping[str, Any],
    post_ingest_still_blocked_gate_ids_rule: Mapping[str, Any],
) -> Dict[str, Any]:
    if payload_path is None:
        return {
            "record_payload_provided": False,
            "record_payload_path": None,
            "record_payload_loaded": False,
            "record_payload_validated": False,
            "validation_status": "not_run",
            "passed_rule_count": 0,
            "failed_rule_count": 0,
            "rule_results": [],
            "detail": ACTUAL_RECORD_VALIDATION_DETAIL,
        }

    payload_path_display = _display_path(project_root, payload_path)
    if payload_report is None or payload_error is not None:
        detail = (
            f"Supplied ingest-review record payload could not be loaded from "
            f"`{payload_path_display}`: {payload_error or 'unknown_error'}. "
            f"{REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        return {
            "record_payload_provided": True,
            "record_payload_path": payload_path_display,
            "record_payload_loaded": False,
            "record_payload_validated": False,
            "validation_status": "payload_load_failed",
            "passed_rule_count": 0,
            "failed_rule_count": 0,
            "rule_results": [],
            "detail": detail,
        }

    payload = _mapping(payload_report)
    rule_results: list[Dict[str, Any]] = []
    rule_results.extend(
        _evaluate_required_field_rules(required_field_rules, payload=payload)
    )
    for rule in (
        reviewer_record_handoff_path_rule,
        required_reviewer_statement_ids_rule,
        required_review_conclusion_ids_rule,
        review_conclusions_rule,
        current_still_blocked_gate_ids_rule,
        post_ingest_still_blocked_gate_ids_rule,
    ):
        rule_results.append(_evaluate_named_rule(rule=rule, payload=payload))

    failed_rule_count = sum(
        1 for result in rule_results if result.get("status") == "fail"
    )
    passed_rule_count = sum(
        1 for result in rule_results if result.get("status") == "pass"
    )
    record_payload_validated = bool(rule_results) and failed_rule_count == 0
    if record_payload_validated:
        detail = (
            f"Supplied ingest-review record payload at `{payload_path_display}` "
            f"validated successfully against the locked scaffold/contract. "
            f"{REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        validation_status = "passed"
    else:
        detail = (
            f"Supplied ingest-review record payload at `{payload_path_display}` "
            f"failed {failed_rule_count} validation rule(s) against the locked "
            f"scaffold/contract. {REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        validation_status = "failed"
    return {
        "record_payload_provided": True,
        "record_payload_path": payload_path_display,
        "record_payload_loaded": True,
        "record_payload_validated": record_payload_validated,
        "validation_status": validation_status,
        "passed_rule_count": passed_rule_count,
        "failed_rule_count": failed_rule_count,
        "rule_results": rule_results,
        "detail": detail,
    }


def _evaluate_required_field_rules(
    required_field_rules: list[Mapping[str, Any]],
    *,
    payload: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    results: list[Dict[str, Any]] = []
    for rule in required_field_rules:
        field = str(rule.get("field") or "").strip()
        validation_rule = str(rule.get("validation_rule") or "").strip()
        if not field or not validation_rule:
            continue
        actual_value = payload.get(field)
        field_present = field in payload
        if validation_rule == "must_equal_template_value":
            passed = field_present and actual_value == rule.get("template_value")
            detail = (
                "Payload value matches locked template value."
                if passed
                else "Payload value does not match locked template value."
            )
        elif validation_rule == "must_be_present_and_non_empty":
            passed = field_present and _is_non_empty_value(actual_value)
            detail = (
                "Required non-empty field supplied."
                if passed
                else "Required non-empty field missing or empty."
            )
        elif validation_rule == "must_be_present_and_not_pending":
            actual_text = _normalized_text(actual_value)
            passed = field_present and bool(actual_text) and actual_text != "pending"
            detail = (
                "Completed review decision supplied."
                if passed
                else "Expected a non-pending review decision."
            )
        elif validation_rule == "must_be_present_and_not_pending_manual_validation":
            actual_text = _normalized_text(actual_value)
            passed = (
                field_present
                and bool(actual_text)
                and actual_text not in {"pending", "pending_manual_validation"}
            )
            detail = (
                "Reviewer-record validation status shows completed manual validation."
                if passed
                else "Expected a completed reviewer-record validation status."
            )
        elif validation_rule.startswith("validated_by_"):
            passed = field_present
            detail = (
                "Field is present and evaluated by its dedicated rule."
                if passed
                else "Required field missing before dedicated rule evaluation."
            )
        elif validation_rule == "must_be_present":
            passed = field_present
            detail = "Field present." if passed else "Required field missing."
        else:
            passed = field_present
            detail = (
                "Field present; no specialized evaluator was required."
                if passed
                else "Required field missing."
            )
        results.append(
            _validation_result(
                rule_id=f"required_field:{field}",
                status="pass" if passed else "fail",
                field=field,
                validation_rule=validation_rule,
                expected=rule.get("template_value"),
                actual=actual_value,
                detail=detail,
            )
        )
    return results


def _evaluate_named_rule(
    *,
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    field = str(rule.get("field") or "").strip()
    validation_rule = str(rule.get("validation_rule") or "").strip()
    if not field or not validation_rule:
        return _validation_result(
            rule_id="unnamed_rule",
            status="fail",
            field=field or None,
            validation_rule=validation_rule or None,
            detail="Rule definition missing field or validation_rule.",
        )
    if field == "reviewer_record_handoff_path":
        return _evaluate_reviewer_record_handoff_path_rule(rule=rule, payload=payload)
    if field in {
        "required_reviewer_statement_ids",
        "required_review_conclusion_ids",
        "current_still_blocked_gate_ids",
        "post_ingest_still_blocked_gate_ids",
    }:
        return _evaluate_required_ids_rule(rule=rule, payload=payload)
    if field == "review_conclusions":
        return _evaluate_review_conclusions_rule(rule=rule, payload=payload)
    return _validation_result(
        rule_id=field,
        status="fail",
        field=field,
        validation_rule=validation_rule,
        actual=payload.get(field),
        detail="No evaluator implemented for rule.",
    )


def _evaluate_reviewer_record_handoff_path_rule(
    *,
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    field = str(rule.get("field") or "reviewer_record_handoff_path")
    actual_text = str(payload.get(field) or "").strip()
    required_format = str(rule.get("required_format") or "").strip()
    locked_path_shape = str(rule.get("locked_path_shape") or "").strip()
    normalized_actual = _normalize_path_text(actual_text)
    shape_pattern = _path_shape_pattern(locked_path_shape)
    passed = bool(normalized_actual)
    if required_format == "json":
        passed = passed and normalized_actual.endswith(".json")
    if locked_path_shape:
        passed = passed and bool(re.fullmatch(shape_pattern, normalized_actual))
    detail = (
        "Reviewer-record handoff path matches the locked scaffold shape."
        if passed
        else "Reviewer-record handoff path does not match the locked scaffold shape."
    )
    return _validation_result(
        rule_id=field,
        status="pass" if passed else "fail",
        field=field,
        validation_rule=str(rule.get("validation_rule") or ""),
        expected=locked_path_shape,
        actual=actual_text,
        detail=detail,
    )


def _evaluate_required_ids_rule(
    *,
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    field = str(rule.get("field") or "").strip()
    required_ids = _string_list(rule.get("required_ids"))
    actual_ids = _string_list(payload.get(field))
    passed = bool(required_ids) and actual_ids == required_ids
    detail = (
        "Payload ids match the locked required ids exactly."
        if passed
        else "Payload ids do not match the locked required ids exactly."
    )
    return _validation_result(
        rule_id=field,
        status="pass" if passed else "fail",
        field=field,
        validation_rule=str(rule.get("validation_rule") or ""),
        expected=required_ids,
        actual=actual_ids,
        detail=detail,
    )


def _evaluate_review_conclusions_rule(
    *,
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    field = str(rule.get("field") or "review_conclusions")
    required_ids = _string_list(rule.get("required_ids"))
    actual_entries = _mapping_list(payload.get(field))
    actual_ids = [
        str(entry.get("conclusion_id") or "").strip()
        for entry in actual_entries
        if entry.get("conclusion_id")
    ]
    actual_id_counts: Dict[str, int] = {}
    for conclusion_id in actual_ids:
        actual_id_counts[conclusion_id] = actual_id_counts.get(conclusion_id, 0) + 1
    duplicate_ids = sorted(
        conclusion_id
        for conclusion_id, count in actual_id_counts.items()
        if count > 1 and conclusion_id
    )
    missing_ids = [
        conclusion_id
        for conclusion_id in required_ids
        if conclusion_id not in actual_id_counts
    ]
    extra_ids = [
        conclusion_id
        for conclusion_id in actual_id_counts
        if conclusion_id not in required_ids
    ]
    invalid_decision_ids: list[str] = []
    missing_notes_ids: list[str] = []
    for entry in actual_entries:
        conclusion_id = str(entry.get("conclusion_id") or "").strip()
        if not conclusion_id:
            continue
        decision = _normalized_text(entry.get("decision"))
        notes = str(entry.get("notes") or "").strip()
        if decision in {"", "pending"}:
            invalid_decision_ids.append(conclusion_id)
        if not notes:
            missing_notes_ids.append(conclusion_id)
    passed = not (
        missing_ids or extra_ids or duplicate_ids or invalid_decision_ids or missing_notes_ids
    )
    if passed:
        detail = "All required review conclusions are present with non-pending decisions and non-empty notes."
    else:
        detail_parts = []
        if missing_ids:
            detail_parts.append(f"missing_ids={','.join(missing_ids)}")
        if extra_ids:
            detail_parts.append(f"extra_ids={','.join(extra_ids)}")
        if duplicate_ids:
            detail_parts.append(f"duplicate_ids={','.join(duplicate_ids)}")
        if invalid_decision_ids:
            detail_parts.append(
                f"pending_or_empty_decisions={','.join(invalid_decision_ids)}"
            )
        if missing_notes_ids:
            detail_parts.append(f"missing_notes={','.join(missing_notes_ids)}")
        detail = "; ".join(detail_parts)
    return _validation_result(
        rule_id=field,
        status="pass" if passed else "fail",
        field=field,
        validation_rule=str(rule.get("validation_rule") or ""),
        expected=required_ids,
        actual=actual_ids,
        detail=detail,
    )


def _validation_result(
    *,
    rule_id: str,
    status: str,
    detail: str,
    field: Optional[str] = None,
    validation_rule: Optional[str] = None,
    expected: Any = None,
    actual: Any = None,
) -> Dict[str, Any]:
    return {
        "rule_id": str(rule_id),
        "status": str(status),
        "field": str(field) if field else None,
        "validation_rule": str(validation_rule) if validation_rule else None,
        "detail": str(detail),
        "expected": expected,
        "actual": actual,
    }


def _is_non_empty_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None


def _normalized_text(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def _normalize_path_text(path_text: str) -> str:
    return str(path_text).replace("\\", "/").strip()


def _path_shape_pattern(path_shape: str) -> str:
    normalized = _normalize_path_text(path_shape)
    if not normalized:
        return r".*"
    parts = re.split(r"(<[^>]+>)", normalized)
    pattern = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            pattern.append(r"[^/]+")
        else:
            pattern.append(re.escape(part))
    return "".join(pattern)


def _ensure_gate_entries(
    entries: list[Mapping[str, Any]],
    *,
    current_still_blocked_gate_ids: list[str],
    post_ingest_still_blocked_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        gate_id = str(entry.get("gate_id") or "").strip()
        if not gate_id or gate_id in seen:
            continue
        merged.append(
            {
                "gate_id": gate_id,
                "satisfied": bool(entry.get("satisfied", False)),
                "blocking": bool(entry.get("blocking", False)),
                "detail": str(entry.get("detail") or ""),
            }
        )
        seen.add(gate_id)
    for gate_id in current_still_blocked_gate_ids:
        gate_id_text = str(gate_id).strip()
        if not gate_id_text or gate_id_text in seen:
            continue
        merged.append(
            _gate(
                gate_id_text,
                False,
                True,
                "Current still-blocked gate preserved from the locked upstream review contracts.",
            )
        )
        seen.add(gate_id_text)
    for gate_id in post_ingest_still_blocked_gate_ids:
        gate_id_text = str(gate_id).strip()
        if not gate_id_text or gate_id_text in seen:
            continue
        merged.append(
            _gate(
                gate_id_text,
                False,
                True,
                "This gate must remain blocked even after future ingest-review record validation.",
            )
        )
        seen.add(gate_id_text)
    return merged


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


def _blocked_gate_entries(report: Optional[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    if not report:
        return []
    entries: list[Dict[str, Any]] = []
    for gate in list(report.get("gates", [])):
        if not isinstance(gate, Mapping):
            continue
        gate_id = str(gate.get("gate_id") or "").strip()
        if not gate_id:
            continue
        entries.append(
            {
                "gate_id": gate_id,
                "satisfied": bool(gate.get("satisfied", False)),
                "blocking": bool(gate.get("blocking", False)),
                "detail": str(gate.get("detail") or ""),
            }
        )
    return entries


def _merge_gate_entries(*gate_groups: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for gate_group in gate_groups:
        for entry in gate_group:
            gate_id = str(entry.get("gate_id") or "").strip()
            if not gate_id or gate_id in seen:
                continue
            merged.append(
                {
                    "gate_id": gate_id,
                    "satisfied": bool(entry.get("satisfied", False)),
                    "blocking": bool(entry.get("blocking", False)),
                    "detail": str(entry.get("detail") or ""),
                }
            )
            seen.add(gate_id)
    return merged


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
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing:{path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{path}:{exc.msg}"
    if not isinstance(data, dict):
        return None, f"not_mapping:{path}"
    return data, None


def _resolve_path(project_root: Path, path: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = project_root / resolved
    return resolved.resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path.resolve())


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

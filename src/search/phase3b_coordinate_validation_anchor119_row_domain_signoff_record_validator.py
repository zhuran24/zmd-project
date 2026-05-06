from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

SIGNOFF_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_v1"
)
REVIEWER_RECORD_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
DEFAULT_SIGNOFF_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_20260424/"
    "anchor119_row_domain_signoff_record_scaffold.json"
)
DEFAULT_REVIEWER_RECORD_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_20260424/"
    "anchor119_row_domain_reviewer_record_prep.json"
)
DEFAULT_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)
VALIDATOR_NOTICE = (
    "Validator contract only; optional reviewed runtime patch signoff payload "
    "validation is review-only/default-off. This artifact does not create or ingest "
    "a real signoff record, does not set reviewed_runtime_patch_exists=true, and "
    "does not allow runtime enablement."
)
ACTUAL_RECORD_VALIDATION_DETAIL = (
    "No actual reviewed runtime patch signoff record payload was supplied. The "
    "validator is ready as a contract only, and runtime remains disabled/default-off."
)
REVIEW_ONLY_VALIDATION_EFFECT_DETAIL = (
    "This validation is review-only/default-off: it does not create or infer a "
    "reviewer-signed record, does not ingest repo-side state, does not set "
    "reviewed_runtime_patch_exists=true, and does not allow runtime enablement."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
    project_root: Path,
    *,
    signoff_record_scaffold_path: Optional[Path] = None,
    reviewer_record_prep_path: Optional[Path] = None,
    signoff_bundle_path: Optional[Path] = None,
    signoff_record_payload_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    signoff_record_scaffold_resolved = _resolve_path(
        project_root,
        signoff_record_scaffold_path
        if signoff_record_scaffold_path is not None
        else DEFAULT_SIGNOFF_RECORD_SCAFFOLD_PATH,
    )
    reviewer_record_prep_resolved = _resolve_path(
        project_root,
        reviewer_record_prep_path
        if reviewer_record_prep_path is not None
        else DEFAULT_REVIEWER_RECORD_PREP_PATH,
    )
    signoff_bundle_resolved = _resolve_path(
        project_root,
        signoff_bundle_path if signoff_bundle_path is not None else DEFAULT_SIGNOFF_BUNDLE_PATH,
    )
    signoff_record_payload_resolved = (
        _resolve_path(project_root, signoff_record_payload_path)
        if signoff_record_payload_path is not None
        else None
    )

    signoff_record_scaffold_report, signoff_record_scaffold_error = _load_json_mapping(
        signoff_record_scaffold_resolved
    )
    reviewer_record_prep_report, reviewer_record_prep_error = _load_json_mapping(
        reviewer_record_prep_resolved
    )
    signoff_bundle_report, signoff_bundle_error = _load_json_mapping(
        signoff_bundle_resolved
    )

    scaffold_meta = (
        _mapping(signoff_record_scaffold_report.get("metadata"))
        if signoff_record_scaffold_report
        else {}
    )
    scaffold_status = (
        _mapping(signoff_record_scaffold_report.get("status"))
        if signoff_record_scaffold_report
        else {}
    )
    signoff_record_scaffold = (
        _mapping(signoff_record_scaffold_report.get("signoff_record_scaffold"))
        if signoff_record_scaffold_report
        else {}
    )
    reviewer_meta = (
        _mapping(reviewer_record_prep_report.get("metadata"))
        if reviewer_record_prep_report
        else {}
    )
    reviewer_status = (
        _mapping(reviewer_record_prep_report.get("status"))
        if reviewer_record_prep_report
        else {}
    )
    reviewer_record_prep = (
        _mapping(reviewer_record_prep_report.get("reviewer_record_prep"))
        if reviewer_record_prep_report
        else {}
    )
    signoff_meta = (
        _mapping(signoff_bundle_report.get("metadata")) if signoff_bundle_report else {}
    )
    signoff_status = (
        _mapping(signoff_bundle_report.get("status")) if signoff_bundle_report else {}
    )
    signoff_bundle = (
        _mapping(signoff_bundle_report.get("signoff_bundle"))
        if signoff_bundle_report
        else {}
    )
    candidate = (
        _mapping(signoff_record_scaffold_report.get("candidate"))
        if signoff_record_scaffold_report
        else _mapping(reviewer_record_prep_report.get("candidate"))
        if reviewer_record_prep_report
        else _mapping(signoff_bundle_report.get("candidate"))
        if signoff_bundle_report
        else {}
    )

    signoff_record_scaffold_present = bool(
        signoff_record_scaffold_report is not None
        and signoff_record_scaffold_error is None
        and scaffold_meta.get("source") == SIGNOFF_RECORD_SCAFFOLD_SOURCE
    )
    reviewer_record_prep_present = bool(
        reviewer_record_prep_report is not None
        and reviewer_record_prep_error is None
        and reviewer_meta.get("source") == REVIEWER_RECORD_PREP_SOURCE
    )
    signoff_bundle_present = bool(
        signoff_bundle_report is not None
        and signoff_bundle_error is None
        and signoff_meta.get("source") == RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE
    )

    signoff_record_scaffold_ready = bool(
        scaffold_status.get("signoff_record_scaffold_ready", False)
    )
    reviewer_record_prep_ready = bool(
        reviewer_status.get("reviewer_record_prep_ready", False)
    )
    signoff_bundle_ready = bool(signoff_status.get("signoff_bundle_ready", False))
    upstream_reviewed_runtime_patch_exists = bool(
        scaffold_status.get("reviewed_runtime_patch_exists", False)
        or reviewer_status.get("reviewed_runtime_patch_exists", False)
        or signoff_status.get("reviewed_runtime_patch_exists", False)
    )
    upstream_runtime_enablement_allowed = bool(
        scaffold_status.get("runtime_enablement_allowed", False)
        or reviewer_status.get("runtime_enablement_allowed", False)
        or signoff_status.get("runtime_enablement_allowed", False)
    )

    pending_signoff_record_payload = _mapping(
        signoff_record_scaffold.get("pending_signoff_record_payload")
    )
    required_record_fields = _mapping_list(
        signoff_record_scaffold.get("required_record_fields")
    )
    if not required_record_fields:
        required_record_fields = _mapping_list(
            reviewer_record_prep.get("required_record_fields")
        )

    required_statement_ids = _string_list(
        signoff_record_scaffold.get("required_reviewer_statement_ids")
    )
    if not required_statement_ids:
        required_statement_ids = _string_list(
            reviewer_record_prep.get("required_reviewer_statement_ids")
        )
    if not required_statement_ids:
        required_statement_ids = [
            str(entry.get("statement_id"))
            for entry in list(signoff_bundle.get("required_reviewer_statements", []))
            if isinstance(entry, Mapping) and entry.get("statement_id")
        ]

    carry_forward_gate_entries = _merge_gate_entries(
        _blocked_gate_entries(signoff_record_scaffold_report),
        _blocked_gate_entries(reviewer_record_prep_report),
        _blocked_gate_entries(signoff_bundle_report),
    )
    carry_forward_still_blocked_gate_ids = _string_list(
        signoff_record_scaffold_report.get("still_blocked_gate_ids")
        if signoff_record_scaffold_report
        else []
    )
    if not carry_forward_still_blocked_gate_ids:
        carry_forward_still_blocked_gate_ids = _string_list(
            pending_signoff_record_payload.get("still_blocked_gate_ids")
        )
    if not carry_forward_still_blocked_gate_ids:
        carry_forward_still_blocked_gate_ids = _string_list(
            reviewer_record_prep_report.get("still_blocked_gate_ids")
            if reviewer_record_prep_report
            else []
        )
    if not carry_forward_still_blocked_gate_ids:
        carry_forward_still_blocked_gate_ids = [
            str(entry.get("gate_id"))
            for entry in carry_forward_gate_entries
            if entry.get("gate_id")
        ]

    required_field_rules = _build_required_field_rules(
        required_record_fields,
        template_payload=pending_signoff_record_payload,
    )
    agreed_statement_ids_rule = _build_agreed_statement_ids_rule(required_statement_ids)
    still_blocked_gate_ids_rule = _build_still_blocked_gate_ids_rule(
        carry_forward_still_blocked_gate_ids
    )

    required_field_rules_ready = bool(required_field_rules)
    agreed_statement_ids_rule_ready = bool(agreed_statement_ids_rule)
    still_blocked_gate_ids_rule_ready = bool(still_blocked_gate_ids_rule)
    default_off_retained = bool(
        signoff_record_scaffold_present
        and reviewer_record_prep_present
        and signoff_bundle_present
        and bool(scaffold_meta.get("default_off", False))
        and bool(reviewer_meta.get("default_off", False))
        and bool(signoff_meta.get("default_off", False))
        and not upstream_runtime_enablement_allowed
    )

    gates = [
        {
            "gate_id": "signoff_record_scaffold_ready",
            "satisfied": bool(signoff_record_scaffold_ready),
            "blocking": not bool(signoff_record_scaffold_ready),
            "detail": "The validator contract depends on the pending signoff record scaffold already being ready.",
        },
        {
            "gate_id": "reviewer_record_prep_ready",
            "satisfied": bool(reviewer_record_prep_ready),
            "blocking": not bool(reviewer_record_prep_ready),
            "detail": "The validator contract depends on reviewer-record prep already being ready.",
        },
        {
            "gate_id": "signoff_bundle_ready",
            "satisfied": bool(signoff_bundle_ready),
            "blocking": not bool(signoff_bundle_ready),
            "detail": "The validator contract depends on the runtime patch signoff bundle already being ready.",
        },
        {
            "gate_id": "validator_required_field_rules_ready",
            "satisfied": bool(required_field_rules_ready),
            "blocking": not bool(required_field_rules_ready),
            "detail": "Required field validation rules must be derivable from the scaffold/template inputs.",
        },
        {
            "gate_id": "validator_agreed_statement_ids_rule_ready",
            "satisfied": bool(agreed_statement_ids_rule_ready),
            "blocking": not bool(agreed_statement_ids_rule_ready),
            "detail": "The validator must carry explicit agreed_statement_ids rules from the reviewer statements.",
        },
        {
            "gate_id": "validator_still_blocked_gate_ids_rule_ready",
            "satisfied": bool(still_blocked_gate_ids_rule_ready),
            "blocking": not bool(still_blocked_gate_ids_rule_ready),
            "detail": "The validator must carry explicit still_blocked_gate_ids rules that preserve the current blocked gates.",
        },
        {
            "gate_id": "default_off_retained_for_validator",
            "satisfied": bool(default_off_retained),
            "blocking": not bool(default_off_retained),
            "detail": "This validator remains explicit default-off and does not imply runtime enablement.",
        },
        {
            "gate_id": "actual_signoff_record_payload_validated",
            "satisfied": False,
            "blocking": False,
            "detail": ACTUAL_RECORD_VALIDATION_DETAIL,
        },
    ]
    gates.extend(carry_forward_gate_entries)

    base_checks = [
        _check(
            "signoff_record_scaffold_present",
            "pass" if signoff_record_scaffold_present else "fail",
            "signoff record scaffold loaded"
            if signoff_record_scaffold_present
            else signoff_record_scaffold_error
            or (
                f"unexpected_source:{scaffold_meta.get('source')}"
                if signoff_record_scaffold_report is not None
                else f"missing:{_display_path(project_root, signoff_record_scaffold_resolved)}"
            ),
        ),
        _check(
            "reviewer_record_prep_present",
            "pass" if reviewer_record_prep_present else "fail",
            "reviewer record prep loaded"
            if reviewer_record_prep_present
            else reviewer_record_prep_error
            or (
                f"unexpected_source:{reviewer_meta.get('source')}"
                if reviewer_record_prep_report is not None
                else f"missing:{_display_path(project_root, reviewer_record_prep_resolved)}"
            ),
        ),
        _check(
            "signoff_bundle_present",
            "pass" if signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if signoff_bundle_present
            else signoff_bundle_error
            or (
                f"unexpected_source:{signoff_meta.get('source')}"
                if signoff_bundle_report is not None
                else f"missing:{_display_path(project_root, signoff_bundle_resolved)}"
            ),
        ),
        _check(
            "signoff_record_scaffold_ready",
            "pass" if signoff_record_scaffold_ready else "fail",
            str(signoff_record_scaffold_ready),
        ),
        _check(
            "reviewer_record_prep_ready",
            "pass" if reviewer_record_prep_ready else "fail",
            str(reviewer_record_prep_ready),
        ),
        _check(
            "signoff_bundle_ready",
            "pass" if signoff_bundle_ready else "fail",
            str(signoff_bundle_ready),
        ),
        _check(
            "required_field_rules_ready",
            "pass" if required_field_rules_ready else "fail",
            ",".join(rule["field"] for rule in required_field_rules)
            if required_field_rules_ready
            else "missing",
        ),
        _check(
            "agreed_statement_ids_rule_ready",
            "pass" if agreed_statement_ids_rule_ready else "fail",
            ",".join(_string_list(agreed_statement_ids_rule.get("required_ids")))
            if agreed_statement_ids_rule_ready
            else "missing",
        ),
        _check(
            "still_blocked_gate_ids_rule_ready",
            "pass" if still_blocked_gate_ids_rule_ready else "fail",
            ",".join(_string_list(still_blocked_gate_ids_rule.get("required_ids")))
            if still_blocked_gate_ids_rule_ready
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

    signoff_record_validator_ready = all(
        check["status"] == "pass" for check in base_checks
    )
    actual_record_validation = _validate_optional_signoff_record_payload(
        project_root=project_root,
        payload_path=signoff_record_payload_resolved,
        validator_ready=signoff_record_validator_ready,
        required_field_rules=required_field_rules,
        agreed_statement_ids_rule=agreed_statement_ids_rule,
        still_blocked_gate_ids_rule=still_blocked_gate_ids_rule,
    )
    supplied_record_payload_provided = bool(
        actual_record_validation.get("record_payload_provided", False)
    )
    supplied_record_payload_loaded = bool(
        actual_record_validation.get("record_payload_loaded", False)
    )
    supplied_record_payload_validated = bool(
        actual_record_validation.get("record_payload_validated", False)
    )
    checks = list(base_checks)
    if supplied_record_payload_provided:
        checks.extend(
            [
                _check(
                    "signoff_record_payload_loaded",
                    "pass" if supplied_record_payload_loaded else "fail",
                    str(actual_record_validation.get("detail")),
                ),
                _check(
                    "actual_signoff_record_payload_validated",
                    "pass" if supplied_record_payload_validated else "fail",
                    str(actual_record_validation.get("detail")),
                ),
            ]
        )
    else:
        checks.append(
            _check(
                "actual_signoff_record_validation_not_run",
                "pass",
                ACTUAL_RECORD_VALIDATION_DETAIL,
            )
        )
    for gate in gates:
        if gate.get("gate_id") == "actual_signoff_record_payload_validated":
            gate["satisfied"] = supplied_record_payload_validated
            gate["detail"] = str(actual_record_validation.get("detail"))
    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    if not signoff_record_validator_ready:
        recommended_next_step = (
            "repair_signoff_record_validator_inputs_then_revalidate_payload"
            if supplied_record_payload_provided
            else "repair_signoff_record_validator_inputs"
        )
        handoff_recommendation = (
            "Validator contract is blocked; repair the missing scaffold/reviewer-prep/"
            "signoff-bundle prerequisites before validating any future signoff payload."
        )
    elif supplied_record_payload_validated:
        recommended_next_step = (
            "review_only_validated_signoff_record_payload_retains_blocked_gates"
        )
        handoff_recommendation = (
            "A supplied reviewed runtime patch signoff payload validated against the "
            "locked required fields, agreed reviewer statement ids, and still-blocked "
            "gate ids. This remains review-only/default-off: no reviewer-signed "
            "record is created or ingested, reviewed_runtime_patch_exists=false "
            "remains locked, and runtime_enablement_allowed=false remains locked."
        )
    elif supplied_record_payload_provided:
        recommended_next_step = (
            "repair_supplied_signoff_record_payload_against_locked_contract"
        )
        handoff_recommendation = (
            "A supplied reviewed runtime patch signoff payload failed validation. "
            "Repair the failed rules and re-run this validator; this artifact still "
            "does not create or ingest a reviewer-signed record, set "
            "reviewed_runtime_patch_exists=true, or allow runtime enablement."
        )
    else:
        recommended_next_step = (
            "handoff_signoff_record_validator_contract_for_future_record_validation"
        )
        handoff_recommendation = (
            "Validator contract is ready: use it to compare a future reviewed runtime "
            "patch signoff record payload against the scaffolded required fields, "
            "agreed reviewer statement ids, and still-blocked gate ids. This artifact "
            "does not validate an actual signed record yet, does not set "
            "reviewed_runtime_patch_exists=true, and does not allow runtime enablement."
        )

    return {
        "metadata": {
            "source": SIGNOFF_RECORD_VALIDATOR_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_signoff_record_validator_contract_not_actual_signoff",
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "signoff_record_scaffold": _display_path(
                project_root, signoff_record_scaffold_resolved
            ),
            "reviewer_record_prep": _display_path(
                project_root, reviewer_record_prep_resolved
            ),
            "signoff_bundle": _display_path(project_root, signoff_bundle_resolved),
            "signoff_record_payload": (
                _display_path(project_root, signoff_record_payload_resolved)
                if signoff_record_payload_resolved is not None
                else None
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "signoff_record_validator_ready": bool(signoff_record_validator_ready),
            "signoff_record_payload_provided": supplied_record_payload_provided,
            "signoff_record_payload_validated": supplied_record_payload_validated,
            "signoff_record_payload_validation_status": str(
                actual_record_validation.get("validation_status")
            ),
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "signoff_record_validator": {
            "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
            "target_record_type": pending_signoff_record_payload.get("record_type")
            or signoff_record_scaffold.get("record_type")
            or reviewer_record_prep.get("record_type"),
            "scope": pending_signoff_record_payload.get("scope")
            or signoff_record_scaffold.get("scope")
            or reviewer_record_prep.get("scope")
            or signoff_bundle.get("scope"),
            "expected_template_payload": dict(pending_signoff_record_payload),
            "required_reviewer_statement_ids": list(required_statement_ids),
            "validator_rules": {
                "required_fields": required_field_rules,
                "agreed_statement_ids": agreed_statement_ids_rule,
                "still_blocked_gate_ids": still_blocked_gate_ids_rule,
            },
            "actual_record_validation": actual_record_validation,
            "validator_notice": VALIDATOR_NOTICE,
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("signoff_record_validator"))
    validator_rules = _mapping(validator.get("validator_rules"))
    actual_validation = _mapping(validator.get("actual_record_validation"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Signoff Record Validator",
        "",
        f"- Signoff record validator ready: `{status.get('signoff_record_validator_ready')}`",
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
        f"- Required reviewer statement ids: `{', '.join(_string_list(validator.get('required_reviewer_statement_ids'))) or '(none)'}`",
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
        f"- Failed rule ids: `{', '.join(_string_list(actual_validation.get('failed_rule_ids'))) or '(none)'}`",
        f"- Detail: {actual_validation.get('detail')}",
        "",
        "## Per-Rule Validation Results",
        "",
    ]
    rule_results = [
        entry
        for entry in list(actual_validation.get("rule_results", []))
        if isinstance(entry, Mapping)
    ]
    if rule_results:
        lines.extend(
            [
                "| Rule | Status | Field | Validation rule | Observed value | Expected value | Detail |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in rule_results:
            lines.append(
                f"| {_markdown_cell(entry.get('rule_id'))} | "
                f"{_markdown_cell(entry.get('status'))} | "
                f"{_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('validation_rule'))} | "
                f"{_markdown_cell(_render_value(entry.get('observed_value')))} | "
                f"{_markdown_cell(_render_value(entry.get('expected_value')))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    else:
        lines.append(
            "- Per-rule validation results: not run because no payload was supplied."
        )
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
    agreed_rule = _mapping(validator_rules.get("agreed_statement_ids"))
    lines.extend(
        [
            "",
            "## Agreed Statement Ids Rule",
            "",
            f"- Required ids: `{', '.join(_string_list(agreed_rule.get('required_ids'))) or '(none)'}`",
            f"- Validation rule: `{agreed_rule.get('validation_rule')}`",
            f"- Detail: {agreed_rule.get('detail')}",
        ]
    )
    blocked_rule = _mapping(validator_rules.get("still_blocked_gate_ids"))
    lines.extend(
        [
            "",
            "## Still Blocked Gate Ids Rule",
            "",
            f"- Required ids: `{', '.join(_string_list(blocked_rule.get('required_ids'))) or '(none)'}`",
            f"- Validation rule: `{blocked_rule.get('validation_rule')}`",
            f"- Detail: {blocked_rule.get('detail')}",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("signoff_record_validator"))
    actual_validation = _mapping(validator.get("actual_record_validation"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain signoff record validator",
            f"signoff_record_validator_ready={status.get('signoff_record_validator_ready')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            f"target_record_type={validator.get('target_record_type')}",
            f"scope={validator.get('scope')}",
            f"actual_record_payload_provided={actual_validation.get('record_payload_provided')}",
            f"actual_record_payload_path={actual_validation.get('record_payload_path')}",
            f"actual_record_payload_validated={actual_validation.get('record_payload_validated')}",
            f"actual_record_validation_status={actual_validation.get('validation_status')}",
            "actual_record_validation_failed_rule_ids="
            + ",".join(_string_list(actual_validation.get("failed_rule_ids"))),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_signoff_record_validator",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _validate_optional_signoff_record_payload(
    *,
    project_root: Path,
    payload_path: Optional[Path],
    validator_ready: bool,
    required_field_rules: list[Mapping[str, Any]],
    agreed_statement_ids_rule: Mapping[str, Any],
    still_blocked_gate_ids_rule: Mapping[str, Any],
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
            "failed_rule_ids": [],
            "rule_results": [],
            "detail": ACTUAL_RECORD_VALIDATION_DETAIL,
        }

    payload_display_path = _display_path(project_root, payload_path)
    payload_report, payload_error = _load_json_mapping(payload_path)
    if payload_report is None or payload_error is not None:
        detail = (
            f"Supplied signoff record payload could not be loaded from "
            f"`{payload_display_path}`: {payload_error or 'unknown_error'}. "
            "Repair/revalidate the supplied payload before any review use. "
            f"{REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        load_result = _validation_result(
            rule_id="payload_load",
            status="fail",
            field="signoff_record_payload",
            validation_rule="must_load_json_mapping",
            observed_value=payload_display_path,
            expected_value="readable_json_object",
            detail=detail,
        )
        return {
            "record_payload_provided": True,
            "record_payload_path": payload_display_path,
            "record_payload_loaded": False,
            "record_payload_validated": False,
            "validation_status": "load_error",
            "passed_rule_count": 0,
            "failed_rule_count": 1,
            "failed_rule_ids": ["payload_load"],
            "rule_results": [load_result],
            "detail": detail,
        }

    if not validator_ready:
        detail = (
            "A signoff record payload path was supplied, but the validator contract "
            "is not ready because upstream scaffold/reviewer-prep/signoff-bundle "
            "inputs are still blocked. Repair the validator inputs, then "
            f"revalidate the supplied payload. {REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        ready_result = _validation_result(
            rule_id="validator_contract_ready",
            status="fail",
            validation_rule="must_be_ready_before_payload_validation",
            observed_value=False,
            expected_value=True,
            detail=detail,
        )
        return {
            "record_payload_provided": True,
            "record_payload_path": payload_display_path,
            "record_payload_loaded": True,
            "record_payload_validated": False,
            "validation_status": "contract_blocked",
            "passed_rule_count": 0,
            "failed_rule_count": 1,
            "failed_rule_ids": ["validator_contract_ready"],
            "rule_results": [ready_result],
            "detail": detail,
        }

    payload = _mapping(payload_report)
    rule_results: list[Dict[str, Any]] = []
    rule_results.extend(
        _evaluate_required_field_rules(required_field_rules, payload=payload)
    )
    rule_results.append(
        _evaluate_agreed_statement_ids_rule(agreed_statement_ids_rule, payload=payload)
    )
    rule_results.append(
        _evaluate_still_blocked_gate_ids_rule(
            still_blocked_gate_ids_rule,
            payload=payload,
        )
    )

    failed_rule_ids = [
        str(entry.get("rule_id"))
        for entry in rule_results
        if str(entry.get("status")) == "fail"
    ]
    failed_rule_count = len(failed_rule_ids)
    passed_rule_count = sum(
        1 for entry in rule_results if str(entry.get("status")) == "pass"
    )
    record_payload_validated = bool(rule_results) and failed_rule_count == 0
    if record_payload_validated:
        detail = (
            f"Supplied signoff record payload at `{payload_display_path}` validated "
            "against signoff_record_validator.validator_rules. "
            f"{REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        validation_status = "passed"
    else:
        detail = (
            f"Supplied signoff record payload at `{payload_display_path}` failed "
            f"{failed_rule_count} validation rule(s): "
            f"{', '.join(failed_rule_ids) or '(none)'}. Repair/revalidate the "
            "supplied payload against the locked signoff_record_validator."
            f" {REVIEW_ONLY_VALIDATION_EFFECT_DETAIL}"
        )
        validation_status = "failed"
    return {
        "record_payload_provided": True,
        "record_payload_path": payload_display_path,
        "record_payload_loaded": True,
        "record_payload_validated": record_payload_validated,
        "validation_status": validation_status,
        "passed_rule_count": passed_rule_count,
        "failed_rule_count": failed_rule_count,
        "failed_rule_ids": failed_rule_ids,
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
        if isinstance(rule, Mapping):
            results.append(_evaluate_required_field_rule(rule, payload=payload))
    return results


def _evaluate_required_field_rule(
    rule: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    field = str(rule.get("field") or "").strip()
    validation_rule = str(rule.get("validation_rule") or "").strip()
    expected_value = rule.get("template_value")
    field_present = field in payload
    observed_value = payload.get(field)
    if validation_rule == "must_equal_template_value":
        passed = field_present and observed_value == expected_value
        detail = (
            "Field matches the locked template value."
            if passed
            else "Field must match the locked template value exactly."
        )
    elif validation_rule == "must_be_present_and_non_empty":
        passed = field_present and _is_non_empty_value(observed_value)
        detail = (
            "Field is present and non-empty."
            if passed
            else "Field must be present and non-empty."
        )
    elif validation_rule == "must_be_iso8601_utc_timestamp":
        passed = field_present and _is_iso8601_utc_timestamp(observed_value)
        detail = (
            "Field is present as an ISO-8601 UTC timestamp ending in Z."
            if passed
            else "Field must be an ISO-8601 UTC timestamp ending in Z."
        )
    elif validation_rule == "must_be_present_and_non_empty_string":
        passed = (
            field_present
            and isinstance(observed_value, str)
            and bool(observed_value.strip())
        )
        detail = (
            "Field is present as a non-empty string."
            if passed
            else "Field must be present as a non-empty string."
        )
    elif validation_rule.startswith("validated_by_"):
        passed = field_present
        detail = (
            "Field is present and evaluated by its dedicated rule."
            if passed
            else "Field is missing, so its dedicated rule cannot pass."
        )
    elif validation_rule == "must_be_present":
        passed = field_present
        detail = "Field is present." if passed else "Field must be present."
    else:
        passed = field_present
        detail = (
            "Field is present; no specialized evaluator was required."
            if passed
            else "Field is missing from the supplied payload."
        )
    return _validation_result(
        rule_id=f"required_field:{field or 'missing_field'}",
        status="pass" if passed else "fail",
        field=field,
        validation_rule=validation_rule,
        observed_value=observed_value,
        expected_value=expected_value,
        detail=detail,
    )


def _evaluate_agreed_statement_ids_rule(
    rule: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    return _evaluate_id_set_rule(
        rule,
        payload=payload,
        rule_id="agreed_statement_ids",
        require_exact_order=False,
    )


def _evaluate_still_blocked_gate_ids_rule(
    rule: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    return _evaluate_id_set_rule(
        rule,
        payload=payload,
        rule_id="still_blocked_gate_ids",
        require_exact_order=True,
    )


def _evaluate_id_set_rule(
    rule: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
    rule_id: str,
    require_exact_order: bool,
) -> Dict[str, Any]:
    field = str(rule.get("field") or rule_id).strip()
    expected_ids = _string_list(rule.get("required_ids"))
    observed_ids = _string_list(payload.get(field))
    missing_ids = [entry for entry in expected_ids if entry not in observed_ids]
    extra_ids = [entry for entry in observed_ids if entry not in expected_ids]
    duplicate_ids = sorted(
        {
            entry
            for entry in observed_ids
            if observed_ids.count(entry) > 1 and entry
        }
    )
    order_mismatch = require_exact_order and observed_ids != expected_ids
    passed = (
        field in payload
        and bool(expected_ids)
        and not missing_ids
        and not extra_ids
        and not duplicate_ids
        and not order_mismatch
    )
    detail_parts = []
    if field not in payload:
        detail_parts.append("field_missing")
    if missing_ids:
        detail_parts.append("missing_ids=" + ",".join(missing_ids))
    if extra_ids:
        detail_parts.append("extra_ids=" + ",".join(extra_ids))
    if duplicate_ids:
        detail_parts.append("duplicate_ids=" + ",".join(duplicate_ids))
    if order_mismatch and not (missing_ids or extra_ids or duplicate_ids):
        detail_parts.append("order_mismatch")
    if not expected_ids:
        detail_parts.append("required_ids_missing_from_validator_rule")
    if not detail_parts:
        detail_parts.append("locked ids satisfied")
    return _validation_result(
        rule_id=rule_id,
        status="pass" if passed else "fail",
        field=field,
        validation_rule=str(rule.get("validation_rule") or ""),
        observed_value=observed_ids,
        expected_value=expected_ids,
        detail="; ".join(detail_parts),
    )


def _validation_result(
    *,
    rule_id: str,
    status: str,
    detail: str,
    field: Optional[str] = None,
    validation_rule: Optional[str] = None,
    observed_value: Any = None,
    expected_value: Any = None,
) -> Dict[str, Any]:
    return {
        "rule_id": str(rule_id),
        "status": str(status),
        "field": str(field) if field else None,
        "validation_rule": str(validation_rule) if validation_rule else None,
        "observed_value": observed_value,
        "expected_value": expected_value,
        "detail": str(detail),
    }


def _is_non_empty_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None


def _is_iso8601_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return False
    return bool(parsed.tzinfo and parsed.utcoffset() == timedelta(0))


def _build_required_field_rules(
    required_record_fields: list[Mapping[str, Any]],
    *,
    template_payload: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    rules: list[Dict[str, Any]] = []
    for entry in required_record_fields:
        field = str(entry.get("field") or "").strip()
        if not field:
            continue
        template_value = template_payload.get(field, entry.get("template_value"))
        validation_rule, validator_detail = _derive_field_validation_rule(
            field, template_value
        )
        rules.append(
            {
                "field": field,
                "required": bool(entry.get("required", False)),
                "template_value": template_value,
                "detail": str(entry.get("detail") or ""),
                "validation_rule": validation_rule,
                "validator_detail": validator_detail,
            }
        )
    return rules


def _derive_field_validation_rule(field: str, template_value: Any) -> tuple[str, str]:
    if field in {"record_type", "scope"}:
        return (
            "must_equal_template_value",
            "Future payload must carry forward this exact template value.",
        )
    if field in {"reviewer_id", "notes"}:
        return (
            "must_be_present_and_non_empty",
            "Future payload must replace the empty scaffold placeholder with a non-empty reviewer-provided value.",
        )
    if field == "reviewed_at":
        return (
            "must_be_iso8601_utc_timestamp",
            "Future payload must provide a reviewer-supplied ISO-8601 UTC timestamp ending in Z.",
        )
    if field == "verdict":
        return (
            "must_be_present_and_non_empty_string",
            "Future payload must provide a non-empty reviewer verdict string, but this contract does not interpret any verdict as runtime enablement.",
        )
    if field == "agreed_statement_ids":
        return (
            "validated_by_agreed_statement_ids_rule",
            "This field is validated by the explicit agreed_statement_ids rule below.",
        )
    if field == "still_blocked_gate_ids":
        return (
            "validated_by_still_blocked_gate_ids_rule",
            "This field is validated by the explicit still_blocked_gate_ids rule below.",
        )
    return (
        "must_be_present",
        f"Future payload must provide `{field}` and keep it compatible with the scaffold/template value `{template_value}`.",
    )


def _build_agreed_statement_ids_rule(required_statement_ids: list[str]) -> Dict[str, Any]:
    if not required_statement_ids:
        return {}
    return {
        "field": "agreed_statement_ids",
        "required": True,
        "required_ids": list(required_statement_ids),
        "validation_rule": "must_include_all_required_ids_and_no_unapproved_ids",
        "detail": "Future payload must explicitly agree to every required reviewer statement id from the scaffold/signoff bundle. This remains a review contract only and does not imply enablement.",
    }


def _build_still_blocked_gate_ids_rule(
    carry_forward_still_blocked_gate_ids: list[str],
) -> Dict[str, Any]:
    if not carry_forward_still_blocked_gate_ids:
        return {}
    return {
        "field": "still_blocked_gate_ids",
        "required": True,
        "required_ids": list(carry_forward_still_blocked_gate_ids),
        "validation_rule": "must_match_scaffold_blocked_gate_ids_until_upstream_contract_changes",
        "detail": "Future payload must preserve these scaffolded blocked gate ids unless the upstream signoff contract is revised. Validating this field does not set reviewed_runtime_patch_exists=true and does not allow runtime enablement.",
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


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

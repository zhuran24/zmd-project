from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_scaffold_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_bundle_v1"
)
ACCEPTANCE_EXECUTION_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
)
ACCEPTANCE_RESULT_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_result_validator_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_validator_v1"
)
LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_scaffold_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_scaffold.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_bundle.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_execution_gate_20260424/"
    "anchor119_row_domain_acceptance_execution_gate.json"
)
DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_result_validator_20260424/"
    "anchor119_row_domain_acceptance_result_validator.json"
)
VALIDATOR_NOTICE = (
    "Validator contract only; no actual acceptance-authorization review record "
    "payload has been provided or validated. This artifact does not authorize "
    "execution, does not allow runtime enablement, and does not execute acceptance."
)
ACTUAL_RECORD_VALIDATION_DETAIL = (
    "No actual acceptance-authorization review record payload was supplied. The "
    "validator is ready as a contract only, and "
    "acceptance_execution_authorized=false, runtime_enablement_allowed=false, and "
    "acceptance_executed=false remain locked here."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
    project_root: Path,
    *,
    acceptance_authorization_review_record_scaffold_path: Optional[Path] = None,
    acceptance_authorization_review_bundle_path: Optional[Path] = None,
    acceptance_execution_gate_path: Optional[Path] = None,
    acceptance_result_validator_path: Optional[Path] = None,
    acceptance_authorization_review_record_payload_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    scaffold_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_record_scaffold_path
        if acceptance_authorization_review_record_scaffold_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_PATH,
    )
    bundle_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_bundle_path
        if acceptance_authorization_review_bundle_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_PATH,
    )
    gate_resolved = _resolve_path(
        project_root,
        acceptance_execution_gate_path
        if acceptance_execution_gate_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH,
    )
    result_validator_resolved = _resolve_path(
        project_root,
        acceptance_result_validator_path
        if acceptance_result_validator_path is not None
        else DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH,
    )
    record_payload_resolved = (
        _resolve_path(project_root, acceptance_authorization_review_record_payload_path)
        if acceptance_authorization_review_record_payload_path is not None
        else None
    )

    scaffold_report, scaffold_error = _load_json_mapping(scaffold_resolved)
    bundle_report, bundle_error = _load_json_mapping(bundle_resolved)
    gate_report, gate_error = _load_json_mapping(gate_resolved)
    result_validator_report, result_validator_error = _load_json_mapping(
        result_validator_resolved
    )

    scaffold_meta = (
        _mapping(scaffold_report.get("metadata")) if scaffold_report else {}
    )
    scaffold_status = (
        _mapping(scaffold_report.get("status")) if scaffold_report else {}
    )
    scaffold = (
        _mapping(
            scaffold_report.get("acceptance_authorization_review_record_scaffold")
        )
        if scaffold_report
        else {}
    )
    bundle_meta = _mapping(bundle_report.get("metadata")) if bundle_report else {}
    bundle_status = _mapping(bundle_report.get("status")) if bundle_report else {}
    bundle = (
        _mapping(bundle_report.get("acceptance_authorization_review_bundle"))
        if bundle_report
        else {}
    )
    gate_meta = _mapping(gate_report.get("metadata")) if gate_report else {}
    gate_status = _mapping(gate_report.get("status")) if gate_report else {}
    gate = _mapping(gate_report.get("acceptance_execution_gate")) if gate_report else {}
    result_validator_meta = (
        _mapping(result_validator_report.get("metadata"))
        if result_validator_report
        else {}
    )
    result_validator_status = (
        _mapping(result_validator_report.get("status"))
        if result_validator_report
        else {}
    )
    result_validator = (
        _mapping(result_validator_report.get("acceptance_result_validator"))
        if result_validator_report
        else {}
    )
    candidate = _first_mapping(
        scaffold_report.get("candidate") if scaffold_report else None,
        bundle_report.get("candidate") if bundle_report else None,
        gate_report.get("candidate") if gate_report else None,
        result_validator_report.get("candidate") if result_validator_report else None,
    )

    scaffold_present = bool(
        scaffold_report is not None
        and scaffold_error is None
        and scaffold_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE
    )
    bundle_present = bool(
        bundle_report is not None
        and bundle_error is None
        and bundle_meta.get("source") == ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE
    )
    gate_present = bool(
        gate_report is not None
        and gate_error is None
        and gate_meta.get("source") == ACCEPTANCE_EXECUTION_GATE_SOURCE
    )
    result_validator_present = bool(
        result_validator_report is not None
        and result_validator_error is None
        and result_validator_meta.get("source") == ACCEPTANCE_RESULT_VALIDATOR_SOURCE
    )

    scaffold_ready = bool(
        scaffold_status.get(
            "acceptance_authorization_review_record_scaffold_ready", False
        )
    )
    bundle_ready = bool(
        bundle_status.get("acceptance_authorization_review_bundle_ready", False)
    )
    gate_ready = bool(gate_status.get("acceptance_execution_gate_ready", False))
    result_validator_ready = bool(
        result_validator_status.get("acceptance_result_validator_ready", False)
    )

    scaffold_payload = _mapping(
        scaffold.get("scaffolded_authorization_review_record_payload")
    )
    scaffold_locked_execution_target = _mapping(scaffold.get("locked_execution_target"))
    bundle_locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    gate_locked_execution_target = _mapping(gate.get("locked_execution_target"))

    production_profile_id, production_profile_locked = _locked_value(
        [
            scaffold_locked_execution_target.get("production_profile_id"),
            bundle_locked_execution_target.get("production_profile_id"),
            gate_locked_execution_target.get("production_profile_id"),
            scaffold.get("production_profile_id"),
            bundle.get("production_profile_id"),
            gate.get("production_profile_id"),
            result_validator.get("production_profile_id"),
        ]
    )
    default_production_runner, default_production_runner_locked = _locked_value(
        [
            scaffold_locked_execution_target.get("default_production_runner"),
            bundle_locked_execution_target.get("default_production_runner"),
            gate_locked_execution_target.get("default_production_runner"),
        ],
        normalize=_normalize_path_text,
    )
    exact_future_acceptance_command, exact_future_acceptance_command_locked = (
        _locked_value(
            [
                scaffold_locked_execution_target.get("exact_future_acceptance_command"),
                bundle_locked_execution_target.get("exact_future_acceptance_command"),
                gate_locked_execution_target.get("exact_future_acceptance_command"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_locked = (
        _locked_value(
            [
                scaffold_locked_execution_target.get(
                    "exact_future_acceptance_result_path"
                ),
                bundle_locked_execution_target.get(
                    "exact_future_acceptance_result_path"
                ),
                gate_locked_execution_target.get("exact_future_acceptance_result_path"),
                result_validator.get("expected_result_path"),
            ],
            normalize=_normalize_path_text,
        )
    )
    command_output_path = _extract_suite_output_path(exact_future_acceptance_command)
    command_matches_result_path = bool(
        exact_future_acceptance_result_path
        and command_output_path
        and _normalize_path_text(exact_future_acceptance_result_path)
        == _normalize_path_text(command_output_path)
    )
    production_profile_locked_prod_4x4_normal = bool(
        production_profile_locked and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )
    locked_execution_target_present = bool(
        production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
        and exact_future_acceptance_command
        and exact_future_acceptance_result_path
    )
    locked_execution_target_consistent = bool(
        locked_execution_target_present
        and production_profile_locked_prod_4x4_normal
        and default_production_runner_locked
        and exact_future_acceptance_command_locked
        and exact_future_acceptance_result_path_locked
        and command_matches_result_path
    )

    required_record_fields = _mapping_list(scaffold.get("required_record_fields"))
    required_review_conclusions = _mapping_list(scaffold.get("required_review_conclusions"))
    required_conclusion_ids = [
        str(entry.get("conclusion_id"))
        for entry in required_review_conclusions
        if str(entry.get("conclusion_id") or "").strip()
    ]
    required_runtime_patch_statement_ids = _string_list(
        scaffold.get("required_runtime_patch_statement_ids")
    )
    if not required_runtime_patch_statement_ids:
        required_runtime_patch_statement_ids = _string_list(
            scaffold_payload.get("required_runtime_patch_statement_ids")
        )
    if not required_runtime_patch_statement_ids:
        required_runtime_patch_statement_ids = _string_list(
            _mapping(bundle.get("reviewed_runtime_patch_state")).get(
                "required_reviewer_statement_ids"
            )
        )

    carry_forward_gate_entries = _merge_gate_entries(
        _blocked_gate_entries(scaffold_report),
        _blocked_gate_entries(bundle_report),
        _blocked_gate_entries(gate_report),
    )
    missing_prerequisites = _build_missing_prerequisites(
        scaffold.get("missing_prerequisites"),
        carry_forward_gate_entries=carry_forward_gate_entries,
        scaffold_reported_missing_gate_ids=_string_list(
            scaffold_status.get("missing_prerequisite_gate_ids")
        ),
        bundle_reported_missing_gate_ids=_string_list(
            bundle_status.get("missing_prerequisite_gate_ids")
        ),
        gate_reported_missing_gate_ids=_string_list(
            gate_status.get("missing_prerequisite_gate_ids")
        ),
    )
    missing_prerequisite_gate_ids = [
        str(entry.get("gate_id"))
        for entry in missing_prerequisites
        if str(entry.get("gate_id") or "").strip()
    ]

    acceptance_execution_authorized = any(
        bool(value)
        for value in [
            scaffold_status.get("acceptance_execution_authorized", False),
            bundle_status.get("acceptance_execution_authorized", False),
            gate_status.get("acceptance_execution_authorized", False),
        ]
    )
    runtime_enablement_still_blocked = all(
        not bool(value)
        for value in [
            scaffold_status.get("runtime_enablement_allowed", False),
            bundle_status.get("runtime_enablement_allowed", False),
            gate_status.get("runtime_enablement_allowed", False),
            result_validator_status.get("runtime_enablement_allowed", False),
            scaffold_payload.get("runtime_enablement_allowed", False),
        ]
    )
    acceptance_executed = any(
        bool(value)
        for value in [
            scaffold_status.get("acceptance_executed", False),
            bundle_status.get("acceptance_executed", False),
            gate_status.get("acceptance_executed", False),
            scaffold_meta.get("acceptance_executed", False),
            bundle_meta.get("acceptance_executed", False),
            gate_meta.get("acceptance_executed", False),
            result_validator_meta.get("acceptance_executed", False),
            scaffold_payload.get("acceptance_executed", False),
        ]
    )
    upstream_authorization_review_completed = bool(
        scaffold_status.get("authorization_review_completed", False)
    )
    review_only_contract_retained = _review_only_contract_retained(
        scaffold_meta,
        bundle_meta,
        gate_meta,
        result_validator_meta,
    )

    required_record_fields_present = bool(required_record_fields)
    required_review_conclusions_present = bool(required_review_conclusions)
    scaffold_payload_present = bool(scaffold_payload)
    pending_verdict_retained = bool(
        str(scaffold_payload.get("verdict") or "").strip() == "pending"
    )
    authorization_granted_retained_false = bool(
        not scaffold_payload.get("authorization_granted", False)
        and not acceptance_execution_authorized
    )
    runtime_enablement_retained_false = bool(
        not scaffold_payload.get("runtime_enablement_allowed", False)
        and runtime_enablement_still_blocked
    )
    acceptance_executed_retained_false = bool(
        not scaffold_payload.get("acceptance_executed", False) and not acceptance_executed
    )

    required_field_rules = _build_required_field_rules(
        required_record_fields,
        template_payload=scaffold_payload,
    )
    required_conclusion_ids_rule = _build_required_ids_rule(
        field="required_conclusion_ids",
        required_ids=required_conclusion_ids,
        validation_rule="must_include_all_required_ids_and_no_missing_conclusions",
        detail=(
            "Future payload must include every required review conclusion id carried "
            "forward from the locked scaffold/contract."
        ),
    )
    required_runtime_patch_statement_ids_rule = _build_required_ids_rule(
        field="required_runtime_patch_statement_ids",
        required_ids=required_runtime_patch_statement_ids,
        validation_rule=(
            "must_include_all_required_ids_and_no_missing_runtime_patch_statements"
        ),
        detail=(
            "Future payload must include every required runtime patch statement id "
            "carried forward from the locked scaffold/contract."
        ),
    )
    missing_prerequisite_gate_ids_rule = _build_required_ids_rule(
        field="missing_prerequisite_gate_ids",
        required_ids=missing_prerequisite_gate_ids,
        validation_rule=(
            "must_match_current_missing_prerequisite_gate_ids_until_upstream_contract_changes"
        ),
        detail=(
            "Future payload must preserve the currently blocked prerequisite gate ids "
            "until the upstream authorization-review contract is revised."
        ),
    )
    locked_execution_target_rule = _build_locked_execution_target_rule(
        production_profile_id=production_profile_id,
        default_production_runner=default_production_runner,
        exact_future_acceptance_command=exact_future_acceptance_command,
        exact_future_acceptance_result_path=exact_future_acceptance_result_path,
    )
    future_validation_checklist = _build_future_validation_checklist(
        exact_future_acceptance_command=exact_future_acceptance_command,
        exact_future_acceptance_result_path=exact_future_acceptance_result_path,
        required_conclusion_ids=required_conclusion_ids,
        required_runtime_patch_statement_ids=required_runtime_patch_statement_ids,
        missing_prerequisite_gate_ids=missing_prerequisite_gate_ids,
    )

    checks = [
        _check(
            "acceptance_authorization_review_record_scaffold_present",
            "pass" if scaffold_present else "fail",
            "acceptance authorization review record scaffold loaded"
            if scaffold_present
            else _presence_detail(
                scaffold_report,
                scaffold_error,
                scaffold_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE,
                project_root,
                scaffold_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_bundle_present",
            "pass" if bundle_present else "fail",
            "acceptance authorization review bundle loaded"
            if bundle_present
            else _presence_detail(
                bundle_report,
                bundle_error,
                bundle_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE,
                project_root,
                bundle_resolved,
            ),
        ),
        _check(
            "acceptance_execution_gate_present",
            "pass" if gate_present else "fail",
            "acceptance execution gate loaded"
            if gate_present
            else _presence_detail(
                gate_report,
                gate_error,
                gate_meta,
                ACCEPTANCE_EXECUTION_GATE_SOURCE,
                project_root,
                gate_resolved,
            ),
        ),
        _check(
            "acceptance_result_validator_present",
            "pass" if result_validator_present else "fail",
            "acceptance result validator loaded"
            if result_validator_present
            else _presence_detail(
                result_validator_report,
                result_validator_error,
                result_validator_meta,
                ACCEPTANCE_RESULT_VALIDATOR_SOURCE,
                project_root,
                result_validator_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_record_scaffold_ready",
            "pass" if scaffold_ready else "fail",
            str(scaffold_ready),
        ),
        _check(
            "acceptance_authorization_review_bundle_ready",
            "pass" if bundle_ready else "fail",
            str(bundle_ready),
        ),
        _check(
            "acceptance_execution_gate_ready",
            "pass" if gate_ready else "fail",
            str(gate_ready),
        ),
        _check(
            "acceptance_result_validator_ready",
            "pass" if result_validator_ready else "fail",
            str(result_validator_ready),
        ),
        _check(
            "required_record_fields_present",
            "pass" if required_record_fields_present else "fail",
            str(required_record_fields_present),
        ),
        _check(
            "required_review_conclusions_present",
            "pass" if required_review_conclusions_present else "fail",
            ",".join(required_conclusion_ids) if required_conclusion_ids else "missing",
        ),
        _check(
            "scaffolded_authorization_review_record_payload_present",
            "pass" if scaffold_payload_present else "fail",
            "scaffold payload present" if scaffold_payload_present else "missing",
        ),
        _check(
            "locked_execution_target_present",
            "pass" if locked_execution_target_present else "fail",
            (
                f"production_profile_id={production_profile_id or 'missing'} "
                f"exact_future_acceptance_command_present={bool(exact_future_acceptance_command)} "
                "exact_future_acceptance_result_path="
                f"{exact_future_acceptance_result_path or 'missing'}"
            ),
        ),
        _check(
            "locked_execution_target_consistent",
            "pass" if locked_execution_target_consistent else "fail",
            (
                "production_profile_locked="
                f"{production_profile_locked} "
                "default_production_runner_locked="
                f"{default_production_runner_locked} "
                "exact_future_acceptance_command_locked="
                f"{exact_future_acceptance_command_locked} "
                "exact_future_acceptance_result_path_locked="
                f"{exact_future_acceptance_result_path_locked} "
                f"command_matches_result_path={command_matches_result_path}"
            ),
        ),
        _check(
            "required_field_rules_ready",
            "pass" if bool(required_field_rules) else "fail",
            ",".join(rule["field"] for rule in required_field_rules)
            if required_field_rules
            else "missing",
        ),
        _check(
            "required_conclusion_ids_rule_ready",
            "pass" if bool(required_conclusion_ids_rule) else "fail",
            ",".join(_string_list(required_conclusion_ids_rule.get("required_ids"))),
        ),
        _check(
            "required_runtime_patch_statement_ids_rule_ready",
            "pass" if bool(required_runtime_patch_statement_ids_rule) else "fail",
            ",".join(
                _string_list(
                    required_runtime_patch_statement_ids_rule.get("required_ids")
                )
            ),
        ),
        _check(
            "missing_prerequisite_gate_ids_rule_ready",
            "pass" if bool(missing_prerequisite_gate_ids_rule) else "fail",
            ",".join(
                _string_list(missing_prerequisite_gate_ids_rule.get("required_ids"))
            )
            or "(none)",
        ),
        _check(
            "locked_execution_target_rule_ready",
            "pass" if bool(locked_execution_target_rule) else "fail",
            locked_execution_target_rule.get("validation_rule") or "missing",
        ),
        _check(
            "future_validation_checklist_present",
            "pass" if bool(future_validation_checklist) else "fail",
            str(bool(future_validation_checklist)),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "all upstream artifacts remain review-only/default-off/no-solve"
            if review_only_contract_retained
            else "expected review-only/default-off/spec-only/no-solve metadata upstream",
        ),
        _check(
            "acceptance_execution_authorized_still_false",
            "pass" if not acceptance_execution_authorized else "fail",
            f"acceptance_execution_authorized={acceptance_execution_authorized}",
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_still_blocked else "fail",
            f"runtime_enablement_still_blocked={runtime_enablement_still_blocked}",
        ),
        _check(
            "acceptance_executed_still_false",
            "pass" if not acceptance_executed else "fail",
            f"acceptance_executed={acceptance_executed}",
        ),
        _check(
            "pending_verdict_retained",
            "pass" if pending_verdict_retained else "fail",
            str(scaffold_payload.get("verdict")),
        ),
        _check(
            "authorization_granted_retained_false",
            "pass" if authorization_granted_retained_false else "fail",
            (
                "template_authorization_granted="
                f"{bool(scaffold_payload.get('authorization_granted', False))} "
                f"upstream_acceptance_execution_authorized={acceptance_execution_authorized}"
            ),
        ),
        _check(
            "runtime_enablement_retained_false",
            "pass" if runtime_enablement_retained_false else "fail",
            (
                "template_runtime_enablement_allowed="
                f"{bool(scaffold_payload.get('runtime_enablement_allowed', False))} "
                f"runtime_enablement_still_blocked={runtime_enablement_still_blocked}"
            ),
        ),
        _check(
            "acceptance_executed_retained_false",
            "pass" if acceptance_executed_retained_false else "fail",
            (
                "template_acceptance_executed="
                f"{bool(scaffold_payload.get('acceptance_executed', False))} "
                f"acceptance_executed={acceptance_executed}"
            ),
        ),
        _check(
            "upstream_authorization_review_completed_still_false",
            "pass" if not upstream_authorization_review_completed else "fail",
            "upstream_authorization_review_completed="
            f"{upstream_authorization_review_completed}",
        ),
    ]

    gates = [
        _gate(
            "acceptance_authorization_review_record_scaffold_ready",
            scaffold_ready,
            True,
            "The validator contract depends on the scaffold already being ready.",
        ),
        _gate(
            "acceptance_authorization_review_bundle_ready",
            bundle_ready,
            True,
            "The validator contract depends on the acceptance-authorization review bundle already being ready.",
        ),
        _gate(
            "acceptance_execution_gate_ready",
            gate_ready,
            True,
            "The validator contract depends on the acceptance execution gate already being ready.",
        ),
        _gate(
            "acceptance_result_validator_ready",
            result_validator_ready,
            True,
            "The validator contract depends on the acceptance result validator already being ready.",
        ),
        _gate(
            "locked_prod_4x4_target_explicit",
            locked_execution_target_present,
            True,
            "The validator must keep the locked prod_4x4 target, command, and result path explicit.",
        ),
        _gate(
            "locked_execution_target_consistent",
            locked_execution_target_consistent,
            True,
            "The scaffold, bundle, execution gate, and acceptance result validator must agree on the same locked execution target.",
        ),
        _gate(
            "required_record_fields_present",
            required_record_fields_present,
            True,
            "The validator must carry forward the scaffolded required record fields.",
        ),
        _gate(
            "required_review_conclusions_present",
            required_review_conclusions_present,
            True,
            "The validator must carry forward the scaffolded required review conclusions.",
        ),
        _gate(
            "review_only_contract_retained",
            review_only_contract_retained,
            True,
            "This validator remains review-only/default-off/spec-only/no-solve.",
        ),
        _gate(
            "runtime_enablement_still_blocked",
            runtime_enablement_still_blocked,
            True,
            "Runtime enablement must remain forbidden throughout this validator contract and any later record validation.",
        ),
        _gate(
            "acceptance_execution_not_authorized",
            not acceptance_execution_authorized,
            True,
            "This validator is contract-only; acceptance_execution_authorized must remain false here.",
        ),
        _gate(
            "acceptance_not_executed_yet",
            not acceptance_executed,
            True,
            "This validator is pre-execution only; production acceptance must remain unexecuted here.",
        ),
    ]
    gates.extend(carry_forward_gate_entries)

    acceptance_authorization_review_record_validator_ready = all(
        check["status"] == "pass" for check in checks
    )
    actual_validation = _validate_optional_authorization_review_record_payload(
        project_root=project_root,
        payload_path=record_payload_resolved,
        validator_ready=acceptance_authorization_review_record_validator_ready,
        required_field_rules=required_field_rules,
        required_conclusion_ids_rule=required_conclusion_ids_rule,
        required_runtime_patch_statement_ids_rule=required_runtime_patch_statement_ids_rule,
        missing_prerequisite_gate_ids_rule=missing_prerequisite_gate_ids_rule,
        locked_execution_target_rule=locked_execution_target_rule,
    )
    authorization_review_record_provided = bool(
        actual_validation.get("record_payload_provided", False)
    )
    authorization_review_record_validated = bool(
        actual_validation.get("record_payload_validated", False)
    )
    authorization_review_completed = bool(
        actual_validation.get("validated_authorization_review_completed", False)
    )
    checks.append(_actual_validation_check(actual_validation))
    gates.extend(
        [
            _gate(
                "authorization_review_record_completion_state",
                bool(
                    actual_validation.get("completion_state_rule_passed")
                    if authorization_review_record_provided
                    else True
                ),
                False,
                str(actual_validation.get("completion_state_detail")),
            ),
            _gate(
                "actual_acceptance_authorization_review_record_validated",
                authorization_review_record_validated,
                False,
                str(actual_validation.get("detail")),
            ),
        ]
    )
    future_manual_authorization_review_prerequisites_met = bool(
        acceptance_authorization_review_record_validator_ready
        and bool(
            scaffold_status.get(
                "future_manual_authorization_review_prerequisites_met", False
            )
        )
        and not missing_prerequisite_gate_ids
    )

    if not acceptance_authorization_review_record_validator_ready:
        recommended_next_step = (
            "repair_acceptance_authorization_review_record_validator_inputs"
        )
        handoff_recommendation = (
            "Acceptance-authorization review record validator contract is blocked; "
            "repair the missing or mismatched upstream review artifacts before using "
            "this validator for any future human-completed review record."
        )
    elif authorization_review_record_provided and not authorization_review_record_validated:
        recommended_next_step = (
            "repair_and_revalidate_completed_acceptance_authorization_review_record_payload"
        )
        handoff_recommendation = (
            "A completed acceptance-authorization review record payload was supplied "
            "but did not validate against the locked scaffold/contract. "
            "acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, and acceptance_executed=false remain "
            "locked here. Repair the payload and re-run this validator; do not treat "
            "this failed validation as execution authorization or runtime enablement."
        )
    elif authorization_review_record_validated:
        recommended_next_step = (
            "handoff_validated_acceptance_authorization_review_record_without_enabling_runtime"
        )
        blocked_text = (
            " Current missing prerequisite(s) remain blocked here: "
            + ", ".join(missing_prerequisite_gate_ids)
            + "."
            if missing_prerequisite_gate_ids
            else ""
        )
        handoff_recommendation = (
            "A completed acceptance-authorization review record payload validated "
            "against the locked scaffold/contract. This confirms contract "
            "compatibility only; it does not authorize execution, does not enable "
            "runtime, and does not execute acceptance. "
            "acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, and acceptance_executed=false remain "
            "locked in this validator artifact."
            + blocked_text
        )
    elif missing_prerequisite_gate_ids:
        recommended_next_step = (
            "complete_missing_prerequisite_gates_then_have_human_fill_and_validate_acceptance_authorization_review_record"
        )
        handoff_recommendation = (
            "Acceptance-authorization review record validator contract is ready as "
            "review-only/default-off scaffolding. It keeps "
            "acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, acceptance_executed=false, and no "
            "actual authorization review record has been validated yet. Current "
            "missing prerequisite(s) still block any future authorization grant: "
            f"{', '.join(missing_prerequisite_gate_ids)}. Next step: resolve those "
            "prerequisites, then have a human reviewer fill a record for the locked "
            f"prod_4x4_normal command `{exact_future_acceptance_command}` writing "
            f"`{exact_future_acceptance_result_path}`, and validate that payload "
            "against this contract without enabling runtime."
        )
    else:
        recommended_next_step = (
            "have_human_fill_and_validate_acceptance_authorization_review_record_without_enabling_runtime"
        )
        handoff_recommendation = (
            "Acceptance-authorization review record validator contract is ready and "
            "the currently known prerequisite gates are satisfied, but no actual "
            "authorization review record has been provided or validated. A human "
            "reviewer must still fill the record for the locked prod_4x4_normal "
            f"command `{exact_future_acceptance_command}` writing "
            f"`{exact_future_acceptance_result_path}`, and runtime_enablement_allowed "
            "must remain false here."
        )

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_review_record_validator_"
                "contract_not_actual_review_record"
            ),
            "spec_only": True,
            "review_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
        "paths": {
            "project_root": str(project_root),
            "acceptance_authorization_review_record_scaffold": _display_path(
                project_root, scaffold_resolved
            ),
            "acceptance_authorization_review_bundle": _display_path(
                project_root, bundle_resolved
            ),
            "acceptance_execution_gate": _display_path(project_root, gate_resolved),
            "acceptance_result_validator": _display_path(
                project_root, result_validator_resolved
            ),
            "acceptance_authorization_review_record_payload": (
                _display_path(project_root, record_payload_resolved)
                if record_payload_resolved is not None
                else None
            ),
            "exact_future_acceptance_command": exact_future_acceptance_command,
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_authorization_review_record_validator_ready": bool(
                acceptance_authorization_review_record_validator_ready
            ),
            "future_manual_authorization_review_prerequisites_met": bool(
                future_manual_authorization_review_prerequisites_met
            ),
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "authorization_review_completed": bool(authorization_review_completed),
            "authorization_review_record_provided": bool(
                authorization_review_record_provided
            ),
            "authorization_review_record_validated": bool(
                authorization_review_record_validated
            ),
            "missing_prerequisite_gate_ids": list(missing_prerequisite_gate_ids),
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_authorization_review_record_validator": {
            "validator_target": (
                "future_acceptance_execution_authorization_review_record_payload"
            ),
            "target_record_type": scaffold_payload.get("record_type")
            or scaffold.get("record_type"),
            "scope": _validator_scope(candidate),
            "review_only": True,
            "default_off": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": production_profile_id,
                "production_profile_locked": bool(
                    production_profile_locked_prod_4x4_normal
                ),
                "default_production_runner": default_production_runner,
                "default_production_runner_locked": bool(
                    default_production_runner_locked
                ),
                "exact_future_acceptance_command": exact_future_acceptance_command,
                "exact_future_acceptance_command_locked": bool(
                    exact_future_acceptance_command_locked
                ),
                "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
                "exact_future_acceptance_result_path_locked": bool(
                    exact_future_acceptance_result_path_locked
                ),
                "command_matches_result_path": bool(command_matches_result_path),
            },
            "required_record_fields": list(required_record_fields),
            "required_review_conclusions": list(required_review_conclusions),
            "required_runtime_patch_statement_ids": list(
                required_runtime_patch_statement_ids
            ),
            "missing_prerequisites": list(missing_prerequisites),
            "future_validation_checklist": list(future_validation_checklist),
            "validator_rules": {
                "required_fields": required_field_rules,
                "required_conclusion_ids": required_conclusion_ids_rule,
                "required_runtime_patch_statement_ids": (
                    required_runtime_patch_statement_ids_rule
                ),
                "missing_prerequisite_gate_ids": missing_prerequisite_gate_ids_rule,
                "locked_execution_target": locked_execution_target_rule,
            },
            "actual_record_validation": actual_validation,
            "validator_notice": VALIDATOR_NOTICE,
            "handoff_recommendation": handoff_recommendation,
        },
        "still_blocked_gate_ids": list(missing_prerequisite_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("acceptance_authorization_review_record_validator"))
    locked_execution_target = _mapping(validator.get("locked_execution_target"))
    validator_rules = _mapping(validator.get("validator_rules"))
    actual_validation = _mapping(validator.get("actual_record_validation"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Review Record Validator",
        "",
        f"- Acceptance authorization review record validator ready: `{status.get('acceptance_authorization_review_record_validator_ready')}`",
        f"- Future manual authorization review prerequisites met: `{status.get('future_manual_authorization_review_prerequisites_met')}`",
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Authorization review completed: `{status.get('authorization_review_completed')}`",
        f"- Authorization review record provided: `{status.get('authorization_review_record_provided')}`",
        f"- Authorization review record validated: `{status.get('authorization_review_record_validated')}`",
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
        f"- Review only: `{validator.get('review_only')}`",
        f"- Default off: `{validator.get('default_off')}`",
        f"- Does not authorize execution: `{validator.get('does_not_authorize_execution')}`",
        "",
        "## Locked Execution Target",
        "",
        f"- Production profile id: `{locked_execution_target.get('production_profile_id')}`",
        f"- Production profile locked: `{locked_execution_target.get('production_profile_locked')}`",
        f"- Default production runner: `{locked_execution_target.get('default_production_runner')}`",
        f"- Default production runner locked: `{locked_execution_target.get('default_production_runner_locked')}`",
        f"- Exact future acceptance command: `{locked_execution_target.get('exact_future_acceptance_command')}`",
        f"- Exact future acceptance command locked: `{locked_execution_target.get('exact_future_acceptance_command_locked')}`",
        f"- Exact future acceptance result path: `{locked_execution_target.get('exact_future_acceptance_result_path')}`",
        f"- Exact future acceptance result path locked: `{locked_execution_target.get('exact_future_acceptance_result_path_locked')}`",
        f"- Command matches result path: `{locked_execution_target.get('command_matches_result_path')}`",
        "",
        "## Actual Record Validation State",
        "",
        f"- Record payload path: `{actual_validation.get('record_payload_path')}`",
        f"- Record payload provided: `{actual_validation.get('record_payload_provided')}`",
        f"- Record payload loaded: `{actual_validation.get('record_payload_loaded')}`",
        f"- Record payload validated: `{actual_validation.get('record_payload_validated')}`",
        f"- Payload completion claimed: `{actual_validation.get('payload_claimed_authorization_review_completed')}`",
        f"- Completed review state validated: `{actual_validation.get('validated_authorization_review_completed')}`",
        f"- Validation status: `{actual_validation.get('validation_status')}`",
        f"- Detail: {actual_validation.get('detail')}",
        "",
        "## Actual Record Rule Results",
        "",
    ]
    per_rule_results = _mapping_list(actual_validation.get("per_rule_results"))
    if per_rule_results:
        lines.extend(
            [
                "| Rule | Status | Field | Validation rule | Observed | Expected | Detail |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in per_rule_results:
            lines.append(
                f"| {_markdown_cell(entry.get('rule_id'))} | "
                f"{_markdown_cell(entry.get('status'))} | "
                f"{_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('validation_rule'))} | "
                f"{_markdown_cell(_render_value(entry.get('observed_value')))} | "
                f"{_markdown_cell(_render_value(entry.get('expected_value')))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
        lines.append("")
    else:
        lines.extend(
            [
                "- Per-rule validation results: not run because no payload was supplied.",
                "",
            ]
        )
    lines.extend(
        [
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
                f"{_markdown_cell(_render_value(rule.get('template_value')))} | "
                f"{_markdown_cell(rule.get('validation_rule'))} | "
                f"{_markdown_cell(rule.get('validator_detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Required Review Conclusions",
            "",
            "| Conclusion | Currently satisfied | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(validator.get("required_review_conclusions", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('conclusion_id'))} | "
                f"{_markdown_cell(entry.get('currently_satisfied'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Missing Prerequisites",
            "",
            "| Gate | Required state | Current value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(validator.get("missing_prerequisites", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('gate_id'))} | "
                f"{_markdown_cell(entry.get('required_state'))} | "
                f"{_markdown_cell(entry.get('current_value'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    for label in (
        "required_conclusion_ids",
        "required_runtime_patch_statement_ids",
        "missing_prerequisite_gate_ids",
        "locked_execution_target",
    ):
        rule = _mapping(validator_rules.get(label))
        lines.extend(
            [
                "",
                f"## {label.replace('_', ' ').title()} Rule",
                "",
                f"- Validation rule: `{rule.get('validation_rule')}`",
            ]
        )
        if "required_ids" in rule:
            lines.append(
                "- Required ids: `"
                + (
                    ", ".join(_string_list(rule.get("required_ids"))) or "(none)"
                )
                + "`"
            )
        if "expected_target" in rule:
            lines.append(
                "- Expected target: `"
                + _render_value(rule.get("expected_target"))
                + "`"
            )
        lines.append(f"- Detail: {rule.get('detail')}")
    lines.extend(
        [
            "",
            "## Future Validation Checklist",
            "",
            "| Checklist | Required | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(validator.get("future_validation_checklist", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('checklist_id'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("acceptance_authorization_review_record_validator"))
    locked_execution_target = _mapping(validator.get("locked_execution_target"))
    actual_validation = _mapping(validator.get("actual_record_validation"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization review record validator",
            "acceptance_authorization_review_record_validator_ready="
            + str(
                status.get(
                    "acceptance_authorization_review_record_validator_ready", False
                )
            ),
            "future_manual_authorization_review_prerequisites_met="
            + str(
                status.get(
                    "future_manual_authorization_review_prerequisites_met", False
                )
            ),
            "acceptance_execution_authorized="
            + str(status.get("acceptance_execution_authorized", False)),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed", False)),
            "acceptance_executed=" + str(status.get("acceptance_executed", False)),
            "authorization_review_completed="
            + str(status.get("authorization_review_completed", False)),
            "authorization_review_record_provided="
            + str(status.get("authorization_review_record_provided", False)),
            "authorization_review_record_validated="
            + str(status.get("authorization_review_record_validated", False)),
            "missing_prerequisite_gate_ids="
            + ",".join(_string_list(status.get("missing_prerequisite_gate_ids"))),
            "authorization_review_record_payload_path="
            + str(actual_validation.get("record_payload_path")),
            "production_profile_id="
            + str(locked_execution_target.get("production_profile_id")),
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path")),
            "target_record_type=" + str(validator.get("target_record_type")),
            "actual_record_validation_rule_failures="
            + str(actual_validation.get("failed_rule_count")),
            "actual_record_validation_status="
            + str(actual_validation.get("validation_status")),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = (
        "anchor119_row_domain_acceptance_authorization_review_record_validator"
    ),
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _validate_optional_authorization_review_record_payload(
    *,
    project_root: Path,
    payload_path: Optional[Path],
    validator_ready: bool,
    required_field_rules: list[Mapping[str, Any]],
    required_conclusion_ids_rule: Mapping[str, Any],
    required_runtime_patch_statement_ids_rule: Mapping[str, Any],
    missing_prerequisite_gate_ids_rule: Mapping[str, Any],
    locked_execution_target_rule: Mapping[str, Any],
) -> Dict[str, Any]:
    if payload_path is None:
        return {
            "record_payload_path": None,
            "record_payload_provided": False,
            "record_payload_loaded": False,
            "record_payload_validated": False,
            "validation_status": "not_run",
            "payload_claimed_authorization_review_completed": False,
            "validated_authorization_review_completed": False,
            "completion_state_rule_passed": False,
            "completion_state_detail": (
                "No actual acceptance-authorization review record has been completed "
                "or validated yet."
            ),
            "failed_rule_count": 0,
            "failed_rule_ids": [],
            "per_rule_results": [],
            "detail": ACTUAL_RECORD_VALIDATION_DETAIL,
        }

    payload_report, payload_error = _load_json_mapping(payload_path)
    payload_display_path = _display_path(project_root, payload_path)
    if payload_error or payload_report is None:
        detail = (
            "A payload path was provided but the acceptance-authorization review "
            "record JSON could not be loaded. "
            f"{payload_error or 'unknown_error'} Even a successful validation here "
            "would not authorize execution, enable runtime, or execute acceptance."
        )
        load_result = _validation_result(
            "payload_load",
            "fail",
            field="acceptance_authorization_review_record_payload",
            validation_rule="must_load_json_mapping",
            observed_value=payload_display_path,
            expected_value="readable_json_object",
            detail=detail,
        )
        return {
            "record_payload_path": payload_display_path,
            "record_payload_provided": True,
            "record_payload_loaded": False,
            "record_payload_validated": False,
            "validation_status": "load_error",
            "payload_claimed_authorization_review_completed": False,
            "validated_authorization_review_completed": False,
            "completion_state_rule_passed": False,
            "completion_state_detail": (
                "Payload load failed, so completed-review validation did not run."
            ),
            "failed_rule_count": 1,
            "failed_rule_ids": ["payload_load"],
            "per_rule_results": [load_result],
            "detail": detail,
        }

    if not validator_ready:
        detail = (
            "A payload path was provided, but the validator contract is not ready "
            "because upstream scaffold/contract inputs are still blocked. Repair the "
            "contract inputs before validating any completed review record payload. "
            "This still does not authorize execution, enable runtime, or execute "
            "acceptance."
        )
        ready_result = _validation_result(
            "validator_contract_ready",
            "fail",
            validation_rule="must_be_ready_before_payload_validation",
            observed_value=False,
            expected_value=True,
            detail=detail,
        )
        return {
            "record_payload_path": payload_display_path,
            "record_payload_provided": True,
            "record_payload_loaded": True,
            "record_payload_validated": False,
            "validation_status": "contract_blocked",
            "payload_claimed_authorization_review_completed": False,
            "validated_authorization_review_completed": False,
            "completion_state_rule_passed": False,
            "completion_state_detail": (
                "Payload validation is blocked until the validator contract is ready."
            ),
            "failed_rule_count": 1,
            "failed_rule_ids": ["validator_contract_ready"],
            "per_rule_results": [ready_result],
            "detail": detail,
        }

    payload = _mapping(payload_report)
    results: list[Dict[str, Any]] = []
    for rule in required_field_rules:
        if isinstance(rule, Mapping):
            results.append(_validate_required_field_rule(rule, payload))
    results.append(
        _validate_required_ids_rule(
            required_conclusion_ids_rule,
            payload,
            allow_extra_ids=True,
        )
    )
    results.append(
        _validate_required_ids_rule(
            required_runtime_patch_statement_ids_rule,
            payload,
            allow_extra_ids=True,
        )
    )
    results.append(
        _validate_required_ids_rule(
            missing_prerequisite_gate_ids_rule,
            payload,
            allow_extra_ids=False,
        )
    )
    results.append(_validate_locked_execution_target_rule(locked_execution_target_rule, payload))
    completion_result = _validate_completed_review_state(payload)
    results.append(completion_result)
    grant_consistency_result = (
        _validate_authorization_grant_consistency_with_missing_prerequisites(
            payload,
            missing_prerequisite_gate_ids_rule,
        )
    )
    results.append(grant_consistency_result)

    failed_rule_ids = [
        str(entry.get("rule_id"))
        for entry in results
        if str(entry.get("status")) == "fail"
    ]
    failed_rule_count = len(failed_rule_ids)
    passed_rule_count = sum(1 for entry in results if str(entry.get("status")) == "pass")
    record_payload_validated = failed_rule_count == 0
    payload_claimed_authorization_review_completed = bool(
        completion_result.get("observed_value")
    )
    validated_authorization_review_completed = bool(
        record_payload_validated and completion_result.get("status") == "pass"
    )
    if record_payload_validated:
        detail = (
            "The provided acceptance-authorization review record payload satisfied "
            f"all {passed_rule_count} validation rules against the locked "
            "scaffold/contract. This confirms contract compatibility only; it does "
            "not authorize execution, does not enable runtime, and does not execute "
            "acceptance."
        )
        validation_status = "passed"
    else:
        detail = (
            "The provided acceptance-authorization review record payload failed "
            f"{failed_rule_count} validation rule(s) against the locked "
            "scaffold/contract. This failed validation does not authorize execution, "
            "does not enable runtime, and does not execute acceptance."
        )
        validation_status = "failed"
    return {
        "record_payload_path": payload_display_path,
        "record_payload_provided": True,
        "record_payload_loaded": True,
        "record_payload_validated": bool(record_payload_validated),
        "validation_status": validation_status,
        "payload_claimed_authorization_review_completed": bool(
            payload_claimed_authorization_review_completed
        ),
        "validated_authorization_review_completed": bool(
            validated_authorization_review_completed
        ),
        "completion_state_rule_passed": bool(
            completion_result.get("status") == "pass"
        ),
        "completion_state_detail": str(completion_result.get("detail")),
        "failed_rule_count": failed_rule_count,
        "failed_rule_ids": failed_rule_ids,
        "per_rule_results": results,
        "detail": detail,
    }


def _validate_required_field_rule(
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    field = str(rule.get("field") or "").strip()
    validation_rule = str(rule.get("validation_rule") or "").strip()
    expected_value = rule.get("template_value")
    field_present = field in payload
    observed_value = payload.get(field)
    if validation_rule.startswith("validated_by_"):
        passed = field_present
        detail = (
            "Field is present and is validated by its dedicated contract rule."
            if passed
            else "Field is missing, so its dedicated contract rule cannot pass."
        )
        return _validation_result(
            f"field:{field}",
            "pass" if passed else "fail",
            field=field,
            validation_rule=validation_rule,
            observed_value=observed_value,
            expected_value=expected_value,
            detail=detail,
        )
    if validation_rule == "must_equal_template_value":
        passed = field_present and observed_value == expected_value
        detail = (
            "Field matches the locked template value."
            if passed
            else "Field must match the locked template value exactly."
        )
    elif validation_rule == "must_be_present_and_non_empty":
        passed = field_present and bool(str(observed_value or "").strip())
        detail = (
            "Field is present and non-empty."
            if passed
            else "Field must be present and non-empty."
        )
    elif validation_rule == "must_be_present_and_non_pending_string":
        value = str(observed_value or "").strip()
        passed = field_present and bool(value) and value != "pending"
        detail = (
            "Field is present and no longer `pending`."
            if passed
            else "Field must be present, non-empty, and not `pending` for a completed review record."
        )
    elif validation_rule == "must_be_explicit_boolean_review_decision":
        passed = field_present and isinstance(observed_value, bool)
        detail = (
            "Field is an explicit boolean review decision."
            if passed
            else "Field must be an explicit boolean review decision."
        )
    elif validation_rule == "must_remain_false":
        passed = field_present and observed_value is False
        detail = (
            "Field remains false as required by the locked review-only contract."
            if passed
            else "Field must remain false in any validated record."
        )
    elif validation_rule == "must_remain_false_until_separate_authorized_execution_occurs":
        passed = field_present and observed_value is False
        detail = (
            "Field remains false because this validator does not execute acceptance."
            if passed
            else "Field must remain false because this validator is review-only and pre-execution."
        )
    elif validation_rule == "must_be_present":
        passed = field_present
        detail = (
            "Field is present."
            if passed
            else "Field must be present in the completed review record payload."
        )
    else:
        passed = field_present
        detail = (
            "Field is present."
            if passed
            else "Field is missing from the completed review record payload."
        )
    return _validation_result(
        f"field:{field}",
        "pass" if passed else "fail",
        field=field,
        validation_rule=validation_rule,
        observed_value=observed_value,
        expected_value=expected_value,
        detail=detail,
    )


def _validate_required_ids_rule(
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    allow_extra_ids: bool,
) -> Dict[str, Any]:
    field = str(rule.get("field") or "").strip()
    validation_rule = str(rule.get("validation_rule") or "").strip()
    expected_ids = _string_list(rule.get("required_ids"))
    observed_ids = _string_list(payload.get(field))
    missing_ids = [entry for entry in expected_ids if entry not in observed_ids]
    extra_ids = [entry for entry in observed_ids if entry not in expected_ids]
    if allow_extra_ids:
        passed = field in payload and not missing_ids
    else:
        passed = field in payload and not missing_ids and not extra_ids
    detail_parts = []
    if missing_ids:
        detail_parts.append("missing_ids=" + ",".join(missing_ids))
    if extra_ids and not allow_extra_ids:
        detail_parts.append("extra_ids=" + ",".join(extra_ids))
    if not detail_parts:
        detail_parts.append("locked ids satisfied")
    return _validation_result(
        f"ids:{field}",
        "pass" if passed else "fail",
        field=field,
        validation_rule=validation_rule,
        observed_value=observed_ids,
        expected_value=expected_ids,
        detail="; ".join(detail_parts),
    )


def _validate_locked_execution_target_rule(
    rule: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    expected_target = _mapping(rule.get("expected_target"))
    observed_target = _mapping(payload.get("locked_execution_target"))
    mismatches: list[str] = []
    if not observed_target:
        mismatches.append("locked_execution_target missing")
    else:
        if str(observed_target.get("production_profile_id") or "").strip() != str(
            expected_target.get("production_profile_id") or ""
        ).strip():
            mismatches.append("production_profile_id")
        if _normalize_path_text(
            str(observed_target.get("default_production_runner") or "")
        ) != _normalize_path_text(str(expected_target.get("default_production_runner") or "")):
            mismatches.append("default_production_runner")
        if _normalize_command_text(
            str(observed_target.get("exact_future_acceptance_command") or "")
        ) != _normalize_command_text(
            str(expected_target.get("exact_future_acceptance_command") or "")
        ):
            mismatches.append("exact_future_acceptance_command")
        if _normalize_path_text(
            str(observed_target.get("exact_future_acceptance_result_path") or "")
        ) != _normalize_path_text(
            str(expected_target.get("exact_future_acceptance_result_path") or "")
        ):
            mismatches.append("exact_future_acceptance_result_path")
    return _validation_result(
        "locked_execution_target",
        "pass" if not mismatches else "fail",
        field="locked_execution_target",
        validation_rule=str(rule.get("validation_rule") or "").strip(),
        observed_value=observed_target,
        expected_value=expected_target,
        detail=(
            "Locked execution target matches exactly."
            if not mismatches
            else "locked_execution_target mismatches: " + ", ".join(mismatches)
        ),
    )


def _validate_completed_review_state(payload: Mapping[str, Any]) -> Dict[str, Any]:
    reviewer_id = str(payload.get("reviewer_id") or "").strip()
    reviewed_at = str(payload.get("reviewed_at") or "").strip()
    verdict = str(payload.get("verdict") or "").strip()
    authorization_granted = payload.get("authorization_granted")
    explicit_completed = payload.get("authorization_review_completed")
    issues: list[str] = []
    if not reviewer_id:
        issues.append("reviewer_id missing")
    if not reviewed_at:
        issues.append("reviewed_at missing")
    if not verdict or verdict == "pending":
        issues.append("verdict must be non-empty and not pending")
    if not isinstance(authorization_granted, bool):
        issues.append("authorization_granted must be boolean")
    if explicit_completed is not None and explicit_completed is not True:
        issues.append("authorization_review_completed must be true when present")
    completed_claim = (
        bool(reviewer_id)
        and bool(reviewed_at)
        and bool(verdict)
        and verdict != "pending"
        and isinstance(authorization_granted, bool)
    )
    return _validation_result(
        "completed_review_state",
        "pass" if not issues else "fail",
        validation_rule="must_reflect_completed_human_review_record",
        observed_value=completed_claim,
        expected_value=True,
        detail=(
            "Payload reflects a completed human review record."
            if not issues
            else "; ".join(issues)
        ),
    )


def _validate_authorization_grant_consistency_with_missing_prerequisites(
    payload: Mapping[str, Any],
    missing_prerequisite_gate_ids_rule: Mapping[str, Any],
) -> Dict[str, Any]:
    authorization_granted = payload.get("authorization_granted")
    expected_missing_ids = _string_list(
        missing_prerequisite_gate_ids_rule.get("required_ids")
    )
    if not isinstance(authorization_granted, bool):
        detail = "authorization_granted must be a boolean before prerequisite consistency can be confirmed."
        passed = False
    elif expected_missing_ids and authorization_granted:
        detail = (
            "authorization_granted cannot be true while locked missing prerequisite "
            "gate ids remain: " + ", ".join(expected_missing_ids)
        )
        passed = False
    else:
        detail = (
            "authorization_granted is consistent with the locked missing prerequisite "
            "gate contract."
        )
        passed = True
    return _validation_result(
        "authorization_grant_consistency_with_missing_prerequisites",
        "pass" if passed else "fail",
        field="authorization_granted",
        validation_rule="must_not_grant_authorization_while_locked_missing_prerequisites_remain",
        observed_value=authorization_granted,
        expected_value=(
            False if expected_missing_ids else "explicit_boolean_decision_allowed"
        ),
        detail=detail,
    )


def _actual_validation_check(actual_validation: Mapping[str, Any]) -> Dict[str, str]:
    if not actual_validation.get("record_payload_provided", False):
        return _check(
            "actual_acceptance_authorization_review_record_validation_not_run",
            "pass",
            str(actual_validation.get("detail")),
        )
    return _check(
        "actual_acceptance_authorization_review_record_validation_performed",
        "pass"
        if bool(actual_validation.get("record_payload_validated", False))
        else "fail",
        str(actual_validation.get("detail")),
    )


def _validation_result(
    rule_id: str,
    status: str,
    *,
    field: Optional[str] = None,
    validation_rule: Optional[str] = None,
    observed_value: Any = None,
    expected_value: Any = None,
    detail: str,
) -> Dict[str, Any]:
    return {
        "rule_id": str(rule_id),
        "status": str(status),
        "field": str(field or ""),
        "validation_rule": str(validation_rule or ""),
        "observed_value": observed_value,
        "expected_value": expected_value,
        "detail": str(detail),
    }


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
    if field == "record_type":
        return (
            "must_equal_template_value",
            "Future payload must carry forward this exact record type.",
        )
    if field in {"reviewer_id", "reviewed_at", "notes"}:
        return (
            "must_be_present_and_non_empty",
            "Future payload must replace the scaffold placeholder with a non-empty human-supplied value.",
        )
    if field == "verdict":
        return (
            "must_be_present_and_non_pending_string",
            "Future completed payload must replace the scaffold `pending` verdict with an explicit human review verdict string.",
        )
    if field == "authorization_granted":
        return (
            "must_be_explicit_boolean_review_decision",
            "Future payload must record an explicit boolean authorization decision, but validating that field here does not itself authorize execution.",
        )
    if field == "runtime_enablement_allowed":
        return (
            "must_remain_false",
            "Future payload must keep runtime_enablement_allowed=false. This record never authorizes runtime enablement.",
        )
    if field == "acceptance_executed":
        return (
            "must_remain_false_until_separate_authorized_execution_occurs",
            "Future payload must keep acceptance_executed=false because this record is review-only, not execution.",
        )
    if field == "locked_execution_target":
        return (
            "validated_by_locked_execution_target_rule",
            "This field is validated by the explicit locked_execution_target rule below.",
        )
    if field == "required_conclusion_ids":
        return (
            "validated_by_required_conclusion_ids_rule",
            "This field is validated by the explicit required_conclusion_ids rule below.",
        )
    if field == "required_runtime_patch_statement_ids":
        return (
            "validated_by_required_runtime_patch_statement_ids_rule",
            "This field is validated by the explicit required_runtime_patch_statement_ids rule below.",
        )
    if field == "missing_prerequisite_gate_ids":
        return (
            "validated_by_missing_prerequisite_gate_ids_rule",
            "This field is validated by the explicit missing_prerequisite_gate_ids rule below.",
        )
    return (
        "must_be_present",
        f"Future payload must provide `{field}` and keep it compatible with template value `{template_value}`.",
    )


def _build_required_ids_rule(
    *,
    field: str,
    required_ids: list[str],
    validation_rule: str,
    detail: str,
) -> Dict[str, Any]:
    return {
        "field": field,
        "required": True,
        "required_ids": list(required_ids),
        "validation_rule": validation_rule,
        "detail": detail,
    }


def _build_locked_execution_target_rule(
    *,
    production_profile_id: str,
    default_production_runner: str,
    exact_future_acceptance_command: str,
    exact_future_acceptance_result_path: str,
) -> Dict[str, Any]:
    if not (
        production_profile_id
        and default_production_runner
        and exact_future_acceptance_command
        and exact_future_acceptance_result_path
    ):
        return {}
    return {
        "field": "locked_execution_target",
        "required": True,
        "expected_target": {
            "production_profile_id": production_profile_id,
            "default_production_runner": default_production_runner,
            "exact_future_acceptance_command": exact_future_acceptance_command,
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "validation_rule": "must_match_locked_execution_target_exactly",
        "detail": (
            "Future payload must carry forward the locked prod_4x4 target, command, "
            "and result path unchanged."
        ),
    }


def _build_future_validation_checklist(
    *,
    exact_future_acceptance_command: str,
    exact_future_acceptance_result_path: str,
    required_conclusion_ids: list[str],
    required_runtime_patch_statement_ids: list[str],
    missing_prerequisite_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    return [
        {
            "checklist_id": "require_non_empty_human_reviewer_identity_and_timestamp",
            "required": True,
            "detail": (
                "A future human-completed review record must populate reviewer_id and "
                "reviewed_at with non-empty values."
            ),
        },
        {
            "checklist_id": "require_explicit_verdict_and_authorization_boolean",
            "required": True,
            "detail": (
                "A future human-completed review record must replace `pending` with "
                "an explicit verdict string and explicit boolean "
                "authorization_granted field."
            ),
        },
        {
            "checklist_id": "preserve_locked_execution_target_exactly",
            "required": True,
            "detail": (
                "The future review record must preserve the locked prod_4x4 target, "
                f"command `{exact_future_acceptance_command}`, and result path "
                f"`{exact_future_acceptance_result_path}` exactly."
            ),
        },
        {
            "checklist_id": "include_all_required_review_conclusions",
            "required": True,
            "detail": (
                "The future review record must include these required conclusion ids: "
                + (", ".join(required_conclusion_ids) or "(none)")
                + "."
            ),
        },
        {
            "checklist_id": "include_all_required_runtime_patch_statement_ids",
            "required": True,
            "detail": (
                "The future review record must include these runtime patch statement "
                "ids: "
                + (", ".join(required_runtime_patch_statement_ids) or "(none)")
                + "."
            ),
        },
        {
            "checklist_id": "preserve_current_missing_prerequisite_gate_ids",
            "required": True,
            "detail": (
                "The future review record must preserve the currently missing "
                "prerequisite gate ids until the upstream contract changes: "
                + (", ".join(missing_prerequisite_gate_ids) or "(none)")
                + "."
            ),
        },
        {
            "checklist_id": "keep_runtime_enablement_forbidden_in_record",
            "required": True,
            "detail": (
                "The future review record must keep runtime_enablement_allowed=false. "
                "This artifact never authorizes runtime enablement."
            ),
        },
        {
            "checklist_id": "keep_acceptance_unexecuted_in_record",
            "required": True,
            "detail": (
                "The future review record must keep acceptance_executed=false because "
                "execution still requires a separate later step."
            ),
        },
        {
            "checklist_id": "do_not_treat_validator_as_validated_record",
            "required": True,
            "detail": (
                "This artifact is only a validator contract. No actual review record "
                "has been provided or validated yet."
            ),
        },
    ]


def _build_missing_prerequisites(
    explicit_entries: Any,
    *,
    carry_forward_gate_entries: list[Mapping[str, Any]],
    scaffold_reported_missing_gate_ids: list[str],
    bundle_reported_missing_gate_ids: list[str],
    gate_reported_missing_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()

    if isinstance(explicit_entries, list):
        for entry in explicit_entries:
            if not isinstance(entry, Mapping):
                continue
            gate_id = str(entry.get("gate_id") or "").strip()
            if not gate_id or gate_id in seen:
                continue
            merged.append(
                {
                    "gate_id": gate_id,
                    "required_state": bool(entry.get("required_state", True)),
                    "current_value": bool(entry.get("current_value")),
                    "detail": str(entry.get("detail") or ""),
                }
            )
            seen.add(gate_id)

    detail_by_gate = {
        str(entry.get("gate_id")): str(entry.get("detail") or "")
        for entry in carry_forward_gate_entries
        if str(entry.get("gate_id") or "").strip()
    }
    for gate_id in (
        scaffold_reported_missing_gate_ids
        + bundle_reported_missing_gate_ids
        + gate_reported_missing_gate_ids
    ):
        text = str(gate_id).strip()
        if not text or text in seen:
            continue
        merged.append(
            {
                "gate_id": text,
                "required_state": True,
                "current_value": False,
                "detail": detail_by_gate.get(
                    text,
                    "Carry-forward missing prerequisite from upstream acceptance review artifacts.",
                ),
            }
        )
        seen.add(text)

    return merged


def _validator_scope(candidate: Mapping[str, Any]) -> str:
    key = str(candidate.get("key") or "").strip()
    anchor_idx = str(candidate.get("anchor_idx") or "").strip()
    if key and anchor_idx:
        return f"candidate={key}, anchor_idx={anchor_idx}"
    if key:
        return f"candidate={key}"
    if anchor_idx:
        return f"anchor_idx={anchor_idx}"
    return ""


def _presence_detail(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
    metadata: Mapping[str, Any],
    expected_source: str,
    project_root: Path,
    path: Path,
) -> str:
    if error:
        return str(error)
    if report is not None:
        return f"unexpected_source:{metadata.get('source')} expected:{expected_source}"
    return f"missing:{_display_path(project_root, path)}"


def _review_only_contract_retained(*metadatas: Mapping[str, Any]) -> bool:
    relevant = [metadata for metadata in metadatas if metadata]
    if not relevant:
        return False
    return all(
        bool(metadata.get("spec_only", False))
        and (
            "review_only" not in metadata or bool(metadata.get("review_only", False))
        )
        and bool(metadata.get("default_off", False))
        and not bool(metadata.get("runtime_precheck_enabled", False))
        and not bool(metadata.get("runtime_semantics_changed", False))
        and not bool(metadata.get("proof_source", False))
        and not bool(metadata.get("candidate_elimination_claim", False))
        and not bool(metadata.get("solver_invoked", False))
        and not bool(metadata.get("acceptance_executed", False))
        for metadata in relevant
    )


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
            gate_id = str(gate.get("gate_id") or "").strip()
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


def _locked_value(
    values: list[Any],
    *,
    normalize: Optional[Callable[[str], str]] = None,
) -> tuple[str, bool]:
    non_empty = [str(value) for value in values if str(value).strip()]
    if not non_empty:
        return "", False
    normalizer = normalize or (lambda value: str(value).strip())
    normalized = {normalizer(value) for value in non_empty}
    return non_empty[0], bool(len(non_empty) >= 2 and len(normalized) == 1)


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[Mapping[str, Any]] = []
    for entry in value:
        if isinstance(entry, Mapping):
            result.append(entry)
    return result


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


def _extract_suite_output_path(command: str) -> Optional[str]:
    if not str(command).strip():
        return None
    try:
        tokens = shlex.split(str(command), posix=False)
    except ValueError:
        tokens = str(command).split()
    for index, token in enumerate(tokens):
        token_text = str(token)
        if token_text == "--suite-output" and index + 1 < len(tokens):
            return str(tokens[index + 1]).strip("\"'")
        if token_text.startswith("--suite-output="):
            return token_text.split("=", 1)[1].strip("\"'")
    return None


def _normalize_command_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

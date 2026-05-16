from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
ACCEPTANCE_REFRESH_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
)
PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1"
)
ACCEPTANCE_EXECUTION_STAGING_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
)
ACCEPTANCE_RESULT_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
)
REVIEW_STATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1"
)
ACCEPTANCE_EXECUTION_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
)
LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_20260424/"
    "anchor119_row_domain_signoff_record_validator.json"
)
DEFAULT_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)
DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_20260424/"
    "anchor119_row_domain_acceptance_refresh_prep.json"
)
DEFAULT_PRE_RUN_ACCEPTANCE_VALIDATION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_20260424/"
    "anchor119_row_domain_pre_run_acceptance_validation.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_20260424/"
    "anchor119_row_domain_acceptance_execution_staging.json"
)
DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_20260424/"
    "anchor119_row_domain_acceptance_result_validator.json"
)
DEFAULT_REVIEW_STATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_review_state_20260425/"
    "anchor119_row_domain_review_state.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
    project_root: Path,
    *,
    signoff_record_validator_path: Optional[Path] = None,
    signoff_bundle_path: Optional[Path] = None,
    acceptance_refresh_prep_path: Optional[Path] = None,
    pre_run_acceptance_validation_path: Optional[Path] = None,
    acceptance_execution_staging_path: Optional[Path] = None,
    acceptance_result_validator_path: Optional[Path] = None,
    review_state_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    signoff_record_validator_resolved = _resolve_path(
        project_root,
        signoff_record_validator_path
        if signoff_record_validator_path is not None
        else DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH,
    )
    signoff_bundle_resolved = _resolve_path(
        project_root,
        signoff_bundle_path
        if signoff_bundle_path is not None
        else DEFAULT_SIGNOFF_BUNDLE_PATH,
    )
    acceptance_refresh_prep_resolved = _resolve_path(
        project_root,
        acceptance_refresh_prep_path
        if acceptance_refresh_prep_path is not None
        else DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH,
    )
    pre_run_acceptance_validation_resolved = _resolve_path(
        project_root,
        pre_run_acceptance_validation_path
        if pre_run_acceptance_validation_path is not None
        else DEFAULT_PRE_RUN_ACCEPTANCE_VALIDATION_PATH,
    )
    acceptance_execution_staging_resolved = _resolve_path(
        project_root,
        acceptance_execution_staging_path
        if acceptance_execution_staging_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH,
    )
    acceptance_result_validator_resolved = _resolve_path(
        project_root,
        acceptance_result_validator_path
        if acceptance_result_validator_path is not None
        else DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH,
    )
    review_state_resolved = _resolve_path(
        project_root,
        review_state_path if review_state_path is not None else DEFAULT_REVIEW_STATE_PATH,
    )

    signoff_record_validator_report, signoff_record_validator_error = _load_json_mapping(
        signoff_record_validator_resolved
    )
    signoff_bundle_report, signoff_bundle_error = _load_json_mapping(
        signoff_bundle_resolved
    )
    acceptance_refresh_prep_report, acceptance_refresh_prep_error = _load_json_mapping(
        acceptance_refresh_prep_resolved
    )
    pre_run_acceptance_validation_report, pre_run_acceptance_validation_error = (
        _load_json_mapping(pre_run_acceptance_validation_resolved)
    )
    acceptance_execution_staging_report, acceptance_execution_staging_error = (
        _load_json_mapping(acceptance_execution_staging_resolved)
    )
    acceptance_result_validator_report, acceptance_result_validator_error = (
        _load_json_mapping(acceptance_result_validator_resolved)
    )
    if review_state_path is not None:
        review_state_report, review_state_error = _load_json_mapping(
            review_state_resolved
        )
    else:
        review_state_report, review_state_error = None, "not_provided"

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
    signoff_bundle_meta = (
        _mapping(signoff_bundle_report.get("metadata")) if signoff_bundle_report else {}
    )
    signoff_bundle_status = (
        _mapping(signoff_bundle_report.get("status")) if signoff_bundle_report else {}
    )
    signoff_bundle = (
        _mapping(signoff_bundle_report.get("signoff_bundle"))
        if signoff_bundle_report
        else {}
    )
    acceptance_refresh_prep_meta = (
        _mapping(acceptance_refresh_prep_report.get("metadata"))
        if acceptance_refresh_prep_report
        else {}
    )
    acceptance_refresh_prep_status = (
        _mapping(acceptance_refresh_prep_report.get("status"))
        if acceptance_refresh_prep_report
        else {}
    )
    acceptance_refresh_prep = (
        _mapping(acceptance_refresh_prep_report.get("acceptance_refresh_prep"))
        if acceptance_refresh_prep_report
        else {}
    )
    pre_run_acceptance_validation_meta = (
        _mapping(pre_run_acceptance_validation_report.get("metadata"))
        if pre_run_acceptance_validation_report
        else {}
    )
    pre_run_acceptance_validation_status = (
        _mapping(pre_run_acceptance_validation_report.get("status"))
        if pre_run_acceptance_validation_report
        else {}
    )
    pre_run_acceptance_validation = (
        _mapping(
            pre_run_acceptance_validation_report.get("pre_run_acceptance_validation")
        )
        if pre_run_acceptance_validation_report
        else {}
    )
    acceptance_execution_staging_meta = (
        _mapping(acceptance_execution_staging_report.get("metadata"))
        if acceptance_execution_staging_report
        else {}
    )
    acceptance_execution_staging_status = (
        _mapping(acceptance_execution_staging_report.get("status"))
        if acceptance_execution_staging_report
        else {}
    )
    acceptance_execution_staging = (
        _mapping(
            acceptance_execution_staging_report.get("acceptance_execution_staging")
        )
        if acceptance_execution_staging_report
        else {}
    )
    acceptance_result_validator_meta = (
        _mapping(acceptance_result_validator_report.get("metadata"))
        if acceptance_result_validator_report
        else {}
    )
    acceptance_result_validator_status = (
        _mapping(acceptance_result_validator_report.get("status"))
        if acceptance_result_validator_report
        else {}
    )
    review_state_meta = (
        _mapping(review_state_report.get("metadata")) if review_state_report else {}
    )
    review_state_status = (
        _mapping(review_state_report.get("status")) if review_state_report else {}
    )
    acceptance_result_validator = (
        _mapping(
            acceptance_result_validator_report.get("acceptance_result_validator")
        )
        if acceptance_result_validator_report
        else {}
    )
    acceptance_result_validation = (
        _mapping(acceptance_result_validator_report.get("result_validation"))
        if acceptance_result_validator_report
        else {}
    )
    candidate = _first_mapping(
        signoff_record_validator_report.get("candidate")
        if signoff_record_validator_report
        else None,
        signoff_bundle_report.get("candidate") if signoff_bundle_report else None,
        acceptance_refresh_prep_report.get("candidate")
        if acceptance_refresh_prep_report
        else None,
        pre_run_acceptance_validation_report.get("candidate")
        if pre_run_acceptance_validation_report
        else None,
        acceptance_execution_staging_report.get("candidate")
        if acceptance_execution_staging_report
        else None,
        acceptance_result_validator_report.get("candidate")
        if acceptance_result_validator_report
        else None,
        review_state_report.get("candidate") if review_state_report else None,
    )

    signoff_record_validator_present = bool(
        signoff_record_validator_report is not None
        and signoff_record_validator_error is None
        and signoff_record_validator_meta.get("source")
        == SIGNOFF_RECORD_VALIDATOR_SOURCE
    )
    signoff_bundle_present = bool(
        signoff_bundle_report is not None
        and signoff_bundle_error is None
        and signoff_bundle_meta.get("source") == RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE
    )
    acceptance_refresh_prep_present = bool(
        acceptance_refresh_prep_report is not None
        and acceptance_refresh_prep_error is None
        and acceptance_refresh_prep_meta.get("source")
        == ACCEPTANCE_REFRESH_PREP_SOURCE
    )
    pre_run_acceptance_validation_present = bool(
        pre_run_acceptance_validation_report is not None
        and pre_run_acceptance_validation_error is None
        and pre_run_acceptance_validation_meta.get("source")
        == PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE
    )
    acceptance_execution_staging_present = bool(
        acceptance_execution_staging_report is not None
        and acceptance_execution_staging_error is None
        and acceptance_execution_staging_meta.get("source")
        == ACCEPTANCE_EXECUTION_STAGING_SOURCE
    )
    acceptance_result_validator_present = bool(
        acceptance_result_validator_report is not None
        and acceptance_result_validator_error is None
        and acceptance_result_validator_meta.get("source")
        == ACCEPTANCE_RESULT_VALIDATOR_SOURCE
    )
    review_state_present = bool(
        review_state_report is not None
        and review_state_error is None
        and review_state_meta.get("source") == REVIEW_STATE_SOURCE
    )
    review_state_valid = bool(
        review_state_present
        and review_state_status.get("review_state_ready", False)
        and review_state_status.get("repo_side_review_state_updated", False)
        and review_state_status.get("reviewed_runtime_patch_exists", False)
        and not review_state_status.get("runtime_enablement_allowed", False)
        and not review_state_status.get("production_acceptance_refresh_completed", False)
    )

    signoff_record_validator_ready = bool(
        signoff_record_validator_present
        and signoff_record_validator_status.get("signoff_record_validator_ready", False)
    )
    signoff_bundle_ready_for_review = bool(
        signoff_bundle_present
        and signoff_bundle_status.get(
            "reviewed_runtime_patch_signoff_ready_for_review",
            signoff_bundle_status.get("signoff_bundle_ready", False),
        )
    )
    acceptance_refresh_ready_for_review = bool(
        acceptance_refresh_prep_present
        and acceptance_refresh_prep_status.get("acceptance_refresh_ready_for_review", False)
    )
    pre_run_acceptance_validation_ready = bool(
        pre_run_acceptance_validation_present
        and pre_run_acceptance_validation_status.get(
            "acceptance_validation_ready_for_review", False
        )
    )
    acceptance_execution_staging_ready = bool(
        acceptance_execution_staging_present
        and acceptance_execution_staging_status.get(
            "acceptance_execution_staging_ready", False
        )
    )
    acceptance_result_validator_ready = bool(
        acceptance_result_validator_present
        and acceptance_result_validator_status.get(
            "acceptance_result_validator_ready", False
        )
    )

    reviewed_runtime_patch_exists_from_validator = bool(
        signoff_record_validator_status.get("reviewed_runtime_patch_exists", False)
    )
    reviewed_runtime_patch_exists_from_bundle = bool(
        signoff_bundle_status.get("reviewed_runtime_patch_exists", False)
    )
    reviewed_runtime_patch_exists_locked = bool(
        signoff_record_validator_present
        and signoff_bundle_present
        and reviewed_runtime_patch_exists_from_validator
        == reviewed_runtime_patch_exists_from_bundle
    )
    if review_state_valid:
        reviewed_runtime_patch_exists = True
        reviewed_runtime_patch_exists_locked = True
    else:
        reviewed_runtime_patch_exists = bool(
            reviewed_runtime_patch_exists_from_validator
            or reviewed_runtime_patch_exists_from_bundle
        )

    runtime_enablement_still_blocked = not any(
        bool(status.get("runtime_enablement_allowed", False))
        for status in (
            signoff_record_validator_status,
            signoff_bundle_status,
            acceptance_refresh_prep_status,
            pre_run_acceptance_validation_status,
            acceptance_execution_staging_status,
            acceptance_result_validator_status,
            review_state_status,
        )
    )
    review_only_contract_retained = _review_only_contract_retained(
        signoff_record_validator_meta,
        signoff_bundle_meta,
        acceptance_refresh_prep_meta,
        pre_run_acceptance_validation_meta,
        acceptance_execution_staging_meta,
        acceptance_result_validator_meta,
        review_state_meta,
    )

    acceptance_result_provided = bool(
        acceptance_result_validation.get("acceptance_result_provided", False)
    )
    acceptance_result_validation_performed = bool(
        acceptance_result_validator_status.get(
            "acceptance_result_validation_performed", False
        )
        or acceptance_result_validation.get("validation_performed", False)
    )
    acceptance_result_validation_passed = bool(
        acceptance_result_validator_status.get(
            "acceptance_result_validation_passed", False
        )
        or acceptance_result_validation.get("validation_passed", False)
    )
    acceptance_result_validation_deferred_as_expected = bool(
        acceptance_result_validator_present
        and not acceptance_result_provided
        and not acceptance_result_validation_performed
        and not acceptance_result_validation_passed
    )
    acceptance_executed = bool(
        pre_run_acceptance_validation_status.get("acceptance_executed", False)
        or acceptance_execution_staging_status.get("acceptance_executed", False)
        or acceptance_result_validator_meta.get("acceptance_executed", False)
        or acceptance_result_provided
        or acceptance_result_validation_performed
    )
    acceptance_not_executed_as_expected = not acceptance_executed
    acceptance_execution_state_allowed = bool(
        acceptance_not_executed_as_expected or acceptance_result_validation_passed
    )
    acceptance_result_validation_state_allowed = bool(
        acceptance_result_validation_deferred_as_expected
        or acceptance_result_validation_passed
    )

    exact_future_acceptance_command, exact_future_acceptance_command_locked = (
        _locked_value(
            [
                signoff_bundle.get("production_acceptance_command"),
                acceptance_refresh_prep.get("acceptance_command"),
                pre_run_acceptance_validation.get("production_acceptance_command"),
                acceptance_execution_staging.get("exact_command_to_run_later"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_locked = (
        _locked_value(
            [
                acceptance_refresh_prep.get("suite_output_path"),
                pre_run_acceptance_validation.get("exact_future_acceptance_json_path"),
                acceptance_execution_staging.get("exact_future_output_path"),
                acceptance_result_validator.get("expected_result_path"),
            ],
            normalize=_normalize_path_text,
        )
    )
    command_output_path = _extract_suite_output_path(exact_future_acceptance_command)
    command_matches_result_path = bool(
        exact_future_acceptance_result_path
        and command_output_path
        and _normalize_path_text(command_output_path)
        == _normalize_path_text(exact_future_acceptance_result_path)
    )
    production_profile_id, production_profile_locked = _locked_value(
        [
            acceptance_refresh_prep.get("production_profile_id"),
            pre_run_acceptance_validation.get("production_profile_id"),
            acceptance_execution_staging.get("production_profile_id"),
            acceptance_result_validator.get("production_profile_id"),
        ]
    )
    production_profile_locked_prod_4x4_normal = bool(
        production_profile_locked
        and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )

    signoff_validation_status = str(
        _mapping(signoff_record_validator.get("actual_record_validation")).get(
            "validation_status", "not_available"
        )
    )
    required_reviewer_statement_ids = _string_list(
        signoff_record_validator.get("required_reviewer_statement_ids")
    )
    if not required_reviewer_statement_ids:
        required_reviewer_statement_ids = [
            str(entry.get("statement_id"))
            for entry in list(signoff_bundle.get("required_reviewer_statements", []))
            if isinstance(entry, Mapping) and entry.get("statement_id")
        ]
    still_blocked_gate_ids = _string_list(
        signoff_record_validator_report.get("still_blocked_gate_ids")
        if signoff_record_validator_report
        else []
    )
    if not still_blocked_gate_ids:
        still_blocked_gate_ids = _string_list(
            _mapping(signoff_bundle.get("signoff_record_template")).get(
                "still_blocked_gate_ids"
            )
        )

    checks = [
        _check(
            "signoff_record_validator_present",
            "pass" if signoff_record_validator_present else "fail",
            "signoff record validator loaded"
            if signoff_record_validator_present
            else _presence_detail(
                signoff_record_validator_report,
                signoff_record_validator_error,
                signoff_record_validator_meta,
                SIGNOFF_RECORD_VALIDATOR_SOURCE,
                project_root,
                signoff_record_validator_resolved,
            ),
        ),
        _check(
            "runtime_patch_signoff_bundle_present",
            "pass" if signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if signoff_bundle_present
            else _presence_detail(
                signoff_bundle_report,
                signoff_bundle_error,
                signoff_bundle_meta,
                RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE,
                project_root,
                signoff_bundle_resolved,
            ),
        ),
        _check(
            "acceptance_refresh_prep_present",
            "pass" if acceptance_refresh_prep_present else "fail",
            "acceptance refresh prep loaded"
            if acceptance_refresh_prep_present
            else _presence_detail(
                acceptance_refresh_prep_report,
                acceptance_refresh_prep_error,
                acceptance_refresh_prep_meta,
                ACCEPTANCE_REFRESH_PREP_SOURCE,
                project_root,
                acceptance_refresh_prep_resolved,
            ),
        ),
        _check(
            "pre_run_acceptance_validation_present",
            "pass" if pre_run_acceptance_validation_present else "fail",
            "pre-run acceptance validation loaded"
            if pre_run_acceptance_validation_present
            else _presence_detail(
                pre_run_acceptance_validation_report,
                pre_run_acceptance_validation_error,
                pre_run_acceptance_validation_meta,
                PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE,
                project_root,
                pre_run_acceptance_validation_resolved,
            ),
        ),
        _check(
            "acceptance_execution_staging_present",
            "pass" if acceptance_execution_staging_present else "fail",
            "acceptance execution staging loaded"
            if acceptance_execution_staging_present
            else _presence_detail(
                acceptance_execution_staging_report,
                acceptance_execution_staging_error,
                acceptance_execution_staging_meta,
                ACCEPTANCE_EXECUTION_STAGING_SOURCE,
                project_root,
                acceptance_execution_staging_resolved,
            ),
        ),
        _check(
            "acceptance_result_validator_present",
            "pass" if acceptance_result_validator_present else "fail",
            "acceptance result validator loaded"
            if acceptance_result_validator_present
            else _presence_detail(
                acceptance_result_validator_report,
                acceptance_result_validator_error,
                acceptance_result_validator_meta,
                ACCEPTANCE_RESULT_VALIDATOR_SOURCE,
                project_root,
                acceptance_result_validator_resolved,
            ),
        ),
        _check(
            "signoff_record_validator_ready",
            "pass" if signoff_record_validator_ready else "fail",
            str(
                signoff_record_validator_status.get(
                    "signoff_record_validator_ready", False
                )
            ),
        ),
        _check(
            "runtime_patch_signoff_bundle_ready_for_review",
            "pass" if signoff_bundle_ready_for_review else "fail",
            str(
                signoff_bundle_status.get(
                    "reviewed_runtime_patch_signoff_ready_for_review",
                    signoff_bundle_status.get("signoff_bundle_ready", False),
                )
            ),
        ),
        _check(
            "acceptance_refresh_ready_for_review",
            "pass" if acceptance_refresh_ready_for_review else "fail",
            str(
                acceptance_refresh_prep_status.get(
                    "acceptance_refresh_ready_for_review", False
                )
            ),
        ),
        _check(
            "pre_run_acceptance_validation_ready",
            "pass" if pre_run_acceptance_validation_ready else "fail",
            str(
                pre_run_acceptance_validation_status.get(
                    "acceptance_validation_ready_for_review", False
                )
            ),
        ),
        _check(
            "acceptance_execution_staging_ready",
            "pass" if acceptance_execution_staging_ready else "fail",
            str(
                acceptance_execution_staging_status.get(
                    "acceptance_execution_staging_ready", False
                )
            ),
        ),
        _check(
            "acceptance_result_validator_ready",
            "pass" if acceptance_result_validator_ready else "fail",
            str(
                acceptance_result_validator_status.get(
                    "acceptance_result_validator_ready", False
                )
            ),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "spec_only/default_off/proof_source=false/solver_invoked=false retained"
            if review_only_contract_retained
            else "expected spec_only/default_off and proof_source=false/solver_invoked=false across upstream artifacts",
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_still_blocked else "fail",
            (
                "signoff_record_validator_runtime_enablement_allowed="
                f"{bool(signoff_record_validator_status.get('runtime_enablement_allowed', False))} "
                "signoff_bundle_runtime_enablement_allowed="
                f"{bool(signoff_bundle_status.get('runtime_enablement_allowed', False))} "
                "acceptance_refresh_runtime_enablement_allowed="
                f"{bool(acceptance_refresh_prep_status.get('runtime_enablement_allowed', False))} "
                "pre_run_runtime_enablement_allowed="
                f"{bool(pre_run_acceptance_validation_status.get('runtime_enablement_allowed', False))} "
                "staging_runtime_enablement_allowed="
                f"{bool(acceptance_execution_staging_status.get('runtime_enablement_allowed', False))} "
                "result_validator_runtime_enablement_allowed="
                f"{bool(acceptance_result_validator_status.get('runtime_enablement_allowed', False))}"
            ),
        ),
        _check(
            "reviewed_runtime_patch_exists_locked",
            "pass" if reviewed_runtime_patch_exists_locked else "fail",
            (
                "validator_reviewed_runtime_patch_exists="
                f"{reviewed_runtime_patch_exists_from_validator} "
                "bundle_reviewed_runtime_patch_exists="
                f"{reviewed_runtime_patch_exists_from_bundle} "
                "review_state_valid="
                f"{review_state_valid}"
            ),
        ),
        _check(
            (
                "review_state_marks_reviewed_runtime_patch"
                if review_state_valid
                else "reviewed_runtime_patch_absent_as_expected"
            ),
            "pass"
            if (review_state_valid and reviewed_runtime_patch_exists)
            or (not review_state_valid and not reviewed_runtime_patch_exists)
            else "fail",
            (
                f"review_state_valid={review_state_valid} "
                f"reviewed_runtime_patch_exists={reviewed_runtime_patch_exists}"
            ),
        ),
        _check(
            "production_profile_locked_prod_4x4_normal",
            "pass" if production_profile_locked_prod_4x4_normal else "fail",
            production_profile_id or "missing",
        ),
        _check(
            "exact_future_acceptance_command_locked",
            "pass" if exact_future_acceptance_command_locked else "fail",
            exact_future_acceptance_command or "missing",
        ),
        _check(
            "exact_future_acceptance_result_path_locked",
            "pass" if exact_future_acceptance_result_path_locked else "fail",
            exact_future_acceptance_result_path or "missing",
        ),
        _check(
            "command_matches_result_path",
            "pass" if command_matches_result_path else "fail",
            exact_future_acceptance_command or "missing",
        ),
        _check(
            "acceptance_execution_state_allowed",
            "pass" if acceptance_execution_state_allowed else "fail",
            (
                f"acceptance_executed={acceptance_executed}; "
                f"acceptance_result_validation_passed={acceptance_result_validation_passed}"
            ),
        ),
        _check(
            "acceptance_result_validation_state_allowed",
            "pass" if acceptance_result_validation_state_allowed else "fail",
            str(
                acceptance_result_validation.get("summary")
                or "expected no acceptance result payload yet, or a validated result after refresh"
            ),
        ),
    ]

    gates = [
        _gate(
            "signoff_record_validator_ready",
            signoff_record_validator_ready,
            True,
            "The reviewed runtime patch signoff validator contract must already be ready.",
        ),
        _gate(
            "runtime_patch_signoff_bundle_ready_for_review",
            signoff_bundle_ready_for_review,
            True,
            "The runtime patch signoff bundle must already be review-ready.",
        ),
        _gate(
            "acceptance_refresh_ready_for_review",
            acceptance_refresh_ready_for_review,
            True,
            "Acceptance refresh prep must already be review-ready.",
        ),
        _gate(
            "pre_run_acceptance_validation_ready",
            pre_run_acceptance_validation_ready,
            True,
            "Pre-run acceptance validation must already be review-ready.",
        ),
        _gate(
            "acceptance_execution_staging_ready",
            acceptance_execution_staging_ready,
            True,
            "Acceptance execution staging must already be review-ready.",
        ),
        _gate(
            "acceptance_result_validator_ready",
            acceptance_result_validator_ready,
            True,
            "Acceptance result validator must already be review-ready.",
        ),
        _gate(
            "production_profile_locked_prod_4x4_normal",
            production_profile_locked_prod_4x4_normal,
            True,
            "Future execution must remain pinned to the locked prod_4x4_normal target.",
        ),
        _gate(
            "exact_future_acceptance_command_locked",
            exact_future_acceptance_command_locked,
            True,
            "The future acceptance command must stay locked across upstream artifacts.",
        ),
        _gate(
            "exact_future_acceptance_result_path_locked",
            exact_future_acceptance_result_path_locked,
            True,
            "The future acceptance result path must stay locked across upstream artifacts.",
        ),
        _gate(
            "runtime_enablement_still_blocked",
            runtime_enablement_still_blocked,
            True,
            "Execution gating remains default-off and must not imply runtime enablement.",
        ),
        _gate(
            "reviewed_runtime_patch_exists",
            reviewed_runtime_patch_exists,
            True,
            "A separately reviewed runtime patch signoff record must exist before a later execution authorization review can approve the locked command.",
        ),
        _gate(
            "acceptance_not_executed_yet_or_result_validated",
            acceptance_execution_state_allowed,
            False,
            (
                "Before the refresh, production acceptance may be absent; after the refresh, "
                "the produced result must validate before this nonblocking state is acceptable."
            ),
        ),
        _gate(
            "review_only_artifact_does_not_authorize_execution",
            True,
            False,
            "This artifact formalizes blockers and the locked target only. A separate future review must still authorize any execution.",
        ),
    ]
    if review_state_valid:
        gates.append(
            _gate(
                "production_acceptance_refresh_completed",
                acceptance_result_validation_passed,
                True,
                "Reviewed runtime patch exists, but the refreshed prod_4x4 production acceptance result has not been validated yet.",
            )
        )

    acceptance_execution_gate_ready = all(
        check["status"] == "pass" for check in checks
    )
    acceptance_execution_authorization_prerequisites_met = all(
        bool(gate.get("satisfied")) for gate in gates if bool(gate.get("blocking"))
    )
    missing_prerequisites_before_execution_authorization = [
        {
            "gate_id": str(gate.get("gate_id")),
            "required_state": True,
            "current_value": bool(gate.get("satisfied")),
            "detail": str(gate.get("detail")),
        }
        for gate in gates
        if bool(gate.get("blocking")) and not bool(gate.get("satisfied"))
    ]
    missing_prerequisite_gate_ids = [
        entry["gate_id"]
        for entry in missing_prerequisites_before_execution_authorization
    ]

    if not acceptance_execution_gate_ready:
        recommended_next_step = "repair_acceptance_execution_gate_inputs"
        handoff_recommendation = (
            "Acceptance execution gate contract is blocked; repair the missing upstream "
            "artifacts or the locked prod_4x4_normal command/result-path contract before "
            "any future execution review."
        )
    elif review_state_valid and missing_prerequisite_gate_ids == [
        "production_acceptance_refresh_completed"
    ]:
        recommended_next_step = (
            "refresh_prod_4x4_normal_production_acceptance_after_separate_authorization"
        )
        handoff_recommendation = (
            "Acceptance execution gate has consumed a valid repo-side review-state marker: "
            "reviewed_runtime_patch_exists=true is no longer the blocker. This artifact still "
            "keeps acceptance_execution_authorized=false and runtime_enablement_allowed=false; "
            "the remaining blocker is production_acceptance_refresh_completed. Next step is a "
            "separate authorization to run the locked prod_4x4_normal acceptance refresh command, "
            f"`{exact_future_acceptance_command}`, and validate the result at "
            f"`{exact_future_acceptance_result_path}`."
        )
    elif review_state_valid and acceptance_result_validation_passed:
        recommended_next_step = (
            "refresh_long_run_preflight_after_validated_prod_4x4_acceptance"
        )
        handoff_recommendation = (
            "Acceptance execution gate has consumed a valid repo-side review-state marker "
            "and a validated prod_4x4_normal production acceptance result. "
            "reviewed_runtime_patch_exists=true and production_acceptance_refresh_completed=true "
            "are both satisfied for this contract, while acceptance_execution_authorized=false "
            "and runtime_enablement_allowed=false remain locked. Next step is to refresh the "
            "long-run preflight against the validated acceptance JSON and continue to the "
            "remaining B5A/certified-anchor gate; do not enable runtime elimination or launch "
            "the final 168h run from this artifact."
        )
    elif missing_prerequisite_gate_ids:
        recommended_next_step = (
            "complete_reviewed_runtime_patch_signoff_then_run_separate_execution_authorization_review"
        )
        handoff_recommendation = (
            "Acceptance execution gate contract is ready for review only: keep "
            "acceptance_execution_authorized=false and runtime_enablement_allowed=false. "
            "The locked prod_4x4_normal execution target is explicit, but execution still "
            "cannot be authorized because the reviewed runtime patch signoff record is "
            "absent and production acceptance has not been executed yet. Next step: "
            "produce and validate the reviewed runtime patch signoff record, then run a "
            "separate future execution-authorization review before running "
            f"`{exact_future_acceptance_command}` to write "
            f"`{exact_future_acceptance_result_path}`."
        )
    else:
        recommended_next_step = (
            "run_separate_execution_authorization_review_without_enabling_runtime"
        )
        handoff_recommendation = (
            "Acceptance execution gate contract is ready and its upstream prerequisites "
            "are satisfied, but this artifact remains review-only and keeps "
            "acceptance_execution_authorized=false. A separate future review must "
            f"explicitly authorize running `{exact_future_acceptance_command}` to write "
            f"`{exact_future_acceptance_result_path}`, and runtime_enablement_allowed "
            "remains false here."
        )

    return {
        "metadata": {
            "source": ACCEPTANCE_EXECUTION_GATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_execution_gate_review_only_not_execution_authorization"
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
            "signoff_record_validator": _display_path(
                project_root, signoff_record_validator_resolved
            ),
            "runtime_patch_signoff_bundle": _display_path(
                project_root, signoff_bundle_resolved
            ),
            "acceptance_refresh_prep": _display_path(
                project_root, acceptance_refresh_prep_resolved
            ),
            "pre_run_acceptance_validation": _display_path(
                project_root, pre_run_acceptance_validation_resolved
            ),
            "acceptance_execution_staging": _display_path(
                project_root, acceptance_execution_staging_resolved
            ),
            "acceptance_result_validator": _display_path(
                project_root, acceptance_result_validator_resolved
            ),
            "review_state": _display_path(project_root, review_state_resolved),
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_execution_gate_ready": bool(acceptance_execution_gate_ready),
            "acceptance_execution_authorization_prerequisites_met": bool(
                acceptance_execution_authorization_prerequisites_met
            ),
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "review_state_present": bool(review_state_present),
            "review_state_ready": bool(review_state_valid),
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "production_acceptance_refresh_completed": bool(
                acceptance_result_validation_passed
            ),
            "acceptance_executed": bool(acceptance_executed),
            "acceptance_result_validation_passed": bool(
                acceptance_result_validation_passed
            ),
            "missing_prerequisite_gate_ids": missing_prerequisite_gate_ids,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_execution_gate": {
            "guard_id": acceptance_result_validator.get("guard_id")
            or acceptance_execution_staging.get("guard_id")
            or pre_run_acceptance_validation.get("guard_id")
            or acceptance_refresh_prep.get("guard_id"),
            "payload_id": acceptance_result_validator.get("payload_id")
            or acceptance_execution_staging.get("payload_id")
            or pre_run_acceptance_validation.get("payload_id")
            or acceptance_refresh_prep.get("payload_id"),
            "production_profile_id": production_profile_id,
            "review_only": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": production_profile_id,
                "production_profile_locked": bool(
                    production_profile_locked_prod_4x4_normal
                ),
                "default_production_runner": str(
                    acceptance_refresh_prep.get("default_production_runner") or ""
                ),
                "exact_future_acceptance_command": exact_future_acceptance_command,
                "exact_future_acceptance_result_path": (
                    exact_future_acceptance_result_path
                ),
            },
            "reviewed_runtime_patch_signoff_state": {
                "signoff_record_validator_ready": bool(signoff_record_validator_ready),
                "runtime_patch_signoff_bundle_ready_for_review": bool(
                    signoff_bundle_ready_for_review
                ),
                "reviewed_runtime_patch_exists": bool(
                    reviewed_runtime_patch_exists
                ),
                "review_state_present": bool(review_state_present),
                "review_state_ready": bool(review_state_valid),
                "actual_signoff_record_validation_status": signoff_validation_status,
                "required_reviewer_statement_ids": required_reviewer_statement_ids,
                "still_blocked_gate_ids": still_blocked_gate_ids,
            },
            "acceptance_execution_state": {
                "acceptance_executed": bool(acceptance_executed),
                "acceptance_result_provided": bool(acceptance_result_provided),
                "acceptance_result_validation_performed": bool(
                    acceptance_result_validation_performed
                ),
                "acceptance_result_validation_passed": bool(
                    acceptance_result_validation_passed
                ),
                "acceptance_result_validation_summary": str(
                    acceptance_result_validation.get("summary") or ""
                ),
            },
            "missing_prerequisites_before_execution_authorization": (
                missing_prerequisites_before_execution_authorization
            ),
            "future_execution_authorization_notice": (
                (
                    "This artifact has consumed a validated prod_4x4_normal acceptance "
                    "result, but still does not authorize runtime enablement, checkpoint "
                    "import-back, release/viewer/frontdoor promotion, or final 168h launch."
                )
                if acceptance_result_validation_passed
                else (
                    "Even if the upstream prerequisites become satisfied, this artifact does "
                    "not grant execution authorization. A separate future review must "
                    "explicitly authorize running the locked prod_4x4_normal command."
                )
            ),
            "future_execution_checklist": [
                {
                    "checklist_id": "keep_acceptance_execution_authorized_false_here",
                    "required": True,
                    "detail": (
                        "Keep acceptance_execution_authorized=false in this artifact. "
                        "It is review-only and does not grant execution."
                    ),
                },
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "required": True,
                    "detail": (
                        "Keep runtime_enablement_allowed=false before, during, and after "
                        "any future execution review."
                    ),
                },
                {
                    "checklist_id": "require_reviewed_runtime_patch_signoff_record",
                    "required": True,
                    "detail": (
                        "Before a future reviewer can authorize execution, a separately "
                        "reviewed runtime patch signoff record must exist and validate "
                        "against the signoff-record contract."
                    ),
                },
                {
                    "checklist_id": "run_exact_locked_command_if_later_authorized",
                    "required": True,
                    "detail": (
                        "If a later reviewer separately authorizes execution, run exactly "
                        f"`{exact_future_acceptance_command}`."
                    ),
                },
                {
                    "checklist_id": "write_result_to_exact_locked_path",
                    "required": True,
                    "detail": (
                        "Write the future production-acceptance result to exactly "
                        f"`{exact_future_acceptance_result_path}`."
                    ),
                },
                {
                    "checklist_id": "validate_result_with_locked_result_validator",
                    "required": True,
                    "detail": (
                        "After the future run, validate the produced acceptance JSON with "
                        "the locked acceptance-result validator before any enablement "
                        "discussion."
                    ),
                },
                {
                    "checklist_id": "preserve_phase3b_execution_boundaries",
                    "required": True,
                    "detail": (
                        "Do not treat this artifact as solver execution, runtime "
                        "enablement, checkpoint creation or import, proof-source "
                        "promotion, or release/viewer/frontdoor status change."
                    ),
                },
            ],
            "handoff_recommendation": handoff_recommendation,
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    execution_gate = _mapping(report.get("acceptance_execution_gate"))
    locked_execution_target = _mapping(execution_gate.get("locked_execution_target"))
    signoff_state = _mapping(execution_gate.get("reviewed_runtime_patch_signoff_state"))
    execution_state = _mapping(execution_gate.get("acceptance_execution_state"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Execution Gate",
        "",
        f"- Acceptance execution gate ready: `{status.get('acceptance_execution_gate_ready')}`",
        (
            "- Acceptance execution authorization prerequisites met: "
            f"`{status.get('acceptance_execution_authorization_prerequisites_met')}`"
        ),
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Acceptance Execution Gate",
        "",
        f"- Guard id: `{execution_gate.get('guard_id')}`",
        f"- Payload id: `{execution_gate.get('payload_id')}`",
        f"- Production profile id: `{execution_gate.get('production_profile_id')}`",
        f"- Review only: `{execution_gate.get('review_only')}`",
        (
            "- Does not authorize execution: "
            f"`{execution_gate.get('does_not_authorize_execution')}`"
        ),
        f"- Authorization notice: {execution_gate.get('future_execution_authorization_notice')}",
        "",
        "## Locked Execution Target",
        "",
        (
            "- Production profile locked: "
            f"`{locked_execution_target.get('production_profile_locked')}`"
        ),
        (
            "- Default production runner: "
            f"`{locked_execution_target.get('default_production_runner')}`"
        ),
        (
            "- Exact future acceptance command: "
            f"`{locked_execution_target.get('exact_future_acceptance_command')}`"
        ),
        (
            "- Exact future acceptance result path: "
            f"`{locked_execution_target.get('exact_future_acceptance_result_path')}`"
        ),
        "",
        "## Reviewed Runtime Patch Signoff State",
        "",
        (
            "- Signoff record validator ready: "
            f"`{signoff_state.get('signoff_record_validator_ready')}`"
        ),
        (
            "- Runtime patch signoff bundle ready for review: "
            f"`{signoff_state.get('runtime_patch_signoff_bundle_ready_for_review')}`"
        ),
        (
            "- Reviewed runtime patch exists: "
            f"`{signoff_state.get('reviewed_runtime_patch_exists')}`"
        ),
        (
            "- Actual signoff record validation status: "
            f"`{signoff_state.get('actual_signoff_record_validation_status')}`"
        ),
        (
            "- Required reviewer statement ids: "
            f"`{', '.join(_string_list(signoff_state.get('required_reviewer_statement_ids'))) or '(none)'}`"
        ),
        (
            "- Still blocked gate ids: "
            f"`{', '.join(_string_list(signoff_state.get('still_blocked_gate_ids'))) or '(none)'}`"
        ),
        "",
        "## Acceptance Execution State",
        "",
        f"- Acceptance executed: `{execution_state.get('acceptance_executed')}`",
        (
            "- Acceptance result provided: "
            f"`{execution_state.get('acceptance_result_provided')}`"
        ),
        (
            "- Acceptance result validation performed: "
            f"`{execution_state.get('acceptance_result_validation_performed')}`"
        ),
        (
            "- Acceptance result validation passed: "
            f"`{execution_state.get('acceptance_result_validation_passed')}`"
        ),
        (
            "- Acceptance result validation summary: "
            f"{execution_state.get('acceptance_result_validation_summary')}"
        ),
        "",
        "## Missing Prerequisites Before Execution Authorization",
        "",
        "| Gate | Current value | Detail |",
        "| --- | --- | --- |",
    ]
    for entry in list(
        execution_gate.get("missing_prerequisites_before_execution_authorization", [])
    ):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('gate_id'))} | "
                f"{_markdown_cell(entry.get('current_value'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Future Execution Checklist",
            "",
        ]
    )
    for entry in list(execution_gate.get("future_execution_checklist", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"- `{entry.get('checklist_id')}`: {entry.get('detail')}"
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    execution_gate = _mapping(report.get("acceptance_execution_gate"))
    locked_execution_target = _mapping(execution_gate.get("locked_execution_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance execution gate",
            f"acceptance_execution_gate_ready={status.get('acceptance_execution_gate_ready')}",
            "acceptance_execution_authorization_prerequisites_met="
            + str(
                status.get("acceptance_execution_authorization_prerequisites_met")
            ),
            f"acceptance_execution_authorized={status.get('acceptance_execution_authorized')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"acceptance_executed={status.get('acceptance_executed')}",
            "missing_prerequisite_gate_ids="
            + ",".join(_string_list(status.get("missing_prerequisite_gate_ids"))),
            f"production_profile_id={execution_gate.get('production_profile_id')}",
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path")),
            f"recommended_next_step={status.get('recommended_next_step')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_acceptance_execution_gate",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


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
        and bool(metadata.get("default_off", False))
        and not bool(metadata.get("runtime_precheck_enabled", False))
        and not bool(metadata.get("runtime_semantics_changed", False))
        and not bool(metadata.get("proof_source", False))
        and not bool(metadata.get("candidate_elimination_claim", False))
        and not bool(metadata.get("solver_invoked", False))
        for metadata in relevant
    )


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


def _gate(
    gate_id: str,
    satisfied: bool,
    blocking: bool,
    detail: str,
) -> Dict[str, Any]:
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
    result = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

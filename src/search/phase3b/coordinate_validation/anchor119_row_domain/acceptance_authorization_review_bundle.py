from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_EXECUTION_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
)
ACCEPTANCE_REFRESH_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
)
ACCEPTANCE_EXECUTION_STAGING_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
)
ACCEPTANCE_RESULT_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_v1"
)
LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_20260424/"
    "anchor119_row_domain_acceptance_execution_gate.json"
)
DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_20260424/"
    "anchor119_row_domain_acceptance_refresh_prep.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_20260424/"
    "anchor119_row_domain_acceptance_execution_staging.json"
)
DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_20260424/"
    "anchor119_row_domain_acceptance_result_validator.json"
)
DEFAULT_RUNTIME_PATCH_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle(
    project_root: Path,
    *,
    acceptance_execution_gate_path: Optional[Path] = None,
    acceptance_refresh_prep_path: Optional[Path] = None,
    acceptance_execution_staging_path: Optional[Path] = None,
    acceptance_result_validator_path: Optional[Path] = None,
    runtime_patch_signoff_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    acceptance_execution_gate_resolved = _resolve_path(
        project_root,
        acceptance_execution_gate_path
        if acceptance_execution_gate_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH,
    )
    acceptance_refresh_prep_resolved = _resolve_path(
        project_root,
        acceptance_refresh_prep_path
        if acceptance_refresh_prep_path is not None
        else DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH,
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
    runtime_patch_signoff_bundle_resolved = _resolve_path(
        project_root,
        runtime_patch_signoff_bundle_path
        if runtime_patch_signoff_bundle_path is not None
        else DEFAULT_RUNTIME_PATCH_SIGNOFF_BUNDLE_PATH,
    )

    acceptance_execution_gate_report, acceptance_execution_gate_error = (
        _load_json_mapping(acceptance_execution_gate_resolved)
    )
    acceptance_refresh_prep_report, acceptance_refresh_prep_error = (
        _load_json_mapping(acceptance_refresh_prep_resolved)
    )
    acceptance_execution_staging_report, acceptance_execution_staging_error = (
        _load_json_mapping(acceptance_execution_staging_resolved)
    )
    acceptance_result_validator_report, acceptance_result_validator_error = (
        _load_json_mapping(acceptance_result_validator_resolved)
    )
    runtime_patch_signoff_bundle_report, runtime_patch_signoff_bundle_error = (
        _load_json_mapping(runtime_patch_signoff_bundle_resolved)
    )

    acceptance_execution_gate_meta = (
        _mapping(acceptance_execution_gate_report.get("metadata"))
        if acceptance_execution_gate_report
        else {}
    )
    acceptance_execution_gate_status = (
        _mapping(acceptance_execution_gate_report.get("status"))
        if acceptance_execution_gate_report
        else {}
    )
    acceptance_execution_gate = (
        _mapping(acceptance_execution_gate_report.get("acceptance_execution_gate"))
        if acceptance_execution_gate_report
        else {}
    )
    gate_locked_execution_target = _mapping(
        acceptance_execution_gate.get("locked_execution_target")
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
    acceptance_result_validator = (
        _mapping(
            acceptance_result_validator_report.get("acceptance_result_validator")
        )
        if acceptance_result_validator_report
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
    candidate = _first_mapping(
        acceptance_execution_gate_report.get("candidate")
        if acceptance_execution_gate_report
        else None,
        acceptance_refresh_prep_report.get("candidate")
        if acceptance_refresh_prep_report
        else None,
        acceptance_execution_staging_report.get("candidate")
        if acceptance_execution_staging_report
        else None,
        acceptance_result_validator_report.get("candidate")
        if acceptance_result_validator_report
        else None,
        runtime_patch_signoff_bundle_report.get("candidate")
        if runtime_patch_signoff_bundle_report
        else None,
    )

    acceptance_execution_gate_present = bool(
        acceptance_execution_gate_report is not None
        and acceptance_execution_gate_error is None
        and acceptance_execution_gate_meta.get("source")
        == ACCEPTANCE_EXECUTION_GATE_SOURCE
    )
    acceptance_refresh_prep_present = bool(
        acceptance_refresh_prep_report is not None
        and acceptance_refresh_prep_error is None
        and acceptance_refresh_prep_meta.get("source") == ACCEPTANCE_REFRESH_PREP_SOURCE
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
    runtime_patch_signoff_bundle_present = bool(
        runtime_patch_signoff_bundle_report is not None
        and runtime_patch_signoff_bundle_error is None
        and runtime_patch_signoff_bundle_meta.get("source")
        == RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE
    )

    acceptance_execution_gate_ready = bool(
        acceptance_execution_gate_status.get("acceptance_execution_gate_ready", False)
    )
    acceptance_refresh_ready_for_review = bool(
        acceptance_refresh_prep_status.get("acceptance_refresh_ready_for_review", False)
    )
    acceptance_execution_staging_ready = bool(
        acceptance_execution_staging_status.get(
            "acceptance_execution_staging_ready", False
        )
    )
    acceptance_result_validator_ready = bool(
        acceptance_result_validator_status.get(
            "acceptance_result_validator_ready", False
        )
    )
    runtime_patch_signoff_bundle_ready_for_review = bool(
        runtime_patch_signoff_bundle_status.get(
            "reviewed_runtime_patch_signoff_ready_for_review",
            runtime_patch_signoff_bundle_status.get("signoff_bundle_ready", False),
        )
    )

    production_profile_id, production_profile_locked = _locked_value(
        [
            gate_locked_execution_target.get("production_profile_id"),
            acceptance_execution_gate.get("production_profile_id"),
            acceptance_refresh_prep.get("production_profile_id"),
            acceptance_execution_staging.get("production_profile_id"),
            acceptance_result_validator.get("production_profile_id"),
        ]
    )
    production_profile_locked_prod_4x4_normal = bool(
        production_profile_locked and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )

    exact_future_acceptance_command, exact_future_acceptance_command_locked = (
        _locked_value(
            [
                gate_locked_execution_target.get("exact_future_acceptance_command"),
                acceptance_refresh_prep.get("acceptance_command"),
                acceptance_execution_staging.get("exact_command_to_run_later"),
                runtime_patch_signoff_bundle.get("production_acceptance_command"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_locked = (
        _locked_value(
            [
                gate_locked_execution_target.get("exact_future_acceptance_result_path"),
                acceptance_refresh_prep.get("suite_output_path"),
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
        and _normalize_path_text(exact_future_acceptance_result_path)
        == _normalize_path_text(command_output_path)
    )

    reviewed_runtime_patch_exists_from_gate = bool(
        acceptance_execution_gate_status.get("reviewed_runtime_patch_exists", False)
    )
    reviewed_runtime_patch_exists_from_bundle = bool(
        runtime_patch_signoff_bundle_status.get("reviewed_runtime_patch_exists", False)
    )
    reviewed_runtime_patch_exists_locked = bool(
        acceptance_execution_gate_present
        and runtime_patch_signoff_bundle_present
        and reviewed_runtime_patch_exists_from_gate
        == reviewed_runtime_patch_exists_from_bundle
    )
    reviewed_runtime_patch_exists = bool(
        reviewed_runtime_patch_exists_from_gate
        or reviewed_runtime_patch_exists_from_bundle
    )

    runtime_enablement_still_blocked = all(
        not bool(value)
        for value in [
            acceptance_execution_gate_status.get("runtime_enablement_allowed", False),
            acceptance_refresh_prep_status.get("runtime_enablement_allowed", False),
            acceptance_execution_staging_status.get("runtime_enablement_allowed", False),
            acceptance_result_validator_status.get("runtime_enablement_allowed", False),
            runtime_patch_signoff_bundle_status.get("runtime_enablement_allowed", False),
        ]
    )
    acceptance_execution_authorized = bool(
        acceptance_execution_gate_status.get("acceptance_execution_authorized", False)
    )
    acceptance_executed = any(
        bool(value)
        for value in [
            acceptance_execution_gate_status.get("acceptance_executed", False),
            acceptance_execution_staging_status.get("acceptance_executed", False),
            acceptance_execution_gate_meta.get("acceptance_executed", False),
            acceptance_refresh_prep_meta.get("acceptance_executed", False),
            acceptance_execution_staging_meta.get("acceptance_executed", False),
            acceptance_result_validator_meta.get("acceptance_executed", False),
            runtime_patch_signoff_bundle_meta.get("acceptance_executed", False),
        ]
    )
    gate_does_not_authorize_execution = bool(
        acceptance_execution_gate.get("does_not_authorize_execution", False)
    )
    review_only_contract_retained = _review_only_contract_retained(
        acceptance_execution_gate_meta,
        acceptance_refresh_prep_meta,
        acceptance_execution_staging_meta,
        acceptance_result_validator_meta,
        runtime_patch_signoff_bundle_meta,
    )

    signoff_required_statement_ids = _statement_id_list(
        runtime_patch_signoff_bundle.get("required_reviewer_statements")
    )
    gate_reported_missing_prerequisite_gate_ids = _string_list(
        acceptance_execution_gate_status.get("missing_prerequisite_gate_ids")
    )
    default_production_runner = str(
        gate_locked_execution_target.get("default_production_runner")
        or acceptance_refresh_prep.get("default_production_runner")
        or ""
    )

    checks = [
        _check(
            "acceptance_execution_gate_present",
            "pass" if acceptance_execution_gate_present else "fail",
            "acceptance execution gate loaded"
            if acceptance_execution_gate_present
            else _presence_detail(
                acceptance_execution_gate_report,
                acceptance_execution_gate_error,
                acceptance_execution_gate_meta,
                ACCEPTANCE_EXECUTION_GATE_SOURCE,
                project_root,
                acceptance_execution_gate_resolved,
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
            "runtime_patch_signoff_bundle_present",
            "pass" if runtime_patch_signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if runtime_patch_signoff_bundle_present
            else _presence_detail(
                runtime_patch_signoff_bundle_report,
                runtime_patch_signoff_bundle_error,
                runtime_patch_signoff_bundle_meta,
                RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE,
                project_root,
                runtime_patch_signoff_bundle_resolved,
            ),
        ),
        _check(
            "acceptance_execution_gate_ready",
            "pass" if acceptance_execution_gate_ready else "fail",
            str(acceptance_execution_gate_status.get("acceptance_execution_gate_ready")),
        ),
        _check(
            "acceptance_refresh_ready_for_review",
            "pass" if acceptance_refresh_ready_for_review else "fail",
            str(acceptance_refresh_prep_status.get("acceptance_refresh_ready_for_review")),
        ),
        _check(
            "acceptance_execution_staging_ready",
            "pass" if acceptance_execution_staging_ready else "fail",
            str(
                acceptance_execution_staging_status.get(
                    "acceptance_execution_staging_ready"
                )
            ),
        ),
        _check(
            "acceptance_result_validator_ready",
            "pass" if acceptance_result_validator_ready else "fail",
            str(
                acceptance_result_validator_status.get(
                    "acceptance_result_validator_ready"
                )
            ),
        ),
        _check(
            "runtime_patch_signoff_bundle_ready_for_review",
            "pass" if runtime_patch_signoff_bundle_ready_for_review else "fail",
            str(
                runtime_patch_signoff_bundle_status.get(
                    "reviewed_runtime_patch_signoff_ready_for_review",
                    runtime_patch_signoff_bundle_status.get("signoff_bundle_ready"),
                )
            ),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "all upstream artifacts remain review-only/default-off/no-solve"
            if review_only_contract_retained
            else "expected review-only/default-off/spec-only/no-solve metadata upstream",
        ),
        _check(
            "gate_does_not_authorize_execution",
            "pass" if gate_does_not_authorize_execution else "fail",
            str(gate_does_not_authorize_execution),
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
            command_output_path or "missing_suite_output_in_command",
        ),
        _check(
            "reviewed_runtime_patch_exists_locked",
            "pass" if reviewed_runtime_patch_exists_locked else "fail",
            (
                "gate_reviewed_runtime_patch_exists="
                f"{reviewed_runtime_patch_exists_from_gate} "
                "bundle_reviewed_runtime_patch_exists="
                f"{reviewed_runtime_patch_exists_from_bundle}"
            ),
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_still_blocked else "fail",
            (
                "gate_runtime_enablement_allowed="
                f"{bool(acceptance_execution_gate_status.get('runtime_enablement_allowed', False))} "
                "refresh_runtime_enablement_allowed="
                f"{bool(acceptance_refresh_prep_status.get('runtime_enablement_allowed', False))} "
                "staging_runtime_enablement_allowed="
                f"{bool(acceptance_execution_staging_status.get('runtime_enablement_allowed', False))} "
                "result_validator_runtime_enablement_allowed="
                f"{bool(acceptance_result_validator_status.get('runtime_enablement_allowed', False))} "
                "signoff_bundle_runtime_enablement_allowed="
                f"{bool(runtime_patch_signoff_bundle_status.get('runtime_enablement_allowed', False))}"
            ),
        ),
        _check(
            "acceptance_execution_authorized_still_false",
            "pass" if not acceptance_execution_authorized else "fail",
            f"acceptance_execution_authorized={acceptance_execution_authorized}",
        ),
        _check(
            "acceptance_executed_still_false",
            "pass" if not acceptance_executed else "fail",
            f"acceptance_executed={acceptance_executed}",
        ),
    ]

    gates = [
        _gate(
            "acceptance_execution_gate_ready",
            acceptance_execution_gate_ready,
            True,
            "Acceptance execution gate must already be review-ready before any future execution-authorization review can start.",
        ),
        _gate(
            "acceptance_refresh_ready_for_review",
            acceptance_refresh_ready_for_review,
            True,
            "Acceptance refresh prep must already be review-ready and keep the locked prod_4x4_normal target explicit.",
        ),
        _gate(
            "acceptance_execution_staging_ready",
            acceptance_execution_staging_ready,
            True,
            "Acceptance execution staging must already be review-ready before any future authorization decision can consider the locked command.",
        ),
        _gate(
            "acceptance_result_validator_ready",
            acceptance_result_validator_ready,
            True,
            "Acceptance result validator must already be review-ready for the locked future output path.",
        ),
        _gate(
            "runtime_patch_signoff_bundle_ready_for_review",
            runtime_patch_signoff_bundle_ready_for_review,
            True,
            "Runtime patch signoff bundle must already be review-ready before any future acceptance-execution authorization review.",
        ),
        _gate(
            "production_profile_locked_prod_4x4_normal",
            production_profile_locked_prod_4x4_normal,
            True,
            "The future execution target must remain pinned to the locked prod_4x4_normal profile.",
        ),
        _gate(
            "exact_future_acceptance_command_locked",
            exact_future_acceptance_command_locked,
            True,
            "The future production-acceptance command must stay locked across the upstream review artifacts.",
        ),
        _gate(
            "exact_future_acceptance_result_path_locked",
            exact_future_acceptance_result_path_locked,
            True,
            "The future production-acceptance result path must stay locked across the upstream review artifacts.",
        ),
        _gate(
            "command_matches_result_path",
            command_matches_result_path,
            True,
            "The locked production-acceptance command must point to the same future result path tracked by the review artifacts.",
        ),
        _gate(
            "runtime_enablement_still_blocked",
            runtime_enablement_still_blocked,
            True,
            "Runtime enablement must remain forbidden throughout this bundle and any later authorization review.",
        ),
        _gate(
            "execution_not_already_authorized",
            not acceptance_execution_authorized,
            True,
            "This bundle is pre-authorization only; acceptance_execution_authorized must remain false here.",
        ),
        _gate(
            "acceptance_not_executed_yet",
            not acceptance_executed,
            True,
            "This bundle is pre-execution only; production acceptance must remain unexecuted here.",
        ),
        _gate(
            "reviewed_runtime_patch_exists",
            reviewed_runtime_patch_exists,
            True,
            "A separately reviewed runtime patch signoff record must exist before a future execution-authorization review could ever authorize the locked prod_4x4_normal run.",
        ),
        _gate(
            "review_bundle_does_not_authorize_execution",
            True,
            False,
            "This bundle formalizes the future authorization-review contract only. It does not authorize execution.",
        ),
    ]

    acceptance_authorization_review_bundle_ready = all(
        check["status"] == "pass" for check in checks
    )
    future_execution_authorization_review_prerequisites_met = all(
        bool(gate.get("satisfied")) for gate in gates if bool(gate.get("blocking"))
    )
    missing_prerequisites_before_future_execution_authorization_review = [
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
        for entry in missing_prerequisites_before_future_execution_authorization_review
    ]

    required_review_conclusions = [
        _review_conclusion(
            "locked_prod_4x4_normal_target_confirmed",
            production_profile_locked_prod_4x4_normal
            and exact_future_acceptance_command_locked
            and exact_future_acceptance_result_path_locked
            and command_matches_result_path,
            (
                "Confirm that the future execution target remains locked to prod_4x4_normal, "
                "with the exact command and exact result path carried forward unchanged."
            ),
        ),
        _review_conclusion(
            "runtime_patch_signoff_bundle_review_ready",
            runtime_patch_signoff_bundle_ready_for_review,
            (
                "Confirm that the runtime patch signoff bundle is already review-ready, "
                "because execution authorization review cannot outrun patch-signoff review."
            ),
        ),
        _review_conclusion(
            "reviewed_runtime_patch_exists",
            reviewed_runtime_patch_exists,
            (
                "Confirm that a separately reviewed runtime patch signoff record exists "
                "before any future execution authorization review could ever approve the "
                "locked prod_4x4_normal command."
            ),
        ),
        _review_conclusion(
            "acceptance_refresh_and_staging_contracts_ready",
            acceptance_refresh_ready_for_review and acceptance_execution_staging_ready,
            (
                "Confirm that acceptance refresh prep and acceptance execution staging both "
                "remain review-ready and still point at the same locked execution target."
            ),
        ),
        _review_conclusion(
            "acceptance_result_validator_ready",
            acceptance_result_validator_ready,
            (
                "Confirm that the locked acceptance-result validator stays ready to validate "
                "the future prod_4x4_normal output path after any later authorized run."
            ),
        ),
        _review_conclusion(
            "runtime_enablement_remains_forbidden",
            runtime_enablement_still_blocked,
            (
                "Confirm that runtime_enablement_allowed remains false throughout this bundle "
                "and any future execution-authorization review."
            ),
        ),
    ]

    if not acceptance_authorization_review_bundle_ready:
        recommended_next_step = "repair_acceptance_authorization_review_bundle_inputs"
        handoff_recommendation = (
            "Acceptance-authorization review bundle is blocked; repair the missing or "
            "mismatched upstream review artifacts before using this bundle for any future "
            "authorization review."
        )
    elif missing_prerequisite_gate_ids:
        recommended_next_step = (
            "complete_reviewed_runtime_patch_signoff_then_run_separate_acceptance_authorization_review"
        )
        handoff_recommendation = (
            "Acceptance-authorization review bundle is ready as review-only/default-off "
            "scaffolding: keep acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, and acceptance_executed=false. The locked "
            "prod_4x4_normal command/result target is explicit, but current missing "
            "prerequisite(s) still block any later authorization decision: "
            f"{', '.join(missing_prerequisite_gate_ids)}. Next step: complete the reviewed "
            "runtime patch signoff record path, then run a separate future "
            "acceptance-authorization review before anybody could authorize "
            f"`{exact_future_acceptance_command}` to write "
            f"`{exact_future_acceptance_result_path}`."
        )
    else:
        recommended_next_step = (
            "run_separate_acceptance_authorization_review_without_enabling_runtime"
        )
        handoff_recommendation = (
            "Acceptance-authorization review bundle is ready and all upstream prerequisites "
            "are satisfied, but this artifact still does not authorize execution. A "
            "separate future review must explicitly decide whether to authorize the locked "
            f"prod_4x4_normal command `{exact_future_acceptance_command}` to write "
            f"`{exact_future_acceptance_result_path}`, while "
            "runtime_enablement_allowed remains false here."
        )

    future_authorization_review_record_template = {
        "record_type": "acceptance_execution_authorization_review_record_v0",
        "reviewer_id": "",
        "reviewed_at": "",
        "verdict": "pending",
        "authorization_granted": False,
        "runtime_enablement_allowed": False,
        "acceptance_executed": False,
        "locked_execution_target": {
            "production_profile_id": production_profile_id,
            "default_production_runner": default_production_runner,
            "exact_future_acceptance_command": exact_future_acceptance_command,
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "required_conclusion_ids": [
            entry["conclusion_id"] for entry in required_review_conclusions
        ],
        "required_runtime_patch_statement_ids": signoff_required_statement_ids,
        "missing_prerequisite_gate_ids": list(missing_prerequisite_gate_ids),
        "notes": "",
    }

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_review_bundle_review_only_not_execution_authorization"
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
            "acceptance_execution_gate": _display_path(
                project_root, acceptance_execution_gate_resolved
            ),
            "acceptance_refresh_prep": _display_path(
                project_root, acceptance_refresh_prep_resolved
            ),
            "acceptance_execution_staging": _display_path(
                project_root, acceptance_execution_staging_resolved
            ),
            "acceptance_result_validator": _display_path(
                project_root, acceptance_result_validator_resolved
            ),
            "runtime_patch_signoff_bundle": _display_path(
                project_root, runtime_patch_signoff_bundle_resolved
            ),
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_authorization_review_bundle_ready": bool(
                acceptance_authorization_review_bundle_ready
            ),
            "future_execution_authorization_review_prerequisites_met": bool(
                future_execution_authorization_review_prerequisites_met
            ),
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "missing_prerequisite_gate_ids": missing_prerequisite_gate_ids,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_authorization_review_bundle": {
            "guard_id": acceptance_execution_gate.get("guard_id")
            or acceptance_execution_staging.get("guard_id")
            or acceptance_refresh_prep.get("guard_id")
            or acceptance_result_validator.get("guard_id"),
            "payload_id": acceptance_execution_gate.get("payload_id")
            or acceptance_execution_staging.get("payload_id")
            or acceptance_refresh_prep.get("payload_id")
            or acceptance_result_validator.get("payload_id"),
            "production_profile_id": production_profile_id,
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
                "exact_future_acceptance_command": exact_future_acceptance_command,
                "exact_future_acceptance_result_path": (
                    exact_future_acceptance_result_path
                ),
                "command_matches_result_path": bool(command_matches_result_path),
            },
            "reviewed_runtime_patch_state": {
                "runtime_patch_signoff_bundle_ready_for_review": bool(
                    runtime_patch_signoff_bundle_ready_for_review
                ),
                "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
                "reviewed_runtime_patch_exists_locked": bool(
                    reviewed_runtime_patch_exists_locked
                ),
                "required_reviewer_statement_ids": signoff_required_statement_ids,
                "gate_reported_missing_prerequisite_gate_ids": (
                    gate_reported_missing_prerequisite_gate_ids
                ),
            },
            "required_review_conclusions_before_future_execution_authorization_review": (
                required_review_conclusions
            ),
            "current_missing_prerequisites_before_future_execution_authorization_review": (
                missing_prerequisites_before_future_execution_authorization_review
            ),
            "future_authorization_review_record_template": (
                future_authorization_review_record_template
            ),
            "authorization_notice": (
                "This bundle is review-only/default-off scaffolding. It does not "
                "authorize execution, does not execute acceptance, and does not allow "
                "runtime enablement."
            ),
            "handoff_recommendation": handoff_recommendation,
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("acceptance_authorization_review_bundle"))
    locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    reviewed_runtime_patch_state = _mapping(bundle.get("reviewed_runtime_patch_state"))
    review_template = _mapping(bundle.get("future_authorization_review_record_template"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Review Bundle",
        "",
        (
            "- Acceptance authorization review bundle ready: "
            f"`{status.get('acceptance_authorization_review_bundle_ready')}`"
        ),
        (
            "- Future execution authorization review prerequisites met: "
            f"`{status.get('future_execution_authorization_review_prerequisites_met')}`"
        ),
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        (
            "- Missing prerequisite gate ids: "
            f"`{', '.join(_string_list(status.get('missing_prerequisite_gate_ids'))) or '(none)'}`"
        ),
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Review Bundle",
        "",
        f"- Guard id: `{bundle.get('guard_id')}`",
        f"- Payload id: `{bundle.get('payload_id')}`",
        f"- Production profile id: `{bundle.get('production_profile_id')}`",
        f"- Review only: `{bundle.get('review_only')}`",
        (
            "- Does not authorize execution: "
            f"`{bundle.get('does_not_authorize_execution')}`"
        ),
        f"- Authorization notice: {bundle.get('authorization_notice')}",
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
        (
            "- Command matches result path: "
            f"`{locked_execution_target.get('command_matches_result_path')}`"
        ),
        "",
        "## Required Review Conclusions",
        "",
        "| Conclusion | Required | Currently satisfied | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(
        bundle.get(
            "required_review_conclusions_before_future_execution_authorization_review",
            [],
        )
    ):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('conclusion_id'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(entry.get('currently_satisfied'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Current Missing Prerequisites",
            "",
            "| Gate | Current value | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(
        bundle.get(
            "current_missing_prerequisites_before_future_execution_authorization_review",
            [],
        )
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
            "## Reviewed Runtime Patch State",
            "",
            (
                "- Runtime patch signoff bundle ready for review: "
                f"`{reviewed_runtime_patch_state.get('runtime_patch_signoff_bundle_ready_for_review')}`"
            ),
            (
                "- Reviewed runtime patch exists: "
                f"`{reviewed_runtime_patch_state.get('reviewed_runtime_patch_exists')}`"
            ),
            (
                "- Reviewed runtime patch state locked: "
                f"`{reviewed_runtime_patch_state.get('reviewed_runtime_patch_exists_locked')}`"
            ),
            (
                "- Required reviewer statement ids: "
                f"`{', '.join(_string_list(reviewed_runtime_patch_state.get('required_reviewer_statement_ids'))) or '(none)'}`"
            ),
            (
                "- Gate reported missing prerequisite ids: "
                f"`{', '.join(_string_list(reviewed_runtime_patch_state.get('gate_reported_missing_prerequisite_gate_ids'))) or '(none)'}`"
            ),
            "",
            "## Future Authorization Review Template",
            "",
            f"- Record type: `{review_template.get('record_type')}`",
            f"- Verdict: `{review_template.get('verdict')}`",
            f"- Authorization granted: `{review_template.get('authorization_granted')}`",
            (
                "- Required conclusion ids: "
                f"`{', '.join(_string_list(review_template.get('required_conclusion_ids'))) or '(none)'}`"
            ),
            (
                "- Required runtime patch statement ids: "
                f"`{', '.join(_string_list(review_template.get('required_runtime_patch_statement_ids'))) or '(none)'}`"
            ),
            (
                "- Template missing prerequisite gate ids: "
                f"`{', '.join(_string_list(review_template.get('missing_prerequisite_gate_ids'))) or '(none)'}`"
            ),
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("acceptance_authorization_review_bundle"))
    locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization review bundle",
            "acceptance_authorization_review_bundle_ready="
            + str(status.get("acceptance_authorization_review_bundle_ready")),
            "future_execution_authorization_review_prerequisites_met="
            + str(status.get("future_execution_authorization_review_prerequisites_met")),
            "acceptance_execution_authorized="
            + str(status.get("acceptance_execution_authorized")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            f"acceptance_executed={status.get('acceptance_executed')}",
            "reviewed_runtime_patch_exists="
            + str(status.get("reviewed_runtime_patch_exists")),
            "missing_prerequisite_gate_ids="
            + ",".join(_string_list(status.get("missing_prerequisite_gate_ids"))),
            f"production_profile_id={bundle.get('production_profile_id')}",
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path")),
            f"recommended_next_step={status.get('recommended_next_step')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_acceptance_authorization_review_bundle",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_text(
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
        and not bool(metadata.get("acceptance_executed", False))
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


def _review_conclusion(
    conclusion_id: str,
    currently_satisfied: bool,
    detail: str,
) -> Dict[str, Any]:
    return {
        "conclusion_id": str(conclusion_id),
        "required": True,
        "currently_satisfied": bool(currently_satisfied),
        "detail": str(detail),
    }


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _statement_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        statement_id = str(entry.get("statement_id") or "").strip()
        if statement_id:
            result.append(statement_id)
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
    result = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

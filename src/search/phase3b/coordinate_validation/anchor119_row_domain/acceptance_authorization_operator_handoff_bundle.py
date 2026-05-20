from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_scaffold_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_validator_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_example_bundle_v1"
)
ACCEPTANCE_EXECUTION_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
)
ACCEPTANCE_EXECUTION_STAGING_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
)
ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_operator_handoff_bundle_v1"
)

LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
VALIDATOR_BUILDER_SCRIPT = (
    "scripts/phase3b/coordinate_validation/anchor119_row_domain/"
    "build_acceptance_authorization_review_record_validator.py"
)
EXAMPLE_BUNDLE_BUILDER_SCRIPT = (
    "scripts/phase3b/coordinate_validation/anchor119_row_domain/"
    "build_acceptance_authorization_review_record_example_bundle.py"
)

DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_scaffold_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_scaffold.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_validator_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_validator.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_example_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_example_bundle.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_execution_gate_20260424/"
    "anchor119_row_domain_acceptance_execution_gate.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_execution_staging_20260424/"
    "anchor119_row_domain_acceptance_execution_staging.json"
)

REFERENCE_ONLY_NOTICE = (
    "Synthetic example is reference only; it is not an actual human authorization "
    "review record and does not authorize execution."
)
EXPLICIT_NON_GOALS = [
    "This handoff bundle is review-only/operator-facing scaffolding for a future manual authorization-review path.",
    "This bundle does not authorize the locked prod_4x4_normal acceptance command.",
    "This bundle does not enable runtime or change runtime semantics.",
    "This bundle does not execute acceptance or validate a real acceptance result.",
    "This bundle does not claim solver work, proof promotion, or candidate elimination.",
]
DISALLOWED_ACTIONS = [
    "Do not authorize execution from this bundle.",
    "Do not enable runtime from this bundle.",
    "Do not execute acceptance from this bundle.",
    "Do not treat the synthetic example bundle as evidence that any human authorization review has happened.",
    "Do not change the locked prod_4x4_normal production profile, command, or result path in a future manual review record.",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle(
    project_root: Path,
    *,
    acceptance_authorization_review_record_scaffold_path: Optional[Path] = None,
    acceptance_authorization_review_record_validator_path: Optional[Path] = None,
    acceptance_authorization_review_record_example_bundle_path: Optional[Path] = None,
    acceptance_execution_gate_path: Optional[Path] = None,
    acceptance_execution_staging_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    scaffold_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_record_scaffold_path
        if acceptance_authorization_review_record_scaffold_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_PATH,
    )
    validator_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_record_validator_path
        if acceptance_authorization_review_record_validator_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH,
    )
    example_bundle_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_record_example_bundle_path
        if acceptance_authorization_review_record_example_bundle_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH,
    )
    execution_gate_resolved = _resolve_path(
        project_root,
        acceptance_execution_gate_path
        if acceptance_execution_gate_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH,
    )
    execution_staging_resolved = _resolve_path(
        project_root,
        acceptance_execution_staging_path
        if acceptance_execution_staging_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH,
    )

    scaffold_report, scaffold_error = _load_json_mapping(scaffold_resolved)
    validator_report, validator_error = _load_json_mapping(validator_resolved)
    example_bundle_report, example_bundle_error = _load_json_mapping(
        example_bundle_resolved
    )
    execution_gate_report, execution_gate_error = _load_json_mapping(
        execution_gate_resolved
    )
    execution_staging_report, execution_staging_error = _load_json_mapping(
        execution_staging_resolved
    )

    scaffold_meta = (
        _mapping(scaffold_report.get("metadata")) if scaffold_report is not None else {}
    )
    validator_meta = (
        _mapping(validator_report.get("metadata"))
        if validator_report is not None
        else {}
    )
    example_bundle_meta = (
        _mapping(example_bundle_report.get("metadata"))
        if example_bundle_report is not None
        else {}
    )
    execution_gate_meta = (
        _mapping(execution_gate_report.get("metadata"))
        if execution_gate_report is not None
        else {}
    )
    execution_staging_meta = (
        _mapping(execution_staging_report.get("metadata"))
        if execution_staging_report is not None
        else {}
    )

    scaffold_status = (
        _mapping(scaffold_report.get("status")) if scaffold_report is not None else {}
    )
    validator_status = (
        _mapping(validator_report.get("status"))
        if validator_report is not None
        else {}
    )
    example_bundle_status = (
        _mapping(example_bundle_report.get("status"))
        if example_bundle_report is not None
        else {}
    )
    execution_gate_status = (
        _mapping(execution_gate_report.get("status"))
        if execution_gate_report is not None
        else {}
    )
    execution_staging_status = (
        _mapping(execution_staging_report.get("status"))
        if execution_staging_report is not None
        else {}
    )

    scaffold = (
        _mapping(scaffold_report.get("acceptance_authorization_review_record_scaffold"))
        if scaffold_report is not None
        else {}
    )
    validator = (
        _mapping(validator_report.get("acceptance_authorization_review_record_validator"))
        if validator_report is not None
        else {}
    )
    example_bundle = (
        _mapping(
            example_bundle_report.get(
                "acceptance_authorization_review_record_example_bundle"
            )
        )
        if example_bundle_report is not None
        else {}
    )
    execution_gate = (
        _mapping(execution_gate_report.get("acceptance_execution_gate"))
        if execution_gate_report is not None
        else {}
    )
    execution_staging = (
        _mapping(execution_staging_report.get("acceptance_execution_staging"))
        if execution_staging_report is not None
        else {}
    )

    candidate = _first_mapping(
        scaffold_report.get("candidate") if scaffold_report is not None else None,
        validator_report.get("candidate") if validator_report is not None else None,
        example_bundle_report.get("candidate")
        if example_bundle_report is not None
        else None,
        execution_gate_report.get("candidate")
        if execution_gate_report is not None
        else None,
        execution_staging_report.get("candidate")
        if execution_staging_report is not None
        else None,
    )

    scaffold_present = bool(
        scaffold_report is not None
        and scaffold_error is None
        and scaffold_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE
    )
    validator_present = bool(
        validator_report is not None
        and validator_error is None
        and validator_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE
    )
    example_bundle_present = bool(
        example_bundle_report is not None
        and example_bundle_error is None
        and example_bundle_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE
    )
    execution_gate_present = bool(
        execution_gate_report is not None
        and execution_gate_error is None
        and execution_gate_meta.get("source") == ACCEPTANCE_EXECUTION_GATE_SOURCE
    )
    execution_staging_present = bool(
        execution_staging_report is not None
        and execution_staging_error is None
        and execution_staging_meta.get("source") == ACCEPTANCE_EXECUTION_STAGING_SOURCE
    )

    scaffold_ready = bool(
        scaffold_status.get("acceptance_authorization_review_record_scaffold_ready", False)
    )
    validator_ready = bool(
        validator_status.get(
            "acceptance_authorization_review_record_validator_ready", False
        )
    )
    example_bundle_ready = bool(
        example_bundle_status.get(
            "acceptance_authorization_review_record_example_bundle_ready", False
        )
    )
    execution_gate_ready = bool(
        execution_gate_status.get("acceptance_execution_gate_ready", False)
    )
    execution_staging_ready = bool(
        execution_staging_status.get("acceptance_execution_staging_ready", False)
    )

    scaffold_locked_target = _mapping(scaffold.get("locked_execution_target"))
    validator_locked_target = _mapping(validator.get("locked_execution_target"))
    example_bundle_locked_target = _mapping(
        example_bundle.get("locked_execution_target")
    )
    execution_gate_locked_target = _mapping(
        execution_gate.get("locked_execution_target")
    )
    scaffold_payload = _mapping(
        scaffold.get("scaffolded_authorization_review_record_payload")
    )

    production_profile_id, production_profile_locked = _locked_value(
        [
            scaffold_locked_target.get("production_profile_id"),
            validator_locked_target.get("production_profile_id"),
            example_bundle_locked_target.get("production_profile_id"),
            execution_gate_locked_target.get("production_profile_id"),
            execution_staging.get("production_profile_id"),
        ]
    )
    production_profile_locked_prod_4x4_normal = bool(
        production_profile_locked and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )

    default_production_runner, default_production_runner_locked = _locked_value(
        [
            scaffold_locked_target.get("default_production_runner"),
            validator_locked_target.get("default_production_runner"),
            example_bundle_locked_target.get("default_production_runner"),
            execution_gate_locked_target.get("default_production_runner"),
        ],
        normalize=_normalize_path_text,
    )
    exact_future_acceptance_command, exact_future_acceptance_command_locked = (
        _locked_value(
            [
                scaffold_locked_target.get("exact_future_acceptance_command"),
                validator_locked_target.get("exact_future_acceptance_command"),
                example_bundle_locked_target.get("exact_future_acceptance_command"),
                execution_gate_locked_target.get("exact_future_acceptance_command"),
                execution_staging.get("exact_command_to_run_later"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_locked = (
        _locked_value(
            [
                scaffold_locked_target.get("exact_future_acceptance_result_path"),
                validator_locked_target.get("exact_future_acceptance_result_path"),
                example_bundle_locked_target.get("exact_future_acceptance_result_path"),
                execution_gate_locked_target.get("exact_future_acceptance_result_path"),
                execution_staging.get("exact_future_output_path"),
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

    review_only_contract_retained = _review_only_contract_retained(
        scaffold_meta,
        validator_meta,
        example_bundle_meta,
        execution_gate_meta,
        execution_staging_meta,
    )

    acceptance_execution_authorized = any(
        bool(value)
        for value in [
            scaffold_status.get("acceptance_execution_authorized", False),
            validator_status.get("acceptance_execution_authorized", False),
            example_bundle_status.get("acceptance_execution_authorized", False),
            execution_gate_status.get("acceptance_execution_authorized", False),
        ]
    )
    runtime_enablement_allowed = any(
        bool(value)
        for value in [
            scaffold_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
            example_bundle_status.get("runtime_enablement_allowed", False),
            execution_gate_status.get("runtime_enablement_allowed", False),
            execution_staging_status.get("runtime_enablement_allowed", False),
        ]
    )
    acceptance_executed = any(
        bool(value)
        for value in [
            scaffold_status.get("acceptance_executed", False),
            validator_status.get("acceptance_executed", False),
            example_bundle_status.get("acceptance_executed", False),
            execution_gate_status.get("acceptance_executed", False),
            execution_staging_status.get("acceptance_executed", False),
            scaffold_meta.get("acceptance_executed", False),
            validator_meta.get("acceptance_executed", False),
            example_bundle_meta.get("acceptance_executed", False),
            execution_gate_meta.get("acceptance_executed", False),
            execution_staging_meta.get("acceptance_executed", False),
        ]
    )
    actual_human_authorization_review_happened = any(
        bool(value)
        for value in [
            scaffold_status.get("authorization_review_completed", False),
            validator_status.get("authorization_review_completed", False),
            validator_status.get("authorization_review_record_provided", False),
            validator_status.get("authorization_review_record_validated", False),
        ]
    )

    example_only_notes = _string_list(example_bundle.get("example_only_notes"))
    synthetic_example_reference_only = _notes_indicate_reference_only(
        example_only_notes
    )

    required_record_fields = _mapping_list(validator.get("required_record_fields"))
    if not required_record_fields:
        required_record_fields = _mapping_list(scaffold.get("required_record_fields"))
    required_review_conclusions = _mapping_list(
        validator.get("required_review_conclusions")
    )
    if not required_review_conclusions:
        required_review_conclusions = _mapping_list(
            scaffold.get("required_review_conclusions")
        )
    required_runtime_patch_statement_ids = _string_list(
        validator.get("required_runtime_patch_statement_ids")
    )
    if not required_runtime_patch_statement_ids:
        required_runtime_patch_statement_ids = _string_list(
            scaffold.get("required_runtime_patch_statement_ids")
        )
    future_validation_checklist = _mapping_list(
        validator.get("future_validation_checklist")
    )
    if not future_validation_checklist:
        future_validation_checklist = _mapping_list(
            scaffold.get("future_validation_checklist")
        )

    missing_prerequisites = _merge_mapping_lists_by_key(
        "gate_id",
        validator.get("missing_prerequisites"),
        scaffold.get("missing_prerequisites"),
        execution_gate.get("missing_prerequisites_before_execution_authorization"),
    )
    still_blocked_gate_ids = _ordered_union(
        validator_report.get("still_blocked_gate_ids")
        if validator_report is not None
        else [],
        scaffold_report.get("still_blocked_gate_ids")
        if scaffold_report is not None
        else [],
        example_bundle_report.get("still_blocked_gate_ids")
        if example_bundle_report is not None
        else [],
        validator_status.get("missing_prerequisite_gate_ids"),
        scaffold_status.get("missing_prerequisite_gate_ids"),
        execution_gate_status.get("missing_prerequisite_gate_ids"),
    )
    if not still_blocked_gate_ids:
        still_blocked_gate_ids = [
            str(entry.get("gate_id"))
            for entry in missing_prerequisites
            if str(entry.get("gate_id")).strip() and not bool(entry.get("current_value"))
        ]

    blocked_prerequisites = [
        dict(entry)
        for entry in missing_prerequisites
        if str(entry.get("gate_id")) in set(still_blocked_gate_ids)
    ]
    blocked_prerequisite_details = {
        str(entry.get("gate_id")): str(entry.get("detail"))
        for entry in blocked_prerequisites
        if str(entry.get("gate_id")).strip()
    }

    authoritative_inputs = [
        _authoritative_input(
            input_id="acceptance_authorization_review_record_scaffold",
            artifact_path=_display_path(project_root, scaffold_resolved),
            source=ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE,
            present=scaffold_present,
            ready=scaffold_ready,
            authoritative_scope="template_for_future_manual_authorization_review_record",
            operator_usage=(
                "Use as the authoritative scaffold for the future human/operator "
                "authorization-review record fields and locked execution target."
            ),
            notes=(
                "Review-only/default-off scaffold only; authorization_review_completed "
                "must remain false here."
            ),
        ),
        _authoritative_input(
            input_id="acceptance_authorization_review_record_validator",
            artifact_path=_display_path(project_root, validator_resolved),
            source=ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
            present=validator_present,
            ready=validator_ready,
            authoritative_scope=(
                "validation_contract_for_future_manual_authorization_review_record"
            ),
            operator_usage=(
                "Use as the authoritative validator contract describing what a future "
                "real human authorization-review record must contain and confirm."
            ),
            notes=(
                "No actual human authorization-review record has been provided or "
                "validated yet."
            ),
        ),
        _authoritative_input(
            input_id="acceptance_authorization_review_record_example_bundle",
            artifact_path=_display_path(project_root, example_bundle_resolved),
            source=ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
            present=example_bundle_present,
            ready=example_bundle_ready,
            authoritative_scope="reference_only_synthetic_example",
            operator_usage=(
                "Use only as a reference/demo for field shape and validator replay; "
                "do not treat it as an actual human review record."
            ),
            notes=REFERENCE_ONLY_NOTICE,
        ),
        _authoritative_input(
            input_id="acceptance_execution_gate",
            artifact_path=_display_path(project_root, execution_gate_resolved),
            source=ACCEPTANCE_EXECUTION_GATE_SOURCE,
            present=execution_gate_present,
            ready=execution_gate_ready,
            authoritative_scope="locked_execution_target_and_blocked_prerequisites",
            operator_usage=(
                "Use as authority for the locked prod_4x4_normal target plus the "
                "currently blocked prerequisite gate ids carried into future review."
            ),
            notes=(
                "This gate remains review-only and does not authorize execution."
            ),
        ),
        _authoritative_input(
            input_id="acceptance_execution_staging",
            artifact_path=_display_path(project_root, execution_staging_resolved),
            source=ACCEPTANCE_EXECUTION_STAGING_SOURCE,
            present=execution_staging_present,
            ready=execution_staging_ready,
            authoritative_scope="locked_command_and_result_path_staging_reference",
            operator_usage=(
                "Use as the authoritative staging reference for the exact future "
                "acceptance command and exact future result path."
            ),
            notes=(
                "Staging only; does not execute acceptance and does not imply enablement."
            ),
        ),
    ]

    acceptance_authorization_operator_handoff_bundle_ready = all(
        [
            scaffold_present,
            validator_present,
            example_bundle_present,
            execution_gate_present,
            execution_staging_present,
            scaffold_ready,
            validator_ready,
            example_bundle_ready,
            execution_gate_ready,
            execution_staging_ready,
            review_only_contract_retained,
            production_profile_locked_prod_4x4_normal,
            bool(exact_future_acceptance_command_locked),
            bool(exact_future_acceptance_result_path_locked),
            bool(command_matches_result_path),
            bool(synthetic_example_reference_only),
            not acceptance_execution_authorized,
            not runtime_enablement_allowed,
            not acceptance_executed,
            not actual_human_authorization_review_happened,
        ]
    )
    future_manual_authorization_review_prerequisites_met = bool(
        acceptance_authorization_operator_handoff_bundle_ready
        and not still_blocked_gate_ids
    )

    if not acceptance_authorization_operator_handoff_bundle_ready:
        recommended_next_step = (
            "repair_acceptance_authorization_operator_handoff_bundle_inputs"
        )
        handoff_recommendation = (
            "Operator handoff bundle is blocked because one or more upstream "
            "acceptance-authorization artifacts are missing, not ready, or no longer "
            "contract-compatible with the locked prod_4x4_normal review-only/default-off "
            "path. Repair those upstream inputs before using this future manual "
            "authorization-review handoff."
        )
    elif still_blocked_gate_ids:
        recommended_next_step = (
            "keep_review_only_handoff_bundle_and_resolve_blocked_prerequisites_before_any_manual_authorization_review"
        )
        handoff_recommendation = (
            "Operator handoff bundle is ready as review-only/spec-only/default-off "
            "scaffolding for a future manual acceptance-authorization review on "
            f"anchor119. Keep acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, and acceptance_executed=false. "
            "The locked prod_4x4_normal target/command/result path remain "
            "authoritative, the validator artifact remains the contract for any future "
            "human review record, and the synthetic example remains reference only. "
            "Prerequisite gate(s) still block any future authorization decision: "
            f"{', '.join(still_blocked_gate_ids)}."
        )
    else:
        recommended_next_step = (
            "have_human_run_separate_manual_acceptance_authorization_review_without_enabling_runtime"
        )
        handoff_recommendation = (
            "Operator handoff bundle is ready and the currently known prerequisite "
            "gate ids are clear, but this still remains review-only/default-off "
            "scaffolding. A future human/operator must run a separate manual "
            "authorization review using the locked prod_4x4_normal target, validator "
            "contract, and reference-only synthetic example without enabling runtime."
        )

    ordered_steps = _build_ordered_steps(
        exact_future_acceptance_command=exact_future_acceptance_command,
        exact_future_acceptance_result_path=exact_future_acceptance_result_path,
        still_blocked_gate_ids=still_blocked_gate_ids,
        validator_artifact_path=_display_path(project_root, validator_resolved),
        example_bundle_artifact_path=_display_path(project_root, example_bundle_resolved),
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
            "acceptance_authorization_review_record_validator_present",
            "pass" if validator_present else "fail",
            "acceptance authorization review record validator loaded"
            if validator_present
            else _presence_detail(
                validator_report,
                validator_error,
                validator_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
                project_root,
                validator_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_record_example_bundle_present",
            "pass" if example_bundle_present else "fail",
            "acceptance authorization review record example bundle loaded"
            if example_bundle_present
            else _presence_detail(
                example_bundle_report,
                example_bundle_error,
                example_bundle_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
                project_root,
                example_bundle_resolved,
            ),
        ),
        _check(
            "acceptance_execution_gate_present",
            "pass" if execution_gate_present else "fail",
            "acceptance execution gate loaded"
            if execution_gate_present
            else _presence_detail(
                execution_gate_report,
                execution_gate_error,
                execution_gate_meta,
                ACCEPTANCE_EXECUTION_GATE_SOURCE,
                project_root,
                execution_gate_resolved,
            ),
        ),
        _check(
            "acceptance_execution_staging_present",
            "pass" if execution_staging_present else "fail",
            "acceptance execution staging loaded"
            if execution_staging_present
            else _presence_detail(
                execution_staging_report,
                execution_staging_error,
                execution_staging_meta,
                ACCEPTANCE_EXECUTION_STAGING_SOURCE,
                project_root,
                execution_staging_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_record_scaffold_ready",
            "pass" if scaffold_ready else "fail",
            str(
                scaffold_status.get(
                    "acceptance_authorization_review_record_scaffold_ready"
                )
            ),
        ),
        _check(
            "acceptance_authorization_review_record_validator_ready",
            "pass" if validator_ready else "fail",
            str(
                validator_status.get(
                    "acceptance_authorization_review_record_validator_ready"
                )
            ),
        ),
        _check(
            "acceptance_authorization_review_record_example_bundle_ready",
            "pass" if example_bundle_ready else "fail",
            str(
                example_bundle_status.get(
                    "acceptance_authorization_review_record_example_bundle_ready"
                )
            ),
        ),
        _check(
            "acceptance_execution_gate_ready",
            "pass" if execution_gate_ready else "fail",
            str(execution_gate_status.get("acceptance_execution_gate_ready")),
        ),
        _check(
            "acceptance_execution_staging_ready",
            "pass" if execution_staging_ready else "fail",
            str(execution_staging_status.get("acceptance_execution_staging_ready")),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "all upstream artifacts remain spec-only/default-off/no-solve"
            if review_only_contract_retained
            else "expected spec-only/default-off/no-solve metadata upstream",
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
            "synthetic_example_reference_only",
            "pass" if synthetic_example_reference_only else "fail",
            REFERENCE_ONLY_NOTICE
            if synthetic_example_reference_only
            else "example bundle must remain explicitly reference-only",
        ),
        _check(
            "actual_human_authorization_review_not_performed",
            "pass" if not actual_human_authorization_review_happened else "fail",
            (
                "scaffold_authorization_review_completed="
                f"{bool(scaffold_status.get('authorization_review_completed', False))} "
                "validator_record_provided="
                f"{bool(validator_status.get('authorization_review_record_provided', False))} "
                "validator_record_validated="
                f"{bool(validator_status.get('authorization_review_record_validated', False))}"
            ),
        ),
        _check(
            "acceptance_execution_authorized_still_false",
            "pass" if not acceptance_execution_authorized else "fail",
            f"acceptance_execution_authorized={acceptance_execution_authorized}",
        ),
        _check(
            "runtime_enablement_allowed_still_false",
            "pass" if not runtime_enablement_allowed else "fail",
            f"runtime_enablement_allowed={runtime_enablement_allowed}",
        ),
        _check(
            "acceptance_executed_still_false",
            "pass" if not acceptance_executed else "fail",
            f"acceptance_executed={acceptance_executed}",
        ),
    ]

    gates = [
        _gate(
            "acceptance_authorization_review_record_scaffold_ready",
            scaffold_ready,
            True,
            "The acceptance-authorization review record scaffold must already be ready and remain the authoritative future-record template.",
        ),
        _gate(
            "acceptance_authorization_review_record_validator_ready",
            validator_ready,
            True,
            "The acceptance-authorization review record validator must already be ready and remain the authoritative future-record contract.",
        ),
        _gate(
            "acceptance_authorization_review_record_example_bundle_ready",
            example_bundle_ready,
            True,
            "The synthetic example bundle must already be ready and remain reference-only.",
        ),
        _gate(
            "acceptance_execution_gate_ready",
            execution_gate_ready,
            True,
            "The acceptance execution gate must already be ready and remain authoritative for blocked prerequisite gate ids.",
        ),
        _gate(
            "acceptance_execution_staging_ready",
            execution_staging_ready,
            True,
            "The acceptance execution staging artifact must already be ready and keep the locked command/result-path reference intact.",
        ),
        _gate(
            "production_profile_locked_prod_4x4_normal",
            production_profile_locked_prod_4x4_normal,
            True,
            "The future manual review path must stay pinned to the locked prod_4x4_normal production profile.",
        ),
        _gate(
            "exact_future_acceptance_command_locked",
            bool(exact_future_acceptance_command_locked),
            True,
            "The exact future acceptance command must remain locked across scaffold, validator, example bundle, execution gate, and execution staging.",
        ),
        _gate(
            "exact_future_acceptance_result_path_locked",
            bool(exact_future_acceptance_result_path_locked),
            True,
            "The exact future acceptance result path must remain locked across scaffold, validator, example bundle, execution gate, and execution staging.",
        ),
        _gate(
            "command_matches_result_path",
            bool(command_matches_result_path),
            True,
            "The locked acceptance command must still point at the exact locked acceptance result path.",
        ),
        _gate(
            "synthetic_example_reference_only",
            bool(synthetic_example_reference_only),
            True,
            "The synthetic example bundle must stay reference-only and must not be treated as an actual human authorization review record.",
        ),
        _gate(
            "actual_human_authorization_review_not_performed",
            not actual_human_authorization_review_happened,
            True,
            "This handoff remains pre-review only; it must not imply that any actual human authorization review has already happened.",
        ),
        _gate(
            "acceptance_execution_authorized_still_false",
            not acceptance_execution_authorized,
            True,
            "acceptance_execution_authorized must remain false throughout this bundle.",
        ),
        _gate(
            "runtime_enablement_allowed_still_false",
            not runtime_enablement_allowed,
            True,
            "runtime_enablement_allowed must remain false throughout this bundle.",
        ),
        _gate(
            "acceptance_executed_still_false",
            not acceptance_executed,
            True,
            "acceptance_executed must remain false throughout this bundle.",
        ),
    ]
    for gate_id in still_blocked_gate_ids:
        gates.append(
            _gate(
                gate_id,
                False,
                True,
                blocked_prerequisite_details.get(gate_id)
                or (
                    "This prerequisite gate remains blocked and must stay visible to "
                    "a future manual authorization review."
                ),
            )
        )

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_operator_handoff_bundle_"
                "review_only_operator_facing_not_manual_authorization_review"
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
            "acceptance_authorization_review_record_validator": _display_path(
                project_root, validator_resolved
            ),
            "acceptance_authorization_review_record_example_bundle": _display_path(
                project_root, example_bundle_resolved
            ),
            "acceptance_execution_gate": _display_path(
                project_root, execution_gate_resolved
            ),
            "acceptance_execution_staging": _display_path(
                project_root, execution_staging_resolved
            ),
            "exact_future_acceptance_command": exact_future_acceptance_command,
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_authorization_operator_handoff_bundle_ready": bool(
                acceptance_authorization_operator_handoff_bundle_ready
            ),
            "future_manual_authorization_review_prerequisites_met": bool(
                future_manual_authorization_review_prerequisites_met
            ),
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": list(still_blocked_gate_ids),
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_authorization_operator_handoff_bundle": {
            "operator_target": {
                "role": "future_manual_acceptance_authorization_review_operator",
                "scope": _operator_scope(candidate),
                "review_phase": "manual_acceptance_authorization_review",
                "detail": (
                    "Read-only/operator-facing handoff for a future manual "
                    "acceptance-authorization review on anchor119. This bundle does "
                    "not authorize execution and does not imply that any actual human "
                    "authorization review has already happened."
                ),
            },
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "authoritative_inputs": authoritative_inputs,
            "locked_execution_target": {
                "production_profile_id": production_profile_id,
                "production_profile_locked": bool(
                    production_profile_locked_prod_4x4_normal
                ),
                "default_production_runner": default_production_runner,
                "default_production_runner_locked": bool(default_production_runner_locked),
                "exact_future_acceptance_command": exact_future_acceptance_command,
                "exact_future_acceptance_command_locked": bool(
                    exact_future_acceptance_command_locked
                ),
                "exact_future_acceptance_result_path": (
                    exact_future_acceptance_result_path
                ),
                "exact_future_acceptance_result_path_locked": bool(
                    exact_future_acceptance_result_path_locked
                ),
                "command_matches_result_path": bool(command_matches_result_path),
            },
            "future_real_human_review_record_requirements": {
                "validator_target": validator.get("validator_target"),
                "target_record_type": validator.get("target_record_type")
                or scaffold_payload.get("record_type"),
                "required_record_fields": list(required_record_fields),
                "required_review_conclusions": list(required_review_conclusions),
                "required_runtime_patch_statement_ids": list(
                    required_runtime_patch_statement_ids
                ),
                "future_validation_checklist": list(future_validation_checklist),
                "validator_notice": validator.get("validator_notice"),
            },
            "blocked_prerequisites": blocked_prerequisites,
            "ordered_steps": ordered_steps,
            "validator_script_or_artifact_reference": {
                "validator_artifact_path": _display_path(project_root, validator_resolved),
                "validator_source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
                "validator_builder_script": VALIDATOR_BUILDER_SCRIPT,
                "validator_target": validator.get("validator_target"),
                "target_record_type": validator.get("target_record_type")
                or scaffold_payload.get("record_type"),
                "validator_notice": validator.get("validator_notice"),
                "use_when": (
                    "Use this validator contract when a future real human/operator "
                    "authorization-review record exists and needs contract validation."
                ),
            },
            "example_bundle_reference": {
                "example_bundle_artifact_path": _display_path(
                    project_root, example_bundle_resolved
                ),
                "example_bundle_source": (
                    ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE
                ),
                "example_bundle_builder_script": EXAMPLE_BUNDLE_BUILDER_SCRIPT,
                "synthetic_example_reference_only": bool(
                    synthetic_example_reference_only
                ),
                "synthetic_example_payload_validated": bool(
                    example_bundle_status.get("synthetic_example_payload_validated", False)
                ),
                "reference_notice": REFERENCE_ONLY_NOTICE,
                "use_when": (
                    "Use only as a reference/demo for record shape and validator replay; "
                    "never as proof that human authorization review has occurred."
                ),
            },
            "preserved_state_assertions": {
                "acceptance_execution_authorized": False,
                "runtime_enablement_allowed": False,
                "acceptance_executed": False,
                "actual_human_authorization_review_happened": False,
            },
            "explicit_non_goals": list(EXPLICIT_NON_GOALS),
            "disallowed_actions": list(DISALLOWED_ACTIONS),
            "reference_only_notice": REFERENCE_ONLY_NOTICE,
            "handoff_recommendation": handoff_recommendation,
        },
        "still_blocked_gate_ids": list(still_blocked_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("acceptance_authorization_operator_handoff_bundle"))
    operator_target = _mapping(bundle.get("operator_target"))
    locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    requirements = _mapping(bundle.get("future_real_human_review_record_requirements"))
    validator_reference = _mapping(bundle.get("validator_script_or_artifact_reference"))
    example_reference = _mapping(bundle.get("example_bundle_reference"))
    state_assertions = _mapping(bundle.get("preserved_state_assertions"))
    blocked_prerequisites = _mapping_list(bundle.get("blocked_prerequisites"))

    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Operator Handoff Bundle",
        "",
        f"- Operator handoff bundle ready: `{status.get('acceptance_authorization_operator_handoff_bundle_ready')}`",
        f"- Future manual authorization review prerequisites met: `{status.get('future_manual_authorization_review_prerequisites_met')}`",
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Actual human authorization review happened: `{status.get('actual_human_authorization_review_happened')}`",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Operator Target",
        "",
        f"- Role: `{operator_target.get('role')}`",
        f"- Scope: `{operator_target.get('scope')}`",
        f"- Review phase: `{operator_target.get('review_phase')}`",
        f"- Detail: {operator_target.get('detail')}",
        "",
        "## Authoritative Inputs",
        "",
        "| Input | Present | Ready | Scope | Artifact path | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in _mapping_list(bundle.get("authoritative_inputs")):
        lines.append(
            f"| {_markdown_cell(entry.get('input_id'))} | "
            f"{_markdown_cell(entry.get('present'))} | "
            f"{_markdown_cell(entry.get('ready'))} | "
            f"{_markdown_cell(entry.get('authoritative_scope'))} | "
            f"{_markdown_cell(entry.get('artifact_path'))} | "
            f"{_markdown_cell(entry.get('notes'))} |"
        )

    lines.extend(
        [
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
            "## Future Real Human Review Record Requirements",
            "",
            f"- Validator target: `{requirements.get('validator_target')}`",
            f"- Target record type: `{requirements.get('target_record_type')}`",
            f"- Validator notice: {requirements.get('validator_notice')}",
            "",
            "### Required Record Fields",
            "",
            "| Field | Required | Template value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in _mapping_list(requirements.get("required_record_fields")):
        lines.append(
            f"| {_markdown_cell(entry.get('field'))} | "
            f"{_markdown_cell(entry.get('required'))} | "
            f"{_markdown_cell(_render_value(entry.get('template_value')))} | "
            f"{_markdown_cell(entry.get('detail'))} |"
        )

    lines.extend(
        [
            "",
            "### Required Review Conclusions",
            "",
        ]
    )
    for entry in _mapping_list(requirements.get("required_review_conclusions")):
        lines.append(
            f"- `{entry.get('conclusion_id')}`: {entry.get('detail')}"
        )

    lines.extend(
        [
            "",
            "### Required Runtime Patch Statement Ids",
            "",
            f"- `{', '.join(_string_list(requirements.get('required_runtime_patch_statement_ids'))) or '(none)'}`",
            "",
            "### Future Validation Checklist",
            "",
        ]
    )
    for entry in _mapping_list(requirements.get("future_validation_checklist")):
        lines.append(f"- `{entry.get('checklist_id')}`: {entry.get('detail')}")

    lines.extend(
        [
            "",
            "## Ordered Handoff Steps",
            "",
        ]
    )
    for entry in _mapping_list(bundle.get("ordered_steps")):
        blocked = ", ".join(_string_list(entry.get("blocked_by_gate_ids"))) or "(none)"
        lines.append(
            f"- `{entry.get('step_id')}`: {entry.get('detail')} "
            f"(blocked_by_gate_ids=`{blocked}`)"
        )

    lines.extend(
        [
            "",
            "## Validator Reference",
            "",
            f"- Validator artifact path: `{validator_reference.get('validator_artifact_path')}`",
            f"- Validator builder script: `{validator_reference.get('validator_builder_script')}`",
            f"- Validator target: `{validator_reference.get('validator_target')}`",
            f"- Target record type: `{validator_reference.get('target_record_type')}`",
            f"- Validator notice: {validator_reference.get('validator_notice')}",
            f"- Use when: {validator_reference.get('use_when')}",
            "",
            "## Example Bundle Reference",
            "",
            f"- Example bundle artifact path: `{example_reference.get('example_bundle_artifact_path')}`",
            f"- Example bundle builder script: `{example_reference.get('example_bundle_builder_script')}`",
            f"- Synthetic example reference only: `{example_reference.get('synthetic_example_reference_only')}`",
            f"- Synthetic example payload validated: `{example_reference.get('synthetic_example_payload_validated')}`",
            f"- Reference notice: {example_reference.get('reference_notice')}",
            f"- Use when: {example_reference.get('use_when')}",
            "",
            "## Preserved State Assertions",
            "",
            "| Assertion | Locked value |",
            "| --- | --- |",
        ]
    )
    for key, value in state_assertions.items():
        lines.append(f"| {_markdown_cell(key)} | {_markdown_cell(value)} |")

    lines.extend(
        [
            "",
            "## Blocked Prerequisites",
            "",
        ]
    )
    if blocked_prerequisites:
        for entry in blocked_prerequisites:
            lines.append(
                f"- `{entry.get('gate_id')}`: {entry.get('detail')}"
            )
    else:
        lines.append("- No currently blocked prerequisite gate ids were reported.")

    lines.extend(
        [
            "",
            "## Explicit Non-Goals",
            "",
        ]
    )
    for entry in _string_list(bundle.get("explicit_non_goals")):
        lines.append(f"- {entry}")

    lines.extend(
        [
            "",
            "## Disallowed Actions",
            "",
        ]
    )
    for entry in _string_list(bundle.get("disallowed_actions")):
        lines.append(f"- {entry}")

    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Satisfied | Blocking | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in _mapping_list(report.get("gates")):
        lines.append(
            f"| {_markdown_cell(entry.get('gate_id'))} | "
            f"{_markdown_cell(entry.get('satisfied'))} | "
            f"{_markdown_cell(entry.get('blocking'))} | "
            f"{_markdown_cell(entry.get('detail'))} |"
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
    for entry in _mapping_list(report.get("checks")):
        lines.append(
            f"| {_markdown_cell(entry.get('check_id'))} | "
            f"{_markdown_cell(entry.get('status'))} | "
            f"{_markdown_cell(entry.get('detail'))} |"
        )

    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("acceptance_authorization_operator_handoff_bundle"))
    locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization operator handoff bundle",
            "acceptance_authorization_operator_handoff_bundle_ready="
            + str(
                status.get(
                    "acceptance_authorization_operator_handoff_bundle_ready", False
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
            "acceptance_executed="
            + str(status.get("acceptance_executed", False)),
            "actual_human_authorization_review_happened="
            + str(status.get("actual_human_authorization_review_happened", False)),
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            "production_profile_id="
            + str(locked_execution_target.get("production_profile_id")),
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path")),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = (
        "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle"
    ),
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _authoritative_input(
    *,
    input_id: str,
    artifact_path: str,
    source: str,
    present: bool,
    ready: bool,
    authoritative_scope: str,
    operator_usage: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "input_id": input_id,
        "artifact_path": artifact_path,
        "source": source,
        "present": bool(present),
        "ready": bool(ready),
        "authoritative_scope": authoritative_scope,
        "operator_usage": operator_usage,
        "notes": notes,
    }


def _build_ordered_steps(
    *,
    exact_future_acceptance_command: str,
    exact_future_acceptance_result_path: str,
    still_blocked_gate_ids: list[str],
    validator_artifact_path: str,
    example_bundle_artifact_path: str,
) -> list[Dict[str, Any]]:
    blocked = list(still_blocked_gate_ids)
    return [
        {
            "step_id": "read_authoritative_artifacts",
            "order": 1,
            "detail": (
                "Read the scaffold, validator, example bundle, acceptance execution "
                "gate, and acceptance execution staging artifacts listed in this "
                "bundle. Treat them as the authoritative inputs for the future manual "
                "authorization-review path."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "confirm_locked_prod_4x4_target",
            "order": 2,
            "detail": (
                "Confirm that the future execution target remains locked to "
                f"prod_4x4_normal, with exact command `{exact_future_acceptance_command}` "
                f"and exact result path `{exact_future_acceptance_result_path}` "
                "unchanged."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "use_validator_contract_for_future_real_record",
            "order": 3,
            "detail": (
                "Use the validator artifact at "
                f"`{validator_artifact_path}` as the contract for what a future real "
                "human authorization-review record must contain and confirm."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "use_synthetic_example_as_reference_only",
            "order": 4,
            "detail": (
                "Use the synthetic example bundle at "
                f"`{example_bundle_artifact_path}` only as a reference/demo. Do not "
                "treat it as evidence that any human authorization review has "
                "already happened."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "preserve_default_off_state",
            "order": 5,
            "detail": (
                "Keep acceptance_execution_authorized=false, "
                "runtime_enablement_allowed=false, and acceptance_executed=false "
                "throughout this handoff and any future manual authorization review."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "stop_if_prerequisites_still_blocked",
            "order": 6,
            "detail": (
                "If any still_blocked_gate_ids remain, stop and carry them forward into "
                "the future manual authorization-review record instead of authorizing "
                "or running anything."
            ),
            "blocked_by_gate_ids": blocked,
        },
    ]


def _notes_indicate_reference_only(notes: list[str]) -> bool:
    if not notes:
        return False
    lowered = [note.lower() for note in notes]
    mentions_synthetic = any("synthetic" in note for note in lowered)
    mentions_reference_only = any(
        "reference only" in note
        or "not an actual human authorization review record" in note
        for note in lowered
    )
    return bool(mentions_synthetic and mentions_reference_only)


def _operator_scope(candidate: Mapping[str, Any]) -> str:
    key = candidate.get("key")
    anchor_idx = candidate.get("anchor_idx")
    formulation_profile = candidate.get("formulation_profile")
    return (
        f"candidate={key}, anchor_idx={anchor_idx}, "
        f"formulation_profile={formulation_profile}"
    )


def _presence_detail(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
    metadata: Mapping[str, Any],
    expected_source: str,
    project_root: Path,
    path: Path,
) -> str:
    if error:
        return error
    if report is None:
        return f"missing:{_display_path(project_root, path)}"
    actual_source = metadata.get("source")
    if actual_source != expected_source:
        return f"unexpected_source:{actual_source}"
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
        "gate_id": gate_id,
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": detail,
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


def _merge_mapping_lists_by_key(key: str, *values: Any) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        for entry in _mapping_list(value):
            entry_key = str(entry.get(key, "")).strip()
            if not entry_key or entry_key in seen:
                continue
            merged.append(dict(entry))
            seen.add(entry_key)
    return merged


def _ordered_union(*values: Any) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        for entry in _string_list(value):
            if entry in seen:
                continue
            ordered.append(entry)
            seen.add(entry)
    return ordered


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing:{path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{path}:{exc.msg}"
    if not isinstance(payload, dict):
        return None, f"invalid_payload_type:{path}"
    return payload, None


def _resolve_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path.resolve())


def _extract_suite_output_path(command: str) -> Optional[str]:
    if not str(command).strip():
        return None
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return None
    for index, part in enumerate(parts):
        if part == "--suite-output" and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith("--suite-output="):
            return part.split("=", 1)[1]
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


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_cell(value: Any) -> str:
    return _render_value(value).replace("|", "\\|").replace("\n", "<br>")

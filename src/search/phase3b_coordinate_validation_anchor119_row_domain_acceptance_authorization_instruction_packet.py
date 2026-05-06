from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_operator_handoff_bundle_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_validator_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_example_bundle_v1"
)
ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_instruction_packet_v1"
)

LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
VALIDATOR_BUILDER_SCRIPT = (
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_validator.py"
)
EXAMPLE_BUNDLE_BUILDER_SCRIPT = (
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_example_bundle.py"
)

DEFAULT_ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.json"
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

REFERENCE_ONLY_NOTICE = (
    "Synthetic example is reference only; it is not an actual human authorization "
    "review record and does not authorize execution."
)
LOCAL_FORBIDDEN_CLAIMS_OR_ACTIONS = [
    "Do not authorize execution from this packet.",
    "Do not enable runtime from this packet.",
    "Do not execute acceptance from this packet.",
    "Do not treat the validator artifact as a validated human review record.",
    "Do not treat the synthetic example bundle as proof that any human authorization review has happened.",
    "Do not claim candidate elimination, proof promotion, or solver work from this packet.",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet(
    project_root: Path,
    *,
    acceptance_authorization_operator_handoff_bundle_path: Optional[Path] = None,
    acceptance_authorization_review_record_validator_path: Optional[Path] = None,
    acceptance_authorization_review_record_example_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    handoff_resolved = _resolve_path(
        project_root,
        acceptance_authorization_operator_handoff_bundle_path
        if acceptance_authorization_operator_handoff_bundle_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH,
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

    handoff_report, handoff_error = _load_json_mapping(handoff_resolved)
    validator_report, validator_error = _load_json_mapping(validator_resolved)
    example_bundle_report, example_bundle_error = _load_json_mapping(
        example_bundle_resolved
    )

    handoff_meta = (
        _mapping(handoff_report.get("metadata")) if handoff_report is not None else {}
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

    handoff_status = (
        _mapping(handoff_report.get("status")) if handoff_report is not None else {}
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

    handoff_bundle = (
        _mapping(handoff_report.get("acceptance_authorization_operator_handoff_bundle"))
        if handoff_report is not None
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

    handoff_requirements = _mapping(
        handoff_bundle.get("future_real_human_review_record_requirements")
    )
    handoff_locked_target = _mapping(handoff_bundle.get("locked_execution_target"))
    validator_locked_target = _mapping(validator.get("locked_execution_target"))
    example_locked_target = _mapping(example_bundle.get("locked_execution_target"))

    candidate = _first_mapping(
        handoff_report.get("candidate") if handoff_report is not None else None,
        validator_report.get("candidate") if validator_report is not None else None,
        example_bundle_report.get("candidate")
        if example_bundle_report is not None
        else None,
    )

    handoff_present = bool(
        handoff_report is not None
        and handoff_error is None
        and handoff_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE
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

    handoff_ready = bool(
        handoff_status.get("acceptance_authorization_operator_handoff_bundle_ready", False)
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

    production_profile_id, production_profile_locked = _locked_value(
        [
            handoff_locked_target.get("production_profile_id"),
            validator_locked_target.get("production_profile_id"),
            example_locked_target.get("production_profile_id"),
        ]
    )
    production_profile_locked_prod_4x4_normal = bool(
        production_profile_locked and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )

    default_production_runner, default_production_runner_locked = _locked_value(
        [
            handoff_locked_target.get("default_production_runner"),
            validator_locked_target.get("default_production_runner"),
            example_locked_target.get("default_production_runner"),
        ],
        normalize=_normalize_path_text,
    )
    exact_future_acceptance_command, exact_future_acceptance_command_locked = (
        _locked_value(
            [
                handoff_locked_target.get("exact_future_acceptance_command"),
                validator_locked_target.get("exact_future_acceptance_command"),
                example_locked_target.get("exact_future_acceptance_command"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_locked = (
        _locked_value(
            [
                handoff_locked_target.get("exact_future_acceptance_result_path"),
                validator_locked_target.get("exact_future_acceptance_result_path"),
                example_locked_target.get("exact_future_acceptance_result_path"),
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

    validator_target, validator_target_locked = _locked_value(
        [
            handoff_requirements.get("validator_target"),
            validator.get("validator_target"),
        ]
    )
    target_record_type, target_record_type_locked = _locked_value(
        [
            handoff_requirements.get("target_record_type"),
            validator.get("target_record_type"),
            example_bundle.get("target_record_type"),
        ]
    )

    required_record_fields = _mapping_list(validator.get("required_record_fields"))
    if not required_record_fields:
        required_record_fields = _mapping_list(
            handoff_requirements.get("required_record_fields")
        )
    required_review_conclusions = _mapping_list(
        validator.get("required_review_conclusions")
    )
    if not required_review_conclusions:
        required_review_conclusions = _mapping_list(
            handoff_requirements.get("required_review_conclusions")
        )
    required_runtime_patch_statement_ids = _string_list(
        validator.get("required_runtime_patch_statement_ids")
    )
    if not required_runtime_patch_statement_ids:
        required_runtime_patch_statement_ids = _string_list(
            handoff_requirements.get("required_runtime_patch_statement_ids")
        )
    future_validation_checklist = _mapping_list(
        validator.get("future_validation_checklist")
    )
    if not future_validation_checklist:
        future_validation_checklist = _mapping_list(
            handoff_requirements.get("future_validation_checklist")
        )
    future_review_record_requirements_present = bool(
        required_record_fields
        and required_review_conclusions
        and required_runtime_patch_statement_ids
        and future_validation_checklist
    )

    handoff_blocked_gate_ids = _string_list(
        handoff_report.get("still_blocked_gate_ids") if handoff_report else []
    )
    validator_blocked_gate_ids = _string_list(
        validator_report.get("still_blocked_gate_ids") if validator_report else []
    )
    example_blocked_gate_ids = _string_list(
        example_bundle_report.get("still_blocked_gate_ids")
        if example_bundle_report
        else []
    )
    still_blocked_gate_ids, still_blocked_gate_ids_locked = _locked_string_lists(
        handoff_blocked_gate_ids,
        validator_blocked_gate_ids,
        example_blocked_gate_ids,
    )

    blocked_prerequisites = _merge_mapping_lists_by_key(
        "gate_id",
        handoff_bundle.get("blocked_prerequisites"),
        validator.get("missing_prerequisites"),
        example_bundle.get("missing_prerequisites"),
    )
    blocked_gate_id_set = set(still_blocked_gate_ids)
    blocked_prerequisites = [
        dict(entry)
        for entry in blocked_prerequisites
        if str(entry.get("gate_id")).strip() in blocked_gate_id_set
    ]
    blocked_prerequisite_details = {
        str(entry.get("gate_id")): str(entry.get("detail"))
        for entry in blocked_prerequisites
        if str(entry.get("gate_id")).strip()
    }

    review_only_contract_retained = _review_only_contract_retained(
        handoff_meta,
        validator_meta,
        example_bundle_meta,
    )
    handoff_preserved_state = bool(
        not handoff_status.get("acceptance_execution_authorized", False)
        and not handoff_status.get("runtime_enablement_allowed", False)
        and not handoff_status.get("acceptance_executed", False)
        and not handoff_status.get("actual_human_authorization_review_happened", False)
    )
    validator_contract_only = _validator_contract_only(validator_status, validator)
    example_reference_only = _example_reference_only(example_bundle_status, example_bundle)

    acceptance_execution_authorized = any(
        bool(value)
        for value in [
            handoff_status.get("acceptance_execution_authorized", False),
            validator_status.get("acceptance_execution_authorized", False),
            example_bundle_status.get("acceptance_execution_authorized", False),
        ]
    )
    runtime_enablement_allowed = any(
        bool(value)
        for value in [
            handoff_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
            example_bundle_status.get("runtime_enablement_allowed", False),
        ]
    )
    acceptance_executed = any(
        bool(value)
        for value in [
            handoff_status.get("acceptance_executed", False),
            validator_status.get("acceptance_executed", False),
            example_bundle_status.get("acceptance_executed", False),
            handoff_meta.get("acceptance_executed", False),
            validator_meta.get("acceptance_executed", False),
            example_bundle_meta.get("acceptance_executed", False),
        ]
    )
    actual_human_authorization_review_happened = any(
        bool(value)
        for value in [
            handoff_status.get("actual_human_authorization_review_happened", False),
            validator_status.get("authorization_review_completed", False),
            validator_status.get("authorization_review_record_provided", False),
            validator_status.get("authorization_review_record_validated", False),
            _mapping(validator.get("actual_record_validation")).get(
                "validated_authorization_review_completed", False
            ),
        ]
    )

    acceptance_authorization_instruction_packet_ready = all(
        [
            handoff_present,
            validator_present,
            example_bundle_present,
            handoff_ready,
            validator_ready,
            example_bundle_ready,
            review_only_contract_retained,
            handoff_preserved_state,
            validator_contract_only,
            example_reference_only,
            future_review_record_requirements_present,
            bool(validator_target_locked),
            bool(target_record_type_locked),
            bool(production_profile_locked_prod_4x4_normal),
            bool(default_production_runner_locked),
            bool(exact_future_acceptance_command_locked),
            bool(exact_future_acceptance_result_path_locked),
            bool(command_matches_result_path),
            bool(still_blocked_gate_ids_locked),
            not acceptance_execution_authorized,
            not runtime_enablement_allowed,
            not acceptance_executed,
            not actual_human_authorization_review_happened,
        ]
    )
    future_manual_acceptance_authorization_review_prerequisites_met = bool(
        acceptance_authorization_instruction_packet_ready and not still_blocked_gate_ids
    )

    if not acceptance_authorization_instruction_packet_ready:
        recommended_next_step = (
            "repair_acceptance_authorization_instruction_packet_inputs"
        )
        handoff_recommendation = (
            "Instruction packet is blocked because the upstream operator handoff bundle, "
            "validator contract, or synthetic example bundle is missing, not ready, or "
            "no longer contract-compatible with the locked review-only/default-off "
            "anchor119 authorization-review path."
        )
    elif still_blocked_gate_ids:
        recommended_next_step = (
            "keep_instruction_packet_review_only_and_wait_for_blocked_prerequisites"
        )
        handoff_recommendation = (
            "Instruction packet is ready as a bounded operator-facing review packet for "
            "a future manual acceptance-authorization review on anchor119. Keep "
            "acceptance_execution_authorized=false, runtime_enablement_allowed=false, "
            "acceptance_executed=false, and actual_human_authorization_review_happened=false. "
            "The locked prod_4x4_normal target/command/result path remain authoritative, "
            "the validator artifact remains the contract for any future human review "
            "record, and the synthetic example remains reference-only. Blocked "
            "prerequisite gate ids still prevent any future authorization decision: "
            f"{', '.join(still_blocked_gate_ids)}."
        )
    else:
        recommended_next_step = (
            "have_human_run_separate_manual_acceptance_authorization_review_without_enabling_runtime"
        )
        handoff_recommendation = (
            "Instruction packet is ready and the currently known prerequisite gate ids "
            "are clear, but this still remains review-only/spec-only/default-off "
            "scaffolding. A future human/operator must run a separate manual "
            "acceptance-authorization review without enabling runtime, authorizing "
            "execution from this packet, or executing acceptance from this packet."
        )

    open_these_first = [
        {
            "order": 1,
            "artifact_id": "acceptance_authorization_operator_handoff_bundle",
            "artifact_path": _display_path(project_root, handoff_resolved),
            "why_read_first": (
                "Primary operator-facing authority for the future manual review path. "
                "Use it first to confirm the locked prod_4x4_normal target and the "
                "currently blocked prerequisite gate ids."
            ),
            "authoritative_for": [
                "locked_execution_target",
                "blocked_prerequisite_gate_ids",
                "preserved_state_assertions",
            ],
        },
        {
            "order": 2,
            "artifact_id": "acceptance_authorization_review_record_validator",
            "artifact_path": _display_path(project_root, validator_resolved),
            "why_read_first": (
                "Contract for what a future real human acceptance-authorization review "
                "record must contain and what it must still keep false."
            ),
            "authoritative_for": [
                "required_record_fields",
                "required_review_conclusions",
                "required_runtime_patch_statement_ids",
                "future_validation_checklist",
            ],
        },
        {
            "order": 3,
            "artifact_id": "acceptance_authorization_review_record_example_bundle",
            "artifact_path": _display_path(project_root, example_bundle_resolved),
            "why_read_first": (
                "Reference-only example for field shape and validator replay. It is "
                "not an actual human review record and must never be treated as "
                "authorization or execution."
            ),
            "authoritative_for": [
                "reference_only_field_shape",
                "synthetic_example_replay",
            ],
        },
    ]

    ordered_instructions = _build_ordered_instructions(
        exact_future_acceptance_command=exact_future_acceptance_command,
        exact_future_acceptance_result_path=exact_future_acceptance_result_path,
        still_blocked_gate_ids=still_blocked_gate_ids,
        validator_artifact_path=_display_path(project_root, validator_resolved),
        example_bundle_artifact_path=_display_path(project_root, example_bundle_resolved),
    )

    verify_before_stopping = [
        {
            "check_id": "locked_prod_4x4_normal_target_unchanged",
            "current_value": bool(
                production_profile_locked_prod_4x4_normal
                and default_production_runner_locked
                and exact_future_acceptance_command_locked
                and exact_future_acceptance_result_path_locked
                and command_matches_result_path
            ),
            "detail": (
                "Verify that the locked prod_4x4_normal runner, exact future command, "
                "and exact future result path remain unchanged."
            ),
        },
        {
            "check_id": "future_review_record_requirements_still_present",
            "current_value": bool(future_review_record_requirements_present),
            "detail": (
                "Verify that the validator still exposes required record fields, "
                "required review conclusions, runtime patch statement ids, and the "
                "future validation checklist."
            ),
        },
        {
            "check_id": "blocked_prerequisites_still_visible",
            "current_value": bool(still_blocked_gate_ids_locked),
            "detail": (
                "Verify that the still-blocked prerequisite gate ids are carried "
                "forward exactly and remain visible to the future human reviewer."
            ),
        },
        {
            "check_id": "preserved_state_assertions_still_false",
            "current_value": bool(
                not acceptance_execution_authorized
                and not runtime_enablement_allowed
                and not acceptance_executed
                and not actual_human_authorization_review_happened
            ),
            "detail": (
                "Verify that acceptance_execution_authorized, "
                "runtime_enablement_allowed, acceptance_executed, and "
                "actual_human_authorization_review_happened all remain false."
            ),
        },
        {
            "check_id": "packet_not_treated_as_authorization_or_execution",
            "current_value": True,
            "detail": (
                "Verify that this packet, the validator contract, and the synthetic "
                "example are still being treated as review-only artifacts rather than "
                "authorization, enablement, or execution."
            ),
        },
    ]

    preserved_state_assertions = {
        "acceptance_execution_authorized": {
            "expected_value": False,
            "current_value": bool(acceptance_execution_authorized),
            "detail": "Must remain false. This packet is not execution authorization.",
        },
        "runtime_enablement_allowed": {
            "expected_value": False,
            "current_value": bool(runtime_enablement_allowed),
            "detail": "Must remain false. This packet never enables runtime.",
        },
        "acceptance_executed": {
            "expected_value": False,
            "current_value": bool(acceptance_executed),
            "detail": "Must remain false. This packet never executes acceptance.",
        },
        "actual_human_authorization_review_happened": {
            "expected_value": False,
            "current_value": bool(actual_human_authorization_review_happened),
            "detail": (
                "Must remain false until a separate real human review record exists "
                "outside this packet."
            ),
        },
    }

    forbidden_claims_or_actions = _ordered_union(
        handoff_bundle.get("explicit_non_goals"),
        handoff_bundle.get("disallowed_actions"),
        LOCAL_FORBIDDEN_CLAIMS_OR_ACTIONS,
    )

    checks = [
        _check(
            "acceptance_authorization_operator_handoff_bundle_present",
            "pass" if handoff_present else "fail",
            "acceptance authorization operator handoff bundle loaded"
            if handoff_present
            else _presence_detail(
                handoff_report,
                handoff_error,
                handoff_meta,
                ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE,
                project_root,
                handoff_resolved,
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
            "acceptance_authorization_operator_handoff_bundle_ready",
            "pass" if handoff_ready else "fail",
            str(
                handoff_status.get(
                    "acceptance_authorization_operator_handoff_bundle_ready"
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
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "all upstream artifacts remain review-only/default-off/spec-only/no-solve"
            if review_only_contract_retained
            else "expected review-only/default-off/spec-only/no-solve metadata upstream",
        ),
        _check(
            "handoff_preserved_state",
            "pass" if handoff_preserved_state else "fail",
            (
                "acceptance_execution_authorized="
                f"{bool(handoff_status.get('acceptance_execution_authorized', False))} "
                "runtime_enablement_allowed="
                f"{bool(handoff_status.get('runtime_enablement_allowed', False))} "
                "acceptance_executed="
                f"{bool(handoff_status.get('acceptance_executed', False))} "
                "actual_human_authorization_review_happened="
                f"{bool(handoff_status.get('actual_human_authorization_review_happened', False))}"
            ),
        ),
        _check(
            "validator_contract_only",
            "pass" if validator_contract_only else "fail",
            str(validator.get("validator_notice") or "validator contract-only check failed"),
        ),
        _check(
            "example_reference_only",
            "pass" if example_reference_only else "fail",
            "; ".join(_string_list(example_bundle.get("example_only_notes")))
            or REFERENCE_ONLY_NOTICE,
        ),
        _check(
            "future_review_record_requirements_present",
            "pass" if future_review_record_requirements_present else "fail",
            (
                "required_record_fields="
                f"{len(required_record_fields)} required_review_conclusions="
                f"{len(required_review_conclusions)} required_runtime_patch_statement_ids="
                f"{len(required_runtime_patch_statement_ids)} future_validation_checklist="
                f"{len(future_validation_checklist)}"
            ),
        ),
        _check(
            "validator_target_locked",
            "pass" if validator_target_locked else "fail",
            validator_target or "missing",
        ),
        _check(
            "target_record_type_locked",
            "pass" if target_record_type_locked else "fail",
            target_record_type or "missing",
        ),
        _check(
            "production_profile_locked_prod_4x4_normal",
            "pass" if production_profile_locked_prod_4x4_normal else "fail",
            production_profile_id or "missing",
        ),
        _check(
            "default_production_runner_locked",
            "pass" if default_production_runner_locked else "fail",
            default_production_runner or "missing",
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
            "still_blocked_gate_ids_locked",
            "pass" if still_blocked_gate_ids_locked else "fail",
            ",".join(still_blocked_gate_ids),
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
        _check(
            "actual_human_authorization_review_not_performed",
            "pass" if not actual_human_authorization_review_happened else "fail",
            (
                "actual_human_authorization_review_happened="
                f"{actual_human_authorization_review_happened}"
            ),
        ),
    ]

    gates = [
        _gate(
            "acceptance_authorization_operator_handoff_bundle_ready",
            handoff_ready,
            True,
            "The upstream operator handoff bundle must already be ready and contract-compatible.",
        ),
        _gate(
            "acceptance_authorization_review_record_validator_ready",
            validator_ready,
            True,
            "The upstream validator contract must already be ready and remain review-only.",
        ),
        _gate(
            "acceptance_authorization_review_record_example_bundle_ready",
            example_bundle_ready,
            True,
            "The upstream synthetic example bundle must already be ready and remain reference-only.",
        ),
        _gate(
            "review_only_contract_retained",
            review_only_contract_retained,
            True,
            "All upstream artifacts must remain review-only/spec-only/default-off/no-solve.",
        ),
        _gate(
            "locked_prod_4x4_normal_target_consistent",
            bool(
                production_profile_locked_prod_4x4_normal
                and default_production_runner_locked
                and exact_future_acceptance_command_locked
                and exact_future_acceptance_result_path_locked
                and command_matches_result_path
            ),
            True,
            "The locked prod_4x4_normal runner, exact future command, and exact future result path must remain consistent across handoff, validator, and example artifacts.",
        ),
        _gate(
            "future_review_record_requirements_present",
            future_review_record_requirements_present,
            True,
            "The validator contract must still expose the required fields, conclusions, runtime patch statements, and checklist for a future real human review record.",
        ),
        _gate(
            "blocked_prerequisite_state_locked",
            still_blocked_gate_ids_locked,
            True,
            "The still-blocked prerequisite gate ids must remain aligned across the handoff, validator, and example artifacts.",
        ),
        _gate(
            "packet_remains_pre_review_only",
            not actual_human_authorization_review_happened,
            True,
            "This packet must not imply that any actual human authorization review has already happened.",
        ),
        _gate(
            "acceptance_execution_authorized_still_false",
            not acceptance_execution_authorized,
            True,
            "acceptance_execution_authorized must remain false throughout this packet.",
        ),
        _gate(
            "runtime_enablement_allowed_still_false",
            not runtime_enablement_allowed,
            True,
            "runtime_enablement_allowed must remain false throughout this packet.",
        ),
        _gate(
            "acceptance_executed_still_false",
            not acceptance_executed,
            True,
            "acceptance_executed must remain false throughout this packet.",
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
                    "This prerequisite gate remains blocked and prevents any future "
                    "manual authorization decision from becoming executable."
                ),
            )
        )

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_instruction_packet_"
                "review_only_operator_facing_not_execution_authorization"
            ),
            "spec_only": True,
            "review_only": True,
            "default_off": True,
            "no_solve": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
        "paths": {
            "project_root": str(project_root),
            "acceptance_authorization_operator_handoff_bundle": _display_path(
                project_root, handoff_resolved
            ),
            "acceptance_authorization_review_record_validator": _display_path(
                project_root, validator_resolved
            ),
            "acceptance_authorization_review_record_example_bundle": _display_path(
                project_root, example_bundle_resolved
            ),
            "exact_future_acceptance_command": exact_future_acceptance_command,
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_authorization_instruction_packet_ready": bool(
                acceptance_authorization_instruction_packet_ready
            ),
            "future_manual_acceptance_authorization_review_prerequisites_met": bool(
                future_manual_acceptance_authorization_review_prerequisites_met
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
        "acceptance_authorization_instruction_packet": {
            "packet_target": {
                "role": "future_manual_acceptance_authorization_review_operator",
                "scope": _operator_scope(candidate),
                "review_phase": "manual_acceptance_authorization_review",
                "detail": (
                    "Bounded, review-only, operator-facing instruction packet for a "
                    "future manual acceptance-authorization review on anchor119. "
                    "This packet does not authorize execution, does not enable "
                    "runtime, does not execute acceptance, and does not imply that "
                    "any actual human authorization review has already happened."
                ),
            },
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "no_solve": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "open_these_first": open_these_first,
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
                "authoritative_from_artifact_id": (
                    "acceptance_authorization_operator_handoff_bundle"
                ),
                "cross_checked_against_artifact_ids": [
                    "acceptance_authorization_review_record_validator",
                    "acceptance_authorization_review_record_example_bundle",
                ],
            },
            "future_real_human_review_record_requirements": {
                "validator_target": validator_target,
                "target_record_type": target_record_type,
                "required_record_fields": list(required_record_fields),
                "required_review_conclusions": list(required_review_conclusions),
                "required_runtime_patch_statement_ids": list(
                    required_runtime_patch_statement_ids
                ),
                "future_validation_checklist": list(future_validation_checklist),
                "carry_forward_missing_prerequisite_gate_ids": list(
                    still_blocked_gate_ids
                ),
                "validator_notice": str(validator.get("validator_notice") or ""),
            },
            "ordered_instructions": ordered_instructions,
            "validator_reference": {
                "validator_artifact_path": _display_path(project_root, validator_resolved),
                "validator_source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
                "validator_builder_script": VALIDATOR_BUILDER_SCRIPT,
                "validator_target": validator_target,
                "target_record_type": target_record_type,
                "validator_notice": str(validator.get("validator_notice") or ""),
                "use_when": (
                    "Consult this validator when defining or checking what a future "
                    "real human acceptance-authorization review record must contain."
                ),
            },
            "example_reference": {
                "example_bundle_artifact_path": _display_path(
                    project_root, example_bundle_resolved
                ),
                "example_bundle_source": (
                    ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE
                ),
                "example_bundle_builder_script": EXAMPLE_BUNDLE_BUILDER_SCRIPT,
                "target_record_type": target_record_type,
                "synthetic_example_reference_only": bool(example_reference_only),
                "synthetic_example_payload_validated": bool(
                    example_bundle_status.get("synthetic_example_payload_validated", False)
                ),
                "reference_notice": (
                    "; ".join(_string_list(example_bundle.get("example_only_notes")))
                    or REFERENCE_ONLY_NOTICE
                ),
                "use_when": (
                    "Consult this synthetic example only for field shape and "
                    "validator replay behavior; never treat it as a real human "
                    "authorization review record."
                ),
            },
            "stop_conditions": [
                {
                    "condition_id": "instruction_packet_not_ready",
                    "currently_triggered": not acceptance_authorization_instruction_packet_ready,
                    "detail": (
                        "Stop if this packet is not ready. Repair the upstream handoff, "
                        "validator, or example artifacts first."
                    ),
                },
                {
                    "condition_id": "locked_execution_target_changed",
                    "currently_triggered": not bool(
                        production_profile_locked_prod_4x4_normal
                        and default_production_runner_locked
                        and exact_future_acceptance_command_locked
                        and exact_future_acceptance_result_path_locked
                        and command_matches_result_path
                    ),
                    "detail": (
                        "Stop if the locked prod_4x4_normal runner, exact future "
                        "command, or exact future result path has drifted."
                    ),
                },
                {
                    "condition_id": "still_blocked_prerequisites_present",
                    "currently_triggered": bool(still_blocked_gate_ids),
                    "detail": (
                        "Stop if any still_blocked_gate_ids remain. Carry them "
                        "forward exactly; do not authorize, enable, or run anything."
                    ),
                },
                {
                    "condition_id": "preserved_state_assertion_flipped",
                    "currently_triggered": bool(
                        acceptance_execution_authorized
                        or runtime_enablement_allowed
                        or acceptance_executed
                        or actual_human_authorization_review_happened
                    ),
                    "detail": (
                        "Stop if any preserved-state assertion flips from false to "
                        "true, because that would mean the packet is no longer a "
                        "pre-review, review-only artifact."
                    ),
                },
                {
                    "condition_id": "packet_treated_as_authorization_or_execution",
                    "currently_triggered": False,
                    "detail": (
                        "Stop if anyone tries to use this packet, the validator, or "
                        "the synthetic example as authorization, runtime enablement, "
                        "or acceptance execution."
                    ),
                },
            ],
            "verify_before_stopping": verify_before_stopping,
            "preserved_state_assertions": preserved_state_assertions,
            "forbidden_claims_or_actions": forbidden_claims_or_actions,
            "reference_only_notice": REFERENCE_ONLY_NOTICE,
            "handoff_recommendation": handoff_recommendation,
        },
        "still_blocked_gate_ids": list(still_blocked_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    packet = _mapping(report.get("acceptance_authorization_instruction_packet"))
    locked_execution_target = _mapping(packet.get("locked_execution_target"))
    future_record_requirements = _mapping(
        packet.get("future_real_human_review_record_requirements")
    )
    validator_reference = _mapping(packet.get("validator_reference"))
    example_reference = _mapping(packet.get("example_reference"))

    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Instruction Packet",
        "",
        (
            "- Acceptance authorization instruction packet ready: "
            f"`{status.get('acceptance_authorization_instruction_packet_ready')}`"
        ),
        (
            "- Future manual acceptance authorization review prerequisites met: "
            f"`{status.get('future_manual_acceptance_authorization_review_prerequisites_met')}`"
        ),
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        (
            "- Actual human authorization review happened: "
            f"`{status.get('actual_human_authorization_review_happened')}`"
        ),
        (
            "- Still blocked gate ids: "
            f"`{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`"
        ),
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Open These First",
        "",
        "| Order | Artifact | Path | Why |",
        "| --- | --- | --- | --- |",
    ]
    for entry in _mapping_list(packet.get("open_these_first")):
        lines.append(
            f"| {_markdown_cell(entry.get('order'))} | "
            f"{_markdown_cell(entry.get('artifact_id'))} | "
            f"{_markdown_cell(entry.get('artifact_path'))} | "
            f"{_markdown_cell(entry.get('why_read_first'))} |"
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
            f"- Validator target: `{future_record_requirements.get('validator_target')}`",
            f"- Target record type: `{future_record_requirements.get('target_record_type')}`",
            f"- Validator notice: {future_record_requirements.get('validator_notice')}",
            "",
            "### Required Record Fields",
            "",
            "| Field | Required | Template value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in _mapping_list(future_record_requirements.get("required_record_fields")):
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
    for entry in _mapping_list(
        future_record_requirements.get("required_review_conclusions")
    ):
        lines.append(
            f"- `{entry.get('conclusion_id')}`: {entry.get('detail')}"
        )

    lines.extend(
        [
            "",
            "### Required Runtime Patch Statement Ids",
            "",
            (
                "- `"
                + ", ".join(
                    _string_list(
                        future_record_requirements.get(
                            "required_runtime_patch_statement_ids"
                        )
                    )
                )
                + "`"
            ),
            "",
            "### Future Validation Checklist",
            "",
        ]
    )
    for entry in _mapping_list(
        future_record_requirements.get("future_validation_checklist")
    ):
        lines.append(f"- `{entry.get('checklist_id')}`: {entry.get('detail')}")

    lines.extend(
        [
            "",
            "## Ordered Instructions",
            "",
        ]
    )
    for entry in _mapping_list(packet.get("ordered_instructions")):
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
            "## Example Reference",
            "",
            f"- Example bundle artifact path: `{example_reference.get('example_bundle_artifact_path')}`",
            f"- Example bundle builder script: `{example_reference.get('example_bundle_builder_script')}`",
            f"- Synthetic example reference only: `{example_reference.get('synthetic_example_reference_only')}`",
            f"- Synthetic example payload validated: `{example_reference.get('synthetic_example_payload_validated')}`",
            f"- Reference notice: {example_reference.get('reference_notice')}",
            f"- Use when: {example_reference.get('use_when')}",
            "",
            "## Verify Before Stopping",
            "",
        ]
    )
    for entry in _mapping_list(packet.get("verify_before_stopping")):
        lines.append(
            f"- `{entry.get('check_id')}`: {entry.get('detail')} "
            f"(current_value=`{entry.get('current_value')}`)"
        )

    lines.extend(
        [
            "",
            "## Preserved State Assertions",
            "",
            "| Assertion | Expected value | Current value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for assertion_id, entry in _mapping(packet.get("preserved_state_assertions")).items():
        assertion_entry = _mapping(entry)
        lines.append(
            f"| {_markdown_cell(assertion_id)} | "
            f"{_markdown_cell(assertion_entry.get('expected_value'))} | "
            f"{_markdown_cell(assertion_entry.get('current_value'))} | "
            f"{_markdown_cell(assertion_entry.get('detail'))} |"
        )

    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
        ]
    )
    for entry in _mapping_list(packet.get("stop_conditions")):
        lines.append(
            f"- `{entry.get('condition_id')}`: {entry.get('detail')} "
            f"(currently_triggered=`{entry.get('currently_triggered')}`)"
        )

    lines.extend(
        [
            "",
            "## Forbidden Claims Or Actions",
            "",
        ]
    )
    for entry in _string_list(packet.get("forbidden_claims_or_actions")):
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    packet = _mapping(report.get("acceptance_authorization_instruction_packet"))
    locked_execution_target = _mapping(packet.get("locked_execution_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization instruction packet",
            "acceptance_authorization_instruction_packet_ready="
            + str(status.get("acceptance_authorization_instruction_packet_ready")),
            "future_manual_acceptance_authorization_review_prerequisites_met="
            + str(
                status.get(
                    "future_manual_acceptance_authorization_review_prerequisites_met"
                )
            ),
            "acceptance_execution_authorized="
            + str(status.get("acceptance_execution_authorized")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            "acceptance_executed=" + str(status.get("acceptance_executed")),
            "actual_human_authorization_review_happened="
            + str(status.get("actual_human_authorization_review_happened")),
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


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = (
        "anchor119_row_domain_acceptance_authorization_instruction_packet"
    ),
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_ordered_instructions(
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
            "step_id": "open_operator_handoff_bundle_first",
            "order": 1,
            "detail": (
                "Open the acceptance-authorization operator handoff bundle first. "
                "Use it as the primary operator entrypoint for the locked "
                "prod_4x4_normal target and the currently blocked prerequisite gates."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "confirm_locked_prod_4x4_normal_target",
            "order": 2,
            "detail": (
                "Confirm that the only authoritative future execution target remains "
                f"prod_4x4_normal, with exact future command "
                f"`{exact_future_acceptance_command}` and exact future result path "
                f"`{exact_future_acceptance_result_path}` unchanged."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "consult_validator_contract",
            "order": 3,
            "detail": (
                "Open the validator artifact at "
                f"`{validator_artifact_path}` and use it as the contract for what "
                "a future real human acceptance-authorization review record must "
                "contain."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "consult_example_reference_only",
            "order": 4,
            "detail": (
                "Open the synthetic example bundle at "
                f"`{example_bundle_artifact_path}` only as a reference for field "
                "shape and validator replay behavior. It is never proof that a human "
                "review has happened."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "carry_forward_blocked_prerequisites_exactly",
            "order": 5,
            "detail": (
                "Carry forward the currently blocked prerequisite gate ids exactly as "
                "reported. Do not clear, downgrade, or reinterpret them by guesswork."
            ),
            "blocked_by_gate_ids": blocked,
        },
        {
            "step_id": "prepare_future_real_human_review_record_requirements",
            "order": 6,
            "detail": (
                "Before stopping, ensure the future real human review record still "
                "has space for every required field, required conclusion id, "
                "required runtime patch statement id, missing prerequisite gate id, "
                "and human-authored notes required by the validator contract."
            ),
            "blocked_by_gate_ids": [],
        },
        {
            "step_id": "verify_preserved_state_and_stop_review_only",
            "order": 7,
            "detail": (
                "Verify that acceptance_execution_authorized=false, "
                "runtime_enablement_allowed=false, acceptance_executed=false, and "
                "actual_human_authorization_review_happened=false still hold, then "
                "stop. Do not authorize execution, enable runtime, or execute "
                "acceptance from this packet."
            ),
            "blocked_by_gate_ids": blocked,
        },
    ]


def _validator_contract_only(
    status: Mapping[str, Any], validator: Mapping[str, Any]
) -> bool:
    actual_record_validation = _mapping(validator.get("actual_record_validation"))
    return bool(
        validator.get("does_not_authorize_execution", False)
        and validator.get("does_not_execute_acceptance", False)
        and validator.get("does_not_imply_enablement", False)
        and not bool(status.get("authorization_review_completed", False))
        and not bool(status.get("authorization_review_record_provided", False))
        and not bool(status.get("authorization_review_record_validated", False))
        and not bool(actual_record_validation.get("record_payload_validated", False))
    )


def _example_reference_only(
    status: Mapping[str, Any], example_bundle: Mapping[str, Any]
) -> bool:
    notes = [entry.lower() for entry in _string_list(example_bundle.get("example_only_notes"))]
    mentions_synthetic = any("synthetic" in entry or "demo" in entry for entry in notes)
    mentions_not_actual = any(
        "not an actual human authorization review record" in entry for entry in notes
    )
    mentions_not_authorization = any(
        "does not authorize execution" in entry
        or "not execution authorization" in entry
        for entry in notes
    )
    return bool(
        example_bundle.get("does_not_authorize_execution", False)
        and example_bundle.get("does_not_execute_acceptance", False)
        and example_bundle.get("does_not_imply_enablement", False)
        and bool(status.get("synthetic_example_payload_created", False))
        and bool(status.get("synthetic_example_payload_validated", False))
        and mentions_synthetic
        and (mentions_not_actual or mentions_not_authorization)
    )


def _operator_scope(candidate: Mapping[str, Any]) -> str:
    key = candidate.get("key")
    anchor_idx = candidate.get("anchor_idx")
    formulation_profile = candidate.get("formulation_profile")
    return (
        f"candidate={key}, anchor_idx={anchor_idx}, "
        f"formulation_profile={formulation_profile}"
    )


def _review_only_contract_retained(*metadatas: Mapping[str, Any]) -> bool:
    relevant = [metadata for metadata in metadatas if metadata]
    if not relevant:
        return False
    return all(
        bool(metadata.get("spec_only", False))
        and bool(metadata.get("review_only", False))
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


def _locked_string_lists(*values: list[str]) -> tuple[list[str], bool]:
    normalized_lists = [_normalize_id_list(value) for value in values if value]
    if not normalized_lists:
        return [], False
    baseline = normalized_lists[0]
    return list(baseline), bool(
        len(normalized_lists) >= 2 and all(entry == baseline for entry in normalized_lists[1:])
    )


def _normalize_id_list(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in values:
        text = str(entry).strip()
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered


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
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


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


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


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
    return _render_value(value).replace("|", "\\|").replace("\n", "<br>")

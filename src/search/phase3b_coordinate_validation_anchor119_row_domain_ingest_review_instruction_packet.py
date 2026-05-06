from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
)
INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
)
INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
)
DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)
DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/"
    "anchor119_row_domain_ingest_review_record_example_bundle.json"
)
DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SCRIPT_PATH = Path(
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle.py"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_SCRIPT_PATH = Path(
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator.py"
)
DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SCRIPT_PATH = Path(
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle.py"
)
INSTRUCTION_PACKET_NOTICE = (
    "Review-only/spec-only/operator-facing instruction packet only. This packet "
    "tightens the future manual ingest-review path on anchor119 into one bounded "
    "checklist, but it does not update repo-side review state, does not imply any "
    "actual human review has happened, does not imply reviewed_runtime_patch_exists=true, "
    "does not imply runtime_enablement_allowed=true, and does not authorize execution."
)
PRESERVED_STATE_DETAIL = (
    "Preserve repo_side_review_state_updated=false, reviewed_runtime_patch_exists=false, "
    "runtime_enablement_allowed=false, proof_source=false, candidate_elimination_claim=false, "
    "and solver_invoked=false. This packet is review-only and never authorizes execution."
)
EXPECTED_HANDOFF_SHAPE_DETAIL = (
    "The locked handoff path shape is authoritative. The validator template's "
    "`reviewer_record_handoff_path` field must continue to reference this exact shape."
)
EXAMPLE_REFERENCE_ONLY_DETAIL = (
    "Synthetic example is reference only. It is not an actual human ingest-review "
    "record, not a completed human review, and not an applied repo-side review-state update."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet(
    project_root: Path,
    *,
    ingest_review_operator_handoff_bundle_path: Optional[Path] = None,
    ingest_review_record_validator_path: Optional[Path] = None,
    ingest_review_record_example_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ingest_review_operator_handoff_bundle_resolved = _resolve_path(
        project_root,
        ingest_review_operator_handoff_bundle_path
        if ingest_review_operator_handoff_bundle_path is not None
        else DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH,
    )
    ingest_review_record_validator_resolved = _resolve_path(
        project_root,
        ingest_review_record_validator_path
        if ingest_review_record_validator_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH,
    )
    ingest_review_record_example_bundle_resolved = _resolve_path(
        project_root,
        ingest_review_record_example_bundle_path
        if ingest_review_record_example_bundle_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH,
    )
    ingest_review_operator_handoff_bundle_script_resolved = _resolve_path(
        project_root, DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SCRIPT_PATH
    )
    ingest_review_record_validator_script_resolved = _resolve_path(
        project_root, DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_SCRIPT_PATH
    )
    ingest_review_record_example_bundle_script_resolved = _resolve_path(
        project_root, DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SCRIPT_PATH
    )

    handoff_report, handoff_error = _load_json_mapping(
        ingest_review_operator_handoff_bundle_resolved
    )
    validator_report, validator_error = _load_json_mapping(
        ingest_review_record_validator_resolved
    )
    example_report, example_error = _load_json_mapping(
        ingest_review_record_example_bundle_resolved
    )

    handoff_meta = _mapping(handoff_report.get("metadata")) if handoff_report else {}
    handoff_status = _mapping(handoff_report.get("status")) if handoff_report else {}
    handoff_paths = _mapping(handoff_report.get("paths")) if handoff_report else {}
    handoff_bundle = (
        _mapping(handoff_report.get("ingest_review_operator_handoff_bundle"))
        if handoff_report
        else {}
    )
    validator_meta = _mapping(validator_report.get("metadata")) if validator_report else {}
    validator_status = (
        _mapping(validator_report.get("status")) if validator_report else {}
    )
    validator = (
        _mapping(validator_report.get("ingest_review_record_validator"))
        if validator_report
        else {}
    )
    example_meta = _mapping(example_report.get("metadata")) if example_report else {}
    example_status = _mapping(example_report.get("status")) if example_report else {}
    example_bundle = (
        _mapping(example_report.get("ingest_review_record_example_bundle"))
        if example_report
        else {}
    )
    candidate = _first_mapping(
        handoff_report.get("candidate") if handoff_report else None,
        validator_report.get("candidate") if validator_report else None,
        example_report.get("candidate") if example_report else None,
    )

    handoff_present = bool(
        handoff_report is not None
        and handoff_error is None
        and handoff_meta.get("source") == INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE
    )
    validator_present = bool(
        validator_report is not None
        and validator_error is None
        and validator_meta.get("source") == INGEST_REVIEW_RECORD_VALIDATOR_SOURCE
    )
    example_present = bool(
        example_report is not None
        and example_error is None
        and example_meta.get("source") == INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE
    )

    upstream_handoff_bundle_ready = bool(
        handoff_present
        and handoff_status.get("ingest_review_operator_handoff_bundle_ready", False)
    )
    upstream_handoff_bundle_contract_compatible = bool(
        handoff_present and handoff_status.get("contract_compatible", False)
    )
    ingest_review_record_validator_ready = bool(
        validator_present and validator_status.get("ingest_review_record_validator_ready", False)
    )
    ingest_review_record_example_bundle_ready = bool(
        example_present
        and example_status.get("ingest_review_record_example_bundle_ready", False)
    )

    handoff_operator_target = _mapping(handoff_bundle.get("operator_target"))
    handoff_locked_handoff = _mapping(handoff_bundle.get("locked_handoff_path_shape"))
    handoff_validator_reference = _mapping(
        handoff_bundle.get("validator_script_or_artifact_reference")
    )
    handoff_example_reference = _mapping(handoff_bundle.get("example_bundle_reference"))
    handoff_preserved_state = _mapping(handoff_bundle.get("preserved_state_assertions"))

    validator_locked_target = _mapping(validator.get("locked_target_review_state"))
    validator_locked_handoff = _mapping(validator.get("locked_reviewer_record_handoff"))
    validator_expected_template_payload = _mapping(
        validator.get("expected_template_payload")
    )
    validator_required_review_conclusions = _mapping_list(
        validator.get("required_review_conclusions")
    )
    validator_blocked_gate_contract = _mapping(validator.get("blocked_gate_contract"))
    validator_rules = _mapping(validator.get("validator_rules"))
    validator_required_fields = _mapping_list(validator_rules.get("required_fields"))
    validator_required_reviewer_statement_ids = _string_list(
        _mapping(validator_rules.get("required_reviewer_statement_ids")).get("required_ids")
    )
    validator_required_review_conclusion_ids = _string_list(
        _mapping(validator_rules.get("required_review_conclusion_ids")).get("required_ids")
    )
    validator_review_conclusions_rule = _mapping(
        validator_rules.get("review_conclusions")
    )

    example_locked_target = _mapping(example_bundle.get("locked_target_review_state"))
    example_locked_handoff = _mapping(example_bundle.get("locked_reviewer_record_handoff"))
    example_preserved_state = _mapping(
        example_bundle.get("preserved_state_assertions")
    )
    example_replay_instructions = _mapping(example_bundle.get("replay_instructions"))
    example_replayed_validation_summary = _mapping(
        example_bundle.get("replayed_validation_summary")
    )
    example_payload = _mapping(
        example_bundle.get("synthetic_completed_ingest_review_record_payload")
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            _mapping(handoff_report.get("candidate")).get("key") if handoff_report else None,
            _mapping(validator_report.get("candidate")).get("key")
            if validator_report
            else None,
            _mapping(example_report.get("candidate")).get("key") if example_report else None,
        ],
        normalize=_normalize_text,
    )
    anchor_idx, anchor_idx_locked = _locked_value(
        [
            _mapping(handoff_report.get("candidate")).get("anchor_idx")
            if handoff_report
            else None,
            _mapping(validator_report.get("candidate")).get("anchor_idx")
            if validator_report
            else None,
            _mapping(example_report.get("candidate")).get("anchor_idx")
            if example_report
            else None,
        ],
        normalize=_normalize_scalar,
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            _mapping(handoff_report.get("candidate")).get("formulation_profile")
            if handoff_report
            else None,
            _mapping(validator_report.get("candidate")).get("formulation_profile")
            if validator_report
            else None,
            _mapping(example_report.get("candidate")).get("formulation_profile")
            if example_report
            else None,
        ],
        normalize=_normalize_text,
    )
    candidate_consistent = bool(
        candidate_key_locked and anchor_idx_locked and formulation_profile_locked
    )

    review_state_kind, review_state_kind_locked = _locked_value(
        [
            handoff_operator_target.get("review_state_kind"),
            validator_locked_target.get("review_state_kind"),
            example_locked_target.get("review_state_kind"),
        ],
        normalize=_normalize_text,
    )
    tracked_field, tracked_field_locked = _locked_value(
        [
            handoff_operator_target.get("tracked_field"),
            validator_locked_target.get("tracked_field"),
            example_locked_target.get("tracked_field"),
        ],
        normalize=_normalize_text,
    )
    record_identity, record_identity_locked = _locked_value(
        [
            handoff_operator_target.get("record_identity"),
            validator_locked_target.get("record_identity"),
            example_locked_target.get("record_identity"),
        ],
        normalize=_normalize_text,
    )
    target_record_type, target_record_type_locked = _locked_value(
        [
            handoff_operator_target.get("target_record_type"),
            validator_locked_target.get("record_type"),
            example_locked_target.get("record_type"),
        ],
        normalize=_normalize_text,
    )
    scope, scope_locked = _locked_value(
        [
            handoff_operator_target.get("scope"),
            validator_locked_target.get("scope"),
            example_locked_target.get("scope"),
        ],
        normalize=_normalize_text,
    )
    proposed_field_value_if_approved, proposed_field_value_if_approved_locked = (
        _locked_value(
            [
                handoff_operator_target.get("proposed_field_value_if_approved"),
                validator_locked_target.get("proposed_field_value_if_approved"),
                example_locked_target.get("proposed_field_value_if_approved"),
            ],
            normalize=_normalize_scalar,
        )
    )
    packet_target_consistent = bool(
        review_state_kind_locked
        and tracked_field_locked
        and record_identity_locked
        and target_record_type_locked
        and scope_locked
        and proposed_field_value_if_approved_locked
    )

    handoff_format, handoff_format_locked = _locked_value(
        [
            handoff_locked_handoff.get("handoff_format"),
            validator_locked_handoff.get("handoff_format"),
            example_locked_handoff.get("handoff_format"),
        ],
        normalize=_normalize_text,
    )
    handoff_dir, handoff_dir_locked = _locked_value(
        [
            handoff_locked_handoff.get("handoff_dir"),
            validator_locked_handoff.get("handoff_dir"),
            example_locked_handoff.get("handoff_dir"),
        ],
        normalize=_normalize_path_text,
    )
    handoff_path_shape, handoff_path_shape_locked = _locked_value(
        [
            handoff_locked_handoff.get("path_shape"),
            validator_locked_handoff.get("handoff_path_shape"),
            example_locked_handoff.get("handoff_path_shape"),
        ],
        normalize=_normalize_path_text,
    )
    handoff_filename_tokens, handoff_filename_tokens_locked = _locked_string_list(
        [
            handoff_locked_handoff.get("handoff_filename_tokens"),
            validator_locked_handoff.get("handoff_filename_tokens"),
            example_locked_handoff.get("handoff_filename_tokens"),
        ]
    )
    locked_handoff_path_shape_consistent = bool(
        handoff_format_locked
        and handoff_dir_locked
        and handoff_path_shape_locked
        and handoff_filename_tokens_locked
        and handoff_format
        and handoff_dir
        and handoff_path_shape
    )

    validator_target, validator_target_locked = _locked_value(
        [
            handoff_validator_reference.get("validator_target"),
            validator.get("validator_target"),
            example_bundle.get("validator_target"),
            example_replay_instructions.get("validator_target"),
        ],
        normalize=_normalize_text,
    )
    locked_reviewer_record_validator_target, locked_reviewer_record_validator_target_locked = (
        _locked_value(
            [
                handoff_validator_reference.get("future_reviewer_record_validator_target"),
                validator.get("locked_reviewer_record_validator_target"),
                validator_expected_template_payload.get("validator_target"),
            ],
            normalize=_normalize_text,
        )
    )
    validator_reference_path_matches = bool(
        _normalize_path_text(handoff_validator_reference.get("artifact_path"))
        == _normalize_path_text(
            _display_path(project_root, ingest_review_record_validator_resolved)
        )
    )
    validator_reference_consistent = bool(
        validator_target_locked
        and locked_reviewer_record_validator_target_locked
        and validator_reference_path_matches
        and validator_target
        and locked_reviewer_record_validator_target
    )

    example_reference_path_matches = bool(
        _normalize_path_text(handoff_example_reference.get("artifact_path"))
        == _normalize_path_text(
            _display_path(project_root, ingest_review_record_example_bundle_resolved)
        )
    )
    example_reference_only = bool(
        example_reference_path_matches
        and ingest_review_record_example_bundle_ready
        and bool(handoff_example_reference.get("synthetic_example_is_reference_only", False))
        and "synthetic" in str(example_bundle.get("example_kind") or "").lower()
        and not bool(example_bundle.get("actual_human_review_record", False))
        and not bool(example_bundle.get("applied_repo_state_update", False))
    )

    validator_contract_shape_available = bool(
        validator_expected_template_payload
        and validator_required_fields
        and validator_required_review_conclusions
        and validator_required_reviewer_statement_ids
        and validator_required_review_conclusion_ids
        and validator_review_conclusions_rule
    )
    validator_expected_handoff_field_locked = bool(
        handoff_path_shape
        and _normalize_path_text(
            validator_expected_template_payload.get("reviewer_record_handoff_path")
        )
        == _normalize_path_text(handoff_path_shape)
    )
    example_shape_matches_validator_template = bool(
        validator_expected_template_payload
        and example_payload
        and set(validator_expected_template_payload.keys()) == set(example_payload.keys())
    )

    review_only_contract_retained = _review_only_contract_retained(
        handoff_meta, validator_meta, example_meta
    )
    repo_side_review_state_unchanged = not any(
        bool(value)
        for value in [
            handoff_meta.get("repo_side_review_state_updated", False),
            validator_meta.get("repo_side_review_state_updated", False),
            example_meta.get("repo_side_review_state_updated", False),
            handoff_status.get("repo_side_review_state_updated", False),
            validator_status.get("repo_side_review_state_updated", False),
            example_status.get("repo_side_review_state_updated", False),
            handoff_preserved_state.get("repo_side_review_state_updated", False),
            example_preserved_state.get("repo_side_review_state_updated", False),
        ]
    )
    reviewed_runtime_patch_exists_false = not any(
        bool(value)
        for value in [
            handoff_status.get("reviewed_runtime_patch_exists", False),
            validator_status.get("reviewed_runtime_patch_exists", False),
            example_status.get("reviewed_runtime_patch_exists", False),
            handoff_preserved_state.get("reviewed_runtime_patch_exists", False),
            example_preserved_state.get("reviewed_runtime_patch_exists", False),
            validator_expected_template_payload.get("reviewed_runtime_patch_exists", False),
            example_payload.get("reviewed_runtime_patch_exists", False),
        ]
    )
    runtime_enablement_allowed_false = not any(
        bool(value)
        for value in [
            handoff_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
            example_status.get("runtime_enablement_allowed", False),
            handoff_preserved_state.get("runtime_enablement_allowed", False),
            example_preserved_state.get("runtime_enablement_allowed", False),
            validator_expected_template_payload.get("runtime_enablement_allowed", False),
            example_payload.get("runtime_enablement_allowed", False),
        ]
    )
    actual_human_review_not_claimed = not any(
        bool(value)
        for value in [
            handoff_operator_target.get("actual_human_review_has_happened", False),
            validator_status.get("manual_ingest_review_record_provided", False),
            validator_status.get("manual_ingest_review_record_validated", False),
            example_bundle.get("actual_human_review_record", False),
        ]
    )
    execution_authorization_not_implied = not any(
        bool(value)
        for value in [
            handoff_operator_target.get("execution_authorized", False),
            handoff_preserved_state.get("execution_authorized", False),
            example_preserved_state.get("execution_authorized", False),
        ]
    )
    preserved_state_assertions_retained = bool(
        repo_side_review_state_unchanged
        and reviewed_runtime_patch_exists_false
        and runtime_enablement_allowed_false
        and actual_human_review_not_claimed
        and execution_authorization_not_implied
    )

    contract_compatible = bool(
        upstream_handoff_bundle_contract_compatible
        and ingest_review_record_validator_ready
        and ingest_review_record_example_bundle_ready
        and candidate_consistent
        and packet_target_consistent
        and locked_handoff_path_shape_consistent
        and validator_reference_consistent
        and validator_contract_shape_available
        and validator_expected_handoff_field_locked
        and example_reference_only
        and example_shape_matches_validator_template
        and review_only_contract_retained
        and preserved_state_assertions_retained
    )
    ingest_review_instruction_packet_ready = bool(
        upstream_handoff_bundle_ready and contract_compatible
    )

    open_these_first = [
        _open_reference(
            order=1,
            artifact_id="ingest_review_operator_handoff_bundle",
            path=_display_path(project_root, ingest_review_operator_handoff_bundle_resolved),
            secondary_reference=_display_path(
                project_root, ingest_review_operator_handoff_bundle_script_resolved
            ),
            why=(
                "Authoritative entrypoint for the future manual ingest-review path. "
                "Confirm it is ready and contract-compatible before trusting any downstream reference."
            ),
        ),
        _open_reference(
            order=2,
            artifact_id="ingest_review_record_validator",
            path=_display_path(project_root, ingest_review_record_validator_resolved),
            secondary_reference=_display_path(
                project_root, ingest_review_record_validator_script_resolved
            ),
            why=(
                "Locks the exact future completed ingest-review record contract, required fields, "
                "required review conclusions, and preserved blocked-gate rules."
            ),
        ),
        _open_reference(
            order=3,
            artifact_id="ingest_review_record_example_bundle",
            path=_display_path(project_root, ingest_review_record_example_bundle_resolved),
            secondary_reference=_display_path(
                project_root, ingest_review_record_example_bundle_script_resolved
            ),
            why=(
                "Synthetic shape reference only. Use it to compare wording and field layout, "
                "never as proof that a human review already happened."
            ),
        ),
    ]
    ordered_instructions = [
        _instruction(
            1,
            "open_operator_handoff_bundle_first",
            "Open the existing ingest-review operator handoff bundle first.",
            [
                "metadata.source must equal the locked operator handoff bundle source",
                "status.ingest_review_operator_handoff_bundle_ready must be true",
                "status.contract_compatible must be true",
            ],
            "Stop if the handoff bundle is missing, not ready, or no longer contract-compatible.",
            (
                "Treat the operator handoff bundle as the authoritative entrypoint for this path. "
                "Do not guess alternate inputs if that bundle is not ready."
            ),
        ),
        _instruction(
            2,
            "treat_only_three_paths_as_authoritative",
            "Use only the locked operator handoff bundle, validator artifact, and example bundle as authoritative inputs for this packet.",
            [
                "The three authoritative artifact paths match the locked packet paths",
                "No substitute path is introduced for validator/example references",
            ],
            "Stop if an operator would need to guess a different artifact path.",
            (
                "This packet is bounded. It narrows the review path to the locked artifacts above "
                "instead of re-opening repo-wide discovery."
            ),
        ),
        _instruction(
            3,
            "read_validator_for_exact_record_shape",
            "Open the validator artifact or script to read the exact future completed ingest-review record shape.",
            [
                "validator_target matches the locked operator handoff bundle reference",
                "expected_template_payload is present",
                "required reviewer statement ids and required review conclusion ids are present",
            ],
            "Stop if the validator no longer exposes the locked template payload and rule set.",
            (
                "The validator artifact, not freeform judgment, defines the exact field shape that a future "
                "manual ingest-review record must satisfy."
            ),
        ),
        _instruction(
            4,
            "lock_the_reviewer_handoff_path_shape",
            "Verify that the locked reviewer-record handoff path shape stays exactly aligned across the handoff bundle, validator, and example bundle.",
            [
                "handoff format remains json",
                "handoff dir, path shape, and filename tokens stay locked",
                "validator expected_template_payload.reviewer_record_handoff_path equals the locked path shape",
            ],
            "Stop if the handoff path shape drifts or the expected handoff field no longer points at that locked shape.",
            EXPECTED_HANDOFF_SHAPE_DETAIL,
        ),
        _instruction(
            5,
            "use_example_only_as_reference",
            "Consult the example bundle only as a synthetic reference for wording and field layout.",
            [
                "example bundle is ready",
                "example_kind remains synthetic",
                "actual_human_review_record remains false",
                "applied_repo_state_update remains false",
            ],
            "Stop if the example bundle starts to imply that a real human review already happened.",
            EXAMPLE_REFERENCE_ONLY_DETAIL,
        ),
        _instruction(
            6,
            "preserve_state_and_stop_without_execution",
            "Before stopping, verify that repo-side state stays unchanged and that the remaining blocked gates are still carried forward.",
            [
                "repo_side_review_state_updated remains false",
                "reviewed_runtime_patch_exists remains false",
                "runtime_enablement_allowed remains false",
                "still_blocked_gate_ids are captured for handoff without claiming they were cleared",
            ],
            "Stop once the operator has confirmed the packet, captured the still-blocked gates, and left repo-side review state unchanged.",
            (
                "This packet is review-only/spec-only/default-off and must not authorize execution, "
                "enablement, or any repo-side review-state update."
            ),
        ),
    ]

    stop_conditions = [
        _stop_condition(
            "authoritative_operator_handoff_bundle_confirmed",
            upstream_handoff_bundle_ready and upstream_handoff_bundle_contract_compatible,
            (
                "The operator handoff bundle is present, ready, and still contract-compatible."
            ),
        ),
        _stop_condition(
            "validator_contract_shape_confirmed",
            ingest_review_record_validator_ready
            and validator_reference_consistent
            and validator_contract_shape_available,
            (
                "The validator reference is ready and still exposes the locked template payload, "
                "required field rules, and required review conclusions."
            ),
        ),
        _stop_condition(
            "synthetic_example_reference_only_confirmed",
            example_reference_only and example_shape_matches_validator_template,
            (
                "The example bundle remains synthetic/reference-only and still matches the validator template shape."
            ),
        ),
        _stop_condition(
            "locked_handoff_path_shape_confirmed",
            locked_handoff_path_shape_consistent and validator_expected_handoff_field_locked,
            EXPECTED_HANDOFF_SHAPE_DETAIL,
        ),
        _stop_condition(
            "preserved_state_assertions_still_false",
            preserved_state_assertions_retained,
            PRESERVED_STATE_DETAIL,
        ),
        _stop_condition(
            "still_blocked_gate_ids_recorded_without_state_change",
            True,
            (
                "The operator stops with the still-blocked gate ids carried forward and with no repo-side "
                "review-state mutation or execution authorization."
            ),
        ),
    ]

    forbidden_claims_or_actions = [
        "Do not claim that any actual human ingest review has already happened.",
        "Do not claim that the synthetic example bundle is proof or a completed human review.",
        "Do not claim candidate elimination or any solver-backed result from this packet.",
        "Do not update repo-side review state from this packet.",
        "Do not imply reviewed_runtime_patch_exists=true.",
        "Do not imply runtime_enablement_allowed=true.",
        "Do not imply reviewed_runtime_patch_ingest_gate execution is authorized.",
        "Do not change the locked reviewer-record handoff path shape or filename tokens.",
        "Do not rewrite repo-side review state or any review-status artifact while following this packet.",
        "Do not authorize execution or runtime enablement.",
    ]

    gates = [
        _gate(
            "upstream_handoff_bundle_ready",
            upstream_handoff_bundle_ready,
            True,
            "The instruction packet depends on the upstream ingest-review operator handoff bundle already being ready.",
        ),
        _gate(
            "upstream_handoff_bundle_contract_compatible",
            upstream_handoff_bundle_contract_compatible,
            True,
            "The instruction packet only holds when the upstream operator handoff bundle remains contract-compatible.",
        ),
        _gate(
            "instruction_packet_contract_compatible",
            contract_compatible,
            True,
            "The instruction packet requires aligned target identity, handoff path shape, validator reference, example reference, and preserved-state assertions.",
        ),
        _gate(
            "instruction_packet_review_only_default_off_retained",
            review_only_contract_retained and preserved_state_assertions_retained,
            True,
            "The packet must remain review-only/spec-only/default-off/no-solve and must preserve proof_source=false.",
        ),
        _gate(
            "instruction_packet_not_execution_authorization",
            True,
            False,
            INSTRUCTION_PACKET_NOTICE,
        ),
    ]
    gates.extend(
        _merge_gate_entries(
            handoff_report.get("gates") if handoff_report else None,
            validator_report.get("gates") if validator_report else None,
            example_report.get("gates") if example_report else None,
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

    checks = [
        _check(
            "ingest_review_operator_handoff_bundle_present",
            "pass" if handoff_present else "fail",
            _presence_detail(
                handoff_report,
                handoff_error,
                handoff_meta,
                INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE,
                project_root,
                ingest_review_operator_handoff_bundle_resolved,
            ),
        ),
        _check(
            "ingest_review_operator_handoff_bundle_ready",
            "pass" if upstream_handoff_bundle_ready else "fail",
            "ingest_review_operator_handoff_bundle_ready=true"
            if upstream_handoff_bundle_ready
            else "ingest_review_operator_handoff_bundle_ready=false",
        ),
        _check(
            "ingest_review_operator_handoff_bundle_contract_compatible",
            "pass" if upstream_handoff_bundle_contract_compatible else "fail",
            "contract_compatible=true"
            if upstream_handoff_bundle_contract_compatible
            else "contract_compatible=false",
        ),
        _check(
            "ingest_review_record_validator_present",
            "pass" if validator_present else "fail",
            _presence_detail(
                validator_report,
                validator_error,
                validator_meta,
                INGEST_REVIEW_RECORD_VALIDATOR_SOURCE,
                project_root,
                ingest_review_record_validator_resolved,
            ),
        ),
        _check(
            "ingest_review_record_validator_ready",
            "pass" if ingest_review_record_validator_ready else "fail",
            "ingest_review_record_validator_ready=true"
            if ingest_review_record_validator_ready
            else "ingest_review_record_validator_ready=false",
        ),
        _check(
            "ingest_review_record_example_bundle_present",
            "pass" if example_present else "fail",
            _presence_detail(
                example_report,
                example_error,
                example_meta,
                INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
                project_root,
                ingest_review_record_example_bundle_resolved,
            ),
        ),
        _check(
            "ingest_review_record_example_bundle_ready",
            "pass" if ingest_review_record_example_bundle_ready else "fail",
            "ingest_review_record_example_bundle_ready=true"
            if ingest_review_record_example_bundle_ready
            else "ingest_review_record_example_bundle_ready=false",
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "All upstream artifacts retain review_only/spec_only/default_off and keep proof_source=false, candidate_elimination_claim=false, and solver_invoked=false."
            if review_only_contract_retained
            else "At least one upstream artifact drifted away from the review-only/default-off/no-solve contract.",
        ),
        _check(
            "candidate_consistent",
            "pass" if candidate_consistent else "fail",
            "Candidate key, anchor_idx, and formulation_profile are locked across the operator handoff bundle, validator, and example bundle."
            if candidate_consistent
            else "Candidate identity mismatch across the upstream artifacts.",
        ),
        _check(
            "packet_target_consistent",
            "pass" if packet_target_consistent else "fail",
            "Locked target review-state identity, tracked field, scope, and proposed field value agree across handoff/validator/example inputs."
            if packet_target_consistent
            else "Locked packet target mismatch across the upstream artifacts.",
        ),
        _check(
            "locked_handoff_path_shape_consistent",
            "pass" if locked_handoff_path_shape_consistent else "fail",
            "Locked handoff format, directory, path shape, and filename tokens agree across the upstream artifacts."
            if locked_handoff_path_shape_consistent
            else "Locked handoff path shape mismatch across the upstream artifacts.",
        ),
        _check(
            "validator_reference_consistent",
            "pass" if validator_reference_consistent else "fail",
            "Validator artifact path, validator target, and reviewer-record validator target remain locked."
            if validator_reference_consistent
            else "Validator reference mismatch across the upstream artifacts.",
        ),
        _check(
            "validator_contract_shape_available",
            "pass" if validator_contract_shape_available else "fail",
            "Validator template payload, required field rules, required reviewer statement ids, and required review conclusions are available."
            if validator_contract_shape_available
            else "Validator no longer exposes the exact future completed ingest-review record shape.",
        ),
        _check(
            "validator_expected_handoff_field_locked",
            "pass" if validator_expected_handoff_field_locked else "fail",
            EXPECTED_HANDOFF_SHAPE_DETAIL
            if validator_expected_handoff_field_locked
            else "Validator template reviewer_record_handoff_path no longer matches the locked handoff path shape.",
        ),
        _check(
            "example_reference_only",
            "pass" if example_reference_only else "fail",
            EXAMPLE_REFERENCE_ONLY_DETAIL
            if example_reference_only
            else "Example bundle no longer reads as a synthetic/reference-only artifact.",
        ),
        _check(
            "example_shape_matches_validator_template",
            "pass" if example_shape_matches_validator_template else "fail",
            "Synthetic example payload key set matches the validator expected template payload key set."
            if example_shape_matches_validator_template
            else "Synthetic example payload shape drifted away from the validator template shape.",
        ),
        _check(
            "preserved_state_assertions_retained",
            "pass" if preserved_state_assertions_retained else "fail",
            PRESERVED_STATE_DETAIL
            if preserved_state_assertions_retained
            else "An upstream artifact implies repo-state mutation, actual human review completion, or execution authorization.",
        ),
    ]
    ready_prerequisite_check_ids = {
        "ingest_review_operator_handoff_bundle_present",
        "ingest_review_operator_handoff_bundle_ready",
        "ingest_review_operator_handoff_bundle_contract_compatible",
        "ingest_review_record_validator_present",
        "ingest_review_record_validator_ready",
        "ingest_review_record_example_bundle_present",
        "ingest_review_record_example_bundle_ready",
        "review_only_contract_retained",
        "candidate_consistent",
        "packet_target_consistent",
        "locked_handoff_path_shape_consistent",
        "validator_reference_consistent",
        "validator_contract_shape_available",
        "validator_expected_handoff_field_locked",
        "example_reference_only",
        "example_shape_matches_validator_template",
        "preserved_state_assertions_retained",
    }
    missing_ready_gate_ids = [
        check["check_id"]
        for check in checks
        if check["status"] == "fail" and check["check_id"] in ready_prerequisite_check_ids
    ]

    if ingest_review_instruction_packet_ready:
        recommended_next_step = (
            "future_manual_operator_may_follow_instruction_packet_without_repo_state_mutation"
        )
        handoff_recommendation = (
            "Instruction packet is ready. Open the operator handoff bundle first, then the "
            "validator artifact, then the synthetic example reference. Keep repo_side_review_state_updated=false, "
            "reviewed_runtime_patch_exists=false, and runtime_enablement_allowed=false, and do not "
            "claim that any actual human review has already happened."
        )
    else:
        recommended_next_step = "repair_ingest_review_instruction_packet_inputs"
        handoff_recommendation = (
            "Instruction packet is blocked. Repair the missing or incompatible upstream operator "
            "handoff bundle, validator artifact, or example bundle before using this bounded packet."
        )

    return {
        "metadata": {
            "source": INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_ingest_review_instruction_packet_review_only_operator_facing_"
                "manual_path_not_executed"
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
            "ingest_review_operator_handoff_bundle": _display_path(
                project_root, ingest_review_operator_handoff_bundle_resolved
            ),
            "ingest_review_record_validator": _display_path(
                project_root, ingest_review_record_validator_resolved
            ),
            "ingest_review_record_example_bundle": _display_path(
                project_root, ingest_review_record_example_bundle_resolved
            ),
            "ingest_review_operator_handoff_bundle_script": _display_path(
                project_root, ingest_review_operator_handoff_bundle_script_resolved
            ),
            "ingest_review_record_validator_script": _display_path(
                project_root, ingest_review_record_validator_script_resolved
            ),
            "ingest_review_record_example_bundle_script": _display_path(
                project_root, ingest_review_record_example_bundle_script_resolved
            ),
            "authoritative_artifact_paths": {
                "ingest_review_operator_handoff_bundle": _display_path(
                    project_root, ingest_review_operator_handoff_bundle_resolved
                ),
                "ingest_review_record_validator": _display_path(
                    project_root, ingest_review_record_validator_resolved
                ),
                "ingest_review_record_example_bundle": _display_path(
                    project_root, ingest_review_record_example_bundle_resolved
                ),
            },
        },
        "candidate": dict(candidate),
        "status": {
            "ingest_review_instruction_packet_ready": ingest_review_instruction_packet_ready,
            "upstream_handoff_bundle_ready": upstream_handoff_bundle_ready,
            "contract_compatible": contract_compatible,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "operator_phase": "review_only_manual_ingest_review_instruction_packet",
            "missing_ready_gate_ids": missing_ready_gate_ids,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "ingest_review_instruction_packet": {
            "packet_target": {
                "operator_role": "future_manual_ingest_review_operator",
                "review_step_kind": "manual_ingest_review_instruction_packet",
                "review_step_summary": (
                    "One bounded, operator-facing instruction packet for the future manual "
                    "ingest-review path on anchor119. It tells the operator what to open first, "
                    "which paths are authoritative, which validator/example references to consult, "
                    "what to verify before stopping, and what must never be claimed or changed."
                ),
                "candidate_key": candidate_key,
                "anchor_idx": anchor_idx,
                "formulation_profile": formulation_profile,
                "review_state_kind": review_state_kind,
                "tracked_field": tracked_field,
                "record_identity": record_identity,
                "target_record_type": target_record_type,
                "scope": scope,
                "proposed_field_value_if_approved": proposed_field_value_if_approved,
                "validator_target": validator_target,
                "locked_reviewer_record_validator_target": (
                    locked_reviewer_record_validator_target
                ),
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "open_these_first": open_these_first,
            "ordered_instructions": ordered_instructions,
            "validator_reference": {
                "artifact_path": _display_path(
                    project_root, ingest_review_record_validator_resolved
                ),
                "builder_script_path": _display_path(
                    project_root, ingest_review_record_validator_script_resolved
                ),
                "artifact_ready": ingest_review_record_validator_ready,
                "validator_target": validator_target,
                "locked_reviewer_record_validator_target": (
                    locked_reviewer_record_validator_target
                ),
                "expected_completed_ingest_review_record_shape": dict(
                    validator_expected_template_payload
                ),
                "required_field_names": [
                    str(entry.get("field"))
                    for entry in validator_required_fields
                    if entry.get("field")
                ],
                "required_reviewer_statement_ids": list(
                    validator_required_reviewer_statement_ids
                ),
                "required_review_conclusion_ids": list(
                    validator_required_review_conclusion_ids
                ),
                "detail": (
                    "Use the validator artifact/script as the authoritative contract for the exact "
                    "future completed ingest-review record shape. This packet does not run the validator."
                ),
            },
            "example_reference": {
                "artifact_path": _display_path(
                    project_root, ingest_review_record_example_bundle_resolved
                ),
                "builder_script_path": _display_path(
                    project_root, ingest_review_record_example_bundle_script_resolved
                ),
                "artifact_ready": ingest_review_record_example_bundle_ready,
                "example_kind": example_bundle.get("example_kind"),
                "synthetic_example_is_reference_only": True,
                "reference_payload_field_names": sorted(example_payload.keys()),
                "replayed_validation_status": example_replayed_validation_summary.get(
                    "manual_ingest_review_record_validation_status"
                ),
                "detail": EXAMPLE_REFERENCE_ONLY_DETAIL,
            },
            "locked_handoff_path_shape": {
                "handoff_format": handoff_format,
                "handoff_dir": handoff_dir,
                "path_shape": handoff_path_shape,
                "handoff_filename_tokens": handoff_filename_tokens,
                "validator_expected_handoff_field": validator_expected_template_payload.get(
                    "reviewer_record_handoff_path"
                ),
                "detail": EXPECTED_HANDOFF_SHAPE_DETAIL,
            },
            "stop_conditions": stop_conditions,
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "proof_source": False,
                "candidate_elimination_claim": False,
                "solver_invoked": False,
                "execution_authorized": False,
                "detail": PRESERVED_STATE_DETAIL,
            },
            "forbidden_claims_or_actions": forbidden_claims_or_actions,
            "packet_notice": INSTRUCTION_PACKET_NOTICE,
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    packet = _mapping(report.get("ingest_review_instruction_packet"))
    target = _mapping(packet.get("packet_target"))
    validator_reference = _mapping(packet.get("validator_reference"))
    example_reference = _mapping(packet.get("example_reference"))
    locked_handoff_path_shape = _mapping(packet.get("locked_handoff_path_shape"))
    preserved_state = _mapping(packet.get("preserved_state_assertions"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Ingest Review Instruction Packet",
        "",
        f"- Instruction packet ready: `{status.get('ingest_review_instruction_packet_ready')}`",
        f"- Upstream handoff bundle ready: `{status.get('upstream_handoff_bundle_ready')}`",
        f"- Contract compatible: `{status.get('contract_compatible')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Operator phase: `{status.get('operator_phase')}`",
        f"- Missing ready gate ids: `{', '.join(_string_list(status.get('missing_ready_gate_ids'))) or '(none)'}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Packet notice: {packet.get('packet_notice')}",
        "",
        "## Packet Target",
        "",
        f"- Operator role: `{target.get('operator_role')}`",
        f"- Review step kind: `{target.get('review_step_kind')}`",
        f"- Record identity: `{target.get('record_identity')}`",
        f"- Target record type: `{target.get('target_record_type')}`",
        f"- Scope: `{target.get('scope')}`",
        f"- Tracked field: `{target.get('tracked_field')}`",
        f"- Proposed field value if approved: `{target.get('proposed_field_value_if_approved')}`",
        f"- Actual human review has happened: `{target.get('actual_human_review_has_happened')}`",
        f"- Execution authorized: `{target.get('execution_authorized')}`",
        "",
        "## Open These First",
        "",
        "| Order | Artifact | Path | Secondary Reference | Why |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in packet.get("open_these_first", []):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('order'))} | "
                f"{_markdown_cell(entry.get('artifact_id'))} | "
                f"{_markdown_cell(entry.get('path'))} | "
                f"{_markdown_cell(entry.get('secondary_reference'))} | "
                f"{_markdown_cell(entry.get('why'))} |"
            )
    lines.extend(
        [
            "",
            "## Ordered Instructions",
            "",
        ]
    )
    for entry in packet.get("ordered_instructions", []):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            f"{entry.get('step_index')}. `{entry.get('instruction_id')}`: {entry.get('action')}"
        )
        lines.append(f"   Verify: {', '.join(_string_list(entry.get('verify')))}")
        lines.append(f"   Stop if: {entry.get('if_not_true_stop')}")
        lines.append(f"   Detail: {entry.get('detail')}")
    lines.extend(
        [
            "",
            "## Validator Reference",
            "",
            f"- Artifact path: `{validator_reference.get('artifact_path')}`",
            f"- Builder script path: `{validator_reference.get('builder_script_path')}`",
            f"- Validator target: `{validator_reference.get('validator_target')}`",
            f"- Locked reviewer-record validator target: `{validator_reference.get('locked_reviewer_record_validator_target')}`",
            f"- Required field names: `{', '.join(_string_list(validator_reference.get('required_field_names'))) or '(none)'}`",
            f"- Required reviewer statement ids: `{', '.join(_string_list(validator_reference.get('required_reviewer_statement_ids'))) or '(none)'}`",
            f"- Required review conclusion ids: `{', '.join(_string_list(validator_reference.get('required_review_conclusion_ids'))) or '(none)'}`",
            f"- Detail: {validator_reference.get('detail')}",
            "",
            "## Example Reference",
            "",
            f"- Artifact path: `{example_reference.get('artifact_path')}`",
            f"- Builder script path: `{example_reference.get('builder_script_path')}`",
            f"- Example kind: `{example_reference.get('example_kind')}`",
            f"- Synthetic example is reference only: `{example_reference.get('synthetic_example_is_reference_only')}`",
            f"- Replayed validation status: `{example_reference.get('replayed_validation_status')}`",
            f"- Detail: {example_reference.get('detail')}",
            "",
            "## Locked Handoff Path Shape",
            "",
            f"- Handoff format: `{locked_handoff_path_shape.get('handoff_format')}`",
            f"- Handoff dir: `{locked_handoff_path_shape.get('handoff_dir')}`",
            f"- Path shape: `{locked_handoff_path_shape.get('path_shape')}`",
            f"- Filename tokens: `{', '.join(_string_list(locked_handoff_path_shape.get('handoff_filename_tokens'))) or '(none)'}`",
            f"- Validator expected handoff field: `{locked_handoff_path_shape.get('validator_expected_handoff_field')}`",
            f"- Detail: {locked_handoff_path_shape.get('detail')}",
            "",
            "## Stop Conditions",
            "",
            "| Condition | Satisfied | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for entry in packet.get("stop_conditions", []):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('condition_id'))} | "
                f"{_markdown_cell(entry.get('satisfied'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Preserved State Assertions",
            "",
            f"- repo_side_review_state_updated: `{preserved_state.get('repo_side_review_state_updated')}`",
            f"- reviewed_runtime_patch_exists: `{preserved_state.get('reviewed_runtime_patch_exists')}`",
            f"- runtime_enablement_allowed: `{preserved_state.get('runtime_enablement_allowed')}`",
            f"- proof_source: `{preserved_state.get('proof_source')}`",
            f"- candidate_elimination_claim: `{preserved_state.get('candidate_elimination_claim')}`",
            f"- solver_invoked: `{preserved_state.get('solver_invoked')}`",
            f"- execution_authorized: `{preserved_state.get('execution_authorized')}`",
            f"- Detail: {preserved_state.get('detail')}",
            "",
            "## Forbidden Claims Or Actions",
            "",
        ]
    )
    for entry in packet.get("forbidden_claims_or_actions", []):
        lines.append(f"- {entry}")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in report.get("checks", []):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    packet = _mapping(report.get("ingest_review_instruction_packet"))
    validator_reference = _mapping(packet.get("validator_reference"))
    locked_handoff_path_shape = _mapping(packet.get("locked_handoff_path_shape"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain ingest review instruction packet",
            "ingest_review_instruction_packet_ready="
            + str(status.get("ingest_review_instruction_packet_ready")),
            "upstream_handoff_bundle_ready="
            + str(status.get("upstream_handoff_bundle_ready")),
            "contract_compatible=" + str(status.get("contract_compatible")),
            "repo_side_review_state_updated="
            + str(status.get("repo_side_review_state_updated")),
            "reviewed_runtime_patch_exists="
            + str(status.get("reviewed_runtime_patch_exists")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            "validator_artifact_path=" + str(validator_reference.get("artifact_path")),
            "locked_handoff_path_shape="
            + str(locked_handoff_path_shape.get("path_shape")),
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_ingest_review_instruction_packet",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _open_reference(
    order: int,
    artifact_id: str,
    path: str,
    secondary_reference: str,
    why: str,
) -> Dict[str, Any]:
    return {
        "order": int(order),
        "artifact_id": str(artifact_id),
        "path": str(path),
        "secondary_reference": str(secondary_reference),
        "why": str(why),
    }


def _instruction(
    step_index: int,
    instruction_id: str,
    action: str,
    verify: list[str],
    if_not_true_stop: str,
    detail: str,
) -> Dict[str, Any]:
    return {
        "step_index": int(step_index),
        "instruction_id": str(instruction_id),
        "action": str(action),
        "verify": list(verify),
        "if_not_true_stop": str(if_not_true_stop),
        "detail": str(detail),
    }


def _stop_condition(condition_id: str, satisfied: bool, detail: str) -> Dict[str, Any]:
    return {
        "condition_id": str(condition_id),
        "satisfied": bool(satisfied),
        "detail": str(detail),
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


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
        if metadata.get("source") == expected_source:
            return f"present:{_display_path(project_root, path)}"
        return f"unexpected_source:{metadata.get('source')} expected:{expected_source}"
    return f"missing:{_display_path(project_root, path)}"


def _merge_gate_entries(*values: Any) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, Mapping):
                continue
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


def _review_only_contract_retained(*metadatas: Mapping[str, Any]) -> bool:
    relevant = [metadata for metadata in metadatas if metadata]
    if not relevant:
        return False
    return all(
        bool(metadata.get("review_only", False))
        and bool(metadata.get("spec_only", False))
        and bool(metadata.get("default_off", False))
        and not bool(metadata.get("runtime_precheck_enabled", False))
        and not bool(metadata.get("runtime_semantics_changed", False))
        and not bool(metadata.get("proof_source", False))
        and not bool(metadata.get("candidate_elimination_claim", False))
        and not bool(metadata.get("solver_invoked", False))
        for metadata in relevant
    )


def _locked_value(values: list[Any], *, normalize) -> tuple[Any, bool]:
    non_empty = [value for value in values if _has_value(value)]
    if not non_empty:
        return "", False
    normalized = {normalize(value) for value in non_empty}
    return non_empty[0], bool(len(non_empty) >= 2 and len(normalized) == 1)


def _locked_string_list(values: list[Any]) -> tuple[list[str], bool]:
    non_empty = [_string_list(value) for value in values if _string_list(value)]
    if not non_empty:
        return [], False
    normalized = {json.dumps(value) for value in non_empty}
    return non_empty[0], bool(len(non_empty) >= 2 and len(normalized) == 1)


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


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _normalize_path_text(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def _normalize_scalar(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


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
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False).replace("|", "\\|")
    return str(value).replace("|", "\\|").replace("\n", " ")

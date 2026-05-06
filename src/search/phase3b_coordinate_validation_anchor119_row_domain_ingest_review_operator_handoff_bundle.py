from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
)
INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
)
REVIEWER_RECORD_COLLECTION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1"
)
INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
)
DEFAULT_INGEST_REVIEW_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_20260424/"
    "anchor119_row_domain_ingest_review_record_scaffold.json"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)
DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/"
    "anchor119_row_domain_ingest_review_record_example_bundle.json"
)
DEFAULT_REVIEWER_RECORD_COLLECTION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
    "anchor119_row_domain_reviewer_record_collection.json"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_SCRIPT_PATH = Path(
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator.py"
)
DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SCRIPT_PATH = Path(
    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle.py"
)
HANDOFF_BUNDLE_NOTICE = (
    "Review-only/operator-facing handoff bundle only. This artifact explains the "
    "future manual ingest-review path on anchor119, but it does not validate any "
    "record, does not update repo-side review state, does not imply any actual "
    "human review has happened, and does not authorize execution or enablement."
)
SYNTHETIC_REFERENCE_ONLY_DETAIL = (
    "Synthetic example is reference only. It is not an actual human review "
    "record, not an actual completed ingest review, and not an applied "
    "repo-side review-state update."
)
PRESERVED_STATE_DETAIL = (
    "Preserve repo_side_review_state_updated=false, "
    "reviewed_runtime_patch_exists=false, and runtime_enablement_allowed=false "
    "throughout this handoff. Nothing in this bundle authorizes execution."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle(
    project_root: Path,
    *,
    ingest_review_record_scaffold_path: Optional[Path] = None,
    ingest_review_record_validator_path: Optional[Path] = None,
    ingest_review_record_example_bundle_path: Optional[Path] = None,
    reviewer_record_collection_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ingest_review_record_scaffold_resolved = _resolve_path(
        project_root,
        ingest_review_record_scaffold_path
        if ingest_review_record_scaffold_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_SCAFFOLD_PATH,
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
    reviewer_record_collection_resolved = _resolve_path(
        project_root,
        reviewer_record_collection_path
        if reviewer_record_collection_path is not None
        else DEFAULT_REVIEWER_RECORD_COLLECTION_PATH,
    )
    ingest_review_record_validator_script_resolved = _resolve_path(
        project_root, DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_SCRIPT_PATH
    )
    ingest_review_record_example_bundle_script_resolved = _resolve_path(
        project_root, DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SCRIPT_PATH
    )

    scaffold_report, scaffold_error = _load_json_mapping(
        ingest_review_record_scaffold_resolved
    )
    validator_report, validator_error = _load_json_mapping(
        ingest_review_record_validator_resolved
    )
    example_bundle_report, example_bundle_error = _load_json_mapping(
        ingest_review_record_example_bundle_resolved
    )
    reviewer_record_collection_report, reviewer_record_collection_error = (
        _load_json_mapping(reviewer_record_collection_resolved)
    )

    scaffold_meta = _mapping(scaffold_report.get("metadata")) if scaffold_report else {}
    scaffold_status = _mapping(scaffold_report.get("status")) if scaffold_report else {}
    scaffold = (
        _mapping(scaffold_report.get("ingest_review_record_scaffold"))
        if scaffold_report
        else {}
    )
    validator_meta = (
        _mapping(validator_report.get("metadata")) if validator_report else {}
    )
    validator_status = (
        _mapping(validator_report.get("status")) if validator_report else {}
    )
    validator = (
        _mapping(validator_report.get("ingest_review_record_validator"))
        if validator_report
        else {}
    )
    example_bundle_meta = (
        _mapping(example_bundle_report.get("metadata")) if example_bundle_report else {}
    )
    example_bundle_status = (
        _mapping(example_bundle_report.get("status")) if example_bundle_report else {}
    )
    example_bundle = (
        _mapping(example_bundle_report.get("ingest_review_record_example_bundle"))
        if example_bundle_report
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
    candidate = _first_mapping(
        scaffold_report.get("candidate") if scaffold_report else None,
        validator_report.get("candidate") if validator_report else None,
        example_bundle_report.get("candidate") if example_bundle_report else None,
        reviewer_record_collection_report.get("candidate")
        if reviewer_record_collection_report
        else None,
    )

    ingest_review_record_scaffold_present = bool(
        scaffold_report is not None
        and scaffold_error is None
        and scaffold_meta.get("source") == INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE
    )
    ingest_review_record_validator_present = bool(
        validator_report is not None
        and validator_error is None
        and validator_meta.get("source") == INGEST_REVIEW_RECORD_VALIDATOR_SOURCE
    )
    ingest_review_record_example_bundle_present = bool(
        example_bundle_report is not None
        and example_bundle_error is None
        and example_bundle_meta.get("source")
        == INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE
    )
    reviewer_record_collection_present = bool(
        reviewer_record_collection_report is not None
        and reviewer_record_collection_error is None
        and reviewer_record_collection_meta.get("source")
        == REVIEWER_RECORD_COLLECTION_SOURCE
    )

    ingest_review_record_scaffold_ready = bool(
        scaffold_status.get("ingest_review_record_scaffold_ready", False)
    )
    ingest_review_record_validator_ready = bool(
        validator_status.get("ingest_review_record_validator_ready", False)
    )
    ingest_review_record_example_bundle_ready = bool(
        example_bundle_status.get("ingest_review_record_example_bundle_ready", False)
    )
    reviewer_record_collection_ready = bool(
        reviewer_record_collection_status.get("reviewer_record_collection_ready", False)
    )
    upstream_inputs_ready = bool(
        ingest_review_record_scaffold_present
        and ingest_review_record_validator_present
        and ingest_review_record_example_bundle_present
        and reviewer_record_collection_present
        and ingest_review_record_scaffold_ready
        and ingest_review_record_validator_ready
        and ingest_review_record_example_bundle_ready
        and reviewer_record_collection_ready
    )

    scaffold_target = _mapping(scaffold.get("locked_target_review_state"))
    validator_target = _mapping(validator.get("locked_target_review_state"))
    example_bundle_target = _mapping(example_bundle.get("locked_target_review_state"))
    reviewer_record_collection_target = _mapping(
        reviewer_record_collection.get("target_record_identity")
    )

    scaffold_handoff = _mapping(scaffold.get("locked_reviewer_record_handoff"))
    validator_handoff = _mapping(validator.get("locked_reviewer_record_handoff"))
    example_bundle_handoff = _mapping(example_bundle.get("locked_reviewer_record_handoff"))
    reviewer_record_collection_handoff = _mapping(
        reviewer_record_collection.get("expected_handoff")
    )

    scaffold_blocked_gates = _mapping(scaffold.get("preserved_blocked_gates"))
    validator_blocked_gate_contract = _mapping(validator.get("blocked_gate_contract"))
    example_payload = _mapping(
        example_bundle.get("synthetic_completed_ingest_review_record_payload")
    )
    reviewer_record_collection_preserved_contract = _mapping(
        reviewer_record_collection.get("preserved_contract")
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            _mapping(scaffold_report.get("candidate")).get("key")
            if scaffold_report
            else None,
            _mapping(validator_report.get("candidate")).get("key")
            if validator_report
            else None,
            _mapping(example_bundle_report.get("candidate")).get("key")
            if example_bundle_report
            else None,
            _mapping(reviewer_record_collection_report.get("candidate")).get("key")
            if reviewer_record_collection_report
            else None,
        ],
        normalize=_normalize_text,
    )
    anchor_idx, anchor_idx_locked = _locked_value(
        [
            _mapping(scaffold_report.get("candidate")).get("anchor_idx")
            if scaffold_report
            else None,
            _mapping(validator_report.get("candidate")).get("anchor_idx")
            if validator_report
            else None,
            _mapping(example_bundle_report.get("candidate")).get("anchor_idx")
            if example_bundle_report
            else None,
            _mapping(reviewer_record_collection_report.get("candidate")).get("anchor_idx")
            if reviewer_record_collection_report
            else None,
        ],
        normalize=_normalize_scalar,
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            _mapping(scaffold_report.get("candidate")).get("formulation_profile")
            if scaffold_report
            else None,
            _mapping(validator_report.get("candidate")).get("formulation_profile")
            if validator_report
            else None,
            _mapping(example_bundle_report.get("candidate")).get("formulation_profile")
            if example_bundle_report
            else None,
            _mapping(reviewer_record_collection_report.get("candidate")).get(
                "formulation_profile"
            )
            if reviewer_record_collection_report
            else None,
        ],
        normalize=_normalize_text,
    )
    candidate_consistent = bool(
        candidate_key_locked and anchor_idx_locked and formulation_profile_locked
    )

    review_state_kind, review_state_kind_locked = _locked_value(
        [
            scaffold_target.get("review_state_kind"),
            validator_target.get("review_state_kind"),
            example_bundle_target.get("review_state_kind"),
        ],
        normalize=_normalize_text,
    )
    tracked_field, tracked_field_locked = _locked_value(
        [
            scaffold_target.get("tracked_field"),
            validator_target.get("tracked_field"),
            example_bundle_target.get("tracked_field"),
        ],
        normalize=_normalize_text,
    )
    record_identity, record_identity_locked = _locked_value(
        [
            scaffold_target.get("record_identity"),
            validator_target.get("record_identity"),
            example_bundle_target.get("record_identity"),
            reviewer_record_collection_target.get("record_identity"),
        ],
        normalize=_normalize_text,
    )
    target_record_type, target_record_type_locked = _locked_value(
        [
            scaffold_target.get("record_type"),
            validator_target.get("record_type"),
            example_bundle_target.get("record_type"),
            reviewer_record_collection_target.get("record_type"),
        ],
        normalize=_normalize_text,
    )
    scope, scope_locked = _locked_value(
        [
            scaffold_target.get("scope"),
            validator_target.get("scope"),
            example_bundle_target.get("scope"),
            reviewer_record_collection_target.get("scope"),
        ],
        normalize=_normalize_text,
    )
    proposed_field_value_if_approved, proposed_field_value_if_approved_locked = (
        _locked_value(
            [
                scaffold_target.get("proposed_field_value_if_approved"),
                validator_target.get("proposed_field_value_if_approved"),
                example_bundle_target.get("proposed_field_value_if_approved"),
            ],
            normalize=_normalize_scalar,
        )
    )
    current_field_value_is_false = not any(
        bool(value)
        for value in [
            scaffold_target.get("current_field_value", False),
            validator_target.get("current_field_value", False),
            example_bundle_target.get("current_field_value", False),
        ]
    )
    locked_target_review_state_consistent = bool(
        review_state_kind_locked
        and tracked_field_locked
        and record_identity_locked
        and target_record_type_locked
        and scope_locked
        and proposed_field_value_if_approved_locked
        and current_field_value_is_false
    )

    handoff_format, handoff_format_locked = _locked_value(
        [
            scaffold_handoff.get("handoff_format"),
            validator_handoff.get("handoff_format"),
            example_bundle_handoff.get("handoff_format"),
            reviewer_record_collection_handoff.get("handoff_format"),
        ],
        normalize=_normalize_text,
    )
    handoff_dir, handoff_dir_locked = _locked_value(
        [
            scaffold_handoff.get("handoff_dir"),
            validator_handoff.get("handoff_dir"),
            example_bundle_handoff.get("handoff_dir"),
            reviewer_record_collection_handoff.get("handoff_dir"),
        ],
        normalize=_normalize_path_text,
    )
    handoff_path_shape, handoff_path_shape_locked = _locked_value(
        [
            scaffold_handoff.get("handoff_path_shape"),
            validator_handoff.get("handoff_path_shape"),
            example_bundle_handoff.get("handoff_path_shape"),
            reviewer_record_collection_handoff.get("handoff_path_shape"),
        ],
        normalize=_normalize_path_text,
    )
    handoff_filename_tokens, handoff_filename_tokens_locked = _locked_string_list(
        [
            scaffold_handoff.get("handoff_filename_tokens"),
            validator_handoff.get("handoff_filename_tokens"),
            example_bundle_handoff.get("handoff_filename_tokens"),
            reviewer_record_collection_handoff.get("handoff_filename_tokens"),
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

    current_still_blocked_gate_ids, current_still_blocked_gate_ids_locked = (
        _locked_string_list(
            [
                scaffold_blocked_gates.get("current_still_blocked_gate_ids"),
                validator_blocked_gate_contract.get("current_still_blocked_gate_ids"),
                example_payload.get("current_still_blocked_gate_ids"),
                reviewer_record_collection_preserved_contract.get("still_blocked_gate_ids"),
            ]
        )
    )
    post_ingest_still_blocked_gate_ids, post_ingest_still_blocked_gate_ids_locked = (
        _locked_string_list(
            [
                scaffold_blocked_gates.get("post_ingest_still_blocked_gate_ids"),
                validator_blocked_gate_contract.get("post_ingest_still_blocked_gate_ids"),
                example_payload.get("post_ingest_still_blocked_gate_ids"),
            ]
        )
    )
    blocked_gate_contract_consistent = bool(
        current_still_blocked_gate_ids_locked
        and post_ingest_still_blocked_gate_ids_locked
        and current_still_blocked_gate_ids
        and post_ingest_still_blocked_gate_ids
    )

    ingest_review_validator_target, ingest_review_validator_target_locked = (
        _locked_value(
            [
                validator.get("validator_target"),
                example_bundle.get("validator_target"),
            ],
            normalize=_normalize_text,
        )
    )
    reviewer_record_validator_target, reviewer_record_validator_target_locked = (
        _locked_value(
            [
                _mapping(scaffold.get("validator_contract_reference")).get(
                    "validator_target"
                ),
                validator.get("locked_reviewer_record_validator_target"),
            ],
            normalize=_normalize_text,
        )
    )
    validator_reference_consistent = bool(
        ingest_review_validator_target_locked
        and reviewer_record_validator_target_locked
        and ingest_review_validator_target
        and reviewer_record_validator_target
    )

    review_only_contract_retained = _review_only_contract_retained(
        scaffold_meta,
        validator_meta,
        example_bundle_meta,
        reviewer_record_collection_meta,
    )
    repo_side_review_state_unchanged = not any(
        bool(value)
        for value in [
            scaffold_meta.get("repo_side_review_state_updated", False),
            validator_meta.get("repo_side_review_state_updated", False),
            example_bundle_meta.get("repo_side_review_state_updated", False),
            scaffold_status.get("repo_side_review_state_updated", False),
            validator_status.get("repo_side_review_state_updated", False),
            example_bundle_status.get("repo_side_review_state_updated", False),
            example_bundle.get("applied_repo_state_update", False),
        ]
    )
    reviewed_runtime_patch_exists_false = not any(
        bool(value)
        for value in [
            scaffold_status.get("reviewed_runtime_patch_exists", False),
            validator_status.get("reviewed_runtime_patch_exists", False),
            example_bundle_status.get("reviewed_runtime_patch_exists", False),
            reviewer_record_collection_status.get("reviewed_runtime_patch_exists", False),
            scaffold_target.get("current_field_value", False),
            example_payload.get("reviewed_runtime_patch_exists", False),
            _mapping(reviewer_record_collection.get("collection_state")).get(
                "reviewed_runtime_patch_exists", False
            ),
        ]
    )
    runtime_enablement_allowed_false = not any(
        bool(value)
        for value in [
            scaffold_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
            example_bundle_status.get("runtime_enablement_allowed", False),
            reviewer_record_collection_status.get("runtime_enablement_allowed", False),
            example_payload.get("runtime_enablement_allowed", False),
            _mapping(reviewer_record_collection.get("collection_state")).get(
                "runtime_enablement_allowed", False
            ),
        ]
    )
    actual_human_review_not_claimed = not any(
        bool(value)
        for value in [
            validator_status.get("manual_ingest_review_record_provided", False),
            validator_status.get("manual_ingest_review_record_validated", False),
            example_bundle.get("actual_human_review_record", False),
            reviewer_record_collection_status.get("actual_reviewer_record_collected", False),
            _mapping(reviewer_record_collection.get("collection_state")).get(
                "actual_record_collected", False
            ),
            _mapping(reviewer_record_collection.get("collection_state")).get(
                "reviewer_signed_record_present", False
            ),
        ]
    )
    synthetic_example_reference_only = bool(
        ingest_review_record_example_bundle_present
        and ingest_review_record_example_bundle_ready
        and "synthetic" in str(example_bundle.get("example_kind") or "").lower()
        and not bool(example_bundle.get("actual_human_review_record", False))
        and not bool(example_bundle.get("applied_repo_state_update", False))
    )
    execution_authorization_not_implied = runtime_enablement_allowed_false
    preserved_state_assertions_retained = bool(
        repo_side_review_state_unchanged
        and reviewed_runtime_patch_exists_false
        and runtime_enablement_allowed_false
        and actual_human_review_not_claimed
        and execution_authorization_not_implied
    )

    contract_compatible = bool(
        candidate_consistent
        and locked_target_review_state_consistent
        and locked_handoff_path_shape_consistent
        and blocked_gate_contract_consistent
        and validator_reference_consistent
        and review_only_contract_retained
        and preserved_state_assertions_retained
        and synthetic_example_reference_only
    )
    ingest_review_operator_handoff_bundle_ready = bool(
        upstream_inputs_ready and contract_compatible
    )

    authoritative_inputs = [
        _authoritative_input(
            artifact_id="ingest_review_record_scaffold",
            project_root=project_root,
            path=ingest_review_record_scaffold_resolved,
            required_source=INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE,
            required_ready_status="ingest_review_record_scaffold_ready",
            present=ingest_review_record_scaffold_present,
            ready=ingest_review_record_scaffold_ready,
            role=(
                "Defines the locked target review-state identity, the future manual "
                "ingest-review conclusions, and the preserved post-review state."
            ),
            detail=_presence_detail(
                scaffold_report,
                scaffold_error,
                scaffold_meta,
                INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE,
                project_root,
                ingest_review_record_scaffold_resolved,
            ),
        ),
        _authoritative_input(
            artifact_id="ingest_review_record_validator",
            project_root=project_root,
            path=ingest_review_record_validator_resolved,
            required_source=INGEST_REVIEW_RECORD_VALIDATOR_SOURCE,
            required_ready_status="ingest_review_record_validator_ready",
            present=ingest_review_record_validator_present,
            ready=ingest_review_record_validator_ready,
            role=(
                "Locks the future completed ingest-review record contract and is the "
                "primary validator reference for the operator."
            ),
            detail=_presence_detail(
                validator_report,
                validator_error,
                validator_meta,
                INGEST_REVIEW_RECORD_VALIDATOR_SOURCE,
                project_root,
                ingest_review_record_validator_resolved,
            ),
        ),
        _authoritative_input(
            artifact_id="ingest_review_record_example_bundle",
            project_root=project_root,
            path=ingest_review_record_example_bundle_resolved,
            required_source=INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
            required_ready_status="ingest_review_record_example_bundle_ready",
            present=ingest_review_record_example_bundle_present,
            ready=ingest_review_record_example_bundle_ready,
            role=(
                "Provides a synthetic reference bundle that shows the intended review "
                "shape without representing a real human review."
            ),
            detail=SYNTHETIC_REFERENCE_ONLY_DETAIL,
            reference_only=True,
        ),
        _authoritative_input(
            artifact_id="reviewer_record_collection",
            project_root=project_root,
            path=reviewer_record_collection_resolved,
            required_source=REVIEWER_RECORD_COLLECTION_SOURCE,
            required_ready_status="reviewer_record_collection_ready",
            present=reviewer_record_collection_present,
            ready=reviewer_record_collection_ready,
            role=(
                "Defines where the future real reviewer-signed record must be dropped "
                "and preserves the reviewer-side handoff contract."
            ),
            detail=_presence_detail(
                reviewer_record_collection_report,
                reviewer_record_collection_error,
                reviewer_record_collection_meta,
                REVIEWER_RECORD_COLLECTION_SOURCE,
                project_root,
                reviewer_record_collection_resolved,
            ),
        ),
    ]

    ordered_steps = [
        {
            "step_index": 1,
            "step_id": "read_locked_review_step_contract",
            "action": "Read the locked ingest-review scaffold and validator first.",
            "detail": (
                "This step is a future manual ingest-review handoff for "
                f"`{record_identity}`. It remains review-only/spec-only/default-off "
                "and does not validate or ingest anything by itself."
            ),
        },
        {
            "step_index": 2,
            "step_id": "locate_future_real_reviewer_record",
            "action": "Use the reviewer-record collection artifact to find the real reviewer record path.",
            "detail": (
                "The future real reviewer-signed record must be handed off as JSON at "
                f"`{handoff_path_shape}`. Do not treat a different path or filename "
                "shape as the locked handoff target."
            ),
        },
        {
            "step_index": 3,
            "step_id": "use_locked_validator_reference",
            "action": "Use the existing ingest-review validator as the contract reference.",
            "detail": (
                f"Reference `{_display_path(project_root, ingest_review_record_validator_resolved)}` "
                f"or `{_display_path(project_root, ingest_review_record_validator_script_resolved)}` "
                "for the future completed ingest-review record contract. This bundle "
                "does not run the validator."
            ),
        },
        {
            "step_index": 4,
            "step_id": "use_synthetic_example_reference_only",
            "action": "Use the existing example bundle only as a synthetic reference.",
            "detail": (
                f"Reference `{_display_path(project_root, ingest_review_record_example_bundle_resolved)}` "
                f"or `{_display_path(project_root, ingest_review_record_example_bundle_script_resolved)}` "
                "only to understand the locked review shape. Synthetic example is "
                "reference only and must not be treated as a real human review."
            ),
        },
        {
            "step_index": 5,
            "step_id": "preserve_state_and_blocked_gates",
            "action": "Keep the preserved state and blocked gates unchanged.",
            "detail": (
                "Keep repo_side_review_state_updated=false, "
                "reviewed_runtime_patch_exists=false, "
                "runtime_enablement_allowed=false, and carry forward still_blocked_gate_ids="
                f"`{', '.join(current_still_blocked_gate_ids)}` until a later separate "
                "manual review path completes."
            ),
        },
    ]

    gates = _merge_gate_entries(
        scaffold_report.get("gates") if scaffold_report else None,
        validator_report.get("gates") if validator_report else None,
        example_bundle_report.get("gates") if example_bundle_report else None,
        reviewer_record_collection_report.get("gates")
        if reviewer_record_collection_report
        else None,
    )
    gate_ids = {
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping) and gate.get("gate_id")
    }
    for gate_id in current_still_blocked_gate_ids:
        if gate_id not in gate_ids:
            gates.append(
                _gate(
                    gate_id,
                    False,
                    True,
                    "Still-blocked gate carried forward into the future manual ingest-review handoff.",
                )
            )

    checks = [
        _check(
            "ingest_review_record_scaffold_present",
            "pass" if ingest_review_record_scaffold_present else "fail",
            _presence_detail(
                scaffold_report,
                scaffold_error,
                scaffold_meta,
                INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE,
                project_root,
                ingest_review_record_scaffold_resolved,
            ),
        ),
        _check(
            "ingest_review_record_scaffold_ready",
            "pass" if ingest_review_record_scaffold_ready else "fail",
            "ingest_review_record_scaffold_ready=true"
            if ingest_review_record_scaffold_ready
            else "ingest_review_record_scaffold_ready=false",
        ),
        _check(
            "ingest_review_record_validator_present",
            "pass" if ingest_review_record_validator_present else "fail",
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
            "pass" if ingest_review_record_example_bundle_present else "fail",
            _presence_detail(
                example_bundle_report,
                example_bundle_error,
                example_bundle_meta,
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
            "reviewer_record_collection_present",
            "pass" if reviewer_record_collection_present else "fail",
            _presence_detail(
                reviewer_record_collection_report,
                reviewer_record_collection_error,
                reviewer_record_collection_meta,
                REVIEWER_RECORD_COLLECTION_SOURCE,
                project_root,
                reviewer_record_collection_resolved,
            ),
        ),
        _check(
            "reviewer_record_collection_ready",
            "pass" if reviewer_record_collection_ready else "fail",
            "reviewer_record_collection_ready=true"
            if reviewer_record_collection_ready
            else "reviewer_record_collection_ready=false",
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "All upstream artifacts retain review_only/spec_only/default_off and "
            "keep proof_source=false, candidate_elimination_claim=false, and solver_invoked=false."
            if review_only_contract_retained
            else "At least one upstream artifact drifted away from the review-only/default-off contract.",
        ),
        _check(
            "candidate_consistent",
            "pass" if candidate_consistent else "fail",
            "Candidate key, anchor_idx, and formulation_profile are locked across the upstream artifacts."
            if candidate_consistent
            else "Candidate identity mismatch across the upstream artifacts.",
        ),
        _check(
            "locked_target_review_state_consistent",
            "pass" if locked_target_review_state_consistent else "fail",
            "Locked target review-state identity, tracked field, scope, and proposed field value agree across scaffold/validator/example inputs."
            if locked_target_review_state_consistent
            else "Locked target review-state contract mismatch across the upstream artifacts.",
        ),
        _check(
            "locked_handoff_path_shape_consistent",
            "pass" if locked_handoff_path_shape_consistent else "fail",
            "Locked handoff format, directory, path shape, and filename tokens agree across scaffold/validator/example/collection inputs."
            if locked_handoff_path_shape_consistent
            else "Locked handoff path shape mismatch across the upstream artifacts.",
        ),
        _check(
            "blocked_gate_contract_consistent",
            "pass" if blocked_gate_contract_consistent else "fail",
            "Current and post-ingest still-blocked gate ids agree across the upstream artifacts."
            if blocked_gate_contract_consistent
            else "Blocked-gate contract mismatch across the upstream artifacts.",
        ),
        _check(
            "validator_reference_consistent",
            "pass" if validator_reference_consistent else "fail",
            "The ingest-review validator target and the reviewer-record validator target are both locked."
            if validator_reference_consistent
            else "Validator reference mismatch across the upstream artifacts.",
        ),
        _check(
            "preserved_state_assertions_retained",
            "pass" if preserved_state_assertions_retained else "fail",
            "repo_side_review_state_updated=false, reviewed_runtime_patch_exists=false, "
            "runtime_enablement_allowed=false, and no actual human review is claimed."
            if preserved_state_assertions_retained
            else "An upstream artifact implies repo-state mutation, actual review completion, or enablement.",
        ),
        _check(
            "synthetic_example_reference_only",
            "pass" if synthetic_example_reference_only else "fail",
            SYNTHETIC_REFERENCE_ONLY_DETAIL
            if synthetic_example_reference_only
            else "The example bundle no longer reads as a synthetic/reference-only artifact.",
        ),
    ]
    ready_prerequisite_check_ids = {
        "ingest_review_record_scaffold_present",
        "ingest_review_record_scaffold_ready",
        "ingest_review_record_validator_present",
        "ingest_review_record_validator_ready",
        "ingest_review_record_example_bundle_present",
        "ingest_review_record_example_bundle_ready",
        "reviewer_record_collection_present",
        "reviewer_record_collection_ready",
        "review_only_contract_retained",
        "candidate_consistent",
        "locked_target_review_state_consistent",
        "locked_handoff_path_shape_consistent",
        "blocked_gate_contract_consistent",
        "validator_reference_consistent",
        "preserved_state_assertions_retained",
        "synthetic_example_reference_only",
    }
    missing_ready_gate_ids = [
        check["check_id"]
        for check in checks
        if check["status"] == "fail" and check["check_id"] in ready_prerequisite_check_ids
    ]

    recommended_next_step = (
        "hand_bundle_to_future_manual_ingest_review_operator_keep_repo_state_unchanged"
    )
    handoff_recommendation = (
        "Operator handoff bundle is ready only when the upstream scaffold, validator, "
        "example bundle, and reviewer-record collection are present, ready, and "
        "contract-compatible. Use the listed inputs as locked references, wait for the "
        "real reviewer-signed record at the locked handoff path shape, and keep "
        "repo_side_review_state_updated=false, reviewed_runtime_patch_exists=false, "
        "and runtime_enablement_allowed=false throughout this handoff."
    )

    return {
        "metadata": {
            "source": INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_ingest_review_operator_handoff_bundle_review_only_contract_"
                "not_actual_ingest_review"
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
            "ingest_review_record_validator": _display_path(
                project_root, ingest_review_record_validator_resolved
            ),
            "ingest_review_record_example_bundle": _display_path(
                project_root, ingest_review_record_example_bundle_resolved
            ),
            "reviewer_record_collection": _display_path(
                project_root, reviewer_record_collection_resolved
            ),
            "ingest_review_record_validator_script": _display_path(
                project_root, ingest_review_record_validator_script_resolved
            ),
            "ingest_review_record_example_bundle_script": _display_path(
                project_root, ingest_review_record_example_bundle_script_resolved
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "ingest_review_operator_handoff_bundle_ready": ingest_review_operator_handoff_bundle_ready,
            "upstream_inputs_ready": upstream_inputs_ready,
            "contract_compatible": contract_compatible,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "operator_phase": "review_only_handoff_contract_only",
            "missing_ready_gate_ids": missing_ready_gate_ids,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "ingest_review_operator_handoff_bundle": {
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "operator_target": {
                "operator_role": "future_manual_ingest_review_operator",
                "review_step_kind": "manual_ingest_review_handoff",
                "review_step_summary": (
                    "Operator-facing handoff for the future manual ingest-review path "
                    "on anchor119. It tells the operator which locked artifacts to "
                    "read, where the future real reviewer record must go, and which "
                    "validator/example references apply."
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
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "authoritative_inputs": authoritative_inputs,
            "ordered_steps": ordered_steps,
            "locked_handoff_path_shape": {
                "handoff_format": handoff_format,
                "handoff_dir": handoff_dir,
                "path_shape": handoff_path_shape,
                "handoff_filename_tokens": handoff_filename_tokens,
                "detail": (
                    "This is the locked file-based destination for the future real "
                    "reviewer-signed record. The operator handoff does not write it."
                ),
            },
            "validator_script_or_artifact_reference": {
                "artifact_path": _display_path(
                    project_root, ingest_review_record_validator_resolved
                ),
                "builder_script_path": _display_path(
                    project_root, ingest_review_record_validator_script_resolved
                ),
                "artifact_ready": ingest_review_record_validator_ready,
                "validator_target": ingest_review_validator_target,
                "future_reviewer_record_validator_target": reviewer_record_validator_target,
                "builder_script_exists": ingest_review_record_validator_script_resolved.exists(),
                "detail": (
                    "Use the ingest-review record validator artifact/script as the "
                    "locked reference for the future completed ingest-review record. "
                    "This bundle does not validate or ingest anything."
                ),
            },
            "example_bundle_reference": {
                "artifact_path": _display_path(
                    project_root, ingest_review_record_example_bundle_resolved
                ),
                "builder_script_path": _display_path(
                    project_root, ingest_review_record_example_bundle_script_resolved
                ),
                "artifact_ready": ingest_review_record_example_bundle_ready,
                "example_kind": example_bundle.get("example_kind"),
                "synthetic_example_is_reference_only": True,
                "builder_script_exists": ingest_review_record_example_bundle_script_resolved.exists(),
                "detail": SYNTHETIC_REFERENCE_ONLY_DETAIL,
            },
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
            "explicit_non_goals": [
                "Do not treat this bundle as an actual completed ingest review.",
                "Do not claim that a real reviewer-signed record has already been provided.",
                "Do not update repo-side review state from this bundle.",
                "Do not imply reviewed_runtime_patch_exists=true.",
                "Do not imply runtime_enablement_allowed=true or any execution authorization.",
            ],
            "disallowed_actions": [
                "Do not treat the synthetic example bundle as proof that any human review happened.",
                "Do not run solver-backed search or claim candidate elimination from this bundle.",
                "Do not mutate repo-side review state or runtime enablement state here.",
                "Do not bypass the locked handoff path shape for the future reviewer record.",
            ],
            "handoff_notice": HANDOFF_BUNDLE_NOTICE,
        },
        "still_blocked_gate_ids": list(current_still_blocked_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("ingest_review_operator_handoff_bundle"))
    operator_target = _mapping(bundle.get("operator_target"))
    locked_handoff_path_shape = _mapping(bundle.get("locked_handoff_path_shape"))
    validator_reference = _mapping(bundle.get("validator_script_or_artifact_reference"))
    example_reference = _mapping(bundle.get("example_bundle_reference"))
    preserved_state = _mapping(bundle.get("preserved_state_assertions"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Ingest Review Operator Handoff Bundle",
        "",
        f"- Bundle ready: `{status.get('ingest_review_operator_handoff_bundle_ready')}`",
        f"- Upstream inputs ready: `{status.get('upstream_inputs_ready')}`",
        f"- Contract compatible: `{status.get('contract_compatible')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Operator phase: `{status.get('operator_phase')}`",
        f"- Missing ready gate ids: `{', '.join(_string_list(status.get('missing_ready_gate_ids'))) or '(none)'}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Handoff notice: {bundle.get('handoff_notice')}",
        "",
        "## Operator Target",
        "",
        f"- Operator role: `{operator_target.get('operator_role')}`",
        f"- Review step kind: `{operator_target.get('review_step_kind')}`",
        f"- Review step summary: {operator_target.get('review_step_summary')}",
        f"- Record identity: `{operator_target.get('record_identity')}`",
        f"- Target record type: `{operator_target.get('target_record_type')}`",
        f"- Scope: `{operator_target.get('scope')}`",
        f"- Tracked field: `{operator_target.get('tracked_field')}`",
        f"- Proposed field value if approved: `{operator_target.get('proposed_field_value_if_approved')}`",
        f"- Actual human review has happened: `{operator_target.get('actual_human_review_has_happened')}`",
        f"- Execution authorized: `{operator_target.get('execution_authorized')}`",
        "",
        "## Authoritative Inputs",
        "",
        "| Artifact | Ready | Path | Role |",
        "| --- | --- | --- | --- |",
    ]
    for entry in bundle.get("authoritative_inputs", []):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('artifact_id'))} | "
                f"{_markdown_cell(entry.get('ready'))} | "
                f"{_markdown_cell(entry.get('path'))} | "
                f"{_markdown_cell(entry.get('role'))} |"
            )
    lines.extend(
        [
            "",
            "## Ordered Steps",
            "",
        ]
    )
    for step in bundle.get("ordered_steps", []):
        if isinstance(step, Mapping):
            lines.append(
                f"{step.get('step_index')}. `{step.get('step_id')}`: {step.get('action')} "
                f"{step.get('detail')}"
            )
    lines.extend(
        [
            "",
            "## Locked Handoff Path",
            "",
            f"- Handoff format: `{locked_handoff_path_shape.get('handoff_format')}`",
            f"- Handoff dir: `{locked_handoff_path_shape.get('handoff_dir')}`",
            f"- Path shape: `{locked_handoff_path_shape.get('path_shape')}`",
            f"- Filename tokens: `{', '.join(_string_list(locked_handoff_path_shape.get('handoff_filename_tokens'))) or '(none)'}`",
            f"- Detail: {locked_handoff_path_shape.get('detail')}",
            "",
            "## Validator And Example References",
            "",
            f"- Validator artifact path: `{validator_reference.get('artifact_path')}`",
            f"- Validator script path: `{validator_reference.get('builder_script_path')}`",
            f"- Validator target: `{validator_reference.get('validator_target')}`",
            f"- Future reviewer record validator target: `{validator_reference.get('future_reviewer_record_validator_target')}`",
            f"- Validator detail: {validator_reference.get('detail')}",
            f"- Example bundle artifact path: `{example_reference.get('artifact_path')}`",
            f"- Example bundle script path: `{example_reference.get('builder_script_path')}`",
            f"- Example kind: `{example_reference.get('example_kind')}`",
            f"- Synthetic example is reference only: `{example_reference.get('synthetic_example_is_reference_only')}`",
            f"- Example detail: {example_reference.get('detail')}",
            "",
            "## Preserved State",
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
            "## Disallowed Actions",
            "",
        ]
    )
    for item in bundle.get("disallowed_actions", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Satisfied | Blocking | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for gate in report.get("gates", []):
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
    for check in report.get("checks", []):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("ingest_review_operator_handoff_bundle"))
    locked_handoff_path_shape = _mapping(bundle.get("locked_handoff_path_shape"))
    validator_reference = _mapping(bundle.get("validator_script_or_artifact_reference"))
    example_reference = _mapping(bundle.get("example_bundle_reference"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain ingest review operator handoff bundle",
            "ingest_review_operator_handoff_bundle_ready="
            + str(status.get("ingest_review_operator_handoff_bundle_ready")),
            "upstream_inputs_ready=" + str(status.get("upstream_inputs_ready")),
            "contract_compatible=" + str(status.get("contract_compatible")),
            "repo_side_review_state_updated="
            + str(status.get("repo_side_review_state_updated")),
            "reviewed_runtime_patch_exists="
            + str(status.get("reviewed_runtime_patch_exists")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            "validator_artifact_path=" + str(validator_reference.get("artifact_path")),
            "example_bundle_artifact_path=" + str(example_reference.get("artifact_path")),
            "locked_handoff_path_shape="
            + str(locked_handoff_path_shape.get("path_shape")),
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_ingest_review_operator_handoff_bundle",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _authoritative_input(
    *,
    artifact_id: str,
    project_root: Path,
    path: Path,
    required_source: str,
    required_ready_status: str,
    present: bool,
    ready: bool,
    role: str,
    detail: str,
    reference_only: bool = False,
) -> Dict[str, Any]:
    return {
        "artifact_id": str(artifact_id),
        "path": _display_path(project_root, path),
        "required_source": str(required_source),
        "required_ready_status": str(required_ready_status),
        "present": bool(present),
        "ready": bool(ready),
        "reference_only": bool(reference_only),
        "role": str(role),
        "detail": str(detail),
    }


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


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


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
    return str(value).replace("\\", "/").strip()


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

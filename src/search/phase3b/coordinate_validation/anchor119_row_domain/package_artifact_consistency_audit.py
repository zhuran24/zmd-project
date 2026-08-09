from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

PACKAGE_ARTIFACT_CONSISTENCY_AUDIT_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_v1"
)
MANUAL_REVIEW_PACKAGE_INDEX_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_v1"
)
FINAL_HUMAN_HANDOFF_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_v1"
)
DELIVERY_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_delivery_note_v1"
)
GUARDED_PRECHECK_SPEC_SOURCE = "phase3b_anchor119_guarded_precheck_spec_v1"
STARTLINE_MANIFEST_SOURCE = "phase3b_startline_manifest_v1"
B5A_OPERATOR_SUMMARY_SOURCE = "phase3b_b5_anchor_sprint_summary_v1"

DEFAULT_MANUAL_REVIEW_PACKAGE_INDEX_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_20260424/"
    "anchor119_row_domain_manual_review_package_index.json"
)
DEFAULT_FINAL_HUMAN_HANDOFF_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_20260424/"
    "anchor119_row_domain_final_human_handoff_note.json"
)
DEFAULT_DELIVERY_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_delivery_note_20260424/"
    "anchor119_row_domain_delivery_note.json"
)
DEFAULT_GUARDED_PRECHECK_SPEC_PATH = Path(
    ".artifacts/phase3b_anchor119_guarded_precheck_spec_20260424/"
    "guarded_precheck_spec.json"
)
DEFAULT_STARTLINE_MANIFEST_PATH = Path(
    ".artifacts/phase3b_startline/startline_manifest.json"
)
DEFAULT_B5A_OPERATOR_SUMMARY_PATH = Path(
    ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json"
)

EXPECTED_BRANCH_IDS = ["ingest_review", "acceptance_authorization"]
EXPECTED_TRUE_METADATA_FIELDS = [
    "review_only",
    "spec_only",
    "default_off",
    "no_solve",
]
EXPECTED_FALSE_METADATA_FIELDS = [
    "proof_source",
    "candidate_elimination_claim",
    "solver_invoked",
    "repo_side_review_state_updated",
]
EXPECTED_STRICT_FALSE_STATE_IDS = [
    "repo_side_review_state_updated",
    "reviewed_runtime_patch_exists",
    "runtime_enablement_allowed",
    "proof_source",
    "candidate_elimination_claim",
    "solver_invoked",
    "actual_human_review_has_happened",
    "execution_authorized",
    "future_manual_acceptance_authorization_review_prerequisites_met",
    "acceptance_execution_authorized",
    "acceptance_executed",
    "actual_human_authorization_review_happened",
]
DEFAULT_NON_AUTHORIZING_NOTICE = (
    "Review-only/spec-only/default-off/no-solve audit only. This audit compares "
    "existing package artifacts only. It does not update repo-side review state, "
    "does not imply reviewed_runtime_patch_exists=true, does not imply "
    "runtime_enablement_allowed=true, does not authorize execution, and does not "
    "imply any actual human review has already happened."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
    project_root: Path,
    *,
    manual_review_package_index_path: Optional[Path] = None,
    final_human_handoff_note_path: Optional[Path] = None,
    delivery_note_path: Optional[Path] = None,
    guarded_precheck_spec_path: Optional[Path] = None,
    startline_manifest_path: Optional[Path] = None,
    b5a_operator_summary_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()

    package_index_resolved = _resolve_path(
        project_root,
        manual_review_package_index_path
        if manual_review_package_index_path is not None
        else DEFAULT_MANUAL_REVIEW_PACKAGE_INDEX_PATH,
    )
    final_handoff_resolved = _resolve_path(
        project_root,
        final_human_handoff_note_path
        if final_human_handoff_note_path is not None
        else DEFAULT_FINAL_HUMAN_HANDOFF_NOTE_PATH,
    )
    delivery_note_resolved = _resolve_path(
        project_root,
        delivery_note_path
        if delivery_note_path is not None
        else DEFAULT_DELIVERY_NOTE_PATH,
    )
    guarded_precheck_spec_resolved = _resolve_path(
        project_root,
        guarded_precheck_spec_path
        if guarded_precheck_spec_path is not None
        else DEFAULT_GUARDED_PRECHECK_SPEC_PATH,
    )
    startline_manifest_resolved = _resolve_path(
        project_root,
        startline_manifest_path
        if startline_manifest_path is not None
        else DEFAULT_STARTLINE_MANIFEST_PATH,
    )
    b5a_operator_summary_resolved = _resolve_path(
        project_root,
        b5a_operator_summary_path
        if b5a_operator_summary_path is not None
        else DEFAULT_B5A_OPERATOR_SUMMARY_PATH,
    )

    package_index_report, package_index_error = _load_json_mapping(
        package_index_resolved
    )
    final_handoff_report, final_handoff_error = _load_json_mapping(
        final_handoff_resolved
    )
    delivery_note_report, delivery_note_error = _load_json_mapping(delivery_note_resolved)
    guarded_precheck_spec_report, guarded_precheck_spec_error = _load_json_mapping(
        guarded_precheck_spec_resolved
    )
    startline_manifest_report, startline_manifest_error = _load_json_mapping(
        startline_manifest_resolved
    )
    b5a_operator_summary_report, b5a_operator_summary_error = _load_json_mapping(
        b5a_operator_summary_resolved
    )

    package_index_meta = (
        _mapping(package_index_report.get("metadata"))
        if package_index_report is not None
        else {}
    )
    package_index_status = (
        _mapping(package_index_report.get("status"))
        if package_index_report is not None
        else {}
    )
    package_target = (
        _mapping(package_index_report.get("package_target"))
        if package_index_report is not None
        else {}
    )

    final_handoff_meta = (
        _mapping(final_handoff_report.get("metadata"))
        if final_handoff_report is not None
        else {}
    )
    final_handoff_status = (
        _mapping(final_handoff_report.get("status"))
        if final_handoff_report is not None
        else {}
    )
    final_candidate = (
        _mapping(final_handoff_report.get("candidate"))
        if final_handoff_report is not None
        else {}
    )
    final_note = (
        _mapping(final_handoff_report.get("final_human_handoff_note"))
        if final_handoff_report is not None
        else {}
    )
    final_note_target = _mapping(final_note.get("note_target"))

    delivery_note_meta = (
        _mapping(delivery_note_report.get("metadata"))
        if delivery_note_report is not None
        else {}
    )
    delivery_note_status = (
        _mapping(delivery_note_report.get("status"))
        if delivery_note_report is not None
        else {}
    )
    delivery_note_body = (
        _mapping(delivery_note_report.get("delivery_note"))
        if delivery_note_report is not None
        else {}
    )
    delivery_note_target = _mapping(delivery_note_body.get("note_target"))
    guarded_precheck_spec_meta = (
        _mapping(guarded_precheck_spec_report.get("metadata"))
        if guarded_precheck_spec_report is not None
        else {}
    )
    guarded_precheck_spec_status = (
        _mapping(guarded_precheck_spec_report.get("status"))
        if guarded_precheck_spec_report is not None
        else {}
    )
    startline_manifest_meta = (
        _mapping(startline_manifest_report.get("metadata"))
        if startline_manifest_report is not None
        else {}
    )
    b5a_operator_summary_meta = (
        _mapping(b5a_operator_summary_report.get("metadata"))
        if b5a_operator_summary_report is not None
        else {}
    )

    package_index_present = bool(
        package_index_report is not None
        and package_index_error is None
        and package_index_meta.get("source") == MANUAL_REVIEW_PACKAGE_INDEX_SOURCE
    )
    final_handoff_present = bool(
        final_handoff_report is not None
        and final_handoff_error is None
        and final_handoff_meta.get("source") == FINAL_HUMAN_HANDOFF_NOTE_SOURCE
    )
    delivery_note_present = bool(
        delivery_note_report is not None
        and delivery_note_error is None
        and delivery_note_meta.get("source") == DELIVERY_NOTE_SOURCE
    )
    guarded_precheck_spec_present = bool(
        guarded_precheck_spec_report is not None
        and guarded_precheck_spec_error is None
        and guarded_precheck_spec_meta.get("source") == GUARDED_PRECHECK_SPEC_SOURCE
    )
    startline_manifest_present = bool(
        startline_manifest_report is not None
        and startline_manifest_error is None
        and startline_manifest_meta.get("source") == STARTLINE_MANIFEST_SOURCE
    )
    b5a_operator_summary_present = bool(
        b5a_operator_summary_report is not None
        and b5a_operator_summary_error is None
        and b5a_operator_summary_meta.get("source") == B5A_OPERATOR_SUMMARY_SOURCE
    )

    package_index_ready = bool(
        package_index_present
        and package_index_status.get("manual_review_package_index_ready", False)
    )
    final_handoff_ready = bool(
        final_handoff_present
        and final_handoff_status.get("final_human_handoff_note_ready", False)
    )
    delivery_note_ready = bool(
        delivery_note_present
        and delivery_note_status.get("delivery_note_ready", False)
    )
    guarded_precheck_spec_ready = bool(
        guarded_precheck_spec_present
        and guarded_precheck_spec_status.get("completed", False)
        and guarded_precheck_spec_status.get("all_gates_pass", False)
        and guarded_precheck_spec_status.get("outcome")
        == "guarded_precheck_spec_ready_for_review"
        and guarded_precheck_spec_meta.get("default_off") is True
        and guarded_precheck_spec_meta.get("spec_only") is True
        and guarded_precheck_spec_meta.get("solver_invoked") is False
        and guarded_precheck_spec_meta.get("proof_source") is False
        and guarded_precheck_spec_meta.get("runtime_precheck_enabled") is False
        and guarded_precheck_spec_meta.get("candidate_elimination_claim") is False
    )
    dynamic_review_default_artifacts_present = bool(
        guarded_precheck_spec_present
        and startline_manifest_present
        and b5a_operator_summary_present
    )

    metadata_by_artifact = {
        "manual_review_package_index": package_index_meta,
        "final_human_handoff_note": final_handoff_meta,
        "delivery_note": delivery_note_meta,
    }
    metadata_contract_aligned = all(
        _metadata_field_matches(metadata_by_artifact, field, expected=True)
        for field in EXPECTED_TRUE_METADATA_FIELDS
    ) and all(
        _metadata_field_matches(metadata_by_artifact, field, expected=False)
        for field in EXPECTED_FALSE_METADATA_FIELDS
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            package_target.get("candidate_key"),
            final_candidate.get("key"),
            final_note_target.get("candidate_key"),
            delivery_note_target.get("candidate_key"),
        ]
    )
    anchor_idx_value, anchor_idx_locked = _locked_value(
        [
            package_target.get("anchor_idx"),
            final_candidate.get("anchor_idx"),
            final_note_target.get("anchor_idx"),
            delivery_note_target.get("anchor_idx"),
        ],
        normalize=_normalize_int_scalar,
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            package_target.get("formulation_profile"),
            final_candidate.get("formulation_profile"),
            final_note_target.get("formulation_profile"),
            delivery_note_target.get("formulation_profile"),
        ]
    )
    package_id, package_id_locked = _locked_value(
        [
            package_target.get("package_id"),
            delivery_note_target.get("package_id"),
        ]
    )
    branch_ids_locked = _lists_match_exact(
        [
            _normalize_branch_list(package_target.get("branches")),
            _normalize_branch_list(final_note_target.get("branch_ids")),
            _normalize_branch_list(delivery_note_target.get("branch_ids")),
            list(EXPECTED_BRANCH_IDS),
        ]
    )
    anchor_idx = _maybe_int(anchor_idx_value)
    candidate_target_locked = bool(
        candidate_key_locked
        and anchor_idx_locked
        and formulation_profile_locked
        and anchor_idx == 119
    )

    package_index_blocker_ids = _string_list(package_index_status.get("global_blocker_gate_ids"))
    package_index_global_blockers = _normalize_blocker_entries(
        _mapping_list(package_index_report.get("global_blockers"))
        if package_index_report is not None
        else []
    )
    package_index_global_blocker_ids = [
        entry["gate_id"] for entry in package_index_global_blockers
    ]
    final_handoff_status_blocker_ids = _string_list(
        final_handoff_status.get("still_blocked_gate_ids")
    )
    final_handoff_blockers = _normalize_blocker_entries(
        _mapping_list(final_note.get("still_blocked"))
    )
    final_handoff_blocker_ids = [entry["gate_id"] for entry in final_handoff_blockers]
    delivery_note_status_blocker_ids = _string_list(
        delivery_note_status.get("top_blocker_gate_ids")
    )
    delivery_top_blockers = _normalize_blocker_entries(
        _mapping_list(delivery_note_body.get("top_blockers"))
    )
    delivery_top_blocker_ids = [entry["gate_id"] for entry in delivery_top_blockers]

    blocker_ids_aligned = _lists_match_as_sets(
        [
            package_index_blocker_ids,
            package_index_global_blocker_ids,
            final_handoff_status_blocker_ids,
            final_handoff_blocker_ids,
            delivery_note_status_blocker_ids,
            delivery_top_blocker_ids,
        ]
    )
    blocker_alignment_rows = _build_blocker_alignment_rows(
        package_index_global_blockers,
        final_handoff_blockers,
        delivery_top_blockers,
    )
    blocker_values_aligned = bool(
        blocker_alignment_rows
        and all(entry["all_consistent"] for entry in blocker_alignment_rows)
    )

    package_false_state_entries = _normalize_false_state_entries(
        _mapping(package_index_report.get("preserved_false_states"))
        if package_index_report is not None
        else {}
    )
    package_false_state_ids = [entry["state_id"] for entry in package_false_state_entries]
    final_false_state_entries = _normalize_false_state_entries(
        _mapping_list(final_note.get("still_false"))
    )
    final_false_state_ids = [entry["state_id"] for entry in final_false_state_entries]
    delivery_false_state_entries = _normalize_false_state_entries(
        _mapping_list(delivery_note_body.get("states_that_remain_false"))
    )
    delivery_false_state_ids = [entry["state_id"] for entry in delivery_false_state_entries]
    delivery_required_false_state_ids = _string_list(
        delivery_note_status.get("required_false_state_ids")
    )

    false_state_ids_aligned = _lists_match_as_sets(
        [
            package_false_state_ids,
            final_false_state_ids,
            delivery_false_state_ids,
            delivery_required_false_state_ids,
        ]
    )
    false_state_alignment_rows = _build_false_state_alignment_rows(
        package_false_state_entries,
        final_false_state_entries,
        delivery_false_state_entries,
    )
    false_state_values_aligned = bool(
        false_state_alignment_rows
        and all(entry["all_consistent"] for entry in false_state_alignment_rows)
    )
    strict_false_states_retained = _strict_false_states_retained(
        false_state_alignment_rows
    )

    package_primary_entrypoints = _normalize_entrypoints(
        _mapping_list(package_index_report.get("primary_entrypoints"))
        if package_index_report is not None
        else []
    )
    final_read_this_first = _normalize_entrypoints(
        _mapping_list(final_note.get("read_this_first"))
    )
    delivery_read_first = _normalize_entrypoints(
        _mapping_list(delivery_note_body.get("read_first"))
    )
    entrypoint_alignment_rows = _build_entrypoint_alignment_rows(
        package_primary_entrypoints,
        final_read_this_first,
        delivery_read_first,
    )
    entrypoints_aligned = bool(
        entrypoint_alignment_rows
        and _entrypoint_branch_order(final_read_this_first)
        == _entrypoint_branch_order(delivery_read_first)
        and all(entry["all_consistent"] for entry in entrypoint_alignment_rows)
    )

    compared_artifacts = {
        "manual_review_package_index": {
            "path": _display_path(project_root, package_index_resolved),
            "present": package_index_present,
            "ready": package_index_ready,
            "source": str(package_index_meta.get("source") or ""),
            "expected_source": MANUAL_REVIEW_PACKAGE_INDEX_SOURCE,
            "error": package_index_error,
        },
        "final_human_handoff_note": {
            "path": _display_path(project_root, final_handoff_resolved),
            "present": final_handoff_present,
            "ready": final_handoff_ready,
            "source": str(final_handoff_meta.get("source") or ""),
            "expected_source": FINAL_HUMAN_HANDOFF_NOTE_SOURCE,
            "error": final_handoff_error,
        },
        "delivery_note": {
            "path": _display_path(project_root, delivery_note_resolved),
            "present": delivery_note_present,
            "ready": delivery_note_ready,
            "source": str(delivery_note_meta.get("source") or ""),
            "expected_source": DELIVERY_NOTE_SOURCE,
            "error": delivery_note_error,
        },
    }
    dynamic_review_artifacts = {
        "guarded_precheck_spec": {
            "path": _display_path(project_root, guarded_precheck_spec_resolved),
            "present": guarded_precheck_spec_present,
            "ready": guarded_precheck_spec_ready,
            "source": str(guarded_precheck_spec_meta.get("source") or ""),
            "expected_source": GUARDED_PRECHECK_SPEC_SOURCE,
            "error": guarded_precheck_spec_error,
        },
        "startline_manifest": {
            "path": _display_path(project_root, startline_manifest_resolved),
            "present": startline_manifest_present,
            "ready": startline_manifest_present,
            "source": str(startline_manifest_meta.get("source") or ""),
            "expected_source": STARTLINE_MANIFEST_SOURCE,
            "error": startline_manifest_error,
        },
        "b5a_operator_summary": {
            "path": _display_path(project_root, b5a_operator_summary_resolved),
            "present": b5a_operator_summary_present,
            "ready": b5a_operator_summary_present,
            "source": str(b5a_operator_summary_meta.get("source") or ""),
            "expected_source": B5A_OPERATOR_SUMMARY_SOURCE,
            "error": b5a_operator_summary_error,
        },
    }

    consistency_checks = [
        _check(
            "manual_review_package_index_present",
            "pass" if package_index_present else "fail",
            _presence_detail(
                project_root,
                package_index_resolved,
                package_index_present,
                package_index_error,
                MANUAL_REVIEW_PACKAGE_INDEX_SOURCE,
            ),
        ),
        _check(
            "manual_review_package_index_ready",
            "pass" if package_index_ready else "fail",
            "manual_review_package_index_ready=true"
            if package_index_ready
            else "manual_review_package_index_ready=false",
        ),
        _check(
            "final_human_handoff_note_present",
            "pass" if final_handoff_present else "fail",
            _presence_detail(
                project_root,
                final_handoff_resolved,
                final_handoff_present,
                final_handoff_error,
                FINAL_HUMAN_HANDOFF_NOTE_SOURCE,
            ),
        ),
        _check(
            "final_human_handoff_note_ready",
            "pass" if final_handoff_ready else "fail",
            "final_human_handoff_note_ready=true"
            if final_handoff_ready
            else "final_human_handoff_note_ready=false",
        ),
        _check(
            "delivery_note_present",
            "pass" if delivery_note_present else "fail",
            _presence_detail(
                project_root,
                delivery_note_resolved,
                delivery_note_present,
                delivery_note_error,
                DELIVERY_NOTE_SOURCE,
            ),
        ),
        _check(
            "delivery_note_ready",
            "pass" if delivery_note_ready else "fail",
            "delivery_note_ready=true"
            if delivery_note_ready
            else "delivery_note_ready=false",
        ),
        _check(
            "guarded_precheck_spec_present",
            "pass" if guarded_precheck_spec_present else "fail",
            _presence_detail(
                project_root,
                guarded_precheck_spec_resolved,
                guarded_precheck_spec_present,
                guarded_precheck_spec_error,
                GUARDED_PRECHECK_SPEC_SOURCE,
            ),
        ),
        _check(
            "guarded_precheck_spec_ready",
            "pass" if guarded_precheck_spec_ready else "fail",
            "guarded precheck spec is default-off/spec-only/no-solve and ready for review"
            if guarded_precheck_spec_ready
            else "guarded precheck spec missing, malformed, source-mismatched, or not ready",
        ),
        _check(
            "startline_manifest_present",
            "pass" if startline_manifest_present else "fail",
            _presence_detail(
                project_root,
                startline_manifest_resolved,
                startline_manifest_present,
                startline_manifest_error,
                STARTLINE_MANIFEST_SOURCE,
            ),
        ),
        _check(
            "b5a_operator_summary_present",
            "pass" if b5a_operator_summary_present else "fail",
            _presence_detail(
                project_root,
                b5a_operator_summary_resolved,
                b5a_operator_summary_present,
                b5a_operator_summary_error,
                B5A_OPERATOR_SUMMARY_SOURCE,
            ),
        ),
        _check(
            "dynamic_review_default_artifacts_present",
            "pass" if dynamic_review_default_artifacts_present else "fail",
            "All default artifacts consumed by the dynamic review command set are present and source-typed."
            if dynamic_review_default_artifacts_present
            else "At least one default artifact consumed by the dynamic review command set is missing or source-mismatched.",
        ),
        _check(
            "review_only_contract_retained",
            "pass" if metadata_contract_aligned else "fail",
            "All three upstream artifacts remain review-only/spec-only/default-off/no-solve with proof_source=false, candidate_elimination_claim=false, solver_invoked=false, and repo_side_review_state_updated=false."
            if metadata_contract_aligned
            else "At least one upstream artifact drifted away from the required review-only/default-off/no-solve contract.",
        ),
        _check(
            "candidate_target_locked",
            "pass" if candidate_target_locked else "fail",
            "Candidate key, anchor_idx=119, and formulation_profile remain locked across the package index, final handoff note, and delivery note."
            if candidate_target_locked
            else "Candidate key, anchor_idx, or formulation_profile drifted across the compared artifacts.",
        ),
        _check(
            "package_id_locked",
            "pass" if package_id_locked else "fail",
            "Package id remains locked across the package index and delivery note."
            if package_id_locked
            else "Package id drifted across the compared artifacts.",
        ),
        _check(
            "branch_ids_locked",
            "pass" if branch_ids_locked else "fail",
            "Branch ids remain locked to ingest_review and acceptance_authorization across the compared artifacts."
            if branch_ids_locked
            else "Branch ids drifted across the compared artifacts.",
        ),
        _check(
            "blocker_ids_aligned",
            "pass" if blocker_ids_aligned else "fail",
            "Package index global blockers, final handoff still_blocked, and delivery note top_blockers carry the same gate ids."
            if blocker_ids_aligned
            else "Blocker gate ids drifted across the compared artifacts.",
        ),
        _check(
            "blocker_values_aligned",
            "pass" if blocker_values_aligned else "fail",
            "Every carried blocker remains present, false, and branch-aligned across the compared artifacts."
            if blocker_values_aligned
            else "At least one carried blocker is missing, no longer false, or no longer branch-aligned.",
        ),
        _check(
            "false_state_ids_aligned",
            "pass" if false_state_ids_aligned else "fail",
            "Package index preserved_false_states, final handoff still_false, and delivery note states_that_remain_false carry the same state ids."
            if false_state_ids_aligned
            else "False-state ids drifted across the compared artifacts.",
        ),
        _check(
            "false_state_values_aligned",
            "pass" if false_state_values_aligned else "fail",
            "Every carried false state remains present, false, and branch-aligned across the compared artifacts."
            if false_state_values_aligned
            else "At least one carried false state is missing, no longer false, or no longer branch-aligned.",
        ),
        _check(
            "strict_non_authorizing_states_retained",
            "pass" if strict_false_states_retained else "fail",
            "All strict non-authorizing states remain false, including reviewed_runtime_patch_exists, runtime_enablement_allowed, proof_source, solver_invoked, repo_side_review_state_updated, execution_authorized, and acceptance_execution_authorized."
            if strict_false_states_retained
            else "One or more strict non-authorizing states are missing or no longer false.",
        ),
        _check(
            "entrypoints_aligned",
            "pass" if entrypoints_aligned else "fail",
            "Final handoff read_this_first and delivery note read_first align with each other and both point at package-index primary entrypoints."
            if entrypoints_aligned
            else "Entrypoint/read-first references drifted across the compared artifacts.",
        ),
    ]

    all_consistency_checks_pass = all(
        check["status"] == "pass" for check in consistency_checks
    )
    package_artifact_consistency_audit_ready = all_consistency_checks_pass
    missing_ready_gate_ids = [
        check["check_id"]
        for check in consistency_checks
        if check["status"] == "fail"
    ]
    recommended_next_step = (
        "carry_forward_review_only_package_artifacts_without_execution_authorization"
        if package_artifact_consistency_audit_ready
        else "repair_package_artifact_consistency_inputs"
    )

    if package_artifact_consistency_audit_ready:
        audit_summary = (
            "The latest package index, final human handoff note, and delivery note "
            "are internally consistent as one bounded review-only/spec-only/default-off/"
            "no-solve package, and the default artifacts required by the dynamic "
            "review command set are present. The audit carries blockers and false "
            "states forward only; it does not authorize execution, runtime "
            "enablement, repo-state mutation, or any claim that human review "
            "already happened."
        )
    else:
        audit_summary = (
            "At least one package-level consistency check failed. Repair the upstream "
            "package artifacts before treating this package as a bounded review-only "
            "handoff."
        )

    return {
        "metadata": {
            "source": PACKAGE_ARTIFACT_CONSISTENCY_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_package_artifact_consistency_audit_review_only_spec_only_"
                "default_off_no_solve_solver_invoked_false"
            ),
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "no_solve": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "paths": {
            "project_root": str(project_root),
        },
        "status": {
            "package_artifact_consistency_audit_ready": (
                package_artifact_consistency_audit_ready
            ),
            "all_consistency_checks_pass": all_consistency_checks_pass,
            "missing_ready_gate_ids": missing_ready_gate_ids,
            "recommended_next_step": recommended_next_step,
        },
        "audit_target": {
            "audit_kind": "bounded_review_only_package_artifact_consistency_audit",
            "package_id": package_id,
            "candidate_key": candidate_key,
            "anchor_idx": anchor_idx,
            "formulation_profile": formulation_profile,
            "branch_ids": list(EXPECTED_BRANCH_IDS),
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "no_solve": True,
            "proof_source": False,
            "solver_invoked": False,
            "candidate_elimination_claim": False,
            "repo_side_review_state_updated": False,
        },
        "compared_artifacts": compared_artifacts,
        "dynamic_review_artifacts": dynamic_review_artifacts,
        "consistency_checks": consistency_checks,
        "blocker_alignment": {
            "package_index_status_blocker_ids": package_index_blocker_ids,
            "package_index_global_blocker_ids": package_index_global_blocker_ids,
            "final_handoff_status_blocker_ids": final_handoff_status_blocker_ids,
            "final_handoff_still_blocked_gate_ids": final_handoff_blocker_ids,
            "delivery_note_status_blocker_ids": delivery_note_status_blocker_ids,
            "delivery_note_top_blocker_gate_ids": delivery_top_blocker_ids,
            "all_blocker_ids_match": blocker_ids_aligned,
            "blockers": blocker_alignment_rows,
        },
        "false_state_alignment": {
            "package_index_state_ids": package_false_state_ids,
            "final_handoff_state_ids": final_false_state_ids,
            "delivery_note_state_ids": delivery_false_state_ids,
            "delivery_note_required_false_state_ids": delivery_required_false_state_ids,
            "all_false_state_ids_match": false_state_ids_aligned,
            "states": false_state_alignment_rows,
        },
        "entrypoint_alignment": {
            "package_index_primary_entrypoints": package_primary_entrypoints,
            "final_handoff_read_this_first": final_read_this_first,
            "delivery_note_read_first": delivery_read_first,
            "all_entrypoints_match": entrypoints_aligned,
            "branches": entrypoint_alignment_rows,
        },
        "summary": {
            "audit_summary": audit_summary,
            "non_authorizing_notice": DEFAULT_NON_AUTHORIZING_NOTICE,
            "remaining_blocker_gate_ids": package_index_global_blocker_ids,
            "states_that_must_remain_false": delivery_false_state_ids,
            "read_first_artifact_paths": [
                entry["artifact_path"] for entry in delivery_read_first
            ],
        },
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    audit_target = _mapping(report.get("audit_target"))
    compared_artifacts = _mapping(report.get("compared_artifacts"))
    dynamic_review_artifacts = _mapping(report.get("dynamic_review_artifacts"))
    blocker_alignment = _mapping(report.get("blocker_alignment"))
    false_state_alignment = _mapping(report.get("false_state_alignment"))
    entrypoint_alignment = _mapping(report.get("entrypoint_alignment"))
    summary = _mapping(report.get("summary"))

    lines = [
        "# Phase 3B Anchor119 Row-Domain Package Artifact Consistency Audit",
        "",
        f"- package_artifact_consistency_audit_ready: `{status.get('package_artifact_consistency_audit_ready')}`",
        f"- all_consistency_checks_pass: `{status.get('all_consistency_checks_pass')}`",
        f"- recommended_next_step: `{status.get('recommended_next_step')}`",
        "",
        "## Audit Target",
        "",
        f"- audit_kind: `{audit_target.get('audit_kind')}`",
        f"- package_id: `{audit_target.get('package_id')}`",
        f"- candidate_key: `{audit_target.get('candidate_key')}`",
        f"- anchor_idx: `{audit_target.get('anchor_idx')}`",
        f"- formulation_profile: `{audit_target.get('formulation_profile')}`",
        f"- branch_ids: `{', '.join(_string_list(audit_target.get('branch_ids')))}`",
        "",
        "## Compared Artifacts",
        "",
    ]

    for artifact_name, artifact in compared_artifacts.items():
        artifact_mapping = _mapping(artifact)
        lines.append(
            f"- `{artifact_name}`: present=`{artifact_mapping.get('present')}`; "
            f"ready=`{artifact_mapping.get('ready')}`; "
            f"path=`{artifact_mapping.get('path')}`; "
            f"source=`{artifact_mapping.get('source')}`"
        )

    lines.extend(["", "## Dynamic Review Default Artifacts", ""])
    for artifact_name, artifact in dynamic_review_artifacts.items():
        artifact_mapping = _mapping(artifact)
        lines.append(
            f"- `{artifact_name}`: present=`{artifact_mapping.get('present')}`; "
            f"ready=`{artifact_mapping.get('ready')}`; "
            f"path=`{artifact_mapping.get('path')}`; "
            f"source=`{artifact_mapping.get('source')}`"
        )

    lines.extend(["", "## Consistency Checks", ""])
    for check in _mapping_list(report.get("consistency_checks")):
        lines.append(
            f"- `{check.get('check_id')}`: `{check.get('status')}` - {check.get('detail')}"
        )

    lines.extend(["", "## Blocker Alignment", ""])
    lines.append(
        f"- all_blocker_ids_match: `{blocker_alignment.get('all_blocker_ids_match')}`"
    )
    lines.append(
        f"- package_index_global_blocker_ids: `{', '.join(_string_list(blocker_alignment.get('package_index_global_blocker_ids')))}`"
    )
    lines.append(
        f"- final_handoff_still_blocked_gate_ids: `{', '.join(_string_list(blocker_alignment.get('final_handoff_still_blocked_gate_ids')))}`"
    )
    lines.append(
        f"- delivery_note_top_blocker_gate_ids: `{', '.join(_string_list(blocker_alignment.get('delivery_note_top_blocker_gate_ids')))}`"
    )
    for entry in _mapping_list(blocker_alignment.get("blockers")):
        lines.append(
            f"- `{entry.get('gate_id')}`: current_values_aligned=`{entry.get('current_values_aligned')}`; "
            f"branch_ids_aligned=`{entry.get('branch_ids_aligned')}`; "
            f"all_consistent=`{entry.get('all_consistent')}`"
        )

    lines.extend(["", "## False State Alignment", ""])
    lines.append(
        f"- all_false_state_ids_match: `{false_state_alignment.get('all_false_state_ids_match')}`"
    )
    lines.append(
        f"- package_index_state_ids: `{', '.join(_string_list(false_state_alignment.get('package_index_state_ids')))}`"
    )
    lines.append(
        f"- final_handoff_state_ids: `{', '.join(_string_list(false_state_alignment.get('final_handoff_state_ids')))}`"
    )
    lines.append(
        f"- delivery_note_state_ids: `{', '.join(_string_list(false_state_alignment.get('delivery_note_state_ids')))}`"
    )
    for entry in _mapping_list(false_state_alignment.get("states")):
        lines.append(
            f"- `{entry.get('state_id')}`: current_values_aligned=`{entry.get('current_values_aligned')}`; "
            f"branch_ids_aligned=`{entry.get('branch_ids_aligned')}`; "
            f"locked_false_consistent=`{entry.get('locked_false_consistent')}`; "
            f"all_consistent=`{entry.get('all_consistent')}`"
        )

    lines.extend(["", "## Entrypoint Alignment", ""])
    lines.append(
        f"- all_entrypoints_match: `{entrypoint_alignment.get('all_entrypoints_match')}`"
    )
    for entry in _mapping_list(entrypoint_alignment.get("branches")):
        lines.append(
            f"- `{entry.get('branch_id')}`: final_vs_delivery_match=`{entry.get('final_vs_delivery_match')}`; "
            f"package_index_contains_final=`{entry.get('package_index_contains_final')}`; "
            f"package_index_contains_delivery=`{entry.get('package_index_contains_delivery')}`; "
            f"all_consistent=`{entry.get('all_consistent')}`"
        )

    lines.extend(
        [
            "",
            "## Summary",
            "",
            str(summary.get("audit_summary") or ""),
            "",
            f"- non_authorizing_notice: {summary.get('non_authorizing_notice')}",
            f"- remaining_blocker_gate_ids: `{', '.join(_string_list(summary.get('remaining_blocker_gate_ids')))}`",
            f"- states_that_must_remain_false: `{', '.join(_string_list(summary.get('states_that_must_remain_false')))}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    audit_target = _mapping(report.get("audit_target"))
    summary = _mapping(report.get("summary"))
    checks = {
        str(check.get("check_id")): check
        for check in _mapping_list(report.get("consistency_checks"))
    }
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain package artifact consistency audit",
            "package_artifact_consistency_audit_ready="
            + str(status.get("package_artifact_consistency_audit_ready")),
            "all_consistency_checks_pass="
            + str(status.get("all_consistency_checks_pass")),
            "candidate_key=" + str(audit_target.get("candidate_key")),
            "anchor_idx=" + str(audit_target.get("anchor_idx")),
            "formulation_profile=" + str(audit_target.get("formulation_profile")),
            "branch_ids=" + ",".join(_string_list(audit_target.get("branch_ids"))),
            "dynamic_review_default_artifacts_present="
            + str(
                _mapping(checks.get("dynamic_review_default_artifacts_present")).get(
                    "status"
                )
                == "pass"
            ),
            "remaining_blocker_gate_ids="
            + ",".join(_string_list(summary.get("remaining_blocker_gate_ids"))),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
            "audit_summary=" + str(summary.get("audit_summary")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_package_artifact_consistency_audit",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_blocker_alignment_rows(
    package_index_entries: list[Dict[str, Any]],
    final_entries: list[Dict[str, Any]],
    delivery_entries: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    package_map = {entry["gate_id"]: entry for entry in package_index_entries}
    final_map = {entry["gate_id"]: entry for entry in final_entries}
    delivery_map = {entry["gate_id"]: entry for entry in delivery_entries}

    rows = []
    for gate_id in _ordered_union(
        list(package_map.keys()),
        list(final_map.keys()),
        list(delivery_map.keys()),
    ):
        package_entry = _mapping(package_map.get(gate_id))
        final_entry = _mapping(final_map.get(gate_id))
        delivery_entry = _mapping(delivery_map.get(gate_id))

        current_values = [
            package_entry.get("current_value"),
            final_entry.get("current_value"),
            delivery_entry.get("current_value"),
        ]
        current_values_aligned = _all_equal(current_values) and _bool_false(
            current_values[0]
        )
        branch_lists = [
            _normalize_branch_list(package_entry.get("branches")),
            _normalize_branch_list(final_entry.get("branches")),
            _normalize_branch_list(delivery_entry.get("branches")),
        ]
        branch_ids_aligned = _lists_match_as_sets(branch_lists)

        rows.append(
            {
                "gate_id": gate_id,
                "package_index_present": bool(package_entry),
                "final_handoff_present": bool(final_entry),
                "delivery_note_present": bool(delivery_entry),
                "package_index_current_value": package_entry.get("current_value"),
                "final_handoff_current_value": final_entry.get("current_value"),
                "delivery_note_current_value": delivery_entry.get("current_value"),
                "package_index_branches": branch_lists[0],
                "final_handoff_branches": branch_lists[1],
                "delivery_note_branches": branch_lists[2],
                "current_values_aligned": current_values_aligned,
                "branch_ids_aligned": branch_ids_aligned,
                "all_consistent": bool(
                    package_entry
                    and final_entry
                    and delivery_entry
                    and current_values_aligned
                    and branch_ids_aligned
                ),
            }
        )
    return rows


def _build_false_state_alignment_rows(
    package_index_entries: list[Dict[str, Any]],
    final_entries: list[Dict[str, Any]],
    delivery_entries: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    package_map = {entry["state_id"]: entry for entry in package_index_entries}
    final_map = {entry["state_id"]: entry for entry in final_entries}
    delivery_map = {entry["state_id"]: entry for entry in delivery_entries}

    rows = []
    for state_id in _ordered_union(
        list(package_map.keys()),
        list(final_map.keys()),
        list(delivery_map.keys()),
    ):
        package_entry = _mapping(package_map.get(state_id))
        final_entry = _mapping(final_map.get(state_id))
        delivery_entry = _mapping(delivery_map.get(state_id))

        current_values = [
            package_entry.get("current_value"),
            final_entry.get("current_value"),
            delivery_entry.get("current_value"),
        ]
        current_values_aligned = _all_equal(current_values) and _bool_false(
            current_values[0]
        )
        branch_lists = [
            _normalize_branch_list(package_entry.get("branches")),
            _normalize_branch_list(final_entry.get("branches")),
            _normalize_branch_list(delivery_entry.get("branches")),
        ]
        branch_ids_aligned = _lists_match_as_sets(branch_lists)
        locked_false_consistent = bool(
            _bool_true(package_entry.get("locked_false"))
            and _bool_true(delivery_entry.get("locked_false"))
        )

        rows.append(
            {
                "state_id": state_id,
                "package_index_present": bool(package_entry),
                "final_handoff_present": bool(final_entry),
                "delivery_note_present": bool(delivery_entry),
                "package_index_current_value": package_entry.get("current_value"),
                "final_handoff_current_value": final_entry.get("current_value"),
                "delivery_note_current_value": delivery_entry.get("current_value"),
                "package_index_locked_false": package_entry.get("locked_false"),
                "delivery_note_locked_false": delivery_entry.get("locked_false"),
                "package_index_branches": branch_lists[0],
                "final_handoff_branches": branch_lists[1],
                "delivery_note_branches": branch_lists[2],
                "current_values_aligned": current_values_aligned,
                "branch_ids_aligned": branch_ids_aligned,
                "locked_false_consistent": locked_false_consistent,
                "all_consistent": bool(
                    package_entry
                    and final_entry
                    and delivery_entry
                    and current_values_aligned
                    and branch_ids_aligned
                    and locked_false_consistent
                ),
            }
        )
    return rows


def _build_entrypoint_alignment_rows(
    package_index_entries: list[Dict[str, Any]],
    final_entries: list[Dict[str, Any]],
    delivery_entries: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    package_by_branch: dict[str, list[Dict[str, Any]]] = {}
    for entry in package_index_entries:
        package_by_branch.setdefault(entry["branch_id"], []).append(entry)

    final_by_branch = {entry["branch_id"]: entry for entry in final_entries}
    delivery_by_branch = {entry["branch_id"]: entry for entry in delivery_entries}
    branch_ids = _ordered_union(
        [entry["branch_id"] for entry in final_entries],
        [entry["branch_id"] for entry in delivery_entries],
    )

    rows = []
    for branch_id in branch_ids:
        package_entries = package_by_branch.get(branch_id, [])
        final_entry = _mapping(final_by_branch.get(branch_id))
        delivery_entry = _mapping(delivery_by_branch.get(branch_id))

        package_artifact_pairs = {
            (str(entry.get("artifact_id") or ""), str(entry.get("artifact_path") or ""))
            for entry in package_entries
        }
        final_pair = (
            str(final_entry.get("artifact_id") or ""),
            str(final_entry.get("artifact_path") or ""),
        )
        delivery_pair = (
            str(delivery_entry.get("artifact_id") or ""),
            str(delivery_entry.get("artifact_path") or ""),
        )
        final_vs_delivery_match = bool(final_entry) and bool(delivery_entry) and (
            final_pair == delivery_pair
        )
        package_index_contains_final = bool(final_entry) and final_pair in package_artifact_pairs
        package_index_contains_delivery = bool(delivery_entry) and (
            delivery_pair in package_artifact_pairs
        )

        rows.append(
            {
                "branch_id": branch_id,
                "package_index_primary_artifact_ids": [
                    str(entry.get("artifact_id") or "") for entry in package_entries
                ],
                "package_index_primary_artifact_paths": [
                    str(entry.get("artifact_path") or "") for entry in package_entries
                ],
                "final_handoff_artifact_id": str(final_entry.get("artifact_id") or ""),
                "final_handoff_artifact_path": str(
                    final_entry.get("artifact_path") or ""
                ),
                "delivery_note_artifact_id": str(
                    delivery_entry.get("artifact_id") or ""
                ),
                "delivery_note_artifact_path": str(
                    delivery_entry.get("artifact_path") or ""
                ),
                "final_vs_delivery_match": final_vs_delivery_match,
                "package_index_contains_final": package_index_contains_final,
                "package_index_contains_delivery": package_index_contains_delivery,
                "all_consistent": bool(
                    final_vs_delivery_match
                    and package_index_contains_final
                    and package_index_contains_delivery
                ),
            }
        )
    return rows


def _normalize_blocker_entries(entries: list[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for entry in entries:
        gate_id = str(entry.get("gate_id") or "").strip()
        if not gate_id:
            continue
        normalized.append(
            {
                "gate_id": gate_id,
                "current_value": entry.get("current_value"),
                "branches": _normalize_branch_list(entry.get("branches")),
            }
        )
    return normalized


def _normalize_false_state_entries(entries: Any) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    if isinstance(entries, Mapping):
        iterator = []
        for state_id, value in entries.items():
            payload = _mapping(value)
            iterator.append({"state_id": state_id, **payload})
    else:
        iterator = _mapping_list(entries)

    for entry in iterator:
        state_id = str(entry.get("state_id") or "").strip()
        if not state_id:
            continue
        normalized.append(
            {
                "state_id": state_id,
                "current_value": entry.get("current_value"),
                "locked_false": entry.get("locked_false"),
                "branches": _normalize_branch_list(entry.get("branches")),
            }
        )
    return normalized


def _normalize_entrypoints(entries: list[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for entry in entries:
        branch_id = _normalize_branch_id(entry.get("branch_id"))
        artifact_id = str(entry.get("artifact_id") or "").strip()
        artifact_path = str(
            entry.get("artifact_path") or entry.get("path") or ""
        ).strip()
        if not branch_id or not artifact_id or not artifact_path:
            continue
        normalized.append(
            {
                "branch_id": branch_id,
                "artifact_id": artifact_id,
                "artifact_path": artifact_path,
            }
        )
    return normalized


def _strict_false_states_retained(rows: list[Mapping[str, Any]]) -> bool:
    row_by_state = {str(entry.get("state_id") or ""): entry for entry in rows}
    for state_id in EXPECTED_STRICT_FALSE_STATE_IDS:
        entry = _mapping(row_by_state.get(state_id))
        if not entry or not bool(entry.get("all_consistent")):
            return False
    return True


def _entrypoint_branch_order(entries: list[Mapping[str, Any]]) -> list[str]:
    return [str(entry.get("branch_id") or "") for entry in entries]


def _metadata_field_matches(
    metadata_by_artifact: Mapping[str, Mapping[str, Any]],
    field: str,
    *,
    expected: bool,
) -> bool:
    values = []
    for metadata in metadata_by_artifact.values():
        if field not in metadata:
            return False
        values.append(metadata.get(field))
    if not _all_equal(values):
        return False
    return _bool_true(values[0]) if expected else _bool_false(values[0])


def _all_equal(values: list[Any]) -> bool:
    if not values:
        return False
    first = values[0]
    return all(value == first for value in values[1:])


def _locked_value(
    values: list[Any], *, normalize: Optional[Any] = None
) -> tuple[Any, bool]:
    normalized_values = []
    for value in values:
        normalized = normalize(value) if normalize is not None else _normalize_scalar(value)
        if normalized is None or normalized == "":
            return None, False
        normalized_values.append(normalized)
    first = normalized_values[0]
    return first, all(value == first for value in normalized_values[1:])


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return text or None


def _normalize_int_scalar(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _maybe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _lists_match_exact(lists: list[list[str]]) -> bool:
    if not lists:
        return False
    first = lists[0]
    if not first:
        return False
    return all(entries == first for entries in lists[1:])


def _lists_match_as_sets(lists: list[list[str]]) -> bool:
    if not lists:
        return False
    normalized = [sorted(_ordered_union(entries)) for entries in lists]
    first = normalized[0]
    if not first:
        return False
    return all(entries == first for entries in normalized[1:])


def _ordered_union(*lists: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for entries in lists:
        for entry in entries:
            text = str(entry or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
    return result


def _normalize_branch_list(value: Any) -> list[str]:
    normalized = []
    for item in _string_list(value):
        branch_id = _normalize_branch_id(item)
        if branch_id and branch_id not in normalized:
            normalized.append(branch_id)
    return normalized


def _normalize_branch_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("-", "_")


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        result = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    return []


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _mapping_list(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            result.append(dict(item))
    return result


def _bool_true(value: Any) -> bool:
    return value is True


def _bool_false(value: Any) -> bool:
    return value is False


def _presence_detail(
    project_root: Path,
    path: Path,
    present: bool,
    error: Optional[str],
    expected_source: str,
) -> str:
    display_path = _display_path(project_root, path)
    if present:
        return f"{display_path} present with expected source {expected_source}."
    if error:
        return f"{display_path} failed to load: {error}"
    return f"{display_path} missing or source drifted from {expected_source}."


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root))
    except Exception:
        return str(path.resolve())


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, Mapping):
        return None, "top-level JSON value is not an object"
    return dict(payload), None


def _resolve_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {
        "check_id": check_id,
        "status": status,
        "detail": detail,
    }

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

SIGNOFF_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_v1"
)
REVIEWER_RECORD_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_v1"
)
SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
REVIEWER_RECORD_COLLECTION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1"
)
DEFAULT_SIGNOFF_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_20260424/"
    "anchor119_row_domain_signoff_record_scaffold.json"
)
DEFAULT_REVIEWER_RECORD_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_20260424/"
    "anchor119_row_domain_reviewer_record_prep.json"
)
DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_20260424/"
    "anchor119_row_domain_signoff_record_validator.json"
)
DEFAULT_FUTURE_REVIEWER_RECORD_HANDOFF_DIR = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
    "reviewer_record_handoff"
)
COLLECTION_NOTICE = (
    "Review-only/default-off collection contract only. No actual reviewer-signed "
    "runtime patch signoff record has been collected. This artifact defines the "
    "future manual reviewer-side collection and handoff shape only; it does not "
    "set reviewed_runtime_patch_exists=true and does not allow runtime enablement."
)
NO_ACTUAL_RECORD_DETAIL = (
    "No actual reviewer-signed runtime patch signoff record has been collected "
    "yet. reviewed_runtime_patch_exists remains false and runtime enablement "
    "remains disallowed."
)
MANUAL_COLLECTION_SOURCE_DETAIL = (
    "A future human reviewer should start from the scaffolded pending payload, "
    "fill the reviewer-owned fields manually, preserve the required reviewer "
    "statement ids and still-blocked gate ids, and then hand off the completed "
    "JSON through a later artifact-backed validation/ingest step. This builder "
    "does not collect or ingest that record."
)
HANDOFF_DETAIL = (
    "The future reviewer-side handoff stays artifact-backed and file-based. The "
    "completed JSON should be dropped at the path shape below, then validated "
    "separately while reviewed_runtime_patch_exists stays false until that later "
    "handoff is actually received and checked."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection(
    project_root: Path,
    *,
    signoff_record_scaffold_path: Optional[Path] = None,
    reviewer_record_prep_path: Optional[Path] = None,
    signoff_record_validator_path: Optional[Path] = None,
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
    signoff_record_validator_resolved = _resolve_path(
        project_root,
        signoff_record_validator_path
        if signoff_record_validator_path is not None
        else DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH,
    )
    reviewer_record_handoff_dir = _resolve_path(
        project_root, DEFAULT_FUTURE_REVIEWER_RECORD_HANDOFF_DIR
    )

    signoff_record_scaffold_report, signoff_record_scaffold_error = _load_json_mapping(
        signoff_record_scaffold_resolved
    )
    reviewer_record_prep_report, reviewer_record_prep_error = _load_json_mapping(
        reviewer_record_prep_resolved
    )
    signoff_record_validator_report, signoff_record_validator_error = _load_json_mapping(
        signoff_record_validator_resolved
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
    validator_meta = (
        _mapping(signoff_record_validator_report.get("metadata"))
        if signoff_record_validator_report
        else {}
    )
    validator_status = (
        _mapping(signoff_record_validator_report.get("status"))
        if signoff_record_validator_report
        else {}
    )
    signoff_record_validator = (
        _mapping(signoff_record_validator_report.get("signoff_record_validator"))
        if signoff_record_validator_report
        else {}
    )
    candidate = (
        _mapping(signoff_record_scaffold_report.get("candidate"))
        if signoff_record_scaffold_report
        else _mapping(reviewer_record_prep_report.get("candidate"))
        if reviewer_record_prep_report
        else _mapping(signoff_record_validator_report.get("candidate"))
        if signoff_record_validator_report
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
    signoff_record_validator_present = bool(
        signoff_record_validator_report is not None
        and signoff_record_validator_error is None
        and validator_meta.get("source") == SIGNOFF_RECORD_VALIDATOR_SOURCE
    )

    signoff_record_scaffold_ready = bool(
        scaffold_status.get("signoff_record_scaffold_ready", False)
    )
    reviewer_record_prep_ready = bool(
        reviewer_status.get("reviewer_record_prep_ready", False)
    )
    signoff_record_validator_ready = bool(
        validator_status.get("signoff_record_validator_ready", False)
    )
    upstream_reviewed_runtime_patch_exists = bool(
        scaffold_status.get("reviewed_runtime_patch_exists", False)
        or reviewer_status.get("reviewed_runtime_patch_exists", False)
        or validator_status.get("reviewed_runtime_patch_exists", False)
    )
    upstream_runtime_enablement_allowed = bool(
        scaffold_status.get("runtime_enablement_allowed", False)
        or reviewer_status.get("runtime_enablement_allowed", False)
        or validator_status.get("runtime_enablement_allowed", False)
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
        required_statement_ids = _string_list(
            signoff_record_validator.get("required_reviewer_statement_ids")
        )

    validator_rules = _mapping(signoff_record_validator.get("validator_rules"))
    validator_required_fields = _mapping_list(validator_rules.get("required_fields"))
    agreed_statement_ids_rule = dict(
        _mapping(validator_rules.get("agreed_statement_ids"))
    )
    still_blocked_gate_ids_rule = dict(
        _mapping(validator_rules.get("still_blocked_gate_ids"))
    )

    carry_forward_gate_entries = _merge_gate_entries(
        _blocked_gate_entries(signoff_record_scaffold_report),
        _blocked_gate_entries(reviewer_record_prep_report),
        _blocked_gate_entries(signoff_record_validator_report),
    )
    carry_forward_still_blocked_gate_ids = _string_list(
        signoff_record_validator_report.get("still_blocked_gate_ids")
        if signoff_record_validator_report
        else []
    )
    if not carry_forward_still_blocked_gate_ids:
        carry_forward_still_blocked_gate_ids = _string_list(
            still_blocked_gate_ids_rule.get("required_ids")
        )
    if not carry_forward_still_blocked_gate_ids:
        carry_forward_still_blocked_gate_ids = _string_list(
            signoff_record_scaffold_report.get("still_blocked_gate_ids")
            if signoff_record_scaffold_report
            else []
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

    target_record_type = (
        signoff_record_validator.get("target_record_type")
        or pending_signoff_record_payload.get("record_type")
        or signoff_record_scaffold.get("record_type")
        or reviewer_record_prep.get("record_type")
    )
    scope = (
        signoff_record_validator.get("scope")
        or pending_signoff_record_payload.get("scope")
        or signoff_record_scaffold.get("scope")
        or reviewer_record_prep.get("scope")
    )
    candidate_key = str(candidate.get("key") or "").strip()
    anchor_idx = candidate.get("anchor_idx")
    record_identity = _build_record_identity(
        target_record_type, candidate_key=candidate_key, anchor_idx=anchor_idx
    )
    handoff_path_shape = _build_handoff_path_shape(
        project_root,
        reviewer_record_handoff_dir,
        target_record_type=target_record_type,
        candidate_key=candidate_key,
        anchor_idx=anchor_idx,
    )
    handoff_filename_tokens = _build_handoff_filename_tokens(
        target_record_type=target_record_type,
        candidate_key=candidate_key,
        anchor_idx=anchor_idx,
    )

    target_identity_defined = bool(target_record_type and scope and record_identity)
    expected_collection_source_defined = bool(
        pending_signoff_record_payload and required_record_fields and validator_required_fields
    )
    handoff_path_shape_defined = bool(handoff_path_shape and handoff_filename_tokens)
    required_record_fields_preserved = bool(required_record_fields)
    required_statement_ids_preserved = bool(required_statement_ids)
    still_blocked_gate_ids_preserved = bool(carry_forward_still_blocked_gate_ids)
    validator_rules_ready = bool(
        validator_required_fields
        and agreed_statement_ids_rule
        and still_blocked_gate_ids_rule
    )
    default_off_retained = bool(
        signoff_record_scaffold_present
        and reviewer_record_prep_present
        and signoff_record_validator_present
        and bool(scaffold_meta.get("default_off", False))
        and bool(reviewer_meta.get("default_off", False))
        and bool(validator_meta.get("default_off", False))
        and not upstream_runtime_enablement_allowed
    )

    gates = [
        {
            "gate_id": "signoff_record_scaffold_ready",
            "satisfied": bool(signoff_record_scaffold_ready),
            "blocking": not bool(signoff_record_scaffold_ready),
            "detail": "Reviewer-record collection depends on the signoff record scaffold already being ready.",
        },
        {
            "gate_id": "reviewer_record_prep_ready",
            "satisfied": bool(reviewer_record_prep_ready),
            "blocking": not bool(reviewer_record_prep_ready),
            "detail": "Reviewer-record collection depends on reviewer-record prep already being ready.",
        },
        {
            "gate_id": "signoff_record_validator_ready",
            "satisfied": bool(signoff_record_validator_ready),
            "blocking": not bool(signoff_record_validator_ready),
            "detail": "Reviewer-record collection depends on the signoff record validator contract already being ready.",
        },
        {
            "gate_id": "reviewer_record_collection_target_identity_defined",
            "satisfied": bool(target_identity_defined),
            "blocking": not bool(target_identity_defined),
            "detail": "The collection artifact must define the target record identity and scope explicitly.",
        },
        {
            "gate_id": "reviewer_record_collection_source_defined",
            "satisfied": bool(expected_collection_source_defined),
            "blocking": not bool(expected_collection_source_defined),
            "detail": "The collection artifact must lock the manual reviewer-side collection source and preserved payload contract.",
        },
        {
            "gate_id": "reviewer_record_collection_handoff_path_shape_defined",
            "satisfied": bool(handoff_path_shape_defined),
            "blocking": not bool(handoff_path_shape_defined),
            "detail": "The collection artifact must define the future handoff path shape for the manual reviewer record.",
        },
        {
            "gate_id": "reviewer_record_collection_validator_rules_ready",
            "satisfied": bool(validator_rules_ready),
            "blocking": not bool(validator_rules_ready),
            "detail": "The collection artifact must preserve the validator field, statement-id, and still-blocked-gate rules.",
        },
        {
            "gate_id": "reviewer_record_collection_required_fields_preserved",
            "satisfied": bool(required_record_fields_preserved),
            "blocking": not bool(required_record_fields_preserved),
            "detail": "The collection artifact must preserve the required signoff record fields.",
        },
        {
            "gate_id": "reviewer_record_collection_required_statement_ids_preserved",
            "satisfied": bool(required_statement_ids_preserved),
            "blocking": not bool(required_statement_ids_preserved),
            "detail": "The collection artifact must preserve the required reviewer statement ids.",
        },
        {
            "gate_id": "reviewer_record_collection_still_blocked_gate_ids_preserved",
            "satisfied": bool(still_blocked_gate_ids_preserved),
            "blocking": not bool(still_blocked_gate_ids_preserved),
            "detail": "The collection artifact must preserve the still-blocked gate ids that remain in force after future signoff.",
        },
        {
            "gate_id": "default_off_retained_for_reviewer_record_collection",
            "satisfied": bool(default_off_retained),
            "blocking": not bool(default_off_retained),
            "detail": "This collection artifact remains explicit default-off and does not imply runtime enablement.",
        },
        {
            "gate_id": "actual_reviewer_signed_record_collected",
            "satisfied": False,
            "blocking": False,
            "detail": NO_ACTUAL_RECORD_DETAIL,
        },
    ]
    gates.extend(carry_forward_gate_entries)

    checks = [
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
            "signoff_record_validator_present",
            "pass" if signoff_record_validator_present else "fail",
            "signoff record validator loaded"
            if signoff_record_validator_present
            else signoff_record_validator_error
            or (
                f"unexpected_source:{validator_meta.get('source')}"
                if signoff_record_validator_report is not None
                else f"missing:{_display_path(project_root, signoff_record_validator_resolved)}"
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
            "signoff_record_validator_ready",
            "pass" if signoff_record_validator_ready else "fail",
            str(signoff_record_validator_ready),
        ),
        _check(
            "target_record_identity_defined",
            "pass" if target_identity_defined else "fail",
            record_identity or "missing",
        ),
        _check(
            "expected_collection_source_defined",
            "pass" if expected_collection_source_defined else "fail",
            "signoff_record_scaffold.pending_signoff_record_payload -> "
            "reviewer_record_prep.required_record_fields -> "
            "signoff_record_validator.validator_rules"
            if expected_collection_source_defined
            else "missing_scaffold_payload_or_preserved_contract",
        ),
        _check(
            "handoff_path_shape_defined",
            "pass" if handoff_path_shape_defined else "fail",
            handoff_path_shape or "missing",
        ),
        _check(
            "required_record_fields_preserved",
            "pass" if required_record_fields_preserved else "fail",
            ",".join(
                str(entry.get("field"))
                for entry in required_record_fields
                if entry.get("field")
            )
            if required_record_fields_preserved
            else "missing",
        ),
        _check(
            "required_reviewer_statement_ids_preserved",
            "pass" if required_statement_ids_preserved else "fail",
            ",".join(required_statement_ids) if required_statement_ids_preserved else "missing",
        ),
        _check(
            "still_blocked_gate_ids_preserved",
            "pass" if still_blocked_gate_ids_preserved else "fail",
            ",".join(carry_forward_still_blocked_gate_ids)
            if still_blocked_gate_ids_preserved
            else "missing",
        ),
        _check(
            "validator_rules_ready",
            "pass" if validator_rules_ready else "fail",
            "required_fields,agreed_statement_ids,still_blocked_gate_ids"
            if validator_rules_ready
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
        _check(
            "actual_reviewer_record_not_collected_yet",
            "pass",
            NO_ACTUAL_RECORD_DETAIL,
        ),
    ]

    reviewer_record_collection_ready = all(check["status"] == "pass" for check in checks)
    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    handoff_recommendation = (
        "Reviewer-record collection contract is ready: ask a reviewer to manually "
        "fill the scaffolded payload, preserve the required fields/reviewer "
        "statement ids/still-blocked gate ids, write the completed JSON to the "
        "locked handoff path shape, and then run a separate validation or ingest "
        "step while keeping reviewed_runtime_patch_exists=false and runtime "
        "disabled/default-off until that later step succeeds."
        if reviewer_record_collection_ready
        else "Reviewer-record collection contract is blocked; repair the missing "
        "scaffold/reviewer-prep/signoff-validator prerequisites before requesting "
        "any future manual reviewer-side collection."
    )

    return {
        "metadata": {
            "source": REVIEWER_RECORD_COLLECTION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_reviewer_record_collection_contract_not_actual_record",
            "review_only": True,
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
            "signoff_record_validator": _display_path(
                project_root, signoff_record_validator_resolved
            ),
            "future_reviewer_record_handoff_dir": _display_path(
                project_root, reviewer_record_handoff_dir
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "reviewer_record_collection_ready": bool(reviewer_record_collection_ready),
            "actual_reviewer_record_collected": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "collection_phase": "review_only_contract_only",
            "recommended_next_step": (
                "manually_collect_reviewer_signed_record_then_run_separate_validation_without_enablement"
                if reviewer_record_collection_ready
                else "repair_reviewer_record_collection_inputs"
            ),
            "handoff_recommendation": handoff_recommendation,
        },
        "reviewer_record_collection": {
            "target_record_identity": {
                "record_identity": record_identity,
                "record_type": target_record_type,
                "scope": scope,
                "candidate_key": candidate_key or None,
                "anchor_idx": anchor_idx,
            },
            "expected_collection_source": {
                "collection_mode": "manual_reviewer_side_collection_only",
                "collection_phase": "review_only",
                "source_artifact_chain": [
                    "signoff_record_scaffold.pending_signoff_record_payload",
                    "reviewer_record_prep.required_record_fields",
                    "signoff_record_validator.validator_rules",
                ],
                "base_payload_template": dict(pending_signoff_record_payload),
                "detail": MANUAL_COLLECTION_SOURCE_DETAIL,
            },
            "expected_handoff": {
                "handoff_format": "json",
                "handoff_dir": _display_path(project_root, reviewer_record_handoff_dir),
                "handoff_path_shape": handoff_path_shape,
                "handoff_filename_tokens": handoff_filename_tokens,
                "detail": HANDOFF_DETAIL,
            },
            "upstream_dependencies": [
                {
                    "artifact_id": "signoff_record_scaffold",
                    "path": _display_path(project_root, signoff_record_scaffold_resolved),
                    "required_source": SIGNOFF_RECORD_SCAFFOLD_SOURCE,
                    "required_ready_status": "signoff_record_scaffold_ready",
                    "ready": bool(signoff_record_scaffold_ready),
                    "role": "Provides the pending signoff payload template, required reviewer statement ids, and scaffolded record fields.",
                },
                {
                    "artifact_id": "reviewer_record_prep",
                    "path": _display_path(project_root, reviewer_record_prep_resolved),
                    "required_source": REVIEWER_RECORD_PREP_SOURCE,
                    "required_ready_status": "reviewer_record_prep_ready",
                    "ready": bool(reviewer_record_prep_ready),
                    "role": "Carries the preserved reviewer-owned record fields that still need manual completion.",
                },
                {
                    "artifact_id": "signoff_record_validator",
                    "path": _display_path(project_root, signoff_record_validator_resolved),
                    "required_source": SIGNOFF_RECORD_VALIDATOR_SOURCE,
                    "required_ready_status": "signoff_record_validator_ready",
                    "ready": bool(signoff_record_validator_ready),
                    "role": "Locks the future validation rules for required fields, reviewer statement ids, and still-blocked gate ids.",
                },
            ],
            "preserved_contract": {
                "required_record_fields": [dict(entry) for entry in required_record_fields],
                "required_reviewer_statement_ids": list(required_statement_ids),
                "still_blocked_gate_ids": list(carry_forward_still_blocked_gate_ids),
                "validator_rules": {
                    "required_fields": [dict(entry) for entry in validator_required_fields],
                    "agreed_statement_ids": agreed_statement_ids_rule,
                    "still_blocked_gate_ids": still_blocked_gate_ids_rule,
                },
            },
            "collection_state": {
                "actual_record_collected": False,
                "reviewer_signed_record_present": False,
                "collection_status": "not_collected",
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "detail": NO_ACTUAL_RECORD_DETAIL,
            },
            "collection_notice": COLLECTION_NOTICE,
            "recommended_manual_next_step": (
                "Have the reviewer manually complete the scaffolded signoff record payload, "
                "place the completed JSON at the expected handoff path shape, and then hand "
                "it to a later validation or ingest step without enabling runtime."
            ),
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    collection = _mapping(report.get("reviewer_record_collection"))
    target_identity = _mapping(collection.get("target_record_identity"))
    expected_collection_source = _mapping(collection.get("expected_collection_source"))
    expected_handoff = _mapping(collection.get("expected_handoff"))
    preserved_contract = _mapping(collection.get("preserved_contract"))
    collection_state = _mapping(collection.get("collection_state"))
    validator_rules = _mapping(preserved_contract.get("validator_rules"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Reviewer Record Collection",
        "",
        f"- Reviewer record collection ready: `{status.get('reviewer_record_collection_ready')}`",
        f"- Actual reviewer record collected: `{status.get('actual_reviewer_record_collected')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Collection phase: `{status.get('collection_phase')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Collection notice: {collection.get('collection_notice')}",
        "",
        "## Target Record Identity",
        "",
        f"- Record identity: `{target_identity.get('record_identity')}`",
        f"- Record type: `{target_identity.get('record_type')}`",
        f"- Scope: `{target_identity.get('scope')}`",
        f"- Candidate key: `{target_identity.get('candidate_key')}`",
        f"- Anchor idx: `{target_identity.get('anchor_idx')}`",
        "",
        "## Expected Collection Source",
        "",
        f"- Collection mode: `{expected_collection_source.get('collection_mode')}`",
        f"- Collection phase: `{expected_collection_source.get('collection_phase')}`",
        f"- Source artifact chain: `{', '.join(_string_list(expected_collection_source.get('source_artifact_chain'))) or '(none)'}`",
        f"- Detail: {expected_collection_source.get('detail')}",
        "",
        "## Expected Handoff",
        "",
        f"- Handoff format: `{expected_handoff.get('handoff_format')}`",
        f"- Handoff dir: `{expected_handoff.get('handoff_dir')}`",
        f"- Handoff path shape: `{expected_handoff.get('handoff_path_shape')}`",
        f"- Filename tokens: `{', '.join(_string_list(expected_handoff.get('handoff_filename_tokens'))) or '(none)'}`",
        f"- Detail: {expected_handoff.get('detail')}",
        "",
        "## Upstream Dependencies",
        "",
        "| Artifact | Ready | Path | Role |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(collection.get("upstream_dependencies", [])):
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
            "## Preserved Required Record Fields",
            "",
            "| Field | Required | Template value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(preserved_contract.get("required_record_fields", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(entry.get('template_value'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Preserved Contract",
            "",
            f"- Required reviewer statement ids: `{', '.join(_string_list(preserved_contract.get('required_reviewer_statement_ids'))) or '(none)'}`",
            f"- Still blocked gate ids: `{', '.join(_string_list(preserved_contract.get('still_blocked_gate_ids'))) or '(none)'}`",
            f"- Validator agreed_statement_ids rule: `{_mapping(validator_rules.get('agreed_statement_ids')).get('validation_rule')}`",
            f"- Validator still_blocked_gate_ids rule: `{_mapping(validator_rules.get('still_blocked_gate_ids')).get('validation_rule')}`",
            "",
            "## Collection State",
            "",
            f"- Actual record collected: `{collection_state.get('actual_record_collected')}`",
            f"- Reviewer-signed record present: `{collection_state.get('reviewer_signed_record_present')}`",
            f"- Collection status: `{collection_state.get('collection_status')}`",
            f"- Reviewed runtime patch exists: `{collection_state.get('reviewed_runtime_patch_exists')}`",
            f"- Runtime enablement allowed: `{collection_state.get('runtime_enablement_allowed')}`",
            f"- Detail: {collection_state.get('detail')}",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    collection = _mapping(report.get("reviewer_record_collection"))
    target_identity = _mapping(collection.get("target_record_identity"))
    expected_handoff = _mapping(collection.get("expected_handoff"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain reviewer record collection",
            f"reviewer_record_collection_ready={status.get('reviewer_record_collection_ready')}",
            f"actual_reviewer_record_collected={status.get('actual_reviewer_record_collected')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            f"record_identity={target_identity.get('record_identity')}",
            f"handoff_path_shape={expected_handoff.get('handoff_path_shape')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_reviewer_record_collection",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_record_identity(
    record_type: Any, *, candidate_key: str, anchor_idx: Any
) -> str:
    record_type_text = str(record_type or "").strip()
    anchor_text = str(anchor_idx).strip() if anchor_idx is not None else ""
    parts = [part for part in [record_type_text, candidate_key, f"anchor_{anchor_text}" if anchor_text else ""] if part]
    return "::".join(parts)


def _build_handoff_path_shape(
    project_root: Path,
    reviewer_record_handoff_dir: Path,
    *,
    target_record_type: Any,
    candidate_key: str,
    anchor_idx: Any,
) -> str:
    handoff_dir = _display_path(project_root, reviewer_record_handoff_dir)
    record_type_token = _slug_token(target_record_type) or "reviewed_runtime_patch_signoff_record"
    candidate_token = _slug_token(candidate_key) or "<candidate_key>"
    anchor_token = _slug_token(anchor_idx) or "<anchor_idx>"
    filename = (
        f"anchor119_row_domain_{record_type_token}"
        f"__candidate_{candidate_token}"
        f"__anchor_{anchor_token}"
        "__reviewer_<reviewer_id>"
        "__reviewed_at_<reviewed_at_utc>.json"
    )
    return f"{handoff_dir}/{filename}"


def _build_handoff_filename_tokens(
    *, target_record_type: Any, candidate_key: str, anchor_idx: Any
) -> list[str]:
    return [
        f"record_type_{_slug_token(target_record_type) or '<record_type>'}",
        f"candidate_{_slug_token(candidate_key) or '<candidate_key>'}",
        f"anchor_{_slug_token(anchor_idx) or '<anchor_idx>'}",
        "reviewer_<reviewer_id>",
        "reviewed_at_<reviewed_at_utc>",
    ]


def _slug_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    chars: list[str] = []
    for char in text:
        if char.isalnum():
            chars.append(char.lower())
        else:
            chars.append("_")
    return "".join(chars).strip("_")


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


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.b5a.coordinate_validation_reason_localization import (
    B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.readiness import (
    B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.review_state import (
    B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.validator import (
    B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
)
from src.search.phase3b.b5a.certification_contracts import (
    AUTHORIZATION_SAFETY_FALSE_FIELDS,
    CORE_B5A_SAFETY_FALSE_FIELDS,
    PREFLIGHT_MUTATION_FALSE_FIELDS,
    REVIEW_PAYLOAD_REQUIRED_FALSE_FIELDS,
    blocking_checks_pass,
    false_field_detail,
    required_false,
)

B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE = (
    "phase3b_b5a_certified_anchor_promotion_review_packet_v1"
)

POST_ACCEPTANCE_BLOCKER_SUMMARY_SOURCE = (
    "phase3b_b5a_post_acceptance_blocker_summary_v1"
)

DEFAULT_REVIEW_STATE_PATH = Path(
    ".artifacts/phase3b_b5a_localized_evidence_review_state_20260425/"
    "b5a_localized_evidence_review_state.json"
)
DEFAULT_LOCALIZED_EVIDENCE_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_b5a_localized_evidence_validator_20260425/"
    "b5a_localized_evidence_validator.json"
)
DEFAULT_LOCALIZED_EVIDENCE_READINESS_PATH = Path(
    ".artifacts/phase3b_b5a_localized_evidence_readiness_20260425/"
    "b5a_localized_evidence_readiness.json"
)
DEFAULT_REASON_LOCALIZATION_PATH = Path(
    ".artifacts/phase3b_b5a_coordinate_validation_reason_localization_20260425/"
    "b5a_coordinate_validation_reason_localization.json"
)
DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH = Path(
    ".artifacts/phase3b_b5a_post_acceptance_blocker_summary_20260425/"
    "b5a_post_acceptance_blocker_summary.json"
)

EXPECTED_PROMOTION_REVIEW_RECORD_TYPE = (
    "b5a_certified_anchor_promotion_review_record_v0"
)
EXPECTED_CANDIDATE = "67x13"
EXPECTED_COVERED_ANCHORS = [118, 119, 120, 121, 122, 123, 124, 125]
EXPECTED_SIGNATURE_ANCHORS = [119, 120, 121, 122, 123, 124, 125]
EXPECTED_SCOPE = (
    "candidate=67x13, anchors=118-125, "
    "b5a_certified_anchor_promotion_review"
)
EXPECTED_STILL_BLOCKED_GATE_IDS = ["b5a_anchor_found"]
EXPECTED_REQUIRED_ACCEPTANCE_IDS = [
    "source_review_state_ready",
    "current_localized_evidence_validator_ready",
    "anchor118_ghost_overlap_auxiliary_promotion_evidence",
    "anchors119_125_signature_monotonic_primary_promotion_evidence",
    "localized_reason_coverage_complete_for_anchors118_125",
    "post_acceptance_only_b5a_anchor_found_blocked",
    "no_runtime_final_checkpoint_release_authorization",
]
EXPECTED_FORBIDDEN_CONCLUSIONS = [
    "runtime_elimination_authorized",
    "final_168h_authorized",
    "checkpoint_write_or_import_back_authorized",
    "release_viewer_frontdoor_status_promoted",
    "preflight_gate_mutated",
    "b5a_anchor_found_changed_by_packet",
    "certified_anchor_found_without_separate_gate_marker",
]


def build_phase3b_b5a_certified_anchor_promotion_review_packet(
    project_root: Path,
    *,
    review_state_path: Optional[Path] = None,
    localized_evidence_validator_path: Optional[Path] = None,
    localized_evidence_readiness_path: Optional[Path] = None,
    reason_localization_path: Optional[Path] = None,
    post_acceptance_blocker_summary_path: Optional[Path] = None,
    promotion_review_payload_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    review_state_resolved = _resolve_path(
        project_root,
        review_state_path if review_state_path is not None else DEFAULT_REVIEW_STATE_PATH,
    )
    validator_resolved = _resolve_path(
        project_root,
        (
            localized_evidence_validator_path
            if localized_evidence_validator_path is not None
            else DEFAULT_LOCALIZED_EVIDENCE_VALIDATOR_PATH
        ),
    )
    readiness_resolved = _resolve_path(
        project_root,
        (
            localized_evidence_readiness_path
            if localized_evidence_readiness_path is not None
            else DEFAULT_LOCALIZED_EVIDENCE_READINESS_PATH
        ),
    )
    reason_resolved = _resolve_path(
        project_root,
        (
            reason_localization_path
            if reason_localization_path is not None
            else DEFAULT_REASON_LOCALIZATION_PATH
        ),
    )
    post_resolved = _resolve_path(
        project_root,
        (
            post_acceptance_blocker_summary_path
            if post_acceptance_blocker_summary_path is not None
            else DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH
        ),
    )

    review_state_report, review_state_error = _load_json_mapping(review_state_resolved)
    validator_report, validator_error = _load_json_mapping(validator_resolved)
    readiness_report, readiness_error = _load_json_mapping(readiness_resolved)
    reason_report, reason_error = _load_json_mapping(reason_resolved)
    post_report, post_error = _load_json_mapping(post_resolved)

    review_state_meta = _mapping(review_state_report.get("metadata")) if review_state_report else {}
    review_state_status = _mapping(review_state_report.get("status")) if review_state_report else {}
    review_state_candidate = _mapping(review_state_report.get("candidate")) if review_state_report else {}
    review_state_payload = _mapping(review_state_report.get("review_state")) if review_state_report else {}

    validator_meta = _mapping(validator_report.get("metadata")) if validator_report else {}
    validator_status = _mapping(validator_report.get("status")) if validator_report else {}
    validator_candidate = _mapping(validator_report.get("candidate")) if validator_report else {}
    validator_payload = (
        _mapping(validator_report.get("localized_evidence_validator"))
        if validator_report
        else {}
    )
    accepted_lanes = _accepted_lane_by_id(validator_payload)

    readiness_meta = _mapping(readiness_report.get("metadata")) if readiness_report else {}
    readiness_status = _mapping(readiness_report.get("status")) if readiness_report else {}
    readiness_candidate = _mapping(readiness_report.get("candidate")) if readiness_report else {}
    readiness_lanes = _lane_by_id(readiness_report.get("lanes") if readiness_report else [])
    old_precedent_policy = (
        _mapping(readiness_report.get("old_signature_precedent_policy"))
        if readiness_report
        else {}
    )

    reason_meta = _mapping(reason_report.get("metadata")) if reason_report else {}
    reason_status = _mapping(reason_report.get("status")) if reason_report else {}
    reason_candidate = _mapping(reason_report.get("candidate")) if reason_report else {}
    reason_payload = _mapping(reason_report.get("reason_localization")) if reason_report else {}

    post_meta = _mapping(post_report.get("metadata")) if post_report else {}
    post_status = _mapping(post_report.get("status")) if post_report else {}

    review_state_chain_ok = _review_state_chain_ok(
        review_state_meta, review_state_status, review_state_candidate, review_state_payload
    )
    validator_chain_ok = _validator_chain_ok(
        validator_meta, validator_status, validator_candidate, accepted_lanes
    )
    readiness_chain_ok = _readiness_chain_ok(
        readiness_meta,
        readiness_status,
        readiness_candidate,
        readiness_lanes,
        old_precedent_policy,
    )
    reason_chain_ok = _reason_chain_ok(
        reason_meta, reason_status, reason_candidate, reason_payload
    )
    post_acceptance_chain_ok = _post_acceptance_chain_ok(
        post_meta,
        post_status,
        post_report.get("checks") if post_report else None,
    )

    packet_checks = [
        _check(
            "review_state_present",
            review_state_report is not None and review_state_error is None,
            (
                "review-state artifact loaded"
                if review_state_report is not None and review_state_error is None
                else review_state_error
                or f"missing:{_display_path(project_root, review_state_resolved)}"
            ),
        ),
        _check(
            "review_state_ready_and_safe",
            review_state_chain_ok,
            _review_state_detail(
                review_state_meta,
                review_state_status,
                review_state_candidate,
                review_state_payload,
            ),
        ),
        _check(
            "localized_evidence_validator_present",
            validator_report is not None and validator_error is None,
            (
                "localized-evidence validator loaded"
                if validator_report is not None and validator_error is None
                else validator_error
                or f"missing:{_display_path(project_root, validator_resolved)}"
            ),
        ),
        _check(
            "localized_evidence_validator_ready_and_safe",
            validator_chain_ok,
            _validator_detail(validator_meta, validator_status, validator_candidate, accepted_lanes),
        ),
        _check(
            "localized_evidence_readiness_present",
            readiness_report is not None and readiness_error is None,
            (
                "localized-evidence readiness loaded"
                if readiness_report is not None and readiness_error is None
                else readiness_error
                or f"missing:{_display_path(project_root, readiness_resolved)}"
            ),
        ),
        _check(
            "localized_evidence_readiness_current_source",
            readiness_chain_ok,
            _readiness_detail(
                readiness_meta,
                readiness_status,
                readiness_candidate,
                readiness_lanes,
                old_precedent_policy,
            ),
        ),
        _check(
            "reason_localization_present",
            reason_report is not None and reason_error is None,
            (
                "reason-localization artifact loaded"
                if reason_report is not None and reason_error is None
                else reason_error
                or f"missing:{_display_path(project_root, reason_resolved)}"
            ),
        ),
        _check(
            "reason_localization_complete_for_anchors118_125",
            reason_chain_ok,
            _reason_detail(reason_meta, reason_status, reason_candidate, reason_payload),
        ),
        _check(
            "post_acceptance_only_b5a_anchor_blocked",
            post_acceptance_chain_ok,
            _post_detail(post_meta, post_status),
        ),
    ]
    promotion_review_packet_ready = all(
        check["status"] == "pass" for check in packet_checks
    )

    payload_resolved = (
        _resolve_path(project_root, promotion_review_payload_path)
        if promotion_review_payload_path is not None
        else None
    )
    payload_validation = _validate_optional_promotion_review_payload(
        payload_resolved,
        packet_ready=promotion_review_packet_ready,
    )
    payload_provided = bool(payload_resolved is not None)
    payload_validated = bool(payload_validation.get("record_payload_validated", False))
    promotion_review_accepted = bool(
        payload_validated
        and payload_validation.get("certified_anchor_promotion_review_accepted") is True
    )

    return {
        "metadata": {
            "source": B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "certified_anchor_promotion_review_contract_not_b5a_gate_integration"
            ),
            "review_only": True,
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "preflight_gate_mutated": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
        },
        "paths": {
            "project_root": str(project_root),
            "review_state": _display_path(project_root, review_state_resolved),
            "localized_evidence_validator": _display_path(
                project_root, validator_resolved
            ),
            "localized_evidence_readiness": _display_path(
                project_root, readiness_resolved
            ),
            "reason_localization": _display_path(project_root, reason_resolved),
            "post_acceptance_blocker_summary": _display_path(project_root, post_resolved),
            "promotion_review_payload": (
                _display_path(project_root, payload_resolved)
                if payload_resolved is not None
                else None
            ),
        },
        "candidate": {
            "candidate_key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "scope": EXPECTED_SCOPE,
        },
        "inputs": {
            "review_state": _input_state(
                review_state_report, review_state_error, review_state_chain_ok
            ),
            "localized_evidence_validator": _input_state(
                validator_report, validator_error, validator_chain_ok
            ),
            "localized_evidence_readiness": _input_state(
                readiness_report, readiness_error, readiness_chain_ok
            ),
            "reason_localization": _input_state(
                reason_report, reason_error, reason_chain_ok
            ),
            "post_acceptance_blocker_summary": _input_state(
                post_report, post_error, post_acceptance_chain_ok
            ),
            "promotion_review_payload": {
                "provided": payload_provided,
                "path": (
                    _display_path(project_root, payload_resolved)
                    if payload_resolved is not None
                    else None
                ),
            },
        },
        "status": {
            "promotion_review_packet_ready": bool(promotion_review_packet_ready),
            "promotion_review_record_validator_ready": bool(
                promotion_review_packet_ready
            ),
            "promotion_review_payload_provided": bool(payload_provided),
            "promotion_review_payload_validated": bool(payload_validated),
            "promotion_review_payload_validation_status": str(
                payload_validation.get("validation_status")
            ),
            "certified_anchor_promotion_review_accepted": bool(
                promotion_review_accepted
            ),
            "source_review_state_ready": bool(review_state_chain_ok),
            "b5a_localized_evidence_reviewed": bool(
                review_state_status.get("b5a_localized_evidence_reviewed") is True
            ),
            "reviewer_acceptance_required": True,
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            "preflight_gate_mutated": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
            "recommended_next_step": _recommended_next_step(
                promotion_review_packet_ready, payload_provided, payload_validated
            ),
            "outcome": _outcome(
                promotion_review_packet_ready, payload_provided, payload_validated
            ),
        },
        "promotion_review_packet": {
            "record_contract": _record_contract(),
            "reviewer_payload_template": _reviewer_payload_template(),
            "external_reviewer_request_text": _external_reviewer_request_text(),
            "source_chain_summary": {
                "review_state_source": review_state_meta.get("source"),
                "source_review_state_ready": bool(review_state_chain_ok),
                "localized_evidence_validator_source": validator_meta.get("source"),
                "localized_evidence_validator_ready": bool(validator_chain_ok),
                "localized_evidence_readiness_source": readiness_meta.get("source"),
                "localized_evidence_readiness_ready": bool(readiness_chain_ok),
                "reason_localization_source": reason_meta.get("source"),
                "reason_localization_ready": bool(reason_chain_ok),
                "post_acceptance_blocker_summary_source": post_meta.get("source"),
                "post_acceptance_only_b5a_anchor_blocked": bool(
                    post_acceptance_chain_ok
                ),
            },
        },
        "promotion_review_record_validator": {
            "validator_target": "future_or_supplied_b5a_certified_anchor_promotion_review_payload",
            "target_record_type": EXPECTED_PROMOTION_REVIEW_RECORD_TYPE,
            "scope": EXPECTED_SCOPE,
            "required_acceptance_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
            "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
            "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
            "actual_record_validation": payload_validation,
        },
        "checks": packet_checks,
    }


def render_phase3b_b5a_certified_anchor_promotion_review_packet_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    packet = _mapping(report.get("promotion_review_packet"))
    contract = _mapping(packet.get("record_contract"))
    validator = _mapping(report.get("promotion_review_record_validator"))
    actual = _mapping(validator.get("actual_record_validation"))
    lines = [
        "# Phase 3B B5A Certified-Anchor Promotion Review Packet",
        "",
        f"- Promotion review packet ready: `{status.get('promotion_review_packet_ready')}`",
        f"- Promotion review payload provided: `{status.get('promotion_review_payload_provided')}`",
        f"- Promotion review payload validated: `{status.get('promotion_review_payload_validated')}`",
        f"- Certified-anchor promotion review accepted: `{status.get('certified_anchor_promotion_review_accepted')}`",
        f"- B5A anchor found: `{status.get('b5a_anchor_found')}`",
        f"- Certified anchor found: `{status.get('certified_anchor_found')}`",
        f"- Proof source: `{status.get('proof_source')}`",
        f"- Runtime semantics changed: `{status.get('runtime_semantics_changed')}`",
        f"- Checkpoint written: `{status.get('checkpoint_written')}`",
        f"- Still blocked gate ids: `{status.get('still_blocked_gate_ids')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        "",
        "## Reviewer Record Contract",
        "",
        f"- Record type: `{contract.get('record_type')}`",
        f"- Scope: `{contract.get('scope')}`",
        f"- Candidate: `{contract.get('candidate_key')}`",
        f"- Covered anchors: `{contract.get('covered_anchors')}`",
        f"- Required verdict: `{contract.get('required_verdict')}`",
        "",
        "### Required Acceptance IDs",
        "",
    ]
    for acceptance_id in list(contract.get("required_acceptance_ids", [])):
        lines.append(f"- `{acceptance_id}`")
    lines.extend(["", "### Forbidden Conclusions", ""])
    for conclusion in list(contract.get("forbidden_conclusions", [])):
        lines.append(f"- `{conclusion}`")
    lines.extend(
        [
            "",
            "## External Reviewer Request Text",
            "",
            str(packet.get("external_reviewer_request_text", "")),
            "",
            "## Payload Validation",
            "",
            f"- Record payload validated: `{actual.get('record_payload_validated')}`",
            f"- Validation status: `{actual.get('validation_status')}`",
            f"- Failed rule count: `{actual.get('failed_rule_count')}`",
            "",
            "| Rule | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for rule in list(actual.get("rule_results", [])):
        if isinstance(rule, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(rule.get("rule_id")),
                        _markdown_cell(rule.get("status")),
                        _markdown_cell(rule.get("detail")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Packet Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_b5a_certified_anchor_promotion_review_packet_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B B5A certified-anchor promotion review packet",
        f"promotion_review_packet_ready={status.get('promotion_review_packet_ready')}",
        f"promotion_review_payload_provided={status.get('promotion_review_payload_provided')}",
        f"promotion_review_payload_validated={status.get('promotion_review_payload_validated')}",
        f"promotion_review_payload_validation_status={status.get('promotion_review_payload_validation_status')}",
        f"certified_anchor_promotion_review_accepted={status.get('certified_anchor_promotion_review_accepted')}",
        f"b5a_anchor_found={status.get('b5a_anchor_found')}",
        f"certified_anchor_found={status.get('certified_anchor_found')}",
        f"proof_source={status.get('proof_source')}",
        f"runtime_semantics_changed={status.get('runtime_semantics_changed')}",
        f"checkpoint_written={status.get('checkpoint_written')}",
        f"preflight_gate_mutated={status.get('preflight_gate_mutated')}",
        f"still_blocked_gate_ids={status.get('still_blocked_gate_ids')}",
        f"recommended_next_step={status.get('recommended_next_step')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check="
                + str(check.get("check_id"))
                + " status="
                + str(check.get("status"))
                + " detail="
                + str(check.get("detail"))
            )
    return "\n".join(lines) + "\n"


def write_phase3b_b5a_certified_anchor_promotion_review_packet(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "b5a_certified_anchor_promotion_review_packet",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    template_path = output_dir / "reviewer_payload_template.json"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(
        md_path,
        render_phase3b_b5a_certified_anchor_promotion_review_packet_markdown(report),
    )
    _atomic_write_text(
        txt_path,
        render_phase3b_b5a_certified_anchor_promotion_review_packet_text(report),
    )
    atomic_write_json(
        template_path,
        dict(_mapping(_mapping(report.get("promotion_review_packet")).get("reviewer_payload_template"))),
    )
    return {
        "json": str(json_path),
        "md": str(md_path),
        "txt": str(txt_path),
        "reviewer_payload_template": str(template_path),
    }


def _review_state_chain_ok(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> bool:
    return bool(
        meta.get("source") == B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE
        and status.get("review_state_ready") is True
        and status.get("repo_side_review_state_updated") is True
        and status.get("b5a_localized_evidence_reviewed") is True
        and status.get("review_record_payload_validated") is True
        and candidate.get("key") == EXPECTED_CANDIDATE
        and _int_list(candidate.get("covered_anchors")) == EXPECTED_COVERED_ANCHORS
        and payload.get("review_state_ready") is True
        and payload.get("b5a_localized_evidence_reviewed") is True
        and _int_list(payload.get("covered_anchors")) == EXPECTED_COVERED_ANCHORS
        and _string_list(status.get("still_blocked_gate_ids"))
        == EXPECTED_STILL_BLOCKED_GATE_IDS
        and required_false(meta, _safety_fields(include_solver=True))
        and required_false(status, _safety_fields(include_solver=False))
        and required_false(payload, _safety_fields(include_solver=False))
    )


def _validator_chain_ok(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    accepted_lanes: Mapping[str, Mapping[str, Any]],
) -> bool:
    return bool(
        meta.get("source") == B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE
        and status.get("localized_evidence_validator_ready") is True
        and status.get("current_localized_evidence_validated") is True
        and status.get("reviewer_acceptance_required") is True
        and candidate.get("expected_key") == EXPECTED_CANDIDATE
        and candidate.get("localized_key") == EXPECTED_CANDIDATE
        and candidate.get("matches") is True
        and _lane_matches(
            accepted_lanes.get("anchor118_ghost_overlap_forced_domain", {}),
            role="auxiliary_cross_evidence",
            category="ghost_overlap_forced_domain",
            anchors=[118],
        )
        and _lane_matches(
            accepted_lanes.get(
                "anchors119_125_signature_monotonic_forced_label", {}
            ),
            role="primary_coverage_evidence",
            category="signature_monotonic_forced_label",
            anchors=EXPECTED_SIGNATURE_ANCHORS,
        )
        and required_false(meta, _safety_fields(include_solver=True))
        and required_false(status, _safety_fields(include_solver=False))
    )


def _readiness_chain_ok(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    lanes: Mapping[str, Mapping[str, Any]],
    old_precedent_policy: Mapping[str, Any],
) -> bool:
    return bool(
        meta.get("source") == B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE
        and status.get("readiness_ready") is True
        and candidate.get("expected_key") == EXPECTED_CANDIDATE
        and candidate.get("localized_key") == EXPECTED_CANDIDATE
        and candidate.get("matches") is True
        and _readiness_lane_matches(
            lanes.get("anchor118_ghost_overlap_forced_domain", {}),
            category="ghost_overlap_forced_domain",
            anchors=[118],
        )
        and _readiness_lane_matches(
            lanes.get("anchors119_125_signature_monotonic_forced_label", {}),
            category="signature_monotonic_forced_label",
            anchors=EXPECTED_SIGNATURE_ANCHORS,
        )
        and old_precedent_policy.get(
            "old_m6x4_signature_artifact_used_as_current_b5a_evidence"
        )
        is False
        and required_false(meta, _safety_fields(include_solver=True))
        and required_false(status, _safety_fields(include_solver=False))
    )


def _reason_chain_ok(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> bool:
    rows = list(payload.get("anchor_rows", []))
    categories = _category_by_anchor(rows)
    localized_key_matches = (
        "localized_key" not in candidate
        or str(candidate.get("localized_key") or "").strip() == EXPECTED_CANDIDATE
    )
    candidate_matches = (
        str(candidate.get("key") or "").strip() == EXPECTED_CANDIDATE
        and str(candidate.get("expected_key") or "").strip() == EXPECTED_CANDIDATE
        and candidate.get("matches_expected") is True
        and localized_key_matches
    )
    return bool(
        meta.get("source") == B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE
        and status.get("reason_localization_ready") is True
        and int(status.get("localized_anchor_count", -1)) == 8
        and int(status.get("requested_anchor_count", -1)) == 8
        and int(status.get("generic_anchor_count", -1)) == 0
        and int(status.get("unknown_anchor_count", -1)) == 0
        and candidate_matches
        and categories.get(118) == "ghost_overlap_forced_domain"
        and all(
            categories.get(anchor) == "signature_monotonic_forced_label"
            for anchor in EXPECTED_SIGNATURE_ANCHORS
        )
        and required_false(meta, _safety_fields(include_solver=True))
        and required_false(status, _safety_fields(include_solver=False))
    )


def _post_acceptance_chain_ok(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    checks: Any = None,
) -> bool:
    return bool(
        meta.get("source") == POST_ACCEPTANCE_BLOCKER_SUMMARY_SOURCE
        and status.get("summary_ready") is True
        and status.get("reviewed_runtime_patch_exists") is True
        and status.get("production_acceptance_refresh_completed") is True
        and status.get("runtime_enablement_allowed") is False
        and status.get("preflight_ready") is False
        and status.get("only_b5a_anchor_found_failed") is True
        and _string_list(status.get("failed_checks")) == EXPECTED_STILL_BLOCKED_GATE_IDS
        and status.get("b5a_anchor_found") is False
        and required_false(meta, _safety_fields(include_solver=True))
        and required_false(status, _safety_fields(include_solver=False))
        and blocking_checks_pass(checks)
    )


def _validate_optional_promotion_review_payload(
    payload_path: Optional[Path],
    *,
    packet_ready: bool,
) -> Dict[str, Any]:
    if payload_path is None:
        return {
            "record_payload_provided": False,
            "record_payload_validated": False,
            "certified_anchor_promotion_review_accepted": False,
            "validation_status": "not_run",
            "failed_rule_count": 0,
            "failed_rule_ids": [],
            "rule_results": [],
        }
    if not packet_ready:
        return {
            "record_payload_provided": True,
            "record_payload_validated": False,
            "certified_anchor_promotion_review_accepted": False,
            "validation_status": "contract_blocked",
            "failed_rule_count": 1,
            "failed_rule_ids": ["promotion_review_packet_ready"],
            "rule_results": [
                _rule(
                    "promotion_review_packet_ready",
                    False,
                    "Cannot validate a promotion payload until packet contract is ready.",
                )
            ],
        }
    payload, error = _load_json_mapping(payload_path)
    if payload is None:
        return {
            "record_payload_provided": True,
            "record_payload_validated": False,
            "certified_anchor_promotion_review_accepted": False,
            "validation_status": "load_error",
            "failed_rule_count": 1,
            "failed_rule_ids": ["promotion_review_payload_loadable"],
            "rule_results": [
                _rule(
                    "promotion_review_payload_loadable",
                    False,
                    error or "payload is missing or not a JSON object",
                )
            ],
        }

    accepted = payload.get("certified_anchor_promotion_review_accepted") is True
    rule_results = [
        _rule(
            "record_type",
            payload.get("record_type") == EXPECTED_PROMOTION_REVIEW_RECORD_TYPE,
            str(payload.get("record_type")),
        ),
        _rule("scope", payload.get("scope") == EXPECTED_SCOPE, str(payload.get("scope"))),
        _rule(
            "candidate_key",
            payload.get("candidate_key") == EXPECTED_CANDIDATE,
            str(payload.get("candidate_key")),
        ),
        _rule(
            "covered_anchors",
            _int_list(payload.get("covered_anchors")) == EXPECTED_COVERED_ANCHORS,
            str(payload.get("covered_anchors")),
        ),
        _rule(
            "source_review_state_ready",
            payload.get("source_review_state_ready") is True,
            str(payload.get("source_review_state_ready")),
        ),
        _rule(
            "verdict_accepts_certified_anchor_promotion_review",
            str(payload.get("verdict") or "").strip()
            == "accepted_for_certified_anchor_promotion",
            str(payload.get("verdict")),
        ),
        _rule(
            "certified_anchor_promotion_review_accepted",
            accepted,
            str(payload.get("certified_anchor_promotion_review_accepted")),
        ),
        _rule(
            "accepted_statement_ids",
            _string_list(payload.get("accepted_statement_ids"))
            == EXPECTED_REQUIRED_ACCEPTANCE_IDS,
            str(payload.get("accepted_statement_ids")),
        ),
        _rule(
            "forbidden_conclusions_rejected",
            _string_list(payload.get("forbidden_conclusions_rejected"))
            == EXPECTED_FORBIDDEN_CONCLUSIONS,
            str(payload.get("forbidden_conclusions_rejected")),
        ),
        _rule(
            "still_blocked_gate_ids",
            _string_list(payload.get("still_blocked_gate_ids"))
            == EXPECTED_STILL_BLOCKED_GATE_IDS,
            str(payload.get("still_blocked_gate_ids")),
        ),
        _rule(
            "reviewer_id_present",
            bool(str(payload.get("reviewer_id") or "").strip()),
            str(payload.get("reviewer_id")),
        ),
        _rule(
            "reviewed_at_utc_iso",
            _is_utc_iso(str(payload.get("reviewed_at") or "")),
            str(payload.get("reviewed_at")),
        ),
        _rule(
            "no_forbidden_positive_flags",
            required_false(payload, _forbidden_bool_fields()),
            _forbidden_flag_detail(payload),
        ),
    ]
    failed_rule_ids = [
        str(rule.get("rule_id"))
        for rule in rule_results
        if rule.get("status") == "fail"
    ]
    record_payload_validated = len(failed_rule_ids) == 0
    return {
        "record_payload_provided": True,
        "record_payload_validated": bool(record_payload_validated),
        "certified_anchor_promotion_review_accepted": bool(
            record_payload_validated and accepted
        ),
        "validation_status": "passed" if record_payload_validated else "failed",
        "failed_rule_count": len(failed_rule_ids),
        "failed_rule_ids": failed_rule_ids,
        "rule_results": rule_results,
    }


def _record_contract() -> Dict[str, Any]:
    return {
        "record_type": EXPECTED_PROMOTION_REVIEW_RECORD_TYPE,
        "scope": EXPECTED_SCOPE,
        "candidate_key": EXPECTED_CANDIDATE,
        "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
        "source_review_state_ready": True,
        "required_verdict": "accepted_for_certified_anchor_promotion",
        "required_acceptance_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
        "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
        "required_fields": [
            "record_type",
            "scope",
            "candidate_key",
            "covered_anchors",
            "source_review_state_ready",
            "reviewer_id",
            "reviewed_at",
            "verdict",
            "certified_anchor_promotion_review_accepted",
            "accepted_statement_ids",
            "forbidden_conclusions_rejected",
            "still_blocked_gate_ids",
        ]
        + _forbidden_bool_fields(),
    }


def _reviewer_payload_template() -> Dict[str, Any]:
    return {
        "record_type": EXPECTED_PROMOTION_REVIEW_RECORD_TYPE,
        "scope": EXPECTED_SCOPE,
        "candidate_key": EXPECTED_CANDIDATE,
        "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
        "source_review_state_ready": True,
        "reviewer_id": "<reviewer id>",
        "reviewed_at": "<ISO-8601 UTC timestamp ending with Z>",
        "verdict": "accepted_for_certified_anchor_promotion",
        "certified_anchor_promotion_review_accepted": True,
        "accepted_statement_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
        "forbidden_conclusions_rejected": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "preflight_gate_mutated": False,
        "b5a_anchor_found": False,
        "certified_anchor_found": False,
        "proof_source": False,
        "runtime_semantics_changed": False,
        "candidate_elimination_claim": False,
        "checkpoint_written": False,
        "notes": (
            "Promotion review only. This record may be used by a later, separate "
            "B5A gate integration marker, but this packet does not mutate "
            "preflight, write checkpoints, or authorize final execution."
        ),
    }


def _external_reviewer_request_text() -> str:
    return (
        "Please review whether the already accepted Phase3B B5A localized "
        "evidence chain for candidate 67x13 and anchors 118-125 is sufficient "
        "to be promoted to certified B5A anchor evidence in a later, separate "
        "gate-integration step. If you accept that promotion review contract, "
        "return a machine-readable JSON payload with "
        f"record_type={EXPECTED_PROMOTION_REVIEW_RECORD_TYPE}, scope={EXPECTED_SCOPE}, "
        "verdict=accepted_for_certified_anchor_promotion, "
        "certified_anchor_promotion_review_accepted=true, all required "
        "acceptance ids, all forbidden conclusions rejected, and "
        "still_blocked_gate_ids=['b5a_anchor_found']. Do not authorize runtime "
        "elimination, final 168h execution, checkpoint write/import-back, "
        "release/viewer/frontdoor status promotion, or direct mutation of "
        "b5a_anchor_found in this packet."
    )


def _input_state(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
    chain_ok: bool,
) -> Dict[str, Any]:
    meta = _mapping(report.get("metadata")) if report else {}
    return {
        "present": bool(report is not None and error is None),
        "load_error": error,
        "source": meta.get("source"),
        "chain_ready": bool(chain_ok),
    }


def _accepted_lane_by_id(validator_payload: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    for lane in list(validator_payload.get("accepted_lanes", [])):
        if isinstance(lane, Mapping) and lane.get("lane_id"):
            result[str(lane.get("lane_id"))] = lane
    return result


def _lane_by_id(lanes: Any) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    for lane in list(lanes or []):
        if isinstance(lane, Mapping) and lane.get("lane_id"):
            result[str(lane.get("lane_id"))] = lane
    return result


def _lane_matches(
    lane: Mapping[str, Any],
    *,
    role: str,
    category: str,
    anchors: list[int],
) -> bool:
    return bool(
        lane
        and lane.get("role") == role
        and lane.get("category") == category
        and _int_list(lane.get("covered_anchors")) == anchors
        and lane.get("reviewer_acceptance_required") is True
        and lane.get("accepted_by_validator") is True
    )


def _readiness_lane_matches(
    lane: Mapping[str, Any],
    *,
    category: str,
    anchors: list[int],
) -> bool:
    return bool(
        lane
        and lane.get("category") == category
        and _int_list(lane.get("required_anchors")) == anchors
        and _int_list(lane.get("covered_anchors")) == anchors
        and lane.get("current_source_complete") is True
        and lane.get("probe_supports_lane") is True
        and lane.get("solver_free_inputs") is True
        and lane.get("proof_safe") is True
    )


def _category_by_anchor(rows: list[Any]) -> Dict[int, str]:
    result: Dict[int, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        try:
            anchor = int(row.get("anchor_idx"))
        except (TypeError, ValueError):
            continue
        result[anchor] = str(row.get("category") or "")
    return result


def _recommended_next_step(
    packet_ready: bool,
    payload_provided: bool,
    payload_validated: bool,
) -> str:
    if not packet_ready:
        return "repair_b5a_localized_evidence_review_state_or_evidence_chain"
    if payload_validated:
        return "build_separate_b5a_gate_integration_marker_after_promotion_review"
    if payload_provided:
        return "repair_b5a_certified_anchor_promotion_review_payload"
    return "send_b5a_certified_anchor_promotion_review_packet_to_external_or_manual_reviewer"


def _outcome(
    packet_ready: bool,
    payload_provided: bool,
    payload_validated: bool,
) -> str:
    if not packet_ready:
        return "b5a_certified_anchor_promotion_review_packet_blocked"
    if payload_validated:
        return "b5a_certified_anchor_promotion_review_payload_validated"
    if payload_provided:
        return "b5a_certified_anchor_promotion_review_payload_rejected"
    return "b5a_certified_anchor_promotion_review_packet_ready_waiting_for_reviewer_payload"


def _review_state_detail(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> str:
    return (
        f"source={meta.get('source')} "
        f"review_state_ready={status.get('review_state_ready')} "
        f"b5a_localized_evidence_reviewed={status.get('b5a_localized_evidence_reviewed')} "
        f"candidate={candidate.get('key')} anchors={candidate.get('covered_anchors')} "
        f"state_ready={payload.get('review_state_ready')} "
        f"safety={_safety_detail(meta, status, payload)}"
    )


def _validator_detail(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    lanes: Mapping[str, Mapping[str, Any]],
) -> str:
    return (
        f"source={meta.get('source')} "
        f"ready={status.get('localized_evidence_validator_ready')} "
        f"current_validated={status.get('current_localized_evidence_validated')} "
        f"candidate={candidate.get('localized_key')} "
        f"lanes={_lane_detail(lanes)} "
        f"safety={_safety_detail(meta, status)}"
    )


def _readiness_detail(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    lanes: Mapping[str, Mapping[str, Any]],
    old_precedent_policy: Mapping[str, Any],
) -> str:
    return (
        f"source={meta.get('source')} readiness_ready={status.get('readiness_ready')} "
        f"candidate={candidate.get('localized_key')} lanes={_lane_detail(lanes)} "
        "old_m6x4_used_as_current="
        + str(
            old_precedent_policy.get(
                "old_m6x4_signature_artifact_used_as_current_b5a_evidence"
            )
        )
        + f" safety={_safety_detail(meta, status)}"
    )


def _reason_detail(
    meta: Mapping[str, Any],
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> str:
    return (
        f"source={meta.get('source')} ready={status.get('reason_localization_ready')} "
        f"candidate={candidate.get('key')} localized={status.get('localized_anchor_count')} "
        f"generic={status.get('generic_anchor_count')} unknown={status.get('unknown_anchor_count')} "
        f"categories={payload.get('category_counts')} safety={_safety_detail(meta, status)}"
    )


def _post_detail(meta: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    return (
        f"source={meta.get('source')} summary_ready={status.get('summary_ready')} "
        f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')} "
        "production_acceptance_refresh_completed="
        + str(status.get("production_acceptance_refresh_completed"))
        + f" failed_checks={status.get('failed_checks')} "
        f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}"
    )


def _safety_detail(*mappings: Mapping[str, Any]) -> str:
    keys = _safety_fields(include_solver=True)
    parts: list[str] = []
    for index, mapping in enumerate(mappings):
        parts.append(
            "map"
            + str(index)
            + ":"
            + " ".join(f"{key}={bool(mapping.get(key, False))}" for key in keys)
        )
    return " ".join(parts)


def _lane_detail(lanes: Mapping[str, Mapping[str, Any]]) -> str:
    return " ".join(
        f"{lane_id}:category={lane.get('category')} anchors={lane.get('covered_anchors')}"
        for lane_id, lane in lanes.items()
    )


def _forbidden_bool_fields() -> list[str]:
    return list(REVIEW_PAYLOAD_REQUIRED_FALSE_FIELDS)


def _forbidden_flag_detail(payload: Mapping[str, Any]) -> str:
    return false_field_detail(payload, _forbidden_bool_fields())


def _safety_fields(*, include_solver: bool) -> list[str]:
    fields = (
        list(CORE_B5A_SAFETY_FALSE_FIELDS)
        + list(AUTHORIZATION_SAFETY_FALSE_FIELDS)
        + list(PREFLIGHT_MUTATION_FALSE_FIELDS)
    )
    if include_solver:
        return ["solver_invoked"] + fields
    return fields


def _all_false(mapping: Mapping[str, Any], keys: list[str]) -> bool:
    return required_false(mapping, keys)


def _rule(rule_id: str, passed: bool, detail: str) -> Dict[str, str]:
    return {
        "rule_id": str(rule_id),
        "status": "pass" if passed else "fail",
        "detail": str(detail),
    }


def _check(check_id: str, passed: bool, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": "pass" if passed else "fail",
        "detail": str(detail),
    }


def _int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            return []
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _is_utc_iso(value: str) -> bool:
    value = str(value or "").strip()
    if not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo == timezone.utc


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if isinstance(payload, Mapping):
            return dict(payload), None
        return None, "JSON root is not an object"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _resolve_path(project_root: Path, path: Optional[Path]) -> Path:
    if path is None:
        return project_root
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)

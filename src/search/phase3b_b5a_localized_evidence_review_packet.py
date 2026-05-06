from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b_b5a_localized_evidence_validator import (
    B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
)

B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE = (
    "phase3b_b5a_localized_evidence_review_packet_v1"
)

DEFAULT_LOCALIZED_EVIDENCE_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_b5a_localized_evidence_validator_20260425/"
    "b5a_localized_evidence_validator.json"
)

EXPECTED_REVIEW_RECORD_TYPE = "b5a_localized_evidence_review_record_v0"
EXPECTED_CANDIDATE = "67x13"
EXPECTED_SCOPE = "candidate=67x13, anchors=118-125, b5a_localized_evidence_validator"
EXPECTED_ANCHORS = [118, 119, 120, 121, 122, 123, 124, 125]
EXPECTED_STILL_BLOCKED_GATE_IDS = ["b5a_anchor_found"]
EXPECTED_REQUIRED_ACCEPTANCE_IDS = [
    "anchor118_ghost_overlap_auxiliary_evidence",
    "anchors119_125_signature_monotonic_primary_evidence",
    "no_runtime_or_final_authorization",
]
EXPECTED_FORBIDDEN_CONCLUSIONS = [
    "runtime_elimination_authorized",
    "final_168h_authorized",
    "checkpoint_write_or_import_back_authorized",
    "release_viewer_frontdoor_status_promoted",
    "certified_b5a_anchor_found",
]


def build_phase3b_b5a_localized_evidence_review_packet(
    project_root: Path,
    *,
    localized_evidence_validator_path: Optional[Path] = None,
    review_record_payload_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    validator_resolved = _resolve_path(
        project_root,
        (
            localized_evidence_validator_path
            if localized_evidence_validator_path is not None
            else DEFAULT_LOCALIZED_EVIDENCE_VALIDATOR_PATH
        ),
    )
    validator_report, validator_error = _load_json_mapping(validator_resolved)

    validator_metadata = _mapping(validator_report.get("metadata")) if validator_report else {}
    validator_status = _mapping(validator_report.get("status")) if validator_report else {}
    validator_candidate = _mapping(validator_report.get("candidate")) if validator_report else {}
    validator_payload = (
        _mapping(validator_report.get("localized_evidence_validator"))
        if validator_report
        else {}
    )
    accepted_lanes = _accepted_lane_by_id(validator_payload)
    review_scaffold = _mapping(validator_payload.get("review_intake_scaffold"))

    validator_present = bool(validator_report is not None and validator_error is None)
    validator_source_supported = bool(
        validator_metadata.get("source") == B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE
    )
    validator_ready = bool(
        validator_status.get("localized_evidence_validator_ready") is True
        and validator_status.get("current_localized_evidence_validated") is True
        and validator_status.get("reviewer_acceptance_required") is True
    )
    validator_safe = _all_false(
        validator_metadata,
        [
            "solver_invoked",
            "checkpoint_written",
            "proof_source",
            "runtime_semantics_changed",
            "candidate_elimination_claim",
            "certified_anchor_found",
            "b5a_anchor_found",
            "runtime_elimination_authorized",
            "final_168h_authorized",
            "checkpoint_write_or_import_back_authorized",
            "release_viewer_frontdoor_status_promoted",
            "preflight_gate_mutated",
        ],
    ) and _all_false(
        validator_status,
        [
            "checkpoint_written",
            "proof_source",
            "runtime_semantics_changed",
            "candidate_elimination_claim",
            "certified_anchor_found",
            "b5a_anchor_found",
            "runtime_elimination_authorized",
            "final_168h_authorized",
            "checkpoint_write_or_import_back_authorized",
            "release_viewer_frontdoor_status_promoted",
            "preflight_gate_mutated",
        ],
    )
    candidate_matches = bool(
        str(validator_candidate.get("expected_key")) == EXPECTED_CANDIDATE
        and str(validator_candidate.get("localized_key")) == EXPECTED_CANDIDATE
        and validator_candidate.get("matches") is True
    )
    required_acceptance_ids_match = bool(
        _acceptance_ids_from_scaffold(review_scaffold)
        == EXPECTED_REQUIRED_ACCEPTANCE_IDS
    )
    forbidden_conclusions_match = bool(
        list(validator_payload.get("forbidden_conclusions", []))
        == EXPECTED_FORBIDDEN_CONCLUSIONS
    )
    lanes_match = bool(
        _lane_matches(
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
            anchors=[119, 120, 121, 122, 123, 124, 125],
        )
    )

    packet_checks = [
        _check(
            "localized_evidence_validator_present",
            validator_present,
            (
                "validator artifact loaded"
                if validator_present
                else validator_error
                or f"missing:{_display_path(project_root, validator_resolved)}"
            ),
        ),
        _check(
            "localized_evidence_validator_source_supported",
            validator_source_supported,
            str(validator_metadata.get("source") or "missing"),
        ),
        _check(
            "localized_evidence_validator_ready",
            validator_ready,
            (
                "ready="
                + str(validator_status.get("localized_evidence_validator_ready"))
                + " current_validated="
                + str(validator_status.get("current_localized_evidence_validated"))
            ),
        ),
        _check(
            "localized_evidence_validator_safe_flags",
            validator_safe,
            _safe_flag_detail(validator_metadata, validator_status),
        ),
        _check(
            "candidate_scope_locked",
            candidate_matches,
            (
                f"expected={validator_candidate.get('expected_key')} "
                f"localized={validator_candidate.get('localized_key')} "
                f"matches={validator_candidate.get('matches')}"
            ),
        ),
        _check(
            "required_acceptance_ids_locked",
            required_acceptance_ids_match,
            str(_acceptance_ids_from_scaffold(review_scaffold)),
        ),
        _check(
            "forbidden_conclusions_locked",
            forbidden_conclusions_match,
            str(validator_payload.get("forbidden_conclusions", [])),
        ),
        _check("localized_evidence_lanes_locked", lanes_match, _lane_detail(accepted_lanes)),
    ]
    review_packet_ready = all(check["status"] == "pass" for check in packet_checks)

    review_record_payload_resolved = (
        _resolve_path(project_root, review_record_payload_path)
        if review_record_payload_path is not None
        else None
    )
    payload_validation = _validate_optional_review_record_payload(
        review_record_payload_resolved,
        validator_ready=review_packet_ready,
    )
    review_record_payload_provided = bool(review_record_payload_resolved is not None)
    review_record_payload_validated = bool(
        payload_validation.get("record_payload_validated", False)
    )

    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "b5a_localized_evidence_reviewer_intake_contract_not_gate_promotion"
            ),
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
        },
        "paths": {
            "project_root": str(project_root),
            "localized_evidence_validator": _display_path(
                project_root, validator_resolved
            ),
            "review_record_payload": (
                _display_path(project_root, review_record_payload_resolved)
                if review_record_payload_resolved is not None
                else None
            ),
        },
        "inputs": {
            "localized_evidence_validator": {
                "present": validator_present,
                "load_error": validator_error,
                "source_supported": validator_source_supported,
                "validator_ready": validator_ready,
            },
            "review_record_payload": {
                "provided": review_record_payload_provided,
                "path": (
                    _display_path(project_root, review_record_payload_resolved)
                    if review_record_payload_resolved is not None
                    else None
                ),
            },
        },
        "status": {
            "review_packet_ready": bool(review_packet_ready),
            "review_record_validator_ready": bool(review_packet_ready),
            "review_record_payload_provided": bool(review_record_payload_provided),
            "review_record_payload_validated": bool(review_record_payload_validated),
            "review_record_payload_validation_status": str(
                payload_validation.get("validation_status")
            ),
            "reviewer_acceptance_required": True,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
            "recommended_next_step": _recommended_next_step(
                review_packet_ready,
                review_record_payload_provided,
                review_record_payload_validated,
            ),
            "outcome": _outcome(
                review_packet_ready,
                review_record_payload_provided,
                review_record_payload_validated,
            ),
        },
        "review_packet": {
            "record_contract": _record_contract(),
            "reviewer_payload_template": _reviewer_payload_template(),
            "external_reviewer_request_text": _external_reviewer_request_text(),
            "source_validator_summary": {
                "source": validator_metadata.get("source"),
                "localized_evidence_validator_ready": validator_status.get(
                    "localized_evidence_validator_ready"
                ),
                "current_localized_evidence_validated": validator_status.get(
                    "current_localized_evidence_validated"
                ),
                "accepted_lanes": list(validator_payload.get("accepted_lanes", [])),
            },
        },
        "review_record_validator": {
            "validator_target": "future_or_supplied_b5a_localized_evidence_review_record_payload",
            "target_record_type": EXPECTED_REVIEW_RECORD_TYPE,
            "scope": EXPECTED_SCOPE,
            "required_acceptance_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
            "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
            "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
            "actual_record_validation": payload_validation,
        },
        "checks": packet_checks,
    }


def render_phase3b_b5a_localized_evidence_review_packet_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    packet = _mapping(report.get("review_packet"))
    contract = _mapping(packet.get("record_contract"))
    validator = _mapping(report.get("review_record_validator"))
    actual = _mapping(validator.get("actual_record_validation"))
    lines = [
        "# Phase 3B B5A Localized Evidence Review Packet",
        "",
        f"- Review packet ready: `{status.get('review_packet_ready')}`",
        f"- Review record validator ready: `{status.get('review_record_validator_ready')}`",
        f"- Review record payload provided: `{status.get('review_record_payload_provided')}`",
        f"- Review record payload validated: `{status.get('review_record_payload_validated')}`",
        f"- Payload validation status: `{status.get('review_record_payload_validation_status')}`",
        f"- Certified anchor found: `{status.get('certified_anchor_found')}`",
        f"- B5A anchor found: `{status.get('b5a_anchor_found')}`",
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


def render_phase3b_b5a_localized_evidence_review_packet_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B B5A localized evidence review packet",
        f"review_packet_ready={status.get('review_packet_ready')}",
        f"review_record_validator_ready={status.get('review_record_validator_ready')}",
        f"review_record_payload_provided={status.get('review_record_payload_provided')}",
        f"review_record_payload_validated={status.get('review_record_payload_validated')}",
        f"review_record_payload_validation_status={status.get('review_record_payload_validation_status')}",
        f"certified_anchor_found={status.get('certified_anchor_found')}",
        f"b5a_anchor_found={status.get('b5a_anchor_found')}",
        f"proof_source={status.get('proof_source')}",
        f"runtime_semantics_changed={status.get('runtime_semantics_changed')}",
        f"checkpoint_written={status.get('checkpoint_written')}",
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


def write_phase3b_b5a_localized_evidence_review_packet(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "b5a_localized_evidence_review_packet",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(
        md_path,
        render_phase3b_b5a_localized_evidence_review_packet_markdown(report),
    )
    _atomic_write_text(
        txt_path,
        render_phase3b_b5a_localized_evidence_review_packet_text(report),
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _validate_optional_review_record_payload(
    payload_path: Optional[Path],
    *,
    validator_ready: bool,
) -> Dict[str, Any]:
    if payload_path is None:
        return {
            "record_payload_provided": False,
            "record_payload_validated": False,
            "validation_status": "not_run",
            "failed_rule_count": 0,
            "failed_rule_ids": [],
            "rule_results": [],
        }
    if not validator_ready:
        return {
            "record_payload_provided": True,
            "record_payload_validated": False,
            "validation_status": "contract_blocked",
            "failed_rule_count": 1,
            "failed_rule_ids": ["review_packet_contract_ready"],
            "rule_results": [
                _rule(
                    "review_packet_contract_ready",
                    False,
                    "Cannot validate a review record until packet contract is ready.",
                )
            ],
        }
    payload, error = _load_json_mapping(payload_path)
    if payload is None:
        return {
            "record_payload_provided": True,
            "record_payload_validated": False,
            "validation_status": "load_error",
            "failed_rule_count": 1,
            "failed_rule_ids": ["review_record_payload_loadable"],
            "rule_results": [
                _rule(
                    "review_record_payload_loadable",
                    False,
                    error or "payload is missing or not a JSON object",
                )
            ],
        }

    rule_results = [
        _rule(
            "record_type",
            payload.get("record_type") == EXPECTED_REVIEW_RECORD_TYPE,
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
            _int_list(payload.get("covered_anchors")) == EXPECTED_ANCHORS,
            str(payload.get("covered_anchors")),
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
            "verdict_accepts_contract",
            str(payload.get("verdict") or "").strip()
            in {"accepted", "accepted_for_review_contract"},
            str(payload.get("verdict")),
        ),
        _rule(
            "no_forbidden_positive_flags",
            not any(bool(payload.get(key, False)) for key in _forbidden_bool_fields()),
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
        "validation_status": "passed" if record_payload_validated else "failed",
        "failed_rule_count": len(failed_rule_ids),
        "failed_rule_ids": failed_rule_ids,
        "rule_results": rule_results,
    }


def _record_contract() -> Dict[str, Any]:
    return {
        "record_type": EXPECTED_REVIEW_RECORD_TYPE,
        "scope": EXPECTED_SCOPE,
        "candidate_key": EXPECTED_CANDIDATE,
        "covered_anchors": list(EXPECTED_ANCHORS),
        "required_acceptance_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
        "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
        "required_fields": [
            "record_type",
            "scope",
            "candidate_key",
            "covered_anchors",
            "reviewer_id",
            "reviewed_at",
            "verdict",
            "accepted_statement_ids",
            "forbidden_conclusions_rejected",
            "still_blocked_gate_ids",
        ],
    }


def _reviewer_payload_template() -> Dict[str, Any]:
    return {
        "record_type": EXPECTED_REVIEW_RECORD_TYPE,
        "scope": EXPECTED_SCOPE,
        "candidate_key": EXPECTED_CANDIDATE,
        "covered_anchors": list(EXPECTED_ANCHORS),
        "reviewer_id": "<reviewer id>",
        "reviewed_at": "<ISO-8601 UTC timestamp ending with Z>",
        "verdict": "accepted",
        "accepted_statement_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
        "forbidden_conclusions_rejected": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "certified_b5a_anchor_found": False,
        "b5a_anchor_found": False,
        "proof_source": False,
        "runtime_semantics_changed": False,
        "notes": (
            "Review/signoff only. This record does not authorize production "
            "execution, runtime elimination, checkpoint writes, or gate promotion."
        ),
    }


def _external_reviewer_request_text() -> str:
    return (
        "Please review the Phase3B B5A localized evidence validator for candidate "
        "67x13 and anchors 118-125. If you accept the review-only evidence "
        "contract, return a machine-readable JSON payload with "
        f"record_type={EXPECTED_REVIEW_RECORD_TYPE}, scope={EXPECTED_SCOPE}, "
        "all required acceptance ids, all forbidden conclusions rejected, and "
        "still_blocked_gate_ids=['b5a_anchor_found']. Do not authorize runtime "
        "elimination, final 168h execution, checkpoint write/import-back, "
        "release/viewer/frontdoor status promotion, or certified B5A anchor "
        "promotion."
    )


def _accepted_lane_by_id(validator_payload: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    for lane in list(validator_payload.get("accepted_lanes", [])):
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


def _acceptance_ids_from_scaffold(review_scaffold: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for item in list(review_scaffold.get("reviewer_must_accept", [])):
        if isinstance(item, Mapping):
            result.append(str(item.get("acceptance_id") or ""))
    return result


def _recommended_next_step(
    review_packet_ready: bool,
    payload_provided: bool,
    payload_validated: bool,
) -> str:
    if not review_packet_ready:
        return "repair_b5a_localized_evidence_validator_before_review_packet"
    if payload_validated:
        return "ingest_b5a_localized_evidence_review_record_without_promoting_b5a_gate"
    if payload_provided:
        return "repair_b5a_localized_evidence_review_record_payload"
    return "send_b5a_localized_evidence_review_packet_to_external_or_manual_reviewer"


def _outcome(
    review_packet_ready: bool,
    payload_provided: bool,
    payload_validated: bool,
) -> str:
    if not review_packet_ready:
        return "b5a_localized_evidence_review_packet_blocked"
    if payload_validated:
        return "b5a_localized_evidence_review_record_payload_validated"
    if payload_provided:
        return "b5a_localized_evidence_review_record_payload_rejected"
    return "b5a_localized_evidence_review_packet_ready_waiting_for_reviewer_payload"


def _all_false(mapping: Mapping[str, Any], keys: list[str]) -> bool:
    return all(key in mapping and mapping.get(key) is False for key in keys)


def _safe_flag_detail(
    metadata: Mapping[str, Any],
    status: Mapping[str, Any],
) -> str:
    keys = [
        "solver_invoked",
        "checkpoint_written",
        "proof_source",
        "runtime_semantics_changed",
        "candidate_elimination_claim",
        "certified_anchor_found",
        "b5a_anchor_found",
    ]
    meta = " ".join(f"metadata.{key}={bool(metadata.get(key, False))}" for key in keys)
    stat = " ".join(f"status.{key}={bool(status.get(key, False))}" for key in keys)
    return meta + " " + stat


def _lane_detail(accepted_lanes: Mapping[str, Mapping[str, Any]]) -> str:
    return " ".join(
        f"{lane_id}:role={lane.get('role')} category={lane.get('category')} anchors={lane.get('covered_anchors')}"
        for lane_id, lane in accepted_lanes.items()
    )


def _forbidden_bool_fields() -> list[str]:
    return [
        "runtime_elimination_authorized",
        "final_168h_authorized",
        "checkpoint_write_or_import_back_authorized",
        "release_viewer_frontdoor_status_promoted",
        "certified_b5a_anchor_found",
        "b5a_anchor_found",
        "proof_source",
        "runtime_semantics_changed",
    ]


def _forbidden_flag_detail(payload: Mapping[str, Any]) -> str:
    return " ".join(
        f"{key}={bool(payload.get(key, False))}" for key in _forbidden_bool_fields()
    )


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

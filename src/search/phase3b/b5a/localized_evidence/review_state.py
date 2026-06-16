from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.b5a.localized_evidence.review_packet import (
    B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE,
    EXPECTED_ANCHORS,
    EXPECTED_FORBIDDEN_CONCLUSIONS,
    EXPECTED_REQUIRED_ACCEPTANCE_IDS,
    EXPECTED_REVIEW_RECORD_TYPE,
    EXPECTED_SCOPE,
    EXPECTED_STILL_BLOCKED_GATE_IDS,
)

B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE = (
    "phase3b_b5a_localized_evidence_review_state_v1"
)

DEFAULT_REVIEW_PACKET_PATH = Path(
    ".artifacts/phase3b_b5a_localized_evidence_review_packet_20260425/"
    "b5a_localized_evidence_review_packet.json"
)

EXPECTED_CANDIDATE = "67x13"


def build_phase3b_b5a_localized_evidence_review_state(
    project_root: Path,
    *,
    review_packet_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    packet_resolved = _resolve_path(
        project_root,
        review_packet_path if review_packet_path is not None else DEFAULT_REVIEW_PACKET_PATH,
    )
    packet_report, packet_error = _load_json_mapping(packet_resolved)

    packet_meta = _mapping(packet_report.get("metadata")) if packet_report else {}
    packet_status = _mapping(packet_report.get("status")) if packet_report else {}
    review_packet = _mapping(packet_report.get("review_packet")) if packet_report else {}
    contract = _mapping(review_packet.get("record_contract"))
    record_validator = (
        _mapping(packet_report.get("review_record_validator")) if packet_report else {}
    )
    actual_validation = _mapping(record_validator.get("actual_record_validation"))

    packet_present = bool(packet_report is not None and packet_error is None)
    packet_source_ok = bool(
        packet_meta.get("source") == B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE
    )
    packet_ready = bool(
        packet_status.get("review_packet_ready") is True
        and packet_status.get("review_record_validator_ready") is True
    )
    payload_validated = bool(
        packet_status.get("review_record_payload_provided") is True
        and packet_status.get("review_record_payload_validated") is True
        and packet_status.get("review_record_payload_validation_status") == "passed"
        and actual_validation.get("record_payload_provided") is True
        and actual_validation.get("record_payload_validated") is True
        and actual_validation.get("validation_status") == "passed"
        and actual_validation.get("failed_rule_ids", []) == []
    )
    contract_locked = bool(
        contract.get("record_type") == EXPECTED_REVIEW_RECORD_TYPE
        and contract.get("scope") == EXPECTED_SCOPE
        and contract.get("candidate_key") == EXPECTED_CANDIDATE
        and _int_list(contract.get("covered_anchors")) == EXPECTED_ANCHORS
        and _string_list(contract.get("required_acceptance_ids"))
        == EXPECTED_REQUIRED_ACCEPTANCE_IDS
        and _string_list(contract.get("forbidden_conclusions"))
        == EXPECTED_FORBIDDEN_CONCLUSIONS
        and _string_list(contract.get("still_blocked_gate_ids"))
        == EXPECTED_STILL_BLOCKED_GATE_IDS
    )
    still_blocked_gate_ids = _string_list(packet_status.get("still_blocked_gate_ids"))
    still_blocked_locked = bool(still_blocked_gate_ids == EXPECTED_STILL_BLOCKED_GATE_IDS)
    safety_flags_off = _all_false(
        packet_meta,
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
        packet_status,
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

    checks = [
        _check(
            "review_packet_present",
            packet_present,
            (
                "review packet loaded"
                if packet_present
                else packet_error or f"missing:{_display_path(project_root, packet_resolved)}"
            ),
        ),
        _check(
            "review_packet_source_supported",
            packet_source_ok,
            str(packet_meta.get("source") or "missing"),
        ),
        _check(
            "review_packet_ready",
            packet_ready,
            (
                "review_packet_ready="
                + str(packet_status.get("review_packet_ready"))
                + " review_record_validator_ready="
                + str(packet_status.get("review_record_validator_ready"))
            ),
        ),
        _check(
            "review_record_payload_validated",
            payload_validated,
            (
                "provided="
                + str(packet_status.get("review_record_payload_provided"))
                + " validated="
                + str(packet_status.get("review_record_payload_validated"))
                + " status="
                + str(packet_status.get("review_record_payload_validation_status"))
            ),
        ),
        _check(
            "review_packet_contract_locked",
            contract_locked,
            _contract_detail(contract),
        ),
        _check(
            "still_blocked_gate_ids_locked",
            still_blocked_locked,
            str(still_blocked_gate_ids),
        ),
        _check(
            "review_packet_safety_flags_off",
            safety_flags_off,
            _safety_detail(packet_meta, packet_status),
        ),
    ]

    review_state_ready = all(check["status"] == "pass" for check in checks)
    b5a_localized_evidence_reviewed = bool(review_state_ready)

    gates = [
        _gate(
            "review_record_payload_validated",
            bool(payload_validated),
            True,
            "GPT5.5 Pro B5A localized-evidence review payload must validate.",
        ),
        _gate(
            "repo_side_review_state_updated",
            bool(review_state_ready),
            True,
            "This artifact is the repo-side marker for accepted B5A localized evidence review.",
        ),
        _gate(
            "b5a_localized_evidence_reviewed",
            bool(b5a_localized_evidence_reviewed),
            True,
            "The review-only evidence contract has been accepted and locally marked.",
        ),
        _gate(
            "b5a_anchor_found",
            False,
            True,
            "B5A anchor remains blocked until a separate certified-anchor promotion gate.",
        ),
        _gate(
            "certified_anchor_found",
            False,
            False,
            "Review-state marking is not certified-anchor proof.",
        ),
    ]
    remaining_blockers = [
        str(gate["gate_id"])
        for gate in gates
        if bool(gate.get("blocking")) and not bool(gate.get("satisfied"))
    ]

    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "b5a_localized_evidence_review_state_not_b5a_gate_promotion"
            ),
            "review_only": True,
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
            "review_packet": _display_path(project_root, packet_resolved),
        },
        "candidate": {
            "key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_ANCHORS),
            "scope": EXPECTED_SCOPE,
        },
        "status": {
            "review_state_ready": bool(review_state_ready),
            "repo_side_review_state_updated": bool(review_state_ready),
            "b5a_localized_evidence_reviewed": bool(
                b5a_localized_evidence_reviewed
            ),
            "review_record_payload_validated": bool(payload_validated),
            "review_record_payload_validation_status": (
                "passed" if payload_validated else "failed"
            ),
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
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
            "remaining_blocker_gate_ids": remaining_blockers,
            "recommended_next_step": (
                "decide_b5a_gate_integration_or_certified_anchor_promotion_review"
                if review_state_ready
                else "repair_b5a_localized_evidence_review_packet_before_review_state"
            ),
            "handoff_recommendation": (
                "Repo-side B5A localized evidence review-state marker is valid: "
                "external review acceptance is now registered, while b5a_anchor_found=false, "
                "certified_anchor_found=false, proof_source=false, and checkpoint_written=false remain locked."
                if review_state_ready
                else "Review-state marker is not ready; do not register B5A localized evidence review."
            ),
        },
        "review_state": {
            "review_state_kind": "repo_side_b5a_localized_evidence_review_state",
            "tracked_field": "b5a_localized_evidence_reviewed",
            "scope": EXPECTED_SCOPE,
            "candidate_key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_ANCHORS),
            "review_state_ready": bool(review_state_ready),
            "repo_side_review_state_updated": bool(review_state_ready),
            "b5a_localized_evidence_reviewed": bool(
                b5a_localized_evidence_reviewed
            ),
            "review_record_payload_validated": bool(payload_validated),
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
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
            "required_acceptance_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
            "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_b5a_localized_evidence_review_state_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    review_state = _mapping(report.get("review_state"))
    lines = [
        "# Phase 3B B5A Localized Evidence Review State",
        "",
        f"- Review-state ready: `{status.get('review_state_ready')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- B5A localized evidence reviewed: `{status.get('b5a_localized_evidence_reviewed')}`",
        f"- B5A anchor found: `{status.get('b5a_anchor_found')}`",
        f"- Certified anchor found: `{status.get('certified_anchor_found')}`",
        f"- Proof source: `{status.get('proof_source')}`",
        f"- Runtime semantics changed: `{status.get('runtime_semantics_changed')}`",
        f"- Checkpoint written: `{status.get('checkpoint_written')}`",
        f"- Still blocked gate ids: `{status.get('still_blocked_gate_ids')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Review State",
        "",
        f"- Kind: `{review_state.get('review_state_kind')}`",
        f"- Scope: `{review_state.get('scope')}`",
        f"- Candidate: `{review_state.get('candidate_key')}`",
        f"- Covered anchors: `{review_state.get('covered_anchors')}`",
        "",
        "## Gates",
        "",
        "| Gate | Satisfied | Blocking | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for gate in list(report.get("gates", [])):
        if isinstance(gate, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(gate.get("gate_id")),
                        _markdown_cell(gate.get("satisfied")),
                        _markdown_cell(gate.get("blocking")),
                        _markdown_cell(gate.get("detail")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
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


def render_phase3b_b5a_localized_evidence_review_state_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    review_state = _mapping(report.get("review_state"))
    lines = [
        "Phase 3B B5A localized evidence review state",
        f"review_state_ready={bool(status.get('review_state_ready', False))}",
        f"repo_side_review_state_updated={bool(status.get('repo_side_review_state_updated', False))}",
        f"b5a_localized_evidence_reviewed={bool(status.get('b5a_localized_evidence_reviewed', False))}",
        f"review_record_payload_validated={bool(status.get('review_record_payload_validated', False))}",
        f"b5a_anchor_found={bool(status.get('b5a_anchor_found', False))}",
        f"certified_anchor_found={bool(status.get('certified_anchor_found', False))}",
        f"proof_source={bool(status.get('proof_source', False))}",
        f"runtime_semantics_changed={bool(status.get('runtime_semantics_changed', False))}",
        f"checkpoint_written={bool(status.get('checkpoint_written', False))}",
        f"still_blocked_gate_ids={status.get('still_blocked_gate_ids')}",
        f"recommended_next_step={status.get('recommended_next_step')}",
        f"scope={review_state.get('scope')}",
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


def write_phase3b_b5a_localized_evidence_review_state(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "b5a_localized_evidence_review_state",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(
        md_path,
        render_phase3b_b5a_localized_evidence_review_state_markdown(report),
    )
    _atomic_write_text(
        txt_path,
        render_phase3b_b5a_localized_evidence_review_state_text(report),
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _contract_detail(contract: Mapping[str, Any]) -> str:
    return (
        "record_type="
        + str(contract.get("record_type"))
        + " scope="
        + str(contract.get("scope"))
        + " candidate_key="
        + str(contract.get("candidate_key"))
        + " covered_anchors="
        + str(contract.get("covered_anchors"))
    )


def _safety_detail(meta: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    keys = [
        "solver_invoked",
        "checkpoint_written",
        "proof_source",
        "runtime_semantics_changed",
        "candidate_elimination_claim",
        "certified_anchor_found",
        "b5a_anchor_found",
    ]
    meta_detail = " ".join(
        f"metadata.{key}={bool(meta.get(key, False))}" for key in keys
    )
    status_detail = " ".join(
        f"status.{key}={bool(status.get(key, False))}" for key in keys
    )
    return meta_detail + " " + status_detail


def _all_false(mapping: Mapping[str, Any], keys: list[str]) -> bool:
    return all(key in mapping and mapping.get(key) is False for key in keys)


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


def _check(check_id: str, passed: bool, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": "pass" if passed else "fail",
        "detail": str(detail),
    }


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

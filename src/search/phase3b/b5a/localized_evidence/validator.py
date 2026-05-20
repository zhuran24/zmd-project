from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.b5a.localized_evidence.readiness import (
    B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
)

B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE = (
    "phase3b_b5a_localized_evidence_validator_v1"
)

DEFAULT_READINESS_PATH = Path(
    ".artifacts/phase3b_b5a_localized_evidence_readiness_20260425/"
    "b5a_localized_evidence_readiness.json"
)

EXPECTED_CANDIDATE = "67x13"
EXPECTED_GHOST_ANCHOR = 118
EXPECTED_SIGNATURE_ANCHORS = tuple(range(119, 126))
GHOST_LANE_ID = "anchor118_ghost_overlap_forced_domain"
SIGNATURE_LANE_ID = "anchors119_125_signature_monotonic_forced_label"


def build_phase3b_b5a_localized_evidence_validator(
    project_root: Path,
    *,
    readiness_path: Optional[Path] = None,
    expected_candidate: str = EXPECTED_CANDIDATE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    readiness_resolved = _resolve_path(
        project_root,
        readiness_path if readiness_path is not None else DEFAULT_READINESS_PATH,
    )
    readiness, readiness_error = _load_json_mapping(readiness_resolved)

    metadata = _mapping(readiness.get("metadata")) if readiness else {}
    status = _mapping(readiness.get("status")) if readiness else {}
    candidate = _mapping(readiness.get("candidate")) if readiness else {}
    inputs = _mapping(readiness.get("inputs")) if readiness else {}
    preflight_input = _mapping(inputs.get("post_acceptance_preflight"))
    lanes = _lane_by_id(readiness)
    ghost_lane = lanes.get(GHOST_LANE_ID, {})
    signature_lane = lanes.get(SIGNATURE_LANE_ID, {})
    precedent_policy = _mapping(readiness.get("old_signature_precedent_policy")) if readiness else {}

    readiness_present = bool(readiness is not None and readiness_error is None)
    readiness_source_supported = bool(
        metadata.get("source") == B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE
    )
    readiness_ready = bool(status.get("readiness_ready", False))
    metadata_safe = _all_false(
        metadata,
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
    )
    status_safe = _all_false(
        status,
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
        str(candidate.get("expected_key")) == str(expected_candidate)
        and str(candidate.get("localized_key")) == str(expected_candidate)
        and candidate.get("matches") is True
    )
    preflight_only_b5a = bool(
        preflight_input.get("failed_checks") == ["b5a_anchor_found"]
        and preflight_input.get("only_b5a_anchor_found_failed") is True
        and preflight_input.get("ready_for_final_long_run") is False
    )
    ghost_lane_valid = _lane_matches(
        ghost_lane,
        lane_id=GHOST_LANE_ID,
        category="ghost_overlap_forced_domain",
        anchors=[EXPECTED_GHOST_ANCHOR],
    )
    signature_lane_valid = _lane_matches(
        signature_lane,
        lane_id=SIGNATURE_LANE_ID,
        category="signature_monotonic_forced_label",
        anchors=list(EXPECTED_SIGNATURE_ANCHORS),
    )
    precedent_not_current_evidence = bool(
        precedent_policy.get(
            "old_m6x4_signature_artifact_used_as_current_b5a_evidence"
        )
        is False
        and _mapping(signature_lane).get("precedent", {}).get(
            "used_as_current_b5a_evidence"
        )
        is False
        and "2026-04-25" in str(precedent_policy.get("required_current_source", ""))
    )
    certified_anchor_not_claimed = bool(
        status.get("certified_anchor_found") is False
        and not bool(status.get("b5a_anchor_found", False))
    )

    checks = [
        _check(
            "readiness_present",
            readiness_present,
            "readiness artifact loaded"
            if readiness_present
            else readiness_error or f"missing:{_display_path(project_root, readiness_resolved)}",
        ),
        _check(
            "readiness_source_supported",
            readiness_source_supported,
            str(metadata.get("source") or "missing"),
        ),
        _check(
            "readiness_ready",
            readiness_ready,
            f"status.readiness_ready={readiness_ready}",
        ),
        _check(
            "metadata_safe_flags",
            metadata_safe,
            _safe_flag_detail(metadata),
        ),
        _check(
            "status_safe_flags",
            status_safe,
            _status_safe_detail(status),
        ),
        _check(
            "candidate_locked_67x13",
            candidate_matches,
            (
                f"expected={candidate.get('expected_key')} "
                f"localized={candidate.get('localized_key')} "
                f"matches={candidate.get('matches')}"
            ),
        ),
        _check(
            "post_acceptance_only_b5a_failed",
            preflight_only_b5a,
            f"failed_checks={preflight_input.get('failed_checks')}",
        ),
        _check(
            "anchor118_ghost_lane_valid",
            ghost_lane_valid,
            _lane_detail(ghost_lane),
        ),
        _check(
            "anchors119_125_signature_lane_valid",
            signature_lane_valid,
            _lane_detail(signature_lane),
        ),
        _check(
            "old_signature_precedent_not_current_evidence",
            precedent_not_current_evidence,
            str(precedent_policy.get("policy") or "missing precedent policy"),
        ),
        _check(
            "certified_anchor_not_claimed",
            certified_anchor_not_claimed,
            "validator keeps certified_anchor_found=false and b5a_anchor_found=false",
        ),
    ]
    validator_ready = all(check["status"] == "pass" for check in checks)

    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "b5a_localized_evidence_validator_review_intake_not_proof_source"
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
            "localized_evidence_readiness": _display_path(
                project_root, readiness_resolved
            ),
        },
        "inputs": {
            "localized_evidence_readiness": {
                "present": readiness_present,
                "load_error": readiness_error,
                "source_supported": readiness_source_supported,
                "readiness_ready": readiness_ready,
            }
        },
        "status": {
            "localized_evidence_validator_ready": bool(validator_ready),
            "current_localized_evidence_validated": bool(validator_ready),
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
            "recommended_next_step": (
                "external_or_manual_review_of_b5a_localized_evidence_validator"
                if validator_ready
                else "repair_b5a_localized_evidence_readiness_before_review_intake"
            ),
            "outcome": (
                "b5a_localized_evidence_validator_ready_for_review_intake"
                if validator_ready
                else "b5a_localized_evidence_validator_blocked"
            ),
        },
        "candidate": {
            "expected_key": str(expected_candidate),
            "localized_key": str(candidate.get("localized_key", "")),
            "matches": bool(candidate_matches),
        },
        "localized_evidence_validator": {
            "validated_readiness_source": metadata.get("source"),
            "accepted_lanes": [
                {
                    "lane_id": GHOST_LANE_ID,
                    "role": "auxiliary_cross_evidence",
                    "category": "ghost_overlap_forced_domain",
                    "covered_anchors": [EXPECTED_GHOST_ANCHOR],
                    "reviewer_acceptance_required": True,
                    "accepted_by_validator": bool(ghost_lane_valid),
                },
                {
                    "lane_id": SIGNATURE_LANE_ID,
                    "role": "primary_coverage_evidence",
                    "category": "signature_monotonic_forced_label",
                    "covered_anchors": list(EXPECTED_SIGNATURE_ANCHORS),
                    "reviewer_acceptance_required": True,
                    "accepted_by_validator": bool(signature_lane_valid),
                },
            ],
            "review_intake_scaffold": _review_intake_scaffold(validator_ready),
            "forbidden_conclusions": [
                "runtime_elimination_authorized",
                "final_168h_authorized",
                "checkpoint_write_or_import_back_authorized",
                "release_viewer_frontdoor_status_promoted",
                "certified_b5a_anchor_found",
            ],
        },
        "checks": checks,
    }


def render_phase3b_b5a_localized_evidence_validator_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("localized_evidence_validator"))
    lines = [
        "# Phase 3B B5A Localized Evidence Validator",
        "",
        f"- Validator ready: `{status.get('localized_evidence_validator_ready')}`",
        f"- Current localized evidence validated: `{status.get('current_localized_evidence_validated')}`",
        f"- Reviewer acceptance required: `{status.get('reviewer_acceptance_required')}`",
        f"- Certified anchor found: `{status.get('certified_anchor_found')}`",
        f"- B5A anchor found: `{status.get('b5a_anchor_found')}`",
        f"- Proof source: `{status.get('proof_source')}`",
        f"- Runtime semantics changed: `{status.get('runtime_semantics_changed')}`",
        f"- Checkpoint written: `{status.get('checkpoint_written')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        "",
        "## Review Intake",
        "",
    ]
    for item in list(_mapping(validator.get("review_intake_scaffold")).get("reviewer_must_accept", [])):
        lines.append(f"- `{item.get('acceptance_id')}`: {item.get('detail')}")
    lines.extend(
        [
            "",
            "## Accepted Lanes",
            "",
            "| Lane | Role | Category | Anchors | Accepted by validator |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for lane in list(validator.get("accepted_lanes", [])):
        if isinstance(lane, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(lane.get("lane_id")),
                        _markdown_cell(lane.get("role")),
                        _markdown_cell(lane.get("category")),
                        _markdown_cell(lane.get("covered_anchors")),
                        _markdown_cell(lane.get("accepted_by_validator")),
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


def render_phase3b_b5a_localized_evidence_validator_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B B5A localized evidence validator",
        f"localized_evidence_validator_ready={status.get('localized_evidence_validator_ready')}",
        f"current_localized_evidence_validated={status.get('current_localized_evidence_validated')}",
        f"reviewer_acceptance_required={status.get('reviewer_acceptance_required')}",
        f"certified_anchor_found={status.get('certified_anchor_found')}",
        f"b5a_anchor_found={status.get('b5a_anchor_found')}",
        f"proof_source={status.get('proof_source')}",
        f"runtime_semantics_changed={status.get('runtime_semantics_changed')}",
        f"checkpoint_written={status.get('checkpoint_written')}",
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


def write_phase3b_b5a_localized_evidence_validator(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "b5a_localized_evidence_validator",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(
        md_path,
        render_phase3b_b5a_localized_evidence_validator_markdown(report),
    )
    _atomic_write_text(
        txt_path,
        render_phase3b_b5a_localized_evidence_validator_text(report),
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _lane_matches(
    lane: Mapping[str, Any],
    *,
    lane_id: str,
    category: str,
    anchors: list[int],
) -> bool:
    return bool(
        lane
        and lane.get("lane_id") == lane_id
        and lane.get("category") == category
        and _int_list(lane.get("required_anchors")) == anchors
        and _int_list(lane.get("covered_anchors")) == anchors
        and lane.get("current_source_complete") is True
        and lane.get("probe_supports_lane") is True
        and lane.get("solver_free_inputs") is True
        and lane.get("proof_safe") is True
    )


def _review_intake_scaffold(validator_ready: bool) -> Dict[str, Any]:
    return {
        "reviewer_acceptance_required": True,
        "validator_ready_for_review": bool(validator_ready),
        "reviewer_must_accept": [
            {
                "acceptance_id": "anchor118_ghost_overlap_auxiliary_evidence",
                "detail": (
                    "Accept anchor118 ghost-overlap forced-domain lane only as "
                    "auxiliary cross-evidence, not as a certified anchor proof."
                ),
            },
            {
                "acceptance_id": "anchors119_125_signature_monotonic_primary_evidence",
                "detail": (
                    "Accept anchors119-125 signature-monotonic forced-label lane as "
                    "the primary current-source localized evidence contract."
                ),
            },
            {
                "acceptance_id": "no_runtime_or_final_authorization",
                "detail": (
                    "Confirm this review-intake step does not authorize runtime "
                    "elimination, production long-run execution, checkpoint writes, "
                    "or release/viewer/frontdoor promotion."
                ),
            },
        ],
    }


def _lane_by_id(readiness: Optional[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    if not readiness:
        return result
    for lane in list(readiness.get("lanes", [])):
        if isinstance(lane, Mapping) and lane.get("lane_id"):
            result[str(lane.get("lane_id"))] = lane
    return result


def _all_false(mapping: Mapping[str, Any], keys: list[str]) -> bool:
    return all(key in mapping and mapping.get(key) is False for key in keys)


def _safe_flag_detail(metadata: Mapping[str, Any]) -> str:
    keys = [
        "solver_invoked",
        "checkpoint_written",
        "proof_source",
        "runtime_semantics_changed",
        "candidate_elimination_claim",
        "certified_anchor_found",
        "b5a_anchor_found",
    ]
    return " ".join(f"{key}={bool(metadata.get(key, False))}" for key in keys)


def _status_safe_detail(status: Mapping[str, Any]) -> str:
    keys = [
        "certified_anchor_found",
        "b5a_anchor_found",
        "proof_source",
        "runtime_semantics_changed",
        "candidate_elimination_claim",
    ]
    return " ".join(f"{key}={bool(status.get(key, False))}" for key in keys)


def _lane_detail(lane: Mapping[str, Any]) -> str:
    return (
        f"id={lane.get('lane_id')} category={lane.get('category')} "
        f"required={lane.get('required_anchors')} covered={lane.get('covered_anchors')} "
        f"current_source_complete={lane.get('current_source_complete')} "
        f"probe_supports_lane={lane.get('probe_supports_lane')}"
    )


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


def _display_path(project_root: Path, path: Path) -> str:
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

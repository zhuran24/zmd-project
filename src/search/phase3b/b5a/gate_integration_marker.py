from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.b5a.certified_anchor_promotion_review_packet import (
    B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE,
    EXPECTED_COVERED_ANCHORS,
    EXPECTED_CANDIDATE,
    EXPECTED_SCOPE,
    EXPECTED_STILL_BLOCKED_GATE_IDS,
    build_phase3b_b5a_certified_anchor_promotion_review_packet,
)
from src.search.phase3b.b5a.certification_contracts import (
    PROMOTION_PACKET_METADATA_REQUIRED_FALSE_FIELDS,
    PROMOTION_PACKET_STATUS_REQUIRED_FALSE_FIELDS,
    AUTHORIZATION_SAFETY_FALSE_FIELDS,
    PREFLIGHT_MUTATION_FALSE_FIELDS,
    blocking_checks_pass,
    chain_fingerprint,
    false_field_detail,
    required_false,
    sha256_file,
)

B5A_GATE_INTEGRATION_MARKER_SOURCE = "phase3b_b5a_gate_integration_marker_v1"

DEFAULT_PROMOTION_REVIEW_PACKET_PATH = Path(
    ".artifacts/phase3b_b5a_certified_anchor_promotion_review_packet_20260425/"
    "b5a_certified_anchor_promotion_review_packet.json"
)

REQUIRED_B5A_GATE_CHAIN_INPUT_IDS = [
    "localized_evidence_readiness",
    "localized_evidence_validator",
    "post_acceptance_blocker_summary",
    "promotion_review_packet",
    "promotion_review_payload",
    "reason_localization",
    "review_state",
]

REQUIRED_B5A_GATE_MARKER_CHECK_IDS = [
    "promotion_review_packet_present",
    "promotion_review_packet_source_supported",
    "promotion_review_payload_validated",
    "promotion_review_source_chain_reverified",
    "chain_input_hashes_recorded",
    "candidate_scope_locked",
    "promotion_packet_safety_flags_off",
    "no_runtime_or_final_authorization",
]


def build_phase3b_b5a_gate_integration_marker(
    project_root: Path,
    *,
    promotion_review_packet_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    packet_resolved = _resolve_path(
        project_root,
        (
            promotion_review_packet_path
            if promotion_review_packet_path is not None
            else DEFAULT_PROMOTION_REVIEW_PACKET_PATH
        ),
    )
    packet, packet_error = _load_json_mapping(packet_resolved)
    meta = _mapping(packet.get("metadata")) if packet else {}
    status = _mapping(packet.get("status")) if packet else {}
    candidate = _mapping(packet.get("candidate")) if packet else {}
    validator = (
        _mapping(packet.get("promotion_review_record_validator")) if packet else {}
    )
    actual_validation = _mapping(validator.get("actual_record_validation"))
    chain_paths = _mapping(packet.get("paths")) if packet else {}
    chain_input_hashes = _build_chain_input_hashes(
        project_root,
        packet_resolved,
        chain_paths,
    )
    recorded_chain_fingerprint = chain_fingerprint(chain_input_hashes)
    chain_input_hashes_recorded = bool(
        recorded_chain_fingerprint
        and all(record.get("exists") is True for record in chain_input_hashes)
    )
    reverified_packet, reverified_error = _reverify_promotion_packet_chain(
        project_root,
        chain_paths,
    )
    reverified_status = (
        _mapping(reverified_packet.get("status")) if reverified_packet else {}
    )
    reverified_actual = _mapping(
        _mapping(reverified_packet.get("promotion_review_record_validator")).get(
            "actual_record_validation"
        )
    ) if reverified_packet else {}

    packet_present = bool(packet is not None and packet_error is None)
    packet_source_ok = bool(
        meta.get("source") == B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE
    )
    payload_validated = bool(
        status.get("promotion_review_packet_ready") is True
        and status.get("promotion_review_payload_provided") is True
        and status.get("promotion_review_payload_validated") is True
        and status.get("promotion_review_payload_validation_status") == "passed"
        and status.get("certified_anchor_promotion_review_accepted") is True
        and actual_validation.get("record_payload_provided") is True
        and actual_validation.get("record_payload_validated") is True
        and actual_validation.get("validation_status") == "passed"
        and actual_validation.get("certified_anchor_promotion_review_accepted") is True
        and list(actual_validation.get("failed_rule_ids", [])) == []
    )
    reverified_chain_validated = bool(
        reverified_packet is not None
        and reverified_error is None
        and reverified_status.get("promotion_review_packet_ready") is True
        and reverified_status.get("promotion_review_payload_provided") is True
        and reverified_status.get("promotion_review_payload_validated") is True
        and reverified_status.get("promotion_review_payload_validation_status") == "passed"
        and reverified_status.get("certified_anchor_promotion_review_accepted") is True
        and reverified_actual.get("record_payload_provided") is True
        and reverified_actual.get("record_payload_validated") is True
        and reverified_actual.get("validation_status") == "passed"
        and list(reverified_actual.get("failed_rule_ids", [])) == []
    )
    scope_locked = bool(
        candidate.get("candidate_key") == EXPECTED_CANDIDATE
        and _int_list(candidate.get("covered_anchors")) == EXPECTED_COVERED_ANCHORS
        and candidate.get("scope") == EXPECTED_SCOPE
        and _string_list(status.get("still_blocked_gate_ids"))
        == EXPECTED_STILL_BLOCKED_GATE_IDS
    )
    safety_flags_off = required_false(
        meta,
        PROMOTION_PACKET_METADATA_REQUIRED_FALSE_FIELDS,
    ) and required_false(status, PROMOTION_PACKET_STATUS_REQUIRED_FALSE_FIELDS)
    no_runtime_or_final_authorization = required_false(
        status,
        AUTHORIZATION_SAFETY_FALSE_FIELDS,
    )

    checks = [
        _check(
            "promotion_review_packet_present",
            packet_present,
            (
                "promotion review packet loaded"
                if packet_present
                else packet_error or f"missing:{_display_path(project_root, packet_resolved)}"
            ),
        ),
        _check(
            "promotion_review_packet_source_supported",
            packet_source_ok,
            str(meta.get("source") or "missing"),
        ),
        _check(
            "promotion_review_payload_validated",
            payload_validated,
            (
                "packet_ready="
                + str(status.get("promotion_review_packet_ready"))
                + " payload_validated="
                + str(status.get("promotion_review_payload_validated"))
                + " validation_status="
                + str(status.get("promotion_review_payload_validation_status"))
                + " accepted="
                + str(status.get("certified_anchor_promotion_review_accepted"))
            ),
        ),
        _check(
            "promotion_review_source_chain_reverified",
            reverified_chain_validated,
            _reverify_detail(reverified_packet, reverified_error),
        ),
        _check(
            "chain_input_hashes_recorded",
            chain_input_hashes_recorded,
            (
                "chain_fingerprint=" + str(recorded_chain_fingerprint)
                if chain_input_hashes_recorded
                else "missing_or_unhashable_chain_inputs="
                + str(
                    [
                        record.get("input_id")
                        for record in chain_input_hashes
                        if record.get("exists") is not True
                        or len(str(record.get("sha256") or "")) != 64
                    ]
                )
            ),
        ),
        _check(
            "candidate_scope_locked",
            scope_locked,
            _scope_detail(candidate, status),
        ),
        _check(
            "promotion_packet_safety_flags_off",
            safety_flags_off,
            _safety_detail(meta, status),
        ),
        _check(
            "no_runtime_or_final_authorization",
            no_runtime_or_final_authorization,
            _authorization_detail(status),
        ),
    ]
    marker_ready = all(check["status"] == "pass" for check in checks)

    return {
        "metadata": {
            "source": B5A_GATE_INTEGRATION_MARKER_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "repo_side_b5a_gate_integration_marker_not_runtime_enablement",
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
        },
        "paths": {
            "project_root": str(project_root),
            "promotion_review_packet": _display_path(project_root, packet_resolved),
            "review_state": str(chain_paths.get("review_state") or ""),
            "localized_evidence_validator": str(
                chain_paths.get("localized_evidence_validator") or ""
            ),
            "localized_evidence_readiness": str(
                chain_paths.get("localized_evidence_readiness") or ""
            ),
            "reason_localization": str(chain_paths.get("reason_localization") or ""),
            "post_acceptance_blocker_summary": str(
                chain_paths.get("post_acceptance_blocker_summary") or ""
            ),
            "promotion_review_payload": str(
                chain_paths.get("promotion_review_payload") or ""
            ),
        },
        "chain_input_hashes": chain_input_hashes,
        "chain_fingerprint": recorded_chain_fingerprint,
        "candidate": {
            "candidate_key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "scope": EXPECTED_SCOPE,
        },
        "status": {
            "gate_integration_marker_ready": bool(marker_ready),
            "repo_side_b5a_gate_state_updated": bool(marker_ready),
            "promotion_review_payload_validated": bool(payload_validated),
            "certified_anchor_promotion_review_accepted": bool(payload_validated),
            "b5a_anchor_found": bool(marker_ready),
            "certified_anchor_found": bool(marker_ready),
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "candidate_elimination_claim": False,
            "chain_fingerprint": recorded_chain_fingerprint,
            "recommended_next_step": (
                "run_explicit_final_preflight_with_b5a_gate_integration_marker"
                if marker_ready
                else "repair_b5a_certified_anchor_promotion_review_packet_before_gate_integration"
            ),
        },
        "gate_integration_marker": {
            "marker_kind": "repo_side_b5a_gate_integration_marker",
            "tracked_field": "b5a_anchor_found",
            "candidate_key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "gate_integration_marker_ready": bool(marker_ready),
            "repo_side_b5a_gate_state_updated": bool(marker_ready),
            "b5a_anchor_found": bool(marker_ready),
            "certified_anchor_found": bool(marker_ready),
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "candidate_elimination_claim": False,
            "chain_fingerprint": recorded_chain_fingerprint,
        },
        "checks": checks,
    }


def validate_phase3b_b5a_gate_integration_marker_for_preflight(
    project_root: Path,
    marker: Optional[Mapping[str, Any]],
    *,
    marker_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    meta = _mapping(marker.get("metadata")) if isinstance(marker, Mapping) else {}
    status = _mapping(marker.get("status")) if isinstance(marker, Mapping) else {}
    payload = (
        _mapping(marker.get("gate_integration_marker"))
        if isinstance(marker, Mapping)
        else {}
    )
    candidate = _mapping(marker.get("candidate")) if isinstance(marker, Mapping) else {}
    paths = _mapping(marker.get("paths")) if isinstance(marker, Mapping) else {}
    checks = list(marker.get("checks", [])) if isinstance(marker, Mapping) else []
    chain_input_hashes = (
        list(marker.get("chain_input_hashes", [])) if isinstance(marker, Mapping) else []
    )
    expected_fingerprint = (
        str(marker.get("chain_fingerprint") or "") if isinstance(marker, Mapping) else ""
    )
    status_false_fields = (
        AUTHORIZATION_SAFETY_FALSE_FIELDS
        + PREFLIGHT_MUTATION_FALSE_FIELDS
        + [
            "proof_source",
            "runtime_semantics_changed",
            "checkpoint_written",
            "candidate_elimination_claim",
        ]
    )
    payload_false_fields = status_false_fields
    metadata_false_fields = (
        PROMOTION_PACKET_METADATA_REQUIRED_FALSE_FIELDS
        + ["preflight_gate_mutated"]
    )
    recomputed_records, recomputed_fingerprint, hash_detail = (
        _recompute_chain_input_hashes(project_root, chain_input_hashes)
    )
    reverified_packet, reverified_error = _reverify_promotion_packet_chain(
        project_root,
        paths,
    )
    reverified_chain_validated = _promotion_packet_reverified_for_preflight(
        reverified_packet,
        reverified_error,
    )
    chain_input_ids_exact, chain_input_ids_detail = _exact_record_ids(
        chain_input_hashes,
        key="input_id",
        expected=REQUIRED_B5A_GATE_CHAIN_INPUT_IDS,
    )
    marker_check_ids_exact, marker_check_ids_detail = _exact_record_ids(
        checks,
        key="check_id",
        expected=REQUIRED_B5A_GATE_MARKER_CHECK_IDS,
    )
    chain_input_paths_match, chain_input_paths_detail = (
        _chain_input_paths_match_marker_paths(
            project_root,
            paths,
            chain_input_hashes,
        )
    )
    candidate_scope_ok = bool(
        candidate.get("candidate_key") == EXPECTED_CANDIDATE
        and _int_list(candidate.get("covered_anchors")) == EXPECTED_COVERED_ANCHORS
        and candidate.get("scope") == EXPECTED_SCOPE
    )
    rule_results = [
        _bool_rule(
            "marker_source_supported",
            meta.get("source") == B5A_GATE_INTEGRATION_MARKER_SOURCE,
            str(meta.get("source") or "missing"),
        ),
        _bool_rule(
            "marker_status_ready",
            status.get("gate_integration_marker_ready") is True
            and status.get("repo_side_b5a_gate_state_updated") is True
            and status.get("b5a_anchor_found") is True
            and status.get("certified_anchor_found") is True,
            "gate_ready="
            + str(status.get("gate_integration_marker_ready"))
            + " b5a_anchor_found="
            + str(status.get("b5a_anchor_found"))
            + " certified_anchor_found="
            + str(status.get("certified_anchor_found")),
        ),
        _bool_rule(
            "marker_payload_ready",
            payload.get("gate_integration_marker_ready") is True
            and payload.get("b5a_anchor_found") is True
            and payload.get("certified_anchor_found") is True,
            "payload_gate_ready="
            + str(payload.get("gate_integration_marker_ready"))
            + " payload_b5a_anchor_found="
            + str(payload.get("b5a_anchor_found")),
        ),
        _bool_rule("candidate_scope_locked", candidate_scope_ok, _scope_detail(candidate, status)),
        _bool_rule(
            "required_chain_inputs_exact",
            chain_input_ids_exact,
            chain_input_ids_detail,
        ),
        _bool_rule(
            "required_marker_check_ids_exact",
            marker_check_ids_exact,
            marker_check_ids_detail,
        ),
        _bool_rule(
            "chain_input_paths_match_marker_paths",
            chain_input_paths_match,
            chain_input_paths_detail,
        ),
        _bool_rule(
            "promotion_review_source_chain_reverified_for_preflight",
            reverified_chain_validated,
            _reverify_detail(reverified_packet, reverified_error),
        ),
        _bool_rule(
            "metadata_safety_flags_off",
            required_false(meta, metadata_false_fields),
            false_field_detail(meta, metadata_false_fields, prefix="metadata."),
        ),
        _bool_rule(
            "status_safety_flags_off",
            required_false(status, status_false_fields),
            false_field_detail(status, status_false_fields, prefix="status."),
        ),
        _bool_rule(
            "payload_safety_flags_off",
            required_false(payload, payload_false_fields),
            false_field_detail(payload, payload_false_fields, prefix="payload."),
        ),
        _bool_rule(
            "marker_checks_all_blocking_pass",
            blocking_checks_pass(checks),
            _marker_checks_detail(checks),
        ),
        _bool_rule(
            "chain_input_hashes_match",
            bool(
                expected_fingerprint
                and recomputed_fingerprint
                and expected_fingerprint == recomputed_fingerprint
                and hash_detail == "all_chain_input_hashes_match"
            ),
            hash_detail
            + " expected_fingerprint="
            + str(expected_fingerprint)
            + " recomputed_fingerprint="
            + str(recomputed_fingerprint),
        ),
    ]
    accepted = all(rule["passed"] is True for rule in rule_results)
    return {
        "accepted": bool(accepted),
        "marker_path": str(marker_path) if marker_path is not None else None,
        "chain_fingerprint": expected_fingerprint or None,
        "recomputed_chain_fingerprint": recomputed_fingerprint,
        "recomputed_chain_input_hashes": recomputed_records,
        "failed_rule_ids": [
            str(rule["rule_id"]) for rule in rule_results if rule["passed"] is not True
        ],
        "rule_results": rule_results,
        "summary": (
            "B5A gate integration marker accepted for final preflight"
            if accepted
            else "B5A gate integration marker rejected: "
            + ",".join(
                str(rule["rule_id"])
                for rule in rule_results
                if rule["passed"] is not True
            )
        ),
    }


def render_phase3b_b5a_gate_integration_marker_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    marker = _mapping(report.get("gate_integration_marker"))
    lines = [
        "# Phase 3B B5A Gate Integration Marker",
        "",
        f"- Marker ready: `{status.get('gate_integration_marker_ready')}`",
        f"- Repo-side B5A gate state updated: `{status.get('repo_side_b5a_gate_state_updated')}`",
        f"- B5A anchor found: `{status.get('b5a_anchor_found')}`",
        f"- Certified anchor found: `{status.get('certified_anchor_found')}`",
        f"- Proof source: `{status.get('proof_source')}`",
        f"- Runtime semantics changed: `{status.get('runtime_semantics_changed')}`",
        f"- Checkpoint written: `{status.get('checkpoint_written')}`",
        f"- Runtime elimination authorized: `{status.get('runtime_elimination_authorized')}`",
        f"- Final 168h authorized: `{status.get('final_168h_authorized')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        "",
        "## Marker",
        "",
        f"- Kind: `{marker.get('marker_kind')}`",
        f"- Candidate: `{marker.get('candidate_key')}`",
        f"- Covered anchors: `{marker.get('covered_anchors')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
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


def render_phase3b_b5a_gate_integration_marker_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B B5A gate integration marker",
        f"gate_integration_marker_ready={bool(status.get('gate_integration_marker_ready', False))}",
        f"repo_side_b5a_gate_state_updated={bool(status.get('repo_side_b5a_gate_state_updated', False))}",
        f"b5a_anchor_found={bool(status.get('b5a_anchor_found', False))}",
        f"certified_anchor_found={bool(status.get('certified_anchor_found', False))}",
        f"proof_source={bool(status.get('proof_source', False))}",
        f"runtime_semantics_changed={bool(status.get('runtime_semantics_changed', False))}",
        f"checkpoint_written={bool(status.get('checkpoint_written', False))}",
        f"runtime_elimination_authorized={bool(status.get('runtime_elimination_authorized', False))}",
        f"final_168h_authorized={bool(status.get('final_168h_authorized', False))}",
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


def write_phase3b_b5a_gate_integration_marker(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "b5a_gate_integration_marker",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(md_path, render_phase3b_b5a_gate_integration_marker_markdown(report))
    _atomic_write_text(txt_path, render_phase3b_b5a_gate_integration_marker_text(report))
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_chain_input_hashes(
    project_root: Path,
    packet_resolved: Path,
    chain_paths: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    path_by_id: dict[str, Path] = {
        "promotion_review_packet": packet_resolved,
    }
    for input_id in [
        "review_state",
        "localized_evidence_validator",
        "localized_evidence_readiness",
        "reason_localization",
        "post_acceptance_blocker_summary",
        "promotion_review_payload",
    ]:
        raw_path = str(chain_paths.get(input_id) or "").strip()
        if raw_path:
            path_by_id[input_id] = _resolve_path(project_root, Path(raw_path))
        else:
            path_by_id[input_id] = project_root / "__missing_chain_input__" / input_id
    records: list[Dict[str, Any]] = []
    for input_id in sorted(path_by_id):
        path = path_by_id[input_id]
        digest = sha256_file(path)
        records.append(
            {
                "input_id": input_id,
                "path": _display_path(project_root, path),
                "exists": digest is not None,
                "sha256": digest,
            }
        )
    return records


def _recompute_chain_input_hashes(
    project_root: Path,
    records: list[Any],
) -> tuple[list[Dict[str, Any]], Optional[str], str]:
    if not records:
        return [], None, "chain_input_hashes=missing"
    recomputed: list[Dict[str, Any]] = []
    mismatches: list[str] = []
    for item in records:
        if not isinstance(item, Mapping):
            mismatches.append("malformed_record")
            continue
        input_id = str(item.get("input_id") or "")
        raw_path = str(item.get("path") or "")
        expected_exists = item.get("exists")
        expected_hash = str(item.get("sha256") or "")
        resolved = _resolve_path(project_root, Path(raw_path)) if raw_path else project_root
        actual_hash = sha256_file(resolved)
        actual_exists = actual_hash is not None
        record = {
            "input_id": input_id,
            "path": raw_path,
            "exists": actual_exists,
            "sha256": actual_hash,
        }
        recomputed.append(record)
        if (
            not input_id
            or not raw_path
            or expected_exists is not True
            or expected_exists is not actual_exists
            or len(expected_hash) != 64
        ):
            mismatches.append(input_id or "missing_input_id")
        elif actual_hash != expected_hash:
            mismatches.append(input_id)
    fingerprint = chain_fingerprint(recomputed)
    detail = (
        "mismatched_inputs=" + str(mismatches)
        if mismatches
        else "all_chain_input_hashes_match"
    )
    return recomputed, fingerprint, detail


def _exact_record_ids(
    records: list[Any],
    *,
    key: str,
    expected: list[str],
) -> tuple[bool, str]:
    actual: list[str] = []
    malformed = 0
    for item in records:
        if not isinstance(item, Mapping):
            malformed += 1
            continue
        actual.append(str(item.get(key) or ""))
    duplicates = sorted({item for item in actual if actual.count(item) > 1})
    ok = bool(malformed == 0 and actual == expected and not duplicates)
    return (
        ok,
        "actual="
        + str(actual)
        + " expected="
        + str(expected)
        + " malformed="
        + str(malformed)
        + " duplicates="
        + str(duplicates),
    )


def _chain_input_paths_match_marker_paths(
    project_root: Path,
    paths: Mapping[str, Any],
    records: list[Any],
) -> tuple[bool, str]:
    expected_paths = _expected_chain_input_paths(project_root, paths)
    mismatches: list[str] = []
    if set(expected_paths) != set(REQUIRED_B5A_GATE_CHAIN_INPUT_IDS):
        missing = sorted(set(REQUIRED_B5A_GATE_CHAIN_INPUT_IDS) - set(expected_paths))
        extra = sorted(set(expected_paths) - set(REQUIRED_B5A_GATE_CHAIN_INPUT_IDS))
        mismatches.append(f"path_keys_missing={missing} extra={extra}")
    record_paths: dict[str, str] = {}
    for item in records:
        if not isinstance(item, Mapping):
            mismatches.append("malformed_record")
            continue
        input_id = str(item.get("input_id") or "")
        record_paths[input_id] = _normalize_path_text(str(item.get("path") or ""))
    for input_id in REQUIRED_B5A_GATE_CHAIN_INPUT_IDS:
        expected_path = _normalize_path_text(expected_paths.get(input_id, ""))
        actual_path = record_paths.get(input_id, "")
        if not expected_path or actual_path != expected_path:
            mismatches.append(
                input_id
                + ":record="
                + str(actual_path or "missing")
                + " expected="
                + str(expected_path or "missing")
            )
    return (
        not mismatches,
        "all_chain_input_paths_match_marker_paths"
        if not mismatches
        else "mismatched_chain_input_paths=" + str(mismatches),
    )


def _expected_chain_input_paths(
    project_root: Path,
    paths: Mapping[str, Any],
) -> dict[str, str]:
    expected: dict[str, str] = {}
    for input_id in REQUIRED_B5A_GATE_CHAIN_INPUT_IDS:
        raw_path = str(paths.get(input_id) or "").strip()
        if not raw_path:
            continue
        expected[input_id] = _display_path(
            project_root,
            _resolve_path(project_root, Path(raw_path)),
        ) or ""
    return expected


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


def _all_false(mapping: Mapping[str, Any], keys: list[str]) -> bool:
    return required_false(mapping, keys)


def _scope_detail(candidate: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    return (
        "candidate_key="
        + str(candidate.get("candidate_key"))
        + " covered_anchors="
        + str(candidate.get("covered_anchors"))
        + " scope="
        + str(candidate.get("scope"))
        + " still_blocked_gate_ids="
        + str(status.get("still_blocked_gate_ids"))
    )


def _safety_detail(meta: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    meta_detail = false_field_detail(
        meta,
        PROMOTION_PACKET_METADATA_REQUIRED_FALSE_FIELDS,
        prefix="metadata.",
    )
    status_detail = false_field_detail(
        status,
        PROMOTION_PACKET_STATUS_REQUIRED_FALSE_FIELDS,
        prefix="status.",
    )
    return meta_detail + " " + status_detail


def _authorization_detail(status: Mapping[str, Any]) -> str:
    return false_field_detail(status, AUTHORIZATION_SAFETY_FALSE_FIELDS)


def _reverify_promotion_packet_chain(
    project_root: Path,
    paths: Mapping[str, Any],
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    required = [
        "review_state",
        "localized_evidence_validator",
        "localized_evidence_readiness",
        "reason_localization",
        "post_acceptance_blocker_summary",
        "promotion_review_payload",
    ]
    missing = [key for key in required if not str(paths.get(key) or "").strip()]
    if missing:
        return None, "missing_chain_paths:" + ",".join(missing)
    try:
        return (
            build_phase3b_b5a_certified_anchor_promotion_review_packet(
                project_root,
                review_state_path=Path(str(paths["review_state"])),
                localized_evidence_validator_path=Path(
                    str(paths["localized_evidence_validator"])
                ),
                localized_evidence_readiness_path=Path(
                    str(paths["localized_evidence_readiness"])
                ),
                reason_localization_path=Path(str(paths["reason_localization"])),
                post_acceptance_blocker_summary_path=Path(
                    str(paths["post_acceptance_blocker_summary"])
                ),
                promotion_review_payload_path=Path(
                    str(paths["promotion_review_payload"])
                ),
            ),
            None,
        )
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _promotion_packet_reverified_for_preflight(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
) -> bool:
    if report is None or error is not None:
        return False
    status = _mapping(report.get("status"))
    actual = _mapping(
        _mapping(report.get("promotion_review_record_validator")).get(
            "actual_record_validation"
        )
    )
    return bool(
        status.get("promotion_review_packet_ready") is True
        and status.get("promotion_review_payload_provided") is True
        and status.get("promotion_review_payload_validated") is True
        and status.get("promotion_review_payload_validation_status") == "passed"
        and status.get("certified_anchor_promotion_review_accepted") is True
        and actual.get("record_payload_provided") is True
        and actual.get("record_payload_validated") is True
        and actual.get("validation_status") == "passed"
        and actual.get("certified_anchor_promotion_review_accepted") is True
        and list(actual.get("failed_rule_ids", [])) == []
    )


def _reverify_detail(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
) -> str:
    if report is None:
        return error or "source chain re-verification did not run"
    status = _mapping(report.get("status"))
    failed = [
        str(check.get("check_id"))
        for check in list(report.get("checks", []))
        if isinstance(check, Mapping) and check.get("status") == "fail"
    ]
    actual = _mapping(
        _mapping(report.get("promotion_review_record_validator")).get(
            "actual_record_validation"
        )
    )
    return (
        "packet_ready="
        + str(status.get("promotion_review_packet_ready"))
        + " payload_validated="
        + str(status.get("promotion_review_payload_validated"))
        + " accepted="
        + str(status.get("certified_anchor_promotion_review_accepted"))
        + " failed_checks="
        + str(failed)
        + " failed_rules="
        + str(actual.get("failed_rule_ids"))
    )


def _check(check_id: str, passed: bool, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": "pass" if passed else "fail",
        "detail": str(detail),
    }


def _bool_rule(rule_id: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {
        "rule_id": str(rule_id),
        "passed": bool(passed),
        "detail": str(detail),
    }


def _marker_checks_detail(checks: Any) -> str:
    if not isinstance(checks, list):
        return "checks=missing_or_not_list"
    failed = [
        str(check.get("check_id") or check.get("id") or "unknown")
        for check in checks
        if isinstance(check, Mapping)
        and str(check.get("status")) != "pass"
        and check.get("blocking") is not False
    ]
    return "blocking_failed=" + str(failed)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip().lower()


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)

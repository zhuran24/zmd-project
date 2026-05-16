from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
)
INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
)
INGEST_REVIEW_COVER_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_v1"
)
DEFAULT_INGEST_REVIEW_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_20260424/"
    "anchor119_row_domain_ingest_review_instruction_packet.json"
)
DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
)
COVER_NOTE_NOTICE = (
    "Review-only/spec-only/default-off cover note only. This package compresses the "
    "existing anchor119 ingest-review packet into a short operator/reviewer entrypoint, "
    "but it does not perform ingest, does not update repo-side review state, does not "
    "claim any actual human review has happened, and does not authorize execution."
)
PRESERVED_FALSE_STATES_DETAIL = (
    "Preserve repo_side_review_state_updated=false, reviewed_runtime_patch_exists=false, "
    "runtime_enablement_allowed=false, proof_source=false, candidate_elimination_claim=false, "
    "solver_invoked=false, actual_human_review_has_happened=false, and execution_authorized=false."
)
REQUIRED_FORBIDDEN_CLAIMS = [
    "Do not claim that this cover note is anything other than review-only/spec-only/default-off.",
    "Do not claim solver-backed search, solver invocation, proof-backed validation, or candidate elimination.",
    "Do not update repo-side review state from this cover note.",
    "Do not imply reviewed_runtime_patch_exists=true.",
    "Do not imply runtime_enablement_allowed=true.",
    "Do not imply any actual human review has happened.",
    "Do not authorize execution.",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note(
    project_root: Path,
    *,
    ingest_review_instruction_packet_path: Optional[Path] = None,
    ingest_review_operator_handoff_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    instruction_packet_resolved = _resolve_path(
        project_root,
        ingest_review_instruction_packet_path
        if ingest_review_instruction_packet_path is not None
        else DEFAULT_INGEST_REVIEW_INSTRUCTION_PACKET_PATH,
    )
    operator_handoff_bundle_resolved = _resolve_path(
        project_root,
        ingest_review_operator_handoff_bundle_path
        if ingest_review_operator_handoff_bundle_path is not None
        else DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH,
    )

    instruction_packet_report, instruction_packet_error = _load_json_mapping(
        instruction_packet_resolved
    )
    operator_handoff_bundle_report, operator_handoff_bundle_error = _load_json_mapping(
        operator_handoff_bundle_resolved
    )

    instruction_packet_meta = (
        _mapping(instruction_packet_report.get("metadata"))
        if instruction_packet_report
        else {}
    )
    instruction_packet_status = (
        _mapping(instruction_packet_report.get("status"))
        if instruction_packet_report
        else {}
    )
    instruction_packet = (
        _mapping(instruction_packet_report.get("ingest_review_instruction_packet"))
        if instruction_packet_report
        else {}
    )
    operator_handoff_bundle_meta = (
        _mapping(operator_handoff_bundle_report.get("metadata"))
        if operator_handoff_bundle_report
        else {}
    )
    operator_handoff_bundle_status = (
        _mapping(operator_handoff_bundle_report.get("status"))
        if operator_handoff_bundle_report
        else {}
    )
    operator_handoff_bundle = (
        _mapping(
            operator_handoff_bundle_report.get("ingest_review_operator_handoff_bundle")
        )
        if operator_handoff_bundle_report
        else {}
    )

    packet_target = _mapping(instruction_packet.get("packet_target"))
    operator_target = _mapping(operator_handoff_bundle.get("operator_target"))
    packet_preserved_state = _mapping(
        instruction_packet.get("preserved_state_assertions")
    )
    handoff_preserved_state = _mapping(
        operator_handoff_bundle.get("preserved_state_assertions")
    )

    instruction_packet_present = bool(
        instruction_packet_report is not None
        and instruction_packet_error is None
        and instruction_packet_meta.get("source")
        == INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE
    )
    operator_handoff_bundle_present = bool(
        operator_handoff_bundle_report is not None
        and operator_handoff_bundle_error is None
        and operator_handoff_bundle_meta.get("source")
        == INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE
    )

    upstream_instruction_packet_ready = bool(
        instruction_packet_present
        and instruction_packet_status.get("ingest_review_instruction_packet_ready", False)
    )
    upstream_instruction_packet_contract_compatible = bool(
        instruction_packet_present
        and instruction_packet_status.get("contract_compatible", False)
    )
    upstream_operator_handoff_bundle_ready = bool(
        operator_handoff_bundle_present
        and operator_handoff_bundle_status.get(
            "ingest_review_operator_handoff_bundle_ready", False
        )
    )
    upstream_operator_handoff_bundle_contract_compatible = bool(
        operator_handoff_bundle_present
        and operator_handoff_bundle_status.get("contract_compatible", False)
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            _mapping(instruction_packet_report.get("candidate")).get("key")
            if instruction_packet_report
            else None,
            _mapping(operator_handoff_bundle_report.get("candidate")).get("key")
            if operator_handoff_bundle_report
            else None,
        ],
        normalize=_normalize_text,
    )
    anchor_idx, anchor_idx_locked = _locked_value(
        [
            _mapping(instruction_packet_report.get("candidate")).get("anchor_idx")
            if instruction_packet_report
            else None,
            _mapping(operator_handoff_bundle_report.get("candidate")).get("anchor_idx")
            if operator_handoff_bundle_report
            else None,
        ],
        normalize=_normalize_scalar,
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            _mapping(instruction_packet_report.get("candidate")).get(
                "formulation_profile"
            )
            if instruction_packet_report
            else None,
            _mapping(operator_handoff_bundle_report.get("candidate")).get(
                "formulation_profile"
            )
            if operator_handoff_bundle_report
            else None,
        ],
        normalize=_normalize_text,
    )
    candidate_consistent = bool(
        candidate_key_locked and anchor_idx_locked and formulation_profile_locked
    )

    review_state_kind, review_state_kind_locked = _locked_value(
        [
            packet_target.get("review_state_kind"),
            operator_target.get("review_state_kind"),
        ],
        normalize=_normalize_text,
    )
    tracked_field, tracked_field_locked = _locked_value(
        [
            packet_target.get("tracked_field"),
            operator_target.get("tracked_field"),
        ],
        normalize=_normalize_text,
    )
    record_identity, record_identity_locked = _locked_value(
        [
            packet_target.get("record_identity"),
            operator_target.get("record_identity"),
        ],
        normalize=_normalize_text,
    )
    target_record_type, target_record_type_locked = _locked_value(
        [
            packet_target.get("target_record_type"),
            operator_target.get("target_record_type"),
        ],
        normalize=_normalize_text,
    )
    scope, scope_locked = _locked_value(
        [
            packet_target.get("scope"),
            operator_target.get("scope"),
        ],
        normalize=_normalize_text,
    )
    proposed_field_value_if_approved, proposed_field_value_if_approved_locked = (
        _locked_value(
            [
                packet_target.get("proposed_field_value_if_approved"),
                operator_target.get("proposed_field_value_if_approved"),
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

    read_first_entries = _mapping_list(instruction_packet.get("open_these_first"))[:3]
    handoff_path_display = _display_path(project_root, operator_handoff_bundle_resolved)
    first_read_entry = read_first_entries[0] if read_first_entries else {}
    read_first_present = bool(
        read_first_entries
        and str(first_read_entry.get("artifact_id") or "").strip()
        == "ingest_review_operator_handoff_bundle"
        and _normalize_path_text(first_read_entry.get("path"))
        == _normalize_path_text(handoff_path_display)
    )

    merged_gates = _merge_gate_entries(
        instruction_packet_report.get("gates") if instruction_packet_report else None,
        operator_handoff_bundle_report.get("gates")
        if operator_handoff_bundle_report
        else None,
    )
    merged_gate_details = {
        str(entry.get("gate_id")): str(entry.get("detail") or "")
        for entry in merged_gates
        if isinstance(entry, Mapping) and entry.get("gate_id")
    }
    current_blocker_ids = _ordered_union(
        _string_list(
            instruction_packet_report.get("still_blocked_gate_ids")
            if instruction_packet_report
            else None
        ),
        _string_list(
            operator_handoff_bundle_report.get("still_blocked_gate_ids")
            if operator_handoff_bundle_report
            else None
        ),
    )
    current_blockers = [
        {
            "gate_id": gate_id,
            "detail": merged_gate_details.get(
                gate_id, "Still blocked and must be carried forward unchanged."
            ),
        }
        for gate_id in current_blocker_ids
    ]
    current_blockers_present = bool(current_blockers)

    review_only_contract_retained = _review_only_contract_retained(
        instruction_packet_meta, operator_handoff_bundle_meta
    )
    repo_side_review_state_updated_false = not any(
        bool(value)
        for value in [
            instruction_packet_meta.get("repo_side_review_state_updated", False),
            operator_handoff_bundle_meta.get("repo_side_review_state_updated", False),
            instruction_packet_status.get("repo_side_review_state_updated", False),
            operator_handoff_bundle_status.get("repo_side_review_state_updated", False),
            packet_preserved_state.get("repo_side_review_state_updated", False),
            handoff_preserved_state.get("repo_side_review_state_updated", False),
        ]
    )
    reviewed_runtime_patch_exists_false = not any(
        bool(value)
        for value in [
            instruction_packet_status.get("reviewed_runtime_patch_exists", False),
            operator_handoff_bundle_status.get("reviewed_runtime_patch_exists", False),
            packet_preserved_state.get("reviewed_runtime_patch_exists", False),
            handoff_preserved_state.get("reviewed_runtime_patch_exists", False),
        ]
    )
    runtime_enablement_allowed_false = not any(
        bool(value)
        for value in [
            instruction_packet_status.get("runtime_enablement_allowed", False),
            operator_handoff_bundle_status.get("runtime_enablement_allowed", False),
            packet_preserved_state.get("runtime_enablement_allowed", False),
            handoff_preserved_state.get("runtime_enablement_allowed", False),
        ]
    )
    proof_source_false = not any(
        bool(value)
        for value in [
            instruction_packet_meta.get("proof_source", False),
            operator_handoff_bundle_meta.get("proof_source", False),
            packet_preserved_state.get("proof_source", False),
            handoff_preserved_state.get("proof_source", False),
        ]
    )
    candidate_elimination_claim_false = not any(
        bool(value)
        for value in [
            instruction_packet_meta.get("candidate_elimination_claim", False),
            operator_handoff_bundle_meta.get("candidate_elimination_claim", False),
            packet_preserved_state.get("candidate_elimination_claim", False),
            handoff_preserved_state.get("candidate_elimination_claim", False),
        ]
    )
    solver_invoked_false = not any(
        bool(value)
        for value in [
            instruction_packet_meta.get("solver_invoked", False),
            operator_handoff_bundle_meta.get("solver_invoked", False),
            packet_preserved_state.get("solver_invoked", False),
            handoff_preserved_state.get("solver_invoked", False),
        ]
    )
    actual_human_review_has_happened_false = not any(
        bool(value)
        for value in [
            packet_target.get("actual_human_review_has_happened", False),
            operator_target.get("actual_human_review_has_happened", False),
        ]
    )
    execution_authorized_false = not any(
        bool(value)
        for value in [
            packet_target.get("execution_authorized", False),
            operator_target.get("execution_authorized", False),
            packet_preserved_state.get("execution_authorized", False),
            handoff_preserved_state.get("execution_authorized", False),
        ]
    )
    preserved_false_states_retained = bool(
        repo_side_review_state_updated_false
        and reviewed_runtime_patch_exists_false
        and runtime_enablement_allowed_false
        and proof_source_false
        and candidate_elimination_claim_false
        and solver_invoked_false
        and actual_human_review_has_happened_false
        and execution_authorized_false
    )

    forbidden_claims = _ordered_union(
        REQUIRED_FORBIDDEN_CLAIMS,
        _string_list(instruction_packet.get("forbidden_claims_or_actions")),
        _string_list(operator_handoff_bundle.get("explicit_non_goals")),
        _string_list(operator_handoff_bundle.get("disallowed_actions")),
    )

    contract_compatible = bool(
        upstream_instruction_packet_contract_compatible
        and upstream_operator_handoff_bundle_contract_compatible
        and candidate_consistent
        and packet_target_consistent
        and read_first_present
        and current_blockers_present
        and review_only_contract_retained
        and preserved_false_states_retained
    )
    ingest_review_cover_note_ready = bool(
        upstream_instruction_packet_ready
        and upstream_operator_handoff_bundle_ready
        and contract_compatible
    )

    checks = [
        _check(
            "instruction_packet_present",
            "pass" if instruction_packet_present else "fail",
            _presence_detail(
                instruction_packet_report,
                instruction_packet_error,
                instruction_packet_meta,
                INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE,
                project_root,
                instruction_packet_resolved,
            ),
        ),
        _check(
            "instruction_packet_ready",
            "pass" if upstream_instruction_packet_ready else "fail",
            "ingest_review_instruction_packet_ready=true"
            if upstream_instruction_packet_ready
            else "ingest_review_instruction_packet_ready=false",
        ),
        _check(
            "instruction_packet_contract_compatible",
            "pass" if upstream_instruction_packet_contract_compatible else "fail",
            "contract_compatible=true"
            if upstream_instruction_packet_contract_compatible
            else "contract_compatible=false",
        ),
        _check(
            "operator_handoff_bundle_present",
            "pass" if operator_handoff_bundle_present else "fail",
            _presence_detail(
                operator_handoff_bundle_report,
                operator_handoff_bundle_error,
                operator_handoff_bundle_meta,
                INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE,
                project_root,
                operator_handoff_bundle_resolved,
            ),
        ),
        _check(
            "operator_handoff_bundle_ready",
            "pass" if upstream_operator_handoff_bundle_ready else "fail",
            "ingest_review_operator_handoff_bundle_ready=true"
            if upstream_operator_handoff_bundle_ready
            else "ingest_review_operator_handoff_bundle_ready=false",
        ),
        _check(
            "operator_handoff_bundle_contract_compatible",
            "pass" if upstream_operator_handoff_bundle_contract_compatible else "fail",
            "contract_compatible=true"
            if upstream_operator_handoff_bundle_contract_compatible
            else "contract_compatible=false",
        ),
        _check(
            "candidate_consistent",
            "pass" if candidate_consistent else "fail",
            "Candidate key, anchor_idx, and formulation_profile stay locked across the packet and handoff bundle."
            if candidate_consistent
            else "Candidate identity drifted between the instruction packet and operator handoff bundle.",
        ),
        _check(
            "packet_target_consistent",
            "pass" if packet_target_consistent else "fail",
            "Target review-state identity, tracked field, scope, and proposed field value stay locked."
            if packet_target_consistent
            else "Packet target drifted between the instruction packet and operator handoff bundle.",
        ),
        _check(
            "read_first_present",
            "pass" if read_first_present else "fail",
            "read_first starts with the operator handoff bundle path from the locked packet."
            if read_first_present
            else "Packet no longer points to the operator handoff bundle as the first thing to read.",
        ),
        _check(
            "current_blockers_present",
            "pass" if current_blockers_present else "fail",
            "Current blockers are available for carry-forward."
            if current_blockers_present
            else "No still-blocked gate ids were available from the upstream artifacts.",
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "Both upstream artifacts retain review_only/spec_only/default_off with proof_source=false, candidate_elimination_claim=false, and solver_invoked=false."
            if review_only_contract_retained
            else "At least one upstream artifact drifted away from the required review-only/default-off semantics.",
        ),
        _check(
            "preserved_false_states_retained",
            "pass" if preserved_false_states_retained else "fail",
            PRESERVED_FALSE_STATES_DETAIL
            if preserved_false_states_retained
            else "An upstream artifact implies repo-side mutation, runtime enablement, actual human review, proof promotion, or execution authorization.",
        ),
    ]
    ready_prerequisite_check_ids = {
        "instruction_packet_present",
        "instruction_packet_ready",
        "instruction_packet_contract_compatible",
        "operator_handoff_bundle_present",
        "operator_handoff_bundle_ready",
        "operator_handoff_bundle_contract_compatible",
        "candidate_consistent",
        "packet_target_consistent",
        "read_first_present",
        "current_blockers_present",
        "review_only_contract_retained",
        "preserved_false_states_retained",
    }
    missing_ready_gate_ids = [
        check["check_id"]
        for check in checks
        if check["status"] == "fail" and check["check_id"] in ready_prerequisite_check_ids
    ]

    if ingest_review_cover_note_ready:
        recommended_next_step = (
            "future_manual_operator_or_reviewer_may_use_cover_note_as_entrypoint_without_repo_state_mutation"
        )
        handoff_summary = (
            f"Future manual ingest-review cover note for candidate {candidate_key} / anchor {anchor_idx}: "
            "read the operator handoff bundle first, then the locked validator/example references named by the packet; "
            "carry forward all listed blockers; keep repo_side_review_state_updated=false, "
            "reviewed_runtime_patch_exists=false, and runtime_enablement_allowed=false; "
            "do not claim human review, proof, candidate elimination, or execution authorization."
        )
    else:
        recommended_next_step = "repair_ingest_review_cover_note_inputs"
        handoff_summary = (
            "Cover note is blocked until the locked instruction packet and operator handoff bundle are both "
            "present, ready, and still contract-compatible."
        )

    return {
        "metadata": {
            "source": INGEST_REVIEW_COVER_NOTE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_ingest_review_cover_note_review_only_spec_only_default_off_"
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
            "ingest_review_instruction_packet": _display_path(
                project_root, instruction_packet_resolved
            ),
            "ingest_review_operator_handoff_bundle": _display_path(
                project_root, operator_handoff_bundle_resolved
            ),
        },
        "candidate": {
            "key": candidate_key,
            "anchor_idx": anchor_idx,
            "formulation_profile": formulation_profile,
        },
        "status": {
            "ingest_review_cover_note_ready": ingest_review_cover_note_ready,
            "upstream_instruction_packet_ready": upstream_instruction_packet_ready,
            "upstream_operator_handoff_bundle_ready": upstream_operator_handoff_bundle_ready,
            "contract_compatible": contract_compatible,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "operator_phase": "review_only_manual_ingest_review_cover_note",
            "missing_ready_gate_ids": missing_ready_gate_ids,
            "recommended_next_step": recommended_next_step,
            "handoff_summary": handoff_summary,
        },
        "ingest_review_cover_note": {
            "packet_target": {
                "package_kind": "bounded_review_only_cover_note",
                "operator_role": str(
                    packet_target.get("operator_role")
                    or operator_target.get("operator_role")
                    or "future_manual_ingest_review_operator"
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
                "package_summary": (
                    "Short cover note for the future manual ingest-review path on anchor119. "
                    "It compresses the existing instruction packet into one review-only/spec-only/default-off "
                    "entrypoint for operators and reviewers, and it does not validate records, mutate repo state, "
                    "or authorize execution."
                ),
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "read_first": [
                {
                    "order": entry.get("order"),
                    "artifact_id": str(entry.get("artifact_id") or ""),
                    "path": str(entry.get("path") or ""),
                    "why": str(entry.get("why") or ""),
                }
                for entry in read_first_entries
            ],
            "current_blockers": current_blockers,
            "preserved_false_states": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "proof_source": False,
                "candidate_elimination_claim": False,
                "solver_invoked": False,
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
                "detail": PRESERVED_FALSE_STATES_DETAIL,
            },
            "forbidden_claims": forbidden_claims,
            "handoff_summary": handoff_summary,
            "cover_note_notice": COVER_NOTE_NOTICE,
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    cover_note = _mapping(report.get("ingest_review_cover_note"))
    packet_target = _mapping(cover_note.get("packet_target"))
    preserved_false_states = _mapping(cover_note.get("preserved_false_states"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Ingest Review Cover Note",
        "",
        f"- Cover note ready: `{status.get('ingest_review_cover_note_ready')}`",
        f"- Upstream instruction packet ready: `{status.get('upstream_instruction_packet_ready')}`",
        f"- Upstream operator handoff bundle ready: `{status.get('upstream_operator_handoff_bundle_ready')}`",
        f"- Contract compatible: `{status.get('contract_compatible')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Operator phase: `{status.get('operator_phase')}`",
        f"- Missing ready gate ids: `{', '.join(_string_list(status.get('missing_ready_gate_ids'))) or '(none)'}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        "",
        "## Packet Target",
        "",
        f"- Package kind: `{packet_target.get('package_kind')}`",
        f"- Operator role: `{packet_target.get('operator_role')}`",
        f"- Candidate key: `{packet_target.get('candidate_key')}`",
        f"- Anchor idx: `{packet_target.get('anchor_idx')}`",
        f"- Formulation profile: `{packet_target.get('formulation_profile')}`",
        f"- Record identity: `{packet_target.get('record_identity')}`",
        f"- Scope: `{packet_target.get('scope')}`",
        f"- Package summary: {packet_target.get('package_summary')}",
        f"- Cover note notice: {cover_note.get('cover_note_notice')}",
        "",
        "## Read First",
        "",
    ]
    for entry in cover_note.get("read_first", []):
        if isinstance(entry, Mapping):
            lines.append(
                f"{entry.get('order')}. `{entry.get('artifact_id')}`: `{entry.get('path')}`"
            )
            lines.append(f"   {entry.get('why')}")
    lines.extend(
        [
            "",
            "## Current Blockers",
            "",
        ]
    )
    for entry in cover_note.get("current_blockers", []):
        if isinstance(entry, Mapping):
            lines.append(
                f"- `{entry.get('gate_id')}`: {entry.get('detail')}"
            )
    lines.extend(
        [
            "",
            "## Preserved False States",
            "",
            f"- repo_side_review_state_updated: `{preserved_false_states.get('repo_side_review_state_updated')}`",
            f"- reviewed_runtime_patch_exists: `{preserved_false_states.get('reviewed_runtime_patch_exists')}`",
            f"- runtime_enablement_allowed: `{preserved_false_states.get('runtime_enablement_allowed')}`",
            f"- proof_source: `{preserved_false_states.get('proof_source')}`",
            f"- candidate_elimination_claim: `{preserved_false_states.get('candidate_elimination_claim')}`",
            f"- solver_invoked: `{preserved_false_states.get('solver_invoked')}`",
            f"- actual_human_review_has_happened: `{preserved_false_states.get('actual_human_review_has_happened')}`",
            f"- execution_authorized: `{preserved_false_states.get('execution_authorized')}`",
            f"- Detail: {preserved_false_states.get('detail')}",
            "",
            "## Forbidden Claims",
            "",
        ]
    )
    for entry in cover_note.get("forbidden_claims", []):
        lines.append(f"- {entry}")
    lines.extend(
        [
            "",
            "## Handoff Summary",
            "",
            str(cover_note.get("handoff_summary") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    paths = _mapping(report.get("paths"))
    cover_note = _mapping(report.get("ingest_review_cover_note"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain ingest review cover note",
            "ingest_review_cover_note_ready="
            + str(status.get("ingest_review_cover_note_ready")),
            "upstream_instruction_packet_ready="
            + str(status.get("upstream_instruction_packet_ready")),
            "upstream_operator_handoff_bundle_ready="
            + str(status.get("upstream_operator_handoff_bundle_ready")),
            "contract_compatible=" + str(status.get("contract_compatible")),
            "repo_side_review_state_updated="
            + str(status.get("repo_side_review_state_updated")),
            "reviewed_runtime_patch_exists="
            + str(status.get("reviewed_runtime_patch_exists")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            "instruction_packet_path="
            + str(paths.get("ingest_review_instruction_packet")),
            "operator_handoff_bundle_path="
            + str(paths.get("ingest_review_operator_handoff_bundle")),
            "current_blockers="
            + ",".join(
                str(entry.get("gate_id"))
                for entry in cover_note.get("current_blockers", [])
                if isinstance(entry, Mapping) and entry.get("gate_id")
            ),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_ingest_review_cover_note",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


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


def _ordered_union(*sequences: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for sequence in sequences:
        for entry in sequence:
            value = str(entry).strip()
            if not value or value in seen:
                continue
            result.append(value)
            seen.add(value)
    return result


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

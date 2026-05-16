from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_instruction_packet_v1"
)
ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_operator_handoff_bundle_v1"
)
ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_cover_note_v1"
)

LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"

DEFAULT_ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_instruction_packet_20260424/"
    "anchor119_row_domain_acceptance_authorization_instruction_packet.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.json"
)

LOCAL_FORBIDDEN_CLAIMS = [
    "Do not treat this cover note as authorization to execute the locked prod_4x4_normal acceptance command.",
    "Do not enable runtime from this cover note.",
    "Do not execute acceptance from this cover note.",
    "Do not claim any actual human acceptance-authorization review has already happened.",
    "Do not claim proof_source=true, solver invocation, or candidate elimination from this cover note.",
    "Do not claim blocked prerequisite gates are cleared from this cover note.",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note(
    project_root: Path,
    *,
    acceptance_authorization_instruction_packet_path: Optional[Path] = None,
    acceptance_authorization_operator_handoff_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    instruction_packet_resolved = _resolve_path(
        project_root,
        acceptance_authorization_instruction_packet_path
        if acceptance_authorization_instruction_packet_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH,
    )
    operator_handoff_resolved = _resolve_path(
        project_root,
        acceptance_authorization_operator_handoff_bundle_path
        if acceptance_authorization_operator_handoff_bundle_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH,
    )

    instruction_packet_report, instruction_packet_error = _load_json_mapping(
        instruction_packet_resolved
    )
    operator_handoff_report, operator_handoff_error = _load_json_mapping(
        operator_handoff_resolved
    )

    instruction_packet_meta = (
        _mapping(instruction_packet_report.get("metadata"))
        if instruction_packet_report is not None
        else {}
    )
    operator_handoff_meta = (
        _mapping(operator_handoff_report.get("metadata"))
        if operator_handoff_report is not None
        else {}
    )

    instruction_packet_status = (
        _mapping(instruction_packet_report.get("status"))
        if instruction_packet_report is not None
        else {}
    )
    operator_handoff_status = (
        _mapping(operator_handoff_report.get("status"))
        if operator_handoff_report is not None
        else {}
    )

    instruction_packet = (
        _mapping(
            instruction_packet_report.get("acceptance_authorization_instruction_packet")
        )
        if instruction_packet_report is not None
        else {}
    )
    operator_handoff_bundle = (
        _mapping(
            operator_handoff_report.get(
                "acceptance_authorization_operator_handoff_bundle"
            )
        )
        if operator_handoff_report is not None
        else {}
    )

    instruction_packet_present = bool(
        instruction_packet_report is not None
        and instruction_packet_error is None
        and instruction_packet_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE
    )
    operator_handoff_present = bool(
        operator_handoff_report is not None
        and operator_handoff_error is None
        and operator_handoff_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE
    )

    instruction_packet_ready = bool(
        instruction_packet_status.get("acceptance_authorization_instruction_packet_ready")
    )
    operator_handoff_ready = bool(
        operator_handoff_status.get(
            "acceptance_authorization_operator_handoff_bundle_ready"
        )
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            _mapping(instruction_packet_report.get("candidate")).get("key")
            if instruction_packet_report is not None
            else None,
            _mapping(operator_handoff_report.get("candidate")).get("key")
            if operator_handoff_report is not None
            else None,
        ]
    )
    anchor_idx_text, anchor_idx_locked = _locked_value(
        [
            _mapping(instruction_packet_report.get("candidate")).get("anchor_idx")
            if instruction_packet_report is not None
            else None,
            _mapping(operator_handoff_report.get("candidate")).get("anchor_idx")
            if operator_handoff_report is not None
            else None,
        ],
        normalize=lambda value: str(value).strip(),
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            _mapping(instruction_packet_report.get("candidate")).get(
                "formulation_profile"
            )
            if instruction_packet_report is not None
            else None,
            _mapping(operator_handoff_report.get("candidate")).get(
                "formulation_profile"
            )
            if operator_handoff_report is not None
            else None,
        ]
    )

    candidate: Dict[str, Any] = {
        "key": candidate_key,
        "anchor_idx": _maybe_int(anchor_idx_text),
        "formulation_profile": formulation_profile,
    }

    packet_target_source = _mapping(instruction_packet.get("packet_target"))
    operator_target_source = _mapping(operator_handoff_bundle.get("operator_target"))
    packet_target = {
        "role": str(
            packet_target_source.get("role")
            or operator_target_source.get("role")
            or "future_manual_acceptance_authorization_review_operator"
        ),
        "scope": str(
            packet_target_source.get("scope")
            or operator_target_source.get("scope")
            or _operator_scope(candidate)
        ),
        "review_phase": str(
            packet_target_source.get("review_phase")
            or operator_target_source.get("review_phase")
            or "manual_acceptance_authorization_review"
        ),
        "detail": str(
            packet_target_source.get("detail")
            or operator_target_source.get("detail")
            or (
                "Bounded, review-only cover note for the future manual "
                "acceptance-authorization review path on anchor119. This cover "
                "note does not authorize execution, does not enable runtime, "
                "does not execute acceptance, and does not imply that any actual "
                "human authorization review has already happened."
            )
        ),
    }

    instruction_packet_locked_target = _mapping(
        instruction_packet.get("locked_execution_target")
    )
    operator_handoff_locked_target = _mapping(
        operator_handoff_bundle.get("locked_execution_target")
    )

    production_profile_id, production_profile_id_locked = _locked_value(
        [
            instruction_packet_locked_target.get("production_profile_id"),
            operator_handoff_locked_target.get("production_profile_id"),
        ]
    )
    default_production_runner, default_production_runner_value_locked = _locked_value(
        [
            instruction_packet_locked_target.get("default_production_runner"),
            operator_handoff_locked_target.get("default_production_runner"),
        ],
        normalize=_normalize_path_text,
    )
    exact_future_acceptance_command, exact_future_acceptance_command_value_locked = (
        _locked_value(
            [
                instruction_packet_locked_target.get("exact_future_acceptance_command"),
                operator_handoff_locked_target.get("exact_future_acceptance_command"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_value_locked = (
        _locked_value(
            [
                instruction_packet_locked_target.get(
                    "exact_future_acceptance_result_path"
                ),
                operator_handoff_locked_target.get(
                    "exact_future_acceptance_result_path"
                ),
            ],
            normalize=_normalize_path_text,
        )
    )
    command_output_path = _extract_suite_output_path(exact_future_acceptance_command)
    command_matches_result_path = bool(
        exact_future_acceptance_result_path
        and command_output_path
        and _normalize_path_text(exact_future_acceptance_result_path)
        == _normalize_path_text(command_output_path)
    )

    locked_execution_target = {
        "production_profile_id": production_profile_id,
        "production_profile_locked": bool(
            production_profile_id_locked
            and bool(instruction_packet_locked_target.get("production_profile_locked"))
            and bool(operator_handoff_locked_target.get("production_profile_locked"))
        ),
        "default_production_runner": default_production_runner,
        "default_production_runner_locked": bool(
            default_production_runner_value_locked
            and bool(
                instruction_packet_locked_target.get("default_production_runner_locked")
            )
            and bool(
                operator_handoff_locked_target.get("default_production_runner_locked")
            )
        ),
        "exact_future_acceptance_command": exact_future_acceptance_command,
        "exact_future_acceptance_command_locked": bool(
            exact_future_acceptance_command_value_locked
            and bool(
                instruction_packet_locked_target.get(
                    "exact_future_acceptance_command_locked"
                )
            )
            and bool(
                operator_handoff_locked_target.get(
                    "exact_future_acceptance_command_locked"
                )
            )
        ),
        "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        "exact_future_acceptance_result_path_locked": bool(
            exact_future_acceptance_result_path_value_locked
            and bool(
                instruction_packet_locked_target.get(
                    "exact_future_acceptance_result_path_locked"
                )
            )
            and bool(
                operator_handoff_locked_target.get(
                    "exact_future_acceptance_result_path_locked"
                )
            )
        ),
        "command_matches_result_path": command_matches_result_path,
        "authoritative_from_artifact_ids": [
            "acceptance_authorization_operator_handoff_bundle",
            "acceptance_authorization_instruction_packet",
        ],
    }

    still_blocked_gate_ids, still_blocked_gate_ids_locked = _locked_string_lists(
        instruction_packet_report.get("still_blocked_gate_ids")
        if instruction_packet_report is not None
        else None,
        instruction_packet_status.get("still_blocked_gate_ids"),
        operator_handoff_report.get("still_blocked_gate_ids")
        if operator_handoff_report is not None
        else None,
        operator_handoff_status.get("still_blocked_gate_ids"),
    )
    reported_blocked_gate_ids = (
        list(still_blocked_gate_ids)
        if still_blocked_gate_ids_locked
        else _ordered_union(
            instruction_packet_report.get("still_blocked_gate_ids")
            if instruction_packet_report is not None
            else None,
            instruction_packet_status.get("still_blocked_gate_ids"),
            operator_handoff_report.get("still_blocked_gate_ids")
            if operator_handoff_report is not None
            else None,
            operator_handoff_status.get("still_blocked_gate_ids"),
        )
    )

    future_manual_prerequisites_met, future_manual_prerequisites_locked = _locked_bool(
        instruction_packet_status.get(
            "future_manual_acceptance_authorization_review_prerequisites_met"
        ),
        operator_handoff_status.get("future_manual_authorization_review_prerequisites_met"),
    )
    acceptance_execution_authorized, acceptance_execution_authorized_locked = (
        _locked_bool(
            instruction_packet_status.get("acceptance_execution_authorized"),
            operator_handoff_status.get("acceptance_execution_authorized"),
        )
    )
    runtime_enablement_allowed, runtime_enablement_allowed_locked = _locked_bool(
        instruction_packet_status.get("runtime_enablement_allowed"),
        operator_handoff_status.get("runtime_enablement_allowed"),
    )
    acceptance_executed, acceptance_executed_locked = _locked_bool(
        instruction_packet_status.get("acceptance_executed"),
        operator_handoff_status.get("acceptance_executed"),
    )
    actual_human_authorization_review_happened, actual_human_review_locked = (
        _locked_bool(
            instruction_packet_status.get("actual_human_authorization_review_happened"),
            operator_handoff_status.get("actual_human_authorization_review_happened"),
        )
    )

    no_solve = bool(
        instruction_packet.get("no_solve") or instruction_packet_meta.get("no_solve")
    )
    solver_invoked, solver_invoked_locked = _locked_bool(
        instruction_packet.get("solver_invoked"),
        operator_handoff_bundle.get("solver_invoked"),
        instruction_packet_meta.get("solver_invoked"),
        operator_handoff_meta.get("solver_invoked"),
    )
    proof_source, proof_source_locked = _locked_bool(
        instruction_packet.get("proof_source"),
        operator_handoff_bundle.get("proof_source"),
        instruction_packet_meta.get("proof_source"),
        operator_handoff_meta.get("proof_source"),
    )
    candidate_elimination_claim, candidate_elimination_claim_locked = _locked_bool(
        instruction_packet.get("candidate_elimination_claim"),
        operator_handoff_bundle.get("candidate_elimination_claim"),
        instruction_packet_meta.get("candidate_elimination_claim"),
        operator_handoff_meta.get("candidate_elimination_claim"),
    )

    preserved_state_assertions = _mapping(
        instruction_packet.get("preserved_state_assertions")
    )
    preserved_false_states = {
        "future_manual_acceptance_authorization_review_prerequisites_met": (
            _preserved_false_state(
                future_manual_prerequisites_met,
                future_manual_prerequisites_locked,
                str(
                    _mapping(
                        preserved_state_assertions.get(
                            "future_manual_acceptance_authorization_review_prerequisites_met"
                        )
                    ).get("detail")
                    or (
                        "Blocked prerequisite gates still prevent any future manual "
                        "acceptance-authorization decision."
                    )
                ),
            )
        ),
        "acceptance_execution_authorized": _preserved_false_state(
            acceptance_execution_authorized,
            acceptance_execution_authorized_locked,
            str(
                _mapping(
                    preserved_state_assertions.get("acceptance_execution_authorized")
                ).get("detail")
                or "Execution authorization must remain false."
            ),
        ),
        "runtime_enablement_allowed": _preserved_false_state(
            runtime_enablement_allowed,
            runtime_enablement_allowed_locked,
            str(
                _mapping(
                    preserved_state_assertions.get("runtime_enablement_allowed")
                ).get("detail")
                or "Runtime enablement must remain false."
            ),
        ),
        "acceptance_executed": _preserved_false_state(
            acceptance_executed,
            acceptance_executed_locked,
            str(
                _mapping(preserved_state_assertions.get("acceptance_executed")).get(
                    "detail"
                )
                or "Acceptance execution must remain false."
            ),
        ),
        "actual_human_authorization_review_happened": _preserved_false_state(
            actual_human_authorization_review_happened,
            actual_human_review_locked,
            str(
                _mapping(
                    preserved_state_assertions.get(
                        "actual_human_authorization_review_happened"
                    )
                ).get("detail")
                or (
                    "No actual human acceptance-authorization review has happened yet."
                )
            ),
        ),
    }
    preserved_false_states_locked = all(
        _mapping(entry).get("locked_false")
        for entry in preserved_false_states.values()
        if isinstance(entry, Mapping)
    )

    review_only_contract_retained = bool(
        _instruction_packet_contract_ok(instruction_packet_meta, instruction_packet)
        and _operator_handoff_contract_ok(operator_handoff_meta, operator_handoff_bundle)
        and no_solve
        and bool(solver_invoked_locked and solver_invoked is False)
        and bool(proof_source_locked and proof_source is False)
        and bool(
            candidate_elimination_claim_locked
            and candidate_elimination_claim is False
        )
    )

    anchor119_candidate_locked = bool(
        candidate_key_locked
        and formulation_profile_locked
        and anchor_idx_locked
        and str(candidate.get("anchor_idx")) == "119"
    )
    locked_execution_target_authoritative = bool(
        locked_execution_target.get("production_profile_locked")
        and locked_execution_target.get("default_production_runner_locked")
        and locked_execution_target.get("exact_future_acceptance_command_locked")
        and locked_execution_target.get("exact_future_acceptance_result_path_locked")
        and locked_execution_target.get("command_matches_result_path")
        and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )

    current_blockers = _build_current_blockers(
        operator_handoff_bundle,
        reported_blocked_gate_ids,
    )

    read_first = [
        {
            "order": 1,
            "artifact_id": "acceptance_authorization_operator_handoff_bundle",
            "artifact_path": _display_path(project_root, operator_handoff_resolved),
            "why_read_first": (
                "Primary authority for the locked prod_4x4_normal target, exact "
                "future acceptance command, exact future result path, and the "
                "currently blocked prerequisite gate ids."
            ),
        },
        {
            "order": 2,
            "artifact_id": "acceptance_authorization_instruction_packet",
            "artifact_path": _display_path(project_root, instruction_packet_resolved),
            "why_read_first": (
                "Condensed source packet for the review-only/spec-only/default-off "
                "contract, preserved false states, and forbidden non-authorization "
                "semantics."
            ),
        },
    ]

    forbidden_claims = _ordered_union(
        instruction_packet.get("forbidden_claims_or_actions"),
        LOCAL_FORBIDDEN_CLAIMS,
    )

    acceptance_authorization_cover_note_ready = bool(
        instruction_packet_present
        and operator_handoff_present
        and instruction_packet_ready
        and operator_handoff_ready
        and review_only_contract_retained
        and anchor119_candidate_locked
        and locked_execution_target_authoritative
        and still_blocked_gate_ids_locked
        and preserved_false_states_locked
    )

    if not acceptance_authorization_cover_note_ready:
        recommended_next_step = "repair_acceptance_authorization_cover_note_inputs"
        handoff_summary = (
            "Cover note is not ready because the upstream instruction packet or "
            "operator handoff bundle is missing, not ready, or no longer retains "
            "the locked review-only/default-off contract."
        )
    elif reported_blocked_gate_ids:
        recommended_next_step = (
            "keep_acceptance_authorization_cover_note_review_only_and_wait_for_"
            "blocked_prerequisites"
        )
        handoff_summary = (
            "Cover note is ready as a bounded review-only/spec-only/default-off "
            "summary for the future manual acceptance-authorization review path on "
            "anchor119. The locked prod_4x4_normal target, exact future acceptance "
            "command, and exact future result path remain authoritative. Any future "
            "authorization path is still blocked by: "
            + ", ".join(reported_blocked_gate_ids)
            + ". Keep acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, acceptance_executed=false, and "
            "actual_human_authorization_review_happened=false."
        )
    else:
        recommended_next_step = (
            "keep_acceptance_authorization_cover_note_review_only_without_"
            "authorizing_execution"
        )
        handoff_summary = (
            "Cover note is ready and no currently reported blocked prerequisite "
            "gate ids remain, but this artifact still stays review-only/spec-only/"
            "default-off and must not be treated as authorization, runtime "
            "enablement, or acceptance execution."
        )

    checks = [
        _check(
            "acceptance_authorization_instruction_packet_present",
            "pass" if instruction_packet_present else "fail",
            _presence_detail(
                project_root,
                instruction_packet_resolved,
                instruction_packet_present,
                instruction_packet_error,
                ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE,
            ),
        ),
        _check(
            "acceptance_authorization_instruction_packet_ready",
            "pass" if instruction_packet_ready else "fail",
            "status.acceptance_authorization_instruction_packet_ready must be true.",
        ),
        _check(
            "acceptance_authorization_operator_handoff_bundle_present",
            "pass" if operator_handoff_present else "fail",
            _presence_detail(
                project_root,
                operator_handoff_resolved,
                operator_handoff_present,
                operator_handoff_error,
                ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE,
            ),
        ),
        _check(
            "acceptance_authorization_operator_handoff_bundle_ready",
            "pass" if operator_handoff_ready else "fail",
            (
                "status.acceptance_authorization_operator_handoff_bundle_ready "
                "must be true."
            ),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            (
                "review_only/spec_only/default_off/no_solve must remain true, and "
                "solver_invoked/proof_source/candidate_elimination_claim must "
                "remain false."
            ),
        ),
        _check(
            "anchor119_candidate_locked",
            "pass" if anchor119_candidate_locked else "fail",
            (
                "Candidate key, anchor_idx=119, and formulation_profile must stay "
                "consistent across the upstream packet and handoff bundle."
            ),
        ),
        _check(
            "locked_execution_target_authoritative",
            "pass" if locked_execution_target_authoritative else "fail",
            (
                "The locked prod_4x4_normal target, exact future acceptance "
                "command, and exact future result path must remain unchanged and "
                "cross-source consistent."
            ),
        ),
        _check(
            "still_blocked_gate_ids_locked",
            "pass" if still_blocked_gate_ids_locked else "fail",
            (
                "still_blocked_gate_ids must match across the upstream packet and "
                "handoff bundle."
            ),
        ),
        _check(
            "preserved_false_states_locked",
            "pass" if preserved_false_states_locked else "fail",
            (
                "future_manual_acceptance_authorization_review_prerequisites_met, "
                "acceptance_execution_authorized, runtime_enablement_allowed, "
                "acceptance_executed, and "
                "actual_human_authorization_review_happened must all remain false."
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_cover_note_review_only_"
                "not_execution_authorization"
            ),
            "spec_only": True,
            "review_only": True,
            "default_off": True,
            "no_solve": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
        "paths": {
            "project_root": str(project_root),
            "acceptance_authorization_instruction_packet": _display_path(
                project_root, instruction_packet_resolved
            ),
            "acceptance_authorization_operator_handoff_bundle": _display_path(
                project_root, operator_handoff_resolved
            ),
        },
        "candidate": candidate,
        "status": {
            "acceptance_authorization_cover_note_ready": bool(
                acceptance_authorization_cover_note_ready
            ),
            "future_manual_acceptance_authorization_review_prerequisites_met": bool(
                future_manual_prerequisites_met
            ),
            "acceptance_execution_authorized": bool(acceptance_execution_authorized),
            "runtime_enablement_allowed": bool(runtime_enablement_allowed),
            "acceptance_executed": bool(acceptance_executed),
            "actual_human_authorization_review_happened": bool(
                actual_human_authorization_review_happened
            ),
            "still_blocked_gate_ids": list(reported_blocked_gate_ids),
            "recommended_next_step": recommended_next_step,
            "handoff_summary": handoff_summary,
        },
        "acceptance_authorization_cover_note": {
            "packet_target": packet_target,
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "no_solve": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "read_first": read_first,
            "locked_execution_target": locked_execution_target,
            "current_blockers": current_blockers,
            "preserved_false_states": preserved_false_states,
            "forbidden_claims": forbidden_claims,
            "handoff_summary": handoff_summary,
        },
        "still_blocked_gate_ids": list(reported_blocked_gate_ids),
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    cover_note = _mapping(report.get("acceptance_authorization_cover_note"))
    packet_target = _mapping(cover_note.get("packet_target"))
    locked_execution_target = _mapping(cover_note.get("locked_execution_target"))
    current_blockers = _mapping_list(cover_note.get("current_blockers"))
    preserved_false_states = _mapping(cover_note.get("preserved_false_states"))

    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Cover Note",
        "",
        (
            "- Acceptance authorization cover note ready: "
            f"`{status.get('acceptance_authorization_cover_note_ready')}`"
        ),
        (
            "- Future manual acceptance authorization review prerequisites met: "
            f"`{status.get('future_manual_acceptance_authorization_review_prerequisites_met')}`"
        ),
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        (
            "- Actual human authorization review happened: "
            f"`{status.get('actual_human_authorization_review_happened')}`"
        ),
        (
            "- Still blocked gate ids: "
            f"`{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`"
        ),
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        "",
        "## Packet Target",
        "",
        f"- Role: `{packet_target.get('role')}`",
        f"- Scope: `{packet_target.get('scope')}`",
        f"- Review phase: `{packet_target.get('review_phase')}`",
        f"- Detail: {packet_target.get('detail')}",
        "",
        "## Read First",
        "",
    ]
    for entry in _mapping_list(cover_note.get("read_first")):
        lines.append(
            f"{entry.get('order')}. `{entry.get('artifact_id')}`: "
            f"`{entry.get('artifact_path')}` - {entry.get('why_read_first')}"
        )

    lines.extend(
        [
            "",
            "## Locked Execution Target",
            "",
            f"- Production profile id: `{locked_execution_target.get('production_profile_id')}`",
            f"- Default production runner: `{locked_execution_target.get('default_production_runner')}`",
            f"- Exact future acceptance command: `{locked_execution_target.get('exact_future_acceptance_command')}`",
            f"- Exact future acceptance result path: `{locked_execution_target.get('exact_future_acceptance_result_path')}`",
            f"- Command matches result path: `{locked_execution_target.get('command_matches_result_path')}`",
            "",
            "## Current Blockers",
            "",
        ]
    )
    if current_blockers:
        for entry in current_blockers:
            lines.append(
                f"- `{entry.get('gate_id')}`: {entry.get('detail')} "
                f"(required_state=`{entry.get('required_state')}`, "
                f"current_value=`{entry.get('current_value')}`)"
            )
    else:
        lines.append("- `(none)`")

    lines.extend(
        [
            "",
            "## Preserved False States",
            "",
            "| State | Current value | Locked false | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for state_id, entry in preserved_false_states.items():
        state_entry = _mapping(entry)
        lines.append(
            f"| {_markdown_cell(state_id)} | "
            f"{_markdown_cell(state_entry.get('current_value'))} | "
            f"{_markdown_cell(state_entry.get('locked_false'))} | "
            f"{_markdown_cell(state_entry.get('detail'))} |"
        )

    lines.extend(
        [
            "",
            "## Forbidden Claims",
            "",
        ]
    )
    for entry in _string_list(cover_note.get("forbidden_claims")):
        lines.append(f"- {entry}")

    lines.extend(
        [
            "",
            "## Handoff Summary",
            "",
            str(cover_note.get("handoff_summary")),
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    cover_note = _mapping(report.get("acceptance_authorization_cover_note"))
    locked_execution_target = _mapping(cover_note.get("locked_execution_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization cover note",
            "acceptance_authorization_cover_note_ready="
            + str(status.get("acceptance_authorization_cover_note_ready")),
            "future_manual_acceptance_authorization_review_prerequisites_met="
            + str(
                status.get(
                    "future_manual_acceptance_authorization_review_prerequisites_met"
                )
            ),
            "acceptance_execution_authorized="
            + str(status.get("acceptance_execution_authorized")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            "acceptance_executed=" + str(status.get("acceptance_executed")),
            "actual_human_authorization_review_happened="
            + str(status.get("actual_human_authorization_review_happened")),
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            "production_profile_id="
            + str(locked_execution_target.get("production_profile_id")),
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path")),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
            "handoff_summary=" + str(status.get("handoff_summary")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_acceptance_authorization_cover_note",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _instruction_packet_contract_ok(
    metadata: Mapping[str, Any], packet: Mapping[str, Any]
) -> bool:
    return bool(
        metadata.get("spec_only")
        and metadata.get("review_only")
        and metadata.get("default_off")
        and metadata.get("no_solve")
        and metadata.get("runtime_precheck_enabled") is False
        and metadata.get("runtime_semantics_changed") is False
        and metadata.get("proof_source") is False
        and metadata.get("candidate_elimination_claim") is False
        and metadata.get("solver_invoked") is False
        and metadata.get("acceptance_executed") is False
        and packet.get("spec_only")
        and packet.get("review_only")
        and packet.get("default_off")
        and packet.get("no_solve")
        and packet.get("solver_invoked") is False
        and packet.get("proof_source") is False
        and packet.get("candidate_elimination_claim") is False
        and packet.get("does_not_execute_acceptance")
        and packet.get("does_not_imply_enablement")
        and packet.get("does_not_authorize_execution")
    )


def _operator_handoff_contract_ok(
    metadata: Mapping[str, Any], handoff: Mapping[str, Any]
) -> bool:
    return bool(
        metadata.get("spec_only")
        and metadata.get("review_only")
        and metadata.get("default_off")
        and metadata.get("runtime_precheck_enabled") is False
        and metadata.get("runtime_semantics_changed") is False
        and metadata.get("proof_source") is False
        and metadata.get("candidate_elimination_claim") is False
        and metadata.get("solver_invoked") is False
        and metadata.get("acceptance_executed") is False
        and handoff.get("spec_only")
        and handoff.get("review_only")
        and handoff.get("default_off")
        and handoff.get("solver_invoked") is False
        and handoff.get("proof_source") is False
        and handoff.get("candidate_elimination_claim") is False
        and handoff.get("does_not_execute_acceptance")
        and handoff.get("does_not_imply_enablement")
        and handoff.get("does_not_authorize_execution")
    )


def _build_current_blockers(
    handoff_bundle: Mapping[str, Any], still_blocked_gate_ids: list[str]
) -> list[Dict[str, Any]]:
    blockers_by_id: Dict[str, Dict[str, Any]] = {}
    for entry in _mapping_list(handoff_bundle.get("blocked_prerequisites")):
        gate_id = str(entry.get("gate_id")).strip()
        if gate_id:
            blockers_by_id[gate_id] = {
                "gate_id": gate_id,
                "required_state": entry.get("required_state"),
                "current_value": entry.get("current_value"),
                "detail": str(entry.get("detail") or "").strip(),
            }

    blockers: list[Dict[str, Any]] = []
    for gate_id in still_blocked_gate_ids:
        blocker = blockers_by_id.get(gate_id)
        if blocker is not None:
            blockers.append(blocker)
            continue
        blockers.append(
            {
                "gate_id": gate_id,
                "required_state": True,
                "current_value": False,
                "detail": (
                    "Blocked prerequisite gate remains unresolved and must stay "
                    "carried forward into any future manual review."
                ),
            }
        )
    return blockers


def _preserved_false_state(
    current_value: bool, value_locked: bool, detail: str
) -> Dict[str, Any]:
    return {
        "expected_value": False,
        "current_value": bool(current_value),
        "locked_false": bool(value_locked and current_value is False),
        "detail": detail,
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _presence_detail(
    project_root: Path,
    path: Path,
    present: bool,
    error: Optional[str],
    expected_source: str,
) -> str:
    displayed_path = _display_path(project_root, path)
    if present:
        return f"{displayed_path} present with expected source {expected_source}."
    return (
        f"{displayed_path} missing or invalid for expected source "
        f"{expected_source}: {error or 'missing'}."
    )


def _locked_value(
    values: list[Any],
    normalize: Optional[Callable[[str], str]] = None,
) -> tuple[str, bool]:
    seen_raw: list[str] = []
    seen_normalized: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        seen_raw.append(text)
        seen_normalized.append(normalize(text) if normalize is not None else text)
    if not seen_raw:
        return "", False
    return seen_raw[0], all(
        entry == seen_normalized[0] for entry in seen_normalized[1:]
    )


def _locked_bool(*values: Any) -> tuple[bool, bool]:
    seen: list[bool] = []
    for value in values:
        if value is None:
            continue
        seen.append(bool(value))
    if not seen:
        return False, False
    return seen[0], all(entry == seen[0] for entry in seen[1:])


def _locked_string_lists(*values: Any) -> tuple[list[str], bool]:
    seen: list[list[str]] = []
    for value in values:
        if value is None:
            continue
        strings = _string_list(value)
        seen.append(strings)
    if not seen:
        return [], False
    return list(seen[0]), all(entry == seen[0] for entry in seen[1:])


def _ordered_union(*values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, list):
            entries = value
        elif value is None:
            entries = []
        else:
            entries = [value]
        for entry in entries:
            text = str(entry).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
    return result


def _maybe_int(value: str) -> Any:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _operator_scope(candidate: Mapping[str, Any]) -> str:
    return (
        f"candidate={candidate.get('key')}, anchor_idx={candidate.get('anchor_idx')}, "
        f"formulation_profile={candidate.get('formulation_profile')}"
    )


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing:{path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{path}:{exc.msg}"
    if not isinstance(payload, dict):
        return None, f"invalid_payload_type:{path}"
    return payload, None


def _resolve_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _extract_suite_output_path(command: str) -> Optional[str]:
    if not str(command).strip():
        return None
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return None
    for index, part in enumerate(parts):
        if part == "--suite-output" and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith("--suite-output="):
            return part.split("=", 1)[1]
    return None


def _normalize_command_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


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
    return str(value).replace("|", "\\|").replace("\n", "<br>")

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

INGEST_REVIEW_COVER_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_v1"
)
INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
)
ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_cover_note_v1"
)
ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_instruction_packet_v1"
)
FINAL_HUMAN_HANDOFF_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_v1"
)

DEFAULT_INGEST_REVIEW_COVER_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
    "ingest_review_cover_note_20260424/"
    "anchor119_row_domain_ingest_review_cover_note.json"
)
DEFAULT_INGEST_REVIEW_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
    "ingest_review_instruction_packet_20260424/"
    "anchor119_row_domain_ingest_review_instruction_packet.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_COVER_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_cover_note_20260424/"
    "anchor119_row_domain_acceptance_authorization_cover_note.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_instruction_packet_20260424/"
    "anchor119_row_domain_acceptance_authorization_instruction_packet.json"
)

LOCAL_DO_NOT_CLAIM = [
    "Do not claim any actual human review has already happened.",
    "Do not claim solver invocation, proof promotion, or candidate elimination.",
    "Do not update repo-side review state from this package.",
    "Do not imply reviewed_runtime_patch_exists=true.",
    "Do not imply runtime_enablement_allowed=true.",
    "Do not imply reviewed_runtime_patch_exists or acceptance blockers were cleared.",
    "Do not imply reviewed_runtime_patch_exists=true for ingest review or acceptance authorization.",
    "Do not authorize execution from this package.",
    "Do not imply reviewed_runtime_patch_exists=true, reviewed_runtime_patch_exists satisfaction, or runtime enablement approval.",
]

LOCAL_DOES_NOT_DO = [
    "It does not run solver-backed search or any runtime or acceptance command.",
    "It does not update repo-side review state or review-status artifacts.",
    "It does not create, ingest, or validate a real human review record.",
    "It does not clear blocked gates or flip preserved false states to true.",
    "It does not authorize execution, runtime enablement, or acceptance execution.",
]

INGEST_FALSE_STATE_DETAILS = {
    "repo_side_review_state_updated": (
        "Repo-side review state must remain unchanged in this review-only branch."
    ),
    "reviewed_runtime_patch_exists": (
        "The reviewed runtime patch record still does not exist in repo-side state."
    ),
    "runtime_enablement_allowed": (
        "Runtime enablement remains blocked and must stay false."
    ),
    "proof_source": "This branch remains non-proof and must keep proof_source=false.",
    "candidate_elimination_claim": (
        "This branch must not claim candidate elimination."
    ),
    "solver_invoked": "This branch remains no-solve with solver_invoked=false.",
    "actual_human_review_has_happened": (
        "No actual human ingest review has happened yet."
    ),
    "execution_authorized": "Execution authorization must remain false.",
}

ACCEPTANCE_FALSE_STATE_DETAILS = {
    "reviewed_runtime_patch_exists": (
        "A reviewed runtime patch signoff record is still missing, so this gate stays false."
    ),
    "future_manual_acceptance_authorization_review_prerequisites_met": (
        "Blocked prerequisites still prevent any future authorization decision."
    ),
    "acceptance_execution_authorized": (
        "Acceptance execution is not authorized in this review-only branch."
    ),
    "runtime_enablement_allowed": (
        "Runtime enablement remains forbidden and must stay false."
    ),
    "acceptance_executed": "Acceptance has not been executed.",
    "actual_human_authorization_review_happened": (
        "No actual human acceptance-authorization review has happened yet."
    ),
    "proof_source": "This branch remains non-proof and must keep proof_source=false.",
    "candidate_elimination_claim": (
        "This branch must not claim candidate elimination."
    ),
    "solver_invoked": "This branch remains no-solve with solver_invoked=false.",
}


def build_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note(
    project_root: Path,
    *,
    ingest_review_cover_note_path: Optional[Path] = None,
    ingest_review_instruction_packet_path: Optional[Path] = None,
    acceptance_authorization_cover_note_path: Optional[Path] = None,
    acceptance_authorization_instruction_packet_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()

    ingest_cover_resolved = _resolve_path(
        project_root,
        ingest_review_cover_note_path
        if ingest_review_cover_note_path is not None
        else DEFAULT_INGEST_REVIEW_COVER_NOTE_PATH,
    )
    ingest_packet_resolved = _resolve_path(
        project_root,
        ingest_review_instruction_packet_path
        if ingest_review_instruction_packet_path is not None
        else DEFAULT_INGEST_REVIEW_INSTRUCTION_PACKET_PATH,
    )
    acceptance_cover_resolved = _resolve_path(
        project_root,
        acceptance_authorization_cover_note_path
        if acceptance_authorization_cover_note_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_COVER_NOTE_PATH,
    )
    acceptance_packet_resolved = _resolve_path(
        project_root,
        acceptance_authorization_instruction_packet_path
        if acceptance_authorization_instruction_packet_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH,
    )

    ingest_cover_report, ingest_cover_error = _load_json_mapping(ingest_cover_resolved)
    ingest_packet_report, ingest_packet_error = _load_json_mapping(
        ingest_packet_resolved
    )
    acceptance_cover_report, acceptance_cover_error = _load_json_mapping(
        acceptance_cover_resolved
    )
    acceptance_packet_report, acceptance_packet_error = _load_json_mapping(
        acceptance_packet_resolved
    )

    ingest_cover_meta = (
        _mapping(ingest_cover_report.get("metadata"))
        if ingest_cover_report is not None
        else {}
    )
    ingest_packet_meta = (
        _mapping(ingest_packet_report.get("metadata"))
        if ingest_packet_report is not None
        else {}
    )
    acceptance_cover_meta = (
        _mapping(acceptance_cover_report.get("metadata"))
        if acceptance_cover_report is not None
        else {}
    )
    acceptance_packet_meta = (
        _mapping(acceptance_packet_report.get("metadata"))
        if acceptance_packet_report is not None
        else {}
    )

    ingest_cover_present = bool(
        ingest_cover_report is not None
        and ingest_cover_error is None
        and ingest_cover_meta.get("source") == INGEST_REVIEW_COVER_NOTE_SOURCE
    )
    ingest_packet_present = bool(
        ingest_packet_report is not None
        and ingest_packet_error is None
        and ingest_packet_meta.get("source")
        == INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE
    )
    acceptance_cover_present = bool(
        acceptance_cover_report is not None
        and acceptance_cover_error is None
        and acceptance_cover_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE
    )
    acceptance_packet_present = bool(
        acceptance_packet_report is not None
        and acceptance_packet_error is None
        and acceptance_packet_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            _mapping(report.get("candidate")).get("key")
            for report in [
                ingest_cover_report,
                ingest_packet_report,
                acceptance_cover_report,
                acceptance_packet_report,
            ]
            if report is not None
        ]
    )
    anchor_idx_text, anchor_idx_locked = _locked_value(
        [
            _mapping(report.get("candidate")).get("anchor_idx")
            for report in [
                ingest_cover_report,
                ingest_packet_report,
                acceptance_cover_report,
                acceptance_packet_report,
            ]
            if report is not None
        ],
        normalize=lambda value: str(value).strip(),
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            _mapping(report.get("candidate")).get("formulation_profile")
            for report in [
                ingest_cover_report,
                ingest_packet_report,
                acceptance_cover_report,
                acceptance_packet_report,
            ]
            if report is not None
        ]
    )
    candidate_locked = bool(
        candidate_key_locked
        and anchor_idx_locked
        and formulation_profile_locked
        and anchor_idx_text == "119"
    )
    candidate = {
        "key": candidate_key,
        "anchor_idx": _maybe_int(anchor_idx_text),
        "formulation_profile": formulation_profile,
    }

    ingest_branch = _build_ingest_branch(
        project_root,
        ingest_cover_resolved,
        ingest_cover_report,
        ingest_packet_resolved,
        ingest_packet_report,
    )
    acceptance_branch = _build_acceptance_branch(
        project_root,
        acceptance_cover_resolved,
        acceptance_cover_report,
        acceptance_packet_resolved,
        acceptance_packet_report,
    )
    branch_summaries = [
        ingest_branch["branch_summary"],
        acceptance_branch["branch_summary"],
    ]

    read_this_first = [
        ingest_branch["branch_summary"]["entrypoint_artifact"],
        acceptance_branch["branch_summary"]["entrypoint_artifact"],
    ]
    branch_read_lists_present = bool(
        ingest_branch["read_list_present"] and acceptance_branch["read_list_present"]
    )

    review_only_contract_retained = bool(
        _contract_ok(ingest_cover_meta, require_no_solve=False)
        and _contract_ok(ingest_packet_meta, require_no_solve=False)
        and _contract_ok(acceptance_cover_meta, require_no_solve=True)
        and _contract_ok(acceptance_packet_meta, require_no_solve=True)
    )
    preserved_false_states_retained = bool(
        ingest_branch["required_false_states_ok"]
        and acceptance_branch["required_false_states_ok"]
    )

    still_blocked = _aggregate_blockers(branch_summaries)
    still_blocked_gate_ids = [str(entry["gate_id"]) for entry in still_blocked]
    still_false = _aggregate_false_states(branch_summaries)
    do_not_claim = _ordered_union(
        LOCAL_DO_NOT_CLAIM,
        ingest_branch["forbidden_claims"],
        acceptance_branch["forbidden_claims"],
    )

    final_human_handoff_note_ready = bool(
        ingest_cover_present
        and ingest_packet_present
        and acceptance_cover_present
        and acceptance_packet_present
        and ingest_branch["branch_ready"]
        and acceptance_branch["branch_ready"]
        and review_only_contract_retained
        and candidate_locked
        and branch_read_lists_present
        and preserved_false_states_retained
    )

    if not final_human_handoff_note_ready:
        recommended_next_step = "repair_final_human_handoff_note_inputs"
        final_handoff_summary = (
            "Final human handoff note is not ready because one or more upstream "
            "branch artifacts are missing, not ready, or no longer retain the "
            "locked review-only/default-off contract."
        )
    elif still_blocked_gate_ids:
        recommended_next_step = (
            "keep_final_human_handoff_note_review_only_and_wait_for_blockers"
        )
        final_handoff_summary = (
            "Anchor119 manual-review package is summarized into two review-only "
            "branches. Start with the ingest-review cover note for repo-side "
            "review-state work, or the acceptance-authorization cover note for "
            "any future locked prod_4x4_normal authorization path. Still blocked "
            "gate ids remain: "
            + ", ".join(still_blocked_gate_ids)
            + ". Keep reviewed_runtime_patch_exists=false, "
            "runtime_enablement_allowed=false, acceptance_execution_authorized=false, "
            "acceptance_executed=false, proof_source=false, "
            "candidate_elimination_claim=false, solver_invoked=false, and do not "
            "treat this package as completed human review or execution authorization."
        )
    else:
        recommended_next_step = (
            "keep_final_human_handoff_note_review_only_without_authorizing_execution"
        )
        final_handoff_summary = (
            "Anchor119 manual-review package is summarized into two review-only "
            "branches with no currently reported blocked gate ids, but the package "
            "still stays default-off, no-solve, non-proof, and non-authorizing."
        )

    checks = [
        _check(
            "ingest_review_cover_note_present",
            "pass" if ingest_cover_present else "fail",
            _presence_detail(
                project_root,
                ingest_cover_resolved,
                ingest_cover_present,
                ingest_cover_error,
                INGEST_REVIEW_COVER_NOTE_SOURCE,
            ),
        ),
        _check(
            "ingest_review_instruction_packet_present",
            "pass" if ingest_packet_present else "fail",
            _presence_detail(
                project_root,
                ingest_packet_resolved,
                ingest_packet_present,
                ingest_packet_error,
                INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE,
            ),
        ),
        _check(
            "acceptance_authorization_cover_note_present",
            "pass" if acceptance_cover_present else "fail",
            _presence_detail(
                project_root,
                acceptance_cover_resolved,
                acceptance_cover_present,
                acceptance_cover_error,
                ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE,
            ),
        ),
        _check(
            "acceptance_authorization_instruction_packet_present",
            "pass" if acceptance_packet_present else "fail",
            _presence_detail(
                project_root,
                acceptance_packet_resolved,
                acceptance_packet_present,
                acceptance_packet_error,
                ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE,
            ),
        ),
        _check(
            "ingest_review_branch_ready",
            "pass" if ingest_branch["branch_ready"] else "fail",
            "ingest review cover note and instruction packet remain ready and bounded."
            if ingest_branch["branch_ready"]
            else "ingest review branch is missing readiness, read order, or preserved false states.",
        ),
        _check(
            "acceptance_authorization_branch_ready",
            "pass" if acceptance_branch["branch_ready"] else "fail",
            "acceptance authorization cover note and instruction packet remain ready and bounded."
            if acceptance_branch["branch_ready"]
            else "acceptance authorization branch is missing readiness, read order, or preserved false states.",
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "All four upstream artifacts remain review-only/spec-only/default-off with solver_invoked=false, proof_source=false, and candidate_elimination_claim=false."
            if review_only_contract_retained
            else "At least one upstream artifact drifted away from the required review-only/default-off contract.",
        ),
        _check(
            "anchor119_candidate_locked",
            "pass" if candidate_locked else "fail",
            "Candidate key, anchor_idx=119, and formulation_profile stay locked across all four upstream artifacts."
            if candidate_locked
            else "Candidate identity drifted across the upstream artifacts.",
        ),
        _check(
            "branch_read_lists_present",
            "pass" if branch_read_lists_present else "fail",
            "Each branch still exposes an entrypoint and a concrete first-read list."
            if branch_read_lists_present
            else "At least one branch no longer exposes a concrete entrypoint plus first-read list.",
        ),
        _check(
            "preserved_false_states_retained",
            "pass" if preserved_false_states_retained else "fail",
            "Branch-critical false states remain false, including reviewed_runtime_patch_exists, runtime_enablement_allowed, proof_source, candidate_elimination_claim, and solver_invoked."
            if preserved_false_states_retained
            else "At least one branch-critical false state no longer remains false.",
        ),
    ]

    note_target = {
        "package_kind": "bounded_review_only_final_human_handoff_note",
        "target_reader": "future_human_operator_or_reviewer",
        "candidate_key": candidate["key"],
        "anchor_idx": candidate["anchor_idx"],
        "formulation_profile": candidate["formulation_profile"],
        "branch_ids": ["ingest_review", "acceptance_authorization"],
        "branch_count": 2,
    }
    what_this_package_is = (
        "One bounded, artifact-backed final human handoff note for the anchor119 "
        "manual-review package. It compresses the current ingest-review branch and "
        "acceptance-authorization branch into one quick reference, while staying "
        "review-only, spec-only, default-off, no-solve, proof_source=false, and "
        "non-authorizing."
    )

    report = {
        "metadata": {
            "source": FINAL_HUMAN_HANDOFF_NOTE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_final_human_handoff_note_review_only_spec_only_default_off_"
                "manual_package_not_executed"
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
            "ingest_review_cover_note": _display_path(project_root, ingest_cover_resolved),
            "ingest_review_instruction_packet": _display_path(
                project_root, ingest_packet_resolved
            ),
            "acceptance_authorization_cover_note": _display_path(
                project_root, acceptance_cover_resolved
            ),
            "acceptance_authorization_instruction_packet": _display_path(
                project_root, acceptance_packet_resolved
            ),
        },
        "candidate": candidate,
        "status": {
            "final_human_handoff_note_ready": bool(final_human_handoff_note_ready),
            "branches_ready": {
                "ingest_review": bool(ingest_branch["branch_ready"]),
                "acceptance_authorization": bool(
                    acceptance_branch["branch_ready"]
                ),
            },
            "still_blocked_gate_ids": list(still_blocked_gate_ids),
            "recommended_next_step": recommended_next_step,
            "final_handoff_summary": final_handoff_summary,
        },
        "final_human_handoff_note": {
            "note_target": note_target,
            "what_this_package_is": what_this_package_is,
            "read_this_first": read_this_first,
            "branch_summaries": branch_summaries,
            "still_blocked": still_blocked,
            "still_false": still_false,
            "do_not_claim": do_not_claim,
            "what_this_package_still_does_not_do": list(LOCAL_DOES_NOT_DO),
            "final_handoff_summary": final_handoff_summary,
        },
        "checks": checks,
    }
    return report


def render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    note = _mapping(report.get("final_human_handoff_note"))
    note_target = _mapping(note.get("note_target"))

    lines = [
        "# Phase 3B Anchor119 Row-Domain Final Human Handoff Note",
        "",
        (
            "- Final human handoff note ready: "
            f"`{status.get('final_human_handoff_note_ready')}`"
        ),
        (
            "- Still blocked gate ids: "
            f"`{', '.join(_string_list(status.get('still_blocked_gate_ids'))) or '(none)'}`"
        ),
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        "",
        "## Note Target",
        "",
        f"- Package kind: `{note_target.get('package_kind')}`",
        f"- Target reader: `{note_target.get('target_reader')}`",
        f"- Candidate key: `{note_target.get('candidate_key')}`",
        f"- Anchor idx: `{note_target.get('anchor_idx')}`",
        f"- Formulation profile: `{note_target.get('formulation_profile')}`",
        f"- Branch ids: `{', '.join(_string_list(note_target.get('branch_ids')))}`",
        "",
        "## What This Package Is",
        "",
        str(note.get("what_this_package_is")),
        "",
        "## Read This First",
        "",
    ]
    for entry in _mapping_list(note.get("read_this_first")):
        lines.append(
            f"- `{entry.get('branch_id')}`: `{entry.get('artifact_path')}` - "
            f"{entry.get('why')}"
        )

    lines.extend(["", "## Branch Summaries", ""])
    for branch in _mapping_list(note.get("branch_summaries")):
        lines.extend(
            [
                f"### {branch.get('branch_label')}",
                "",
                f"- Branch ready: `{branch.get('branch_ready')}`",
                f"- What this branch is for: {branch.get('what_branch_is_for')}",
            ]
        )
        entrypoint = _mapping(branch.get("entrypoint_artifact"))
        lines.append(
            f"- Entry point: `{entrypoint.get('artifact_path')}` - {entrypoint.get('why')}"
        )
        lines.append("- Read this first in the branch:")
        for entry in _mapping_list(branch.get("read_this_first")):
            lines.append(
                f"  - `{entry.get('artifact_id')}`: `{entry.get('artifact_path')}` - "
                f"{entry.get('why_read_first')}"
            )
        lines.append("- Still blocked in the branch:")
        blockers = _mapping_list(branch.get("still_blocked"))
        if blockers:
            for entry in blockers:
                lines.append(
                    f"  - `{entry.get('gate_id')}`: {entry.get('detail')} "
                    f"(current_value=`{entry.get('current_value')}`)"
                )
        else:
            lines.append("  - `(none)`")
        lines.append("- Still false in the branch:")
        false_states = _mapping_list(branch.get("still_false"))
        if false_states:
            for entry in false_states:
                lines.append(
                    f"  - `{entry.get('state_id')}`: `{entry.get('current_value')}` - "
                    f"{entry.get('detail')}"
                )
        else:
            lines.append("  - `(none)`")
        lines.append(f"- Branch summary: {branch.get('branch_summary')}")
        lines.append("")

    lines.extend(["## Still Blocked", ""])
    for entry in _mapping_list(note.get("still_blocked")):
        lines.append(
            f"- `{entry.get('gate_id')}`: branches=`{', '.join(_string_list(entry.get('branches')))}`; "
            f"current_value=`{entry.get('current_value')}`; {entry.get('detail')}"
        )

    lines.extend(["", "## Still False", ""])
    for entry in _mapping_list(note.get("still_false")):
        lines.append(
            f"- `{entry.get('state_id')}`: branches=`{', '.join(_string_list(entry.get('branches')))}`; "
            f"current_value=`{entry.get('current_value')}`; {entry.get('detail')}"
        )

    lines.extend(["", "## Do Not Claim", ""])
    for entry in _string_list(note.get("do_not_claim")):
        lines.append(f"- {entry}")

    lines.extend(["", "## What This Package Still Does Not Do", ""])
    for entry in _string_list(note.get("what_this_package_still_does_not_do")):
        lines.append(f"- {entry}")

    lines.extend(
        [
            "",
            "## Final Handoff Summary",
            "",
            str(note.get("final_handoff_summary")),
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    note = _mapping(report.get("final_human_handoff_note"))
    note_target = _mapping(note.get("note_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain final human handoff note",
            "final_human_handoff_note_ready="
            + str(status.get("final_human_handoff_note_ready")),
            "candidate_key=" + str(note_target.get("candidate_key")),
            "anchor_idx=" + str(note_target.get("anchor_idx")),
            "formulation_profile=" + str(note_target.get("formulation_profile")),
            "branch_ids=" + ",".join(_string_list(note_target.get("branch_ids"))),
            "still_blocked_gate_ids="
            + ",".join(_string_list(status.get("still_blocked_gate_ids"))),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
            "final_handoff_summary=" + str(status.get("final_handoff_summary")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_final_human_handoff_note",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_ingest_branch(
    project_root: Path,
    cover_path: Path,
    cover_report: Optional[Dict[str, Any]],
    instruction_packet_path: Path,
    instruction_packet_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    cover_status = _mapping(cover_report.get("status")) if cover_report is not None else {}
    cover_note = (
        _mapping(cover_report.get("ingest_review_cover_note"))
        if cover_report is not None
        else {}
    )
    instruction_packet = (
        _mapping(instruction_packet_report.get("ingest_review_instruction_packet"))
        if instruction_packet_report is not None
        else {}
    )
    packet_target = _mapping(cover_note.get("packet_target"))
    instruction_target = _mapping(instruction_packet.get("packet_target"))

    branch_entrypoint = {
        "branch_id": "ingest_review",
        "branch_label": "Ingest Review",
        "artifact_id": "ingest_review_cover_note",
        "artifact_path": _display_path(project_root, cover_path),
        "why": (
            "Fastest review-only entrypoint for the future manual ingest-review path."
        ),
    }
    read_this_first = _read_steps_from_entries(
        instruction_packet.get("open_these_first")
    ) or _read_steps_from_entries(cover_note.get("read_first"))
    read_list_present = bool(read_this_first)

    purpose = str(
        packet_target.get("package_summary")
        or instruction_target.get("review_step_summary")
        or cover_status.get("handoff_summary")
        or (
            "Future manual ingest-review path for repo-side reviewed-runtime-patch "
            "state handling on anchor119."
        )
    )

    still_blocked = _normalize_blockers(
        cover_note.get("current_blockers"),
        cover_report.get("still_blocked_gate_ids") if cover_report is not None else None,
        instruction_packet_report.get("still_blocked_gate_ids")
        if instruction_packet_report is not None
        else None,
    )
    false_state_entries = [
        _false_state_entry(
            "ingest_review",
            "repo_side_review_state_updated",
            _all_false(
                _mapping(cover_report.get("metadata")).get(
                    "repo_side_review_state_updated"
                )
                if cover_report is not None
                else None,
                cover_status.get("repo_side_review_state_updated"),
                _mapping(cover_note.get("preserved_false_states")).get(
                    "repo_side_review_state_updated"
                ),
                _mapping(instruction_packet_report.get("metadata")).get(
                    "repo_side_review_state_updated"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "repo_side_review_state_updated"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["repo_side_review_state_updated"],
        ),
        _false_state_entry(
            "ingest_review",
            "reviewed_runtime_patch_exists",
            _all_false(
                cover_status.get("reviewed_runtime_patch_exists"),
                _mapping(cover_note.get("preserved_false_states")).get(
                    "reviewed_runtime_patch_exists"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "reviewed_runtime_patch_exists"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["reviewed_runtime_patch_exists"],
        ),
        _false_state_entry(
            "ingest_review",
            "runtime_enablement_allowed",
            _all_false(
                cover_status.get("runtime_enablement_allowed"),
                _mapping(cover_note.get("preserved_false_states")).get(
                    "runtime_enablement_allowed"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "runtime_enablement_allowed"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["runtime_enablement_allowed"],
        ),
        _false_state_entry(
            "ingest_review",
            "proof_source",
            _all_false(
                _mapping(cover_report.get("metadata")).get("proof_source")
                if cover_report is not None
                else None,
                _mapping(instruction_packet_report.get("metadata")).get("proof_source")
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get("proof_source"),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "proof_source"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["proof_source"],
        ),
        _false_state_entry(
            "ingest_review",
            "candidate_elimination_claim",
            _all_false(
                _mapping(cover_report.get("metadata")).get(
                    "candidate_elimination_claim"
                )
                if cover_report is not None
                else None,
                _mapping(instruction_packet_report.get("metadata")).get(
                    "candidate_elimination_claim"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get(
                    "candidate_elimination_claim"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "candidate_elimination_claim"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["candidate_elimination_claim"],
        ),
        _false_state_entry(
            "ingest_review",
            "solver_invoked",
            _all_false(
                _mapping(cover_report.get("metadata")).get("solver_invoked")
                if cover_report is not None
                else None,
                _mapping(instruction_packet_report.get("metadata")).get("solver_invoked")
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get("solver_invoked"),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "solver_invoked"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["solver_invoked"],
        ),
        _false_state_entry(
            "ingest_review",
            "actual_human_review_has_happened",
            _all_false(packet_target.get("actual_human_review_has_happened")),
            INGEST_FALSE_STATE_DETAILS["actual_human_review_has_happened"],
        ),
        _false_state_entry(
            "ingest_review",
            "execution_authorized",
            _all_false(
                packet_target.get("execution_authorized"),
                _mapping(cover_note.get("preserved_false_states")).get(
                    "execution_authorized"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "execution_authorized"
                ),
            ),
            INGEST_FALSE_STATE_DETAILS["execution_authorized"],
        ),
    ]
    required_false_states_ok = all(
        entry["current_value"] is False for entry in false_state_entries
    )

    branch_ready = bool(
        cover_status.get("ingest_review_cover_note_ready")
        and _mapping(instruction_packet_report.get("status")).get(
            "ingest_review_instruction_packet_ready"
        )
        if instruction_packet_report is not None
        else False
    )
    branch_ready = bool(branch_ready and read_list_present and required_false_states_ok)

    forbidden_claims = _ordered_union(
        _string_list(cover_note.get("forbidden_claims")),
        _string_list(instruction_packet.get("forbidden_claims_or_actions")),
    )
    branch_summary = str(
        cover_note.get("handoff_summary")
        or cover_status.get("handoff_summary")
        or (
            "Read the operator handoff bundle first, then the locked validator/example "
            "references, and keep the ingest-review path review-only."
        )
    )

    return {
        "branch_summary": {
            "branch_id": "ingest_review",
            "branch_label": "Ingest Review",
            "branch_ready": branch_ready,
            "what_branch_is_for": purpose,
            "entrypoint_artifact": branch_entrypoint,
            "read_this_first": read_this_first,
            "still_blocked": still_blocked,
            "still_false": [
                entry for entry in false_state_entries if entry["current_value"] is False
            ],
            "branch_summary": branch_summary,
        },
        "branch_ready": branch_ready,
        "read_list_present": read_list_present,
        "required_false_states_ok": required_false_states_ok,
        "forbidden_claims": forbidden_claims,
    }


def _build_acceptance_branch(
    project_root: Path,
    cover_path: Path,
    cover_report: Optional[Dict[str, Any]],
    instruction_packet_path: Path,
    instruction_packet_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    cover_status = _mapping(cover_report.get("status")) if cover_report is not None else {}
    cover_note = (
        _mapping(cover_report.get("acceptance_authorization_cover_note"))
        if cover_report is not None
        else {}
    )
    instruction_packet = (
        _mapping(
            instruction_packet_report.get(
                "acceptance_authorization_instruction_packet"
            )
        )
        if instruction_packet_report is not None
        else {}
    )
    packet_target = _mapping(cover_note.get("packet_target"))
    instruction_target = _mapping(instruction_packet.get("packet_target"))

    branch_entrypoint = {
        "branch_id": "acceptance_authorization",
        "branch_label": "Acceptance Authorization",
        "artifact_id": "acceptance_authorization_cover_note",
        "artifact_path": _display_path(project_root, cover_path),
        "why": (
            "Fastest review-only entrypoint for the future manual acceptance-authorization path."
        ),
    }
    read_this_first = _read_steps_from_entries(
        instruction_packet.get("open_these_first")
    ) or _read_steps_from_entries(cover_note.get("read_first"))
    read_list_present = bool(read_this_first)

    purpose = str(
        packet_target.get("detail")
        or instruction_target.get("detail")
        or cover_status.get("handoff_summary")
        or (
            "Future manual acceptance-authorization path for the locked prod_4x4_normal "
            "execution target."
        )
    )

    still_blocked = _normalize_blockers(
        cover_note.get("current_blockers"),
        cover_report.get("still_blocked_gate_ids") if cover_report is not None else None,
        _mapping(instruction_packet_report.get("status")).get("still_blocked_gate_ids")
        if instruction_packet_report is not None
        else None,
        instruction_packet_report.get("still_blocked_gate_ids")
        if instruction_packet_report is not None
        else None,
    )
    false_state_entries = [
        _false_state_entry(
            "acceptance_authorization",
            "reviewed_runtime_patch_exists",
            _gate_currently_false(still_blocked, "reviewed_runtime_patch_exists"),
            ACCEPTANCE_FALSE_STATE_DETAILS["reviewed_runtime_patch_exists"],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "future_manual_acceptance_authorization_review_prerequisites_met",
            _all_false(
                cover_status.get(
                    "future_manual_acceptance_authorization_review_prerequisites_met"
                ),
                _mapping(instruction_packet_report.get("status")).get(
                    "future_manual_acceptance_authorization_review_prerequisites_met"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get(
                    "future_manual_acceptance_authorization_review_prerequisites_met"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "future_manual_acceptance_authorization_review_prerequisites_met"
                ),
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS[
                "future_manual_acceptance_authorization_review_prerequisites_met"
            ],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "acceptance_execution_authorized",
            _all_false(
                cover_status.get("acceptance_execution_authorized"),
                _mapping(instruction_packet_report.get("status")).get(
                    "acceptance_execution_authorized"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get(
                    "acceptance_execution_authorized"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "acceptance_execution_authorized"
                ),
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS["acceptance_execution_authorized"],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "runtime_enablement_allowed",
            _all_false(
                cover_status.get("runtime_enablement_allowed"),
                _mapping(instruction_packet_report.get("status")).get(
                    "runtime_enablement_allowed"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get(
                    "runtime_enablement_allowed"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "runtime_enablement_allowed"
                ),
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS["runtime_enablement_allowed"],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "acceptance_executed",
            _all_false(
                cover_status.get("acceptance_executed"),
                _mapping(instruction_packet_report.get("status")).get(
                    "acceptance_executed"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get(
                    "acceptance_executed"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "acceptance_executed"
                ),
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS["acceptance_executed"],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "actual_human_authorization_review_happened",
            _all_false(
                cover_status.get("actual_human_authorization_review_happened"),
                _mapping(instruction_packet_report.get("status")).get(
                    "actual_human_authorization_review_happened"
                )
                if instruction_packet_report is not None
                else None,
                _mapping(cover_note.get("preserved_false_states")).get(
                    "actual_human_authorization_review_happened"
                ),
                _mapping(instruction_packet.get("preserved_state_assertions")).get(
                    "actual_human_authorization_review_happened"
                ),
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS[
                "actual_human_authorization_review_happened"
            ],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "proof_source",
            _all_false(
                _mapping(cover_report.get("metadata")).get("proof_source")
                if cover_report is not None
                else None,
                _mapping(instruction_packet_report.get("metadata")).get("proof_source")
                if instruction_packet_report is not None
                else None,
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS["proof_source"],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "candidate_elimination_claim",
            _all_false(
                _mapping(cover_report.get("metadata")).get(
                    "candidate_elimination_claim"
                )
                if cover_report is not None
                else None,
                _mapping(instruction_packet_report.get("metadata")).get(
                    "candidate_elimination_claim"
                )
                if instruction_packet_report is not None
                else None,
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS["candidate_elimination_claim"],
        ),
        _false_state_entry(
            "acceptance_authorization",
            "solver_invoked",
            _all_false(
                _mapping(cover_report.get("metadata")).get("solver_invoked")
                if cover_report is not None
                else None,
                _mapping(instruction_packet_report.get("metadata")).get("solver_invoked")
                if instruction_packet_report is not None
                else None,
            ),
            ACCEPTANCE_FALSE_STATE_DETAILS["solver_invoked"],
        ),
    ]
    required_false_states_ok = all(
        entry["current_value"] is False for entry in false_state_entries
    )

    branch_ready = bool(
        cover_status.get("acceptance_authorization_cover_note_ready")
        and _mapping(instruction_packet_report.get("status")).get(
            "acceptance_authorization_instruction_packet_ready"
        )
        if instruction_packet_report is not None
        else False
    )
    branch_ready = bool(branch_ready and read_list_present and required_false_states_ok)

    forbidden_claims = _ordered_union(
        _string_list(cover_note.get("forbidden_claims")),
        _string_list(instruction_packet.get("forbidden_claims_or_actions")),
    )
    branch_summary = str(
        cover_note.get("handoff_summary")
        or cover_status.get("handoff_summary")
        or (
            "Keep the locked prod_4x4_normal path review-only and blocked until "
            "reviewed_runtime_patch_exists becomes true through a separate process."
        )
    )

    return {
        "branch_summary": {
            "branch_id": "acceptance_authorization",
            "branch_label": "Acceptance Authorization",
            "branch_ready": branch_ready,
            "what_branch_is_for": purpose,
            "entrypoint_artifact": branch_entrypoint,
            "read_this_first": read_this_first,
            "still_blocked": still_blocked,
            "still_false": [
                entry for entry in false_state_entries if entry["current_value"] is False
            ],
            "branch_summary": branch_summary,
        },
        "branch_ready": branch_ready,
        "read_list_present": read_list_present,
        "required_false_states_ok": required_false_states_ok,
        "forbidden_claims": forbidden_claims,
    }


def _aggregate_blockers(branch_summaries: list[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}
    for branch in branch_summaries:
        branch_id = str(branch.get("branch_id"))
        for entry in _mapping_list(branch.get("still_blocked")):
            gate_id = str(entry.get("gate_id") or "").strip()
            if not gate_id:
                continue
            target = aggregated.setdefault(
                gate_id,
                {
                    "gate_id": gate_id,
                    "branches": [],
                    "required_state": entry.get("required_state"),
                    "current_value": entry.get("current_value", False),
                    "detail": str(entry.get("detail") or ""),
                },
            )
            if branch_id and branch_id not in target["branches"]:
                target["branches"].append(branch_id)
            if target.get("required_state") is None and entry.get("required_state") is not None:
                target["required_state"] = entry.get("required_state")
            if target.get("detail") == "" and entry.get("detail"):
                target["detail"] = str(entry.get("detail"))
    return list(aggregated.values())


def _aggregate_false_states(
    branch_summaries: list[Mapping[str, Any]]
) -> list[Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}
    for branch in branch_summaries:
        branch_id = str(branch.get("branch_id"))
        for entry in _mapping_list(branch.get("still_false")):
            state_id = str(entry.get("state_id") or "").strip()
            if not state_id or entry.get("current_value") is not False:
                continue
            target = aggregated.setdefault(
                state_id,
                {
                    "state_id": state_id,
                    "branches": [],
                    "current_value": False,
                    "detail": str(entry.get("detail") or ""),
                },
            )
            if branch_id and branch_id not in target["branches"]:
                target["branches"].append(branch_id)
            if target.get("detail") == "" and entry.get("detail"):
                target["detail"] = str(entry.get("detail"))
    return list(aggregated.values())


def _false_state_entry(
    branch_id: str,
    state_id: str,
    is_false: bool,
    detail: str,
) -> Dict[str, Any]:
    return {
        "branch_id": branch_id,
        "state_id": state_id,
        "current_value": False if is_false else True,
        "detail": detail,
    }


def _normalize_blockers(*sources: Any) -> list[Dict[str, Any]]:
    blockers: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        if isinstance(source, list):
            for entry in source:
                if isinstance(entry, Mapping):
                    gate_id = str(entry.get("gate_id") or "").strip()
                    if not gate_id or gate_id in seen:
                        continue
                    blockers.append(
                        {
                            "gate_id": gate_id,
                            "required_state": entry.get("required_state"),
                            "current_value": entry.get("current_value", False),
                            "detail": str(
                                entry.get("detail")
                                or "Still blocked and must be carried forward unchanged."
                            ),
                        }
                    )
                    seen.add(gate_id)
                else:
                    gate_id = str(entry).strip()
                    if gate_id and gate_id not in seen:
                        blockers.append(
                            {
                                "gate_id": gate_id,
                                "required_state": True,
                                "current_value": False,
                                "detail": "Still blocked and must be carried forward unchanged.",
                            }
                        )
                        seen.add(gate_id)
    return blockers


def _read_steps_from_entries(entries: Any) -> list[Dict[str, Any]]:
    steps: list[Dict[str, Any]] = []
    for raw in _mapping_list(entries):
        artifact_id = str(raw.get("artifact_id") or "").strip()
        artifact_path = _artifact_path_from_entry(raw)
        why_read_first = str(
            raw.get("why_read_first") or raw.get("why") or raw.get("detail") or ""
        ).strip()
        if not artifact_id or not artifact_path:
            continue
        steps.append(
            {
                "artifact_id": artifact_id,
                "artifact_path": artifact_path,
                "why_read_first": why_read_first,
            }
        )
    return steps


def _artifact_path_from_entry(entry: Mapping[str, Any]) -> str:
    for key in ("artifact_path", "path"):
        value = str(entry.get(key) or "").strip()
        if value:
            return value
    return ""


def _gate_currently_false(
    blockers: list[Mapping[str, Any]], gate_id: str
) -> bool:
    for entry in blockers:
        if str(entry.get("gate_id")) == gate_id:
            return entry.get("current_value", False) is False
    return False


def _all_false(*values: Any) -> bool:
    if not values:
        return False
    for value in values:
        normalized = _extract_boolean_like(value)
        if normalized is None:
            continue
        if normalized:
            return False
    return True


def _extract_boolean_like(value: Any) -> Optional[bool]:
    if isinstance(value, Mapping):
        for key in ("current_value", "expected_value", "locked_false"):
            if key in value:
                nested = value.get(key)
                if isinstance(nested, bool):
                    if key == "locked_false":
                        return False if nested else True
                    return nested
        return None
    if isinstance(value, bool):
        return value
    return None


def _contract_ok(metadata: Mapping[str, Any], *, require_no_solve: bool) -> bool:
    if not metadata:
        return False
    if require_no_solve and metadata.get("no_solve") is not True:
        return False
    return bool(
        metadata.get("review_only")
        and metadata.get("spec_only")
        and metadata.get("default_off")
        and metadata.get("runtime_precheck_enabled") is False
        and metadata.get("runtime_semantics_changed") is False
        and metadata.get("proof_source") is False
        and metadata.get("candidate_elimination_claim") is False
        and metadata.get("solver_invoked") is False
    )


def _locked_value(
    values: list[Any], *, normalize=None
) -> tuple[Optional[str], bool]:
    if normalize is None:
        normalize = _normalize_text
    normalized_values = [normalize(value) for value in values if normalize(value) != ""]
    if not normalized_values:
        return None, False
    first = normalized_values[0]
    return first, all(value == first for value in normalized_values[1:])


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc.msg}"
    if not isinstance(payload, dict):
        return None, "not_a_json_object"
    return payload, None


def _resolve_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (project_root / candidate).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(path)


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
    if error is None:
        return f"{display_path} missing expected source {expected_source}."
    return f"{display_path} unavailable: {error}."


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _ordered_union(*sources: Any) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for source in sources:
        for item in _string_list(source):
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _normalize_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _maybe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

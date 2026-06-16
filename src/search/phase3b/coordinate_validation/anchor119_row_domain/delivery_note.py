from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

DELIVERY_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_delivery_note_v1"
)
MANUAL_REVIEW_PACKAGE_INDEX_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_v1"
)
FINAL_HUMAN_HANDOFF_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_v1"
)

DEFAULT_MANUAL_REVIEW_PACKAGE_INDEX_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_20260424/"
    "anchor119_row_domain_manual_review_package_index.json"
)
DEFAULT_FINAL_HUMAN_HANDOFF_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_20260424/"
    "anchor119_row_domain_final_human_handoff_note.json"
)

DEFAULT_PACKAGE_NOTICE = (
    "Review-only/spec-only/default-off/no-solve only. This note does not update "
    "repo-side review state, does not imply reviewed_runtime_patch_exists=true, "
    "does not imply runtime_enablement_allowed=true, does not authorize execution, "
    "and does not imply any actual human review has already happened."
)
DEFAULT_WHAT_THIS_PACKAGE_DOES_NOT_DO = [
    "It does not run solver-backed search or any runtime or acceptance command.",
    "It does not update repo-side review state or review-status artifacts.",
    "It does not create, ingest, validate, or imply a completed real human review record.",
    "It does not clear blocked gates or flip preserved false states to true.",
    "It does not set reviewed_runtime_patch_exists=true or runtime_enablement_allowed=true.",
    "It does not authorize execution, runtime enablement, or acceptance execution.",
]
REQUIRED_FALSE_STATE_IDS = [
    "reviewed_runtime_patch_exists",
    "runtime_enablement_allowed",
    "proof_source",
    "candidate_elimination_claim",
    "solver_invoked",
    "repo_side_review_state_updated",
    "actual_human_review_has_happened",
    "execution_authorized",
    "future_manual_acceptance_authorization_review_prerequisites_met",
    "acceptance_execution_authorized",
    "acceptance_executed",
    "actual_human_authorization_review_happened",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_delivery_note(
    project_root: Path,
    *,
    manual_review_package_index_path: Optional[Path] = None,
    final_human_handoff_note_path: Optional[Path] = None,
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

    package_index_report, package_index_error = _load_json_mapping(
        package_index_resolved
    )
    final_handoff_report, final_handoff_error = _load_json_mapping(
        final_handoff_resolved
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
    preserved_false_states = (
        _mapping(package_index_report.get("preserved_false_states"))
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
    package_index_ready = bool(
        package_index_present
        and package_index_status.get("manual_review_package_index_ready", False)
    )
    final_handoff_ready = bool(
        final_handoff_present
        and final_handoff_status.get("final_human_handoff_note_ready", False)
    )

    contract_compatible = bool(
        package_index_present
        and final_handoff_present
        and _contract_ok(package_index_meta)
        and _contract_ok(final_handoff_meta)
        and _bool_false(package_index_meta.get("repo_side_review_state_updated"))
        and _bool_false(final_handoff_meta.get("repo_side_review_state_updated"))
    )

    candidate_key, candidate_key_locked = _locked_value(
        [
            package_target.get("candidate_key"),
            final_candidate.get("key"),
            final_note_target.get("candidate_key"),
        ]
    )
    anchor_idx_value, anchor_idx_locked = _locked_value(
        [
            package_target.get("anchor_idx"),
            final_candidate.get("anchor_idx"),
            final_note_target.get("anchor_idx"),
        ],
        normalize=_normalize_scalar,
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            package_target.get("formulation_profile"),
            final_candidate.get("formulation_profile"),
            final_note_target.get("formulation_profile"),
        ]
    )
    anchor_idx = _maybe_int(anchor_idx_value)
    candidate_locked = bool(
        candidate_key_locked
        and anchor_idx_locked
        and formulation_profile_locked
        and anchor_idx == 119
    )

    package_branches = _build_branch_overview(
        final_note,
        _mapping(package_index_report.get("branch_artifact_index"))
        if package_index_report is not None
        else {},
    )
    read_first = _build_read_first(final_note, package_index_report)
    top_blockers = _merge_top_blockers(
        package_index_report,
        final_handoff_status,
        final_note,
    )
    states_that_remain_false = _merge_false_states(preserved_false_states, final_note)
    required_false_states_retained = _required_false_states_retained(
        states_that_remain_false
    )

    what_this_package_does_not_do = _ordered_union(
        DEFAULT_WHAT_THIS_PACKAGE_DOES_NOT_DO,
        _string_list(final_note.get("what_this_package_still_does_not_do")),
    )

    note_target = {
        "note_kind": "bounded_review_only_package_delivery_note",
        "target_reader": str(
            final_note_target.get("target_reader") or "future_human_operator_or_reviewer"
        ),
        "package_id": str(
            package_target.get("package_id")
            or "anchor119_manual_review_package_across_ingest_and_acceptance_branches"
        ),
        "candidate_key": candidate_key,
        "anchor_idx": anchor_idx,
        "formulation_profile": formulation_profile,
        "branch_ids": [entry["branch_id"] for entry in package_branches],
        "branch_count": len(package_branches),
    }

    what_package_this_is = _first_text(
        final_note.get("what_this_package_is"),
        package_index_report.get("short_package_summary")
        if package_index_report is not None
        else None,
        (
            "Bounded delivery note for the anchor119 manual-review package. It points "
            "the next human to the two review-only branches, the first artifacts to "
            "open, the current blockers, and the states that must remain false."
        ),
    )
    package_overview = {
        "what_package_this_is": what_package_this_is,
        "package_notice": _first_text(
            DEFAULT_PACKAGE_NOTICE,
            package_target.get("package_notice"),
        ),
        "two_branches": package_branches,
    }

    top_blocker_gate_ids = [entry["gate_id"] for entry in top_blockers]
    delivery_summary = _build_delivery_summary(
        read_first=read_first,
        top_blockers=top_blockers,
        states_that_remain_false=states_that_remain_false,
    )

    checks = [
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
            "review_only_contract_retained",
            "pass" if contract_compatible else "fail",
            "Both upstream artifacts remain review-only/spec-only/default-off/no-solve with proof_source=false, candidate_elimination_claim=false, solver_invoked=false, and repo_side_review_state_updated=false."
            if contract_compatible
            else "At least one upstream artifact drifted away from the required review-only/default-off/no-solve contract.",
        ),
        _check(
            "anchor119_candidate_locked",
            "pass" if candidate_locked else "fail",
            "Candidate key, anchor_idx=119, and formulation_profile remain locked across the package index and final handoff note."
            if candidate_locked
            else "Candidate identity drifted across the upstream artifacts.",
        ),
        _check(
            "two_branches_present",
            "pass" if len(package_branches) == 2 else "fail",
            "The delivery note still resolves exactly two package branches."
            if len(package_branches) == 2
            else "The delivery note could not resolve exactly two package branches.",
        ),
        _check(
            "read_first_present",
            "pass" if len(read_first) >= 2 else "fail",
            "The delivery note exposes concrete first-read artifacts for both branches."
            if len(read_first) >= 2
            else "The delivery note could not resolve first-read artifacts for both branches.",
        ),
        _check(
            "top_blockers_present",
            "pass" if bool(top_blockers) else "fail",
            "The delivery note carries forward the current package-level blockers."
            if top_blockers
            else "The delivery note could not resolve any package-level blockers.",
        ),
        _check(
            "required_false_states_retained",
            "pass" if required_false_states_retained else "fail",
            "Required locked-false states remain false across the bounded delivery note."
            if required_false_states_retained
            else "At least one required locked-false state is missing or no longer false.",
        ),
    ]

    ready_prerequisite_check_ids = {
        "manual_review_package_index_present",
        "manual_review_package_index_ready",
        "final_human_handoff_note_present",
        "final_human_handoff_note_ready",
        "review_only_contract_retained",
        "anchor119_candidate_locked",
        "two_branches_present",
        "read_first_present",
        "top_blockers_present",
        "required_false_states_retained",
    }
    delivery_note_ready = all(
        check["status"] == "pass"
        for check in checks
        if check["check_id"] in ready_prerequisite_check_ids
    )
    missing_ready_gate_ids = [
        check["check_id"]
        for check in checks
        if check["status"] == "fail" and check["check_id"] in ready_prerequisite_check_ids
    ]

    if delivery_note_ready:
        recommended_next_step = (
            "hand_delivery_note_to_next_human_without_authorizing_execution"
        )
    else:
        recommended_next_step = "repair_delivery_note_inputs"

    return {
        "metadata": {
            "source": DELIVERY_NOTE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_delivery_note_review_only_spec_only_default_off_"
                "no_solve_solver_invoked_false"
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
            "manual_review_package_index": _display_path(
                project_root, package_index_resolved
            ),
            "final_human_handoff_note": _display_path(
                project_root, final_handoff_resolved
            ),
        },
        "status": {
            "delivery_note_ready": delivery_note_ready,
            "package_index_ready": package_index_ready,
            "final_human_handoff_note_ready": final_handoff_ready,
            "contract_compatible": contract_compatible,
            "missing_ready_gate_ids": missing_ready_gate_ids,
            "top_blocker_gate_ids": top_blocker_gate_ids,
            "required_false_state_ids": [
                entry["state_id"] for entry in states_that_remain_false
            ],
            "recommended_next_step": recommended_next_step,
        },
        "delivery_note": {
            "note_target": note_target,
            "package_overview": package_overview,
            "read_first": read_first,
            "top_blockers": top_blockers,
            "states_that_remain_false": states_that_remain_false,
            "what_this_package_does_not_do": what_this_package_does_not_do,
            "delivery_summary": delivery_summary,
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    note = _mapping(report.get("delivery_note"))
    note_target = _mapping(note.get("note_target"))
    package_overview = _mapping(note.get("package_overview"))

    lines = [
        "# Phase 3B Anchor119 Row-Domain Delivery Note",
        "",
        f"- delivery_note_ready: `{status.get('delivery_note_ready')}`",
        f"- package_index_ready: `{status.get('package_index_ready')}`",
        f"- final_human_handoff_note_ready: `{status.get('final_human_handoff_note_ready')}`",
        f"- contract_compatible: `{status.get('contract_compatible')}`",
        f"- top_blocker_gate_ids: `{', '.join(_string_list(status.get('top_blocker_gate_ids'))) or '(none)'}`",
        f"- recommended_next_step: `{status.get('recommended_next_step')}`",
        "",
        "## Note Target",
        "",
        f"- note_kind: `{note_target.get('note_kind')}`",
        f"- target_reader: `{note_target.get('target_reader')}`",
        f"- package_id: `{note_target.get('package_id')}`",
        f"- candidate_key: `{note_target.get('candidate_key')}`",
        f"- anchor_idx: `{note_target.get('anchor_idx')}`",
        f"- formulation_profile: `{note_target.get('formulation_profile')}`",
        f"- branch_ids: `{', '.join(_string_list(note_target.get('branch_ids')))}`",
        "",
        "## Package Overview",
        "",
        str(package_overview.get("what_package_this_is") or ""),
        "",
        f"- package_notice: {package_overview.get('package_notice')}",
    ]

    for entry in _mapping_list(package_overview.get("two_branches")):
        lines.append(
            f"- `{entry.get('branch_id')}` ({entry.get('branch_label')}): "
            f"{entry.get('what_branch_is_for')} "
            f"Entry point: `{entry.get('entrypoint_artifact_path')}`."
        )

    lines.extend(["", "## Read First", ""])
    for entry in _mapping_list(note.get("read_first")):
        lines.append(
            f"- `{entry.get('branch_id')}`: `{entry.get('artifact_path')}` - "
            f"{entry.get('why')}"
        )

    lines.extend(["", "## Top Blockers", ""])
    for entry in _mapping_list(note.get("top_blockers")):
        lines.append(
            f"- `{entry.get('gate_id')}`: branches=`{', '.join(_string_list(entry.get('branches')))}`; "
            f"current_value=`{entry.get('current_value')}`; {entry.get('detail')}"
        )

    lines.extend(["", "## States That Remain False", ""])
    for entry in _mapping_list(note.get("states_that_remain_false")):
        lines.append(
            f"- `{entry.get('state_id')}`: branches=`{', '.join(_string_list(entry.get('branches')))}`; "
            f"locked_false=`{entry.get('locked_false')}`; {entry.get('detail')}"
        )

    lines.extend(["", "## What This Package Does Not Do", ""])
    for entry in _string_list(note.get("what_this_package_does_not_do")):
        lines.append(f"- {entry}")

    lines.extend(
        [
            "",
            "## Delivery Summary",
            "",
            str(note.get("delivery_summary") or ""),
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    note = _mapping(report.get("delivery_note"))
    note_target = _mapping(note.get("note_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain delivery note",
            "delivery_note_ready=" + str(status.get("delivery_note_ready")),
            "candidate_key=" + str(note_target.get("candidate_key")),
            "anchor_idx=" + str(note_target.get("anchor_idx")),
            "formulation_profile=" + str(note_target.get("formulation_profile")),
            "branch_ids=" + ",".join(_string_list(note_target.get("branch_ids"))),
            "top_blocker_gate_ids="
            + ",".join(_string_list(status.get("top_blocker_gate_ids"))),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
            "delivery_summary="
            + str(_mapping(report.get("delivery_note")).get("delivery_summary")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_delivery_note(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_delivery_note",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_branch_overview(
    final_note: Mapping[str, Any],
    branch_artifact_index: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    summaries = _mapping_list(final_note.get("branch_summaries"))
    if summaries:
        result: list[Dict[str, Any]] = []
        for summary in summaries:
            entrypoint = _mapping(summary.get("entrypoint_artifact"))
            result.append(
                {
                    "branch_id": _normalize_branch_id(summary.get("branch_id")),
                    "branch_label": str(summary.get("branch_label") or ""),
                    "what_branch_is_for": str(
                        summary.get("what_branch_is_for")
                        or summary.get("branch_summary")
                        or ""
                    ),
                    "entrypoint_artifact_id": str(entrypoint.get("artifact_id") or ""),
                    "entrypoint_artifact_path": str(
                        entrypoint.get("artifact_path") or ""
                    ),
                }
            )
        return result

    result = []
    for branch_id, branch in branch_artifact_index.items():
        branch_mapping = _mapping(branch)
        primary_ids = _string_list(branch_mapping.get("primary_entrypoint_artifact_ids"))
        primary_path = ""
        for artifact in _mapping_list(branch_mapping.get("artifacts")):
            if str(artifact.get("artifact_id") or "") in primary_ids:
                primary_path = str(artifact.get("path") or "")
                break
        result.append(
            {
                "branch_id": _normalize_branch_id(branch_id),
                "branch_label": _branch_label(branch_id),
                "what_branch_is_for": str(branch_mapping.get("branch_summary") or ""),
                "entrypoint_artifact_id": primary_ids[0] if primary_ids else "",
                "entrypoint_artifact_path": primary_path,
            }
        )
    return result


def _build_read_first(
    final_note: Mapping[str, Any],
    package_index_report: Optional[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    read_first = []
    for index, entry in enumerate(_mapping_list(final_note.get("read_this_first")), start=1):
        artifact_path = str(entry.get("artifact_path") or entry.get("path") or "").strip()
        if not artifact_path:
            continue
        read_first.append(
            {
                "order": index,
                "branch_id": _normalize_branch_id(entry.get("branch_id")),
                "branch_label": str(entry.get("branch_label") or ""),
                "artifact_id": str(entry.get("artifact_id") or ""),
                "artifact_path": artifact_path,
                "why": str(entry.get("why") or ""),
            }
        )
    if read_first:
        return read_first

    if package_index_report is None:
        return []
    fallback = []
    for index, entry in enumerate(
        _mapping_list(package_index_report.get("primary_entrypoints")), start=1
    ):
        fallback.append(
            {
                "order": index,
                "branch_id": _normalize_branch_id(entry.get("branch_id")),
                "branch_label": _branch_label(entry.get("branch_id")),
                "artifact_id": str(entry.get("artifact_id") or ""),
                "artifact_path": str(entry.get("path") or ""),
                "why": str(entry.get("reason") or ""),
            }
        )
    return fallback


def _merge_top_blockers(
    package_index_report: Optional[Mapping[str, Any]],
    final_handoff_status: Mapping[str, Any],
    final_note: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for entry in _mapping_list(final_note.get("still_blocked")):
        gate_id = str(entry.get("gate_id") or "").strip()
        if not gate_id:
            continue
        merged[gate_id] = {
            "gate_id": gate_id,
            "branches": [_normalize_branch_id(branch) for branch in _string_list(entry.get("branches"))],
            "current_value": False if entry.get("current_value") is False else bool(entry.get("current_value")),
            "detail": str(entry.get("detail") or ""),
        }

    if package_index_report is not None:
        for entry in _mapping_list(package_index_report.get("global_blockers")):
            gate_id = str(entry.get("gate_id") or "").strip()
            if not gate_id:
                continue
            target = merged.setdefault(
                gate_id,
                {
                    "gate_id": gate_id,
                    "branches": [],
                    "current_value": False,
                    "detail": "",
                },
            )
            target["branches"] = _ordered_union(
                target["branches"],
                [_normalize_branch_id(branch) for branch in _string_list(entry.get("branches"))],
            )
            target["detail"] = _first_text(
                target.get("detail"),
                "; ".join(_string_list(entry.get("details"))),
            )
            if entry.get("current_value") is False:
                target["current_value"] = False

    order = _ordered_union(
        _string_list(final_handoff_status.get("still_blocked_gate_ids")),
        _string_list(
            _mapping(package_index_report.get("status") if package_index_report is not None else {}).get(
                "global_blocker_gate_ids"
            )
        ),
        list(merged.keys()),
    )

    result = []
    for gate_id in order:
        entry = merged.get(gate_id)
        if entry is None:
            continue
        result.append(entry)
    return result


def _merge_false_states(
    preserved_false_states: Mapping[str, Any],
    final_note: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    final_note_false_state_map: Dict[str, Dict[str, Any]] = {}
    for entry in _mapping_list(final_note.get("still_false")):
        state_id = str(entry.get("state_id") or "").strip()
        if not state_id:
            continue
        final_note_false_state_map[state_id] = {
            "branches": [_normalize_branch_id(branch) for branch in _string_list(entry.get("branches"))],
            "current_value": entry.get("current_value"),
            "detail": str(entry.get("detail") or ""),
        }

    ordered_state_ids = _ordered_union(
        REQUIRED_FALSE_STATE_IDS,
        list(preserved_false_states.keys()),
        list(final_note_false_state_map.keys()),
    )

    result = []
    for state_id in ordered_state_ids:
        package_entry = _mapping(preserved_false_states.get(state_id))
        handoff_entry = _mapping(final_note_false_state_map.get(state_id))
        if not package_entry and not handoff_entry:
            continue
        current_value = _state_current_value(package_entry, handoff_entry)
        locked_false = bool(
            package_entry.get("locked_false") is True or current_value is False
        )
        branches = _ordered_union(
            [_normalize_branch_id(branch) for branch in _string_list(package_entry.get("branches"))],
            _string_list(handoff_entry.get("branches")),
        )
        result.append(
            {
                "state_id": state_id,
                "branches": branches,
                "current_value": current_value,
                "locked_false": locked_false,
                "detail": _first_text(
                    handoff_entry.get("detail"),
                    package_entry.get("detail"),
                ),
            }
        )
    return result


def _required_false_states_retained(
    states_that_remain_false: list[Mapping[str, Any]]
) -> bool:
    state_map = {
        str(entry.get("state_id") or ""): entry for entry in states_that_remain_false
    }
    for state_id in REQUIRED_FALSE_STATE_IDS:
        entry = _mapping(state_map.get(state_id))
        if not entry:
            return False
        if entry.get("current_value") is not False:
            return False
        if entry.get("locked_false") is not True:
            return False
    return True


def _build_delivery_summary(
    *,
    read_first: list[Mapping[str, Any]],
    top_blockers: list[Mapping[str, Any]],
    states_that_remain_false: list[Mapping[str, Any]],
) -> str:
    first_paths = [str(entry.get("artifact_path") or "") for entry in read_first[:2]]
    top_gate_ids = [str(entry.get("gate_id") or "") for entry in top_blockers[:5]]
    important_false_state_ids = []
    for state_id in [
        "reviewed_runtime_patch_exists",
        "runtime_enablement_allowed",
        "acceptance_execution_authorized",
        "acceptance_executed",
        "proof_source",
        "candidate_elimination_claim",
        "solver_invoked",
    ]:
        if any(str(entry.get("state_id") or "") == state_id for entry in states_that_remain_false):
            important_false_state_ids.append(state_id)
    first_read_text = (
        ", then ".join(f"`{path}`" for path in first_paths)
        if first_paths
        else "the locked branch entrypoints"
    )
    blocker_text = (
        ", ".join(f"`{gate_id}`" for gate_id in top_gate_ids)
        if top_gate_ids
        else "the existing blocked gates"
    )
    false_state_text = (
        ", ".join(f"`{state_id}=false`" for state_id in important_false_state_ids)
        if important_false_state_ids
        else "the locked false-state contract"
    )
    return (
        "Start with "
        + first_read_text
        + ". The package remains blocked by "
        + blocker_text
        + ". Keep "
        + false_state_text
        + ", keep the package review-only/spec-only/default-off/no-solve, and do not "
        "treat this note as human review completion, reviewed-runtime-patch approval, "
        "runtime enablement approval, or execution authorization."
    )


def _state_current_value(
    package_entry: Mapping[str, Any], handoff_entry: Mapping[str, Any]
) -> bool:
    if package_entry:
        if "current_value" in package_entry:
            return bool(package_entry.get("current_value"))
        if "locked_false" in package_entry:
            return not bool(package_entry.get("locked_false"))
    if handoff_entry and "current_value" in handoff_entry:
        return bool(handoff_entry.get("current_value"))
    return True


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


def _contract_ok(metadata: Mapping[str, Any]) -> bool:
    if not metadata:
        return False
    return bool(
        metadata.get("review_only") is True
        and metadata.get("spec_only") is True
        and metadata.get("default_off") is True
        and metadata.get("no_solve") is True
        and metadata.get("runtime_precheck_enabled") is False
        and metadata.get("runtime_semantics_changed") is False
        and metadata.get("proof_source") is False
        and metadata.get("candidate_elimination_claim") is False
        and metadata.get("solver_invoked") is False
    )


def _bool_false(value: Any) -> bool:
    return value is False


def _locked_value(
    values: list[Any], *, normalize=None
) -> tuple[Optional[Any], bool]:
    if normalize is None:
        normalize = _normalize_text
    actual_values = [value for value in values if _normalize_text(value) != ""]
    if not actual_values:
        return None, False
    normalized_values = [normalize(value) for value in actual_values]
    return actual_values[0], all(
        value == normalized_values[0] for value in normalized_values[1:]
    )


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


def _normalize_branch_id(value: Any) -> str:
    return str(value or "").strip().replace("-", "_")


def _branch_label(value: Any) -> str:
    branch_id = _normalize_branch_id(value)
    if branch_id == "ingest_review":
        return "Ingest Review"
    if branch_id == "acceptance_authorization":
        return "Acceptance Authorization"
    return branch_id.replace("_", " ").title()


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).strip().split()) if value is not None else ""


def _normalize_scalar(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _maybe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            text = "; ".join(_string_list(value))
            if text:
                return text
        elif value not in (None, ""):
            text = str(value).strip()
            if text:
                return text
    return ""


def _ordered_union(*sources: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for source in sources:
        items: list[str]
        if isinstance(source, list):
            items = [str(item).strip() for item in source if str(item).strip()]
        elif isinstance(source, tuple):
            items = [str(item).strip() for item in source if str(item).strip()]
        else:
            items = _string_list(source)
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}

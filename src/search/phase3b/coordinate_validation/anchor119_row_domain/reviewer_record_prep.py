from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
ACCEPTANCE_REFRESH_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
)
REVIEWER_RECORD_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_v1"
)
DEFAULT_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)
DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_20260424/"
    "anchor119_row_domain_acceptance_refresh_prep.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep(
    project_root: Path,
    *,
    signoff_bundle_path: Optional[Path] = None,
    acceptance_refresh_prep_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    signoff_bundle_resolved = _resolve_path(
        project_root,
        signoff_bundle_path if signoff_bundle_path is not None else DEFAULT_SIGNOFF_BUNDLE_PATH,
    )
    acceptance_refresh_prep_resolved = _resolve_path(
        project_root,
        acceptance_refresh_prep_path
        if acceptance_refresh_prep_path is not None
        else DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH,
    )

    signoff_bundle_report, signoff_bundle_error = _load_json_mapping(
        signoff_bundle_resolved
    )
    acceptance_refresh_prep_report, acceptance_refresh_prep_error = _load_json_mapping(
        acceptance_refresh_prep_resolved
    )

    signoff_meta = (
        _mapping(signoff_bundle_report.get("metadata")) if signoff_bundle_report else {}
    )
    signoff_status = (
        _mapping(signoff_bundle_report.get("status")) if signoff_bundle_report else {}
    )
    signoff_bundle = (
        _mapping(signoff_bundle_report.get("signoff_bundle")) if signoff_bundle_report else {}
    )
    acceptance_meta = (
        _mapping(acceptance_refresh_prep_report.get("metadata"))
        if acceptance_refresh_prep_report
        else {}
    )
    acceptance_status = (
        _mapping(acceptance_refresh_prep_report.get("status"))
        if acceptance_refresh_prep_report
        else {}
    )
    acceptance_refresh_prep = (
        _mapping(acceptance_refresh_prep_report.get("acceptance_refresh_prep"))
        if acceptance_refresh_prep_report
        else {}
    )
    candidate = (
        _mapping(acceptance_refresh_prep_report.get("candidate"))
        if acceptance_refresh_prep_report
        else _mapping(signoff_bundle_report.get("candidate"))
        if signoff_bundle_report
        else {}
    )

    signoff_bundle_present = bool(
        signoff_bundle_report is not None
        and signoff_bundle_error is None
        and signoff_meta.get("source") == SIGNOFF_BUNDLE_SOURCE
    )
    acceptance_refresh_prep_present = bool(
        acceptance_refresh_prep_report is not None
        and acceptance_refresh_prep_error is None
        and acceptance_meta.get("source") == ACCEPTANCE_REFRESH_PREP_SOURCE
    )

    signoff_bundle_ready = bool(signoff_status.get("signoff_bundle_ready", False))
    acceptance_refresh_prep_ready = bool(
        acceptance_status.get("acceptance_refresh_prep_ready", False)
    )
    reviewed_runtime_patch_exists = bool(
        signoff_status.get("reviewed_runtime_patch_exists", False)
    )
    runtime_enablement_allowed = bool(
        signoff_status.get("runtime_enablement_allowed", False)
        or acceptance_status.get("runtime_enablement_allowed", False)
    )

    signoff_record_template = _mapping(signoff_bundle.get("signoff_record_template"))
    required_sequence = _string_list(acceptance_refresh_prep.get("required_sequence"))
    required_statement_ids = [
        str(entry.get("statement_id"))
        for entry in list(signoff_bundle.get("required_reviewer_statements", []))
        if isinstance(entry, Mapping) and entry.get("statement_id")
    ]

    signoff_record_template_present = bool(signoff_record_template)
    sequence_mentions_reviewed_record = (
        "reviewed_runtime_patch_signoff_record" in required_sequence
    )
    default_off_retained = bool(
        signoff_bundle_present
        and acceptance_refresh_prep_present
        and bool(signoff_meta.get("default_off", False))
        and bool(acceptance_meta.get("default_off", False))
        and not runtime_enablement_allowed
    )
    reviewed_runtime_patch_absent_as_expected = bool(
        signoff_bundle_present and not reviewed_runtime_patch_exists
    )

    carry_forward_gate_entries = _merge_gate_entries(
        _blocked_gate_entries(signoff_bundle_report),
        _blocked_gate_entries(acceptance_refresh_prep_report),
    )
    carry_forward_still_blocked_gate_ids = [
        str(entry.get("gate_id")) for entry in carry_forward_gate_entries if entry.get("gate_id")
    ]

    gates = [
        {
            "gate_id": "signoff_bundle_ready",
            "satisfied": bool(signoff_bundle_ready),
            "blocking": not bool(signoff_bundle_ready),
            "detail": "Reviewer-record prep depends on the runtime patch signoff bundle already being ready for review.",
        },
        {
            "gate_id": "acceptance_refresh_prep_ready",
            "satisfied": bool(acceptance_refresh_prep_ready),
            "blocking": not bool(acceptance_refresh_prep_ready),
            "detail": "Reviewer-record prep depends on acceptance-refresh prep already being review-ready, but still default-off.",
        },
        {
            "gate_id": "signoff_record_template_present",
            "satisfied": bool(signoff_record_template_present),
            "blocking": not bool(signoff_record_template_present),
            "detail": "The signoff bundle must provide the eventual reviewer signoff record template.",
        },
        {
            "gate_id": "reviewed_record_step_present_in_acceptance_sequence",
            "satisfied": bool(sequence_mentions_reviewed_record),
            "blocking": not bool(sequence_mentions_reviewed_record),
            "detail": "Acceptance refresh prep must still name reviewed_runtime_patch_signoff_record as the next concrete step before any acceptance refresh.",
        },
        {
            "gate_id": "default_off_retained_for_reviewer_record_prep",
            "satisfied": bool(default_off_retained),
            "blocking": not bool(default_off_retained),
            "detail": "This prep remains explicit default-off and is not runtime enablement.",
        },
    ]
    gates.extend(carry_forward_gate_entries)

    checks = [
        _check(
            "signoff_bundle_present",
            "pass" if signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if signoff_bundle_present
            else signoff_bundle_error
            or (
                f"unexpected_source:{signoff_meta.get('source')}"
                if signoff_bundle_report is not None
                else f"missing:{_display_path(project_root, signoff_bundle_resolved)}"
            ),
        ),
        _check(
            "acceptance_refresh_prep_present",
            "pass" if acceptance_refresh_prep_present else "fail",
            "acceptance refresh prep loaded"
            if acceptance_refresh_prep_present
            else acceptance_refresh_prep_error
            or (
                f"unexpected_source:{acceptance_meta.get('source')}"
                if acceptance_refresh_prep_report is not None
                else f"missing:{_display_path(project_root, acceptance_refresh_prep_resolved)}"
            ),
        ),
        _check(
            "signoff_bundle_ready",
            "pass" if signoff_bundle_ready else "fail",
            str(signoff_bundle_ready),
        ),
        _check(
            "acceptance_refresh_prep_ready",
            "pass" if acceptance_refresh_prep_ready else "fail",
            str(acceptance_refresh_prep_ready),
        ),
        _check(
            "signoff_record_template_present",
            "pass" if signoff_record_template_present else "fail",
            "signoff record template present"
            if signoff_record_template_present
            else "missing",
        ),
        _check(
            "acceptance_sequence_mentions_reviewed_record",
            "pass" if sequence_mentions_reviewed_record else "fail",
            ",".join(required_sequence) if required_sequence else "missing",
        ),
        _check(
            "default_off_retained",
            "pass" if default_off_retained else "fail",
            "default-off retained and runtime enablement remains blocked"
            if default_off_retained
            else "expected default_off=true and runtime_enablement_allowed=false",
        ),
        _check(
            "reviewed_runtime_patch_absent_as_expected",
            "pass" if reviewed_runtime_patch_absent_as_expected else "fail",
            str(reviewed_runtime_patch_exists),
        ),
    ]

    reviewer_record_prep_ready = all(check["status"] == "pass" for check in checks)
    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    handoff_recommendation = (
        "Reviewer-record prep is ready for review: fill the eventual reviewed runtime patch signoff record with the required fields and reviewer statement ids, keep reviewed_runtime_patch_exists=false until the signed record is actually created, and keep runtime disabled/default-off because this prep is not runtime enablement."
        if reviewer_record_prep_ready
        else "Reviewer-record prep is blocked; repair the missing signoff-bundle or acceptance-refresh-prep prerequisites before asking for reviewer signoff record preparation."
    )

    return {
        "metadata": {
            "source": REVIEWER_RECORD_PREP_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_reviewer_record_prep_not_runtime_enablement",
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
            "signoff_bundle": _display_path(project_root, signoff_bundle_resolved),
            "acceptance_refresh_prep": _display_path(
                project_root, acceptance_refresh_prep_resolved
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "reviewer_record_prep_ready": bool(reviewer_record_prep_ready),
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "runtime_enablement_allowed": bool(runtime_enablement_allowed),
            "recommended_next_step": (
                "prepare_reviewed_runtime_patch_signoff_record_then_hold_default_off"
                if reviewer_record_prep_ready
                else "repair_reviewer_record_prep_inputs"
            ),
            "handoff_recommendation": handoff_recommendation,
        },
        "reviewer_record_prep": {
            "record_type": signoff_record_template.get("record_type"),
            "scope": signoff_record_template.get("scope") or signoff_bundle.get("scope"),
            "required_reviewer_statement_ids": required_statement_ids,
            "required_record_fields": _build_required_record_fields(
                signoff_record_template,
                required_statement_ids=required_statement_ids,
                carry_forward_still_blocked_gate_ids=carry_forward_still_blocked_gate_ids,
            ),
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("reviewer_record_prep"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Reviewer Record Prep",
        "",
        f"- Reviewer record prep ready: `{status.get('reviewer_record_prep_ready')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        "- This artifact remains explicit default-off and is not runtime enablement.",
        "",
        "## Reviewer Record Prep",
        "",
        f"- Record type: `{prep.get('record_type')}`",
        f"- Scope: `{prep.get('scope')}`",
        f"- Required reviewer statement ids: `{', '.join(_string_list(prep.get('required_reviewer_statement_ids'))) or '(none)'}`",
        "",
        "## Required Record Fields",
        "",
        "| Field | Required | Template value | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(prep.get("required_record_fields", [])):
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


def render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("reviewer_record_prep"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain reviewer record prep",
            f"reviewer_record_prep_ready={status.get('reviewer_record_prep_ready')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            f"record_type={prep.get('record_type')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_reviewer_record_prep",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_required_record_fields(
    signoff_record_template: Mapping[str, Any],
    *,
    required_statement_ids: list[str],
    carry_forward_still_blocked_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    if not signoff_record_template:
        return []
    return [
        {
            "field": "record_type",
            "required": True,
            "template_value": signoff_record_template.get("record_type"),
            "detail": "Carry forward the fixed record type from the signoff bundle template.",
        },
        {
            "field": "reviewer_id",
            "required": True,
            "template_value": signoff_record_template.get("reviewer_id"),
            "detail": "Populate the reviewer identifier before the signoff record is considered complete.",
        },
        {
            "field": "reviewed_at",
            "required": True,
            "template_value": signoff_record_template.get("reviewed_at"),
            "detail": "Populate the review timestamp; ISO-8601 UTC is preferred.",
        },
        {
            "field": "verdict",
            "required": True,
            "template_value": signoff_record_template.get("verdict"),
            "detail": "Record the reviewer verdict; this prep artifact does not apply runtime enablement.",
        },
        {
            "field": "scope",
            "required": True,
            "template_value": signoff_record_template.get("scope"),
            "detail": "Carry forward the reviewed runtime patch scope from the signoff bundle.",
        },
        {
            "field": "notes",
            "required": True,
            "template_value": signoff_record_template.get("notes"),
            "detail": "Reviewer notes or justification captured alongside the signoff record.",
        },
        {
            "field": "agreed_statement_ids",
            "required": True,
            "template_value": required_statement_ids,
            "detail": "Populate with the required reviewer statement ids that the reviewer explicitly agrees to.",
        },
        {
            "field": "still_blocked_gate_ids",
            "required": True,
            "template_value": carry_forward_still_blocked_gate_ids,
            "detail": "Carry forward the gates that remain blocked after signoff; this stays default-off and not runtime enablement.",
        },
    ]


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

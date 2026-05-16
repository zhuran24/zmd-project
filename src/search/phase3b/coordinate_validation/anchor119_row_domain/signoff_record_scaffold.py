from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

REVIEWER_RECORD_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
SIGNOFF_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_v1"
)
DEFAULT_REVIEWER_RECORD_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_20260424/"
    "anchor119_row_domain_reviewer_record_prep.json"
)
DEFAULT_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)
SCAFFOLD_NOTICE = (
    "Pending scaffold only; this artifact is not an actual reviewed runtime patch signoff "
    "record and does not allow runtime enablement."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold(
    project_root: Path,
    *,
    reviewer_record_prep_path: Optional[Path] = None,
    signoff_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    reviewer_record_prep_resolved = _resolve_path(
        project_root,
        reviewer_record_prep_path
        if reviewer_record_prep_path is not None
        else DEFAULT_REVIEWER_RECORD_PREP_PATH,
    )
    signoff_bundle_resolved = _resolve_path(
        project_root,
        signoff_bundle_path if signoff_bundle_path is not None else DEFAULT_SIGNOFF_BUNDLE_PATH,
    )

    reviewer_record_prep_report, reviewer_record_prep_error = _load_json_mapping(
        reviewer_record_prep_resolved
    )
    signoff_bundle_report, signoff_bundle_error = _load_json_mapping(
        signoff_bundle_resolved
    )

    reviewer_meta = (
        _mapping(reviewer_record_prep_report.get("metadata"))
        if reviewer_record_prep_report
        else {}
    )
    reviewer_status = (
        _mapping(reviewer_record_prep_report.get("status"))
        if reviewer_record_prep_report
        else {}
    )
    reviewer_record_prep = (
        _mapping(reviewer_record_prep_report.get("reviewer_record_prep"))
        if reviewer_record_prep_report
        else {}
    )
    signoff_meta = (
        _mapping(signoff_bundle_report.get("metadata")) if signoff_bundle_report else {}
    )
    signoff_status = (
        _mapping(signoff_bundle_report.get("status")) if signoff_bundle_report else {}
    )
    signoff_bundle = (
        _mapping(signoff_bundle_report.get("signoff_bundle"))
        if signoff_bundle_report
        else {}
    )
    candidate = (
        _mapping(reviewer_record_prep_report.get("candidate"))
        if reviewer_record_prep_report
        else _mapping(signoff_bundle_report.get("candidate"))
        if signoff_bundle_report
        else {}
    )

    reviewer_record_prep_present = bool(
        reviewer_record_prep_report is not None
        and reviewer_record_prep_error is None
        and reviewer_meta.get("source") == REVIEWER_RECORD_PREP_SOURCE
    )
    signoff_bundle_present = bool(
        signoff_bundle_report is not None
        and signoff_bundle_error is None
        and signoff_meta.get("source") == RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE
    )

    reviewer_record_prep_ready = bool(
        reviewer_status.get("reviewer_record_prep_ready", False)
    )
    signoff_bundle_ready = bool(signoff_status.get("signoff_bundle_ready", False))
    upstream_reviewed_runtime_patch_exists = bool(
        reviewer_status.get("reviewed_runtime_patch_exists", False)
        or signoff_status.get("reviewed_runtime_patch_exists", False)
    )
    upstream_runtime_enablement_allowed = bool(
        reviewer_status.get("runtime_enablement_allowed", False)
        or signoff_status.get("runtime_enablement_allowed", False)
    )

    required_record_fields = _mapping_list(
        reviewer_record_prep.get("required_record_fields")
    )
    signoff_record_template = _mapping(signoff_bundle.get("signoff_record_template"))
    required_statement_ids = _string_list(
        reviewer_record_prep.get("required_reviewer_statement_ids")
    )
    if not required_statement_ids:
        required_statement_ids = [
            str(entry.get("statement_id"))
            for entry in list(signoff_bundle.get("required_reviewer_statements", []))
            if isinstance(entry, Mapping) and entry.get("statement_id")
        ]

    carry_forward_gate_entries = _merge_gate_entries(
        _blocked_gate_entries(reviewer_record_prep_report),
        _blocked_gate_entries(signoff_bundle_report),
    )
    carry_forward_still_blocked_gate_ids = [
        str(entry.get("gate_id"))
        for entry in carry_forward_gate_entries
        if entry.get("gate_id")
    ]

    pending_signoff_record_payload = _build_pending_signoff_record_payload(
        signoff_record_template,
        required_record_fields=required_record_fields,
        required_statement_ids=required_statement_ids,
        carry_forward_still_blocked_gate_ids=carry_forward_still_blocked_gate_ids,
    )

    required_record_fields_present = bool(required_record_fields)
    signoff_record_template_present = bool(signoff_record_template)
    required_statement_ids_present = bool(required_statement_ids)
    pending_signoff_record_payload_present = bool(pending_signoff_record_payload)
    default_off_retained = bool(
        reviewer_record_prep_present
        and signoff_bundle_present
        and bool(reviewer_meta.get("default_off", False))
        and bool(signoff_meta.get("default_off", False))
        and not upstream_runtime_enablement_allowed
    )

    gates = [
        {
            "gate_id": "reviewer_record_prep_ready",
            "satisfied": bool(reviewer_record_prep_ready),
            "blocking": not bool(reviewer_record_prep_ready),
            "detail": "The reviewer-record prep artifact must already be ready before the scaffold is emitted.",
        },
        {
            "gate_id": "signoff_bundle_ready",
            "satisfied": bool(signoff_bundle_ready),
            "blocking": not bool(signoff_bundle_ready),
            "detail": "The runtime patch signoff bundle must remain review-ready before the scaffold is emitted.",
        },
        {
            "gate_id": "required_record_fields_present",
            "satisfied": bool(required_record_fields_present),
            "blocking": not bool(required_record_fields_present),
            "detail": "Reviewer-record prep must carry the required record fields for the pending scaffold payload.",
        },
        {
            "gate_id": "signoff_record_template_present",
            "satisfied": bool(signoff_record_template_present),
            "blocking": not bool(signoff_record_template_present),
            "detail": "The signoff bundle must carry the eventual signoff record template that the scaffold reuses.",
        },
        {
            "gate_id": "required_reviewer_statement_ids_present",
            "satisfied": bool(required_statement_ids_present),
            "blocking": not bool(required_statement_ids_present),
            "detail": "Required reviewer statement ids must remain attached to the scaffold payload.",
        },
        {
            "gate_id": "pending_signoff_record_payload_present",
            "satisfied": bool(pending_signoff_record_payload_present),
            "blocking": not bool(pending_signoff_record_payload_present),
            "detail": "The scaffold must expose a pending signoff record payload without creating an actual signoff.",
        },
        {
            "gate_id": "default_off_retained_for_scaffold",
            "satisfied": bool(default_off_retained),
            "blocking": not bool(default_off_retained),
            "detail": "This scaffold remains explicit default-off and is not runtime enablement.",
        },
    ]
    gates.extend(carry_forward_gate_entries)

    checks = [
        _check(
            "reviewer_record_prep_present",
            "pass" if reviewer_record_prep_present else "fail",
            "reviewer record prep loaded"
            if reviewer_record_prep_present
            else reviewer_record_prep_error
            or (
                f"unexpected_source:{reviewer_meta.get('source')}"
                if reviewer_record_prep_report is not None
                else f"missing:{_display_path(project_root, reviewer_record_prep_resolved)}"
            ),
        ),
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
            "reviewer_record_prep_ready",
            "pass" if reviewer_record_prep_ready else "fail",
            str(reviewer_record_prep_ready),
        ),
        _check(
            "signoff_bundle_ready",
            "pass" if signoff_bundle_ready else "fail",
            str(signoff_bundle_ready),
        ),
        _check(
            "required_record_fields_present",
            "pass" if required_record_fields_present else "fail",
            str(required_record_fields_present),
        ),
        _check(
            "signoff_record_template_present",
            "pass" if signoff_record_template_present else "fail",
            "signoff record template present"
            if signoff_record_template_present
            else "missing",
        ),
        _check(
            "required_reviewer_statement_ids_present",
            "pass" if required_statement_ids_present else "fail",
            ",".join(required_statement_ids) if required_statement_ids else "missing",
        ),
        _check(
            "pending_signoff_record_payload_present",
            "pass" if pending_signoff_record_payload_present else "fail",
            "pending scaffold payload present"
            if pending_signoff_record_payload_present
            else "missing",
        ),
        _check(
            "default_off_retained",
            "pass" if default_off_retained else "fail",
            "default-off retained and runtime enablement remains blocked"
            if default_off_retained
            else "expected default_off=true and runtime_enablement_allowed=false upstream",
        ),
        _check(
            "upstream_reviewed_runtime_patch_absent_as_expected",
            "pass" if not upstream_reviewed_runtime_patch_exists else "fail",
            str(upstream_reviewed_runtime_patch_exists),
        ),
        _check(
            "upstream_runtime_enablement_blocked_as_expected",
            "pass" if not upstream_runtime_enablement_allowed else "fail",
            str(upstream_runtime_enablement_allowed),
        ),
    ]

    signoff_record_scaffold_ready = all(check["status"] == "pass" for check in checks)
    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    handoff_recommendation = (
        "Signoff record scaffold is ready: hand the pending scaffold payload to the reviewer as a template only, keep reviewed_runtime_patch_exists=false until a real signed record exists, and keep runtime disabled/default-off because this scaffold is not actual signoff."
        if signoff_record_scaffold_ready
        else "Signoff record scaffold is blocked; repair the missing reviewer-record-prep or signoff-bundle prerequisites before asking anyone to fill the pending template."
    )

    return {
        "metadata": {
            "source": SIGNOFF_RECORD_SCAFFOLD_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_signoff_record_scaffold_not_actual_signoff",
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
            "reviewer_record_prep": _display_path(
                project_root, reviewer_record_prep_resolved
            ),
            "signoff_bundle": _display_path(project_root, signoff_bundle_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "signoff_record_scaffold_ready": bool(signoff_record_scaffold_ready),
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommended_next_step": (
                "handoff_pending_signoff_record_scaffold_for_manual_reviewer_completion"
                if signoff_record_scaffold_ready
                else "repair_signoff_record_scaffold_inputs"
            ),
            "handoff_recommendation": handoff_recommendation,
        },
        "signoff_record_scaffold": {
            "record_type": pending_signoff_record_payload.get("record_type"),
            "scope": pending_signoff_record_payload.get("scope"),
            "required_reviewer_statement_ids": required_statement_ids,
            "required_record_fields": [dict(entry) for entry in required_record_fields],
            "pending_signoff_record_payload": pending_signoff_record_payload,
            "scaffold_notice": SCAFFOLD_NOTICE,
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    scaffold = _mapping(report.get("signoff_record_scaffold"))
    pending_payload = _mapping(scaffold.get("pending_signoff_record_payload"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Signoff Record Scaffold",
        "",
        f"- Signoff record scaffold ready: `{status.get('signoff_record_scaffold_ready')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Scaffold notice: {scaffold.get('scaffold_notice')}",
        "",
        "## Pending Signoff Record Payload",
        "",
        f"- Record type: `{pending_payload.get('record_type')}`",
        f"- Scope: `{pending_payload.get('scope')}`",
        f"- Verdict: `{pending_payload.get('verdict')}`",
        f"- Agreed statement ids: `{', '.join(_string_list(pending_payload.get('agreed_statement_ids'))) or '(none)'}`",
        f"- Still blocked gate ids: `{', '.join(_string_list(pending_payload.get('still_blocked_gate_ids'))) or '(none)'}`",
        "- This artifact is not an actual reviewed signoff and does not allow runtime enablement.",
        "",
        "## Required Record Fields",
        "",
        "| Field | Required | Template value | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(scaffold.get("required_record_fields", [])):
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


def render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    scaffold = _mapping(report.get("signoff_record_scaffold"))
    pending_payload = _mapping(scaffold.get("pending_signoff_record_payload"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain signoff record scaffold",
            f"signoff_record_scaffold_ready={status.get('signoff_record_scaffold_ready')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            f"record_type={pending_payload.get('record_type')}",
            f"scope={pending_payload.get('scope')}",
            f"scaffold_notice={scaffold.get('scaffold_notice')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_signoff_record_scaffold",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_pending_signoff_record_payload(
    signoff_record_template: Mapping[str, Any],
    *,
    required_record_fields: list[Mapping[str, Any]],
    required_statement_ids: list[str],
    carry_forward_still_blocked_gate_ids: list[str],
) -> Dict[str, Any]:
    if not signoff_record_template and not required_record_fields:
        return {}
    payload: Dict[str, Any] = dict(signoff_record_template)
    for entry in required_record_fields:
        field = str(entry.get("field") or "").strip()
        if not field:
            continue
        payload[field] = entry.get("template_value")
    if required_statement_ids:
        payload["agreed_statement_ids"] = list(required_statement_ids)
    if carry_forward_still_blocked_gate_ids:
        payload["still_blocked_gate_ids"] = list(carry_forward_still_blocked_gate_ids)
    return payload


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

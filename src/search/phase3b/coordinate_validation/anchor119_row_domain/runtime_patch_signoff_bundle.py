from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

PATCH_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1"
)
RUNTIME_PATCH_PROPOSAL_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_v1"
)
RUNTIME_PATCH_STATUS_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
)
ENABLEMENT_GATE_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
DEFAULT_PATCH_REVIEW_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_20260424/"
    "anchor119_row_domain_guard_patch_review_bundle.json"
)
DEFAULT_RUNTIME_PATCH_PROPOSAL_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_20260424/"
    "anchor119_row_domain_runtime_patch_proposal.json"
)
DEFAULT_RUNTIME_PATCH_STATUS_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_20260424/"
    "anchor119_row_domain_runtime_patch_status.json"
)
DEFAULT_ENABLEMENT_GATE_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_20260424/"
    "anchor119_row_domain_enablement_gate_prep.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle(
    project_root: Path,
    *,
    patch_review_bundle_path: Optional[Path] = None,
    runtime_patch_proposal_path: Optional[Path] = None,
    runtime_patch_status_path: Optional[Path] = None,
    enablement_gate_prep_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    patch_review_bundle_resolved = _resolve_path(
        project_root,
        patch_review_bundle_path
        if patch_review_bundle_path is not None
        else DEFAULT_PATCH_REVIEW_BUNDLE_PATH,
    )
    runtime_patch_proposal_resolved = _resolve_path(
        project_root,
        runtime_patch_proposal_path
        if runtime_patch_proposal_path is not None
        else DEFAULT_RUNTIME_PATCH_PROPOSAL_PATH,
    )
    runtime_patch_status_resolved = _resolve_path(
        project_root,
        runtime_patch_status_path
        if runtime_patch_status_path is not None
        else DEFAULT_RUNTIME_PATCH_STATUS_PATH,
    )
    enablement_gate_prep_resolved = _resolve_path(
        project_root,
        enablement_gate_prep_path
        if enablement_gate_prep_path is not None
        else DEFAULT_ENABLEMENT_GATE_PREP_PATH,
    )

    patch_review_bundle_report, patch_review_bundle_error = _load_json_mapping(
        patch_review_bundle_resolved
    )
    runtime_patch_proposal_report, runtime_patch_proposal_error = _load_json_mapping(
        runtime_patch_proposal_resolved
    )
    runtime_patch_status_report, runtime_patch_status_error = _load_json_mapping(
        runtime_patch_status_resolved
    )
    enablement_gate_prep_report, enablement_gate_prep_error = _load_json_mapping(
        enablement_gate_prep_resolved
    )

    patch_review_meta = (
        _mapping(patch_review_bundle_report.get("metadata"))
        if patch_review_bundle_report
        else {}
    )
    patch_review_status = (
        _mapping(patch_review_bundle_report.get("status"))
        if patch_review_bundle_report
        else {}
    )
    review_bundle = (
        _mapping(patch_review_bundle_report.get("review_bundle"))
        if patch_review_bundle_report
        else {}
    )
    runtime_patch_proposal_meta = (
        _mapping(runtime_patch_proposal_report.get("metadata"))
        if runtime_patch_proposal_report
        else {}
    )
    runtime_patch_proposal_status = (
        _mapping(runtime_patch_proposal_report.get("status"))
        if runtime_patch_proposal_report
        else {}
    )
    runtime_patch_proposal = (
        _mapping(runtime_patch_proposal_report.get("proposal"))
        if runtime_patch_proposal_report
        else {}
    )
    runtime_patch_status_meta = (
        _mapping(runtime_patch_status_report.get("metadata"))
        if runtime_patch_status_report
        else {}
    )
    runtime_patch_status = (
        _mapping(runtime_patch_status_report.get("status"))
        if runtime_patch_status_report
        else {}
    )
    code_status = (
        _mapping(runtime_patch_status_report.get("code_status"))
        if runtime_patch_status_report
        else {}
    )
    enablement_gate_prep_meta = (
        _mapping(enablement_gate_prep_report.get("metadata"))
        if enablement_gate_prep_report
        else {}
    )
    enablement_gate_prep_status = (
        _mapping(enablement_gate_prep_report.get("status"))
        if enablement_gate_prep_report
        else {}
    )
    enablement_prep = (
        _mapping(enablement_gate_prep_report.get("enablement_prep"))
        if enablement_gate_prep_report
        else {}
    )
    candidate = (
        _mapping(enablement_gate_prep_report.get("candidate"))
        if enablement_gate_prep_report
        else _mapping(runtime_patch_status_report.get("candidate"))
        if runtime_patch_status_report
        else {}
    )

    patch_review_bundle_present = bool(
        patch_review_bundle_report is not None
        and patch_review_bundle_error is None
        and patch_review_meta.get("source") == PATCH_REVIEW_BUNDLE_SOURCE
    )
    runtime_patch_proposal_present = bool(
        runtime_patch_proposal_report is not None
        and runtime_patch_proposal_error is None
        and runtime_patch_proposal_meta.get("source") == RUNTIME_PATCH_PROPOSAL_SOURCE
    )
    runtime_patch_status_present = bool(
        runtime_patch_status_report is not None
        and runtime_patch_status_error is None
        and runtime_patch_status_meta.get("source") == RUNTIME_PATCH_STATUS_SOURCE
    )
    enablement_gate_prep_present = bool(
        enablement_gate_prep_report is not None
        and enablement_gate_prep_error is None
        and enablement_gate_prep_meta.get("source") == ENABLEMENT_GATE_PREP_SOURCE
    )

    review_ready = bool(patch_review_status.get("bundle_ready_for_review", False))
    proposal_ready = bool(
        runtime_patch_proposal_status.get("proposal_ready_for_review", False)
    )
    authored_but_not_enableable = bool(
        runtime_patch_status.get("authored_but_not_enableable", False)
    )
    enablement_prep_ready = bool(
        enablement_gate_prep_status.get("reviewed_enablement_gate_ready_for_review", False)
    )

    signoff_statements = [
        {
            "statement_id": "default_off_retained",
            "must_agree": True,
            "detail": "This patch remains disabled by default and does not enable runtime precheck in the shipped state.",
        },
        {
            "statement_id": "reserved_runtime_request_downgrades_to_advisory",
            "must_agree": True,
            "detail": "Reserved runtime requests still collapse back to advisory mode until a future reviewed enablement step clears the gates.",
        },
        {
            "statement_id": "no_proof_source_promotion",
            "must_agree": True,
            "detail": "The patch does not promote diagnostic evidence to proof_source and does not create a candidate elimination claim in the current shipped state.",
        },
        {
            "statement_id": "acceptance_refresh_required_before_enablement",
            "must_agree": True,
            "detail": "Any future enablement discussion requires a refreshed production-acceptance run on prod_4x4_normal after reviewed patch signoff.",
        },
    ]

    signoff_record_template = {
        "record_type": "reviewed_runtime_patch_signoff_record_v0",
        "reviewer_id": "",
        "reviewed_at": "",
        "verdict": "pending",
        "scope": runtime_patch_proposal.get("scope"),
        "notes": "",
        "agreed_statement_ids": [],
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
        ],
    }

    gates = [
        {
            "gate_id": "patch_review_bundle_ready",
            "satisfied": bool(review_ready),
            "blocking": not bool(review_ready),
            "detail": "Patch review bundle must already be review-ready.",
        },
        {
            "gate_id": "runtime_patch_proposal_ready",
            "satisfied": bool(proposal_ready),
            "blocking": not bool(proposal_ready),
            "detail": "Runtime patch proposal must already be ready for review.",
        },
        {
            "gate_id": "runtime_patch_authored_but_not_enableable",
            "satisfied": bool(authored_but_not_enableable),
            "blocking": not bool(authored_but_not_enableable),
            "detail": "The code path must be authored but still explicitly blocked from enablement.",
        },
        {
            "gate_id": "enablement_gate_prep_ready",
            "satisfied": bool(enablement_prep_ready),
            "blocking": not bool(enablement_prep_ready),
            "detail": "Enablement gate prep must already identify the locked production profile and acceptance command.",
        },
        {
            "gate_id": "reviewed_runtime_patch_exists",
            "satisfied": False,
            "blocking": True,
            "detail": "This bundle is for review/signoff preparation only; the reviewed runtime patch record does not exist yet.",
        },
        {
            "gate_id": "production_acceptance_refresh_completed",
            "satisfied": False,
            "blocking": True,
            "detail": "Production acceptance refresh still has not been run on prod_4x4_normal after reviewed signoff.",
        },
    ]

    checks = [
        _check(
            "patch_review_bundle_present",
            "pass" if patch_review_bundle_present else "fail",
            "patch review bundle loaded"
            if patch_review_bundle_present
            else patch_review_bundle_error
            or f"missing:{_display_path(project_root, patch_review_bundle_resolved)}",
        ),
        _check(
            "runtime_patch_proposal_present",
            "pass" if runtime_patch_proposal_present else "fail",
            "runtime patch proposal loaded"
            if runtime_patch_proposal_present
            else runtime_patch_proposal_error
            or f"missing:{_display_path(project_root, runtime_patch_proposal_resolved)}",
        ),
        _check(
            "runtime_patch_status_present",
            "pass" if runtime_patch_status_present else "fail",
            "runtime patch status loaded"
            if runtime_patch_status_present
            else runtime_patch_status_error
            or f"missing:{_display_path(project_root, runtime_patch_status_resolved)}",
        ),
        _check(
            "enablement_gate_prep_present",
            "pass" if enablement_gate_prep_present else "fail",
            "enablement gate prep loaded"
            if enablement_gate_prep_present
            else enablement_gate_prep_error
            or f"missing:{_display_path(project_root, enablement_gate_prep_resolved)}",
        ),
        _check("patch_review_bundle_ready", "pass" if review_ready else "fail", str(review_ready)),
        _check(
            "runtime_patch_proposal_ready",
            "pass" if proposal_ready else "fail",
            str(proposal_ready),
        ),
        _check(
            "authored_but_not_enableable",
            "pass" if authored_but_not_enableable else "fail",
            str(authored_but_not_enableable),
        ),
        _check(
            "enablement_gate_prep_ready",
            "pass" if enablement_prep_ready else "fail",
            str(enablement_prep_ready),
        ),
    ]

    signoff_bundle_ready = all(check["status"] == "pass" for check in checks)

    return {
        "metadata": {
            "source": RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_runtime_patch_signoff_bundle_not_runtime_enablement",
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
            "patch_review_bundle": _display_path(project_root, patch_review_bundle_resolved),
            "runtime_patch_proposal": _display_path(
                project_root, runtime_patch_proposal_resolved
            ),
            "runtime_patch_status": _display_path(
                project_root, runtime_patch_status_resolved
            ),
            "enablement_gate_prep": _display_path(
                project_root, enablement_gate_prep_resolved
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "signoff_bundle_ready": bool(signoff_bundle_ready),
            "reviewed_runtime_patch_signoff_ready_for_review": bool(signoff_bundle_ready),
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommended_next_step": "review_signoff_bundle_then_hold_for_acceptance_refresh",
            "recommendation": (
                "Signoff bundle is ready: collect reviewed patch signoff against the listed statements, then keep runtime disabled until production acceptance is refreshed on prod_4x4_normal."
                if signoff_bundle_ready
                else "Signoff bundle is blocked; repair the upstream review/proposal/status/prep artifacts first."
            ),
        },
        "signoff_bundle": {
            "guard_id": code_status.get("guard_id") or review_bundle.get("guard_id"),
            "payload_id": code_status.get("payload_id")
            or review_bundle.get("payload_id"),
            "scope": runtime_patch_proposal.get("scope") or review_bundle.get("scope"),
            "patch_review_targets": list(review_bundle.get("patch_review_targets", [])),
            "production_acceptance_command": enablement_prep.get(
                "production_acceptance_command"
            ),
            "required_reviewer_statements": signoff_statements,
            "signoff_record_template": signoff_record_template,
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("signoff_bundle"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Runtime Patch Signoff Bundle",
        "",
        f"- Signoff bundle ready: `{status.get('signoff_bundle_ready')}`",
        f"- Reviewed runtime patch signoff ready for review: `{status.get('reviewed_runtime_patch_signoff_ready_for_review')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Signoff Bundle",
        "",
        f"- Guard id: `{bundle.get('guard_id')}`",
        f"- Payload id: `{bundle.get('payload_id')}`",
        f"- Scope: `{bundle.get('scope')}`",
        f"- Production acceptance command: `{bundle.get('production_acceptance_command')}`",
        "",
        "## Required Reviewer Statements",
        "",
        "| Statement | Must agree | Detail |",
        "| --- | --- | --- |",
    ]
    for entry in list(bundle.get("required_reviewer_statements", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('statement_id'))} | "
                f"{_markdown_cell(entry.get('must_agree'))} | "
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


def render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("signoff_bundle"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain runtime patch signoff bundle",
            f"signoff_bundle_ready={status.get('signoff_bundle_ready')}",
            f"reviewed_runtime_patch_signoff_ready_for_review={status.get('reviewed_runtime_patch_signoff_ready_for_review')}",
            f"reviewed_runtime_patch_exists={status.get('reviewed_runtime_patch_exists')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"guard_id={bundle.get('guard_id')}",
            f"payload_id={bundle.get('payload_id')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_runtime_patch_signoff_bundle",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


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

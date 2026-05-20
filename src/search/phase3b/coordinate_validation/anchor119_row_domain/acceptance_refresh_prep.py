from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.operating_profile.operating_profile import (
    DEFAULT_PRODUCTION_PROFILE_ID,
    build_phase3b_operating_profile_summary,
)

SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
ENABLEMENT_GATE_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_v1"
)
ACCEPTANCE_REFRESH_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
)
REVIEW_STATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1"
)
DEFAULT_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)
DEFAULT_ENABLEMENT_GATE_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_20260424/"
    "anchor119_row_domain_enablement_gate_prep.json"
)
DEFAULT_ACCEPTANCE_OUTPUT_PATH = (
    ".codex_test_logs/phase3b/production_acceptance_after_change.json"
)
DEFAULT_REVIEW_STATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_review_state_20260425/"
    "anchor119_row_domain_review_state.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep(
    project_root: Path,
    *,
    signoff_bundle_path: Optional[Path] = None,
    enablement_gate_prep_path: Optional[Path] = None,
    review_state_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    signoff_bundle_resolved = _resolve_path(
        project_root,
        signoff_bundle_path if signoff_bundle_path is not None else DEFAULT_SIGNOFF_BUNDLE_PATH,
    )
    enablement_gate_prep_resolved = _resolve_path(
        project_root,
        enablement_gate_prep_path
        if enablement_gate_prep_path is not None
        else DEFAULT_ENABLEMENT_GATE_PREP_PATH,
    )
    review_state_resolved = _resolve_path(
        project_root,
        review_state_path if review_state_path is not None else DEFAULT_REVIEW_STATE_PATH,
    )

    signoff_bundle_report, signoff_bundle_error = _load_json_mapping(
        signoff_bundle_resolved
    )
    enablement_gate_prep_report, enablement_gate_prep_error = _load_json_mapping(
        enablement_gate_prep_resolved
    )
    review_state_report: Optional[Dict[str, Any]]
    review_state_error: Optional[str]
    if review_state_path is not None:
        review_state_report, review_state_error = _load_json_mapping(review_state_resolved)
    else:
        review_state_report, review_state_error = None, "not_provided"

    signoff_meta = (
        _mapping(signoff_bundle_report.get("metadata")) if signoff_bundle_report else {}
    )
    signoff_status = (
        _mapping(signoff_bundle_report.get("status")) if signoff_bundle_report else {}
    )
    signoff_bundle = (
        _mapping(signoff_bundle_report.get("signoff_bundle")) if signoff_bundle_report else {}
    )
    enablement_meta = (
        _mapping(enablement_gate_prep_report.get("metadata"))
        if enablement_gate_prep_report
        else {}
    )
    enablement_status = (
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
        else _mapping(signoff_bundle_report.get("candidate"))
        if signoff_bundle_report
        else {}
    )
    review_state_meta = (
        _mapping(review_state_report.get("metadata")) if review_state_report else {}
    )
    review_state_status = (
        _mapping(review_state_report.get("status")) if review_state_report else {}
    )

    signoff_bundle_present = bool(
        signoff_bundle_report is not None
        and signoff_bundle_error is None
        and signoff_meta.get("source") == SIGNOFF_BUNDLE_SOURCE
    )
    enablement_gate_prep_present = bool(
        enablement_gate_prep_report is not None
        and enablement_gate_prep_error is None
        and enablement_meta.get("source") == ENABLEMENT_GATE_PREP_SOURCE
    )
    review_state_present = bool(
        review_state_report is not None
        and review_state_error is None
        and review_state_meta.get("source") == REVIEW_STATE_SOURCE
    )
    review_state_valid = bool(
        review_state_present
        and review_state_status.get("review_state_ready", False)
        and review_state_status.get("repo_side_review_state_updated", False)
        and review_state_status.get("reviewed_runtime_patch_exists", False)
        and not review_state_status.get("runtime_enablement_allowed", False)
        and not review_state_status.get("production_acceptance_refresh_completed", False)
    )
    reviewed_runtime_patch_exists = bool(review_state_valid)
    signoff_bundle_ready = bool(signoff_status.get("signoff_bundle_ready", False))
    enablement_gate_ready = bool(
        enablement_status.get("reviewed_enablement_gate_ready_for_review", False)
    )

    operating_profile = build_phase3b_operating_profile_summary(project_root)
    defaults = _mapping(operating_profile.get("defaults"))
    policy = _mapping(operating_profile.get("policy"))
    profile_by_id = _mapping(operating_profile.get("profile_by_id"))
    production_profile = _mapping(profile_by_id.get(DEFAULT_PRODUCTION_PROFILE_ID))

    production_profile_locked = bool(
        defaults.get("production_profile_id") == DEFAULT_PRODUCTION_PROFILE_ID
        and production_profile.get("profile_id") == DEFAULT_PRODUCTION_PROFILE_ID
        and production_profile.get("parallel_processes") == 4
        and _mapping(production_profile.get("env")).get("EXACT_CP_SAT_WORKERS") == "4"
        and production_profile.get("process_priority") == "normal"
        and production_profile.get("frontier_probe_mode") == "auto"
    )
    acceptance_command = str(
        enablement_prep.get("production_acceptance_command")
        or policy.get("production_acceptance_command")
        or ""
    )

    validity_criteria = {
        "label": "prod_4x4",
        "completed": True,
        "return_code": 0,
        "campaign_valid_after_run": True,
        "duplicated_work": False,
    }

    gates = [
        {
            "gate_id": "signoff_bundle_ready",
            "satisfied": bool(signoff_bundle_ready),
            "blocking": not bool(signoff_bundle_ready),
            "detail": "Acceptance refresh prep assumes the runtime patch signoff bundle is already ready for review.",
        },
        {
            "gate_id": "enablement_gate_ready",
            "satisfied": bool(enablement_gate_ready),
            "blocking": not bool(enablement_gate_ready),
            "detail": "Enablement gate prep must already be ready so the production baseline and command are fixed.",
        },
        {
            "gate_id": "production_profile_locked_prod_4x4_normal",
            "satisfied": bool(production_profile_locked),
            "blocking": not bool(production_profile_locked),
            "detail": "Acceptance refresh must remain pinned to prod_4x4_normal.",
        },
        {
            "gate_id": "acceptance_command_present",
            "satisfied": bool(acceptance_command),
            "blocking": not bool(acceptance_command),
            "detail": "A concrete acceptance refresh command must be known.",
        },
        {
            "gate_id": "reviewed_runtime_patch_exists",
            "satisfied": bool(reviewed_runtime_patch_exists),
            "blocking": not bool(reviewed_runtime_patch_exists),
            "detail": (
                "Valid repo-side review-state artifact marks reviewed_runtime_patch_exists=true."
                if reviewed_runtime_patch_exists
                else "Acceptance refresh should not be treated as completed or promotable before a reviewed runtime patch signoff state marker exists."
            ),
        },
        {
            "gate_id": "production_acceptance_refresh_completed",
            "satisfied": False,
            "blocking": True,
            "detail": "The refreshed prod_4x4 acceptance run has not been executed yet.",
        },
    ]

    checks = [
        _check(
            "signoff_bundle_present",
            "pass" if signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if signoff_bundle_present
            else signoff_bundle_error
            or f"missing:{_display_path(project_root, signoff_bundle_resolved)}",
        ),
        _check(
            "enablement_gate_prep_present",
            "pass" if enablement_gate_prep_present else "fail",
            "enablement gate prep loaded"
            if enablement_gate_prep_present
            else enablement_gate_prep_error
            or f"missing:{_display_path(project_root, enablement_gate_prep_resolved)}",
        ),
        _check(
            "signoff_bundle_ready",
            "pass" if signoff_bundle_ready else "fail",
            str(signoff_bundle_ready),
        ),
        _check(
            "enablement_gate_ready",
            "pass" if enablement_gate_ready else "fail",
            str(enablement_gate_ready),
        ),
        _check(
            "production_profile_locked",
            "pass" if production_profile_locked else "fail",
            f"default_profile={defaults.get('production_profile_id')}",
        ),
        _check(
            "acceptance_command_present",
            "pass" if bool(acceptance_command) else "fail",
            acceptance_command or "missing",
        ),
    ]

    prep_ready = all(check["status"] == "pass" for check in checks)

    return {
        "metadata": {
            "source": ACCEPTANCE_REFRESH_PREP_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_acceptance_refresh_prep_not_runtime_enablement",
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
            "enablement_gate_prep": _display_path(
                project_root, enablement_gate_prep_resolved
            ),
            "review_state": _display_path(project_root, review_state_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_refresh_prep_ready": bool(prep_ready),
            "acceptance_refresh_ready_for_review": bool(prep_ready),
            "review_state_present": bool(review_state_present),
            "review_state_ready": bool(review_state_valid),
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "runtime_enablement_allowed": False,
            "recommended_next_step": (
                "run_prod_4x4_acceptance_refresh"
                if reviewed_runtime_patch_exists
                else "await_signoff_then_run_prod_4x4_acceptance_refresh"
            ),
            "recommendation": (
                "Acceptance refresh prep is explicit and the reviewed runtime patch marker is valid: the next gate is the locked prod_4x4 acceptance refresh, still with runtime_enablement_allowed=false."
                if prep_ready and reviewed_runtime_patch_exists
                else "Acceptance refresh prep is explicit: after reviewed signoff, run the locked prod_4x4 acceptance command and require the expected validity record before any enablement review."
                if prep_ready
                else "Acceptance refresh prep is incomplete; repair signoff/gate/profile prerequisites first."
            ),
        },
        "acceptance_refresh_prep": {
            "guard_id": signoff_bundle.get("guard_id"),
            "payload_id": signoff_bundle.get("payload_id"),
            "production_profile_id": DEFAULT_PRODUCTION_PROFILE_ID,
            "default_production_runner": str(policy.get("default_production_runner", "")),
            "acceptance_command": acceptance_command,
            "suite_output_path": DEFAULT_ACCEPTANCE_OUTPUT_PATH,
            "validity_criteria": validity_criteria,
            "required_sequence": [
                "reviewed_runtime_patch_signoff_record",
                "repo_side_review_state_marker",
                "run_prod_4x4_acceptance_refresh",
                "validate_prod_4x4_record_fields",
                "post_acceptance_enablement_review",
            ],
            "review_state": {
                "provided": bool(review_state_report is not None),
                "source": review_state_meta.get("source"),
                "ready": bool(review_state_valid),
                "error": review_state_error,
            },
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("acceptance_refresh_prep"))
    validity = _mapping(prep.get("validity_criteria"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Refresh Prep",
        "",
        f"- Acceptance refresh prep ready: `{status.get('acceptance_refresh_prep_ready')}`",
        f"- Acceptance refresh ready for review: `{status.get('acceptance_refresh_ready_for_review')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Acceptance Refresh Prep",
        "",
        f"- Guard id: `{prep.get('guard_id')}`",
        f"- Payload id: `{prep.get('payload_id')}`",
        f"- Production profile id: `{prep.get('production_profile_id')}`",
        f"- Default production runner: `{prep.get('default_production_runner')}`",
        f"- Acceptance command: `{prep.get('acceptance_command')}`",
        f"- Suite output path: `{prep.get('suite_output_path')}`",
        "",
        "## Validity Criteria",
        "",
        f"- Label: `{validity.get('label')}`",
        f"- Completed: `{validity.get('completed')}`",
        f"- Return code: `{validity.get('return_code')}`",
        f"- Campaign valid after run: `{validity.get('campaign_valid_after_run')}`",
        f"- Duplicated work: `{validity.get('duplicated_work')}`",
        "",
        "## Required Sequence",
        "",
    ]
    for step in list(prep.get("required_sequence", [])):
        lines.append(f"- `{step}`")
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("acceptance_refresh_prep"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance refresh prep",
            f"acceptance_refresh_prep_ready={status.get('acceptance_refresh_prep_ready')}",
            f"acceptance_refresh_ready_for_review={status.get('acceptance_refresh_ready_for_review')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"production_profile_id={prep.get('production_profile_id')}",
            f"suite_output_path={prep.get('suite_output_path')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_acceptance_refresh_prep",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_text(
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

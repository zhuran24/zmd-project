from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b_anchor119_guard_controls import (
    PHASE3B_ANCHOR119_ADVISORY_ENV,
    PHASE3B_ANCHOR119_GUARD_ID,
    PHASE3B_ANCHOR119_PAYLOAD_ID,
    build_phase3b_anchor119_guard_runtime_state,
)

CONTROL_SURFACE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_v1"
)
RUNTIME_PATCH_PROPOSAL_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_v1"
)
RUNTIME_PATCH_STATUS_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
)
DEFAULT_CONTROL_SURFACE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_20260424/"
    "anchor119_row_domain_guard_control_surface.json"
)
DEFAULT_RUNTIME_PATCH_PROPOSAL_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_20260424/"
    "anchor119_row_domain_runtime_patch_proposal.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status(
    project_root: Path,
    *,
    control_surface_path: Optional[Path] = None,
    runtime_patch_proposal_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    control_surface_resolved = _resolve_path(
        project_root,
        control_surface_path if control_surface_path is not None else DEFAULT_CONTROL_SURFACE_PATH,
    )
    runtime_patch_proposal_resolved = _resolve_path(
        project_root,
        runtime_patch_proposal_path
        if runtime_patch_proposal_path is not None
        else DEFAULT_RUNTIME_PATCH_PROPOSAL_PATH,
    )

    control_surface_report, control_surface_error = _load_json_mapping(
        control_surface_resolved
    )
    runtime_patch_proposal_report, runtime_patch_proposal_error = _load_json_mapping(
        runtime_patch_proposal_resolved
    )

    control_surface_meta = (
        _mapping(control_surface_report.get("metadata")) if control_surface_report else {}
    )
    (
        _mapping(control_surface_report.get("status")) if control_surface_report else {}
    )
    runtime_patch_meta = (
        _mapping(runtime_patch_proposal_report.get("metadata"))
        if runtime_patch_proposal_report
        else {}
    )
    runtime_patch_status = (
        _mapping(runtime_patch_proposal_report.get("status"))
        if runtime_patch_proposal_report
        else {}
    )
    candidate = (
        _mapping(runtime_patch_proposal_report.get("candidate"))
        if runtime_patch_proposal_report
        else _mapping(control_surface_report.get("candidate")) if control_surface_report else {}
    )

    control_surface_present = bool(
        control_surface_report is not None
        and control_surface_error is None
        and control_surface_meta.get("source") == CONTROL_SURFACE_SOURCE
    )
    runtime_patch_proposal_present = bool(
        runtime_patch_proposal_report is not None
        and runtime_patch_proposal_error is None
        and runtime_patch_meta.get("source") == RUNTIME_PATCH_PROPOSAL_SOURCE
    )
    proposal_ready_for_review = bool(
        runtime_patch_status.get("proposal_ready_for_review", False)
    )
    runtime_patch_authoring_allowed = bool(
        runtime_patch_status.get("runtime_patch_authoring_allowed", False)
    )
    runtime_enablement_allowed = bool(
        runtime_patch_status.get("runtime_enablement_allowed", False)
    )

    controls_module_path = Path(__file__).resolve().parent / "phase3b_anchor119_guard_controls.py"
    runtime_module_path = (
        Path(__file__).resolve().parent / "phase3b_anchor119_guarded_precheck_runtime.py"
    )
    benders_loop_path = Path(__file__).resolve().parent / "benders_loop.py"

    controls_text = controls_module_path.read_text(encoding="utf-8")
    runtime_module_text = runtime_module_path.read_text(encoding="utf-8")
    benders_text = benders_loop_path.read_text(encoding="utf-8")

    authored_target_files = [
        _target_entry(project_root, controls_module_path),
        _target_entry(project_root, runtime_module_path),
        _target_entry(project_root, benders_loop_path),
    ]

    reserved_runtime_request_shape = build_phase3b_anchor119_guard_runtime_state(
        advisory_env_raw="runtime"
    )
    reserved_runtime_request_downgrades_to_advisory = bool(
        reserved_runtime_request_shape.get("requested_state")
        == "runtime_enabled_reserved"
        and reserved_runtime_request_shape.get("effective_state") == "advisory_enabled"
        and reserved_runtime_request_shape.get("runtime_requested") is True
        and reserved_runtime_request_shape.get("runtime_precheck_enabled") is False
        and reserved_runtime_request_shape.get("runtime_activation_allowed") is False
    )

    marker_checks = [
        {
            "marker_id": "controls_runtime_request_values_present",
            "present": all(
                token in controls_text
                for token in [
                    "PHASE3B_ANCHOR119_RUNTIME_REQUEST_VALUES",
                    "runtime_enabled_reserved",
                    "runtime_requested",
                ]
            ),
            "file": _display_path(project_root, controls_module_path),
        },
        {
            "marker_id": "runtime_module_runtime_apply_branch_present",
            "present": all(
                token in runtime_module_text
                for token in [
                    "runtime_guard_reject_anchor119",
                    "anchor119_row_domain_runtime_guard",
                    "runtime_apply_enabled",
                ]
            ),
            "file": _display_path(project_root, runtime_module_path),
        },
        {
            "marker_id": "benders_pre_master_runtime_hook_present",
            "present": all(
                token in benders_text
                for token in [
                    "_maybe_build_anchor119_row_domain_runtime_precheck_result",
                    "apply_runtime_elimination",
                    "anchor119_row_domain_runtime_guard",
                ]
            ),
            "file": _display_path(project_root, benders_loop_path),
        },
    ]
    runtime_patch_authored_in_code = bool(
        reserved_runtime_request_downgrades_to_advisory
        and all(bool(entry.get("present", False)) for entry in marker_checks)
    )

    checks = [
        _check(
            "control_surface_present",
            "pass" if control_surface_present else "fail",
            "control surface artifact loaded"
            if control_surface_present
            else control_surface_error
            or f"missing:{_display_path(project_root, control_surface_resolved)}",
        ),
        _check(
            "runtime_patch_proposal_present",
            "pass" if runtime_patch_proposal_present else "fail",
            "runtime patch proposal artifact loaded"
            if runtime_patch_proposal_present
            else runtime_patch_proposal_error
            or f"missing:{_display_path(project_root, runtime_patch_proposal_resolved)}",
        ),
        _check(
            "proposal_ready_for_review",
            "pass" if proposal_ready_for_review else "fail",
            str(runtime_patch_status.get("proposal_ready_for_review")),
        ),
        _check(
            "runtime_patch_authoring_allowed",
            "pass" if runtime_patch_authoring_allowed else "fail",
            str(runtime_patch_status.get("runtime_patch_authoring_allowed")),
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_allowed is False else "fail",
            f"runtime_enablement_allowed={runtime_enablement_allowed}",
        ),
        _check(
            "reserved_runtime_request_downgrades_to_advisory",
            "pass" if reserved_runtime_request_downgrades_to_advisory else "fail",
            (
                "requested=runtime_enabled_reserved effective=advisory_enabled "
                "runtime_requested=true runtime_precheck_enabled=false "
                "runtime_activation_allowed=false"
            ),
        ),
        *[
            _check(
                str(entry.get("marker_id")),
                "pass" if bool(entry.get("present", False)) else "fail",
                str(entry.get("file")),
            )
            for entry in marker_checks
        ],
    ]

    patch_status_ready = all(check["status"] == "pass" for check in checks)

    return {
        "metadata": {
            "source": RUNTIME_PATCH_STATUS_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_runtime_patch_authored_but_not_enableable",
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
            "control_surface": _display_path(project_root, control_surface_resolved),
            "runtime_patch_proposal": _display_path(
                project_root, runtime_patch_proposal_resolved
            ),
            "controls_module": _display_path(project_root, controls_module_path),
            "runtime_module": _display_path(project_root, runtime_module_path),
            "benders_loop": _display_path(project_root, benders_loop_path),
        },
        "candidate": dict(candidate),
        "status": {
            "patch_status_ready": bool(patch_status_ready),
            "runtime_patch_authored_in_code": bool(runtime_patch_authored_in_code),
            "runtime_patch_authoring_allowed": bool(runtime_patch_authoring_allowed),
            "runtime_enablement_allowed": False,
            "authored_but_not_enableable": bool(
                runtime_patch_authored_in_code
                and runtime_patch_authoring_allowed
                and not runtime_enablement_allowed
            ),
            "current_phase": "disabled_runtime_patch_authored",
            "recommended_next_step": "keep_disabled_and_require_reviewed_enablement_gate",
            "recommendation": (
                "Runtime patch is now authored in code and backed by proposal/control artifacts, but enablement remains blocked; keep the shipped state disabled."
                if patch_status_ready
                else "Runtime patch status is incomplete; repair the missing proposal/control/code markers first."
            ),
        },
        "code_status": {
            "guard_id": PHASE3B_ANCHOR119_GUARD_ID,
            "payload_id": PHASE3B_ANCHOR119_PAYLOAD_ID,
            "advisory_env": PHASE3B_ANCHOR119_ADVISORY_ENV,
            "reserved_runtime_request_shape": {
                "requested_state": reserved_runtime_request_shape.get("requested_state"),
                "effective_state": reserved_runtime_request_shape.get("effective_state"),
                "runtime_requested": bool(
                    reserved_runtime_request_shape.get("runtime_requested", False)
                ),
                "runtime_precheck_enabled": bool(
                    reserved_runtime_request_shape.get("runtime_precheck_enabled", False)
                ),
                "runtime_activation_allowed": bool(
                    reserved_runtime_request_shape.get("runtime_activation_allowed", False)
                ),
            },
            "authored_target_files": authored_target_files,
            "marker_checks": marker_checks,
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    code_status = _mapping(report.get("code_status"))
    request_shape = _mapping(code_status.get("reserved_runtime_request_shape"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Runtime Patch Status",
        "",
        f"- Patch status ready: `{status.get('patch_status_ready')}`",
        f"- Runtime patch authored in code: `{status.get('runtime_patch_authored_in_code')}`",
        f"- Runtime patch authoring allowed: `{status.get('runtime_patch_authoring_allowed')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Authored but not enableable: `{status.get('authored_but_not_enableable')}`",
        f"- Current phase: `{status.get('current_phase')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Reserved Runtime Request Shape",
        "",
        f"- Requested state: `{request_shape.get('requested_state')}`",
        f"- Effective state: `{request_shape.get('effective_state')}`",
        f"- Runtime requested: `{request_shape.get('runtime_requested')}`",
        f"- Runtime precheck enabled: `{request_shape.get('runtime_precheck_enabled')}`",
        f"- Runtime activation allowed: `{request_shape.get('runtime_activation_allowed')}`",
        "",
        "## Authored Target Files",
        "",
        "| Path | Exists |",
        "| --- | --- |",
    ]
    for entry in list(code_status.get("authored_target_files", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('path'))} | {_markdown_cell(entry.get('exists'))} |"
            )
    lines.extend(
        [
            "",
            "## Marker Checks",
            "",
            "| Marker | Present | File |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(code_status.get("marker_checks", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('marker_id'))} | "
                f"{_markdown_cell(entry.get('present'))} | "
                f"{_markdown_cell(entry.get('file'))} |"
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


def render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    code_status = _mapping(report.get("code_status"))
    request_shape = _mapping(code_status.get("reserved_runtime_request_shape"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain runtime patch status",
            f"patch_status_ready={status.get('patch_status_ready')}",
            f"runtime_patch_authored_in_code={status.get('runtime_patch_authored_in_code')}",
            f"runtime_patch_authoring_allowed={status.get('runtime_patch_authoring_allowed')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"authored_but_not_enableable={status.get('authored_but_not_enableable')}",
            f"current_phase={status.get('current_phase')}",
            f"requested_state={request_shape.get('requested_state')}",
            f"effective_state={request_shape.get('effective_state')}",
            f"runtime_requested={request_shape.get('runtime_requested')}",
            f"runtime_precheck_enabled={request_shape.get('runtime_precheck_enabled')}",
            f"runtime_activation_allowed={request_shape.get('runtime_activation_allowed')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_runtime_patch_status",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _target_entry(project_root: Path, path: Path) -> Dict[str, Any]:
    return {
        "path": _display_path(project_root, path),
        "exists": bool(Path(path).exists()),
    }


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

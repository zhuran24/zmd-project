from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.operating_profile.operating_profile import (
    DEFAULT_PRODUCTION_PROFILE_ID,
    build_phase3b_operating_profile_summary,
)

RUNTIME_PATCH_STATUS_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
)
ENABLEMENT_GATE_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_v1"
)
DEFAULT_RUNTIME_PATCH_STATUS_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_20260424/"
    "anchor119_row_domain_runtime_patch_status.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep(
    project_root: Path,
    *,
    runtime_patch_status_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    runtime_patch_status_resolved = _resolve_path(
        project_root,
        runtime_patch_status_path
        if runtime_patch_status_path is not None
        else DEFAULT_RUNTIME_PATCH_STATUS_PATH,
    )

    runtime_patch_status_report, runtime_patch_status_error = _load_json_mapping(
        runtime_patch_status_resolved
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
    candidate = (
        _mapping(runtime_patch_status_report.get("candidate"))
        if runtime_patch_status_report
        else {}
    )

    runtime_patch_status_present = bool(
        runtime_patch_status_report is not None
        and runtime_patch_status_error is None
        and runtime_patch_status_meta.get("source") == RUNTIME_PATCH_STATUS_SOURCE
    )
    patch_status_ready = bool(runtime_patch_status.get("patch_status_ready", False))
    runtime_patch_authored_in_code = bool(
        runtime_patch_status.get("runtime_patch_authored_in_code", False)
    )
    authored_but_not_enableable = bool(
        runtime_patch_status.get("authored_but_not_enableable", False)
    )

    operating_profile = build_phase3b_operating_profile_summary(project_root)
    defaults = _mapping(operating_profile.get("defaults"))
    policy = _mapping(operating_profile.get("policy"))
    profile_by_id = _mapping(operating_profile.get("profile_by_id"))
    production_profile = _mapping(profile_by_id.get(DEFAULT_PRODUCTION_PROFILE_ID))

    production_acceptance_command = str(policy.get("production_acceptance_command", ""))
    default_production_runner = str(policy.get("default_production_runner", ""))
    production_profile_locked = bool(
        defaults.get("production_profile_id") == DEFAULT_PRODUCTION_PROFILE_ID
        and production_profile.get("profile_id") == DEFAULT_PRODUCTION_PROFILE_ID
        and production_profile.get("parallel_processes") == 4
        and _mapping(production_profile.get("env")).get("EXACT_CP_SAT_WORKERS") == "4"
        and production_profile.get("process_priority") == "normal"
        and production_profile.get("frontier_probe_mode") == "auto"
    )

    gates = [
        {
            "gate_id": "runtime_patch_status_ready",
            "satisfied": bool(patch_status_ready),
            "blocking": not bool(patch_status_ready),
            "detail": "Runtime patch status artifact must be ready before enablement prep is meaningful.",
        },
        {
            "gate_id": "runtime_patch_authored_in_code",
            "satisfied": bool(runtime_patch_authored_in_code),
            "blocking": not bool(runtime_patch_authored_in_code),
            "detail": "The reviewed runtime patch path must already exist in code before any enablement review.",
        },
        {
            "gate_id": "reviewed_runtime_patch_exists",
            "satisfied": False,
            "blocking": True,
            "detail": "A separately reviewed runtime patch approval record does not exist yet.",
        },
        {
            "gate_id": "production_profile_locked_prod_4x4_normal",
            "satisfied": bool(production_profile_locked),
            "blocking": not bool(production_profile_locked),
            "detail": "Enablement discussion should continue against the locked prod_4x4_normal baseline.",
        },
        {
            "gate_id": "production_acceptance_refresh_prepared",
            "satisfied": bool(production_acceptance_command),
            "blocking": not bool(production_acceptance_command),
            "detail": "Acceptance-refresh command should be known before any reviewed enablement plan is drafted.",
        },
        {
            "gate_id": "production_acceptance_refresh_completed",
            "satisfied": False,
            "blocking": True,
            "detail": "Refreshed production-acceptance evidence does not exist yet.",
        },
        {
            "gate_id": "proof_source_promotion_still_forbidden",
            "satisfied": True,
            "blocking": False,
            "detail": "Runtime enablement prep must not be treated as proof-source promotion.",
        },
    ]

    checks = [
        _check(
            "runtime_patch_status_present",
            "pass" if runtime_patch_status_present else "fail",
            "runtime patch status artifact loaded"
            if runtime_patch_status_present
            else runtime_patch_status_error
            or f"missing:{_display_path(project_root, runtime_patch_status_resolved)}",
        ),
        _check(
            "patch_status_ready",
            "pass" if patch_status_ready else "fail",
            str(runtime_patch_status.get("patch_status_ready")),
        ),
        _check(
            "runtime_patch_authored_in_code",
            "pass" if runtime_patch_authored_in_code else "fail",
            str(runtime_patch_status.get("runtime_patch_authored_in_code")),
        ),
        _check(
            "authored_but_not_enableable",
            "pass" if authored_but_not_enableable else "fail",
            str(runtime_patch_status.get("authored_but_not_enableable")),
        ),
        _check(
            "production_profile_locked",
            "pass" if production_profile_locked else "fail",
            f"default_profile={defaults.get('production_profile_id')}",
        ),
        _check(
            "production_acceptance_command_present",
            "pass" if bool(production_acceptance_command) else "fail",
            production_acceptance_command or "missing",
        ),
    ]

    prep_ready = all(check["status"] == "pass" for check in checks)

    return {
        "metadata": {
            "source": ENABLEMENT_GATE_PREP_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_enablement_gate_prep_not_runtime_enablement",
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
            "runtime_patch_status": _display_path(project_root, runtime_patch_status_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "prep_ready": bool(prep_ready),
            "reviewed_enablement_gate_ready_for_review": bool(prep_ready),
            "runtime_enablement_allowed": False,
            "recommended_next_step": "review_runtime_patch_then_refresh_production_acceptance",
            "recommendation": (
                "Enablement prep is now explicit: keep runtime disabled, obtain a reviewed patch signoff, then refresh production acceptance on prod_4x4_normal before any activation discussion."
                if prep_ready
                else "Enablement prep is incomplete; repair the missing status or production-profile prerequisites first."
            ),
        },
        "enablement_prep": {
            "guard_id": code_status.get("guard_id"),
            "payload_id": code_status.get("payload_id"),
            "current_phase": runtime_patch_status.get("current_phase"),
            "production_profile_id": DEFAULT_PRODUCTION_PROFILE_ID,
            "production_profile_locked": bool(production_profile_locked),
            "default_production_runner": default_production_runner,
            "production_acceptance_command": production_acceptance_command,
            "required_sequence": [
                "reviewed_runtime_patch_signoff",
                "production_acceptance_refresh_on_prod_4x4_normal",
                "post_acceptance_enablement_review",
            ],
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("enablement_prep"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Enablement Gate Prep",
        "",
        f"- Prep ready: `{status.get('prep_ready')}`",
        f"- Reviewed enablement gate ready for review: `{status.get('reviewed_enablement_gate_ready_for_review')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Enablement Prep",
        "",
        f"- Guard id: `{prep.get('guard_id')}`",
        f"- Payload id: `{prep.get('payload_id')}`",
        f"- Current phase: `{prep.get('current_phase')}`",
        f"- Production profile id: `{prep.get('production_profile_id')}`",
        f"- Production profile locked: `{prep.get('production_profile_locked')}`",
        f"- Default production runner: `{prep.get('default_production_runner')}`",
        f"- Production acceptance command: `{prep.get('production_acceptance_command')}`",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("enablement_prep"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain enablement gate prep",
            f"prep_ready={status.get('prep_ready')}",
            f"reviewed_enablement_gate_ready_for_review={status.get('reviewed_enablement_gate_ready_for_review')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"production_profile_id={prep.get('production_profile_id')}",
            f"production_profile_locked={prep.get('production_profile_locked')}",
            f"production_acceptance_command={prep.get('production_acceptance_command')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_enablement_gate_prep",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_text(
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

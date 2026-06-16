from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.anchor119.guard_controls import (
    PHASE3B_ANCHOR119_DEFAULT_STATE,
    PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
    PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED,
    phase3b_anchor119_guard_candidate_scope,
)

CONTROL_SURFACE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_v1"
)
PATCH_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1"
)
RUNTIME_PATCH_PROPOSAL_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_v1"
)
DEFAULT_CONTROL_SURFACE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_20260424/"
    "anchor119_row_domain_guard_control_surface.json"
)
DEFAULT_PATCH_REVIEW_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_20260424/"
    "anchor119_row_domain_guard_patch_review_bundle.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal(
    project_root: Path,
    *,
    control_surface_path: Optional[Path] = None,
    patch_review_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    control_surface_resolved = _resolve_path(
        project_root,
        control_surface_path if control_surface_path is not None else DEFAULT_CONTROL_SURFACE_PATH,
    )
    patch_review_bundle_resolved = _resolve_path(
        project_root,
        patch_review_bundle_path
        if patch_review_bundle_path is not None
        else DEFAULT_PATCH_REVIEW_BUNDLE_PATH,
    )

    control_surface_report, control_surface_error = _load_json_mapping(
        control_surface_resolved
    )
    patch_review_bundle_report, patch_review_bundle_error = _load_json_mapping(
        patch_review_bundle_resolved
    )

    control_surface_meta = (
        _mapping(control_surface_report.get("metadata")) if control_surface_report else {}
    )
    control_surface_status = (
        _mapping(control_surface_report.get("status")) if control_surface_report else {}
    )
    control_surface = (
        _mapping(control_surface_report.get("control_surface"))
        if control_surface_report
        else {}
    )
    activation_gates = [
        dict(entry)
        for entry in list(
            control_surface_report.get("activation_gates", []) if control_surface_report else []
        )
        if isinstance(entry, Mapping)
    ]

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
    candidate = _mapping(control_surface_report.get("candidate")) if control_surface_report else {}

    control_surface_present = bool(
        control_surface_report is not None
        and control_surface_error is None
        and control_surface_meta.get("source") == CONTROL_SURFACE_SOURCE
    )
    patch_review_present = bool(
        patch_review_bundle_report is not None
        and patch_review_bundle_error is None
        and patch_review_meta.get("source") == PATCH_REVIEW_BUNDLE_SOURCE
    )
    control_surface_ready = bool(control_surface_status.get("control_surface_ready", False))
    patch_review_ready = bool(patch_review_status.get("bundle_ready_for_review", False))
    runtime_activation_allowed = bool(
        control_surface_status.get("runtime_activation_allowed", False)
    )

    patch_targets = [
        dict(entry)
        for entry in list(review_bundle.get("patch_review_targets", []))
        if isinstance(entry, Mapping)
    ]

    proposal_ready = bool(control_surface_present and patch_review_present and control_surface_ready and patch_review_ready)
    proposal = {
        "proposal_id": "anchor119_row_domain_runtime_patch_proposal_v0",
        "guard_id": control_surface.get("guard_id"),
        "payload_id": control_surface.get("payload_id"),
        "scope": review_bundle.get("scope"),
        "target_files": patch_targets,
        "runtime_shape": {
            "default_state": PHASE3B_ANCHOR119_DEFAULT_STATE,
            "advisory_mode_retained": True,
            "future_runtime_mode_reserved": True,
            "candidate_scope_fixed": phase3b_anchor119_guard_candidate_scope(),
        },
        "non_goals": [
            "Do not enable runtime_precheck in this proposal artifact.",
            "Do not claim proof_source promotion.",
            "Do not treat advisory evidence as campaign proof.",
            "Do not authorize 168h long-run launch.",
        ],
        "review_requirements": [
            "separate reviewed runtime patch exists",
            "acceptance refresh after any runtime-facing code change",
            "control-surface gates explicitly satisfied",
            "default-off remains the shipped state until acceptance closes",
        ],
        "rollout_plan": [
            {
                "phase": "review_only",
                "allowed": True,
                "detail": f"Keep current {PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED}/{PHASE3B_ANCHOR119_DEFAULT_STATE} shape and use it only for diagnostics.",
            },
            {
                "phase": "patch_authoring",
                "allowed": bool(proposal_ready),
                "detail": "Author a narrowly scoped reviewed runtime patch, but keep it disabled by default.",
            },
            {
                "phase": "runtime_enablement",
                "allowed": False,
                "detail": f"Blocked until a reviewed patch exists, acceptance is refreshed, activation gates are cleared, and {PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED} can be promoted safely.",
            },
        ],
    }

    checks = [
        _check(
            "control_surface_present",
            "pass" if control_surface_present else "fail",
            "control surface artifact loaded"
            if control_surface_present
            else control_surface_error or f"missing:{_display_path(project_root, control_surface_resolved)}",
        ),
        _check(
            "patch_review_bundle_present",
            "pass" if patch_review_present else "fail",
            "patch review bundle loaded"
            if patch_review_present
            else patch_review_bundle_error
            or f"missing:{_display_path(project_root, patch_review_bundle_resolved)}",
        ),
        _check(
            "control_surface_ready",
            "pass" if control_surface_ready else "fail",
            str(control_surface_status.get("control_surface_ready")),
        ),
        _check(
            "patch_review_bundle_ready",
            "pass" if patch_review_ready else "fail",
            str(patch_review_status.get("bundle_ready_for_review")),
        ),
        _check(
            "runtime_activation_still_blocked",
            "pass" if runtime_activation_allowed is False else "fail",
            f"runtime_activation_allowed={runtime_activation_allowed}",
        ),
    ]

    return {
        "metadata": {
            "source": RUNTIME_PATCH_PROPOSAL_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_row_domain_runtime_patch_proposal_not_runtime_patch",
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
            "patch_review_bundle": _display_path(project_root, patch_review_bundle_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "proposal_ready_for_review": bool(proposal_ready),
            "runtime_patch_authoring_allowed": bool(proposal_ready),
            "runtime_enablement_allowed": False,
            "recommended_next_step": "keep_disabled_and_require_reviewed_runtime_patch",
            "recommendation": (
                "Runtime patch proposal is explicit: a reviewed patch may be authored as a separate step, but runtime enablement remains blocked until acceptance evidence and activation gates are cleared."
                if proposal_ready
                else "Runtime patch proposal is blocked; repair the control surface or patch-review bundle first."
            ),
        },
        "proposal": proposal,
        "activation_gates": activation_gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    proposal = _mapping(report.get("proposal"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Runtime Patch Proposal",
        "",
        f"- Proposal ready for review: `{status.get('proposal_ready_for_review')}`",
        f"- Runtime patch authoring allowed: `{status.get('runtime_patch_authoring_allowed')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Proposal",
        "",
        f"- Proposal id: `{proposal.get('proposal_id')}`",
        f"- Guard id: `{proposal.get('guard_id')}`",
        f"- Payload id: `{proposal.get('payload_id')}`",
        f"- Scope: `{proposal.get('scope')}`",
        "",
        "## Rollout Plan",
        "",
        "| Phase | Allowed | Detail |",
        "| --- | --- | --- |",
    ]
    for entry in list(proposal.get("rollout_plan", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('phase'))} | "
                f"{_markdown_cell(entry.get('allowed'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
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


def render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    proposal = _mapping(report.get("proposal"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain runtime patch proposal",
            f"proposal_ready_for_review={status.get('proposal_ready_for_review')}",
            f"runtime_patch_authoring_allowed={status.get('runtime_patch_authoring_allowed')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"proposal_id={proposal.get('proposal_id')}",
            f"guard_id={proposal.get('guard_id')}",
            f"payload_id={proposal.get('payload_id')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_runtime_patch_proposal",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_text(
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
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
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

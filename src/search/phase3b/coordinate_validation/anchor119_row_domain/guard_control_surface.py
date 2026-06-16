from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.anchor119.guard_controls import (
    PHASE3B_ANCHOR119_ADVISORY_ENV,
    PHASE3B_ANCHOR119_DEFAULT_STATE,
    PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
    PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED,
)

ANCHOR119_ROW_DOMAIN_GUARD_CONTROL_SURFACE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_v1"
)
ANCHOR119_ROW_DOMAIN_GUARD_PATCH_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1"
)
DEFAULT_PATCH_REVIEW_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_20260424/"
    "anchor119_row_domain_guard_patch_review_bundle.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface(
    project_root: Path,
    *,
    patch_review_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    bundle_resolved = _resolve_path(
        project_root,
        patch_review_bundle_path
        if patch_review_bundle_path is not None
        else DEFAULT_PATCH_REVIEW_BUNDLE_PATH,
    )

    bundle_report, bundle_error = _load_json_mapping(bundle_resolved)
    bundle_meta = _mapping(bundle_report.get("metadata")) if bundle_report else {}
    bundle_status = _mapping(bundle_report.get("status")) if bundle_report else {}
    review_bundle = _mapping(bundle_report.get("review_bundle")) if bundle_report else {}
    evidence = _mapping(bundle_report.get("evidence")) if bundle_report else {}
    candidate = _mapping(bundle_report.get("candidate")) if bundle_report else {}

    bundle_present = bool(
        bundle_report is not None
        and bundle_error is None
        and bundle_meta.get("source") == ANCHOR119_ROW_DOMAIN_GUARD_PATCH_REVIEW_BUNDLE_SOURCE
    )
    bundle_ready_for_review = bool(bundle_status.get("bundle_ready_for_review", False))
    runtime_patch_ready = bool(bundle_status.get("runtime_patch_ready", False))
    review_targets = [
        dict(entry)
        for entry in list(review_bundle.get("patch_review_targets", []))
        if isinstance(entry, Mapping)
    ]
    all_targets_exist = bool(review_targets) and all(
        bool(entry.get("exists", False)) for entry in review_targets
    )

    activation_gates = [
        {
            "gate_id": "patch_review_bundle_ready",
            "satisfied": bool(bundle_ready_for_review),
            "blocking": not bool(bundle_ready_for_review),
            "detail": "Patch-review bundle must be review-ready before any activation discussion.",
        },
        {
            "gate_id": "patch_targets_present",
            "satisfied": bool(all_targets_exist),
            "blocking": not bool(all_targets_exist),
            "detail": "Target files listed by the review bundle must still exist.",
        },
        {
            "gate_id": "reviewed_runtime_patch_exists",
            "satisfied": bool(runtime_patch_ready),
            "blocking": True,
            "detail": "No reviewed runtime patch is approved yet; current artifact is still review scaffolding.",
        },
        {
            "gate_id": "production_acceptance_refresh_required",
            "satisfied": False,
            "blocking": True,
            "detail": "Any future runtime enablement still requires refreshed production-acceptance evidence.",
        },
        {
            "gate_id": "proof_source_promotion_forbidden",
            "satisfied": False,
            "blocking": True,
            "detail": "Current line remains advisory-only, proof_source=false, candidate_elimination_claim=false.",
        },
    ]
    runtime_activation_allowed = all(
        bool(gate.get("satisfied", False)) or not bool(gate.get("blocking", False))
        for gate in activation_gates
    )

    control_surface = {
        "guard_id": review_bundle.get("guard_id"),
        "payload_id": review_bundle.get("payload_id"),
        "default_state": PHASE3B_ANCHOR119_DEFAULT_STATE,
        "current_mode": "default_off_advisory_only",
        "advisory_env": {
            "name": PHASE3B_ANCHOR119_ADVISORY_ENV,
            "truthy_values": ["1", "true", "yes", "on"],
            "when_enabled": "report would_trigger only; do not change triggered/status",
        },
        "allowed_states": [
            {
                "state_id": "disabled",
                "allowed_now": True,
                "runtime_precheck_enabled": False,
                "advisory_only": True,
                "candidate_elimination_claim": False,
                "proof_source": False,
                "entry_condition": "default state with advisory env unset",
            },
            {
                "state_id": PHASE3B_ANCHOR119_STATE_ADVISORY_ENABLED,
                "allowed_now": True,
                "runtime_precheck_enabled": False,
                "advisory_only": True,
                "candidate_elimination_claim": False,
                "proof_source": False,
                "entry_condition": f"set {PHASE3B_ANCHOR119_ADVISORY_ENV} to a truthy value",
            },
            {
                "state_id": PHASE3B_ANCHOR119_STATE_RUNTIME_ENABLED_RESERVED,
                "allowed_now": False,
                "runtime_precheck_enabled": True,
                "advisory_only": False,
                "would_be_candidate_elimination_claim": True,
                "would_be_proof_source": True,
                "entry_condition": "reserved for a future separately reviewed patch and acceptance cycle",
            },
        ],
        "locked_boundaries": {
            "non_trigger_max_slot_count": evidence.get("non_trigger_max_slot_count"),
            "anchored_trigger_min_slot_count": evidence.get(
                "anchored_trigger_min_slot_count"
            ),
            "free_ghost_trigger_min_slot_count": evidence.get(
                "free_ghost_trigger_min_slot_count"
            ),
        },
    }

    checks = [
        _check(
            "patch_review_bundle_present",
            "pass" if bundle_present else "fail",
            "anchor119 row-domain guard patch review bundle loaded"
            if bundle_present
            else bundle_error or f"missing:{_display_path(project_root, bundle_resolved)}",
        ),
        _check(
            "patch_review_bundle_ready",
            "pass" if bundle_ready_for_review else "fail",
            str(bundle_status.get("bundle_ready_for_review")),
        ),
        _check(
            "review_targets_present",
            "pass" if all_targets_exist else "fail",
            f"target_count={len(review_targets)} all_exist={all_targets_exist}",
        ),
        _check(
            "default_state_disabled",
            "pass" if control_surface.get("default_state") == "disabled" else "fail",
            f"default_state={control_surface.get('default_state')}",
        ),
        _check(
            "runtime_activation_blocked",
            "pass" if runtime_activation_allowed is False else "fail",
            f"runtime_activation_allowed={runtime_activation_allowed}",
        ),
        _check(
            "advisory_env_declared",
            "pass"
            if control_surface.get("advisory_env", {}).get("name")
            == PHASE3B_ANCHOR119_ADVISORY_ENV
            else "fail",
            str(control_surface.get("advisory_env", {}).get("name")),
        ),
    ]

    return {
        "metadata": {
            "source": ANCHOR119_ROW_DOMAIN_GUARD_CONTROL_SURFACE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_row_domain_guard_control_surface_not_runtime_patch",
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
            "patch_review_bundle": _display_path(project_root, bundle_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "control_surface_ready": bool(bundle_present and bundle_ready_for_review),
            "current_mode": "default_off_advisory_only",
            "runtime_activation_allowed": bool(runtime_activation_allowed),
            "recommended_next_step": (
                "hold_default_off_until_reviewed_runtime_patch_and_acceptance"
            ),
            "recommendation": (
                "Control surface is explicit: keep the guard disabled by default, use advisory mode only for diagnostics, and do not discuss runtime enablement until a reviewed patch and refreshed acceptance evidence exist."
                if bundle_present and bundle_ready_for_review
                else "Control surface is blocked; repair the patch-review bundle first."
            ),
        },
        "control_surface": control_surface,
        "activation_gates": activation_gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    surface = _mapping(report.get("control_surface"))
    locked = _mapping(surface.get("locked_boundaries"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Guard Control Surface",
        "",
        f"- Control surface ready: `{status.get('control_surface_ready')}`",
        f"- Current mode: `{status.get('current_mode')}`",
        f"- Runtime activation allowed: `{status.get('runtime_activation_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Control Surface",
        "",
        f"- Guard id: `{surface.get('guard_id')}`",
        f"- Payload id: `{surface.get('payload_id')}`",
        f"- Default state: `{surface.get('default_state')}`",
        f"- Advisory env: `{_mapping(surface.get('advisory_env')).get('name')}`",
        "",
        "## Locked Boundaries",
        "",
        f"- Non-trigger max slot count: `{locked.get('non_trigger_max_slot_count')}`",
        f"- Anchored trigger min slot count: `{locked.get('anchored_trigger_min_slot_count')}`",
        f"- Free-ghost trigger min slot count: `{locked.get('free_ghost_trigger_min_slot_count')}`",
        "",
        "## Allowed States",
        "",
        "| State | Allowed now | Runtime precheck enabled | Advisory only |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(surface.get("allowed_states", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('state_id'))} | "
                f"{_markdown_cell(entry.get('allowed_now'))} | "
                f"{_markdown_cell(entry.get('runtime_precheck_enabled'))} | "
                f"{_markdown_cell(entry.get('advisory_only'))} |"
            )
    lines.extend(
        [
            "",
            "## Activation Gates",
            "",
            "| Gate | Satisfied | Blocking | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for gate in list(report.get("activation_gates", [])):
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


def render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    surface = _mapping(report.get("control_surface"))
    locked = _mapping(surface.get("locked_boundaries"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain guard control surface",
            f"control_surface_ready={status.get('control_surface_ready')}",
            f"current_mode={status.get('current_mode')}",
            f"runtime_activation_allowed={status.get('runtime_activation_allowed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"guard_id={surface.get('guard_id')}",
            f"payload_id={surface.get('payload_id')}",
            f"advisory_env={_mapping(surface.get('advisory_env')).get('name')}",
            f"non_trigger_max_slot_count={locked.get('non_trigger_max_slot_count')}",
            f"anchored_trigger_min_slot_count={locked.get('anchored_trigger_min_slot_count')}",
            f"free_ghost_trigger_min_slot_count={locked.get('free_ghost_trigger_min_slot_count')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_guard_control_surface",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_text(
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

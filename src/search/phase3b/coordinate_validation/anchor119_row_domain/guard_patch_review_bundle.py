from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

ANCHOR119_ROW_DOMAIN_GUARD_PATCH_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1"
)
ANCHOR119_ROW_DOMAIN_GUARD_SPEC_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_guard_spec_v1"
)

DEFAULT_GUARD_SPEC_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_spec_20260424/"
    "anchor119_row_domain_guard_spec.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle(
    project_root: Path,
    *,
    guard_spec_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    spec_resolved = _resolve_path(
        project_root,
        guard_spec_path if guard_spec_path is not None else DEFAULT_GUARD_SPEC_PATH,
    )

    spec_report, spec_error = _load_json_mapping(spec_resolved)
    spec_meta = _mapping(spec_report.get("metadata")) if spec_report else {}
    spec_status = _mapping(spec_report.get("status")) if spec_report else {}
    proposed_guard = _mapping(spec_report.get("proposed_guard")) if spec_report else {}
    evidence = _mapping(spec_report.get("evidence")) if spec_report else {}
    candidate = _mapping(spec_report.get("candidate")) if spec_report else {}

    spec_present = bool(
        spec_report is not None
        and spec_error is None
        and spec_meta.get("source") == ANCHOR119_ROW_DOMAIN_GUARD_SPEC_SOURCE
    )
    spec_ready = (
        spec_status.get("outcome") == "anchor119_row_domain_guard_spec_ready_for_review"
        and bool(spec_status.get("all_gates_pass", False))
    )

    patch_targets = [
        str(path)
        for path in list(proposed_guard.get("patch_review_targets", []))
        if str(path).strip()
    ]
    target_entries = []
    for relative_path in patch_targets:
        absolute = (project_root / relative_path).resolve()
        target_entries.append(
            {
                "path": relative_path.replace("\\", "/"),
                "exists": absolute.exists(),
            }
        )
    all_targets_exist = bool(target_entries) and all(entry["exists"] for entry in target_entries)

    bundle_ready_for_review = bool(spec_present and spec_ready and all_targets_exist)

    invariants = [
        {
            "invariant_id": "default_off_retained",
            "detail": "Guard default state must remain disabled.",
        },
        {
            "invariant_id": "advisory_only_retained",
            "detail": "Runtime helper may report would_trigger but must not return triggered=True.",
        },
        {
            "invariant_id": "runtime_semantics_unchanged",
            "detail": "No runtime precheck enablement, no candidate elimination claim, no proof-source promotion.",
        },
        {
            "invariant_id": "boundary_controls_locked",
            "detail": "Keep non-trigger max=13, anchored trigger min=14, free-ghost trigger min=15.",
        },
    ]

    test_plan = [
        {
            "command": (
                "python -m pytest -q "
                "src\\tests\\test_phase3b_anchor119_guarded_precheck_spec.py "
                "src\\tests\\test_phase3b_anchor119_guarded_precheck_runtime.py"
            ),
            "reason": "baseline guard family remains advisory/default-off",
        },
        {
            "command": (
                "python -m pytest -q "
                "src\\tests\\test_phase3b_coordinate_validation_anchor119_row_domain_guard_spec.py "
                "src\\tests\\test_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate.py "
                "src\\tests\\test_phase3b_coordinate_validation_row_domain_count_witness_payload.py"
            ),
            "reason": "row-domain bridge chain remains aligned",
        },
    ]

    checks = [
        _check(
            "guard_spec_present",
            "pass" if spec_present else "fail",
            "anchor119 row-domain guard spec loaded"
            if spec_present
            else spec_error or f"missing:{_display_path(project_root, spec_resolved)}",
        ),
        _check(
            "guard_spec_ready_for_review",
            "pass" if spec_ready else "fail",
            str(spec_status.get("outcome") or "guard spec not ready"),
        ),
        _check(
            "patch_review_targets_exist",
            "pass" if all_targets_exist else "fail",
            f"target_count={len(target_entries)} all_exist={all_targets_exist}",
        ),
        _check(
            "default_off_invariant_present",
            "pass" if proposed_guard.get("default_state") == "disabled" else "fail",
            f"default_state={proposed_guard.get('default_state')}",
        ),
        _check(
            "advisory_only_invariant_present",
            "pass" if proposed_guard.get("advisory_only") is True else "fail",
            f"advisory_only={proposed_guard.get('advisory_only')}",
        ),
        _check(
            "runtime_boundaries_present",
            "pass"
            if (
                spec_meta.get("runtime_precheck_enabled") is False
                and spec_meta.get("runtime_semantics_changed") is False
                and spec_meta.get("proof_source") is False
            )
            else "fail",
            (
                f"runtime_precheck_enabled={spec_meta.get('runtime_precheck_enabled')} "
                f"runtime_semantics_changed={spec_meta.get('runtime_semantics_changed')} "
                f"proof_source={spec_meta.get('proof_source')}"
            ),
        ),
        _check(
            "runtime_patch_guard",
            "fail",
            (
                "patch-review bundle is review scaffolding only; do not treat it as an approved "
                "runtime change until a separate reviewed patch is produced and verified"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ANCHOR119_ROW_DOMAIN_GUARD_PATCH_REVIEW_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_row_domain_guard_patch_review_bundle_not_runtime_patch",
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
            "guard_spec": _display_path(project_root, spec_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "bundle_ready_for_review": bool(bundle_ready_for_review),
            "runtime_patch_ready": False,
            "recommended_next_step": "author_default_off_guard_patch",
            "recommendation": (
                "Patch-review bundle is ready: author a narrowly scoped default-off patch against the listed targets, preserving advisory-only behavior and existing boundaries."
                if bundle_ready_for_review
                else "Patch-review bundle is blocked; repair guard spec or target-file presence first."
            ),
        },
        "review_bundle": {
            "guard_id": proposed_guard.get("guard_id"),
            "payload_id": proposed_guard.get("payload_id"),
            "scope": proposed_guard.get("scope"),
            "patch_review_targets": target_entries,
            "must_preserve_invariants": invariants,
            "test_plan": test_plan,
            "non_goals": list(proposed_guard.get("non_goals", [])),
        },
        "evidence": {
            "non_trigger_max_slot_count": evidence.get("non_trigger_max_slot_count"),
            "anchored_trigger_min_slot_count": evidence.get("anchored_trigger_min_slot_count"),
            "free_ghost_trigger_min_slot_count": evidence.get("free_ghost_trigger_min_slot_count"),
            "advisory_would_trigger": evidence.get("advisory_would_trigger"),
            "advisory_triggered": evidence.get("advisory_triggered"),
        },
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("review_bundle"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Guard Patch Review Bundle",
        "",
        f"- Bundle ready for review: {bool(status.get('bundle_ready_for_review', False))}",
        f"- Runtime patch ready: {bool(status.get('runtime_patch_ready', False))}",
        f"- Recommended next step: {status.get('recommended_next_step')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Review Bundle",
        "",
        f"- Guard id: `{bundle.get('guard_id')}`",
        f"- Payload id: `{bundle.get('payload_id')}`",
        f"- Scope: `{bundle.get('scope')}`",
        "",
        "## Evidence",
        "",
        f"- Non-trigger max slot count: `{evidence.get('non_trigger_max_slot_count')}`",
        f"- Anchored trigger min slot count: `{evidence.get('anchored_trigger_min_slot_count')}`",
        f"- Free-ghost trigger min slot count: `{evidence.get('free_ghost_trigger_min_slot_count')}`",
        f"- Advisory would trigger: `{evidence.get('advisory_would_trigger')}`",
        f"- Advisory triggered: `{evidence.get('advisory_triggered')}`",
        "",
        "## Patch Targets",
        "",
        "| Path | Exists |",
        "| --- | --- |",
    ]
    for entry in list(bundle.get("patch_review_targets", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('path'))} | {_markdown_cell(entry.get('exists'))} |"
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


def render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("review_bundle"))
    evidence = _mapping(report.get("evidence"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain guard patch review bundle",
            f"bundle_ready_for_review={status.get('bundle_ready_for_review')}",
            f"runtime_patch_ready={status.get('runtime_patch_ready')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"guard_id={bundle.get('guard_id')}",
            f"payload_id={bundle.get('payload_id')}",
            f"non_trigger_max_slot_count={evidence.get('non_trigger_max_slot_count')}",
            f"anchored_trigger_min_slot_count={evidence.get('anchored_trigger_min_slot_count')}",
            f"advisory_would_trigger={evidence.get('advisory_would_trigger')}",
        ]
    ) + "\n"


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

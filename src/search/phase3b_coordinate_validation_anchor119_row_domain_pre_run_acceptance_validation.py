from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_REFRESH_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
)
RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
)
PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1"
)
DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_20260424/"
    "anchor119_row_domain_acceptance_refresh_prep.json"
)
DEFAULT_SIGNOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_20260424/"
    "anchor119_row_domain_runtime_patch_signoff_bundle.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation(
    project_root: Path,
    *,
    acceptance_refresh_prep_path: Optional[Path] = None,
    signoff_bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    acceptance_refresh_prep_resolved = _resolve_path(
        project_root,
        acceptance_refresh_prep_path
        if acceptance_refresh_prep_path is not None
        else DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH,
    )
    signoff_bundle_resolved = _resolve_path(
        project_root,
        signoff_bundle_path if signoff_bundle_path is not None else DEFAULT_SIGNOFF_BUNDLE_PATH,
    )

    acceptance_refresh_report, acceptance_refresh_error = _load_json_mapping(
        acceptance_refresh_prep_resolved
    )
    signoff_bundle_report, signoff_bundle_error = _load_json_mapping(
        signoff_bundle_resolved
    )

    acceptance_refresh_meta = (
        _mapping(acceptance_refresh_report.get("metadata"))
        if acceptance_refresh_report
        else {}
    )
    acceptance_refresh_status = (
        _mapping(acceptance_refresh_report.get("status"))
        if acceptance_refresh_report
        else {}
    )
    acceptance_refresh_prep = (
        _mapping(acceptance_refresh_report.get("acceptance_refresh_prep"))
        if acceptance_refresh_report
        else {}
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
    candidate = (
        _mapping(acceptance_refresh_report.get("candidate"))
        if acceptance_refresh_report
        else _mapping(signoff_bundle_report.get("candidate"))
        if signoff_bundle_report
        else {}
    )

    acceptance_refresh_prep_present = bool(
        acceptance_refresh_report is not None
        and acceptance_refresh_error is None
        and acceptance_refresh_meta.get("source") == ACCEPTANCE_REFRESH_PREP_SOURCE
    )
    signoff_bundle_present = bool(
        signoff_bundle_report is not None
        and signoff_bundle_error is None
        and signoff_meta.get("source") == RUNTIME_PATCH_SIGNOFF_BUNDLE_SOURCE
    )
    acceptance_refresh_ready = bool(
        acceptance_refresh_status.get("acceptance_refresh_ready_for_review", False)
    )
    signoff_ready = bool(
        signoff_status.get("reviewed_runtime_patch_signoff_ready_for_review", False)
    )
    acceptance_runtime_enablement_allowed = bool(
        acceptance_refresh_status.get("runtime_enablement_allowed", False)
    )
    signoff_runtime_enablement_allowed = bool(
        signoff_status.get("runtime_enablement_allowed", False)
    )
    runtime_enablement_still_blocked = bool(
        not acceptance_runtime_enablement_allowed and not signoff_runtime_enablement_allowed
    )

    exact_future_acceptance_json_path = str(
        acceptance_refresh_prep.get("suite_output_path") or ""
    )
    production_acceptance_command = str(
        signoff_bundle.get("production_acceptance_command")
        or acceptance_refresh_prep.get("acceptance_command")
        or ""
    )
    command_suite_output_path = _extract_suite_output_path(production_acceptance_command)
    command_output_path_matches = bool(
        exact_future_acceptance_json_path
        and command_suite_output_path
        and _normalize_path_text(command_suite_output_path)
        == _normalize_path_text(exact_future_acceptance_json_path)
    )

    required_prod_4x4_validity_fields = [
        {
            "field": "completed",
            "expected": True,
            "reason": "long-run preflight requires the prod_4x4 record to be completed",
        },
        {
            "field": "return_code",
            "expected": 0,
            "reason": "long-run preflight requires the prod_4x4 record return_code to equal 0",
        },
        {
            "field": "campaign_valid_after_run",
            "expected": True,
            "reason": "long-run preflight requires the refreshed campaign to remain valid",
        },
        {
            "field": "duplicated_work",
            "expected": False,
            "reason": "long-run preflight rejects duplicated work in the prod_4x4 record",
        },
    ]
    prod_4x4_validity_criteria = _mapping(
        acceptance_refresh_prep.get("validity_criteria")
    )
    prod_4x4_validity_contract_defined = bool(
        prod_4x4_validity_criteria.get("label") == "prod_4x4"
        and prod_4x4_validity_criteria.get("completed") is True
        and int(prod_4x4_validity_criteria.get("return_code", -1)) == 0
        and prod_4x4_validity_criteria.get("campaign_valid_after_run") is True
        and prod_4x4_validity_criteria.get("duplicated_work") is False
    )

    pre_run_checklist_items = [
        {
            "checklist_id": "review_and_collect_runtime_patch_signoff_record",
            "required": True,
            "detail": (
                "Review the signoff bundle and collect the separate reviewed runtime patch "
                "signoff record before executing the acceptance command."
            ),
        },
        {
            "checklist_id": "keep_runtime_enablement_forbidden",
            "required": True,
            "detail": (
                "Keep runtime_enablement_allowed=false throughout this step; this prep does "
                "not enable runtime behavior."
            ),
        },
        {
            "checklist_id": "lock_future_acceptance_output_path",
            "required": True,
            "detail": (
                "Use the locked prod_4x4 acceptance command and write the future acceptance "
                f"JSON to `{exact_future_acceptance_json_path}`."
            ),
        },
        {
            "checklist_id": "validate_future_prod_4x4_record_contract",
            "required": True,
            "detail": (
                "After the future run, validate the prod_4x4 record fields "
                "completed=True, return_code=0, campaign_valid_after_run=True, "
                "duplicated_work=False before any enablement discussion."
            ),
        },
        {
            "checklist_id": "preserve_execution_boundaries",
            "required": True,
            "detail": (
                "Do not treat this prep as acceptance execution, runtime enablement, long-run "
                "authorization, checkpoint creation, or proof-source promotion."
            ),
        },
    ]

    checks = [
        _check(
            "acceptance_refresh_prep_present",
            "pass" if acceptance_refresh_prep_present else "fail",
            "acceptance refresh prep loaded"
            if acceptance_refresh_prep_present
            else acceptance_refresh_error
            or f"missing:{_display_path(project_root, acceptance_refresh_prep_resolved)}",
        ),
        _check(
            "signoff_bundle_present",
            "pass" if signoff_bundle_present else "fail",
            "runtime patch signoff bundle loaded"
            if signoff_bundle_present
            else signoff_bundle_error
            or f"missing:{_display_path(project_root, signoff_bundle_resolved)}",
        ),
        _check(
            "acceptance_refresh_ready_for_review",
            "pass" if acceptance_refresh_ready else "fail",
            str(acceptance_refresh_status.get("acceptance_refresh_ready_for_review")),
        ),
        _check(
            "reviewed_runtime_patch_signoff_ready_for_review",
            "pass" if signoff_ready else "fail",
            str(
                signoff_status.get(
                    "reviewed_runtime_patch_signoff_ready_for_review", False
                )
            ),
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_still_blocked else "fail",
            (
                f"acceptance_refresh_runtime_enablement_allowed="
                f"{acceptance_runtime_enablement_allowed} "
                f"signoff_runtime_enablement_allowed={signoff_runtime_enablement_allowed}"
            ),
        ),
        _check(
            "exact_future_acceptance_json_path_known",
            "pass" if bool(exact_future_acceptance_json_path) else "fail",
            exact_future_acceptance_json_path or "missing",
        ),
        _check(
            "production_acceptance_command_matches_output_path",
            "pass" if command_output_path_matches else "fail",
            production_acceptance_command or "missing",
        ),
        _check(
            "prod_4x4_validity_contract_defined",
            "pass" if prod_4x4_validity_contract_defined else "fail",
            json.dumps(prod_4x4_validity_criteria, sort_keys=True)
            if prod_4x4_validity_criteria
            else "missing",
        ),
    ]

    gates = [
        {
            "gate_id": "acceptance_refresh_prep_ready_for_review",
            "satisfied": bool(acceptance_refresh_ready),
            "blocking": not bool(acceptance_refresh_ready),
            "detail": "The acceptance-refresh prep artifact must already be review-ready.",
        },
        {
            "gate_id": "runtime_patch_signoff_bundle_ready_for_review",
            "satisfied": bool(signoff_ready),
            "blocking": not bool(signoff_ready),
            "detail": "The runtime patch signoff bundle must already be review-ready.",
        },
        {
            "gate_id": "exact_future_acceptance_json_path_known",
            "satisfied": bool(exact_future_acceptance_json_path),
            "blocking": not bool(exact_future_acceptance_json_path),
            "detail": "The future acceptance JSON output path must be explicit before review.",
        },
        {
            "gate_id": "prod_4x4_validity_contract_defined",
            "satisfied": bool(prod_4x4_validity_contract_defined),
            "blocking": not bool(prod_4x4_validity_contract_defined),
            "detail": "The prod_4x4 validity contract must match the long-run preflight rules.",
        },
        {
            "gate_id": "runtime_enablement_still_blocked",
            "satisfied": bool(runtime_enablement_still_blocked),
            "blocking": not bool(runtime_enablement_still_blocked),
            "detail": "This review-prep step must keep runtime enablement forbidden.",
        },
    ]

    acceptance_validation_ready_for_review = all(
        check["status"] == "pass" for check in checks
    )
    handoff_recommendation = (
        "Pre-run acceptance validation prep is ready for review: approve this contract, then "
        "collect the separate reviewed runtime patch signoff record, execute the locked "
        f"prod_4x4 acceptance command to `{exact_future_acceptance_json_path}`, and validate "
        "the resulting prod_4x4 record before any enablement discussion."
        if acceptance_validation_ready_for_review
        else "Pre-run acceptance validation prep is blocked; repair the missing upstream prep, "
        "signoff, output-path, or prod_4x4 validity-contract inputs before review."
    )

    return {
        "metadata": {
            "source": PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_pre_run_acceptance_validation_prep_not_acceptance_execution"
            ),
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
        "paths": {
            "project_root": str(project_root),
            "acceptance_refresh_prep": _display_path(
                project_root, acceptance_refresh_prep_resolved
            ),
            "signoff_bundle": _display_path(project_root, signoff_bundle_resolved),
            "expected_future_acceptance_json": exact_future_acceptance_json_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_validation_ready_for_review": bool(
                acceptance_validation_ready_for_review
            ),
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "recommended_next_step": (
                "review_pre_run_acceptance_validation_then_collect_signoff_before_execution"
            ),
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "pre_run_acceptance_validation": {
            "guard_id": acceptance_refresh_prep.get("guard_id")
            or signoff_bundle.get("guard_id"),
            "payload_id": acceptance_refresh_prep.get("payload_id")
            or signoff_bundle.get("payload_id"),
            "production_profile_id": acceptance_refresh_prep.get("production_profile_id"),
            "production_acceptance_command": production_acceptance_command,
            "exact_future_acceptance_json_path": exact_future_acceptance_json_path,
            "prod_4x4_record_match_rules": [
                {
                    "selector": "label",
                    "field": "label",
                    "expected": "prod_4x4",
                    "reason": "primary long-run preflight selector",
                },
                {
                    "selector": "fallback_4x4_parallelism",
                    "fields": {
                        "process_count": 4,
                        "worker_count_per_process": 4,
                    },
                    "reason": "fallback selector when label is absent",
                },
            ],
            "required_prod_4x4_validity_fields": required_prod_4x4_validity_fields,
            "pre_run_checklist_items": pre_run_checklist_items,
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("pre_run_acceptance_validation"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Pre-Run Acceptance Validation",
        "",
        f"- Acceptance validation ready for review: `{status.get('acceptance_validation_ready_for_review')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Pre-Run Acceptance Validation",
        "",
        f"- Guard id: `{prep.get('guard_id')}`",
        f"- Payload id: `{prep.get('payload_id')}`",
        f"- Production profile id: `{prep.get('production_profile_id')}`",
        f"- Production acceptance command: `{prep.get('production_acceptance_command')}`",
        f"- Exact future acceptance JSON path: `{prep.get('exact_future_acceptance_json_path')}`",
        "",
        "## Prod 4x4 Record Match Rules",
        "",
        "| Selector | Detail | Reason |",
        "| --- | --- | --- |",
    ]
    for entry in list(prep.get("prod_4x4_record_match_rules", [])):
        if isinstance(entry, Mapping):
            detail = (
                f"{entry.get('field')}={entry.get('expected')}"
                if entry.get("field") is not None
                else json.dumps(dict(entry.get("fields", {})), sort_keys=True)
            )
            lines.append(
                f"| {_markdown_cell(entry.get('selector'))} | "
                f"{_markdown_cell(detail)} | "
                f"{_markdown_cell(entry.get('reason'))} |"
            )
    lines.extend(
        [
            "",
            "## Required Prod 4x4 Validity Fields",
            "",
            "| Field | Expected | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(prep.get("required_prod_4x4_validity_fields", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('expected'))} | "
                f"{_markdown_cell(entry.get('reason'))} |"
            )
    lines.extend(
        [
            "",
            "## Pre-Run Checklist",
            "",
        ]
    )
    for entry in list(prep.get("pre_run_checklist_items", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"- `{entry.get('checklist_id')}`: {entry.get('detail')}"
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


def render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    prep = _mapping(report.get("pre_run_acceptance_validation"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain pre-run acceptance validation",
            f"acceptance_validation_ready_for_review={status.get('acceptance_validation_ready_for_review')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"acceptance_executed={status.get('acceptance_executed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"exact_future_acceptance_json_path={prep.get('exact_future_acceptance_json_path')}",
            f"handoff_recommendation={status.get('handoff_recommendation')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_pre_run_acceptance_validation",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_text(
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


def _extract_suite_output_path(command: str) -> Optional[str]:
    if not str(command).strip():
        return None
    try:
        tokens = shlex.split(str(command), posix=False)
    except ValueError:
        tokens = str(command).split()
    for index, token in enumerate(tokens):
        token_text = str(token)
        if token_text == "--suite-output" and index + 1 < len(tokens):
            return str(tokens[index + 1]).strip("\"'")
        if token_text.startswith("--suite-output="):
            return token_text.split("=", 1)[1].strip("\"'")
    return None


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

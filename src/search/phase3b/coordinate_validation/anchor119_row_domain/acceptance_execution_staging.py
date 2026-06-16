from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1"
)
ACCEPTANCE_REFRESH_PREP_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
)
ACCEPTANCE_EXECUTION_STAGING_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
)
DEFAULT_PRE_RUN_ACCEPTANCE_VALIDATION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_20260424/"
    "anchor119_row_domain_pre_run_acceptance_validation.json"
)
DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_20260424/"
    "anchor119_row_domain_acceptance_refresh_prep.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging(
    project_root: Path,
    *,
    pre_run_acceptance_validation_path: Optional[Path] = None,
    acceptance_refresh_prep_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    pre_run_resolved = _resolve_path(
        project_root,
        pre_run_acceptance_validation_path
        if pre_run_acceptance_validation_path is not None
        else DEFAULT_PRE_RUN_ACCEPTANCE_VALIDATION_PATH,
    )
    acceptance_refresh_resolved = _resolve_path(
        project_root,
        acceptance_refresh_prep_path
        if acceptance_refresh_prep_path is not None
        else DEFAULT_ACCEPTANCE_REFRESH_PREP_PATH,
    )

    pre_run_report, pre_run_error = _load_json_mapping(pre_run_resolved)
    acceptance_refresh_report, acceptance_refresh_error = _load_json_mapping(
        acceptance_refresh_resolved
    )

    pre_run_meta = _mapping(pre_run_report.get("metadata")) if pre_run_report else {}
    pre_run_status = _mapping(pre_run_report.get("status")) if pre_run_report else {}
    pre_run_validation = (
        _mapping(pre_run_report.get("pre_run_acceptance_validation"))
        if pre_run_report
        else {}
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
    candidate = (
        _mapping(pre_run_report.get("candidate"))
        if pre_run_report
        else _mapping(acceptance_refresh_report.get("candidate"))
        if acceptance_refresh_report
        else {}
    )

    pre_run_present = bool(
        pre_run_report is not None
        and pre_run_error is None
        and pre_run_meta.get("source") == PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE
    )
    acceptance_refresh_present = bool(
        acceptance_refresh_report is not None
        and acceptance_refresh_error is None
        and acceptance_refresh_meta.get("source") == ACCEPTANCE_REFRESH_PREP_SOURCE
    )
    pre_run_ready_for_review = bool(
        pre_run_status.get("acceptance_validation_ready_for_review", False)
    )
    acceptance_refresh_ready_for_review = bool(
        acceptance_refresh_status.get("acceptance_refresh_ready_for_review", False)
    )
    pre_run_runtime_enablement_allowed = bool(
        pre_run_status.get("runtime_enablement_allowed", False)
    )
    acceptance_refresh_runtime_enablement_allowed = bool(
        acceptance_refresh_status.get("runtime_enablement_allowed", False)
    )
    runtime_enablement_still_blocked = bool(
        not pre_run_runtime_enablement_allowed
        and not acceptance_refresh_runtime_enablement_allowed
    )
    acceptance_executed = bool(pre_run_status.get("acceptance_executed", False))

    pre_run_command = str(
        pre_run_validation.get("production_acceptance_command") or ""
    )
    acceptance_refresh_command = str(
        acceptance_refresh_prep.get("acceptance_command") or ""
    )
    exact_command_to_run_later = pre_run_command or acceptance_refresh_command
    exact_command_locked = bool(
        pre_run_command
        and acceptance_refresh_command
        and _normalize_command_text(pre_run_command)
        == _normalize_command_text(acceptance_refresh_command)
    )

    pre_run_output_path = str(
        pre_run_validation.get("exact_future_acceptance_json_path") or ""
    )
    acceptance_refresh_output_path = str(
        acceptance_refresh_prep.get("suite_output_path") or ""
    )
    exact_future_output_path = pre_run_output_path or acceptance_refresh_output_path
    exact_future_output_path_locked = bool(
        pre_run_output_path
        and acceptance_refresh_output_path
        and _normalize_path_text(pre_run_output_path)
        == _normalize_path_text(acceptance_refresh_output_path)
    )
    command_output_path = _extract_suite_output_path(exact_command_to_run_later)
    command_matches_output_path = bool(
        exact_future_output_path
        and command_output_path
        and _normalize_path_text(exact_future_output_path)
        == _normalize_path_text(command_output_path)
    )

    prod_4x4_record_match_rules = _match_rule_list(
        pre_run_validation.get("prod_4x4_record_match_rules")
    )
    expected_prod_4x4_validity_fields = _expected_prod_4x4_validity_fields(
        pre_run_validation.get("required_prod_4x4_validity_fields"),
        _mapping(acceptance_refresh_prep.get("validity_criteria")),
    )
    expected_validity_fields_defined = _expected_prod_4x4_validity_fields_defined(
        expected_prod_4x4_validity_fields,
        _mapping(acceptance_refresh_prep.get("validity_criteria")),
    )

    staging_checklist_before_execution = [
        {
            "checklist_id": "review_staging_artifact_only",
            "required": True,
            "detail": (
                "Review this staging artifact as a contract only. It does not execute "
                "acceptance and it does not imply runtime enablement."
            ),
        },
        {
            "checklist_id": "keep_runtime_enablement_forbidden",
            "required": True,
            "detail": (
                "Keep runtime_enablement_allowed=false throughout staging and any "
                "subsequent review. Do not treat this as activation approval."
            ),
        },
        {
            "checklist_id": "hold_locked_acceptance_command_for_later_execution",
            "required": True,
            "detail": (
                "When a later reviewer separately authorizes execution, run exactly "
                f"`{exact_command_to_run_later}`."
            ),
        },
        {
            "checklist_id": "hold_locked_future_output_path",
            "required": True,
            "detail": (
                "Write the later acceptance output to exactly "
                f"`{exact_future_output_path}`."
            ),
        },
        {
            "checklist_id": "validate_expected_prod_4x4_fields_after_future_run",
            "required": True,
            "detail": (
                "After the future run, validate the prod_4x4 record against the staged "
                "expected validity fields before any enablement discussion."
            ),
        },
        {
            "checklist_id": "preserve_phase3b_execution_boundaries",
            "required": True,
            "detail": (
                "Do not treat staging as proof-source promotion, runtime behavior "
                "enablement, release/viewer/frontdoor status change, campaign checkpoint "
                "creation or import, or long-run authorization."
            ),
        },
    ]

    checks = [
        _check(
            "pre_run_acceptance_validation_present",
            "pass" if pre_run_present else "fail",
            "pre-run acceptance validation loaded"
            if pre_run_present
            else pre_run_error or f"missing:{_display_path(project_root, pre_run_resolved)}",
        ),
        _check(
            "acceptance_refresh_prep_present",
            "pass" if acceptance_refresh_present else "fail",
            "acceptance refresh prep loaded"
            if acceptance_refresh_present
            else acceptance_refresh_error
            or f"missing:{_display_path(project_root, acceptance_refresh_resolved)}",
        ),
        _check(
            "pre_run_acceptance_validation_ready_for_review",
            "pass" if pre_run_ready_for_review else "fail",
            str(pre_run_status.get("acceptance_validation_ready_for_review")),
        ),
        _check(
            "acceptance_refresh_ready_for_review",
            "pass" if acceptance_refresh_ready_for_review else "fail",
            str(acceptance_refresh_status.get("acceptance_refresh_ready_for_review")),
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_still_blocked else "fail",
            (
                f"pre_run_runtime_enablement_allowed={pre_run_runtime_enablement_allowed} "
                "acceptance_refresh_runtime_enablement_allowed="
                f"{acceptance_refresh_runtime_enablement_allowed}"
            ),
        ),
        _check(
            "acceptance_not_executed",
            "pass" if not acceptance_executed else "fail",
            f"acceptance_executed={acceptance_executed}",
        ),
        _check(
            "exact_command_to_run_later_locked",
            "pass" if exact_command_locked else "fail",
            exact_command_to_run_later or "missing",
        ),
        _check(
            "exact_future_output_path_locked",
            "pass" if exact_future_output_path_locked else "fail",
            exact_future_output_path or "missing",
        ),
        _check(
            "command_matches_output_path",
            "pass" if command_matches_output_path else "fail",
            exact_command_to_run_later or "missing",
        ),
        _check(
            "expected_prod_4x4_validity_fields_defined",
            "pass" if expected_validity_fields_defined else "fail",
            json.dumps(
                {
                    entry.get("field"): entry.get("expected")
                    for entry in expected_prod_4x4_validity_fields
                    if isinstance(entry, Mapping)
                },
                sort_keys=True,
            )
            if expected_prod_4x4_validity_fields
            else "missing",
        ),
    ]

    gates = [
        {
            "gate_id": "pre_run_acceptance_validation_ready_for_review",
            "satisfied": bool(pre_run_ready_for_review),
            "blocking": not bool(pre_run_ready_for_review),
            "detail": (
                "Acceptance execution staging depends on the pre-run acceptance validation "
                "artifact already being review-ready."
            ),
        },
        {
            "gate_id": "acceptance_refresh_ready_for_review",
            "satisfied": bool(acceptance_refresh_ready_for_review),
            "blocking": not bool(acceptance_refresh_ready_for_review),
            "detail": (
                "Acceptance refresh prep must remain review-ready so the execution command "
                "and output contract stay fixed."
            ),
        },
        {
            "gate_id": "exact_command_to_run_later_locked",
            "satisfied": bool(exact_command_locked),
            "blocking": not bool(exact_command_locked),
            "detail": (
                "The exact future acceptance command must match across the upstream staging "
                "artifacts before review."
            ),
        },
        {
            "gate_id": "exact_future_output_path_locked",
            "satisfied": bool(exact_future_output_path_locked),
            "blocking": not bool(exact_future_output_path_locked),
            "detail": (
                "The exact future acceptance output path must match across the upstream "
                "staging artifacts before review."
            ),
        },
        {
            "gate_id": "expected_prod_4x4_validity_fields_defined",
            "satisfied": bool(expected_validity_fields_defined),
            "blocking": not bool(expected_validity_fields_defined),
            "detail": (
                "The staged prod_4x4 validity contract must remain explicit before any "
                "future execution discussion."
            ),
        },
        {
            "gate_id": "runtime_enablement_still_blocked",
            "satisfied": bool(runtime_enablement_still_blocked),
            "blocking": not bool(runtime_enablement_still_blocked),
            "detail": (
                "Acceptance execution staging must remain default-off and must not imply "
                "runtime enablement."
            ),
        },
        {
            "gate_id": "acceptance_not_executed",
            "satisfied": bool(not acceptance_executed),
            "blocking": bool(acceptance_executed),
            "detail": (
                "This artifact is staging only. It must not claim that acceptance has "
                "already been executed."
            ),
        },
    ]

    acceptance_execution_staging_ready = all(
        check["status"] == "pass" for check in checks
    )
    handoff_recommendation = (
        "Acceptance execution staging is ready for review only: keep "
        "runtime_enablement_allowed=false, do not execute acceptance from this staging "
        "artifact, and when later execution is separately authorized run "
        f"`{exact_command_to_run_later}` to produce `{exact_future_output_path}`, then "
        "validate the staged prod_4x4 record fields before any enablement discussion."
        if acceptance_execution_staging_ready
        else "Acceptance execution staging is blocked; repair the upstream review-ready "
        "artifacts, locked command/output-path contract, or staged prod_4x4 validity "
        "fields before review."
    )

    return {
        "metadata": {
            "source": ACCEPTANCE_EXECUTION_STAGING_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_execution_staging_not_acceptance_execution"
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
            "pre_run_acceptance_validation": _display_path(
                project_root, pre_run_resolved
            ),
            "acceptance_refresh_prep": _display_path(
                project_root, acceptance_refresh_resolved
            ),
            "exact_future_output_path": exact_future_output_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_execution_staging_ready": bool(
                acceptance_execution_staging_ready
            ),
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "recommended_next_step": (
                "review_acceptance_execution_staging_then_hold_locked_prod_4x4_execution"
            ),
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_execution_staging": {
            "guard_id": pre_run_validation.get("guard_id")
            or acceptance_refresh_prep.get("guard_id"),
            "payload_id": pre_run_validation.get("payload_id")
            or acceptance_refresh_prep.get("payload_id"),
            "production_profile_id": pre_run_validation.get("production_profile_id")
            or acceptance_refresh_prep.get("production_profile_id"),
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "exact_command_to_run_later": exact_command_to_run_later,
            "exact_future_output_path": exact_future_output_path,
            "prod_4x4_record_match_rules": prod_4x4_record_match_rules,
            "expected_prod_4x4_validity_fields": expected_prod_4x4_validity_fields,
            "staging_checklist_before_execution": staging_checklist_before_execution,
            "handoff_recommendation": handoff_recommendation,
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    staging = _mapping(report.get("acceptance_execution_staging"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Execution Staging",
        "",
        f"- Acceptance execution staging ready: `{status.get('acceptance_execution_staging_ready')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Acceptance Execution Staging",
        "",
        f"- Guard id: `{staging.get('guard_id')}`",
        f"- Payload id: `{staging.get('payload_id')}`",
        f"- Production profile id: `{staging.get('production_profile_id')}`",
        f"- Does not execute acceptance: `{staging.get('does_not_execute_acceptance')}`",
        f"- Does not imply enablement: `{staging.get('does_not_imply_enablement')}`",
        f"- Exact command to run later: `{staging.get('exact_command_to_run_later')}`",
        f"- Exact future output path: `{staging.get('exact_future_output_path')}`",
        "",
        "## Prod 4x4 Record Match Rules",
        "",
        "| Selector | Detail | Reason |",
        "| --- | --- | --- |",
    ]
    for entry in list(staging.get("prod_4x4_record_match_rules", [])):
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
            "## Expected Prod 4x4 Validity Fields",
            "",
            "| Field | Expected | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(staging.get("expected_prod_4x4_validity_fields", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('expected'))} | "
                f"{_markdown_cell(entry.get('reason'))} |"
            )
    lines.extend(
        [
            "",
            "## Staging Checklist Before Execution",
            "",
        ]
    )
    for entry in list(staging.get("staging_checklist_before_execution", [])):
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    staging = _mapping(report.get("acceptance_execution_staging"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance execution staging",
            f"acceptance_execution_staging_ready={status.get('acceptance_execution_staging_ready')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            f"acceptance_executed={status.get('acceptance_executed')}",
            f"recommended_next_step={status.get('recommended_next_step')}",
            f"exact_command_to_run_later={staging.get('exact_command_to_run_later')}",
            f"exact_future_output_path={staging.get('exact_future_output_path')}",
            f"handoff_recommendation={status.get('handoff_recommendation')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_acceptance_execution_staging",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _expected_prod_4x4_validity_fields(
    pre_run_fields: Any, validity_criteria: Mapping[str, Any]
) -> list[Dict[str, Any]]:
    normalized = _validity_field_list(pre_run_fields)
    if normalized:
        return normalized
    derived = []
    reasons = {
        "completed": "future prod_4x4 record must report completed=True",
        "return_code": "future prod_4x4 record must report return_code=0",
        "campaign_valid_after_run": (
            "future prod_4x4 record must preserve campaign validity"
        ),
        "duplicated_work": "future prod_4x4 record must keep duplicated_work=False",
    }
    for field in (
        "completed",
        "return_code",
        "campaign_valid_after_run",
        "duplicated_work",
    ):
        if field in validity_criteria:
            derived.append(
                {
                    "field": field,
                    "expected": validity_criteria.get(field),
                    "reason": reasons[field],
                }
            )
    return derived


def _expected_prod_4x4_validity_fields_defined(
    fields: list[Dict[str, Any]], validity_criteria: Mapping[str, Any]
) -> bool:
    if not fields:
        return False
    expected = {entry.get("field"): entry.get("expected") for entry in fields}
    return bool(
        validity_criteria.get("label") == "prod_4x4"
        and expected.get("completed") is True
        and int(expected.get("return_code", -1)) == 0
        and expected.get("campaign_valid_after_run") is True
        and expected.get("duplicated_work") is False
        and validity_criteria.get("completed") is True
        and int(validity_criteria.get("return_code", -1)) == 0
        and validity_criteria.get("campaign_valid_after_run") is True
        and validity_criteria.get("duplicated_work") is False
    )


def _validity_field_list(value: Any) -> list[Dict[str, Any]]:
    normalized = []
    if not isinstance(value, list):
        return normalized
    for entry in value:
        if isinstance(entry, Mapping) and entry.get("field") is not None:
            normalized.append(
                {
                    "field": str(entry.get("field")),
                    "expected": entry.get("expected"),
                    "reason": str(entry.get("reason", "")),
                }
            )
    return normalized


def _match_rule_list(value: Any) -> list[Dict[str, Any]]:
    normalized = []
    if not isinstance(value, list):
        return normalized
    for entry in value:
        if isinstance(entry, Mapping):
            normalized.append(dict(entry))
    return normalized


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


def _normalize_command_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

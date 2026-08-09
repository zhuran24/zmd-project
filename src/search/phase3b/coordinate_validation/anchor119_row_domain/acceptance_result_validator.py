from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.long_run.preflight import (
    _prod_4x4_record,
    _prod_4x4_record_valid,
    _production_acceptance_summary_contract_detail,
    _production_acceptance_summary_contract_valid,
)
from src.search.phase3b.b5a.certification_contracts import chain_fingerprint, sha256_file

ACCEPTANCE_EXECUTION_STAGING_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
)
PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1"
)
ACCEPTANCE_RESULT_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
)
DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_20260424/"
    "anchor119_row_domain_acceptance_execution_staging.json"
)
DEFAULT_PRE_RUN_ACCEPTANCE_VALIDATION_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_20260424/"
    "anchor119_row_domain_pre_run_acceptance_validation.json"
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
    project_root: Path,
    *,
    acceptance_execution_staging_path: Optional[Path] = None,
    pre_run_acceptance_validation_path: Optional[Path] = None,
    acceptance_result_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    acceptance_execution_staging_resolved = _resolve_path(
        project_root,
        acceptance_execution_staging_path
        if acceptance_execution_staging_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_STAGING_PATH,
    )
    pre_run_acceptance_validation_resolved = _resolve_path(
        project_root,
        pre_run_acceptance_validation_path
        if pre_run_acceptance_validation_path is not None
        else DEFAULT_PRE_RUN_ACCEPTANCE_VALIDATION_PATH,
    )
    acceptance_result_resolved = (
        _resolve_path(project_root, acceptance_result_path)
        if acceptance_result_path is not None
        else None
    )

    acceptance_execution_staging_report, acceptance_execution_staging_error = (
        _load_json_mapping(acceptance_execution_staging_resolved)
    )
    pre_run_acceptance_validation_report, pre_run_acceptance_validation_error = (
        _load_json_mapping(pre_run_acceptance_validation_resolved)
    )
    acceptance_result_report, acceptance_result_error = (
        _load_json_mapping(acceptance_result_resolved)
        if acceptance_result_resolved is not None
        else (None, None)
    )

    acceptance_execution_staging_meta = (
        _mapping(acceptance_execution_staging_report.get("metadata"))
        if acceptance_execution_staging_report
        else {}
    )
    acceptance_execution_staging_status = (
        _mapping(acceptance_execution_staging_report.get("status"))
        if acceptance_execution_staging_report
        else {}
    )
    acceptance_execution_staging = (
        _mapping(acceptance_execution_staging_report.get("acceptance_execution_staging"))
        if acceptance_execution_staging_report
        else {}
    )
    pre_run_acceptance_validation_meta = (
        _mapping(pre_run_acceptance_validation_report.get("metadata"))
        if pre_run_acceptance_validation_report
        else {}
    )
    pre_run_acceptance_validation_status = (
        _mapping(pre_run_acceptance_validation_report.get("status"))
        if pre_run_acceptance_validation_report
        else {}
    )
    pre_run_acceptance_validation = (
        _mapping(
            pre_run_acceptance_validation_report.get("pre_run_acceptance_validation")
        )
        if pre_run_acceptance_validation_report
        else {}
    )
    candidate = (
        _mapping(acceptance_execution_staging_report.get("candidate"))
        if acceptance_execution_staging_report
        else _mapping(pre_run_acceptance_validation_report.get("candidate"))
        if pre_run_acceptance_validation_report
        else {}
    )

    acceptance_execution_staging_present = bool(
        acceptance_execution_staging_report is not None
        and acceptance_execution_staging_error is None
        and acceptance_execution_staging_meta.get("source")
        == ACCEPTANCE_EXECUTION_STAGING_SOURCE
    )
    pre_run_acceptance_validation_present = bool(
        pre_run_acceptance_validation_report is not None
        and pre_run_acceptance_validation_error is None
        and pre_run_acceptance_validation_meta.get("source")
        == PRE_RUN_ACCEPTANCE_VALIDATION_SOURCE
    )
    acceptance_execution_staging_ready = bool(
        acceptance_execution_staging_status.get("acceptance_execution_staging_ready", False)
    )
    pre_run_acceptance_validation_ready = bool(
        pre_run_acceptance_validation_status.get(
            "acceptance_validation_ready_for_review", False
        )
    )
    runtime_enablement_still_blocked = bool(
        not acceptance_execution_staging_status.get("runtime_enablement_allowed", False)
        and not pre_run_acceptance_validation_status.get(
            "runtime_enablement_allowed", False
        )
    )

    staging_expected_result_path = str(
        acceptance_execution_staging.get("exact_future_output_path") or ""
    )
    pre_run_expected_result_path = str(
        pre_run_acceptance_validation.get("exact_future_acceptance_json_path") or ""
    )
    expected_result_path = staging_expected_result_path or pre_run_expected_result_path
    expected_result_path_locked = bool(
        staging_expected_result_path
        and pre_run_expected_result_path
        and _normalize_path_text(staging_expected_result_path)
        == _normalize_path_text(pre_run_expected_result_path)
    )

    expected_prod_4x4_selector_rules_from_staging = _rule_list(
        acceptance_execution_staging.get("prod_4x4_record_match_rules")
    )
    expected_prod_4x4_selector_rules_from_pre_run = _rule_list(
        pre_run_acceptance_validation.get("prod_4x4_record_match_rules")
    )
    expected_prod_4x4_selector_rules = (
        expected_prod_4x4_selector_rules_from_staging
        or expected_prod_4x4_selector_rules_from_pre_run
    )
    prod_4x4_selector_rules_locked = bool(
        expected_prod_4x4_selector_rules_from_staging
        and expected_prod_4x4_selector_rules_from_pre_run
        and _canonical_json(expected_prod_4x4_selector_rules_from_staging)
        == _canonical_json(expected_prod_4x4_selector_rules_from_pre_run)
    )
    prod_4x4_selector_rules_match_long_run_preflight = (
        _selector_rules_match_long_run_preflight(expected_prod_4x4_selector_rules)
    )

    expected_prod_4x4_validity_fields_from_staging = _validity_field_list(
        acceptance_execution_staging.get("expected_prod_4x4_validity_fields")
    )
    expected_prod_4x4_validity_fields_from_pre_run = _validity_field_list(
        pre_run_acceptance_validation.get("required_prod_4x4_validity_fields")
    )
    expected_prod_4x4_validity_fields = (
        expected_prod_4x4_validity_fields_from_staging
        or expected_prod_4x4_validity_fields_from_pre_run
    )
    prod_4x4_validity_fields_locked = bool(
        expected_prod_4x4_validity_fields_from_staging
        and expected_prod_4x4_validity_fields_from_pre_run
        and _canonical_json(expected_prod_4x4_validity_fields_from_staging)
        == _canonical_json(expected_prod_4x4_validity_fields_from_pre_run)
    )
    prod_4x4_validity_fields_match_long_run_preflight = (
        _validity_fields_match_long_run_preflight(
            expected_prod_4x4_validity_fields
        )
    )

    result_validation = _build_acceptance_result_validation(
        project_root=project_root,
        acceptance_result_path=acceptance_result_resolved,
        acceptance_result_report=acceptance_result_report,
        acceptance_result_error=acceptance_result_error,
        expected_result_path=expected_result_path,
        selector_rules=expected_prod_4x4_selector_rules,
        validity_fields=expected_prod_4x4_validity_fields,
    )
    chain_input_hashes = _build_acceptance_result_chain_input_hashes(
        project_root=project_root,
        acceptance_execution_staging_path=acceptance_execution_staging_resolved,
        pre_run_acceptance_validation_path=pre_run_acceptance_validation_resolved,
        acceptance_result_path=acceptance_result_resolved,
    )
    chain_fingerprint_value = chain_fingerprint(chain_input_hashes)

    contract_checks = [
        _check(
            "acceptance_execution_staging_present",
            "pass" if acceptance_execution_staging_present else "fail",
            "acceptance execution staging loaded"
            if acceptance_execution_staging_present
            else acceptance_execution_staging_error
            or f"missing:{_display_path(project_root, acceptance_execution_staging_resolved)}",
        ),
        _check(
            "pre_run_acceptance_validation_present",
            "pass" if pre_run_acceptance_validation_present else "fail",
            "pre-run acceptance validation loaded"
            if pre_run_acceptance_validation_present
            else pre_run_acceptance_validation_error
            or f"missing:{_display_path(project_root, pre_run_acceptance_validation_resolved)}",
        ),
        _check(
            "acceptance_execution_staging_ready",
            "pass" if acceptance_execution_staging_ready else "fail",
            str(
                acceptance_execution_staging_status.get(
                    "acceptance_execution_staging_ready", False
                )
            ),
        ),
        _check(
            "pre_run_acceptance_validation_ready",
            "pass" if pre_run_acceptance_validation_ready else "fail",
            str(
                pre_run_acceptance_validation_status.get(
                    "acceptance_validation_ready_for_review", False
                )
            ),
        ),
        _check(
            "runtime_enablement_still_blocked",
            "pass" if runtime_enablement_still_blocked else "fail",
            (
                "acceptance_execution_staging_runtime_enablement_allowed="
                f"{bool(acceptance_execution_staging_status.get('runtime_enablement_allowed', False))} "
                "pre_run_runtime_enablement_allowed="
                f"{bool(pre_run_acceptance_validation_status.get('runtime_enablement_allowed', False))}"
            ),
        ),
        _check(
            "expected_result_path_locked",
            "pass" if expected_result_path_locked else "fail",
            expected_result_path or "missing",
        ),
        _check(
            "expected_prod_4x4_selector_rules_locked",
            "pass" if prod_4x4_selector_rules_locked else "fail",
            _canonical_json(expected_prod_4x4_selector_rules)
            if expected_prod_4x4_selector_rules
            else "missing",
        ),
        _check(
            "expected_prod_4x4_selector_rules_match_long_run_preflight",
            "pass" if prod_4x4_selector_rules_match_long_run_preflight else "fail",
            _canonical_json(expected_prod_4x4_selector_rules)
            if expected_prod_4x4_selector_rules
            else "missing",
        ),
        _check(
            "expected_prod_4x4_validity_fields_locked",
            "pass" if prod_4x4_validity_fields_locked else "fail",
            _canonical_json(expected_prod_4x4_validity_fields)
            if expected_prod_4x4_validity_fields
            else "missing",
        ),
        _check(
            "expected_prod_4x4_validity_fields_match_long_run_preflight",
            "pass" if prod_4x4_validity_fields_match_long_run_preflight else "fail",
            json.dumps(
                {
                    entry.get("field"): entry.get("expected")
                    for entry in expected_prod_4x4_validity_fields
                },
                sort_keys=True,
            )
            if expected_prod_4x4_validity_fields
            else "missing",
        ),
    ]
    result_checks = [
        _check(
            "real_acceptance_result_validation_deferred_or_passed",
            "pass"
            if (
                not bool(result_validation.get("acceptance_result_provided", False))
                or bool(result_validation.get("validation_passed", False))
            )
            else "fail",
            str(result_validation.get("summary")),
        ),
    ]
    gates = [
        {
            "gate_id": "acceptance_execution_staging_ready",
            "satisfied": bool(acceptance_execution_staging_ready),
            "blocking": not bool(acceptance_execution_staging_ready),
            "detail": (
                "Acceptance result validation depends on the staged command/output-path "
                "contract already being review-ready."
            ),
        },
        {
            "gate_id": "pre_run_acceptance_validation_ready",
            "satisfied": bool(pre_run_acceptance_validation_ready),
            "blocking": not bool(pre_run_acceptance_validation_ready),
            "detail": (
                "The validator contract depends on the pre-run acceptance validation "
                "artifact already being review-ready."
            ),
        },
        {
            "gate_id": "expected_result_path_locked",
            "satisfied": bool(expected_result_path_locked),
            "blocking": not bool(expected_result_path_locked),
            "detail": (
                "The future production-acceptance JSON path must stay locked across "
                "the upstream artifacts."
            ),
        },
        {
            "gate_id": "expected_prod_4x4_selector_rules_locked",
            "satisfied": bool(prod_4x4_selector_rules_locked),
            "blocking": not bool(prod_4x4_selector_rules_locked),
            "detail": (
                "The prod_4x4 selector rules must stay aligned between staging and "
                "pre-run validation."
            ),
        },
        {
            "gate_id": "expected_prod_4x4_validity_fields_locked",
            "satisfied": bool(prod_4x4_validity_fields_locked),
            "blocking": not bool(prod_4x4_validity_fields_locked),
            "detail": (
                "The prod_4x4 validity-field contract must stay aligned between staging "
                "and pre-run validation."
            ),
        },
        {
            "gate_id": "runtime_enablement_still_blocked",
            "satisfied": bool(runtime_enablement_still_blocked),
            "blocking": not bool(runtime_enablement_still_blocked),
            "detail": (
                "This validator is contract-only. Runtime enablement must remain "
                "forbidden."
            ),
        },
        {
            "gate_id": "real_acceptance_result_not_required_for_contract_review",
            "satisfied": True,
            "blocking": False,
            "detail": (
                "No real acceptance result JSON is required for the validator contract "
                "to be review-ready."
            ),
        },
    ]

    acceptance_result_validator_ready = all(
        check["status"] == "pass" for check in contract_checks
    )
    acceptance_result_validation_performed = bool(
        result_validation.get("validation_performed", False)
    )
    acceptance_result_validation_passed = bool(
        result_validation.get("validation_passed", False)
    )

    if acceptance_result_validator_ready and not acceptance_result_validation_performed:
        handoff_recommendation = (
            "Acceptance result validator contract is ready for review only: keep "
            "runtime_enablement_allowed=false, do not treat this as a real acceptance "
            "validation or enablement signal, and when a separately authorized future "
            f"production-acceptance JSON is produced at `{expected_result_path}`, "
            "validate its prod_4x4 record against the locked selector rules and validity "
            "fields before any enablement discussion."
        )
    elif acceptance_result_validator_ready and acceptance_result_validation_passed:
        handoff_recommendation = (
            "Acceptance result validator contract is ready and the provided acceptance "
            "result matches the staged prod_4x4 contract, but runtime_enablement_allowed "
            "must remain false until a separate enablement review explicitly authorizes "
            "any behavior change."
        )
    elif acceptance_result_validator_ready:
        handoff_recommendation = (
            "Acceptance result validator contract is ready, but the provided acceptance "
            "result does not satisfy the staged path/selector/validity contract. Keep "
            "runtime_enablement_allowed=false and repair the acceptance result before any "
            "enablement discussion."
        )
    else:
        handoff_recommendation = (
            "Acceptance result validator contract is blocked; repair the upstream staging "
            "or pre-run acceptance-validation artifacts before review."
        )

    return {
        "metadata": {
            "source": ACCEPTANCE_RESULT_VALIDATOR_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_result_validator_contract_not_acceptance_execution"
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
            "acceptance_execution_staging": _display_path(
                project_root, acceptance_execution_staging_resolved
            ),
            "pre_run_acceptance_validation": _display_path(
                project_root, pre_run_acceptance_validation_resolved
            ),
            "expected_result_path": expected_result_path,
            "provided_acceptance_result": (
                _display_path(project_root, acceptance_result_resolved)
                if acceptance_result_resolved is not None
                else None
            ),
        },
        "chain_input_hashes": chain_input_hashes,
        "chain_fingerprint": chain_fingerprint_value,
        "candidate": dict(candidate),
        "status": {
            "acceptance_result_validator_ready": bool(
                acceptance_result_validator_ready
            ),
            "runtime_enablement_allowed": False,
            "acceptance_result_validation_performed": bool(
                acceptance_result_validation_performed
            ),
            "acceptance_result_validation_passed": bool(
                acceptance_result_validation_passed
            ),
            "recommended_next_step": (
                "review_acceptance_result_validator_then_wait_for_future_prod_4x4_result"
            ),
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_result_validator": {
            "guard_id": acceptance_execution_staging.get("guard_id")
            or pre_run_acceptance_validation.get("guard_id"),
            "payload_id": acceptance_execution_staging.get("payload_id")
            or pre_run_acceptance_validation.get("payload_id"),
            "production_profile_id": acceptance_execution_staging.get(
                "production_profile_id"
            )
            or pre_run_acceptance_validation.get("production_profile_id"),
            "validates_future_acceptance_result_payload": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_validate_real_acceptance_run_yet": not bool(
                result_validation.get("acceptance_result_provided", False)
            ),
            "expected_result_path": expected_result_path,
            "expected_prod_4x4_selector_rules": expected_prod_4x4_selector_rules,
            "expected_prod_4x4_validity_fields": expected_prod_4x4_validity_fields,
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "required": True,
                    "detail": (
                        "Keep runtime_enablement_allowed=false before, during, and after "
                        "future acceptance-result validation."
                    ),
                },
                {
                    "checklist_id": "use_locked_acceptance_result_path",
                    "required": True,
                    "detail": (
                        "Validate the future acceptance result only against the locked "
                        f"path `{expected_result_path}`."
                    ),
                },
                {
                    "checklist_id": "validate_prod_4x4_record_against_staged_contract",
                    "required": True,
                    "detail": (
                        "Require the future acceptance JSON to expose a prod_4x4 record "
                        "that matches the staged selector rules and validity fields."
                    ),
                },
                {
                    "checklist_id": "preserve_phase3b_execution_boundaries",
                    "required": True,
                    "detail": (
                        "Do not treat this validator as runtime enablement, long-run "
                        "authorization, checkpoint creation or import, proof-source "
                        "promotion, or release/viewer/frontdoor status change."
                    ),
                },
            ],
            "handoff_recommendation": handoff_recommendation,
        },
        "result_validation": result_validation,
        "gates": gates,
        "checks": contract_checks + result_checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("acceptance_result_validator"))
    result_validation = _mapping(report.get("result_validation"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Result Validator",
        "",
        f"- Acceptance result validator ready: `{status.get('acceptance_result_validator_ready')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance result validation performed: `{status.get('acceptance_result_validation_performed')}`",
        f"- Acceptance result validation passed: `{status.get('acceptance_result_validation_passed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Validator Contract",
        "",
        f"- Guard id: `{validator.get('guard_id')}`",
        f"- Payload id: `{validator.get('payload_id')}`",
        f"- Production profile id: `{validator.get('production_profile_id')}`",
        f"- Validates future acceptance result payload: `{validator.get('validates_future_acceptance_result_payload')}`",
        f"- Does not execute acceptance: `{validator.get('does_not_execute_acceptance')}`",
        f"- Does not imply enablement: `{validator.get('does_not_imply_enablement')}`",
        f"- Does not validate real acceptance run yet: `{validator.get('does_not_validate_real_acceptance_run_yet')}`",
        f"- Expected result path: `{validator.get('expected_result_path')}`",
        "",
        "## Expected Prod 4x4 Selector Rules",
        "",
        "| Selector | Detail | Reason |",
        "| --- | --- | --- |",
    ]
    for entry in list(validator.get("expected_prod_4x4_selector_rules", [])):
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
    for entry in list(validator.get("expected_prod_4x4_validity_fields", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('expected'))} | "
                f"{_markdown_cell(entry.get('reason'))} |"
            )
    lines.extend(
        [
            "",
            "## Future Validation Checklist",
            "",
        ]
    )
    for entry in list(validator.get("future_validation_checklist", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"- `{entry.get('checklist_id')}`: {entry.get('detail')}"
            )
    lines.extend(
        [
            "",
            "## Result Validation State",
            "",
            f"- Acceptance result provided: `{result_validation.get('acceptance_result_provided')}`",
            f"- Validation performed: `{result_validation.get('validation_performed')}`",
            f"- Validation passed: `{result_validation.get('validation_passed')}`",
            f"- Path matches expected: `{result_validation.get('result_path_matches_expected')}`",
            f"- Prod 4x4 record found: `{result_validation.get('prod_4x4_record_found')}`",
            f"- Prod 4x4 record selected by: `{result_validation.get('prod_4x4_record_selected_by')}`",
            f"- Long-run preflight validity satisfied: `{result_validation.get('prod_4x4_record_valid_under_long_run_preflight')}`",
            f"- Summary: {result_validation.get('summary')}",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    validator = _mapping(report.get("acceptance_result_validator"))
    result_validation = _mapping(report.get("result_validation"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance result validator",
            f"acceptance_result_validator_ready={status.get('acceptance_result_validator_ready')}",
            f"runtime_enablement_allowed={status.get('runtime_enablement_allowed')}",
            "acceptance_result_validation_performed="
            + str(status.get("acceptance_result_validation_performed")),
            "acceptance_result_validation_passed="
            + str(status.get("acceptance_result_validation_passed")),
            f"expected_result_path={validator.get('expected_result_path')}",
            "does_not_validate_real_acceptance_run_yet="
            + str(validator.get("does_not_validate_real_acceptance_run_yet")),
            f"result_validation_summary={result_validation.get('summary')}",
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_acceptance_result_validator",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_acceptance_result_validation(
    *,
    project_root: Path,
    acceptance_result_path: Optional[Path],
    acceptance_result_report: Optional[Dict[str, Any]],
    acceptance_result_error: Optional[str],
    expected_result_path: str,
    selector_rules: list[Dict[str, Any]],
    validity_fields: list[Dict[str, Any]],
) -> Dict[str, Any]:
    acceptance_result_provided = acceptance_result_path is not None
    provided_acceptance_result_path = (
        _display_path(project_root, acceptance_result_path)
        if acceptance_result_path is not None
        else None
    )
    if not acceptance_result_provided:
        return {
            "acceptance_result_provided": False,
            "validation_performed": False,
            "validation_passed": False,
            "provided_acceptance_result_path": None,
            "provided_acceptance_result_sha256": None,
            "result_path_matches_expected": None,
            "prod_4x4_record_found": None,
            "prod_4x4_record_selected_by": None,
            "prod_4x4_record_valid_under_long_run_preflight": None,
            "selected_record_excerpt": {},
            "selector_rule_results": [],
            "validity_field_results": [],
            "summary": (
                "No real acceptance result JSON was provided. This artifact is a "
                "review-ready validator contract only and does not validate a real "
                "acceptance run yet."
            ),
        }

    result_path_matches_expected = bool(
        expected_result_path
        and provided_acceptance_result_path
        and _normalize_path_text(provided_acceptance_result_path)
        == _normalize_path_text(expected_result_path)
    )
    acceptance_result_sha256 = (
        sha256_file(acceptance_result_path)
        if acceptance_result_path is not None
        else None
    )
    if acceptance_result_report is None:
        return {
            "acceptance_result_provided": True,
            "validation_performed": False,
            "validation_passed": False,
            "provided_acceptance_result_path": provided_acceptance_result_path,
            "provided_acceptance_result_sha256": acceptance_result_sha256,
            "result_path_matches_expected": result_path_matches_expected,
            "prod_4x4_record_found": False,
            "prod_4x4_record_selected_by": None,
            "prod_4x4_record_valid_under_long_run_preflight": False,
            "selected_record_excerpt": {},
            "selector_rule_results": [],
            "validity_field_results": [],
            "summary": (
                "Acceptance result JSON could not be loaded: "
                f"{acceptance_result_error or 'unknown error'}"
            ),
        }

    selector_rule_results, selected_record, selected_by = _evaluate_selector_rules(
        acceptance_result_report, selector_rules
    )
    validity_field_results = _evaluate_validity_fields(selected_record, validity_fields)
    suite_contract_passed = _production_acceptance_summary_contract_valid(
        acceptance_result_report
    )
    supporting_artifact_results = _evaluate_supporting_artifacts(
        project_root,
        selected_record,
    )
    supporting_artifacts_passed = bool(
        supporting_artifact_results
        and all(item.get("passed") is True for item in supporting_artifact_results)
    )
    prod_4x4_record_valid_under_long_run_preflight = bool(
        selected_record is not None
        and _prod_4x4_record_valid(selected_record, summary=acceptance_result_report)
    )
    validation_passed = bool(
        result_path_matches_expected
        and selected_record is not None
        and suite_contract_passed
        and supporting_artifacts_passed
        and prod_4x4_record_valid_under_long_run_preflight
        and all(item.get("passed", False) for item in validity_field_results)
    )

    if not result_path_matches_expected:
        summary = (
            "Acceptance result JSON was provided, but its path does not match the staged "
            f"expected result path `{expected_result_path}`."
        )
    elif selected_record is None:
        summary = (
            "Acceptance result JSON was loaded, but no prod_4x4 record matched the "
            "staged selector rules."
        )
    elif not suite_contract_passed:
        summary = (
            "Acceptance result JSON was loaded, but it does not satisfy the locked "
            "production-acceptance suite contract: "
            + _production_acceptance_summary_contract_detail(acceptance_result_report)
        )
    elif not supporting_artifacts_passed:
        failed_artifacts = [
            str(item.get("artifact_id"))
            for item in supporting_artifact_results
            if item.get("passed") is not True
        ]
        summary = (
            "Acceptance result JSON was loaded, but supporting run artifacts failed "
            "validation: "
            + ", ".join(failed_artifacts)
        )
    elif not prod_4x4_record_valid_under_long_run_preflight:
        summary = (
            "Acceptance result JSON was loaded, but the selected prod_4x4 record does "
            "not satisfy the long-run preflight validity expectations."
        )
    elif not validation_passed:
        failed_fields = [
            str(item.get("field"))
            for item in validity_field_results
            if not bool(item.get("passed", False))
        ]
        summary = (
            "Acceptance result JSON was loaded, but the selected prod_4x4 record failed "
            "the staged validity-field checks: "
            + ", ".join(failed_fields)
        )
    else:
        summary = (
            "Acceptance result JSON matches the staged prod_4x4 selector rules and "
            "validity fields. This still does not imply runtime enablement."
        )

    return {
        "acceptance_result_provided": True,
        "validation_performed": True,
        "validation_passed": validation_passed,
        "provided_acceptance_result_path": provided_acceptance_result_path,
        "provided_acceptance_result_sha256": acceptance_result_sha256,
        "result_path_matches_expected": result_path_matches_expected,
        "production_acceptance_suite_contract_passed": suite_contract_passed,
        "production_acceptance_suite_contract_detail": (
            _production_acceptance_summary_contract_detail(acceptance_result_report)
        ),
        "prod_4x4_record_found": selected_record is not None,
        "prod_4x4_record_selected_by": selected_by,
        "prod_4x4_record_valid_under_long_run_preflight": (
            prod_4x4_record_valid_under_long_run_preflight
        ),
        "supporting_artifacts_passed": supporting_artifacts_passed,
        "supporting_artifact_results": supporting_artifact_results,
        "selected_record_excerpt": _record_excerpt(selected_record),
        "selector_rule_results": selector_rule_results,
        "validity_field_results": validity_field_results,
        "summary": summary,
    }


def _build_acceptance_result_chain_input_hashes(
    *,
    project_root: Path,
    acceptance_execution_staging_path: Path,
    pre_run_acceptance_validation_path: Path,
    acceptance_result_path: Optional[Path],
) -> list[Dict[str, Any]]:
    path_by_id: dict[str, Optional[Path]] = {
        "acceptance_execution_staging": acceptance_execution_staging_path,
        "pre_run_acceptance_validation": pre_run_acceptance_validation_path,
        "provided_acceptance_result": acceptance_result_path,
    }
    records: list[Dict[str, Any]] = []
    for input_id in sorted(path_by_id):
        path = path_by_id[input_id]
        digest = sha256_file(path) if path is not None else None
        records.append(
            {
                "input_id": input_id,
                "path": _display_path(project_root, path) if path is not None else None,
                "exists": digest is not None,
                "sha256": digest,
            }
        )
    return records


def _evaluate_supporting_artifacts(
    project_root: Path,
    record: Optional[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    if not isinstance(record, Mapping):
        return []
    results: list[Dict[str, Any]] = []
    for field in [
        "output_json",
        "log_path",
        "campaign_state_path",
        "campaign_telemetry_path",
    ]:
        raw_path = str(record.get(field) or "").strip()
        path = _resolve_acceptance_artifact_path(project_root, raw_path) if raw_path else None
        digest = sha256_file(path) if path is not None else None
        results.append(
            {
                "artifact_id": field,
                "path": _display_path(project_root, path) if path is not None else None,
                "exists": digest is not None,
                "sha256": digest,
                "passed": digest is not None,
                "detail": "exists" if digest is not None else "missing",
            }
        )
    output_result = _evaluate_child_output_json(project_root, record)
    if output_result is not None:
        results.append(output_result)
    return results


def _evaluate_child_output_json(
    project_root: Path,
    record: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    raw_path = str(record.get("output_json") or "").strip()
    if not raw_path:
        return {
            "artifact_id": "output_json_content_matches_record",
            "path": None,
            "exists": False,
            "sha256": None,
            "passed": False,
            "detail": "output_json missing",
        }
    path = _resolve_acceptance_artifact_path(project_root, raw_path)
    payload, error = _load_json_mapping(path)
    if payload is None:
        return {
            "artifact_id": "output_json_content_matches_record",
            "path": _display_path(project_root, path),
            "exists": False,
            "sha256": sha256_file(path),
            "passed": False,
            "detail": error or "output_json could not be loaded",
        }
    comparisons = {
        "target": record.get("target"),
        "completed": record.get("completed"),
        "campaign_valid_after_run": record.get("campaign_valid_after_run"),
        "duplicated_work": record.get("duplicated_work"),
        "parallel_processes": record.get("process_count"),
        "requested_master_search_profile": record.get("requested_master_search_profile"),
    }
    mismatches = [
        field
        for field, expected in comparisons.items()
        if payload.get(field) != expected
    ]
    return {
        "artifact_id": "output_json_content_matches_record",
        "path": _display_path(project_root, path),
        "exists": True,
        "sha256": sha256_file(path),
        "passed": not mismatches,
        "detail": "matches" if not mismatches else "mismatched_fields=" + str(mismatches),
    }


def _evaluate_selector_rules(
    acceptance_result_report: Mapping[str, Any],
    selector_rules: list[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    run_records = acceptance_result_report.get("run_records", [])
    if not isinstance(run_records, list):
        return [], None, None

    selected_record = None
    selected_by = None
    selector_rule_results = []
    for rule in selector_rules:
        matched_record = None
        for record in run_records:
            if not isinstance(record, Mapping):
                continue
            if _record_matches_rule(record, rule):
                matched_record = dict(record)
                break
        selector_rule_results.append(
            {
                "selector": str(rule.get("selector")),
                "matched": matched_record is not None,
                "detail": (
                    json.dumps(_record_excerpt(matched_record), sort_keys=True)
                    if matched_record is not None
                    else "no matching run_records entry"
                ),
            }
        )
        if selected_record is None and matched_record is not None:
            selected_record = matched_record
            selected_by = str(rule.get("selector"))

    if selected_record is None:
        fallback = _prod_4x4_record(acceptance_result_report)
        if isinstance(fallback, Mapping):
            selected_record = dict(fallback)
            selected_by = "long_run_preflight_fallback"
            selector_rule_results.append(
                {
                    "selector": "long_run_preflight_fallback",
                    "matched": True,
                    "detail": json.dumps(
                        _record_excerpt(selected_record), sort_keys=True
                    ),
                }
            )
    return selector_rule_results, selected_record, selected_by


def _evaluate_validity_fields(
    record: Optional[Mapping[str, Any]], validity_fields: list[Dict[str, Any]]
) -> list[Dict[str, Any]]:
    if not isinstance(record, Mapping):
        return []
    results = []
    for entry in validity_fields:
        field = str(entry.get("field"))
        actual = record.get(field)
        expected = entry.get("expected")
        results.append(
            {
                "field": field,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
                "reason": str(entry.get("reason", "")),
            }
        )
    return results


def _record_matches_rule(record: Mapping[str, Any], rule: Mapping[str, Any]) -> bool:
    if rule.get("field") is not None:
        return record.get(str(rule.get("field"))) == rule.get("expected")
    fields = _mapping(rule.get("fields"))
    if not fields:
        return False
    return all(record.get(str(field)) == expected for field, expected in fields.items())


def _selector_rules_match_long_run_preflight(
    selector_rules: list[Dict[str, Any]]
) -> bool:
    has_label_rule = any(
        entry.get("field") == "label" and entry.get("expected") == "prod_4x4"
        for entry in selector_rules
    )
    has_parallelism_rule = any(
        _mapping(entry.get("fields")).get("process_count") == 4
        and _mapping(entry.get("fields")).get("worker_count_per_process") == 4
        for entry in selector_rules
    )
    if not has_label_rule or not has_parallelism_rule:
        return False
    return bool(
        _prod_4x4_record(
            {
                "suite_kind": "production-acceptance",
                "run_records": [
                    {
                        "label": "prod_4x4",
                        "process_count": 4,
                        "worker_count_per_process": 4,
                    }
                ],
            }
        )
    )


def _validity_fields_match_long_run_preflight(
    validity_fields: list[Dict[str, Any]]
) -> bool:
    validity_record = {
        entry.get("field"): entry.get("expected") for entry in validity_fields
    }
    validation_probe = {
        **validity_record,
        "label": "prod_4x4",
        "process_count": 4,
        "worker_count_per_process": 4,
    }
    return bool(
        {"completed", "return_code", "campaign_valid_after_run", "duplicated_work"}
        <= set(validity_record)
        and _prod_4x4_record_valid(validation_probe)
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


def _rule_list(value: Any) -> list[Dict[str, Any]]:
    normalized = []
    if not isinstance(value, list):
        return normalized
    for entry in value:
        if isinstance(entry, Mapping):
            normalized.append(dict(entry))
    return normalized


def _record_excerpt(record: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(record, Mapping):
        return {}
    excerpt = {}
    for field in (
        "label",
        "process_count",
        "worker_count_per_process",
        "completed",
        "return_code",
        "campaign_valid_after_run",
        "duplicated_work",
    ):
        if field in record:
            excerpt[field] = record.get(field)
    return excerpt


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _load_json_mapping(path: Optional[Path]) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if path is None or not path.exists():
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


def _resolve_acceptance_artifact_path(project_root: Path, raw_path: str) -> Path:
    raw_text = str(raw_path).strip()
    if _looks_like_windows_absolute_path(raw_text):
        candidates = _project_local_mirror_candidates_from_parts(
            project_root,
            list(PureWindowsPath(raw_text).parts),
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    path = Path(raw_text)
    if not path.is_absolute():
        return (project_root / path).resolve()
    candidates = _project_local_mirror_candidates(project_root, path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return path.resolve()


def _project_local_mirror_candidates(project_root: Path, absolute_path: Path) -> list[Path]:
    return _project_local_mirror_candidates_from_parts(project_root, list(absolute_path.parts))


def _project_local_mirror_candidates_from_parts(
    project_root: Path,
    normalized_parts: list[str],
) -> list[Path]:
    candidates: list[Path] = []
    for marker in [".codex_test_logs", ".artifacts"]:
        if marker in normalized_parts:
            marker_index = normalized_parts.index(marker)
            candidates.append(project_root.joinpath(*normalized_parts[marker_index:]))
    if "endfield_phase3b_project_current" in normalized_parts:
        root_index = normalized_parts.index("endfield_phase3b_project_current")
        suffix = normalized_parts[root_index + 1 :]
        if suffix:
            candidates.append(project_root.joinpath(*suffix))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _looks_like_windows_absolute_path(raw_path: str) -> bool:
    return (
        len(raw_path) >= 3
        and raw_path[1] == ":"
        and raw_path[2] in ("\\", "/")
        and raw_path[0].isalpha()
    )


def _display_path(project_root: Path, path: Optional[Path]) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

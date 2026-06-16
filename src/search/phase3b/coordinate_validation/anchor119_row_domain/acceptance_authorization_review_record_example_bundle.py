from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_record_scaffold import (
    ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE,
)
from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_record_validator import (
    ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
    _display_path,
    _load_json_mapping,
    _mapping,
    _mapping_list,
    _markdown_cell,
    _render_value,
    _resolve_path,
    _review_only_contract_retained,
    _string_list,
    _validate_authorization_grant_consistency_with_missing_prerequisites,
    _validate_completed_review_state,
    _validate_locked_execution_target_rule,
    _validate_required_field_rule,
    _validate_required_ids_rule,
)

ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_example_bundle_v1"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_scaffold_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_scaffold.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_"
    "acceptance_authorization_review_record_validator_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_validator.json"
)
INLINE_SYNTHETIC_EXAMPLE_PAYLOAD_PATH = (
    "inline://anchor119_acceptance_authorization_review_record_example_payload"
)
SYNTHETIC_REVIEWER_ID = "synthetic_example_reviewer_anchor119"
SYNTHETIC_REVIEWED_AT = "2026-04-24T12:00:00Z"
SYNTHETIC_VERDICT = "blocked_until_reviewed_runtime_patch_exists"
SYNTHETIC_NOTES = (
    "Synthetic example/demo payload only for artifact-backed validation replay. "
    "This is not an actual human authorization review record, does not authorize "
    "execution, does not enable runtime, and does not execute acceptance."
)
EXAMPLE_ONLY_NOTES = [
    "Synthetic example/demo payload only; not an actual human authorization review record.",
    "Validation replay confirms contract compatibility only; it is not execution authorization.",
    "acceptance_execution_authorized=false, runtime_enablement_allowed=false, and acceptance_executed=false remain locked here.",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle(
    project_root: Path,
    *,
    acceptance_authorization_review_record_scaffold_path: Optional[Path] = None,
    acceptance_authorization_review_record_validator_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    scaffold_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_record_scaffold_path
        if acceptance_authorization_review_record_scaffold_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_PATH,
    )
    validator_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_record_validator_path
        if acceptance_authorization_review_record_validator_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH,
    )

    scaffold_report, scaffold_error = _load_json_mapping(scaffold_resolved)
    validator_report, validator_error = _load_json_mapping(validator_resolved)

    scaffold_meta = _mapping(scaffold_report.get("metadata")) if scaffold_report else {}
    scaffold_status = _mapping(scaffold_report.get("status")) if scaffold_report else {}
    scaffold = (
        _mapping(
            scaffold_report.get("acceptance_authorization_review_record_scaffold")
        )
        if scaffold_report
        else {}
    )
    validator_meta = (
        _mapping(validator_report.get("metadata")) if validator_report else {}
    )
    validator_status = (
        _mapping(validator_report.get("status")) if validator_report else {}
    )
    validator = (
        _mapping(
            validator_report.get("acceptance_authorization_review_record_validator")
        )
        if validator_report
        else {}
    )
    validator_paths = _mapping(validator_report.get("paths")) if validator_report else {}

    candidate = _first_mapping(
        scaffold_report.get("candidate") if scaffold_report else None,
        validator_report.get("candidate") if validator_report else None,
    )

    scaffold_present = bool(
        scaffold_report is not None
        and scaffold_error is None
        and scaffold_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE
    )
    validator_present = bool(
        validator_report is not None
        and validator_error is None
        and validator_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE
    )
    scaffold_ready = bool(
        scaffold_status.get(
            "acceptance_authorization_review_record_scaffold_ready", False
        )
    )
    validator_ready = bool(
        validator_status.get(
            "acceptance_authorization_review_record_validator_ready", False
        )
    )
    review_only_contract_retained = _review_only_contract_retained(
        scaffold_meta,
        validator_meta,
    )
    acceptance_execution_authorized = any(
        bool(value)
        for value in [
            scaffold_status.get("acceptance_execution_authorized", False),
            validator_status.get("acceptance_execution_authorized", False),
        ]
    )
    runtime_enablement_allowed = any(
        bool(value)
        for value in [
            scaffold_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
        ]
    )
    acceptance_executed = any(
        bool(value)
        for value in [
            scaffold_status.get("acceptance_executed", False),
            validator_status.get("acceptance_executed", False),
            scaffold_meta.get("acceptance_executed", False),
            validator_meta.get("acceptance_executed", False),
        ]
    )

    scaffold_payload = _mapping(
        scaffold.get("scaffolded_authorization_review_record_payload")
    )
    required_review_conclusions = _mapping_list(
        validator.get("required_review_conclusions")
    )
    required_runtime_patch_statement_ids = _string_list(
        validator.get("required_runtime_patch_statement_ids")
    )
    missing_prerequisites = _mapping_list(validator.get("missing_prerequisites"))
    validator_rules = _mapping(validator.get("validator_rules"))
    required_field_rules = _mapping_list(validator_rules.get("required_fields"))
    required_conclusion_ids_rule = _mapping(
        validator_rules.get("required_conclusion_ids")
    )
    required_runtime_patch_statement_ids_rule = _mapping(
        validator_rules.get("required_runtime_patch_statement_ids")
    )
    missing_prerequisite_gate_ids_rule = _mapping(
        validator_rules.get("missing_prerequisite_gate_ids")
    )
    locked_execution_target_rule = _mapping(
        validator_rules.get("locked_execution_target")
    )
    locked_execution_target = _mapping(validator.get("locked_execution_target"))
    future_validation_checklist = _mapping_list(
        validator.get("future_validation_checklist")
    )
    still_blocked_gate_ids = _string_list(
        validator_report.get("still_blocked_gate_ids") if validator_report else []
    )
    if not still_blocked_gate_ids:
        still_blocked_gate_ids = _string_list(
            validator_status.get("missing_prerequisite_gate_ids")
        )

    validator_rules_ready = bool(
        required_field_rules
        and required_conclusion_ids_rule
        and required_runtime_patch_statement_ids_rule
        and missing_prerequisite_gate_ids_rule
        and locked_execution_target_rule
    )
    synthetic_example_payload_created = bool(
        scaffold_present
        and validator_present
        and scaffold_ready
        and validator_ready
        and bool(scaffold_payload)
        and validator_rules_ready
        and review_only_contract_retained
        and not acceptance_execution_authorized
        and not runtime_enablement_allowed
        and not acceptance_executed
    )

    if synthetic_example_payload_created:
        synthetic_payload = _build_synthetic_completed_example_payload(
            scaffold_payload=scaffold_payload,
            locked_execution_target_rule=locked_execution_target_rule,
            required_conclusion_ids_rule=required_conclusion_ids_rule,
            required_runtime_patch_statement_ids_rule=(
                required_runtime_patch_statement_ids_rule
            ),
            missing_prerequisite_gate_ids_rule=missing_prerequisite_gate_ids_rule,
        )
        replayed_validation = _replay_existing_validator_logic(
            payload=synthetic_payload,
            required_field_rules=required_field_rules,
            required_conclusion_ids_rule=required_conclusion_ids_rule,
            required_runtime_patch_statement_ids_rule=(
                required_runtime_patch_statement_ids_rule
            ),
            missing_prerequisite_gate_ids_rule=missing_prerequisite_gate_ids_rule,
            locked_execution_target_rule=locked_execution_target_rule,
        )
    else:
        synthetic_payload = {}
        replayed_validation = _not_run_validation(
            scaffold_present=scaffold_present,
            validator_present=validator_present,
            scaffold_ready=scaffold_ready,
            validator_ready=validator_ready,
            scaffold_payload_present=bool(scaffold_payload),
            validator_rules_ready=validator_rules_ready,
            review_only_contract_retained=review_only_contract_retained,
            acceptance_execution_authorized=acceptance_execution_authorized,
            runtime_enablement_allowed=runtime_enablement_allowed,
            acceptance_executed=acceptance_executed,
        )

    replayed_validation_passed = bool(
        replayed_validation.get("record_payload_validated", False)
    )
    acceptance_authorization_review_record_example_bundle_ready = bool(
        synthetic_example_payload_created and replayed_validation_passed
    )

    if acceptance_authorization_review_record_example_bundle_ready:
        recommended_next_step = (
            "review_example_bundle_only_do_not_treat_as_execution_authorization"
        )
        handoff_recommendation = (
            "The synthetic example bundle replayed the existing validator logic "
            "successfully against a completed demo payload. This remains review-only, "
            "default-off, spec-only, no-solve, and proof-preserving; it does not "
            "authorize execution, does not enable runtime, and does not execute "
            "acceptance."
        )
    else:
        recommended_next_step = (
            "repair_acceptance_authorization_review_record_example_bundle_inputs"
        )
        handoff_recommendation = (
            "The example bundle could not be assembled or replay-validated because "
            "the upstream scaffold/validator contract is missing, blocked, or no "
            "longer review-only/default-off. Repair those inputs before relying on "
            "this demo artifact."
        )

    checks = [
        _check(
            "acceptance_authorization_review_record_scaffold_present",
            "pass" if scaffold_present else "fail",
            "acceptance authorization review record scaffold loaded"
            if scaffold_present
            else _presence_detail(
                scaffold_report,
                scaffold_error,
                scaffold_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE,
                project_root,
                scaffold_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_record_validator_present",
            "pass" if validator_present else "fail",
            "acceptance authorization review record validator loaded"
            if validator_present
            else _presence_detail(
                validator_report,
                validator_error,
                validator_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
                project_root,
                validator_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_record_scaffold_ready",
            "pass" if scaffold_ready else "fail",
            str(scaffold_ready),
        ),
        _check(
            "acceptance_authorization_review_record_validator_ready",
            "pass" if validator_ready else "fail",
            str(validator_ready),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "upstream scaffold and validator remain review-only/default-off/spec-only/no-solve"
            if review_only_contract_retained
            else "expected upstream scaffold and validator metadata to remain review-only/default-off/spec-only/no-solve",
        ),
        _check(
            "scaffold_payload_present",
            "pass" if bool(scaffold_payload) else "fail",
            "scaffolded authorization review record payload present"
            if scaffold_payload
            else "missing scaffolded authorization review record payload",
        ),
        _check(
            "validator_rules_ready",
            "pass" if validator_rules_ready else "fail",
            "validator rules present for required fields, ids, and locked execution target"
            if validator_rules_ready
            else "validator rule snapshot incomplete",
        ),
        _check(
            "acceptance_execution_authorized_still_false",
            "pass" if not acceptance_execution_authorized else "fail",
            f"acceptance_execution_authorized={acceptance_execution_authorized}",
        ),
        _check(
            "runtime_enablement_allowed_still_false",
            "pass" if not runtime_enablement_allowed else "fail",
            f"runtime_enablement_allowed={runtime_enablement_allowed}",
        ),
        _check(
            "acceptance_executed_still_false",
            "pass" if not acceptance_executed else "fail",
            f"acceptance_executed={acceptance_executed}",
        ),
        _check(
            "synthetic_example_payload_created",
            "pass" if synthetic_example_payload_created else "fail",
            "synthetic completed example payload assembled"
            if synthetic_example_payload_created
            else "synthetic example payload not assembled",
        ),
        _check(
            "replayed_validation_passed",
            "pass" if replayed_validation_passed else "fail",
            str(replayed_validation.get("detail")),
        ),
    ]

    gates = [
        _gate(
            "acceptance_authorization_review_record_scaffold_ready",
            scaffold_ready,
            True,
            "The example bundle depends on the upstream scaffold already being ready.",
        ),
        _gate(
            "acceptance_authorization_review_record_validator_ready",
            validator_ready,
            True,
            "The example bundle depends on the upstream validator already being ready.",
        ),
        _gate(
            "review_only_contract_retained",
            review_only_contract_retained,
            True,
            "The example bundle is review-only/default-off/spec-only and must stay that way.",
        ),
        _gate(
            "synthetic_example_payload_replay_validated",
            replayed_validation_passed,
            True,
            str(replayed_validation.get("detail")),
        ),
        _gate(
            "acceptance_execution_not_authorized",
            not acceptance_execution_authorized,
            True,
            "The example bundle never authorizes execution.",
        ),
        _gate(
            "runtime_enablement_not_allowed",
            not runtime_enablement_allowed,
            True,
            "The example bundle never enables runtime.",
        ),
        _gate(
            "acceptance_not_executed",
            not acceptance_executed,
            True,
            "The example bundle never executes acceptance.",
        ),
    ]

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_review_record_example_bundle_"
                "review_only_demo_not_execution_authorization"
            ),
            "spec_only": True,
            "review_only": True,
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
            "acceptance_authorization_review_record_scaffold": _display_path(
                project_root, scaffold_resolved
            ),
            "acceptance_authorization_review_record_validator": _display_path(
                project_root, validator_resolved
            ),
            "inline_synthetic_example_payload": INLINE_SYNTHETIC_EXAMPLE_PAYLOAD_PATH,
            "exact_future_acceptance_command": locked_execution_target.get(
                "exact_future_acceptance_command"
            )
            or validator_paths.get("exact_future_acceptance_command"),
            "exact_future_acceptance_result_path": locked_execution_target.get(
                "exact_future_acceptance_result_path"
            )
            or validator_paths.get("exact_future_acceptance_result_path"),
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_authorization_review_record_example_bundle_ready": bool(
                acceptance_authorization_review_record_example_bundle_ready
            ),
            "synthetic_example_payload_created": bool(
                synthetic_example_payload_created
            ),
            "synthetic_example_payload_validated": bool(
                replayed_validation_passed
            ),
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_authorization_review_record_example_bundle": {
            "bundle_target": (
                "synthetic_completed_acceptance_execution_authorization_review_record_example"
            ),
            "target_record_type": validator.get("target_record_type")
            or scaffold_payload.get("record_type"),
            "scope": validator.get("scope"),
            "review_only": True,
            "default_off": True,
            "spec_only": True,
            "solver_invoked": False,
            "proof_source": False,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "example_only_notes": list(EXAMPLE_ONLY_NOTES),
            "locked_execution_target": dict(locked_execution_target),
            "required_review_conclusions": list(required_review_conclusions),
            "required_runtime_patch_statement_ids": list(
                required_runtime_patch_statement_ids
            ),
            "missing_prerequisites": list(missing_prerequisites),
            "future_validation_checklist": list(future_validation_checklist),
            "synthetic_completed_authorization_review_record_payload": dict(
                synthetic_payload
            ),
            "replayed_validation": replayed_validation,
            "validator_rule_snapshot": dict(validator_rules),
            "validator_notice": validator.get("validator_notice"),
        },
        "still_blocked_gate_ids": list(still_blocked_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(
        report.get("acceptance_authorization_review_record_example_bundle")
    )
    replayed_validation = _mapping(bundle.get("replayed_validation"))
    locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    synthetic_payload = _mapping(
        bundle.get("synthetic_completed_authorization_review_record_payload")
    )
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Review Record Example Bundle",
        "",
        f"- Example bundle ready: `{status.get('acceptance_authorization_review_record_example_bundle_ready')}`",
        f"- Synthetic example payload created: `{status.get('synthetic_example_payload_created')}`",
        f"- Synthetic example payload validated: `{status.get('synthetic_example_payload_validated')}`",
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Example-Only Notes",
        "",
    ]
    for note in list(bundle.get("example_only_notes", [])):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Locked Execution Target",
            "",
            f"- Production profile id: `{locked_execution_target.get('production_profile_id')}`",
            f"- Default production runner: `{locked_execution_target.get('default_production_runner')}`",
            f"- Exact future acceptance command: `{locked_execution_target.get('exact_future_acceptance_command')}`",
            f"- Exact future acceptance result path: `{locked_execution_target.get('exact_future_acceptance_result_path')}`",
            "",
            "## Synthetic Completed Example Payload",
            "",
            "```json",
            json.dumps(synthetic_payload, indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Replayed Validation Summary",
            "",
            f"- Validation logic source: `{replayed_validation.get('validation_logic_source')}`",
            f"- Replay mode: `{replayed_validation.get('replay_mode')}`",
            f"- Validation status: `{replayed_validation.get('validation_status')}`",
            f"- Record payload validated: `{replayed_validation.get('record_payload_validated')}`",
            f"- Completed review state validated: `{replayed_validation.get('validated_authorization_review_completed')}`",
            f"- Failed rule count: `{replayed_validation.get('failed_rule_count')}`",
            f"- Detail: {replayed_validation.get('detail')}",
            "",
            "## Replayed Validation Rule Results",
            "",
        ]
    )
    per_rule_results = _mapping_list(replayed_validation.get("per_rule_results"))
    if per_rule_results:
        lines.extend(
            [
                "| Rule | Status | Field | Validation rule | Observed | Expected | Detail |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in per_rule_results:
            lines.append(
                f"| {_markdown_cell(entry.get('rule_id'))} | "
                f"{_markdown_cell(entry.get('status'))} | "
                f"{_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('validation_rule'))} | "
                f"{_markdown_cell(_render_value(entry.get('observed_value')))} | "
                f"{_markdown_cell(_render_value(entry.get('expected_value')))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
        lines.append("")
    else:
        lines.extend(
            [
                "- Replayed validation did not run.",
                "",
            ]
        )
    lines.extend(
        [
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(
        report.get("acceptance_authorization_review_record_example_bundle")
    )
    replayed_validation = _mapping(bundle.get("replayed_validation"))
    locked_execution_target = _mapping(bundle.get("locked_execution_target"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization review record example bundle",
            "acceptance_authorization_review_record_example_bundle_ready="
            + str(
                status.get(
                    "acceptance_authorization_review_record_example_bundle_ready",
                    False,
                )
            ),
            "synthetic_example_payload_created="
            + str(status.get("synthetic_example_payload_created", False)),
            "synthetic_example_payload_validated="
            + str(status.get("synthetic_example_payload_validated", False)),
            "acceptance_execution_authorized="
            + str(status.get("acceptance_execution_authorized", False)),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed", False)),
            "acceptance_executed="
            + str(status.get("acceptance_executed", False)),
            "target_record_type=" + str(bundle.get("target_record_type")),
            "production_profile_id="
            + str(locked_execution_target.get("production_profile_id")),
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(locked_execution_target.get("exact_future_acceptance_result_path")),
            "replayed_validation_status="
            + str(replayed_validation.get("validation_status")),
            "replayed_validation_failed_rule_count="
            + str(replayed_validation.get("failed_rule_count")),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = (
        "anchor119_row_domain_acceptance_authorization_review_record_example_bundle"
    ),
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_synthetic_completed_example_payload(
    *,
    scaffold_payload: Mapping[str, Any],
    locked_execution_target_rule: Mapping[str, Any],
    required_conclusion_ids_rule: Mapping[str, Any],
    required_runtime_patch_statement_ids_rule: Mapping[str, Any],
    missing_prerequisite_gate_ids_rule: Mapping[str, Any],
) -> Dict[str, Any]:
    payload = deepcopy(dict(scaffold_payload))
    expected_target = _mapping(locked_execution_target_rule.get("expected_target"))
    if expected_target:
        payload["locked_execution_target"] = dict(expected_target)
    payload["reviewer_id"] = SYNTHETIC_REVIEWER_ID
    payload["reviewed_at"] = SYNTHETIC_REVIEWED_AT
    payload["verdict"] = SYNTHETIC_VERDICT
    payload["authorization_granted"] = False
    payload["authorization_review_completed"] = True
    payload["runtime_enablement_allowed"] = False
    payload["acceptance_executed"] = False
    payload["required_conclusion_ids"] = _string_list(
        required_conclusion_ids_rule.get("required_ids")
    )
    payload["required_runtime_patch_statement_ids"] = _string_list(
        required_runtime_patch_statement_ids_rule.get("required_ids")
    )
    payload["missing_prerequisite_gate_ids"] = _string_list(
        missing_prerequisite_gate_ids_rule.get("required_ids")
    )
    payload["notes"] = SYNTHETIC_NOTES
    return payload


def _replay_existing_validator_logic(
    *,
    payload: Mapping[str, Any],
    required_field_rules: list[Mapping[str, Any]],
    required_conclusion_ids_rule: Mapping[str, Any],
    required_runtime_patch_statement_ids_rule: Mapping[str, Any],
    missing_prerequisite_gate_ids_rule: Mapping[str, Any],
    locked_execution_target_rule: Mapping[str, Any],
) -> Dict[str, Any]:
    results = []
    for rule in required_field_rules:
        if isinstance(rule, Mapping):
            results.append(_validate_required_field_rule(rule, payload))
    results.append(
        _validate_required_ids_rule(
            required_conclusion_ids_rule,
            payload,
            allow_extra_ids=True,
        )
    )
    results.append(
        _validate_required_ids_rule(
            required_runtime_patch_statement_ids_rule,
            payload,
            allow_extra_ids=True,
        )
    )
    results.append(
        _validate_required_ids_rule(
            missing_prerequisite_gate_ids_rule,
            payload,
            allow_extra_ids=False,
        )
    )
    results.append(
        _validate_locked_execution_target_rule(locked_execution_target_rule, payload)
    )
    completion_result = _validate_completed_review_state(payload)
    results.append(completion_result)
    grant_consistency_result = (
        _validate_authorization_grant_consistency_with_missing_prerequisites(
            payload,
            missing_prerequisite_gate_ids_rule,
        )
    )
    results.append(grant_consistency_result)

    failed_rule_ids = [
        str(entry.get("rule_id"))
        for entry in results
        if str(entry.get("status")) == "fail"
    ]
    failed_rule_count = len(failed_rule_ids)
    passed_rule_count = sum(
        1 for entry in results if str(entry.get("status")) == "pass"
    )
    record_payload_validated = failed_rule_count == 0
    payload_claimed_authorization_review_completed = bool(
        completion_result.get("observed_value")
    )
    validated_authorization_review_completed = bool(
        record_payload_validated and completion_result.get("status") == "pass"
    )
    if record_payload_validated:
        detail = (
            "The synthetic acceptance-authorization review record example payload "
            f"satisfied all {passed_rule_count} validation rules from the existing "
            "validator contract. This confirms review-only contract compatibility "
            "only; it does not authorize execution, does not enable runtime, and "
            "does not execute acceptance."
        )
        validation_status = "passed"
    else:
        detail = (
            "The synthetic acceptance-authorization review record example payload "
            f"failed {failed_rule_count} validation rule(s) from the existing "
            "validator contract. This still does not authorize execution, does not "
            "enable runtime, and does not execute acceptance."
        )
        validation_status = "failed"
    return {
        "validation_logic_source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
        "replay_mode": "in_memory_reuse_of_existing_validator_rules",
        "record_payload_path": INLINE_SYNTHETIC_EXAMPLE_PAYLOAD_PATH,
        "record_payload_provided": True,
        "record_payload_loaded": True,
        "record_payload_validated": bool(record_payload_validated),
        "validation_status": validation_status,
        "payload_claimed_authorization_review_completed": bool(
            payload_claimed_authorization_review_completed
        ),
        "validated_authorization_review_completed": bool(
            validated_authorization_review_completed
        ),
        "completion_state_rule_passed": bool(
            completion_result.get("status") == "pass"
        ),
        "completion_state_detail": str(completion_result.get("detail")),
        "failed_rule_count": failed_rule_count,
        "failed_rule_ids": failed_rule_ids,
        "per_rule_results": results,
        "detail": detail,
    }


def _not_run_validation(
    *,
    scaffold_present: bool,
    validator_present: bool,
    scaffold_ready: bool,
    validator_ready: bool,
    scaffold_payload_present: bool,
    validator_rules_ready: bool,
    review_only_contract_retained: bool,
    acceptance_execution_authorized: bool,
    runtime_enablement_allowed: bool,
    acceptance_executed: bool,
) -> Dict[str, Any]:
    reasons = []
    if not scaffold_present:
        reasons.append("scaffold missing")
    if not validator_present:
        reasons.append("validator missing")
    if scaffold_present and not scaffold_ready:
        reasons.append("scaffold not ready")
    if validator_present and not validator_ready:
        reasons.append("validator not ready")
    if scaffold_present and not scaffold_payload_present:
        reasons.append("scaffold payload missing")
    if validator_present and not validator_rules_ready:
        reasons.append("validator rules incomplete")
    if not review_only_contract_retained:
        reasons.append("review-only/default-off/spec-only contract not retained")
    if acceptance_execution_authorized:
        reasons.append("acceptance_execution_authorized unexpectedly true upstream")
    if runtime_enablement_allowed:
        reasons.append("runtime_enablement_allowed unexpectedly true upstream")
    if acceptance_executed:
        reasons.append("acceptance_executed unexpectedly true upstream")
    reason_text = "; ".join(reasons) if reasons else "unknown prerequisite failure"
    return {
        "validation_logic_source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
        "replay_mode": "not_run",
        "record_payload_path": INLINE_SYNTHETIC_EXAMPLE_PAYLOAD_PATH,
        "record_payload_provided": False,
        "record_payload_loaded": False,
        "record_payload_validated": False,
        "validation_status": "not_run",
        "payload_claimed_authorization_review_completed": False,
        "validated_authorization_review_completed": False,
        "completion_state_rule_passed": False,
        "completion_state_detail": "Validation replay did not run.",
        "failed_rule_count": 0,
        "failed_rule_ids": [],
        "per_rule_results": [],
        "detail": (
            "The example payload replay did not run because upstream scaffold and/or "
            "validator prerequisites were not satisfied: "
            + reason_text
            + "."
        ),
    }


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _presence_detail(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
    metadata: Mapping[str, Any],
    expected_source: str,
    project_root: Path,
    path: Path,
) -> str:
    if error:
        return str(error)
    if report is not None:
        return f"unexpected_source:{metadata.get('source')} expected:{expected_source}"
    return f"missing:{_display_path(project_root, path)}"


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }

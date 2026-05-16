from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_v1"
)
ACCEPTANCE_EXECUTION_GATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
)
ACCEPTANCE_RESULT_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_v1"
)
LOCKED_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_bundle.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_20260424/"
    "anchor119_row_domain_acceptance_execution_gate.json"
)
DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_20260424/"
    "anchor119_row_domain_acceptance_result_validator.json"
)
SCAFFOLD_NOTICE = (
    "Pending scaffold only; this artifact is not an actual acceptance-authorization "
    "review record, does not authorize execution, does not enable runtime, and does "
    "not execute acceptance."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold(
    project_root: Path,
    *,
    acceptance_authorization_review_bundle_path: Optional[Path] = None,
    acceptance_execution_gate_path: Optional[Path] = None,
    acceptance_result_validator_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    acceptance_authorization_review_bundle_resolved = _resolve_path(
        project_root,
        acceptance_authorization_review_bundle_path
        if acceptance_authorization_review_bundle_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_PATH,
    )
    acceptance_execution_gate_resolved = _resolve_path(
        project_root,
        acceptance_execution_gate_path
        if acceptance_execution_gate_path is not None
        else DEFAULT_ACCEPTANCE_EXECUTION_GATE_PATH,
    )
    acceptance_result_validator_resolved = _resolve_path(
        project_root,
        acceptance_result_validator_path
        if acceptance_result_validator_path is not None
        else DEFAULT_ACCEPTANCE_RESULT_VALIDATOR_PATH,
    )

    acceptance_authorization_review_bundle_report, bundle_error = _load_json_mapping(
        acceptance_authorization_review_bundle_resolved
    )
    acceptance_execution_gate_report, gate_error = _load_json_mapping(
        acceptance_execution_gate_resolved
    )
    acceptance_result_validator_report, validator_error = _load_json_mapping(
        acceptance_result_validator_resolved
    )

    bundle_meta = (
        _mapping(acceptance_authorization_review_bundle_report.get("metadata"))
        if acceptance_authorization_review_bundle_report
        else {}
    )
    bundle_status = (
        _mapping(acceptance_authorization_review_bundle_report.get("status"))
        if acceptance_authorization_review_bundle_report
        else {}
    )
    acceptance_authorization_review_bundle = (
        _mapping(
            acceptance_authorization_review_bundle_report.get(
                "acceptance_authorization_review_bundle"
            )
        )
        if acceptance_authorization_review_bundle_report
        else {}
    )
    gate_meta = (
        _mapping(acceptance_execution_gate_report.get("metadata"))
        if acceptance_execution_gate_report
        else {}
    )
    gate_status = (
        _mapping(acceptance_execution_gate_report.get("status"))
        if acceptance_execution_gate_report
        else {}
    )
    acceptance_execution_gate = (
        _mapping(acceptance_execution_gate_report.get("acceptance_execution_gate"))
        if acceptance_execution_gate_report
        else {}
    )
    validator_meta = (
        _mapping(acceptance_result_validator_report.get("metadata"))
        if acceptance_result_validator_report
        else {}
    )
    validator_status = (
        _mapping(acceptance_result_validator_report.get("status"))
        if acceptance_result_validator_report
        else {}
    )
    acceptance_result_validator = (
        _mapping(
            acceptance_result_validator_report.get("acceptance_result_validator")
        )
        if acceptance_result_validator_report
        else {}
    )

    candidate = _first_mapping(
        acceptance_authorization_review_bundle_report.get("candidate")
        if acceptance_authorization_review_bundle_report
        else None,
        acceptance_execution_gate_report.get("candidate")
        if acceptance_execution_gate_report
        else None,
        acceptance_result_validator_report.get("candidate")
        if acceptance_result_validator_report
        else None,
    )

    acceptance_authorization_review_bundle_present = bool(
        acceptance_authorization_review_bundle_report is not None
        and bundle_error is None
        and bundle_meta.get("source")
        == ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE
    )
    acceptance_execution_gate_present = bool(
        acceptance_execution_gate_report is not None
        and gate_error is None
        and gate_meta.get("source") == ACCEPTANCE_EXECUTION_GATE_SOURCE
    )
    acceptance_result_validator_present = bool(
        acceptance_result_validator_report is not None
        and validator_error is None
        and validator_meta.get("source") == ACCEPTANCE_RESULT_VALIDATOR_SOURCE
    )

    acceptance_authorization_review_bundle_ready = bool(
        bundle_status.get("acceptance_authorization_review_bundle_ready", False)
    )
    acceptance_execution_gate_ready = bool(
        gate_status.get("acceptance_execution_gate_ready", False)
    )
    acceptance_result_validator_ready = bool(
        validator_status.get("acceptance_result_validator_ready", False)
    )

    future_manual_authorization_review_prerequisites_reported_ready = bool(
        bundle_status.get(
            "future_execution_authorization_review_prerequisites_met", False
        )
    )
    reviewed_runtime_patch_exists = bool(
        bundle_status.get("reviewed_runtime_patch_exists", False)
        or gate_status.get("reviewed_runtime_patch_exists", False)
    )
    acceptance_execution_authorized = any(
        bool(value)
        for value in [
            bundle_status.get("acceptance_execution_authorized", False),
            gate_status.get("acceptance_execution_authorized", False),
        ]
    )
    runtime_enablement_still_blocked = all(
        not bool(value)
        for value in [
            bundle_status.get("runtime_enablement_allowed", False),
            gate_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
        ]
    )
    acceptance_executed = any(
        bool(value)
        for value in [
            bundle_status.get("acceptance_executed", False),
            gate_status.get("acceptance_executed", False),
            bundle_meta.get("acceptance_executed", False),
            gate_meta.get("acceptance_executed", False),
            validator_meta.get("acceptance_executed", False),
        ]
    )

    future_authorization_review_record_template = _mapping(
        acceptance_authorization_review_bundle.get(
            "future_authorization_review_record_template"
        )
    )
    bundle_locked_execution_target = _mapping(
        acceptance_authorization_review_bundle.get("locked_execution_target")
    )
    gate_locked_execution_target = _mapping(
        acceptance_execution_gate.get("locked_execution_target")
    )
    template_locked_execution_target = _mapping(
        future_authorization_review_record_template.get("locked_execution_target")
    )

    production_profile_id, production_profile_locked = _locked_value(
        [
            template_locked_execution_target.get("production_profile_id"),
            bundle_locked_execution_target.get("production_profile_id"),
            gate_locked_execution_target.get("production_profile_id"),
            acceptance_execution_gate.get("production_profile_id"),
            acceptance_result_validator.get("production_profile_id"),
        ]
    )
    default_production_runner, default_production_runner_locked = _locked_value(
        [
            template_locked_execution_target.get("default_production_runner"),
            bundle_locked_execution_target.get("default_production_runner"),
            gate_locked_execution_target.get("default_production_runner"),
        ],
        normalize=_normalize_path_text,
    )
    exact_future_acceptance_command, exact_future_acceptance_command_locked = (
        _locked_value(
            [
                template_locked_execution_target.get("exact_future_acceptance_command"),
                bundle_locked_execution_target.get("exact_future_acceptance_command"),
                gate_locked_execution_target.get("exact_future_acceptance_command"),
            ],
            normalize=_normalize_command_text,
        )
    )
    exact_future_acceptance_result_path, exact_future_acceptance_result_path_locked = (
        _locked_value(
            [
                template_locked_execution_target.get(
                    "exact_future_acceptance_result_path"
                ),
                bundle_locked_execution_target.get(
                    "exact_future_acceptance_result_path"
                ),
                gate_locked_execution_target.get(
                    "exact_future_acceptance_result_path"
                ),
                acceptance_result_validator.get("expected_result_path"),
            ],
            normalize=_normalize_path_text,
        )
    )
    command_output_path = _extract_suite_output_path(exact_future_acceptance_command)
    command_matches_result_path = bool(
        exact_future_acceptance_result_path
        and command_output_path
        and _normalize_path_text(exact_future_acceptance_result_path)
        == _normalize_path_text(command_output_path)
    )
    production_profile_locked_prod_4x4_normal = bool(
        production_profile_locked and production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
    )
    locked_execution_target_present = bool(
        production_profile_id == LOCKED_PRODUCTION_PROFILE_ID
        and exact_future_acceptance_command
        and exact_future_acceptance_result_path
    )
    locked_execution_target_consistent = bool(
        production_profile_locked_prod_4x4_normal
        and default_production_runner_locked
        and exact_future_acceptance_command_locked
        and exact_future_acceptance_result_path_locked
        and command_matches_result_path
    )

    required_review_conclusions = _mapping_list(
        acceptance_authorization_review_bundle.get(
            "required_review_conclusions_before_future_execution_authorization_review"
        )
    )
    required_conclusion_ids = [
        str(entry.get("conclusion_id"))
        for entry in required_review_conclusions
        if str(entry.get("conclusion_id") or "").strip()
    ]
    required_runtime_patch_statement_ids = _string_list(
        future_authorization_review_record_template.get(
            "required_runtime_patch_statement_ids"
        )
    )
    if not required_runtime_patch_statement_ids:
        required_runtime_patch_statement_ids = _string_list(
            _mapping(
                acceptance_authorization_review_bundle.get(
                    "reviewed_runtime_patch_state"
                )
            ).get("required_reviewer_statement_ids")
        )

    carry_forward_gate_entries = _merge_gate_entries(
        _blocked_gate_entries(acceptance_authorization_review_bundle_report),
        _blocked_gate_entries(acceptance_execution_gate_report),
    )
    missing_prerequisites = _build_missing_prerequisites(
        acceptance_authorization_review_bundle.get(
            "current_missing_prerequisites_before_future_execution_authorization_review"
        ),
        carry_forward_gate_entries=carry_forward_gate_entries,
        bundle_reported_missing_gate_ids=_string_list(
            bundle_status.get("missing_prerequisite_gate_ids")
        ),
        gate_reported_missing_gate_ids=_string_list(
            gate_status.get("missing_prerequisite_gate_ids")
        ),
    )
    missing_prerequisite_gate_ids = [
        str(entry.get("gate_id"))
        for entry in missing_prerequisites
        if str(entry.get("gate_id") or "").strip()
    ]

    scaffolded_authorization_review_record_payload = (
        _build_scaffolded_authorization_review_record_payload(
            future_authorization_review_record_template,
            production_profile_id=production_profile_id,
            default_production_runner=default_production_runner,
            exact_future_acceptance_command=exact_future_acceptance_command,
            exact_future_acceptance_result_path=exact_future_acceptance_result_path,
            required_conclusion_ids=required_conclusion_ids,
            required_runtime_patch_statement_ids=required_runtime_patch_statement_ids,
            missing_prerequisite_gate_ids=missing_prerequisite_gate_ids,
        )
    )
    required_record_fields = _build_required_record_fields(
        scaffolded_authorization_review_record_payload
    )
    future_validation_checklist = _mapping_list(
        acceptance_result_validator.get("future_validation_checklist")
    )

    template_present = bool(future_authorization_review_record_template)
    required_review_conclusions_present = bool(required_review_conclusions)
    scaffolded_payload_present = bool(scaffolded_authorization_review_record_payload)
    required_record_fields_present = bool(required_record_fields)
    pending_verdict_retained = bool(
        str(scaffolded_authorization_review_record_payload.get("verdict") or "").strip()
        == "pending"
    )
    authorization_granted_retained_false = bool(
        not scaffolded_authorization_review_record_payload.get(
            "authorization_granted", False
        )
        and not acceptance_execution_authorized
    )
    runtime_enablement_retained_false = bool(
        not scaffolded_authorization_review_record_payload.get(
            "runtime_enablement_allowed", False
        )
        and runtime_enablement_still_blocked
    )
    acceptance_executed_retained_false = bool(
        not scaffolded_authorization_review_record_payload.get("acceptance_executed", False)
        and not acceptance_executed
    )
    review_only_contract_retained = _review_only_contract_retained(
        bundle_meta,
        gate_meta,
        validator_meta,
    )

    checks = [
        _check(
            "acceptance_authorization_review_bundle_present",
            "pass" if acceptance_authorization_review_bundle_present else "fail",
            "acceptance authorization review bundle loaded"
            if acceptance_authorization_review_bundle_present
            else _presence_detail(
                acceptance_authorization_review_bundle_report,
                bundle_error,
                bundle_meta,
                ACCEPTANCE_AUTHORIZATION_REVIEW_BUNDLE_SOURCE,
                project_root,
                acceptance_authorization_review_bundle_resolved,
            ),
        ),
        _check(
            "acceptance_execution_gate_present",
            "pass" if acceptance_execution_gate_present else "fail",
            "acceptance execution gate loaded"
            if acceptance_execution_gate_present
            else _presence_detail(
                acceptance_execution_gate_report,
                gate_error,
                gate_meta,
                ACCEPTANCE_EXECUTION_GATE_SOURCE,
                project_root,
                acceptance_execution_gate_resolved,
            ),
        ),
        _check(
            "acceptance_result_validator_present",
            "pass" if acceptance_result_validator_present else "fail",
            "acceptance result validator loaded"
            if acceptance_result_validator_present
            else _presence_detail(
                acceptance_result_validator_report,
                validator_error,
                validator_meta,
                ACCEPTANCE_RESULT_VALIDATOR_SOURCE,
                project_root,
                acceptance_result_validator_resolved,
            ),
        ),
        _check(
            "acceptance_authorization_review_bundle_ready",
            "pass" if acceptance_authorization_review_bundle_ready else "fail",
            str(acceptance_authorization_review_bundle_ready),
        ),
        _check(
            "acceptance_execution_gate_ready",
            "pass" if acceptance_execution_gate_ready else "fail",
            str(acceptance_execution_gate_ready),
        ),
        _check(
            "acceptance_result_validator_ready",
            "pass" if acceptance_result_validator_ready else "fail",
            str(acceptance_result_validator_ready),
        ),
        _check(
            "future_authorization_review_record_template_present",
            "pass" if template_present else "fail",
            "future authorization review record template present"
            if template_present
            else "missing",
        ),
        _check(
            "required_review_conclusions_present",
            "pass" if required_review_conclusions_present else "fail",
            ",".join(required_conclusion_ids) if required_conclusion_ids else "missing",
        ),
        _check(
            "locked_execution_target_present",
            "pass" if locked_execution_target_present else "fail",
            (
                f"production_profile_id={production_profile_id or 'missing'} "
                f"exact_future_acceptance_command_present={bool(exact_future_acceptance_command)} "
                "exact_future_acceptance_result_path="
                f"{exact_future_acceptance_result_path or 'missing'}"
            ),
        ),
        _check(
            "locked_execution_target_consistent",
            "pass" if locked_execution_target_consistent else "fail",
            (
                "production_profile_locked="
                f"{production_profile_locked} "
                "default_production_runner_locked="
                f"{default_production_runner_locked} "
                "exact_future_acceptance_command_locked="
                f"{exact_future_acceptance_command_locked} "
                "exact_future_acceptance_result_path_locked="
                f"{exact_future_acceptance_result_path_locked} "
                f"command_matches_result_path={command_matches_result_path}"
            ),
        ),
        _check(
            "required_record_fields_present",
            "pass" if required_record_fields_present else "fail",
            str(required_record_fields_present),
        ),
        _check(
            "scaffolded_authorization_review_record_payload_present",
            "pass" if scaffolded_payload_present else "fail",
            "scaffold payload present" if scaffolded_payload_present else "missing",
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            str(review_only_contract_retained),
        ),
        _check(
            "authorization_granted_retained_false",
            "pass" if authorization_granted_retained_false else "fail",
            (
                "template_authorization_granted="
                f"{bool(scaffolded_authorization_review_record_payload.get('authorization_granted', False))} "
                f"upstream_acceptance_execution_authorized={acceptance_execution_authorized}"
            ),
        ),
        _check(
            "runtime_enablement_retained_false",
            "pass" if runtime_enablement_retained_false else "fail",
            (
                "template_runtime_enablement_allowed="
                f"{bool(scaffolded_authorization_review_record_payload.get('runtime_enablement_allowed', False))} "
                f"runtime_enablement_still_blocked={runtime_enablement_still_blocked}"
            ),
        ),
        _check(
            "acceptance_executed_retained_false",
            "pass" if acceptance_executed_retained_false else "fail",
            (
                "template_acceptance_executed="
                f"{bool(scaffolded_authorization_review_record_payload.get('acceptance_executed', False))} "
                f"acceptance_executed={acceptance_executed}"
            ),
        ),
        _check(
            "pending_verdict_retained",
            "pass" if pending_verdict_retained else "fail",
            str(scaffolded_authorization_review_record_payload.get("verdict")),
        ),
    ]

    gates = [
        _gate(
            "acceptance_authorization_review_bundle_ready",
            acceptance_authorization_review_bundle_ready,
            True,
            "The acceptance-authorization review bundle must already be ready before its future record scaffold can be emitted.",
        ),
        _gate(
            "acceptance_execution_gate_ready",
            acceptance_execution_gate_ready,
            True,
            "The acceptance execution gate must remain ready because the scaffold carries forward the locked prod_4x4_normal target from that gate.",
        ),
        _gate(
            "acceptance_result_validator_ready",
            acceptance_result_validator_ready,
            True,
            "The acceptance result validator must remain ready so the future authorized run still has a locked result-validation contract.",
        ),
        _gate(
            "required_review_conclusions_present",
            required_review_conclusions_present,
            True,
            "The scaffold must carry forward the required manual review conclusions from the acceptance-authorization review bundle.",
        ),
        _gate(
            "locked_prod_4x4_target_explicit",
            locked_execution_target_present,
            True,
            "The scaffold must make the locked prod_4x4_normal target, command, and result path explicit.",
        ),
        _gate(
            "locked_execution_target_consistent",
            locked_execution_target_consistent,
            True,
            "The scaffold must keep the bundle, gate, and validator aligned on the same locked future execution target.",
        ),
        _gate(
            "runtime_enablement_still_blocked",
            runtime_enablement_still_blocked,
            True,
            "Runtime enablement must remain forbidden throughout this scaffold and any later manual authorization review.",
        ),
        _gate(
            "acceptance_execution_not_authorized",
            not acceptance_execution_authorized,
            True,
            "This scaffold is pre-authorization only; acceptance_execution_authorized must remain false here.",
        ),
        _gate(
            "acceptance_not_executed_yet",
            not acceptance_executed,
            True,
            "This scaffold is pre-execution only; production acceptance must remain unexecuted here.",
        ),
        _gate(
            "manual_authorization_review_not_performed_yet",
            pending_verdict_retained and authorization_granted_retained_false,
            False,
            "No actual authorization review has been performed yet; the future record payload remains pending.",
        ),
        _gate(
            "review_record_scaffold_does_not_authorize_execution",
            True,
            False,
            "This artifact formalizes the future manual authorization-review record only. It does not authorize execution.",
        ),
    ]
    gates.extend(carry_forward_gate_entries)

    acceptance_authorization_review_record_scaffold_ready = all(
        check["status"] == "pass" for check in checks
    )
    future_manual_authorization_review_prerequisites_met = bool(
        acceptance_authorization_review_record_scaffold_ready
        and future_manual_authorization_review_prerequisites_reported_ready
        and not missing_prerequisite_gate_ids
    )

    if not acceptance_authorization_review_record_scaffold_ready:
        recommended_next_step = (
            "repair_acceptance_authorization_review_record_scaffold_inputs"
        )
        handoff_recommendation = (
            "Acceptance-authorization review record scaffold is blocked; repair the "
            "missing or mismatched upstream review artifacts before using this "
            "scaffold as a future manual authorization-review record template."
        )
    elif missing_prerequisite_gate_ids:
        recommended_next_step = (
            "complete_reviewed_runtime_patch_signoff_then_fill_manual_acceptance_authorization_review_record"
        )
        handoff_recommendation = (
            "Acceptance-authorization review record scaffold is ready as "
            "review-only/default-off scaffolding. It keeps "
            "acceptance_execution_authorized=false, "
            "runtime_enablement_allowed=false, acceptance_executed=false, and no "
            "actual authorization review has been performed. Current missing "
            "prerequisite(s) still block any future manual authorization decision: "
            f"{', '.join(missing_prerequisite_gate_ids)}. Next step: resolve those "
            "prerequisites, then have a human reviewer fill this scaffold record for "
            f"the locked prod_4x4_normal command `{exact_future_acceptance_command}` "
            f"writing `{exact_future_acceptance_result_path}` without enabling runtime."
        )
    else:
        recommended_next_step = (
            "have_human_fill_manual_acceptance_authorization_review_record_without_enabling_runtime"
        )
        handoff_recommendation = (
            "Acceptance-authorization review record scaffold is ready and upstream "
            "prerequisites are satisfied, but no actual authorization review has been "
            "performed. A human reviewer must fill this scaffold record to decide "
            "whether to authorize the locked prod_4x4_normal command "
            f"`{exact_future_acceptance_command}` to write "
            f"`{exact_future_acceptance_result_path}`, while "
            "runtime_enablement_allowed remains false here."
        )

    return {
        "metadata": {
            "source": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_SCAFFOLD_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_acceptance_authorization_review_record_scaffold_review_only_not_execution_authorization"
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
            "acceptance_authorization_review_bundle": _display_path(
                project_root, acceptance_authorization_review_bundle_resolved
            ),
            "acceptance_execution_gate": _display_path(
                project_root, acceptance_execution_gate_resolved
            ),
            "acceptance_result_validator": _display_path(
                project_root, acceptance_result_validator_resolved
            ),
            "exact_future_acceptance_command": exact_future_acceptance_command,
            "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
        },
        "candidate": dict(candidate),
        "status": {
            "acceptance_authorization_review_record_scaffold_ready": bool(
                acceptance_authorization_review_record_scaffold_ready
            ),
            "future_manual_authorization_review_prerequisites_met": bool(
                future_manual_authorization_review_prerequisites_met
            ),
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "authorization_review_completed": False,
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "missing_prerequisite_gate_ids": list(missing_prerequisite_gate_ids),
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
            "recommendation": handoff_recommendation,
        },
        "acceptance_authorization_review_record_scaffold": {
            "guard_id": acceptance_authorization_review_bundle.get("guard_id")
            or acceptance_execution_gate.get("guard_id")
            or acceptance_result_validator.get("guard_id"),
            "payload_id": acceptance_authorization_review_bundle.get("payload_id")
            or acceptance_execution_gate.get("payload_id")
            or acceptance_result_validator.get("payload_id"),
            "production_profile_id": production_profile_id,
            "review_only": True,
            "default_off": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "authorization_review_completed": False,
            "locked_execution_target": {
                "production_profile_id": production_profile_id,
                "production_profile_locked": bool(
                    production_profile_locked_prod_4x4_normal
                ),
                "default_production_runner": default_production_runner,
                "default_production_runner_locked": bool(
                    default_production_runner_locked
                ),
                "exact_future_acceptance_command": exact_future_acceptance_command,
                "exact_future_acceptance_command_locked": bool(
                    exact_future_acceptance_command_locked
                ),
                "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
                "exact_future_acceptance_result_path_locked": bool(
                    exact_future_acceptance_result_path_locked
                ),
                "command_matches_result_path": bool(command_matches_result_path),
            },
            "required_record_fields": required_record_fields,
            "required_review_conclusions": required_review_conclusions,
            "required_runtime_patch_statement_ids": (
                required_runtime_patch_statement_ids
            ),
            "missing_prerequisites": missing_prerequisites,
            "future_validation_checklist": future_validation_checklist,
            "scaffolded_authorization_review_record_payload": (
                scaffolded_authorization_review_record_payload
            ),
            "scaffold_notice": SCAFFOLD_NOTICE,
            "recommended_next_step_for_future_manual_review": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "still_blocked_gate_ids": list(missing_prerequisite_gate_ids),
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    scaffold = _mapping(report.get("acceptance_authorization_review_record_scaffold"))
    locked_execution_target = _mapping(scaffold.get("locked_execution_target"))
    payload = _mapping(scaffold.get("scaffolded_authorization_review_record_payload"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Acceptance Authorization Review Record Scaffold",
        "",
        f"- Acceptance authorization review record scaffold ready: `{status.get('acceptance_authorization_review_record_scaffold_ready')}`",
        f"- Future manual authorization review prerequisites met: `{status.get('future_manual_authorization_review_prerequisites_met')}`",
        f"- Acceptance execution authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{status.get('acceptance_executed')}`",
        f"- Authorization review completed: `{status.get('authorization_review_completed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Scaffold notice: {scaffold.get('scaffold_notice')}",
        "",
        "## Locked Execution Target",
        "",
        f"- Production profile id: `{locked_execution_target.get('production_profile_id')}`",
        f"- Production profile locked: `{locked_execution_target.get('production_profile_locked')}`",
        f"- Default production runner: `{locked_execution_target.get('default_production_runner')}`",
        f"- Default production runner locked: `{locked_execution_target.get('default_production_runner_locked')}`",
        f"- Exact future acceptance command: `{locked_execution_target.get('exact_future_acceptance_command')}`",
        f"- Exact future acceptance command locked: `{locked_execution_target.get('exact_future_acceptance_command_locked')}`",
        f"- Exact future acceptance result path: `{locked_execution_target.get('exact_future_acceptance_result_path')}`",
        f"- Exact future acceptance result path locked: `{locked_execution_target.get('exact_future_acceptance_result_path_locked')}`",
        f"- Command matches result path: `{locked_execution_target.get('command_matches_result_path')}`",
        "",
        "## Scaffolded Record Payload",
        "",
        f"- Record type: `{payload.get('record_type')}`",
        f"- Verdict: `{payload.get('verdict')}`",
        f"- Authorization granted: `{payload.get('authorization_granted')}`",
        f"- Runtime enablement allowed: `{payload.get('runtime_enablement_allowed')}`",
        f"- Acceptance executed: `{payload.get('acceptance_executed')}`",
        f"- Required conclusion ids: `{', '.join(_string_list(payload.get('required_conclusion_ids'))) or '(none)'}`",
        f"- Required runtime patch statement ids: `{', '.join(_string_list(payload.get('required_runtime_patch_statement_ids'))) or '(none)'}`",
        f"- Missing prerequisite gate ids: `{', '.join(_string_list(payload.get('missing_prerequisite_gate_ids'))) or '(none)'}`",
        "- This payload remains pending; no actual authorization review has been performed.",
        "",
        "## Required Record Fields",
        "",
        "| Field | Required | Template value | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(scaffold.get("required_record_fields", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(_render_value(entry.get('template_value')))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Required Review Conclusions",
            "",
            "| Conclusion | Currently satisfied | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(scaffold.get("required_review_conclusions", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('conclusion_id'))} | "
                f"{_markdown_cell(entry.get('currently_satisfied'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Missing Prerequisites",
            "",
            "| Gate | Required state | Current value | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(scaffold.get("missing_prerequisites", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('gate_id'))} | "
                f"{_markdown_cell(entry.get('required_state'))} | "
                f"{_markdown_cell(entry.get('current_value'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    lines.extend(
        [
            "",
            "## Future Validation Checklist",
            "",
            "| Checklist | Required | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for entry in list(scaffold.get("future_validation_checklist", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('checklist_id'))} | "
                f"{_markdown_cell(entry.get('required'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
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


def render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    scaffold = _mapping(report.get("acceptance_authorization_review_record_scaffold"))
    locked_execution_target = _mapping(scaffold.get("locked_execution_target"))
    payload = _mapping(scaffold.get("scaffolded_authorization_review_record_payload"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain acceptance authorization review record scaffold",
            "acceptance_authorization_review_record_scaffold_ready="
            + str(
                status.get(
                    "acceptance_authorization_review_record_scaffold_ready", False
                )
            ),
            "future_manual_authorization_review_prerequisites_met="
            + str(
                status.get(
                    "future_manual_authorization_review_prerequisites_met", False
                )
            ),
            "acceptance_execution_authorized="
            + str(status.get("acceptance_execution_authorized", False)),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed", False)),
            "acceptance_executed=" + str(status.get("acceptance_executed", False)),
            "authorization_review_completed="
            + str(status.get("authorization_review_completed", False)),
            "missing_prerequisite_gate_ids="
            + ",".join(_string_list(status.get("missing_prerequisite_gate_ids"))),
            "production_profile_id="
            + str(locked_execution_target.get("production_profile_id")),
            "exact_future_acceptance_command="
            + str(locked_execution_target.get("exact_future_acceptance_command")),
            "exact_future_acceptance_result_path="
            + str(
                locked_execution_target.get("exact_future_acceptance_result_path")
            ),
            "record_type=" + str(payload.get("record_type")),
            "verdict=" + str(payload.get("verdict")),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = (
        "anchor119_row_domain_acceptance_authorization_review_record_scaffold"
    ),
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_scaffolded_authorization_review_record_payload(
    template: Mapping[str, Any],
    *,
    production_profile_id: str,
    default_production_runner: str,
    exact_future_acceptance_command: str,
    exact_future_acceptance_result_path: str,
    required_conclusion_ids: list[str],
    required_runtime_patch_statement_ids: list[str],
    missing_prerequisite_gate_ids: list[str],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = dict(template)
    payload["record_type"] = str(
        payload.get("record_type") or "acceptance_execution_authorization_review_record_v0"
    )
    payload["reviewer_id"] = str(payload.get("reviewer_id") or "")
    payload["reviewed_at"] = str(payload.get("reviewed_at") or "")
    payload["verdict"] = "pending"
    payload["authorization_granted"] = False
    payload["runtime_enablement_allowed"] = False
    payload["acceptance_executed"] = False
    payload["locked_execution_target"] = {
        "production_profile_id": production_profile_id,
        "default_production_runner": default_production_runner,
        "exact_future_acceptance_command": exact_future_acceptance_command,
        "exact_future_acceptance_result_path": exact_future_acceptance_result_path,
    }
    payload["required_conclusion_ids"] = list(required_conclusion_ids)
    payload["required_runtime_patch_statement_ids"] = list(
        required_runtime_patch_statement_ids
    )
    payload["missing_prerequisite_gate_ids"] = list(missing_prerequisite_gate_ids)
    payload["notes"] = str(payload.get("notes") or "")
    return payload


def _build_required_record_fields(
    payload: Mapping[str, Any]
) -> list[Dict[str, Any]]:
    return [
        _field(
            "record_type",
            payload.get("record_type"),
            "Carry forward the locked authorization-review record type.",
        ),
        _field(
            "reviewer_id",
            payload.get("reviewer_id"),
            "Human reviewer must populate reviewer identity later.",
        ),
        _field(
            "reviewed_at",
            payload.get("reviewed_at"),
            "Human reviewer must populate review timestamp later.",
        ),
        _field(
            "verdict",
            payload.get("verdict"),
            "Remain pending until a future human authorization review is actually completed.",
        ),
        _field(
            "authorization_granted",
            payload.get("authorization_granted"),
            "Must remain false in this scaffold; a future human review would decide whether authorization can ever be granted.",
        ),
        _field(
            "runtime_enablement_allowed",
            payload.get("runtime_enablement_allowed"),
            "Must remain false; this scaffold is not runtime enablement.",
        ),
        _field(
            "acceptance_executed",
            payload.get("acceptance_executed"),
            "Must remain false because no production acceptance has been run.",
        ),
        _field(
            "locked_execution_target",
            payload.get("locked_execution_target"),
            "Carry forward the locked prod_4x4_normal target, command, and result path unchanged.",
        ),
        _field(
            "required_conclusion_ids",
            payload.get("required_conclusion_ids"),
            "Future manual review must address every required authorization-review conclusion.",
        ),
        _field(
            "required_runtime_patch_statement_ids",
            payload.get("required_runtime_patch_statement_ids"),
            "Carry forward runtime patch review statements that remain prerequisites for any future authorization decision.",
        ),
        _field(
            "missing_prerequisite_gate_ids",
            payload.get("missing_prerequisite_gate_ids"),
            "Carry forward currently unresolved prerequisite gates blocking any future authorization approval.",
        ),
        _field(
            "notes",
            payload.get("notes"),
            "Human reviewer notes and justification go here when the future manual review is actually performed.",
        ),
    ]


def _build_missing_prerequisites(
    explicit_entries: Any,
    *,
    carry_forward_gate_entries: list[Mapping[str, Any]],
    bundle_reported_missing_gate_ids: list[str],
    gate_reported_missing_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()

    if isinstance(explicit_entries, list):
        for entry in explicit_entries:
            if not isinstance(entry, Mapping):
                continue
            gate_id = str(entry.get("gate_id") or "").strip()
            if not gate_id or gate_id in seen:
                continue
            merged.append(
                {
                    "gate_id": gate_id,
                    "required_state": bool(entry.get("required_state", True)),
                    "current_value": bool(entry.get("current_value")),
                    "detail": str(entry.get("detail") or ""),
                }
            )
            seen.add(gate_id)

    detail_by_gate = {
        str(entry.get("gate_id")): str(entry.get("detail") or "")
        for entry in carry_forward_gate_entries
        if str(entry.get("gate_id") or "").strip()
    }
    for gate_id in bundle_reported_missing_gate_ids + gate_reported_missing_gate_ids:
        text = str(gate_id).strip()
        if not text or text in seen:
            continue
        merged.append(
            {
                "gate_id": text,
                "required_state": True,
                "current_value": False,
                "detail": detail_by_gate.get(
                    text,
                    "Carry-forward missing prerequisite from upstream acceptance review artifacts.",
                ),
            }
        )
        seen.add(text)

    return merged


def _blocked_gate_entries(report: Optional[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    if not report:
        return []
    entries: list[Dict[str, Any]] = []
    for gate in list(report.get("gates", [])):
        if not isinstance(gate, Mapping):
            continue
        gate_id = str(gate.get("gate_id") or "").strip()
        if not gate_id:
            continue
        blocking = bool(gate.get("blocking"))
        satisfied = bool(gate.get("satisfied"))
        if blocking and not satisfied:
            entries.append(
                {
                    "gate_id": gate_id,
                    "satisfied": False,
                    "blocking": True,
                    "detail": str(gate.get("detail") or "carry-forward blocked gate"),
                }
            )
    return entries


def _merge_gate_entries(*gate_groups: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for gate_group in gate_groups:
        for gate in gate_group:
            gate_id = str(gate.get("gate_id") or "").strip()
            if not gate_id or gate_id in seen:
                continue
            merged.append(
                {
                    "gate_id": gate_id,
                    "satisfied": bool(gate.get("satisfied")),
                    "blocking": bool(gate.get("blocking")),
                    "detail": str(gate.get("detail") or ""),
                }
            )
            seen.add(gate_id)
    return merged


def _field(field: str, template_value: Any, detail: str) -> Dict[str, Any]:
    return {
        "field": str(field),
        "required": True,
        "template_value": template_value,
        "detail": str(detail),
    }


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


def _review_only_contract_retained(*metadatas: Mapping[str, Any]) -> bool:
    relevant = [metadata for metadata in metadatas if metadata]
    if not relevant:
        return False
    return all(
        bool(metadata.get("spec_only", False))
        and (
            "review_only" not in metadata or bool(metadata.get("review_only", False))
        )
        and bool(metadata.get("default_off", False))
        and not bool(metadata.get("runtime_precheck_enabled", False))
        and not bool(metadata.get("runtime_semantics_changed", False))
        and not bool(metadata.get("proof_source", False))
        and not bool(metadata.get("candidate_elimination_claim", False))
        and not bool(metadata.get("solver_invoked", False))
        and not bool(metadata.get("acceptance_executed", False))
        for metadata in relevant
    )


def _locked_value(
    values: list[Any],
    *,
    normalize: Optional[Callable[[str], str]] = None,
) -> tuple[str, bool]:
    non_empty = [str(value) for value in values if str(value).strip()]
    if not non_empty:
        return "", False
    normalizer = normalize or (lambda value: str(value).strip())
    normalized = {normalizer(value) for value in non_empty}
    return non_empty[0], bool(len(non_empty) >= 2 and len(normalized) == 1)


def _gate(
    gate_id: str,
    satisfied: bool,
    blocking: bool,
    detail: str,
) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[Mapping[str, Any]] = []
    for entry in value:
        if isinstance(entry, Mapping):
            result.append(entry)
    return result


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


def _normalize_command_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

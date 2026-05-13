from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import atomic_write_json, now_iso

REVIEW_STATE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1"
)
SIGNOFF_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
)

DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_gpt55pro_20260425/"
    "anchor119_row_domain_signoff_record_validator.json"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_gpt55pro_20260425/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)

EXPECTED_CANDIDATE_KEY = "67x13"
EXPECTED_ANCHOR_IDX = 119
EXPECTED_FORMULATION_PROFILE = "joined_xy_block64_all_templates"
EXPECTED_SCOPE = (
    "candidate=67x13, anchor_idx=119, joined_xy_block64_all_templates, "
    "anchor119 fixed-anchor row-domain/count bridge"
)
EXPECTED_REVIEWER_ID = "gpt55pro"
EXPECTED_INGEST_REVIEWER_ID = "codex_main_coordinator"
EXPECTED_RECORD_IDENTITY = "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
EXPECTED_REVIEWER_STATEMENT_IDS = [
    "default_off_retained",
    "reserved_runtime_request_downgrades_to_advisory",
    "no_proof_source_promotion",
    "acceptance_refresh_required_before_enablement",
]
EXPECTED_REVIEW_CONCLUSION_IDS = [
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
    "repo_side_review_state_may_mark_reviewed_runtime_patch",
    "runtime_enablement_remains_blocked_after_review",
    "post_ingest_still_blocked_gate_ids_preserved",
]
EXPECTED_CURRENT_STILL_BLOCKED_GATE_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
]
EXPECTED_POST_INGEST_STILL_BLOCKED_GATE_IDS = [
    "production_acceptance_refresh_completed",
]


def build_phase3b_coordinate_validation_anchor119_row_domain_review_state(
    project_root: Path,
    *,
    signoff_record_validator_path: Optional[Path] = None,
    ingest_review_record_validator_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    signoff_path = _resolve_path(
        project_root,
        signoff_record_validator_path
        if signoff_record_validator_path is not None
        else DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH,
    )
    ingest_path = _resolve_path(
        project_root,
        ingest_review_record_validator_path
        if ingest_review_record_validator_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH,
    )

    signoff_report, signoff_error = _load_json_mapping(signoff_path)
    ingest_report, ingest_error = _load_json_mapping(ingest_path)

    signoff_meta = _mapping(signoff_report.get("metadata")) if signoff_report else {}
    ingest_meta = _mapping(ingest_report.get("metadata")) if ingest_report else {}
    signoff_status = _mapping(signoff_report.get("status")) if signoff_report else {}
    ingest_status = _mapping(ingest_report.get("status")) if ingest_report else {}
    signoff_validator = (
        _mapping(signoff_report.get("signoff_record_validator"))
        if signoff_report
        else {}
    )
    ingest_validator = (
        _mapping(ingest_report.get("ingest_review_record_validator"))
        if ingest_report
        else {}
    )
    signoff_validation = _mapping(signoff_validator.get("actual_record_validation"))
    ingest_validation = _mapping(ingest_validator.get("actual_record_validation"))

    signoff_present = bool(
        signoff_report is not None
        and signoff_error is None
        and signoff_meta.get("source") == SIGNOFF_RECORD_VALIDATOR_SOURCE
    )
    ingest_present = bool(
        ingest_report is not None
        and ingest_error is None
        and ingest_meta.get("source") == INGEST_REVIEW_RECORD_VALIDATOR_SOURCE
    )
    signoff_passed = bool(
        signoff_status.get("signoff_record_payload_provided", False)
        and signoff_status.get("signoff_record_payload_validated", False)
        and signoff_status.get("signoff_record_payload_validation_status") == "passed"
        and signoff_validation.get("record_payload_provided", False)
        and signoff_validation.get("record_payload_validated", False)
        and signoff_validation.get("validation_status") == "passed"
    )
    ingest_passed = bool(
        ingest_status.get("manual_ingest_review_record_provided", False)
        and ingest_status.get("manual_ingest_review_record_validated", False)
        and ingest_status.get("manual_ingest_review_record_validation_status")
        == "passed"
        and ingest_validation.get("record_payload_provided", False)
        and ingest_validation.get("record_payload_validated", False)
        and ingest_validation.get("validation_status") == "passed"
    )

    signoff_candidate_ok = _candidate_matches(
        _mapping(signoff_report.get("candidate")) if signoff_report else {}
    )
    ingest_candidate_ok = _candidate_matches(
        _mapping(ingest_report.get("candidate")) if ingest_report else {}
    )
    signoff_scope = _rule_value(signoff_validation, "required_field:scope", "scope")
    ingest_scope = _rule_value(ingest_validation, "required_field:scope", "scope")
    signoff_scope_ok = signoff_scope == EXPECTED_SCOPE
    ingest_scope_ok = ingest_scope == EXPECTED_SCOPE

    signoff_statement_ids = _string_list(
        _rule_value(signoff_validation, "agreed_statement_ids", "agreed_statement_ids")
    )
    ingest_statement_ids = _string_list(
        _rule_value(
            ingest_validation,
            "required_reviewer_statement_ids",
            "required_reviewer_statement_ids",
        )
    )
    ingest_conclusion_ids = _string_list(
        _rule_value(
            ingest_validation,
            "required_review_conclusion_ids",
            "required_review_conclusion_ids",
        )
    )
    current_still_blocked_gate_ids = _string_list(
        _rule_value(
            ingest_validation,
            "current_still_blocked_gate_ids",
            "current_still_blocked_gate_ids",
        )
    )
    post_ingest_still_blocked_gate_ids = _string_list(
        _rule_value(
            ingest_validation,
            "post_ingest_still_blocked_gate_ids",
            "post_ingest_still_blocked_gate_ids",
        )
    )

    reviewer_id = str(_rule_value(signoff_validation, "required_field:reviewer_id", "reviewer_id") or "")
    ingest_reviewer_id = str(
        _rule_value(ingest_validation, "required_field:ingest_reviewer_id", "ingest_reviewer_id")
        or ""
    )
    target_record_identity = str(
        _rule_value(
            ingest_validation,
            "required_field:target_record_identity",
            "target_record_identity",
        )
        or ""
    )

    signoff_safety_ok = _metadata_default_off(signoff_meta) and _status_default_off(
        signoff_status
    )
    ingest_safety_ok = (
        _metadata_default_off(ingest_meta)
        and _status_default_off(ingest_status)
        and not bool(ingest_meta.get("repo_side_review_state_updated", False))
        and not bool(ingest_status.get("repo_side_review_state_updated", False))
    )

    checks = [
        _check(
            "signoff_record_validator_present",
            "pass" if signoff_present else "fail",
            "signoff validator loaded"
            if signoff_present
            else signoff_error or f"missing:{_display_path(project_root, signoff_path)}",
        ),
        _check(
            "ingest_review_record_validator_present",
            "pass" if ingest_present else "fail",
            "ingest-review validator loaded"
            if ingest_present
            else ingest_error or f"missing:{_display_path(project_root, ingest_path)}",
        ),
        _check(
            "signoff_payload_validated",
            "pass" if signoff_passed else "fail",
            str(signoff_validation.get("validation_status", "not_available")),
        ),
        _check(
            "ingest_review_payload_validated",
            "pass" if ingest_passed else "fail",
            str(ingest_validation.get("validation_status", "not_available")),
        ),
        _check(
            "signoff_candidate_matches_locked_scope",
            "pass" if signoff_candidate_ok else "fail",
            _candidate_detail(signoff_report),
        ),
        _check(
            "ingest_candidate_matches_locked_scope",
            "pass" if ingest_candidate_ok else "fail",
            _candidate_detail(ingest_report),
        ),
        _check(
            "signoff_scope_matches_locked_contract",
            "pass" if signoff_scope_ok else "fail",
            str(signoff_scope or "missing"),
        ),
        _check(
            "ingest_scope_matches_locked_contract",
            "pass" if ingest_scope_ok else "fail",
            str(ingest_scope or "missing"),
        ),
        _check(
            "reviewer_id_matches_external_reviewer",
            "pass" if reviewer_id == EXPECTED_REVIEWER_ID else "fail",
            reviewer_id or "missing",
        ),
        _check(
            "ingest_reviewer_id_matches_coordinator",
            "pass" if ingest_reviewer_id == EXPECTED_INGEST_REVIEWER_ID else "fail",
            ingest_reviewer_id or "missing",
        ),
        _check(
            "target_record_identity_locked",
            "pass" if target_record_identity == EXPECTED_RECORD_IDENTITY else "fail",
            target_record_identity or "missing",
        ),
        _check(
            "signoff_required_statement_ids_locked",
            "pass" if signoff_statement_ids == EXPECTED_REVIEWER_STATEMENT_IDS else "fail",
            ",".join(signoff_statement_ids) or "missing",
        ),
        _check(
            "ingest_required_statement_ids_locked",
            "pass" if ingest_statement_ids == EXPECTED_REVIEWER_STATEMENT_IDS else "fail",
            ",".join(ingest_statement_ids) or "missing",
        ),
        _check(
            "ingest_required_conclusion_ids_locked",
            "pass" if ingest_conclusion_ids == EXPECTED_REVIEW_CONCLUSION_IDS else "fail",
            ",".join(ingest_conclusion_ids) or "missing",
        ),
        _check(
            "current_still_blocked_gate_ids_locked",
            "pass"
            if current_still_blocked_gate_ids == EXPECTED_CURRENT_STILL_BLOCKED_GATE_IDS
            else "fail",
            ",".join(current_still_blocked_gate_ids) or "missing",
        ),
        _check(
            "post_ingest_still_blocked_gate_ids_locked",
            "pass"
            if post_ingest_still_blocked_gate_ids
            == EXPECTED_POST_INGEST_STILL_BLOCKED_GATE_IDS
            else "fail",
            ",".join(post_ingest_still_blocked_gate_ids) or "missing",
        ),
        _check(
            "signoff_safety_flags_default_off",
            "pass" if signoff_safety_ok else "fail",
            _safety_detail(signoff_meta, signoff_status),
        ),
        _check(
            "ingest_safety_flags_default_off",
            "pass" if ingest_safety_ok else "fail",
            _safety_detail(ingest_meta, ingest_status),
        ),
    ]

    review_state_ready = all(check["status"] == "pass" for check in checks)
    reviewed_runtime_patch_exists = bool(review_state_ready)
    production_acceptance_refresh_completed = False

    gates = [
        _gate(
            "signoff_record_payload_validated",
            bool(signoff_passed),
            True,
            "GPT5.5 Pro signoff payload must validate against the locked signoff contract.",
        ),
        _gate(
            "manual_ingest_review_payload_validated",
            bool(ingest_passed),
            True,
            "The local coordinator ingest-review record must validate against the locked ingest contract.",
        ),
        _gate(
            "repo_side_review_state_updated",
            bool(review_state_ready),
            True,
            "This review-state artifact is the first repo-side marker that may set reviewed_runtime_patch_exists=true.",
        ),
        _gate(
            "reviewed_runtime_patch_exists",
            bool(reviewed_runtime_patch_exists),
            True,
            "The reviewed-runtime-patch existence blocker is cleared only inside this repo-side review-state artifact.",
        ),
        _gate(
            "runtime_enablement_allowed",
            False,
            False,
            "Runtime enablement remains locked false after review-state marking.",
        ),
        _gate(
            "production_acceptance_refresh_completed",
            False,
            True,
            "Production acceptance has not been refreshed yet.",
        ),
    ]
    remaining_blockers = [
        str(gate["gate_id"])
        for gate in gates
        if bool(gate.get("blocking")) and not bool(gate.get("satisfied"))
    ]

    return {
        "metadata": {
            "source": REVIEW_STATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_repo_side_review_state_not_proof_source",
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
            "signoff_record_validator": _display_path(project_root, signoff_path),
            "ingest_review_record_validator": _display_path(project_root, ingest_path),
        },
        "candidate": {
            "key": EXPECTED_CANDIDATE_KEY,
            "anchor_idx": EXPECTED_ANCHOR_IDX,
            "formulation_profile": EXPECTED_FORMULATION_PROFILE,
        },
        "status": {
            "review_state_ready": bool(review_state_ready),
            "repo_side_review_state_updated": bool(review_state_ready),
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "runtime_enablement_allowed": False,
            "production_acceptance_refresh_completed": bool(
                production_acceptance_refresh_completed
            ),
            "acceptance_execution_authorized": False,
            "remaining_blocker_gate_ids": remaining_blockers,
            "recommended_next_step": (
                "refresh_prod_4x4_normal_production_acceptance"
                if review_state_ready
                else "repair_signoff_or_ingest_review_validation_before_review_state"
            ),
            "handoff_recommendation": (
                "Repo-side review-state marker is valid: reviewed_runtime_patch_exists=true "
                "is now represented as a local audit artifact, while runtime_enablement_allowed=false "
                "and proof_source=false remain locked. Next gate is prod_4x4_normal production "
                "acceptance refresh, not final 168h."
                if review_state_ready
                else "Review-state marker is not ready; do not mark reviewed_runtime_patch_exists=true."
            ),
        },
        "review_state": {
            "review_state_kind": "repo_side_review_state",
            "tracked_field": "reviewed_runtime_patch_exists",
            "record_identity": EXPECTED_RECORD_IDENTITY,
            "scope": EXPECTED_SCOPE,
            "reviewer_id": reviewer_id,
            "ingest_reviewer_id": ingest_reviewer_id,
            "review_state_ready": bool(review_state_ready),
            "repo_side_review_state_updated": bool(review_state_ready),
            "reviewed_runtime_patch_exists": bool(reviewed_runtime_patch_exists),
            "runtime_enablement_allowed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "production_acceptance_refresh_completed": False,
            "current_still_blocked_gate_ids": EXPECTED_CURRENT_STILL_BLOCKED_GATE_IDS,
            "post_ingest_still_blocked_gate_ids": EXPECTED_POST_INGEST_STILL_BLOCKED_GATE_IDS,
            "required_reviewer_statement_ids": EXPECTED_REVIEWER_STATEMENT_IDS,
            "required_review_conclusion_ids": EXPECTED_REVIEW_CONCLUSION_IDS,
        },
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_review_state_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    review_state = _mapping(report.get("review_state"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Review State",
        "",
        f"- Review-state ready: `{status.get('review_state_ready')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Production acceptance refresh completed: `{status.get('production_acceptance_refresh_completed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Recommendation: {status.get('handoff_recommendation')}",
        "",
        "## Review State",
        "",
        f"- Record identity: `{review_state.get('record_identity')}`",
        f"- Scope: `{review_state.get('scope')}`",
        f"- Reviewer: `{review_state.get('reviewer_id')}`",
        f"- Ingest reviewer: `{review_state.get('ingest_reviewer_id')}`",
        "",
        "## Gates",
        "",
        "| Gate | Satisfied | Blocking | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for gate in list(report.get("gates", [])):
        if isinstance(gate, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(gate.get("gate_id")),
                        _markdown_cell(gate.get("satisfied")),
                        _markdown_cell(gate.get("blocking")),
                        _markdown_cell(gate.get("detail")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_review_state_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    review_state = _mapping(report.get("review_state"))
    lines = [
        "Phase 3B anchor119 row-domain review state",
        f"review_state_ready={bool(status.get('review_state_ready', False))}",
        f"repo_side_review_state_updated={bool(status.get('repo_side_review_state_updated', False))}",
        f"reviewed_runtime_patch_exists={bool(status.get('reviewed_runtime_patch_exists', False))}",
        f"runtime_enablement_allowed={bool(status.get('runtime_enablement_allowed', False))}",
        f"production_acceptance_refresh_completed={bool(status.get('production_acceptance_refresh_completed', False))}",
        f"recommended_next_step={status.get('recommended_next_step')}",
        f"record_identity={review_state.get('record_identity')}",
        f"scope={review_state.get('scope')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check="
                + str(check.get("check_id"))
                + " status="
                + str(check.get("status"))
                + " detail="
                + str(check.get("detail"))
            )
    return "\n".join(lines) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_review_state(
    report: Mapping[str, Any],
    output_dir: Path,
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_review_state.json"
    md_path = output_dir / "anchor119_row_domain_review_state.md"
    txt_path = output_dir / "anchor119_row_domain_review_state.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(
        md_path,
        render_phase3b_coordinate_validation_anchor119_row_domain_review_state_markdown(
            report
        ),
    )
    _atomic_write_text(
        txt_path,
        render_phase3b_coordinate_validation_anchor119_row_domain_review_state_text(
            report
        ),
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _metadata_default_off(meta: Mapping[str, Any]) -> bool:
    return bool(
        meta.get("default_off", False)
        and not meta.get("runtime_precheck_enabled", False)
        and not meta.get("runtime_semantics_changed", False)
        and not meta.get("proof_source", False)
        and not meta.get("candidate_elimination_claim", False)
        and not meta.get("solver_invoked", False)
    )


def _status_default_off(status: Mapping[str, Any]) -> bool:
    return bool(
        not status.get("runtime_enablement_allowed", False)
        and not status.get("reviewed_runtime_patch_exists", False)
    )


def _candidate_matches(candidate: Mapping[str, Any]) -> bool:
    try:
        anchor_idx = int(candidate.get("anchor_idx", -1))
    except (TypeError, ValueError):
        anchor_idx = -1
    return bool(
        str(candidate.get("key")) == EXPECTED_CANDIDATE_KEY
        and anchor_idx == EXPECTED_ANCHOR_IDX
        and str(candidate.get("formulation_profile")) == EXPECTED_FORMULATION_PROFILE
    )


def _candidate_detail(report: Optional[Mapping[str, Any]]) -> str:
    candidate = _mapping(report.get("candidate")) if report else {}
    return (
        "key="
        + str(candidate.get("key"))
        + " anchor_idx="
        + str(candidate.get("anchor_idx"))
        + " formulation_profile="
        + str(candidate.get("formulation_profile"))
    )


def _safety_detail(meta: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    return (
        "runtime_enablement_allowed="
        + str(bool(status.get("runtime_enablement_allowed", False)))
        + " reviewed_runtime_patch_exists="
        + str(bool(status.get("reviewed_runtime_patch_exists", False)))
        + " proof_source="
        + str(bool(meta.get("proof_source", False)))
        + " candidate_elimination_claim="
        + str(bool(meta.get("candidate_elimination_claim", False)))
        + " solver_invoked="
        + str(bool(meta.get("solver_invoked", False)))
    )


def _rule_value(
    validation: Mapping[str, Any],
    rule_id: str,
    field: str,
) -> Any:
    for entry in list(validation.get("rule_results", [])):
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("rule_id")) != rule_id:
            continue
        if str(entry.get("field", field)) != field:
            continue
        if "actual" in entry:
            return entry.get("actual")
        if "observed_value" in entry:
            return entry.get("observed_value")
        return entry.get("value")
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _load_json_mapping(path: Path) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"json_error:{exc}"
    if not isinstance(payload, Mapping):
        return None, "not_mapping"
    return payload, None


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _gate(
    gate_id: str,
    satisfied: bool,
    blocking: bool,
    detail: str,
) -> Dict[str, Any]:
    return {
        "gate_id": gate_id,
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": detail,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return project_root / path


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root))
    except ValueError:
        return str(Path(path).resolve())


def _markdown_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

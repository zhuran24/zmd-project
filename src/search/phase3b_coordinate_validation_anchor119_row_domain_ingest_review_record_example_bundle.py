from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator,
)

INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
)
INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
)
DEFAULT_INGEST_REVIEW_RECORD_SCAFFOLD_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_20260424/"
    "anchor119_row_domain_ingest_review_record_scaffold.json"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)
DEFAULT_REVIEWED_RUNTIME_PATCH_INGEST_GATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_20260424/"
    "anchor119_row_domain_reviewed_runtime_patch_ingest_gate.json"
)
DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_20260424/"
    "anchor119_row_domain_signoff_record_validator.json"
)
SYNTHETIC_EXAMPLE_REVIEWER_ID = "synthetic_demo_reviewer_anchor119"
SYNTHETIC_EXAMPLE_REVIEWED_AT = "2026-04-24T12:00:00Z"
SYNTHETIC_EXAMPLE_REVIEW_DECISION = "approved_for_repo_side_review_state_marking"
SYNTHETIC_EXAMPLE_VALIDATION_STATUS = "validated_against_locked_contract"
EXAMPLE_BUNDLE_NOTICE = (
    "Synthetic example/demo payload only. This is not an actual human ingest-review "
    "record and not an applied repo-side review-state update."
)
REVIEW_ONLY_EFFECT_DETAIL = (
    "This bundle remains review-only/default-off/spec-only. "
    "repo_side_review_state_updated stays false, reviewed_runtime_patch_exists stays "
    "false, and runtime_enablement_allowed stays false."
)
REPLAY_INSTRUCTIONS_DETAIL = (
    "To replay this validation later, write the synthetic example payload below to a "
    "JSON file and rerun the existing ingest-review record validator against the same "
    "locked scaffold and upstream validator dependencies."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle(
    project_root: Path,
    *,
    ingest_review_record_scaffold_path: Optional[Path] = None,
    ingest_review_record_validator_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ingest_review_record_scaffold_resolved = _resolve_path(
        project_root,
        ingest_review_record_scaffold_path
        if ingest_review_record_scaffold_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_SCAFFOLD_PATH,
    )
    ingest_review_record_validator_resolved = _resolve_path(
        project_root,
        ingest_review_record_validator_path
        if ingest_review_record_validator_path is not None
        else DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH,
    )

    scaffold_report, scaffold_error = _load_json_mapping(
        ingest_review_record_scaffold_resolved
    )
    validator_report, validator_error = _load_json_mapping(
        ingest_review_record_validator_resolved
    )

    scaffold_meta = _mapping(scaffold_report.get("metadata")) if scaffold_report else {}
    scaffold_status = _mapping(scaffold_report.get("status")) if scaffold_report else {}
    scaffold = (
        _mapping(scaffold_report.get("ingest_review_record_scaffold"))
        if scaffold_report
        else {}
    )
    validator_meta = _mapping(validator_report.get("metadata")) if validator_report else {}
    validator_status = _mapping(validator_report.get("status")) if validator_report else {}
    validator = (
        _mapping(validator_report.get("ingest_review_record_validator"))
        if validator_report
        else {}
    )
    validator_paths = _mapping(validator_report.get("paths")) if validator_report else {}
    candidate = _first_mapping(
        scaffold_report.get("candidate") if scaffold_report else None,
        validator_report.get("candidate") if validator_report else None,
    )

    ingest_review_record_scaffold_present = bool(
        scaffold_report is not None
        and scaffold_error is None
        and scaffold_meta.get("source") == INGEST_REVIEW_RECORD_SCAFFOLD_SOURCE
    )
    ingest_review_record_validator_present = bool(
        validator_report is not None
        and validator_error is None
        and validator_meta.get("source") == INGEST_REVIEW_RECORD_VALIDATOR_SOURCE
    )
    ingest_review_record_scaffold_ready = bool(
        scaffold_status.get("ingest_review_record_scaffold_ready", False)
    )
    ingest_review_record_validator_ready = bool(
        validator_status.get("ingest_review_record_validator_ready", False)
    )

    locked_target_review_state = _mapping(scaffold.get("locked_target_review_state")) or _mapping(
        validator.get("locked_target_review_state")
    )
    locked_reviewer_record_handoff = _mapping(
        scaffold.get("locked_reviewer_record_handoff")
    ) or _mapping(validator.get("locked_reviewer_record_handoff"))
    scaffold_template_payload = _mapping(scaffold.get("ingest_review_record_template"))
    validator_template_payload = _mapping(validator.get("expected_template_payload"))
    required_review_conclusions = _mapping_list(
        scaffold.get("required_review_conclusions")
    ) or _mapping_list(validator.get("required_review_conclusions"))
    blocked_gate_contract = _mapping(validator.get("blocked_gate_contract"))
    validator_target = (
        str(validator.get("validator_target") or "").strip()
        or "future_completed_ingest_review_record_payload"
    )

    template_payload_present = bool(scaffold_template_payload)
    validator_template_payload_present = bool(validator_template_payload)
    selected_template_payload = dict(scaffold_template_payload or validator_template_payload)
    template_payload_aligned = bool(
        template_payload_present
        and validator_template_payload_present
        and scaffold_template_payload == validator_template_payload
    )

    replay_ingest_gate_path = _resolve_optional_path(
        project_root,
        validator_paths.get("reviewed_runtime_patch_ingest_gate"),
    ) or _resolve_path(project_root, DEFAULT_REVIEWED_RUNTIME_PATCH_INGEST_GATE_PATH)
    replay_signoff_validator_path = _resolve_optional_path(
        project_root,
        validator_paths.get("signoff_record_validator"),
    ) or _resolve_path(project_root, DEFAULT_SIGNOFF_RECORD_VALIDATOR_PATH)
    recorded_scaffold_path = _resolve_optional_path(
        project_root,
        validator_paths.get("ingest_review_record_scaffold"),
    ) or ingest_review_record_scaffold_resolved
    validator_replay_paths_defined = bool(
        replay_ingest_gate_path is not None and replay_signoff_validator_path is not None
    )
    validator_scaffold_path_matches_selected_scaffold = bool(
        recorded_scaffold_path == ingest_review_record_scaffold_resolved
    )

    current_still_blocked_gate_ids = _string_list(
        selected_template_payload.get("current_still_blocked_gate_ids")
    ) or _string_list(blocked_gate_contract.get("current_still_blocked_gate_ids"))
    post_ingest_still_blocked_gate_ids = _string_list(
        selected_template_payload.get("post_ingest_still_blocked_gate_ids")
    ) or _string_list(blocked_gate_contract.get("post_ingest_still_blocked_gate_ids"))

    review_only_contract_retained = bool(
        ingest_review_record_scaffold_present
        and ingest_review_record_validator_present
        and bool(scaffold_meta.get("review_only", False))
        and bool(scaffold_meta.get("spec_only", False))
        and bool(scaffold_meta.get("default_off", False))
        and not bool(scaffold_meta.get("runtime_precheck_enabled", False))
        and not bool(scaffold_meta.get("runtime_semantics_changed", False))
        and not bool(scaffold_meta.get("proof_source", False))
        and not bool(scaffold_meta.get("candidate_elimination_claim", False))
        and not bool(scaffold_meta.get("solver_invoked", False))
        and bool(validator_meta.get("review_only", False))
        and bool(validator_meta.get("spec_only", False))
        and bool(validator_meta.get("default_off", False))
        and not bool(validator_meta.get("runtime_precheck_enabled", False))
        and not bool(validator_meta.get("runtime_semantics_changed", False))
        and not bool(validator_meta.get("proof_source", False))
        and not bool(validator_meta.get("candidate_elimination_claim", False))
        and not bool(validator_meta.get("solver_invoked", False))
    )
    upstream_repo_side_review_state_unchanged = not any(
        bool(value)
        for value in [
            scaffold_status.get("repo_side_review_state_updated", False),
            validator_status.get("repo_side_review_state_updated", False),
            scaffold_meta.get("repo_side_review_state_updated", False),
            validator_meta.get("repo_side_review_state_updated", False),
        ]
    )
    upstream_reviewed_runtime_patch_absent_as_expected = not any(
        bool(value)
        for value in [
            scaffold_status.get("reviewed_runtime_patch_exists", False),
            validator_status.get("reviewed_runtime_patch_exists", False),
        ]
    )
    upstream_runtime_enablement_blocked_as_expected = not any(
        bool(value)
        for value in [
            scaffold_status.get("runtime_enablement_allowed", False),
            validator_status.get("runtime_enablement_allowed", False),
        ]
    )

    synthetic_example_payload = _build_synthetic_completed_ingest_review_record_payload(
        selected_template_payload,
        locked_reviewer_record_handoff=locked_reviewer_record_handoff,
        required_review_conclusions=required_review_conclusions,
    )
    synthetic_example_payload_generated = bool(synthetic_example_payload)

    replay_report, replay_error = _replay_validator_against_synthetic_payload(
        project_root,
        ingest_review_record_scaffold_path=ingest_review_record_scaffold_resolved,
        reviewed_runtime_patch_ingest_gate_path=replay_ingest_gate_path,
        signoff_record_validator_path=replay_signoff_validator_path,
        synthetic_payload=synthetic_example_payload,
    )
    replay_meta = _mapping(replay_report.get("metadata")) if replay_report else {}
    replay_status = _mapping(replay_report.get("status")) if replay_report else {}
    replay_validator = (
        _mapping(replay_report.get("ingest_review_record_validator"))
        if replay_report
        else {}
    )
    replay_actual_validation = _mapping(
        replay_validator.get("actual_record_validation")
    )
    replay_validator_ready = bool(
        replay_status.get("ingest_review_record_validator_ready", False)
    )
    synthetic_ingest_review_record_example_validated = bool(
        replay_validator_ready
        and replay_status.get("manual_ingest_review_record_provided", False)
        and replay_status.get("manual_ingest_review_record_validated", False)
        and replay_actual_validation.get("record_payload_validated", False)
    )
    synthetic_ingest_review_record_validation_status = str(
        replay_status.get("manual_ingest_review_record_validation_status")
        or replay_actual_validation.get("validation_status")
        or "not_run"
    )
    replay_review_only_effect_retained = not any(
        bool(value)
        for value in [
            replay_status.get("repo_side_review_state_updated", False),
            replay_status.get("reviewed_runtime_patch_exists", False),
            replay_status.get("runtime_enablement_allowed", False),
        ]
    )
    replayed_validation_summary = _build_replayed_validation_summary(
        replay_meta=replay_meta,
        replay_status=replay_status,
        replay_validator=replay_validator,
        replay_actual_validation=replay_actual_validation,
    )

    checks = [
        _check(
            "ingest_review_record_scaffold_present",
            "pass" if ingest_review_record_scaffold_present else "fail",
            "ingest review record scaffold loaded"
            if ingest_review_record_scaffold_present
            else scaffold_error
            or (
                f"unexpected_source:{scaffold_meta.get('source')}"
                if scaffold_report is not None
                else f"missing:{_display_path(project_root, ingest_review_record_scaffold_resolved)}"
            ),
        ),
        _check(
            "ingest_review_record_validator_present",
            "pass" if ingest_review_record_validator_present else "fail",
            "ingest review record validator loaded"
            if ingest_review_record_validator_present
            else validator_error
            or (
                f"unexpected_source:{validator_meta.get('source')}"
                if validator_report is not None
                else f"missing:{_display_path(project_root, ingest_review_record_validator_resolved)}"
            ),
        ),
        _check(
            "ingest_review_record_scaffold_ready",
            "pass" if ingest_review_record_scaffold_ready else "fail",
            str(ingest_review_record_scaffold_ready),
        ),
        _check(
            "ingest_review_record_validator_ready",
            "pass" if ingest_review_record_validator_ready else "fail",
            str(ingest_review_record_validator_ready),
        ),
        _check(
            "template_payload_present",
            "pass" if template_payload_present else "fail",
            "locked ingest-review record template present"
            if template_payload_present
            else "missing",
        ),
        _check(
            "validator_template_payload_present",
            "pass" if validator_template_payload_present else "fail",
            "validator expected template payload present"
            if validator_template_payload_present
            else "missing",
        ),
        _check(
            "template_payload_aligned",
            "pass" if template_payload_aligned else "fail",
            "scaffold template and validator expected template match exactly"
            if template_payload_aligned
            else "scaffold_template_and_validator_expected_template_mismatch",
        ),
        _check(
            "validator_replay_paths_defined",
            "pass" if validator_replay_paths_defined else "fail",
            "reviewed_runtime_patch_ingest_gate="
            + str(_display_path(project_root, replay_ingest_gate_path))
            + " signoff_record_validator="
            + str(_display_path(project_root, replay_signoff_validator_path))
            if validator_replay_paths_defined
            else "missing_replay_dependency_paths",
        ),
        _check(
            "validator_scaffold_path_matches_selected_scaffold",
            "pass" if validator_scaffold_path_matches_selected_scaffold else "fail",
            _display_path(project_root, recorded_scaffold_path),
        ),
        _check(
            "review_only_contract_retained",
            "pass" if review_only_contract_retained else "fail",
            "review_only/spec_only/default_off/no-solve retained upstream"
            if review_only_contract_retained
            else "expected review_only/spec_only/default_off/no-solve metadata upstream",
        ),
        _check(
            "upstream_repo_side_review_state_unchanged_as_expected",
            "pass" if upstream_repo_side_review_state_unchanged else "fail",
            str(upstream_repo_side_review_state_unchanged),
        ),
        _check(
            "upstream_reviewed_runtime_patch_absent_as_expected",
            "pass" if upstream_reviewed_runtime_patch_absent_as_expected else "fail",
            str(upstream_reviewed_runtime_patch_absent_as_expected),
        ),
        _check(
            "upstream_runtime_enablement_blocked_as_expected",
            "pass" if upstream_runtime_enablement_blocked_as_expected else "fail",
            str(upstream_runtime_enablement_blocked_as_expected),
        ),
        _check(
            "synthetic_example_payload_generated",
            "pass" if synthetic_example_payload_generated else "fail",
            str(synthetic_example_payload.get("record_type") or "missing"),
        ),
        _check(
            "replayed_validator_ready",
            "pass" if replay_validator_ready else "fail",
            replay_error
            or str(
                replay_status.get("handoff_recommendation")
                or replayed_validation_summary.get("detail")
                or synthetic_ingest_review_record_validation_status
            ),
        ),
        _check(
            "replayed_validation_passed",
            "pass" if synthetic_ingest_review_record_example_validated else "fail",
            replay_error or str(replayed_validation_summary.get("detail")),
        ),
        _check(
            "replayed_review_only_effect_retained",
            "pass" if replay_review_only_effect_retained else "fail",
            REVIEW_ONLY_EFFECT_DETAIL
            if replay_review_only_effect_retained
            else "replayed_validator_status_changed_repo_side_state_or_enablement",
        ),
    ]

    ingest_review_record_example_bundle_ready = all(
        check["status"] == "pass" for check in checks
    )

    gates = [
        _gate(
            "ingest_review_record_scaffold_ready",
            ingest_review_record_scaffold_ready,
            True,
            "This example bundle depends on the locked ingest-review record scaffold already being ready.",
        ),
        _gate(
            "ingest_review_record_validator_ready",
            ingest_review_record_validator_ready,
            True,
            "This example bundle depends on the ingest-review record validator contract already being ready.",
        ),
        _gate(
            "synthetic_example_payload_generated",
            synthetic_example_payload_generated,
            True,
            "The example bundle must expose one synthetic completed ingest-review record payload example.",
        ),
        _gate(
            "replayed_validation_passed",
            synthetic_ingest_review_record_example_validated,
            True,
            "The synthetic example payload must validate successfully through the existing ingest-review validator logic.",
        ),
        _gate(
            "review_only_default_off_effect_retained",
            review_only_contract_retained and replay_review_only_effect_retained,
            True,
            "The bundle must remain review-only/default-off/spec-only/no-solve and must not imply repo-state application or runtime enablement.",
        ),
        _gate(
            "example_bundle_not_actual_human_review_record",
            True,
            False,
            EXAMPLE_BUNDLE_NOTICE,
        ),
        _gate(
            "repo_side_review_state_not_applied",
            True,
            False,
            REVIEW_ONLY_EFFECT_DETAIL,
        ),
    ]
    gates.extend(
        _ensure_gate_entries(
            _merge_gate_entries(
                _blocked_gate_entries(scaffold_report),
                _blocked_gate_entries(validator_report),
                _blocked_gate_entries(replay_report),
            ),
            current_still_blocked_gate_ids=current_still_blocked_gate_ids,
            post_ingest_still_blocked_gate_ids=post_ingest_still_blocked_gate_ids,
        )
    )

    still_blocked_gate_ids = [
        str(gate.get("gate_id"))
        for gate in gates
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking"))
        and not bool(gate.get("satisfied"))
        and gate.get("gate_id")
    ]

    if ingest_review_record_example_bundle_ready:
        recommended_next_step = (
            "review_example_bundle_only_keep_actual_manual_ingest_review_separate"
        )
        handoff_recommendation = (
            "The example bundle is ready. Use the synthetic completed ingest-review "
            "payload and replayed validator summary as a demo/reference only. Keep "
            "reviewed_runtime_patch_exists=false, repo_side_review_state_updated=false, "
            "and runtime_enablement_allowed=false until a separate actual human "
            "ingest-review record is completed and reviewed."
        )
    else:
        recommended_next_step = "repair_ingest_review_record_example_bundle_inputs"
        handoff_recommendation = (
            "The example bundle is blocked. Repair the scaffold/validator inputs or the "
            "validator replay dependencies before using this review-only example bundle."
        )

    return {
        "metadata": {
            "source": INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_ingest_review_record_example_bundle_review_only_demo_not_applied"
            ),
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "paths": {
            "project_root": str(project_root),
            "ingest_review_record_scaffold": _display_path(
                project_root, ingest_review_record_scaffold_resolved
            ),
            "ingest_review_record_validator": _display_path(
                project_root, ingest_review_record_validator_resolved
            ),
            "reviewed_runtime_patch_ingest_gate": _display_path(
                project_root, replay_ingest_gate_path
            ),
            "signoff_record_validator": _display_path(
                project_root, replay_signoff_validator_path
            ),
        },
        "candidate": dict(candidate),
        "status": {
            "ingest_review_record_example_bundle_ready": bool(
                ingest_review_record_example_bundle_ready
            ),
            "synthetic_ingest_review_record_example_generated": bool(
                synthetic_example_payload_generated
            ),
            "synthetic_ingest_review_record_example_validated": bool(
                synthetic_ingest_review_record_example_validated
            ),
            "synthetic_ingest_review_record_validation_status": (
                synthetic_ingest_review_record_validation_status
            ),
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommended_next_step": recommended_next_step,
            "handoff_recommendation": handoff_recommendation,
        },
        "ingest_review_record_example_bundle": {
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "example_kind": "synthetic_completed_ingest_review_record_payload_demo",
            "actual_human_review_record": False,
            "applied_repo_state_update": False,
            "locked_target_review_state": dict(locked_target_review_state),
            "locked_reviewer_record_handoff": dict(locked_reviewer_record_handoff),
            "validator_target": validator_target,
            "synthetic_completed_ingest_review_record_payload": (
                synthetic_example_payload
            ),
            "replayed_validation_summary": replayed_validation_summary,
            "replay_instructions": {
                "validator_script": (
                    "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator.py"
                ),
                "validator_target": validator_target,
                "detail": REPLAY_INSTRUCTIONS_DETAIL,
            },
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "detail": REVIEW_ONLY_EFFECT_DETAIL,
            },
            "bundle_notice": EXAMPLE_BUNDLE_NOTICE,
        },
        "still_blocked_gate_ids": still_blocked_gate_ids,
        "gates": gates,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("ingest_review_record_example_bundle"))
    locked_target = _mapping(bundle.get("locked_target_review_state"))
    locked_handoff = _mapping(bundle.get("locked_reviewer_record_handoff"))
    replayed_validation = _mapping(bundle.get("replayed_validation_summary"))
    state_assertions = _mapping(bundle.get("preserved_state_assertions"))
    lines = [
        "# Phase 3B Anchor119 Row-Domain Ingest Review Record Example Bundle",
        "",
        f"- Example bundle ready: `{status.get('ingest_review_record_example_bundle_ready')}`",
        f"- Synthetic example generated: `{status.get('synthetic_ingest_review_record_example_generated')}`",
        f"- Synthetic example validated: `{status.get('synthetic_ingest_review_record_example_validated')}`",
        f"- Synthetic validation status: `{status.get('synthetic_ingest_review_record_validation_status')}`",
        f"- Repo-side review state updated: `{status.get('repo_side_review_state_updated')}`",
        f"- Reviewed runtime patch exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- Runtime enablement allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- Recommended next step: `{status.get('recommended_next_step')}`",
        f"- Handoff recommendation: {status.get('handoff_recommendation')}",
        f"- Still blocked gate ids: `{', '.join(_string_list(report.get('still_blocked_gate_ids'))) or '(none)'}`",
        f"- Bundle notice: {bundle.get('bundle_notice')}",
        "",
        "## Locked Contract",
        "",
        f"- Validator target: `{bundle.get('validator_target')}`",
        f"- Record identity: `{locked_target.get('record_identity')}`",
        f"- Record type: `{locked_target.get('record_type')}`",
        f"- Scope: `{locked_target.get('scope')}`",
        f"- Tracked field: `{locked_target.get('tracked_field')}`",
        f"- Handoff path shape: `{locked_handoff.get('handoff_path_shape')}`",
        "",
        "## Synthetic Example Payload",
        "",
        "```json",
        json.dumps(
            bundle.get("synthetic_completed_ingest_review_record_payload", {}),
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
        "## Replayed Validation Summary",
        "",
        f"- Validator source: `{replayed_validation.get('validator_source')}`",
        f"- Validator target: `{replayed_validation.get('validator_target')}`",
        f"- Validator ready: `{replayed_validation.get('ingest_review_record_validator_ready')}`",
        f"- Manual payload provided: `{replayed_validation.get('manual_ingest_review_record_provided')}`",
        f"- Manual payload validated: `{replayed_validation.get('manual_ingest_review_record_validated')}`",
        f"- Validation status: `{replayed_validation.get('manual_ingest_review_record_validation_status')}`",
        f"- Record payload path: `{replayed_validation.get('record_payload_path')}`",
        f"- Passed rule count: `{replayed_validation.get('passed_rule_count')}`",
        f"- Failed rule count: `{replayed_validation.get('failed_rule_count')}`",
        f"- Detail: {replayed_validation.get('detail')}",
        f"- Validator notice: {replayed_validation.get('validator_notice')}",
        "",
        "## Replayed Rule Results",
        "",
        "| Rule | Status | Field | Validation rule | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in list(replayed_validation.get("rule_results", [])):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('rule_id'))} | "
                f"{_markdown_cell(entry.get('status'))} | "
                f"{_markdown_cell(entry.get('field'))} | "
                f"{_markdown_cell(entry.get('validation_rule'))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )
    if not list(replayed_validation.get("rule_results", [])):
        lines.append("| `(not run)` | `not_run` |  |  | Replay did not produce rule results. |")
    lines.extend(
        [
            "",
            "## Preserved State Assertions",
            "",
            f"- Repo-side review state updated: `{state_assertions.get('repo_side_review_state_updated')}`",
            f"- Reviewed runtime patch exists: `{state_assertions.get('reviewed_runtime_patch_exists')}`",
            f"- Runtime enablement allowed: `{state_assertions.get('runtime_enablement_allowed')}`",
            f"- Detail: {state_assertions.get('detail')}",
            "",
            "## Replay Instructions",
            "",
            f"- Validator script: `{_mapping(bundle.get('replay_instructions')).get('validator_script')}`",
            f"- Detail: {_mapping(bundle.get('replay_instructions')).get('detail')}",
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


def render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    bundle = _mapping(report.get("ingest_review_record_example_bundle"))
    locked_target = _mapping(bundle.get("locked_target_review_state"))
    replayed_validation = _mapping(bundle.get("replayed_validation_summary"))
    return "\n".join(
        [
            "Phase 3B anchor119 row-domain ingest review record example bundle",
            "ingest_review_record_example_bundle_ready="
            + str(status.get("ingest_review_record_example_bundle_ready")),
            "synthetic_ingest_review_record_example_generated="
            + str(status.get("synthetic_ingest_review_record_example_generated")),
            "synthetic_ingest_review_record_example_validated="
            + str(status.get("synthetic_ingest_review_record_example_validated")),
            "synthetic_ingest_review_record_validation_status="
            + str(status.get("synthetic_ingest_review_record_validation_status")),
            "repo_side_review_state_updated="
            + str(status.get("repo_side_review_state_updated")),
            "reviewed_runtime_patch_exists="
            + str(status.get("reviewed_runtime_patch_exists")),
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed")),
            "still_blocked_gate_ids="
            + ",".join(_string_list(report.get("still_blocked_gate_ids"))),
            "validator_target=" + str(bundle.get("validator_target")),
            "record_identity=" + str(locked_target.get("record_identity")),
            "replayed_failed_rule_count="
            + str(replayed_validation.get("failed_rule_count")),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_ingest_review_record_example_bundle",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_synthetic_completed_ingest_review_record_payload(
    template_payload: Mapping[str, Any],
    *,
    locked_reviewer_record_handoff: Mapping[str, Any],
    required_review_conclusions: list[Mapping[str, Any]],
) -> Dict[str, Any]:
    if not template_payload:
        return {}
    payload = deepcopy(dict(template_payload))
    payload["ingest_reviewer_id"] = SYNTHETIC_EXAMPLE_REVIEWER_ID
    payload["ingest_reviewed_at"] = SYNTHETIC_EXAMPLE_REVIEWED_AT
    payload["review_decision"] = SYNTHETIC_EXAMPLE_REVIEW_DECISION
    payload["decision_notes"] = (
        "Synthetic example/demo payload only for replayable validation. "
        "Not an actual human ingest-review record and not an applied repo-state update."
    )
    payload["reviewer_record_validation_status"] = SYNTHETIC_EXAMPLE_VALIDATION_STATUS
    payload["reviewer_record_handoff_path"] = _populate_handoff_path(
        str(
            locked_reviewer_record_handoff.get("handoff_path_shape")
            or payload.get("reviewer_record_handoff_path")
            or ""
        ),
        reviewer_id=SYNTHETIC_EXAMPLE_REVIEWER_ID,
        reviewed_at_utc=SYNTHETIC_EXAMPLE_REVIEWED_AT,
    )
    required_review_conclusion_ids = _string_list(
        payload.get("required_review_conclusion_ids")
    ) or [
        str(entry.get("conclusion_id"))
        for entry in required_review_conclusions
        if entry.get("conclusion_id")
    ]
    conclusion_details = {
        str(entry.get("conclusion_id")): str(entry.get("detail") or "")
        for entry in required_review_conclusions
        if entry.get("conclusion_id")
    }
    payload["required_review_conclusion_ids"] = list(required_review_conclusion_ids)
    payload["review_conclusions"] = [
        {
            "conclusion_id": conclusion_id,
            "decision": "confirmed",
            "notes": (
                "Synthetic example/demo confirmation only. "
                + (
                    conclusion_details.get(conclusion_id)
                    or f"Replay confirms {conclusion_id}."
                )
            ).strip(),
        }
        for conclusion_id in required_review_conclusion_ids
    ]
    payload["required_reviewer_statement_ids"] = _string_list(
        payload.get("required_reviewer_statement_ids")
    )
    payload["current_still_blocked_gate_ids"] = _string_list(
        payload.get("current_still_blocked_gate_ids")
    )
    payload["post_ingest_still_blocked_gate_ids"] = _string_list(
        payload.get("post_ingest_still_blocked_gate_ids")
    )
    payload["repo_side_review_state_updated"] = False
    payload["reviewed_runtime_patch_exists"] = False
    payload["runtime_enablement_allowed"] = False
    return payload


def _populate_handoff_path(
    path_shape: str, *, reviewer_id: str, reviewed_at_utc: str
) -> str:
    if not str(path_shape).strip():
        return ""
    return (
        str(path_shape)
        .replace("<reviewer_id>", reviewer_id)
        .replace("<reviewed_at_utc>", _path_safe_timestamp(reviewed_at_utc))
    )


def _path_safe_timestamp(value: str) -> str:
    return str(value).strip().replace(":", "-").replace(" ", "_")


def _replay_validator_against_synthetic_payload(
    project_root: Path,
    *,
    ingest_review_record_scaffold_path: Path,
    reviewed_runtime_patch_ingest_gate_path: Optional[Path],
    signoff_record_validator_path: Optional[Path],
    synthetic_payload: Mapping[str, Any],
) -> tuple[Dict[str, Any], Optional[str]]:
    if not synthetic_payload:
        return {}, "synthetic_example_payload_missing"
    if (
        reviewed_runtime_patch_ingest_gate_path is None
        or signoff_record_validator_path is None
    ):
        return {}, "validator_replay_dependency_paths_missing"
    try:
        with tempfile.TemporaryDirectory(
            prefix="anchor119_ingest_review_record_example_"
        ) as temp_dir:
            synthetic_payload_path = Path(temp_dir) / "synthetic_example_payload.json"
            atomic_write_json(synthetic_payload_path, dict(synthetic_payload))
            report = (
                build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
                    project_root,
                    ingest_review_record_scaffold_path=ingest_review_record_scaffold_path,
                    reviewed_runtime_patch_ingest_gate_path=(
                        reviewed_runtime_patch_ingest_gate_path
                    ),
                    signoff_record_validator_path=signoff_record_validator_path,
                    ingest_review_record_payload_path=synthetic_payload_path,
                )
            )
            return dict(report), None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _build_replayed_validation_summary(
    *,
    replay_meta: Mapping[str, Any],
    replay_status: Mapping[str, Any],
    replay_validator: Mapping[str, Any],
    replay_actual_validation: Mapping[str, Any],
) -> Dict[str, Any]:
    detail = str(replay_actual_validation.get("detail") or "").strip()
    record_payload_path = str(replay_actual_validation.get("record_payload_path") or "")
    if record_payload_path:
        detail = detail.replace(record_payload_path, "synthetic_example_payload.json")
    return {
        "validator_source": replay_meta.get("source"),
        "validator_target": replay_validator.get("validator_target"),
        "ingest_review_record_validator_ready": bool(
            replay_status.get("ingest_review_record_validator_ready", False)
        ),
        "manual_ingest_review_record_provided": bool(
            replay_status.get("manual_ingest_review_record_provided", False)
        ),
        "manual_ingest_review_record_validated": bool(
            replay_status.get("manual_ingest_review_record_validated", False)
        ),
        "manual_ingest_review_record_validation_status": str(
            replay_status.get("manual_ingest_review_record_validation_status")
            or replay_actual_validation.get("validation_status")
            or "not_run"
        ),
        "record_payload_path": (
            "synthetic_example_payload.json"
            if replay_actual_validation.get("record_payload_provided", False)
            else None
        ),
        "record_payload_loaded": bool(
            replay_actual_validation.get("record_payload_loaded", False)
        ),
        "record_payload_validated": bool(
            replay_actual_validation.get("record_payload_validated", False)
        ),
        "passed_rule_count": _coerce_int(
            replay_actual_validation.get("passed_rule_count")
        ),
        "failed_rule_count": _coerce_int(
            replay_actual_validation.get("failed_rule_count")
        ),
        "detail": detail or replay_status.get("handoff_recommendation"),
        "validator_notice": replay_validator.get("validator_notice"),
        "rule_results": [
            dict(entry)
            for entry in list(replay_actual_validation.get("rule_results", []))
            if isinstance(entry, Mapping)
        ],
    }


def _ensure_gate_entries(
    entries: list[Mapping[str, Any]],
    *,
    current_still_blocked_gate_ids: list[str],
    post_ingest_still_blocked_gate_ids: list[str],
) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        gate_id = str(entry.get("gate_id") or "").strip()
        if not gate_id or gate_id in seen:
            continue
        merged.append(
            {
                "gate_id": gate_id,
                "satisfied": bool(entry.get("satisfied", False)),
                "blocking": bool(entry.get("blocking", False)),
                "detail": str(entry.get("detail") or ""),
            }
        )
        seen.add(gate_id)
    for gate_id in current_still_blocked_gate_ids:
        gate_id_text = str(gate_id).strip()
        if not gate_id_text or gate_id_text in seen:
            continue
        merged.append(
            _gate(
                gate_id_text,
                False,
                True,
                "Current still-blocked gate preserved into the review-only example bundle.",
            )
        )
        seen.add(gate_id_text)
    for gate_id in post_ingest_still_blocked_gate_ids:
        gate_id_text = str(gate_id).strip()
        if not gate_id_text or gate_id_text in seen:
            continue
        merged.append(
            _gate(
                gate_id_text,
                False,
                True,
                "This gate must remain blocked even after replaying the synthetic example validation.",
            )
        )
        seen.add(gate_id_text)
    return merged


def _gate(gate_id: str, satisfied: bool, blocking: bool, detail: str) -> Dict[str, Any]:
    return {
        "gate_id": str(gate_id),
        "satisfied": bool(satisfied),
        "blocking": bool(blocking),
        "detail": str(detail),
    }


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
        entries.append(
            {
                "gate_id": gate_id,
                "satisfied": bool(gate.get("satisfied", False)),
                "blocking": bool(gate.get("blocking", False)),
                "detail": str(gate.get("detail") or ""),
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
                    "satisfied": bool(gate.get("satisfied", False)),
                    "blocking": bool(gate.get("blocking", False)),
                    "detail": str(gate.get("detail") or ""),
                }
            )
            seen.add(gate_id)
    return merged


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[Mapping[str, Any]] = []
    for entry in value:
        if isinstance(entry, Mapping):
            result.append(entry)
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


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


def _resolve_optional_path(project_root: Path, value: Any) -> Optional[Path]:
    text = str(value or "").strip()
    if not text:
        return None
    return _resolve_path(project_root, Path(text))


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Optional[Path]) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False).replace("|", "\\|")
    return str(value).replace("|", "\\|").replace("\n", " ")

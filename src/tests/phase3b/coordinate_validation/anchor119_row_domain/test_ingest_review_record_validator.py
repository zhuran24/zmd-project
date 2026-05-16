from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from src.search.phase3b.coordinate_validation.anchor119_row_domain.ingest_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_text,
)

STATEMENT_IDS = [
    "default_off_retained",
    "reserved_runtime_request_downgrades_to_advisory",
    "no_proof_source_promotion",
    "acceptance_refresh_required_before_enablement",
]
CURRENT_STILL_BLOCKED_GATE_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
]
POST_INGEST_STILL_BLOCKED_GATE_IDS = [
    "production_acceptance_refresh_completed",
]
REQUIRED_REVIEW_CONCLUSION_IDS = [
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
    "repo_side_review_state_may_mark_reviewed_runtime_patch",
    "runtime_enablement_remains_blocked_after_review",
    "post_ingest_still_blocked_gate_ids_preserved",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _ingest_review_record_scaffold_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1",
            "default_off": True,
            "review_only": True,
            "spec_only": True,
            "proof_source": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "ingest_review_record_scaffold_ready": True,
            "manual_ingest_review_record_completed": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_record_scaffold": {
            "record_type": "reviewed_runtime_patch_ingest_review_record_v0",
            "locked_target_review_state": {
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
                "current_field_value": False,
                "proposed_field_value_if_approved": True,
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": "json",
                "handoff_dir": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff",
                "handoff_path_shape": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff/anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json",
                "handoff_filename_tokens": [
                    "record_type_reviewed_runtime_patch_signoff_record_v0",
                    "candidate_67x13",
                    "anchor_119",
                    "reviewer_<reviewer_id>",
                    "reviewed_at_<reviewed_at_utc>",
                ],
            },
            "validator_contract_reference": {
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "required_record_fields": [
                    {"field": "record_type", "required": True},
                    {"field": "reviewer_id", "required": True},
                    {"field": "reviewed_at", "required": True},
                ],
            },
            "required_review_conclusions": [
                {
                    "conclusion_id": conclusion_id,
                    "required": True,
                    "template_value": "pending",
                    "detail": f"Resolve {conclusion_id} during future manual ingest review.",
                }
                for conclusion_id in REQUIRED_REVIEW_CONCLUSION_IDS
            ],
            "preserved_blocked_gates": {
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
                "runtime_enablement_allowed_after_review": False,
            },
            "ingest_review_record_template": {
                "record_type": "reviewed_runtime_patch_ingest_review_record_v0",
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "target_record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "target_record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
                "proposed_field_value_if_approved": True,
                "ingest_reviewer_id": "",
                "ingest_reviewed_at": "",
                "review_decision": "pending",
                "decision_notes": "",
                "reviewer_record_handoff_path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff/anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json",
                "reviewer_record_validation_status": "pending_manual_validation",
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "required_review_conclusion_ids": list(REQUIRED_REVIEW_CONCLUSION_IDS),
                "review_conclusions": [
                    {
                        "conclusion_id": conclusion_id,
                        "decision": "pending",
                        "notes": "",
                    }
                    for conclusion_id in REQUIRED_REVIEW_CONCLUSION_IDS
                ],
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
            "scaffold_notice": "Future human ingest-review record scaffold only.",
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch record does not exist yet.",
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "satisfied": False,
                "blocking": True,
                "detail": "Acceptance refresh still has not been run.",
            },
        ],
    }


def _reviewed_runtime_patch_ingest_gate_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_v1",
            "default_off": True,
            "review_only": True,
            "spec_only": True,
            "proof_source": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "reviewed_runtime_patch_ingest_gate_ready": True,
            "future_review_state_marking_prerequisites_met": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "missing_prerequisite_gate_ids": list(REQUIRED_REVIEW_CONCLUSION_IDS[:3]),
        },
        "reviewed_runtime_patch_ingest_gate": {
            "repo_side_review_state_target": {
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": "json",
                "handoff_dir": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff",
                "handoff_path_shape": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff/anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json",
                "handoff_filename_tokens": [
                    "record_type_reviewed_runtime_patch_signoff_record_v0",
                    "candidate_67x13",
                    "anchor_119",
                    "reviewer_<reviewer_id>",
                    "reviewed_at_<reviewed_at_utc>",
                ],
            },
            "ingest_review_contract": {
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
            },
        },
        "gates": [
            {
                "gate_id": "reviewer_signed_record_supplied_for_review",
                "satisfied": False,
                "blocking": True,
                "detail": "A future reviewer-signed record must be supplied before manual ingest review can mark the patch as reviewed.",
            },
            {
                "gate_id": "reviewer_signed_record_validates_against_locked_contract",
                "satisfied": False,
                "blocking": True,
                "detail": "A future reviewer-signed record must validate against the locked contract before manual ingest review can mark the patch as reviewed.",
            },
            {
                "gate_id": "separate_manual_ingest_review_approved",
                "satisfied": False,
                "blocking": True,
                "detail": "A separate future review must explicitly approve the repo-side review-state update.",
            },
        ],
    }


def _signoff_record_validator_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1",
            "default_off": True,
            "spec_only": True,
            "proof_source": False,
            "solver_invoked": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "signoff_record_validator_ready": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_record_validator": {
            "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
            "target_record_type": "reviewed_runtime_patch_signoff_record_v0",
            "scope": "candidate=67x13, anchor_idx=119",
            "required_reviewer_statement_ids": list(STATEMENT_IDS),
            "validator_rules": {
                "required_fields": [
                    {"field": "record_type", "required": True},
                    {"field": "reviewer_id", "required": True},
                    {"field": "reviewed_at", "required": True},
                ],
                "agreed_statement_ids": {
                    "field": "agreed_statement_ids",
                    "required": True,
                    "required_ids": list(STATEMENT_IDS),
                },
                "still_blocked_gate_ids": {
                    "field": "still_blocked_gate_ids",
                    "required": True,
                    "required_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                },
            },
            "actual_record_validation": {
                "record_payload_provided": False,
                "record_payload_validated": False,
                "validation_status": "not_run",
            },
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch record does not exist yet.",
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "satisfied": False,
                "blocking": True,
                "detail": "Acceptance refresh still has not been run.",
            },
        ],
    }


def _completed_ingest_review_record_payload() -> dict:
    payload = deepcopy(
        _ingest_review_record_scaffold_json()["ingest_review_record_scaffold"][
            "ingest_review_record_template"
        ]
    )
    payload.update(
        {
            "ingest_reviewer_id": "row-domain-reviewer",
            "ingest_reviewed_at": "2026-04-24T10:00:00Z",
            "review_decision": "approved_for_repo_side_review_state_marking",
            "decision_notes": "Manual ingest review completed against the locked scaffold contract.",
            "reviewer_record_handoff_path": (
                ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_"
                "reviewer_record_collection_20260424/reviewer_record_handoff/"
                "anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__"
                "candidate_67x13__anchor_119__reviewer_row-domain-reviewer__"
                "reviewed_at_2026-04-24T10-00-00Z.json"
            ),
            "reviewer_record_validation_status": "validated_against_locked_contract",
        }
    )
    payload["review_conclusions"] = [
        {
            "conclusion_id": conclusion_id,
            "decision": "confirmed",
            "notes": f"Resolved {conclusion_id} during manual ingest review.",
        }
        for conclusion_id in REQUIRED_REVIEW_CONCLUSION_IDS
    ]
    return payload


def _invalid_completed_ingest_review_record_payload() -> dict:
    payload = _completed_ingest_review_record_payload()
    payload["review_decision"] = "pending"
    payload["reviewer_record_handoff_path"] = "unexpected/other_record.json"
    payload["runtime_enablement_allowed"] = True
    payload["post_ingest_still_blocked_gate_ids"] = []
    payload["review_conclusions"][0]["decision"] = "pending"
    return payload


def _repo_state_remains_blocked(report: dict) -> bool:
    return (
        report["status"]["repo_side_review_state_updated"] is False
        and report["status"]["reviewed_runtime_patch_exists"] is False
        and report["status"]["runtime_enablement_allowed"] is False
    )


def test_anchor119_row_domain_ingest_review_record_validator_ready_without_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    ingest_review_record_scaffold_path = tmp_path / "ingest_review_record_scaffold.json"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    _write_json(
        ingest_review_record_scaffold_path, _ingest_review_record_scaffold_json()
    )
    _write_json(
        reviewed_runtime_patch_ingest_gate_path,
        _reviewed_runtime_patch_ingest_gate_json(),
    )
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            project_root,
            ingest_review_record_scaffold_path=ingest_review_record_scaffold_path,
            reviewed_runtime_patch_ingest_gate_path=reviewed_runtime_patch_ingest_gate_path,
            signoff_record_validator_path=signoff_record_validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["repo_side_review_state_updated"] is False
    assert report["status"]["ingest_review_record_validator_ready"] is True
    assert report["status"]["manual_ingest_review_record_provided"] is False
    assert report["status"]["manual_ingest_review_record_validated"] is False
    assert report["status"]["manual_ingest_review_record_validation_status"] == "not_run"
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["recommended_next_step"] == (
        "handoff_ingest_review_record_validator_contract_for_future_manual_validation"
    )
    validator = report["ingest_review_record_validator"]
    assert validator["validator_target"] == "future_completed_ingest_review_record_payload"
    assert validator["target_record_type"] == "reviewed_runtime_patch_ingest_review_record_v0"
    assert validator["locked_target_review_state"]["record_identity"] == (
        "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
    )
    blocked_gate_contract = validator["blocked_gate_contract"]
    assert blocked_gate_contract["current_still_blocked_gate_ids"] == (
        CURRENT_STILL_BLOCKED_GATE_IDS
    )
    assert blocked_gate_contract["post_ingest_still_blocked_gate_ids"] == (
        POST_INGEST_STILL_BLOCKED_GATE_IDS
    )
    assert blocked_gate_contract["repo_side_review_state_updated_after_validation"] is False
    assert blocked_gate_contract["runtime_enablement_allowed_after_validation"] is False
    rules = validator["validator_rules"]
    field_rules = {entry["field"]: entry for entry in rules["required_fields"]}
    assert field_rules["record_type"]["validation_rule"] == "must_equal_template_value"
    assert (
        field_rules["ingest_reviewer_id"]["validation_rule"]
        == "must_be_present_and_non_empty"
    )
    assert (
        field_rules["review_decision"]["validation_rule"]
        == "must_be_present_and_not_pending"
    )
    assert (
        field_rules["reviewer_record_handoff_path"]["validation_rule"]
        == "validated_by_reviewer_record_handoff_path_rule"
    )
    assert (
        field_rules["reviewer_record_validation_status"]["validation_rule"]
        == "must_be_present_and_not_pending_manual_validation"
    )
    assert (
        rules["required_review_conclusion_ids"]["required_ids"]
        == REQUIRED_REVIEW_CONCLUSION_IDS
    )
    assert (
        rules["current_still_blocked_gate_ids"]["required_ids"]
        == CURRENT_STILL_BLOCKED_GATE_IDS
    )
    assert (
        rules["post_ingest_still_blocked_gate_ids"]["required_ids"]
        == POST_INGEST_STILL_BLOCKED_GATE_IDS
    )
    assert validator["actual_record_validation"]["record_payload_validated"] is False
    assert validator["actual_record_validation"]["record_payload_loaded"] is False
    assert validator["actual_record_validation"]["record_payload_path"] is None
    assert validator["actual_record_validation"]["validation_status"] == "not_run"
    assert validator["actual_record_validation"]["failed_rule_count"] == 0
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_text(
            report
        )
    )
    assert "Ingest Review Record Validator" in markdown
    assert "Review-only/default-off validator" in markdown
    assert "Per-Rule Validation Results" in markdown
    assert "No payload supplied" in markdown
    assert "ingest_review_record_validator_ready=True" in text
    assert "manual_ingest_review_record_validation_status=not_run" in text


def test_anchor119_row_domain_ingest_review_record_validator_validates_supplied_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    ingest_review_record_scaffold_path = tmp_path / "ingest_review_record_scaffold.json"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    ingest_review_record_payload_path = tmp_path / "completed_ingest_review_record.json"
    _write_json(
        ingest_review_record_scaffold_path, _ingest_review_record_scaffold_json()
    )
    _write_json(
        reviewed_runtime_patch_ingest_gate_path,
        _reviewed_runtime_patch_ingest_gate_json(),
    )
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(
        ingest_review_record_payload_path, _completed_ingest_review_record_payload()
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            project_root,
            ingest_review_record_scaffold_path=ingest_review_record_scaffold_path,
            reviewed_runtime_patch_ingest_gate_path=reviewed_runtime_patch_ingest_gate_path,
            signoff_record_validator_path=signoff_record_validator_path,
            ingest_review_record_payload_path=ingest_review_record_payload_path,
        )
    )

    assert report["status"]["ingest_review_record_validator_ready"] is True
    assert report["status"]["manual_ingest_review_record_provided"] is True
    assert report["status"]["manual_ingest_review_record_validated"] is True
    assert report["status"]["manual_ingest_review_record_validation_status"] == "passed"
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["recommended_next_step"] == (
        "review_only_validated_ingest_review_record_payload_retains_blocked_gates"
    )
    actual_validation = report["ingest_review_record_validator"]["actual_record_validation"]
    assert actual_validation["record_payload_provided"] is True
    assert actual_validation["record_payload_loaded"] is True
    assert actual_validation["record_payload_validated"] is True
    assert actual_validation["validation_status"] == "passed"
    assert actual_validation["failed_rule_count"] == 0
    assert actual_validation["passed_rule_count"] > 0
    rule_results = {entry["rule_id"]: entry for entry in actual_validation["rule_results"]}
    assert rule_results["required_field:review_decision"]["status"] == "pass"
    assert rule_results["reviewer_record_handoff_path"]["status"] == "pass"
    assert rule_results["required_review_conclusion_ids"]["status"] == "pass"
    assert rule_results["review_conclusions"]["status"] == "pass"
    assert _repo_state_remains_blocked(report)


def test_anchor119_row_domain_ingest_review_record_validator_rejects_invalid_supplied_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    ingest_review_record_scaffold_path = tmp_path / "ingest_review_record_scaffold.json"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    ingest_review_record_payload_path = tmp_path / "invalid_ingest_review_record.json"
    _write_json(
        ingest_review_record_scaffold_path, _ingest_review_record_scaffold_json()
    )
    _write_json(
        reviewed_runtime_patch_ingest_gate_path,
        _reviewed_runtime_patch_ingest_gate_json(),
    )
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(
        ingest_review_record_payload_path,
        _invalid_completed_ingest_review_record_payload(),
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            project_root,
            ingest_review_record_scaffold_path=ingest_review_record_scaffold_path,
            reviewed_runtime_patch_ingest_gate_path=reviewed_runtime_patch_ingest_gate_path,
            signoff_record_validator_path=signoff_record_validator_path,
            ingest_review_record_payload_path=ingest_review_record_payload_path,
        )
    )

    assert report["status"]["ingest_review_record_validator_ready"] is True
    assert report["status"]["manual_ingest_review_record_provided"] is True
    assert report["status"]["manual_ingest_review_record_validated"] is False
    assert report["status"]["manual_ingest_review_record_validation_status"] == "failed"
    assert report["status"]["recommended_next_step"] == (
        "repair_supplied_ingest_review_record_payload_against_locked_contract"
    )
    actual_validation = report["ingest_review_record_validator"]["actual_record_validation"]
    assert actual_validation["record_payload_loaded"] is True
    assert actual_validation["record_payload_validated"] is False
    assert actual_validation["validation_status"] == "failed"
    assert actual_validation["failed_rule_count"] >= 1
    failed_rule_ids = {
        entry["rule_id"]
        for entry in actual_validation["rule_results"]
        if entry["status"] == "fail"
    }
    assert "required_field:review_decision" in failed_rule_ids
    assert "reviewer_record_handoff_path" in failed_rule_ids
    assert "required_field:runtime_enablement_allowed" in failed_rule_ids
    assert "post_ingest_still_blocked_gate_ids" in failed_rule_ids
    assert "review_conclusions" in failed_rule_ids
    assert "runtime_enablement_allowed stays false" in actual_validation["detail"]


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        ("scaffold", "ingest_review_record_scaffold_present"),
        ("ingest_gate", "reviewed_runtime_patch_ingest_gate_present"),
        ("signoff_validator", "signoff_record_validator_present"),
    ],
)
def test_anchor119_row_domain_ingest_review_record_validator_fails_if_upstream_artifact_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    ingest_review_record_scaffold_path = tmp_path / "ingest_review_record_scaffold.json"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    if missing_name != "scaffold":
        _write_json(
            ingest_review_record_scaffold_path, _ingest_review_record_scaffold_json()
        )
    if missing_name != "ingest_gate":
        _write_json(
            reviewed_runtime_patch_ingest_gate_path,
            _reviewed_runtime_patch_ingest_gate_json(),
        )
    if missing_name != "signoff_validator":
        _write_json(signoff_record_validator_path, _signoff_record_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            project_root,
            ingest_review_record_scaffold_path=ingest_review_record_scaffold_path,
            reviewed_runtime_patch_ingest_gate_path=reviewed_runtime_patch_ingest_gate_path,
            signoff_record_validator_path=signoff_record_validator_path,
        )
    )

    assert report["status"]["ingest_review_record_validator_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_ingest_review_record_validator_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    ingest_review_record_scaffold_path = tmp_path / "ingest_review_record_scaffold.json"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    ingest_review_record_payload_path = tmp_path / "completed_ingest_review_record.json"
    output_dir = tmp_path / "out"
    _write_json(
        ingest_review_record_scaffold_path, _ingest_review_record_scaffold_json()
    )
    _write_json(
        reviewed_runtime_patch_ingest_gate_path,
        _reviewed_runtime_patch_ingest_gate_json(),
    )
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(
        ingest_review_record_payload_path, _completed_ingest_review_record_payload()
    )
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_ingest_review_record_validator.py"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--ingest-review-record-scaffold",
            str(ingest_review_record_scaffold_path),
            "--reviewed-runtime-patch-ingest-gate",
            str(reviewed_runtime_patch_ingest_gate_path),
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--ingest-review-record-payload",
            str(ingest_review_record_payload_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain ingest review record validator" in no_write.stdout
    assert "ingest_review_record_validator_ready=True" in no_write.stdout
    assert "manual_ingest_review_record_provided=True" in no_write.stdout
    assert "manual_ingest_review_record_validated=True" in no_write.stdout
    assert "manual_ingest_review_record_validation_status=passed" in no_write.stdout
    assert "actual_record_validation_status=passed" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--ingest-review-record-scaffold",
            str(ingest_review_record_scaffold_path),
            "--reviewed-runtime-patch-ingest-gate",
            str(reviewed_runtime_patch_ingest_gate_path),
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--ingest-review-record-payload",
            str(ingest_review_record_payload_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_ingest_review_record_validator_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_ingest_review_record_validator.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["ingest_review_record_validator_ready"] is True
    assert payload["status"]["manual_ingest_review_record_provided"] is True
    assert payload["status"]["manual_ingest_review_record_validated"] is True
    assert payload["status"]["manual_ingest_review_record_validation_status"] == "passed"
    assert (
        payload["ingest_review_record_validator"]["actual_record_validation"][
            "record_payload_validated"
        ]
        is True
    )
    assert (
        output_dir / "anchor119_row_domain_ingest_review_record_validator.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_ingest_review_record_validator.txt"
    ).exists()

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _metadata(source: str) -> dict:
    return {
        "source": source,
        "spec_only": True,
        "review_only": True,
        "default_off": True,
        "runtime_precheck_enabled": False,
        "runtime_semantics_changed": False,
        "proof_source": False,
        "candidate_elimination_claim": False,
        "solver_invoked": False,
        "acceptance_executed": False,
    }


def _candidate() -> dict:
    return {
        "key": "67x13",
        "anchor_idx": 119,
        "formulation_profile": "joined_xy_block64_all_templates",
    }


def _locked_acceptance_command() -> str:
    return (
        "python temp_scripts/benchmark_parallelism.py --suite-kind "
        "production-acceptance --suite-output "
        ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )


def _locked_acceptance_result_path() -> str:
    return ".codex_test_logs/phase3b/production_acceptance_after_change.json"


def _default_runner() -> str:
    return "scripts/run_prod_4x4_normal.ps1"


def _acceptance_authorization_review_record_scaffold_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_record_scaffold_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_review_record_scaffold_ready": True,
            "future_manual_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "authorization_review_completed": False,
            "reviewed_runtime_patch_exists": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_review_record_scaffold": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "review_only": True,
            "default_off": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "authorization_review_completed": False,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "production_profile_locked": True,
                "default_production_runner": _default_runner(),
                "default_production_runner_locked": True,
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_command_locked": True,
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                "exact_future_acceptance_result_path_locked": True,
                "command_matches_result_path": True,
            },
            "required_record_fields": [
                {
                    "field": "record_type",
                    "required": True,
                    "template_value": "acceptance_execution_authorization_review_record_v0",
                    "detail": "Carry forward the locked authorization-review record type.",
                },
                {
                    "field": "reviewer_id",
                    "required": True,
                    "template_value": "",
                    "detail": "Human reviewer must populate reviewer identity later.",
                },
                {
                    "field": "reviewed_at",
                    "required": True,
                    "template_value": "",
                    "detail": "Human reviewer must populate review timestamp later.",
                },
                {
                    "field": "verdict",
                    "required": True,
                    "template_value": "pending",
                    "detail": "Remain pending until a future human review is completed.",
                },
                {
                    "field": "authorization_granted",
                    "required": True,
                    "template_value": False,
                    "detail": "Future reviewer must explicitly decide this field.",
                },
                {
                    "field": "runtime_enablement_allowed",
                    "required": True,
                    "template_value": False,
                    "detail": "Must remain false.",
                },
                {
                    "field": "acceptance_executed",
                    "required": True,
                    "template_value": False,
                    "detail": "Must remain false.",
                },
                {
                    "field": "locked_execution_target",
                    "required": True,
                    "template_value": {
                        "production_profile_id": "prod_4x4_normal",
                        "default_production_runner": _default_runner(),
                        "exact_future_acceptance_command": _locked_acceptance_command(),
                        "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                    },
                    "detail": "Carry forward the locked prod_4x4 target.",
                },
                {
                    "field": "required_conclusion_ids",
                    "required": True,
                    "template_value": [
                        "locked_prod_4x4_normal_target_confirmed",
                        "reviewed_runtime_patch_exists",
                    ],
                    "detail": "Carry forward required review conclusions.",
                },
                {
                    "field": "required_runtime_patch_statement_ids",
                    "required": True,
                    "template_value": [
                        "default_off_retained",
                        "acceptance_refresh_required_before_enablement",
                    ],
                    "detail": "Carry forward required runtime patch statements.",
                },
                {
                    "field": "missing_prerequisite_gate_ids",
                    "required": True,
                    "template_value": ["reviewed_runtime_patch_exists"],
                    "detail": "Carry forward missing prerequisite gates.",
                },
                {
                    "field": "notes",
                    "required": True,
                    "template_value": "",
                    "detail": "Human reviewer notes go here later.",
                },
            ],
            "required_review_conclusions": [
                {
                    "conclusion_id": "locked_prod_4x4_normal_target_confirmed",
                    "required": True,
                    "currently_satisfied": True,
                    "detail": "Locked prod_4x4_normal target is explicit.",
                },
                {
                    "conclusion_id": "reviewed_runtime_patch_exists",
                    "required": True,
                    "currently_satisfied": False,
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                },
            ],
            "required_runtime_patch_statement_ids": [
                "default_off_retained",
                "acceptance_refresh_required_before_enablement",
            ],
            "missing_prerequisites": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                }
            ],
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "required": True,
                    "detail": "Keep runtime_enablement_allowed=false.",
                }
            ],
            "scaffolded_authorization_review_record_payload": {
                "record_type": "acceptance_execution_authorization_review_record_v0",
                "reviewer_id": "",
                "reviewed_at": "",
                "verdict": "pending",
                "authorization_granted": False,
                "runtime_enablement_allowed": False,
                "acceptance_executed": False,
                "locked_execution_target": {
                    "production_profile_id": "prod_4x4_normal",
                    "default_production_runner": _default_runner(),
                    "exact_future_acceptance_command": _locked_acceptance_command(),
                    "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                },
                "required_conclusion_ids": [
                    "locked_prod_4x4_normal_target_confirmed",
                    "reviewed_runtime_patch_exists",
                ],
                "required_runtime_patch_statement_ids": [
                    "default_off_retained",
                    "acceptance_refresh_required_before_enablement",
                ],
                "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
                "notes": "",
            },
            "scaffold_notice": "Pending scaffold only; not an actual validated review record.",
        },
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch signoff record is still absent.",
            }
        ],
    }


def _acceptance_authorization_review_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_bundle_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_review_bundle_ready": True,
            "future_execution_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "reviewed_runtime_patch_exists": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_review_bundle": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "review_only": True,
            "default_off": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "production_profile_locked": True,
                "default_production_runner": _default_runner(),
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                "command_matches_result_path": True,
            },
            "reviewed_runtime_patch_state": {
                "required_reviewer_statement_ids": [
                    "default_off_retained",
                    "acceptance_refresh_required_before_enablement",
                ]
            },
        },
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch signoff record is still absent.",
            }
        ],
    }


def _acceptance_execution_gate_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_execution_gate_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_execution_gate_ready": True,
            "acceptance_execution_authorization_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "reviewed_runtime_patch_exists": False,
            "acceptance_executed": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_execution_gate": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "default_production_runner": _default_runner(),
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
            },
        },
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch signoff record is still absent.",
            }
        ],
    }


def _acceptance_result_validator_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_result_validator_v1",
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
        "candidate": _candidate(),
        "status": {
            "acceptance_result_validator_ready": True,
            "runtime_enablement_allowed": False,
            "acceptance_result_validation_performed": False,
            "acceptance_result_validation_passed": False,
        },
        "acceptance_result_validator": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "expected_result_path": _locked_acceptance_result_path(),
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "required": True,
                    "detail": "Keep runtime_enablement_allowed=false during future validation.",
                }
            ],
        },
        "result_validation": {
            "acceptance_result_provided": False,
            "validation_performed": False,
            "validation_passed": False,
            "summary": "No real acceptance result JSON was provided.",
        },
    }


def _valid_completed_authorization_review_record_payload() -> dict:
    return {
        "record_type": "acceptance_execution_authorization_review_record_v0",
        "reviewer_id": "reviewer_anchor119",
        "reviewed_at": "2026-04-24T10:15:00Z",
        "verdict": "blocked_until_reviewed_runtime_patch_exists",
        "authorization_granted": False,
        "authorization_review_completed": True,
        "runtime_enablement_allowed": False,
        "acceptance_executed": False,
        "locked_execution_target": {
            "production_profile_id": "prod_4x4_normal",
            "default_production_runner": _default_runner(),
            "exact_future_acceptance_command": _locked_acceptance_command(),
            "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
        },
        "required_conclusion_ids": [
            "locked_prod_4x4_normal_target_confirmed",
            "reviewed_runtime_patch_exists",
        ],
        "required_runtime_patch_statement_ids": [
            "default_off_retained",
            "acceptance_refresh_required_before_enablement",
        ],
        "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        "notes": "Completed review recorded without authorizing execution.",
    }


def _invalid_completed_authorization_review_record_payload() -> dict:
    payload = _valid_completed_authorization_review_record_payload()
    payload["verdict"] = "pending"
    payload["authorization_granted"] = True
    payload["runtime_enablement_allowed"] = True
    payload["missing_prerequisite_gate_ids"] = []
    return payload


def test_anchor119_row_domain_acceptance_authorization_review_record_validator_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    scaffold_path = tmp_path / "acceptance_authorization_review_record_scaffold.json"
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    result_validator_path = tmp_path / "acceptance_result_validator.json"
    _write_json(scaffold_path, _acceptance_authorization_review_record_scaffold_json())
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(result_validator_path, _acceptance_result_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            project_root,
            acceptance_authorization_review_record_scaffold_path=scaffold_path,
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=result_validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_review_record_validator_v1"
    )
    assert (
        report["status"]["acceptance_authorization_review_record_validator_ready"] is True
    )
    assert (
        report["status"]["future_manual_authorization_review_prerequisites_met"] is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    assert report["status"]["authorization_review_completed"] is False
    assert report["status"]["authorization_review_record_provided"] is False
    assert report["status"]["authorization_review_record_validated"] is False
    assert report["still_blocked_gate_ids"] == ["reviewed_runtime_patch_exists"]
    validator = report["acceptance_authorization_review_record_validator"]
    locked_execution_target = validator["locked_execution_target"]
    assert validator["target_record_type"] == (
        "acceptance_execution_authorization_review_record_v0"
    )
    assert validator["scope"] == "candidate=67x13, anchor_idx=119"
    assert locked_execution_target["production_profile_id"] == "prod_4x4_normal"
    assert (
        locked_execution_target["exact_future_acceptance_command"]
        == _locked_acceptance_command()
    )
    assert (
        locked_execution_target["exact_future_acceptance_result_path"]
        == _locked_acceptance_result_path()
    )
    rules = validator["validator_rules"]
    field_rules = {entry["field"]: entry for entry in rules["required_fields"]}
    assert field_rules["record_type"]["validation_rule"] == "must_equal_template_value"
    assert field_rules["reviewer_id"]["validation_rule"] == (
        "must_be_present_and_non_empty"
    )
    assert rules["required_conclusion_ids"]["required_ids"] == [
        "locked_prod_4x4_normal_target_confirmed",
        "reviewed_runtime_patch_exists",
    ]
    assert rules["required_runtime_patch_statement_ids"]["required_ids"] == [
        "default_off_retained",
        "acceptance_refresh_required_before_enablement",
    ]
    assert rules["missing_prerequisite_gate_ids"]["required_ids"] == [
        "reviewed_runtime_patch_exists"
    ]
    assert rules["locked_execution_target"]["validation_rule"] == (
        "must_match_locked_execution_target_exactly"
    )
    assert validator["actual_record_validation"]["record_payload_provided"] is False
    assert validator["actual_record_validation"]["record_payload_validated"] is False
    assert validator["actual_record_validation"]["validation_status"] == "not_run"
    assert validator["actual_record_validation"]["per_rule_results"] == []
    checklist_ids = [
        entry["checklist_id"] for entry in validator["future_validation_checklist"]
    ]
    assert "preserve_locked_execution_target_exactly" in checklist_ids
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text(
            report
        )
    )
    assert "Acceptance Authorization Review Record Validator" in markdown
    assert "Validator contract only" in markdown
    assert (
        "acceptance_authorization_review_record_validator_ready=True" in text
    )


def test_anchor119_row_domain_acceptance_authorization_review_record_validator_validates_completed_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    scaffold_path = tmp_path / "acceptance_authorization_review_record_scaffold.json"
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    result_validator_path = tmp_path / "acceptance_result_validator.json"
    payload_path = tmp_path / "completed_acceptance_authorization_review_record.json"
    _write_json(scaffold_path, _acceptance_authorization_review_record_scaffold_json())
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(result_validator_path, _acceptance_result_validator_json())
    _write_json(payload_path, _valid_completed_authorization_review_record_payload())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            project_root,
            acceptance_authorization_review_record_scaffold_path=scaffold_path,
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=result_validator_path,
            acceptance_authorization_review_record_payload_path=payload_path,
        )
    )

    assert (
        report["status"]["acceptance_authorization_review_record_validator_ready"] is True
    )
    assert report["status"]["authorization_review_record_provided"] is True
    assert report["status"]["authorization_review_record_validated"] is True
    assert report["status"]["authorization_review_completed"] is True
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    validator = report["acceptance_authorization_review_record_validator"]
    actual_validation = validator["actual_record_validation"]
    assert actual_validation["record_payload_loaded"] is True
    assert actual_validation["record_payload_validated"] is True
    assert actual_validation["validation_status"] == "passed"
    assert actual_validation["record_payload_path"] == str(payload_path.resolve())
    assert actual_validation["failed_rule_count"] == 0
    rule_results = {
        entry["rule_id"]: entry for entry in actual_validation["per_rule_results"]
    }
    assert rule_results["field:verdict"]["status"] == "pass"
    assert rule_results["completed_review_state"]["status"] == "pass"
    assert (
        rule_results[
            "authorization_grant_consistency_with_missing_prerequisites"
        ]["status"]
        == "pass"
    )
    assert "does not authorize execution" in actual_validation["detail"]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_text(
            report
        )
    )
    assert "Authorization review record provided: `True`" in markdown
    assert "Actual Record Rule Results" in markdown
    assert "authorization_review_record_provided=True" in text
    assert "actual_record_validation_status=passed" in text


def test_anchor119_row_domain_acceptance_authorization_review_record_validator_rejects_invalid_completed_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    scaffold_path = tmp_path / "acceptance_authorization_review_record_scaffold.json"
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    result_validator_path = tmp_path / "acceptance_result_validator.json"
    payload_path = tmp_path / "invalid_acceptance_authorization_review_record.json"
    _write_json(scaffold_path, _acceptance_authorization_review_record_scaffold_json())
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(result_validator_path, _acceptance_result_validator_json())
    _write_json(payload_path, _invalid_completed_authorization_review_record_payload())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            project_root,
            acceptance_authorization_review_record_scaffold_path=scaffold_path,
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=result_validator_path,
            acceptance_authorization_review_record_payload_path=payload_path,
        )
    )

    assert (
        report["status"]["acceptance_authorization_review_record_validator_ready"] is True
    )
    assert report["status"]["authorization_review_record_provided"] is True
    assert report["status"]["authorization_review_record_validated"] is False
    assert report["status"]["authorization_review_completed"] is False
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    actual_validation = report["acceptance_authorization_review_record_validator"][
        "actual_record_validation"
    ]
    assert actual_validation["record_payload_loaded"] is True
    assert actual_validation["validation_status"] == "failed"
    failed_rule_ids = set(actual_validation["failed_rule_ids"])
    assert "field:verdict" in failed_rule_ids
    assert "field:runtime_enablement_allowed" in failed_rule_ids
    assert "ids:missing_prerequisite_gate_ids" in failed_rule_ids
    assert "completed_review_state" in failed_rule_ids
    assert (
        "authorization_grant_consistency_with_missing_prerequisites"
        in failed_rule_ids
    )


def test_anchor119_row_domain_acceptance_authorization_review_record_validator_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    result_validator_path = tmp_path / "acceptance_result_validator.json"
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(result_validator_path, _acceptance_result_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            project_root,
            acceptance_authorization_review_record_scaffold_path=tmp_path
            / "missing_acceptance_authorization_review_record_scaffold.json",
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=result_validator_path,
        )
    )

    assert (
        report["status"]["acceptance_authorization_review_record_validator_ready"]
        is False
    )
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "acceptance_authorization_review_record_scaffold_present" in failed


def test_anchor119_row_domain_acceptance_authorization_review_record_validator_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    scaffold_path = tmp_path / "acceptance_authorization_review_record_scaffold.json"
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    result_validator_path = tmp_path / "acceptance_result_validator.json"
    payload_path = tmp_path / "completed_acceptance_authorization_review_record.json"
    output_dir = tmp_path / "out"
    _write_json(scaffold_path, _acceptance_authorization_review_record_scaffold_json())
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(result_validator_path, _acceptance_result_validator_json())
    _write_json(payload_path, _valid_completed_authorization_review_record_payload())
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts"
        / "phase3b"
        / "coordinate_validation"
        / "anchor119_row_domain"
        / "build_acceptance_authorization_review_record_validator.py"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--acceptance-authorization-review-record-scaffold",
            str(scaffold_path),
            "--acceptance-authorization-review-bundle",
            str(bundle_path),
            "--acceptance-execution-gate",
            str(gate_path),
            "--acceptance-result-validator",
            str(result_validator_path),
            "--acceptance-authorization-review-record-payload",
            str(payload_path),
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

    assert (
        "Phase 3B anchor119 row-domain acceptance authorization review record validator"
        in no_write.stdout
    )
    assert "authorization_review_record_provided=True" in no_write.stdout
    assert "authorization_review_record_validated=True" in no_write.stdout
    assert "actual_record_validation_status=passed" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--acceptance-authorization-review-record-scaffold",
            str(scaffold_path),
            "--acceptance-authorization-review-bundle",
            str(bundle_path),
            "--acceptance-execution-gate",
            str(gate_path),
            "--acceptance-result-validator",
            str(result_validator_path),
            "--acceptance-authorization-review-record-payload",
            str(payload_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (
        "anchor119_row_domain_acceptance_authorization_review_record_validator_json="
        in write.stdout
    )
    payload = json.loads(
        (
            output_dir
            / "anchor119_row_domain_acceptance_authorization_review_record_validator.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        payload["status"]["acceptance_authorization_review_record_validator_ready"]
        is True
    )
    assert payload["status"]["acceptance_execution_authorized"] is False
    assert payload["status"]["authorization_review_record_provided"] is True
    assert payload["status"]["authorization_review_record_validated"] is True
    assert (
        payload["acceptance_authorization_review_record_validator"][
            "actual_record_validation"
        ]["validation_status"]
        == "passed"
    )
    assert (
        output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_validator.md"
    ).exists()
    assert (
        output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_validator.txt"
    ).exists()

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator,
    render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _signoff_record_scaffold_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_v1",
            "default_off": True,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "signoff_record_scaffold_ready": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_record_scaffold": {
            "record_type": "reviewed_runtime_patch_signoff_record_v0",
            "scope": "candidate=67x13, anchor_idx=119",
            "required_reviewer_statement_ids": [
                "default_off_retained",
                "acceptance_refresh_required_before_enablement",
            ],
            "required_record_fields": [
                {
                    "field": "record_type",
                    "required": True,
                    "template_value": "reviewed_runtime_patch_signoff_record_v0",
                    "detail": "Carry forward the record type.",
                },
                {
                    "field": "reviewer_id",
                    "required": True,
                    "template_value": "",
                    "detail": "Populate reviewer id later.",
                },
                {
                    "field": "reviewed_at",
                    "required": True,
                    "template_value": "",
                    "detail": "Populate timestamp later.",
                },
                {
                    "field": "verdict",
                    "required": True,
                    "template_value": "pending",
                    "detail": "Keep verdict explicit.",
                },
                {
                    "field": "scope",
                    "required": True,
                    "template_value": "candidate=67x13, anchor_idx=119",
                    "detail": "Carry forward scope.",
                },
                {
                    "field": "notes",
                    "required": True,
                    "template_value": "",
                    "detail": "Populate reviewer notes later.",
                },
                {
                    "field": "agreed_statement_ids",
                    "required": True,
                    "template_value": [
                        "default_off_retained",
                        "acceptance_refresh_required_before_enablement",
                    ],
                    "detail": "Carry forward reviewer statements.",
                },
                {
                    "field": "still_blocked_gate_ids",
                    "required": True,
                    "template_value": [
                        "reviewed_runtime_patch_exists",
                        "production_acceptance_refresh_completed",
                    ],
                    "detail": "Carry forward blocked gates.",
                },
            ],
            "pending_signoff_record_payload": {
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "reviewer_id": "",
                "reviewed_at": "",
                "verdict": "pending",
                "scope": "candidate=67x13, anchor_idx=119",
                "notes": "",
                "agreed_statement_ids": [
                    "default_off_retained",
                    "acceptance_refresh_required_before_enablement",
                ],
                "still_blocked_gate_ids": [
                    "reviewed_runtime_patch_exists",
                    "production_acceptance_refresh_completed",
                ],
            },
            "scaffold_notice": "Pending scaffold only; not actual signoff.",
        },
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
        ],
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


def _reviewer_record_prep_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_v1",
            "default_off": True,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "reviewer_record_prep_ready": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "reviewer_record_prep": {
            "record_type": "reviewed_runtime_patch_signoff_record_v0",
            "scope": "candidate=67x13, anchor_idx=119",
            "required_reviewer_statement_ids": [
                "default_off_retained",
                "acceptance_refresh_required_before_enablement",
            ],
            "required_record_fields": [
                {
                    "field": "record_type",
                    "required": True,
                    "template_value": "reviewed_runtime_patch_signoff_record_v0",
                    "detail": "Carry forward the record type.",
                },
                {
                    "field": "reviewer_id",
                    "required": True,
                    "template_value": "",
                    "detail": "Populate reviewer id later.",
                },
                {
                    "field": "reviewed_at",
                    "required": True,
                    "template_value": "",
                    "detail": "Populate timestamp later.",
                },
                {
                    "field": "verdict",
                    "required": True,
                    "template_value": "pending",
                    "detail": "Still pending; no real signoff yet.",
                },
                {
                    "field": "scope",
                    "required": True,
                    "template_value": "candidate=67x13, anchor_idx=119",
                    "detail": "Carry forward scope.",
                },
                {
                    "field": "notes",
                    "required": True,
                    "template_value": "",
                    "detail": "Populate reviewer notes later.",
                },
                {
                    "field": "agreed_statement_ids",
                    "required": True,
                    "template_value": [
                        "default_off_retained",
                        "acceptance_refresh_required_before_enablement",
                    ],
                    "detail": "Carry forward required statement ids.",
                },
                {
                    "field": "still_blocked_gate_ids",
                    "required": True,
                    "template_value": [
                        "reviewed_runtime_patch_exists",
                        "production_acceptance_refresh_completed",
                    ],
                    "detail": "Carry forward blocked gate ids.",
                },
            ],
        },
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
        ],
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


def _signoff_bundle_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1",
            "default_off": True,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "signoff_bundle_ready": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_bundle": {
            "scope": "candidate=67x13, anchor_idx=119",
            "required_reviewer_statements": [
                {
                    "statement_id": "default_off_retained",
                    "must_agree": True,
                    "detail": "Patch stays default-off.",
                },
                {
                    "statement_id": "acceptance_refresh_required_before_enablement",
                    "must_agree": True,
                    "detail": "Acceptance refresh stays blocked.",
                },
            ],
            "signoff_record_template": {
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "reviewer_id": "",
                "reviewed_at": "",
                "verdict": "pending",
                "scope": "candidate=67x13, anchor_idx=119",
                "notes": "",
                "agreed_statement_ids": [],
                "still_blocked_gate_ids": [
                    "reviewed_runtime_patch_exists",
                    "production_acceptance_refresh_completed",
                ],
            },
        },
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


def _valid_signoff_record_payload() -> dict:
    payload = json.loads(
        json.dumps(
            _signoff_record_scaffold_json()["signoff_record_scaffold"][
                "pending_signoff_record_payload"
            ]
        )
    )
    payload.update(
        {
            "reviewer_id": "row-domain-reviewer",
            "reviewed_at": "2026-04-24T10:00:00Z",
            "verdict": "review_only_validated_default_off",
            "notes": "Manual signoff payload checked against the locked validator contract.",
        }
    )
    return payload


def _invalid_signoff_record_payload() -> dict:
    payload = _valid_signoff_record_payload()
    payload["record_type"] = "unexpected_record_type"
    payload["reviewer_id"] = ""
    payload["agreed_statement_ids"] = [
        "default_off_retained",
        "unexpected_statement_id",
    ]
    payload["still_blocked_gate_ids"] = ["reviewed_runtime_patch_exists"]
    return payload


def _hard_gates_remain_false(report: dict) -> bool:
    return (
        report["status"]["reviewed_runtime_patch_exists"] is False
        and report["status"]["runtime_enablement_allowed"] is False
    )


def test_anchor119_row_domain_signoff_record_validator_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
    )
    assert report["status"]["signoff_record_validator_ready"] is True
    assert report["status"]["signoff_record_payload_provided"] is False
    assert report["status"]["signoff_record_payload_validated"] is False
    assert report["status"]["signoff_record_payload_validation_status"] == "not_run"
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["still_blocked_gate_ids"] == [
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
    ]
    validator = report["signoff_record_validator"]
    assert validator["target_record_type"] == "reviewed_runtime_patch_signoff_record_v0"
    assert validator["required_reviewer_statement_ids"] == [
        "default_off_retained",
        "acceptance_refresh_required_before_enablement",
    ]
    rules = validator["validator_rules"]
    field_rules = {entry["field"]: entry for entry in rules["required_fields"]}
    assert field_rules["record_type"]["validation_rule"] == "must_equal_template_value"
    assert field_rules["reviewer_id"]["validation_rule"] == "must_be_present_and_non_empty"
    assert (
        field_rules["reviewed_at"]["validation_rule"]
        == "must_be_iso8601_utc_timestamp"
    )
    assert (
        rules["agreed_statement_ids"]["required_ids"]
        == validator["required_reviewer_statement_ids"]
    )
    assert rules["still_blocked_gate_ids"]["required_ids"] == [
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
    ]
    assert validator["actual_record_validation"]["record_payload_provided"] is False
    assert validator["actual_record_validation"]["record_payload_loaded"] is False
    assert validator["actual_record_validation"]["record_payload_validated"] is False
    assert validator["actual_record_validation"]["validation_status"] == "not_run"
    assert validator["actual_record_validation"]["failed_rule_count"] == 0
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_text(
            report
        )
    )
    assert "Signoff Record Validator" in markdown
    assert "Validator contract only" in markdown
    assert "Per-rule validation results: not run because no payload was supplied." in markdown
    assert "signoff_record_validator_ready=True" in text
    assert _hard_gates_remain_false(report)


def test_anchor119_row_domain_signoff_record_validator_validates_supplied_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    signoff_record_payload_path = tmp_path / "completed_signoff_record.json"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(signoff_record_payload_path, _valid_signoff_record_payload())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
        signoff_record_payload_path=signoff_record_payload_path,
    )

    assert report["status"]["signoff_record_validator_ready"] is True
    assert report["status"]["signoff_record_payload_provided"] is True
    assert report["status"]["signoff_record_payload_validated"] is True
    assert report["status"]["signoff_record_payload_validation_status"] == "passed"
    assert report["status"]["recommended_next_step"] == (
        "review_only_validated_signoff_record_payload_retains_blocked_gates"
    )
    actual_validation = report["signoff_record_validator"]["actual_record_validation"]
    assert actual_validation["record_payload_loaded"] is True
    assert actual_validation["record_payload_validated"] is True
    assert actual_validation["failed_rule_count"] == 0
    assert actual_validation["passed_rule_count"] > 0
    rule_results = {
        entry["rule_id"]: entry for entry in actual_validation["rule_results"]
    }
    assert rule_results["required_field:record_type"]["status"] == "pass"
    assert rule_results["required_field:reviewer_id"]["status"] == "pass"
    assert rule_results["agreed_statement_ids"]["status"] == "pass"
    assert rule_results["still_blocked_gate_ids"]["status"] == "pass"
    assert _hard_gates_remain_false(report)


def test_anchor119_row_domain_signoff_record_validator_rejects_invalid_supplied_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    signoff_record_payload_path = tmp_path / "invalid_signoff_record.json"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(signoff_record_payload_path, _invalid_signoff_record_payload())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
        signoff_record_payload_path=signoff_record_payload_path,
    )

    assert report["status"]["signoff_record_validator_ready"] is True
    assert report["status"]["signoff_record_payload_provided"] is True
    assert report["status"]["signoff_record_payload_validated"] is False
    assert report["status"]["signoff_record_payload_validation_status"] == "failed"
    assert report["status"]["recommended_next_step"] == (
        "repair_supplied_signoff_record_payload_against_locked_contract"
    )
    actual_validation = report["signoff_record_validator"]["actual_record_validation"]
    assert actual_validation["record_payload_loaded"] is True
    assert actual_validation["record_payload_validated"] is False
    assert actual_validation["failed_rule_count"] >= 1
    failed_rule_ids = set(actual_validation["failed_rule_ids"])
    assert "required_field:record_type" in failed_rule_ids
    assert "required_field:reviewer_id" in failed_rule_ids
    assert "agreed_statement_ids" in failed_rule_ids
    assert "still_blocked_gate_ids" in failed_rule_ids
    assert "Repair/revalidate the supplied payload" in actual_validation["detail"]
    assert _hard_gates_remain_false(report)


def test_anchor119_row_domain_signoff_record_validator_rejects_non_utc_reviewed_at(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    signoff_record_payload_path = tmp_path / "non_utc_signoff_record.json"
    payload = _valid_signoff_record_payload()
    payload["reviewed_at"] = "2026-04-24T18:00:00+08:00"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(signoff_record_payload_path, payload)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
        signoff_record_payload_path=signoff_record_payload_path,
    )

    assert report["status"]["signoff_record_validator_ready"] is True
    assert report["status"]["signoff_record_payload_validated"] is False
    actual_validation = report["signoff_record_validator"]["actual_record_validation"]
    failed_rule_ids = set(actual_validation["failed_rule_ids"])
    assert "required_field:reviewed_at" in failed_rule_ids
    rule_results = {
        entry["rule_id"]: entry for entry in actual_validation["rule_results"]
    }
    assert rule_results["required_field:reviewed_at"]["validation_rule"] == (
        "must_be_iso8601_utc_timestamp"
    )
    assert _hard_gates_remain_false(report)


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        ("scaffold", "signoff_record_scaffold_present"),
        ("reviewer", "reviewer_record_prep_present"),
        ("signoff", "signoff_bundle_present"),
    ],
)
def test_anchor119_row_domain_signoff_record_validator_fails_if_upstream_artifact_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    if missing_name != "scaffold":
        _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    if missing_name != "reviewer":
        _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    if missing_name != "signoff":
        _write_json(signoff_bundle_path, _signoff_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
    )

    assert report["status"]["signoff_record_validator_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_signoff_record_validator_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    signoff_record_payload_path = tmp_path / "completed_signoff_record.json"
    output_dir = tmp_path / "out"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(signoff_record_payload_path, _valid_signoff_record_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator.py"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--signoff-record-scaffold",
            str(signoff_record_scaffold_path),
            "--reviewer-record-prep",
            str(reviewer_record_prep_path),
            "--signoff-bundle",
            str(signoff_bundle_path),
            "--signoff-record-payload",
            str(signoff_record_payload_path),
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

    assert "phase3b anchor119 row-domain signoff record validator" in no_write.stdout
    assert "signoff_record_payload_validated=True" in no_write.stdout
    assert "actual_record_validation_status=passed" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--signoff-record-scaffold",
            str(signoff_record_scaffold_path),
            "--reviewer-record-prep",
            str(reviewer_record_prep_path),
            "--signoff-bundle",
            str(signoff_bundle_path),
            "--signoff-record-payload",
            str(signoff_record_payload_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_signoff_record_validator_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_signoff_record_validator.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["signoff_record_validator_ready"] is True
    assert payload["status"]["signoff_record_payload_provided"] is True
    assert payload["status"]["signoff_record_payload_validated"] is True
    assert payload["status"]["reviewed_runtime_patch_exists"] is False
    assert payload["status"]["runtime_enablement_allowed"] is False
    assert (output_dir / "anchor119_row_domain_signoff_record_validator.md").exists()
    assert (output_dir / "anchor119_row_domain_signoff_record_validator.txt").exists()

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection import (
    build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection,
    render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_text,
)

STATEMENT_IDS = [
    "default_off_retained",
    "reserved_runtime_request_downgrades_to_advisory",
    "no_proof_source_promotion",
    "acceptance_refresh_required_before_enablement",
]
STILL_BLOCKED_GATE_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _pending_payload() -> dict:
    return {
        "record_type": "reviewed_runtime_patch_signoff_record_v0",
        "reviewer_id": "",
        "reviewed_at": "",
        "verdict": "pending",
        "scope": "candidate=67x13, anchor_idx=119",
        "notes": "",
        "agreed_statement_ids": list(STATEMENT_IDS),
        "still_blocked_gate_ids": list(STILL_BLOCKED_GATE_IDS),
    }


def _required_record_fields() -> list[dict]:
    return [
        {
            "field": "record_type",
            "required": True,
            "template_value": "reviewed_runtime_patch_signoff_record_v0",
            "detail": "Carry forward the fixed record type.",
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
            "detail": "Populate reviewed_at later.",
        },
        {
            "field": "verdict",
            "required": True,
            "template_value": "pending",
            "detail": "Still pending; no actual signoff yet.",
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
            "template_value": list(STATEMENT_IDS),
            "detail": "Carry forward required reviewer statement ids.",
        },
        {
            "field": "still_blocked_gate_ids",
            "required": True,
            "template_value": list(STILL_BLOCKED_GATE_IDS),
            "detail": "Carry forward still-blocked gate ids.",
        },
    ]


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
            "required_reviewer_statement_ids": list(STATEMENT_IDS),
            "required_record_fields": _required_record_fields(),
            "pending_signoff_record_payload": _pending_payload(),
            "scaffold_notice": "Pending scaffold only; not actual signoff.",
        },
        "still_blocked_gate_ids": list(STILL_BLOCKED_GATE_IDS),
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
            "required_reviewer_statement_ids": list(STATEMENT_IDS),
            "required_record_fields": _required_record_fields(),
        },
        "still_blocked_gate_ids": list(STILL_BLOCKED_GATE_IDS),
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


def _signoff_record_validator_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1",
            "default_off": True,
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
            "expected_template_payload": _pending_payload(),
            "required_reviewer_statement_ids": list(STATEMENT_IDS),
            "validator_rules": {
                "required_fields": [
                    {
                        "field": "record_type",
                        "required": True,
                        "template_value": "reviewed_runtime_patch_signoff_record_v0",
                        "detail": "Carry forward the fixed record type.",
                        "validation_rule": "must_equal_template_value",
                        "validator_detail": "Future payload must carry forward this exact template value.",
                    },
                    {
                        "field": "reviewer_id",
                        "required": True,
                        "template_value": "",
                        "detail": "Populate reviewer id later.",
                        "validation_rule": "must_be_present_and_non_empty",
                        "validator_detail": "Future payload must provide a non-empty reviewer id.",
                    },
                ],
                "agreed_statement_ids": {
                    "field": "agreed_statement_ids",
                    "required": True,
                    "required_ids": list(STATEMENT_IDS),
                    "validation_rule": "must_include_all_required_ids_and_no_unapproved_ids",
                    "detail": "Carry forward required reviewer statement ids.",
                },
                "still_blocked_gate_ids": {
                    "field": "still_blocked_gate_ids",
                    "required": True,
                    "required_ids": list(STILL_BLOCKED_GATE_IDS),
                    "validation_rule": "must_match_scaffold_blocked_gate_ids_until_upstream_contract_changes",
                    "detail": "Carry forward still-blocked gate ids.",
                },
            },
            "actual_record_validation": {
                "record_payload_provided": False,
                "record_payload_validated": False,
                "validation_status": "not_run",
                "detail": "No actual payload was supplied.",
            },
            "validator_notice": "Validator contract only.",
        },
        "still_blocked_gate_ids": list(STILL_BLOCKED_GATE_IDS),
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


def test_anchor119_row_domain_reviewer_record_collection_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_record_validator_path=signoff_record_validator_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["reviewer_record_collection_ready"] is True
    assert report["status"]["actual_reviewer_record_collected"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    collection = report["reviewer_record_collection"]
    target_identity = collection["target_record_identity"]
    assert target_identity["record_identity"] == (
        "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
    )
    expected_handoff = collection["expected_handoff"]
    assert expected_handoff["handoff_dir"] == (
        ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff"
    )
    assert (
        "anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119"
        in expected_handoff["handoff_path_shape"]
    )
    preserved_contract = collection["preserved_contract"]
    assert preserved_contract["required_reviewer_statement_ids"] == STATEMENT_IDS
    assert preserved_contract["still_blocked_gate_ids"] == STILL_BLOCKED_GATE_IDS
    assert collection["collection_state"]["actual_record_collected"] is False
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_text(
            report
        )
    )
    assert "Reviewer Record Collection" in markdown
    assert "No actual reviewer-signed runtime patch signoff record has been collected" in markdown
    assert "reviewer_record_collection_ready=True" in text


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        ("scaffold", "signoff_record_scaffold_present"),
        ("reviewer", "reviewer_record_prep_present"),
        ("validator", "signoff_record_validator_present"),
    ],
)
def test_anchor119_row_domain_reviewer_record_collection_fails_if_upstream_artifact_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    if missing_name != "scaffold":
        _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    if missing_name != "reviewer":
        _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    if missing_name != "validator":
        _write_json(signoff_record_validator_path, _signoff_record_validator_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection(
        project_root,
        signoff_record_scaffold_path=signoff_record_scaffold_path,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_record_validator_path=signoff_record_validator_path,
    )

    assert report["status"]["reviewer_record_collection_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_reviewer_record_collection_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_scaffold_path = tmp_path / "scaffold.json"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    output_dir = tmp_path / "out"
    _write_json(signoff_record_scaffold_path, _signoff_record_scaffold_json())
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection.py"
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
            "--signoff-record-validator",
            str(signoff_record_validator_path),
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

    assert "phase3b anchor119 row-domain reviewer record collection" in no_write.stdout
    assert "actual_reviewer_record_collected=False" in no_write.stdout
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
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_reviewer_record_collection_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_reviewer_record_collection.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["reviewer_record_collection_ready"] is True
    assert payload["status"]["actual_reviewer_record_collected"] is False
    assert (output_dir / "anchor119_row_domain_reviewer_record_collection.md").exists()
    assert (output_dir / "anchor119_row_domain_reviewer_record_collection.txt").exists()

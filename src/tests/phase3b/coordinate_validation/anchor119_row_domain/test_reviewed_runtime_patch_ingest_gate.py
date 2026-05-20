from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b.coordinate_validation.anchor119_row_domain.reviewed_runtime_patch_ingest_gate import (
    build_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate,
    render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_text,
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


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
            "expected_template_payload": {
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "reviewer_id": "",
                "reviewed_at": "",
                "verdict": "pending",
                "scope": "candidate=67x13, anchor_idx=119",
                "notes": "",
                "agreed_statement_ids": list(STATEMENT_IDS),
                "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
            },
            "required_reviewer_statement_ids": list(STATEMENT_IDS),
            "validator_rules": {
                "required_fields": [
                    {
                        "field": "record_type",
                        "required": True,
                        "template_value": "reviewed_runtime_patch_signoff_record_v0",
                    },
                    {
                        "field": "reviewer_id",
                        "required": True,
                        "template_value": "",
                    },
                    {
                        "field": "reviewed_at",
                        "required": True,
                        "template_value": "",
                    },
                    {
                        "field": "verdict",
                        "required": True,
                        "template_value": "pending",
                    },
                    {
                        "field": "scope",
                        "required": True,
                        "template_value": "candidate=67x13, anchor_idx=119",
                    },
                    {
                        "field": "notes",
                        "required": True,
                        "template_value": "",
                    },
                    {
                        "field": "agreed_statement_ids",
                        "required": True,
                        "template_value": list(STATEMENT_IDS),
                    },
                    {
                        "field": "still_blocked_gate_ids",
                        "required": True,
                        "template_value": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                    },
                ],
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
    }


def _reviewer_record_collection_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1",
            "default_off": True,
            "review_only": True,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "reviewer_record_collection_ready": True,
            "actual_reviewer_record_collected": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "reviewer_record_collection": {
            "target_record_identity": {
                "record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
                "candidate_key": "67x13",
                "anchor_idx": 119,
            },
            "expected_collection_source": {
                "collection_mode": "manual_reviewer_side_collection_only",
                "collection_phase": "review_only",
                "source_artifact_chain": [
                    "signoff_record_scaffold.pending_signoff_record_payload",
                    "reviewer_record_prep.required_record_fields",
                    "signoff_record_validator.validator_rules",
                ],
                "base_payload_template": {
                    "record_type": "reviewed_runtime_patch_signoff_record_v0",
                    "reviewer_id": "",
                    "reviewed_at": "",
                    "verdict": "pending",
                    "scope": "candidate=67x13, anchor_idx=119",
                    "notes": "",
                    "agreed_statement_ids": list(STATEMENT_IDS),
                    "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                },
            },
            "expected_handoff": {
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
            "preserved_contract": {
                "required_record_fields": [
                    {"field": "record_type", "required": True},
                    {"field": "reviewer_id", "required": True},
                    {"field": "reviewed_at", "required": True},
                    {"field": "verdict", "required": True},
                    {"field": "scope", "required": True},
                    {"field": "notes", "required": True},
                    {"field": "agreed_statement_ids", "required": True},
                    {"field": "still_blocked_gate_ids", "required": True},
                ],
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
            },
            "collection_state": {
                "actual_record_collected": False,
                "reviewer_signed_record_present": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
    }


def _runtime_patch_status_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1",
            "default_off": True,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "patch_status_ready": True,
            "authored_but_not_enableable": True,
            "runtime_enablement_allowed": False,
        },
        "code_status": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
        },
    }


def _runtime_patch_signoff_bundle_json() -> dict:
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
            "reviewed_runtime_patch_signoff_ready_for_review": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_bundle": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "scope": "candidate=67x13, anchor_idx=119",
            "required_reviewer_statements": [
                {"statement_id": statement_id, "must_agree": True}
                for statement_id in STATEMENT_IDS
            ],
            "signoff_record_template": {
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "reviewer_id": "",
                "reviewed_at": "",
                "verdict": "pending",
                "scope": "candidate=67x13, anchor_idx=119",
                "notes": "",
                "agreed_statement_ids": [],
                "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
            },
        },
    }


def test_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    reviewer_record_collection_path = tmp_path / "reviewer_record_collection.json"
    runtime_patch_status_path = tmp_path / "runtime_patch_status.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    _write_json(runtime_patch_status_path, _runtime_patch_status_json())
    _write_json(
        runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json()
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate(
            project_root,
            signoff_record_validator_path=signoff_record_validator_path,
            reviewer_record_collection_path=reviewer_record_collection_path,
            runtime_patch_status_path=runtime_patch_status_path,
            runtime_patch_signoff_bundle_path=runtime_patch_signoff_bundle_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["reviewed_runtime_patch_ingest_gate_ready"] is True
    assert report["status"]["future_review_state_marking_prerequisites_met"] is False
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["recommended_next_step"] == (
        "manually_validate_reviewer_record_then_run_separate_ingest_review_without_enablement"
    )
    ingest_gate = report["reviewed_runtime_patch_ingest_gate"]
    review_target = ingest_gate["repo_side_review_state_target"]
    assert review_target["record_identity"] == (
        "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
    )
    handoff = ingest_gate["locked_reviewer_record_handoff"]
    assert (
        "anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119"
        in handoff["handoff_path_shape"]
    )
    contract = ingest_gate["ingest_review_contract"]
    assert contract["required_reviewer_statement_ids"] == STATEMENT_IDS
    assert contract["current_still_blocked_gate_ids"] == CURRENT_STILL_BLOCKED_GATE_IDS
    assert contract["post_ingest_still_blocked_gate_ids"] == (
        POST_INGEST_STILL_BLOCKED_GATE_IDS
    )
    actual_state = ingest_gate["actual_record_state"]
    assert actual_state["reviewer_signed_record_provided"] is False
    assert actual_state["repo_side_review_state_updated"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert not failed
    missing_prereqs = set(report["status"]["missing_prerequisite_gate_ids"])
    assert "reviewer_signed_record_supplied_for_review" in missing_prereqs
    assert "reviewer_signed_record_validates_against_locked_contract" in missing_prereqs
    assert "separate_manual_ingest_review_approved" in missing_prereqs
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_text(
            report
        )
    )
    assert "Reviewed Runtime Patch Ingest Gate" in markdown
    assert "No actual reviewer-signed runtime patch signoff record has been provided" in markdown
    assert "future_review_state_marking_prerequisites_met=False" in text


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        ("signoff_record_validator", "signoff_record_validator_present"),
        ("reviewer_record_collection", "reviewer_record_collection_present"),
        ("runtime_patch_status", "runtime_patch_status_present"),
        ("runtime_patch_signoff_bundle", "runtime_patch_signoff_bundle_present"),
    ],
)
def test_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_fails_if_upstream_artifact_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    reviewer_record_collection_path = tmp_path / "reviewer_record_collection.json"
    runtime_patch_status_path = tmp_path / "runtime_patch_status.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"

    if missing_name != "signoff_record_validator":
        _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    if missing_name != "reviewer_record_collection":
        _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    if missing_name != "runtime_patch_status":
        _write_json(runtime_patch_status_path, _runtime_patch_status_json())
    if missing_name != "runtime_patch_signoff_bundle":
        _write_json(
            runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json()
        )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate(
            project_root,
            signoff_record_validator_path=signoff_record_validator_path,
            reviewer_record_collection_path=reviewer_record_collection_path,
            runtime_patch_status_path=runtime_patch_status_path,
            runtime_patch_signoff_bundle_path=runtime_patch_signoff_bundle_path,
        )
    )

    assert report["status"]["reviewed_runtime_patch_ingest_gate_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    reviewer_record_collection_path = tmp_path / "reviewer_record_collection.json"
    runtime_patch_status_path = tmp_path / "runtime_patch_status.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    output_dir = tmp_path / "out"
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    _write_json(runtime_patch_status_path, _runtime_patch_status_json())
    _write_json(
        runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json()
    )
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_reviewed_runtime_patch_ingest_gate.py"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--reviewer-record-collection",
            str(reviewer_record_collection_path),
            "--runtime-patch-status",
            str(runtime_patch_status_path),
            "--runtime-patch-signoff-bundle",
            str(runtime_patch_signoff_bundle_path),
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

    assert "phase3b anchor119 row-domain reviewed runtime patch ingest gate" in no_write.stdout
    assert "reviewed_runtime_patch_ingest_gate_ready=True" in no_write.stdout
    assert "future_review_state_marking_prerequisites_met=False" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--reviewer-record-collection",
            str(reviewer_record_collection_path),
            "--runtime-patch-status",
            str(runtime_patch_status_path),
            "--runtime-patch-signoff-bundle",
            str(runtime_patch_signoff_bundle_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_reviewed_runtime_patch_ingest_gate_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "anchor119_row_domain_reviewed_runtime_patch_ingest_gate.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["reviewed_runtime_patch_ingest_gate_ready"] is True
    assert payload["status"]["future_review_state_marking_prerequisites_met"] is False
    assert (
        output_dir / "anchor119_row_domain_reviewed_runtime_patch_ingest_gate.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_reviewed_runtime_patch_ingest_gate.txt"
    ).exists()

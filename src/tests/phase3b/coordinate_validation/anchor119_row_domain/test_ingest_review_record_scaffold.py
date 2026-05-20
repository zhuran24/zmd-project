from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b.coordinate_validation.anchor119_row_domain.ingest_review_record_scaffold import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_text,
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
            "missing_prerequisite_gate_ids": [
                "reviewer_signed_record_supplied_for_review",
                "reviewer_signed_record_validates_against_locked_contract",
                "separate_manual_ingest_review_approved",
            ],
        },
        "reviewed_runtime_patch_ingest_gate": {
            "repo_side_review_state_target": {
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
                "current_field_value": False,
                "future_manual_ingest_review_may_mark_true": True,
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
            "expected_review_input": {
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
            "ingest_review_contract": {
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
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
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
                "runtime_enablement_allowed_after_ingest_review": False,
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


def _reviewer_record_collection_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1",
            "default_off": True,
            "review_only": True,
            "spec_only": True,
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
            },
            "expected_collection_source": {
                "collection_mode": "manual_reviewer_side_collection_only",
                "collection_phase": "review_only",
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
                    {
                        "field": "record_type",
                        "required": True,
                        "template_value": "reviewed_runtime_patch_signoff_record_v0",
                    },
                    {"field": "reviewer_id", "required": True, "template_value": ""},
                    {"field": "reviewed_at", "required": True, "template_value": ""},
                    {"field": "verdict", "required": True, "template_value": "pending"},
                    {
                        "field": "scope",
                        "required": True,
                        "template_value": "candidate=67x13, anchor_idx=119",
                    },
                    {"field": "notes", "required": True, "template_value": ""},
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
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
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
                    {"field": "reviewer_id", "required": True, "template_value": ""},
                    {"field": "reviewed_at", "required": True, "template_value": ""},
                    {"field": "verdict", "required": True, "template_value": "pending"},
                    {
                        "field": "scope",
                        "required": True,
                        "template_value": "candidate=67x13, anchor_idx=119",
                    },
                    {"field": "notes", "required": True, "template_value": ""},
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


def test_anchor119_row_domain_ingest_review_record_scaffold_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    reviewer_record_collection_path = tmp_path / "reviewer_record_collection.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    _write_json(
        reviewed_runtime_patch_ingest_gate_path,
        _reviewed_runtime_patch_ingest_gate_json(),
    )
    _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold(
            project_root,
            reviewed_runtime_patch_ingest_gate_path=reviewed_runtime_patch_ingest_gate_path,
            reviewer_record_collection_path=reviewer_record_collection_path,
            signoff_record_validator_path=signoff_record_validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["ingest_review_record_scaffold_ready"] is True
    assert report["status"]["manual_ingest_review_record_completed"] is False
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["recommended_next_step"] == (
        "manually_complete_ingest_review_record_then_run_separate_repo_side_review_decision_without_enablement"
    )
    assert report["still_blocked_gate_ids"] == CURRENT_STILL_BLOCKED_GATE_IDS
    scaffold = report["ingest_review_record_scaffold"]
    target = scaffold["locked_target_review_state"]
    assert target["record_identity"] == (
        "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
    )
    template = scaffold["ingest_review_record_template"]
    assert template["record_type"] == "reviewed_runtime_patch_ingest_review_record_v0"
    assert template["tracked_field"] == "reviewed_runtime_patch_exists"
    assert template["review_decision"] == "pending"
    assert template["reviewer_record_validation_status"] == "pending_manual_validation"
    assert template["current_still_blocked_gate_ids"] == CURRENT_STILL_BLOCKED_GATE_IDS
    assert template["post_ingest_still_blocked_gate_ids"] == (
        POST_INGEST_STILL_BLOCKED_GATE_IDS
    )
    conclusion_ids = [
        entry["conclusion_id"] for entry in scaffold["required_review_conclusions"]
    ]
    assert "reviewer_signed_record_supplied_for_review" in conclusion_ids
    assert "reviewer_signed_record_validates_against_locked_contract" in conclusion_ids
    assert "separate_manual_ingest_review_approved" in conclusion_ids
    assert "repo_side_review_state_may_mark_reviewed_runtime_patch" in conclusion_ids
    assert "runtime_enablement_remains_blocked_after_review" in conclusion_ids
    assert "post_ingest_still_blocked_gate_ids_preserved" in conclusion_ids
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_text(
            report
        )
    )
    assert "Ingest Review Record Scaffold" in markdown
    assert "Future human ingest-review record scaffold only" in markdown
    assert "ingest_review_record_scaffold_ready=True" in text


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        (
            "reviewed_runtime_patch_ingest_gate",
            "reviewed_runtime_patch_ingest_gate_present",
        ),
        ("reviewer_record_collection", "reviewer_record_collection_present"),
        ("signoff_record_validator", "signoff_record_validator_present"),
    ],
)
def test_anchor119_row_domain_ingest_review_record_scaffold_fails_if_upstream_artifact_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    reviewer_record_collection_path = tmp_path / "reviewer_record_collection.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"

    if missing_name != "reviewed_runtime_patch_ingest_gate":
        _write_json(
            reviewed_runtime_patch_ingest_gate_path,
            _reviewed_runtime_patch_ingest_gate_json(),
        )
    if missing_name != "reviewer_record_collection":
        _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    if missing_name != "signoff_record_validator":
        _write_json(signoff_record_validator_path, _signoff_record_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold(
            project_root,
            reviewed_runtime_patch_ingest_gate_path=reviewed_runtime_patch_ingest_gate_path,
            reviewer_record_collection_path=reviewer_record_collection_path,
            signoff_record_validator_path=signoff_record_validator_path,
        )
    )

    assert report["status"]["ingest_review_record_scaffold_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_ingest_review_record_scaffold_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    reviewed_runtime_patch_ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    reviewer_record_collection_path = tmp_path / "reviewer_record_collection.json"
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    output_dir = tmp_path / "out"
    _write_json(
        reviewed_runtime_patch_ingest_gate_path,
        _reviewed_runtime_patch_ingest_gate_json(),
    )
    _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_ingest_review_record_scaffold.py"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--reviewed-runtime-patch-ingest-gate",
            str(reviewed_runtime_patch_ingest_gate_path),
            "--reviewer-record-collection",
            str(reviewer_record_collection_path),
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

    assert "phase3b anchor119 row-domain ingest review record scaffold" in no_write.stdout
    assert "ingest_review_record_scaffold_ready=True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--reviewed-runtime-patch-ingest-gate",
            str(reviewed_runtime_patch_ingest_gate_path),
            "--reviewer-record-collection",
            str(reviewer_record_collection_path),
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

    assert "anchor119_row_domain_ingest_review_record_scaffold_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "anchor119_row_domain_ingest_review_record_scaffold.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["ingest_review_record_scaffold_ready"] is True
    assert payload["status"]["repo_side_review_state_updated"] is False
    assert (
        output_dir / "anchor119_row_domain_ingest_review_record_scaffold.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_ingest_review_record_scaffold.txt"
    ).exists()

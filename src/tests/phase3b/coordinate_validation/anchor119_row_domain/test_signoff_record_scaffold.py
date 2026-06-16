from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b.coordinate_validation.anchor119_row_domain.signoff_record_scaffold import (
    build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold,
    render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def test_anchor119_row_domain_signoff_record_scaffold_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold(
        project_root,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_v1"
    )
    assert report["status"]["signoff_record_scaffold_ready"] is True
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["still_blocked_gate_ids"] == [
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
    ]
    scaffold = report["signoff_record_scaffold"]
    payload = scaffold["pending_signoff_record_payload"]
    assert payload["record_type"] == "reviewed_runtime_patch_signoff_record_v0"
    assert payload["verdict"] == "pending"
    assert payload["agreed_statement_ids"] == [
        "default_off_retained",
        "acceptance_refresh_required_before_enablement",
    ]
    assert payload["still_blocked_gate_ids"] == [
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
    ]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold_text(
            report
        )
    )
    assert "Signoff Record Scaffold" in markdown
    assert "not an actual reviewed signoff" in markdown
    assert "signoff_record_scaffold_ready=True" in text


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        ("reviewer", "reviewer_record_prep_present"),
        ("signoff", "signoff_bundle_present"),
    ],
)
def test_anchor119_row_domain_signoff_record_scaffold_fails_if_upstream_artifact_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    if missing_name != "reviewer":
        _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    if missing_name != "signoff":
        _write_json(signoff_bundle_path, _signoff_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_signoff_record_scaffold(
        project_root,
        reviewer_record_prep_path=reviewer_record_prep_path,
        signoff_bundle_path=signoff_bundle_path,
    )

    assert report["status"]["signoff_record_scaffold_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_signoff_record_scaffold_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    reviewer_record_prep_path = tmp_path / "reviewer_record_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    output_dir = tmp_path / "out"
    _write_json(reviewer_record_prep_path, _reviewer_record_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_signoff_record_scaffold.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--reviewer-record-prep",
            str(reviewer_record_prep_path),
            "--signoff-bundle",
            str(signoff_bundle_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain signoff record scaffold" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--reviewer-record-prep",
            str(reviewer_record_prep_path),
            "--signoff-bundle",
            str(signoff_bundle_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_signoff_record_scaffold_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_signoff_record_scaffold.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["signoff_record_scaffold_ready"] is True
    assert (output_dir / "anchor119_row_domain_signoff_record_scaffold.md").exists()
    assert (output_dir / "anchor119_row_domain_signoff_record_scaffold.txt").exists()

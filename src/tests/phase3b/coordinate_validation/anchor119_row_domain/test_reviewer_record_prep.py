from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b.coordinate_validation.anchor119_row_domain.reviewer_record_prep import (
    build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep,
    render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
                    "detail": "Acceptance refresh is still required.",
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
                "detail": "Acceptance refresh has not been executed yet.",
            },
        ],
    }


def _acceptance_refresh_prep_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1",
            "default_off": True,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "acceptance_refresh_prep_ready": True,
            "runtime_enablement_allowed": False,
        },
        "acceptance_refresh_prep": {
            "required_sequence": [
                "reviewed_runtime_patch_signoff_record",
                "run_prod_4x4_acceptance_refresh",
                "validate_prod_4x4_record_fields",
                "post_acceptance_enablement_review",
            ]
        },
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Acceptance refresh still waits for the reviewed runtime patch record.",
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "satisfied": False,
                "blocking": True,
                "detail": "Acceptance refresh still has not been run.",
            },
        ],
    }


def test_anchor119_row_domain_reviewer_record_prep_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    signoff_bundle_path = tmp_path / "signoff.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance.json"
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep(
        project_root,
        signoff_bundle_path=signoff_bundle_path,
        acceptance_refresh_prep_path=acceptance_refresh_prep_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_v1"
    )
    assert report["status"]["reviewer_record_prep_ready"] is True
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["still_blocked_gate_ids"] == [
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
    ]
    prep = report["reviewer_record_prep"]
    assert prep["record_type"] == "reviewed_runtime_patch_signoff_record_v0"
    fields = {entry["field"]: entry for entry in prep["required_record_fields"]}
    assert fields["reviewer_id"]["required"] is True
    assert fields["still_blocked_gate_ids"]["template_value"] == [
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
    ]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_markdown(
            report
        )
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep_text(
        report
    )
    assert "Reviewer Record Prep" in markdown
    assert "default-off" in markdown
    assert "reviewer_record_prep_ready=True" in text


@pytest.mark.parametrize(
    ("missing_name", "failed_check"),
    [
        ("signoff", "signoff_bundle_present"),
        ("acceptance", "acceptance_refresh_prep_present"),
    ],
)
def test_anchor119_row_domain_reviewer_record_prep_fails_if_required_input_missing(
    tmp_path: Path,
    missing_name: str,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    signoff_bundle_path = tmp_path / "signoff.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance.json"
    if missing_name != "signoff":
        _write_json(signoff_bundle_path, _signoff_bundle_json())
    if missing_name != "acceptance":
        _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_prep(
        project_root,
        signoff_bundle_path=signoff_bundle_path,
        acceptance_refresh_prep_path=acceptance_refresh_prep_path,
    )

    assert report["status"]["reviewer_record_prep_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert failed_check in failed


def test_anchor119_row_domain_reviewer_record_prep_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    signoff_bundle_path = tmp_path / "signoff.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance.json"
    output_dir = tmp_path / "out"
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_reviewer_record_prep.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--signoff-bundle",
            str(signoff_bundle_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain reviewer record prep" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--signoff-bundle",
            str(signoff_bundle_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_reviewer_record_prep_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_reviewer_record_prep.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["reviewer_record_prep_ready"] is True
    assert (output_dir / "anchor119_row_domain_reviewer_record_prep.md").exists()
    assert (output_dir / "anchor119_row_domain_reviewer_record_prep.txt").exists()

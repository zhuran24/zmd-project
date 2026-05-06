from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _pre_run_acceptance_validation_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "acceptance_validation_ready_for_review": True,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "pre_run_acceptance_validation": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "production_acceptance_command": (
                "python temp_scripts/benchmark_parallelism.py --suite-kind "
                "production-acceptance --suite-output "
                ".codex_test_logs/phase3b/production_acceptance_after_change.json"
            ),
            "exact_future_acceptance_json_path": ".codex_test_logs/phase3b/production_acceptance_after_change.json",
            "prod_4x4_record_match_rules": [
                {
                    "selector": "label",
                    "field": "label",
                    "expected": "prod_4x4",
                    "reason": "primary long-run preflight selector",
                }
            ],
            "required_prod_4x4_validity_fields": [
                {
                    "field": "completed",
                    "expected": True,
                    "reason": "completed must be true",
                },
                {
                    "field": "return_code",
                    "expected": 0,
                    "reason": "return_code must be zero",
                },
                {
                    "field": "campaign_valid_after_run",
                    "expected": True,
                    "reason": "campaign validity must hold",
                },
                {
                    "field": "duplicated_work",
                    "expected": False,
                    "reason": "duplicated_work must stay false",
                },
            ],
        },
    }


def _acceptance_refresh_prep_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "acceptance_refresh_prep_ready": True,
            "acceptance_refresh_ready_for_review": True,
            "runtime_enablement_allowed": False,
        },
        "acceptance_refresh_prep": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "acceptance_command": (
                "python temp_scripts/benchmark_parallelism.py --suite-kind "
                "production-acceptance --suite-output "
                ".codex_test_logs/phase3b/production_acceptance_after_change.json"
            ),
            "suite_output_path": ".codex_test_logs/phase3b/production_acceptance_after_change.json",
            "validity_criteria": {
                "label": "prod_4x4",
                "completed": True,
                "return_code": 0,
                "campaign_valid_after_run": True,
                "duplicated_work": False,
            },
        },
    }


def test_anchor119_row_domain_acceptance_execution_staging_ready(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pre_run_path = tmp_path / "pre_run_acceptance_validation.json"
    acceptance_refresh_path = tmp_path / "acceptance_refresh_prep.json"
    _write_json(pre_run_path, _pre_run_acceptance_validation_json())
    _write_json(acceptance_refresh_path, _acceptance_refresh_prep_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging(
            repo_root,
            pre_run_acceptance_validation_path=pre_run_path,
            acceptance_refresh_prep_path=acceptance_refresh_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
    )
    assert report["status"]["acceptance_execution_staging_ready"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    staging = report["acceptance_execution_staging"]
    assert staging["does_not_execute_acceptance"] is True
    assert staging["does_not_imply_enablement"] is True
    assert (
        staging["exact_command_to_run_later"]
        == "python temp_scripts/benchmark_parallelism.py --suite-kind "
        "production-acceptance --suite-output "
        ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )
    assert (
        staging["exact_future_output_path"]
        == ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )
    expected_fields = {
        entry["field"]: entry["expected"]
        for entry in staging["expected_prod_4x4_validity_fields"]
    }
    assert expected_fields == {
        "completed": True,
        "return_code": 0,
        "campaign_valid_after_run": True,
        "duplicated_work": False,
    }
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_text(
            report
        )
    )
    assert "Acceptance Execution Staging" in markdown
    assert "acceptance_execution_staging_ready=True" in text


def test_anchor119_row_domain_acceptance_execution_staging_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    acceptance_refresh_path = tmp_path / "acceptance_refresh_prep.json"
    _write_json(acceptance_refresh_path, _acceptance_refresh_prep_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging(
            repo_root,
            pre_run_acceptance_validation_path=tmp_path / "missing_pre_run.json",
            acceptance_refresh_prep_path=acceptance_refresh_path,
        )
    )

    assert report["status"]["acceptance_execution_staging_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "pre_run_acceptance_validation_present" in failed


def test_anchor119_row_domain_acceptance_execution_staging_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pre_run_path = tmp_path / "pre_run_acceptance_validation.json"
    acceptance_refresh_path = tmp_path / "acceptance_refresh_prep.json"
    output_dir = tmp_path / "out"
    _write_json(pre_run_path, _pre_run_acceptance_validation_json())
    _write_json(acceptance_refresh_path, _acceptance_refresh_prep_json())
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--pre-run-acceptance-validation",
            str(pre_run_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain acceptance execution staging" in no_write.stdout
    assert "exact_command_to_run_later=" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--pre-run-acceptance-validation",
            str(pre_run_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_acceptance_execution_staging_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "anchor119_row_domain_acceptance_execution_staging.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["acceptance_execution_staging_ready"] is True
    assert (
        output_dir / "anchor119_row_domain_acceptance_execution_staging.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_acceptance_execution_staging.txt"
    ).exists()

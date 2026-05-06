from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation import (
    build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation,
    render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_text,
)
from src.search.phase3b_long_run_preflight import _prod_4x4_record_valid


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def _signoff_bundle_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1",
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
            "production_acceptance_command": (
                "python temp_scripts/benchmark_parallelism.py --suite-kind "
                "production-acceptance --suite-output "
                ".codex_test_logs/phase3b/production_acceptance_after_change.json"
            ),
            "signoff_record_template": {
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
            },
        },
    }


def test_anchor119_row_domain_pre_run_acceptance_validation_ready(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation(
            repo_root,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            signoff_bundle_path=signoff_bundle_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1"
    )
    assert report["status"]["acceptance_validation_ready_for_review"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    prep = report["pre_run_acceptance_validation"]
    assert (
        prep["exact_future_acceptance_json_path"]
        == ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )
    validity_record = {
        entry["field"]: entry["expected"]
        for entry in prep["required_prod_4x4_validity_fields"]
    }
    assert _prod_4x4_record_valid(validity_record) is True
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_text(
            report
        )
    )
    assert "Pre-Run Acceptance Validation" in markdown
    assert "acceptance_validation_ready_for_review=True" in text


def test_anchor119_row_domain_pre_run_acceptance_validation_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    _write_json(signoff_bundle_path, _signoff_bundle_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation(
            repo_root,
            acceptance_refresh_prep_path=tmp_path / "missing_acceptance_refresh_prep.json",
            signoff_bundle_path=signoff_bundle_path,
        )
    )

    assert report["status"]["acceptance_validation_ready_for_review"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "acceptance_refresh_prep_present" in failed


def test_anchor119_row_domain_pre_run_acceptance_validation_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    signoff_bundle_path = tmp_path / "signoff_bundle.json"
    output_dir = tmp_path / "out"
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
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

    assert "phase3b anchor119 row-domain pre-run acceptance validation" in no_write.stdout
    assert "exact_future_acceptance_json_path=" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
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

    assert "anchor119_row_domain_pre_run_acceptance_validation_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "anchor119_row_domain_pre_run_acceptance_validation.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["acceptance_validation_ready_for_review"] is True
    assert (
        output_dir / "anchor119_row_domain_pre_run_acceptance_validation.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_pre_run_acceptance_validation.txt"
    ).exists()

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _metadata(source: str, *, acceptance_executed: bool = False) -> dict:
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
        "acceptance_executed": acceptance_executed,
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


def _acceptance_execution_gate_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
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
            "review_only": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "default_production_runner": "scripts/run_prod_4x4_normal.ps1",
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
            },
        },
    }


def _acceptance_refresh_prep_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_refresh_ready_for_review": True,
            "runtime_enablement_allowed": False,
        },
        "acceptance_refresh_prep": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "default_production_runner": "scripts/run_prod_4x4_normal.ps1",
            "acceptance_command": _locked_acceptance_command(),
            "suite_output_path": _locked_acceptance_result_path(),
        },
    }


def _acceptance_execution_staging_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_execution_staging_ready": True,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "acceptance_execution_staging": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "exact_command_to_run_later": _locked_acceptance_command(),
            "exact_future_output_path": _locked_acceptance_result_path(),
        },
    }


def _acceptance_result_validator_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
        ),
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
        },
    }


def _runtime_patch_signoff_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "signoff_bundle_ready": True,
            "reviewed_runtime_patch_signoff_ready_for_review": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_bundle": {
            "scope": "anchor119_row_domain_runtime_guard_patch",
            "production_acceptance_command": _locked_acceptance_command(),
            "required_reviewer_statements": [
                {"statement_id": "default_off_retained"},
                {"statement_id": "acceptance_refresh_required_before_enablement"},
            ],
        },
    }


def test_anchor119_row_domain_acceptance_authorization_review_bundle_ready(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    acceptance_execution_gate_path = tmp_path / "acceptance_execution_gate.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    acceptance_result_validator_path = tmp_path / "acceptance_result_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"

    _write_json(acceptance_execution_gate_path, _acceptance_execution_gate_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        acceptance_execution_staging_path, _acceptance_execution_staging_json()
    )
    _write_json(
        acceptance_result_validator_path, _acceptance_result_validator_json()
    )
    _write_json(
        runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json()
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle(
            repo_root,
            acceptance_execution_gate_path=acceptance_execution_gate_path,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            acceptance_result_validator_path=acceptance_result_validator_path,
            runtime_patch_signoff_bundle_path=runtime_patch_signoff_bundle_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_v1"
    )
    assert report["status"]["acceptance_authorization_review_bundle_ready"] is True
    assert (
        report["status"]["future_execution_authorization_review_prerequisites_met"]
        is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["missing_prerequisite_gate_ids"] == [
        "reviewed_runtime_patch_exists"
    ]
    bundle = report["acceptance_authorization_review_bundle"]
    assert bundle["does_not_authorize_execution"] is True
    assert bundle["locked_execution_target"]["production_profile_id"] == "prod_4x4_normal"
    assert (
        bundle["locked_execution_target"]["exact_future_acceptance_command"]
        == _locked_acceptance_command()
    )
    assert (
        bundle["locked_execution_target"]["exact_future_acceptance_result_path"]
        == _locked_acceptance_result_path()
    )
    conclusions = bundle[
        "required_review_conclusions_before_future_execution_authorization_review"
    ]
    assert [entry["conclusion_id"] for entry in conclusions] == [
        "locked_prod_4x4_normal_target_confirmed",
        "runtime_patch_signoff_bundle_review_ready",
        "reviewed_runtime_patch_exists",
        "acceptance_refresh_and_staging_contracts_ready",
        "acceptance_result_validator_ready",
        "runtime_enablement_remains_forbidden",
    ]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_text(
            report
        )
    )
    assert "Acceptance Authorization Review Bundle" in markdown
    assert "acceptance_execution_authorized=False" in text


def test_anchor119_row_domain_acceptance_authorization_review_bundle_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    acceptance_execution_gate_path = tmp_path / "acceptance_execution_gate.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"

    _write_json(acceptance_execution_gate_path, _acceptance_execution_gate_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        acceptance_execution_staging_path, _acceptance_execution_staging_json()
    )
    _write_json(
        runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json()
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle(
            repo_root,
            acceptance_execution_gate_path=acceptance_execution_gate_path,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            acceptance_result_validator_path=tmp_path
            / "missing_acceptance_result_validator.json",
            runtime_patch_signoff_bundle_path=runtime_patch_signoff_bundle_path,
        )
    )

    assert report["status"]["acceptance_authorization_review_bundle_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "acceptance_result_validator_present" in failed
    assert "acceptance_result_validator_ready" in report["status"][
        "missing_prerequisite_gate_ids"
    ]


def test_anchor119_row_domain_acceptance_authorization_review_bundle_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    acceptance_execution_gate_path = tmp_path / "acceptance_execution_gate.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    acceptance_result_validator_path = tmp_path / "acceptance_result_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    output_dir = tmp_path / "out"

    _write_json(acceptance_execution_gate_path, _acceptance_execution_gate_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        acceptance_execution_staging_path, _acceptance_execution_staging_json()
    )
    _write_json(
        acceptance_result_validator_path, _acceptance_result_validator_json()
    )
    _write_json(
        runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json()
    )
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_acceptance_authorization_review_bundle.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-execution-gate",
            str(acceptance_execution_gate_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
            "--acceptance-execution-staging",
            str(acceptance_execution_staging_path),
            "--acceptance-result-validator",
            str(acceptance_result_validator_path),
            "--runtime-patch-signoff-bundle",
            str(runtime_patch_signoff_bundle_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (
        "phase3b anchor119 row-domain acceptance authorization review bundle"
        in no_write.stdout
    )
    assert "acceptance_execution_authorized=False" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-execution-gate",
            str(acceptance_execution_gate_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
            "--acceptance-execution-staging",
            str(acceptance_execution_staging_path),
            "--acceptance-result-validator",
            str(acceptance_result_validator_path),
            "--runtime-patch-signoff-bundle",
            str(runtime_patch_signoff_bundle_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (
        "anchor119_row_domain_acceptance_authorization_review_bundle_json="
        in write.stdout
    )
    payload = json.loads(
        (
            output_dir
            / "anchor119_row_domain_acceptance_authorization_review_bundle.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["acceptance_authorization_review_bundle_ready"] is True
    assert payload["status"]["acceptance_execution_authorized"] is False
    assert (
        output_dir / "anchor119_row_domain_acceptance_authorization_review_bundle.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_acceptance_authorization_review_bundle.txt"
    ).exists()

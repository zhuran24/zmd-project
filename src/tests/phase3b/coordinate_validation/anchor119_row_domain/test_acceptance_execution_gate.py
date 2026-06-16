from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_execution_gate import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _metadata(source: str, *, acceptance_executed: bool = False) -> dict:
    return {
        "source": source,
        "spec_only": True,
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


def _signoff_record_validator_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "signoff_record_validator_ready": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_record_validator": {
            "required_reviewer_statement_ids": [
                "default_off_retained",
                "reserved_runtime_request_downgrades_to_advisory",
                "no_proof_source_promotion",
                "acceptance_refresh_required_before_enablement",
            ],
            "actual_record_validation": {
                "validation_status": "not_run",
            },
        },
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
        ],
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
            "production_acceptance_command": _locked_acceptance_command(),
            "required_reviewer_statements": [
                {"statement_id": "default_off_retained"},
                {"statement_id": "reserved_runtime_request_downgrades_to_advisory"},
                {"statement_id": "no_proof_source_promotion"},
                {"statement_id": "acceptance_refresh_required_before_enablement"},
            ],
            "signoff_record_template": {
                "still_blocked_gate_ids": [
                    "reviewed_runtime_patch_exists",
                    "production_acceptance_refresh_completed",
                ]
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


def _pre_run_acceptance_validation_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_validation_ready_for_review": True,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "pre_run_acceptance_validation": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "production_acceptance_command": _locked_acceptance_command(),
            "exact_future_acceptance_json_path": _locked_acceptance_result_path(),
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
        "result_validation": {
            "acceptance_result_provided": False,
            "validation_performed": False,
            "validation_passed": False,
            "summary": (
                "No real acceptance result JSON was provided. This artifact is a "
                "review-ready validator contract only and does not validate a real "
                "acceptance run yet."
            ),
        },
    }


def _acceptance_result_validator_passed_json() -> dict:
    payload = _acceptance_result_validator_json()
    payload["metadata"]["acceptance_executed"] = True
    payload["status"]["acceptance_result_validation_performed"] = True
    payload["status"]["acceptance_result_validation_passed"] = True
    payload["result_validation"] = {
        "acceptance_result_provided": True,
        "validation_performed": True,
        "validation_passed": True,
        "summary": "prod_4x4_normal acceptance result validated against the locked contract.",
    }
    return payload


def _review_state_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "review_state_ready": True,
            "repo_side_review_state_updated": True,
            "reviewed_runtime_patch_exists": True,
            "runtime_enablement_allowed": False,
            "production_acceptance_refresh_completed": False,
        },
    }


def test_anchor119_row_domain_acceptance_execution_gate_ready(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    acceptance_result_validator_path = tmp_path / "acceptance_result_validator.json"

    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    _write_json(acceptance_execution_staging_path, _acceptance_execution_staging_json())
    _write_json(acceptance_result_validator_path, _acceptance_result_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
            repo_root,
            signoff_record_validator_path=signoff_record_validator_path,
            signoff_bundle_path=runtime_patch_signoff_bundle_path,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            acceptance_result_validator_path=acceptance_result_validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
    )
    assert report["status"]["acceptance_execution_gate_ready"] is True
    assert (
        report["status"]["acceptance_execution_authorization_prerequisites_met"]
        is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["acceptance_executed"] is False
    assert report["status"]["missing_prerequisite_gate_ids"] == [
        "reviewed_runtime_patch_exists"
    ]
    execution_gate = report["acceptance_execution_gate"]
    assert execution_gate["does_not_authorize_execution"] is True
    assert (
        execution_gate["locked_execution_target"]["production_profile_id"]
        == "prod_4x4_normal"
    )
    assert (
        execution_gate["locked_execution_target"]["exact_future_acceptance_command"]
        == _locked_acceptance_command()
    )
    assert (
        execution_gate["locked_execution_target"][
            "exact_future_acceptance_result_path"
        ]
        == _locked_acceptance_result_path()
    )
    assert (
        execution_gate["reviewed_runtime_patch_signoff_state"][
            "reviewed_runtime_patch_exists"
        ]
        is False
    )
    missing = execution_gate["missing_prerequisites_before_execution_authorization"]
    assert [entry["gate_id"] for entry in missing] == ["reviewed_runtime_patch_exists"]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_text(
            report
        )
    )
    assert "Acceptance Execution Gate" in markdown
    assert "acceptance_execution_authorized=False" in text


def test_anchor119_row_domain_acceptance_execution_gate_uses_review_state_marker(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    acceptance_result_validator_path = tmp_path / "acceptance_result_validator.json"
    review_state_path = tmp_path / "review_state.json"

    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    _write_json(acceptance_execution_staging_path, _acceptance_execution_staging_json())
    _write_json(acceptance_result_validator_path, _acceptance_result_validator_json())
    _write_json(review_state_path, _review_state_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
            repo_root,
            signoff_record_validator_path=signoff_record_validator_path,
            signoff_bundle_path=runtime_patch_signoff_bundle_path,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            acceptance_result_validator_path=acceptance_result_validator_path,
            review_state_path=review_state_path,
        )
    )

    assert report["status"]["acceptance_execution_gate_ready"] is True
    assert report["status"]["review_state_ready"] is True
    assert report["status"]["reviewed_runtime_patch_exists"] is True
    assert (
        report["status"]["acceptance_execution_authorization_prerequisites_met"]
        is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["missing_prerequisite_gate_ids"] == [
        "production_acceptance_refresh_completed"
    ]
    state = report["acceptance_execution_gate"]["reviewed_runtime_patch_signoff_state"]
    assert state["review_state_ready"] is True
    assert state["reviewed_runtime_patch_exists"] is True


def test_anchor119_row_domain_acceptance_execution_gate_consumes_validated_acceptance_result(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    acceptance_result_validator_path = tmp_path / "acceptance_result_validator.json"
    review_state_path = tmp_path / "review_state.json"

    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    _write_json(acceptance_execution_staging_path, _acceptance_execution_staging_json())
    _write_json(
        acceptance_result_validator_path, _acceptance_result_validator_passed_json()
    )
    _write_json(review_state_path, _review_state_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
            repo_root,
            signoff_record_validator_path=signoff_record_validator_path,
            signoff_bundle_path=runtime_patch_signoff_bundle_path,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            acceptance_result_validator_path=acceptance_result_validator_path,
            review_state_path=review_state_path,
        )
    )

    assert report["status"]["acceptance_execution_gate_ready"] is True
    assert (
        report["status"]["acceptance_execution_authorization_prerequisites_met"]
        is True
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is True
    assert report["status"]["production_acceptance_refresh_completed"] is True
    assert report["status"]["acceptance_result_validation_passed"] is True
    assert report["status"]["missing_prerequisite_gate_ids"] == []
    assert report["status"]["recommended_next_step"] == (
        "refresh_long_run_preflight_after_validated_prod_4x4_acceptance"
    )
    assert "remaining B5A/certified-anchor gate" in report["status"][
        "handoff_recommendation"
    ]
    execution_state = report["acceptance_execution_gate"]["acceptance_execution_state"]
    assert execution_state["acceptance_result_validation_passed"] is True


def test_anchor119_row_domain_acceptance_execution_gate_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"

    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    _write_json(acceptance_execution_staging_path, _acceptance_execution_staging_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate(
            repo_root,
            signoff_record_validator_path=signoff_record_validator_path,
            signoff_bundle_path=runtime_patch_signoff_bundle_path,
            acceptance_refresh_prep_path=acceptance_refresh_prep_path,
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            acceptance_result_validator_path=tmp_path / "missing_result_validator.json",
        )
    )

    assert report["status"]["acceptance_execution_gate_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "acceptance_result_validator_present" in failed
    assert "acceptance_result_validator_ready" in report["status"][
        "missing_prerequisite_gate_ids"
    ]


def test_anchor119_row_domain_acceptance_execution_gate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    signoff_record_validator_path = tmp_path / "signoff_record_validator.json"
    runtime_patch_signoff_bundle_path = tmp_path / "runtime_patch_signoff_bundle.json"
    acceptance_refresh_prep_path = tmp_path / "acceptance_refresh_prep.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    acceptance_result_validator_path = tmp_path / "acceptance_result_validator.json"
    output_dir = tmp_path / "out"

    _write_json(signoff_record_validator_path, _signoff_record_validator_json())
    _write_json(runtime_patch_signoff_bundle_path, _runtime_patch_signoff_bundle_json())
    _write_json(acceptance_refresh_prep_path, _acceptance_refresh_prep_json())
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    _write_json(acceptance_execution_staging_path, _acceptance_execution_staging_json())
    _write_json(acceptance_result_validator_path, _acceptance_result_validator_json())
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_acceptance_execution_gate.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--runtime-patch-signoff-bundle",
            str(runtime_patch_signoff_bundle_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
            "--pre-run-acceptance-validation",
            str(pre_run_acceptance_validation_path),
            "--acceptance-execution-staging",
            str(acceptance_execution_staging_path),
            "--acceptance-result-validator",
            str(acceptance_result_validator_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain acceptance execution gate" in no_write.stdout
    assert "acceptance_execution_authorized=False" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--signoff-record-validator",
            str(signoff_record_validator_path),
            "--runtime-patch-signoff-bundle",
            str(runtime_patch_signoff_bundle_path),
            "--acceptance-refresh-prep",
            str(acceptance_refresh_prep_path),
            "--pre-run-acceptance-validation",
            str(pre_run_acceptance_validation_path),
            "--acceptance-execution-staging",
            str(acceptance_execution_staging_path),
            "--acceptance-result-validator",
            str(acceptance_result_validator_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_acceptance_execution_gate_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "anchor119_row_domain_acceptance_execution_gate.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["acceptance_execution_gate_ready"] is True
    assert payload["status"]["acceptance_execution_authorized"] is False
    assert (
        output_dir / "anchor119_row_domain_acceptance_execution_gate.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_acceptance_execution_gate.txt"
    ).exists()

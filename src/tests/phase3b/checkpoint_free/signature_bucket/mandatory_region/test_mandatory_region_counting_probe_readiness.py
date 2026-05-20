from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.mandatory_region.build_mandatory_region_counting_probe_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FUTURE_RUN_ID,
    MANDATORY_REGION_COUNTING_ENV_VAR,
    SIGNATURE_INSTRUMENTATION_ENV_VAR,
    build_signature_bucket_mandatory_region_counting_probe_readiness,
    build_future_command_template,
    validate_future_command_template,
)


def test_mandatory_region_counting_probe_readiness_builds_artifact(
    tmp_path: Path,
) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_mandatory_region_counting_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert (
        readiness["readiness"]["classification"]
        == "ready_for_mandatory_region_counting_probe_review"
    )
    assert readiness["probe_execution_enabled"] is False
    assert readiness["next_probe_allowed_only_after_readiness_review"] is True
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["production_profile_changed"] is False
    assert (output_dir / "signature_bucket_mandatory_region_counting_probe_readiness.json").exists()
    assert (output_dir / "signature_bucket_mandatory_region_counting_probe_readiness.md").exists()
    assert (output_dir / "future_command_template.json").exists()
    assert (output_dir / "sensitive_path_fingerprint.json").exists()


def test_mandatory_region_counting_probe_readiness_missing_s51_blocks(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s51_implementation"].unlink()

    readiness = build_signature_bucket_mandatory_region_counting_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    assert readiness["readiness"]["classification"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s51_patch_implemented_and_verified"] == "failed"


def test_mandatory_region_counting_probe_readiness_missing_s48_blocks(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s48_visibility_probe_review"].unlink()

    readiness = build_signature_bucket_mandatory_region_counting_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s48_completed_mandatory_scan_hotspot"] == "failed"


def test_mandatory_region_counting_probe_command_template_is_bounded(
    tmp_path: Path,
) -> None:
    readiness = build_signature_bucket_mandatory_region_counting_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    template = readiness["future_command_template"]
    command = template["command"]
    command_text = " ".join(command).lower()
    assert command == EXPECTED_FUTURE_COMMAND
    assert template["candidate_key"] == "42x32"
    assert template["execute_no_solve"] is True
    assert template["run_id"] == FUTURE_RUN_ID
    assert template["environment"] == {
        SIGNATURE_INSTRUMENTATION_ENV_VAR: "1",
        MANDATORY_REGION_COUNTING_ENV_VAR: "1",
    }
    assert "--execute-no-solve" in command
    assert "--resume-campaign" not in command
    assert "168h" not in command_text
    assert "--checkpoint" not in command
    assert "--checkpoint-dir" not in command
    assert "--write-checkpoint" not in command
    assert "--import-checkpoint" not in command
    assert "--proof" not in command
    assert "--release" not in command
    assert "--viewer" not in command
    assert "--frontdoor" not in command
    assert readiness["future_command_validation"]["valid"] is True


def test_mandatory_region_counting_probe_command_validator_rejects_drift(
    tmp_path: Path,
) -> None:
    base = build_future_command_template()
    cases = [
        (
            "extra_flag",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND, "--extra-diagnostic"]},
            "command_vector_mismatch",
        ),
        (
            "duplicate_flag",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND, "--execute-no-solve"]},
            "duplicate_flags:--execute-no-solve",
        ),
        (
            "reordered_command",
            {
                **base,
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--candidate-key",
                    "42x32",
                    "--execute-no-solve",
                    "--run-id",
                    FUTURE_RUN_ID,
                ],
            },
            "command_vector_mismatch",
        ),
        (
            "wrong_run_id",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND[:-1], "wrong_run"], "run_id": "wrong_run"},
            "unexpected_run_id",
        ),
        (
            "wrong_candidate",
            {
                **base,
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--execute-no-solve",
                    "--candidate-key",
                    "67x20",
                    "--run-id",
                    FUTURE_RUN_ID,
                ],
                "candidate_key": "67x20",
            },
            "candidate_key_must_be_42x32",
        ),
        (
            "checkpoint_flag",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND, "--write-checkpoint"]},
            "checkpoint_flag_forbidden",
        ),
        (
            "proof_flag",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND, "--proof"]},
            "forbidden_tokens:--proof",
        ),
        (
            "viewer_flag",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND, "--viewer"]},
            "forbidden_tokens:--viewer",
        ),
        (
            "frontdoor_flag",
            {**base, "command": [*EXPECTED_FUTURE_COMMAND, "--frontdoor"]},
            "forbidden_tokens:--frontdoor",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for _name, template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_mandatory_region_counting_probe_readiness_no_write_does_not_create_artifacts(
    tmp_path: Path,
) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_mandatory_region_counting_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert readiness["status"] == "completed"
    assert not output_dir.exists()


def test_mandatory_region_counting_probe_readiness_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S52 readiness namespace"):
        build_signature_bucket_mandatory_region_counting_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad_namespace",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(root: Path) -> dict[str, Path]:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    agents = root.parent / "AGENTS.md"
    agents.write_text(
        "- Current S51 mandatory-region-counting source patch state: implemented.\n",
        encoding="utf-8",
    )
    paths = {
        "s48_visibility_probe_review": evidence / "s48_probe_review.json",
        "s49_mandatory_scan_strategy": evidence / "s49_strategy.json",
        "s50_review_summary": evidence / "s50_review_summary.json",
        "s51_implementation": evidence / "s51_implementation.json",
        "agents": agents,
    }
    paths["s48_visibility_probe_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "mandatory_scan_hotspot"},
                "signature_instrumentation": {
                    "present": True,
                    "phase_seconds": {"per_anchor_mandatory_scan": 68.0},
                    "totals": {
                        "mandatory_cells_scanned": 1000,
                        "mandatory_pose_hits": 2000,
                        "mandatory_unique_blocked_poses": 300,
                    },
                },
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s49_mandatory_scan_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "mandatory_signature_bucket_region_counting_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s50_review_summary"].write_text(
        json.dumps(
            {
                "status": "review_passed_safe_to_request_authorization",
                "review_verdict": {
                    "scope_safe_to_request_authorization": True,
                    "review_is_authorization": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s51_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "user_authorization": {"granted": True},
                "source_patch": {"env_var": MANDATORY_REGION_COUNTING_ENV_VAR},
                "sensitive_path_status": {
                    "cp_solver_solve_called": False,
                    "checkpoint_written": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "52_signature_bucket_mandatory_region_counting_probe_readiness"
    )

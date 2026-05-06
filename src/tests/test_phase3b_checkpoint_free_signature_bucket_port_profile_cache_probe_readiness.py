from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_port_profile_cache_probe_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FUTURE_RUN_ID,
    PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR,
    REQUIRED_ENVIRONMENT,
    build_future_command_template,
    build_signature_bucket_port_profile_cache_probe_readiness,
    validate_future_command_template,
)


def test_port_profile_cache_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_port_profile_cache_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_port_profile_cache_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert (output_dir / "signature_bucket_port_profile_cache_probe_readiness.json").exists()
    assert (output_dir / "future_command_template.json").exists()


def test_port_profile_cache_probe_readiness_missing_s116_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s116_implementation"].unlink()

    readiness = build_signature_bucket_port_profile_cache_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert readiness["status"] == "manual_review_required"
    assert checks["s116_patch_implemented_and_verified"] == "failed"


def test_port_profile_cache_command_template_is_exact_and_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_port_profile_cache_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    template = readiness["future_command_template"]
    assert template["command"] == EXPECTED_FUTURE_COMMAND
    assert template["candidate_key"] == "42x32"
    assert template["execute_no_solve"] is True
    assert template["run_id"] == FUTURE_RUN_ID
    assert template["environment"][PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR] == "1"
    assert set(REQUIRED_ENVIRONMENT).issubset(set(template["environment"]))
    assert readiness["future_command_validation"]["valid"] is True


def test_port_profile_cache_command_validator_rejects_drift() -> None:
    base = build_future_command_template()
    cases = [
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--extra"]}, "command_vector_mismatch"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--execute-no-solve"]}, "duplicate_flags:--execute-no-solve"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND[:-1], "wrong_run"], "run_id": "wrong_run"}, "unexpected_run_id"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--write-checkpoint"]}, "checkpoint_flag_forbidden"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--proof"]}, "forbidden_tokens:--proof"),
        (
            {
                **base,
                "environment": {
                    key: value
                    for key, value in base["environment"].items()
                    if key != PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR
                },
            },
            f"{PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR}_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_port_profile_cache_readiness_no_write_and_namespace_guard(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)
    readiness = build_signature_bucket_port_profile_cache_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )
    assert readiness["status"] == "completed"
    assert not output_dir.exists()
    with pytest.raises(ValueError, match="S117 readiness namespace"):
        build_signature_bucket_port_profile_cache_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    paths = {
        "s113_execution": evidence / "s113_execution.json",
        "s111_review": evidence / "s111_review.json",
        "s114_strategy": evidence / "s114_strategy.json",
        "s115_review_summary": evidence / "s115_review_summary.json",
        "s116_implementation": evidence / "s116_implementation.json",
        "agents": tmp_path / "AGENTS.md",
    }
    paths["s113_execution"].write_text(
        json.dumps(
            {
                "status": "completed",
                "classification": "port_profile_and_boundary_cache_initialization_hotspot",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s111_review"].write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "port_profile_and_boundary_cache_initialization_hotspot"
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s114_strategy"].write_text(
        json.dumps({"classification": "port_profile_boundary_cache_subphase_strategy_required"})
        + "\n",
        encoding="utf-8",
    )
    paths["s115_review_summary"].write_text(json.dumps({"review_verdict": "pass"}) + "\n", encoding="utf-8")
    paths["s116_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "env_var": PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["agents"].write_text("S116 implemented\n", encoding="utf-8")
    return paths


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "117_signature_bucket_port_profile_cache_probe_readiness"
    )

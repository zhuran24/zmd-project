from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_powered_support_compact_item_probe_readiness import (
    COMPACT_ITEM_OPTIMIZATION_ENV_VAR,
    EXPECTED_FUTURE_COMMAND,
    FUTURE_RUN_ID,
    POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR,
    REQUIRED_ENVIRONMENT,
    build_future_command_template,
    build_signature_bucket_powered_support_compact_item_probe_readiness,
    validate_future_command_template,
)


def test_powered_support_compact_item_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_powered_support_compact_item_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_powered_support_compact_item_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert (output_dir / "signature_bucket_powered_support_compact_item_probe_readiness.json").exists()
    assert (output_dir / "future_command_template.json").exists()


def test_powered_support_compact_item_probe_readiness_missing_s131_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s131_implementation"].unlink()

    readiness = build_signature_bucket_powered_support_compact_item_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert readiness["status"] == "manual_review_required"
    assert checks["s131_patch_implemented_and_verified"] == "failed"


def test_powered_support_coverer_command_template_is_exact_and_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_powered_support_compact_item_probe_readiness(
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
    assert template["environment"][POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR] == "1"
    assert template["environment"][COMPACT_ITEM_OPTIMIZATION_ENV_VAR] == "1"
    assert set(REQUIRED_ENVIRONMENT).issubset(set(template["environment"]))
    assert readiness["future_command_validation"]["valid"] is True


def test_powered_support_coverer_command_validator_rejects_drift() -> None:
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
                    if key != COMPACT_ITEM_OPTIMIZATION_ENV_VAR
                },
            },
            f"{COMPACT_ITEM_OPTIMIZATION_ENV_VAR}_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_powered_support_coverer_readiness_no_write_and_namespace_guard(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)
    readiness = build_signature_bucket_powered_support_compact_item_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )
    assert readiness["status"] == "completed"
    assert not output_dir.exists()
    with pytest.raises(ValueError, match="S132 readiness namespace"):
        build_signature_bucket_powered_support_compact_item_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    paths = {
        "s128_execution": evidence / "s128_execution.json",
        "s126_review": evidence / "s126_review.json",
        "s130_review_summary": evidence / "s130_review_summary.json",
        "s131_implementation": evidence / "s131_implementation.json",
        "agents": tmp_path / "AGENTS.md",
    }
    paths["s128_execution"].write_text(
        json.dumps(
            {
                "status": "completed",
                "probe_safety": {"sensitive_path_clean": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s126_review"].write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "compact_item_accumulation_hotspot"
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s130_review_summary"].write_text(
        json.dumps({"review_verdict": "pass", "review_is_authorization": False}) + "\n",
        encoding="utf-8",
    )
    paths["s131_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "env_var": COMPACT_ITEM_OPTIMIZATION_ENV_VAR,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["agents"].write_text("S131 implemented\n", encoding="utf-8")
    return paths


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "132_signature_bucket_powered_support_compact_item_probe_readiness"
    )



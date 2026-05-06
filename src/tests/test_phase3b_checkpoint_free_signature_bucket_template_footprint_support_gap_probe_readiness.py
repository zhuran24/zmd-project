from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_template_footprint_support_gap_probe_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FALLBACK_INSTRUMENTATION_ENV_VAR,
    FUTURE_RUN_ID,
    MANDATORY_REGION_COUNTING_ENV_VAR,
    SIGNATURE_INSTRUMENTATION_ENV_VAR,
    SUPPORT_GAP_INSTRUMENTATION_ENV_VAR,
    TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR,
    build_future_command_template,
    build_signature_bucket_template_footprint_support_gap_probe_readiness,
    validate_future_command_template,
)


def test_support_gap_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_template_footprint_support_gap_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_support_gap_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["readiness"]["baseline_support_attempts"] == 21489
    assert readiness["readiness"]["baseline_support_used"] == 0
    assert (output_dir / "signature_bucket_template_footprint_support_gap_probe_readiness.json").exists()
    assert (output_dir / "future_command_template.json").exists()


def test_support_gap_probe_readiness_missing_s78_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s78_implementation"].unlink()

    readiness = build_signature_bucket_template_footprint_support_gap_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s78_patch_implemented_and_verified"] == "failed"


def test_support_gap_probe_readiness_checkpoint_file_blocks(tmp_path: Path) -> None:
    checkpoint = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{}\n", encoding="utf-8")

    readiness = build_signature_bucket_template_footprint_support_gap_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert readiness["status"] == "manual_review_required"
    assert checks["canonical_checkpoint_state_files_absent"] == "failed"


def test_support_gap_probe_command_template_is_exact_and_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_template_footprint_support_gap_probe_readiness(
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
    assert template["environment"] == {
        SIGNATURE_INSTRUMENTATION_ENV_VAR: "1",
        MANDATORY_REGION_COUNTING_ENV_VAR: "1",
        FALLBACK_INSTRUMENTATION_ENV_VAR: "1",
        TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR: "1",
        SUPPORT_GAP_INSTRUMENTATION_ENV_VAR: "1",
    }
    assert readiness["future_command_validation"]["valid"] is True


def test_support_gap_probe_command_validator_rejects_drift() -> None:
    base = build_future_command_template()
    cases = [
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--extra"]}, "command_vector_mismatch"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--execute-no-solve"]}, "duplicate_flags:--execute-no-solve"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND[:-1], "wrong_run"], "run_id": "wrong_run"}, "unexpected_run_id"),
        (
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
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--write-checkpoint"]}, "checkpoint_flag_forbidden"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--proof"]}, "forbidden_tokens:--proof"),
        (
            {
                **base,
                "environment": {
                    SIGNATURE_INSTRUMENTATION_ENV_VAR: "1",
                    MANDATORY_REGION_COUNTING_ENV_VAR: "1",
                    FALLBACK_INSTRUMENTATION_ENV_VAR: "1",
                    TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR: "1",
                },
            },
            "support_gap_instrumentation_env_gate_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_support_gap_probe_readiness_no_write_and_namespace_guard(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)
    readiness = build_signature_bucket_template_footprint_support_gap_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )
    assert readiness["status"] == "completed"
    assert not output_dir.exists()
    with pytest.raises(ValueError, match="S79 readiness namespace"):
        build_signature_bucket_template_footprint_support_gap_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    agents = tmp_path / "AGENTS.md"
    paths = {
        "s75_execution": evidence / "s75_execution.json",
        "s73_review": evidence / "s73_review.json",
        "s76_strategy": evidence / "s76_strategy.json",
        "s77_review_summary": evidence / "s77_review_summary.json",
        "s78_implementation": evidence / "s78_implementation.json",
        "agents": agents,
    }
    paths["s75_execution"].write_text(json.dumps(_s75_payload()) + "\n", encoding="utf-8")
    paths["s73_review"].write_text(json.dumps(_s73_payload()) + "\n", encoding="utf-8")
    paths["s76_strategy"].write_text(json.dumps(_s76_payload()) + "\n", encoding="utf-8")
    paths["s77_review_summary"].write_text(json.dumps(_s77_payload()) + "\n", encoding="utf-8")
    paths["s78_implementation"].write_text(json.dumps(_s78_payload()) + "\n", encoding="utf-8")
    agents.write_text(
        "- Current S77 external review result and S78 support-gap instrumentation patch state: "
        f"{SUPPORT_GAP_INSTRUMENTATION_ENV_VAR}\n",
        encoding="utf-8",
    )
    return paths


def _s75_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "s73_classification": "template_footprint_support_not_used",
        "run_id": "local_hotspot_42x32_signature_bucket_template_footprint_inst_no_solve_001",
        "model_build_seconds": 38.9,
        "interpretation": {
            "template_footprint_support_attempts": 21489,
            "template_footprint_support_used": 0,
            "template_footprint_support_fallbacks": 6786,
            "current_mandatory_scan_seconds": 27.088,
            "fallback_reasons": {"unsupported_or_missing_template_footprint": 6786},
        },
        "safety": {
            "execute_no_solve": True,
            "cp_solver_solve_called": False,
            "main_py_executed": False,
            "exact_campaign_used": False,
            "runtime_execution_performed": False,
            "checkpoint_written": False,
            "proof_source": False,
            "source_model_mutation": False,
            "source_mutation_performed": False,
            "candidate_universe_changed": False,
            "scheduler_integration": False,
            "production_profile_changed": False,
            "sensitive_path_changed": False,
            "canonical_checkpoint_state_exists": False,
            "canonical_checkpoint_telemetry_exists": False,
        },
    }


def _s73_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "run_id": "local_hotspot_42x32_signature_bucket_template_footprint_inst_no_solve_001",
        "interpretation": {
            "classification": "template_footprint_support_not_used",
            "template_footprint_support_attempts": 21489,
            "template_footprint_support_used": 0,
            "template_footprint_support_fallbacks": 6786,
            "current_mandatory_scan_seconds": 27.088,
            "current_unsupported_footprint_fallbacks": 6786,
        },
    }


def _s76_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "source_mutation_performed": False,
        "review_required_before_authorization": True,
        "interpretation": {"classification": "template_footprint_support_not_used_strategy_required"},
    }


def _s77_payload() -> dict[str, object]:
    return {
        "review_verdict": "pass",
        "safe_to_request_authorization": True,
        "review_is_authorization": False,
        "authorization_required_next": True,
    }


def _s78_payload() -> dict[str, object]:
    return {
        "status": "implemented_and_verified",
        "implementation": {"env_var": SUPPORT_GAP_INSTRUMENTATION_ENV_VAR},
        "verification": {
            "canonical_checkpoint_state_exists_after": False,
            "canonical_checkpoint_telemetry_exists_after": False,
        },
        "safety": {
            "probe_executed": False,
            "runtime_solve_executed": False,
            "cp_solver_solve_called": False,
            "checkpoint_written": False,
            "proof_source": False,
            "production_default_changed": False,
        },
    }


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "79_signature_bucket_template_footprint_support_gap_probe_readiness"
    )

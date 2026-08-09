from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.payload_footprint.build_probe_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FALLBACK_INSTRUMENTATION_ENV_VAR,
    FUTURE_RUN_ID,
    MANDATORY_REGION_COUNTING_ENV_VAR,
    PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR,
    SIGNATURE_INSTRUMENTATION_ENV_VAR,
    SUPPORT_GAP_INSTRUMENTATION_ENV_VAR,
    TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR,
    build_future_command_template,
    build_signature_bucket_payload_footprint_probe_readiness,
    validate_future_command_template,
)


def test_payload_footprint_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_payload_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_payload_footprint_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["readiness"]["baseline_unstable_footprint_bounds_fallbacks"] == 6786
    assert (output_dir / "signature_bucket_payload_footprint_probe_readiness.json").exists()
    assert (output_dir / "future_command_template.json").exists()


def test_payload_footprint_probe_readiness_missing_s85_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s85_implementation"].unlink()

    readiness = build_signature_bucket_payload_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s85_patch_implemented_and_verified"] == "failed"


def test_payload_footprint_probe_readiness_checkpoint_file_blocks(tmp_path: Path) -> None:
    checkpoint = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{}\n", encoding="utf-8")

    readiness = build_signature_bucket_payload_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert readiness["status"] == "manual_review_required"
    assert checks["canonical_checkpoint_state_files_absent"] == "failed"


def test_payload_footprint_probe_command_template_is_exact_and_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_payload_footprint_probe_readiness(
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
        PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR: "1",
    }
    assert readiness["future_command_validation"]["valid"] is True


def test_payload_footprint_probe_command_validator_rejects_drift() -> None:
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
                    SUPPORT_GAP_INSTRUMENTATION_ENV_VAR: "1",
                },
            },
            "payload_footprint_stability_env_gate_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_payload_footprint_probe_readiness_no_write_and_namespace_guard(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)
    readiness = build_signature_bucket_payload_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )
    assert readiness["status"] == "completed"
    assert not output_dir.exists()
    with pytest.raises(ValueError, match="S86 readiness namespace"):
        build_signature_bucket_payload_footprint_probe_readiness(
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
        "s82_execution": evidence / "s82_execution.json",
        "s80_review": evidence / "s80_review.json",
        "s83_strategy": evidence / "s83_strategy.json",
        "s84_review_summary": evidence / "s84_review_summary.json",
        "s85_implementation": evidence / "s85_implementation.json",
        "agents": agents,
    }
    paths["s82_execution"].write_text(json.dumps(_s82_payload()) + "\n", encoding="utf-8")
    paths["s80_review"].write_text(json.dumps(_s80_payload()) + "\n", encoding="utf-8")
    paths["s83_strategy"].write_text(json.dumps(_s83_payload()) + "\n", encoding="utf-8")
    paths["s84_review_summary"].write_text(json.dumps(_s84_payload()) + "\n", encoding="utf-8")
    paths["s85_implementation"].write_text(json.dumps(_s85_payload()) + "\n", encoding="utf-8")
    agents.write_text(
        f"- S85 implemented {PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR}\n",
        encoding="utf-8",
    )
    return paths


def _s82_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "s80_classification": "unstable_footprint_bounds_dominates",
        "run_id": "local_hotspot_42x32_signature_bucket_template_footprint_support_gap_inst_no_solve_001",
        "dominant_gap_reason": "unstable_footprint_bounds_within_payload",
        "dominant_gap_count": 6786,
        "current_mandatory_scan_seconds": 26.631,
        "template_footprint_support_attempts": 21489,
        "template_footprint_support_used": 0,
        "template_footprint_support_fallbacks": 6786,
        "execute_no_solve": True,
        "safety": {
            "cp_solver_solve_called": False,
            "main_py_executed": False,
            "exact_campaign_used": False,
            "runtime_execution_performed": False,
            "checkpoint_written": False,
            "proof_source": False,
            "sensitive_path_comparison": {
                "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
                "changed": False,
                "changed_paths": [],
                "changed_entries": [],
            },
        },
    }


def _s80_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "interpretation": {
            "classification": "unstable_footprint_bounds_dominates",
            "current_mandatory_scan_seconds": 26.631,
            "template_footprint_support_attempts": 21489,
            "template_footprint_support_used": 0,
            "template_footprint_support_fallbacks": 6786,
            "dominant_gap_count": 6786,
        },
    }


def _s83_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "source_mutation_performed": False,
        "review_required_before_authorization": True,
        "interpretation": {"classification": "payload_footprint_stability_strategy_required"},
    }


def _s84_payload() -> dict[str, object]:
    return {
        "review_verdict": "pass",
        "review_is_authorization": False,
        "authorization_required_next": True,
    }


def _s85_payload() -> dict[str, object]:
    return {
        "status": "implemented_and_verified",
        "authorization": {"env_var": PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR},
        "verification": {
            "canonical_checkpoint_state_exists": False,
            "canonical_checkpoint_telemetry_exists": False,
        },
        "safety_flags": {
            "cp_solver_solve_called": False,
            "runtime_execution_performed": False,
            "checkpoint_written": False,
            "proof_source": False,
            "production_profile_changed": False,
        },
    }


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "86_signature_bucket_payload_footprint_probe_readiness"
    )

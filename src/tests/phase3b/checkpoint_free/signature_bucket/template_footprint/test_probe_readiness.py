from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.template_footprint.build_probe_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FALLBACK_INSTRUMENTATION_ENV_VAR,
    FUTURE_RUN_ID,
    MANDATORY_REGION_COUNTING_ENV_VAR,
    SIGNATURE_INSTRUMENTATION_ENV_VAR,
    TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR,
    build_future_command_template,
    build_signature_bucket_template_footprint_probe_readiness,
    validate_future_command_template,
)


def test_template_footprint_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_template_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_template_footprint_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["production_profile_changed"] is False
    assert readiness["readiness"]["baseline_unsupported_footprint_fallbacks"] == 6786
    assert (output_dir / "signature_bucket_template_footprint_probe_readiness.json").exists()
    assert (output_dir / "signature_bucket_template_footprint_probe_readiness.md").exists()
    assert (output_dir / "future_command_template.json").exists()
    assert (output_dir / "sensitive_path_fingerprint.json").exists()


def test_template_footprint_probe_readiness_missing_s71_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s71_implementation"].unlink()

    readiness = build_signature_bucket_template_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s71_patch_implemented_and_verified"] == "failed"


def test_template_footprint_probe_readiness_s70_not_pass_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    s70 = json.loads(inputs["s70_review_summary"].read_text(encoding="utf-8"))
    s70["review_verdict"] = "needs_revision"
    s70["review_passed"] = False
    inputs["s70_review_summary"].write_text(json.dumps(s70) + "\n", encoding="utf-8")

    readiness = build_signature_bucket_template_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s70_review_passed_not_authorization"] == "failed"


def test_template_footprint_probe_readiness_checkpoint_file_blocks(tmp_path: Path) -> None:
    checkpoint = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{}\n", encoding="utf-8")

    readiness = build_signature_bucket_template_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["canonical_checkpoint_state_files_absent"] == "failed"


def test_template_footprint_probe_command_template_is_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_template_footprint_probe_readiness(
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
        FALLBACK_INSTRUMENTATION_ENV_VAR: "1",
        TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR: "1",
    }
    assert "--execute-no-solve" in command
    assert "--resume-campaign" not in command
    assert "168h" not in command_text
    assert "--write-checkpoint" not in command
    assert "--proof" not in command
    assert "--release" not in command
    assert "--viewer" not in command
    assert "--frontdoor" not in command
    assert readiness["future_command_validation"]["valid"] is True


def test_template_footprint_probe_command_validator_rejects_drift() -> None:
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
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--viewer"]}, "forbidden_tokens:--viewer"),
        ({**base, "command": [*EXPECTED_FUTURE_COMMAND, "--frontdoor"]}, "forbidden_tokens:--frontdoor"),
        (
            {
                **base,
                "environment": {
                    SIGNATURE_INSTRUMENTATION_ENV_VAR: "1",
                    MANDATORY_REGION_COUNTING_ENV_VAR: "1",
                    FALLBACK_INSTRUMENTATION_ENV_VAR: "1",
                },
            },
            "template_footprint_support_env_gate_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_template_footprint_probe_readiness_no_write_does_not_create_artifacts(
    tmp_path: Path,
) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_template_footprint_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert readiness["status"] == "completed"
    assert not output_dir.exists()


def test_template_footprint_probe_readiness_rejects_bad_namespace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="S72 readiness namespace"):
        build_signature_bucket_template_footprint_probe_readiness(
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
        "s68_execution": evidence / "s68_execution.json",
        "s64_review": evidence / "s64_review.json",
        "s69_strategy": evidence / "s69_strategy.json",
        "s70_review_summary": evidence / "s70_review_summary.json",
        "s71_implementation": evidence / "s71_implementation.json",
        "agents": agents,
    }
    paths["s68_execution"].write_text(json.dumps(_s68_payload()) + "\n", encoding="utf-8")
    paths["s64_review"].write_text(json.dumps(_s64_payload()) + "\n", encoding="utf-8")
    paths["s69_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "review_required_before_authorization": True,
                "interpretation": {
                    "classification": "unsupported_template_footprint_support_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s70_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "pass",
                "review_passed": True,
                "review_is_authorization": False,
                "authorization_required_next": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s71_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "env_gate": {"name": TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR},
                "safety": {
                    "cp_solver_solve_called": False,
                    "runtime_execution_performed": False,
                    "checkpoint_written": False,
                    "proof_source": False,
                    "production_profile_changed": False,
                    "source_model_mutation": True,
                    "source_model_mutation_authorized": True,
                    "canonical_checkpoint_state_exists_before_after": False,
                    "canonical_checkpoint_telemetry_exists_before_after": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents.write_text(
        "- Current S71 template-footprint support state: implemented and verified.\n",
        encoding="utf-8",
    )
    return paths


def _s68_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "probe": {
            "run_id": "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001",
            "model_build_seconds": 38.14,
            "signature_bucket_tightening_seconds": 28.78,
        },
        "safety": {
            "execute_no_solve": True,
            "no_solve": True,
            "fresh_solver_run_started": False,
            "cp_solver_solve_called": False,
            "runtime_execution_performed": False,
            "main_py_executed": False,
            "exact_campaign_used": False,
            "checkpoint_written": False,
            "proof_source": False,
            "source_model_mutation": False,
            "source_mutation_performed": False,
            "candidate_universe_changed": False,
            "scheduler_integration": False,
            "production_profile_changed": False,
            "sensitive_path_comparison_changed": False,
            "sensitive_path_schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed_paths": [],
            "changed_entries": [],
            "canonical_checkpoint_state_exists_after": False,
            "canonical_checkpoint_telemetry_exists_after": False,
        },
        "s64_review": {
            "status": "completed",
            "classification": "unsupported_footprint_dominates",
            "dominant_reason": "unsupported_or_missing_template_footprint",
            "dominant_reason_count": 6786,
            "fallback_reason_total": 6786,
            "mandatory_scan_seconds": 27.09,
            "mandatory_region_counting_attempts": 21489,
            "mandatory_region_counting_used": 14703,
            "mandatory_region_counting_fallbacks": 6786,
        },
        "next_gate": "prepare_template_footprint_support_strategy_or_review",
    }


def _s64_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "interpretation": {
            "classification": "unsupported_footprint_dominates",
            "dominant_reason": "unsupported_or_missing_template_footprint",
            "dominant_reason_count": 6786,
            "fallback_reason_total": 6786,
            "mandatory_scan_seconds": 27.09,
        },
        "signature_instrumentation": {
            "fallback_reason_visibility": "fallback_reason_instrumentation_visible",
            "phase_seconds": {"per_anchor_mandatory_scan": 27.09},
            "totals": {
                "mandatory_region_counting_attempts": 21489,
                "mandatory_region_counting_used": 14703,
                "mandatory_region_counting_fallbacks": 6786,
            },
            "fallback_reasons": {"unsupported_or_missing_template_footprint": 6786},
            "top_fallback_entries": [],
        },
    }


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "72_signature_bucket_template_footprint_probe_readiness"
    )

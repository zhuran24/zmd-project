from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.fallback_reason.build_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FALLBACK_INSTRUMENTATION_ENV_VAR,
    FUTURE_RUN_ID,
    MANDATORY_REGION_COUNTING_ENV_VAR,
    SIGNATURE_INSTRUMENTATION_ENV_VAR,
    build_future_command_template,
    build_signature_bucket_fallback_reason_probe_readiness,
    validate_future_command_template,
)


def test_fallback_reason_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_fallback_reason_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_fallback_reason_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["production_profile_changed"] is False
    assert (output_dir / "signature_bucket_fallback_reason_probe_readiness.json").exists()
    assert (output_dir / "signature_bucket_fallback_reason_probe_readiness.md").exists()
    assert (output_dir / "future_command_template.json").exists()
    assert (output_dir / "sensitive_path_fingerprint.json").exists()


def test_fallback_reason_probe_readiness_missing_s62_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s62_implementation"].unlink()

    readiness = build_signature_bucket_fallback_reason_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s62_patch_implemented_and_verified"] == "failed"


def test_fallback_reason_probe_readiness_missing_residual_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path, fallbacks=0)

    readiness = build_signature_bucket_fallback_reason_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s59_fallback_residual_present"] == "failed"


def test_fallback_reason_probe_command_template_is_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_fallback_reason_probe_readiness(
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


def test_fallback_reason_probe_command_validator_rejects_drift() -> None:
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
                },
            },
            "fallback_reason_instrumentation_env_gate_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_fallback_reason_probe_readiness_no_write_does_not_create_artifacts(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_fallback_reason_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert readiness["status"] == "completed"
    assert not output_dir.exists()


def test_fallback_reason_probe_readiness_rejects_bad_namespace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="S63 readiness namespace"):
        build_signature_bucket_fallback_reason_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(root: Path, *, fallbacks: int = 6786) -> dict[str, Path]:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    agents = root.parent / "AGENTS.md"
    agents.write_text("- Current S62 fallback-reason instrumentation state: implemented.\n", encoding="utf-8")
    paths = {
        "s59_probe": evidence / "s59_probe.json",
        "s60_strategy": evidence / "s60_strategy.json",
        "s61_review_summary": evidence / "s61_review_summary.json",
        "s62_implementation": evidence / "s62_implementation.json",
        "agents": agents,
    }
    paths["s59_probe"].write_text(
        json.dumps(
            {
                "status": "completed",
                "target": {"candidate_key": "42x32"},
                "execute_no_solve": True,
                "cp_solver_solve_called": False,
                "runtime_execution_performed": False,
                "sensitive_path_comparison": {"changed": False, "changed_paths": []},
                "inventory": {
                    "build_stats_summary": {
                        "global_valid_inequalities": {
                            "signature_bucket_capacity_bounds": {
                                "signature_tightening_instrumentation": {
                                    "phase_seconds": {"per_anchor_mandatory_scan": 32.0},
                                    "totals": {
                                        "mandatory_region_counting_attempts": 21489,
                                        "mandatory_region_counting_used": 14703,
                                        "mandatory_region_counting_fallbacks": fallbacks,
                                    },
                                }
                            }
                        }
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s60_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "mandatory_region_counting_effective_but_fallback_residual_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s61_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "pass_safe_to_request_authorization",
                "review_is_authorization": False,
                "authorization_required_next": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s62_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "env_var": FALLBACK_INSTRUMENTATION_ENV_VAR,
                "preserved_behavior": {
                    "checkpoint_written": False,
                    "proof_source": False,
                },
                "sensitive_path_status": {
                    "data/checkpoints/exact_campaign_state.json_exists": False,
                    "data/checkpoints/exact_campaign_telemetry.json_exists": False,
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
        / "63_signature_bucket_fallback_reason_probe_readiness"
    )

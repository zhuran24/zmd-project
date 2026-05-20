from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.enabled_no_solve.build_readiness import (
    ENV_VAR,
    FUTURE_RUN_ID,
    build_signature_bucket_enabled_no_solve_probe_readiness,
)


def test_signature_bucket_enabled_no_solve_probe_readiness_builds_artifact(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_enabled_no_solve_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_readiness_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["next_probe_allowed_only_after_readiness_review"] is True
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["source_model_mutation"] is False
    assert readiness["production_profile_changed"] is False
    assert readiness["candidate_universe_changed"] is False
    assert (output_dir / "signature_bucket_enabled_no_solve_probe_readiness.json").exists()
    assert (output_dir / "signature_bucket_enabled_no_solve_probe_readiness.md").exists()
    assert (output_dir / "future_command_template.json").exists()
    assert (output_dir / "sensitive_path_fingerprint.json").exists()


def test_signature_bucket_enabled_no_solve_probe_readiness_missing_s41_blocks_probe_flag(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s41_implementation"].unlink()

    readiness = build_signature_bucket_enabled_no_solve_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    assert readiness["readiness"]["classification"] == "manual_review_required"
    assert readiness["readiness"]["future_probe_executable_now"] is False
    checks = {
        check["name"]: check["status"]
        for check in readiness["readiness"]["checks"]
    }
    assert checks["s41_implemented_and_user_authorized"] == "failed"


def test_signature_bucket_enabled_no_solve_probe_command_template_is_bounded(
    tmp_path: Path,
) -> None:
    readiness = build_signature_bucket_enabled_no_solve_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    command_template = readiness["future_command_template"]
    command = command_template["command"]
    command_text = " ".join(command).lower()
    assert command_template["candidate_key"] == "42x32"
    assert command_template["execute_no_solve"] is True
    assert command_template["run_id"] == FUTURE_RUN_ID
    assert command_template["environment"] == {ENV_VAR: "1"}
    assert "--execute-no-solve" in command
    assert "--resume-campaign" not in command
    assert "168h" not in command_text
    assert "--proof" not in command
    assert "--release" not in command
    assert "--viewer" not in command
    assert "--frontdoor" not in command
    assert readiness["future_command_validation"]["valid"] is True


def test_signature_bucket_enabled_no_solve_probe_readiness_no_write_does_not_create_artifacts(
    tmp_path: Path,
) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_enabled_no_solve_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert readiness["status"] == "completed"
    assert not output_dir.exists()


def test_signature_bucket_enabled_no_solve_probe_readiness_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S42 readiness namespace"):
        build_signature_bucket_enabled_no_solve_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad_namespace",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def test_signature_bucket_enabled_no_solve_probe_readiness_s40_s41_mismatch_blocks(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s40_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "does_not_pass",
                "review_approval_is_authorization": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    readiness = build_signature_bucket_enabled_no_solve_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    checks = {
        check["name"]: check["status"]
        for check in readiness["readiness"]["checks"]
    }
    assert checks["s40_review_passed_not_authorization"] == "failed"


def _write_inputs(root: Path) -> dict[str, Path]:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    agents = root.parent / "AGENTS.md"
    agents.write_text(
        "- Current S41 signature-bucket instrumentation state: implemented.\n",
        encoding="utf-8",
    )
    paths = {
        "s35_overlay_timing_probe": evidence / "s35_overlay_timing_probe.json",
        "s36_signature_bucket_strategy": evidence / "s36_strategy.json",
        "s39_revised_patch_spec": evidence / "s39_revision.json",
        "s40_review_summary": evidence / "s40_review_summary.json",
        "s41_implementation": evidence / "s41_implementation.json",
        "agents": agents,
    }
    paths["s35_overlay_timing_probe"].write_text(
        json.dumps(
            {
                "status": "completed",
                "cp_solver_solve_called": False,
                "target": {"candidate_key": "42x32"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s36_signature_bucket_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "signature_bucket_internal_loop_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s39_revised_patch_spec"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "output_path_finalization_revision_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s40_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "safe_to_request_user_project_owner_authorization",
                "review_approval_is_authorization": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s41_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "review_and_authorization": {"user_authorization_granted": True},
                "safety_flags": {
                    "solver_runtime_executed": False,
                    "canonical_checkpoint_written": False,
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
        / "42_signature_bucket_enabled_no_solve_probe_readiness"
    )

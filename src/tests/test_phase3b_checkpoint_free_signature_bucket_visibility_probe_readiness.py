from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_visibility_probe_readiness import (
    ENV_VAR,
    FUTURE_RUN_ID,
    build_signature_bucket_visibility_probe_readiness,
)


def test_signature_bucket_visibility_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_visibility_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_visibility_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["next_probe_allowed_only_after_readiness_review"] is True
    assert readiness["cp_solver_solve_called"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert readiness["production_profile_changed"] is False
    assert (output_dir / "signature_bucket_visibility_probe_readiness.json").exists()
    assert (output_dir / "signature_bucket_visibility_probe_readiness.md").exists()
    assert (output_dir / "future_command_template.json").exists()
    assert (output_dir / "sensitive_path_fingerprint.json").exists()


def test_signature_bucket_visibility_probe_readiness_missing_s46_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s46_implementation"].unlink()

    readiness = build_signature_bucket_visibility_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    assert readiness["status"] == "manual_review_required"
    assert readiness["readiness"]["classification"] == "manual_review_required"
    assert readiness["readiness"]["future_probe_executable_now"] is False
    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert checks["s46_patch_implemented_and_verified"] == "failed"


def test_signature_bucket_visibility_probe_command_template_is_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_visibility_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    template = readiness["future_command_template"]
    command = template["command"]
    command_text = " ".join(command).lower()
    assert template["candidate_key"] == "42x32"
    assert template["execute_no_solve"] is True
    assert template["run_id"] == FUTURE_RUN_ID
    assert template["environment"] == {ENV_VAR: "1"}
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


def test_signature_bucket_visibility_probe_readiness_no_write_does_not_create_artifacts(
    tmp_path: Path,
) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_visibility_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert readiness["status"] == "completed"
    assert not output_dir.exists()


def test_signature_bucket_visibility_probe_readiness_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S47 readiness namespace"):
        build_signature_bucket_visibility_probe_readiness(
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
        "- Current S46 visibility-path source patch state: implemented.\n",
        encoding="utf-8",
    )
    paths = {
        "s43_probe_review": evidence / "s43_probe_review.json",
        "s44_visibility_strategy": evidence / "s44_strategy.json",
        "s45_review_summary": evidence / "s45_review_summary.json",
        "s46_implementation": evidence / "s46_implementation.json",
        "agents": agents,
    }
    paths["s43_probe_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "instrumentation_inconclusive"},
                "signature_instrumentation": {"present": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s44_visibility_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "exact_core_overlay_instrumentation_visibility_gap"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s45_review_summary"].write_text(
        json.dumps(
            {
                "review_status": "passed_safe_to_request_authorization",
                "review_is_authorization": False,
                "implementation_authorized": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s46_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "user_authorization": {"granted": True},
                "source_patch": {"env_var": ENV_VAR},
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
        / "47_signature_bucket_visibility_probe_readiness"
    )

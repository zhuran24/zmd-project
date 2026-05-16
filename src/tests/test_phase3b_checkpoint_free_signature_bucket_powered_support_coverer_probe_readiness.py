"""[Codex-era artifact dependent] 永远 skip (除非 artifact 再生).

这个测试导入 scripts/build_phase3b_*_probe_review (或类似), 后者读取 Codex
session (2026-04-30) 产生的 tuning artifact:
  .artifacts/phase3b_local_13900ks_tuning_20260430/126_signature_bucket_powered_support_coverer_probe_review/
    signature_bucket_powered_support_coverer_probe_review.json

该 artifact 是 GPT-Codex workspace 实验产物, 未迁移到当前 project. src/tests/conftest.py
的 fixture guard `_missing_phase3b_signature_bucket_powered_support_coverer_artifact`
检测缺失时自动 skip 整个文件, 不报错.

保留原因 (per memory `feedback_cleanup_preserve_clarify` — 不丢东西原则):
- 历史 reference: 看 Phase 3B signature bucket 调研当时的 verification 逻辑
- 万一未来重生 artifact (e.g. 复现 Codex 实验), 这测试可以直接 re-enable
- 删了会丢历史, 留着零运行成本 (conftest skip 一次)

如果将来要清理, 必须**先**确认 artifact 不会复现 + 没人需要历史参考, 再批量删.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_readiness import (
    EXPECTED_FUTURE_COMMAND,
    FUTURE_RUN_ID,
    POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR,
    REQUIRED_ENVIRONMENT,
    build_future_command_template,
    build_signature_bucket_powered_support_coverer_probe_readiness,
    validate_future_command_template,
)


def test_powered_support_coverer_probe_readiness_builds_artifact(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    readiness = build_signature_bucket_powered_support_coverer_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
    )

    assert readiness["status"] == "completed"
    assert readiness["readiness"]["classification"] == "ready_for_powered_support_coverer_probe_review"
    assert readiness["probe_execution_enabled"] is False
    assert readiness["runtime_execution_performed"] is False
    assert readiness["checkpoint_written"] is False
    assert readiness["proof_source"] is False
    assert (output_dir / "signature_bucket_powered_support_coverer_probe_readiness.json").exists()
    assert (output_dir / "future_command_template.json").exists()


def test_powered_support_coverer_probe_readiness_missing_s124_blocks(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    inputs["s124_implementation"].unlink()

    readiness = build_signature_bucket_powered_support_coverer_probe_readiness(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=inputs,
        no_write=True,
    )

    checks = {check["name"]: check["status"] for check in readiness["readiness"]["checks"]}
    assert readiness["status"] == "manual_review_required"
    assert checks["s124_patch_implemented_and_verified"] == "failed"


def test_powered_support_coverer_command_template_is_exact_and_bounded(tmp_path: Path) -> None:
    readiness = build_signature_bucket_powered_support_coverer_probe_readiness(
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
                    if key != POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR
                },
            },
            f"{POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR}_must_be_1",
        ),
    ]
    assert validate_future_command_template(base)["valid"] is True
    for template, expected_failure in cases:
        validation = validate_future_command_template(template)
        assert validation["valid"] is False
        assert expected_failure in validation["failures"]


def test_powered_support_coverer_readiness_no_write_and_namespace_guard(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)
    readiness = build_signature_bucket_powered_support_coverer_probe_readiness(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )
    assert readiness["status"] == "completed"
    assert not output_dir.exists()
    with pytest.raises(ValueError, match="S125 readiness namespace"):
        build_signature_bucket_powered_support_coverer_probe_readiness(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    paths = {
        "s120_execution": evidence / "s120_execution.json",
        "s118_review": evidence / "s118_review.json",
        "s122_strategy": evidence / "s122_strategy.json",
        "s123_review_summary": evidence / "s123_review_summary.json",
        "s124_implementation": evidence / "s124_implementation.json",
        "agents": tmp_path / "AGENTS.md",
    }
    paths["s120_execution"].write_text(
        json.dumps(
            {
                "status": "completed",
                "post_s121_s118_review": {
                    "classification": "powered_support_coverer_hotspot"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s118_review"].write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": "powered_support_coverer_hotspot"
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s122_strategy"].write_text(
        json.dumps({"classification": "powered_support_coverer_detail_instrumentation_strategy_required"})
        + "\n",
        encoding="utf-8",
    )
    paths["s123_review_summary"].write_text(json.dumps({"review_verdict": "pass"}) + "\n", encoding="utf-8")
    paths["s124_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "env_var": POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["agents"].write_text("S124 implemented\n", encoding="utf-8")
    return paths


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "125_signature_bucket_powered_support_coverer_probe_readiness"
    )

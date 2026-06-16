from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.run_phase3b_local_tuning_profile import (
    run_local_tuning_profile,
    validate_tuning_command,
)
from scripts.summarize_phase3b_local_tuning_matrix import build_tuning_matrix_summary
from src.runtime.hardware_profile import build_hardware_profile
from src.runtime.process_tree_telemetry import (
    ProcessTreeSampler,
    summarize_telemetry_samples,
)


def test_hardware_profile_records_required_sections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "4")

    profile = build_hardware_profile(tmp_path)

    assert profile["schema"] == "phase3b-local-hardware-profile/v0"
    assert profile["project_root"] == str(tmp_path.resolve())
    assert profile["cpu"]["logical_count"] is not None
    assert profile["memory"]["virtual"]["total_bytes"] > 0
    assert profile["environment"]["vars"]["EXACT_CP_SAT_WORKERS"] == "4"
    assert set(profile["disk"]["drives"]).issuperset({"C", "D", "E"})
    assert profile["safety"]["final_168h_started"] is False
    assert profile["safety"]["checkpoint_written"] is False


def test_process_tree_sampler_and_summary_shape() -> None:
    sample = ProcessTreeSampler().sample()

    assert sample["schema"] == "phase3b-process-tree-telemetry-sample/v0"
    assert sample["aggregate"]["process_count"] >= 1
    assert sample["aggregate"]["thread_count"] >= 1
    telemetry = summarize_telemetry_samples([sample])
    assert telemetry["sample_count"] == 1
    assert telemetry["peak_process_count"] >= 1


def test_tuning_command_safety_rejects_final_and_mutating_commands() -> None:
    assert validate_tuning_command(["python", "x.py", "--no-write"])["allowed"] is True

    final_run = validate_tuning_command(
        ["python", "main.py", "--campaign-hours", "168", "--no-write"]
    )
    assert final_run["allowed"] is False
    assert "forbidden_final_168h_campaign_hours" in final_run["reasons"]

    checkpoint_write = validate_tuning_command(
        ["python", "main.py", "--write-checkpoint", "--no-write"]
    )
    assert checkpoint_write["allowed"] is False
    assert any(reason.startswith("forbidden_checkpoint_token") for reason in checkpoint_write["reasons"])

    unsafe = validate_tuning_command(["python", "main.py"])
    assert unsafe["allowed"] is False
    assert "missing_dry_run_or_no_write_guard" in unsafe["reasons"]

    proof_marker = validate_tuning_command(
        ["python", "tool.py", "--no-write", "data/checkpoints/exact_campaign_state.json"]
    )
    assert proof_marker["allowed"] is False
    assert any(reason.startswith("forbidden_marker:data/checkpoints") for reason in proof_marker["reasons"])


def test_local_tuning_runner_no_execute_writes_only_tuning_namespaces(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    artifact_root = tmp_path / "artifacts" / "phase3b_local_13900ks_tuning_20260430"
    log_root = tmp_path / "logs" / "phase3b" / "local_13900ks_tuning_20260430"
    forbidden = [
        repo_root / "data" / "checkpoints" / "exact_campaign_state.json",
        repo_root / "data" / "checkpoints" / "exact_campaign_telemetry.json",
        repo_root / "data" / "solutions" / "final_solution.json",
        repo_root / "data" / "blueprints" / "optimal_blueprint.json",
        repo_root / "data" / "solutions" / "certified_delivery_manifest.json",
    ]
    before = {path: _file_fingerprint(path) for path in forbidden}

    summary = run_local_tuning_profile(
        project_root=repo_root,
        profile_id="prod_4x4_normal_validator_no_write",
        run_id="unit_no_execute",
        artifact_root=artifact_root,
        log_root=log_root,
        no_execute=True,
        sample_interval_seconds=0.05,
        timeout_seconds=1.0,
    )

    assert summary["status"] == "skipped_no_execute"
    assert summary["safety"]["final_168h_started"] is False
    assert summary["safety"]["checkpoint_written"] is False
    assert summary["safety"]["proof_source_mutated"] is False
    assert Path(summary["paths"]["raw_log"]).is_file()
    assert Path(summary["paths"]["telemetry_samples_jsonl"]).is_file()
    assert Path(summary["paths"]["hardware_profile_json"]).is_file()
    assert Path(summary["paths"]["campaign_telemetry_snapshot_json"]).is_file()
    assert Path(summary["paths"]["run_summary_json"]).is_file()
    assert Path(summary["paths"]["run_summary_md"]).is_file()
    for output_path in summary["paths"].values():
        assert str(output_path).startswith(str(tmp_path))
    after = {path: _file_fingerprint(path) for path in forbidden}
    assert after == before


def test_local_tuning_runner_executes_no_write_profile_and_matrix_summary(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    artifact_root = tmp_path / "artifacts" / "phase3b_local_13900ks_tuning_20260430"
    log_root = tmp_path / "logs" / "phase3b" / "local_13900ks_tuning_20260430"

    summary = run_local_tuning_profile(
        project_root=repo_root,
        profile_id="prod_4x4_normal_validator_no_write",
        run_id="unit_execute",
        artifact_root=artifact_root,
        log_root=log_root,
        sample_interval_seconds=0.05,
        timeout_seconds=20.0,
    )

    assert summary["status"] == "completed"
    assert summary["return_code"] == 0
    payload = json.loads(Path(summary["paths"]["run_summary_json"]).read_text(encoding="utf-8"))
    assert payload["profile_id"] == "prod_4x4_normal_validator_no_write"
    assert payload["telemetry_summary"]["sample_count"] >= 1

    matrix = build_tuning_matrix_summary(
        project_root=repo_root,
        artifact_root=artifact_root,
        log_root=log_root,
    )
    assert matrix["run_count"] == 1
    assert matrix["runs"][0]["run_id"] == "unit_execute"
    assert matrix["safety"]["summary_is_proof_source"] is False


def test_runner_cli_no_execute(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "run_phase3b_local_tuning_profile.py"
    artifact_root = tmp_path / "artifacts"
    log_root = tmp_path / "logs"

    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--profile",
            "prod_4x4_normal_validator_no_write",
            "--run-id",
            "cli_no_execute",
            "--artifact-root",
            str(artifact_root),
            "--log-root",
            str(log_root),
            "--no-execute",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "status=skipped_no_execute" in result.stdout
    assert (artifact_root / "cli_no_execute" / "run_summary.json").exists()


def _file_fingerprint(path: Path) -> tuple[bool, int | None, int | None]:
    if not path.exists():
        return (False, None, None)
    stat = path.stat()
    return (True, int(stat.st_size), int(stat.st_mtime_ns))

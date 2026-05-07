from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.hardware_profile import build_hardware_profile
from src.runtime.process_tree_telemetry import (
    ProcessTreeSampler,
    append_jsonl,
    read_telemetry_jsonl,
    summarize_telemetry_samples,
)
from src.search.exact_campaign import atomic_write_json, now_iso

ARTIFACT_ROOT = Path(".artifacts/phase3b_local_13900ks_tuning_20260430")
LOG_ROOT = Path(".codex_test_logs/phase3b/local_13900ks_tuning_20260430")

SAFE_PROFILE_COMMANDS: dict[str, list[str]] = {
    "prod_4x4_normal_dry_run": [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/run_prod_4x4_normal.ps1",
        "-ResumeCampaign",
        "-DryRun",
    ],
    "prod_4x4_high_dry_run": [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/run_prod_4x4_high.ps1",
        "-ResumeCampaign",
        "-DryRun",
    ],
    "prod_4x4_normal_validator_no_write": [
        sys.executable,
        "scripts/build_phase3b_prod_4x4_normal_dry_run.py",
        "--no-write",
    ],
    "operating_profile_no_write": [
        sys.executable,
        "scripts/build_phase3b_operating_profile.py",
        "--no-write",
    ],
    "baseline_4x4_normal_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "baseline_1x1_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "1",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "baseline_2x4_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "2",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "baseline_2x8_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "2",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "matrix_3x4_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "3",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "matrix_3x8_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "3",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "matrix_2x12_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "2",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "matrix_1x16_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "1",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "matrix_4x8_300s": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    # S6: Stage-specific worker profiles (per plan W0-W7)
    "s6_w0_4x_4444": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w1_4x_m6b2": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w2_4x_m8b2": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w3_4x_m6l6b2r6": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w4_4x_m8l6b2r6": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w5_3x_m8l8b2r8": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "3",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w6_3x_m8l6b2r6": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "3",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s6_w7_2x_m12l8b2r8": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.083",
        "--parallel-processes", "2",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    # S8: Medium confirmation — 30-minute throughput measurement runs
    "s8_w0_30min": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.5",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s8_builtin_defaults_30min": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.5",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s8_w6_30min": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.5",
        "--parallel-processes", "3",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    "s8_w7_2proc_30min": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "0.5",
        "--parallel-processes", "2",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
    # Accumulation loop: built-in defaults, 24h campaign budget, crash-resume循环跑
    "accumulation_builtin_24h": [
        sys.executable, "main.py",
        "--mode", "certified_exact",
        "--campaign-hours", "24.0",
        "--parallel-processes", "4",
        "--process-priority", "normal",
        "--frontier-probe-mode", "auto",
        "--resume-campaign",
    ],
}

LIVE_BASELINE_MAX_CAMPAIGN_HOURS = 48.0

PROFILE_ENV_OVERRIDES: dict[str, dict[str, str]] = {
    "baseline_4x4_normal_300s": {"EXACT_CP_SAT_WORKERS": "4"},
    "baseline_1x1_300s": {"EXACT_CP_SAT_WORKERS": "4"},
    "baseline_2x4_300s": {"EXACT_CP_SAT_WORKERS": "4"},
    "baseline_2x8_300s": {"EXACT_CP_SAT_WORKERS": "8"},
    "matrix_3x4_300s": {"EXACT_CP_SAT_WORKERS": "4"},
    "matrix_3x8_300s": {"EXACT_CP_SAT_WORKERS": "8"},
    "matrix_2x12_300s": {"EXACT_CP_SAT_WORKERS": "12"},
    "matrix_1x16_300s": {"EXACT_CP_SAT_WORKERS": "16"},
    "matrix_4x8_300s": {"EXACT_CP_SAT_WORKERS": "8"},
    # S6: Stage-specific worker overrides (master/local_capacity/binding/routing)
    "s6_w0_4x_4444": {
        "EXACT_MASTER_CP_SAT_WORKERS": "4",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "4",
        "EXACT_BINDING_CP_SAT_WORKERS": "4",
        "EXACT_ROUTING_CP_SAT_WORKERS": "4",
    },
    "s6_w1_4x_m6b2": {
        "EXACT_MASTER_CP_SAT_WORKERS": "6",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "4",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "4",
    },
    "s6_w2_4x_m8b2": {
        "EXACT_MASTER_CP_SAT_WORKERS": "8",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "4",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "4",
    },
    "s6_w3_4x_m6l6b2r6": {
        "EXACT_MASTER_CP_SAT_WORKERS": "6",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "6",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "6",
    },
    "s6_w4_4x_m8l6b2r6": {
        "EXACT_MASTER_CP_SAT_WORKERS": "8",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "6",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "6",
    },
    "s6_w5_3x_m8l8b2r8": {
        "EXACT_MASTER_CP_SAT_WORKERS": "8",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "8",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "8",
    },
    "s6_w6_3x_m8l6b2r6": {
        "EXACT_MASTER_CP_SAT_WORKERS": "8",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "6",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "6",
    },
    "s6_w7_2x_m12l8b2r8": {
        "EXACT_MASTER_CP_SAT_WORKERS": "12",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "8",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "8",
    },
    # S8: Medium confirmation env overrides
    "s8_w0_30min": {
        "EXACT_MASTER_CP_SAT_WORKERS": "4",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "4",
        "EXACT_BINDING_CP_SAT_WORKERS": "4",
        "EXACT_ROUTING_CP_SAT_WORKERS": "4",
    },
    # s8_builtin_defaults_30min: NO env overrides — uses built-in 8/8/4/8
    "s8_w6_30min": {
        "EXACT_MASTER_CP_SAT_WORKERS": "8",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "6",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "6",
    },
    "s8_w7_2proc_30min": {
        "EXACT_MASTER_CP_SAT_WORKERS": "12",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "8",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "8",
    },
}

DRY_GUARD_TOKENS = {"-dryrun", "--dry-run", "--no-write", "-whatif"}
CHECKPOINT_TOKENS = {
    "--write-checkpoint",
    "--import-checkpoint",
    "--checkpoint-write",
    "--checkpoint-import",
    "--checkpoint-output",
}
FORBIDDEN_MARKERS = (
    "data/checkpoints",
    "final_solution.json",
    "optimal_blueprint.json",
    "certified_delivery_manifest.json",
    "runtime_elimination",
    "runtime-elimination",
    "frontdoor",
    "release_promotion",
    "viewer_promotion",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a safe local Phase3B tuning profile with process telemetry."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--profile",
        choices=sorted(SAFE_PROFILE_COMMANDS),
        default="prod_4x4_normal_dry_run",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--log-root", type=Path, default=LOG_ROOT)
    parser.add_argument("--sample-interval-seconds", type=float, default=0.5)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Write the run plan and snapshots without launching the wrapped command.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    artifact_root = _resolve_output_dir(project_root, Path(args.artifact_root))
    log_root = _resolve_output_dir(project_root, Path(args.log_root))
    summary = run_local_tuning_profile(
        project_root=project_root,
        profile_id=str(args.profile),
        run_id=args.run_id,
        artifact_root=artifact_root,
        log_root=log_root,
        sample_interval_seconds=float(args.sample_interval_seconds),
        timeout_seconds=float(args.timeout_seconds),
        no_execute=bool(args.no_execute),
    )
    print("phase3b local tuning profile")
    print(f"profile_id={summary['profile_id']}")
    print(f"status={summary['status']}")
    print(f"run_summary_json={_display_path(project_root, Path(summary['paths']['run_summary_json']))}")
    return 0 if summary["status"] in {"completed", "skipped_no_execute"} else 2


def run_local_tuning_profile(
    *,
    project_root: Path,
    profile_id: str,
    run_id: str | None = None,
    artifact_root: Path | None = None,
    log_root: Path | None = None,
    sample_interval_seconds: float = 0.5,
    timeout_seconds: float = 60.0,
    no_execute: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    if profile_id not in SAFE_PROFILE_COMMANDS:
        raise ValueError(f"Unsupported local tuning profile: {profile_id}")
    command = list(SAFE_PROFILE_COMMANDS[profile_id])
    safety = validate_tuning_command(command)
    if not safety["allowed"]:
        raise ValueError("Unsafe local tuning command: " + "; ".join(safety["reasons"]))

    run_id = run_id or _default_run_id(profile_id)
    artifact_dir = (artifact_root or project_root / ARTIFACT_ROOT) / run_id
    log_dir = (log_root or project_root / LOG_ROOT) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    raw_log_path = log_dir / "raw.log"
    telemetry_path = log_dir / "telemetry_samples.jsonl"
    hardware_path = artifact_dir / "hardware_profile.json"
    campaign_snapshot_path = artifact_dir / "campaign_telemetry_snapshot.json"
    summary_json_path = artifact_dir / "run_summary.json"
    summary_md_path = artifact_dir / "run_summary.md"

    hardware_profile = build_hardware_profile(project_root)
    atomic_write_json(hardware_path, hardware_profile)
    atomic_write_json(
        campaign_snapshot_path,
        _campaign_telemetry_snapshot(project_root),
    )

    started_at = now_iso()
    start_ts = time.time()
    timed_out = False
    return_code: int | None = None
    env_overrides = PROFILE_ENV_OVERRIDES.get(profile_id, {})
    if no_execute:
        raw_log_path.write_text("execution skipped by --no-execute\n", encoding="utf-8")
        append_jsonl(telemetry_path, ProcessTreeSampler(os.getpid()).sample())
        status = "skipped_no_execute"
    else:
        return_code, timed_out = _run_command_with_telemetry(
            command=command,
            cwd=project_root,
            env_overrides=env_overrides,
            raw_log_path=raw_log_path,
            telemetry_path=telemetry_path,
            sample_interval_seconds=sample_interval_seconds,
            timeout_seconds=timeout_seconds,
        )
        status = "timeout" if timed_out else ("completed" if return_code == 0 else "failed")
    finished_at = now_iso()
    duration_seconds = time.time() - start_ts
    telemetry_summary = summarize_telemetry_samples(read_telemetry_jsonl(telemetry_path))
    summary = {
        "schema": "phase3b-local-tuning-run-summary/v0",
        "profile_id": profile_id,
        "run_id": run_id,
        "status": status,
        "return_code": return_code,
        "timed_out": timed_out,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(float(duration_seconds), 3),
        "command": command,
        "env_overrides": env_overrides,
        "safety": safety,
        "telemetry_summary": telemetry_summary,
        "paths": {
            "artifact_dir": str(artifact_dir),
            "log_dir": str(log_dir),
            "raw_log": str(raw_log_path),
            "telemetry_samples_jsonl": str(telemetry_path),
            "hardware_profile_json": str(hardware_path),
            "campaign_telemetry_snapshot_json": str(campaign_snapshot_path),
            "run_summary_json": str(summary_json_path),
            "run_summary_md": str(summary_md_path),
        },
    }
    atomic_write_json(summary_json_path, summary)
    _atomic_write_text(summary_md_path, render_run_summary_markdown(summary))
    return summary


def validate_tuning_command(command: Sequence[str]) -> dict[str, Any]:
    tokens = [str(token) for token in command]
    lower_tokens = [token.strip().lower() for token in tokens]
    normalized_command = " ".join(lower_tokens).replace("\\", "/")
    reasons: list[str] = []
    has_dry_guard = any(token in DRY_GUARD_TOKENS for token in lower_tokens)
    campaign_hours = _extract_campaign_hours(lower_tokens)
    is_live_baseline = (
        not has_dry_guard
        and campaign_hours is not None
        and campaign_hours < LIVE_BASELINE_MAX_CAMPAIGN_HOURS
    )
    if not has_dry_guard and not is_live_baseline:
        reasons.append("missing_dry_run_or_no_write_guard")
    for index, token in enumerate(lower_tokens):
        if token in CHECKPOINT_TOKENS:
            reasons.append(f"forbidden_checkpoint_token:{token}")
        if token in {"--resume-campaign", "-resumecampaign"} and not has_dry_guard and not is_live_baseline:
            reasons.append(f"resume_campaign_without_dry_guard:{token}")
        if token == "--campaign-hours":
            value = lower_tokens[index + 1] if index + 1 < len(lower_tokens) else ""
            if _float_or_none(value) is not None and float(value) >= 168.0:
                reasons.append("forbidden_final_168h_campaign_hours")
        if token.startswith("--campaign-hours="):
            value = token.split("=", 1)[1]
            if _float_or_none(value) is not None and float(value) >= 168.0:
                reasons.append("forbidden_final_168h_campaign_hours")
    for marker in FORBIDDEN_MARKERS:
        if marker in normalized_command:
            reasons.append(f"forbidden_marker:{marker}")
    return {
        "allowed": not reasons,
        "reasons": reasons,
        "has_dry_run_or_no_write_guard": has_dry_guard,
        "is_live_baseline": is_live_baseline,
        "campaign_hours": campaign_hours,
        "non_production_local_tuning": True,
        "profile_is_experimental_local": True,
        "final_168h_started": False,
        "final_168h_authorized": False,
        "production_long_run_started": False,
        "checkpoint_written": False,
        "checkpoint_write_or_import_back_authorized": False,
        "runtime_elimination_enabled": False,
        "proof_source_mutated": False,
        "preflight_mutated": False,
        "release_viewer_frontdoor_promoted": False,
    }


def _extract_campaign_hours(lower_tokens: list[str]) -> float | None:
    for index, token in enumerate(lower_tokens):
        if token == "--campaign-hours" and index + 1 < len(lower_tokens):
            return _float_or_none(lower_tokens[index + 1])
        if token.startswith("--campaign-hours="):
            return _float_or_none(token.split("=", 1)[1])
    return None


def render_run_summary_markdown(summary: Mapping[str, Any]) -> str:
    telemetry = _mapping(summary.get("telemetry_summary"))
    safety = _mapping(summary.get("safety"))
    lines = [
        "# Phase3B Local Tuning Run",
        "",
        f"- Profile: `{summary.get('profile_id')}`",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Return code: `{summary.get('return_code')}`",
        f"- Duration seconds: `{summary.get('duration_seconds')}`",
        f"- Final 168h started: `{safety.get('final_168h_started')}`",
        f"- Checkpoint written: `{safety.get('checkpoint_written')}`",
        f"- Proof source mutated: `{safety.get('proof_source_mutated')}`",
        "",
        "## Telemetry",
        "",
        f"- Samples: `{telemetry.get('sample_count', 0)}`",
        f"- Peak process count: `{telemetry.get('peak_process_count', 0)}`",
        f"- Peak thread count: `{telemetry.get('peak_thread_count', 0)}`",
        f"- Peak RSS bytes: `{telemetry.get('peak_total_rss_bytes', 0)}`",
        f"- Peak private bytes: `{telemetry.get('peak_total_private_bytes', 0)}`",
        f"- Peak CPU percent: `{telemetry.get('peak_total_cpu_percent', 0.0)}`",
        "",
        "## Command",
        "",
        "```text",
        " ".join(str(part) for part in summary.get("command", [])),
        "```",
    ]
    return "\n".join(lines) + "\n"


MIN_SYSTEM_AVAILABLE_GIB = 4.0


def _system_available_gib() -> float:
    try:
        mem = psutil.virtual_memory()
        return float(mem.available) / (1024 ** 3)
    except Exception:
        return 999.0


def _run_command_with_telemetry(
    *,
    command: Sequence[str],
    cwd: Path,
    raw_log_path: Path,
    telemetry_path: Path,
    sample_interval_seconds: float,
    timeout_seconds: float,
    env_overrides: Mapping[str, str] | None = None,
) -> tuple[int | None, bool]:
    raw_log_path.parent.mkdir(parents=True, exist_ok=True)
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    run_env = None
    if env_overrides:
        run_env = {**os.environ, **env_overrides}
    with raw_log_path.open("w", encoding="utf-8", errors="replace") as raw_log:
        raw_log.write("$ " + " ".join(str(part) for part in command) + "\n")
        if env_overrides:
            raw_log.write("env: " + " ".join(f"{k}={v}" for k, v in env_overrides.items()) + "\n")
        raw_log.flush()
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd),
            stdout=raw_log,
            stderr=subprocess.STDOUT,
            text=True,
            env=run_env,
        )
        sampler = ProcessTreeSampler(process.pid)
        deadline = time.time() + max(float(timeout_seconds), 0.1)
        timed_out = False
        oom_killed = False
        while process.poll() is None:
            try:
                append_jsonl(telemetry_path, sampler.sample())
            except OSError:
                pass
            avail_gib = _system_available_gib()
            if avail_gib < MIN_SYSTEM_AVAILABLE_GIB:
                raw_log.write(
                    f"\n[MEMORY GUARDIAN] System available RAM {avail_gib:.1f} GiB "
                    f"< {MIN_SYSTEM_AVAILABLE_GIB} GiB threshold — killing solver to protect system\n"
                )
                raw_log.flush()
                oom_killed = True
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                break
            if time.time() >= deadline:
                timed_out = True
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                break
            time.sleep(max(float(sample_interval_seconds), 0.05))
        try:
            append_jsonl(telemetry_path, sampler.sample())
        except OSError:
            pass
        return process.returncode, timed_out or oom_killed


def _campaign_telemetry_snapshot(project_root: Path) -> dict[str, Any]:
    telemetry_path = project_root / "data" / "checkpoints" / "exact_campaign_telemetry.json"
    if not telemetry_path.exists():
        return {
            "schema": "phase3b-local-tuning-campaign-telemetry-snapshot/v0",
            "exists": False,
            "path": str(telemetry_path),
            "snapshot_is_proof_source": False,
        }
    try:
        payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "schema": "phase3b-local-tuning-campaign-telemetry-snapshot/v0",
            "exists": True,
            "path": str(telemetry_path),
            "load_error": f"{type(exc).__name__}: {exc}",
            "snapshot_is_proof_source": False,
        }
    return {
        "schema": "phase3b-local-tuning-campaign-telemetry-snapshot/v0",
        "exists": True,
        "path": str(telemetry_path),
        "snapshot_is_proof_source": False,
        "payload": payload,
    }


def _default_run_id(profile_id: str) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    return f"{profile_id}_{stamp}"


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())

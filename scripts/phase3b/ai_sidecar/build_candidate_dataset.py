"""Build S4 AI dataset v0 from S3/S5 tuning campaign telemetry.

Reads campaign_telemetry_snapshot.json and run_summary.json from each tuning
profile run, adapts them into the acceptance-like format that
feature_extract.extract_candidate_run_samples() expects, then writes
candidate_runs.jsonl + feature_schema.json + dataset_summary.json.

This is a shadow-only read operation — no canonical paths are modified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_accel.feature_extract import (
    build_feature_dataset_summary,
    build_feature_schema,
    extract_candidate_run_samples,
    stable_json_dumps,
    write_candidate_runs_jsonl,
)
from src.ai_accel.schemas import build_ai_dataset_safety_contract
from src.search.exact_campaign import now_iso

TUNING_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
CAMPAIGN_BACKUP = (
    PROJECT_ROOT
    / ".artifacts"
    / "phase3b_accel_tuning"
    / "00_baseline"
    / "campaign_backup_20260506"
)
OUTPUT_ROOT = (
    PROJECT_ROOT / ".artifacts" / "phase3b_ai_accel_20260429" / "01_feature_dataset"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_valid_tuning_runs() -> list[dict[str, Any]]:
    """Find tuning runs that have both run_summary and campaign_telemetry_snapshot with data."""
    runs: list[dict[str, Any]] = []
    for run_dir in sorted(TUNING_ROOT.iterdir()):
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "run_summary.json"
        telemetry_path = run_dir / "campaign_telemetry_snapshot.json"
        if not summary_path.exists() or not telemetry_path.exists():
            continue
        summary = _load_json(summary_path)
        telemetry = _load_json(telemetry_path)
        # Only include runs with actual campaign data
        if not telemetry.get("exists", False):
            continue
        runs.append({
            "run_dir": str(run_dir),
            "summary": summary,
            "campaign_telemetry": telemetry,
        })
    # Also check campaign backup from S3
    backup_telemetry_path = CAMPAIGN_BACKUP / "exact_campaign_telemetry.json"
    if backup_telemetry_path.exists():
        telemetry = _load_json(backup_telemetry_path)
        runs.append({
            "run_dir": str(CAMPAIGN_BACKUP),
            "summary": _make_backup_summary(),
            "campaign_telemetry": telemetry,
        })
    return runs


def _make_backup_summary() -> dict[str, Any]:
    """Synthesize a summary for the campaign backup (S3 baseline)."""
    return {
        "profile_id": "s3_baseline_campaign_backup",
        "env_overrides": {},
        "duration_seconds": 0,
        "telemetry_summary": {},
    }


def _adapt_to_acceptance_payload(
    campaign_telemetry: dict[str, Any],
    run_summary: dict[str, Any],
) -> dict[str, Any]:
    """Convert campaign telemetry + run summary into an acceptance-like payload.

    The existing feature_extract.extract_candidate_run_samples() expects:
    - run_records[].campaign_wave_summaries[].candidate_results[]
    - run_records[].target == "production-campaign-run"
    - run_records[].label or inferred profile_id
    - run_records[].worker_profile, process_count, etc.
    """
    profile_id = run_summary.get("profile_id", "unknown")
    env = run_summary.get("env_overrides", {})
    workers_env = env.get("EXACT_CP_SAT_WORKERS")

    # Extract command to find parallel_processes
    command = run_summary.get("command", [])
    parallel_processes = None
    for i, token in enumerate(command):
        if token == "--parallel-processes" and i + 1 < len(command):
            try:
                parallel_processes = int(command[i + 1])
            except ValueError:
                pass

    # Build worker_profile from env override
    worker_count = int(workers_env) if workers_env else None
    worker_profile = {}
    if worker_count is not None:
        worker_profile = {
            "master": worker_count,
            "local_capacity": worker_count,
            "binding": min(worker_count, 4),  # binding capped at 4 in defaults
            "routing": worker_count,
        }

    # Adapt waves
    waves = campaign_telemetry.get("waves", [])
    if not waves and "snapshot" in campaign_telemetry:
        # Some snapshots embed the data differently
        snapshot = campaign_telemetry["snapshot"]
        waves = snapshot.get("waves", [])

    adapted_waves = []
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        adapted_waves.append({
            "wave_index": wave.get("wave_index"),
            "candidate_count": wave.get("candidate_count"),
            "elapsed_seconds": wave.get("elapsed_seconds"),
            "peak_rss_bytes_external_total": wave.get("peak_rss_bytes_external_total"),
            "candidate_results": wave.get("candidate_results", []),
        })

    # Telemetry summary for resource metrics
    ts = run_summary.get("telemetry_summary", {})

    run_record = {
        "target": "production-campaign-run",
        "label": profile_id,
        "process_count": parallel_processes,
        "parallel_processes": parallel_processes,
        "worker_count_per_process": worker_count,
        "worker_profile": worker_profile,
        "peak_rss_bytes_external_total": ts.get("peak_total_rss_bytes"),
        "avg_process_cpu_pct": ts.get("peak_total_cpu_percent"),
        "campaign_wave_summaries": adapted_waves,
    }

    return {
        "run_records": [run_record],
        "logical_cpu_count": 24,  # i9-13900KS HT-off
    }


def main() -> None:
    print("=" * 60)
    print("S4: AI dataset v0 shadow — feature extraction")
    print("=" * 60)

    runs = _find_valid_tuning_runs()
    print(f"\nFound {len(runs)} tuning runs with campaign telemetry:")
    for run in runs:
        run_dir = Path(run["run_dir"]).name
        s = run["summary"]
        telemetry = run["campaign_telemetry"]
        wave_count = len(telemetry.get("waves", []))
        print(f"  {run_dir}: profile={s.get('profile_id', '?')}, waves={wave_count}")

    # Extract candidate samples from all runs
    all_samples: list[dict[str, Any]] = []
    for run in runs:
        acceptance_payload = _adapt_to_acceptance_payload(
            campaign_telemetry=run["campaign_telemetry"],
            run_summary=run["summary"],
        )
        samples = extract_candidate_run_samples(acceptance_payload)
        print(f"  -> Extracted {len(samples)} candidate samples from {Path(run['run_dir']).name}")
        all_samples.extend(samples)

    print(f"\nTotal candidate samples: {len(all_samples)}")

    if not all_samples:
        print("\n[!] No candidate samples extracted. This may be because:")
        print("    - Campaign telemetry snapshots don't have candidate_results")
        print("    - Short runs didn't complete any waves")
        print("    Writing empty dataset with schema only.")

    # Write outputs
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # 1. candidate_runs.jsonl
    jsonl_path = OUTPUT_ROOT / "candidate_runs.jsonl"
    write_candidate_runs_jsonl(jsonl_path, all_samples)
    print(f"\nWritten: {jsonl_path} ({len(all_samples)} samples)")

    # 2. feature_schema.json
    schema = build_feature_schema()
    schema_path = OUTPUT_ROOT / "feature_schema.json"
    schema_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Written: {schema_path}")

    # 3. dataset_summary.json
    summary = build_feature_dataset_summary(
        all_samples,
        acceptance_summary_path=TUNING_ROOT,
        scorecard_path=PROJECT_ROOT
        / ".artifacts"
        / "phase3b_accel_tuning"
        / "00_baseline"
        / "baseline_scorecard.json",
    )
    summary_path = OUTPUT_ROOT / "dataset_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Written: {summary_path}")

    # 4. Idempotency check — extract again and compare
    print("\n--- Idempotency check ---")
    all_samples_2: list[dict[str, Any]] = []
    for run in runs:
        acceptance_payload = _adapt_to_acceptance_payload(
            campaign_telemetry=run["campaign_telemetry"],
            run_summary=run["summary"],
        )
        all_samples_2.extend(extract_candidate_run_samples(acceptance_payload))

    s1 = [stable_json_dumps(s) for s in all_samples]
    s2 = [stable_json_dumps(s) for s in all_samples_2]
    if s1 == s2:
        print("PASS: Repeated extraction produces identical output")
    else:
        print(f"FAIL: Output differs ({len(s1)} vs {len(s2)} samples)")

    # Safety summary
    print("\n--- Safety ---")
    print(f"  shadow_only: True")
    print(f"  proof_source: False")
    print(f"  canonical_write: False")
    print(f"  scheduler_integration: False")


if __name__ == "__main__":
    main()

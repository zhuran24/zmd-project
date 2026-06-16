from __future__ import annotations

import concurrent.futures
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from src.models.master_model import load_generic_io_requirements_artifact, load_project_data
from src.runtime.process_tree_telemetry import (
    ProcessTreeSampler,
    append_jsonl,
    read_telemetry_jsonl,
    summarize_telemetry_samples,
)
from src.runtime.sensitive_path_audit import (
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
    fingerprint_path,
)
from src.search.benders_loop import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    compute_exact_static_area_lower_bound,
)
from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.exact_parallel_scheduler import (
    ExactParallelWorkerPool,
    ParallelWaveExecution,
    build_parallel_worker_tasks,
)
from src.search.outer_search import (
    _candidate_key,
    _compute_exact_frontier_state,
    _select_parallel_wave_candidate_entries,
    generate_candidate_sizes,
)

LOCAL_TUNING_NAMESPACE = "phase3b_local_13900ks_tuning_20260430"
LOCAL_TUNING_LOG_NAMESPACE = "local_13900ks_tuning_20260430"
EVALUATOR_SUBDIR = "08_checkpoint_free_evaluator"
ARTIFACT_ROOT = Path(".artifacts") / LOCAL_TUNING_NAMESPACE / EVALUATOR_SUBDIR
LOG_ROOT = Path(".codex_test_logs/phase3b") / LOCAL_TUNING_LOG_NAMESPACE / EVALUATOR_SUBDIR
DEFAULT_READINESS_PACKET = (
    Path(".artifacts")
    / LOCAL_TUNING_NAMESPACE
    / "07_short_run_readiness"
    / "short_run_readiness_packet.json"
)
ALLOWED_DURATIONS_SECONDS = (300, 600)
CHECKPOINT_FREE_SCHEMA = "phase3b-checkpoint-free-evaluator/v0"
DEFAULT_MAX_TOTAL_PRIVATE_GIB = 44.0
DEFAULT_MAX_TOTAL_RSS_GIB: float | None = None
FORBIDDEN_EXTRA_TOKENS = {
    "--resume-campaign",
    "-resumecampaign",
    "--write-checkpoint",
    "--import-checkpoint",
    "--checkpoint-write",
    "--checkpoint-import",
    "--checkpoint-output",
}
FORBIDDEN_OUTPUT_MARKERS = (
    "data/checkpoints",
    "final_solution.json",
    "optimal_blueprint.json",
    "certified_delivery_manifest.json",
    "preflight_summary.json",
    "viewer",
    "release",
    "frontdoor",
    "proof-source",
    "proof_source",
)

WorkerPoolFactory = Callable[..., ExactParallelWorkerPool]


def validate_checkpoint_free_request(
    *,
    duration_seconds: int,
    artifact_root: Path,
    log_root: Path,
    extra_tokens: Sequence[str] = (),
) -> dict[str, Any]:
    reasons: list[str] = []
    if int(duration_seconds) not in set(ALLOWED_DURATIONS_SECONDS):
        reasons.append(f"unsupported_duration_seconds:{duration_seconds}")
    for token in extra_tokens:
        lowered = str(token).strip().lower().replace("\\", "/")
        if lowered in FORBIDDEN_EXTRA_TOKENS:
            reasons.append(f"forbidden_cli_token:{token}")
        elif any(marker in lowered for marker in FORBIDDEN_OUTPUT_MARKERS):
            reasons.append(f"forbidden_cli_marker:{token}")
        else:
            reasons.append(f"unsupported_extra_cli_token:{token}")
    for label, path, namespace in (
        ("artifact_root", Path(artifact_root), LOCAL_TUNING_NAMESPACE),
        ("log_root", Path(log_root), LOCAL_TUNING_LOG_NAMESPACE),
    ):
        normalized = str(path).replace("\\", "/")
        lowered = normalized.lower()
        if namespace.lower() not in lowered or EVALUATOR_SUBDIR.lower() not in lowered:
            reasons.append(f"{label}_outside_checkpoint_free_namespace:{path}")
        if any(marker in lowered for marker in FORBIDDEN_OUTPUT_MARKERS):
            reasons.append(f"{label}_contains_forbidden_marker:{path}")
    return {
        "allowed": not reasons,
        "reasons": reasons,
        "duration_seconds": int(duration_seconds),
        "allowed_durations_seconds": list(ALLOWED_DURATIONS_SECONDS),
        "checkpoint_free": True,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "proof_source": False,
        "checkpoint_written": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
    }


def build_checkpoint_free_run_plan(
    *,
    project_root: Path,
    readiness_packet_path: Path,
    candidate_id: str,
    duration_seconds: int,
    artifact_root: Path | None = None,
    log_root: Path | None = None,
    run_id: str | None = None,
    max_wave_candidates: int | None = None,
    wave_candidate_keys: Sequence[str] = (),
    exclude_wave_candidate_keys: Sequence[str] = (),
    max_total_private_gib: float | None = DEFAULT_MAX_TOTAL_PRIVATE_GIB,
    max_total_rss_gib: float | None = DEFAULT_MAX_TOTAL_RSS_GIB,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    readiness_packet_path = _resolve_path(project_root, readiness_packet_path)
    artifact_root = _resolve_output_root(project_root, artifact_root or ARTIFACT_ROOT)
    log_root = _resolve_output_root(project_root, log_root or LOG_ROOT)
    guard = validate_checkpoint_free_request(
        duration_seconds=int(duration_seconds),
        artifact_root=artifact_root,
        log_root=log_root,
    )
    if not guard["allowed"]:
        raise ValueError("Unsafe checkpoint-free evaluator request: " + "; ".join(guard["reasons"]))

    packet = _load_json_mapping(readiness_packet_path)
    candidate = _candidate_from_readiness(packet, str(candidate_id))
    process_count = max(1, int(candidate.get("process_count", 1)))
    explicit_candidate_keys = _normalize_candidate_keys(wave_candidate_keys)
    excluded_candidate_keys = _normalize_candidate_keys(exclude_wave_candidate_keys)
    overlap = sorted(set(explicit_candidate_keys) & set(excluded_candidate_keys))
    if overlap:
        raise ValueError(
            "Requested wave_candidate_keys overlap exclude_wave_candidate_keys: "
            + ", ".join(overlap)
        )
    default_wave = len(explicit_candidate_keys) if explicit_candidate_keys else process_count
    max_wave = max(1, int(max_wave_candidates or default_wave))
    if explicit_candidate_keys and len(explicit_candidate_keys) > max_wave:
        raise ValueError(
            "Requested wave_candidate_keys exceed max_wave_candidates: "
            f"{len(explicit_candidate_keys)} > {max_wave}"
        )
    frontier_probe_mode = str(candidate.get("frontier_probe_mode") or "off")
    wave_entries = select_checkpoint_free_wave_entries(
        project_root=project_root,
        process_count=process_count,
        max_wave_candidates=max_wave,
        frontier_probe_mode=frontier_probe_mode,
        wave_candidate_keys=explicit_candidate_keys,
        exclude_wave_candidate_keys=excluded_candidate_keys,
    )
    run_id = run_id or _default_run_id(str(candidate_id), int(duration_seconds))
    artifact_dir = artifact_root / run_id
    log_dir = log_root / run_id
    solve_budgets = _solve_budgets(int(duration_seconds))
    return {
        "schema": CHECKPOINT_FREE_SCHEMA,
        "plan_kind": "checkpoint_free_short_run_plan",
        "generated_at": now_iso(),
        "project_root": str(project_root),
        "run_id": str(run_id),
        "candidate_id": str(candidate_id),
        "duration_seconds": int(duration_seconds),
        "artifact_dir": str(artifact_dir),
        "log_dir": str(log_dir),
        "readiness_packet": fingerprint_path(
            readiness_packet_path,
            relative_path=str(readiness_packet_path),
        ),
        "candidate_profile": _checkpoint_free_candidate_profile(candidate),
        "wave": {
            "selection_kind": (
                "explicit_frontier_candidate_key_v0"
                if explicit_candidate_keys
                else (
                    "deterministic_frontier_bounded_wave_excluding_keys_v0"
                    if excluded_candidate_keys
                    else "deterministic_frontier_bounded_wave_v0"
                )
            ),
            "max_wave_candidates": int(max_wave),
            "selected_count": len(wave_entries),
            "requested_candidate_keys": explicit_candidate_keys,
            "excluded_candidate_keys": excluded_candidate_keys,
            "entries": wave_entries,
        },
        "solve_budgets": solve_budgets,
        "resource_stop_rules": _resource_stop_rules(
            max_total_private_gib=max_total_private_gib,
            max_total_rss_gib=max_total_rss_gib,
        ),
        "safety": guard,
    }


def select_checkpoint_free_wave_entries(
    *,
    project_root: Path,
    process_count: int,
    max_wave_candidates: int,
    frontier_probe_mode: str,
    wave_candidate_keys: Sequence[str] = (),
    exclude_wave_candidate_keys: Sequence[str] = (),
) -> list[dict[str, Any]]:
    exact_instances, facility_pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)
    grid = dict(rules["globals"]["grid"])
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])
    safe_area_upper_bound = grid_w * grid_h - compute_exact_static_area_lower_bound(
        exact_instances,
        rules,
        generic_io_requirements,
        facility_pools=facility_pools,
    )
    candidates = generate_candidate_sizes(
        max_w=grid_w,
        max_h=grid_h,
        min_side=6,
        area_upper_bound=safe_area_upper_bound,
    )
    frontier_state = _compute_exact_frontier_state(
        candidates,
        None,
        grid_w=grid_w,
        grid_h=grid_h,
        frontier_probe_mode=frontier_probe_mode,
    )
    explicit_candidate_keys = _normalize_candidate_keys(wave_candidate_keys)
    excluded_candidate_keys = _normalize_candidate_keys(exclude_wave_candidate_keys)
    overlap = sorted(set(explicit_candidate_keys) & set(excluded_candidate_keys))
    if overlap:
        raise ValueError(
            "Requested wave_candidate_keys overlap exclude_wave_candidate_keys: "
            + ", ".join(overlap)
        )
    if explicit_candidate_keys:
        if len(explicit_candidate_keys) > max(1, int(max_wave_candidates)):
            raise ValueError(
                "Requested wave_candidate_keys exceed max_wave_candidates: "
                f"{len(explicit_candidate_keys)} > {max_wave_candidates}"
            )
        return _explicit_frontier_wave_entries(
            frontier_state,
            candidate_keys=explicit_candidate_keys,
        )
    if excluded_candidate_keys:
        return _select_wave_entries_excluding_keys(
            frontier_state=frontier_state,
            process_count=process_count,
            max_wave_candidates=max_wave_candidates,
            excluded_candidate_keys=excluded_candidate_keys,
        )
    entries = _select_parallel_wave_candidate_entries(
        frontier_state,
        parallel_processes=max(1, int(process_count)),
        remaining_attempt_budget=max(1, int(max_wave_candidates)),
    )
    return [_normalize_wave_entry(entry) for entry in entries]


def run_checkpoint_free_evaluator(
    *,
    project_root: Path,
    readiness_packet_path: Path = DEFAULT_READINESS_PACKET,
    candidate_id: str = "B0_prod_4x4",
    duration_seconds: int = 300,
    execute: bool = False,
    artifact_root: Path | None = None,
    log_root: Path | None = None,
    run_id: str | None = None,
    max_wave_candidates: int | None = None,
    wave_candidate_keys: Sequence[str] = (),
    exclude_wave_candidate_keys: Sequence[str] = (),
    sample_interval_seconds: float = 0.5,
    max_total_private_gib: float | None = DEFAULT_MAX_TOTAL_PRIVATE_GIB,
    max_total_rss_gib: float | None = DEFAULT_MAX_TOTAL_RSS_GIB,
    worker_pool_factory: WorkerPoolFactory = ExactParallelWorkerPool,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    plan = build_checkpoint_free_run_plan(
        project_root=project_root,
        readiness_packet_path=readiness_packet_path,
        candidate_id=candidate_id,
        duration_seconds=duration_seconds,
        artifact_root=artifact_root,
        log_root=log_root,
        run_id=run_id,
        max_wave_candidates=max_wave_candidates,
        wave_candidate_keys=wave_candidate_keys,
        exclude_wave_candidate_keys=exclude_wave_candidate_keys,
        max_total_private_gib=max_total_private_gib,
        max_total_rss_gib=max_total_rss_gib,
    )
    artifact_dir = Path(str(plan["artifact_dir"]))
    log_dir = Path(str(plan["log_dir"]))
    _assert_checkpoint_free_namespace(artifact_dir, required_namespace=LOCAL_TUNING_NAMESPACE)
    _assert_checkpoint_free_namespace(log_dir, required_namespace=LOCAL_TUNING_LOG_NAMESPACE)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    paths = _run_paths(artifact_dir=artifact_dir, log_dir=log_dir)
    before = build_sensitive_path_fingerprint(project_root)
    atomic_write_json(paths["sensitive_before"], before)
    atomic_write_json(paths["run_plan"], plan)
    paths["results_jsonl"].write_text("", encoding="utf-8")
    paths["stage_heartbeats_jsonl"].write_text("", encoding="utf-8")

    started_at = now_iso()
    start_time = time.time()
    execution_payload: dict[str, Any]
    if execute:
        execution_payload = _execute_checkpoint_free_wave(
            project_root=project_root,
            plan=plan,
            results_jsonl_path=paths["results_jsonl"],
            telemetry_path=paths["telemetry_jsonl"],
            stage_heartbeat_path=paths["stage_heartbeats_jsonl"],
            sample_interval_seconds=sample_interval_seconds,
            worker_pool_factory=worker_pool_factory,
        )
    else:
        append_jsonl(paths["telemetry_jsonl"], ProcessTreeSampler(os.getpid()).sample())
        execution_payload = {
            "status": "planned_only",
            "execute": False,
            "worker_pool_started": False,
            "result_count": 0,
            "stage_heartbeat_count": 0,
            "failure_reason": None,
            "timed_out": False,
        }

    after = build_sensitive_path_fingerprint(project_root)
    comparison = compare_sensitive_path_fingerprints(before, after)
    atomic_write_json(paths["sensitive_after"], after)
    atomic_write_json(paths["sensitive_comparison"], comparison)
    status = str(execution_payload.get("status") or "failed")
    if bool(comparison.get("changed", False)):
        status = "disqualified_sensitive_path_mutation"

    telemetry_summary = summarize_telemetry_samples(read_telemetry_jsonl(paths["telemetry_jsonl"]))
    summary = {
        "schema": CHECKPOINT_FREE_SCHEMA,
        "summary_kind": "checkpoint_free_short_run_summary",
        "run_id": str(plan["run_id"]),
        "candidate_id": str(plan["candidate_id"]),
        "status": status,
        "execute": bool(execute),
        "started_at": started_at,
        "finished_at": now_iso(),
        "duration_seconds": round(float(time.time() - start_time), 3),
        "requested_duration_seconds": int(duration_seconds),
        "checkpoint_free": True,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "proof_source": False,
        "checkpoint_written": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "execution": execution_payload,
        "resource_stop_rules": dict(_mapping(plan.get("resource_stop_rules"))),
        "telemetry_summary": telemetry_summary,
        "sensitive_path_comparison": comparison,
        "paths": {key: str(path) for key, path in paths.items()},
    }
    atomic_write_json(paths["run_summary_json"], summary)
    _atomic_write_text(paths["run_summary_md"], render_checkpoint_free_summary_markdown(summary))
    return summary


def render_checkpoint_free_summary_markdown(summary: Mapping[str, Any]) -> str:
    execution = _mapping(summary.get("execution"))
    telemetry = _mapping(summary.get("telemetry_summary"))
    comparison = _mapping(summary.get("sensitive_path_comparison"))
    rules = _mapping(summary.get("resource_stop_rules"))
    resource_stop = _mapping(execution.get("resource_stop"))
    wave_diag = _mapping(execution.get("wave_result_diagnostics"))
    lines = [
        "# Phase3B Checkpoint-Free Evaluator V0",
        "",
        f"- Candidate: `{summary.get('candidate_id')}`",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Execute: `{summary.get('execute')}`",
        f"- Requested duration seconds: `{summary.get('requested_duration_seconds')}`",
        f"- Checkpoint-free: `{summary.get('checkpoint_free')}`",
        f"- Main.py executed: `{summary.get('main_py_executed')}`",
        f"- Exact campaign used: `{summary.get('exact_campaign_used')}`",
        f"- Proof source: `{summary.get('proof_source')}`",
        f"- Checkpoint written: `{summary.get('checkpoint_written')}`",
        f"- Candidate universe changed: `{summary.get('candidate_universe_changed')}`",
        f"- Production profile changed: `{summary.get('production_profile_changed')}`",
        f"- Sensitive paths changed: `{comparison.get('changed')}`",
        "",
        "## Execution",
        "",
        f"- Worker pool started: `{execution.get('worker_pool_started')}`",
        f"- Result count: `{execution.get('result_count')}`",
        f"- Timed out: `{execution.get('timed_out')}`",
        f"- Failure reason: `{execution.get('failure_reason')}`",
        f"- Resource stop triggered: `{execution.get('resource_stop_triggered', False)}`",
        f"- Resource stop reason: `{resource_stop.get('reason')}`",
        f"- Resource stop max private GiB: `{rules.get('max_total_private_gib')}`",
        f"- Resource stop max RSS GiB: `{rules.get('max_total_rss_gib')}`",
        f"- Stage heartbeats: `{execution.get('stage_heartbeat_count', 0)}`",
        f"- Planned wave candidates: `{wave_diag.get('planned_count')}`",
        f"- Completed wave candidates: `{wave_diag.get('completed_count')}`",
        f"- Pending wave candidates: `{wave_diag.get('pending_candidate_keys')}`",
        f"- Straggler candidates: `{wave_diag.get('straggler_candidate_keys')}`",
        "",
        "## Telemetry",
        "",
        f"- Samples: `{telemetry.get('sample_count', 0)}`",
        f"- Peak process count: `{telemetry.get('peak_process_count', 0)}`",
        f"- Peak RSS bytes: `{telemetry.get('peak_total_rss_bytes', 0)}`",
    ]
    return "\n".join(lines) + "\n"


def _execute_checkpoint_free_wave(
    *,
    project_root: Path,
    plan: Mapping[str, Any],
    results_jsonl_path: Path,
    telemetry_path: Path,
    stage_heartbeat_path: Path,
    sample_interval_seconds: float,
    worker_pool_factory: WorkerPoolFactory,
) -> dict[str, Any]:
    profile = _mapping(plan.get("candidate_profile"))
    env = {str(key): str(value) for key, value in _mapping(profile.get("env")).items()}
    process_count = max(1, int(profile.get("process_count", 1)))
    solve_budgets = _mapping(plan.get("solve_budgets"))
    wave = _mapping(plan.get("wave"))
    wave_entries = [
        _mapping(entry)
        for entry in list(wave.get("entries", []))
        if isinstance(entry, Mapping)
    ]
    candidates = [tuple(int(value) for value in entry.get("candidate", [])) for entry in wave_entries]
    tasks = build_parallel_worker_tasks(
        candidates=candidates,
        attempt_start=0,
        attempt_indices=list(range(1, len(candidates) + 1)),
        master_seconds=float(solve_budgets.get("master_seconds", plan.get("duration_seconds", 300))),
        binding_seconds=float(solve_budgets.get("binding_seconds", plan.get("duration_seconds", 300))),
        routing_seconds=float(solve_budgets.get("routing_seconds", plan.get("duration_seconds", 300))),
        flow_seconds=float(solve_budgets.get("flow_seconds", 60.0)),
        benders_max_iter=int(solve_budgets.get("benders_max_iter", 30)),
        disable_master_warm_start=bool(solve_budgets.get("disable_master_warm_start", False)),
        preloaded_cut_map={},
    )
    timeout_seconds = float(plan.get("duration_seconds", 300)) + 30.0
    pool = worker_pool_factory(
        process_count=process_count,
        project_root=project_root,
        solve_mode="certified_exact",
        master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    sampler = ProcessTreeSampler(os.getpid())
    started = time.time()
    timed_out = False
    wave_execution: ParallelWaveExecution | None = None
    resource_stopped = False
    resource_stop_payload: dict[str, Any] | None = None
    resource_rules = _mapping(plan.get("resource_stop_rules"))
    max_total_private_bytes = _optional_positive_int(resource_rules.get("max_total_private_bytes"))
    max_total_rss_bytes = _optional_positive_int(resource_rules.get("max_total_rss_bytes"))
    with _temporary_env(env):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(pool.run_wave, tasks)
        try:
            while True:
                sample = sampler.sample()
                append_jsonl(telemetry_path, sample)
                resource_stop_payload = _resource_stop_trigger(
                    sample,
                    max_total_private_bytes=max_total_private_bytes,
                    max_total_rss_bytes=max_total_rss_bytes,
                )
                if resource_stop_payload is not None:
                    resource_stopped = True
                    pool.terminate()
                    try:
                        wave_execution = future.result(timeout=10.0)
                    except Exception:
                        wave_execution = None
                    break
                try:
                    wave_execution = future.result(timeout=max(float(sample_interval_seconds), 0.05))
                    break
                except concurrent.futures.TimeoutError:
                    if time.time() - started >= timeout_seconds:
                        timed_out = True
                        pool.terminate()
                        try:
                            wave_execution = future.result(timeout=10.0)
                        except Exception:
                            wave_execution = None
                        break
                    continue
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            if not timed_out and not resource_stopped:
                try:
                    pool.close()
                except Exception:
                    pool.terminate()
            append_jsonl(telemetry_path, sampler.sample())

    result_count = 0
    if resource_stopped:
        failure_reason = "checkpoint_free_resource_stop_limit_exceeded"
    elif timed_out:
        failure_reason = "checkpoint_free_wave_timeout"
    else:
        failure_reason = None
    completed = False
    if wave_execution is not None:
        completed = bool(getattr(wave_execution, "completed", False))
        failure_reason = failure_reason or getattr(wave_execution, "failure_reason", None)
        for result in tuple(getattr(wave_execution, "results", tuple())):
            append_jsonl(results_jsonl_path, _worker_result_to_json(result))
            result_count += 1
    stage_heartbeat_count = 0
    if wave_execution is not None:
        for event in tuple(getattr(wave_execution, "heartbeat_events", tuple()) or tuple()):
            if isinstance(event, Mapping):
                append_jsonl(stage_heartbeat_path, dict(event))
                stage_heartbeat_count += 1
    wave_diagnostics = _wave_result_diagnostics(
        tasks=tasks,
        wave_execution=wave_execution,
        timed_out=timed_out,
        resource_stopped=resource_stopped,
    )
    return {
        "status": (
            "stopped_resource_limit"
            if resource_stopped
            else ("timeout" if timed_out else ("completed" if completed else "failed"))
        ),
        "execute": True,
        "worker_pool_started": True,
        "result_count": int(result_count),
        "stage_heartbeat_count": int(stage_heartbeat_count),
        "failure_reason": failure_reason,
        "timed_out": bool(timed_out),
        "resource_stop_triggered": bool(resource_stopped),
        "resource_stop": resource_stop_payload,
        "resource_stop_rules": dict(resource_rules),
        "wave_result_diagnostics": wave_diagnostics,
        "elapsed_seconds": None if wave_execution is None else float(wave_execution.elapsed_seconds),
        "peak_rss_bytes_external_total": None
        if wave_execution is None
        else int(wave_execution.peak_rss_bytes_external_total),
        "peak_rss_bytes_internal_max_single_process": None
        if wave_execution is None
        else int(wave_execution.peak_rss_bytes_internal_max_single_process),
    }


def _checkpoint_free_candidate_profile(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": str(candidate.get("candidate_id")),
        "source_kind": str(candidate.get("source_kind")),
        "source_profile_id": str(candidate.get("source_profile_id")),
        "process_count": int(candidate.get("process_count", 1)),
        "env": dict(_mapping(candidate.get("env"))),
        "risk": dict(_mapping(candidate.get("risk"))),
        "process_priority": str(candidate.get("process_priority") or "normal"),
        "frontier_probe_mode": str(candidate.get("frontier_probe_mode") or "off"),
        "worker_profile_kind": candidate.get("worker_profile_kind"),
        "global_workers": candidate.get("global_workers"),
        "stage_workers": candidate.get("stage_workers"),
        "total_worker_slots": candidate.get("total_worker_slots"),
        "max_stage_worker_slots": candidate.get("max_stage_worker_slots"),
        "execution_enabled": False,
        "checkpoint_free_execution_requires_explicit_execute": True,
        "proof_source": False,
        "checkpoint_written": False,
    }


def _candidate_from_readiness(packet: Mapping[str, Any], candidate_id: str) -> Mapping[str, Any]:
    for candidate in list(packet.get("candidates", []) or []):
        if isinstance(candidate, Mapping) and str(candidate.get("candidate_id")) == str(candidate_id):
            return candidate
    raise ValueError(f"Candidate not found in readiness packet: {candidate_id}")


def _normalize_wave_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    candidate = tuple(int(value) for value in entry.get("candidate", ()))
    return {
        "candidate": [int(value) for value in candidate],
        "candidate_key": _candidate_key(candidate),
        "selection_reason": str(entry.get("selection_reason") or "unknown"),
        "wave_slot_index": int(entry.get("wave_slot_index", 0)),
        "probe_candidate": bool(entry.get("probe_candidate", False)),
        "probe_prune_gain": int(entry.get("probe_prune_gain", 0)),
        "probe_resume_pending": bool(entry.get("probe_resume_pending", False)),
        "frontier_probe_mode": str(entry.get("frontier_probe_mode") or "off"),
    }


def _explicit_frontier_wave_entries(
    frontier_state: Mapping[str, Any],
    *,
    candidate_keys: Sequence[str],
) -> list[dict[str, Any]]:
    normalized_keys = _normalize_candidate_keys(candidate_keys)
    frontier_by_key = {
        _candidate_key(tuple(candidate)): tuple(candidate)
        for candidate in list(frontier_state.get("frontier", []) or [])
    }
    missing = [key for key in normalized_keys if key not in frontier_by_key]
    if missing:
        raise ValueError(
            "Requested checkpoint-free wave candidate key is not in the current frontier: "
            + ", ".join(missing)
        )
    entries = []
    for index, key in enumerate(normalized_keys):
        entries.append(
            _normalize_wave_entry(
                {
                    "candidate": frontier_by_key[key],
                    "selection_reason": "explicit_candidate_key",
                    "wave_slot_index": index,
                    "probe_candidate": False,
                    "probe_prune_gain": 0,
                    "probe_resume_pending": False,
                    "frontier_probe_mode": str(
                        frontier_state.get("frontier_probe_mode") or "off"
                    ),
                }
            )
        )
    return entries


def _select_wave_entries_excluding_keys(
    *,
    frontier_state: Mapping[str, Any],
    process_count: int,
    max_wave_candidates: int,
    excluded_candidate_keys: Sequence[str],
) -> list[dict[str, Any]]:
    max_wave = max(1, int(max_wave_candidates))
    excluded = set(_normalize_candidate_keys(excluded_candidate_keys))
    initial_budget = max_wave + len(excluded)
    parallel_counts = [
        max(1, int(process_count)),
        max(1, int(process_count), int(initial_budget)),
    ]
    best_filtered: list[dict[str, Any]] = []
    for parallel_processes in parallel_counts:
        raw_entries = _select_parallel_wave_candidate_entries(
            frontier_state,
            parallel_processes=parallel_processes,
            remaining_attempt_budget=max(1, int(initial_budget)),
        )
        filtered: list[dict[str, Any]] = []
        for entry in raw_entries:
            candidate = tuple(int(value) for value in entry.get("candidate", ()))
            candidate_key = _candidate_key(candidate)
            if candidate_key in excluded:
                continue
            normalized = _normalize_wave_entry(entry)
            normalized["original_wave_slot_index"] = normalized["wave_slot_index"]
            normalized["wave_slot_index"] = len(filtered)
            filtered.append(normalized)
            if len(filtered) >= max_wave:
                return filtered
        if len(filtered) > len(best_filtered):
            best_filtered = filtered
    return best_filtered


def _normalize_candidate_keys(candidate_keys: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    for raw_key in list(candidate_keys or []):
        key = str(raw_key).strip().lower()
        if not key:
            continue
        if "x" not in key:
            raise ValueError(f"Invalid candidate key, expected WxH: {raw_key}")
        raw_w, raw_h = key.split("x", 1)
        try:
            width = int(raw_w)
            height = int(raw_h)
        except ValueError as exc:
            raise ValueError(f"Invalid candidate key, expected integer WxH: {raw_key}") from exc
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid candidate key, expected positive WxH: {raw_key}")
        normalized_key = f"{width}x{height}"
        if normalized_key in normalized:
            raise ValueError(f"Duplicate checkpoint-free wave candidate key: {normalized_key}")
        normalized.append(normalized_key)
    return normalized


def _solve_budgets(duration_seconds: int) -> dict[str, Any]:
    duration = float(duration_seconds)
    return {
        "master_seconds": duration,
        "binding_seconds": duration,
        "routing_seconds": duration,
        "flow_seconds": min(60.0, duration),
        "benders_max_iter": 30,
        "disable_master_warm_start": False,
        "wall_timeout_seconds": duration + 30.0,
    }


def _resource_stop_rules(
    *,
    max_total_private_gib: float | None,
    max_total_rss_gib: float | None,
) -> dict[str, Any]:
    max_private = _gib_to_bytes(max_total_private_gib)
    max_rss = _gib_to_bytes(max_total_rss_gib)
    return {
        "enabled": bool(max_private is not None or max_rss is not None),
        "source": "process_tree_telemetry.aggregate",
        "action": "terminate_worker_pool_and_mark_stopped_resource_limit",
        "max_total_private_gib": None if max_private is None else round(_bytes_to_gib(max_private), 6),
        "max_total_private_bytes": max_private,
        "max_total_rss_gib": None if max_rss is None else round(_bytes_to_gib(max_rss), 6),
        "max_total_rss_bytes": max_rss,
    }


def _resource_stop_trigger(
    sample: Mapping[str, Any],
    *,
    max_total_private_bytes: int | None,
    max_total_rss_bytes: int | None,
) -> dict[str, Any] | None:
    aggregate = _mapping(sample.get("aggregate"))
    checks = (
        ("total_private_bytes", max_total_private_bytes),
        ("total_rss_bytes", max_total_rss_bytes),
    )
    for metric, limit in checks:
        if limit is None:
            continue
        observed = int(aggregate.get(metric, 0) or 0)
        if observed >= int(limit):
            return {
                "reason": f"{metric}_gte_limit",
                "exceeded_metric": metric,
                "observed_bytes": int(observed),
                "limit_bytes": int(limit),
                "observed_gib": round(_bytes_to_gib(observed), 6),
                "limit_gib": round(_bytes_to_gib(limit), 6),
                "sample_time_unix": sample.get("sample_time_unix"),
            }
    return None


def _gib_to_bytes(value: float | None) -> int | None:
    if value is None:
        return None
    numeric = float(value)
    if numeric <= 0.0:
        return None
    return int(numeric * (1024**3))


def _bytes_to_gib(value: int | float) -> float:
    return float(value) / float(1024**3)


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    numeric = int(value)
    if numeric <= 0:
        return None
    return numeric


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_paths(*, artifact_dir: Path, log_dir: Path) -> dict[str, Path]:
    return {
        "run_plan": artifact_dir / "run_plan.json",
        "results_jsonl": artifact_dir / "checkpoint_free_eval_results.jsonl",
        "run_summary_json": artifact_dir / "run_summary.json",
        "run_summary_md": artifact_dir / "run_summary.md",
        "sensitive_before": artifact_dir / "sensitive_path_before.json",
        "sensitive_after": artifact_dir / "sensitive_path_after.json",
        "sensitive_comparison": artifact_dir / "sensitive_path_comparison.json",
        "telemetry_jsonl": log_dir / "telemetry_samples.jsonl",
        "stage_heartbeats_jsonl": log_dir / "stage_heartbeats.jsonl",
    }


def _worker_result_to_json(result: Any) -> dict[str, Any]:
    if is_dataclass(result):
        payload = asdict(result)
    elif isinstance(result, Mapping):
        payload = dict(result)
    else:
        payload = dict(getattr(result, "__dict__", {}))
    candidate = payload.get("candidate")
    if isinstance(candidate, tuple):
        payload["candidate"] = [int(value) for value in candidate]
    if candidate and "candidate_key" not in payload:
        values = list(candidate)
        if len(values) >= 3:
            payload["candidate_key"] = f"{int(values[1])}x{int(values[2])}"
    return payload


def _wave_result_diagnostics(
    *,
    tasks: Sequence[Any],
    wave_execution: ParallelWaveExecution | None,
    timed_out: bool,
    resource_stopped: bool,
) -> dict[str, Any]:
    planned = [
        {
            "dispatch_seq": int(getattr(task, "dispatch_seq", index)),
            "attempt_index": int(getattr(task, "attempt_index", index + 1)),
            "candidate_key": str(getattr(task, "candidate_key", "")),
        }
        for index, task in enumerate(tasks)
    ]
    results = tuple(getattr(wave_execution, "results", tuple()) or ()) if wave_execution is not None else tuple()
    result_summaries = [_worker_result_summary(result) for result in results]
    completed_dispatches = {int(item["dispatch_seq"]) for item in result_summaries}
    completed_keys = [str(item["candidate_key"]) for item in result_summaries]
    pending = [
        item
        for item in planned
        if int(item["dispatch_seq"]) not in completed_dispatches
    ]
    status_counts: dict[str, int] = {}
    for item in result_summaries:
        status = str(item.get("status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    pending_keys = [str(item["candidate_key"]) for item in pending]
    return {
        "schema": "phase3b-checkpoint-free-wave-result-diagnostics/v0",
        "planned_count": len(planned),
        "completed_count": len(result_summaries),
        "pending_count": len(pending),
        "planned_candidate_keys": [str(item["candidate_key"]) for item in planned],
        "completed_candidate_keys": completed_keys,
        "pending_candidate_keys": pending_keys,
        "straggler_candidate_keys": pending_keys if timed_out else [],
        "interrupted_candidate_keys": pending_keys if resource_stopped else [],
        "timed_out": bool(timed_out),
        "resource_stop_triggered": bool(resource_stopped),
        "status_counts": status_counts,
        "result_summaries": result_summaries,
        "proof_source": False,
        "checkpoint_written": False,
    }


def _worker_result_summary(result: Any) -> dict[str, Any]:
    payload = _worker_result_to_json(result)
    return {
        "dispatch_seq": int(payload.get("dispatch_seq", 0) or 0),
        "attempt_index": int(payload.get("attempt_index", 0) or 0),
        "candidate_key": str(payload.get("candidate_key") or ""),
        "status": str(payload.get("status") or "UNKNOWN"),
        "worker_wall_seconds": _optional_float(payload.get("worker_wall_seconds")),
        "peak_rss_bytes": int(payload.get("peak_rss_bytes", 0) or 0),
        "error": payload.get("error"),
    }


@contextmanager
def _temporary_env(env: Mapping[str, str]) -> Iterator[None]:
    previous: dict[str, str | None] = {}
    try:
        for key, value in env.items():
            previous[str(key)] = os.environ.get(str(key))
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def _assert_checkpoint_free_namespace(path: Path, *, required_namespace: str) -> None:
    normalized = str(Path(path).resolve()).replace("\\", "/").lower()
    if required_namespace.lower() not in normalized or EVALUATOR_SUBDIR.lower() not in normalized:
        raise ValueError(f"Refusing to write outside checkpoint-free evaluator namespace: {path}")


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _resolve_output_root(project_root: Path, path: Path) -> Path:
    return _resolve_path(project_root, path)


def _load_json_mapping(path: Path) -> Mapping[str, Any]:
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _default_run_id(candidate_id: str, duration_seconds: int) -> str:
    safe_candidate = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in candidate_id)
    return f"{safe_candidate}_{int(duration_seconds)}s_{time.strftime('%Y%m%d_%H%M%S', time.gmtime())}"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
